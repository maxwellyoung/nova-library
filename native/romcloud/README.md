# ROM cloud client

An optional Qt 5.15/6 native bridge for the existing Nova interface. A bridge advertising `catalogueVersion: 1` supplies cloud copies to the normal Library, Consoles and Details. Their primary action installs, resumes or verifies and plays that copy. `CloudLibrary.qml` presents a focused download view and returns to the originating selection; Settings → Cloud library retains the complete connection/maintenance view. Older bridges keep that separate shelf. Theme-only operation, the save picker and the existing progress bridge do not require it.

## Catalogue and launch continuity

The native bridge mints each edition ID from a canonical server origin, game ID and content descriptor (platform, entry filename and sorted payload names, byte counts and checksums). Titles and server file IDs are not identity. Installed copies retain their ownership marker's content identity when the remote catalogue changes. They remain distinct from matching titles in Pegasus; there is no fuzzy merge. The stable origin/game key preserves selection across a later scan without joining the old and new content editions.

Cloud entries use the normal search, filters, console browsing, Details and local favourites. After Android accepts a verified launch, versioned local history makes that edition eligible for Home's recent shelf. This records an opening, not playtime or progress. Unsupported/corrupt history is retained rather than silently replaced. Cloud favourites are local; service-backed status/collection edits stay unavailable until these content identities are registered by the progress service. The native edition-scoped notebook remains separate.

Immediately before launch, after hashing, `launchPrepared` supplies the exact installed identity for the existing ROM recorder. Android uses `MainActivity.launchAmCommand` with a literal allowlisted argv array, preserving the existing launch/recorder boundary. No server command is executed. Only Android's accepted result emits `launchAccepted`; a desktop signal is not a successful device launch. Actual foreground intervals, emulator return and central media ingestion require their own runtime checks.

`launchChecking` exposes pre-launch verification. Leaving the frontend cancels this pending launch check, without cancelling an ordinary download. Catalogue rebuilds are debounced, ignore scan-only timestamps and retain the originating game. These source/host checks do not establish Android background-download persistence or suspend/resume behavior.

The first adapter targets RomM **5.4.1**'s `/api/roms` paged catalogue and its individual-file download endpoint, `/api/roms/{file_id}/files/content/{file_name}`. It accepts an origin and a separately scoped ROM-read token; credentials never enter QML, catalogue JSON, SQLite, URLs or logs. Redirects are refused. HTTP is limited to loopback and Tailscale addresses; HTTPS is preferred.

Supported download/launch adapters: SNES through Snes9x and PlayStation through SwanStation in RetroArch AArch64. Other consoles remain visible with an unavailable explanation. The relevant core must already be installed. File hashes must be present from a server scan. PS1 multi-file entries must contain a valid M3U with their discs; CUE/BIN sets and archive extraction are deliberately not part of the initial adapter.

Downloads use a dedicated `nova-cloud/<rom-id>` subtree under the selected ROM root. Interrupted bytes and a matching plan are retained in `.partial`, resumed with HTTP Range, and checked against RomM's SHA-1 or MD5 file checksum. A complete install is activated by a directory rename only after every file and playlist passes. The client never removes arbitrary preexisting folders or emulator saves. Removal refuses extra files, directories or symlinks. Successful downloads and the catalogue remain usable without a network connection.

Before opening a download, the client validates its local ownership record and
requires the launch target to be one of the recorded, supported files. Linked
markers, unlisted targets and malformed records cannot supply a launch route.
It then checks every payload checksum on a worker thread, including later discs,
and rechecks file/marker identities before requesting the launch. This works
offline. Large discs take time to read; the existing progress indicator remains
responsive and Pause cancels the pending launch. A same-size corruption or a file
changed during verification is kept for review rather than opened or silently
replaced. These checks do not establish save compatibility, actual core
availability, or protection against another process with the same file access
replacing files after the final check.

Before downloading, the optional `installPlan(id)` preview measures available space on the selected ROM volume, accounts for matching retained partial bytes, and exposes the existing 128 MiB working headroom. It creates no directories or downloads. The UI shows required remaining bytes, free space and any shortfall; it blocks a known non-fitting download while preserving remove/cancel paths. Installation measures again before writing, so a displayed plan is not a storage reservation. Unavailable space stays unknown rather than zero.

Recovery facts distinguish a partial folder from files that can actually be
resumed. The same partial inspection supplies catalogue labels, the preflight
and the install boundary. A foreign endpoint, changed descriptor, extra file
(including a save), linked marker/payload or oversized retained file blocks
resume and keeps the files. These facts contain no endpoint or credentials.
Matching retained bytes are measured file lengths, not verified content; every
completed payload still needs its checksum before activation. Earlier plans
without an endpoint retain their existing exact-descriptor/final-checksum path.
Older bridges without these facts offer Check download rather than promising
Resume. Active transfer labels are separate from interrupted files. A blocked
resume still permits a separate cleanup review, whose existing runtime/safety
guards remain mandatory; this does not enable Android deletion.

### Review cleanup before removal

`cleanupPlan(installId)` lists other cloud-managed complete or partial downloads. It does not scan arbitrary ROM folders, installed apps or emulator-private storage. Each `removalPlan(id)` measures the actual payload bytes and file count, checks endpoint ownership, and protects extra files, links, incomplete metadata and unsupported payload types. Logical file bytes are an estimate of the candidate, not a promise of reclaimed filesystem capacity.

The existing Cloud screen's **Make room** action retains the intended install selection. A reviews one eligible candidate; a second A confirms that exact preview. B cancels or returns to the install selection. Previews expire after 60 seconds. Refreshing or changing selection clears the confirmation.

`removeDownload(id, previewToken)` rechecks identity, ownership and runtime safety before detaching the folder, and checks again before deletion. It deletes only the reviewed filenames, with metadata last; it never recursively sweeps a directory. A changed or newly arriving file is retained. On partial failure, remaining files can be left in a sibling `.removed` folder; inspect and preserve it before any recovery action. Never recursively delete that folder merely because its name ends in `.removed`. Successful removal reports the measured before/after free-space delta separately; other device activity can affect it.

Removal requires a trusted native `RomCloudConfig.removalBlocker` adapter. An empty result means the adapter established that the runtime is idle; a nonempty result explains the blocker. **The production Android adapter is not connected yet, so cleanup is review-only and deletion is blocked.** Returning to Library, a missing foreground event or an operator assertion is not sufficient idle proof. QML cannot enable or bypass this guard. Tests inject a synthetic idle adapter only for disposable fixtures.

## Native source integration

First apply the base Nova bridge patch as documented by the repository README. Then run:

```
python3 tools/apply_rom_cloud.py /path/to/patched/pegasus --backup /path/to/new/private/backup
```

This adds the source module, Java vault and a `romCloud` QML context property. It does not build, deploy, enroll or modify emulator settings. Both qmake and CMake source lists are updated. Existing native modifications are preserved and changed integration files are backed up. The original bridge's enrollment is untouched.

On Android a separate app-private `rom-cloud-enrollment.json` contains `endpoint`, `token` and `romRoot`. The operator injects it only after specific service/device authorization. The new `RomCloudVault` seals it with a separate Android Keystore alias and removes the plaintext after the encrypted file is durable. Do not put enrollment in source, shared storage or an APK. Desktop tests inject synthetic configuration directly; ordinary desktop builds stay unconfigured.

## Save synchronization

The prepared WebDAV settings stay **disabled by default**. RomM documents a RetroArch frontend-launch race: the core can read a local save before startup sync finishes, then upload it over a newer server save. Merely enabling Cloud Sync is not a verified automatic-save solution.

The next runtime gate is a pre-launch synchronization barrier (start RetroArch without content, confirm sync completion, then load the game), or a separate guarded device-sync adapter. Keep automatic save sync off until this ordering and a copied-memory-card restore are proven on the actual device. The config preparer refuses its legacy enable flag until that startup ordering is implemented and verified. It can prepare only a disabled candidate; the flag is not an escape hatch for the runtime test.

References: https://docs.romm.app/5.4.0/ecosystem/retroarch-cloud-sync/#launching-a-game-from-a-frontend

Use RomM's existing RetroArch WebDAV integration only once that gate is satisfied. The native ROM-read token is separate from RetroArch's password-authenticated save account. `tools/prepare_rom_save_sync.py` creates a private candidate config from a backed-up original; it never changes the input. It preserves save names, layout, controls and core settings, refuses content-directory saves that need migration, and disables configuration/system/thumbnail synchronization.

Actual save enrollment is a separate gate: first back up real memory cards and states, close RetroArch, test a copy's upload/download/restore, and verify the exact installed core and filenames. Multi-disc memory cards must keep their M3U basename. Save states remain core/version-specific; do not enable automatic state loading. RomM/RetroArch synchronize deletions too, so retain an independent server backup and named checkpoints before enabling the real account. The UI never equates downloaded ROMs or synced progress notes with acknowledged cloud saves.

## Verification

```
cd native/romcloud
qmake tests.pro
make
./rom-cloud-tests
```

Tests use synthetic bytes and an isolated loopback HTTP server. They exercise
connection loss and explicit pause followed by client recreation and Range
resume, ignored Range, wrong checksums, offline reconstruction and removal with
saves preserved. Launch tests cover unlisted targets, malformed/linked markers,
same-size corruption, a changed file or marker during verification, cancellation
before and after hashing, and corruption in a later disc. They do not prove
device permissions, actual ROM boot, server deployment or a cloud-memory-card
restore.
