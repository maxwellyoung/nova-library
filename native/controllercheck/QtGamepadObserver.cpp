#include "QtGamepadObserver.h"
#include <QCoreApplication>
#include <QGuiApplication>
#include <QKeyEvent>
#include <cmath>

QtGamepadObserver::QtGamepadObserver(ControllerCheck* model, bool attachNative)
    : QObject(model), m_model(model) {
    // Test calls never connect to a native backend; an injected session cannot
    // accidentally capture and export host input as the synthetic fixture.
    if (!attachNative || model->isInjected()) return;
    auto* source=QGamepadManager::instance();
    connect(source,&QGamepadManager::gamepadConnected,model,&ControllerCheck::connectDevice);
    connect(source,&QGamepadManager::gamepadDisconnected,model,&ControllerCheck::disconnectDevice);
    connect(source,&QGamepadManager::gamepadButtonPressEvent,this,&QtGamepadObserver::pressed);
    connect(source,&QGamepadManager::gamepadButtonReleaseEvent,this,&QtGamepadObserver::released);
    connect(source,&QGamepadManager::gamepadAxisEvent,this,&QtGamepadObserver::moved);
    for (int id : source->connectedGamepads()) model->connectDevice(id);
    QCoreApplication::instance()->installEventFilter(this);
    if (auto* app=qobject_cast<QGuiApplication*>(QCoreApplication::instance())) {
        model->setFocused(app->applicationState()==Qt::ApplicationActive);
        connect(app,&QGuiApplication::applicationStateChanged,model,[model](Qt::ApplicationState state) {
            model->setFocused(state==Qt::ApplicationActive);
        });
    }
}
QString QtGamepadObserver::buttonName(QGamepadManager::GamepadButton button) {
    switch (button) {
    case QGamepadManager::ButtonUp:return "up"; case QGamepadManager::ButtonDown:return "down";
    case QGamepadManager::ButtonLeft:return "left"; case QGamepadManager::ButtonRight:return "right";
    case QGamepadManager::ButtonA:return "south"; case QGamepadManager::ButtonB:return "east";
    case QGamepadManager::ButtonX:return "west"; case QGamepadManager::ButtonY:return "north";
    case QGamepadManager::ButtonL1:return "l1"; case QGamepadManager::ButtonL2:return "l2";
    case QGamepadManager::ButtonL3:return "l3"; case QGamepadManager::ButtonR1:return "r1";
    case QGamepadManager::ButtonR2:return "r2"; case QGamepadManager::ButtonR3:return "r3";
    case QGamepadManager::ButtonSelect:return "select"; case QGamepadManager::ButtonStart:return "start";
    case QGamepadManager::ButtonGuide:return "guide"; default:return {};
    }
}
void QtGamepadObserver::pressed(int id,QGamepadManager::GamepadButton button,double value) {
    const auto name=buttonName(button);
    if (!std::isfinite(value) || value < 0 || value > 1) { m_model->trigger(id,name,value); return; }
    if (button==QGamepadManager::ButtonL2 || button==QGamepadManager::ButtonR2) m_model->trigger(id,name,value);
    // Pegasus itself treats any Qt press event as a digital press. Preserve
    // that observation independently from the raw trigger-pressure channel.
    m_model->button(id,name,true);
}
void QtGamepadObserver::released(int id,QGamepadManager::GamepadButton button) {
    const auto name=buttonName(button);
    if (button==QGamepadManager::ButtonL2 || button==QGamepadManager::ButtonR2) m_model->trigger(id,name,0);
    m_model->button(id,name,false);
}
void QtGamepadObserver::moved(int id,QGamepadManager::GamepadAxis axis,double value) {
    QString name;
    switch (axis) {
    case QGamepadManager::AxisLeftX:name="left-x";break;
    case QGamepadManager::AxisLeftY:name="left-y";break;
    case QGamepadManager::AxisRightX:name="right-x";break;
    case QGamepadManager::AxisRightY:name="right-y";break;
    default:break;
    }
    m_model->axis(id,name,value);
}
bool QtGamepadObserver::eventFilter(QObject*,QEvent* event) {
    if (event->type()==QEvent::KeyPress || event->type()==QEvent::KeyRelease) {
        auto* key=static_cast<QKeyEvent*>(event);
        if (key->key()==Qt::Key_Back) m_model->systemBack(event->type()==QEvent::KeyPress,key->isAutoRepeat());
    }
    return false;
}
