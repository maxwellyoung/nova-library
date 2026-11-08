#include "ControllerCheck.h"
#include "QtGamepadObserver.h"
#include "ControllerCheckHost.h"
#include <QPointer>
#include <QtTest>
#include <QFile>
#include <QTemporaryDir>
#include <QKeyEvent>
#include <limits>
#ifdef Q_OS_UNIX
#include <sys/stat.h>
#endif

namespace {
QVariantMap device(const ControllerCheck& m,int id=7) {
    for (auto raw:m.state().value("devices").toList()) if (raw.toMap().value("qtDeviceId").toInt()==id) return raw.toMap();
    return {};
}
QVariantMap sample(const ControllerCheck& m,const QString& kind,const QString& key,int id=7) { return device(m,id).value(kind).toMap().value(key).toMap(); }
}
class CheckTests : public QObject {
    Q_OBJECT
private slots:
    void methodsAreExplicitAndNeverPhysicalApproval() {
        ControllerCheck fixture(true),native(false);
        QCOMPARE(fixture.state().value("method").toString(),QString("injected"));
        QCOMPARE(native.state().value("method").toString(),QString("observed"));
        QVERIFY(!fixture.state().value("physicalAccepted").toBool());
        QVERIFY(!native.state().value("physicalAccepted").toBool());
        QVERIFY(!fixture.state().value("startedAt").toString().isEmpty());
        QCOMPARE(fixture.state().value("qtVersion").toString(),QString::fromLatin1(qVersion()));
        QVERIFY(!fixture.systemBack(true,true) || !fixture.state().value("systemBack").toMap().value("pressObserved").toBool());
    }
    void buttonsAndSticksHaveRealSeparateChannels() {
        ControllerCheck m(true); QVERIFY(m.connectDevice(7));
        for (const auto& key:ControllerCheck::buttons()) { QVERIFY(m.button(7,key,true)); QVERIFY(m.button(7,key,false));
            QVERIFY(sample(m,"buttons",key).value("pressObserved").toBool()); QVERIFY(sample(m,"buttons",key).value("releaseObserved").toBool()); }
        for (const auto& key:ControllerCheck::axes()) { QVERIFY(m.axis(7,key,-1)); QVERIFY(m.axis(7,key,1));
            QCOMPARE(sample(m,"axes",key).value("minimum").toDouble(),-1.0); QCOMPARE(sample(m,"axes",key).value("maximum").toDouble(),1.0); }
        QCOMPARE(device(m).value("buttons").toMap().size(),17);
        QCOMPARE(device(m).value("axes").toMap().size(),4);
    }
    void selectAndSystemBackNeverAlias() {
        ControllerCheck m(true); m.connectDevice(7); QtGamepadObserver adapter(&m,false);
        adapter.pressed(7,QGamepadManager::ButtonSelect,1);
        QVERIFY(sample(m,"buttons","select").value("pressObserved").toBool());
        QVERIFY(!m.state().value("systemBack").toMap().value("seen").toBool());
        QKeyEvent back(QEvent::KeyPress,Qt::Key_Back,Qt::NoModifier);
        QVERIFY(!adapter.eventFilter(nullptr,&back));
        QVERIFY(m.state().value("systemBack").toMap().value("pressObserved").toBool());
        adapter.released(7,QGamepadManager::ButtonSelect);
        QCOMPARE(m.state().value("systemBack").toMap().value("raw").toDouble(),1.0);
        QCOMPARE(sample(m,"buttons","select").value("raw").toDouble(),0.0);
        QVERIFY(m.state().value("backDeviceIdentity").toString().contains("unavailable"));
    }
    void nativeQtMappingPreservesPressureBeforePegasusBooleanConversion() {
        ControllerCheck m(true); m.connectDevice(7); QtGamepadObserver adapter(&m,false);
        adapter.pressed(7,QGamepadManager::ButtonA,1); QVERIFY(sample(m,"buttons","south").value("seen").toBool());
        adapter.pressed(7,QGamepadManager::ButtonL2,0.23);
        QCOMPARE(sample(m,"triggers","l2").value("raw").toDouble(),0.23);
        QVERIFY(!sample(m,"triggers","l2").value("aboveThreshold").toBool());
        QVERIFY(sample(m,"buttons","l2").value("pressObserved").toBool());
        adapter.pressed(7,QGamepadManager::ButtonL2,0.81);
        QVERIFY(sample(m,"triggers","l2").value("aboveThreshold").toBool());
        adapter.released(7,QGamepadManager::ButtonL2);
        QCOMPARE(sample(m,"triggers","l2").value("raw").toDouble(),0.0);
        QCOMPARE(sample(m,"triggers","l2").value("maximum").toDouble(),0.81);
        adapter.moved(7,QGamepadManager::AxisRightY,-0.7);
        QCOMPARE(sample(m,"axes","right-y").value("raw").toDouble(),-0.7);
        QVERIFY(device(m).value("triggerResolution").toString().contains("not established"));
        adapter.pressed(7,QGamepadManager::ButtonR2,std::numeric_limits<double>::quiet_NaN());
        QVERIFY(!sample(m,"buttons","r2").value("seen").toBool());
    }
    void focusAndDisconnectNeutralizeWithoutInventingReleaseOrCenter() {
        ControllerCheck m(true); m.connectDevice(7); m.button(7,"select",true); m.axis(7,"left-x",0.7); m.trigger(7,"r2",0.8); m.systemBack(true);
        m.setActive(false);
        QCOMPARE(sample(m,"buttons","select").value("raw").toDouble(),0.0);
        QVERIFY(!sample(m,"buttons","select").value("releaseObserved").toBool());
        QVERIFY(!sample(m,"axes","left-x").value("liveValueObserved").toBool());
        QCOMPARE(sample(m,"axes","left-x").value("minimum").toDouble(),0.7);
        QVERIFY(!m.axis(7,"left-x",0));
        m.setActive(true); m.button(7,"select",true);
        QCOMPARE(sample(m,"buttons","select").value("changes").toInt(),0);
        m.systemBack(true); m.disconnectDevice(7);
        QCOMPARE(m.state().value("systemBack").toMap().value("raw").toDouble(),0.0);
        QVERIFY(!m.state().value("systemBack").toMap().value("releaseObserved").toBool());
        QVERIFY(!device(m).value("connected").toBool());
        QCOMPARE(sample(m,"triggers","r2").value("raw").toDouble(),0.0);
        QVERIFY(!m.trigger(7,"r2",0.3));
        m.connectDevice(7); QVERIFY(m.trigger(7,"r2",0.3));
        QCOMPARE(sample(m,"triggers","r2").value("changes").toInt(),0);
    }
    void appFocusCannotReenableAClosedDiagnostic() {
        ControllerCheck m(true); m.connectDevice(7); m.setActive(false);
        m.setFocused(false); m.setFocused(true);
        QVERIFY(!m.state().value("active").toBool());
        QVERIFY(!m.button(7,"select",true));
        m.setActive(true); QVERIFY(m.button(7,"select",true));
        m.setFocused(false); QCOMPARE(sample(m,"buttons","select").value("raw").toDouble(),0.0);
        QVERIFY(!sample(m,"buttons","select").value("releaseObserved").toBool());
    }
    void duplicateNotificationsDoNotInflateTransitions() {
        ControllerCheck m(true); m.connectDevice(7);
        for(int i=0;i<20;++i) {m.button(7,"south",true);m.axis(7,"left-x",0.6);m.systemBack(true);}
        QCOMPARE(sample(m,"buttons","south").value("changes").toInt(),0);
        QCOMPARE(sample(m,"axes","left-x").value("changes").toInt(),0);
        QCOMPARE(m.state().value("systemBack").toMap().value("changes").toInt(),0);
        QCOMPARE(m.state().value("duplicateEvents").toInt(),57);
    }
    void deadzoneKeepsRawRangeAndRescalesOnlyDisplay() {
        ControllerCheck m(true); m.connectDevice(7); QVERIFY(m.setDeadzone(0.2));
        m.axis(7,"left-x",0.1); QCOMPARE(sample(m,"axes","left-x").value("filtered").toDouble(),0.0);
        m.axis(7,"left-x",0.6); QVERIFY(qAbs(sample(m,"axes","left-x").value("filtered").toDouble()-0.5)<1e-9);
        m.axis(7,"left-x",-1); QCOMPARE(sample(m,"axes","left-x").value("filtered").toDouble(),-1.0);
        QCOMPARE(sample(m,"axes","left-x").value("maximum").toDouble(),0.6);
        QVERIFY(!m.setDeadzone(1)); QVERIFY(!m.setDeadzone(-0.1));
        QVERIFY(!m.setTriggerThreshold(-0.1)); QVERIFY(!m.setTriggerThreshold(1.1));
        QVERIFY(!m.setDeadzone(std::numeric_limits<double>::quiet_NaN()));
    }
    void invalidEventsAreRetainedAsFailuresWithoutChangingValues() {
        ControllerCheck m(true); m.connectDevice(7); m.axis(7,"left-x",0.4);
        QVERIFY(!m.axis(7,"left-x",2)); QVERIFY(!m.trigger(7,"r2",-0.1));
        QVERIFY(!m.axis(7,"left-x",std::numeric_limits<double>::infinity()));
        QVERIFY(!m.button(7,"unrecognized",true)); QVERIFY(!m.button(9,"south",true));
        QCOMPARE(sample(m,"axes","left-x").value("raw").toDouble(),0.4);
        QCOMPARE(m.state().value("rejectedEvents").toInt(),5);
        QVERIFY(!sample(m,"triggers","r2").value("seen").toBool());
    }
    void deviceIdsRemainDistinctAndBounded() {
        ControllerCheck m(true); for (int i=0;i<8;++i) QVERIFY(m.connectDevice(i));
        QVERIFY(!m.connectDevice(8)); QVERIFY(!m.connectDevice(-1));
        m.button(1,"south",true); QVERIFY(!sample(m,"buttons","south",2).value("seen").toBool());
        QVERIFY(m.preview().value("bytes").toInt()<65536);
    }
    void exportRequiresCurrentPreviewAndPreservesExistingFiles() {
        QTemporaryDir tmp; QVERIFY(tmp.isValid()); const auto root=QDir(tmp.path()).canonicalPath();
        const auto path=root+"/new.json"; ControllerCheck m(true); m.connectDevice(7); m.button(7,"select",true);
        auto p=m.preview(); QVERIFY(!m.exportReport(path,"").value("ok").toBool()); QVERIFY(!QFile::exists(path));
        m.button(7,"select",false); QVERIFY(!m.exportReport(path,p.value("sha256").toString()).value("ok").toBool());
        p=m.preview(); QVERIFY(m.exportReport(path,p.value("sha256").toString()).value("ok").toBool());
        QFile file(path); QVERIFY(file.open(QIODevice::ReadOnly)); QCOMPARE(file.readAll(),p.value("json").toString().toUtf8()); file.close();
        QVERIFY(!m.exportReport(path,p.value("sha256").toString()).value("ok").toBool());
        QVERIFY(!p.value("sent").toBool());
#ifdef Q_OS_UNIX
        struct stat st{}; QVERIFY(::stat(QFile::encodeName(path).constData(),&st)==0); QCOMPARE(st.st_mode&0777,mode_t(0600));
#endif
    }
    void applicationFactoryIsDisabledObservedAndOwnedByEngineLifetime() {
        QObject* owner=new QObject;
        QCoreApplication::setApplicationName(QStringLiteral("diagnostic-fixture"));
        QCoreApplication::setApplicationVersion(QStringLiteral("fixture.v1"));
        QPointer<ControllerCheck> model=controllercheck::createForApplication(owner,false);
        QVERIFY(model); QVERIFY(!model->state().value("active").toBool());
        QCOMPARE(model->state().value("method").toString(),QString("observed"));
        QCOMPARE(model->state().value("runtimeMetadata").toMap().value("applicationVersion").toString(),QString("fixture.v1"));
        QVERIFY(!model->state().value("physicalAccepted").toBool());
        delete owner; QVERIFY(model.isNull());
    }
    void privateExportNeedsExplicitDigestAndNeverEscapesApplicationRoot() {
        QTemporaryDir tmp; const auto root=QDir(tmp.path()).canonicalPath(); ControllerCheck m(true);
        m.configureApplication({{"applicationId","fixture.app"},{"applicationVersion","fixture.v1"}},root);
        const auto digest=m.preview().value("sha256").toString();
        QVERIFY(!m.exportPrivateReport("check.json","").value("ok").toBool());
        QVERIFY(!QFile::exists(root+"/controller-checks"));
        QVERIFY(!m.exportPrivateReport("../escape.json",digest).value("ok").toBool());
        QVERIFY(!m.exportReport(root+"/outside.json",digest).value("ok").toBool());
        QVERIFY(m.exportPrivateReport("check.json",digest).value("ok").toBool());
        QVERIFY(!m.exportPrivateReport("check.json",digest).value("ok").toBool());
        QVERIFY(QFile::exists(root+"/controller-checks/check.json"));
#ifdef Q_OS_UNIX
        struct stat st{}; QVERIFY(::stat(QFile::encodeName(root+"/controller-checks").constData(),&st)==0);
        QCOMPARE(st.st_mode&0777,mode_t(0700));
#endif
        ControllerCheck unavailable(true); unavailable.configureApplication({},QString());
        QVERIFY(!unavailable.exportPrivateReport("check.json",unavailable.preview().value("sha256").toString()).value("ok").toBool());
        QVERIFY(!unavailable.exportReport(root+"/outside.json",unavailable.preview().value("sha256").toString()).value("ok").toBool());
    }
    void privateExportRejectsLinksAndNonprivateExistingDirectory() {
        QTemporaryDir tmp; const auto root=QDir(tmp.path()).canonicalPath(); ControllerCheck m(true);
        m.configureApplication({},root); const auto digest=m.preview().value("sha256").toString();
        QVERIFY(QFile::link(root,root+"/controller-checks"));
        QVERIFY(!m.exportPrivateReport("check.json",digest).value("ok").toBool());
        QVERIFY(QFile::remove(root+"/controller-checks")); QVERIFY(QDir(root).mkdir("controller-checks"));
        QVERIFY(QFile::setPermissions(root+"/controller-checks",QFileDevice::ReadOwner|QFileDevice::WriteOwner|QFileDevice::ExeOwner|QFileDevice::ReadOther));
        QVERIFY(!m.exportPrivateReport("check.json",digest).value("ok").toBool());
        QVERIFY(!QFile::exists(root+"/controller-checks/check.json"));
    }
    void symlinkAndMissingOutputParentsAreRefused() {
        QTemporaryDir tmp; const auto root=QDir(tmp.path()).canonicalPath(); ControllerCheck m(true); auto p=m.preview();
        QVERIFY(QFile::link(root,root+"/alias"));
        QVERIFY(!m.exportReport(root+"/alias/new.json",p.value("sha256").toString()).value("ok").toBool());
        QVERIFY(!QFile::exists(root+"/new.json"));
        QVERIFY(!m.exportReport(root+"/missing/new.json",p.value("sha256").toString()).value("ok").toBool());
    }
};
QTEST_GUILESS_MAIN(CheckTests)
#include "tst_ControllerCheck.moc"
