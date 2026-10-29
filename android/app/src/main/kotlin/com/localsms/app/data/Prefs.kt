package com.localsms.app.data

import android.content.Context
import android.content.SharedPreferences
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey
import java.util.UUID

/**
 * Réglages et jeton d'appareil, chiffrés (AES-256) avec une clé stockée dans l'Android Keystore.
 * Le jeton n'est jamais journalisé ni sauvegardé dans le cloud (allowBackup=false).
 */
class Prefs(context: Context) {
    private val sp: SharedPreferences = create(context.applicationContext)

    var serverUrl: String
        get() = sp.getString(K_URL, "") ?: ""
        set(v) = sp.edit().putString(K_URL, v).apply()

    var deviceToken: String
        get() = sp.getString(K_TOKEN, "") ?: ""
        set(v) = sp.edit().putString(K_TOKEN, v).apply()

    var deviceName: String
        get() = sp.getString(K_NAME, "") ?: ""
        set(v) = sp.edit().putString(K_NAME, v).apply()

    /** Le service de synchronisation en continu doit-il tourner (relancé au démarrage) ? */
    var serviceEnabled: Boolean
        get() = sp.getBoolean(K_SERVICE, true)
        set(v) = sp.edit().putBoolean(K_SERVICE, v).apply()

    var lastSyncAt: Long
        get() = sp.getLong(K_LAST_SYNC, 0L)
        set(v) = sp.edit().putLong(K_LAST_SYNC, v).apply()

    val isPaired: Boolean get() = serverUrl.isNotEmpty() && deviceToken.isNotEmpty()

    /** Identifiant stable de cette installation (généré une fois). */
    val deviceId: String
        @Synchronized get() {
            val existing = sp.getString(K_DEVICE_ID, null)
            if (!existing.isNullOrEmpty()) return existing
            val id = UUID.randomUUID().toString()
            sp.edit().putString(K_DEVICE_ID, id).apply()
            return id
        }

    fun clearPairing() {
        sp.edit().remove(K_TOKEN).remove(K_URL).remove(K_LAST_SYNC).apply()
    }

    private companion object {
        const val FILE = "localsms_secure"
        const val K_URL = "server_url"
        const val K_TOKEN = "device_token"
        const val K_NAME = "device_name"
        const val K_SERVICE = "service_enabled"
        const val K_LAST_SYNC = "last_sync_at"
        const val K_DEVICE_ID = "device_id"

        fun create(ctx: Context): SharedPreferences = try {
            build(ctx)
        } catch (e: Exception) {
            // Keystore corrompu (restauration, changement de verrouillage…) : on repart de zéro.
            ctx.deleteSharedPreferences(FILE)
            build(ctx)
        }

        fun build(ctx: Context): SharedPreferences {
            val key = MasterKey.Builder(ctx).setKeyScheme(MasterKey.KeyScheme.AES256_GCM).build()
            return EncryptedSharedPreferences.create(
                ctx, FILE, key,
                EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
            )
        }
    }
}
