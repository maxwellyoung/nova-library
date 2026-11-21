from pathlib import Path
import copy
import json
import os
import subprocess
import sys
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


class RouteCandidateTests(unittest.TestCase):
    setUp=MigrationTests.setUp
    tearDown=MigrationTests.tearDown
    def fixture(self, *, playlist=False):
        if playlist:
            (self.source/'disc2.bin').write_bytes(b'second synthetic disc')
            (self.source/'set.m3u').write_text('# Stable playlist name\ngame.bin\ndisc2.bin\n')
            self.entries=[{'editionId':'fixture:edition','path':name} for name in ('set.m3u','game.bin','disc2.bin')]
        self.copy_plan=m.plan(self.source,self.entries);self.out=self.root/'card'
        m.copy(self.copy_plan,self.out,approved_digest=self.copy_plan['planSha256'])
        self.saves=self.root/'saves';self.saves.mkdir();(self.saves/'progress.srm').write_bytes(b'precious progress')
        name='set.m3u' if playlist else 'game.bin'
        self.catalogue=self.root/'metadata.txt'
        self.text=('collection: Fixture\nlaunch: emulator "{file.path}"\n\n'
                   'game: Synthetic game\nfile: '+str(self.source/name)+'\n'
                   'x-edition-id: fixture:edition\nx-disc-set-id: fixture:family\n'
                   'x-launchable: false\nx-story: Keep original note\nx-progress-state: playing\n'
                   'x-last-played: 2026-11-10\nx-favorite: true\n\n'
                   'game: Same title, different edition\nfile: untouched.bin\n'
                   'x-edition-id: fixture:other\nx-story: Unrelated note\n')
        self.catalogue.write_text(self.text)
        self.selections=[{'editionId':'fixture:edition','path':name,'familyPaths':[f['path'] for f in self.entries],
                          'saveBinding':{'mode':'explicit-independent-directory','directory':str(self.saves),
                          'evidence':'Synthetic fixture adapter declaration; no emulator tested',
                          'identity':{'editionId':'fixture:edition','recipeId':'fixture.runtime.v1','kind':'native-save',
                                      'runtime':{'name':'fixture','version':'1','core':'fixture-core'}}}}]
        return m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)

    def review(self,value):
        return m.review_routes(value,approved_digest=value['routePlanSha256'])

    def test_candidate_changes_only_exact_file_route_and_supplies_original_rollback(self):
        p=self.fixture();r=self.review(p)
        self.assertEqual(r['candidate'],self.text.replace('file: '+str(self.source/'game.bin')+'\n','file: '+str(self.out/'game.bin')+'\n'))
        self.assertEqual(r['rollback'],self.text);self.assertEqual(self.catalogue.read_text(),self.text)
        self.assertFalse(r['catalogueChanged']);self.assertFalse(r['runtimeSaveContinuityVerified'])
        self.assertEqual((self.saves/'progress.srm').read_bytes(),b'precious progress')
        self.assertEqual((self.source/'game.bin').read_bytes(),b'original ROM')

    def test_playlist_name_members_and_edition_family_are_retained_byte_for_byte(self):
        p=self.fixture(playlist=True);r=self.review(p)
        self.assertIn('file: '+str(self.out/'set.m3u'),r['candidate'])
        self.assertEqual((self.source/'set.m3u').read_bytes(),(self.out/'set.m3u').read_bytes())
        self.assertEqual(p['changes'][0]['familyPaths'],['set.m3u','game.bin','disc2.bin'])
        self.assertIn('x-disc-set-id: fixture:family',r['candidate'])

    def test_partial_or_missing_receipt_never_generates_a_route(self):
        self.fixture();marker=self.out/'MIGRATION-INCOMPLETE';marker.write_text(self.copy_plan['planSha256']+'\n')
        with self.assertRaises(ValueError):m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)
        marker.unlink();(self.out/'migration-receipt.json').unlink()
        with self.assertRaises(OSError):m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)

    def test_tampered_or_subset_receipt_cannot_adopt_plan_digest(self):
        self.fixture(playlist=True);receipt_path=self.out/'migration-receipt.json'
        receipt=json.loads(receipt_path.read_text());receipt['files']=receipt['files'][:1];receipt_path.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)
        with self.assertRaises(ValueError):m.copy(self.copy_plan,self.out,approved_digest=self.copy_plan['planSha256'],resume=True)

    def test_same_byte_source_destination_and_catalogue_replacements_stale_the_review(self):
        p=self.fixture()
        for path in (self.source/'game.bin',self.out/'game.bin',self.catalogue,self.out/'migration-receipt.json'):
            with self.subTest(path=path.name):
                backup=path.with_name(path.name+'.replacement');backup.write_bytes(path.read_bytes());os.replace(backup,path)
                with self.assertRaises(ValueError):self.review(p)
                p=m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)

    def test_replaced_save_directory_and_content_edits_stale_the_review(self):
        p=self.fixture();self.saves.rename(self.root/'original-saves');self.saves.mkdir()
        with self.assertRaises(ValueError):self.review(p)
        p=m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)
        (self.source/'game.bin').write_bytes(b'changed source')
        with self.assertRaises(ValueError):self.review(p)

    def test_changed_destination_catalogue_and_digest_refuse(self):
        p=self.fixture();self.catalogue.write_text(self.text+'# new export\n')
        with self.assertRaises(ValueError):self.review(p)
        self.catalogue.write_text(self.text);p=m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)
        (self.out/'game.bin').write_bytes(b'changed copy')
        with self.assertRaises(ValueError):self.review(p)
        with self.assertRaises(ValueError):m.review_routes(p,approved_digest='0'*64)
        altered=copy.deepcopy(p);altered['after']='invented route'
        with self.assertRaises(ValueError):self.review(altered)

    def test_ambiguous_records_source_routes_or_launch_adapters_refuse(self):
        self.fixture()
        variants=[self.text.replace('fixture:other','fixture:edition'),
                  self.text.replace('file: '+str(self.source/'game.bin'),'file: game.bin'),
                  self.text.replace('x-edition-id: fixture:edition','x-edition-id: fixture:edition\nx-edition-id: fixture:edition'),
                  self.text.replace('file: '+str(self.source/'game.bin'),'file: '+str(self.source/'game.bin')+'\nfile: other.bin'),
                  self.text.replace('{file.path}','hardcoded.bin'),
                  self.text.replace('emulator "{file.path}"','emulator '+str(self.source)+' "{file.path}"'),
                  self.text.replace('x-edition-id: fixture:edition','x-edition-id: fixture:edition\n continued'),
                  self.text+'collection: Another collection\n']
        for text in variants:
            with self.subTest(text=text[-60:]):
                self.catalogue.write_text(text)
                with self.assertRaises(ValueError):m.route_plan(self.copy_plan,self.out,self.catalogue,self.selections)

    def test_unknown_content_relative_mismatched_or_nested_save_paths_refuse(self):
        self.fixture()
        for field,value in [('mode','unknown'),('directory',str(self.source)),('directory',str(self.out/'folder')),
                            ('directory',str(self.root)),('directory','saves'),('evidence',''),('evidence','unknown')]:
            with self.subTest(field=field,value=value):
                selected=copy.deepcopy(self.selections);selected[0]['saveBinding'][field]=value
                with self.assertRaises((ValueError,OSError)):m.route_plan(self.copy_plan,self.out,self.catalogue,selected)
        selected=copy.deepcopy(self.selections);selected[0]['saveBinding']['identity']['editionId']='fixture:other'
        with self.assertRaises(ValueError):m.route_plan(self.copy_plan,self.out,self.catalogue,selected)
        selected=copy.deepcopy(self.selections);selected[0]['saveBinding']['identity']['runtime']['core']='unknown'
        with self.assertRaises(ValueError):m.route_plan(self.copy_plan,self.out,self.catalogue,selected)

    def test_path_escape_and_incomplete_or_mismatched_families_refuse(self):
        self.fixture(playlist=True)
        for family in [['set.m3u'],['set.m3u','../game.bin'],['set.m3u','game.bin','disc2.bin','unknown.bin'],
                       ['set.m3u','game.bin','game.bin']]:
            with self.subTest(family=family):
                selected=copy.deepcopy(self.selections);selected[0]['familyPaths']=family
                with self.assertRaises(ValueError):m.route_plan(self.copy_plan,self.out,self.catalogue,selected)
        for content in ['../escape.bin\n','/absolute.bin\n','game.bin\n','game.bin\ngame.bin\n','https://host/game.bin\n']:
            with self.subTest(content=content):
                (self.source/'set.m3u').write_text(content);(self.out/'set.m3u').write_text(content)
                plan=m.plan(self.source,self.entries);receipt=json.loads((self.out/'migration-receipt.json').read_text())
                receipt['planSha256']=plan['planSha256'];receipt['files']=plan['files'];(self.out/'migration-receipt.json').write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):m.route_plan(plan,self.out,self.catalogue,self.selections)

    def test_linked_files_and_root_traversal_refuse(self):
        p=self.fixture();(self.out/'game.bin').unlink();(self.out/'game.bin').symlink_to(self.source/'game.bin')
        with self.assertRaises(ValueError):self.review(p)
        with self.assertRaises(ValueError):m.plan(self.source/'..'/'roms',self.entries)

    def test_dangling_incomplete_marker_and_ambiguous_receipt_inventory_refuse(self):
        self.fixture();marker=self.out/'MIGRATION-INCOMPLETE';marker.symlink_to(self.root/'missing')
        with self.assertRaises(ValueError):m.verify(self.out)
        marker.unlink();receipt_path=self.out/'migration-receipt.json';receipt=json.loads(receipt_path.read_text())
        receipt['files']*=2;receipt_path.write_text(json.dumps(receipt))
        with self.assertRaises(ValueError):m.verify(self.out)

    def test_unsupported_descriptor_and_shell_sensitive_destination_refuse(self):
        self.fixture();selected=copy.deepcopy(self.selections)
        other=self.root/'card;command';self.out.rename(other)
        with self.assertRaises(ValueError):m.route_plan(self.copy_plan,other,self.catalogue,selected)
        other.rename(self.out)
        (self.source/'game.cue').write_text('FILE "game.bin" BINARY\n')
        (self.out/'game.cue').write_bytes((self.source/'game.cue').read_bytes())
        entries=self.entries+[{'editionId':'fixture:edition','path':'game.cue'}];plan=m.plan(self.source,entries)
        receipt=json.loads((self.out/'migration-receipt.json').read_text());receipt.update(planSha256=plan['planSha256'],files=plan['files'])
        (self.out/'migration-receipt.json').write_text(json.dumps(receipt))
        selected[0]['familyPaths']=['game.bin','game.cue']
        with self.assertRaises(ValueError):m.route_plan(plan,self.out,self.catalogue,selected)

    def test_fresh_cli_review_writes_private_json_only_and_refuses_overwrite(self):
        p=self.fixture();plan_path=self.root/'route-plan.json';plan_path.write_text(json.dumps(p));output=self.root/'review.json'
        command=[sys.executable,str(Path(m.__file__)), 'route-review','--plan',str(plan_path),
                 '--approve-digest',p['routePlanSha256'],'--output',str(output)]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);review=json.loads(output.read_text())
        self.assertEqual(review['rollback'],self.text);self.assertIn(str(self.out/'game.bin'),review['candidate'])
        self.assertEqual(output.stat().st_mode&0o777,0o600)
        self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
        self.assertEqual(self.catalogue.read_text(),self.text)
