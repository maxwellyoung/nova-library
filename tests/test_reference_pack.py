import copy
import csv
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import reference_pack as refs


def catalogue(rows):
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=[
        'id', 'title', 'url', 'read_status', 'read_scope', 'private_extra'])
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode()


class ReferencePacks(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {'id': 'deck', 'title': 'Synthetic deck', 'url': 'https://example.org/deck.pdf',
             'read_status': 'read_full', 'read_scope': 'All 4 slides; spoken talk not read',
             'private_extra': 'NEVER_EXPORT_THIS'},
            {'id': 'listing', 'title': 'Synthetic article', 'url': 'https://example.org/article',
             'read_status': 'catalogued', 'read_scope': 'Listing only; content not read'},
            {'id': 'partial', 'title': 'Synthetic video', 'url': 'https://example.org/watch?v=sample',
             'read_status': 'read_partial', 'read_scope': 'Captions 0:00-1:00 only; no video viewing'},
        ]
        self.data = catalogue(self.rows)
        self.selection = {'schema': 1, 'catalogue_sha256': hashlib.sha256(self.data).hexdigest(),
                          'catalogue_label': 'Synthetic public reference catalogue',
                          'selected_ids': ['listing', 'deck', 'partial']}
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.csv = self.root / 'talks.csv'
        self.csv.write_bytes(self.data)
        self.selection_path = self.root / 'selection.json'
        self.selection_path.write_text(json.dumps(self.selection))

    def make(self, rows=None, selection=None):
        data = self.data if rows is None else catalogue(rows)
        selected = copy.deepcopy(self.selection if selection is None else selection)
        if rows is not None:
            selected['catalogue_sha256'] = hashlib.sha256(data).hexdigest()
        return refs.make_pack(data, selected)

    def test_preserves_retained_scopes_order_and_unknown_review_dates(self):
        pack = self.make()
        self.assertEqual([x['id'] for x in pack['items']], ['listing', 'deck', 'partial'])
        for item in pack['items']:
            row = next(r for r in self.rows if r['id'] == item['id'])
            self.assertEqual(item['read_status'], row['read_status'])
            self.assertEqual(item['read_scope'], row['read_scope'])
            self.assertEqual(item['source']['provenance'], 'retained_catalogue')
            self.assertIsNone(item['source']['reviewed_at'])
            self.assertIs(item['source']['checked_live'], False)
            self.assertEqual(item['offline_content'], 'not_included')

    def test_only_selected_allowlisted_fields_leave_catalogue(self):
        self.selection['selected_ids'] = ['deck']
        text = json.dumps(self.make())
        self.assertNotIn('Synthetic article', text)
        self.assertNotIn('NEVER_EXPORT_THIS', text)
        self.assertNotIn('private_extra', text)
        self.assertNotIn(str(self.root), text)

    def test_hash_changes_missing_duplicate_and_empty_selection_refuse(self):
        for values in [[], ['missing'], ['deck', 'deck'], ['../deck'], ['deck'] * 33, 'deck']:
            with self.subTest(values=values):
                selected = dict(self.selection, selected_ids=values)
                with self.assertRaises(ValueError): self.make(selection=selected)
        with self.assertRaises(ValueError):
            refs.make_pack(self.data + b'\n', self.selection)
        with self.assertRaises(ValueError): self.make(rows=self.rows + [self.rows[0]])

    def test_selection_cannot_override_review_status_or_add_assets(self):
        for key, value in [('read_status', 'read_full'), ('assets', ['deck.pdf']),
                           ('reviewed_at', '2026-11-11')]:
            with self.assertRaises(ValueError): self.make(selection=dict(self.selection, **{key: value}))
        for schema in [True, 2, '1']:
            with self.assertRaises(ValueError): self.make(selection=dict(self.selection, schema=schema))
        with self.assertRaises(ValueError):
            refs.decode_selection(b'{"schema":1,"schema":1}')

    def test_selected_invalid_urls_refuse_without_creating_output(self):
        urls = ['file:///private/file', 'javascript:alert(1)', 'http://example.org/a',
                'https://user:secret' + '@' + 'example.org/a', 'https://localhost/a',
                'https://127.0.0.1/a', 'https://' + '.'.join(map(str, [192, 168, 1, 1])) + '/a', 'https://[::1]/a',
                'https://127.1/a', 'https://0x7f.1/a', 'https://0177.0.0.1/a',
                'https://host.local/a', 'https://host.internal/a',
                'https://example.org/a?token=secret', 'https://example.org/a#token=secret',
                'https://example.org:8443/a', 'https://example.org/a\nb',
                'https://example.org\\evil/a']
        for url in urls:
            with self.subTest(url=url):
                rows = copy.deepcopy(self.rows); rows[0]['url'] = url
                with self.assertRaises(ValueError): self.make(rows=rows)
        self.assertFalse((self.root / 'pack').exists())

    def test_invalid_status_scope_and_malformed_or_oversized_input_refuse(self):
        for key, value in [('read_status', 'reviewed'), ('read_scope', ''),
                           ('read_scope', 'x' * 2001), ('title', 'hello\nworld')]:
            rows = copy.deepcopy(self.rows); rows[0][key] = value
            with self.assertRaises(ValueError): self.make(rows=rows)
        for data in [b'\xff', b'id,title\nx,y\n', b'x' * (refs.MAX_INPUT + 1),
                     b'id,title,url,read_status,read_scope\na,b,c,d,e,EXTRA\n']:
            selected = dict(self.selection, catalogue_sha256=hashlib.sha256(data).hexdigest())
            with self.assertRaises(ValueError): refs.make_pack(data, selected)

    def test_index_escapes_text_has_no_external_assets_or_scripts(self):
        rows = copy.deepcopy(self.rows)
        rows[0]['title'] = '<script>alert("synthetic")</script>'
        pack = self.make(rows=rows)
        output = refs.render_index(pack)
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__(); self.tags = []
            def handle_starttag(self, tag, attrs):
                self.tags.append((tag, dict(attrs)))
        parsed = Tags(); parsed.feed(output)
        self.assertFalse(any(tag in {'script', 'img', 'iframe', 'video', 'audio', 'link'}
                             for tag, _ in parsed.tags))
        self.assertEqual([attrs['href'] for tag, attrs in parsed.tags if tag == 'a'],
                         [item['url'] for item in pack['items']])
        self.assertIn('&lt;script&gt;', output)
        self.assertIn('Catalogued means listed only', output)
        self.assertIn('not a fresh review', output)
        self.assertIn('requires connectivity', output)

    def test_cli_real_export_is_deterministic_and_existing_output_is_preserved(self):
        cli = Path(refs.__file__)
        first = self.root / 'one'; second = self.root / 'two'
        for destination in [first, second]:
            result = subprocess.run([sys.executable, str(cli), '--catalogue', str(self.csv),
                                     '--selection', str(self.selection_path), '--output', str(destination)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {
                'items': 3, 'kind': 'link_index', 'downloaded': False, 'checked_live': False})
        self.assertEqual(sorted(p.name for p in first.iterdir()), ['index.html', 'pack.json'])
        for name in ['index.html', 'pack.json']:
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())
            self.assertEqual((first / name).stat().st_mode & 0o777, 0o600)
        before = {p.name: p.read_bytes() for p in first.iterdir()}
        with self.assertRaises(ValueError): refs.export_pack(self.csv, self.selection_path, first)
        self.assertEqual(before, {p.name: p.read_bytes() for p in first.iterdir()})

    def test_failed_export_preserves_newly_arriving_files(self):
        original_open = Path.open
        for failed_name in ['index.html', 'pack.json']:
            with self.subTest(failed_name=failed_name):
                output = self.root / ('failed-' + failed_name)
                def interrupted_open(path, *args, **kwargs):
                    if path == output / failed_name:
                        (output / 'arrived.txt').write_text('another writer', encoding='utf-8')
                        raise OSError('synthetic output failure')
                    return original_open(path, *args, **kwargs)
                with mock.patch.object(Path, 'open', interrupted_open):
                    with self.assertRaises(OSError):
                        refs.export_pack(self.csv, self.selection_path, output)
                self.assertEqual((output / 'arrived.txt').read_text(), 'another writer')
                self.assertFalse((output / 'pack.json').exists())

    def test_no_partial_pack_on_validation_failure_and_linked_paths_refuse(self):
        bad = dict(self.selection, selected_ids=['deck', 'missing'])
        self.selection_path.write_text(json.dumps(bad))
        output = self.root / 'bad'
        with self.assertRaises(ValueError): refs.export_pack(self.csv, self.selection_path, output)
        self.assertFalse(output.exists())
        self.selection_path.write_text(json.dumps(self.selection))
        linked = self.root / 'link.csv'; linked.symlink_to(self.csv)
        with self.assertRaises(ValueError): refs.export_pack(linked, self.selection_path, output)
        directory = self.root / 'linked'; directory.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): refs.export_pack(self.csv, self.selection_path, directory / 'out')
        self.assertFalse((self.root / 'out').exists())


if __name__ == '__main__':
    unittest.main()
