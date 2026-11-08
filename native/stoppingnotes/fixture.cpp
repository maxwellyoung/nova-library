// SPDX-License-Identifier: GPL-3.0-or-later
#include "StoppingNotes.h"
#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QDir>
#include <QFileInfo>
#include <QImage>
#include <QUrl>
int main(int argc,char** argv){
    QGuiApplication app(argc,argv);const auto args=app.arguments();
    if(args.size()!=2 && (args.size()!=4 || (args[2]!="--smoke" && args[2]!="--reopen-smoke"))){qCritical("Usage: stopping-notes-fixture /private/new-store [--smoke|--reopen-smoke /private/capture.png]");return 2;}
    library::StoppingNotes store(args[1]);if(!store.capabilities().value("ok").toBool()){qCritical("Private fixture storage unavailable");return 2;}
    const bool smoke=args.size()==4&&args[2]=="--smoke",reopen=args.size()==4&&args[2]=="--reopen-smoke";const auto parent=QFileInfo(args[1]).absolutePath();const auto image=parent+"/synthetic-original.png";
    if(smoke){if(QFileInfo::exists(image)){qCritical("Synthetic image target already exists; choose a fresh private fixture directory");return 2;}QImage i(640,400,QImage::Format_RGB32);i.fill(QColor("#38586b"));if(!i.save(image,"PNG"))return 2;}
    QQmlApplicationEngine engine;engine.rootContext()->setContextProperty("stoppingNotes",&store);
    engine.rootContext()->setContextProperty("fixtureSmoke",smoke);
    engine.rootContext()->setContextProperty("fixtureReopen",reopen);
    engine.rootContext()->setContextProperty("fixtureImageUrl",QUrl::fromLocalFile(image).toString());
    engine.rootContext()->setContextProperty("fixtureExportUrl",QUrl::fromLocalFile(parent+"/explicit-private-export").toString());
    engine.rootContext()->setContextProperty("fixtureScreenshotPath",smoke||reopen?args[3]:QString());
    engine.load(QUrl("qrc:/stoppingnotes/StoppingNotes.qml"));if(engine.rootObjects().isEmpty())return 1;return app.exec();
}
