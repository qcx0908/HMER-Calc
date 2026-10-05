package com.hmercalc.ui.screens

import android.graphics.Color
import android.view.Gravity
import android.widget.TextView
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.viewinterop.AndroidView
import ru.noties.jlatexmath.JLatexMathDrawable

// 用 jlatexmath 把 LaTeX 渲染成公式图（通过 TextView 的 drawable 展示）。
// 组长订正 2026-10：加健壮性兜底——空公式 / 半成品公式（如刚敲到 \frac{）
// 渲染失败时显示占位文字，绝不崩溃。结果页、修正页实时预览、数值 LaTeX 均复用本组件。
@Composable
fun LatexFormula(
    latex: String,
    textSize: Float = 40f,
    modifier: Modifier = Modifier,
) {
    AndroidView(
        modifier = modifier,
        factory = { ctx ->
            TextView(ctx).apply { gravity = Gravity.CENTER }
        },
        update = { tv ->
            val drawable = if (latex.isBlank()) null else try {
                JLatexMathDrawable.builder(latex).textSize(textSize).build()
            } catch (e: Exception) {
                null
            }
            if (drawable != null) {
                tv.text = ""
                tv.setCompoundDrawablesWithIntrinsicBounds(null, null, null, drawable)
            } else {
                tv.setCompoundDrawablesWithIntrinsicBounds(null, null, null, null)
                tv.text = if (latex.isBlank()) "（暂无公式）" else "公式不完整或无法渲染"
                tv.textSize = 14f
                tv.setTextColor(Color.GRAY)
            }
        },
    )
}
