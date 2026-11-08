"""Pure, disabled save-sync transaction model; no network, disk or runtime writes.

An adapter must persist snapshot() before executing an upload intent. All receipts
are adapter preconditions, not evidence that this model contacted a real runtime.
"""
import base64
import copy
import hashlib
import io
import json
import re
import tarfile

if __package__:
    from . import save_passport as passport
else:
    import save_passport as passport

MAX_REVISIONS = 1024
MAX_ARCHIVE = passport.MAX_TOTAL + 2 * 1024 * 1024
HEX = re.compile(r'[0-9a-f]{64}')
TOKEN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')


class SyncError(ValueError):
    """Fixed diagnostics without private identities, paths or save bytes."""


def need(condition, message):
    if not condition:
        raise SyncError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def token(value):
    need(isinstance(value, str) and TOKEN.fullmatch(value), 'Invalid adapter token')
    return value


def sha(value):
    need(isinstance(value, str) and HEX.fullmatch(value), 'Invalid content digest')
    return value


def known_identity(value):
    try:
        result = passport.identity(value)
        passport.compatible(result, result)
        need(value == result, 'Unexpected identity fields')
        return result
    except passport.PassportError:
        raise SyncError('Exact known save identity is required') from None


def inspect_archive(data, identity):
    need(isinstance(data, bytes) and len(data) <= MAX_ARCHIVE, 'Invalid archive bytes')
    try:
        manifest = passport.scan(io.BytesIO(data))
        passport.compatible(manifest, identity)
    except (ValueError, OSError, EOFError, tarfile.TarError):
        raise SyncError('Archive verification or exact compatibility failed') from None
    # Dates describe capture; only exact file paths/hashes/sizes and setup identify data.
    return digest({'identity': identity, 'files': sorted(manifest['files'], key=lambda item: item['path'])})


def reference(value, identity, archive_sha):
    need(isinstance(value, dict) and set(value) == {'checkpointId', 'passportSha256', 'identity'},
         'Invalid catalogue reference')
    need(isinstance(value['checkpointId'], str) and re.fullmatch(r'[0-9a-f]{32}', value['checkpointId']),
         'Invalid checkpoint ID')
    need(known_identity(value['identity']) == identity and value['passportSha256'] == archive_sha,
         'Catalogue reference does not match archive identity')
    return copy.deepcopy(value)


def revision(value, identity):
    need(isinstance(value, dict) and set(value) == {'revisionId', 'identity', 'passportSha256',
         'saveDataSha256', 'bytes', 'parentIds'}, 'Invalid sync revision')
    value = copy.deepcopy(value)
    need(known_identity(value['identity']) == identity, 'Revision setup differs')
    sha(value['passportSha256']); sha(value['saveDataSha256']); sha(value['revisionId'])
    need(type(value['bytes']) is int and 0 < value['bytes'] <= MAX_ARCHIVE, 'Invalid archive size')
    parents = value['parentIds']
    need(isinstance(parents, list) and len(parents) <= 32 and all(isinstance(p, str) for p in parents) and parents == sorted(set(parents)),
         'Invalid parent revision list')
    for item in parents:
        sha(item)
    body = {k: v for k, v in value.items() if k != 'revisionId'}
    need(digest(body) == value['revisionId'], 'Revision metadata digest failed')
    return value


class SyncModel:
    """One exact edition/setup/kind. Immutable branches are never overwritten.

    Downloaded means complete transport bytes. Verified means both the archive
    and passport identity passed. Staging and runtime application are independent
    session receipts. Neither is inferred from transport or catalogue presence.
    """

    def __init__(self, identity):
        self.identity = known_identity(identity)
        self.records = {}
        self.operations = {}
        self.remote = None  # Last-known complete inventory; never startup freshness.
        self.used_sessions = []
        self.used_downloads = []
        self.startup = None

    def _record(self, revision_id):
        need(revision_id in self.records, 'Unknown save revision')
        return self.records[revision_id]

    @staticmethod
    def _empty(meta):
        return {'revision': meta, 'checkpoint': None, 'local': False, 'queued': False,
                'uploaded': False, 'downloaded': False, 'verified': False,
                'buffer': b'', 'error': None, 'downloadId': None}

    def _add(self, meta):
        revision_id = meta['revisionId']
        if revision_id in self.records:
            need(self.records[revision_id]['revision'] == meta, 'Immutable revision differs')
        else:
            need(len(self.records) < MAX_REVISIONS, 'Revision limit reached; retain/export branches')
            self.records[revision_id] = self._empty(meta)
        return self.records[revision_id]

    def add_local(self, checkpoint, data, parent_ids=()):
        """Accept an F07 catalogue reference and its verified immutable archive."""
        need(isinstance(data, bytes), 'Invalid archive bytes')
        archive_sha = hashlib.sha256(data).hexdigest()
        checkpoint = reference(checkpoint, self.identity, archive_sha)
        data_sha = inspect_archive(data, self.identity)
        need(isinstance(parent_ids, (list, tuple)) and len(parent_ids) <= 32 and all(isinstance(p, str) for p in parent_ids),
             'Invalid parent revision list')
        parents = sorted(set(parent_ids))
        for parent in parents:
            self._record(parent)
        meta = {'identity': copy.deepcopy(self.identity), 'passportSha256': archive_sha,
                'saveDataSha256': data_sha, 'bytes': len(data), 'parentIds': parents}
        meta['revisionId'] = digest(meta)
        meta = revision(meta, self.identity)
        record = self._add(meta)
        record.update(checkpoint=checkpoint, local=True, verified=True, buffer=data, error=None)
        return meta['revisionId']

    def statuses(self, revision_id):
        record = self._record(revision_id)
        return [name for name in ('local', 'queued', 'uploaded', 'downloaded', 'verified') if record[name]]

    def queue_upload(self, revision_id):
        record = self._record(revision_id)
        need(record['verified'] and record['checkpoint'] is not None, 'Upload requires a verified catalogue archive')
        operation_id = 'put:' + revision_id
        if record['uploaded']:
            return operation_id
        record['queued'] = True
        self.operations[operation_id] = {'revisionId': revision_id, 'state': 'queued'}
        return operation_id

    def upload_intent(self, operation_id):
        need(operation_id in self.operations, 'Unknown transfer operation')
        op = self.operations[operation_id]
        need(op['state'] == 'queued', 'Transfer is not queued')
        record = self._record(op['revisionId'])
        known_remote = self.remote['revisionIds'] if self.remote else []
        need(all(self._record(p)['uploaded'] or p in known_remote for p in record['revision']['parentIds']),
             'Publish acknowledged parent revisions before their child')
        return {'operationId': operation_id, 'revision': copy.deepcopy(record['revision']),
                'archive': record['buffer']}

    def acknowledge_upload(self, operation_id, revision_id, archive_sha):
        need(operation_id in self.operations, 'Unknown transfer acknowledgement')
        op = self.operations[operation_id]
        need(op['revisionId'] == revision_id and self._record(revision_id)['revision']['passportSha256'] == archive_sha,
             'Upload acknowledgement differs')
        # Cancellation cannot undo an already accepted remote put. A late reply is
        # deliberately not presented as the result of a cancelled local operation.
        if op['state'] == 'cancelled':
            return False
        self._record(revision_id).update(queued=False, uploaded=True)
        op['state'] = 'uploaded'
        return True

    def cancel_upload(self, operation_id):
        need(operation_id in self.operations, 'Unknown transfer operation')
        op = self.operations[operation_id]
        if op['state'] == 'queued':
            op['state'] = 'cancelled'
            self._record(op['revisionId'])['queued'] = False

    def observe_inventory(self, revisions, heads, inventory_token, session_id=None):
        """Complete ancestry, scoped to this identity; validate atomically."""
        sha(inventory_token)
        if session_id is not None:
            need(self._startup()['sessionId'] == session_id, 'Inventory belongs to another startup session')
        need(isinstance(revisions, list) and len(revisions) <= MAX_REVISIONS, 'Invalid remote inventory')
        incoming = {}
        for raw in revisions:
            meta = revision(raw, self.identity)
            need(meta['revisionId'] not in incoming, 'Duplicate remote revision')
            incoming[meta['revisionId']] = meta
        for meta in incoming.values():
            need(all(parent in incoming for parent in meta['parentIds']), 'Incomplete remote ancestry')
            if meta['revisionId'] in self.records:
                need(self.records[meta['revisionId']]['revision'] == meta, 'Remote revision differs')
        need(isinstance(heads, list) and all(isinstance(h, str) for h in heads)
             and heads == sorted(set(heads)), 'Invalid remote heads')
        parents = {parent for meta in incoming.values() for parent in meta['parentIds']}
        need(set(heads) == set(incoming) - parents, 'Remote heads do not match ancestry')
        need(inventory_token == digest({'revisionIds': sorted(incoming), 'heads': heads}), 'Inventory token does not bind its content')
        need(len(set(self.records) | set(incoming)) <= MAX_REVISIONS, 'Revision limit reached; retain/export branches')
        # The content-addressed graph is still traversed explicitly so malformed
        # future metadata cannot turn a graph walk into an unbounded loop.
        for current in incoming:
            seen, stack = set(), list(incoming[current]['parentIds'])
            while stack:
                item = stack.pop()
                need(item != current, 'Cyclic save ancestry')
                if item not in seen:
                    seen.add(item); stack.extend(incoming[item]['parentIds'])
        for meta in incoming.values():
            self._add(meta)
        self.remote = {'heads': list(heads), 'token': inventory_token, 'revisionIds': sorted(incoming)}
        if session_id is not None:
            self.startup['fresh'] = True
            if self.startup.get('inventoryToken') != inventory_token:
                self.startup['selection'] = None
                self.startup['localChoice'] = False
            self.startup['inventoryToken'] = inventory_token
            self.startup['heads'] = list(heads)

    def begin_download(self, revision_id, transfer_id):
        record = self._record(revision_id)
        token(transfer_id)
        need(not record['verified'] and record['error'] is None, 'Cancel corrupt transport before retrying')
        need(transfer_id not in self.used_downloads and len(self.used_downloads) < MAX_REVISIONS,
             'Download session must be new')
        self.used_downloads.append(transfer_id)
        record['downloadId'] = transfer_id
        return len(record['buffer'])

    def append_download(self, revision_id, transfer_id, offset, chunk):
        record = self._record(revision_id)
        need(not record['verified'], 'Verified archive is immutable')
        need(record['downloadId'] is not None and record['downloadId'] == transfer_id, 'Download session is stale or cancelled')
        need(type(offset) is int and offset == len(record['buffer']), 'Download offset differs; restart or resume exact prefix')
        need(isinstance(chunk, bytes) and 0 < len(chunk) <= 1024 * 1024, 'Invalid download chunk')
        need(offset + len(chunk) <= record['revision']['bytes'], 'Download exceeds declared archive')
        record['buffer'] += chunk
        record['downloaded'] = len(record['buffer']) == record['revision']['bytes']
        record['error'] = None

    def cancel_download(self, revision_id):
        record = self._record(revision_id)
        need(not record['verified'], 'Verified archive is immutable')
        record.update(buffer=b'', downloaded=False, error=None, downloadId=None)

    def verify_download(self, revision_id):
        record = self._record(revision_id)
        meta = record['revision']
        need(record['downloaded'], 'Download is incomplete')
        try:
            need(hashlib.sha256(record['buffer']).hexdigest() == meta['passportSha256'], 'Archive checksum failed')
            need(inspect_archive(record['buffer'], self.identity) == meta['saveDataSha256'], 'Save-data checksum differs')
        except SyncError:
            record['error'] = 'verification-failed'
            raise
        record.update(verified=True, error=None, downloadId=None)

    def attach_checkpoint(self, revision_id, checkpoint):
        """Only after the verified archive is imported into the F07 catalogue."""
        record = self._record(revision_id)
        need(record['verified'], 'Catalogue import requires verified bytes')
        record['checkpoint'] = reference(checkpoint, self.identity, record['revision']['passportSha256'])
        record['local'] = True

    def is_ancestor(self, ancestor, child):
        self._record(ancestor); self._record(child)
        seen, stack = set(), [child]
        while stack:
            current = stack.pop()
            if current == ancestor:
                return True
            if current not in seen:
                seen.add(current); stack.extend(self._record(current)['revision']['parentIds'])
        return False

    def begin_startup(self, session_id, current_revision):
        token(session_id)
        need(session_id not in self.used_sessions and len(self.used_sessions) < MAX_REVISIONS,
             'Startup session must be new')
        record = self._record(current_revision)
        need(record['verified'] and record['checkpoint'] is not None, 'Current branch requires a verified checkpoint')
        self.used_sessions.append(session_id)
        self.startup = {'sessionId': session_id, 'current': current_revision, 'fresh': False,
                        'inventoryToken': None, 'heads': None, 'selection': None, 'localChoice': False,
                        'idle': None, 'staged': None, 'issued': False}

    def _startup(self):
        need(self.startup is not None and not self.startup['issued'], 'No active startup barrier')
        return self.startup

    def observe_idle(self, receipt):
        state = self._startup()
        need(isinstance(receipt, dict) and set(receipt) == {'sessionId', 'boundaryId', 'identity', 'state', 'saveDataSha256'},
             'Invalid runtime boundary receipt')
        need(receipt['sessionId'] == state['sessionId'] and receipt['state'] == 'contentless'
             and known_identity(receipt['identity']) == self.identity
             and receipt['saveDataSha256'] == self._record(state['current'])['revision']['saveDataSha256'],
             'Runtime boundary or current save readback differs')
        token(receipt['boundaryId'])
        state['idle'] = copy.deepcopy(receipt)

    def invalidate_runtime(self):
        """Any activity, process change or uncertain lifecycle invalidates startup."""
        self.startup = None

    def choose_branch(self, revision_id, prefer_local=False):
        state = self._startup()
        record = self._record(revision_id)
        need(type(prefer_local) is bool, 'Invalid branch choice')
        if prefer_local:
            need(record['verified'] and record['checkpoint'] is not None, 'Local choice requires retained verified data')
        else:
            need(state['fresh'] and revision_id in state['heads'], 'Choose a current remote head')
        state['selection'] = revision_id
        state['localChoice'] = prefer_local
        state['staged'] = None

    def _selection(self):
        state = self._startup()
        if state['selection'] is not None:
            return state['selection']
        if not state['fresh']:
            return None
        heads, current = state['heads'], state['current']
        if all(self.is_ancestor(head, current) for head in heads):
            return current
        if len(heads) == 1 and self.is_ancestor(current, heads[0]):
            return heads[0]
        return None

    def barrier(self):
        state = self._startup()
        selected = self._selection()
        if selected is None:
            return 'needs-branch-choice' if state['fresh'] else 'needs-inventory-or-local-choice'
        record = self._record(selected)
        if not record['downloaded'] and not record['verified']:
            return 'needs-download'
        if not record['verified']:
            return 'needs-verification'
        if record['checkpoint'] is None:
            return 'needs-catalogue-import'
        if state['idle'] is None:
            return 'needs-runtime-idle-readback'
        if selected != state['current']:
            return 'needs-runtime-apply'
        return 'ready-local-choice' if state['localChoice'] else 'needs-remote-head-guard'

    def record_staged(self, receipt):
        state = self._startup()
        selected = self._selection()
        need(selected is not None, 'Select a branch before staging')
        record = self._record(selected)
        need(record['verified'] and record['checkpoint'] is not None, 'Staging requires a verified catalogue archive')
        expected = {'sessionId': state['sessionId'], 'revisionId': selected,
                    'checkpointId': record['checkpoint']['checkpointId'],
                    'passportSha256': record['revision']['passportSha256']}
        need(receipt == expected, 'Staging receipt differs')
        state['staged'] = selected

    def record_applied(self, receipt):
        state = self._startup()
        selected = self._selection()
        need(selected is not None and state['idle'] is not None and state['staged'] == selected,
             'Runtime apply requires idle boundary and separate staging receipt')
        expected = {'sessionId': state['sessionId'], 'boundaryId': state['idle']['boundaryId'],
                    'revisionId': selected, 'saveDataSha256': self._record(selected)['revision']['saveDataSha256']}
        need(receipt == expected, 'Runtime import/readback receipt differs')
        state['current'] = selected
        state['idle']['saveDataSha256'] = expected['saveDataSha256']

    def issue_load_intent(self, guard=None):
        """One-use intent only. The model never launches a process or restores files."""
        state = self._startup()
        result = self.barrier()
        need(result in {'ready-local-choice', 'needs-remote-head-guard'}, 'Pre-launch save barrier is not satisfied')
        guard_id = None
        if not state['localChoice']:
            need(isinstance(guard, dict) and set(guard) == {'guardId', 'sessionId', 'identity', 'inventoryToken'},
                 'A live remote-head guard is required')
            need(guard['sessionId'] == state['sessionId'] and known_identity(guard['identity']) == self.identity
                 and guard['inventoryToken'] == state['inventoryToken'], 'Remote-head guard is stale or differs')
            guard_id = token(guard['guardId'])
        state['issued'] = True
        return {'intent': 'load-content', 'sessionId': state['sessionId'], 'revisionId': state['current'],
                'saveDataSha256': self._record(state['current'])['revision']['saveDataSha256'],
                'remoteGuardId': guard_id, 'explicitLocalChoice': state['localChoice']}

    def snapshot(self):
        """Private adapter checkpoint; buffers contain save bytes. No live receipts."""
        records = copy.deepcopy(self.records)
        for record in records.values():
            record['buffer'] = base64.b64encode(record['buffer']).decode('ascii')
        return {'schemaVersion': 1, 'identity': copy.deepcopy(self.identity), 'records': records,
                'operations': copy.deepcopy(self.operations), 'remote': copy.deepcopy(self.remote),
                'usedSessions': list(self.used_sessions), 'usedDownloads': list(self.used_downloads)}

    @classmethod
    def restart(cls, snapshot):
        need(isinstance(snapshot, dict) and set(snapshot) == {'schemaVersion', 'identity', 'records', 'operations', 'remote', 'usedSessions', 'usedDownloads'}
             and type(snapshot['schemaVersion']) is int and snapshot['schemaVersion'] == 1, 'Unsupported sync checkpoint')
        model = cls(snapshot['identity'])
        records = snapshot['records']
        need(isinstance(records, dict) and len(records) <= MAX_REVISIONS, 'Invalid checkpoint revisions')
        for revision_id, raw in records.items():
            need(isinstance(raw, dict) and set(raw) == {'revision', 'checkpoint', 'local', 'queued', 'uploaded',
                 'downloaded', 'verified', 'buffer', 'error', 'downloadId'}, 'Invalid checkpoint revision state')
            meta = revision(raw['revision'], model.identity)
            need(meta['revisionId'] == revision_id, 'Checkpoint revision key differs')
            for flag in ('local', 'queued', 'uploaded', 'downloaded', 'verified'):
                need(type(raw[flag]) is bool, 'Invalid transfer status')
            need(raw['error'] in (None, 'verification-failed'), 'Invalid transfer error')
            if raw['downloadId'] is not None:
                token(raw['downloadId'])
            try:
                need(isinstance(raw['buffer'], str) and len(raw['buffer']) <= (MAX_ARCHIVE + 2) // 3 * 4,
                     'Invalid checkpoint buffer')
                data = base64.b64decode(raw['buffer'], validate=True)
            except (ValueError, TypeError):
                raise SyncError('Invalid checkpoint buffer') from None
            need(len(data) <= meta['bytes'], 'Checkpoint buffer exceeds archive')
            need(not raw['downloaded'] or len(data) == meta['bytes'], 'Incomplete downloaded checkpoint')
            need(raw['verified'] or raw['downloaded'] == (len(data) == meta['bytes']), 'Downloaded checkpoint status differs')
            need(not raw['verified'] or (raw['error'] is None and raw['downloadId'] is None), 'Verified checkpoint has an active failed transfer')
            if raw['verified']:
                need(hashlib.sha256(data).hexdigest() == meta['passportSha256']
                     and inspect_archive(data, model.identity) == meta['saveDataSha256'], 'Verified checkpoint bytes differ')
            need(not (raw['local'] or raw['uploaded'] or raw['queued']) or raw['verified'], 'Transfer status lacks verified bytes')
            need(not (raw['uploaded'] or raw['queued']) or raw['local'], 'Upload status lacks a local catalogue branch')
            checkpoint = reference(raw['checkpoint'], model.identity, meta['passportSha256']) if raw['checkpoint'] is not None else None
            need(not raw['local'] or checkpoint is not None, 'Local branch lacks catalogue reference')
            model.records[revision_id] = {**copy.deepcopy(raw), 'revision': meta, 'buffer': data, 'checkpoint': checkpoint, 'downloadId': None}
        for record in model.records.values():
            need(all(p in records for p in record['revision']['parentIds']), 'Checkpoint ancestry is incomplete')
        ops = snapshot['operations']
        need(isinstance(ops, dict) and len(ops) <= MAX_REVISIONS, 'Invalid queued operations')
        for operation_id, op in ops.items():
            need(isinstance(op, dict) and set(op) == {'revisionId', 'state'} and op['revisionId'] in records
                 and operation_id == 'put:' + op['revisionId'] and op['state'] in ('queued', 'uploaded', 'cancelled'), 'Invalid queued operation')
            record = model.records[op['revisionId']]
            need(record['queued'] == (op['state'] == 'queued') and record['uploaded'] == (op['state'] == 'uploaded'),
                 'Transfer checkpoint status differs')
        need(all(not (r['queued'] or r['uploaded']) or 'put:' + key in ops for key, r in model.records.items()), 'Transferred revision lacks operation')
        model.operations = copy.deepcopy(ops)
        remote = snapshot['remote']
        if remote is not None:
            need(isinstance(remote, dict) and set(remote) == {'heads', 'token', 'revisionIds'}, 'Invalid last-known inventory')
            sha(remote['token'])
            need(isinstance(remote['heads'], list) and all(isinstance(h, str) for h in remote['heads']) and remote['heads'] == sorted(set(remote['heads']))
                 and all(head in records for head in remote['heads']), 'Invalid last-known heads')
            ids = remote['revisionIds']
            need(isinstance(ids, list) and all(isinstance(item, str) for item in ids) and ids == sorted(set(ids))
                 and all(item in records for item in ids), 'Invalid last-known revision set')
            need(all(p in ids for item in ids for p in records[item]['revision']['parentIds']), 'Last-known ancestry is incomplete')
            parents = {p for item in ids for p in records[item]['revision']['parentIds']}
            need(set(remote['heads']) == set(ids) - parents and remote['token'] == digest({'revisionIds': ids, 'heads': remote['heads']}),
                 'Last-known inventory token differs')
        model.remote = copy.deepcopy(remote)
        sessions = snapshot['usedSessions']
        need(isinstance(sessions, list) and len(sessions) <= MAX_REVISIONS and all(isinstance(s, str) for s in sessions) and len(set(sessions)) == len(sessions), 'Invalid startup history')
        model.used_sessions = [token(session) for session in sessions]
        downloads = snapshot['usedDownloads']
        need(isinstance(downloads, list) and len(downloads) <= MAX_REVISIONS and all(isinstance(d, str) for d in downloads)
             and len(set(downloads)) == len(downloads), 'Invalid download history')
        model.used_downloads = [token(d) for d in downloads]
        need(all(r['downloadId'] is None or r['downloadId'] in downloads for r in records.values()), 'Unknown checkpoint download session')
        # Runtime, staging, application and head guards cannot survive restart.
        return model
