# Provenance

Modified source notice: Nova's native changes and this publication layout were prepared on 2026-10-15 by Maxwell Young.

| Material | Origin | Boundary |
| --- | --- | --- |
| `theme/theme.qml`, `ArtView.qml`, `library.js`, `theme.cfg` | Nova's bespoke interface | QML theme using Pegasus API; does not implement an independent engine |
| `native/nova-library.patch` | Nova modifications to Pegasus | All modified tracked files and all new native source/test/fixture files captured against the pinned upstream commit |
| Native engine, launching, scanning, controller mapping, upstream resources | Pegasus Frontend contributors | Obtained from upstream, not vendored or claimed as Nova's original work |
| `tools/`, repository `tests/`, demo wrapper and generated SVG/PNG design | Nova publication tooling | Standalone synthetic fixtures and checks; no personal catalogue |
| `assets/platforms/`, generated `theme/PlatformMarks.js` | Pinned Simple Icons 13.21.0, Font Awesome Free 6.7.2 and RetroArch assets Monochrome | Original vectors, source URLs, SHA-256 digests and full collection notices retained; geometry converted for Qt Canvas. Simple Icons collection: CC0-1.0. Xbox and console gamepad: Fonticons, Inc., CC BY 4.0. PC, DS, N64, SNES, NES, Game Boy, Game Boy Color, Game Boy Advance and Dreamcast: Libretro contributors, CC BY 4.0, https://creativecommons.org/licenses/by/4.0/ . Platform trademarks remain with their owners; no endorsement implied |
| `LICENSE.md` | Pegasus Frontend license | Preserved verbatim, including supplementary terms |

Upstream: https://github.com/mmatyas/pegasus-frontend.git

Base commit: `5d58223e58f84afb31d5d14a67438841b981a6fa`.

The patch modifies build integration, Android package/activity handling, the frontend layer, scanner behavior, and adds the Device Library bridge with its full Java/C++ code and synthetic tests. `native/upstream.json` enumerates the patch's files, patch digest and resulting file digests. The bridge README has been rewritten for a portable public audience; machine-specific operating instructions and historical private QA claims were removed. Executable native modifications were retained.

The public theme uses Pegasus's system font instead of an optional local General Sans font asset. No font asset or third-party cover is distributed. Demo artwork is generated from simple shapes and invented names. PNG companions use the same original geometry and work without an SVG decoder; both are generated using Python's standard library.

Action icons and the Nova and Legion device silhouettes in `theme/Icon.qml` are Nova drawings. Recognizable platform marks are the separately credited vector material above. The generated JavaScript retains the Font Awesome attribution and licence link when the theme is copied on its own; Settings → About Nova also displays those credits. Regeneration is an optional build-time operation, not a network dependency of the running theme.

The patch leaves upstream resources in the reconstructed source tree, including icon/banner assets. This source candidate supplies no executable. Any future modified binary must satisfy the supplementary trademark terms; the Nova package label alone is not proof that all upstream branding has been replaced.

No source claim here covers the optional private service or its deployment. No corresponding-source claim is made for an already installed binary or an earlier debug build.

## Classic hardware marks

RetroArch assets Monochrome, Libretro contributors, pinned commit `d9f969054dc7fbb6fa89519036d2b971e0855b51`. Original SVG files, URLs and SHA-256 values are retained in `assets/platforms/sources.json`; full CC BY 4.0 text is in `assets/platforms/RetroArch-COPYING.txt`. Covers PC, DS, N64, SNES, NES, Game Boy, Game Boy Color, Game Boy Advance and Dreamcast. Shapes and transforms are converted to Canvas commands, uniformly scaled to a shared optical keyline and recoloured to the theme ink; source proportions and path geometry are retained. No endorsement or trademark licence is implied. Source: https://github.com/libretro/retroarch-assets .

Console navigation uses Font Awesome Free 6.7.2 `gamepad`, Fonticons, Inc., CC BY 4.0, pinned to the same commit as Xbox. Its original SVG, URL and SHA are retained; only theme-ink recolouring and uniform Canvas scaling are applied.
