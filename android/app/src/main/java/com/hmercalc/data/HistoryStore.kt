package com.hmercalc.data

import android.content.Context
import android.graphics.Bitmap
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.coroutines.withContext
import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import java.io.File
import javax.inject.Inject
import javax.inject.Singleton

// 历史记录持久化：元数据（JSON 列表）走 DataStore，缩略图走应用私有目录 filesDir/history/。
// 与 SettingsStore 各用各的 DataStore 文件（name 不同），互不干扰。
private val Context.historyDataStore: DataStore<Preferences> by preferencesDataStore(name = "history")

@Singleton
class HistoryStore @Inject constructor(
    @ApplicationContext private val context: Context,
    private val json: Json,
) {
    companion object {
        const val MAX_ENTRIES = 10
        private const val KEY_ENTRIES = "entries"
        // 缩略图最长边：10 条 × ~640px JPEG ≈ 每张几十 KB，总量可控、列表加载流畅
        private const val THUMB_MAX_EDGE = 640
        private const val JPEG_QUALITY = 85
    }

    private val entriesKey = stringPreferencesKey(KEY_ENTRIES)

    val entriesFlow: Flow<List<HistoryEntry>> = context.historyDataStore.data.map { prefs ->
        val raw = prefs[entriesKey] ?: return@map emptyList()
        runCatching { json.decodeFromString<List<HistoryEntry>>(raw) }.getOrDefault(emptyList())
    }

    suspend fun addEntry(
        bitmap: Bitmap,
        latex: String,
        confidence: Double,
        value: Double?,
        valueLatex: String?,
        status: String?,
    ) {
        val id = System.currentTimeMillis()
        val dir = File(context.filesDir, "history").apply { mkdirs() }
        val file = File(dir, "$id.jpg")
        withContext(Dispatchers.IO) { saveScaledJpeg(bitmap, file) }

        val entry = HistoryEntry(id, file.absolutePath, latex, confidence, value, valueLatex, status)
        val current = readEntries()
        val updated = (listOf(entry) + current).take(MAX_ENTRIES)
        context.historyDataStore.edit { prefs -> prefs[entriesKey] = json.encodeToString(updated) }

        // 被挤出 10 条的旧记录：删掉对应缩略图，避免磁盘膨胀
        current.drop(MAX_ENTRIES - 1).forEach { old ->
            runCatching { File(old.imagePath).delete() }
        }
    }

    suspend fun clearAll() {
        val current = readEntries()
        context.historyDataStore.edit { prefs -> prefs.remove(entriesKey) }
        current.forEach { old -> runCatching { File(old.imagePath).delete() } }
    }

    private suspend fun readEntries(): List<HistoryEntry> {
        val raw = context.historyDataStore.data.first()[entriesKey] ?: return emptyList()
        return runCatching { json.decodeFromString<List<HistoryEntry>>(raw) }.getOrDefault(emptyList())
    }

    // 只压缩新生成的缩略图；传入的原图由 ViewModel/UI 持有，绝不 recycle 它（否则界面会崩）
    private fun saveScaledJpeg(bitmap: Bitmap, file: File) {
        val scaled = scaleDown(bitmap, THUMB_MAX_EDGE)
        file.outputStream().use { out -> scaled.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, out) }
        if (scaled !== bitmap) scaled.recycle()
    }

    private fun scaleDown(bitmap: Bitmap, maxEdge: Int): Bitmap {
        val longEdge = maxOf(bitmap.width, bitmap.height)
        if (longEdge <= maxEdge) return bitmap
        val scale = maxEdge.toFloat() / longEdge
        return Bitmap.createScaledBitmap(
            bitmap,
            (bitmap.width * scale).toInt().coerceAtLeast(1),
            (bitmap.height * scale).toInt().coerceAtLeast(1),
            true,
        )
    }
}
