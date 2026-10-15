import QtQuick 2.15
import QtQml 2.15
import "library.js" as Lib

// Personal Library: Home is a shelf, Library is an index, Threads holds kept groups and
// explained suggestions. Covers carry the colour; focus is light, size and a plain edge.
// Nothing here starts a game unless the exporter marked a local route and Pegasus still
// sees the file. Progress is only what someone wrote down; play time stays separate.
FocusScope {
    id: root
    focus: true

    // ---------- scale, type, surface ----------

    readonly property bool wide: width / Math.max(1, height) >= 1.5
    readonly property real s: Math.max(0.5, Math.min(width / 1280, height / 800))
    readonly property real textScale: appearance.size === "large" ? 1.12 : 1
    function px(v) { return Math.round(v * s) }
    function fs(v) { return Math.round(v * s * textScale) }

    readonly property bool light: appearance.surface === "light"
    readonly property color ground: light ? "#f3f3f1" : "#0c0d0e"
    readonly property color ink: light ? "#151617" : "#e9eaea"
    readonly property color quiet: Qt.rgba(ink.r, ink.g, ink.b, 0.62)
    readonly property color faint: Qt.rgba(ink.r, ink.g, ink.b, 0.38)
    readonly property color rowQuiet: Qt.rgba(ink.r, ink.g, ink.b, 0.52)
    readonly property color rowFaint: Qt.rgba(ink.r, ink.g, ink.b, 0.3)
    readonly property color slab: light ? "#e1e1de" : "#1a1c1e"

    readonly property string sans: global.fonts.sans

    // ---------- state ----------

    property var rawEntries: []       // api.allGames order
    property var presentationEntries: [] // explicit disc sets collapse only in browse surfaces
    readonly property int gameCount: presentationEntries.filter(function(e) { return e.systemId !== "androidapps" && e.systemId !== "emulators"; }).length
    property var allEntries: []       // A to Z, for the Home fallback
    property var entryById: ({})
    property var homeEntries: []
    property var homeCaptions: ({})   // id -> segment name
    property var homeGapAfter: ({})   // id -> true where a segment ends
    property bool homeIsFallback: false
    property var libraryEntries: []
    property var appsEntries: []
    property int appIndex: 0
    property string appsReturnView: "home"
    property var pins: []
    property var appearance: ({ surface: "dark", size: "standard", time: false })

    property var filters: Lib.emptyFilters()
    property string sortMode: "alpha"
    property var systems: []
    readonly property var consoleSystems: systems.filter(function(x) { return x.id !== "androidapps" && x.id !== "emulators"; })
    property int consoleIndex: 0
    property bool fromConsole: false
    property string libAnchorId: ""   // the edition the user last chose in Library
    property double now: Date.now()

    property var threads: []
    property int threadIndex: 0
    property int memberIndex: 0
    property string threadZone: "list" // list | members

    // The native Device Library is optional. Without it there is no progress sync to show.
    readonly property var bridge: typeof deviceLibrary !== "undefined" && deviceLibrary ? deviceLibrary : null
    property var device: null         // normalised read({}), or null when absent or unreadable
    readonly property bool canEdit: bridge !== null && device !== null
    property int personalRev: 0
    property string notice: ""

    property string view: "home"      // home | library | consoles | threads
    property string zone: "content"   // content | nav | search
    property string overlay: ""       // "" | details | appearance | filters | status | threadpick | text
    property string overlayReturn: ""
    property int navIndex: 0
    property int searchCol: 0         // 0 search field, 1 filter control
    property int panelIndex: 0
    property int settingsIndex: 0
    property var discTarget: null
    property int detailAction: 0
    property int homeIndex: 0
    property int libIndex: 0
    property string searchText: ""
    property bool editingSearch: false
    property string textMode: ""      // checkpoint | thread-name
    property string textTarget: ""    // edition the text belongs to
    property bool editingText: false
    property bool ready: false
    property string lastLogged: ""

    readonly property var homeCurrent: homeIndex >= 0 && homeIndex < homeEntries.length ? homeEntries[homeIndex] : null
    readonly property var libCurrent: libIndex >= 0 && libIndex < libraryEntries.length ? libraryEntries[libIndex] : null
    readonly property var appCurrent: appIndex >= 0 && appIndex < appsEntries.length ? appsEntries[appIndex] : null
    readonly property var currentThread: threadIndex >= 0 && threadIndex < threads.length ? threads[threadIndex] : null
    readonly property var threadMember: currentThread && memberIndex >= 0 && memberIndex < currentThread.entries.length
                                        ? currentThread.entries[memberIndex] : null
    readonly property var current: view === "home" ? homeCurrent
                                 : view === "library" ? libCurrent
                                 : view === "apps" ? appCurrent
                                 : view === "threads" && threadZone === "members" ? threadMember : null
    readonly property bool currentPinned: current !== null && pins.indexOf(current.id) !== -1
    readonly property bool filtering: Lib.filtersActive(filters)

    readonly property string kAccept: Lib.keyLabel(api.keys.accept, "A")
    readonly property string kCancel: Lib.keyLabel(api.keys.cancel, "B")
    readonly property string kDetails: Lib.keyLabel(api.keys.details, "X")
    readonly property string kKeep: Lib.keyLabel(api.keys.filters, "Y")
    readonly property string kPrev: Lib.keyLabel(api.keys.prevPage, "L1")
    readonly property string kNext: Lib.keyLabel(api.keys.nextPage, "R1")

    readonly property var views: ["home", "library", "consoles", "threads", "apps"]
    readonly property var viewNames: ({ home: "Home", library: "Library", consoles: "Consoles", threads: "Collections", apps: "Apps" })

    onCurrentChanged: {
        if (!ready)
            return;
        logFocus();
        saveTimer.restart();
    }
    onViewChanged: if (ready) { logFocus(); saveTimer.restart(); }

    // ---------- memory ----------

    function memGet(key, fallback) {
        return api.memory.has(key) ? api.memory.get(key) : fallback;
    }

    function saveFocus() {
        var f = memGet("focus", {}) || {};
        var out = { home: f.home || "", library: f.library || "", thread: f.thread || "", console: f.console || "", app: f.app || "", consoleBrowse: fromConsole };
        if (consoleSystems.length && consoleSystems[consoleIndex]) out.console = consoleSystems[consoleIndex].id;
        if (homeCurrent) out.home = homeCurrent.id;
        if (libCurrent) out.library = libCurrent.id;
        if (currentThread) out.thread = currentThread.id;
        if (appCurrent) out.app = appCurrent.id;
        api.memory.set("focus", out);
        api.memory.set("view", view);
    }

    function saveLibraryPrefs() {
        api.memory.set("library", { filters: filters, sort: sortMode });
    }

    Timer { id: saveTimer; interval: 700; onTriggered: root.saveFocus() }
    // Android can leave the soft keyboard up when hide() lands while the field
    // still owns focus or the IME is finishing its Enter. Ask again once settled.
    Timer {
        id: keyboardTimer
        objectName: "keyboardTimer"
        interval: 150
        onTriggered: if (!root.editingSearch && !searchInput.activeFocus
                         && !root.editingText && !textInput.activeFocus) Qt.inputMethod.hide()
    }
    Timer { id: noticeTimer; interval: 4000; onTriggered: root.notice = "" }

    function say(text) {
        notice = text;
        noticeTimer.restart();
    }

    function logFocus() {
        var id = current ? current.id : "none";
        var line = "NOVA_LIBRARY focus=" + id + " view=" + view;
        if (line === lastLogged)
            return;
        lastLogged = line;
        console.log(line);
    }

    onConsoleIndexChanged: if (ready) saveTimer.restart()
    onAppIndexChanged: if (ready) saveTimer.restart()

    // ---------- models ----------

    function rebuildAll() {
        var raw = [];
        var byId = {};
        for (var i = 0; i < api.allGames.count; i++) {
            var e = Lib.makeEntry(api.allGames.get(i));
            e.order = i;
            raw.push(e);
            if (!byId[e.id])
                byId[e.id] = e;
        }
        Lib.applyPersonal(raw, device);
        rawEntries = raw;
        entryById = byId;
        rebuildPresentations();
        now = Date.now();
    }

    function rebuildPresentations() {
        var appId = appCurrent ? appCurrent.id : "";
        appsEntries = Lib.sortEntries(rawEntries.filter(function(e) { return e.systemId === "androidapps"; }), "alpha");
        setAppIndex(Math.max(0, Lib.indexOfId(appsEntries, appId)));
        presentationEntries = Lib.groupEntries(rawEntries);
        allEntries = Lib.sortEntries(presentationEntries, "alpha");
        systems = Lib.systemsOf(presentationEntries);
    }

    function rebuildHome(keepId) {
        var seen = {};
        var grouped = Lib.groupEntries(rawEntries);
        function take(list, cap) {
            var out = [];
            for (var i = 0; i < list.length && out.length < cap; i++) {
                var e = list[i];
                if (!e || e.systemId === "androidapps" || e.systemId === "emulators") continue;
                if (e && !e.discMembers) e = Lib.presentEdition(e, grouped);
                var key = e ? Lib.presentationKey(e) : "";
                if (e && !seen[key]) {
                    out.push(e);
                    seen[key] = true;
                }
            }
            return out;
        }
        // The handheld's own launcher history comes first. Imported activity
        // and seeded catalogue picks are labelled separately from local play.
        var localRecent = take(Lib.sortEntries(grouped.filter(function(e) {
            return e.lastPlayedHere !== null && e.launchable;
        }), "local-recent"), 6);
        var playing = take(Lib.sortEntries(rawEntries.filter(function(e) { return e.status === "playing"; }), "recent"), 6);
        var kept = take(pins.map(function(id) { return entryById[id]; }), 1000);
        var recent = take(Lib.sortEntries(rawEntries.filter(function(e) { return e.lastPlayed !== null; }), "recent"), 4);
        var captions = {};
        var gaps = {};
        var out = [];
        [["Last opened here", localRecent], ["Playing", playing], ["Favourite", kept], ["Recent from catalogue", recent]].forEach(function(seg) {
            if (!seg[1].length) return;
            if (out.length) gaps[out[out.length - 1].id] = true;
            seg[1].forEach(function(t) { captions[t.id] = seg[0]; out.push(t); });
        });
        if (!out.length) {
            var starters = rawEntries.filter(function(e) { return e.home; }).sort(function(a, b) {
                var oa = parseInt(Lib.extra(a.game, "home-order"), 10);
                var ob = parseInt(Lib.extra(b.game, "home-order"), 10);
                return (isNaN(oa) ? a.order : oa) - (isNaN(ob) ? b.order : ob);
            });
            take(starters, 12).forEach(function(e) { captions[e.id] = "Starter pick"; out.push(e); });
        }

        var fallback = false;
        if (!out.length) {
            for (var j = 0; j < allEntries.length && out.length < 12; j++) {
                if (allEntries[j].launchable && allEntries[j].systemId !== "androidapps" && allEntries[j].systemId !== "emulators") {
                    out.push(allEntries[j]);
                    captions[allEntries[j].id] = "Set up here";
                }
            }
            fallback = out.length > 0;
        }

        homeCaptions = captions;
        homeGapAfter = gaps;
        homeIsFallback = fallback;
        var previous = homeIndex;
        homeEntries = out;
        var idx = Lib.indexOfId(out, keepId);
        if (idx < 0)
            idx = Math.min(previous, out.length - 1);
        homeIndex = Math.max(0, idx);
    }

    function rebuildLibrary(keepId) {
        var previous = libraryEntries;
        var out = Lib.sortEntries(Lib.filterEntries(Lib.groupEntries(rawEntries), filters, pins, searchText), sortMode);
        libraryEntries = out;
        setLibIndex(Lib.stableIndex(out, previous, libAnchorId, keepId), true, true);
    }

    function rebuildThreads(keepId) {
        var memberId = threadMember ? threadMember.id : "";
        var out = Lib.buildThreads(rawEntries, device);
        threads = out;
        var idx = Lib.indexOfId(out, keepId);
        // A suggestion that was just kept comes back under a new id; stay on it.
        for (var i = 0; idx < 0 && keepId && i < out.length; i++)
            if (out[i].suggestedId === keepId)
                idx = i;
        threadIndex = idx >= 0 ? idx : Math.max(0, Math.min(threadIndex, out.length - 1));
        var t = currentThread;
        var m = t ? Lib.indexOfId(t.entries, memberId) : -1;
        memberIndex = m >= 0 ? m : Math.max(0, Math.min(memberIndex, t ? t.entries.length - 1 : 0));
        if (threadZone === "members" && !threadMember)
            threadZone = "list";
    }

    function rebuildEverything() {
        var f = memGet("focus", {}) || {};
        var homeId = homeCurrent ? homeCurrent.id : f.home;
        var libId = libCurrent ? libCurrent.id : f.library;
        var threadId = currentThread ? currentThread.id : f.thread;
        rebuildAll();
        rebuildHome(homeId);
        rebuildLibrary(libId);
        rebuildThreads(threadId);
        personalRev++;
    }

    Connections {
        target: api.allGames
        function onCountChanged() { if (root.ready) root.rebuildEverything(); }
    }

    // ---------- the Device Library bridge ----------

    function refreshDevice() {
        if (!bridge || typeof bridge.read !== "function") {
            device = null;
        } else {
            try {
                device = Lib.normalizeDevice(bridge.read({}));
            } catch (err) {
                // Unreadable is not the same as empty: editing stays off until a read succeeds.
                console.log("NOVA_LIBRARY bridge read failed: " + err);
                device = null;
            }
        }
        if (ready)
            rebuildEverything();
    }

    Connections {
        target: root.bridge
        ignoreUnknownSignals: true
        function onChanged() { root.refreshDevice(); }
        function onStatusChanged() { root.refreshDevice(); }
    }

    // Sends one action. The receipt, not the request, decides what we say happened.
    function act(action, okText) {
        if (!canEdit || typeof bridge.act !== "function") {
            say("The Device Library isn't available, so nothing was saved.");
            return null;
        }
        var receipt = null;
        // An untouched edition has no server revision yet. Let the native queue
        // infer its initial revision rather than sending an invalid JSON null.
        if (action.expectedRevision === null || action.expectedRevision === undefined)
            delete action.expectedRevision;
        try {
            receipt = bridge.act(action);
        } catch (err) {
            receipt = { ok: false, error: String(err) };
        }
        receipt = receipt || { ok: false, error: "no receipt" };
        console.log("NOVA_LIBRARY act type=" + action.type + " ok=" + (receipt.ok === true)
                    + " queued=" + (receipt.queued === true));
        if (receipt.ok === true)
            say(okText + (receipt.queued === true ? " Waiting to sync." : ""));
        else
            say("Not saved: " + (receipt.error || "the Device Library refused it") + ".");
        refreshDevice();
        return receipt;
    }

    function syncLabel() {
        if (!bridge)
            return "Not in this build";
        if (!device)
            return "Couldn't read";
        var st = device.sync.state;
        var waiting = device.sync.pending > 0 ? device.sync.pending + " waiting" : "";
        if (st === "synced" || st === "idle" || st === "settled" || st === "acknowledged")
            return waiting || "Up to date";
        if (st === "offline")
            return "Offline" + (waiting ? ", " + waiting : "");
        if (st === "syncing")
            return "Syncing";
        if (st === "error")
            return "Last sync failed";
        return waiting || (st ? st.charAt(0).toUpperCase() + st.slice(1) : "Unknown");
    }

    function requestSync() {
        if (!bridge || typeof bridge.synchronize !== "function") {
            say("Sync isn't available in this build.");
            return;
        }
        try {
            bridge.synchronize();
            say("Sync requested.");
        } catch (err) {
            say("Sync couldn't start: " + err + ".");
        }
        refreshDevice();
    }

    Component.onCompleted: {
        // Drop the record left by the retired QA launch probe.
        if (api.memory.has("launchProbe") && typeof api.memory.unset === "function")
            api.memory.unset("launchProbe");

        var storedPins = memGet("pins", []);
        var cleanPins = [];
        if (storedPins && storedPins.length !== undefined)
            for (var i = 0; i < storedPins.length; i++)
                if (typeof storedPins[i] === "string" && cleanPins.indexOf(storedPins[i]) === -1)
                    cleanPins.push(storedPins[i]);
        pins = cleanPins;

        var t = memGet("theme", {}) || {};
        appearance = {
            surface: t.surface === "light" ? "light" : "dark",
            size: t.size === "large" ? "large" : "standard",
            time: t.time === true
        };

        var v = memGet("view", "home");
        view = views.indexOf(v) !== -1 ? v : "home";

        if (bridge && typeof bridge.read === "function") {
            try { device = Lib.normalizeDevice(bridge.read({})); }
            catch (err) { console.log("NOVA_LIBRARY bridge read failed: " + err); device = null; }
        }

        rebuildAll();

        // Saved filters only come back if they still make sense for this catalogue.
        var lib = memGet("library", {}) || {};
        var sf = lib.filters || {};
        var systemIds = systems.map(function(x) { return x.id; });
        filters = {
            system: systemIds.indexOf(sf.system) !== -1 ? sf.system : "",
            device: Lib.DEVICES.indexOf(sf.device) !== -1 ? sf.device : "",
            kept: sf.kept === true,
            status: Lib.STATUSES.indexOf(sf.status) !== -1 ? sf.status : ""
        };
        sortMode = Lib.SORTS.indexOf(lib.sort) !== -1 ? lib.sort : "alpha";

        var f = memGet("focus", {}) || {};
        libAnchorId = f.library || "";
        setAppIndex(Math.max(0, Lib.indexOfId(appsEntries, f.app)));
        fromConsole = f.consoleBrowse === true && filters.system !== "";
        for (var c = 0; c < consoleSystems.length; c++)
            if (consoleSystems[c].id === f.console) consoleIndex = c;
        rebuildHome(f.home);
        rebuildLibrary(f.library);
        rebuildThreads(f.thread);
        ready = true;
        console.log("NOVA_LIBRARY ready games=" + allEntries.length + " home=" + homeEntries.length
                    + " pins=" + pins.length + " fallback=" + homeIsFallback + " view=" + view
                    + " threads=" + threads.length + " bridge=" + (bridge ? (device ? "read" : "unreadable") : "absent"));
        logFocus();
    }

    Component.onDestruction: if (ready) saveFocus()

    // ---------- actions ----------

    function setLibIndex(i, instant, keepAnchor) {
        if (!libraryEntries.length) {
            libIndex = 0;
            return;
        }
        libIndex = Math.max(0, Math.min(libraryEntries.length - 1, i));
        libraryView.currentIndex = libIndex;
        if (instant)
            libraryView.positionViewAtIndex(libIndex, ListView.Center);
        if (!keepAnchor)
            libAnchorId = libraryEntries[libIndex].id;
    }

    function moveHome(step) {
        if (!homeEntries.length)
            return;
        homeIndex = Math.max(0, Math.min(homeEntries.length - 1, homeIndex + step));
    }

    function jumpLetter(dir) {
        if (!libCurrent)
            return;
        if (sortMode !== "alpha") {
            setLibIndex(libIndex + dir * 8);
            return;
        }
        var here = Lib.initialOf(libCurrent);
        var i = libIndex;
        if (dir > 0) {
            while (i < libraryEntries.length && Lib.initialOf(libraryEntries[i]) === here) i++;
            setLibIndex(i < libraryEntries.length ? i : libraryEntries.length - 1);
        } else {
            while (i > 0 && Lib.initialOf(libraryEntries[i - 1]) === here) i--;
            if (i === libIndex && i > 0) {
                var prev = Lib.initialOf(libraryEntries[i - 1]);
                i--;
                while (i > 0 && Lib.initialOf(libraryEntries[i - 1]) === prev) i--;
            }
            setLibIndex(i);
        }
    }

    function setAppIndex(i) {
        appIndex = Math.max(0, Math.min(appsEntries.length - 1, i));
        appsList.currentIndex = appIndex;
        if (appsEntries.length) appsList.positionViewAtIndex(appIndex, ListView.Contain);
    }

    function switchView(v) {
        if (v === "apps" && view !== "apps") appsReturnView = view;
        if (editingSearch)
            endSearch(false);
        overlay = "";
        zone = "content";
        if (v === "threads")
            threadZone = "list";
        if (view !== v)
            view = v;
    }

    function stepView(dir) {
        var i = views.indexOf(view) + dir;
        if (i >= 0 && i < views.length) {
            fromConsole = false;
            switchView(views[i]);
        }
    }

    function play(e) {
        if (!e) return;
        if (e.discMembers) {
            discTarget = e;
            var preferred = Lib.defaultDisc(e.discMembers);
            openPanel("discs", Lib.indexOfId(e.discMembers, preferred.id));
            return;
        }
        playEdition(e);
    }

    function playEdition(e) {
        if (!e)
            return;
        if (!e.launchable || e.game.missing) {
            console.log("NOVA_LIBRARY launch-skipped id=" + e.id + " reason=" + (e.game.missing ? "missing" : "no-route"));
            openDetails();
            return;
        }
        saveTimer.stop();
        saveFocus();
        console.log("NOVA_LIBRARY launch id=" + e.id + " route=" + (e.route || "unlabelled") + " view=" + view);
        e.game.launch();
    }

    function toggleKeep(e) {
        if (!e)
            return;
        var homeId = homeCurrent ? homeCurrent.id : "";
        var libId = libCurrent ? libCurrent.id : "";
        var next = pins.slice();
        var at = next.indexOf(e.id);
        if (at === -1)
            next.push(e.id);
        else
            next.splice(at, 1);
        pins = next;
        api.memory.set("pins", next);
        console.log("NOVA_LIBRARY keep id=" + e.id + " " + (at === -1 ? "on" : "off"));
        // Keep works without the bridge; with it, the pin also goes into the outbox.
        if (canEdit && typeof bridge.act === "function") {
            try { bridge.act({ type: "pin", editionId: e.id, pinned: at === -1 }); }
            catch (err) { console.log("NOVA_LIBRARY pin not recorded: " + err); }
        }
        rebuildHome(homeId);
        if (filters.kept)
            rebuildLibrary(libId);
    }

    function setAppearance(key, value) {
        var a = { surface: appearance.surface, size: appearance.size, time: appearance.time };
        a[key] = value;
        appearance = a;
        api.memory.set("theme", a);
    }

    function cycleAppearance(i) {
        if (i === 0) setAppearance("surface", appearance.surface === "dark" ? "light" : "dark");
        else if (i === 1) setAppearance("size", appearance.size === "standard" ? "large" : "standard");
        else if (i === 2) setAppearance("time", !appearance.time);

    }

    function navActivate(i) {
        if (i < views.length) {
            fromConsole = false;
            switchView(views[i]);
        } else openPanel("settings", settingsIndex);
    }

    function selectConsole(i) {
        consoleIndex = Math.max(0, Math.min(consoleSystems.length - 1, i));
        consoleGrid.currentIndex = consoleIndex;
        consoleGrid.positionViewAtIndex(consoleIndex, GridView.Contain);
    }

    function consoleReady(id) {
        return presentationEntries.filter(function(e) {
            return (id === "?" ? !e.systemId : e.systemId === id) && e.launchable && !e.missing;
        }).length;
    }

    function browseConsole() {
        if (!consoleSystems.length || !consoleSystems[consoleIndex]) return;
        // Console browsing starts with the whole system, so an old search or
        // status filter cannot make a populated console look empty.
        var f = Lib.emptyFilters();
        f.system = consoleSystems[consoleIndex].id;
        filters = f;
        searchInput.text = "";
        searchText = "";
        saveLibraryPrefs();
        rebuildLibrary("");
        fromConsole = true;
        switchView("library");
        logFilters();
    }

    function openPanel(name, index) {
        if (editingSearch)
            endSearch(false);
        zone = name === "filters" ? zone : "content";
        overlayReturn = overlay;
        panelIndex = index;
        overlay = name;
    }

    function openDetails() {
        if (!current)
            return;
        detailAction = 0;
        detailFlick.contentY = 0;
        overlay = "details";
    }

    function closeOverlay() {
        if (overlay === "facts") { overlay = "details";
        } else if (overlay === "discs") {
            overlay = overlayReturn === "details" ? "details" : "";
            discTarget = null;
        } else if (["appearance", "storage", "controls", "refresh"].indexOf(overlay) !== -1 && overlayReturn === "settings") {
            overlay = "settings";
            panelIndex = settingsIndex;
            overlayReturn = "";
        } else if (overlay === "status" || overlay === "threadpick" || (overlay === "text" && overlayReturn === "details"))
            overlay = "details";
        else
            overlay = "";
    }

    // ---------- filters and sort ----------

    function setFilter(key, value) {
        var keep = libCurrent ? libCurrent.id : "";
        var f = { system: filters.system, device: filters.device, kept: filters.kept, status: filters.status };
        f[key] = value;
        filters = f;
        saveLibraryPrefs();
        rebuildLibrary(keep);
        logFilters();
    }

    function setSort(mode) {
        var keep = libCurrent ? libCurrent.id : "";
        sortMode = mode;
        saveLibraryPrefs();
        rebuildLibrary(keep);
        logFilters();
    }

    function clearFilters() {
        var keep = libCurrent ? libCurrent.id : "";
        filters = Lib.emptyFilters();
        saveLibraryPrefs();
        rebuildLibrary(keep);
        logFilters();
    }

    function logFilters() {
        console.log("NOVA_LIBRARY filter system=" + (filters.system || "any") + " device=" + (filters.device || "any")
                    + " kept=" + filters.kept + " status=" + (filters.status || "any") + " sort=" + sortMode
                    + " shown=" + libraryEntries.length);
    }

    function systemLabel(id) {
        if (!id)
            return "All systems";
        for (var i = 0; i < systems.length; i++)
            if (systems[i].id === id)
                return systems[i].name;
        return id;
    }

    function cycleFilter(row, step) {
        if (row === 0) setFilter("system", Lib.cycle([""].concat(systems.map(function(x) { return x.id; })), filters.system, step));
        else if (row === 1) setFilter("device", Lib.cycle(Lib.DEVICES, filters.device, step));
        else if (row === 2) setFilter("kept", !filters.kept);
        else if (row === 3) setFilter("status", Lib.cycle([""].concat(Lib.STATUSES), filters.status, step));
        else if (row === 4) setSort(Lib.cycle(Lib.SORTS, sortMode, step));
        else if (row === 5) clearFilters();
    }

    function filterSummary() {
        var parts = [];
        if (filters.system) parts.push(systemLabel(filters.system));
        if (filters.device) parts.push(Lib.DEVICE_LABELS[filters.device]);
        if (filters.kept) parts.push("Kept");
        if (filters.status) parts.push(Lib.STATUS_LABELS[filters.status]);
        // One filter is named; more are counted, so the line stays short on the Nova.
        var label = parts.length === 0 ? "All" : parts.length === 1 ? parts[0] : parts.length + " filters";
        return label + "  ·  " + Lib.SORT_LABELS[sortMode];
    }

    // ---------- progress and threads ----------

    function keptThreads() {
        return threads.filter(function(t) { return t.origin === "kept"; });
    }

    function setStatus(status) {
        var e = current;
        if (!e || status === e.status)
            return;
        act({ type: "status", editionId: e.id, status: status, expectedRevision: e.revision },
            "Status set to " + Lib.STATUS_LABELS[status].toLowerCase() + ".");
    }

    function canKeepThread(t) {
        return canEdit && t !== null && (t.origin === "suggested" || t.origin === "catalogue");
    }

    function keepThread(t) {
        if (!canKeepThread(t))
            return;
        var members = t.members.slice();
        t.entries.forEach(function(e) { if (members.indexOf(e.id) === -1) members.push(e.id); });
        act({ type: "thread-keep", suggestedId: t.id, name: t.name, members: members }, "Kept “" + t.name + "”.");
    }

    function toggleMembership(t, e) {
        if (!t || !e)
            return;
        if (t.id.indexOf("local:") === 0) {
            say("This thread is saved here. Add games after its first sync.");
            return;
        }
        var member = Lib.indexOfId(t.entries, e.id) === -1;
        act({ type: "thread-membership", threadId: t.id, editionId: e.id, member: member },
            (member ? "Added to " : "Removed from ") + "“" + t.name + "”.");
    }

    function createThread(name, editionId) {
        var before = keptThreads().map(function(t) { return t.id; });
        var receipt = act({ type: "thread-create", name: name }, "Made “" + name + "”.");
        if (!editionId || !receipt || receipt.ok !== true)
            return;
        var made = keptThreads().filter(function(t) { return t.name === name && before.indexOf(t.id) === -1; });
        if (made.length === 1)
            toggleMembership(made[0], entryById[editionId]);
        else
            say("Made “" + name + "”. Add this game once the thread appears.");
    }

    // ---------- text entry (search and notes share the keyboard fix) ----------

    function beginSearch() {
        keyboardTimer.stop();
        zone = "search";
        searchCol = 0;
        editingSearch = true;
        searchInput.forceActiveFocus();
        Qt.inputMethod.show();
    }

    function endSearch(toList) {
        Qt.inputMethod.commit();
        editingSearch = false;
        searchInput.focus = false;
        root.forceActiveFocus();
        dropKeyboard();
        if (toList && libraryEntries.length) {
            zone = "content";
            // Landing on a result is a choice, so clearing the search stays on it.
            if (libCurrent)
                libAnchorId = libCurrent.id;
        }
    }

    function dropKeyboard() {
        Qt.inputMethod.hide();
        keyboardTimer.restart();
    }

    function openText(mode, target) {
        if (!canEdit)
            return;
        overlayReturn = overlay === "" ? "" : "details";
        textMode = mode;
        textTarget = target;
        var e = entryById[target];
        textInput.text = mode === "checkpoint" && e && e.checkpointSource === "you" ? e.checkpoint : "";
        overlay = "text";
        beginText();
    }

    function beginText() {
        keyboardTimer.stop();
        editingText = true;
        textInput.forceActiveFocus();
        Qt.inputMethod.show();
    }

    function endText(save) {
        Qt.inputMethod.commit();
        var value = textInput.text.trim();
        editingText = false;
        textInput.focus = false;
        root.forceActiveFocus();
        dropKeyboard();
        if (save)
            submitText(value);
        closeOverlay();
    }

    function submitText(value) {
        if (textMode === "checkpoint") {
            var e = entryById[textTarget];
            if (!e || (value === e.checkpoint && e.checkpointSource === "you"))
                return;
            act({ type: "checkpoint", editionId: e.id, text: value, expectedRevision: e.revision },
                value ? "Checkpoint saved." : "Checkpoint cleared.");
        } else if (textMode === "thread-name") {
            if (value)
                createThread(value, textTarget);
        }
    }

    // ---------- words ----------

    function homeReason(e) {
        if (!e) return "";
        var reason = homeCaptions[e.id];
        if (reason === "Last opened here") return "From this Nova’s launch history · " + Lib.ago(e.lastPlayedHere, now) + ".";
        if (reason === "Favourite") return "You added this to favourites. " + kKeep + " removes it.";
        if (reason === "Playing") return "Marked Playing in your saved progress.";
        if (reason === "Recent from catalogue") return "Recent activity from the catalogue, which can include other devices.";
        if (reason === "Starter pick") return "A preselected starter pick, not your play history. " + kKeep + " adds a favourite to make Home yours.";
        return "Set up on this device. Play or favourite a game to build your own Home.";
    }

    function quietLine(e, rev) {
        if (!e)
            return "";
        var parts = [];
        if (view === "home" && homeCaptions[e.id])
            parts.push(homeCaptions[e.id]);
        var r = e.systemId === "androidapps" ? Lib.shortRoute(e) : Lib.availabilityText(e) + (e.launchable ? " · " + Lib.shortRoute(e) : " · Needs setup");
        if (r)
            parts.push(r);
        if (e.discMembers) parts.push("Disc " + e.discNumber + " record");
        if (e.status !== "unknown" && !(view === "home" && homeCaptions[e.id] === "Playing"))
            parts.push(Lib.STATUS_LABELS[e.status]);
        if (appearance.time && e.minutes)
            parts.push(e.minutes + " lifetime");
        return parts.join("  ·  ");
    }

    function detailLines(e, rev) {
        if (!e)
            return [];
        var out = [];
        out.push({ t: Lib.routeSentence(e), q: false });
        ["nova", "legion"].forEach(function(d) { var v = Lib.installation(e,d); out.push({ t: Lib.deviceName(d) + " install: " + Lib.installLabel(e,d) + (v.observedAt ? " · " + Lib.dateEvidenceText(v.observedAt) + " · " + v.source + (v.offline ? " · device offline at refresh" : "") : ""), q: true }); });
        if (e.discMembers) {
            out.push({ t: "Notes, status and favourites shown here belong to Disc " + e.discNumber + ". Other discs keep separate records.", q: false });
            e = e.discEdition;
        }
        if (e.readyDevices.length)
            out.push({ t: "Launch route on " + e.readyDevices.map(Lib.deviceName).join(" and ") + ", per the catalogue export.", q: true });
        if (e.systemId === "androidapps") {
            out.push({ t: Lib.appPurpose(e) + ".", q: false });
            return out;
        }
        if (Lib.isSteamGame(e) && !e.launchable)
            out.push({ t: droidDeckApp()
                ? "Open DroidDeck, then search “" + e.title + "” in Steam to check or install it there."
                : "DroidDeck isn't configured here. Check this game in your Steam app; Library cannot install it from this entry.", q: false });
        out.push({ t: e.novaGameplayNote && e.novaGameplaySource && e.novaGameplayObservedAt && Lib.dateEvidenceText(e.novaGameplayObservedAt) !== "Date unknown"
            ? "Gameplay check on Nova · " + Lib.dateEvidenceText(e.novaGameplayObservedAt) + " · " + e.novaGameplaySource + ": " + e.novaGameplayNote
            : "Gameplay on Nova: not checked. A configured launch route does not establish compatibility or performance.", q: true });
        out.push({ t: e.displayAspect && e.displayAspectSource
            ? "Screen aspect: " + e.displayAspect + " (" + e.displayAspectSource + "). Screen fit on this device is not checked."
            : "Screen fit: not checked. Original aspect ratio is unknown.", q: true });
        out.push({ t: "Nova: " + (e.nova || "not checked"), q: true });
        out.push({ t: "Legion: " + (e.legion || "not checked"), q: true });

        var wait = e.pending ? ", waiting to sync" : "";
        if (e.status !== "unknown")
            out.push({ t: "Status: " + Lib.STATUS_LABELS[e.status]
                          + (e.statusSource === "catalogue" ? " (from the catalogue)" : wait), q: false });
        if (e.checkpoint)
            out.push({ t: "Checkpoint: " + e.checkpoint
                          + (e.checkpointSource === "catalogue" ? " (from the catalogue)" : wait), q: false });
        if (e.conflict)
            out.push({ t: "Another device changed this too. The conflict is kept for you to settle, not overwritten.", q: false });
        if (e.minutes)
            out.push({ t: (e.minutesSource === "steam" ? "Steam lifetime: " : "Lifetime play time: ") + e.minutes
                          + ". Time played, not story progress.", q: true });
        if (e.lastPlayed !== null)
            out.push({ t: "Last played: " + Lib.ago(e.lastPlayed, now), q: true });
        if (e.recReason || e.recScore !== null)
            out.push({ t: e.recReason ? "Suggested: " + e.recReason + " (" + e.recSource + ")"
                                      : "Suggested by the " + e.recSource + ", with no reason given.", q: true });
        var names = Lib.threadNamesFor(e, threads);
        if (names.length)
            out.push({ t: "In threads: " + names.join(", "), q: true });
        if (e.deviceFit)
            out.push({ t: "Catalogue fit note: " + e.deviceFit + ". This does not verify the original aspect ratio.", q: true });
        var why = [];
        if (homeCaptions[e.id] === "Starter pick") why.push("a preselected starter pick");
        if (pins.indexOf(e.id) !== -1) why.push("kept");
        if (why.length)
            out.push({ t: "On Home because it's " + why.join(" and ") + ".", q: true });
        if (e.source)
            out.push({ t: "Source: " + e.source, q: true });
        if (!bridge)
            out.push({ t: "Status and checkpoints can't be edited here: this build has no Device Library service.", q: true });
        else if (!device)
            out.push({ t: "The Device Library didn't answer, so editing is off for now.", q: true });
        return out;
    }

    function overviewLines(e, rev) {
        if (!e) return [];
        if (e.systemId === "androidapps") return [{ t: Lib.appPurpose(e), q: false, icon: "apps" }, { t: e.launchable ? "Open app" : "Needs setup", q: true, icon: "info" }];
        var out = [{ t: e.discMembers ? e.discMembers.length + " discs · " + Lib.discReadyCount(e) + " set up here" : e.launchable ? (e.route || "Local shortcut configured") : "Needs setup here", q: false, icon: e.discMembers ? "disc" : "play" }];
        if (e.discMembers) { out.push({ t: "Disc " + e.discNumber + " progress record", q: true, icon: "note" }); e = e.discEdition; }
        var checked = e.novaGameplayNote && e.novaGameplaySource && Lib.dateEvidenceText(e.novaGameplayObservedAt) !== "Date unknown";
        out.push({ t: checked ? "Short check · " + String(e.novaGameplayObservedAt).slice(0,10) : "Gameplay untested", q: true, icon: checked ? "check" : "info" });
        out.push({ t: e.displayAspect && e.displayAspectSource ? "Aspect · " + e.displayAspect : "Aspect not checked", q: true, icon: "aspect" });
        if (e.status !== "unknown") out.push({ t: Lib.STATUS_LABELS[e.status], q: false, icon: "note" });
        if (e.checkpoint) out.push({ t: "Stopped: " + e.checkpoint + (e.pending ? " · sync pending" : ""), q: false, icon: "note" });
        if (e.conflict) out.push({ t: "Progress conflict · open Info", q: false, icon: "info" });
        if (e.minutes) out.push({ t: "Lifetime · " + e.minutes, q: true, icon: "clock" });
        if (e.recReason) out.push({ t: e.recReason, q: true, icon: "star" });
        return out;
    }

    function storageApp(kind) {
        if (kind === "steam") return droidDeckApp();
        return rawEntries.filter(function(e) { return e.systemId === "androidapps" && e.title === "Files" && e.launchable && !e.game.missing; })[0] || null;
    }

    function droidDeckApp() {
        return Lib.configuredApp(rawEntries, "com.droiddeck.launcher", "DroidDeck");
    }

    function openDroidDeck() {
        var app = droidDeckApp();
        if (!app) { say("DroidDeck has no configured app route here."); return; }
        say("Opening DroidDeck. Search this game in Steam there.");
        playEdition(app);
    }

    function detailActions() {
        var e = current;
        if (!e)
            return [];
        var out = [];
        if (e.systemId === "androidapps") return e.launchable ? [{ a: "play", l: "Open app" }] : [];
        if (e.discMembers || e.launchable) out.push({ a: "play", l: e.discMembers ? "Choose disc" : "Play" });
        if (Lib.isSteamGame(e) && !e.launchable && droidDeckApp()) out.push({ a: "droiddeck", l: "Open DroidDeck" });
        out.push({ a: "keep", l: (currentPinned ? "Remove" : "Keep") + (e.discMembers ? " disc " + e.discNumber : "") });
        if (canEdit) {
            out.push({ a: "status", l: "Status" });
            out.push({ a: "note", l: "Stopping note" });
            out.push({ a: "thread", l: "Threads" });
        }
        out.push({ a: "facts", l: "Info" });
        return out;
    }

    function runDetailAction(i) {
        var list = detailActions();
        if (i < 0 || i >= list.length)
            return;
        detailAction = i;
        var a = list[i].a;
        if (a === "play") play(current);
        else if (a === "droiddeck") openDroidDeck();
        else if (a === "facts") { overlay = "facts"; detailFlick.contentY = 0; }
        else if (a === "keep") toggleKeep(current);
        else if (a === "status") openPanel("status", Math.max(0, Lib.STATUSES.indexOf(current.status)));
        else if (a === "note") openText("checkpoint", current.id);
        else if (a === "thread") openPanel("threadpick", 0);
    }

    // Settings and its read-only guides reuse the existing list panel.
    function panelTitle() {
        if (overlay === "discs") return discTarget ? discTarget.title + " · choose a disc" : "Choose a disc";
        if (overlay === "settings") return "Settings";
        if (overlay === "storage") return "Storage";
        if (overlay === "controls") return "Launcher controls";
        if (overlay === "refresh") return "Library refresh";
        if (overlay === "appearance") return "Appearance";
        if (overlay === "filters") return "Filter and sort";
        if (overlay === "status") return "Status";
        if (overlay === "threadpick") return "Threads";
        return "";
    }

    function isListPanel() {
        return ["discs", "settings", "appearance", "storage", "controls", "refresh", "filters", "status", "threadpick"].indexOf(overlay) !== -1;
    }

    function storageRows() {
        var summary = Lib.storageSummary(rawEntries);
        function label(g) {
            return g.known ? Lib.bytesText(g.bytes) + (g.unknown ? " · " + g.unknown + " unknown" : "") : "Unknown";
        }
        var rows = [{ label: "Known ROM files", value: label(summary), evidence: summary }];
        if (storageApp("files")) rows.push({ label: "Manage files", value: "Open Files", app: "files" });
        if (storageApp("steam")) rows.push({ label: "Steam storage", value: "Open DroidDeck", app: "steam" });
        summary.groups.forEach(function(g) { rows.push({ label: g.name, value: label(g), evidence: g, fraction: summary.bytes && g.known ? g.bytes / summary.bytes : 0 }); });
        if (summary.largest.length) {
            rows.push({ label: "Largest observed files", value: "", dim: true });
            summary.largest.slice(0, 8).forEach(function(e) {
                rows.push({ label: e.title, value: Lib.bytesText(e.sizeBytes), entry: e });
            });
        }
        return rows;
    }

    function captureText(oldest, newest) {
        if (oldest === null) return "Capture date unknown.";
        return "Captured " + Lib.utcDateText(oldest) + (newest !== oldest ? " to " + Lib.utcDateText(newest) : "") + ".";
    }

    function homeCheckpoint(e) {
        if (!e || !e.checkpoint) return "";
        return (e.discMembers ? "Disc " + e.discNumber + " · " : "")
             + (e.checkpointSource === "you" ? "You stopped: " : "Catalogue note: ") + e.checkpoint;
    }

    function panelRows(rev) {
        if (overlay === "discs") return discTarget ? discTarget.discMembers.map(function(e) {
            return { label: "Disc " + e.discNumber, value: e.game.missing ? "File missing here" : e.launchable ? "Set up here" : "Not set up here" };
        }) : [];
        if (overlay === "settings")
            return [
                { label: "Appearance", value: appearance.surface === "light" ? "Light" : "Dark" },
                { label: "Sync progress", value: syncLabel() },
                { label: "Storage", value: "Observed ROM files" },
                { label: "Launcher controls", value: "Button guide" },
                { label: "Library refresh", value: "Catalogue and artwork" }
            ];
        if (overlay === "storage") return storageRows();
        if (overlay === "controls")
            return [
                { label: "Choose / play", value: kAccept },
                { label: "Back", value: kCancel },
                { label: "Game details", value: kDetails },
                { label: "Favourite / filters", value: kKeep },
                { label: "Previous / next page", value: kPrev + " / " + kNext },
                { label: "Native launcher menu", value: "Start (default)" }
            ];
        if (overlay === "refresh") {
            var stamp = Lib.storageSummary(rawEntries).exported;
            return [
                { label: "Catalogue export", value: Lib.utcDateText(stamp) },
                { label: "Games in catalogue", value: String(gameCount) },
                { label: "Browse entries", value: String(presentationEntries.length) },
                { label: "Catalogue entries", value: String(rawEntries.length) }
            ];
        }
        if (overlay === "appearance")
            return [
                { label: "Surface", value: appearance.surface === "light" ? "Light" : "Dark" },
                { label: "Text size", value: appearance.size === "large" ? "Larger" : "Standard" },
                { label: "Play time on focus", value: appearance.time ? "Shown" : "Hidden" }
            ];
        if (overlay === "filters")
            return [
                { label: "System", value: systemLabel(filters.system) },
                { label: "Device", value: Lib.DEVICE_LABELS[filters.device] },
                { label: "Kept", value: filters.kept ? "Kept only" : "Any" },
                { label: "Status", value: filters.status ? Lib.STATUS_LABELS[filters.status] : "Any status" },
                { label: "Sort", value: Lib.SORT_LABELS[sortMode] },
                { label: "Clear filters", value: "", dim: !filtering }
            ];
        if (overlay === "status")
            return Lib.STATUSES.map(function(s) {
                return { label: Lib.STATUS_LABELS[s], value: current && current.status === s ? "Current" : "" };
            });
        if (overlay === "threadpick") {
            var rows = keptThreads().map(function(t) {
                return { label: t.name, value: current && Lib.indexOfId(t.entries, current.id) !== -1 ? "In this thread" : "" };
            });
            rows.push({ label: "New thread with this game", value: "" });
            return rows;
        }
        return [];
    }

    function panelFooter(rev) {
        if (overlay === "discs") {
            var member = discTarget && discTarget.discMembers[panelIndex];
            return member ? Lib.routeSentence(member)
                + (member.lastPlayedHere !== null ? " Last opened here: " + Lib.ago(member.lastPlayedHere, now) + "." : " No local launch history.")
                + " This launches the selected disc. Changing discs during a running game uses the emulator." : "";
        }
        if (overlay === "settings") {
            if (panelIndex === 1) return "Sync sends saved progress, favourites and notes. It does not scan games or download artwork."
                + (device && device.sync.message ? " " + device.sync.message : "");
            return "Your launcher settings. Emulator controls are configured inside each emulator.";
        }
        if (overlay === "controls") return "These are the current launcher bindings. Start opens the native menu with the default mapping; its Settings includes controller mapping. Stopping notes are in game details. Emulator controls are separate. This guide does not change mappings.";
        if (overlay === "refresh") return "New games and artwork come from a refreshed catalogue. This build loads the catalogue prepared on your computer; progress sync does not scan files. The refreshed catalogue must be transferred and loaded before new games or artwork appear.";
        if (overlay === "storage") {
            var rows = storageRows();
            var row = rows[panelIndex];
            if (row && row.app) return row.app === "steam" ? "Manage Steam installs in DroidDeck. No download is started here." : "Browse and manage your files in the Files app.";
            var evidence = row && row.entry ? { known: 1, unknown: 0, oldest: row.entry.sizeObservedAt, newest: row.entry.sizeObservedAt, undated: row.entry.sizeObservedAt === null ? 1 : 0 }
                         : row && row.evidence ? row.evidence : Lib.storageSummary(rawEntries);
            return evidence.known + " known file sizes · " + evidence.unknown + " unknown. "
                 + "Bars compare known ROM files, separately from filesystem capacity. " + captureText(evidence.oldest, evidence.newest);
        }
        if (overlay === "appearance") {
            var msg = device && device.sync.message ? " " + device.sync.message : "";
            return "Saved with this theme on this device. Play time is lifetime time from the catalogue, not story progress."
                   + msg;
        }
        if (overlay === "filters")
            return "Showing " + libraryEntries.length + " of " + presentationEntries.length + " browse entries · " + gameCount + " games · " + rawEntries.length + " catalogue entries"
                   + ". Status is only what you or the catalogue set. Unknown dates and times sort last.";
        if (overlay === "status")
            return (current ? current.title + ". " : "") + (current && current.discMembers ? "Disc " + current.discNumber + " record. " : "") + "Status is yours to set. Play time never changes it.";
        if (overlay === "threadpick")
            return current ? "Choose a thread to add or remove " + current.title + (current.discMembers ? " · Disc " + current.discNumber : "") + "." : "";
        return "";
    }

    function panelActivate(i, step) {
        panelIndex = i;
        if (overlay === "discs") {
            var member = discTarget && discTarget.discMembers[i];
            if (member && member.launchable && !member.game.missing) playEdition(member);
            else say("This disc isn't set up here. No game was launched.");
        } else if (overlay === "storage") {
            var row = storageRows()[i];
            if (row && row.app) { var app = storageApp(row.app); if (app) playEdition(app); }
        } else if (overlay === "settings") {
            settingsIndex = i;
            if (i === 0) openPanel("appearance", 0);
            else if (i === 1) requestSync();
            else if (i === 2) openPanel("storage", 0);
            else if (i === 3) openPanel("controls", 0);
            else if (i === 4) openPanel("refresh", 0);
        } else if (overlay === "appearance") cycleAppearance(i);
        else if (overlay === "filters") cycleFilter(i, step);
        else if (overlay === "status") { setStatus(Lib.STATUSES[i]); closeOverlay(); }
        else if (overlay === "threadpick") {
            var kept = keptThreads();
            if (i < kept.length) toggleMembership(kept[i], current);
            else openText("thread-name", current ? current.id : "");
        }
    }

    function hints() {
        if (overlay === "facts") return [{ k: kCancel, l: "Back", a: "close" }];
        if (overlay === "discs") {
            var member = discTarget && discTarget.discMembers[panelIndex];
            return [{ k: kAccept, l: member && member.launchable && !member.game.missing ? "Play disc" : "Unavailable", a: "panel" }, { k: kCancel, l: "Back", a: "close" }];
        }
        if (overlay === "settings") return [{ k: kAccept, l: panelIndex === 1 ? "Sync now" : "Open", a: "panel" }, { k: kCancel, l: "Back", a: "close" }];
        if (overlay === "storage") {
            var row = storageRows()[panelIndex];
            return (row && row.app ? [{ k: kAccept, l: "Open", a: "panel" }] : [])
                .concat([{ k: "↑ ↓", l: "Browse", a: "read" }, { k: kCancel, l: "Back", a: "close" }]);
        }
        if (overlay === "controls" || overlay === "refresh")
            return [{ k: "↑ ↓", l: "Read", a: "read" }, { k: kCancel, l: "Back", a: "close" }];
        if (overlay === "appearance" || overlay === "filters") {
            var p = [{ k: kAccept, l: "Change", a: "panel" }];
            if (overlay === "filters" && filtering) p.push({ k: kDetails, l: "Clear filters", a: "clearfilters" });
            p.push({ k: kCancel, l: "Done", a: "close" });
            return p;
        }
        if (overlay === "status" || overlay === "threadpick")
            return [{ k: kAccept, l: "Choose", a: "panel" }, { k: kCancel, l: "Back", a: "close" }];
        if (overlay === "text")
            return [{ k: kAccept, l: "Save", a: "save" }, { k: kCancel, l: "Cancel", a: "cancel" }];
        if (zone === "nav")
            return [{ k: kAccept, l: "Open", a: "nav" }, { k: kCancel, l: "Back", a: "content" }];
        if (zone === "search") {
            if (editingSearch)
                return [{ k: kAccept, l: "Done", a: "endsearch" }];
            var s = searchCol === 0 ? [{ k: kAccept, l: "Type", a: "search" }, { k: kKeep, l: "Filter", a: "filters" }]
                                    : [{ k: kAccept, l: "Filter", a: "filters" }];
            if (filtering) s.push({ k: kDetails, l: "Clear filters", a: "clearfilters" });
            return s;
        }
        if (view === "apps" && !current) return [{ k: kCancel, l: "Back", a: "appsback" }];
        if (view === "apps") return [
            { k: kAccept, l: current && current.launchable ? "Open app" : "Details", a: "play" },
            { k: kDetails, l: "Details", a: "details" }, { k: kCancel, l: "Back", a: "appsback" }
        ];
        if (view === "consoles")
            return consoleSystems.length ? [{ k: kAccept, l: "Browse games", a: "console" }, { k: kCancel, l: "Home", a: "home" }]
                                  : [{ k: kCancel, l: "Home", a: "home" }];
        if (view === "threads" && threadZone === "list") {
            var t = [];
            if (currentThread && currentThread.entries.length) t.push({ k: kAccept, l: "Open", a: "openthread" });
            if (canKeepThread(currentThread)) t.push({ k: kKeep, l: "Keep thread", a: "keepthread" });
            if (canEdit) t.push({ k: kDetails, l: "New thread", a: "newthread" });
            return t;
        }
        var h = [];
        if (current && !current.launchable && Lib.isSteamGame(current)) h.push({ k: kAccept, l: "Details", a: "play" });
        if (current && (current.discMembers || current.launchable)) h.push({ k: kAccept, l: current.discMembers ? "Choose disc" : "Play", a: "play" });
        if (current) h.push({ k: kDetails, l: "Details", a: "details" });
        if (current) h.push({ k: kKeep, l: (currentPinned ? "Unfavourite" : "Favourite") + (current.discMembers ? " disc " + current.discNumber : ""), a: "keep" });
        return h;
    }

    function runHint(a) {
        if (a === "play") play(current);
        else if (a === "droiddeck") openDroidDeck();
        else if (a === "details") openDetails();
        else if (a === "keep") toggleKeep(current);
        else if (a === "close") closeOverlay();
        else if (a === "panel") panelActivate(panelIndex, 1);
        else if (a === "read") panelIndex = Math.min(panelRows(personalRev).length - 1, panelIndex + 1);
        else if (a === "nav") navActivate(navIndex);
        else if (a === "content") zone = "content";
        else if (a === "search") beginSearch();
        else if (a === "endsearch") endSearch(true);
        else if (a === "filters") openPanel("filters", 0);
        else if (a === "clearfilters") clearFilters();
        else if (a === "console") browseConsole();
        else if (a === "home") switchView("home");
        else if (a === "appsback") switchView(appsReturnView);
        else if (a === "openthread") openThread();
        else if (a === "keepthread") keepThread(currentThread);
        else if (a === "newthread") openText("thread-name", "");
        else if (a === "save") endText(true);
        else if (a === "cancel") endText(false);
    }

    function openThread() {
        if (!currentThread || !currentThread.entries.length)
            return;
        zone = "content";
        threadZone = "members";
        memberIndex = Math.max(0, Math.min(memberIndex, currentThread.entries.length - 1));
    }

    function selectThread(i) {
        if (i === threadIndex)
            return;
        threadIndex = Math.max(0, Math.min(threads.length - 1, i));
        memberIndex = 0;
    }

    // ---------- controller and keyboard ----------

    Keys.onPressed: function(event) { root.handleKey(event); }

    function handleKey(event) {
        var k = api.keys;
        if (event.isAutoRepeat && (k.isAccept(event) || k.isDetails(event) || k.isFilters(event) || k.isCancel(event))) {
            event.accepted = true;
            return;
        }

        if (overlay === "facts") {
            event.accepted = true;
            if (k.isCancel(event) || k.isDetails(event)) closeOverlay();
            else if (k.isUp(event)) detailFlick.contentY = Math.max(0, detailFlick.contentY - px(120));
            else if (k.isDown(event)) detailFlick.contentY = Math.max(0, Math.min(detailFlick.contentHeight - detailFlick.height, detailFlick.contentY + px(120)));
            else event.accepted = false;
            return;
        }
        if (overlay === "details") {
            event.accepted = true;
            var n = detailActions().length;
            if (k.isCancel(event) || k.isDetails(event)) overlay = "";
            else if (k.isAccept(event)) runDetailAction(detailAction);
            else if (k.isFilters(event)) toggleKeep(current);
            else if (k.isLeft(event)) detailAction = Math.max(0, detailAction - 1);
            else if (k.isRight(event)) detailAction = Math.min(n - 1, detailAction + 1);
            else if (k.isUp(event)) detailFlick.contentY = Math.max(0, detailFlick.contentY - px(120));
            else if (k.isDown(event)) detailFlick.contentY = Math.max(0, Math.min(detailFlick.contentHeight - detailFlick.height, detailFlick.contentY + px(120)));
            else event.accepted = false;
            return;
        }

        if (isListPanel()) {
            event.accepted = true;
            var rows = panelRows(personalRev).length;
            // Left and right change a value; they never trigger Sync or Clear filters.
            var cycles = (overlay === "appearance" && panelIndex < 3) || (overlay === "filters" && panelIndex < 5);
            if (k.isCancel(event) || (overlay === "filters" && k.isFilters(event))) closeOverlay();
            else if (k.isUp(event)) panelIndex = Math.max(0, panelIndex - 1);
            else if (k.isDown(event)) panelIndex = Math.min(rows - 1, panelIndex + 1);
            else if (k.isAccept(event)) panelActivate(panelIndex, 1);
            else if (cycles && k.isRight(event)) panelActivate(panelIndex, 1);
            else if (cycles && k.isLeft(event)) panelActivate(panelIndex, -1);
            else if (overlay === "filters" && k.isDetails(event)) clearFilters();
            else event.accepted = false;
            return;
        }

        if (overlay === "text") {
            // Reached only once the field has let go of the keyboard.
            event.accepted = true;
            if (k.isAccept(event)) endText(true);
            else if (k.isCancel(event)) endText(false);
            else if (k.isDetails(event)) beginText();
            else event.accepted = false;
            return;
        }

        if (k.isPrevPage(event)) { stepView(-1); event.accepted = true; return; }
        if (k.isNextPage(event)) { stepView(1); event.accepted = true; return; }

        if (zone === "nav") {
            event.accepted = true;
            if (k.isLeft(event)) navIndex = Math.max(0, navIndex - 1);
            else if (k.isRight(event)) navIndex = Math.min(views.length, navIndex + 1);
            else if (k.isAccept(event)) navActivate(navIndex);
            else if (k.isDown(event) || k.isCancel(event)) zone = view === "library" ? "search" : "content";
            else event.accepted = false;
            return;
        }

        if (zone === "search") {
            event.accepted = true;
            if (k.isUp(event)) { zone = "nav"; navIndex = 1; }
            else if (k.isDown(event)) { if (libraryEntries.length) zone = "content"; }
            else if (k.isRight(event)) searchCol = 1;
            else if (k.isLeft(event)) searchCol = 0;
            else if (k.isAccept(event)) { if (searchCol === 0) beginSearch(); else openPanel("filters", 0); }
            else if (k.isFilters(event)) openPanel("filters", 0);
            else if (k.isDetails(event)) { if (filtering) clearFilters(); }
            else if (k.isCancel(event)) {
                if (searchText !== "") searchInput.text = "";
                else if (libraryEntries.length) zone = "content";
                else switchView(fromConsole ? "consoles" : "home");
            }
            else event.accepted = false;
            return;
        }

        if (view === "home") {
            if (k.isLeft(event)) moveHome(-1);
            else if (k.isRight(event)) moveHome(1);
            else if (k.isUp(event)) { zone = "nav"; navIndex = 0; }
            else if (k.isPageUp(event)) homeIndex = 0;
            else if (k.isPageDown(event)) homeIndex = Math.max(0, homeEntries.length - 1);
            else if (k.isAccept(event)) play(current);
            else if (k.isDetails(event)) openDetails();
            else if (k.isFilters(event)) toggleKeep(current);
            else return; // B and Start fall through to the Pegasus menu
            event.accepted = true;
            return;
        }

        if (view === "apps") {
            if (k.isUp(event)) { if (appIndex === 0 || !appsEntries.length) { zone = "nav"; navIndex = views.indexOf("apps"); } else setAppIndex(appIndex - 1); }
            else if (k.isDown(event)) setAppIndex(appIndex + 1);
            else if (k.isPageUp(event)) setAppIndex(appIndex - 6);
            else if (k.isPageDown(event)) setAppIndex(appIndex + 6);
            else if (k.isAccept(event)) play(current);
            else if (k.isDetails(event)) openDetails();
            else if (k.isCancel(event)) switchView(appsReturnView);
            else return;
            event.accepted = true;
            return;
        }

        if (view === "consoles") {
            if (k.isLeft(event)) selectConsole(consoleIndex - 1);
            else if (k.isRight(event)) selectConsole(consoleIndex + 1);
            else if (k.isUp(event)) {
                if (consoleIndex < 3) { zone = "nav"; navIndex = views.indexOf("consoles"); }
                else selectConsole(consoleIndex - 3);
            }
            else if (k.isDown(event)) selectConsole(consoleIndex + 3);
            else if (k.isAccept(event)) browseConsole();
            else if (k.isCancel(event)) switchView("home");
            else return;
            event.accepted = true;
            return;
        }

        if (view === "threads") {
            if (threadZone === "list") {
                if (k.isUp(event)) { if (threadIndex === 0 || !threads.length) { zone = "nav"; navIndex = views.indexOf("threads"); } else selectThread(threadIndex - 1); }
                else if (k.isDown(event)) selectThread(threadIndex + 1);
                else if (k.isRight(event) || k.isAccept(event)) openThread();
                else if (k.isFilters(event)) keepThread(currentThread);
                else if (k.isDetails(event)) openText("thread-name", "");
                else if (k.isCancel(event)) switchView("home");
                else return;
            } else {
                var count = currentThread ? currentThread.entries.length : 0;
                if (k.isUp(event)) memberIndex = Math.max(0, memberIndex - 1);
                else if (k.isDown(event)) memberIndex = Math.min(count - 1, memberIndex + 1);
                else if (k.isLeft(event) || k.isCancel(event)) threadZone = "list";
                else if (k.isAccept(event)) play(current);
                else if (k.isDetails(event)) openDetails();
                else if (k.isFilters(event)) toggleKeep(current);
                else return;
            }
            event.accepted = true;
            return;
        }

        // Library
        if (k.isUp(event)) {
            if (libIndex === 0 || !libraryEntries.length) { zone = "search"; searchCol = 0; }
            else setLibIndex(libIndex - 1);
        }
        else if (k.isDown(event)) setLibIndex(libIndex + 1);
        else if (k.isLeft(event)) jumpLetter(-1);
        else if (k.isRight(event)) jumpLetter(1);
        else if (k.isPageUp(event)) setLibIndex(libIndex - 8);
        else if (k.isPageDown(event)) setLibIndex(libIndex + 8);
        else if (k.isAccept(event)) play(current);
        else if (k.isDetails(event)) openDetails();
        else if (k.isFilters(event)) toggleKeep(current);
        else if (k.isCancel(event)) switchView(fromConsole ? "consoles" : "home");
        else return;
        event.accepted = true;
    }

    // ---------- surface ----------

    Rectangle { anchors.fill: parent; color: root.ground }

    // Top line: the library destinations and Settings.
    Item {
        id: nav
        x: px(64)
        y: px(36)
        width: root.width - px(128)
        height: fs(40)
        visible: overlay === ""

        Row {
            spacing: px(28)
            Repeater {
                model: root.views.map(function(v) { return root.viewNames[v]; })
                delegate: Item {
                    width: navLabel.implicitWidth + px(32)
                    height: nav.height
                    readonly property bool active: root.views[index] === root.view
                    Icon { name: root.views[index]; width: px(22); height: width; ink: parent.active ? root.ink : root.quiet; y: px(5) }
                    Text {
                        id: navLabel
                        x: px(32)
                        text: modelData
                        color: parent.active ? root.ink : root.quiet
                        font.family: root.sans
                        font.pixelSize: fs(26)
                        font.weight: parent.active ? Font.DemiBold : Font.Normal
                    }
                    Rectangle {
                        visible: root.zone === "nav" && root.navIndex === index
                        anchors.top: navLabel.bottom
                        anchors.topMargin: px(6)
                        width: navLabel.width
                        height: Math.max(2, px(3))
                        color: root.ink
                    }
                    MouseArea {
                        objectName: "navTab_" + index
                        anchors.fill: parent
                        anchors.margins: -px(12)
                        onClicked: root.navActivate(index)
                    }
                }
            }
        }

        Item {
            anchors.right: parent.right
            width: lookLabel.implicitWidth + px(30)
            height: nav.height
            Icon { name: "settings"; width: px(22); height: width; ink: root.quiet; y: px(5) }
            Text {
                id: lookLabel
                x: px(30)
                text: "Settings"
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(24)
            }
            Rectangle {
                visible: root.zone === "nav" && root.navIndex === root.views.length
                anchors.top: lookLabel.bottom
                anchors.topMargin: px(6)
                width: lookLabel.width
                height: Math.max(2, px(3))
                color: root.ink
            }
            MouseArea {
                objectName: "navTab_" + root.views.length
                anchors.fill: parent
                anchors.margins: -px(12)
                onClicked: root.navActivate(root.views.length)
            }
        }
    }

    // ---------- Consoles: a direct path into each system ----------

    Item {
        id: consoles
        anchors.fill: parent
        visible: root.view === "consoles" && root.overlay === ""
        Text {
            x: px(64); y: px(103)
            text: "Choose a console"; color: root.ink
            font.family: root.sans; font.pixelSize: fs(30)
        }
        Text {
            x: px(64); y: px(147)
            text: "Pick a system to browse its games."
            color: root.quiet; font.family: root.sans; font.pixelSize: fs(19)
            width: parent.width - px(128); wrapMode: Text.Wrap
        }
        GridView {
            id: consoleGrid
            objectName: "consoleGrid"
            x: px(64); y: px(205)
            width: parent.width - px(128); height: parent.height - y - px(108)
            cellWidth: width / 3; cellHeight: px(174)
            model: root.consoleSystems; currentIndex: root.consoleIndex
            clip: true; boundsBehavior: Flickable.StopAtBounds
            delegate: Rectangle {
                width: consoleGrid.cellWidth - px(16); height: consoleGrid.cellHeight - px(16)
                color: root.slab
                border.width: root.zone === "content" && root.consoleIndex === index ? Math.max(2, px(3)) : 0
                border.color: root.ink
                Text {
                    x: px(22); y: px(22); width: parent.width - px(44)
                    text: modelData.name; color: root.ink
                    font.family: root.sans; font.pixelSize: fs(25); font.weight: Font.DemiBold
                    wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
                }
                Text {
                    x: px(22); anchors.bottom: parent.bottom; anchors.bottomMargin: px(20)
                    width: parent.width - px(44)
                    text: root.consoleReady(modelData.id) + " set up here · " + modelData.count + " games in catalogue"
                    color: root.quiet; font.family: root.sans; font.pixelSize: fs(18)
                    wrapMode: Text.Wrap
                }
                MouseArea {
                    objectName: "consoleCard_" + index
                    anchors.fill: parent
                    onClicked: { root.zone = "content"; root.selectConsole(index); root.browseConsole(); }
                }
            }
        }
        Text {
            visible: !root.consoleSystems.length; x: px(64); y: px(230)
            text: "No systems in this catalogue yet."; color: root.quiet
            font.family: root.sans; font.pixelSize: fs(26)
        }
    }

    // ---------- Apps: existing Android app routes, separate from game discovery ----------

    Item {
        id: appsView
        anchors.fill: parent
        visible: root.view === "apps" && root.overlay === ""
        readonly property real rowH: Math.round(fs(30) * 2.6)
        ListView {
            id: appsList
            x: px(40); y: px(140)
            width: Math.round(root.width * 0.44)
            height: Math.floor((root.height - px(244)) / appsView.rowH) * appsView.rowH
            clip: true
            model: root.appsEntries
            currentIndex: root.appIndex
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: appsView.rowH
            preferredHighlightEnd: height - appsView.rowH
            highlightMoveDuration: 0
            keyNavigationEnabled: false
            boundsBehavior: Flickable.StopAtBounds
            delegate: Item {
                width: appsList.width; height: appsView.rowH
                readonly property bool isCurrent: index === root.appIndex
                Rectangle {
                    visible: parent.isCurrent && root.zone === "content"
                    width: Math.max(3, px(4)); height: fs(30)
                    anchors.verticalCenter: parent.verticalCenter; color: root.ink
                }
                Column {
                    x: px(24); width: parent.width - px(40)
                    anchors.verticalCenter: parent.verticalCenter; spacing: px(3)
                    Text {
                        width: parent.width; text: modelData.title
                        color: parent.parent.isCurrent ? root.ink : modelData.launchable ? root.rowQuiet : root.rowFaint
                        font.family: root.sans; font.pixelSize: fs(30)
                        font.weight: parent.parent.isCurrent ? Font.DemiBold : Font.Normal
                        elide: Text.ElideRight
                    }
                    Text {
                        width: parent.width; text: Lib.appPurpose(modelData)
                        color: root.faint; font.family: root.sans; font.pixelSize: fs(19)
                        elide: Text.ElideRight
                    }
                }
                MouseArea {
                    objectName: "appRow_" + index
                    anchors.fill: parent
                    onClicked: { root.zone = "content"; if (index === root.appIndex) root.play(root.appCurrent); else root.setAppIndex(index); }
                }
            }
        }
        Column {
            x: root.width * 0.51; y: px(154)
            width: root.width - x - px(64); spacing: px(20)
            visible: root.appCurrent !== null
            Text {
                width: parent.width; text: root.appCurrent ? root.appCurrent.title : ""
                color: root.ink; font.family: root.sans; font.pixelSize: fs(44); font.weight: Font.DemiBold
                maximumLineCount: 2; elide: Text.ElideRight; wrapMode: Text.Wrap
            }
            Text {
                width: parent.width; text: Lib.appPurpose(root.appCurrent)
                color: root.quiet; font.family: root.sans; font.pixelSize: fs(26); wrapMode: Text.Wrap
            }
            Text {
                width: parent.width; text: root.appCurrent ? Lib.routeSentence(root.appCurrent) : ""
                color: root.faint; font.family: root.sans; font.pixelSize: fs(24); wrapMode: Text.Wrap
            }
        }
        Text {
            visible: !root.appsEntries.length; x: px(64); y: px(160)
            width: root.width - px(128)
            text: "No Android app entries in this catalogue yet."
            color: root.quiet; font.family: root.sans; font.pixelSize: fs(26); wrapMode: Text.Wrap
        }
    }

    // ---------- Home: one shelf ----------

    Item {
        id: home
        anchors.fill: parent
        visible: root.view === "home" && root.overlay === ""

        readonly property real shelfBase: Math.round(root.height * 0.64)
        readonly property real focusH: Math.min(px(450), shelfBase - px(150))
        readonly property real area: focusH * focusH * 2 / 3

        Item {
            id: shelf
            y: px(96)
            width: parent.width
            height: home.shelfBase - y + px(16)
            clip: true

            Row {
                id: shelfRow
                property real focusX: 0
                height: home.shelfBase - shelf.y
                spacing: px(36)
                x: px(64) - focusX
                Behavior on x { NumberAnimation { duration: 120; easing.type: Easing.OutCubic } }

                Repeater {
                    id: shelfRepeater
                    model: root.homeEntries
                    delegate: Item {
                        id: cell
                        readonly property bool isCurrent: index === root.homeIndex
                        readonly property real k: isCurrent ? 1 : 0.72
                        readonly property var fit: Lib.fitArea(cover.ratio, home.area * k * k, root.width * 0.55 * k, home.focusH * k)
                        width: fit.w + (root.homeGapAfter[modelData.id] ? px(60) : 0)
                        height: shelfRow.height
                        // Earlier covers leave the screen rather than showing as a cropped sliver.
                        opacity: index < root.homeIndex ? 0 : 1

                        Binding {
                            target: shelfRow
                            property: "focusX"
                            value: cell.x
                            when: cell.isCurrent
                            restoreMode: Binding.RestoreNone
                        }

                        ArtView {
                            id: cover
                            entry: modelData
                            width: cell.fit.w
                            height: cell.fit.h
                            anchors.bottom: parent.bottom
                            fontFamily: root.sans
                            slabColor: root.slab
                            textColor: root.ink
                            quietColor: root.quiet
                            veilColor: root.ground
                            veil: 1 - (cell.isCurrent ? 1 : 0.7) * (modelData.launchable ? 1 : 0.55)
                        }

                        Rectangle {
                            visible: cell.isCurrent && root.zone === "content"
                            x: cover.x - px(9)
                            y: cover.y - px(9)
                            width: cover.width + px(18)
                            height: cover.height + px(18)
                            color: "transparent"
                            border.color: root.ink
                            border.width: Math.max(2, px(3))
                        }
                    }
                }
            }

            MouseArea {
                id: shelfTouch
                anchors.fill: parent
                property real startX: 0
                onPressed: function(mouse) { startX = mouse.x; }
                onReleased: function(mouse) {
                    root.zone = "content";
                    var dx = mouse.x - startX;
                    if (Math.abs(dx) > px(40)) {
                        var steps = Math.max(1, Math.round(Math.abs(dx) / px(260)));
                        root.moveHome(dx < 0 ? steps : -steps);
                        return;
                    }
                    for (var i = 0; i < shelfRepeater.count; i++) {
                        var it = shelfRepeater.itemAt(i);
                        if (!it || it.opacity === 0)
                            continue;
                        var p = shelfTouch.mapToItem(it, mouse.x, mouse.y);
                        if (p.x >= 0 && p.x <= it.width) {
                            if (i === root.homeIndex) root.openDetails();
                            else root.homeIndex = i;
                            return;
                        }
                    }
                }
            }
        }

        Column {
            x: px(64)
            y: home.shelfBase + px(34)
            width: root.width - px(128)
            spacing: px(6)
            visible: root.homeCurrent !== null

            Text {
                width: parent.width
                text: root.homeCurrent ? root.homeCurrent.title : ""
                color: root.ink
                font.family: root.sans
                font.pixelSize: fs(44)
                font.weight: Font.DemiBold
                maximumLineCount: 1
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                text: root.quietLine(root.homeCurrent, root.personalRev)
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(24)
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: root.homeCurrent !== null
                text: root.homeReason(root.homeCurrent)
                color: root.faint
                font.family: root.sans
                font.pixelSize: fs(24)
                maximumLineCount: 1
                elide: Text.ElideRight
            }
            Text {
                objectName: "homeCheckpoint"
                width: parent.width
                visible: root.homeCurrent !== null && (root.homeCurrent.checkpoint !== "" || root.canEdit)
                text: root.homeCheckpoint(root.homeCurrent) || "Add a stopping note · " + root.kDetails + " Details"
                color: root.homeCurrent && root.homeCurrent.checkpoint ? root.quiet : root.faint
                font.family: root.sans
                font.pixelSize: fs(24)
                maximumLineCount: root.wide ? 1 : 2
                elide: Text.ElideRight
                wrapMode: Text.Wrap
                MouseArea {
                    objectName: "homeNote"
                    anchors.fill: parent
                    enabled: root.canEdit && root.homeCurrent !== null
                    onClicked: root.openText("checkpoint", root.homeCurrent.id)
                }
            }
        }

        Column {
            x: px(64)
            y: home.shelfBase - px(120)
            width: root.width - px(128)
            spacing: px(10)
            visible: root.homeEntries.length === 0

            Text {
                text: root.allEntries.length ? "Nothing on Home yet." : "The library is empty."
                color: root.ink
                font.family: root.sans
                font.pixelSize: fs(36)
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                wrapMode: Text.Wrap
                text: root.allEntries.length
                      ? "Open Library with " + root.kNext + " and keep a game with " + root.kKeep + "."
                      : "Pegasus found no games in the exported metadata."
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(26)
            }
        }
    }

    // ---------- Library: an index beside one cover ----------

    Item {
        id: library
        anchors.fill: parent
        visible: root.view === "library" && root.overlay === ""

        readonly property real listX: px(40)
        readonly property real listW: root.wide ? root.width * 0.40 - listX : px(660)
        readonly property real listTop: px(156)
        readonly property real listBottom: root.height - px(104)
        readonly property real rowH: Math.round(fs(30) * 2.1)
        readonly property real panelX: root.wide ? Math.round(root.width * 0.42) : px(736)
        readonly property real panelW: root.wide ? Math.round(root.width * 0.29) : px(480)
        readonly property real panelBase: root.wide ? listBottom - px(8) : listBottom - px(84)
        readonly property real panelH: panelBase - listTop

        // Search line, with the one filter and sort control at its end.
        Item {
            id: searchLine
            x: library.listX + px(24)
            y: px(100)
            width: library.listW - px(24)
            height: fs(36)

            Rectangle {
                visible: root.zone === "search" && root.searchCol === 0
                x: -px(24)
                width: Math.max(3, px(4))
                height: fs(28)
                anchors.verticalCenter: parent.verticalCenter
                color: root.ink
            }
            Item {
                id: searchBox
                width: parent.width - filterControl.width - px(24)
                height: parent.height
                TextInput {
                    id: searchInput
                    objectName: "searchInput"
                    anchors.fill: parent
                    verticalAlignment: TextInput.AlignVCenter
                    color: root.ink
                    selectionColor: root.quiet
                    font.family: root.sans
                    font.pixelSize: fs(26)
                    clip: true
                    inputMethodHints: Qt.ImhNoPredictiveText
                    onTextChanged: {
                        var keep = root.libCurrent ? root.libCurrent.id : "";
                        root.searchText = text;
                        root.rebuildLibrary(keep);
                    }
                    onActiveFocusChanged: {
                        if (activeFocus)
                            return;
                        if (root.editingSearch)
                            root.editingSearch = false;
                        root.dropKeyboard();
                    }
                    Keys.onPressed: function(event) {
                        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Down
                                || event.key === 0x100000) {
                            root.endSearch(true);
                            event.accepted = true;
                        } else if (event.key === Qt.Key_Escape || event.key === 0x100001 || event.key === Qt.Key_Up) {
                            root.endSearch(false);
                            event.accepted = true;
                        }
                    }
                }
                Text {
                    visible: searchInput.text === "" && !searchInput.activeFocus
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Search"
                    color: root.faint
                    font.family: root.sans
                    font.pixelSize: fs(26)
                }
                MouseArea {
                    objectName: "searchTouch"
                    anchors.fill: parent
                    visible: !searchInput.activeFocus
                    onClicked: root.beginSearch()
                }
            }

            Item {
                id: filterControl
                anchors.right: parent.right
                width: Math.min(filterText.implicitWidth, searchLine.width * 0.62)
                height: parent.height
                Text {
                    id: filterText
                    width: parent.width
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.filterSummary()
                    color: root.zone === "search" && root.searchCol === 1 ? root.ink : (root.filtering ? root.quiet : root.faint)
                    font.family: root.sans
                    font.pixelSize: fs(22)
                    elide: Text.ElideLeft
                }
                Rectangle {
                    visible: root.zone === "search" && root.searchCol === 1
                    anchors.top: filterText.bottom
                    anchors.topMargin: px(4)
                    width: parent.width
                    height: Math.max(2, px(3))
                    color: root.ink
                }
                MouseArea {
                    objectName: "filterControl"
                    anchors.fill: parent
                    anchors.margins: -px(12)
                    onClicked: { root.zone = "search"; root.searchCol = 1; root.openPanel("filters", 0); }
                }
            }
        }

        ListView {
            id: libraryView
            x: library.listX
            y: library.listTop
            width: library.listW
            // Whole rows only, so the last title is never cut in half.
            height: Math.max(library.rowH, Math.floor((library.listBottom - library.listTop) / library.rowH) * library.rowH)
            clip: true
            model: root.libraryEntries
            interactive: true
            boundsBehavior: Flickable.StopAtBounds
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: library.rowH * 2
            preferredHighlightEnd: height - library.rowH * 2
            highlightMoveDuration: 0
            keyNavigationEnabled: false
            cacheBuffer: library.rowH * 6

            delegate: Item {
                width: libraryView.width
                height: library.rowH
                readonly property bool isCurrent: index === root.libIndex
                readonly property string sortValue: Lib.sortValueText(modelData, root.sortMode, root.now)

                Rectangle {
                    visible: parent.isCurrent && root.zone === "content"
                    x: 0
                    width: Math.max(3, px(4))
                    height: fs(30)
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.ink
                }
                Text {
                    x: px(24)
                    width: parent.width - px(24) - (valueText.visible ? valueText.implicitWidth + px(20) : 0)
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.title
                    color: parent.isCurrent ? root.ink : (modelData.launchable ? root.rowQuiet : root.rowFaint)
                    font.family: root.sans
                    font.pixelSize: fs(30)
                    font.weight: parent.isCurrent ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
                Text {
                    id: valueText
                    visible: text !== ""
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: parent.sortValue
                    color: parent.isCurrent ? root.quiet : root.rowFaint
                    font.family: root.sans
                    font.pixelSize: fs(22)
                }
                MouseArea {
                    objectName: "libraryRow_" + index
                    anchors.fill: parent
                    onClicked: {
                        root.zone = "content";
                        if (index === root.libIndex) root.openDetails();
                        else root.setLibIndex(index);
                    }
                }
            }
        }

        Column {
            x: library.listX + px(24)
            y: library.listTop + px(8)
            width: library.listW - px(24)
            spacing: px(18)
            visible: root.libraryEntries.length === 0

            Text {
                width: parent.width
                wrapMode: Text.Wrap
                text: root.rawEntries.length === 0 ? "The library is empty."
                      : root.searchText !== "" && root.filtering ? "Nothing matches “" + root.searchText + "” with these filters."
                      : root.searchText !== "" ? "Nothing matches “" + root.searchText + "”."
                      : "Nothing matches these filters."
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(28)
            }
            Text {
                visible: root.filtering
                text: root.kDetails + "  Clear filters"
                color: root.ink
                font.family: root.sans
                font.pixelSize: fs(26)
                font.weight: Font.DemiBold
                MouseArea {
                    objectName: "emptyClear"
                    anchors.fill: parent
                    anchors.margins: -px(14)
                    onClicked: root.clearFilters()
                }
            }
        }

        // One cover, bottom-aligned on a shared baseline.
        ArtView {
            id: panelArt
            readonly property var fit: Lib.fitArea(ratio, Math.min(library.panelW, library.panelH * 2 / 3) * Math.min(library.panelW * 1.5, library.panelH),
                                                    library.panelW, library.panelH)
            visible: root.libCurrent !== null
            entry: root.libCurrent
            x: library.panelX
            y: library.panelBase - fit.h
            width: fit.w
            height: fit.h
            decodeHeight: 960
            fontFamily: root.sans
            slabColor: root.slab
            textColor: root.ink
            quietColor: root.quiet
            veilColor: root.ground
            veil: root.libCurrent && !root.libCurrent.launchable ? 0.45 : 0
        }

        // Nova: one quiet caption under the cover.
        Column {
            visible: !root.wide && root.libCurrent !== null
            x: library.panelX
            y: library.panelBase + px(18)
            width: root.width - library.panelX - px(48)
            spacing: px(4)
            Text {
                width: parent.width
                visible: text !== ""
                text: root.libCurrent ? root.libCurrent.developer : ""
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(24)
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                text: root.quietLine(root.libCurrent, root.personalRev)
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(24)
                elide: Text.ElideRight
            }
        }

        // Legion: there is room for the facts without a press. Details has the rest.
        Item {
            visible: root.wide && root.libCurrent !== null
            x: library.panelX + library.panelW + px(32)
            y: library.listTop
            width: root.width - x - px(48)
            height: library.listBottom - library.listTop
            clip: true
        Column {
            width: parent.width
            spacing: px(14)
            Text {
                width: parent.width
                visible: text !== ""
                text: root.libCurrent ? [root.libCurrent.developer, root.libCurrent.genre, root.libCurrent.systemName].filter(function(x) { return x; }).join(", ") : ""
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(24)
                wrapMode: Text.Wrap
            }
            Repeater {
                model: root.detailLines(root.libCurrent, root.personalRev)
                delegate: Text {
                    width: parent.width
                    text: modelData.t
                    color: modelData.q ? root.quiet : root.ink
                    font.family: root.sans
                    font.pixelSize: fs(24)
                    wrapMode: Text.Wrap
                    lineHeight: 1.1
                }
            }
        }
        }
    }

    // ---------- Threads: kept groups and explained suggestions ----------

    Item {
        id: threadsView
        anchors.fill: parent
        visible: root.view === "threads" && root.overlay === ""

        readonly property real listX: px(40)
        readonly property real listW: root.wide ? Math.round(root.width * 0.28) : px(420)
        readonly property real areaTop: px(120)
        readonly property real areaBottom: root.height - px(104)
        readonly property real rowH: Math.round(fs(28) * 2.1)
        readonly property real panelX: listX + listW + px(48)
        readonly property real panelW: root.width - panelX - px(64)
        readonly property real membersW: Math.round(panelW * (root.wide ? 0.46 : 0.56))
        readonly property real memberRowH: Math.round(fs(26) * 1.9)

        ListView {
            id: threadList
            x: threadsView.listX
            y: threadsView.areaTop
            width: threadsView.listW
            height: Math.max(threadsView.rowH, Math.floor((threadsView.areaBottom - threadsView.areaTop) / threadsView.rowH) * threadsView.rowH)
            clip: true
            model: root.threads
            currentIndex: root.threadIndex
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: threadsView.rowH * 2
            preferredHighlightEnd: height - threadsView.rowH * 2
            highlightMoveDuration: 0
            keyNavigationEnabled: false
            boundsBehavior: Flickable.StopAtBounds

            delegate: Item {
                width: threadList.width
                height: threadsView.rowH
                readonly property bool isCurrent: index === root.threadIndex
                Rectangle {
                    visible: parent.isCurrent && root.zone === "content" && root.threadZone === "list"
                    width: Math.max(3, px(4))
                    height: fs(28)
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.ink
                }
                Text {
                    x: px(24)
                    width: parent.width - px(24) - originText.implicitWidth - px(16)
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.name
                    color: parent.isCurrent ? root.ink : root.rowQuiet
                    font.family: root.sans
                    font.pixelSize: fs(28)
                    font.weight: parent.isCurrent ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
                Text {
                    id: originText
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    text: Lib.originLabel(modelData)
                    color: root.rowFaint
                    font.family: root.sans
                    font.pixelSize: fs(20)
                }
                MouseArea {
                    objectName: "threadRow_" + index
                    anchors.fill: parent
                    onClicked: {
                        root.zone = "content";
                        if (index === root.threadIndex) root.openThread();
                        else { root.selectThread(index); root.threadZone = "list"; }
                    }
                }
            }
        }

        Column {
            x: threadsView.listX + px(24)
            y: threadsView.areaTop + px(8)
            width: root.width - px(128)
            spacing: px(12)
            visible: root.threads.length === 0
            Text {
                text: "No threads yet."
                color: root.ink
                font.family: root.sans
                font.pixelSize: fs(32)
                font.weight: Font.DemiBold
            }
            Text {
                width: Math.min(parent.width, px(820))
                wrapMode: Text.Wrap
                text: root.bridge
                      ? "Threads you keep and explained suggestions from the Device Library will appear here."
                      : "Kept threads and suggestions come from the Device Library service, which this build doesn't have. Games you keep are still on Home."
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(24)
            }
        }

        Column {
            id: threadHead
            visible: root.currentThread !== null
            x: threadsView.panelX
            y: threadsView.areaTop
            width: threadsView.panelW
            spacing: px(8)
            Text {
                width: parent.width
                text: root.currentThread ? root.currentThread.name : ""
                color: root.ink
                font.family: root.sans
                font.pixelSize: fs(36)
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: {
                    var t = root.currentThread;
                    if (!t) return "";
                    if (t.reason) return t.reason;
                    if (t.origin === "kept") return "Kept by you.";
                    return "Suggested, with no reason given.";
                }
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(24)
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: {
                    var t = root.currentThread;
                    if (!t) return "";
                    var bits = [];
                    if (t.origin === "suggested") bits.push("A suggestion until you keep it");
                    if (t.origin === "catalogue") bits.push("Grouped in the catalogue export");
                    if (t.source) bits.push("source: " + t.source);
                    if (t.absent) bits.push(t.absent + (t.absent === 1 ? " game isn't" : " games aren't") + " in this library");
                    return bits.join(", ") + (bits.length ? "." : "");
                }
                color: root.faint
                font.family: root.sans
                font.pixelSize: fs(22)
                wrapMode: Text.Wrap
            }
        }

        ListView {
            id: memberList
            x: threadsView.panelX - px(24)
            y: threadHead.y + threadHead.height + px(28)
            width: threadsView.membersW + px(24)
            height: Math.max(threadsView.memberRowH, Math.floor((threadsView.areaBottom - px(70) - y) / threadsView.memberRowH) * threadsView.memberRowH)
            clip: true
            model: root.currentThread ? root.currentThread.entries : []
            currentIndex: root.memberIndex
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: threadsView.memberRowH
            preferredHighlightEnd: height - threadsView.memberRowH
            highlightMoveDuration: 0
            keyNavigationEnabled: false
            boundsBehavior: Flickable.StopAtBounds

            delegate: Item {
                width: memberList.width
                height: threadsView.memberRowH
                readonly property bool isCurrent: index === root.memberIndex
                readonly property bool focused: isCurrent && root.threadZone === "members" && root.zone === "content"
                Rectangle {
                    visible: parent.focused
                    width: Math.max(3, px(4))
                    height: fs(26)
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.ink
                }
                Text {
                    x: px(24)
                    width: parent.width - px(24)
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.title
                    color: parent.focused ? root.ink : (modelData.launchable ? root.rowQuiet : root.rowFaint)
                    font.family: root.sans
                    font.pixelSize: fs(26)
                    font.weight: parent.focused ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
                MouseArea {
                    objectName: "memberRow_" + index
                    anchors.fill: parent
                    onClicked: {
                        root.zone = "content";
                        if (root.threadZone === "members" && index === root.memberIndex) root.openDetails();
                        else { root.threadZone = "members"; root.memberIndex = index; }
                    }
                }
            }
        }

        // Why this game is in the thread, for the one in focus.
        Text {
            x: threadsView.panelX
            y: threadsView.areaBottom - px(56)
            width: threadsView.panelW
            visible: text !== ""
            text: {
                var e = root.threadMember;
                var t = root.currentThread;
                if (!e || !t) return "";
                if (t.origin === "recommendations")
                    return e.recReason ? e.recReason + " (" + e.recSource + ")" : "Suggested by the " + e.recSource + ", with no reason given.";
                return root.quietLine(e, root.personalRev);
            }
            color: root.quiet
            font.family: root.sans
            font.pixelSize: fs(22)
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
        }

        ArtView {
            id: threadArt
            readonly property real boxX: threadsView.panelX + threadsView.membersW + px(32)
            readonly property real boxW: root.width - boxX - px(64)
            readonly property real boxH: threadsView.areaBottom - px(80) - memberList.y
            readonly property var fit: Lib.fitArea(ratio, boxW * Math.min(boxH, boxW * 1.5), boxW, boxH)
            visible: root.threadMember !== null && boxW > px(120)
            entry: root.threadMember
            x: boxX
            y: memberList.y + boxH - fit.h
            width: fit.w
            height: fit.h
            fontFamily: root.sans
            slabColor: root.slab
            textColor: root.ink
            quietColor: root.quiet
            veilColor: root.ground
            veil: root.threadZone === "members" ? (root.threadMember && !root.threadMember.launchable ? 0.45 : 0) : 0.35
        }
    }

    // ---------- Details ----------

    Item {
        id: details
        objectName: "detailsSurface"
        anchors.fill: parent
        visible: (root.overlay === "details" || root.overlay === "facts") && root.current !== null

        MouseArea { anchors.fill: parent }

        readonly property real artBoxW: root.wide ? px(300) : px(260)
        readonly property real artBoxH: root.wide ? px(450) : px(390)

        ArtView {
            id: detailArt
            readonly property var fit: Lib.fitArea(ratio, details.artBoxW * details.artBoxH, details.artBoxW * 1.6, details.artBoxH)
            entry: root.current
            x: px(64)
            y: px(64)
            width: fit.w
            height: fit.h
            decodeHeight: 720
            fontFamily: root.sans
            slabColor: root.slab
            textColor: root.ink
            quietColor: root.quiet
            veilColor: root.ground
        }

        Flickable {
            id: detailFlick
            // Wide capsule art pushes the text below it instead of beside it.
            readonly property bool below: detailArt.width > details.artBoxW * 1.05
            x: below ? px(64) : px(64) + detailArt.width + px(48)
            y: below ? detailArt.y + detailArt.height + px(36) : px(64)
            width: root.width - x - px(64)
            height: root.height - y - px(120)
            contentHeight: detailColumn.height
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            Column {
                id: detailColumn
                width: detailFlick.width
                spacing: px(16)

                Text {
                    width: parent.width
                    text: root.current ? root.current.title : ""
                    color: root.ink
                    font.family: root.sans
                    font.pixelSize: fs(40)
                    font.weight: Font.DemiBold
                    wrapMode: Text.Wrap
                    maximumLineCount: 3
                    elide: Text.ElideRight
                }
                Text {
                    width: parent.width
                    visible: text !== ""
                    text: root.current ? [root.current.developer, root.current.genre, root.current.systemName].filter(function(x) { return x; }).join(", ") : ""
                    color: root.quiet
                    font.family: root.sans
                    font.pixelSize: fs(24)
                    wrapMode: Text.Wrap
                }
                DeviceStates {
                    visible: root.overlay === "details" && root.current && root.current.systemId !== "androidapps"
                    entry: root.current; ink: root.ink; quiet: root.quiet; fontFamily: root.sans; size: fs(21)
                }
                Item { width: 1; height: px(8) }
                Repeater {
                    model: root.overlay === "facts" ? root.detailLines(root.current, root.personalRev) : root.overviewLines(root.current, root.personalRev)
                    delegate: Item {
                        width: parent.width; height: lineText.implicitHeight
                        Icon { visible: root.overlay === "details"; name: modelData.icon || "info"; width: fs(24); height: width; ink: modelData.q ? root.quiet : root.ink }
                        Text {
                            id: lineText
                            x: root.overlay === "details" ? fs(36) : 0
                            width: parent.width - x
                            text: modelData.t; color: modelData.q ? root.quiet : root.ink
                            font.family: root.sans; font.pixelSize: modelData.q ? fs(24) : fs(26)
                            wrapMode: Text.Wrap; lineHeight: 1.12
                        }
                    }
                }
            }
        }
    }

    // ---------- Appearance, Filter and sort, Status, Threads picker ----------

    Item {
        id: panel
        anchors.fill: parent
        visible: root.isListPanel()

        MouseArea { anchors.fill: parent }

        readonly property real rowH: Math.round(fs(30) * 2.2)

        Text {
            id: panelHead
            x: px(64)
            y: px(64)
            width: root.width - px(128)
            text: root.panelTitle()
            maximumLineCount: 1
            elide: Text.ElideRight
            color: root.ink
            font.family: root.sans
            font.pixelSize: fs(40)
            font.weight: Font.DemiBold
        }

        CapacityBar {
            id: diskCapacity
            objectName: "diskCapacity"
            x: px(64); y: panelHead.y + panelHead.height + px(28)
            width: Math.min(root.width - px(128), px(860))
            visible: root.overlay === "storage"
            warning: root.light ? "#955100" : "#dca56a"
            evidence: Lib.storageCapacity(root.rawEntries)
            ink: root.ink; quiet: root.quiet; slab: root.slab; fontFamily: root.sans; size: fs(26)
        }
        ListView {
            id: panelList
            x: px(64)
            y: root.overlay === "storage" ? diskCapacity.y + diskCapacity.height + px(20) : panelHead.y + panelHead.height + px(34)
            width: Math.min(root.width - px(128), px(860))
            height: Math.min(count * panel.rowH, Math.floor((root.height - px(300) - y) / panel.rowH) * panel.rowH)
            clip: true
            model: panel.visible ? root.panelRows(root.personalRev) : []
            currentIndex: root.panelIndex
            highlightRangeMode: ListView.ApplyRange
            preferredHighlightBegin: panel.rowH
            preferredHighlightEnd: height - panel.rowH
            highlightMoveDuration: 0
            keyNavigationEnabled: false
            boundsBehavior: Flickable.StopAtBounds

            delegate: Item {
                width: panelList.width
                height: panel.rowH
                Rectangle { visible: root.overlay === "storage" && modelData.fraction !== undefined; x: px(24); y: parent.height - px(7); height: px(4); width: Math.max(0, (parent.width - px(24)) * (modelData.fraction || 0)); color: root.quiet }
                readonly property bool isCurrent: index === root.panelIndex
                Rectangle {
                    visible: parent.isCurrent
                    width: Math.max(3, px(4))
                    height: fs(30)
                    anchors.verticalCenter: parent.verticalCenter
                    color: root.ink
                }
                Text {
                    x: px(24)
                    width: px(400)
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.label
                    color: modelData.dim ? root.faint : parent.isCurrent ? root.ink : root.quiet
                    font.family: root.sans
                    font.pixelSize: fs(30)
                    font.weight: parent.isCurrent ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                }
                Text {
                    x: px(464)
                    width: parent.width - x
                    anchors.verticalCenter: parent.verticalCenter
                    text: modelData.value
                    color: parent.isCurrent ? root.ink : root.quiet
                    font.family: root.sans
                    font.pixelSize: fs(30)
                    elide: Text.ElideRight
                }
                MouseArea {
                    objectName: "panelRow_" + index
                    anchors.fill: parent
                    onClicked: root.panelActivate(index, 1)
                }
            }
        }

        Text {
            x: px(64)
            y: panelList.y + panelList.height + px(28)
            width: Math.min(root.width - px(128), px(860))
            wrapMode: Text.Wrap
            text: root.panelFooter(root.personalRev)
            color: root.faint
            font.family: root.sans
            font.pixelSize: fs(24)
        }
    }

    // ---------- A line of text: checkpoint or thread name ----------

    Item {
        id: textPanel
        anchors.fill: parent
        visible: root.overlay === "text"

        MouseArea { anchors.fill: parent }

        Column {
            x: px(64)
            y: px(64)
            width: Math.min(root.width - px(128), px(980))
            spacing: px(14)

            Text {
                text: root.textMode === "checkpoint" ? "Stopping note" : "New thread"
                color: root.ink
                font.family: root.sans
                font.pixelSize: fs(40)
                font.weight: Font.DemiBold
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: root.entryById[root.textTarget] ? root.entryById[root.textTarget].title : ""
                color: root.quiet
                font.family: root.sans
                font.pixelSize: fs(26)
                elide: Text.ElideRight
            }
            Item { width: 1; height: px(16) }
            Item {
                width: parent.width
                height: fs(44)
                TextInput {
                    id: textInput
                    objectName: "textInput"
                    anchors.fill: parent
                    verticalAlignment: TextInput.AlignVCenter
                    color: root.ink
                    selectionColor: root.quiet
                    font.family: root.sans
                    font.pixelSize: fs(30)
                    clip: true
                    maximumLength: 280
                    onActiveFocusChanged: {
                        if (activeFocus)
                            return;
                        if (root.editingText)
                            root.editingText = false;
                        root.dropKeyboard();
                    }
                    Keys.onPressed: function(event) {
                        if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === 0x100000) {
                            root.endText(true);
                            event.accepted = true;
                        } else if (event.key === Qt.Key_Escape || event.key === 0x100001) {
                            root.endText(false);
                            event.accepted = true;
                        }
                    }
                }
                Text {
                    visible: textInput.text === "" && !textInput.activeFocus
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.textMode === "checkpoint" ? "Where you stopped" : "Name"
                    color: root.faint
                    font.family: root.sans
                    font.pixelSize: fs(30)
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: Math.max(1, px(2))
                    color: textInput.activeFocus ? root.ink : root.faint
                }
                MouseArea {
                    objectName: "textTouch"
                    anchors.fill: parent
                    visible: !textInput.activeFocus
                    onClicked: root.beginText()
                }
            }
            Item { width: 1; height: px(12) }
            Text {
                width: parent.width
                wrapMode: Text.Wrap
                text: root.textMode === "checkpoint"
                      ? "Write where you stopped. Saved here first, synced when connected. Leave it empty to clear it."
                      : "A small group you keep, named for the reason it exists."
                color: root.faint
                font.family: root.sans
                font.pixelSize: fs(24)
            }
        }
    }

    // ---------- Button hints ----------

    Item {
        x: px(64)
        y: root.height - px(76)
        width: root.width - px(128)
        height: fs(32)

        Row {
            spacing: px(40)
            visible: root.overlay !== "details"
            Repeater {
                model: root.hints()
                delegate: Item {
                    width: hintRow.implicitWidth
                    height: fs(32)
                    Row {
                        id: hintRow
                        spacing: px(10)
                        Text {
                            text: modelData.k
                            color: root.ink
                            font.family: root.sans
                            font.pixelSize: fs(24)
                            font.weight: Font.DemiBold
                        }
                        Text {
                            text: modelData.l
                            color: root.quiet
                            font.family: root.sans
                            font.pixelSize: fs(24)
                        }
                    }
                    MouseArea {
                        objectName: "hint_" + modelData.a
                        anchors.fill: parent
                        anchors.margins: -px(14)
                        onClicked: root.runHint(modelData.a)
                    }
                }
            }
        }

        // Details: the actions themselves, one in focus.
        Row {
            spacing: px(36)
            visible: root.overlay === "details" || root.overlay === "facts"
            Repeater {
                model: root.overlay === "details" ? root.detailActions() : []
                delegate: Item {
                    width: actionLabel.implicitWidth
                    height: fs(32)
                    readonly property bool isCurrent: index === root.detailAction
                    Text {
                        id: actionLabel
                        text: modelData.l
                        color: parent.isCurrent ? root.ink : root.quiet
                        font.family: root.sans
                        font.pixelSize: fs(24)
                        font.weight: parent.isCurrent ? Font.DemiBold : Font.Normal
                    }
                    Rectangle {
                        visible: parent.isCurrent
                        anchors.top: actionLabel.bottom
                        anchors.topMargin: px(4)
                        width: actionLabel.width
                        height: Math.max(2, px(3))
                        color: root.ink
                    }
                    MouseArea {
                        objectName: "action_" + modelData.a
                        anchors.fill: parent
                        anchors.margins: -px(14)
                        onClicked: root.runDetailAction(index)
                    }
                }
            }
        }

        Text {
            anchors.right: parent.right
            visible: root.notice !== ""
            width: Math.min(implicitWidth, parent.width * 0.5)
            horizontalAlignment: Text.AlignRight
            elide: Text.ElideRight
            text: root.notice
            color: root.quiet
            font.family: root.sans
            font.pixelSize: fs(22)
        }

        Text {
            anchors.right: parent.right
            visible: root.notice === "" && root.overlay === "details"
            text: root.kAccept + "  Select    " + root.kCancel + "  Back"
            color: root.faint
            font.family: root.sans
            font.pixelSize: fs(24)
            MouseArea {
                objectName: "detailsBack"
                anchors.fill: parent
                anchors.margins: -px(14)
                onClicked: root.overlay = ""
            }
        }

        Row {
            anchors.right: parent.right
            visible: root.notice === "" && root.overlay === ""
            spacing: px(28)
            Text {
                visible: root.view !== "home"
                text: root.kPrev + "  " + root.viewNames[root.views[Math.max(0, root.views.indexOf(root.view) - 1)]]
                color: root.faint
                font.family: root.sans
                font.pixelSize: fs(24)
                MouseArea {
                    objectName: "viewPrev"
                    anchors.fill: parent
                    anchors.margins: -px(14)
                    onClicked: root.stepView(-1)
                }
            }
            Text {
                visible: root.views.indexOf(root.view) < root.views.length - 1
                text: root.kNext + "  " + root.viewNames[root.views[Math.min(root.views.length - 1, root.views.indexOf(root.view) + 1)]]
                color: root.faint
                font.family: root.sans
                font.pixelSize: fs(24)
                MouseArea {
                    objectName: "viewNext"
                    anchors.fill: parent
                    anchors.margins: -px(14)
                    onClicked: root.stepView(1)
                }
            }
        }
    }
}
