# Verified microSD preparation

`tools/rom_migration.py` copies an explicit set of edition/file pairs into a new
destination, checks all source and destination hashes, retains every original and
writes a completion receipt. It never deletes a source, formats a card, rewrites
a playlist, changes a catalogue/launch route or moves a save implicitly.

```
python3 tools/rom_migration.py plan /private/rom-root \
  --entries /private/selected-files.json --output /private/new-copy-plan.json
python3 tools/rom_migration.py copy --plan /private/new-copy-plan.json \
  --destination /private/new-card-folder --approve-digest REVIEWED_PLAN_SHA256
python3 tools/rom_migration.py verify /private/new-card-folder
```

Selection is a JSON array of `{ "editionId": "fixture:edition", "path": "game.bin" }`.
Keep real plans outside repositories: they contain private paths and game identity.
The plan binds every edition, relative path, byte count and checksum. Changed plan
or source, existing destination, links, overlapping names, reserved control names
and insufficient destination space refuse. Originals remain even after success.
An interrupted destination keeps MIGRATION-INCOMPLETE and cannot verify; preserve
it for review. Explicit `copy --resume` requires the identical plan, validates
every existing byte prefix against its source, appends only remaining bytes and
rechecks full hashes. A changed prefix or unmanaged file is preserved and refused.
There is no automatic cleanup of failed copies.

The receipt preserves edition IDs as data. It does not prove history continuity
after a real launcher change. Before selecting the new path on Android, review
playlist/CUE dependencies, content-directory saves, actual emulator permissions,
BIOS/artwork locations, supported runtime identity and the stable edition link.
Copy all necessary companion files explicitly. Then verify launch, disc changes,
native save/state reopen, offline behaviour and return on the actual card. Only
after a separately reviewed route update and recovery test may old file cleanup
be considered. This tool supplies no authority or trusted runtime-idle evidence
for deletion.
