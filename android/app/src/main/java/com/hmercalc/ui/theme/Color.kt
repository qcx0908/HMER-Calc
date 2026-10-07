package com.hmercalc.ui.theme

import androidx.compose.ui.graphics.Color

// 高级感配色（组长订正 2026-10-07）：低饱和、克制。深邃靛蓝为主色、暖铜为点缀、暖白为底。
// 全项目统一走这一套，不跟随系统壁纸取色（见 Theme.kt dynamicColor=false），保证不同设备观感一致。

// —— 浅色 ——
val InkBlue = Color(0xFF2E4A6B)          // primary：主色（按钮 / 选中 / 标题强调）
val SlateBlue = Color(0xFF5A7090)        // secondary：次级（图标 / 辅助色块）
val Copper = Color(0xFFB0825A)           // tertiary：暖铜点缀（数值结果 / 高亮）
val WarmWhite = Color(0xFFF7F8FA)        // background：暖白底（非纯白，更柔和）
val CardWhite = Color(0xFFFFFFFF)        // surface：卡片纯白，与底拉开层次
val InkText = Color(0xFF1B1F24)          // onBackground/onSurface：深墨灰（非纯黑）
val SoftOutline = Color(0xFF8A919B)      // outline：次级说明文字 / 边框
val SoftOutlineVariant = Color(0xFFD6DAE0) // outlineVariant：卡片细边框

// —— 深色 ——
val MistBlue = Color(0xFF9FBFE8)         // primary
val MistSlate = Color(0xFFB7C6DC)        // secondary
val WarmCopper = Color(0xFFE0B48C)       // tertiary
val InkBackground = Color(0xFF111418)    // background
val InkSurface = Color(0xFF191C20)       // surface
