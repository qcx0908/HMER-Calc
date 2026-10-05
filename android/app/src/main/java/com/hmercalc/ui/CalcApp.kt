package com.hmercalc.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.lifecycle.viewmodel.compose.viewModel
import com.hmercalc.ui.screens.CaptureScreen
import com.hmercalc.ui.screens.ResultScreen

// 路由（组长订正 2026-10 新状态机）：
//   IDLE / IMAGE_LOADED / ERROR → 选图页（识别中、失败重试都在这）
//   RESULT（含 correcting 子态）→ 结果页（结果视图 / 修正视图）
@Composable
fun CalcApp(viewModel: CalcViewModel = viewModel()) {
    val state by viewModel.uiState.collectAsState()

    when (state.phase) {
        Phase.RESULT -> ResultScreen(
            state = state,
            onModeChanged = viewModel::onModeChanged,
            onLatexChanged = viewModel::onLatexChanged,
            onEnterCorrection = viewModel::enterCorrection,
            onExitCorrection = viewModel::exitCorrection,
            onCommitCorrection = viewModel::commitCorrection,
            onRecalculate = viewModel::calculate,
            onReset = viewModel::reset,
        )

        else -> CaptureScreen(
            state = state,
            onImageUri = viewModel::onImageUri,
            onRetry = viewModel::retryRecognize,
            onBaseUrlChanged = viewModel::setBaseUrl,
        )
    }
}
