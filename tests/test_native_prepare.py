import hashlib
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('native_prepare', ROOT / 'tools/prepare_native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def run(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True, stderr=subprocess.DEVNULL).strip()


def repository(path):
    path.mkdir()
    run(path, 'init', '--quiet')
    run(path, 'config', 'user.name', 'Fixture')
    run(path, 'config', 'user.email', 'fixture@' + 'example.test')
    (path / 'input.txt').write_text('upstream\n')
    run(path, 'add', 'input.txt')
    run(path, 'commit', '--quiet', '-m', 'Fixture base')
    return run(path, 'rev-parse', 'HEAD')


class NativePrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.upstream = self.base / 'upstream'
        self.pin = repository(self.upstream)
        self.root = self.base / 'nova'
        for folder in ['native', 'theme', 'tools']:
            (self.root / folder).mkdir(parents=True)
        shutil.copyfile(ROOT / 'tools/prepare_native.py', self.root / 'tools/prepare_native.py')
        (self.root / 'theme/theme.cfg').write_text('name: Synthetic\n')
        (self.upstream / 'input.txt').write_text('patched\n')
        patch = run(self.upstream, 'diff') + '\n'
        (self.upstream / 'input.txt').write_text('upstream\n')
        (self.root / 'native/nova-library.patch').write_text(patch)
        self.manifest = {'repository': 'https://example.test/upstream.git', 'commit': self.pin,
                         'patch': 'nova-library.patch', 'patchSha256': native.sha(self.root / 'native/nova-library.patch'),
                         'resultSha256': {'input.txt': hashlib.sha256(b'patched\n').hexdigest()}}
        self.write_spec()
        self.output = self.base / 'prepared'

    def write_spec(self):
        (self.root / 'native/upstream.json').write_text(json.dumps(self.manifest))

    def prepare(self):
        return native.prepare(self.upstream, self.output, root=self.root)

    def optional_inputs(self):
        backend = self.upstream / 'src/backend'
        (backend / 'library').mkdir(parents=True)
        (backend / 'FrontendLayer.cpp').write_text('#include "library/DeviceLibrary.h"\n#include <QQmlContext>\nvoid FrontendLayer::rebuild()\n{\n    m_engine = new QQmlApplicationEngine(this);\n    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);\n    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));\n}\n')
        (backend / 'backend.pro').write_text('TEMPLATE = lib\nSOURCES += \\\n    library/DeviceLibrary.cpp \\\n    library/PlatformEnrollment.cpp \\\n    Backend.cpp\nHEADERS += \\\n    library/DeviceLibrary.h \\\n    Backend.h\n')
        (backend / 'CMakeLists.txt').write_text('add_library(pegasus-backend\n    library/PlatformEnrollment.cpp\n)\n')
        (backend / 'library/DeviceLibrary.h').write_text('// fixture native bridge\n')
        java = self.upstream / 'src/app/platform/android/src/org/pegasus_frontend/android'
        java.mkdir(parents=True)
        (java / 'MainActivity.java').write_text('// retained fixture activity\n')
        run(self.upstream, 'add', 'src')
        run(self.upstream, 'commit', '--quiet', '-m', 'Fixture native integration anchors')
        self.manifest['commit'] = run(self.upstream, 'rev-parse', 'HEAD')
        self.write_spec()
        payloads = {
            'romcloud': ('RomCloud.cpp', 'RomCloud.h', 'romcloud.pri', 'RomCloudVault.java'),
            'stoppingnotes': ('StoppingNotes.cpp', 'StoppingNotes.h', 'stoppingnotes.pri'),
            'controllercheck': ('ControllerCheck.cpp', 'ControllerCheck.h', 'QtGamepadObserver.cpp',
                                'QtGamepadObserver.h', 'ControllerCheckHost.cpp', 'ControllerCheckHost.h', 'controllercheck.pri'),
        }
        for component, names in payloads.items():
            destination = self.root / 'native' / component
            destination.mkdir()
            for name in names:
                shutil.copyfile(ROOT / 'native' / component / name, destination / name)
            (destination / 'README.md').write_text('Not a runtime dependency\n')
            (destination / 'tst_ignored.cpp').write_text('// Not installed runtime source\n')
        for name in ('apply_rom_cloud.py', 'apply_stopping_notes.py', 'apply_controller_check.py'):
            shutil.copyfile(ROOT / 'tools' / name, self.root / 'tools' / name)
        return payloads

    def test_pc_runtime_is_explicit_and_paired_without_other_optional_modules(self):
        self.optional_inputs()
        manifest=self.upstream/'src/app/platform/android/AndroidManifest.xml'
        manifest.write_text('<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application /></manifest>')
        run(self.upstream,'add','src');run(self.upstream,'commit','--quiet','-m','Fixture Android manifest')
        self.manifest['commit']=run(self.upstream,'rev-parse','HEAD');self.write_spec()
        destination=self.root/'native/pcgames';destination.mkdir()
        for name in ('PcRuntime.h','PcRuntime.cpp','pcgames.pri','PcLaunchContract.java','PcRuntimeBridge.java'):
            shutil.copyfile(ROOT/'native/pcgames'/name,destination/name)
        shutil.copyfile(ROOT/'tools/apply_pc_runtime.py',self.root/'tools/apply_pc_runtime.py')
        result=native.prepare(self.upstream,self.output,False,self.root,pc_runtime=True)
        self.assertTrue(result['components']['pcRuntime'])
        self.assertFalse(result['components']['romCloud'])
        self.assertTrue((self.output/'source/src/backend/library/pcgames/PcRuntime.cpp').is_file())
        self.assertTrue((self.output/'source/src/app/platform/android/src/org/pegasus_frontend/android/PcRuntimeBridge.java').is_file())
        self.assertEqual(native.verify(self.output),result)

    def test_shallow_cache_clone_retains_a_valid_history_boundary(self):
        (self.upstream / 'history.txt').write_text('A later committed object\n')
        run(self.upstream, 'add', 'history.txt')
        run(self.upstream, 'commit', '--quiet', '-m', 'Fixture second commit')
        self.manifest['commit'] = run(self.upstream, 'rev-parse', 'HEAD')
        self.write_spec()
        shallow = self.base / 'shallow-cache'
        subprocess.run(['git', 'clone', '--quiet', '--depth=1', self.upstream.as_uri(), str(shallow)], check=True)
        self.upstream = shallow
        self.assertEqual(run(shallow, 'rev-parse', '--is-shallow-repository'), 'true')
        self.prepare()
        clone = self.output / 'source'
        self.assertEqual(run(clone, 'rev-list', '--count', 'HEAD'), '1')
        self.assertEqual(run(clone, 'rev-parse', '--is-shallow-repository'), 'true')
        self.assertEqual((clone / 'input.txt').read_text(), 'patched\n')

    def test_optional_flags_default_off_and_original_positional_api_survives(self):
        self.optional_inputs()
        result = native.prepare(self.upstream, self.output, False, self.root)
        self.assertIs(result['components']['stoppingNotes'], False)
        self.assertIs(result['components']['controllerCheck'], False)
        for component in ('stoppingnotes', 'controllercheck', 'romcloud'):
            self.assertFalse((self.output / 'source/src/backend/library' / component).exists())
            self.assertFalse(any(component in name for name in result['inputs']))

    def test_both_optional_modules_follow_cloud_and_bind_only_runtime_inputs(self):
        payloads = self.optional_inputs()
        result = native.prepare(self.upstream, self.output, True, self.root,
                                stopping_notes=True, controller_check=True)
        self.assertEqual(result['components'], {'nativeBridge': True, 'romCloud': True, 'externalTheme': True,
                                                'stoppingNotes': True, 'controllerCheck': True, 'pcRuntime': False})
        for component, names in payloads.items():
            for name in names:
                input_name = 'native/' + component + '/' + name
                self.assertEqual(result['inputs'][input_name], native.sha(self.root / input_name))
            self.assertNotIn('native/' + component + '/README.md', result['inputs'])
            self.assertNotIn('native/' + component + '/tst_ignored.cpp', result['inputs'])
        for name in ('tools/apply_rom_cloud.py', 'tools/apply_stopping_notes.py', 'tools/apply_controller_check.py'):
            self.assertEqual(result['inputs'][name], native.sha(self.root / name))
        for component in ('stoppingnotes', 'controllercheck'):
            for name in payloads[component]:
                target = 'src/backend/library/' + component + '/' + name
                self.assertEqual(result['nativeFiles'][target], native.sha(self.root / 'native' / component / name))
        for backup in ('cloud-integration-before', 'stopping-notes-integration-before', 'controller-check-integration-before'):
            self.assertTrue((self.output / backup).is_dir())
            self.assertFalse((self.output / 'source' / backup).exists())
        self.assertEqual(native.verify(self.output), result)
        self.assertFalse((self.output / 'PREPARATION-INCOMPLETE').exists())

    def test_each_optional_flag_can_be_selected_independently(self):
        self.optional_inputs()
        for keyword, selected, excluded in [('stopping_notes', 'stoppingnotes', 'controllercheck'),
                                            ('controller_check', 'controllercheck', 'stoppingnotes')]:
            output = self.base / selected
            result = native.prepare(self.upstream, output, root=self.root, **{keyword: True})
            self.assertTrue((output / 'source/src/backend/library' / selected).is_dir())
            self.assertFalse((output / 'source/src/backend/library' / excluded).exists())
            self.assertFalse(any(excluded in name for name in result['inputs']))

    def test_optional_payload_drift_retains_incomplete_marker(self):
        self.optional_inputs()
        real_run = subprocess.run
        def changed(command, *args, **kwargs):
            result = real_run(command, *args, **kwargs)
            if len(command) > 1 and str(command[1]).endswith('apply_controller_check.py'):
                with (self.root / 'native/controllercheck/ControllerCheck.cpp').open('a') as out:
                    out.write('\n// changed during preparation\n')
            return result
        with mock.patch.object(native.subprocess, 'run', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'inputs changed'):
                native.prepare(self.upstream, self.output, root=self.root, controller_check=True)
        self.assertTrue((self.output / 'PREPARATION-INCOMPLETE').exists())
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            native.verify(self.output)

    def test_optional_applier_failure_retains_incomplete_marker(self):
        self.optional_inputs()
        real_run = subprocess.run
        def failed(command, *args, **kwargs):
            if len(command) > 1 and str(command[1]).endswith('apply_stopping_notes.py'):
                raise subprocess.CalledProcessError(1, command)
            return real_run(command, *args, **kwargs)
        with mock.patch.object(native.subprocess, 'run', side_effect=failed):
            with self.assertRaises(subprocess.CalledProcessError):
                native.prepare(self.upstream, self.output, root=self.root, stopping_notes=True)
        self.assertTrue((self.output / 'PREPARATION-INCOMPLETE').exists())
        self.assertFalse((self.output / 'nova-build-inputs.json').exists())

    def test_final_validation_failure_cannot_clear_incomplete_marker(self):
        real_verify = native.verify_contents
        def changed(output, manifest):
            (output / 'source/input.txt').write_text('changed after final snapshot')
            return real_verify(output, manifest)
        with mock.patch.object(native, 'verify_contents', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'stale'):
                self.prepare()
        self.assertTrue((self.output / 'PREPARATION-INCOMPLETE').exists())
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            native.verify(self.output)

    def test_optional_cli_flags_are_explicit(self):
        self.optional_inputs()
        result = subprocess.run(['python3', str(self.root / 'tools/prepare_native.py'), 'prepare',
                                 str(self.upstream), '--output', str(self.output), '--rom-cloud',
                                 '--stopping-notes', '--controller-check'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        summary = json.loads(result.stdout)
        self.assertTrue(summary['verified'])
        self.assertTrue(summary['components']['stoppingNotes'])
        self.assertTrue(summary['components']['controllerCheck'])

    def test_pairing_is_repeatable_and_preserves_upstream(self):
        before = native.tree(self.upstream)
        first = self.prepare()
        self.assertEqual(native.verify(self.output), first)
        self.assertEqual(native.tree(self.upstream), before)
        self.assertEqual((self.output / 'source/input.txt').read_text(), 'patched\n')
        self.assertEqual((self.output / 'theme/theme.cfg').read_text(), 'name: Synthetic\n')
        second = native.prepare(self.upstream, self.base / 'second', root=self.root)
        self.assertEqual(first, second)
        self.assertNotIn(str(self.base), (self.output / 'nova-build-inputs.json').read_text())

    def test_changed_and_extra_native_files_invalidate_receipt(self):
        self.prepare()
        (self.output / 'source/extra.txt').write_text('unrecorded')
        with self.assertRaisesRegex(ValueError, 'stale'):
            native.verify(self.output)
        (self.output / 'source/extra.txt').unlink()
        (self.output / 'source/input.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'stale'):
            native.verify(self.output)

    def test_theme_drift_and_symlinks_invalidate_receipt(self):
        self.prepare()
        p = self.output / 'theme/theme.cfg'
        p.write_text('other')
        with self.assertRaisesRegex(ValueError, 'stale'):
            native.verify(self.output)
        p.unlink()
        p.symlink_to(self.root / 'theme/theme.cfg')
        with self.assertRaisesRegex(ValueError, 'Linked'):
            native.verify(self.output)

    def test_existing_output_and_input_nested_destination_are_preserved(self):
        self.output.mkdir()
        (self.output / 'keep').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.prepare()
        self.assertEqual((self.output / 'keep').read_text(), 'keep')
        with self.assertRaisesRegex(ValueError, 'outside'):
            native.prepare(self.upstream, self.upstream / 'build', root=self.root)
        with self.assertRaisesRegex(ValueError, 'outside'):
            native.prepare(self.upstream, self.root / 'build', root=self.root)

    def test_wrong_revision_dirty_and_untracked_inputs_are_refused_before_output(self):
        self.manifest['commit'] = '0' * 40
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'pinned'):
            self.prepare()
        self.manifest['commit'] = self.pin
        self.write_spec()
        (self.upstream / 'private.txt').write_text('keep outside build')
        with self.assertRaisesRegex(ValueError, 'clean'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_patch_hash_and_result_mismatch_do_not_create_a_ready_workspace(self):
        self.manifest['patchSha256'] = '0' * 64
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'pinned hash'):
            self.prepare()
        self.assertFalse(self.output.exists())
        self.manifest['patchSha256'] = native.sha(self.root / 'native/nova-library.patch')
        self.manifest['resultSha256']['input.txt'] = '0' * 64
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'pinned results'):
            self.prepare()
        self.assertTrue((self.output / 'PREPARATION-INCOMPLETE').is_file())
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            native.verify(self.output)

    def test_unreviewed_theme_artifact_is_refused(self):
        (self.root / 'theme/private.db').write_text('not source')
        with self.assertRaisesRegex(ValueError, 'unreviewed'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_incomplete_git_history_is_refused_before_output(self):
        parent = self.pin
        (self.upstream / 'another.txt').write_text('second commit')
        run(self.upstream, 'add', 'another.txt')
        run(self.upstream, 'commit', '--quiet', '-m', 'Child of missing parent')
        self.manifest['commit'] = run(self.upstream, 'rev-parse', 'HEAD')
        self.write_spec()
        # The working files and HEAD are intact, but qmake's history-derived
        # version would fail. This recreates an incomplete source cache.
        (self.upstream / '.git/objects' / parent[:2] / parent[2:]).unlink()
        with self.assertRaisesRegex(ValueError, 'history is incomplete'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_linked_prepared_root_is_not_accepted(self):
        self.prepare()
        original = self.output / 'theme'
        original.rename(self.output / 'theme-original')
        original.symlink_to(self.output / 'theme-original', target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'Linked'):
            native.verify(self.output)

    def test_git_identity_drift_is_refused_even_when_source_bytes_match(self):
        self.prepare()
        source = self.output / 'source'
        run(source, 'config', 'user.name', 'Fixture')
        run(source, 'config', 'user.email', 'fixture@' + 'example.test')
        # Git metadata participates in qmake's version fields. A changed HEAD
        # with identical file bytes must not keep claiming the original base.
        run(source, 'commit', '--quiet', '--allow-empty', '-m', 'Different identity')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            native.verify(self.output)

    def test_pinned_submodule_is_copied_offline_and_drift_is_rejected(self):
        child = self.base / 'child'
        revision = repository(child)
        run(self.upstream, '-c', 'protocol.file.allow=always', 'submodule', 'add', '--quiet', str(child), 'thirdparty/fixture')
        run(self.upstream, 'commit', '--quiet', '-am', 'Pinned submodule')
        self.manifest['commit'] = run(self.upstream, 'rev-parse', 'HEAD')
        self.write_spec()
        result = self.prepare()
        self.assertEqual(result['upstream']['submodules'], {'thirdparty/fixture': revision})
        self.assertEqual((self.output / 'source/thirdparty/fixture/input.txt').read_text(), 'upstream\n')
        (self.upstream / 'thirdparty/fixture/input.txt').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'clean'):
            native.prepare(self.upstream, self.base / 'third', root=self.root)


if __name__ == '__main__':
    unittest.main()
