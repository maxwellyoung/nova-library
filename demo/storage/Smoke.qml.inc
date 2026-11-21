    Timer {
        interval:200;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property string originalLibrary:""
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Unaccepted key "+k);driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function capture(name,next){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function parts(ui){var track=find(ui,"capacityTrack"),out=[];for(var i=0;i<track.children.length;i++)if(track.children[i].objectName.indexOf("capacityPart_")===0)out.push(track.children[i]);return out;}
        function geometry(ui){
            var list=find(ui,"panelList"),row=list.currentItem,footer=find(ui,"panelExplanation"),top=row.y-list.contentY;
            require(top>=-1 && top+row.height<=list.height+1,"Selected storage row is offscreen");
            require(footer.y+footer.height<=ui.usableHeight-ui.px(80),"Storage explanation collides with controls");
        }
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                originalLibrary=ui.rawEntries.map(function(e){return e.id;}).join(",");
                ui.openPanel("settings",2);ui.panelActivate(2,1);require(ui.overlay==="storage" && ui.panelRows(0)[0].volume,"Settings storage volume selector missing");
                if(fixtureScenario==="conflict")require(ui.storageObservation.status==="conflict" && !ui.storageObservation.snapshot,"Conflicting snapshots plotted a value");
                else {
                    require(ui.storageObservation.snapshot.total===64*1073741824,"Internal capacity missing or combined with SD");
                    if(fixtureScenario==="invalid" || fixtureScenario==="category-conflict"){
                        require(ui.panelRows(0).filter(function(r){return r.category==="unclassified";})[0].bytes===40*1073741824,"Bad category data manufactured a measurement");
                        require(ui.panelFooter(0).indexOf(fixtureScenario==="invalid"?"reconciled":"conflict")>=0,"Category failure hidden");
                    }
                }
                capture("internal",1);return;
            }
            if(step===1){
                geometry(ui);
                if(fixtureScenario!=="conflict") {
                    var chart=parts(ui),track=find(ui,"capacityTrack");
                    require(chart.length>=3,"Measured capacity has no segments");
                    require(Math.abs(chart.reduce(function(sum,p){return sum+p.width;},0)-track.width)<0.01,"Segments do not cover exact capacity");
                    require(ui.storageRows().some(function(r){return r.label==="ROM inventory · all locations";}),"ROM inventory lost its separate scope");
                    var cache=ui.storageRows().map(function(r){return r.category;}).indexOf("cache");ui.panelIndex=cache;
                    if(fixtureScenario==="flow" || fixtureScenario==="zero") {
                        require(ui.panelRows(0)[cache].value==="0 B","Measured zero became unknown");
                        var zero=find(ui,"capacityPart_cache");require(zero && zero.width===0 && !zero.visible,"Zero category gained visual area");
                    }
                }
                ui.panelIndex=0;key(Qt.Key_Right);require(ui.storageVolumeId==="sd-card","Right did not select microSD");step=2;return;
            }
            if(step===2){
                geometry(ui);
                if(fixtureScenario==="legacy" || fixtureScenario==="sd-unknown") {
                    require(ui.storageObservation.status==="unknown" && !ui.storageObservation.snapshot,"Unknown SD became an empty or absent card");
                    require(parts(ui).length===0,"Unknown SD drew measured segments");require(ui.panelFooter(0).indexOf("does not establish")>=0,"Unknown-card boundary lost");
                } else require(ui.storageObservation.snapshot.total===256*1073741824,"microSD capacity missing or combined");
                capture("sd",3);return;
            }
            if(step===3){
                ui.runHint("panel");require(ui.storageVolumeId==="internal-data","Touch footer did not change volume");
                key(Qt.Key_Return);require(ui.storageVolumeId==="sd-card","A did not change volume");key(Qt.Key_Left);require(ui.storageVolumeId==="internal-data","Left did not restore internal storage");
                var category=ui.storageRows().map(function(r){return r.category;}).indexOf("unclassified");ui.panelIndex=category;step=4;return;
            }
            if(step===4){
                geometry(ui);
                if(ui.storageObservation.snapshot){var selected=find(ui,"capacityPart_unclassified");require(selected && selected.opacity===1,"Selected category did not highlight its bar segment");}
                capture("unclassified",5);return;
            }
            if(step===5){
                var inventory=ui.storageRows().map(function(r){return r.label;}).indexOf("ROM inventory · all locations");ui.panelIndex=inventory;
                require(ui.panelFooter(0).indexOf("separately from filesystem capacity")>=0,"Logical and filesystem bytes mixed");
                key(Qt.Key_Escape);require(ui.overlay==="settings" && ui.panelIndex===2,"Back did not return to Storage settings row");
                ui.panelActivate(2,1);require(driver.key(Qt.Key_Back),"Android Back unaccepted");require(ui.overlay==="storage","Android Back acted before release");driver.key(Qt.Key_Back,false);
                require(ui.overlay==="settings" && ui.panelIndex===2,"Android Back lost Settings context");
                require(ui.rawEntries.map(function(e){return e.id;}).join(",")===originalLibrary,"Read-only storage changed catalogue");
                stop();console.log("STORAGE_THEME_PASS "+fixtureScenario);Qt.exit(0);
            }
        }catch(error){stop();console.error("STORAGE_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
