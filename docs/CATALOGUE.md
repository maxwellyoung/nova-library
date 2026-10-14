# Catalogue contract

Pegasus supplies each game object, assets, files, and missing-file status. Nova reads additional metadata using Pegasus's `x-` fields. Stable edition identity keeps editions and progress distinct; titles alone are not an identity.

| Field | Meaning |
| --- | --- |
| `x-edition-id` | Stable identifier for one edition |
| `x-system-id`, `x-system-name` | Console/platform grouping |
| `x-home` | `true` includes an entry in the catalogue's Home selection |
| `x-launchable` | `true` only for a separately validated local launch route; runtime missing status still blocks play |
| `x-route-label` | Human-readable local route description |
| `x-ready-devices` | JSON list or separated names; last-known catalogue availability |
| `x-minutes-value` | Numeric recorded minutes; empty means unknown, `0` means zero |
| `x-last-played` | Recorded date; absent means unknown |
| `x-progress-state` | `unknown`, `backlog`, `playing`, `finished`, or `abandoned` |
| `x-story` | Explicit written checkpoint, never inferred from minutes |
| `x-recommendation-score`, `x-recommendation-reason` | Optional score and explanation |
| `x-catalog-source` | Plain provenance label |
| `x-thread-ids` | Collection identifiers |

The theme retains some legacy `canon-*`, `nova-location` and `legion-location` fields for compatibility with earlier exports. Device names are display labels, not hardware authentication or reachability evidence. The generator uses synthetic identifiers and never copies a personal export.

The optional native bridge supplies personal entries, thread memberships and recommendations. Its explicit personal status, including `unknown`, overrides catalogue status. Theme-only kept games remain in Pegasus theme memory. Bridge writes and synchronization are unavailable in the synthetic demo.

Do not mark a route ready merely because a server lists a copy. Validate the local file and adapter separately. Metadata and sync snapshots must never supply executable network content to the bridge.
