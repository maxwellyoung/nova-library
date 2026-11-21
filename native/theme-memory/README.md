# Checked theme memory

This is an optional Nova modification of Pegasus `model::Memory` at commit
`5d58223e58f84afb31d5d14a67438841b981a6fa`. Original GPL notices are retained;
`upstream/` and `upstream.json` hold exact original inputs and hashes. The rest of
Pegasus theme-memory identity remains the theme folder name.

The original writer mutates in-memory preferences first, truncates the JSON file,
and only logs a failed write. Its void API cannot acknowledge a saved profile.
This replacement stages the complete map and uses `QSaveFile` with direct-write
fallback disabled. It publishes the new map and change signal only after commit.
It also persists an empty object when the last key is removed.

- `checkedRead(key)` returns `{ok,exists,value?}` or an unavailable error. It
  distinguishes an absent key from an unreadable document.
- `checkedSet(key,value)` and `checkedUnset(key)` return an explicit boolean.
- Invalid/non-object/oversized files, links at the settings directory or target,
  changed/deleted on-disk snapshots, a busy cooperative lock, and failed writes
  refuse without replacing prior memory or bytes.
- Legacy `set`, `unset`, `get` and `has` remain available. Legacy writes use the
  same atomic commit, but callers still need the checked API to report failure.
- A 4 MiB document limit bounds reads/writes. Valid JSON objects with duplicate
  keys are interpreted by Qt's JSON parser; this does not add a general JSON
  duplicate-key audit. Profile/schema validation remains with each caller.

`QLockFile` serializes cooperating writers; a byte snapshot detects edits made
before the final commit. This is not a transaction with arbitrary external editors
that ignore that lock, nor proof of survival through power loss or faulty storage.
A changed/unreadable file requires restarting/reloading the theme to review it;
it is not automatically repaired or merged. No folder contents, paths or preference
values are logged by this implementation.

Prepare a new paired source workspace with `--checked-memory`. The applier refuses
any source different from the pinned originals and retains an exact rollback
copy. Preparation/build/device acceptance are separate. No new Android permission
or file export is added.

`tests.pro` compiles the actual replacement against Qt Core/QML/Test in an isolated
host. `testsupport/Paths.h` only supplies the production path declaration for that
host; production still uses Pegasus's own path provider. Tests cover reopen,
clearing the last key, malformed/oversized preservation, external edits/deletion,
links, competing writers, lock refusal, bounded writes, QML values and separate
theme identities. Android filesystems and physical-device acceptance remain open.
