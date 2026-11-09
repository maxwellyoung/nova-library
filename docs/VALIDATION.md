# Validation boundaries

The release is source-only. The recent-first Home, console browsing, Settings, Apps and explicit disc-picker source passed the checks below on 2026-10-15.

- Python tests exercise deterministic demo generation, refusal to overwrite output, fictional/non-launchable catalogue entries, and privacy-scan rejection fixtures.
- Node tests load the actual QML JavaScript helper file and exercise identity, missing-file launch gating, unknown-vs-zero time, explicit personal progress overrides, filtering and sorting, observed storage, explicit disc grouping and app identity. Gameplay date evidence preserves its source and precision; catalogue markers do not establish game-file presence.
- The native patch was applied to a pristine archive of the pinned Pegasus commit in private scratch. Every resulting modified/new file matched the complete captured native source, with the documented bridge README rewrite.
- `tools/check_native_patch.py` checks the exact Git base, clean state, and patch application without mutating a provided checkout.
- The actual-theme synthetic QML wrapper passed an offscreen Qt 6.11.1 runtime smoke on macOS. Enter, X, Y, arrows, Escape, Page Up/Page Down, Home/End exercised the theme key handler; kept toggles, details, unavailable-route explanation, console filtering and return were checked. This used a mock Pegasus API and an isolated temporary copy. It is not physical keyboard/controller input, real engine discovery, game-launch, private bridge or screenshot proof.
- `python3 tools/smoke_demo.py` reproduces the offscreen smoke with a compatible QML runner. Explicit `--qml` and `--import-path` arguments accommodate installations whose runner and modules are outside their default search paths. Generic interactive Qt/Pegasus setup remains installation-dependent.
- A full portable native build, native fixture tests from this exact patch, service synchronization, physical controller/game launching and Android installation are separate verification gates.

No binaries or private QA artifacts are supplied. Do not turn the successful patch check into an APK/source identity claim.

The private integration harness additionally exercised Settings/storage reverse paths, raw-file totals, explicit disc grouping, picker defaults/cancel/dispatch, app-only lists, unavailable Steam app actions, missing app routes and malformed evidence. Hardware checks distinguish injected input from physical controls; desktop fixtures are not an Android performance claim.

On Android, an unhandled Back key can close a Qt window. Preserve existing cancel bindings and add `Back` through Pegasus controls/settings. For an untouched default map the resulting setting is `keys.cancel: Esc,Backspace,GamepadB,Back`. Do not overwrite a customized map with those defaults. This is a host configuration step, not a native binary shipped by this source repository.

Installation and capacity additions passed 21 Node / 7 Python checks, a Qt6 synthetic smoke including Info return and Storage, and private Qt5 integration scenarios with 236 bare / 139 bridge assertions. The integration tested missing capacity, measured bars and progressive disclosure. On Android the capacity view, compact device badges and full Info rendered; management actions opened Files and DroidDeck and returned to Home without starting a game. Maxwell also confirmed physical X/Details/Info/B and Settings/Storage/D-pad paths. Captures remain snapshots, and a launch route is not a gameplay/performance guarantee.

## Recent history, display evidence and artwork

Home's helper tests separate local launch history, handpicked shelves, imported activity and fallback picks. The QML harness emits Pegasus launch/finish signals and changes the fixture statistics after emission, checking that the queued refresh reads the updated values. These are API-event fixtures, not real emulator launch/return or timing measurements.

Aspect tests cover source requirements, edition/recipe mismatches, changed/conflicting settings, failed/future checks, independent filter intersections and mixed-disc sets. The actual QML path exercises directional changes, empty results, explicit/shortcut Clear, Back, Info and saved-filter reconstruction in a new theme instance. In-process mock memory demonstrates the theme's save/read path; persistence to a physical device's disk remains separate.

Artwork has a regression fixture for a pending loopback image request: the title fallback stays visible while the image loads. No HTTP server is started. Generated PNG covers have checked dimensions, chunk CRCs and decompressed data size, and the QML capture waits for image decoding and verifies their natural ratio. PNG output avoids requiring an SVG image plugin for this demo. The artwork and game identities are synthetic.

Use `tools/smoke_demo.py --surface aspect` or `--surface home` with a compatible QML runner; `--appearance light --text-size large` exercises the alternate layout. Screenshot mode checks selected-row visibility and explanation/footer separation. Existing cloud, controls and Checks scenarios remain in the same harness. No device installation, rendering-setting change, gameplay, native 4:3 hardware proof or publication follows from these checks.

## Session windows

See [SESSION-WINDOWS.md](SESSION-WINDOWS.md). The real theme smoke covers label editing, filtering, clear, malformed-version refusal and theme recreation, with all Details actions and chooser/filter rows checked for focus containment. Desktop fixture storage is in memory; Android disk persistence and physical input remain separate gates.

## Integrated local notebook

`tools/smoke_notebook.py` drives the full theme with `demo/notebook/host.pro`, the actual native store and synthetic catalogue/input. Separate GUI processes reopen the same real disk notebook. It covers edit, screenshot selection, controller image marking, Home/Details return, dirty Back/History, conflict branches, clear/restore, legacy provenance, write refusal/retry, missing originals and corrupt metadata. Screenshots and action/footer containment are checked across dark/light, large text, wide and bottom-clearance profiles. `--absent` checks the optional context boundary. This is desktop Qt evidence; Android storage permissions, keyboard, physical touch/buttons and installed-app persistence remain separate gates.


## Persistent Downloads — 8 November 2026

The native Cloud suite passes 65 cases on each of Qt 5.15.10 and Qt 6.11.1 using
synthetic payloads and loopback HTTP. New cases exercise FIFO batches, foreground
loss with explicit resume, network interruption/recreation/Range, persisted and
private queue records, stale writers, malformed/foreign/linked state, the 100-job
limit and content identity changes before and after fetching details. Unqueue
retains the partial payload and descriptor. Queue consent never survives restart.

Twelve desktop Qt runs exercise empty, paused, blocked and active Downloads at
1280×960 dark/standard, 960×720 light/large and 1600×900 dark/large. Each also runs
the common controller-key routing harness: enqueue/start, mapped next-page route,
pause, explicit retry, unqueue, empty Back and original Cloud selection. The older
queue-less bridge path remains exercised. These are injected keys and synthetic
records, not physical-controller or Android lifecycle evidence.

The wider source suite passes 85 Node cases and 161 Python cases. The private
combined Android candidate compiles, links and packages with the original signer;
its binary manifest and five DEX files match the prior recovery build. Its external
theme is paired separately. Build inclusion is not device installation, approval,
background execution, safe cloud-save restoration or full dreamlist acceptance.


## Optional PC runtime requests — 9 November 2026

The native PC adapter passes 23 cases on each of Qt 5.15.10 and Qt 6.11.1. Injected
platform tests exercise exact Steam IDs, permitted backend selection, malformed
observations, foreground/version changes, refused dispatch and result
minimisation without fallback. The actual Java target allowlist passes host-JDK
checks; the Android wrapper compiles in the private candidate against SDK 30.

The current source suite passes 94 Node cases and 168 Python cases, including
private/bounded per-edition choices, preference preservation, explicit preparation,
package queries, refusal/rollback and a fresh paired source. Public preparation
with Cloud, notebook, controller check and PC runtime together passes.

Desktop Qt exercises installed/missing/changed/refused/remembered states across
Nova 4:3, small light/large and wide dark/large profiles. The key harness covers
explicit selection, memory reload, direct remembered requests, changed/missing
adapter review, failed dispatch/preference/focus writes, corrupt preferences,
explicit legacy route/forget and original Library/Details Back. These are
synthetic states and injected keys, not Android app queries or physical buttons.

The private Android APK builds and its linked runtime sections match the linked
output. Signer and Android permissions match the previous queue candidate. The
existing recorder/foreground/verification/surface compiled classes are byte-equal
and present in DEX; four DEX files remain identical and the app DEX changes with
the new helpers. The final external theme is separately paired over the identical
native tree after UI text cleanup. No deployment, runtime upgrade, actual PC launch,
performance, save restoration or owner acceptance is established by this work.
