# RetroArch disk-load guard candidate

This optional source patch targets only RetroArch 1.22.2 commit
`69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`. `source.json` pins the complete
`tasks/task_save.c`, the resulting file, patch and exact test excerpts.
It is not included in Library's APK or automatically applied to an emulator.

The pinned disk-load callback requests an in-memory undo backup but proceeds to
deserialize without checking the backup result. This patch requires successful
backup before that callback can load. Undo-load likewise requires a successful
backup of the current state before swapping back. A replacement undo buffer must
be allocated before the previous buffer is freed; an empty undo and a failed
temporary allocation refuse. Existing cleanup and SRAM-protection paths remain.

This is an opt-in source-level policy. A failed backup blocks the requested load;
there is no silent unsafe fallback. This can also refuse a recovery load when the
current core cannot serialize. Review that tradeoff before building or using it.
Keeping the previous undo until replacement succeeds also raises peak memory
by roughly one serialized state during that replacement. Test real memory pressure;
this guard cannot prevent an operating-system memory kill.

## Prepare and verify

Obtain the full pinned upstream checkout separately, including its licence and
build dependencies. The helper reads the exact task source into a **new review
directory outside repositories**, retains baseline/candidate bytes, and writes a
completion marker after checking the baseline hash. It never edits upstream:

```sh
python3 tools/prepare_retroarch_safe_load.py prepare \
  --source /path/to/retroarch/tasks/task_save.c --output /path/to/new-review
python3 tools/prepare_retroarch_safe_load.py verify /path/to/new-review
```

Existing output, wrong source, changed patch or changed result refuses. Partial
preparation remains without a completion marker. Files are owner-only. This
verifies one file, not the whole checkout, toolchain, core or resulting binary.
Later builds need the full source/dependencies verified, the existing package,
signer and saves preserved, and reviewed protected installation/rollback tests.

## Limits

The backup is volatile RAM, not a named/durable checkpoint, crash recovery,
automatic disk/cloud save or cross-core conversion. Closing content, restarting
or crashing can lose it. This patch does not protect the separate load-from-RAM,
rewind, replay or other restore paths, or change ordinary disk saving. Successful
deserialization does not prove correct gameplay. A failed deserialize may change
a core; retained bytes permit an explicit undo attempt, not guaranteed recovery.

There is no new launcher acknowledgement/UI, live support probe or fix for the
Library Save copies reader failure. RetroArch's Undo Load State menu depends on
menu/core/Hardcore constraints and needs an installed-build check. Do not advertise
this source guard as installed from a preparation receipt.

## Host verification

`test_driver.c` uses the **exact three function bodies** extracted into
`task_save_fixture.c`, with a fake integer core, allocator/serializer failures and
optional fake SRAM. The original callback reproduces loading despite backup
failure. The guarded functions exercise 14 scenarios including failed backup,
allocation failure, previous-undo retention, load/undo/redo, empty undo,
unsupported core, failed load then undo, and backup-buffer-only behaviour.
This is real C control flow with synthetic endpoints, not an emulated console,
full RetroArch build, Android ABI or physical save-state proof.

```sh
python3 -m unittest discover -s tests -p test_retroarch_safe_load.py -v
```

Use the machine's development admission wrapper for compilation where required.
The suite uses an installed compiler without downloads; absent compiler coverage
is explicitly skipped. Real-core disposable restore/undo, visible failure feedback,
memory pressure, task scheduling, installed versions, ordinary controls and
original-save preservation remain separate gates.

## Provenance

Original source/excerpts: Libretro/RetroArch contributors, GPL-3.0-or-later.
Original copyright/licence notice remains in the excerpts. Nova guard/tooling:
Maxwell Young, GPL-3.0-or-later. No Pegasus resource/trademark grant is supplied.
Preserve matching source and notices for any eventual binary release. Source:
https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/tasks/task_save.c
