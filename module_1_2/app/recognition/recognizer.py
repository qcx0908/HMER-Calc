# -*- coding: utf-8 -*-
"""模块一：Pix2Text 识别封装（C3）。

本文件是 `server/README.md` §四 与 `hmer_cs_1.md` §5 约定的**换模型口子**（B2）：
日后换自训模型，只需替换 `Recognizer` 的实现，对外接口与契约字段都不动。

实测基线（P0，2026-10-06，Pix2Text 1.1.7 / CPU）：
- 模型加载约 3s → 服务里只加载一次、全局复用。
- 单公式小图 0.4~0.9s；整页大图 6~7s；首跑曾出现 34s 离群值。
- `recognize_formula(img, return_text=False)` → `{"text": str, "score": float∈[0,1]}`。
- ⚠️ score 是模型 token 级自信度，**不等于正确率**：
  picture1 把上标 `n` 读成 `{3 3}`，score 仍有 0.9337。
  实测各方向 score：picture1 → 0°=0.9069(垃圾) / **90°=0.9337(正确)** / 180°=0.8739 / 270°=0.8254；
  picture3 → **0°=0.9969(正确)** / 90°=0.8666 / 180°=0.8527 / 270°=0.8115。
  垃圾输出也能拿到 0.9069，所以**不能**用「score 够高就跳过其余方向」来短路，必须跑满候选方向取最优。
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from app.recognition import preprocess

__all__ = [
    "RecognitionOutcome",
    "Recognizer",
    "get_recognizer",
    "load_model",
    "is_multiline_structure",
    "MULTILINE_ENVIRONMENTS",
    "DEFAULT_ANGLES",
    "EARLY_EXIT_SCORE",
    "MIN_ACCEPTABLE_SCORE",
]

#: 识别失败（模型没给出内容）
STATUS_ERROR = "ERROR"
#: 识别成功
STATUS_SUCCESS = "SUCCESS"

#: 判定为「多行/多公式结构」的 LaTeX 环境名。
#: 依据：D:\\...\\基于深度学习...txt 的功能列表 —— C3 只要求单一公式，E7（多行/多公式）是扩展项。
#: 因此整页多公式的图（如 picture2 输出大段 `\\begin{array}`）不应冒充成功。
MULTILINE_ENVIRONMENTS = frozenset(
    {
        "array",
        "matrix",
        "pmatrix",
        "bmatrix",
        "Bmatrix",
        "vmatrix",
        "Vmatrix",
        "cases",
        "aligned",
        "align",
        "align*",
        "gathered",
        "split",
        "subarray",
    }
)

#: 图片没有 EXIF 方向时的候选旋转角；有 EXIF 时只用 0°（见 preprocess.prepare_candidates）
DEFAULT_ANGLES: Tuple[int, ...] = (0, 90, 180, 270)

#: 多方向竞优的提前结束阈值：候选方向达到这个 score 就不再试其余方向。
#: 实测依据（picture3，EXIF 归正后）：正确方向 0°=0.9969，其余方向均 ≤0.8666 ——
#: 0.95 能安全落在这个间隔里，既保住常见路径的速度（0.4~0.5s），
#: 又不会像「一见 SUCCESS 就返回」那样把 picture1 的 90° 正确答案漏掉。
EARLY_EXIT_SCORE = 0.95

#: 最低可接受置信度：最高分候选低于此值时**不输出结果**，改为 `status="ERROR"` 让用户确认。
#: 实测依据（22 个样本，人工标注比对，见交付说明 §5）：
#:   正确样本 score 0.9568~1.0；错误样本 0.8977~0.9445；方向误判样本 0.8914。
#: 用户于 2026-10-06 确认采用该门槛。
#: ⚠️ 这是**经验阈值**（正确下沿 0.9568 与错误上沿 0.9445 仅差 0.012，样本量 19），
#: 不能替代 C7 手动修正闭环，只用于"宁可让用户确认，也不返回错误结果"。
MIN_ACCEPTABLE_SCORE = 0.95


@dataclass
class RecognitionOutcome:
    """一次识别的完整结果，含契约字段与排查用的元信息。

    `meta` 只是**诊断信息**，不会进入 HTTP 响应（契约字段不可私自增加）。
    """

    latex: str = ""
    confidence: float = 0.0
    status: str = STATUS_SUCCESS
    message: Optional[str] = None
    #: 因置信度不足被降级为 ERROR 时，模型**原始输出**保留在这里（`latex` 会被清空）。
    #: 仅供排查与日志使用，不进入 HTTP 响应。
    returned_latex: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------------------
# 多行 / 多公式结构检测
# --------------------------------------------------------------------------------------
def _count_multiline_row_breaks(text: str) -> int:
    """数出 `\\begin{...}` 环境里、**花括号嵌套深度为 0** 处的换行符 `\\\\`。

    只看深度 0 是关键：`\\frac{a}{b \\\\ c}` 里嵌在 `{}` 中的 `\\\\` 不算换行。
    """
    count = 0
    depth = 0
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth = max(0, depth - 1)
            index += 1
            continue
        if char == "\\":
            # 双反斜杠 = LaTeX 换行
            if index + 1 < length and text[index + 1] == "\\":
                if depth == 0:
                    count += 1
                index += 2
                continue
            # 跳过控制序列，避免把 `\{` 之类的转义算成花括号
            index += 2
            continue
        index += 1
    return count


def _contains_multiline_environment(latex: str) -> bool:
    """`latex` 是否含有被判定为多行结构的环境。"""
    for name in MULTILINE_ENVIRONMENTS:
        if f"\\begin{{{name}}}" in latex:
            return True
    return False


def is_multiline_structure(latex: str) -> bool:
    """判断识别结果是否是「多行 / 多公式」结构。

    判定规则（故意保守，宁可漏判也不制造假成功）：
    1. 出现多行环境（`array` / `matrix` / `cases` / `aligned` ...）**且**
    2. 该串里存在 **≥2 处**深度为 0 的 `\\\\` 换行符（即至少 3 行内容）

    单行 `\\begin{matrix} x \\end{matrix}` 只有 0 处换行，不会被误判，
    因为 Pix2Text 有时会给**单个**公式套一层 matrix。
    """
    if not latex or not _contains_multiline_environment(latex):
        return False
    return _count_multiline_row_breaks(latex) >= 2


# --------------------------------------------------------------------------------------
# 模型单例
# --------------------------------------------------------------------------------------
_MODEL: Optional[Any] = None
_MODEL_LOCK = threading.Lock()


def load_model() -> Any:
    """加载 Pix2Text（线程安全，进程内只加载一次）。

    `enable_table=False` 跳过本模块用不到的表格模型，省内存与启动时间。
    """
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:
                from pix2text import Pix2Text

                _MODEL = Pix2Text.from_config(enable_table=False)
    return _MODEL


def get_recognizer() -> "Recognizer":
    """取进程内共享的 `Recognizer` 单例（模型延迟到首次识别时加载）。"""
    global _SHARED_RECOGNIZER
    if _SHARED_RECOGNIZER is None:
        with _MODEL_LOCK:
            if _SHARED_RECOGNIZER is None:
                _SHARED_RECOGNIZER = Recognizer()
    return _SHARED_RECOGNIZER


_SHARED_RECOGNIZER: Optional["Recognizer"] = None


# --------------------------------------------------------------------------------------
# 识别器
# --------------------------------------------------------------------------------------
class Recognizer:
    """Pix2Text 封装：图片 → LaTeX + 置信度。

    用法：
        recognizer = Recognizer()              # 不加载模型
        outcome = recognizer.recognize(image)  # 首次调用时加载模型
    """

    def __init__(self, engine: Optional[Any] = None, angles: Tuple[int, ...] = DEFAULT_ANGLES) -> None:
        self._engine = engine
        self._angles = angles
        # 候选方向是串行试的：模型对同一进程内的并发调用不保证线程安全，
        # 而 FastAPI 默认把同步 endpoint 丢进线程池，所以这里自己加锁。
        self._infer_lock = threading.Lock()

    @property
    def engine(self) -> Any:
        """底层 Pix2Text 实例（首次访问时加载）。"""
        if self._engine is None:
            self._engine = load_model()
        return self._engine

    # -- 单次推理 ------------------------------------------------------------------
    def _recognize_once(self, image: Image.Image) -> Tuple[str, float]:
        """对单张图跑一次识别，返回 `(latex, score)`。"""
        with self._infer_lock:
            result = self.engine.recognize_formula(image, return_text=False)

        if isinstance(result, str):  # 兼容未来版本只返回字符串的情况
            return result, 0.0
        if isinstance(result, dict):
            text = result.get("text") or ""
            try:
                score = float(result.get("score") or 0.0)
            except (TypeError, ValueError):
                score = 0.0
            return str(text), min(1.0, max(0.0, score))
        return "", 0.0

    @staticmethod
    def _rank(outcome: RecognitionOutcome) -> Tuple[int, int, float]:
        """竞优关键字：先看是否识别出内容，再比 score，最后比长度（score 相同时长的更可信）。

        纯 score 排序在实测中会选错：`picture1` 的 0° 输出垃圾
        `\\begin{matrix} \\hline{} \\\\ \\end{matrix}` 却有 score 0.9040，
        而正确方向 90°（`\\frac{1}{1-x}=\\sum...`）是 0.9348 —— 差距只有 0.03。
        因此这里给「两字符以下的退化输出」降一级，避免它压过正确结果。
        """
        content = (outcome.latex or "").strip()
        if not content:
            return (0, 0.0, 0)
        degenerate = 0 if len(content) <= 2 else 1
        return (1, degenerate, outcome.confidence)

    def _evaluate(self, image: Image.Image, angle: int) -> RecognitionOutcome:
        """识别单个候选方向，并做「空结果 / 多行结构」判定。"""
        started = time.time()
        latex, score = self._recognize_once(image)
        elapsed = round(time.time() - started, 2)
        latex = latex or ""

        if not latex.strip():
            return RecognitionOutcome(
                latex="",
                confidence=score,
                status=STATUS_ERROR,
                message="识别失败：模型未给出任何公式内容（可能图片中没有公式，或公式区域过小）",
                meta={"angle": angle, "score": score, "reason": "empty", "seconds": elapsed},
            )

        if is_multiline_structure(latex):
            return RecognitionOutcome(
                latex=latex,
                confidence=score,
                status=STATUS_ERROR,
                message=(
                    "识别到多行/多公式结构，当前版本仅支持单一公式（对应功能项 C3；"
                    "多公式 E7 未实现）。请框选单个公式后重试。"
                ),
                meta={"angle": angle, "score": score, "reason": "multiline", "seconds": elapsed},
            )

        return RecognitionOutcome(
            latex=latex,
            confidence=score,
            status=STATUS_SUCCESS,
            message=None,
            meta={"angle": angle, "score": score, "reason": "ok", "seconds": elapsed},
        )

    # -- 对外入口 ------------------------------------------------------------------
    def recognize(self, image: Image.Image, *, try_multiple_orientations: bool = True) -> RecognitionOutcome:
        """识别一张图片，必要时在多个旋转方向上竞优。

        流程：EXIF 归正 + 尺寸控制 + 方向候选（preprocess）→ 逐个识别 → 按 score 取最优。
        图片自带 EXIF 时只有一个候选（0°），无 EXIF 时有四个。
        """
        candidates = preprocess.prepare_candidates(
            image, try_multiple_orientations=try_multiple_orientations
        )
        exif_corrected = bool(candidates and candidates[0].get("exif_corrected"))

        attempted: List[Dict[str, Any]] = []
        best: Optional[RecognitionOutcome] = None
        for item in candidates:
            outcome = self._evaluate(item["image"], item["angle"])
            attempted.append(
                {
                    "angle": item["angle"],
                    "status": outcome.status,
                    "score": outcome.confidence,
                    "reason": outcome.meta.get("reason"),
                    "chars": len(outcome.latex),
                    "seconds": outcome.meta.get("seconds"),
                }
            )
            if best is None or self._rank(outcome) > self._rank(best):
                best = outcome

            # ① EXIF 来自相机元数据，是**结构性**信息：归正后的 0° 直接采信，
            #    绝不用其它旋转方向去覆盖它（否则低分但物理正确的方向可能压过正确结果）。
            if exif_corrected:
                break
            # ② 无 EXIF 时需要竞优。但**不能「一见 SUCCESS 就 break」**：
            #    实测 picture1 的 0° 输出垃圾 `\begin{matrix} \hline{} \\ \end{matrix}` 却判为 SUCCESS，
            #    一旦 break，真正正确的 90°（score 0.9348 > 0.9040）就永远没机会被试。
            #    因此只有「已经足够可信」才提前结束，否则继续评估其余候选方向。
            if best.status == STATUS_SUCCESS and best.confidence >= EARLY_EXIT_SCORE:
                break

        assert best is not None  # candidates 至少有一个
        best.meta["attempted"] = attempted
        best.meta["candidates"] = len(candidates)
        best.meta["exif_corrected"] = exif_corrected
        best.confidence = min(1.0, max(0.0, float(best.confidence)))

        # ---- 最低置信度门槛（用户 2026-10-06 确认采用 score ≥ 0.95）----
        # 实测依据（22 个样本，人工标注比对）：
        #   正确样本 score 区间 0.9568 ~ 1.0；错误样本 0.8977 ~ 0.9445；
        #   另有一张方向选错的样本 0.8914。
        # 即「最高分候选 < 0.95」时，输出**很可能是错的**（本样本集内 100% 是错的），
        # 此时不应冒充成功，而应把决定权交回用户（题目 C7 的手动修正闭环）。
        best.meta["min_acceptable_score"] = MIN_ACCEPTABLE_SCORE
        if best.status == STATUS_SUCCESS and best.confidence < MIN_ACCEPTABLE_SCORE:
            best.meta["reason"] = "low_confidence"
            best.returned_latex = best.latex  # 保留原文供诊断，但不作为结果返回
            best.latex = ""
            best.status = STATUS_ERROR
            best.message = (
                f"识别置信度偏低（{best.confidence:.4f} < {MIN_ACCEPTABLE_SCORE}），"
                "结果可能不可靠：请确认图片方向是否正确、或框选单个公式后重试。"
            )
        return best

    def recognize_base64(self, image_base64: str) -> RecognitionOutcome:
        """便捷入口：Base64 → 识别。解码失败直接返回 ERROR（不抛给调用方）。"""
        try:
            image = preprocess.decode_base64_image(image_base64)
        except ValueError as exc:
            return RecognitionOutcome(
                latex="",
                confidence=0.0,
                status=STATUS_ERROR,
                message=str(exc),
                meta={"reason": "decode_error"},
            )
        return self.recognize(image)
