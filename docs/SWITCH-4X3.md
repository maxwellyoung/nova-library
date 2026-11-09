# Switch 4:3 patches

Switch setup is not yet device-verified. A console icon is not an emulator, and a
patch catalogue is not a compatibility result. Start from an exact emulator APK,
program ID, installed game version and NSO build ID, with current saves protected.
No emulator or game files are installed by the source tools described here.

## Source references

The [4:3 mod collection](https://github.com/JalenJaceX2/4x3-Aspect-Ratio-Mods/tree/b70d1ff148978775450a279fc3462cfd0800a539)
contains IPSwitch `.pchtxt` files for individual game builds. Its author explicitly
says not all have been tested. Preserve the original attribution and bytes; this
project does not redistribute the collection. Some patches request the emulator's
stretch-to-window setting after modifying the game's projection. That combination
may produce a correctly proportioned 4:3 scene; the stretch setting alone does not
prove it. HUD, menus, cutscenes, clipping and performance need separate checks.

Eden v0.2.1, source commit `58c1e20ee58efa3900ba616207d460886214480b`,
collects enabled per-program mod directories' `exefs` files and compares their
IPSwitch NSO build IDs before applying them. See its
[patch manager](https://git.eden-emu.dev/eden-emu/eden/src/commit/58c1e20ee58efa3900ba616207d460886214480b/src/core/file_sys/patch_manager.cpp)
and [case-sensitive IPSwitch parser](https://git.eden-emu.dev/eden-emu/eden/src/commit/58c1e20ee58efa3900ba616207d460886214480b/src/core/file_sys/ips_layer.cpp).
Short build IDs are padded on the right to 32 bytes, not compared by title alone.
Source inspection is not an APK or device verification receipt.

## Read-only audit

```
python3 tools/switch_patch_audit.py /private/mod/exefs/1.0.0.pchtxt
python3 tools/switch_patch_audit.py /private/mod/exefs/1.0.0.pchtxt \
  --program-id 0100000000001000 --game-version 1.0.0 \
  --build-id A1A1A1A1A1A1A1A1A1A1A1A1A1A1A1A1
```

The example identity is synthetic. Use observed IDs from the actual game;
a filename or downloaded patch is not evidence of the installed build.
The tool reads at most 64 KiB and prints a metadata report. It never downloads,
installs, edits, compiles, executes or enables a patch, emulator, driver or ROM.
It accepts a deliberately narrow hex-write subset, flags conflicting/overlapping
writes and unsupported or mis-capitalised directives, and checks declared program
ID, filename game version and build ID independently. Unsupported syntax means
review required, not that every such mod is invalid in every emulator.

`sourceCandidate: true` means only that declared identities match and this audit
found no issue in the supported subset. It does not validate intended instruction
semantics, patch safety, the source author's identity, the game or APK bytes,
other installed mods, visual results, controls or saves. The audit does not emulate
the whole IPSwitch parser or certify a patch. Output always leaves device and
gameplay verification false. Warnings and the original notes still require review.

Exit status is 0 for a clean source audit/match, 1 for an issue/mismatch, and 2 for
refused input. A missing program ID is never filled from a similar game title.
Separate variants remain separate candidates; this tool does not choose or combine
them. It cannot inspect the emulator's private live mod state.

## Prepared collection findings

At the pinned collection revision, Smash Bros. Ultimate 13.0.4 has two different
writes at the same offset. Brothership 1.0.0 uses `@Flag`/`@Stop`, while the pinned
Eden parser recognises lowercase directives. Captain Toad lacks a declared program
ID in its patch comments. These need review rather than automatic correction.
Fire Emblem has two variants with documented HUD/camera compromises; Xenoblade
warns about its HUD; Echoes of Wisdom has inconsistent aspect descriptions.
None supplies a tested 4:3 result on a particular handheld.

## Device gate and reversal

At an available, approved device window, refresh installed emulator/version/signer,
GPU/driver and exact game build. Take fresh backups before changing an existing
setup. Import one reviewed matching mod through the emulator's supported per-game
mod UI, preserving all other mod states and settings. Use its actual chosen user
folder rather than assuming an app-private or shared-storage path. Verify the
patch appears and is enabled for the intended program/build, then compare the same
scene with the patch off and on. Check HUD, menus, cutscenes, viewport proportions,
physical controls, sound, save/reopen, offline launch and return to Library.

Reversal disables only that exact mod and restores the recorded per-game display
setting, while leaving original game files and saves unchanged. Do not delete a
mod tree or reset an emulator profile to undo one patch. Keep new compatibility
recipes and actual render observations separate from this source audit. The
existing [Checks model](COMPATIBILITY.md) can hold an observed 4:3 result after
these gates; no patch availability flag should fabricate one.
