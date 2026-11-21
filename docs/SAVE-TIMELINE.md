# Protected save history adapter

`tools/save_catalogue.py` stores verified [save passports](SAVE-PASSPORT.md) in a private local SQLite catalogue. It provides dated entries, optional original PNG thumbnails, names and protected anchors, explicit rotation/trash/purge previews, undo, exact passport export and recovery staging. It sends no emulator commands, enrolls no service and never writes to a current save folder.

The catalogue remains host-side. The optional [Save copies view](SAVE-COPIES.md) can display an explicitly exported, private bundle in Library and recheck an archive checksum. It does not edit the catalogue, capture a checkpoint or restore live progress. Its Android deployment and physical acceptance remain separate gates. Python 3.11 or later with SQLite BLOB support is required for the host catalogue; Python tests do not prove device paths.

## Existing picker boundary

The separate [RetroArch disk-load guard candidate](../native/retroarch-safe-load/README.md)
requires a successful volatile backup before pinned disk-load/undo paths
deserialize. It is not installed by Library, is not a durable catalogue copy and
does not supply the trusted live export/import boundary described here. Controls
offers conditional undo guidance and full readable notes; Library never executes
a save/load from that guide. The selected slot is not presumed to be the newest.

`nova-library/recent-saves` remains a read-only view of RetroArch manual numbered state slots. It sorts file observations by modification time, supports missing preview/time fallbacks and refuses ambiguous core folders. Numbered slots can be reused by the emulator, so that list is not immutable history. It does not capture native memory cards, protect named anchors or delete files. This catalogue imports a supported **idle/exported passport** instead of treating a filename/slot observation as a stable save identity. No picker permission or loading behavior was changed.

## Integration API

From the repository root:

```python
from tools.save_catalogue import Catalogue

history = Catalogue('/private/new-save-history', create=True)
# After a supported cold export and passport creation, using actual known identities:
reference = history.import_passport('/private/export.nvs',
    name='Before the lift', pinned=True, thumbnail_path='/private/preview.png')
checkpoint_id = reference['checkpointId']
entries = history.list_entries(target=actual_target_identity)
history.review(checkpoint_id, actual_target_identity)  # Full hashes + identity, no restore.
history.stage(checkpoint_id, actual_target_identity, '/private/new-recovery-folder')
history.export_passport(checkpoint_id, '/private/new-copy.nvs')
history.close()

# Reopen without changing the stored policy:
history = Catalogue('/private/new-save-history')
```

The root must be a new canonical directory outside repositories when creating, and owner-only when reopening. SQLite data and its transient journal remain inside that private root. The database stores original passport bytes and optional original thumbnail bytes; it contains private game identity/file metadata and actual saves. It is not a public catalogue or a credential vault.

`import_passport` returns exactly `{checkpointId, passportSha256, identity}`. `checkpointId` is a random catalogue checkpoint ID; it is not a cross-device content revision. `passportSha256` hashes the complete immutable `.nvs` archive and `identity` contains edition, recipe, kind and full runtime identity. `reference(id)` rechecks every archived byte and the manifest before returning the same shape. The separate save-sync model owns revision ancestry; this catalogue does not infer parents or choose a winning offline branch.

Timeline entries include `capturedAt` from the verified passport, `addedAt` from the catalogue clock, `identity.kind`, name/pin, archive/thumbnail byte counts, thumbnail status, trash expiry and compatibility explanation. Arrival sequence determines display/rotation order; dates remain observations and never resolve a conflict. `list_entries` checks metadata/optional thumbnail bytes, and labels full passport integrity as requiring `review`, `reference` or `stage`. It does not read all stored archive bytes merely to draw a list. Every entry explicitly has `runtimeRestoreAvailable: false`.

`thumbnail(id)` returns verified encoded PNG bytes or `None`; the real client still needs a decoder with an honest fallback. Supported source thumbnails are bounded noninterlaced 8-bit RGB/RGBA PNGs, at most 2048×2048 and 2 MiB encoded. CRCs, bounded inflation and scanline structure are checked. Missing, unsupported/malformed and stored-corrupt images are labelled `missing`, `invalid` and `corrupt` respectively; save bytes remain usable. No screenshot is generated, replaced or inferred.

## Names, protected anchors and retention

`rename(id, name, pinned=bool)` edits only an active entry's local label/pin. A pin requires a nonempty explicit name. Pinned anchors consume overall catalogue capacity but never count toward quick slots or become rotation/deletion candidates. Unpinning is explicit and refuses if it would overflow quick slots. Passport export preserves the original archive/hash; local catalogue labels and pins are not silently added to passport schema 1.

For a client that displays or holds a proposed name/pin change, review it first:

```python
edit = history.plan_rename(checkpoint_id, 'Before Mantis', pinned=True)
# Display edit.before, edit.after and the exact checkpoint identity/hash.
history.apply(edit)
```

The metadata preview binds the catalogue ID, generation, checkpoint ID, original passport checksum, exact edition/recipe/save kind/runtime identity, and both the previous and proposed name/pin. Preview and apply each verify the archived bytes and manifest. Applying changes only the local name/pin columns; it neither duplicates the archive nor changes its provenance, thumbnail, dates or retention state. The returned list contains the edited checkpoint ID, matching retention `apply` results. `rename` uses this same operation immediately; callers displaying a preview must keep and apply that preview rather than call `rename` again.

Any intervening catalogue write invalidates a metadata preview, including a second caller changing a label and changing it back. Reused, malformed, foreign or changed previews refuse without altering history. Unpinning rechecks exact-identity quick-slot capacity; trashed checkpoints must be undone first. Successful metadata edits invalidate older retention previews. These plans contain private save metadata and belong only in the private client flow. Their integrity token detects accidental alteration; it is not authentication or authorization.

Default policy: 20 unpinned active checkpoints per **exact edition/recipe/kind/runtime identity**, 128 total entries including trash, 512 MiB total logical archive/thumbnail bytes, 256 MiB per passport, 64 trash entries/256 MiB trash bytes, and two-stage deletion with 30 days of undo. Policies are explicit positive bounded integers supplied as `retention=` on creation, persisted and checked on reopen. They cannot be silently replaced by another caller. SQLite metadata/allocated free pages and temporary rollback journal space are separate from logical payload bytes; purge is not a promise of reclaimed filesystem capacity.

Import refuses when quick slots, total entries or logical bytes are full. It does not rotate or purge implicitly. To review rotation before making one quick slot available:

```python
plan = history.plan_rotation(actual_target_identity, reserve=1)
# Show plan.items IDs/hashes/archive+thumbnail bytes and undoForDays, then explicitly apply.
history.apply(plan)  # Only selected unpinned entries move into retained trash.

delete_plan = history.plan_delete([checkpoint_id])  # Refuses a pinned anchor.
history.apply(delete_plan)
history.undo(checkpoint_id)  # Exact bytes/identity; refuses expiry or full quick slots.
```

Every plan is bound to the catalogue ID, generation, selected checkpoint IDs/hashes/bytes and an integrity token. Edits, imports, deletion or other writes invalidate earlier previews; changed/tampered/foreign plans refuse. The token detects a changed plan and is not a user-authentication credential or a substitute for displaying the selected action. Independent processes use SQLite transaction locking; callers serialize operations on each Python instance.

Trash capacity is measured before any deletion/rotation. Full trash refuses the transaction. Undo expiry is measured from applying the trash operation using the explicit clock, and it never triggers background deletion. Inspect retained entries with `list_entries(include_trash=True)`. Then deliberately review permanent purge:

```python
expired = history.plan_purge()  # Proposes only expired trash; changes nothing.
history.apply(expired)          # permanent=True, undoForDays=0.

# An explicit selected-trash purge can also be reviewed before expiry:
plan = history.plan_purge([a_trashed_id])
history.apply(plan)
```

Only trash can be purged. Both branches remain independently addressable until an explicit trash/purge transaction removes one. Trash may be exported before purging. Undo, stage and purge recheck stored archive integrity; corrupt history is retained for investigation instead of silently destroyed. There is no automatic filesystem sweep, anchor eviction, slot rewrite or timestamp-only winner.

## Atomicity and actual restore boundary

Import streams into an SQLite BLOB, verifies source stability and checks the stored archive/manifest before committing. Full synchronous transactions keep previous history intact on failed capture, metadata edits, trash, undo or purge. Tests terminate a separate process immediately before commit and reopen the real database to verify rollback for capture, metadata edits, deletion and purge. A failed unpin commit retains the protected anchor and its exact archive reference. Disk errors refuse rather than guessing success. Catalogue creation interrupted before initialization completes is not silently adopted as valid history.

Recovery stages through an unnamed private temporary file into a **new directory** using `save_passport.stage_file`. It checks the exact target identity, archive hash/manifest, payload checksums and source stability; existing output directories are never replaced. A mismatch or unknown version/core remains a refusal for native saves as well as states. Full integrity review and byte staging do not prove an installed emulator can restore either format.

The remaining gate is a current, identity-bound supported emulator export/import boundary; copied-save boot and progress recovery; a named anchor surviving real emulator slot rotation; controller/UI/reopen/thumbnail fallback and undo on Nova; plus safe integration with the current launch/return adapter. Automatic cloud sync/restore remains disabled. No source model or successful network acknowledgement may be labelled as a restored checkpoint.

## Verification

```sh
python3 -m unittest discover -s tests -p 'test_save_catalogue.py' -v
python3 -m unittest discover -s tests -p 'test_save_passport.py' -v
```

All fixtures use invented bytes in disposable local directories. They cover pinned-anchor rotation/full slots, reviewed name/pin edits, concurrent stale writes and changed-back metadata, separate kinds/editions, dated/reopened storage, bad/missing thumbnails, fixed identities, retained branches, existing-output refusal, bounded/full trash, expiry, delete/undo/purge, stale/forged plans, source/record corruption, failed writes and actual process interruption. They neither inspect nor mutate current owner saves.
