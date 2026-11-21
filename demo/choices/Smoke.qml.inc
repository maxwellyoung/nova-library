    property int syntheticLaunches:0
    property string lastSyntheticLaunch:""
    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property string homeBefore:""
        property string pinsBefore:""
        property string choicesBefore:""
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Unaccepted key "+k);driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var found=find(item.children[i],name);if(found)return found;}return null;}
        function snap(name,next){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function ids(ui){return ui.choiceData.choices.map(function(p){return p.key;}).join(",");}
        function gotoRow(ui,n){while(ui.panelIndex<n)key(Qt.Key_Down);while(ui.panelIndex>n)key(Qt.Key_Up);}
        function game(id,title,extra){return {title:title,sortBy:title,extra:extra,missing:false,lastPlayed:"",assets:{},files:{count:1},launch:function(){window.syntheticLaunches++;window.lastSyntheticLaunch=id;}};}
        function setup(ui){
            var raw=[],count=fixtureScenario==="fewer"?2:6;
            for(var n=1;n<=count;n++){
                var id="demo:choice"+n,title="Choice "+n;
                if(fixtureScenario==="long" && n===1)title="A very long distinct edition title, including its regional subtitle and an archived revision that must remain distinguishable from the other editions of this same game";
                var extra={"edition-id":[id],"system-id":["snes"],"system-name":["Super Nintendo"],"launchable":[fixtureScenario==="empty"?"false":"true"]};
                if(fixtureScenario==="discs" && n<=2){extra["disc-set-id"]=["choice-adventure"];extra["disc-set-name"]=["Choice adventure"];extra["disc-number"]=[String(n)];}
                raw.push(ChoicesFixture.makeEntry(game(id,title,extra)));
            }
            ui.rawEntries=raw;ui.pins=["demo:choice2"];ui.rotation={version:1,editions:[{id:"demo:choice1",title:raw[0].title}]};
            ui.rebuildPresentations();ui.rebuildHome("");ui.rebuildLibrary("");ui.rebuildThreads("");ui.switchView("home");
            ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
            homeBefore=ui.homeCurrent?ui.homeCurrent.id:"";pinsBefore=JSON.stringify(ui.pins);
        }
        function bounds(ui){
            var explanation=find(ui,"panelExplanation"),list=find(ui,"panelList"),bottom=ui.usableHeight-ui.px(88);
            require(explanation.y+explanation.height<=bottom+1,"Explanation overlaps footer");
            var current=list.currentItem;require(current && current.y-list.contentY>=-1 && current.y-list.contentY+current.height<=list.height+1,"Selected row is offscreen");
        }
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item;
            if(step===0){setup(ui);require(ui.hints().some(function(h){return h.a==="choices";}),"Home has no choice hint");key(Qt.Key_Down);
                require(ui.overlay==="choices" && window.syntheticLaunches===0,"Opening choices launched a game");
                if(fixtureScenario==="empty"){
                    require(ui.choiceData.total===0 && ui.choiceRows().length===3 && ui.choiceRows()[0].dim,"Empty choices invented games");
                    key(Qt.Key_Return);require(window.syntheticLaunches===0,"Empty row launched");snap("empty",10);return;
                }
                if(fixtureScenario==="fewer"){
                    require(ui.choiceData.total===2 && ui.choiceData.choices.length===2,"Fewer games duplicated or invented");choicesBefore=ids(ui);gotoRow(ui,2);key(Qt.Key_Return);
                    require(ids(ui)!==choicesBefore && ui.choiceData.choices.length===2,"Small-pool refresh failed");snap("fewer",10);return;
                }
                if(fixtureScenario==="discs"){
                    require(ui.choiceData.total===5 && ui.choiceData.choices[0].entry.discMembers.length===2,"Disc set was offered twice");
                    require(ui.hints()[0].l==="Choose disc","Disc hint promised immediate Play");key(Qt.Key_Return);require(ui.overlay==="discs","Picker bypassed");
                    key(Qt.Key_X);require(ui.overlay==="dischelp","Disc help missing");key(Qt.Key_Escape);key(Qt.Key_Escape);
                    require(ui.overlay==="choices" && ui.panelIndex===0,"Disc Back lost choice/selection");key(Qt.Key_Return);key(Qt.Key_Return);
                    require(window.syntheticLaunches===1 && window.lastSyntheticLaunch==="demo:choice1","Wrong disc dispatched");snap("discs",20);return;
                }
                require(ui.choiceData.choices.length===3 && ui.choiceData.total===6,"Three choices missing");
                require(ui.choiceData.choices[0].reason==="In your rotation" && ui.choiceData.choices[1].reason==="You favourited this edition","Explicit reasons lost");
                require(ui.panelFooter(0).indexOf("offline readiness is checked separately")>=0,"Routes promoted into offline proof");
                choicesBefore=ids(ui);snap("choices",1);return;
            }
            if(step===1){bounds(ui);gotoRow(ui,3);key(Qt.Key_Return);
                require(ui.choiceData.choices.every(function(p){return choicesBefore.split(",").indexOf(p.key)<0;}),"Refresh repeated the previous three");
                key(Qt.Key_Escape);require(ui.overlay==="" && ui.homeCurrent.id===homeBefore,"Back changed Home focus");snap("home",2);return;
            }
            if(step===2){
                var button=find(ui,"hint_choices"),point=button.mapToItem(ui,button.width/2,button.height/2);driver.tap(Math.round(point.x),Math.round(point.y));
                require(ui.overlay==="choices","Touch hint did not open choices");gotoRow(ui,4);key(Qt.Key_Return);
                require(ui.overlay==="" && JSON.stringify(ui.pins)===pinsBefore && window.syntheticLaunches===0 && ui.homeCurrent.id===homeBefore,"Pass changed state or launched");
                key(Qt.Key_Down);key(Qt.Key_Return);require(window.syntheticLaunches===1 && window.lastSyntheticLaunch==="demo:choice1","Choice dispatched wrong edition");
                key(Qt.Key_Escape);key(Qt.Key_Down);ui.choiceData.choices[0].entry.game.missing=true;key(Qt.Key_Return);
                require(window.syntheticLaunches===1 && ui.notice.indexOf("no longer available")>=0,"Stale choice launched or silently substituted");snap("stale",20);return;
            }
            if(step===10){bounds(ui);gotoRow(ui,ui.choiceRows().length-1);key(Qt.Key_Return);require(ui.overlay==="" && JSON.stringify(ui.pins)===pinsBefore,"Pass from limited pool failed");step=20;return;}
            if(step===20){stop();console.log("CHOICES_THEME_PASS "+fixtureScenario);Qt.exit(0);}
        }catch(error){stop();console.error("CHOICES_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
