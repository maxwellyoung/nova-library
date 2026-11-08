// SPDX-License-Identifier: GPL-3.0-or-later
#include "StoppingNotes.h"
#include <QBuffer>
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QDirIterator>
#include <QFile>
#include <QFileInfo>
#include <QImageReader>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLockFile>
#include <QRegularExpression>
#include <QSaveFile>
#include <QSet>
#include <QStandardPaths>
#include <QUrl>
#include <QUuid>
#include <cmath>
#ifdef Q_OS_ANDROID
#include <QAndroidJniObject>
#endif

namespace library {
namespace {
constexpr qint64 MaxMetadata = 512 * 1024, MaxImage = 16 * 1024 * 1024, MaxOriginalBytes = 128 * 1024 * 1024;
constexpr int MaxNotes = 64, MaxOriginals = 32, MaxMarks = 32;
const QFileDevice::Permissions PrivateFile = QFileDevice::ReadOwner | QFileDevice::WriteOwner;
const QFileDevice::Permissions PrivateDirectory = PrivateFile | QFileDevice::ExeOwner;
QString hash(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex()); }
QString stamp() { return QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs); }
QVariantMap failure(const QString& reason) { return {{"ok",false},{"error",reason}}; }
bool text(const QVariant& value, int bound, bool empty = true) {
    if (value.userType() != QMetaType::QString) return false;
    const auto s = value.toString();
    return (empty || !s.isEmpty()) && s.size() <= bound && !s.contains(QChar(0));
}
bool edition(const QString& id) {
    if (id.isEmpty() || id.size() > 200 || id.startsWith("untagged:")) return false;
    for (const auto c : id) if (c.unicode() < 32) return false;
    return true;
}
bool integer(const QVariant& v, qint64 min, qint64 max) {
    if (v.userType() != QMetaType::Int && v.userType() != QMetaType::LongLong && v.userType() != QMetaType::UInt && v.userType() != QMetaType::Double) return false;
    bool ok = false; const double n = v.toDouble(&ok);
    return ok && std::isfinite(n) && n >= min && n <= max && std::floor(n) == n;
}
bool keys(const QVariantMap& m, const QStringList& allowed, const QStringList& required = {}) {
    for (auto i = m.cbegin(); i != m.cend(); ++i) if (!allowed.contains(i.key())) return false;
    for (const auto& k : required) if (!m.contains(k)) return false;
    return true;
}
bool digest(const QString& s) { return QRegularExpression("^[0-9a-f]{64}$").match(s).hasMatch(); }
bool noteId(const QString& s) { return QRegularExpression("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$").match(s).hasMatch(); }
bool date(const QVariant& v) { return text(v,40,false) && QDateTime::fromString(v.toString(),Qt::ISODateWithMs).isValid() && v.toString().endsWith('Z'); }
bool map(const QVariant& v) { return v.userType() == QMetaType::QVariantMap; }
bool list(const QVariant& v) { return v.userType() == QMetaType::QVariantList; }
QString atomicWrite(const QString& path, const QByteArray& bytes) {
    if (QFileInfo(path).isSymLink()) return "unsafe_storage_path";
    QSaveFile file(path); file.setDirectWriteFallback(false);
    if (!file.open(QIODevice::WriteOnly) || !file.setPermissions(PrivateFile)
            || file.write(bytes) != bytes.size() || !file.commit()) return "write_failed";
    return {};
}
bool plainDirectory(const QString& path) { const QFileInfo i(path); return i.isDir() && !i.isSymLink(); }
bool privateDirectory(const QString& path) {
    const QFileInfo info(path);
    if(info.exists())return plainDirectory(path) && !(info.permissions() & (QFileDevice::ReadGroup|QFileDevice::WriteGroup|QFileDevice::ExeGroup|QFileDevice::ReadOther|QFileDevice::WriteOther|QFileDevice::ExeOther));
    return QDir().mkpath(path) && QFile::setPermissions(path,PrivateDirectory);
}
bool originalValid(const QString& id, const QVariantMap& m) {
    return digest(id) && keys(m,{"sha256","bytes","mime","width","height","importedAt"}, {"sha256","bytes","mime","width","height","importedAt"})
        && m.value("sha256").toString() == id && integer(m.value("bytes"),1,MaxImage)
        && QStringList({"image/png","image/jpeg","image/webp"}).contains(m.value("mime").toString())
        && integer(m.value("width"),1,8192) && integer(m.value("height"),1,8192)
        && m.value("width").toLongLong()*m.value("height").toLongLong() <= 16*1024*1024 && date(m.value("importedAt"));
}
bool annotations(const QVariant& input) {
    if (!list(input) || input.toList().size() > MaxMarks) return false;
    for (const auto& value : input.toList()) {
        if (!map(value)) return false;
        const auto mark = value.toMap();
        if (!keys(mark,{"kind","x1","y1","x2","y2","text","colour"},{"kind","x1","y1","x2","y2","text","colour"})
                || !QStringList({"ellipse","rectangle","arrow","text"}).contains(mark.value("kind").toString())
                || !text(mark.value("text"),160) || !QStringList({"light","dark","amber"}).contains(mark.value("colour").toString())) return false;
        for (const auto& key : {"x1","y1","x2","y2"}) {
            const auto v = mark.value(key);
            if (v.userType() == QMetaType::Bool || (v.userType() != QMetaType::Double && v.userType() != QMetaType::Int)) return false;
            const double n = v.toDouble(); if (!std::isfinite(n) || n < 0 || n > 1) return false;
        }
        const auto kind = mark.value("kind").toString();
        if ((kind == "ellipse" || kind == "rectangle") && (mark.value("x2").toDouble() <= mark.value("x1").toDouble() || mark.value("y2").toDouble() <= mark.value("y1").toDouble())) return false;
        if (kind == "text" && mark.value("text").toString().isEmpty()) return false;
    }
    return true;
}
bool legacy(const QVariantMap& value) {
    return keys(value,{"text","revision","pending","conflict","source"},{"text","revision","pending","conflict","source"})
        && text(value.value("text"),4000) && (value.value("revision").isNull() || integer(value.value("revision"),0,2147483646))
        && value.value("pending").userType() == QMetaType::Bool && value.value("conflict").userType() == QMetaType::Bool
        && QStringList({"you","catalogue"}).contains(value.value("source").toString());
}
bool valid(const QVariantMap& doc, const QString& id) {
    if (!keys(doc,{"schemaVersion","editionId","revision","stoppingNoteId","notes","originals"},{"schemaVersion","editionId","revision","stoppingNoteId","notes","originals"})
            || !integer(doc.value("schemaVersion"),1,1) || doc.value("editionId").toString() != id
            || !integer(doc.value("revision"),0,2147483646) || !text(doc.value("stoppingNoteId"),36)
            || !list(doc.value("notes")) || doc.value("notes").toList().size() > MaxNotes || !map(doc.value("originals"))) return false;
    const auto originals = doc.value("originals").toMap();
    if (originals.size() > MaxOriginals) return false;
    qint64 total = 0;
    for (auto i = originals.cbegin(); i != originals.cend(); ++i) {
        if (!map(i.value()) || !originalValid(i.key(),i.value().toMap())) return false;
        total += i.value().toMap().value("bytes").toLongLong();
    }
    if (total > MaxOriginalBytes) return false;
    QSet<QString> ids; bool stoppingFound = doc.value("stoppingNoteId").toString().isEmpty();
    for (const auto& item : doc.value("notes").toList()) {
        if (!map(item)) return false; const auto n = item.toMap(); const auto nid = n.value("id").toString();
        if (!keys(n,{"id","text","imageId","annotations","createdAt","updatedAt","cleared","legacyReference"},{"id","text","imageId","annotations","createdAt","updatedAt","cleared"})
                || !noteId(nid) || ids.contains(nid) || !text(n.value("text"),4000) || !text(n.value("imageId"),64)
                || !date(n.value("createdAt")) || !date(n.value("updatedAt")) || n.value("cleared").userType() != QMetaType::Bool
                || !annotations(n.value("annotations"))) return false;
        const auto image = n.value("imageId").toString();
        if ((!image.isEmpty() && !originals.contains(image)) || (image.isEmpty() && !n.value("annotations").toList().isEmpty())) return false;
        if (n.contains("legacyReference") && (!map(n.value("legacyReference")) || !legacy(n.value("legacyReference").toMap()))) return false;
        if (nid == doc.value("stoppingNoteId").toString()) { if (n.value("cleared").toBool()) return false; stoppingFound = true; }
        ids.insert(nid);
    }
    return stoppingFound;
}
QVariantMap fresh(const QString& id) { return {{"schemaVersion",1},{"editionId",id},{"revision",0},{"stoppingNoteId",""},{"notes",QVariantList()},{"originals",QVariantMap()}}; }
QString imageState(const QString& path, const QVariantMap& descriptor) {
    if (QFileInfo(QFileInfo(path).absolutePath()).isSymLink()) return "corrupt";
    if (!QFileInfo::exists(path)) return "missing";
    if (!QFileInfo(path).isFile() || QFileInfo(path).isSymLink()) return "corrupt";
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly) || f.size() != descriptor.value("bytes").toLongLong()) return "corrupt";
    return hash(f.read(MaxImage+1)) == descriptor.value("sha256").toString() ? "ready" : "corrupt";
}
}

StoppingNotes::StoppingNotes(const QString& privateRoot, QObject* parent, const QString& screenshotsRoot)
    : QObject(parent), m_root(QDir(privateRoot).absolutePath()),
      m_screenshots(screenshotsRoot) {
    if(m_screenshots.isEmpty()) {
#ifdef Q_OS_ANDROID
        // Qt 5 maps PicturesLocation to app-specific external storage on Android.
        // Ask Android for the public Pictures directory; existing permissions
        // still govern access, and only Screenshots is listed on explicit request.
        const auto kind=QAndroidJniObject::getStaticObjectField(
            "android/os/Environment", "DIRECTORY_PICTURES", "Ljava/lang/String;");
        const auto folder=kind.isValid() ? QAndroidJniObject::callStaticObjectMethod(
            "android/os/Environment", "getExternalStoragePublicDirectory",
            "(Ljava/lang/String;)Ljava/io/File;", kind.object<jstring>()) : QAndroidJniObject();
        const auto pictures=folder.isValid() ? folder.callObjectMethod(
            "getAbsolutePath", "()Ljava/lang/String;").toString() : QString();
#else
        const auto pictures=QStandardPaths::writableLocation(QStandardPaths::PicturesLocation);
#endif
        if(!pictures.isEmpty())m_screenshots=pictures+"/Screenshots";
    }
    if (privateRoot.isEmpty() || !QDir::isAbsolutePath(privateRoot) || QFileInfo(m_root).isSymLink()) { m_error="unsafe_storage_path"; return; }
    const bool existed = QFileInfo::exists(m_root);
    if (existed && !plainDirectory(m_root)) { m_error="unsafe_storage_path"; return; }
    const QString marker=m_root+"/.nova-stopping-notes";
    if (existed && !QFileInfo::exists(marker) && !QDir(m_root).entryList(QDir::AllEntries|QDir::NoDotAndDotDot|QDir::Hidden).isEmpty()) {m_error="unowned_storage_directory";return;}
    if (!privateDirectory(m_root)) {m_error="storage_not_private_or_unwritable";return;}
    if (!QFileInfo::exists(marker)) m_error=atomicWrite(marker,"nova-stopping-notes-v1\n");
    else { QFile f(marker); if (f.symLinkTarget().size() || !f.open(QIODevice::ReadOnly) || f.readAll() != "nova-stopping-notes-v1\n") m_error="unowned_storage_directory"; }
}
QString StoppingNotes::directory(const QString& id) const { return m_root+"/"+hash(id.toUtf8()); }
QVariantMap StoppingNotes::capabilities() const {
    return {{"ok",m_error.isEmpty()},{"error",m_error},{"schemaVersion",1},{"localOnly",true},{"originalImport",true},{"maxText",4000},{"maxNotes",MaxNotes},{"maxAnnotations",MaxMarks},{"maxImageBytes",MaxImage},{"maxEditionImageBytes",MaxOriginalBytes}};
}
QVariantMap StoppingNotes::imageChoices() const {
    if (!m_error.isEmpty()) return failure(m_error);
    const QFileInfo folder(m_screenshots);
    if (!QDir::isAbsolutePath(m_screenshots) || !folder.isDir() || folder.isSymLink() || !folder.isReadable())
        return failure("screenshot_folder_unavailable");
    // Only this explicit public screenshot folder. Never recurse into photos or
    // import a file until the owner chooses it in the notebook.
    const auto files=QDir(m_screenshots).entryInfoList(QDir::Files|QDir::NoDotAndDotDot,QDir::Time|QDir::IgnoreCase);
    QVariantList choices; bool more=false;
    for (const auto& f:files) {
        if (f.isSymLink() || !f.isReadable() || f.size()<1 || f.size()>MaxImage
                || !QStringList({"png","jpg","jpeg","webp"}).contains(f.suffix().toLower())) continue;
        if (choices.size()>=64) {more=true;break;}
        choices.append(QVariantMap{{"label",f.fileName()},{"fileUrl",QUrl::fromLocalFile(f.absoluteFilePath()).toString()},
            {"updatedAt",f.lastModified().toUTC().toString(Qt::ISODateWithMs)}});
    }
    return {{"ok",true},{"choices",choices},{"more",more}};
}
QString StoppingNotes::load(const QString& id, QVariantMap* doc) const {
    if (!m_error.isEmpty()) return m_error; if (!edition(id)) return "explicit_edition_id_required";
    const auto dir=directory(id), path=dir+"/notebook.json";
    if (QFileInfo::exists(dir) && !plainDirectory(dir)) return "unsafe_storage_path";
    if (!QFileInfo::exists(path)) { *doc=fresh(id); return {}; }
    if (QFileInfo(path).isSymLink()) return "unsafe_storage_path";
    QFile file(path); if (!file.open(QIODevice::ReadOnly)) return "read_failed";
    if (file.size() > MaxMetadata) return "corrupt_metadata";
    QJsonParseError error; const auto json=QJsonDocument::fromJson(file.readAll(),&error);
    if (error.error != QJsonParseError::NoError || !json.isObject()) return "corrupt_metadata";
    *doc=json.object().toVariantMap(); return valid(*doc,id) ? QString() : "corrupt_metadata";
}
QString StoppingNotes::save(const QString& id, QVariantMap* doc) const {
    if (doc->value("revision").toLongLong() >= 2147483646) return "revision_limit";
    (*doc)["revision"]=doc->value("revision").toInt()+1;
    if (!valid(*doc,id)) return "invalid_note";
    const auto bytes=QJsonDocument::fromVariant(*doc).toJson(QJsonDocument::Compact);
    if (bytes.size() > MaxMetadata) return "metadata_limit";
    const auto dir=directory(id);
    if (!privateDirectory(dir)) return "write_failed";
    return atomicWrite(dir+"/notebook.json",bytes);
}
QVariantMap StoppingNotes::view(const QVariantMap& document) const {
    auto out=document; QVariantList notes;
    const auto dir=directory(document.value("editionId").toString()); const auto originals=document.value("originals").toMap();
    for (const auto& item : document.value("notes").toList()) {
        auto note=item.toMap(); const auto id=note.value("imageId").toString();
        note["imageStatus"]=id.isEmpty() ? "none" : imageState(dir+"/originals/"+id,originals.value(id).toMap());
        note["imageUrl"]=note.value("imageStatus")=="ready" ? QUrl::fromLocalFile(dir+"/originals/"+id).toString() : "";
        notes.append(note);
    }
    out["notes"]=notes; return {{"ok",true},{"notebook",out}};
}
QVariantMap StoppingNotes::openEdition(const QString& id, const QVariantMap& checkpoint) const {
    QLockFile lock(m_root+"/.lock"); if (!lock.tryLock(1000)) return failure("storage_busy");
    QVariantMap doc; const auto error=load(id,&doc); if (!error.isEmpty()) return failure(error);
    auto result=view(doc);
    if (!checkpoint.isEmpty()) { if (!legacy(checkpoint)) return failure("invalid_legacy_checkpoint"); result["legacyCheckpoint"]=checkpoint; }
    return result;
}
QVariantMap StoppingNotes::importOriginal(const QString& id, const QString& localUrl, const QVariant& expected) {
    QLockFile lock(m_root+"/.lock"); if (!lock.tryLock(1000)) return failure("storage_busy");
    QVariantMap doc; auto error=load(id,&doc); if (!error.isEmpty()) return failure(error);
    if (!integer(expected,0,2147483646)) return failure("invalid_revision");
    if (expected.toInt()!=doc.value("revision").toInt()) return {{"ok",false},{"error","revision_conflict"},{"current",view(doc).value("notebook")}};
    const QUrl url(localUrl); const auto path=url.toLocalFile(); QFileInfo info(path);
    if (!url.isLocalFile() || !url.host().isEmpty() || !QDir::isAbsolutePath(path) || !info.isFile() || info.isSymLink()) return failure("explicit_local_image_required");
    QFile source(path); if (!source.open(QIODevice::ReadOnly) || source.size()<1 || source.size()>MaxImage) return failure("image_unreadable_or_too_large");
    const auto bytes=source.read(MaxImage+1); if (bytes.size()!=source.size() || bytes.size()>MaxImage) return failure("image_changed_during_import");
    QBuffer buffer;buffer.setData(bytes);buffer.open(QIODevice::ReadOnly);QImageReader reader(&buffer);
    const auto size=reader.size(); const auto format=reader.format().toLower();
    if (!QList<QByteArray>({"png","jpeg","jpg","webp"}).contains(format) || size.width()<1 || size.height()<1 || size.width()>8192 || size.height()>8192 || qint64(size.width())*size.height()>16*1024*1024 || reader.read().isNull()) return failure("unsupported_or_corrupt_image");
    const auto image=hash(bytes); auto originals=doc.value("originals").toMap();
    if (!originals.contains(image)) {
        qint64 total=bytes.size(); for (const auto& v : originals) total+=v.toMap().value("bytes").toLongLong();
        if (originals.size()>=MaxOriginals || total>MaxOriginalBytes) return failure("original_storage_limit");
        const QString mime=format=="png" ? "image/png" : format=="webp" ? "image/webp" : "image/jpeg";
        originals[image]=QVariantMap{{"sha256",image},{"bytes",bytes.size()},{"mime",mime},{"width",size.width()},{"height",size.height()},{"importedAt",stamp()}};
    }
    const auto folder=directory(id)+"/originals", target=folder+"/"+image;
    if (!privateDirectory(directory(id)) || !privateDirectory(folder)) return failure("write_failed");
    // Failed metadata commits may leave an unassociated original. Count retained
    // bytes too, so repeated failures cannot bypass the edition's storage bounds.
    qint64 retainedBytes=QFileInfo::exists(target) ? 0 : bytes.size();
    int retainedCount=QFileInfo::exists(target) ? 0 : 1;
    QDirIterator retained(folder,QDir::AllEntries|QDir::NoDotAndDotDot|QDir::Hidden);
    while(retained.hasNext()) {
        retained.next();const auto info=retained.fileInfo();
        if(!info.isFile()||info.isSymLink()||!digest(info.fileName()))return failure("unexpected_original_storage_entry");
        retainedBytes+=info.size();
        if(++retainedCount>MaxOriginals||retainedBytes>MaxOriginalBytes)return failure("original_storage_limit");
    }
    if (QFileInfo::exists(target)) { if (imageState(target,originals.value(image).toMap())!="ready") return failure("original_copy_conflict"); }
    else { error=atomicWrite(target,bytes); if (!error.isEmpty()) return failure(error); }
    // Never delete an original if publishing its association fails. It can be reimported.
    doc["originals"]=originals; error=save(id,&doc); if (!error.isEmpty()) return failure(error);
    auto result=view(doc); result["imageId"]=image; result["imageUrl"]=QUrl::fromLocalFile(target).toString(); return result;
}
QVariantMap StoppingNotes::change(const QString& id, const QString& nid, const QVariantMap& draft, const QVariant& expected, const QString& op) {
    QLockFile lock(m_root+"/.lock"); if (!lock.tryLock(1000)) return failure("storage_busy");
    QVariantMap doc; auto error=load(id,&doc); if (!error.isEmpty()) return failure(error);
    if (!integer(expected,0,2147483646)) return failure("invalid_revision");
    if (expected.toInt()!=doc.value("revision").toInt()) return {{"ok",false},{"error","revision_conflict"},{"current",view(doc).value("notebook")}};
    auto notes=doc.value("notes").toList(); int index=-1;
    for (int i=0;i<notes.size();++i) if (notes[i].toMap().value("id").toString()==nid) index=i;
    QVariantMap note;
    if (op=="create" || op=="adopt") {
        if (notes.size()>=MaxNotes) return failure("note_limit");
        note={{"id",QUuid::createUuid().toString(QUuid::WithoutBraces)},{"text",""},{"imageId",""},{"annotations",QVariantList()},{"createdAt",stamp()},{"updatedAt",stamp()},{"cleared",false}};
        if (op=="adopt") {if (!legacy(draft)) return failure("invalid_legacy_checkpoint");note["legacyReference"]=draft;note["text"]=draft.value("text");}
    } else {
        if (index<0) return failure("note_not_found"); note=notes[index].toMap();
    }
    if (op=="edit" || op=="create") {
        if (!keys(draft,{"text","imageId","annotations"}) || (op=="create" && !draft.contains("text"))) return failure("invalid_note");
        for (auto i=draft.cbegin();i!=draft.cend();++i) note[i.key()]=i.value();
        if (note.value("cleared").toBool()) return failure("note_is_cleared");
    }
    if (op=="clear") {note["cleared"]=true;if(doc.value("stoppingNoteId")==nid)doc["stoppingNoteId"]="";}
    if (op=="restore") note["cleared"]=false;
    if (op=="stopping") {if (note.value("cleared").toBool())return failure("note_is_cleared");doc["stoppingNoteId"]=nid;}
    note["updatedAt"]=stamp();
    if (index<0) {notes.append(note);doc["stoppingNoteId"]=note.value("id");} else notes[index]=note;
    doc["notes"]=notes; error=save(id,&doc); if (!error.isEmpty()) return failure(error);
    auto result=view(doc);result["noteId"]=note.value("id");return result;
}
QVariantMap StoppingNotes::createNote(const QString& id,const QVariantMap& draft,const QVariant& rev){return change(id,"",draft,rev,"create");}
QVariantMap StoppingNotes::editNote(const QString& id,const QString& nid,const QVariantMap& draft,const QVariant& rev){return change(id,nid,draft,rev,"edit");}
QVariantMap StoppingNotes::clearNote(const QString& id,const QString& nid,const QVariant& rev){return change(id,nid,{},rev,"clear");}
QVariantMap StoppingNotes::restoreNote(const QString& id,const QString& nid,const QVariant& rev){return change(id,nid,{},rev,"restore");}
QVariantMap StoppingNotes::setStoppingNote(const QString& id,const QString& nid,const QVariant& rev){return change(id,nid,{},rev,"stopping");}
QVariantMap StoppingNotes::adoptLegacy(const QString& id,const QVariantMap& checkpoint,const QVariant& rev){return change(id,"",checkpoint,rev,"adopt");}
QVariantMap StoppingNotes::search(const QString& id,const QString& query,bool includeCleared) const {
    if (query.size()>4000 || query.contains(QChar(0)))return failure("invalid_query");
    auto result=openEdition(id,{});if(!result.value("ok").toBool())return result;QVariantList matches;
    for(const auto& v:result.value("notebook").toMap().value("notes").toList()) {
        const auto note=v.toMap();if(note.value("cleared").toBool()&&!includeCleared)continue;
        auto content=note.value("text").toString();for(const auto& mark:note.value("annotations").toList())content+="\n"+mark.toMap().value("text").toString();
        if(content.contains(query,Qt::CaseInsensitive))matches.append(note);
    }
    return {{"ok",true},{"editionId",id},{"matches",matches}};
}
QVariantMap StoppingNotes::exportEdition(const QString& id,const QString& localDirectory) const {
    QLockFile lock(m_root+"/.lock");if(!lock.tryLock(1000))return failure("storage_busy");QVariantMap doc;auto error=load(id,&doc);if(!error.isEmpty())return failure(error);
    const QUrl url(localDirectory);const auto target=QDir::cleanPath(url.toLocalFile());QFileInfo destination(target);
    const auto parent=destination.absolutePath();
    if(!url.isLocalFile()||!url.host().isEmpty()||!QDir::isAbsolutePath(target)||destination.exists()||destination.isSymLink()||!plainDirectory(parent))return failure("new_private_export_directory_required");
    const auto canonicalParent=QDir(parent).canonicalPath();const auto canonicalRoot=QDir(m_root).canonicalPath();
    if(canonicalParent==canonicalRoot||canonicalParent.startsWith(canonicalRoot+"/"))return failure("export_must_be_outside_store");
    const auto stage=parent+"/.nova-notes-export-"+QUuid::createUuid().toString(QUuid::WithoutBraces);
    if(!QDir().mkdir(stage)||!QFile::setPermissions(stage,PrivateDirectory))return failure("write_failed");
    auto abort=[&](const QString& reason){QDir(stage).removeRecursively();return failure(reason);};
    if(!QDir().mkdir(stage+"/originals")||!QFile::setPermissions(stage+"/originals",PrivateDirectory))return abort("write_failed");
    const auto originals=doc.value("originals").toMap();
    for(auto i=originals.cbegin();i!=originals.cend();++i){
        const auto path=directory(id)+"/originals/"+i.key();if(imageState(path,i.value().toMap())!="ready")return abort("original_missing_or_corrupt");
        QFile f(path);if(!f.open(QIODevice::ReadOnly))return abort("read_failed");const auto bytes=f.read(MaxImage+1);
        if(bytes.size()!=i.value().toMap().value("bytes").toLongLong()||hash(bytes)!=i.key())return abort("original_changed_during_export");
        error=atomicWrite(stage+"/originals/"+i.key(),bytes);if(!error.isEmpty())return abort(error);
    }
    error=atomicWrite(stage+"/notebook.json",QJsonDocument::fromVariant(doc).toJson(QJsonDocument::Compact));if(!error.isEmpty())return abort(error);
    if(!QDir().rename(stage,target))return abort("export_publish_failed");
    return {{"ok",true},{"editionId",id},{"revision",doc.value("revision")},{"originalCount",originals.size()},{"privateOnly",true},{"directoryUrl",QUrl::fromLocalFile(target).toString()}};
}
}
