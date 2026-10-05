# -*- coding: utf-8 -*-
"""模块一：识别输出的后处理（组长订正 2026-10 新增）。

背景（2026-10-05 实测复现）：
Pix2Text 的 MFR 解码器会把「间隔偏大的相邻数字」当成两个 token 输出 ——
手写 `486` → `4 8 6`（置信度 1.0，0.95 门槛拦不住）、`48` → `4 8`。
而 latex2sympy2 会把 `4 8` 解析成 4×8（**静默算错**）、`4\\ 8` 直接 PARSE_ERROR，
所以必须在识别输出侧把这层修复掉（hmer_cs_1.md §2.1 第 5 条，组长订正）。

规则（保守，宁少勿多）：
- 仅当**数字与数字之间只隔空白类内容**（空格 / `\\,` / `\\;` / `~` / `\\!` /
  `\\quad` / `\\qquad`）时合并；
- 显式运算符（`\\cdot` / `\\times` / `\\div` / `+` / `-` 等）与其它内容一律不动；
- 纯函数、幂等（输出再喂一遍不变）。

模块二 `calculation/calculator.py` 里有一份同规则的**兜底**实现
（用户在修正页手工输入也可能带出拆散数字），两份各自独立测试，互不 import。
"""
from __future__ import annotations

import re

__all__ = ["merge_split_digits"]

#: 数字之间允许的「空白类」间隔；不含 \cdot / \times 等显式运算符
_DIGIT_GAP = re.compile(r"(?<=\d)(?:[ \t]+|\\,|\\;|\\ |~|\\!|\\quad|\\qquad)+(?=\d)")


def merge_split_digits(latex: str) -> str:
    r"""合并被空白拆散的数字：`4 8 6` → `486`。

    只处理「数字-空白-数字」形态，`4 \cdot 8`（显式乘号）保持原样。

    实测样例（2026-10-05，latex2sympy2）：
    - `4 8 6` → `486`（修复前会被算成 4×8×6=192）
    - `2 5+3 \times4` → `25+3 \times4`（修复前 2×5+12=22，应为 37）
    - `4 8 \div6` → `48 \div6`（修复前 4×8÷6≈5.33，应为 8）
    - `4 \cdot 8` → 原样（= 32，显式乘号不能合并）
    """
    if not latex:
        return latex
    previous = None
    current = latex
    # 一次 sub 即可处理所有非重叠匹配；循环是防御性写法，
    # 保证任何嵌套/相邻形态都收敛（长度单调不增，必然终止）。
    while previous != current:
        previous, current = current, _DIGIT_GAP.sub("", current)
    return current
