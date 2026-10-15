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

Optional storage evidence: `x-size-bytes` contains nonnegative observed ROM-file bytes; absence means unknown. `x-size-observed-at` contains an ISO8601 capture timestamp. `x-catalogue-generated-at` is the separate export timestamp. These do not establish current disk usage, free space or emulator readiness. Android utilities are excluded from the storage view; entries without size remain counted as unknown.

Optional multi-disc presentation: `x-disc-set-id`, `x-disc-set-name` and a positive integer `x-disc-number` group two or more uniquely numbered members of the same explicit set, system and set name. Similar titles alone never group. Browse views show one game; A opens a disc picker using the latest local launch history, otherwise the lowest disc number. Progress, favourites, IDs, routes and file bytes remain edition scoped. Changing discs during an active game uses the emulator.

Optional app identity: `x-app-package` identifies an Android app entry. The Apps view uses `androidapps` entries. An unavailable Steam edition may offer a separate action to open the configured DroidDeck app; this action does not configure the game route or start an install.

Optional gameplay evidence uses `x-nova-gameplay-note`, `x-nova-gameplay-source` and `x-nova-gameplay-observed-at` together. The original observation date is independent of catalogue export time. A short interaction check is not sustained performance evidence. `x-display-aspect` requires `x-display-aspect-source`; absent evidence remains unknown. Legacy `x-device-fit` is a catalogue note, not proof of original aspect or rendering behavior.

Home is a game shelf: Android apps and emulator utilities are excluded from recent, favourite and fallback Home selections. Their entries remain available in Apps or Library.

Per-device installation and filesystem-capacity fields are specified in [Installation observations](installation-observations.md). They retain scan dates and do not promote launch routes.
