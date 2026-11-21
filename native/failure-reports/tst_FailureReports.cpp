// SPDX-License-Identifier: GPL-3.0-or-later
#include "FailureReports.h"
#include "SaveCopies.h"
#include "RomCloud.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QStandardPaths>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QCryptographicHash>
#include <QScopeGuard>
#include <memory>
#include <atomic>
#include <QUrl>
#ifdef Q_OS_UNIX
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#endif
using library::FailureReports;
#ifdef Q_OS_UNIX
struct OwnedDescriptor {
 explicit OwnedDescriptor(int value):fd(value) {}
 ~OwnedDescriptor(){if(fd>=0)::close(fd);}
 int fd;
};
static library::DocumentTarget documentTarget(int fd) {
 const auto owned=std::make_shared<OwnedDescriptor>(fd);
 return [owned](const QByteArray& bytes,const std::function<bool()>& cancelled){return library::writeFailureDocument(owned->fd,bytes,cancelled);};
}
#endif

static QString sha(const QByteArray& data){return QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex();}
static void put(const QString& path,const QByteArray& data){QFile f(path);QVERIFY(f.open(QIODevice::WriteOnly));QCOMPARE(f.write(data),qint64(data.size()));f.close();QVERIFY(f.setPermissions(QFile::ReadOwner|QFile::WriteOwner));}
static QVariantMap bad(){return {{"ok",false},{"error","invalid_index"},{"token","secret_fixture_only"},{"path","/private/fixture/secret"}};}
static QQmlError diagnostic(const QUrl& url,const QString& description,int line=4,int column=7){QQmlError e;e.setUrl(url);e.setDescription(description);e.setLine(line);e.setColumn(column);return e;}
class Checks:public QObject {
 Q_OBJECT
private slots:
 void initTestCase(){QStandardPaths::setTestModeEnabled(true);}
 void themeCaptureRequiresBoundSelectedLoaderError(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());
  QVERIFY(!r.captureThemeFailure());QVERIFY(!r.themeFailureAvailable());
  QObject loader;const QUrl selected("file:///private/fixture/theme.qml");
  loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);r.bindThemeLoader(&loader);
  for(int status:{0,1,2}){loader.setProperty("status",status);QVERIFY(!r.captureThemeFailure());}
  loader.setProperty("status",3);loader.setProperty("source",QUrl("qrc:/frontend/messages/ThemeError.qml"));QVERIFY(!r.captureThemeFailure());
  loader.setProperty("source",selected);QVERIFY(r.captureThemeFailure());QVERIFY(r.themeFailureAvailable());
  const auto preview=r.previewThemeFailure();QVERIFY(preview["ok"].toBool());const auto bytes=preview["text"].toString().toUtf8();QVERIFY(bytes.size()<=8192);QVERIFY(!bytes.contains("/private/fixture"));QVERIFY(!bytes.contains("file:"));
  auto report=QJsonDocument::fromJson(bytes).object();QCOMPARE(report["source"].toString(),QString("native-theme-load-observation"));QCOMPARE(report["editionSha256"].toString(),sha("nova:launcher"));
  QCOMPARE(report["facts"].toArray()[0].toObject()["code"].toString(),QString("selected-theme-load-failed"));QVERIFY(!report["currentSetupVerified"].toBool());QVERIFY(report["provenance"].toObject()["observed"].toObject()["sourceSha256"].isNull());
  loader.setProperty("source",QUrl("qrc:/frontend/messages/ThemeError.qml"));loader.setProperty("status",1);r.clearThemeFailure();QVERIFY(r.themeFailureAvailable());
  const auto saved=r.exportPreview(preview["ticket"].toString(),preview["sha256"].toString());QVERIFY(saved["ok"].toBool());
  QFile file(tmp.path()+"/failure-reports-v1/"+saved["fileName"].toString());QVERIFY(file.open(QIODevice::ReadOnly));QCOMPARE(file.readAll(),bytes);
  QVERIFY(!r.available("nova:launcher",{},{}));QVERIFY(!r.cloudPlayAvailable("nova:launcher",{}));
  loader.setProperty("source",selected);r.clearThemeFailure();QVERIFY(!r.themeFailureAvailable());
 }
 void themeSelectionChangeAndLoaderLifetimeInvalidateTickets(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());auto* loader=new QObject;
  const QUrl selected("file:///private/fixture/theme.qml");loader->setProperty("apiThemePath",selected);loader->setProperty("source",selected);loader->setProperty("status",3);r.bindThemeLoader(loader);QVERIFY(r.captureThemeFailure());
  auto p=r.previewThemeFailure();loader->setProperty("apiThemePath",QUrl("file:///private/another.qml"));QVERIFY(!r.themeFailureAvailable());QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());r.clearThemeFailure();
  loader->setProperty("apiThemePath",selected);QVERIFY(!r.themeFailureAvailable());QVERIFY(r.captureThemeFailure());p=r.previewThemeFailure();delete loader;
  QVERIFY(!r.themeFailureAvailable());QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());
 }
 void themeConstructionFailureKeepsSelectedComponentBinding_data(){
  QTest::addColumn<QString>("kind");
  for(auto kind:{"missing","foreign","loading","null","ready","normalized"})QTest::newRow(kind)<<QString(kind);
 }
 void themeConstructionFailureKeepsSelectedComponentBinding(){
  QFETCH(QString,kind);QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());QObject loader,component;
  const QUrl selected("file:///private/fixture/theme.qml");loader.setProperty("apiThemePath",selected);loader.setProperty("source",QUrl());loader.setProperty("status",3);
  if(kind!="missing")loader.setProperty("sourceComponent",QVariant::fromValue<QObject*>(&component));
  component.setProperty("status",kind=="loading"?2:kind=="null"?0:1);
  component.setProperty("url",kind=="foreign"?QUrl("qrc:/frontend/messages/ThemeError.qml"):kind=="normalized"?QUrl("file:///private/fixture/../fixture/theme.qml"):selected);
  r.bindThemeLoader(&loader);const bool valid=kind=="ready" || kind=="normalized";
  QCOMPARE(r.captureThemeFailure(),valid);QCOMPARE(r.themeFailureAvailable(),valid);
  if(valid){const auto p=r.previewThemeFailure();QVERIFY(p["ok"].toBool());QVERIFY(!p["text"].toString().contains("/private/fixture"));const auto report=QJsonDocument::fromJson(p["text"].toString().toUtf8()).object();QCOMPARE(report["facts"].toArray()[0].toObject()["code"].toString(),QString("selected-theme-construction-failed"));QVERIFY(!report["currentSetupVerified"].toBool());QCOMPARE(report["hypotheses"].toArray()[0].toObject()["status"].toString(),QString("unconfirmed"));QVERIFY(r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());}
 }
 void themeDiagnosticCollectionIsBoundedAndExcludesFreeText(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());QObject loader;
  const QUrl selected("file:///private/fixture/theme.qml");loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);loader.setProperty("status",2);r.bindThemeLoader(&loader);
  QList<QQmlError> errors{diagnostic(QUrl("file:///private/other/theme.qml"),"TypeError: secret_foreign"),diagnostic(QUrl("qrc:/frontend/messages/ThemeError.qml"),"TypeError: secret_fallback"),diagnostic(QUrl("file:///private/fixture/child.qml"),"TypeError: secret_child")};
  r.observeThemeWarnings(errors);QVERIFY(!r.captureThemeFailure());
  errors.clear();for(int i=0;i<12;++i)errors.append(diagnostic(selected,"Required property secret_fixture_token was not initialized",i,i));
  errors.prepend(errors[0]);r.observeThemeWarnings(errors);QVERIFY(!r.themeFailureAvailable());loader.setProperty("status",3);QVERIFY(r.captureThemeFailure());
  const auto p=r.previewThemeFailure();const auto bytes=p["text"].toString().toUtf8();QVERIFY(bytes.size()<=8192);QVERIFY(!bytes.contains("secret_"));QVERIFY(!bytes.contains("/private/"));QVERIFY(!bytes.contains("file:"));
  const auto evidence=QJsonDocument::fromJson(bytes).object()["localEvidence"].toObject();const auto log=evidence["errorLog"].toObject();QCOMPARE(log["status"].toString(),QString("collected"));QCOMPARE(log["entries"].toArray().size(),8);QVERIFY(log["truncated"].toBool());
  const auto first=log["entries"].toArray()[0].toObject();QCOMPARE(first["code"].toString(),QString("required-property-uninitialized"));QCOMPARE(first["line"].toInt(),0);QCOMPARE(evidence["configuration"].toObject()["frameworkVersion"].toString(),QString::fromLatin1(qVersion()));QCOMPARE(evidence["lastCloudPreflight"].toObject()["status"].toString(),QString("unavailable"));
  QVERIFY(!QFileInfo::exists(tmp.path()+"/failure-reports-v1"));r.cancelPreview(p["ticket"].toString());QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());
 }
 void themeDiagnosticKindsAndPositionBounds_data(){
  QTest::addColumn<QString>("description");QTest::addColumn<QString>("code");
  QTest::newRow("syntax")<<QString("Expected token secret_token")<<QString("qml-syntax-error");
  QTest::newRow("type")<<QString("SecretPrivateName is not a type")<<QString("qml-type-unavailable");
  QTest::newRow("js-type")<<QString("TypeError: private-secret")<<QString("javascript-type-error");
  QTest::newRow("js-reference")<<QString("ReferenceError: private-secret")<<QString("javascript-reference-error");
  QTest::newRow("unknown")<<QString("password=private-secret")<<QString("qml-error-unclassified");
  QTest::newRow("oversized")<<(QString("TypeError:")+QString(10000,'s'))<<QString("qml-error-unclassified");
 }
 void themeDiagnosticKindsAndPositionBounds(){
  QFETCH(QString,description);QFETCH(QString,code);QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());QObject loader;const QUrl selected("file:///private/fixture/theme.qml");loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);loader.setProperty("status",3);r.bindThemeLoader(&loader);r.observeThemeWarnings({diagnostic(selected,description,-1,20000)});QVERIFY(r.captureThemeFailure());
  auto report=QJsonDocument::fromJson(r.previewThemeFailure()["text"].toString().toUtf8()).object();auto entry=report["localEvidence"].toObject()["errorLog"].toObject()["entries"].toArray()[0].toObject();QCOMPARE(entry["code"].toString(),code);QCOMPARE(entry["line"].toInt(),0);QCOMPARE(entry["column"].toInt(),10000);
 }
 void themeDiagnosticLifecycleDoesNotReplayAnOldLoad(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());QObject loader;const QUrl selected("file:///private/fixture/theme.qml");loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);loader.setProperty("status",3);r.bindThemeLoader(&loader);r.observeThemeWarnings({diagnostic(selected,"TypeError: secret")});QVERIFY(r.captureThemeFailure());auto p=r.previewThemeFailure();
  r.beginThemeLoad();QVERIFY(!r.themeFailureAvailable());QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());QVERIFY(r.captureThemeFailure());
  auto report=QJsonDocument::fromJson(r.previewThemeFailure()["text"].toString().toUtf8()).object();QCOMPARE(report["localEvidence"].toObject()["errorLog"].toObject()["status"].toString(),QString("unavailable"));
  r.beginThemeLoad();r.observeThemeWarnings({diagnostic(selected,"TypeError: secret")});loader.setProperty("status",1);r.clearThemeFailure();loader.setProperty("status",3);r.observeThemeWarnings({diagnostic(selected,"TypeError: after-success-secret")});QVERIFY(r.captureThemeFailure());report=QJsonDocument::fromJson(r.previewThemeFailure()["text"].toString().toUtf8()).object();QCOMPARE(report["localEvidence"].toObject()["errorLog"].toObject()["status"].toString(),QString("unavailable"));
  r.beginThemeLoad();r.observeThemeWarnings({diagnostic(selected,"TypeError: secret")});const QUrl next("file:///private/next/theme.qml");loader.setProperty("apiThemePath",next);loader.setProperty("source",next);QVERIFY(r.captureThemeFailure());report=QJsonDocument::fromJson(r.previewThemeFailure()["text"].toString().toUtf8()).object();QCOMPARE(report["localEvidence"].toObject()["errorLog"].toObject()["status"].toString(),QString("unavailable"));
 }
 void themeContextRetainsOnlyKnownCloudRefusalUntilNextAttempt(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());QObject loader;const QUrl selected("file:///private/fixture/theme.qml");loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);loader.setProperty("status",3);r.bindThemeLoader(&loader);
  r.observeCloudPlay("nova:cloud_fixture",QString(32,'a'),"runtime_refused");QVERIFY(r.captureThemeFailure());auto report=QJsonDocument::fromJson(r.previewThemeFailure()["text"].toString().toUtf8()).object();auto last=report["localEvidence"].toObject()["lastCloudPreflight"].toObject();QCOMPARE(last["status"].toString(),QString("observed-refusal"));QCOMPARE(last["code"].toString(),QString("runtime-request-refused"));QCOMPARE(last["editionSha256"].toString(),sha("nova:cloud_fixture"));QVERIFY(!report.contains("lastLaunchSucceeded"));
  r.observeCloudPlay({},QString(32,'b'),{});QVERIFY(r.captureThemeFailure());report=QJsonDocument::fromJson(r.previewThemeFailure()["text"].toString().toUtf8()).object();QCOMPARE(report["localEvidence"].toObject()["lastCloudPreflight"].toObject()["status"].toString(),QString("unavailable"));
 }
 void capacitySafeIntegerBoundsSerializeAsExactJsonIntegers(){
  for(qint64 value:{qint64(0),qint64(9007199254740991LL)}) {
   const auto bytes=QJsonDocument::fromVariant(QVariantMap{{"availableBytes",value},{"totalBytes",qint64(9007199254740991LL)}}).toJson();
   QVERIFY(bytes.contains(QByteArray("\"availableBytes\": ")+QByteArray::number(value)));
   QVERIFY(bytes.contains("\"totalBytes\": 9007199254740991"));
  }
 }
 void themeFailureCapturesPrivateAppVolumeCapacityWithoutScanningOrWriting(){
  QTemporaryDir tmp;const auto root=QFileInfo(tmp.path()).canonicalFilePath();put(root+"/untouched","capacity_fixture_only");FailureReports r(root);QObject loader;const QUrl selected("file:///private/fixture/theme.qml");loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);loader.setProperty("status",3);r.bindThemeLoader(&loader);QVERIFY(r.captureThemeFailure());
  const auto preview=r.previewThemeFailure();const auto bytes=preview["text"].toString().toUtf8();const auto report=QJsonDocument::fromJson(bytes).object();const auto storage=report["localEvidence"].toObject()["appDataStorage"].toObject();
#ifdef Q_OS_UNIX
  QCOMPARE(storage["status"].toString(),QString("measured"));QCOMPARE(storage["scope"].toString(),QString("app-data-volume"));QCOMPARE(storage["method"].toString(),QString("fstatvfs"));
  QVERIFY(storage["totalBytes"].toDouble()>0);QVERIFY(storage["totalBytes"].toDouble()<=9007199254740991.0);QVERIFY(storage["availableBytes"].toDouble()>=0);QVERIFY(storage["availableBytes"].toDouble()<=storage["totalBytes"].toDouble());QVERIFY(storage["observedAt"].toString()<=report["observedAt"].toString());
#else
  QCOMPARE(storage["status"].toString(),QString("unavailable"));QCOMPARE(storage.size(),1);
#endif
  QVERIFY(bytes.size()<=8192);QVERIFY(!bytes.contains(root.toUtf8()));QVERIFY(!bytes.contains("capacity_fixture_only"));QVERIFY(!QFileInfo::exists(root+"/failure-reports-v1"));QFile keep(root+"/untouched");QVERIFY(keep.open(QIODevice::ReadOnly));QCOMPARE(keep.readAll(),QByteArray("capacity_fixture_only"));QCOMPARE(report["hypotheses"].toArray()[0].toObject()["code"].toString(),QString("unknown-cause"));
 }
 void themeCapacityUnsafeOrMissingRootsRemainUnavailable_data(){
  QTest::addColumn<QString>("kind");QTest::newRow("missing")<<QString("missing");QTest::newRow("file")<<QString("file");
#ifdef Q_OS_UNIX
  for(auto kind:{"linked","parent-alias","fifo","shared"})QTest::newRow(kind)<<QString(kind);
#endif
 }
 void themeCapacityUnsafeOrMissingRootsRemainUnavailable(){
  QFETCH(QString,kind);QTemporaryDir tmp;const auto base=QFileInfo(tmp.path()).canonicalFilePath();QString root=base+"/store";const auto target=base+"/target";
  if(kind=="file")put(root,"capacity_fixture_only");
  else if(kind=="linked"){QVERIFY(QDir().mkdir(target));QVERIFY(QFile::link(target,root));}
  else if(kind=="parent-alias"){QVERIFY(QDir().mkdir(target));QVERIFY(QDir().mkdir(target+"/store"));QVERIFY(QFile::link(target,base+"/alias"));root=base+"/alias/store";}
#ifdef Q_OS_UNIX
  else if(kind=="fifo")QCOMPARE(::mkfifo(QFile::encodeName(root).constData(),0600),0);
  else if(kind=="shared"){QVERIFY(QDir().mkdir(root));QCOMPARE(::chmod(QFile::encodeName(root).constData(),0777),0);}
#endif
  FailureReports r(root);QObject loader;const QUrl selected("file:///private/fixture/theme.qml");loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);loader.setProperty("status",3);r.bindThemeLoader(&loader);QVERIFY(r.captureThemeFailure());const auto preview=r.previewThemeFailure();const auto bytes=preview["text"].toString().toUtf8();const auto storage=QJsonDocument::fromJson(bytes).object()["localEvidence"].toObject()["appDataStorage"].toObject();QCOMPARE(storage["status"].toString(),QString("unavailable"));QCOMPARE(storage.size(),1);QVERIFY(!bytes.contains(base.toUtf8()));QVERIFY(!r.exportPreview(preview["ticket"].toString(),preview["sha256"].toString())["ok"].toBool());if(kind=="missing")QVERIFY(!QFileInfo::exists(root));
#ifdef Q_OS_UNIX
  if(kind=="shared")QCOMPARE(::chmod(QFile::encodeName(root).constData(),0700),0);
#endif
 }
 void privateCapacityAndExactExportThroughSearchOnlyAncestor_data(){
  QTest::addColumn<int>("mode");QTest::addColumn<int>("rootMode");QTest::addColumn<bool>("accepted");
  QTest::newRow("search-only")<<0111<<0700<<true;
  QTest::newRow("android-style")<<0711<<0700<<true;
  QTest::newRow("android-files-own-group")<<0711<<0771<<true;
  QTest::newRow("other-writable-root")<<0711<<0773<<false;
  QTest::newRow("search-denied")<<0000<<0700<<false;
  QTest::newRow("private-root-not-readable")<<0111<<0111<<false;
 }
 void privateCapacityAndExactExportThroughSearchOnlyAncestor(){
#if defined(Q_OS_UNIX) && (defined(O_PATH) || defined(O_SEARCH))
  QFETCH(int,mode);QFETCH(int,rootMode);QFETCH(bool,accepted);QTemporaryDir tmp;const auto base=QFileInfo(tmp.path()).canonicalFilePath();
  const auto parent=base+"/search-only",root=parent+"/app-data";
  QVERIFY(QDir().mkdir(parent));QVERIFY(QDir().mkdir(root));
  QCOMPARE(::chmod(QFile::encodeName(root).constData(),mode_t(rootMode)),0);
  QCOMPARE(::chmod(QFile::encodeName(parent).constData(),mode_t(mode)),0);
  const auto restore=qScopeGuard([&]{::chmod(QFile::encodeName(parent).constData(),0700);::chmod(QFile::encodeName(root).constData(),0700);});
  FailureReports r(root);QObject loader;const QUrl selected("file:///private/fixture/theme.qml");
  loader.setProperty("apiThemePath",selected);loader.setProperty("source",selected);loader.setProperty("status",3);r.bindThemeLoader(&loader);QVERIFY(r.captureThemeFailure());
  const auto preview=r.previewThemeFailure();QVERIFY(preview["ok"].toBool());const auto bytes=preview["text"].toString().toUtf8();
  const auto storage=QJsonDocument::fromJson(bytes).object()["localEvidence"].toObject()["appDataStorage"].toObject();
  QCOMPARE(storage["status"].toString(),QString(accepted?"measured":"unavailable"));QVERIFY(!QFileInfo::exists(root+"/failure-reports-v1"));QVERIFY(!bytes.contains(base.toUtf8()));
  const auto saved=r.exportPreview(preview["ticket"].toString(),preview["sha256"].toString());QCOMPARE(saved["ok"].toBool(),accepted);
  if(!accepted){QCOMPARE(saved["error"].toString(),QString("private_storage_unavailable"));return;}
  const auto name=root+"/failure-reports-v1/"+saved["fileName"].toString();QFile file(name);QVERIFY(file.open(QIODevice::ReadOnly));QCOMPARE(file.readAll(),bytes);
  struct stat st{};QCOMPARE(::stat(QFile::encodeName(name).constData(),&st),0);QCOMPARE(st.st_mode&0777,mode_t(0600));QCOMPARE(::stat(QFile::encodeName(parent).constData(),&st),0);QCOMPARE(st.st_mode&0777,mode_t(mode));
#else
  QSKIP("Search-only directory descriptors are unavailable on this platform");
#endif
 }
 void nativeReaderAndCancel(){
  QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();QDir().mkdir(root+"/copies");QFile::setPermissions(root+"/copies",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner);put(root+"/copies/catalogue.json","{}");
  FailureReports reports(root);library::SaveCopies reader(root+"/copies");QObject::connect(&reader,&library::SaveCopies::operationObserved,&reports,&FailureReports::observeSaveCopies);
  auto result=reader.openEdition("demo:failure");QCOMPARE(result.value("ok").toBool(),false);QCOMPARE(result.value("error").toString(),QString("invalid_index"));
  auto preview=reports.preview("demo:failure",{},{});QVERIFY(preview.value("ok").toBool());QVERIFY(!QFileInfo::exists(root+"/failure-reports-v1"));
  reports.cancelPreview(preview["ticket"].toString());QVERIFY(!reports.exportPreview(preview["ticket"].toString(),preview["sha256"].toString())["ok"].toBool());QVERIFY(!QFileInfo::exists(root+"/failure-reports-v1"));
  QCOMPARE(QFileInfo(root+"/copies/catalogue.json").size(),qint64(2));
 }
 void nativeOwnerCheckIsAnObservation(){
  QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();QDir().mkdir(root+"/copies");QFile::setPermissions(root+"/copies",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner|QFile::ReadGroup);
  FailureReports reports(root);library::SaveCopies reader(root+"/copies");QObject::connect(&reader,&library::SaveCopies::operationObserved,&reports,&FailureReports::observeSaveCopies);
  auto result=reader.openEdition("demo:failure");QCOMPARE(result.value("error").toString(),QString("storage_unavailable"));QCOMPARE(result.value("storageCheck").toString(),QString("shared_permissions"));
  auto p=reports.preview("demo:failure",{},{});QVERIFY(p["ok"].toBool());auto doc=QJsonDocument::fromJson(p["text"].toString().toUtf8()).object();QCOMPARE(doc["facts"].toArray()[0].toObject()["code"].toString(),QString("copy-directory-owner-check-failed"));QVERIFY(!doc["currentSetupVerified"].toBool());
 }
 void exactPrivateExport(){
  QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();FailureReports reports(root);reports.observeSaveCopies("demo:failure",{},{},bad());auto p=reports.preview("demo:failure",{},{});QVERIFY(p["ok"].toBool());
  const auto bytes=p["text"].toString().toUtf8();QVERIFY(bytes.size()<=8192);QVERIFY(!bytes.contains("secret_fixture_only"));QVERIFY(!bytes.contains("/private/fixture"));QCOMPARE(sha(bytes),p["sha256"].toString());
  auto doc=QJsonDocument::fromJson(bytes).object();QVERIFY(!doc["currentSetupVerified"].toBool());QCOMPARE(doc["source"].toString(),QString("native-save-copies-observation"));QCOMPARE(doc["provenance"].toObject()["collection"].toObject()["method"].toString(),QString("synthetic"));
  auto saved=reports.exportPreview(p["ticket"].toString(),p["sha256"].toString());QVERIFY(saved["ok"].toBool());QVERIFY(!saved["sent"].toBool());QFile file(root+"/failure-reports-v1/"+saved["fileName"].toString());QVERIFY(file.open(QIODevice::ReadOnly));QCOMPARE(file.readAll(),bytes);
#ifdef Q_OS_UNIX
  struct stat st{};QCOMPARE(::stat(file.fileName().toUtf8().constData(),&st),0);QCOMPARE(st.st_mode&0777,mode_t(0600));QCOMPARE(::stat((root+"/failure-reports-v1").toUtf8().constData(),&st),0);QCOMPARE(st.st_mode&0777,mode_t(0700));
#endif
  QVERIFY(!reports.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());QCOMPARE(QDir(root+"/failure-reports-v1").entryList(QDir::Files).size(),1);
 }
 void bindingAndStalePreview(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());QString id(32,'a'),index(64,'b');r.observeSaveCopies("demo:a",id,index,{{"ok",false},{"error","checksum_mismatch"}});
  QVERIFY(!r.available("demo:b",id,index));QVERIFY(!r.available("demo:a",QString(32,'c'),index));QVERIFY(!r.available("demo:a",id,QString(64,'c')));
  auto first=r.preview("demo:a",id,index),second=r.preview("demo:a",id,index);r.cancelPreview(first["ticket"].toString());QVERIFY(!r.exportPreview(first["ticket"].toString(),first["sha256"].toString())["ok"].toBool());QVERIFY(!r.exportPreview(second["ticket"].toString(),QString(64,'0'))["ok"].toBool());
  r.observeSaveCopies("demo:a",id,index,{{"ok",true}});QVERIFY(!r.exportPreview(second["ticket"].toString(),second["sha256"].toString())["ok"].toBool());QVERIFY(!QFileInfo::exists(tmp.path()+"/failure-reports-v1"));
 }
 void newerFailureAndUnknowns(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());r.observeSaveCopies("demo:a",{},{},bad());auto p=r.preview("demo:a",{},{});r.observeSaveCopies("demo:b",{},{},bad());QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());
  for(auto code:{"cancelled","review_busy","made-up"}){r.observeSaveCopies("demo:a",{},{},{{"ok",false},{"error",code}});QVERIFY(!r.available("demo:a",{},{}));}
  r.observeSaveCopies(QString(513,'a'),{},{},bad());QVERIFY(!r.preview(QString(513,'a'),{},{}).value("ok").toBool());r.observeSaveCopies("bad/<private>",{},{},bad());QVERIFY(!r.available("bad/<private>",{},{}));
 }
 void linksAndSharedStorage(){
  QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();QDir().mkdir(root+"/target");QVERIFY(QFile::link(root+"/target",root+"/failure-reports-v1"));FailureReports r(root);r.observeSaveCopies("demo:a",{},{},bad());auto p=r.preview("demo:a",{},{});QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());QVERIFY(QDir(root+"/target").entryList(QDir::Files).isEmpty());
  QVERIFY(QFile::remove(root+"/failure-reports-v1"));QDir().mkdir(root+"/failure-reports-v1");QFile::setPermissions(root+"/failure-reports-v1",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner|QFile::ReadOther);p=r.preview("demo:a",{},{});QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());
 }
 void existingFilesAndUnavailableRoot(){
  QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();QDir().mkdir(root+"/failure-reports-v1");QFile::setPermissions(root+"/failure-reports-v1",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner);put(root+"/failure-reports-v1/existing.json","keep");FailureReports r(root);r.observeSaveCopies("demo:a",{},{},bad());auto p=r.preview("demo:a",{},{});QVERIFY(r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());QFile old(root+"/failure-reports-v1/existing.json");QVERIFY(old.open(QIODevice::ReadOnly));QCOMPARE(old.readAll(),QByteArray("keep"));
  FailureReports unavailable(root+"/absent");unavailable.observeSaveCopies("demo:a",{},{},bad());p=unavailable.preview("demo:a",{},{});QVERIFY(!unavailable.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());QVERIFY(!QFileInfo::exists(root+"/absent"));
 }
 void nativeCloudPlay_data(){
  QTest::addColumn<QString>("kind");for(auto kind:{"checksum","changed","refused","accepted","cancel"})QTest::newRow(kind)<<QString(kind);
 }
 void nativeCloudPlay(){
  QFETCH(QString,kind);QTemporaryDir tmp;const auto root=QFileInfo(tmp.path()).canonicalFilePath();const auto folder=root+"/roms/nova-cloud/1",cache=root+"/cache";
  QVERIFY(QDir().mkpath(folder));QVERIFY(QDir().mkpath(cache));const QByteArray payload(65536,'x');
  const auto hash=QString::fromLatin1(QCryptographicHash::hash(payload,QCryptographicHash::Sha1).toHex());
  auto game=library::RomCloud::validateGame({{"id",1},{"name","Synthetic game"},{"fs_name","game.sfc"},{"platform_slug","snes"},{"files",QVariantList{QVariantMap{{"id",3},{"file_name","game.sfc"},{"file_size_bytes",payload.size()},{"sha1_hash",hash}}}}});
  library::RomCloudConfig config{QUrl("http://127.0.0.1:1"),"synthetic-token",root+"/roms",cache};int calls=0;bool accepted=kind!="refused";
  config.downloadWindow=[]{return true;};config.launch=[&](const QString&,const QString&){++calls;return accepted;};
  auto marker=QJsonDocument::fromVariant(QVariantMap{{"id",1},{"endpoint",config.endpoint.toString()},{"files",game["files"]},{"entry",game["entry"]},{"platform",game["platform"]}}).toJson();
  put(folder+"/.nova-install.json",marker);put(folder+"/game.sfc",kind=="checksum"?QByteArray(payload.size(),'y'):payload);
  put(cache+"/catalogue.json",QJsonDocument::fromVariant(QVariantMap{{"endpoint",config.endpoint.toString()},{"games",QVariantList{game}}}).toJson());
  library::RomCloud cloud(config);FailureReports reports(root);QObject::connect(&cloud,&library::RomCloud::playObserved,&reports,&FailureReports::observeCloudPlay);
  bool mutated=false;QObject::connect(&cloud,&library::RomCloud::changed,this,[&]{if(kind=="changed" && cloud.busy() && cloud.progress()==1 && !mutated){mutated=true;put(folder+"/.nova-install.json",marker+" ");}});
  cloud.play(1);if(kind=="cancel")cloud.cancel();QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
  const bool failed=QStringList{"checksum","changed","refused"}.contains(kind);const auto result=cloud.playFailure();QCOMPARE(!result.isEmpty(),failed);
  QCOMPARE(calls,kind=="refused" || kind=="accepted"?1:0);const auto edition=library::RomCloud::editionIdentity(config.endpoint,game);
  if(!failed){QVERIFY(!reports.cloudPlayAvailable(edition,{}));return;}
  QCOMPARE(result["editionId"].toString(),edition);auto attempt=result["attempt"].toString();QVERIFY(reports.cloudPlayAvailable(edition,attempt));QVERIFY(!reports.available(edition,attempt,{}));QVERIFY(!reports.cloudPlayAvailable(edition,QString(32,'a')));
  auto preview=reports.previewCloudPlay(edition,attempt);QVERIFY(preview["ok"].toBool());auto text=preview["text"].toString().toUtf8();QVERIFY(!text.contains(root.toUtf8()));QVERIFY(!text.contains("synthetic-token"));
  auto doc=QJsonDocument::fromJson(text).object();QCOMPARE(doc["source"].toString(),QString("native-cloud-play-observation"));QVERIFY(!doc["currentSetupVerified"].toBool());
  const QString code=kind=="checksum"?"download-checksum-unverified":kind=="changed"?"download-changed-before-open":"runtime-request-refused";
  QCOMPARE(doc["facts"].toArray()[0].toObject()["code"].toString(),code);
  auto saved=reports.exportPreview(preview["ticket"].toString(),preview["sha256"].toString());QVERIFY(saved["ok"].toBool());QFile file(root+"/failure-reports-v1/"+saved["fileName"].toString());QVERIFY(file.open(QIODevice::ReadOnly));QCOMPARE(file.readAll(),text);
  preview=reports.previewCloudPlay(edition,attempt);put(folder+"/game.sfc",payload);put(folder+"/.nova-install.json",marker);accepted=true;cloud.play(1);cloud.cancel();QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
  QVERIFY(cloud.playFailure().isEmpty());QVERIFY(!reports.exportPreview(preview["ticket"].toString(),preview["sha256"].toString())["ok"].toBool());
 }
 void sourceScopesCannotReusePreview(){
  QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());const QString edition="nova:cloud_demo:1_demo",attempt(32,'a');
  r.observeCloudPlay(edition,attempt,"runtime_refused");auto p=r.previewCloudPlay(edition,attempt);QVERIFY(p["ok"].toBool());r.observeSaveCopies(edition,{},{},bad());
  QVERIFY(!r.cloudPlayAvailable(edition,attempt));QVERIFY(r.available(edition,{},{}));QVERIFY(!r.exportPreview(p["ticket"].toString(),p["sha256"].toString())["ok"].toBool());
  for(auto error:{"cancelled","made-up",""}){r.observeCloudPlay(edition,attempt,error);QVERIFY(!r.cloudPlayAvailable(edition,attempt));}
 }
#ifdef Q_OS_UNIX
 void documentCopyRequiresPrivateExportAndExactApproval(){
  QTemporaryDir tmp;int calls=0;library::DocumentReceiver receive;
  FailureReports r(QFileInfo(tmp.path()).canonicalFilePath(),[&](const QString&,library::DocumentReceiver result){++calls;receive=result;return true;});
  r.observeSaveCopies("demo:a",{},{},bad());auto p=r.preview("demo:a",{},{});
  QVERIFY(!r.copyPrivateExport(QString(32,'a'),p["sha256"].toString())["ok"].toBool());QCOMPARE(calls,0);
  auto saved=r.exportPreview(p["ticket"].toString(),p["sha256"].toString());QVERIFY(saved["ok"].toBool());QCOMPARE(saved["copyToken"].toString().size(),32);
  QVERIFY(!r.copyPrivateExport(saved["copyToken"].toString(),QString(64,'0'))["ok"].toBool());QCOMPARE(calls,0);
  const auto request=r.copyPrivateExport(saved["copyToken"].toString(),p["sha256"].toString());QVERIFY(request["pending"].toBool());QVERIFY(r.documentCopyBusy());QCOMPARE(calls,1);
  QVERIFY(!r.copyPrivateExport(saved["copyToken"].toString(),p["sha256"].toString())["ok"].toBool());QCOMPARE(calls,1);
  QSignalSpy finished(&r,&FailureReports::documentCopyFinished);receive({},"cancelled");QTRY_VERIFY(!r.documentCopyBusy());QCOMPARE(finished.size(),1);QVERIFY(finished[0][1].toMap()["cancelled"].toBool());
 }
 void documentPickerResult_data(){
  QTest::addColumn<QString>("kind");for(auto kind:{"success","cancel","unavailable","chooser-refusal","stale-before-result","stale-queued-result","nonempty","read-only","duplicate"})QTest::newRow(kind)<<QString(kind);
 }
 void documentPickerResult(){
  QFETCH(QString,kind);QTemporaryDir tmp;const auto root=QFileInfo(tmp.path()).canonicalFilePath();library::DocumentReceiver receive;QString suggested;
  FailureReports r(root,[&](const QString& name,library::DocumentReceiver result){suggested=name;receive=result;return true;});
  r.observeSaveCopies("demo:a",{},{},bad());auto p=r.preview("demo:a",{},{});auto saved=r.exportPreview(p["ticket"].toString(),p["sha256"].toString());QVERIFY(saved["ok"].toBool());
  const auto destination=root+"/chosen.json";const int create=::open(destination.toUtf8().constData(),O_CREAT|O_EXCL|O_RDWR,0600);QVERIFY(create>=0);
  if(kind=="nonempty")QCOMPARE(::write(create,"keep",4),ssize_t(4));
  int descriptor=create;if(kind=="read-only"){::close(create);descriptor=::open(destination.toUtf8().constData(),O_RDONLY);QVERIFY(descriptor>=0);}
  QSignalSpy finished(&r,&FailureReports::documentCopyFinished);auto pending=r.copyPrivateExport(saved["copyToken"].toString(),p["sha256"].toString());QVERIFY(pending["pending"].toBool());QCOMPARE(suggested,saved["fileName"].toString());
  if(kind=="stale-before-result")r.observeSaveCopies("demo:b",{},{},bad());
  receive(documentTarget(descriptor),kind=="cancel"?"cancelled":kind=="unavailable"?"document_unavailable":kind=="chooser-refusal"?"chooser_unavailable":"");
  if(kind=="stale-queued-result")r.observeSaveCopies("demo:b",{},{},bad());
  int duplicate=-1;
  if(kind=="duplicate") {duplicate=::open((root+"/duplicate.json").toUtf8().constData(),O_CREAT|O_EXCL|O_RDWR,0600);QVERIFY(duplicate>=0);receive(documentTarget(duplicate),{});}
  QTRY_COMPARE_WITH_TIMEOUT(finished.size(),1,3000);QVERIFY(!r.documentCopyBusy());auto result=finished[0][1].toMap();
  const bool success=kind=="success" || kind=="duplicate";QCOMPARE(result["ok"].toBool(),success);
  QCOMPARE(finished[0][0].toString(),pending["request"].toString());QTRY_COMPARE_WITH_TIMEOUT(::fcntl(descriptor,F_GETFD),-1,3000);
  QFile read(destination);QVERIFY(read.open(QIODevice::ReadOnly));QCOMPARE(read.readAll(),success?p["text"].toString().toUtf8():kind=="nonempty"?QByteArray("keep"):QByteArray());
  if(kind=="chooser-refusal"){QCOMPARE(result["error"].toString(),QString("chooser_unavailable"));QVERIFY(result["message"].toString().contains("chooser is unavailable"));}
  if(success){QCOMPARE(result["sha256"],p["sha256"]);QVERIFY(result["providerLocationUnverified"].toBool());QVERIFY(!result.contains("sent"));}
  if(duplicate>=0){QTRY_COMPARE_WITH_TIMEOUT(::fcntl(duplicate,F_GETFD),-1,3000);QCOMPARE(QFileInfo(root+"/duplicate.json").size(),qint64(0));}
  QCOMPARE(QDir(root+"/failure-reports-v1").entryList(QDir::Files).size(),1);
 }
 void refusedPickerCannotWriteFromLateCallback(){
  QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();library::DocumentReceiver receive;
  FailureReports r(root,[&](const QString&,library::DocumentReceiver result){receive=result;return false;});r.observeSaveCopies("demo:a",{},{},bad());auto p=r.preview("demo:a",{},{});auto saved=r.exportPreview(p["ticket"].toString(),p["sha256"].toString());
  QSignalSpy finished(&r,&FailureReports::documentCopyFinished);QVERIFY(!r.copyPrivateExport(saved["copyToken"].toString(),p["sha256"].toString())["ok"].toBool());QVERIFY(!r.documentCopyBusy());
  auto path=root+"/late.json";int fd=::open(path.toUtf8().constData(),O_CREAT|O_EXCL|O_RDWR,0600);QVERIFY(fd>=0);receive(documentTarget(fd),{});QTRY_COMPARE_WITH_TIMEOUT(::fcntl(fd,F_GETFD),-1,3000);QCOMPARE(finished.size(),0);QCOMPARE(QFileInfo(path).size(),qint64(0));
 }
 void destroyedOwner_data(){QTest::addColumn<bool>("worker");QTest::newRow("waiting-for-picker")<<false;QTest::newRow("worker-started")<<true;}
 void destroyedOwner(){
  QFETCH(bool,worker);QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();library::DocumentReceiver receive;
  auto r=std::unique_ptr<FailureReports>(new FailureReports(root,[&](const QString&,library::DocumentReceiver result){receive=result;return true;}));r->observeSaveCopies("demo:a",{},{},bad());auto p=r->preview("demo:a",{},{});auto saved=r->exportPreview(p["ticket"].toString(),p["sha256"].toString());QVERIFY(r->copyPrivateExport(saved["copyToken"].toString(),p["sha256"].toString())["pending"].toBool());
  auto path=root+"/selected.json";int fd=::open(path.toUtf8().constData(),O_CREAT|O_EXCL|O_RDWR,0600);QVERIFY(fd>=0);
  if(worker){receive(documentTarget(fd),{});QCoreApplication::sendPostedEvents(nullptr,QEvent::MetaCall);r.reset();}else {r.reset();receive(documentTarget(fd),{});}
  QTRY_COMPARE_WITH_TIMEOUT(::fcntl(fd,F_GETFD),-1,3000);if(!worker)QCOMPARE(QFileInfo(path).size(),qint64(0));
 }
 void documentWriterBoundsAndUnseekableTargets(){
  QTemporaryDir tmp;const auto path=QFileInfo(tmp.path()).canonicalFilePath()+"/empty.json";int fd=::open(path.toUtf8().constData(),O_CREAT|O_EXCL|O_RDWR,0600);QVERIFY(fd>=0);
  QVERIFY(!library::writeFailureDocument(fd,QByteArray(8193,'x'))["ok"].toBool());QCOMPARE(QFileInfo(path).size(),qint64(0));
  QVERIFY(!library::writeFailureDocument(fd,QByteArray("approved"),[]{return true;})["ok"].toBool());QCOMPARE(QFileInfo(path).size(),qint64(0));::close(fd);
  int pipefd[2];QCOMPARE(::pipe(pipefd),0);QVERIFY(!library::writeFailureDocument(pipefd[1],QByteArray("approved"))["ok"].toBool());::close(pipefd[0]);::close(pipefd[1]);
 }
 void slowProviderKeepsGuiUsableAndAcceptsCancellation(){
  QTemporaryDir tmp;auto root=QFileInfo(tmp.path()).canonicalFilePath();library::DocumentReceiver receive;
  FailureReports r(root,[&](const QString&,library::DocumentReceiver result){receive=result;return true;});r.observeSaveCopies("demo:a",{},{},bad());auto p=r.preview("demo:a",{},{});auto saved=r.exportPreview(p["ticket"].toString(),p["sha256"].toString());QVERIFY(r.copyPrivateExport(saved["copyToken"].toString(),p["sha256"].toString())["pending"].toBool());
  const auto path=root+"/slow.json";int fd=::open(path.toUtf8().constData(),O_CREAT|O_EXCL|O_RDWR,0600);QVERIFY(fd>=0);auto entered=std::make_shared<std::atomic_bool>(false);
  receive([target=documentTarget(fd),entered](const QByteArray& bytes,const std::function<bool()>& cancelled){
   entered->store(true);for(int i=0;i<500 && !cancelled();++i)QThread::msleep(1);
   return target(bytes,cancelled);
  },{});
  QTRY_VERIFY(entered->load());int ticks=0;QTimer timer;connect(&timer,&QTimer::timeout,this,[&]{++ticks;});timer.start(1);QTRY_VERIFY(ticks>=3);QVERIFY(r.documentCopyBusy());
  QSignalSpy finished(&r,&FailureReports::documentCopyFinished);r.observeSaveCopies("demo:b",{},{},bad());QTRY_VERIFY(!r.documentCopyBusy());QCOMPARE(finished.size(),1);QVERIFY(!finished[0][1].toMap()["copied"].toBool());QTRY_COMPARE_WITH_TIMEOUT(::fcntl(fd,F_GETFD),-1,3000);QCOMPARE(QFileInfo(path).size(),qint64(0));
 }
#endif
 void conformanceFixture(){
  const QString out=qEnvironmentVariable("NOVA_FAILURE_FIXTURE");if(out.isEmpty())QSKIP("No fixture output requested");QTemporaryDir tmp;FailureReports r(QFileInfo(tmp.path()).canonicalFilePath());r.observeSaveCopies("demo:failure",{},{},bad());auto p=r.preview("demo:failure",{},{});QVERIFY(p["ok"].toBool());auto text=p["text"].toString().toUtf8();const QJsonValue stamp=QJsonDocument::fromJson(text).object()["observedAt"];
  QJsonObject observed{{"editionId","demo:failure"},{"recipeId","nova.copy.open.v1"},{"sourceSha256",QJsonValue::Null},{"buildSha256",QJsonValue::Null},{"runtimeId",QJsonValue::Null},{"runtimeVersion",QJsonValue::Null}};
  QJsonObject raw{{"schemaVersion",2},{"origin","native-save-copies"},{"editionId","demo:failure"},{"observedRecipeId","nova.copy.open.v1"},{"activeRecipeId",QJsonValue::Null},{"observedAt",stamp},{"stage","preflight"},
   {"facts",QJsonArray{QJsonObject{{"code","copy-history-unavailable"},{"method","test"}}}},{"hypotheses",QJsonArray{QJsonObject{{"code","unknown-cause"},{"basedOn",QJsonArray{"copy-history-unavailable"}}}}},
   {"provenance",QJsonObject{{"observed",observed},{"active",QJsonValue::Null},{"collection",QJsonObject{{"status","collected"},{"method","synthetic"},{"collectedAt",stamp}}}}}};
  put(out+"/native-preview.json",text);put(out+"/descriptor.json",QJsonDocument(raw).toJson());
 }
};
QTEST_GUILESS_MAIN(Checks)
#include "tst_FailureReports.moc"
