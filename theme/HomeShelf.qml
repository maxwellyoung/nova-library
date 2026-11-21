import QtQuick 2.15
import QtQml 2.15
import "library.js" as Lib

// Presentation only. The parent owns selection, notes, launch and return state.
Item {
    id: surface
    objectName: "homeShelf"
    property var entries: []
    property int selectedIndex: 0
    property bool focusActive: true
    property bool reducedMotion: false
    property bool active: visible
    property string heading: "Your games"
    property string contextText: ""
    property string statusText: ""
    property string checkpointText: ""
    property bool canOpenNotebook: false
    property string emptyTitle: "Nothing on Home yet."
    property string emptyText: "Choose a game in Library."
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property color slab: "#1a1c1e"
    property string fontFamily: ""
    property real textScale: 1
    readonly property real scale: Math.max(0.5, Math.min(width / 1280, height / 800))
    readonly property int currentIndex: entries.length ? Math.max(0, Math.min(entries.length - 1, selectedIndex)) : -1
    readonly property var current: currentIndex >= 0 ? entries[currentIndex] : null
    readonly property real stageTop: greeting.y + greeting.height + px(24)
    readonly property real stageBottom: Math.max(stageTop, information.y - px(28))
    readonly property real focusHeight: Math.max(0, Math.min(px(440), stageBottom - stageTop - px(40)))
    readonly property real coverArea: focusHeight * focusHeight * 2 / 3
    signal selectionRequested(int index)
    signal detailsRequested()
    signal notebookRequested()
    function px(value) { return Math.round(value * scale); }
    function fs(value) { return Math.round(value * scale * textScale); }
    function select(index) {
        if (entries.length) selectionRequested(Math.max(0, Math.min(entries.length - 1, index)));
    }

    Item {
        id: greeting
        objectName: "homeGreeting"
        x: surface.px(64); y: surface.px(104)
        width: parent.width - surface.px(128)
        height: headingText.height
        Text {
            id: headingText
            width: parent.width - (position.visible ? position.width + surface.px(24) : 0)
            text: surface.heading; textFormat: Text.PlainText; elide: Text.ElideRight
            color: surface.ink; font.family: surface.fontFamily; font.pixelSize: surface.fs(28)
            font.weight: Font.DemiBold
        }
        Text {
            id: position
            objectName: "homeShelfPosition"
            anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
            visible: surface.entries.length > 1
            text: (surface.currentIndex + 1) + " / " + surface.entries.length
            color: surface.quiet; font.family: surface.fontFamily; font.pixelSize: surface.fs(20)
        }
    }

    Item {
        id: stage
        objectName: "homeShelfStage"
        y: surface.stageTop
        width: parent.width; height: Math.max(0, surface.stageBottom - y)
        clip: true; visible: surface.current !== null
        Row {
            id: row
            property real focusX: 0
            x: stage.width / 2 - focusX
            height: stage.height - surface.px(12)
            spacing: surface.px(54)
            Behavior on x {
                enabled: surface.active && !surface.reducedMotion
                NumberAnimation { duration: 120; easing.type: Easing.OutCubic }
            }
            Repeater {
                id: items
                model: surface.entries
                delegate: Item {
                    id: cell
                    objectName: "homeShelfCell_" + index
                    readonly property bool selected: index === surface.currentIndex
                    readonly property real factor: selected ? 1 : 0.78
                    readonly property real ratio: artwork.item ? artwork.item.ratio : 2 / 3
                    readonly property var fit: Lib.fitArea(ratio, surface.coverArea * factor * factor,
                                                         surface.width * 0.46 * factor, surface.focusHeight * factor)
                    readonly property real edge: surface.px(7)
                    readonly property var caseItem: object
                    readonly property var caseArt: artwork.item
                    width: fit.w + edge * 2; height: row.height
                    opacity: Math.abs(index - surface.currentIndex) <= 2 ? 1 : 0
                    Binding {
                        target: row; property: "focusX"
                        value: cell.x + cell.width / 2
                        when: cell.selected
                        restoreMode: Binding.RestoreNone
                    }
                    Item {
                        id: object
                        objectName: "homeShelfObject_" + index
                        width: cell.width; height: cell.fit.h + cell.edge * 2
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: cell.selected ? surface.px(9) : 0
                        // Shallow neutral case depth, not a claim about the original media.
                        Rectangle {
                            x: surface.px(8); y: surface.px(11); width: parent.width; height: parent.height
                            radius: surface.px(3); color: "#000000"; opacity: cell.selected ? 0.18 : 0.09
                        }
                        Rectangle {
                            anchors.fill: parent; radius: surface.px(3)
                            color: Qt.darker(surface.slab, 1.18)
                            border.color: Qt.rgba(surface.ink.r, surface.ink.g, surface.ink.b, cell.selected ? 0.45 : 0.18)
                            border.width: 1
                        }
                        Rectangle {
                            x: surface.px(2); y: surface.px(3); width: cell.edge - surface.px(2)
                            height: parent.height - surface.px(6); radius: 1
                            color: Qt.lighter(surface.slab, 1.5)
                            opacity: cell.selected ? 0.9 : 0.5
                        }
                        Loader {
                            id: artwork
                            x: cell.edge; y: cell.edge
                            width: cell.fit.w; height: cell.fit.h
                            active: Math.abs(index - surface.currentIndex) <= 2
                            sourceComponent: Component {
                                ArtView {
                                    entry: modelData
                                    fontFamily: surface.fontFamily; slabColor: surface.slab
                                    textColor: surface.ink; quietColor: surface.quiet; veilColor: surface.ground
                                    // Keep decode size independent of fit/ratio: changing it
                                    // during selection reloads the image and cycles the fit.
                                    decodeHeight: 720
                                    veil: cell.selected ? (modelData.launchable ? 0 : 0.24) : 0.32
                                }
                            }
                        }
                        Rectangle {
                            x: 0; y: parent.height + surface.px(6); width: parent.width; height: Math.max(2, surface.px(2))
                            color: surface.ink; visible: cell.selected && surface.focusActive
                        }
                    }
                }
            }
        }
        MouseArea {
            id: pointer
            objectName: "homeShelfPointer"
            anchors.fill: parent
            property real startX: 0
            property bool tracking: false
            onPressed: function(mouse) { startX = mouse.x; tracking = true; }
            onCanceled: tracking = false
            onReleased: function(mouse) {
                if (!tracking) return;
                tracking = false;
                var distance = mouse.x - startX;
                if (Math.abs(distance) > surface.px(40)) {
                    var step = Math.max(1, Math.round(Math.abs(distance) / surface.px(260)));
                    surface.select(surface.currentIndex + (distance < 0 ? step : -step));
                    return;
                }
                for (var i = 0; i < items.count; i++) {
                    var item = items.itemAt(i);
                    if (!item || !item.opacity) continue;
                    var object = item.caseItem;
                    if (!object) continue;
                    var point = pointer.mapToItem(object, mouse.x, mouse.y);
                    if (point.x >= 0 && point.x <= object.width && point.y >= 0 && point.y <= object.height) {
                        if (i === surface.currentIndex) surface.detailsRequested();
                        else surface.select(i);
                        return;
                    }
                }
            }
        }
    }

    Column {
        id: information
        objectName: "homeShelfInformation"
        x: surface.px(64); y: surface.height - surface.px(116) - height
        width: parent.width - surface.px(128); spacing: surface.px(7)
        visible: surface.current !== null
        Row {
            width: parent.width; spacing: surface.px(10)
            Icon {
                name: Lib.consoleCardGlyph(surface.current ? surface.current.systemId : "")
                width: surface.px(28); height: surface.px(22); alignX: 0; ink: surface.quiet
            }
            Text {
                width: parent.width - surface.px(38)
                text: surface.contextText; textFormat: Text.PlainText; elide: Text.ElideRight
                color: surface.quiet; font.family: surface.fontFamily; font.pixelSize: surface.fs(20)
            }
        }
        Text {
            objectName: "homeShelfTitle"
            width: parent.width; text: Lib.displayTitle(surface.current); textFormat: Text.PlainText
            wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight
            color: surface.ink; font.family: surface.fontFamily; font.pixelSize: surface.fs(40); font.weight: Font.DemiBold
        }
        Text {
            width: parent.width; text: surface.statusText; textFormat: Text.PlainText
            visible: text !== ""; elide: Text.ElideRight
            color: surface.quiet; font.family: surface.fontFamily; font.pixelSize: surface.fs(20)
        }
        Text {
            objectName: "homeCheckpoint"
            width: parent.width; text: surface.checkpointText; textFormat: Text.PlainText
            visible: text !== ""; wrapMode: Text.Wrap; maximumLineCount: surface.width / surface.height >= 1.5 ? 1 : 2
            elide: Text.ElideRight; color: surface.quiet; font.family: surface.fontFamily; font.pixelSize: surface.fs(22)
            MouseArea {
                objectName: "homeNote"
                anchors.fill: parent; enabled: surface.canOpenNotebook
                onClicked: surface.notebookRequested()
            }
        }
    }
    Column {
        x: surface.px(64); y: surface.px(220)
        width: parent.width - surface.px(128); spacing: surface.px(10)
        visible: surface.current === null
        Text {
            width: parent.width; text: surface.emptyTitle; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: surface.ink; font.family: surface.fontFamily; font.pixelSize: surface.fs(36); font.weight: Font.DemiBold
        }
        Text {
            width: parent.width; text: surface.emptyText; textFormat: Text.PlainText; wrapMode: Text.Wrap
            color: surface.quiet; font.family: surface.fontFamily; font.pixelSize: surface.fs(26)
        }
    }
}
