    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property int countBefore:0
        property string pinsBefore:""
        property string rawBefore:""
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Unaccepted key "+k);driver.key(k,false);}
        function ids(ui){return ui.rotation.editions.map(function(e){return e.id;}).join(",");}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function capture(name,next){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function picker(ui,id){
            ui.overlay="";ui.switchView("library");ui.zone="content";
            var index=ui.libraryEntries.map(function(e){return e.id;}).indexOf(id);require(index>=0,"Fixture edition missing");ui.setLibIndex(index);ui.openDetails();
            var a=ui.detailActions().map(function(e){return e.a;}).indexOf("thread");require(a>=0,"Offline Collections action missing");ui.runDetailAction(a);
            require(ui.overlay==="threadpick" && ui.panelRows(0)[0].rotation,"Local picker missing");
        }
        function collections(ui){ui.overlay="";ui.switchView("threads");ui.zone="content";ui.threadIndex=0;require(ui.currentThread.origin==="rotation","Local collection is not reachable first");}
        function finish(ui){
            require(ui.gameCount===countBefore && JSON.stringify(ui.rawEntries.map(function(e){return e.id;}))===rawBefore,"Rotation altered the library");
            require(JSON.stringify(ui.pins)===pinsBefore,"Rotation altered favourites");
            stop();console.log("ROTATION_THEME_PASS "+fixtureScenario);Qt.exit(0);
        }
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                require(!ui.canEdit,"Fixture accidentally enables sync");countBefore=ui.gameCount;pinsBefore=JSON.stringify(ui.pins);rawBefore=JSON.stringify(ui.rawEntries.map(function(e){return e.id;}));
                collections(ui);
                if(fixtureScenario==="reopen"){
                    require(ids(ui)==="demo:garden,demo:orbit","Fresh process lost authored order");
                    require(ui.currentThread.entries.map(function(e){return e.id;}).join(",")===ids(ui),"Collection alphabetised saved order");
                    key(Qt.Key_Return);require(ui.threadZone==="members" && ui.current.id==="demo:garden","Open did not select first rotation game");
                    key(Qt.Key_Escape);require(ui.threadZone==="list","Back left collection context");capture("reopened",20);return;
                }
                if(fixtureScenario==="corrupt" || fixtureScenario==="readrefusal"){
                    require(ui.rotation===null,"Unreadable preference became empty");picker(ui,"demo:orbit");var before=JSON.stringify(api.memory.values.rotationV1);key(Qt.Key_Return);
                    require(ui.rotation===null && JSON.stringify(api.memory.values.rotationV1)===before,"Unreadable preference overwritten");
                    collections(ui);key(Qt.Key_X);require(ui.overlay==="rotation" && ui.hints().every(function(h){return h.l!=="Remove";}),"Corrupt state offered removal");capture("unreadable",20);return;
                }
                if(fixtureScenario==="missing"){
                    require(ui.currentThread.absent===1 && ui.currentThread.entries.length===1,"Absent edition disappeared or became launchable");
                    key(Qt.Key_X);require(ui.panelRows(0)[0].label==="Absent edition" && ui.panelRows(0)[0].value.indexOf("Not in catalogue")>=0,"Missing edition has no cached context");
                    ui.panelIndex=1;find(ui,"panelRow_0").clicked(null);require(ids(ui)==="demo:orbit","Touch handler removed the focused row instead of the tapped row");capture("missing-removed",20);return;
                }
                if(fixtureScenario==="long"){
                    key(Qt.Key_X);require(ui.panelFooter(0).indexOf(ui.rotation.editions[0].title)>=0,"Full selected edition title lost");step=31;return;
                }
                if(fixtureScenario==="full"){
                    require(ui.rotation.editions.length===12,"Capacity fixture wrong");picker(ui,"demo:orbit");var before=ids(ui);key(Qt.Key_Return);
                    require(ids(ui)===before && ui.notice.indexOf("12 games")>=0,"Capacity did not preserve rotation");collections(ui);key(Qt.Key_X);
                    for(var i=0;i<11;i++)key(Qt.Key_Down);step=30;return;
                }
                require(ui.rotation.editions.length===0 && !ui.currentThread.entries.length,"Empty rotation invented games");
                key(Qt.Key_X);require(ui.overlay==="rotation" && ui.hints().every(function(h){return h.l!=="Remove";}),"Empty rotation offered removal");capture("empty",1);return;
            }
            if(step===1){
                key(Qt.Key_Escape);require(ui.overlay==="" && ui.view==="threads","Empty Back failed");
                picker(ui,"demo:garden");key(Qt.Key_Return);require(ids(ui)==="demo:garden","First add failed");
                key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id==="demo:garden","Picker Back lost edition");
                picker(ui,"demo:orbit");key(Qt.Key_Return);require(ids(ui)==="demo:garden,demo:orbit","Second add or order failed");
                collections(ui);key(Qt.Key_X);require(ui.overlay==="rotation","Controller edit action failed");step=2;return;
            }
            if(step===2){
                key(Qt.Key_Right);require(ids(ui)==="demo:orbit,demo:garden" && ui.panelIndex===1,"Right did not move selected edition later");
                key(Qt.Key_Left);require(ids(ui)==="demo:garden,demo:orbit" && ui.panelIndex===0,"Left did not retain selection");
                key(Qt.Key_Left);require(ids(ui)==="demo:garden,demo:orbit" && ui.panelIndex===0,"Boundary move changed order");
                ui.runHint("rotationlater");require(ids(ui)==="demo:orbit,demo:garden","Touch hint did not move later");
                ui.runHint("rotationearlier");require(ids(ui)==="demo:garden,demo:orbit","Touch hint did not move earlier");
                capture("editor",3);return;
            }
            if(step===3){
                key(Qt.Key_Return);require(ids(ui)==="demo:orbit" && ui.panelIndex===0,"Removal failed or focus escaped");
                picker(ui,"demo:garden");key(Qt.Key_Return);require(ids(ui)==="demo:orbit,demo:garden","Re-add did not append");
                collections(ui);key(Qt.Key_Return);key(Qt.Key_Down);require(ui.current.id==="demo:garden","Member selection wrong");
                key(Qt.Key_X);var a=ui.detailActions().map(function(e){return e.a;}).indexOf("thread");ui.runDetailAction(a);key(Qt.Key_Return);
                require(ids(ui)==="demo:orbit" && ui.overlay==="" && ui.threadZone==="list","Removing an open member silently switched its Details");
                picker(ui,"demo:garden");key(Qt.Key_Return);collections(ui);key(Qt.Key_X);key(Qt.Key_Down);key(Qt.Key_Left);
                require(ids(ui)==="demo:garden,demo:orbit" && ui.panelIndex===0,"Final order wrong");step=4;return;
            }
            if(step===4){
                var before=ids(ui),saved=JSON.stringify(api.memory.get("rotationV1"));api.memory.refuseAllWrites=true;key(Qt.Key_Return);api.memory.refuseAllWrites=false;
                require(ids(ui)===before && JSON.stringify(api.memory.get("rotationV1"))===saved,"Refused write changed UI or preferences");
                require(ui.notice.indexOf("previous order was kept")>=0,"Write failure hidden");
                capture("write-refusal",5);return;
            }
            if(step===5){
                require(driver.key(Qt.Key_Back),"Android Back press unaccepted");require(ui.overlay==="rotation","Back acted before release");driver.key(Qt.Key_Back,false);
                require(ui.overlay==="" && ui.view==="threads","Android Back closed the launcher context");
                ui.notice="";
                console.log("ROTATION_SAVED "+JSON.stringify(api.memory.get("rotationV1")));capture("collection",20);return;
            }
            if(step===20){finish(ui);return;}
            if(step===30){
                var list=find(ui,"panelList"),selected=list.currentItem,top=selected.y-list.contentY;
                require(ui.panelIndex===11 && top>=-1 && top+selected.height<=list.height+1,"Last rotation row is offscreen");
                var notice=find(ui,"footerNotice"),hints=find(ui,"primaryHints");
                require(!notice.visible || notice.x>=hints.x+hints.width+ui.px(20),"Status notice overlaps the Back controls");
                key(Qt.Key_Right);require(ui.panelIndex===11,"End move escaped bounds");capture("full",20);return;
            }
            if(step===31){
                var list=find(ui,"panelList"),selected=list.currentItem,top=selected.y-list.contentY,footer=find(ui,"panelExplanation");
                require(top>=-1 && top+selected.height<=list.height+1,"Long-title selection is offscreen");
                require(footer.y+footer.height<=ui.usableHeight-ui.px(80),"Long-title explanation collides with controls");capture("long-title",20);return;
            }
        }catch(error){stop();console.error("ROTATION_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
