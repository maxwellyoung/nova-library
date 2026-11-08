import importlib.util
import json
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOL = Path(__file__).resolve().parents[1] / 'tools/apply_stopping_notes.py'
spec = importlib.util.spec_from_file_location('stopping_apply', TOOL)
applier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(applier)

CPP = '''// Existing recorder/cloud work stays intact.
#include "FrontendLayer.h"
#include "library/DeviceLibrary.h"
#include "library/romcloud/RomCloud.h"
#include <QQmlApplicationEngine>
#include <QQmlContext>
void FrontendLayer::rebuild()
{
    m_engine = new QQmlApplicationEngine(this);
    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);
    m_engine->rootContext()->setContextProperty(QStringLiteral("romCloud"), new library::RomCloud(this));
    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));
}
'''
PRO = '''TEMPLATE = lib
QT += qml quick sql network
CONFIG += c++11 staticlib
SOURCES += \\
    FrontendLayer.cpp \\
    library/DeviceLibrary.cpp
HEADERS += \\
    FrontendLayer.h \\
    library/DeviceLibrary.h
# Existing custom build settings.
'''
CMAKE = '''add_library(pegasus-backend
    FrontendLayer.cpp
    library/DeviceLibrary.cpp
)
target_link_libraries(pegasus-backend PUBLIC Qt::Qml Qt::Quick)
'''


class ApplyStoppingNotes(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.source = self.base / 'source'
        self.backend = self.source / 'src/backend'
        (self.backend / 'library').mkdir(parents=True)
        for name, data in zip(applier.FILES, (CPP, PRO, CMAKE)):
            (self.source / name).write_text(data)
        self.canary = self.source / 'keep-private-native-work.cpp'
        self.canary.write_bytes(b'Unrelated native source; retain exactly.\n')
        self.root = self.base / 'module-inputs'
        module = self.root / 'native/stoppingnotes'
        module.mkdir(parents=True)
        for name in applier.PAYLOAD:
            shutil.copy2(applier.ROOT / 'native/stoppingnotes' / name, module / name)
        self.backup = self.base / 'private-backup'

    def snapshot(self):
        return {str(p.relative_to(self.source)): p.read_bytes()
                for p in sorted(self.source.rglob('*')) if p.is_file()}

    def apply(self, expected=None):
        return applier.apply(self.source, self.backup, expected, self.root)

    def test_fresh_backups_stage_module_and_preserve_other_work(self):
        before = self.snapshot()
        expected = applier.plan(self.source, self.root)
        result = self.apply(expected)
        self.assertEqual(result['status'], 'applied')
        self.assertTrue(result['sharedFilesMatchOriginalReceipt'])
        for name in applier.FILES:
            self.assertEqual((self.backup / name).read_bytes(), before[name])
            self.assertEqual(stat.S_IMODE((self.backup / name).stat().st_mode), 0o600)
        self.assertEqual(self.canary.read_bytes(), before[self.canary.name])
        self.assertEqual({p.name for p in (self.source / applier.MODULE).iterdir()}, set(applier.PAYLOAD))
        cpp = (self.source / applier.FILES[0]).read_text()
        self.assertLess(cpp.index('QStringLiteral("stoppingNotes")'), cpp.index('m_engine->load('))
        self.assertIn('stoppingNotesRoot.isEmpty() ? nullptr', cpp)
        self.assertIn('AppLocalDataLocation', cpp)
        self.assertNotIn('stoppingNotes', (self.source / applier.FILES[1]).read_text().split('include(')[0])
        self.assertFalse((self.backup / 'INTEGRATION-INCOMPLETE').exists())

    def test_reapply_is_read_only_and_verifies_the_saved_plan(self):
        expected = applier.plan(self.source, self.root)
        self.apply(expected)
        before = self.snapshot()
        receipt = (self.backup / 'receipt.json').read_bytes()
        mtimes = {p: p.stat().st_mtime_ns for p in [self.source / n for n in applier.FILES]}
        self.assertEqual(self.apply(expected)['status'], 'already_applied')
        self.assertEqual(self.snapshot(), before)
        self.assertEqual((self.backup / 'receipt.json').read_bytes(), receipt)
        self.assertTrue(all(p.stat().st_mtime_ns == value for p, value in mtimes.items()))

    def test_changed_source_after_plan_refuses_before_any_write(self):
        expected = applier.plan(self.source, self.root)
        cpp = self.source / applier.FILES[0]
        cpp.write_text(cpp.read_text() + '// Another edit arrived.\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'changed after the plan'):
            self.apply(expected)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.backup.exists())

    def test_changed_owned_hook_or_module_refuses_without_replacing_it(self):
        self.apply()
        cpp = self.source / applier.FILES[0]
        saved = cpp.read_bytes()
        cpp.write_bytes(saved.replace(b'/stopping-notes-v1', b'/owner-edited-location'))
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        cpp.write_bytes(saved)
        target = self.source / applier.MODULE / 'StoppingNotes.cpp'
        target.write_bytes(target.read_bytes() + b'\n// changed native module\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'module bytes changed'):
            self.apply()
        self.assertEqual(self.snapshot(), before)

    def test_reapply_preserves_foreign_edits_and_does_not_certify_old_whole_file_hash(self):
        self.apply()
        cpp = self.source / applier.FILES[0]
        cpp.write_text(cpp.read_text() + '// Separate optional integrator source.\n')
        before = self.snapshot()
        result = self.apply()
        self.assertEqual(result['status'], 'already_applied')
        self.assertFalse(result['sharedFilesMatchOriginalReceipt'])
        self.assertEqual(self.snapshot(), before)

    def test_ambiguous_context_and_partial_integrations_refuse(self):
        cpp = self.source / applier.FILES[0]
        cpp.write_text(CPP + '#include "library/DeviceLibrary.h"\n')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.backup.exists())
        cpp.write_text(CPP + applier.INCLUDE)
        with self.assertRaisesRegex(ValueError, 'partial'):
            self.apply()
        cpp.write_text(CPP)
        (self.source / applier.MODULE).mkdir()
        with self.assertRaises(ValueError):
            self.apply()

    def test_changed_payload_after_plan_is_not_an_implicit_upgrade(self):
        expected = applier.plan(self.source, self.root)
        module = self.root / 'native/stoppingnotes/StoppingNotes.cpp'
        module.write_bytes(module.read_bytes() + b'\n// later module edit\n')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'changed after the plan'):
            self.apply(expected)
        self.assertEqual(self.snapshot(), before)
        self.assertFalse(self.backup.exists())

    def test_failed_second_write_restores_exact_published_files_and_keeps_backup(self):
        before = self.snapshot()
        real = applier.atomic
        calls = []
        def fail_once(path, data, mode):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('Synthetic write failure')
            return real(path, data, mode)
        with mock.patch.object(applier, 'atomic', fail_once):
            with self.assertRaises(OSError):
                self.apply()
        self.assertEqual(self.snapshot(), before)
        self.assertTrue((self.backup / 'INTEGRATION-INCOMPLETE').exists())
        self.assertFalse((self.source / applier.MODULE).exists())
        for name in applier.FILES:
            self.assertEqual((self.backup / name).read_bytes(), before[name])

    def test_rollback_does_not_overwrite_a_concurrent_owner_edit(self):
        real = applier.atomic
        calls = []
        cpp = self.source / applier.FILES[0]
        def fail_after_owner_edit(path, data, mode):
            calls.append(path)
            if len(calls) == 2:
                cpp.write_bytes(cpp.read_bytes() + b'\n// Concurrent owner edit; retain.\n')
                raise OSError('Synthetic concurrent failure')
            return real(path, data, mode)
        with mock.patch.object(applier, 'atomic', fail_after_owner_edit):
            with self.assertRaises(OSError):
                self.apply()
        self.assertIn(b'Concurrent owner edit; retain.', cpp.read_bytes())
        self.assertTrue((self.backup / 'INTEGRATION-INCOMPLETE').exists())

    def test_private_outputs_are_exclusive_outside_inputs_and_symlinks_refuse(self):
        expected = applier.write_plan(self.source, self.base / 'plan.json', self.root)
        self.assertEqual(stat.S_IMODE((self.base / 'plan.json').stat().st_mode), 0o600)
        with self.assertRaises(FileExistsError):
            applier.write_plan(self.source, self.base / 'plan.json', self.root)
        with self.assertRaises(ValueError):
            applier.apply(self.source, self.source / 'backup', expected, self.root)
        cpp = self.source / applier.FILES[0]
        external = self.base / 'owner.cpp'
        cpp.rename(external)
        cpp.symlink_to(external)
        with self.assertRaises(ValueError):
            self.apply()
        self.assertEqual(external.read_text(), CPP)

    def test_cli_plan_apply_reapply_and_change_refusal(self):
        plan_file = self.base / 'cli-plan.json'
        def run(*args):
            return subprocess.run([sys.executable, str(TOOL), *map(str, args)], capture_output=True, text=True)
        result = run('plan', self.source, '--output', plan_file)
        self.assertEqual(result.returncode, 0, result.stderr)
        for state in ('applied', 'already_applied'):
            result = run('apply', self.source, '--backup', self.backup, '--plan', plan_file)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], state)
            self.assertFalse(json.loads(result.stdout)['built'])
        cpp = self.source / applier.FILES[0]
        cpp.write_text(cpp.read_text().replace('AppLocalDataLocation', 'GenericDataLocation'))
        result = run('verify', self.source, '--backup', self.backup)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn(str(self.base), result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_optional_controller_applier_composes_in_both_orders(self):
        tool = applier.ROOT / 'tools/apply_controller_check.py'
        if not tool.is_file():
            self.skipTest('Optional controller applier is not present')
        spec = importlib.util.spec_from_file_location('controller_apply_for_composition', tool)
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
        for first in ('notes', 'controller'):
            with self.subTest(first=first):
                case = self.base / first
                case.mkdir()
                source = case / 'source'
                shutil.copytree(self.source, source)
                notes_backup, controller_backup = case / 'notes-backup', case / 'controller-backup'
                def notes():
                    return applier.apply(source, notes_backup, root=self.root)
                def controls():
                    return controller.apply(source, controller_backup)
                for action in (notes, controls) if first == 'notes' else (controls, notes):
                    action()
                before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
                self.assertEqual(notes()['status'], 'already_applied')
                self.assertEqual(controls()['state'], 'already-applied')
                self.assertEqual(before, {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()})


if __name__ == '__main__':
    unittest.main()
