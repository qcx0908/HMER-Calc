package com.hmercalc.common

// 计算能力抽象。mode = "deg" | "rad" | "auto"（组长订正 2026-10：新增 auto 智能换算）。
interface Calculator {
    suspend fun calculate(latex: String, mode: String): CalculateResponse
}
