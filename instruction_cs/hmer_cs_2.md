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
   --> 参数校验（mode ∈ {"deg","rad"}）
   --> 【C4 解析】latex2sympy2 把 LaTeX 转成 sympy 表达式
   --> 【C5 计算】sympy 求值
        ├─ 成功 --> 数值 value + valueLatex
        └─ 失败 --> 分类 PARSE_ERROR / COMPUTE_ERROR，携带 message
   --> 封装为 CalculateResponse(latex, value, valueLatex, status, message)
   --> 返回 JSON
```

**角度制处理**：`mode="deg"` 时，对 `sin/cos/tan` 的参数做 `x * pi / 180` 换算后再交给 sympy（sympy 的三角默认弧度制）。

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

- 默认端口 **8000**，与模块 1 同进程（`uvicorn app.main:app`），各自独立成 router。
- `curl http://127.0.0.1:8000/health` 自测。

### 3.2 JSON 契约（本模块的请求/响应，放 `common/models.py`，与模块 1/3 共用）

```python
# server/app/common/models.py
from pydantic import BaseModel
from typing import List, Optional

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

**JSON 字段命名铁律**：一律 **snake_case**（`value_latex`），Android 端用 `@SerialName` 映射。

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
| 三角 | `\sin(30)` | `sin(30)`（deg 时换算） |
| π / e | `\pi` / `e` | `pi` / `E` |

### 3.4 两条铁律

1. 结构一律按带花括号规范形式解析（`\frac{...}{...}`、`\sqrt{...}`、`a^{...}`）。
2. 改词表/映射，必须同步通知模块 1 与模块 3。

---

## 4. 本模块对外接口

- **`POST /calculate`**：请求 `{"latex": "...", "mode": "deg"|"rad"}`，响应 `CalculateResponse`。
- 实现封装成 `calculation/calculator.py` 里的 `Calculator`，router 只做参数校验与调用。
- **错误处理是重点**：所有异常（解析失败、除零、未定义变量等）都要转成 `CalculateResponse`，`status` 取 `PARSE_ERROR` 或 `COMPUTE_ERROR` 并填 `message`，**绝不让接口 500 崩溃**。
- 挂载点：`app/main.py` 中 `app.include_router(calculation_router)`。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E6 常量/模式切换 | `mode` 参数已定义，`\pi`/`e` 已在词表 | 解析层顺手支持 |
| E7 结果格式化 | sympy 可返回精确分数；`value_latex` 可扩展 | 可选（sympy 天然支持） |
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

- **依赖**：`pip install -r requirements.txt`（含 fastapi、uvicorn、latex2sympy2、sympy、pydantic、pytest、httpx）。
- **无需训练集**。
- 建议本地写好单元测试覆盖词表里每种运算（分数、幂、根号、三角、除零、非法结构）。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
└── server/
    ├── app/
    │   ├── main.py                      # FastAPI 入口，挂两个 router（模块 1+2 共用）
    │   ├── common/                      # 共享契约（本模块与模块 1 共同维护）
    │   │   ├── models.py
    │   │   └── vocab.py
    │   └── calculation/                 # 本模块实现
    │       ├── router.py                # POST /calculate
    │       └── calculator.py            # latex2sympy2 + sympy 封装
    ├── tests/
    │   └── test_calculation.py          # 本模块独立测试
    └── requirements.txt
```

---

## 9. 测试方式（独立测试）

```python
# tests/test_calculation.py —— 只测本模块，不依赖模块 1
from fastapi.testclient import TestClient
from app.main import app

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

---

## 10. 交付物与验收要点

1. `POST /calculate` 可被 curl 调通，返回合法 `CalculateResponse`。
2. 能正确解析词表覆盖的所有合法输入（对照映射表逐条测试）。
3. 任何非法输入返回 `PARSE_ERROR`/`COMPUTE_ERROR`，不 500、不崩溃。
4. 角度制/弧度制切换生效（默认 deg）。
5. 独立测试 `pytest tests/test_calculation.py` 通过。
6. 对照 `ALL.md`「模块 2 查验对照单」逐项自查。
