# Compatibility receipts

A launch route, an installed file and a gameplay result answer different questions. **Details → Checks** shows independent observations for boot, menus, gameplay, physical controls, sound, save/restore, exit/return and sustained play. It reuses the read-only Controls list and returns to Details without changing the selected game. Select a row and press A for its complete, scrollable note; Back returns to that row. Long notes stay intact even when the compact footer truncates its preview.

## Scope and trust

These are imported, informational records, not authenticated hardware telemetry. Each observation shows its source, method and UTC date. It never grants launch permission, runs a command, changes a driver, restores a save or certifies another scene. A later stage does not imply earlier stages. An injected-input check cannot establish physical controls or audible sound. Sustained observations require an explicit scene note and a positive measured duration; the UI shows the actual duration rather than a universal performance score.

`x-compatibility-receipts` contains a JSON array (at most 32 records, 64 observations per record, 256 KiB total). `x-compatibility-recipe-id` explicitly links the entry to one recipe. Edition identity must match `x-edition-id`. Disc members retain separate records; a group's Checks applies to its displayed disc edition. No ID is inferred from a similar title.

The exporter/operator must update the linked recipe ID when the actual runtime, device or settings change. The theme cannot inspect an emulator's private live configuration. Without an explicit matching link, records are historical and all current stages remain not checked. Different configurations using the same recipe ID are a visible conflict and supply no current evidence. When a stage has several observations in one setup, its newest result wins; equal-time pass/fail disagreement resolves to failure. Old results stay in the portable record.

Legacy `x-nova-gameplay-*` notes remain visible in Info with their original dates/sources. They do not fill this ladder, because a short note does not establish separate stage tests. An invalid record is counted visibly, never silently upgraded. Unknown schema versions, impossible/future dates, markup, invalid durations and excessive sizes are rejected. Text is bounded, plain, and not executable. Unknown setup details should be written explicitly as unknown, not guessed.

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

Stages: `boot`, `menus`, `gameplay`, `physical-controls`, `audio`, `save-restore`, `exit-return`, `sustained`, `native-4-3`, `stretch-only`. Result: `pass` or `fail`; an absent stage means not checked. Methods: `physical`, `owner`, `observed`, `injected`, `log`, `test`. Passing physical controls/audio requires `physical` or `owner`. Passing display observations require `physical`, `owner`, `observed` or `injected`; a log or pure test fixture cannot certify a rendered picture. Failure observations can retain log/test methods and remain unconfirmed. Add integer `durationSeconds` for sustained observations (1 to 604800); it is optional for other stages. UTC timestamps include seconds, optional milliseconds and `Z`.

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
