# -*- coding: utf-8 -*-
"""模块一交付自检脚本（组长一键验收用）。

用法（在交付文件夹下）：
    python selfcheck.py

它只做**只读检查 + 一次真实识别**，不改动任何文件，约 10~60 秒（首次要加载模型）。
检查项对应 `ALL.md`「模块 1 查验对照单」M1-1~M1-7，外加环境与契约一致性。

退出码：0 = 全部通过；1 = 有失败项（细节见输出）。
"""
from __future__ import annotations

import base64
import hashlib
import importlib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))  # 让 `from app...` 能导入（等价 conftest.py 的作用）

# Windows 控制台默认编码常为 GBK，中文会乱码；这里强制 UTF-8 输出。
for stream_name in ("stdout", "stderr"):
    stream = getattr(sys, stream_name, None)
    if stream is not None and hasattr(stream, "reconfigure"):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass

results: list[tuple[str, bool, str]] = []


def _version_of(module) -> str:
    """取可读版本号；pix2text 把 `__version__` 暴露成模块，需要再取一层。"""
    version = getattr(module, "__version__", None)
    if version is None:
        return "?"
    if isinstance(version, str):
        return version
    inner = getattr(version, "__version__", None)
    return inner if isinstance(inner, str) else type(version).__name__


def check(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, bool(ok), detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail else ""), flush=True)
    return bool(ok)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def section(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}", flush=True)


# ======================================================================================
section("一、环境")
# ======================================================================================
check("Python 版本 >= 3.10", sys.version_info >= (3, 10),
      f"实际 {sys.version.split()[0]}")

REQUIRED = ["fastapi", "starlette", "pydantic", "PIL", "pix2text", "pytest"]
#: 缺任何一个都无法继续做接口层检查（会 import 失败）
CRITICAL = ("fastapi", "starlette", "pydantic", "PIL", "pix2text")
missing: list[str] = []
optional_results = {}
for module_name in REQUIRED:
    try:
        module = importlib.import_module(module_name)
        optional_results[module_name] = _version_of(module)
        check(f"依赖 {module_name}", True, f"v{optional_results[module_name]}")
    except Exception as exc:  # noqa: BLE001
        missing.append(module_name)
        hint = ""
        if module_name == "pix2text":
            hint = "（不在 requirements.txt 中，见 README §0）"
        elif module_name == "pytest":
            hint = "（只在跑 pytest 时需要）"
        check(f"依赖 {module_name}", False,
              f"{type(exc).__name__}: {exc}｜当前解释器 {sys.executable} {hint}")

# 注：依赖缺失的**闸门**放在「二、契约」之后 —— 契约一致性是纯哈希比对，
# 不依赖任何第三方库，缺依赖时也应该照常给出结论（实测：3.14 环境里契约三项全 PASS）。

# ======================================================================================
section("二、契约文件与组长锁定版逐字一致")
# ======================================================================================
CONTRACT_SHA256 = {
    "app/common/models.py": "90701FB20161C0D2264DC371247F71F696D84EAD869F1EBAC5017E6CD21F2444",
    "app/common/vocab.py": "89D56C5C9E2CB7C92D29EC093BA2B3B3DBAA6D2BB75164D4D0D79B12379A9598",
    "app/main.py": "BEE9E9AC23D32BA8E3E0F24394B1E08BFCA8729CADB26DB72D6A0791638DFF2E",
}
for rel, expected in CONTRACT_SHA256.items():
    path = ROOT / rel
    if not path.exists():
        check(f"{rel} 存在", False, "文件缺失")
        continue
    actual = sha256(path)
    check(f"{rel} 与锁定版一致", actual == expected, f"{actual[:16]}…")

# ======================================================================================
section("三、接口层（TestClient，覆盖 ALL.md M1-1 ~ M1-4）")
# ======================================================================================
# 闸门：关键依赖缺失时**不能**硬 import（否则抛 traceback，看起来像代码坏了）。
# 实测踩过：有人用 conda base 的 Python 3.14 跑本脚本，pydantic 恰好自带、
# 其余全缺，于是崩在 `from fastapi import FastAPI` —— 场景一/二却全 PASS，容易误判。
critical_missing = [name for name in missing if name in CRITICAL]

if critical_missing:
    print("\n" + "=" * 72)
    print("无法继续：缺少关键依赖 " + "、".join(critical_missing))
    print("=" * 72)
    print(f"当前解释器：{sys.executable}")
    print(f"Python 版本：{sys.version.split()[0]}")
    print()
    print("这**不是代码坏了**，而是这个 Python 环境里没装本模块的依赖。请二选一：")
    print()
    print("  【A】用项目自带的 venv 解释器跑（开发机上推荐，依赖已就绪）")
    print(r'      & "D:\2026秋软件工程设计\成员1_模块一_识别\成员1_模块一_识别\server\.venv\Scripts\python.exe" selfcheck.py')
    print()
    print("  【B】在当前环境安装依赖（组长/验收方推荐）")
    print("      pip install -r requirements.txt")
    print("      pip install pix2text        # requirements.txt 中缺失，见 README §0")
    print()
    if missing:
        print("缺失清单：" + "、".join(missing))
    print()
    print(f"（已完成 {sum(1 for _, ok, _ in results if ok)}/{len(results)} 项检查，"
          "契约文件部分的结论仍然有效）")
    sys.exit(2)

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.recognition.router import META_HEADER  # noqa: E402
from app.recognition.router import router as recognition_router  # noqa: E402

app = FastAPI()
app.include_router(recognition_router)
client = TestClient(app)

# M1-1 /health
response = client.get("/health")
check("M1-1 GET /health 返回 {'status':'ok'}",
      response.status_code == 200 and response.json() == {"status": "ok"},
      f"HTTP {response.status_code} {response.text[:60]}")

# M1-2 ~ M1-4 用随包携带的印刷体素材（结论确定，不依赖外部照片）
fixture = ROOT / "tests" / "fixtures" / "formula_2.png"
if fixture.exists():
    payload = {"image": base64.b64encode(fixture.read_bytes()).decode("ascii")}
    started = time.time()
    response = client.post("/recognize", json=payload)
    elapsed = time.time() - started
    body = response.json() if response.status_code == 200 else {}
    check("M1-2 POST /recognize 返回合法 JSON", response.status_code == 200,
          f"HTTP {response.status_code}, 耗时 {elapsed:.1f}s")
    check("M1-3 latex 非空字符串", isinstance(body.get("latex"), str) and bool(body["latex"].strip()),
          f"latex={body.get('latex')!r}")
    check("M1-4 confidence ∈ [0,1]",
          isinstance(body.get("confidence"), (int, float)) and 0.0 <= body["confidence"] <= 1.0,
          f"confidence={body.get('confidence')}")
    check("M1-7 预留字段 tokens 保留（空列表）", body.get("tokens") == [], f"tokens={body.get('tokens')}")
    check("响应头带 X-Recognition-Meta 诊断信息", META_HEADER in response.headers)
else:
    check("测试素材 tests/fixtures/formula_2.png 存在", False, "文件缺失，无法验证 M1-2~M1-4")

# ======================================================================================
section("四、错误场景不得返回 5xx（ALL.md 红牌项 2/3）")
# ======================================================================================
response = client.post("/recognize", json={"image": ""})
check("空图片 → 200 + status=ERROR",
      response.status_code == 200 and response.json().get("status") == "ERROR",
      f"HTTP {response.status_code}")

response = client.post("/recognize", json={"image": "!!!not-base64!!!"})
check("非法 Base64 → 200 + status=ERROR",
      response.status_code == 200 and response.json().get("status") == "ERROR",
      f"HTTP {response.status_code}")

response = client.post("/recognize", json={})
check("缺 image 字段 → 422（格式错误走 4xx）", response.status_code == 422,
      f"HTTP {response.status_code}")

# ======================================================================================
section("五、M1-6 不依赖模块 2")
# ======================================================================================
loaded = sorted(m for m in sys.modules if m == "app" or m.startswith("app."))
check("未加载 app.calculation", not any(m.startswith("app.calculation") for m in loaded),
      f"已加载：{', '.join(loaded)}")
check("未加载 app.main", "app.main" not in sys.modules)

offenders = []
for rel in ("app/recognition/router.py", "app/recognition/recognizer.py",
            "app/recognition/preprocess.py", "tests/test_recognition.py"):
    path = ROOT / rel
    if not path.exists():
        continue
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        code = line.strip()
        if code.startswith("#") or "import" not in code:
            continue
        if "app.main" in code or "app.calculation" in code:
            offenders.append(f"{rel}:{lineno}")
check("模块一源码无 import main/calculation", not offenders, "、".join(offenders))

# ======================================================================================
section("六、模块 2 状态（信息项，不影响本模块验收）")
# ======================================================================================
try:
    import app.main  # noqa: F401

    print("[INFO] app.main 可导入 → 模块 2 已交付，可用 uvicorn app.main:app 整体启动")
except Exception as exc:  # noqa: BLE001
    print(f"[INFO] app.main 暂不可导入（{type(exc).__name__}: {exc}）")
    print("       这是 server/README.md §五 说明的正常状态：模块 2 尚未交付。")
    print("       模块一可单独验收（本脚本即如此），或用 README §2.1 的临时入口启动。")

# ======================================================================================
passed = sum(1 for _, ok, _ in results if ok)
total = len(results)
print(f"\n{'=' * 72}\n自检结果：{passed}/{total} 项通过\n{'=' * 72}")
if passed != total:
    print("\n未通过项：")
    for name, ok, detail in results:
        if not ok:
            print(f"  - {name}  {detail}")
sys.exit(0 if passed == total else 1)
