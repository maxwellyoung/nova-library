// Drives the actual theme with the actual ControllerCheck model and QtGamepadObserver.
// Data is injected and labelled as such (method: "injected"); the native backend is never
// attached, so nothing here can be mistaken for a physical controller result.
#include "ControllerCheck.h"
#include "ControllerCheckHost.h"
#include "QtGamepadObserver.h"
#include <QCommandLineParser>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QKeyEvent>
#include <QFocusEvent>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTemporaryDir>
#include <QTest>
#include <sys/stat.h>

namespace {
// Same values as Pegasus src/backend/types/GamepadKeyId.h.
enum : int { A = 0x100000, B, X, Y, L1, L2, L3, R1, R2, R3, SELECT, START, GUIDE };
struct Mapping { QGamepadManager::GamepadButton button; int key; };
const QHash<QString, Mapping>& mappings() {
    static const QHash<QString, Mapping> table{
        {"up",{QGamepadManager::ButtonUp,Qt::Key_Up}},{"down",{QGamepadManager::ButtonDown,Qt::Key_Down}},
        {"left",{QGamepadManager::ButtonLeft,Qt::Key_Left}},{"right",{QGamepadManager::ButtonRight,Qt::Key_Right}},
        {"south",{QGamepadManager::ButtonA,A}},{"east",{QGamepadManager::ButtonB,B}},
        {"west",{QGamepadManager::ButtonX,X}},{"north",{QGamepadManager::ButtonY,Y}},
        {"l1",{QGamepadManager::ButtonL1,L1}},{"l2",{QGamepadManager::ButtonL2,L2}},{"l3",{QGamepadManager::ButtonL3,L3}},
        {"r1",{QGamepadManager::ButtonR1,R1}},{"r2",{QGamepadManager::ButtonR2,R2}},{"r3",{QGamepadManager::ButtonR3,R3}},
        {"select",{QGamepadManager::ButtonSelect,SELECT}},{"start",{QGamepadManager::ButtonStart,START}},
        {"guide",{QGamepadManager::ButtonGuide,GUIDE}}};
    return table;
}
}

class FixtureDriver : public QObject {
    Q_OBJECT
public:
    FixtureDriver(ControllerCheck* model, QtGamepadObserver* observer, QString privateParent, QString output, QObject* parent)
        : QObject(parent), m_model(model), m_observer(observer), m_private(std::move(privateParent)), m_output(std::move(output)) {}
    void setWindow(QQuickWindow* window) { m_window = window; }
    Q_INVOKABLE void focusWindow() { QFocusEvent in(QEvent::FocusIn, Qt::ActiveWindowFocusReason); QCoreApplication::sendEvent(m_window, &in); }
    // QGuiApplication::sendEvent to the window is exactly how Pegasus GamepadButtonNavigation delivers keys.
    Q_INVOKABLE bool key(int code, bool press, bool repeat = false) {
        QKeyEvent event(press ? QEvent::KeyPress : QEvent::KeyRelease, code, Qt::NoModifier, QString(), repeat);
        QGuiApplication::sendEvent(m_window, &event);
        return event.isAccepted();
    }
    // keyFirst follows Pegasus's earlier connection to QGamepadManager; the other order is also legal in Qt.
    Q_INVOKABLE bool pad(const QString& control, bool down, int device = 7, bool keyFirst = true, double value = 1.0) {
        const auto map = mappings().value(control);
        const auto observe = [&] {
            if (down) m_observer->pressed(device, map.button, value);
            else m_observer->released(device, map.button);
        };
        if (!keyFirst) observe();
        const bool accepted = key(map.key, down);
        if (keyFirst) observe();
        return accepted;
    }
    // Pegasus's repeat timer: a repeated release then a repeated press, with no new gamepad signal.
    Q_INVOKABLE bool padRepeat(const QString& control) {
        const int code = mappings().value(control).key;
        const bool released = key(code, false, true), pressed = key(code, true, true);
        return released && pressed;
    }
    Q_INVOKABLE void stick(const QString& axis, double value, int device = 7) {
        const QHash<QString, QGamepadManager::GamepadAxis> axes{{"left-x",QGamepadManager::AxisLeftX},{"left-y",QGamepadManager::AxisLeftY},{"right-x",QGamepadManager::AxisRightX},{"right-y",QGamepadManager::AxisRightY}};
        m_observer->moved(device, axes.value(axis), value);
    }
    Q_INVOKABLE bool connectPad(int device = 7) { return m_model->connectDevice(device); }
    Q_INVOKABLE bool disconnectPad(int device = 7) { return m_model->disconnectDevice(device); }
    Q_INVOKABLE void appFocus(bool focused) { m_model->setFocused(focused); }
    Q_INVOKABLE void touch(QObject* object) {
        auto* item = qobject_cast<QQuickItem*>(object);
        const QPoint at = item->mapToScene(QPointF(item->width() / 2, item->height() / 2)).toPoint();
        QTest::mouseClick(m_window, Qt::LeftButton, Qt::NoModifier, at);
    }
    Q_INVOKABLE bool grab(const QString& name) {
        const auto path = m_output + QLatin1Char('/') + name + QStringLiteral(".png");
        if (m_output.isEmpty()) return true;
        if (QFile::exists(path)) return false;
        return m_window->grabWindow().save(path);
    }
    Q_INVOKABLE QStringList reports() const {
        return QDir(m_private + QStringLiteral("/controller-checks")).entryList(QDir::Files | QDir::Hidden);
    }
    Q_INVOKABLE QString readReport(const QString& name) const {
        QFile file(m_private + QStringLiteral("/controller-checks/") + name);
        return file.open(QIODevice::ReadOnly) ? QString::fromUtf8(file.readAll()) : QString();
    }
    Q_INVOKABLE int reportMode(const QString& name) const {
        struct stat info{};
        return ::stat(QFile::encodeName(m_private + QStringLiteral("/controller-checks/") + name).constData(), &info) == 0 ? int(info.st_mode & 0777) : -1;
    }
    // A world-readable child directory is the real refusal the native export must keep.
    Q_INVOKABLE bool blockExports(bool blocked) {
        const auto dir = QFile::encodeName(m_private + QStringLiteral("/controller-checks"));
        ::mkdir(dir.constData(), 0700);
        return ::chmod(dir.constData(), blocked ? 0755 : 0700) == 0;
    }
private:
    ControllerCheck* const m_model;
    QtGamepadObserver* const m_observer;
    const QString m_private, m_output;
    QQuickWindow* m_window = nullptr;
};

int main(int argc, char** argv) {
    QGuiApplication app(argc, argv);
    app.setApplicationName("Nova controller theme fixture");
    QCommandLineParser parser;
    parser.addOptions({{"qml", "Harness QML file", "file"}, {"output", "New image folder", "dir"}, {"scenario", "Scripted scenario", "name"},
                       {"width", "Window width", "px"}, {"height", "Window height", "px"}, {"light", "Light surface"}, {"large", "Larger text"},
                       {"font", "Review font file", "file"}, {"bridge", "model | absent | partial | unconfigured", "kind"}, {"keyboard-labels", "Keys with no gamepad names"}});
    parser.process(app);
    const QString bridge = parser.value("bridge").isEmpty() ? QStringLiteral("model") : parser.value("bridge");
    QTemporaryDir privateRoot;
    const QString privateParent = QDir(privateRoot.path()).canonicalPath();

    // Disabled by default, as ControllerCheckHost creates it; the injected method stays visible in the report.
    ControllerCheck model(true);
    model.setActive(false);
    if (bridge == QLatin1String("model"))
        model.configureApplication({{"applicationId","fixture.injected"},{"applicationName","Nova fixture"},{"platform","desktop-fixture"},{"inputBackend","QtGamepad"}}, privateParent);
    QtGamepadObserver observer(&model, false);
    // Same application-wide filter native attachment installs, so Back ordering is the real order.
    app.installEventFilter(&observer);
    FixtureDriver driver(&model, &observer, privateParent, parser.value("output"), &app);
    QObject partial;

    QQmlApplicationEngine engine;
    auto* context = engine.rootContext();
    context->setContextProperty("driver", &driver);
    context->setContextProperty("scenario", parser.value("scenario"));
    context->setContextProperty("fixtureWidth", parser.value("width").toInt());
    context->setContextProperty("fixtureHeight", parser.value("height").toInt());
    context->setContextProperty("fixtureLight", parser.isSet("light"));
    context->setContextProperty("fixtureLarge", parser.isSet("large"));
    context->setContextProperty("fixtureFont", parser.isSet("font") ? QUrl::fromLocalFile(parser.value("font")) : QUrl());
    context->setContextProperty("fixtureKeyboardLabels", parser.isSet("keyboard-labels"));
    context->setContextProperty("fixtureBridge", bridge);
    if (bridge == QLatin1String("model") || bridge == QLatin1String("unconfigured")) context->setContextProperty("controllerCheck", &model);
    else if (bridge == QLatin1String("partial")) context->setContextProperty("controllerCheck", &partial);
    QObject::connect(&engine, &QQmlApplicationEngine::warnings, &app, [](const QList<QQmlError>& errors) {
        for (const auto& error : errors) fprintf(stderr, "QML_WARNING %s\n", qPrintable(error.toString()));
    });
    engine.load(QUrl::fromLocalFile(parser.value("qml")));
    if (engine.rootObjects().isEmpty()) return 3;
    auto* window = qobject_cast<QQuickWindow*>(engine.rootObjects().first());
    driver.setWindow(window);
    driver.focusWindow();
    return app.exec();
}
#include "main.moc"
