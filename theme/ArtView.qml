import QtQuick 2.15
import "library.js" as Lib

// Cover art at its natural ratio, or a plain title slab when there is none.
// The parent sizes this item; `ratio` reports the source's own shape so the
// parent can do equal-area sizing without cropping.
Item {
    id: art
    objectName: "coverArt"

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
    readonly property bool loading: image.status === Image.Loading
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
        objectName: "artFallback"
        anchors.fill: parent
        visible: !art.loaded
        color: art.slabColor

        Column {
            visible: art.width >= 140
            x: Math.round(art.width * 0.08); y: x
            width: parent.width - x * 2
            spacing: Math.round(art.width * 0.05)
            Icon {
                name: Lib.consoleGlyph(art.entry ? art.entry.systemId : "")
                width: Lib.consoleWordmark(art.entry ? art.entry.systemId : "") ? Math.min(180,art.width*.65) : Math.min(80,art.width*.25)
                height: Math.min(80,art.width*.25)
                ink: art.quietColor
            }
            Text {
                width: parent.width
                text: art.entry ? Lib.consoleShortName({id:art.entry.systemId,name:art.entry.systemName}) : ""
                color: art.quietColor; font.family: art.fontFamily
                font.pixelSize: Math.max(11,Math.round(art.width * 0.055))
                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
            }
        }

        Column {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Math.round(art.width * 0.08)
            y: art.width >= 140 ? art.height * .43 : parent.height-height-Math.round(art.width*.08)
            spacing: Math.round(art.width * 0.03)

            Text {
                width: parent.width
                text: art.entry ? art.entry.title : ""
                color: art.textColor
                font.family: art.fontFamily
                font.weight: Font.DemiBold
                font.pixelSize: Math.max(12, Math.round(art.width * (art.width >= 140 ? 0.14 : 0.1)))
                lineHeight: 1.15
                wrapMode: Text.Wrap
                maximumLineCount: art.width >= 140 ? 3 : 4
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: art.width >= 140
                text: art.loading ? "Loading artwork…" : "No cover yet"
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
