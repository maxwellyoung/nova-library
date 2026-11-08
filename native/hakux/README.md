# HakuX session adapter

A source-level controller adapter for **HakuX 1.2.0**, pinned by `source.json`. It reuses that version's existing native SaveStates implementation. It does not modify the native emulation core, ROM, native save format, storage permissions or network configuration.

Hold Select and press R1 to save, L1 to load, L3/R3 to change the selected slot, or Y for the emulator menu. Tap Select alone to send Xbox Back. The menu's **Controller shortcuts** entry explains the controls and switches them off if a game needs the modifier combinations.

A quick save uses an empty slot at or after the selected slot. When all ten slots are occupied, replacing the selected slot asks first. Quick load loads the selected existing checkpoint; an empty slot produces an explanation. Slots persist per game. Manual save/load remains available in the original menu. The adapter does not implement automatic saves, cloud sync or an undo-load state.

Legacy checkpoints keyed by the disc URI are copied as bundles: supporting cache blobs are verified before a state is published. Existing destination checkpoints take precedence, and conflicting files or links prevent promotion. Copies are published without replacing a concurrently arriving file. The old directory is retained for recovery; this can use additional storage. No automatic legacy cleanup is included. This prevents migration from separating a state from its cache, but does not establish that the saved native state itself is compatible or playable.

## Apply to upstream source

Start with the complete upstream HakuX checkout at the commit in `source.json`, including its matching mods and original native libraries. From this Nova repository:

```sh
python3 tools/apply_hakux_session.py /path/to/hakux --backup /path/to/new/backup
```

The tool rejects changed inputs, verifies its patch/helpers, keeps a rollback copy and verifies the result. A second application to the identical result makes no changes. Other upstream versions require a reviewed port.

Use HakuX's pinned Gradle wrapper and JDK 21. Run `testReleaseUnitTest assembleRelease` from its Android project. The upstream build requires matching prebuilt native libraries; this adapter does not download or rebuild them. Preserve their provenance and hashes. Optional Gradle properties allow a separate package without changing source:

- `novaApplicationId`, `novaVersionCode`, `novaVersionName`, `novaAppName`
- `novaBuildTools` when the chosen installed SDK build-tools version differs

If upstream's Gradle properties point at a different Java installation, pass `-Dorg.gradle.java.home=/path/to/jdk21`. Sign the resulting APK with the intended package's existing signer before considering an update. This repository distributes source only and grants no authority to install, publish or replace an existing app.

## Evidence and limits

The input/slot suite covers repeated/canceled keys, device isolation, shoulder release order, focus/disconnect reset, normal input and empty/full slot selection. The source integration goes through the native activity's real dispatch and existing save/load methods. A passing JVM test and Android build do not establish physical button behavior or native save-state compatibility.

`SaveStateStoreTest.kt` exercises the actual store with temporary filesystem roots: state/blob/original preservation, destination precedence, conflicting blobs, linked paths, thumbnail conflicts, repeat adoption and invalid folder keys. Its internal filesystem constructor shares the Android constructor's implementation and only substitutes the root and migration logger. These fixtures are synthetic; the suite does not import a real save or run the emulation core.

Before using it with real progress: export the **currently installed compatibility app's** saves/states; check package and signer; exercise a disposable state through save → move → load → exit → reopen, including Select alone, repeats, full-slot replacement cancellation and ordinary game controls. Never replace the original official app or migrate an existing profile incidentally.

The frontend's optional `x-session-profile: hakux-nova-v1` selects this adapter's guide. It must not be added to a live catalogue merely because an APK was built; install, enabled-setting and hardware checks come first. The default HakuX guide retains its existing menu path.

These changes apply only to HakuX's Java/Kotlin frontend. Pegasus, RetroArch and other standalone emulators retain their own adapters and verification gates. The upstream HakuX source and this derived patch retain its GPL obligations; an eventual binary release needs the complete matching source and notices.
