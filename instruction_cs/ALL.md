# ALL.md —— 组长查验对照单（C/S 版）

> 用途：组长在收集、整合三个模块交付物时，对照本单查验各模块是否满足整体集成要求。
> 维护：组长。全局契约以本文件为准，模块文档 `hmer_cs_1/2/3.md` 与之冲突时以本文件为准。
> 旧方案（端侧）文档 `hmer_calc_*`、`HEAD.md` 保留作日后端侧对比的余量参考，不在本次落实范围。

---

## 一、全局契约核对（先验这个，任何一项不符都退回）

- [ ] 后端统一端口 8000，一个 FastAPI 进程挂两个 router（`/recognize`、`/calculate`）
- [ ] `server/app/common/` 两个文件三方一致：
  - [ ] `models.py`（`Token`/`RecognitionResponse`/`CalculateRequest`/`CalculateResponse` 字段一致）
  - [ ] `vocab.py`（词表一致，与 Android 端 `LatexVocab.kt` 一致）
- [ ] JSON 字段一律 snake_case（`value_latex`、`range_start`），Android 用 `@SerialName` 映射
- [ ] LaTeX 词表与映射双方遵守（`\frac/\sqrt/^{}/\times/\div/\sin/\cos/\tan/\pi/e` + 数字 + 括号）
- [ ] 两条铁律遵守：结构带花括号规范形式；改词表/映射同步通知

### 契约基准（金标准，查验时对照）

```python
# server/app/common/models.py
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
    mode: str = "deg"              # "deg" | "rad"

class CalculateResponse(BaseModel):
    latex: str
    value: Optional[float] = None
    value_latex: Optional[str] = None
    status: str                    # SUCCESS | PARSE_ERROR | COMPUTE_ERROR
    message: Optional[str] = None
```

```kotlin
// android/.../common/Dto.kt（对应字段，snake_case 用 @SerialName 映射）
@Serializable data class Token(val text: String, val confidence: Double,
    @SerialName("range_start") val rangeStart: Int,
    @SerialName("range_end") val rangeEnd: Int,
    val alternatives: List<String> = emptyList())
@Serializable data class RecognitionResponse(val latex: String, val confidence: Double,
    val tokens: List<Token> = emptyList())
@Serializable data class CalculateRequest(val latex: String, val mode: String = "deg")
@Serializable data class CalculateResponse(val latex: String, val value: Double? = null,
    @SerialName("value_latex") val valueLatex: String? = null,
    val status: String, val message: String? = null)
```

---

## 二、模块 1（后端识别）查验对照单

| # | 查验项 | 怎么验 | 结果 |
|---|---|---|---|
| M1-1 | `/health` 可访问 | `curl http://127.0.0.1:8000/health` 返回 ok | ☐ |
| M1-2 | `/recognize` 返回合法 JSON | `curl` 传 Base64 图，返回 `latex`+`confidence` | ☐ |
| M1-3 | `latex` 合法 | 逐字符合词表，无 `\over`/`\left` 等 | ☐ |
| M1-4 | `confidence` ∈ [0,1] | 抽查若干样本 | ☐ |
| M1-5 | 独立测试通过 | `pytest tests/test_recognition.py` 全绿 | ☐ |
| M1-6 | 不依赖模块 2 | 只挂 recognition router 也能启动并测通 | ☐ |
| M1-7 | 预留字段未删 | `tokens`/`alternatives`/`range_*` 保留 | ☐ |

---

## 三、模块 2（后端计算）查验对照单

| # | 查验项 | 怎么验 | 结果 |
|---|---|---|---|
| M2-1 | `/calculate` 返回合法 JSON | `curl` 传 LaTeX，返回 `value`+`status` | ☐ |
| M2-2 | 四则正确 | `1+2*3` 等手工比对 | ☐ |
| M2-3 | 分数正确 | `\frac{1}{2}` → 0.5 | ☐ |
| M2-4 | 幂正确 | `2^{3}` → 8 | ☐ |
| M2-5 | 根号正确 | `\sqrt{9}` → 3 | ☐ |
| M2-6 | 三角（角度制）正确 | `\sin(30)` → 0.5 | ☐ |
| M2-7 | 弧度制切换 | `mode="rad"` 下 `\sin(\pi)` 正确 | ☐ |
| M2-8 | 非法输入不 500 | 除零、括号不匹配 → 返回 `PARSE_ERROR`/`COMPUTE_ERROR` + message | ☐ |
| M2-9 | 独立测试通过 | `pytest tests/test_calculation.py` 全绿 | ☐ |
| M2-10 | 不依赖模块 1 | 只挂 calculation router 也能启动并测通 | ☐ |

---

## 四、模块 3（Android 客户端）查验对照单

| # | 查验项 | 怎么验 | 结果 |
|---|---|---|---|
| M3-1 | 拍照/选图可用 | CameraX / Photo Picker 调起 | ☐ |
| M3-2 | `/recognize` 调通 | 模拟器 `10.0.2.2:8000` 下识别出 LaTeX | ☐ |
| M3-3 | `/calculate` 调通 | 识别结果能算出数值 | ☐ |
| M3-4 | 修正闭环 | 编辑 LaTeX → 重新计算 → 结果刷新 | ☐ |
| M3-5 | 错误不崩 | 后端未启动/网络失败 → 友好提示不崩溃 | ☐ |
| M3-6 | UI 只依赖接口 | 可注入替换 `Local`/`Remote` 实现 | ☐ |
| M3-7 | LaTeX 渲染正常 | jlatexmath 显示公式 | ☐ |
| M3-8 | 明文 HTTP 已配置 | `usesCleartextTraffic` 或 network config | ☐ |
| M3-9 | 后端地址可配置 | 能切换模拟器/真机热点地址 | ☐ |

---

## 五、联合测试验收清单（组长主导）

### 5.1 模块 1+2 联合测试（后端整机）

- [ ] 启动完整后端 `uvicorn app.main:app`，`/health` 通
- [ ] `pytest tests/test_integration.py` 全绿（用模块 1 识别一张图 → 拿 latex → 喂给模块 2 → 断言结果）
- [ ] 无 integration 测试时，手动：`curl /recognize` 拿 latex → `curl /calculate` 算结果，全链路通

### 5.2 模块 1+2+3 联合测试（端到端）

- [ ] 后端全起 + Android 客户端跑通完整流程
- [ ] 核心样例逐个通过（至少：分数、幂、根号、三角函数各一例）
- [ ] 模拟器（`10.0.2.2`）验证一次
- [ ] 真机热点（电脑 IP）验证一次
- [ ] 错误场景不崩：空输入、除零、非法 LaTeX、后端断连

---

## 六、红牌项（出现即退回，不能进入整合）

1. 后端契约文件 `common/models.py` / `vocab.py` 被成员私自改动，三方不一致。
2. `/recognize` 或 `/calculate` 遇非法输入返回 500 崩溃（必须返回结果对象）。
3. 识别输出 `latex` 超出词表（含 `\over`、`\left`、`\right` 等未约定 token）。
4. Android 端没走 `common` 接口、把 `RemoteRecognizer`/`RemoteCalculator` 具体类硬编码进 UI（日后无法换端侧实现）。
5. 后端地址写死、不可配置，导致换真机/模拟器时无法切换。

---

## 七、收口检查（整合前最后确认）

- [ ] 后端 `pytest`（三个测试文件）全绿
- [ ] Android 工程能编译通过
- [ ] 端到端流程在真机热点下走通
- [ ] 本单所有 ☐ 已勾选
