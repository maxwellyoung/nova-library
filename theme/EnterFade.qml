import QtQuick 2.15

// Fades an overlay in and lifts it into place when it opens from the base
// screen. Closing stays instant, swaps between overlays stay instant (the
// caller passes fromBase), and reduced motion turns it off. Declare it inside
// the overlay; it drives the parent's opacity and a Translate it installs.
Item {
    id: fade
    property bool allowed: true
    property bool fromBase: true
    property real rise: 8
    readonly property Item target: parent
    width: 0; height: 0

    Translate { id: shift }
    Component.onCompleted: if (target) target.transform = [shift]

    function settle() {
        run.stop();
        if (target) target.opacity = 1;
        shift.y = 0;
    }

    Connections {
        target: fade.target
        function onVisibleChanged() {
            if (fade.target.visible && fade.allowed && fade.fromBase) run.restart();
            else fade.settle();
        }
    }

    ParallelAnimation {
        id: run
        NumberAnimation { target: fade.target; property: "opacity"; from: 0; to: 1; duration: 140; easing.type: Easing.OutCubic }
        NumberAnimation { target: shift; property: "y"; from: fade.rise; to: 0; duration: 140; easing.type: Easing.OutCubic }
    }
}
