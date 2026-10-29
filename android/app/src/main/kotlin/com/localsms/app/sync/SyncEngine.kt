package com.localsms.app.sync

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.os.BatteryManager
import androidx.core.content.ContextCompat
import com.localsms.app.BuildConfig
import com.localsms.app.data.OutboxDb
import com.localsms.app.data.Prefs
import com.localsms.app.net.ApiClient
import com.localsms.app.net.ApiResult
import com.localsms.app.sms.ContactResolver
import com.localsms.app.sms.SmsReader
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/** Résultat d'un passage de synchronisation. */
sealed class SyncOutcome {
    object Done : SyncOutcome()
    object NotPaired : SyncOutcome()
    object PermissionMissing : SyncOutcome()
    /** Jeton révoqué par le PC : il faut réassocier le téléphone. */
    object Revoked : SyncOutcome()
    /** Échec temporaire (PC éteint, Wi-Fi coupé, erreur 5xx…) : à réessayer plus tard. */
    data class Retry(val reason: String) : SyncOutcome()
}

/**
 * Cœur de la synchronisation :
 *  1. lit les nouveaux SMS du fournisseur Android (curseur = dernier _id lu) et les met en file ;
 *  2. envoie la file par lots de 200 ; un lot n'est supprimé qu'après accusé de réception.
 * Le serveur ignore les doublons : renvoyer un lot (après coupure) est toujours sans danger.
 */
class SyncEngine(
    private val context: Context,
    private val prefs: Prefs,
    private val db: OutboxDb,
    private val api: ApiClient,
) {
    private val mutex = Mutex()

    fun refreshStatus(message: String? = null, phase: Phase? = null) {
        val pairedNow = prefs.isPaired
        SyncStatusHolder.update {
            it.copy(
                paired = pairedNow,
                phase = when {
                    !pairedNow -> Phase.NOT_PAIRED
                    phase != null -> phase
                    it.phase == Phase.NOT_PAIRED -> Phase.IDLE
                    else -> it.phase
                },
                pending = db.count(),
                lastSyncAt = prefs.lastSyncAt,
                message = if (message != null || phase != null) message else it.message,
                serverUrl = prefs.serverUrl,
                deviceName = prefs.deviceName,
            )
        }
    }

    suspend fun sync(): SyncOutcome = mutex.withLock {
        if (!prefs.isPaired) { refreshStatus(); return SyncOutcome.NotPaired }
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.READ_SMS) != PackageManager.PERMISSION_GRANTED) {
            refreshStatus("Autorisation de lire les SMS manquante.", Phase.ERROR)
            return SyncOutcome.PermissionMissing
        }
        refreshStatus(null, Phase.SYNCING)
        try {
            scanIntoOutbox()
            val outcome = uploadOutbox()
            when (outcome) {
                is SyncOutcome.Done -> refreshStatus(null, Phase.IDLE)
                is SyncOutcome.Retry -> refreshStatus(outcome.reason, Phase.OFFLINE)
                is SyncOutcome.Revoked -> refreshStatus("Ce téléphone a été révoqué sur le PC. Réassociez-le.", Phase.ERROR)
                else -> refreshStatus()
            }
            outcome
        } catch (e: SecurityException) {
            refreshStatus("Autorisation SMS refusée par le système.", Phase.ERROR)
            SyncOutcome.PermissionMissing
        } catch (e: Exception) {
            refreshStatus("Erreur inattendue : ${e.javaClass.simpleName}", Phase.ERROR)
            SyncOutcome.Retry(e.javaClass.simpleName)
        }
    }

    private fun scanIntoOutbox() {
        val contacts = ContactResolver(context)
        var cursor = db.cursor()
        while (true) {
            val items = SmsReader.readAfter(context, cursor, SCAN_BATCH)
            if (items.isEmpty()) break
            val enriched = items.map { it.copy(contactName = contacts.nameFor(it.address)) }
            cursor = items.last().smsId
            db.enqueue(enriched, cursor)
            refreshStatus()
            if (items.size < SCAN_BATCH) break
        }
    }

    private fun uploadOutbox(): SyncOutcome {
        val base = prefs.serverUrl
        val token = prefs.deviceToken
        var limit = UPLOAD_BATCH
        val total = db.count()
        var sent = 0L
        while (true) {
            val batch = db.peek(limit)
            if (batch.isEmpty()) break
            val remaining = db.count() - batch.size
            when (val r = api.uploadBatch(base, token, batch.map { it.sms }, total, remaining)) {
                is ApiResult.Ok -> {
                    db.delete(batch.map { it.rowId })
                    sent += batch.size
                    limit = UPLOAD_BATCH
                    prefs.lastSyncAt = System.currentTimeMillis()
                    refreshStatus()
                }
                is ApiResult.NetworkError -> return SyncOutcome.Retry("PC injoignable : ${r.message}")
                is ApiResult.HttpError -> when (r.code) {
                    401, 403 -> return SyncOutcome.Revoked
                    400, 413, 422 -> {
                        // Lot refusé : on réduit la taille pour isoler et abandonner le message fautif
                        // (sinon il bloquerait toute la file indéfiniment).
                        if (batch.size == 1) { db.delete(listOf(batch[0].rowId)) } else { limit = maxOf(1, batch.size / 2) }
                    }
                    else -> return SyncOutcome.Retry("Serveur : erreur ${r.code}")
                }
            }
        }
        return SyncOutcome.Done
    }

    /** Envoie l'état du téléphone (batterie, file d'attente) ; sert aussi à détecter la révocation. */
    fun heartbeat(): SyncOutcome {
        if (!prefs.isPaired) return SyncOutcome.NotPaired
        val intent: Intent? = context.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val level = intent?.getIntExtra(BatteryManager.EXTRA_LEVEL, -1) ?: -1
        val scale = intent?.getIntExtra(BatteryManager.EXTRA_SCALE, -1) ?: -1
        val battery = if (level >= 0 && scale > 0) (level * 100 / scale).coerceIn(0, 100) else null
        val status = intent?.getIntExtra(BatteryManager.EXTRA_STATUS, -1) ?: -1
        val charging = status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        return when (val r = api.heartbeat(prefs.serverUrl, prefs.deviceToken, battery, charging, BuildConfig.VERSION_NAME, db.count())) {
            is ApiResult.Ok -> SyncOutcome.Done
            is ApiResult.NetworkError -> SyncOutcome.Retry(r.message)
            is ApiResult.HttpError -> if (r.code == 401 || r.code == 403) SyncOutcome.Revoked else SyncOutcome.Retry("Serveur : erreur ${r.code}")
        }
    }

    /** « Resynchroniser tout » : le serveur ignore les doublons, aucun risque de duplication. */
    fun resetForFullSync() {
        db.reset()
        refreshStatus()
    }

    private companion object {
        const val SCAN_BATCH = 500
        const val UPLOAD_BATCH = 200
    }
}
