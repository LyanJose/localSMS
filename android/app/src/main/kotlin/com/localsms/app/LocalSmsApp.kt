package com.localsms.app

import android.app.Application
import android.content.Context
import com.localsms.app.data.OutboxDb
import com.localsms.app.data.Prefs
import com.localsms.app.net.ApiClient
import com.localsms.app.net.ApiResult
import com.localsms.app.net.ServerUrl
import com.localsms.app.sync.Notifications
import com.localsms.app.sync.SyncEngine
import com.localsms.app.sync.SyncService
import com.localsms.app.sync.SyncStatusHolder
import com.localsms.app.sync.SyncWorker
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

class LocalSmsApp : Application() {
    val prefs: Prefs by lazy { Prefs(this) }
    val outbox: OutboxDb by lazy { OutboxDb(this) }
    val api: ApiClient by lazy { ApiClient() }
    val engine: SyncEngine by lazy { SyncEngine(this, prefs, outbox, api) }

    override fun onCreate() {
        super.onCreate()
        Notifications.ensureChannel(this)
        SyncStatusHolder.update { it.copy(serviceRunning = SyncService.running) }
        if (prefs.isPaired) SyncWorker.schedulePeriodic(this)
    }

    /** Associe le téléphone au PC. Retourne un message d'erreur, ou null en cas de succès. */
    suspend fun pair(rawUrl: String, code: String, name: String): String? = withContext(Dispatchers.IO) {
        val url = when (val v = ServerUrl.normalize(rawUrl)) {
            is ServerUrl.Result.Valid -> v.url
            is ServerUrl.Result.Invalid -> return@withContext v.reason
        }
        if (code.isBlank()) return@withContext "Saisissez le code d'appairage affiché sur le PC."
        val deviceName = name.trim().ifEmpty { android.os.Build.MODEL ?: "Téléphone" }.take(64)
        when (val r = api.pair(url, code.trim(), prefs.deviceId, deviceName)) {
            is ApiResult.Ok -> {
                if (!r.value.startsWith("lsd_")) return@withContext "Réponse inattendue du serveur."
                prefs.serverUrl = url
                prefs.deviceToken = r.value
                prefs.deviceName = deviceName
                prefs.serviceEnabled = true
                outbox.reset() // nouvelle association : envoi complet de l'historique (doublons ignorés)
                engine.refreshStatus()
                SyncWorker.schedulePeriodic(this@LocalSmsApp)
                null
            }
            is ApiResult.HttpError -> when (r.code) {
                403 -> "Code invalide ou expiré. Générez-en un nouveau sur le PC."
                429 -> "Trop de tentatives. Patientez quelques minutes."
                else -> "Erreur du serveur (${r.code}) : ${r.message}"
            }
            is ApiResult.NetworkError -> "Serveur injoignable ($url). Vérifiez l'adresse, le Wi-Fi ou le câble USB. ${r.message}"
        }
    }

    suspend fun unpair() = withContext(Dispatchers.IO) {
        if (prefs.isPaired) api.unpair(prefs.serverUrl, prefs.deviceToken) // au mieux ; ignoré si le PC est éteint
        SyncService.stop(this@LocalSmsApp)
        SyncWorker.cancelAll(this@LocalSmsApp)
        prefs.clearPairing()
        outbox.reset()
        engine.refreshStatus()
    }

    fun startService(context: Context = this) {
        prefs.serviceEnabled = true
        SyncService.start(context)
    }

    fun stopService(context: Context = this) {
        prefs.serviceEnabled = false
        SyncService.stop(context)
    }
}
