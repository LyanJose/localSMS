package com.localsms.app.ui

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.localsms.app.LocalSmsApp
import com.localsms.app.sync.Phase
import com.localsms.app.sync.SyncService
import com.localsms.app.sync.SyncStatusHolder
import com.localsms.app.sync.SyncWorker
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

private fun requiredPermissions(): Array<String> = buildList {
    add(Manifest.permission.READ_SMS)
    add(Manifest.permission.RECEIVE_SMS)
    add(Manifest.permission.READ_CONTACTS) // facultative : noms des contacts
    if (Build.VERSION.SDK_INT >= 33) add(Manifest.permission.POST_NOTIFICATIONS)
}.toTypedArray()

@Composable
fun RootScreen() {
    val app = LocalContext.current.applicationContext as LocalSmsApp
    val status by SyncStatusHolder.state.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) {
        while (true) { app.engine.refreshStatus(); delay(2000) }
    }
    Column(
        Modifier.statusBarsPadding().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Text("LocalSMS", style = MaterialTheme.typography.headlineMedium)
        if (status.paired) Dashboard(app) else PairingScreen(app)
    }
}

@Composable
private fun PairingScreen(app: LocalSmsApp) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var url by remember { mutableStateOf("http://127.0.0.1:8765") }
    var code by remember { mutableStateOf("") }
    var name by remember { mutableStateOf(Build.MODEL ?: "") }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    fun doPair() {
        busy = true; error = null
        scope.launch {
            val err = app.pair(url, code, name)
            busy = false
            if (err != null) error = err else app.startService(ctx)
        }
    }

    val permLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        val smsOk = result[Manifest.permission.READ_SMS] == true && result[Manifest.permission.RECEIVE_SMS] == true
        if (smsOk) doPair() else error = "L'accès aux SMS est indispensable pour synchroniser."
    }

    Text(
        "Associez ce téléphone à LocalSMS sur votre PC. Sur le PC, ouvrez l'onglet « Téléphone » et générez un code.",
        style = MaterialTheme.typography.bodyMedium,
    )
    OutlinedTextField(
        url, { url = it }, Modifier.fillMaxWidth(), label = { Text("Adresse du serveur") },
        supportingText = { Text("USB : http://127.0.0.1:8765 · Wi-Fi : http://192.168.x.x:8765") },
        singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
    )
    OutlinedTextField(code, { code = it.uppercase() }, Modifier.fillMaxWidth(), label = { Text("Code d'appairage") }, singleLine = true)
    OutlinedTextField(name, { name = it }, Modifier.fillMaxWidth(), label = { Text("Nom de ce téléphone") }, singleLine = true)
    error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
    Button(
        onClick = {
            val missing = requiredPermissions().filter { ContextCompat.checkSelfPermission(ctx, it) != PackageManager.PERMISSION_GRANTED }
            val smsMissing = missing.any { it == Manifest.permission.READ_SMS || it == Manifest.permission.RECEIVE_SMS }
            if (smsMissing || missing.isNotEmpty()) permLauncher.launch(requiredPermissions()) else doPair()
        },
        enabled = !busy && code.isNotBlank(), modifier = Modifier.fillMaxWidth(),
    ) { Text(if (busy) "Association…" else "Associer et synchroniser") }
    Text(
        "Vos SMS sont envoyés uniquement vers l'adresse saisie ci-dessus, sans aucun service cloud.",
        style = MaterialTheme.typography.bodySmall,
    )
}

@Composable
private fun Dashboard(app: LocalSmsApp) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val st by SyncStatusHolder.state.collectAsStateWithLifecycle()
    var confirmUnpair by remember { mutableStateOf(false) }

    val phaseText = when (st.phase) {
        Phase.SYNCING -> "Synchronisation en cours…"
        Phase.OFFLINE -> "PC injoignable — nouvelle tentative automatique"
        Phase.ERROR -> "Erreur"
        Phase.IDLE -> if (st.pending == 0L) "À jour" else "En attente d'envoi"
        Phase.NOT_PAIRED -> "Non associé"
    }

    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(phaseText, style = MaterialTheme.typography.titleMedium)
            st.message?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Text("Serveur : ${st.serverUrl}")
            Text("Appareil : ${st.deviceName}")
            Text("SMS en file d'attente : ${st.pending}")
            Text(
                "Dernière synchronisation : " +
                    if (st.lastSyncAt > 0) DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(st.lastSyncAt)) else "jamais",
            )
            Text("Synchronisation en direct : ${if (st.serviceRunning) "active" else "arrêtée"}")
        }
    }
    Button({ SyncWorker.runNow(ctx); if (SyncService.running) SyncService.start(ctx) }, Modifier.fillMaxWidth()) {
        Text("Synchroniser maintenant")
    }
    if (st.serviceRunning) {
        OutlinedButton({ app.stopService(ctx) }, Modifier.fillMaxWidth()) { Text("Arrêter la synchronisation en direct") }
    } else {
        Button({ app.startService(ctx) }, Modifier.fillMaxWidth()) { Text("Démarrer la synchronisation en direct") }
    }
    OutlinedButton(
        { app.engine.resetForFullSync(); SyncWorker.runNow(ctx); if (SyncService.running) SyncService.start(ctx) },
        Modifier.fillMaxWidth(),
    ) { Text("Renvoyer tout l'historique") }

    val pm = ctx.getSystemService(PowerManager::class.java)
    if (!pm.isIgnoringBatteryOptimizations(ctx.packageName)) {
        OutlinedButton({
            ctx.startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${ctx.packageName}")))
        }, Modifier.fillMaxWidth()) { Text("Désactiver l'optimisation de batterie") }
        Text(
            "Recommandé : sans cela, Android peut suspendre la synchronisation écran éteint.",
            style = MaterialTheme.typography.bodySmall,
        )
    }

    Spacer(Modifier.height(8.dp))
    if (confirmUnpair) {
        Text("Dissocier ce téléphone ? Les SMS déjà copiés sur le PC y restent.")
        Button({ scope.launch { app.unpair(); confirmUnpair = false } }, Modifier.fillMaxWidth()) { Text("Oui, dissocier") }
        OutlinedButton({ confirmUnpair = false }, Modifier.fillMaxWidth()) { Text("Annuler") }
    } else {
        OutlinedButton({ confirmUnpair = true }, Modifier.fillMaxWidth()) { Text("Dissocier ce téléphone") }
    }
}
