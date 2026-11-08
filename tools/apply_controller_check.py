#!/usr/bin/env python3
"""Add the optional controller-check context to a patched native source copy.

No build, installation, permission, device, UI or service change. Serialise optional
appliers against a given source copy. Unrelated native edits remain in place.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MODULE_FILES = ('ControllerCheck.h', 'ControllerCheck.cpp', 'QtGamepadObserver.h',
                'QtGamepadObserver.cpp', 'ControllerCheckHost.h', 'ControllerCheckHost.cpp',
                'controllercheck.pri')
TARGET = Path('src/backend/library/controllercheck')
CPP = Path('src/backend/FrontendLayer.cpp')
PRO = Path('src/backend/backend.pro')
CMAKE = Path('src/backend/CMakeLists.txt')
INCLUDE = '''// NOVA_CONTROLLER_CHECK_V1_INCLUDE_BEGIN
#include "library/controllercheck/ControllerCheckHost.h"
// NOVA_CONTROLLER_CHECK_V1_INCLUDE_END'''
CONTEXT = '''    // NOVA_CONTROLLER_CHECK_V1_CONTEXT_BEGIN
    m_engine->rootContext()->setContextProperty(QStringLiteral("controllerCheck"),
        controllercheck::createForApplication(m_engine));
    // NOVA_CONTROLLER_CHECK_V1_CONTEXT_END'''
QMAKE = '''# NOVA_CONTROLLER_CHECK_V1_BEGIN
!isEmpty(USE_SDL_GAMEPAD): error(Nova controller check requires the QtGamepad backend)
include(library/controllercheck/controllercheck.pri)
# NOVA_CONTROLLER_CHECK_V1_END'''
CMAKE_BLOCK = '''# NOVA_CONTROLLER_CHECK_V1_BEGIN
if(PEGASUS_USE_SDL2_GAMEPAD)
    message(FATAL_ERROR "Nova controller check requires the QtGamepad backend")
endif()
target_sources(pegasus-backend PRIVATE
    library/controllercheck/ControllerCheck.cpp
    library/controllercheck/ControllerCheck.h
    library/controllercheck/QtGamepadObserver.cpp
    library/controllercheck/QtGamepadObserver.h
    library/controllercheck/ControllerCheckHost.cpp
    library/controllercheck/ControllerCheckHost.h
)
# NOVA_CONTROLLER_CHECK_V1_END'''
BLOCKS = {CPP: (INCLUDE, CONTEXT), PRO: (QMAKE,), CMAKE: (CMAKE_BLOCK,)}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical_directory(path):
    path = Path(path).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or not part.is_dir():
            raise ValueError('Canonical existing directories are required')
    return path.resolve()


def regular(path):
    canonical_directory(path.parent)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Missing, linked or oversized native source file')
    return path.read_bytes()


def exact_block(text, block):
    first, last = block.splitlines()[0].strip(), block.splitlines()[-1].strip()
    return text.count(block) == 1 and text.count(first) == 1 and text.count(last) == 1



def write_native(path, data, expected, mode):
    descriptor, temporary = tempfile.mkstemp(prefix='.controllercheck-write-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        if regular(path) != expected:
            raise ValueError('Native input changed before publication; newer edits preserved')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(source, backup, *, module=None):
    source = canonical_directory(source)
    backup = Path(backup).absolute()
    module = canonical_directory(module or ROOT / 'native/controllercheck')
    backup = canonical_directory(backup.parent) / backup.name
    if backup == source or source in backup.parents or backup == module or module in backup.parents or backup == ROOT or ROOT in backup.parents:
        raise ValueError('Backup must be outside the source and module')
    inputs = {name: regular(module / name) for name in MODULE_FILES}
    before = {path: regular(source / path) for path in BLOCKS}
    text = {path: data.decode('utf-8') for path, data in before.items()}
    modes = {path: stat.S_IMODE((source / path).stat().st_mode) for path in before}
    target = source / TARGET
    include_anchor = '#include "library/DeviceLibrary.h"'
    context_anchor = '    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);'
    lifecycle = ('void FrontendLayer::rebuild()', '    m_engine = new QQmlApplicationEngine(this);',
                 '    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));')
    if any(text[CPP].splitlines().count(line) != 1 for line in lifecycle):
        raise ValueError('Unsupported frontend engine lifecycle')
    if text[CPP].count(include_anchor) != 1 or text[CPP].count(context_anchor) != 1:
        raise ValueError('Patched frontend anchors are missing or ambiguous')
    if not text[CPP].index(lifecycle[1]) < text[CPP].index(context_anchor) < text[CPP].index(lifecycle[2]):
        raise ValueError('Controller context must belong to the rebuilt engine')
    present = [exact_block(text[path], block) for path, blocks in BLOCKS.items() for block in blocks]
    if any(present):
        if not all(present) or not target.is_dir() or target.is_symlink():
            raise ValueError('Partial or changed controller integration; preserve and inspect it')
        for path, blocks in BLOCKS.items():
            remaining = text[path]
            for block in blocks:
                remaining = remaining.replace(block, '', 1)
            if 'NOVA_CONTROLLER_CHECK_V1' in remaining or 'library/controllercheck/' in remaining or 'QStringLiteral("controllerCheck")' in remaining:
                raise ValueError('Additional controller integration requires review')
        if not text[CPP].index(lifecycle[1]) < text[CPP].index(CONTEXT) < text[CPP].index(lifecycle[2]):
            raise ValueError('Controller context moved outside the supported engine lifecycle')
        if {p.name for p in target.iterdir()} != set(MODULE_FILES):
            raise ValueError('Unexpected controller module files; preserve them')
        if any(regular(target / name) != data for name, data in inputs.items()):
            raise ValueError('Controller module differs from current source; no replacement attempted')
        return {'state': 'already-applied', 'moduleHashes': {n: sha(d) for n, d in inputs.items()},
                'observedIntegrationHashes': {str(p): sha(d) for p, d in before.items()},
                'boundary': 'Own blocks/module verified; foreign native source is preserved, not certified.'}
    if target.exists() or target.is_symlink() or any('NOVA_CONTROLLER_CHECK_V1' in s or 'library/controllercheck/' in s or 'QStringLiteral("controllerCheck")' in s for s in text.values()):
        raise ValueError('Existing controller source or markers require review')
    if 'library/DeviceLibrary.cpp' not in text[PRO] or 'add_library(pegasus-backend' not in text[CMAKE]:
        raise ValueError('Expected patched native build anchors are missing')
    after = {
        CPP: text[CPP].replace(include_anchor, include_anchor + '\n' + INCLUDE, 1)
            .replace(context_anchor, context_anchor + '\n' + CONTEXT, 1).encode(),
        PRO: (text[PRO] + '\n' + QMAKE + '\n').encode(),
        CMAKE: (text[CMAKE] + '\n' + CMAKE_BLOCK + '\n').encode(),
    }
    if backup.exists() or backup.is_symlink():
        raise ValueError('Backup already exists; choose a new private directory')
    canonical_directory(target.parent)
    # All refusal checks precede mutation. Shared files are rechecked before write;
    # another applier must not run concurrently on the same native source copy.
    backup.mkdir(mode=0o700)
    for path, data in before.items():
        saved = backup / path
        saved.parent.mkdir(parents=True, exist_ok=True)
        saved.write_bytes(data)
    receipt = {'schemaVersion': 1, 'state': 'preparing', 'integration': 'nova-controller-check-v1',
               'before': {str(p): sha(d) for p, d in before.items()},
               'afterAtApplication': {str(p): sha(d) for p, d in after.items()},
               'moduleHashes': {n: sha(d) for n, d in inputs.items()},
               'scope': 'Whole-file hashes are dated application evidence; scoped idempotence permits other independent marked integrations.'}
    (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    staged, written, published = None, [], False
    try:
        staged = Path(tempfile.mkdtemp(prefix='.controllercheck-', dir=target.parent))
        for name, data in inputs.items():
            (staged / name).write_bytes(data)
        if any(regular(source / path) != data for path, data in before.items()):
            raise ValueError('Native input changed during preparation; newer edits preserved')
        os.rename(staged, target)
        published = True
        for path, data in after.items():
            if regular(source / path) != before[path]:
                raise ValueError('Native input changed during application; newer edits preserved')
            write_native(source / path, data, before[path], modes[path])
            written.append(path)
        if any(regular(source / path) != data for path, data in after.items()):
            raise ValueError('Native integration changed before verification')
    except Exception:
        receipt['state'] = 'incomplete'
        for path in written:
            # Never replace a newer foreign edit while recovering our own writes.
            try:
                if regular(source / path) == after[path]:
                    write_native(source / path, before[path], after[path], modes[path])
            except (OSError, ValueError):
                pass
        if published and target.is_dir() and not target.is_symlink():
            if {p.name for p in target.iterdir()} == set(inputs) and all(regular(target / n) == d for n, d in inputs.items()):
                shutil.rmtree(target)
        try:
            (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        except OSError:
            pass
        raise
    finally:
        if staged is not None and staged.exists() and staged != target:
            shutil.rmtree(staged)
    receipt['state'] = 'applied'
    (backup / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return {'state': 'applied', 'moduleHashes': receipt['moduleHashes'],
            'observedIntegrationHashes': receipt['afterAtApplication'],
            'boundary': 'Source only; disabled by default, private explicit exports; no build, UI, permission or device change.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--backup', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(apply(args.source, args.backup), indent=2))
    except (OSError, ValueError, UnicodeError):
        parser.exit(1, 'Controller-check source integration refused; inspect inputs and retained backup. No device or service was changed.\n')
