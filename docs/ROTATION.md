# Your rotation

Your rotation is a small, ordered collection saved in this theme on this device. It works without the optional progress service. It is separate from favourites, recent play and synced collections; adding a game never installs it, changes its route or moves a file.

## Use

From a game's **Details → Collections → Your rotation**, select the row to add or remove that exact edition. For a disc group this affects only the displayed disc, identified in the explanation. Other discs, regions and remakes keep their own identities.

Open **Collections → Your rotation** to browse in your chosen order. The normal Play/Details/Back paths still apply. An unavailable game does not become launchable by entering the rotation. Home continues to lead with recent local launches.

With Your rotation selected in the collection list, press **X → Edit rotation** (or its mapped Details button). Up/down selects an edition, left/right moves it earlier/later, the mapped accept button removes it from this collection, and Back returns to Collections. The footer buttons provide the same operations for touch. Removing a game from the rotation keeps its files, saves, favourites and history. If removal affects the edition whose Details are open, the view returns to Collections instead of silently replacing it with another game.

The limit is 12 editions, keeping this a small optional rotation rather than a second full library. The wider library is never capped. Remove an entry before adding another at the limit; nothing is automatically displaced.

## Persistence and unavailable state

`rotationV1` uses the existing Pegasus theme-memory store:

```json
{"version":1,"editions":[{"id":"demo:orbit","title":"Amber Orbit"}]}
```

IDs are explicit stable edition IDs. Untagged identities, apps, emulator apps and unresolved disc groups cannot be added. Each cached display title is plain, bounded text. Only version, ordered IDs and cached titles are retained; there is no network action or progress-service outbox entry.

If an edition temporarily leaves the catalogue, its identity and place stay in the store. The editor shows the last saved title and **Not in catalogue**; no launch target is invented. The edition returns to its old place when its exact identity is available again. Duplicate catalogue identities also stay unavailable rather than selecting an arbitrary route. The editor can remove an absent edition to free a slot.

Unreadable, future-schema, duplicate or otherwise invalid preferences remain unreadable; they are not silently replaced with an empty rotation. Read exceptions disable editing for this feature. A refused write leaves the previous UI state and saved order intact. There is no automatic reset or migration, and no sync promise.

The synthetic demo uses in-process theme memory and forgets it when closed. Actual Pegasus persists theme memory. A synthetic preference roundtrip or fresh host process seeded with saved JSON tests the theme boundary, not the Android runtime's disk durability.

## Verification

```sh
node --test tests/rotation.test.cjs
python3 tools/smoke_rotation.py --host /path/to/existing-theme-host \
  --bundle /path/to/synthetic-save-copy-fixture --output /path/to/new-evidence
```

The smoke runner reuses the isolated Qt host built for the read-only Save copies fixture; it does not install an app, build a native library, contact a service or launch a real game. It checks the actual theme with synthetic games across Nova, light, large-text, wide and inset profiles, plus fresh-process preference reapplication, corrupt/read-refused/write-refused preferences, missing entries, long titles and the full-list boundary. Source and desktop verification do not prove installation, physical buttons, real game return or Android persistence; those remain device acceptance gates.
