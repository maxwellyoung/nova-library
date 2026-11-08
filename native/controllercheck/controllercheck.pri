QT += core gui gamepad
CONFIG += c++11
HEADERS += $$PWD/ControllerCheck.h $$PWD/QtGamepadObserver.h
SOURCES += $$PWD/ControllerCheck.cpp $$PWD/QtGamepadObserver.cpp
HEADERS += $$PWD/ControllerCheckHost.h
SOURCES += $$PWD/ControllerCheckHost.cpp
android: QT += androidextras
