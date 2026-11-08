#!/usr/bin/env python3
"""Add the optional cloud module to an existing patched Pegasus source tree.

Does not build, install, deploy, enroll, or change any emulator configuration.
Existing dirty native work is preserved; every changed integration file is backed up.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

ROOT=Path(__file__).resolve().parents[1]
def apply(source, backup):
    source=source.resolve();backup=backup.resolve()
    if backup.exists(): raise ValueError('Backup directory already exists')
    backend=source/'src/backend'
    target=backend/'library/romcloud'
    vault=source/'src/app/platform/android/src/org/pegasus_frontend/android/RomCloudVault.java'
    if target.exists() or vault.exists(): raise ValueError('Cloud integration already exists; refusing to replace it')
    replacements={
        backend/'FrontendLayer.cpp': [('#include "library/DeviceLibrary.h"','#include "library/DeviceLibrary.h"\n#include "library/romcloud/RomCloud.h"'),('setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);','setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);\n    m_engine->rootContext()->setContextProperty(QStringLiteral("romCloud"), new library::RomCloud(this));')],
        backend/'backend.pro': [('    library/PlatformEnrollment.cpp \\','    library/PlatformEnrollment.cpp \\\n    library/romcloud/RomCloud.cpp \\'),('    library/DeviceLibrary.h \\','    library/DeviceLibrary.h \\\n    library/romcloud/RomCloud.h \\')],
        backend/'CMakeLists.txt': [('    library/PlatformEnrollment.cpp','    library/PlatformEnrollment.cpp\n    library/romcloud/RomCloud.cpp\n    library/romcloud/RomCloud.h')]
    }
    pending={}
    for path, edits in replacements.items():
        text=path.read_text()
        for before,after in edits:
            if text.count(before)!=1: raise ValueError('Native integration anchor is ambiguous: '+path.name)
            text=text.replace(before,after,1)
        pending[path]=text
    backup.mkdir(parents=True)
    manifest={}
    for path,text in pending.items():
        relative=path.relative_to(source);dest=backup/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
        manifest[str(relative)]=hashlib.sha256(path.read_bytes()).hexdigest()
    (backup/'before.json').write_text(json.dumps(manifest,indent=2)+'\n')
    target.mkdir(parents=True)
    for name in ['RomCloud.cpp','RomCloud.h','romcloud.pri']:
        shutil.copy2(ROOT/'native/romcloud'/name,target/name)
    shutil.copy2(ROOT/'native/romcloud/RomCloudVault.java',vault)
    for path,text in pending.items(): path.write_text(text)
    print('Source integration prepared; no application or service was deployed.')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('--backup',type=Path,required=True);a=p.parse_args()
    try: apply(a.source,a.backup)
    except (ValueError,OSError) as e: p.exit(1,str(e)+'\n')
