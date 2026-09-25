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

- 默认端口 **8000**，全后端一个进程，启动命令：`uvicorn app.main:app --host 0.0.0.0 --port 8000`（**必须 `--host 0.0.0.0`**，否则手机连不上；Windows 防火墙放行 8000）。
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
- **`POST /recognize`**：请求 `RecognizeRequest`（`{"image": "<base64 无前缀>"}`），响应 `RecognitionResponse`（失败走 `status="ERROR"` + `message`，不 500）。
- 实现类封装成 `recognition/recognizer.py` 里的 `Recognizer`，router 只做参数校验与调用。
- 挂载点：`app/main.py` 中 `app.include_router(recognition_router)`。

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

- **依赖**：`pip install -r requirements.txt`（全后端**共享一份**，含 pix2tex、latex2sympy2、sympy、fastapi、uvicorn、pydantic、pillow、pytest、httpx；pix2tex 会顺带装 torch）。
- **模型权重**：pix2tex 首次运行自动下载，需联网一次。
- **训练集**（仅 B2 自训时用，本次不落实）：CROHME 官方包（见旧 `hmer_calc_1.md` 第 7 节）。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
└── server/
    ├── app/
    │   ├── main.py                      # FastAPI 入口，挂两个 router（组长锁定）
    │   ├── common/                      # 共享契约（组长锁定，成员只读）
    │   │   ├── models.py                # pydantic 数据模型
    │   │   └── vocab.py                 # 词表
    │   └── recognition/                 # 本模块实现
    │       ├── router.py                # POST /recognize
    │       ├── recognizer.py            # pix2tex 封装
    │       └── preprocess.py            # base64→PIL + 可选裁剪
    ├── tests/
    │   ├── fixtures/                    # 测试图片
    │   └── test_recognition.py          # 本模块独立测试
    └── requirements.txt
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
