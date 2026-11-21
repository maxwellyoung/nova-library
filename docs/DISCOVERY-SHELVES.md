# Your shelves

Your shelves are small collections that you name yourself, for a feeling or a purpose: "dreamlike", "funny", "tight mechanics", "beautiful old menus", "ten-minute adrenaline". The theme saves them on this device. They work without the optional progress service and change no game files, saves, favourites, history or Home.

A shelf only holds what you put on it. Nothing is inferred from play time, ranked or recommended. Every shelf is labelled **Yours** in Collections, and its explanation reads "Chosen by you … Not a suggestion." That keeps it visibly apart from service suggestions and catalogue groupings, which keep their own labels and reasons.

## Use

- **Start a shelf.** Open a game's **Details → Collections → New shelf**, type a name and confirm. One write makes the shelf and adds that exact edition. For a disc group, only the displayed disc is added, and the explanation names it.
- **Add or remove a game.** In **Details → Collections**, select a shelf to toggle that edition. Rows show **Add here** or **On this shelf**.
- **Browse.** **Collections** lists Your rotation first, then your shelves in your order, then synced collections and suggestions. Open a shelf to see its games in your order. Play, Details and Back work as they do elsewhere.
- **Edit.** With a shelf selected in the Collections list, press **X → Edit shelf** (or its mapped Details button). Rows:
  - **Name**: accept to rename. The games stay on the shelf.
  - **Kind**: Feeling or Purpose. Accept, left or right changes it. It is only your description.
  - **Shelf order**: left / right moves the shelf earlier / later in Collections. Your rotation stays first.
  - **Each game**: left / right moves it earlier / later. Accept removes it from this shelf only.
  - **Delete shelf**: available only when the shelf is empty. A shelf with games is never discarded by one press.
  Back returns to Collections. The footer buttons give touch the same operations.

If you remove a game from a shelf while its Details are open from that shelf, the view goes back to Collections instead of silently showing another game.

## Limits and names

You can keep up to 8 shelves, each holding up to 24 editions. At a limit the action is refused with an explanation, and nothing is displaced. A name is plain text of up to 40 characters, with inner spaces collapsed. Two shelves cannot share a name, ignoring case. A blank name changes nothing.

## Persistence, conflicts and unavailable state

`shelvesV1` uses the existing Pegasus theme-memory store:

```json
{"version":1,"serial":2,"shelves":[
  {"id":"shelf:2","name":"Ten-minute adrenaline","kind":"purpose","editions":[{"id":"demo:orbit","title":"Amber Orbit"}]},
  {"id":"shelf:1","name":"Dreamlike","kind":"feeling","editions":[{"id":"demo:garden","title":"Tidal Garden"}]}]}
```

Shelf IDs come from a counter that only moves forward, so a deleted shelf's ID is never reused. Edition IDs are exact stable edition identities. Untagged identities, apps, emulator apps and unresolved disc groups cannot join a shelf. Same-title regional or remade editions remain separate entries. Cached titles are bounded plain text.

If an edition leaves the catalogue, it keeps its place and last saved title. The editor marks it **Not in catalogue**, and no launch target is invented. Duplicate catalogue identities are also treated as unavailable rather than picking an arbitrary route.

Unreadable, future-schema, duplicate or otherwise invalid preferences stay unreadable. They are never silently replaced with an empty set. Collections then shows **Your shelves** with the reason, and the picker shows it as unavailable, without offering New shelf. A read exception behaves the same way. Before each write, the theme re-reads the stored value. If it differs from what the screen opened, the newer value is loaded and the edit is not applied. A refused write leaves both the screen and the saved shelves unchanged. There is no automatic reset, migration, network action or sync promise.

## Verification

```sh
node --test tests/discovery.test.cjs
python3 tools/smoke_shelves.py --host /path/to/existing-theme-host \
  --bundle /path/to/synthetic-save-copy-fixture --output /path/to/new-evidence
```

The smoke runner reuses the isolated Qt host built for the read-only Save copies fixture. It does not install an app, build a native library, contact a service or launch a real game. It drives the actual theme with synthetic games across Nova, light, large-text, wide and inset profiles. Coverage: creating with an edition, duplicate and blank names, add/remove, rename, kind, shelf and member reordering with controller keys and touch hints, the guarded delete, a refused write, a conflicting stored value, Android Back, and removing an open member. It also covers reapplying preferences in a fresh process, corrupt or read-refused preferences, absent editions, both limits and long titles. Source and desktop checks do not prove installation, physical buttons, the Android keyboard or Android persistence. Those remain device acceptance gates.
