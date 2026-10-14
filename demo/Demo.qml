import QtQuick 2.15
import QtQuick.Window 2.15
import "generated/games.js" as DemoData

Window {
    id: window
    visible: true
    width: 1280
    height: 800
    title: "Nova — synthetic demo"
    color: "#0c0d0e"

    // Context values match the subset of Pegasus API used by the actual theme.
    // The demo cannot launch programs or contact a service.
    property var global: ({ fonts: { sans: Qt.application.font.family } })
    property var deviceLibrary: null
    property QtObject api: QtObject {
        property QtObject allGames: QtObject {
            property int count: DemoData.games.length
            function get(index) {
                var source = DemoData.games[index];
                return {
                    title: source.title, sortBy: source.sortBy, developer: source.developer,
                    genre: source.genre, missing: source.missing, lastPlayed: source.lastPlayed,
                    favorite: false, playCount: 0, extra: source.extra,
                    assets: { boxFront: Qt.resolvedUrl("generated/" + source.cover).toString() },
                    files: { count: 1, get: function() { return { path: source.file }; } },
                    launch: function() { console.log("Synthetic demo has no launch route."); }
                };
            }
        }
        property QtObject memory: QtObject {
            property var values: ({})
            function has(key) { return Object.prototype.hasOwnProperty.call(values, key); }
            function get(key) { return values[key]; }
            function set(key, value) { values[key] = value; }
            function unset(key) { delete values[key]; }
        }
        property QtObject keys: QtObject {
            property var accept: [{name: function() { return "Enter"; }}]
            property var cancel: [{name: function() { return "Esc"; }}]
            property var details: [{name: function() { return "X"; }}]
            property var filters: [{name: function() { return "Y"; }}]
            property var prevPage: [{name: function() { return "PgUp"; }}]
            property var nextPage: [{name: function() { return "PgDn"; }}]
            function isAccept(e) { return e.key === Qt.Key_Return || e.key === Qt.Key_Enter; }
            function isCancel(e) { return e.key === Qt.Key_Escape; }
            function isDetails(e) { return e.key === Qt.Key_X; }
            function isFilters(e) { return e.key === Qt.Key_Y; }
            function isPrevPage(e) { return e.key === Qt.Key_PageUp; }
            function isNextPage(e) { return e.key === Qt.Key_PageDown; }
            function isLeft(e) { return e.key === Qt.Key_Left; }
            function isRight(e) { return e.key === Qt.Key_Right; }
            function isUp(e) { return e.key === Qt.Key_Up; }
            function isDown(e) { return e.key === Qt.Key_Down; }
            function isPageUp(e) { return e.key === Qt.Key_Home; }
            function isPageDown(e) { return e.key === Qt.Key_End; }
        }
    }

    Loader {
        id: themeLoader
        anchors.fill: parent
        source: "../theme/theme.qml"
        onLoaded: item.forceActiveFocus()
    }
}
