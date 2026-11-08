#pragma once
#include "ControllerCheck.h"
namespace controllercheck {
// New per-engine diagnostic, disabled until opened. No permission or file write.
ControllerCheck* createForApplication(QObject* owner, bool attachNative = true);
}
