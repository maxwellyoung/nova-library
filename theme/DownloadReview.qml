import QtQuick 2.15
import "library.js" as Lib
Item {
    id: panel
    objectName: "downloadReview"
    property var cloud: null
    property var keyMap: null
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property real textScale: 1
    property string fontFamily: ""
    property real scale: Math.max(0.5, Math.min(width / 1280, height / 800))
    property int gameId: 0
    property var preview: ({})
    property bool inspecting: false
    property int selected: 0
    property string actionError: ""
    property int planRevision: 0
    property bool recheckRequired: false
    readonly property bool busy: !!(cloud && cloud.busy)
    readonly property var latest: {
        if (!visible || !cloud || gameId <= 0) return ({});
        var revision = [cloud.games, cloud.message, cloud.busy, planRevision];
        return typeof cloud.downloadReview === "function" ? cloud.downloadReview(gameId) : ({});
    }
    readonly property bool changed: !!preview.editionId && (latest.editionId !== preview.editionId || latest.title !== preview.title)
    readonly property bool canConfirm: !!(preview.detailsKnown && preview.supported && !changed && latest.id === gameId && latest.detailsKnown && latest.supported
        && !latest.installed && latest.spaceKnown && latest.fits && !latest.blocked && (!busy || queueAvailable))
    property bool queueAvailable: false
    readonly property string primaryLabel: changed ? "Review again" : recheckRequired ? "Check again" : "Download"
    signal closed()
    signal confirmed(int gameId, string editionId)
    function px(n) { return Math.round(n * scale); }
    function fs(n) { return Math.round(n * scale * textScale); }
    function refreshPlan() { planRevision++; actionError = ""; recheckRequired = false; }
    function takePreview() { preview = JSON.parse(JSON.stringify(latest)); selected = 0; actionError = ""; recheckRequired = false; }
    function refuseCurrentPlan(reason) {
        // Filesystem changes need not emit a catalogue signal. Refresh the measured
        // plan and keep the refusal visible instead of leaving old capacity on screen.
        planRevision++; actionError = reason || "Download conditions changed. Nothing was downloaded."; recheckRequired = true;
    }
    function begin(id) {
        gameId = id; inspecting = false; refreshPlan(); takePreview();
        if (!preview.detailsKnown) inspect();
    }
    function inspect() {
        if (!cloud || busy) return;
        inspecting = true; cloud.inspectDownload(gameId);
        if (!busy) { inspecting = false; takePreview(); }
    }
    function primary() {
        if (changed) { refreshPlan(); takePreview(); if (!preview.detailsKnown) inspect(); return; }
        if (recheckRequired) { refreshPlan(); return; }
        if (canConfirm) { actionError = ""; confirmed(gameId, preview.editionId); }
    }
    function back() { inspecting = false; closed(); }
    function handleKey(event) {
        if (!keyMap) return;
        event.accepted = true;
        if (keyMap.isCancel(event)) back();
        else if (keyMap.isUp(event)) selected = Math.max(0, selected - 1);
        else if (keyMap.isDown(event)) selected = Math.min(Math.max(0, (preview.files || []).length - 1), selected + 1);
        else if (keyMap.isAccept(event) && !event.isAutoRepeat) primary();
        else if (keyMap.isDetails(event) && !busy && !event.isAutoRepeat) { if (!preview.detailsKnown) inspect(); else refreshPlan(); }
    }
    function costText() {
        if (!preview.detailsKnown) return "File sizes have not been checked yet.";
        var total = Lib.bytesText(preview.totalBytes) + " in " + preview.files.length + (preview.files.length === 1 ? " file" : " files");
        if (changed) return total + " · Previous review";
        if (!latest.spaceKnown) return total + " · Free space unknown";
        return total + " · " + Lib.bytesText(latest.remainingBytes) + " to download"
            + (latest.retainedBytes > 0 ? " · " + Lib.bytesText(latest.retainedBytes) + " retained, not yet verified" : "")
            + " · " + Lib.bytesText(latest.freeBytes) + " free · " + Lib.bytesText(latest.headroomBytes) + " working space";
    }
    function notice() {
        if (changed) return "The cloud copy changed. Review its new files before downloading.";
        if (actionError) return actionError;
        if (latest.installed) return "This game is already downloaded. Go back to play it.";
        if (inspecting) return "Checking the file list. No game files are downloading.";
        if (!preview.detailsKnown) return busy ? "Another operation is running. Return after it finishes to check these files." : cloud ? cloud.message : "Cloud is unavailable.";
        if (latest.blocked) return latest.reason || "Retained files need review. Nothing will be replaced.";
        if (!preview.supported) return latest.reason || "This download is not supported.";
        if (!latest.spaceKnown || !latest.fits) return latest.reason || "Storage must be available before downloading.";
        return "Space is checked again at download time. All files must pass verification before Play is offered.";
    }
    onLatestChanged: if (visible && inspecting && !busy) { inspecting = false; takePreview(); }
    onVisibleChanged: if (!visible) inspecting = false;
    Rectangle { anchors.fill: parent; color: panel.ground }
    Text {
        objectName: "reviewTitle"
        x: px(64); y: px(48); width: parent.width - px(128)
        text: "Review download"; color: ink; font.family: fontFamily; font.pixelSize: fs(36); font.weight: Font.DemiBold
    }
    Text {
        objectName: "reviewGameTitle"
        x: px(64); y: px(104); width: parent.width - px(128)
        text: preview.title || "Game unavailable"; textFormat: Text.PlainText; elide: Text.ElideRight
        color: ink; font.family: fontFamily; font.pixelSize: fs(26)
    }
    Column {
        id: summary
        x: px(64); y: px(150); width: parent.width - px(128); spacing: px(8)
        Text { width: parent.width; text: costText(); textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: quiet; font.family: fontFamily; font.pixelSize: fs(19) }
        Text { width: parent.width; text: preview.detailsKnown ? preview.scope : "The file list must be checked before choosing Download."; textFormat: Text.PlainText; wrapMode: Text.WordWrap; color: ink; font.family: fontFamily; font.pixelSize: fs(20) }
    }
    ListView {
        id: files
        objectName: "reviewFiles"
        x: px(64); y: summary.y + summary.height + px(20); width: parent.width - px(128)
        height: Math.max(0, parent.height - y - px(187)); clip: true
        model: preview.files || []; currentIndex: selected; spacing: px(8); highlightMoveDuration: 0
        preferredHighlightBegin: 0; preferredHighlightEnd: height; highlightRangeMode: ListView.ApplyRange
        delegate: Item {
            objectName: "reviewFile_" + index
            width: files.width; height: fileText.height + px(24)
            Rectangle { x: 0; y: px(8); width: px(3); height: parent.height - px(16); color: panel.ink; visible: index === selected }
            Column {
                id: fileText
                x: px(18); y: px(12); width: parent.width - px(36); spacing: px(4)
                Text { width: parent.width; text: modelData.name; textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere; color: panel.ink; font.family: panel.fontFamily; font.pixelSize: panel.fs(22) }
                Text { width: parent.width; text: modelData.role + " · " + Lib.bytesText(modelData.bytes); textFormat: Text.PlainText; color: panel.quiet; font.family: panel.fontFamily; font.pixelSize: panel.fs(18) }
            }
            MouseArea { anchors.fill: parent; onClicked: selected = index }
        }
    }
    Text {
        objectName: "reviewNotice"
        x: px(64); y: parent.height - px(156); width: parent.width - px(128); height: px(76)
        text: notice(); textFormat: Text.PlainText; wrapMode: Text.WordWrap
        color: quiet; font.family: fontFamily; font.pixelSize: fs(20)
    }
    Row {
        objectName: "reviewHints"
        x: px(64); y: parent.height - px(64); spacing: px(28)
        Repeater {
            model: [{key:Lib.keyLabel(keyMap ? keyMap.accept : null,"A"),label:primaryLabel,action:"confirm",enabled:changed || recheckRequired || canConfirm},
                {key:Lib.keyLabel(keyMap ? keyMap.details : null,"X"),label:preview.detailsKnown ? "Check again" : "Check files",action:"inspect",enabled:!busy && (!preview.detailsKnown || !canConfirm && !latest.installed)},
                {key:"↑↓",label:"Files " + (selected+1) + "/" + (preview.files || []).length,action:"files",enabled:(preview.files || []).length>1},
                {key:Lib.keyLabel(keyMap ? keyMap.cancel : null,"B"),label:"Back",action:"back",enabled:true}]
            delegate: Item {
                visible: modelData.enabled; width: hint.implicitWidth; height: px(32)
                Row {
                    id: hint; spacing: px(10)
                    KeyCap { label: modelData.key; ink: panel.ink; ground: panel.ground; primary: modelData.action === "confirm"; fontFamily: panel.fontFamily; textSize: panel.fs(21) }
                    Text { text: modelData.label; color: panel.ink; font.family: panel.fontFamily; font.pixelSize: panel.fs(24); anchors.verticalCenter: parent.verticalCenter }
                }
                MouseArea { anchors.fill: parent; anchors.margins: px(8); enabled:modelData.action !== "files"; onClicked: { if(modelData.action === "confirm")primary(); else if(modelData.action === "inspect") {if(preview.detailsKnown)refreshPlan();else inspect();} else back(); } }
            }
        }
    }
}
