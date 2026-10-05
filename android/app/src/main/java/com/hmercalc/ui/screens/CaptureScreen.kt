package com.hmercalc.ui.screens

import android.content.ActivityNotFoundException
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
import androidx.compose.material3.OutlinedTextField
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

// 选图页（组长订正 2026-10 精简）：只负责拍照/选图 + 识别进度 + 错误重试 + 可编辑后端地址。
// 识别成功后由 CalcApp 切到结果页（含自动初算），LaTeX 编辑不再在本页出现。
@Composable
fun CaptureScreen(
    state: UiState,
    onImageUri: (Uri) -> Unit,
    onRetry: () -> Unit,
    onBaseUrlChanged: (String) -> Unit,
) {
    val context = LocalContext.current
    var pendingCameraUri by remember { mutableStateOf<Uri?>(null) }
    var cameraError by remember { mutableStateOf<String?>(null) }

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
        cameraError = null
        // 启动系统相机失败时给出提示而不是崩溃（相册选图仍可用）：
        // ActivityNotFound = 设备没有能响应拍照 Intent 的相机 App；
        // Security       = 相机被设备策略禁用等（2026-10-06 模拟器那次就是本 App 声明了
        //                  未授权的 CAMERA 权限被拒，根因已在 AndroidManifest 移除该权限）。
        try {
            cameraLauncher.launch(uri)
        } catch (e: ActivityNotFoundException) {
            pendingCameraUri = null
            cameraError = "本机没有可用的相机应用，请改用「从相册选图」"
        } catch (e: SecurityException) {
            pendingCameraUri = null
            cameraError = "系统拒绝了相机调用（相机可能被设备策略禁用），请改用「从相册选图」"
        }
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
            // 标题（组长订正 2026-10-06）：改全称；字号从 headlineSmall 降到 titleLarge，
            // 长标题在窄屏（360dp 档）也能单行放下，放不下时正常换行，不会顶出显示区
            Text(
                "HMER-Calc 手写公式识别计算系统",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.fillMaxWidth(),
            )

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
            cameraError?.let { Text(it, color = MaterialTheme.colorScheme.error) }

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

            // 后端地址（组长订正 2026-10-06：开放编辑，真机换网络时在 App 内直接改，免重新打包）。
            // 初值自动填入 SettingsStore 的默认值（模拟器 10.0.2.2 → 宿主机 8000），保存后立即生效。
            var urlInput by remember(state.baseUrl) { mutableStateOf(state.baseUrl) }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                OutlinedTextField(
                    value = urlInput,
                    onValueChange = { urlInput = it },
                    label = { Text("后端地址") },
                    singleLine = true,
                    enabled = !state.loading,
                    textStyle = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.fillMaxWidth(),
                )
                Button(
                    onClick = { onBaseUrlChanged(urlInput) },
                    enabled = !state.loading && urlInput.isNotBlank(),
                ) { Text("保存地址") }

                // 当前生效地址（保存后才变）+ 模拟器默认说明，均为浅灰小字
                Text(
                    "当前生效：${state.baseUrl}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
                Text(
                    "模拟器默认 http://10.0.2.2:8000（10.0.2.2 即电脑本机）；" +
                        "真机改填电脑的局域网 IP，如 http://192.168.43.100:8000",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
}
