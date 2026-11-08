QT += core gui qml quick testlib
CONFIG += console c++11
CONFIG -= app_bundle
TARGET = notebook-theme-host
include(../../native/stoppingnotes/stoppingnotes.pri)
INCLUDEPATH += ../../native/stoppingnotes
SOURCES += main.cpp
OTHER_FILES += imports.qml
