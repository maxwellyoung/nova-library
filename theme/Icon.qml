import QtQuick 2.15

// Small original line symbols. Labels remain beside actions and device states.
Canvas {
    id: icon
    property string name: "info"
    property color ink: "#e9eaea"
    property real strokeWidth: 1.7
    onNameChanged: requestPaint()
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset(); c.scale(width / 24, height / 24);
        c.strokeStyle = ink; c.fillStyle = ink; c.lineWidth = strokeWidth; c.lineCap = "round"; c.lineJoin = "round";
        function line(points) { c.beginPath(); c.moveTo(points[0], points[1]); for (var i=2;i<points.length;i+=2)c.lineTo(points[i],points[i+1]); c.stroke(); }
        function box(x,y,w,h) { c.strokeRect(x,y,w,h); }
        function circle(x,y,r) { c.beginPath(); c.arc(x,y,r,0,Math.PI*2); c.stroke(); }
        switch(name) {
        case "home": line([3,11,12,3,21,11]); line([5,10,5,21,10,21,10,15,14,15,14,21,19,21,19,10]); break;
        case "library": box(3,4,4,16);box(10,4,4,16);line([17,5,20,4,23,19,20,20,17,5]);break;
        case "consoles": case "nova": case "legion": box(2,6,20,12);box(7,8,10,8);line([4,11,4,15]);line([2.5,13,5.5,13]);circle(20,11,0.6);circle(19,15,0.6);break;
        case "threads": line([2,7,10,7,12,9,22,9,22,20,2,20,2,7]);break;
        case "apps": box(3,3,7,7);box(14,3,7,7);box(3,14,7,7);box(14,14,7,7);break;
        case "settings": circle(12,12,4);circle(12,12,9);line([12,1,12,4]);line([12,20,12,23]);line([1,12,4,12]);line([20,12,23,12]);break;
        case "storage": box(3,5,18,14);line([3,14,21,14]);circle(17,17,0.6);break;
        case "aspect": box(2,5,20,14);line([6,5,6,19]);line([18,5,18,19]);break;
        case "disc": circle(12,12,9);circle(12,12,2);line([8,5,5,8]);break;
        case "star": line([12,2,15,8,22,9,17,14,18,21,12,18,6,21,7,14,2,9,9,8,12,2]);break;
        case "check": line([4,12,9,17,20,6]);break;
        case "clock": circle(12,12,9);line([12,6,12,12,16,15]);break;
        case "play": line([7,3,21,12,7,21,7,3]);break;
        case "back": line([12,4,4,12,12,20]);line([4,12,21,12]);break;
        case "sync": line([3,9,6,4,18,4,21,9]);line([18,9,21,9,21,5]);line([21,15,18,20,6,20,3,15]);line([6,15,3,15,3,19]);break;
        case "note": box(4,3,16,18);line([8,8,16,8]);line([8,12,16,12]);line([8,16,13,16]);break;
        default: circle(12,12,9);line([12,10,12,17]);circle(12,6.5,0.5);break;
        }
    }
}
