package com.localsms.app.sync

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

enum class Phase { NOT_PAIRED, IDLE, SYNCING, OFFLINE, ERROR }

data class SyncStatus(
    val paired: Boolean = false,
    val phase: Phase = Phase.NOT_PAIRED,
    val pending: Long = 0,
    val lastSyncAt: Long = 0,
    val message: String? = null,
    val serviceRunning: Boolean = false,
    val serverUrl: String = "",
    val deviceName: String = "",
)

/** État observable par l'interface (écrit par le moteur de synchronisation et le service). */
object SyncStatusHolder {
    private val _state = MutableStateFlow(SyncStatus())
    val state: StateFlow<SyncStatus> = _state.asStateFlow()
    fun update(block: (SyncStatus) -> SyncStatus) = _state.update(block)
}
