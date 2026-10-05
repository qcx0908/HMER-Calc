package com.hmercalc.remote

import com.hmercalc.common.CalculateRequest
import com.hmercalc.common.CalculateResponse
import com.hmercalc.common.Calculator
import javax.inject.Inject

class RemoteCalculator @Inject constructor(
    private val api: CalcApi,
) : Calculator {

    override suspend fun calculate(latex: String, mode: String): CalculateResponse {
        return api.calculate(CalculateRequest(latex = latex, mode = mode))
    }
}
