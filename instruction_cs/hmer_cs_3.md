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
   --> 拍照 (系统相机 + FileProvider①) / 选图 (Photo Picker) --> 显示原图
   --> 压缩 + Base64 --> RemoteRecognizer.recognize() --> POST /recognize
   --> 识别成功 --> 自动先算一次 RemoteCalculator.calculate() --> POST /calculate {latex, mode="auto（默认）"}
   --> 结果页：原图缩略 + 渲染公式 + LaTeX 源码（只读） + 数值结果（用户先判断对错）
   --> 用户判定：✅ 结果正确 --> 完成本次任务（重置回初始）
               ✗ 需要修正 --> 修正页（实时渲染预览 + LaTeX 编辑 + 分类符号面板）
                              --> 手动【重新计算】反复调整【C7 闭环】
                              --> 【完成修正】保留改动回结果页 /【退出修正】放弃改动回结果页
   --> (E1) 已实现：识别+初算完成后自动保存进「历史记录」（最近 10 次，含图片/LaTeX/结果）

> ① 组长订正 2026-10：C1 现状先用「系统相机 + FileProvider」兜底；CameraX 内嵌取景列入后续。
>
> ⚠️ **拍照权限铁律（组长订正 2026-10-06）**：本方式走 `ACTION_IMAGE_CAPTURE`，相机权限归**系统相机 App** 持有，故本 App 的 Manifest **绝不能声明 `android.permission.CAMERA`**。声明了却未申请运行时授权时，系统会以 `Permission Denial: ... with revoked permission android.permission.CAMERA` 抛 `SecurityException` 拒绝启动相机，未捕获即**闪退回桌面**（Pixel_7 AVD 实测连崩 3 次，栈顶为 `CaptureScreen.kt` 的 `cameraLauncher.launch(uri)`）。另注：模拟器 AVD 可配虚拟摄像头（`hw.camera.back=virtualscene`），并非「无摄像头」。
```

**状态机（ViewModel 的 UiState，组长订正 2026-10）**：

```
IDLE ─拍照/选图─▶ IMAGE_LOADED ─识别成功(自动初算)─▶ RESULT（结果视图，用户判定对/错）
IDLE ◀─【结果正确】(完成本次任务)──────────────────────┘
IMAGE_LOADED ─识别失败─▶ ERROR（可【重试识别】）
RESULT ─【需要修正】─▶ correcting 子态（修正视图）─【完成修正】/【退出修正】─▶ RESULT
correcting 子态内：【重新计算】原地刷新「最近一次计算」，不退出
```

---

## 2. 需要实现的功能

| 编号 | 功能 | 说明 |
|---|---|---|
| C1 | 拍照 / 选图入口 | Photo Picker；拍照先用系统相机 + FileProvider（组长订正 2026-10，CameraX 内嵌取景列入后续） |
| C6-1 | LaTeX 渲染回显 | jlatexmath 渲染供核对；修正页实时预览带 250ms 防抖 + 半成品公式渲染兜底（组长订正 2026-10）；结果页渲染公式下方并列只读 LaTeX 源码（2026-10 按用户需求新增） |
| C6-2 | 计算结果显示 | 识别后**自动先算一次**并展示 `value` / `valueLatex`，供用户判定（组长订正 2026-10） |
| C6-3 | 角度模式三态 | 自动（默认）/ 角度° / 弧度；结果页切换即自动重算（组长订正 2026-10，替代原强制二选一） |
| C7 | 手动修正 | 阶段一（已落实 2026-10）：实时渲染预览 + 分类符号面板（光标处插入 / 包裹选中文本 / 插入内容变色高亮）+ 显式【重新计算 / 完成修正 / 退出修正】；阶段二（待启动）：在渲染公式上直接点选符号替换（WYSIWYG，先做 spike） |
| C8 | 主界面 + 结果界面 | 完整操作闭环（识别 → 自动初算 → 判定 →（必要时）修正 → 结果） |
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
- **组长订正 2026-10-06（UI 编辑已恢复）**：选图页底部提供「**后端地址**」输入框 + 「保存地址」按钮 + 浅灰小字提示（`当前生效：xxx` + 模拟器默认说明）。初值自动填入当前地址；手输省略 `http://` 时**自动补全**（漏 scheme 会被拦截器判为无效而**静默回退**，不易排查）。保存即写入 `data/SettingsStore`，经 `CalcViewModel` 订阅链同步到 `DynamicBaseUrlInterceptor` **立即生效**，无需重启 App、无需重新打包。识别中禁用输入。
  - 沿革：2026-10 模拟器阶段曾简化为「UI 只读展示、不提供输入」，切换能力保留在 SettingsStore + 拦截器；2026-10-06 恢复 UI 编辑（ALL.md M3-9 达成、红牌项 5 解除）。

### 3.2 JSON 契约（本模块的 DTO，与后端 pydantic 字段一一对应）

```kotlin
// android/.../common/Dto.kt —— 用 kotlinx.serialization，字段映射 snake_case
@Serializable
data class RecognRequest(val image: String)   // JPEG 字节的 base64，无 data URL 前缀

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
    val status: String = "SUCCESS",          // "SUCCESS" | "ERROR"（识别失败）
    val message: String? = null,
)

@Serializable
data class CalculateRequest(val latex: String, val mode: String = "auto")   // 组长订正 2026-10：默认 auto

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
    fun calculate(latex: String, mode: String): CalculateResponse   // mode ∈ "deg" | "rad" | "auto"（组长订正 2026-10）
}
```

### 3.4 展示约定

- 识别成功后**自动先算一次**，先给计算值让用户判定「对 / 错」；仅当判错才进修正（组长订正 2026-10）。
- 结果页在渲染公式下方**并列只读展示 LaTeX 源码**（等宽字体 + 细边框，2026-10 按用户需求新增）：二者一一对应，供核对识别结果；需要改动仍走【需要修正】页的编辑框，本页不提供编辑。
- 修正页提供 LaTeX 的**实时渲染预览**（防抖 + 失败兜底）；操作以「可读公式 + 分类符号面板」为主、LaTeX 文本框为辅；完全点选替换（WYSIWYG）列阶段二（组长订正 2026-10）。符号面板「基础运算」含 `π` 与 `e`（自然常数，2026-10 按用户需求新增，后端 `vocab.py` 的 `E` 早已在册）；进入修正页时**光标默认落在公式末尾**（2026-10 按用户需求），直接点符号即追加，想插在别处可先点输入框定位。
- 修正的进入/完成/退出全部由**显式按钮**驱动，清空输入框不会自动退出修正（组长订正 2026-10）。
- 识别结果以**所见即所得公式**呈现（渲染 + 点选编辑，C7 的一等公民），不是只读 LaTeX 文本框。
- 识别 `status == "ERROR"` 或计算 `status != "SUCCESS"` 时显示 `message`，不让 App 崩溃。
- 数值结果区：以大字号显示 `value` 数值；当 `valueLatex`（精确形式，如 `\frac{5}{6}`）与数值文本不同时，在其下**额外渲染一行**——二者并列（近似值 + 精确形式）供对照，相同则不重复渲染。后端在无精确形式时返回 `null`（如 rad 模式下的 `\sin 30`），此时只显示数值（组长订正 2026-10-06；此前 `rad` 档会把**输入式**当精确值回显，多出一行）。

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
- **图像压缩与编码**：上传前压缩（如最长边 ≤ 1024、JPEG 质量 85）减小传输量；`image` = 该 JPEG 字节的 base64，**无 `data:image/...;base64,` 前缀**。
- **超时**：OkHttp read 超时调到 30s——首次 `/recognize` 要加载/下载模型（几秒到十几秒），默认 10s 会误判超时。
- **错误处理**：网络失败（连不上后端）要给出友好提示（如"请确认已连接电脑热点"），不崩溃；识别/计算失败靠 JSON 的 `status` 区分，非 200 也要容错。

### 4.1 C7 所见即所得编辑的三条稳定性保障

> 组长订正 2026-10：C7 分两阶段——**阶段一（已落实）**：实时渲染预览 + 分类符号面板插入 + 显式进出修正；**阶段二（待启动）**：在渲染公式上直接点选符号替换。下列 ① 的编辑器 spike 属阶段二前置；②③ 在阶段一已生效（渲染兜底、PARSE_ERROR 不崩）。

针对「渲染成公式 → 点选 → 增删改 → 回写 LaTeX → 重算」链路的三个已知风险，各一条落实手段：

**① 编辑器库是 experimental（风险：不成熟）**

- **前置 spike（必做）**：正式写 UI 前，先用 huarangmeng/latex 搭最小 demo，跑通「喂入 LaTeX → 渲染 → 点选改一个符号 → 回读 LaTeX」闭环，重点验 `\frac`/`\sqrt`/`\sin`/上下标能否渲染、能否 tap 定位、回读 LaTeX 是否合法。spike 不通过就不往下写。
- **锁版本**：pin 具体版本号（如 1.5.0），不追 latest，避免 API 漂移。
- **兜底**：保留「可编辑 LaTeX 文本框 + jlatexmath 只读渲染」作为 fallback。编辑器崩溃/渲染失败时退回文本框编辑，C7「可改 + 重算」底线仍在。

**② Pix2Text 输出的 LaTeX 非标准子集（风险：喂进编辑器报错）**

- 模块 1 已把多行结构（`\begin{matrix}`/`array`/`cases` 等）拦成 ERROR，不会进编辑态。
- 喂入编辑器前做一层**规范化**：`\cdot`→`\times`、`\left(`/`\right)`→`(`/`)`、`\mathrm{...}`→去壳等，只保留已知安全结构。
- 编辑器解析/渲染抛异常时捕获，回退到文本框显示原始 `latex`。

**③ 回写 LaTeX 必须能被 latex2sympy2 解析（风险：/calculate 报 PARSE_ERROR）**

- 模块 2 补「编辑器输出样例」测试（见 hmer_cs_2.md §9），把编辑器实际产出的典型形式直接喂 `/calculate` 断言 SUCCESS。
- 模块 3 侧把编辑器输出**规范化到 latex2sympy2 支持形式**再发（如 `\sin 30`→`\sin(30)`、`2^3`→`2^{3}`）。
- 兜底：`/calculate` 返回 `PARSE_ERROR` 时展示 message 让用户继续改（C7 闭环本意），不崩溃。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E1 历史记录 | 已实现（组长订正 2026-10-07）：`data/` 的 `HistoryStore`（DataStore 存 JSON 元数据 + `filesDir/history/` 存缩略图），最近 10 次，可回载/清空 | 已做 |
| E2 导出分享 | UI 加按钮；LaTeX 源码已在响应里 | 否 |
| E3/E8 候选与高亮 | E3 已并入 C7 点选修正；E8 降级为整体置信度分档（0.55~0.95 返回并提示、<0.55 拦截；后端已做，见 hmer_cs_1.md） | 否 |
| E4 框选区域 | 加裁剪交互，上传裁剪后图片 | 否 |
| E6 模式切换 | 已完成（组长订正 2026-10：升级为 自动/角度/弧度 三态，默认自动） | 已做 |
| E9 界面优化 | 已做（组长订正 2026-10-07）：高级感配色主题（深邃靛蓝 + 暖铜点缀 + 暖白底，关闭壁纸取色）+ 结果页/首页/历史页卡片化排版 | 已做 |
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
| 渲染（只读结果） | ru.noties:jlatexmath-android（组长订正：原写 `noties/jlatexmath-android` 是 GitHub 仓库路径，Maven 坐标组为 `ru.noties`） |
| 编辑（C7 所见即所得） | huarangmeng/latex（KMP，含 WYSIWYG 编辑器） |
| 图像 | CameraX、Photo Picker、Coil |
| DI | Hilt |
| 持久化 | DataStore（E1 历史记录 + E6 设置/后端地址） |

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
| jlatexmath-android | 0.2.0（组长订正：原写 0.4.0，Maven 中央仓库无此版本，实际最新为 0.2.0） |
| huarangmeng/latex | 1.5.0（或与 Kotlin 版本匹配的变体，以实际发布为准） |
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
    ├── data/                            # E1/E6
    │   ├── HistoryEntry.kt              # 历史记录一条（@Serializable）
    │   ├── HistoryStore.kt              # 历史持久化（DataStore JSON + filesDir 缩略图）
    │   └── SettingsStore.kt             # 后端地址、deg/rad 设置
    └── ui/
        ├── MainActivity.kt
        ├── HmerCalcApp.kt               # Application，Hilt 装配
        ├── CalcViewModel.kt             # UiState 状态机
        ├── screens/
        │   ├── CaptureScreen.kt
        │   ├── ResultScreen.kt
        │   └── HistoryScreen.kt         # 历史记录列表页（组长订正 2026-10-07 新增）
        └── theme/
```

---

## 9. 测试方式（联合测试）

- **单模块联调（1+3 或 2+3）**：后端起一半（只挂一个 router）也能测——`RemoteRecognizer` 只依赖 `/recognize`，`RemoteCalculator` 只依赖 `/calculate`，互不耦合。
- **端到端（1+2+3）**：后端全起 + 客户端走完整流程。模拟器用 `10.0.2.2:8000`，真机热点用电脑 IP。

---

## 10. 交付物与验收要点

1. 端到端流程可走通：选图 → 识别 → 自动初算 → 用户判定 →（必要时修正重算）→ 结果。
2. UI 只依赖 `common` 接口，不依赖 `RemoteRecognizer`/`RemoteCalculator` 具体类（可注入替换）。
3. 识别后自动初算供判定；判错可进修正（实时渲染 + 符号面板编辑），修正后能重新计算（C7 闭环，组长订正 2026-10）。
4. 结果与错误信息都能正常展示，网络失败不崩溃。
5. LaTeX 公式用 jlatexmath 正常渲染。
6. 模拟器 + 真机（热点）各验证一次全流程。
7. 对照 `ALL.md`「模块 3 查验对照单」与「联合测试验收清单」逐项自查。
