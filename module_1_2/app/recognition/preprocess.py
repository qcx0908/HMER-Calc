# -*- coding: utf-8 -*-
"""模块一：图像解码与可选预处理（C2）。

职责边界（见 hmer_cs_1.md 铁律 1）：
- 只做「Base64 → PIL」、「方向候选生成」与「墨迹裁剪（低置信度重试用，组长订正 2026-10）」。
- **不做**二值化/去噪/锐化等像素级增强：Pix2Text 自带缩放与归一化，额外处理会降低识别率。
  （组长订正 2026-10：唯一例外是 `crop_to_ink` 的**几何裁剪**——只裁掉空白背景、
  不做任何像素值层面的变换，实测能救回「整页照片中公式占比小」的低置信度样本。）
- **不改写**模型输出的 LaTeX（数字粘连修复在 recognizer/postprocess.py，不在这里）。

方向说明（P0 实测得出，2026-10-06）：
- `picture3.jpg` 的 EXIF orientation = 8，不做 `exif_transpose` 时 Pix2Text 输出垃圾；
  归正后立刻得到 `\\cos\\frac{\\pi} {2}+1`（score 0.9969）。因此 EXIF 归正是**必需**步骤。
- `picture1.jpg` / `picture2.jpg` 的 EXIF = 0，方向烧在像素里，没有任何图像指标能判定，
  只能让模型在多个候选方向上都识别一遍、再按 score 竞优（见 recognizer.py）。
"""
from __future__ import annotations

import base64
import binascii
import io
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageOps

#: 模型输入像素上限（最长边）。Pix2Text 内部会自行缩放，这里只防超大图拖慢推理。
MAX_SIDE = 1600

# ---- 墨迹裁剪参数（组长订正 2026-10，实测标定见 crop_to_ink） ----
#: 灰度低于「背景中位数 - 该值」视为墨迹
INK_DELTA = 40
#: 四周留白 = 长边的该比例（12.jpg 实测：0.05 × 1600 = 80px 时 score 0.7831 → 0.9940）
INK_PAD_RATIO = 0.05
#: 最小留白像素，防小图裁得太紧
INK_MIN_PAD = 20
#: 墨迹框覆盖超过整图该比例时视为「没裁到东西」，原样返回（调用方跳过重试）
INK_MAX_COVER = 0.95

#: re-export，便于测试与调用方复用同一套异常类型
ImageDecodeError = ValueError

__all__ = [
    "ImageDecodeError",
    "MAX_SIDE",
    "INK_DELTA",
    "INK_PAD_RATIO",
    "INK_MIN_PAD",
    "INK_MAX_COVER",
    "decode_base64_image",
    "encode_image_to_base64",
    "normalize_orientation",
    "has_exif_orientation",
    "exif_rotation_is_trustworthy",
    "generate_orientation_candidates",
    "downscale_for_model",
    "crop_to_ink",
    "prepare_candidates",
    "to_png_bytes",
    "to_base64_png",
]


def decode_base64_image(image_base64: str) -> Image.Image:
    """Base64 字符串 → PIL.Image（RGB）。

    参数
    ----
    image_base64:
        JPEG/PNG 字节的 Base64，**不带** `data:` URL 前缀（契约见 ALL.md §3.2）。

    异常
    ----
    ValueError
        空串、非法 Base64、或解码后不是图片格式时抛出。router 会把它翻译成
        `status="ERROR"` + `message`（HTTP 200），而不是 500。
    """
    if not isinstance(image_base64, str) or not image_base64.strip():
        raise ImageDecodeError("image 为空：需要 JPEG/PNG 字节的 Base64 字符串（不带 data: 前缀）")

    raw_text = "".join(image_base64.split())
    # 容错：客户端误带 data URL 前缀时当场剥掉，避免把整个请求判死
    if raw_text.startswith("data:"):
        _, _, raw_text = raw_text.partition(",")

    try:
        raw = base64.b64decode(raw_text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ImageDecodeError(f"Base64 解码失败：{exc}") from exc

    if not raw:
        raise ImageDecodeError("Base64 解码后为空字节")

    try:
        image = Image.open(io.BytesIO(raw))
        image.load()
    except Exception as exc:  # noqa: BLE001 - PIL 会抛各种异常，统一转成解码错误
        raise ImageDecodeError(f"不是可识别的图片格式：{type(exc).__name__}: {exc}") from exc

    return image.convert("RGB")


def encode_image_to_base64(image: Image.Image, fmt: str = "PNG") -> str:
    """PIL.Image → Base64（供测试造数据与排查用）。"""
    buf = io.BytesIO()
    image.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def to_png_bytes(image: Image.Image) -> bytes:
    """PIL.Image → PNG 字节。"""
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def to_base64_png(image: Image.Image) -> str:
    """PIL.Image → PNG 的 Base64（不带前缀）。"""
    return base64.b64encode(to_png_bytes(image)).decode("ascii")


def _read_exif_orientation(image: Image.Image) -> Optional[int]:
    """读取 EXIF orientation（274 号标签），读不到返回 None。"""
    try:
        exif = image.getexif()
    except Exception:  # noqa: BLE001
        return None
    if not exif:
        return None
    value = exif.get(274)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def has_exif_orientation(image: Image.Image) -> bool:
    """图片是否带 EXIF orientation 信息。

    注意：`orientation == 0` 与「没有该标签」是两种不同情况 ——
    前者表示「已经摆正」，后者表示「信息烧在像素里」，本模块据此决定要不要多方向竞优。
    """
    return _read_exif_orientation(image) is not None


def normalize_orientation(image: Image.Image) -> Image.Image:
    """按 EXIF orientation 把图片摆正（无 EXIF 时原样返回）。

    这是 P0 实测确认的**关键步骤**：picture3.jpg 不做这一步必然识别失败。
    """
    try:
        return ImageOps.exif_transpose(image)
    except Exception:  # noqa: BLE001 - 坏 EXIF 不应让整个请求失败
        return image


def exif_rotation_is_trustworthy(image: Image.Image) -> bool:
    """EXIF 是否**真的**指示了一次旋转（决定要不要信任归正后的 0° 方向）。

    ⚠️ 必须区分两种情况（实测踩过坑）：

    - `orientation = 8`（rotate 270）等 **2~8**：`exif_transpose` 会真的旋转像素，
      归正后的 0° 就是相机认定的正确方向 → **可信**，不必再试其它方向。
    - `orientation = 0 或 1`：含义是「本来就摆正」，`exif_transpose` **什么都不做**。
      此时"方向信息"其实并没有提供任何方向约束，若因此跳过其它候选就错了 ——
      实测 `picture1.jpg` 正是这种情况（EXIF 标签存在但值为 0），
      0° 输出垃圾、90° 才是正确方向。

    判定方式：比较归正前后像素尺寸是否变化（0/1 与 5/6/7/8 无 EXIF 时尺寸不变）。
    """
    orientation = _read_exif_orientation(image)
    if orientation is None or orientation in (0, 1):
        return False
    try:
        return ImageOps.exif_transpose(image).size != image.size
    except Exception:  # noqa: BLE001
        return False


def downscale_for_model(image: Image.Image, max_side: int = MAX_SIDE) -> Image.Image:
    """仅在超过 `max_side` 时等比缩小；否则原样返回（尽量不动模型输入）。"""
    width, height = image.size
    longest = max(width, height)
    if longest <= max_side:
        return image
    scale = max_side / float(longest)
    new_size = (max(1, int(round(width * scale))), max(1, int(round(height * scale))))
    return image.resize(new_size, Image.LANCZOS)


def crop_to_ink(
    image: Image.Image,
    *,
    pad_ratio: float = INK_PAD_RATIO,
    min_pad: int = INK_MIN_PAD,
    ink_delta: int = INK_DELTA,
    max_cover: float = INK_MAX_COVER,
) -> Image.Image:
    """裁剪到「墨迹包围盒 + 留白」（低置信度重试用，组长订正 2026-10）。

    动机（2026-10-05 实测）：整页照片里公式只占小区域时，模型会把空格/噪声
    当上下文，容易误读（`12.jpg` 全图 0° 输出 `'( 2-7'`，score 0.7831；
    裁到墨迹后输出 `'1 2-7'`，score **0.9940** —— 「1」不再被读成「(」）。

    保守策略（任何一条不满足就原样返回，调用方据此跳过重试）：
    - 找不到墨迹（纯背景图）；
    - 墨迹框覆盖 ≥ `max_cover` 的整图面积（没裁到东西）；
    - 裁剪结果与原图同尺寸。

    极性问题（组长订正 2026-10）：主体是「深色墨迹 / 浅色背景」（纸面书写），
    因此只找比背景**暗**的像素；仅当整幅都找不到暗像素时，才反过来找比背景**亮**
    的像素（黑板 + 粉笔字这类反色场景）。正常纸面照片永远走不到这一步，路径不受影响。

    实现只做**几何裁剪**：背景亮度取灰度中位数（亮/暗照片都能自适应），
    不做二值化以外的像素值变换（Pix2Text 自带归一化，多改反而伤识别率）。
    """
    gray = image.convert("L")
    width, height = gray.size
    if width <= 2 or height <= 2:
        return image

    # 背景亮度 ≈ 灰度中位数：整体偏亮或偏暗的照片都能自适应
    histogram = gray.histogram()
    total = sum(histogram)
    cumulative = 0
    background = 255
    for value, count in enumerate(histogram):
        cumulative += count
        if cumulative * 2 >= total:
            background = value
            break

    dark_threshold = max(0, background - ink_delta)
    mask = gray.point(lambda v: 255 if v < dark_threshold else 0)
    bbox = mask.getbbox()
    if bbox is None:
        # 深底浅字（如黑板照）：全图没有比背景暗的像素，反向找比背景亮的像素
        light_threshold = min(255, background + ink_delta)
        mask = gray.point(lambda v: 255 if v > light_threshold else 0)
        bbox = mask.getbbox()
    if bbox is None:
        return image  # 没有墨迹，没什么可裁

    left, top, right, bottom = bbox
    if (right - left) * (bottom - top) >= max_cover * width * height:
        return image  # 墨迹几乎铺满全图，裁剪无意义

    pad = max(min_pad, int(round(pad_ratio * max(width, height))))
    box = (
        max(0, left - pad),
        max(0, top - pad),
        min(width, right + pad),
        min(height, bottom + pad),
    )
    cropped = image.crop(box)
    if cropped.size == image.size:
        return image
    return cropped


def generate_orientation_candidates(image: Image.Image, angles: Tuple[int, ...] = (0, 90, 180, 270)) -> List[Dict]:
    """生成若干候选方向，供 recognizer 逐个识别并竞优。

    返回 `[{"angle": int, "image": Image}, ...]`。旋转用双线性插值并补白底，
    避免出现黑角影响模型。
    """
    candidates: List[Dict] = []
    for angle in angles:
        if angle % 360 == 0:
            rotated = image.copy()
        else:
            rotated = image.rotate(
                angle % 360,
                expand=True,
                resample=Image.BILINEAR,
                fillcolor=(255, 255, 255),
            )
        candidates.append({"angle": int(angle) % 360, "image": rotated})
    return candidates


def prepare_candidates(
    image: Image.Image,
    *,
    try_multiple_orientations: bool = True,
    max_side: int = MAX_SIDE,
) -> List[Dict]:
    """把「EXIF 归正 + 尺寸控制 + 方向候选」串成一条流水线。

    - 始终先做 EXIF 归正（有 EXIF 时等于把图摆正）。
    - EXIF **真的指示了一次旋转**时（orientation 2~8），只返回归正后的 0°：
      相机元数据可信，不必浪费 3 次推理。
    - 其余情况（无 EXIF，或 orientation 为 0/1 等于"本来就正"）返回 0/90/180/270 四个候选，
      由 recognizer 按 score 竞优 —— 因为此时方向**并没有**被元数据约束。

    每个候选都带 `"exif_corrected"` 标记：为 True 表示方向来自可信的相机元数据，
    recognizer 应**直接采信**、不要再拿其它旋转方向去覆盖它。
    """
    normalized = normalize_orientation(image)
    trusted = exif_rotation_is_trustworthy(image)

    if trusted or not try_multiple_orientations:
        angles: Tuple[int, ...] = (0,)
    else:
        angles = (0, 90, 180, 270)

    exif_corrected = bool(trusted and try_multiple_orientations)
    return [
        {
            "angle": item["angle"],
            "image": downscale_for_model(item["image"], max_side=max_side),
            "exif_corrected": exif_corrected,
        }
        for item in generate_orientation_candidates(normalized, angles)
    ]
