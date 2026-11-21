#include "SaveCopies.h"
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
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QCryptographicHash>
class Driver:public QObject {
    Q_OBJECT
public:
    QQuickWindow* window=nullptr;QString store;
    Q_INVOKABLE bool key(int key,bool down=true){QKeyEvent e(down?QEvent::KeyPress:QEvent::KeyRelease,key,Qt::NoModifier);QGuiApplication::sendEvent(window,&e);return e.isAccepted();}
    Q_INVOKABLE void damage(bool remove){for(const auto& name:QDir(store+"/archives").entryList({"*.nvs"},QDir::Files)){QFile f(store+"/archives/"+name);if(remove)f.remove();else if(f.open(QIODevice::ReadWrite)){f.write("x",1);f.close();}}}
    Q_INVOKABLE void damagePicture(const QString& mode){
        if(mode=="decoder"){
            QFile indexFile(store+"/catalogue.json");if(!indexFile.open(QIODevice::ReadOnly))return;auto index=QJsonDocument::fromJson(indexFile.readAll()).object();indexFile.close();auto rows=index["entries"].toArray();
            for(int i=0;i<rows.size();++i){auto row=rows[i].toObject();auto meta=row["picture"].toObject();auto path=store+"/pictures/"+meta["sha256"].toString()+".png";QFile old(path);if(!old.open(QIODevice::ReadOnly))continue;auto bytes=old.readAll();old.close();if(bytes.size()>45)bytes[45]=char(bytes[45]^7);auto hash=QString::fromLatin1(QCryptographicHash::hash(bytes,QCryptographicHash::Sha256).toHex());QFile target(store+"/pictures/"+hash+".png");if(!target.open(QIODevice::WriteOnly))continue;target.setPermissions(QFile::ReadOwner|QFile::WriteOwner);target.write(bytes);target.close();meta["sha256"]=hash;row["picture"]=meta;rows[i]=row;}
            index["entries"]=rows;if(indexFile.open(QIODevice::WriteOnly|QIODevice::Truncate))indexFile.write(QJsonDocument(index).toJson(QJsonDocument::Compact));return;
        }
        if(mode=="stale"){
            QFile f(store+"/catalogue.json");if(!f.open(QIODevice::ReadOnly))return;auto index=QJsonDocument::fromJson(f.readAll()).object();f.close();
            auto rows=index["entries"].toArray();auto row=rows[0].toObject();row["name"]="Changed after listing";rows[0]=row;index["entries"]=rows;
            if(f.open(QIODevice::WriteOnly|QIODevice::Truncate))f.write(QJsonDocument(index).toJson(QJsonDocument::Compact));return;
        }
        for(const auto& name:QDir(store+"/pictures").entryList({"*.png"},QDir::Files)){
            QFile f(store+"/pictures/"+name);
            if(mode=="missing")f.remove();
            else if(mode=="corrupt" && f.open(QIODevice::ReadWrite)){f.write("x",1);f.close();}
            else if(mode=="shared")f.setPermissions(QFile::ReadOwner|QFile::WriteOwner|QFile::ReadGroup);
            else if(mode=="link"){auto path=f.fileName();f.rename(path+".kept");QFile::link(path+".kept",path);}
        }
    }
};
class Partial:public QObject{Q_OBJECT public:Q_INVOKABLE QVariantMap capabilities()const{return {{"schemaVersion",1}};}};
class Legacy:public QObject{
    Q_OBJECT
public:
    library::SaveCopies* reader;
    explicit Legacy(library::SaveCopies* value):reader(value){connect(reader,&library::SaveCopies::reviewFinished,this,&Legacy::reviewFinished);}
    Q_INVOKABLE QVariantMap capabilities()const{auto c=reader->capabilities();c.remove("reviewSnapshotVersion");return c;}
    Q_INVOKABLE QVariantMap openEdition(const QString& id)const{return reader->openEdition(id);}
    Q_INVOKABLE QVariantMap review(const QString& edition,const QString& id){return reader->review(edition,id);}
    Q_INVOKABLE void cancelReview(){reader->cancelReview();}
signals:
    void reviewFinished(const QString& token,const QVariantMap& result);
};
int main(int argc,char** argv){
    QGuiApplication app(argc,argv);QCommandLineParser p;p.addOptions({{"qml","Harness","path"},{"store","Synthetic private bundle","path"},{"output","Evidence folder","path"},{"scenario","Scenario","name","flow"},{"width","Width","pixels","1280"},{"height","Height","pixels","960"},{"bridge","model/absent/partial","kind","model"},{"light","Light"},{"large","Large text"}});p.process(app);
    QDir().mkpath(p.value("output"));QQmlApplicationEngine engine;library::SaveCopies copies(p.value("store"),&engine);Driver driver;driver.store=p.value("store");Partial partial;Legacy legacy(&copies);
    auto* context=engine.rootContext();
    if(p.value("bridge")=="model")context->setContextProperty("saveCopies",&copies);
    if(p.value("bridge")=="partial")context->setContextProperty("saveCopies",&partial);
    if(p.value("bridge")=="legacy")context->setContextProperty("saveCopies",&legacy);
    context->setContextProperty("driver",&driver);context->setContextProperty("fixtureOutput",p.value("output"));context->setContextProperty("fixtureScenario",p.value("scenario"));context->setContextProperty("fixtureLight",p.isSet("light"));context->setContextProperty("fixtureLarge",p.isSet("large"));
    QObject::connect(&engine,&QQmlApplicationEngine::warnings,&app,[](const QList<QQmlError>& errors){for(const auto& e:errors)fprintf(stderr,"QML_WARNING %s\n",qPrintable(e.toString()));});
    engine.load(QUrl::fromLocalFile(p.value("qml")));if(engine.rootObjects().isEmpty())return 3;
    driver.window=qobject_cast<QQuickWindow*>(engine.rootObjects().first());driver.window->resize(p.value("width").toInt(),p.value("height").toInt());QFocusEvent focus(QEvent::FocusIn,Qt::ActiveWindowFocusReason);QGuiApplication::sendEvent(driver.window,&focus);return app.exec();
}
#include "main.moc"
