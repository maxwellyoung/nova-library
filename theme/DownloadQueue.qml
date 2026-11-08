import QtQuick 2.15
import "library.js" as Lib
Item {
    id: panel
    objectName: "downloadQueue"
    property var cloud: null
    property var keyMap: null
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property color slab: "#1a1c1e"
    property color quiet: "#9a9b9b"
    property real textScale: 1
    property string fontFamily: ""
    property real scale: Math.max(0.5,Math.min(width/1280,height/800))
    property int selected: 0
    property int selectedId: 0
    readonly property var jobs: cloud && cloud.downloads ? cloud.downloads : []
    readonly property var current: selected>=0 && selected<jobs.length ? jobs[selected] : null
    readonly property bool running: !!(cloud && cloud.queueRunning)
    readonly property bool busy: !!(cloud && cloud.busy)
    readonly property string primaryLabel: !current ? "Start queue" : current.installed ? "Play" : current.state==="blocked" ? "Retry" : "Start here"
    signal closed()
    function px(n){return Math.round(n*scale);}
    function fs(n){return Math.round(n*scale*textScale);}
    function key(value,fallback){return Lib.keyLabel(value,fallback);}
    function stateLabel(job) {
        return job.installed ? "Ready offline" : job.state==="active" ? "Downloading" : job.state==="paused" ? "Paused" : job.state==="blocked" ? "Needs attention" : "Queued";
    }
    function select(index){selected=Math.max(0,Math.min(jobs.length-1,index));selectedId=current?current.id:0;}
    function primary(){if(!cloud || busy || !current)return;if(current.installed)cloud.play(current.id);else cloud.startDownloads(current.id);}
    function pause(){if(cloud && running)cloud.pauseDownloads();}
    function unqueue(){if(cloud && current && current.state!=="active")cloud.removeQueuedDownload(current.id);}
    function handleKey(event){
        if(!keyMap)return;event.accepted=true;
        if(keyMap.isCancel(event))closed();
        else if(keyMap.isUp(event))select(selected-1);
        else if(keyMap.isDown(event))select(selected+1);
        else if(keyMap.isAccept(event))primary();
        else if(keyMap.isDetails(event))pause();
        else if(keyMap.isFilters(event))unqueue();
    }
    onJobsChanged:{var found=-1;jobs.forEach(function(job,i){if(job.id===selectedId)found=i;});select(found>=0?found:selected);}
    Rectangle {anchors.fill:parent;color:panel.ground}
    Text {textFormat:Text.PlainText;x:px(64);y:px(64);width:parent.width-px(128);text:"Downloads";color:ink;font.family:fontFamily;font.pixelSize:fs(40);font.weight:Font.DemiBold}
    Text {textFormat:Text.PlainText;x:px(64);y:px(122);width:parent.width-px(128);text:jobs.length ? (running ? "Downloading in order" : jobs.some(function(job){return !job.installed;}) ? "Paused until you start" : "All downloads ready offline")+" · "+jobs.length+" in Downloads" : "Your next games, ready to bring along.";color:quiet;font.family:fontFamily;font.pixelSize:fs(22);elide:Text.ElideRight}
    Item {
        objectName:"queueContent"
        x:px(64);y:px(176);width:parent.width-px(128);height:Math.max(0,parent.height-px(382));visible:jobs.length>0
        ArtView {
            entry:current?{title:current.title,art:current.cover||"",systemId:current.platform||"",systemName:current.system||""}:null
            width:parent.width*0.32;height:Math.min(parent.height,width*1.5)
            fontFamily:panel.fontFamily;textColor:panel.ink;quietColor:panel.quiet;slabColor:panel.slab;veilColor:panel.ground
        }
        ListView {
            id:list;x:parent.width*0.38;width:parent.width-x;height:parent.height;clip:true;spacing:px(8)
            model:panel.jobs;currentIndex:panel.selected;highlightMoveDuration:0;preferredHighlightBegin:0;preferredHighlightEnd:height;highlightRangeMode:ListView.ApplyRange
            delegate:Item {
                width:list.width;height:Math.max(px(98),fs(88))
                Rectangle {x:0;y:px(12);width:px(3);height:parent.height-px(24);color:ink;visible:index===panel.selected}
                Column {
                    x:px(18);y:px(12);width:parent.width-px(30);spacing:px(6)
                    Text {textFormat:Text.PlainText;width:parent.width;text:modelData.title;elide:Text.ElideRight;color:ink;font.family:fontFamily;font.pixelSize:fs(25)}
                    Text {textFormat:Text.PlainText;width:parent.width;text:panel.stateLabel(modelData)+" · "+(modelData.system||"Platform unavailable")+(modelData.bytes>0?" · "+Lib.bytesText(modelData.bytes):"");elide:Text.ElideRight;color:quiet;font.family:fontFamily;font.pixelSize:fs(18)}
                }
                MouseArea {anchors.fill:parent;onClicked:panel.select(index);onDoubleClicked:panel.primary()}
            }
        }
    }
    Text {textFormat:Text.PlainText;x:px(64);y:px(202);width:parent.width-px(128);visible:!jobs.length;text:"Choose a game in Cloud library to download. Its place here survives a restart. Removing an entry keeps its ROM and save files.";wrapMode:Text.WordWrap;color:quiet;font.family:fontFamily;font.pixelSize:fs(27)}
    Rectangle {
        objectName:"queueProgress"
        x:px(64);y:parent.height-px(190);width:parent.width-px(128);height:px(3);visible:running && busy;color:Qt.rgba(ink.r,ink.g,ink.b,0.12)
        Rectangle {width:parent.width*(cloud?Math.max(0,Math.min(1,cloud.progress)):0);height:parent.height;color:ink}
    }
    Text {
        objectName:"queueNotice";textFormat:Text.PlainText
        x:px(64);y:parent.height-px(170);width:parent.width-px(128);height:px(84)
        text:running && busy ? cloud.message : current && current.state==="blocked" ? current.message : cloud ? cloud.queueMessage : "Downloads are unavailable in this build."
        wrapMode:Text.WordWrap;maximumLineCount:3;elide:Text.ElideRight;color:quiet;font.family:fontFamily;font.pixelSize:fs(20)
    }
    Row {
        objectName:"queueHints";x:px(64);y:parent.height-px(68);spacing:px(28)
        Repeater {
            model:[{key:key(keyMap?keyMap.accept:null,"A"),label:primaryLabel,action:"primary",enabled:!!current && !busy},
                {key:key(keyMap?keyMap.details:null,"X"),label:"Pause",action:"pause",enabled:running},
                {key:key(keyMap?keyMap.filters:null,"Y"),label:"Remove entry",action:"remove",enabled:!!current && current.state!=="active"},
                {key:key(keyMap?keyMap.cancel:null,"B"),label:"Back",action:"back",enabled:true}]
            delegate:Item {
                visible:modelData.enabled;width:hint.implicitWidth;height:px(32)
                Row {id:hint;spacing:px(10)
                    KeyCap {label:modelData.key;ink:panel.ink;ground:panel.ground;primary:modelData.action==="primary";fontFamily:panel.fontFamily;textSize:panel.fs(21)}
                    Text {textFormat:Text.PlainText;text:modelData.label;color:modelData.action==="primary"?panel.ink:panel.quiet;font.family:panel.fontFamily;font.pixelSize:panel.fs(24);anchors.verticalCenter:parent.verticalCenter}
                }
                MouseArea {anchors.fill:parent;anchors.margins:-px(10);onClicked:{if(modelData.action==="primary")panel.primary();else if(modelData.action==="pause")panel.pause();else if(modelData.action==="remove")panel.unqueue();else panel.closed();}}
            }
        }
    }
}
