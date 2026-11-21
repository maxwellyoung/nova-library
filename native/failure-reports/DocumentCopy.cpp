// SPDX-License-Identifier: GPL-3.0-or-later
#include "DocumentCopy.h"
#include <QCryptographicHash>
#ifdef Q_OS_UNIX
#include <sys/stat.h>
#include <unistd.h>
#include <cerrno>
#endif
#ifdef Q_OS_ANDROID
#include <QtAndroid>
#include <QAndroidJniEnvironment>
#include <QAndroidJniObject>
#include <QAndroidActivityResultReceiver>
#include <QCoreApplication>
#include <memory>
#include <mutex>
#endif

namespace library {
QVariantMap writeFailureDocument(int fd,const QByteArray& bytes,const std::function<bool()>& cancelled) {
    const auto refuse=[] { return QVariantMap{{"ok",false},{"copied",false},{"error","document_copy_unverified"}}; };
#ifdef Q_OS_UNIX
    struct stat initial{};
    // The create-document result must be a new empty seekable document. Never
    // truncate an unexpected existing target, and keep the private source.
    if(cancelled() || fd<0 || bytes.isEmpty() || bytes.size()>8192 || ::fstat(fd,&initial)!=0
       || !S_ISREG(initial.st_mode) || initial.st_size!=0 || ::lseek(fd,0,SEEK_SET)!=0)return refuse();
    qint64 done=0;
    while(done<bytes.size()) {
        if(cancelled())return refuse();
        const auto n=::write(fd,bytes.constData()+done,size_t(bytes.size()-done));
        if(n<0 && errno==EINTR)continue;
        if(n<=0)return refuse();
        done+=n;
    }
    if(cancelled() || ::fsync(fd)!=0 || ::lseek(fd,0,SEEK_SET)!=0)return refuse();
    QByteArray readBack(bytes.size()+1,0);qint64 count=0;
    while(count<readBack.size()) {
        if(cancelled())return refuse();
        const auto n=::read(fd,readBack.data()+count,size_t(readBack.size()-count));
        if(n<0 && errno==EINTR)continue;
        if(n<0)return refuse();
        if(n==0)break;
        count+=n;
    }
    readBack.resize(int(count));struct stat verified{};
    if(cancelled() || readBack!=bytes || ::fstat(fd,&verified)!=0 || verified.st_dev!=initial.st_dev
       || verified.st_ino!=initial.st_ino || verified.st_size!=bytes.size())return refuse();
    return {{"ok",true},{"copied",true},{"bytes",bytes.size()},
        {"sha256",QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex())},
        {"providerLocationUnverified",true}};
#else
    Q_UNUSED(fd);Q_UNUSED(bytes);Q_UNUSED(cancelled);
    return refuse();
#endif
}

#ifdef Q_OS_ANDROID
namespace {
struct PendingDocument {
    std::mutex mutex;
    DocumentReceiver receive;
};
DocumentReceiver takeReceiver(const std::weak_ptr<PendingDocument>& weak) {
    const auto pending=weak.lock();if(!pending)return {};
    std::lock_guard<std::mutex> lock(pending->mutex);
    auto result=std::move(pending->receive);pending->receive={};return result;
}
void selectedDocument(DocumentReceiver receive,int result,const QAndroidJniObject& data) {
    if(result!= -1){receive({},"cancelled");return;}
    if(!data.isValid()){receive({},"document_unavailable");return;}
    QAndroidJniEnvironment env;
    auto failed=[&] {if(!env->ExceptionCheck())return false;env->ExceptionClear();return true;};
    const auto uri=data.callObjectMethod("getData","()Landroid/net/Uri;");
    if(failed() || !uri.isValid()){receive({},"document_unavailable");return;}
    const auto scheme=uri.callObjectMethod("getScheme","()Ljava/lang/String;");
    if(failed() || scheme.toString()!="content"){receive({},"document_unavailable");return;}
    receive([uri](const QByteArray& bytes,const std::function<bool()>& cancelled) {
        const auto unavailable=[] {return QVariantMap{{"ok",false},{"copied",false},{"error","document_unavailable"}};};
        if(cancelled())return unavailable();
        QAndroidJniEnvironment env;
        auto failed=[&] {if(!env->ExceptionCheck())return false;env->ExceptionClear();return true;};
        const auto context=QtAndroid::androidContext();
        if(!context.isValid())return unavailable();
        const auto resolver=context.callObjectMethod("getContentResolver","()Landroid/content/ContentResolver;");
        if(failed() || !resolver.isValid())return unavailable();
        const auto mode=QAndroidJniObject::fromString("rw");
        const auto parcel=resolver.callObjectMethod("openFileDescriptor","(Landroid/net/Uri;Ljava/lang/String;)Landroid/os/ParcelFileDescriptor;",uri.object(),mode.object<jstring>());
        if(failed() || !parcel.isValid())return unavailable();
        const int descriptor=parcel.callMethod<jint>("getFd","()I");
        const bool descriptorFailed=failed();
        auto result=descriptorFailed?unavailable():writeFailureDocument(descriptor,bytes,cancelled);
        // The provider's descriptor stays alive through read-back and closes on
        // this worker too. No provider I/O blocks either UI thread.
        parcel.callMethod<void>("close","()V");
        if(failed())result=unavailable();
        return result;
    },{});
}
class DocumentResultReceiver : public QAndroidActivityResultReceiver {
public:
    explicit DocumentResultReceiver(std::weak_ptr<PendingDocument> pending):m_pending(std::move(pending)) {}
    void handleActivityResult(int,int result,const QAndroidJniObject& data) override {
        if(m_consumed)return;m_consumed=true;
        const auto receive=takeReceiver(m_pending);
        if(receive)selectedDocument(receive,result,data);
        retire();
    }
    void failedToStart() {
        if(m_consumed)return;m_consumed=true;
        const auto receive=takeReceiver(m_pending);if(receive)receive({},"chooser_unavailable");
        retire();
    }
private:
    void retire() {
        auto* app=QCoreApplication::instance();if(!app)return;
        // Qt holds its result-listener mutex while dispatching. Hop through the
        // Qt event loop, then queue deletion onto Android's UI thread after the
        // dispatch returns; never unregister inside the callback's locked stack.
        QMetaObject::invokeMethod(app,[this] {QtAndroid::runOnAndroidThread([this] {delete this;});},Qt::QueuedConnection);
    }
    std::weak_ptr<PendingDocument> m_pending;
    bool m_consumed=false;
};
}
#endif
DocumentPicker failureDocumentPicker() {
#ifdef Q_OS_ANDROID
    const auto pending=std::make_shared<PendingDocument>();
    return [pending](const QString& name,DocumentReceiver receive) {
        QAndroidJniEnvironment env;
        auto failed=[&] {if(!env->ExceptionCheck())return false;env->ExceptionClear();return true;};
        if(!QtAndroid::androidActivity().isValid())return false;
        const auto action=QAndroidJniObject::fromString("android.intent.action.CREATE_DOCUMENT");
        QAndroidJniObject intent("android/content/Intent","(Ljava/lang/String;)V",action.object<jstring>());
        if(failed() || !intent.isValid())return false;
        const auto category=QAndroidJniObject::fromString("android.intent.category.OPENABLE");
        const auto type=QAndroidJniObject::fromString("application/json");
        const auto title=QAndroidJniObject::fromString("android.intent.extra.TITLE");
        const auto filename=QAndroidJniObject::fromString(name);
        intent.callObjectMethod("addCategory","(Ljava/lang/String;)Landroid/content/Intent;",category.object<jstring>());
        if(failed())return false;
        intent.callObjectMethod("setType","(Ljava/lang/String;)Landroid/content/Intent;",type.object<jstring>());
        if(failed())return false;
        intent.callObjectMethod("putExtra","(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;",title.object<jstring>(),filename.object<jstring>());
        if(failed())return false;
        {
            std::lock_guard<std::mutex> lock(pending->mutex);
            if(pending->receive)return false;
            pending->receive=std::move(receive);
        }
        const std::weak_ptr<PendingDocument> weak=pending;
        QtAndroid::runOnAndroidThread([weak,intent] {
            const auto pending=weak.lock();if(!pending)return;
            auto* receiver=new DocumentResultReceiver(weak);
            QAndroidJniEnvironment env;
            if(!QtAndroid::androidActivity().isValid()){receiver->failedToStart();return;}
            // Launch directly: resolveActivity can hide a usable picker under
            // Android package visibility. Catch the actual JNI launch refusal.
            // A separate receiver gives this request its own global Qt code.
            QtAndroid::startActivity(intent,0,receiver);
            if(env->ExceptionCheck()){env->ExceptionClear();receiver->failedToStart();}
        });
        return true;
    };
#else
    return {};
#endif
}
}
