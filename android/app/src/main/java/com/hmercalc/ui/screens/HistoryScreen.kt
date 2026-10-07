package com.hmercalc.ui.screens

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.hmercalc.data.HistoryEntry
import com.hmercalc.data.HistoryStore
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

// 历史记录列表页（组长订正 2026-10-07 新增）：最近 10 次「拍摄图 → 识别 → 计算」。
// 点一条可重新载入该次结果（回结果页）；支持一键清空。
@Composable
fun HistoryScreen(
    entries: List<HistoryEntry>,
    onOpen: (HistoryEntry) -> Unit,
    onBack: () -> Unit,
    onClear: () -> Unit,
) {
    Scaffold { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .padding(16.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween,
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text("历史记录", style = MaterialTheme.typography.headlineSmall)
                    Text(
                        "最近 ${HistoryStore.MAX_ENTRIES} 次，点一条可重新载入",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
                TextButton(onClick = onBack) { Text("返回") }
            }

            if (entries.isEmpty()) {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text(
                        "还没有历史记录\n拍照或选图识别一次后就会出现在这里",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.outline,
                    )
                }
            } else {
                TextButton(
                    onClick = onClear,
                    modifier = Modifier.align(Alignment.End),
                ) { Text("清空历史") }

                LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    items(entries, key = { it.id }) { entry ->
                        HistoryCard(entry = entry, onClick = { onOpen(entry) })
                    }
                }
            }
        }
    }
}

@Composable
private fun HistoryCard(entry: HistoryEntry, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
        shape = RoundedCornerShape(16.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            HistoryThumb(entry.imagePath, Modifier.size(56.dp))
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    entry.latex.ifBlank { "（空公式）" },
                    style = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace),
                    maxLines = 1,
                )
                Text(
                    "${SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(entry.id))} · 置信度 ${String.format(Locale.US, "%.0f%%", entry.confidence * 100)}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
            Text(
                formatHistoryValue(entry),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
        }
    }
}

// 缩略图异步解码（图片很小，IO 线程加载避免主线程卡顿）
@Composable
private fun HistoryThumb(path: String, modifier: Modifier = Modifier) {
    val bmp by produceState<Bitmap?>(initialValue = null, path) {
        value = withContext(Dispatchers.IO) {
            runCatching { BitmapFactory.decodeFile(path) }.getOrNull()
        }
    }
    val bitmap = bmp
    if (bitmap != null) {
        Image(
            bitmap = bitmap.asImageBitmap(),
            contentDescription = "历史缩略图",
            modifier = modifier,
            contentScale = ContentScale.Crop,
        )
    } else {
        Box(modifier = modifier, contentAlignment = Alignment.Center) {
            Text("无图", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.outline)
        }
    }
}

private fun formatHistoryValue(entry: HistoryEntry): String {
    entry.value?.let { return formatValue(it) }
    return when (entry.status) {
        "PARSE_ERROR", "COMPUTE_ERROR" -> "算不出"
        else -> "未完成"
    }
}

// 与 ResultScreen 的 formatValue 保持一致（结果页那份是 private，此处为历史列表独立一份）
private fun formatValue(v: Double): String {
    if (v.isNaN() || v.isInfinite()) return v.toString()
    if (v == v.toLong().toDouble()) return v.toLong().toString()
    val s = String.format(Locale.US, "%.10g", v)
    return if (s.contains('e') || s.contains('E')) s else s.trimEnd('0').trimEnd('.')
}
