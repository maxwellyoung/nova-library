import hashlib
import importlib.util
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


demo, privacy = load('make_demo'), load('privacy_scan')


def tree_hashes(root):
    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob('*') if path.is_file()}


class DemoTests(unittest.TestCase):
    def test_raster_cover_has_valid_chunks_dimensions_and_pixel_payload(self):
        raw = demo.cover_png('#bc7747', 0)
        self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
        chunks, offset = {}, 8
        while offset < len(raw):
            size = struct.unpack_from('>I', raw, offset)[0]
            kind = raw[offset+4:offset+8]
            payload = raw[offset+8:offset+8+size]
            self.assertEqual(zlib.crc32(kind+payload)&0xffffffff, struct.unpack_from('>I', raw, offset+8+size)[0])
            chunks[kind] = payload
            offset += size+12
        self.assertEqual(offset, len(raw))
        self.assertEqual(struct.unpack('>IIBBBBB', chunks[b'IHDR']), (480, 640, 8, 2, 0, 0, 0))
        pixels = zlib.decompress(chunks[b'IDAT'])
        self.assertEqual(len(pixels), (480*3+1)*640)
        self.assertTrue(all(pixels[y*(480*3+1)] == 0 for y in range(640)))
        self.assertNotEqual(raw, demo.cover_png('#719b8a', 1))

    def test_deterministic_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            first, second = Path(temporary) / 'first', Path(temporary) / 'second'
            demo.generate(first)
            demo.generate(second)
            self.assertEqual(tree_hashes(first), tree_hashes(second))

    def test_no_launch_commands_and_unknown_time_remains_absent(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'demo'
            games = demo.generate(output)
            self.assertEqual(len({game['extra']['edition-id'] for game in games}), 4)
            self.assertTrue(all(game['extra']['launchable'] == 'false' for game in games))
            self.assertTrue(all(game['extra']['ready-devices'] == '[]' for game in games))
            self.assertTrue(any(game['extra']['minutes-value'] == '' for game in games))
            self.assertTrue(any(game['extra']['minutes-value'] == '0' for game in games))
            self.assertNotIn('\nlaunch:', (output / 'metadata.txt').read_text())
            self.assertEqual(json.loads((output / 'games.json').read_text()), games)
            for game in games:
                self.assertTrue((output / game['file']).is_file())
                self.assertTrue((output / game['cover']).is_file())

    def test_refuses_existing_output_and_preserves_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'demo'
            demo.generate(output)
            before = tree_hashes(output)
            with self.assertRaises(FileExistsError):
                demo.generate(output)
            self.assertEqual(tree_hashes(output), before)


class PrivacyTests(unittest.TestCase):
    def test_rejects_private_network_and_machine_path_without_echoing_value(self):
        failures = privacy.findings('README.md', 'http://' + '192.168.' + '1.44 /' + 'Users/demo/secret')
        self.assertEqual(failures, ['machine path', 'private network address'])

    def test_rejects_token_and_email(self):
        failures = privacy.findings('source.txt', 'ghp_' + 'A' * 30 + ' demo@' + 'private.example')
        self.assertEqual(failures, ['access token', 'email address'])

    def test_boundary_fixture_exception_is_scoped(self):
        sample = 'Enrollment e; e.endpoint=QUrl("http://' + '100.100.' + '1.1:3000");'
        self.assertEqual(privacy.findings('native/nova-library.patch', sample), [])
        self.assertEqual(privacy.findings('README.md', sample), ['private network address'])

    def test_source_scan_rejects_symlink_and_binary(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'public.txt').write_text('ordinary source')
            (root / 'link').symlink_to(root / 'public.txt')
            (root / 'release.apk').write_bytes(b'\x00\xff')
            failures = privacy.scan(root)
            self.assertEqual(len(failures), 2)
            self.assertTrue(any('symlink' in rule for _, rule in failures))
            self.assertTrue(any('artifact' in rule for _, rule in failures))

    def test_save_passports_are_private_artifacts_even_when_bytes_look_like_text(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'progress.nvs').write_text('private progress')
            self.assertEqual(privacy.scan(root), [('progress.nvs', 'private/generated artifact')])


if __name__ == '__main__':
    unittest.main()
