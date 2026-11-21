import QtQuick 2.15
import "library.js" as Lib
Column {
    id: capacity
    property var evidence: null
    property string volumeName: "Internal storage"
    property string evidenceStatus: "unknown"
    property string selectedCategory: ""
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property color slab: "#1a1c1e"
    property color warning: "#dca56a"
    property string fontFamily: ""
    property real size: 26
    readonly property bool known: evidence !== null && evidence !== undefined
    height: size * 5.4
    spacing: size * 0.45
    Text {
        width: parent.width
        text: capacity.volumeName + " · " + (capacity.known ? Lib.bytesText(capacity.evidence.free) + " free at snapshot" : capacity.evidenceStatus === "conflict" ? "Snapshot values conflict" : "Free space not checked")
        color: capacity.known && capacity.evidence.free / capacity.evidence.total < 0.05 ? capacity.warning : capacity.ink
        font.family: capacity.fontFamily; font.pixelSize: capacity.size; font.weight: Font.DemiBold
        maximumLineCount: 1; elide: Text.ElideRight
    }
    Rectangle {
        width: capacity.width; height: capacity.size * 0.6; color: capacity.slab
        id: capacityTrack
        objectName: "capacityTrack"
        Repeater {
            model: Lib.capacitySegments(capacity.evidence)
            delegate: Rectangle {
                objectName: "capacityPart_"+modelData.id
                x: capacity.evidence ? capacityTrack.width*modelData.offset/capacity.evidence.total : 0
                width: capacityTrack.width*modelData.fraction
                height: capacityTrack.height
                visible: modelData.bytes>0
                color: modelData.id==="free" && capacity.evidence && capacity.evidence.free/capacity.evidence.total<0.05 ? capacity.warning : capacity.ink
                readonly property real shade: ({"game-data":0.85,"app-data":0.65,cache:0.5,"save-data":0.35,unclassified:0.25,unavailable:0.1,free:0.95})[modelData.id]
                opacity: modelData.id==="free" && capacity.evidence && capacity.evidence.free/capacity.evidence.total<0.05 ? 1
                    : capacity.selectedCategory===modelData.id?1:capacity.selectedCategory?shade*0.35:shade
            }
        }
    }
    Text { text: capacity.known ? Lib.bytesText(capacity.evidence.used) + " used / " + Lib.bytesText(capacity.evidence.total) + " total" : "No filesystem capacity snapshot"; color: capacity.quiet; font.family: capacity.fontFamily; font.pixelSize: capacity.size * 0.8 }
    Text { text: capacity.known ? "Snapshot · " + Lib.dateEvidenceText(capacity.evidence.observedAt) : "ROM sizes below do not establish free space"; color: capacity.quiet; font.family: capacity.fontFamily; font.pixelSize: capacity.size * 0.7 }
}
