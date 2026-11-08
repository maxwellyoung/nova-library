#include "ControllerCheckHost.h"
#include "ControllerCheck.h"
#include "QtGamepadObserver.h"
#include <QCoreApplication>
#include <QStandardPaths>
#include <QSysInfo>
#ifdef Q_OS_ANDROID
#include <QtAndroidExtras/QAndroidJniObject>
#include <QtAndroidExtras/QtAndroid>
#endif

namespace controllercheck {
ControllerCheck* createForApplication(QObject* owner, bool attachNative) {
    auto* model=new ControllerCheck(false,owner);
    model->setActive(false);
    QVariantMap metadata{{"applicationName",QCoreApplication::applicationName()},
        {"applicationVersion",QCoreApplication::applicationVersion()},
        {"platform",QSysInfo::productType()},{"platformVersion",QSysInfo::productVersion()},
        {"inputBackend",QStringLiteral("QtGamepad")}};
#ifdef Q_OS_ANDROID
    const auto activity=QtAndroid::androidActivity();
    metadata["applicationId"]=activity.isValid() ? activity.callObjectMethod("getPackageName","()Ljava/lang/String;").toString() : QStringLiteral("unknown");
    metadata["androidModel"]=QAndroidJniObject::getStaticObjectField<jstring>("android/os/Build","MODEL").toString();
    metadata["androidApiLevel"]=QString::number(QAndroidJniObject::getStaticField<jint>("android/os/Build$VERSION","SDK_INT"));
#endif
    model->configureApplication(metadata,QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation));
    new QtGamepadObserver(model,attachNative);
    return model;
}
}
