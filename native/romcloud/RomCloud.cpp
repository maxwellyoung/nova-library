// SPDX-License-Identifier: GPL-3.0-or-later
#include "RomCloud.h"
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QSaveFile>
#include <QDir>
#include <QDirIterator>
#include <QFileInfo>
#include <QStorageInfo>
#include <QCryptographicHash>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QHostAddress>
#include <QTimer>
#include <QDateTime>
#include <QThread>
#include <algorithm>
#ifdef Q_OS_UNIX
#include <sys/stat.h>
#endif
#ifdef Q_OS_ANDROID
#include <QAndroidJniObject>
#include <QAndroidJniEnvironment>
#endif
namespace library {
namespace {
QByteArray originBytes(QUrl url) {
    url.setPath(QString());
    if((url.scheme()=="https" && url.port()==443) || (url.scheme()=="http" && url.port()==80))url.setPort(-1);
    return url.toEncoded();
}
RomCloudConfig platformConfig() {
    RomCloudConfig c;
#ifdef Q_OS_ANDROID
    QAndroidJniObject payload = QAndroidJniObject::callStaticObjectMethod("org/pegasus_frontend/android/RomCloudVault", "enrollment", "()Ljava/lang/String;");
    QAndroidJniEnvironment env;
    if (env->ExceptionCheck()) { env->ExceptionClear(); return c; }
    auto o = QJsonDocument::fromJson(payload.toString().toUtf8()).object();
    c.endpoint = QUrl(o["endpoint"].toString()); c.token = o["token"].toString().toUtf8(); c.root = o["romRoot"].toString();
    c.cache = QStandardPaths::writableLocation(QStandardPaths::AppDataLocation) + "/rom-cloud";
#endif
    return c;
}
QString coreFor(const QString& platform) {
    if (platform == "ps") return "swanstation_libretro_android.so";
    if (platform == "snes") return "snes9x_libretro_android.so";
    return {};
}
QString digest(const QString& path, const QByteArray& expected) {
    QFile f(path); if (!f.open(QIODevice::ReadOnly)) return {};
    QCryptographicHash hash(expected.size() == 40 ? QCryptographicHash::Sha1 : QCryptographicHash::Md5);
    while (!f.atEnd()) {
        if (QThread::currentThread()->isInterruptionRequested()) return {};
        const auto bytes=f.read(256*1024);
        if (f.error()!=QFile::NoError) return {};
        hash.addData(bytes);
    }
    return QString::fromLatin1(hash.result().toHex());
}
class DigestThread final : public QThread {
public:
    DigestThread(const QString& path, const QByteArray& hash) : path(path), hash(hash) {}
    QString result;
protected:
    void run() override { result=digest(path,hash); }
private:
    QString path;
    QByteArray hash;
};
bool writeJson(const QString& path, const QVariant& value) {
    QSaveFile f(path); if (!f.open(QIODevice::WriteOnly)) return false;
    auto bytes = QJsonDocument::fromVariant(value).toJson(QJsonDocument::Compact);
    return f.write(bytes) == bytes.size() && f.commit();
}
QVariant readJson(const QString& path, qint64 limit = 8*1024*1024) {
    QFile f(path); if (!f.open(QIODevice::ReadOnly) || f.size() > limit) return {};
    return QJsonDocument::fromJson(f.readAll()).toVariant();
}
QVariantList fileIdentity(const QString& path, bool directory = false) {
#ifdef Q_OS_UNIX
    struct stat s;
    if(::lstat(QFile::encodeName(path).constData(), &s) || (directory ? !S_ISDIR(s.st_mode) : !S_ISREG(s.st_mode))) return {};
    QVariantList out{QString::number(s.st_dev),QString::number(s.st_ino),QString::number(s.st_mode)};
    if(directory) return out; // Moving the directory changes its own timestamps.
#ifdef Q_OS_MACOS
    const auto mt=s.st_mtimespec,ct=s.st_ctimespec;
#else
    const auto mt=s.st_mtim,ct=s.st_ctim;
#endif
    out << QString::number(s.st_size) << QString::number(mt.tv_sec) << QString::number(mt.tv_nsec)
        << QString::number(ct.tv_sec) << QString::number(ct.tv_nsec);
    return out;
#else
    Q_UNUSED(path); Q_UNUSED(directory); return {};
#endif
}
}
bool RomCloud::allowedEndpoint(const QUrl& url) {
    if (!url.isValid() || url.host().isEmpty() || !url.userInfo().isEmpty() || url.hasQuery() || url.hasFragment() || (url.path() != "" && url.path() != "/")) return false;
    // HTTP credentials are permitted only inside loopback or a Tailscale address.
    QHostAddress ip(url.host());
    const bool tail = ip.protocol() == QAbstractSocket::IPv4Protocol && (ip.toIPv4Address() & 0xffc00000u) == 0x64400000u;
    return url.scheme() == "https" || (url.scheme() == "http" && (ip.isLoopback() || tail));
}
bool RomCloud::safeName(const QString& s) {
    if (s.isEmpty() || s.size() > 180 || s == "." || s == ".." || s.startsWith('.') || s.contains('/') || s.contains('\\') || s.contains(':') || s != s.trimmed()) return false;
    for (QChar c : s) if (c.unicode() < 32 || c.unicode() == 127) return false;
    return true;
}
QVariantMap RomCloud::validateGame(const QVariantMap& source) {
    QVariantMap g; const int id = source.value("id").toInt();
    if (id <= 0) return g;
    auto platform = source.value("platform_slug").toString();
    g["id"] = id; g["title"] = source.value("name").toString().left(300);
    if (g["title"].toString().isEmpty()) g["title"] = source.value("fs_name").toString().left(300);
    g["platform"] = platform; g["system"] = source.value("platform_display_name").toString().left(120);
    const QUrl cover(source.value("path_cover_small").toString());
    if(cover.isRelative() && cover.authority().isEmpty() && !cover.hasFragment() && cover.path().startsWith("/assets/") && !cover.path().split('/').contains("..")) g["coverPath"]=cover.toString();
    g["supported"] = !coreFor(platform).isEmpty(); g["files"] = QVariantList();
    QString entry = source.value("fs_name").toString();
    auto rawFiles = source.value("files").toList(); QVariantList files; qint64 total = 0;
    QSet<QString> names; bool valid = !rawFiles.isEmpty() && rawFiles.size() <= 16;
    for (const auto& raw : rawFiles) {
        const auto f = raw.toMap(); const auto name = f.value("file_name").toString();
        const auto category = f.value("category").toString();
        if (!category.isEmpty() && category != "game") continue;
        const auto suffix = QFileInfo(name).suffix().toLower();
        const QStringList supported = platform == "ps" ? QStringList{"chd", "m3u", "pbp"} : QStringList{"sfc", "smc", "zip"};
        const double size = f.value("file_size_bytes").toDouble();
        const auto sha1 = f.value("sha1_hash").toString().toLower(); const auto md5 = f.value("md5_hash").toString().toLower();
        const auto hash = QRegularExpression("^[0-9a-f]{40}$").match(sha1).hasMatch() ? sha1 : md5;
        if (!safeName(name) || names.contains(name.toCaseFolded()) || !supported.contains(suffix) || f.value("id").toInt() <= 0 || size <= 0 || size > 64.0*1024*1024*1024 || size != double(qint64(size)) || !QRegularExpression("^([0-9a-f]{32}|[0-9a-f]{40})$").match(hash).hasMatch()) { valid = false; break; }
        names.insert(name.toCaseFolded()); total += qint64(size);
        files.append(QVariantMap{{"id", f.value("id")}, {"name", name}, {"bytes", qint64(size)}, {"hash", hash}});
    }
    if (files.isEmpty()) valid = false;
    if (files.size() == 1) entry = files.first().toMap()["name"].toString();
    else {
        QStringList playlists;
        for(const auto& raw:files) {auto name=raw.toMap()["name"].toString();if(name.endsWith(".m3u",Qt::CaseInsensitive))playlists.append(name);}
        if(playlists.size()==1)entry=playlists.first();else valid=false;
    }
    g["needsDetails"] = !coreFor(platform).isEmpty() && rawFiles.isEmpty();
    g["supported"] = g["supported"].toBool() && (valid || g["needsDetails"].toBool());
    g["reason"] = coreFor(platform).isEmpty() ? "This emulator is not connected yet." : "Needs a scan with file checksums; disc sets must include their M3U playlist.";
    g["files"] = files; g["bytes"] = rawFiles.isEmpty() ? qMax<qint64>(0,source.value("fs_size_bytes").toLongLong()) : total; g["entry"] = entry;
    return g;
}
RomCloud::RomCloud(QObject* parent) : RomCloud(platformConfig(), parent) {}
RomCloud::RomCloud(const RomCloudConfig& config, QObject* parent) : QObject(parent), m_config(config) {
    if (!allowedEndpoint(config.endpoint) || config.token.isEmpty() || config.token.size() > 8192 || config.token.contains('\n') || config.token.contains('\r') || !QDir::isAbsolutePath(config.root) || QDir::cleanPath(config.root) == "/" || !QDir::isAbsolutePath(config.cache) || config.root.split('/').contains("..")) { m_config = {}; return; }
    QDir().mkpath(config.cache); loadCache(); m_message = "Cloud library ready. Refresh to check for games.";
}
RomCloud::~RomCloud() { if(m_verifier)m_verifier->requestInterruption(); }
QString RomCloud::gamePath(int id) const { return m_config.root + "/nova-cloud/" + QString::number(id); }
bool RomCloud::safeDirectory(const QString& path, bool create) const {
    if (m_config.root.isEmpty() || !QDir::isAbsolutePath(path)) return false;
    const auto root = QDir::cleanPath(m_config.root); const auto clean = QDir::cleanPath(path);
    if (clean != root && !clean.startsWith(root + "/")) return false;
    // Do not follow symlinks in any ancestor, including the selected root.
    QString current = "/";
    for (const auto& part : clean.split('/', Qt::SkipEmptyParts)) { current = QDir(current).filePath(part); if (QFileInfo(current).isSymLink()) return false; }
    if (create && !QDir().mkpath(clean)) return false;
    return QFileInfo(clean).isDir();
}
QVariantMap RomCloud::installedManifest(int id) const {
    const auto path = gamePath(id);
    if (id <= 0 || !safeDirectory(path) || QFileInfo(path + "/.nova-install.json").isSymLink()) return {};
    const auto marker = readJson(path + "/.nova-install.json", 65536).toMap();
    if (marker.value("id").toInt() != id || marker.value("endpoint").toString() != m_config.endpoint.toString()) return {};
    QVariantList rawFiles;
    for (const auto& raw : marker.value("files").toList()) {
        const auto f=raw.toMap();const auto hash=f["hash"].toString();
        rawFiles.append(QVariantMap{{"id",f["id"]},{"file_name",f["name"]},{"file_size_bytes",f["bytes"]},
            {"sha1_hash",hash.size()==40?hash:QString()},{"md5_hash",hash.size()==32?hash:QString()}});
    }
    // The launch target must be one of the exact, supported files checked at
    // installation. A neighbouring file or linked ownership marker is not a route.
    const auto checked=validateGame(QVariantMap{{"id",id},{"name","Download"},{"fs_name",marker["entry"]},
        {"platform_slug",marker["platform"]},{"files",rawFiles}});
    if (!checked["supported"].toBool() || checked["needsDetails"].toBool()
        || checked["entry"]!=marker["entry"] || checked["files"]!=marker["files"]) return {};
    for (const auto& raw : checked.value("files").toList()) {
        auto f = raw.toMap(); auto name = f["name"].toString(); QFileInfo info(path+"/"+name);
        if (info.isSymLink() || !info.isFile() || info.size() != f["bytes"].toLongLong()) return {};
    }
    return marker;
}
bool RomCloud::ownedInstalled(int id) const { return !installedManifest(id).isEmpty(); }
QVariantMap RomCloud::partialPlan(const QVariantMap& game) const {
    QVariantMap out{{"partialPresent",false},{"resumeAvailable",false},{"blocked",false},{"retainedBytes",qint64(0)}};
    const auto folder=gamePath(game["id"].toInt())+".partial";
    const QFileInfo dir(folder);
    if(!dir.exists() && !dir.isSymLink())return out;
    out["partialPresent"]=true;
    const auto blocked=[&out](const QString& why){out["blocked"]=true;out["reason"]=why;return out;};
    if(!safeDirectory(folder))return blocked("Download storage is linked or unavailable. Retained files were kept.");
    QStringList entries;QDirIterator scan(folder,QDir::AllEntries|QDir::Hidden|QDir::NoDotAndDotDot);
    while(scan.hasNext()) {
        entries.append(QFileInfo(scan.next()).fileName());
        // A supported descriptor has at most sixteen payloads and one plan.
        if(entries.size()>17)return blocked("Too many retained files. Everything was kept for review.");
    }
    if(entries.isEmpty())return out;
    const auto plan=folder+"/.plan.json";
    if(QFileInfo(plan).isSymLink() || fileIdentity(plan).isEmpty())return blocked("Unrecognised partial files; nothing will be replaced.");
#ifdef Q_OS_UNIX
    struct stat planStat;if(::lstat(QFile::encodeName(plan).constData(),&planStat) || planStat.st_nlink!=1)
        return blocked("The retained download plan is linked or unreadable. Files were kept.");
#endif
    const auto old=readJson(plan,65536).toMap();
    if(old.isEmpty())return blocked("The retained download plan is unreadable. Files were kept for review.");
    if(old.contains("endpoint") && old["endpoint"].toString()!=m_config.endpoint.toString())
        return blocked("These partial files belong to a different library. They were kept.");
    if(game["needsDetails"].toBool()){out["reason"]="File details must be checked before resuming.";return out;}
    if(old["files"]!=game["files"] || old["entry"]!=game["entry"] || old["platform"]!=game["platform"] || old["id"]!=game["id"])
        return blocked("The server's files changed. Retained files need review before resuming.");
    QSet<QString> permitted{QStringLiteral(".plan.json")};
    for(const auto& raw:game["files"].toList())permitted.insert(raw.toMap()["name"].toString());
    for(const auto& name:entries)if(!permitted.contains(name))return blocked("Extra files are protected, including saves. Review this download before resuming.");
    qint64 retained=0;
    for(const auto& raw:game["files"].toList()) {
        const auto f=raw.toMap();const auto path=folder+"/"+f["name"].toString();const QFileInfo local(path);
        if(!local.exists() && !local.isSymLink())continue;
        if(local.isSymLink() || fileIdentity(path).isEmpty())return blocked("A retained file is linked or unreadable. Nothing will be replaced.");
#ifdef Q_OS_UNIX
        struct stat s;if(::lstat(QFile::encodeName(path).constData(),&s) || s.st_nlink!=1)
            return blocked("A retained file is linked or unreadable. Nothing will be replaced.");
#endif
        if(local.size()>f["bytes"].toLongLong())return blocked("A retained file is larger than expected. Files were kept for review.");
        retained+=local.size();
    }
    out["retainedBytes"]=retained;out["resumeAvailable"]=true;
    out["reason"]=old.contains("endpoint")?"Retained bytes can be resumed; every completed file is checked.":"Earlier download files will be checked before they can be used.";
    return out;
}
QString RomCloud::editionIdentity(const QUrl& endpoint, const QVariantMap& game) {
    if(!allowedEndpoint(endpoint) || game["id"].toInt()<=0)return {};
    QVariantList files;
    for(const auto& raw:game["files"].toList()) {
        const auto f=raw.toMap();
        files.append(QVariantMap{{"name",f["name"]},{"bytes",f["bytes"]},{"hash",f["hash"]}});
    }
    std::sort(files.begin(),files.end(),[](const QVariant& a,const QVariant& b){return a.toMap()["name"].toString()<b.toMap()["name"].toString();});
    const auto scope=QCryptographicHash::hash(originBytes(endpoint),QCryptographicHash::Sha256).toHex();
    const auto content=QJsonDocument::fromVariant(QVariantMap{{"platform",game["platform"]},{"entry",game["entry"]},{"files",files}}).toJson(QJsonDocument::Compact);
    const auto revision=QCryptographicHash::hash(content,QCryptographicHash::Sha256).toHex();
    return "nova:cloud_"+QString::fromLatin1(scope)+":"+QString::number(game["id"].toInt())+"_"+QString::fromLatin1(revision);
}
QVariantList RomCloud::games() const {
    auto result = m_games;
    for (auto& raw : result) {
        auto g=raw.toMap();const int id=g["id"].toInt();const auto marker=installedManifest(id);
        const auto cover=m_config.cache+"/covers/"+QString::number(id)+".img";
        g["cover"]=QFileInfo(cover).isFile() && !QFileInfo(cover).isSymLink()?QUrl::fromLocalFile(cover).toString():QString();
        const auto recovery=partialPlan(g);
        g["installed"]=!marker.isEmpty();g["partial"]=recovery["partialPresent"];
        g["resumeAvailable"]=recovery["resumeAvailable"];g["downloadBlocked"]=marker.isEmpty() && recovery["blocked"].toBool();
        g["downloadReason"]=recovery["reason"];g["retainedBytes"]=recovery["retainedBytes"];
        g["downloadState"]=!marker.isEmpty()?"installed":m_busy && !m_launchChecking && m_installId==id?"downloading":recovery["blocked"].toBool()?"blocked":recovery["partialPresent"].toBool()?"partial":"none";
        g["editionId"]=editionIdentity(m_config.endpoint,marker.isEmpty()?g:marker);
        const auto scope=QCryptographicHash::hash(originBytes(m_config.endpoint),QCryptographicHash::Sha256).toHex();
        g["cloudKey"]="cloud:"+QString::fromLatin1(scope)+":"+QString::number(id);
        g["observedAt"]=QDateTime::currentDateTimeUtc().toString(Qt::ISODate);
        g["cloudCopyChanged"]=!marker.isEmpty() && !g["needsDetails"].toBool() && g["supported"].toBool()
            && g["editionId"].toString()!=editionIdentity(m_config.endpoint,g);
        if(!marker.isEmpty()) {
            g["platform"]=marker["platform"];g["entry"]=marker["entry"];
            qint64 bytes=0;for(const auto& file:marker["files"].toList())bytes+=file.toMap()["bytes"].toLongLong();g["bytes"]=bytes;
        }
        raw=g;
    }
    return result;
}
void RomCloud::loadCache() {
    auto cached = readJson(m_config.cache+"/catalogue.json").toMap();
    if (cached["endpoint"].toString() != m_config.endpoint.toString()) return;
    QVariantList checked;
    for(const auto& raw:cached["games"].toList()) {
        auto g=raw.toMap(); QVariantList files;
        for(const auto& value:g["files"].toList()) {auto f=value.toMap(); files.append(QVariantMap{{"id",f["id"]},{"file_name",f["name"]},{"file_size_bytes",f["bytes"]},{"sha1_hash",f["hash"].toString().size()==40?f["hash"]:QVariant()},{"md5_hash",f["hash"].toString().size()==32?f["hash"]:QVariant()}});}
        auto rebuilt=validateGame(QVariantMap{{"id",g["id"]},{"name",g["title"]},{"platform_slug",g["platform"]},{"platform_display_name",g["system"]},{"fs_name",g["entry"]},{"path_cover_small",g["coverPath"]},{"fs_size_bytes",g["bytes"]},{"files",files}});
        if(rebuilt.isEmpty() || rebuilt["supported"] != g["supported"]) return;
        checked.append(rebuilt);
    }
    m_games=checked;
}
bool RomCloud::writeCache() { return writeJson(m_config.cache+"/catalogue.json", QVariantMap{{"endpoint", m_config.endpoint.toString()}, {"games", m_games}}); }
QNetworkRequest RomCloud::request(const QString& path) const {
    QNetworkRequest req(m_config.endpoint.resolved(QUrl(path)));
    req.setRawHeader("Authorization", "Bearer " + m_config.token);
    req.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
    req.setAttribute(QNetworkRequest::CacheLoadControlAttribute, QNetworkRequest::AlwaysNetwork);
#if QT_VERSION >= QT_VERSION_CHECK(5,15,0)
    req.setTransferTimeout(30000);
#endif
    return req;
}
void RomCloud::fail(const QString& message) { m_file.close(); m_busy=false; m_launchChecking=false; m_message=message; m_reply=nullptr; emit changed(); }
void RomCloud::refresh() {
    if (m_busy) return;
    if (m_config.token.isEmpty()) { m_message="Connect a private ROM library first."; emit changed(); return; }
    m_installId=0;m_coverTried.clear(); m_pending.clear(); m_progress=0; m_busy=true; m_cancelled=false; m_message="Checking your cloud library…"; emit changed(); page(0);
}
void RomCloud::page(int offset) {
    auto reply=m_network.get(request("/api/roms?limit=100&offset="+QString::number(offset)+"&with_char_index=false&with_filter_values=false&with_rom_id_index=false")); m_reply=reply;
    connect(reply,&QNetworkReply::readyRead,this,[reply]{ if (reply->bytesAvailable()>8*1024*1024) reply->abort(); });
    connect(reply,&QNetworkReply::finished,this,[this,reply,offset]{
        reply->deleteLater(); if (m_cancelled) return fail("Refresh cancelled; cached games retained.");
        if (reply->error()!=QNetworkReply::NoError || reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt()!=200) return fail("Cloud unavailable. Your cached library and downloads are still here.");
        auto bytes=reply->readAll(); if(bytes.size()>8*1024*1024) return fail("Cloud catalogue page is too large.");
        auto o=QJsonDocument::fromJson(bytes).object();
        if (!o["items"].isArray()) return fail("Cloud catalogue format was not recognised.");
        auto items=o["items"].toArray();
        for (const auto& raw:items) { auto g=validateGame(raw.toObject().toVariantMap()); if(g.isEmpty()) return fail("Cloud catalogue contains an invalid game."); for(const auto& old:m_pending) if(old.toMap()["id"]==g["id"]) return fail("Cloud catalogue repeated a game; cached library retained."); m_pending.append(g); }
        if(m_pending.size()>10000) return fail("Cloud catalogue exceeds this device's limit.");
        if(items.size()==100) return page(offset+100);
        auto previous=m_games; m_games=m_pending;
        if(!writeCache()) {m_games=previous;return fail("Could not save the catalogue; previous library retained.");}
        m_reply=nullptr; m_busy=false; m_message="Library refreshed. Download a game to play offline."; emit changed();
    });
}
void RomCloud::details(int id) {
    m_installId=id;m_busy=true; m_progress=0; m_cancelled=false; m_message="Checking download files…"; emit changed();
    auto reply=m_network.get(request("/api/roms/"+QString::number(id))); m_reply=reply;
    connect(reply,&QNetworkReply::readyRead,this,[reply]{if(reply->bytesAvailable()>2*1024*1024)reply->abort();});
    connect(reply,&QNetworkReply::finished,this,[this,reply,id]{
        reply->deleteLater();if(m_cancelled)return fail("Download check cancelled.");
        if(reply->error()!=QNetworkReply::NoError||reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt()!=200)return fail("Could not check this game's files. Cached downloads are unchanged.");
        auto bytes=reply->readAll();if(bytes.size()>2*1024*1024)return fail("Game file list is too large.");
        auto game=validateGame(QJsonDocument::fromJson(bytes).object().toVariantMap());
        if(game["id"].toInt()!=id||game["needsDetails"].toBool())return fail("This game needs a server scan with file checksums.");
        for(auto& raw:m_games)if(raw.toMap()["id"].toInt()==id)raw=game;
        if(!writeCache())return fail("Could not retain this game's download details.");
        m_busy=false;m_reply=nullptr;install(id);
    });
}
void RomCloud::requestCover(int id) {
    if(m_config.token.isEmpty()||id<=0||m_coverTried.contains(id))return;
    const auto target=m_config.cache+"/covers/"+QString::number(id)+".img";
    if(QFileInfo::exists(target))return;
    QString path;for(const auto& raw:m_games)if(raw.toMap()["id"].toInt()==id)path=raw.toMap()["coverPath"].toString();
    QUrl url(path);if(path.isEmpty()||!url.isRelative()||!url.authority().isEmpty()||!url.path().startsWith("/assets/")||url.path().split('/').contains(".."))return;
    m_coverTried.insert(id);
    if(m_coverReply) { auto old=m_coverReply; m_coverReply=nullptr; old->abort(); }
    auto reply=m_network.get(request(path));m_coverReply=reply;
    connect(reply,&QNetworkReply::readyRead,this,[reply]{if(reply->bytesAvailable()>2*1024*1024)reply->abort();});
    connect(reply,&QNetworkReply::finished,this,[this,reply,target]{
        reply->deleteLater();if(reply!=m_coverReply)return;
        m_coverReply=nullptr;if(reply->error()!=QNetworkReply::NoError||reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt()!=200)return;
        auto bytes=reply->readAll();if(bytes.isEmpty()||bytes.size()>2*1024*1024||!reply->header(QNetworkRequest::ContentTypeHeader).toString().startsWith("image/"))return;
        QDir().mkpath(m_config.cache+"/covers");QSaveFile f(target);if(f.open(QIODevice::WriteOnly)&&f.write(bytes)==bytes.size()&&f.commit())emit changed();
    });
}
QVariantMap RomCloud::installPlan(int id) const {
    QVariantMap out{{"spaceKnown",false},{"fits",false},{"blocked",false},{"headroomBytes",qint64(128)*1024*1024}};
    QVariantMap game; for(const auto& g:m_games) if(g.toMap()["id"].toInt()==id) game=g.toMap();
    if(game.isEmpty() || !game["supported"].toBool()) { out["reason"]="This download is not available.";return out; }
    out["totalBytes"]=game["bytes"];
    if(ownedInstalled(id)) {out["installed"]=true;out["remainingBytes"]=qint64(0);out["reason"]="Already downloaded.";return out;}
    const auto recovery=partialPlan(game);
    for(const auto& key:recovery.keys())out[key]=recovery[key];
    if(recovery["blocked"].toBool())return out;
    if(game["needsDetails"].toBool()) {out["reason"]="File details are checked before downloading.";return out;}
    if(!safeDirectory(m_config.root)) {out["reason"]="Selected storage is unavailable; free space is unknown.";return out;}
    const qint64 retained=recovery["retainedBytes"].toLongLong();
    const qint64 remaining=qMax<qint64>(0,game["bytes"].toLongLong()-retained);
    out["retainedBytes"]=retained;out["remainingBytes"]=remaining;
    QStorageInfo storage(m_config.root);storage.refresh();
    if(!storage.isValid() || !storage.isReady() || storage.bytesAvailable()<0) {out["reason"]="Free space could not be measured.";return out;}
    out["spaceKnown"]=true;out["freeBytes"]=storage.bytesAvailable();
    out["observedAt"]=QDateTime::currentDateTimeUtc().toString(Qt::ISODate);
    const qint64 required=remaining+out["headroomBytes"].toLongLong();
    out["requiredBytes"]=required;out["shortfallBytes"]=qMax<qint64>(0,required-storage.bytesAvailable());
    out["fits"]=storage.bytesAvailable()>=required;
    out["reason"]=out["fits"].toBool()?"Space measured; checked again when the download starts.":"Not enough free space. Remove a chosen download first; saves are not cleanup targets.";
    return out;
}
void RomCloud::install(int id) {
    if(m_busy || m_config.token.isEmpty()) return;
    QVariantMap game; for(const auto& g:m_games) if(g.toMap()["id"].toInt()==id) game=g.toMap();
    if(game["needsDetails"].toBool()) {
        const auto recovery=partialPlan(game);if(recovery["blocked"].toBool())return fail(recovery["reason"].toString());
        details(id);return;
    }
    if(!game["supported"].toBool()) return fail(game.value("reason","Game not available.").toString());
    if(ownedInstalled(id)) return fail("Already downloaded.");
    if(!safeDirectory(m_config.root,true)) return fail("The selected storage is unavailable.");
    const auto plan=installPlan(id);m_total=game["bytes"].toLongLong();
    if(plan["blocked"].toBool())return fail(plan["reason"].toString());
    if(!plan["spaceKnown"].toBool() || !plan["fits"].toBool()) return fail("Not enough free storage or storage unavailable. Your saves have not changed.");
    if(QFileInfo::exists(gamePath(id))) return fail("That installation folder already exists; no files were replaced.");
    if(!safeDirectory(gamePath(id)+".partial",true)) return fail("Cannot create a download folder.");
    const auto identity=gamePath(id)+".partial/.plan.json";
    if(QFileInfo(identity).isSymLink()) return fail("Download folder is unsafe.");
    auto old=readJson(identity,65536).toMap();
    if(old.isEmpty() && !QDir(gamePath(id)+".partial").entryList(QDir::AllEntries|QDir::Hidden|QDir::NoDotAndDotDot).isEmpty()) return fail("Unrecognised partial files; no files were replaced.");
    if(!old.isEmpty() && (old["files"] != game["files"] || old["entry"] != game["entry"] || old["platform"] != game["platform"] || old["id"] != game["id"])) return fail("The server's files changed. Keep this partial download aside before retrying.");
    if(old.contains("endpoint") && old["endpoint"].toString()!=m_config.endpoint.toString()) return fail("This partial download belongs to a different library; it was kept.");
    game["endpoint"]=m_config.endpoint.toString();
    if(!writeJson(identity,game)) return fail("Cannot save the download plan.");
    m_installId=id; m_files=game["files"].toList(); m_fileIndex=0; m_completed=0; m_progress=0; m_busy=true; m_cancelled=false; m_message="Downloading "+game["title"].toString(); emit changed(); nextFile();
}
void RomCloud::verify(const QString& path, const QByteArray& hash, const std::function<void(bool)>& complete) {
    // Full-disc checksums run away from the GUI thread; the context disconnects
    // the completion handler if the library is destroyed while hashing.
    auto worker=new DigestThread(path,hash);
    m_verifier=worker;
    connect(worker,&QThread::finished,this,[this,worker,hash,complete]{m_verifier=nullptr;if(m_cancelled)return fail("Paused. Files retained; nothing was opened.");complete(worker->result==QString::fromLatin1(hash));});
    connect(worker,&QThread::finished,worker,&QObject::deleteLater);
    worker->start();
}
void RomCloud::nextFile() {
    const auto folder=gamePath(m_installId)+".partial";
    if(!safeDirectory(folder)) return fail("Download storage was removed.");
    QVariantMap active;for(const auto& raw:m_games)if(raw.toMap()["id"].toInt()==m_installId)active=raw.toMap();
    if(active.isEmpty())return fail("The active download plan is unavailable. Files were kept.");
    const auto recovery=partialPlan(active);if(recovery["blocked"].toBool())return fail(recovery["reason"].toString());
    if(m_fileIndex==m_files.size()) {
        const auto game=readJson(folder+"/.plan.json",65536).toMap();
        for(const auto& raw:m_files) {
            auto f=raw.toMap(); if(!f["name"].toString().endsWith(".m3u",Qt::CaseInsensitive)) continue;
            QFile playlist(folder+"/"+f["name"].toString()); if(!playlist.open(QIODevice::ReadOnly)||playlist.size()>65536) return fail("Disc playlist is invalid.");
            auto lines=QString::fromUtf8(playlist.readAll()).split('\n'); int count=0;
            for(auto line:lines) { line=line.trimmed(); if(line.isEmpty()||line.startsWith('#'))continue; bool found=false; for(const auto& disc:m_files) {auto d=disc.toMap(); if(d["name"].toString()==line && !line.endsWith(".m3u",Qt::CaseInsensitive))found=true;} if(!safeName(line)||!found)return fail("Disc playlist references a missing or unsafe file."); ++count; }
            if(count<1) return fail("Disc playlist has no discs.");
        }
        QVariantMap marker{{"id",m_installId},{"endpoint",m_config.endpoint.toString()},{"files",m_files},{"entry",game["entry"]},{"platform",game["platform"]}};
        if(!writeJson(folder+"/.nova-install.json",marker) || !QDir().rename(folder,gamePath(m_installId))) return fail("Could not finish installation; partial files retained.");
        m_progress=1; m_busy=false; m_reply=nullptr; m_message="Download complete. Files checked. Cloud saves are not enabled in this build.";emit changed();return;
    }
    auto f=m_files[m_fileIndex].toMap(); const auto path=folder+"/"+f["name"].toString(); const auto size=f["bytes"].toLongLong(); const auto hash=f["hash"].toByteArray();
    QFileInfo info(path); if(info.isSymLink() || (info.exists()&&!info.isFile())) return fail("Unsafe partial file; nothing replaced.");
    if(info.exists()&&info.size()==size) {verify(path,hash,[this,size](bool valid){if(!valid)return fail("Checksum failed. Discard the partial download to retry.");m_completed+=size;++m_fileIndex;nextFile();});return;}
    if(info.exists()&&info.size()>size) return fail("Partial download is larger than expected.");
    const qint64 start=info.exists()?info.size():0;
    m_file.setFileName(path); if(!m_file.open(QIODevice::WriteOnly|QIODevice::Append))return fail("Cannot write to download storage.");
    auto req=request("/api/roms/"+QString::number(f["id"].toInt())+"/files/content/"+QString::fromLatin1(QUrl::toPercentEncoding(f["name"].toString())));
    if(start)req.setRawHeader("Range","bytes="+QByteArray::number(start)+"-");
    auto reply=m_network.get(req);m_reply=reply;
    auto consume=[this,reply,start,size]{
        if(!reply->isOpen())return; // An explicit pause may close the reply before finished.
        const int status=reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        if(!status)return;
        const QByteArray expected="bytes "+QByteArray::number(start)+"-"+QByteArray::number(size-1)+"/"+QByteArray::number(size);
        if((start && (status!=206||reply->rawHeader("Content-Range")!=expected))||(!start && status!=200)){reply->abort();return;}
        auto bytes=reply->read(256*1024);
        while(!bytes.isEmpty()) {if(m_file.size()+bytes.size()>size || m_file.write(bytes)!=bytes.size()){reply->abort();return;}bytes=reply->read(256*1024);}
        m_progress=double(m_completed+m_file.size())/qMax<qint64>(1,m_total);emit changed();
    };
    connect(reply,&QNetworkReply::readyRead,this,consume);
    connect(reply,&QNetworkReply::finished,this,[this,reply,consume,path,size,hash]{
        consume();m_file.close();reply->deleteLater();
        if(m_cancelled)return fail("Download paused. Retained files can be checked and resumed.");
        if(reply->error()!=QNetworkReply::NoError || QFileInfo(path).size()!=size)return fail("Download interrupted. Retained files can be checked and resumed; saves are unchanged.");
        m_reply=nullptr;m_message="Checking downloaded files…";emit changed();
        verify(path,hash,[this,size](bool valid){if(!valid)return fail("Checksum failed. Partial files retained; installation was not activated.");m_completed+=size;++m_fileIndex;nextFile();});
    });
}
void RomCloud::cancel() { if(!m_busy)return; m_cancelled=true;if(m_verifier)m_verifier->requestInterruption();if(m_reply)m_reply->abort(); }
QVariantMap RomCloud::inspectRemoval(int id, const QString& path, bool partial) const {
    QVariantMap out{{"id",id},{"partial",partial},{"eligible",false},{"bytesKnown",false}};
    auto blocked=[&out](const QString& reason){out["reason"]=reason;return out;};
    if(id<=0 || !safeDirectory(path)) return blocked("Download folder is unavailable.");
    const auto folderState=fileIdentity(path,true);
    if(folderState.isEmpty()) return blocked("File identity checks are unavailable on this filesystem.");
    const QString markerName=partial?".plan.json":".nova-install.json";
    if(QFileInfo(path+"/"+markerName).isSymLink()) return blocked("Linked metadata is protected.");
    const auto marker=readJson(path+"/"+markerName,65536).toMap();
    if(marker["id"].toInt()!=id || marker["endpoint"].toString()!=m_config.endpoint.toString())
        return blocked("This folder has no matching download ownership record.");
    QVariantList rawFiles;
    for(const auto& raw:marker["files"].toList()) {
        const auto f=raw.toMap();const auto hash=f["hash"].toString();
        rawFiles.append(QVariantMap{{"id",f["id"]},{"file_name",f["name"]},{"file_size_bytes",f["bytes"]},
            {"sha1_hash",hash.size()==40?hash:QString()},{"md5_hash",hash.size()==32?hash:QString()}});
    }
    const auto checked=validateGame(QVariantMap{{"id",id},{"name","Download"},{"fs_name",marker["entry"]},
        {"platform_slug",marker["platform"]},{"files",rawFiles}});
    if(!checked["supported"].toBool() || checked["needsDetails"].toBool() || checked["entry"]!=marker["entry"]
        || checked["files"]!=marker["files"]) return blocked("Download metadata is incomplete or includes unsupported files.");
    QStringList permitted{markerName};
    if(!partial && QFileInfo::exists(path+"/.plan.json")) {
        if(QFileInfo(path+"/.plan.json").isSymLink()) return blocked("Linked metadata is protected.");
        auto plan=readJson(path+"/.plan.json",65536).toMap();
        for(const auto& key:QStringList{"id","platform","entry","files"})
            if(plan[key]!=marker[key]) return blocked("Download metadata changed; this folder is protected.");
        permitted.append(".plan.json");
    }
    qint64 bytes=0;int payloadCount=0;
    for(const auto& raw:checked["files"].toList()) {
        auto f=raw.toMap();QString name=f["name"].toString();QFileInfo info(path+"/"+name);
        if(!info.exists() && partial) continue;
        if(!info.isFile() || info.isSymLink() || info.size()>f["bytes"].toLongLong()
            || (!partial && info.size()!=f["bytes"].toLongLong())) return blocked("Download files changed or are incomplete; review is required.");
        bytes+=info.size();++payloadCount;permitted.append(name);
    }
    auto entries=QDir(path).entryList(QDir::AllEntries|QDir::Hidden|QDir::NoDotAndDotDot);
    permitted.sort();entries.sort();
    if(entries!=permitted) return blocked("Extra files are protected, including any saves stored beside this download.");
    QVariantList states;
    for(const auto& name:entries) {
        const auto state=fileIdentity(path+"/"+name);
        if(state.isEmpty()) return blocked("A file is linked, unreadable or changed; download kept.");
        states.append(QVariantMap{{"name",name},{"identity",state}});
    }
    QVariantMap snapshot{{"root",m_config.root},{"endpoint",m_config.endpoint.toString()},{"id",id},{"partial",partial},
        {"folder",folderState},{"files",states},{"marker",marker}};
    out["_fingerprint"]=QString::fromLatin1(QCryptographicHash::hash(QJsonDocument::fromVariant(snapshot).toJson(QJsonDocument::Compact),QCryptographicHash::Sha256).toHex());
    out["_path"]=path;out["_names"]=entries;out["_states"]=states;out["bytesKnown"]=true;out["bytes"]=bytes;out["fileCount"]=payloadCount;
    if(m_busy) return blocked("Wait until the current download or verification finishes.");
    if(!m_config.removalBlocker) return blocked("Runtime idle is not verified. Cleanup is review-only in this build.");
    const auto runtimeReason=m_config.removalBlocker();
    if(!runtimeReason.isEmpty()) return blocked(runtimeReason);
    out["eligible"]=true;out["reason"]="Only these managed download files will be removed. Emulator saves are outside this folder.";
    return out;
}
QVariantMap RomCloud::removalPlan(int id) const {
    const auto complete=gamePath(id),partial=complete+".partial";
    QVariantMap out;
    if(QFileInfo::exists(complete) && QFileInfo::exists(partial))
        out={{"id",id},{"eligible",false},{"bytesKnown",false},{"reason","Both complete and partial folders exist; keep them for review."}};
    else out=inspectRemoval(id,QFileInfo::exists(complete)?complete:partial,!QFileInfo::exists(complete));
    if(out["eligible"].toBool()) out["token"]=QString::number(QDateTime::currentMSecsSinceEpoch())+":"+out["_fingerprint"].toString();
    out["observedAt"]=QDateTime::currentDateTimeUtc().toString(Qt::ISODate);
    for(const auto& key:out.keys()) if(key.startsWith('_')) out.remove(key);
    return out;
}
QVariantMap RomCloud::cleanupPlan(int installId) const {
    auto out=installPlan(installId);QVariantList candidates;
    for(const auto& raw:m_games) {
        const auto g=raw.toMap();int id=g["id"].toInt();
        if(id==installId || (!QFileInfo::exists(gamePath(id))&&!QFileInfo::exists(gamePath(id)+".partial"))) continue;
        auto candidate=removalPlan(id);candidate["title"]=g["title"];candidate["system"]=g["system"];
        candidates.append(candidate);
    }
    out["candidates"]=candidates;out["installId"]=installId;return out;
}
void RomCloud::removeDownload(int id, const QString& previewToken) {
    if(m_busy) return;
    const auto token=previewToken.split(':');bool ok=false;
    const qint64 issued=token.value(0).toLongLong(&ok),age=QDateTime::currentMSecsSinceEpoch()-issued;
    if(!ok || token.size()!=2 || age<0 || age>60000) return fail("Removal preview expired. Review this download again; nothing was removed.");
    const auto complete=gamePath(id),partial=complete+".partial";
    if(QFileInfo::exists(complete)&&QFileInfo::exists(partial)) return fail("Download folders changed; nothing was removed.");
    const bool isPartial=!QFileInfo::exists(complete);const auto path=isPartial?partial:complete;
    const auto plan=inspectRemoval(id,path,isPartial);
    if(!plan["eligible"].toBool()) return fail(plan["reason"].toString());
    if(token[1]!=plan["_fingerprint"].toString()) return fail("Files changed since review. Review again; nothing was removed.");
    QStorageInfo before(m_config.root);before.refresh();
    const auto detached=path+".removed";
    if(QFileInfo::exists(detached)||QFileInfo(detached).isSymLink()||!QDir().rename(path,detached)) return fail("Could not detach this download; nothing removed.");
    const auto rechecked=inspectRemoval(id,detached,isPartial);
    if(!rechecked["eligible"].toBool() || rechecked["_fingerprint"]!=plan["_fingerprint"]) {
        const bool restored=!QFileInfo::exists(path)&&!QFileInfo(path).isSymLink()&&QDir().rename(detached,path);
        return fail(restored?"Download changed during removal; it was kept.":"Download kept in its detached folder for recovery; no files removed.");
    }
    // Delete only reviewed payloads, then their metadata. No recursive sweep.
    auto names=plan["_names"].toStringList();
    std::stable_sort(names.begin(),names.end(),[](const QString& a,const QString& b){return a.startsWith('.')<b.startsWith('.');});
    for(const auto& name:names) {
        QVariantList expected;for(const auto& raw:plan["_states"].toList()) {auto f=raw.toMap();if(f["name"].toString()==name)expected=f["identity"].toList();}
        if(expected.isEmpty() || fileIdentity(detached+"/"+name)!=expected || !QFile::remove(detached+"/"+name))
            return fail("Removal stopped; remaining files are retained in the detached folder.");
    }
    if(!QDir().rmdir(detached)) return fail("Reviewed files removed; unexpected files remain in the detached folder.");
    QStorageInfo after(m_config.root);after.refresh();
    const QString measured=before.isValid()&&after.isValid()&&before.bytesAvailable()>=0&&after.bytesAvailable()>=0
        ?" Free-space change: "+QString::number(after.bytesAvailable()-before.bytesAvailable())+" bytes (other activity can affect this).":" Free-space change could not be measured.";
    m_message="Reviewed download removed; save folders were not touched."+measured;emit changed();
}
void RomCloud::play(int id) {
    if(m_busy)return;
    const auto marker=installedManifest(id);
    if(marker.isEmpty())return fail("This download is incomplete or its file record changed. Files were kept; review the download before playing.");
    const auto path=gamePath(id);
    QVariantList identities;identities.append(QVariant(fileIdentity(path+"/.nova-install.json")));
    for(const auto& raw:marker["files"].toList()) identities.append(QVariant(fileIdentity(path+"/"+raw.toMap()["name"].toString())));
    for(const auto& state:identities) if(state.toList().isEmpty())return fail("Download files could not be checked. Nothing was opened.");
    m_installId=0;m_busy=true;m_launchChecking=true;m_cancelled=false;m_progress=0;m_message="Checking downloaded files before opening…";emit changed();
    verifyLaunch(id,marker,identities,0);
}
void RomCloud::verifyLaunch(int id, const QVariantMap& marker, const QVariantList& identities, int index) {
    if(m_cancelled)return fail("Paused. Files retained; nothing was opened.");
    const auto path=gamePath(id);const auto files=marker["files"].toList();
    if(installedManifest(id)!=marker || fileIdentity(path+"/.nova-install.json")!=identities[0].toList())
        return fail("Download changed while checking. Files were kept; nothing was opened.");
    for(int i=0;i<files.size();++i)
        if(fileIdentity(path+"/"+files[i].toMap()["name"].toString())!=identities[i+1].toList())
            return fail("Download changed while checking. Files were kept; nothing was opened.");
    if(index<files.size()) {
        const auto file=files[index].toMap();
        verify(path+"/"+file["name"].toString(),file["hash"].toByteArray(),[this,id,marker,identities,index,files](bool valid){
            if(!valid)return fail("Downloaded file checksum failed. Files were kept; nothing was opened.");
            m_progress=double(index+1)/files.size();emit changed();
            verifyLaunch(id,marker,identities,index+1);
        });
        return;
    }
    const auto entry=marker["entry"].toString();const auto core=coreFor(marker["platform"].toString());
    const auto edition=editionIdentity(m_config.endpoint,marker);
    QString title="Cloud game";for(const auto& raw:m_games)if(raw.toMap()["id"].toInt()==id)title=raw.toMap()["title"].toString();
    emit launchPrepared(edition,title,marker["platform"].toString()=="ps"?"psx":marker["platform"].toString());
    emit launchRequested(path+"/"+entry,core);
#ifdef Q_OS_ANDROID
    const auto rom=QAndroidJniObject::fromString(path+"/"+entry);const auto lib=QAndroidJniObject::fromString(core);
    auto ok=QAndroidJniObject::callStaticMethod<jboolean>("org/pegasus_frontend/android/RomCloudVault","launch","(Ljava/lang/String;Ljava/lang/String;)Z",rom.object<jstring>(),lib.object<jstring>());
    QAndroidJniEnvironment env;if(env->ExceptionCheck()){env->ExceptionClear();ok=false;}
    if(ok)emit launchAccepted(edition);
    m_message=ok?"Opened in RetroArch. Using this device's saves.":"RetroArch could not open this game. Check its core installation.";
#else
    m_message="Download ready. Launch is available in the Android build.";
#endif
    m_busy=false;m_launchChecking=false;emit changed();
}
}
