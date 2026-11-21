# Disc continuity and swap help

An explicit disc set appears as one browse entry. **Play** opens the existing picker: its default comes from the most recent local opening, or the lowest disc number when there is no local history. Selecting an available member sends that exact edition's launch request. It does not swap the disc in an already running emulator. Cancellation and reading help do not supply new launch history.

Press the mapped **Details/X → Swap help** from the picker, or tap that footer action. The read-only panel follows the selected disc's declared route. Back returns to the same picker row; a second Back returns to its original Library or Details parent. Android Back uses the same reverse path on release. No game is launched by opening or reading help.

For a declared RetroArch route, the guide separates a disc already listed by the active runtime from an image that must be added through the runtime's file selector. It never assumes that both discs are in an active M3U, that a declared group is installed completely, or that the loaded core supports Disc Control. Unknown runtime routes get an explicit unsupported/unverified fallback. The same guidance appears in Controls for explicit disc sets and the original PlayStation Metal Gear Solid guide.

The MGS-specific RGUI eject-detection workaround is labelled with that menu/core limitation. It is not offered to unrelated disc games, and no title match supplies a universal RetroArch shortcut. The static guide contains no automatic save, swap, restart, memory-card rename, configuration write or download.

Sources, reviewed for the conditional guidance:

- [Libretro: Disc swapping](https://docs.libretro.com/guides/disc-swapping/): runtime disc index, adding images, M3U and the RGUI/MGS eject-detection issue.
- [Libretro: Disc images](https://docs.libretro.com/guides/disc-images/): disc image/container and playlist context.

These documents describe runtime behaviour; they do not establish the contents of a user's playlist, their memory-card mapping or successful progress continuity. Check those on the exact device/runtime before treating a swap as verified. Keep the current session and protect progress rather than restarting a title or changing save names to guess at a fix.

## Evidence boundary

The selector retains member IDs, routes, progress and missing-file state. Same-title entries without an explicit compatible set stay separate. An unavailable latest disc remains labelled unavailable; the picker does not silently launch another disc instead.

```sh
node --test tests/guides.test.cjs tests/library.test.cjs
python3 tools/smoke_discs.py --host /path/to/existing-theme-host \
  --bundle /path/to/synthetic-save-copy-fixture --output /path/to/new-evidence
```

The runtime fixture uses generated artwork and non-executable catalogue markers. Its dispatch callback records an edition ID instead of launching a program. It exercises default/cancel/help/Back and supplied local-history refresh; it cannot establish a real emulator swap, shared memory-card setup, physical controls or save preservation. Those remain separate device acceptance gates.
