package com.hmercalc.ui.screens

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.FileProvider
import com.hmercalc.ui.Phase
import com.hmercalc.ui.UiState
import java.io.File

// 选图页（组长订正 2026-10 精简）：只负责拍照/选图 + 识别进度 + 错误重试 + 只读后端地址。
// 识别成功后由 CalcApp 切到结果页（含自动初算），LaTeX 编辑不再在本页出现。
@Composable
fun CaptureScreen(
    state: UiState,
    onImageUri: (Uri) -> Unit,
    onRetry: () -> Unit,
) {
    val context = LocalContext.current
    var pendingCameraUri by remember { mutableStateOf<Uri?>(null) }

    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture()
    ) { success ->
        val uri = pendingCameraUri
        pendingCameraUri = null
        if (success && uri != null) onImageUri(uri)
    }

    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri -> if (uri != null) onImageUri(uri) }

    fun launchCamera() {
        val file = File(context.cacheDir, "capture_${System.currentTimeMillis()}.jpg")
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.fileprovider", file)
        pendingCameraUri = uri
        cameraLauncher.launch(uri)
    }

    Scaffold { padding ->
        Column(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("HMER-Calc 手写公式计算", style = MaterialTheme.typography.headlineSmall)

            // 图片预览
            val bitmap = state.imageBitmap
            if (bitmap != null) {
                Image(
                    bitmap = bitmap.asImageBitmap(),
                    contentDescription = "手写公式",
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(240.dp),
                )
            } else {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(240.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Text("暂无图片，点下方「拍照」或「从相册选图」开始", color = MaterialTheme.colorScheme.outline)
                }
            }

            // 拍照 / 选图
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Button(onClick = { launchCamera() }, enabled = !state.loading) { Text("拍照") }
                OutlinedButton(
                    onClick = {
                        galleryLauncher.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)
                        )
                    },
                    enabled = !state.loading,
                ) { Text("从相册选图") }
            }

            // 加载中（识别首次可能要加载模型，给出提示避免误判卡死）
            if (state.loading) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    CircularProgressIndicator(modifier = Modifier.width(20.dp).height(20.dp))
                    Text("识别中…首次识别需加载模型，可能较慢")
                }
            }

            // 错误信息 + 重试
            state.message?.let { msg ->
                Text(msg, color = MaterialTheme.colorScheme.error)
            }
            if (state.phase == Phase.ERROR && state.imageBitmap != null && !state.loading) {
                Button(onClick = onRetry) { Text("重试识别") }
            }

            // 后端地址（组长订正 2026-10：模拟器阶段只读展示，不提供输入；
            // SettingsStore 与拦截器保留，真机适配时再开放编辑）
            Text(
                "后端地址：${state.baseUrl}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.outline,
            )
        }
    }
}
