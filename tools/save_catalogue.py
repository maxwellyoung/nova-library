#!/usr/bin/env python3
"""Private, transactional passport history; no emulator commands or live restore."""
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import struct
import tempfile
import uuid
import zlib

if __package__:
    from . import save_passport as passport
else:
    import save_passport as passport

DEFAULT_POLICY = {'quickSlots': 20, 'maxEntries': 128, 'maxBytes': 512 * 1024 * 1024,
                  'maxPassportBytes': 256 * 1024 * 1024, 'trashEntries': 64,
                  'trashBytes': 256 * 1024 * 1024, 'trashDays': 30}
MAX_THUMBNAIL = 2 * 1024 * 1024
RECORD_COLUMNS = ('sequence,id,archive_sha,manifest,name,pinned,status,added_at,deleted_at,expires_at,'
                  'thumbnail,thumbnail_sha,thumbnail_status,length(archive) AS bytes')


class CatalogueError(passport.PassportError):
    """Fixed, path-free adapter diagnostic."""


def require(value, message):
    if not value:
        raise CatalogueError(message)


def policy(value):
    require(isinstance(value, dict) and set(value) == set(DEFAULT_POLICY)
            and all(type(v) is int and v > 0 for v in value.values()), 'Invalid retention policy')
    require(value['quickSlots'] <= value['maxEntries'] <= 4096
            and value['trashEntries'] <= value['maxEntries']
            and value['maxPassportBytes'] <= value['maxBytes'] <= 1024 * 1024 * 1024
            and value['maxPassportBytes'] <= 256 * 1024 * 1024
            and value['trashBytes'] <= value['maxBytes'] and value['trashDays'] <= 3650,
            'Retention policy exceeds supported bounds')
    return dict(value)


def checkpoint_id(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{32}', value), 'Invalid checkpoint ID')
    return value


def named(value, pinned):
    require(isinstance(value, str) and len(value) <= 120 and type(pinned) is bool, 'Invalid checkpoint name or pin')
    if value:
        passport.label(value)
    require(not pinned or bool(value), 'A protected anchor needs an explicit name')


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def valid_png(data):
    """Validate bounded noninterlaced 8-bit RGB/RGBA PNG, without a GUI decoder."""
    try:
        if not data.startswith(b'\x89PNG\r\n\x1a\n') or len(data) > MAX_THUMBNAIL:
            return False
        offset, dimensions, compressed, ended = 8, None, bytearray(), False
        seen_idat, idat_ended = False, False
        while offset < len(data):
            length, kind = struct.unpack('>I4s', data[offset:offset + 8])
            chunk = data[offset + 8:offset + 8 + length]
            crc = struct.unpack('>I', data[offset + 8 + length:offset + 12 + length])[0]
            if len(chunk) != length or zlib.crc32(kind + chunk) & 0xffffffff != crc:
                return False
            if kind == b'IHDR':
                if dimensions is not None or offset != 8 or length != 13:
                    return False
                width, height, bits, colour, compression, filtering, interlace = struct.unpack('>IIBBBBB', chunk)
                if not (0 < width <= 2048 and 0 < height <= 2048 and bits == 8 and colour in (2, 6)
                        and compression == filtering == interlace == 0):
                    return False
                dimensions = (width, height, 3 if colour == 2 else 4)
            elif kind == b'IDAT':
                if dimensions is None or idat_ended:
                    return False
                seen_idat = True
                compressed.extend(chunk)
            elif kind == b'IEND':
                if length != 0 or offset + 12 != len(data):
                    return False
                ended = True
            elif kind[0] & 32 == 0:
                return False  # Unknown critical format feature.
            if seen_idat and kind != b'IDAT':
                idat_ended = True
            offset += 12 + length
        if not ended or dimensions is None:
            return False
        width, height, channels = dimensions
        stride = 1 + width * channels
        inflater = zlib.decompressobj()
        pixels = inflater.decompress(compressed, height * stride + 1)
        return (len(pixels) == height * stride and inflater.eof and not inflater.unused_data
                and not inflater.unconsumed_tail and all(pixels[i] <= 4 for i in range(0, len(pixels), stride)))
    except (ValueError, IndexError, struct.error, zlib.error):
        return False


def thumbnail(path):
    if path is None:
        return None, None, 'missing'
    try:
        with passport.open_archive(path) as source:
            before = passport.file_state(os.fstat(source.fileno()))
            if before[2] > MAX_THUMBNAIL:
                return None, None, 'invalid'
            data = source.read(MAX_THUMBNAIL + 1)
            if before != passport.file_state(os.fstat(source.fileno())) or not valid_png(data):
                return None, None, 'invalid'
            return data, hashlib.sha256(data).hexdigest(), 'available'
    except FileNotFoundError:
        return None, None, 'missing'
    except (OSError, ValueError):
        return None, None, 'invalid'


class BlobStream:
    def __init__(self, blob):
        self.blob = blob

    def read(self, size=-1):
        return self.blob.read(size)

    def seek(self, offset, whence=os.SEEK_SET):
        self.blob.seek(offset, whence)
        return self.blob.tell()

    def tell(self):
        return self.blob.tell()


class Catalogue:
    def __init__(self, root, *, create=False, retention=None, clock=None):
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.root = Path(root).absolute()
        repo = Path(__file__).resolve().parents[1]
        require(self.root != repo and repo not in self.root.parents
                and not any((p / '.git').exists() for p in (self.root, *self.root.parents)),
                'Private save catalogues must remain outside repositories')
        if create:
            passport.directory(self.root.parent)
            self.root.mkdir(mode=0o700)  # An existing folder is never adopted.
        passport.directory(self.root)
        require(stat.S_IMODE(self.root.stat().st_mode) & 0o077 == 0, 'Catalogue directory must be owner-only')
        self.path = self.root / 'catalogue.sqlite3'
        if create:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        require(not self.path.is_symlink() and self.path.is_file(), 'Catalogue database is unavailable or linked')
        require(stat.S_IMODE(self.path.stat().st_mode) & 0o077 == 0, 'Catalogue database must be owner-only')
        try:
            self.db = sqlite3.connect(self.path.as_uri() + '?mode=rw', uri=True, timeout=1)
            self.db.row_factory = sqlite3.Row
            self.db.execute('PRAGMA synchronous=FULL')
            self.db.execute('PRAGMA secure_delete=ON')
            if create:
                with self.db:
                    self.db.execute('CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
                    self.db.execute('''CREATE TABLE records (
                        sequence INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                        archive BLOB NOT NULL, archive_sha TEXT NOT NULL, manifest TEXT NOT NULL,
                        name TEXT NOT NULL, pinned INTEGER NOT NULL, status TEXT NOT NULL,
                        added_at TEXT NOT NULL, deleted_at TEXT, expires_at TEXT,
                        thumbnail BLOB, thumbnail_sha TEXT, thumbnail_status TEXT NOT NULL)''')
                    values = {'catalogueId': uuid.uuid4().hex, 'generation': 0,
                              'policy': policy(retention if retention is not None else DEFAULT_POLICY)}
                    self.db.executemany('INSERT INTO metadata VALUES (?, ?)', [(k, encoded(v)) for k, v in values.items()])
                    self.db.execute('PRAGMA user_version=1')
            require(self.db.execute('PRAGMA user_version').fetchone()[0] == 1, 'Unsupported save catalogue schema')
            objects = {(row['type'], row['name']) for row in self.db.execute(
                "SELECT type,name FROM sqlite_master WHERE type IN ('table','trigger','view')")}
            require(objects == {('table', 'metadata'), ('table', 'records'), ('table', 'sqlite_sequence')},
                    'Unexpected save catalogue structure')
            self.retention = policy(self._meta('policy'))
            require(retention is None or policy(retention) == self.retention, 'Retention policy differs from this catalogue')
        except BaseException as error:
            if hasattr(self, 'db'):
                self.db.close()
            if isinstance(error, sqlite3.Error):
                raise CatalogueError('Invalid or unavailable catalogue database') from None
            raise

    def close(self):
        self.db.close()

    def _commit(self):
        self.db.commit()

    def _meta(self, key):
        row = self.db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        require(row is not None, 'Catalogue metadata is incomplete')
        return passport.parse_json(row[0])

    def _now(self):
        value = self.clock()
        require(isinstance(value, dt.datetime) and value.tzinfo is not None, 'Catalogue clock is unavailable')
        return value.astimezone(dt.timezone.utc)

    def _stamp(self, value=None):
        return (value or self._now()).strftime('%Y-%m-%dT%H:%M:%SZ')

    @contextmanager
    def _transaction(self, write=False):
        try:
            self.db.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
            yield
            if write:
                self.db.execute('UPDATE metadata SET value=? WHERE key=?', (encoded(self._meta('generation') + 1), 'generation'))
            self._commit()
        except BaseException as error:
            self.db.rollback()
            if isinstance(error, sqlite3.Error):
                raise CatalogueError('Catalogue transaction failed; prior history is retained') from None
            raise

    def _row(self, value, active=False):
        row = self.db.execute('SELECT ' + RECORD_COLUMNS + ' FROM records WHERE id=?', (checkpoint_id(value),)).fetchone()
        require(row is not None, 'Checkpoint is unavailable')
        require(not active or row['status'] == 'active', 'Checkpoint is in trash; undo it before staging')
        return row

    def _identity(self, row):
        return passport.identity(passport.manifest(passport.parse_json(row['manifest'])))

    def _verify(self, row):
        with self.db.blobopen('records', 'archive', row['sequence'], readonly=True) as blob:
            stream = BlobStream(blob)
            h = hashlib.sha256()
            while data := stream.read(1024 * 1024):
                h.update(data)
            require(h.hexdigest() == row['archive_sha'], 'Stored passport checksum failed; history was retained')
            result = passport.scan(stream)
            require(encoded(result) == row['manifest'], 'Stored passport metadata differs; history was retained')
            return result

    def _quick(self, identity):
        return [r for r in self.db.execute('SELECT ' + RECORD_COLUMNS + ' FROM records ORDER BY sequence')
                if r['status'] == 'active' and not r['pinned'] and self._identity(r) == identity]

    def import_passport(self, path, *, name='', pinned=False, thumbnail_path=None):
        named(name, pinned)
        image, image_sha, image_status = thumbnail(thumbnail_path)
        with passport.open_archive(path) as source, self._transaction(write=True):
            before = passport.file_state(os.fstat(source.fileno()))
            size = before[2]
            require(size <= self.retention['maxPassportBytes'], 'Passport exceeds this catalogue record limit')
            result = passport.scan(source)
            require(pinned or len(self._quick(passport.identity(result))) < self.retention['quickSlots'],
                    'Quick-save slots are full; explicitly review rotation to trash first')
            count, used = self.db.execute('SELECT count(*),coalesce(sum(length(archive)+coalesce(length(thumbnail),0)),0) FROM records').fetchone()
            require(count < self.retention['maxEntries'] and used + size + len(image or b'') <= self.retention['maxBytes'],
                    'Catalogue is full; review trash purge or export before adding history')
            identifier = uuid.uuid4().hex
            cursor = self.db.execute('''INSERT INTO records
                (id,archive,archive_sha,manifest,name,pinned,status,added_at,thumbnail,thumbnail_sha,thumbnail_status)
                VALUES (?,zeroblob(?),'',?,?,?,'active',?,?,?,?)''',
                (identifier, size, encoded(result), name, int(pinned), self._stamp(), image, image_sha, image_status))
            source.seek(0)
            h = hashlib.sha256()
            with self.db.blobopen('records', 'archive', cursor.lastrowid) as blob:
                while data := source.read(1024 * 1024):
                    blob.write(data)
                    h.update(data)
            require(before == passport.file_state(os.fstat(source.fileno())), 'Passport changed during import; prior history is retained')
            self.db.execute('UPDATE records SET archive_sha=? WHERE id=?', (h.hexdigest(), identifier))
            self._verify(self._row(identifier))
        return self.reference(identifier)

    def reference(self, identifier):
        with self._transaction():
            row = self._row(identifier, active=True)
            result = self._verify(row)
            return {'checkpointId': row['id'], 'passportSha256': row['archive_sha'], 'identity': passport.identity(result)}

    def _thumbnail(self, row):
        data = row['thumbnail']
        if data is None:
            return None, row['thumbnail_status']
        if hashlib.sha256(data).hexdigest() != row['thumbnail_sha'] or not valid_png(data):
            return None, 'corrupt'
        return data, 'available'

    def thumbnail(self, identifier):
        with self._transaction():
            return self._thumbnail(self._row(identifier))[0]

    def list_entries(self, *, target=None, include_trash=False):
        with self._transaction():
            entries = []
            for row in self.db.execute('SELECT ' + RECORD_COLUMNS + ' FROM records ORDER BY sequence DESC'):
                if not include_trash and row['status'] != 'active':
                    continue
                meta = passport.manifest(passport.parse_json(row['manifest']))
                compatibility = 'Target identity has not been reviewed'
                if target is not None:
                    try:
                        passport.compatible(meta, target)
                        compatibility = 'Identity matches; emulator import and boot remain unverified'
                    except passport.PassportError as error:
                        compatibility = str(error)
                entries.append({'checkpointId': row['id'], 'passportSha256': row['archive_sha'],
                                'identity': passport.identity(meta), 'capturedAt': meta['createdAt'],
                                'addedAt': row['added_at'], 'name': row['name'], 'pinned': bool(row['pinned']),
                                'status': row['status'], 'expiresAt': row['expires_at'], 'bytes': row['bytes'],
                                'thumbnailBytes': len(row['thumbnail'] or b''),
                                'thumbnailStatus': self._thumbnail(row)[1], 'compatibility': compatibility,
                                'integrity': 'Rechecked by review/reference/stage, not by timeline listing',
                                'runtimeRestoreAvailable': False})
            return entries

    def rename(self, identifier, name, *, pinned):
        named(name, pinned)
        with self._transaction(write=True):
            self._row(identifier, active=True)
            self.db.execute('UPDATE records SET name=?,pinned=? WHERE id=?', (name, int(pinned), identifier))
            require(pinned or len(self._quick(self._identity(self._row(identifier)))) <= self.retention['quickSlots'],
                    'Unpinning would overflow quick-save slots; review rotation first')

    def _plan(self, action, identifiers):
        require(isinstance(action, str) and action in {'trash', 'purge'}
                and isinstance(identifiers, (list, tuple))
                and all(isinstance(i, str) for i in identifiers)
                and len(set(identifiers)) == len(identifiers) <= self.retention['maxEntries'], 'Invalid retention selection')
        rows = [self._row(i) for i in sorted(identifiers)]
        if action == 'trash':
            require(all(r['status'] == 'active' and not r['pinned'] for r in rows), 'Protected anchors or nonactive checkpoints cannot rotate or enter trash')
            count, size = self.db.execute("SELECT count(*),coalesce(sum(length(archive)+coalesce(length(thumbnail),0)),0) FROM records WHERE status='trash'").fetchone()
            require(count + len(rows) <= self.retention['trashEntries'] and size + sum(r['bytes'] + len(r['thumbnail'] or b'') for r in rows) <= self.retention['trashBytes'],
                    'Trash retention is full; review explicit purge before deleting or rotating')
        else:
            require(all(r['status'] == 'trash' for r in rows), 'Only explicitly trashed checkpoints can be purged')
        result = {'schemaVersion': 1, 'catalogueId': self._meta('catalogueId'), 'generation': self._meta('generation'),
                  'undoForDays': self.retention['trashDays'] if action == 'trash' else 0,
                  'permanent': action == 'purge',
                  'action': action, 'items': [{'checkpointId': r['id'], 'passportSha256': r['archive_sha'],
                                              'bytes': r['bytes'], 'thumbnailBytes': len(r['thumbnail'] or b''),
                                              'expiresAt': r['expires_at']} for r in rows]}
        result['token'] = hashlib.sha256(encoded(result).encode()).hexdigest()
        return result

    def plan_delete(self, identifiers):
        with self._transaction():
            return self._plan('trash', identifiers)

    def plan_rotation(self, target, *, reserve=1):
        with self._transaction():
            wanted = passport.compatible(target, target)
            require(type(reserve) is int and 0 <= reserve <= self.retention['quickSlots'], 'Invalid rotation reservation')
            rows = self._quick(wanted)
            count = max(0, len(rows) - (self.retention['quickSlots'] - reserve))
            return self._plan('trash', [r['id'] for r in rows[:count]])

    def plan_purge(self, identifiers=None):
        with self._transaction():
            if identifiers is None:
                identifiers = [r['id'] for r in self.db.execute("SELECT id FROM records WHERE status='trash' AND expires_at<=?", (self._stamp(),))]
            return self._plan('purge', identifiers)

    def apply(self, plan):
        with self._transaction(write=True):
            require(isinstance(plan, dict) and set(plan) == {'schemaVersion', 'catalogueId', 'generation', 'action', 'items', 'token', 'undoForDays', 'permanent'}
                    and type(plan['schemaVersion']) is int and plan['schemaVersion'] == 1
                    and type(plan['generation']) is int
                    and type(plan['undoForDays']) is int and type(plan['permanent']) is bool
                    and isinstance(plan['items'], list) and all(isinstance(i, dict) and 'checkpointId' in i for i in plan['items']),
                    'Invalid retention plan')
            identifiers = [i['checkpointId'] for i in plan['items']]
            require(self._plan(plan['action'], identifiers) == plan, 'Retention preview changed; review it again')
            for identifier in identifiers:
                self._verify(self._row(identifier))
            if plan['action'] == 'trash':
                now = self._now()
                expires = self._stamp(now + dt.timedelta(days=self.retention['trashDays']))
                self.db.executemany("UPDATE records SET status='trash',deleted_at=?,expires_at=? WHERE id=?",
                                    [(self._stamp(now), expires, i) for i in identifiers])
            else:
                self.db.executemany('DELETE FROM records WHERE id=?', [(i,) for i in identifiers])
        return identifiers

    def undo(self, identifier):
        with self._transaction(write=True):
            row = self._row(identifier)
            require(row['status'] == 'trash' and row['expires_at'] > self._stamp(), 'Undo retention expired or checkpoint is not in trash')
            require(len(self._quick(self._identity(row))) < self.retention['quickSlots'], 'Quick-save slots are full; review rotation before undo')
            self._verify(row)
            self.db.execute("UPDATE records SET status='active',deleted_at=NULL,expires_at=NULL WHERE id=?", (identifier,))
        return self.reference(identifier)

    def review(self, identifier, target):
        with self._transaction():
            result = self._verify(self._row(identifier, active=True))
            passport.compatible(result, target)
            return result

    def export_passport(self, identifier, output):
        """Export exact archive bytes to a new filename; preserve the stored branch."""
        output = Path(output).absolute()
        parent = passport.directory(output.parent)
        require(not output.exists() and not output.is_symlink(), 'Passport export output already exists')
        with self._transaction():
            row = self._row(identifier)  # Trash can be exported before deliberate purge.
            self._verify(row)
            with tempfile.TemporaryDirectory(prefix='.save-export-', dir=parent) as temporary:
                candidate = Path(temporary) / 'candidate.nvs'
                with candidate.open('xb') as sink:
                    os.chmod(candidate, 0o600)
                    with self.db.blobopen('records', 'archive', row['sequence'], readonly=True) as blob:
                        while data := blob.read(1024 * 1024):
                            sink.write(data)
                    sink.flush()
                    os.fsync(sink.fileno())
                # Exclusive hard link publishes only complete, already verified bytes.
                os.link(candidate, output)
            return {'checkpointId': row['id'], 'passportSha256': row['archive_sha'], 'identity': self._identity(row)}

    def stage(self, identifier, target, output):
        with self._transaction():
            row = self._row(identifier, active=True)
            result = self._verify(row)
            passport.compatible(result, target)
            # Unnamed file disappears even if this process is interrupted.
            with tempfile.TemporaryFile(mode='w+b', dir=self.root) as temporary:
                with self.db.blobopen('records', 'archive', row['sequence'], readonly=True) as blob:
                    while data := blob.read(1024 * 1024):
                        temporary.write(data)
                temporary.flush()
                return passport.stage_file(temporary, target, output)
