#!/usr/bin/env python3
"""Prepare a new private, read-only Library bundle from verified save history."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

if __package__:
    from . import save_catalogue as history
    from . import save_passport as passport
    from .native_save_capture import private_output
else:
    import save_catalogue as history
    import save_passport as passport
    from native_save_capture import private_output

MAX_ENTRIES = 128
MAX_BYTES = 512 * 1024 * 1024


def export(catalogue, output, *, include_thumbnails=False):
    output = private_output(output)
    before = catalogue.list_entries()
    passport.require(len(before) <= MAX_ENTRIES, 'Save-copy export exceeds its entry limit')
    with tempfile.TemporaryDirectory(prefix='.save-copies-', dir=output.parent) as temporary:
        bundle = Path(temporary) / 'bundle'
        bundle.mkdir(mode=0o700)
        (bundle / 'archives').mkdir(mode=0o700)
        if include_thumbnails:
            (bundle / 'pictures').mkdir(mode=0o700)
        entries, total, seen = [], 0, set()
        for row in before:
            identifier, digest = row['checkpointId'], row['passportSha256']
            reference = catalogue.reference(identifier)
            passport.require(reference['passportSha256'] == digest
                             and reference['identity'] == row['identity'],
                             'Save history changed during export')
            archive = bundle / 'archives' / (digest + '.nvs')
            if digest not in seen:
                catalogue.export_passport(identifier, archive)
                total += archive.stat().st_size
                passport.require(total <= MAX_BYTES, 'Save-copy export exceeds its byte limit')
                seen.add(digest)
            manifest = passport.verify(archive)
            passport.require(passport.identity(manifest) == row['identity']
                             and manifest['createdAt'] == row['capturedAt'],
                             'Save-copy identity differs from history')
            with passport.open_archive(archive) as source:
                hashed = hashlib.file_digest(source, 'sha256').hexdigest()
            passport.require(hashed == digest, 'Save-copy archive differs from history')
            entries.append({'checkpointId': identifier, 'sha256': digest, 'bytes': archive.stat().st_size,
                            'identity': row['identity'], 'capturedAt': row['capturedAt'],
                            'addedAt': row['addedAt'], 'name': row['name'], 'pinned': row['pinned'],
                            'files': len(manifest['files']),
                            'payloadBytes': sum(f['bytes'] for f in manifest['files'])})
            if include_thumbnails:
                image = catalogue.thumbnail(identifier)
                picture = {'state': 'missing' if row['thumbnailStatus'] == 'missing' else 'unavailable'}
                if image is not None:
                    passport.require(row['thumbnailStatus'] == 'available' and history.valid_png(image),
                                     'Save-copy picture changed during export')
                    picture_sha = hashlib.sha256(image).hexdigest()
                    target = bundle / 'pictures' / (picture_sha + '.png')
                    if not target.exists():
                        total += len(image)
                        passport.require(total <= MAX_BYTES, 'Save-copy export exceeds its byte limit')
                        with target.open('xb') as stream:
                            os.chmod(target, 0o600)
                            stream.write(image); stream.flush(); os.fsync(stream.fileno())
                    picture = {'state': 'available', 'sha256': picture_sha, 'bytes': len(image)}
                else:
                    passport.require(row['thumbnailStatus'] != 'available',
                                     'Save-copy picture became unavailable during export')
                entries[-1]['picture'] = picture
        passport.require(catalogue.list_entries() == before, 'Save history changed before export publication')
        version = 2 if include_thumbnails else 1
        encoded = json.dumps({'schemaVersion': version, 'source': f'verified-passport-export-v{version}',
                              'entries': entries}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
        passport.require(len(encoded) <= 256 * 1024, 'Save-copy index exceeds its limit')
        with (bundle / 'catalogue.json').open('xb') as stream:
            os.chmod(bundle / 'catalogue.json', 0o600)
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        # mkdir is the exclusive publication boundary. Index arrives last, so a
        # process interruption leaves an unavailable bundle, never a partial list.
        output.mkdir(mode=0o700)
        (bundle / 'archives').rename(output / 'archives')
        if include_thumbnails:
            (bundle / 'pictures').rename(output / 'pictures')
        (bundle / 'catalogue.json').rename(output / 'catalogue.json')
    return {'entries': len(entries), 'archives': len(seen), 'bytes': total,
            'indexSha256': hashlib.sha256(encoded).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--thumbnails', action='store_true', help='Include attached history pictures in a version-two bundle')
    args = parser.parse_args()
    catalogue = None
    try:
        catalogue = history.Catalogue(args.catalogue)
        result = export(catalogue, args.output, include_thumbnails=args.thumbnails)
        print(f"Private save-copy bundle verified: {result['entries']} entries, {result['archives']} archives. No device changed.")
    except (ValueError, OSError):
        print('Save-copy export failed; prior history and existing outputs were kept.', file=__import__('sys').stderr)
        return 1
    finally:
        if catalogue:
            catalogue.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
