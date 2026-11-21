#!/usr/bin/env python3
"""Wire the optional read-only save-copy context into a prepared native source."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parents[1]
FILES=('src/backend/FrontendLayer.cpp','src/backend/backend.pro','src/backend/CMakeLists.txt')
PAYLOAD=('SaveCopies.h','SaveCopies.cpp','SaveCopyPictureProvider.h','SaveCopyPictureProvider.cpp','savecopies.pri')
MODULE='src/backend/library/savecopies'
MARKER='NOVA_SAVE_COPIES_V1'


def regular(path):
    if any(p.is_symlink() for p in (path,*path.parents)) or not path.is_file() or path.stat().st_size>2*1024*1024:
        raise ValueError('Missing, linked or oversized integration source')
    return path.read_bytes()


def apply(source,backup,*,module=None):
    source,backup=Path(source).absolute(),Path(backup).absolute()
    module=Path(module or ROOT/'native/savecopies')
    if any(p.is_symlink() for p in (source,*source.parents,backup,*backup.parents)):
        raise ValueError('Canonical integration paths required')
    if not source.is_dir() or not backup.parent.is_dir() or backup.exists() or source==backup or source in backup.parents or ROOT==backup or ROOT in backup.parents:
        raise ValueError('Choose a new backup outside native and product source')
    before={n:regular(source/n) for n in FILES};payload={n:regular(module/n) for n in PAYLOAD}
    target=source/MODULE
    if target.exists() or target.is_symlink() or not target.parent.is_dir():raise ValueError('Save-copy module already exists or its parent is unavailable')
    texts={n:data.decode() for n,data in before.items()}
    if any(MARKER in s or 'library/savecopies/' in s or 'QStringLiteral("saveCopies")' in s for s in texts.values()):raise ValueError('Existing or partial save-copy integration requires review')
    cpp=texts[FILES[0]];anchor='    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);'
    create='    m_engine = new QQmlApplicationEngine(this);';load='    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));'
    if any(cpp.count(x)!=1 for x in (anchor,create,load,'#include "library/DeviceLibrary.h"')) or not cpp.index(create)<cpp.index(anchor)<cpp.index(load):raise ValueError('Unsupported native context lifecycle')
    include='#include <QStandardPaths>'
    if cpp.count(include)>1:raise ValueError('Ambiguous standard-paths include')
    if cpp.count('#include <QFileInfo>')==0:include+='\n#include <QFileInfo>'
    if include not in cpp:
        if cpp.count('#include <QQmlContext>')!=1:raise ValueError('Missing native include anchor')
        cpp=cpp.replace('#include <QQmlContext>','#include <QQmlContext>\n'+include,1)
    cpp=cpp.replace('#include "library/DeviceLibrary.h"','#include "library/DeviceLibrary.h"\n#include "library/savecopies/SaveCopies.h"',1)
    cpp=cpp.replace(anchor,anchor+'''\n    // NOVA_SAVE_COPIES_V1: immutable operator-delivered copies, never live restore.
    // Android app data isolation makes /data/user/0 a link to /data/data inside the
    // app's own mount namespace. Resolve that system-owned ancestor once here; the
    // reader still refuses any link or alias at or below its own root.
    const QString saveCopiesRoot = QFileInfo(QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation)).canonicalFilePath();
    m_engine->rootContext()->setContextProperty(QStringLiteral("saveCopies"), saveCopiesRoot.isEmpty() ? nullptr : new library::SaveCopies(
        saveCopiesRoot + QStringLiteral("/save-copies-v1"), m_engine));''',1)
    after={FILES[0]:cpp.encode(),FILES[1]:(texts[FILES[1]]+'\n# '+MARKER+'\ninclude(library/savecopies/savecopies.pri)\n').encode(),
           FILES[2]:(texts[FILES[2]]+'\n# '+MARKER+'\ntarget_sources(pegasus-backend PRIVATE library/savecopies/SaveCopies.cpp library/savecopies/SaveCopies.h library/savecopies/SaveCopyPictureProvider.cpp library/savecopies/SaveCopyPictureProvider.h)\n').encode()}
    if texts[FILES[1]].count('TEMPLATE = lib')!=1 or texts[FILES[2]].count('add_library(pegasus-backend')!=1:raise ValueError('Unsupported native build anchors')
    backup.mkdir(mode=0o700)
    for name,data in before.items():
        dest=backup/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);dest.chmod(0o600)
    changed=[]
    try:
        if any(regular(source/n)!=data for n,data in before.items()):raise ValueError('Source changed before integration')
        target.mkdir()
        for name,data in payload.items():(target/name).write_bytes(data)
        for name,data in after.items():
            if regular(source/name)!=before[name]:raise ValueError('Shared native source changed during integration')
            with tempfile.NamedTemporaryFile(dir=(source/name).parent,delete=False) as stream:
                temp=Path(stream.name);stream.write(data)
            try:os.replace(temp,source/name)
            finally:temp.unlink(missing_ok=True)
            changed.append(name)
        if any(regular(source/n)!=data for n,data in after.items()) or any(regular(target/n)!=data for n,data in payload.items()):raise ValueError('Integration readback differs')
        receipt={'state':'applied','module':'savecopies','before':{n:hashlib.sha256(d).hexdigest() for n,d in before.items()},'after':{n:hashlib.sha256(d).hexdigest() for n,d in after.items()},'payload':{n:hashlib.sha256(d).hexdigest() for n,d in payload.items()}}
        (backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
    except BaseException:
        for name in reversed(changed):
            if regular(source/name)==after[name]:(source/name).write_bytes(before[name])
        if target.is_dir() and {p.name for p in target.iterdir()}==set(payload) and all(regular(target/n)==data for n,data in payload.items()):
            for name in payload:(target/name).unlink()
            target.rmdir()
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('--backup',type=Path,required=True);args=parser.parse_args()
    try:apply(args.source,args.backup);print('Read-only save-copy native context integrated; no build or deployment.')
    except (ValueError,OSError):parser.exit(1,'Save-copy source integration refused; preserve the source and inspect its backup.\n')
