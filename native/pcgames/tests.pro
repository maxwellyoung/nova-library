QT += core testlib
QT -= gui
CONFIG += testcase console c++17
CONFIG -= app_bundle
TARGET = pc-runtime-tests
SOURCES += PcRuntime.cpp tst_PcRuntime.cpp
HEADERS += PcRuntime.h
