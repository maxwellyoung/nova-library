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


def synthetic_capture(status='collected'):
    """A disposable producer fixture; it never contacts a runtime or reads logs."""
    raw = fixture()
    raw['schemaVersion'] = 2
    observed = {'editionId': raw['editionId'], 'recipeId': raw['observedRecipeId'],
                'sourceSha256': 'a' * 64, 'buildSha256': 'b' * 64,
                'runtimeId': 'demo.runtime', 'runtimeVersion': '1.2.3'}
    raw['provenance'] = {'observed': observed, 'active': copy.deepcopy(observed),
                         'collection': {'status': status, 'method': 'synthetic',
                                        'collectedAt': '2026-11-04T12:01:00Z'}}
    return raw


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

    def test_native_origin_preserves_legacy_bytes_and_minimizes_context(self):
        raw = synthetic_capture()
        legacy = bundle.preview(raw, now=NOW)
        explicit = copy.deepcopy(raw)
        explicit['origin'] = 'operator'
        self.assertEqual(bundle.preview(explicit, now=NOW), legacy)
        raw['origin'] = 'native-save-copies'
        raw['stage'] = 'preflight'
        raw['facts'] = [{'code': 'copy-history-unavailable', 'method': 'test'}]
        raw['hypotheses'] = [{'code': 'unknown-cause', 'basedOn': ['copy-history-unavailable']}]
        raw['activeRecipeId'] = None
        raw['provenance']['active'] = None
        for field in ('sourceSha256', 'buildSha256', 'runtimeId', 'runtimeVersion'):
            raw['provenance']['observed'][field] = None
        report = bundle.preview(raw, now=NOW)['bundle']
        self.assertEqual(report['source'], 'native-save-copies-observation')
        self.assertEqual(report['provenance']['collection']['method'], 'synthetic')
        self.assertEqual(report['provenance']['contextScope'], 'unlinked')
        self.assertFalse(report['currentSetupVerified'])
        self.assertFalse(report['provenance']['authenticated'])
        self.assertEqual(report['hypotheses'][0]['status'], 'unconfirmed')

    def test_cloud_play_observation_is_unlinked_and_fixed_vocabulary(self):
        for code in ('download-file-unverified', 'download-changed-before-open',
                     'download-checksum-unverified', 'runtime-request-refused'):
            raw = synthetic_capture()
            raw.update(origin='native-cloud-play', stage='preflight', activeRecipeId=None,
                       facts=[{'code': code, 'method': 'test'}],
                       hypotheses=[{'code': 'unknown-cause', 'basedOn': [code]}])
            raw['provenance']['active'] = None
            for field in ('sourceSha256', 'buildSha256', 'runtimeId', 'runtimeVersion'):
                raw['provenance']['observed'][field] = None
            report = bundle.preview(raw, now=NOW)['bundle']
            self.assertEqual(report['source'], 'native-cloud-play-observation')
            self.assertFalse(report['currentSetupVerified'])
            self.assertFalse(report['provenance']['authenticated'])
            self.assertEqual(report['hypotheses'][0]['status'], 'unconfirmed')
            raw['stage'] = 'gameplay'
            with self.assertRaises(bundle.BundleError):
                bundle.preview(raw, now=NOW)

    def test_native_origin_and_copy_stage_are_bounded(self):
        for origin in ('unsupported', None, [], False):
            raw = synthetic_capture()
            raw['origin'] = origin
            with self.assertRaises(bundle.BundleError):
                bundle.preview(raw, now=NOW)
        raw = fixture()
        raw['origin'] = 'native-save-copies'
        with self.assertRaises(bundle.BundleError):
            bundle.preview(raw, now=NOW)

        raw = synthetic_capture()
        raw['facts'] = [{'code': 'copy-archive-unverified', 'method': 'test'}]
        raw['hypotheses'] = []
        with self.assertRaises(bundle.BundleError):
            bundle.preview(raw, now=NOW)

    def test_theme_load_fact_does_not_claim_source_identity_or_cause(self):
        raw = synthetic_capture()
        raw.update(origin='native-theme-load', editionId='nova:launcher', stage='preflight',
                   activeRecipeId=None, facts=[{'code': 'selected-theme-load-failed', 'method': 'test'}],
                   hypotheses=[{'code': 'unknown-cause', 'basedOn': ['selected-theme-load-failed']}])
        raw['provenance']['observed']['editionId'] = raw['editionId']
        raw['provenance']['active'] = None
        for field in ('sourceSha256', 'buildSha256', 'runtimeId', 'runtimeVersion'):
            raw['provenance']['observed'][field] = None
        report = bundle.preview(raw, now=NOW)['bundle']
        self.assertEqual(report['source'], 'native-theme-load-observation')
        self.assertFalse(report['currentSetupVerified'])
        self.assertIsNone(report['provenance']['observed']['sourceSha256'])
        self.assertEqual(report['hypotheses'][0]['status'], 'unconfirmed')
        raw['stage'] = 'gameplay'
        with self.assertRaises(bundle.BundleError):
            bundle.preview(raw, now=NOW)

    def test_theme_construction_fact_keeps_cause_unknown_and_context_unlinked(self):
        raw = synthetic_capture()
        raw.update(origin='native-theme-load', editionId='nova:launcher', stage='preflight',
                   activeRecipeId=None, facts=[{'code': 'selected-theme-construction-failed', 'method': 'test'}],
                   hypotheses=[{'code': 'unknown-cause', 'basedOn': ['selected-theme-construction-failed']}])
        raw['provenance']['observed']['editionId'] = raw['editionId']
        raw['provenance']['active'] = None
        for field in ('sourceSha256', 'buildSha256', 'runtimeId', 'runtimeVersion'):
            raw['provenance']['observed'][field] = None
        report = bundle.preview(raw, now=NOW)['bundle']
        self.assertEqual(report['source'], 'native-theme-load-observation')
        self.assertFalse(report['currentSetupVerified'])
        self.assertIsNone(report['provenance']['observed']['sourceSha256'])
        self.assertEqual(report['hypotheses'][0]['status'], 'unconfirmed')
        raw['stage'] = 'gameplay'
        with self.assertRaises(bundle.BundleError):
            bundle.preview(raw, now=NOW)

    def theme_context(self):
        raw = synthetic_capture()
        raw.update(origin='native-theme-load', editionId='nova:launcher', stage='preflight',
                   activeRecipeId=None, facts=[{'code': 'selected-theme-load-failed', 'method': 'test'}],
                   hypotheses=[{'code': 'unknown-cause', 'basedOn': ['selected-theme-load-failed']}])
        raw['provenance']['observed']['editionId'] = raw['editionId']
        raw['provenance']['active'] = None
        for field in ('sourceSha256', 'buildSha256', 'runtimeId', 'runtimeVersion'):
            raw['provenance']['observed'][field] = None
        raw['localEvidence'] = {
            'configuration': {'framework': 'Qt', 'frameworkVersion': '5.15.10',
                              'selectionKind': 'local-file', 'loaderStatus': 'error', 'failureStage': 'theme-load'},
            'errorLog': {'status': 'collected', 'maxEntries': 8, 'truncated': False,
                         'entries': [{'code': 'qml-type-unavailable', 'line': 3, 'column': 7}]},
            'lastCloudPreflight': {'status': 'unavailable'}}
        return raw

    def test_app_data_capacity_keeps_zero_distinct_and_exports_exactly(self):
        for available in (0, 123, 2**53 - 1):
            raw = self.theme_context()
            storage = {'status': 'measured', 'scope': 'app-data-volume', 'method': 'fstatvfs',
                       'totalBytes': 2**53 - 1, 'availableBytes': available, 'observedAt': raw['observedAt']}
            raw['localEvidence']['appDataStorage'] = storage
            report = self.preview(raw)
            self.assertEqual(report['bundle']['localEvidence']['appDataStorage'], storage)
            self.assertEqual(report['bundle']['limits'], bundle.APP_DATA_EVIDENCE_LIMITS)
            self.assertFalse(report['bundle']['currentSetupVerified'])
            self.assertEqual(report['bundle']['hypotheses'][0]['code'], 'unknown-cause')
            if available == 0:
                bundle.export(raw, self.output, approve_sha256=report['sha256'], now=NOW)
                self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), report['sha256'])
                self.assertEqual(json.loads(self.output.read_text())['localEvidence']['appDataStorage']['availableBytes'], 0)
        raw['localEvidence']['appDataStorage'] = {'status': 'unavailable'}
        self.assertEqual(self.preview(raw)['bundle']['localEvidence']['appDataStorage'], {'status': 'unavailable'})

    def test_app_data_capacity_refuses_unbounded_private_or_misbound_fields(self):
        good = {'status': 'measured', 'scope': 'app-data-volume', 'method': 'fstatvfs',
                'totalBytes': 1024, 'availableBytes': 0, 'observedAt': '2026-11-04T12:00:00Z'}
        mutations = [('totalBytes', 0), ('totalBytes', 2**53), ('totalBytes', True),
                     ('totalBytes', 1024.0), ('availableBytes', -1), ('availableBytes', 1025),
                     ('availableBytes', False), ('availableBytes', '0'), ('scope', 'sd-card'),
                     ('method', 'du'), ('observedAt', '2026-11-04T12:00:01Z'),
                     ('status', 'unknown'), ('path', '/private/capacity_fixture_only'), ('token', 'capacity_fixture_only')]
        for key, value in mutations:
            raw = self.theme_context()
            raw['localEvidence']['appDataStorage'] = dict(good, **{key: value})
            with self.subTest(key=key, value=value), self.assertRaises(bundle.BundleError) as caught:
                self.preview(raw)
            self.assertNotIn('capacity_fixture_only', str(caught.exception))
        for storage in (None, [], {}, {'status': 'unavailable', 'availableBytes': 0}):
            raw = self.theme_context()
            raw['localEvidence']['appDataStorage'] = storage
            with self.subTest(storage=storage), self.assertRaises(bundle.BundleError):
                self.preview(raw)

    def test_typed_local_evidence_is_bounded_previewed_and_exported_exactly(self):
        raw = self.theme_context()
        report = self.preview(raw)
        self.assertEqual(report['bundle']['localEvidence'], raw['localEvidence'])
        self.assertEqual(report['bundle']['limits'], bundle.LOCAL_EVIDENCE_LIMITS)
        self.assertLessEqual(report['bytes'], 8192)
        self.assertFalse(self.output.exists())
        self.assertFalse(report['bundle']['currentSetupVerified'])
        bundle.export(raw, self.output, approve_sha256=report['sha256'], now=NOW)
        self.assertEqual(json.loads(self.output.read_text()), report['bundle'])
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), report['sha256'])
        raw['localEvidence']['errorLog'].update(status='unavailable', entries=[])
        self.assertEqual(self.preview(raw)['bundle']['localEvidence']['errorLog']['status'], 'unavailable')
        raw['localEvidence']['errorLog'].update(status='collected', truncated=True,
            entries=[{'code': 'qml-syntax-error', 'line': i, 'column': 0} for i in range(8)])
        self.assertLessEqual(self.preview(raw)['bytes'], 8192)
        raw['localEvidence']['lastCloudPreflight'] = {'status': 'observed-refusal',
            'code': 'runtime-request-refused', 'editionSha256': 'a' * 64, 'observedAt': '2026-11-04T11:00:00Z'}
        self.assertEqual(self.preview(raw)['bundle']['localEvidence']['lastCloudPreflight']['code'], 'runtime-request-refused')

    def test_typed_local_evidence_rejects_private_text_extra_fields_and_false_results(self):
        mutations = [
            lambda e: e.update(path='/private/fixture/secret'),
            lambda e: e['configuration'].update(token='secret_fixture'),
            lambda e: e['configuration'].update(frameworkVersion='secret_fixture'),
            lambda e: e['configuration'].update(selectionKind='file:///private/secret'),
            lambda e: e['configuration'].update(failureStage='gameplay'),
            lambda e: e['errorLog'].update(maxEntries=9),
            lambda e: e['errorLog'].update(status='unavailable'),
            lambda e: e['errorLog'].update(entries=e['errorLog']['entries'] * 2),
            lambda e: e['errorLog'].update(entries=[{'code': 'qml-syntax-error', 'line': i, 'column': 0} for i in range(9)]),
            lambda e: e['errorLog']['entries'][0].update(description='password=secret_fixture'),
            lambda e: e['errorLog']['entries'][0].update(code='secret_fixture'),
            lambda e: e['errorLog']['entries'][0].update(line=True),
            lambda e: e['errorLog']['entries'][0].update(line=-1),
            lambda e: e['errorLog']['entries'][0].update(column=10001),
            lambda e: e['lastCloudPreflight'].update(succeeded=True),
            lambda e: e.update(lastCloudPreflight={'status': 'observed-refusal', 'code': 'game-booted',
                'editionSha256': 'a' * 64, 'observedAt': '2026-11-04T11:00:00Z'}),
            lambda e: e.update(lastCloudPreflight={'status': 'observed-refusal', 'code': 'runtime-request-refused',
                'editionSha256': 'a' * 64, 'observedAt': '2026-11-04T13:00:00Z'}),
        ]
        for mutate in mutations:
            raw = self.theme_context()
            mutate(raw['localEvidence'])
            with self.subTest(raw=raw['localEvidence']), self.assertRaises(bundle.BundleError) as caught:
                self.preview(raw)
            self.assertNotIn('secret_fixture', str(caught.exception))
            self.assertFalse(self.output.exists())

    def test_typed_local_evidence_requires_matching_native_theme_stage(self):
        for origin in ('operator', 'native-save-copies', 'native-cloud-play'):
            raw = self.theme_context()
            raw['origin'] = origin
            with self.assertRaises(bundle.BundleError):
                self.preview(raw)
        raw = self.theme_context()
        raw['facts'][0]['code'] = 'selected-theme-construction-failed'
        raw['hypotheses'][0]['basedOn'] = ['selected-theme-construction-failed']
        with self.assertRaises(bundle.BundleError):
            self.preview(raw)
        raw['localEvidence']['configuration']['failureStage'] = 'interface-creation'
        self.assertEqual(self.preview(raw)['bundle']['localEvidence']['configuration']['failureStage'], 'interface-creation')

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
        self.assertNotIn('provenance', report['bundle'])
        self.assertEqual(report['bundle']['schemaVersion'], 1)
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

    def test_offline_stage_retains_only_a_failure_observation_without_certifying_readiness(self):
        self.raw.update(stage='offline-launch', facts=[{'code': 'operation-failed', 'method': 'log'}], hypotheses=[])
        out = self.preview()['bundle']
        self.assertEqual(out['stage'], 'offline-launch')
        self.assertEqual(out['facts'][0]['method'], 'log')
        self.assertFalse(out['currentSetupVerified'])
        self.assertEqual(out['hypotheses'], [])
        self.raw['facts'] = [{'code': 'checksum-mismatch', 'method': 'log'}]
        with self.assertRaises(bundle.BundleError): self.preview()

    def test_synthetic_capture_retains_exact_declared_binding_without_authenticating_it(self):
        raw = synthetic_capture()
        raw['provenance']['observed']['runtimeVersion'] = '1.2.3+fixture'
        raw['provenance']['active']['runtimeVersion'] = '1.2.3+fixture'
        with mock.patch('socket.socket', side_effect=AssertionError('network attempted')), \
             mock.patch('subprocess.Popen', side_effect=AssertionError('process attempted')):
            report = self.preview(raw)
        out = report['bundle']
        provenance = out['provenance']
        self.assertEqual(out['schemaVersion'], 2)
        self.assertEqual(provenance['contextScope'], 'same-declared-context')
        self.assertEqual(provenance['observed']['sourceSha256'], 'a' * 64)
        self.assertEqual(provenance['observed']['buildSha256'], 'b' * 64)
        self.assertEqual(provenance['observed'], provenance['active'])
        self.assertEqual(provenance['collection'], raw['provenance']['collection'])
        self.assertFalse(provenance['authenticated'])
        self.assertFalse(out['currentSetupVerified'])
        for value in ['demo.runtime', '1.2.3+fixture', raw['editionId'], raw['observedRecipeId']]:
            self.assertNotIn(value, json.dumps(out))
        self.assertEqual(bundle.findings('synthetic-report', json.dumps(out)), [])
        bundle.export(raw, self.output, approve_sha256=report['sha256'], now=NOW)
        self.assertEqual(hashlib.sha256(self.output.read_bytes()).hexdigest(), report['sha256'])
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)

    def test_schema2_accepts_exact_cloud_edition_ids_without_relaxing_schema1(self):
        raw = synthetic_capture()
        edition = 'nova:cloud_' + 'a' * 64 + ':41_' + 'b' * 64
        raw['editionId'] = edition
        for side in ['observed', 'active']:
            raw['provenance'][side]['editionId'] = edition
        out = self.preview(raw)['bundle']
        self.assertEqual(out['editionSha256'], hashlib.sha256(edition.encode()).hexdigest())
        self.assertEqual(out['provenance']['contextScope'], 'same-declared-context')
        old = fixture(); old['editionId'] = edition
        with self.assertRaises(bundle.BundleError): self.preview(old)
        raw['editionId'] = 'x' * 513
        with self.assertRaises(bundle.BundleError): self.preview(raw)

    def test_schema2_rejects_placeholder_runtime_identity_or_version(self):
        for field in ['runtimeId', 'runtimeVersion']:
            for value in ['unknown', 'Unverified', 'unspecified', 'pending', 'none', 'null', 'latest', 'current']:
                raw = synthetic_capture()
                for side in ['observed', 'active']:
                    raw['provenance'][side][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(bundle.BundleError):
                    self.preview(raw)

    def test_same_recipe_cannot_hide_source_build_runtime_or_edition_drift(self):
        for field, value in [('editionId', 'demo:edition-b'), ('sourceSha256', 'c' * 64),
                             ('buildSha256', 'd' * 64), ('runtimeId', 'other.runtime'),
                             ('runtimeVersion', '2.0.0')]:
            raw = synthetic_capture()
            raw['provenance']['active'][field] = value
            out = self.preview(raw)['bundle']
            with self.subTest(field=field):
                self.assertEqual(out['recipeScope'], 'same-declared-recipe')
                self.assertEqual(out['provenance']['contextScope'], 'historical-context')
                self.assertIn('does not establish the current context', out['recoveryHints'][0])
                self.assertFalse(out['currentSetupVerified'])
                self.assertEqual(out['facts'][0]['method'], 'test')
                self.assertEqual(out['hypotheses'][0]['status'], 'unconfirmed')

    def test_missing_context_stays_unknown_and_known_mismatch_survives_unknown_fields(self):
        for side in ['observed', 'active']:
            for field in ['sourceSha256', 'buildSha256', 'runtimeId', 'runtimeVersion']:
                raw = synthetic_capture()
                raw['provenance'][side][field] = None
                self.assertEqual(self.preview(raw)['bundle']['provenance']['contextScope'], 'unknown-context')
        raw['provenance']['active']['sourceSha256'] = 'f' * 64
        self.assertEqual(self.preview(raw)['bundle']['provenance']['contextScope'], 'historical-context')
        raw = synthetic_capture()
        raw['activeRecipeId'] = None
        raw['provenance']['active'] = None
        self.assertEqual(self.preview(raw)['bundle']['provenance']['contextScope'], 'unlinked')

    def test_collection_refusal_and_unsupported_statuses_never_become_success_or_causes(self):
        for status in bundle.COLLECTION_STATUSES:
            raw = synthetic_capture(status)
            raw.update(stage='offline-launch', facts=[{'code': 'operation-failed', 'method': 'log'}], hypotheses=[])
            out = self.preview(raw)['bundle']
            with self.subTest(status=status):
                self.assertEqual(out['provenance']['collection']['status'], status)
                self.assertEqual(out['facts'][0]['method'], 'log')
                self.assertEqual(out['hypotheses'], [])
                self.assertFalse(out['currentSetupVerified'])
                if status != 'collected':
                    self.assertIn('did not collect evidence', out['recoveryHints'][0])

    def test_provenance_mismatch_malformed_private_unknown_and_date_fields_are_refused(self):
        variants = []
        for side in ['observed', 'active']:
            for field, value in [('recipeId', 'wrong.v2'), ('runtimeId', '/private/runtime'),
                                 ('runtimeVersion', 'owner@' + 'private.example'), ('buildSha256', 'g' * 64),
                                 ('sourceSha256', True), ('extra', 'secret')]:
                raw = synthetic_capture(); raw['provenance'][side][field] = value; variants.append(raw)
        raw = synthetic_capture(); raw['provenance']['observed']['editionId'] = 'other:edition'; variants.append(raw)
        raw = synthetic_capture(); raw['provenance']['active'] = None; variants.append(raw)
        raw = synthetic_capture(); raw['activeRecipeId'] = None; variants.append(raw)
        raw = synthetic_capture(); del raw['provenance']['observed']['buildSha256']; variants.append(raw)
        for field, value in [('status', 'passed'), ('status', []), ('method', 'physical'),
                             ('collectedAt', '2026-11-04T11:59:59Z'),
                             ('collectedAt', '2026-11-06T00:00:00Z'), ('extra', 'private')]:
            raw = synthetic_capture(); raw['provenance']['collection'][field] = value; variants.append(raw)
        for value in [None, [], {}, {'observed': {}, 'active': {}, 'collection': {}}]:
            raw = synthetic_capture(); raw['provenance'] = value; variants.append(raw)
        raw = synthetic_capture(); raw['schemaVersion'] = 1; variants.append(raw)
        for raw in variants:
            with self.assertRaises(bundle.BundleError): self.preview(raw)

    def test_changed_context_or_collection_invalidates_exact_preview_approval(self):
        for part, field, value in [('active', 'buildSha256', 'e' * 64),
                                   ('collection', 'status', 'refused'),
                                   ('collection', 'collectedAt', '2026-11-04T12:02:00Z')]:
            raw = synthetic_capture()
            digest = self.preview(raw)['sha256']
            raw['provenance'][part][field] = value
            with self.assertRaises(bundle.BundleError):
                bundle.export(raw, self.output, approve_sha256=digest, now=NOW)
            self.assertFalse(self.output.exists())

    def test_schema_two_cli_roundtrip_and_private_provenance_refusal(self):
        descriptor = self.root / 'capture.json'
        raw = synthetic_capture('refused')
        descriptor.write_text(json.dumps(raw))
        result = subprocess.run([sys.executable, str(SCRIPT), 'preview', str(descriptor)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['bundle']['provenance']['collection']['status'], 'refused')
        self.assertFalse(self.output.exists())
        result = subprocess.run([sys.executable, str(SCRIPT), 'export', str(descriptor), str(self.output),
                                 '--approve-sha256', report['sha256']], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.output.read_bytes()), report['bundle'])
        raw['provenance']['active']['runtimeId'] = '/private/synthetic-runtime'
        descriptor.write_text(json.dumps(raw))
        result = subprocess.run([sys.executable, str(SCRIPT), 'preview', str(descriptor)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, '')
        self.assertNotIn('/private/synthetic-runtime', result.stderr)
        self.assertNotIn(str(descriptor), result.stderr)

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
