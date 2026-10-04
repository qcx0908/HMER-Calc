"""tests/test_calculation.py —— 模块 2 独立测试。

约束（来自 hmer_cs_2.md §9）：
- 只挂自己的 router，不 import main.py
- 独立 FastAPI() 实例
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.calculation.router import router as calculation_router

app = FastAPI()
app.include_router(calculation_router)
client = TestClient(app)


def _calc(latex: str, mode: str = "deg"):
    r = client.post("/calculate", json={"latex": latex, "mode": mode})
    assert r.status_code == 200, f"不应返回非 200: {r.status_code}, {r.text}"
    return r.json()


# ---------- M2-2 四则 ----------
def test_basic_arithmetic():
    result = _calc(r"1+2\times 3")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 7.0) < 1e-9


def test_basic_arithmetic_plain():
    result = _calc(r"1+2*3")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 7.0) < 1e-9


# ---------- M2-3 分数 ----------
def test_fraction():
    result = _calc(r"\frac{1}{2}")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 0.5) < 1e-9


# ---------- M2-4 幂 ----------
def test_power():
    result = _calc(r"2^{3}")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 8.0) < 1e-9


# ---------- M2-5 根号 ----------
def test_sqrt():
    result = _calc(r"\sqrt{9}")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 3.0) < 1e-9


# ---------- M2-6 三角（角度制） ----------
def test_sin_deg():
    result = _calc(r"\sin(30)", mode="deg")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 0.5) < 1e-9


def test_cos_deg():
    result = _calc(r"\cos(60)", mode="deg")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 0.5) < 1e-9


def test_tan_deg():
    result = _calc(r"\tan(45)", mode="deg")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 1.0) < 1e-9


# ---------- M2-7 弧度制切换 ----------
def test_sin_rad():
    result = _calc(r"\sin(\pi)", mode="rad")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"]) < 1e-9


def test_cos_rad():
    result = _calc(r"\cos(0)", mode="rad")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 1.0) < 1e-9


# ---------- M2-8 非法输入不 500 ----------
def test_divide_by_zero():
    result = _calc(r"\frac{1}{0}")
    assert result["status"] in ("COMPUTE_ERROR", "PARSE_ERROR")
    assert result["message"]


def test_invalid_latex():
    result = _calc(r"\this_is_not_a_valid_command")
    assert result["status"] == "PARSE_ERROR"
    assert result["message"]


def test_invalid_mode():
    result = _calc(r"1+1", mode="xxx")
    assert result["status"] == "PARSE_ERROR"
    assert result["message"]


# ---------- 附加：value_latex 回显 ----------
def test_value_latex_present():
    result = _calc(r"\frac{1}{2}")
    assert result["value_latex"] is not None
    assert isinstance(result["value_latex"], str)


# ---------- 附加：混合运算 ----------
def test_mixed():
    result = _calc(r"\frac{1}{2}+\sqrt{9}")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 3.5) < 1e-9