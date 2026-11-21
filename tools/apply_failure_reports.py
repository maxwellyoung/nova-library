#!/usr/bin/env python3
"""Wire optional structured failure preview/private export into prepared source. No build/install."""
from pathlib import Path
import hashlib,json
from apply_save_copies import regular
ROOT=Path(__file__).resolve().parents[1]
FILES=('src/backend/FrontendLayer.cpp','src/backend/backend.pro','src/backend/CMakeLists.txt',
       'src/frontend/main.qml','src/frontend/frontend.qrc','src/frontend/messages/ThemeError.qml')
MODULE='src/backend/library/failure-reports'
PAYLOAD=('FailureReports.h','FailureReports.cpp','DocumentCopy.h','DocumentCopy.cpp','failure-reports.pri')
THEME_ERRORS={'ddd160e58536a7785b8020c52adb64242f4293b0dd6a1d97cef138d02c4e4135',
              'a8a23240d0d1d2d3172d33d14ddc86a12aff7178c754d9fe4d531ace71bcf1cd'}
def apply(source,backup,*,module=None,theme_preview=None):
 source,backup=Path(source).absolute(),Path(backup).absolute();module=Path(module or ROOT/'native/failure-reports')
 theme_preview=Path(theme_preview or ROOT/'theme/FailurePreview.qml')
 if any(p.is_symlink() for p in (source,backup,*source.parents,*backup.parents)) or not source.is_dir() or not backup.parent.is_dir() or backup.exists() or source in backup.parents or ROOT in backup.parents:raise ValueError('Canonical prepared source and new external backup required')
 before={n:regular(source/n) for n in FILES};texts={n:b.decode() for n,b in before.items()};target=source/MODULE
 if target.exists() or any('NOVA_FAILURE_REPORTS_V1' in t for t in texts.values()):raise ValueError('Existing failure report integration requires review')
 cpp=texts[FILES[0]];old='''    m_engine->rootContext()->setContextProperty(QStringLiteral("saveCopies"), saveCopiesRoot.isEmpty() ? nullptr : new library::SaveCopies(
        saveCopiesRoot + QStringLiteral("/save-copies-v1"), m_engine));'''
 if cpp.count(old)!=1 or cpp.count('#include "library/savecopies/SaveCopies.h"')!=1:raise ValueError('Unsupported save-copy context anchor')
 if b'operationObserved' not in regular(source/'src/backend/library/savecopies/SaveCopies.h'):raise ValueError('Matching native structured observer required')
 if '#include <QFileInfo>' not in cpp:
  if cpp.count('#include <QStandardPaths>')!=1:raise ValueError('Missing framework data-path anchor')
  cpp=cpp.replace('#include <QStandardPaths>','#include <QStandardPaths>\n#include <QFileInfo>',1)
 cpp=cpp.replace('#include "library/savecopies/SaveCopies.h"','#include "library/savecopies/SaveCopies.h"\n#include "library/failure-reports/FailureReports.h"',1)
 cloud='    m_engine->rootContext()->setContextProperty(QStringLiteral("romCloud"), new library::RomCloud(this));'
 if cpp.count(cloud)>1:raise ValueError('Ambiguous native Cloud context')
 if cpp.count(cloud) and b'playObserved' not in regular(source/'src/backend/library/romcloud/RomCloud.h'):raise ValueError('Matching native Cloud observation context required')
 cpp=cpp.replace(cloud,'''    auto* cloudLibrary = new library::RomCloud(this);
    QObject::connect(cloudLibrary, &library::RomCloud::playObserved,
        failureReports, &library::FailureReports::observeCloudPlay);
    m_engine->rootContext()->setContextProperty(QStringLiteral("romCloud"), cloudLibrary);''',1)
 cpp=cpp.replace(old,'''    auto* saveCopiesReader = saveCopiesRoot.isEmpty() ? nullptr : new library::SaveCopies(
        saveCopiesRoot + QStringLiteral("/save-copies-v1"), m_engine);
    m_engine->rootContext()->setContextProperty(QStringLiteral("saveCopies"), saveCopiesReader);
    // NOVA_FAILURE_REPORTS_V1: minimized native observations; explicit private export only.
    auto* failureReports = new library::FailureReports(saveCopiesRoot.isEmpty() ? QString() : QFileInfo(saveCopiesRoot).canonicalFilePath(), m_engine);
    if (saveCopiesReader) QObject::connect(saveCopiesReader, &library::SaveCopies::operationObserved,
        failureReports, &library::FailureReports::observeSaveCopies);
    m_engine->rootContext()->setContextProperty(QStringLiteral("failureReports"), failureReports);''',1)
 load='    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));'
 cpp=cpp.replace('    m_engine->rootContext()->setContextProperty(QStringLiteral("failureReports"), failureReports);', '''    m_engine->rootContext()->setContextProperty(QStringLiteral("failureReports"), failureReports);
    QObject::connect(m_engine, &QQmlEngine::warnings,
        failureReports, &library::FailureReports::observeThemeWarnings);''',1)
 if cpp.count(load)!=1:raise ValueError('Unsupported compiled frontend anchor')
 cpp=cpp.replace(load,'''    // Bind the compiled Loader before asynchronous external theme loading begins.
    QObject::connect(m_engine, &QQmlApplicationEngine::objectCreated, failureReports,
        [failureReports](QObject* root, const QUrl& url) {
            if (root && url == QUrl(QStringLiteral("qrc:/frontend/main.qml")))
                failureReports->bindThemeLoader(root->findChild<QObject*>(QStringLiteral("novaSelectedThemeLoader")));
        });
'''+load,1)
 main=texts[FILES[3]]
 replacements={
  '                return apiThemePath;':'                failureReports.beginThemeLoad();\n                return apiThemePath;',
  '            id: theme\n':'            id: theme\n            objectName: "novaSelectedThemeLoader"\n',
  '            onApiThemePathChanged: source = Qt.binding(getThemeFile)':'            onApiThemePathChanged: { failureReports.clearThemeFailure(); source = Qt.binding(getThemeFile); }',
  '                if (status == Loader.Error)\n                    source = "messages/ThemeError.qml";':'                if (status == Loader.Error) {\n                    failureReports.captureThemeFailure();\n                    source = "messages/ThemeError.qml";\n                }',
  '            onLoaded: item.focus = focus':'            onLoaded: { failureReports.clearThemeFailure(); item.focus = focus; }',
 }
 # The main-menu Loader also has onLoaded: only replace the first theme occurrence.
 for old,new in replacements.items():
  if main.count(old)!=(2 if old=='            onLoaded: item.focus = focus' else 1):raise ValueError('Unsupported native Loader anchor')
  main=main.replace(old,new,1)
 qrc=texts[FILES[4]];anchor='        <file>messages/ThemeError.qml</file>'
 if qrc.count(anchor)!=1:raise ValueError('Unsupported frontend resources')
 qrc=qrc.replace(anchor,anchor+'\n        <file>messages/ThemeFailureReview.qml</file>\n        <file>messages/FailurePreview.qml</file>',1)
 error=texts[FILES[5]]
 if hashlib.sha256(before[FILES[5]]).hexdigest() not in THEME_ERRORS:raise ValueError('Review changed native error/recovery source first')
 error=error.replace('Error {','Error {\n    Keys.forwardTo: [themeFailureReview]',1)
 if '    function recover() {' in error:
  error=error.replace('    function recover() {','    function recover() {\n        if (themeFailureReview.previewOpen || themeFailureReview.releaseFence.length) return;',1)
  error=error.replace('        objectName: "builtinThemeRecovery"','        objectName: "builtinThemeRecovery"\n        enabled: !themeFailureReview.previewOpen\n        width: parent.width / 2 - vpx(75)',1)
  # Retain the existing height/gesture semantics while giving each explicit action half the row.
  oldwidth='        width: Math.min(parent.width - vpx(100), recoveryLabel.implicitWidth + vpx(60))\n'
  if error.count(oldwidth)!=1:raise ValueError('Unsupported recovery layout')
  error=error.replace(oldwidth,'',1)
 at=error.rfind('}');error=error[:at]+'    ThemeFailureReview { id: themeFailureReview }\n'+error[at:]
 frontend_payload={'src/frontend/messages/ThemeFailureReview.qml':regular(module/'ThemeFailureReview.qml'),
                   'src/frontend/messages/FailurePreview.qml':regular(theme_preview)}
 if any((source/n).exists() for n in frontend_payload):raise ValueError('Existing compiled review requires inspection')
 cmakeExtra='' if 'Qt5::AndroidExtras' in texts[FILES[2]] else '\nif(ANDROID)\n    find_package(Qt5 5.15 COMPONENTS AndroidExtras REQUIRED)\n    target_link_libraries(pegasus-backend PUBLIC Qt5::AndroidExtras)\nendif()\n'
 after={FILES[0]:cpp.encode(),FILES[1]:(texts[FILES[1]]+'\n# NOVA_FAILURE_REPORTS_V1\ninclude(library/failure-reports/failure-reports.pri)\n').encode(),FILES[2]:(texts[FILES[2]]+'\n# NOVA_FAILURE_REPORTS_V1\ntarget_sources(pegasus-backend PRIVATE library/failure-reports/FailureReports.cpp library/failure-reports/FailureReports.h library/failure-reports/DocumentCopy.cpp library/failure-reports/DocumentCopy.h)\n'+cmakeExtra).encode()}
 after.update({FILES[3]:main.encode(),FILES[4]:qrc.encode(),FILES[5]:error.encode()})
 payload={n:regular(module/n) for n in PAYLOAD};backup.mkdir(mode=0o700)
 for n,b in before.items():p=backup/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b);p.chmod(0o600)
 if any(regular(source/n)!=b for n,b in before.items()):raise ValueError('Integration source changed')
 try:
  target.mkdir()
  for n,b in payload.items():(target/n).write_bytes(b)
  for n,b in frontend_payload.items():(source/n).write_bytes(b)
  for n,b in after.items():
   if regular(source/n)!=before[n]:raise ValueError('Source changed during integration')
   (source/n).write_bytes(b)
 except OSError:
  # Restore only our exact completed replacements; retain partial/drifted files and backup.
  for n,b in after.items():
   if (source/n).is_file() and regular(source/n)==b:(source/n).write_bytes(before[n])
  raise
 (backup/'receipt.json').write_text(json.dumps({'before':{n:hashlib.sha256(b).hexdigest() for n,b in before.items()},'after':{n:hashlib.sha256(b).hexdigest() for n,b in after.items()},'built':False,'installed':False},indent=2)+'\n')

if __name__=='__main__':
 import argparse
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('source',type=Path);parser.add_argument('--backup',type=Path,required=True);args=parser.parse_args()
 try:apply(args.source,args.backup);print('Optional native failure preview/private export integrated; no build/install.')
 except (ValueError,OSError):parser.exit(1,'Failure report source integration refused; retain and inspect its backup.\n')
