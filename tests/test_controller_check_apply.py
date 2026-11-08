import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from tools import apply_controller_check as controller
from tools import apply_stopping_notes as stopping


CPP = '''#include "FrontendLayer.h"
#include "library/DeviceLibrary.h"
// Retained recorder-specific native code.
#include <QQmlContext>
void FrontendLayer::rebuild()
{
    m_engine = new QQmlApplicationEngine(this);
    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);
    m_engine->rootContext()->setContextProperty(QStringLiteral("api"), m_api_public);
    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));
}
'''
PRO = 'TEMPLATE = lib\nQT += qml quick\nSOURCES += library/DeviceLibrary.cpp\n# retained native build settings\n'
CMAKE = 'add_library(pegasus-backend\n    library/DeviceLibrary.cpp\n)\n# retained native build settings\n'


def fixture(root):
    source = root / 'source'
    (source / 'src/backend/library').mkdir(parents=True)
    for name, text in [(controller.CPP, CPP), (controller.PRO, PRO), (controller.CMAKE, CMAKE)]:
        (source / name).write_text(text)
    return source


def snapshot(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


class ControllerApplyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.source = fixture(self.root)
        self.backup = self.root / 'backup'

    def tearDown(self):
        self.tmp.cleanup()

    def test_fresh_source_is_backed_up_and_real_module_is_included(self):
        before = snapshot(self.source)
        result = controller.apply(self.source, self.backup)
        self.assertEqual(result['state'], 'applied')
        for name, value in before.items():
            self.assertEqual((self.backup / name).read_bytes(), value)
        for name in controller.MODULE_FILES:
            self.assertEqual((self.source / controller.TARGET / name).read_bytes(), (controller.ROOT / 'native/controllercheck' / name).read_bytes())
        text = (self.source / controller.CPP).read_text()
        self.assertIn('Retained recorder-specific native code', text)
        self.assertIn('controllercheck::createForApplication(m_engine)', text)
        self.assertEqual(text.count('QStringLiteral("controllerCheck")'), 1)
        self.assertIn('include(library/controllercheck/controllercheck.pri)', (self.source / controller.PRO).read_text())
        self.assertIn('ControllerCheckHost.cpp', (self.source / controller.CMAKE).read_text())
        self.assertEqual(json.loads((self.backup / 'receipt.json').read_text())['state'], 'applied')

    def test_scoped_reapplication_preserves_foreign_independent_integrations(self):
        controller.apply(self.source, self.backup)
        for path in controller.BLOCKS:
            with (self.source / path).open('a') as out:
                out.write('\n// unrelated optional module remains here\n' if path == controller.CPP else '\n# unrelated optional module remains here\n')
        before = snapshot(self.source)
        result = controller.apply(self.source, self.root / 'unused-backup')
        self.assertEqual(result['state'], 'already-applied')
        self.assertEqual(snapshot(self.source), before)
        self.assertFalse((self.root / 'unused-backup').exists())
        self.assertEqual(controller.apply(self.source, self.backup)['state'], 'already-applied')

    def test_changed_own_block_or_module_refuses_without_overwriting(self):
        controller.apply(self.source, self.backup)
        target = self.source / controller.TARGET / 'ControllerCheck.cpp'
        target.write_bytes(target.read_bytes() + b'\n// newer local change\n')
        before = snapshot(self.source)
        with self.assertRaises(ValueError): controller.apply(self.source, self.root / 'unused')
        self.assertEqual(snapshot(self.source), before)
        target.write_bytes((controller.ROOT / 'native/controllercheck/ControllerCheck.cpp').read_bytes())
        path = self.source / controller.CPP
        path.write_text(path.read_text().replace('createForApplication(m_engine)', 'createForApplication(this)'))
        before = snapshot(self.source)
        with self.assertRaises(ValueError): controller.apply(self.source, self.root / 'unused')
        self.assertEqual(snapshot(self.source), before)

    def test_partial_duplicate_and_unmarked_contexts_refuse_before_mutation(self):
        for replacement in [CPP.replace('#include "library/DeviceLibrary.h"', ''), CPP + CPP,
                            CPP + '\n// NOVA_CONTROLLER_CHECK_V1_CONTEXT_BEGIN\n',
                            CPP + '\nsetContextProperty(QStringLiteral("controllerCheck"), old);\n']:
            (self.source / controller.CPP).write_text(replacement)
            before = snapshot(self.source)
            with self.assertRaises(ValueError): controller.apply(self.source, self.backup)
            self.assertEqual(snapshot(self.source), before)
            self.assertFalse(self.backup.exists())

    def test_existing_backup_module_and_backup_inside_source_are_protected(self):
        self.backup.mkdir(); (self.backup / 'keep').write_text('retain')
        before = snapshot(self.source)
        with self.assertRaises(ValueError): controller.apply(self.source, self.backup)
        self.assertEqual(snapshot(self.source), before)
        self.assertEqual((self.backup / 'keep').read_text(), 'retain')
        with self.assertRaises(ValueError): controller.apply(self.source, self.source / 'backup')
        target = self.source / controller.TARGET; target.mkdir(); (target / 'keep').write_text('new source')
        with self.assertRaises(ValueError): controller.apply(self.source, self.root / 'another-backup')
        self.assertEqual((target / 'keep').read_text(), 'new source')

    def test_linked_sources_and_modules_are_not_followed(self):
        alias = self.root / 'alias'; alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(ValueError): controller.apply(alias, self.backup)
        path = self.source / controller.CPP; old = self.root / 'original.cpp'; path.rename(old); path.symlink_to(old)
        with self.assertRaises(ValueError): controller.apply(self.source, self.backup)
        self.assertFalse(self.backup.exists())

    def test_new_foreign_edit_during_staging_is_preserved(self):
        real = controller.tempfile.mkdtemp
        path = self.source / controller.CPP
        def changed(*args, **kwargs):
            staged = real(*args, **kwargs)
            path.write_text(path.read_text() + '// concurrent new edit\n')
            return staged
        with mock.patch.object(controller.tempfile, 'mkdtemp', side_effect=changed):
            with self.assertRaises(ValueError): controller.apply(self.source, self.backup)
        self.assertTrue(path.read_text().endswith('// concurrent new edit\n'))
        self.assertFalse((self.source / controller.TARGET).exists())
        self.assertEqual(json.loads((self.backup / 'receipt.json').read_text())['state'], 'incomplete')

    def test_real_optional_appliers_compose_idempotently_in_both_orders(self):
        for order in [('controller', 'stopping'), ('stopping', 'controller')]:
            base = self.root / '-'.join(order); base.mkdir(); source = fixture(base)
            backups = {name: base / (name + '-backup') for name in order}
            for name in order:
                if name == 'controller': controller.apply(source, backups[name])
                else: stopping.apply(source, backups[name])
            before = snapshot(source)
            self.assertEqual(controller.apply(source, backups['controller'])['state'], 'already-applied')
            self.assertEqual(stopping.apply(source, backups['stopping'])['status'], 'already_applied')
            self.assertEqual(snapshot(source), before)
            cpp = (source / controller.CPP).read_text()
            self.assertEqual(cpp.count('QStringLiteral("controllerCheck")'), 1)
            self.assertEqual(cpp.count('QStringLiteral("stoppingNotes")'), 1)
            self.assertIn('Retained recorder-specific native code', cpp)
            self.assertLess(cpp.index('QStringLiteral("controllerCheck")'), cpp.index('m_engine->load('))
            self.assertLess(cpp.index('QStringLiteral("stoppingNotes")'), cpp.index('m_engine->load('))

    def test_failed_shared_write_recovers_only_own_published_changes(self):
        before = snapshot(self.source)
        real = controller.write_native
        calls = []
        def fail_second(path, data, expected, mode):
            calls.append(path)
            if len(calls) == 2:
                raise OSError('fixture write failure')
            return real(path, data, expected, mode)
        with mock.patch.object(controller, 'write_native', side_effect=fail_second):
            with self.assertRaises(OSError): controller.apply(self.source, self.backup)
        self.assertEqual(snapshot(self.source), before)
        self.assertEqual(json.loads((self.backup / 'receipt.json').read_text())['state'], 'incomplete')

    def test_failed_staging_leaves_backups_and_original_source(self):
        before = snapshot(self.source)
        with mock.patch.object(controller.os, 'rename', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError): controller.apply(self.source, self.backup)
        self.assertEqual(snapshot(self.source), before)
        self.assertEqual((self.backup / controller.CPP).read_text(), CPP)
        self.assertFalse(list((self.source / 'src/backend/library').glob('.controllercheck-*')))


if __name__ == '__main__':
    unittest.main()
