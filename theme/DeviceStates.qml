import QtQuick 2.15
import "library.js" as Lib
Row {
    id: deviceStates
    property var entry: null
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property string fontFamily: ""
    property real size: 22
    spacing: size * 1.4
    Repeater {
        model: ["nova", "legion"]
        delegate: Row {
            readonly property var fact: Lib.installation(deviceStates.entry, modelData)
            spacing: deviceStates.size * 0.4
            Icon { name: modelData; width: deviceStates.size * 1.25; height: width; ink: parent.fact.state === "installed" ? deviceStates.ink : deviceStates.quiet; anchors.verticalCenter: parent.verticalCenter }
            Column {
                spacing: 2
                Text { text: Lib.deviceName(modelData) + " · " + Lib.installLabel(deviceStates.entry, modelData); font.family: deviceStates.fontFamily; font.pixelSize: deviceStates.size; color: parent.parent.fact.state === "installed" ? deviceStates.ink : deviceStates.quiet }
                Text { visible: parent.parent.fact.state !== "unknown"; text: (parent.parent.fact.offline ? "Offline · " : "Checked · ") + String(parent.parent.fact.observedAt).slice(0,10); font.family: deviceStates.fontFamily; font.pixelSize: deviceStates.size * 0.75; color: deviceStates.quiet }
            }
        }
    }
}
