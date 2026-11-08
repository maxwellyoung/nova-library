# Private save passports

`tools/save_passport.py` captures explicitly selected save files into a verified portable archive. It can verify the archive later and stage its exact bytes in a **new directory**. It never writes into an existing live save folder, deletes originals, changes emulator settings, accesses a device or synchronizes a cloud account.

This is a host-side backup building block. The current frontend does not yet provide a save-history/import screen for it. A successful stage proves byte recovery, not that an emulator accepts the save or that a captured runtime state can boot. Protect current game progress and test the actual restore separately.

## Capture

Close the emulator normally and obtain its supported save export or accessible save files. Standalone Android apps may require their own export UI; the tool cannot bypass private storage. Use a canonical local source directory without symlink ancestors. Select exact relative filenames, not a wildcard or an entire profile/configuration folder.

A private selection descriptor:

```json
{
  "schemaVersion": 1,
  "editionId": "demo:edition-a",
  "recipeId": "fixture.v1",
  "kind": "native-save",
  "runtime": {
    "name": "Fixture runtime",
    "version": "1.0",
    "core": "Fixture core"
  },
  "files": ["cards/card.srm", "empty.srm"]
}
```

Use `emulator-state` for states and a separate archive from native memory cards. Use the actual stable edition ID and versioned setup ID; the recipe ID follows the [compatibility-receipt contract](COMPATIBILITY.md). No emulator/game identity or region is inferred from a title or filename. Include all files the relevant save format actually needs. The tool cannot determine whether an operator-selected file is a complete save, a ROM, a credential or an unrelated file; it archives only the explicit selection. Keep descriptors and archives private.

```sh
python3 tools/save_passport.py pack \
  --source /path/to/canonical/save-export \
  --selection /path/to/private/selection.json \
  --output /path/to/private/new-backup.nvs \
  --source-idle
python3 tools/save_passport.py verify /path/to/private/new-backup.nvs
```

`--source-idle` is an operator declaration, **not a foreground-app or emulator process check**. A device adapter must first prove its own cold/export boundary. Capture checks file identity, size and modification metadata during each copy and again before publishing. It hashes each payload while copying, verifies the completed archive and publishes to a new filename without replacing an existing one. The output must be outside the save source. A changed source, unreadable file, space failure or existing output prevents publication. Export requires atomic file-link support in the destination filesystem; use private host storage if the chosen card/filesystem lacks it.

Archive creation does not release the original data or prove a second independent backup. Destructive cleanup still needs its own exact-path approval, recovery requirements and restore test. SHA-256 detects payload corruption relative to the manifest; the archive is unsigned and does not authenticate an author or resist an attacker replacing both payload and manifest.

## Staged recovery

Create a target descriptor by taking only `editionId`, `recipeId`, `kind` and `runtime` from the intended target setup. It contains no `schemaVersion` or `files` keys. Verify the actual target configuration before constructing it.

Review a restore without creating any files or directories:

```sh
python3 tools/save_passport.py review /path/to/private/new-backup.nvs \
  --target /path/to/private/target.json
```

`review` verifies the full archive and compares every identity field. Its fixed diagnostics explain edition, save-kind, recipe, runtime, version or core mismatches without printing the private identity values. A successful review means the declared identities and archive bytes match; emulator import and boot are still unverified. It does not find a newer branch, choose a winner, or contact a device/server. Give each divergent branch its own archive and staging directory and compare them deliberately; capture timestamps never resolve conflicts.

```sh
python3 tools/save_passport.py stage /path/to/private/new-backup.nvs \
  --target /path/to/private/target.json \
  --output /path/to/private/new-staging-folder
```

All identity fields must match, including runtime name/version/core and save kind. A native save may genuinely be portable between versions, but this tool makes no automatic compatibility exception; a tested format adapter is a later gate. Emulator states are especially version/core dependent.

Unknown identity labels (`unknown`, `unverified`, `unspecified`, `pending`, `none`, `n/a`, `null`, `?` or `*`, ignoring case) may be captured for safekeeping, but cannot pass review or staging even when both descriptors contain the same placeholder. Version labels `latest` and `current` are also insufficient. Use an actual runtime version and core identity; for a standalone app use a consistent explicit `standalone` core label. The tool compares declarations and cannot discover an installed version or authenticate a claimed edition. Unsupported future passport schemas and duplicate JSON keys at any nesting level are refused instead of guessing which value or format was intended.

The tool verifies before writing, copies into a private temporary area, verifies again and only then creates the new output directory. Existing outputs, links, path traversal, case-colliding or ancestor-colliding paths, extra archive entries, trailing data and corrupt payloads are refused. Filenames are portable relative paths; archive members themselves use fixed numeric names. Archive paths are never handed to an extraction function.

Inspect/compare the staged files, retain the original archive and a separate backup of current target progress, then use the emulator's supported import mechanism at a safe idle boundary. This tool deliberately has no in-place restore or overwrite flag. Actual app restore, game boot, cloud conflicts, SD migration and checkpoint undo remain independent acceptance tests.

## Format and bounds

`.nvs` is an uncompressed USTAR archive with `payload/0000`, subsequent numeric payloads and a final `manifest.json`. The manifest contains schema version 1, stable edition and recipe IDs, save kind, runtime identity, UTC capture timestamp, operator capture declaration, relative file paths, byte counts and SHA-256 hashes. It contains no source root or automatic machine/account identifiers. Explicit descriptor values and save bytes may themselves be sensitive.

Limits: 128 files, 512 MiB per file, 1 GiB payload total, 128 KiB manifest. No archive compression or expansion is supported. POSIX output archives/files use owner-only permissions and staging directories are private; keep them on storage with appropriate privacy controls. Command summaries omit save identities and local paths. `.nvs` is ignored by Git and rejected by the repository privacy scan, including archives whose bytes happen to decode as text.

The Python suite exercises round-trip recovery, empty files, corruption, malformed metadata, symlinks, traversal/collisions, wrong identities, source mutation, changed archives between verification passes, existing-output preservation, private permissions and CLI error redaction. These are filesystem tests using disposable data, not physical Nova save/restore proof.

## Disabled cloud-sync candidate

`tools/prepare_rom_save_sync.py` prepares a separate private RetroArch configuration; it does not apply it. Every generated candidate contains `cloud_sync_enable = "false"`. The legacy `--enable-after-launch-barrier-verified` argument now refuses rather than treating an operator assertion as installed launch-order evidence. Automatic sync/restore remains unavailable until a trusted pre-launch barrier and a copied native-save restore have been verified on the current installed runtime/core. There is no automatic passport restore.

The preparer preserves the existing save layout and controls, and disables configuration, system and thumbnail sync. Content-directory save/state settings are refused even with inline comments; duplicate or unrecognized layout settings and config includes require explicit review. It does not scan profiles, infer external included-file settings, or establish which native saves/states the installed client's saves category covers. Keep states separate and do not enable state autoload for the restore test. An independent backup and a deliberate two-branch conflict test are still required before real enrollment.

Credentials arrive through stdin, outputs are owner-only and exclusively created outside this repository, and CLI failures omit paths and credential values. Keep candidate files out of every repository and publication. These local checks do not establish remote sync, conflict resolution, startup ordering or current-device recovery.
