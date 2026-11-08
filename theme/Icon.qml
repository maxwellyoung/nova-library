import QtQuick 2.15
import "PlatformMarks.js" as PlatformMarks

// Original action and device lines; console identities are the credited paths in PlatformMarks.
// Labels remain beside actions and device states.
Canvas {
    id: icon
    property string name: "info"
    property color ink: "#e9eaea"
    property real strokeWidth: 1.7
    property real alignX: 0.5
    onNameChanged: requestPaint()
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onStrokeWidthChanged: requestPaint()
    onPaint: {
        var c = getContext("2d"); c.reset();
        c.strokeStyle = ink; c.fillStyle = ink; c.lineWidth = strokeWidth; c.lineCap = "round"; c.lineJoin = "round";
        if (PlatformMarks.draw(c, name, width, height, alignX)) return;
        // Line drawings stay undistorted in the wider console slots.
        var unit = Math.min(width, height) / 24;
        c.translate((width - 24 * unit) * alignX, (height - 24 * unit) / 2);
        c.scale(unit, unit);
        function line(points) { c.beginPath(); c.moveTo(points[0], points[1]); for (var i=2;i<points.length;i+=2)c.lineTo(points[i],points[i+1]); c.stroke(); }
        function box(x,y,w,h) { c.strokeRect(x,y,w,h); }
        function circle(x,y,r) { c.beginPath(); c.arc(x,y,r,0,Math.PI*2); c.stroke(); }
        function dot(x,y,r) { c.beginPath(); c.arc(x,y,r,0,Math.PI*2); c.fill(); }
        function rbox(x,y,w,h,r) { c.beginPath(); c.moveTo(x+r,y); c.lineTo(x+w-r,y); c.arcTo(x+w,y,x+w,y+r,r); c.lineTo(x+w,y+h-r); c.arcTo(x+w,y+h,x+w-r,y+h,r); c.lineTo(x+r,y+h); c.arcTo(x,y+h,x,y+h-r,r); c.lineTo(x,y+r); c.arcTo(x,y,x+r,y,r); c.closePath(); c.stroke(); }
        switch(name) {
        case "home": line([3,11,12,3,21,11]); line([5,10,5,21,10,21,10,15,14,15,14,21,19,21,19,10]); break;
        case "library": box(3,4,4,16);box(10,4,4,16);line([17,5,20,4,23,19,20,20,17,5]);break;
        case "nova": rbox(1,5.5,22,13,3);box(6.5,8,11,8);line([3.8,10.5,3.8,13.5]);line([2.5,12,5.1,12]);dot(20,10.5,0.7);dot(20,14,0.7);break;
        case "legion": rbox(1,4,4,16,1.5);box(7,4,10,16);rbox(19,4,4,16,1.5);dot(3,8,0.7);dot(21,8,0.7);line([3,13,3,16]);line([21,13,21,16]);break;
        case "threads": line([2,7,10,7,12,9,22,9,22,20,2,20,2,7]);break;
        case "apps": box(3,3,7,7);box(14,3,7,7);box(3,14,7,7);box(14,14,7,7);break;
        case "settings": line([4,3,4,7]);line([4,13,4,21]);rbox(1.5,7,5,6,1);line([12,3,12,13]);line([12,19,12,21]);rbox(9.5,13,5,6,1);line([20,3,20,5]);line([20,11,20,21]);rbox(17.5,5,5,6,1);break;
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
        case "system": box(2,5,20,14);line([5,9,16,9]);circle(18,15,1);break;
        default: circle(12,12,9);line([12,10,12,17]);circle(12,6.5,0.5);break;
        }
    }
}
