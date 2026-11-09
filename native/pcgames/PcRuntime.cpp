// SPDX-License-Identifier: GPL-3.0-or-later
#include "PcRuntime.h"
#include <QRegularExpression>
#ifdef Q_OS_ANDROID
#include <QAndroidJniObject>
#include <QAndroidJniEnvironment>
#include <QGuiApplication>
#include <QtAndroid>
#include <QJsonDocument>
#endif
namespace library {
namespace {
struct Backend {const char* id;const char* name;const char* package;const char* version;};
const Backend backends[]={{"droiddeck","DroidDeck","com.droiddeck.launcher","0.7.0"},{"gamenative","GameNative","app.gamenative","1.4.0"}};
QVariantMap result(bool accepted,const QString& code,const QString& message) {return {{"accepted",accepted},{"code",code},{"message",message}};}
PcRuntimePlatform platform() {
    PcRuntimePlatform p;
#ifdef Q_OS_ANDROID
    p.foreground=[] {return QGuiApplication::applicationState()==Qt::ApplicationActive;};
    p.inspect=[] {
        QVariantList records;
        QtAndroid::runOnAndroidThreadSync([&records]{
            const auto value=QAndroidJniObject::callStaticObjectMethod("org/pegasus_frontend/android/PcRuntimeBridge","inspect","(Landroid/app/Activity;)Ljava/lang/String;",QtAndroid::androidActivity().object());
            QAndroidJniEnvironment env;if(env->ExceptionCheck()){env->ExceptionClear();return;}
            records=QJsonDocument::fromJson(value.toString().toUtf8()).toVariant().toList();
        });
        return records;
    };
    p.dispatch=[](const QString& runtime,int appId,const QString& version) {
        QVariantMap response;
        QtAndroid::runOnAndroidThreadSync([&]{
            const auto id=QAndroidJniObject::fromString(runtime),expected=QAndroidJniObject::fromString(version);
            const auto value=QAndroidJniObject::callStaticObjectMethod("org/pegasus_frontend/android/PcRuntimeBridge","openGame","(Landroid/app/Activity;Ljava/lang/String;ILjava/lang/String;)Ljava/lang/String;",QtAndroid::androidActivity().object(),id.object<jstring>(),jint(appId),expected.object<jstring>());
            QAndroidJniEnvironment env;if(env->ExceptionCheck()){env->ExceptionClear();return;}
            response=QJsonDocument::fromJson(value.toString().toUtf8()).toVariant().toMap();
        });
        return response;
    };
#endif
    return p;
}
}
PcRuntime::PcRuntime(QObject* parent):PcRuntime(platform(),parent) {}
PcRuntime::PcRuntime(const PcRuntimePlatform& p,QObject* parent):QObject(parent),m_platform(p){refresh();}
int PcRuntime::steamId(const QString& editionId) {
    static const QRegularExpression id("\\Asteam:([1-9][0-9]{0,9})\\z");const auto match=id.match(editionId);
    if(!match.hasMatch())return 0;bool ok=false;const int value=match.captured(1).toInt(&ok);return ok?value:0;
}
void PcRuntime::refresh() {
    const auto observed=m_platform.inspect?m_platform.inspect():QVariantList();QVariantList states;
    for(const auto& backend:backends) {
        QVariantMap item;int count=0;
        for(const auto& raw:observed)if(raw.toMap()["id"].toString()==backend.id){item=raw.toMap();++count;}
        auto version=item["version"].toString();
        if(version.size()>80 || !QRegularExpression("\\A[A-Za-z0-9.+_-]*\\z").match(version).hasMatch())version.clear();
        const bool available=count==1 && item["available"].type()==QVariant::Bool && item["available"].toBool();
        const bool supported=available && version==backend.version;
        states.append(QVariantMap{{"id",backend.id},{"name",backend.name},{"packageName",backend.package},{"version",version},
            {"available",available},{"supported",supported},{"reason",!available?"App unavailable or access could not be checked.":!supported?"This app version needs an adapter check.":"Launch protocol checked in source; game installation and boot are not checked."}});
    }
    m_runtimes=states;emit changed();
}
QVariantMap PcRuntime::openGame(const QString& editionId,const QString& runtimeId,const QString& expectedVersion) {
    const int appId=steamId(editionId);
    if(!appId)return result(false,"invalid-edition","This action requires an exact Steam edition ID.");
    bool known=false;for(const auto& b:backends)if(runtimeId==b.id)known=true;
    if(!known)return result(false,"unknown-runtime","This runtime is not supported by the adapter.");
    if(!m_platform.foreground || !m_platform.foreground())return result(false,"not-foreground","Return to Library before requesting a game.");
    refresh();QVariantMap state;for(const auto& raw:m_runtimes)if(raw.toMap()["id"]==runtimeId)state=raw.toMap();
    if(!state["available"].toBool())return result(false,"unavailable","The selected runtime is unavailable. No other runtime was opened.");
    if(expectedVersion.isEmpty() || state["version"]!=expectedVersion)return result(false,"version-changed","The runtime version changed. Review PC runtime before trying again.");
    if(!state["supported"].toBool())return result(false,"unsupported-version","This version needs a checked launch adapter.");
    if(!m_platform.foreground() || !m_platform.dispatch)return result(false,"not-foreground","Return to Library before requesting a game.");
    const auto response=m_platform.dispatch(runtimeId,appId,expectedVersion);
    if(response["accepted"].type()==QVariant::Bool && response["accepted"].toBool())
        return result(true,"dispatched","Request handed to "+state["name"].toString()+". Game boot is not confirmed.");
    const auto code=response["code"].toString();
    if(code=="version-changed")return result(false,code,"The runtime version changed before dispatch. Review it and try again.");
    if(code=="not-foreground")return result(false,code,"Library left the foreground. Nothing was requested.");
    return result(false,"dispatch-failed","The runtime could not accept this request. No other runtime was opened.");
}
}
