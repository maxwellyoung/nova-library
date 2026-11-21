# Private structured failure bundles

`tools/failure_bundle.py` is a host-side building block for N044/N045/N050. It accepts one explicitly prepared structured observation, previews the complete portable report, and writes a new private file only after approval of those exact bytes. It never reads live logs, queries a device, opens attachments, sends data, changes a catalogue, starts a game or performs a repair.

The matching source now has an optional **Save copies failure → Review failure → private preview → Export privately** flow. It requires a build prepared with `--save-copies --failure-reports`; older builds hide this action. This source is not installed or deployment-approved. Physical Nova recovery remains the first device gate.

The native adapter observes existing copy-history reads and requested archive checks. It does not collect raw OS logs, arbitrary configuration, screenshots, ROMs or save payloads. Its report retains the requested edition and, for a check, checkpoint/index identity as fingerprints. The reader contract uses `nova.copy.open.v1` or `nova.copy.check.v1:<checkpoint>:<index>` as its operational recipe; this is not an emulator recipe or proof of game/runtime identity. Source/build/runtime context stays null and unlinked. The report states `authenticated: false` and `currentSetupVerified: false`. A typed owner-only guard result describes a reader check, not an OS permission diagnosis or a proposed chmod.

Preview and Cancel perform no report writes. Back is the default action; export requires the current preview ticket and exact SHA-256. A newer result, success or cancellation invalidates an older ticket. Export creates a new `0600` file in the app's private `failure-reports-v1` directory (`0700`), with no-follow directory handles, exclusive creation, flush, read-back and identity checks. It never replaces an existing file, changes copied history, repairs anything or sends data. The UI retains the generated filename. The optional Android source now offers a separate **Save a copy…** action after private export. It opens the system create-document chooser for this exact report; provider storage and sync can be outside private app storage. Actual Android chooser/provider/lifecycle acceptance is still unverified, and older builds expose no such action. No automatic sharing or send is implemented.

The optional preview presentation is loaded lazily. Missing/invalid presentation files return to the invoking Save copies or Cloud pane without failing the main theme. Real controller, Android filesystem/domain, accessibility and unaided private-export acceptance remain unverified. Desktop native tests and safely induced disposable failures prove only those named host paths.

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

The stage must be explicit: `unknown`, `catalogue`, `preflight`, `download`, `activation`, or an existing compatibility stage: `boot`, `menus`, `gameplay`, `physical-controls`, `audio`, `save-restore`, `exit-return`, `sustained`, `native-4-3`, `stretch-only`, `offline-launch`. Stage-specific codes are rejected in an unrelated stage; a download checksum failure cannot become gameplay or offline-launch evidence. No result from this tool fills the compatibility ladder or grants launch/cleanup authority.

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

## Source, build and collection provenance

Schema 1 remains supported with the same report shape and recipe-only comparison.
For a capture that needs explicit source/build/runtime binding, set
`schemaVersion` to `2` and add this `provenance` object to the descriptor above:

```json
{
  "observed": {
    "editionId": "demo:edition-a",
    "recipeId": "fixture.v1",
    "sourceSha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "buildSha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "runtimeId": "demo.runtime",
    "runtimeVersion": "1.2.3"
  },
  "active": {
    "editionId": "demo:edition-a",
    "recipeId": "fixture.v1",
    "sourceSha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "buildSha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "runtimeId": "demo.runtime",
    "runtimeVersion": "1.2.3"
  },
  "collection": {
    "status": "supplied",
    "method": "operator",
    "collectedAt": "2026-11-04T12:01:00Z"
  }
}
```

The digest values above are fictional fixtures. `sourceSha256` identifies the
exact source manifest bytes (including relevant dirty changes); `buildSha256`
identifies the actual artifact bytes. Neither is inferred from a branch or
recipe label. The caller supplies both; this tool does not hash a source tree,
inspect an installed build, authenticate a collector or inspect runtime state.
Use `null` for unknown source/build/runtime fields rather than inventing a
value. Runtime placeholder labels such as `unknown`, `latest` or `current`
are refused rather than counted as exact provenance. Schema2 edition IDs allow
up to 512 characters to retain content-scoped Cloud identities; schema1 keeps its
128-character limit. Recipe/runtime IDs stay bounded to 128 characters. Runtime identity uses the same bounded syntax as recipe IDs. Runtime
versions start with a letter or digit, contain only letters, digits, dots,
pluses, underscores or hyphens, and are at most 80 characters. Arbitrary
runtime/configuration strings remain excluded. The report fingerprints edition,
recipe, runtime and version IDs.
Only the two declared SHA-256 digests remain verbatim. All fields in each
context object are required, even when their value is `null` where allowed.

The observed context must match the descriptor's edition and observed recipe.
The active context must match its active recipe; when that recipe is `null`,
the active context must also be `null`. An active edition may differ: that is
an explicit historical observation, never evidence for the new edition.
`contextScope` is `same-declared-context` only when both contexts are complete
and equal; a known difference produces `historical-context`, incomplete fields
produce `unknown-context`, and no active context produces `unlinked`. A known
difference remains historical even when other fields are unknown. This
comparison catches a changed source, build, runtime or edition even if a caller
reuses the same recipe label. Matching contexts still have `authenticated:
false` and `currentSetupVerified: false`.

`collection.status` is one of `supplied`, `collected`, `unsupported`, `refused`
or `unavailable`. `supplied` means a manually prepared observation without a
collection claim. The other values describe the caller's declared collection
outcome, including an unsuccessful attempt; they are not compatibility results.
`collection.method` is `operator`, `adapter` or `synthetic`. Synthetic fixtures
must retain `synthetic`; they never establish real device collection.
`collectedAt` records when that outcome was recorded, including refusal, and
must be a real UTC date at or after the observation and no later than now.
Unknown fields and unsupported statuses/methods are refused. The tool never
changes a fact's original method or infers a cause from collection status.
Non-collected outcomes carry an explicit warning that retained facts are only
supplied observations. Even `collected` is a supplied, unauthenticated claim.

The full redacted provenance is included in preview and exact-byte approval.
Changing context, collection status, method or date requires reviewing a new
digest. There is still no raw-log or attachment collector. The optional native reader adapter
retains only the structured boundary described above; physical device integration
and acceptance are not inferred from source or desktop tests. A refusal receipt documents the declared
boundary; it is not a substitute for collecting bounded supported evidence.

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

The caller must supply observations from a known edition/runtime path, avoid fabricating physical methods, and preserve its real active recipe identity. The optional native/QML adapter shows this full preview and explicit private export/cancel boundary; it must not send arbitrary free text into this format or treat a report as permission to repair.

## Verification and remaining device gate

```sh
python3 -m unittest discover -s tests -p test_failure_bundle.py -v
```

Disposable tests cover exact-byte/private export, no-approval/cancel/stale-preview refusal, sensitive field exclusion, malicious/nested inputs, duplicate keys, date/stage/method and collection/byte bounds, missing/error/symlink/FIFO inputs, existing-output preservation, write-failure cleanup, historical recipes and redacted CLI failures. Network/process mocks demonstrate that the pure preview has no such side effects; no device or service is contacted.

Schema-2 tests use a synthetic producer and disposable local files to cover
source/build/runtime/edition drift under an unchanged recipe label, unknown and
unlinked contexts, collection/refusal provenance, malformed/private fields,
collection dates, unauthenticated matching contexts and invalidated approval
after provenance changes. Log-method offline failures remain failures with no
inferred gameplay pass or cause. These checks exercise the host contract only.

Still required for N044/N045: exercise the integrated failure-screen/native adapter with one safely induced actual failure on the declared Nova edition/recipe, inspect the local bundle, cancel and explicitly export, then recover without modifying live saves or enabling permissions implicitly. N050 additionally requires a reviewed public candidate and exact publication approval. Local Python tests do not establish those gates.

## Native producer extension

Schema2 optionally accepts `origin: "native-save-copies"`; omitted origin and explicit `"operator"` retain the previous bytes. This is a declared producer, not an authentication claim. The native report uses `source: "native-save-copies-observation"`. Synthetic Qt test mode retains `collection.method: "synthetic"` and fact method `"test"`; ordinary native observations use `"adapter"`/`"observed"`.

Additional preflight-only fact codes are `copy-history-unavailable`, `copy-history-changed`, `copy-archive-unverified`, `copy-directory-owner-check-failed` and `copy-index-owner-check-failed`. Their statements and safe hints are fixed vocabulary. Other storage refusals keep their generic observation rather than inventing an explanation. A failed archive check is not a live restore failure or a gameplay result.

The optional native adapter also observes bounded Cloud Play refusals. The selected game and exact native attempt must still match before **Review failure** appears in Cloud or Downloads. Mapped previous-page/L1 or the pointer action opens the complete minimized preview; Back returns to the same selected game and child panel. New attempts and Save copies observations invalidate older preview tickets. A runtime request returning false is recorded as a refusal with unknown cause, not as a diagnosed missing core. Accepted dispatch and cancellation create no failure report. Operational Cloud Play recipe fingerprints include the attempt token and declared exact edition; source/build/runtime and active context remain unknown. Catalogue, transfer, install and cleanup notices remain outside this native collector. None of this establishes Android/client or unaided physical acceptance.

The document-copy source accepts only the current private-export token and exact digest. It neither accepts arbitrary report text/paths/URIs from QML nor enumerates previous reports. Only a fresh Android create-document result can supply the opaque target. New observations invalidate a pending selection and request in-flight cancellation; a failed/stale copy may leave an empty or incomplete chosen document, which Nova does not delete. The private source remains intact. Provider open/write/read-back/close runs on a worker. Empty, seekable regular targets are required, at most8192 bytes are written, and verified success requires exact read-back and a clean descriptor close. This verifies the supplied document handle, not a provider's remote durability or sync.

The compiled native ThemeError screen also offers **Review failure**, using Details or the pointer action. Its preview is compiled with the launcher rather than loaded from the failed external theme. The native producer reads the bound selected-theme Loader's Error state and emits the fixed `selected-theme-load-failed` or `selected-theme-construction-failed` fact with `origin: "native-theme-load"` / `source: "native-theme-load-observation"`. A new operational attempt identifies this observation; it is not a theme content/build/runtime fingerprint. The selected path and raw error/log text are excluded, cause remains unknown, and all source/build/runtime context stays unlinked. Successful loading or a changed selection invalidates the old report approval. Back is the default, and reviewing/exporting does not choose the built-in theme, change settings or repair anything. The separate guarded recovery action remains deliberate. Current physical incident diagnosis still requires current identity and a real failure log; this minimized source integration does not supply them.

### Bounded selected-theme diagnostic context

Schema2 native-theme observations optionally include `localEvidence`. The compiled
frontend starts a new collection window per selected-theme load and observes that
engine's warnings. It retains only matching selected-file events and never turns a
warning alone into a failure report. Child/helper/fallback or foreign URLs do not
enter this collection. A new load, selection/rebind or successful load drops old
staging; the native selected-Loader Error gate still applies.

`localEvidence.configuration` has exactly `framework: "Qt"`, the numeric framework
version, `selectionKind` (`local-file`, `bundled`, `other`), `loaderStatus: "error"`
and `failureStage` (`theme-load`, `interface-creation`). It contains no settings dump,
filename, endpoint, account or runtime identity. `errorLog` has `status` (`collected`
or `unavailable`), `maxEntries: 8`, a truncation flag and at most8 deduplicated entries.
Each entry contains only a fixed category and bounded integer line/column positions
(0 means unavailable). Categories are `required-property-uninitialized`,
`qml-syntax-error`, `qml-type-unavailable`, `javascript-type-error`,
`javascript-reference-error` and `qml-error-unclassified`. The original error text,
including property/type names, paths and credentials, is discarded before retention.
No matching events means unavailable rather than a fabricated log.

`lastCloudPreflight` is either `{ "status": "unavailable" }` or an
`observed-refusal` with a reviewed Cloud refusal code, edition SHA-256 and observation
time. It covers only that supported preflight observer; a newer opening attempt
invalidates it. It does not establish the latest global launch, a successful adapter
request, game boot/exit or a save result. Complete runtime configuration and broader
launch/log coverage remain open. These scoped facts do not establish a cause.

The Python descriptor accepts this optional evidence only with one matching native
theme fact in preflight. Extra/private text fields, unsupported categories,
noninteger/out-of-bound positions, more than8 entries, duplicates, incompatible
stages and future previous-refusal timestamps are refused. All evidence is included
in the existing full preview and its byte/digest approval;8KiB remains the output
limit. A supplied descriptor remains unauthenticated. Native engine collection is a
bounded category collector, not a parser or redactor for arbitrary raw log files.
Actual physical error/current configuration, Android/export retrieval and another
owner's unaided acceptance remain required.

The source uses a separate Qt result receiver for each chooser, actual JNI refusal handling, and deferred receiver disposal after result dispatch. No package-visibility query, protected manifest/Java/provider change, service, storage permission request or persistable URI grant is added. Android's create-document behavior is documented in the [Storage Access Framework guide](https://developer.android.com/training/data-storage/shared/documents-files); [package-visibility guidance](https://developer.android.com/training/package-visibility/use-cases) supports direct launch with failure handling. These API contracts do not certify this implementation on Nova. The owner must still exercise real chooser cancellation, provider failures, inactive/return/recreation and unaided retrieval before acceptance.

The optional `appDataStorage` field captures the private app-data directory's
filesystem capacity at the native theme-failure boundary. On supported Unix builds,
the existing no-follow directory opener and `fstatvfs` read total and caller-available
bytes from that descriptor. It reports `scope:app-data-volume`, method and time;
this is neither an enrolled SD-card measurement nor a category scan. No path, mount,
serial, filenames or file contents are retained. Missing/linked/unsafe roots,
unsupported platforms and invalid/overflowing counts report only unavailable.
Zero available bytes remain a measured zero. Values must fit exact JSON integers
and available cannot exceed total. The portable descriptor strictly validates the
optional field and its time while retaining compatibility with earlier reports
without it. Capacity is a dated observation, not an established failure cause,
authority to delete data or a device storage/performance acceptance result.

The standalone compiled preview also shows a short launcher-volume capacity
caption. Its rounded binary units say available at capture; exact byte counts and
time remain in the full report. The preview adds no external helper dependency.
