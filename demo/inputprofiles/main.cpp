#include "SaveCopies.h"
#include "Memory.h"
#include <QLockFile>
#include <memory>
namespace paths { QString writableConfigDir(){return {};} }
#include <QGuiApplication>
#include <QCommandLineParser>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QQuickItem>
#include <QKeyEvent>
#include <QFocusEvent>
#include <QFile>
#include <QDir>
#include <QTest>
class Driver:public QObject {
    Q_OBJECT
public:
    QQuickWindow* window=nullptr;QString store;
    QString memoryDir,output;std::unique_ptr<QLockFile> preferenceLock;
    Q_INVOKABLE void lockPreferences(bool locked){
        if(!locked){preferenceLock.reset();return;}
        preferenceLock.reset(new QLockFile(memoryDir+"/nova.json.nova-lock"));
        if(!preferenceLock->tryLock(0))qFatal("Synthetic lock failed");
    }
    Q_INVOKABLE QString preferenceBytes(){QFile f(memoryDir+"/nova.json");if(!f.open(QIODevice::ReadOnly))return {};return QString::fromUtf8(f.readAll());}
    Q_INVOKABLE bool retainCommit(){return QFile::copy(memoryDir+"/nova.json",output+"/committed.json");}
    Q_INVOKABLE void externalPreferences(){QFile f(memoryDir+"/nova.json");if(!f.open(QIODevice::WriteOnly))qFatal("Synthetic edit failed");f.write("{\"external\":1}");}
    Q_INVOKABLE void tap(int x,int y){QTest::mouseClick(window,Qt::LeftButton,Qt::NoModifier,QPoint(x,y));}
    Q_INVOKABLE bool key(int key,bool down=true){QKeyEvent e(down?QEvent::KeyPress:QEvent::KeyRelease,key,Qt::NoModifier);QGuiApplication::sendEvent(window,&e);return e.isAccepted();}
    Q_INVOKABLE void damage(bool remove){for(const auto& name:QDir(store+"/archives").entryList({"*.nvs"},QDir::Files)){QFile f(store+"/archives/"+name);if(remove)f.remove();else if(f.open(QIODevice::ReadWrite)){f.write("x",1);f.close();}}}
};
class Partial:public QObject{Q_OBJECT public:Q_INVOKABLE QVariantMap capabilities()const{return {{"schemaVersion",1}};}};
int main(int argc,char** argv){
    QGuiApplication app(argc,argv);QCommandLineParser p;p.addOptions({{"memory-dir","Private synthetic preferences","path"},{"qml","Harness","path"},{"store","Synthetic private bundle","path"},{"output","Evidence folder","path"},{"scenario","Scenario","name","flow"},{"width","Width","pixels","1280"},{"height","Height","pixels","960"},{"bridge","model/absent/partial","kind","model"},{"light","Light"},{"large","Large text"}});p.process(app);
    QDir().mkpath(p.value("output"));library::SaveCopies copies(p.value("store"));Driver driver;driver.store=p.value("store");driver.output=p.value("output");Partial partial;
    QDir().mkpath(p.value("memory-dir"));model::Memory memory(p.value("memory-dir"));memory.changeTheme("/themes/nova/");driver.memoryDir=p.value("memory-dir");
    QQmlApplicationEngine engine;auto* context=engine.rootContext();
    if(p.value("bridge")=="model")context->setContextProperty("saveCopies",&copies);
    if(p.value("bridge")=="partial")context->setContextProperty("saveCopies",&partial);
    context->setContextProperty("checkedMemory",&memory);
    context->setContextProperty("driver",&driver);context->setContextProperty("fixtureOutput",p.value("output"));context->setContextProperty("fixtureScenario",p.value("scenario"));context->setContextProperty("fixtureLight",p.isSet("light"));context->setContextProperty("fixtureLarge",p.isSet("large"));
    QObject::connect(&engine,&QQmlApplicationEngine::warnings,&app,[](const QList<QQmlError>& errors){for(const auto& e:errors)fprintf(stderr,"QML_WARNING %s\n",qPrintable(e.toString()));});
    engine.load(QUrl::fromLocalFile(p.value("qml")));if(engine.rootObjects().isEmpty())return 3;
    driver.window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());driver.window->resize(p.value("width").toInt(),p.value("height").toInt());QFocusEvent focus(QEvent::FocusIn,Qt::ActiveWindowFocusReason);QGuiApplication::sendEvent(driver.window,&focus);return app.exec();
}
#include "main.moc"
