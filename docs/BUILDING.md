# Paired source and Android review builds

Nova has two separate deliverables: the external QML theme and an optional native
Pegasus build. Preparing, compiling, installing and accepting a release are
separate operations. These tools never install an app, select Home, enroll a
service, enable save sync or change emulator settings.

## Prepare exact source

Obtain a clean checkout of the pinned Pegasus revision and all of its submodules:

```sh
git clone --no-checkout https://github.com/mmatyas/pegasus-frontend.git pegasus-upstream
git -C pegasus-upstream checkout --detach 5d58223e58f84afb31d5d14a67438841b981a6fa
git -C pegasus-upstream submodule update --init --recursive
```

From the Nova repository, prepare a **new sibling directory**:

```sh
python3 tools/prepare_native.py prepare ../pegasus-upstream --output ../nova-paired --rom-cloud
python3 tools/prepare_native.py verify ../nova-paired
```

Omit `--rom-cloud` for the base bridge alone. Preparation clones the clean local
Git objects without hard links or fetching, verifies upstream/submodule revisions,
checks the native patch and its resulting files, integrates the optional module,
and copies the current external theme. It does not copy dirty private worktrees.
It also rejects incomplete Git parent history, which otherwise breaks qmake's
history-derived version metadata even when the working files are present. A
valid shallow checkout is supported.

The base patch also includes the [Android surface-order hooks](SURFACE-ORDER.md).
They need no additional flag; source inclusion does not establish the installed
app's compositor behaviour or import its private recorder.

### Optional stopping notebook and controller diagnostic

Both optional modules are **off by default**. To stage their native contexts in a
new paired workspace, explicitly request them alongside any desired cloud client:

```sh
python3 tools/prepare_native.py prepare ../pegasus-upstream --output ../nova-paired-tools \
  --rom-cloud --stopping-notes --controller-check
python3 tools/prepare_native.py verify ../nova-paired-tools
```

Each flag works independently. Preparation applies the base patch, then cloud,
stopping notes and controller check serially when selected. Their existing
appliers retain backups beside `source/`, outside the prepared native tree. The
manifest explicitly records `stoppingNotes` and `controllerCheck`, including false
values, and binds only selected runtime payloads and applier dependencies to the
inputs. Tests, fixture runners and module documentation are not runtime inputs.
All resulting native files and the complete paired theme still have their own
hash manifests. Input drift or a failed applier/final validation leaves
`PREPARATION-INCOMPLETE`; do not build that workspace.

`stoppingNotes` provides the separate private notebook API. `controllerCheck`
starts disabled, observes the current QtGamepad stream only when explicitly
opened, and permits only reviewed, user-requested private exports. The controller
module explicitly requires the QtGamepad backend; SDL configurations are refused.
The current theme exposes each UI entry only when its complete native context exists. Neither flag migrates existing checkpoints, requests
permissions, enables synchronization or establishes physical-controller proof.
See the [stopping-notes integration](STOPPING-NOTES.md) and
[controller diagnostic](../native/controllercheck/README.md) for host/UI contracts
and remaining Android/device gates. The original `prepare(upstream, output,
cloud=False, root=...)` Python API remains valid; the two new options are keyword
arguments `stopping_notes=False` and `controller_check=False`.

`nova-build-inputs.json` binds all prepared native-source and theme files to their
SHA-256 hashes, plus the Nova integration inputs. It contains no local source
paths or service enrollment. Verification rejects changed **and additional** files.
A failure leaves `PREPARATION-INCOMPLETE`; preserve and inspect it, then use a new
output directory. Do not build or publish an incomplete workspace.

This is a build workspace, not a distribution archive. Its `.git` directories can
contain local clone paths. Do not upload the workspace wholesale. Checksums bind
bytes; they are not a signature, authorship proof or security review.

## Build an arm64 Android review APK

The scoped recipe uses an already provisioned Qt 5.15 Android environment. It does
not download or repair a toolchain. The currently exercised setup uses Qt 5.15.10,
NDK r21e, Android platform 30, JDK 17, matching host `androiddeployqt`, cached Gradle
dependencies, and the OpenSSL directory layout required by upstream's
`src/app/install.pri`. Supplying host Qt alone is insufficient; an arm64 target Qt
SDK and matching cross configuration are required.

Set these path variables to **your own provisioned tools and caches**. No variable
is a credential or a signing password:

```sh
python3 tools/build_android.py ../nova-paired \
  --build-dir ../nova-android-review \
  --qmake "$NOVA_QMAKE" --qt-conf "$NOVA_QT_CONF" \
  --qt-android "$NOVA_QT_ANDROID" --sdk "$NOVA_ANDROID_SDK" \
  --ndk "$NOVA_ANDROID_NDK" --ndk-host "$NOVA_NDK_HOST" \
  --openssl "$NOVA_OPENSSL_ROOT" --androiddeployqt "$NOVA_ANDROIDDEPLOYQT" \
  --java-home "$NOVA_JAVA_HOME" --gradle-user-home "$NOVA_GRADLE_HOME" \
  --android-user-home "$NOVA_ANDROID_USER_HOME" --jobs 2
```

The NDK host name is `darwin-x86_64` for the exercised macOS toolchain; use the
installed NDK's actual host directory on other systems. Other hosts are not
certified by a successful macOS build.

The wrapper distribution and dependencies must already be cached. The driver
checks the wrapper's URL-derived cache location and completion marker before
starting. It gives this build its own Gradle home and offline init script, sharing
only the provisioned cache directories. The existing Gradle profile is not edited.

For a combined notebook/controller debug build, add `--gradle-heap-mib 1536`.
The exercised Android build needed that heap while packaging its unstripped
debug library. This optional setting is written only to the new build's Gradle
home and recorded in its result receipt; omitting it preserves Gradle's default.
It accepts 512–8192 MiB. Choose a value the build host can accommodate.

The build directory must be new and outside the source tree. The driver verifies
the pairing before and after compilation, configures qmake for arm64, forces the
final app link, stages that exact native library, verifies stripping preserves
allocated runtime sections, and runs Gradle offline. It then checks the APK
contains exactly the staged native bytes and records the DEX hashes. This guards
against the deployment tool retaining an older native library.

On success:

- `nova-android-review/apk/build/outputs/apk/debug/apk-debug.apk` is the debug APK.
- `nova-android-review/nova-build-result.json` records APK/native/DEX hashes and the
  input-manifest hash.
- `nova-paired/theme/` is the matching external theme. The APK does **not** include
  or install that theme merely because it shares a receipt.

On failure `BUILD-INCOMPLETE` remains, with `build.log` for diagnosis. No successful
build receipt is written. Builds are source-paired; bit-identical APK output across
hosts, timestamps, signing keys or toolchain versions is not promised.

## Existing device and release boundaries

This source recipe deliberately excludes private recorder/service modifications
that are not in `native/nova-library.patch`. It is **not a replacement/update for
an existing personal Library installation**. Updating such a device requires an
explicit integration of its current source/capabilities, signer and data, plus
recovery tests. Do not uninstall a working app to bypass a signing mismatch.

The generated APK uses debug signing and upstream resource assets. It is a private
review artifact, not a public release. Before public binary distribution, complete
branding, matching-source/dependency notices, dependency/security review, release
signing, clean onboarding and physical-device acceptance. See
[provenance](../PROVENANCE.md) and [validation](VALIDATION.md). The source recipe
does not establish full corresponding-source coverage for the provisioned Qt,
OpenSSL or other third-party toolchain binaries.

Cloud cleanup stays review-only without a trusted runtime-idle adapter, and
automatic save synchronization remains disabled. A build success cannot enable
those capabilities or certify gameplay.

## Source CI boundary

The `Source contracts` workflow runs Python and JavaScript contracts, the privacy
guard and fresh pinned native/theme preparation. It does **not** compile Qt,
produce an APK, run QML visually or certify a physical device. The first hosted
workflow run remains a separate check after publication approval.

### Updating a private installation

For a personal in-place update, use the existing approved signing identity in the scoped Android user home. A fresh Android user home may generate a different debug key. Verify the final signer and binary manifest against the installed baseline before any installation; a successful compile/package is insufficient. Never uninstall or reset an existing app to work around a signer mismatch. Keep signing material outside source and publication outputs.

Use a data-preserving Android package update (`adb install -r`) only after those checks. The Device CLI's `reinstall` uninstalls first: it deletes app-private data, app-scoped external preferences/history and Android Keystore keys, and resets Home and permissions. Never use it for an existing personal Library. Back up both internal files/shared preferences and the app-scoped external Pegasus directory before updating; a ciphertext enrollment vault alone cannot recover a deleted Keystore key. Retain the previously approved enrollment privately for recovery. Verify the same local files, grants, Home choice and sync after the update.

Restore writable app data as the app UID, including the external `theme_settings` directory and `stats.db`. An ADB push can leave shell-owned files that Qt can read but cannot save. Check owner IDs and an actual preference write after restoration; readback alone does not establish writability. Retain prior bytes and database integrity during repair.


## Optional public PC-game requests

`--pc-runtime` adds the allowlisted DroidDeck/GameNative Steam launch adapter,
Android Java wrapper, two explicit package-visibility entries and `pcRuntime`
context. It adds no Android permission or service. It may be combined with
`--rom-cloud --stopping-notes --controller-check`; the paired manifest records
all inputs. The public recipe remains separate from a recorder-preserving
personal APK. See [the PC adapter contract](../native/pcgames/README.md).
