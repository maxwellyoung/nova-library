# Nova

A quiet, controller-first library for a handheld: a Home shelf, a searchable index, consoles, and collections. Covers keep their shape. Missing artwork gets a title. A game becomes playable only when its catalogue marks a local route and the runtime still sees its file. Unknown progress stays unknown.

Nova is a custom QML frontend **built on Pegasus Frontend**. The engine, game discovery, controller integration, launching, and much of the native application come from [Pegasus Frontend](https://github.com/mmatyas/pegasus-frontend). This repository contains the original Nova interface and a complete source patch for its optional native personal-library bridge; it is not a new native engine.

## Try the synthetic demo

The demo has invented titles and original generated SVG covers, without ROMs, accounts, network access or launch commands. It loads the same QML interface as the theme through a small mock of the Pegasus API. Memory is in-process and resets when the demo closes; personal synchronization and editing are unavailable.

Requirements: Python 3.10+ and a Qt 5.15+ or Qt 6 installation with QtQuick, QtQml, QtQuick.Window and its `qml` runner.

```sh
python3 tools/make_demo.py
qml demo/Demo.qml
```

Use arrow keys to move, Enter to select, Escape to return, X for details, Y to favourite a game, and Page Up/Page Down to change screens. Home/End jump within a list. The demo generator is deterministic and refuses to overwrite an existing output directory. A Pegasus metadata catalogue is also generated for testing inside Pegasus itself; all demo entries are non-launchable.

See [validation](docs/VALIDATION.md) for which steps were exercised. A passing helper test or generated demo is not proof of the GUI running on a device.

## Use the theme in Pegasus

Copy the `theme/` directory to a new theme directory in your Pegasus configuration, select **Nova** in Pegasus's theme settings, and point Pegasus at a catalogue containing your own files. Existing themes and catalogue settings need not be replaced. The theme uses the runtime's system font; no third-party font binaries are bundled.

Plain Pegasus can display the theme, browse, filter, and keep games in theme memory. The optional `deviceLibrary` bridge adds durable personal progress and collections. The demo makes no claim that a file exists on a real device. See [the metadata contract](docs/CATALOGUE.md) when producing your own catalogue.

## Native source

`native/nova-library.patch` contains all tracked native modifications and the previously untracked C++, Java, fixture, and test sources from the Nova native worktree. Its base is pinned in [native/upstream.json](native/upstream.json). To check and apply it to a separate clean checkout:

```sh
git clone https://github.com/mmatyas/pegasus-frontend.git pegasus-source
git -C pegasus-source checkout 5d58223e58f84afb31d5d14a67438841b981a6fa
python3 tools/check_native_patch.py pegasus-source
git -C pegasus-source apply ../native/nova-library.patch
```

Run these commands from this repository's root. The checker is read-only and rejects the wrong base or dirty checkout. It does not download dependencies or change the upstream source tree. Fetch upstream submodules and build using the upstream instructions for that exact revision; this repository does not provide a verified portable Android build recipe. The bridge's Qt test project is included in the patch.

The patch adds SQLite-backed offline actions, snapshot validation, conflict retention, optional synchronization, Android credential storage, and Linux Secret Service integration. The private server implementation, enrollment, tokens, inventories and user ledger are deliberately absent. No service is required for the theme or synthetic demo. Sync requires a compatible service and separately provisioned device capability; this repository is not a turnkey server deployment.

## Check the source

```sh
python3 -m unittest discover -s tests -v
node --test tests/library.test.cjs
python3 tools/privacy_scan.py
python3 tools/smoke_demo.py
```

Python tooling uses only the standard library. JavaScript helper tests need Node 18+. The optional QML smoke requires the Qt runner; use `--qml /path/to/qml` and repeatable `--import-path /path/to/modules` if your installation does not put them in the default paths. It runs an isolated offscreen synthetic copy and never launches a game or touches your catalogue. The privacy scan is a publication guard, not a guarantee that every private detail can be recognized; review the full diff before publishing.

## Provenance and distribution

Nova interface and repository tooling: Maxwell Young, 2026. Pegasus native source: the Pegasus contributors. The native modifications and Nova source are distributed under GPL-3.0-or-later with the preserved Pegasus supplementary terms in [LICENSE.md](LICENSE.md). See [PROVENANCE.md](PROVENANCE.md) for the precise boundary.

This is an early source release. No APK, ROM, commercial cover art, private library or credential is included. Before distributing a modified native binary, replace upstream Pegasus title/logo assets in accordance with its supplementary license terms and provide the complete matching source, dependency notices and build instructions. Applying a patch does not prove a binary was built from it.
