# Pinned analog input excerpt

`input_joypad_axis.inc` is the unchanged `input_joypad_axis` function from Libretro
RetroArch at the exact commit and source-file SHA in `source.json`.
`source-notice.txt` retains that file's original GPL-3.0-or-later notice. The
excerpt is not a separate Nova input implementation or a full emulator build.

`tests/test_retroarch_input.py` verifies the excerpt's SHA and compiles it with a
synthetic axis callback to exercise translated preferences. Config registration,
full source hashes and the original Android CONFIGFILE reader are independently
retained in the private review evidence. See [the adapter boundaries](../../docs/RETROARCH-INPUT.md).
