package com.hmercalc.common

// 全局常量：角度模式 + C7 编辑面板常用 LaTeX 片段（组长订正 2026-10：三态 + 分类面板）。
object Modes {
    const val AUTO = "auto" // 智能：三角参数纯数字按角度、含 π/变量按弧度（后端 2026-10 新增）
    const val DEG = "deg"
    const val RAD = "rad"
}

// 片段分类：决定面板分组与配色（同类同色，减少插入时的混淆）
enum class SnippetCategory(val label: String) {
    BASIC("基础运算"),
    STRUCTURE("分数/幂/根"),
    TRIG("三角函数"),
    OTHER("对数/其他"),
}

/**
 * 插入片段：
 * - insert 里的 `▮` 是「插入后光标停留位」标记，插入时会被移除；
 * - 若编辑框中已选中文本，则用 前段+选中内容+后段 把它包住（如选中 x 点分数 → \frac{x}{}）。
 */
data class LatexSnippet(
    val label: String,
    val insert: String,
    val category: SnippetCategory,
)

object LatexVocab {
    const val CURSOR_MARK = '▮'

    val snippets: List<LatexSnippet> = listOf(
        // —— 基础运算 ——
        LatexSnippet("+", "+", SnippetCategory.BASIC),
        LatexSnippet("−", "-", SnippetCategory.BASIC),
        LatexSnippet("×", "\\times", SnippetCategory.BASIC),
        LatexSnippet("÷", "\\div", SnippetCategory.BASIC),
        LatexSnippet("π", "\\pi", SnippetCategory.BASIC),
        // 自然常数 e（与后端 vocab.py 的 `PI, E = "\\pi", "e"` 对齐）。
        // 可紧跟数字使用（如 `2e` = 2×e，latex2sympy2 支持隐式乘法）
        LatexSnippet("e", "e", SnippetCategory.BASIC),

        // —— 分数/幂/根 ——
        LatexSnippet("分数", "\\frac{▮}{}", SnippetCategory.STRUCTURE),
        LatexSnippet("幂", "^{▮}", SnippetCategory.STRUCTURE),
        LatexSnippet("根号", "\\sqrt{▮}", SnippetCategory.STRUCTURE),
        LatexSnippet("绝对值", "|▮|", SnippetCategory.STRUCTURE),

        // —— 三角函数（组长订正：原只有 sin/cos/tan，扩到全套 + 反三角） ——
        LatexSnippet("sin", "\\sin(▮)", SnippetCategory.TRIG),
        LatexSnippet("cos", "\\cos(▮)", SnippetCategory.TRIG),
        LatexSnippet("tan", "\\tan(▮)", SnippetCategory.TRIG),
        LatexSnippet("cot", "\\cot(▮)", SnippetCategory.TRIG),
        LatexSnippet("sec", "\\sec(▮)", SnippetCategory.TRIG),
        LatexSnippet("csc", "\\csc(▮)", SnippetCategory.TRIG),
        LatexSnippet("arcsin", "\\arcsin(▮)", SnippetCategory.TRIG),
        LatexSnippet("arccos", "\\arccos(▮)", SnippetCategory.TRIG),
        LatexSnippet("arctan", "\\arctan(▮)", SnippetCategory.TRIG),

        // —— 对数/其他 ——
        LatexSnippet("log", "\\log(▮)", SnippetCategory.OTHER),
        LatexSnippet("ln", "\\ln(▮)", SnippetCategory.OTHER),
        LatexSnippet("求和", "\\sum_{i=1}^{n} ▮", SnippetCategory.OTHER),
        LatexSnippet("积分", "\\int_{0}^{1} ▮ \\, dx", SnippetCategory.OTHER),
    )
}
