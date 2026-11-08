# Private RomM deployment candidate

`compose.yaml` pins RomM 5.4.1 and MariaDB 11.4, binds HTTP to loopback, mounts the ROM collection read-only, and separates database/resources and writable save storage. Hasheous is disabled and no other provider credentials are configured. Upstream always enables Libretro artwork, so its endpoint is mapped to container loopback during initial setup; its enabled flag remains visible but it cannot contact the provider. This is a provider-specific block, not general egress isolation. It preserves the existing progress-sync service. Deployment and live verification are recorded separately from this reusable definition.

Supply an owner-only environment file outside the repository with `ROMM_DB_PASSWORD`, `ROMM_DB_ROOT_PASSWORD`, `ROMM_AUTH_SECRET_KEY`, `ROMM_LIBRARY_PATH`, `ROMM_STATE_PATH`, and optionally `ROMM_PORT`. Use the official library folder structure. Set up a private HTTPS Tailscale route only after approval; do not expose the port publicly. Do not add a shared Steam credential or reuse the progress-ledger capability.

When Docker runs in a VM, verify that both host paths resolve to the actual host folders inside that VM before starting the service. Share only the library read-only and state writable; the environment file and secret folder stay outside VM shares. Adding mounts to an existing shared VM can require a restart and separate approval for its other services.

Before enabling saves, back up assets and the database independently, create the intended private account, scan file hashes, retain original M3U names, and test using a copied memory card. Automatic save synchronization remains disabled until the RetroArch launch-order barrier and restore tests pass. Other emulators need separate tested save adapters.

References:
- https://github.com/rommapp/romm/tree/5.4.1
- https://docs.romm.app/5.4.0/ecosystem/retroarch-cloud-sync/
- https://docs.romm.app/5.4.0/using/saves-and-states/

Deployment, persistent route creation, account enrollment and actual save access require current approval for this service. Source preparation and synthetic checks do not establish live operation.
