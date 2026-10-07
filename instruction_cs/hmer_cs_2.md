# 模块 2 指导文档：后端计算服务（C/S 版，C4 / C5 / C6 的服务端部分）

> 项目：HMER-Calc（C/S 架构）
> 责任人：成员 2
> 架构：手机开热点，电脑跑后端。本模块是后端「LaTeX → 数值结果」计算服务。
> 全局约定以同目录 `ALL.md` 为准。旧方案 `hmer_calc_2.md` 为日后端侧对比的余量参考，不在本次落实范围。

---

## 0. 模块定位

提供一个 HTTP 接口 `POST /calculate`：接收 LaTeX 字符串，解析并计算，返回数值结果。
**关键提醒：本模块用 Python 的 sympy / latex2sympy2 实现，这正是 C/S 架构相比端侧最大的省力点。**
**交付物是"能独立启动、能被 pytest 独立测试、能被模块 3 通过 HTTP 调通"的计算服务。**

---

## 1. 处理流程（箭头 = 数据流向）

```
HTTP 请求 { "latex": "\frac{1}{2}+\sqrt{9}", "mode": "deg" }
   --> 参数校验（mode ∈ {"deg","rad","auto"}，组长订正 2026-10 新增 auto）
   --> 归一化：合并被空白拆散的数字 `4 8` → `48`（组长订正 2026-10，见 §4 兜底说明）
   --> 【C4 解析】latex2sympy2 把 LaTeX 转成 sympy 表达式
   --> 【C5 计算】sympy 求值
        ├─ 成功 --> 数值 value + valueLatex
        └─ 失败 --> 分类 PARSE_ERROR / COMPUTE_ERROR，携带 message
   --> 封装为 CalculateResponse(latex, value, valueLatex, status, message)
   --> 返回 JSON
```

**角度制处理**（组长订正 2026-10：扩充三角函数 + 新增 auto）：

- `mode="deg"`：对 `sin/cos/tan/cot/sec/csc` 的参数做 `x * pi / 180`；对 `arcsin/arccos/arctan` 的**输出**做 `× 180 / pi`（输出按角度，如 `\arcsin(1/2)` → 30）。
- `mode="rad"`：不做任何换算（反三角输出按弧度）。
- `mode="auto"`：逐节点判断——三角参数是**纯数字且不含 π**（如 `\sin(30)`、`\cot(45)`）→ 按角度换算；参数含 π 或变量（如 `\sin(\pi/2)`、`\sin(x)`）→ 保持不动（按弧度）。反三角在 auto 下按弧度输出。

---

## 2. 需要实现的功能

| 编号 | 功能 | 说明 |
|---|---|---|
| C4-1 | LaTeX 解析 | latex2sympy2 把 LaTeX 转 sympy 表达式 |
| C5-1 | 四则运算 | + − × ÷ |
| C5-2 | 幂运算 | `a^{b}` |
| C5-3 | 根号运算 | `\sqrt{a}` |
| C5-4 | 基础三角函数 | sin / cos / tan，支持角度/弧度 |
| C5-5 | 输出数值结果 | 返回 `float`（或精确值） |
| C6 | 结果封装 | `CalculateResponse`，含可回显 LaTeX、状态、错误信息 |
| — | 独立可测试 | 提供 `pytest tests/test_calculation.py` |

---

## 3. 全局统一约定（必须遵守，以 ALL.md 为准）

### 3.1 服务地址约定

- 默认端口 **8000**，与模块 1 同进程，启动命令：`uvicorn app.main:app --host 0.0.0.0 --port 8000`（**必须 `--host 0.0.0.0`**，否则手机连不上），各自独立成 router。
- `curl http://127.0.0.1:8000/health` 自测。

### 3.2 JSON 契约（本模块的请求/响应，放 `common/models.py`，与模块 1/3 共用）

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
    mode: str = "deg"            # "deg" | "rad" | "auto"（组长订正 2026-10：新增 auto，默认值保持 deg 不变）

class CalculateResponse(BaseModel):
    latex: str
    value: Optional[float] = None
    value_latex: Optional[str] = None
    status: str                  # "SUCCESS" | "PARSE_ERROR" | "COMPUTE_ERROR"
    message: Optional[str] = None
```

**JSON 字段命名铁律**：一律 **snake_case**（`value_latex`），Android 端用 `@SerialName` 映射。

**`value_latex` 语义（组长订正 2026-10-06）**：它是**结果**的 LaTeX，不是输入式。实现为先 `sympy.simplify(expr)` 再 `latex`；化简后仍含未求值函数（如 rad 下的 `\sin 30`）即没有有用的精确形式，置 `None`，由客户端只显示数值。

> 为什么必须化简：`rad` 模式不做角度换算，`expr` 保持解析后的**原始输入式**，直接 `latex` 会把**输入**当结果回显（`1+2*3` → `"1 + 2 \cdot 3"`）；而 `deg`/`auto` 换算时重建表达式、sympy 顺带求值，恰好返回结果。三档行为不一致会让客户端「数值 + 精确值」两行的去重逻辑失效，`rad` 档凭空多显示一行。

### 3.3 LaTeX 词表与映射（本模块必须能逐字解析这些输入）

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

| 数学含义 | 输入 LaTeX | 解析为 |
|---|---|---|
| 加 / 减 | `+` / `-` | `+` / `-` |
| 乘 | `\times`（兼容 `\cdot`） | `*` |
| 除 | `\div` | `/` |
| 分数 | `\frac{1}{2}` | `1/2` |
| 幂 | `2^{3}` | `2**3` |
| 根号 | `\sqrt{9}` | `sqrt(9)` |
| 三角 | `\sin(30)` | `sin(30)`（deg/auto 换算，rad 不换算） |
| 扩充三角 | `\cot(45)` / `\sec(60)` / `\csc(30)` | `cot(45)` 等（组长订正 2026-10 新增，换算规则同 sin） |
| 反三角 | `\arcsin(1/2)` | `asin(1/2)`（deg 输出 ×180/π → 30；rad/auto 输出弧度） |
| π / e | `\pi` / `e` | `pi` / `E` |

> latex2sympy2 本身就能解析 `\left(`、`\right)`、`\cdot`、`\mathrm`、`\over` 等常见变体，**不用手写清洗**。上表是「必须覆盖的基线」；模块 1 透传的 pix2text 原始输出若超出基线，交给 latex2sympy2 兜底解析，解析失败按 §4 返回 `PARSE_ERROR`。

> **求和 / 积分的行为边界（组长订正 2026-10-07）**：二者不在验收基线内，但 latex2sympy2/sympy 天然支持，属**免费附带**（不承诺正确、不宣传）。
> - 求和 `\sum` **必须写上下限**：`\sum_{n=0}^{3} n` → 6 能算；缺上下限（`\sum n`）latex2sympy2 直接 `PARSE_ERROR`；上界是符号（`\sum_{n=1}^{n}`）无法数值化 → `COMPUTE_ERROR`。
> - 积分分定/不定：定积分 `\int_{0}^{1} x dx` → 0.5 能算；不定积分 `\int x dx`（无上下限）解析为 sympy 的 `Integral(x, x)`，**无积分区间、不做数值化** → `COMPUTE_ERROR`。
> - 一句话：**不定积分 / 无界求和返回计算失败、不做数值化**；要算出数值，必须在 LaTeX 里写明上下限。

### 3.4 两条铁律

1. 优先支持花括号规范形式（`\frac{...}{...}`、`\sqrt{...}`、`a^{...}`）；`\left(...\right)`、`\cdot`、`\over` 等变体靠 latex2sympy2 兜底解析，不额外手写清洗。
2. 改 `common/models.py` 的字段，必须同步通知模块 1 与模块 3。

---

## 4. 本模块对外接口

- **`POST /calculate`**：请求 `{"latex": "...", "mode": "deg"|"rad"|"auto"}`，响应 `CalculateResponse`。
- 实现封装成 `calculation/calculator.py` 里的 `Calculator`，router 只做参数校验与调用。
- **错误处理是重点**：所有异常（解析失败、除零、未定义变量等）都要转成 `CalculateResponse`，`status` 取 `PARSE_ERROR` 或 `COMPUTE_ERROR` 并填 `message`，**绝不让接口 500 崩溃**。
- **数字粘连兜底（组长订正 2026-10）**：解析前先合并「数字-空白-数字」（`4 8 \div6` → `48 \div6`）。这是第二道保险——模块一已在识别端修复，但 C7 修正页用户手工输入的 LaTeX 同样可能带拆散数字，而 latex2sympy2 会把 `4 8` **静默**解析成 4×8（不报错、算错）。规则与模块一 `recognition/postprocess.py` 一致，但**各持一份实现、互不 import**（模块边界：见 `hmer_cs_1.md` §3.4）。显式乘号（`4 \cdot 8` = 32）不受影响。
- **C7 修正闭环（跨模块）**：用户修正后把新的 LaTeX 重新 POST 到本接口再算一次。修正的所见即所得编辑 UI 在模块 3（Android，见 `hmer_cs_3.md`），本模块只需保证「修正后的 LaTeX 仍能被 latex2sympy2 解析」，解析失败返回 `PARSE_ERROR` 让用户继续改。
- 挂载点：`app/main.py` 中 `app.include_router(calculation_router)`。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E6 常量/模式切换 | `mode` 参数已定义，`\pi`/`e` 已在词表 | 解析层顺手支持 |
| E7 结果格式化 | **已落实（2026-10-06）**：`value_latex` 返回**化简后的结果** LaTeX（精确分数如 `\frac{5}{6}`）；无精确形式时返回 `None`。三档（auto/deg/rad）行为一致 | ✅ 已做 |
| B3 数据回流 | 本模块记录「输入 LaTeX + 修正后 LaTeX + 结果」日志 | 可顺手记日志 |
| B5 端云协同 | 本身即云端计算 | — |

---

## 6. 开发语言与版本要求

| 项 | 要求 |
|---|---|
| 语言 | Python 3.10+（与模块 1 同仓库） |
| Web 框架 | FastAPI + uvicorn |
| 解析/计算 | latex2sympy2 + sympy |
| 数据校验 | pydantic v2 |

| 组件 | 推荐版本 |
|---|---|
| Python | 3.10+ |
| FastAPI / uvicorn | 0.111+ / 0.30+ |
| latex2sympy2 | 最新（PyPI `latex2sympy2`） |
| sympy | 1.12+ |
| pytest / httpx | 8.x / 0.27.x |

---

## 7. 需要额外下载的内容

- **依赖**：`pip install -r requirements.txt`（全后端**共享一份**，含 pix2text、latex2sympy2、sympy、fastapi、uvicorn、pydantic、pillow、pytest、httpx；pix2text 会顺带装 onnxruntime、cnocr、cnstd 等）。
- **无需训练集**。
- 建议本地写好单元测试覆盖词表里每种运算（分数、幂、根号、三角、除零、非法结构）。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
└── server/
    ├── app/
    │   ├── main.py                      # FastAPI 入口，挂两个 router（组长锁定）
    │   ├── common/                      # 共享契约（组长锁定，成员只读）
    │   │   ├── models.py
    │   │   └── vocab.py
    │   └── calculation/                 # 本模块实现
    │       ├── router.py                # POST /calculate
    │       └── calculator.py            # latex2sympy2 + sympy 封装 + 数字粘连兜底
    ├── tests/
    │   └── test_calculation.py          # 本模块独立测试
    └── requirements.txt
```

---

## 9. 测试方式（独立测试）

```python
# tests/test_calculation.py —— 只测本模块，不依赖模块 1
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.calculation.router import router as calculation_router

app = FastAPI()                 # 独立 app，只挂本模块 router
app.include_router(calculation_router)
client = TestClient(app)

def test_fraction():
    r = client.post("/calculate", json={"latex": "\\frac{1}{2}", "mode": "deg"})
    assert r.json()["status"] == "SUCCESS"
    assert abs(r.json()["value"] - 0.5) < 1e-9

def test_sqrt():
    r = client.post("/calculate", json={"latex": "\\sqrt{9}", "mode": "deg"})
    assert abs(r.json()["value"] - 3.0) < 1e-9

def test_sin_degree():
    r = client.post("/calculate", json={"latex": "\\sin(30)", "mode": "deg"})
    assert abs(r.json()["value"] - 0.5) < 1e-9

def test_divide_by_zero():
    r = client.post("/calculate", json={"latex": "\\frac{1}{0}", "mode": "deg"})
    assert r.json()["status"] in ("COMPUTE_ERROR", "PARSE_ERROR")
```

运行：`cd server && pytest tests/test_calculation.py`

> **稳定性补充（对应 C7 所见即所得编辑）**：模块 3 用编辑器（huarangmeng/latex）回写的 LaTeX 形式可能与手写样例不同（如 `\sin 30` 不带括号、`2^3` 不带花括号、`\left(...\right)`）。建议补一组「编辑器输出样例」测试：把这些典型形式直接喂 `/calculate` 断言能 SUCCESS；跑不通的形式在模块 3 侧规范化后再发（见 `hmer_cs_3.md` §4.1）。

---

## 10. 交付物与验收要点

1. `POST /calculate` 可被 curl 调通，返回合法 `CalculateResponse`。
2. 能正确解析词表覆盖的所有合法输入（对照映射表逐条测试）。
3. 任何非法输入返回 `PARSE_ERROR`/`COMPUTE_ERROR`，不 500、不崩溃。
4. 角度制/弧度制/自动（auto）切换生效（后端默认 deg；Android 端默认 auto）。
5. 被空白拆散的数字不改变语义：`4 8 \div6` → 8、`2 5+3 \times4` → 37、`\sqrt{4 8}` → √48；同时显式乘号 `4 \cdot 8` 仍为 32（防误合并）。
6. 独立测试 `pytest tests/test_calculation.py` 通过。
6. 对照 `ALL.md`「模块 2 查验对照单」逐项自查。
