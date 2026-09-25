# 模块 1 指导文档：后端识别服务（C/S 版，C1 / C2 / C3 的服务端部分）

> 项目：HMER-Calc（C/S 架构）
> 责任人：成员 1
> 架构：手机开热点，电脑跑后端。本模块是后端「图片 → LaTeX」识别服务。
> 全局约定以同目录 `ALL.md` 为准。旧方案 `hmer_calc_1.md` 为日后端侧对比的余量参考，不在本次落实范围。

---

## 0. 模块定位

提供一个 HTTP 接口 `POST /recognize`：接收 Base64 图片，返回 LaTeX 字符串 + 置信度（+ 可选 token 级信息）。
**交付物是"能独立启动、能被 pytest 独立测试、能被模块 3 通过 HTTP 调通"的识别服务**，不是一份 Python 脚本。

---

## 1. 处理流程（箭头 = 数据流向）

```
HTTP 请求 { "image": "<base64>" }
   --> 解码 Base64 --> PIL Image
   --> 【C2 预处理】可选裁剪到公式区域 --> 交给 pix2tex（自带缩放/分辨率预测）
   --> 【C3 识别】pix2tex 模型推理 --> LaTeX 字符串
   --> 计算整体置信度 (可选: token 级置信度)
   --> 封装为 RecognitionResponse(latex, confidence, tokens)
   --> 返回 JSON
```

**预处理（C2）**：pix2tex 自带预处理（自动预测最优分辨率并缩放），**不要做二值化/去噪**（会降低识别率）。可选：裁剪到公式区域。

---

## 2. 需要实现的功能

| 编号 | 功能 | 说明 |
|---|---|---|
| C2-1 | 图像解码 | Base64 → PIL Image |
| C2-2 | 可选裁剪 | 裁剪到公式区域（可选） |
| C2-3 | 交给模型 | pix2tex 自带缩放/归一化，无需手写预处理 |
| C3-1 | 深度学习识别 | pix2tex（ViT+Transformer，现成强模型）图片→LaTeX |
| C3-2 | 置信度输出 | 整体置信度；token 级作为可选 |
| — | 独立可测试 | 提供 `pytest tests/test_recognition.py` |

> 说明：pix2tex 首次运行会自动下载模型权重（需联网一次）。CPU 可跑（单张 1–3 秒），有 NVIDIA 卡可装 CUDA 版 PyTorch 加速。

---

## 3. 全局统一约定（必须遵守，以 ALL.md 为准）

### 3.1 服务地址约定

- 默认端口 **8000**，全后端一个进程，启动命令：`uvicorn app.main:app --host 0.0.0.0 --port 8000`。
  - **必须带 `--host 0.0.0.0`**：默认只绑 127.0.0.1，手机连不上电脑。
  - Windows 防火墙首次运行需放行 8000 端口入站，否则真机仍连不上。
- 电脑端启动后，用 `curl http://127.0.0.1:8000/health` 自测。
- 真机通过热点访问电脑的局域网 IP（如 `http://192.168.43.100:8000`，具体看电脑 `ipconfig`）。

### 3.2 JSON 契约（本模块的响应，放 `common/models.py`，模块 2/3 共用）

```python
# server/app/common/models.py
from pydantic import BaseModel
from typing import List, Optional

class RecognizeRequest(BaseModel):
    image: str                  # JPEG 字节的 base64，无 data URL 前缀

class Token(BaseModel):
    text: str
    confidence: float
    range_start: int
    range_end: int
    alternatives: List[str] = []

class RecognitionResponse(BaseModel):
    latex: str
    confidence: float
    tokens: List[Token] = []
    status: str = "SUCCESS"            # "SUCCESS" | "ERROR"（识别失败）
    message: Optional[str] = None

class CalculateRequest(BaseModel):
    latex: str
    mode: str = "deg"            # "deg" | "rad"

class CalculateResponse(BaseModel):
    latex: str
    value: Optional[float] = None
    value_latex: Optional[str] = None
    status: str                  # "SUCCESS" | "PARSE_ERROR" | "COMPUTE_ERROR"
    message: Optional[str] = None
```

**JSON 字段命名铁律**：一律 **snake_case**（`value_latex`、`range_start`），Android 端用 `@SerialName` 映射。

### 3.3 LaTeX 词表（仅供参考，不作为过滤规则）

```python
# server/app/common/vocab.py
PLUS, MINUS = "+", "-"
TIMES, DIV = "\\times", "\\div"      # 兼容 \cdot
FRAC, SQRT, POW = "\\frac", "\\sqrt", "^"
TRIG = {"\\sin", "\\cos", "\\tan"}
PI, E = "\\pi", "e"
DIGITS = "0123456789"
PARENS = "()"
```

> 本模块识别输出**原样透传** pix2tex 的结果，**不做词表过滤、不做规范化**。pix2tex 可能输出 `\left(`、`\right)`、`\cdot`、`\over`、`\mathrm` 等变体，全部原样放进 `latex` 字段，由模块 2（latex2sympy2）兜底解析。上面词表只用于报告里说明支持范围。

### 3.4 两条铁律

1. 识别输出原样透传 pix2tex 结果，不做词表过滤、不做结构规范化（`\left(`、`\over` 等变体也原样传）。
2. 改 `common/models.py` 的字段，必须同步通知模块 2 与模块 3。

---

## 4. 本模块对外接口

- **`GET /health`**：返回 `{"status": "ok"}`，供联调前探测后端是否存活。
- **`POST /recognize`**：请求 `{"image": "<base64 无前缀>"}`，响应 `RecognitionResponse`。
- 实现类封装成 `recognition/recognizer.py` 里的 `Recognizer`，router 只做参数校验与调用。
- 挂载点：`app/main.py` 中 `app.include_router(recognition_router)`。

### 4.1 pix2tex 调用要点（照着写即可，别自己摸索）

```python
# recognition/recognizer.py
import os
os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")  # 国内下载权重用镜像
from PIL import Image
from pix2tex.cli import LatexOCR

_model = None
def get_model():
    global _model
    if _model is None:
        _model = LatexOCR()      # 首次会联网下载权重，只在进程启动时加载一次
    return _model

def recognize(image: Image.Image):
    out = get_model()(image)      # 传单张 PIL Image（不是列表）
    # 不同版本返回不同：新版返回 (latex, conf) 元组，旧版只返回字符串
    if isinstance(out, tuple):
        latex, conf = out
    else:
        latex, conf = out, 0.9    # 拿不到置信度时给粗略默认值
    return latex, float(conf)
```

- **模型只加载一次**：放模块级变量/启动时初始化，不要每个请求都 `LatexOCR()`（会反复下载/加载）。
- **router 用同步 `def`**（不要 `async def`）：pix2tex 是同步 CPU 计算，FastAPI 会自动丢线程池，避免阻塞事件循环。
- **失败走错误通道**：Base64 解码失败 / 图片打不开 / 模型报错时，router 返回 `RecognitionResponse(latex="", confidence=0.0, status="ERROR", message="...")`，**不要 500**。

### 4.2 本模块另外两个文件（照抄即可）

```python
# recognition/preprocess.py —— base64→PIL，可选裁剪
import base64
from io import BytesIO
from PIL import Image

def decode_image(b64: str) -> Image.Image:
    raw = base64.b64decode(b64)                 # 无 data URL 前缀
    return Image.open(BytesIO(raw)).convert("RGB")

def crop_to_formula(img: Image.Image) -> Image.Image:
    return img                                   # 本版不裁剪，原样返回
```

```python
# recognition/router.py —— FastAPI 端点
from fastapi import APIRouter
from app.common.models import RecognizeRequest, RecognitionResponse
from app.recognition.preprocess import decode_image, crop_to_formula
from app.recognition.recognizer import recognize

router = APIRouter()

@router.post("/recognize", response_model=RecognitionResponse)
def recognize_endpoint(req: RecognizeRequest):
    try:
        image = crop_to_formula(decode_image(req.image))
    except Exception as e:
        return RecognitionResponse(latex="", confidence=0.0, status="ERROR", message=f"图片解码失败: {e}")
    try:
        latex, conf = recognize(image)
        return RecognitionResponse(latex=latex, confidence=conf, status="SUCCESS")
    except Exception as e:
        return RecognitionResponse(latex="", confidence=0.0, status="ERROR", message=f"识别失败: {e}")
```

- 三个文件（`recognizer.py`/`preprocess.py`/`router.py`）加在一起就是模块 1 的全部代码，`response_model` 让 FastAPI 自动按契约序列化。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E3 候选符号推荐 | `Token.alternatives` 字段已预留 | 否（留空） |
| E8 低置信度高亮 | `Token.confidence` + `range_start/end` 已预留 | 否 |
| E4 框选识别区域 | 客户端裁剪后上传，接口不变 | 否 |
| E5 多公式 | 响应预留可扩展为 `List[RecognitionResponse]` | 否 |
| B2 模型训练对比 | `recognizer.py` 换成自训模型实现即可 | 留接口 |
| B3 数据回流 | 本模块记录识别日志（图片+LaTeX） | 可顺手记日志 |
| B4 实时流式识别 | `/recognize` 保持无状态，可被连续调用 | 否 |

---

## 6. 开发语言与版本要求

| 项 | 要求 |
|---|---|
| 语言 | Python 3.10+（本模块与模块 2 同语言同仓库） |
| Web 框架 | FastAPI + uvicorn |
| 数据校验 | pydantic v2 |
| 识别模型 | pix2tex（LaTeX-OCR） |
| 图像 | Pillow（可选 numpy/OpenCV） |

| 组件 | 推荐版本 |
|---|---|
| Python | 3.10+ |
| FastAPI / uvicorn | 0.111+ / 0.30+ |
| pydantic | 2.x |
| pix2tex | 最新（PyPI `pix2tex`，依赖 PyTorch） |
| Pillow | 10.x |
| pytest / httpx | 8.x / 0.27.x |

---

## 7. 需要额外下载的内容

- **依赖**：本模块单独一份 `requirements-recognition.txt`（pix2tex、torch、fastapi、uvicorn、pydantic、pillow、pytest、httpx）；**不要和模块 2 共用一份**（模块 2 无需 torch/pix2tex）。torch 先装 CPU 版即可。文件内容照抄：
  ```
  fastapi>=0.111
  uvicorn>=0.30
  pydantic>=2.0
  pillow>=10.0
  pix2tex
  pytest>=8.0
  httpx>=0.27
  ```
  （torch 会随 `pix2tex` 自动装；Windows 默认装 CPU 版，够用。）
- **模型权重**：pix2tex 首次运行自动下载，需联网一次。**国内直连 huggingface 常失败**，先设镜像（`os.environ["HF_ENDPOINT"]="https://hf-mirror.com"`，见 §4.1）。
- **训练集**（仅 B2 自训时用，本次不落实）：CROHME 官方包（见旧 `hmer_calc_1.md` 第 7 节）。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
└── server/
    ├── app/
    │   ├── __init__.py                  # 空文件（Python 包标记，下同）
    │   ├── main.py                      # FastAPI 入口，挂两个 router（组长锁定）
    │   ├── common/                      # 共享契约（组长锁定）
    │   │   ├── __init__.py
    │   │   ├── models.py                # pydantic 数据模型
    │   │   └── vocab.py                 # 词表
    │   └── recognition/                 # 本模块实现
    │       ├── __init__.py
    │       ├── router.py                # POST /recognize
    │       ├── recognizer.py            # pix2tex 封装
    │       └── preprocess.py            # base64→PIL + 可选裁剪
    ├── tests/
    │   ├── fixtures/                    # 测试图片（自备一张手写公式样图）
    │   └── test_recognition.py          # 本模块独立测试
    └── requirements-recognition.txt     # 本模块依赖（pix2tex/torch 等）
```

---

## 9. 测试方式（独立测试）

```python
# tests/test_recognition.py —— 只测本模块，不依赖模块 2
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.recognition.router import router as recognition_router

app = FastAPI()                 # 独立 app，只挂本模块 router
app.include_router(recognition_router)
client = TestClient(app)

def test_recognize_returns_valid_latex():
    import base64
    img = open("tests/fixtures/sample1.png", "rb").read()
    r = client.post("/recognize", json={"image": base64.b64encode(img).decode()})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "SUCCESS"
    assert isinstance(body["latex"], str) and body["latex"]
    assert 0.0 <= body["confidence"] <= 1.0

def test_recognize_bad_image_returns_error():
    r = client.post("/recognize", json={"image": ""})
    assert r.status_code == 200
    assert r.json()["status"] == "ERROR"
```

运行：`cd server && pytest tests/test_recognition.py`

---

## 10. 交付物与验收要点

1. `POST /recognize` 可被 curl 调通，返回合法 `RecognitionResponse`。
2. 输出 `latex` 为 pix2tex 原始输出（原样透传，含 `\left` 等变体也接受），`confidence` ∈ [0,1]。
3. `confidence` ∈ [0,1]。
4. 独立测试 `pytest tests/test_recognition.py` 通过。
5. 对照 `ALL.md`「模块 1 查验对照单」逐项自查。
