# Save copies in Library

The optional `saveCopies` context adds **Details → Save copies** for an exact edition. It shows exported names, dates, save kind, runtime identity and protected-anchor labels. **Check copy** rehashes that stored archive asynchronously. Back returns to the same game's Details action; leaving the screen or application cancels an active check. A checksum match is not evidence that the game can load the copy.

This source implements a read-only client of an operator-delivered bundle. It does not capture saves, select a cloud winner, enroll a service, edit names, delete copies or write to a live save directory. Actual Android deployment, physical controls, lifecycle and game restoration require separate verification. Plain Pegasus and partial/older bridges hide the action.

## Explicit host export

After a supported idle capture and import into the private [save catalogue](SAVE-TIMELINE.md):

```sh
python3 tools/export_save_copies.py \
  --catalogue /private/existing-save-history \
  --output /private/new-save-copy-bundle
```

The exporter verifies every active passport and its complete archive hash. It excludes trash, retains distinct named checkpoint IDs and deduplicates identical archive bytes. It refuses changed history, corrupt passports, existing destinations and limits exceeded. A concurrent writer's destination is retained. The index is published last, so interruption leaves an unavailable bundle rather than a partial list. Existing history and live saves stay unchanged.

The result contains `catalogue.json` and `archives/<sha256>.nvs`, with owner-only directory/file permissions. It contains actual private saves and metadata: keep it outside repositories and public evidence. Limits are 128 entries, 512 MiB of unique archives, 256 MiB per archive and a 256 KiB index. These logical limits do not promise spare filesystem capacity.

## Native adapter and delivery boundary

Use `tools/prepare_native.py prepare … --save-copies` with the existing paired-source recipe. `tools/apply_save_copies.py` copies only the optional C++ module and wires the engine context and build files; preparation itself neither builds nor installs. The context resolves a fixed `save-copies-v1` directory under `QStandardPaths::AppLocalDataLocation`. It accepts no caller-supplied filesystem paths.

An authorized operator must deliver the complete bundle to that app-private location with correct owner-only permissions. Do not replace an open bundle in place: prepare a separate copy, verify its hashes, close Library and retain the previous bundle for rollback before switching. There is no in-app network/download/import route in this slice. Installation and delivery must preserve the device's existing signer, permissions, recorder, owner settings, catalogue and progress data.

The index is strict canonical compact JSON produced by the exporter (sorted keys, UTF-8, no trailing newline). Schema 1 has `source: verified-passport-export-v1` and entries containing checkpoint ID, archive SHA/size, exact edition/recipe/kind/runtime identity, capture/arrival timestamps, name, pin, file count and payload bytes. Unknown/duplicate keys, linked paths, broad permissions and malformed/oversized data refuse. The native view filters by exact edition; runtime identity remains visible rather than implying portability.

Listing metadata is not a fresh full integrity check. It distinguishes missing/unavailable/changed files from copies not rechecked here. Selecting **Check copy** first binds the request to the exact index displayed on screen, then hashes the bounded archive on a worker, verifies its byte count and rechecks that snapshot. A changed index before or during the check is refused; close and reopen Save copies to review its new contents. Results belong to that selected checkpoint and request; cancelled/old results cannot populate a different screen. The native reader checks archive bytes against this trusted private index; it does not independently parse the passport payload or authenticate an untrusted index. Full passport validation belongs to the host exporter.

The current theme requires `capabilities().reviewSnapshotVersion === 1` and
`reviewSnapshot(editionId, checkpointId, indexSha256)` for Check copy. Older
readers can still show their history, with checking unavailable and a matching-build
explanation. The original two-argument `review` API remains for existing consumers;
it cannot bind a previously displayed snapshot and is not used by this theme.

## Verification

```sh
python3 -m unittest discover -s tests -p 'test_export_save_copies.py'
python3 -m unittest discover -s tests -p 'test_native_prepare.py'
node --test tests/save-copies.test.cjs
```

`native/savecopies/tests.pro` tests the real C++ reader with disposable synthetic bundles, including edition isolation, corruption, cancellation and changed history. Set `NOVA_SAVE_FIXTURE` to an actual Python-exported synthetic bundle (edition `demo:orbit`) for the cross-language case; otherwise that case explicitly skips. `demo/savecopies/host.pro` and `tools/smoke_save_copies.py` exercise the full theme with the native module across missing/partial contexts, success/failure, layout profiles and Back/focus loss. Desktop injected input does not prove physical Nova controls or Android lifecycle.

## Bounded storage-failure evidence

The source candidate reports which existing check stopped: copied-save folder or
index, then missing/type/link/canonical-path/system-stat/owner-only-permission
check. These are failed checks, not inferred root causes or repair instructions.
Unknown diagnostic values retain the generic unavailable explanation. The UI
keeps Check copy disabled and states that no restore was attempted.

`capabilities().storageDiagnosticsVersion === 1` exposes an optional
`storageRootSha256` path binding. Index failures carry the same binding and
allowlisted `storageStage`/`storageCheck` values. The hash identifies the configured
path spelling, not its contents, successful access, an installed-runtime attestation
or caller authority. No raw path is returned or displayed. Existing read-only
capabilities and error codes remain compatible with older consumers.

This adds observations to the existing guards; it does not relax them, follow
links, change permissions, create a missing store or implement restoration.
A same-UID host/probe pass cannot certify another SELinux/application context.

### App mount namespace (diagnosed on Nova, 21 Nov 2026)

On Android 11+ each app runs in its own mount namespace, where `/data/user/0` is
a symlink to `/data/data`. `run-as` and adb probes see the normal namespace, where
it is a real directory, which is why they passed while the installed app reported
`canonical_mismatch`. The wiring now canonicalizes `AppLocalDataLocation` once
before constructing the reader; the reader itself still refuses any alias at or
below its root. Android also creates that files directory `0771` with the app's
own per-app group, so failure export accepts group write only for that group.
Installed as review APK `393489bc`: Diablo's copy lists, and Check copy reports a
matching checksum on Nova. Loading a copy in its game is still unverified.

## Attached checkpoint pictures

An optional version-two export includes the pictures already attached to private
save history:

```sh
python3 tools/export_save_copies.py --catalogue /private/existing-save-history \
  --output /private/new-save-copy-bundle --thumbnails
```

The default export remains version one for existing readers, including the
separately reviewed minimal storage diagnostic. Version two requires this newer
native reader and theme; do not send it to an older installed reader. It retains
the same archive bytes and checkpoint/edition identity, adding a `picture` object
per entry. `missing` and `unavailable` contain only `state`; `available` also has
`sha256` and `bytes`. Pictures are deduplicated under `pictures/<sha256>.png`, in
owner-only files/directories, and count toward the existing total export budget.
The host fully validates bounded RGB/RGBA PNGs; no image is manufactured for an
absent, invalid or corrupt attachment. Index publication remains last.

On a capable bridge, **Save copies → Picture** opens only the selected checkpoint's
attachment. Native `picture(editionId, checkpointId, indexSha256)` rechecks the
listed index snapshot, exact edition/checkpoint, file privacy, size/hash and PNG
decoder dimensions before handing one immutable PNG to an engine-private image
provider. `pictureVersion === 2` returns an opaque `image://nova-save-copies/`
token; no image bytes or filesystem path enters the QML URL or decoder error log.
The context registers its provider when constructed with its QML engine parent,
as the normal native adapter does. Callers cannot supply a path. Only the selected
image is read; browsing the list does not decode every attachment. QML displays
a decode failure explicitly and accepts no file, network, inline-data or SVG URL.
Back, another picture request and foreground loss clear the cached picture/token.
Back returns to the same copy, then the exact edition's Details action.

The image is a **history attachment**, not evidence of the save's actual contents,
capture time, successful restore or current runtime compatibility. Its byte check
is separate from **Check copy**, which verifies the archive. The view still offers
no live save/restore, capture, network enrollment or permission API. Desktop
synthetic checks and a decoder pass do not establish Android or physical-input
acceptance. `tools/smoke_copy_pictures.py` exercises the complete exporter/native/
theme path using disposable synthetic pictures and progress.
