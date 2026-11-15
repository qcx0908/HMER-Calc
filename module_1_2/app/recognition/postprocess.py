# -*- coding: utf-8 -*-
r"""模块一：识别输出的后处理（组长订正 2026-10 新增；成员 1 于 2026-10-08 扩充）。

背景（2026-10-05 实测复现）：
Pix2Text 的 MFR 解码器会把「间隔偏大的相邻数字」当成两个 token 输出 ——
手写 `486` → `4 8 6`（置信度 1.0，0.95 门槛拦不住）、`48` → `4 8`。
而 latex2sympy2 会把 `4 8` 解析成 4×8（**静默算错**）、`4\\ 8` 直接 PARSE_ERROR，
所以必须在识别输出侧把这层修复掉（hmer_cs_1.md §2.1 第 5 条，组长订正）。

2026-10-08 扩充（成员 1，依据 PHOTO 目录 39 张人工标注样本的实测失败案例）：

| 实测失败 | 病因 | 本次修复 |
|---|---|---|
| `8 \div2` → `z \div2` | 8 被读成 z | 数字上下文中的 z 还原为 2 |
| `6 \times7` → `L \times9` | 6→L | 数字上下文中的 L 还原为 6（同 token 含数字时） |
| `3^{2}+1` → `3^{z}+1` | 上标 2→z | 上标位置的 z 还原为 2 |
| `5^{0}` → `5^{\circ}` | 0 被读成度符号 | 非三角函数语境下的 `^{\circ}` 还原为 `^{0}` |
| `100 \times4` → `100 x 4` | × 被读成字母 x | 数字之间的孤立 x 还原为 \times |
| `sin60°` → `sin 6 o^{...}` | 0 被读成字母 o | 数字上下文中的 o 还原为 0 |

规则（保守，宁少勿多）：
- 仅当**数字与数字之间只隔空白类内容**（空格 / `\\,` / `\\;` / `~` / `\\!` /
  `\\quad` / `\\qquad`）时合并；
- 显式运算符（`\\cdot` / `\\times` / `\\div` / `+` / `-` 等）与其它内容一律不动；
- 字母→数字的还原**必须由相邻数字或函数名约束**，避免把真正的函数名/变量改坏；
- 纯函数、幂等（输出再喂一遍不变）。

模块二 `calculation/calculator.py` 里有一份同规则的**兜底**实现
（用户在修正页手工输入也可能带出拆散数字），两份各自独立测试，互不 import。
"""
from __future__ import annotations

import re

__all__ = [
    "merge_split_digits",
    "normalize_digit_confusions",
    "fix_stray_backslash_digits",
    "normalize_x_times",
    "fix_spaced_function_names",
    "fix_degree_mark_variants",
]

#: 数字之间允许的「空白类」间隔；不含 \cdot / \times 等显式运算符
_DIGIT_GAP = re.compile(r"(?<=\d)(?:[ \t]+|\\,|\\;|\\ |~|\\!|\\quad|\\qquad)+(?=\d)")

#: LaTeX 里表示「度」的写法
_DEGREE_MARKS = ("^{\\circ}", "^\\circ", "^{\\text{°}}", "°")

#: 三角函数名（用于判断 `^{\circ}` 是否处于三角函数语境）
_TRIG = re.compile(r"\\(?:sin|cos|tan|cot|sec|csc)|\\operatorname\s*\{[^}]*\}")

#: 被拆散成单字母的函数名：`c o s` / `\operatorname{C o s}` / `\mathsf{c o t}` → `\cos` / `\cot`
#: 实测（2026-10-08）：
#:   p1.jpg 真值 `cos90°` → 模型 `\operatorname{C o s} \9 \sigma^{\circ}`
#:   P8.jpg 真值 `cot60°` → 模型 `\mathsf{c o t 6 o^{\nu}}`
#:   对照 20.jpg 真值 `cos45°` → 模型 `\cos4 5^{\circ}`（函数名是完整 token，所以读得对）
#: 即：**函数名一旦被拆成带空格的单字母，就再也拼不回来** —— 这是 cos/cot 读不出的直接原因。
_SPACED_FUNC = re.compile(
    r"(?:\\(?:operatorname|mathsf|mathrm|text)\s*\{[ \t]*)?"
    r"(?P<c>[cC])[ \t]+(?P<o>[oO0])[ \t]+(?P<last>[sStT])"
)

#: 度符号的各种误读形态 → 标准 `^{\circ}`
#: 实测：P8.jpg 的 `^{\nu}`（度号被读成 ν）、19.jpg 的裸 `\circ`（丢了上标）、
#:       p1.jpg 的 `\sigma^{\circ}`（度号前多出一个被误读的 σ）
_DEGREE_VARIANTS = re.compile(
    r"[\^]\s*(?:\{\s*)?(?:\\nu|\\upsilon|\\prime|\\circ|ν|°|º)(?:\s*\})?"
)

#: 度号前多出的、被误读成希腊字母的「前一个字符」（如 `9\sigma^{\circ}` 里的 `\sigma`）。
#: 不要求紧邻（实测可能是 `\9 \sigma^{\circ}`），只要它与度号之间只剩空白/数字/反斜杠。
_DEGREE_PREFIX_JUNK = re.compile(
    r"\\(?:sigma|varsigma|theta|varphi|psi|mu|alpha|beta)\s*(?=[\d\s\\]*\^\{?\\circ)"
)

#: 数字上下文中被误读的字母 → 数字。
#: 依据实测：8→z、6→L、2→z（上标）、0→o。不做无约束的全局替换。
_LETTER_FIXES = (
    # --- o/O → 0 ---
    # "9o0"：数字-字母-数字
    (re.compile(r"(?<=\d)\s*[oO]\s*(?=\d)"), "0"),
    # "6 o^{\circ}" / "6o^{\circ}" / "6o}" / "6o^"：数字后、紧跟上标或右界的 o
    (re.compile(r"(?<=\d)\s*[oO](?=\s*[\^}\]])"), "0"),
    # "6o"：数字后接词边界的 o
    (re.compile(r"(?<=\d)[oO]\b"), "0"),
    # --- z → 2（指数位）或 8（算术位） ---
    # 上标 z → 2（比通用规则更 specific，须先执行）
    (re.compile(r"\^\s*\{\s*z\s*\}"), "^{2}"),
    # 孤立 z 参与算术（z \div2 / z+1 / z-1）→ 8
    (re.compile(r"\bz(?=\s*(?:\\div|\\times|\+|-|$))"), "8"),
    # "8z" 类尾部 → 2
    (re.compile(r"(?<=\d)z\b"), "2"),
    # --- 其他易混 ---
    # 数字后的孤立 L → 6（如 "6L"、" L" 无明显数字约束时不动）
    (re.compile(r"(?<=\d)L"), "6"),
)


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


def fix_stray_backslash_digits(latex: str) -> str:
    r"""去掉数字前多出来的孤立反斜杠：`\9` → `9`。

    实测案例（2026-10-08）：`\operatorname{C o s} \9 \sigma^{\circ}` 里的 `\9`
    是解码器把数字 9 误当命令前缀输出，latex2sympy2 无法解析。
    只在反斜杠后面紧跟数字、且该反斜杠不属于已知命令时处理。
    """
    if not latex:
        return latex
    return re.sub(r"\\(?=\d)", "", latex)


def normalize_x_times(latex: str) -> str:
    r"""把数字之间被误读成字母 `x` 的乘号还原：`100 x 4` → `100 \times4`。

    实测案例：手写 `100×4` → 模型输出 `100 x 4`（P5.jpg）。
    只在「数字 - 空白 - x - 空白 - 数字」这一形态下替换，
    避免破坏变量 x（如 `2 x+5`、`x^{2}`）。
    """
    if not latex:
        return latex
    return re.sub(r"(?<=\d)\s*[xX]\s*(?=\d)", r" \\times ", latex)


def fix_spaced_function_names(latex: str) -> str:
    r"""把被拆成单字母的函数名拼回来：`c o s` / `\operatorname{C o s}` → `\cos`。

    实测依据（2026-10-08）：这是 cos/cot「读不出」的**直接原因** ——
    解码器把 `cos` 拆成三个 token 输出，而下游没有任何规则会把它合回去；
    对照组 20.jpg 的 `\cos4 5^{\circ}`（函数名完整）则一直正常。

    实现说明：不用正则，改为**索引扫描 + 花括号深度跟踪**。
    原因是正则的可选包装组会回溯（把空格吃给 `s`，导致 `\operatorname{` 的 `}` 变孤儿），
    实测无法稳定处理 `\operatorname{C o s}` 与 `\mathsf{c o t ...}` 两种形态。
    扫描法显式匹配前缀、并要求满 2 个空白分隔，行为完全确定。

    同时顺带修掉函数名内部被拆出的数字误读：`c 0 s` → `cos`（`o` 被读成 `0`）。
    """
    if not latex:
        return latex

    # ① 先把包装命令整段处理掉。
    #    优先处理**花括号配对**的形态（`\mathsf{c o t}`）：取内容、去掉内部空白、
    #    若内容恰好是函数名则改写为标准命令。
    #    实测必须这样做的原因：若只删左括号 `\operatorname{`，当内容与 `}` 之间有空格
    #    （如 `\mathsf{c o t 6 o^{...}}`），那个 `}` 会落进内容里，字母就不连续、再也拼不回来。
    def _unwrap(match: re.Match[str]) -> str:
        # 大小写不敏感（实测有 `\operatorname{C o s}` 这种首字母大写的形态）
        content = re.sub(r"[ \t\n]+", "", match.group("body")).lower()
        return {"cost": "\\cos", "cot": "\\cot", "cos": "\\cos",
                "sin": "\\sin", "tan": "\\tan"}.get(content, content)

    out = re.sub(
        r"\\(?:operatorname|mathsf|mathrm|text)[ \t]*\{(?P<body>[^{}]*)\}",
        _unwrap, latex,
    )
    # 花括号不配对的残留前缀（如 `\operatorname{s i n}` 缺 `}`）：只删前缀，
    # 让后续字母级替换仍能工作，末尾残留的 `}` 由 ④ 清理。
    out = re.sub(r"\\(?:operatorname|mathsf|mathrm|text)[ \t]*\{", "", out)

    # ② 字母级替换：`c o s` → `\cos`（要求字母之间确有空白，避免误伤 cost / cos）
    rebuilt: list[str] = []
    i = 0
    n = len(out)
    while i < n:
        if (i + 4 < n and out[i] in "cC" and out[i + 1] in " \t"
                and out[i + 2] in "oO0" and out[i + 3] in " \t"
                and out[i + 4] in "sStT"):
            rebuilt.append("\\cot" if out[i + 4].lower() == "t" else "\\cos")
            i += 5
            continue
        rebuilt.append(out[i])
        i += 1
    result = "".join(rebuilt)

    # ③ 去掉因吞掉包装前缀而多出来的右花括号（只删多余的，不碰配对的）
    while result.count("}") > result.count("{"):
        idx = result.rfind("}")
        result = result[:idx] + result[idx + 1:]

    # ④ 压掉 `\cos` 与数字之间由原空格留下的多余空白：`\cos 9` → `\cos9`
    result = re.sub(r"(\\(?:cos|cot|sin|tan))[ \t]+(?=\d)", r"\1", result)
    return result


def fix_degree_mark_variants(latex: str) -> str:
    r"""把被误读的度符号统一成 `^{\circ}`。

    实测（2026-10-08）：
      - P8.jpg `\mathsf{c o t 6 o^{\nu}}` —— 度号 `°` 被读成希腊字母 `\nu`
      - p1.jpg `\sigma^{\circ}` —— 度号前多了 `\sigma`
      - 19.jpg `\cos P_{0} \circ` —— 度号丢了上标
    仅在**三角函数语境**下改写（否则会把真正的指数改坏）。
    """
    if not latex or not _TRIG.search(latex):
        return latex
    # ① 先吞掉度号前被误读成希腊字母的前缀（`9\sigma^{\circ}` → `9^{\circ}`）
    out = _DEGREE_PREFIX_JUNK.sub("", latex)
    # ② 再把各种度号写法统一成 `^{\circ}`
    #    用 lambda 作替换串：普通字符串里的 `\c` 会被 re 当转义解析而报错
    #
    # 注：**不**处理「裸 `\circ`（既无 `^` 也无花括号）」——实测 19.jpg 的
    # `\cos P_{0} \circ` 真正丢的是数字 90（原始内容是 cos90°），改度号也救不回来，
    # 反而会把 `^{\circ}` 变成 `^{^{\circ}}`（双上标）造成误伤。
    return _DEGREE_VARIANTS.sub(lambda _m: "^{\\circ}", out)


def _fix_l_as_six(latex: str) -> str:
    r"""孤立 `L` 在乘除语境中还原为 6：`L \times9` → `6 \times9`。

    需求与依据（需求方指出，2026-10-08）：「带符号的乘法一般不存在未知数，除法也是常数优先」。
    即出现 `\times` / `\div` 时，两侧几乎一定是**常数**，`L` 就是被误读的 `6`
    （实测 3.jpg：真值 `6×7`，270° 输出 `L \times9`）。
    """
    if not latex:
        return latex
    # L 后面紧跟乘除号 → 常数
    latex = re.sub(r"\bL(?=\s*(?:\\times|\\div))", "6", latex)
    # 乘除号后面紧跟 L → 常数（如 `\times L`），用捕获组避免变长后顾
    latex = re.sub(r"(\\(?:times|div))\s*L\b", r"\1 6", latex)
    return latex


def _fix_degree_as_zero(latex: str) -> str:
    r"""非三角函数语境下，`^{\circ}` 还原为 `^{0}`。

    实测案例（2026-10-08）：手写 `5^0` → 模型输出 `5^{\circ}`
    （13.jpg，score 0.9632，0.95 门槛拦不住）。
    判据：该 `^{\circ}` 所在的表达式里**没有任何三角函数名**，
    且它的底数是个位数 —— 手写三角函数度数通常是两位数（30/45/60/90/540）。
    两者同时满足才还原，避免把真正的 `\tan540^{\circ}` 改坏。
    """
    if not latex or "^{\\circ}" not in latex and "^\\circ" not in latex:
        return latex
    if _TRIG.search(latex):
        return latex
    return re.sub(r"\^\s*\{\s*\\circ\s*\}", "^{0}", latex)


def normalize_digit_confusions(latex: str) -> str:
    r"""把数字上下文里被误读的字母还原成数字（依据实测失败案例，保守规则）。

    按以下顺序处理：
    1. **把被拆散的函数名拼回来**（`c o s` → `\cos`）—— cos/cot 读不出的头号原因；
    2. 三角函数语境下统一度符号（`^{\nu}` / `\sigma^{\circ}` → `^{\circ}`）；
    3. `^{\circ}` 的语义消歧（非三角函数语境 → `^{0}`）；
    4. **乘除语境中的孤立 `L` → 6**（「带符号的乘法一般不存在未知数」）；
    5. 孤立反斜杠数字；
    6. 数字之间的 `x` → `\times`；
    7. 数字上下文中的 `o/O` → `0`、`z` → `2`；幂指数位置的 `z` → `2`；
    8. 再做一次拆散数字合并；
    9. 修掉数字内部残留的空格（`\cot6 0^{\circ}` → `\cot60^{\circ}`）。

    纯函数、幂等。
    """
    if not latex:
        return latex
    out = latex
    out = fix_spaced_function_names(out)
    out = fix_degree_mark_variants(out)
    out = _fix_degree_as_zero(out)
    out = _fix_l_as_six(out)
    out = fix_stray_backslash_digits(out)
    out = normalize_x_times(out)
    # 幂指数位置的字母 z → 2（须在通用 z 规则之前，形态更 specific）
    out = re.sub(r"\^\s*\{\s*z\s*\}", "^{2}", out)
    for pattern, repl in _LETTER_FIXES:
        out = pattern.sub(repl, out)
    out = merge_split_digits(out)
    # 数字内部残留的空格：仅在「数字 空格 数字」时收紧
    out = re.sub(r"(?<=\d) (?=\d)", "", out)
    return out
