import copy
import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
catalogue = importlib.import_module('save_catalogue')
passport = catalogue.passport


def png():
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(b'\0\x10\x20\x30')) + chunk(b'IEND', b''))


class SaveCatalogue(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / 'source'
        self.source.mkdir()
        self.retention = {**catalogue.DEFAULT_POLICY, 'quickSlots': 2, 'maxEntries': 8,
                          'maxBytes': 128 * 1024, 'maxPassportBytes': 32 * 1024,
                          'trashEntries': 4, 'trashBytes': 64 * 1024, 'trashDays': 2}
        self.now = dt.datetime(2026, 11, 5, tzinfo=dt.timezone.utc)
        self.root = self.base / 'history'
        self.store = catalogue.Catalogue(self.root, create=True, retention=self.retention, clock=lambda: self.now)
        self.selection = {'schemaVersion': 1, 'editionId': 'fixture:edition-a', 'recipeId': 'fixture.v1',
                          'kind': 'native-save', 'runtime': {'name': 'Fixture runtime', 'version': '1.0', 'core': 'Fixture core'},
                          'files': ['fixture.srm']}
        self.target = {k: copy.deepcopy(self.selection[k]) for k in ('editionId', 'recipeId', 'kind', 'runtime')}
        self.counter = 0

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def archive(self, content=b'invented branch', selection=None):
        self.counter += 1
        (self.source / 'fixture.srm').write_bytes(content)
        output = self.base / f'fixture-{self.counter}.nvs'
        passport.pack(self.source, selection or self.selection, output, source_idle=True)
        return output

    def add(self, content=b'invented branch', **kwargs):
        return self.store.import_passport(self.archive(content), **kwargs)['checkpointId']

    def reopen(self):
        self.store.close()
        self.store = catalogue.Catalogue(self.root, clock=lambda: self.now)

    def test_persisted_timeline_has_dates_kind_named_anchor_and_exact_reference(self):
        identifier = self.add(name='Before the lift', pinned=True)
        state_selection = copy.deepcopy(self.selection)
        state_selection['kind'] = 'emulator-state'
        state = self.store.import_passport(self.archive(selection=state_selection))['checkpointId']
        self.reopen()
        rows = self.store.list_entries(target=self.target)
        self.assertEqual([r['checkpointId'] for r in rows], [state, identifier])
        anchor = rows[1]
        self.assertEqual(anchor['name'], 'Before the lift')
        self.assertTrue(anchor['pinned'])
        self.assertRegex(anchor['capturedAt'], r'^\d{4}-\d\d-\d\dT')
        self.assertEqual(anchor['addedAt'], '2026-11-05T00:00:00Z')
        self.assertFalse(anchor['runtimeRestoreAvailable'])
        self.assertIn('Save kind differs', rows[0]['compatibility'])
        ref = self.store.reference(identifier)
        self.assertEqual(set(ref), {'checkpointId', 'passportSha256', 'identity'})
        self.assertEqual(ref['identity'], self.target)
        self.assertEqual(stat.S_IMODE(self.root.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(self.store.path.stat().st_mode), 0o600)

    def test_package_import_does_not_depend_on_test_order_or_path_injection(self):
        result = subprocess.run([sys.executable, '-c', 'from tools.save_catalogue import Catalogue; print(Catalogue.__name__)'],
                                cwd=TOOLS.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'Catalogue')

    def test_pinned_anchor_survives_repeated_full_slot_rotation(self):
        anchor = self.add(b'named anchor', name='Disc 2 begins', pinned=True)
        original = self.store.reference(anchor)
        first = self.add(b'quick 1')
        second = self.add(b'quick 2')
        with self.assertRaisesRegex(ValueError, 'slots are full'):
            self.add(b'quick 3')
        plan = self.store.plan_rotation(self.target)
        self.assertEqual(plan['undoForDays'], 2)
        self.assertFalse(plan['permanent'])
        self.assertEqual([i['checkpointId'] for i in plan['items']], [first])
        self.store.apply(plan)
        self.add(b'quick 3')
        plan = self.store.plan_rotation(self.target)
        self.assertEqual([i['checkpointId'] for i in plan['items']], [second])
        self.store.apply(plan)
        self.add(b'quick 4')
        self.assertEqual(self.store.reference(anchor), original)
        with self.assertRaisesRegex(ValueError, 'Protected anchors'):
            self.store.plan_delete([anchor])
        with self.assertRaisesRegex(ValueError, 'overflow quick-save slots'):
            self.store.rename(anchor, 'Disc 2 begins', pinned=False)
        self.assertTrue(next(r for r in self.store.list_entries() if r['checkpointId'] == anchor)['pinned'])

    def test_rotation_is_scoped_to_exact_identity_and_uses_arrival_sequence_not_clocks(self):
        first = self.add(b'first')
        self.now -= dt.timedelta(days=90)
        self.add(b'second')
        other = copy.deepcopy(self.selection)
        other['editionId'] = 'fixture:other-region'
        other_id = self.store.import_passport(self.archive(b'other region', other))['checkpointId']
        plan = self.store.plan_rotation(self.target)
        self.assertEqual([i['checkpointId'] for i in plan['items']], [first])
        self.store.apply(plan)
        self.store.reference(other_id)

    def test_delete_undo_and_existing_restore_output_preserve_both_branches(self):
        a = self.add(b'branch A')
        b = self.add(b'branch B')
        first = self.store.reference(a)
        self.store.apply(self.store.plan_delete([a]))
        with self.assertRaisesRegex(ValueError, 'in trash'):
            self.store.stage(a, self.target, self.base / 'staged')
        self.assertEqual(self.store.undo(a), first)
        self.store.stage(a, self.target, self.base / 'staged')
        with self.assertRaisesRegex(ValueError, 'Staging output already exists'):
            self.store.stage(b, self.target, self.base / 'staged')
        self.assertEqual((self.base / 'staged/fixture.srm').read_bytes(), b'branch A')
        self.store.stage(b, self.target, self.base / 'separate')
        self.assertEqual((self.base / 'separate/fixture.srm').read_bytes(), b'branch B')
        self.assertNotEqual(self.store.reference(b)['passportSha256'], first['passportSha256'])

    def test_export_preserves_exact_passport_hash_and_never_replaces_output(self):
        original = self.archive(b'exported progress')
        reference = self.store.import_passport(original)
        identifier = reference['checkpointId']
        self.store.apply(self.store.plan_delete([identifier]))
        output = self.base / 'export.nvs'
        self.assertEqual(self.store.export_passport(identifier, output), reference)
        self.assertEqual(output.read_bytes(), original.read_bytes())
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(), reference['passportSha256'])
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        with self.assertRaisesRegex(ValueError, 'output already exists'):
            self.store.export_passport(identifier, output)
        self.assertEqual(len(self.store.list_entries(include_trash=True)), 1)

    def test_malformed_plan_and_duplicate_selection_never_modify_history(self):
        identifier = self.add()
        before = self.store.reference(identifier)
        for selection in ([identifier, identifier], [{}], ['../outside']):
            with self.assertRaises(ValueError):
                self.store.plan_delete(selection)
        plan = self.store.plan_delete([identifier])
        for patch in ({'schemaVersion': True}, {'action': {}}, {'items': [{'checkpointId': {}}]}, {'generation': False}):
            invalid = {**copy.deepcopy(plan), **patch}
            with self.assertRaises(ValueError):
                self.store.apply(invalid)
        self.assertEqual(self.store.reference(identifier), before)

    def test_unknown_wrong_edition_version_and_core_refuse_without_creating_output(self):
        identifier = self.add()
        for field in ('editionId', 'recipeId'):
            target = copy.deepcopy(self.target)
            target[field] = 'fixture:different'
            with self.assertRaises(ValueError):
                self.store.stage(identifier, target, self.base / 'staged')
        for field in ('name', 'version', 'core'):
            target = copy.deepcopy(self.target)
            target['runtime'][field] = 'different'
            with self.assertRaises(ValueError):
                self.store.stage(identifier, target, self.base / 'staged')
        unknown = copy.deepcopy(self.selection)
        unknown['runtime']['version'] = 'unknown'
        unknown_id = self.store.import_passport(self.archive(selection=unknown))['checkpointId']
        wanted = {k: unknown[k] for k in self.target}
        with self.assertRaisesRegex(ValueError, 'Unknown edition or runtime/setup identity'):
            self.store.stage(unknown_id, wanted, self.base / 'staged')
        self.assertFalse((self.base / 'staged').exists())

    def test_optional_images_have_honest_missing_invalid_and_corrupt_fallbacks(self):
        image = self.base / 'preview.png'
        image.write_bytes(png())
        good = self.add(name='With image', pinned=True, thumbnail_path=image)
        missing = self.add(name='Missing image', pinned=True, thumbnail_path=self.base / 'missing.png')
        image.write_bytes(png()[:-1])
        bad = self.add(name='Corrupt image', pinned=True, thumbnail_path=image)
        states = {r['checkpointId']: r['thumbnailStatus'] for r in self.store.list_entries()}
        self.assertEqual(states, {good: 'available', missing: 'missing', bad: 'invalid'})
        self.assertEqual(self.store.thumbnail(good), png())
        self.assertIsNone(self.store.thumbnail(bad))
        self.store.db.execute('UPDATE records SET thumbnail=? WHERE id=?', (b'corruption', good))
        self.store.db.commit()
        self.assertIsNone(self.store.thumbnail(good))
        self.assertEqual(next(r for r in self.store.list_entries() if r['checkpointId'] == good)['thumbnailStatus'], 'corrupt')
        self.store.stage(good, self.target, self.base / 'staged')

    def test_png_crc_decompression_size_and_unknown_critical_features_are_bounded(self):
        self.assertTrue(catalogue.valid_png(png()))
        for data in (b'', b'not an image', png()[:-1], png() + b'extra', png().replace(b'IDAT', b'ABCD')):
            self.assertFalse(catalogue.valid_png(data))
        huge = bytearray(png())
        huge[16:20] = struct.pack('>I', 65535)
        self.assertFalse(catalogue.valid_png(bytes(huge)))

    def test_trash_is_bounded_and_expiry_does_not_silently_delete_history(self):
        a, b = self.add(b'A'), self.add(b'B')
        self.store.apply(self.store.plan_delete([a, b]))
        self.now += dt.timedelta(days=3)
        self.assertEqual(len(self.store.list_entries(include_trash=True)), 2)
        with self.assertRaisesRegex(ValueError, 'Undo retention expired'):
            self.store.undo(a)
        plan = self.store.plan_purge()
        self.assertEqual({i['checkpointId'] for i in plan['items']}, {a, b})
        self.assertEqual(len(self.store.list_entries(include_trash=True)), 2)
        self.store.apply(plan)
        self.assertEqual(self.store.list_entries(include_trash=True), [])

    def test_full_trash_refuses_rotation_without_changing_active_history(self):
        self.store.close()
        self.retention['trashEntries'] = 1
        self.root = self.base / 'small-trash'
        self.store = catalogue.Catalogue(self.root, create=True, retention=self.retention)
        a = self.add(b'A')
        self.store.apply(self.store.plan_delete([a]))
        b = self.add(b'B')
        self.add(b'C')
        before = self.store.list_entries(include_trash=True)
        with self.assertRaisesRegex(ValueError, 'Trash retention is full'):
            self.store.plan_rotation(self.target)
        self.assertEqual(self.store.list_entries(include_trash=True), before)
        self.store.apply(self.store.plan_purge([a]))
        self.store.apply(self.store.plan_rotation(self.target))
        self.assertEqual(next(r for r in self.store.list_entries(include_trash=True) if r['checkpointId'] == b)['status'], 'trash')

    def test_full_store_never_implicitly_purges_or_discards_anchors(self):
        self.store.close()
        self.root = self.base / 'tiny-store'
        self.retention.update(maxEntries=2, trashEntries=2, maxBytes=20 * 1024, maxPassportBytes=20 * 1024, trashBytes=20 * 1024)
        self.store = catalogue.Catalogue(self.root, create=True, retention=self.retention)
        a = self.add(b'A', name='anchor A', pinned=True)
        self.add(b'B', name='anchor B', pinned=True)
        before = self.store.reference(a)
        with self.assertRaisesRegex(ValueError, 'Catalogue is full'):
            self.add(b'C', name='anchor C', pinned=True)
        self.assertEqual(self.store.reference(a), before)

    def test_stale_tampered_and_foreign_plans_are_refused(self):
        a = self.add(b'A')
        plan = self.store.plan_delete([a])
        forged = copy.deepcopy(plan)
        forged['items'][0]['bytes'] += 1
        with self.assertRaisesRegex(ValueError, 'preview changed'):
            self.store.apply(forged)
        self.store.rename(a, 'Named but unpinned', pinned=False)
        with self.assertRaisesRegex(ValueError, 'preview changed'):
            self.store.apply(plan)
        other = catalogue.Catalogue(self.base / 'other', create=True)
        try:
            with self.assertRaises(ValueError):
                other.apply(self.store.plan_delete([a]))
        finally:
            other.close()
        self.store.reference(a)

    def test_corrupt_passport_is_never_staged_or_silently_purged(self):
        a = self.add(b'A')
        self.store.apply(self.store.plan_delete([a]))
        plan = self.store.plan_purge([a])
        rowid = self.store.db.execute('SELECT sequence FROM records WHERE id=?', (a,)).fetchone()[0]
        with self.store.db.blobopen('records', 'archive', rowid) as blob:
            blob.write(b'corruption')
        self.store.db.commit()
        with self.assertRaisesRegex(ValueError, 'Stored passport checksum failed'):
            self.store.apply(plan)
        with self.assertRaisesRegex(ValueError, 'Stored passport checksum failed'):
            self.store.undo(a)
        self.assertEqual(len(self.store.list_entries(include_trash=True)), 1)
        self.assertFalse((self.base / 'staged').exists())

    def test_failed_capture_rolls_back_all_bytes_and_metadata(self):
        a = self.add(b'prior history')
        before = self.store.reference(a)
        archive = self.archive(b'new branch')
        with mock.patch.object(self.store, '_verify', side_effect=OSError('synthetic write interruption')):
            with self.assertRaises(OSError):
                self.store.import_passport(archive)
        self.reopen()
        self.assertEqual(len(self.store.list_entries()), 1)
        self.assertEqual(self.store.reference(a), before)

    def test_changed_input_during_catalogue_copy_keeps_prior_branch_only(self):
        identifier = self.add(b'prior branch')
        archive = self.archive(b'new branch')
        original = passport.scan
        calls = 0
        def mutate(source, sink=None):
            nonlocal calls
            result = original(source, sink)
            calls += 1
            if calls == 1:
                data = bytearray(archive.read_bytes())
                data[512] ^= 1
                archive.write_bytes(data)
            return result
        with mock.patch.object(passport, 'scan', mutate):
            with self.assertRaisesRegex(ValueError, 'changed during import'):
                self.store.import_passport(archive)
        self.assertEqual([r['checkpointId'] for r in self.store.list_entries()], [identifier])

    def test_process_exit_before_commit_recovers_capture_delete_and_purge(self):
        a = self.add(b'original branch')
        archive = self.archive(b'interrupted import')
        scripts = ["c.import_passport(Path(sys.argv[2]))", "c.apply(c.plan_delete([sys.argv[2]]))",
                   "c.apply(c.plan_purge([sys.argv[2]]))"]
        for index, operation in enumerate(scripts):
            if index == 2:
                self.store.apply(self.store.plan_delete([a]))
            before = self.store.list_entries(include_trash=True)
            self.store.close()
            script = (f'import sys,os;from pathlib import Path;sys.path.insert(0,{str(TOOLS)!r});'
                      'from save_catalogue import Catalogue;c=Catalogue(Path(sys.argv[1]));'
                      'c._commit=lambda:os._exit(77);' + operation)
            result = subprocess.run([sys.executable, '-c', script, str(self.root), str(archive) if index == 0 else a], capture_output=True)
            self.assertEqual(result.returncode, 77, result.stderr)
            self.store = catalogue.Catalogue(self.root, clock=lambda: self.now)
            self.assertEqual(self.store.list_entries(include_trash=True), before)
        self.store.undo(a)
        self.store.stage(a, self.target, self.base / 'recovered')
        self.assertEqual((self.base / 'recovered/fixture.srm').read_bytes(), b'original branch')

    def test_undo_respects_full_quick_slots_and_metadata_edits_require_named_pin(self):
        a = self.add(b'A')
        self.store.apply(self.store.plan_delete([a]))
        self.add(b'B')
        self.add(b'C')
        with self.assertRaisesRegex(ValueError, 'slots are full'):
            self.store.undo(a)
        with self.assertRaisesRegex(ValueError, 'explicit name'):
            self.store.rename(self.store.list_entries()[0]['checkpointId'], '', pinned=True)

    def test_unknown_schema_policy_links_and_nonprivate_storage_are_refused(self):
        self.store.close()
        connection = sqlite3.connect(self.root / 'catalogue.sqlite3')
        connection.execute('PRAGMA user_version=2')
        connection.close()
        with self.assertRaisesRegex(ValueError, 'Unsupported save catalogue schema'):
            catalogue.Catalogue(self.root)
        connection = sqlite3.connect(self.root / 'catalogue.sqlite3')
        connection.execute('PRAGMA user_version=1')
        connection.close()
        self.store = catalogue.Catalogue(self.root)
        alias = self.base / 'linked-history'
        alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            catalogue.Catalogue(alias)
        os.chmod(self.root, 0o755)
        with self.assertRaisesRegex(ValueError, 'owner-only'):
            catalogue.Catalogue(self.root)
        os.chmod(self.root, 0o700)
        with self.assertRaisesRegex(ValueError, 'outside repositories'):
            catalogue.Catalogue(TOOLS.parent / 'private-history', create=True)


if __name__ == '__main__':
    unittest.main()
