// SPDX-License-Identifier: GPL-3.0-or-later
#include "FailureReports.h"
#include <QCryptographicHash>
#include <QDateTime>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QUuid>
#include <QCoreApplication>
#include <QPointer>
#include <utility>
#include <QThread>
#include <QUrl>
#ifdef Q_OS_UNIX
#include <fcntl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <unistd.h>
#include <cerrno>
#endif
namespace {
QString digest(const QByteArray& bytes) { return QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex()); }
bool hex(const QString& s,int n) { return QRegularExpression(QStringLiteral("^[a-f0-9]{%1}$").arg(n)).match(s).hasMatch(); }
bool editionId(const QString& s) { return QRegularExpression(QStringLiteral("^[A-Za-z0-9][A-Za-z0-9._:-]{0,511}$")).match(s).hasMatch(); }
QVariantMap failure(const char* code) { return {{"ok",false},{"error",QString::fromLatin1(code)},{"sent",false}}; }
QByteArray jsonBytes(const QJsonObject& object) {
    // Match the existing Python preview's sorted, two-space ASCII JSON exactly.
    QByteArray out;
    for(const auto& line:QJsonDocument(object).toJson(QJsonDocument::Indented).split('\n')) {
        if(line.isEmpty())continue;
        int indent=0;while(indent<line.size() && line[indent]==' ')++indent;
        out+=QByteArray(indent/2,' ')+line.mid(indent)+'\n';
    }
    return out;
}
class DocumentThread : public QThread {
public:
    DocumentThread(library::DocumentTarget target,const QByteArray& bytes)
        :m_target(std::move(target)),m_bytes(bytes) {}
    QVariantMap result;
protected:
    void run() override { result=m_target(m_bytes,[this] { return isInterruptionRequested(); }); }
private:
    library::DocumentTarget m_target;
    QByteArray m_bytes;
};
#ifdef Q_OS_UNIX
struct Fd { int value; explicit Fd(int v=-1):value(v){} ~Fd(){if(value>=0)::close(value);} Fd(const Fd&)=delete; Fd& operator=(const Fd&)=delete; };
int directory(const QString& path) {
    if(!QDir::isAbsolutePath(path) || QDir::cleanPath(path)!=path)return -1;
    // Android's private-data ancestors can allow search without directory
    // listing. Keep every component no-follow; only the final private root
    // needs a readable descriptor for capacity checks and durable export.
#if defined(O_PATH)
    constexpr int search=O_PATH;
#elif defined(O_SEARCH)
    constexpr int search=O_SEARCH;
#else
    constexpr int search=O_RDONLY;
#endif
    const auto parts=path.split('/',Qt::SkipEmptyParts);
    int fd=::open("/",(parts.isEmpty()?O_RDONLY:search)|O_DIRECTORY|O_CLOEXEC);
    for(int i=0;i<parts.size();++i) {
        if(fd<0)return -1;
        const int next=::openat(fd,parts[i].toUtf8().constData(),(i==parts.size()-1?O_RDONLY:search)|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        ::close(fd);fd=next;
    }
    return fd;
}
bool same(const struct stat& a,const struct stat& b){return a.st_dev==b.st_dev && a.st_ino==b.st_ino;}
// Android creates the app files directory as 0771 with the app's own per-app
// group. Group write is only accepted for that group; other-write still refuses.
bool ownerControlled(const struct stat& s){
    return s.st_uid==::geteuid() && !(s.st_mode&0002) && (!(s.st_mode&0020) || s.st_gid==::getegid());
}
QVariantMap writePrivate(const QString& root,const QByteArray& data) {
    Fd parent(directory(root));struct stat base{};
    if(parent.value<0 || ::fstat(parent.value,&base)!=0 || !ownerControlled(base))return failure("private_storage_unavailable");
    if(::mkdirat(parent.value,"failure-reports-v1",0700)!=0 && errno!=EEXIST)return failure("private_storage_unavailable");
    Fd dir(::openat(parent.value,"failure-reports-v1",O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC));struct stat folder{};
    if(dir.value<0 || ::fstat(dir.value,&folder)!=0 || folder.st_uid!=::geteuid() || (folder.st_mode&0077))return failure("private_storage_unavailable");
    const QByteArray name=(QStringLiteral("failure-")+QUuid::createUuid().toString(QUuid::Id128)+QStringLiteral(".json")).toLatin1();
    Fd file(::openat(dir.value,name.constData(),O_RDWR|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));struct stat created{};
    if(file.value<0 || ::fstat(file.value,&created)!=0)return failure("export_failed");
    auto refuse=[&](){struct stat current{};if(::fstatat(dir.value,name.constData(),&current,AT_SYMLINK_NOFOLLOW)==0 && same(current,created))::unlinkat(dir.value,name.constData(),0);return failure("export_failed");};
    if(!S_ISREG(created.st_mode) || (created.st_mode&0777)!=0600 || created.st_uid!=::geteuid())return refuse();
    qint64 done=0;
    while(done<data.size()) {const auto n=::write(file.value,data.constData()+done,size_t(data.size()-done));if(n<0 && errno==EINTR)continue;if(n<=0)return refuse();done+=n;}
    if(::fsync(file.value)!=0 || ::lseek(file.value,0,SEEK_SET)<0)return refuse();
    QByteArray checked(data.size()+1,0);qint64 read=0;
    while(read<checked.size()) {const auto n=::read(file.value,checked.data()+read,size_t(checked.size()-read));if(n<0 && errno==EINTR)continue;if(n<0)return refuse();if(!n)break;read+=n;}
    checked.resize(int(read));struct stat verified{},named{},namedFolder{},newBase{};Fd currentRoot(directory(root));
    if(checked!=data || ::fstat(file.value,&verified)!=0 || !same(created,verified) || verified.st_size!=data.size()
       || (verified.st_mode&0777)!=0600 || ::fstatat(dir.value,name.constData(),&named,AT_SYMLINK_NOFOLLOW)!=0 || !same(named,created)
       || ::fstatat(parent.value,"failure-reports-v1",&namedFolder,AT_SYMLINK_NOFOLLOW)!=0 || !same(namedFolder,folder) || namedFolder.st_uid!=::geteuid() || (namedFolder.st_mode&0077)
       || currentRoot.value<0 || ::fstat(currentRoot.value,&newBase)!=0 || !same(newBase,base) || !ownerControlled(newBase) || ::fsync(dir.value)!=0)return refuse();
    return {{"ok",true},{"exported",true},{"sent",false},{"bytes",data.size()},{"sha256",digest(data)},{"fileName",QString::fromLatin1(name)}};
}
#endif
QVariantMap appDataStorage(const QString& root) {
#ifdef Q_OS_UNIX
    // Use the opened private directory, so a path alias/replacement cannot
    // substitute another filesystem. This observes capacity, not a failure cause.
    Fd fd(directory(root));struct stat owner{};struct statvfs storage{};
    if(fd.value>=0 && ::fstat(fd.value,&owner)==0 && ownerControlled(owner)
       && ::fstatvfs(fd.value,&storage)==0) {
        constexpr quint64 maxJsonInteger=9007199254740991ULL;
        const quint64 unit=storage.f_frsize,blocks=storage.f_blocks,available=storage.f_bavail;
        if(unit && blocks && blocks<=maxJsonInteger/unit && available<=blocks) {
            return {{"status","measured"},{"scope","app-data-volume"},{"method","fstatvfs"},
                {"totalBytes",qint64(blocks*unit)},{"availableBytes",qint64(available*unit)},
                {"observedAt",QDateTime::currentDateTimeUtc().toString(QStringLiteral("yyyy-MM-ddTHH:mm:ssZ"))}};
        }
    }
#else
    Q_UNUSED(root);
#endif
    return {{"status","unavailable"}};
}
}
namespace library {
FailureReports::FailureReports(const QString& root,QObject* parent)
    :FailureReports(root,failureDocumentPicker(),parent) {}
FailureReports::FailureReports(const QString& root,DocumentPicker picker,QObject* parent)
    :QObject(parent),m_root(root),m_documentPicker(std::move(picker)) {}
FailureReports::~FailureReports() {if(m_documentWorker)m_documentWorker->requestInterruption();}
QVariantMap FailureReports::capabilities() const {
    return {{"schemaVersion",1},{"privatePreview",true},{"maxBytes",8192},{"sendAvailable",false},
        {"documentCopyAvailable",bool(m_documentPicker)},
#ifdef Q_OS_UNIX
        {"exportAvailable",true}
#else
        {"exportAvailable",false}
#endif
    };
}
void FailureReports::observeSaveCopies(const QString& edition,const QString& checkpoint,const QString& index,const QVariantMap& result) {
    // Any newer result invalidates an older preview, including success/cancellation.
    resetObservation();
    if(result.value("ok").toBool() || !editionId(edition) || (!checkpoint.isEmpty() && (!hex(checkpoint,32)||!hex(index,64)))
       || (checkpoint.isEmpty() && !index.isEmpty()))return;
    const QString error=result.value("error").toString();QString code,statement,hint;
    if(error=="storage_unavailable" && result.value("storageCheck")=="shared_permissions"
       && (result.value("storageStage")=="copy-directory" || result.value("storageStage")=="copy-index")) {
        const bool folder=result.value("storageStage")=="copy-directory";
        code=folder?"copy-directory-owner-check-failed":"copy-index-owner-check-failed";
        statement=folder?"The copied-save folder did not pass the reader's owner-only permissions check.":"The copied-save index did not pass the reader's owner-only permissions check.";
        hint="Review the observed file-access check without granting new permissions or changing saves automatically.";
    } else if(QStringList{"storage_unavailable","bundle_incomplete","invalid_index","index_unavailable"}.contains(error)) {
        code="copy-history-unavailable";statement="The copied-save history reader reported unavailable.";
        hint="Keep the copied history and current progress. Review the reader result without restoring or resetting saves.";
    } else if(error=="history_changed" || error=="index_changed") {
        code="copy-history-changed";statement="The copied-save history changed before the requested check completed.";
        hint="Reopen copied history before checking again. Keep all current copies and progress.";
    } else if(QStringList{"checksum_mismatch","copy_unavailable_or_changed","copy_not_found"}.contains(error)) {
        code="copy-archive-unverified";statement="The requested copied-save archive could not be verified.";
        hint="Keep the archive and current progress. This result does not authorize loading or replacing a save.";
    } else return;
    const QString recipe=checkpoint.isEmpty()?QStringLiteral("nova.copy.open.v1"):QStringLiteral("nova.copy.check.v1:")+checkpoint+":"+index;
    m_scope="save-copies";m_checkpoint=checkpoint;m_index=index;
    retain(edition,recipe,"native-save-copies-observation",code,statement,hint);
}
void FailureReports::resetObservation() {
    m_bytes.clear();m_ticket.clear();m_editionHash.clear();m_checkpoint.clear();m_index.clear();m_scope.clear();
    m_themeSelection.clear();
    m_copyToken.clear();m_copyName.clear();m_copySha.clear();
    if(m_documentWorker)m_documentWorker->requestInterruption();
    m_revision=m_revision==2147483647?0:m_revision+1;emit observationChanged();
}
void FailureReports::bindThemeLoader(QObject* loader) {
    if(m_themeLoader!=loader && m_scope=="theme-load")resetObservation();
    m_themeLoader=loader;
    beginThemeLoad();
}
void FailureReports::beginThemeLoad() {
    if(m_scope=="theme-load")resetObservation();
    m_themeDiagnostics.clear();m_themeDiagnosticsTruncated=false;
    m_diagnosticSelection=m_themeLoader?m_themeLoader->property("apiThemePath").toUrl().adjusted(QUrl::NormalizePathSegments).toString(QUrl::FullyEncoded):QString();
    m_collectThemeDiagnostics=!m_diagnosticSelection.isEmpty();
}
void FailureReports::observeThemeWarnings(const QList<QQmlError>& errors) {
    if(!m_collectThemeDiagnostics || !m_themeLoader)return;
    const auto selected=m_themeLoader->property("apiThemePath").toUrl().adjusted(QUrl::NormalizePathSegments);
    if(selected.toString(QUrl::FullyEncoded)!=m_diagnosticSelection)return;
    // The engine may emit before Loader.status becomes Error. Stage only this
    // selection's diagnostics; capture still requires the native Error boundary.
    for(const auto& error:errors) {
        if(error.url().adjusted(QUrl::NormalizePathSegments)!=selected)continue;
        const auto text=error.description();QString code=QStringLiteral("qml-error-unclassified");
        if(text.size()<=4096) {
            if(text.startsWith("Required property ") && text.endsWith(" was not initialized"))code="required-property-uninitialized";
            else if(text.startsWith("Expected token ") || text.startsWith("Unexpected token "))code="qml-syntax-error";
            else if(text.endsWith(" is not a type"))code="qml-type-unavailable";
            else if(text.startsWith("TypeError:"))code="javascript-type-error";
            else if(text.startsWith("ReferenceError:"))code="javascript-reference-error";
        }
        const QVariantMap entry{{"code",code},{"line",qBound(0,error.line(),1000000)},{"column",qBound(0,error.column(),10000)}};
        if(m_themeDiagnostics.contains(entry))continue;
        if(m_themeDiagnostics.size()==8){m_themeDiagnosticsTruncated=true;continue;}
        m_themeDiagnostics.append(entry);
    }
}
bool FailureReports::captureThemeFailure() {
    if(!m_themeLoader)return false;
    const auto source=m_themeLoader->property("source").toUrl();
    const auto selected=m_themeLoader->property("apiThemePath").toUrl();
    // Qt clears source on construction failure, retaining the ready component.
    // Its current URL still binds this error to the selected theme, not fallback.
    const auto component=m_themeLoader->property("sourceComponent").value<QObject*>();
    const bool construction=source.isEmpty() && component && component->property("status").toInt()==1
        && component->property("url").toUrl().adjusted(QUrl::NormalizePathSegments)==selected.adjusted(QUrl::NormalizePathSegments);
    // QQmlLoader::Error is 3. Observe before the compiled fallback replaces it.
    if(m_themeLoader->property("status").toInt()!=3 || selected.isEmpty() || (source!=selected && !construction))return false;
    const bool current=m_diagnosticSelection==selected.adjusted(QUrl::NormalizePathSegments).toString(QUrl::FullyEncoded);
    const auto entries=current?m_themeDiagnostics:QVariantList();
    const QVariantMap evidence{
        {"configuration",QVariantMap{{"framework","Qt"},{"frameworkVersion",QString::fromLatin1(qVersion())},
            {"selectionKind",selected.isLocalFile()?"local-file":selected.scheme()=="qrc"?"bundled":"other"},
            {"loaderStatus","error"},{"failureStage",construction?"interface-creation":"theme-load"}}},
        {"errorLog",QVariantMap{{"status",entries.isEmpty()?"unavailable":"collected"},{"maxEntries",8},
            {"truncated",current && m_themeDiagnosticsTruncated},{"entries",entries}}},
        {"lastCloudPreflight",m_lastCloudPreflight.isEmpty()?QVariantMap{{"status","unavailable"}}:m_lastCloudPreflight},
        {"appDataStorage",appDataStorage(m_root)}};
    m_collectThemeDiagnostics=false;
    resetObservation();m_scope="theme-load";m_themeSelection=selected.toString(QUrl::FullyEncoded);
    retain("nova:launcher","nova.theme.load.v1:"+QUuid::createUuid().toString(QUuid::Id128),
        "native-theme-load-observation",construction?"selected-theme-construction-failed":"selected-theme-load-failed",
        construction?"The selected theme failed while creating its interface.":"The native launcher could not load the selected theme.",
        "Keep the selected theme and current progress. Review the failure or deliberately choose the built-in theme; no cause or repair is established.",evidence);
    return !m_bytes.isEmpty();
}
void FailureReports::clearThemeFailure() {
    if(m_themeLoader && m_themeLoader->property("status").toInt()==1
       && m_themeLoader->property("source").toUrl()==m_themeLoader->property("apiThemePath").toUrl()) {
        m_collectThemeDiagnostics=false;m_themeDiagnostics.clear();m_diagnosticSelection.clear();
    }
    if(m_scope!="theme-load" || !m_themeLoader)return;
    if(!themeFailureAvailable() || (m_themeLoader->property("status").toInt()==1
       && m_themeLoader->property("source").toUrl()==m_themeLoader->property("apiThemePath").toUrl()))resetObservation();
}
bool FailureReports::themeFailureAvailable() const {
    return m_scope=="theme-load" && !m_bytes.isEmpty() && m_themeLoader
        && m_themeLoader->property("apiThemePath").toUrl().toString(QUrl::FullyEncoded)==m_themeSelection;
}
QVariantMap FailureReports::previewThemeFailure() {
    if(!themeFailureAvailable())return failure("observation_unavailable");
    return makePreview();
}
void FailureReports::observeCloudPlay(const QString& edition,const QString& attempt,const QString& error) {
    resetObservation();
    m_lastCloudPreflight.clear();
    if(!editionId(edition) || !edition.startsWith("nova:cloud_") || !hex(attempt,32))return;
    QString code,statement,hint;
    if(error=="file_unavailable") {
        code="download-file-unverified";statement="A downloaded file could not pass the native identity check before opening.";
        hint="Keep the downloaded files and saves. Review the local copy before trying to open it again.";
    } else if(error=="snapshot_changed") {
        code="download-changed-before-open";statement="The downloaded file record or payload changed during the native opening check.";
        hint="Keep all current files and progress. Review the changed download before a fresh deliberate attempt.";
    } else if(error=="checksum_mismatch") {
        code="download-checksum-unverified";statement="A downloaded file did not pass its expected checksum before opening.";
        hint="Keep the download and current saves. Do not open or replace a save on the strength of this failed check.";
    } else if(error=="runtime_refused") {
        code="runtime-request-refused";statement="The platform launch adapter did not accept the verified-file request.";
        hint="Review the supported runtime and core installation. This refusal does not establish its cause or authorize a new installation.";
    } else return;
    m_lastCloudPreflight={{"status","observed-refusal"},{"code",code},{"editionSha256",digest(edition.toUtf8())},
        {"observedAt",QDateTime::currentDateTimeUtc().toString(QStringLiteral("yyyy-MM-ddTHH:mm:ssZ"))}};
    m_scope="cloud-play";m_checkpoint=attempt;
    retain(edition,"nova.cloud.play.v1:"+attempt,"native-cloud-play-observation",code,statement,hint);
}
void FailureReports::retain(const QString& edition,const QString& recipe,const QString& origin,
                            const QString& code,const QString& statement,const QString& hint,const QVariantMap& localEvidence) {
    const QString stamp=QDateTime::currentDateTimeUtc().toString(QStringLiteral("yyyy-MM-ddTHH:mm:ssZ"));
    const auto editionHash=digest(edition.toUtf8()),recipeHash=digest(recipe.toUtf8());
    const bool synthetic=QStandardPaths::isTestModeEnabled();
    const QJsonObject observed{{"editionSha256",editionHash},{"recipeSha256",recipeHash},{"sourceSha256",QJsonValue::Null},{"buildSha256",QJsonValue::Null},{"runtimeIdSha256",QJsonValue::Null},{"runtimeVersionSha256",QJsonValue::Null}};
    QJsonObject report{{"schemaVersion",2},{"kind","nova-structured-failure"},{"observedAt",stamp},{"editionSha256",editionHash},{"observedRecipeSha256",recipeHash},
        {"activeRecipeSha256",QJsonValue::Null},{"recipeScope","unlinked"},{"currentSetupVerified",false},{"stage","preflight"},{"source",origin},
        {"facts",QJsonArray{QJsonObject{{"code",code},{"method",synthetic?"test":"observed"},{"statement",statement}}}},
        {"hypotheses",QJsonArray{QJsonObject{{"code","unknown-cause"},{"status","unconfirmed"},{"statement","No cause is established."},{"basedOn",QJsonArray{code}}}}},
        {"recoveryHints",QJsonArray{"The declared edition, source, build or runtime context is changed or incomplete. This retained observation does not establish the current context.","This observation does not establish the current setup. Compare its declared recipe before applying any guidance.",hint}},
        {"discardedFieldCount",0},{"limits","No raw logs, attachments, config, ROMs, saves, credentials or commands. No repair or send was performed."},
        {"provenance",QJsonObject{{"observed",observed},{"active",QJsonValue::Null},{"contextScope","unlinked"},
            {"collection",QJsonObject{{"status","collected"},{"method",synthetic?"synthetic":"adapter"},{"collectedAt",stamp}}},{"authenticated",false}}}};
    if(!localEvidence.isEmpty()) {
        report["localEvidence"]=QJsonObject::fromVariantMap(localEvidence);
        report["limits"]="Only bounded error categories/positions, fixed configuration facts and app-data volume capacity. No raw log/config text, paths, attachments, ROMs, saves, credentials or commands. No repair or send was performed.";
    }
    const auto bytes=jsonBytes(report);if(bytes.size()>8192)return;
    m_bytes=bytes;m_editionHash=editionHash;
    m_revision=m_revision==2147483647?0:m_revision+1;emit observationChanged();
}
bool FailureReports::available(const QString& edition,const QString& checkpoint,const QString& index) const {
    return m_scope=="save-copies" && !m_bytes.isEmpty() && editionId(edition) && digest(edition.toUtf8())==m_editionHash && checkpoint==m_checkpoint && index==m_index;
}
QVariantMap FailureReports::preview(const QString& edition,const QString& checkpoint,const QString& index) {
    if(!available(edition,checkpoint,index))return failure("observation_unavailable");
    return makePreview();
}
bool FailureReports::cloudPlayAvailable(const QString& edition,const QString& attempt) const {
    return m_scope=="cloud-play" && !m_bytes.isEmpty() && editionId(edition) && digest(edition.toUtf8())==m_editionHash && attempt==m_checkpoint;
}
QVariantMap FailureReports::previewCloudPlay(const QString& edition,const QString& attempt) {
    if(!cloudPlayAvailable(edition,attempt))return failure("observation_unavailable");
    return makePreview();
}
QVariantMap FailureReports::makePreview() {
    m_ticket=QUuid::createUuid().toString(QUuid::Id128);
    return {{"ok",true},{"ticket",m_ticket},{"sha256",digest(m_bytes)},{"bytes",m_bytes.size()},{"text",QString::fromUtf8(m_bytes)},{"sent",false}};
}
void FailureReports::cancelPreview(const QString& ticket) {if(ticket==m_ticket)m_ticket.clear();}
QVariantMap FailureReports::exportPreview(const QString& ticket,const QString& sha) {
    if(m_scope=="theme-load" && !themeFailureAvailable())return failure("preview_changed");
    if(!hex(ticket,32) || ticket!=m_ticket || !hex(sha,64) || sha!=digest(m_bytes) || m_bytes.isEmpty())return failure("preview_changed");
    m_ticket.clear();
#ifdef Q_OS_UNIX
    auto result=writePrivate(m_root,m_bytes);
    if(result.value("ok").toBool() && m_documentPicker) {
        m_copyToken=QUuid::createUuid().toString(QUuid::Id128);
        m_copyName=result.value("fileName").toString();m_copySha=digest(m_bytes);
        result["copyToken"]=m_copyToken;
    }
    return result;
#else
    return failure("export_unavailable");
#endif
}
QVariantMap FailureReports::copyPrivateExport(const QString& token,const QString& sha) {
    if(m_scope=="theme-load" && !themeFailureAvailable())return failure("export_changed");
    if(!m_documentPicker)return failure("document_copy_unavailable");
    if(m_documentBusy)return failure("document_copy_busy");
    if(!hex(token,32) || token!=m_copyToken || !hex(sha,64) || sha!=m_copySha
       || m_bytes.isEmpty() || digest(m_bytes)!=sha)return failure("export_changed");
    const auto request=QUuid::createUuid().toString(QUuid::Id128);
    const QByteArray bytes=m_bytes;
    m_documentRequest=request;m_documentBusy=true;m_documentSelectionPending=true;emit documentCopyChanged();
    const QPointer<FailureReports> owner(this);
    const bool started=m_documentPicker(m_copyName,[owner,request,token,sha,bytes](DocumentTarget target,const QString& status) {
        auto* app=QCoreApplication::instance();if(!app)return;
        // Android's result may arrive on its UI thread. Only inspect the report
        // object's lifetime/current approval and write on its Qt GUI thread.
        QMetaObject::invokeMethod(app,[owner,request,token,sha,bytes,status,target] {
            if(!owner || owner->m_documentRequest!=request || !owner->m_documentSelectionPending)return;
            owner->m_documentSelectionPending=false;
            QVariantMap result;
            if(token!=owner->m_copyToken || sha!=owner->m_copySha || digest(owner->m_bytes)!=sha)
                result={{"ok",false},{"copied",false},{"error","export_changed"}};
            else if(status=="cancelled")result={{"ok",false},{"copied",false},{"cancelled",true}};
            else if(status=="chooser_unavailable")result={{"ok",false},{"copied",false},{"error","chooser_unavailable"}};
            else if(!status.isEmpty() || !target)result={{"ok",false},{"copied",false},{"error","document_unavailable"}};
            else {
                // A document provider can be slow. Keep its I/O off the GUI
                // thread; Back/navigation and new observations remain usable.
                auto* worker=new DocumentThread(target,bytes);owner->m_documentWorker=worker;
                QObject::connect(worker,&QThread::finished,owner.data(),[owner,worker,request,token,sha] {
                    if(!owner)return;
                    owner->m_documentWorker=nullptr;
                    auto result=worker->result;
                    if(owner->m_copyToken!=token || owner->m_copySha!=sha)
                        result={{"ok",false},{"copied",false},{"error","export_changed"}};
                    owner->finishDocumentCopy(request,result);
                });
                QObject::connect(worker,&QThread::finished,worker,&QObject::deleteLater);
                worker->start();return;
            }
            owner->finishDocumentCopy(request,result);
        },Qt::QueuedConnection);
    });
    if(!started) {
        m_documentRequest.clear();m_documentBusy=false;m_documentSelectionPending=false;emit documentCopyChanged();
        return failure("document_copy_unavailable");
    }
    return {{"ok",true},{"pending",true},{"request",request}};
}
void FailureReports::finishDocumentCopy(const QString& request,const QVariantMap& result) {
    if(m_documentRequest!=request)return;
    auto receipt=result;
    receipt["message"]=result.value("ok").toBool() && result.value("copied").toBool()
        ?"Copied to the chosen document. Its provider controls storage and sync."
        :result.value("cancelled").toBool()?"Copy cancelled. The private report was kept."
        :result.value("error")=="chooser_unavailable"?"The document chooser is unavailable. The private report was kept."
        :result.value("error")=="export_changed"?"The report changed. The chosen document may be empty or incomplete. The private report was kept."
        :"The document copy could not be verified. The chosen document may be incomplete. The private report was kept.";
    m_documentRequest.clear();m_documentBusy=false;m_documentSelectionPending=false;
    emit documentCopyChanged();emit documentCopyFinished(request,receipt);
}
}
