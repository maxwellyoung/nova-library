#!/usr/bin/env python3
"""Prepare checked atomic theme-memory source from exact pinned inputs. Never builds/installs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TARGET=Path('src/backend/model/memory')
FILES=('Memory.h','Memory.cpp')

def regular(path):
    if any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file() or path.stat().st_size>1024*1024:
        raise ValueError('Canonical bounded source files required')
    return path.read_bytes()

def apply(source,backup,*,module=None):
    source=Path(source).absolute();backup=Path(backup).absolute();module=Path(module or ROOT/'native/theme-memory').absolute()
    if any(p.is_symlink() for p in (source,backup,*source.parents,*backup.parents)):
        raise ValueError('Linked source or backup refused')
    if not source.is_dir() or not backup.parent.is_dir() or backup.exists() or source==backup or source in backup.parents:
        raise ValueError('New backup outside the source required')
    pins=json.loads(regular(module/'upstream.json'))['files']
    before={name:regular(source/TARGET/name) for name in FILES}
    after={name:regular(module/name) for name in FILES}
    if any(hashlib.sha256(before[n]).hexdigest()!=pins.get(n) for n in FILES):
        raise ValueError('Theme-memory input differs from the exact pinned source')
    if b'NOVA_CHECKED_THEME_MEMORY_V1' not in after['Memory.cpp'] or b'checkedSet' not in after['Memory.h']:
        raise ValueError('Checked-memory implementation missing')
    backup.mkdir(mode=0o700)
    for name in FILES:
        (backup/name).write_bytes(before[name]);(backup/name).chmod(0o600)
    # Preparing a disposable source pair, not a live application. Preserve rollback inputs on any error.
    for name in FILES:
        if regular(source/TARGET/name)!=before[name]:raise ValueError('Source changed during preparation')
    for name in FILES:(source/TARGET/name).write_bytes(after[name])
    receipt={'schemaVersion':1,'kind':'checked-theme-memory-source','before':pins,
             'after':{n:hashlib.sha256(after[n]).hexdigest() for n in FILES},'built':False,'installed':False}
    (backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--backup',required=True,type=Path);args=p.parse_args()
    try:print(json.dumps(apply(args.source,args.backup),sort_keys=True))
    except (ValueError,OSError,KeyError,json.JSONDecodeError) as e:p.exit(1,str(e)+'\n')
