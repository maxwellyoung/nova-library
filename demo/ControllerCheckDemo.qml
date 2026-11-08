import QtQuick 2.15
import QtQuick.Window 2.15
import "generated/games.js" as DemoData

// Scripted, non-launching host for theme/ControllerCheck.qml. Mirrors the parts of Pegasus
// main.qml that decide where an unaccepted key goes: Cancel and Menu open the native menu.
// demo/controllercheck/main.cpp supplies `driver` and the native model.
Window {
    id: window
    visible: true
    width: fixtureWidth || 1280
    height: fixtureHeight || 960
    title: "Nova controller check — scripted fixture"
    color: "#0c0d0e"

    FontLoader { id: reviewFont; source: fixtureFont }
    property var global: ({ fonts: { sans: reviewFont.status === FontLoader.Ready ? reviewFont.name : Qt.application.font.family } })
    property var deviceLibrary: null
    property var romCloud: null
    property int menuOpens: 0
    property var stopHint: null

    function gamepadKey(n) { return 0x100000 + n; }
    function named(keyboard, pad) {
        return (fixtureKeyboardLabels ? [keyboard] : [keyboard, "Gamepad (" + pad + ")"]).map(function(n) { return { name: function() { return n; } }; });
    }
    property QtObject api: QtObject {
        signal gameFileLaunched(var file)
        signal gameFileFinished(var file)
        property QtObject allGames: QtObject {
            property int count: DemoData.games.length
            function get(index) {
                var source = DemoData.games[index];
                return {
                    title: source.title, sortBy: source.sortBy, developer: source.developer,
                    genre: source.genre, missing: source.missing, lastPlayed: source.lastPlayed,
                    favorite: false, playCount: 0, extra: source.extra,
                    assets: { boxFront: Qt.resolvedUrl("generated/" + source.cover).toString() },
                    files: { count: 1, get: function() { return { path: source.file }; } },
                    launch: function() { console.error("CONTROLLER_FIXTURE_FAIL: a launch was requested"); Qt.exit(1); }
                };
            }
        }
        property QtObject memory: QtObject {
            property var values: ({})
            function has(key) { return Object.prototype.hasOwnProperty.call(values, key); }
            function get(key) { return values[key]; }
            function set(key, value) { values[key] = value; }
            function unset(key) { delete values[key]; }
        }
        // Pegasus AppSettings default_keymap, including its keyboard alternatives.
        property QtObject keys: QtObject {
            property var accept: window.named("Return", "A")
            property var cancel: window.named("Esc", "B")
            property var details: window.named("I", "X")
            property var filters: window.named("F", "Y")
            property var prevPage: window.named("Q", "L1")
            property var nextPage: window.named("E", "R1")
            function isAccept(e) { return e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === window.gamepadKey(0); }
            function isCancel(e) { return e.key === Qt.Key_Escape || e.key === Qt.Key_Backspace || e.key === window.gamepadKey(1); }
            function isDetails(e) { return e.key === Qt.Key_I || e.key === window.gamepadKey(2); }
            function isFilters(e) { return e.key === Qt.Key_F || e.key === window.gamepadKey(3); }
            function isPrevPage(e) { return e.key === Qt.Key_Q || e.key === Qt.Key_A || e.key === window.gamepadKey(4); }
            function isNextPage(e) { return e.key === Qt.Key_E || e.key === Qt.Key_D || e.key === window.gamepadKey(7); }
            function isPageUp(e) { return e.key === Qt.Key_PageUp || e.key === window.gamepadKey(5); }
            function isPageDown(e) { return e.key === Qt.Key_PageDown || e.key === window.gamepadKey(8); }
            function isMenu(e) { return e.key === Qt.Key_F1 || e.key === window.gamepadKey(11); }
            function isLeft(e) { return e.key === Qt.Key_Left; }
            function isRight(e) { return e.key === Qt.Key_Right; }
            function isUp(e) { return e.key === Qt.Key_Up; }
            function isDown(e) { return e.key === Qt.Key_Down; }
        }
    }

    FocusScope {
        anchors.fill: parent
        focus: true
        Loader {
            id: themeLoader
            anchors.fill: parent
            focus: true
            source: "../theme/theme.qml"
            onLoaded: item.focus = true
            Keys.onPressed: {
                if (window.api.keys.isCancel(event) || window.api.keys.isMenu(event)) {
                    event.accepted = true;
                    window.menuOpens++;
                }
            }
        }
    }

    function fail(reason) { console.error("CONTROLLER_FIXTURE_FAIL: " + reason); Qt.exit(1); }
    function require(value, reason) { if (!value) throw new Error(reason); }
    function find(item, name) {
        if (item.objectName === name) return item;
        var kids = item.children || [];
        for (var i = 0; i < kids.length; i++) { var hit = find(kids[i], name); if (hit) return hit; }
        return null;
    }
    function hintLabels() {
        return ui().hints().map(function(h) { return h.l; }).join("|");
    }
    function ui() { return themeLoader.item; }
    function panel() { return find(ui(), "controllerCheckPanel"); }
    function text(name) { return find(panel(), name).text; }
    function look(name) { return find(panel(), name).look; }
    function shot(name) { require(driver.grab(name), "could not retain image " + name); }
    function buttons() { var d = controllerCheck.state.devices; return d.length ? d[0].buttons : {}; }
    function stickInvariant() { require(controllerCheck.state.physicalAccepted === false, "physical acceptance claimed"); }
    function back() {
        require(driver.key(Qt.Key_Back, true) === true, "Back press not accepted");
        require(driver.key(Qt.Key_Back, false) === true, "Back release not accepted");
    }
    function tap(name) { driver.pad(name, true); driver.pad(name, false); }

    function toSettings(scrollTo) {
        var view = ui();
        view.setAppearance("surface", fixtureLight ? "light" : "dark");
        view.setAppearance("size", fixtureLarge ? "large" : "standard");
        // The real path: Up into the top line, across to Settings, A to open. No direct calls.
        tap("up");
        for (var i = 0; i < 5; i++) tap("right");
        require(view.zone === "nav" && view.navIndex === 5, "top line did not reach Settings");
        tap("south");
        require(view.overlay === "settings", "A did not open Settings");
        for (var j = 0; j < scrollTo; j++) tap("down");
    }

    readonly property var everyControl: ["up","down","left","right","north","south","east","west","l1","l2","l3","r1","r2","r3","select","start","guide"]

    property var script: ({
        settingsback: [
            function() { driver.connectPad(); toSettings(7); tap("south"); },
            function() {
                back();
                require(ui().overlay === "settings", "controller Back did not reach Settings");
                require(driver.key(Qt.Key_Back, true), "Settings did not consume Android Back");
                driver.key(Qt.Key_Back, false);
                require(ui().overlay === "" && menuOpens === 0, "Settings Back escaped into the native menu");
                var panels = ["settings", "appearance", "storage", "controls", "refresh", "about", "guide", "checks", "filters", "status", "threadpick"];
                panels.forEach(function(name) {
                    ui().overlay = "";
                    ui().openPanel(name, 0);
                    require(driver.key(Qt.Key_Back, true), name + " did not consume Android Back");
                    driver.key(Qt.Key_Back, false);
                    require(ui().overlay !== name && menuOpens === 0, name + " did not follow its existing reverse path");
                });
                shot("settings-back-complete");
            }
        ],
        reviewfocus: [
            function() { driver.connectPad(); toSettings(7); tap("south"); },
            function() { tap("south"); },
            function() { tap("select"); back(); },
            function() { tap("west"); },
            function() {
                require(panel().mode === "review", "report review missing");
                stopHint = panel().preview.json;
                driver.appFocus(false);
            },
            function() {
                require(panel().previewStale && panel().preview.json === stopHint, "focus loss silently replaced the preview");
                require(hintLabels().indexOf("Save private copy") === -1, "stale focus report offered Save");
                require(text("controllerCheckStatus").indexOf("Report details changed") === 0, "focus change blamed controller hardware");
                shot("review-focus-lost");
                driver.appFocus(true);
            },
            function() {
                require(!panel().previewStale && panel().preview.json === stopHint, "identical restored report did not match original bytes");
                require(controllerCheck.state.captureEnabled === false, "focus reopened capture during review");
                tap("east");
                require(panel().mode === "stopped" && driver.reports().length === 0, "cancel wrote a report");
                shot("review-focus-restored");
            }
        ],
        flow: [
            function() { driver.connectPad(); toSettings(7); },
            function() {
                var row = ui().panelRows(0)[7];
                require(row.label === "Controller check", "row missing: " + row.label);
                require(ui().panelRows(0)[8].label === "About Nova" && ui().panelRows(0)[6].label === "Cloud library", "Settings order changed");
                require(ui().panelFooter(0).indexOf("nothing leaves") !== -1, "footer missing");
                require(controllerCheck.state.captureEnabled === false, "capture running before the check opened");
                shot("1-settings-row");
                tap("south");
            },
            function() {
                require(ui().overlay === "controller" && panel().mode === "stopped", "row did not open the check");
                require(controllerCheck.state.captureEnabled === false && controllerCheck.state.active === false, "opening alone started capture");
                require(hintLabels() === "Start check|Back", "ready hints: " + hintLabels());
                shot("2-ready");
                tap("east");
            },
            function() {
                require(ui().overlay === "settings" && ui().panelIndex === 7, "B did not return to the Controller row");
                tap("south");
            },
            function() {
                driver.pad("south", true);
                require(panel().mode === "capturing" && controllerCheck.state.captureEnabled === true, "A did not start capture");
                require(hintLabels() === "Stop check", "capture hints: " + hintLabels());
            },
            function() { driver.pad("south", false); },
            function() {
                // Every controller button, press, held repeat and release: none may leave capture.
                var view = ui(), startMenu = window.menuOpens, nav = view.navIndex, index = view.panelIndex;
                everyControl.forEach(function(c) {
                    require(driver.pad(c, true) === true, c + " press leaked past the theme");
                    require(view.overlay === "controller" && panel().mode === "capturing", c + " press changed the screen");
                    require(driver.padRepeat(c) === true, c + " repeat leaked");
                    require(driver.pad(c, false) === true, c + " release leaked");
                    require(view.overlay === "controller" && panel().mode === "capturing", c + " release changed the screen");
                });
                // Keyboard equivalents are mapped keys too, and a controller can present as one.
                [Qt.Key_Escape, Qt.Key_Backspace, Qt.Key_Return, Qt.Key_F1, Qt.Key_I, Qt.Key_F, Qt.Key_Q, Qt.Key_E, Qt.Key_F5].forEach(function(k) {
                    require(driver.key(k, true) === true && driver.key(k, false) === true, "keyboard key leaked: " + k);
                });
                require(window.menuOpens === startMenu, "a capture key reached the Pegasus menu");
                require(view.navIndex === nav && view.panelIndex === index, "capture moved launcher state");
                var pressed = buttons();
                everyControl.forEach(function(c) { require(pressed[c].pressObserved && pressed[c].releaseObserved, c + " not observed"); });
                console.log("CONTROLLER_FIXTURE: all 17 controls reserved; repeats consumed; menu untouched");
            },
            function() {
                everyControl.forEach(function(c) { require(look("pad_" + c) === "seen", "pressed control not held on the map: " + c); });
                stopHint = find(ui(), "hint_controller:stop");
                driver.pad("east", true);
                driver.stick("left-x", -0.72); driver.stick("left-y", 0.41);
                driver.stick("left-x", 0.96); driver.stick("left-y", -0.88);
                driver.stick("left-x", -0.52); driver.stick("left-y", 0.23);
                driver.pad("l2", true, 7, true, 0.62);
            },
            function() {
                require(look("pad_east") === "live", "held B not live");
                require(find(panel(), "stickLeft").live === true, "moved stick not live");
                require(text("controllerCheckStatus").indexOf("Press everything") === 0, "capture status: " + text("controllerCheckStatus"));
                // Rebuilding the hint on every event would drop a finger already on Stop.
                require(find(ui(), "hint_controller:stop") === stopHint, "input rebuilt the Stop target");
                shot("3-capture-live");
                // A burst far beyond any real controller: the display catches up to the last value.
                for (var i = 0; i < 4000; i++) driver.stick("left-y", (i % 200) / 100 - 1);
                driver.stick("left-y", 0.23);
                driver.pad("east", false);
                driver.pad("l2", false);
            },
            function() {
                require(find(panel(), "stickLeft").y_.raw === 0.23, "display did not settle on the last value");
                require(find(ui(), "hint_controller:stop") === stopHint, "burst rebuilt the Stop target");
            },
            function() {
                // Stop: press lights Back, the observer sees press and release, then capture ends.
                require(driver.key(Qt.Key_Back, true) === true, "Back press not accepted");
                require(panel().mode === "capturing", "Back acted on press, losing the observed release");
            },
            function() {
                require(look("pad_back") === "live", "Back press not shown");
                require(driver.key(Qt.Key_Back, false) === true, "Back release not accepted");
                require(panel().mode === "stopped" && ui().overlay === "controller", "first Back did not stop into the summary");
                var state = controllerCheck.state;
                require(state.captureEnabled === false && state.active === false, "capture still on after stop");
                require(state.systemBack.pressObserved && state.systemBack.releaseObserved, "Back press/release not in the report");
                require(state.backDeviceIdentity.indexOf("unavailable") === 0, "Back gained an identity");
                require(buttons().select.pressObserved, "Select lost");
                stickInvariant();
            },
            function() {
                require(hintLabels() === "Continue check|Review report|Back", "summary hints: " + hintLabels());
                require(text("controllerCheckStatus") === "17 of 17 buttons · 2 of 4 stick axes · 2 of 2 triggers", "tally: " + text("controllerCheckStatus"));
                require(text("controllerCheckDetail").indexOf("not a hardware pass") !== -1, "hardware caveat missing");
                require(text("controllerCheckDetail").indexOf("Trigger depth") !== -1, "trigger caveat missing");
                require(find(find(panel(), "stickLeft"), "stickPuck").visible === false, "reset stick still drawn as a live centre");
                shot("4-summary");
                // Stopped is really stopped: a stray axis changes nothing.
                var before = controllerCheck.preview().sha256;
                driver.stick("right-x", 0.5);
                require(controllerCheck.preview().sha256 === before, "event recorded after stop");
                tap("west");
            },
            function() {
                require(panel().mode === "review", "X did not open the report");
                var preview = panel().preview;
                require(preview.sent === false, "preview reports sent");
                require(text("controllerCheckReportText") === preview.json, "shown report differs from the digest's bytes");
                require(JSON.parse(preview.json).method === "injected" && JSON.parse(preview.json).physicalAccepted === false, "report claims");
                require(text("controllerCheckDetail").indexOf(preview.sha256.slice(0, 16)) !== -1 && text("controllerCheckDetail").indexOf("Not sent") !== -1, "report label");
                require(preview.json.indexOf("controller-checks") === -1 && text("controllerCheckStatus").indexOf("/") === -1, "report shows a path");
                require(hintLabels() === "Save private copy|Read|Back", "review hints: " + hintLabels());
                shot("5-review");
                driver.key(Qt.Key_Down, true); driver.key(Qt.Key_Down, true, true); driver.key(Qt.Key_Down, false);
                require(find(panel(), "controllerCheckReport").contentY > 0, "report does not scroll");
                require(driver.reports().length === 0, "written before approval");
                tap("east");
            },
            function() {
                require(panel().mode === "stopped" && panel().preview === null, "cancel kept the preview");
                require(driver.reports().length === 0, "cancel wrote a file");
                console.log("CONTROLLER_FIXTURE: preview cancel wrote nothing");
                tap("west");
            },
            function() {
                // A connection event invalidates the digest: never quietly re-approved.
                var approved = panel().preview.sha256;
                require(driver.disconnectPad(), "disconnect refused");
                require(panel().previewStale === true, "disconnect did not invalidate the preview");
                require(panel().preview.sha256 === approved, "preview silently refreshed");
                require(hintLabels() === "Review again|Read|Back", "stale hints: " + hintLabels());
                require(text("controllerCheckStatus").indexOf("can't be saved") !== -1, "stale wording");
                shot("6-review-stale");
                tap("south");
            },
            function() {
                require(panel().previewStale === false && driver.reports().length === 0, "Review again wrote or stayed stale");
                require(panel().preview.sha256 === controllerCheck.preview().sha256, "Review again did not show current bytes");
                driver.connectPad();
                require(panel().previewStale === true, "reconnect did not invalidate");
                tap("south");
            },
            function() {
                // Refused export keeps the same reviewed bytes and lets the user retry.
                require(driver.blockExports(true), "could not stage refusal");
                var approved = panel().preview.sha256;
                tap("south");
                require(panel().saveFailed === true && panel().savedName === "", "refusal not shown");
                require(panel().preview.sha256 === approved, "failure replaced the reviewed preview");
                require(hintLabels() === "Try again|Read|Back", "error hints: " + hintLabels());
                require(driver.reports().length === 0, "refused export wrote");
                shot("7-review-error");
                require(driver.blockExports(false), "could not clear refusal");
                tap("south");
            },
            function() {
                var saved = panel().savedName, reports = driver.reports();
                require(saved !== "" && reports.length === 1 && reports[0] === saved, "explicit approval did not write one new file: " + reports.join());
                require(/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}\.json$/.test(saved), "unsafe name");
                require(driver.reportMode(saved) === 384, "report is not owner-only");
                require(driver.readReport(saved) === panel().preview.json, "written bytes differ from the reviewed preview");
                require(text("controllerCheckStatus") === "Saved in Nova's private storage. Nothing was sent.", "saved wording");
                require(hintLabels() === "Done|Read|Back", "saved hints: " + hintLabels());
                shot("8-review-saved");
                tap("south");
                console.log("CONTROLLER_FIXTURE: exact reviewed bytes written once, mode 0600");
            },
            function() {
                require(panel().mode === "stopped", "Done did not return");
                back();
                require(ui().overlay === "settings" && ui().panelIndex === 7, "second Back did not leave to Settings");
            },
            function() {
                // Reopening is a continuation; the model has no reset, and the words must not imply one.
                tap("south");
                require(panel().mode === "stopped" && hintLabels() === "Continue check|Review report|Back", "reopen hints: " + hintLabels());
                require(text("controllerCheckDetail").indexOf("Continue adds to this session") !== -1, "continuation not stated");
                require(buttons().south.pressObserved, "session results lost");
                shot("9-reopened");
                tap("south");
            },
            function() {
                require(panel().mode === "capturing", "Continue did not resume");
                driver.touch(find(ui(), "hint_controller:stop"));
                require(panel().mode === "stopped" && controllerCheck.state.captureEnabled === false, "touch Stop failed");
                console.log("CONTROLLER_FIXTURE: touch Stop works");
                tap("south");
            },
            function() {
                // App focus: the model pauses and clears; ranges stay; a reset draws no centred stick.
                driver.stick("left-x", 0.8); driver.pad("south", true);
            },
            function() {
                require(find(find(panel(), "stickLeft"), "stickPuck").visible === true, "live stick not drawn");
                driver.appFocus(false);
            },
            function() {
                var state = controllerCheck.state;
                require(state.active === false && state.captureEnabled === true && state.lastResetReason === "focus-lost", "focus pause");
                require(panel().paused && text("controllerCheckStatus").indexOf("Paused") === 0, "pause not shown");
                require(find(find(panel(), "stickLeft"), "stickPuck").visible === false, "reset drawn as observed centre");
                require(look("pad_south") === "seen", "reset shown as a live press");
                require(buttons().south.liveValueObserved === false, "live value survived a reset");
                require(find(panel(), "stickLeft").x_.maximum === 0.96, "observed range lost");
                shot("10-paused");
                driver.appFocus(true);
            },
            function() {
                require(panel().mode === "capturing" && panel().paused === false, "open capture did not resume with focus");
                driver.pad("south", false);
                driver.stick("left-x", 0.3);
                driver.disconnectPad();
            },
            function() {
                require(text("controllerCheckStatus").indexOf("Controller disconnected") === 0, "disconnect not shown: " + text("controllerCheckStatus"));
                require(find(find(panel(), "stickLeft"), "stickPuck").visible === false, "disconnect drawn as observed centre");
                shot("11-disconnected");
                back();
                require(panel().mode === "stopped", "Back while disconnected");
                driver.appFocus(false); driver.appFocus(true);
                require(controllerCheck.state.active === false && controllerCheck.state.captureEnabled === false, "app focus reopened a closed capture");
                console.log("CONTROLLER_FIXTURE: focus cannot reopen closed capture");
                driver.connectPad();
                tap("south");
            },
            function() {
                // The Pegasus menu (swipe, power dialog) disables the theme: capture must not run under it.
                require(panel().mode === "capturing", "resume before menu");
                themeLoader.enabled = false;
                require(panel().mode === "stopped" && controllerCheck.state.captureEnabled === false, "capture survived the native menu");
                themeLoader.enabled = true;
                ui().forceActiveFocus();
                console.log("CONTROLLER_FIXTURE: native menu stops capture");
                tap("east");
            },
            function() {
                require(ui().overlay === "settings", "B did not leave summary");
                tap("east");
                require(ui().overlay === "", "B did not close Settings");
                ui().openPanel("settings", 7);
                tap("south");
                tap("south");
                require(panel().mode === "capturing", "resume before teardown");
                themeLoader.source = "";
            },
            function() {
                require(controllerCheck.state.captureEnabled === false, "theme destruction left capture on");
                console.log("CONTROLLER_FIXTURE: destruction closes capture");
            }
        ],
        ready: [
            function() { driver.connectPad(); toSettings(7); tap("south"); },
            function() { require(panel().mode === "stopped", "not ready"); shot("ready"); }
        ],
        nodevice: [
            function() { toSettings(7); tap("south"); },
            function() {
                require(hintLabels() === "Start check|Back", "no-device hints");
                tap("south");
            },
            function() {
                require(text("controllerCheckStatus") === "No controller connected yet.", "no-device words: " + text("controllerCheckStatus"));
                require(look("pad_south") === "idle", "invented a press");
                shot("no-device");
                back();
                // Back itself was observed, so it is all the report can say, and it says so.
                require(panel().mode === "stopped" && hintLabels() === "Continue check|Review report|Back", "no-device stop: " + hintLabels());
                require(text("controllerCheckStatus") === "Only Android Back was seen. No controller connected.", "no-device summary: " + text("controllerCheckStatus"));
                shot("no-device-summary");
            }
        ],
        missing: [
            // A device reporting only one stick and no pressure: unseen stays unseen, never failed.
            function() { driver.connectPad(); toSettings(7); tap("south"); },
            function() { tap("south"); },
            function() {
                ["south","east","up","select","start","l1","r1"].forEach(tap);
                driver.stick("left-x", -1); driver.stick("left-x", 1); driver.stick("left-y", -0.98); driver.stick("left-y", 1);
            },
            function() {
                require(text("stickRangeX") !== undefined, "range text");
                shot("missing-capture");
                back();
            },
            function() {
                require(text("controllerCheckStatus") === "7 of 17 buttons · 2 of 4 stick axes · 0 of 2 triggers", "tally: " + text("controllerCheckStatus"));
                require(text("controllerCheckDetail").indexOf("isn't a fault") !== -1, "unseen called a fault");
                require(/fail/i.test(text("controllerCheckDetail") + text("controllerCheckStatus")) === false, "words a failure");
                var right = find(panel(), "stickRight");
                require(right.moved === false && right.live === false, "invented right stick");
                shot("missing-summary");
            }
        ],
        multi: [
            function() { driver.connectPad(3); driver.connectPad(7); toSettings(7); tap("south"); },
            function() { tap("south"); },
            function() { driver.pad("north", true, 3); },
            function() {
                require(panel().device.qtDeviceId === 3, "first device not shown");
                driver.pad("north", false, 3);
            },
            function() { driver.pad("start", true, 7); },
            function() {
                require(panel().device.qtDeviceId === 7, "display did not follow the controller in use");
                require(look("pad_north") === "idle" && look("pad_start") === "live", "showed another device's state");
                require(text("controllerCheckDevice") === "Qt device 7 · 2 seen", "device label: " + text("controllerCheckDevice"));
                shot("multi-capture");
                driver.pad("start", false, 7);
                back();
            },
            function() {
                require(hintLabels() === "Continue check|Review report|Controller|Back", "multi hints: " + hintLabels());
                tap("l1");
                require(panel().device.qtDeviceId === 3, "L1 did not switch device");
                require(look("pad_north") === "seen" && look("pad_south") === "idle" && look("pad_start") === "idle", "device 3 shows device 7's presses");
                shot("multi-summary");
            }
        ],
        order: [
            // Qt does not promise which QGamepadManager listener runs first. Either way the A that
            // starts capture is reported truthfully, and a lone release never reads as a press.
            function() { driver.connectPad(); toSettings(7); tap("south"); },
            function() { driver.pad("south", true, 7, false); },
            function() {
                require(panel().mode === "capturing", "A did not start capture");
                require(buttons().south.pressObserved === false, "press before capture was recorded");
                driver.pad("south", false, 7, false);
            },
            function() {
                require(buttons().south.releaseObserved === true && buttons().south.pressObserved === false, "lone release state");
                require(look("pad_south") === "idle", "lone release shown as pressed");
                back();
            },
            function() {
                require(text("controllerCheckStatus").indexOf("0 of 17 buttons") === 0, "lone release counted: " + text("controllerCheckStatus"));
                tap("east");
            },
            function() {
                tap("south");
                driver.pad("south", true, 7, true);
                require(panel().mode === "capturing" && buttons().south.pressObserved === true, "key-first start did not observe its press");
                driver.pad("south", false, 7, true);
                console.log("CONTROLLER_FIXTURE: both listener orders truthful");
            }
        ],
        absent: [
            function() { toSettings(7); },
            function() {
                var rows = ui().panelRows(0);
                require(typeof controllerCheck === "undefined" || fixtureBridge === "partial", "bridge unexpectedly present");
                require(rows.length === 8, "old build gained a row: " + rows.length);
                require(rows[7].label === "About Nova" && rows[6].label === "Cloud library", "old build order changed");
                require(ui().controllerBridge === null, "partial bridge accepted");
                shot("settings-" + fixtureBridge);
                tap("south");
                require(ui().overlay === "about", "About did not open at its old index");
                tap("east");
                require(ui().overlay === "settings" && ui().panelIndex === 7, "About return changed");
            }
        ],
        unconfigured: [
            function() { driver.connectPad(); toSettings(7); tap("south"); },
            function() { tap("south"); },
            function() { tap("south"); driver.key(Qt.Key_Back, true); driver.key(Qt.Key_Back, false); },
            function() { tap("west"); },
            function() {
                require(panel().mode === "review" && controllerCheck.state.privateExportConfigured === false, "unconfigured review");
                require(hintLabels() === "Read|Back", "save offered without private storage: " + hintLabels());
                require(text("controllerCheckStatus").indexOf("can't save") !== -1, "unconfigured words");
                shot("review-unconfigured");
                tap("south");
                require(driver.reports().length === 0, "wrote without private storage");
            }
        ]
    })

    Timer {
        id: runner
        interval: 80; repeat: true; running: true
        property int step: -1
        property int waited: 0
        onTriggered: {
            try {
                if (step < 0) {
                    if (!themeLoader.item || !themeLoader.item.ready) { if (++waited > 100) throw new Error("theme not ready"); return; }
                    driver.focusWindow();
                    themeLoader.item.forceActiveFocus();
                    step = 0;
                    return;
                }
                var steps = window.script[scenario];
                if (step >= steps.length) {
                    stop();
                    console.log("CONTROLLER_FIXTURE_PASS " + scenario);
                    Qt.exit(0);
                    return;
                }
                steps[step++]();
                // A slow grab must not eat the settle time the next step's checks rely on.
                restart();
            } catch (error) {
                stop();
                window.fail(scenario + " step " + (step - 1) + ": " + error);
            }
        }
    }
}
