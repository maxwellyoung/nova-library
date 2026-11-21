import copy
import contextlib
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import collect_storage as storage

NOW = datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)
MOUNT = '/storage/ABCD-1234'
HEADER = 'Filesystem 1K-blocks Used Available Use% Mounted on\n'


def table(mount='/data', total=1000, used=700, free=200):
    return HEADER + f'/dev/block/example {total} {used} {free} 70% {mount}\n'


class Reader:
    def __init__(self, changes=None):
        self.calls = []
        self.replies = {'getprop ro.serialno': (0, 'demo-nova\n', ''),
                        'df -k /data': (0, table(), ''),
                        'sm list-volumes public': (0, 'public:179,65 mounted ABCD-1234\n', ''),
                        'df -k ' + MOUNT: (0, table(MOUNT, 2000, 500, 1500), '')}
        self.replies.update(changes or {})

    def shell(self, command, timeout):
        self.calls.append(command)
        reply = self.replies[command]
        if isinstance(reply, list): reply = reply.pop(0)
        if isinstance(reply, Exception): raise reply
        return reply


class CapacityCapture(unittest.TestCase):
    def capture(self, reader=None):
        return storage.capture(reader or Reader(), 'demo-nova', lambda: NOW, sd_uuid='ABCD-1234')

    def test_generic_public_storage_never_becomes_microSD_without_explicit_enrolment(self):
        for uuid in [None, 'EEEE-1111']:
            reader = Reader()
            report = storage.capture(reader, 'demo-nova', lambda: NOW, sd_uuid=uuid)
            self.assertEqual([row['id'] for row in report['volumes']], ['internal-data'])
            self.assertFalse(any(command.startswith('df -k /storage') for command in reader.calls))
        with self.assertRaises(ValueError): storage.capture(Reader(), 'demo-nova', sd_uuid='ABCD-1234;command')

    def test_internal_and_card_are_separate_kib_measurements_without_invented_categories(self):
        reader = Reader(); report = self.capture(reader)
        self.assertEqual(report['errors'], [])
        internal, card = report['volumes']
        self.assertEqual((internal['total'], internal['used'], internal['free']), (1024000, 716800, 204800))
        self.assertEqual((card['total'], card['used'], card['free']), (2048000, 512000, 1536000))
        self.assertEqual(internal['total']-internal['used']-internal['free'], 102400)
        self.assertTrue(all('breakdown' not in row for row in report['volumes']))
        self.assertEqual(internal['observedAt'], '2026-11-10T10:00:00Z')
        self.assertEqual(reader.calls, ['getprop ro.serialno', 'df -k /data', 'sm list-volumes public',
                                        'df -k ' + MOUNT, 'sm list-volumes public'])

    def test_identity_mismatch_stops_before_reading_any_capacity(self):
        reader = Reader({'getprop ro.serialno': (0, 'other-device', '')})
        with self.assertRaises(ValueError): self.capture(reader)
        self.assertEqual(reader.calls, ['getprop ro.serialno'])
        for serial in ['', None, 'demo; command']:
            with self.assertRaises(ValueError): storage.capture(Reader(), serial)

    def test_no_unmounted_or_ambiguous_card_is_reported_as_empty(self):
        for discovery in ['', 'public:179,65 unmounted ABCD-1234',
                          'public:179,65 mounted ABCD-1234\npublic:179,66 mounted EEEE-1111',
                          'public:179,65 mounted null', 'public:179,65 mystery ABCD-1234',
                          'public:179,65 mounted ABCD-1234;command',
                          'public:179,65 mounted ABCD-1234\npublic:179,66 mounted abcd-1234']:
            with self.subTest(discovery=discovery):
                reader = Reader({'sm list-volumes public': (0, discovery, '')})
                report = self.capture(reader)
                self.assertEqual([row['id'] for row in report['volumes']], ['internal-data'])
                self.assertEqual(report['errors'][0]['volume'], 'sd-card')
                self.assertFalse(any(command.startswith('df -k /storage') for command in reader.calls))

    def test_card_change_removal_and_internal_fallback_do_not_create_sd_capacity(self):
        for after in ['', 'public:179,65 mounted EEEE-1111', 'public:179,65 mounted_ro ABCD-1234']:
            replies = [(0, 'public:179,65 mounted ABCD-1234', ''), (0, after, '')]
            report = self.capture(Reader({'sm list-volumes public': replies}))
            self.assertEqual([r['id'] for r in report['volumes']], ['internal-data'])
        report = self.capture(Reader({'df -k ' + MOUNT: (0, table('/storage'), '')}))
        self.assertEqual([r['id'] for r in report['volumes']], ['internal-data'])

    def test_readonly_card_is_capacity_evidence_without_install_authority(self):
        report = self.capture(Reader({'sm list-volumes public': (0, 'public:179,65 mounted_ro ABCD-1234', '')}))
        self.assertEqual(len(report['volumes']), 2)
        self.assertNotIn('installable', json.dumps(report))

    def test_one_volume_failure_keeps_the_other_and_zero_is_measured(self):
        report = self.capture(Reader({'df -k /data': (1, '', 'denied')}))
        self.assertEqual([r['id'] for r in report['volumes']], ['sd-card'])
        report = self.capture(Reader({'df -k /data': (0, table(used=1000, free=0), '')}))
        self.assertEqual(report['volumes'][0]['free'], 0)
        self.assertEqual(report['errors'], [])

    def test_unknown_units_bad_mount_extra_rows_arithmetic_and_large_values_are_refused(self):
        for raw in [table().replace('1K-blocks', 'Size'), table().replace('/data', '/storage/emulated'),
                    table() + '/dev/other 1 0 1 0% /data\n', table(total=0), table(used=1001),
                    table(free=-1), table(total=2**53), table().replace('70%', '101%'),
                    table().replace('700', '7.0K'), 'x' * (storage.MAX_CAPTURE + 1)]:
            with self.assertRaises(ValueError): storage.parse_df(raw, '/data', 'internal-data', NOW)
        self.assertEqual(storage.parse_df(table().replace('1K-blocks', '1024-blocks'), '/data', 'internal-data', NOW)['total'], 1024000)

    def test_nonzero_exit_stderr_timeout_and_clock_failure_keep_unknown_explicit(self):
        for reply in [(1, table(), ''), (0, table(), 'partial'), OSError('read failed'),
                      subprocess.TimeoutExpired('synthetic', 15)]:
            report = self.capture(Reader({'df -k /data': reply}))
            self.assertEqual([r['id'] for r in report['volumes']], ['sd-card'])
            self.assertNotIn('partial', json.dumps(report))
        with self.assertRaises(ValueError): storage.timestamp(datetime(2026, 11, 10))

    def test_export_fields_keep_dates_and_matching_legacy_snapshot_and_strip_private_identity(self):
        report = self.capture(); before = copy.deepcopy(report)
        fields = storage.catalogue_fields(report, 'demo-nova', NOW)
        self.assertEqual(fields['storage_volume'], fields['storage_volumes'][0])
        self.assertEqual(fields['storage_volume']['observedAt'], '2026-11-10T10:00:00Z')
        self.assertNotIn('demo-nova', json.dumps(fields))
        self.assertNotIn('ABCD-1234', json.dumps(fields))
        self.assertEqual(report, before)
        fields['storage_volume']['free'] = 0
        self.assertEqual(report, before)

    def test_wrong_device_forged_fields_future_dates_and_duplicate_roles_fail_export(self):
        report = self.capture()
        with self.assertRaises(ValueError): storage.catalogue_fields(report, 'other-device', NOW)
        invalid = [dict(report, schemaVersion=True), dict(report, producer='unknown'), dict(report, sdVolumeUuid=None)]
        for key, value in [('total', 0), ('free', True), ('used', 2**53), ('source', 'inferred'),
                           ('id', 'other'), ('observedAt', '2999-01-01T00:00:00Z'),
                           ('observedAt', 'not-a-date'), ('breakdown', {})]:
            changed = copy.deepcopy(report); changed['volumes'][0][key] = value; invalid.append(changed)
        changed = copy.deepcopy(report); changed['volumes'][1] = changed['volumes'][0]; invalid.append(changed)
        for changed in invalid:
            with self.assertRaises(ValueError): storage.catalogue_fields(changed, 'demo-nova', NOW)
        empty = dict(report, volumes=[])
        self.assertEqual(storage.catalogue_fields(empty, 'demo-nova', NOW), {'storage_volumes': []})

    def test_cli_writes_new_private_file_and_keeps_existing_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.json'
            arguments = ['collect_storage.py', '--serial', 'demo-nova', '--sd-uuid', 'ABCD-1234', '--output', str(path)]
            with mock.patch.object(sys, 'argv', arguments), mock.patch.object(storage, 'AdbReader', return_value=Reader()), contextlib.redirect_stdout(io.StringIO()):
                storage.main()
            report = json.loads(path.read_text())
            self.assertEqual(report['hardwareSerial'], 'demo-nova')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            before = path.read_bytes()
            with mock.patch.object(sys, 'argv', arguments), mock.patch.object(storage, 'AdbReader', return_value=Reader()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error: storage.main()
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(path.read_bytes(), before)

    def test_cli_refuses_repository_output_without_reading_device(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory); (parent / '.git').mkdir()
            path = parent / 'capture.json'
            with mock.patch.object(sys, 'argv', ['collect_storage.py', '--serial', 'demo-nova', '--output', str(path)]), mock.patch.object(storage, 'AdbReader') as adb, contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit): storage.main()
            adb.assert_not_called()
            self.assertFalse(path.exists())


if __name__ == '__main__': unittest.main()
