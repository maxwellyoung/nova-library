// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariantList>
#include <functional>
namespace library {
struct PcRuntimePlatform {
    std::function<QVariantList()> inspect;
    std::function<bool()> foreground;
    std::function<QVariantMap(const QString&,int,const QString&)> dispatch;
};
class PcRuntime final : public QObject {
    Q_OBJECT
    Q_PROPERTY(int capabilityVersion READ capabilityVersion CONSTANT)
    Q_PROPERTY(QVariantList runtimes READ runtimes NOTIFY changed)
public:
    explicit PcRuntime(QObject* parent=nullptr);
    PcRuntime(const PcRuntimePlatform&,QObject* parent=nullptr);
    int capabilityVersion() const {return 1;}
    QVariantList runtimes() const {return m_runtimes;}
    Q_INVOKABLE void refresh();
    Q_INVOKABLE QVariantMap openGame(const QString& editionId,const QString& runtimeId,const QString& expectedVersion);
    static int steamId(const QString& editionId);
signals:
    void changed();
private:
    PcRuntimePlatform m_platform;
    QVariantList m_runtimes;
};
}
