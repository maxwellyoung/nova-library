#include "ControllerCheck.h"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QtMath>
#include <cmath>
#ifdef Q_OS_UNIX
#include <fcntl.h>
#include <cerrno>
#include <unistd.h>
#include <sys/stat.h>
#endif

namespace {
QString stamp() { return QDateTime::currentDateTimeUtc().toString(Qt::ISODateWithMs); }
void increment(int& n) { if (n < 1000000000) ++n; }
QVariantMap refused() { return {{"ok", false}, {"error", "Export refused; review the current preview and select a new private local file."}, {"sent", false}}; }
}
ControllerCheck::ControllerCheck(bool injected, QObject* parent)
    : QObject(parent), m_injected(injected), m_startedAt(stamp()) {}
QStringList ControllerCheck::buttons() { return {"up","down","left","right","north","south","east","west","l1","l2","l3","r1","r2","r3","select","start","guide"}; }
QStringList ControllerCheck::axes() { return {"left-x","left-y","right-x","right-y"}; }
bool ControllerCheck::reject() { increment(m_rejected); emit changed(); return false; }
bool ControllerCheck::connectDevice(int id) {
    if (id < 0 || (!m_devices.contains(id) && m_devices.size() >= 8)) return reject();
    if (m_devices.contains(id) && m_devices[id].connected) { increment(m_duplicates); emit changed(); return true; }
    if (!m_devices.contains(id)) m_devices.insert(id, Device{});
    m_devices[id].connected = true;
    m_lastEventAt = stamp(); emit changed(); return true;
}
void ControllerCheck::neutral(Device& d) {
    for (auto* map : {&d.buttons, &d.axes, &d.triggers})
        for (auto it = map->begin(); it != map->end(); ++it) { it->raw = 0; it->liveObserved = false; }
}
bool ControllerCheck::disconnectDevice(int id) {
    if (!m_devices.contains(id)) return reject();
    if (!m_devices[id].connected) { increment(m_duplicates); emit changed(); return true; }
    m_devices[id].connected = false; neutral(m_devices[id]);
    // Back has no device id in Qt5; discard its live state on any detach.
    m_back.raw = 0; m_back.liveObserved = false;
    m_resetReason = "device-disconnected"; m_lastEventAt = stamp(); emit changed(); return true;
}
bool ControllerCheck::button(int id, const QString& control, bool down) { return observe(id, control, down ? 1 : 0, 0); }
bool ControllerCheck::axis(int id, const QString& control, double value) { return observe(id, control, value, 1); }
bool ControllerCheck::trigger(int id, const QString& control, double value) { return observe(id, control, value, 2); }
bool ControllerCheck::observe(int id, const QString& control, double value, int kind) {
    if (!m_active) return false;
    if (!m_devices.contains(id) || !m_devices[id].connected || !std::isfinite(value)
        || value < (kind == 1 ? -1 : 0) || value > 1
        || (kind == 0 && !buttons().contains(control))
        || (kind == 1 && !axes().contains(control))
        || (kind == 2 && control != "l2" && control != "r2")) return reject();
    auto& d = m_devices[id];
    auto& values = kind == 0 ? d.buttons : kind == 1 ? d.axes : d.triggers;
    auto& s = values[control];
    if (s.liveObserved && s.raw == value) { increment(m_duplicates); emit changed(); return true; }
    if (s.liveObserved && s.raw != value) increment(s.changes);
    if (!s.seen) s.minimum = s.maximum = value;
    else { s.minimum = qMin(s.minimum, value); s.maximum = qMax(s.maximum, value); }
    s.seen = true; s.liveObserved = true; s.raw = value;
    if (kind != 1) { if (value > (kind == 2 ? m_threshold : 0)) s.downSeen = true; else s.upSeen = true; }
    m_lastEventAt = stamp(); emit changed(); return true;
}
bool ControllerCheck::systemBack(bool down, bool autoRepeat) {
    if (!m_active) return false;
    if (autoRepeat || (m_back.liveObserved && m_back.raw == (down ? 1 : 0))) { increment(m_duplicates); emit changed(); return true; }
    if (m_back.liveObserved) increment(m_back.changes);
    m_back.seen = true; m_back.liveObserved = true; m_back.raw = down ? 1 : 0;
    if (down) m_back.downSeen = true; else m_back.upSeen = true;
    m_lastEventAt = stamp(); emit changed(); return true;
}
void ControllerCheck::resetLive(const QString& reason) {
    for (auto it = m_devices.begin(); it != m_devices.end(); ++it) neutral(it.value());
    m_back.raw = 0; m_back.liveObserved = false; m_resetReason = reason;
}
void ControllerCheck::setActive(bool active) {
    if (m_enabled == active) return;
    m_enabled = active;
    const bool next = m_enabled && m_focused;
    const bool wasActive = m_active;
    m_active = next; if (wasActive && !next) resetLive("diagnostic-closed");
    emit changed();
}
void ControllerCheck::setFocused(bool focused) {
    if (m_focused == focused) return;
    m_focused = focused;
    const bool next = m_enabled && m_focused;
    const bool wasActive = m_active;
    m_active = next; if (wasActive && !next) resetLive("focus-lost");
    emit changed();
}
bool ControllerCheck::setDeadzone(double value) {
    if (!std::isfinite(value) || value < 0 || value > 0.5) return reject();
    m_deadzone = value; emit changed(); return true;
}
bool ControllerCheck::setTriggerThreshold(double value) {
    if (!std::isfinite(value) || value < 0 || value > 1) return reject();
    m_threshold = value; emit changed(); return true;
}
QVariantMap ControllerCheck::sampleState(const Sample& s, int kind) const {
    double filtered = s.raw;
    if (kind == 1) filtered = qAbs(s.raw) <= m_deadzone ? 0 : std::copysign((qAbs(s.raw)-m_deadzone)/(1-m_deadzone), s.raw);
    QVariantMap out{{"seen",s.seen},{"liveValueObserved",s.liveObserved},{"raw",s.raw},{"filtered",filtered},{"changes",s.changes},
                    {"pressObserved",s.downSeen},{"releaseObserved",s.upSeen}};
    if (kind != 0) { out.remove("pressObserved"); out.remove("releaseObserved"); out["minimum"] = s.seen ? QVariant(s.minimum) : QVariant(); out["maximum"] = s.seen ? QVariant(s.maximum) : QVariant(); }
    if (kind == 2) out["aboveThreshold"] = s.raw > m_threshold;
    return out;
}
QVariantMap ControllerCheck::state() const {
    QVariantList devices;
    for (auto it = m_devices.cbegin(); it != m_devices.cend(); ++it) {
        QVariantMap b,a,t;
        for (const auto& key : buttons()) b[key] = sampleState(it->buttons.value(key),0);
        for (const auto& key : axes()) a[key] = sampleState(it->axes.value(key),1);
        for (const auto& key : QStringList{"l2","r2"}) t[key] = sampleState(it->triggers.value(key),2);
        devices.append(QVariantMap{{"qtDeviceId",it.key()},{"identityScope","volatile Qt id; hardware serial not established"},
            {"connected",it->connected},{"buttons",b},{"axes",a},{"triggers",t},
            {"triggerResolution","Qt pressure values only; analogue hardware resolution not established"}});
    }
    return {{"schemaVersion",1},{"kind","nova-controller-check"},{"method",m_injected ? "injected" : "observed"},
        {"physicalAccepted",false},{"runtime","QtGamepad event API"},{"qtVersion",QString::fromLatin1(qVersion())},
        {"hostBuildIdentity",m_runtimeMetadata.isEmpty() ? "not established by this standalone model" : "runtime metadata only; source/artifact binding requires a separate build receipt"},{"runtimeMetadata",m_runtimeMetadata},{"privateExportConfigured",m_confinedExports && !m_privateParent.isEmpty()},{"startedAt",m_startedAt},{"lastEventAt",m_lastEventAt},
        {"active",m_active},{"captureEnabled",m_enabled},{"focused",m_focused},{"deadzone",m_deadzone},{"triggerThreshold",m_threshold},{"devices",devices},
        {"systemBack",sampleState(m_back,0)},{"backDeviceIdentity","unavailable in Qt5 QKeyEvent"},
        {"duplicateEvents",m_duplicates},{"rejectedEvents",m_rejected},{"lastResetReason",m_resetReason},
        {"resetMeaning","Neutral live values are synthetic resets, never observed hardware releases or range samples."}};
}
QByteArray ControllerCheck::bytes() const { return QJsonDocument::fromVariant(state()).toJson(QJsonDocument::Indented); }
QVariantMap ControllerCheck::preview() const {
    const auto data=bytes();
    return {{"json",QString::fromUtf8(data)},{"bytes",data.size()},
        {"sha256",QString::fromLatin1(QCryptographicHash::hash(data,QCryptographicHash::Sha256).toHex())},{"sent",false}};
}
QVariantMap ControllerCheck::exportReport(const QString& path, const QString& approved) const {
    const auto p=preview();
    if (approved.isEmpty() || approved != p.value("sha256").toString() || p.value("bytes").toInt() > 65536) return refused();
#ifdef Q_OS_UNIX
    const QFileInfo output(path);
    const auto parent=output.absoluteDir().absolutePath();
    if (m_confinedExports && (m_privateParent.isEmpty() || QDir::cleanPath(parent) != m_privateParent+QStringLiteral("/controller-checks"))) return refused();
    if (path.contains(QChar(0)) || !output.isAbsolute() || QDir(parent).canonicalPath() != QDir::cleanPath(parent) || output.fileName().isEmpty()) return refused();
    const auto directoryBytes=QFile::encodeName(parent), name=QFile::encodeName(output.fileName());
    int directoryFd=::open(directoryBytes.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (directoryFd < 0) return refused();
    int fd=::openat(directoryFd,name.constData(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW,0600);
    if (fd < 0) { ::close(directoryFd); return refused(); }
    struct stat own{}; ::fstat(fd,&own);
    const auto data=bytes(); qint64 done=0;
    while (done<data.size()) { auto n=::write(fd,data.constData()+done,size_t(data.size()-done)); if (n<=0) break; done+=n; }
    const bool flushed=done==data.size() && ::fsync(fd)==0;
    ::close(fd);
    if (!flushed) {
        struct stat current{};
        if (::fstatat(directoryFd,name.constData(),&current,AT_SYMLINK_NOFOLLOW)==0 && own.st_ino==current.st_ino && own.st_dev==current.st_dev) ::unlinkat(directoryFd,name.constData(),0);
        ::close(directoryFd); return refused();
    }
    ::close(directoryFd);
    return {{"ok",true},{"bytes",data.size()},{"sha256",approved},{"sent",false}};
#else
    Q_UNUSED(path); return refused();
#endif
}

void ControllerCheck::configureApplication(const QVariantMap& metadata, const QString& privateParent) {
    // Native integration opts into confinement even when private storage is
    // unavailable; an empty standard path must never become a relative export.
    m_confinedExports = true;
    m_privateParent.clear();
    const auto parent=QDir(privateParent).absolutePath();
    if (!privateParent.isEmpty() && QFileInfo(privateParent).isAbsolute()
        && QDir(parent).canonicalPath()==QDir::cleanPath(parent)) m_privateParent=parent;
    m_runtimeMetadata.clear();
    const QStringList fields{"applicationId","applicationName","applicationVersion","platform","platformVersion","androidModel","androidApiLevel","inputBackend"};
    const QRegularExpression plain(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9 ._:+()/-]{0,127}$"));
    for (const auto& key:fields) {
        const auto value=metadata.value(key).toString();
        m_runtimeMetadata[key]=plain.match(value).hasMatch() && !value.contains(QLatin1Char('/')) ? value : QStringLiteral("unknown");
    }
    emit changed();
}
QVariantMap ControllerCheck::exportPrivateReport(const QString& fileName, const QString& approved) const {
    const QRegularExpression leaf(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\\.json$"));
    const auto p=preview();
    if (!m_confinedExports || m_privateParent.isEmpty() || !leaf.match(fileName).hasMatch()
        || approved.isEmpty() || approved!=p.value("sha256").toString() || p.value("bytes").toInt()>65536) return refused();
#ifdef Q_OS_UNIX
    const auto base=QFile::encodeName(m_privateParent);
    const int dir=::open(base.constData(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW);
    if (dir<0) return refused();
    if (::mkdirat(dir,"controller-checks",0700)!=0 && errno!=EEXIST) { ::close(dir); return refused(); }
    struct stat existing{};
    const bool safe=::fstatat(dir,"controller-checks",&existing,AT_SYMLINK_NOFOLLOW)==0
        && S_ISDIR(existing.st_mode) && (existing.st_mode & 0077)==0 && existing.st_uid==::geteuid();
    ::close(dir);
    if (!safe) return refused();
    return exportReport(m_privateParent+QStringLiteral("/controller-checks/")+fileName,approved);
#else
    return refused();
#endif
}
