# Android 13 surface-order workaround

The pinned `native/nova-library.patch` includes `QtSurfaceOrder.java` and the
matching `MainActivity.onContentChanged`/`onDestroy` hooks. Fresh base and cloud
source preparation include it automatically; no additional applier or build flag
is needed. `native/upstream.json` binds both resulting Java files and the complete
patch to their hashes. The helper matches the separately tested private candidate;
the public patch still excludes the private ROM recorder and usage-access grant.

On the tested Android 13 client, Qt rendered the full screen while an opaque
parent-Window strip covered the composed bottom edge. Moving the sole Qt surface
above its Window bypassed that strip; restoring its ordinary order reproduced it.
The workaround does not establish or fix the underlying Window-hole defect.

The hooks activate only on runtime API 33 with target SDK at least 30. An additive
global-layout listener evaluates geometry before SurfaceView's pre-draw path,
including initial creation and replacement surfaces. It raises only one exact
`QtSurface` filling the exact `QtLayout`. Other runtimes, multiple surfaces,
partial geometry and unknown native children retain ordinary stacking. Binding
and destruction preserve other observers; no timer or polling service is added.

Two known nondrawing Qt children may coexist: the exact `QtEditText` input proxy,
and Qt's virtual accessibility host. The latter must be an exact `View` with an
exact `QtAccessibilityDelegate`, `NO_ID`, no background or foreground, and
full-layout bounds. Arbitrary Views, subclasses and drawable hosts remain
blocked. The check uses public APIs and preserves the delegate and hover routing.

Virtual accessibility-focus highlighting may use the parent Window. A public
touch-exploration state listener therefore restores ordinary order when
exploration is enabled, including transitions without a layout pass. Missing
state observation also blocks the workaround. No accessibility service or global
setting is changed. Other accessibility modes and their visual focus behavior
still require runtime verification.

The helper's Java lifecycle tests use bounded view and accessibility-manager
stubs and exercise 39 policy assertions:

```sh
python3 -m unittest discover -s tests -p 'test_surface_order.py'
```

The test applies only the complete helper-file section from the pinned patch,
checks its result hash, and compiles that actual source with Java 8 compatibility.
It requires an installed JDK and does not download one. Stub checks establish the
transition policy, not Android rendering, keyboard behavior or gameplay.

Physical checks observed clear screen edges on two cold launches, a visible
keyboard with search/filter/clear, native Settings to default-Home return, the
expected compositor order, and unchanged recorder bytes in the private build.
Native dialogs, live touch exploration, human controls and an actual game-recording
interval remain separate acceptance gates. The source-only public build is not a
recorder-preserving replacement for an existing private installation.

No theme clearance, permission, activity, service, signing identity or emulator
setting is changed by this patch. Theme pairing and private recorder integration
remain separate operations. Production cloud removal still requires a trusted
idle adapter; this workaround does not provide one.

Relevant implementation references are [Qt's accessibility host](https://github.com/qt/qtbase/blob/v5.15.10-lts-lgpl/src/android/jar/src/org/qtproject/qt5/android/accessibility/QtAccessibilityDelegate.java),
[Qt's input proxy](https://github.com/qt/qtbase/blob/v5.15.10-lts-lgpl/src/android/jar/src/org/qtproject/qt5/android/QtEditText.java),
and Android 13's [SurfaceView](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/view/SurfaceView.java)
and [ViewRootImpl](https://android.googlesource.com/platform/frameworks/base/+/android-13.0.0_r1/core/java/android/view/ViewRootImpl.java).
