package com.localsms.app.sync

import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.database.ContentObserver
import android.net.ConnectivityManager
import android.net.Network
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.provider.Telephony
import androidx.core.content.ContextCompat
import com.localsms.app.LocalSmsApp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Service de premier plan : synchronisation en direct.
 *  - observe la base SMS (réception ET envoi) ;
 *  - reprend dès que le réseau revient ;
 *  - signale sa présence et la batterie au PC toutes les 30 s ;
 *  - réessaie avec un délai croissant (5 s → 5 min) si le PC est injoignable.
 */
class SyncService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val trigger = Channel<Unit>(Channel.CONFLATED)
    private val wake = Channel<Unit>(Channel.CONFLATED)
    private var observer: ContentObserver? = null
    private var netCallback: ConnectivityManager.NetworkCallback? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        running = true
        SyncStatusHolder.update { it.copy(serviceRunning = true) }
        val notification = Notifications.build(this, "Synchronisation des SMS active")
        if (Build.VERSION.SDK_INT >= 29) {
            startForeground(Notifications.ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(Notifications.ID, notification)
        }
        val app = application as LocalSmsApp

        observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) { trigger.trySend(Unit) }
        }.also { contentResolver.registerContentObserver(Telephony.Sms.CONTENT_URI, true, it) }

        val cm = getSystemService(ConnectivityManager::class.java)
        netCallback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { wake.trySend(Unit); trigger.trySend(Unit) }
        }.also { cm.registerDefaultNetworkCallback(it) }

        // Boucle de synchronisation
        scope.launch {
            trigger.trySend(Unit) // passage initial : historique + messages manqués
            var backoff = MIN_BACKOFF_MS
            for (ignored in trigger) {
                delay(800) // regroupe les rafales de notifications (SMS multiparties, etc.)
                when (val outcome = app.engine.sync()) {
                    is SyncOutcome.Retry -> {
                        withTimeoutOrNull(backoff) { wake.receive() } // réveillé tôt si le réseau revient
                        backoff = minOf(backoff * 2, MAX_BACKOFF_MS)
                        trigger.trySend(Unit)
                    }
                    is SyncOutcome.Revoked -> { stopSelf(); return@launch }
                    else -> backoff = MIN_BACKOFF_MS
                }
            }
        }
        // Présence + batterie
        scope.launch {
            while (true) {
                if (app.engine.heartbeat() is SyncOutcome.Revoked) { app.engine.refreshStatus("Téléphone révoqué sur le PC.", Phase.ERROR); stopSelf(); break }
                delay(HEARTBEAT_MS)
            }
        }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { stopSelf(); return START_NOT_STICKY }
        trigger.trySend(Unit)
        return START_STICKY
    }

    override fun onDestroy() {
        running = false
        SyncStatusHolder.update { it.copy(serviceRunning = false) }
        observer?.let { contentResolver.unregisterContentObserver(it) }
        netCallback?.let { runCatching { getSystemService(ConnectivityManager::class.java).unregisterNetworkCallback(it) } }
        scope.cancel()
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "com.localsms.app.STOP"
        private const val HEARTBEAT_MS = 30_000L
        private const val MIN_BACKOFF_MS = 5_000L
        private const val MAX_BACKOFF_MS = 300_000L
        @Volatile var running = false

        fun start(context: Context) {
            ContextCompat.startForegroundService(context, Intent(context, SyncService::class.java))
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, SyncService::class.java))
        }
    }
}
