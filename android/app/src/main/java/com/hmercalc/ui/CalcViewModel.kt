package com.hmercalc.ui

import android.content.Context
import android.graphics.Bitmap
import android.net.Uri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.hmercalc.common.BitmapUtils
import com.hmercalc.common.Calculator
import com.hmercalc.common.Modes
import com.hmercalc.common.Recognizer
import com.hmercalc.data.SettingsStore
import com.hmercalc.remote.BackendUrlHolder
import dagger.hilt.android.lifecycle.HiltViewModel
import dagger.hilt.android.qualifiers.ApplicationContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import javax.inject.Inject

// 新状态机（组长订正 2026-10）：
//   IDLE ─选图─▶ IMAGE_LOADED ─识别成功(自动初算)─▶ RESULT ⇄（correcting 子态：修正公式）
//   识别/读图失败 ─▶ ERROR（留在选图页，可重试）
// 修正模式的进出全部由用户显式按钮驱动；清空输入框不会退出修正（组长订正第 6 条）。
enum class Phase { IDLE, IMAGE_LOADED, RESULT, ERROR }

// 进入修正前的快照：退出修正时整体恢复，保证「公式↔数值」始终一致
data class ResultSnapshot(
    val latex: String,
    val value: Double?,
    val valueLatex: String?,
    val status: String?,
)

data class UiState(
    val phase: Phase = Phase.IDLE,
    val imageBitmap: Bitmap? = null,
    val latex: String = "",
    val confidence: Double = 0.0,
    val value: Double? = null,
    val valueLatex: String? = null,
    val status: String? = null,
    val message: String? = null,
    val loading: Boolean = false,
    val baseUrl: String = SettingsStore.DEFAULT_BASE_URL,
    val mode: String = Modes.AUTO,
    // —— 修正模式 ——
    val correcting: Boolean = false,
    val snapshot: ResultSnapshot? = null,
    val lastInsertRange: IntRange? = null, // 最近一次点选插入的区间（输入框内变色高亮）
)

@HiltViewModel
class CalcViewModel @Inject constructor(
    private val recognizer: Recognizer,
    private val calculator: Calculator,
    private val settingsStore: SettingsStore,
    @ApplicationContext private val appContext: Context,
) : ViewModel() {

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        // 后端地址持久化 → 同步到运行期拦截器 + UI（UI 可编辑，见 setBaseUrl）
        viewModelScope.launch {
            settingsStore.baseUrlFlow.collect { url ->
                BackendUrlHolder.baseUrl = url
                _uiState.update { it.copy(baseUrl = url) }
            }
        }
    }

    // ---------------- 设置 ----------------

    /**
     * 保存后端地址。手输常漏 scheme，这里自动补 http://（不带 scheme 的地址会被拦截器判为无效而静默回退）。
     * 写入 DataStore 后经 init 的订阅链立即生效，无需重启 App。
     */
    fun setBaseUrl(input: String) {
        val raw = input.trim()
        if (raw.isEmpty()) return
        val url = if (raw.startsWith("http://") || raw.startsWith("https://")) raw else "http://$raw"
        viewModelScope.launch { settingsStore.setBaseUrl(url) }
    }

    // ---------------- 识别 ----------------

    // 拍照/选图得到 content:// URI
    fun onImageUri(uri: Uri) {
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, message = null) }
            val bitmap = withContext(Dispatchers.IO) {
                BitmapUtils.decodeBitmap(appContext, uri)
            }
            if (bitmap == null) {
                _uiState.update { it.copy(loading = false, message = "图片读取失败") }
                return@launch
            }
            _uiState.update {
                it.copy(
                    phase = Phase.IMAGE_LOADED,
                    imageBitmap = bitmap,
                    latex = "",
                    confidence = 0.0,
                    value = null,
                    valueLatex = null,
                    status = null,
                    correcting = false,
                    snapshot = null,
                    lastInsertRange = null,
                )
            }
            recognize(bitmap)
        }
    }

    /** 识别当前图片（识别失败后的【重试】入口） */
    fun retryRecognize() {
        val bitmap = _uiState.value.imageBitmap ?: return
        viewModelScope.launch { recognize(bitmap) }
    }

    private suspend fun recognize(bitmap: Bitmap) {
        _uiState.update { it.copy(loading = true, message = null) }
        try {
            val resp = recognizer.recognize(bitmap)
            if (resp.status == "SUCCESS") {
                // 识别成功 → 直接进结果页，并自动先算一次（组长订正第 5 条：先给计算值，由用户判断对错）
                _uiState.update {
                    it.copy(
                        phase = Phase.RESULT,
                        latex = resp.latex,
                        confidence = resp.confidence,
                        lastInsertRange = null,
                    )
                }
                calculate()
            } else {
                _uiState.update {
                    it.copy(phase = Phase.ERROR, loading = false, message = resp.message ?: "识别失败")
                }
            }
        } catch (e: Exception) {
            _uiState.update {
                it.copy(phase = Phase.ERROR, loading = false, message = "网络或服务异常：${e.message}")
            }
        }
    }

    // ---------------- 计算 ----------------

    /** 自动初算 / 修正中【重新计算】/ 结果页切换角度模式 共用。修正中成功也不退修正态。 */
    fun calculate() {
        val s = _uiState.value
        val latex = s.latex.trim()
        if (latex.isEmpty()) {
            _uiState.update { it.copy(message = "公式为空，请先识别或输入") }
            return
        }
        val mode = s.mode
        viewModelScope.launch {
            _uiState.update { it.copy(loading = true, message = null) }
            try {
                val resp = calculator.calculate(latex, mode)
                _uiState.update {
                    it.copy(
                        phase = Phase.RESULT,
                        value = resp.value,
                        valueLatex = resp.valueLatex,
                        status = resp.status,
                        message = if (resp.status == "SUCCESS") null else (resp.message ?: "计算失败"),
                        loading = false,
                    )
                }
            } catch (e: Exception) {
                _uiState.update { it.copy(loading = false, message = "网络或服务异常：${e.message}") }
            }
        }
    }

    /** 角度模式：结果页切换 → 自动重算；修正中切换 → 只记录，手动重算时生效 */
    fun onModeChanged(mode: String) {
        val s = _uiState.value
        if (s.mode == mode) return
        _uiState.update { it.copy(mode = mode) }
        if (s.phase == Phase.RESULT && !s.correcting && !s.loading && s.latex.isNotBlank()) {
            calculate()
        }
    }

    // ---------------- 修正模式（进出全部显式） ----------------

    // C7：用户编辑 LaTeX（insertedRange = 点选插入的区间，用于高亮；普通输入传 null）
    fun onLatexChanged(newLatex: String, insertedRange: IntRange? = null) {
        _uiState.update { it.copy(latex = newLatex, lastInsertRange = insertedRange) }
    }

    fun enterCorrection() {
        _uiState.update {
            it.copy(
                correcting = true,
                snapshot = ResultSnapshot(it.latex, it.value, it.valueLatex, it.status),
                lastInsertRange = null,
                message = null,
            )
        }
    }

    /** 退出修正：放弃改动，恢复进入修正前的公式与数值 */
    fun exitCorrection() {
        val snap = _uiState.value.snapshot
        _uiState.update {
            it.copy(
                correcting = false,
                latex = snap?.latex ?: it.latex,
                value = snap?.value,
                valueLatex = snap?.valueLatex,
                status = snap?.status,
                snapshot = null,
                lastInsertRange = null,
                message = null,
            )
        }
    }

    /** 完成修正：保留改动并重算，回结果视图 */
    fun commitCorrection() {
        _uiState.update { it.copy(correcting = false, snapshot = null, lastInsertRange = null, message = null) }
        calculate()
    }

    fun reset() {
        _uiState.update { UiState(baseUrl = it.baseUrl, mode = it.mode) }
    }
}
