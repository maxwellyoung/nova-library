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
        function rbox(x,y,w,h,r) { c.beginPath(); c.moveTo(x+r,y); c.lineTo(x+w-r,y); c.arcTo(x+w,y,x+w,y+r,r); c.lineTo(x+w,y+h-r); c.arcTo(x+w,y+h,x+w-r,y+h,r); c.lineTo(x+r,y+h); c.arcTo(x,y+h,x,y+h-r,r); c.lineTo(x,y+r); c.arcTo(x,y,x+r,y,r); c.closePath(); c.stroke(); }
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
        // Console glyphs: original line drawings of each system's hardware, not maker logos.
        case "snes": rbox(1.5,7.5,21,9,4.5);line([5,10.5,5,13.5]);line([3.5,12,6.5,12]);circle(17,10.3,0.9);circle(19.2,12,0.9);circle(14.8,12,0.9);circle(17,13.7,0.9);line([10,13,11,13]);line([13,13,14,13]);break;
        case "n64": line([2,8,22,8]);line([2,8,3,14,6,14,7,10]);line([10,10,10.5,20,13.5,20,14,10]);line([17,10,18,14,21,14,22,8]);circle(12,12.5,1.2);line([4,10.5,5,10.5]);circle(19,9.5,0.6);circle(20.5,11,0.6);break;
        case "gc": line([3,9,7,6,17,6,21,9,22,16,19,19,16,15,8,15,5,19,2,16,3,9]);circle(7,10,1.6);circle(17.5,10.5,2);circle(14.8,8.4,0.7);circle(15.4,12.7,0.9);break;
        case "psx": line([3,8,21,8,23,18,20,20,16,14,8,14,4,20,1,18,3,8]);line([6,9.8,6,12.6]);line([4.6,11.2,7.4,11.2]);circle(18,9.7,0.7);circle(19.6,11.2,0.7);circle(16.4,11.2,0.7);circle(18,12.7,0.7);break;
        case "ps2": line([3,8,21,8,23,18,20,20,16,14,8,14,4,20,1,18,3,8]);line([5.4,9.4,5.4,11.6]);line([4.3,10.5,6.5,10.5]);circle(18.6,9.3,0.6);circle(20,10.6,0.6);circle(17.2,10.6,0.6);circle(18.6,11.9,0.6);circle(9,12.2,1.3);circle(15,12.2,1.3);break;
        case "psp": rbox(1,7,22,10,5);box(6.5,8.5,11,7);line([3.7,10.6,3.7,13.4]);line([2.3,12,5.1,12]);circle(20.3,10.6,0.6);circle(20.3,13.4,0.6);break;
        case "dreamcast": line([4,6,20,6,22,12,19,21,15,15,9,15,5,21,2,12,4,6]);box(9.5,6,5,4);circle(7,11,1.6);circle(17,10.2,0.6);circle(18.6,11.8,0.6);circle(15.4,11.8,0.6);circle(17,13.4,0.6);break;
        case "gbc": rbox(5.5,1.5,13,21,2);box(7.5,3.5,9,7);line([9,14,9,17]);line([7.5,15.5,10.5,15.5]);circle(15.8,14.6,0.8);circle(14,16.4,0.8);line([10,20,11,20]);line([13,20,14,20]);break;
        case "nds": rbox(4,1.5,16,9.5,1.5);box(6.5,3,11,6.5);rbox(4,12,16,10.5,1.5);box(8,13.5,8,6);line([5.8,16,5.8,19]);line([4.6,17.5,7,17.5]);circle(18.2,16.4,0.5);circle(18.2,18.6,0.5);break;
        case "pc": box(2,4,20,13);line([9,21,15,21]);line([12,17,12,21]);line([5,14,8,14]);break;
        default: circle(12,12,9);line([12,10,12,17]);circle(12,6.5,0.5);break;
        }
    }
}
