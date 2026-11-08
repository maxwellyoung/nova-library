import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/save_passport.py'
spec = importlib.util.spec_from_file_location('save_passport', SCRIPT)
passport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(passport)


class SavePassport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name).resolve()
        self.source = self.base / 'source'
        self.source.mkdir()
        (self.source / 'cards').mkdir()
        (self.source / 'cards/card.srm').write_bytes(b'original game progress')
        (self.source / 'empty.srm').write_bytes(b'')
        (self.source / 'unselected.cfg').write_text('not selected')
        self.selection = {'schemaVersion': 1, 'editionId': 'demo:edition-a', 'recipeId': 'fixture.v1',
                          'kind': 'native-save', 'runtime': {'name': 'Fixture runtime', 'version': '1.0', 'core': 'Fixture core'},
                          'files': ['cards/card.srm', 'empty.srm']}
        self.output = self.base / 'backup.nvs'
        self.target = {k: copy.deepcopy(self.selection[k]) for k in ('editionId', 'recipeId', 'kind', 'runtime')}

    def tearDown(self):
        self.tmp.cleanup()

    def pack(self):
        return passport.pack(self.source, self.selection, self.output, source_idle=True)

    def crafted(self, manifest, payload=b'original game progress', link=False):
        with tarfile.open(self.output, 'w', format=tarfile.USTAR_FORMAT) as archive:
            item = passport.header('payload/0000', len(payload))
            if link:
                item.type = tarfile.SYMTYPE
                item.linkname = '../outside'
            archive.addfile(item, io.BytesIO(payload))
            data = (manifest if isinstance(manifest, str) else json.dumps(manifest)).encode()
            archive.addfile(passport.header('manifest.json', len(data)), io.BytesIO(data))

    def sample_manifest(self, path='cards/card.srm'):
        return {**copy.deepcopy(self.target), 'schemaVersion': 1, 'createdAt': '2026-11-04T00:00:00Z',
                'sourceState': 'operator-confirmed-idle', 'files': [{'path': path, 'bytes': 22,
                 'sha256': hashlib.sha256(b'original game progress').hexdigest()}]}

    def test_round_trip_keeps_originals_and_only_stages_explicit_files(self):
        result = self.pack()
        self.assertEqual(passport.verify(self.output), result)
        staged = self.base / 'staged'
        self.assertEqual(passport.stage(self.output, self.target, staged), result)
        self.assertEqual((staged / 'cards/card.srm').read_bytes(), b'original game progress')
        self.assertEqual((staged / 'empty.srm').read_bytes(), b'')
        self.assertFalse((staged / 'unselected.cfg').exists())
        self.assertEqual((self.source / 'cards/card.srm').read_bytes(), b'original game progress')
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(staged.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE((staged / 'cards/card.srm').stat().st_mode), 0o600)
        with tarfile.open(self.output) as archive:
            metadata = json.loads(archive.extractfile('manifest.json').read())
        self.assertNotIn(str(self.source), json.dumps(metadata))
        self.assertEqual(metadata['sourceState'], 'operator-confirmed-idle')

    def test_closed_source_declaration_is_required(self):
        for value in (False, None, 'yes', 1):
            with self.assertRaises(ValueError):
                passport.pack(self.source, self.selection, self.output, source_idle=value)
        self.assertFalse(self.output.exists())

    def test_existing_archive_and_existing_stage_are_never_replaced(self):
        self.output.write_bytes(b'keep prior backup')
        with self.assertRaises(ValueError):
            self.pack()
        self.assertEqual(self.output.read_bytes(), b'keep prior backup')
        self.output.unlink()
        self.pack()
        staged = self.base / 'existing'
        staged.mkdir()
        (staged / 'keep.srm').write_bytes(b'keep live progress')
        with self.assertRaises(ValueError):
            passport.stage(self.output, self.target, staged)
        self.assertEqual((staged / 'keep.srm').read_bytes(), b'keep live progress')

    def test_backup_must_be_outside_the_source(self):
        with self.assertRaises(ValueError):
            passport.pack(self.source, self.selection, self.source / 'backup.nvs', source_idle=True)
        self.assertFalse((self.source / 'backup.nvs').exists())

    def test_symlink_sources_archives_and_output_parents_are_refused(self):
        (self.source / 'linked.srm').symlink_to(self.source / 'cards/card.srm')
        self.selection['files'] = ['linked.srm']
        with self.assertRaises(ValueError):
            self.pack()
        (self.source / 'linked-dir').symlink_to(self.source / 'cards', target_is_directory=True)
        self.selection['files'] = ['linked-dir/card.srm']
        with self.assertRaises(ValueError):
            self.pack()
        self.selection['files'] = ['cards/card.srm']
        self.pack()
        alias = self.base / 'alias.nvs'
        alias.symlink_to(self.output)
        with self.assertRaises(ValueError):
            passport.verify(alias)
        folder = self.base / 'alias-dir'
        folder.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError):
            passport.stage(self.output, self.target, folder / 'child')

    def test_edition_kind_recipe_and_all_runtime_parts_must_match(self):
        self.pack()
        targets = []
        for key, value in [('editionId', 'demo:other'), ('recipeId', 'fixture.v2'), ('kind', 'emulator-state')]:
            target = copy.deepcopy(self.target)
            target[key] = value
            targets.append(target)
        for key in ('name', 'version', 'core'):
            target = copy.deepcopy(self.target)
            target['runtime'][key] += ' changed'
            targets.append(target)
        for target in targets:
            with self.assertRaises(ValueError):
                passport.stage(self.output, target, self.base / 'stage')
            self.assertFalse((self.base / 'stage').exists())

    def test_review_is_read_only_and_explains_each_mismatch_without_identity_values(self):
        self.pack()
        before = {p.relative_to(self.base): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.assertEqual(passport.review(self.output, self.target), passport.verify(self.output))
        cases = [('editionId', 'Game edition differs'), ('recipeId', 'Setup recipe differs'), ('kind', 'Save kind differs')]
        for field, reason in cases:
            target = copy.deepcopy(self.target)
            target[field] = 'emulator-state' if field == 'kind' else 'private-other-value'
            with self.assertRaisesRegex(ValueError, reason):
                passport.review(self.output, target)
        for field in ('name', 'version', 'core'):
            target = copy.deepcopy(self.target)
            target['runtime'][field] = 'private-other-value'
            with self.assertRaisesRegex(ValueError, 'Runtime .*differs') as error:
                passport.review(self.output, target)
            self.assertNotIn('private-other-value', str(error.exception))
        after = {p.relative_to(self.base): p.read_bytes() for p in self.base.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_unknown_runtime_can_be_preserved_but_never_approved_for_restore(self):
        self.selection['runtime']['version'] = 'unknown'
        self.target['runtime']['version'] = 'unknown'
        self.pack()
        self.assertEqual(passport.verify(self.output)['runtime']['version'], 'unknown')
        with self.assertRaisesRegex(ValueError, 'Unknown edition or runtime/setup identity'):
            passport.review(self.output, self.target)
        with self.assertRaisesRegex(ValueError, 'Unknown edition or runtime/setup identity'):
            passport.stage(self.output, self.target, self.base / 'stage')
        self.assertFalse((self.base / 'stage').exists())
        for placeholder in ('Unknown', '?', '*', 'unverified', 'n/a', 'none', 'null', 'latest', 'current'):
            target = copy.deepcopy(self.target)
            target['runtime']['version'] = placeholder
            with self.assertRaisesRegex(ValueError, 'Unknown edition or runtime/setup identity'):
                passport.compatible({**self.sample_manifest(), 'runtime': copy.deepcopy(target['runtime'])}, target)

    def test_state_archive_remains_a_distinct_exact_runtime_backup(self):
        self.selection['kind'] = self.target['kind'] = 'emulator-state'
        self.pack()
        passport.review(self.output, self.target)
        target = copy.deepcopy(self.target)
        target['runtime']['core'] = 'another core'
        with self.assertRaisesRegex(ValueError, 'Runtime core differs'):
            passport.stage(self.output, target, self.base / 'stage')
        passport.stage(self.output, self.target, self.base / 'stage')

    def test_divergent_progress_is_kept_in_separate_stages_without_timestamp_selection(self):
        self.pack()
        first = self.base / 'first-branch'
        passport.stage(self.output, self.target, first)
        newer = b'a different offline progress branch'
        (self.source / 'cards/card.srm').write_bytes(newer)
        second_archive = self.base / 'second.nvs'
        passport.pack(self.source, self.selection, second_archive, source_idle=True)
        passport.review(second_archive, self.target)
        with self.assertRaisesRegex(ValueError, 'Staging output already exists'):
            passport.stage(second_archive, self.target, first)
        second = self.base / 'second-branch'
        passport.stage(second_archive, self.target, second)
        self.assertEqual((first / 'cards/card.srm').read_bytes(), b'original game progress')
        self.assertEqual((second / 'cards/card.srm').read_bytes(), newer)
        self.assertEqual(passport.verify(self.output)['files'][0]['sha256'], hashlib.sha256(b'original game progress').hexdigest())

    def test_future_and_noninteger_schemas_are_refused_before_staging(self):
        for version in (2, 999, 1.0, True, None):
            with self.subTest(version=version):
                self.selection['schemaVersion'] = version
                with self.assertRaises(ValueError):
                    self.pack()
                meta = self.sample_manifest()
                meta['schemaVersion'] = version
                self.crafted(meta)
                with self.assertRaisesRegex(ValueError, 'Unsupported passport schema'):
                    passport.review(self.output, self.target)
                with self.assertRaises(ValueError):
                    passport.stage(self.output, self.target, self.base / 'stage')
                self.output.unlink()
                self.assertFalse((self.base / 'stage').exists())

    def test_duplicate_json_identity_keys_are_ambiguous_even_when_values_match(self):
        for data in ('{"editionId":"first","editionId":"second"}',
                     '{"runtime":{"version":"1","version":"1"}}'):
            descriptor = self.base / 'ambiguous.json'
            descriptor.write_text(data)
            with self.assertRaisesRegex(ValueError, 'Duplicate JSON metadata key'):
                passport.read_json(descriptor)
        raw = json.dumps(self.sample_manifest()).replace('"schemaVersion": 1', '"schemaVersion": 2, "schemaVersion": 1')
        self.crafted(raw)
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON metadata key'):
            passport.stage(self.output, self.target, self.base / 'stage')
        self.assertFalse((self.base / 'stage').exists())

    def test_corruption_is_detected_before_staging(self):
        self.pack()
        data = bytearray(self.output.read_bytes())
        data[512] ^= 1
        self.output.write_bytes(data)
        with self.assertRaises(ValueError):
            passport.verify(self.output)
        with self.assertRaises(ValueError):
            passport.stage(self.output, self.target, self.base / 'stage')
        self.assertFalse((self.base / 'stage').exists())

    def test_unsafe_and_colliding_paths_do_not_reach_the_filesystem(self):
        for path in ('../outside.srm', '/outside.srm', '.', 'a//b', 'a/./b', 'C:/save', 'a\\b', '.private/file', 'CON.srm', 'a. /file', 'a?.srm', 'a|b.srm'):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    passport.relative(path)
        for files in (['a.srm', 'A.srm'], ['a.srm', 'a.srm/child'], ['a.srm/child', 'a.srm']):
            with self.assertRaises(ValueError):
                passport.paths_unique(files)
        self.crafted(self.sample_manifest('../outside.srm'))
        with self.assertRaises(ValueError):
            passport.stage(self.output, self.target, self.base / 'stage')
        self.assertFalse((self.base / 'outside.srm').exists())
        self.assertFalse((self.base / 'stage').exists())

    def test_links_unexpected_entries_and_trailers_are_refused(self):
        self.crafted(self.sample_manifest(), link=True)
        with self.assertRaises(ValueError):
            passport.verify(self.output)
        self.output.unlink()
        self.pack()
        original = self.output.read_bytes()
        for data in (original[:-512], original + b'hidden content'):
            self.output.write_bytes(data)
            with self.assertRaises(ValueError):
                passport.verify(self.output)
        altered = bytearray(original)
        altered[-1] = 1
        self.output.write_bytes(altered)
        with self.assertRaises(ValueError):
            passport.verify(self.output)

    def test_invalid_metadata_and_size_limits_fail_closed(self):
        for value in (None, [], {'schemaVersion': True}, {**self.selection, 'kind': []}, {**self.selection, 'extra': 'not allowed'}):
            with self.assertRaises(ValueError):
                passport.pack(self.source, value, self.output, source_idle=True)
        meta = self.sample_manifest()
        meta['files'][0]['bytes'] = True
        with self.assertRaises(ValueError):
            passport.manifest(meta)
        with mock.patch.object(passport, 'MAX_FILE', 3):
            with self.assertRaises(ValueError):
                self.pack()
        self.assertFalse(self.output.exists())

    def test_unexpected_entries_and_oversized_archive_headers_are_rejected(self):
        for name, size in [('unexpected', 0), ('../escape', 0), ('/absolute', 0), ('payload/0000', passport.MAX_FILE + 1)]:
            self.output.write_bytes(passport.header(name, size).tobuf(format=tarfile.USTAR_FORMAT) + bytes(10240 - 512))
            with self.assertRaises(ValueError):
                passport.verify(self.output)

    def test_a_backup_destination_created_during_capture_is_preserved(self):
        original = passport.os.link
        def concurrent(candidate, output):
            Path(output).write_bytes(b'another backup arrived')
            original(candidate, output)
        with mock.patch.object(passport.os, 'link', concurrent):
            with self.assertRaises(FileExistsError):
                self.pack()
        self.assertEqual(self.output.read_bytes(), b'another backup arrived')
        self.assertEqual((self.source / 'cards/card.srm').read_bytes(), b'original game progress')

    def test_a_stage_destination_created_during_verification_is_preserved(self):
        self.pack()
        original = passport.scan
        output = self.base / 'stage'
        def concurrent(source, sink=None):
            result = original(source, sink)
            if not output.exists():
                output.mkdir()
                (output / 'keep.srm').write_bytes(b'another task owns this')
            return result
        with mock.patch.object(passport, 'scan', concurrent):
            with self.assertRaises(FileExistsError):
                passport.stage(self.output, self.target, output)
        self.assertEqual((output / 'keep.srm').read_bytes(), b'another task owns this')

    def test_source_changed_during_capture_never_publishes_a_backup(self):
        original = passport.HashReader.read
        changed = False
        def mutate(reader, count):
            nonlocal changed
            data = original(reader, count)
            if not changed:
                changed = True
                (self.source / 'cards/card.srm').write_bytes(b'concurrent game write')
            return data
        with mock.patch.object(passport.HashReader, 'read', mutate):
            with self.assertRaises(ValueError):
                self.pack()
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.base.glob('.save-passport-*')))

    def test_staging_rechecks_payload_if_archive_changes_between_passes(self):
        self.pack()
        original = passport.scan
        calls = 0
        def mutate(source, sink=None):
            nonlocal calls
            result = original(source, sink)
            calls += 1
            if calls == 1:
                data = bytearray(self.output.read_bytes())
                data[512] ^= 1
                self.output.write_bytes(data)
            return result
        with mock.patch.object(passport, 'scan', mutate):
            with self.assertRaises(ValueError):
                passport.stage(self.output, self.target, self.base / 'stage')
        self.assertFalse((self.base / 'stage').exists())
        self.assertFalse(list(self.base.glob('.save-stage-*')))

    def test_a_previously_copied_file_changing_before_publication_is_detected(self):
        original = passport.HashReader.read
        reads = 0
        def mutate(reader, count):
            nonlocal reads
            data = original(reader, count)
            reads += 1
            if reads == 2:
                (self.source / 'cards/card.srm').write_bytes(b'later game write')
            return data
        # Make the second file nonempty so it is read after the first file's own guard.
        (self.source / 'empty.srm').write_bytes(b'second save')
        with mock.patch.object(passport.HashReader, 'read', mutate):
            with self.assertRaises(ValueError):
                self.pack()
        self.assertFalse(self.output.exists())

    def test_nonregular_descriptor_does_not_block_or_publish(self):
        fifo = self.base / 'descriptor.fifo'
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            passport.read_json(fifo)

    def test_cli_round_trip_and_private_error_output(self):
        selection = self.base / 'selection.json'
        selection.write_text(json.dumps(self.selection))
        target = self.base / 'target.json'
        target.write_text(json.dumps(self.target))
        def run(*args):
            return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(run('pack', '--source', self.source, '--selection', selection, '--output', self.output, '--source-idle').returncode, 0)
        self.assertEqual(run('verify', self.output).returncode, 0)
        review = run('review', self.output, '--target', target)
        self.assertEqual(review.returncode, 0)
        self.assertIn('emulator import and boot remain unverified', review.stdout)
        self.assertFalse((self.base / 'staged').exists())
        self.assertEqual(run('stage', self.output, '--target', target, '--output', self.base / 'staged').returncode, 0)
        selection.write_text('{')
        result = run('pack', '--source', self.source, '--selection', selection, '--output', self.base / 'second.nvs', '--source-idle')
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(str(self.base), result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
