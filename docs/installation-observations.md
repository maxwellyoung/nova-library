# Installation and capacity observations

Installation is separate from a launch route, a registered catalogue item, and a gameplay check. The frontend never downloads or deletes games itself.

`x-installations` accepts a JSON object with `nova` and `legion` observations. Each has `state` (`installed`, `absent`, `partial`), `observedAt` (ISO timestamp), `source`, `scopeComplete` and optional `offline`. Missing, malformed or undated observations display **Not checked**. An absent observation is accepted only with a complete scan. An offline capture keeps its original date. Matching is by edition identity; ROM and Steam editions are not merged by title. A disc set is fully installed only when every member has an installed observation.

`x-storage-volume` accepts a JSON object on any catalogue entry, carried once on a utility entry in a private export. Fields are `id: internal-data`, `total`, `used`, `free` (nonnegative integer bytes), `observedAt` and `source`. Used plus free may be less than total; that gap is unavailable space, not an invented file category. Conflicting values from the same newest capture show unknown capacity. The capacity view labels the capture as a snapshot.

Existing `x-size-bytes` and `x-size-observed-at` supply separate logical ROM file bars. These do not measure app private storage or explain total filesystem usage. Unknown sizes are retained explicitly. Files and DroidDeck management rows use configured utility-app routes; they do not launch a game or start an install.

Default game details show labelled symbols and compact facts. **Info** preserves sources, dates and longer explanations; B returns to details. Icons are original Canvas line drawings and do not require a symbol font.
