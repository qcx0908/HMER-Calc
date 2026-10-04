# -*- coding: utf-8 -*-
"""模块一：HTTP 接口层（C1/C2/C3 的服务端入口）。

协同约定（`server/README.md` §三，不可违反）：
1. 变量名必须是 `router` —— `app/main.py` 按这个名字 import。
2. 路由写**全路径**、不带 prefix：本模块是 `GET /health` 与 `POST /recognize`。
3. `GET /health` 归本模块（`main.py` 里没有，别去那边加）。
4. 业务错误一律返回 **HTTP 200** + `status="ERROR"` + `message`，绝不 500
   （`ALL.md` §六 红牌项 2/3）。
5. router 只做参数校验与调用，识别逻辑都在 `recognizer.py` 的 `Recognizer` 里。

本文件**不新增也不删减**契约字段：响应就是 `common.models.RecognitionResponse`。
识别过程的诊断信息（试验过哪些方向、各自 score）通过 `X-Recognition-Meta` 响应头暴露，
既方便联调排查，又不会污染 JSON 契约。
"""
from __future__ import annotations

import json
import logging
import traceback

from fastapi import APIRouter, Response
from starlette.concurrency import run_in_threadpool

from app.common.models import RecognitionResponse, RecognizeRequest
from app.recognition.recognizer import STATUS_ERROR, RecognitionOutcome, get_recognizer

logger = logging.getLogger(__name__)

router = APIRouter()

#: 响应头名：放识别诊断信息（候选方向与各自 score），不属于 JSON 契约
META_HEADER = "X-Recognition-Meta"


@router.get("/health")
def health() -> dict:
    """存活探测（`ALL.md` M1-1）。返回固定结构，不触碰模型。"""
    return {"status": "ok"}


@router.post("/recognize", response_model=RecognitionResponse)
async def recognize(payload: RecognizeRequest, response: Response) -> RecognitionResponse:
    """图片 Base64 → LaTeX + 置信度。

    - 请求体格式错误（缺 `image`、类型不对）由 FastAPI/pydantic 返回 422，符合契约。
    - 空串、非法 Base64、非图片 → HTTP 200 + `status="ERROR"` + `message`。
    - 识别不出内容 / 多行多公式结构 → HTTP 200 + `status="ERROR"` + `message`。
    - **任何未预期的异常**（模型加载失败、无网络下首次下载权重、模型内部崩溃等）
      同样返回 200 + `status="ERROR"`，**绝不 500**（`ALL.md` §六 红牌项 2/3）。

    识别是 CPU 密集的同步调用（实测 0.4~7s，首次遇到新尺寸可能 30s+），用线程池跑，避免阻塞事件循环。
    """
    try:
        outcome = await run_in_threadpool(get_recognizer().recognize_base64, payload.image)
    except Exception as exc:  # noqa: BLE001 - 兜底：把任何意外都翻译成契约内的错误响应，而不是 500
        logger.exception("识别过程出现未预期异常")
        outcome = _error_outcome(exc)

    meta = json.dumps(outcome.meta, ensure_ascii=False, default=str)
    if len(meta) > 1800:  # 响应头别太长
        meta = meta[:1800] + "...(truncated)"
    response.headers[META_HEADER] = meta

    return RecognitionResponse(
        latex=outcome.latex,
        confidence=outcome.confidence,
        tokens=[],  # E3/E8 预留：Pix2Text 不提供 token 级信息，保持空列表
        status=outcome.status,
        message=outcome.message,
    )


def _error_outcome(exc: BaseException) -> RecognitionOutcome:
    """把未预期异常翻译成 `status="ERROR"` 的结果对象（含异常类型与最后几帧，便于排查）。"""
    frames: list[str] = []
    try:
        for line in traceback.format_exc().strip().splitlines():
            stripped = line.strip()
            if stripped.startswith("File "):
                frames.append(stripped)
    except Exception:  # noqa: BLE001 - 连取栈都不该让请求失败
        frames = []

    message = f"识别过程出现未预期异常：{type(exc).__name__}: {exc}"
    if frames:
        message += "｜" + " <- ".join(frames[-3:])
    return RecognitionOutcome(
        latex="",
        confidence=0.0,
        status=STATUS_ERROR,
        message=message[:600],
        meta={"reason": "unexpected_error", "exception": type(exc).__name__},
    )
