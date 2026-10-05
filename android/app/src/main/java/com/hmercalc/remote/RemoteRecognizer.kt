package com.hmercalc.remote

import android.graphics.Bitmap
import android.util.Base64
import com.hmercalc.common.RecognitionResponse
import com.hmercalc.common.Recognizer
import com.hmercalc.common.RecognizeRequest
import java.io.ByteArrayOutputStream
import javax.inject.Inject

class RemoteRecognizer @Inject constructor(
    private val api: CalcApi,
) : Recognizer {

    override suspend fun recognize(bitmap: Bitmap): RecognitionResponse {
        // 后端预处理也会缩放，这里先压到最长边 1024，减少传输体积。
        val scaled = scaleDown(bitmap, maxEdge = 1024)
        val jpeg = ByteArrayOutputStream().use { out ->
            scaled.compress(Bitmap.CompressFormat.JPEG, 85, out)
            out.toByteArray()
        }
        val base64 = Base64.encodeToString(jpeg, Base64.NO_WRAP)
        return api.recognize(RecognizeRequest(image = base64))
    }

    companion object {
        fun scaleDown(bitmap: Bitmap, maxEdge: Int): Bitmap {
            val longEdge = maxOf(bitmap.width, bitmap.height)
            if (longEdge <= maxEdge) return bitmap
            val ratio = maxEdge.toFloat() / longEdge
            val newW = (bitmap.width * ratio).toInt().coerceAtLeast(1)
            val newH = (bitmap.height * ratio).toInt().coerceAtLeast(1)
            return Bitmap.createScaledBitmap(bitmap, newW, newH, true)
        }
    }
}
