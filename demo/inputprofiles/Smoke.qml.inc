    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property string bytesBefore:""
        property var key:({editionId:"demo:orbit",runtimeId:"demo-runtime",runtimeVersion:"1.2.3"})
        property var other:({editionId:"demo:garden",runtimeId:"demo-runtime",runtimeVersion:"1.2.3"})
        function require(v,m){if(!v)throw new Error(m);}
        function press(k){require(driver.key(k),"Unaccepted key "+k);driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var x=find(item.children[i],name);if(x)return x;}return null;}
        function snap(name,next){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function value(){var r=api.memory.checkedRead(ProfilesFixture.KEY);return r.ok?ProfilesFixture.store(r.exists?r.value:undefined):null;}
        function gotoRow(panel,n){while(panel.index<n)press(Qt.Key_Down);while(panel.index>n)press(Qt.Key_Up);}
        function open(ui){
            ui.openPanel("guide",0);var rows=ui.panelRows(0),idx=-1;
            rows.forEach(function(r,i){if(r.inputProfile)idx=i;});require(idx>=0,"Controls has no input preferences route");require(ui.profileSetup(ui.current),"Fixture has no exact recorded setup");
            ui.panelIndex=idx;press(Qt.Key_Return);require(ui.overlay==="inputprofile","Input route did not open");
            return find(ui,"inputProfilePanel");
        }
        function setup(ui,version){
            ui.overlay="";ui.switchView("library");ui.zone="content";
            var i=ui.libraryEntries.map(function(e){return e.id;}).indexOf(key.editionId);require(i>=0,"Fixture edition absent");ui.setLibIndex(i);
            var e=ui.current;e.compatibilityRecipeId="fixture-setup";
            e.compatibilityReceipts=[{schemaVersion:1,editionId:e.id,recipe:{id:"fixture-setup",device:"demo",runtime:"demo-runtime",version:version,core:"demo",driver:"demo",display:"4:3",input:"demo",settings:"fixture"},checks:[{stage:"boot",result:"pass",observedAt:"2026-01-01T00:00:00Z",source:"Synthetic fixture",method:"test",note:"Fixture only"}]}];
            // The actual Details -> Controls path remains the entry point.
            ui.openDetails();var a=ui.detailActions().map(function(r){return r.a;}).indexOf("guide");require(a>=0,"Details has no Controls");ui.runDetailAction(a);
        }
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item,panel=find(ui,"inputProfilePanel");
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                if(fixtureScenario==="flow")require(api.memory.checkedSet(ProfilesFixture.KEY,ProfilesFixture.edit(ProfilesFixture.store(undefined),other,ProfilesFixture.defaults())),"Seed failed");
                setup(ui,fixtureScenario==="unlinked"?"unknown":"1.2.3");
                if(fixtureScenario==="unlinked"){
                    var rows=ui.panelRows(0),idx=rows.length-1;require(rows[idx].inputProfile && rows[idx].value==="Setup not recorded","Unknown setup hidden");
                    ui.panelIndex=idx;press(Qt.Key_Return);require(ui.overlay==="facts" && !api.memory.checkedRead(ProfilesFixture.KEY).exists,"Unknown setup opened an editor or saved a profile");
                    snap("unlinked",20);return;
                }
                panel=open(ui);require(panel.binding.editionId===key.editionId,"Wrong edition");
                if(fixtureScenario==="corrupt" || fixtureScenario==="future"){
                    bytesBefore=driver.preferenceBytes();require(!panel.ready,"Unreadable preferences became writable");press(Qt.Key_Right);press(Qt.Key_Return);
                    require(driver.preferenceBytes()===bytesBefore,"Unreadable preferences overwritten");snap("unavailable",20);return;
                }
                if(fixtureScenario==="reopen"){
                    require(panel.hadProfile && panel.draft.sensitivity.x===1.2,"Fresh process lost saved preference");
                    require(ProfilesFixture.profile(value(),other)!==null,"Other edition lost");snap("reopened",20);return;
                }
                require(!panel.hadProfile && !panel.dirty,"Invented saved profile");snap("starting",1);return;
            }
            if(step===1){
                press(Qt.Key_Right);require(panel.draft.sensitivity.x===1.1,"Right did not adjust");
                var row=find(panel,"inputProfileTouch_0"),point=row.mapToItem(themeLoader.item,row.width/2,row.height/2);driver.tap(Math.round(point.x),Math.round(point.y));
                require(panel.draft.sensitivity.x===1.2,"Touch did not adjust focused field");press(Qt.Key_Left);gotoRow(panel,4);press(Qt.Key_Return);require(panel.draft.inversion.x,"Accept did not toggle");
                gotoRow(panel,11);press(Qt.Key_Return);require(panel.hadProfile && !panel.dirty && ProfilesFixture.profile(value(),key).preferences.sensitivity.x===1.1,"Save did not commit");
                require(ProfilesFixture.profile(value(),other).preferences.sensitivity.x===1,"Another edition changed");snap("saved",2);return;
            }
            if(step===2){
                gotoRow(panel,0);press(Qt.Key_Right);gotoRow(panel,11);bytesBefore=driver.preferenceBytes();driver.lockPreferences(true);press(Qt.Key_Return);
                require(panel.dirty && panel.draft.sensitivity.x===1.2 && ProfilesFixture.profile(panel.savedState,key).preferences.sensitivity.x===1.1,"Refused commit changed saved state or draft");
                require(driver.preferenceBytes()===bytesBefore,"Refused commit changed file bytes");require(panel.message.indexOf("could not be saved")>=0,"Refused commit message: "+panel.message);snap("write-refusal",3);return;
            }
            if(step===3){
                driver.lockPreferences(false);press(Qt.Key_Return);require(!panel.dirty && ProfilesFixture.profile(value(),key).preferences.sensitivity.x===1.2,"Retry failed");
                press(Qt.Key_Back);require(ui.overlay==="guide","Android Back lost Controls");setup(ui,"1.2.4");panel=open(ui);
                require(!panel.hadProfile && panel.draft.sensitivity.x===1,"New version inherited an older profile");press(Qt.Key_Right);gotoRow(panel,11);press(Qt.Key_Return);
                require(value().profiles.length===3,"New version overwrote another binding");gotoRow(panel,12);press(Qt.Key_Return);require(panel.mode==="clear" && panel.index===1,"Clear lacks safe default");
                press(Qt.Key_Return);require(panel.mode==="edit" && value().profiles.length===3,"Cancel cleared preferences");gotoRow(panel,12);press(Qt.Key_Return);press(Qt.Key_Up);press(Qt.Key_Return);
                require(!panel.hadProfile && value().profiles.length===2 && ProfilesFixture.profile(value(),key).preferences.sensitivity.x===1.2,"Clear affected another setup");
                bytesBefore=driver.preferenceBytes();ui.handleKey({key:Qt.Key_Return,isAutoRepeat:true,accepted:false});
                require(!panel.hadProfile && value().profiles.length===2 && driver.preferenceBytes()===bytesBefore,"Held clear confirmation recreated saved preferences");
                ui.handleKey({key:Qt.Key_Up,isAutoRepeat:true,accepted:false});require(panel.index===10,"Directional repeat stopped reaching input preferences");gotoRow(panel,11);
                snap("cleared-version",4);return;
            }
            if(step===4){
                press(Qt.Key_Escape);setup(ui,"1.2.3");panel=open(ui);press(Qt.Key_Right);bytesBefore=driver.preferenceBytes();press(Qt.Key_Escape);
                require(panel.mode==="discard" && panel.index===0,"Dirty Back discarded immediately");press(Qt.Key_Return);require(panel.mode==="edit" && panel.dirty,"Keep editing lost draft");
                press(Qt.Key_Escape);press(Qt.Key_Down);press(Qt.Key_Return);require(ui.overlay==="guide" && driver.preferenceBytes()===bytesBefore,"Discard wrote or lost Controls");panel=open(ui);
                require(panel.draft.sensitivity.x===1.2,"Discard leaked into saved preferences");
                gotoRow(panel,11);snap("final",5);return;
            }
            if(step===5){
                var list=find(panel,"inputProfileList"),item=list.currentItem,top=item.y-list.contentY;
                require(top>=-1 && top+item.height<=list.height+1,"Save row is offscreen");require(Math.abs(list.contentY/ item.height-Math.round(list.contentY/item.height))<0.01,"Viewport cuts through a settled row");
                require(driver.retainCommit(),"Retain exact committed preferences failed");driver.externalPreferences();bytesBefore=driver.preferenceBytes();press(Qt.Key_Return);
                require(panel.message.indexOf("Restart Library")>=0 && driver.preferenceBytes()===bytesBefore,"External preferences overwritten");snap("external-change",20);return;
            }
            if(step===20){
                // Flow's separately saved file is captured by the runner before the external edit.
                stop();console.log("INPUT_PROFILE_THEME_PASS "+fixtureScenario);Qt.exit(0);
            }
        }catch(e){stop();console.error("INPUT_PROFILE_THEME_FAIL "+fixtureScenario+": "+e);Qt.exit(1);}}
    }
