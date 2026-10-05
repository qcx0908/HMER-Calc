package com.hmercalc.common

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import androidx.exifinterface.media.ExifInterface

// 图片解码工具：采样缩放 + EXIF 方向纠正（否则识别端可能拿到旋转过的图）。
object BitmapUtils {

    fun decodeBitmap(context: Context, uri: Uri, maxEdge: Int = 2000): Bitmap? {
        // 1. 读取 EXIF 方向（相机通常只写方向、不旋转像素）
        var orientation = ExifInterface.ORIENTATION_NORMAL
        runCatching {
            context.contentResolver.openInputStream(uri)?.use { input ->
                orientation = ExifInterface(input).getAttributeInt(
                    ExifInterface.TAG_ORIENTATION,
                    ExifInterface.ORIENTATION_NORMAL,
                )
            }
        }

        // 2. 只读尺寸，算采样率（避免大图 OOM）
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, bounds)
        }
        val longEdge = maxOf(bounds.outWidth, bounds.outHeight)
        var sampleSize = 1
        while (longEdge / (sampleSize * 2) >= maxEdge) sampleSize *= 2

        // 3. 采样解码
        val opts = BitmapFactory.Options().apply { inSampleSize = sampleSize }
        val bitmap = context.contentResolver.openInputStream(uri)?.use {
            BitmapFactory.decodeStream(it, null, opts)
        } ?: return null

        // 4. 应用 EXIF 旋转
        val matrix = Matrix()
        when (orientation) {
            ExifInterface.ORIENTATION_ROTATE_90 -> matrix.postRotate(90f)
            ExifInterface.ORIENTATION_ROTATE_180 -> matrix.postRotate(180f)
            ExifInterface.ORIENTATION_ROTATE_270 -> matrix.postRotate(270f)
            ExifInterface.ORIENTATION_FLIP_HORIZONTAL -> matrix.postScale(-1f, 1f)
            ExifInterface.ORIENTATION_FLIP_VERTICAL -> matrix.postScale(1f, -1f)
            else -> return bitmap
        }
        val rotated = Bitmap.createBitmap(bitmap, 0, 0, bitmap.width, bitmap.height, matrix, true)
        if (rotated != bitmap) bitmap.recycle()
        return rotated
    }
}
