QT += core gui qml quick testlib
QTPLUGIN += qoffscreen
CONFIG += console c++17
CONFIG -= app_bundle
TARGET = input-profiles-theme-host
QMAKE_APPLE_DEVICE_ARCHS = x86_64
include(../../native/savecopies/savecopies.pri)
INCLUDEPATH += ../../native/savecopies ../../native/theme-memory ../../native/theme-memory/testsupport
SOURCES += main.cpp ../../native/theme-memory/Memory.cpp
HEADERS += ../../native/theme-memory/Memory.h
