#include "Memory.h"
#include <QtTest>
#include <QFile>
#include <QDir>
#include <QLockFile>
#include <QTemporaryDir>
#include <QJsonDocument>
#include <QJSEngine>
namespace paths { QString writableConfigDir() { return {}; } }
class Tests : public QObject {
    Q_OBJECT
    static void write(const QString& p, const QByteArray& b) { QFile f(p);QVERIFY(f.open(QIODevice::WriteOnly));QCOMPARE(f.write(b),qint64(b.size())); }
    static QByteArray read(const QString& p) { QFile f(p);if(!f.open(QIODevice::ReadOnly))return {};return f.readAll(); }
private slots:
    void absentWriteReopenAndClearLastKey() {
        QTemporaryDir d;model::Memory m(d.path());m.changeTheme("/themes/nova/");
        QVERIFY(m.checkedRead("inputProfilesV1")["ok"].toBool());QVERIFY(!m.checkedRead("inputProfilesV1")["exists"].toBool());
        QVariantMap prefs{{"version",1},{"profiles",QVariantList{}}};QSignalSpy spy(&m,&model::Memory::dataChanged);
        QVERIFY(m.checkedSet("inputProfilesV1",prefs));QCOMPARE(spy.count(),1);
        model::Memory n(d.path());n.changeTheme("/themes/nova/");QCOMPARE(n.get("inputProfilesV1").toMap(),prefs);
        QVERIFY(n.checkedUnset("inputProfilesV1"));QCOMPARE(read(d.filePath("nova.json")),QByteArray("{}"));
        model::Memory last(d.path());last.changeTheme("/themes/nova/");QVERIFY(!last.has("inputProfilesV1"));
    }
    void malformedPreserved_data() {
        QTest::addColumn<QByteArray>("bytes");QTest::newRow("partial")<<QByteArray("{broken");QTest::newRow("array")<<QByteArray("[]");QTest::newRow("empty")<<QByteArray();
        QTest::newRow("oversized")<<QByteArray(4*1024*1024+1,' ');
    }
    void malformedPreserved() {
        QFETCH(QByteArray,bytes);QTemporaryDir d;const auto p=d.filePath("nova.json");write(p,bytes);
        model::Memory m(d.path());m.changeTheme("/themes/nova/");QVERIFY(!m.checkedRead("x")["ok"].toBool());
        QVERIFY(!m.checkedSet("x",42));m.set("x",42);QVERIFY(!m.has("x"));QCOMPARE(read(p),bytes);
    }
    void competingWriterRefused() {
        QTemporaryDir d;model::Memory a(d.path()),b(d.path());a.changeTheme("/themes/nova/");b.changeTheme("/themes/nova/");
        QVERIFY(a.checkedSet("first",1));auto bytes=read(d.filePath("nova.json"));
        QVERIFY(!b.checkedSet("second",2));QVERIFY(!b.checkedRead("second")["ok"].toBool());QCOMPARE(read(d.filePath("nova.json")),bytes);
        b.changeTheme("/themes/nova/");QVERIFY(b.checkedSet("second",2));QVERIFY(!a.checkedUnset("first"));
    }
    void externalEditDeletionAndLinkRefused() {
        QTemporaryDir d;auto p=d.filePath("nova.json");model::Memory m(d.path());m.changeTheme("/themes/nova/");QVERIFY(m.checkedSet("saved",1));
        write(p,"{\"external\":7}");QVERIFY(!m.checkedSet("saved",2));QCOMPARE(read(p),QByteArray("{\"external\":7}"));
        m.changeTheme("/themes/nova/");QVERIFY(QFile::remove(p));QVERIFY(!m.checkedSet("saved",2));QVERIFY(!QFile::exists(p));
        auto target=d.filePath("outside.json");write(target,"{}");QVERIFY(QFile::link(target,p));m.changeTheme("/themes/nova/");QVERIFY(!m.checkedSet("saved",2));QCOMPARE(read(target),QByteArray("{}"));
    }
    void lockedCommitKeepsMemoryBytesAndSignals() {
        QTemporaryDir d;auto p=d.filePath("nova.json");model::Memory m(d.path());m.changeTheme("/themes/nova/");QVERIFY(m.checkedSet("saved",1));auto bytes=read(p);QSignalSpy spy(&m,&model::Memory::dataChanged);
        QLockFile lock(p+".nova-lock");QVERIFY(lock.tryLock(0));QVERIFY(!m.checkedSet("saved",2));QVERIFY(!m.checkedUnset("saved"));
        QCOMPARE(m.get("saved").toInt(),1);QCOMPARE(read(p),bytes);QCOMPARE(spy.count(),0);lock.unlock();QVERIFY(m.checkedSet("saved",3));
    }
    void invalidInputAndOversizedWritePreserve() {
        QTemporaryDir d;model::Memory m(d.path());m.changeTheme("/themes/nova/");QVERIFY(m.checkedSet("saved",1));auto bytes=read(d.filePath("nova.json"));
        QVERIFY(!m.checkedSet("",42));QVERIFY(!m.checkedSet("saved",QVariant()));QVERIFY(!m.checkedUnset("absent"));
        QVERIFY(!m.checkedSet("huge",QString(4*1024*1024,'x')));QCOMPARE(read(d.filePath("nova.json")),bytes);QVERIFY(!m.has("huge"));
    }
    void qmlValuesAndSeparateThemes() {
        QTemporaryDir d;model::Memory m(d.path());m.changeTheme("/themes/nova/");QJSEngine js;auto val=js.evaluate("({version:1,profiles:[]})");
        QVERIFY(m.checkedSet("inputProfilesV1",QVariant::fromValue(val)));QCOMPARE(m.get("inputProfilesV1").toMap()["version"].toInt(),1);
        m.changeTheme("/themes/other/");QVERIFY(!m.has("inputProfilesV1"));QVERIFY(m.checkedSet("other",2));
        m.changeTheme("/themes/nova/");QVERIFY(m.has("inputProfilesV1"));QVERIFY(!m.has("other"));
    }
};
QTEST_GUILESS_MAIN(Tests)
#include "tst_Memory.moc"
