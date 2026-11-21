// SPDX-License-Identifier: GPL-3.0-or-later
#include "SaveCopies.h"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>
#include <QThread>
#include <QtEndian>
#include <QUuid>
#include <QMutexLocker>
#ifdef QT_QUICK_LIB
#include "SaveCopyPictureProvider.h"
#include <QQmlEngine>
#endif
#ifdef Q_OS_UNIX
#include <sys/stat.h>
#endif

namespace library {
namespace {
constexpr qint64 MaxIndex=256*1024, MaxArchive=256*1024*1024, MaxPicture=2*1024*1024;
QVariantMap failure(const QString& code) { return {{"ok",false},{"error",code}}; }
bool label(const QJsonValue& value,int limit=200) {
    const auto text=value.toString();
    return value.isString() && !text.trimmed().isEmpty() && text==text.trimmed()
        && text.size()<=limit && !text.contains(QRegularExpression("[<>\\x00-\\x1f\\x7f]"));
}
bool hex(const QString& value,int count) {
    return value.size()==count && QRegularExpression("^[0-9a-f]+$").match(value).hasMatch();
}
bool number(const QJsonValue& v,qint64 min,qint64 max) {
    return v.isDouble() && v.toDouble()>=min && v.toDouble()<=max && double(qint64(v.toDouble()))==v.toDouble();
}
bool keys(const QJsonObject& o,const QStringList& expected) {
    auto actual=o.keys(),wanted=expected;actual.sort();wanted.sort();return actual==wanted;
}
bool date(const QJsonValue& v) {
    const auto s=v.toString();auto d=QDateTime::fromString(s,Qt::ISODate);
    return v.isString() && d.isValid() && d.toUTC().toString("yyyy-MM-dd'T'HH:mm:ss'Z'")==s;
}
bool identity(const QJsonObject& o) {
    const auto runtime=o.value("runtime").toObject();
    if(!keys(o,{"editionId","recipeId","kind","runtime"}) || !label(o.value("editionId"))
       || !label(o.value("recipeId"),128) || !keys(runtime,{"name","version","core"}))return false;
    if(o.value("kind")!="native-save" && o.value("kind")!="emulator-state")return false;
    return label(runtime.value("name")) && label(runtime.value("version")) && label(runtime.value("core"));
}
bool pictureRecord(const QJsonObject& p) {
    if(p.value("state")=="missing" || p.value("state")=="unavailable")return keys(p,{"state"});
    return keys(p,{"state","sha256","bytes"}) && p.value("state")=="available"
        && hex(p.value("sha256").toString(),64) && number(p.value("bytes"),45,MaxPicture);
}
bool boundedPng(const QByteArray& data) {
    // The exporter fully validates PNG chunks/pixels. Recheck its immutable bytes
    // and decoder dimensions here; QML handles a decoder failure without a preview.
    if(data.size()<45 || data.size()>MaxPicture || data.left(8)!=QByteArray::fromHex("89504e470d0a1a0a")
       || data.mid(8,8)!=QByteArray::fromHex("0000000d49484452"))return false;
    const auto* p=reinterpret_cast<const uchar*>(data.constData());
    const auto width=qFromBigEndian<quint32>(p+16),height=qFromBigEndian<quint32>(p+20);
    return width>0 && width<=2048 && height>0 && height<=2048 && p[24]==8 && (p[25]==2 || p[25]==6)
        && p[26]==0 && p[27]==0 && p[28]==0;
}
bool privatePath(const QString& path,bool file,QString* check=nullptr) {
    auto refuse=[check](const char* reason){if(check)*check=QString::fromLatin1(reason);return false;};
    if(check)check->clear();
    const QFileInfo info(path);
    if(!info.exists())return refuse("not_found");
    if(info.isSymLink())return refuse("symbolic_link");
    if(file?!info.isFile():!info.isDir())return refuse("wrong_type");
    if(info.canonicalFilePath()!=QDir::cleanPath(info.absoluteFilePath()))return refuse("canonical_mismatch");
#ifdef Q_OS_UNIX
    struct stat s;
    if(::stat(QFile::encodeName(path).constData(),&s)!=0)return refuse("stat_unavailable");
    if((s.st_mode&0077)!=0)return refuse("shared_permissions");
#endif
    return true;
}
QString rootBinding(const QString& root) {
    return QString::fromLatin1(QCryptographicHash::hash(root.toUtf8(),QCryptographicHash::Sha256).toHex());
}
struct Index { QString error,stage=QStringLiteral("copy-index"),check; QByteArray hash; QJsonArray entries; };
QVariantMap indexFailure(const Index& loaded,const QString& root) {
    auto result=failure(loaded.error);
    result.insert("storageStage",loaded.stage);
    if(!loaded.check.isEmpty())result.insert("storageCheck",loaded.check);
    // A path binding lets private diagnostics compare contexts without logging paths.
    result.insert("storageRootSha256",rootBinding(root));
    return result;
}
Index index(const QString& root) {
    Index out;
    if(QFileInfo(root).isSymLink()){out.error="storage_unavailable";out.stage="copy-directory";out.check="symbolic_link";return out;}
    if(!QFileInfo::exists(root))return out;
    if(!privatePath(root,false,&out.check)){out.error="storage_unavailable";out.stage="copy-directory";return out;}
    const auto path=root+"/catalogue.json";
    if(!QFileInfo::exists(path)){out.error="bundle_incomplete";return out;}
    if(!privatePath(path,true,&out.check)){out.error="storage_unavailable";return out;}
    QFile file(path);
    if(!file.open(QIODevice::ReadOnly) || file.size()>MaxIndex){out.error="index_unavailable";return out;}
    const auto bytes=file.read(MaxIndex+1);
    if(bytes.size()!=file.size()){out.error="index_changed";return out;}
    QJsonParseError error;const auto doc=QJsonDocument::fromJson(bytes,&error);const auto o=doc.object();
    const auto version=o.value("schemaVersion").toInt();
    // Only the exporter's canonical encoding is accepted. Qt's JSON parser
    // collapses duplicate keys; a byte roundtrip refuses that ambiguity too.
    if(error.error!=QJsonParseError::NoError || !doc.isObject() || doc.toJson(QJsonDocument::Compact)!=bytes
       || !keys(o,{"schemaVersion","source","entries"}) || (version!=1 && version!=2) || o.value("schemaVersion")!=version
       || o.value("source")!=QStringLiteral("verified-passport-export-v%1").arg(version) || !o.value("entries").isArray()
       || o.value("entries").toArray().size()>128){out.error="invalid_index";return out;}
    QSet<QString> ids;
    for(const auto v:o.value("entries").toArray()) {
        const auto e=v.toObject();const auto id=e.value("checkpointId").toString();
        const auto name=e.value("name").toString();
        QStringList fields={"checkpointId","sha256","bytes","identity","capturedAt","addedAt","name","pinned","files","payloadBytes"};
        if(version==2)fields.push_back("picture");
        if(!v.isObject() || !keys(e,fields) || (version==2 && (!e.value("picture").isObject() || !pictureRecord(e.value("picture").toObject())))
           || !hex(id,32) || ids.contains(id) || !hex(e.value("sha256").toString(),64)
           || !number(e.value("bytes"),1,MaxArchive) || !identity(e.value("identity").toObject())
           || !date(e.value("capturedAt")) || !date(e.value("addedAt")) || !e.value("pinned").isBool()
           || !e.value("name").isString() || name.size()>120 || name!=name.trimmed() || (e.value("pinned").toBool() && name.isEmpty())
           || name.contains(QRegularExpression("[<>\\x00-\\x1f\\x7f]"))
           || !number(e.value("files"),1,128) || !number(e.value("payloadBytes"),0,1024LL*1024*1024)) {
            out.error="invalid_index";return out;
        }
        ids.insert(id);out.entries.push_back(e);
    }
    out.hash=QCryptographicHash::hash(bytes,QCryptographicHash::Sha256);return out;
}
QString archivePath(const QString& root,const QJsonObject& entry) {
    return root+"/archives/"+entry.value("sha256").toString()+".nvs";
}
QString copyState(const QString& root,const QJsonObject& entry) {
    const auto path=archivePath(root,entry);
    if(!QFileInfo::exists(path))return "missing";
    if(!privatePath(root+"/archives",false) || !privatePath(path,true))return "unavailable";
    return QFileInfo(path).size()==qint64(entry.value("bytes").toDouble())?"not-rechecked":"changed";
}
class Review final:public QThread {
public:
    QString root,token;QJsonObject entry;QByteArray indexHash;QVariantMap result;
    void run() override {
        if(copyState(root,entry)!="not-rechecked"){result=failure("copy_unavailable_or_changed");return;}
        QFile file(archivePath(root,entry));
        if(!file.open(QIODevice::ReadOnly)){result=failure("copy_unavailable_or_changed");return;}
        QCryptographicHash hash(QCryptographicHash::Sha256);qint64 total=0;
        while(!file.atEnd()) {
            if(isInterruptionRequested()){result=failure("cancelled");return;}
            const auto bytes=file.read(256*1024);
            if(bytes.isEmpty() && file.error()!=QFile::NoError){result=failure("copy_unavailable_or_changed");return;}
            total+=bytes.size();if(total>MaxArchive){result=failure("copy_unavailable_or_changed");return;}hash.addData(bytes);
        }
        if(isInterruptionRequested()){result=failure("cancelled");return;}
        const auto current=index(root);
        if(!current.error.isEmpty() || current.hash!=indexHash){result=failure("history_changed");return;}
        if(total!=qint64(entry.value("bytes").toDouble()) || hash.result().toHex()!=entry.value("sha256").toString().toLatin1()
           || copyState(root,entry)!="not-rechecked"){result=failure("checksum_mismatch");return;}
        result={{"ok",true},{"archiveChecksumMatched",true},{"runtimeRestoreAvailable",false}};
    }
};
}
SaveCopies::SaveCopies(const QString& root,QObject* parent):QObject(parent),m_root(QDir::cleanPath(QFileInfo(root).absoluteFilePath())),m_pictureData(new SaveCopyPictureData) {
#ifdef QT_QUICK_LIB
    if(auto* engine=qobject_cast<QQmlEngine*>(parent))engine->addImageProvider(QStringLiteral("nova-save-copies"),new SaveCopyPictureProvider(m_pictureData));
#endif
}
SaveCopies::~SaveCopies() {clearPicture();if(m_worker){m_worker->requestInterruption();m_worker->wait();}}
void SaveCopies::clearPicture() const {QMutexLocker lock(&m_pictureData->mutex);m_pictureData->bytes.clear();m_pictureData->token.clear();}
QVariantMap SaveCopies::capabilities() const {return {{"schemaVersion",1},{"readOnly",true},{"capture",false},{"runtimeRestoreAvailable",false},
    {"storageDiagnosticsVersion",1},{"storageRootSha256",rootBinding(m_root)},{"pictureVersion",2},{"reviewSnapshotVersion",1}};}
QVariantMap SaveCopies::observedResult(const QString& edition,const QString& checkpoint,const QString& index,const QVariantMap& result) const {
    emit operationObserved(edition,checkpoint,index,result);
    return result;
}
QVariantMap SaveCopies::openEdition(const QString& edition) const {
    if(!label(QJsonValue(edition)))return observedResult(edition,{}, {},failure("explicit_edition_required"));
    const auto loaded=index(m_root);if(!loaded.error.isEmpty())return observedResult(edition,{}, {},indexFailure(loaded,m_root));
    QVariantList copies;
    for(const auto v:loaded.entries){const auto e=v.toObject();if(e.value("identity").toObject().value("editionId")!=edition)continue;
        auto row=e.toVariantMap();row["copyState"]=copyState(m_root,e);row["runtimeRestoreAvailable"]=false;copies.push_back(row);}
    return observedResult(edition,{}, {},{{"ok",true},{"copies",copies},{"indexSha256",QString::fromLatin1(loaded.hash.toHex())},{"runtimeRestoreAvailable",false}});
}
QVariantMap SaveCopies::picture(const QString& edition,const QString& id,const QString& expectedIndex) const {
    clearPicture();
    if(!label(QJsonValue(edition)) || !hex(id,32) || !hex(expectedIndex,64))return failure("explicit_edition_required");
    const auto loaded=index(m_root);if(!loaded.error.isEmpty())return indexFailure(loaded,m_root);
    if(loaded.hash.toHex()!=expectedIndex.toLatin1())return failure("history_changed");
    QJsonObject selected;
    for(const auto v:loaded.entries){const auto e=v.toObject();if(e.value("checkpointId")==id && e.value("identity").toObject().value("editionId")==edition){selected=e;break;}}
    if(selected.isEmpty())return failure("copy_not_found");
    const auto meta=selected.value("picture").toObject();
    if(meta.value("state")!="available")return failure("picture_unavailable");
    const auto directory=m_root+"/pictures",path=directory+"/"+meta.value("sha256").toString()+".png";
    if(!privatePath(directory,false) || !privatePath(path,true))return failure("picture_unavailable");
    QFile file(path);if(!file.open(QIODevice::ReadOnly) || file.size()!=qint64(meta.value("bytes").toDouble()) || file.size()>MaxPicture)return failure("picture_unavailable");
    const auto data=file.read(MaxPicture+1);
    if(data.size()!=file.size() || QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex()!=meta.value("sha256").toString().toLatin1()
       || !boundedPng(data) || index(m_root).hash!=loaded.hash)return failure("picture_unavailable_or_changed");
    const auto token=QUuid::createUuid().toString(QUuid::Id128);
    {QMutexLocker lock(&m_pictureData->mutex);m_pictureData->token=token;m_pictureData->bytes=data;}
    // Decoder errors may echo their URL. Only an opaque token reaches QML/logs.
    return {{"ok",true},{"imageUrl",QStringLiteral("image://nova-save-copies/")+token},
        {"imageChecksumMatched",true},{"runtimeRestoreAvailable",false}};
}
QVariantMap SaveCopies::review(const QString& edition,const QString& id) {
    return startReview(edition,id,QString());
}
QVariantMap SaveCopies::reviewSnapshot(const QString& edition,const QString& id,const QString& expectedIndex) {
    if(!hex(expectedIndex,64))return observedResult(edition,id,expectedIndex,failure("invalid_snapshot"));
    return startReview(edition,id,expectedIndex);
}
QVariantMap SaveCopies::startReview(const QString& edition,const QString& id,const QString& expectedIndex) {
    if(m_worker)return observedResult(edition,id,expectedIndex,failure("review_busy"));
    if(!label(QJsonValue(edition)) || !hex(id,32))return observedResult(edition,id,expectedIndex,failure("explicit_edition_required"));
    const auto loaded=index(m_root);if(!loaded.error.isEmpty())return observedResult(edition,id,expectedIndex,indexFailure(loaded,m_root));
    // Match the displayed snapshot before selecting any archive; do not reload it
    // through the legacy entry point after this comparison.
    if(!expectedIndex.isEmpty() && loaded.hash.toHex()!=expectedIndex.toLatin1())return observedResult(edition,id,expectedIndex,failure("history_changed"));
    QJsonObject selected;
    for(const auto v:loaded.entries){const auto e=v.toObject();if(e.value("checkpointId")==id && e.value("identity").toObject().value("editionId")==edition){selected=e;break;}}
    if(selected.isEmpty())return observedResult(edition,id,expectedIndex,failure("copy_not_found"));
    auto* worker=new Review;worker->setParent(this);worker->root=m_root;worker->entry=selected;worker->indexHash=loaded.hash;
    worker->token=QString::number(++m_sequence);m_worker=worker;
    connect(worker,&QThread::finished,this,[this,worker,edition,id,expectedIndex]{m_worker=nullptr;observedResult(edition,id,expectedIndex,worker->result);emit reviewFinished(worker->token,worker->result);worker->deleteLater();});
    worker->start();return observedResult(edition,id,expectedIndex,{{"ok",true},{"token",worker->token}});
}
void SaveCopies::cancelReview(){if(m_worker)m_worker->requestInterruption();}
}
