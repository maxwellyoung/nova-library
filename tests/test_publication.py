import hashlib
import importlib.util
import json
import tempfile
import unittest
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


if __name__ == '__main__':
    unittest.main()
