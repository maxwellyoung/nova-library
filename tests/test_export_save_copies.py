import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import struct
import zlib
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import export_save_copies as exporter
import save_catalogue as history
import save_passport as passport


class SaveCopyExport(unittest.TestCase):
    def picture(self, colour=b'\x10\x20\x30'):
        def chunk(kind, data):
            return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
        data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\0'+colour))+chunk(b'IEND',b'')
        path=self.root/('picture-'+hashlib.sha256(data).hexdigest()+'.png');path.write_bytes(data);path.chmod(0o600)
        return path

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.root.chmod(0o700)
        source = self.root / 'source'; source.mkdir()
        (source / 'save.sav').write_bytes(b'synthetic recoverable progress')
        self.selection = {'schemaVersion':1, 'editionId':'demo:orbit', 'recipeId':'fixture.v1',
                          'kind':'native-save', 'runtime':{'name':'Fixture', 'version':'1.0', 'core':'standalone'},
                          'files':['save.sav']}
        self.archive = self.root / 'source.nvs'
        passport.pack(source, self.selection, self.archive, source_idle=True)
        self.catalogue = history.Catalogue(self.root / 'history', create=True)
        self.output = self.root / 'bundle'

    def tearDown(self):
        self.catalogue.close(); self.temp.cleanup()

    def test_export_rechecks_real_archives_keeps_names_and_pins_and_preserves_source(self):
        self.catalogue.import_passport(self.archive, name='Before the lift', pinned=True)
        before = self.catalogue.list_entries()
        result = exporter.export(self.catalogue, self.output)
        index = json.loads((self.output / 'catalogue.json').read_text())
        self.assertEqual(result['entries'], 1)
        row = index['entries'][0]
        self.assertEqual(row['name'], 'Before the lift'); self.assertTrue(row['pinned'])
        self.assertEqual(row['identity']['editionId'], 'demo:orbit')
        copied = self.output / 'archives' / (row['sha256'] + '.nvs')
        self.assertEqual(copied.read_bytes(), self.archive.read_bytes())
        self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), row['sha256'])
        self.assertEqual(len(passport.verify(copied)['files']), row['files'])
        self.assertEqual(self.catalogue.list_entries(), before)
        self.assertNotIn(str(self.root), (self.output / 'catalogue.json').read_text())
        self.assertEqual((self.output.stat().st_mode & 0o777), 0o700)
        self.assertEqual(((self.output / 'catalogue.json').stat().st_mode & 0o777), 0o600)
        self.assertEqual((copied.stat().st_mode & 0o777), 0o600)

    def test_identical_archives_deduplicate_without_collapsing_named_entries(self):
        self.catalogue.import_passport(self.archive, name='First', pinned=True)
        self.catalogue.import_passport(self.archive, name='Second', pinned=True)
        result = exporter.export(self.catalogue, self.output)
        self.assertEqual((result['entries'], result['archives']), (2,1))
        rows = json.loads((self.output / 'catalogue.json').read_text())['entries']
        self.assertEqual([r['name'] for r in rows], ['Second','First'])
        self.assertNotEqual(rows[0]['checkpointId'], rows[1]['checkpointId'])

    def test_opt_in_pictures_keep_exact_checkpoint_association_and_original_archives(self):
        a=self.picture();b=self.picture(b'\xff\x80\x40')
        first=self.catalogue.import_passport(self.archive,name='First',thumbnail_path=a)
        second=self.catalogue.import_passport(self.archive,name='Second',thumbnail_path=b)
        before=self.catalogue.list_entries()
        result=exporter.export(self.catalogue,self.output,include_thumbnails=True)
        index=json.loads((self.output/'catalogue.json').read_text());self.assertEqual(index['schemaVersion'],2)
        self.assertEqual(index['source'],'verified-passport-export-v2')
        rows={r['checkpointId']:r for r in index['entries']}
        for ref,path in [(first,a),(second,b)]:
            pic=rows[ref['checkpointId']]['picture'];self.assertEqual(pic,{'state':'available','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bytes':path.stat().st_size})
            target=self.output/'pictures'/(pic['sha256']+'.png');self.assertEqual(target.read_bytes(),path.read_bytes());self.assertEqual(target.stat().st_mode&0o777,0o600)
        self.assertEqual(result['archives'],1);self.assertEqual(result['bytes'],self.archive.stat().st_size+a.stat().st_size+b.stat().st_size)
        self.assertEqual(self.catalogue.list_entries(),before)

    def test_picture_deduplication_and_unavailable_images_do_not_invent_screenshots(self):
        path=self.picture()
        for name in ['One','Two']:self.catalogue.import_passport(self.archive,name=name,thumbnail_path=path)
        self.catalogue.import_passport(self.archive,name='Missing')
        broken=self.root/'broken.png';broken.write_bytes(b'not an image')
        self.catalogue.import_passport(self.archive,name='Invalid',thumbnail_path=broken)
        exporter.export(self.catalogue,self.output,include_thumbnails=True)
        rows={r['name']:r for r in json.loads((self.output/'catalogue.json').read_text())['entries']}
        self.assertEqual(rows['One']['picture'],rows['Two']['picture']);self.assertEqual(len(list((self.output/'pictures').iterdir())),1)
        self.assertEqual(rows['Missing']['picture'],{'state':'missing'});self.assertEqual(rows['Invalid']['picture'],{'state':'unavailable'})

    def test_picture_drift_and_resource_budget_refuse_before_publication(self):
        path=self.picture();self.catalogue.import_passport(self.archive,thumbnail_path=path)
        with mock.patch.object(self.catalogue,'thumbnail',return_value=None):
            with self.assertRaises(passport.PassportError):exporter.export(self.catalogue,self.output,include_thumbnails=True)
        with mock.patch.object(exporter,'MAX_BYTES',self.archive.stat().st_size+path.stat().st_size-1):
            with self.assertRaises(passport.PassportError):exporter.export(self.catalogue,self.output,include_thumbnails=True)
        self.assertFalse(self.output.exists());self.assertFalse(any(p.name.startswith('.save-copies-') for p in self.root.iterdir()))

    def test_default_export_remains_compatible_with_the_frozen_diagnostic_reader(self):
        self.catalogue.import_passport(self.archive,thumbnail_path=self.picture())
        exporter.export(self.catalogue,self.output)
        index=json.loads((self.output/'catalogue.json').read_text());self.assertEqual(index['schemaVersion'],1)
        self.assertNotIn('picture',index['entries'][0]);self.assertFalse((self.output/'pictures').exists())

    def test_empty_export_is_explicit_and_does_not_invent_a_copy(self):
        self.assertEqual(exporter.export(self.catalogue, self.output)['entries'], 0)
        self.assertEqual(json.loads((self.output / 'catalogue.json').read_text())['entries'], [])

    def test_trash_is_excluded_without_erasing_catalogue_history(self):
        ref = self.catalogue.import_passport(self.archive)
        self.catalogue.apply(self.catalogue.plan_delete([ref['checkpointId']]))
        self.assertEqual(exporter.export(self.catalogue, self.output)['entries'], 0)
        self.assertEqual(len(self.catalogue.list_entries(include_trash=True)), 1)

    def test_changed_history_and_corrupt_archive_are_not_published(self):
        ref = self.catalogue.import_passport(self.archive)
        original = self.catalogue.list_entries
        count = [0]
        def changing():
            count[0] += 1
            rows = original()
            if count[0]>1: rows[0]['name']='changed'
            return rows
        with mock.patch.object(self.catalogue, 'list_entries', side_effect=changing):
            with self.assertRaises(passport.PassportError): exporter.export(self.catalogue, self.output)
        self.assertFalse(self.output.exists())
        self.catalogue.db.execute('UPDATE records SET archive=? WHERE id=?', (b'corrupt',ref['checkpointId']))
        self.catalogue.db.commit()
        with self.assertRaises(passport.PassportError): exporter.export(self.catalogue, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_and_competing_outputs_are_preserved(self):
        self.output.mkdir(); (self.output / 'keep').write_bytes(b'owner copy')
        with self.assertRaises(ValueError): exporter.export(self.catalogue, self.output)
        self.assertEqual((self.output / 'keep').read_bytes(), b'owner copy')

    def test_competing_directory_created_before_publication_is_kept(self):
        self.catalogue.import_passport(self.archive)
        original = self.catalogue.list_entries
        count = [0]
        def compete():
            count[0] += 1
            rows = original()
            if count[0] == 2:
                self.output.mkdir()
                (self.output / 'keep').write_bytes(b'other writer')
            return rows
        with mock.patch.object(self.catalogue, 'list_entries', side_effect=compete):
            with self.assertRaises(FileExistsError): exporter.export(self.catalogue, self.output)
        self.assertEqual((self.output / 'keep').read_bytes(), b'other writer')
        self.assertFalse((self.output / 'catalogue.json').exists())

    def test_resource_limits_fail_before_publishing_a_bundle(self):
        self.catalogue.import_passport(self.archive)
        with mock.patch.object(exporter, 'MAX_BYTES', 1):
            with self.assertRaises(passport.PassportError): exporter.export(self.catalogue, self.output)
        self.assertFalse(self.output.exists())
        with mock.patch.object(exporter, 'MAX_ENTRIES', 0):
            with self.assertRaises(passport.PassportError): exporter.export(self.catalogue, self.output)
        self.assertFalse(self.output.exists())
        self.assertFalse(any(p.name.startswith('.save-copies-') for p in self.root.iterdir()))


if __name__ == '__main__': unittest.main()
