import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

TOOL = Path(__file__).resolve().parents[1] / 'tools/retroarch_display.py'
spec = importlib.util.spec_from_file_location('retroarch_display', TOOL)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
BASE = (b'# disposable owner profile\nauto_overrides_enable = "false"\n'
        b'config_save_on_exit = "false"\ninput_menu_toggle_btn = "3"\n'
        b'savefile_directory = "/synthetic/saves"\nsavestate_auto_load = "false"\n'
        b'aspect_ratio_index = "0"\nvideo_force_aspect = "true"\n')


class DisplayTransactions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.store = m.Store.create(self.base / 'display')
        self.profile = self.base / 'owner.cfg'
        self.profile.write_bytes(BASE)

    def tearDown(self):
        self.tmp.cleanup()

    def choose(self, mode='fit', edition='edition-a', baseline=BASE):
        plan = self.store.preview(m.RUNTIME, 'game-a', edition, mode, baseline)
        return self.store.confirm(plan, plan['token'], baseline)

    def tree(self):
        return {str(p.relative_to(self.store.root)): p.read_bytes()
                for p in self.store.root.rglob('*') if p.is_file()}

    def test_exact_modes_and_unknown_runtime_refuse_without_writes(self):
        caps = m.capabilities(m.RUNTIME)
        self.assertEqual({k for k, v in caps['modes'].items() if v['available']}, {'fit', 'fill'})
        before = self.tree()
        for mode in ('native', 'crop', 'Fit', 'fit; touch /synthetic/sentinel'):
            with self.subTest(mode=mode), self.assertRaises(m.DisplayError):
                self.store.preview(m.RUNTIME, 'game-a', 'edition-a', mode, BASE)
        for field, value in [('version', '1.21.0'), ('package', 'com.example.fake'), ('sourceCommit', 'unknown')]:
            runtime = {**m.RUNTIME, field: value}
            with self.subTest(field=field), self.assertRaises(m.DisplayError):
                self.store.preview(runtime, 'game-a', 'edition-a', 'fit', BASE)
        self.assertEqual(self.tree(), before)

    def test_preview_is_read_only_and_wrong_token_cannot_confirm(self):
        before = self.tree()
        plan = self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fit', BASE)
        self.assertEqual(self.tree(), before)
        self.assertNotIn('/synthetic/saves', json.dumps(plan))
        with self.assertRaises(m.DisplayError):
            self.store.confirm(plan, '0' * 64, BASE)
        self.assertEqual(self.tree(), before)

    def test_fit_fill_restart_and_two_steps_of_exact_revert(self):
        fit = self.choose()
        fit_data = Path(fit['configPath']).read_bytes()
        self.assertIn(b'aspect_ratio_index = "22"', fit_data)
        self.assertIn(b'video_scale_integer = "false"', fit_data)
        for line in BASE.splitlines(keepends=True):
            if not line.startswith((b'aspect_ratio_index', b'video_force_aspect')):
                self.assertIn(line, fit_data)
        self.assertEqual(self.profile.read_bytes(), BASE)
        self.store = m.Store(self.store.root)
        self.assertEqual(self.store.current('game-a', 'edition-a')['mode'], 'fit')
        fill = self.choose('fill', baseline=None)
        self.assertIn(b'aspect_ratio_index = "24"', Path(fill['configPath']).read_bytes())
        self.assertIn(b'video_force_aspect = "false"', Path(fill['configPath']).read_bytes())
        for expected in (fit_data, BASE):
            plan = self.store.preview_revert(m.RUNTIME, 'game-a', 'edition-a')
            state = self.store.confirm(plan, plan['token'])
            self.assertEqual(Path(state['configPath']).read_bytes(), expected)
        self.assertEqual(state['mode'], 'original')
        with self.assertRaises(m.DisplayError):
            self.store.preview_revert(m.RUNTIME, 'game-a', 'edition-a')
        self.assertEqual(self.profile.read_bytes(), BASE)
        self.assertFalse(state['deviceApplied'])

    def test_editions_are_isolated_even_when_game_is_same(self):
        first = self.choose('fit', 'edition-a')
        second = self.choose('fill', 'edition-b')
        self.assertNotEqual(first['configPath'], second['configPath'])
        before = Path(first['configPath']).read_bytes()
        plan = self.store.preview_revert(m.RUNTIME, 'game-a', 'edition-b')
        self.store.confirm(plan, plan['token'])
        self.assertEqual(self.store.current('game-a', 'edition-a')['generation'], first['generation'])
        self.assertEqual(Path(first['configPath']).read_bytes(), before)

    def test_changed_baseline_modified_preview_and_expiry_refuse(self):
        plan = self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fit', BASE)
        for candidate, data in ((plan, BASE + b'# changed\n'), ({**plan, 'mode': 'fill'}, BASE),
                                ({**plan, 'command': 'unsafe'}, BASE)):
            with self.assertRaises(m.DisplayError):
                self.store.confirm(candidate, plan['token'], data)
        with patch.object(m.time, 'time', return_value=plan['expiresAt'] + 1), self.assertRaises(m.DisplayError):
            self.store.confirm(plan, plan['token'], BASE)
        with patch.object(m.time, 'time', return_value=plan['issuedAt'] - 1), self.assertRaises(m.DisplayError):
            self.store.confirm(plan, plan['token'], BASE)
        self.assertIsNone(self.store.current('game-a', 'edition-a')['mode'])

    def test_stale_preview_and_external_config_edit_refuse(self):
        first = self.choose()
        plan = self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fill')
        second = self.choose('fit', baseline=None)
        with self.assertRaises(m.DisplayError):
            self.store.confirm(plan, plan['token'])
        path = Path(second['configPath'])
        path.write_bytes(path.read_bytes() + b'# outside editor\n')
        with self.assertRaises(m.DisplayError):
            self.store.preview_revert(m.RUNTIME, 'game-a', 'edition-a')
        self.assertTrue(path.read_bytes().endswith(b'# outside editor\n'))
        self.assertTrue(Path(first['configPath']).exists())

    def test_include_duplicate_unknown_precedence_and_bounds_refuse(self):
        bad = [BASE + b'#include "other.cfg"\n', BASE + b'# Include "other.cfg"\n',
               BASE + b'aspect_ratio_index = "22"\n',
               BASE.replace(b'auto_overrides_enable = "false"', b'auto_overrides_enable = "true"'),
               BASE.replace(b'config_save_on_exit = "false"', b'config_save_on_exit = "true"'),
               BASE.replace(b'aspect_ratio_index = "0"', b'aspect_ratio_index = "99"'),
               BASE + b'video_viewport_bias_x = "NaN"\n', BASE + b'video_viewport_bias_y = "1.1"\n',
               BASE + b'video_scale_integer = "unknown"\n', BASE + b'$(touch /synthetic/sentinel)\n',
               b'\xff', BASE + b'\x00', b'#' * (m.LIMIT + 1)]
        before = self.tree()
        for data in bad:
            with self.subTest(data=data[:40]), self.assertRaises(m.DisplayError):
                self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fit', data)
        self.assertEqual(self.tree(), before)

    def test_portable_recipe_is_allowlisted_and_import_does_not_apply(self):
        self.choose()
        recipe = self.store.recipe('game-a', 'edition-a')
        raw = m._json(recipe)
        self.assertNotIn('configPath', recipe)
        self.assertNotIn(b'/synthetic', raw)
        before = self.tree()
        self.assertEqual(m.import_recipe(raw), recipe)
        imported_plan = self.store.preview_recipe(raw)
        self.assertEqual(imported_plan['mode'], 'fit')
        variants = [{**recipe, 'command': 'touch sentinel'}, {**recipe, 'config': '#include "other.cfg"'},
                    {**recipe, 'aspectReceipt': {'observed': '4:3'}}, {**recipe, 'mode': 'crop'},
                    {**recipe, 'schema': True}, {**recipe, 'editionId': '../other'},
                    {**recipe, 'settings': {**recipe['settings'], 'system_command': 'unsafe'}},
                    {**recipe, 'settings': {**recipe['settings'], 'aspect_ratio_index': '22; unsafe'}}]
        for candidate in variants:
            with self.subTest(candidate=candidate), self.assertRaises(m.DisplayError):
                m.import_recipe(m._json(candidate))
        for raw in (b'{"schema":1,"schema":1}', b'{"x":NaN}', b'{}' * 20000):
            with self.assertRaises(m.DisplayError):
                m.import_recipe(raw)
        self.assertEqual(self.tree(), before)

    def test_private_configs_are_refused_inside_source_checkout(self):
        checkout = self.base / 'checkout'; checkout.mkdir(); (checkout / '.git').mkdir()
        with self.assertRaisesRegex(m.DisplayError, 'Git checkout'):
            m.Store.create(checkout / 'private-profile')
        self.assertFalse((checkout / 'private-profile').exists())

    def test_wrong_edition_and_path_injection_are_rejected(self):
        for game, edition in (('../outside', 'a'), ('a', 'x/y'), ('a', 'x\\y'), ('a', 'x\n'), ('a', 'x' * 129)):
            with self.subTest(edition=edition), self.assertRaises(m.DisplayError):
                self.store.preview(m.RUNTIME, game, edition, 'fit', BASE)
        state = self.choose()
        receipt_path = Path(state['configPath']).with_name('receipt.json')
        receipt = json.loads(receipt_path.read_text()); receipt['editionId'] = 'wrong-edition'
        receipt_path.write_text(json.dumps(receipt))
        with self.assertRaises(m.DisplayError):
            self.store.current('game-a', 'edition-a')

    def test_existing_directory_symlinks_hardlinks_and_busy_lock_refuse(self):
        with self.assertRaises(m.DisplayError):
            m.Store.create(self.base)
        outside = self.base / 'outside'; outside.mkdir()
        (self.store.root / 'editions').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(m.DisplayError):
            self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fit', BASE)
        self.assertEqual(list(outside.iterdir()), [])
        (self.store.root / 'editions').unlink()
        self.choose()
        path = Path(self.store.current('game-a', 'edition-a')['configPath'])
        os.link(path, self.base / 'hardlink.cfg')
        with self.assertRaises(m.DisplayError):
            self.store.current('game-a', 'edition-a')
        (self.base / 'hardlink.cfg').unlink()
        with (self.store.root / 'lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaises(m.DisplayError):
                self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fill')

    def test_configs_backups_and_receipts_are_private(self):
        state = self.choose()
        self.assertEqual(stat.S_IMODE(self.store.root.stat().st_mode), 0o700)
        for path in self.store.root.rglob('*'):
            if path.is_file():
                self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(len(list(self.store.root.rglob('config.cfg'))), 2)
        self.assertEqual(Path(state['configPath']).read_bytes(), m.render_config(BASE, 'fit'))

    def test_write_failure_before_selection_never_changes_prior(self):
        first = self.choose()
        plan = self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fill')
        atomic = m._atomic
        def fail_receipt(path, data):
            if path.name == 'receipt.json':
                raise OSError('synthetic disk-full detail')
            atomic(path, data)
        with patch.object(m, '_atomic', side_effect=fail_receipt), self.assertRaises(OSError):
            self.store.confirm(plan, plan['token'])
        self.assertEqual(self.store.current('game-a', 'edition-a')['generation'], first['generation'])
        self.assertEqual(self.profile.read_bytes(), BASE)

    def test_write_failure_after_selection_rolls_back_immediately(self):
        first = self.choose()
        plan = self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fill')
        def fail(stage):
            if stage == 'selection_durable':
                raise OSError('synthetic failure after pointer')
        with patch.object(m, '_checkpoint', side_effect=fail), self.assertRaisesRegex(m.DisplayError, 'prior selection restored'):
            self.store.confirm(plan, plan['token'])
        self.assertEqual(m.Store(self.store.root).current('game-a', 'edition-a')['generation'], first['generation'])
        self.assertFalse((self.store.root / 'pending.json').exists())

    def test_rollback_failure_retains_journal_for_later_recovery(self):
        first = self.choose()
        plan = self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fill')
        select = self.store._select
        calls = 0
        def fail_rollback(key, generation):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('synthetic second failure')
            return select(key, generation)
        def fail(stage):
            if stage == 'selection_durable':
                raise OSError('synthetic failure')
        with patch.object(self.store, '_select', side_effect=fail_rollback), patch.object(m, '_checkpoint', side_effect=fail):
            with self.assertRaisesRegex(m.DisplayError, 'rollback failed'):
                self.store.confirm(plan, plan['token'])
        with self.assertRaisesRegex(m.DisplayError, 'requires recover'):
            self.store.current('game-a', 'edition-a')
        self.assertTrue(m.Store(self.store.root).recover()['recovered'])
        self.assertEqual(self.store.current('game-a', 'edition-a')['generation'], first['generation'])

    def test_real_process_death_recovery_at_durable_boundaries(self):
        first = self.choose()
        child = """import importlib.util,os,sys
spec=importlib.util.spec_from_file_location('d',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s=m.Store(sys.argv[2]);p=s.preview(m.RUNTIME,'game-a','edition-a','fill')
def stop(stage):
 if stage==sys.argv[3]:os._exit(90)
m._checkpoint=stop
s.confirm(p,p['token'])
"""
        for stage in ('journal_durable', 'selection_durable'):
            with self.subTest(stage=stage):
                result = subprocess.run([sys.executable, '-c', child, str(TOOL), str(self.store.root), stage], capture_output=True)
                self.assertEqual(result.returncode, 90, result.stderr)
                fresh = m.Store(self.store.root)
                with self.assertRaisesRegex(m.DisplayError, 'requires recover'):
                    fresh.preview(m.RUNTIME, 'game-a', 'edition-a', 'fit')
                self.assertTrue(fresh.recover()['recovered'])
                self.assertEqual(fresh.current('game-a', 'edition-a')['generation'], first['generation'])
                self.assertFalse(fresh.recover()['recovered'])
                self.assertEqual(self.profile.read_bytes(), BASE)

    def test_recovery_refuses_newer_external_selection_and_bad_journal(self):
        first = self.choose()
        second = self.choose('fill', baseline=None)
        plan = self.store.preview(m.RUNTIME, 'game-a', 'edition-a', 'fit')
        with patch.object(m, '_checkpoint', side_effect=SystemExit), self.assertRaises(SystemExit):
            self.store.confirm(plan, plan['token'])
        pointer = self.store.root / 'editions' / m._identity('game-a', 'edition-a') / 'current.json'
        pointer.write_text(json.dumps({'generation': first['generation']}))
        with self.assertRaisesRegex(m.DisplayError, 'refuses to overwrite'):
            self.store.recover()
        self.assertEqual(json.loads(pointer.read_text())['generation'], first['generation'])
        (self.store.root / 'pending.json').write_text('{"schema":1,"gameId":"../outside"}')
        with self.assertRaises(m.DisplayError):
            self.store.recover()
        self.assertTrue(Path(second['configPath']).exists())

    def test_cli_redacts_errors_and_never_changes_input(self):
        runtime = self.base / 'runtime.json'; runtime.write_text(json.dumps(m.RUNTIME))
        command = [sys.executable, str(TOOL), 'preview', str(self.store.root), '--runtime', str(runtime),
                   '--game', 'game-a', '--edition', 'edition-a', '--mode', 'fit', '--baseline', str(self.profile)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['mode'], 'fit')
        self.profile.unlink()
        failed = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        self.assertNotIn(str(self.base), failed.stderr)
        self.assertNotIn('Traceback', failed.stderr)


if __name__ == '__main__':
    unittest.main()
