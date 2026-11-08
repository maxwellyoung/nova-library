import QtQuick 2.15
import "library.js" as Lib
Row {
    id: deviceStates
    property var entry: null
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property string fontFamily: ""
    property real size: 22
    property real textInset: size * 1.65
    readonly property bool bothUnknown: Lib.installation(entry,"nova").state === "unknown" && Lib.installation(entry,"legion").state === "unknown"
    spacing: size * 1.4
    Text {
        visible: deviceStates.bothUnknown
        text: "Installation not checked"
        color: deviceStates.quiet; font.family: deviceStates.fontFamily; font.pixelSize: deviceStates.size
    }
    Repeater {
        model: deviceStates.bothUnknown ? [] : ["nova", "legion"]
        delegate: Row {
            readonly property var fact: Lib.installation(deviceStates.entry, modelData)
            spacing: Math.max(0, deviceStates.textInset - deviceStates.size * 1.25)
            Icon { name: modelData; width: deviceStates.size * 1.25; height: width; ink: parent.fact.state === "installed" ? deviceStates.ink : deviceStates.quiet; y:(installLabel.height-height)/2 }
            Column {
                spacing: 2
                Text { id:installLabel; text: Lib.deviceName(modelData) + " · " + Lib.installLabel(deviceStates.entry, modelData); font.family: deviceStates.fontFamily; font.pixelSize: deviceStates.size; color: parent.parent.fact.state === "installed" ? deviceStates.ink : deviceStates.quiet }
                Text { visible: parent.parent.fact.state !== "unknown"; text: (parent.parent.fact.offline ? "Offline check · " : "Install checked · ") + String(parent.parent.fact.observedAt).slice(0,10); font.family: deviceStates.fontFamily; font.pixelSize: deviceStates.size * 0.75; color: deviceStates.quiet }
            }
        }
    }
}
