# Local stopping notebook adapter

The main theme uses this optional local notebook through Details → Note and Home’s stopping-note line. The source installer exposes a separate `stoppingNotes` QObject in a selected native copy. Native source inclusion, an Android build, the staged external theme and an installed/physically verified path remain separate states. No camera, screen capture, SAF permission, network, sync, game launch, generated objective or automatic dictation is provided.

`native/stoppingnotes/StoppingNotes` owns offline persistence and explicit original-image import. `theme/StoppingNoteModel.qml` is the receipt-driven QML adapter; `theme/StoppingNotebook.qml` is the integrated controller/touch surface. `demo/StoppingNotes.qml` is a standalone editable fixture with original-image preview, an ellipse-drag annotation interaction, saved-note selection, search, clear/restore and private export. The model/store also support arrows, rectangles and text annotations.

## Main frontend behavior

On builds exposing the complete notebook API, Note opens a notebook for the selected edition, including the currently selected member of a disc set. Earlier notes includes cleared records and searches written text and annotation labels offline. New, History, Reopen and Back cannot silently discard a dirty draft. Clear defaults to Keep note and is reversible. Restoring a note does not choose it for Home; Show on Home is explicit. A stale save retains the draft and offers Keep as new note or a guarded reopen, preserving both writers.

Home shows the explicitly selected local stopping note. When a notebook has retained notes but no stopping selection after a clear, Home does not resurrect its older synced checkpoint as a replacement. The old checkpoint remains visible in Info and can be copied explicitly with provenance/conflicts intact. Note saving never sends a DeviceLibrary action or changes its sync queue.

Attach screenshot lists up to 64 readable regular PNG/JPEG/WebP files in `Pictures/Screenshots`, newest first, without recursion or automatic import. Choosing one copies its exact original to this edition and attaches it to the draft; Save commits the note association. The chooser adds no permission and refuses an inaccessible folder. It cannot browse arbitrary photo libraries, SAF/cloud URIs or capture the screen. Older native builds without `imageChoices()` omit this action. Mark image creates a separate ellipse using controller-selected corners or a touch drag; existing arrow/rectangle/text marks also render. Remove image detaches the draft association while retaining originals.

The main theme reads/caches only viewed stopping cards, rather than loading every edition’s notebook when browsing. Drafts stay fixed across incoming catalogue/progress changes; saving remains bound to the edition opened. On old builds without the optional context, the existing text-checkpoint editor remains available when its original bridge is present.

## Existing text and identity boundary

The existing `library.js` uses `x-edition-id`; its untagged title/path fallback is for browsing only. This store requires an explicit nonempty edition ID of at most 200 characters and refuses `untagged:` IDs. Edition IDs are never inferred from a title, filename, image or play time. A disc's notes belong to its member edition ID, not the presentation group's title.

Existing text-only checkpoints remain in DeviceLibrary and retain their own revision, queued actions and conflicts. This adapter never calls that bridge or changes its SQLite database. Pass the exact existing checkpoint descriptor to `openEdition`/`model.open` to expose it alongside the local notebook:

```js
{ text: "The text already written", revision: 7, pending: true,
  conflict: true, source: "you" } // source is "you" or "catalogue"; revision may be null
```

Reading this descriptor writes nothing. `adoptLegacy` is an explicit copy into a new local note; it preserves the text, whitespace and full descriptor as `legacyReference`. It neither resolves nor acknowledges the old bridge conflict. It does not infer an objective from metadata or time. The main integration reads the exact edition's checkpoint descriptor and leaves the original bridge record intact. An existing checkpoint is shown before any copy, and its established editor remains reachable when the original bridge is available; entering that editor also protects an unsaved local draft.

## Integration API

An integration may include `native/stoppingnotes/stoppingnotes.pri` in its build. The default native preparation/build helpers do not enable it. The optional source installer below adds that build inclusion and exposes a separate `stoppingNotes` context before QML loads. The QObject belongs to the QML engine, so teardown/rebuild reopens the same store without retaining stale engine-owned objects. Its path is `QStandardPaths::writableLocation(QStandardPaths::AppLocalDataLocation) + "/stopping-notes-v1"`; an empty base exposes `stoppingNotes` as null instead of creating a relative/root fallback. A QML caller can use `storage: typeof stoppingNotes !== "undefined" ? stoppingNotes : null`.

For standalone/manual integration, construct `library::StoppingNotes(privateRoot)` explicitly. Its optional third constructor argument selects an explicit screenshot folder for isolated fixtures; the production context uses the platform Pictures/Screenshots location, with no root-path fallback. The directory must be new/empty or carry this store's marker. Use application-private storage **outside every repository and catalogue/media directory**. The platform/build owner must verify the actual app-private location; this module does not grant permissions or decide a SAF location. Existing read-only private directories remain read-only; an attempted write returns failure.

All writes require the notebook's exact `expectedRevision`, a numeric integer. Each committed mutation increments it. A failed write does not publish a new revision. Successful receipts contain `{ok:true, notebook}`; note writes also contain `noteId`, and import contains `imageId`/`imageUrl`. Failures contain `{ok:false,error}`. Revision conflicts additionally include `current`, preserving the stored notebook. Receipts describe a completed local commit, never a sync or gameplay observation.

| Method | Behavior |
|---|---|
| `capabilities()` | Version, local-only capability and bounds; reports unavailable storage |
| `imageChoices()` | Read-only bounded screenshot-folder choices; importing still requires explicit selection |
| `openEdition(id, legacyDescriptor)` | Reopen exact edition; empty descriptor is `{}`; missing notebook is revision 0; malformed existing metadata is an error |
| `importOriginal(id, localFileUrl, expectedRevision)` | Explicitly copy one local regular PNG/JPEG/WebP into this edition's immutable originals registry; no folder scan or URI/network fetch |
| `createNote(id, draft, expectedRevision)` | Append a note and make it the stopping card |
| `editNote(id, noteId, patch, expectedRevision)` | Change allowed fields only; omitted fields are preserved; editing a cleared note is refused |
| `clearNote(id, noteId, expectedRevision)` | Retain a cleared note and all original bytes; clear the stopping-card pointer if applicable |
| `restoreNote(id, noteId, expectedRevision)` | Restore a cleared note; selecting it as the stopping card is a separate explicit action |
| `setStoppingNote(id, noteId, expectedRevision)` | Select a retained, non-cleared note as the stopping card |
| `adoptLegacy(id, descriptor, expectedRevision)` | Explicitly copy text-only checkpoint and provenance; never mutate the old bridge |
| `search(id, text, includeCleared)` | Case-insensitive offline search of written text and annotation labels in one exact edition |
| `exportEdition(id, newLocalDirectoryUrl)` | Explicit new private bundle directory outside the store; refuses existing outputs and missing/corrupt originals |

A draft/patch accepts only `text`, `imageId` and `annotations`. Creation requires `text`, which may be empty. `imageId` must be empty or identify an original explicitly imported for this exact edition. A different edition cannot attach an image merely by guessing/knowing its hash. To remove an association, pass both `imageId:""` and `annotations:[]`; the original stays retained. Annotations refer to the imported original, never a rendered screenshot or a mutable edited image.

```js
{
  text: "My written clue",
  imageId: "<64 lowercase SHA-256 characters from import receipt>",
  annotations: [{kind:"ellipse", x1:.1, y1:.2, x2:.4, y2:.6,
                 text:"", colour:"amber"}]
}
```

Each mark requires all seven fields. `kind` is `ellipse`, `rectangle`, `arrow` or `text`; `colour` is `light`, `dark` or `amber`. Coordinates are finite normalized original-image coordinates in `[0,1]`; ellipse/rectangle corners must have positive extent. Text marks need a nonempty label. Annotation rendering must account for the actual preserved-aspect image bounds, not the whole preview box. The fixture demonstrates this.

`openEdition` supplies transient `imageStatus` (`none`, `ready`, `missing`, `corrupt`) and a private local `imageUrl` only for verified bytes. These transient fields are never persisted/exported. Missing/corrupt images retain the written note and marks. They cannot be silently replaced by another asset. Exports stop instead of producing a supposedly complete bundle with missing originals.

## QML adapter behavior

Set `storage`, then call `open(exactEditionId, legacyDescriptor)`. `select`, `beginNew`, `setText`, `setAnnotations`, `addAnnotation`, `detachImage`, `save`, `importOriginal`, `clear`, `restore`, `makeStopping`, `adoptLegacy`, `search` and `exportTo` wrap the methods above. `notebook`, `selectedNote`, `draft`, `dirty`, `previewUrl`, `lastError` and `conflictingNotebook` describe state.

The adapter updates saved state only from successful receipts. Save/import errors keep unsaved draft text and marks. A stale-revision save leaves the expected revision stale, preventing a blind retry from overwriting another writer. The user can explicitly reopen stored state to discard a draft, or call `keepDraftAsNew()` to retain the other writer's note and append the draft as another note. This is **local notebook conflict handling**, not a resolver for the existing bridge/server conflict. No network conflict is acknowledged or overwritten.

The standalone fixture's Reopen/New/selection buttons are explicit draft-changing actions. An integrated product should apply its own normal unsaved-edit confirmation before those actions. Never refresh incoming bridge data over a dirty draft.

## Storage, bounds and private export

The store uses a private marker, cross-process `QLockFile`, exact edition IDs inside SHA-256-named directories and atomically committed JSON (`QSaveFile`, direct-write fallback disabled). Metadata is validated before saving and on reopen. Existing corrupt/wrong-edition metadata is retained and refuses mutation; it never becomes an empty writable notebook. New directories are owner-only; existing private-directory permissions are respected. Files are owner read/write. Symlink source images, metadata and image storage paths are refused.

Bounds per edition: 64 retained notes (including cleared notes), 4,000 UTF-16 characters per note, 32 annotations per note, 160 characters per annotation label, 512 KiB metadata, 32 retained originals, 16 MiB per original, 128 MiB total originals, dimensions at most 8192 each and at most 16 megapixels. Image headers and full decode must succeed before import. Unsupported/invalid/oversized inputs and unknown metadata fields are rejected. Text/mark rendering is plain text; user text is not treated as rich HTML.

Originals are immutable byte copies named by their SHA-256. Source files are never edited/deleted. Editing annotations, detaching an image, clearing/restoring notes and changing the stopping card do not alter/remove originals. No garbage collector or automatic retention deletion exists. Quota exhaustion is an explicit failure, and retained orphan copies count toward the bounds too. If copying an original succeeds but its metadata commit fails, the copy remains unassociated and can be explicitly reimported; the old committed notebook remains intact.

An export contains `notebook.json` and `originals/<sha256>` with byte-identical original images. It includes retained cleared notes and registered originals; it excludes transient local URLs/source paths. It is staged privately and published to a new directory. The original may contain EXIF or other private metadata, and text may contain private information: originals are intentionally preserved. This is a **private export**, never an upload or permission to share. Orphan copies from failed association commits are retained in storage but are not registered/exported until a successful explicit reimport.

## Build and verification

Use an available Qt 5.15 toolchain with Core, Gui, Qml, Quick and Test. Build in disposable directories outside the source checkout:

```sh
qmake /absolute/source/native/stoppingnotes/tests.pro
make -j4
./stopping-notes-tests
```

Build `fixture.pro` in a separate directory. The fixture takes an explicit new private store; it never defaults to a repository path:

```sh
QT_QUICK_BACKEND=software ./stopping-notes-fixture /private/fixture/store
# Synthetic QA-only import/edit/clear/reopen/export and screenshot, using a fresh parent:
QT_QUICK_BACKEND=software ./stopping-notes-fixture /private/qa/store --smoke /private/qa/fixture.png
# A separate process reopens the saved image, annotation and text without editing:
QT_QUICK_BACKEND=software ./stopping-notes-fixture /private/qa/store --reopen-smoke /private/qa/reopened.png
```

The retained macOS Qt 5.15.10 static toolchain references the removed AGL framework. On the current SDK, the verification run removed only ` -framework AGL` from each **generated disposable Makefile** before linking. No global toolchain or source project was altered for this compatibility adjustment. The Qt SDK-version warning remains disclosed.

Tests launch independent OS processes against the same real disk store, then check restart/reopen/edit/clear/restore/search, exact edition isolation, legacy conflict retention, concurrent revisions, missing/corrupt image and metadata, real failed writes, original retention, bounded/path rejection, private export and actual QML draft retention. The standalone QML smoke renders and persists against this same real store implementation.

No result here establishes an Android build, installed UI, SAF capability, physical screenshot capture, or device restart behavior. Root-owned integration, real permission handling and the latest-theme offline edit/restart/reopen/clear gate remain required on Nova.

## Optional application-source inclusion

`tools/apply_stopping_notes.py` operates on an explicitly selected patched Pegasus source **copy**. It supports the current DeviceLibrary lifecycle/anchors and refuses unsupported or ambiguous input. It changes only `src/backend/FrontendLayer.cpp`, `src/backend/backend.pro` and `src/backend/CMakeLists.txt`, and stages only `StoppingNotes.cpp`, `StoppingNotes.h` and `stoppingnotes.pri` under `src/backend/library/stoppingnotes`. It does not touch `FrontendLayer.h`, Java/JNI, permissions, the existing checkpoint database, service configuration, `prepare_native.py`, `build_android.py`, or the main QML UI.

```sh
python3 tools/apply_stopping_notes.py plan /owned/native-copy/source --output /private/stopping-plan.json
python3 tools/apply_stopping_notes.py apply /owned/native-copy/source --plan /private/stopping-plan.json --backup /private/stopping-before
python3 tools/apply_stopping_notes.py verify /owned/native-copy/source --backup /private/stopping-before
```

The plan is read-only for the native source and binds exact shared-file and module hashes. Changing those inputs before apply refuses without mutation. Plan and backup locations must be outside both source and repository; output files are exclusive/private. Apply without a saved `--plan` performs the same preflight/checks immediately in one process. Before replacing shared files, the tool backs up their exact bytes and records hashes. Writes are staged/atomic, checked again before publication, and verified afterward. A failed transaction keeps an `INTEGRATION-INCOMPLETE` marker and recoverable originals; it restores only its own exact writes, never a newer owner edit. Do not build an incomplete copy.

Reapply with the same backup is read-only when the exact owned include/context/build blocks and staged module bytes still match. Changed owned blocks, partial integrations, modified module payloads and implicit module upgrades refuse. Other optional integrators may add their own independent blocks. Thus whole-file after-hashes in the original receipt remain **historical**; `observedSharedFiles` and `sharedFilesMatchOriginalReceipt` make any later whole-file difference explicit. Scoped reapply does not certify arbitrary surrounding source. Serialise appliers against one source copy; both application orders and reapplication with the controller-check applier are tested.

The qmake hook includes the staged `.pri`; the CMake hook appends an owned `target_sources(pegasus-backend PRIVATE ...)` block. The local source-inclusion verification compiled the actual patched `FrontendLayer.cpp`, module and moc objects against the retained native headers using desktop Qt 5.15, C++11 and exceptions disabled, and configured the emitted CMake block with assertions on its target sources. The Python installer itself performs no build. This is a desktop static-archive/build-hook check, **not a complete linked native application or Android build**. The previous standalone model/fixture tests are separate storage/API evidence, not native application inclusion evidence.

Applying an optional module changes a prepared source tree. The original `nova-build-inputs.json`/APK receipt cannot certify those new bytes; the native owner must bind a new complete source/build receipt. No default preparer/build helper is modified to bypass that check. Android compile/link, actual platform storage, QML entry point, SAF import and current-device restart/edit/clear remain the next integration gates.
