// SPDX-License-Identifier: GPL-3.0-or-later
#include "RomCloud.h"
#include <QtTest>
#include <QTemporaryDir>
#include <QTcpServer>
#include <QTcpSocket>
#include <QJsonDocument>
#include <QJsonObject>
#include <QCryptographicHash>
#include <QSignalSpy>
#include <QDirIterator>
#ifdef Q_OS_UNIX
#include <unistd.h>
#include <sys/stat.h>
#endif
using namespace library;
class Tests : public QObject {
    Q_OBJECT
    QByteArray payload=QByteArray(65536,'x');
    QVariantMap game(int id=1, QString filename="Example.sfc", QString platform="snes") {
        return {{"id",id},{"name","Example"},{"fs_name",filename},{"platform_slug",platform},{"platform_display_name","SNES"},{"files",QVariantList{QVariantMap{{"id",3},{"file_name",filename},{"file_size_bytes",payload.size()},{"sha1_hash",QString(QCryptographicHash::hash(payload,QCryptographicHash::Sha1).toHex())}}}}};
    }
    RomCloudConfig removalFixture(QTemporaryDir& dir, bool partial=false) {
        const auto root=QDir(dir.path()).canonicalPath()+"/roms", cache=dir.path()+"/cache";
        RomCloudConfig c{QUrl("http://127.0.0.1:1"),"synthetic-token",root,cache,[]{return QString();}};
        const auto normal=RomCloud::validateGame(game());const auto folder=root+"/nova-cloud/1"+(partial?".partial":"");
        if(!QDir().mkpath(folder)||!QDir().mkpath(cache))qFatal("Synthetic fixture failed");
        auto write=[](const QString& p,const QByteArray& bytes){QFile f(p);if(!f.open(QIODevice::WriteOnly)||f.write(bytes)!=bytes.size())qFatal("Synthetic fixture write failed");};
        write(folder+"/Example.sfc",partial?payload.left(123):payload);
        QVariantMap marker=partial?normal:QVariantMap{{"id",1},{"endpoint",c.endpoint.toString()},{"files",normal["files"]},{"entry",normal["entry"]},{"platform",normal["platform"]}};
        marker["endpoint"]=c.endpoint.toString();
        write(folder+(partial?"/.plan.json":"/.nova-install.json"),QJsonDocument::fromVariant(marker).toJson());
        write(cache+"/catalogue.json",QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{normal}}}).toJson());
        return c;
    }
private slots:
    void reviewInspectionNeverStartsPayloads_data() {
        QTest::addColumn<QString>("kind");
        for(const auto& kind:{"success","wrong-id","http-failure","cancel"})QTest::newRow(kind)<<QString(kind);
    }
    void reviewInspectionNeverStartsPayloads() {
        QFETCH(QString,kind);QTemporaryDir dir;QTcpServer server;QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto root=QDir(dir.path()).canonicalPath()+"/roms";
        RomCloudConfig c{QUrl("http://127.0.0.1:"+QString::number(server.serverPort())),"synthetic-token",root,dir.path()+"/cache"};
        QVERIFY(QDir().mkpath(c.cache));auto summary=game();summary.remove("files");
        QFile cache(c.cache+"/catalogue.json");QVERIFY(cache.open(QIODevice::WriteOnly));
        cache.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{RomCloud::validateGame(summary)}}}).toJson());cache.close();
        int metadataRequests=0,payloadRequests=0;
        connect(&server,&QTcpServer::newConnection,this,[&]{auto socket=server.nextPendingConnection();auto buffer=new QByteArray;
            connect(socket,&QObject::destroyed,this,[buffer]{delete buffer;});
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket,buffer]{buffer->append(socket->readAll());if(!buffer->contains("\r\n\r\n"))return;
                socket->disconnect(socket,nullptr,socket,nullptr);
                const bool metadata=buffer->startsWith("GET /api/roms/1 ");
                if(metadata)++metadataRequests;else ++payloadRequests;
                if(kind=="cancel")return;
                const auto body=metadata?QJsonDocument::fromVariant(game(kind=="wrong-id"?2:1)).toJson():payload;
                socket->write((kind=="http-failure"?QByteArray("HTTP/1.1 503 Unavailable\r\n"):QByteArray("HTTP/1.1 200 OK\r\n"))+"Content-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);socket->disconnectFromHost();
            });connect(socket,&QTcpSocket::disconnected,socket,&QObject::deleteLater);
        });
        RomCloud cloud(c);QCOMPARE(cloud.reviewVersion(),1);QVERIFY(!cloud.downloadReview(1)["detailsKnown"].toBool());
        cloud.inspectDownload(1);QVERIFY(cloud.inspectingDownload());QVERIFY(cloud.games()[0].toMap()["downloadState"]!="downloading");QTRY_COMPARE_WITH_TIMEOUT(metadataRequests,1,3000);
        if(kind=="cancel")cloud.cancel();
        QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
        QVERIFY(!cloud.inspectingDownload());
        QCOMPARE(payloadRequests,0);QVERIFY(!QFileInfo::exists(root));QVERIFY(cloud.downloads().isEmpty());
        QCOMPARE(cloud.downloadReview(1)["detailsKnown"].toBool(),kind=="success");
        if(kind=="success") {
            {RomCloud reopened(c);QVERIFY(reopened.downloadReview(1)["detailsKnown"].toBool());reopened.inspectDownload(1);QVERIFY(!reopened.busy());QCOMPARE(metadataRequests,1);}
            QVERIFY(QDir().mkpath(root));cloud.install(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
            QCOMPARE(payloadRequests,1);QVERIFY(cloud.games()[0].toMap()["installed"].toBool());
            server.close();RomCloud offline(c);QSignalSpy launch(&offline,&RomCloud::launchRequested);
            offline.play(1);QTRY_VERIFY_WITH_TIMEOUT(!offline.busy(),3000);QCOMPARE(launch.count(),1);
        }
    }
    void reviewPreservesDependenciesIdentityAndPrivacy() {
        QTemporaryDir dir;auto c=removalFixture(dir,true);RomCloud cloud(c);
        const auto review=cloud.downloadReview(1);QVERIFY(review["detailsKnown"].toBool());
        QCOMPARE(review["files"].toList().size(),1);QCOMPARE(review["remainingBytes"].toLongLong(),qint64(payload.size()-123));
        QVERIFY(review["scope"].toString().contains("smaller selection is not supported"));
        QCOMPARE(review["editionId"].toString(),cloud.games()[0].toMap()["editionId"].toString());
        const auto bytes=QJsonDocument::fromVariant(review).toJson();
        QVERIFY(!bytes.contains(c.token));QVERIFY(!bytes.contains(c.endpoint.toString().toUtf8()));QVERIFY(!bytes.contains(c.root.toUtf8()));
        QVERIFY(cloud.downloadReview(999).isEmpty());cloud.inspectDownload(999);QVERIFY(!cloud.busy());
        auto item=game(2,"disc-1.chd","ps"),second=game(2,"disc-2.chd","ps")["files"].toList()[0].toMap();second["id"]=4;
        auto playlist=game(2,"set.m3u","ps")["files"].toList()[0].toMap();playlist["id"]=5;
        item["files"]=QVariantList{item["files"].toList()[0],second,playlist};
        QFile cache(c.cache+"/catalogue.json");QVERIFY(cache.open(QIODevice::WriteOnly|QIODevice::Truncate));
        auto normal=RomCloud::validateGame(item);cache.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{normal}}}).toJson());cache.close();
        RomCloud discs(c);const auto set=discs.downloadReview(2);QVERIFY(set["scope"].toString().contains("Individual-disc downloads are not supported"));
        QCOMPARE(set["entry"].toString(),QString("set.m3u"));QCOMPARE(set["files"].toList().size(),3);
        QCOMPARE(set["files"].toList()[2].toMap()["role"].toString(),QString("Disc playlist"));
        auto changed=normal;auto files=changed["files"].toList();auto file=files[0].toMap();file["hash"]=QString(40,'e');files[0]=file;changed["files"]=files;
        QVERIFY(set["editionId"].toString()!=RomCloud::editionIdentity(c.endpoint,changed));
    }
    void boundedConnectionRecovery_data() {
        QTest::addColumn<QString>("kind");QTest::addColumn<int>("requestsExpected");QTest::addColumn<bool>("installedExpected");
        QTest::newRow("recover")<<QString("recover")<<2<<true;
        QTest::newRow("preexisting-prefix")<<QString("preexisting-prefix")<<2<<true;
        QTest::newRow("twice")<<QString("twice")<<2<<false;
        for(const auto& kind:{"unknown-window","away","no-progress","extra-save","changed-plan","cancel","http-error","bad-hash","wrong-length","changed-after-notice","away-after-notice"})
            QTest::newRow(kind)<<QString(kind)<<1<<false;
        QTest::newRow("range-ignored")<<QString("range-ignored")<<2<<false;
        QTest::newRow("wrong-range")<<QString("wrong-range")<<2<<false;
    }
    void boundedConnectionRecovery() {
        QFETCH(QString,kind);QFETCH(int,requestsExpected);QFETCH(bool,installedExpected);
        QTemporaryDir dir;QTcpServer server;QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto root=QDir(dir.path()).canonicalPath()+"/roms";QVERIFY(QDir().mkpath(root));bool foreground=true;
        RomCloudConfig c{QUrl("http://127.0.0.1:"+QString::number(server.serverPort())),"synthetic-token",root,dir.path()+"/cache"};
        if(kind!="unknown-window")c.downloadWindow=[&]{return foreground;};
        QVERIFY(QDir().mkpath(c.cache));QFile cache(c.cache+"/catalogue.json");QVERIFY(cache.open(QIODevice::WriteOnly));
        cache.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{RomCloud::validateGame(game())}}}).toJson());cache.close();
        if(kind=="preexisting-prefix") {
            const auto folder=root+"/nova-cloud/1.partial";QVERIFY(QDir().mkpath(folder));
            auto plan=RomCloud::validateGame(game());plan["endpoint"]=c.endpoint.toString();
            QFile marker(folder+"/.plan.json");QVERIFY(marker.open(QIODevice::WriteOnly));marker.write(QJsonDocument::fromVariant(plan).toJson());marker.close();
            QFile prefix(folder+"/Example.sfc");QVERIFY(prefix.open(QIODevice::WriteOnly));QCOMPARE(prefix.write(payload.left(123)),qint64(123));
        }
        int requests=0;QList<QByteArray> ranges;
        connect(&server,&QTcpServer::newConnection,this,[&]{auto socket=server.nextPendingConnection();auto buffer=new QByteArray;
            connect(socket,&QObject::destroyed,this,[buffer]{delete buffer;});
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket,buffer]{buffer->append(socket->readAll());if(!buffer->contains("\r\n\r\n"))return;
                socket->disconnect(socket,nullptr,socket,nullptr);++requests;
                QByteArray range;for(const auto& line:buffer->split('\n'))if(line.toLower().startsWith("range:"))range=line.trimmed();ranges.append(range);
                if(kind=="away")foreground=false;
                const auto folder=root+"/nova-cloud/1.partial";
                if(kind=="extra-save") {QFile save(folder+"/owner.srm");if(!save.open(QIODevice::WriteOnly)||save.write("protected-save")!=14)qFatal("Save fixture failed");}
                if(kind=="changed-plan") {QFile plan(folder+"/.plan.json");if(!plan.open(QIODevice::ReadOnly))qFatal("Plan fixture failed");auto j=QJsonDocument::fromJson(plan.readAll()).object();plan.close();j["endpoint"]="https://example.invalid";if(!plan.open(QIODevice::WriteOnly|QIODevice::Truncate))qFatal("Plan fixture write failed");plan.write(QJsonDocument(j).toJson());}
                if(kind=="http-error") {socket->write("HTTP/1.1 503 Unavailable\r\nContent-Length: 1\r\nConnection: close\r\n\r\nx");socket->disconnectFromHost();return;}
                if(kind=="wrong-length") {socket->write("HTTP/1.1 200 OK\r\nContent-Length: 123\r\nConnection: close\r\n\r\n"+payload.left(123));socket->disconnectFromHost();return;}
                if(kind=="bad-hash") {socket->write("HTTP/1.1 200 OK\r\nContent-Length: 65536\r\nConnection: close\r\n\r\n"+QByteArray(65536,'z'));socket->disconnectFromHost();return;}
                const qint64 start=range.isEmpty()?0:range.split('=').value(1).split('-').value(0).toLongLong();
                if(requests==1 || kind=="twice") {
                    const auto header=start?QByteArray("HTTP/1.1 206 Partial Content\r\nContent-Range: bytes ")+QByteArray::number(start)+"-65535/65536\r\nContent-Length: "+QByteArray::number(65536-start)+"\r\n":QByteArray("HTTP/1.1 200 OK\r\nContent-Length: 65536\r\n");
                    socket->write(header+"Connection: close\r\n\r\n"+(kind=="no-progress"?QByteArray():payload.mid(start,123)));socket->disconnectFromHost();return;
                }
                if(kind=="wrong-range")socket->write("HTTP/1.1 206 Partial Content\r\nContent-Range: bytes 124-65535/65536\r\nContent-Length: 65413\r\nConnection: close\r\n\r\n"+payload.mid(123));
                else if(kind=="range-ignored")socket->write("HTTP/1.1 200 OK\r\nContent-Length: 65536\r\nConnection: close\r\n\r\n"+payload);
                else socket->write("HTTP/1.1 206 Partial Content\r\nContent-Range: bytes "+QByteArray::number(start)+"-65535/65536\r\nContent-Length: "+QByteArray::number(65536-start)+"\r\nConnection: close\r\n\r\n"+payload.mid(start));
                socket->disconnectFromHost();
            });connect(socket,&QTcpSocket::disconnected,socket,&QObject::deleteLater);
        });
        RomCloud cloud(c);bool cancelled=false;
        connect(&cloud,&RomCloud::changed,this,[&]{if(!cancelled && cloud.message().contains("Retrying")){
            if(kind=="cancel"){cancelled=true;cloud.cancel();}
            if(kind=="away-after-notice"){cancelled=true;foreground=false;}
            if(kind=="changed-after-notice"){cancelled=true;QFile marker(root+"/nova-cloud/1.partial/.plan.json");if(!marker.open(QIODevice::WriteOnly|QIODevice::Truncate)||marker.write("{}")!=2)qFatal("Late plan mutation failed");}
        }});
        cloud.install(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),5000);
        QCOMPARE(requests,requestsExpected);QCOMPARE(cloud.games()[0].toMap()["installed"].toBool(),installedExpected);
        const auto partial=root+"/nova-cloud/1.partial/Example.sfc";
        if(requestsExpected==2)QCOMPARE(ranges[1],kind=="preexisting-prefix"?QByteArray("Range: bytes=246-"):QByteArray("Range: bytes=123-"));
        if(installedExpected) {QFile actual(root+"/nova-cloud/1/Example.sfc");QVERIFY(actual.open(QIODevice::ReadOnly));QCOMPARE(actual.readAll(),payload);server.close();RomCloud offline(c);QSignalSpy launch(&offline,&RomCloud::launchRequested);offline.play(1);QTRY_VERIFY_WITH_TIMEOUT(!offline.busy(),3000);QCOMPARE(launch.count(),1);}
        else {QVERIFY(QFileInfo::exists(partial));QVERIFY(!QFileInfo::exists(root+"/nova-cloud/1/.nova-install.json"));if(kind=="twice")QCOMPARE(QFileInfo(partial).size(),qint64(246));if(kind=="range-ignored" || kind=="wrong-range")QCOMPARE(QFileInfo(partial).size(),qint64(123));}
        if(kind=="extra-save") {QFile save(root+"/nova-cloud/1.partial/owner.srm");QVERIFY(save.open(QIODevice::ReadOnly));QCOMPARE(save.readAll(),QByteArray("protected-save"));}
        if(kind=="cancel")QVERIFY(cancelled);
    }
    void automaticRetryBudgetSpansAllDiscs() {
        QTemporaryDir dir;QTcpServer server;QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto root=QDir(dir.path()).canonicalPath()+"/roms";QVERIFY(QDir().mkpath(root));
        RomCloudConfig c{QUrl("http://127.0.0.1:"+QString::number(server.serverPort())),"synthetic-token",root,dir.path()+"/cache",{},[]{return true;}};
        auto item=game(1,"disc-1.chd","ps");auto files=item["files"].toList();
        auto second=files[0].toMap();second["file_name"]="disc-2.chd";second["id"]=4;files.append(second);
        const QByteArray playlistBytes="disc-1.chd\ndisc-2.chd\n";
        auto playlist=second;playlist["file_name"]="set.m3u";playlist["id"]=5;playlist["file_size_bytes"]=playlistBytes.size();playlist["sha1_hash"]=QString(QCryptographicHash::hash(playlistBytes,QCryptographicHash::Sha1).toHex());files.append(playlist);item["files"]=files;
        QVERIFY(QDir().mkpath(c.cache));QFile cache(c.cache+"/catalogue.json");QVERIFY(cache.open(QIODevice::WriteOnly));
        cache.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{RomCloud::validateGame(item)}}}).toJson());cache.close();
        int requests=0;
        connect(&server,&QTcpServer::newConnection,this,[&]{auto socket=server.nextPendingConnection();auto buffer=new QByteArray;
            connect(socket,&QObject::destroyed,this,[buffer]{delete buffer;});
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket,buffer]{buffer->append(socket->readAll());if(!buffer->contains("\r\n\r\n"))return;
                socket->disconnect(socket,nullptr,socket,nullptr);++requests;
                if(buffer->contains("/set.m3u "))socket->write("HTTP/1.1 200 OK\r\nContent-Length: "+QByteArray::number(playlistBytes.size())+"\r\nConnection: close\r\n\r\n"+playlistBytes);
                else if(buffer->contains("Range: bytes=123-"))socket->write("HTTP/1.1 206 Partial Content\r\nContent-Range: bytes 123-65535/65536\r\nContent-Length: 65413\r\nConnection: close\r\n\r\n"+payload.mid(123));
                else socket->write("HTTP/1.1 200 OK\r\nContent-Length: 65536\r\nConnection: close\r\n\r\n"+payload.left(123));
                socket->disconnectFromHost();
            });connect(socket,&QTcpSocket::disconnected,socket,&QObject::deleteLater);
        });
        RomCloud cloud(c);cloud.install(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),5000);
        QCOMPARE(requests,3);QVERIFY(!cloud.games()[0].toMap()["installed"].toBool());
        QFile first(root+"/nova-cloud/1.partial/disc-1.chd");QVERIFY(first.open(QIODevice::ReadOnly));QCOMPARE(first.readAll(),payload);
        QCOMPARE(QFileInfo(root+"/nova-cloud/1.partial/disc-2.chd").size(),qint64(123));
        QVERIFY(!QFileInfo::exists(root+"/nova-cloud/1/.nova-install.json"));
    }
    void queuePersistsWithoutExecutionAndUnqueueKeepsFiles() {
        QTemporaryDir dir;auto c=removalFixture(dir,true);c.downloadWindow=[]{return false;};
        const auto queue=c.cache+"/download-queue.json",part=c.root+"/nova-cloud/1.partial/Example.sfc";
        {
            RomCloud cloud(c);QVERIFY(cloud.enqueueDownload(1));QVERIFY(cloud.enqueueDownload(1));
            QCOMPARE(cloud.downloads().size(),1);QVERIFY(!cloud.queueRunning());
            cloud.startDownloads(1);QVERIFY(!cloud.busy());QVERIFY(!cloud.queueRunning());
        }
        QFile q(queue);QVERIFY(q.open(QIODevice::ReadOnly));const auto bytes=q.readAll();q.close();
        QVERIFY(!bytes.contains(c.token));QVERIFY(!bytes.contains(c.endpoint.toString().toUtf8()));QVERIFY(!bytes.contains(c.root.toUtf8()));
        auto data=QJsonDocument::fromJson(bytes).toVariant().toMap();auto jobs=data["jobs"].toList();auto job=jobs[0].toMap();
        job["state"]="active";jobs[0]=job;data["jobs"]=jobs;
        QVERIFY(q.open(QIODevice::WriteOnly|QIODevice::Truncate));q.write(QJsonDocument::fromVariant(data).toJson());q.close();
        RomCloud reopened(c);QVERIFY(!reopened.queueRunning());QVERIFY(!reopened.busy());
        QCOMPARE(reopened.downloads()[0].toMap()["state"].toString(),QString("paused"));
        QVERIFY(reopened.removeQueuedDownload(1));QVERIFY(reopened.downloads().isEmpty());
        QCOMPARE(QFileInfo(part).size(),qint64(123));QVERIFY(QFileInfo::exists(c.root+"/nova-cloud/1.partial/.plan.json"));
        RomCloud empty(c);QVERIFY(empty.downloads().isEmpty());
    }
    void queueRetainsUnrecognisedState_data() {
        QTest::addColumn<QString>("kind");
        for(const auto& kind:{"malformed","foreign-root","foreign-origin","oversized","extra-field","linked","hardlinked"})QTest::newRow(kind)<<QString(kind);
    }
    void queueRetainsUnrecognisedState() {
        QFETCH(QString,kind);QTemporaryDir dir;auto c=removalFixture(dir,true);const auto path=c.cache+"/download-queue.json";
        {RomCloud cloud(c);QVERIFY(cloud.enqueueDownload(1));}
        QFile file(path);QVERIFY(file.open(QIODevice::ReadOnly));auto bytes=file.readAll();file.close();
        if(kind=="malformed")bytes="{broken";
        if(kind=="oversized")bytes=QByteArray(256*1024+1,'x');
        if(kind=="extra-field") {auto j=QJsonDocument::fromJson(bytes).object();j["surprise"]=true;bytes=QJsonDocument(j).toJson();}
        QVERIFY(file.open(QIODevice::WriteOnly|QIODevice::Truncate));file.write(bytes);file.close();
        if(kind=="foreign-root"){c.root=dir.path()+"/other-roms";QVERIFY(QDir().mkpath(c.root));}
        if(kind=="foreign-origin")c.endpoint=QUrl("http://127.0.0.1:2");
        if(kind=="linked"){QVERIFY(QFile::rename(path,path+".kept"));QVERIFY(QFile::link(path+".kept",path));}
        if(kind=="hardlinked") {
#ifdef Q_OS_UNIX
            QVERIFY(::link(QFile::encodeName(path).constData(),QFile::encodeName(path+".kept").constData())==0);
#else
            QSKIP("Hardlink adapter not available");
#endif
        }
        c.downloadWindow=[]{return true;};RomCloud cloud(c);QVERIFY(cloud.downloads().isEmpty());
        QVERIFY(!cloud.enqueueDownload(1));cloud.startDownloads();QVERIFY(!cloud.queueRunning());QVERIFY(!cloud.busy());
        QVERIFY(file.open(QIODevice::ReadOnly));QCOMPARE(file.readAll(),bytes);
    }
    void queueStaleWriterAndNewEmptyFileAreProtected() {
        QTemporaryDir dir;auto c=removalFixture(dir,true);const auto path=c.cache+"/download-queue.json";
        RomCloud first(c),stale(c);QVERIFY(first.enqueueDownload(1));QVERIFY(!stale.enqueueDownload(1));
        QFile f(path);QVERIFY(f.open(QIODevice::ReadOnly));const auto original=f.readAll();f.close();
        RomCloud current(c);QVERIFY(current.removeQueuedDownload(1));QVERIFY(!first.removeQueuedDownload(1));
        QVERIFY(f.open(QIODevice::ReadOnly));QVERIFY(f.readAll()!=original);f.close();
        QVERIFY(QFile::remove(path));RomCloud beforeEmpty(c);QVERIFY(f.open(QIODevice::WriteOnly));f.close();
        QVERIFY(!beforeEmpty.enqueueDownload(1));QCOMPARE(QFileInfo(path).size(),qint64(0));
    }
    void queuedEditionNeverRetargetsChangedContent() {
        QTemporaryDir dir;auto c=removalFixture(dir,true);c.downloadWindow=[]{return true;};
        {RomCloud cloud(c);QVERIFY(cloud.enqueueDownload(1));}
        auto changed=game();auto files=changed["files"].toList();auto f=files[0].toMap();f["sha1_hash"]=QString(40,'b');files[0]=f;changed["files"]=files;
        QFile cache(c.cache+"/catalogue.json");QVERIFY(cache.open(QIODevice::WriteOnly|QIODevice::Truncate));
        cache.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{RomCloud::validateGame(changed)}}}).toJson());cache.close();
        RomCloud reopened(c);reopened.startDownloads(1);QTRY_VERIFY(!reopened.queueRunning());
        QCOMPARE(reopened.downloads()[0].toMap()["state"].toString(),QString("blocked"));
        QVERIFY(!reopened.busy());QCOMPARE(QFileInfo(c.root+"/nova-cloud/1.partial/Example.sfc").size(),qint64(123));
    }
    void queueLimitsAndPrivatePermissions() {
        QTemporaryDir dir;auto c=removalFixture(dir,true);QVariantList games;
        for(int id=1;id<=101;++id)games.append(RomCloud::validateGame(game(id,"Game.sfc")));
        QFile cache(c.cache+"/catalogue.json");QVERIFY(cache.open(QIODevice::WriteOnly|QIODevice::Truncate));
        cache.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",games}}).toJson());cache.close();
        RomCloud cloud(c);for(int id=1;id<=100;++id)QVERIFY(cloud.enqueueDownload(id));
        QVERIFY(!cloud.enqueueDownload(101));QCOMPARE(cloud.downloads().size(),100);QVERIFY(!cloud.busy());
        const auto permissions=QFileInfo(c.cache+"/download-queue.json").permissions();
        QVERIFY(!(permissions & (QFileDevice::ReadGroup|QFileDevice::WriteGroup|QFileDevice::ReadOther|QFileDevice::WriteOther)));
        RomCloud reopened(c);QCOMPARE(reopened.downloads().size(),100);QVERIFY(!reopened.queueRunning());
    }
    void fetchedDetailsCannotRetargetPinnedQueue() {
        QTemporaryDir dir;QTcpServer server;QVERIFY(server.listen(QHostAddress::LocalHost));auto c=removalFixture(dir,true);
        c.endpoint=QUrl("http://127.0.0.1:"+QString::number(server.serverPort()));c.downloadWindow=[]{return true;};
        auto writeCatalogue=[&](QVariantMap g){QFile f(c.cache+"/catalogue.json");if(!f.open(QIODevice::WriteOnly|QIODevice::Truncate))qFatal("Fixture write failed");f.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{g}}}).toJson());};
        writeCatalogue(RomCloud::validateGame(game()));{RomCloud cloud(c);QVERIFY(cloud.enqueueDownload(1));}
        auto summary=RomCloud::validateGame(game());summary["files"]=QVariantList();summary["needsDetails"]=true;writeCatalogue(summary);
        // Remove the old endpoint from the partial marker only in this disposable fixture,
        // so the new details identity check is the boundary under test.
        QFile marker(c.root+"/nova-cloud/1.partial/.plan.json");QVERIFY(marker.open(QIODevice::ReadOnly));auto plan=QJsonDocument::fromJson(marker.readAll()).object();marker.close();plan.remove("endpoint");
        QVERIFY(marker.open(QIODevice::WriteOnly|QIODevice::Truncate));marker.write(QJsonDocument(plan).toJson());marker.close();
        int detailRequests=0,payloadRequests=0;
        connect(&server,&QTcpServer::newConnection,this,[&]{auto socket=server.nextPendingConnection();
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket]{const auto request=socket->readAll();if(!request.contains("\r\n\r\n"))return;
                if(request.startsWith("GET /api/roms/1 "))++detailRequests;else ++payloadRequests;
                auto changed=game();auto files=changed["files"].toList();auto file=files[0].toMap();file["sha1_hash"]=QString(40,'b');files[0]=file;changed["files"]=files;
                const auto body=QJsonDocument::fromVariant(changed).toJson();socket->write("HTTP/1.1 200 OK\r\nContent-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);socket->disconnectFromHost();});
            connect(socket,&QTcpSocket::disconnected,socket,&QObject::deleteLater);
        });
        RomCloud cloud(c);cloud.startDownloads(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.queueRunning() && !cloud.busy(),3000);
        QCOMPARE(detailRequests,1);QCOMPARE(payloadRequests,0);QCOMPARE(cloud.downloads()[0].toMap()["state"].toString(),QString("blocked"));
        QCOMPARE(QFileInfo(c.root+"/nova-cloud/1.partial/Example.sfc").size(),qint64(123));
    }
    void queueTransfers_data() {
        QTest::addColumn<QString>("kind");
        for(const auto& kind:{"fifo","foreground-pause","connection-lost","details"})QTest::newRow(kind)<<QString(kind);
    }
    void queueTransfers() {
        QFETCH(QString,kind);QTemporaryDir dir;QTcpServer server;QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto root=QDir(dir.path()).canonicalPath()+"/roms";QVERIFY(QDir().mkpath(root));bool foreground=true;
        RomCloudConfig c{QUrl("http://127.0.0.1:"+QString::number(server.serverPort())),"synthetic-token",root,dir.path()+"/cache",{},[&]{return foreground;}};
        QList<int> order;bool ranged=false;int detailsRequests=0;
        connect(&server,&QTcpServer::newConnection,this,[&]{
            auto socket=server.nextPendingConnection();auto buffer=new QByteArray;
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket,buffer]{
                buffer->append(socket->readAll());if(!buffer->contains("\r\n\r\n"))return;
                const auto request=*buffer;socket->disconnect(socket,nullptr,socket,nullptr);
                QByteArray body;int status=200;QByteArray headers;
                if(request.startsWith("GET /api/roms?")) {
                    auto first=game(1,"One.sfc");if(kind=="details")first.remove("files");
                    body=QJsonDocument::fromVariant(QVariantMap{{"items",QVariantList{first,game(2,"Two.sfc")}}}).toJson();
                } else if(request.startsWith("GET /api/roms/1 ")){++detailsRequests;body=QJsonDocument::fromVariant(game(1,"One.sfc")).toJson();}
                else {
                    const int id=request.contains("/One.sfc ")?1:2;order.append(id);
                    const bool interrupt=kind=="foreground-pause" || kind=="connection-lost";
                    if(interrupt && order.size()==1) {
                        socket->write("HTTP/1.1 200 OK\r\nContent-Length: 65536\r\nConnection: close\r\n\r\n"+payload.left(123));
                        if(kind=="connection-lost")socket->disconnectFromHost();return;
                    }
                    const bool range=request.contains("Range: bytes=123-");
                    if(range){ranged=true;status=206;headers="Content-Range: bytes 123-65535/65536\r\n";body=payload.mid(123);}else body=payload;
                }
                socket->write("HTTP/1.1 "+QByteArray::number(status)+" OK\r\n"+headers+"Content-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);socket->disconnectFromHost();
            });
            connect(socket,&QTcpSocket::disconnected,socket,&QObject::deleteLater);
            connect(socket,&QTcpSocket::destroyed,this,[buffer]{delete buffer;});
        });
        const bool interrupted=kind=="foreground-pause";
        {
            RomCloud cloud(c);cloud.refresh();QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(cloud.games().size(),2);
            QVERIFY(cloud.enqueueDownload(1));QVERIFY(cloud.enqueueDownload(2));
            connect(&cloud,&RomCloud::changed,this,[&]{if(kind=="foreground-pause" && foreground && cloud.busy() && cloud.progress()>0){foreground=false;cloud.reevaluateDownloadWindow();}});
            cloud.startDownloads();QTRY_VERIFY_WITH_TIMEOUT(!cloud.queueRunning() && !cloud.busy(),5000);
            const auto expectedOrder=interrupted?QList<int>{1}:kind=="connection-lost"?QList<int>{1,1,2}:QList<int>{1,2};
            QCOMPARE(order,expectedOrder);
            if(kind=="connection-lost")QVERIFY(ranged);
            if(interrupted) {
                QCOMPARE(cloud.downloads()[0].toMap()["state"].toString(),kind=="foreground-pause"?QString("paused"):QString("blocked"));
                QCOMPARE(QFileInfo(root+"/nova-cloud/1.partial/One.sfc").size(),qint64(123));
                foreground=true;cloud.reevaluateDownloadWindow();QVERIFY(!cloud.queueRunning());
            } else for(const auto& raw:cloud.downloads())QCOMPARE(raw.toMap()["state"].toString(),QString("ready"));
        }
        RomCloud reopened(c);QVERIFY(!reopened.queueRunning());QVERIFY(!reopened.busy());
        QCOMPARE(order.size(),interrupted?1:kind=="connection-lost"?3:2);
        if(interrupted){reopened.startDownloads(1);QTRY_VERIFY_WITH_TIMEOUT(!reopened.queueRunning() && !reopened.busy(),5000);QVERIFY(ranged);QCOMPARE(order,(QList<int>{1,1,2}));}
        for(const auto& raw:reopened.downloads()) {QCOMPARE(raw.toMap()["state"].toString(),QString("ready"));QVERIFY(!raw.toMap()["editionId"].toString().isEmpty());}
        QCOMPARE(detailsRequests,kind=="details"?1:0);
        QFile result(root+"/nova-cloud/2/Two.sfc");QVERIFY(result.open(QIODevice::ReadOnly));QCOMPARE(result.readAll(),payload);
    }
    void retainedDownloadFacts_data() {
        QTest::addColumn<QString>("kind");QTest::addColumn<bool>("blocked");QTest::addColumn<bool>("resumable");
        for(const auto& kind:{"matching","legacy"})QTest::newRow(kind)<<QString(kind)<<false<<true;
        for(const auto& kind:{"foreign","foreign-without-details","changed","extra-save","many-files","malformed","oversized","linked-marker","linked-payload","linked-directory","hardlinked-marker","hardlinked-payload"})
            QTest::newRow(kind)<<QString(kind)<<true<<false;
        QTest::newRow("empty")<<QString("empty")<<false<<false;
        QTest::newRow("missing")<<QString("missing")<<false<<false;
    }
    void retainedDownloadFacts() {
        QFETCH(QString,kind);QFETCH(bool,blocked);QFETCH(bool,resumable);
        QTemporaryDir dir;QVERIFY(dir.isValid());const auto c=removalFixture(dir,true);
        const auto folder=c.root+"/nova-cloud/1.partial",plan=folder+"/.plan.json",part=folder+"/Example.sfc",outside=dir.path()+"/outside";
        auto write=[](const QString& path,const QByteArray& bytes){QFile f(path);if(!f.open(QIODevice::WriteOnly)||f.write(bytes)!=bytes.size())qFatal("Write failed");};
        QFile input(plan);QVERIFY(input.open(QIODevice::ReadOnly));auto record=QJsonDocument::fromJson(input.readAll()).object().toVariantMap();input.close();
        if(kind.startsWith("foreign"))record["endpoint"]="http://127.0.0.1:2";
        if(kind=="changed")record["entry"]="Other.sfc";
        if(kind=="legacy")record.remove("endpoint");
        write(plan,QJsonDocument::fromVariant(record).toJson());
        if(kind=="foreign-without-details") {
            auto cached=RomCloud::validateGame(game());cached["files"]=QVariantList();cached["needsDetails"]=true;
            write(c.cache+"/catalogue.json",QJsonDocument::fromVariant(QVariantMap{{"endpoint",c.endpoint.toString()},{"games",QVariantList{cached}}}).toJson());
        }
        if(kind=="extra-save")write(folder+"/personal.srm","preserve this save");
        if(kind=="many-files")for(int i=0;i<20;++i)write(folder+"/extra-"+QString::number(i),"preserve this file");
        if(kind=="malformed")write(plan,"{broken");
        if(kind=="oversized")write(part,payload+"extra");
        if(kind=="linked-marker"){QVERIFY(QFile::rename(plan,outside));QVERIFY(QFile::link(outside,plan));}
        if(kind=="linked-payload"){QVERIFY(QFile::rename(part,outside));QVERIFY(QFile::link(outside,part));}
        if(kind=="linked-directory"){QVERIFY(QDir().rename(folder,outside));QVERIFY(QFile::link(outside,folder));}
        if(kind.startsWith("hardlinked")) {
#ifdef Q_OS_UNIX
            const auto source=kind=="hardlinked-marker"?plan:part;
            QVERIFY(::link(QFile::encodeName(source).constData(),QFile::encodeName(outside).constData())==0);
#else
            QSKIP("Hardlink protection is a POSIX adapter check");
#endif
        }
        if(kind=="empty" || kind=="missing"){QVERIFY(QFile::remove(plan));QVERIFY(QFile::remove(part));if(kind=="missing")QVERIFY(QDir().rmdir(folder));}
        QMap<QString,QByteArray> before;
        QDirIterator files(dir.path(),QDir::Files|QDir::Hidden,QDirIterator::Subdirectories);
        while(files.hasNext()){QFile f(files.next());if(f.open(QIODevice::ReadOnly))before[f.fileName()]=f.readAll();}
        RomCloud cloud(c);const auto facts=cloud.games().first().toMap(),space=cloud.installPlan(1);
        QCOMPARE(facts["partial"].toBool(),kind!="missing");QCOMPARE(facts["resumeAvailable"].toBool(),resumable);
        QCOMPARE(facts["downloadBlocked"].toBool(),blocked);QCOMPARE(space["blocked"].toBool(),blocked);
        QCOMPARE(space["resumeAvailable"].toBool(),resumable);
        if(resumable){QCOMPARE(space["retainedBytes"].toLongLong(),qint64(123));QCOMPARE(space["remainingBytes"].toLongLong(),qint64(payload.size()-123));}
        if(blocked) {
            QVERIFY(!facts["downloadReason"].toString().isEmpty());QVERIFY(!space["spaceKnown"].toBool());
            cloud.install(1);QVERIFY(!cloud.busy());QVERIFY(!QFileInfo::exists(c.root+"/nova-cloud/1"));
            for(auto it=before.cbegin();it!=before.cend();++it){QFile f(it.key());QVERIFY(f.open(QIODevice::ReadOnly));QCOMPARE(f.readAll(),it.value());}
        }
    }
    void configurationStateIsExposedWithoutCredentials() {
        RomCloud unconfigured(RomCloudConfig{});
        QVERIFY(!unconfigured.property("configured").toBool());
        QTemporaryDir dir;QVERIFY(dir.isValid());
        RomCloudConfig config{QUrl("http://127.0.0.1:1"),"synthetic-token",dir.path()+"/roms",dir.path()+"/cache",{}};
        RomCloud configured(config);
        QVERIFY(configured.property("configured").toBool());
        config.root="/";RomCloud invalid(config);
        QVERIFY(!invalid.property("configured").toBool());
    }
    void emptyTokenCannotExposePopulatedCache() {
        QTemporaryDir dir;QVERIFY(dir.isValid());auto config=removalFixture(dir);
        const auto cache=config.cache+"/catalogue.json";
        QFile original(cache);QVERIFY(original.open(QIODevice::ReadOnly));const auto bytes=original.readAll();original.close();
        config.token.clear();RomCloud cloud(config);
        QVERIFY(!cloud.configured());QVERIFY(cloud.games().isEmpty());QVERIFY(!cloud.busy());
        cloud.install(1);QVERIFY(!cloud.busy());QVERIFY(cloud.games().isEmpty());
        QFile after(cache);QVERIFY(after.open(QIODevice::ReadOnly));QCOMPARE(after.readAll(),bytes);
        QVERIFY(QFileInfo::exists(config.root+"/nova-cloud/1/Example.sfc"));
    }
    void validation() {
        QVERIFY(!RomCloud::allowedEndpoint(QUrl("http://example.com")));
        QUrl credentialUrl("https://example.com"); credentialUrl.setUserName("demo"); credentialUrl.setPassword("synthetic");
        QVERIFY(!RomCloud::allowedEndpoint(credentialUrl));
        QVERIFY(!RomCloud::allowedEndpoint(QUrl("https://example.com/prefix")));
        QUrl tailUrl("http://example.com:8080"); tailUrl.setHost(QHostAddress(quint32(0x64400001)).toString());
        QVERIFY(RomCloud::allowedEndpoint(tailUrl));
        QVERIFY(RomCloud::allowedEndpoint(QUrl("http://127.0.0.1:8080")));
        QVERIFY(!RomCloud::safeName("../save.srm")); QVERIFY(!RomCloud::safeName(".srm"));
        QVERIFY(!RomCloud::safeName("C:\\bad")); QVERIFY(!RomCloud::safeName(" a.sfc"));
        QVERIFY(RomCloud::validateGame(game())["supported"].toBool());
        auto g=game();g["files"]=QVariantList{QVariantMap{{"id",3},{"file_name","../save.srm"},{"file_size_bytes",123},{"sha1_hash",QString(40,'a')}}};
        QVERIFY(!RomCloud::validateGame(g)["supported"].toBool());
        QVERIFY(!RomCloud::validateGame(game(1,"Example.iso","ps2"))["supported"].toBool());
        auto coverGame=game();coverGame["path_cover_small"]="//example.com/assets/cover.png";
        QVERIFY(!RomCloud::validateGame(coverGame).contains("coverPath"));
        coverGame["path_cover_small"]="/assets/cover.png?ts=synthetic";
        QVERIFY(RomCloud::validateGame(coverGame).contains("coverPath"));
    }
    void catalogueIdentityBindsOriginAndContentInsteadOfTitle() {
        const QUrl endpoint("https://example.test");auto g=RomCloud::validateGame(game());
        const auto id=RomCloud::editionIdentity(endpoint,g);
        QVERIFY(QRegularExpression("^nova:cloud_[a-f0-9]{64}:1_[a-f0-9]{64}$").match(id).hasMatch());
        auto renamed=g;renamed["title"]="A renamed title";auto files=renamed["files"].toList();
        auto f=files.first().toMap();f["id"]=999;files[0]=f;renamed["files"]=files;
        QCOMPARE(RomCloud::editionIdentity(endpoint,renamed),id);
        QCOMPARE(RomCloud::editionIdentity(QUrl("https://example.test/"),renamed),id);
        QVERIFY(RomCloud::editionIdentity(QUrl("https://different.test"),g)!=id);
        f["hash"]=QString(40,'a');files[0]=f;renamed["files"]=files;
        QVERIFY(RomCloud::editionIdentity(endpoint,renamed)!=id);
        QVERIFY(!id.contains("example"));
    }
    void cachedServerUpdateCannotRenameTheInstalledEdition() {
        QTemporaryDir dir;auto config=removalFixture(dir);RomCloud before(config);
        const auto original=before.games().first().toMap();
        auto newer=RomCloud::validateGame(game());auto files=newer["files"].toList();
        auto f=files.first().toMap();f["hash"]=QString(40,'a');f["bytes"]=payload.size()+99;files[0]=f;
        newer["files"]=files;newer["bytes"]=payload.size()+99;
        QFile cache(config.cache+"/catalogue.json");QVERIFY(cache.open(QIODevice::WriteOnly|QIODevice::Truncate));
        cache.write(QJsonDocument::fromVariant(QVariantMap{{"endpoint",config.endpoint.toString()},{"games",QVariantList{newer}}}).toJson());cache.close();
        RomCloud reopened(config);const auto current=reopened.games().first().toMap();
        QVERIFY(current["installed"].toBool());QVERIFY(current["cloudCopyChanged"].toBool());
        QCOMPARE(current["editionId"],original["editionId"]);QCOMPARE(current["cloudKey"],original["cloudKey"]);
        QCOMPARE(current["bytes"].toLongLong(),qint64(payload.size()));
    }
    void downloadResumeOfflineRemove() { run(false,false); }
    void summaryFetchesDetails() { run(false,false,true); }
    void wrongChecksumNeverActivated() { run(true,false); }
    void rangeIgnoredNeverAppended() { run(false,true); }
    void installedManifestMustDescribeTheLaunchFile_data() {
        QTest::addColumn<QString>("change");
        for(const auto& change:QStringList{"unlisted-entry","linked-marker","missing-hash","duplicate-file","foreign-platform"})
            QTest::newRow(qPrintable(change)) << change;
    }
    void installedManifestMustDescribeTheLaunchFile() {
        QFETCH(QString,change);
        QTemporaryDir dir;auto config=removalFixture(dir);const auto folder=config.root+"/nova-cloud/1";
        QFile marker(folder+"/.nova-install.json");QVERIFY(marker.open(QIODevice::ReadOnly));
        auto data=QJsonDocument::fromJson(marker.readAll()).toVariant().toMap();marker.close();
        if(change=="linked-marker") {
            const auto outside=dir.path()+"/marker.json";
            QVERIFY(QFile::rename(marker.fileName(),outside));QVERIFY(QFile::link(outside,marker.fileName()));
        } else {
            auto files=data["files"].toList();auto file=files.first().toMap();
            if(change=="unlisted-entry") {
                QFile unlisted(folder+"/Unlisted.sfc");QVERIFY(unlisted.open(QIODevice::WriteOnly));unlisted.write(payload);unlisted.close();
                data["entry"]="Unlisted.sfc";
            } else if(change=="missing-hash") {file.remove("hash");files[0]=file;data["files"]=files;}
            else if(change=="duplicate-file") {files.append(file);data["files"]=files;}
            else if(change=="foreign-platform") data["platform"]="ps2";
            QVERIFY(marker.open(QIODevice::WriteOnly|QIODevice::Truncate));
            marker.write(QJsonDocument::fromVariant(data).toJson());marker.close();
        }
        RomCloud cloud(config);QSignalSpy launch(&cloud,&RomCloud::launchRequested);
        QVERIFY(!cloud.games().first().toMap()["installed"].toBool());
        cloud.play(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),0);
        QVERIFY(QFileInfo::exists(folder+"/Example.sfc"));
    }
    void sameSizeCorruptionCannotLaunch() {
        QTemporaryDir dir;auto config=removalFixture(dir);const auto path=config.root+"/nova-cloud/1/Example.sfc";
        QFile changed(path);QVERIFY(changed.open(QIODevice::WriteOnly));changed.write(QByteArray(payload.size(),'y'));changed.close();
        RomCloud cloud(config);QSignalSpy launch(&cloud,&RomCloud::launchRequested);
        cloud.play(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),0);
        QVERIFY2(cloud.message().contains("checksum",Qt::CaseInsensitive),qPrintable(cloud.message()));
        QVERIFY(changed.open(QIODevice::ReadOnly));QCOMPARE(changed.readAll(),QByteArray(payload.size(),'y'));
    }
    void cancellingLaunchCheckNeverOpensTheGame() {
        QTemporaryDir dir;auto config=removalFixture(dir);RomCloud cloud(config);
        QSignalSpy launch(&cloud,&RomCloud::launchRequested);
        cloud.play(1);QVERIFY(cloud.busy());QVERIFY(cloud.launchChecking());cloud.cancel();
        QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QVERIFY(!cloud.launchChecking());QCOMPARE(launch.count(),0);
        cloud.play(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),1);
    }
    void launchCheckRejectsFilesChangedWhileChecking() {
        QTemporaryDir dir;auto config=removalFixture(dir);RomCloud cloud(config);
        QSignalSpy launch(&cloud,&RomCloud::launchRequested);
        cloud.play(1);QVERIFY(cloud.busy());
        QFile changed(config.root+"/nova-cloud/1/Example.sfc");QVERIFY(changed.open(QIODevice::WriteOnly));
        changed.write(QByteArray(payload.size(),'y'));changed.close();
        QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),0);
    }
    void cancellingAfterChecksumStillPreventsLaunch() {
        QTemporaryDir dir;auto config=removalFixture(dir);RomCloud cloud(config);
        QSignalSpy launch(&cloud,&RomCloud::launchRequested);bool cancelled=false;
        connect(&cloud,&RomCloud::changed,this,[&]{
            if(cloud.busy() && cloud.progress()==1){cancelled=true;cloud.cancel();}
        });
        cloud.play(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
        QVERIFY(cancelled);QCOMPARE(launch.count(),0);
    }
    void launchRechecksItsForegroundAndCancellationBoundaries_data() {
        QTest::addColumn<QString>("boundary");
        for(const auto& b:{"unknown-window","already-away","while-hashing","after-checksum","prepared-cancel","prepared-away","requested-cancel","requested-away"})QTest::newRow(b)<<QString(b);
    }
    void launchRechecksItsForegroundAndCancellationBoundaries() {
        QFETCH(QString,boundary);QTemporaryDir dir;auto config=removalFixture(dir);bool foreground=boundary!="already-away",triggered=!foreground || boundary=="unknown-window";int dispatched=0;QString sentPath,sentCore;
        if(boundary!="unknown-window")config.downloadWindow=[&]{return foreground;};
        config.launch=[&](const QString& path,const QString& core){++dispatched;sentPath=path;sentCore=core;return true;};RomCloud cloud(config);
        QSignalSpy prepared(&cloud,&RomCloud::launchPrepared),requested(&cloud,&RomCloud::launchRequested),accepted(&cloud,&RomCloud::launchAccepted);
        connect(&cloud,&RomCloud::changed,this,[&]{if(boundary=="after-checksum" && cloud.busy() && cloud.progress()==1){foreground=false;triggered=true;}});
        connect(&cloud,&RomCloud::launchPrepared,this,[&]{
            if(boundary=="prepared-cancel"){triggered=true;cloud.cancel();}
            if(boundary=="prepared-away"){triggered=true;foreground=false;}
        });
        connect(&cloud,&RomCloud::launchRequested,this,[&]{
            if(boundary=="requested-cancel"){triggered=true;cloud.cancel();}
            if(boundary=="requested-away"){triggered=true;foreground=false;}
        });
        cloud.play(1);
        if(boundary=="while-hashing"){QVERIFY(cloud.busy());foreground=false;triggered=true;}
        QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QVERIFY(triggered);QCOMPARE(accepted.count(),0);QCOMPARE(dispatched,0);
        const bool requestedBoundary=boundary.startsWith("requested-");QCOMPARE(requested.count(),requestedBoundary?1:0);
        QCOMPARE(prepared.count(),boundary.startsWith("prepared-") || requestedBoundary?1:0);
        QVERIFY2(cloud.message().contains(boundary.endsWith("cancel")?"Paused":"Library",Qt::CaseInsensitive),qPrintable(cloud.message()));
        QFile retained(config.root+"/nova-cloud/1/Example.sfc");QVERIFY(retained.open(QIODevice::ReadOnly));QCOMPARE(retained.readAll(),payload);
        // A fresh deliberate retry in the foreground is allowed; an old request is not retried automatically.
        if(boundary=="unknown-window")return;
        disconnect(&cloud,nullptr,this,nullptr);foreground=true;requested.clear();cloud.play(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(requested.count(),1);QCOMPARE(dispatched,1);QCOMPARE(accepted.count(),1);
        QCOMPARE(sentPath,config.root+"/nova-cloud/1/Example.sfc");QCOMPARE(sentCore,QString("snes9x_libretro_android.so"));
    }
    void platformAcceptanceIsSeparateFromGameBoot_data(){QTest::addColumn<bool>("accepted");QTest::newRow("refused")<<false;QTest::newRow("accepted")<<true;}
    void platformAcceptanceIsSeparateFromGameBoot(){
        QFETCH(bool,accepted);QTemporaryDir dir;auto config=removalFixture(dir);int calls=0;
        config.downloadWindow=[]{return true;};config.launch=[&](const QString&,const QString&){++calls;return accepted;};RomCloud cloud(config);
        QSignalSpy observation(&cloud,&RomCloud::launchAccepted);cloud.play(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
        QCOMPARE(calls,1);QCOMPARE(observation.count(),accepted?1:0);
        QVERIFY2(cloud.message().contains(accepted?"not confirmed":"could not accept"),qPrintable(cloud.message()));
    }
    void changedMarkerCannotRedirectPendingLaunch() {
        QTemporaryDir dir;auto config=removalFixture(dir);RomCloud cloud(config);
        QSignalSpy launch(&cloud,&RomCloud::launchRequested);cloud.play(1);QVERIFY(cloud.busy());
        QFile marker(config.root+"/nova-cloud/1/.nova-install.json");QVERIFY(marker.open(QIODevice::ReadOnly));
        auto data=QJsonDocument::fromJson(marker.readAll()).toVariant().toMap();marker.close();data["platform"]="ps";
        QVERIFY(marker.open(QIODevice::WriteOnly|QIODevice::Truncate));marker.write(QJsonDocument::fromVariant(data).toJson());marker.close();
        QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),0);
    }
    void interruptedTransferResumesAfterReopen_data() {
        QTest::addColumn<bool>("pause");
        QTest::newRow("connection-lost") << false;
        QTest::newRow("explicit-pause") << true;
    }
    void interruptedTransferResumesAfterReopen() {
        QFETCH(bool,pause);
        QTemporaryDir dir;QTcpServer server;QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto root=QDir(dir.path()).canonicalPath()+"/roms";QVERIFY(QDir().mkpath(root));
        RomCloudConfig config{QUrl("http://127.0.0.1:"+QString::number(server.serverPort())),"synthetic-token",root,dir.path()+"/cache",{}};
        int downloads=0;bool resumed=false;
        connect(&server,&QTcpServer::newConnection,this,[&]{
            auto socket=server.nextPendingConnection();auto buffer=new QByteArray;
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket,buffer]{
                buffer->append(socket->readAll());if(!buffer->contains("\r\n\r\n"))return;
                const auto request=*buffer;socket->disconnect(socket,nullptr,socket,nullptr);
                QVERIFY(request.contains("Authorization: Bearer synthetic-token"));
                if(request.startsWith("GET /api/roms?")) {
                    const auto body=QJsonDocument::fromVariant(QVariantMap{{"items",QVariantList{game()}}}).toJson();
                    socket->write("HTTP/1.1 200 OK\r\nContent-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);
                    socket->disconnectFromHost();return;
                }
                QVERIFY(request.startsWith("GET /api/roms/3/files/content/Example.sfc "));
                if(++downloads==1) {
                    socket->write("HTTP/1.1 200 OK\r\nContent-Length: 65536\r\nConnection: close\r\n\r\n"+payload.left(123));
                    if(!pause)socket->disconnectFromHost();
                } else {
                    resumed=request.contains("Range: bytes=123-");
                    const auto body=payload.mid(123);
                    socket->write("HTTP/1.1 206 Partial Content\r\nContent-Range: bytes 123-65535/65536\r\nContent-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);
                    socket->disconnectFromHost();
                }
            });
            connect(socket,&QTcpSocket::disconnected,socket,&QObject::deleteLater);
            connect(socket,&QTcpSocket::destroyed,this,[buffer]{delete buffer;});
        });
        {
            RomCloud cloud(config);cloud.refresh();QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
            bool cancelled=false,sawDownloading=false;
            connect(&cloud,&RomCloud::changed,this,[&]{
                if(cloud.busy() && cloud.progress()>0){sawDownloading=true;QCOMPARE(cloud.games().first().toMap()["downloadState"].toString(),QString("downloading"));}
                if(pause && !cancelled && cloud.busy() && cloud.progress()>0){cancelled=true;cloud.cancel();}
            });
            cloud.install(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
            QVERIFY(sawDownloading);QCOMPARE(cloud.games().first().toMap()["downloadState"].toString(),QString("partial"));
            QVERIFY(!cloud.games().first().toMap()["installed"].toBool());
            QCOMPARE(QFileInfo(root+"/nova-cloud/1.partial/Example.sfc").size(),qint64(123));
            QVERIFY(!QFileInfo::exists(root+"/nova-cloud/1/.nova-install.json"));
            if(pause)QVERIFY(cancelled);
        }
        RomCloud reopened(config);QCOMPARE(reopened.games().size(),1);
        QVERIFY(reopened.games().first().toMap()["resumeAvailable"].toBool());
        reopened.install(1);QTRY_VERIFY_WITH_TIMEOUT(!reopened.busy(),3000);
        QVERIFY(resumed);QCOMPARE(downloads,2);
        QVERIFY2(reopened.games().first().toMap()["installed"].toBool(),qPrintable(reopened.message()));
        QFile result(root+"/nova-cloud/1/Example.sfc");QVERIFY(result.open(QIODevice::ReadOnly));QCOMPARE(result.readAll(),payload);
    }
    void multiDiscInstall() { disc(false); }
    void escapingPlaylistNeverActivates() { disc(true); }
    void unconfiguredSpacePlanIsUnknownAndDoesNotWrite() {
        RomCloud cloud;
        const auto plan=cloud.installPlan(999);
        QVERIFY(!plan["spaceKnown"].toBool());QVERIFY(!plan["fits"].toBool());
        QVERIFY(!plan.contains("freeBytes"));QVERIFY(!plan["reason"].toString().isEmpty());
    }
    void absentSelectedRootIsNotRecreatedByInstall_data() {
        QTest::addColumn<QString>("kind");
        for(auto kind:{"configured-but-absent","disappeared-after-review","queued-root-disappeared"})
            QTest::newRow(kind)<<QString(kind);
    }
    void absentSelectedRootIsNotRecreatedByInstall() {
        QFETCH(QString,kind);QTemporaryDir dir;auto c=removalFixture(dir,true);
        c.downloadWindow=[]{return true;};
        RomCloud cloud(c);QVERIFY(cloud.downloadReview(1)["spaceKnown"].toBool());
        if(kind=="queued-root-disappeared")QVERIFY(cloud.enqueueDownload(1));
        const auto retained=c.root+".retained";QVERIFY(QDir().rename(c.root,retained));
        if(kind=="configured-but-absent") {
            // A configured folder that has never been provisioned has the same safe refusal.
            c.root=QDir(dir.path()).canonicalPath()+"/not-provisioned";
        }
        RomCloud absent(c);auto* subject=kind=="configured-but-absent"?&absent:&cloud;
        auto review=subject->downloadReview(1);
        QVERIFY(!review["spaceKnown"].toBool());QVERIFY(!review["fits"].toBool());
        QVERIFY(!QFileInfo::exists(c.root));
        if(kind=="queued-root-disappeared") {subject->startDownloads();QTRY_VERIFY_WITH_TIMEOUT(!subject->queueRunning(),3000);}
        else subject->install(1);
        QVERIFY2(!QFileInfo::exists(c.root),"Install recreated the absent selected storage before checking it");
        QVERIFY(!subject->busy());QVERIFY(subject->message().contains("storage",Qt::CaseInsensitive));
        QFile bytes(retained+"/nova-cloud/1.partial/Example.sfc");QVERIFY(bytes.open(QIODevice::ReadOnly));QCOMPARE(bytes.readAll(),payload.left(123));
        QVERIFY(!QFileInfo::exists(c.root+"/nova-cloud"));
    }
    void retainedRemovalBlocksFreshDownload_data() {
        QTest::addColumn<QString>("suffix");QTest::addColumn<QString>("kind");
        QStringList kinds{"directory","file"};
#ifdef Q_OS_UNIX
        kinds<<"symlink"<<"dangling"<<"fifo";
#endif
        for(const auto& suffix:{QString(".removed"),QString(".partial.removed")})for(const auto& kind:kinds)QTest::newRow(qPrintable(suffix+"-"+kind))<<suffix<<kind;
    }
    void retainedRemovalBlocksFreshDownload() {
        QFETCH(QString,suffix);QFETCH(QString,kind);QTemporaryDir d;auto c=removalFixture(d,true);c.downloadWindow=[]{return true;};const auto held=c.root+"/nova-cloud/1"+suffix,foreign=d.path()+"/foreign";
        auto write=[](const QString& path){QFile f(path);if(!f.open(QIODevice::WriteOnly))qFatal("Owned retained fixture failed");f.write("protected synthetic progress");};
        if(kind=="directory") {QVERIFY(QDir().mkdir(held));write(held+"/late.srm");}
        else if(kind=="file")write(held);
        else if(kind=="symlink") {QVERIFY(QDir().mkdir(foreign));write(foreign+"/late.srm");QVERIFY(QFile::link(foreign,held));}
        else if(kind=="dangling")QVERIFY(QFile::link(foreign,held));
#ifdef Q_OS_UNIX
        else if(kind=="fifo")QCOMPARE(::mkfifo(QFile::encodeName(held).constData(),0600),0);
#endif
        RomCloud cloud(c);QVERIFY(cloud.enqueueDownload(1));const auto plan=cloud.downloadReview(1);QVERIFY(plan["blocked"].toBool());QVERIFY(plan["removalRetained"].toBool());QVERIFY(!plan["fits"].toBool());QVERIFY(!plan["resumeAvailable"].toBool());QVERIFY(plan["reason"].toString().contains("removal recovery"));
        QVERIFY(cloud.games()[0].toMap()["downloadBlocked"].toBool());QCOMPARE(cloud.downloads()[0].toMap()["state"].toString(),QString("blocked"));
        cloud.startDownloads(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.queueRunning(),3000);QVERIFY(!cloud.busy());QVERIFY(cloud.queueMessage().contains("removal recovery"));QVERIFY(!QFileInfo::exists(c.root+"/nova-cloud/1"));
        QFile partial(c.root+"/nova-cloud/1.partial/Example.sfc");QVERIFY(partial.open(QIODevice::ReadOnly));QCOMPARE(partial.readAll(),payload.left(123));
        if(kind=="directory" || kind=="file" || kind=="symlink") {QFile progress(kind=="directory"?held+"/late.srm":kind=="symlink"?foreign+"/late.srm":held);QVERIFY(progress.open(QIODevice::ReadOnly));QCOMPARE(progress.readAll(),QByteArray("protected synthetic progress"));}
        else QVERIFY(QFileInfo::exists(held)||QFileInfo(held).isSymLink());
    }
    void retainedRemovalDoesNotReplaceOrInvalidateCurrentInstalledCopy() {
        QTemporaryDir d;auto c=removalFixture(d);const auto held=c.root+"/nova-cloud/1.removed";QVERIFY(QDir().mkdir(held));QFile keep(held+"/late.srm");QVERIFY(keep.open(QIODevice::WriteOnly));keep.write("keep retained progress");keep.close();RomCloud cloud(c);QVERIFY(cloud.installPlan(1)["installed"].toBool());QVERIFY(cloud.games()[0].toMap()["installed"].toBool());cloud.install(1);QVERIFY(cloud.message().contains("Already downloaded"));QFile rom(c.root+"/nova-cloud/1/Example.sfc");QVERIFY(rom.open(QIODevice::ReadOnly));QCOMPARE(rom.readAll(),payload);QVERIFY(keep.open(QIODevice::ReadOnly));QCOMPARE(keep.readAll(),QByteArray("keep retained progress"));
    }
    void managedRemovalPublishesCurrentDownloadAvailability_data() {
        QTest::addColumn<QString>("kind");
        for(auto kind:{"complete","rollback-refusal","detached-kept"})QTest::newRow(kind)<<QString(kind);
    }
    void managedRemovalPublishesCurrentDownloadAvailability() {
        QFETCH(QString,kind);QTemporaryDir d;auto c=removalFixture(d);int checks=0;
        c.removalBlocker=[&]{
            if(++checks==3 && kind=="rollback-refusal")return QString("Synthetic late idle refusal");
            if(checks==3 && kind=="detached-kept") {QFile save(c.root+"/nova-cloud/1.removed/late.srm");if(!save.open(QIODevice::WriteOnly))qFatal("Synthetic late save failed");save.write("keep-new-save");}
            return QString();
        };
        auto normal=RomCloud::validateGame(game());const auto edition=RomCloud::editionIdentity(c.endpoint,normal);
        const auto scope=QString::fromLatin1(QCryptographicHash::hash((c.endpoint.toString()+"\n"+QDir::cleanPath(c.root)).toUtf8(),QCryptographicHash::Sha256).toHex());
        const auto bytes=QJsonDocument::fromVariant(QVariantMap{{"schema",1},{"scope",scope},{"jobs",QVariantList{QVariantMap{{"id",1},{"editionId",edition},{"title","Synthetic queued game"},{"state","ready"},{"message","Download complete. Files checked."}}}}}).toJson();
        QFile queue(c.cache+"/download-queue.json");QVERIFY(queue.open(QIODevice::WriteOnly));QCOMPARE(queue.write(bytes),qint64(bytes.size()));queue.close();
        RomCloud cloud(c);QCOMPARE(cloud.downloads().size(),1);QVERIFY(cloud.downloads()[0].toMap()["installed"].toBool());
        bool notifiedInstalled=true;QObject::connect(&cloud,&RomCloud::queueChanged,this,[&]{notifiedInstalled=cloud.downloads()[0].toMap()["installed"].toBool();});
        auto plan=cloud.removalPlan(1);QVERIFY(plan["eligible"].toBool());cloud.removeDownload(1,plan["token"].toString());
        const bool retained=kind=="rollback-refusal";QCOMPARE(cloud.downloads()[0].toMap()["installed"].toBool(),retained);QCOMPARE(notifiedInstalled,retained);
        QVERIFY(queue.open(QIODevice::ReadOnly));QCOMPARE(queue.readAll(),bytes);queue.close();
        if(kind=="detached-kept") {QFile save(c.root+"/nova-cloud/1.removed/late.srm");QVERIFY(save.open(QIODevice::ReadOnly));QCOMPARE(save.readAll(),QByteArray("keep-new-save"));QVERIFY(cloud.message().contains("unexpected files remain"));}
        else if(retained) {QFile payloadFile(c.root+"/nova-cloud/1/Example.sfc");QVERIFY(payloadFile.open(QIODevice::ReadOnly));QCOMPARE(payloadFile.readAll(),payload);}
        else QVERIFY(!QFileInfo::exists(c.root+"/nova-cloud/1"));
    }
    void removalRequiresIdleAdapterAndFreshReview() {
        QTemporaryDir d;auto c=removalFixture(d);c.removalBlocker={};RomCloud protectedCloud(c);
        auto blocked=protectedCloud.removalPlan(1);QVERIFY(!blocked["eligible"].toBool());QVERIFY(blocked["bytesKnown"].toBool());
        QVERIFY(!blocked.contains("token"));QVERIFY(!blocked.contains("_path"));
        c.removalBlocker=[]{return QString();};RomCloud cloud(c);auto plan=cloud.removalPlan(1);
        QVERIFY2(plan["eligible"].toBool(),qPrintable(plan["reason"].toString()));QCOMPARE(plan["bytes"].toLongLong(),qint64(payload.size()));
        cloud.removeDownload(1);QVERIFY(QFileInfo::exists(c.root+"/nova-cloud/1"));
        cloud.removeDownload(1,"1:"+plan["token"].toString().section(':',1));QVERIFY(QFileInfo::exists(c.root+"/nova-cloud/1"));
        cloud.removeDownload(1,plan["token"].toString());QVERIFY(!QFileInfo::exists(c.root+"/nova-cloud/1"));
    }
    void changedFilesAndBusyRuntimeAreProtected() {
        QTemporaryDir d;auto c=removalFixture(d);QString blocker;c.removalBlocker=[&]{return blocker;};RomCloud cloud(c);
        auto plan=cloud.removalPlan(1);blocker="A synthetic game is active";cloud.removeDownload(1,plan["token"].toString());
        QVERIFY(QFileInfo::exists(c.root+"/nova-cloud/1"));blocker.clear();plan=cloud.removalPlan(1);
        QFile changed(c.root+"/nova-cloud/1/Example.sfc");QVERIFY(changed.open(QIODevice::WriteOnly));changed.write(QByteArray(payload.size(),'y'));changed.close();
        cloud.removeDownload(1,plan["token"].toString());QVERIFY(QFileInfo::exists(changed.fileName()));
        QVERIFY(cloud.message().contains("changed"));
    }
    void extraSaveAndForgedMetadataAreProtected() {
        QTemporaryDir d;auto c=removalFixture(d);RomCloud cloud(c);
        QFile save(c.root+"/nova-cloud/1/owner.srm");QVERIFY(save.open(QIODevice::WriteOnly));save.write("owner-save");save.close();
        QVERIFY(!cloud.removalPlan(1)["eligible"].toBool());QVERIFY(save.remove());
        QFile marker(c.root+"/nova-cloud/1/.nova-install.json");QVERIFY(marker.open(QIODevice::ReadOnly));auto data=QJsonDocument::fromJson(marker.readAll()).object().toVariantMap();marker.close();
        data["endpoint"]="https://other.example";QVERIFY(marker.open(QIODevice::WriteOnly|QIODevice::Truncate));marker.write(QJsonDocument::fromVariant(data).toJson());marker.close();
        QVERIFY(!cloud.removalPlan(1)["eligible"].toBool());
    }
    void cleanupPreviewListsPartialWithoutChangingIt() {
        QTemporaryDir d;auto c=removalFixture(d,true);RomCloud cloud(c);auto plan=cloud.cleanupPlan(999);
        auto candidates=plan["candidates"].toList();QCOMPARE(candidates.size(),1);
        QCOMPARE(candidates.first().toMap()["bytes"].toLongLong(),qint64(123));
        QVERIFY(candidates.first().toMap()["partial"].toBool());QVERIFY(QFileInfo::exists(c.root+"/nova-cloud/1.partial/Example.sfc"));
        QVERIFY(cloud.cleanupPlan(1)["candidates"].toList().isEmpty());
    }
    void ownershipCannotClaimSaveFiles() {
        QTemporaryDir d;auto c=removalFixture(d);RomCloud cloud(c);
        const auto folder=c.root+"/nova-cloud/1";
        QVERIFY(QFile::rename(folder+"/Example.sfc",folder+"/owner.srm"));
        QFile marker(folder+"/.nova-install.json");QVERIFY(marker.open(QIODevice::ReadOnly));
        auto data=QJsonDocument::fromJson(marker.readAll()).object().toVariantMap();marker.close();
        auto files=data["files"].toList();auto file=files.first().toMap();file["name"]="owner.srm";files[0]=file;
        data["files"]=files;data["entry"]="owner.srm";
        QVERIFY(marker.open(QIODevice::WriteOnly|QIODevice::Truncate));marker.write(QJsonDocument::fromVariant(data).toJson());marker.close();
        const auto plan=cloud.removalPlan(1);QVERIFY(!plan["eligible"].toBool());QVERIFY(!plan.contains("token"));
        cloud.removeDownload(1,plan["token"].toString());QVERIFY(QFileInfo::exists(folder+"/owner.srm"));
    }
    void linkedMarkerAndLegacyPartialRemainProtected() {
        QTemporaryDir d;auto c=removalFixture(d,true);RomCloud cloud(c);
        const auto path=c.root+"/nova-cloud/1.partial/.plan.json";
        QFile marker(path);QVERIFY(marker.open(QIODevice::ReadOnly));
        auto data=QJsonDocument::fromJson(marker.readAll()).object().toVariantMap();marker.close();
        data.remove("endpoint");QVERIFY(marker.open(QIODevice::WriteOnly|QIODevice::Truncate));
        marker.write(QJsonDocument::fromVariant(data).toJson());marker.close();
        QVERIFY(!cloud.removalPlan(1)["eligible"].toBool());
        data["endpoint"]=c.endpoint.toString();QVERIFY(marker.open(QIODevice::WriteOnly|QIODevice::Truncate));
        marker.write(QJsonDocument::fromVariant(data).toJson());marker.close();
        const auto outside=d.path()+"/original-plan.json";QVERIFY(QFile::rename(path,outside));QVERIFY(QFile::link(outside,path));
        QVERIFY(QFileInfo(path).isSymLink());QVERIFY(!cloud.removalPlan(1)["eligible"].toBool());
        QVERIFY(QFileInfo::exists(outside));QVERIFY(QFileInfo::exists(c.root+"/nova-cloud/1.partial/Example.sfc"));
    }
    void newlyArrivingFilesAreNeverSweptRecursively() {
        QTemporaryDir d;auto c=removalFixture(d);int checks=0;
        c.removalBlocker=[&]{if(++checks==3){QFile save(c.root+"/nova-cloud/1.removed/late.srm");if(!save.open(QIODevice::WriteOnly))qFatal("Synthetic arrival failed");save.write("keep-new-save");}return QString();};
        RomCloud cloud(c);auto plan=cloud.removalPlan(1);cloud.removeDownload(1,plan["token"].toString());
        QFile save(c.root+"/nova-cloud/1.removed/late.srm");QVERIFY(save.open(QIODevice::ReadOnly));QCOMPARE(save.readAll(),QByteArray("keep-new-save"));
    }
    void disc(bool escape) {
        QTemporaryDir dir; QTcpServer server; QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto root=QDir(dir.path()).canonicalPath()+"/roms";QVERIFY(QDir().mkpath(root));
        QMap<QString,QByteArray> bytes{{"disc-1.chd","synthetic disc one"},{"disc-2.chd","synthetic disc two"},{"two-discs.m3u",escape?QByteArray("../foreign.chd\n"):QByteArray("disc-1.chd\ndisc-2.chd\n")}};
        QVariantList files;int fid=1;
        for(auto it=bytes.cbegin();it!=bytes.cend();++it)files.append(QVariantMap{{"id",fid++},{"file_name",it.key()},{"file_size_bytes",it.value().size()},{"sha1_hash",QString(QCryptographicHash::hash(it.value(),QCryptographicHash::Sha1).toHex())}});
        QVariantMap item{{"id",9},{"name","Synthetic Disc Set"},{"fs_name","folder-name"},{"platform_slug","ps"},{"platform_display_name","PlayStation"},{"files",files}};
        auto normalized=RomCloud::validateGame(item);QVERIFY(normalized["supported"].toBool());QCOMPARE(normalized["entry"].toString(),QString("two-discs.m3u"));
        connect(&server,&QTcpServer::newConnection,this,[&]{auto socket=server.nextPendingConnection();auto buffer=new QByteArray;
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket,buffer]{buffer->append(socket->readAll());if(!buffer->contains("\r\n\r\n"))return;
                QByteArray body;const auto target=buffer->split(' ').value(1);
                if(target.startsWith("/api/roms?"))body=QJsonDocument::fromVariant(QVariantMap{{"items",QVariantList{item}}}).toJson();
                else {const auto name=QUrl::fromPercentEncoding(target.mid(target.lastIndexOf('/')+1));QVERIFY(bytes.contains(name));body=bytes[name];}
                socket->disconnect(socket,nullptr,socket,nullptr);socket->write("HTTP/1.1 200 OK\r\nContent-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n"+body);socket->disconnectFromHost();
            });connect(socket,&QTcpSocket::destroyed,this,[buffer]{delete buffer;});});
        RomCloud cloud(RomCloudConfig{QUrl("http://127.0.0.1:"+QString::number(server.serverPort())),"synthetic-token",root,dir.path()+"/cache",[]{return QString();}});
        cloud.refresh();QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);cloud.install(9);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);
        QCOMPARE(cloud.games().first().toMap()["installed"].toBool(),!escape);
        QVERIFY(QFileInfo::exists(root+"/nova-cloud/9")==!escape);
        if(escape){QVERIFY(cloud.games().first().toMap()["partial"].toBool());cloud.removeDownload(9,cloud.removalPlan(9)["token"].toString());QVERIFY(!QFileInfo::exists(root+"/nova-cloud/9.partial"));}
        else {
            QSignalSpy launch(&cloud,&RomCloud::launchRequested);cloud.play(9);
            QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),1);launch.clear();
            // A valid first disc and playlist cannot conceal a damaged later disc.
            QFile changed(root+"/nova-cloud/9/disc-2.chd");QVERIFY(changed.open(QIODevice::WriteOnly));
            changed.write(QByteArray(bytes["disc-2.chd"].size(),'y'));changed.close();
            cloud.play(9);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),0);
            QVERIFY(cloud.message().contains("checksum",Qt::CaseInsensitive));
        }
    }
    void run(bool corrupt,bool ignoreRange,bool summary=false) {
        QTemporaryDir dir;QVERIFY(dir.isValid()); QTcpServer server;QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto root=QDir(dir.path()).canonicalPath()+"/roms";QVERIFY(QDir().mkpath(root));
        RomCloudConfig config{QUrl("http://127.0.0.1:"+QString::number(server.serverPort())),"synthetic-token",root,dir.path()+"/cache",[]{return QString();}};
        bool gotRange=false;
        connect(&server,&QTcpServer::newConnection,this,[&]{
            auto socket=server.nextPendingConnection();auto buffer=new QByteArray;
            connect(socket,&QTcpSocket::readyRead,socket,[&,socket,buffer]{
                buffer->append(socket->readAll());if(!buffer->contains("\r\n\r\n"))return;
                const auto req=*buffer;socket->disconnect(socket,nullptr,socket,nullptr);
                QVERIFY(req.contains("Authorization: Bearer synthetic-token"));
                QByteArray body;QByteArray headers="HTTP/1.1 200 OK\r\n";
                if(req.startsWith("GET /api/roms?")) {auto item=game();if(summary)item.remove("files");body=QJsonDocument::fromVariant(QVariantMap{{"items",QVariantList{item}}}).toJson();}
                else if(req.startsWith("GET /api/roms/1 "))body=QJsonDocument::fromVariant(game()).toJson();
                else {
                    QVERIFY(req.startsWith("GET /api/roms/3/files/content/Example.sfc "));
                    gotRange=req.contains("Range: bytes=123-"); body=payload;
                    if(corrupt)body[1000]='y';
                    if(gotRange&&!ignoreRange){headers="HTTP/1.1 206 Partial Content\r\nContent-Range: bytes 123-65535/65536\r\n";body=body.mid(123);}
                }
                headers+="Content-Length: "+QByteArray::number(body.size())+"\r\nConnection: close\r\n\r\n";
                socket->write(headers+body);socket->disconnectFromHost();
            });
            connect(socket,&QTcpSocket::destroyed,this,[buffer]{delete buffer;});
        });
        RomCloud cloud(config);cloud.refresh();QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(cloud.games().size(),1);
        const auto initial=cloud.installPlan(1);
        QVERIFY(!QFileInfo::exists(root+"/nova-cloud")); // Preview is read-only.
        if(!summary) {
            QVERIFY(initial["spaceKnown"].toBool());QCOMPARE(initial["remainingBytes"].toLongLong(),qint64(payload.size()));
            QCOMPARE(initial["headroomBytes"].toLongLong(),qint64(128)*1024*1024);
            QVERIFY(initial["freeBytes"].toLongLong()>=0);QVERIFY(!initial["observedAt"].toString().isEmpty());
        } else QVERIFY(!initial["spaceKnown"].toBool());
        // Simulate a process stopping midway. The durable plan, not an invented marker, owns the partial file.
        auto normal=RomCloud::validateGame(game());QVERIFY(QDir().mkpath(root+"/nova-cloud/1.partial"));
        QFile plan(root+"/nova-cloud/1.partial/.plan.json");QVERIFY(plan.open(QIODevice::WriteOnly));plan.write(QJsonDocument::fromVariant(normal).toJson());plan.close();
        QFile partial(root+"/nova-cloud/1.partial/Example.sfc");QVERIFY(partial.open(QIODevice::WriteOnly));partial.write(payload.left(123));partial.close();
        if(!summary) {
            const auto resumed=cloud.installPlan(1);
            QCOMPARE(resumed["retainedBytes"].toLongLong(),qint64(123));
            QCOMPARE(resumed["remainingBytes"].toLongLong(),qint64(payload.size()-123));
            QFile checkPlan(plan.fileName());QVERIFY(checkPlan.open(QIODevice::ReadOnly));
            QCOMPARE(QJsonDocument::fromJson(checkPlan.readAll()).toVariant().toMap(),normal);
        }
        cloud.install(1);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QVERIFY2(gotRange,qPrintable(cloud.message()));
        if(corrupt||ignoreRange){QVERIFY(!cloud.games().first().toMap()["installed"].toBool());QVERIFY(!QFileInfo::exists(root+"/nova-cloud/1"));if(ignoreRange)QCOMPARE(QFileInfo(partial.fileName()).size(),qint64(123));return;}
        QVERIFY(cloud.games().first().toMap()["installed"].toBool());
        QSignalSpy launch(&cloud,&RomCloud::launchRequested),prepared(&cloud,&RomCloud::launchPrepared),accepted(&cloud,&RomCloud::launchAccepted);
        cloud.play(1);QCOMPARE(prepared.count(),0);QTRY_VERIFY_WITH_TIMEOUT(!cloud.busy(),3000);QCOMPARE(launch.count(),1);QCOMPARE(prepared.count(),1);
        QCOMPARE(prepared.first()[0].toString(),cloud.games().first().toMap()["editionId"].toString());
        QCOMPARE(accepted.count(),0); // A desktop request never pretends Android accepted a launch.
        server.close();RomCloud offline(config);QCOMPARE(offline.games().size(),1);QVERIFY(offline.games().first().toMap()["installed"].toBool());
        // Protect saves even when someone unexpectedly places one beside a ROM.
        QFile unexpected(root+"/nova-cloud/1/owner.srm");QVERIFY(unexpected.open(QIODevice::WriteOnly));unexpected.write("owner-save");unexpected.close();
        offline.removeDownload(1,offline.removalPlan(1)["token"].toString());QVERIFY(QFileInfo::exists(unexpected.fileName()));QVERIFY(offline.games().first().toMap()["installed"].toBool());
        QVERIFY(unexpected.remove());QVERIFY(QDir().mkpath(root+"/../saves"));QFile save(root+"/../saves/Example.srm");QVERIFY(save.open(QIODevice::WriteOnly));save.write("owner-save");save.close();
        offline.removeDownload(1,offline.removalPlan(1)["token"].toString());QVERIFY(!QFileInfo::exists(root+"/nova-cloud/1"));QVERIFY(save.open(QIODevice::ReadOnly));QCOMPARE(save.readAll(),QByteArray("owner-save"));
    }
};
QTEST_GUILESS_MAIN(Tests)
#include "tst_RomCloud.moc"
