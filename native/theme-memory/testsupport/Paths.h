#pragma once
#include <QString>
// The isolated test supplies a default directory; production uses Pegasus Paths.h.
namespace paths { QString writableConfigDir(); }
