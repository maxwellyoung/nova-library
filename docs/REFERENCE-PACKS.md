# Selected reference packs

`tools/reference_pack.py` produces a portable **link index**, containing only
explicitly selected references from an existing CSV catalogue. `index.html` can
be read offline; the linked articles, decks and videos require connectivity.
`pack.json` carries the same selection and provenance for a future adapter.
There are no downloads, transcripts, binaries, images, research claims,
notifications or service writes. No Margin or Nova reader integration is claimed.

The CSV requires `id,title,url,read_status,read_scope`. Extra columns are discarded.
Select exact stable IDs rather than titles or search terms. A selection JSON has
exactly these fields:

```json
{
  "schema": 1,
  "catalogue_sha256": "REPLACE_WITH_EXACT_CATALOGUE_SHA256",
  "catalogue_label": "Public developer reference catalogue",
  "selected_ids": ["selected-source-id"]
}
```

Compute the digest from the exact retained CSV bytes, inspect the selected rows,
then run with portable inputs in a private working directory:

```sh
python3 tools/reference_pack.py --catalogue /private/references.csv \
  --selection /private/selection.json --output /private/new-reference-pack
```

The output directory must be new and have an existing parent. Existing packs are
preserved. Inputs and outputs cannot pass through symlinks. The command validates
the complete selection before writing owner-only JSON/HTML files. Input files are
limited to 1 MiB, catalogues to 4096 rows, selections to 32 unique IDs. Duplicate
columns/IDs/JSON keys, unknown selection fields, missing IDs and changed catalogue
bytes refuse. The tool uses only the Python standard library and makes no network
requests. Tests use synthetic public references only.

Each selected source retains its exact `read_status` and `read_scope`:

- `catalogued`: listed only, never promoted to reviewed.
- `read_partial`: only the stated portion was reviewed by the catalogue owner.
- `read_full`: the whole stated format/scope, which may be captions or a deck and
  may exclude audiovisual demonstrations or spoken presentation.

These are **retained catalogue claims**, not reviews performed by this producer.
The source includes the catalogue label, SHA-256 and record ID. `reviewed_at` stays
null because this catalogue contract supplies no per-item review dates;
`checked_live` is false and `offline_content` is `not_included`. File timestamps
and export dates never become source review dates. Original URL availability,
authorship and permission to download must be checked separately. HTTPS DNS URL
syntax is checked locally; it is not proof that a link is public or accessible.
Credentialed, IP/local-host links, fragments, custom ports and arbitrary query
parameters refuse; public `v`, `t`, `start` and `page` locators are supported.
An unsupported URL is not silently rewritten.

Use a retained source catalogue rather than repeating research. Never point this
producer at mixed private recovery, employer, course-assessment or account exports.
It does not inspect neighbouring files or import extra CSV columns. Keep actual
selections private until separately reviewed for publication.

This is a source/provenance foundation for a chosen emulation research shelf and
game-development reference cartridge. A bounded update adapter, real dated
emulator/decompilation references, an explicitly permitted offline-content path,
a source-linked exercise and handheld navigation/reading/playback remain separate
work. Preparing links does not satisfy those runtime or integration gates.

Run the targeted checks with:

```sh
python3 -m unittest discover -s tests -p 'test_reference_pack.py'
```

Failed writes retain the private output directory for review, including any files
that arrived from another writer. The index is written before the data manifest.
A failed/partial directory is never adopted or overwritten by this tool; select a
new output after resolving the failure. This is not a crash-durability receipt.
URL syntax requires an alphabetic DNS suffix, also refusing abbreviated, octal
and hexadecimal IPv4 spellings; no DNS or remote availability is checked.
