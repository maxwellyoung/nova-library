    Timer {
        interval:250;running:true;repeat:true
        property int step:0
        property int attempts:0
        property bool capturing:false
        property string selectedId:""
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"unaccepted key "+k);driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function snapshot(name,done){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"capture failed");capturing=false;if(done)done();});}
        function finish(){stop();snapshot("final",function(){console.log("SAVE_COPIES_THEME_PASS "+fixtureScenario);Qt.exit(0);});}
        onTriggered:{try{
            if(capturing)return;
            var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                ui.switchView("library");ui.zone="content";
                var index=ui.libraryEntries.map(function(e){return e.id;}).indexOf("demo:orbit");require(index>=0,"edition fixture missing");ui.setLibIndex(index);ui.openDetails();
                var action=ui.detailActions().map(function(a){return a.a;}).indexOf("savecopies");
                if(fixtureScenario==="absent" || fixtureScenario==="partial"){require(action<0 && !ui.saveCopiesBridge,"unsupported bridge exposed action");finish();return;}
                require(action>=0,"Save copies action missing");
                if(fixtureScenario==="missing" || fixtureScenario==="corrupt")driver.damage(fixtureScenario==="missing");
                ui.runDetailAction(action);require(ui.overlay==="savecopies","entry failed");require(ui.saveCopyEdition==="demo:orbit","wrong edition");
                if(["shared-directory","shared-index","parent-alias","index-link","index-type"].indexOf(fixtureScenario)>=0){
                    require(ui.saveCopiesData.ok===false && ui.saveCopiesData.error==="storage_unavailable","Invalid private storage became readable");
                    var expectedStage=fixtureScenario==="shared-directory" || fixtureScenario==="parent-alias"?"copy-directory":"copy-index";
                    var expectedCheck=fixtureScenario==="parent-alias"?"canonical_mismatch":fixtureScenario==="index-link"?"symbolic_link":fixtureScenario==="index-type"?"wrong_type":"shared_permissions";
                    require(ui.saveCopiesData.storageStage===expectedStage && ui.saveCopiesData.storageCheck===expectedCheck,"Wrong factual storage check");
                    require(ui.saveCopiesData.storageRootSha256===ui.saveCopiesBridge.capabilities().storageRootSha256,"Failure/root context binding differs");
                    require(ui.hints().every(function(h){return h.l!=="Check copy";}),"Unavailable storage offered checksum check");
                    var explanation=find(ui,"panelExplanation");require(explanation && explanation.y+explanation.height<=ui.usableHeight,"Storage failure explanation overflows");
                    require(ui.panelFooter(0).indexOf("No restore was attempted")>=0,"Storage refusal lost restore boundary");
                    require(ui.panelFooter(0).indexOf(ui.saveCopiesData.storageRootSha256)<0,"Opaque diagnostic binding became user-facing text");
                    ui.panelActivate(0,1);require(!ui.saveCopyToken,"Unavailable storage started checksum worker");snapshot("storage-refusal");step=3;return;
                }
                if(fixtureScenario==="empty"){require(ui.panelRows(0).length===1 && !ui.panelRows(0)[0].copy,"empty view invented a copy");require(ui.hints().every(function(h){return h.l!=="Check copy";}),"empty view offered check");step=3;return;}
                require(ui.panelRows(0).length===2,"history size differs");
                if(fixtureScenario==="legacy-review"){
                    require(ui.hints().every(function(h){return h.l!=="Check copy";}),"Legacy reader offered unbound checking");
                    key(Qt.Key_Return);require(!ui.saveCopyToken && !ui.saveCopyResults[ui.panelRows(0)[0].copy.checkpointId],"Legacy reader started unbound checking");
                    require(ui.panelFooter(0).indexOf("matching Library build")>=0,"Legacy reader lacks capability explanation");snapshot("legacy-reader");step=3;return;
                }
                if(fixtureScenario==="missing"){require(ui.panelRows(0)[0].copy.copyState==="missing","missing archive looked ready");ui.panelActivate(0,1);require(!ui.saveCopyToken,"missing copy started check");step=3;return;}
                snapshot("copies");step=1;return;
            }
            if(step===1){
                key(Qt.Key_Down);require(ui.panelIndex===1,"D-pad list navigation failed");selectedId=ui.panelRows(0)[1].copy.checkpointId;
                if(fixtureScenario==="stale-review")driver.damagePicture("stale");
                key(Qt.Key_Return);
                if(fixtureScenario==="focus"){ui.applicationActive(false);require(!ui.saveCopyToken && !ui.saveCopyResults[selectedId],"focus loss retained a stale result");ui.applicationActive(true);step=3;return;}
                step=2;return;
            }
            if(step===2){
                if(ui.saveCopyToken){require(++attempts<40,"check did not finish");return;}
                var result=ui.saveCopyResults[selectedId];require(result,"result missing");
                require(result.ok===(fixtureScenario!=="corrupt" && fixtureScenario!=="stale-review"),"wrong checksum outcome");require(result.runtimeRestoreAvailable!==true,"restore capability manufactured");
                if(fixtureScenario==="stale-review")require(result.error==="history_changed","Changed displayed history was not refused");
                var footer=find(ui,"panelExplanation");require(footer && footer.y+footer.height<=ui.usableHeight,"copy explanation overflows the panel");
                require(ui.panelFooter(0).indexOf("does not load or replace")>=0,"restore boundary missing");snapshot("checked");step=3;return;
            }
            if(step===3){key(Qt.Key_Escape);require(ui.overlay==="details","Back did not return to Details");require(ui.current.id==="demo:orbit","return changed edition");var action=ui.detailActions().map(function(a){return a.a;}).indexOf("savecopies");require(ui.detailAction===action,"return lost action focus");key(Qt.Key_Escape);require(ui.overlay==="","Details Back failed");finish();}
        }catch(error){stop();console.error("SAVE_COPIES_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
