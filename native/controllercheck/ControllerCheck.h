#pragma once
#include <QObject>
#include <QMap>
#include <QSet>
#include <QVariantMap>

// A diagnostic observation model, not a controller remapper or physical approval.
class ControllerCheck : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap state READ state NOTIFY changed)
public:
    explicit ControllerCheck(bool injected, QObject* parent = nullptr);
    bool connectDevice(int id);
    bool disconnectDevice(int id);
    bool button(int id, const QString& control, bool down);
    bool axis(int id, const QString& control, double value);
    bool trigger(int id, const QString& control, double value);
    bool systemBack(bool down, bool autoRepeat = false);
    Q_INVOKABLE void setActive(bool active);
    void setFocused(bool focused);
    bool setDeadzone(double value);
    bool setTriggerThreshold(double value);
    QVariantMap state() const;
    Q_INVOKABLE QVariantMap preview() const;
    Q_INVOKABLE QVariantMap exportReport(const QString& path, const QString& approvedSha256) const;
    Q_INVOKABLE QVariantMap exportPrivateReport(const QString& fileName, const QString& approvedSha256) const;
    void configureApplication(const QVariantMap& metadata, const QString& privateParent);
    bool isInjected() const { return m_injected; }
    static QStringList buttons();
    static QStringList axes();
signals:
    void changed();
private:
    struct Sample {
        bool seen = false, liveObserved = false, downSeen = false, upSeen = false;
        double raw = 0, minimum = 0, maximum = 0;
        int changes = 0;
    };
    struct Device {
        bool connected = true;
        QMap<QString, Sample> buttons, axes, triggers;
    };
    bool observe(int id, const QString& control, double value, int kind);
    bool reject();
    void resetLive(const QString& reason);
    static void neutral(Device& device);
    QVariantMap sampleState(const Sample& sample, int kind) const;
    QByteArray bytes() const;
    const bool m_injected;
    const QString m_startedAt;
    QString m_lastEventAt, m_resetReason, m_privateParent;
    QVariantMap m_runtimeMetadata;
    bool m_confinedExports = false;
    QMap<int, Device> m_devices;
    Sample m_back;
    bool m_active = true, m_enabled = true, m_focused = true;
    double m_deadzone = 0.15, m_threshold = 0.5;
    int m_duplicates = 0, m_rejected = 0;
};
