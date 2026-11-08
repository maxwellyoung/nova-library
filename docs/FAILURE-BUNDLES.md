# Private structured failure bundles

`tools/failure_bundle.py` is a host-side building block for N044/N045/N050. It accepts one explicitly prepared structured observation, previews the complete portable report, and writes a new private file only after approval of those exact bytes. It never reads live logs, queries a device, opens attachments, sends data, changes a catalogue, starts a game or performs a repair.

The current theme has no failure-screen integration for this tool. A CLI preview is not evidence of that future UI, a real game failure, automatic diagnosis or a successful recovery.

## Input and trust

Use the existing stable edition and versioned recipe IDs from the [compatibility contract](COMPATIBILITY.md). The declared recipe ID must change when the runtime or configuration changes. The tool compares IDs; it cannot inspect or authenticate the active configuration. Even matching IDs produce `currentSetupVerified: false`.

Facts and hypotheses use separate reviewed vocabularies. A fact is a **supplied observation**, retaining its declared method (`physical`, `owner`, `observed`, `injected`, `log` or `test`); the tool does not certify that declaration. A hypothesis must reference retained fact codes and is always marked `unconfirmed`. An `unknown-cause` hypothesis remains unknown. The fixed recovery hints recommend preserving data, checking an existing result or using an existing guarded flow. They contain no commands and are never executed.

This fictional descriptor records a failed checksum, not a ROM or gameplay result:

```json
{
  "schemaVersion": 1,
  "editionId": "demo:edition-a",
  "observedRecipeId": "fixture.v1",
  "activeRecipeId": "fixture.v1",
  "observedAt": "2026-11-04T12:00:00Z",
  "stage": "download",
  "facts": [{"code": "checksum-mismatch", "method": "test"}],
  "hypotheses": [{"code": "interrupted-transfer", "basedOn": ["checksum-mismatch"]}]
}
```

`activeRecipeId` may be `null` when unknown. Different observed/active IDs produce `historical-recipe`; a missing active ID produces `unlinked`. Both retain the observation but explicitly withhold diagnosis of the current setup. Matching IDs mean only `same-declared-recipe`, not verified live identity.

The stage must be explicit: `unknown`, `catalogue`, `preflight`, `download`, `activation`, or an existing compatibility stage: `boot`, `menus`, `gameplay`, `physical-controls`, `audio`, `save-restore`, `exit-return`, `sustained`, `native-4-3`, `stretch-only`. Stage-specific codes are rejected in an unrelated stage; a download checksum failure cannot become gameplay evidence. No result from this tool fills the compatibility ladder or grants launch/cleanup authority.

Available fact codes:

| Code | Stage |
| --- | --- |
| `route-unavailable` | catalogue, boot |
| `file-missing` | preflight, boot |
| `storage-insufficient` | preflight, download |
| `network-unavailable` | catalogue, download |
| `transfer-interrupted` | download |
| `checksum-mismatch` | download, activation |
| `activation-refused` | activation |
| `runtime-idle-unknown`, `runtime-active` | preflight, exit-return |
| `save-result-unknown`, `save-identity-mismatch` | save-restore |
| `configuration-mismatch`, `permission-unavailable`, `operation-failed`, `result-unknown` | any declared stage |

Hypothesis codes: `setup-changed`, `temporary-network-failure`, `interrupted-transfer`, `runtime-unavailable`, `unknown-cause`. They are suggestions from the caller, not an automatically inferred root cause. Irrelevant hypotheses should be removed during preview.

## Exclusion and bounds

There are no free-text descriptions, configuration strings, commands, filenames, account labels or binary attachments in the output. Edition/recipe IDs are SHA-256 fingerprints, never copied verbatim. Hashes allow an explicitly supplied local ID to be compared privately; they are not signatures, authenticated identities or a promise of anonymisation. A guessable ID may still be guessed by hashing it. Observation dates, event codes and equality of IDs can also be private; review the whole preview before any sharing.

Known sensitive top-level fields are **discarded entirely**, without reading their contents: `logs`, `rawLog`, `token`, `tokens`, `account`, `accountId`, `path`, `paths`, `rom`, `save`, `payload`, `config`, `endpoint`, `url`, `device`, `runtime`, `attachments`. The report records only how many such fields were discarded. Prefer omitting them at the source. Unknown fields, unknown nested fact/hypothesis fields, duplicate JSON keys, markup/control characters in IDs, and identities matching the existing privacy scanner's path/account/token patterns are refused. This is structured minimisation rather than a promise to sanitize arbitrary logs. No raw log parser is provided.

Input is a regular canonical file no larger than 16 KiB. Symlinked files/ancestors, FIFOs, changing files, invalid JSON and missing inputs are refused. Facts are limited to 16, hypotheses to 8, and output to 8 KiB. Observation timestamps must be real UTC dates at or before the current clock. The portable output contains no automatically captured machine/account identifiers or current host paths.

## Preview and explicit export

Use private canonical host storage. Preview writes no report file:

```sh
python3 tools/failure_bundle.py preview /canonical/private/descriptor.json
```

Inspect every field in `bundle`, the byte count and `sha256`. Cancel by doing nothing; no export or send occurs. To export the **same** descriptor after review, supply the exact preview digest:

```sh
python3 tools/failure_bundle.py export /canonical/private/descriptor.json \
  /canonical/private/new-failure.json --approve-sha256 "$REVIEWED_PREVIEW_SHA256"
```

The destination must be new, with a canonical existing parent. Existing files and links are never replaced. A changed descriptor that affects exported bytes invalidates approval; discarded private fields do not change the report because their contents are excluded. Output is owner-only (`0600`) and flushed before success. A failed write removes only the new file created by that export. Errors use fixed diagnostics without echoing descriptor contents or filesystem exception paths. The summary reports `sent: false`; there is no send mode or automatic recipient.

An export is still a private local artifact. Explicit publication/sharing approval and full text/provenance review remain separate. No approval is obtained merely by creating or inspecting a report.

## API for later integration

- `build(raw, now=None)` validates supplied structured data and returns the allowlisted report.
- `preview(raw, now=None)` returns `{bytes, sha256, bundle}` without filesystem/network/device actions.
- `read_descriptor(path)` provides bounded regular-file JSON input and duplicate-key rejection.
- `export(raw, output, approve_sha256=..., now=None)` writes the exact approved report into a new private file and returns `{bytes, sha256, exported: true, sent: false}`.

The tool reuses `privacy_scan.findings` and the save passport's canonical-directory/duplicate-JSON helpers. It does not modify those tools or add a second generic privacy/log parser. Existing compatibility stage/method vocabularies are retained for integration, with install-stage additions kept diagnostic-only.

The caller must supply observations from a known edition/runtime path, avoid fabricating physical methods, and preserve its real active recipe identity. A future native/QML adapter must show this same full preview and explicit export/cancel boundary; it must not send arbitrary free text into this format or treat a report as permission to repair.

## Verification and remaining device gate

```sh
python3 -m unittest discover -s tests -p test_failure_bundle.py -v
```

Disposable tests cover exact-byte/private export, no-approval/cancel/stale-preview refusal, sensitive field exclusion, malicious/nested inputs, duplicate keys, date/stage/method and collection/byte bounds, missing/error/symlink/FIFO inputs, existing-output preservation, write-failure cleanup, historical recipes and redacted CLI failures. Network/process mocks demonstrate that the pure preview has no such side effects; no device or service is contacted.

Still required for N044/N045: integrate the failure-screen/native adapter, exercise one safely induced actual failure on the declared Nova edition/recipe, inspect the local bundle, cancel and explicitly export, then recover without modifying live saves or enabling permissions implicitly. N050 additionally requires a reviewed public candidate and exact publication approval. Local Python tests do not establish those gates.
