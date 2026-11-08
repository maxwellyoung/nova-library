// SPDX-License-Identifier: GPL-3.0-or-later
package org.pegasus_frontend.android;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import org.json.JSONObject;
import org.qtproject.qt5.android.QtNative;
import java.io.File;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.security.KeyStore;
import javax.crypto.Cipher;
import javax.crypto.KeyGenerator;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;

/** Enrollment is injected into app-private files/enrollment.json by the operator.
 * It is consumed only after an encrypted durable vault exists. Nothing is logged. */
public final class RomCloudVault {
    private static final String ALIAS = "rom-cloud-capability-v1";
    private RomCloudVault() {}
    private static Context context() { return QtNative.activity().getApplicationContext(); }
    public static String storagePath() {
        File dir = new File(context().getFilesDir(), "rom-cloud");
        if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("Private storage unavailable");
        return dir.getAbsolutePath();
    }
    private static byte[] read(File file, int limit) throws Exception {
        if (file.length() > limit) throw new IllegalArgumentException("Enrollment too large");
        byte[] data = new byte[(int) file.length()];
        try (FileInputStream input = new FileInputStream(file)) {
            int offset = 0;
            while (offset < data.length) { int n = input.read(data, offset, data.length - offset); if (n < 0) throw new IllegalArgumentException("Incomplete enrollment"); offset += n; }
        }
        return data;
    }
    private static SecretKey key() throws Exception {
        KeyStore store = KeyStore.getInstance("AndroidKeyStore"); store.load(null);
        if (!store.containsAlias(ALIAS)) {
            KeyGenerator gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore");
            gen.init(new KeyGenParameterSpec.Builder(ALIAS, KeyProperties.PURPOSE_ENCRYPT | KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());
            gen.generateKey();
        }
        return (SecretKey) store.getKey(ALIAS, null);
    }
    public static synchronized String enrollment() {
        try {
            File input = new File(context().getFilesDir(), "rom-cloud-enrollment.json");
            File vault = new File(storagePath(), "enrollment.vault");
            if (input.exists()) {
                byte[] plain = read(input, 16384);
                JSONObject o = new JSONObject(new String(plain, "UTF-8"));
                if (o.optString("endpoint").isEmpty() || o.optString("romRoot").isEmpty() || o.optString("token").isEmpty()) return "{}";
                Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding"); cipher.init(Cipher.ENCRYPT_MODE, key());
                byte[] iv = cipher.getIV(), ciphertext = cipher.doFinal(plain);
                File temp = new File(vault.getParentFile(), "enrollment.vault.tmp");
                try (FileOutputStream out = new FileOutputStream(temp)) { out.write(iv.length); out.write(iv); out.write(ciphertext); out.getFD().sync(); }
                if (!temp.renameTo(vault)) throw new IllegalStateException("Vault commit failed");
                if (!input.delete()) return "{}";
            }
            if (!vault.exists()) return "{}";
            byte[] encrypted = read(vault, 32768); int ivSize = encrypted[0] & 255;
            if (ivSize != 12 || encrypted.length <= 1 + ivSize) return "{}";
            Cipher cipher = Cipher.getInstance("AES/GCM/NoPadding");
            cipher.init(Cipher.DECRYPT_MODE, key(), new GCMParameterSpec(128, encrypted, 1, ivSize));
            return new String(cipher.doFinal(encrypted, 1 + ivSize, encrypted.length - 1 - ivSize), "UTF-8");
        } catch (Exception ignored) { return "{}"; }
    }

    /** The native downloader supplies a verified path and a fixed adapter name. */
    public static boolean launch(String rom, String core) {
        try {
            if (!core.equals("swanstation_libretro_android.so") && !core.equals("snes9x_libretro_android.so")) return false;
            File file = new File(rom);
            if (!file.isFile() || !file.getCanonicalPath().equals(file.getAbsolutePath())) return false;
            // Reuse the ordinary launcher boundary: private builds consume their
            // staged ROM identity here and close failed observations on an error.
            // These are literal arguments, never a shell command or server code.
            return MainActivity.launchAmCommand(new String[] {
                "start", "-a", "android.intent.action.MAIN",
                "-n", "com.retroarch.aarch64/com.retroarch.browser.retroactivity.RetroActivityFuture",
                "--es", "ROM", rom,
                "--es", "LIBRETRO", "/data/user/0/com.retroarch.aarch64/cores/" + core,
                "--es", "CONFIGFILE", "/storage/emulated/0/Android/data/com.retroarch.aarch64/files/retroarch.cfg",
                "--esn", "QUITFOCUS", "-f", "0x14000000"
            }) == null;
        } catch (Exception ignored) { return false; }
    }
}
