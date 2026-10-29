package com.localsms.app.sync

import android.content.Context
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.work.BackoffPolicy
import androidx.work.CoroutineWorker
import androidx.work.Constraints
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.ForegroundInfo
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.OutOfQuotaPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.localsms.app.LocalSmsApp
import java.util.concurrent.TimeUnit

/**
 * Filet de sécurité hors service de premier plan : déclenché à la réception d'un SMS
 * et toutes les 15 minutes (Doze, service tué par le constructeur, etc.).
 */
class SyncWorker(context: Context, params: WorkerParameters) : CoroutineWorker(context, params) {

    override suspend fun doWork(): Result {
        val engine = (applicationContext as LocalSmsApp).engine
        return when (val outcome = engine.sync()) {
            is SyncOutcome.Retry -> Result.retry()
            else -> {
                engine.heartbeat()
                Result.success()
            }
        }
    }

    override suspend fun getForegroundInfo(): ForegroundInfo {
        val n = Notifications.build(applicationContext, "Synchronisation des SMS…")
        return if (Build.VERSION.SDK_INT >= 29) {
            ForegroundInfo(Notifications.ID + 1, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            ForegroundInfo(Notifications.ID + 1, n)
        }
    }

    companion object {
        private const val ONE_SHOT = "localsms-sync-now"
        private const val PERIODIC = "localsms-sync-periodic"
        private val NETWORK = Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build()

        /** Synchronisation immédiate (accélérée) ; REPLACE inutile : un seul passage en attente suffit. */
        fun runNow(context: Context) {
            val req = OneTimeWorkRequestBuilder<SyncWorker>()
                .setExpedited(OutOfQuotaPolicy.RUN_AS_NON_EXPEDITED_WORK_IF_QUOTA_EXCEEDED)
                .setConstraints(NETWORK)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
                .build()
            WorkManager.getInstance(context).enqueueUniqueWork(ONE_SHOT, ExistingWorkPolicy.APPEND_OR_REPLACE, req)
        }

        fun schedulePeriodic(context: Context) {
            val req = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(NETWORK)
                .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 1, TimeUnit.MINUTES)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(PERIODIC, ExistingPeriodicWorkPolicy.UPDATE, req)
        }

        fun cancelAll(context: Context) {
            val wm = WorkManager.getInstance(context)
            wm.cancelUniqueWork(ONE_SHOT)
            wm.cancelUniqueWork(PERIODIC)
        }
    }
}
