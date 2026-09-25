# 模块 3 指导文档：Android 客户端（C/S 版，C1 / C6 / C7 / C8 + 整合调用 1、2）

> 项目：HMER-Calc（C/S 架构）
> 责任人：成员 3
> 架构：本模块是 Android 客户端，负责拍照/选图、展示、修正，通过 HTTP 调用模块 1（识别）与模块 2（计算）。
> 全局约定以同目录 `ALL.md` 为准。旧方案 `hmer_calc_3.md` 为日后端侧对比的余量参考，不在本次落实范围。

---

## 0. 模块定位

**本模块不实现识别和计算逻辑**，只通过 `common` 里的两个接口调用它们；两个接口的 `Remote` 实现走 HTTP 到后端。
**关键：保留 `Recognizer`/`Calculator` 接口抽象**，日后想对比端侧方案时补 `Local*` 实现即可，UI 一行不改。

---

## 1. 处理流程（箭头 = 数据流向，即端到端流程）

```
启动 --> 主界面【拍照 / 选图】
   --> 拍照 (CameraX) / 选图 (Photo Picker) --> 显示原图
   --> 压缩 + Base64 --> RemoteRecognizer.recognize() --> POST /recognize
   --> 收到 RecognitionResponse --> 显示：原图 + LaTeX(可编辑) + 渲染 + 置信度
   --> 用户：确认 / 手动修正 latex
   --> RemoteCalculator.calculate() --> POST /calculate {latex, mode}
   --> 收到 CalculateResponse --> 显示：渲染结果 + 数值结果
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
| C1 | 拍照 / 选图入口 | CameraX + Photo Picker |
| C6-1 | LaTeX 渲染回显 | jlatexmath 渲染，供核对 |
| C6-2 | 计算结果显示 | 展示 `CalculateResponse.value` / `valueLatex` |
| C7 | 手动修正 | 可编辑 LaTeX 文本框，改完重新计算 |
| C8 | 主界面 + 结果界面 | 完整操作闭环 |
| — | 网络层 | Retrofit 封装 `RemoteRecognizer` / `RemoteCalculator` |
| — | 依赖注入 | Hilt 注入接口，UI 不依赖具体实现 |

---

## 3. 全局统一约定（必须遵守，以 ALL.md 为准）

### 3.1 服务地址约定（本模块重点）

- 后端地址可配置（建议放 `data/SettingsStore`，默认值见下），三种连接方式：
  1. **模拟器**：`http://10.0.2.2:8000`（模拟器访问宿主机 localhost 的固定地址）
  2. **真机 USB**：`adb reverse tcp:8000 tcp:8000`，然后 App 用 `http://localhost:8000`
  3. **真机热点**（主用）：手机开热点，电脑连上，App 用电脑局域网 IP，如 `http://192.168.43.100:8000`
- **明文 HTTP 配置**：本地是 http 明文，Manifest 需开启 `android:usesCleartextTraffic="true"`（或 network security config 仅放行该 IP）。

### 3.2 JSON 契约（本模块的 DTO，与后端 pydantic 字段一一对应）

```kotlin
// android/.../common/Dto.kt —— 用 kotlinx.serialization，字段映射 snake_case
@Serializable
data class Token(
    val text: String,
    val confidence: Double,
    @SerialName("range_start") val rangeStart: Int,
    @SerialName("range_end") val rangeEnd: Int,
    val alternatives: List<String> = emptyList(),
)

@Serializable
data class RecognitionResponse(
    val latex: String,
    val confidence: Double,
    val tokens: List<Token> = emptyList(),
)

@Serializable
data class CalculateRequest(val latex: String, val mode: String = "deg")

@Serializable
data class CalculateResponse(
    val latex: String,
    val value: Double? = null,
    @SerialName("value_latex") val valueLatex: String? = null,
    val status: String,                       // "SUCCESS"|"PARSE_ERROR"|"COMPUTE_ERROR"
    val message: String? = null,
)
```

**JSON 字段命名铁律**：JSON 一律 **snake_case**，Kotlin 用 `@SerialName` 映射。

### 3.3 接口抽象（本模块保留，供日后端侧对比）

```kotlin
// common/Recognizer.kt —— 现在实现 RemoteRecognizer，日后可补 LocalRecognizer
interface Recognizer {
    fun recognize(bitmap: Bitmap): RecognitionResponse
}

// common/Calculator.kt —— 现在实现 RemoteCalculator，日后可补 LocalCalculator
interface Calculator {
    fun calculate(latex: String, mode: String = "deg"): CalculateResponse
}
```

### 3.4 展示约定

- 识别结果 `latex` 以**可编辑文本框**呈现（C7 的一等公民），不是只读展示。
- `status != "SUCCESS"` 时显示 `message`，不让 App 崩溃。
- 结果优先渲染 `valueLatex`（若有），否则显示 `value` 数值。

---

## 4. 本模块实现要点

- **架构**：单 Activity + Jetpack Compose + MVVM。ViewModel 持有一个 `StateFlow<UiState>`，按状态机渲染。
- **网络**：Retrofit + kotlinx.serialization。`CalcApi` 定义两个端点：
  ```kotlin
  interface CalcApi {
      @POST("recognize")  suspend fun recognize(@Body body: RecognRequest): RecognitionResponse
      @POST("calculate")  suspend fun calculate(@Body body: CalculateRequest): CalculateResponse
  }
  ```
- **依赖注入**：用 Hilt 把 `RemoteRecognizer`/`RemoteCalculator` 注入 ViewModel；**UI 层只依赖接口**。
- **图像压缩**：上传前压缩（如最长边 ≤ 1024、JPEG 质量 85），减小传输量。
- **错误处理**：网络失败（连不上后端）要给出友好提示（如"请确认已连接电脑热点"），不崩溃。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E1 历史记录 | `data/` 的 Room（`HistoryEntity`/`HistoryDao`）建表预留 | 建表即可 |
| E2 导出分享 | UI 加按钮；LaTeX 源码已在响应里 | 否 |
| E3/E8 候选与高亮 | 读取 `tokens[].alternatives` / `confidence`+`range` 展示 | 否 |
| E4 框选区域 | 加裁剪交互，上传裁剪后图片 | 否 |
| E6 模式切换 | UI 加 deg/rad 切换，传入 `mode` | 可选 |
| E9 界面优化 | theme / 多语言 / 夜间模式 | 否 |
| B1 端侧部署 | 补 `LocalRecognizer`/`LocalCalculator` 实现 | 否（余量） |
| B4 实时流式识别 | 加相机预览 + 连续调 `/recognize` | 否 |
| B5 端云协同 | 依赖注入处切换 Local/Remote 实现 | 否 |

---

## 6. 开发语言与版本要求

| 项 | 要求 |
|---|---|
| 语言 | Kotlin（全项目统一） |
| UI | Jetpack Compose（单 Activity） |
| 架构 | MVVM + Repository + `StateFlow` |
| 网络 | Retrofit + OkHttp + kotlinx.serialization |
| 渲染 | noties/jlatexmath-android |
| 图像 | CameraX、Photo Picker、Coil |
| DI | Hilt |
| 持久化 | Room（E1）+ DataStore（E6 设置/后端地址） |

| 组件 | 推荐版本 |
|---|---|
| Android Studio | Koala 2024.1.1 或更新 |
| JDK | 17 |
| Gradle / AGP | 8.7+ / 8.5+ |
| Kotlin | 2.0.x |
| Compose BOM | 2024.06.00 或更新 |
| compileSdk / targetSdk / minSdk | 34 / 34 / 26 |
| Retrofit / OkHttp | 2.11.0 / 4.12.0 |
| kotlinx.serialization | 1.7.x |
| jlatexmath-android | 0.4.0 |
| CameraX / Coil | 1.3.4 / 2.6.0 |
| Room / DataStore | 2.6.1 / 1.1.1 |
| Hilt | 2.51.1 |

---

## 7. 需要额外下载的内容

- **依赖**：上表列出的 Gradle 依赖。
- **真机**：Vivo X90（Android 13/14）用于真机测试；无真机时用 Android Studio 模拟器（`10.0.2.2` 访问后端）。
- **无需训练集**。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
└── android/app/src/main/java/com/hmercalc/
    ├── common/                          # 契约（DTO + 接口 + 词表）
    │   ├── Dto.kt                       # JSON DTO
    │   ├── Recognizer.kt                # 接口
    │   ├── Calculator.kt                # 接口
    │   └── LatexVocab.kt                # 词表（与后端 vocab.py 一致）
    ├── remote/                          # 网络层（本模块实现）
    │   ├── CalcApi.kt                   # Retrofit 接口
    │   ├── RemoteRecognizer.kt          # 实现 common.Recognizer
    │   └── RemoteCalculator.kt          # 实现 common.Calculator
    ├── data/                            # E1/E6 预留
    │   ├── HistoryEntity.kt / HistoryDao.kt
    │   └── SettingsStore.kt             # 后端地址、deg/rad 设置
    └── ui/
        ├── MainActivity.kt
        ├── HmerCalcApp.kt               # Application，Hilt 装配
        ├── CalcViewModel.kt             # UiState 状态机
        ├── screens/
        │   ├── CaptureScreen.kt
        │   └── ResultScreen.kt
        └── theme/
```

---

## 9. 测试方式（联合测试）

- **单模块联调（1+3 或 2+3）**：后端起一半（只挂一个 router）也能测——`RemoteRecognizer` 只依赖 `/recognize`，`RemoteCalculator` 只依赖 `/calculate`，互不耦合。
- **端到端（1+2+3）**：后端全起 + 客户端走完整流程。模拟器用 `10.0.2.2:8000`，真机热点用电脑 IP。

---

## 10. 交付物与验收要点

1. 端到端流程可走通：选图 → 识别 → 显示 → 修正 → 计算 → 结果。
2. UI 只依赖 `common` 接口，不依赖 `RemoteRecognizer`/`RemoteCalculator` 具体类（可注入替换）。
3. 识别结果以可编辑文本框呈现，修正后能重新计算（C7 闭环）。
4. 结果与错误信息都能正常展示，网络失败不崩溃。
5. LaTeX 公式用 jlatexmath 正常渲染。
6. 模拟器 + 真机（热点）各验证一次全流程。
7. 对照 `ALL.md`「模块 3 查验对照单」与「联合测试验收清单」逐项自查。
