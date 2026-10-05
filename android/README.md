# HMER-Calc Android 客户端（模块三）

手写公式 → LaTeX → 数值结果 的 Android 端。C/S 架构，客户端只负责：拍照/选图 → 调后端识别 → 编辑/确认 LaTeX → 调后端计算 → 展示结果。

## 技术栈

- Kotlin 2.0 + Jetpack Compose (Material3) + MVVM
- 依赖注入：Hilt（KSP）
- 网络：Retrofit + OkHttp + kotlinx.serialization（JSON，snake_case 与后端对齐）
- 图片：系统相机（FileProvider）+ 相册选择器（Photo Picker）
- 设置持久化：DataStore Preferences（后端地址）
- LaTeX 渲染：jlatexmath-android

## 环境要求

| 项 | 版本 |
|---|---|
| Android Studio | 任意较新版本（Ladybug / Koala 即可） |
| JDK | 17 |
| Gradle | 8.7（Android Studio 首次打开会自动下载） |
| AGP | 8.5.2 |
| Kotlin | 2.0.21 |
| compileSdk / targetSdk | 34 |
| minSdk | 26（Android 8.0） |

## 打开与运行

1. 用 Android Studio 打开 **本目录 `android/`**（不是仓库根目录）。
2. 首次 sync 会自动下载 Gradle 8.7 与依赖（需要联网，几分钟）。
   - 本骨架未内置 `gradle-wrapper.jar`/`gradlew`，Android Studio 检测到 `gradle/wrapper/gradle-wrapper.properties` 会自动生成；若提示缺失 wrapper，选「Use Gradle from wrapper」让 AS 自动补全。
3. 启动后端（见仓库根目录 `server/` 或 `module_1_2/`），确认 `http://<host>:8000/health` 返回 `{"status":"ok"}`。
4. 选一个模拟器或真机运行 `app`。

## 后端地址配置

App 内底部「后端地址」可改，点「保存地址」生效（无需重启）。默认值：

| 运行方式 | 地址 |
|---|---|
| Android 模拟器访问宿主机 | `http://10.0.2.2:8000`（默认） |
| 真机 + USB 调试 | `http://localhost:8000`（需 adb reverse tcp:8000 tcp:8000） |
| 真机 + 手机热点 | `http://192.168.x.x:8000`（宿主机局域网 IP，注意防火墙放行 8000） |

> 已通过 `usesCleartextTraffic=true` 放行 HTTP，无需额外 network security config。

## 代码结构

```
com.hmercalc
├── common/     DTO（与后端 models.py 对齐）、Recognizer/Calculator 接口、LaTeX 词表、图片工具
├── remote/     CalcApi(Retrofit)、RemoteRecognizer、RemoteCalculator、动态 baseUrl 拦截器
├── data/       SettingsStore（DataStore，后端地址）
├── di/         NetworkModule（Hilt 提供 Json/OkHttp/Retrofit）
└── ui/         CalcViewModel（状态机）+ theme + screens（CaptureScreen / ResultScreen）
```

状态机：`IDLE → IMAGE_LOADED → RECOGNIZED →(编辑)→ EDITING → COMPUTED`，任何环节可 `ERROR`。

## 与对接文档的差异（重要）

1. **拍照实现**：文档 C1 写 CameraX；本骨架先用「系统相机 + FileProvider」+「相册选择器 Photo Picker」实现拍照/选图（零额外依赖、更稳）。CameraX 升级项见下方 TODO。
2. **jlatexmath 坐标**：文档写 `io.github.noties` + `0.4.0`，实际正确坐标是 **`ru.noties:jlatexmath-android:0.2.0`**（文档需订正）。
3. **C7 编辑**：先用「可编辑 LaTeX 文本框 + jlatexmath 渲染」的可靠方案；huarangmeng/latex WYSIWYG 是后续 spike（文档 §4.1 也要求 spike 优先）。

## TODO（后续迭代）

- [ ] C1：把「系统相机」换成 CameraX 内置预览 + 拍照（体验更好）。
- [ ] C7：接入 huarangmeng/latex（KMP WYSIWYG）做所见即所得编辑。
- [ ] E1：接入 Room 做历史记录（文档只要求「建表即可」）。
- [ ] 后端地址配置做成独立设置页 + 连接自检（点保存时 ping `/health`）。
