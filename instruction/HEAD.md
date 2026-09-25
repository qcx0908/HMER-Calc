# HEAD.md —— 组长查验对照单

> 用途：组长在收集、整合模块 1 / 2 交付物时，对照本单查验它们是否满足模块 3 的集成要求。
> 维护：组长。全局契约以本文件为准，模块文档 `hmer_calc_1/2/3.md` 与之冲突时以本文件为准。

---

## 一、全局契约核对（先验这个，任何一项不符都要退回）

- [ ] 统一包名 `com.hmercalc`，三份代码一致
- [ ] `common` 包下四个文件齐全且三人版本一致：
  - [ ] `Recognizer.kt`（接口签名与本文档一致）
  - [ ] `Calculator.kt`（接口签名与本文档一致）
  - [ ] `ResultTypes.kt`（`RecognitionResult` / `Token` / `CalculationResult` / `AngleMode` / `Status` 字段一致）
  - [ ] `LatexVocab.kt`（词表一致）
- [ ] LaTeX 映射表双方遵守（`\frac/\sqrt/^{}/\times/\div/\sin/\cos/\tan/\pi/e` + 数字 + 括号）
- [ ] 两条铁律双方遵守：结构带花括号规范形式；改词表/映射同步通知

### 契约基准（金标准，查验时对照）

```kotlin
interface Recognizer {
    fun recognize(bitmap: Bitmap): RecognitionResult
}

interface Calculator {
    fun calculate(latex: String, mode: AngleMode = AngleMode.DEGREE): CalculationResult
}

enum class AngleMode { DEGREE, RADIAN }
enum class Status { SUCCESS, PARSE_ERROR, COMPUTE_ERROR }

data class RecognitionResult(
    val latex: String,
    val confidence: Double,
    val tokens: List<Token> = emptyList(),
)

data class Token(
    val text: String,
    val confidence: Double,
    val range: IntRange,
    val alternatives: List<String> = emptyList(),
)

data class CalculationResult(
    val latex: String,
    val value: Double?,
    val valueLatex: String?,
    val status: Status,
    val message: String? = null,
)

object LatexVocab {
    const val PLUS = "+"
    const val MINUS = "-"
    const val TIMES = "\\times"
    const val DIV = "\\div"
    const val FRAC = "\\frac"
    const val SQRT = "\\sqrt"
    const val POW = "^"
    val TRIG = setOf("\\sin", "\\cos", "\\tan")
    const val PI = "\\pi"
    const val E = "e"
    const val DIGITS = "0123456789"
    const val PARENS = "()"
}
```

---

## 二、模块 1 查验对照单（M1 → 是否满足 M3）

| # | 查验项 | 怎么验 | 结果 |
|---|---|---|---|
| M1-1 | `recognize(bitmap)` 可调用 | M3 能拿到 `RecognitionResult` | ☐ |
| M1-2 | 返回 `latex` 合法 | 逐字符合 `LatexVocab`，无 `\over` 等变体 | ☐ |
| M1-3 | `confidence` ∈ [0,1] | 抽查若干样本 | ☐ |
| M1-4 | 模型能加载 | `assets/model.onnx` 存在，ONNX Runtime 加载成功 | ☐ |
| M1-5 | 真机推理不崩 | Vivo X90 / 模拟器运行不崩溃 | ☐ |
| M1-6 | 预处理输入尺寸与模型一致 | 缩放/归一化后的张量尺寸 = 模型输入 | ☐ |
| M1-7 | 里程碑 stub 可用 | `StubRecognizer` 返回写死合法 LaTeX | ☐ |
| M1-8 | 耗时可接受 | 单次识别耗时记录（首次冷启动另计） | ☐ |
| M1-9 | 不依赖模块 2/3 | 单独可编译、可跑（只依赖 common） | ☐ |
| M1-10 | 预留字段未删 | `Token.alternatives` / `range` / `confidence` 保留 | ☐ |

---

## 三、模块 2 查验对照单（M2 → 是否满足 M3）

| # | 查验项 | 怎么验 | 结果 |
|---|---|---|---|
| M2-1 | `calculate(latex, mode)` 可调用 | M3 能拿到 `CalculationResult` | ☐ |
| M2-2 | 四则正确 | `1+2*3` 等手工比对 | ☐ |
| M2-3 | 分数正确 | `\frac{1}{2}` → 0.5 | ☐ |
| M2-4 | 幂正确 | `2^{3}` → 8 | ☐ |
| M2-5 | 根号正确 | `\sqrt{9}` → 3 | ☐ |
| M2-6 | 三角正确 | `\sin(30)`（DEGREE）→ 0.5 | ☐ |
| M2-7 | 角度/弧度切换 | `RADIAN` 下 `\sin(\pi)` 结果正确 | ☐ |
| M2-8 | 非法输入不崩 | 除零、括号不匹配、未知命令 → 返回错误状态 + message | ☐ |
| M2-9 | SUCCESS 时字段完整 | `value` 非空、`valueLatex` 可渲染 | ☐ |
| M2-10 | 修正后重算 | 同一实例多次 `calculate` 结果正确 | ☐ |
| M2-11 | 不依赖模块 1/3 | 单独可编译、可跑（只依赖 common） | ☐ |

---

## 四、联调验收清单（端到端，组长主导）

- [ ] 选图 → 识别 → 显示原图 + LaTeX + 渲染 + 置信度
- [ ] 编辑 LaTeX → 重新计算 → 结果刷新（C7 闭环）
- [ ] 核心样例逐个通过（至少含：分数、幂、根号、三角函数各一例）
- [ ] 错误场景不崩：空输入、除零、非法 LaTeX
- [ ] 真机（Vivo X90）或模拟器全流程通过
- [ ] UI 只依赖 `common` 接口，不依赖具体实现类（可注入替换）

---

## 五、红牌项（出现即退回，不能进入整合）

1. 包名不一致，或 `common` 契约文件被成员私自改动。
2. 模块 2 用了 Python/sympy 等 Android 无法本地运行的方案。
3. 识别输出 `latex` 超出 `LatexVocab` 词表（含 `\over`、`\left`、`\right` 等未约定 token）。
4. 任何模块把异常抛到上层导致 App 崩溃（识别或计算失败必须返回结果对象，不能 crash）。
5. 模块 1 交付物停留在"Python 脚本能识别"，没有 ONNX 模型 + Android 可调用实现。

---

## 六、收口检查（整合前最后确认）

- [ ] 三份代码在同一 Android 工程内，能一次性编译通过
- [ ] `common` 接口 + 两个实现 + UI 能完整跑通流程
- [ ] `HEAD.md` 本单所有 ☐ 已勾选
