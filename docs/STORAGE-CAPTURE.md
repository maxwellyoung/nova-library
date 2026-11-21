# Read-only capacity capture

`tools/collect_storage.py` captures internal and portable public-volume capacity
through an existing authorized ADB connection. It does not install anything,
change settings, inspect private app directories, enumerate games or remove data.
Use an explicit enrolled device and a **new private file outside repositories**:

```sh
python3 tools/collect_storage.py --serial "$NOVA_SERIAL" --output "$PRIVATE_CAPTURE_FILE"
```

To include microSD, first identify that card's filesystem UUID on the actual
device and add `--sd-uuid "$NOVA_CARD_UUID"`. Without that explicit enrollment,
the card stays unmeasured: a generic public volume could instead be a USB drive.
The pin is an operator selection, not independent proof of physical card identity.

The output's parent must already exist. The file is created exclusively with
mode 0600; an existing capture is never replaced. It includes the matched device
serial and selected card UUID and stays private. A successful command may still report unmeasured
volumes; inspect `errors` rather than interpreting an absent row as zero usage.

## What is measured

The collector checks `getprop ro.serialno` against the supplied serial before
reading capacity. `df -k /data` supplies internal capacity. The table must state
1 KiB units, a single row, valid integer arithmetic and the expected mount.
Total, used and available values are multiplied by 1024. Available bytes become
the UI's `free` value. Any difference between total and used plus available stays
unavailable capacity, without an invented explanation.

For microSD, `sm list-volumes public` must show exactly one mounted public volume
matching the explicitly selected filesystem UUID. The collector reads that specific mount, then checks
discovery again. Changed/removed cards, fallback to another mount, stderr,
timeouts, ambiguous cards and unsupported output stay unmeasured. A read-only
mounted card can supply capacity; it gains no install or write capability.
Adopted/private volumes, unsupported UUID formats and other storage roles need
their own adapters. There is no inference from a directory merely existing.

Each successful reading retains its own UTC capture time. A partial internal
reading does not discard a valid card reading, or vice versa. No category
breakdown is emitted: filesystem capacity does not tell us how much belongs to
games, apps, caches or saves. Logical ROM sizes are never subtracted from it.

## Exporter integration

`capture(reader, expected_serial)` accepts the existing shell-reader interface
`shell(command, timeout) -> (exit_code, stdout, stderr)`. Its fixed read commands
are bounded and no captured text is executed. `catalogue_fields(report,
expected_serial)` revalidates producer, device identity, unique roles, byte
arithmetic, plain source labels and nonfuture canonical capture times. It returns
`storage_volumes` plus an identical internal-only `storage_volume` for older
readers, without the device serial or card UUID.

An exporter can emit these as `x-storage-volumes` and `x-storage-volume` on one
existing metadata carrier. Do not sum duplicate legacy/new readings or refresh
their dates at export time. An ambiguous/missing carrier must be resolved rather
than silently assigning capacity to an arbitrary game. Preserve the previous
catalogue if validation fails, using the exporter's publication boundary.

The producer name and serial check constrain this operator workflow; they are
not cryptographic authentication of imported JSON. A source file claiming this
producer still needs a trusted capture path. The capture adds no persistent
Android permission, service, periodic scan or cleanup authority. Before a write
or installation, remeasure capacity and perform its separate preflight.

## Verification boundary

```sh
python3 -m unittest discover -s tests -p test_collect_storage.py -v
```

These checks use a fake shell reader. They verify units, exact mounts, partial
reads, card swaps, unknown versus zero, identity, date/provenance validation and
private output preservation. They do not establish the physical device's current
capacity or its exact shell output. Reconcile actual internal/card readings with
the device and the Storage screen before accepting the device feature.
