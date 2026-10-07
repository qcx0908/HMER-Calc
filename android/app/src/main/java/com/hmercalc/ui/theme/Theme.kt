package com.hmercalc.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

// 浅色：深邃靛蓝 + 暖铜点缀 + 暖白底，层次靠「背景/卡片/细边框」拉开，避免纯白惨白
private val LightColorScheme = lightColorScheme(
    primary = InkBlue,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE5F0),
    onPrimaryContainer = Color(0xFF16273E),
    secondary = SlateBlue,
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE6ECF3),
    onSecondaryContainer = Color(0xFF24364C),
    tertiary = Copper,
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFF0E3D6),
    onTertiaryContainer = Color(0xFF3A2B1C),
    background = WarmWhite,
    onBackground = InkText,
    surface = CardWhite,
    onSurface = InkText,
    surfaceVariant = Color(0xFFEDF0F4),
    onSurfaceVariant = Color(0xFF454A52),
    outline = SoftOutline,
    outlineVariant = SoftOutlineVariant,
    error = Color(0xFFB3261E),
)

// 深色：同色系提亮，保证可读性
private val DarkColorScheme = darkColorScheme(
    primary = MistBlue,
    onPrimary = Color(0xFF12253A),
    primaryContainer = InkBlue,
    onPrimaryContainer = Color(0xFFDCE5F0),
    secondary = MistSlate,
    onSecondary = Color(0xFF1C2A3A),
    tertiary = WarmCopper,
    onTertiary = Color(0xFF3A2B1C),
    background = InkBackground,
    onBackground = Color(0xFFE5E8EC),
    surface = InkSurface,
    onSurface = Color(0xFFE5E8EC),
    surfaceVariant = Color(0xFF2A2E34),
    onSurfaceVariant = Color(0xFFC0C6CE),
    outline = Color(0xFF7A828C),
    outlineVariant = Color(0xFF3A3F46),
    error = Color(0xFFF2B8B5),
)

@Composable
fun HMERCalcTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // 组长订正 2026-10-07：关闭壁纸动态取色，统一用上面的高级感配色，
    // 避免 Android 12+ 设备因壁纸不同导致 App 配色五花八门（普适性要求）。
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content,
    )
}
