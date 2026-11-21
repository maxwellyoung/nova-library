# ROM cloud client

An optional Qt 5.15/6 native bridge for the existing Nova interface. A bridge advertising `catalogueVersion: 1` supplies cloud copies to the normal Library, Consoles and Details. Their primary action installs, resumes or verifies and plays that copy. `CloudLibrary.qml` presents a focused download view and returns to the originating selection; Settings → Cloud library retains the complete connection/maintenance view. Older bridges keep that separate shelf. Theme-only operation, the save picker and the existing progress bridge do not require it.

## Catalogue and launch continuity

The native bridge mints each edition ID from a canonical server origin, game ID and content descriptor (platform, entry filename and sorted payload names, byte counts and checksums). Titles and server file IDs are not identity. Installed copies retain their ownership marker's content identity when the remote catalogue changes. They remain distinct from matching titles in Pegasus; there is no fuzzy merge. The stable origin/game key preserves selection across a later scan without joining the old and new content editions.

Cloud entries use the normal search, filters, console browsing, Details and local favourites. After Android accepts a verified launch, versioned local history makes that edition eligible for Home's recent shelf. This records an opening, not playtime or progress. Unsupported/corrupt history is retained rather than silently replaced. Cloud favourites are local; service-backed status/collection edits stay unavailable until these content identities are registered by the progress service. The native edition-scoped notebook remains separate.

Immediately before launch, after hashing, `launchPrepared` supplies the exact installed identity for the existing ROM recorder. Android uses `MainActivity.launchAmCommand` with a literal allowlisted argv array, preserving the existing launch/recorder boundary. No server command is executed. Only Android's accepted result emits `launchAccepted`; a desktop signal is not a successful device launch. Actual foreground intervals, emulator return and central media ingestion require their own runtime checks.

The theme stages Cloud recorder metadata only when the optional private bridge
provides both `beginRomLaunch(edition, title, platform)` and
`cancelRomLaunch(token)`. The token owns one in-memory pre-dispatch stage.
Cancellation, refusal, bridge replacement or theme teardown clears only that
stage, preserving newer stages, pending observations and the existing journal.
The platform consumes the stage before accepting a request and omits its token
from pending/history records. Older bridges do not use the unscoped legacy
staging call for Cloud launches; accepted-opening recents remain separate.
Stage tokens are neither caller authentication nor gameplay evidence. Local ROM
staging and existing recording permissions are unchanged.

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

### Bounded connection recovery

During an explicitly started install, the client may continue one interrupted
payload automatically. This is one application-level retry budget for the whole
game, not one per file, and it never starts another game by itself. The existing
explicit queue may continue to its next job only after the current game passes.

The only eligible signal is Qt's RemoteHostClosedError after an accepted 200 or
exact 206 response has appended some, but not all, of the expected bytes. A trusted
foreground-download adapter must still say Library is active. The ownership
plan, file set, storage availability and remaining capacity are checked before
announcing the retry and again on its queued continuation. The current prefix is
kept; the existing Range/Content-Range and final checksum checks still apply.

Cancellation, loss of foreground, changed/linked/unrecognised retained files,
extra files (including saves), no progress, HTTP/auth/TLS errors, wrong response
length, ignored/malformed Range and checksum failures receive no automatic
repair. An unknown foreground adapter also refuses it. A second interruption
stops with partial data retained; a later explicit resume starts a new install
attempt. Restart does not resume a queue without that explicit action.

The existing status text reports the bounded attempt. It never claims that an
interrupted prefix is verified, that a save was made, or that a cloud save was
restored. This feature does not delete corrupt bytes, alter routes/settings,
reset a prefix, change drivers, touch saves or implement privileged repairs.
Those require their own preview, checkpoint, rollback and runtime proof.

### Review a download before adding it

`reviewVersion == 1` advertises `inspectDownload(id)` and `downloadReview(id)`.
Inspection fetches a missing RomM detail record and updates the private metadata
cache only. It never calls install, queues a job, creates a ROM directory or
fetches game payloads. `inspectingDownload` distinguishes this request from a
transfer. Leaving the panel does not cancel a metadata request; its eventual
completion cannot reopen the review or start a download. X can retry a failed
inspection, while the ordinary Cloud Pause action can cancel the request.

The review returns only the checked file names, sizes, roles, entry name, opaque
content identity and existing storage/recovery facts. Endpoints, credentials and
storage paths stay native. The UI freezes the reviewed descriptor and asks for
Review again after a changed identity/title. Confirmation rechecks that identity,
current storage and retained-file blockers before entering the existing pinned
queue/install boundary. Space is measured again by installation, never reserved.
The queue remains a separately explicit batch-start surface; existing jobs do
not gain a new consent requirement on upgrade.

A playlist is shown as a dependency, not an optional tiny download. All files
still participate in activation and offline checksum checks. Smaller selections
are deliberately unavailable: generic RomM file membership does not establish
safe disc-switch, boot or save-name semantics for a partial set. No new server
schema, service deployment or runtime support is implied by this UI.

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

## Persistent Downloads queue

With `queueVersion === 1`, the Cloud screen offers **Downloads** on the mapped
next-page button (normally R1) and by touch. Starting a game download persists
its queue entry first. While a download is running, other Cloud games can be
added without interrupting it. Downloads offers explicit start/retry, pause,
offline Play and Remove entry. Back returns to the exact Cloud selection;
Remove entry changes queue metadata only and never deletes ROMs or saves.
Older bridges retain direct downloads and hide the queue route.

Queue records live in app-private `download-queue.json`. They contain at most
100 jobs, a hashed origin/storage scope, pinned edition identities, titles and
bounded state messages. They contain no tokens, server URLs or ROM paths.
Writes are private, locked and atomic; a malformed, foreign, linked, oversized
or externally changed queue is preserved rather than replaced. Queue failure
does not disable the older direct-download API. Known content identities cannot
be retargeted by refreshed metadata or a details response. A summary without
file hashes is pinned once its checked descriptor arrives, before payload writes.

Execution consent is deliberately not persisted. Reopening Library leaves the
queue paused. The Android adapter permits a batch only while Qt reports Library
active; leaving pauses it, and returning requires an explicit start. Other
platforms must supply `RomCloudConfig.downloadWindow` or the queue cannot run.
This foreground window does not prove emulator exit or idle and never permits
cleanup. Downloads are sequential and each activation uses the existing
space/checksum/playlist checks. A blocked job stops the batch for review.

This is an on-device queue, without background execution, notifications or new
permissions. It is not the planned household queue or automatic cloud-save sync.
Android lifecycle, actual controller input, interruption/return and throughput
remain physical-device gates; the host HTTP and QML tests do not establish them.

The selected ROM root must already be a present, safe directory. Install and
queued retry preserve the same missing-storage refusal as preflight: they do not
create a missing selected root on its containing filesystem. Managed download
and partial directories can still be created inside that present root. Restore
or deliberately provision/review the selected storage before retrying. This
path check does not authenticate a physical card, identify a replacement card,
or establish hot-swap behavior on Android.

The Downloaded state and queue completion text describe checked download files.
Runtime opening, real offline play and save loading have separate acceptance gates.

### Opening a checked download

Play rechecks the foreground window before hashing, when checksum callbacks
return, and after each launch-preparation/request signal. Those direct Qt signal
handlers can cancel synchronously. Cancellation or foreground loss stops before
the platform dispatcher; returning to Library does not retry an old request.
A real dispatcher without a foreground observer is refused. The Android factory
supplies both the existing Qt application-state observer and the literal
file/core JNI dispatcher. Desktop observer-only fixtures still make no Android
dispatch or accepted-launch claim.

The platform call is an injected boundary, like the existing foreground/idle
observers, so native tests can count its calls without launching a game.
`launchAccepted` means the platform accepted this request; the UI explicitly
leaves game boot and save loading unconfirmed. A foreground window does not
establish emulator idle or authorize removal. No save/sync/permission policy is
changed by these launch checks.

Managed removal refreshes Downloads availability after detaching a reviewed folder,
including a refusal/partial cleanup that leaves a detached recovery folder. A
removed payload cannot remain Downloaded/Play merely because its queue entry was
already visible. The queue file and selected edition stay; reinstallation requires
a fresh deliberate Retry and the usual file/capacity/checksum guards. This does not
supply trusted Android idle, start a queue automatically or widen removal targets.

A `.removed` or `.partial.removed` location blocks a new download for an
uninstalled edition. Presence alone does not establish ownership or the cause of
an interrupted removal. The existing plan/game/queue surfaces report the fixed
refusal without reading those locations' contents or deleting, moving or restoring
them. Directories, files, links (including dangling links) and FIFOs are kept for
review. A valid current installed copy remains available and is never replaced by
this guard. Actual recovery/idle/device review is still required.
