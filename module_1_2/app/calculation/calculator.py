"""calculation/calculator.py —— LaTeX 解析 + sympy 计算封装。

对外只暴露 Calculator 类，包含一个 calculate() 方法。
router 只做参数校验和调用，不写计算逻辑。

组长订正 2026-10：新增 `_merge_split_digits` 兜底。
识别端（模块一）已修掉「数字被空格拆散」（`4 8` → `48`），这里是第二道保险：
用户在 C7 修正页手工输入的 LaTeX 同样可能带出拆散数字，而 latex2sympy2 会把
`4 8` **静默**解析成 4×8（不报错、结果错），必须在解析前合并。
两份实现各自独立（模块间不互相 import，见 hmer_cs_1.md §3.4），规则保持一致。
"""

import math
import re

import sympy
from sympy import asin, acos, atan, cos, cot, csc, pi, sec, sin, tan
from latex2sympy2 import latex2sympy

#: 数字之间允许的「空白类」间隔；不含 \cdot / \times 等显式运算符
_DIGIT_GAP = re.compile(r"(?<=\d)(?:[ \t]+|\\,|\\;|\\ |~|\\!|\\quad|\\qquad)+(?=\d)")


def _merge_split_digits(latex: str) -> str:
    r"""合并被空白拆散的数字：`4 8 6` → `486`。

    只处理「数字-空白-数字」形态；`4 \cdot 8`（显式乘号）保持原样。
    与模块一 `recognition/postprocess.py::merge_split_digits` 同规则（互不 import）。
    """
    if not latex:
        return latex
    previous = None
    current = latex
    while previous != current:
        previous, current = current, _DIGIT_GAP.sub("", current)
    return current


class Calculator:
    """LaTeX → sympy 表达式 → 数值结果。"""

    def calculate(self, latex: str, mode: str = "deg") -> dict:
        """
        返回 dict，字段：value, value_latex, status, message
        status ∈ {SUCCESS, PARSE_ERROR, COMPUTE_ERROR}
        """
        # ---------- 0. 归一化：合并被空白拆散的数字（组长订正 2026-10） ----------
        # 必须在解析前：latex2sympy2 把 `4 8` 当 4×8（静默算错），`4\ 8` 直接报错。
        latex = _merge_split_digits(latex or "")

        # ---------- 1. 解析：LaTeX → sympy 表达式 ----------
        try:
            expr = self._parse(latex)
        except Exception as e:
            return {
                "value": None,
                "value_latex": None,
                "status": "PARSE_ERROR",
                "message": f"解析失败: {e}",
            }

        # ---------- 2. 角度制换算 ----------
        # deg ：全部按角度制（三角参数 → 弧度；反三角输出 → 角度）
        # auto：智能判断——三角参数是纯数字（不含 π/变量）视为角度，否则按弧度
        # rad ：不做任何换算
        try:
            if mode == "deg":
                expr = self._to_radians(expr)
            elif mode == "auto":
                expr = self._auto_to_radians(expr)
        except Exception as e:
            return {
                "value": None,
                "value_latex": None,
                "status": "COMPUTE_ERROR",
                "message": f"角度制换算失败: {e}",
            }

        # ---------- 3. 计算：sympy 求值 → float ----------
        try:
            # value_latex 必须是**结果**的 LaTeX（契约：E7 结果格式化）。
            # rad 模式不做角度换算，expr 仍是解析后的原始输入式（`1+2*3`、`2^{3}`），
            # 直接 latex 会把**输入**当结果回显；而 deg/auto 换算时会重建表达式，
            # sympy 顺带求值，于是恰好是结果——三档行为不一致，
            # 客户端「数值 + 精确值」两行的去重逻辑失效，rad 档会多显示一行（组长订正 2026-10-06）。
            # 故先化简；化简后仍含未求值函数（如 sin(30)，非精确形式）的置 None，
            # 客户端只显示数值。
            simplified = sympy.simplify(expr)
            if simplified.is_number and not simplified.atoms(sympy.Function):
                value_latex = sympy.latex(simplified)
            else:
                value_latex = None

            numeric = expr.evalf()
            value = float(numeric)

            if math.isnan(value) or math.isinf(value):
                return {
                    "value": None,
                    "value_latex": value_latex,
                    "status": "COMPUTE_ERROR",
                    "message": "结果不是有限实数",
                }

            return {
                "value": value,
                "value_latex": value_latex,
                "status": "SUCCESS",
                "message": None,
            }
        except Exception as e:
            return {
                "value": None,
                "value_latex": None,
                "status": "COMPUTE_ERROR",
                "message": f"计算失败: {e}",
            }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _parse(latex: str):
        """latex2sympy2 兜底解析。兼容不同版本返回值。"""
        parsed = latex2sympy(latex)
        # 某些版本返回 (expr, mathrm_dict)，这里取 expr
        if isinstance(parsed, tuple):
            parsed = parsed[0]
        return parsed

    #: 输入为角度的三角函数（deg/auto 下把参数 * pi / 180）
    ANGLE_IN_FUNCS = (sin, cos, tan, cot, sec, csc)
    #: 输出为角度的反三角函数（deg 下把结果 * 180 / pi）
    ANGLE_OUT_FUNCS = (asin, acos, atan)

    @classmethod
    def _to_radians(cls, expr):
        """
        deg 模式全量换算：三角函数参数 → 弧度；反三角函数输出 → 角度。

        例：sin(30) → sin(π/6) = 0.5；arcsin(1/2) → (π/6)×180/π = 30。
        """
        def convert(node):
            if not node.args:
                return node
            new_args = [convert(a) for a in node.args]
            if node.func in cls.ANGLE_IN_FUNCS:
                return node.func(new_args[0] * pi / 180)
            if node.func in cls.ANGLE_OUT_FUNCS:
                return node.func(new_args[0]) * 180 / pi
            return node.func(*new_args)

        return convert(expr)

    @classmethod
    def _auto_to_radians(cls, expr):
        """
        auto 模式智能换算：三角函数参数是纯数字（is_number 且不含 π）→ 视为角度制；
        含 π 或变量 → 保持原样（按弧度处理）。反三角不做输出换算（按弧度输出）。

        例：sin(30) → 0.5（手写习惯）；cos(π/2)+1 → 1.0；
            2×sin(30) 逐节点判断，同样只换算纯数字参数。
        """
        def convert(node):
            if not node.args:
                return node
            new_args = [convert(a) for a in node.args]
            if node.func in cls.ANGLE_IN_FUNCS:
                arg = new_args[0]
                if arg.is_number and not arg.has(pi):
                    return node.func(arg * pi / 180)
            return node.func(*new_args)

        return convert(expr)