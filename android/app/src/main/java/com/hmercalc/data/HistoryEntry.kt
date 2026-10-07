package com.hmercalc.data

import kotlinx.serialization.Serializable

// 一条历史记录：一次「拍照/选图 → 识别 → 计算」的完整快照。
// 图片存应用私有目录（imagePath 指向 JPEG 缩略图文件），元数据经 DataStore 以 JSON 持久化。
// 与后端契约无关（后端契约在 common/Dto.kt），故放在 data 包。
@Serializable
data class HistoryEntry(
    val id: Long,                    // 时间戳，兼作缩略图文件名（{id}.jpg）
    val imagePath: String,           // 缩略图 JPEG 的绝对路径
    val latex: String,               // 识别出的 LaTeX
    val confidence: Double,          // 识别置信度
    val value: Double? = null,       // 计算结果（计算失败/异常时为 null）
    val valueLatex: String? = null,  // 结果的精确值 LaTeX（可能为 null）
    val status: String? = null,      // 计算状态：SUCCESS / PARSE_ERROR / COMPUTE_ERROR / null(网络异常)
)
