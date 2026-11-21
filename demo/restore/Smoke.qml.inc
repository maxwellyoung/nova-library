    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property var original:null
        property int selectedRow:0
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Key not accepted");driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var f=find(item.children[i],name);if(f)return f;}return null;}
        function show(ui,route,profile){
            var e={};Object.keys(original).forEach(function(k){e[k]=original[k];});e.route=route;e.sessionProfile=profile||"";
            ui.overlay="";ui.rawEntries=ui.rawEntries.map(function(old){return old.id===e.id?e:old;});ui.rebuildPresentations();ui.switchView("library");ui.rebuildLibrary(e.id);
            ui.setLibIndex(ui.libraryEntries.map(function(x){return x.id;}).indexOf(e.id));ui.zone="content";ui.openDetails();
            ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("guide"));require(ui.overlay==="guide","Controls not open");
        }
        function select(ui,label){var rows=ui.panelRows(0);selectedRow=rows.map(function(r){return r.label;}).indexOf(label);require(selectedRow>=0,"Missing row "+label);while(ui.panelIndex<selectedRow)key(Qt.Key_Down);}
        function capture(ui,name,next){capturing=true;ui.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        onTriggered:{try{
            if(capturing)return;
            var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                original=ui.rawEntries.filter(function(e){return e.id==="demo:orbit";})[0];require(original,"Fixture missing");
                show(ui,"RetroArch fixture");select(ui,"Undo a load");require(ui.hints().some(function(h){return h.l==="Read full";}),"Read full hint absent");step=1;return;
            }
            if(step===1){
                var list=find(ui,"panelList"),row=find(ui,"panelRow_"+selectedRow);require(row,"Selected row not rendered");
                var p=row.mapToItem(list,0,0);require(p.y>=-1 && p.y+row.height<=list.height+1,"Undo row clipped");
                capture(ui,"controls",2);return;
            }
            if(step===2){
                key(Qt.Key_Return);require(ui.overlay==="facts" && ui.checkDetailReturn==="guide","Read opened wrong parent");
                require(ui.checkDetail.detail.indexOf("not a durable checkpoint")>=0 && ui.checkDetail.detail.indexOf("if offered")>=0,"Undo scope lost");step=3;return;
            }
            if(step===3){capture(ui,"full-guidance",4);return;}
            if(step===4){
                var facts=find(ui,"detailFacts");if(facts.contentHeight>facts.height+1){var before=facts.contentY;ui.runHint("readfacts");require(facts.contentY>before,"Full guidance cannot scroll");}
                key(Qt.Key_Escape);require(ui.overlay==="guide" && ui.panelIndex===selectedRow,"Back lost Controls row");
                key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id===original.id,"Controls Back lost edition");
                ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("checks"));key(Qt.Key_Return);
                require(ui.overlay==="facts" && ui.checkDetailReturn==="checks","Guide contaminated Checks return");key(Qt.Key_Escape);require(ui.overlay==="checks","Checks Back returned to Controls");
                show(ui,"HakuX","hakux-nova-v1");select(ui,"Undo after loading");require(ui.panelRows(0)[selectedRow].value==="Not in this shortcut profile","HakuX claimed undo");step=5;return;
            }
            if(step===5){capture(ui,"unsupported-profile",6);return;}
            if(step===6){
                key(Qt.Key_Return);require(ui.overlay==="facts" && ui.checkDetailReturn==="guide","Unsupported full note failed");key(Qt.Key_Back);
                require(ui.overlay==="guide" && ui.panelIndex===selectedRow,"Android Back lost guide row");
                show(ui,"Unknown runtime");select(ui,"Undo after loading");require(ui.panelRows(0)[selectedRow].value==="Not checked","Unknown runtime borrowed undo");step=7;return;
            }
            if(step===7){capture(ui,"unknown",8);return;}
            if(step===8){key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id===original.id,"Final Back failed");stop();console.log("RESTORE_GUIDE_PASS");Qt.exit(0);}
        }catch(error){stop();console.error("RESTORE_GUIDE_FAIL "+error);Qt.exit(1);}}
    }
