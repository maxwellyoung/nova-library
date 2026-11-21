#include "SaveCopies.h"
#include <QTest>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonObject>
#include <QJsonDocument>
#include <QCryptographicHash>
#include <QRegularExpression>

namespace {
QString sha(const QByteArray& bytes){return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());}
bool put(const QString& path,const QByteArray& bytes){QFile f(path);if(!f.open(QIODevice::WriteOnly))return false;f.setPermissions(QFile::ReadOwner|QFile::WriteOwner);return f.write(bytes)==bytes.size();}
QJsonObject entry(const QByteArray& bytes,const QString& edition="demo:orbit",const QString& id=QString(32,'a')) {
    return {{"checkpointId",id},{"sha256",sha(bytes)},{"bytes",bytes.size()},
        {"identity",QJsonObject{{"editionId",edition},{"recipeId","fixture.v1"},{"kind","native-save"},
            {"runtime",QJsonObject{{"name","Fixture"},{"version","1.0"},{"core","standalone"}}}}},
        {"name","Before the lift"},{"pinned",true},{"capturedAt","2026-11-09T10:00:00Z"},
        {"addedAt","2026-11-10T10:00:00Z"},{"files",1},{"payloadBytes",23}};
}
void writeIndex(const QString& root,const QJsonArray& rows,int version=1){QVERIFY(put(root+"/catalogue.json",QJsonDocument(QJsonObject{{"schemaVersion",version},{"source",QStringLiteral("verified-passport-export-v%1").arg(version)},{"entries",rows}}).toJson(QJsonDocument::Compact)));}
void setup(const QString& root,const QByteArray& bytes){QVERIFY(QDir().mkpath(root+"/archives"));QVERIFY(QFile::setPermissions(root+"/archives",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));QVERIFY(put(root+"/archives/"+sha(bytes)+".nvs",bytes));writeIndex(root,{entry(bytes)});}
QByteArray pictureBytes(){return QByteArray::fromHex("89504e470d0a1a0a0000000d4948445200000001000000010802000000907753de0000000c49444154789c63105030000000a4006134667d720000000049454e44ae426082");}
void addPicture(const QString& root,const QByteArray& png=pictureBytes()){
    QVERIFY(QDir(root).mkdir("pictures"));QVERIFY(QFile::setPermissions(root+"/pictures",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));
    QVERIFY(put(root+"/pictures/"+sha(png)+".png",png));auto row=entry("bytes");
    row.insert("picture",QJsonObject{{"state","available"},{"sha256",sha(png)},{"bytes",png.size()}});writeIndex(root,{row},2);
}
}
class Tests:public QObject {
    Q_OBJECT
private slots:
    void readOnlyCapabilities(){library::SaveCopies s("/absent");auto c=s.capabilities();QVERIFY(c["readOnly"].toBool());QVERIFY(!c["capture"].toBool());QVERIFY(!c["runtimeRestoreAvailable"].toBool());}
    void absentDoesNotCreateStorage(){QTemporaryDir t;QString path=QDir(t.path()).canonicalPath()+"/absent";library::SaveCopies s(path);QVERIFY(s.openEdition("demo:orbit")["ok"].toBool());QVERIFY(!QFileInfo::exists(path));}
    void exactEditionAndMetadata(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"synthetic archive bytes");auto other=entry("other","demo:other",QString(32,'b'));writeIndex(root,{entry("synthetic archive bytes"),other});library::SaveCopies s(root);auto r=s.openEdition("demo:orbit");QVERIFY(r["ok"].toBool());auto rows=r["copies"].toList();QCOMPARE(rows.size(),1);auto row=rows[0].toMap();QCOMPARE(row["name"].toString(),QString("Before the lift"));QVERIFY(row["pinned"].toBool());QCOMPARE(row["copyState"].toString(),QString("not-rechecked"));QVERIFY(!row["runtimeRestoreAvailable"].toBool());QCOMPARE(s.openEdition("demo:absent")["copies"].toList().size(),0);}
    void checksumReviewIsAsyncAndReadOnly(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"synthetic archive bytes");library::SaveCopies s(root);QSignalSpy spy(&s,&library::SaveCopies::reviewFinished);auto queued=s.review("demo:orbit",QString(32,'a'));QVERIFY(queued["ok"].toBool());QTRY_COMPARE(spy.count(),1);auto result=spy.at(0).at(1).toMap();QVERIFY(result["ok"].toBool());QVERIFY(result["archiveChecksumMatched"].toBool());QVERIFY(!result["runtimeRestoreAvailable"].toBool());QCOMPARE(spy.at(0).at(0).toString(),queued["token"].toString());QCOMPARE(QDir(root).entryList(QDir::NoDotAndDotDot|QDir::AllEntries),QStringList({"archives","catalogue.json"}));}
    void checksumCorruptionIsNotSuccess(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();QByteArray original("synthetic archive bytes");setup(root,original);QVERIFY(put(root+"/archives/"+sha(original)+".nvs",QByteArray(original.size(),'x')));library::SaveCopies s(root);QSignalSpy spy(&s,&library::SaveCopies::reviewFinished);QVERIFY(s.review("demo:orbit",QString(32,'a'))["ok"].toBool());QTRY_COMPARE(spy.count(),1);QVERIFY(!spy.at(0).at(1).toMap()["ok"].toBool());}
    void reviewRejectsSnapshotChangedBeforeItStarts_data(){QTest::addColumn<bool>("replaceArchive");QTest::newRow("renamed-row")<<false;QTest::newRow("replacement-archive")<<true;}
    void reviewRejectsSnapshotChangedBeforeItStarts(){
        QFETCH(bool,replaceArchive);QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"original archive");library::SaveCopies s(root);
        const auto displayed=s.openEdition("demo:orbit");const auto expected=displayed["indexSha256"].toString();
        auto changed=entry(replaceArchive?"replacement archive":"original archive");changed["name"]="Changed after listing";
        if(replaceArchive)QVERIFY(put(root+"/archives/"+sha("replacement archive")+".nvs","replacement archive"));
        writeIndex(root,{changed});QSignalSpy spy(&s,&library::SaveCopies::reviewFinished);QVariantMap queued;
        // The baseline fallback reproduces the original caller's two-argument path.
        if(s.metaObject()->indexOfMethod("reviewSnapshot(QString,QString,QString)")>=0)
            QVERIFY(QMetaObject::invokeMethod(&s,"reviewSnapshot",Q_RETURN_ARG(QVariantMap,queued),Q_ARG(QString,QString("demo:orbit")),Q_ARG(QString,QString(32,'a')),Q_ARG(QString,expected)));
        else queued=s.review("demo:orbit",QString(32,'a'));
        if(queued["ok"].toBool()){
            QTRY_COMPARE(spy.count(),1);
            QVERIFY2(!spy.at(0).at(1).toMap()["ok"].toBool(),"A new index/archive was verified beneath the displayed old row");
        }else{QCOMPARE(queued["error"].toString(),QString("history_changed"));QCOMPARE(spy.count(),0);}
        QFile original(root+"/archives/"+sha("original archive")+".nvs");QVERIFY(original.open(QIODevice::ReadOnly));QCOMPARE(original.readAll(),QByteArray("original archive"));
    }
    void missingCopiesStayVisible(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");QVERIFY(QFile::remove(root+"/archives/"+sha("bytes")+".nvs"));library::SaveCopies s(root);QCOMPARE(s.openEdition("demo:orbit")["copies"].toList().at(0).toMap()["copyState"].toString(),QString("missing"));}
    void snapshotReviewRequiresAValidDisplayedIndex(){
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"original archive");library::SaveCopies s(root);QCOMPARE(s.capabilities()["reviewSnapshotVersion"].toInt(),1);
        QSignalSpy spy(&s,&library::SaveCopies::reviewFinished);
        for(const QString bad:{QString(),QString("../path"),QString(64,'A'),QString(63,'a')})QCOMPARE(s.reviewSnapshot("demo:orbit",QString(32,'a'),bad)["error"].toString(),QString("invalid_snapshot"));
        QCOMPARE(spy.count(),0);const auto displayed=s.openEdition("demo:orbit");
        QVERIFY(s.reviewSnapshot("demo:orbit",QString(32,'a'),displayed["indexSha256"].toString())["ok"].toBool());QTRY_COMPARE(spy.count(),1);QVERIFY(spy.at(0).at(1).toMap()["archiveChecksumMatched"].toBool());
    }
    void crossEditionAndUnknownIdsRefuse(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");library::SaveCopies s(root);QVERIFY(!s.review("demo:other",QString(32,'a'))["ok"].toBool());QVERIFY(!s.review("demo:orbit","../../secret")["ok"].toBool());QVERIFY(!s.openEdition("<invalid>")["ok"].toBool());}
    void partialAndMalformedIndexRefuse(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();library::SaveCopies s(root);QVERIFY(!s.openEdition("demo:orbit")["ok"].toBool());QVERIFY(put(root+"/catalogue.json","{"));QVERIFY(!s.openEdition("demo:orbit")["ok"].toBool());auto invalid=entry("bytes");invalid["sha256"]="../other";writeIndex(root,{invalid});QVERIFY(!s.openEdition("demo:orbit")["ok"].toBool());writeIndex(root,{entry("bytes"),entry("bytes")});QVERIFY(!s.openEdition("demo:orbit")["ok"].toBool());}
    void duplicateJsonKeysAreNotCollapsedIntoTrustedMetadata(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();QVERIFY(put(root+"/catalogue.json","{\"entries\":[],\"schemaVersion\":1,\"schemaVersion\":1,\"source\":\"verified-passport-export-v1\"}"));library::SaveCopies s(root);QVERIFY(!s.openEdition("demo:orbit")["ok"].toBool());}
    void indexChangeAndCancellationDoNotPromoteResult(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();QByteArray bytes(32*1024*1024,'x');setup(root,bytes);library::SaveCopies s(root);QSignalSpy spy(&s,&library::SaveCopies::reviewFinished);QVERIFY(s.review("demo:orbit",QString(32,'a'))["ok"].toBool());QVERIFY(!s.review("demo:orbit",QString(32,'a'))["ok"].toBool());writeIndex(root,{});QTRY_COMPARE(spy.count(),1);QVERIFY(!spy.at(0).at(1).toMap()["ok"].toBool());writeIndex(root,{entry(bytes)});spy.clear();QVERIFY(s.review("demo:orbit",QString(32,'a'))["ok"].toBool());s.cancelReview();QTRY_COMPARE(spy.count(),1);QVERIFY(!spy.at(0).at(1).toMap()["ok"].toBool());}
    void linkedAndSharedStorageRefuse(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");library::SaveCopies s(root);
#ifdef Q_OS_UNIX
        QVERIFY(QFile::setPermissions(root+"/catalogue.json",QFile::ReadOwner|QFile::WriteOwner|QFile::ReadGroup));QVERIFY(!s.openEdition("demo:orbit")["ok"].toBool());QVERIFY(QFile::setPermissions(root+"/catalogue.json",QFile::ReadOwner|QFile::WriteOwner));
        auto linked=root+"-link";QVERIFY(QFile::link(root,linked));library::SaveCopies other(linked);QVERIFY(!other.openEdition("demo:orbit")["ok"].toBool());QVERIFY(QFile::remove(linked));
#endif
    }
    void reopenedHistoryPersistsWithoutWrites(){QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");QVariantMap first;{library::SaveCopies s(root);first=s.openEdition("demo:orbit");}library::SaveCopies s(root);QCOMPARE(s.openEdition("demo:orbit"),first);}
    void diagnosticsBindTheSuppliedRootWithoutExposingIt(){
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath()+"/absent";library::SaveCopies s(root);
        auto c=s.capabilities();QCOMPARE(c["storageDiagnosticsVersion"].toInt(),1);
        QCOMPARE(c["storageRootSha256"].toString(),sha(root.toUtf8()));
        QVERIFY(!QJsonDocument::fromVariant(c).toJson().contains(root.toUtf8()));
        QVERIFY(s.openEdition("demo:orbit")["ok"].toBool());QVERIFY(!QFileInfo::exists(root));
    }
    void folderPrivacyFailureNamesOnlyTheFailedCheck(){
#ifdef Q_OS_UNIX
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");library::SaveCopies s(root);
        QVERIFY(QFile::setPermissions(root,QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner|QFile::ReadGroup));
        auto r=s.openEdition("demo:orbit");QCOMPARE(r["error"].toString(),QString("storage_unavailable"));
        QCOMPARE(r["storageStage"].toString(),QString("copy-directory"));QCOMPARE(r["storageCheck"].toString(),QString("shared_permissions"));
        QCOMPARE(r["storageRootSha256"],s.capabilities()["storageRootSha256"]);
        QCOMPARE(s.review("demo:orbit",QString(32,'a'))["storageCheck"],r["storageCheck"]);
        QVERIFY(!QJsonDocument::fromVariant(r).toJson().contains(root.toUtf8()));
        QVERIFY(QFile::setPermissions(root,QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));
        QVERIFY(s.openEdition("demo:orbit")["ok"].toBool());
#else
        QSKIP("POSIX permission diagnostic");
#endif
    }
    void indexPrivacyIsDistinctFromFolderPrivacy(){
#ifdef Q_OS_UNIX
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");library::SaveCopies s(root);
        QVERIFY(QFile::setPermissions(root+"/catalogue.json",QFile::ReadOwner|QFile::WriteOwner|QFile::ReadGroup));
        auto r=s.openEdition("demo:orbit");QCOMPARE(r["storageStage"].toString(),QString("copy-index"));
        QCOMPARE(r["storageCheck"].toString(),QString("shared_permissions"));
        QVERIFY(QFile::setPermissions(root+"/catalogue.json",QFile::ReadOwner|QFile::WriteOwner));
        QVERIFY(s.openEdition("demo:orbit")["ok"].toBool());
#else
        QSKIP("POSIX permission diagnostic");
#endif
    }
    void parentAliasesRemainRefusedWithACanonicalCheck(){
#ifdef Q_OS_UNIX
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root+"/copies","bytes");
        QVERIFY(QFile::setPermissions(root+"/copies",QFile::ReadOwner|QFile::WriteOwner|QFile::ExeOwner));
        QVERIFY(QFile::link(root,root+"/alias"));library::SaveCopies s(root+"/alias/copies");
        auto r=s.openEdition("demo:orbit");QCOMPARE(r["storageStage"].toString(),QString("copy-directory"));
        QCOMPARE(r["storageCheck"].toString(),QString("canonical_mismatch"));QVERIFY(QFile::remove(root+"/alias"));
#else
        QSKIP("POSIX parent link diagnostic");
#endif
    }
    void linkedAndNonFileIndexesKeepTheirGuards(){
#ifdef Q_OS_UNIX
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");
        QVERIFY(QFile::rename(root+"/catalogue.json",root+"/retained-index"));
        QVERIFY(QFile::link(root+"/retained-index",root+"/catalogue.json"));library::SaveCopies s(root);
        auto r=s.openEdition("demo:orbit");QCOMPARE(r["storageStage"].toString(),QString("copy-index"));
        QCOMPARE(r["storageCheck"].toString(),QString("symbolic_link"));
        QVERIFY(QFile::remove(root+"/catalogue.json"));QVERIFY(QDir(root).mkdir("catalogue.json"));
        r=s.openEdition("demo:orbit");QCOMPARE(r["storageCheck"].toString(),QString("wrong_type"));
#else
        QSKIP("POSIX link diagnostic");
#endif
    }
    void malformedMetadataDoesNotInventAPrivacyReason(){
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();QVERIFY(put(root+"/catalogue.json","{"));
        library::SaveCopies s(root);auto r=s.openEdition("demo:orbit");QCOMPARE(r["error"].toString(),QString("invalid_index"));
        QCOMPARE(r["storageStage"].toString(),QString("copy-index"));QVERIFY(!r.contains("storageCheck"));
    }
    void attachedPictureIsBoundToTheSelectedEditionAndListSnapshot(){
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");addPicture(root);library::SaveCopies s(root);
        const auto listed=s.openEdition("demo:orbit");const auto revision=listed["indexSha256"].toString();
        QCOMPARE(s.capabilities()["pictureVersion"].toInt(),2);auto result=s.picture("demo:orbit",QString(32,'a'),revision);
        QVERIFY(result["ok"].toBool());QVERIFY(result["imageChecksumMatched"].toBool());QVERIFY(!result["runtimeRestoreAvailable"].toBool());
        QVERIFY(QRegularExpression("^image://nova-save-copies/[a-f0-9]{32}$").match(result["imageUrl"].toString()).hasMatch());
        QCOMPARE(s.pictureData()->bytes,pictureBytes());QVERIFY(!result.contains("dataUrl"));
        QVERIFY(!QJsonDocument::fromVariant(result).toJson().contains(root.toUtf8()));
        QCOMPARE(s.picture("demo:other",QString(32,'a'),revision)["error"].toString(),QString("copy_not_found"));
        QVERIFY(s.pictureData()->bytes.isEmpty() && s.pictureData()->token.isEmpty());
        QVERIFY(s.picture("demo:orbit",QString(32,'a'),revision)["ok"].toBool());s.clearPicture();
        QVERIFY(s.pictureData()->bytes.isEmpty() && s.pictureData()->token.isEmpty());
        QVERIFY(!s.picture("demo:orbit","../../save",revision)["ok"].toBool());
        auto row=entry("bytes");row["picture"]=QJsonObject{{"state","missing"}};writeIndex(root,{row},2);
        QCOMPARE(s.picture("demo:orbit",QString(32,'a'),revision)["error"].toString(),QString("history_changed"));
    }
    void changedOrMissingPictureNeverBecomesAValidPreview(){
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");addPicture(root);library::SaveCopies s(root);
        auto revision=s.openEdition("demo:orbit")["indexSha256"].toString();auto path=root+"/pictures/"+sha(pictureBytes())+".png";
        auto altered=pictureBytes();altered[altered.size()-1]='x';QVERIFY(put(path,altered));QVERIFY(!s.picture("demo:orbit",QString(32,'a'),revision)["ok"].toBool());
        QVERIFY(QFile::remove(path));QVERIFY(!s.picture("demo:orbit",QString(32,'a'),revision)["ok"].toBool());
        QVERIFY(s.openEdition("demo:orbit")["ok"].toBool()); // The copy remains browsable when its attached picture is lost.
    }
    void previewKeepsVerifiedBytesAndInvalidatesThePreviousToken(){
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");addPicture(root);library::SaveCopies s(root);
        const auto revision=s.openEdition("demo:orbit")["indexSha256"].toString();auto first=s.picture("demo:orbit",QString(32,'a'),revision);
        auto token=s.pictureData()->token;QVERIFY(!token.isEmpty());
        auto path=root+"/pictures/"+sha(pictureBytes())+".png";QVERIFY(put(path,QByteArray(pictureBytes().size(),'x')));
        QCOMPARE(s.pictureData()->bytes,pictureBytes()); // A later file write cannot replace an already-verified in-memory preview.
        QVERIFY(!s.picture("demo:orbit",QString(32,'a'),revision)["ok"].toBool());
        QVERIFY(s.pictureData()->bytes.isEmpty() && s.pictureData()->token.isEmpty());
        QVERIFY(put(path,pictureBytes()));auto next=s.picture("demo:orbit",QString(32,'a'),revision);
        QVERIFY(next["ok"].toBool());QVERIFY(s.pictureData()->token!=token);QVERIFY(first["imageUrl"]!=next["imageUrl"]);
    }
    void oversizedDecoderDimensionsAndNonPngBytesRefuse(){
        for(bool png:{false,true}){
            QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");auto bytes=png?pictureBytes():QByteArray(100,'x');
            if(png){bytes[16]=0x7f;bytes[17]=char(0xff);}addPicture(root,bytes);library::SaveCopies s(root);
            QVERIFY(!s.picture("demo:orbit",QString(32,'a'),s.openEdition("demo:orbit")["indexSha256"].toString())["ok"].toBool());
        }
    }
    void linkedAndSharedPicturesRefuseWithoutChangingTheCopy(){
#ifdef Q_OS_UNIX
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");addPicture(root);library::SaveCopies s(root);
        auto revision=s.openEdition("demo:orbit")["indexSha256"].toString();auto path=root+"/pictures/"+sha(pictureBytes())+".png";
        QVERIFY(QFile::setPermissions(path,QFile::ReadOwner|QFile::WriteOwner|QFile::ReadGroup));QVERIFY(!s.picture("demo:orbit",QString(32,'a'),revision)["ok"].toBool());
        QVERIFY(QFile::setPermissions(path,QFile::ReadOwner|QFile::WriteOwner));QVERIFY(QFile::rename(path,path+".kept"));QVERIFY(QFile::link(path+".kept",path));
        QVERIFY(!s.picture("demo:orbit",QString(32,'a'),revision)["ok"].toBool());
#else
        QSKIP("POSIX picture privacy checks");
#endif
    }
    void oldBundlesAndMissingOrInvalidPictureDescriptorsRemainExplicit(){
        QTemporaryDir t;auto root=QDir(t.path()).canonicalPath();setup(root,"bytes");library::SaveCopies s(root);
        auto revision=s.openEdition("demo:orbit")["indexSha256"].toString();QCOMPARE(s.picture("demo:orbit",QString(32,'a'),revision)["error"].toString(),QString("picture_unavailable"));
        for(const auto state:{QString("missing"),QString("unavailable")}){auto row=entry("bytes");row["picture"]=QJsonObject{{"state",state}};writeIndex(root,{row},2);QVERIFY(s.openEdition("demo:orbit")["ok"].toBool());}
        auto row=entry("bytes");row["picture"]=QJsonObject{{"state","available"},{"sha256","../../private"},{"bytes",72}};writeIndex(root,{row},2);
        QCOMPARE(s.openEdition("demo:orbit")["error"].toString(),QString("invalid_index"));
    }
    void actualExporterContract(){auto path=qEnvironmentVariable("NOVA_SAVE_FIXTURE");if(path.isEmpty())QSKIP("Pass a Python-exported synthetic bundle to check cross-language contract");library::SaveCopies s(path);auto rows=s.openEdition("demo:orbit");QVERIFY(rows["ok"].toBool());QVERIFY(!rows["copies"].toList().isEmpty());auto row=rows["copies"].toList().first().toMap();QSignalSpy spy(&s,&library::SaveCopies::reviewFinished);QVERIFY(s.review("demo:orbit",row["checkpointId"].toString())["ok"].toBool());QTRY_COMPARE(spy.count(),1);QVERIFY(spy.at(0).at(1).toMap()["ok"].toBool());}
};
QTEST_GUILESS_MAIN(Tests)
#include "tst_SaveCopies.moc"
