# Catalogue contract

Pegasus supplies each game object, assets, files, and missing-file status. Nova reads additional metadata using Pegasus's `x-` fields. Stable edition identity keeps editions and progress distinct; titles alone are not an identity.

| Field | Meaning |
| --- | --- |
| `x-edition-id` | Stable identifier for one edition |
| `x-system-id`, `x-system-name` | Console/platform grouping |
| `x-home` | `true` includes an entry in the catalogue's Home selection |
| `x-launchable` | `true` only for a separately validated local launch route; runtime missing status still blocks play |
| `x-route-label` | Human-readable local route description |
| `x-session-profile` | Optional verified control adapter; `hakux-nova-v1` selects the HakuX shortcut guide only after the matching build and enabled controls are checked. Absent/unknown values keep the ordinary runtime guide. |
| `x-compatibility-recipe-id`, `x-compatibility-receipts` | Explicit tested-setup link and bounded JSON observations for Details → Checks; informational only. See [compatibility receipts](COMPATIBILITY.md). Neither field promotes route readiness. |
| `x-ready-devices` | JSON list or separated names; last-known catalogue availability |
| `x-minutes-value` | Numeric recorded minutes; empty means unknown, `0` means zero |
| `x-last-played` | Recorded date; absent means unknown |
| `x-progress-state` | `unknown`, `backlog`, `playing`, `paused`, `finished`, or `abandoned` |
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

`x-original-aspect` accepts `4:3`, `16:9` or `other`, paired with a nonempty plain-text `x-original-aspect-source` citation (at most 500 characters). It describes that edition's original presentation. Neither screen-aspect metadata, cover dimensions, console identity nor a fit note supplies this evidence. Without a valid pair, original aspect remains unknown.

Library → Filters → Aspect separates **Originally 4:3**, **Native 4:3 tested**, **Stretch-only setup** and **Setup unconfirmed**. Native/stretch results come only from explicit display observations in the linked compatibility recipe; see [display checks](COMPATIBILITY.md). They do not alter settings or enable Play. Positive filters require every disc in an explicit set to match; unconfirmed includes sets with unconfirmed members and selects such a member for Details. The disc picker still contains the complete set. Aspect intersects the existing system/device/status/favourites/search filters, is saved locally, and Clear resets it. Entering a new console intentionally starts with that whole console, as before.

Home leads with valid local launch history, followed by separately labelled handpicked, playing, favourite and imported shelves. A game appears once per explicit disc group. Pegasus launch/finish events refresh the copied history after statistics providers handle them; an observed launch is not gameplay or save-state-resume proof. Source-only starter/fallback labels remain explicit when history is absent.

Home is a game shelf: Android apps and emulator utilities are excluded from recent, favourite and fallback Home selections. Their entries remain available in Apps or Library.

Per-device installation and filesystem-capacity fields are specified in [Installation observations](installation-observations.md). They retain scan dates and do not promote launch routes.

An optional `romCloud` bridge with `catalogueVersion: 1` adds native-minted cloud editions to this same browsing model. Server origin and exact content identity distinguish them from Pegasus entries with the same title. A server listing alone never enables Play. Installed copies use the local ownership marker, and a changed remote copy cannot relabel that installed identity. Cloud openings are versioned local history, not recorded minutes or service progress. Until the progress service registers those identities, cloud favourites stay local and service status/collection edits stay unavailable. See [the Cloud client contract](../native/romcloud/README.md).

The optional phone-audio action requires an available, launchable Android app entry whose `x-app-package` exactly matches `io.github.jqssun.airplay`. Matching titles do not enable it. This is an app route, not a ROM launch or a claim that an audio receiver is connected. See [phone audio](PHONE-AUDIO.md).
