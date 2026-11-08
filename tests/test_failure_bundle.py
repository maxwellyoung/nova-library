import copy
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tools import failure_bundle as bundle

SCRIPT = Path(__file__).resolve().parents[1] / 'tools/failure_bundle.py'
NOW = dt.datetime(2026, 11, 5, tzinfo=dt.timezone.utc)


def fixture():
    return {'schemaVersion': 1, 'editionId': 'demo:edition-a',
            'observedRecipeId': 'fixture.v1', 'activeRecipeId': 'fixture.v1',
            'observedAt': '2026-11-04T12:00:00Z', 'stage': 'download',
            'facts': [{'code': 'checksum-mismatch', 'method': 'test'}],
            'hypotheses': [{'code': 'interrupted-transfer', 'basedOn': ['checksum-mismatch']}]}


class FailureBundleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.output = self.root / 'new-report.json'
        self.raw = fixture()

    def tearDown(self):
        self.tmp.cleanup()

    def preview(self, raw=None):
        return bundle.preview(self.raw if raw is None else raw, now=NOW)

    def test_preview_is_complete_deterministic_and_has_no_write_or_network(self):
        with mock.patch('socket.socket', side_effect=AssertionError('network attempted')), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('process attempted')):
            report = self.preview()
            self.assertEqual(report, self.preview())
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertEqual(report['bundle']['facts'][0]['method'], 'test')
        self.assertEqual(report['bundle']['hypotheses'][0]['status'], 'unconfirmed')
        self.assertFalse(report['bundle']['currentSetupVerified'])
        self.assertNotIn('commands', report['bundle'])
        self.assertEqual(report['bundle']['recipeScope'], 'same-declared-recipe')

    def test_explicit_digest_exports_exact_private_bytes_without_send(self):
        report = self.preview()
        result = bundle.export(self.raw, self.output, approve_sha256=report['sha256'], now=NOW)
        data = self.output.read_bytes()
        self.assertEqual(len(data), report['bytes'])
        self.assertEqual(hashlib.sha256(data).hexdigest(), report['sha256'])
        self.assertEqual(json.loads(data), report['bundle'])
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        self.assertTrue(result['exported'])
        self.assertFalse(result['sent'])

    def test_no_approval_cancel_and_stale_preview_never_create_output(self):
        for digest in [None, '', '0' * 64, True, ['bad']]:
            with self.assertRaises(bundle.BundleError):
                bundle.export(self.raw, self.output, approve_sha256=digest, now=NOW)
            self.assertFalse(self.output.exists())
        digest = self.preview()['sha256']
        self.raw['facts'][0]['code'] = 'transfer-interrupted'
        self.raw['hypotheses'][0]['basedOn'] = ['transfer-interrupted']
        with self.assertRaises(bundle.BundleError):
            bundle.export(self.raw, self.output, approve_sha256=digest, now=NOW)
        self.assertFalse(self.output.exists())

    def test_sensitive_fields_are_discarded_and_raw_ids_are_not_exported(self):
        secrets = ['ghp_' + 'A' * 30, '/' + 'Users/demo/private', 'owner@' + 'private.example',
                   'private-game.sfc', 'private-progress.srm', 'Bearer private-secret']
        for key in bundle.DISCARDED:
            self.raw[key] = {'arbitrary': secrets, 'nested': {'not-followed': 'private'}}
        report = self.preview()
        text = json.dumps(report)
        for secret in secrets + [self.raw['editionId'], self.raw['observedRecipeId']]:
            self.assertNotIn(secret, text)
        self.assertEqual(report['bundle']['discardedFieldCount'], len(bundle.DISCARDED))
        self.assertEqual(report['bundle']['editionSha256'], hashlib.sha256(self.raw['editionId'].encode()).hexdigest())
        self.assertEqual(bundle.findings('synthetic-report', text), [])

    def test_identity_screen_rejects_path_account_tokens_markup_and_controls(self):
        values = ['/' + 'Users/demo/private', 'owner@' + 'private.example', 'ghp_' + 'A' * 30,
                  'sk-' + 'Z' * 30, '../escape', 'file.srm/path', '<script>', 'thing\nvalue', 'x' * 129, '', None]
        for value in values:
            for field in ['editionId', 'observedRecipeId', 'activeRecipeId']:
                if field == 'activeRecipeId' and value is None:
                    continue
                raw = fixture()
                raw[field] = value
                with self.subTest(field=field, value_type=type(value).__name__), self.assertRaises(bundle.BundleError):
                    self.preview(raw)

    def test_unknown_and_nested_fields_cannot_smuggle_text_or_commands(self):
        variants = []
        raw = fixture(); raw['freeText'] = 'sensitive'; variants.append(raw)
        raw = fixture(); raw['facts'][0]['note'] = 'sensitive'; variants.append(raw)
        raw = fixture(); raw['hypotheses'][0]['command'] = 'rm'; variants.append(raw)
        raw = fixture(); raw['facts'][0]['code'] = '<script>'; variants.append(raw)
        raw = fixture(); raw['hypotheses'][0]['code'] = 'proven-cause'; variants.append(raw)
        raw = fixture(); raw['facts'][0]['method'] = 'automatically-certified'; variants.append(raw)
        for raw in variants:
            with self.assertRaises(bundle.BundleError):
                self.preview(raw)

    def test_facts_require_matching_stage_and_hypotheses_require_retained_facts(self):
        self.raw['stage'] = 'gameplay'
        with self.assertRaises(bundle.BundleError): self.preview()
        self.raw = fixture(); self.raw['hypotheses'][0]['basedOn'] = ['file-missing']
        with self.assertRaises(bundle.BundleError): self.preview()
        self.raw['hypotheses'][0]['basedOn'] = []
        with self.assertRaises(bundle.BundleError): self.preview()
        self.raw = fixture(); self.raw['facts'].append(copy.deepcopy(self.raw['facts'][0]))
        with self.assertRaises(bundle.BundleError): self.preview()

    def test_historical_and_unlinked_recipes_do_not_diagnose_current_setup(self):
        for active, scope in [('fixture.v2', 'historical-recipe'), (None, 'unlinked')]:
            self.raw['activeRecipeId'] = active
            out = self.preview()['bundle']
            self.assertEqual(out['recipeScope'], scope)
            self.assertFalse(out['currentSetupVerified'])
            self.assertIn('does not establish the current setup', out['recoveryHints'][0])
            self.assertEqual(out['facts'][0]['code'], 'checksum-mismatch')
        self.raw['activeRecipeId'] = self.raw['observedRecipeId']
        self.assertFalse(self.preview()['bundle']['currentSetupVerified'])

    def test_safe_factual_recovery_does_not_invent_success_or_execute_repair(self):
        self.raw.update(stage='save-restore', facts=[{'code': 'save-result-unknown', 'method': 'log'}], hypotheses=[])
        out = self.preview()['bundle']
        self.assertIn('not established', out['facts'][0]['statement'])
        self.assertIn('Keep the active session', out['recoveryHints'][0])
        self.assertEqual(out['hypotheses'], [])
        self.raw.update(stage='exit-return', facts=[{'code': 'runtime-idle-unknown', 'method': 'observed'}])
        out = self.preview()['bundle']
        self.assertIn('Keep cleanup blocked', out['recoveryHints'][0])

    def test_schema_missing_malformed_future_and_collection_bounds(self):
        variants = [None, [], {}, {**fixture(), 'schemaVersion': True}, {**fixture(), 'schemaVersion': 2}]
        for stamp in ['2026-02-30T00:00:00Z', '2026-11-06T00:00:00Z', '2026-11-04', 123]:
            variants.append({**fixture(), 'observedAt': stamp})
        for key, value in [('facts', []), ('facts', [fixture()['facts'][0]] * (bundle.MAX_FACTS + 1)),
                           ('hypotheses', [fixture()['hypotheses'][0]] * (bundle.MAX_HYPOTHESES + 1)),
                           ('stage', {}), ('facts', [{'code': [], 'method': 'test'}]),
                           ('hypotheses', [{'code': 'unknown-cause', 'basedOn': [[]]}])]:
            variants.append({**fixture(), key: value})
        for raw in variants:
            with self.subTest(raw_type=type(raw).__name__), self.assertRaises(bundle.BundleError): bundle.preview(raw, now=NOW)
        with mock.patch.object(bundle, 'MAX_OUTPUT', 32):
            with self.assertRaises(bundle.BundleError): self.preview()

    def test_reader_rejects_oversize_missing_duplicate_invalid_symlink_and_fifo(self):
        source = self.root / 'input.json'
        for data in [b'x' * (bundle.MAX_INPUT + 1), b'{broken', b'{"schemaVersion":1,"schemaVersion":1}', b'\xff', b'[' * 1200]:
            source.write_bytes(data)
            with self.assertRaises(bundle.BundleError): bundle.read_descriptor(source)
        with self.assertRaises(bundle.BundleError): bundle.read_descriptor(self.root / 'missing')
        with self.assertRaises(bundle.BundleError): bundle.read_descriptor(self.root)
        link = self.root / 'linked'; link.symlink_to(source)
        with self.assertRaises(bundle.BundleError): bundle.read_descriptor(link)
        fifo = self.root / 'pipe'; os.mkfifo(fifo)
        with self.assertRaises(bundle.BundleError): bundle.read_descriptor(fifo)
        source.write_text(json.dumps(fixture()))
        self.assertEqual(bundle.read_descriptor(source), fixture())

    def test_existing_output_links_and_linked_parents_are_preserved(self):
        report = self.preview()
        self.output.write_bytes(b'preserve')
        with self.assertRaises(bundle.BundleError):
            bundle.export(self.raw, self.output, approve_sha256=report['sha256'], now=NOW)
        self.assertEqual(self.output.read_bytes(), b'preserve')
        link = self.root / 'link'; link.symlink_to(self.output)
        with self.assertRaises(bundle.BundleError):
            bundle.export(self.raw, link, approve_sha256=report['sha256'], now=NOW)
        alias = self.root / 'alias'; alias.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(bundle.BundleError):
            bundle.export(self.raw, alias / 'other', approve_sha256=report['sha256'], now=NOW)
        self.assertFalse((self.root / 'other').exists())

    def test_failed_write_cleans_only_new_output(self):
        digest = self.preview()['sha256']
        with mock.patch.object(bundle.os, 'fsync', side_effect=OSError('private error')):
            with self.assertRaises(bundle.BundleError):
                bundle.export(self.raw, self.output, approve_sha256=digest, now=NOW)
        self.assertFalse(self.output.exists())

    def test_cli_previews_and_exports_then_refuses_without_echoing_private_errors(self):
        descriptor = self.root / 'fixture.json'; descriptor.write_text(json.dumps(fixture()))
        result = subprocess.run([sys.executable, str(SCRIPT), 'preview', str(descriptor)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        digest = json.loads(result.stdout)['sha256']
        result = subprocess.run([sys.executable, str(SCRIPT), 'export', str(descriptor), str(self.output),
                                 '--approve-sha256', digest], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(json.loads(result.stdout)['sent'])
        descriptor.write_text('secret malformed data')
        result = subprocess.run([sys.executable, str(SCRIPT), 'preview', str(descriptor)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(str(descriptor), result.stderr)
        self.assertNotIn('secret malformed data', result.stderr)
        self.assertEqual(result.stdout, '')


if __name__ == '__main__':
    unittest.main()
