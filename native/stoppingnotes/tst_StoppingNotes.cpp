// SPDX-License-Identifier: GPL-3.0-or-later
#include "StoppingNotes.h"
#include <QtTest>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QImage>
#include <QJsonDocument>
#include <QProcess>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QTemporaryDir>
#include <QUrl>
using library::StoppingNotes;
namespace {
const QString Edition="fixture:snes:one", Other="fixture:snes:two";
QString digest(const QByteArray& b){return QString::fromLatin1(QCryptographicHash::hash(b,QCryptographicHash::Sha256).toHex());}
QString url(const QString& path){return QUrl::fromLocalFile(path).toString();}
QVariantMap notebook(const QVariantMap& result){return result.value("notebook").toMap();}
int rev(const QVariantMap& result){return notebook(result).value("revision").toInt();}
QVariantMap first(const QVariantMap& result){return notebook(result).value("notes").toList().value(0).toMap();}
QByteArray read(const QString& path){QFile f(path);if(!f.open(QIODevice::ReadOnly))return {};return f.readAll();}
void write(const QString& path,const QByteArray& bytes){QFile f(path);if(!f.open(QIODevice::WriteOnly)||f.write(bytes)!=bytes.size())qFatal("Synthetic fixture write failed");}
QString png(const QString& path){QImage i(120,80,QImage::Format_RGB32);i.fill(Qt::darkBlue);if(!i.save(path,"PNG"))qFatal("Synthetic PNG failed");return path;}
QVariantMap mark(){return {{"kind","ellipse"},{"x1",.1},{"y1",.2},{"x2",.4},{"y2",.6},{"text","Door I marked"},{"colour","amber"}};}
QVariantMap old(){return {{"text","  My original text-only checkpoint  "},{"revision",7},{"pending",true},{"conflict",true},{"source","you"}};}
QString docPath(const QString& root,const QString& id=Edition){return root+"/"+digest(id.toUtf8())+"/notebook.json";}
int processMode(const QStringList& args) {
    const QString mode=args.value(1), root=args.value(2);
    StoppingNotes store(root);
    if(mode=="--seed") {
        const auto source=png(QFileInfo(root).absolutePath()+"/explicit-original.png");
        auto r=store.importOriginal(Edition,url(source),0);if(!r.value("ok").toBool())return 11;
        r=store.createNote(Edition,{{"text","Room code 1234"},{"imageId",r.value("imageId")},{"annotations",QVariantList{mark()}}},rev(r));if(!r.value("ok").toBool())return 12;
        r=store.editNote(Edition,r.value("noteId").toString(),{{"text","Room code 5678"}},rev(r));return r.value("ok").toBool()?0:13;
    }
    const auto r=store.openEdition(Edition,{});const auto n=first(r);
    if(!r.value("ok").toBool()||n.value("text")!="Room code 5678"||n.value("imageStatus")!="ready"||n.value("annotations").toList().size()!=1)return 14;
    if(mode=="--clear")return store.clearNote(Edition,n.value("id").toString(),rev(r)).value("ok").toBool()?0:15;
    if(mode=="--verify-cleared")return n.value("cleared").toBool()&&notebook(r).value("stoppingNoteId").toString().isEmpty()?0:16;
    return 17;
}
}
class Tests:public QObject {
    Q_OBJECT
private slots:
    void screenshotChoicesStayExplicitAndBounded() {
        QTemporaryDir d;const auto folder=d.path()+"/screenshots";QVERIFY(QDir().mkdir(folder));
        const auto source=png(folder+"/chosen.png");png(d.path()+"/outside.png");
        QVERIFY(QDir().mkdir(folder+"/nested"));png(folder+"/nested/hidden.png");
        write(folder+"/ignored.txt","not an image");QVERIFY(QFile::link(d.path()+"/outside.png",folder+"/linked.png"));
        StoppingNotes store(d.path()+"/store",nullptr,folder);
        auto r=store.imageChoices();QVERIFY(r.value("ok").toBool());QCOMPARE(r.value("choices").toList().size(),1);
        const auto item=r.value("choices").toList().first().toMap();QCOMPARE(item.value("label").toString(),QString("chosen.png"));QCOMPARE(item.value("fileUrl").toString(),url(source));
        QVERIFY(!QFileInfo::exists(docPath(d.path()+"/store"))); // Listing never imports.
        auto imported=store.importOriginal(Edition,item.value("fileUrl").toString(),0);QVERIFY(imported.value("ok").toBool());
        QCOMPARE(read(source),read(d.path()+"/store/"+digest(Edition.toUtf8())+"/originals/"+imported.value("imageId").toString()));
        for(int i=0;i<70;i++)png(folder+QString("/extra-%1.png").arg(i));
        r=store.imageChoices();QCOMPARE(r.value("choices").toList().size(),64);QVERIFY(r.value("more").toBool());
        StoppingNotes unavailable(d.path()+"/other",nullptr,d.path()+"/absent");QVERIFY(!unavailable.imageChoices().value("ok").toBool());
    }

    void realProcessRestartEditClearRetainsOriginal() {
        QTemporaryDir d;const auto root=d.path()+"/private-store";
        QCOMPARE(QProcess::execute(QCoreApplication::applicationFilePath(),{"--seed",root}),0);
        const auto before=read(d.path()+"/explicit-original.png");QVERIFY(!before.isEmpty());
        QCOMPARE(QProcess::execute(QCoreApplication::applicationFilePath(),{"--clear",root}),0);
        QCOMPARE(QProcess::execute(QCoreApplication::applicationFilePath(),{"--verify-cleared",root}),0);
        QCOMPARE(read(d.path()+"/explicit-original.png"),before);
        StoppingNotes s(root);auto r=s.openEdition(Edition,{});const auto n=first(r);
        QCOMPARE(read(QUrl(n.value("imageUrl").toString()).toLocalFile()),before);
        QVERIFY(s.search(Edition,"5678",false).value("matches").toList().isEmpty());
        QCOMPARE(s.search(Edition,"door I",true).value("matches").toList().size(),1);
        r=s.restoreNote(Edition,n.value("id").toString(),rev(r));QVERIFY(r.value("ok").toBool());
        QVERIFY(!first(r).value("cleared").toBool());
        r=s.setStoppingNote(Edition,n.value("id").toString(),rev(r));QVERIFY(r.value("ok").toBool());
        QCOMPARE(notebook(r).value("stoppingNoteId").toString(),n.value("id").toString());
    }
    void exactEditionIsolationAndImmutableAssociation() {
        QTemporaryDir d;StoppingNotes s(d.path()+"/store");const auto image=png(d.path()+"/source.png");
        auto imported=s.importOriginal(Edition,url(image),0);QVERIFY(imported.value("ok").toBool());const auto imageId=imported.value("imageId").toString();
        auto wrong=s.createNote(Other,{{"text","Same title, other edition"},{"imageId",imageId}},0);QVERIFY(!wrong.value("ok").toBool());
        auto r=s.createNote(Edition,{{"text","My clue"},{"imageId",imageId},{"annotations",QVariantList{mark()}}},rev(imported));QVERIFY(r.value("ok").toBool());
        QVERIFY(notebook(s.openEdition(Other,{})).value("notes").toList().isEmpty());
        const auto originalPath=QUrl(first(r).value("imageUrl").toString()).toLocalFile();const auto bytes=read(originalPath);
        r=s.editNote(Edition,r.value("noteId").toString(),{{"annotations",QVariantList()},{"imageId",""}},rev(r));QVERIFY(r.value("ok").toBool());
        QCOMPARE(read(originalPath),bytes);QCOMPARE(read(image),bytes);
        QVERIFY(!s.openEdition("untagged:Same title|path",{}).value("ok").toBool());
        QVERIFY(!s.openEdition("",{}).value("ok").toBool());
    }
    void legacyReadAndExplicitAdoptionPreserveConflict() {
        QTemporaryDir d;StoppingNotes s(d.path()+"/store");const auto legacy=old();
        auto r=s.openEdition(Edition,legacy);QVERIFY(r.value("ok").toBool());QCOMPARE(r.value("legacyCheckpoint").toMap(),legacy);
        QVERIFY(!QFileInfo::exists(docPath(d.path()+"/store")));
        r=s.adoptLegacy(Edition,legacy,0);QVERIFY(r.value("ok").toBool());
        QCOMPARE(first(r).value("text").toString(),legacy.value("text").toString());QCOMPARE(first(r).value("legacyReference").toMap(),legacy);
        QCOMPARE(first(s.openEdition(Edition,legacy)).value("imageStatus").toString(),QString("none"));QCOMPARE(legacy,old());
    }
    void revisionsRetainBothEditors() {
        QTemporaryDir d;StoppingNotes a(d.path()+"/store"),b(d.path()+"/store");
        auto initial=a.createNote(Edition,{{"text","First"}},0);QVERIFY(initial.value("ok").toBool());const auto id=initial.value("noteId").toString();
        auto updated=a.editNote(Edition,id,{{"text","Editor one"}},1);QVERIFY(updated.value("ok").toBool());
        auto refused=b.editNote(Edition,id,{{"text","Editor two"}},1);QCOMPARE(refused.value("error").toString(),QString("revision_conflict"));QCOMPARE(refused.value("current").toMap().value("revision").toInt(),2);
        QCOMPARE(first(b.openEdition(Edition,{})).value("text").toString(),QString("Editor one"));
        auto fork=b.createNote(Edition,{{"text","Editor two"}},2);QVERIFY(fork.value("ok").toBool());QCOMPARE(notebook(fork).value("notes").toList().size(),2);
    }
    void missingCorruptImageDoesNotEraseTextOrExportPartial() {
        QTemporaryDir d;StoppingNotes s(d.path()+"/store");auto r=s.importOriginal(Edition,url(png(d.path()+"/source.png")),0);QVERIFY(r.value("ok").toBool());
        r=s.createNote(Edition,{{"text","Keep my written clue"},{"imageId",r.value("imageId")}},rev(r));QVERIFY(r.value("ok").toBool());
        const auto path=QUrl(first(r).value("imageUrl").toString()).toLocalFile();const auto bytes=read(path);QVERIFY(QFile::remove(path));
        auto missing=first(s.openEdition(Edition,{}));QCOMPARE(missing.value("imageStatus").toString(),QString("missing"));QCOMPARE(missing.value("text").toString(),QString("Keep my written clue"));
        QVERIFY(!s.exportEdition(Edition,url(d.path()+"/missing-export")).value("ok").toBool());QVERIFY(!QFileInfo::exists(d.path()+"/missing-export"));
        write(path,"corrupt original");QCOMPARE(first(s.openEdition(Edition,{})).value("imageStatus").toString(),QString("corrupt"));
        QVERIFY(!s.importOriginal(Edition,url(d.path()+"/source.png"),rev(r)).value("ok").toBool());QCOMPARE(read(path),QByteArray("corrupt original"));
        write(path,bytes);QCOMPARE(first(s.openEdition(Edition,{})).value("imageStatus").toString(),QString("ready"));
    }
    void corruptMetadataNeverBecomesAnEmptyWritableNotebook() {
        QTemporaryDir d;StoppingNotes s(d.path()+"/store");auto r=s.createNote(Edition,{{"text","Retain"}},0);QVERIFY(r.value("ok").toBool());const auto path=docPath(d.path()+"/store");
        const auto good=read(path);write(path,"{broken");
        QCOMPARE(s.openEdition(Edition,{}).value("error").toString(),QString("corrupt_metadata"));QVERIFY(!s.createNote(Edition,{{"text","Replacement"}},0).value("ok").toBool());QCOMPARE(read(path),QByteArray("{broken"));
        write(path,good);auto doc=QJsonDocument::fromJson(good).toVariant().toMap();doc["editionId"]=Other;write(path,QJsonDocument::fromVariant(doc).toJson());
        QCOMPARE(s.openEdition(Edition,{}).value("error").toString(),QString("corrupt_metadata"));
    }
    void failedAtomicWriteRetainsCommittedRecordAndOriginal() {
        QTemporaryDir d;const auto root=d.path()+"/store";StoppingNotes s(root);auto r=s.createNote(Edition,{{"text","Committed"}},0);QVERIFY(r.value("ok").toBool());const auto path=docPath(root);const auto before=read(path);const auto dir=QFileInfo(path).absolutePath();
        QVERIFY(QFile::setPermissions(dir,QFileDevice::ReadOwner|QFileDevice::ExeOwner));
        auto refused=s.editNote(Edition,r.value("noteId").toString(),{{"text","Must not replace"}},rev(r));
        QVERIFY(QFile::setPermissions(dir,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner));
        QCOMPARE(refused.value("error").toString(),QString("write_failed"));QCOMPARE(read(path),before);QCOMPARE(first(s.openEdition(Edition,{})).value("text").toString(),QString("Committed"));
    }
    void failedImageAssociationRetainsBothOriginalsAndCanRetry() {
        QTemporaryDir d;const auto root=d.path()+"/store";StoppingNotes s(root);
        auto imported=s.importOriginal(Edition,url(png(d.path()+"/first.png")),0);QVERIFY(imported.value("ok").toBool());
        auto r=s.createNote(Edition,{{"text","Committed image"},{"imageId",imported.value("imageId")}},rev(imported));QVERIFY(r.value("ok").toBool());
        const auto original=QUrl(first(r).value("imageUrl").toString()).toLocalFile();const auto originalBytes=read(original);
        QImage second(90,70,QImage::Format_RGB32);second.fill(Qt::red);QVERIFY(second.save(d.path()+"/second.png","PNG"));const auto secondBytes=read(d.path()+"/second.png");
        const auto metadata=docPath(root),dir=QFileInfo(metadata).absolutePath();const auto before=read(metadata);
        QVERIFY(QFile::setPermissions(dir,QFileDevice::ReadOwner|QFileDevice::ExeOwner));
        auto refused=s.importOriginal(Edition,url(d.path()+"/second.png"),rev(r));
        QVERIFY(QFile::setPermissions(dir,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner));
        QCOMPARE(refused.value("error").toString(),QString("write_failed"));QCOMPARE(read(metadata),before);QCOMPARE(read(original),originalBytes);
        QCOMPARE(read(dir+"/originals/"+digest(secondBytes)),secondBytes);QCOMPARE(read(d.path()+"/second.png"),secondBytes);
        auto retried=s.importOriginal(Edition,url(d.path()+"/second.png"),rev(r));QVERIFY(retried.value("ok").toBool());QCOMPARE(retried.value("imageId").toString(),digest(secondBytes));
    }
    void oversizedAndSymlinkInputsStayOutsideTheStore() {
        QTemporaryDir d;const auto root=d.path()+"/store";StoppingNotes s(root);
        write(d.path()+"/too-large.png",QByteArray(16*1024*1024+1,'x'));
        QCOMPARE(s.importOriginal(Edition,url(d.path()+"/too-large.png"),0).value("error").toString(),QString("image_unreadable_or_too_large"));
        const auto source=png(d.path()+"/source.png");QVERIFY(QFile::link(source,d.path()+"/linked.png"));
        QVERIFY(!s.importOriginal(Edition,url(d.path()+"/linked.png"),0).value("ok").toBool());
        auto r=s.createNote(Edition,{{"text","Retain"}},0);QVERIFY(r.value("ok").toBool());const auto path=docPath(root);const auto before=read(path);
        write(d.path()+"/outside",before);QVERIFY(QFile::remove(path));QVERIFY(QFile::link(d.path()+"/outside",path));
        QCOMPARE(s.editNote(Edition,r.value("noteId").toString(),{{"text","Must not escape"}},rev(r)).value("error").toString(),QString("unsafe_storage_path"));QCOMPARE(read(d.path()+"/outside"),before);
    }
    void retainedOrphansCannotBypassOriginalQuota() {
        QTemporaryDir d;const auto root=d.path()+"/store";StoppingNotes s(root);
        auto r=s.importOriginal(Edition,url(png(d.path()+"/source.png")),0);QVERIFY(r.value("ok").toBool());
        const auto dir=QFileInfo(docPath(root)).absolutePath()+"/originals";
        for(int i=0;i<31;i++)write(dir+"/"+digest(QByteArray::number(i)),"retained orphan fixture");
        QImage other(12,10,QImage::Format_RGB32);other.fill(Qt::red);QVERIFY(other.save(d.path()+"/other.png","PNG"));const auto before=read(docPath(root));
        QCOMPARE(s.importOriginal(Edition,url(d.path()+"/other.png"),rev(r)).value("error").toString(),QString("original_storage_limit"));QCOMPARE(read(docPath(root)),before);
    }
    void boundsPathsAndPrivatePortableExport() {
        QTemporaryDir d;const auto root=d.path()+"/store";StoppingNotes s(root);
        QVERIFY(!s.importOriginal(Edition,"https://example.test/image.png",0).value("ok").toBool());
        write(d.path()+"/not-image","not an image");QVERIFY(!s.importOriginal(Edition,url(d.path()+"/not-image"),0).value("ok").toBool());
        QVERIFY(!s.createNote(Edition,{{"text",QString(4001,'x')}},0).value("ok").toBool());
        QVERIFY(!s.createNote(Edition,{{"text","x"}},true).value("ok").toBool());
        QVERIFY(!s.createNote(Edition,{{"text","x"}},0.5).value("ok").toBool());
        auto imported=s.importOriginal(Edition,url(png(d.path()+"/source.png")),0);QVERIFY(imported.value("ok").toBool());
        auto invalid=mark();invalid["x2"]=1.1;QVERIFY(!s.createNote(Edition,{{"text","x"},{"imageId",imported.value("imageId")},{"annotations",QVariantList{invalid}}},rev(imported)).value("ok").toBool());
        auto r=s.createNote(Edition,{{"text","Private note"},{"imageId",imported.value("imageId")},{"annotations",QVariantList{mark()}}},rev(imported));QVERIFY(r.value("ok").toBool());
        const auto exportPath=d.path()+"/explicit-export";QVERIFY(s.exportEdition(Edition,url(exportPath)).value("ok").toBool());
        const auto exported=read(exportPath+"/notebook.json");QVERIFY(!exported.contains(d.path().toUtf8()));QVERIFY(!exported.contains("imageUrl"));QVERIFY(exported.contains("Private note"));
        QCOMPARE(read(exportPath+"/originals/"+imported.value("imageId").toString()),read(d.path()+"/source.png"));
        QVERIFY(!s.exportEdition(Edition,url(exportPath)).value("ok").toBool());QCOMPARE(read(exportPath+"/notebook.json"),exported);
        QVERIFY(!s.exportEdition(Edition,url(root+"/export")).value("ok").toBool());
        QVERIFY(!(QFileInfo(exportPath+"/notebook.json").permissions()&QFileDevice::ReadGroup));
        auto unowned=d.path()+"/unowned";QDir().mkdir(unowned);write(unowned+"/keep","keep");StoppingNotes refused(unowned);QVERIFY(!refused.capabilities().value("ok").toBool());QCOMPARE(read(unowned+"/keep"),QByteArray("keep"));
    }
    void qmlModelKeepsDraftOnConflictAndFailure() {
        QTemporaryDir d;StoppingNotes storage(d.path()+"/store");QQmlEngine engine;QQmlComponent component(&engine,QUrl("qrc:/stoppingnotes/StoppingNoteModel.qml"));
        QScopedPointer<QObject> model(component.create());QVERIFY2(model,qPrintable(component.errorString()));QVERIFY(model->setProperty("storage",QVariant::fromValue<QObject*>(&storage)));
        auto invoke=[&](const char* method,QVariant a=QVariant(),QVariant b=QVariant()) {QVariant out;bool ok;
            if(b.isValid())ok=QMetaObject::invokeMethod(model.data(),method,Q_RETURN_ARG(QVariant,out),Q_ARG(QVariant,a),Q_ARG(QVariant,b));
            else if(a.isValid())ok=QMetaObject::invokeMethod(model.data(),method,Q_RETURN_ARG(QVariant,out),Q_ARG(QVariant,a));
            else ok=QMetaObject::invokeMethod(model.data(),method,Q_RETURN_ARG(QVariant,out));
            if(!ok)qFatal("QML fixture invocation failed");return out;};
        QVERIFY(invoke("open",Edition,QVariantMap()).toBool());invoke("setText","My draft");
        QVERIFY(storage.createNote(Edition,{{"text","Other writer"}},0).value("ok").toBool());
        QVERIFY(!invoke("save").toBool());QCOMPARE(model->property("lastError").toString(),QString("revision_conflict"));QCOMPARE(model->property("draft").toMap().value("text").toString(),QString("My draft"));QVERIFY(model->property("dirty").toBool());
        QVERIFY(invoke("keepDraftAsNew").toBool());QCOMPARE(notebook(storage.openEdition(Edition,{})).value("notes").toList().size(),2);
        invoke("setText","Uncommitted");const auto path=docPath(d.path()+"/store");const auto before=read(path);const auto dir=QFileInfo(path).absolutePath();QVERIFY(QFile::setPermissions(dir,QFileDevice::ReadOwner|QFileDevice::ExeOwner));
        QVERIFY(!invoke("save").toBool());QVERIFY(QFile::setPermissions(dir,QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner));QCOMPARE(read(path),before);QCOMPARE(model->property("draft").toMap().value("text").toString(),QString("Uncommitted"));
        QVERIFY(!invoke("exportTo",url(d.path()+"/store/forbidden-export")).toMap().value("ok").toBool());
        QVERIFY(invoke("exportTo",url(d.path()+"/explicit-export")).toMap().value("ok").toBool());QVERIFY(model->property("lastError").toString().isEmpty());QVERIFY(model->property("dirty").toBool());
    }
};
int main(int argc,char** argv){QCoreApplication app(argc,argv);if(app.arguments().value(1).startsWith("--"))return processMode(app.arguments());Tests tests;return QTest::qExec(&tests,argc,argv);}
#include "tst_StoppingNotes.moc"
