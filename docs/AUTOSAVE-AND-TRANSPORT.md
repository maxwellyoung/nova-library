# Local automatic saves and immutable save transport

Local automatic writes, retained backups, uploads and verified restore are separate
facts. This source adds a private RetroArch profile preparer and a real durable
save transport. Neither changes an installed emulator, restores a live save,
enables a background job or deploys a service.

## RetroArch profile

`tools/retroarch_autosave.py` targets the same source descriptor as the existing
display adapter: Android AArch64 1.22.2, commit
`69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576`. Its reviewed delta is:

- `autosave_interval = "30"`: periodically flush core-exposed nonvolatile memory.
  This preserves memory the game/core has already written; it does not invent an
  in-game checkpoint or periodically capture the full emulated machine.
- `savestate_auto_save = "true"`: request the automatic state on a supported clean
  content exit. A force-stop, crash or battery loss is not a clean exit.
- `savestate_auto_load = "false"`: retain the state for deliberate review; never
  load an incompatible state automatically after a core/version change.

Source: [interval semantics](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/retroarch.cfg#L913)
and [automatic state semantics](https://github.com/libretro/RetroArch/blob/69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576/retroarch.cfg#L7).
Core support, effective overrides and actual device behaviour still require checks.
The auto slot can replace an older auto state; preserve an independent checkpoint
and native saves before enabling it. Manual slot indexing, hotkeys, save paths,
input, cloud settings and core options remain unchanged.

Preparation requires an explicitly flat config with overrides and config-write-on-
exit already disabled. Includes, duplicate keys, unknown syntax and unsupported
runtime descriptors refuse. These requirements prevent a candidate from pretending
it represents effective settings while another override can supersede them.

```
python3 tools/retroarch_autosave.py prepare --baseline /private/reviewed.cfg \
  --parent /private/profiles --name edition-a --edition fixture:edition
python3 tools/retroarch_autosave.py verify /private/profiles/edition-a
```

The new owner-only folder retains exact baseline/candidate bytes, their hashes,
explicit deltas and a completion marker. An interrupted folder is not deployable.
No current config is replaced. Restore uses the retained baseline after separately
reviewing the actual target. `--display-mode fit|fill` composes the existing exact-
version display adapter with the autosave delta in one candidate; this is not proof
of native 4:3 rendering or an implemented on-device mode picker.

## Durable transport

`tools/save_vault.py` connects the existing [save-sync model](SAVE-SYNC-MODEL.md)
to a real SQLite archive store and authenticated HTTP client/server. The SQLite
transaction owns the immutable archive, exact revision metadata and idempotent
acceptance. A retry after a lost reply cannot replace a revision or add another
copy. Parent revisions must already exist in the same exact identity scope.
Two children remain separate heads; timestamps do not select a winner.

The server verifies the full passport and archive/payload hashes before commit.
Inventory and range downloads are scoped by exact identity/revision IDs. The
client refuses redirects and only accepts HTTPS or HTTP on 127.0.0.1. Downloads
still pass the model's complete checksum/identity verification and F07 catalogue
import before deliberate new-directory staging. Transport acceptance is not a
live restore or a claim that a state can be loaded by its emulator.

The service binds only 127.0.0.1. A private token file supplies authentication;
no credentials belong in source, command arguments, output or logs. There is no
CORS policy, auto-start, public route, external enrollment or deployment script.
A separately approved private proxy/service configuration is required for another
machine to reach it. Never expose this development server to the public internet.

```
python3 tools/save_vault.py init /private/new-save-vault
NOVA_SAVE_TOKEN_FILE=/private/reviewed-token-file \
  python3 tools/save_vault.py serve /private/new-save-vault --port 8768
```

Do not run a persistent service until its exact deployment is approved. The
caller owns shutdown. The current bounds are 64 MiB per archive, 4,096 revisions
and 1 GiB total archive bytes. Full capacity refuses new uploads without deleting
history. This version has no retention deletion, state conversion or migration of
an older vault schema.

**The service explicitly reports `loadGuard: false` and `automaticRestore: false`.**
It does not implement the pre-content remote-head guard or a trusted emulator
import/idle boundary. Automatic cloud restore remains disabled. An archive can be
uploaded, fetched, verified and staged while that boundary is being built; neither
WebDAV nor a last-second timestamp comparison substitutes for it.

Tests exercise real loopback HTTP, authentication refusal, durable reopen,
idempotent retry, range resume after model restart, divergent branches, corruption,
actual F07 catalogue import and new-directory payload staging. They use synthetic
saves and do not establish native memory-card import or on-device autosaves.
