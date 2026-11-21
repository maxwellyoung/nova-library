// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariantMap>
#include <QMutex>
#include <QSharedPointer>
#include <QByteArray>
class QThread;

namespace library {
struct SaveCopyPictureData {
    QMutex mutex;
    QString token;
    QByteArray bytes;
};
// Reads operator-delivered private bundles. No capture, network or restore API.
class SaveCopies : public QObject {
    Q_OBJECT
public:
    explicit SaveCopies(const QString& privateRoot, QObject* parent = nullptr);
    ~SaveCopies() override;
    Q_INVOKABLE QVariantMap capabilities() const;
    Q_INVOKABLE QVariantMap openEdition(const QString& editionId) const;
    Q_INVOKABLE QVariantMap review(const QString& editionId, const QString& checkpointId);
    Q_INVOKABLE QVariantMap reviewSnapshot(const QString& editionId, const QString& checkpointId, const QString& indexSha256);
    Q_INVOKABLE QVariantMap picture(const QString& editionId, const QString& checkpointId, const QString& indexSha256) const;
    Q_INVOKABLE void clearPicture() const;
    QSharedPointer<SaveCopyPictureData> pictureData() const {return m_pictureData;}
    Q_INVOKABLE void cancelReview();
signals:
    void operationObserved(const QString& edition, const QString& checkpoint, const QString& indexSha256, const QVariantMap& result) const;
    void reviewFinished(const QString& token, const QVariantMap& result);
private:
    QVariantMap observedResult(const QString& edition, const QString& checkpoint, const QString& indexSha256, const QVariantMap& result) const;
    QVariantMap startReview(const QString& editionId, const QString& checkpointId, const QString& indexSha256);
    QString m_root;
    QThread* m_worker = nullptr;
    quint64 m_sequence = 0;
    QSharedPointer<SaveCopyPictureData> m_pictureData;
};
}
