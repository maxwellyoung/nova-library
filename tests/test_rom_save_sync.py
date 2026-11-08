import importlib.util
import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

path=Path(__file__).resolve().parents[1]/'tools/prepare_rom_save_sync.py'
spec=importlib.util.spec_from_file_location('save_sync',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class SaveSync(unittest.TestCase):
    def test_preserves_existing_layout_and_controls(self):
        source='sort_savefiles_enable = "false"\nsavefile_directory = "/synthetic/saves"\ninput_menu_toggle_btn = "3"\nsavestate_auto_load = "false"\n'
        text=module.prepare(source,'https://library.example.com','demo','synthetic-password')
        self.assertTrue(text.startswith(source))
        self.assertIn('cloud_sync_enable = "false"',text)
        self.assertIn('cloud_sync_sync_configs = "false"',text)
        self.assertIn('webdav_url = "https://library.example.com/api/sync/retroarch/"',text)
    def test_refuses_unsafe_origin_and_credentials(self):
        for endpoint in ['http://example.com','https://'+ 'demo:synthetic'+chr(64)+'example.com',
                         'https://@example.com','https://example.com/prefix','https://example.com?token=x',
                         'https://example.com?','https://example.com#','https://example.com:']:
            with self.assertRaises(ValueError):module.prepare('',endpoint,'demo','example')
        with self.assertRaises(ValueError):module.prepare('','https://example.com','demo','example\nsecret')
    def test_refuses_orphaning_saves(self):
        with self.assertRaises(ValueError):module.prepare('savefiles_in_content_dir = "true"','https://example.com','demo','example')
    def test_refuses_duplicate_cloud_settings(self):
        with self.assertRaises(ValueError):module.prepare('cloud_sync_enable = "true"\ncloud_sync_enable = "false"','https://example.com','demo','example')
    def test_inline_comments_and_unknown_layout_cannot_bypass_migration_refusal(self):
        for source in ('savefiles_in_content_dir = "true" # owner setting',
                       'savestates_in_content_dir = "true" # state files',
                       'savefiles_in_content_dir = true',
                       'savefiles_in_content_dir = "unknown"',
                       'savefiles_in_content_dir = "false"\nsavefiles_in_content_dir = "false"',
                       '#include "private-profile.cfg"'):
            with self.subTest(source=source):
                with self.assertRaises(ValueError):
                    module.prepare(source,'https://example.com','demo','example')
        source='savefiles_in_content_dir = "false" # reviewed layout\n'
        self.assertTrue(module.prepare(source,'https://example.com','demo','example').startswith(source))
    def test_enable_assertion_cannot_replace_installed_launch_barrier_proof(self):
        for enable in (True,1,'true',None):
            with self.assertRaisesRegex(ValueError,'Automatic save sync remains disabled'):
                module.prepare('','https://example.com','demo','example',enable=enable)
    def test_invalid_ports_controls_and_del_are_refused(self):
        for endpoint in ('https://example.com:private-value','https://example.com:65536','https://example.com:0',
                         'https://example.com\n','https://[broken','https://example.com\x7f'):
            with self.assertRaises(ValueError):
                module.prepare('',endpoint,'demo','example')
        with self.assertRaises(ValueError):
            module.prepare('','https://example.com','demo','private\x7fvalue')
    def test_cli_candidate_is_private_disabled_and_never_overwrites_or_exposes_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve()
            source=base/'source.cfg'
            output=base/'candidate.cfg'
            original='savefiles_in_content_dir = "false"\nsavestate_auto_load = "false"\n'
            source.write_text(original)
            secret=json.dumps({'username':'synthetic-user','password':'synthetic-private-password'})
            def run(*args,credentials=secret):
                return subprocess.run([sys.executable,str(path),str(source),str(output),
                                       '--endpoint','https://example.com',*args],input=credentials,capture_output=True,text=True)
            success=run()
            self.assertEqual(success.returncode,0,success.stderr)
            self.assertEqual(source.read_text(),original)
            self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600)
            candidate=output.read_bytes()
            self.assertIn(b'cloud_sync_enable = "false"',candidate)
            for result in (run(),run('--enable-after-launch-barrier-verified'),run(credentials='[]'),run(credentials='{')):
                self.assertEqual(result.returncode,1)
                self.assertNotIn(str(base),result.stderr)
                self.assertNotIn('synthetic-private-password',result.stderr)
                self.assertNotIn('Traceback',result.stderr)
                self.assertEqual(output.read_bytes(),candidate)
            output.unlink()
            source.unlink()
            missing=run()
            self.assertEqual(missing.returncode,1)
            self.assertNotIn(str(base),missing.stderr)
            self.assertFalse(output.exists())
