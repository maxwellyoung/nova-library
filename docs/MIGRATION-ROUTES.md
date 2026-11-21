# Verified ROM copy and route candidates

`tools/rom_migration.py` retains the existing inventory, new-destination copy,
checksum verification and explicit interrupted-prefix resume. It never deletes
originals. `route-plan` and `route-review` extend that same receipt boundary with
a private Pegasus metadata candidate and the exact original metadata for rollback.
Neither command applies a route, edits a catalogue, executes an emulator, changes
a save, updates the canonical exporter or enables Play.

## Supported boundary

Start with the original copy plan and a completed destination receipt. The helper
rehashes the original source and destination. Receipt files, exact edition IDs,
sizes and checksums must match that plan. Partial copies, changed content,
ambiguous inventory, symlinks and hard links refuse. A completed-copy resume also
checks the complete receipt inventory rather than trusting its plan digest alone.

The catalogue adapter accepts a single bounded UTF-8 Pegasus collection with one
`x-edition-id` per game and no duplicate identities. A selected game must have
one `file:` field equal to its exact absolute source path. Its effective `launch:`
must contain exactly one `{file.path}` placeholder and no hard-coded migration
root. Relative catalogue routes, multiline route identity, multiple file fields,
multiple collections and unfamiliar quoting need a separate reviewed adapter.
Only paths containing letters, numbers, underscore, spaces, periods, plus signs,
hyphens and directory separators are supported by this initial route adapter.

The candidate changes only the selected `file:` lines. Edition identity,
collection, launch command, playlist name, disc-set ID, notes, favourites,
progress, missing/readiness metadata and unrelated entries remain byte-for-byte
as supplied. An unavailable route remains unavailable; the helper never changes
`x-launchable` or manufactures installation observations.

Select a standalone direct image or one `.m3u` with relative direct-image members.
The full copied family for that exact edition must be selected. Playlist entries
must match the family exactly, preserving every relative name and playlist byte.
Absolute references, parent traversal, duplicates, partial families, nested
playlists and CUE/GDI/CCD/MDS descriptor families refuse. Direct-image extensions
are explicitly bounded in `DIRECT_IMAGES`; unknown containers and archives need
an adapter. The list describes the file-layout boundary, not tested emulator
support or proof that a disc set is playable.

Save layout must be explicitly declared as an independent directory outside both
content trees, with exact save-passport edition/recipe/runtime identity and a
plain evidence label. Unknown, content-relative and mismatched save identities
refuse. This declaration is operator evidence, **not runtime save-continuity
verification**. No save directory is scanned, copied, renamed or restored. Actual
runtime path resolution and recovery remain required before applying a route.

## Private review flow

Keep all plans and review outputs outside Git repositories. Inputs may contain
private paths and the complete original catalogue. Output creation is exclusive
and owner-only; an existing output is protected.

After the existing `plan`, `copy` and `verify` commands, create a selection like
this synthetic example. Use a real exact identity and separately verified save
binding when preparing an actual migration; do not copy this fixture declaration
as runtime evidence.

```json
[
  {
    "editionId": "fixture:edition",
    "path": "set.m3u",
    "familyPaths": ["set.m3u", "disc1.chd", "disc2.chd"],
    "saveBinding": {
      "mode": "explicit-independent-directory",
      "directory": "/private/fixture/saves",
      "identity": {
        "editionId": "fixture:edition",
        "recipeId": "fixture.runtime.v1",
        "kind": "native-save",
        "runtime": {"name": "fixture", "version": "1", "core": "fixture-core"}
      },
      "evidence": "Synthetic adapter declaration; no emulator tested"
    }
  }
]
```

```sh
python3 tools/rom_migration.py route-plan \
  --plan /private/fixture/copy-plan.json \
  --destination /private/fixture/card \
  --catalogue /private/fixture/metadata.txt \
  --selections /private/fixture/selections.json \
  --output /private/fixture/route-plan.json

python3 tools/rom_migration.py route-review \
  --plan /private/fixture/route-plan.json \
  --approve-digest REVIEWED_ROUTE_PLAN_SHA256 \
  --output /private/fixture/review.json
```

Review `changes`, the entire `before`/`after` metadata, `saveBindings` and the
`routePlanSha256` before the second command. `route-review` reconstructs the plan
from current inputs and rejects drift, including same-byte replacement of a
source, destination, receipt or catalogue file; changed root/save-directory
device/inode identities also refuse. The output contains inert `candidate` and
`rollback` text, the reviewed digest and explicit false catalogue/device/runtime
verification flags. It is not a deployment receipt or a migration apply command.

`rollback` is the exact original catalogue, not permission to overwrite a newer
export. Any future apply/revert adapter must compare the current catalogue with
the exact expected before/after identity, preserve later edits and obtain the
required approval. The exporter must consume the reviewed exact route mapping
with stable edition IDs before a later refresh can safely retain those routes.
No canonical exporter integration is included here.

## Remaining physical gates

Filesystem device/inode values bind one local review; they do not authenticate a
removable card, establish Android permissions or prove an adapter can access it.
Refresh the actual volume/card identity, mount, permission and free-space facts.
Reconcile the save binding on the exact runtime, preserve recoverable backups,
review the actual exporter/candidate delta, then seek exact approval for any live
catalogue or device change. Launch a representative standalone and multi-disc
game offline, verify restored saves, notes/favourites/history and return/swap
behaviour. Original deletion remains unavailable in this helper and requires
verified recovery plus separate exact approval.

Targeted verification: `python3 -m unittest tests.test_rom_migration -v`. The
fixtures use synthetic bytes and metadata. They establish candidate generation,
rollback fidelity and refusal/preservation behaviour, not real ROM play, Android
route inclusion, device history or human approval.
