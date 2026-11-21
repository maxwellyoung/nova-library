    Timer {
        interval:200;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property var original:null
        property int offlineRow:-1
        function require(value,message){if(!value)throw new Error(message);}
        function key(k){require(driver.key(k),"Key was not accepted");driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var found=find(item.children[i],name);if(found)return found;}return null;}
        function entry(kind){
            var e={};Object.keys(original).forEach(function(k){e[k]=original[k];});
            var game={};Object.keys(e.game).forEach(function(k){game[k]=e.game[k];});e.game=game;
            e.launchable=true;e.missing=false;e.game.missing=false;e.compatibilityRecipeId="fixture.offline.v1";
            var setup={id:"fixture.offline.v1",device:"Synthetic handheld",runtime:"Fixture runtime",version:"1.0",core:"Fixture core",driver:"Fixture driver",display:"Fit",input:"Fixture pad",settings:"Fixture settings"};
            var check={stage:"offline-launch",result:kind==="failed"?"fail":"pass",method:"owner",observedAt:"2026-11-09T10:00:00Z",source:"Synthetic fixture",note:"Cold launch with the test network disconnected",network:"disconnected",coldStart:true};
            e.compatibilityReceipts=kind==="unknown"?"":JSON.stringify([{schemaVersion:1,editionId:e.id,recipe:setup,checks:[check]}]);
            if(kind==="missing"){e.missing=true;e.game.missing=true;}
            if(kind==="historical")e.compatibilityRecipeId="changed.recipe";
            return e;
        }
        function show(ui,kind){
            var e=entry(kind);ui.overlay="";ui.rawEntries=ui.rawEntries.map(function(old){return old.id===e.id?e:old;});
            ui.rebuildPresentations();ui.switchView("library");ui.rebuildLibrary(e.id);
            ui.setLibIndex(ui.libraryEntries.map(function(x){return x.id;}).indexOf(e.id));ui.zone="content";ui.openDetails();return e;
        }
        function capture(ui,name,next){capturing=true;ui.grabToImage(function(image){require(image.saveToFile(fixtureOutput+"/"+name+".png"),"Screenshot failed");capturing=false;step=next;});}
        onTriggered:{try{
            if(capturing)return;
            var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                original=ui.rawEntries.filter(function(e){return e.id==="demo:orbit";})[0];require(original,"Fixture edition missing");
                var e=show(ui,"passed");
                require(ui.overviewLines(e,0).some(function(l){return l.t.indexOf("Offline launch tested")>=0;}),"Details lost offline observation");
                require(ui.wideSummaryLines(e,0).some(function(l){return l.t.indexOf("Offline launch tested")>=0;}),"Wide summary hid offline observation");
                require(ui.detailLines(e,0).some(function(l){return l.t.indexOf("does not verify saves")>=0;}),"Info lost scope limitation");
                step=1;return;
            }
            if(step===1){capture(ui,"details",2);return;}
            if(step===2){
                var action=ui.detailActions().map(function(a){return a.a;}).indexOf("checks");require(action>=0,"Checks action missing");ui.runDetailAction(action);
                var rows=ui.panelRows(0);offlineRow=rows.map(function(r){return r.label;}).indexOf("Offline launch");require(offlineRow>=0,"Offline stage missing");
                require(rows[offlineRow].value==="Passed in check","Wrong offline result");
                while(ui.panelIndex<offlineRow)key(Qt.Key_Down);require(ui.panelIndex===offlineRow,"Cannot reach final check by D-pad");step=3;return;
            }
            if(step===3){
                var list=find(ui,"panelList"), selected=list && list.currentItem;
                require(selected && list.currentIndex===offlineRow,"Selected stage delegate missing");
                var top=selected.y-list.contentY;
                require(top>=-1 && top+selected.height<=list.height+1,"Selected stage is outside the visible list");
                var footer=find(ui,"panelExplanation");require(footer && footer.y+footer.height<=ui.usableHeight,"Checks footer overflows");capture(ui,"checks",4);return;
            }
            if(step===4){key(Qt.Key_Return);require(ui.overlay==="facts","A did not open complete check");step=5;return;}
            if(step===5){
                capture(ui,"full-check",6);return;
            }
            if(step===6){
                key(Qt.Key_Escape);require(ui.overlay==="checks" && ui.panelIndex===offlineRow,"Back lost stage focus");
                key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id===original.id,"Back lost edition");
                var e=show(ui,"missing");require(!ui.overviewLines(e,0).some(function(l){return l.t.indexOf("Offline launch tested")>=0;}),"Missing file retained positive summary");
                require(ui.detailLines(e,0).some(function(l){return l.t.indexOf("local file not confirmed")>=0;}),"Missing file explanation lost");step=7;return;
            }
            if(step===7){capture(ui,"missing",8);return;}
            if(step===8){
                var e=show(ui,"historical");require(!ui.overviewLines(e,0).some(function(l){return l.t.indexOf("Offline launch tested")>=0;}),"Changed recipe retained positive summary");
                e=show(ui,"unknown");require(!ui.overviewLines(e,0).some(function(l){return l.t.indexOf("Offline")>=0;}),"Unknown evidence cluttered compact Details");
                e=show(ui,"failed");require(ui.overviewLines(e,0).some(function(l){return l.t.indexOf("Offline launch failed")>=0;}),"Failed check hidden");step=9;return;
            }
            if(step===9){capture(ui,"failed",10);return;}
            if(step===10){
                ui.openPanel("checks",0);var rows=ui.panelRows(0);
                require(rows[0].label==="Recorded failure" && rows[0].value==="Offline launch","Failure guidance is not first");
                require(rows[0].detail.indexOf("Cause · Not established")>=0,"Unknown cause was lost");
                key(Qt.Key_Return);require(ui.overlay==="facts","Failure note did not open");
                require(ui.checkDetail.detail.indexOf("not a live diagnosis")>=0,"Evidence boundary was lost");step=11;return;
            }
            if(step===11){capture(ui,"failure-guidance",12);return;}
            if(step===12){
                key(Qt.Key_Escape);require(ui.overlay==="checks" && ui.panelIndex===0,"Back lost failure row");
                key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id===original.id,"Failure Back lost edition");
                stop();console.log("OFFLINE_THEME_PASS");Qt.exit(0);
            }
        }catch(error){stop();console.error("OFFLINE_THEME_FAIL "+error);Qt.exit(1);}}
    }
