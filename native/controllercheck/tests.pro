QT += testlib
CONFIG += console testcase c++11
CONFIG -= app_bundle
TARGET = controller-check-tests
include(controllercheck.pri)
SOURCES += tst_ControllerCheck.cpp
