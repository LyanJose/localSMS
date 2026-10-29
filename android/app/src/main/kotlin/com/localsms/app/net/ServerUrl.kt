package com.localsms.app.net

import java.net.URI
import java.net.URISyntaxException

/**
 * Valide l'adresse du serveur saisie par l'utilisateur.
 * Le HTTP en clair n'est accepté que vers le PC lui-même (127.0.0.1 via USB/adb reverse) ou une
 * adresse du réseau local : le trafic (SMS, jeton) ne doit jamais circuler en clair sur Internet.
 */
object ServerUrl {
    sealed class Result {
        data class Valid(val url: String) : Result()
        data class Invalid(val reason: String) : Result()
    }

    const val DEFAULT_PORT = 8765

    fun normalize(raw: String): Result {
        var s = raw.trim()
        if (s.isEmpty()) return Result.Invalid("Saisissez l'adresse du serveur.")
        if (!s.contains("://")) s = "http://$s"
        val uri = try {
            URI(s)
        } catch (e: URISyntaxException) {
            return Result.Invalid("Adresse invalide.")
        }
        val scheme = uri.scheme?.lowercase()
        if (scheme != "http" && scheme != "https") return Result.Invalid("L'adresse doit commencer par http:// ou https://.")
        val host = uri.host ?: return Result.Invalid("Adresse invalide.")
        if (uri.userInfo != null || (uri.rawPath ?: "").trim('/').isNotEmpty() || uri.rawQuery != null) {
            return Result.Invalid("Saisissez uniquement l'adresse et le port (ex. 192.168.1.20:8765).")
        }
        if (scheme == "http" && !isLocalHost(host)) {
            return Result.Invalid("En HTTP, seule une adresse du réseau local (ou 127.0.0.1 en USB) est acceptée.")
        }
        val port = if (uri.port == -1) (if (scheme == "https") 443 else DEFAULT_PORT) else uri.port
        if (port !in 1..65535) return Result.Invalid("Port invalide.")
        return Result.Valid("$scheme://$host:$port")
    }

    fun isLocalHost(hostRaw: String): Boolean {
        val host = hostRaw.lowercase().removePrefix("[").removeSuffix("]")
        if (host == "localhost" || host == "::1" || host.endsWith(".local")) return true
        parseIpv4(host)?.let { (a, b) ->
            return a == 127 || a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168) || (a == 169 && b == 254)
        }
        if (host.contains(':')) return host.startsWith("fe80:") || host.startsWith("fc") || host.startsWith("fd")
        return !host.contains('.') // nom d'hôte simple du réseau local (ex. « mon-pc »)
    }

    /** Retourne (octet1, octet2) si [host] est une adresse IPv4 valide. */
    private fun parseIpv4(host: String): Pair<Int, Int>? {
        val parts = host.split('.')
        if (parts.size != 4) return null
        val nums = parts.map { it.toIntOrNull() ?: return null }
        if (nums.any { it !in 0..255 }) return null
        return nums[0] to nums[1]
    }
}
