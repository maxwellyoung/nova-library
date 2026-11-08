# Standalone controller diagnostic

A native Qt 5.15 model and fixture for N019. It observes supported QtGamepad events, exposes an inspectable snapshot, and exports only a reviewed snapshot into a new private file. It does not remap input, alter an emulator, request permissions, upload data or mark physical acceptance.

## Actual Pegasus input boundary

The pinned Pegasus base is `5d58223e58f84afb31d5d14a67438841b981a6fa`. Its `src/backend/model/internal/Gamepad.h` exposes 17 boolean buttons (including Select) and four double axes (`axisLeftX`, `axisLeftY`, `axisRightX`, `axisRightY`). `GamepadManagerQt.cpp` receives QtGamepad events and converts trigger presses to booleans; its forwarded gamepad model does not retain trigger pressure. Android in the inspected paired build selects this QtGamepad backend. SDL input is a separate desktop backend and is not implemented by this adapter.

`QtGamepadObserver` uses the same actual `QGamepadManager` signals directly:

- `gamepadConnected(int)`, `gamepadDisconnected(int)`
- `gamepadButtonPressEvent(int, GamepadButton, double)` and `gamepadButtonReleaseEvent(int, GamepadButton)`
- `gamepadAxisEvent(int, GamepadAxis, double)`

This preserves the four stick axes and L2/R2 Qt pressure values before Pegasus reduces them to boolean presses. It does **not** establish that a particular Android driver/controller provides analogue trigger resolution. If that backend only reports 0/1, the diagnostic keeps those values without inventing intermediate travel. All channels start explicitly unseen.

Select uses `QGamepadManager::ButtonSelect`. System Back uses a separate `Qt::Key_Back` event filter. Qt 5's `QKeyEvent` supplies no controller device identity, so Back remains unattributed and is never relabelled Select. The observer returns false from the event filter; the host diagnostic must handle its own Back/cancel action. The fixture accepts Back to keep its window open. No key is globally consumed or remapped.

No upstream input patch is required to receive these existing QtGamepad signals. A **host integration** is still required to compile the new module, expose its context object and open the diagnostic surface. Nothing in this directory is included in the current paired APK or theme merely because these files exist.

## Model and lifecycle

`ControllerCheck(bool injected)` fixes the capture method for its lifetime: `injected` for tests or `observed` for native events. Both export `physicalAccepted: false`. This is declared provenance, not authenticated telemetry; code calling the model must honor its capture mode. Synthetic tests never construct/attach the native gamepad singleton.

`connectDevice`, `disconnectDevice`, `button`, `axis`, `trigger`, and `systemBack` accept events. `state` contains:

- Separate device IDs, connection states, 17 button observations, four raw/filtered stick values and two raw trigger-pressure channels.
- Seen/not-seen and live-value-observed flags, actual sampled min/max, press/release observations and accepted value-change counts.
- Explicit system Back with unavailable device identity, duplicate/rejected event totals, fixed method, UTC session/event dates, actual Qt version, and unknown host build identity.
- Display-only axial deadzone and trigger threshold, with their current values. These never change emulator or OS settings.

Stick inputs must be finite and within −1…1. Trigger inputs must be finite and within 0…1. Unknown controls/devices, detached devices, inactive captures and invalid ranges are rejected without changing the last valid sample. Rejected counts identify invalid observations; unseen channels are **not** automatically declared failed hardware. Actual hardware failures still require a real operator check.

Repeated identical notifications do not inflate value-change counts or establish extra presses/releases. A disconnect or focus loss clears live values, while retaining the previously observed range and press/release evidence. Such resets set `liveValueObserved: false`; they do not fabricate a hardware release, center sample or transition. Because Back is unattributed, any device detach also clears its live state conservatively.

The host controls whether the diagnostic is open with `setActive(bool)`. The native observer separately tracks application focus using `setFocused(bool)`. Returning app focus cannot reopen a diagnostic that the host closed. Integrate it only inside the scoped diagnostic lifecycle, not as a background controller monitor.

At most eight device records are retained in one model. Reconnecting a known ID preserves its session observations; Qt IDs are volatile and are not a hardware serial or cross-reboot identity. Construct a fresh model for a new check/session. Session metadata explicitly says the host application's build identity is not established; a future integration should bind the exported record to its separately verified build receipt rather than inventing a version.

## Preview and export

`preview()` returns `{json, bytes, sha256, sent: false}` without writing. Inspect the full JSON. Cancel by doing nothing.

`exportReport(absoluteCanonicalPath, approvedSha256)` writes only if the digest still matches the current snapshot and the report is at most 64 KiB. Any changed event, setting or lifecycle state invalidates a previous approval. The destination must be new, with an existing canonical parent; existing files/symlinks and linked/missing parents are refused. On supported Unix hosts (including Android), exclusive creation uses mode `0600`, flushes the output and never replaces existing data. A failed write removes only its own newly created file. Other platforms refuse export until a safe equivalent is implemented. Errors contain fixed text without caller paths.

This is a private local diagnostic. Qt IDs, dates and observed input can still be private. No device name, hardware serial, account, ROM, save, arbitrary text or raw log is included. No send mode exists. Creating a report does not authorize sharing it.

## Integration API

```cpp
// The host owns this lifetime while its diagnostic surface is open.
auto* check = new ControllerCheck(false, diagnosticOwner);
auto* observer = new QtGamepadObserver(check);
engine.rootContext()->setContextProperty("controllerCheck", check);
// On leaving the diagnostic:
check->setActive(false);
```

Include `controllercheck.pri` from the host's qmake project. The inspected Android build already links QtGamepad. A host using SDL must supply a reviewed equivalent adapter or explicitly mark native capture unsupported; this implementation does not infer it from keyboard/QML events. The QML fixture does not synthesize axes from keyboard presses.

Keep one native integration owner responsible for build lists, object lifetime, context property and host-version binding. No `MainActivity`, native patch, theme or live input settings were edited by this standalone slice.

## Build and verify

Use a provisioned Qt 5.15 toolchain with QtGamepad, QtTest, QtQml and QtQuick. Build into separate private directories:

```sh
mkdir controller-check-tests
cd controller-check-tests
/path/to/qmake /path/to/nova-frontend/native/controllercheck/tests.pro
make
./controller-check-tests
```

For the standalone fixture, use `fixture.pro`. `--fixture` injects labelled values and never attaches the native backend. `--smoke` checks QML warnings, the expected rendered device delegate and a real rendered frame, then exits. `--image new-file.png` optionally retains the synthetic frame and refuses an existing image. Running without `--fixture` attaches the host's native QtGamepad stream and requires a separate deliberate runtime check; it was not used for the synthetic verification.

The isolated macOS Qt 5.15.10 build passed 12 functional tests plus Qt init/cleanup (14 passes total). The actual QML fixture rendered at 1280×960 with software rendering and explicit injected labels. The test toolchain's old static Qt GUI dependency requested the removed AGL framework under Xcode 26.2; only the generated test/fixture Makefiles had `-framework AGL` removed. No toolchain, SDK or repository build recipe was rewritten. A fresh generated Makefile on that same provisioned toolchain needs the same scoped adjustment.

## Remaining gate

Integrate into the intended recorder-preserving native build and diagnostic surface, verify build/source inclusion, then have Maxwell operate the physical Nova once: every button, Select versus Back, full stick ranges, trigger travel, release, focus loss and disconnect/reconnect. Record actual host/runtime/device/date and any failed inputs with the build receipt. Test both cancel and explicit private export. Physical comfort, native axis availability and trigger resolution are open until that check; desktop injected tests and this screenshot do not close N019.

## Optional native source inclusion

`tools/apply_controller_check.py` now stages this module into a **separate patched Pegasus source copy** and exposes a `controllerCheck` QML context. It does not edit or package the theme, prepare/build a release, install anything or change Android permissions:

```sh
python3 tools/apply_controller_check.py /canonical/private/native-copy \
  --backup /canonical/private/new-controller-source-backup
```

The tool backs up the exact three integration files before changing them: `FrontendLayer.cpp`, `backend.pro` and `CMakeLists.txt`. It stages the seven owned module files, checks unique DeviceLibrary/engine-lifecycle anchors, and uses distinct marked blocks. Shared native source is rechecked before publication, source-file modes are retained, and failed application recovers its own writes without overwriting newer foreign edits. A failed receipt remains `incomplete`; inspect it and its original files before proceeding. Serialise appliers against a single source copy.

Fresh and scoped idempotent application compose with `apply_stopping_notes.py` in either order. Reapplication checks this module's exact blocks and staged bytes, permitting the other module's independent changes. Full integration-file hashes in the retained receipt describe the application time; they do not certify later foreign changes. Changed owned blocks/payloads, partial integration, linked paths and existing module/backup collisions fail closed. Automatic module upgrades are refused.

The new `ControllerCheckHost` factory creates one object per QML engine, parents its observer to the model and starts capture **disabled**. The theme must explicitly call `setActive(true)` when the diagnostic is opened and `setActive(false)` on exit; app focus alone cannot enable it. Engine teardown destroys the model/observer. No background input capture or permission is added.

Runtime metadata comes from the running application and Qt: application name/version, platform/version and Qt version. On Android, the factory reads the current activity package, public Build.MODEL and API level using the existing QtAndroidExtras/JNI APIs. These are runtime observations, not physical-controller acceptance or a source/APK signature. Source/build matching still requires the separate build receipt. Missing/invalid metadata remains unknown. No Android serial, user account or new permission is read.

Native-host exports are confined to the existing canonical `QStandardPaths::AppLocalDataLocation` parent. `exportPrivateReport("new-name.json", reviewedDigest)` creates only its `controller-checks` child (`0700`) after valid explicit approval, then a new report (`0600`). Blank/unavailable app storage fails closed. Linked/nonprivate child directories and path-escaping names are refused. The older absolute-path `exportReport` API is also confined once the host factory configures it; QML cannot unset this C++ confinement. No path is included in the exported metadata and no send operation exists.

The optional adapter requires the current QtGamepad backend. Its build blocks explicitly reject an SDL-gamepad configuration instead of silently using a second unrelated input backend. Both qmake and CMake include the owned source/header files; existing Qt/AndroidExtras dependencies remain in use. The code uses the host's C++11 level.

Updated native-inclusion verification: 15 functional Qt cases plus init/cleanup (17 passes), including factory ownership/default-disabled state, real runtime metadata fields, private-only export and empty/link/nonprivate storage refusal. Ten focused Python applier tests cover backup/refusal/recovery/foreign edits and both-order composition. Actual retained native source copies were integrated in both orders; their repeated applications were unchanged. The composed actual `FrontendLayer.cpp` and both staged modules compiled as an isolated desktop Qt static library. This verifies source inclusion/type/build-list compatibility at that layer; it is not a linked Android application, native runtime check, theme entry point or physical-device acceptance.
