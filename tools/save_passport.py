#!/usr/bin/env python3
"""Private, checksummed save archives. Import stages into a new directory only."""
import argparse
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tarfile
import tempfile
import unicodedata

MAX_FILES = 128
MAX_FILE = 512 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_MANIFEST = 128 * 1024
KINDS = {'native-save', 'emulator-state'}
UNKNOWN_LABELS = {'unknown', 'unverified', 'unspecified', 'pending', 'none', 'n/a', 'null', '?', '*'}


class PassportError(ValueError):
    """A fixed diagnostic containing no source values or private paths."""


def require(condition, message):
    if not condition:
        raise PassportError(message)


def label(value):
    require(isinstance(value, str) and value == value.strip() and 0 < len(value) <= 200
            and not re.search(r'[<>\x00-\x1f\x7f]', value), 'Invalid identity or runtime label')
    return value


def relative(value):
    label(value)
    require(unicodedata.normalize('NFC', value) == value and not any(c in value for c in '\\:*?"|'),
            'Invalid portable file path')
    p = PurePosixPath(value)
    require(bool(p.parts) and not p.is_absolute() and str(p) == value and all(part not in ('.', '..') and not part.startswith('.')
            and not part.endswith((' ', '.')) for part in p.parts), 'Unsafe portable file path')
    require(not any(re.fullmatch(r'(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?', part, re.I)
                    for part in p.parts), 'Reserved portable file name')
    return value


def identity(raw):
    require(isinstance(raw, dict), 'Missing save identity')
    runtime = raw.get('runtime')
    require(isinstance(runtime, dict) and set(runtime) == {'name', 'version', 'core'}, 'Missing runtime identity')
    require(isinstance(raw.get('kind'), str) and raw['kind'] in KINDS, 'Unsupported save kind')
    require(isinstance(raw.get('recipeId'), str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', raw['recipeId']),
            'Invalid setup recipe ID')
    return {'editionId': label(raw.get('editionId')), 'recipeId': label(raw.get('recipeId')),
            'kind': raw['kind'], 'runtime': {k: label(runtime[k]) for k in ('name', 'version', 'core')}}


def paths_unique(paths):
    seen = set()
    for path in paths:
        key = relative(path).casefold()
        require(key not in seen and not any(key.startswith(old + '/') or old.startswith(key + '/') for old in seen),
                'Duplicate or overlapping portable paths')
        seen.add(key)


def directory(path):
    path = Path(path).absolute()
    for current in reversed((path, *path.parents)):
        require(not current.is_symlink(), 'Symlinked directory is not supported; select its canonical path')
        require(current.is_dir(), 'Directory is unavailable')
    return path


def source_file(root, name):
    p = root
    for part in PurePosixPath(name).parts:
        p = p / part
        require(not p.is_symlink(), 'Symlinked save source is not supported')
    require(p.is_file(), 'Save source is not a regular file')
    return p


def file_state(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def read_json(path):
    with open_archive(path) as source:
        require(os.fstat(source.fileno()).st_size <= MAX_MANIFEST, 'Descriptor is too large')
        return parse_json(source.read(MAX_MANIFEST + 1))


def parse_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, 'Duplicate JSON metadata key; identity is ambiguous')
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


class HashReader:
    def __init__(self, source):
        self.source = source
        self.hash = hashlib.sha256()
        self.count = 0

    def read(self, count):
        data = self.source.read(count)
        self.hash.update(data)
        self.count += len(data)
        return data


def header(name, size):
    item = tarfile.TarInfo(name)
    item.size = size
    item.mode = 0o600
    item.mtime = 0
    return item


def manifest(value):
    require(isinstance(value, dict) and type(value.get('schemaVersion')) is int and value['schemaVersion'] == 1, 'Unsupported passport schema')
    require(set(value) == {'schemaVersion', 'editionId', 'recipeId', 'kind', 'runtime', 'createdAt', 'sourceState', 'files'},
            'Unexpected passport metadata')
    identity(value)
    require(value['sourceState'] == 'operator-confirmed-idle', 'Missing capture-state declaration')
    require(isinstance(value['createdAt'], str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value['createdAt']),
            'Invalid capture date')
    dt.datetime.strptime(value['createdAt'], '%Y-%m-%dT%H:%M:%SZ')
    files = value.get('files')
    require(isinstance(files, list) and 0 < len(files) <= MAX_FILES, 'Invalid save file count')
    total = 0
    for f in files:
        require(isinstance(f, dict) and set(f) == {'path', 'bytes', 'sha256'}, 'Invalid file manifest')
        require(type(f['bytes']) is int and 0 <= f['bytes'] <= MAX_FILE, 'Invalid save size')
        require(isinstance(f['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}', f['sha256']), 'Invalid save checksum')
        total += f['bytes']
    require(total <= MAX_TOTAL, 'Passport exceeds size limit')
    paths_unique([f['path'] for f in files])
    return value


def scan(source, sink=None):
    """Stream uncompressed tar without extracting archive-provided paths."""
    source.seek(0)
    observed = []
    result = None
    payload_end = 0
    with tarfile.open(fileobj=source, mode='r|') as archive:
        for item in archive:
            require(item.isreg() and not item.pax_headers and not item.sparse, 'Only ordinary passport files are allowed')
            require(result is None, 'Unexpected content after passport manifest')
            require(item.size >= 0 and len(observed) <= MAX_FILES, 'Invalid passport entry')
            stream = archive.extractfile(item)
            if item.name == 'manifest.json':
                require(item.size <= MAX_MANIFEST, 'Manifest exceeds size limit')
                result = manifest(parse_json(stream.read()))
                payload_end = item.offset_data + ((item.size + 511) // 512) * 512
                continue
            require(item.name == f'payload/{len(observed):04}' and len(observed) < MAX_FILES and item.size <= MAX_FILE,
                    'Unexpected or oversized passport entry')
            require(sum(f['bytes'] for f in observed) + item.size <= MAX_TOTAL, 'Passport exceeds size limit')
            h = hashlib.sha256()
            count = 0
            target = sink(len(observed)) if sink else None
            try:
                while True:
                    data = stream.read(1024 * 1024)
                    if not data:
                        break
                    count += len(data)
                    require(count <= item.size, 'Passport entry exceeds declared size')
                    h.update(data)
                    if target:
                        target.write(data)
            finally:
                if target:
                    target.close()
            require(count == item.size, 'Passport payload is truncated')
            observed.append({'bytes': count, 'sha256': h.hexdigest()})
    require(result is not None and len(result['files']) == len(observed), 'Passport manifest does not match its payload')
    require(all(expected['bytes'] == actual['bytes'] and expected['sha256'] == actual['sha256']
                for expected, actual in zip(result['files'], observed)), 'Passport checksum failed')
    size = source.seek(0, os.SEEK_END)
    expected_size = ((payload_end + 1024 + 10239) // 10240) * 10240
    require(size == expected_size, 'Unexpected passport trailer or truncation')
    source.seek(payload_end)
    require(not any(source.read(size - payload_end)), 'Unexpected content after passport manifest')
    return result


def open_archive(path):
    require(not Path(path).is_symlink(), 'Symlinked passport is not supported')
    f = os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)), 'rb')
    try:
        require(stat.S_ISREG(os.fstat(f.fileno()).st_mode) and os.fstat(f.fileno()).st_size <= MAX_TOTAL + 2 * 1024 * 1024,
                'Passport is not a bounded regular file')
    except Exception:
        f.close()
        raise
    return f


def pack(root, selection, output, source_idle=False):
    require(source_idle is True, 'Close the source emulator and explicitly confirm idle capture first')
    root = directory(root)
    require(isinstance(selection, dict) and type(selection.get('schemaVersion')) is int and selection['schemaVersion'] == 1
            and set(selection) == {'schemaVersion', 'editionId', 'recipeId', 'kind', 'runtime', 'files'},
            'Invalid save selection schema')
    meta = identity(selection)
    files = selection.get('files')
    require(isinstance(files, list) and 0 < len(files) <= MAX_FILES, 'Select explicit save files, not a directory scan')
    paths_unique(files)
    output = Path(output).absolute()
    parent = directory(output.parent)
    require(parent != root and root not in parent.parents, 'Keep the backup outside its save source')
    require(not output.exists() and not output.is_symlink(), 'Passport output already exists')
    selected = [(name, source_file(root, name)) for name in sorted(files)]
    require(sum(p.stat().st_size for _, p in selected) <= MAX_TOTAL, 'Selected saves exceed size limit')
    with tempfile.TemporaryDirectory(prefix='.save-passport-', dir=parent) as temporary:
        candidate = Path(temporary) / 'candidate.nvs'
        candidate.touch(mode=0o600)
        records = []
        states = []
        with tarfile.open(candidate, 'w', format=tarfile.USTAR_FORMAT) as archive:
            for index, (name, path) in enumerate(selected):
                with os.fdopen(os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NONBLOCK', 0)), 'rb') as source:
                    before = os.fstat(source.fileno())
                    require(stat.S_ISREG(before.st_mode) and 0 <= before.st_size <= MAX_FILE, 'Invalid save source size or type')
                    reader = HashReader(source)
                    archive.addfile(header(f'payload/{index:04}', before.st_size), reader)
                    require(reader.count == before.st_size and file_state(before) == file_state(os.fstat(source.fileno()))
                            and file_state(before) == file_state(source_file(root, name).stat()), 'Save source changed during capture; nothing published')
                    records.append({'path': name, 'bytes': reader.count, 'sha256': reader.hash.hexdigest()})
                    states.append((name, file_state(before)))
            meta.update(schemaVersion=1, createdAt=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                        sourceState='operator-confirmed-idle', files=records)
            encoded = json.dumps(meta, ensure_ascii=False, sort_keys=True).encode('utf-8')
            require(len(encoded) <= MAX_MANIFEST, 'Manifest exceeds size limit')
            archive.addfile(header('manifest.json', len(encoded)), io.BytesIO(encoded))
        with open_archive(candidate) as captured:
            scan(captured)
            os.fsync(captured.fileno())
        directory(root)
        require(all(file_state(source_file(root, name).stat()) == state for name, state in states),
                'Save source changed before backup publication; nothing published')
        # Linking a new file refuses an existing destination atomically.
        os.link(candidate, output)
    return meta


def verify(path):
    with open_archive(path) as source:
        before = file_state(os.fstat(source.fileno()))
        result = scan(source)
        require(before == file_state(os.fstat(source.fileno())), 'Passport changed while being verified')
        return result


def compatible(result, target):
    require(isinstance(target, dict) and set(target) == {'editionId', 'recipeId', 'kind', 'runtime'}, 'Invalid target identity')
    wanted = identity(target)
    captured = identity(result)
    for value in (captured, wanted):
        labels = [value['editionId'], value['recipeId'], *value['runtime'].values()]
        require(not any(item.casefold() in UNKNOWN_LABELS for item in labels)
                and value['runtime']['version'].casefold() not in {'latest', 'current'},
                'Unknown edition or runtime/setup identity; verify the actual configuration before staging')
    for field, reason in (
            ('editionId', 'Game edition differs; region, revision and disc-set compatibility need a tested adapter'),
            ('kind', 'Save kind differs; emulator states are not interchangeable with native saves'),
            ('recipeId', 'Setup recipe differs; compatibility has not been established')):
        require(captured[field] == wanted[field], reason)
    for field, reason in (
            ('name', 'Runtime differs; cross-runtime save compatibility has not been established'),
            ('version', 'Runtime version differs; native-save portability needs a tested adapter and states remain version-specific'),
            ('core', 'Runtime core differs; state and native-save format compatibility has not been established')):
        require(captured['runtime'][field] == wanted['runtime'][field], reason)
    return wanted


def review(path, target):
    """Verify bytes and identity without creating even a staging directory."""
    result = verify(path)
    compatible(result, target)
    return result


def stage(path, target, output):
    with open_archive(path) as source:
        return stage_file(source, target, output)


def stage_file(source, target, output):
    """Stage an open regular passport file, including a private unnamed adapter copy."""
    output = Path(output).absolute()
    parent = directory(output.parent)
    require(not output.exists() and not output.is_symlink(), 'Staging output already exists; live save folders are never overwritten')
    state = os.fstat(source.fileno())
    require(stat.S_ISREG(state.st_mode) and state.st_size <= MAX_TOTAL + 2 * 1024 * 1024,
            'Passport is not a bounded regular file')
    before = file_state(state)
    result = scan(source)
    compatible(result, target)
    with tempfile.TemporaryDirectory(prefix='.save-stage-', dir=parent) as temporary:
        temp = Path(temporary)
        def sink(index):
            require(index < len(result['files']), 'Passport changed during staging')
            f = temp / result['files'][index]['path']
            f.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            return os.fdopen(os.open(f, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb')
        require(scan(source, sink) == result and before == file_state(os.fstat(source.fileno())), 'Passport changed during staging')
        # Reserve a new destination before moving files; never replace a live folder.
        output.mkdir(mode=0o700)
        try:
            for child in temp.iterdir():
                child.rename(output / child.name)
        except Exception:
            shutil.rmtree(output)
            raise
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    create = sub.add_parser('pack')
    create.add_argument('--source', type=Path, required=True)
    create.add_argument('--selection', type=Path, required=True)
    create.add_argument('--output', type=Path, required=True)
    create.add_argument('--source-idle', action='store_true')
    check = sub.add_parser('verify')
    check.add_argument('passport', type=Path)
    preview = sub.add_parser('review', help='Verify restore compatibility without creating files')
    preview.add_argument('passport', type=Path)
    preview.add_argument('--target', type=Path, required=True)
    restore = sub.add_parser('stage')
    restore.add_argument('passport', type=Path)
    restore.add_argument('--target', type=Path, required=True)
    restore.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        if args.command == 'pack':
            result = pack(args.source, read_json(args.selection), args.output, args.source_idle)
        elif args.command == 'stage':
            result = stage(args.passport, read_json(args.target), args.output)
        elif args.command == 'review':
            result = review(args.passport, read_json(args.target))
        else:
            result = verify(args.passport)
        note = ' Identity matches; emulator import and boot remain unverified.' if args.command in {'review', 'stage'} else ''
        if result['kind'] == 'emulator-state':
            note += ' Emulator state: exact runtime/core only; not a portable native save.'
        print(f"{args.command}: {len(result['files'])} file(s), {sum(f['bytes'] for f in result['files'])} bytes verified.{note} No live save folder changed.")
    except (ValueError, OSError, tarfile.TarError, EOFError, UnicodeError) as error:
        # File errors can include private paths. Keep command output redacted.
        reason = str(error) if isinstance(error, PassportError) else f"Invalid or unavailable input ({type(error).__name__})"
        p.exit(1, f"{reason}. Source and existing outputs were not replaced.\n")


if __name__ == '__main__':
    main()
