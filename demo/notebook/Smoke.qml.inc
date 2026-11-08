    FontLoader { id:notebookFont; source:fixtureFont }
    Timer {
        interval:350;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property string originalText:"The lift. Watch the door. <literal text>"
        property string priorHash:""
        property string savedId:""
        property string imageNoteId:""
        function require(value,message){if(!value)throw new Error(message);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function action(panel,id){var index=panel.actions().map(function(a){return a.id;}).indexOf(id);require(index>=0,"missing action "+id);panel.actionIndex=index;panel.activate(index);}
        function key(k){require(driver.key(k),"unaccepted key "+k);driver.key(k,false);}
        function snapshot(name,done){capturing=true;themeLoader.item.grabToImage(function(im){try{require(im.saveToFile(fixtureOutput+"/"+name+".png"),"image capture failed");capturing=false;if(done)done();}catch(error){console.error("NOTEBOOK_THEME_FAIL capture: "+error);Qt.exit(1);}});}
        function finish(){stop();snapshot("final",function(){console.log("NOTEBOOK_THEME_PASS "+fixtureScenario);Qt.exit(0);});}
        onTriggered:{try{
            if(capturing)return;
            var ui=themeLoader.item,panel=find(ui,"stoppingNotebook");require(panel,"component absent");
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                if(fixtureScenario === "legacy"){
                    var bridge=Qt.createQmlObject('import QtQml 2.15; QtObject {property int writes:0;function read(q){return {personal:{entries:{"demo:orbit":{status:"playing",checkpoint:"  Existing checkpoint.  ",revision:7,pending:true,conflict:true}}}};}function act(a){writes++;return {ok:false,error:"Synthetic refusal"};}}',window);
                    window.deviceLibrary=bridge;ui.refreshDevice();
                }
                if(fixtureScenario === "discs"){
                    [0,1].forEach(function(i){var extra=window.api.allGames.get(i).extra;extra["system-id"]="psx";extra["disc-set-id"]="fixture.set";extra["disc-set-name"]="Two-disc fixture";extra["disc-number"]=String(i+1);});ui.rebuildEverything();
                }
                ui.switchView("library");ui.zone="content";ui.setLibIndex(fixtureScenario === "discs"?ui.libraryEntries.map(function(e){return e.discSetId;}).indexOf("fixture.set"):0);ui.openDetails();
                if(fixtureScenario === "absent" || fixtureScenario === "partial"){require(!ui.notebookBridge && ui.detailActions().every(function(a){return a.a!=="note";}),"absent notebook manufactured editing");finish();return;}
                var index=ui.detailActions().map(function(a){return a.a;}).indexOf("note");require(index>=0,"Note unavailable without progress service");ui.runDetailAction(index);
                if(fixtureScenario === "corrupt"){
                    require(ui.overlay==="notebook" && !panel.opened && panel.model.lastError==="corrupt_metadata","unreadable notebook became an empty editable store");
                    require(!ui.notebookCards[ui.current.id].ok,"bad notebook advertised a stopping card");action(panel,"reload");require(!panel.opened,"retry silently recreated corrupt notebook");finish();return;
                }
                require(ui.overlay==="notebook" && panel.opened,"main Note entry failed");
                require(panel.edition===ui.current.id,"wrong edition");
                if(fixtureScenario === "flow") {
                    var entry=ui.current,oldTitle=entry.title,oldLabel=entry.editionLabel;
                    entry.title="Synthetic colliding game";entry.editionLabel="USA · CISO";ui.overlay="details";ui.openNotebook(entry);
                    require(panel.edition===entry.id && panel.title==="Synthetic colliding game · USA · CISO","notebook lost first edition display identity");
                    var other=ui.rawEntries.filter(function(e){return e.id!==entry.id && ui.notebookEligible(e);})[0];
                    require(other,"second notebook fixture missing");var otherTitle=other.title,otherLabel=other.editionLabel;
                    other.title=entry.title;other.editionLabel="USA · NKit";ui.overlay="details";ui.openNotebook(other);
                    require(panel.edition===other.id && panel.title==="Synthetic colliding game · USA · NKit","notebook lost second edition display identity");
                    other.title=otherTitle;other.editionLabel=otherLabel;entry.title=oldTitle;entry.editionLabel=oldLabel;ui.overlay="details";ui.openNotebook(entry);
                }
                if(fixtureScenario === "legacy"){
                    require(panel.showingLegacy && find(panel,"notebookReading").text.indexOf("Existing checkpoint.")>=0,"existing note disappeared behind an empty editor");
                    require(panel.legacyEditable && panel.legacy.conflict,"legacy context missing");panel.model.setText("Unsaved local draft");action(panel,"legacy");require(panel.mode==="confirm","legacy editor dropped local draft");panel.activate(0);require(panel.model.dirty,"Keep draft failed before legacy editor");
                    action(panel,"legacy");panel.activate(1);require(ui.overlay==="text" && ui.textTarget==="demo:orbit","existing editor became unreachable");ui.endText(false);require(ui.overlay==="details" && window.deviceLibrary.writes===0,"cancel wrote old progress");
                    ui.openNotebook(ui.current);action(panel,"adopt");require(panel.model.selectedNote.text==="  Existing checkpoint.  " && panel.model.selectedNote.legacyReference.conflict,"explicit copy lost source conflict: "+JSON.stringify({note:panel.model.selectedNote,legacy:panel.legacy,error:panel.model.lastError,dirty:panel.model.dirty,message:panel.message}));
                    require(window.deviceLibrary.writes===0 && ui.current.conflict && ui.current.pending,"local notebook changed server checkpoint flags");finish();return;
                }
                if(fixtureScenario === "discs"){
                    require(panel.title.indexOf("Disc 1")>=0,"notebook does not identify Disc 1");
                    var disc=ui.current.discEdition,originalTitle=disc.title;
                    disc.title="Synthetic game (Disc 1)";ui.overlay="details";ui.openNotebook(ui.current);
                    require(panel.edition==="demo:orbit" && panel.title==="Synthetic game (Disc 1)","notebook repeats an existing disc cue");
                    disc.title=originalTitle;ui.overlay="details";ui.openNotebook(ui.current);
                    require(panel.edition==="demo:orbit","Disc 1 did not open its member identity");panel.model.setText("Disc one note");panel.save();key(Qt.Key_Back);ui.closeOverlay();
                    window.api.allGames.observedPlayDates={"demo:garden":"2026-11-05T00:00:00Z"};ui.rebuildEverything();
                    ui.setLibIndex(ui.libraryEntries.map(function(e){return e.discSetId;}).indexOf("fixture.set"));ui.openDetails();ui.openNotebook(ui.current);
                    require(panel.edition==="demo:garden" && panel.model.notebook.notes.length===0,"Disc 2 inherited Disc 1 notebook");panel.model.setText("Disc two draft");
                    require(panel.title.indexOf("Disc 2")>=0,"notebook does not identify Disc 2");
                    // A later catalogue/history refresh cannot retarget the open draft.
                    window.api.allGames.observedPlayDates={"demo:orbit":"2026-11-05T01:00:00Z"};ui.rebuildEverything();panel.save();
                    require(stoppingNotes.openEdition("demo:orbit",{}).notebook.notes[0].text==="Disc one note","Disc 1 overwritten by Disc 2 draft");
                    require(stoppingNotes.openEdition("demo:garden",{}).notebook.notes[0].text==="Disc two draft","frozen disc identity lost across refresh");finish();return;
                }
                if(fixtureScenario === "failures"){
                    action(panel,"edit");find(panel,"notebookEditor").cursorPosition=panel.model.draft.text.length;driver.typeText(" after refusal");
                    priorHash=driver.metadataHash(panel.edition);require(driver.allowWrites(panel.edition,false),"could not stage real refused-write fixture");key(0x100002);
                    require(panel.model.dirty && panel.model.lastError==="write_failed" && driver.metadataHash(panel.edition)===priorHash,"failed write lost draft or changed committed bytes");snapshot("write-refused");step=40;return;
                }
                if(fixtureScenario === "reopen"){
                    require(panel.model.draft.text===originalText+" Branch" && panel.model.draft.annotations.length===1 && panel.hasImage,"fresh process did not restore exact note/image/annotation");
                    require(ui.homeCheckpoint(ui.current,0).indexOf("Branch")>=0,"Home did not reopen card");step=30;return;
                }
                if(fixtureScenario === "missing"){
                    require(panel.model.draft.text.indexOf("Branch")>=0 && panel.hasImage && panel.model.previewUrl==="","missing image lost written note or supplied a false preview");step=30;return;
                }
                require(panel.model.notebook.notes.length===0,"fresh store not empty");step=10;return;
            }
            if(step===10){
                driver.tap(find(panel,"notebookAction-edit"));require(panel.mode==="edit","pointer edit action failed");
                driver.typeText(originalText);require(panel.model.draft.text===originalText && panel.model.dirty,"actual text key events did not update draft");key(0x100002);
                require(!panel.model.dirty && panel.mode==="read","physical-key path did not save");savedId=panel.model.selectedNoteId;
                require(ui.homeCheckpoint(ui.current,0).indexOf(originalText)>=0,"Home card not updated from local receipt");snapshot("saved");step=1;return;
            }
            if(step===1){
                action(panel,"edit");find(panel,"notebookEditor").cursorPosition=panel.model.draft.text.length;driver.typeText(" unsaved");
                require(driver.key(Qt.Key_Back),"Back press not consumed");ui.enabled=false;ui.enabled=true;driver.key(Qt.Key_Back,false);require(panel.mode==="read" && panel.model.dirty && !panel.backArmed,"focus loss dropped draft or retained armed Back");key(Qt.Key_Back);require(panel.mode==="confirm","dirty close lacked confirmation");key(0x100000);require(panel.mode==="read" && panel.model.dirty,"safe Keep draft failed");
                action(panel,"history");require(panel.mode==="confirm","dirty History lacked guard");panel.activate(1);
                require(panel.mode==="history" && !panel.model.dirty,"discard/History failed");key(0x100000);require(panel.model.draft.text===originalText,"discard left stale unsaved text visible");step++;return;
            }
            if(step===2){
                action(panel,"attach");require(panel.mode==="images" && panel.imageChoices.length===1,"screenshot chooser failed");step=11;return;
            }
            if(step===11){driver.tap(find(panel,"notebookRow-0"));require(panel.mode==="read" && panel.hasImage,"explicit screenshot selection failed");panel.save();
                require(!panel.model.dirty && panel.hasImage,"image association save failed");imageNoteId=panel.model.selectedNoteId;step=20;return;
            }
            if(step===20){
                if(find(panel,"notebookOriginal").status!==1)return;
                action(panel,"mark");snapshot("marking");step=24;return;
            }
            if(step===24){key(0x100000);key(Qt.Key_Right);key(Qt.Key_Right);key(Qt.Key_Down);key(Qt.Key_Down);key(0x100000);
                require(panel.mode==="read" && panel.model.dirty && panel.model.draft.annotations.length===1,"controller image marking failed");panel.save();snapshot("image");step=3;return;
            }
            if(step===3){
                if(find(panel,"notebookOriginal").status!==1)return;
                action(panel,"edit");find(panel,"notebookEditor").cursorPosition=panel.model.draft.text.length;driver.typeText(" Branch");
                require(driver.otherWriter(panel.edition),"competing writer failed");key(0x100002);
                require(panel.model.dirty && panel.model.lastError==="revision_conflict" && panel.model.draft.text===originalText+" Branch","conflict lost draft");
                panel.mode="read";snapshot("conflict");step=21;return;
            }
            if(step===21){action(panel,"branch");
                require(!panel.model.dirty && panel.model.notebook.notes.length===3,"branch did not retain both writers");imageNoteId=panel.model.selectedNoteId;step=4;return;
            }
            if(step===4){
                action(panel,"clear");require(panel.mode==="confirm","clear lacks review");panel.activate(0);require(panel.model.selectedNoteId===imageNoteId,"safe Keep note cleared data");
                action(panel,"clear");panel.activate(1);require(!panel.model.selectedNoteId && ui.homeCheckpoint(ui.current,0)==="","clear retained false Home stopping card");
                action(panel,"history");panel.beginFind();driver.typeText("Branch");key(Qt.Key_Back);panel.refreshHistory();require(panel.history.length===1 && panel.history[0].cleared,"offline search lost cleared note");snapshot("history");step=22;return;
            }
            if(step===22){panel.chooseHistory(0);
                require(panel.cleared,"cleared state not visible: "+JSON.stringify({opened:panel.opened,selected:panel.model.selectedNoteId,note:panel.model.selectedNote,rows:panel.history}));action(panel,"restore");require(!panel.cleared && panel.model.notebook.stoppingNoteId==="","restore silently changed Home");action(panel,"stopping");
                require(ui.homeCheckpoint(ui.current,0).indexOf("Branch")>=0,"explicit stopping choice not on Home");step=5;return;
            }
            if(step===5){
                var expectedId=ui.current.id;key(Qt.Key_Back);require(ui.overlay==="details" && ui.current.id===expectedId,"Back did not return to same Details");
                var e=ui.current;e.checkpoint="  Existing checkpoint.  ";e.checkpointSource="you";e.revision=7;e.pending=true;e.conflict=true;
                ui.openNotebook(e);action(panel,"adopt");
                var ref=panel.model.selectedNote.legacyReference;
                require(ref.text==="  Existing checkpoint.  " && ref.pending && ref.conflict && ref.revision===7,"copy lost legacy provenance");
                require(e.checkpoint==="  Existing checkpoint.  " && e.pending && e.conflict && e.revision===7,"local copy changed old progress");
                panel.model.select(imageNoteId);panel.model.makeStopping(imageNoteId);panel.changed(panel.edition);
                key(Qt.Key_Back);ui.closeOverlay();ui.switchView("home");ui.homeIndex=ui.homeEntries.map(function(e){return e.id;}).indexOf(expectedId);
                snapshot("home-card");step=23;return;
            }
            if(step===23){
                driver.tap(find(ui,"homeNote"));require(ui.overlay==="notebook" && panel.edition===ui.homeCurrent.id,"Home note pointer opened wrong edition");step=30;return;
            }
            if(step===40){
                require(driver.allowWrites(panel.edition,true),"could not restore test directory permissions");key(0x100002);require(!panel.model.dirty,"retry failed after write access restored");
                var originalStorage=panel.storage;action(panel,"edit");driver.typeText(" draft survives exception");
                var bad=Qt.createQmlObject('import QtQml 2.15; QtObject {function capabilities(){throw new Error("Synthetic storage exception");}}',window);
                panel.storage=bad;panel.save();require(panel.model.dirty && panel.model.lastError==="storage_unavailable","adapter exception discarded the draft");panel.storage=originalStorage;
                panel.request("history");require(panel.mode==="confirm","exception draft lost its guard");panel.activate(1);require(panel.mode==="history" && !panel.model.dirty,"explicit discard failed after exception");bad.destroy();finish();return;
            }
            if(step===30){
                if(panel.hasImage && panel.model.previewUrl && find(panel,"notebookOriginal").status!==1)return;
                require(find(panel,"notebookFeedback").y+find(panel,"notebookFeedback").height<=find(panel,"notebookActions").y,"feedback overlaps action rail");
                var rail=find(panel,"notebookActions");require(rail.y+rail.height<=ui.usableHeight-ui.px(50),"rail exceeds usable area");
                panel.actionIndex=0;step=31;return;
            }
            if(step===31){
                var rail=find(panel,"notebookActions"),item=rail.currentItem,hints=find(ui,"buttonHints");
                require(item && item.opacity===1 && item.x-rail.contentX>=-1 && item.x-rail.contentX+item.width<=rail.width+1,"focused action clipped");
                require(rail.y+rail.height<=hints.y-ui.px(8),"notebook rail overlaps shared footer");
                if(panel.actionIndex+1<panel.actions().length){panel.actionIndex++;return;}
                finish();
            }
        }catch(error){console.error("NOTEBOOK_THEME_FAIL step="+step+": "+error);Qt.exit(1);}}
    }
