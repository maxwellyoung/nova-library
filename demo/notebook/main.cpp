// Isolated full-theme fixture. All catalogue/input data is synthetic; the notebook
// uses the actual native storage on disk and can be reopened by a fresh process.
#include "StoppingNotes.h"
#include <QGuiApplication>
#include <QCommandLineParser>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickWindow>
#include <QKeyEvent>
#include <QFocusEvent>
#include <QImage>
#include <QDir>
#include <QUrl>
#include <QTest>
#include <QQuickItem>
#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
class Driver : public QObject {
    Q_OBJECT
public:
    QString root;
    QQuickWindow* window=nullptr;
    Q_INVOKABLE bool key(int key,bool down=true) {
        QKeyEvent e(down?QEvent::KeyPress:QEvent::KeyRelease,key,Qt::NoModifier);
        QGuiApplication::sendEvent(window,&e);return e.isAccepted();
    }
    Q_INVOKABLE void typeText(const QString& text) {
        for(const auto c:text){QKeyEvent e(QEvent::KeyPress,0,Qt::NoModifier,QString(c));QGuiApplication::sendEvent(window,&e);}
    }
    QString document(const QString& id) const {return root+"/"+QString::fromLatin1(QCryptographicHash::hash(id.toUtf8(),QCryptographicHash::Sha256).toHex())+"/notebook.json";}
    Q_INVOKABLE QString metadataHash(const QString& id) {QFile f(document(id));if(!f.open(QIODevice::ReadOnly))return {};return QString::fromLatin1(QCryptographicHash::hash(f.readAll(),QCryptographicHash::Sha256).toHex());}
    Q_INVOKABLE bool allowWrites(const QString& id,bool allowed) {return QFile::setPermissions(QFileInfo(document(id)).absolutePath(),QFileDevice::ReadOwner|QFileDevice::ExeOwner|(allowed?QFileDevice::WriteOwner:QFileDevice::Permissions()));}
    Q_INVOKABLE void tap(QObject* object){auto* item=qobject_cast<QQuickItem*>(object);if(!item)return;const auto p=item->mapToScene(QPointF(item->width()/2,item->height()/2));QTest::mouseClick(window,Qt::LeftButton,Qt::NoModifier,p.toPoint());}
    Q_INVOKABLE bool otherWriter(const QString& id) {
        library::StoppingNotes other(root);auto r=other.openEdition(id);if(!r.value("ok").toBool())return false;
        return other.createNote(id,{{"text","Another writer's saved note"},{"imageId",""},{"annotations",QVariantList()}},r.value("notebook").toMap().value("revision")).value("ok").toBool();
    }
};
int main(int argc,char** argv){
    QGuiApplication app(argc,argv);QCommandLineParser p;
    p.addOptions({{"qml","Harness file","file"},{"store","Private test store","dir"},{"output","Output folder","dir"},{"scenario","Scenario","name"},{"width","Width","px","1280"},{"height","Height","px","960"},{"light","Light theme"},{"large","Large text"},{"font","Font","file"},{"bridge","model or absent","type","model"}});p.process(app);
    QDir().mkpath(p.value("output"));
    const auto screenshots=p.value("output")+"/screenshots";QDir().mkpath(screenshots);
    library::StoppingNotes store(p.value("store"),nullptr,screenshots);Driver driver;driver.root=p.value("store");
    const auto image=screenshots+"/synthetic-original.png";QImage im(640,400,QImage::Format_RGB32);im.fill(QColor("#38586b"));if(!im.save(image,"PNG"))return 4;
    QQmlApplicationEngine engine;auto* c=engine.rootContext();
    if(p.value("bridge")!="absent")c->setContextProperty("stoppingNotes",&store);
    c->setContextProperty("fixtureImageUrl",QUrl::fromLocalFile(image).toString());c->setContextProperty("fixtureOutput",p.value("output"));
    c->setContextProperty("fixtureScenario",p.value("scenario"));c->setContextProperty("fixtureLight",p.isSet("light"));c->setContextProperty("fixtureLarge",p.isSet("large"));
    c->setContextProperty("fixtureFont",QUrl::fromLocalFile(p.value("font")));c->setContextProperty("driver",&driver);
    QObject::connect(&engine,&QQmlApplicationEngine::warnings,&app,[](const QList<QQmlError>& es){for(const auto& e:es)fprintf(stderr,"QML_WARNING %s\n",qPrintable(e.toString()));});
    engine.load(QUrl::fromLocalFile(p.value("qml")));if(engine.rootObjects().isEmpty())return 3;
    driver.window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());
    driver.window->resize(p.value("width").toInt(),p.value("height").toInt());
    QFocusEvent in(QEvent::FocusIn,Qt::ActiveWindowFocusReason);QCoreApplication::sendEvent(driver.window,&in);
    return app.exec();
}
#include "main.moc"
