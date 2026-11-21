// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariantMap>
#include <QByteArray>
#include "DocumentCopy.h"
#include <QPointer>
#include <QQmlError>
class QThread;
namespace library {
// Native observations only. No raw log/config/save input or send API in QML.
class FailureReports : public QObject {
    Q_OBJECT
    Q_PROPERTY(int revision READ revision NOTIFY observationChanged)
    Q_PROPERTY(bool documentCopyBusy READ documentCopyBusy NOTIFY documentCopyChanged)
public:
    explicit FailureReports(const QString& privateDataRoot, QObject* parent = nullptr);
    FailureReports(const QString& privateDataRoot, DocumentPicker picker, QObject* parent = nullptr);
    ~FailureReports() override;
    void observeSaveCopies(const QString& edition, const QString& checkpoint,
                           const QString& indexSha256, const QVariantMap& result);
    void observeCloudPlay(const QString& edition, const QString& attempt, const QString& code);
    // Bound only by the compiled frontend; QML cannot supply a failure or source.
    void bindThemeLoader(QObject* loader);
    void observeThemeWarnings(const QList<QQmlError>& errors);
    Q_INVOKABLE void beginThemeLoad();
    Q_INVOKABLE bool captureThemeFailure();
    Q_INVOKABLE void clearThemeFailure();
    Q_INVOKABLE bool themeFailureAvailable() const;
    Q_INVOKABLE QVariantMap previewThemeFailure();
    int revision() const { return m_revision; }
    bool documentCopyBusy() const { return m_documentBusy; }
    Q_INVOKABLE QVariantMap capabilities() const;
    Q_INVOKABLE bool available(const QString& edition, const QString& checkpoint, const QString& indexSha256) const;
    Q_INVOKABLE QVariantMap preview(const QString& edition, const QString& checkpoint, const QString& indexSha256);
    Q_INVOKABLE bool cloudPlayAvailable(const QString& edition, const QString& attempt) const;
    Q_INVOKABLE QVariantMap previewCloudPlay(const QString& edition, const QString& attempt);
    Q_INVOKABLE void cancelPreview(const QString& ticket);
    Q_INVOKABLE QVariantMap exportPreview(const QString& ticket, const QString& sha256);
    Q_INVOKABLE QVariantMap copyPrivateExport(const QString& copyToken, const QString& sha256);
signals:
    void observationChanged();
    void documentCopyChanged();
    void documentCopyFinished(const QString& request, const QVariantMap& result);
private:
    void resetObservation();
    void retain(const QString& edition, const QString& recipe, const QString& origin,
                const QString& code, const QString& statement, const QString& hint,
                const QVariantMap& localEvidence = {});
    QVariantMap makePreview();
    void finishDocumentCopy(const QString& request, const QVariantMap& result);
    QString m_root, m_editionHash, m_checkpoint, m_index, m_ticket;
    QString m_scope;
    QString m_copyToken, m_copyName, m_copySha, m_documentRequest;
    bool m_documentBusy = false;
    bool m_documentSelectionPending = false;
    DocumentPicker m_documentPicker;
    QPointer<QThread> m_documentWorker;
    QPointer<QObject> m_themeLoader;
    QString m_themeSelection;
    QString m_diagnosticSelection;
    QVariantList m_themeDiagnostics;
    QVariantMap m_lastCloudPreflight;
    bool m_collectThemeDiagnostics = false;
    bool m_themeDiagnosticsTruncated = false;
    int m_revision = 0;
    QByteArray m_bytes;
};
}
