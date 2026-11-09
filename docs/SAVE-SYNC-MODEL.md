# Branch-aware save-sync model

`tools/save_sync_model.py` is a pure Python transaction model and adapter contract. It never opens a network connection, reads a profile, launches an emulator, stages a file or changes an emulator setting. Runtime boundaries and guarded startup still have only synthetic fixtures in `tests/test_save_sync_model.py`. The optional [immutable transport](AUTOSAVE-AND-TRANSPORT.md) now implements real durable upload/inventory/range download, but explicitly lacks the head guard and runtime import needed for automatic restore. Automatic synchronization remains disabled. This foundation does not establish real cloud-save or device startup readiness.

The model reuses [save passports](SAVE-PASSPORT.md) for archive verification and exact edition/recipe/save-kind/runtime compatibility. F07's `Catalogue.reference(checkpointId)` supplies the exact `{checkpointId, passportSha256, identity}` binding. Checkpoint IDs belong to an individual catalogue, so two devices can import the same revision under different checkpoint IDs. Sync ancestry lives only in this module; it is not a second catalogue or a progress-note conflict model.

## Revision and transport facts

A revision contains an exact identity, full passport SHA-256, save-data SHA-256, archive byte count and sorted parent revision IDs. `revisionId` is the SHA-256 of those canonical metadata fields; it does not use a wall clock or checkpoint ID. The save-data digest covers exact identity and path-sorted passport file records (path, bytes and payload SHA-256), excluding capture dates. Capture dates remain available through the passport/catalogue for display only. Identical save data captured at two dates can have different archive/revision IDs and equal data digests; neither wins automatically.

Every revision and its archive are immutable. Multiple children of the same parent remain separate retained branches. Publishing a child requires its parents to have been acknowledged or observed in the complete remote inventory. There is no remote delete, overwrite, timestamp winner or conflict-merging operation in this model. A future deliberate merge would be another revision whose parent list retains both histories; no merge is invented here.

The status facts are independent, rather than one ambiguous “synced” flag:

| Fact | Evidence represented |
| --- | --- |
| `local` | Exact F07 catalogue reference attached to the archive |
| `queued` | Persisted immutable upload operation awaiting acknowledgement |
| `uploaded` | Matching operation/revision/archive-digest acknowledgement received |
| `downloaded` | Declared transport byte count received; checksum may still fail |
| `verified` | Full archive SHA-256, internal passport checksums and exact identity passed |
| staged receipt | Catalogue adapter reports a new staging directory; no live restore implied |
| runtime apply receipt | Supported runtime adapter reports import and save-data readback in the same contentless session |

`statuses(revisionId)` returns only the five transport/catalogue facts. Staging and application belong to an ephemeral startup transaction and never become a persistent `restored` label. A downloaded archive must be verified and imported into the local F07 catalogue before it can be selected for runtime application.

`queue_upload` uses `put:<revisionId>` as the durable idempotency key. Persist `snapshot()` before dispatching `upload_intent()`. A lost reply leaves `queued` true, even if the service already accepted the immutable archive. Retry the same bytes with the same key; the service must return the original acknowledgement without publishing a second revision. Cancellation prevents further local dispatch and ignores a late acknowledgement, but cannot retract an already accepted remote operation. Refreshing inventory reveals any such retained remote branch; cancellation never deletes it.

Downloads have independent unique transfer IDs and exact append offsets. Persist a partial buffer before requesting the next range. Restart retains the prefix but invalidates the old callback ID, so a new transfer ID resumes at its exact length. Cancel clears only unverified transport bytes and fences old callbacks. Complete corrupt bytes stay `downloaded` with a verification failure and cannot become verified, enter a catalogue or satisfy startup; explicit cancel/retry replaces that failed transport buffer without touching the current verified branch.

## Pre-content startup barrier

A fresh `begin_startup(sessionId, currentRevisionId)` starts blocked. The current revision must already have a verified catalogue reference; this is a declared starting point, not discovery of installed emulator files. Real adapters must establish that identity and the actual current save through their supported runtime boundary.

1. Fetch a complete remote ancestry/inventory for this exact identity. `observe_inventory(..., session_id=...)` accepts only the current session. Its token is the canonical SHA-256 of sorted revision IDs and heads. Generic/background inventory is last-known data and cannot mark a later startup fresh.
2. If remote heads are ancestors of the current local branch, it can remain selected. A single remote descendant becomes the pending selection and blocks until available and applied. Divergent/multiple heads require an explicit choice. No capture date is consulted.
3. Obtain a positive same-session contentless runtime boundary and current save-data readback through `observe_idle`. Paused, active, wrong-runtime, wrong-data and stale-session receipts refuse. A foreground app name or absent reply supplies no receipt.
4. For a selected revision other than the live current branch, first download/verify/import it into the catalogue, then call the catalogue's new-directory staging API and supply its exact staging receipt. A separate supported runtime import and save-data readback supplies `record_applied`. Staging alone leaves the barrier blocked.
5. Before online startup, the service adapter must acquire a fresh complete-head guard for the same identity, inventory token and session. It must serialize remote head publication from that check through the actual content-load acknowledgement. `issue_load_intent(guard)` validates its declared scope and returns one load intent. It launches nothing and cannot prove that a supplied receipt is authentic or a guard is still live.
6. The runtime adapter must consume that intent exactly once while the contentless boundary and remote guard remain valid, then release the guard only after content load is acknowledged. Changed heads require another inventory and re-evaluation. Runtime activity, process changes, ambiguity, lease loss or timeouts must invalidate the transaction and refuse the old intent.

An explicit `choose_branch(retainedId, prefer_local=True)` is the alternative when the player knowingly chooses retained local progress, including while offline. The intent carries `explicitLocalChoice: true` and makes no remote-freshness claim. Choosing another retained local revision still requires staging, runtime import and readback; choosing the already current local revision does not pretend to restore it. All other local/remote branches remain retained. This choice is not permission to upload over another branch.

Restart discards all runtime, staging, application and guard receipts. Persisted last-known inventory cannot satisfy a new startup, and old session/callback IDs cannot resume. The adapter must use fresh session IDs and runtime observations. The model is bounded to 1,024 revisions, upload operations, recorded startup IDs and download IDs, with at most 32 parents per revision and the passport archive size bound. It fails closed at capacity; it has no implicit history/session eviction. This is an in-memory reference foundation, not a mobile storage implementation. Production adapters need a reviewed immutable blob store, retention/export policy and session-lifetime strategy before adoption.

## Required adapter guarantees

These are requirements for a future adapter, not implemented service capabilities:

- **Catalogue:** use active, fully verified F07 references; import new archives without replacing existing archives or live saves. Retain an independent backup and the old branch before any real runtime import.
- **Durability:** write private checkpoints atomically and durably before external dispatch. `snapshot()` contains full save bytes encoded as base64, so it is private save material, never diagnostic/public output. The model revalidates bytes and invariants on `restart`; it does not authenticate a checkpoint author or encrypt storage. Parse external JSON with `save_passport.parse_json` to reject duplicate keys before calling `restart`.
- **Service:** authenticate the identity scope, verify archive bytes, keep immutable revisions and ancestor closure, bind idempotency keys to exact bytes, supply complete inventories and provide a real atomic head guard. A final `HEAD`/timestamp check followed by an unguarded launch is insufficient because a publisher can race it. Current RetroArch/WebDAV configuration is not an implementation of this guard contract.
- **Runtime:** authenticate an exact installed runtime/core/setup and session, prove a contentless boundary, export/hash the current native save, perform supported import only while safe, read back the complete imported payload and preserve the boundary through content load. Plain dictionaries, operator assertions, staging success and fake-service tests cannot provide device evidence.
- **Cancellation/restart:** fence old callbacks, retain acknowledged and divergent archives, reacquire service/runtime authority and never convert an uncertain outcome into success. A cancelled/lost-response upload may still exist remotely.

The model supplies fixed diagnostics and never needs credentials, account names, local paths, commands or device secrets. Save identity descriptors and archive bytes themselves can still be sensitive.

## Verification and remaining gate

```sh
python3 -m unittest tests.test_save_sync_model -v
```

The suite uses two offline branches with opposing clock skew, lost replies and idempotent retry, cancelled uploads/downloads and late callbacks, interrupted range fetch/restart, archive/checksum failures, missing ancestry, wrong runtime/save kind, malformed checkpoints, exact F07 import/export/stage references, and pre-content startup ordering. Its fake atomic head guard refuses concurrent publication before content load and rejects an expired guard. It deliberately has no account/service/device implementation.

Before any automatic save setting changes, the remaining gate is independent backups plus an authorized copied-memory-card upload/download/actual import and recovery test on the exact installed runtime/core, including offline divergent branches, lost responses, restart and a verified pre-content ordering/guard mechanism. If the selected real service/runtime cannot supply these guarantees, keep automation disabled and offer only deliberate retained-branch export/staging/local choice.
