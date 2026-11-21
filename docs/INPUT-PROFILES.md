# Offline input profiles

`theme/InputProfiles.js` is a local preference model with a Controls editor on
builds prepared with `--checked-memory`. It is not wired to a gameplay runtime. Saving/importing a profile does not change gameplay,
controller settings, emulator configuration, shortcuts or saves. Runtime support
is **unknown** and application is **not-applied**, including after a successful
edit or import. No supported runtime matrix is asserted by this module.

A binding contains exactly `editionId`, `runtimeId` and `runtimeVersion`. Use the
catalogue's stable edition ID and an explicit recorded runtime name/version; unknown/latest
placeholders are refused. Another edition, runtime or version never inherits a
profile. Titles, current launch selection and fuzzy names do not resolve bindings.
An app update leaves the older profile intact and requires deliberate review of
the new binding. This identifies declarations, not an authenticated installed app.

Each profile stores all five preference groups; missing/unknown fields refuse the
whole operation. Bounds describe portable preferences, not runtime units or a
promise that a game supports them:

| Group | Fields | Values |
| --- | --- | --- |
| `sensitivity` | `x`, `y` | finite multiplier 0.1–10, inclusive |
| `deadzone` | `left`, `right` | normalized stick fraction 0–0.95, inclusive |
| `inversion` | `x`, `y` | booleans |
| `triggers` | `left`, `right` | preferred normalized activation threshold 0–1, inclusive |
| `holdToggle` | `aim`, `sprint`, `crouch` | `hold` or `toggle` |

No game/menu detection, automatic mode switching, remapping, macros, commands,
paths or runtime support/application claims are accepted. A future adapter must
explicitly translate these preferences, disclose unsupported fields and verify
effective gameplay and rollback independently.

## Caller contract

- `store(undefined)` creates `{version:1, profiles:[]}` only when storage is known
  absent. `store(raw)` validates/reopens an existing document and returns a deep
  copy, or `null` for unsupported/corrupt data. Do not turn a read error into
  `undefined`; keep original bytes and expose the failure.
- `edit(state, binding, preferences)` creates/replaces one exact binding;
  `clear(state, binding)` removes only that binding. They return a new document,
  or `null` on refusal. `undefined` is refused as an editing state; initialize
  intentionally with `store(undefined)`. Neither function mutates its input.
- `profile(state, binding)` returns an independent copy or `null`.
- `exportProfile(state, binding)` returns JSON `{version:1, profile:{binding,
  preferences}}`, or `null`. `importProfile(state, binding, text)` validates that
  exact envelope and matching binding, then atomically returns a new document.
  It never silently retargets, merges fields or changes other profiles.
- `status(state, binding)` reports storage readability, saved presence,
  `support:"unknown"` and `application:"not-applied"`.

The model holds at most 256 bindings. Edition IDs are bounded to 512 characters,
runtime identities to 160 portable name characters (including literal spaces),
versions to 80 portable token characters, and import text to 16,384
UTF-16 code units. JSON syntax, duplicate keys (including escaped equivalents),
unknown fields/versions, nonfinite or coerced values and duplicate stored bindings
are refused. Refusal returns `null`; it never clears or repairs original data.
This schema has no migration or automatic pruning policy.

The editor uses the optional [checked theme-memory writer](../native/theme-memory/README.md).
It publishes a saved state only after a successful atomic file commit. Failed or
conflicting writes retain the preceding saved state and the unsaved draft. File
import/export dialogs remain future work; the pure JSON APIs below do not open files.
Clear removes a Nova preference only; it cannot roll back a runtime setting.
An exported preference is not a runtime backup or an applied-controls receipt.

Run `node --test tests/input-profiles.test.cjs`. The tests exercise offline
edit/clear, serialized reopen, strict import/export, bounds, exact binding and
refusal preservation. They do not establish Android persistence, physical controls,
gameplay, runtime application, another game's isolation on a real device, or
rollback of effective runtime controls. Those remain integration/device gates.

## Controls editor

Details → Controls → Input preferences appears only with the checked read/write
capability. It uses the exact remembered PC-runtime choice, or the edition's linked
compatibility setup. The runtime and version must pass the model's explicit token
rules. Missing/unknown setup information opens an explanation instead of inventing
a runtime. These are retained declarations, not proof of the currently installed
runtime. Displayed disc editions stay separate.

Left/right adjusts a field; Accept changes a toggle. Save preferences commits the
whole exact profile. Back asks before discarding a changed draft. Clear has a
confirmation whose default keeps the saved copy. Touch uses the same rows and
shared launcher footer. Starting values are labelled as starting preferences,
not detected runtime settings. A version change opens a separate profile and keeps
the old one. The editor always says **Not applied**. No settings are sent to an
emulator or PC runtime; save files, shortcuts and other profiles are untouched.

The fixture `tools/smoke_input_profiles.py` uses the real native `Memory` class,
not mock QML persistence. It checks exact edition/version isolation, saving,
lock refusal/retry, cancel/discard, confirmation, external-file refusal and a new
process reopening the exact committed file. Its synthetic catalogue and injected
keys do not establish Android storage, physical controls or effective gameplay.

## First source-supported runtime mapping

The separate [RetroArch host adapter](RETROARCH-INPUT.md) accepts the exact exported
profile and explicitly selected shared sensitivity/deadzone groups. It refuses
unrepresentable values and requires review of effects on analog buttons too.
It produces/selects private configs with exact revert/recovery; it is not connected
to this editor or Android launch dispatch. Saving here therefore still says Not applied.
