"""tests/test_calculation.py —— 模块 2 独立测试。

约束（来自 hmer_cs_2.md §9）：
- 只挂自己的 router，不 import main.py
- 独立 FastAPI() 实例
"""

import math

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


# ---------- M2-9 auto 模式（组长订正：契约新增 "auto" ∵ 客户端三态角度选择） ----------
def test_auto_sin_plain_number_as_degrees():
    """auto：三角函数参数是纯数字 → 按角度制（手写习惯 sin30 → 0.5）。"""
    result = _calc(r"\sin(30)", mode="auto")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 0.5) < 1e-9


def test_auto_pi_arg_stays_radians():
    """auto：参数含 π → 按弧度（cos(π/2)+1 → 1.0，顺带修掉 deg 下的数值偏差）。"""
    result = _calc(r"\cos(\pi/2)+1", mode="auto")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 1.0) < 1e-9


def test_auto_no_trig():
    """auto：不涉及三角函数的公式不受影响。"""
    result = _calc(r"2+3\times 4", mode="auto")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 14.0) < 1e-9


def test_auto_cot_plain_number_as_degrees():
    """auto：扩充的 cot/sec/csc 同样参与角度换算（cot45 → 1）。"""
    result = _calc(r"\cot(45)", mode="auto")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 1.0) < 1e-9


# ---------- M2-10 扩充三角函数（组长订正：cot/sec/csc + 反三角，2026-10） ----------
def test_cot_deg():
    result = _calc(r"\cot(45)", mode="deg")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 1.0) < 1e-9


def test_sec_deg():
    result = _calc(r"\sec(60)", mode="deg")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 2.0) < 1e-9


def test_arcsin_deg_output():
    """deg：反三角函数输出按角度（arcsin(1/2) → 30°）。"""
    result = _calc(r"\arcsin(\frac{1}{2})", mode="deg")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 30.0) < 1e-9


def test_arcsin_rad_output():
    """rad：反三角函数按弧度输出（arcsin(1/2) → π/6）。"""
    result = _calc(r"\arcsin(\frac{1}{2})", mode="rad")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - math.pi / 6) < 1e-9


# ---------- M2-13 数字粘连兜底（组长订正 2026-10） ----------
# 背景：识别端可能输出被空白拆散的数字（`4 8`）；用户在修正页手输也可能带出。
# latex2sympy2 把 `4 8` **静默**解析成 4×8（不报错、算错），所以在解析前必须合并。
def test_split_digits_merged_div():
    """`4 8 \\div6` 应按 48÷6=8（修复前会被静默算成 4×8÷6≈5.33）。"""
    result = _calc(r"4 8 \div6")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 8.0) < 1e-9


def test_split_digits_merged_with_operator():
    """`2 5+3 \\times4` 应按 25+12=37（修复前 2×5+12=22）。"""
    result = _calc(r"2 5+3 \times4")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - 37.0) < 1e-9


def test_split_digits_merged_inside_radical():
    """花括号内同样生效：`\\sqrt{4 8}` → √48。"""
    result = _calc(r"\sqrt{4 8}")
    assert result["status"] == "SUCCESS"
    assert abs(result["value"] - math.sqrt(48)) < 1e-9


def test_explicit_times_not_merged():
    """回归保护：显式乘号 `4 \\cdot 8` / `4 \\times 8` 是 4×8=32，绝不能被合并成 48。"""
    for latex in (r"4 \cdot 8", r"4 \times 8"):
        result = _calc(latex)
        assert result["status"] == "SUCCESS", f"{latex} 不应解析失败"
        assert abs(result["value"] - 32.0) < 1e-9, f"{latex} 被错误合并了"