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

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image

from app.recognition import postprocess, preprocess

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
    "LOW_CONFIDENCE_SCORE",
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

#: 低置信度下界（成员 1 于 2026-10-08 按需求方要求新增）：
#: 需求原文「无结果的图像给出置信度最高的选择，并且告知用户识别置信度低」。
#: 因此把原来「< 0.95 一律拒收」改为三档：
#:   >= 0.95          → 正常返回 SUCCESS
#:   0.55 ~ 0.95      → **仍返回最高分候选**，message 提示低置信、请人工核对
#:   <  0.55          → 仍拒收为 ERROR（过低的分基本是噪声，返回反而误导）
#: 取值依据：实测 7 张"无结果"样本中，有实际内容的最高分为 0.9445、
#: 方向选错时为 0.8977~0.9133；而真正是噪声的候选（如 270° 的
#: `\underbrace{\overbrace{\varsigma}}`）在 0.86 以下。0.55 留有安全余量。
LOW_CONFIDENCE_SCORE = 0.55

#: 裁剪轮替换首轮结果所需的**最小分数优势**（成员 1 于 2026-10-08 新增）。
#: 原实现「裁剪轮 rank 更高就替换」会把首轮正确结果换掉（P8.jpg / P10.jpg 实测）。
#: 真实需要裁剪的案例提升幅度很大（12.jpg：0.7831 → 0.9940，+0.21），
#: 因此 0.03 足以放过真实改善、挡住 0.0006 级别的噪声替换。
CROP_REPLACE_MARGIN = 0.03

#: 「字母紧邻乘除号」= 错误翻转产生的伪形态。
#: 需求方判据（2026-10-08）：「带符号的乘法一般不存在未知数，除法也是常数优先」——
#: 出现 `\times` / `\div` 时两侧几乎一定是常数，若某侧是字母，说明该候选来自错误翻转。
#: 实测 3.jpg：真值 `6×7`，错误翻转的 270° 输出 `L \times9` 反而拿到 0.9983。
#: ⚠️ 只惩罚**归一化救不回来**的翻转形态：`z \div2` 虽然也含字母，但 `normalize_digit_confusions`
#:    会把 `z` 还原为 8、得到正确结果，因此**不能**在这里降级（实测那样会让 4.jpg / 6.jpg 反而选错）。
#:    真正要压的是 `L \times9`（`L` 是数字 7 被翻转的产物）这类字母**不是**已知可还原形态的情形。
_BAD_OPERAND = re.compile(
    r"(?<![A-Za-z])(?:[L](?=\s*(?:\\times|\\div)))"           # `L \times9`：7 翻转成 L
    r"|(?:(?:\\times|\\div)\s*[Ll](?![a-zA-Z]))"
    r"|(?:[\d}\s]\s*[+\-=]\s*[ilI]\b(?![a-zA-Z]))"            # `1-i=8`：1 翻转成 i
)

#: 「结构命令堆砌」= 模型读不出内容时的典型输出形态（输出可信度低）。
#: 实测：6.jpg 的 0° 输出 `\underbrace{\alpha}_{\Downarrow}`（0.891）、
#:       p1.jpg 的 270° 输出 `\underbrace{\overbrace{\varsigma}}...`（0.9119）、
#:       P10.jpg 的 90° 输出 `\underbrace{\omicron}...`（0.9475）——
#:       它们在纯 score 排序下会压过真正可读的候选，必须显式降级。
#: 判据用「堆砌结构命令 **且** 一个数字都没有」：`\frac{1} {2}` 这类正常结构含数字，不会误伤。
_STRUCT_NOISE = re.compile(
    r"\\(?:underbrace|overbrace|stackrel|wp|varsigma|zeta|omicron|Im|neq|sharp|"
    r"bullet|diamond|protect|relax|textcircled)"
)

#: 与 `_STRUCT_NOISE` 同类的**符号名**（本身不是算式内容的装饰符号）
_SYMBOL_NAMES = re.compile(
    r"\\(?:bullet|diamond|varsigma|zeta|wp|omicron|Im|ast|star|circ|sim|S|P|lambda|"
    r"leftarrow|longrightarrow|Leftrightarrow|breve|varpi|vartheta|alpha|beta)"
)


def _looks_unreliable(latex: str) -> bool:
    r"""输出可信度粗判 → 判为不可信的条件（满足任一）：

    1. **结构命令堆砌 + 数字密度极低**；
    2. **完全没有数字**。

    判据 2 的依据（成员 1，2026-10-08，需求方确认）：
    本模块的需求范围是「四则 / 分数 / 幂 / 根号 / 基础三角函数」——
    **任何合法结果必然至少含一个数字**。实测所有正确输出均含数字：

    | 含数字 ✅ | 完全无数字 ❌（实测垃圾） |
    |---|---|
    | `6 \\times7` / `8 \\div2-1` / `\\frac{1} {2}` | `\\log \\pi^{\\rho\\sigma}`（P8.jpg 180°） |
    | `\\sin60^{\\circ}` / `\\tan540^{\\circ}` / `2^{10}` | `\\underbrace{\\overbrace{\\varsigma}}_{\\wp}` |
    | `\\cos 9 ^{\\circ}` | `\\stackrel{\\longleftarrow} {a}` |

    这条判据直接解决了 P8.jpg 的失败：180° 的 `\\log \\pi^{\\rho\\sigma}`（0.8977）
    曾压过 0° 的正确结果 `\\cot60^{\\circ}`（0.8319），而它**一个数字都没有**。
    """
    if not latex:
        return False
    if not re.search(r"\d", latex):
        return True  # 判据 2：合法结果必含数字
    if not _STRUCT_NOISE.search(latex):
        return False
    digits = len(re.findall(r"\d", latex))
    structures = len(_STRUCT_NOISE.findall(latex)) + len(_SYMBOL_NAMES.findall(latex))
    return digits <= 1 or structures >= 3


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
    def _rank(outcome: RecognitionOutcome) -> Tuple[int, int, int, int, int, float]:
        """竞优关键字（按优先级从高到低）：

        1. `有内容`            —— 空结果最低；
        2. `非多行结构`        —— 多行本来就会被拒收，不该压过可用候选
                                  （实测 19.jpg：180° 的 6 行矩阵拿下 0.9133，压过了单行结果）；
        3. `形态可信`          —— **数字×数字 优先于 字母×数字**。
                                  实测 3.jpg：真值 `6×7`，但错误翻转（270°）产生的 `L \\times9`
                                  拿到 0.9983、反超正确的 90°（`6 \\times7`，0.9487）。
                                  据需求方判据「带符号的乘法一般不存在未知数」，
                                  字母参与乘除时判为翻转伪形态，降级；
        4. `非退化`（长度 > 2）；
        5. `score`             —— 最后才比模型置信度。

        注：**不**把「输出可信度」做成细粒度打分参与排序 —— 实测那样会让
        `\\frac{1} {2 6}`（3.jpg 180°）压过正确结果。可信度只做**粗粒度垃圾判定**（第 3 步的形态检查）。
        """
        content = (outcome.latex or "").strip()
        if not content:
            return (0, 0, 0, 0, 0.0)
        # 形态/可信度用**原始形态**判断：归一化后的文本会掩盖「翻转」证据
        raw = str(outcome.meta.get("raw_latex") or content)
        multiline = 0 if outcome.meta.get("reason") == "multiline" else 1
        shape = 0 if _BAD_OPERAND.search(raw) else 1
        credible = 0 if _looks_unreliable(raw) else 1
        degenerate = 0 if len(content) <= 2 else 1
        return (1, multiline, shape, credible, degenerate, outcome.confidence)

    def _evaluate(self, image: Image.Image, angle: int) -> RecognitionOutcome:
        """识别单个候选方向，做「空结果 / 多行结构」判定，并**先归一化再竞优**。

        为什么归一化要放在竞优**之前**（需求方 2026-10-08 明确）：
        有些候选**原始形态**是垃圾、但归一化后就是正确答案，例如 P10.jpg 的 0°
        `\\operatorname{s i n} \\ 6 o^{\\circ}` → `\\sin \\ 60^{\\circ}`（正确）。
        若先按原始形态竞优，它会被 90° 的垃圾（0.9475）压掉、**根本没机会参赛**。
        所以每个候选都先过 `normalize_digit_confusions`，用**修复后的形态**参与排序。
        """
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

        normalized = postprocess.normalize_digit_confusions(latex)
        # 保留原始形态：**排序要用原始形态判断翻转伪形态**（见 _rank 的 shape 维度）。
        # 否则归一化会把 `L \times9` 修成 `6 \times9`，把「错误翻转」的证据自己抹掉，
        # 结果它反而以 0.9983 压过正确的 90°（实测 3.jpg 回归）。
        raw_latex = latex
        if normalized != latex:
            latex = normalized

        # 兼容旧标记：`digit_merge` 表示做过拆散数字合并，`confusion_fix` 表示做过混淆还原。
        # 注意：归一化已提前到 _evaluate（为了让修复后的形态能参与竞优），
        # 所以这两个标记也必须在**这里**设置；放在 recognize() 末尾的话永远不会触发。
        merged_only = postprocess.merge_split_digits(raw_latex)
        meta_extra: Dict[str, Any] = {"raw_latex": raw_latex}
        if merged_only != raw_latex:
            meta_extra["digit_merge"] = True
        if latex != merged_only:
            meta_extra["confusion_fix"] = True

        if is_multiline_structure(latex):
            return RecognitionOutcome(
                latex=latex,
                confidence=score,
                status=STATUS_ERROR,
                message=(
                    "识别到多行/多公式结构，当前版本仅支持单一公式（对应功能项 C3；"
                    "多公式 E7 未实现）。请框选单个公式后重试。"
                ),
                meta={"angle": angle, "score": score, "reason": "multiline",
                      "seconds": elapsed, **meta_extra},
            )

        return RecognitionOutcome(
            latex=latex,
            confidence=score,
            status=STATUS_SUCCESS,
            message=None,
            meta={"angle": angle, "score": score, "reason": "ok", "seconds": elapsed,
                  **meta_extra},
        )

    # -- 对外入口 ------------------------------------------------------------------
    @staticmethod
    def _attempt_note(outcome: RecognitionOutcome, angle: int, stage: str) -> Dict[str, Any]:
        """构造 `meta["attempted"]` 里的一条诊断记录。"""
        return {
            "angle": angle,
            "stage": stage,
            "status": outcome.status,
            "score": outcome.confidence,
            "reason": outcome.meta.get("reason"),
            "chars": len(outcome.latex),
            "seconds": outcome.meta.get("seconds"),
        }

    def _run_pass(
        self,
        candidates: List[Dict[str, Any]],
        *,
        stage: str,
        use_crop: bool,
    ) -> Tuple[Optional[RecognitionOutcome], List[Dict[str, Any]]]:
        """跑一轮候选方向竞优。

        `use_crop=True` 时先对每个候选 `preprocess.crop_to_ink`：
        裁剪无变化的候选（纯背景/裁剪无意义）**跳过**——同一张图重复推理结果一样，
        白白多花 0.3~1s；调用方据 `crop_noop` 仍能看出该轮跑过。

        返回 `(best, attempted)`；`best` 为 None 表示整轮候选都被跳过。
        """
        attempted: List[Dict[str, Any]] = []
        best: Optional[RecognitionOutcome] = None
        for item in candidates:
            source = item["image"]
            image = source
            if use_crop:
                image = preprocess.crop_to_ink(source)
                if image.size == source.size:
                    attempted.append(
                        {
                            "angle": item["angle"],
                            "stage": stage,
                            "status": "SKIPPED",
                            "score": None,
                            "reason": "crop_noop",
                            "chars": 0,
                            "seconds": 0.0,
                        }
                    )
                    continue

            outcome = self._evaluate(image, item["angle"])
            outcome.meta["stage"] = stage
            attempted.append(self._attempt_note(outcome, item["angle"], stage))
            if best is None or self._rank(outcome) > self._rank(best):
                best = outcome

            # ① EXIF 来自相机元数据，是**结构性**信息：归正后的 0° 直接采信，
            #    绝不用其它旋转方向去覆盖它（否则低分但物理正确的方向可能压过正确结果）。
            if item.get("exif_corrected"):
                break
            # ② 无 EXIF 时需要竞优。但**不能「一见 SUCCESS 就 break」**：
            #    实测 picture1 的 0° 输出垃圾 `\begin{matrix} \hline{} \\ \end{matrix}` 却判为 SUCCESS，
            #    一旦 break，真正正确的 90°（score 0.9348 > 0.9040）就永远没机会被试。
            #    因此只有「已经足够可信」才提前结束，否则继续评估其余候选方向。
            if best.status == STATUS_SUCCESS and best.confidence >= EARLY_EXIT_SCORE:
                break
        return best, attempted

    def recognize(self, image: Image.Image, *, try_multiple_orientations: bool = True) -> RecognitionOutcome:
        """识别一张图片，必要时在多个旋转方向上竞优。

        流程（组长订正 2026-10 更新）：

        1. `preprocess` 做 EXIF 归正 + 尺寸控制 + 方向候选；逐个识别、按 score 取最优。
           图片自带可信 EXIF 时只有一个候选（0°），否则四个方向。
        2. **低置信度回退（新增）**：若第 1 轮最好成绩 < `MIN_ACCEPTABLE_SCORE`，
           先裁到墨迹区域再跑一轮（`preprocess.crop_to_ink`），两轮取更优。
           动机：整页照片里公式占比小时模型容易误读，实测 12.jpg
           全图 `'( 2-7'`(0.7831) → 裁剪后 `'1 2-7'`(0.9940)。
        3. **数字粘连修复（新增）**：`postprocess.merge_split_digits` 合并被空白
           拆散的数字（`4 8 6` → `486`），防止 latex2sympy2 把 `4 8` 静默算成 4×8。
        4. 最低置信度门槛照旧：最终成绩 < 0.95 仍降级为 ERROR。
        """
        candidates = preprocess.prepare_candidates(
            image, try_multiple_orientations=try_multiple_orientations
        )
        exif_corrected = bool(candidates and candidates[0].get("exif_corrected"))

        best, attempted = self._run_pass(candidates, stage="full", use_crop=False)
        assert best is not None  # candidates 至少有一个，且 full 轮不会跳过

        # ---- 低置信度回退：墨迹裁剪重试（组长订正 2026-10）----
        # 只在首轮低于门槛时触发；裁剪无变化的候选被跳过，所以纯背景 / 已裁紧的图
        # 不会额外花推理。裁剪轮达到 EARLY_EXIT_SCORE 会在轮内提前结束。
        #
        # ⚠️ 替换门槛（成员 1 于 2026-10-08 加，需求方确认）：
        # 原实现是「裁剪轮只要 `_rank` 更高就替换」，实测**会把首轮的正确结果换掉**：
        #   · P8.jpg  首轮 0° = `\cot60^{\circ}`（0.8319，**正确**）
        #             → 裁剪轮 180° 的 `log \pi^{\rho\sigma}` 0.8977 把它顶掉
        #   · P10.jpg 首轮 0° = `\sin 60^{\circ}`（0.9445，**正确**）
        #             → 裁剪轮 0° 变异成 `\sin \not< o \nu`，score 0.9451 只高 0.0006 就顶掉
        # 而真正需要裁剪的案例（12.jpg：0.7831 → 0.9940）提升幅度是 0.21，远超噪声。
        # 因此要求裁剪轮**显著更优**才允许替换（同时不允许形态/可信度变差）。
        # `CROP_REPLACE_MARGIN` 取 0.03：能放过 12.jpg 那类真实改善，挡住 0.0006 级别的噪声。
        score_before_crop = best.confidence
        crop_info: Dict[str, Any] = {"crop_retry_used": False}
        if best.confidence < MIN_ACCEPTABLE_SCORE:
            crop_best, crop_attempted = self._run_pass(candidates, stage="crop", use_crop=True)
            attempted.extend(crop_attempted)
            improved = False
            if crop_best is not None:
                rank_ok = self._rank(crop_best) > self._rank(best)
                score_margin_ok = crop_best.confidence >= best.confidence + CROP_REPLACE_MARGIN
                # 裁剪结果不允许形态/可信度比首轮差（防止用垃圾换掉可读结果）
                form_ok = (
                    (0 if _BAD_OPERAND.search(str(crop_best.meta.get("raw_latex") or "")) else 1,
                     0 if _looks_unreliable(str(crop_best.meta.get("raw_latex") or "")) else 1)
                    >= (0 if _BAD_OPERAND.search(str(best.meta.get("raw_latex") or "")) else 1,
                        0 if _looks_unreliable(str(best.meta.get("raw_latex") or "")) else 1)
                )
                improved = rank_ok and score_margin_ok and form_ok
            crop_info = {
                "crop_retry_used": True,
                "crop_retry_improved": improved,
                "crop_score": None if crop_best is None else round(float(crop_best.confidence), 4),
                "crop_required_margin": CROP_REPLACE_MARGIN,
                "score_before_crop": score_before_crop,
            }
            if improved:
                best = crop_best

        # ---- 数字粘连修复 + 数字/字母混淆修复（组长订正 2026-10；成员 1 扩充 2026-10-08）----
        # 放在选优之后（兜底）：_evaluate 已做过一轮归一化，这里是**幂等的二次保险**，
        # 并保证 `best.latex` 一定是归一化后的形态。
        # 注意标记要在 _evaluate 里设（那里比较的是**原始形态**）；这里只补漏。
        raw_of_best = str(best.meta.get("raw_latex") or "")
        if raw_of_best:
            if postprocess.merge_split_digits(raw_of_best) != raw_of_best:
                best.meta["digit_merge"] = True
        normalized = postprocess.normalize_digit_confusions(best.latex or "")
        if normalized != (best.latex or ""):
            best.meta["confusion_fix"] = True
            best.meta.setdefault("before_confusion_fix", best.latex)
        best.latex = normalized

        best.meta["attempted"] = attempted
        best.meta["candidates"] = len(candidates)
        best.meta["exif_corrected"] = exif_corrected
        best.meta.update(crop_info)
        best.confidence = min(1.0, max(0.0, float(best.confidence)))

        # ---- 置信度分档（成员 1 于 2026-10-08 按需求方要求调整）----
        # 需求：「无结果的图像给出置信度最高的选择，并且告知用户识别置信度低」
        # 因此不再一律拒收：
        #   score >= MIN_ACCEPTABLE_SCORE(0.95)      → 正常 SUCCESS
        #   LOW_CONFIDENCE_SCORE <= score < 0.95     → **仍返回结果**，但 message 提示低置信
        #   score <  LOW_CONFIDENCE_SCORE(0.55)      → 太低，仍降级为 ERROR（避免返回纯噪声）
        best.meta["min_acceptable_score"] = MIN_ACCEPTABLE_SCORE
        best.meta["low_confidence_score"] = LOW_CONFIDENCE_SCORE
        if best.status == STATUS_SUCCESS and best.confidence < MIN_ACCEPTABLE_SCORE:
            if best.confidence >= LOW_CONFIDENCE_SCORE:
                best.meta["reason"] = "low_confidence"
                best.message = (
                    f"识别置信度偏低（{best.confidence:.4f} < {MIN_ACCEPTABLE_SCORE}），"
                    "结果仅供参考，请人工核对；如不对请确认图片方向或框选单个公式后重试。"
                )
            else:
                # 置信度过低：保留最高分候选原文供诊断，但不作为结果返回
                best.meta["reason"] = "low_confidence"
                best.returned_latex = best.latex
                best.latex = ""
                best.status = STATUS_ERROR
                best.message = (
                    f"识别置信度过低（{best.confidence:.4f} < {LOW_CONFIDENCE_SCORE}），"
                    "无法给出可靠结果：请确认图片方向是否正确、或框选单个公式后重试。"
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
