# 模块 2 指导文档：LaTeX 解析 + 计算 + 手动修正（C4 / C5 / C6 / C7）

> 项目：HMER-Calc（手写公式识别 + 计算）
> 责任人：成员 2
> 本文档为模块 2 的开发指导。全局约定以同目录 `HEAD.md` 为准。

---

## 0. 模块定位

接收模块 1 输出的 LaTeX 字符串，解析成语法树并计算数值结果；同时支持用户手动修正后重新解析计算。
**关键提醒：计算必须用 Kotlin/exp4j 在端侧完成，不能用 Python/sympy/latex2sympy（Android 本地跑不了 Python）。**

---

## 1. 处理流程（箭头 = 数据流向）

```
接收 latex 字符串 + AngleMode
   --> 【C4 解析】LatexLexer 词法分析 --> token 流
   --> LatexParser 递归下降 --> AST 语法树
   --> 【C5 计算】ExprTranslator：AST --> exp4j 表达式字符串
   --> exp4j 求值
        ├─ 成功 --> CalculationResult(SUCCESS, value, valueLatex)
        └─ 失败 --> 分类 PARSE_ERROR / COMPUTE_ERROR，携带 message（除零、非法结构等）
   --> 返回给 UI 层（模块 3）

【C7 手动修正闭环】用户编辑 latex 字符串后，UI 再次调用 calculate()，重复上面流程
```

**AST 示例**：`\frac{1}{2}+\sqrt{9}` → `Add( Frac(1,2) , Sqrt(9) )` → `"(1)/(2) + sqrt(9)"` → exp4j 求值得 `3.5`。

---

## 2. 需要实现的功能

| 编号 | 功能 | 说明 |
|---|---|---|
| C4-1 | 词法分析 | 把 LaTeX 字符串切分成 token（命令 `\frac` `\sqrt` `\sin`…、花括号 `{ }`、符号 `^ + - \times \div ( )`、数字、字母） |
| C4-2 | 语法树构建 | 递归下降解析，构建表达式语法树（AST） |
| C5-1 | 四则运算 | + − × ÷ |
| C5-2 | 幂运算 | `a^{b}` → `pow(a,b)` |
| C5-3 | 根号运算 | `\sqrt{a}` → `sqrt(a)` |
| C5-4 | 基础三角函数 | `\sin/\cos/\tan` → `sin/cos/tan`，注意角度制/弧度制 |
| C5-5 | 输出数值结果 | 返回 `Double` |
| C6 | 结果数据封装 | 返回可回显的 LaTeX + 数值 + 状态 |
| C7 | 手动修正支持 | 接受用户改过的 LaTeX 字符串重新解析计算 |

---

## 3. 全局统一约定（必须遵守，以 HEAD.md 为准）

### 3.1 统一包名

`com.hmercalc`（建项目时定死，不得改）。

### 3.2 公共接口与数据结构（放 `common` 包，本模块负责提供 `Calculator` 的实现）

```kotlin
// common/Calculator.kt —— 本模块实现它
interface Calculator {
    fun calculate(latex: String, mode: AngleMode = AngleMode.DEGREE): CalculationResult
}
```

```kotlin
// common/ResultTypes.kt —— 与模块 1/3 共用
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
    val latex: String,          // 规范化回显的 LaTeX（供渲染核对）
    val value: Double?,         // 数值结果（SUCCESS 时非空）
    val valueLatex: String?,    // 结果的 LaTeX，如 "1.414213..."
    val status: Status,
    val message: String? = null,
)
```

```kotlin
// common/Recognizer.kt —— 模块 1 实现，本模块仅知晓其输出 latex 的格式
interface Recognizer {
    fun recognize(bitmap: Bitmap): RecognitionResult
}
```

### 3.3 LaTeX 词表（本模块必须能逐字解析这些输入）

```kotlin
// common/LatexVocab.kt —— 本模块解析器支持的 token 集合必须覆盖它
object LatexVocab {
    const val PLUS = "+"
    const val MINUS = "-"
    const val TIMES = "\\times"     // 兼容 \cdot
    const val DIV = "\\div"
    const val FRAC = "\\frac"       // 一律 \frac{分子}{分母}
    const val SQRT = "\\sqrt"       // 一律 \sqrt{被开方数}
    const val POW = "^"             // a^{b}；单字符 a^b 也兼容
    val TRIG = setOf("\\sin", "\\cos", "\\tan")
    const val PI = "\\pi"
    const val E = "e"
    const val DIGITS = "0123456789"
    const val PARENS = "()"
}
```

### 3.4 LaTeX → 表达式映射表（本模块解析器必须严格按此翻译）

| 数学含义 | M1 输出 LaTeX | 本模块解析为 |
|---|---|---|
| 加 / 减 | `+` / `-` | `+` / `-` |
| 乘 | `\times`（兼容 `\cdot`） | `*` |
| 除 | `\div` | `/` |
| 分数 | `\frac{1}{2}` | `(1)/(2)` |
| 幂 | `2^{3}` | `pow(2,3)` |
| 根号 | `\sqrt{9}` | `sqrt(9)` |
| 三角 | `\sin(30)` | `sin(30)` |
| π / e | `\pi` / `e` | `pi` / `e` |
| 括号 | `(` `)` | `(` `)` |
| 小数 | `3.14` | `3.14` |

### 3.5 两条铁律

1. 结构一律按带花括号的规范形式解析（`\frac{...}{...}`、`\sqrt{...}`、`a^{...}`）。
2. 改词表 / 映射，必须同步通知模块 1，双方同步改、同步测。

---

## 4. 本模块对外接口实现要点

- 实现类名建议 `Exp4jCalculator`，实现 `common.Calculator`。
- 内部三层：`LatexLexer`（词法）→ `LatexParser`（递归下降 → AST）→ `ExprTranslator`（AST → exp4j 字符串）→ exp4j 求值。
- **错误处理是重点**：所有异常都要转成 `CalculationResult`（`PARSE_ERROR` / `COMPUTE_ERROR` + message），**绝不能向上抛异常让 App 崩溃**。至少覆盖：非法/未知命令、括号不匹配、除零、空输入。
- 三角函数默认 `AngleMode.DEGREE`（角度制），`RADIAN` 作为 E6 预留；exp4j 的 `sin/cos/tan` 本身是弧度制，DEGREE 时需做 `x * PI / 180` 换算。
- `valueLatex` 用于模块 3 渲染结果；初期可简单格式化为数字字符串。
- **M1 里程碑**：先交付 `Exp4jCalculator`（真实现，因解析器工作量小），与模块 1 的 stub 联调。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E6 常量/模式切换 | `AngleMode` 已定义，`\pi`/`e` 已在词表 | 解析层顺手支持 |
| E7 结果格式化 | `valueLatex` 可扩展精度/分数显示 | 否 |
| B3 数据回流 | 解析器天然接受"修正后的 latex"，修正结果由模块 3 存 `data/` | 否 |
| B5 端云协同 | `RemoteCalculator` 接口形状预留，不实现 | 否 |

---

## 6. 开发语言与版本要求

| 项 | 要求 |
|---|---|
| 语言 | Kotlin（全项目统一） |
| 求值引擎 | exp4j（`net.objecthunter:exp4j:0.4.8`） |
| LaTeX 解析 | 自写（JVM 无现成 LaTeX→表达式库） |

版本（推荐稳定值，三人保持一致）：

| 组件 | 推荐版本 |
|---|---|
| JDK | 17 |
| Kotlin | 2.0.x |
| minSdk | 26 |
| exp4j | 0.4.8 |

---

## 7. 需要额外下载的内容

- **依赖**：exp4j（Gradle 依赖，见上表）。
- **无需训练集**（本模块不涉及训练）。
- 建议本地写一份**单元测试**覆盖词表里每种运算（分数、幂、根号、三角、除零、括号不匹配），用于自验与联调。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
└── app/src/main/java/com/hmercalc/
    ├── common/                            # 契约（实现以下接口，不拥有 common）
    │   ├── Calculator.kt
    │   ├── ResultTypes.kt
    │   └── LatexVocab.kt
    └── calculation/                       # 本模块实现
        ├── Exp4jCalculator.kt             # 实现 common.Calculator
        ├── latex2expr/
        │   ├── LatexLexer.kt              # 词法分析
        │   ├── LatexParser.kt             # 递归下降 → AST
        │   └── Ast.kt                     # 语法树节点定义
        └── evaluate/
            └── ExprTranslator.kt          # AST → exp4j 字符串
```

---

## 9. 交付物与验收要点

1. `Exp4jCalculator` 实现 `calculate(latex, mode)`，返回合法 `CalculationResult`。
2. 能正确解析 `LatexVocab` 覆盖的所有合法输入（对照映射表逐条测试）。
3. 任何非法输入返回 `PARSE_ERROR` / `COMPUTE_ERROR`，不崩溃。
4. 角度制/弧度制切换生效（DEGREE 默认）。
5. 手动修正后重新计算可走通（与模块 3 联调 C7 闭环）。
6. 对照 `HEAD.md` 中"模块 2 查验对照单"逐项自查。
