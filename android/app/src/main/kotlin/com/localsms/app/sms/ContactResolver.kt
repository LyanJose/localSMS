package com.localsms.app.sms

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.ContactsContract
import androidx.core.content.ContextCompat

/** Résout un numéro en nom de contact (optionnel : nécessite READ_CONTACTS), avec cache. */
class ContactResolver(private val context: Context) {
    private val cache = HashMap<String, String?>()

    private val allowed: Boolean
        get() = ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED

    fun nameFor(address: String): String? {
        if (!allowed || address.any { it.isLetter() }) return null
        return cache.getOrPut(address) {
            try {
                val uri = Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(address))
                context.contentResolver.query(uri, arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null)
                    ?.use { if (it.moveToFirst()) it.getString(0)?.take(128) else null }
            } catch (e: Exception) {
                null
            }
        }
    }
}
