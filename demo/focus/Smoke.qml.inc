    readonly property url focusThemeUrl: Qt.resolvedUrl("../theme/theme.qml")
    Timer {
        interval:120;running:true;repeat:true
        property int step:0
        property int waits:0
        property var pendingFocus:null
        property bool capturing:false
        function require(v,m){if(!v)throw new Error(m);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        onTriggered:{try{
            if(capturing)return;
            if(step===0){
                var ui=themeLoader.item;require(ui && ui.ready,"Theme not ready");
                if(fixtureScenario==="library-search"){
                    ui.switchView("library");ui.setLibIndex(ui.libraryEntries.map(function(e){return e.id;}).indexOf("demo:orbit"));
                    ui.toggleKeep(ui.current);ui.setFilter("kept",true);ui.setSort("recent");find(ui,"searchInput").text="amber";
                    require(ui.current && ui.current.id==="demo:orbit","Search fixture not selected");require(ui.saveFocus(),"Library return context refused");
                    api.memory.set("library",{filters:{},sort:"alpha"});themeLoader.source="";step=1;return;
                }
                ui.switchView("threads");ui.threadIndex=0;ui.openThread();ui.memberIndex=1;
                require(ui.current && ui.current.id==="demo:orbit","Second member missing");
                ui.openDetails();ui.closeOverlay();require(ui.threadZone==="members" && ui.current.id==="demo:orbit","Details lost member");
                ui.saveFocus();var f=api.memory.get("focus");
                require(f.thread==="local:rotation-v1" && f.threadMember==="demo:orbit" && f.threadZone==="members","Focus did not retain exact member");
                if(fixtureScenario==="missing")api.memory.set("rotationV1",{version:1,editions:[{id:"demo:garden",title:"The Moss Garden"}]});
                else if(fixtureScenario==="reordered")api.memory.set("rotationV1",{version:1,editions:[{id:"demo:orbit",title:"Amber Orbit"},{id:"demo:garden",title:"The Moss Garden"}]});
                else if(fixtureScenario==="other-collection"){f.thread="local:absent-collection";pendingFocus=f;}
                else if(fixtureScenario==="legacy"){delete f.threadMember;delete f.threadZone;delete f.view;pendingFocus=f;}
                else if(fixtureScenario==="list"){ui.threadZone="list";ui.saveFocus();}
                themeLoader.source="";step=1;return;
            }
            if(step===1){if(pendingFocus){api.memory.set("focus",pendingFocus);if(fixtureScenario==="legacy")api.memory.set("view","threads");}themeLoader.source=focusThemeUrl;step=2;return;}
            if(step===2){
                var fresh=themeLoader.item;if(!fresh || !fresh.ready){require(++waits<60,"Theme recreation timed out");return;}
                if(fixtureScenario==="library-search"){
                    require(fresh.view==="library" && fresh.current && fresh.current.id==="demo:orbit","Search return lost exact edition");
                    require(fresh.filters.kept && fresh.sortMode==="recent" && fresh.searchText==="amber" && find(fresh,"searchInput").text==="amber","Search/sort/filter did not return together");
                    fresh.openDetails();fresh.closeOverlay();require(fresh.current.id==="demo:orbit" && fresh.searchText==="amber","Details lost searched selection");
                    capturing=true;fresh.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/restored.png"),"Capture failed");capturing=false;step=3;});return;
                }
                require(fresh.view==="threads" && fresh.zone==="content","Recreation lost view/content");
                if(["missing","other-collection","legacy","list"].indexOf(fixtureScenario)>=0){
                    require(fresh.threadZone==="list" && fresh.current===null,"Stale/legacy/list focus opened another member");
                }else{
                    require(fresh.threadZone==="members" && fresh.current.id==="demo:orbit","Recreation lost exact collection member");
                    require(fresh.memberIndex===(fixtureScenario==="reordered"?0:1),"Saved numeric position replaced identity");
                    fresh.rebuildEverything();require(fresh.current.id==="demo:orbit","Refresh lost member");
                    require(driver.key(Qt.Key_Escape),"Back key refused");driver.key(Qt.Key_Escape,false);
                    require(fresh.threadZone==="list" && fresh.current===null,"Back did not return to collection list");
                    fresh.openThread();fresh.memberIndex=fixtureScenario==="reordered"?0:1;
                }
                capturing=true;fresh.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/restored.png"),"Capture failed");capturing=false;step=3;});return;
            }
            if(step===3){stop();console.log("FOCUS_THEME_PASS "+fixtureScenario);Qt.exit(0);}
        }catch(error){stop();console.error("FOCUS_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
