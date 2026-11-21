// Pegasus Frontend
// Copyright (C) 2017-2018  Mátyás Mustoha
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <http://www.gnu.org/licenses/>.


// NOVA_CHECKED_THEME_MEMORY_V1: preserve last committed preferences on refusal.
#include "Memory.h"
#include "Paths.h"
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJSValue>
#include <QLockFile>
#include <QSaveFile>
#include <QStringBuilder>

namespace {
const qint64 MaxBytes = 4 * 1024 * 1024;
QString default_settings_dir()
{
    return paths::writableConfigDir() % QStringLiteral("/theme_settings/");
}
QString json_path_for(const QString& dir, const QString& theme)
{
    return QDir(dir).filePath(theme + QStringLiteral(".json"));
}
}
namespace model {
Memory::Memory(QObject* parent) : Memory(default_settings_dir(), parent) {}
Memory::Memory(QString dir, QObject* parent) : QObject(parent), m_settings_dir(std::move(dir)) {}

bool Memory::readDisk(QByteArray& bytes, bool& exists) const
{
    if (m_current_theme.isEmpty() || QFileInfo(m_settings_dir).isSymLink()) return false;
    const QFileInfo info(json_path_for(m_settings_dir, m_current_theme));
    if (info.isSymLink()) return false;
    exists = info.exists(); bytes.clear();
    if (!exists) return true;
    if (!info.isFile() || info.size() > MaxBytes) return false;
    QFile file(info.filePath());
    if (!file.open(QIODevice::ReadOnly)) return false;
    bytes = file.read(MaxBytes + 1);
    return file.error() == QFile::NoError && bytes.size() <= MaxBytes;
}
bool Memory::unchanged() const
{
    QByteArray bytes; bool exists = false;
    return m_readable && readDisk(bytes, exists) && exists == m_disk_exists && bytes == m_disk_bytes;
}
QVariantMap Memory::checkedRead(const QString& key) const
{
    if (!unchanged()) return {{"ok", false}, {"error", "preferences_unavailable"}};
    QVariantMap result{{"ok", true}, {"exists", m_data.contains(key)}};
    if (m_data.contains(key)) result.insert("value", m_data.value(key));
    return result;
}
bool Memory::commit(const QVariantMap& next)
{
    if (!m_readable || m_current_theme.isEmpty() || QFileInfo(m_settings_dir).isSymLink()
            || !QDir(m_settings_dir).mkpath(QStringLiteral("."))) return false;
    const QString path = json_path_for(m_settings_dir, m_current_theme);
    QLockFile lock(path + QStringLiteral(".nova-lock"));
    if (!lock.tryLock(0) || !unchanged()) return false;
    const QByteArray bytes = QJsonDocument::fromVariant(next).toJson(QJsonDocument::Compact);
    if (bytes.size() > MaxBytes) return false;
    QSaveFile file(path); file.setDirectWriteFallback(false);
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit()) return false;
    m_data = next; m_disk_bytes = bytes; m_disk_exists = true;
    emit dataChanged(); return true;
}
QVariant Memory::get(const QString& key) const { return m_data.value(key); }
bool Memory::has(const QString& key) const { return m_data.contains(key); }
bool Memory::checkedSet(const QString& key, QVariant value)
{
    if (key.isEmpty() || !value.isValid()) return false;
    if (value.userType() == qMetaTypeId<QJSValue>()) value = value.value<QJSValue>().toVariant();
    if (!value.isValid()) return false;
    auto next = m_data; next[key] = std::move(value); return commit(next);
}
bool Memory::checkedUnset(const QString& key)
{
    if (!m_data.contains(key)) return false;
    auto next = m_data; next.remove(key); return commit(next);
}
void Memory::set(const QString& key, QVariant value) { checkedSet(key, std::move(value)); }
void Memory::unset(const QString& key) { checkedUnset(key); }
void Memory::changeTheme(const QString& root)
{
    // Preserve upstream folder-name identity, but never turn an invalid load into writable empty storage.
    const QString clean = QDir::cleanPath(root);
    m_current_theme = QFileInfo(clean).fileName();
    m_data.clear(); m_disk_bytes.clear(); m_disk_exists = false; m_readable = false;
    if (m_current_theme.isEmpty() || m_current_theme == QStringLiteral("..")
            || m_current_theme == QStringLiteral(".")) { emit dataChanged(); return; }
    QByteArray bytes; bool exists = false;
    if (readDisk(bytes, exists)) {
        QJsonParseError error;
        const auto doc = exists ? QJsonDocument::fromJson(bytes, &error) : QJsonDocument(QJsonObject());
        if (!exists || (error.error == QJsonParseError::NoError && doc.isObject())) {
            m_data = doc.object().toVariantMap(); m_disk_bytes = bytes; m_disk_exists = exists; m_readable = true;
        }
    }
    emit dataChanged();
}
} // namespace model
