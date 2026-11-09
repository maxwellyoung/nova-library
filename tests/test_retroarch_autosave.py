from pathlib import Path
import tempfile
import unittest
from tools import retroarch_autosave as a

BASE=b'auto_overrides_enable = "false"\nconfig_save_on_exit = "false"\nsavefile_directory = "original/saves"\ninput_player1_a_btn = "0"\n'


class AutosaveTests(unittest.TestCase):
    def test_three_settings_only_and_no_automatic_load_or_cloud_restore(self):
        data,r=a.prepare(BASE,a.RUNTIME,'fixture:edition');self.assertEqual(BASE.count(b'autosave_interval'),0)
        self.assertIn(b'autosave_interval = "30"',data);self.assertIn(b'savestate_auto_save = "true"',data);self.assertIn(b'savestate_auto_load = "false"',data)
        self.assertTrue(data.startswith(BASE));self.assertFalse(r['deviceApplied']);self.assertFalse(r['automaticCloudRestore']);self.assertEqual(len(r['changes']),3)
    def test_unknown_runtime_includes_duplicates_and_active_overrides_refuse(self):
        for base in [BASE+b'#include "other.cfg"\n',BASE+BASE,BASE.replace(b'auto_overrides_enable = "false"',b'auto_overrides_enable = "true"'),BASE+b'savestate_auto_save = "maybe"\n']:
            with self.assertRaises(a.AutosaveError):a.prepare(base,a.RUNTIME,'fixture:edition')
        with self.assertRaises(a.AutosaveError):a.prepare(BASE,{**a.RUNTIME,'version':'next'},'fixture:edition')
    def test_private_new_artifacts_retain_exact_baseline_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td).resolve();r=a.write_candidate(root,'profile',BASE,a.RUNTIME,'fixture:edition');folder=root/'profile'
            self.assertEqual((folder/'baseline.cfg').read_bytes(),BASE);self.assertEqual(folder.stat().st_mode&0o777,0o700)
            self.assertEqual(a.verify_candidate(folder)['baselineSha256'],r['baselineSha256']);self.assertTrue((folder/'COMPLETE').is_file());self.assertEqual((folder/'candidate.cfg').stat().st_mode&0o777,0o600)
            with self.assertRaises(FileExistsError):a.write_candidate(root,'profile',BASE,a.RUNTIME,'fixture:edition')
    def test_existing_values_are_reviewed_and_original_paths_and_controls_preserved(self):
        base=BASE+b'autosave_interval = "0"\nsavestate_auto_save = "false"\nsavestate_auto_load = "true"\n'
        data,r=a.prepare(base,a.RUNTIME,'fixture:edition');self.assertEqual(len(r['changes']),3)
        self.assertIn(b'savefile_directory = "original/saves"',data);self.assertIn(b'input_player1_a_btn = "0"',data)

    def test_existing_fit_fill_adapter_composes_without_losing_autosave_or_baseline_identity(self):
        import hashlib
        for mode in ['fit','fill']:
            data,r=a.prepare(BASE,a.RUNTIME,'fixture:edition',display_mode=mode)
            self.assertEqual(r['baselineSha256'],hashlib.sha256(BASE).hexdigest());self.assertEqual(r['displayMode'],mode)
            self.assertIn(b'autosave_interval = "30"',data);self.assertIn(b'savestate_auto_load = "false"',data)
            self.assertIn(b'video_force_aspect = "'+(b'true' if mode=='fit' else b'false')+b'"',data)
