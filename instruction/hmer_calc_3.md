# 模块 3 指导文档：整合 + 前端 + 真机测试（C6 / C8 + 联调）

> 项目：HMER-Calc（手写公式识别 + 计算）
> 责任人：成员 3
> 本文档为模块 3 的开发指导。全局约定以同目录 `HEAD.md` 为准。

---

## 0. 模块定位

整合模块 1（识别）、模块 2（计算），完成界面编排与真机测试。
**本模块不实现识别和计算逻辑，只通过 `common` 里的两个接口调用它们。**

---

## 1. 处理流程（箭头 = 数据流向，即 App 端到端流程）

```
启动 --> 主界面【拍照 / 选图】
   --> 拍照 (CameraX) / 选图 (Photo Picker) --> 显示原图
   --> 调用 Recognizer.recognize(bitmap) --> RecognitionResult
   --> 显示：原图 + LaTeX 文本(可编辑) + 渲染公式 + 置信度
   --> 用户：确认 / 手动修正 latex 字符串
   --> 调用 Calculator.calculate(latex, mode) --> CalculationResult
   --> 显示：渲染结果 + 数值结果
   --> 用户可回到修正，反复循环【C7 闭环】
   --> (E1) 可选：保存历史记录
```

**状态机（ViewModel 的 UiState）**：

```
IDLE ─拍照/选图─▶ IMAGE_LOADED ─recognize()─▶ RECOGNIZED
                                               │ 确认 / 编辑
                                               ▼
                                           (EDITING) ◀──┐
                                               │ 改 latex │ 重新计算 C7
                                               ▼          │
                                           COMPUTED ─────┘
```

---

## 2. 需要实现的功能

| 编号 | 功能 | 说明 |
|---|---|---|
| C1 | 拍照 / 选图入口 | CameraX + Photo Picker（与模块 1 协商谁调，接口只认 Bitmap） |
| C6-1 | LaTeX 渲染回显 | jlatexmath 渲染，供用户核对 |
| C6-2 | 计算结果显示 | 展示 `CalculationResult.value` / `valueLatex` |
| C7 | 手动修正 | 可编辑 LaTeX 文本框，改完重新计算 |
| C8-1 | 主界面 | 拍照/选图入口 |
| C8-2 | 识别结果界面 | 原图 + LaTeX + 渲染 + 置信度 + 修正框 + 结果 |
| — | 依赖注入 | 把 `OnnxRecognizer` / `Exp4jCalculator` 注入 ViewModel |
| — | 真机测试 | Vivo X90 真机验证全流程 |

---

## 3. 全局统一约定（必须遵守，以 HEAD.md 为准）

### 3.1 统一包名

`com.hmercalc`（建项目时定死，不得改）。

### 3.2 公共接口与数据结构（放 `common` 包，本模块只调用，不修改）

```kotlin
// common/Recognizer.kt —— 模块 1 实现，本模块调用
interface Recognizer {
    fun recognize(bitmap: Bitmap): RecognitionResult
}
```

```kotlin
// common/Calculator.kt —— 模块 2 实现，本模块调用
interface Calculator {
    fun calculate(latex: String, mode: AngleMode = AngleMode.DEGREE): CalculationResult
}
```

```kotlin
// common/ResultTypes.kt —— 本模块展示这些数据
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
```

### 3.3 本模块必须遵守的渲染 / 展示约定

- 识别结果 `latex` 以**可编辑文本框**呈现（C7 的一等公民），不是只读展示。
- `CalculationResult.status != SUCCESS` 时，显示 `message`，不让 App 崩溃。
- 计算结果按 `valueLatex`（若有）渲染，否则显示 `value` 数值。

---

## 4. 本模块实现要点

- **架构**：单 Activity + Jetpack Compose + MVVM。ViewModel 持有一个 `StateFlow<UiState>`，按状态机渲染。
- **依赖注入**：用 Hilt（或手动注入）把 `OnnxRecognizer`、`Exp4jCalculator` 注入；**UI 层不 new 具体实现，只依赖接口**（这是换 B2/B5 实现不改 UI 的关键）。
- **相机**：CameraX；**相册**：Photo Picker。先确认与模块 1 的职责边界（模块 1 只要 `recognize(bitmap)` 能吃 Bitmap 即可）。
- **渲染**：noties/jlatexmath-android 渲染 `latex` 与 `valueLatex`。
- **里程碑 M1**：先用模块 1 的 `StubRecognizer` + 模块 2 的 `Exp4jCalculator` 跑通端到端流程，不依赖真模型。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E1 历史记录 | `data/` 的 Room（`HistoryEntity`/`HistoryDao`）建表预留 | 建表即可，功能后续补 |
| E2 导出分享 | UI 加按钮；LaTeX 源码已在 `RecognitionResult.latex` | 否 |
| E3/E8 候选与高亮 | 读取 `Token.alternatives` / `confidence`+`range` 展示 | 否 |
| E4 框选区域 | 加裁剪交互，接口不变 | 否 |
| E9 界面优化 | theme / 多语言 / 夜间模式，放 `ui/theme` | 否 |
| B4 实时流式识别 | 加相机预览 + `recognizeFrame()` | 否 |
| B5 端云协同 | 依赖注入处换 `Remote*` 实现 | 否 |

---

## 6. 开发语言与版本要求

| 项 | 要求 |
|---|---|
| 语言 | Kotlin（全项目统一） |
| UI | Jetpack Compose（单 Activity） |
| 架构 | MVVM + Repository + `StateFlow` |
| 渲染 | noties/jlatexmath-android |
| 图像 | CameraX、Photo Picker、Coil |
| DI | Hilt（或手动注入起步） |
| 持久化 | Room（E1）+ DataStore（E6 设置） |

版本（推荐稳定值，三人保持一致）：

| 组件 | 推荐版本 |
|---|---|
| Android Studio | Koala 2024.1.1 或更新 |
| JDK | 17 |
| Gradle / AGP | 8.7+ / 8.5+ |
| Kotlin | 2.0.x |
| Compose BOM | 2024.06.00 或更新 |
| compileSdk / targetSdk / minSdk | 34 / 34 / 26 |
| CameraX | 1.3.4 |
| Coil | 2.6.0 |
| jlatexmath-android | 0.4.0 |
| Room | 2.6.1 |
| DataStore | 1.1.1 |
| Hilt | 2.51.1 |

---

## 7. 需要额外下载的内容

- **依赖**：上表列出的 Gradle 依赖。
- **真机**：Vivo X90（Android 13/14）用于真机测试；无真机时用 Android Studio 模拟器兜底。
- **无训练集**。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
└── app/src/main/java/com/hmercalc/
    ├── common/                        # 契约（只读，不修改）
    │   ├── Recognizer.kt
    │   ├── Calculator.kt
    │   ├── ResultTypes.kt
    │   └── LatexVocab.kt
    ├── data/                          # 本模块负责（E1/E6 预留）
    │   ├── HistoryEntity.kt           # Room 表
    │   ├── HistoryDao.kt
    │   └── SettingsStore.kt           # DataStore（角度制等设置）
    └── ui/                            # 本模块实现
        ├── MainActivity.kt
        ├── HmerCalcApp.kt             # Application，装配依赖
        ├── CalcViewModel.kt           # UiState 状态机
        ├── screens/
        │   ├── CaptureScreen.kt       # 拍照/选图 + 显示原图
        │   └── ResultScreen.kt        # LaTeX 可编辑 + 渲染 + 结果
        └── theme/
```

---

## 9. 交付物与验收要点

1. 端到端流程可走通：选图 → 识别 → 显示 → 修正 → 计算 → 结果。
2. UI 只依赖 `common` 接口，不依赖 `OnnxRecognizer`/`Exp4jCalculator` 具体类。
3. 识别结果以可编辑文本框呈现，修正后能重新计算（C7 闭环）。
4. 计算结果与错误信息（`message`）都能正常展示，不崩溃。
5. LaTeX 公式用 jlatexmath 正常渲染。
6. Vivo X90 真机全流程测试通过（或模拟器兜底）。
7. 对照 `HEAD.md` 中"联调验收清单"逐项自查。
