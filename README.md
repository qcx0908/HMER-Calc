# HMER-Calc

手写体数学公式识别与计算系统 —— 拍一张手写公式的照片，自动转成 LaTeX 并算出数值结果。

基于 C/S 架构：手机（Android 客户端）拍照/选图，上传到电脑（FastAPI 后端）完成识别与计算，结果回显到手机。

## 功能

### 识别（图片 → LaTeX）

- 手写公式图片 → LaTeX 字符串 + 整体置信度（`confidence`）。
- 识别模型为 **pix2text**（P2T 的 MFR 数学公式识别模型，对手写体重训），基于 onnxruntime，CPU 即可运行。
- 加固语义：EXIF 方向归正 + 多方向竞优、低置信度墨迹裁剪重试、数字粘连修复（`48` 不被拆成 `4 8`）、数字/字母混淆纠正（`8→z`、`cos` 被拆成 `c o s` 等）。
- 置信度三档：`≥0.95` 正常返回；`0.55~0.95` 仍返回结果并提示「置信度偏低，请人工核对」；`<0.55` 判为失败。

### 计算（LaTeX → 数值）

- 四则运算、分数、幂、根号、π/e、三角函数（sin/cos/tan/cot/sec/csc）、反三角（arcsin/arccos/arctan）、对数、阶乘、求和、定积分。
- 角度模式三态：
  - `deg`：全部按角度制（`sin(30)` → 0.5）；
  - `rad`：全部按弧度制（`sin(pi)` → 0）；
  - `auto`：智能判断——三角参数是纯数字按角度，含 π/变量按弧度。
- 结果同时给出数值（`value`）与精确值 LaTeX（`value_latex`，如 `0.8333…` 对应 `\frac{5}{6}`）。

### 客户端（Android）

- 拍照 / 相册选图 → 识别 → 结果页 → 手动修正（所见即所得点选）→ 重算。
- 后端地址 App 内可配置、历史记录（最近 10 次，可回载）。

## 架构

```
Android 客户端（Kotlin + Compose + Hilt + Retrofit）
        │  HTTP / JSON
        ▼
FastAPI 后端（module_1_2/）
   ├─ /recognize  →  pix2text 识别
   ├─ /calculate →  latex2sympy2 + sympy 计算
   └─ /health    →  存活探测
```

| 目录 | 内容 |
|---|---|
| `module_1_2/` | 后端实际代码（识别 + 计算整合版），含 `pytest` 110 项 |
| `android/` | Android 客户端 |
| `instruction_cs/` | C/S 版需求与技术文档（`ALL.md` 为契约基准） |

## 接口设计

统一约定：

- 端口 **8000**，一个 FastAPI 进程挂两个 router。
- JSON 字段一律 **snake_case**（`value_latex`、`range_start`）。
- 业务错误返回 **HTTP 200 + `status` 字段**；仅请求体格式错误返回 4xx/422。

### GET /health

存活探测，返回固定结构，不加载模型。

```json
{"status": "ok"}
```

### POST /recognize

图片 Base64 → LaTeX + 置信度。

**请求** `RecognizeRequest`

| 字段 | 类型 | 说明 |
|---|---|---|
| `image` | string | JPEG/PNG 字节的 Base64，**无 `data:` URL 前缀** |

**响应** `RecognitionResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `latex` | string | 识别出的 LaTeX（pix2text 原始输出） |
| `confidence` | float | 整体置信度 ∈ [0,1] |
| `tokens` | list | 恒为 `[]`（Pix2Text 无 token 级输出，字段为 E3/E8 预留） |
| `status` | string | `"SUCCESS"` \| `"ERROR"` |
| `message` | string \| null | 失败原因或低置信度提示 |

**示例**

```bash
curl -X POST http://127.0.0.1:8000/recognize \
  -H "Content-Type: application/json" \
  -d '{"image":"<base64 无前缀>"}'
```

```json
{
  "latex": "48 \\div 6",
  "confidence": 0.996,
  "tokens": [],
  "status": "SUCCESS",
  "message": null
}
```

> 诊断信息（各候选方向与其 score）通过响应头 `X-Recognition-Meta` 暴露，不进入 JSON 契约体。

### POST /calculate

LaTeX → 数值结果。

**请求** `CalculateRequest`

| 字段 | 类型 | 说明 |
|---|---|---|
| `latex` | string | 待计算的 LaTeX |
| `mode` | string | `"deg"` \| `"rad"` \| `"auto"`，默认 `"deg"` |

**响应** `CalculateResponse`

| 字段 | 类型 | 说明 |
|---|---|---|
| `latex` | string | 原样回显输入的 LaTeX |
| `value` | float \| null | 数值结果 |
| `value_latex` | string \| null | 结果的精确值 LaTeX（非纯数值时为 `null`） |
| `status` | string | `"SUCCESS"` \| `"PARSE_ERROR"` \| `"COMPUTE_ERROR"` |
| `message` | string \| null | 错误说明 |

**示例**

```bash
curl -X POST http://127.0.0.1:8000/calculate \
  -H "Content-Type: application/json" \
  -d '{"latex":"48 \\div 6","mode":"deg"}'
```

```json
{
  "latex": "48 \\div 6",
  "value": 8.0,
  "value_latex": "8",
  "status": "SUCCESS",
  "message": null
}
```

## 快速开始

```bash
cd module_1_2
pip install -r requirements.txt        # 建议先 pip install "pip==24.0"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 自测：浏览器打开 <http://127.0.0.1:8000/health>，应返回 `{"status":"ok"}`。
- 全量测试：`python -m pytest tests/ -q`（110 项通过）。
- 首次识别会自动下载模型权重（约 230MB，需联网一次）。
- Android 客户端用 Android Studio 打开 `android/`，模拟器默认后端地址 `http://10.0.2.2:8000`。

> 真机部署、联网配置与常见坑详见 `instruction_cs/` 与 `hmer.md`。
