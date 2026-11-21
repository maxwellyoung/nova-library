# Checked native save capture

`tools/native_save_capture.py` connects the [save-passport format](SAVE-PASSPORT.md) to two explicitly checked Android save layouts. It reads the selected device, verifies the installed APK and game-data hashes, requires the game to be closed, and captures only the listed save files. It never launches/stops an app, writes a device file, imports progress, changes permissions or enrolls cloud sync.

This is an operator-side adapter, not an installed Library screen or automatic backup service. A successful capture proves recovery of the captured bytes. It does not prove the game will load a later restore.

## Supported profiles

| Profile | Exact checked runtime | Save selection |
|---|---|---|
| `soh-nova-slot1` | Ship of Harkinian Android `9.3.1-android.4`, checked Ocarina US 1.2 data | `Save/file1.sav` and `Save/global.sav` |
| `diablo-shareware-hero0` | DevilutionX Android `1.5.5`, checked official shareware data | `spawn_0.sv` |

The APK and working-data SHA-256 pins are in `PROFILES` in the source. Hashing game data does not copy it into the backup. Zelda's other slots, Diablo's other heroes/full-game saves, emulator states and Mario are not covered. Mario's earned-progress save path and reload still need a real check before an adapter can be added.

These are conservative profiles for the exact Nova setup that was exercised. Even a repack of the same named version is refused. Pin updates require checking the real package, game data, save layout and recovery; the tool never accepts a user-supplied checksum override or infers compatibility from a title.

The archive's edition ID stays linked to the native game. Its recipe ID names this **save capture profile**, independently of display/input settings. It does not attest to an unchanged gameplay configuration. Older manually described passports with different recipe IDs remain separate; no automatic migration or identity rewriting is provided.

## Inspect and capture

Use an explicit ADB serial; the adapter never chooses the first attached device. Close the game normally first, including any background native process. If Android still retains a process, the adapter refuses. It does not kill the process for you.

Choose a new backup file in an existing owner-only directory outside every repository:

```sh
NOVA_SAVE_DIR="$HOME/.local/share/nova-save-backups"
install -d -m 700 "$NOVA_SAVE_DIR"
# Set NOVA_SAVE_SERIAL to the intended device's ADB serial.
python3 tools/native_save_capture.py inspect \
  --serial "$NOVA_SAVE_SERIAL" --profile soh-nova-slot1
python3 tools/native_save_capture.py capture \
  --serial "$NOVA_SAVE_SERIAL" --profile soh-nova-slot1 \
  --confirm-closed --output "$NOVA_SAVE_DIR/zelda-new-checkpoint.nvs"
python3 tools/save_passport.py verify "$NOVA_SAVE_DIR/zelda-new-checkpoint.nvs"
```

`inspect` reads identities, file metadata and checksums, without fetching save payloads or creating an archive. `--confirm-closed` is still an operator declaration: PID checks are observations, not a runtime lock or a prelaunch barrier. Do not start the game while capture is running.

Capture checks package/data identity and idle state before and after copying. Each source file has a bounded size and a metadata/checksum snapshot. Copied bytes must match, and every source must still match before publication. Linked sources, missing/empty saves, changed sources, unknown APK/data, device errors and existing outputs are refused. Save payload reads are capped at 4 MiB per selected file; device reads have a timeout. Only verified archives are linked to a new destination. Existing backups are never replaced, including a competing writer's destination.

Archive payloads and temporary files stay in the private host output area; no ROMs, assets or configuration files are selected. The archive contains identity labels, save paths relative to their source root, checksums and the actual private progress bytes. No device serial, host path or account identifier is automatically added.

## Recovery boundary

Use `save_passport.py review` and `stage` with the profile's exact identity descriptor to reconstruct files in a new disposable directory. See [the recovery instructions](SAVE-PASSPORT.md). Wrong edition, recipe or runtime identities are refused. There is no live-restore option in this adapter.

Actual runtime import/load, Library save history and recovery UI, before-launch protection, background scheduling and cloud conflict handling remain separate integrations. Do not schedule the CLI against active games or treat a captured passport as permission to overwrite current progress.

## Verification

```sh
python3 -m unittest discover -s tests -p test_native_save_capture.py -v
python3 -m unittest discover -s tests -p test_save_passport.py -v
```

The adapter suite exercises real passport packing/staging with disposable files, wrong identities, unselected assets, missing/empty saves, active/restarting apps, changed APK/game data, changing save files, private output boundaries, destination races and redacted device failures. Fake devices test refusal cases; actual Nova capture/recovery evidence is retained privately outside this repository.
