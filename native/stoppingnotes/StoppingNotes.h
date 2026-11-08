// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariantMap>

namespace library {
// An opt-in local store. It is deliberately independent of DeviceLibrary and sync.
class StoppingNotes : public QObject {
    Q_OBJECT
public:
    explicit StoppingNotes(const QString& privateRoot, QObject* parent = nullptr, const QString& screenshotsRoot = QString());
    Q_INVOKABLE QVariantMap capabilities() const;
    Q_INVOKABLE QVariantMap imageChoices() const;
    Q_INVOKABLE QVariantMap openEdition(const QString& editionId, const QVariantMap& legacyCheckpoint = {}) const;
    Q_INVOKABLE QVariantMap importOriginal(const QString& editionId, const QString& localUrl, const QVariant& expectedRevision);
    Q_INVOKABLE QVariantMap createNote(const QString& editionId, const QVariantMap& draft, const QVariant& expectedRevision);
    Q_INVOKABLE QVariantMap editNote(const QString& editionId, const QString& noteId, const QVariantMap& draft, const QVariant& expectedRevision);
    Q_INVOKABLE QVariantMap clearNote(const QString& editionId, const QString& noteId, const QVariant& expectedRevision);
    Q_INVOKABLE QVariantMap restoreNote(const QString& editionId, const QString& noteId, const QVariant& expectedRevision);
    Q_INVOKABLE QVariantMap setStoppingNote(const QString& editionId, const QString& noteId, const QVariant& expectedRevision);
    Q_INVOKABLE QVariantMap adoptLegacy(const QString& editionId, const QVariantMap& legacyCheckpoint, const QVariant& expectedRevision);
    Q_INVOKABLE QVariantMap search(const QString& editionId, const QString& query, bool includeCleared = false) const;
    Q_INVOKABLE QVariantMap exportEdition(const QString& editionId, const QString& newLocalDirectory) const;
private:
    QString m_root, m_error, m_screenshots;
    QString directory(const QString& editionId) const;
    QString load(const QString& editionId, QVariantMap* document) const;
    QString save(const QString& editionId, QVariantMap* document) const;
    QVariantMap view(const QVariantMap& document) const;
    QVariantMap change(const QString& editionId, const QString& noteId, const QVariantMap& draft,
                       const QVariant& expectedRevision, const QString& operation);
};
}
