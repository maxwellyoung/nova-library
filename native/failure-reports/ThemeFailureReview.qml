// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick 2.15

Item {
    id: root
    objectName: "nativeThemeFailureReview"
    anchors.fill: parent
    z: 10
    property bool previewOpen: false
    property var report: ({})
    property string notice: ""
    property var releaseFence: []
    readonly property bool available: {
        var revision = failureReports.revision;
        return failureReports.themeFailureAvailable();
    }

    function cancelRecovery() {
        if (typeof parent.cancelGesture === "function") parent.cancelGesture();
    }
    function openReport() {
        // A second mapped action cannot complete an already armed recovery.
        if (typeof parent.acceptArmed !== "undefined") parent.acceptArmed = false;
        if (releaseFence.length || (parent.heldAcceptKeys && parent.heldAcceptKeys.length)) {
            notice = qsTr("Release the accept button, then review again.");
            return;
        }
        var result = failureReports.previewThemeFailure();
        if (!result || result.ok !== true) {
            notice = qsTr("This failure observation is no longer available. Nothing was exported.");
            return;
        }
        cancelRecovery(); notice = ""; report = result; previewOpen = true;
    }
    function closeReport() {
        failureReports.cancelPreview(report.ticket || "");
        previewOpen = false; report = ({}); cancelRecovery();
    }

    // The native error root forwards keys here before its guarded recovery handler.
    Keys.onPressed: {
        if (previewOpen) {
            event.accepted = true;
            if (api.keys.isAccept(event) && !event.isAutoRepeat) {
                var held = releaseFence.slice(0);
                if (held.indexOf(event.key) < 0) held.push(event.key);
                releaseFence = held;
            }
            if (preview.item) preview.item.handleKey(event, api.keys);
            return;
        }
        if (!event.isAutoRepeat) notice = "";
        if (api.keys.isDetails(event) && available) {
            event.accepted = true;
            if (!event.isAutoRepeat) openReport();
        } else if (api.keys.isAccept(event) && releaseFence.length) event.accepted = true;
        else event.accepted = false;
    }
    Keys.onReleased: {
        var held = releaseFence.slice(0);
        var at = held.indexOf(event.key);
        if (at >= 0 && !event.isAutoRepeat) { held.splice(at, 1); releaseFence = held; }
        event.accepted = previewOpen || at >= 0;
    }
    Connections {
        target: Qt.application
        function onStateChanged() {
            if (Qt.application.state !== Qt.ApplicationActive) {
                if (root.previewOpen) root.closeReport();
                root.releaseFence = []; root.cancelRecovery();
            }
        }
    }
    Connections {
        target: failureReports
        function onObservationChanged() {
            if (root.previewOpen && !root.available) root.closeReport();
        }
        function onDocumentCopyFinished(request, result) {
            if (!root.previewOpen) root.notice = result && typeof result.message === "string"
                ? result.message : qsTr("The document copy could not be verified. The private report was kept.");
        }
    }

    Rectangle {
        objectName: "nativeThemeFailureNotice"
        visible: root.notice !== ""
        x: vpx(50); width: parent.width - vpx(100)
        anchors.bottom: reviewButton.top; anchors.bottomMargin: vpx(20)
        height: resultText.implicitHeight + vpx(28)
        color: "#202122"
        Text {
            id: resultText
            x: vpx(14); y: vpx(14); width: parent.width - vpx(28)
            text: root.notice; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: "#eee"; font.family: globalFonts.sans; font.pixelSize: Math.max(14, vpx(20))
        }
    }
    Rectangle {
        id: reviewButton
        objectName: "nativeThemeFailureButton"
        visible: root.available && !root.previewOpen
        anchors.right: parent.right; anchors.rightMargin: vpx(50)
        anchors.bottom: parent.bottom; anchors.bottomMargin: vpx(32)
        width: parent.width / 2 - vpx(75)
        height: Math.max(44, vpx(55), reviewLabel.implicitHeight + vpx(20))
        color: pointer.containsMouse ? "#333" : "#000"
        border.width: Math.max(1, vpx(2)); border.color: "#eee"
        Text {
            id: reviewLabel
            anchors.centerIn: parent; width: parent.width - vpx(30)
            text: qsTr("Review failure · Details")
            color: "#eee"; font.family: globalFonts.sans; font.pixelSize: Math.max(14, vpx(20))
            wrapMode: Text.WordWrap; horizontalAlignment: Text.AlignHCenter
        }
        MouseArea { id: pointer; anchors.fill: parent; hoverEnabled: true; onClicked: root.openReport() }
        Accessible.role: Accessible.Button
        Accessible.name: qsTr("Review failure")
        Accessible.onPressAction: root.openReport()
    }
    Loader {
        id: preview
        anchors.fill: parent
        active: root.previewOpen
        source: "FailurePreview.qml"
        onLoaded: {
            item.report = Qt.binding(function() { return root.report; });
            item.bridge = failureReports; item.sans = globalFonts.sans;
            item.unit = Qt.binding(function() { return Math.min(root.width / 1280, root.height / 720); });
        }
        onStatusChanged: if (status === Loader.Error) {
            root.closeReport();
            root.notice = qsTr("The compiled preview could not load. Nothing was exported. The recovery action remains available.");
        }
    }
    Connections { target: preview.item; ignoreUnknownSignals: true; function onBack() { root.closeReport(); } }
}
