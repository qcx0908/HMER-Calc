"""calculation/calculator.py —— LaTeX 解析 + sympy 计算封装。

对外只暴露 Calculator 类，包含一个 calculate() 方法。
router 只做参数校验和调用，不写计算逻辑。
"""

import math

import sympy
from sympy import sin, cos, tan, pi
from latex2sympy2 import latex2sympy


class Calculator:
    """LaTeX → sympy 表达式 → 数值结果。"""

    def calculate(self, latex: str, mode: str = "deg") -> dict:
        """
        返回 dict，字段：value, value_latex, status, message
        status ∈ {SUCCESS, PARSE_ERROR, COMPUTE_ERROR}
        """
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

        # ---------- 2. 角度制换算：把 sin/cos/tan 的参数转弧度 ----------
        if mode == "deg":
            try:
                expr = self._to_radians(expr)
            except Exception as e:
                return {
                    "value": None,
                    "value_latex": None,
                    "status": "COMPUTE_ERROR",
                    "message": f"角度制换算失败: {e}",
                }

        # ---------- 3. 计算：sympy 求值 → float ----------
        try:
            value_latex = sympy.latex(expr)
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

    @staticmethod
    def _to_radians(expr):
        """
        把 sin/cos/tan 的角度参数转成弧度。
        sympy 的三角函数默认弧度制，所以 deg 模式下需要 * pi / 180。
        """
        trig_funcs = (sin, cos, tan)

        def convert(node):
            if not node.args:
                return node
            new_args = [convert(a) for a in node.args]
            if node.func in trig_funcs:
                return node.func(new_args[0] * pi / 180)
            return node.func(*new_args)

        return convert(expr)