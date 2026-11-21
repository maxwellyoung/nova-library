// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QByteArray>
#include <QString>
#include <QVariantMap>
#include <functional>

namespace library {
// Only the platform supplies this one-document writer. It opens/writes/closes
// on a worker after current approval is checked; QML cannot supply a target.
using DocumentTarget = std::function<QVariantMap(const QByteArray&, const std::function<bool()>&)>;
using DocumentReceiver = std::function<void(DocumentTarget, const QString&)>;
using DocumentPicker = std::function<bool(const QString&, DocumentReceiver)>;
DocumentPicker failureDocumentPicker();
QVariantMap writeFailureDocument(int descriptor, const QByteArray& bytes,
                                const std::function<bool()>& cancelled = [] { return false; });
}
