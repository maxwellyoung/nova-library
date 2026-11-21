    Timer {
        interval:200;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property var original:null
        property int selectedRow:0
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Key not accepted");driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var f=find(item.children[i],name);if(f)return f;}return null;}
        function capture(ui,name,next){capturing=true;ui.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function show(ui,kind){
            var e={};Object.keys(original).forEach(function(k){e[k]=original[k];});e.compatibilityRecipeId="fixture.measured.v1";
            var setup={id:e.compatibilityRecipeId,device:"Synthetic handheld",runtime:"Fixture runtime",version:"1.0",core:"Fixture core",driver:"Fixture driver",display:"Fit 4:3",input:"Fixture pad",settings:"Synthetic 2x render setup"};
            var c={stage:kind==="menu"?"menus":"gameplay",result:"pass",method:"observed",observedAt:"2026-11-10T10:00:00Z",source:"Synthetic fixture; no hardware measurement",note:"Limited to the named fixture scene",durationSeconds:120,
                performance:{context:kind==="menu"?"menus":"gameplay",scene:kind==="menu"?"Options screen":"Courtyard fight",measurement:"Synthetic frame-time log, whole scene",metrics:{averageFps:59.8,p95FrameMs:18.2,p99FrameMs:24.5}}};
            var checks=[c];if(kind==="conflict"){var b=JSON.parse(JSON.stringify(c));b.performance.metrics.averageFps=42;checks.push(b);}
            if(kind==="zero")c.performance.metrics={averageFps:0};
            if(kind==="invalid")c.performance.metrics.averageFps=-1;
            if(fixtureLarge && kind==="gameplay"){
                c.performance.scene+=" · "+new Array(8).join("panning section ");
                c.performance.measurement+=" · "+new Array(8).join("frame-time pass ");
            }
            if(kind==="legacy")delete c.performance;
            e.compatibilityReceipts=JSON.stringify([{schemaVersion:1,editionId:e.id,recipe:setup,checks:checks}]);
            ui.overlay="";ui.rawEntries=ui.rawEntries.map(function(old){return old.id===e.id?e:old;});ui.rebuildPresentations();ui.switchView("library");ui.rebuildLibrary(e.id);
            ui.setLibIndex(ui.libraryEntries.map(function(x){return x.id;}).indexOf(e.id));ui.zone="content";ui.openDetails();
            ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("checks"));
        }
        function select(ui,label){
            var rows=ui.panelRows(0);selectedRow=rows.map(function(r){return r.label;}).indexOf(label);require(selectedRow>=0,"Measurement row absent: "+label);
            while(ui.panelIndex<selectedRow)key(Qt.Key_Down);while(ui.panelIndex>selectedRow)key(Qt.Key_Up);
        }
        function closeFacts(ui){key(Qt.Key_Escape);require(ui.overlay==="checks" && ui.panelIndex===selectedRow,"Back lost measured row");}
        onTriggered:{try{
            if(capturing)return;
            var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                original=ui.rawEntries.filter(function(e){return e.id==="demo:orbit";})[0];require(original,"Fixture missing");show(ui,"menu");
                select(ui,fixtureScenario==="before"?"Menus":"Menu measurement");step=1;return;
            }
            if(step===1){capture(ui,"menu-checks",2);return;}
            if(step===2){
                key(Qt.Key_Return);require(ui.overlay==="facts","Full observation did not open");
                if(fixtureScenario!=="before")require(ui.checkDetail.detail.indexOf("Menu sample")>=0 && ui.checkDetail.detail.indexOf("59.8")>=0,"Menu figures or context lost");
                step=3;return;
            }
            if(step===3){capture(ui,"menu-note",4);return;}
            if(step===4){
                closeFacts(ui);if(fixtureScenario==="before"){stop();console.log("PERFORMANCE_THEME_PASS");Qt.exit(0);return;}
                require(ui.panelRows(0).filter(function(r){return r.label==="Sustained play";})[0].value==="Not checked","Menu certified sustained play");
                show(ui,"gameplay");select(ui,"Gameplay measurement");key(Qt.Key_Return);step=5;return;
            }
            if(step===5){
                require(ui.checkDetail.detail.indexOf("95th percentile 18.2 ms")>=0 && ui.checkDetail.detail.indexOf("Courtyard fight")>=0,"Scene/pacing lost");
                capture(ui,"gameplay-note",6);return;
            }
            if(step===6){
                var facts=find(ui,"detailFacts");require(facts,"Facts viewport missing");
                if(facts.contentHeight>facts.height+1){var before=facts.contentY;ui.runHint("readfacts");require(facts.contentY>before,"Long note cannot scroll");}
                step=7;return;
            }
            if(step===7){capture(ui,"gameplay-scrolled",8);return;}
            if(step===8){
                closeFacts(ui);key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id===original.id,"Back lost edition");
                show(ui,"conflict");select(ui,"Gameplay measurement");key(Qt.Key_Return);
                require(ui.checkDetail.detail.indexOf("figures withheld")>=0 && ui.checkDetail.detail.indexOf("59.8")<0,"Conflicting figures were chosen");step=9;return;
            }
            if(step===9){capture(ui,"conflict",10);return;}
            if(step===10){
                closeFacts(ui);show(ui,"zero");select(ui,"Gameplay measurement");key(Qt.Key_Return);
                require(ui.checkDetail.detail.indexOf("Average FPS · 0")>=0 && ui.checkDetail.detail.indexOf("Frame pacing · Not measured")>=0,"Unknown pacing became a fabricated zero");step=11;return;
            }
            if(step===11){capture(ui,"zero-unknown",12);return;}
            if(step===12){
                closeFacts(ui);show(ui,"invalid");select(ui,"Unreadable records");require(ui.panelRows(0)[selectedRow].value==="1","Invalid sample was silently accepted");step=13;return;
            }
            if(step===13){capture(ui,"invalid",14);return;}
            if(step===14){
                show(ui,"legacy");require(!ui.panelRows(0).some(function(r){return /measurement$/.test(r.label);}),"Legacy note invented metrics");
                key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id===original.id,"Legacy Back lost edition");
                stop();console.log("PERFORMANCE_THEME_PASS");Qt.exit(0);
            }
        }catch(error){stop();console.error("PERFORMANCE_THEME_FAIL "+error);Qt.exit(1);}}
    }
