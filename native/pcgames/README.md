# Optional PC runtime adapter

Nova can send an explicit Steam-game request to an allowlisted Android runtime.
This adds no emulator, game installer, compatibility engine, background service or
Steam credentials. The existing Pegasus file-launch path remains separate.

The source-reviewed protocols are:

| Runtime | Version | Exported entry | Action |
| --- | --- | --- | --- |
| DroidDeck | 0.7.0 | `com.droiddeck.launcher.FrontEndActivity` | `com.droiddeck.launcher.LAUNCH_GAME` |
| GameNative | 1.4.0 | `app.gamenative.MainActivity` | `app.gamenative.LAUNCH_GAME` |

Both receive only a positive signed 32-bit integer `app_id` and
`game_source=STEAM`. No executable, configuration JSON, command line, URI or
credentials can be supplied through this bridge. AgentStartActivity, DUMP,
debugging tools and private runtime files are not used.

Sources: [DroidDeck 0.7.0 manifest](https://github.com/Droid-Deck/DroidDeck/blob/0.7.0/app/src/main/AndroidManifest.xml),
[public request parser](https://github.com/Droid-Deck/DroidDeck/blob/0.7.0/app/src/main/java/com/droiddeck/launcher/frontend/GameLaunchIntent.kt),
[GameNative 1.4.0 manifest](https://github.com/utkarshdalal/GameNative/blob/v1.4.0/app/src/main/AndroidManifest.xml),
[request parser](https://github.com/utkarshdalal/GameNative/blob/v1.4.0/app/src/main/java/app/gamenative/utils/IntentLaunchManager.kt).
These are reviewed source interfaces; no third-party APK was downloaded or run
for this source implementation.

## Capability and UI

The optional `pcRuntime` context exposes `capabilityVersion:1`, `runtimes`,
`refresh()` and `openGame(editionId, runtimeId, expectedVersion)`. Android queries
exactly the two packages through explicit manifest visibility entries. No new
Android permission is requested. Package/version observations do not authenticate
the publisher or establish a particular APK hash, game installation or GPU support.

Details → PC runtime reuses the existing controller/touch list panel. Opening a
runtime remembers that explicit runtime and observed version for the exact Steam
edition only after Android accepts dispatch. A later A uses that choice. A
changed/missing/unsupported backend opens review instead of silently trying a
second app or the old shortcut. The existing shortcut is an explicit alternative;
Forget runtime choice changes preferences only. Back preserves Library/Details
and the originating edition. Older bridges keep their original route behaviour.

Choices live in bounded, versioned Pegasus theme memory. Invalid stored choices
are retained, never automatically replaced. Failed choice writes are visible and
leave the old preference intact. The adapter does not promote `x-launchable`, add
ROM observations, record play time or claim a game reached its menu. Actual PC
history capture remains a separate session-evidence contract.

Native code refreshes availability/version immediately before dispatch and checks
foreground status twice. Android's UI-thread wrapper checks the app version,
enabled/exported entry and window focus again. Backend refusals are reported
without fallback. Unsupported versions require an adapter review; the allowlist
is not a gameplay whitelist. This first version intentionally exposes no driver,
input-profile or aspect-setting overrides.

## Source preparation

```
python3 tools/prepare_native.py prepare /path/to/clean/pinned/pegasus \
  --output /path/to/new/pair --pc-runtime
python3 tools/prepare_native.py verify /path/to/new/pair
```

Combine with the other optional flags as needed. The lower-level
`tools/apply_pc_runtime.py` operates only on a separate already-patched source
copy and requires a new private backup directory. It refuses reapplication or a
partial existing integration rather than overwriting it. The context belongs to
the rebuilt QML engine; Android Java files and package visibility are paired with
C++ and theme inputs. The public source recipe still excludes the private ROM
recorder; it is not a recorder-preserving personal-device updater.

## Evidence boundaries

Qt tests inject platform observations and dispatch; they prove validation,
version/foreground guards, result minimisation and no fallback. Java contract
tests exercise the actual dispatch target allowlist, and the Android build
compiles the wrapper against the real SDK. Desktop QML tests inject runtime
states and request results. None proves the installed APK identity, physical
buttons, Android focus, cold/warm Steam launch, offline behaviour, return,
controls, screen fit, performance or save restoration on a real device.

The next acceptance gate is an isolated owner-game test with current backups,
version/APK/signer records, exact setup identity and separate boot, menu,
gameplay, controls, sound, save/reopen, offline and return results. Do not change
runtime prefixes or real saves to force a pass.
