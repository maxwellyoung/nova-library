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
    // Fade in art that arrives after an asynchronous load. Cached art and
    // reduced motion appear at once; callers opt in.
    property bool fadeIn: false
    property bool arrivedLate: false

    readonly property bool hasArt: entry !== null && entry.art !== "" && image.status !== Image.Error
    readonly property bool loaded: hasArt && image.status === Image.Ready && image.implicitHeight > 0
    readonly property bool loading: image.status === Image.Loading
    readonly property real ratio: loaded ? image.implicitWidth / image.implicitHeight : 2 / 3
    // Short preview boxes need a smaller fallback without shrinking real artwork.
    readonly property real fallbackUnit: Math.min(width, height * 2 / 3)

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
        opacity: art.loaded ? 1 : 0
        Behavior on opacity {
            enabled: art.fadeIn && art.arrivedLate
            NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
        }
        onStatusChanged: if (status === Image.Loading) art.arrivedLate = true
    }

    Rectangle {
        objectName: "artFallback"
        anchors.fill: parent
        visible: !art.loaded && art.width > 0 && art.height > 0
        clip: true
        color: art.slabColor

        Column {
            objectName: "artFallbackHeader"
            visible: art.fallbackUnit >= 140
            x: Math.round(art.fallbackUnit * 0.08); y: x
            width: parent.width - x * 2
            spacing: Math.round(art.fallbackUnit * 0.05)
            Icon {
                name: Lib.consoleGlyph(art.entry ? art.entry.systemId : "")
                width: Lib.consoleWordmark(art.entry ? art.entry.systemId : "") ? Math.min(180,art.fallbackUnit*.65) : Math.min(80,art.fallbackUnit*.25)
                height: Math.min(80,art.fallbackUnit*.25)
                ink: art.quietColor
            }
            Text {
                width: parent.width
                text: art.entry ? Lib.consoleShortName({id:art.entry.systemId,name:art.entry.systemName}) : ""
                color: art.quietColor; font.family: art.fontFamily
                font.pixelSize: Math.max(11,Math.round(art.fallbackUnit * 0.055))
                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
            }
        }

        Column {
            objectName: "artFallbackBody"
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: Math.round(art.fallbackUnit * 0.08)
            y: art.fallbackUnit >= 140 ? art.height * .43 : parent.height-height-Math.round(art.fallbackUnit*.08)
            spacing: Math.round(art.fallbackUnit * 0.03)

            FontMetrics { id: titleMetrics; font: fallbackTitle.font }
            Text {
                id: fallbackTitle
                width: parent.width
                text: art.entry ? art.entry.title : ""
                color: art.textColor
                font.family: art.fontFamily
                font.weight: Font.DemiBold
                font.pixelSize: Math.max(1, Math.min(Math.max(12, Math.round(art.fallbackUnit * (art.fallbackUnit >= 140 ? 0.14 : 0.1))), Math.floor((art.height - Math.round(art.fallbackUnit * .16)) / 2)))
                lineHeight: 1.15
                wrapMode: Text.Wrap
                maximumLineCount: art.fallbackUnit >= 140 ? 3 : Math.max(1, Math.min(4, Math.floor((art.height - Math.round(art.fallbackUnit * .16)) / Math.max(1, titleMetrics.lineSpacing * 1.15))))
                elide: Text.ElideRight
            }
            Text {
                width: parent.width
                visible: art.fallbackUnit >= 140
                text: art.loading ? "Loading artwork…" : "No cover yet"
                color: art.quietColor
                font.family: art.fontFamily
                font.pixelSize: Math.max(10, Math.round(art.fallbackUnit * 0.07))
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
