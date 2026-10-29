package com.localsms.app.sms

import android.content.Context
import android.provider.Telephony
import com.localsms.app.data.SmsItem

/** Lecture de l'historique SMS via le fournisseur de contenu Android (permission READ_SMS). */
object SmsReader {
    private val PROJECTION = arrayOf(
        Telephony.Sms._ID, Telephony.Sms.ADDRESS, Telephony.Sms.BODY,
        Telephony.Sms.DATE, Telephony.Sms.TYPE, Telephony.Sms.READ,
    )
    // On ignore les brouillons (type 3) : ils ne sont ni reçus ni envoyés.
    private val SELECTION = "${Telephony.Sms._ID} > ? AND ${Telephony.Sms.TYPE} != ${Telephony.Sms.MESSAGE_TYPE_DRAFT}"

    /** Lit au plus [limit] SMS dont l'identifiant est supérieur à [afterId], du plus ancien au plus récent. */
    fun readAfter(context: Context, afterId: Long, limit: Int): List<SmsItem> {
        val out = ArrayList<SmsItem>(limit)
        context.contentResolver.query(
            Telephony.Sms.CONTENT_URI, PROJECTION, SELECTION, arrayOf(afterId.toString()),
            "${Telephony.Sms._ID} ASC",
        )?.use { c ->
            val iId = c.getColumnIndexOrThrow(Telephony.Sms._ID)
            val iAddr = c.getColumnIndexOrThrow(Telephony.Sms.ADDRESS)
            val iBody = c.getColumnIndexOrThrow(Telephony.Sms.BODY)
            val iDate = c.getColumnIndexOrThrow(Telephony.Sms.DATE)
            val iType = c.getColumnIndexOrThrow(Telephony.Sms.TYPE)
            val iRead = c.getColumnIndexOrThrow(Telephony.Sms.READ)
            while (out.size < limit && c.moveToNext()) {
                val date = c.getLong(iDate)
                if (date <= 0L) continue // date invalide : refusée par le serveur, inutile de l'envoyer
                out += SmsItem(
                    smsId = c.getLong(iId),
                    address = (c.getString(iAddr) ?: "").trim().ifEmpty { "inconnu" },
                    body = c.getString(iBody) ?: "",
                    dateMs = date,
                    type = c.getInt(iType).coerceIn(1, 6),
                    read = c.getInt(iRead) == 1,
                )
            }
        }
        return out
    }

    /** Nombre de SMS restant à lire après [afterId] (pour la progression). */
    fun countAfter(context: Context, afterId: Long): Long =
        context.contentResolver.query(
            Telephony.Sms.CONTENT_URI, arrayOf(Telephony.Sms._ID), SELECTION, arrayOf(afterId.toString()), null,
        )?.use { it.count.toLong() } ?: 0L
}
