QT += core network testlib
QT -= gui
CONFIG += testcase console c++17
CONFIG -= app_bundle
TARGET = rom-cloud-tests
SOURCES += RomCloud.cpp tst_RomCloud.cpp
HEADERS += RomCloud.h
