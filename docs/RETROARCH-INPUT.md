# Reviewed RetroArch input configs

`tools/retroarch_input.py` maps selected portable input preferences into private
RetroArch Android AArch64 **1.22.2**, source commit
`69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`, configs. It reuses the existing display
adapter's private generations, exact preview/confirmation, locking, journal,
interruption recovery and revert engine. Display and input workspaces have distinct
markers and refuse each other; existing display behaviour is unchanged.

This is an operator/host adapter. It does not launch an emulator, replace its
existing profile, stage files on Android, prove an installed APK/core, or make the
Library editor apply gameplay controls. Those integration gates remain open.

## Supported mapping and shared effects

| Selected group | Required shape | Runtime setting |
| --- | --- | --- |
| Sensitivity | Horizontal and vertical values equal | `input_analog_sensitivity` |
| Deadzone | Left and right values equal | `input_analog_deadzone` |

The runtime settings are shared, including **analog buttons**, not independent
axes/sticks. The pinned function uses a radial magnitude for sticks and a linear
magnitude for analog buttons. Sensitivity can clip at full scale. The review must
acknowledge this broader effect with `--allow-shared-analog`; it is never inferred
from a general preference save. Unrelated config bytes stay unchanged, but effective
analog-button response can change as a result of the selected shared settings.

Unequal values refuse for that group rather than being averaged. Inversion,
separate trigger thresholds and per-game aim/sprint/crouch hold/toggle are explicitly
unmapped, even when their saved values happen to resemble defaults. Only groups
named by `--field` are selected; `notApplied` lists the rest. Mapping is source
support, not a physical or installed-runtime compatibility result. Runtime floats
have their own precision; the portable model's double values are not a precision
promise.

Input is exactly the version-one single-profile envelope exported by
`InputProfiles.js`. Runtime ID must be `retroarch-android-aarch64`, version `1.22.2`.
Do not infer architecture from a human label such as RetroArch. The complete
edition/runtime/version binding is hashed for workspace indexing and retained in
reviewed choices. Long Cloud IDs are not truncated or matched by prefix/title.
Changed versions require a separately reviewed adapter.

## Private review flow

Use a new workspace outside Git and an explicitly reviewed **flat effective**
baseline whose `auto_overrides_enable` and `config_save_on_exit` are already false.
The tool refuses includes, duplicate/unknown syntax, unsupported analog values,
unknown runtime identity, expired or edited plans, stale selection and unsafe files.
It does not silently disable unrelated baseline settings. Source configs can contain
credentials: keep the originals, workspace and stdout review files private.

```sh
python3 tools/retroarch_input.py mapping --profile /private/profile.json
python3 tools/retroarch_input.py init /private/new-input-store
python3 tools/retroarch_input.py preview /private/new-input-store \
  --profile /private/profile.json --field sensitivity --field deadzone \
  --allow-shared-analog --baseline /private/reviewed-flat.cfg
```

Preview is read-only. Retain its exact JSON as a private plan, inspect the delta,
unsupported groups and shared effect, then use its exact token within 60 seconds:

```sh
python3 tools/retroarch_input.py confirm /private/new-input-store \
  --plan /private/reviewed-plan.json --token EXACT_REVIEWED_TOKEN \
  --baseline /private/reviewed-flat.cfg
```

The first confirm retains an exact original generation. Later previews for the
same binding omit `--baseline`; they cannot replace its existing baseline. Confirm
selects a new managed config and returns its path plus the existing Android
`CONFIGFILE` adapter point. It does **not** send that intent. Each resulting receipt
keeps `deviceApplied`, `installedRuntimeVerified` and `gameplayVerified` false.

`preview-revert` accepts the same `--profile` to identify the exact binding. Review
and confirm that new plan without a baseline to select the previous generation.
Repeated deliberate reverts reach the exact original bytes. `recover` restores the
prior selection after an interrupted switch; normal operations refuse while its
journal remains. Newer outside changes refuse rather than being overwritten.
Unselected/incomplete generations stay for inspection. Hash tokens bind a review;
they do not authenticate the caller or defend against a malicious same-user process.

No automatic restore, directory deletion, global profile change or save access is
performed. The Python helper is not shipped/executed by Android Library. A real
native adapter must verify APK/signer/source/core, stopped-runtime state, content
and route, readable config delivery and Android permissions without exposing a
private baseline in shared storage. It must then prove actual application and
rollback in the game. Existing baseline controls, hotkeys, save/core paths and
other runtime settings need preservation before that step.

## Source and verification

The pinned `configuration.c` registers the two float settings and loads them into
`settings->floats`. `input/input_driver.c` passes those values to the retained
`input_joypad_axis` function. `native/retroarch-input/source.json` binds the exact
source and extracted function hashes, with original GPL notices alongside it.

The host tests compile that unchanged function with a synthetic axis driver,
pass translated config values and check deadzone removal, sensitivity, sign and
clipping. This proves the bounded function behaviour, **not** the whole config
loader, an actual Android intent, a core's use of analog input, physical controls,
latency, fun or real-game compatibility.

```sh
python3 -m unittest discover -s tests -p 'test_retroarch_input.py' -v
```

The same suite checks JS export interoperability, unsupported groups, explicit
shared-effect review, selected-field-only changes, long identity isolation,
private-baseline preservation, restart/revert, staleness, corrupted generations,
locks/write failure and real child-process interruption at both transaction
boundaries followed by fresh-process recovery. Use a C compiler for these source
checks. It builds a tiny temporary host probe, not RetroArch or an Android APK.

Primary sources:
- https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/configuration.c
- https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/input/input_driver.c
- https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/frontend/drivers/platform_unix.c
