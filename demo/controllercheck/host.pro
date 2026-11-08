# Isolated desktop host for theme/ControllerCheck.qml: real native module, labelled injected
# data, real QKeyEvents. Not part of any Android or release build.
QT += qml quick testlib
CONFIG += console c++11
CONFIG -= app_bundle
TARGET = controller-check-theme-host
include(../../native/controllercheck/controllercheck.pri)
INCLUDEPATH += ../../native/controllercheck
SOURCES += main.cpp
# qmlimportscanner reads this for the static Qt build's plugins. Deliberately not in a qrc.
OTHER_FILES += imports.qml
