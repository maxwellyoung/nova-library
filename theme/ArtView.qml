import QtQuick 2.15

// Cover art at its natural ratio, or a plain title slab when there is none.
// The parent sizes this item; `ratio` reports the source's own shape so the
// parent can do equal-area sizing without cropping.
Item {
    id: art

    property var entry: null
    property string fontFamily: ""
    property color slabColor: "#1a1c1e"
    property color textColor: "#e9eaea"
    property color quietColor: "#9a9b9b"
    property color veilColor: "#0c0d0e"
    property real veil: 0
    property int decodeHeight: 720

    readonly property bool hasArt: entry !== null && entry.art !== "" && image.status !== Image.Error
    readonly property bool loaded: hasArt && image.status === Image.Ready && image.implicitHeight > 0
    readonly property real ratio: loaded ? image.implicitWidth / image.implicitHeight : 2 / 3

    Image {
        id: image
        anchors.fill: parent
        source: art.entry ? art.entry.art : ""
        asynchronous: true
        cache: true
        smooth: true
        fillMode: Image.PreserveAspectFit
        sourceSize.height: art.decodeHeight
        visible: art.loaded
    }

    Rectangle {
        anchors.fill: parent
        visible: !art.hasArt
        color: art.slabColor

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            anchors.margins: Math.round(art.width * 0.08)
            spacing: Math.round(art.width * 0.03)

            Text {
                width: parent.width
                text: art.entry ? art.entry.title : ""
                color: art.textColor
                font.family: art.fontFamily
                font.weight: Font.DemiBold
                font.pixelSize: Math.max(12, Math.round(art.width * 0.1))
                lineHeight: 1.15
                wrapMode: Text.Wrap
                maximumLineCount: 4
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: text !== ""
                text: art.entry && art.entry.launchable ? art.entry.route : ""
                color: art.quietColor
                font.family: art.fontFamily
                font.pixelSize: Math.max(10, Math.round(art.width * 0.07))
                elide: Text.ElideRight
            }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: art.veil > 0
        color: art.veilColor
        opacity: art.veil
    }
}
