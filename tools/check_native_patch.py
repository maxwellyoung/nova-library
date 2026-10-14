#!/usr/bin/env python3
"""Read-only check of the complete Nova patch against its exact upstream base."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path


def check(source):
    root = Path(__file__).resolve().parents[1]
    pin = json.loads((root / 'native/upstream.json').read_text())
    patch = root / 'native' / pin['patch']
    if hashlib.sha256(patch.read_bytes()).hexdigest() != pin['patchSha256']:
        raise ValueError('Patch differs from the recorded source manifest')
    def git(*args):
        return subprocess.check_output(['git', '-C', str(source), *args], text=True).strip()
    if git('rev-parse', 'HEAD') != pin['commit']:
        raise ValueError('Checkout is not the pinned upstream commit')
    if git('status', '--porcelain', '--untracked-files=all'):
        raise ValueError('Checkout must be clean, including untracked files')
    subprocess.run(['git', '-C', str(source), 'apply', '--check', str(patch)], check=True)
    print('Pinned base is clean; complete native patch applies. No source files changed.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    try:
        check(args.source)
    except (ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'{error}\n')
