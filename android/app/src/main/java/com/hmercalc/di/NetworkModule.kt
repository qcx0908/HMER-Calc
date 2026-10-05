package com.hmercalc.di

import com.hmercalc.common.Calculator
import com.hmercalc.common.Recognizer
import com.hmercalc.remote.CalcApi
import com.hmercalc.remote.DynamicBaseUrlInterceptor
import com.hmercalc.remote.RemoteCalculator
import com.hmercalc.remote.RemoteRecognizer
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideJson(): Json = Json {
        ignoreUnknownKeys = true // 后端新增字段时向前兼容
        explicitNulls = false
    }

    @Provides
    @Singleton
    fun provideOkHttpClient(): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = HttpLoggingInterceptor.Level.BASIC
        }
        return OkHttpClient.Builder()
            .addInterceptor(DynamicBaseUrlInterceptor())
            .addInterceptor(logging)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .build()
    }

    @Provides
    @Singleton
    fun provideCalcApi(client: OkHttpClient, json: Json): CalcApi {
        val contentType = "application/json".toMediaType()
        return Retrofit.Builder()
            // 占位 baseUrl；真实 host/port 由 DynamicBaseUrlInterceptor 注入
            .baseUrl("http://localhost/")
            .client(client)
            .addConverterFactory(json.asConverterFactory(contentType))
            .build()
            .create(CalcApi::class.java)
    }

    @Provides
    @Singleton
    fun provideRecognizer(api: CalcApi): Recognizer = RemoteRecognizer(api)

    @Provides
    @Singleton
    fun provideCalculator(api: CalcApi): Calculator = RemoteCalculator(api)
}
