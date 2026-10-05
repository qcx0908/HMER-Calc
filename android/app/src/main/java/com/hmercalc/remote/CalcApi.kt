package com.hmercalc.remote

import com.hmercalc.common.CalculateRequest
import com.hmercalc.common.CalculateResponse
import com.hmercalc.common.RecognitionResponse
import com.hmercalc.common.RecognizeRequest
import retrofit2.http.Body
import retrofit2.http.POST

// 与后端路由对齐：POST /recognize、POST /calculate（路径前缀由 baseUrl 决定）。
interface CalcApi {
    @POST("recognize")
    suspend fun recognize(@Body body: RecognizeRequest): RecognitionResponse

    @POST("calculate")
    suspend fun calculate(@Body body: CalculateRequest): CalculateResponse
}
