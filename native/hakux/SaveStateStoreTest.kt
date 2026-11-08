package com.rfandango.haku_x.data

import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File
import java.security.MessageDigest
import java.nio.file.Files

class SaveStateStoreTest {
  @get:Rule val temporary = TemporaryFolder()
  private val uri = "content://synthetic/legacy-disc"
  private val key = "4D530004.9"
  private val blob = "0123456789abcdef0123456789abcdef.gz"

  private fun legacy(root: File): File {
    val hash = MessageDigest.getInstance("SHA-1").digest(uri.toByteArray())
      .take(8).joinToString("") { "%02x".format(it) }
    return File(root, hash).apply {
      mkdirs()
      File(this, "slot1.hxs").writeText("synthetic state referencing $blob")
      File(this, "slot1.jpg").writeText("synthetic thumbnail")
      File(this, "blobs").mkdir()
      File(this, "blobs/$blob").writeText("synthetic cache content")
    }
  }

  @Test fun legacyStateRetainsItsCacheAndOriginals() {
    val root = temporary.newFolder("states")
    val old = legacy(root)
    val store = SaveStateStore(root, key, uri)
    assertTrue("State migration lost its supporting blob", File(root, "$key/blobs/$blob").isFile)
    assertEquals("synthetic cache content", File(root, "$key/blobs/$blob").readText())
    assertEquals(File(old, "slot1.hxs").readText(), store.state(1).readText())
    assertTrue("Migration must retain the source checkpoint", File(old, "slot1.hxs").isFile)
    assertTrue(File(old, "blobs/$blob").isFile)
  }

  @Test fun existingDestinationWinsEvenWhenLegacyIsNewer() {
    val root = temporary.newFolder("states")
    val old = legacy(root)
    val destination = File(root, key).apply { mkdirs() }
    File(destination, "slot1.hxs").writeText("current checkpoint")
    File(old, "slot1.hxs").setLastModified(System.currentTimeMillis() + 60000)
    val store = SaveStateStore(root, key, uri)
    assertEquals("current checkpoint", store.state(1).readText())
    assertTrue(File(old, "slot1.hxs").isFile)
    assertFalse(File(destination, "blobs").exists())
  }

  @Test fun conflictingBlobKeepsBothBundlesWithoutPublishingState() {
    val root = temporary.newFolder("states")
    val old = legacy(root)
    val destination = File(root, "$key/blobs").apply { mkdirs() }
    File(destination, blob).writeText("different existing bytes")
    val store = SaveStateStore(root, key, uri)
    assertFalse(store.state(1).exists())
    assertEquals("different existing bytes", File(destination, blob).readText())
    assertTrue(File(old, "slot1.hxs").isFile)
    assertEquals("synthetic cache content", File(old, "blobs/$blob").readText())
  }

  @Test fun linkedBlobCannotPublishAStateOrTouchItsTarget() {
    val root = temporary.newFolder("states")
    val old = legacy(root)
    val outside = temporary.newFile("outside").apply { writeText("keep") }
    File(old, "blobs/$blob").delete()
    Files.createSymbolicLink(File(old, "blobs/$blob").toPath(), outside.toPath())
    assertFalse(SaveStateStore(root, key, uri).state(1).exists())
    assertEquals("keep", outside.readText())
    assertTrue(File(old, "slot1.hxs").isFile)
  }

  @Test fun linkedDestinationCannotRedirectCopies() {
    val root = temporary.newFolder("states")
    val old = legacy(root)
    val outside = temporary.newFolder("outside")
    Files.createSymbolicLink(File(root, key).toPath(), outside.toPath())
    SaveStateStore(root, key, uri)
    assertTrue(outside.listFiles()!!.isEmpty())
    assertTrue(File(old, "slot1.hxs").isFile)
  }

  @Test fun existingThumbnailCannotBePairedWithAnotherState() {
    val root = temporary.newFolder("states")
    val old = legacy(root)
    File(root, key).mkdirs()
    File(root, "$key/slot1.jpg").writeText("another checkpoint's picture")
    val store = SaveStateStore(root, key, uri)
    assertFalse(store.state(1).exists())
    assertEquals("another checkpoint's picture", store.thumb(1).readText())
    assertTrue(File(old, "slot1.hxs").isFile)
  }

  @Test fun repeatedAdoptionLeavesOriginalsAndNoTemporaryFiles() {
    val root = temporary.newFolder("states")
    val old = legacy(root)
    val first = SaveStateStore(root, key, uri)
    val before = first.state(1).readBytes()
    SaveStateStore(root, key, uri)
    assertArrayEquals(before, first.state(1).readBytes())
    assertTrue(File(old, "slot1.hxs").isFile)
    assertFalse(root.walk().any { it.name.endsWith(".pending") })
  }

  @Test fun invalidFolderKeysCannotEscapeTheStateRoot() {
    val root = temporary.newFolder("states")
    for (key in listOf(".", "..", "../other")) {
      val store = SaveStateStore(root, key)
      store.prepare()
      assertEquals(root.canonicalFile, store.state(1).parentFile.parentFile.canonicalFile)
      assertNotEquals(root.canonicalFile, store.state(1).parentFile.canonicalFile)
    }
  }
}
