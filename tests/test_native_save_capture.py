import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
import native_save_capture as capture
import save_passport as passport


class Device:
    def __init__(self, key='soh-nova-slot1'):
        self.profile = capture.PROFILES[key]
        self.data = {self.profile.source + '/' + name: b'checked progress ' + name.encode()
                     for name in self.profile.files}
        self.active = False
        self.apk_hash = self.profile.apk_sha256
        self.content = {self.profile.source + '/' + name: digest
                        for name, digest in self.profile.data_checks}
        self.read_hook = None
        self.snap_hook = None
        self.calls = []

    def idle(self, package):
        self.calls.append(('idle', package))
        capture.require(not self.active, 'Close the native game normally before capturing its saves')

    def apk(self, package):
        self.calls.append(('apk', package))
        return self.apk_hash

    def snapshot(self, path):
        self.calls.append(('snapshot', path))
        if self.snap_hook:
            self.snap_hook(self, path)
        capture.require(path in self.data, 'Save unavailable')
        value = self.data[path]
        capture.require(0 < len(value) <= capture.MAX_FILE_BYTES, 'Invalid save size')
        return len(value), 41, 123, hashlib.sha256(value).hexdigest()

    def data_digest(self, path):
        self.calls.append(('data_digest', path))
        return self.content[path]

    def read(self, path):
        self.calls.append(('read', path))
        if self.read_hook:
            self.read_hook(self, path)
        return self.data[path]


class NativeCapture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.root.chmod(0o700)
        self.output = self.root / 'progress.nvs'
        self.device = Device()

    def tearDown(self):
        self.tmp.cleanup()

    def pack(self, **kwargs):
        return capture.capture(self.device, 'soh-nova-slot1', self.output,
                               confirm_idle=True, **kwargs)

    def assert_unpublished(self):
        self.assertFalse(self.output.exists())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_actual_passport_contract_roundtrip_and_no_unselected_files(self):
        original = copy.deepcopy(self.device.data)
        self.device.data[self.device.profile.source + '/OOT.z64'] = b'not a save'
        result = self.pack()
        self.assertEqual(result, passport.verify(self.output))
        target = self.device.profile.identity()
        recovered = self.root / 'recovered'
        passport.stage(self.output, target, recovered)
        self.assertEqual(set(result['files'][i]['path'] for i in range(len(result['files']))),
                         set(self.device.profile.files))
        for remote, data in original.items():
            name = remote.removeprefix(self.device.profile.source + '/')
            self.assertEqual((recovered / name).read_bytes(), data)
            self.assertEqual(self.device.data[remote], data)
        self.assertFalse((recovered / 'OOT.z64').exists())
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(recovered.stat().st_mode), 0o700)
        self.assertNotIn(self.device.profile.source, str(result))

    def test_diablo_profile_captures_only_checked_shareware_hero(self):
        device = Device('diablo-shareware-hero0')
        device.data[device.profile.source + '/diablo.ini'] = b'keep configuration'
        device.data[device.profile.source + '/spawn.mpq'] = b'game assets'
        result = capture.capture(device, 'diablo-shareware-hero0', self.output, confirm_idle=True)
        self.assertEqual([f['path'] for f in result['files']], ['spawn_0.sv'])
        self.assertEqual(result['editionId'], 'native:org.diasurgical.devilutionx:shareware')
        self.assertEqual(len(passport.verify(self.output)['files']), 1)

    def test_user_closed_declaration_and_explicit_supported_profile_required(self):
        for value in [False, None, 1, 'yes']:
            with self.assertRaises(capture.CaptureError):
                capture.capture(self.device, 'soh-nova-slot1', self.output, confirm_idle=value)
        with self.assertRaises(capture.CaptureError):
            capture.capture(self.device, 'mario', self.output, confirm_idle=True)
        self.assertEqual(self.device.calls, [])
        self.assert_unpublished()

    def test_running_game_and_changed_apk_refuse_before_reading_save_bytes(self):
        for active, apk in [(True, self.device.profile.apk_sha256), (False, '0' * 64)]:
            with self.subTest(active=active):
                self.device.active, self.device.apk_hash = active, apk
                self.device.calls.clear()
                with self.assertRaises(capture.CaptureError):
                    self.pack()
                self.assertFalse(any(x[0] == 'read' for x in self.device.calls))
                self.assert_unpublished()

    def test_missing_or_empty_save_never_creates_a_successful_empty_backup(self):
        first = self.device.profile.source + '/' + self.device.profile.files[0]
        for data in [None, b'']:
            if data is None:
                self.device.data.pop(first, None)
            else:
                self.device.data[first] = data
            with self.assertRaises(capture.CaptureError):
                self.pack()
            self.assert_unpublished()

    def test_changed_game_data_refuses_capture_before_reading_saves(self):
        self.device.content[next(iter(self.device.content))] = 'f' * 64
        with self.assertRaisesRegex(capture.CaptureError, 'Game data differs'):
            self.pack()
        self.assertFalse(any(x[0] == 'read' for x in self.device.calls))
        self.assert_unpublished()

    def test_game_data_change_during_capture_is_not_published(self):
        def changed_content(device, path):
            device.content[next(iter(device.content))] = 'f' * 64
        self.device.read_hook = changed_content
        with self.assertRaisesRegex(capture.CaptureError, 'Game data differs'):
            self.pack()
        self.assert_unpublished()

    def test_changed_read_bytes_are_not_published(self):
        self.device.read_hook = lambda device, path: device.data.update({path: b'newer progress'})
        with self.assertRaises(capture.CaptureError):
            self.pack()
        self.assert_unpublished()

    def test_same_size_mutation_of_an_earlier_file_is_caught_before_publication(self):
        first = self.device.profile.source + '/' + self.device.profile.files[0]
        def change_after_first_read(device, path):
            if path != first:
                device.data[first] = b'x' * len(device.data[first])
        self.device.read_hook = change_after_first_read
        with self.assertRaises(capture.CaptureError):
            self.pack()
        self.assert_unpublished()

    def test_app_restart_or_apk_update_during_capture_prevents_publication(self):
        for field, value in [('active', True), ('apk_hash', '1' * 64)]:
            with self.subTest(field=field):
                self.device = Device()
                self.device.read_hook = lambda device, path: setattr(device, field, value)
                with self.assertRaises(capture.CaptureError):
                    self.pack()
                self.assert_unpublished()

    def test_new_destination_race_and_existing_backup_preserve_prior_bytes(self):
        self.output.write_bytes(b'prior backup')
        with self.assertRaises(capture.CaptureError):
            self.pack()
        self.assertEqual(self.output.read_bytes(), b'prior backup')
        self.output.unlink()
        real_link = os.link
        def racing_link(source, dest):
            if Path(dest) == self.output:
                self.output.write_bytes(b'competing backup')
            return real_link(source, dest)
        with mock.patch.object(capture.os, 'link', side_effect=racing_link):
            with self.assertRaises(FileExistsError):
                self.pack()
        self.assertEqual(self.output.read_bytes(), b'competing backup')
        self.assertFalse(any(x.name.startswith('.native-save-') for x in self.root.iterdir()))

    def test_symlink_shared_directory_and_repository_destinations_are_refused(self):
        self.root.chmod(0o755)
        with self.assertRaises(capture.CaptureError):
            self.pack()
        self.root.chmod(0o700)
        (self.root / '.git').mkdir()
        with self.assertRaises(capture.CaptureError):
            self.pack()
        (self.root / '.git').rmdir()
        self.output.symlink_to(self.root / 'absent')
        with self.assertRaises(capture.CaptureError):
            self.pack()
        self.assertTrue(self.output.is_symlink())

    def test_inspect_does_not_read_payloads_or_create_output(self):
        result = capture.inspect(self.device, 'soh-nova-slot1')
        self.assertEqual(result['files'], 2)
        self.assertTrue(result['idleObserved'])
        self.assertFalse(any(x[0] == 'read' for x in self.device.calls))
        self.assert_unpublished()

    def test_backup_cannot_be_staged_into_another_runtime_or_over_existing_progress(self):
        self.pack()
        identity = self.device.profile.identity()
        identity['runtime']['version'] = 'other-checked-version'
        with self.assertRaises(passport.PassportError):
            passport.stage(self.output, identity, self.root / 'wrong-version')
        self.assertFalse((self.root / 'wrong-version').exists())
        target = self.root / 'live'
        target.mkdir()
        (target / 'keep.sav').write_bytes(b'owner progress')
        with self.assertRaises(passport.PassportError):
            passport.stage(self.output, self.device.profile.identity(), target)
        self.assertEqual((target / 'keep.sav').read_bytes(), b'owner progress')


class AdbBoundary(unittest.TestCase):
    def setUp(self):
        self.adb = capture.Adb('fixture-serial')

    @staticmethod
    def completed(code=0, output=b''):
        return subprocess.CompletedProcess([], code, output, b'private-device-path')

    def test_serial_is_explicit_and_is_not_shell_interpolated(self):
        for value in ['', None, 'two devices', '$(secret)']:
            with self.assertRaises(capture.CaptureError):
                capture.Adb(value)
        with mock.patch.object(capture.subprocess, 'run', return_value=self.completed(1)) as run:
            self.adb.idle('com.example.game')
        self.assertEqual(run.call_args.args[0],
                         ['adb', '-s', 'fixture-serial', 'shell', 'pidof com.example.game'])

    def test_pidof_failure_is_never_interpreted_as_idle(self):
        for code, output in [(0, b'123'), (1, b'123'), (255, b'')]:
            with mock.patch.object(capture.subprocess, 'run', return_value=self.completed(code, output)):
                with self.assertRaises(capture.CaptureError):
                    self.adb.idle('com.example.game')

    def test_disconnect_and_timeout_diagnostics_redact_device_values(self):
        for error in [OSError('private source'), subprocess.TimeoutExpired('private command', 20)]:
            with mock.patch.object(capture.subprocess, 'run', side_effect=error):
                with self.assertRaisesRegex(capture.CaptureError, '^Device read unavailable or timed out; no backup published$'):
                    self.adb.idle('com.example.game')

    def test_split_or_unexpected_package_paths_are_refused(self):
        for value in [b'package:/data/app/game/base.apk\npackage:/data/app/game/split.apk\n',
                      b'package:/data/app/../other/base.apk\n', b'package:/secret/base.apk\n']:
            with mock.patch.object(self.adb, '_shell', return_value=self.completed(output=value)):
                with self.assertRaises(capture.CaptureError):
                    self.adb.apk('com.example.game')

    def test_game_data_is_hashed_without_reading_or_archiving_its_bytes(self):
        path = '/storage/emulated/0/game/data.mpq'
        with mock.patch.object(self.adb, '_shell', side_effect=[self.completed(output=path.encode()),
                self.completed(output=b'b' * 64 + b'  data.mpq')]) as shell:
            self.assertEqual(self.adb.data_digest(path), 'b' * 64)
        self.assertEqual([x.args[0] for x in shell.call_args_list], ['readlink', 'sha256sum'])

    def test_file_type_links_bounds_and_checksums_are_checked(self):
        path = '/storage/emulated/0/game/save.sav'
        for canonical, metadata in [(b'/storage/emulated/0/other.sav', b''),
                                    (path.encode(), b'directory:4:1:1'),
                                    (path.encode(), b'regular file:0:1:1'),
                                    (path.encode(), f'regular file:{capture.MAX_FILE_BYTES + 1}:1:1'.encode())]:
            with mock.patch.object(self.adb, '_shell', side_effect=[self.completed(output=canonical),
                                                                   self.completed(output=metadata)]):
                with self.assertRaises(capture.CaptureError):
                    self.adb.snapshot(path)
        with mock.patch.object(self.adb, '_shell', side_effect=[self.completed(output=path.encode()),
                self.completed(output=b'regular file:4:12:123'), self.completed(output=b'a' * 64 + b'  save.sav')]):
            self.assertEqual(self.adb.snapshot(path), (4, 12, 123, 'a' * 64))

    def test_payload_read_is_bounded_and_contains_no_mutation_command(self):
        with mock.patch.object(self.adb, '_run', return_value=self.completed(output=b'save')) as run:
            self.assertEqual(self.adb.read('/storage/emulated/0/game/save.sav'), b'save')
        self.assertEqual(run.call_args.args,
                         ('exec-out', 'head', '-c', str(capture.MAX_FILE_BYTES + 1),
                          '/storage/emulated/0/game/save.sav'))


if __name__ == '__main__':
    unittest.main()
