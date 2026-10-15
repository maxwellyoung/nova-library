import QtQuick 2.15
import "library.js" as Lib
Column {
    id: capacity
    property var evidence: null
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property color slab: "#1a1c1e"
    property color warning: "#dca56a"
    property string fontFamily: ""
    property real size: 26
    readonly property bool known: evidence !== null
    height: size * 5.4
    spacing: size * 0.45
    Row {
        spacing: capacity.size * 0.45
        Icon { name: "storage"; width: capacity.size; height: width; ink: capacity.ink }
        Text { text: capacity.known ? Lib.bytesText(capacity.evidence.free) + " available" : "Free space not checked"; color: capacity.known && capacity.evidence.free / capacity.evidence.total < 0.05 ? capacity.warning : capacity.ink; font.family: capacity.fontFamily; font.pixelSize: capacity.size; font.weight: Font.DemiBold }
    }
    Rectangle {
        width: capacity.width; height: capacity.size * 0.6; color: capacity.slab
        Rectangle { visible: capacity.known; height: parent.height; width: capacity.known ? parent.width * capacity.evidence.used / capacity.evidence.total : 0; color: capacity.ink; opacity: 0.55 }
        Rectangle { visible: capacity.known; anchors.right: parent.right; height: parent.height; width: capacity.known ? parent.width * capacity.evidence.free / capacity.evidence.total : 0; color: capacity.evidence && capacity.evidence.free / capacity.evidence.total < 0.05 ? capacity.warning : capacity.ink }
    }
    Text { text: capacity.known ? Lib.bytesText(capacity.evidence.used) + " used / " + Lib.bytesText(capacity.evidence.total) + " total" : "No filesystem capacity snapshot"; color: capacity.quiet; font.family: capacity.fontFamily; font.pixelSize: capacity.size * 0.8 }
    Text { text: capacity.known ? "Snapshot · " + Lib.dateEvidenceText(capacity.evidence.observedAt) : "ROM sizes below do not establish free space"; color: capacity.quiet; font.family: capacity.fontFamily; font.pixelSize: capacity.size * 0.7 }
}
