import QtQuick 2.15

Item {
    id: root
    property string source: ""
    property string title: ""
    property var copy: null
    property string sans: ""
    property color ink: "white"
    property color quiet: "#999999"
    property real unit: 1
    property real textScale: 1
    property real usableHeight: height
    function px(v){return Math.round(v*unit);}
    function fs(v){return Math.round(v*unit*textScale);}
    MouseArea {anchors.fill:parent}
    Column {
        id: heading
        x:root.px(64);y:root.px(48);width:parent.width-root.px(128);spacing:root.px(10)
        Text {width:parent.width;text:root.title;textFormat:Text.PlainText;color:root.ink;font.family:root.sans;font.pixelSize:root.fs(34);maximumLineCount:1;elide:Text.ElideRight}
        Text {
            width:parent.width
            text:root.copy?(root.copy.name || "Attached picture")+" · "+root.copy.capturedAt.slice(0,10)+" · "+(root.copy.identity.kind==="native-save"?"Game save":"Emulator state"):""
            textFormat:Text.PlainText;color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(23);wrapMode:Text.Wrap;maximumLineCount:2;elide:Text.ElideRight
        }
    }
    Image {
        id: picture
        objectName:"saveCopyPicture"
        x:root.px(64);y:heading.y+heading.height+root.px(24)
        width:parent.width-root.px(128);height:Math.max(0,caption.y-root.px(20)-y)
        source:root.visible?root.source:""
        sourceSize.width:2048;sourceSize.height:2048
        fillMode:Image.PreserveAspectFit;cache:false;asynchronous:true
    }
    Text {
        objectName:"saveCopyPictureUnavailable"
        anchors.centerIn:picture;visible:picture.status===Image.Error
        text:"The attached picture could not be displayed. Your save copy was kept."
        width:picture.width;wrapMode:Text.Wrap;color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(24)
    }
    Text {
        id:caption
        objectName:"saveCopyPictureCaption"
        x:root.px(64);width:parent.width-root.px(128)
        y:root.usableHeight-root.px(114)-height
        text:"Attached to this checkpoint in save history. This picture does not prove what the save contains or that it can be loaded."
        wrapMode:Text.Wrap;color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(22)
    }
}
