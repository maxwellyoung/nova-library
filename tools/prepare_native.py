#!/usr/bin/env python3
"""Prepare and verify a paired Nova native-source/theme build workspace.

Uses a clean local checkout of the pinned upstream and its submodules. Never
fetches, builds, installs, enrolls or changes the input checkout. A failed
preparation remains explicitly incomplete for inspection.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(source, *args):
    return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()


def tree(path):
    """Include new files as well as tracked files; Git internals are not source."""
    if path.is_symlink() or not path.is_dir():
        raise ValueError('Linked or missing source root requires separate review')
    result = {}
    for p in sorted(path.rglob('*')):
        rel = p.relative_to(path)
        if '.git' in rel.parts:
            continue
        if p.is_symlink():
            raise ValueError('Linked source requires separate review: ' + rel.as_posix())
        if p.is_file():
            result[rel.as_posix()] = sha(p)
    return result


def submodules(source):
    result = []
    for line in git(source, 'ls-tree', '-r', 'HEAD').splitlines():
        info, name = line.split('\t', 1)
        mode, kind, commit = info.split()
        if mode == '160000':
            if name.startswith('/') or '..' in Path(name).parts:
                raise ValueError('Unsafe submodule path')
            result.append((name, commit))
    return result


def check_upstream(source, commit):
    if source.is_symlink() or git(source, 'rev-parse', 'HEAD') != commit:
        raise ValueError('Checkout is not the pinned upstream commit')
    if git(source, 'status', '--porcelain', '--untracked-files=all', '--ignore-submodules=none'):
        raise ValueError('Upstream checkout must be clean, including submodules')
    try:
        # qmake derives package version metadata from history. Checking only
        # HEAD/files accepts caches whose parent objects have disappeared.
        subprocess.run(['git', '-C', str(source), 'rev-list', '--count', 'HEAD'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    except subprocess.CalledProcessError as error:
        raise ValueError('Upstream history is incomplete; obtain a clean pinned checkout') from error
    pins = {}
    for name, revision in submodules(source):
        child = source / name
        if not (child / '.git').exists():
            raise ValueError('Initialize pinned submodule: ' + name)
        check_upstream(child, revision)
        pins[name] = revision
    return pins


def clone_local(source, dest, commit):
    subprocess.run(['git', 'clone', '--quiet', '--no-local', '--no-checkout',
                    '--', str(source), str(dest)], check=True)
    subprocess.run(['git', '-C', str(dest), 'checkout', '--quiet', '--detach', commit], check=True)
    for name, revision in submodules(source):
        clone_local(source / name, dest / name, revision)


def prepare(upstream, output, cloud=False, root=ROOT, *, stopping_notes=False, controller_check=False):
    if Path(upstream).is_symlink() or Path(output).is_symlink():
        raise ValueError('Linked workspace roots require separate review')
    upstream, output, root = Path(upstream).resolve(), Path(output).resolve(), Path(root).resolve()
    if output.exists() or output.is_symlink():
        raise ValueError('Output already exists; preserve it and choose a new workspace')
    if upstream == output or upstream in output.parents or root == output or root in output.parents:
        raise ValueError('Build workspace must be outside the input checkout and Nova source')
    spec = json.loads((root / 'native/upstream.json').read_text())
    pins = check_upstream(upstream, spec['commit'])
    patch = root / 'native' / spec['patch']
    if sha(patch) != spec['patchSha256']:
        raise ValueError('Native patch differs from its pinned hash')
    theme_hashes = tree(root / 'theme')
    if not theme_hashes or any(Path(n).suffix not in {'.qml', '.js', '.cfg'} for n in theme_hashes):
        raise ValueError('Theme contains missing or unreviewed file types')
    inputs = {'native/upstream.json': sha(root / 'native/upstream.json'),
              'native/' + spec['patch']: sha(patch),
              'tools/prepare_native.py': sha(root / 'tools/prepare_native.py')}
    if cloud:
        inputs['tools/apply_rom_cloud.py'] = sha(root / 'tools/apply_rom_cloud.py')
        for name in ('RomCloud.cpp', 'RomCloud.h', 'romcloud.pri', 'RomCloudVault.java'):
            inputs['native/romcloud/' + name] = sha(root / 'native/romcloud' / name)
    if stopping_notes:
        inputs['tools/apply_stopping_notes.py'] = sha(root / 'tools/apply_stopping_notes.py')
        for name in ('StoppingNotes.cpp', 'StoppingNotes.h', 'stoppingnotes.pri'):
            inputs['native/stoppingnotes/' + name] = sha(root / 'native/stoppingnotes' / name)
    if controller_check:
        inputs['tools/apply_controller_check.py'] = sha(root / 'tools/apply_controller_check.py')
        for name in ('ControllerCheck.cpp', 'ControllerCheck.h', 'QtGamepadObserver.cpp',
                     'QtGamepadObserver.h', 'ControllerCheckHost.cpp', 'ControllerCheckHost.h', 'controllercheck.pri'):
            inputs['native/controllercheck/' + name] = sha(root / 'native/controllercheck' / name)
    output.mkdir(parents=True, exist_ok=False)
    marker = output / 'PREPARATION-INCOMPLETE'
    marker.write_text('Do not build or distribute this workspace until preparation succeeds.\n')
    source = output / 'source'
    clone_local(upstream, source, spec['commit'])
    check_upstream(source, spec['commit'])
    # The only source bytes copied from upstream are committed Git objects.
    subprocess.run(['git', '-C', str(source), 'apply', '--check', str(patch)], check=True)
    subprocess.run(['git', '-C', str(source), 'apply', str(patch)], check=True)
    if any(sha(source / n) != h for n, h in spec['resultSha256'].items()):
        raise ValueError('Applied native patch does not match its pinned results')
    if cloud:
        subprocess.run(['python3', str(root / 'tools/apply_rom_cloud.py'), str(source),
                        '--backup', str(output / 'cloud-integration-before')], check=True, stdout=subprocess.DEVNULL)
    if stopping_notes:
        subprocess.run(['python3', str(root / 'tools/apply_stopping_notes.py'), 'apply', str(source),
                        '--backup', str(output / 'stopping-notes-integration-before')], check=True, stdout=subprocess.DEVNULL)
    if controller_check:
        subprocess.run(['python3', str(root / 'tools/apply_controller_check.py'), str(source),
                        '--backup', str(output / 'controller-check-integration-before')], check=True, stdout=subprocess.DEVNULL)
    for name, digest in theme_hashes.items():
        data = (root / 'theme' / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('Theme changed during preparation')
        target = output / 'theme' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    if tree(root / 'theme') != theme_hashes or any(sha(root / n) != h for n, h in inputs.items()):
        raise ValueError('Nova inputs changed during preparation')
    check_upstream(upstream, spec['commit'])
    manifest = {'schemaVersion': 1, 'upstream': {'repository': spec['repository'],
                'commit': spec['commit'], 'submodules': pins},
                'components': {'nativeBridge': True, 'romCloud': cloud, 'externalTheme': True,
                               'stoppingNotes': stopping_notes, 'controllerCheck': controller_check},
                'inputs': inputs, 'nativeFiles': tree(source), 'themeFiles': tree(output / 'theme'),
                'limits': ['Source pairing only; not a build or installation receipt.',
                           'Private recorder/service code is not imported from other worktrees.',
                           'Cloud removal remains blocked without its trusted runtime adapter.',
                           'Automatic save synchronization is not enabled.',
                           'Optional native contexts require explicit preparation flags; source inclusion does not establish a UI entry point.',
                           'Controller capture is disabled until explicitly opened; exports remain private and user-requested.']}
    (output / 'nova-build-inputs.json').write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    # Keep the incomplete marker until final native/theme/Git validation passes.
    # A failed final check must not leave a workspace looking ready to build.
    verify_contents(output, manifest)
    marker.unlink()
    return manifest


def verify(output):
    output = Path(output)
    if (output / 'PREPARATION-INCOMPLETE').exists():
        raise ValueError('Preparation is incomplete')
    manifest = json.loads((output / 'nova-build-inputs.json').read_text())
    return verify_contents(output, manifest)


def verify_contents(output, manifest):
    if manifest.get('schemaVersion') != 1:
        raise ValueError('Unsupported build-input manifest')
    source = output / 'source'
    if git(source, 'rev-parse', 'HEAD') != manifest['upstream']['commit']:
        raise ValueError('Prepared upstream identity changed; build receipt is stale')
    pins = dict(submodules(source))
    if pins != manifest['upstream']['submodules'] or any(
            git(source / name, 'rev-parse', 'HEAD') != revision for name, revision in pins.items()):
        raise ValueError('Prepared submodule identity changed; build receipt is stale')
    for folder, key in [('source', 'nativeFiles'), ('theme', 'themeFiles')]:
        if tree(output / folder) != manifest.get(key):
            raise ValueError('Prepared ' + folder + ' changed; build receipt is stale')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    p = commands.add_parser('prepare')
    p.add_argument('upstream', type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--rom-cloud', action='store_true')
    p.add_argument('--stopping-notes', action='store_true')
    p.add_argument('--controller-check', action='store_true')
    p = commands.add_parser('verify')
    p.add_argument('output', type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.upstream, args.output, args.rom_cloud,
                         stopping_notes=args.stopping_notes, controller_check=args.controller_check) if args.command == 'prepare' else verify(args.output)
        print(json.dumps({'nativeFiles': len(result['nativeFiles']), 'themeFiles': len(result['themeFiles']),
                          'components': result['components'], 'verified': True}))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
