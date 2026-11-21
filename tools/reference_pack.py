"""Export an explicit, hash-pinned reference selection without fetching content."""
import argparse
import csv
import hashlib
import html
import io
import ipaddress
import json
import os
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit


MAX_INPUT = 1024 * 1024
MAX_ROWS = 4096
MAX_SELECTED = 32
REQUIRED_COLUMNS = {'id', 'title', 'url', 'read_status', 'read_scope'}
STATUSES = {'catalogued', 'read_partial', 'read_full'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def plain(value, limit):
    require(isinstance(value, str) and 0 < len(value) <= limit
            and value == value.strip() and not any(ord(c) < 32 or ord(c) == 127 for c in value),
            'Invalid reference text')
    return value


def public_url(value):
    """Check portable link syntax only; this does not verify remote availability."""
    plain(value, 2048)
    require(not any(c.isspace() for c in value) and '\\' not in value,
            'Invalid public URL')
    try:
        parts = urlsplit(value)
        host = parts.hostname or ''
        port = parts.port
    except ValueError:
        raise ValueError('Invalid public URL') from None
    require(parts.scheme == 'https' and not parts.username and not parts.password
            and port in (None, 443) and not parts.fragment,
            'Reference links require uncredentialed HTTPS without fragments')
    require(re.fullmatch(r'[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z][a-zA-Z0-9-]+', host) is not None
            and not host.lower().endswith(('.local', '.internal', '.localhost', '.lan', '.home', '.test')),
            'Reference links require a public DNS hostname')
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError('Reference links require a public DNS hostname')
    # Public video locators are supported, never signed download/auth queries.
    require(all(key in {'v', 't', 'start', 'page'} and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', val)
                for key, val in parse_qsl(parts.query, keep_blank_values=True)),
            'Reference URL query is not a supported public locator')
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate selection key')
        result[key] = value
    return result


def decode_selection(data):
    require(isinstance(data, bytes) and len(data) <= MAX_INPUT, 'Selection exceeds byte limit')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError):
        raise ValueError('Invalid selection JSON') from None


def make_pack(catalogue, selection):
    """Preserve selected catalogue claims, explicitly attributed to that snapshot."""
    require(isinstance(catalogue, bytes) and 0 < len(catalogue) <= MAX_INPUT,
            'Catalogue exceeds byte limit')
    require(isinstance(selection, dict) and set(selection) == {
        'schema', 'catalogue_sha256', 'catalogue_label', 'selected_ids'},
        'Selection requires schema, catalogue_sha256, catalogue_label and selected_ids')
    require(type(selection['schema']) is int and selection['schema'] == 1,
            'Unsupported selection schema')
    digest = hashlib.sha256(catalogue).hexdigest()
    require(selection['catalogue_sha256'] == digest, 'Catalogue differs from selected snapshot')
    label = plain(selection['catalogue_label'], 120)
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9 ._-]*', label) is not None,
            'Catalogue label must be portable text, without paths')
    ids = selection['selected_ids']
    require(isinstance(ids, list) and 0 < len(ids) <= MAX_SELECTED
            and all(isinstance(i, str) and re.fullmatch(r'[A-Za-z0-9_-]{1,100}', i) for i in ids),
            'Select between one and 32 explicit reference IDs')
    require(len(set(ids)) == len(ids), 'Duplicate selected reference ID')
    try:
        reader = csv.DictReader(io.StringIO(catalogue.decode('utf-8-sig'), newline=''))
        fields = reader.fieldnames or []
        require(REQUIRED_COLUMNS <= set(fields) and len(fields) == len(set(fields)),
                'Catalogue requires unique provenance columns')
        rows = {}
        count = 0
        for row in reader:
            count += 1
            require(count <= MAX_ROWS, 'Catalogue exceeds row limit')
            require(None not in row and all(v is not None for v in row.values()),
                    'Malformed catalogue row')
            identity = row['id']
            require(identity not in rows, 'Duplicate catalogue reference ID')
            rows[identity] = row
    except (UnicodeError, csv.Error):
        raise ValueError('Invalid catalogue CSV') from None
    items = []
    for identity in ids:
        require(identity in rows, 'Selected reference is absent from catalogue')
        row = rows[identity]
        require(row['read_status'] in STATUSES, 'Unknown retained read status')
        items.append({
            'id': identity, 'title': plain(row['title'], 500),
            'url': public_url(row['url']), 'read_status': row['read_status'],
            'read_scope': plain(row['read_scope'], 2000),
            'source': {'catalogue_label': label, 'catalogue_sha256': digest,
                       'catalogue_record_id': identity, 'provenance': 'retained_catalogue',
                       'reviewed_at': None, 'checked_live': False},
            'offline_content': 'not_included',
        })
    return {'schema': 'nova-reference-pack-v1', 'kind': 'link_index', 'items': items}


def render_index(pack):
    cards = []
    for item in pack['items']:
        escape = html.escape
        source = item['source']
        cards.append('<li><h2><a href="{}" rel="noreferrer">{}</a></h2>'
                     '<p>Retained status: <strong>{}</strong></p><p>{}</p>'
                     '<p>Source: {} · record {} · SHA-256 <code>{}</code></p></li>'.format(
                         escape(item['url'], quote=True), escape(item['title']),
                         escape(item['read_status']), escape(item['read_scope']),
                         escape(source['catalogue_label']), escape(item['id']),
                         escape(source['catalogue_sha256'])))
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
            'style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">'
            '<title>Selected references</title><style>body{font:18px/1.5 system-ui;'
            'max-width:48rem;margin:2rem auto;padding:0 1rem}li{margin:2rem 0}'
            'code{overflow-wrap:anywhere}a{color:#235b95}</style><body>'
            '<h1>Selected references</h1><p>Offline link index only. Linked talks, videos, '
            'articles and assets are not included; opening them requires connectivity. '
            'Read statuses are retained catalogue claims, not a fresh review. '
            'Catalogued means listed only. A full read covers only its stated read scope, '
            'not necessarily the complete audiovisual work. Review dates are unknown; '
            'links were not checked live.</p><ol>' + ''.join(cards) + '</ol></body></html>')


def read_input(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(),
            'Input must be a regular file without linked ancestors')
    with path.open('rb') as stream:
        data = stream.read(MAX_INPUT + 1)
    require(len(data) <= MAX_INPUT, 'Input exceeds byte limit')
    return data


def export_pack(catalogue_path, selection_path, destination):
    # Validate all selected data before creating anything; existing packs are immutable.
    pack = make_pack(read_input(catalogue_path), decode_selection(read_input(selection_path)))
    outputs = {'index.html': render_index(pack),
               'pack.json': json.dumps(pack, ensure_ascii=False, indent=2) + '\n'}
    destination = Path(destination).absolute()
    require('..' not in destination.parts and destination.parent.is_dir()
            and not any(p.is_symlink() for p in (destination, *destination.parents)),
            'Output needs an existing parent without links')
    require(not destination.exists(), 'Output already exists; preserve it')
    destination.mkdir(mode=0o700)
    # Keep failed output for review: another writer may have added files after mkdir.
    # The data manifest follows its index; existing/partial outputs are never adopted.
    for name, content in outputs.items():
        with (destination / name).open('x', encoding='utf-8') as stream:
            os.chmod(destination / name, 0o600)
            stream.write(content)
    return pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalogue', required=True)
    parser.add_argument('--selection', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    try:
        pack = export_pack(args.catalogue, args.selection, args.output)
    except (OSError, ValueError):
        parser.exit(2, 'Reference pack refused; check input schema, hash, selection and new output path.\n')
    print(json.dumps({'items': len(pack['items']), 'kind': pack['kind'],
                      'downloaded': False, 'checked_live': False}))


if __name__ == '__main__':
    main()
