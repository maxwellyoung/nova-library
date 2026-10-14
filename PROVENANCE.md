# Provenance

Modified source notice: Nova's native changes and this publication layout were prepared on 2026-10-15 by Maxwell Young.

| Material | Origin | Boundary |
| --- | --- | --- |
| `theme/theme.qml`, `ArtView.qml`, `library.js`, `theme.cfg` | Nova's bespoke interface | QML theme using Pegasus API; does not implement an independent engine |
| `native/nova-library.patch` | Nova modifications to Pegasus | All modified tracked files and all new native source/test/fixture files captured against the pinned upstream commit |
| Native engine, launching, scanning, controller mapping, upstream resources | Pegasus Frontend contributors | Obtained from upstream, not vendored or claimed as Nova's original work |
| `tools/`, repository `tests/`, demo wrapper and generated SVG design | Nova publication tooling | Standalone synthetic fixtures and checks; no personal catalogue |
| `LICENSE.md` | Pegasus Frontend license | Preserved verbatim, including supplementary terms |

Upstream: https://github.com/mmatyas/pegasus-frontend.git

Base commit: `5d58223e58f84afb31d5d14a67438841b981a6fa`.

The patch modifies build integration, Android package/activity handling, the frontend layer, scanner behavior, and adds the Device Library bridge with its full Java/C++ code and synthetic tests. `native/upstream.json` enumerates the patch's files, patch digest and resulting file digests. The bridge README has been rewritten for a portable public audience; machine-specific operating instructions and historical private QA claims were removed. Executable native modifications were retained.

The public theme uses Pegasus's system font instead of an optional local General Sans font asset. No font asset or third-party cover is distributed. Demo artwork is generated from simple shapes and invented names.

The patch leaves upstream resources in the reconstructed source tree, including icon/banner assets. This source candidate supplies no executable. Any future modified binary must satisfy the supplementary trademark terms; the Nova package label alone is not proof that all upstream branding has been replaced.

No source claim here covers the optional private service or its deployment. No corresponding-source claim is made for an already installed binary or an earlier debug build.
