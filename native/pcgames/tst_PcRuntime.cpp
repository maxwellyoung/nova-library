// SPDX-License-Identifier: GPL-3.0-or-later
#include "PcRuntime.h"
#include <QtTest>
using namespace library;
class Tests:public QObject {
    Q_OBJECT
    QVariantList states{{QVariantMap{{"id","droiddeck"},{"available",true},{"version","0.7.0"}}},
                       {QVariantMap{{"id","gamenative"},{"available",true},{"version","1.4.0"}}}};
private slots:
    void init(){states={QVariantMap{{"id","droiddeck"},{"available",true},{"version","0.7.0"}},QVariantMap{{"id","gamenative"},{"available",true},{"version","1.4.0"}}};}
    void idBoundaries_data(){
        QTest::addColumn<QString>("id");QTest::addColumn<int>("expected");
        QTest::newRow("minimum")<<QString("steam:1")<<1;
        QTest::newRow("maximum")<<QString("steam:2147483647")<<2147483647;
        for(const auto& id:{"steam:0","steam:01","steam:-1","steam:+1","steam:1 "," steam:1","Steam:1","steam:1/2","steam:1?x=2","steam:2147483648","steam:99999999999","https://example.test","steam:1\n","demo:1","steam:1;sh"})QTest::newRow(id)<<QString(id)<<0;
    }
    void idBoundaries(){QFETCH(QString,id);QFETCH(int,expected);QCOMPARE(PcRuntime::steamId(id),expected);}
    void acceptedDispatchIsNotBootAndCarriesOnlyAllowedIdentity(){
        QString runtime,version;int app=0,calls=0;
        PcRuntime client(PcRuntimePlatform{[&]{return states;},[]{return true;},[&](const QString& r,int id,const QString& v){runtime=r;app=id;version=v;++calls;return QVariantMap{{"accepted",true},{"secret","never expose"}};}});
        auto r=client.openGame("steam:123","gamenative","1.4.0");QVERIFY(r["accepted"].toBool());QCOMPARE(r["code"].toString(),QString("dispatched"));
        QCOMPARE(runtime,QString("gamenative"));QCOMPARE(app,123);QCOMPARE(version,QString("1.4.0"));QCOMPARE(calls,1);
        QVERIFY(r["message"].toString().contains("boot is not confirmed"));QCOMPARE(r.size(),3);QVERIFY(!r.contains("secret"));
        r=client.openGame("steam:123","droiddeck","0.7.0");QVERIFY(r["accepted"].toBool());QCOMPARE(runtime,QString("droiddeck"));QCOMPARE(calls,2);
    }
    void refusalNeverFallsBackToAnotherBackend(){
        bool foreground=true;int calls=0;
        PcRuntime client(PcRuntimePlatform{[&]{return states;},[&]{return foreground;},[&](const QString&,int,const QString&){++calls;return QVariantMap{{"accepted",false},{"message","private platform details"}};}});
        auto r=client.openGame("steam:123","droiddeck","0.7.0");QVERIFY(!r["accepted"].toBool());QCOMPARE(calls,1);QVERIFY(!r["message"].toString().contains("private"));
        foreground=false;r=client.openGame("steam:123","gamenative","1.4.0");QCOMPARE(r["code"].toString(),QString("not-foreground"));QCOMPARE(calls,1);
        foreground=true;r=client.openGame("steam:123","other","1");QCOMPARE(r["code"].toString(),QString("unknown-runtime"));QCOMPARE(calls,1);
        client.openGame("steam:1/other","droiddeck","0.7.0");QCOMPARE(calls,1);
        states[0]=QVariantMap{{"id","droiddeck"},{"available",false},{"version","0.7.0"}};
        r=client.openGame("steam:123","droiddeck","0.7.0");QCOMPARE(r["code"].toString(),QString("unavailable"));QCOMPARE(calls,1);
    }
    void changedVersionAndMalformedStateCannotAuthorizeDispatch(){
        int calls=0;PcRuntime client(PcRuntimePlatform{[&]{return states;},[]{return true;},[&](const QString&,int,const QString&){++calls;return QVariantMap{{"accepted",true}};}});
        auto r=client.openGame("steam:123","droiddeck","0.6.9");QCOMPARE(r["code"].toString(),QString("version-changed"));QCOMPARE(calls,0);
        for(const auto& version:{"0.7.1","0.7.0-beta","0.7.0\n",""}){
            states[0]=QVariantMap{{"id","droiddeck"},{"available",true},{"version",version}};
            r=client.openGame("steam:123","droiddeck",version);QVERIFY(!r["accepted"].toBool());QCOMPARE(calls,0);
        }
        states[0]=QVariantMap{{"id","droiddeck"},{"available","true"},{"version","0.7.0"}};
        client.openGame("steam:123","droiddeck","0.7.0");QCOMPARE(calls,0);
        states[0]=QVariantMap{{"id","droiddeck"},{"available",true},{"version","0.7.0"}};states.append(states[0]);
        client.openGame("steam:123","droiddeck","0.7.0");QCOMPARE(calls,0);
    }
    void refreshAndFinalDispatchRaceRemainFailClosed(){
        int foregroundChecks=0,calls=0;
        PcRuntime client(PcRuntimePlatform{[&]{return states;},[&]{return ++foregroundChecks<2;},[&](const QString&,int,const QString&){++calls;return QVariantMap{{"accepted",true}};}});
        auto r=client.openGame("steam:123","droiddeck","0.7.0");QCOMPARE(r["code"].toString(),QString("not-foreground"));QCOMPARE(calls,0);
        PcRuntime changed(PcRuntimePlatform{[&]{return states;},[]{return true;},[&](const QString&,int,const QString&){++calls;return QVariantMap{{"accepted",false},{"code","version-changed"}};}});
        r=changed.openGame("steam:123","droiddeck","0.7.0");QCOMPARE(r["code"].toString(),QString("version-changed"));QCOMPARE(calls,1);
        PcRuntime noPlatform(PcRuntimePlatform{});QCOMPARE(noPlatform.runtimes().size(),2);
        QVERIFY(!noPlatform.openGame("steam:123","droiddeck","0.7.0")["accepted"].toBool());
    }
};
QTEST_GUILESS_MAIN(Tests)
#include "tst_PcRuntime.moc"
