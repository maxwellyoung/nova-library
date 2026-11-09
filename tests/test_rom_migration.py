from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import rom_migration as m


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.source=self.root/'roms';self.source.mkdir();(self.source/'game.bin').write_bytes(b'original ROM');self.entries=[{'editionId':'fixture:edition','path':'game.bin'}]
    def tearDown(self):self.tmp.cleanup()
    def test_copy_and_fresh_process_style_verification_keep_originals_and_identity(self):
        plan=m.plan(self.source,self.entries);out=self.root/'card';r=m.copy(plan,out,approved_digest=plan['planSha256']);self.assertEqual(m.verify(out),r)
        self.assertEqual((self.source/'game.bin').read_bytes(),(out/'game.bin').read_bytes());self.assertFalse(r['historyIdentityChanged']);self.assertFalse(r['catalogueChanged'])
    def test_changed_source_or_plan_refuses_before_destination_creation(self):
        p=m.plan(self.source,self.entries);(self.source/'game.bin').write_bytes(b'changed')
        with self.assertRaises(m.MigrationError):m.copy(p,self.root/'card',approved_digest=p['planSha256'])
        self.assertFalse((self.root/'card').exists())
        with self.assertRaises(m.MigrationError):m.copy(p,self.root/'card',approved_digest='wrong')
    def test_linked_overlapping_paths_and_existing_destination_refuse(self):
        (self.source/'link.bin').symlink_to(self.source/'game.bin')
        with self.assertRaises(ValueError):m.plan(self.source,[{'editionId':'fixture:a','path':'link.bin'}])
        with self.assertRaises(ValueError):m.plan(self.source,self.entries+self.entries)
        p=m.plan(self.source,self.entries)
        with self.assertRaises(m.MigrationError):m.copy(p,self.source,approved_digest=p['planSha256'])
    def test_interrupted_copy_stays_incomplete_and_keeps_source(self):
        p=m.plan(self.source,self.entries)
        original=m.file_hash(self.source/'game.bin')
        with patch.object(m,'file_hash',side_effect=[original,(12,'wrong')]):
            with self.assertRaises(m.MigrationError):m.copy(p,self.root/'card',approved_digest=p['planSha256'])
        self.assertTrue((self.source/'game.bin').exists());self.assertTrue((self.root/'card/MIGRATION-INCOMPLETE').exists())
        with self.assertRaises(m.MigrationError):m.verify(self.root/'card')
    def test_changed_copy_never_verifies_and_saves_are_not_selected_implicitly(self):
        (self.source/'memory.srm').write_bytes(b'precious save');p=m.plan(self.source,self.entries);out=self.root/'card';m.copy(p,out,approved_digest=p['planSha256'])
        self.assertFalse((out/'memory.srm').exists());(out/'game.bin').write_bytes(b'wrong')
        with self.assertRaises(m.MigrationError):m.verify(out)

    def test_explicit_resume_validates_prefix_and_uses_same_edition_plan(self):
        p=m.plan(self.source,self.entries);out=self.root/'card';out.mkdir();(out/'MIGRATION-INCOMPLETE').write_text(p['planSha256']+'\n');(out/'game.bin').write_bytes(b'original')
        result=m.copy(p,out,approved_digest=p['planSha256'],resume=True);self.assertEqual(m.verify(out),result)
        self.assertEqual(m.copy(p,out,approved_digest=p['planSha256'],resume=True),result)
    def test_changed_partial_prefix_or_unmanaged_file_is_preserved_and_refused(self):
        p=m.plan(self.source,self.entries);out=self.root/'card';out.mkdir();(out/'MIGRATION-INCOMPLETE').write_text(p['planSha256']+'\n');(out/'game.bin').write_bytes(b'wrong')
        with self.assertRaises(m.MigrationError):m.copy(p,out,approved_digest=p['planSha256'],resume=True)
        self.assertEqual((out/'game.bin').read_bytes(),b'wrong');self.assertTrue((out/'MIGRATION-INCOMPLETE').exists())
        (out/'precious.txt').write_text('keep')
        with self.assertRaises(m.MigrationError):m.copy(p,out,approved_digest=p['planSha256'],resume=True)
        self.assertEqual((out/'precious.txt').read_text(),'keep')
