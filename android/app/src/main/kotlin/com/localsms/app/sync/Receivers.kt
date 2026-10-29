package com.localsms.app.sync

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.provider.Telephony
import com.localsms.app.LocalSmsApp

/**
 * Déclenché à la réception d'un SMS. On ne lit pas le contenu de l'intent : la synchronisation lit
 * le fournisseur SMS (source unique de vérité), ce qui évite les doublons et les écarts d'horodatage.
 */
class SmsReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Telephony.Sms.Intents.SMS_RECEIVED_ACTION) return
        val app = context.applicationContext as LocalSmsApp
        if (!app.prefs.isPaired) return
        // Si le service tourne, son ContentObserver s'en charge ; sinon le travail accéléré prend le relais.
        if (!SyncService.running) SyncWorker.runNow(context.applicationContext)
    }
}

/** Relance la synchronisation après un redémarrage du téléphone ou une mise à jour de l'application. */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val app = context.applicationContext as LocalSmsApp
        if (!app.prefs.isPaired) return
        SyncWorker.schedulePeriodic(context.applicationContext)
        if (app.prefs.serviceEnabled) {
            try {
                SyncService.start(context.applicationContext)
            } catch (e: Exception) {
                // Démarrage en arrière-plan refusé par le système : le travail périodique prend le relais.
                SyncWorker.runNow(context.applicationContext)
            }
        }
    }
}
