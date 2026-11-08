// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariantList>
#include <QUrl>
#include <QNetworkAccessManager>
#include <QFile>
#include <QSet>
#include <functional>
#include <QPointer>
class QThread;
namespace library {
struct RomCloudConfig {
    QUrl endpoint; QByteArray token; QString root; QString cache;
    // Empty text means a trusted adapter established idle; no adapter means unknown.
    std::function<QString()> removalBlocker;
    // A foreground download window is distinct from emulator-idle/removal proof.
    std::function<bool()> downloadWindow;
};
class RomCloud : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantList games READ games NOTIFY changed)
    Q_PROPERTY(QString message READ message NOTIFY changed)
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(bool configured READ configured CONSTANT)
    Q_PROPERTY(double progress READ progress NOTIFY changed)
    Q_PROPERTY(int catalogueVersion READ catalogueVersion CONSTANT)
    Q_PROPERTY(bool launchChecking READ launchChecking NOTIFY changed)
    Q_PROPERTY(int queueVersion READ queueVersion CONSTANT)
    Q_PROPERTY(QVariantList downloads READ downloads NOTIFY queueChanged)
    Q_PROPERTY(bool queueRunning READ queueRunning NOTIFY queueChanged)
    Q_PROPERTY(QString queueMessage READ queueMessage NOTIFY queueChanged)
public:
    explicit RomCloud(QObject* parent = nullptr);
    RomCloud(const RomCloudConfig&, QObject* parent = nullptr);
    ~RomCloud() override;
    QVariantList games() const;
    QString message() const { return m_message; }
    bool busy() const { return m_busy; }
    bool configured() const { return !m_config.token.isEmpty(); }
    double progress() const { return m_progress; }
    int catalogueVersion() const { return 1; }
    bool launchChecking() const { return m_launchChecking; }
    int queueVersion() const { return 1; }
    QVariantList downloads() const;
    bool queueRunning() const { return m_queueRunning; }
    QString queueMessage() const { return m_queueMessage; }
    Q_INVOKABLE bool enqueueDownload(int id);
    Q_INVOKABLE void startDownloads(int firstId = 0);
    Q_INVOKABLE void pauseDownloads();
    Q_INVOKABLE bool removeQueuedDownload(int id);
    Q_INVOKABLE void reevaluateDownloadWindow();
    Q_INVOKABLE void refresh();
    Q_INVOKABLE void install(int id);
    Q_INVOKABLE void cancel();
    Q_INVOKABLE void removeDownload(int id, const QString& previewToken = QString());
    Q_INVOKABLE void play(int id);
    Q_INVOKABLE void requestCover(int id);
    Q_INVOKABLE QVariantMap installPlan(int id) const;
    Q_INVOKABLE QVariantMap removalPlan(int id) const;
    Q_INVOKABLE QVariantMap cleanupPlan(int installId) const;
    static bool allowedEndpoint(const QUrl&);
    static bool safeName(const QString&);
    static QVariantMap validateGame(const QVariantMap&);
    static QString editionIdentity(const QUrl&, const QVariantMap&);
signals:
    void changed();
    void queueChanged();
    void launchRequested(const QString& path, const QString& core);
    void launchPrepared(const QString& editionId, const QString& title, const QString& platform);
    void launchAccepted(const QString& editionId);
private:
    void loadCache();
    bool writeCache();
    void page(int offset);
    void details(int id);
    void nextFile();
    void verify(const QString&, const QByteArray&, const std::function<void(bool)>&);
    void fail(const QString&);
    QString gamePath(int id) const;
    QVariantMap installedManifest(int id) const;
    bool ownedInstalled(int id) const;
    QVariantMap partialPlan(const QVariantMap& game) const;
    void loadQueue();
    bool saveQueue(const QVariantList& jobs);
    QString queueScope() const;
    int queueIndex(int id) const;
    QVariantMap queueGame(int id) const;
    void pumpDownloads();
    void finishQueuedDownload(bool success, const QString& message);
    void verifyLaunch(int id, const QVariantMap&, const QVariantList&, int index);
    bool safeDirectory(const QString&, bool create = false) const;
    QVariantMap inspectRemoval(int id, const QString& path, bool partial) const;
    QNetworkRequest request(const QString&) const;
    RomCloudConfig m_config;
    QNetworkAccessManager m_network;
    QVariantList m_games, m_pending, m_files;
    QPointer<QNetworkReply> m_reply, m_coverReply;
    QPointer<QThread> m_verifier;
    QSet<int> m_coverTried;
    QFile m_file;
    QString m_message = QStringLiteral("Connect a private ROM library to browse and download games.");
    bool m_busy = false;
    bool m_cancelled = false;
    bool m_launchChecking = false;
    double m_progress = 0;
    int m_installId = 0, m_fileIndex = 0;
    qint64 m_completed = 0, m_total = 0;
    QVariantList m_downloads;
    QByteArray m_queueFingerprint;
    bool m_queueReadable = true, m_queueRunning = false, m_queuePauseRequested = false;
    int m_queueActiveId = 0, m_queuePreferredId = 0;
    QString m_queueMessage = QStringLiteral("Downloads are paused. Start when ready.");
};
}
