# DELIVERY.md —— 模块 1+2 后端交付约定（成员 1 打包 / 组长验收）

> 用途：成员 1 把「模块 1（识别）+ 模块 2（计算）」合并、跑通、自测后，打包成**一个文件夹**交给组长。
> 对象：成员 1（打包方）＋ 组长（接收方）。全局契约以同目录 `ALL.md` 为准。
> **核心目标：让组长拿到手就能——读得懂、装得起、跑得通、直接对接模块 3（Android）。**

---

## 一、必须交给组长的东西（★ = 少一样就退回）

- ★ 1. **后端代码**：一个能启动的 FastAPI 项目，`/health`、`/recognize`、`/calculate` 三个接口都在、都能调通。
- ★ 2. **依赖清单**：`requirements.txt`（一个或拆成多个都行），组长 `pip install` 后能装齐**两个模块**的全部依赖（pix2tex、latex2sympy2、sympy、fastapi、uvicorn、pydantic、pillow 等）。
- ★ 3. **契约文件**：`app/common/models.py` + `app/common/vocab.py`，与组长锁定的版本**逐字一致**（金标准，改了整包退回）。
- ★ 4. **一张测试图**：手写公式照片（如 `1+2`），组长拿来冒烟识别。
- ★ 5. **一份「交付说明 README」**：讲清下面 §三 的 4 件事。
- 6.（可选）测试脚本：有更好，没有就靠 §三 的 curl 自测结果证明。

> 一句话：**代码 + 依赖 + 契约 + 测试图 + 说明**，五样齐了就能收。

---

## 二、目录结构：参考，不要求逐字一致

```
（交付文件夹）/
├── README.md              ← 交付说明（§三 的 4 件事，必写）
├── app/
│   ├── main.py            ← 入口，挂两个 router
│   ├── common/
│   │   ├── models.py      ← ★ 契约，逐字一致
│   │   └── vocab.py       ← ★ 契约，逐字一致
│   ├── recognition/       ← 模块 1（router / recognizer / preprocess，文件名可自定）
│   └── calculation/       ← 模块 2（router / calculator，文件名可自定）
├── requirements.txt       ← 依赖（一个或多个都行）
├── sample1.png            ← ★ 测试图（放哪都行，README 里说明路径）
└── （可选）tests/         ← 测试脚本，不强制
```

**可以自己定的（不用逐字对齐）**：
- 文件怎么拆、叫什么名（`recognizer.py` / `preprocess.py` / `router.py` 是否分开，随你）。
- `requirements` 一个还是多个、叫什么名。
- 测试脚本写不写、叫什么名。
- 交付文件夹叫什么名（`server/` 还是别的）。

**不能动的**：`models.py` / `vocab.py` 的**字段**（和 `ALL.md` 契约基准逐字一致）。

> 组长只看三件事：**① 能不能起　② 接口通不通　③ 契约对不对**。这三样对了，其余怎么组织都行。

---

## 三、交付说明 README 必须写清的 4 件事（这就是"说清楚"）

1. **怎么装依赖**：`pip install -r requirements.txt`（给出确切的文件名 / 命令）。
2. **怎么启动**：`uvicorn app.main:app --host 0.0.0.0 --port 8000`（**`--host 0.0.0.0` 必须带**，否则手机连不上；Windows 防火墙需放行 8000）。
3. **三个接口各一条自测命令 + 真实返回**（贴出来，别只写"能跑"）：
   - `curl http://127.0.0.1:8000/health`
   - `curl -X POST .../recognize`（传 sample1.png 的 base64，无 `data:` 前缀）
   - `curl -X POST .../calculate`（如 `{"latex":"1+2*3","mode":"deg"}`）
4. **坑点**（组长对接模块 3 时最容易踩，务必写）：
   - 首次 `/recognize` 会**下载模型权重，慢（几秒到十几秒），需联网一次** → Android 端超时要给足。
   - 接口字段以 `ALL.md` 契约为准，**没有私自加字段**（尤其别在响应里自己加东西）。

---

## 四、交付前自查（自己先跑一遍，全过再发）

- [ ] `uvicorn app.main:app --host 0.0.0.0 --port 8000` 能启动
- [ ] `curl .../health` 返回 ok
- [ ] `/calculate` 传 `1+2*3` 返回正确数值、`status="SUCCESS"`
- [ ] `/recognize` 传 sample1.png 返回非空 `latex`（且符合词表）
- [ ] 非法输入不 500 崩溃：除零、坏图等都要有合理返回（`/calculate` 走 `PARSE_ERROR`/`COMPUTE_ERROR` + `message`；字段以契约为准）
- [ ] `models.py` / `vocab.py` 与组长锁定版逐字一致
- [ ] README 里 §三 的 4 件事都写了

---

## 五、绝不能放进文件夹的东西

- [ ] `.venv/`、`venv/`（组长自己 `pip install`）
- [ ] `__pycache__/`、`*.pyc`
- [ ] 模型权重文件（几百 MB，组长首次跑会自动下载）
- [ ] `.git/`

> 目的：文件夹要小、干净，组长拿到后自己装依赖、首次跑自动下权重即可。

---

## 六、组长拿到手就三步

```bash
pip install -r requirements.txt                      # 1. 装依赖
uvicorn app.main:app --host 0.0.0.0 --port 8000      # 2. 起服务
curl http://127.0.0.1:8000/health                    # 3. 冒烟
```

再按 README 里的 curl 命令把 `/recognize`、`/calculate` 各打一遍；通了就对齐 `ALL.md` 契约，直接接模块 3。

---

## 附：和 ALL.md 的关系

- `ALL.md` = 全局契约 + 三模块查验对照单；本文件 = **交付时点怎么打包、怎么让组长读懂跑通**。
- 契约字段有冲突时以 `ALL.md` 为准；本文件只讲"交付内容与方式"。
