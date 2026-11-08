import QtQuick 2.15
import "library.js" as Lib
Item {
    id: panel
    objectName: "cloudLibrary"
    property var cloud: null
    property var keyMap: null
    property int targetId: 0
    readonly property string kAccept: Lib.keyLabel(keyMap ? keyMap.accept : null,"A")
    readonly property string kCancel: Lib.keyLabel(keyMap ? keyMap.cancel : null,"B")
    readonly property string kDetails: Lib.keyLabel(keyMap ? keyMap.details : null,"X")
    readonly property string kFilters: Lib.keyLabel(keyMap ? keyMap.filters : null,"Y")
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property color slab: "#1a1c1e"
    property real textScale: 1
    property color quiet: "#9a9b9b"
    property string fontFamily: ""
    property real scale: Math.max(0.5, Math.min(width / 1280, height / 800))
    property int selected: 0
    property bool queueOpen: false
    readonly property bool queueAvailable: !!(cloud && cloud.queueVersion === 1 && typeof cloud.enqueueDownload === "function" && typeof cloud.startDownloads === "function")
    readonly property bool currentQueued: { var jobs=queueAvailable ? cloud.downloads || [] : [];return !!current && jobs.some(function(job){return job.id===current.id;}); }
    property bool confirmRemove: false
    property int selectedIdentity: 0
    property bool cleanupOpen: false
    property var cleanupCandidates: []
    property int cleanupIndex: 0
    property var removalPreview: null
    property var removalTarget: null
    property string removalNotice: ""
    readonly property var visibleGames: cleanupOpen ? cleanupCandidates : games
    readonly property var highlighted: cleanupOpen ? (cleanupIndex >= 0 && cleanupIndex < cleanupCandidates.length ? cleanupCandidates[cleanupIndex] : null) : current
    readonly property int highlightIndex: cleanupOpen ? cleanupIndex : selected
    readonly property var games: cloud ? cloud.games.filter(function(g){return targetId===0 || g.id===targetId;}) : []
    readonly property var current: selected >= 0 && selected < games.length ? games[selected] : null
    readonly property bool busy: cloud ? cloud.busy : false
    readonly property bool setupRequired: !cloud || cloud.configured === false
    readonly property string setupText: "Cloud library is not connected on this Nova. Set up the connection from your computer, then restart Library."
    readonly property var spacePlan: {
        var messageRevision = cloud ? cloud.message : "";
        return cloud && current && !busy && typeof cloud.installPlan === "function" ? cloud.installPlan(current.id) : ({});
    }
    readonly property bool spaceBlocked: spacePlan.spaceKnown === true && spacePlan.fits !== true
    readonly property bool recoveryBlocked: spacePlan.blocked === true || !!(current && current.downloadBlocked)
    readonly property string recoveryReason: spacePlan.blocked === true ? spacePlan.reason || "Retained files need review."
        : current && current.downloadReason ? current.downloadReason : spacePlan.reason || "Retained files need review."
    signal closed()
    function px(n) { return Math.round(n * scale); }
    function fs(n) { return Math.round(n * scale * textScale); }
    function spaceText() {
        if (!current || current.installed) return "";
        if (recoveryBlocked) return "Retained files need review. Nothing will be replaced.";
        if (busy) return "Downloading to selected storage; interrupted bytes are retained.";
        if (!spacePlan.spaceKnown) return spacePlan.reason || "Space is checked before downloading.";
        return (spaceBlocked ? "Free " + Lib.bytesText(spacePlan.shortfallBytes) + " more · " : "")
            + (spacePlan.retainedBytes > 0 ? Lib.bytesText(spacePlan.retainedBytes) + " retained · " : "")
            + Lib.bytesText(spacePlan.remainingBytes) + " to download · " + Lib.bytesText(spacePlan.freeBytes)
            + " free · " + Lib.bytesText(spacePlan.headroomBytes) + " working space"
            + " · measured at selection";
    }
    function clearRemoval() { confirmRemove=false;removalPreview=null;removalTarget=null; }
    function openCleanup() {
        clearRemoval();removalNotice="";
        if(!cloud || !current || typeof cloud.cleanupPlan !== "function") {removalNotice="Cleanup review needs the matching native Library build.";return;}
        var keep=highlighted ? highlighted.id : 0;
        var plan=cloud.cleanupPlan(current.id);cleanupCandidates=plan.candidates || [];
        cleanupIndex=0;cleanupCandidates.forEach(function(g,i){if(g.id === keep)cleanupIndex=i;});
        cleanupOpen=true;
    }
    function reviewRemoval() {
        if(!cloud || !highlighted || busy)return;
        if(confirmRemove){clearRemoval();return;}
        if(typeof cloud.removalPlan !== "function") {removalNotice="Removal needs the matching native review capability.";return;}
        var plan=cloud.removalPlan(highlighted.id);
        if(!plan.eligible || !plan.token) {removalNotice=plan.reason || "This download is protected.";return;}
        removalPreview=plan;removalTarget=highlighted;removalNotice="";confirmRemove=true;
    }
    function goBack() {
        if(queueOpen){queueOpen=false;return;}
        if(confirmRemove)clearRemoval();
        else if(cleanupOpen){cleanupOpen=false;removalNotice="";}
        else closed();
    }
    function primary() {
        if (!cloud || setupRequired) return;
        if(queueAvailable && !cleanupOpen && !confirmRemove && current && !current.installed && current.supported && !recoveryBlocked && !spaceBlocked) {
            if(currentQueued){queueOpen=true;return;}
            if(cloud.enqueueDownload(current.id) && !busy)cloud.startDownloads(current.id);
            return;
        }
        if(busy)return;
        if (confirmRemove && removalTarget && removalPreview) {
            cloud.removeDownload(removalTarget.id,removalPreview.token);clearRemoval();
            if(cleanupOpen)openCleanup();
        } else if(cleanupOpen)reviewRemoval();
        else if (current && current.installed) cloud.play(current.id);
        else if (current && current.supported && !spaceBlocked && !recoveryBlocked) cloud.install(current.id);
    }
    function handleKey(event) {
        if (!keyMap) return;
        if(queueOpen){queueView.handleKey(event);return;}
        event.accepted = true;
        if(queueAvailable && typeof keyMap.isNextPage === "function" && keyMap.isNextPage(event)){queueOpen=true;clearRemoval();return;}
        if (keyMap.isCancel(event)) goBack();
        else if (keyMap.isUp(event) || keyMap.isDown(event)) {
            var step=keyMap.isUp(event)?-1:1;
            if(cleanupOpen)cleanupIndex=Math.max(0,Math.min(cleanupCandidates.length-1,cleanupIndex+step));
            else selected=Math.max(0,Math.min(games.length-1,selected+step));
            clearRemoval();removalNotice="";
        } else if (keyMap.isAccept(event)) primary();
        else if (keyMap.isDetails(event) && cloud && !setupRequired) {
            clearRemoval();removalNotice="";
            if (busy) cloud.cancel(); else if(cleanupOpen)openCleanup();else cloud.refresh();
        } else if (keyMap.isFilters(event) && current && !busy) {
            if(cleanupOpen || current.installed || current.partial)reviewRemoval();else openCleanup();
        }
    }
    onCurrentChanged: {
        var identity=current ? current.id : 0;
        if(identity !== selectedIdentity) { clearRemoval();cleanupOpen=false;removalNotice="";selectedIdentity=identity; }
        if(visible && !cleanupOpen && cloud && current && typeof cloud.requestCover === "function") cloud.requestCover(current.id);
    }
    onVisibleChanged: {
        if(!visible){queueOpen=false;clearRemoval();cleanupOpen=false;removalNotice="";}
        else if(cloud && current && typeof cloud.requestCover === "function")cloud.requestCover(current.id);
    }
    onGamesChanged: selected = Math.max(0, Math.min(selected, games.length - 1))
    onTargetIdChanged: {selected=0;clearRemoval();cleanupOpen=false;removalNotice="";}
    Item {
    anchors.fill:parent;visible:!panel.queueOpen
    Rectangle { anchors.fill: parent; color: panel.ground }
    Text { textFormat: Text.PlainText; x: px(64); y: px(64); text: cleanupOpen ? "Make room for " + (current ? current.title : "a game") : targetId ? "Download details" : "Cloud library"; width: parent.width-px(queueAvailable && !cleanupOpen ? 360 : 128); elide: Text.ElideRight; color: ink; font.family: fontFamily; font.pixelSize: fs(40); font.weight: Font.DemiBold }
    Item {
        visible:queueAvailable && !cleanupOpen;x:parent.width-width-px(64);y:px(76);width:downloadsHint.implicitWidth;height:px(34)
        Row {
            id:downloadsHint;spacing:px(10)
            KeyCap {label:Lib.keyLabel(keyMap?keyMap.nextPage:null,"R1");ink:panel.ink;ground:panel.ground;fontFamily:panel.fontFamily;textSize:panel.fs(21)}
            Text {text:"Downloads";color:panel.ink;font.family:panel.fontFamily;font.pixelSize:panel.fs(24)}
        }
        MouseArea {anchors.fill:parent;anchors.margins:-panel.px(10);onClicked:{queueOpen=true;clearRemoval();}}
    }
    Text { textFormat: Text.PlainText; x: px(64); y: px(122); width: parent.width-px(128); text: cleanupOpen ? "Cloud-managed downloads only. Save folders are not cleanup targets." : setupRequired ? "Your local library is available while Cloud is disconnected." : "Download here. Play offline. Keep your saves."; color: quiet; font.family: fontFamily; font.pixelSize: fs(22) }
    Text { textFormat: Text.PlainText; x: px(64); y: px(152); width: parent.width-px(128); text: spaceText(); color: quiet; font.family: fontFamily; font.pixelSize: fs(18); elide: Text.ElideRight }
    Item {
        objectName:"cloudContent"
        // Keep content sixteen layout units above the active progress rule.
        x: px(64); y: px(182); width: parent.width-px(128); height: Math.max(0,parent.height-px(374))
        visible: visibleGames.length > 0
        ArtView {
            entry: highlighted ? {title:highlighted.title,art:highlighted.cover || "",systemId:highlighted.systemId || highlighted.platform || "",systemName:highlighted.system || ""} : null
            width: parent.width * 0.32; height: Math.min(parent.height,width*1.5)
            fontFamily: panel.fontFamily; textColor: panel.ink; quietColor: panel.quiet; slabColor: panel.slab; veilColor: panel.ground
        }
        ListView {
            id: list
            x: parent.width * 0.38; width: parent.width-x; height: parent.height
            clip: true; model: panel.visibleGames; currentIndex: panel.highlightIndex; spacing: px(8)
            highlightMoveDuration: 0; preferredHighlightBegin: 0; preferredHighlightEnd: height; highlightRangeMode: ListView.ApplyRange
            delegate: Item {
                width: list.width; height: Math.max(px(90),fs(80))
                Rectangle { x: 0; y: px(12); width: px(3); height: parent.height-px(24); color: ink; visible: index === highlightIndex }
                Column {
                    x: px(18); y: px(12); width: parent.width-px(30); spacing: px(5)
                    Text { textFormat: Text.PlainText; width: parent.width; elide: Text.ElideRight; text: modelData.title; color: ink; font.family: fontFamily; font.pixelSize: fs(25) }
                    Text { textFormat: Text.PlainText; width: parent.width; elide: Text.ElideRight; text: cleanupOpen ? (modelData.bytesKnown ? Lib.bytesText(modelData.bytes) + " observed files" : "Size unknown") + " · " + (modelData.eligible ? "Review removal" : "Protected") : modelData.system + " · " + (modelData.installed ? "On this device" : modelData.downloadBlocked ? "Needs review" : modelData.downloadState === "downloading" ? "Downloading" : modelData.partial ? "Partial download" : "In your cloud") + " · " + (modelData.bytes > 0 ? Lib.bytesText(modelData.bytes) : "Size unknown"); color: quiet; font.family: fontFamily; font.pixelSize: fs(18) }
                }
                MouseArea { anchors.fill: parent; onClicked: { if(cleanupOpen)cleanupIndex=index;else selected=index;clearRemoval();removalNotice=""; } onDoubleClicked: primary() }
            }
        }
    }
    Text { textFormat: Text.PlainText;
        x: px(64); y: px(204); width: parent.width-px(128); visible: !visibleGames.length
        text: cleanupOpen ? "No other managed downloads to review. Other ROM folders and app data are outside this cleanup." : setupRequired ? setupText : cloud.message
        color: quiet; wrapMode: Text.WordWrap; font.family: fontFamily; font.pixelSize: fs(27)
    }
    Rectangle {
        objectName:"cloudProgress"
        x: px(64); y: parent.height-px(176); width: parent.width-px(128); height: px(3); color: Qt.rgba(ink.r,ink.g,ink.b,0.12); visible: busy
        Rectangle { width: parent.width * (cloud ? Math.max(0,Math.min(1,cloud.progress)) : 0); height: parent.height; color: ink }
    }
    Text { objectName:"cloudNotice"; textFormat: Text.PlainText;
        x: px(64); y: parent.height-px(157); width: parent.width-px(128); height: px(62)
        text: confirmRemove && removalTarget && removalPreview ? "Remove “" + removalTarget.title.slice(0,72) + (removalTarget.title.length>72?"…":"") + "”? " + Lib.bytesText(removalPreview.bytes) + " in " + removalPreview.fileCount + " managed files. Press " + kAccept + " to confirm; " + kCancel + " keeps it."
            : removalNotice ? removalNotice : busy ? cloud.message : cleanupOpen && highlighted ? highlighted.reason || "Review a download; nothing is selected for automatic removal."
            : current && !current.supported && !current.installed ? current.reason : recoveryBlocked && current && !current.installed ? recoveryReason : spaceBlocked && current && !current.installed ? spacePlan.reason : setupRequired ? "" : cloud && visibleGames.length ? cloud.message : ""
        wrapMode: Text.WordWrap; elide: Text.ElideRight; maximumLineCount: 2; color: quiet; font.family: fontFamily; font.pixelSize: fs(20)
    }
    Row {
        objectName:"cloudHints"
        x: px(64); y: parent.height-px(76); spacing: px(30)
        Repeater {
            model: [{key:kAccept,label:confirmRemove ? "Confirm removal" : cleanupOpen ? highlighted && highlighted.eligible ? "Review" : "Why protected" : current && current.installed ? "Play" : currentQueued ? "Downloads" : busy && queueAvailable ? "Queue" : current && current.resumeAvailable ? "Resume" : current && current.partial ? "Check download" : "Download",action:"primary",enabled:!setupRequired && (!busy || queueAvailable && !cleanupOpen && current && !current.installed) && (confirmRemove || cleanupOpen && highlighted || current && (current.installed || current.supported && !spaceBlocked && !recoveryBlocked))},
                {key:kDetails,label:busy ? "Pause" : "Refresh",action:"refresh",enabled:cloud !== null && !setupRequired},
                {key:kFilters,label:current && (current.installed || current.partial) ? "Review removal" : "Make room",action:"remove",enabled:!cleanupOpen && current && !busy && cloud && typeof cloud.removalPlan === "function"},
                {key:kCancel,label:"Back",action:"back",enabled:true}]
            delegate: Item {
                objectName:"cloudHint_"+modelData.action
                visible: !!modelData.enabled; width:cloudHint.implicitWidth; height:px(32)
                Row {
                    id:cloudHint; spacing:px(10)
                    KeyCap { label:modelData.key; ink:panel.ink; ground:panel.ground; primary:modelData.action === "primary"; fontFamily:panel.fontFamily; textSize:panel.fs(21) }
                    Text { objectName:"cloudHintLabel_"+modelData.action; textFormat:Text.PlainText; text:modelData.label; color:modelData.action === "primary" ? panel.ink : panel.quiet; font.family:panel.fontFamily; font.pixelSize:panel.fs(24); anchors.verticalCenter:parent.verticalCenter }
                }
                MouseArea { anchors.fill: parent; anchors.margins: -px(10); onClicked: {
                    if (modelData.action === "primary") primary();
                    else if (modelData.action === "refresh") { clearRemoval();removalNotice="";if (busy) cloud.cancel(); else if(cleanupOpen)openCleanup();else cloud.refresh(); }
                    else if (modelData.action === "remove") {if(current && (current.installed || current.partial))reviewRemoval();else openCleanup();}
                    else goBack();
                } }
            }
        }
    }
    }
    DownloadQueue {
        id:queueView;anchors.fill:parent;visible:panel.queueOpen
        cloud:panel.cloud;keyMap:panel.keyMap;ground:panel.ground;ink:panel.ink;slab:panel.slab;quiet:panel.quiet
        textScale:panel.textScale;fontFamily:panel.fontFamily
        onClosed:panel.queueOpen=false
    }
}
