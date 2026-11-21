QT += core gui qml quick testlib
CONFIG += console c++17
CONFIG -= app_bundle
TARGET = save-copies-theme-host
include(../../native/savecopies/savecopies.pri)
INCLUDEPATH += ../../native/savecopies
SOURCES += main.cpp
