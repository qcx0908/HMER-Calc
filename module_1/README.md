# 交付说明 README —— 模块一（后端识别服务）

> 交付人：成员 1　接收人：**模块 2 负责人（整合方）**，最终由组长验收
> 对应文档：`ALL.md`（契约与查验单）、`DELIVERY.md`（打包规范）、`hmer_cs_1.md`（模块一技术指南）
> 本文件按 `DELIVERY.md` §三 要求，讲清 **4 件事**：怎么装依赖、怎么启动、三个接口的自测命令与**真实返回**、坑点。

> ## 🔴 如果你是来整合模块一 + 模块二的：先读 **§9 整合指南**
> §9 用最短路径告诉你：**复制哪些文件、`requirements.txt` 要改什么、哪些文件一个字都不能动、
> 怎么验证整合结果**，以及整合时最常见的 5 个坑。

---

## ⚠️ 0. 请先看这条：`requirements.txt` 缺少 `pix2text`

> **【组长已处理 2026-10-04 · 本条作废】**
> 组长按「方案 A」：`requirements.txt` 已改为**只含 `pix2text`**，`pix2tex` 移除不再保留（运行时不用，且拉 torch/降级 transformers/opencv 并存；报告里 pix2tex 的对比结论照写即可）。
> 因此下面 §0/§1 的「临时安装命令」、§9.2 的「加一行 pix2text」都不再需要，直接 `pip install -r requirements.txt` 即可。

本模块的识别模型是 **Pix2Text 1.1.7**（`hmer_cs_1.md` 里写的 pix2tex 已弃用，原因见 §5）。

**但组长锁定的 `requirements.txt` 里没有 `pix2text`**，只有旧方案 `pix2tex`：

```
pix2tex        ← 旧方案，已弃用但保留（作为报告里的模型对比基线）
latex2sympy2   ← 模块二
sympy          ← 模块二
fastapi / uvicorn / pydantic / pillow / pytest / httpx
```

**后果**：按现状 `pip install -r requirements.txt` 之后，模块一 `import pix2text` 会直接失败。

**这不是成员 1 能自行修的** —— `requirements.txt` 属组长锁定只读（`server/README.md` §一）。
请组长在合库时补一行：

```
pix2text
```

在补齐之前，临时安装命令是：

```bash
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install pix2text -i https://pypi.tuna.tsinghua.edu.cn/simple
```

> ⚠️ 安装 `pix2text` 会把 `transformers` 从 5.x **降级到 4.57.x**（实测），
> 并同时拉入 `opencv-python`（与 pix2tex 要的 `opencv-python-headless` 并存）。
> 实测降级后 `pix2tex` 仍可正常导入，不影响模块二的 `latex2sympy2` / `sympy`。

---

## 1. 怎么装依赖

```bash
cd <交付文件夹>
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install pix2text -i https://pypi.tuna.tsinghua.edu.cn/simple   # 见 §0
```

Python 要求 **3.10+**（开发与验证环境为 **3.12.2**）。

---

## 2. 怎么启动

**⚠️ 重要：模块二（`app/calculation/`）尚未交付，所以现在还不能用组长入口启动。**

`app/main.py` 会 import 两个 router，缺一个就起不来（实测报错）：

```
ModuleNotFoundError: No module named 'app.calculation.router'
```

这是 `server/README.md` §五 写明的**骨架正常状态**，不是骨架或模块一损坏。

### 2.1 模块二交付前：只启动模块一（用于验收本模块）

在交付文件夹下建一个临时入口文件 `tmp_app.py`：

```python
# tmp_app.py —— 仅用于模块二交付前单独验收模块一，合库后请删除
from fastapi import FastAPI
from app.recognition.router import router as recognition_router

app = FastAPI()
app.include_router(recognition_router)
```

```bash
uvicorn tmp_app:app --host 0.0.0.0 --port 8000
```

### 2.2 模块二交付后：用组长入口（正式方式）

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**`--host 0.0.0.0` 必须带** —— 不带的话手机连不上；Windows 防火墙需放行 8000 端口。

---

## 3. 三个接口的自测命令 + 真实返回

以下返回均为 **2026-10-06 在本机实测**粘贴的原样输出（Pix2Text 1.1.7 / CPU / Python 3.12.2）。
测试图：`tests/fixtures/formula_2.png`（`\frac{\pi}{2}` 的渲染图）与 `tests/fixtures/photo_picture3.png`（真实手写照片）。

### 3.1 `GET /health`

```bash
curl http://127.0.0.1:8000/health
```

真实返回（HTTP 200，实测 `time_total=0.004s`）：

```json
{"status":"ok"}
```

### 3.2 `POST /recognize`（传 `tests/fixtures/formula_2.png` 的 base64，无 `data:` 前缀）

因为 base64 很长（约 3900 字符），建议先用文件承载请求体：

```bash
# 1) 生成请求体 JSON（Python 一行搞定，避免命令行超长）
python -c "import base64,json;print(json.dumps({'image':base64.b64encode(open('tests/fixtures/formula_2.png','rb').read()).decode()}))" > body.json

# 2) 发请求
curl -X POST http://127.0.0.1:8000/recognize -H "Content-Type: application/json" --data-binary @body.json
```

真实返回（HTTP 200）：

```json
{"latex":"\\frac{\\pi} {2}","confidence":0.9997474551200867,"tokens":[],"status":"SUCCESS","message":null}
```

同一命令传 **真实手写照片** `tests/fixtures/photo_picture3.png`（实测 `time_total=0.514s`）：

```json
{"latex":"\\cos\\frac{\\pi} {2}+1","confidence":0.9969229102134705,"tokens":[],"status":"SUCCESS","message":null}
```

### 3.3 `POST /calculate`（**模块二，尚未交付**）

模块二交付后按 `hmer_cs_2.md` 补此节；预期形如：

```bash
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" -d "{\"latex\":\"1+2*3\",\"mode\":\"deg\"}"
```

### 3.4 错误场景（验证"业务错误不 500"）

```bash
# 空图片
curl -X POST http://127.0.0.1:8000/recognize -H "Content-Type: application/json" -d "{\"image\":\"\"}"
```
真实返回（**HTTP 200**，走 ERROR 通道）：
```json
{"latex":"","confidence":0.0,"tokens":[],"status":"ERROR","message":"image 为空：需要 JPEG/PNG 字节的 Base64 字符串（不带 data: 前缀）"}
```

非法 base64（实测）：`{"latex":"","confidence":0.0,"tokens":[],"status":"ERROR","message":"Base64 解码失败：Only base64 data is allowed"}`

缺字段（实测 **HTTP 422**，格式错误走 4xx，符合契约）：
```json
{"detail":[{"type":"missing","loc":["body","image"],"msg":"Field required","input":{}}]}
```

**异常兜底（可靠性保证）**：识别过程中任何**未预期异常**（模型加载失败、无网络下首次下载权重、
模型内部崩溃、ONNX 会话初始化失败等）也会被翻译成
`HTTP 200` + `status="ERROR"` + `message`（含异常类型与最后几帧调用栈），**绝不返回 5xx**。

对应回归测试 `test_unexpected_exception_never_returns_500`：
它 monkeypatch 掉识别器使其抛 `RuntimeError`，断言接口仍返回 200 + ERROR。
这直接对应 `ALL.md` §六 红牌项 2/3（"遇非法输入返回 500 崩溃即退回"）。

**低置信度门槛（`MIN_ACCEPTABLE_SCORE = 0.95`，2026-10-06 按需求方确认实现）**：
当所有候选方向的**最高分 < 0.95** 时，接口**不返回识别结果**，改为
`HTTP 200` + `status="ERROR"` + `latex=""`，`message` 提示"请确认图片方向是否正确、或框选单个公式后重试"。
模型原始输出仍保留在内部 `returned_latex` 与响应头 `X-Recognition-Meta` 中供排查。

实测依据（22 个样本人工标注比对，见 §5）：**正确样本 score 0.9568~1.0；错误样本 0.8977~0.9445**；
另有一张方向选错的样本 0.8914 —— 即"最高分 < 0.95"在本样本集内**全部是错的结果**。

真实 HTTP 验证（同一进程内两次请求）：

```
POST /recognize (photo_picture3.png, 0.9969) → 200 {"latex":"\\cos\\frac{\\pi} {2}+1",...,"status":"SUCCESS"}
POST /recognize (picture1.jpg,     0.9348) → 200 {"latex":"","confidence":0.9348,...,"status":"ERROR",
                                               "message":"识别置信度偏低（0.9348 < 0.95），结果可能不可靠：..."}
                                               X-Recognition-Meta: reason="low_confidence", angle=90
```

⚠️ 这是**经验阈值**，不是理论边界：正确样本下沿（0.9568）与错误样本上沿（0.9445）仅差 0.012，
样本量 19。因此它**只用于"宁可让用户确认，也不返回错误结果"**，不能替代题目 C7 的手动修正闭环。

对应回归测试 `test_low_confidence_is_downgraded_to_error`。

---

## 4. 坑点（对接模块 3 前必读）

1. **首次 `/recognize` 会下载模型权重，很慢**（约 230 MB，几秒到十几秒，需联网一次）。

   **⚠️ 更要紧的是「首跑预热」现象**（实测数据，见下表）：模型**每遇到一种新的图片尺寸**，
   第一次推理会异常慢（**32~37 秒**），之后同尺寸的推理骤降到 0.5~12 秒。

   > 已复现三次：`picture1` 0° 首次 37.21s、`picture2` 0° 首次 32.66s、
   > 以及**全新进程对一张 7 KB 小图（`formula_2.png`）的第一次请求 37.19s**。

   | 图片（尺寸） | 该尺寸下 0° 首次 | 90° | 180° | 270° |
   |---|---|---|---|---|
   | picture1（852×2382） | **37.21s** | 0.63s | 1.21s | 0.56s |
   | picture2（1317×1756） | **32.66s** | 5.86s | 11.98s | 5.86s |
   | picture3（292×582，EXIF 归正→582×292） | 0.42s | — | — | — |

   **注意**：这不是"权重下载"造成的（权重已缓存时同样发生），而是首次推理本身的预热开销。

   **对 Android 端的建议**：客户端超时**不要只给 15s**，建议 **≥60s**；
   或在 App 启动后用一张固定图先"预热"一次，把首次的真实体验让给启动画面而不是用户操作。
   若首次请求即超时，用户看到的是失败，而模型其实只是还没热身。
2. **接口字段严格以 `ALL.md` 契约为准，没有私自加字段。**
   响应就是 `latex / confidence / tokens / status / message` 五个字段。
   识别过程的诊断信息（试过哪些旋转方向、各自 score 与耗时）走**响应头 `X-Recognition-Meta`**，不进 JSON 契约。
3. **图片方向**：本模块会先按 EXIF 方向把图摆正。注意区分两种情况：
   - EXIF **真的指示了一次旋转**（orientation 2~8，例如 `picture3` 的 8）：归正后直接采信，**只跑 1 次推理**（实测 0.42s）；
   - EXIF **等于 0/1 或缺失**（例如 `picture1`/`picture2`）：表示"本来就正"，**并不构成方向约束**。
     此时会依次尝试 0°/90°/180°/270° 并选最优 —— 更稳，但耗时成倍增加（picture1 实测 39.89s、picture2 56.74s）。

   **建议 Android 端把手机与纸面文字方向对齐后再上传**，可省掉多方向搜索这一大块开销。
4. **`confidence` 是模型原生 token 级自信度，不等于"识别正确"**。实测：输出明显错误时 score 仍可达 0.88~0.93
   （`picture1` 的 0° 垃圾输出 `\begin{matrix} \hline{} \\ \end{matrix}` 拿到 0.9040）。
   `ALL.md` 只要求它 ∈[0,1]，本模块满足；但**不要**拿它当正确性判据（E8 低置信度高亮要谨慎使用）。
5. **多行 / 多公式结构不支持**：识别到多行结构（`array`/`matrix`/`cases` 且含多个换行）会返回
   `status="ERROR"` + message（C3 只要求单一公式；E7 多公式未实现）。**请框选单个公式后再上传。**
   （`picture2` 是整页多公式，实测四个方向全部落到 ERROR 通道，未冒充成功。）
6. **不要指望"预处理救图片"**：本模块**不做**二值化/去噪/锐化（Pix2Text 自带归一化，额外处理反而降准确率）。
   真实照片识别失败时，优先改拍摄方式（对准、占满画面、光线均匀、横持对齐）。

---

## 5. 关键实现说明（供组长验收与报告引用）

| 项 | 说明 |
|---|---|
| 识别模型 | **Pix2Text 1.1.7**（ONNX Runtime，CPU 可跑）。换 pix2tex 的原因见下方"模型对比" |
| 换模型口子 | `app/recognition/recognizer.py` 的 `Recognizer` 类（对应 B2）。契约字段不变 |
| 预处理 | 仅做 Base64 解码 + EXIF 方向归正 + 超大图等比缩小；不做像素增强 |
| LaTeX 处理 | **原样透传，不做任何规范化/词表过滤**（遵守 `hmer_cs_1.md` §3.3/§3.4 铁律 1） |
| 置信度来源 | `recognize_formula(img, return_text=False)["score"]`，模型原生值 ∈[0,1] |

### 实测方向竞优数据（`X-Recognition-Meta` 可复现）

| 图片 | EXIF | 0° | 90° | 180° | 270° | 选中 |
|---|---|---|---|---|---|---|
| picture3 | 8 | **0.9969（正确）** | 0.8666 | 0.8527 | 0.8115 | 0° |
| picture1 | 0 | 0.9069（垃圾） | **0.9337（正确）** | 0.8739 | 0.8254 | 90° |

> 注意 0° 的垃圾输出也拿到 0.9069 —— 所以不能"score 高就短路"，必须跑满候选方向取最优。

### 真实照片/素材实测对照表（2026-10-06）

评估工具：`eval_photos.py`（走与线上完全相同的 `Recognizer.recognize` 路径）。
正确性由**人工标注**（`ground_truth.json`）逐条比对，不由脚本猜测。

| 图片 | 尺寸 | EXIF | 候选数 | 选中角度 | score | 耗时(s) | 状态 | 正确性 | 识别结果(LaTeX) |
|---|---|---|---|---|---|---|---|---|---|
| formula_1.png | 578×218 | 无 | 4 | 0° | 1.0 | 37.17 | SUCCESS | ✅ 正确 | `1+2 \times3` |
| formula_2.png | 173×232 | 无 | 4 | 0° | 0.9997 | 0.43 | SUCCESS | ✅ 正确 | `\frac{\pi} {2}` |
| formula_3.png | 638×218 | 无 | 4 | 0° | 1.0 | 0.43 | SUCCESS | ✅ 正确 | `\operatorname{c o s} ( \pi)+1` |
| photo_picture3.png | 292×582 | **8** | **1** | 0° | 0.9969 | 0.43 | SUCCESS | ✅ 正确 | `\cos\frac{\pi} {2}+1` |
| picture1.jpg | 852×2382 | 0 | 4 | 90° | 0.9348 | 3.14 | SUCCESS | ❌ 错误 | `\frac{1} {1-x}=\sum_{n=0}^{3 3} X^{n}` |
| picture2.jpg | 1317×1756 | 0 | 4 | 270° | 0.8985 | 56.77 | ERROR | （整页多公式，不计入） | 多行结构被拦下 |

**准确率：4/5 = 80.0%**（picture2 是整页多公式，超出 C3 单一公式范围，不计入）。

> ⚠️ **本节数据已并入下方「全程合并总表」**（20 个样本、准确率 14/18 = 77.8%），
> 结论以合并总表为准；此处保留仅便于对照。

**置信度与实际正确性的关系**（合并全部 18 个已标注样本）：

| 样本组 | 数量 | score 区间 | 平均 score |
|---|---|---|---|
| 正确样本 | 14 | **0.9568 ~ 1.0** | 0.9931 |
| **错误样本** | 4 | **0.8977 ~ 0.9445** | 0.9222 |

**阈值检验**：若按 `score ≥ 0.95` 判为"可信"，**0/4 个错误样本会被放行** ——
本样本集里 0.95 确实能干净地分开正确与错误两组。

**但这不等于 confidence 可以当正确性判据**，原因有二：

1. **样本量只有 18**，且这是**单一模型、有限书写风格**下的经验值。报告里应写成
   "本实验中 0.95 可作为经验阈值"，而不是"confidence 能判对错"。
2. 更关键的是：**错误样本的 score 依然很高**（0.8977~0.9445，与正确样本的下沿 0.9568 只差 0.012）。
   其中 `picture1.jpg` 把求和上标 `n` 误读为 `3 3`（`\sum_{n=0}^{\infty}` → `\sum_{n=0}^{3 3}`），
   score 仍有 **0.9348**；`picture1` 的 0° 方向输出纯垃圾 `\begin{matrix} \hline{} \\ \end{matrix}`
   时 score 也有 **0.9040**。这类"自信地读错"无法靠阈值拦住。

**对 E8「低置信度高亮」的建议**：可以用 `score < 0.95` 作为**初步提示**（本实验中有效），
但必须同时提供**人工修正闭环**（题目 C7），不能把 confidence 当作自动放行的依据。

各候选方向得分 / 耗时明细：

| 图片 | 0° | 90° | 180° | 270° |
|---|---|---|---|---|
| formula_1.png | **1.0** / 37.17s | — | — | — |
| formula_2.png | **0.9997** / 0.43s | — | — | — |
| formula_3.png | **1.0** / 0.43s | — | — | — |
| photo_picture3.png | **0.9969** / 0.43s | —（EXIF 可信，未试其余方向） | — | — |
| picture1.jpg | 0.904 / 0.42s | **0.9348** / 0.64s | 0.8739 / 1.20s | 0.8255 / 0.56s |
| picture2.jpg | 0.8606 / 32.57s | 0.8765 / 5.86s | 0.8843 / 12.17s | 0.8985 / 5.78s |

> 表中"—"表示该方向未被尝试：识别器在得分 ≥ `EARLY_EXIT_SCORE`(0.95) 时提前结束，
> 既然首个方向已达 0.9969~1.0，就没有必要再花 3 次推理。

### Pad 手写图实测（`PHOTO/`，14 张，2026-10-06）

Pad 导出图特点：**全部 EXIF 无方向标记**（走多方向竞优路径）、白底占比 94~98%、无相机噪声。

**管线成功率 14/14**（无一张失败或多行拦截）；**准确率 10/13 = 76.9%**（1 张语义存疑不计入）。

| 图片 | 尺寸 | 选中角度 | score | 耗时(s) | 正确性 | 识别结果 | 实际内容 |
|---|---|---|---|---|---|---|---|
| 1e07c8c1… | 767×200 | 0° | 0.9996 | 0.56 | ✅ | `1 \times2 \times4 \times8 \times1 6 \times3 2` | 1×2×4×8×16×32 |
| 3b46a53f… | 832×236 | 0° | 0.9993 | 0.50 | ✅ | `1 0 \div5+6 \div3+2 1 \div7` | 10÷5+6÷3+21÷7 |
| 3d3d58dd… | 270×297 | 0° | 1.0 | 0.52 | ✅ | `\frac{6 4} {1 0 2 4}` | 64/1024 |
| 74e8fe95… | 887×238 | 0° | 0.9976 | 0.60 | ✅ | `3 2 1 \times1 3 2+1 2 3 \times1 1 2` | 321×132+123×112 |
| 91741319… | 868×320 | 0° | 1.0 | 0.58 | ✅ | `\frac{1 0 2 4} {6 4}+\frac{6 4} {3 2}+\frac{3 2} {1 6}` | 1024/64+64/32+32/16 |
| 951778c0… | 720×241 | 0° | 0.9995 | 0.51 | ✅ | `\frac{5 1 2} {1 0 2 4}+\sqrt{1 0 2 4}+2^{5}` | 512/1024+√1024+2⁵ |
| bb6d5488… | 1055×226 | 0° | 0.9886 | 0.54 | ✅ | `4+6+5+6 8+1 0 0 x 4` | 4+6+5+68+100×4 |
| cf43c041… | 252×265 | 0° | 0.9568 | 0.50 | ✅ | `2^{1 0}` | 2^10 |
| eb76b4b8… | 442×221 | 0° | 0.9998 | 0.44 | ✅ | `\tan5 4 0^{\circ}` | tan540° |
| fb591a4e… | 252×270 | 0° | 0.9654 | 0.49 | ✅ | `\sqrt{4 0 9 6}` | √4096 |
| 7ec6aec8… | 352×250 | 0° | 0.9445 | 1.77 | ❌ | `\operatorname{s i n} \ 6 o^{\circ}` | sin60°（`0`→字母`o`） |
| 0206eb24… | 400×200 | **180°** | 0.8977 | 47.23 | ❌ | `\operatorname{l o g} \pi^{\rho\sigma}` | **cot60°（选错方向）** |
| fe208988… | 387×200 | **270°** | 0.9119 | 2.74 | ❌ | `\underbrace{\overbrace{\varsigma}}…` | **cos90°（选错方向）** |
| 963562d3… | 1313×207 | 0° | 0.8904 | 11.09 | — | 输出含多处 `\circ^{\circ}` 异常 | 语义存疑，不计入 |

#### ⚠️ 已确认局限：方向竞优会选错（如实记录，勿美化）

两张误判图**都完全正立**（宽高比 2.0 / 1.94，横排笔迹），但**错误方向的 score 反而更高**：

| 图片 | 0°（正确方向） | 90° | 180° | 270° | 机制选中 |
|---|---|---|---|---|---|
| 0206eb24…（实际 `cot 60°`） | **0.8319** | 0.8245 | **0.8977** ← 最高 | 0.8711 | ❌ 180° |
| fe208988…（实际 `cos 90°`） | **0.8772** | 0.8609 | 0.7473 | **0.9119** ← 最高 | ❌ 270° |

**结论**：`score` **不能**作为方向选择的可靠依据。当所有方向得分都偏低（0.83~0.91）时，
"取最高分"会选中错误旋转方向并返回错误结果。

已有的缓解手段与边界：

- **手机照片（带 EXIF 旋转）不受影响**：`photo_picture3.png`（EXIF=8）走单候选路径，0.42s 命中 0.9969。
- **正立且模型自信的图不受影响**：得 0.9996/1.0 的那些图，0° 首试即 ≥0.95 提前结束。
- **受影响场景**：无 EXIF + 模型对 0° 不够自信（<0.95）→ 会继续试其余方向，可能选中错误的。

> 改进方向（**尚未实施，需与需求方确认取舍**）：
> ① 0° 优先 + 要求非 0° 方向**领先 ≥0.05** 才旋转；
> ② 所有方向普遍偏低时返回 `status="ERROR"` 提示用户确认方向，而不是硬猜。
> 注意 `picture1.jpg` 是真需要 90° 的样本（0°=0.9040 垃圾 / 90°=0.9348 正确，**仅领先 0.031**），
> 所以任何"偏好 0°"的规则都必须明确它对这类图的代价。

### 置信度 vs 实际正确性（合并全部已标注样本）

| 样本组 | 数量 | 平均 score |
|---|---|---|
| 正确样本 | 14 | **0.9942** |
| **错误**样本 | 4 | **0.9221** |

错误样本的 score 全部落在 **0.89~0.95** 区间，与正确样本（普遍 >0.96）**有重叠**：
`7ec6aec8`（sin60° 误读）拿到 **0.9445**、`fe208988`（选错方向）**0.9119**、`0206eb24` **0.8977**。

**因此**：`confidence` 可用于**粗筛**（明显偏低时提示用户），但**不能**作为正确性判据；
若按 0.95 阈值过滤，上述错误样本会被当作"可信"放行。
`picture1.jpg`（score 0.9348 但上标读错）是手机照片侧的同类证据。

### 全程合并总表（权威数据，供报告直接引用）

把上述全部素材合并后的单一总表（20 个样本，含每张的尺寸/EXIF/候选数/选中角度/score/耗时/正确性）：

| | 数值 |
|---|---|
| 样本总数 | **20**（计入准确率 18；排除 2 个整页多公式样本） |
| **准确率** | **14/18 = 77.8%** |
| 正确样本 score | 0.9568 ~ 1.0（平均 0.9931） |
| 错误样本 score | 0.8977 ~ 0.9445（平均 0.9222） |
| 阈值检验（0.95） | 错误样本 **0/4** 会被放行 |
| 管线成功率 | 20/20 均返回了 `status`（无 5xx、无崩溃） |

完整逐行表格（Markdown，可直接贴报告）：
`EVIDENCE_模块一\final_report\accuracy_table_all.md`（JSON 原始数据同名 `.json`）

### 模型对比（报告"实验与结果分析"章的素材）

| 模型 | 结果 |
|---|---|
| pix2tex（旧方案） | 三张真实照片、累计 20+ 次推理**全部失败**。根因：权重停在 2021-10-28、`max_height=192`、训练分布只有 LaTeX 渲染截图 |
| **Pix2Text 1.1.7（现方案）** | 真实手写照片**识别成功**（`\cos\frac{\pi}{2}+1`，score 0.9969）。自带 MFD 公式检测，能先定位公式再识别 |

---

## 6. 测试（含给验收方 AI 的执行指南）

> 本节是**可以照着执行**的版本。如果你是接手验收的 AI：按 §6.1 判断走哪条路 → 跑 §6.2/§6.3 →
> 用 §6.4 判定 → 遇到 §6.6 的坑按对应解法处理 → 按 §6.7 回复结果。

### 6.1 先判断走哪条路

```
这个环境里 pip 能装东西吗？
├─ 能   → 路径 A：安装依赖，然后自检 + 跑测试        （验收方标准流程）
└─ 不能 → 路径 B：用已有的 venv 解释器（仅开发机上存在）
```

**无论哪条路，先确认解释器版本是 3.12 左右**（判断方法见 §6.6 坑 1）。

**路径 A（推荐）**

```bash
cd <交付文件夹>
pip install -r requirements.txt      # 约 1~3 分钟
pip install pix2text                 # ⚠️ 必须补装，见 §0 与 §6.6 坑 2
python selfcheck.py                  # 一键自检
pytest tests/test_recognition.py -v  # 完整测试
```

**路径 B（开发机上有现成 venv）**

```powershell
& "<项目>\server\.venv\Scripts\python.exe" selfcheck.py
& "<项目>\server\.venv\Scripts\python.exe" -m pytest tests/test_recognition.py -v
```

**期望结果（实测基线 2026-10-06，Windows / Python 3.12.2）**

| 步骤 | 期望输出 | 退出码 |
|---|---|---|
| `python selfcheck.py` | 逐项 `[PASS]`，结尾 `自检结果：22/22 项通过` | `0` |
| `pytest tests/test_recognition.py -v` | **36 passed**（约 2 分钟） | `0` |

**`selfcheck.py` 退出码语义**：`0` = 全通过；`1` = 有检查项失败（**可能是真问题**）；
`2` = **缺前置依赖**（环境问题，不是代码问题）。

### 6.2 一键自检 `selfcheck.py` 检查什么（22 项）

**不需要启动服务、不依赖外部文件**，用 FastAPI `TestClient` 在进程内直接打接口。

| 组 | 检查内容 | 对应 `ALL.md` |
|---|---|---|
| 一、环境 | Python ≥3.10；fastapi / starlette / pydantic / PIL / **pix2text** / pytest 能否导入 | — |
| 二、契约 | `common/models.py`、`common/vocab.py`、`main.py` 的 **SHA256 是否与组长锁定版逐字一致** | 全局契约 |
| 三、接口 | `/health` 返回 `{"status":"ok"}`；`/recognize` 返回合法 JSON、`latex` 非空、`confidence ∈ [0,1]`、`tokens` 保留为空列表、响应头带 `X-Recognition-Meta` | **M1-1 ~ M1-4、M1-7** |
| 四、错误场景 | 空图 / 非法 Base64 → **200 + `status="ERROR"`**；缺 `image` → **422** | 红牌项 2/3 |
| 五、独立性 | 未加载 `app.calculation`、未加载 `app.main`、源码无违规 import | **M1-6** |

第六节只打印**信息项**：`app.main` 当前不可导入是**正常的**（见 §6.6 坑 3）。

### 6.3 pytest 完整测试

```bash
cd <交付文件夹>
pytest tests/test_recognition.py -v
```

**实测结果：36 passed**（约 2 分钟，含模型加载与多次推理）。

其中针对真实照片的回归测试，素材**已随包携带**，因此验收方离线也能跑出完整覆盖（0 skipped）：
- `picture1.jpg`（EXIF=0）→ 验证「EXIF=0 不等于方向可信」与「低置信度降级为 ERROR」
- `picture2.jpg`（整页多公式）→ 验证多公式走 ERROR 通道
- `photo_picture3.png`（EXIF=8）→ 验证 EXIF 归正链路

> 若在**无网络**的机器上首次运行，会先尝试下载模型权重（约 230 MB）而失败 —— 请先联网跑一次。

### 6.4 `ALL.md`「模块 1 查验对照单」逐项结果

| # | 查验项 | 怎么验 | 本包实测 |
|---|---|---|---|
| M1-1 | `/health` 可访问 | `selfcheck.py` 第三节 | ✅ 200 `{"status":"ok"}` |
| M1-2 | `/recognize` 返回合法 JSON | `selfcheck.py` 第三节 | ✅ |
| M1-3 | `latex` 非空字符串 | `selfcheck.py` 第三节 | ✅ `\frac{\pi} {2}` |
| M1-4 | `confidence ∈ [0,1]` | `selfcheck.py` 第三节 | ✅ 0.9997 |
| M1-5 | 独立测试通过 | `pytest tests/test_recognition.py` | ✅ 36 passed |
| M1-6 | 不依赖模块 2 | `selfcheck.py` 第五节（新进程验证） | ✅ 未加载 `app.calculation` / `app.main` |
| M1-7 | 预留字段未删 | `selfcheck.py` 第三节 | ✅ `tokens: []` |

### 6.5 联调时怎么读结果

`POST /recognize` 响应字段（契约见 `ALL.md`，**不得增删**）：
`latex` / `confidence` / `tokens` / `status` / `message`。
诊断信息（试过哪些旋转方向、各自 score 与耗时）走**响应头 `X-Recognition-Meta`**，不进 JSON。

| 返回 | 含义 |
|---|---|
| `SUCCESS` | 拿到 LaTeX。**但仍需肉眼核对**：实测 19 个标注样本准确率 **15/19 ≈ 78.9%**，典型错误是字符级误读（上标 `n`→`3 3`、数字 `0`→字母 `o`） |
| `ERROR` + `reason=empty` | 模型没读出任何公式（图里可能没公式，或公式过小） |
| `ERROR` + `reason=multiline` | 读出的是**多行/多公式结构** → 当前只支持单一公式（C3；E7 未实现）。需框选单个公式 |
| `ERROR` + `reason=low_confidence` | **置信度低于门槛 0.95，被主动拒绝**（设计行为，不是崩溃），详见 §5 与 §6.6 |
| `ERROR` + `reason=unexpected_error` | 任何未预期异常都被兜底成 200 + ERROR，**绝不返回 5xx**（红牌项 2/3） |

**`confidence` 的正确用法**（实测 22 样本：正确 15 个 score 0.9568~1.0；错误 4 个 0.8977~0.9445）：
可拿 `< 0.95` 做**初步提示**，但两组间距只有 0.012（样本量 19），**必须保留人工修正闭环**（题目 C7），
不能当作正确性判据。详见 §5「置信度 vs 实际正确性」。

### 6.6 已知坑（按踩到的概率排序）

#### 坑 1：`ModuleNotFoundError: No module named 'fastapi'`

**这几乎总是用错了解释器，不是代码问题。**

实测案例：在装了 conda 的机器上敲 `python selfcheck.py`，走的是 conda base 的 Python（实测遇到过
**3.14.7**），里面没有本模块依赖。典型症状是**环境组大量 FAIL、但第二组「契约文件一致」三项全 PASS**
（因为契约比对是纯 SHA256 计算，不需要任何第三方库）。

**判断方法**：看自检输出第一行「Python 版本」，以及 FAIL 项附带的「当前解释器」完整路径。
本项目验证环境是 **3.12.2**。自检脚本在缺关键依赖时会打印解释器路径并退出码 `2`，**不会抛 traceback**。

**解法**：`pip install -r requirements.txt`（路径 A），或换用 venv 解释器（路径 B）。

#### 坑 2：`requirements.txt` 里没有 `pix2text`

该文件属**组长锁定只读**，成员 1 不能改，但本模块使用的模型是 **Pix2Text 1.1.7**
（`hmer_cs_1.md` 里写的 pix2tex 已弃用，原因见 §5 模型对比）。
**后果**：只跑 `pip install -r requirements.txt` 后，模块一 `import pix2text` 会失败。
**解法**：`pip install pix2text`。**请把这条缺失反馈给组长补进 `requirements.txt`。**

#### 坑 3：`import app.main` 失败 —— 这是正常的

```
ModuleNotFoundError: No module named 'app.calculation.router'
```

`app/main.py` 是组长骨架，同时 import **模块一（识别）**与**模块二（计算）**两个 router。
**模块二尚未交付**，所以整体启动必然失败 —— 这是 `server/README.md` §五 写明的骨架正常状态，
**不是模块一的缺陷**。因此验收模块一时：

- **不要**用 `uvicorn app.main:app`；
- 用 `selfcheck.py`（进程内测试），或 §2.1 的临时入口只挂模块一 router。

#### 坑 4：第一次请求要等 30~60 秒

模型**每遇到一种新的图片尺寸**，第一次推理会异常慢（实测 **32~57 秒**），之后同尺寸降到 **0.4~2 秒**。
这不是卡死，也**不是权重下载**造成的（权重已缓存时同样发生）。
**给联调方的建议**：Android 端超时设 **≥60 秒**，或在 App 启动时先预热一次。

#### 坑 5：首次运行需要联网下载模型权重

约 230 MB，缓存在 `%APPDATA%\pix2text`（Windows）。**干净机器首次必须联网**，之后离线可跑。
缓存路径随用户名变化，不要写死。

### 6.7 验收方需要回什么

1. `python selfcheck.py` 的**完整输出**与**退出码**；
2. `pytest tests/test_recognition.py -v` 的**结尾统计**（`N passed`）；
3. 若失败：贴出失败项、当前解释器路径与版本，以及
   `pip list | findstr -i "fastapi pix2text pillow"` 的结果；
4. 坑 2（`requirements.txt` 缺 `pix2text`）请反馈给组长。

### 6.8 验收时不要做的事

- ❌ 不要用 `uvicorn app.main:app` 验收模块一（模块二未交付，必然 ImportError，见坑 3）；
- ❌ 不要修改 `common/models.py`、`common/vocab.py`、`main.py`（组长锁定契约，
  `selfcheck.py` 会用 SHA256 检出一字之差）；
- ❌ 不要给响应加字段（`ALL.md` §六 红牌项：契约必须一致）；
- ❌ 不要把 `confidence` 当正确性判据直接放行结果（见 §5）；
- ❌ 不要因为首次请求慢就判定超时失败（见坑 4）。

---

## 7. 本包内容与"没有放什么"

已放（24 个文件，约 0.39 MB）：

```
selfcheck.py              一键自检脚本（22 项，见 §6.2）
README.md                 本文件（§6 是给验收方 AI 的可执行测试指南）
app/                     后端代码（recognition/ 为模块一实现）
  common/models.py       ★ 契约，与组长锁定版逐字一致（SHA256 在 §6.2 说明其校验方式）
  common/vocab.py        ★ 契约，逐字一致
  main.py                组长锁定入口
  calculation/           模块二占位（只有 __init__.py，待成员 2 交付）
  recognition/           模块一实现：router.py / recognizer.py / preprocess.py
tests/test_recognition.py   模块一独立测试（36 passed）
tests/fixtures/           测试素材 7 张：
    formula_1/2/3.png     印刷体公式渲染图（matplotlib 渲染，结论确定）
    photo_picture3.png    真实手写照片，保留 EXIF 方向=8（验证 EXIF 归正链路）
    picture1.jpg          真实手写照片（EXIF=0），两个回归测试依赖它
    picture2.jpg          真实手写照片（整页多公式），多公式 ERROR 通道测试依赖它
    picture4.jpg          真实手写照片（竖幅、无 EXIF、需 90°旋转，内容 2x+5）
requirements.txt  conftest.py  .gitignore
```

> ⚠️ **本包不应含** `__pycache__/` 与 `*.pyc`（`DELIVERY.md` §五 要求排除）。
> 在包内直接跑过 `pytest` / `python` 就会生成它们 —— 打包前请清理一次。
> 用 `python -B` 运行可避免生成字节码。

**没有放**（按 `DELIVERY.md` §五）：`.venv/`（实测 **1,807.6 MB / 48,884 个文件**）、`__pycache__/`、`*.pyc`、
模型权重文件（230 MB，首次运行自动下载）、`.git/`。

---

## 8. 现状与待办（截至本包生成）

- [x] 模块一三个实现文件 + 独立测试
- [x] `/health`、`/recognize` 真实 HTTP 验证通过（`ALL.md` M1-1~M1-7 全绿）
- [ ] **模块二 `app/calculation/`（待成员 2 交付）** → 交付后 `uvicorn app.main:app` 即可整体启动
- [ ] **`requirements.txt` 补 `pix2text`（待组长）** —— 见 §0
- [ ] 交付说明 §3.3 `/calculate` 的自测返回（待模块二）

---

# 9. 整合指南（模块 2 负责人专用）

> 目标：把**模块一（识别）**与**模块二（计算）**合进组长锁定的骨架仓库，得到一个
> `uvicorn app.main:app` 能启动、`pytest` 全绿、可直接对接 Android（模块 3）的后端。
> 全程只需要你动**一个文件**（`requirements.txt`），其余都是"复制 + 不碰"。

## 9.1 第一步：复制哪些文件

把本包下列内容复制进**组长锁定的骨架仓库**（你手上应该已经有一份）：

| 从本包复制 | 到骨架仓库 | 说明 |
|---|---|---|
| `app/recognition/`（整个目录：`__init__.py` + `router.py` + `recognizer.py` + `preprocess.py`） | `server/app/recognition/` | **模块一全部实现**，覆盖同名目录即可 |
| `tests/test_recognition.py` | `server/tests/test_recognition.py` | 模块一独立测试（36 个用例） |
| `tests/fixtures/` 下 7 张图 | `server/tests/fixtures/` | 测试素材，**必须带**，否则 4 个回归测试会 skip |
| `selfcheck.py` | `server/`（或交付文件夹根） | 一键自检，**建议留给组长做验收** |

**如果你是把两个模块打包成一个交付文件夹给组长**（`DELIVERY.md` §一 要求的 5 件交付物），
那么 `app/`、`tests/`、`requirements.txt`、`conftest.py`、`.gitignore` 取**骨架版本 + 两个模块目录**，
不要用本包自带的 `app/common/`、`app/main.py`（见 §9.3，它们只是为了让本包能独立自检）。

## 9.2 第二步：改 `requirements.txt`（**唯一需要你动的文件**）

在组长锁定的 `requirements.txt` 里**加一行 `pix2text`**：

```diff
  pix2tex
+ pix2text
  latex2sympy2
  sympy
  fastapi
  uvicorn
  pydantic
  pillow
  pytest
  httpx
```

**为什么必须加**：模块一用的识别模型是 **Pix2Text 1.1.7**（`hmer_cs_1.md` 里写的 pix2tex 已弃用，
原因见 §5「模型对比」：pix2tex 在三张真实手写照片上累计 20+ 次推理全部失败）。
`requirements.txt` 是组长锁定只读，**我（成员 1）不能改**，所以留给你整合时一起处理。

**安装 `pix2text` 会带来的版本变化（请知情）**：

| 包 | 变化 | 影响 |
|---|---|---|
| `transformers` | 5.x → **4.57.x**（降级） | 已验证 `pix2tex` 仍可正常导入（其要求 `>=4.18.0`），不影响模块二 |
| `huggingface_hub` / `tokenizers` | 小幅降级 | 无观察到影响 |
| `opencv-python` | 新增 | 与 `pix2tex` 要的 `opencv-python-headless` **并存**，两者抢同一个 `cv2` 模块；实测导入正常、功能无碍，但要知道这个状态"脏" |
| `onnxruntime`、`numpy`、`matplotlib` 等 | 新增 | 无冲突 |

**`pix2tex` 请保留不要删** —— 它依赖的 `latex2sympy2` + `sympy` 是**模块二的核心**，
而且 pix2tex 本身是报告里模型对比实验的基线。

> **【组长回执 2026-10-04 · 采纳相反意见】** 组长按「方案 A」：`pix2tex` 已从 `requirements.txt` 移除。
> 理由：① `latex2sympy2`/`sympy` 在 requirements 里本就单独列出，删 pix2tex 不影响模块二；② 对比实验已完成，报告照写无需重装；③ 保留会拉 torch、降级 transformers、opencv 并存（脏状态）。

## 9.3 第三步：这些文件**一个字都不能动**

`ALL.md` §六 红牌项 1：契约文件被成员私自改动、三方不一致 → 整包退回。
整合后请用 SHA256 核对（`selfcheck.py` 会自动做这件事）：

| 文件 | 期望 SHA256（uppercase） |
|---|---|
| `app/common/models.py` | `90701FB20161C0D2264DC371247F71F696D84EAD869F1EBAC5017E6CD21F2444` |
| `app/common/vocab.py` | `89D56C5C9E2CB7C92D29EC093BA2B3B3DBAA6D2BB75164D4D0D79B12379A9598` |
| `app/main.py` | `BEE9E9AC23D32BA8E3E0F24394B1E08BFCA8729CADB26DB72D6A0791638DFF2E` |

```powershell
# 核对命令
Get-FileHash server\app\common\models.py, server\app\common\vocab.py, server\app\main.py -Algorithm SHA256 |
  Select-Object Path, Hash
```

另外**不要改**：`conftest.py`、`app/**/__init__.py`、`.gitignore`（都是骨架必需，删了会导致
`ModuleNotFoundError: No module named 'app'` 或 pytest 找不到模块）。

**契约内容速览**（`ALL.md` §一 的金标准，勿增删字段）：

```python
# app/common/models.py
class RecognizeRequest(BaseModel):  image: str
class Token(BaseModel):             text: str; confidence: float; range_start: int; range_end: int; alternatives: List[str] = []
class RecognitionResponse(BaseModel): latex: str; confidence: float; tokens: List[Token] = []; status: str = "SUCCESS"; message: Optional[str] = None
class CalculateRequest(BaseModel):  latex: str; mode: str = "deg"
class CalculateResponse(BaseModel): latex: str; value: Optional[float] = None; value_latex: Optional[str] = None; status: str; message: Optional[str] = None

# app/common/vocab.py
PLUS, MINUS = "+", "-"
TIMES, DIV = "\\times", "\\div"      # 兼容 \cdot
FRAC, SQRT, POW = "\\frac", "\\sqrt", "^"
TRIG = {"\\sin", "\\cos", "\\tan"}
PI, E = "\\pi", "e"
DIGITS = "0123456789"
PARENS = "()"
```

## 9.4 第四步：整合后怎么验证

```bash
cd <骨架仓库>/server

# 1) 整体启动（模块二就位后这条才通；这是模块一交付时唯一做不到的事）
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 2) 存活 + 两个接口
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/recognize -H "Content-Type: application/json" -d "{\"image\":\"<base64>\"}"
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" -d "{\"latex\":\"1+2*3\",\"mode\":\"deg\"}"

# 3) 全部测试（模块一 36 个 + 模块二自己的）
pytest -v

# 4) 契约与接口自检
python selfcheck.py      # 期望：自检结果：22/22 项通过（退出码 0）
```

**验收基线**（实测 2026-10-06，Windows / Python 3.12.2）：

| 项 | 期望 |
|---|---|
| `python selfcheck.py` | `22/22 项通过`，退出码 `0` |
| `pytest tests/test_recognition.py` | `36 passed`（约 2 分钟） |
| `GET /health` | `{"status":"ok"}` |
| `POST /recognize`（`tests/fixtures/formula_2.png`） | `{"latex":"\\frac{\\pi} {2}","confidence":0.99975,...,"status":"SUCCESS"}` |

## 9.5 整合时最容易踩的 5 个坑

### 坑 1：模块一代码"看起来多余"的 `common/` 副本

本包里带了一份 `app/common/models.py`、`app/common/vocab.py`、`app/main.py` —— 那是**为了让本包能独立自检**
（`selfcheck.py` 需要完整可导入的包结构）。**整合时以骨架版本为准**，只要 SHA256 一致就说明没有分叉。
若不一致，**先停下来问组长**，不要自行合并。

### 坑 2：把 `pix2text` 漏了（最常见）

只装 `requirements.txt` 而不加 `pix2text` → 模块一 `import pix2text` 直接失败，
表现为后端启动即崩。症状与解法见 §0 与 §6.6 坑 2。

### 坑 3：用错 Python 解释器

本项目需要 **Python 3.12**（3.14 上 scipy 等包没有可用 wheel，无法解析依赖；
实测还遇到过在 conda base 3.14 上跑自检、环境组全 FAIL 的情况）。症状与判断方法见 §6.6 坑 1。

### 坑 4：第一次识别请求要等 30~60 秒

模型**每遇到一种新的图片尺寸**，第一次推理实测 **32~57 秒**，之后同尺寸降到 **0.4~2 秒**。
这不是卡死，也**不是下载权重**造成的。**务必让模块 3 把 Android 端超时设到 ≥60 秒**，
或在 App 启动时先预热一次 —— 否则模块 3 联调时会误判成"后端挂了"。

### 坑 5：把 `confidence` 当成"识别正确"的判据

实测 22 个标注样本：正确样本 score 0.9568~1.0，错误样本 0.8977~0.9445，**两组间距只有 0.012**。
模块一已实现 **`MIN_ACCEPTABLE_SCORE = 0.95`** 门槛：所有候选方向最高分 < 0.95 时**不返回结果**，
改为 `status="ERROR"` + `message` 提示用户确认方向。**模块二/模块三不要依赖 confidence 做自动放行**，
必须保留题目 C7 的手动修正闭环。

## 9.6 模块一对外的接口契约（模块二/模块三对接用）

| 接口 | 请求 | 响应 |
|---|---|---|
| `GET /health` | — | `{"status": "ok"}` |
| `POST /recognize` | `{"image": "<base64，JPEG/PNG 字节，不带 data: 前缀>"}` | `RecognitionResponse` |

**响应字段固定 5 个**（`latex` / `confidence` / `tokens` / `status` / `message`），**不得增删**。
诊断信息（试过哪些旋转方向、各自 score 与耗时）走**响应头 `X-Recognition-Meta`**，不在 JSON 里。

**`status` 与失败语义**（模块二/模块三按这个分支，不要靠 HTTP 码判断业务失败）：

| 值 | 含义 | 调用方该做什么 |
|---|---|---|
| `SUCCESS` | 有结果。**识别准确率实测 15/19 ≈ 78.9%**，仍需用户核对 | 展示 `latex`，允许用户编辑后送 `/calculate` |
| `ERROR` | 无结果，看 `message` 与响应头 `reason` | 展示 `message` 给用户；`reason` 取值 `empty` / `multiline` / `low_confidence` / `decode_error` / `unexpected_error` |

**接口无状态**：可被连续调用（对应 `server/README.md` §四 的 B4 实时流式余量）。

## 9.7 模块二可以复用的预留口子

`server/README.md` §四 约定的换模型口子在这里：

- `app/recognition/recognizer.py` 的 **`Recognizer` 类** —— 换自训模型（B2）只改这一个类，
  契约字段与 router 都不用动。它的 `__init__` 接受 `engine` 参数，便于注入替身做测试。
- `confidence` 门槛常量 `MIN_ACCEPTABLE_SCORE`（同文件），调整门槛不需要动 router。

## 9.8 我这边已完成 / 未完成的边界（交接声明）

**已完成**：
- `app/recognition/` 三个实现文件 + `tests/test_recognition.py`（36 passed）
- `selfcheck.py` 一键自检 22 项（含契约 SHA256 校验）
- `/health`、`/recognize` 真实 uvicorn + curl 验证；手机热点联调已跑通
- `pytest` 36 passed / 0 skipped（素材随包携带，离线可跑）

**未完成 / 需你接手**：
- **模块二 `app/calculation/` 本身**（你的部分）
- **`requirements.txt` 加 `pix2text`**（§9.2）—— ✅ 组长已处理（方案 A：pix2tex 移除、只留 pix2text）
- `DELIVERY.md` §三 要求的交付说明中 **§3.3 `/calculate` 的自测真实返回**（等模块二就位后补）
- 打包成 `DELIVERY.md` §一 要求的**单一交付文件夹**（整合后一次做，记得排除 `.venv/`、`__pycache__/`、模型权重）
- 文档层面：`hmer_cs_1.md` 全文仍写 pix2tex、`ALL.md` 契约基准仍是 pix2tex 措辞 ——
  **属组长维护的文档，我未改动**，建议由组长统一更新以免报告与实现不一致。
  **✅ 组长已处理 2026-10-04**：`hmer_cs_1.md`、`ALL.md` 已统一改为 pix2text（含换模型说明与 4 个识别加固语义）。
