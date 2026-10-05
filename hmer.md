# HMER-Calc 项目速览（onboarding）

> 用途：让（未来的自己 / 新组员 / 接手的 AI）读完本文件就能迅速跟上项目现状。
> 维护：组长 秦琛翔。最后更新：2026-10-06。

---

## 一、项目是什么

**HMER-Calc**：手写体数学公式识别与计算系统（课程综合工程设计）。

- 用户手写/拍摄一条数学公式 → **识别成 LaTeX** → **渲染成可读公式** → **算出数值结果**。
- 典型用例：拍 `48÷6`，App 显示 `48 ÷ 6` 与结果 `8`；识别错了可手动修正后重算。

**架构：C/S（客户端-服务端）**

```
[Android 手机 App]  ── HTTP ──►  [电脑后端 FastAPI]
   拍照/选图                          ① /recognize  图片 → LaTeX + 置信度
   渲染公式 + 修正                    ② /calculate  LaTeX → 数值
   显示数值结果
```

- 后端跑在**电脑**上（模型推理吃 CPU/内存，放手机不现实）；手机开热点、电脑连热点访问。
- 模拟器阶段用固定地址 `http://10.0.2.2:8000` 访问宿主机；**真机要换成电脑局域网 IP**（见 §七）。

---

## 二、目录地图（重点：哪个是「当前活跃代码」）

| 路径 | 是什么 | 状态 |
|---|---|---|
| `module_1_2/` | **后端实际代码**（识别 + 计算合并后的完整实现） | ✅ 当前开发/运行/测试都在这里 |
| `android/` | **Android 客户端源码**（Compose + Hilt + Retrofit） | ✅ 当前活跃 |
| `instruction_cs/` | C/S 版指导文档（`ALL.md` 全局契约 + `hmer_cs_1/2/3.md`） | ✅ 权威文档 |
| `server/` | 后端**仓库骨架**（组长锁定的 main/models/vocab + 空 recognition/calculation） | ⚠️ 仅骨架，**未合并** module_1_2 的实现，别在这里改 |
| `module_1/`、`module_2/` | 旧的**单模块**目录（合并前遗留） | ❌ 历史，不再使用 |
| `instruction/` | 旧版（端侧方案）指导文档 | ❌ 历史，仅作对比参考 |
| `files/` | 开题/中期/总结报告（docx/doc） | 📄 报告素材 |
| `对接差异.md` | 复盘：pix2tex→pix2text 等选型变更的来龙去脉 | 📄 参考 |
| `分发/`、`error/`、`.venv/`、`.gradle-home/`、`.android-avd/` | 生成物 / 临时测试图 / 虚拟环境 / 缓存 / 模拟器镜像 | 🚫 已 .gitignore，不入库 |

> ⚠️ 最容易踩的坑：**别去 `server/` 或 `module_1/`、`module_2/` 改代码**，当前一切都在 `module_1_2/`。

---

## 三、三个模块分工

| 模块 | 责任人 | 负责 | 代码位置 |
|---|---|---|---|
| 一（识别） | 马自远 | 图片 → LaTeX + 置信度 | `module_1_2/app/recognition/` |
| 二（计算） | 孟飞扬 | LaTeX → 数值结果 | `module_1_2/app/calculation/` |
| 三（客户端） | 秦琛翔（组长） | Android App | `android/` |

契约文件（三方共用、组长锁定、只读）：`module_1_2/app/common/models.py` + `vocab.py`。

---

## 四、关键技术决策（含组长订正，读懂这些就懂大半）

1. **识别模型 = pix2text**（不是 pix2tex）。pix2tex 默认权重偏印刷体，手写体实测全失败；pix2text 的 MFR 模型已用手写数据重训。基于 onnxruntime，CPU 即可，无需 PyTorch/CUDA。首次运行会自动下载模型权重（需联网一次）。
2. **预处理只做几何**：EXIF 方向归正 + 最长边缩到 ≤1600 + 方向候选。**不做**二值化/去噪（会伤识别率）。
3. **多方向竞优**：无可信 EXIF 时跑 0/90/180/270° 四方向取最高分；有 EXIF 只认归正后的 0°。
4. **低置信度门槛 0.95**：最高分候选 < 0.95 时降级为 ERROR 让用户确认（正确样本 0.9568~1.0，错误样本 0.8977~0.9445）。
5. **数字粘连修复（2026-10 新增，两处双保险）**：pix2text 会把 `48` 拆成 `4 8`（score 仍 1.0，门槛拦不住），而 latex2sympy2 把 `4 8` **静默**算成 4×8。修复在模块一 `recognition/postprocess.py`（识别后合并「数字-空白-数字」）+ 模块二 `calculation/calculator.py`（解析前兜底再合并，覆盖 C7 修正页手输）。两份互不 import，守模块边界。
6. **低置信度墨迹裁剪重试（2026-10 新增）**：首轮 < 0.95 时裁到墨迹包围盒再跑一轮，两轮取优（实测 12.jpg 全图 0.7831 → 裁剪 0.9960）。好图零开销（裁剪无变化的候选跳过）。
7. **角度模式三态**：`deg`（角度）/ `rad`（弧度）/ `auto`（默认，三角参数纯数字按角度、含 π 按弧度）。
8. **C7 修正闭环**：识别后自动先算一次供判定 → 错了进「修正公式」页（实时渲染预览 + 分类符号面板 + LaTeX 编辑框）→ 重算 → 完成/退出修正。
9. **契约字段 snake_case**，Android 端 `@SerialName` 映射；业务错误返回 HTTP 200 + `status`，只有请求体格式错误才 4xx。

---

## 五、本机环境与路径（Windows，组长实测 2026-10-05）

| 项 | 路径/值 |
|---|---|
| 后端 Python 虚拟环境 | `E:\HMER-Calc\.venv\Scripts\python.exe` |
| JDK | `E:\JDK-17`（环境变量 `JAVA_HOME`） |
| Android SDK | `E:\AndroidSdk`（`platform-tools\adb.exe`、`emulator\emulator.exe`） |
| Gradle 缓存 home | `E:\HMER-Calc\.gradle-home`（`GRADLE_USER_HOME`） |
| 模拟器镜像 home | `E:\HMER-Calc\.android-avd\avd`（`ANDROID_AVD_HOME`） |
| 模拟器 AVD 名 | `Pixel_7` |
| 后端端口 | `8000` |
| 模拟器 → 宿主机地址 | `http://10.0.2.2:8000` |

---

## 六、常用命令速查（在 Git Bash 下）

**后端启动**（工作目录 = `module_1_2`）：

```bash
cd /e/HMER-Calc/module_1_2
../.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**后端测试**（识别 60 项 + 计算 27 项，约 100s）：

```bash
cd /e/HMER-Calc/module_1_2
../.venv/Scripts/python -m pytest tests/ -q
```

**Android 构建**（工作目录 = `android`）：

```bash
cd /e/HMER-Calc/android
JAVA_HOME="E:/JDK-17" GRADLE_USER_HOME="E:/HMER-Calc/.gradle-home" ./gradlew assembleDebug
# 产物：android/app/build/outputs/apk/debug/app-debug.apk
```

**装机**（模拟器或真机，先 `adb devices` 确认连接）：

```bash
export PATH="$PATH:/e/AndroidSdk/platform-tools"
adb install -r /e/HMER-Calc/android/app/build/outputs/apk/debug/app-debug.apk
```

**启动模拟器**：

```bash
ANDROID_AVD_HOME="E:/HMER-Calc/.android-avd/avd" E:/AndroidSdk/emulator/emulator.exe -avd Pixel_7 -no-snapshot-load -no-boot-anim -gpu auto
```

---

## 七、真机验证「拍照识别」完整步骤（含联网配置）

> 模拟器只能验证「选图」，**真实摄像头拍照**必须在真机验证。以下是一次到位的最简流程。

### 第 0 步：前置准备

- 手机开启 **开发者选项 → USB 调试**（设置 → 关于手机 → 连点版本号 7 次 → 开发者选项 → 打开 USB 调试）。
- 电脑装了 adb（`E:\AndroidSdk\platform-tools\adb.exe`）。

### 第 1 步：手机与电脑同网（二选一）

- **方式 A（推荐，最省事）**：手机开「个人热点」→ 电脑连上这个热点。
- **方式 B**：手机和电脑连**同一个 WiFi**。

### 第 2 步：查电脑局域网 IP

电脑命令行跑：

```bash
ipconfig
```

看「无线局域网适配器 WLAN」的 **IPv4 地址**（热点下常见 `192.168.43.x`，WiFi 下常见 `192.168.1.x` / `192.168.0.x`）。记下它，比如 `192.168.43.100`。

### 第 3 步：启动后端（已默认 `--host 0.0.0.0`）

```bash
cd /e/HMER-Calc/module_1_2
../.venv/Scripts/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

电脑上自测：`curl http://127.0.0.1:8000/health` 返回 `{"status":"ok"}`。

### 第 4 步：Windows 防火墙放行 8000 端口

控制面板 → Windows Defender 防火墙 → 高级设置 → **入站规则** → 新建规则 → 端口 → TCP 8000 → 允许连接。
（排查阶段也可先临时关闭防火墙，确认是它挡的再加规则。）

### 第 5 步：把 App 后端地址改成电脑 IP（⚠️ 关键，当前默认是模拟器专用）

当前 App 实际请求地址由 `BackendUrlHolder.baseUrl` 决定（拦截器读它），默认写死 `http://10.0.2.2:8000`——**真机上这个地址不通**。改法二选一：

- **方案 A（不依赖我，改默认值重编译）**：改两个文件的默认值为电脑 IP，再重编译装机：
  - `android/app/src/main/java/com/hmercalc/remote/DynamicBaseUrlInterceptor.kt` 里的 `BackendUrlHolder.baseUrl`
  - `android/app/src/main/java/com/hmercalc/data/SettingsStore.kt` 里的 `DEFAULT_BASE_URL`
- **方案 B（一劳永逸，需改 UI）**：恢复后端地址的输入框（当前 UI 只读展示，是「真机适配时再开放」预留项）。要我做的话说一声，我在设置页加个可编辑地址栏，改了即存 DataStore、无需重编译。

> 提示：方案 A 每次换热点/WiFi 都要改 IP 重编译；方案 B 改一次代码，之后在 App 里随手改。

### 第 6 步：装 APK 到真机

USB 连接手机，首次会弹「允许 USB 调试」→ 允许。

```bash
export PATH="$PATH:/e/AndroidSdk/platform-tools"
adb devices                 # 应看到手机，状态 device
adb install -r /e/HMER-Calc/android/app/build/outputs/apk/debug/app-debug.apk
```

### 第 7 步：拍照验证

打开 App → 点「拍照」→ 拍摄手写公式（如 `48÷6`）→ 应识别出 `48 ÷ 6`、算出 `8`。

### 第 8 步：连不上时的排查顺序

1. `adb devices` 有没有手机？没有 → USB 线/驱动/授权。
2. 电脑 `curl http://127.0.0.1:8000/health` 通不通？不通 → 后端没起。
3. 手机浏览器打开 `http://<电脑IP>:8000/health` 通不通？不通 → 防火墙/不在同一网。
4. 手机和电脑是不是真在同一网（热点 vs WiFi 别混）？部分热点有「设备隔离」，可改用 USB 网络共享或换 WiFi。
5. App 里地址改对没（第 5 步）？

---

## 八、已知坑（踩过的都记在这）

- **Windows .bat**：LF 换行会闪退；`if` 块里 `echo` 带括号会破坏 cmd 解析。写 bat 用 CRLF + 括号外提。
- **adb 路径**：Git Bash 下给 adb.exe 传本地文件路径必须用 `E:/...`（Windows 风格），不能用 MSYS 的 `/e/...`，否则报找不到。
- **编码**：中文路径/内容过 cmd 可能变 GBK 乱码，脚本里涉及中文要留意。
- **模型首次加载慢**：pix2text 首次 `recognize_formula` 要加载模型（数秒到十几秒），后续变快。App 已提示「首次识别需加载模型，可能较慢」。
- **低置信度重试**：整页照片且公式占比小会触发裁剪重试，单请求最长约 9s；正常公式图 0.8s。
- **照片 EXIF**：真机拍照自带 orientation，后端已做 EXIF 归正；不要用会剥离 EXIF 的工具重存测试图。

---

## 九、当前状态（截至 2026-10-06）

- **代码已全部提交**，工作树干净：
  - `e1a07ea` fix: 数字粘连修复 + 低置信度墨迹裁剪重试（模块 1/2 双保险）
  - `443df1b` feat: Android 客户端首次入库 + 本轮 UI 改进
- 后端与模拟器当前**均未运行**（上次会话结束后已停）。
- 待办 / 可继续的方向：
  - 真机验证拍照识别（见 §七，需先处理第 5 步的后端地址）。
  - 恢复后端地址 UI 编辑（方案 B，见 §七第 5 步）。
  - 之前规划的优化项（首请求模型加载延迟、方向竞优顺序等）按需再议。
