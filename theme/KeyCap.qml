import QtQuick 2.15

// A binding, not a new button: the parent owns the action and its touch target.
Item {
    property string label: ""
    property string fontFamily: ""
    property real textSize: 20
    property color ink: "#e9eaea"
    property color ground: "#0c0d0e"
    property bool primary: false
    implicitWidth: Math.max(implicitHeight,keyText.implicitWidth+textSize*.65)
    implicitHeight: textSize*1.45
    width: implicitWidth; height: implicitHeight
    Rectangle {
        anchors.fill: parent
        radius: label.length === 1 ? height/2 : textSize*.18
        color: primary ? ink : "transparent"
        border.width: 1
        border.color: ink
        opacity: primary ? 1 : .75
    }
    Text {
        id: keyText
        anchors.centerIn: parent
        text: label; color: primary ? ground : ink
        font.family: fontFamily; font.pixelSize: textSize; font.weight: Font.DemiBold
    }
}
