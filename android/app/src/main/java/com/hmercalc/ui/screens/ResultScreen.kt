package com.hmercalc.ui.screens

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AssistChip
import androidx.compose.material3.AssistChipDefaults
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.OffsetMapping
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.text.input.TransformedText
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.hmercalc.common.LatexSnippet
import com.hmercalc.common.LatexVocab
import com.hmercalc.common.Modes
import com.hmercalc.common.SnippetCategory
import com.hmercalc.ui.UiState
import kotlinx.coroutines.delay
import java.util.Locale

// 最近插入内容在输入框中的高亮色（与各分类配色都不撞，便于区分刚插入的部分）
private val InsertedHighlight = Color(0xFFD81B60)

// 结果页（组长订正 2026-10）：
//   结果视图：识别公式（渲染）→ 角度模式 → 数值 →【结果正确 / 需要修正】
//   修正视图（correcting）：实时渲染预览 + LaTeX 编辑 + 分类符号面板 + 显式【重新计算/完成修正/退出修正】
@Composable
fun ResultScreen(
    state: UiState,
    onModeChanged: (String) -> Unit,
    onLatexChanged: (String, IntRange?) -> Unit,
    onEnterCorrection: () -> Unit,
    onExitCorrection: () -> Unit,
    onCommitCorrection: () -> Unit,
    onRecalculate: () -> Unit,
    onReset: () -> Unit,
) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (state.correcting) {
                CorrectionContent(
                    state = state,
                    onLatexChanged = onLatexChanged,
                    onModeChanged = onModeChanged,
                    onRecalculate = onRecalculate,
                    onCommitCorrection = onCommitCorrection,
                    onExitCorrection = onExitCorrection,
                )
            } else {
                ResultContent(
                    state = state,
                    onModeChanged = onModeChanged,
                    onEnterCorrection = onEnterCorrection,
                    onReset = onReset,
                )
            }
        }
    }
}

// ---------------- 结果视图 ----------------

@Composable
private fun ResultContent(
    state: UiState,
    onModeChanged: (String) -> Unit,
    onEnterCorrection: () -> Unit,
    onReset: () -> Unit,
) {
    Text("计算结果", style = MaterialTheme.typography.headlineSmall)

    // 原图缩略（供对照判断识别是否正确）—— 卡片承载，与背景拉开层次
    state.imageBitmap?.let { bmp ->
        Card(
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(16.dp),
            colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Image(
                bitmap = bmp.asImageBitmap(),
                contentDescription = "原图",
                modifier = Modifier
                    .fillMaxWidth()
                    .height(120.dp)
                    .padding(8.dp),
                contentScale = ContentScale.Fit,
            )
        }
    }

    // 识别公式卡片：渲染公式 + LaTeX 源码（只读）
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                "识别公式（置信度 ${String.format(Locale.US, "%.1f%%", state.confidence * 100)}）",
                style = MaterialTheme.typography.titleMedium,
            )
            LatexFormula(state.latex, modifier = Modifier.fillMaxWidth())

            // LaTeX 源码（2026-10 按用户需求新增）：只读展示，与上方渲染公式一一对应，
            // 供核对识别结果；需要改动时走【需要修正】页的编辑框
            if (state.latex.isNotBlank()) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        "LaTeX 源码",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                    Text(
                        state.latex,
                        style = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
                        modifier = Modifier
                            .fillMaxWidth()
                            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(8.dp))
                            .padding(8.dp),
                    )
                }
            }
        }
    }

    ModeSelector(state.mode, enabled = !state.loading, onModeChanged = onModeChanged)

    // 数值结果卡片：浅底 + 铜色大号数值点睛（公式图为黑色，需浅底才可读）
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Text(
                "数值结果",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.outline,
            )
            if (state.loading) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    CircularProgressIndicator(modifier = Modifier.width(20.dp).height(20.dp))
                    Text("计算中…")
                }
            } else {
                state.value?.let { v ->
                    Text(
                        formatValue(v),
                        style = MaterialTheme.typography.displaySmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.tertiary,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                // 精确值（如 π/6）与数值明显不同时才额外渲染，避免与大数字重复
                state.valueLatex?.let { v ->
                    val plain = state.value?.let { formatValue(it) }
                    if (plain == null || v.trim() != plain) {
                        LatexFormula(v, textSize = 28f, modifier = Modifier.fillMaxWidth())
                    }
                }
            }
        }
    }
    state.message?.let { Text(it, color = MaterialTheme.colorScheme.error) }

    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(
            onClick = onEnterCorrection,
            enabled = !state.loading,
            modifier = Modifier.weight(1f),
        ) { Text("需要修正") }
        Button(
            onClick = onReset,
            enabled = !state.loading,
            modifier = Modifier.weight(1f),
        ) { Text("结果正确") }
    }
    Text(
        "「结果正确」= 完成本次任务；「需要修正」= 进入手动修改",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.outline,
    )
}

// ---------------- 修正视图 ----------------

@Composable
private fun CorrectionContent(
    state: UiState,
    onLatexChanged: (String, IntRange?) -> Unit,
    onModeChanged: (String) -> Unit,
    onRecalculate: () -> Unit,
    onCommitCorrection: () -> Unit,
    onExitCorrection: () -> Unit,
) {
    Text("修正公式", style = MaterialTheme.typography.headlineSmall)

    // 实时渲染预览（防抖 250ms；半成品公式渲染失败显示占位，不崩溃）
    val debounced = rememberDebouncedLatex(state.latex)
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(12.dp))
            .padding(12.dp),
    ) {
        LatexFormula(debounced, textSize = 36f, modifier = Modifier.fillMaxWidth())
    }

    // LaTeX 编辑框（由状态同步；点选符号按光标位置插入）
    // 初始光标落在末尾（2026-10 按用户需求）：进修正页直接点符号即追加在公式后面，
    // 不必先点一下输入框定位；想插在别处仍可自己点光标位置
    var tfv by remember { mutableStateOf(TextFieldValue(state.latex, TextRange(state.latex.length))) }
    LaunchedEffect(state.latex) {
        if (tfv.text != state.latex) {
            tfv = tfv.copy(text = state.latex, selection = TextRange(state.latex.length))
        }
    }

    fun applySnippet(s: LatexSnippet) {
        val sel = tfv.selection
        val marker = s.insert.indexOf(LatexVocab.CURSOR_MARK)
        val before = if (marker >= 0) s.insert.substring(0, marker) else s.insert
        val after = if (marker >= 0) s.insert.substring(marker + 1) else ""
        val selected = tfv.text.substring(sel.min, sel.max)
        val replacement = before + selected + after
        val newText = tfv.text.replaceRange(sel.min, sel.max, replacement)
        val cursor = sel.min + before.length + selected.length // 有标记则落标记处；无标记则落末尾
        tfv = TextFieldValue(newText, TextRange(cursor))
        onLatexChanged(newText, sel.min until (sel.min + replacement.length)) // 高亮本次插入
    }

    OutlinedTextField(
        value = tfv,
        onValueChange = {
            tfv = it
            onLatexChanged(it.text, null) // 普通输入清除高亮
        },
        modifier = Modifier.fillMaxWidth(),
        label = { Text("LaTeX 源码") },
        textStyle = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
        visualTransformation = remember(state.lastInsertRange) {
            highlightTransformation(state.lastInsertRange)
        },
    )

    // 符号面板：先选分类，再点符号插入（分类配色，减少混淆）
    var category by remember { mutableStateOf(SnippetCategory.BASIC) }
    Row(
        modifier = Modifier.horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        SnippetCategory.entries.forEach { c ->
            FilterChip(
                selected = category == c,
                onClick = { category = c },
                label = { Text(c.label) },
            )
        }
    }
    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        items(LatexVocab.snippets.filter { it.category == category }) { s ->
            AssistChip(
                onClick = { applySnippet(s) },
                label = { Text(s.label) },
                colors = AssistChipDefaults.assistChipColors(labelColor = categoryColor(s.category)),
            )
        }
    }
    Text(
        "插入规则：在光标处插入；先在框里选中一段文本再点符号，会把它包住（如选中 x 点「分数」→ \\frac{x}{}）",
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.outline,
    )

    ModeSelector(state.mode, enabled = !state.loading, onModeChanged = onModeChanged)

    // 最近一次计算（修正中手动重算后刷新；只提示，不改变修正状态）
    if (state.loading) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            CircularProgressIndicator(modifier = Modifier.width(20.dp).height(20.dp))
            Text("计算中…")
        }
    } else {
        state.value?.let { v ->
            Text("最近一次计算：${formatValue(v)}", style = MaterialTheme.typography.titleMedium)
        }
    }
    state.message?.let { Text(it, color = MaterialTheme.colorScheme.error) }

    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
        OutlinedButton(
            onClick = onRecalculate,
            enabled = !state.loading,
            modifier = Modifier.weight(1f),
        ) { Text("重新计算") }
        Button(
            onClick = onCommitCorrection,
            enabled = !state.loading,
            modifier = Modifier.weight(1f),
        ) { Text("完成修正") }
    }
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
        TextButton(
            onClick = onExitCorrection,
            enabled = !state.loading,
        ) { Text("退出修正（放弃改动）") }
    }
}

// ---------------- 公共小组件 ----------------

// 角度模式三态（组长订正 2026-10：新增「自动」，不再强制二选一）
@Composable
private fun ModeSelector(
    selected: String,
    enabled: Boolean,
    onModeChanged: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("角度模式")
            FilterChip(
                selected = selected == Modes.AUTO,
                onClick = { onModeChanged(Modes.AUTO) },
                label = { Text("自动") },
                enabled = enabled,
            )
            FilterChip(
                selected = selected == Modes.DEG,
                onClick = { onModeChanged(Modes.DEG) },
                label = { Text("角度") },
                enabled = enabled,
            )
            FilterChip(
                selected = selected == Modes.RAD,
                onClick = { onModeChanged(Modes.RAD) },
                label = { Text("弧度") },
                enabled = enabled,
            )
        }
        Text(
            "自动：三角参数是纯数字按角度（sin 30 → 0.5）、含 π 按弧度（cos(π/2) → 0）；公式不涉及角度时无需关心",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.outline,
        )
    }
}

// 实时预览防抖：latex 停止变化 250ms 后才刷新渲染，避免每个按键都触发解析卡顿
@Composable
private fun rememberDebouncedLatex(latex: String, delayMs: Long = 250L): String {
    val debounced by produceState(initialValue = latex, latex) {
        delay(delayMs)
        value = latex
    }
    return debounced
}

// 「最近插入」高亮：把插入区间染成高亮色加粗；普通输入时传 null（不高亮）
private fun highlightTransformation(range: IntRange?): VisualTransformation {
    if (range == null || range.isEmpty()) return VisualTransformation.None
    return VisualTransformation { annotated ->
        val end = (range.last + 1).coerceAtMost(annotated.text.length)
        val start = range.first.coerceAtLeast(0)
        val transformed = if (start >= end) {
            annotated
        } else {
            AnnotatedString.Builder(annotated)
                .apply {
                    addStyle(
                        SpanStyle(color = InsertedHighlight, fontWeight = FontWeight.Bold),
                        start,
                        end,
                    )
                }
                .toAnnotatedString()
        }
        TransformedText(transformed, OffsetMapping.Identity)
    }
}

private fun categoryColor(c: SnippetCategory): Color = when (c) {
    SnippetCategory.BASIC -> Color(0xFF1E88E5)     // 蓝
    SnippetCategory.STRUCTURE -> Color(0xFF2E7D32) // 绿
    SnippetCategory.TRIG -> Color(0xFFEF6C00)      // 橙
    SnippetCategory.OTHER -> Color(0xFF8E24AA)     // 紫
}

private fun formatValue(v: Double): String {
    if (v.isNaN() || v.isInfinite()) return v.toString()
    // 整数值直接显示整数（避免 5.000000000）；其余保留 10 位有效数字并裁掉尾零
    if (v == v.toLong().toDouble()) return v.toLong().toString()
    val s = String.format(Locale.US, "%.10g", v)
    return if (s.contains('e') || s.contains('E')) s else s.trimEnd('0').trimEnd('.')
}
