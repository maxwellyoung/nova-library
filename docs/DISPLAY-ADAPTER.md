# Reversible edition display configs

`tools/retroarch_display.py` is a host-only foundation for RetroArch Android AArch64 **1.22.2**, source commit `69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`. It creates private configs for individual game/edition IDs, previews exact display changes, requires confirmation, retains backups, and supports revert/recovery. It never launches RetroArch, writes the existing emulator profile, changes device settings, or runs imported text as commands. Current installed runtime identity and visible behavior remain unverified.

## Real adapter point and capabilities

The pinned Android frontend reads the `CONFIGFILE` intent extra into its config path. Nova's existing cloud launcher already supplies that extra. A future launch integration can select a confirmed edition config instead of the global config; this tool does not edit the launcher, copy anything onto Android, or supply a shell command. Its returned `configPath` is a **local host artifact**, not an Android-accessible path.

Automatic game overrides are keyed by core name plus ROM basename, so two editions with the same basename can collide. This adapter uses a separate config generation under the hash of both stable game and edition IDs. It requires a reviewed flat baseline with `auto_overrides_enable = "false"` and `config_save_on_exit = "false"` already set. It refuses includes, duplicate keys, unknown syntax and ambiguous precedence. It does not silently disable another profile's overrides or save behavior. Effective controls/save/core settings must be reviewed in that baseline before any future device use. Manual runtime config edits remain outside the transaction and are detected by hash on the next operation.

| Mode | Available | Exact meaning/settings |
|---|---|---|
| Native | No | One-to-one pixels require measured core output geometry and scene/driver proof |
| Fit | Yes, source-supported | Core-provided aspect (`aspect_ratio_index=22`), aspect enforcement on, integer scaling off, centered viewport |
| Fill | Yes, source-supported | Full viewport (`aspect_ratio_index=24`), aspect enforcement off, integer scaling off, centered viewport; image may stretch |
| Crop | No | Aspect-preserving fill/crop needs measured geometry and clipping acceptance; overscan and integer overscale are not substitutes |

The five changed keys are allowlisted. Aspect indices are fixed at 22/24, booleans at true/false, and viewport biases at 0.5. Existing values are validated within their supported bounds before preview. The adapter never infers that a descriptive 4:3 receipt is a setting, that a core-provided aspect is necessarily 4:3, or that source-supported Fit proves the actual scene is uncropped. Core-specific overscan/shader behavior is preserved and needs separate observation.

Source references: [aspect enum](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/gfx/video_defines.h#L39), [core/full aspect selection and viewport scaling](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/gfx/video_driver.c#L2058), [recognized config keys](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/configuration.c#L1888), [Android CONFIGFILE](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/frontend/drivers/platform_unix.c#L1428), [override precedence and basename scope](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/configuration.c#L4559).

## API

```python
from retroarch_display import Store, RUNTIME

store = Store.create('/private/existing-parent/new-display-workspace')
plan = store.preview(RUNTIME, 'game-a', 'edition-us', 'fit', baseline_bytes)
# Show plan['changes']; wait for the user's explicit confirmation of plan['token'].
selected = store.confirm(plan, confirmed_token, baseline_bytes)

# A fresh process reopens persisted preference, with the same game+edition identity.
selected = Store(store.root).current('game-a', 'edition-us')
plan = store.preview_revert(RUNTIME, 'game-a', 'edition-us')
restored = store.confirm(plan, confirmed_revert_token)
```

Only the exact supported runtime descriptor is accepted. It describes source support, **not an attestation of an installed APK**; returned status explicitly keeps `installedRuntimeVerified` and `deviceApplied` false. Unknown versions, package identities or source commits refuse. A real device adapter must refresh installed APK/signature/version/core identity and bind it to the reviewed source contract before selecting these files.

The first choice takes a baseline; subsequent choices use the existing edition's private config and reject replacement baselines. Every preview is read-only and binds identity, current generation, before/after hashes, bounded display deltas, and a 60-second confirmation token. A changed baseline, stale preference, modified plan, expiry or backwards clock change refuses. Both changing mode and reverting require their own preview/confirmation.

`recipe(game, edition)` exports only the versioned source/runtime descriptor, stable IDs, mode and canonical five-key settings. It excludes full configs, save paths, account data and executable commands. `import_recipe(bytes)` validates data only; `preview_recipe(bytes, baseline=None)` produces a read-only plan that still requires explicit confirmation. Unknown fields/settings, duplicates, NaN, path-like IDs and descriptive aspect receipts refuse. Arbitrary RetroArch config files are not portable recipe imports.

## Host CLI

Keep baseline configs and workspaces outside Git checkouts; profiles can contain credentials. The tool refuses creating/opening a workspace inside a Git checkout, creates its root 0700 and files 0600, and never prints baseline contents. Use a new directory under an existing private parent.

```sh
python3 tools/retroarch_display.py capabilities
python3 tools/retroarch_display.py init /private/parent/new-display
python3 tools/retroarch_display.py preview /private/parent/new-display --runtime /private/runtime.json --game game-a --edition edition-us --mode fit --baseline /private/reviewed-flat.cfg
python3 tools/retroarch_display.py confirm /private/parent/new-display --plan /private/preview.json --token EXACT_REVIEWED_TOKEN --baseline /private/reviewed-flat.cfg
python3 tools/retroarch_display.py current /private/parent/new-display --game game-a --edition edition-us
python3 tools/retroarch_display.py preview-revert /private/parent/new-display --runtime /private/runtime.json --game game-a --edition edition-us
python3 tools/retroarch_display.py recipe /private/parent/new-display --game game-a --edition edition-us
python3 tools/retroarch_display.py preview-recipe /private/parent/new-display --recipe /private/recipe.json
python3 tools/retroarch_display.py recover /private/parent/new-display
```

Save the displayed plan as private JSON before `confirm`; it contains only bounded display deltas and identities. `runtime.json` must exactly equal the source-supported descriptor printed by `capabilities`; copying that descriptor does not verify a device. A preview/recipe never confirms itself or applies runtime settings.

## Transaction and recovery

Configs and their receipts are written to new generation directories and synced before the active selection changes. The original baseline is retained byte-for-byte as its own generation; every confirmed choice keeps its previous generation. Selecting a completed generation is one atomic pointer replacement, so preference and config cannot become mismatched across separate writes. No existing config bytes are overwritten. Revert selects the previous verified generation, retaining the abandoned choice as well.

A durable journal records the selection before/after a switch. Interrupted work blocks all normal operations until explicit `recover`. Recovery validates both generations and restores the prior selection; a process crash after the completed commit leaves a consistent new selection. If rollback itself cannot write, the journal remains and success is not reported; retry recovery once storage is writable. If a third party changed the active selection/config, recovery refuses to overwrite it. Incomplete/unselected generation files are retained for inspection; no recursive cleanup is performed.

The workspace lock is bounded/nonblocking. Symlinked entries, hardlinked files, corrupted metadata, missing backups and unrecognized runtime/config values refuse. This is a private local transaction under one trusted host user, not a defense against a malicious process running as that same user. A caller must honor any failed/unknown result and must not bypass the journal.

## Verification and remaining gate

```sh
python3 -m unittest discover -s tests -p 'test_retroarch_display.py' -v
```

Tests use disposable bytes only. They cover edition isolation, restart persistence, exact baseline restoration, stale/expired confirmation, malformed/imported data, linked files, busy locks, write/rollback failures, and abrupt real process death before/after selection with fresh-process recovery. Existing sync/session tools were inspected and left unchanged; their candidate/source-patch semantics do not provide this edition config transaction.

The remaining device gate requires separately authorized staging/CONFIGFILE integration, fresh actual runtime/source/core identity, safe stopped-runtime selection, screenshots of real Fit/Fill scenes, explicit visible choice/revert, restart persistence, recovery to previous settings, and one separately evidenced genuine native 4:3 scene. No source fixture or numeric setting receipt closes that gate. No current emulator settings, saves, permissions or device state were changed by this foundation.
