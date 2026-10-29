package com.localsms.app

import com.localsms.app.net.ServerUrl
import com.localsms.app.net.ServerUrl.Result
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ServerUrlTest {
    private fun ok(raw: String) = (ServerUrl.normalize(raw) as Result.Valid).url
    private fun bad(raw: String) = assertTrue("devrait être refusé : $raw", ServerUrl.normalize(raw) is Result.Invalid)

    @Test fun addsSchemeAndDefaultPort() = assertEquals("http://192.168.1.20:8765", ok("192.168.1.20"))
    @Test fun keepsExplicitPort() = assertEquals("http://10.0.0.5:9000", ok("http://10.0.0.5:9000/"))
    @Test fun acceptsLoopbackForUsb() = assertEquals("http://127.0.0.1:8765", ok("127.0.0.1:8765"))
    @Test fun acceptsLocalHostnames() { ok("mon-pc:8765"); ok("pc.local") }
    @Test fun acceptsHttpsAnywhere() = assertEquals("https://exemple.org:443", ok("https://exemple.org"))
    @Test fun rejectsPublicHttp() { bad("http://8.8.8.8:8765"); bad("http://exemple.com"); bad("172.32.0.1"); bad("192.169.1.1") }
    @Test fun rejectsGarbage() { bad(""); bad("ftp://192.168.1.1"); bad("http://192.168.1.1/chemin"); bad("http://u:p@192.168.1.1"); bad("http://192.168.1.1:99999") }
    @Test fun privateRanges() { ok("172.16.0.1"); ok("172.31.255.255"); ok("10.1.2.3") }
}
