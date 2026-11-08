# Android foundation decision

Reviewed 8 November 2026. This is a source-based recommendation, not a migration or a device comparison.

**Keep Pegasus for the current Nova release. For a successor, evaluate a separate native Kotlin/Compose app against Argosy before committing to a rewrite.** Switching to another closed launcher would give us a different product to configure, rather than a foundation we can maintain. An independent app may be the better long-term architecture; a rewrite has not yet earned its cost.

## What changed since the October assessment

The previous “small native patch” description is obsolete. The current tree has a 19-file base patch plus separate Cloud, notebook, controller-check and Android surface modules. Its theme contains 15 QML/JS files and 6,607 lines. Those counts include tests in the native modules and are size observations, not quality or complexity scores. Private recording integration is a separate source/build boundary.

The source pin is `5d58223e58f84afb31d5d14a67438841b981a6fa`. Upstream HEAD is now [`2a13b4f`](https://github.com/mmatyas/pegasus-frontend/commit/2a13b4f49c5c4a18d308b0cb5e7c99a2e6b8ac9b), committed 29 October. “We are at upstream HEAD” is no longer true. Updating the pin needs a patch/build regression check; it has not been done as part of this assessment.

## Real alternatives

| Foundation | Relevant benefit | Cost or limitation for this product | Decision |
| --- | --- | --- | --- |
| Existing Pegasus + Nova | Retains the actual QML interface, launch routes, notebook, checks and bridge contracts | Android CI still uses Qt 5.15.10 and NDK r21e; Android lifecycle features need native glue | Finish the current release here |
| Argosy | Open Kotlin/Compose Android application with RomM, a persistent queue, foreground download service and save-sync implementation | Our QML does not port; our identity/history/notebook contracts need adapters and regression checks. Following a rapidly changing application is a different maintenance burden | Strongest source alternative and comparison target |
| Own Kotlin/Compose app | Direct Android lifecycle, storage, background-transfer and controller integration; control of the product model | Rebuild focus/navigation, catalogue import, artwork caching, launches/returns, settings and all native modules. Compose alone does not solve emulator quirks or safe saves | Preferred direction to test for a successor, not yet approved as a rewrite |
| Own Qt 6 shell | Potential QML reuse; modern Qt Android backend | Still own the launcher/provider layer and JNI integrations; no measured migration result | Reserve option if preserving QML dominates |
| Cocoon / iiSU / Daijisho | Useful interaction and visual references; usable as alternative installed launchers | Public repositories are not reusable launcher application source. A release APK, assets repository or future source promise is not a foundation licence | References rather than implementation bases |
| ES-DE Android | Existing emulator catalogue and theme ecosystem | Does not provide the source/extension freedom needed for our in-process services; moving an XML theme does not port this application | Alternative product, not a shortcut to Nova parity |
| Socket / Godot | Custom visual composition is possible | Socket's source availability could not be freshly verified; Godot would still require Android service/storage adapters and a new launcher model | No evidence of a lower-cost route |

## Sources checked

- **Pegasus:** [repository](https://github.com/mmatyas/pegasus-frontend), [Android workflow at reviewed HEAD](https://github.com/mmatyas/pegasus-frontend/blob/2a13b4f49c5c4a18d308b0cb5e7c99a2e6b8ac9b/.github/workflows/android.yml), [licence](https://github.com/mmatyas/pegasus-frontend/blob/2a13b4f49c5c4a18d308b0cb5e7c99a2e6b8ac9b/LICENSE.md). GPLv3 plus the additional trademark terms remain relevant to distributing a modified binary.
- **Argosy:** [`v2.29.2`](https://github.com/rommapp/argosy-launcher/releases/tag/v2.29.2), published 7 November; reviewed commit [`2acbe47`](https://github.com/rommapp/argosy-launcher/tree/2acbe47aa56790c5e99a036de22bf1e86fa5677b). [Build configuration](https://github.com/rommapp/argosy-launcher/blob/2acbe47aa56790c5e99a036de22bf1e86fa5677b/app/build.gradle.kts) uses Compose/Room, compile/target SDK 35 and min SDK 26. [Queue persistence](https://github.com/rommapp/argosy-launcher/blob/2acbe47aa56790c5e99a036de22bf1e86fa5677b/app/src/main/kotlin/com/nendo/argosy/data/local/dao/DownloadQueueDao.kt), [download service controller](https://github.com/rommapp/argosy-launcher/blob/2acbe47aa56790c5e99a036de22bf1e86fa5677b/app/src/main/kotlin/com/nendo/argosy/data/download/DownloadServiceController.kt), and [save-sync orchestration](https://github.com/rommapp/argosy-launcher/blob/2acbe47aa56790c5e99a036de22bf1e86fa5677b/app/src/main/kotlin/com/nendo/argosy/data/repository/SaveSyncOrchestrator.kt) exist in source. GPL-3.0; source existence and project feature claims do not prove safe restore or control quality on Nova.
- **Cocoon:** [current repository](https://github.com/KansoMirai/CocoonFE) (`a4b2e3a`, 3 November; latest release beta-3.11, 28 October). It contains release material, platform data and tools, not the launcher app's reusable source. Its [own explanation of closed source](https://cocoon-shell.com/news/post-2-0/) promises possible future release if maintenance stops; that is not current source access.
- **iiSU:** [repository](https://github.com/iisu-network/iiSU), root commit `2fc0279`, with README/updates; latest release 0.0.7.4, 31 July. No application source or application licence was found there.
- **Daijisho:** [project README](https://github.com/TapiocaFox/Daijishou). Its MIT assets repository does not make the closed application source available.
- **ES-DE:** [official project](https://gitlab.com/es-de/emulationstation-de), [Android FAQ](https://gitlab.com/es-de/emulationstation-de/-/blob/master/FAQ.md). Android source and extension constraints are project-described, not a tested Nova migration.
- **Socket:** [official page](https://depmots.com/socket) returned HTTP 403 during this review. Earlier descriptions of its Godot foundation are historical, not freshly verified. It is not eliminated on an invented current feature claim.

## What an independent app would preserve

The transferable assets are edition identity, catalogue schema, source/check evidence, save-passport rules, queue semantics, notebook records and tests. The QML implementation, Pegasus API objects and Android activity/JNI wiring are not drop-in Kotlin components. AirPlay reception is an external Android app and is not tied to the frontend engine.

An independent repository also does not automatically make copied code independent. Reusing GPL application code retains its licence obligations. Reimplementing a contract in new code is different from copying a module. Keep notices and provenance explicit either way.

## A bounded decision experiment

Before choosing Argosy or an independent shell, compare one vertical path on the actual handheld, without changing its default Home or live saves:

1. Import a synthetic two-console catalogue and navigate it with physical controls at 1280×960 and large text.
2. Queue two synthetic downloads, interrupt/reopen, reconnect and verify retained bytes. Measure frame stalls and response, not a library screenshot alone.
3. Launch and return from the installed RetroArch and Dolphin routes using isolated test saves. Verify Home, Back, sleep/wake and focus.
4. Round-trip a synthetic notebook and observed-session record with the same edition identity; never infer session end from a foreground switch.
5. Compare dependency/toolchain size, build reproducibility, background-transfer behaviour and code ownership. Record actual parity gaps; do not assign speculative weeks-to-finish.

**Migration gate:** choose a successor only if it handles that path and offers a demonstrated maintenance or interaction benefit. Keep the existing app as rollback until catalogue identities, saves, history and controls survive the move. The current release and download-recovery approval remain separate from this proposed experiment.
