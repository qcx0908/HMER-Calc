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
   --> 【C2 预处理】EXIF 方向归正 + 尺寸控制（最长边 ≤1600）--> 生成方向候选（无 EXIF 时 0/90/180/270°）
   --> 【C3 识别】pix2text（MFR 模型）逐方向推理 --> 每条 LaTeX + score
   --> 每个候选先做混淆归一化（数字/字母误读、拆散函数名，2026-10-08）→ 再多方向竞优
   --> 低置信度回退：首轮 < 0.95 时裁到墨迹区域再试一轮；裁剪轮需 +0.03 分且形态不变差才替换（2026-10）
   --> 数字粘连修复：合并被空白拆散的数字 `4 8 6` → `486`（组长订正 2026-10）
   --> 多行/多公式检测（array/matrix/cases 等 → ERROR）
   --> 置信度分档（≥0.95 正常；0.55~0.95 返回并提示人工核对；<0.55 → ERROR）
   --> 封装为 RecognitionResponse(latex, confidence, tokens=[]) + X-Recognition-Meta 诊断头
   --> 返回 JSON
```

**预处理（C2）**：EXIF 方向归正（`ImageOps.exif_transpose`）+ 尺寸控制（最长边 ≤1600），**不要做二值化/去噪**（会降低识别率）。无可信 EXIF 时生成 0°/90°/180°/270° 四个方向候选。

---

## 2. 需要实现的功能

| 编号 | 功能 | 说明 |
|---|---|---|
| C2-1 | 图像解码 | Base64 → PIL Image |
| C2-2 | EXIF 方向归正 + 尺寸控制 | `exif_transpose` 归正方向；最长边 ≤1600 降采样 |
| C2-3 | 方向候选 + 交给模型 | 无 EXIF 时生成 0/90/180/270° 候选；pix2text 推理 |
| C3-1 | 深度学习识别 | pix2text（P2T，Transformer 架构的 MFR 数学公式识别模型，已用手写数据重训）图片→LaTeX |
| C3-2 | 置信度输出 | 整体 score（Pix2Text 无 token 级，`tokens` 恒空 `[]`） |
| — | 独立可测试 | 提供 `pytest tests/test_recognition.py` |

> 说明：pix2text 首次运行会自动下载模型权重（需联网一次）。基于 onnxruntime，CPU 即可跑，无需 PyTorch/CUDA 配置。

### 2.1 为什么用 pix2text + 本模块的识别加固语义

> **为什么是 pix2text 而不是 pix2tex**：输入是纯手写公式。pix2tex（LaTeX-OCR）默认权重偏印刷体（im2latex 数据），对手写体准确率明显下降；pix2text（P2T）的 MFR 数学公式识别模型已用手写数据重训，对手写体更友好。代价是 pix2text 更重（cnocr/cnstd/onnxruntime）且**不输出 token 级信息**（见下面第 3 条）。

以下七个语义是模块 1 实际实现里对契约最小集的加固，接口字段不变，只影响返回行为：

1. **EXIF 方向归正 + 多方向竞优**：图片带可信 EXIF 时归正后只认 0°；无 EXIF 时在 0/90/180/270° 各识别一遍，按 score 取最优。对 ≤2 字符的退化输出（如 `\begin{matrix}\hline{}\\` 这类垃圾）降级，避免它压过正确结果。
2. **多行/多公式检测**：识别出 `array`/`matrix`/`cases`/`aligned` 等多行环境且含 ≥2 处换行时，判定为多公式，返回 `status="ERROR"`（当前仅支持单一公式 C3，多公式 E7 未实现）。
3. **置信度分档（2026-10-08 修订）**：`score ≥ 0.95` 正常返回；`0.55 ≤ score < 0.95` **仍返回最高分结果**，`message` 提示「识别置信度偏低，结果仅供参考，请人工核对」（对应 C7 闭环）；`score < 0.55` 才改 `status="ERROR"`（过低基本是噪声，返回反而误导）。实测依据：正确样本 0.9568~1.0，错误样本 0.8977~0.9445，两组重叠，故 `confidence` 只能做提示、不能做正确性判据。
4. **`X-Recognition-Meta` 诊断头**：各方向 `angle`/`status`/`score`/`reason`/`seconds` 等诊断信息放 HTTP 响应头，不进入 JSON 契约体。
5. **数字粘连修复（组长订正 2026-10）**：MFR 解码器会把间隔偏大的相邻数字当两个 token 输出（手写 `486` → `4 8 6`，且 score 可达 1.0，门槛拦不住），而 latex2sympy2 会把 `4 8` **静默**算成 4×8。`postprocess.merge_split_digits` 在竞优选出结果后合并「数字-空白-数字」形态（`4 8 6`→`486`、`2 5+3 \times4`→`25+3 \times4`），显式运算符（`\cdot`/`\times`）一律不动。实测样本：12/25/48 三张照片修复后输出 `12-7` / `25+3 \times4` / `48 \div6`。
6. **低置信度墨迹裁剪重试（组长订正 2026-10；2026-10-08 加替换门槛）**：首轮最高分 < 0.95 时，把候选图裁到墨迹包围盒（+5% 留白）再跑一轮；裁剪轮需比首轮 **+0.03 分以上**且形态/可信度不变差才替换（原实现「rank 更高就换」会把首轮正确结果顶掉，实测 P8/P10）。裁剪无变化的候选直接跳过（好图零额外开销）。动机：整页照片里公式占比小时模型易误读——实测 `12.jpg` 全图 0° 输出 `'( 2-7'`（0.7831），裁剪后 `'1 2-7'`（**0.9960**，先合并为 `12-7` 再过关）。裁剪只做几何裁切、不改像素值（§3.4 铁律 1 的例外之一）。
7. **数字/字母混淆纠正（成员 1，2026-10-08）**：模型存在系统性误读——`8→z`、`6→L`、`0→o`、`×→x`、`cos` 被拆成 `c o s`、度号 `°→ν/σ` 等。`postprocess.normalize_digit_confusions` 在**每个候选竞优之前**做保守归一化（必须由相邻数字或函数名约束，避免改坏真正的变量），并参与排序；竞优另加「字母参与乘除 / 完全无数字 / 结构命令堆砌」降级规则。实测能力：39 张人工标注样本正确 34 张（87.2%，校正后约 89.7%），详见 `分发/HMER-Calc-TestKit/RECOGNITION-CAPABILITY.md`。

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
    mode: str = "deg"            # "deg" | "rad" | "auto"（组长订正 2026-10：新增 auto，语义见 hmer_cs_2.md §1）

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

> 本模块识别输出**原样透传** pix2text 的结果，**不做词表过滤、不做规范化**。pix2text 可能输出 `\left(`、`\right)`、`\cdot`、`\over`、`\mathrm` 等变体，全部原样放进 `latex` 字段，由模块 2（latex2sympy2）兜底解析。上面词表只用于报告里说明支持范围。
>
> ⚠️ **组长订正 2026-10 的唯一例外**：`\left(`/`\over` 等变体仍原样透传，但「数字被空白拆散」（`4 8 6`）会做**合并修复**（§2.1 第 5 条）——因为它是**模型解码错误**而非合法变体，且下游 latex2sympy2 会把它**静默算错**（`4 8` → 4×8）。除此之外不得增加任何过滤/规范化。

### 3.4 两条铁律

1. 识别输出原样透传 pix2text 结果，不做词表过滤、不做结构规范化（`\left(`、`\over` 等变体也原样传）。
   **例外**：数字粘连修复（§2.1 第 5 条）、低置信度墨迹裁剪重试（§2.1 第 6 条，仅几何裁切、不改像素值）、数字/字母混淆纠正（§2.1 第 7 条，保守规则、有数字/函数名约束）。三者都有实测回归测试（`tests/test_recognition.py` 对应末节）。
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
| E3 候选符号推荐 | `Token.alternatives` 字段已预留 | 放弃（由 C7 所见即所得点选修正覆盖，见模块 3） |
| E8 低置信度高亮 | `Token.confidence` + `range_start/end` 已预留 | 降级实现：整体置信度分档——0.55~0.95 返回并提示人工核对，<0.55 拦截（见 §2.1 第 3 条） |
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
| 识别模型 | pix2text（P2T，含 MFR 数学公式识别模型） |
| 图像 | Pillow（可选 numpy/OpenCV） |

| 组件 | 推荐版本 |
|---|---|
| Python | 3.10+ |
| FastAPI / uvicorn | 0.111+ / 0.30+ |
| pydantic | 2.x |
| pix2text | 最新（PyPI `pix2text`，基于 onnxruntime） |
| Pillow | 10.x |
| pytest / httpx | 8.x / 0.27.x |

---

## 7. 需要额外下载的内容

- **依赖**：`pip install -r requirements.txt`（全后端**共享一份**，含 pix2text、latex2sympy2、sympy、fastapi、uvicorn、pydantic、pillow、pytest、httpx；pix2text 会顺带装 onnxruntime、cnocr、cnstd 等）。
- **模型权重**：pix2text 首次运行自动下载，需联网一次。
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
    │       ├── recognizer.py            # pix2text 封装 + 两轮竞优（含裁剪重试）
    │       ├── preprocess.py            # base64→PIL + 方向候选 + crop_to_ink 墨迹裁剪
    │       └── postprocess.py           # 数字粘连修复 merge_split_digits（组长订正 2026-10）
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
2. 输出 `latex` 为 pix2text 原始输出（原样透传，含 `\left` 等变体也接受；数字粘连已按 §2.1 第 5 条修复），`confidence` ∈ [0,1]。
3. `confidence` ∈ [0,1]。
4. 独立测试 `pytest tests/test_recognition.py` 通过。
5. 三位数内识别正确：两位数不得被空白拆散（回归素材 `tests/fixtures/photo_12.jpg` / `photo_25.jpg` / `photo_48.jpg`，期望输出 `12-7` / `25+3 \times4` / `48 \div6`）。
6. 对照 `ALL.md`「模块 1 查验对照单」逐项自查。
