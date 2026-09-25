# DELIVERY.md —— 后端交付文件夹约定

> 用途：成员 1 收集「模块 1 + 模块 2」、合并、跑通测试后，打包成**一个文件夹**交给组长。
> 本文件约定这个文件夹里该有什么、处于什么状态、什么不能有。
> 对象：成员 1（打包方）＋ 组长（接收方）。全局契约以同目录 `ALL.md` 为准。

---

## 一、交付物：一个文件夹，内部结构必须如下

```
server/                          ← 交付的就是这个文件夹（名可用 server 或其它，内部结构必须一致）
├── app/
│   ├── main.py                  # FastAPI 入口，挂 recognition_router + calculation_router
│   ├── common/
│   │   ├── models.py            # 契约模型（= 组长锁定的版本，一字不改）
│   │   └── vocab.py             # 词表（= 组长锁定的版本，一字不改）
│   ├── recognition/             # 模块 1
│   │   ├── router.py            # POST /recognize
│   │   ├── recognizer.py        # pix2tex 封装
│   │   └── preprocess.py        # base64→PIL + 可选裁剪
│   └── calculation/             # 模块 2
│       ├── router.py            # POST /calculate
│       └── calculator.py        # latex2sympy2 + sympy
├── tests/
│   ├── fixtures/
│   │   └── sample1.png          # 一张手写公式测试图（组长用它冒烟识别）
│   ├── test_recognition.py      # 模块 1 独立测试
│   ├── test_calculation.py      # 模块 2 独立测试
│   └── test_integration.py      # 1+2 联合测试（成员 1 负责写通）
├── requirements-recognition.txt # 模块 1 依赖（pix2tex/torch 等）
├── requirements-calculation.txt # 模块 2 依赖（无 torch）
└── .gitignore                   # 至少忽略 __pycache__/ .venv/ 模型权重 *.pyc
```

---

## 二、交付前必须自查（任何一项不满足，退回重做）

- [ ] `cd server && pytest tests/` 三个测试文件**全绿**
- [ ] `uvicorn app.main:app --host 0.0.0.0 --port 8000` 能正常启动
- [ ] `curl http://127.0.0.1:8000/health` 返回 ok
- [ ] `/calculate` 传合法 latex（如 `\frac{1}{2}`）返回 `status="SUCCESS"` 且 `value` 正确
- [ ] `/recognize` 传 `tests/fixtures/sample1.png` 返回非空 `latex`
- [ ] 非法输入不 500：除零、坏图 → 返回 `status="PARSE_ERROR"`/`"COMPUTE_ERROR"`/`"ERROR"` + `message`
- [ ] 每个包目录（`app/`、`app/common/`、`app/recognition/`、`app/calculation/`）都有空的 `__init__.py`
- [ ] `app/common/models.py`、`app/common/vocab.py` 与组长锁定的版本**逐字一致**（没被私自改）

---

## 三、绝不能放进文件夹的东西

- [ ] 虚拟环境 `.venv/`、`venv/`（组长拿到后自己 `pip install`）
- [ ] `__pycache__/`、`*.pyc`（运行生成的缓存）
- [ ] 模型权重文件（pix2tex 下载的大文件，几百 MB；组长首次跑会自动下载）
- [ ] `.git/`（除非双方约定用同一个 git 仓库，否则打包成纯文件夹）

> 目的：文件夹要小、要干净，组长拿到后自己装依赖、首次跑自动下权重即可。

---

## 四、组长收到后怎么验（就这几条命令）

```bash
pip install -r requirements-recognition.txt
pip install -r requirements-calculation.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

另开一个终端：

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/calculate -H "Content-Type: application/json" \
  -d '{"latex":"1+2*3","mode":"deg"}'
```

- `health` 返回 `{"status":"ok"}` ✅
- `calculate` 返回 `"value":7.0` ✅

分数/根号/三角等复杂样例不用手敲，`pytest tests/` 已经覆盖，能全绿即可。

---

## 五、联合测试 test_integration.py（成员 1 负责写，照抄即可）

```python
# tests/test_integration.py —— 1+2 联合测试：识别一张图 → 拿 latex → 喂给计算
import base64
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_end_to_end():
    img = open("tests/fixtures/sample1.png", "rb").read()
    r = client.post("/recognize", json={"image": base64.b64encode(img).decode()})
    assert r.status_code == 200
    assert r.json()["status"] == "SUCCESS"
    latex = r.json()["latex"]
    assert latex
    c = client.post("/calculate", json={"latex": latex, "mode": "deg"})
    assert c.status_code == 200
    assert c.json()["status"] in ("SUCCESS", "PARSE_ERROR", "COMPUTE_ERROR")
```

- `sample1.png` 用**一张清晰的手写算式照片**（如 `1+2`）。联合测试只断言"识别→计算全链路不崩"；若识别稳定，可再补一条 `assert abs(c.json()["value"] - 3.0) < 1e-9` 断言具体值。

---

## 附：和 ALL.md 的关系

- `ALL.md` = 全局契约 + 三模块查验对照单；本文件 = **交付时点的打包规范**。
- 打包前成员 1 对照本文件 §二 自查；交付后组长对照 §四 验收；有冲突以 `ALL.md` 为准。
