QT = core qml testlib
CONFIG += console testcase c++14
CONFIG -= app_bundle
TEMPLATE = app
TARGET = checked-memory-tests
INCLUDEPATH += $$PWD/testsupport
SOURCES += $$PWD/Memory.cpp $$PWD/tst_Memory.cpp
HEADERS += $$PWD/Memory.h
