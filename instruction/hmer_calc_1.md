# 模块 1 指导文档：图像读取 + 识别（C1 / C2 / C3）

> 项目：HMER-Calc（手写公式识别 + 计算）
> 责任人：成员 1
> 本文档为模块 1 的开发指导。全局约定以同目录 `HEAD.md` 为准。

---

## 0. 模块定位

输入一张手写公式图片，输出一条**符合全局词表约定**的 LaTeX 字符串（及置信度），供模块 2 解析计算、模块 3 展示。
**交付物不是"模型能识别"，而是"能在 Android 真机上通过接口输出合法 LaTeX"。**

---

## 1. 处理流程（箭头 = 数据流向）

```
拍照 (CameraX) / 相册选图 (Photo Picker)
   --> 得到 Bitmap 原图
   --> 【C2 预处理】灰度化 --> 二值化/去噪 --> 书写区域裁剪(可选: 倾斜校正) --> 缩放到模型输入尺寸 --> 归一化
   --> 【C3 推理】ONNX Runtime 加载 assets/model.onnx
   --> CNN 编码器提取特征 --> GRU/Attention 解码器逐 token 生成
   --> Tokenizer：token id --> LaTeX 字符，拼接成 LaTeX 字符串
   --> 计算整体置信度 (可选: token 级置信度)
   --> 封装为 RecognitionResult(latex, confidence, tokens)
   --> 返回给 UI 层（模块 3）
```

**预处理子流程（C2，先做能做的）**：灰度化 --> 二值化/去噪 --> 归一化缩放。倾斜校正与区域裁剪列为可选，先不做（需要时再引入 OpenCV）。

---

## 2. 需要实现的功能

| 编号 | 功能 | 说明 |
|---|---|---|
| C1-1 | 拍照获取图片 | 用 CameraX 调起相机 |
| C1-2 | 相册导入 | 用 Photo Picker |
| C2-1 | 灰度化 | Bitmap 转单通道灰度 |
| C2-2 | 二值化 / 去噪 | 阈值分割、去除孤立噪点 |
| C2-3 | 尺寸归一化 | 缩放到模型输入尺寸（如 96×192 或 64×128） |
| C3-1 | 深度学习识别 | 自训 CNN+GRU/Attention encoder-decoder，输出 LaTeX token 序列 |
| C3-2 | 置信度输出 | 输出整体置信度；token 级置信度作为可选 |
| — | 训练 + 导出 ONNX | PyTorch 训练，`torch.onnx.export` 导出，Python/ONNX 输出一致性对比 |

> 注意：C1 的拍照/选图也可以由模块 3 在 UI 层直接调用，模块 1 只需保证 `recognize(bitmap)` 能吃下 Bitmap 即可。与模块 3 协商谁调相机，但**接口只认 Bitmap**。

---

## 3. 全局统一约定（必须遵守，以 HEAD.md 为准）

### 3.1 统一包名

`com.hmercalc`（建项目时定死，不得改）。

### 3.2 公共接口与数据结构（放 `common` 包，本模块负责提供 `Recognizer` 的实现）

```kotlin
// common/Recognizer.kt —— 本模块实现它
interface Recognizer {
    fun recognize(bitmap: Bitmap): RecognitionResult
}
```

```kotlin
// common/ResultTypes.kt —— 与模块 2/3 共用
enum class AngleMode { DEGREE, RADIAN }
enum class Status { SUCCESS, PARSE_ERROR, COMPUTE_ERROR }

data class RecognitionResult(
    val latex: String,                       // 最终 LaTeX 字符串（单一事实来源）
    val confidence: Double,                  // 整体置信度 0..1
    val tokens: List<Token> = emptyList(),   // 初期可空，E3/E8 再填
)

data class Token(
    val text: String,                        // token 文本，如 "\frac" "{" "2" "}"
    val confidence: Double,                  // 0..1
    val range: IntRange,                     // 在 latex 中的位置，供 E8 高亮
    val alternatives: List<String> = emptyList(), // top-k 候选，供 E3
)
```

```kotlin
// common/Calculator.kt —— 模块 2 实现，本模块不实现，仅知晓
interface Calculator {
    fun calculate(latex: String, mode: AngleMode = AngleMode.DEGREE): CalculationResult
}

data class CalculationResult(
    val latex: String,
    val value: Double?,
    val valueLatex: String?,
    val status: Status,
    val message: String? = null,
)
```

### 3.3 LaTeX 词表（本模块的模型只能输出这些 token）

```kotlin
// common/LatexVocab.kt —— 本模块训练词表 / 推理时 tokenizer 与它保持一致
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

### 3.4 两条铁律

1. 结构一律输出带花括号的规范形式（`\frac{...}{...}`、`\sqrt{...}`、`a^{...}`），不输出 `\over` 等变体。
2. 改词表 / 输出格式，必须同步通知模块 2，双方同步改、同步测。

---

## 4. 本模块对外接口实现要点

- 实现类名建议 `OnnxRecognizer`，实现 `common.Recognizer`。
- 预处理（C2）封装在 `ImagePreprocessor` 内，`recognize()` 内部完成，调用方（模块 3）不关心预处理细节。
- 模型文件放 `app/src/main/assets/model.onnx`，首次加载用 `OnnxSessionManager` 单例管理，避免每次识别重复加载（首次冷启动慢是正常现象，提前测）。
- **M1 里程碑**：先交付一个 `StubRecognizer`（返回写死的合法 LaTeX，如 `"\frac{1}{2}+\sqrt{9}"`），让模块 2/3 先联调；真模型就绪后替换为 `OnnxRecognizer`。

---

## 5. 为 B / E 功能预留的内容

| 功能 | 预留方式 | 现在是否要做 |
|---|---|---|
| E3 候选符号推荐 | `Token.alternatives` 字段已预留 | 否（字段留空） |
| E8 低置信度高亮 | `Token.confidence` + `range` 已预留 | 否 |
| E4 框选识别区域 | `recognize()` 前加裁剪步骤，接口不变 | 否 |
| E5 多公式 | 注意别把返回值写死成单个结果，预留 `List` 扩展 | 否 |
| B1 端侧部署 | 本身就是主路径（ONNX Runtime） | 是（主路径） |
| B2 模型训练对比 | 换 `Recognizer` 实现即可 | 留接口 |
| B3 数据回流 | 修正结果由模块 2/3 序列化到 `data/`，本模块不涉及 | 否 |
| B4 实时流式识别 | 接口预留 `recognizeFrame()`（后续加） | 否 |
| B5 端云协同 | `RemoteRecognizer` 接口形状预留，不实现 | 否 |

---

## 6. 开发语言与版本要求

| 项 | 要求 |
|---|---|
| App 语言 | Kotlin（全项目统一） |
| 训练语言 | Python 3.10+ |
| 推理引擎 | ONNX Runtime（`onnxruntime-android`） |
| 图像 | CameraX、Photo Picker、Coil |
| 预处理 | 纯 Kotlin Bitmap 操作；倾斜校正若做再引入 OpenCV |

版本（推荐稳定值，三人保持一致，以 Android Studio 最新稳定模板为准）：

| 组件 | 推荐版本 |
|---|---|
| Android Studio | Koala 2024.1.1 或更新 |
| JDK | 17 |
| Gradle / AGP | 8.7+ / 8.5+ |
| Kotlin | 2.0.x |
| compileSdk / targetSdk / minSdk | 34 / 34 / 26 |
| onnxruntime-android | 1.18.0 |
| CameraX | 1.3.4 |
| Coil | 2.6.0 |
| Python / PyTorch / onnx | 3.10 / 2.2+ / 1.16.0 |

---

## 7. 需要额外下载的内容

- **模型依赖**：`onnxruntime-android`（Gradle 依赖，见上表）。
- **训练集**（训练侧，不进 App）：
  1. CROHME 官方包 `TC11_package_CROHME2019.zip`（364MB，含 2011–2019 手写公式 + InkML 内嵌 LaTeX 标签），下载页：https://tc101-demo.github.io/datasets/ICDAR2019-CROHME-TDF_1/
  2. 合成数据可选：[lukas-blecher/LaTeX-OCR](https://github.com/lukas-blecher/LaTeX-OCR) 的 `tex2png` / `render_dataset` 渲染管线，或现成合成集 [PadishahIIIXXX/latex-ocr-dataset](https://huggingface.co/datasets/PadishahIIIXXX/latex-ocr-dataset)
  3. 自采集手写样本（可选，兼作 B2 加分项）
- **预处理工具**：CROHME 是 InkML 格式，需渲染笔画成图 + 抽 LaTeX 标签，可用 CROHMELib 或自写脚本（`python/dataset/` 内）。

---

## 8. 文件目录设计（本模块负责的部分）

```
HMER-Calc/
├── app/src/main/
│   ├── assets/
│   │   └── model.onnx                     # 本模块交付的模型
│   └── java/com/hmercalc/
│       ├── common/                        # 契约（实现以下接口，不拥有 common）
│       │   ├── Recognizer.kt
│       │   ├── ResultTypes.kt
│       │   └── LatexVocab.kt
│       └── recognition/                   # 本模块实现
│           ├── StubRecognizer.kt          # 里程碑 M1 用的桩
│           ├── OnnxRecognizer.kt          # 真实现（实现 common.Recognizer）
│           ├── preprocess/
│           │   └── ImagePreprocessor.kt   # C2 灰度/二值/去噪/裁剪/归一化
│           └── onnx/
│               ├── OnnxSessionManager.kt  # 模型加载/释放（单例）
│               └── Tokenizer.kt           # token id <-> LaTeX 字符（与词表一致）
└── python/                                # 训练侧（独立，不进 App）
    ├── dataset/                           # CROHME InkML 提取、合成数据脚本
    │   ├── extract_crohme.py
    │   └── generate_synthetic.py
    ├── train.py                           # CNN+GRU/Attention 训练
    ├── export_onnx.py                     # 导出 .onnx
    └── requirements.txt
```

---

## 9. 交付物与验收要点

1. `OnnxRecognizer` 实现 `recognize(bitmap)`，返回合法 `RecognitionResult`。
2. `assets/model.onnx` 能被 ONNX Runtime 正常加载，真机推理不崩。
3. 输出的 `latex` 逐字符合 `LatexVocab` 词表与映射规则。
4. `confidence` ∈ [0,1]。
5. 里程碑 M1 的 `StubRecognizer` 可用。
6. 对照 `HEAD.md` 中"模块 1 查验对照单"逐项自查。
