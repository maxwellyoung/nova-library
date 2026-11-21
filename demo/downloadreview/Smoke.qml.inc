    QtObject {
        id:testCloud
        property int reviewVersion:1
        property int queueVersion:0
        property bool configured:true
        property bool busy:false
        readonly property bool inspectingDownload:busy && !detailsKnown
        property double progress:0
        property string message:"Synthetic file list; no network."
        property string called:""
        property int revision:1
        property bool detailsKnown:true
        property bool spaceKnown:true
        property bool fits:true
        property bool blocked:false
        property bool installed:false
        property bool supported:true
        property var downloads:[]
        property bool queueRunning:false
        property string queueMessage:"Paused"
        property bool acceptsQueue:true
        property var boundaryPlan: ({})
        property var games:[{id:1,title:"Synthetic two-disc adventure",system:"PlayStation",platform:"ps",bytes:3072,installed:false,supported:true,cover:""}]
        property var files:[{name:"disc-one.chd",bytes:1024,role:"Game file"},{name:"disc-two.chd",bytes:1024,role:"Game file"},{name:"adventure.m3u",bytes:1024,role:"Disc playlist"}]
        signal changed()
        function downloadReview(id){
            var currentFits=boundaryPlan.fits===undefined?fits:boundaryPlan.fits;
            return id!==1?{}:{id:id,title:games[0].title,editionId:"synthetic:"+revision,detailsKnown:detailsKnown,supported:supported,installed:installed,files:detailsKnown?files:[],totalBytes:files.reduce(function(n,f){return n+f.bytes;},0),remainingBytes:files.reduce(function(n,f){return n+f.bytes;},0)-72,retainedBytes:72,freeBytes:4000000,headroomBytes:1024,spaceKnown:spaceKnown,fits:currentFits,blocked:blocked,reason:blocked?"Retained files need review.":!currentFits?"Not enough free space.":"Free space could not be measured.",scope:"The playlist and every listed file download together. Individual-disc downloads are not supported here."};
        }
        function installPlan(id){return downloadReview(id);}
        function inspectDownload(id){called="inspect:"+id;busy=true;message="Checking metadata";changed();}
        function install(id){called="install:"+id;}
        function enqueueDownload(id){
            called="enqueue:"+id;if(!acceptsQueue)return false;
            if(!downloads.length)downloads=[{id:id,title:games[0].title,system:"PlayStation",platform:"ps",bytes:files.reduce(function(n,f){return n+f.bytes;},0),state:"queued",installed:false,message:"Waiting in Downloads."}];
            return true;
        }
        function startDownloads(id){called="start:"+id;queueRunning=true;busy=true;downloads=downloads.map(function(job){job.state="active";return job;});}
        function refresh(){called="refresh";}
        function requestCover(id){}
        function cancel(){called="cancel";busy=false;changed();}
        function play(id){called="play:"+id;}
    }
    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property bool capturedChanged:false
        property var artChecks:[]
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Key not accepted");driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var f=find(item.children[i],name);if(f)return f;}return null;}
        function capture(ui,name,next){capturing=true;ui.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        onTriggered:{try{
            if(capturing)return;
            var ui=themeLoader.item,cloud=find(ui,"cloudLibrary"),review=find(ui,"downloadReview");
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                ui.openCloud();testCloud.called="";key(Qt.Key_Return);
                require(cloud.reviewOpen && testCloud.called==="","Review started a transfer");
                require(review.preview.files.length===3 && review.preview.scope.indexOf("Individual-disc")>=0,"Set dependencies missing");step=1;return;
            }
            if(step===1){capture(ui,"review",2);return;}
            if(step===2){
                key(Qt.Key_Down);key(Qt.Key_Down);require(review.selected===2,"File selection failed");
                var list=find(review,"reviewFiles"),row=find(review,"reviewFile_2");require(row,"File row absent");
                var p=row.mapToItem(list,0,0);require(p.y>=-1 && p.y+row.height<=list.height+1,"Selected file clipped");
                testCloud.revision++;testCloud.changed();step=3;return;
            }
            if(step===3){
                require(review.changed && !review.canConfirm,"Changed descriptor still confirmable");
                if(!capturedChanged && review.changed){capturedChanged=true;capture(ui,"changed",30);return;}
                key(Qt.Key_Return);require(!review.changed && testCloud.called==="","Review again started transfer");
                testCloud.fits=false;testCloud.changed();step=4;return;
            }
            if(step===30){step=3;return;}
            if(step===4){
                key(Qt.Key_Return);require(cloud.reviewOpen && testCloud.called==="" && !review.canConfirm,"Insufficient space installed");
                testCloud.fits=true;testCloud.spaceKnown=false;testCloud.changed();step=5;return;
            }
            if(step===5){
                key(Qt.Key_Return);require(testCloud.called==="" && !review.canConfirm,"Unknown space installed");
                testCloud.spaceKnown=true;testCloud.blocked=true;testCloud.changed();step=6;return;
            }
            if(step===6){
                key(Qt.Key_Return);require(testCloud.called==="" && !review.canConfirm,"Blocked partial installed");capture(ui,"blocked",7);return;
            }
            if(step===7){
                testCloud.blocked=false;testCloud.installed=true;testCloud.changed();step=8;return;
            }
            if(step===8){
                key(Qt.Key_Return);require(testCloud.called==="" && !review.canConfirm,"Installed during review installed again");
                testCloud.installed=false;testCloud.changed();step=9;return;
            }
            if(step===9){
                key(Qt.Key_Return);require(testCloud.called==="install:1" && !cloud.reviewOpen,"Confirmation missed install boundary");
                testCloud.called="";testCloud.detailsKnown=false;key(Qt.Key_Return);
                require(cloud.reviewOpen && testCloud.called==="inspect:1" && testCloud.busy,"Summary did not inspect");step=10;return;
            }
            if(step===10){capture(ui,"inspecting",11);return;}
            if(step===11){
                key(Qt.Key_Back);require(!cloud.reviewOpen && ui.overlay==="cloud","Android Back lost Cloud parent");
                testCloud.detailsKnown=true;testCloud.busy=false;testCloud.changed();testCloud.called="";
                require(!cloud.reviewOpen,"Late metadata reopened review");key(Qt.Key_Return);require(cloud.reviewOpen && testCloud.called==="","Late metadata triggered install");
                key(Qt.Key_Escape);require(!cloud.reviewOpen && ui.overlay==="cloud","Back did not retain Cloud selection");
                testCloud.detailsKnown=false;key(Qt.Key_Return);testCloud.busy=false;testCloud.message="Could not check this game's files.";testCloud.changed();step=12;return;
            }
            if(step===12){
                require(!review.preview.detailsKnown && !review.canConfirm,"Metadata failure became ready");
                key(Qt.Key_X);require(testCloud.called==="inspect:1" && testCloud.busy,"Metadata retry missing");
                testCloud.detailsKnown=true;testCloud.busy=false;testCloud.changed();step=13;return;
            }
            if(step===13){
                require(review.preview.detailsKnown && review.canConfirm,"Metadata success not reviewable");
                testCloud.files=Array.apply(null,Array(16)).map(function(v,i){return {name:"disc-"+i+"-"+Array(9).join("very-long-name-")+(i===15?".m3u":".chd"),bytes:1024,role:i===15?"Disc playlist":"Game file"};});
                testCloud.revision++;testCloud.changed();key(Qt.Key_Return);step=14;return;
            }
            if(step===14){
                for(var i=0;i<15;i++)key(Qt.Key_Down);require(review.selected===15,"Long file list inaccessible");step=15;return;
            }
            if(step===15){
                var l=find(review,"reviewFiles"),r=find(review,"reviewFile_15");require(r,"Long final row absent");var point=r.mapToItem(l,0,0);
                require(point.y>=-1 && point.y+r.height<=l.height+1,"Long final file clipped");
                var notice=find(review,"reviewNotice"),hints=find(review,"reviewHints");require(l.y+l.height<=notice.y,"Files overlap notice");require(notice.y+notice.height<=hints.y,"Notice overlaps hints");
                capture(ui,"long-files",16);return;
            }
            if(step===16){
                // Mutate nested state without a QObject notification, like a volume
                // changing after its last measured plan was rendered.
                testCloud.called="";testCloud.boundaryPlan.fits=false;key(Qt.Key_Return);
                require(testCloud.called==="" && !review.canConfirm && review.notice().indexOf("Not enough free space")>=0,"Fresh capacity refusal left stale feedback");
                require(review.primaryLabel==="Check again","Capacity refusal has no recheck action");
                testCloud.boundaryPlan.fits=true;key(Qt.Key_Return);
                require(testCloud.called==="" && review.canConfirm && review.primaryLabel==="Download","Recheck started an unrequested transfer or failed to recover");
                review.handleKey({key:Qt.Key_Return,isAutoRepeat:true,accepted:false});
                require(testCloud.called==="","Held recheck key started a transfer");
                delete testCloud.boundaryPlan.fits;
                key(Qt.Key_Escape);testCloud.queueVersion=1;testCloud.called="";key(Qt.Key_Return);
                testCloud.acceptsQueue=false;testCloud.queueMessage="Synthetic queue write refused";key(Qt.Key_Return);
                require(cloud.reviewOpen && review.actionError==="Synthetic queue write refused","Queue refusal lost feedback");
                testCloud.acceptsQueue=true;key(Qt.Key_Return);
                require(testCloud.called==="start:1" && !cloud.reviewOpen && cloud.queueOpen,"Queue confirmation failed");
                testCloud.message="Connection closed. Retrying retained bytes once; files still need checks.";step=17;return;
            }
            if(step===17){
                var notice=find(ui,"queueNotice"),hints=find(ui,"queueHints");
                require(notice.text===testCloud.message,"Active retry explanation not shown");
                require(notice.paintedHeight<=notice.height+1 && notice.y+notice.height<=hints.y,"Retry feedback clips or overlaps controls");
                var queue=find(ui,"downloadQueue"),fallback=find(queue,"artFallback"),body=find(fallback,"artFallbackBody");
                require(body.y>=0 && body.y+body.height<=fallback.height+1,"Missing-cover text crosses its art boundary");
                capture(ui,"recovering",18);return;
            }
            if(step===18){
                testCloud.busy=false;testCloud.queueRunning=false;key(Qt.Key_Escape);
                testCloud.reviewVersion=0;testCloud.queueVersion=0;testCloud.called="";key(Qt.Key_Return);
                require(testCloud.called==="install:1" && !cloud.reviewOpen,"Legacy bridge changed");
                var artComponent=Qt.createComponent("../theme/ArtView.qml");require(artComponent.status===Component.Ready,"Fallback component did not load");
                var sizes=[[333,377],[320,100],[80,60],[180,60],[120,120],[200,300],[100,20],[40,20]];
                sizes.forEach(function(size){var item=artComponent.createObject(ui,{width:size[0],height:size[1],opacity:0,entry:{title:Array(9).join("A long missing cover title "),art:"",systemId:"ps",systemName:"PlayStation"}});require(item,"Fallback fixture absent");artChecks.push(item);});
                step=19;return;
            }
            if(step===19){
                artChecks.forEach(function(item){var f=find(item,"artFallback"),body=find(f,"artFallbackBody"),header=find(f,"artFallbackHeader");require(body.y>=-1 && body.y+body.height<=f.height+1,"Compact fallback body escapes at "+item.width+"x"+item.height);if(header.visible)require(header.y+header.height<=body.y+1,"Fallback header overlaps its title");item.destroy();});
                stop();console.log("DOWNLOAD_REVIEW_PASS");Qt.exit(0);
            }
        }catch(error){stop();console.error("DOWNLOAD_REVIEW_FAIL "+error);Qt.exit(1);}}
    }
