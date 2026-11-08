#!/usr/bin/env python3
"""Stage the stopping-notebook module and expose its separate native QML API.

Source integration only: no build, install, permission, migration or service action.
Fresh plans bind exact inputs. Reapply verifies owned blocks and module bytes while
preserving other optional integrations; historical whole-file hashes are not a
claim that another integrator has left those shared files unchanged.
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
FILES = ('src/backend/FrontendLayer.cpp', 'src/backend/backend.pro', 'src/backend/CMakeLists.txt')
MODULE = 'src/backend/library/stoppingnotes'
PAYLOAD = ('StoppingNotes.cpp', 'StoppingNotes.h', 'stoppingnotes.pri')
INCLUDE = '#include "library/stoppingnotes/StoppingNotes.h"\n'
CONTEXT = '''    // NOVA_STOPPING_NOTES_V1_BEGIN
    const QString stoppingNotesRoot = QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation);
    m_engine->rootContext()->setContextProperty(QStringLiteral("stoppingNotes"),
        stoppingNotesRoot.isEmpty() ? nullptr : new library::StoppingNotes(
            stoppingNotesRoot + QStringLiteral("/stopping-notes-v1"), m_engine));
    // NOVA_STOPPING_NOTES_V1_END
'''
QMAKE = '''\n# NOVA_STOPPING_NOTES_V1_BEGIN
include(library/stoppingnotes/stoppingnotes.pri)
# NOVA_STOPPING_NOTES_V1_END
'''
CMAKE = '''\n# NOVA_STOPPING_NOTES_V1_BEGIN
target_sources(pegasus-backend PRIVATE
    library/stoppingnotes/StoppingNotes.cpp
    library/stoppingnotes/StoppingNotes.h
)
# NOVA_STOPPING_NOTES_V1_END
'''


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + '\n').encode()


def regular(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Missing, linked or oversized integration input: ' + path.name)
    return path.read_bytes()


def source_root(path):
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Missing or linked source root')
    for relative in FILES + (MODULE,):
        candidate = path
        for part in Path(relative).parts:
            candidate = candidate / part
            if candidate.is_symlink():
                raise ValueError('Linked integration path requires separate review')
    return path.resolve()


def payload(root):
    folder = Path(root) / 'native/stoppingnotes'
    if folder.is_symlink():
        raise ValueError('Linked notebook module requires separate review')
    return {name: regular(folder / name) for name in PAYLOAD}


def replace_line(text, before, after):
    lines = text.splitlines(keepends=True)
    if lines.count(before) != 1:
        raise ValueError('Native integration anchor is missing or ambiguous')
    lines[lines.index(before)] = after
    return ''.join(lines)


def transformed(before):
    texts = {}
    for name, data in before.items():
        try:
            text = data.decode('utf-8')
        except UnicodeError as error:
            raise ValueError('Unsupported native source encoding') from error
        if '\r' in text or not text.endswith('\n'):
            raise ValueError('Unsupported native source line endings')
        if any(token in text for token in ('NOVA_STOPPING_NOTES', 'stoppingnotes/', '"stoppingNotes"', 'stoppingNotesRoot')):
            raise ValueError('Notebook integration already present or partial')
        texts[name] = text
    cpp = texts[FILES[0]]
    for anchor in ('void FrontendLayer::rebuild()\n', '    m_engine = new QQmlApplicationEngine(this);\n',
                   '    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));\n'):
        if cpp.splitlines(keepends=True).count(anchor) != 1:
            raise ValueError('Unsupported FrontendLayer lifecycle context')
    anchor = '    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);\n'
    if not cpp.index('    m_engine = new QQmlApplicationEngine(this);\n') < cpp.index(anchor) < cpp.index('    m_engine->load('):
        raise ValueError('Device Library context is outside the supported engine lifecycle')
    cpp = replace_line(cpp, '#include "library/DeviceLibrary.h"\n', '#include "library/DeviceLibrary.h"\n' + INCLUDE)
    standard = '#include <QStandardPaths>\n'
    if cpp.splitlines(keepends=True).count(standard) > 1:
        raise ValueError('Ambiguous QStandardPaths include')
    if standard not in cpp.splitlines(keepends=True):
        cpp = replace_line(cpp, '#include <QQmlContext>\n', '#include <QQmlContext>\n' + standard)
    texts[FILES[0]] = replace_line(cpp, anchor, anchor + CONTEXT)
    if texts[FILES[1]].splitlines(keepends=True).count('TEMPLATE = lib\n') != 1:
        raise ValueError('Unsupported backend qmake context')
    if texts[FILES[2]].splitlines(keepends=True).count('add_library(pegasus-backend\n') != 1:
        raise ValueError('Unsupported backend CMake target')
    texts[FILES[1]] += QMAKE
    texts[FILES[2]] += CMAKE
    return {name: text.encode() for name, text in texts.items()}


def owned_state(source, expected):
    current = {name: regular(source / name) for name in FILES}
    for relative, block in ((FILES[0], CONTEXT), (FILES[1], QMAKE), (FILES[2], CMAKE)):
        text = current[relative].decode('utf-8')
        if text.count(block) != 1:
            raise ValueError('Installed notebook integration block changed or is ambiguous')
        remaining = text.replace(block, '', 1)
        if relative == FILES[0]:
            if remaining.splitlines(keepends=True).count(INCLUDE) != 1:
                raise ValueError('Installed notebook include changed or is ambiguous')
            remaining = remaining.replace(INCLUDE, '', 1)
            if remaining.splitlines(keepends=True).count('#include <QStandardPaths>\n') != 1:
                raise ValueError('Installed QStandardPaths include changed')
        if any(token in remaining for token in ('NOVA_STOPPING_NOTES', 'stoppingnotes/', '"stoppingNotes"', 'stoppingNotesRoot')):
            raise ValueError('Additional or partial notebook integration requires review')
    target = source / MODULE
    if target.is_symlink() or not target.is_dir() or {p.name for p in target.iterdir()} != set(PAYLOAD):
        raise ValueError('Installed notebook module changed or is incomplete')
    for name, sha in expected.items():
        if digest(regular(target / name)) != sha:
            raise ValueError('Installed notebook module bytes changed')
    return {name: digest(data) for name, data in current.items()}


def plan(source, root=ROOT):
    source = source_root(source)
    if (source / MODULE).exists():
        raise ValueError('Notebook module already exists; use its existing receipt')
    before = {name: regular(source / name) for name in FILES}
    after = transformed(before)
    return {'schemaVersion': 1, 'component': 'stopping-notes-v1',
            'before': {name: digest(data) for name, data in before.items()},
            'after': {name: digest(data) for name, data in after.items()},
            'module': {name: digest(data) for name, data in payload(root).items()},
            'api': 'stoppingNotes', 'storage': 'QStandardPaths::AppLocalDataLocation/stopping-notes-v1',
            'limits': ['Native source integration only; not a build or installation receipt.',
                       'No checkpoint migration, permissions, camera, network or service configuration.',
                       'Reapply verifies owned blocks/module; other shared-source edits are preserved.']}


def output_path(path, source, root=ROOT):
    raw = Path(path).absolute()
    if raw.is_symlink():
        raise ValueError('Linked output path requires separate review')
    resolved = raw.resolve()
    for protected in (source, Path(root).resolve()):
        if resolved == protected or protected in resolved.parents:
            raise ValueError('Private plan and backup must be outside source and repository')
    return resolved


def exclusive(path, data):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def write_plan(source, output, root=ROOT):
    source = source_root(source)
    result = plan(source, root)
    output = output_path(output, source, root)
    output.parent.mkdir(parents=True, exist_ok=True)
    exclusive(output, encoded(result))
    return result


def atomic(path, data, mode):
    descriptor, temporary = tempfile.mkstemp(prefix='.nova-notes-', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def verify(source, backup, root=ROOT):
    source = source_root(source)
    backup = output_path(backup, source, root)
    receipt = json.loads(regular(backup / 'receipt.json'))
    if receipt.get('schemaVersion') != 1 or receipt.get('component') != 'stopping-notes-v1' or set(receipt.get('before', {})) != set(FILES) or set(receipt.get('module', {})) != set(PAYLOAD):
        raise ValueError('Unsupported notebook source receipt')
    if (backup / 'INTEGRATION-INCOMPLETE').exists():
        raise ValueError('Previous integration is incomplete; inspect retained backup')
    for name, sha in receipt['before'].items():
        if digest(regular(backup / name)) != sha:
            raise ValueError('Notebook integration backup changed')
    if {name: digest(data) for name, data in payload(root).items()} != receipt['module']:
        raise ValueError('Notebook module inputs changed; automatic upgrade is refused')
    observed = owned_state(source, receipt['module'])
    return dict(receipt, status='already_applied', observedSharedFiles=observed,
                sharedFilesMatchOriginalReceipt=observed == receipt['after'])


def apply(source, backup, expected=None, root=ROOT):
    source = source_root(source)
    backup = output_path(backup, source, root)
    if backup.exists():
        result = verify(source, backup, root)
        if expected is not None and digest(encoded(expected)) != result['planSha256']:
            raise ValueError('Reapply plan differs from the retained source receipt')
        return result
    current = plan(source, root)
    if expected is not None and current != expected:
        raise ValueError('Native source or module changed after the plan; nothing was written')
    expected = current
    before = {name: regular(source / name) for name in FILES}
    after = transformed(before)
    contents = payload(root)
    if {name: digest(data) for name, data in before.items()} != expected['before'] or {name: digest(data) for name, data in contents.items()} != expected['module']:
        raise ValueError('Integration inputs changed during planning')
    modes = {name: stat.S_IMODE((source / name).stat().st_mode) for name in FILES}
    backup.mkdir(parents=True, mode=0o700, exist_ok=False)
    incomplete = backup / 'INTEGRATION-INCOMPLETE'
    exclusive(incomplete, b'Native source transaction is incomplete. Do not build from it.\n')
    for name, data in before.items():
        dest = backup / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        exclusive(dest, data)
    exclusive(backup / 'before.json', encoded(expected['before']))
    target = source / MODULE
    staged = Path(tempfile.mkdtemp(prefix='.stoppingnotes-stage-', dir=target.parent))
    written, published = [], False
    try:
        for name, data in contents.items():
            exclusive(staged / name, data)
        # Guard all inputs again after the complete recoverable backup exists.
        if any(regular(source / name) != data for name, data in before.items()) or payload(root) != contents or target.exists():
            raise ValueError('Integration inputs changed before publication')
        for name, data in after.items():
            if regular(source / name) != before[name]:
                raise ValueError('Shared native source changed during integration')
            atomic(source / name, data, modes[name])
            written.append(name)
        if target.exists() or target.is_symlink():
            raise ValueError('Notebook module target appeared during integration')
        staged.rename(target)
        published = True
        observed = owned_state(source, expected['module'])
        if observed != expected['after']:
            raise ValueError('Shared native source changed during publication')
        receipt = dict(expected, planSha256=digest(encoded(expected)), status='applied',
                       sourceModes=modes, observedSharedFiles=observed,
                       sharedFilesMatchOriginalReceipt=True)
        exclusive(backup / 'receipt.json', encoded(receipt))
        incomplete.unlink()
        return receipt
    except (OSError, ValueError):
        # Restore only our exact published bytes; never overwrite concurrent edits.
        for name in reversed(written):
            try:
                if regular(source / name) == after[name]:
                    atomic(source / name, before[name], modes[name])
            except (OSError, ValueError):
                pass
        if published:
            try:
                if {p.name for p in target.iterdir()} == set(PAYLOAD) and all(regular(target / n) == contents[n] for n in PAYLOAD):
                    for name in PAYLOAD:
                        (target / name).unlink()
                    target.rmdir()
            except (OSError, ValueError):
                pass
        raise
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('plan'); p.add_argument('source', type=Path); p.add_argument('--output', required=True, type=Path)
    p = commands.add_parser('apply'); p.add_argument('source', type=Path); p.add_argument('--backup', required=True, type=Path); p.add_argument('--plan', type=Path)
    p = commands.add_parser('verify'); p.add_argument('source', type=Path); p.add_argument('--backup', required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'plan':
            result = write_plan(args.source, args.output)
            result['status'] = 'planned'
        elif args.command == 'verify':
            result = verify(args.source, args.backup)
        else:
            expected = json.loads(regular(args.plan)) if args.plan else None
            result = apply(args.source, args.backup, expected)
        print(json.dumps({'status': result['status'], 'api': 'stoppingNotes', 'sourceIntegrationOnly': True,
                          'sharedFilesMatchOriginalReceipt': result.get('sharedFilesMatchOriginalReceipt'),
                          'built': False, 'installed': False}))
    except (OSError, ValueError, KeyError, UnicodeError) as error:
        message = str(error) if isinstance(error, ValueError) else 'Native integration I/O failed; inspect the private backup.'
        parser.exit(1, message + '\n')


if __name__ == '__main__':
    main()
