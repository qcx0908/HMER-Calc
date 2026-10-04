# server/ —— 后端仓库骨架说明 + 协同约束（成员 1 / 2 必读）

> 本文件就是 `ALL.md`「零、分工与合并约定」里说的**组长锁定的仓库骨架**说明书。
> 拿到骨架后先读本文件，再看你自己的模块文档（成员 1 = `hmer_cs_1.md`，成员 2 = `hmer_cs_2.md`）。
> 本文件只补两件模块文档没写清、却会直接影响合库的事：**组长对骨架做的改动** 和 **两边必须对齐的铁律**。

## 一、目录与归属（谁能动什么）

| 路径 | 归属 | 你能否改 |
|---|---|---|
| `app/main.py` | 组长锁定 | ❌ 只读 |
| `app/common/models.py` | 组长锁定（契约） | ❌ 只读，一字不改 |
| `app/common/vocab.py` | 组长锁定（契约） | ❌ 只读，一字不改 |
| `app/**/__init__.py` | 组长（包标记） | ❌ 勿删 |
| `app/recognition/` | 成员 1 | ✅ 只在这里写 |
| `app/calculation/` | 成员 2 | ✅ 只在这里写 |
| `tests/test_recognition.py` | 成员 1 | ✅ |
| `tests/test_calculation.py` | 成员 2 | ✅ |
| `requirements.txt` | 组长 | ❌ 别自己加依赖 |
| `conftest.py` | 组长 | ❌ 勿删 |
| `.gitignore` | 组长 | ❌ 勿删 |

## 二、组长相对模块文档做的改动（你的 AI 读到这就能明白）

1. **加了 4 个空的 `__init__.py`**（`app/`、`app/common/`、`app/recognition/`、`app/calculation/` 下各一个）。
   为什么：让 `from app.recognition.router import router` 这类导入按「普通包」正常工作。模块文档的目录树没画它们，但**没有它们，测试会报 `ModuleNotFoundError: No module named 'app'`**。别删。
2. **加了 `conftest.py`**。为什么：让 pytest 自动把 `server/` 加进 `sys.path`，测试里的 `from app...` 才导入得到。别删。
3. **加了 `.gitignore`**。为什么：防止 `.venv/`、`__pycache__/`、模型权重被误提交进 git。
4. **`main.py` 里没有 `/health`**：`/health` 归成员 1，写在 `recognition/router.py`（见下第 4 条）。

## 三、协同铁律（两边都照做，才合得上）

1. **各写各的目录**：成员 1 只动 `recognition/` + `tests/test_recognition.py`；成员 2 只动 `calculation/` + `tests/test_calculation.py`。互不碰对方目录，也别碰 `common/`、`main.py`。
2. **router 变量必须叫 `router`**：你的 `router.py` 里写 `router = APIRouter()`，变量名就一个 `router`。`main.py` 按这个名字 import，改名 → import 失败 → 整库起不来。
3. **路由路径写全路径、不带前缀**：成员 1 写 `POST /recognize`；成员 2 写 `POST /calculate`。（`main.py` 挂载时没有 prefix。）
4. **`GET /health` 归成员 1**：写在 `recognition/router.py`，返回 `{"status": "ok"}`。这是 `ALL.md` 的 M1-1 查验项；`main.py` 里没有，别去 main.py 找或加。
5. **测试只测自己、别 import main.py**：各自 `FastAPI()` 只挂自己的 router（照 `hmer_cs_1.md` / `hmer_cs_2.md` §9 的写法）。`main.py` 在两边都交付前 import 会报错，**这是正常的，不是骨架坏了**。
6. **依赖共享**：统一 `pip install -r requirements.txt`，别自己再建 requirements 或加包。

## 四、E / B 拓展余量（骨架已预留，字段别删、结构别写死）

骨架靠「契约字段」+「类封装结构」给日后拓展留余量，**现在不用实现**：

| 预留点 | 在哪 | 对应日后功能 |
|---|---|---|
| `Token.alternatives` / `confidence` / `range_*` | models.py | E3 候选推荐 / E8 低置信度高亮 |
| `RecognitionResponse.tokens` | models.py | E3 / E8 |
| `CalculateResponse.value_latex` | models.py | E7 结果格式化 |
| `CalculateRequest.mode`（deg/rad） | models.py | E6 模式切换 |
| `recognizer.py` 里的 `Recognizer` 类 | recognition/ | B2 换自训模型只改这一个类 |
| `calculator.py` 里的 `Calculator` 类 | calculation/ | 计算逻辑换实现 |
| 接口无状态 | 两个 router | B4 实时流式（可连续调 `/recognize`） |

> 说明：E1 历史记录、B1 端侧部署、B5 端云协同是 **Android 端**的余量（见 `hmer_cs_3.md` §5），后端骨架不涉及，成员 1/2 不用管。

## 五、骨架现在的状态

- 现在 `uvicorn app.main:app --host 0.0.0.0 --port 8000` 会报 ImportError，因为 `recognition/router.py`、`calculation/router.py` 还没写。
- 成员各自跑测试用「独立 FastAPI 只挂自己的 router」，不需要 main.py。
- 等两边都交付、把 `recognition/` 和 `calculation/` 拷回这份骨架后，`main.py` 两行 import 就通，`pytest` 全绿即交付组长。
