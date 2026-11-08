#include "ControllerCheck.h"
#include "QtGamepadObserver.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QTimer>
#include <QTextStream>
#include <QFileInfo>

int main(int argc,char** argv) {
    QGuiApplication app(argc,argv);
    app.setApplicationName("Nova controller check fixture");
    const bool injected=app.arguments().contains("--fixture");
    ControllerCheck model(injected);
    QtGamepadObserver observer(&model,!injected);
    if (injected) {
        model.connectDevice(7); model.button(7,"select",true); model.button(7,"south",true);
        model.axis(7,"left-x",-0.75); model.axis(7,"left-y",0.04);
        model.axis(7,"right-x",0.5); model.axis(7,"right-y",1);
        model.trigger(7,"l2",0.23); model.trigger(7,"r2",0.81); model.systemBack(true);
    }
    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("controllerCheck",&model);
    bool qmlErrors=false;
    QObject::connect(&engine,&QQmlApplicationEngine::warnings,&app,[&](const QList<QQmlError>&) { qmlErrors=true; });
    engine.load(QUrl("qrc:/ControllerCheckFixture.qml"));
    if (engine.rootObjects().isEmpty()) return 1;
    if (app.arguments().contains("--smoke")) QTimer::singleShot(300,&app,[&]() {
        auto* window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
        const auto image=window ? window->grabWindow() : QImage();
        bool imageOk=!image.isNull() && !qmlErrors && (!injected || engine.rootObjects().first()->property("renderedDeviceCount").toInt()==1);
        const auto imageAt=app.arguments().indexOf("--image");
        if (imageAt>=0 && imageAt+1<app.arguments().size()) {
            const auto path=app.arguments().at(imageAt+1);
            imageOk=imageOk && !QFileInfo::exists(path) && image.save(path);
        }
        QTextStream(stdout)<<"qml-loaded=true rendered="<<(imageOk?"true":"false")<<" method="<<model.state().value("method").toString()<<Qt::endl;
        app.exit(imageOk?0:2);
    });
    return app.exec();
}
