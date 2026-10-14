# Validation boundaries

The release is source-only. The final recent-first Home and console browsing source passed the checks below on 2026-10-15.

- Python tests exercise deterministic demo generation, refusal to overwrite output, fictional/non-launchable catalogue entries, and privacy-scan rejection fixtures.
- Node tests load the actual QML JavaScript helper file and exercise identity, missing-file launch gating, unknown-vs-zero time, explicit personal progress overrides, filtering and sorting.
- The native patch was applied to a pristine archive of the pinned Pegasus commit in private scratch. Every resulting modified/new file matched the complete captured native source, with the documented bridge README rewrite.
- `tools/check_native_patch.py` checks the exact Git base, clean state, and patch application without mutating a provided checkout.
- The actual-theme synthetic QML wrapper passed an offscreen Qt 6.11.1 runtime smoke on macOS. Enter, X, Y, arrows, Escape, Page Up/Page Down, Home/End exercised the theme key handler; kept toggles, details, unavailable-route explanation, console filtering and return were checked. This used a mock Pegasus API and an isolated temporary copy. It is not physical keyboard/controller input, real engine discovery, game-launch, private bridge or screenshot proof.
- `python3 tools/smoke_demo.py` reproduces the offscreen smoke with a compatible QML runner. Explicit `--qml` and `--import-path` arguments accommodate installations whose runner and modules are outside their default search paths. Generic interactive Qt/Pegasus setup remains installation-dependent.
- A full portable native build, native fixture tests from this exact patch, service synchronization, physical controller/game launching and Android installation are separate verification gates.

No binaries or private QA artifacts are supplied. Do not turn the successful patch check into an APK/source identity claim.
