package com.localsms.app.data

import android.content.ContentValues
import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.database.sqlite.SQLiteOpenHelper

/** Un SMS lu dans le fournisseur Android. */
data class SmsItem(
    val smsId: Long,
    val address: String,
    val body: String,
    val dateMs: Long,
    val type: Int,
    val read: Boolean,
    val contactName: String? = null,
)

data class QueuedSms(val rowId: Long, val sms: SmsItem)

/**
 * File d'attente persistante (SQLite) des SMS à envoyer au PC.
 *
 * Les SMS sont copiés ici AVANT l'envoi et ne sont supprimés qu'après l'accusé de réception du
 * serveur : coupure Wi-Fi, PC éteint, application tuée ou redémarrage du téléphone ne perdent rien.
 * Le curseur « dernier SMS mis en file » est stocké dans la même base et avancé dans la même
 * transaction que l'ajout, ce qui garantit l'absence de trou comme de répétition.
 */
class OutboxDb(context: Context) : SQLiteOpenHelper(context.applicationContext, "outbox.db", null, 1) {

    override fun onCreate(db: SQLiteDatabase) {
        db.execSQL(
            """CREATE TABLE outbox (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 sms_id INTEGER NOT NULL, address TEXT NOT NULL, body TEXT NOT NULL,
                 date_ms INTEGER NOT NULL, type INTEGER NOT NULL, read INTEGER NOT NULL,
                 contact_name TEXT)"""
        )
        db.execSQL("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    }

    override fun onUpgrade(db: SQLiteDatabase, oldVersion: Int, newVersion: Int) = Unit

    fun cursor(): Long = readableDatabase.rawQuery("SELECT value FROM meta WHERE key = 'cursor'", null).use {
        if (it.moveToFirst()) it.getString(0).toLongOrNull() ?: 0L else 0L
    }

    fun enqueue(items: List<SmsItem>, newCursor: Long) {
        val db = writableDatabase
        db.beginTransaction()
        try {
            for (s in items) {
                val cv = ContentValues().apply {
                    put("sms_id", s.smsId); put("address", s.address); put("body", s.body)
                    put("date_ms", s.dateMs); put("type", s.type); put("read", if (s.read) 1 else 0)
                    put("contact_name", s.contactName)
                }
                db.insertOrThrow("outbox", null, cv)
            }
            setCursor(db, newCursor)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun peek(limit: Int): List<QueuedSms> {
        val out = ArrayList<QueuedSms>(limit)
        readableDatabase.rawQuery(
            "SELECT id, sms_id, address, body, date_ms, type, read, contact_name FROM outbox ORDER BY id LIMIT ?",
            arrayOf(limit.toString()),
        ).use { c ->
            while (c.moveToNext()) {
                out += QueuedSms(
                    c.getLong(0),
                    SmsItem(c.getLong(1), c.getString(2), c.getString(3), c.getLong(4), c.getInt(5), c.getInt(6) == 1, c.getString(7)),
                )
            }
        }
        return out
    }

    fun delete(rowIds: List<Long>) {
        if (rowIds.isEmpty()) return
        val db = writableDatabase
        db.beginTransaction()
        try {
            rowIds.chunked(500).forEach { chunk ->
                db.execSQL("DELETE FROM outbox WHERE id IN (${chunk.joinToString(",")})")
            }
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    fun count(): Long = readableDatabase.rawQuery("SELECT COUNT(*) FROM outbox", null).use {
        if (it.moveToFirst()) it.getLong(0) else 0L
    }

    /** Efface la file et remet le curseur à zéro : le prochain passage renverra tout l'historique. */
    fun reset() {
        val db = writableDatabase
        db.beginTransaction()
        try {
            db.execSQL("DELETE FROM outbox")
            setCursor(db, 0L)
            db.setTransactionSuccessful()
        } finally {
            db.endTransaction()
        }
    }

    private fun setCursor(db: SQLiteDatabase, value: Long) {
        db.execSQL("INSERT OR REPLACE INTO meta (key, value) VALUES ('cursor', ?)", arrayOf(value.toString()))
    }
}
