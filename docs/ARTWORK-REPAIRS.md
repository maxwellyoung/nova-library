# Durable cover repairs

`tools/artwork_overrides.py` supplies an exporter-side repair step. It is not an
on-device editor, scraper or catalogue publisher. No network access is needed.
Call `apply_repairs(records, repairs, input_root, output_root)` after ordinary
artwork collection and before publishing catalogue metadata. Both roots must
already exist. Records need a stable `edition` and an optional `art` path.

```json
{
  "demo:orbit-us": {
    "path": "repairs/orbit-cover.png",
    "sha256": "<64 lowercase hex characters from the selected image>",
    "source": "Manual selection: edition cover from its publisher",
    "mode": "replace"
  }
}
```

Choose the edition explicitly. `replace` corrects an existing banner or cover;
`fill` acts only when artwork is absent. Similar titles, another region or
another edition never inherit the repair. An absent edition keeps its manifest
entry for a later refresh. A duplicate matching edition is an error.

The source citation must describe the actual image origin; it is operator
supplied, not independently verified. Keep private paths and credentials out of
citations. The helper pins exact file bytes, checks a PNG/JPEG/WebP signature and
matching extension, and limits each image to 1 MiB and applicable images together
to 32 MiB. Signature checks do not prove successful decoding, appropriate edition,
visual quality, licensing or permission to redistribute.

All applicable input repairs and existing output targets are validated before
copying. Images use edition-and-content-addressed names under `art/`. Neither a
new correction nor an interrupted export overwrites bytes behind the old cover
path. Existing conflicting assets and symlinked output targets are refused.
An I/O failure can leave unreferenced new assets; it does not change records.
The caller still owns atomic catalogue publication and must not publish on error.
Run exports serially; this helper is not a cross-process publication lock.

Successful records retain `artwork_source` and `artwork_sha256`, alongside their
new `art` path. A Pegasus exporter can emit these as `x-artwork-source` and
`x-artwork-sha256`; the theme currently has no repair editor or dedicated
provenance display. Rebuild every refresh from upstream records, then reapply
the saved manifest. Removing a repair returns to upstream art on the next
refresh; it does not delete any cover files. No save, progress, route or install
field is changed.

Legacy fill-only string overrides belong to the existing exporter adapter.
Keep their old behaviour separate; do not silently reinterpret a string as
permission to replace an existing image or invent a citation for it.

Check the helper with:

```sh
python3 -m unittest discover -s tests -p test_artwork_overrides.py -v
```

These tests use generated art and check two fresh-catalogue refreshes, exact
identity, unaffected records/assets, byte drift and failure preservation.
Product acceptance still needs the actual refreshed catalogue on the device.
