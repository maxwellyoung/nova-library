import QtQuick 2.15
import QtQml 2.15
import "library.js" as Lib

// Optional diagnostic over the native `controllerCheck` context. The theme opens it only when
// that context exists. It shows what Qt delivered; a result here is never a hardware pass.
//
// While capturing, every controller button is the thing under test, so no mapped key does
// anything. Only an exact Qt.Key_Back or a touch on Stop ends capture. Back acts on release
// so the observer can record both events; both are accepted by this scoped flow.
Item {
    id: panel
    objectName: "controllerCheckPanel"

    property var check: null
    property var keyMap: null
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property color faint: "#777777"
    property color slab: "#1a1c1e"
    property color warning: "#dca56a"
    property string fontFamily: ""
    property string monoFamily: ""
    property real unit: 1
    property real textScale: 1
    property bool wide: false
    property real bottomLimit: height

    property string mode: "stopped"   // stopped | capturing | review
    property var snap: ({})
    property int followId: -1
    property var scores: ({})
    property bool backArmed: false
    property var preview: null        // the exact bytes on screen; only an explicit action replaces it
    property bool previewStale: false
    property bool saveFailed: false
    property string savedName: ""

    readonly property string kAccept: Lib.keyLabel(keyMap ? keyMap.accept : null, "A")
    readonly property string kCancel: Lib.keyLabel(keyMap ? keyMap.cancel : null, "B")
    readonly property string kDetails: Lib.keyLabel(keyMap ? keyMap.details : null, "X")
    readonly property string kPrev: Lib.keyLabel(keyMap ? keyMap.prevPage : null, "L1")
    readonly property string kNext: Lib.keyLabel(keyMap ? keyMap.nextPage : null, "R1")

    readonly property var devices: snap.devices || []
    readonly property var device: {
        for (var i = 0; i < devices.length; i++)
            if (devices[i].qtDeviceId === followId) return devices[i];
        return devices.length ? devices[0] : null;
    }
    readonly property bool capturing: mode === "capturing"
    readonly property bool paused: capturing && snap.active === false
    readonly property bool injected: snap.method === "injected"
    readonly property bool hasObservations: {
        var back = snap.systemBack;
        if (back && back.seen) return true;
        return devices.some(function(d) { return score(d) > 0; });
    }
    readonly property var names: ({ up: "Up", down: "Down", left: "Left", right: "Right", north: "Y", south: "A", east: "B", west: "X", l1: "L1", l2: "L2", l3: "L3", r1: "R1", r2: "R2", r3: "R3", select: "Select", start: "Start", guide: "Guide" })

    signal closed()

    function px(n) { return Math.round(n * unit); }
    function fs(n) { return Math.round(n * unit * textScale); }

    // ---------- lifecycle: capture is on only between start() and stop() ----------

    function refresh() {
        if (!check) return;
        var next = check.state;
        var known = scores, moved = -1, current = false;
        (next.devices || []).forEach(function(d) {
            var value = score(d);
            if (known[d.qtDeviceId] !== undefined && value > known[d.qtDeviceId] || known[d.qtDeviceId] === undefined && value > 0) {
                if (d.qtDeviceId === followId) current = true;
                else if (moved < 0) moved = d.qtDeviceId;
            }
            known[d.qtDeviceId] = value;
        });
        scores = known;
        // Show whichever controller is being used, so a press is never lost on a hidden one.
        if (moved >= 0 && !current) followId = moved;
        snap = next;
    }

    function score(d) {
        var total = 0;
        [d.buttons, d.axes, d.triggers].forEach(function(group) {
            Object.keys(group).forEach(function(key) { if (group[key].seen) total += 1 + group[key].changes; });
        });
        return total;
    }

    function open() {
        if (!check) return;
        check.setActive(false);
        closeReview();
    }

    function start() {
        if (!check || !enabled) return;
        mode = "capturing";
        check.setActive(true);
        refresh();
    }

    function stop() {
        if (check) check.setActive(false);
        mode = "stopped";
        refresh();
    }

    function leave() {
        stop();
        closed();
    }

    function openReview() {
        if (!check || capturing || !hasObservations) return;
        preview = check.preview();
        previewStale = false;
        saveFailed = false;
        savedName = "";
        report.contentY = 0;
        mode = "review";
    }

    function closeReview() {
        preview = null;
        previewStale = false;
        saveFailed = false;
        savedName = "";
        mode = "stopped";
        refresh();
    }

    function compareReview() {
        if (!preview || savedName !== "") return;
        previewStale = check.preview().sha256 !== preview.sha256;
    }

    function reportName(sha) {
        return "controller-check-" + new Date().toISOString().replace(/[-:]/g, "").replace("T", "-").slice(0, 15) + "-" + sha.slice(0, 8) + ".json";
    }

    function saveReport() {
        if (!preview || previewStale || savedName !== "" || !check.state.privateExportConfigured) return;
        var name = reportName(preview.sha256);
        var result = check.exportPrivateReport(name, preview.sha256);
        if (result.ok) {
            savedName = name;
            saveFailed = false;
        } else {
            saveFailed = true;
            compareReview();
        }
    }

    function reviewPrimary() {
        if (savedName !== "") closeReview();
        else if (previewStale) openReview();
        else saveReport();
    }

    function goBack() {
        if (capturing) stop();
        else if (mode === "review") closeReview();
        else leave();
    }

    function stepDevice(step) {
        if (devices.length < 2) return;
        var at = 0;
        devices.forEach(function(d, i) { if (d.qtDeviceId === (device ? device.qtDeviceId : -1)) at = i; });
        followId = devices[(at + step + devices.length) % devices.length].qtDeviceId;
    }

    function scroll(delta) {
        report.contentY = Math.max(0, Math.min(Math.max(0, report.contentHeight - report.height), report.contentY + delta));
    }

    // ---------- input: reached through the theme's own key handlers ----------

    function handleKey(event) {
        event.accepted = true;
        if (event.key === Qt.Key_Back) {
            if (!event.isAutoRepeat) backArmed = true;
            return;
        }
        if (capturing || !keyMap) return;
        var k = keyMap;
        if (mode === "review") {
            if (k.isUp(event)) scroll(-px(120));
            else if (k.isDown(event)) scroll(px(120));
            else if (event.isAutoRepeat) return;
            else if (k.isCancel(event)) closeReview();
            else if (k.isAccept(event)) reviewPrimary();
            else if (k.isPageUp(event)) scroll(-report.height);
            else if (k.isPageDown(event)) scroll(report.height);
            return;
        }
        if (event.isAutoRepeat) return;
        if (k.isCancel(event)) leave();
        else if (k.isAccept(event)) start();
        else if (k.isDetails(event)) openReview();
        else if (k.isPrevPage(event)) stepDevice(-1);
        else if (k.isNextPage(event)) stepDevice(1);
    }

    function handleKeyRelease(event) {
        event.accepted = true;
        if (event.key !== Qt.Key_Back || event.isAutoRepeat || !backArmed) return;
        backArmed = false;
        goBack();
    }

    function hints() {
        if (capturing) return [{ k: "Android Back", l: "Stop check", a: "controller:stop" }];
        if (mode === "review") {
            var rows = [];
            if (savedName !== "") rows.push({ k: kAccept, l: "Done", a: "controller:primary" });
            else if (previewStale) rows.push({ k: kAccept, l: "Review again", a: "controller:primary" });
            else if (snap.privateExportConfigured) rows.push({ k: kAccept, l: saveFailed ? "Try again" : "Save private copy", a: "controller:primary" });
            rows.push({ k: "↑ ↓", l: "Read", a: "controller:read" });
            rows.push({ k: kCancel, l: "Back", a: "controller:back" });
            return rows;
        }
        var out = [{ k: kAccept, l: hasObservations ? "Continue check" : "Start check", a: "controller:start" }];
        if (hasObservations) out.push({ k: kDetails, l: "Review report", a: "controller:review" });
        if (devices.length > 1) out.push({ k: kPrev + " / " + kNext, l: "Controller", a: "controller:device" });
        out.push({ k: kCancel, l: "Back", a: "controller:back" });
        return out;
    }

    function runHint(action) {
        if (action === "stop" || action === "back") goBack();
        else if (action === "start") start();
        else if (action === "review") openReview();
        else if (action === "primary") reviewPrimary();
        else if (action === "read") scroll(px(120));
        else if (action === "device") stepDevice(1);
    }

    // ---------- plain words over the map ----------

    function count(group, test) {
        return Object.keys(group).filter(function(key) { return test(group[key]); }).length;
    }

    function statusText() {
        if (mode === "review") {
            if (savedName !== "") return "Saved in Nova's private storage. Nothing was sent.";
            if (previewStale) return "Report details changed after this preview, so it can't be saved.";
            if (saveFailed) return "Couldn't save this report. Nothing was written or sent.";
            return snap.privateExportConfigured ? "Read it first. Saving keeps it on this device." : "This build can't save reports. You can still read it here.";
        }
        if (paused) return "Paused while Nova is in the background. Live values were cleared.";
        if (capturing) {
            if (!devices.length) return "No controller connected yet.";
            if (device && !device.connected) return "Controller disconnected. What you tested stays; live values were cleared.";
            return "Press everything, and move both sticks all the way round.";
        }
        if (!hasObservations) return "Start, then press everything. The buttons won't control Nova until you stop.";
        if (!device) return "Only Android Back was seen. No controller connected.";
        return count(device.buttons, function(s) { return s.pressObserved; }) + " of 17 buttons · "
             + count(device.axes, function(s) { return s.seen; }) + " of 4 stick axes · "
             + count(device.triggers, function(s) { return s.seen; }) + " of 2 triggers";
    }

    function detailText() {
        if (mode === "review") {
            if (savedName !== "") return savedName;
            if (!preview) return "";
            return Number(preview.bytes).toLocaleString(Qt.locale("en_NZ"), "f", 0) + " bytes · SHA-256 " + preview.sha256.slice(0, 16) + "… · Not sent";
        }
        if (capturing) return device && device.connected && !paused ? "Buttons here only light up. They don't change anything in Nova." : "";
        if (!hasObservations) return "Stop with Android Back, or touch Stop.";
        var parts = [];
        if (device) {
            var missing = Object.keys(names).filter(function(key) { return !device.buttons[key].pressObserved; }).map(function(key) { return names[key]; });
            if (missing.length) parts.push("Not pressed: " + (missing.length > 6 ? missing.slice(0, 6).join(", ") + " and " + (missing.length - 6) + " more" : missing.join(", ")) + ". That isn't a fault.");
            if (!device.connected) parts.push("Controller disconnected.");
            if (count(device.triggers, function(s) { return s.seen; })) parts.push("Trigger depth isn't confirmed.");
        }
        if (snap.rejectedEvents) parts.push(snap.rejectedEvents + " invalid events ignored.");
        parts.push("This is what Nova received, not a hardware pass. Continue adds to this session; restarting Nova clears it.");
        return parts.join(" ");
    }

    function rangeText(sample) {
        if (!sample.seen) return "not moved";
        return (sample.minimum.toFixed(2) + " … " + sample.maximum.toFixed(2)).replace(/-/g, "−");
    }

    onModeChanged: backArmed = false
    onVisibleChanged: if (!visible && capturing) stop()
    // Pegasus disables the theme under its own menu (swipe, power dialog). Nothing may keep listening there.
    onEnabledChanged: if (!enabled && capturing) stop()
    Component.onDestruction: if (check) check.setActive(false)

    // A controller can emit hundreds of axis events a second; repaint at most every other frame.
    Timer { id: settle; interval: 33; onTriggered: panel.refresh() }
    Connections {
        target: panel.visible ? panel.check : null
        function onChanged() {
            if (panel.mode === "review") panel.compareReview();
            else if (!settle.running) settle.start();
        }
    }

    Rectangle { anchors.fill: parent; color: panel.ground }
    MouseArea { anchors.fill: parent }

    Text {
        id: head
        x: px(64); y: px(64)
        width: parent.width - px(128) - labelRow.width - px(24)
        text: mode === "review" ? "Review report" : "Controller check"
        textFormat: Text.PlainText
        elide: Text.ElideRight
        color: panel.ink
        font.family: panel.fontFamily
        font.pixelSize: fs(40)
        font.weight: Font.DemiBold
    }
    Row {
        id: labelRow
        anchors.right: parent.right; anchors.rightMargin: px(64)
        anchors.verticalCenter: head.verticalCenter
        spacing: px(20)
        Text {
            objectName: "controllerCheckMethod"
            visible: panel.injected
            text: "Test data, not a controller"
            textFormat: Text.PlainText
            color: panel.warning
            font.family: panel.fontFamily; font.pixelSize: fs(22)
        }
        Text {
            objectName: "controllerCheckDevice"
            visible: mode !== "review" && panel.devices.length > 1 && panel.device
            text: panel.device ? "Qt device " + panel.device.qtDeviceId + " · " + panel.devices.length + " seen" : ""
            textFormat: Text.PlainText
            color: panel.quiet
            font.family: panel.fontFamily; font.pixelSize: fs(22)
        }
        Row {
            objectName: "controllerCheckListening"
            visible: mode !== "review"
            spacing: px(10)
            Rectangle {
                anchors.verticalCenter: parent.verticalCenter
                width: px(12); height: width; radius: width / 2
                color: panel.capturing && !panel.paused ? panel.ink : "transparent"
                border.width: 1; border.color: panel.capturing && !panel.paused ? panel.ink : panel.faint
            }
            Text {
                text: panel.paused ? "Paused" : panel.capturing ? "Listening" : "Stopped"
                textFormat: Text.PlainText
                color: panel.capturing ? panel.ink : panel.quiet
                font.family: panel.fontFamily; font.pixelSize: fs(22)
            }
        }
    }

    // The block holds its height in every mode so the map never jumps when capture stops.
    Item {
        id: words
        x: px(64); y: head.y + head.height + px(10)
        width: parent.width - px(128)
        height: fs(24) * 1.4 + fs(22) * 1.35 * 2
        Text {
            id: status
            objectName: "controllerCheckStatus"
            width: parent.width
            text: panel.statusText()
            textFormat: Text.PlainText
            elide: Text.ElideRight
            color: mode === "review" && (panel.previewStale || panel.saveFailed) ? panel.warning : panel.ink
            font.family: panel.fontFamily; font.pixelSize: fs(24)
        }
        Text {
            objectName: "controllerCheckDetail"
            y: status.height + px(4)
            width: parent.width
            text: panel.detailText()
            textFormat: Text.PlainText
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
            color: panel.quiet
            font.family: panel.fontFamily; font.pixelSize: fs(22)
        }
    }

    // ---------- the map: solid is happening now, a tint stays once seen, untouched is an outline ----------

    component PadKey: Item {
        id: key
        property Item host
        property string label: ""
        property var sample: null
        property real size: 56
        property bool live: !!sample && sample.liveValueObserved && sample.raw > 0
        property bool pressed: !!sample && !!sample.pressObserved
        property bool round: label.length === 1
        readonly property string look: live ? "live" : pressed ? "seen" : "idle"
        width: label.length === 1 ? size : Math.max(size, keyText.implicitWidth + size * .5)
        height: size
        Rectangle {
            anchors.fill: parent
            radius: key.round ? height / 2 : key.size * .14
            color: key.live ? key.host.ink : key.pressed ? Qt.rgba(key.host.ink.r, key.host.ink.g, key.host.ink.b, .22) : "transparent"
            border.width: 1
            border.color: key.live || key.pressed ? key.host.ink : key.host.faint
        }
        Text {
            id: keyText
            anchors.centerIn: parent
            text: key.label
            textFormat: Text.PlainText
            color: key.live ? key.host.ground : key.pressed ? key.host.ink : key.host.faint
            font.family: key.host.fontFamily
            font.pixelSize: Math.round(key.size * .42)
            font.weight: key.live || key.pressed ? Font.DemiBold : Font.Normal
        }
    }

    component Stick: Item {
        id: stick
        property Item host
        property string clickLabel: ""
        property var x_: null
        property var y_: null
        property var click: null
        property real gate: 200
        property real keySize: 56
        property string info: "right"   // right | left | below
        readonly property bool live: !!x_ && !!y_ && (x_.liveValueObserved || y_.liveValueObserved)
        readonly property bool moved: !!x_ && !!y_ && (x_.seen || y_.seen)
        readonly property real puckX: live ? (x_.liveValueObserved ? x_.raw : 0) : 0
        readonly property real puckY: live ? (y_.liveValueObserved ? y_.raw : 0) : 0
        width: info === "below" ? gate : gate + host.px(20) + infoColumn.width
        height: info === "below" ? gate + host.px(12) + infoColumn.height : gate
        // Inset by the dot's radius, so full travel stays inside the gate and still reads as full.
        readonly property real dot: gate * .13
        function travel(value) { return dot / 2 + (value + 1) / 2 * (gate - dot); }
        Item {
            id: gateBox
            x: stick.info === "left" ? stick.width - stick.gate : 0
            width: stick.gate; height: stick.gate
            Rectangle {
                objectName: "stickRange"
                readonly property real minX: stick.x_ && stick.x_.seen ? stick.x_.minimum : 0
                readonly property real maxX: stick.x_ && stick.x_.seen ? stick.x_.maximum : 0
                readonly property real minY: stick.y_ && stick.y_.seen ? stick.y_.minimum : 0
                readonly property real maxY: stick.y_ && stick.y_.seen ? stick.y_.maximum : 0
                visible: stick.moved
                x: stick.travel(minX); y: stick.travel(minY)
                width: Math.max(2, stick.travel(maxX) - x); height: Math.max(2, stick.travel(maxY) - y)
                color: stick.host.ink; opacity: .22
            }
            Rectangle { x: parent.width / 2; width: 1; height: parent.height; color: stick.host.faint; opacity: .5 }
            Rectangle { y: parent.height / 2; height: 1; width: parent.width; color: stick.host.faint; opacity: .5 }
            Rectangle {
                anchors.fill: parent
                color: "transparent"
                radius: stick.host.px(4)
                border.width: 1
                border.color: stick.moved ? stick.host.ink : stick.host.faint
            }
            // A cleared value has no dot: a reset is not evidence the stick came back to centre.
            Rectangle {
                objectName: "stickPuck"
                visible: stick.live
                width: stick.dot; height: width; radius: width / 2
                x: stick.travel(stick.puckX) - width / 2
                y: stick.travel(stick.puckY) - height / 2
                color: stick.host.ink
            }
        }
        Column {
            id: infoColumn
            x: stick.info === "right" ? stick.gate + stick.host.px(20) : 0
            y: stick.info === "below" ? stick.gate + stick.host.px(12) : 0
            width: stick.info === "below" ? stick.gate : stick.host.fs(186)
            spacing: stick.host.px(8)
            PadKey {
                objectName: "pad_" + stick.clickLabel.toLowerCase()
                host: stick.host; label: stick.clickLabel; sample: stick.click; size: stick.keySize * .78
                x: stick.info === "left" ? parent.width - width : 0
            }
            Repeater {
                model: ["X", "Y"]
                Text {
                    objectName: "stickRange" + modelData
                    readonly property var axis: modelData === "X" ? stick.x_ : stick.y_
                    width: parent.width
                    horizontalAlignment: stick.info === "left" ? Text.AlignRight : Text.AlignLeft
                    text: modelData + "  " + (axis ? stick.host.rangeText(axis) : "not moved")
                    textFormat: Text.PlainText
                    color: axis && axis.seen ? stick.host.ink : stick.host.faint
                    font.family: stick.host.fontFamily
                    font.pixelSize: stick.host.fs(21)
                }
            }
        }
    }

    component Shoulder: Item {
        id: shoulder
        property Item host
        property string triggerLabel: ""
        property string bumperLabel: ""
        property var triggerSample: null
        property var triggerButton: null
        property var bumper: null
        property bool mirrored: false
        property real keySize: 44
        height: keySize * 2 + host.px(10)
        PadKey {
            id: triggerKey
            objectName: "pad_" + shoulder.triggerLabel.toLowerCase()
            host: shoulder.host; label: shoulder.triggerLabel; sample: shoulder.triggerButton; size: shoulder.keySize
            x: shoulder.mirrored ? parent.width - width : 0
        }
        Item {
            id: travel
            objectName: "triggerTravel_" + shoulder.triggerLabel
            readonly property var s: shoulder.triggerSample
            readonly property real rangeLow: s && s.seen ? s.minimum : 0
            readonly property real rangeHigh: s && s.seen ? s.maximum : 0
            readonly property real liveValue: s && s.liveValueObserved ? s.raw : 0
            x: shoulder.mirrored ? 0 : triggerKey.width + shoulder.host.px(14)
            width: parent.width - triggerKey.width - shoulder.host.px(14)
            height: shoulder.keySize
            Rectangle {
                id: track
                anchors.bottom: parent.bottom
                width: parent.width; height: shoulder.host.px(12)
                color: shoulder.host.slab
                Rectangle {
                    objectName: "triggerRange"
                    visible: travel.s && travel.s.seen
                    x: shoulder.mirrored ? parent.width * (1 - travel.rangeHigh) : parent.width * travel.rangeLow
                    width: parent.width * (travel.rangeHigh - travel.rangeLow)
                    height: parent.height
                    color: shoulder.host.ink; opacity: .22
                }
                Rectangle {
                    objectName: "triggerLive"
                    x: shoulder.mirrored ? parent.width * (1 - travel.liveValue) : 0
                    width: parent.width * travel.liveValue
                    height: parent.height
                    color: shoulder.host.ink
                }
            }
            Text {
                objectName: "triggerText"
                width: parent.width
                horizontalAlignment: shoulder.mirrored ? Text.AlignRight : Text.AlignLeft
                text: travel.s && travel.s.seen ? "Peak " + travel.rangeHigh.toFixed(2) : "Not pressed"
                textFormat: Text.PlainText
                color: travel.s && travel.s.seen ? shoulder.host.ink : shoulder.host.faint
                font.family: shoulder.host.fontFamily
                font.pixelSize: shoulder.host.fs(20)
            }
        }
        PadKey {
            objectName: "pad_" + shoulder.bumperLabel.toLowerCase()
            host: shoulder.host; label: shoulder.bumperLabel; sample: shoulder.bumper; size: shoulder.keySize
            y: shoulder.keySize + shoulder.host.px(10)
            x: shoulder.mirrored ? parent.width - width : 0
        }
    }

    Item {
        id: map
        objectName: "controllerCheckMap"
        visible: mode !== "review"
        x: px(64); y: words.y + words.height + px(16)
        width: parent.width - px(128)
        height: panel.bottomLimit - y

        readonly property var buttons: panel.device ? panel.device.buttons : ({})
        readonly property var axes: panel.device ? panel.device.axes : ({})
        readonly property var triggers: panel.device ? panel.device.triggers : ({})
        readonly property real keySize: Math.max(px(52), Math.round(fs(24) * 2.2))
        readonly property real gap: px(6)
        readonly property real cluster: keySize * 3 + gap * 2
        readonly property real shoulderKey: Math.round(keySize * .78)
        readonly property real shoulderH: shoulderKey * 2 + px(10)
        readonly property real centreW: px(wide ? 300 : 270)
        readonly property real sideW: (width - centreW) / 2
        readonly property real stickInfoBelow: keySize * .78 + 2 * (fs(21) * 1.35) + px(36)
        // On 4:3 the sticks sit diagonally, each sharing a row with a button cluster.
        readonly property real gate: wide
            ? Math.max(px(120), Math.min(px(280), height - shoulderH - px(24) - stickInfoBelow))
            : Math.max(px(120), Math.min(px(236), sideW - fs(186) - px(20), (height - shoulderH - px(40)) / 2))
        readonly property real topZone: shoulderH + px(wide ? 24 : 20)
        readonly property real lowZone: wide ? topZone : topZone + Math.max(gate, cluster) + px(20)

        Shoulder {
            host: panel; objectName: "shoulderLeft"
            width: map.sideW - px(16)
            triggerLabel: "L2"; bumperLabel: "L1"; keySize: map.shoulderKey
            triggerSample: map.triggers.l2 || null; triggerButton: map.buttons.l2 || null; bumper: map.buttons.l1 || null
        }
        Shoulder {
            host: panel; objectName: "shoulderRight"
            x: map.width - width
            width: map.sideW - px(16)
            mirrored: true
            triggerLabel: "R2"; bumperLabel: "R1"; keySize: map.shoulderKey
            triggerSample: map.triggers.r2 || null; triggerButton: map.buttons.r2 || null; bumper: map.buttons.r1 || null
        }

        Stick {
            objectName: "stickLeft"
            host: panel; y: map.topZone
            gate: map.gate; keySize: map.keySize; info: panel.wide ? "below" : "right"
            clickLabel: "L3"; click: map.buttons.l3 || null
            x_: map.axes["left-x"] || null; y_: map.axes["left-y"] || null
        }
        Stick {
            objectName: "stickRight"
            host: panel
            x: map.width - width
            y: panel.wide ? map.topZone : map.lowZone
            gate: map.gate; keySize: map.keySize; info: panel.wide ? "below" : "left"
            clickLabel: "R3"; click: map.buttons.r3 || null
            x_: map.axes["right-x"] || null; y_: map.axes["right-y"] || null
        }

        Item {
            id: dpad
            objectName: "dpad"
            x: panel.wide ? map.gate + (map.sideW - map.gate - width) / 2 : 0
            y: panel.wide ? map.topZone : map.lowZone
            width: map.cluster; height: map.cluster
            PadKey { objectName: "pad_up"; host: panel; round: false; label: "↑"; size: map.keySize; sample: map.buttons.up || null; x: map.keySize + map.gap }
            PadKey { objectName: "pad_left"; host: panel; round: false; label: "←"; size: map.keySize; sample: map.buttons.left || null; y: map.keySize + map.gap }
            PadKey { objectName: "pad_right"; host: panel; round: false; label: "→"; size: map.keySize; sample: map.buttons.right || null; x: (map.keySize + map.gap) * 2; y: map.keySize + map.gap }
            PadKey { objectName: "pad_down"; host: panel; round: false; label: "↓"; size: map.keySize; sample: map.buttons.down || null; x: map.keySize + map.gap; y: (map.keySize + map.gap) * 2 }
        }

        Item {
            id: face
            objectName: "face"
            x: panel.wide ? map.width - map.gate - width - (map.sideW - map.gate - width) / 2 : map.width - width
            y: map.topZone
            width: map.cluster; height: map.cluster
            PadKey { objectName: "pad_north"; host: panel; label: "Y"; size: map.keySize; sample: map.buttons.north || null; x: map.keySize + map.gap }
            PadKey { objectName: "pad_west"; host: panel; label: "X"; size: map.keySize; sample: map.buttons.west || null; y: map.keySize + map.gap }
            PadKey { objectName: "pad_east"; host: panel; label: "B"; size: map.keySize; sample: map.buttons.east || null; x: (map.keySize + map.gap) * 2; y: map.keySize + map.gap }
            PadKey { objectName: "pad_south"; host: panel; label: "A"; size: map.keySize; sample: map.buttons.south || null; x: map.keySize + map.gap; y: (map.keySize + map.gap) * 2 }
        }

        Column {
            id: centre
            objectName: "centreKeys"
            width: map.centreW
            x: (map.width - width) / 2
            y: map.topZone
            spacing: px(14)
            PadKey {
                objectName: "pad_guide"
                host: panel; label: "Guide"; size: map.shoulderKey; sample: map.buttons.guide || null
                anchors.horizontalCenter: parent.horizontalCenter
            }
            Row {
                anchors.horizontalCenter: parent.horizontalCenter
                spacing: px(14)
                PadKey { objectName: "pad_select"; host: panel; label: "Select"; size: map.shoulderKey; sample: map.buttons.select || null }
                PadKey { objectName: "pad_start"; host: panel; label: "Start"; size: map.shoulderKey; sample: map.buttons.start || null }
            }
            Item { width: 1; height: px(panel.wide ? 10 : 24) }
            // Back is a system key, not a controller button, so it never sits with Select.
            PadKey {
                objectName: "pad_back"
                host: panel; label: "Android Back"; size: map.shoulderKey
                sample: panel.snap.systemBack || null
                anchors.horizontalCenter: parent.horizontalCenter
            }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.Wrap
                text: "System key. Not tied to a controller."
                textFormat: Text.PlainText
                color: panel.faint
                font.family: panel.fontFamily; font.pixelSize: fs(20)
            }
        }
    }

    // ---------- the full report, exactly as it would be written ----------

    Flickable {
        id: report
        objectName: "controllerCheckReport"
        visible: mode === "review"
        x: px(64); y: words.y + words.height + px(16)
        width: parent.width - px(128)
        height: panel.bottomLimit - y
        clip: true
        contentWidth: width - px(16)
        contentHeight: reportText.height
        boundsBehavior: Flickable.StopAtBounds
        Text {
            id: reportText
            objectName: "controllerCheckReportText"
            width: report.contentWidth
            text: panel.preview ? panel.preview.json : ""
            textFormat: Text.PlainText
            wrapMode: Text.WrapAnywhere
            color: panel.quiet
            font.family: panel.monoFamily || panel.fontFamily
            font.pixelSize: fs(20)
        }
        Rectangle {
            parent: report
            visible: report.contentHeight > report.height
            anchors.right: parent.right
            y: report.height * report.visibleArea.yPosition
            width: px(4)
            height: Math.max(px(40), report.height * report.visibleArea.heightRatio)
            color: panel.faint
        }
    }
}
