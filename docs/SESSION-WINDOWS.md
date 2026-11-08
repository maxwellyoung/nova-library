# Session length

Details → Session length lets you label a game as comfortable for **5 minutes**, **20 minutes** or **an evening**. Choose **Not labelled** to clear it. Library → Filter and sort → Session length browses that label, intersecting search, system, local readiness, favourites, status and aspect. Not labelled is also a filter; it never guesses from playtime, console, title or a launch profile.

These are editable preferences about a comfortable start/stop window, not estimates of completion time. A disc-set edit applies to every explicit member in one preference update. Conflicting old per-disc labels appear as Mixed labels and do not satisfy a uniform session filter. Untagged games and apps/emulator launchers cannot be labelled. No game is launched by choosing a label.

Preferences use Pegasus's existing `api.memory` under the versioned `sessionWindows` key, scoped to the current theme on this device. They are not uploaded, included in the progress service, or synced to another device. Catalogue refreshes retain labels by explicit edition ID. No native rebuild or permission is needed. Switching to a different theme settings identity does not transfer these preferences.

The reader rejects unsupported versions, invalid IDs/values and oversized maps without replacing the saved value. The chooser then explains that labels are unavailable; unreadable records do not appear as deliberately unlabelled games. Missing catalogue IDs remain retained for a later refresh. Clear removes only the selected edition(s)' labels.

The existing Pegasus Memory implementation flushes JSON on `set`, but returns no disk-write receipt and does not use an atomic replacement. Nova therefore cannot distinguish an in-memory preference from a failed disk flush. Use these labels as low-stakes preferences, not as a save or progress record. Android process-restart persistence remains a device verification gate.

Verification: `node --test tests/session-windows.test.cjs` covers explicit/unknown labels, disc edits, filter intersections, rejected records and serialization. `tools/smoke_demo.py --surface session` and `--surface session-filter` exercise the actual theme's chooser, native Back path, filtering, clear, theme recreation and unreadable-store refusal. This desktop fixture uses in-memory theme settings; recreation is not a physical Nova process restart.
