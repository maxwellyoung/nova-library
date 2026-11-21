    QtObject {
        id:guardCloud
        property int requests:0
        property int catalogueVersion:1
        property int queueVersion:1
        property bool queueRunning:false
        property var downloads:[{id:42,title:"Guarded Cloud fixture",system:"SNES",installed:true,state:"complete",bytes:1}]
        property string queueMessage:"Synthetic queue is paused."
        property bool configured:true
        property bool busy:false
        property double progress:0
        property string message:"Synthetic launch guard; no network."
        property var games:[{id:42,editionId:"demo:orbit",title:"Guarded Cloud fixture",platform:"snes",system:"SNES",installed:true,supported:true,bytes:1}]
        signal launchAccepted(string edition)
        function play(id){requests++;}
        function refresh(){}
        function enqueueDownload(id){return true;}
        function startDownloads(id){}
        function installPlan(id){return {};}
    }
    QtObject {
        id:guardPc
        property int capabilityVersion:1
        property int requests:0
        property var runtimes:[{id:"droiddeck",name:"DroidDeck",version:"0.7.0",available:true,supported:true}]
        function refresh(){}
        function openGame(id,runtime,version){requests++;return {accepted:true};}
    }
    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property string bytesBefore:""
        property string edition:"demo:orbit"
        property int localLaunches:0
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function launchRefusal(ui){
            var timer=this,e={id:edition,title:"Guarded fixture",systemId:"snes",route:"Synthetic",launchable:true,game:{missing:false,launch:function(){timer.localLaunches++;}}};
            window.romCloud=guardCloud;window.pcRuntime=guardPc;
            driver.lockPreferences(true);var before=driver.preferenceBytes();
            ui.playEdition(e);require(localLaunches===0 && window.romStages===0 && ui.notice.indexOf("Nothing was launched")>=0,"Refused focus still staged/launched local game");
            e.cloudId=42;ui.playEdition(e);require(guardCloud.requests===0,"Refused focus still launched integrated Cloud");
            ui.openCloud(e);var panel=find(ui,"cloudLibrary");require(panel && panel.current.id===42,"Cloud fixture missing");panel.primary();
            require(guardCloud.requests===0 && panel.removalNotice.indexOf("Nothing was launched")>=0,"Cloud panel bypassed return commit");
            panel.queueOpen=true;var queue=find(ui,"downloadQueue");require(queue && queue.current.id===42,"Downloaded queue fixture missing");queue.primary();
            require(guardCloud.requests===0 && queue.launchNotice.indexOf("Nothing was launched")>=0,"Downloads bypassed return commit");
            require(queue.stateLabel(queue.current)==="Downloaded","Download receipt became an offline-play claim");
            var pc={id:"steam:123",systemId:"pc"};ui.requestPcGame(pc,"droiddeck","0.7.0");
            require(guardPc.requests===0 && ui.pcNotice.indexOf("Nothing was requested")>=0,"Refused focus still dispatched PC runtime");
            require(driver.preferenceBytes()===before,"Refused focus changed file bytes");
            driver.lockPreferences(false);delete e.cloudId;ui.overlay="";ui.playEdition(e);
            require(localLaunches===1 && window.romStages===1,"Local retry did not dispatch exactly once");
            var committed=api.memory.checkedRead("focus");require(committed.ok && committed.value.view===ui.view && committed.value.library===edition,"Return view/edition were not committed together");
            e.cloudId=42;ui.playEdition(e);require(guardCloud.requests===1,"Integrated Cloud retry failed");
            ui.openCloud(e);panel.primary();require(guardCloud.requests===2,"Cloud panel retry failed");
            panel.queueOpen=true;queue.primary();require(guardCloud.requests===3,"Downloads retry failed");
            ui.requestPcGame(pc,"droiddeck","0.7.0");require(guardPc.requests===1,"PC retry failed");
            var cloudId="nova:cloud_"+Array(65).join("a")+":42_"+Array(65).join("b"),history=JSON.stringify(ui.cloudOpened);
            driver.lockPreferences(true);before=driver.preferenceBytes();guardCloud.launchAccepted(cloudId);
            require(JSON.stringify(ui.cloudOpened)===history && driver.preferenceBytes()===before && ui.notice.indexOf("Couldn't add")>=0,"Refused cloud history produced phantom recents");
            driver.lockPreferences(false);guardCloud.launchAccepted(cloudId);
            require(api.memory.checkedRead("cloudOpened").value.opened[cloudId]===ui.cloudOpened[cloudId],"Cloud history retry not committed");
            driver.externalPreferences();before=driver.preferenceBytes();delete e.cloudId;ui.playEdition(e);
            e.cloudId=42;ui.playEdition(e);ui.requestPcGame(pc,"droiddeck","0.7.0");
            require(localLaunches===1 && window.romStages===1 && guardCloud.requests===3 && guardPc.requests===1 && driver.preferenceBytes()===before,"Stale external file still dispatched or was overwritten");
            ui.openCloud(e);panel.primary();panel.queueOpen=true;queue.primary();
            require(guardCloud.requests===3 && driver.preferenceBytes()===before,"Cloud panel/Downloads bypassed stale-file refusal");
        }
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Key not accepted: "+k);driver.key(k,false);}
        function snap(name,next){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function select(ui){ui.overlay="";ui.switchView("library");ui.zone="content";ui.setLibIndex(ui.libraryEntries.map(function(e){return e.id;}).indexOf(edition));require(ui.current.id===edition,"Fixture missing");}
        function session(ui){ui.openDetails();var n=ui.detailActions().map(function(a){return a.a;}).indexOf("session");require(n>=0,"Session action missing");ui.runDetailAction(n);ui.panelIndex=2;}
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item;
            if(step===0){
                select(ui);
                if(fixtureScenario==="launch-refusal"){launchRefusal(ui);snap("launch-refusals",20);return;}
                if(fixtureScenario==="corrupt" || fixtureScenario==="bad-pins"){
                    require(!ui.pinsReadable,"Unreadable favourites became writable");bytesBefore=driver.preferenceBytes();key(Qt.Key_Y);
                    require(driver.preferenceBytes()===bytesBefore && window.pinActions===0 && ui.notice.indexOf("unreadable")>=0,"Unreadable favourites changed");
                    if(fixtureScenario==="corrupt"){
                        require(ui.sessions===null,"Unreadable session file became empty labels");
                        require(!ui.cloudHistoryReadable,"Unreadable Cloud history became writable");session(ui);key(Qt.Key_Return);
                        require(ui.overlay==="session" && driver.preferenceBytes()===bytesBefore,"Unreadable sessions overwritten");
                    }
                    snap("unreadable",20);return;
                }
                if(fixtureScenario==="reopen"){
                    require(ui.pins.indexOf(edition)>=0 && ui.pins.indexOf("demo:garden")>=0,"Restart lost favourites");
                    require(ui.sessions.labels[edition]==="twenty" && ui.sessions.labels["demo:garden"]==="evening","Restart lost session labels");
                    require(ui.appearance.surface==="light","Restart lost appearance");snap("reopened",20);return;
                }
                require(ui.pins.indexOf(edition)<0,"Fixture already favourited");
                bytesBefore=driver.preferenceBytes();driver.lockPreferences(true);key(Qt.Key_Y);
                require(ui.pins.indexOf(edition)<0 && window.pinActions===0 && driver.preferenceBytes()===bytesBefore,"Refused favourite changed UI, outbox or bytes");
                require(ui.notice.indexOf("could not be saved")>=0,"Favourite refusal hidden");snap("favourite-refusal",1);return;
            }
            if(step===1){
                driver.lockPreferences(false);key(Qt.Key_Y);
                require(ui.pins.indexOf(edition)>=0 && window.pinActions===1 && api.memory.checkedRead("pins").value.indexOf(edition)>=0,"Favourite retry did not commit");
                bytesBefore=driver.preferenceBytes();driver.lockPreferences(true);key(Qt.Key_Y);
                require(ui.pins.indexOf(edition)>=0 && window.pinActions===1 && driver.preferenceBytes()===bytesBefore,"Refused unfavourite changed state");
                driver.lockPreferences(false);session(ui);bytesBefore=driver.preferenceBytes();driver.lockPreferences(true);key(Qt.Key_Return);
                require(ui.overlay==="session" && !ui.sessions.labels[edition] && driver.preferenceBytes()===bytesBefore,"Refused session label changed UI or bytes");
                require(ui.notice.indexOf("could not be stored")>=0,"Session refusal hidden");snap("session-refusal",2);return;
            }
            if(step===2){
                driver.lockPreferences(false);key(Qt.Key_Return);
                require(ui.sessions.labels[edition]==="twenty" && api.memory.checkedRead("sessionWindows").value.labels[edition]==="twenty","Session retry failed");
                require(ui.sessions.labels["demo:garden"]==="evening","Other edition label changed");
                ui.overlay="";ui.openPanel("appearance",0);var old=ui.appearance.surface;bytesBefore=driver.preferenceBytes();driver.lockPreferences(true);key(Qt.Key_Return);
                require(ui.appearance.surface===old && driver.preferenceBytes()===bytesBefore && ui.notice.indexOf("could not be saved")>=0,"Refused appearance changed UI or bytes");
                snap("appearance-refusal",3);return;
            }
            if(step===3){
                driver.lockPreferences(false);key(Qt.Key_Return);require(ui.appearance.surface===(fixtureLight?"dark":"light"),"Appearance retry failed");
                key(Qt.Key_Escape);require(ui.overlay==="","Appearance Back failed");
                require(api.memory.checkedRead("unrelated").value==="keep","Unrelated preference changed");
                require(driver.retainCommit(),"Could not retain restart fixture");
                session(ui);ui.panelIndex=0;bytesBefore=driver.preferenceBytes();driver.lockPreferences(true);key(Qt.Key_Return);
                require(ui.sessions.labels[edition]==="twenty" && driver.preferenceBytes()===bytesBefore,"Refused clear lost label");
                driver.lockPreferences(false);key(Qt.Key_Return);require(!ui.sessions.labels[edition],"Session clear failed");
                session(ui);ui.panelIndex=2;key(Qt.Key_Return);require(ui.sessions.labels[edition]==="twenty","Restore session label failed");
                select(ui);driver.externalPreferences();bytesBefore=driver.preferenceBytes();key(Qt.Key_Y);
                require(ui.pins.indexOf(edition)>=0 && window.pinActions===1 && driver.preferenceBytes()===bytesBefore,"External preferences overwritten");snap("external-change",20);return;
            }
            if(step===20){stop();console.log("PREFERENCES_THEME_PASS "+fixtureScenario);Qt.exit(0);}
        }catch(error){stop();console.error("PREFERENCES_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
