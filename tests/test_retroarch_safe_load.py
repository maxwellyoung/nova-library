import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

from tools import prepare_retroarch_safe_load as guard

MODULE = guard.MODULE
SCENARIOS = ['backup-failure', 'backup-allocation', 'older-undo-retained', 'load-undo-redo',
             'undo-backup-failure', 'undo-copy-allocation', 'undo-replacement-allocation',
             'empty-undo', 'unsupported-core', 'failed-load-then-undo', 'sram-backup-failure',
             'background-serialization', 'backup-buffer-only', 'zero-serialization']


class SourceCandidateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.module = self.root / 'module'; self.module.mkdir()
        self.original = (MODULE / 'task_save_fixture.c').read_bytes()
        self.spec = json.loads((MODULE / 'source.json').read_text())
        self.assertEqual(guard.sha(self.original), self.spec['fixtureSha256'])
        self.spec['beforeSha256'] = guard.sha(self.original)
        self.spec['afterSha256'] = guard.sha(guard.guard_text(self.original.decode()).encode())
        shutil.copyfile(MODULE / 'safe-load.patch', self.module / 'safe-load.patch')
        self.save_spec()
        self.source = self.root / 'task_save.c'; self.source.write_bytes(self.original)
        self.output = self.root / 'review'
        patch = mock.patch.object(guard, 'MODULE', self.module)
        patch.start(); self.addCleanup(patch.stop)

    def save_spec(self):
        (self.module / 'source.json').write_text(json.dumps(self.spec))

    def test_new_candidate_keeps_original_and_explicit_non_runtime_receipt(self):
        receipt = guard.write_candidate(self.source, self.output)
        self.assertEqual(self.source.read_bytes(), self.original)
        self.assertEqual((self.output / 'baseline.c').read_bytes(), self.original)
        self.assertEqual(guard.sha((self.output / 'candidate.c').read_bytes()), self.spec['afterSha256'])
        self.assertEqual((self.output / 'COMPLETE').read_text(), self.spec['afterSha256']+'\n')
        self.assertEqual(self.output.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in self.output.iterdir()))
        for key in ['built', 'installed', 'runtimeRestoreVerified', 'durableCheckpoint']:
            self.assertIs(receipt[key], False)
        self.assertEqual(guard.verify_candidate(self.output), receipt)

    def test_reopen_refuses_edited_source_receipt_marker_and_linked_files(self):
        guard.write_candidate(self.source, self.output)
        for name in ['candidate.c', 'receipt.json', 'COMPLETE']:
            path = self.output / name; before = path.read_bytes()
            path.write_bytes(before+b'changed')
            with self.assertRaises(ValueError): guard.verify_candidate(self.output)
            path.write_bytes(before)
        path = self.output / 'candidate.c'; path.unlink(); path.symlink_to(self.source)
        with self.assertRaises(ValueError): guard.verify_candidate(self.output)

    def test_changed_source_and_patch_refuse_before_output(self):
        self.source.write_bytes(self.original+b'changed')
        with self.assertRaises(ValueError): guard.write_candidate(self.source, self.output)
        self.assertFalse(self.output.exists())
        self.source.write_bytes(self.original)
        (self.module / 'safe-load.patch').write_bytes(b'changed')
        with self.assertRaises(ValueError): guard.write_candidate(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_and_linked_source_are_kept(self):
        self.output.mkdir(); (self.output / 'keep').write_bytes(b'owner copy')
        with self.assertRaises(FileExistsError): guard.write_candidate(self.source, self.output)
        self.assertEqual((self.output / 'keep').read_bytes(), b'owner copy')
        linked = self.root / 'link.c'; linked.symlink_to(self.source)
        with self.assertRaises(ValueError): guard.write_candidate(linked, self.root / 'other')
        self.assertFalse((self.root / 'other').exists())

    def test_interrupted_preparation_has_no_completion_marker(self):
        real_open = Path.open
        def refuse(path, *args, **kwargs):
            if path.name == 'candidate.c': raise OSError('synthetic write failure')
            return real_open(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', refuse):
            with self.assertRaises(OSError): guard.write_candidate(self.source, self.output)
        self.assertFalse((self.output / 'COMPLETE').exists())
        self.assertEqual(self.source.read_bytes(), self.original)

    def test_unknown_anchor_and_result_pin_refuse_without_publication(self):
        self.spec['afterSha256'] = '0'*64; self.save_spec()
        with self.assertRaises(ValueError): guard.write_candidate(self.source, self.output)
        self.assertFalse(self.output.exists())
        with self.assertRaises(ValueError): guard.guard_text('unrelated source')


@unittest.skipUnless(shutil.which('cc'), 'An installed C compiler is required; no download attempted')
class NativeLoadCallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        cls.root = Path(cls.temporary.name)
        fixture = (MODULE / 'task_save_fixture.c').read_text()
        spec = json.loads((MODULE / 'source.json').read_text())
        if guard.sha(fixture.encode()) != spec['fixtureSha256']:
            raise AssertionError('Pinned function fixture changed')
        template = (MODULE / 'test_driver.c').read_text()
        cls.programs = {}
        for mode, functions in [('before', fixture), ('after', guard.guard_text(fixture))]:
            source = cls.root / (mode+'.c'); binary = cls.root / mode
            source.write_text(template.replace('/* PINNED_FUNCTIONS */', functions))
            compiled = subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-Wno-unused-parameter',
                                       str(source), '-o', str(binary)], capture_output=True, text=True)
            if compiled.returncode:
                raise AssertionError(compiled.stderr)
            cls.programs[mode] = binary

    def test_original_callback_reproduces_loading_despite_backup_failure(self):
        result = subprocess.run([str(self.programs['before']), 'backup-failure'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('FAIL backup-failure', result.stderr)

    def test_guarded_actual_functions_preserve_current_state_and_undo_on_failure(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario):
                result = subprocess.run([str(self.programs['after']), scenario], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(result.stdout.strip(), 'PASS '+scenario)


if __name__ == '__main__': unittest.main()
