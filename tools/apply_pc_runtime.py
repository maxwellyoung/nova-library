#!/usr/bin/env python3
"""Prepare the optional public PC-game launch bridge. No build, install or enrollment."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
MODULE_FILES=('PcRuntime.h','PcRuntime.cpp','pcgames.pri')
JAVA_FILES=('PcLaunchContract.java','PcRuntimeBridge.java')
TARGET=Path('src/backend/library/pcgames')
JAVA=Path('src/app/platform/android/src/org/pegasus_frontend/android')
CPP=Path('src/backend/FrontendLayer.cpp')
PRO=Path('src/backend/backend.pro')
CMAKE=Path('src/backend/CMakeLists.txt')
MANIFEST=Path('src/app/platform/android/AndroidManifest.xml')


def regular(path):
    for parent in (path,*path.parents):
        if parent.is_symlink():raise ValueError('Linked source requires review')
    if not path.is_file() or path.stat().st_size>2*1024*1024:raise ValueError('Missing or oversized source file')
    return path.read_bytes()


def apply(source,backup,*,module=None):
    original=Path(source).absolute()
    if any(p.is_symlink() for p in (original,*original.parents)):raise ValueError('Canonical source required')
    source=original.resolve();backup=Path(backup).absolute();module=Path(module or ROOT/'native/pcgames')
    if any(p.is_symlink() for p in (backup,*backup.parents)) or not backup.parent.is_dir():raise ValueError('Canonical backup parent required')
    if backup.exists() or backup==source or source in backup.parents or backup==ROOT or ROOT in backup.parents:raise ValueError('New backup outside the source is required')
    before={p:regular(source/p) for p in (CPP,PRO,CMAKE,MANIFEST)}
    inputs={name:regular(module/name) for name in MODULE_FILES+JAVA_FILES}
    target=source/TARGET
    if target.exists() or target.is_symlink() or any((source/JAVA/name).exists() or (source/JAVA/name).is_symlink() for name in JAVA_FILES):raise ValueError('PC integration exists; preserve and inspect it')
    for folder in (target.parent,source/JAVA):
        if not folder.is_dir() or any(p.is_symlink() for p in (folder,*folder.parents)):raise ValueError('Native module parents require review')
    texts={p:b.decode() for p,b in before.items()}
    if any('NOVA_PC_RUNTIME_V1' in s or 'QStringLiteral("pcRuntime")' in s or 'library/pcgames/' in s for s in texts.values()):raise ValueError('Partial PC integration requires review')
    include='#include "library/DeviceLibrary.h"'
    context='    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);'
    create='    m_engine = new QQmlApplicationEngine(this);'
    load='    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));'
    if any(texts[CPP].count(a)!=1 for a in (include,context,create,load)) or not texts[CPP].index(create)<texts[CPP].index(context)<texts[CPP].index(load):raise ValueError('Unsupported context lifecycle')
    if 'library/DeviceLibrary.cpp' not in texts[PRO] or 'add_library(pegasus-backend' not in texts[CMAKE]:raise ValueError('Patched native anchors missing')
    xml=texts[MANIFEST];ET.fromstring(xml)
    if any(name in xml for name in ('com.droiddeck.launcher','app.gamenative')):raise ValueError('Existing package queries require review')
    packages='''<!-- NOVA_PC_RUNTIME_V1_QUERIES_BEGIN -->
        <package android:name="com.droiddeck.launcher" />
        <package android:name="app.gamenative" />
        <!-- NOVA_PC_RUNTIME_V1_QUERIES_END -->'''
    if xml.count('<queries>')==1:xml=xml.replace('<queries>','<queries>\n        '+packages,1)
    elif '<queries' not in xml and xml.count('<application')==1:xml=xml.replace('<application','<queries>\n        '+packages+'\n    </queries>\n    <application',1)
    else:raise ValueError('Unsupported package-visibility layout')
    ET.fromstring(xml)
    after={CPP:texts[CPP].replace(include,include+'\n// NOVA_PC_RUNTIME_V1\n#include "library/pcgames/PcRuntime.h"',1).replace(context,context+'\n    // NOVA_PC_RUNTIME_V1\n    m_engine->rootContext()->setContextProperty(QStringLiteral("pcRuntime"), new library::PcRuntime(m_engine));',1).encode(),
        PRO:(texts[PRO]+'\n# NOVA_PC_RUNTIME_V1\ninclude(library/pcgames/pcgames.pri)\n').encode(),
        CMAKE:(texts[CMAKE]+'\n# NOVA_PC_RUNTIME_V1\ntarget_sources(pegasus-backend PRIVATE library/pcgames/PcRuntime.cpp library/pcgames/PcRuntime.h)\n').encode(),MANIFEST:xml.encode()}
    backup.mkdir(mode=0o700)
    for name,data in before.items():
        p=backup/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    receipt={'state':'preparing','before':{str(p):hashlib.sha256(b).hexdigest() for p,b in before.items()}}
    (backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    written=[];published=[]
    try:
        if any(regular(source/p)!=data for p,data in before.items()):raise ValueError('Source changed; newer work preserved')
        target.mkdir()
        for name in MODULE_FILES:(target/name).write_bytes(inputs[name])
        for name in JAVA_FILES:
            dest=source/JAVA/name
            with dest.open('xb') as f:f.write(inputs[name])
            published.append(dest)
        for name,data in after.items():
            path=source/name
            if regular(path)!=before[name]:raise ValueError('Source changed before write')
            fd,tmp=tempfile.mkstemp(prefix='.pc-runtime-',dir=path.parent)
            try:
                with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
                os.chmod(tmp,stat.S_IMODE(path.stat().st_mode));os.replace(tmp,path)
            finally:
                if os.path.exists(tmp):os.unlink(tmp)
            written.append(name)
        receipt['state']='applied';receipt['after']={str(p):hashlib.sha256(b).hexdigest() for p,b in after.items()};(backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt
    except Exception:
        for name in reversed(written):
            if regular(source/name)==after[name]:(source/name).write_bytes(before[name])
        for path in published:
            if path.read_bytes()==inputs[path.name]:path.unlink()
        if target.is_dir() and {p.name for p in target.iterdir()}==set(MODULE_FILES) and all(regular(target/n)==inputs[n] for n in MODULE_FILES):
            for name in MODULE_FILES:(target/name).unlink()
            target.rmdir()
        receipt['state']='failed';(backup/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');raise

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--backup',type=Path,required=True);a=p.parse_args()
    try:apply(a.source,a.backup)
    except (ValueError,OSError,ET.ParseError) as e:p.exit(1,str(e)+'\n')
