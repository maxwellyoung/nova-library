import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import artwork_overrides as covers
import make_demo


class CoverRepairs(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'input'; self.source.mkdir()
        self.output = self.root / 'output'; self.output.mkdir()
        (self.output / 'art').mkdir()
        self.image = make_demo.cover_png('#bc7747', 0)
        (self.source / 'cover.png').write_bytes(self.image)
        self.repair = {'path': 'cover.png', 'sha256': hashlib.sha256(self.image).hexdigest(),
                       'source': 'Synthetic cover drawn for the test edition', 'mode': 'replace'}
        self.records = [{'edition': 'demo:orbit', 'art': 'art/banner.png', 'launchable': False, 'minutes': '0'},
                        {'edition': 'demo:other', 'art': 'art/other.png', 'launchable': True}]
        (self.output / 'art/banner.png').write_bytes(b'previous banner')
        (self.output / 'art/other.png').write_bytes(b'unrelated original')

    def apply(self, records=None, repairs=None):
        return covers.apply_repairs(self.records if records is None else records,
                                   {'demo:orbit': self.repair} if repairs is None else repairs,
                                   self.source, self.output)

    def hashes(self):
        return {str(p.relative_to(self.output)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.output.rglob('*') if p.is_file()}

    def test_replaces_bad_banner_with_provenance_and_survives_two_fresh_catalogue_refreshes(self):
        original = copy.deepcopy(self.records)
        untouched = self.hashes()
        self.assertEqual(self.apply(), 1)
        expected = copy.deepcopy(self.records)
        self.assertEqual(expected[0]['artwork_source'], self.repair['source'])
        self.assertEqual(expected[0]['artwork_sha256'], self.repair['sha256'])
        self.assertEqual((self.output / expected[0]['art']).read_bytes(), self.image)
        self.assertEqual(expected[1], original[1])
        self.assertEqual(expected[0]['launchable'], original[0]['launchable'])
        self.assertEqual(expected[0]['minutes'], original[0]['minutes'])
        files = self.hashes()
        for _ in range(2):
            refreshed = copy.deepcopy(original)
            self.assertEqual(self.apply(refreshed), 1)
            self.assertEqual(refreshed, expected)
            self.assertEqual(self.hashes(), files)
        for name, digest in untouched.items(): self.assertEqual(files[name], digest)
        self.assertNotIn(str(self.root), json.dumps(expected))

    def test_fill_preserves_existing_cover_and_missing_editions_wait(self):
        self.repair['mode'] = 'fill'
        original = copy.deepcopy(self.records)
        before = self.hashes()
        self.assertEqual(self.apply(), 0)
        self.assertEqual(self.records, original)
        self.assertEqual(self.apply(repairs={'demo:absent': self.repair}), 0)
        self.assertEqual(self.hashes(), before)
        self.records[0]['art'] = ''
        self.assertEqual(self.apply(), 1)

    def test_exact_edition_not_same_title_or_other_region_and_duplicate_is_refused(self):
        self.records[0]['title'] = 'Orbit'; self.records[1]['title'] = 'Orbit'
        self.records[1]['edition'] = 'demo:orbit-eu'
        other = copy.deepcopy(self.records[1])
        self.apply()
        self.assertEqual(self.records[1], other)
        duplicate = [{'edition': 'demo:orbit'}, {'edition': 'demo:orbit'}]
        before = copy.deepcopy(duplicate)
        with self.assertRaises(ValueError): self.apply(duplicate)
        self.assertEqual(duplicate, before)

    def test_all_validation_precedes_record_and_asset_changes(self):
        before, files = copy.deepcopy(self.records), self.hashes()
        broken = dict(self.repair, sha256='0' * 64)
        with self.assertRaises(ValueError):
            self.apply(repairs={'demo:orbit': self.repair, 'demo:other': broken})
        self.assertEqual(self.records, before); self.assertEqual(self.hashes(), files)

    def test_path_escape_external_symlink_and_invalid_source_are_refused(self):
        outside = self.root / 'outside.png'; outside.write_bytes(self.image)
        (self.source / 'link.png').symlink_to(outside)
        for path in ['../outside.png', str(outside), 'link.png', 'missing.png', 'nested\\cover.png']:
            with self.subTest(path=path):
                with self.assertRaises(ValueError): self.apply(repairs={'demo:orbit': dict(self.repair, path=path)})
        for source in ['', '  ', 'one\ntwo', 'x' * 501, None]:
            with self.assertRaises(ValueError): self.apply(repairs={'demo:orbit': dict(self.repair, source=source)})

    def test_unpinned_unknown_mode_extra_fields_and_bad_identity_are_refused(self):
        for repair in [dict(self.repair, sha256=''), dict(self.repair, mode='auto'),
                       dict(self.repair, guessed_title='Orbit'), {'path':'cover.png'}]:
            with self.assertRaises(ValueError): self.apply(repairs={'demo:orbit': repair})
        with self.assertRaises(ValueError): self.apply(repairs={'../orbit': self.repair})

    def test_changed_image_bad_signature_wrong_extension_and_limits_are_refused(self):
        (self.source / 'cover.png').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.apply()
        self.repair['sha256'] = hashlib.sha256(b'changed').hexdigest()
        with self.assertRaises(ValueError): self.apply()
        (self.source / 'wrong.jpg').write_bytes(self.image)
        bad = dict(self.repair, path='wrong.jpg', sha256=hashlib.sha256(self.image).hexdigest())
        with self.assertRaises(ValueError): self.apply(repairs={'demo:orbit': bad})
        (self.source / 'cover.png').write_bytes(self.image)
        self.repair['sha256'] = hashlib.sha256(self.image).hexdigest()
        with mock.patch.object(covers, 'MAX_BYTES', 1):
            with self.assertRaises(ValueError): self.apply()
        with mock.patch.object(covers, 'MAX_TOTAL_BYTES', 1):
            with self.assertRaises(ValueError): self.apply()

    def test_preexisting_asset_tampering_and_output_symlinks_are_preserved(self):
        self.apply(); asset = self.output / self.records[0]['art']
        asset.write_bytes(b'owner changed bytes')
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(asset.read_bytes(), b'owner changed bytes')
        asset.unlink(); asset.symlink_to(self.source / 'cover.png')
        with self.assertRaises(ValueError): self.apply()
        self.assertTrue(asset.is_symlink())
        asset.unlink(); (self.output / 'art/banner.png').unlink(); (self.output / 'art/other.png').unlink()
        (self.output / 'art').rmdir()
        elsewhere = self.root / 'elsewhere'; elsewhere.mkdir()
        (self.output / 'art').symlink_to(elsewhere, target_is_directory=True)
        with self.assertRaises(ValueError): self.apply()
        self.assertEqual(list(elsewhere.iterdir()), [])

    def test_write_failure_keeps_records_and_original_asset_bytes(self):
        before, files = copy.deepcopy(self.records), self.hashes()
        original = Path.open
        def refuse(path, *args, **kwargs):
            if args and args[0] == 'xb': raise OSError('synthetic write refusal')
            return original(path, *args, **kwargs)
        with mock.patch.object(Path, 'open', refuse):
            with self.assertRaises(OSError): self.apply()
        self.assertEqual(self.records, before); self.assertEqual(self.hashes(), files)


if __name__ == '__main__':
    unittest.main()
