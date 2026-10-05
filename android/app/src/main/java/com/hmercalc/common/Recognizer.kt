package com.hmercalc.common

import android.graphics.Bitmap

// 识别能力抽象（UI 只依赖接口，可替换为本地实现做单元测试）。
interface Recognizer {
    suspend fun recognize(bitmap: Bitmap): RecognitionResponse
}
