# Installation and capacity observations

Installation is separate from a launch route, a registered catalogue item and a gameplay check. The observations below neither perform nor authorize installation or cleanup. The separately guarded Cloud download flow has its own ownership, preflight and runtime boundaries.

`x-installations` accepts a JSON object with `nova` and `legion` observations. Each has `state` (`installed`, `absent`, `partial`), `observedAt` (ISO timestamp), `source`, `scopeComplete` and optional `offline`. Missing, malformed or undated observations display **Not checked**. An absent observation is accepted only with a complete scan. An offline capture keeps its original date. Matching is by edition identity; ROM and Steam editions are not merged by title. A disc set is fully installed only when every member has an installed observation.

## Filesystem capacity

The legacy `x-storage-volume` field accepts one JSON snapshot with `id: internal-data`. Its internal-only readers remain supported. The additive `x-storage-volumes` field accepts an array of at most two snapshots, with unique roles `internal-data` and `sd-card`. These roles name internal storage and the removable slot, not an authenticated card identity. Both fields may be exported for older-reader compatibility; agreeing duplicate observations are deduplicated for selection rather than added together.

Each snapshot requires nonnegative safe-integer bytes `total`, `used` and `free`, positive total, a real nonfuture `observedAt`, and a plain source label of at most 200 characters. Used plus free may be less than total. The gap is displayed as **Unavailable capacity**, with no claimed cause or invented file category. Captures retain their own timestamps; export time does not refresh them. Invalid core values are omitted.

The latest valid capture is chosen separately for each role. Contradictory total/used/free values at the same instant suppress that volume's capacity rather than silently using an older reading. Different timezone spellings of the same instant are compared as one capture. A missing SD observation means **not checked**, not that no card exists or that it is empty. Card removal/replacement requires a fresh observation; cached data does not prove a current mount.

## Optional measured categories

A snapshot can contain an optional `breakdown`:

```json
{
  "id": "internal-data",
  "total": 1000,
  "used": 800,
  "free": 100,
  "observedAt": "2026-11-10T10:00:00Z",
  "source": "Synthetic allocated-byte observation",
  "breakdown": {
    "basis": "allocated-bytes",
    "disjoint": true,
    "categories": {
      "game-data": 300,
      "app-data": 200,
      "cache": 0,
      "save-data": 50
    }
  }
}
```

The producer must actually measure disjoint allocated-byte sets. `game-data`, `app-data`, `cache` and `save-data` must not overlap; in particular an app's cache/save subdirectories cannot also be counted within its app-data category. The theme validates the declaration and arithmetic; it cannot authenticate the scan. A boolean assertion is not independent proof that measurement was disjoint. No category collector, private-app access or persistent permission is supplied by this display contract. The separate [capacity collector](STORAGE-CAPTURE.md) reads filesystem totals only; it never invents category shares.

Only those four category keys are supported. Each supplied value is a nonnegative safe integer and their sum cannot exceed used bytes. Missing categories show **Not measured**, while an explicitly measured zero shows **0 B**. Remaining used bytes stay **Unclassified used**. A malformed, overlapping, unknown-kind or logical-file-size breakdown is refused without discarding agreeing capacity totals; all used bytes remain unclassified. Conflicting category reports for one capture likewise suppress classification while retaining agreed capacity. Older categories are never borrowed for a newer snapshot.

## Presentation and bounds

Settings → Storage starts with a **Volume** row. Accept or left/right selects Internal storage or microSD; the footer supplies the same action. It updates the existing capacity bar and category rows. Selecting a category highlights its segment, including unclassified usage. Exact segment widths represent bytes divided by that volume's total: there is no minimum-width inflation, and zero-width measured categories stay zero. Free and unavailable capacity are separate parts. Low reported free space retains its existing warning treatment. Different volumes are never summed or displayed as equally sized byte quantities.

The independent **ROM inventory · all locations** remains below. Existing `x-size-bytes` and `x-size-observed-at` supply logical ROM file sizes, which neither measure app private storage nor reconcile filesystem usage. They are not subtracted from used space. Unknown sizes remain counted. Files/DroidDeck management rows use configured utility routes; this observation view adds no deletion, scan, install or permission action. Back returns to the same Settings row.

All fields are informational imported snapshots. Do not treat them as an authenticated live reading, runtime-idle proof, save backup or cleanup authority. Before removal/migration, use the separately guarded flow and obtain its actual required evidence. Icon provenance is retained in `PROVENANCE.md`; no symbol font is required.

Verification: `tests/storage-volumes.test.cjs` checks byte arithmetic, zero/unknown, per-role captures, conflicts, invalid classifications and input preservation. `tools/smoke_storage.py` exercises the real QML with synthetic snapshots and the existing isolated Qt host. Neither establishes actual Nova internal/SD measurements or physical controls; those remain device acceptance gates.
