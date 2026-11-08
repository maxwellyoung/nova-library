#pragma once
#include "ControllerCheck.h"
#include <QGamepadManager>

// Observes Qt's existing gamepad stream without consuming or remapping events.
class QtGamepadObserver : public QObject {
    Q_OBJECT
public:
    explicit QtGamepadObserver(ControllerCheck* model, bool attachNative = true);
    bool eventFilter(QObject*, QEvent*) override;
public slots:
    void pressed(int id, QGamepadManager::GamepadButton button, double value);
    void released(int id, QGamepadManager::GamepadButton button);
    void moved(int id, QGamepadManager::GamepadAxis axis, double value);
private:
    static QString buttonName(QGamepadManager::GamepadButton);
    ControllerCheck* const m_model;
};
