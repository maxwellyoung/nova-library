import importlib.util
import struct
import sys
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
spec = importlib.util.spec_from_file_location('android_build', TOOLS / 'build_android.py')
android = importlib.util.module_from_spec(spec)
spec.loader.exec_module(android)


def elf(text=b'code', debug=b'private debug symbols'):
    names = b'\0.shstrtab\0.text\0.debug\0'
    start = 64 + 4 * 64
    header = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF\x02\x01' + b'\0' * 10,
                         3, 183, 1, 0, 0, 64, 0, 64, 0, 0, 64, 4, 1)
    sections = [b'\0' * 64,
                struct.pack('<IIQQQQIIQQ', 1, 3, 0, 0, start, len(names), 0, 0, 1, 0),
                struct.pack('<IIQQQQIIQQ', names.index(b'.text'), 1, 6, 4096,
                            start + len(names), len(text), 0, 0, 4, 0),
                struct.pack('<IIQQQQIIQQ', names.index(b'.debug'), 1, 0, 0,
                            start + len(names) + len(text), len(debug), 0, 0, 1, 0)]
    return header + b''.join(sections) + names + text + debug


class AndroidBuildReceiptTests(unittest.TestCase):
    def test_optional_heap_is_bounded_and_confined_to_generated_properties(self):
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / 'existing-gradle.properties'
            original = 'org.gradle.jvmargs=-Xmx512m\n'
            profile.write_text(original)
            scoped = Path(folder) / 'new-build-gradle.properties'
            scoped.write_text(android.gradle_properties(1536))
            self.assertIn('-Xmx1536m', scoped.read_text())
            self.assertEqual(profile.read_text(), original)
            self.assertNotIn('jvmargs', android.gradle_properties())
        for invalid in [True, 511, 8193, 1536.0, '1536m\nother=value']:
            with self.assertRaises(ValueError):
                android.gradle_properties(invalid)

    def test_missing_wrapper_distribution_fails_before_network_or_build(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            template = p / 'gradle-wrapper.properties'
            template.write_text('distributionUrl=https\\://example.test/gradle-7.2-bin.zip\n')
            with self.assertRaisesRegex(ValueError, 'no download attempted'):
                android.cached_gradle(p, template)
            # Match Gradle's URL-to-cache-key algorithm, including the ZIP marker.
            directory = p / 'wrapper/dists/gradle-7.2-bin'
            import hashlib
            number = int.from_bytes(hashlib.md5(b'https://example.test/gradle-7.2-bin.zip').digest(), 'big')
            key = ''
            while number:
                number, digit = divmod(number, 36)
                key = '0123456789abcdefghijklmnopqrstuvwxyz'[digit] + key
            destination = directory / key
            executable = destination / 'gradle-7.2/bin/gradle'
            executable.parent.mkdir(parents=True)
            executable.write_text('provisioned fixture')
            with self.assertRaisesRegex(ValueError, 'no download attempted'):
                android.cached_gradle(p, template)
            (destination / 'gradle-7.2-bin.zip.ok').touch()
            self.assertEqual(android.cached_gradle(p, template), executable)

    def test_debug_changes_do_not_hide_runtime_changes(self):
        self.assertEqual(android.runtime_sections(elf()), android.runtime_sections(elf(debug=b'stripped')))
        self.assertNotEqual(android.runtime_sections(elf()), android.runtime_sections(elf(text=b'old!')))

    def test_invalid_binary_and_table_are_refused(self):
        for data in [b'not ELF', elf()[:80]]:
            with self.assertRaises(ValueError):
                android.runtime_sections(data)

    def test_stale_packaged_library_is_rejected_and_dex_hashes_are_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            linked, staged, apk = p / 'linked.so', p / 'staged.so', p / 'test.apk'
            linked.write_bytes(elf())
            staged.write_bytes(elf(debug=b'stripped'))
            name = 'lib/arm64-v8a/libpegasus-fe_arm64-v8a.so'
            with zipfile.ZipFile(apk, 'w') as archive:
                archive.writestr(name, elf(text=b'old!'))
            with self.assertRaisesRegex(ValueError, 'exact staged'):
                android.verify_packaged_native(linked, staged, apk)
            with zipfile.ZipFile(apk, 'w') as archive:
                archive.writestr(name, staged.read_bytes())
                archive.writestr('classes.dex', b'synthetic bytecode')
            self.assertEqual(set(android.verify_packaged_native(linked, staged, apk)), {'classes.dex'})
            staged.write_bytes(elf(text=b'old!'))
            with self.assertRaisesRegex(ValueError, 'linked runtime'):
                android.verify_packaged_native(linked, staged, apk)

    def test_duplicate_native_zip_entry_is_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            linked, apk = p / 'linked.so', p / 'test.apk'
            linked.write_bytes(elf())
            name = 'lib/arm64-v8a/libpegasus-fe_arm64-v8a.so'
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', UserWarning)
                with zipfile.ZipFile(apk, 'w') as archive:
                    archive.writestr(name, linked.read_bytes())
                    archive.writestr(name, linked.read_bytes())
            with self.assertRaisesRegex(ValueError, 'exact staged'):
                android.verify_packaged_native(linked, linked, apk)


if __name__ == '__main__':
    unittest.main()
