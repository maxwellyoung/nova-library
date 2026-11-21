# Optional private failure reports

`FailureReports` observes structured `SaveCopies::operationObserved` results, the compiled selected-theme Loader, and, when Cloud is included, fixed `RomCloud::playObserved` results. It does not accept a caller-supplied report, raw log, path or configuration document. It keeps one bounded capture and preview token in RAM, bound to the requested edition/checkpoint/index, selected theme failure or exact Cloud Play attempt. Source scopes cannot reuse each other's previews. Newer results invalidate old approvals, including success and cancelled checks.

`available` and `preview` do not write. `exportPreview` requires the current token and exact digest and creates one new owner-only private file, never a replacement or send. POSIX export uses no-follow anchored directory handles, exclusive creation, fsync/read-back and identity checks. Unsupported platforms retain preview with export unavailable. The trusted framework app-data directory is resolved at native construction before the no-follow writer boundary; caller report paths and report-directory links are not accepted. Existing directories with unsafe modes are refused, never chmodded. The copied-save store remains read-only.

Ancestors are opened for search with `O_PATH` on Linux/Android or `O_SEARCH`
where available. This supports private-data parents that permit traversal but
not listing. Every component still refuses links; the final private root remains
readable and subject to the same owner/mode, capacity and export checks. Platforms
without either search flag retain the read-only traversal fallback. No directory
permissions are changed to make an export succeed.

The report follows the existing failure_bundle schema2 encoding. Optional declared native origin and fixed preflight facts preserve older descriptor bytes. Recipe fingerprints describe a reader or Cloud Play operation, not an emulator setup; source/build/runtime and active context stay unknown. There is no authenticated/current-setup claim. Test mode stays synthetic. See [failure bundles](../../docs/FAILURE-BUNDLES.md).

Prepare with `tools/prepare_native.py prepare … --save-copies --failure-reports`. `tools/apply_failure_reports.py` wires only the optional module into a disposable prepared source and retains a source backup; neither command builds or installs. The component requires matching structured observer signals for included components. Native test code exercises real private files, reader refusals, checksum workers and controlled launch-adapter refusals; no live saves or connected device is used.

UI and Android inclusion are separate gates. No installation, permissions, publication, sharing, repair or runtime restore is authorized by these files.

The compiled frontend binds its Loader before asynchronous theme loading. `captureThemeFailure()` reads that object's actual Error status and compares its source with the selected theme. There is no QML failure/path/text argument. A successful selected-theme load or selection change clears the capture and invalidates pending approval. The report retains a fixed load/construction-stage fact, unknown cause and a per-observation operational recipe; the selection URL is not exported or represented as a content hash. It does not diagnose an existing physical device incident.

Qt clears `Loader.source` after a construction failure such as an unprovided
required property. In that branch the same bound Loader must still be in Error,
and its retained ready `sourceComponent.url` must match the selected URL after
lexical path normalization. Null/loading/mismatched/fallback components refuse.
This observes the current component without adding raw error text or caller input.
That branch reports `selected-theme-construction-failed`: the interface failed
during creation. Other selected-source failures retain `selected-theme-load-failed`.
The failure stage is observed; its underlying cause remains unknown.

The compiled frontend also connects `QQmlEngine::warnings` to a native-only
collector. `beginThemeLoad()` starts a fresh selection-bound staging window before
returning the selected filename. Only diagnostics whose URL exactly matches that
selection are considered; child, foreign and fallback files are excluded. Warnings
can precede Loader.Error, but no report exists until the bound native Error check
passes. Rebind, a new load, selection change and successful load prevent replay.

The report's optional `localEvidence` retains at most8 deduplicated error categories
and bounded line/column numbers. Required-property, syntax, unavailable-type,
JavaScript type/reference and unclassified categories are fixed vocabulary. Raw
descriptions, property/type names, URLs, paths and credentials are discarded before
retention. Framework/version, local/bundled/other selection origin and failure stage
are the only configuration facts. This is not a log-file scan, full configuration
capture or stack trace. `errorLog.status` is unavailable when no matching diagnostic
was collected; collection is never inferred from Loader.Error alone.

`lastCloudPreflight` separately retains a known native Cloud opening refusal as a
code, edition fingerprint and time. A newer opening attempt invalidates it. Absence
is unavailable; it is not the latest global launch, accepted dispatch, game boot,
exit or save outcome. These broader runtime observations remain a separate gate.
All fields are present in the same complete private preview and exact-byte export.
The Python producer accepts the same strict optional native-theme evidence shape;
a supplied descriptor still does not authenticate an engine event.

`ThemeFailureReview.qml` and the same standalone `FailurePreview.qml` are compiled resources. An invalid external theme or missing external helper therefore cannot remove this review path. Details or the pointer action opens it with Back selected. Preview keys are forwarded before the existing recovery gesture, and its closing Accept release is fenced. The guarded built-in-theme action remains separate. Private export and the second explicit document copy retain the same native gates; completion after leaving the preview remains visible on the error screen. `apply_failure_reports.py` supports the pinned upstream error screen and the exact retained guarded recovery variant; changed recovery source requires review. `upstream/ThemeError.qml` retains the pinned original solely for preparation fixtures.

Cloud Play retains a report only for an observed file-identity/checksum refusal, changed download snapshot or a platform adapter that returned false. The latter does not prove a missing core or permission problem. Success, cancellation and another attempt invalidate the previous preview. In Cloud or Downloads, L1 (the mapped previous-page action) or **Review failure** opens the same full private preview; Back preserves the selected child panel. Accepted dispatch still does not prove boot, gameplay or save loading. Catalogue/network/install/removal failures are not collected by this adapter.

After a successful private export, a capable Android build returns a separate `copyToken`. `copyPrivateExport(copyToken, sha256)` opens a deliberate system create-document action and emits its asynchronous request/result. The picker never receives a caller report or path. A per-request public Qt receiver keeps old Android results separate; only its weak pending callback retains authority. The exact current token/digest is checked again before the selected target's worker opens/writes/read-backs/closes the provider descriptor. New observations request cancellation; an already-started copy can leave a partial document. The private export remains. Occupied, nonregular, unseekable or unverifiable destinations refuse. No provider URI is retained or exposed to QML, no existing document is truncated, and no persistable grant or new manifest/Java/provider/service/permission source is added.

The provider controls external storage and sync; a verified descriptor read-back is not remote durability proof or a claim that nothing could leave the device. Desktop tests inject only an owned target, never the actual Android chooser. Actual framework/provider/lifecycle and another owner's unaided acceptance remain open. The C++ picker injection is for native adapters/tests, not a QML target API. Provider I/O stays off the GUI thread, while lifetime/currentness/duplicate checks remain on it.

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
