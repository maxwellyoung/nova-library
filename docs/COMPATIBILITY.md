# Compatibility receipts

A launch route, an installed file and a gameplay result answer different questions. **Details → Checks** shows independent observations for boot, menus, gameplay, physical controls, sound, save/restore, exit/return and sustained play. It reuses the read-only Controls list and returns to Details without changing the selected game. Select a row and press A for its complete, scrollable note; Back returns to that row. Long notes stay intact even when the compact footer truncates its preview.

## Scope and trust

These are imported, informational records, not authenticated hardware telemetry. Each observation shows its source, method and UTC date. It never grants launch permission, runs a command, changes a driver, restores a save or certifies another scene. A later stage does not imply earlier stages. An injected-input check cannot establish physical controls or audible sound. Sustained observations require an explicit scene note and a positive measured duration; the UI shows the actual duration rather than a universal performance score.

`x-compatibility-receipts` contains a JSON array (at most 32 records, 64 observations per record, 256 KiB total). `x-compatibility-recipe-id` explicitly links the entry to one recipe. Edition identity must match `x-edition-id`. Disc members retain separate records; a group's Checks applies to its displayed disc edition. No ID is inferred from a similar title.

The exporter/operator must update the linked recipe ID when the actual runtime, device or settings change. The theme cannot inspect an emulator's private live configuration. Without an explicit matching link, records are historical and all current stages remain not checked. Different configurations using the same recipe ID are a visible conflict and supply no current evidence. When a stage has several observations in one setup, its newest result wins; equal-time pass/fail disagreement resolves to failure. Old results stay in the portable record.

Legacy `x-nova-gameplay-*` notes remain visible in Info with their original dates/sources. They do not fill this ladder, because a short note does not establish separate stage tests. An invalid record is counted visibly, never silently upgraded. Unknown schema versions, impossible/future dates, markup, invalid durations and excessive sizes are rejected. Text is bounded, plain, and not executable. Unknown setup details should be written explicitly as unknown, not guessed.

## Recorded failures

When a linked setup retains failures, Checks starts with **Recorded failure**. It selects the newest failure among each stage's latest observations, retains the exact scene note, date, source and method, and says explicitly that the cause is not established. Press A for the full scrollable explanation; Back returns to the same row and edition. Other failed stages remain listed independently. A newer pass clears only that stage's failure; passing gameplay never clears a failed save or return check.

The next step is fixed guidance for the recorded stage, not a generated root cause or an executed repair. Save failures recommend keeping both copies and comparing edition/runtime/save kind. Return failures keep cleanup blocked until the runtime's idle boundary is established. Input/audio failures require an actual button/listening check before claiming recovery. No settings, profiles, saves, launches or network requests are changed. Unlinked, historical, conflicting, invalid or cross-edition records supply no current failure guidance. Imported test/log observations retain those methods and never become live device diagnosis.

The separate host-side [failure bundle](FAILURE-BUNDLES.md) also accepts the `offline-launch` stage for structured failure reports. This vocabulary alignment adds no device collection, automatic export or offline-readiness certification.

## Format

This fictional example supplies one menu observation, not gameplay or sound proof:

```json
[
  {
    "schemaVersion": 1,
    "editionId": "demo:tidal-garden",
    "recipe": {
      "id": "fixture.menu.v1",
      "device": "Synthetic handheld",
      "runtime": "Fixture emulator",
      "version": "1.0",
      "core": "Fixture core",
      "driver": "Fixture driver",
      "display": "Fit 4:3",
      "input": "Fixture pad profile",
      "settings": "Default fixture settings"
    },
    "checks": [
      {
        "stage": "menus",
        "result": "pass",
        "observedAt": "2026-11-03T10:00:00Z",
        "method": "injected",
        "source": "Synthetic QA",
        "note": "Opened Options and returned; no game started"
      }
    ]
  }
]
```

Stages: `boot`, `menus`, `gameplay`, `physical-controls`, `audio`, `save-restore`, `exit-return`, `sustained`, `native-4-3`, `stretch-only`, `offline-launch`. Result: `pass` or `fail`; an absent stage means not checked. Methods: `physical`, `owner`, `observed`, `injected`, `log`, `test`. Passing physical controls/audio requires `physical` or `owner`. Passing display observations require `physical`, `owner`, `observed` or `injected`; a log or pure test fixture cannot certify a rendered picture. Failure observations can retain log/test methods and remain unconfirmed. Add integer `durationSeconds` for sustained observations (1 to 604800); it is optional for other stages. UTC timestamps include seconds, optional milliseconds and `Z`.

## Scene measurements

A `menus`, `gameplay` or `sustained` check can retain an optional structured
`performance` sample. A positive `durationSeconds` is required when it is present:

```json
{
  "context": "gameplay",
  "scene": "Courtyard fight",
  "measurement": "Synthetic frame-time log, whole scene",
  "metrics": {"averageFps": 59.8, "p95FrameMs": 18.2, "p99FrameMs": 24.5}
}
```

This is a fictional sample, not a measured game result. Context is `menus` for
menu checks; gameplay checks allow `gameplay`, `cutscene` or `mixed`; sustained
checks allow `gameplay` or `mixed`. A menu/cutscene sample cannot be filed as a
sustained gameplay measurement. Existing checks without samples remain valid,
but no numerical performance or frame pacing is inferred from their notes,
duration, scene label, launch route or configured display.

Scene (160 characters) and measurement method/instrument (200) are required
plain text. At least one of the three named numeric metrics is required:
`averageFps` from 0 to 1000, and positive frame-time percentiles at most 60000 ms.
The 99th percentile cannot be below the 95th when both are supplied. Missing FPS
or frame-time statistics stay **Not measured**; a measured 0 FPS is distinct.
Unknown metric/sample keys and invalid values reject the record. No percentile
is calculated from FPS, and averages do not establish frame pacing. Measurement
labels and imported figures remain operator claims, not authenticated telemetry.

Checks adds a measurement row directly after its observed stage, opening the
existing full-note view. It shows the exact scene, duration, context, metric
units, instrument, source, method, date and linked runtime/driver/settings. It
does not put a universal FPS score on the game card or promote any other check.
Samples use the same exact edition/setup link and newest-per-stage rule as the
ladder. A newer check with no measurement supersedes the older sample in this
view. Same-time, same-result observations with different samples or sample
durations show **Conflicting samples**, withholding figures; original records
remain unchanged in the portable copy. The existing equal-time failure rule
still wins over a pass. Earlier scene readings remain in the portable records;
this view is not a full multi-scene benchmark browser.

The portable CLI retains the structured sample with its recipe and duration.
Older readers can ignore this optional field; exporting through them may drop
the measurements. Keep the original portable copy when exchanging versions.
All current UI checks use synthetic readings. Device-side measurement capture,
instrument calibration, real game scenes and physical navigation remain separate
acceptance gates; this feature does not collect frame telemetry itself.

## Offline launch evidence

`offline-launch` requires two additional explicit fields: `network: "disconnected"` and `coldStart: true`. The observer must close the runtime and test launch with network access disconnected; switching off Wi-Fi alone is not evidence if another connection remains. A pass requires an actual `physical`, `owner`, `observed` or `injected` observation. Pure tests and logs may retain failures, but cannot certify an offline pass. The note should name the scene/mode reached and limits of the test. The portable exporter preserves both conditions.

Checks shows this stage independently. Details displays a dated **Offline launch tested** summary only for the exact linked setup while both current file-presence signals are explicitly present and its local launch route remains enabled. Missing/unknown files and disabled routes suppress that positive summary while retaining the historical check in Info. Changed recipe links, conflicting configurations, future observations and a later failure do not yield a positive current summary. One tested disc is labelled with its disc number and never establishes a complete offline disc set.

These are imported operator observations, not authenticated network telemetry. There is no automatic network probe, download, launch, input change or save operation. The theme cannot inspect live emulator settings or rehash private game data: the operator must version/relink the recipe after changing the actual game/runtime/setup. A dated offline cold launch does not prove offline saves, all game modes, media-service downloads, current remote-server availability or a complete travel pack. A real device check is required before adding a pass to a real catalogue; synthetic fixture passes remain fixtures.

Older readers that do not support `offline-launch` reject that record. Keep it separate from existing stage records when exchanging with older clients, so unsupported evidence cannot silently become a positive or hide every other supported record.

## Display checks

`native-4-3` records an observed native 4:3 render in the stated setup. `stretch-only` records that the tested setup fills the display by stretching; it is not a claim that every configuration of that game requires stretching. A recipe's free-text `display` description alone never supplies either check. Explain the actual setting, scene and observation in the note. Original release aspect is a separate sourced catalogue fact.

Library's Aspect filter uses these edition- and recipe-scoped observations. Changed recipe IDs, conflicting recipe definitions, malformed/future observations and failed checks cannot create a positive match. Simultaneous native/stretch-only passes conflict and remain unconfirmed; when a setup changes, give it a new recipe ID instead of leaving contradictory passes under one identity. Missing or failed confirmations remain discoverable under Setup unconfirmed. This UI reads reported evidence; it cannot verify that a private live emulator configuration still matches the catalogue. It never changes display settings or launch readiness.

Older readers that do not recognise the two optional display stages reject those records rather than guessing. Existing records without display stages remain valid.

Recipe IDs are edition-scoped, versioned labels, not a cryptographic signature. Recipe fields are required plain-text descriptions. They do not include launch scripts, ROMs, account identities, file paths, save data or credentials. Separate configuration IDs must identify real differences rather than relabelling failed tests.

## Portable copy

```sh
node tools/compatibility_receipts.cjs validate /path/to/records.json
node tools/compatibility_receipts.cjs export /path/to/records.json /path/to/new-portable.json
```

Both use the theme's own validator. Export writes only the supported fields to a new owner-only file and refuses to overwrite an existing output. It does not enroll a device, update metadata or publish anything. Unknown fields are dropped, but free text can still contain private information: review the complete text and provenance before sharing. Public distribution remains an explicit approval and licence/privacy review gate.

Before claiming a recipe works, protect current saves, physically exercise the stated checks on that exact device/runtime/configuration, retain failure evidence and verify recovery. This source UI and its synthetic tests do not prove those device checks.
