"""Apply explicit, edition-scoped cover repairs to an exporter candidate.

No network requests, title matching or catalogue publication happen here.
Assets are content addressed so a later export failure cannot change the bytes
behind a previously published cover path.
"""
import hashlib
import os
from pathlib import Path
import re


MAX_BYTES = 1024 * 1024
MAX_TOTAL_BYTES = 32 * 1024 * 1024


def _image_suffix(data):
    # This is a format signature check, not a decoder or a visual-quality check.
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        return '.png'
    if data.startswith(b'\xff\xd8\xff'):
        return '.jpg'
    if len(data) >= 12 and data[:4] == b'RIFF' and data[8:12] == b'WEBP':
        return '.webp'
    raise ValueError('Cover repair needs a PNG, JPEG or WebP signature')


def apply_repairs(records, repairs, input_root, output_root):
    """Validate every applicable repair, then copy pinned art and update records.

    Missing editions stay in the input manifest for a later refresh. Duplicate
    matching editions are refused. Unknown keys and unpinned replacements fail
    closed; existing records and asset bytes are kept on validation failure.
    """
    if not isinstance(repairs, dict) or len(repairs) > 4096:
        raise ValueError('Cover repairs need a bounded edition mapping')
    input_root, output_root = Path(input_root).resolve(), Path(output_root).resolve()
    if not input_root.is_dir() or not output_root.is_dir():
        raise ValueError('Cover repair roots must already exist')
    indexed = {}
    for record in records:
        indexed.setdefault(record.get('edition'), []).append(record)
    pending, total = [], 0
    for edition, repair in repairs.items():
        if not isinstance(edition, str) or not re.fullmatch(r'[A-Za-z0-9:_-]{1,256}', edition):
            raise ValueError('Invalid cover repair edition')
        if not isinstance(repair, dict) or set(repair) != {'path', 'sha256', 'source', 'mode'}:
            raise ValueError('Cover repair requires path, sha256, source and mode')
        relative, digest, source, mode = (repair[k] for k in ('path', 'sha256', 'source', 'mode'))
        if not isinstance(relative, str) or not relative or '\\' in relative or '\x00' in relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
            raise ValueError('Cover repair path must stay inside input')
        if not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest):
            raise ValueError('Cover repair requires a lowercase SHA256')
        if not isinstance(source, str) or not source.strip() or len(source) > 500 or any(ord(c) < 32 or ord(c) == 127 for c in source):
            raise ValueError('Cover repair requires a plain source citation')
        if mode not in ('replace', 'fill'):
            raise ValueError('Cover repair mode must be replace or fill')
        matches = indexed.get(edition, [])
        if len(matches) > 1:
            raise ValueError('Ambiguous cover repair edition')
        if not matches or (mode == 'fill' and matches[0].get('art')):
            continue
        path = (input_root / relative).resolve()
        if not path.is_relative_to(input_root) or not path.is_file() or not 0 < path.stat().st_size <= MAX_BYTES:
            raise ValueError('Cover repair source unavailable or outside its byte limit')
        with path.open('rb') as stream:
            data = stream.read(MAX_BYTES + 1)
        if not 0 < len(data) <= MAX_BYTES or hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Cover repair bytes differ from the pinned image')
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('Cover repairs exceed the total byte limit')
        suffix = _image_suffix(data)
        if path.suffix.lower() not in ({'.jpg', '.jpeg'} if suffix == '.jpg' else {suffix}):
            raise ValueError('Cover repair extension differs from its signature')
        edition_hash = hashlib.sha256(edition.encode()).hexdigest()
        art = 'art/repair-' + edition_hash + '-' + digest + suffix
        destination = output_root / art
        parent = destination.parent
        if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
            raise ValueError('Cover repair asset directory is unsafe')
        if destination.is_symlink() or (destination.exists() and (not destination.is_file() or destination.stat().st_size != len(data) or destination.read_bytes() != data)):
            raise ValueError('Existing cover repair asset differs; preserve it')
        pending.append((matches[0], destination, art, data, source.strip(), digest))
    # All inputs and existing targets were checked before any record is changed.
    for _, destination, _, data, _, _ in pending:
        destination.parent.mkdir(exist_ok=True)
        if destination.exists():
            if destination.is_symlink() or destination.stat().st_size != len(data) or destination.read_bytes() != data:
                raise ValueError('Cover repair target changed during export')
            continue
        try:
            with destination.open('xb') as stream:
                os.chmod(destination, 0o600)
                stream.write(data)
        except FileExistsError:
            raise ValueError('Cover repair target appeared during export') from None
    for record, _, art, _, source, digest in pending:
        record.update(art=art, artwork_source=source, artwork_sha256=digest)
    return len(pending)
