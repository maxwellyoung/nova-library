# PC runtime choice

The optional native PC adapter lets Nova send a Steam game directly to a selected
runtime. It does not replace DroidDeck/GameNative or their compatibility stack.

Open a Steam edition's **Details → PC runtime**. Each row describes the app's
availability and observed version, not whether the game is installed there.
Select a supported row with A to request that game. The choice is remembered for
that edition after accepted dispatch; future A actions say **Open in DroidDeck**
or **Open in GameNative**. The runtime handles installation and setup if needed.

A changed version needs review. Nothing silently selects another runtime.
**Existing shortcut** explicitly uses the catalogue route and clears the separate
choice. **Forget runtime choice** removes only that preference. B returns to the
originating game, or its Details. X refreshes app observations.

GameNative 1.4.0 and DroidDeck 0.7.0 protocols are checked in source. Their installed
versions, signers and actual behaviour still need device verification. Other
versions stay visible with Needs adapter check. Missing adapter builds retain the
older shortcuts; a stored choice remains visible for review instead of becoming
an invisible fallback.

No game-ready label, compatibility pass, play time or ROM tracking entry is
created by a successful Android request. Controls, aspect ratio and saves still
need edition/runtime-specific checks. See the [adapter contract and build
instructions](../native/pcgames/README.md) and [compatibility evidence](COMPATIBILITY.md).
