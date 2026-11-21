    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property string groupIdentity:""
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Unaccepted key "+k);driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function capture(name,next){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function untouched(){require(api.allGames.launches.length===0,"Help or cancel dispatched a game");}
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};ui.switchView("library");ui.zone="content";
                var index=ui.libraryEntries.map(function(e){return e.discSetId;}).indexOf("demo:set");require(index>=0,"Grouped fixture absent");ui.setLibIndex(index);groupIdentity=ui.current.discSetId;
                require(ui.rawEntries.length===4 && ui.libraryEntries.length===2,"Explicit set/alias grouping changed unrelated edition");
                key(Qt.Key_Return);require(ui.overlay==="discs","Play did not open picker");
                require(ui.panelIndex===(fixtureScenario==="nohistory"?0:1),"Wrong latest-history/first-disc default");
                if(fixtureScenario==="missing"){
                    require(ui.hints()[0].l==="Unavailable","Missing disc advertised play");key(Qt.Key_Return);untouched();require(ui.overlay==="discs","Unavailable disc changed surface");
                }
                require(ui.panelFooter(0).indexOf("does not swap")>=0,"Launch/swap distinction missing");capture("picker",1);return;
            }
            if(step===1){
                var selected=ui.panelIndex;key(Qt.Key_X);require(ui.overlay==="dischelp","X did not open swap help");require(ui.discHelpEntry.discNumber===selected+1,"Help borrowed another disc");
                var rows=ui.panelRows(0),all=rows.map(function(r){return r.label+" "+r.value+" "+r.detail;}).join(" ");
                if(fixtureScenario==="unknown" || fixtureScenario==="mixed"){
                    require(rows.length===2 && all.indexOf("Not checked")>=0,"Unknown runtime invented support");require(all.indexOf("Current Disc Index")<0,"Unknown runtime borrowed RetroArch controls");
                } else require(all.indexOf("If the disc is not listed")>=0 && all.indexOf("Both discs are in the playlist")<0,"Playlist contents were assumed");
                key(Qt.Key_Return);untouched();
                step=11;return;
            }
            if(step===11){
                var list=find(ui,"panelList"),selected=list.currentItem,top=selected.y-list.contentY,footer=find(ui,"panelExplanation");
                require(top>=-1 && top+selected.height<=list.height+1,"Selected help step offscreen");
                require(footer.y+footer.height<=ui.usableHeight-ui.px(80),"Help step explanation collides with controls");
                if(ui.panelIndex<ui.panelRows(0).length-1){key(Qt.Key_Down);return;}
                step=2;return;
            }
            if(step===2){
                var list=find(ui,"panelList"),selected=list.currentItem,top=selected.y-list.contentY,footer=find(ui,"panelExplanation");
                require(top>=-1 && top+selected.height<=list.height+1,"Final help row offscreen");require(footer.y+footer.height<=ui.usableHeight-ui.px(80),"Help collides with footer");capture("help",3);return;
            }
            if(step===3){
                var selected=ui.discHelpIndex;key(Qt.Key_Escape);require(ui.overlay==="discs" && ui.panelIndex===selected && ui.overlayReturn==="","Help Back lost picker selection/parent");
                key(Qt.Key_Escape);require(ui.overlay==="" && ui.current.discSetId===groupIdentity,"Picker Back lost game");untouched();
                ui.openDetails();var play=ui.detailActions().map(function(a){return a.a;}).indexOf("play");ui.runDetailAction(play);
                require(ui.overlay==="discs" && ui.overlayReturn==="details","Details picker entry lost parent");
                ui.runHint("dischelp");require(ui.overlay==="dischelp","Touch hint did not open help");
                require(driver.key(Qt.Key_Back),"Back press unaccepted");require(ui.overlay==="dischelp","Back acted before release");driver.key(Qt.Key_Back,false);
                require(ui.overlay==="discs" && ui.overlayReturn==="details","Android Back lost Details parent");
                key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.discSetId===groupIdentity,"Nested Back did not restore Details");
                key(Qt.Key_Escape);untouched();
                key(Qt.Key_Return);ui.panelIndex=0;key(Qt.Key_Return);
                require(api.allGames.launches.join(",")==="demo:disc1","Explicit A dispatched wrong edition or more than once");
                var opened={};opened["demo:disc1"]="2026-11-11T00:00:00Z";api.allGames.observedPlayDates=opened;api.gameFileLaunched({});step=4;return;
            }
            if(step===4){
                // A synthetic Pegasus observation, not a real launch or physical swap.
                ui.overlay="";key(Qt.Key_Return);require(ui.overlay==="discs" && ui.panelIndex===0,"New local observation did not update default");
                key(Qt.Key_Escape);require(ui.current.discSetId===groupIdentity,"Default refresh lost group");
                stop();console.log("DISC_THEME_PASS "+fixtureScenario);Qt.exit(0);
            }
        }catch(error){stop();console.error("DISC_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
