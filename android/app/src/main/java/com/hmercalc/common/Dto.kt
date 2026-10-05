package com.hmercalc.common

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// 与后端 app/common/models.py 字段一一对应（snake_case 用 @SerialName 映射）。
// 后端 status 取值：识别 = SUCCESS|ERROR；计算 = SUCCESS|PARSE_ERROR|COMPUTE_ERROR。

@Serializable
data class RecognizeRequest(
    @SerialName("image") val image: String,
)

@Serializable
data class Token(
    @SerialName("text") val text: String,
    @SerialName("confidence") val confidence: Double,
    @SerialName("range_start") val rangeStart: Int = 0,
    @SerialName("range_end") val rangeEnd: Int = 0,
    @SerialName("alternatives") val alternatives: List<String> = emptyList(),
)

@Serializable
data class RecognitionResponse(
    @SerialName("latex") val latex: String = "",
    @SerialName("confidence") val confidence: Double = 0.0,
    @SerialName("tokens") val tokens: List<Token> = emptyList(),
    @SerialName("status") val status: String = "SUCCESS",
    @SerialName("message") val message: String? = null,
)

@Serializable
data class CalculateRequest(
    @SerialName("latex") val latex: String,
    // 组长订正 2026-10：新增 "auto"（智能换算），作为客户端默认；"deg"/"rad" 仍可显式选择
    @SerialName("mode") val mode: String = Modes.AUTO,
)

@Serializable
data class CalculateResponse(
    @SerialName("latex") val latex: String = "",
    @SerialName("value") val value: Double? = null,
    @SerialName("value_latex") val valueLatex: String? = null,
    @SerialName("status") val status: String = "SUCCESS",
    @SerialName("message") val message: String? = null,
)
