# Home presentation

`theme/HomeShelf.qml` presents the exact entries selected by the main theme. It
owns no catalogue, recent history, saving, game launch or return behaviour.
`theme.qml` supplies selection, heading, platform/reason, availability, authored
stopping note, palette and text size. Its existing key handlers remain the source
of controller behaviour. Cover taps request Details; note taps request the
existing notebook.

The selected work is centred, with nearby artwork kept in its original shape.
A shallow neutral edge provides separation without claiming to reproduce a
physical cartridge or disc. At most five artwork loaders are active; decode size
is independent of layout to avoid a reload/ratio feedback loop. Selection uses
an interruptible 120 ms transition, disabled by reduced motion and inactive
surfaces. Android performance still needs measurement.

Home loads the presentation through a `Loader`. A missing or invalid component
must leave the main theme running and expose the selected title and a Library
link. This boundary cannot protect against failures elsewhere in the theme or
native launcher. Ship the complete theme directory, including HomeShelf and its
existing ArtView/Icon/library dependencies, in both the external theme and any
compiled default theme. Do not copy only `theme.qml`.

## Desktop check

Use an already provisioned input-preferences host and synthetic bundle:

```sh
python3 tools/smoke_home_shelf.py \
  --host /path/to/input-profiles-theme-host \
  --bundle /path/to/synthetic-bundle \
  --output /path/to/new-evidence-directory
```

The check runs real Qt in isolated temporary directories. It covers portrait,
square and wide artwork, pointer Details/note actions, injected navigation,
long text, missing art, reduced motion, single and empty states across six
profiles. It neither launches games nor modifies a real catalogue. Its
screenshots include synthetic page chrome; full-theme checks must separately
exercise the parent mappings and missing/invalid presentation fallback.

Desktop checks do not certify physical controls, a real swipe, Android layout,
sleep/return, frame timing or owner visual approval. A device update requires a
reviewed complete source pair and the project's normal release gates.
