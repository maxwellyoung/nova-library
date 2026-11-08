#!/usr/bin/env python3
"""Apply the pinned HakuX session adapter with a new, verified rollback copy."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def apply(source, backup):
    source, backup = Path(source).resolve(), Path(backup).resolve()
    module = Path(__file__).resolve().parents[1] / 'native' / 'hakux'
    spec = json.loads((module / 'source.json').read_text())
    patch = module / 'hakux-1.2-session.patch'
    if digest(patch) != spec['patchSha256']:
        raise ValueError('The source patch differs from its recorded hash')
    for name, item in spec['helpers'].items():
        if digest(module / name) != item['sha256']:
            raise ValueError('An adapter helper differs from its recorded hash')
    targets = {**spec['after'], **{item['destination']: item['sha256'] for item in spec['helpers'].values()}}
    if all((source / name).is_file() and digest(source / name) == sha for name, sha in targets.items()):
        return 'Matching session adapter is already applied; no files changed.'
    for name, sha in spec['before'].items():
        path = source / name
        if not path.is_file() or path.is_symlink() or digest(path) != sha:
            raise ValueError('Expected unmodified HakuX 1.2 input differs: ' + name)
    for item in spec['helpers'].values():
        if (source / item['destination']).exists():
            raise ValueError('An adapter destination already exists; preserve that work')
    if backup.exists():
        raise ValueError('Backup destination already exists; select a new directory')
    subprocess.run(['git', 'apply', '--check', str(patch)], cwd=source, check=True)
    backup.mkdir(parents=True, exist_ok=False)
    for name in spec['before']:
        target = backup / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / name, target)
    try:
        subprocess.run(['git', 'apply', str(patch)], cwd=source, check=True)
        for name, item in spec['helpers'].items():
            target = source / item['destination']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(module / name, target)
        if not all(digest(source / name) == sha for name, sha in targets.items()):
            raise ValueError('Applied source did not match the recorded result')
    except Exception:
        for name in spec['before']:
            shutil.copy2(backup / name, source / name)
        for item in spec['helpers'].values():
            (source / item['destination']).unlink(missing_ok=True)
        raise
    (backup / 'receipt.json').write_text(json.dumps({'before': spec['before'], 'after': targets}, indent=2) + '\n')
    return 'Session adapter applied and source hashes verified. No build, install or game data changed.'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--backup', required=True, type=Path)
    args = parser.parse_args()
    try:
        print(apply(args.source, args.backup))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(1, str(error) + '\n')
