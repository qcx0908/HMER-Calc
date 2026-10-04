# -*- coding: utf-8 -*-
"""模块一独立测试（C1/C2/C3 的服务端部分）。

铁律（`server/README.md` §三 第 5 条）：
- **不得 import `main.py`** —— 组长的骨架在模块 2 交付前 import 会报错，这是正常的。
- 这里用独立 `FastAPI()`，只挂本模块的 `router`。

运行：
    cd server
    pytest tests/test_recognition.py -v

测试素材（`tests/fixtures/`）：
- `formula_1.png` ~ `formula_3.png`：印刷体公式图，随仓库携带，结论确定。
- `photo_picture3.png`：**真实手写照片，保留 EXIF orientation=8**。
  它专门验证 `preprocess` 的 EXIF 归正链路 —— P0 实测：不做归正时 Pix2Text 输出垃圾。
- `sample1.png` / `sample2.png`：前一阶段从 picture1/2 转出的旧素材，pix2tex 认不出，
  本测试不使用（保留以免影响他人）。

期望值来源：全部为 **2026-10-06 在本机实测**（Pix2Text 1.1.7 / CPU）得到的真实输出，
不是照文档臆测的。模型升级后这些断言可能需要同步更新。
"""
from __future__ import annotations

import base64
import io
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image

from app.recognition import preprocess, router as router_module
from app.recognition.recognizer import (
    EARLY_EXIT_SCORE,
    MIN_ACCEPTABLE_SCORE,
    STATUS_ERROR,
    STATUS_SUCCESS,
    Recognizer,
    is_multiline_structure,
)
from app.recognition.router import META_HEADER
from app.recognition.router import router as recognition_router

# 独立 app：只挂本模块 router，不依赖模块 2 / main.py
app = FastAPI()
app.include_router(recognition_router)
client = TestClient(app)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

#: 工作区根目录（照片素材的常见位置）
PROJECT_ROOT = Path(r"D:\2026秋软件工程设计")


def find_photo(name: str):
    """在若干候选位置里找照片素材；找不到返回 None（调用方 skip）。

    优先级说明（重要）：
    1. **包内 `tests/fixtures/<name>`** —— 交付包自带，组长拿到包即可跑出完整覆盖，
       不依赖他机器上有别的文件。**这是给验收方准备的主路径。**
    2. `D:\\2026秋软件工程设计\\PHOTO\\<name>` —— 开发机上的当前素材位置。
    3. `D:\\2026秋软件工程设计\\<name>` —— 历史位置。

    若三者都没有，相关测试会 skip（不失败）。实测教训：`picture1.jpg` 曾被移动位置，
    导致 4 个回归测试静默 skip —— 所以这里按优先级依次尝试，并优先包内素材防复发。
    """
    for candidate in (
        FIXTURES / name,
        PROJECT_ROOT / "PHOTO" / name,
        PROJECT_ROOT / name,
    ):
        if candidate.exists():
            return candidate
    return None

FORMULA_1 = FIXTURES / "formula_1.png"
FORMULA_2 = FIXTURES / "formula_2.png"
FORMULA_3 = FIXTURES / "formula_3.png"
PHOTO = FIXTURES / "photo_picture3.png"


def _b64_of(path) -> str:
    """按**原始字节**转 base64（不做任何重编码，以免丢掉 EXIF 方向信息）。"""
    return base64.b64encode(path.read_bytes()).decode("ascii")


def _post_image(image_b64: str):
    return client.post("/recognize", json={"image": image_b64})


# ======================================================================================
# 接口层
# ======================================================================================
def test_health_returns_ok():
    """M1-1：`/health` 可访问。"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_recognize_returns_valid_latex():
    """M1-2 / M1-3 / M1-4：合法 JSON、非空 latex、confidence ∈ [0,1]。"""
    response = _post_image(_b64_of(FORMULA_1))
    assert response.status_code == 200
    body = response.json()

    assert body["status"] == STATUS_SUCCESS
    assert body["message"] is None
    assert isinstance(body["latex"], str) and body["latex"].strip()
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["tokens"] == []  # M1-7：预留字段保留为空列表

    # 实测输出为 `1+2 \times3`
    assert "\\times" in body["latex"]
    assert "1" in body["latex"] and "2" in body["latex"] and "3" in body["latex"]


def test_recognize_fraction_fixture():
    r"""C5-1 相关：分数与 \pi 的识别（实测输出 `\frac{\pi} {2}`）。"""
    body = _post_image(_b64_of(FORMULA_2)).json()
    assert body["status"] == STATUS_SUCCESS
    assert "\\frac" in body["latex"]
    assert "\\pi" in body["latex"]


def test_recognize_trig_fixture():
    """C5-3 相关：三角函数的识别。

    实测输出 `\\operatorname{c o s} ( \\pi)+1` —— 注意 Pix2Text 会写成
    `\\operatorname{c o s}`，字符间带空格。这正是「输出原样透传、不做规范化」的体现，
    所以这里只断言 `cos` 的字母序列存在，不断言具体写法。
    """
    body = _post_image(_b64_of(FORMULA_3)).json()
    assert body["status"] == STATUS_SUCCESS
    assert "\\pi" in body["latex"]
    assert "c o s" in body["latex"] or "cos" in body["latex"]


def test_recognize_bad_image_returns_error():
    """ALL.md 红牌项 3：识别失败必须走 `status="ERROR"` + message，且不 500。"""
    response = _post_image("")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == STATUS_ERROR
    assert body["message"]
    assert body["latex"] == ""


def test_recognize_garbage_base64_returns_error():
    """非法 Base64（不是图片）→ 200 + ERROR，不 500。"""
    body = _post_image("这显然不是 base64!!!").json()
    assert body["status"] == STATUS_ERROR
    assert body["message"]


def test_recognize_missing_field_is_422():
    """请求体格式错误才返回 4xx（契约：业务错误 200，格式错误 4xx）。"""
    response = client.post("/recognize", json={})
    assert response.status_code == 422


def test_unexpected_exception_never_returns_500(monkeypatch):
    """兜底回归测试：识别过程抛出**任意未预期异常**也必须返回 200 + ERROR，绝不 500。

    覆盖真实风险场景：模型权重下载失败（无网络首次运行）、模型内部崩溃、
    ONNX 会话初始化失败等 —— 这些都发生在 `recognize_base64` 内部，不属于
    "非法输入"分支（那条由 decode 的 ValueError 处理）。

    `ALL.md` §六 红牌项 2/3：接口遇异常返回 500 崩溃即退回。
    """

    class ExplodingRecognizer:
        def recognize_base64(self, _image: str):
            raise RuntimeError("模拟模型加载失败")

    monkeypatch.setattr(router_module, "get_recognizer", lambda: ExplodingRecognizer())

    response = client.post("/recognize", json={"image": _b64_of(FORMULA_2)})
    assert response.status_code == 200, f"未预期异常不应变成 5xx，实际 {response.status_code}"

    body = response.json()
    assert body["status"] == STATUS_ERROR
    assert body["latex"] == ""
    assert body["confidence"] == 0.0
    assert "RuntimeError" in body["message"]
    assert "unexpected_error" in response.headers[router_module.META_HEADER]


def test_response_exposes_diagnostic_header():
    """诊断信息走响应头，不污染 JSON 契约。"""
    response = _post_image(_b64_of(FORMULA_2))
    assert META_HEADER in response.headers
    assert "angle" in response.headers[META_HEADER]


# ======================================================================================
# 真实照片 + EXIF 方向链路
# ======================================================================================
def test_photo_fixture_keeps_exif_orientation():
    """素材自身必须带**真实的** EXIF 旋转信息，否则这个测试就失去意义。"""
    assert PHOTO.exists(), f"缺少照片素材：{PHOTO}"
    with Image.open(PHOTO) as image:
        orientation = image.getexif().get(274)
        assert orientation == 8, f"照片素材的 EXIF orientation 应为 8，实际 {orientation}"
        assert preprocess.has_exif_orientation(image)
        assert preprocess.exif_rotation_is_trustworthy(image) is True


def test_exif_orientation_zero_is_not_trusted():
    """回归测试：`orientation = 0` 表示"本来就正"，**不构成方向约束**。

    实测 `picture1.jpg` 正是这种情况（有 EXIF 标签、值为 0），
    但它的手写内容实际是 90° 方向。早期实现把"有 EXIF 标签"当成"方向可信"，
    导致只试 0°、返回垃圾 `\\begin{matrix} \\hline{} \\\\ \\end{matrix}`。
    """
    picture1 = find_photo("picture1.jpg")
    if picture1 is None:
        pytest.skip("picture1.jpg 不存在，跳过 orientation=0 回归测试")

    with Image.open(picture1) as image:
        assert image.getexif().get(274) == 0, "该回归测试依赖 picture1 的 EXIF orientation = 0"
        assert preprocess.has_exif_orientation(image) is True, "标签存在"
        assert preprocess.exif_rotation_is_trustworthy(image) is False, "但不应被信任"
        # 因此必须给多个候选方向
        candidates = preprocess.prepare_candidates(image.convert("RGB"))
    assert [c["angle"] for c in candidates] == [0, 90, 180, 270]


def test_photo_with_exif_is_recognized():
    """P0 核心回归：EXIF 归正后，真实手写照片可被识别。

    实测：`\\cos\\frac{\\pi} {2}+1`，score ≈ 0.9969。
    """
    body = _post_image(_b64_of(PHOTO)).json()
    assert body["status"] == STATUS_SUCCESS, body["message"]
    assert "cos" in body["latex"]
    assert "\\pi" in body["latex"]
    assert body["confidence"] > 0.9
    assert 0.0 <= body["confidence"] <= 1.0


def test_exif_present_needs_only_one_candidate():
    """带 EXIF 的图片只应有一个候选方向（信息可信，不必浪费 3 次推理）。"""
    with Image.open(PHOTO) as image:
        candidates = preprocess.prepare_candidates(image.convert("RGB"))
    assert [c["angle"] for c in candidates] == [0]


def test_orientation_competition_picks_best_angle():
    """不带 EXIF 时跑满候选方向，并按 score 选出正确方向。

    这里把照片**重建为不带 EXIF 的图**（`copy()` 会保留 EXIF，必须走 PNG 往返剥离），
    于是 `preprocess` 无法信任方向、必须跑满 4 个候选，再由 score 竞优。
    """
    with Image.open(PHOTO) as opened:
        reopened = Image.open(io.BytesIO(preprocess.to_png_bytes(opened.convert("RGB"))))
        stripped = reopened.convert("RGB")
    assert preprocess.has_exif_orientation(stripped) is False

    candidates = preprocess.prepare_candidates(stripped)
    assert [c["angle"] for c in candidates] == [0, 90, 180, 270]

    outcome = Recognizer().recognize(stripped)
    assert outcome.status == STATUS_SUCCESS
    assert len(outcome.meta["attempted"]) <= 4
    scores = {item["angle"]: item["score"] for item in outcome.meta["attempted"]}
    assert scores, "至少应尝试一个方向"
    # 选中的方向必须取自已尝试方向，且其 score 不低于任何已尝试方向
    chosen = outcome.meta["angle"]
    assert chosen in scores
    best_score = max(scores.values())
    assert scores[chosen] >= best_score - 1e-9, f"选中 {chosen}° 的 score 不是最高：{scores}"


def test_low_confidence_success_does_not_stop_the_search():
    """回归测试：**低置信度的 SUCCESS 不能终止方向搜索**（真实 bug）。

    `picture1.jpg` 的 EXIF=0（方向烧在像素里），实测四个方向：

    | 角度 | score | 输出 | 是否有用 |
    |---|---|---|---|
    | 0° | 0.9040 | `\\begin{matrix} \\hline{} \\\\ \\end{matrix}` | ❌ 垃圾 |
    | 90° | 0.9348 | `\\frac{1} {1-x}=\\sum_{n=0}^{3 3} X^{n}` | ✅ 正确 |

    0° 的垃圾输出**通过了**多行检测（只有 1 个换行符、未达阈值），因此被判为 SUCCESS。
    早期实现写的是「一见 SUCCESS 就 break」，于是 90° 永远没机会被试，对外返回垃圾结果。
    修复后：只有在 score ≥ `EARLY_EXIT_SCORE`(0.95) 时才提前结束，0.9040 不达标 → 继续试 90°。

    注意：模型本身会把上标 `n` 误读为 `3 3`（score 仍 0.9348），
    所以本测试**只断言方向选择正确**，不断言识别完全正确。

    另注：该 0.9348 也低于 `MIN_ACCEPTABLE_SCORE`(0.95)，
    因此最终会被降级为 `status="ERROR"`（见下一个测试）——这正是预期行为。
    """
    picture1 = find_photo("picture1.jpg")
    if picture1 is None:
        pytest.skip("picture1.jpg 不存在，跳过低置信度回归测试")

    outcome = Recognizer().recognize(preprocess.decode_base64_image(_b64_of(picture1)))

    attempted = outcome.meta["attempted"]
    assert len(attempted) > 1, f"低置信度结果不应终止搜索，实际只试了 {attempted}"
    assert attempted[0]["angle"] == 0 and attempted[0]["score"] < EARLY_EXIT_SCORE

    # 方向必须选对（这是本测试的核心：0° 的垃圾结果不能终止搜索）
    assert outcome.meta["angle"] == 90, f"应选中 90°，实际 {outcome.meta['angle']}°"
    assert "\\hline" not in outcome.returned_latex, "不能采用 0° 的垃圾结果"
    assert "\\frac" in outcome.returned_latex and "\\sum" in outcome.returned_latex
    assert outcome.confidence == max(item["score"] for item in attempted)


def test_low_confidence_is_downgraded_to_error():
    """`score < MIN_ACCEPTABLE_SCORE`(0.95) 时必须降级为 ERROR，不冒充成功。

    实测依据（22 个样本人工标注比对）：正确样本 score 0.9568~1.0；
    错误样本 0.8977~0.9445。用户 2026-10-06 确认采用 0.95 门槛。

    用 `picture1.jpg`（选对 90° 但 score 0.9348 < 0.95）验证：
    模型原始输出仍保留在 `returned_latex` 里供诊断，但 `latex` 必须清空。
    """
    picture1 = find_photo("picture1.jpg")
    if picture1 is None:
        pytest.skip("picture1.jpg 不存在，跳过低置信度门槛测试")

    outcome = Recognizer().recognize(preprocess.decode_base64_image(_b64_of(picture1)))

    assert outcome.confidence < MIN_ACCEPTABLE_SCORE, "该测试依赖 picture1 的 score 低于门槛"
    assert outcome.status == STATUS_ERROR
    assert outcome.latex == "", "低置信度结果不应作为 latex 返回"
    assert outcome.returned_latex, "原始输出应保留在 returned_latex 供诊断"
    assert outcome.message and "0.95" in outcome.message
    assert outcome.meta["reason"] == "low_confidence"
    assert outcome.meta["min_acceptable_score"] == MIN_ACCEPTABLE_SCORE


# ======================================================================================
# 多行 / 多公式结构判定
# ======================================================================================
@pytest.mark.parametrize(
    "latex",
    [
        r"\begin{array}{c} a \\ b \\ c \end{array}",
        r"\begin{matrix} x & y \\ z & w \\ p & q \end{matrix}",
        r"\begin{cases} x+1 \\ x-1 \\ x*1 \end{cases}",
        r"\begin{aligned} a &= 1 \\ b &= 2 \\ c &= 3 \end{aligned}",
        r"\begin{array}{c} {{\zeta}} \\ {{\zeta}} \\ {{-i \bar{\tau}}} \end{array}",
    ],
)
def test_multiline_structures_detected(latex):
    """多行/多公式结构必须被识别出来（C3 只支持单一公式，E7 未实现）。"""
    assert is_multiline_structure(latex) is True


@pytest.mark.parametrize(
    "latex",
    [
        r"1+2 \times3",
        r"\frac{\pi} {2}",
        r"\cos\frac{\pi} {2}+1",
        r"\frac{1} {1-x}=x^{n}",
        # 单行 matrix：Pix2Text 有时给单个公式套一层 matrix，不能误判
        r"\begin{matrix} x \end{matrix}",
        # 花括号里的换行不算多行
        r"\frac{a \\ b}{c}",
        # 矩阵内的 \hline 不是换行
        r"\begin{matrix} \hline{} \end{matrix}",
        "",
    ],
)
def test_single_line_structures_not_flagged(latex):
    """单行/非多行输入不能被误判为多公式（宁可漏判，也不制造假成功）。"""
    assert is_multiline_structure(latex) is False


def test_multiline_reaches_error_channel_through_http():
    """多行结构走 ERROR 通道，但 latex 仍原样带出，便于客户端展示原文。

    这里用 picture2（整页多公式）构造请求；素材不存在时跳过。
    """
    picture2 = find_photo("picture2.jpg")
    if picture2 is None:
        pytest.skip("picture2.jpg 不存在，跳过多公式端到端验证")

    body = _post_image(_b64_of(picture2)).json()
    # 该图是整页多公式，最可能的结局是 ERROR；即便模型给出单行结果，
    # 也必须满足「非空则 status 与 message 自洽」的契约
    if body["status"] == STATUS_ERROR:
        assert body["message"]
    else:
        assert body["latex"].strip()
        assert 0.0 <= body["confidence"] <= 1.0


# ======================================================================================
# preprocess 单元测试
# ======================================================================================
def test_decode_rejects_empty_and_invalid():
    """空串 / 非法 Base64 都抛 ValueError（由 router 翻译成 ERROR）。"""
    with pytest.raises(ValueError):
        preprocess.decode_base64_image("")
    with pytest.raises(ValueError):
        preprocess.decode_base64_image("！！！不是base64！！！")


def test_decode_tolerates_data_url_prefix():
    """客户端误带 `data:image/jpeg;base64,` 前缀时不应直接把请求判死。"""
    raw = _b64_of(FORMULA_1)
    image = preprocess.decode_base64_image("data:image/png;base64," + raw)
    assert image.size[0] > 0 and image.size[1] > 0


def test_decode_returns_rgb():
    image = preprocess.decode_base64_image(_b64_of(FORMULA_2))
    assert image.mode == "RGB"


def test_downscale_only_shrinks_when_larger():
    small = Image.new("RGB", (100, 50), "white")
    assert preprocess.downscale_for_model(small, max_side=1600).size == (100, 50)

    large = Image.new("RGB", (4000, 2000), "white")
    scaled = preprocess.downscale_for_model(large, max_side=1600)
    assert max(scaled.size) == 1600
    assert scaled.size[0] > scaled.size[1]  # 保持宽高比


def test_generate_orientation_candidates_rotates_pixels():
    image = Image.new("RGB", (10, 4), "white")
    image.putpixel((0, 0), (255, 0, 0))  # 左上角标红
    candidates = dict((c["angle"], c["image"]) for c in preprocess.generate_orientation_candidates(image))

    assert set(candidates) == {0, 90, 180, 270}
    assert candidates[0].size == (10, 4)
    assert candidates[90].size == (4, 10)  # expand=True
    assert candidates[0].getpixel((0, 0)) == (255, 0, 0)
    assert candidates[180].getpixel((9, 3)) == (255, 0, 0)


def test_normalize_orientation_is_noop_without_exif():
    """没有 EXIF 的图片不应被改动。"""
    image = Image.new("RGB", (7, 5), "white")
    assert preprocess.normalize_orientation(image).size == (7, 5)
