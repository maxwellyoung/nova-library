"""Synthetic in-memory service/runtime adapters; never contact an account or device."""
import copy
import hashlib
import io
import json
import tarfile
import tempfile
from pathlib import Path
import unittest

from tools import save_passport as passport
from tools.save_sync_model import SyncModel, SyncError, digest

IDENTITY = {'editionId': 'fixture:edition', 'recipeId': 'fixture.v1', 'kind': 'native-save',
            'runtime': {'name': 'Fixture runtime', 'version': '1.0', 'core': 'Fixture core'}}


def archive(payload=b'initial', date='2026-11-05T00:00:00Z', identity=None):
    identity = identity or IDENTITY
    manifest = {**copy.deepcopy(identity), 'schemaVersion': 1, 'createdAt': date,
                'sourceState': 'operator-confirmed-idle', 'files': [
                    {'path': 'memory.srm', 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}]}
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w', format=tarfile.USTAR_FORMAT) as stream:
        stream.addfile(passport.header('payload/0000', len(payload)), io.BytesIO(payload))
        raw = json.dumps(manifest).encode()
        stream.addfile(passport.header('manifest.json', len(raw)), io.BytesIO(raw))
    return output.getvalue()


def ref(data, number=1, identity=None):
    return {'checkpointId': f'{number:032x}', 'passportSha256': hashlib.sha256(data).hexdigest(),
            'identity': copy.deepcopy(identity or IDENTITY)}


def local(model, data, number=1, parents=()):
    return model.add_local(ref(data, number, model.identity), data, parents)


class FakeService:
    """Immutable blobs, durable operation IDs and atomic complete-head guard.

    Real WebDAV does not supply this API. This is deliberately only a contract
    fixture: its guard serializes publish versus startup through content load.
    """
    def __init__(self):
        self.revisions = {}
        self.operations = {}
        self.generation = 0
        self.guard = None
        self.online = True
        self.put_calls = 0

    @property
    def token(self):
        metas = [item[0] for item in self.revisions.values()]
        parents = {p for meta in metas for p in meta['parentIds']}
        heads = sorted(meta['revisionId'] for meta in metas if meta['revisionId'] not in parents)
        return digest({'revisionIds': sorted(self.revisions), 'heads': heads})

    def put(self, intent, lose_response=False):
        if not self.online:
            raise ConnectionError('fixture offline')
        if self.guard:
            raise RuntimeError('head guard prevents publication before content load')
        op, meta, data = intent['operationId'], intent['revision'], intent['archive']
        if hashlib.sha256(data).hexdigest() != meta['passportSha256'] or len(data) != meta['bytes']:
            raise ValueError('fixture checksum failed')
        if not all(parent in self.revisions for parent in meta['parentIds']):
            raise ValueError('parent revisions must be published first')
        binding = (meta, data)
        if op in self.operations and self.operations[op] != binding:
            raise ValueError('idempotency key reused with another revision')
        if meta['revisionId'] in self.revisions and self.revisions[meta['revisionId']] != binding:
            raise ValueError('immutable revision changed')
        self.put_calls += 1
        self.operations[op] = copy.deepcopy(binding)
        if meta['revisionId'] not in self.revisions:
            self.revisions[meta['revisionId']] = copy.deepcopy(binding)
            self.generation += 1
        if lose_response:
            raise TimeoutError('fixture lost response after durable acceptance')
        return (op, meta['revisionId'], meta['passportSha256'])

    def inventory(self, model, session=None):
        if not self.online:
            raise ConnectionError('fixture offline')
        metas = [copy.deepcopy(item[0]) for item in self.revisions.values()]
        parents = {p for m in metas for p in m['parentIds']}
        heads = sorted(m['revisionId'] for m in metas if m['revisionId'] not in parents)
        model.observe_inventory(metas, heads, self.token, session_id=session)

    def fetch(self, revision_id, offset, count=1024):
        if not self.online:
            raise ConnectionError('fixture offline')
        return self.revisions[revision_id][1][offset:offset + count]

    def acquire_guard(self, model, session):
        if not self.online or model.startup['inventoryToken'] != self.token or self.guard is not None:
            raise RuntimeError('fresh guarded heads unavailable')
        self.guard = {'guardId': f'guard:{session}', 'sessionId': session,
                      'identity': copy.deepcopy(model.identity), 'inventoryToken': self.token}
        return copy.deepcopy(self.guard)


class FakeRuntime:
    """In-memory import/readback ordering oracle, not an emulator integration."""
    def __init__(self, model, current):
        self.identity = copy.deepcopy(model.identity)
        self.data_sha = model.records[current]['revision']['saveDataSha256']
        self.active = False
        self.boundary = 'idle:fixture'
        self.events = []

    def idle(self, model, session):
        if self.active:
            raise RuntimeError('fixture content still active')
        self.events.append('contentless-readback')
        model.observe_idle({'sessionId': session, 'boundaryId': self.boundary,
                            'identity': self.identity, 'state': 'contentless', 'saveDataSha256': self.data_sha})

    def stage(self, model):
        selected = model._selection()
        record = model.records[selected]
        self.events.append('stage-new-directory')
        model.record_staged({'sessionId': model.startup['sessionId'], 'revisionId': selected,
                             'checkpointId': record['checkpoint']['checkpointId'],
                             'passportSha256': record['revision']['passportSha256']})

    def apply(self, model):
        if self.active:
            raise RuntimeError('fixture cannot import while content active')
        selected = model._selection()
        self.events.append('runtime-import-and-readback')
        model.record_applied({'sessionId': model.startup['sessionId'], 'boundaryId': self.boundary,
                              'revisionId': selected, 'saveDataSha256': model.records[selected]['revision']['saveDataSha256']})
        self.data_sha = model.records[selected]['revision']['saveDataSha256']

    def load(self, intent, service=None):
        if self.active or intent['saveDataSha256'] != self.data_sha:
            raise RuntimeError('fixture startup ordering failed')
        if not intent['explicitLocalChoice']:
            if not service or not service.guard or service.guard['guardId'] != intent['remoteGuardId']:
                raise RuntimeError('fixture head guard expired')
            service.guard = None
        self.events.append('load-content')
        self.active = True


def upload(model, service, revision_id, lose_response=False):
    op = model.queue_upload(revision_id)
    result = service.put(model.upload_intent(op), lose_response=lose_response)
    model.acknowledge_upload(*result)
    return op


def download(model, service, revision_id, transfer='fetch:1'):
    offset = model.begin_download(revision_id, transfer)
    while offset < model.records[revision_id]['revision']['bytes']:
        chunk = service.fetch(revision_id, offset)
        model.append_download(revision_id, transfer, offset, chunk)
        offset += len(chunk)
    model.verify_download(revision_id)
    data = model.records[revision_id]['buffer']
    model.attach_checkpoint(revision_id, ref(data, 100, model.identity))


class SaveSyncModelTests(unittest.TestCase):
    def setUp(self):
        self.base = archive()
        self.client = SyncModel(IDENTITY)
        self.base_id = local(self.client, self.base)
        self.service = FakeService()
        upload(self.client, self.service, self.base_id)

    def remote_child(self, data=None):
        other = SyncModel.restart(self.client.snapshot())
        data = data or archive(b'remote progress')
        child = local(other, data, 2, [self.base_id])
        upload(other, self.service, child)
        return child, data

    def test_two_offline_branches_and_extreme_clock_skew_are_both_retained(self):
        a = SyncModel.restart(self.client.snapshot())
        b = SyncModel.restart(self.client.snapshot())
        first = local(a, archive(b'offline A', '2099-01-01T00:00:00Z'), 2, [self.base_id])
        second = local(b, archive(b'offline B', '2000-01-01T00:00:00Z'), 3, [self.base_id])
        self.service.online = False
        for model, branch in ((a, first), (b, second)):
            model.queue_upload(branch)
            with self.assertRaises(ConnectionError):
                self.service.put(model.upload_intent('put:' + branch))
        self.service.online = True
        upload(a, self.service, first); upload(b, self.service, second)
        self.service.inventory(a)
        self.assertEqual(set(a.remote['heads']), {first, second})
        a.begin_startup('startup:a', first); self.service.inventory(a, 'startup:a')
        self.assertEqual(a.barrier(), 'needs-branch-choice')
        self.assertEqual(len(self.service.revisions), 3)
        self.assertTrue(a.is_ancestor(self.base_id, first))
        self.assertFalse(a.is_ancestor(first, second))
        a.choose_branch(first, prefer_local=True)
        runtime = FakeRuntime(a, first); runtime.idle(a, 'startup:a')
        runtime.load(a.issue_load_intent())
        self.assertEqual(set(a.remote['heads']), {first, second})

    def test_lost_upload_response_retries_same_durable_id_without_duplicate_revision(self):
        child = local(self.client, archive(b'new local'), 2, [self.base_id])
        op = self.client.queue_upload(child)
        with self.assertRaises(TimeoutError):
            self.service.put(self.client.upload_intent(op), lose_response=True)
        self.assertEqual(self.client.statuses(child), ['local', 'queued', 'verified'])
        restarted = SyncModel.restart(json.loads(json.dumps(self.client.snapshot())))
        result = self.service.put(restarted.upload_intent(op))
        self.assertTrue(restarted.acknowledge_upload(*result))
        self.assertTrue(restarted.acknowledge_upload(*result))
        self.assertEqual(len(self.service.revisions), 2)
        self.assertEqual(restarted.statuses(child), ['local', 'uploaded', 'verified'])
        with self.assertRaises(SyncError):
            restarted.acknowledge_upload(op, self.base_id, hashlib.sha256(self.base).hexdigest())

    def test_cancel_upload_preserves_local_and_ignores_late_reply(self):
        child = local(self.client, archive(b'cancel upload'), 2, [self.base_id])
        op = self.client.queue_upload(child)
        reply = self.service.put(self.client.upload_intent(op))
        self.client.cancel_upload(op)
        self.assertFalse(self.client.acknowledge_upload(*reply))
        with self.assertRaises(SyncError):
            self.client.upload_intent(op)
        self.assertEqual(self.client.statuses(child), ['local', 'verified'])
        # Immutable remote acceptance already happened; cancellation does not delete it.
        self.assertIn(child, self.service.revisions)
        upload(self.client, self.service, child)
        self.assertEqual(len(self.service.revisions), 2)

    def test_partial_fetch_restart_resumes_prefix_and_rejects_old_callback(self):
        child, data = self.remote_child()
        self.service.inventory(self.client)
        self.client.begin_download(child, 'fetch:old')
        chunk = self.service.fetch(child, 0, 777)
        self.client.append_download(child, 'fetch:old', 0, chunk)
        restarted = SyncModel.restart(self.client.snapshot())
        with self.assertRaises(SyncError):
            restarted.append_download(child, 'fetch:old', 777, b'late')
        self.assertEqual(restarted.begin_download(child, 'fetch:new'), 777)
        with self.assertRaises(SyncError):
            restarted.append_download(child, 'fetch:new', 0, chunk)
        restarted.append_download(child, 'fetch:new', 777, data[777:])
        self.assertEqual(restarted.statuses(child), ['downloaded'])
        restarted.verify_download(child)
        self.assertEqual(restarted.statuses(child), ['downloaded', 'verified'])
        self.assertIsNone(restarted.records[child]['checkpoint'])

    def test_cancel_download_fences_stale_chunks_and_does_not_touch_current(self):
        child, _ = self.remote_child(); self.service.inventory(self.client)
        self.client.begin_download(child, 'fetch:cancel')
        self.client.append_download(child, 'fetch:cancel', 0, b'prefix')
        self.client.cancel_download(child)
        with self.assertRaises(SyncError):
            self.client.append_download(child, 'fetch:cancel', 0, b'late')
        self.assertEqual(self.client.records[child]['buffer'], b'')
        self.assertEqual(self.client.records[self.base_id]['buffer'], self.base)
        download(self.client, self.service, child, 'fetch:retry')
        self.assertTrue(self.client.records[child]['verified'])

    def test_wrong_checksum_never_becomes_verified_or_launchable(self):
        child, data = self.remote_child(); self.service.inventory(self.client)
        self.client.begin_download(child, 'fetch:bad')
        wrong = b'X' + data[1:]
        self.client.append_download(child, 'fetch:bad', 0, wrong)
        self.assertEqual(self.client.statuses(child), ['downloaded'])
        with self.assertRaises(SyncError): self.client.verify_download(child)
        with self.assertRaises(SyncError): self.client.attach_checkpoint(child, ref(data))
        self.assertEqual(self.client.records[child]['error'], 'verification-failed')
        self.assertEqual(self.client.records[self.base_id]['buffer'], self.base)
        restarted = SyncModel.restart(self.client.snapshot())
        self.assertFalse(restarted.records[child]['verified'])
        with self.assertRaises(SyncError): restarted.begin_download(child, 'fetch:retry')
        restarted.cancel_download(child)
        download(restarted, self.service, child, 'fetch:retry')

    def test_newer_remote_branch_blocks_until_download_import_readback_and_guard(self):
        child, _ = self.remote_child()
        self.client.begin_startup('startup:remote', self.base_id)
        runtime = FakeRuntime(self.client, self.base_id)
        self.assertEqual(self.client.barrier(), 'needs-inventory-or-local-choice')
        self.service.inventory(self.client, 'startup:remote')
        self.assertEqual(self.client.barrier(), 'needs-download')
        with self.assertRaises(SyncError): self.client.issue_load_intent()
        download(self.client, self.service, child)
        self.assertEqual(self.client.barrier(), 'needs-runtime-idle-readback')
        runtime.idle(self.client, 'startup:remote')
        self.assertEqual(self.client.barrier(), 'needs-runtime-apply')
        runtime.stage(self.client)
        self.assertEqual(self.client.barrier(), 'needs-runtime-apply')
        with self.assertRaises(SyncError): self.client.issue_load_intent()
        runtime.apply(self.client)
        self.assertEqual(self.client.barrier(), 'needs-remote-head-guard')
        with self.assertRaises(SyncError): self.client.issue_load_intent()
        guard = self.service.acquire_guard(self.client, 'startup:remote')
        intent = self.client.issue_load_intent(guard)
        runtime.load(intent, self.service)
        self.assertEqual(runtime.events, ['contentless-readback', 'stage-new-directory', 'runtime-import-and-readback', 'load-content'])
        self.assertEqual(intent['revisionId'], child)
        with self.assertRaises(SyncError): self.client.issue_load_intent(guard)
        self.assertEqual(len(self.client.records), 2)

    def test_explicit_offline_local_choice_preserves_unfetched_newer_remote_branch(self):
        child, _ = self.remote_child()
        self.client.begin_startup('startup:offline', self.base_id)
        runtime = FakeRuntime(self.client, self.base_id)
        self.service.online = False
        with self.assertRaises(ConnectionError): self.service.inventory(self.client, 'startup:offline')
        with self.assertRaises(SyncError): self.client.issue_load_intent()
        self.client.choose_branch(self.base_id, prefer_local=True)
        runtime.idle(self.client, 'startup:offline')
        intent = self.client.issue_load_intent()
        self.assertTrue(intent['explicitLocalChoice'])
        self.assertIsNone(intent['remoteGuardId'])
        runtime.load(intent)
        self.assertIn(child, self.service.revisions)

    def test_startup_restart_requires_new_runtime_inventory_and_session_receipts(self):
        self.client.begin_startup('startup:old', self.base_id)
        self.service.inventory(self.client, 'startup:old')
        FakeRuntime(self.client, self.base_id).idle(self.client, 'startup:old')
        old_guard = self.service.acquire_guard(self.client, 'startup:old')
        restarted = SyncModel.restart(self.client.snapshot())
        with self.assertRaises(SyncError): restarted.barrier()
        with self.assertRaises(SyncError): restarted.begin_startup('startup:old', self.base_id)
        restarted.begin_startup('startup:new', self.base_id)
        self.assertEqual(restarted.barrier(), 'needs-inventory-or-local-choice')
        with self.assertRaises(SyncError): self.service.inventory(restarted, 'startup:old')
        self.service.guard = None
        self.service.inventory(restarted, 'startup:new')
        FakeRuntime(restarted, self.base_id).idle(restarted, 'startup:new')
        with self.assertRaises(SyncError): restarted.issue_load_intent(old_guard)
        restarted.invalidate_runtime()
        with self.assertRaises(SyncError): restarted.issue_load_intent(old_guard)

    def test_remote_publish_between_inventory_and_startup_requires_refresh(self):
        self.client.begin_startup('startup:race', self.base_id)
        self.service.inventory(self.client, 'startup:race')
        FakeRuntime(self.client, self.base_id).idle(self.client, 'startup:race')
        child, _ = self.remote_child()
        with self.assertRaises(RuntimeError): self.service.acquire_guard(self.client, 'startup:race')
        self.service.inventory(self.client, 'startup:race')
        self.assertEqual(self.client.barrier(), 'needs-download')
        self.assertEqual(self.client._selection(), child)

    def test_head_guard_covers_content_load_and_expired_guard_cannot_load(self):
        self.client.begin_startup('startup:guard', self.base_id)
        self.service.inventory(self.client, 'startup:guard')
        runtime = FakeRuntime(self.client, self.base_id); runtime.idle(self.client, 'startup:guard')
        writer = SyncModel.restart(self.client.snapshot())
        child = local(writer, archive(b'concurrent progress'), 5, [self.base_id])
        operation = writer.queue_upload(child)
        guard = self.service.acquire_guard(self.client, 'startup:guard')
        with self.assertRaises(RuntimeError): self.service.put(writer.upload_intent(operation))
        intent = self.client.issue_load_intent(guard)
        self.service.guard = None
        with self.assertRaises(RuntimeError): runtime.load(intent, self.service)
        self.assertFalse(runtime.active)

    def test_wrong_runtime_kind_catalogue_reference_and_apply_receipts_are_refused(self):
        state_identity = {**copy.deepcopy(IDENTITY), 'kind': 'emulator-state'}
        state_archive = archive(b'state', identity=state_identity)
        with self.assertRaises(SyncError): self.client.add_local(ref(state_archive), state_archive)
        wrong = ref(self.base); wrong['identity']['runtime']['core'] = 'Another core'
        with self.assertRaises(SyncError): self.client.add_local(wrong, self.base)
        wrong = ref(self.base); wrong['passportSha256'] = '0' * 64
        with self.assertRaises(SyncError): self.client.add_local(wrong, self.base)
        self.client.begin_startup('startup:wrong', self.base_id)
        receipt = {'sessionId': 'startup:wrong', 'boundaryId': 'idle:fixture', 'identity': copy.deepcopy(IDENTITY),
                   'state': 'contentless', 'saveDataSha256': '0' * 64}
        with self.assertRaises(SyncError): self.client.observe_idle(receipt)
        with self.assertRaises(SyncError): self.client.record_applied({})
        self.client.choose_branch(self.base_id, prefer_local=True)
        receipt['saveDataSha256'] = self.client.records[self.base_id]['revision']['saveDataSha256']
        receipt['state'] = 'paused'
        with self.assertRaises(SyncError): self.client.observe_idle(receipt)
        self.assertFalse(self.client.startup['idle'])

    def test_imported_remote_revision_is_exact_and_inventory_failures_are_atomic(self):
        before = self.client.snapshot()
        meta = copy.deepcopy(self.service.revisions[self.base_id][0])
        meta['bytes'] += 1
        with self.assertRaises(SyncError): self.client.observe_inventory([meta], [self.base_id], 'inventory:bad')
        with self.assertRaises(SyncError): self.client.observe_inventory([], [self.base_id], 'inventory:bad')
        with self.assertRaises(SyncError): self.client.observe_inventory([self.service.revisions[self.base_id][0]] * 2, [self.base_id], 'inventory:bad')
        self.assertEqual(self.client.snapshot(), before)
        child, _ = self.remote_child()
        meta = self.service.revisions[child][0]
        with self.assertRaises(SyncError): self.client.observe_inventory([meta], [child], 'inventory:incomplete')
        self.assertEqual(self.client.snapshot(), before)

    def test_real_catalogue_import_export_download_and_stage_keep_exact_reference_contract(self):
        from tools.save_catalogue import Catalogue
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            left = Catalogue(root / 'left', create=True)
            right = Catalogue(root / 'right', create=True)
            source = root / 'synthetic.nvs'; source.write_bytes(self.base)
            source_ref = left.import_passport(source, name='Synthetic anchor', pinned=True)
            sender = SyncModel(IDENTITY)
            initial = sender.add_local(source_ref, self.base)
            service = FakeService(); upload(sender, service, initial)
            receiver = SyncModel(IDENTITY); service.inventory(receiver)
            receiver.begin_download(initial, 'fetch:catalogue')
            receiver.append_download(initial, 'fetch:catalogue', 0, self.base)
            receiver.verify_download(initial)
            incoming = root / 'incoming.nvs'; incoming.write_bytes(receiver.records[initial]['buffer'])
            target_ref = right.import_passport(incoming, name='Received branch')
            receiver.attach_checkpoint(initial, target_ref)
            self.assertNotEqual(source_ref['checkpointId'], target_ref['checkpointId'])
            self.assertEqual(source_ref['passportSha256'], target_ref['passportSha256'])
            exported = root / 'exact-export.nvs'
            right.export_passport(target_ref['checkpointId'], exported)
            self.assertEqual(exported.read_bytes(), self.base)
            staged = root / 'new-stage'
            right.stage(target_ref['checkpointId'], IDENTITY, staged)
            self.assertEqual((staged / 'memory.srm').read_bytes(), b'initial')
            # A catalogue stage is not a runtime apply receipt or startup intent.
            self.assertIsNone(receiver.startup)
            with self.assertRaises(SyncError): receiver.issue_load_intent()
            self.assertEqual(receiver.records[initial]['checkpoint'], right.reference(target_ref['checkpointId']))

    def test_parents_are_published_before_child_and_archive_state_kind_is_not_native(self):
        parent = local(self.client, archive(b'unsynced parent'), 2, [self.base_id])
        child = local(self.client, archive(b'unsynced child'), 3, [parent])
        operation = self.client.queue_upload(child)
        with self.assertRaises(SyncError): self.client.upload_intent(operation)
        upload(self.client, self.service, parent)
        upload(self.client, self.service, child)
        self.service.inventory(self.client)
        self.assertEqual(self.client.remote['heads'], [child])
        state_identity = {**copy.deepcopy(IDENTITY), 'kind': 'emulator-state'}
        state = SyncModel(state_identity)
        data = archive(b'state', identity=state_identity)
        state_id = local(state, data)
        self.assertEqual(state.statuses(state_id), ['local', 'verified'])
        before = self.client.snapshot()
        with self.assertRaises(SyncError):
            self.client.observe_inventory([state.records[state_id]['revision']], [state_id], '0' * 64)
        self.assertEqual(self.client.snapshot(), before)

    def test_explicit_retained_local_branch_still_needs_real_apply_when_it_is_not_current(self):
        old = self.base_id
        current = local(self.client, archive(b'current progress'), 2, [old])
        self.client.begin_startup('startup:old-local', current)
        self.client.choose_branch(old, prefer_local=True)
        runtime = FakeRuntime(self.client, current); runtime.idle(self.client, 'startup:old-local')
        self.assertEqual(self.client.barrier(), 'needs-runtime-apply')
        with self.assertRaises(SyncError): self.client.issue_load_intent()
        runtime.stage(self.client); runtime.apply(self.client)
        runtime.load(self.client.issue_load_intent())
        self.assertIn(current, self.client.records)
        self.assertIn(old, self.client.records)

    def test_background_last_known_inventory_cannot_replace_startup_bound_heads(self):
        child, _ = self.remote_child()
        self.client.begin_startup('startup:fresh', self.base_id)
        self.service.inventory(self.client, 'startup:fresh')
        self.assertEqual(self.client.barrier(), 'needs-download')
        # An older cache response is valid last-known data, not startup evidence.
        meta = self.service.revisions[self.base_id][0]
        old_token = digest({'revisionIds': [self.base_id], 'heads': [self.base_id]})
        self.client.observe_inventory([meta], [self.base_id], old_token)
        self.assertEqual(self.client.barrier(), 'needs-download')
        self.assertEqual(self.client._selection(), child)
        self.assertNotEqual(self.client.startup['inventoryToken'], self.client.remote['token'])

    def test_matching_outer_hash_does_not_bypass_internal_passport_or_identity_checks(self):
        for raw in (b'not a passport', archive(b'state', identity={**copy.deepcopy(IDENTITY), 'kind': 'emulator-state'})):
            meta = {'identity': copy.deepcopy(IDENTITY), 'passportSha256': hashlib.sha256(raw).hexdigest(),
                    'saveDataSha256': '0' * 64, 'bytes': len(raw), 'parentIds': []}
            meta['revisionId'] = digest(meta)
            remote_token = digest({'revisionIds': [meta['revisionId']], 'heads': [meta['revisionId']]})
            self.client.observe_inventory([meta], [meta['revisionId']], remote_token)
            self.client.begin_download(meta['revisionId'], 'fetch:' + meta['revisionId'])
            self.client.append_download(meta['revisionId'], 'fetch:' + meta['revisionId'], 0, raw)
            with self.assertRaises(SyncError): self.client.verify_download(meta['revisionId'])
            self.assertFalse(self.client.records[meta['revisionId']]['verified'])
            self.assertEqual(self.client.records[self.base_id]['buffer'], self.base)

    def test_snapshot_corruption_future_schema_and_state_claims_are_refused(self):
        for field, value in [('schemaVersion', 2), ('schemaVersion', True)]:
            bad = self.client.snapshot(); bad[field] = value
            with self.assertRaises(SyncError): SyncModel.restart(bad)
        bad = self.client.snapshot(); bad['records'][self.base_id]['buffer'] = 'AAAA'
        with self.assertRaises(SyncError): SyncModel.restart(bad)
        bad = self.client.snapshot(); bad['records'][self.base_id]['verified'] = False
        with self.assertRaises(SyncError): SyncModel.restart(bad)
        bad = self.client.snapshot(); bad['records'][self.base_id]['checkpoint']['passportSha256'] = '0' * 64
        with self.assertRaises(SyncError): SyncModel.restart(bad)
        bad = self.client.snapshot(); bad['operations']['put:' + self.base_id]['state'] = 'queued'
        with self.assertRaises(SyncError): SyncModel.restart(bad)
        self.assertNotIn('startup', self.client.snapshot())

    def test_same_save_bytes_with_different_capture_dates_share_data_digest_not_a_clock_winner(self):
        first = local(self.client, archive(b'same', '2099-01-01T00:00:00Z'), 2, [self.base_id])
        second = local(self.client, archive(b'same', '2000-01-01T00:00:00Z'), 3, [self.base_id])
        self.assertNotEqual(first, second)
        self.assertEqual(self.client.records[first]['revision']['saveDataSha256'], self.client.records[second]['revision']['saveDataSha256'])
        upload(self.client, self.service, first); upload(self.client, self.service, second)
        self.client.begin_startup('startup:same-data', first); self.service.inventory(self.client, 'startup:same-data')
        self.assertEqual(self.client.barrier(), 'needs-branch-choice')


if __name__ == '__main__':
    unittest.main()
