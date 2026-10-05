package com.hmercalc.remote

import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.Response

// 运行期可改后端地址：Retrofit 用占位 baseUrl，真实 host/port 由这里注入。
// 修改 BackendUrlHolder.baseUrl 后立即生效，无需重建 Retrofit。
object BackendUrlHolder {
    @Volatile
    var baseUrl: String = "http://10.0.2.2:8000" // Android 模拟器访问宿主机 8000 端口
}

class DynamicBaseUrlInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val base = BackendUrlHolder.baseUrl.toHttpUrlOrNull()
            ?: return chain.proceed(request)

        val newUrl = request.url.newBuilder()
            .scheme(base.scheme)
            .host(base.host)
            .port(base.port)
            .build()
        return chain.proceed(request.newBuilder().url(newUrl).build())
    }
}
