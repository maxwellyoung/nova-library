import QtQuick 2.15
import QtQuick.Window 2.15
import "../../theme" as Nova

Window {
    id: window
    visible: true
    width: 1280; height: 960
    color: queue.ground
    property int bottomInset: 0
    property bool refuseLaunch: false
    property int returnChecks: 0
    property int closes: 0
    QtObject {
        id: keys
        property var accept: [{name:function(){return "Gamepad (A)";}}]
        property var cancel: [{name:function(){return "Gamepad (B)";}}]
        property var details: [{name:function(){return "Gamepad (X)";}}]
        property var filters: [{name:function(){return "Gamepad (Y)";}}]
        function isCancel(event){return event.key===Qt.Key_Escape || event.key===Qt.Key_Back;}
        function isAccept(event){return event.key===Qt.Key_Return;}
        function isDetails(event){return event.key===Qt.Key_X;}
        function isFilters(event){return event.key===Qt.Key_Y;}
        function isUp(event){return event.key===Qt.Key_Up;}
        function isDown(event){return event.key===Qt.Key_Down;}
    }
    QtObject {
        id: testCloud
        property var downloads: []
        property bool queueRunning: false
        property bool busy: false
        property real progress: 0
        property string message: "Synthetic download; no network."
        property string queueMessage: "Paused until you start."
        property string called: ""
        property bool refuseRemoval: false
        function startDownloads(id){called="start:"+id;}
        function pauseDownloads(){called="pause";queueRunning=false;busy=false;}
        function removeQueuedDownload(id){called="remove:"+id;if(refuseRemoval){queueMessage="Could not save the queue. Nothing was removed.";return false;}downloads=downloads.filter(function(job){return job.id!==id;});return true;}
        function play(id){called="play:"+id;}
        function jobs(count,installed){
            var result=[];
            for(var i=0;i<count;i++)result.push({id:i+1,title:"Synthetic adventure "+(i+1)+" · A deliberately long game title",system:"Super Nintendo",platform:"snes",bytes:2048,cover:"",installed:!!installed,state:installed?"ready":"paused",message:"Retained bytes need attention. Nothing was replaced."});
            return result;
        }
        function refresh(){downloads=downloads.map(function(job){return JSON.parse(JSON.stringify(job));});}
    }
    FocusScope {
        anchors.fill:parent;focus:true
        Keys.onPressed: queue.handleKey(event)
        Nova.DownloadQueue {
            id: queue
            anchors.left:parent.left;anchors.right:parent.right;anchors.top:parent.top
            height:parent.height-window.bottomInset
            cloud:testCloud;keyMap:keys;textScale:fixtureLarge?1.12:1
            ground:fixtureLight?"#f3f3f1":"#0c0d0e"
            ink:fixtureLight?"#151617":"#e9eaea"
            slab:fixtureLight?"#e1e1de":"#1a1c1e"
            quiet:Qt.rgba(ink.r,ink.g,ink.b,0.62)
            fontFamily:Qt.application.font.family
            preparePlay:function(){window.returnChecks++;return !window.refuseLaunch;}
            onClosed:window.closes++
        }
    }
    Timer {
        interval:140;running:true;repeat:true
        property int step:0
        property bool capturing:false
        function require(value,why){if(!value)throw new Error(why);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var found=find(item.children[i],name);if(found)return found;}return null;}
        function label(item,text){if(item.text===text && item.visible)return item;for(var i=0;i<item.children.length;i++){var found=label(item.children[i],text);if(found)return found;}return null;}
        function click(text){var target=label(queue,text);require(target,"Pointer target absent: "+text);var point=target.mapToItem(null,target.width/2,target.height/2);driver.tap(Math.round(point.x),Math.round(point.y));}
        function key(code){require(driver.key(code),"Queue did not consume a key");driver.key(code,false);}
        function capture(name,next){capturing=true;queue.grabToImage(function(image){require(image.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function rowVisible(){var list=find(queue,"queueRows"),row=list.currentItem;require(row,"Selected row absent");var point=row.mapToItem(list,0,0);require(point.y>=-1 && point.y+row.height<=list.height+1,"Selected queue row is clipped");}
        function hintsFit(){var hints=find(queue,"queueHints");require(hints.x+hints.childrenRect.width<=queue.width-queue.px(64)+1,"Queue controls escape the right margin");require(hints.y>=0 && hints.y+hints.childrenRect.height<=queue.height-queue.px(30)+1,"Queue controls escape the bottom edge");var notice=find(queue,"queueNotice");require(notice.y+notice.height<=hints.y-queue.px(8),"Queue notice overlaps controls");var content=find(queue,"queueContent");require(content.y+content.height<=notice.y-queue.px(12),"Queue rows overlap feedback");}
        onTriggered:{try{
            if(capturing)return;
            if(step===0){
                testCloud.downloads=testCloud.jobs(40,false);queue.select(0);testCloud.queueRunning=true;
                queue.forceActiveFocus();step=1;return;
            }
            if(fixtureScenario==="layout"){
                if(step===1){for(var i=0;i<39;i++)key(Qt.Key_Down);step=2;return;}
                if(step===2){require(queue.current.id===40,"Last item unreachable");capture("last-row",3);return;}
                if(step===3){rowVisible();hintsFit();testCloud.downloads=[];step=4;return;}
                if(step===4){capture("empty",5);return;}
                if(step===5){hintsFit();key(Qt.Key_Return);require(testCloud.called==="","Empty queue started an operation");key(Qt.Key_Escape);require(window.closes===1,"Empty queue lost Back");step=99;}
            } else if(fixtureScenario==="continuity"){
                if(step===1){testCloud.downloads=testCloud.jobs(4,true);queue.select(2);window.refuseLaunch=true;key(Qt.Key_Return);require(window.returnChecks===1 && testCloud.called==="" && !!queue.launchNotice,"Launch refusal did not block play");capture("refused",2);return;}
                if(step===2){testCloud.refresh();step=3;return;}
                if(step===3){require(queue.current.id===3 && !!queue.launchNotice,"Queue refresh erased the same game's launch refusal");testCloud.downloads=testCloud.downloads.slice().reverse();step=4;return;}
                if(step===4){require(queue.current.id===3 && !!queue.launchNotice,"Queue reorder lost refusal or exact selection");capture("retained-refusal",5);return;}
                if(step===5){key(Qt.Key_Down);require(queue.current.id===2 && queue.launchNotice==="","Explicit selection retained another game's refusal");queue.select(1);window.refuseLaunch=false;key(Qt.Key_Return);require(testCloud.called==="play:3","Retry did not play exact game");window.refuseLaunch=true;testCloud.called="";key(Qt.Key_Return);testCloud.downloads=testCloud.downloads.filter(function(job){return job.id!==3;});step=6;return;}
                if(step===6){require(queue.current.id!==3 && queue.selectedId===queue.current.id && queue.launchNotice==="","Removed game kept stale refusal or identity");step=99;}
            } else if(fixtureScenario==="pointer"){
                if(step===1){testCloud.downloads=testCloud.jobs(4,true);queue.select(1);window.refuseLaunch=true;step=2;return;}
                if(step===2){click("Play");require(window.returnChecks===1 && testCloud.called==="" && !!queue.launchNotice,"Pointer bypassed launch guard");testCloud.refresh();step=3;return;}
                if(step===3){require(queue.current.id===2 && !!queue.launchNotice,"Pointer refusal disappeared on refresh");window.refuseLaunch=false;step=4;return;}
                if(step===4){click("Play");require(testCloud.called==="play:2","Pointer retry lost exact game");click("Back");require(window.closes===1,"Pointer Back did not close queue");capture("pointer",99);return;}
            } else {
                if(step===1){queue.select(1);testCloud.downloads=testCloud.downloads.map(function(job){if(job.id===2){job.state="blocked";job.message="Synthetic checksum failure. Files were kept.";}return job;});step=2;return;}
                if(step===2){key(Qt.Key_Return);require(testCloud.called==="start:2","Blocked game cannot retry");testCloud.busy=true;testCloud.called="";key(Qt.Key_Return);require(testCloud.called==="","Busy queue dispatched primary action");key(Qt.Key_X);require(testCloud.called==="pause" && !testCloud.busy,"Pause did not use queue boundary");testCloud.called="";testCloud.downloads=testCloud.downloads.map(function(job){if(job.id===2)job.state="active";return job;});key(Qt.Key_Y);require(testCloud.called==="","Active download removed");testCloud.downloads=testCloud.downloads.map(function(job){job.state="paused";return job;});key(Qt.Key_Y);require(testCloud.called==="remove:2","Paused entry removal failed");step=3;return;}
                if(step===3){require(queue.current && queue.current.id!==2,"Removed job remains selected");testCloud.downloads=testCloud.downloads.map(function(job){job.state="blocked";return job;});testCloud.refuseRemoval=true;key(Qt.Key_Y);step=4;return;}
                if(step===4){require(queue.launchNotice===testCloud.queueMessage,"Refused queue removal hides its current error");key(Qt.Key_Back);require(window.closes===1,"Android Back lost queue parent");capture("actions",99);return;}
            }
            if(step===99){stop();console.log("DOWNLOAD_QUEUE_PASS "+fixtureScenario);Qt.exit(0);}
        }catch(error){stop();console.error("DOWNLOAD_QUEUE_FAIL "+error);queue.grabToImage(function(image){image.saveToFile(fixtureOutput+"/failure.png");Qt.exit(1);});}}
    }
}
