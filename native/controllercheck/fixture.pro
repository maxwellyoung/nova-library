QT += qml quick
CONFIG += console c++11
CONFIG -= app_bundle
TARGET = controller-check-fixture
include(controllercheck.pri)
SOURCES += fixture_main.cpp
RESOURCES += fixture.qrc
