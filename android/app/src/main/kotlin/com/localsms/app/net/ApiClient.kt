package com.localsms.app.net

import com.localsms.app.data.SmsItem
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

sealed class ApiResult<out T> {
    data class Ok<T>(val value: T) : ApiResult<T>()
    data class HttpError(val code: Int, val message: String) : ApiResult<Nothing>()
    data class NetworkError(val message: String) : ApiResult<Nothing>()
}

data class BatchAck(val received: Int, val inserted: Int, val duplicates: Int)

/** Client REST de l'API LocalSMS (voir /docs sur le PC). */
class ApiClient(
    private val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(8, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build(),
) {
    private val json = "application/json; charset=utf-8".toMediaType()

    fun pair(baseUrl: String, code: String, deviceId: String, deviceName: String): ApiResult<String> {
        val body = JSONObject().put("code", code).put("device_id", deviceId).put("device_name", deviceName)
        return call(Request.Builder().url("$baseUrl/api/v1/pair").post(body.toString().toRequestBody(json)).build())
            .map { it.optString("device_token") }
    }

    fun uploadBatch(baseUrl: String, token: String, items: List<SmsItem>, total: Long, remaining: Long): ApiResult<BatchAck> {
        val arr = JSONArray()
        for (s in items) {
            arr.put(
                JSONObject().put("sms_id", s.smsId).put("address", s.address).put("body", s.body)
                    .put("date_ms", s.dateMs).put("type", s.type).put("read", s.read)
                    .apply { if (s.contactName != null) put("contact_name", s.contactName) },
            )
        }
        val body = JSONObject().put("messages", arr).put("sync_total", total).put("sync_remaining", remaining)
        return call(authed(baseUrl, "/api/v1/sms/batch", token).post(body.toString().toRequestBody(json)).build())
            .map { BatchAck(it.optInt("received"), it.optInt("inserted"), it.optInt("duplicates")) }
    }

    fun heartbeat(baseUrl: String, token: String, battery: Int?, charging: Boolean?, appVersion: String, pending: Long): ApiResult<Unit> {
        val body = JSONObject().put("app_version", appVersion).put("pending", pending)
        if (battery != null) body.put("battery", battery)
        if (charging != null) body.put("charging", charging)
        return call(authed(baseUrl, "/api/v1/device/heartbeat", token).post(body.toString().toRequestBody(json)).build()).map { }
    }

    fun unpair(baseUrl: String, token: String): ApiResult<Unit> =
        call(authed(baseUrl, "/api/v1/device/self", token).delete().build()).map { }

    private fun authed(baseUrl: String, path: String, token: String) =
        Request.Builder().url(baseUrl + path).header("Authorization", "Bearer $token")

    private fun call(request: Request): ApiResult<JSONObject> = try {
        http.newCall(request).execute().use { resp ->
            val text = resp.body?.string().orEmpty()
            if (resp.isSuccessful) {
                ApiResult.Ok(if (text.isBlank()) JSONObject() else JSONObject(text))
            } else {
                ApiResult.HttpError(resp.code, detail(text) ?: resp.message)
            }
        }
    } catch (e: IOException) {
        ApiResult.NetworkError(e.message ?: "Réseau indisponible")
    } catch (e: JSONException) {
        ApiResult.NetworkError("Réponse invalide du serveur")
    } catch (e: IllegalArgumentException) {
        ApiResult.NetworkError("Adresse du serveur invalide")
    }

    private fun detail(text: String): String? = try {
        JSONObject(text).opt("detail")?.toString()?.take(200)
    } catch (e: JSONException) {
        null
    }

    private inline fun <T, R> ApiResult<T>.map(f: (T) -> R): ApiResult<R> = when (this) {
        is ApiResult.Ok -> ApiResult.Ok(f(value))
        is ApiResult.HttpError -> this
        is ApiResult.NetworkError -> this
    }
}
