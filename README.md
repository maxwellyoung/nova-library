# Nova

A quiet, controller-first library for a handheld: a recent-games Home shelf, a searchable index, consoles, collections, and Settings. Covers keep their shape. Missing artwork gets a title. Play is enabled only when the catalogue marks a local route and the runtime sees its referenced file. Launch availability is separate from gameplay compatibility. Unknown progress stays unknown.

Nova is a custom QML frontend **built on Pegasus Frontend**. The engine, game discovery, controller integration, launching, and much of the native application come from [Pegasus Frontend](https://github.com/mmatyas/pegasus-frontend). This repository contains the original Nova interface and a complete source patch for its optional native personal-library bridge; it is not a new native engine.

## Try the synthetic demo

The demo has invented titles and original generated PNG covers with SVG source designs, without ROMs, accounts, network access or launch commands. It loads the same QML interface as the theme through a small mock of the Pegasus API. Memory is in-process and resets when the demo closes; personal synchronization and editing are unavailable.

Requirements: Python 3.10+ and a Qt 5.15+ or Qt 6 installation with QtQuick, QtQml, QtQuick.Window and its `qml` runner.

```sh
python3 tools/make_demo.py
qml demo/Demo.qml
```

Use arrow keys to move, Enter to select, Escape to return, X for details, Y to favourite a game, and Page Up/Page Down to change screens. Home/End jump within a list. The demo generator is deterministic and refuses to overwrite an existing output directory. A Pegasus metadata catalogue is also generated for testing inside Pegasus itself; all demo entries are non-launchable.

The interface also includes an Apps index, explicit multi-disc selection, and an Open DroidDeck action for Steam editions without a configured local game route. That action opens the app so you can find/install the game there; it does not start a download. Gameplay evidence and screen fit are shown separately from launch availability.

With the optional [PC runtime adapter](docs/PC-RUNTIMES.md), Details offers explicit DroidDeck/GameNative selection for Steam editions and remembers the selected app/version. Direct requests do not require debugging tools and never imply game installation, successful boot or working controls. Existing shortcuts remain available separately; changing a runtime never resets prefixes or saves.

Home leads with recent local launches when available, otherwise an optional owner shelf or your library. The selected game's platform and reason sit beside its title. `theme/Owner.js` holds an optional name and a short "Right now" list of edition ids. A game's Details offer **Controls**: its emulator's buttons, plus game-specific cards for the titles in `theme/Guides.js`. Settings → Status shows the last health check if a `health.json` sits beside the catalogue; without one it says no check has arrived. Library labels an active filter and counts what it shows, and drops recognized dump tags from displayed titles without changing files or edition identity.

See [validation](docs/VALIDATION.md) for which steps were exercised. A passing helper test or generated demo is not proof of the GUI running on a device.

Details → **Checks** keeps boot, menus, gameplay, physical controls, sound, save/restore, return and sustained-play observations separate. Each result belongs to an explicit edition and tested setup, with its date, source and method. Missing, conflicting and old-setup evidence stays visible rather than becoming a compatibility promise. See [receipt format and portable export](docs/COMPATIBILITY.md).

Home puts local launch history before handpicked shelves and refreshes it on Pegasus launch/return events. Library's **Aspect** filter separates sourced original 4:3 presentation from explicit native-4:3 or stretch-only checks for a linked setup. Console identity, cover shape and a fit note never establish those results.

## Use the theme in Pegasus

Copy the `theme/` directory to a new theme directory in your Pegasus configuration, select **Nova** in Pegasus's theme settings, and point Pegasus at a catalogue containing your own files. Existing themes and catalogue settings need not be replaced. The theme uses the runtime's system font; no third-party font binaries are bundled.

Plain Pegasus can display the theme, browse, filter, and keep games in theme memory. Settings separates appearance, progress sync, storage snapshots and file-management shortcuts, launcher controls and catalogue refresh guidance. Home surfaces a stopping note when one exists. With the optional native notebook, Details → Note supports local text, explicit screenshot attachment, image marks, history/search, reversible clear and draft/conflict protection; older builds retain the original checkpoint editor. See [the local notebook](docs/STOPPING-NOTES.md). The optional `deviceLibrary` bridge adds durable personal progress and collections. The demo makes no claim that a file exists on a real device. See [the metadata contract](docs/CATALOGUE.md) when producing your own catalogue.

Console browsing uses two columns on a 4:3 handheld and three on wider screens, with natural-shape cover previews when artwork loads. Platform marks are drawn locally with Qt Canvas, so no SVG decoder or icon font is required. Settings → Appearance includes larger text, light/dark surfaces and reduced motion; Settings → About Nova retains engine and artwork credits. The third-party marks identify platforms, not compatibility or endorsement.

`Owner.bottomInsetPixels` optionally reserves a measured device overlay band. Its default is zero; the same usable height applies to lists, Home, Details, the cloud shelf and button hints. This is an explicit device profile, not automatic safe-area detection or a repair to the native compositor.

## Optional cloud library

The optional RomM client adds cloud copies to the ordinary Library and Consoles. Their main action is Install, Resume download or Play; download details return to the originating game. Settings → Cloud library retains connection and maintenance. Cached browsing, resumable downloads, checksum verification, multi-disc playlists and offline launch use the same native client. Removal is review-only until a trusted runtime-idle adapter is connected. Initial native adapters cover SNES/Snes9x and PlayStation/SwanStation. Other systems retain an explicit unavailable state. Older native builds keep the separate Cloud shelf. With the optional queue bridge, R1 opens persistent Downloads from Cloud; other games can be queued while one transfers. Batches pause when Library leaves the foreground and always reopen paused after a restart. Remove entry changes only the queue, never ROMs or saves.

See [client integration and evidence boundaries](native/romcloud/README.md) and the [private backend deployment candidate](infra/romm/README.md). Automatic cloud-save loading is **not enabled** in this first download build: RetroArch's startup-sync ordering must be verified before it can safely load a game with a newer remote save. Existing progress sync is a separate feature.

Apps → Phone audio explains the optional receiver route for sending an iPhone's existing playback to Nova. A configured receiver gets an ordinary app-launch action; the theme does not install or start one. Wi-Fi reception and mixing with game audio require device verification. See [phone audio](docs/PHONE-AUDIO.md).

## Native source

The host-side [private save-passport tool](docs/SAVE-PASSPORT.md) captures explicit save files with edition/runtime identity and checksums, verifies them, and stages recovery into a new folder. It never overwrites live saves or enables cloud sync. Actual emulator export/import and restore remain device-specific verification gates.

Per-game Controls puts saving and emulator navigation first, with HakuX menu guidance and an explicit fallback for unidentified runtimes. Story solutions are kept out of this controls sheet. The optional [HakuX session adapter](native/hakux/README.md) adds physical Select combinations in a pinned source build; its APK and physical save/restore checks remain separate from the frontend demo. A catalogue entry never gains these shortcuts from its title or emulator name alone.

`native/nova-library.patch` contains all tracked native modifications and the previously untracked C++, Java, fixture, and test sources from the Nova native worktree. Its base is pinned in [native/upstream.json](native/upstream.json). To check and apply it to a separate clean checkout:

```sh
git clone https://github.com/mmatyas/pegasus-frontend.git pegasus-source
git -C pegasus-source checkout 5d58223e58f84afb31d5d14a67438841b981a6fa
python3 tools/check_native_patch.py pegasus-source
git -C pegasus-source apply ../native/nova-library.patch
```

Run these commands from this repository's root. The checker is read-only and rejects the wrong base or dirty checkout. It does not download dependencies or change the upstream source tree. The bridge's Qt test project is included in the patch. The [paired-source and Android review-build recipe](docs/BUILDING.md) prepares a fresh native tree plus its matching external theme and checks packaged native inclusion. It requires a provisioned Qt Android toolchain; it is not a turnkey installer, existing-device update or public binary release.

The patch adds SQLite-backed offline actions, snapshot validation, conflict retention, optional synchronization, Android credential storage, and Linux Secret Service integration. The private server implementation, enrollment, tokens, inventories and user ledger are deliberately absent. No service is required for the theme or synthetic demo. Sync requires a compatible service and separately provisioned device capability; this repository is not a turnkey server deployment.

## Check the source

```sh
python3 -m unittest discover -s tests -v
node --test tests/*.cjs
python3 tools/privacy_scan.py
python3 tools/smoke_demo.py
```

Python checks and demo/build tooling use only the standard library. The optional platform-vector regeneration step, `uv run tools/make_platform_marks.py`, pins the build-time `fonttools` parser; generated paths are already included, with no application dependency. JavaScript helper tests need Node 18+. The optional QML smoke requires the Qt runner; use `--qml /path/to/qml` and repeatable `--import-path /path/to/modules` if your installation does not put them in the default paths. It runs an isolated offscreen synthetic copy (`--platform cocoa` for a macOS Qt without offscreen support) and never launches a game or touches your catalogue. The privacy scan is a publication guard, not a guarantee that every private detail can be recognized; review the full diff before publishing.

## Provenance and distribution

Nova interface and repository tooling: Maxwell Young, 2026. Pegasus native source: the Pegasus contributors. The native modifications and Nova source are distributed under GPL-3.0-or-later with the preserved Pegasus supplementary terms in [LICENSE.md](LICENSE.md). See [PROVENANCE.md](PROVENANCE.md) for the precise boundary.

This is an early source release. No APK, ROM, commercial cover art, private library or credential is included. Before distributing a modified native binary, replace upstream Pegasus title/logo assets in accordance with its supplementary license terms and provide the complete matching source, dependency notices and build instructions. Applying a patch does not prove a binary was built from it.

Storage snapshots, per-device installation cues and the compact Info flow are described in [Installation observations](docs/installation-observations.md).
