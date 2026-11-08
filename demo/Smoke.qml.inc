    property string cloudScreenshotPath: ""
    property string screenshotSurface: "cloud"
    QtObject {
        id: syntheticCloud
        property var games: [{id:1,title:"Synthetic Adventure",system:"PlayStation",platform:"ps",bytes:2048,installed:false,supported:true,cover:""},{id:2,title:"Unavailable System",system:"Other",bytes:1024,installed:false,supported:false,reason:"This emulator is not connected yet.",cover:""}]
        property bool configured: true
        property bool busy: false
        property double progress: 0
        property string message: "Synthetic cloud; no network or games."
        property string called: ""
        property int catalogueVersion: 0
        property bool simulateAcceptedLaunch: false
        property bool launchChecking: false
        signal launchPrepared(string editionId,string title,string platform)
        signal launchAccepted(string editionId)
        property var storagePlan: ({spaceKnown:true,fits:true,remainingBytes:2048,freeBytes:1073741824,headroomBytes:134217728,shortfallBytes:0,reason:"Synthetic measured space"})
        function installPlan(id) {return storagePlan;}
        function refresh() { called="refresh"; }
        function cancel() { called="cancel"; busy=false; }
        function play(id) {
            called="play:"+id;
            if(simulateAcceptedLaunch) {
                var g=games.filter(function(g){return g.id===id;})[0];
                launchPrepared(g.editionId,g.title,g.platform==="ps"?"psx":g.platform);launchAccepted(g.editionId);
            }
        }
        function install(id) { called="install:"+id; }
        property bool removalAllowed: true
        property int removalGeneration: 1
        function removalPlan(id) {return {id:id,eligible:removalAllowed,bytesKnown:true,bytes:4096,fileCount:1,partial:false,token:removalAllowed?"fixture-"+removalGeneration+":"+id:"",reason:removalAllowed?"Synthetic idle verified; reviewed files only":"Runtime idle is unknown in this synthetic fixture"};}
        function cleanupPlan(id) {var c=removalPlan(9);c.title="Synthetic Arcade";c.system="SNES";c.cover="";return {candidates:[c]};}
        function removeDownload(id, token) {if(token === "fixture-"+removalGeneration+":"+id)called="remove:"+id;else message="Synthetic stale preview refused";}
    }
    Timer {
        interval: 1500; running: true; repeat: false
        function require(value, reason) { if (!value) throw new Error(reason); }
        function key(ui, value) { ui.handleKey({key:value, isAutoRepeat:false, accepted:false}); if(value===Qt.Key_Back)ui.handleKeyRelease({key:value,accepted:false}); }
        function afterHistoryRefresh(ui, done) {
            var id=window.api.allGames.get(0).extra["edition-id"];
            var first="2026-11-03T10:00:00Z", second="2026-11-04T10:00:00Z", dates={};
            window.api.gameFileLaunched(null);dates[id]=first;window.api.allGames.observedPlayDates=dates;
            Qt.callLater(function(){
                try {
                    require(ui.entryById[id].lastPlayedHere === Date.parse(first),"launch event did not refresh local history");
                    window.api.gameFileFinished(null);var next={};next[id]=second;window.api.allGames.observedPlayDates=next;
                    Qt.callLater(function(){
                        try {require(ui.entryById[id].lastPlayedHere === Date.parse(second),"return event did not refresh local history");done();}
                        catch(error){console.error("NOVA_DEMO_SMOKE_FAIL: "+error);Qt.exit(1);}
                    });
                } catch(error){console.error("NOVA_DEMO_SMOKE_FAIL: "+error);Qt.exit(1);}
            });
        }
        function checkRecorderLaunch(ui) {
            var original=window.deviceLibrary,order=[],staged=[];
            var recorder=Qt.createQmlObject('import QtQuick 2.15; QtObject { signal staged(string edition,string title,string system); function recordRomLaunch(edition,title,system) { staged(edition,title,system); } }',window);
            recorder.staged.connect(function(id,title,system){order.push("stage");staged=[id,title,system];});
            var entry={id:"synthetic:rom",title:"Synthetic ROM",systemId:"snes",route:"Synthetic route",launchable:true,game:{missing:false,launch:function(){order.push("launch");}}};
            window.deviceLibrary=recorder;ui.playEdition(entry);
            require(order.join(",") === "stage,launch" && staged.join(",") === "synthetic:rom,Synthetic ROM,snes","ROM identity not staged before native launch");
            ["androidapps","emulators"].forEach(function(system){
                order=[];entry.systemId=system;ui.playEdition(entry);require(order.join(",") === "launch","utility launch entered ROM recorder: "+system);
            });
            order=[];entry.id="steam:123";entry.systemId="pc";ui.playEdition(entry);require(order.join(",") === "launch","Steam launch entered ROM recorder");
            order=[];entry.id="synthetic:rom";entry.systemId="snes";entry.launchable=false;ui.playEdition(entry);require(order.length===0,"unconfigured ROM recorded or launched");
            entry.launchable=true;entry.game.missing=true;ui.playEdition(entry);require(order.length===0,"missing ROM recorded or launched");
            entry.game.missing=false;
            var absent=Qt.createQmlObject('import QtQuick 2.15; QtObject {}',window);
            window.deviceLibrary=absent;ui.playEdition(entry);require(order.join(",") === "launch","bridge without recorder blocked launch");
            order=[];window.deviceLibrary=null;ui.playEdition(entry);require(order.join(",") === "launch","absent bridge blocked launch");
            window.deviceLibrary=original;recorder.destroy();absent.destroy();ui.overlay="";
            console.log("NOVA_UI_REPAIR: recorder stages ROM identity before launch; absent/unsupported bridges launch normally; apps/Steam excluded");
        }
        function cloudFixture(installed,cover) {
            var scope=Array(65).join("a"),revision=Array(65).join("b");
            return {id:41,title:"Synthetic Cloud Adventure",system:"Super Nintendo",platform:"snes",bytes:524288,
                installed:installed,partial:false,supported:true,cover:cover || "",observedAt:"2026-11-06T00:00:00Z",
                editionId:"nova:cloud_"+scope+":41_"+revision,cloudKey:"cloud:"+scope+":41"};
        }
        function checkIntegratedCloud(ui) {
            var previousCloud=window.romCloud,previousBridge=window.deviceLibrary,previousGames=syntheticCloud.games;
            var previousPins=ui.pins,previousOpened=ui.cloudOpened,hadOpened=window.api.memory.has("cloudOpened");
            var previousStored=hadOpened?window.api.memory.get("cloudOpened"):null,previousReadable=ui.cloudHistoryReadable;
            var previousReturn=ui.cloudReturnOverlay,previousPanel=ui.cloudReturnPanel;
            var recorder=Qt.createQmlObject('import QtQuick 2.15; QtObject { property int stages:0; property int writes:0; property string edition:""; function read(q){return {};} function act(a){writes++;return {ok:false};} function recordRomLaunch(id,title,system){stages++;edition=id;} }',window);
            window.deviceLibrary=recorder;
            var g=cloudFixture(false,ui.rawEntries[0].art);
            syntheticCloud.catalogueVersion=1;syntheticCloud.games=[g];window.romCloud=syntheticCloud;
            ui.rebuildEverything();ui.clearFilters();ui.switchView("library");ui.zone="content";
            var at=ui.libraryEntries.map(function(e){return e.id;}).indexOf(g.editionId);
            require(at>=0,"cloud game missing from ordinary Library");ui.setLibIndex(at);
            syntheticCloud.busy=true;syntheticCloud.launchChecking=true;syntheticCloud.called="";
            ui.applicationActive(false);require(syntheticCloud.called==="cancel","background switch did not cancel a pending launch");
            syntheticCloud.busy=true;syntheticCloud.launchChecking=false;syntheticCloud.called="";
            ui.applicationActive(false);require(syntheticCloud.called==="","background switch cancelled a download");syntheticCloud.busy=false;
            require(ui.hints()[0].l==="Install","cloud game does not lead with Install");
            ui.play(ui.current);
            var panel=findItem(ui,"cloudLibrary");
            require(ui.overlay==="cloud" && panel.targetId===41 && panel.games.length===1,"Install lost the selected game or required Settings");
            panel.primary();require(syntheticCloud.called==="install:41","Install did not reach native preflight/download");
            require(!ui.cloudOpened[g.editionId],"download was recorded as a game opening");
            g=cloudFixture(true,g.cover);syntheticCloud.games=[g];ui.rebuildEverything();ui.closeOverlay();
            require(ui.overlay==="" && ui.view==="library" && ui.current.id===g.editionId,"Back lost the originating game");
            ui.openDetails();require(ui.detailActions()[0].l==="Play","installed cloud game does not lead with Play");
            require(!ui.detailActions().some(function(a){return a.a==="status";}),"cloud edition wrote to an unrelated progress service");
            ui.toggleKeep(ui.current);require(recorder.writes===0,"local cloud favourite queued an unknown service identity");
            syntheticCloud.simulateAcceptedLaunch=true;ui.playEdition(ui.current);
            require(recorder.stages===1 && recorder.edition===g.editionId,"verified cloud identity did not stage before the common Android launch boundary");
            require(ui.cloudOpened[g.editionId]>0 && window.api.memory.get("cloudOpened").opened[g.editionId]>0,"accepted cloud opening was not retained locally");
            ui.rebuildEverything();require(ui.homeEntries.some(function(e){return e.id===g.editionId;}),"accepted cloud opening missing from Home recents");
            syntheticCloud.simulateAcceptedLaunch=false;syntheticCloud.catalogueVersion=0;syntheticCloud.games=previousGames;
            window.romCloud=previousCloud;window.deviceLibrary=previousBridge;
            ui.pins=previousPins;window.api.memory.set("pins",previousPins);ui.cloudOpened=previousOpened;
            ui.cloudHistoryReadable=previousReadable;
            if(hadOpened)window.api.memory.set("cloudOpened",previousStored);else window.api.memory.unset("cloudOpened");
            ui.overlay="";ui.cloudReturnOverlay=previousReturn;ui.cloudReturnPanel=previousPanel;ui.rebuildEverything();
            require(!ui.rawEntries.some(function(e){return e.cloudId;}),"older bridge fabricated integrated cloud entries");
            recorder.destroy();console.log("NOVA_INTEGRATED_CLOUD_PASS: ordinary Library Install/Play, focused download/back, local favourites/recents and exact recorder identity; older bridge preserved");
        }
        function checkPhoneAudio(ui) {
            var previous=ui.rawEntries,launched=0;
            ui.overlay="";ui.switchView("apps");ui.zone="content";
            key(ui,Qt.Key_Y);require(ui.overlay==="phoneaudio","Apps has no controller route to phone audio");
            require(!ui.hints().some(function(h){return h.a==="panel";}),"missing receiver exposes a working launch");
            key(ui,Qt.Key_Escape);require(ui.overlay==="" && ui.view==="apps","phone audio Back left Apps");
            var app={};Object.keys(previous[0]).forEach(function(k){app[k]=previous[0][k];});
            app.id="demo:phone-audio";app.title="AirPlay Server";app.systemId="androidapps";app.appPackage="io.github.jqssun.airplay";app.launchable=true;
            app.game={missing:false,launch:function(){launched++;}};
            ui.rawEntries=previous.concat([app]);ui.rebuildPresentations();
            ui.openPanel("settings",0);var index=ui.panelRows(0).map(function(r){return r.label;}).indexOf("Phone audio");
            require(index>=0,"configured receiver has no Settings route");ui.panelActivate(index,1);
            require(ui.overlay==="phoneaudio" && ui.hints()[0].l==="Open receiver","phone receiver primary action missing");
            ui.panelActivate(0,1);require(launched===1,"phone receiver did not use the configured app route");
            key(ui,Qt.Key_Escape);require(ui.overlay==="settings" && ui.panelIndex===index,"phone audio Back lost Settings focus");
            ui.rawEntries=previous;ui.rebuildPresentations();ui.overlay="";
            console.log("NOVA_PHONE_AUDIO_PASS: Apps/Settings open exact configured receiver and preserve Back; absence never pretends audio is available");
        }
        function afterUIRepairs(ui, done) {
            // Run after layout turns: source arithmetic cannot prove focus containment.
            var bridge=Qt.createQmlObject('import QtQuick 2.15; QtObject { function read(query) { return {}; } function act(action) { return {ok:false,message:"Synthetic UI check"}; } }',window);
            window.deviceLibrary=bridge; ui.refreshDevice();
            var savedEntries=ui.rawEntries, app={};
            Object.keys(savedEntries[0]).forEach(function(k){app[k]=savedEntries[0][k];});
            app.id="demo:emulator";app.title="Synthetic emulator";app.systemId="emulators";
            ui.rawEntries=savedEntries.concat([app]);ui.rebuildPresentations();ui.rebuildLibrary("");
            require(ui.appsEntries.some(function(e){return e.id===app.id;}),"emulator shortcut disappeared from Apps");
            require(!ui.libraryEntries.some(function(e){return e.id===app.id;}),"emulator shortcut mixed into game discovery");
            ui.switchView("apps");ui.setAppIndex(0);ui.openDetails();
            require(ui.detailActions().some(function(a){return a.a==="facts";}) && !ui.detailActions().some(function(a){return a.a==="checks";}),"app Details uses game actions");
            var steam={}, deck={};
            Object.keys(savedEntries[0]).forEach(function(k){steam[k]=savedEntries[0][k];deck[k]=savedEntries[0][k];});
            steam.id="steam:480";steam.systemId="pc";steam.launchable=false;
            deck.id="demo:droiddeck";deck.title="DroidDeck";deck.systemId="androidapps";deck.launchable=true;
            ui.rawEntries=[steam,deck];ui.rebuildPresentations();ui.rebuildLibrary("");ui.switchView("library");ui.setLibIndex(0);ui.openDetails();
            require(ui.detailActions()[0].a==="droiddeck","unavailable Steam game does not lead with its configured setup handoff");
            deck.launchable=false;
            require(!ui.detailActions().some(function(a){return a.a==="droiddeck";}),"unconfigured DroidDeck route fabricated an action");
            ui.rawEntries=savedEntries;ui.rebuildPresentations();ui.rebuildLibrary("");
            ui.overlay="";ui.switchView("library");ui.zone="content";ui.setLibIndex(0);
            ui.current.launchable=false;
            require(ui.hints().filter(function(h){return h.l==="Details";}).length===1,"nonlaunchable game repeats Details hints");
            ui.current.status="playing";ui.current.installations={nova:{state:"absent",scopeComplete:true,source:"Synthetic scan",observedAt:"2026-11-05"},legion:{state:"installed",source:"Synthetic scan",observedAt:"2026-11-05"}};
            require(ui.quietLine(ui.current,0)==="No launch route here  ·  Playing","Library caption repeats badge or loses Playing");
            var homeCaptionEntry={launchable:true,status:"unknown",route:"Synthetic local shortcut",installations:{}};
            ui.switchView("home");require(ui.quietLine(homeCaptionEntry,0)==="Synthetic local shortcut","Home leads with an unknown install observation");
            var keptThreads=ui.threads;
            ui.threads=[{id:"demo:return",name:"Synthetic collection",origin:"kept",entries:[ui.rawEntries[0]]}];ui.threadIndex=0;ui.memberIndex=0;
            ui.switchView("threads");ui.threadZone="members";
            require(ui.hints().some(function(h){return h.a==="threadback" && h.l==="Collections";}),"Collections members has no Back hint");
            ui.runHint("threadback");require(ui.threadZone==="list","Collections Back hint did not reverse");
            ui.threads=keptThreads;ui.switchView("library");ui.setLibIndex(0);
            require(!ui.detailLines(app,0).some(function(line){return /install:|Lifetime|Session length/.test(line.t);}),"emulator Info includes game-only observations");
            ui.current.launchable=true;ui.openDetails();ui.detailAction=0;
            var railWidth=-1, actions=0, panel=0, row=0, phase="actions", factsLayoutTurns=0, savedAppearance=ui.appearance;
            require(ui.detailActions()[0].a==="play","launchable game no longer starts on Play");
            var panels=["settings","appearance","filters","storage","controls","refresh","checks","guide","about","session","status","threadpick","discs"];
            var timer=Qt.createQmlObject('import QtQuick 2.15; Timer { interval:40; repeat:true }',window);
            timer.triggered.connect(function(){try {
                var hints=findItem(ui,"buttonHints");
                require(hints.y+hints.height <= ui.usableHeight-ui.px(20),"hints enter reserved edge");
                if(phase === "actions") {
                    var list=findItem(ui,"detailActions"),item=list.currentItem;
                    require(ui.detailActions().length === 9,"editable fixture lost an action");
                    if(railWidth<0)railWidth=list.width;
                    require(Math.abs(list.width-railWidth)<.01,"Details rail changes width with focus");
                    require(item && item.opacity === 1 && item.x-list.contentX>=-1 && item.x-list.contentX+item.width<=list.width+1,"Details action clipped at "+ui.detailAction);
                    if(++actions<9){key(ui,Qt.Key_Right);return;}
                    console.log("NOVA_UI_REPAIR: all 9 Details actions contained; stable width "+railWidth);
                    ui.openPanel(panels[panel],0);phase="panels";return;
                }
                if(phase === "panels") {
                    var list=findItem(ui,"panelList"), explanation=findItem(ui,"panelExplanation"),item=list.currentItem;
                    require(item && item.y-list.contentY>=-1 && item.y-list.contentY+item.height<=list.height+1,"selected "+ui.overlay+" row clipped: "+row);
                    require(explanation.y+explanation.height<=hints.y-ui.px(16),ui.overlay+" explanation overlaps hints");
                    require(Math.abs(list.height/item.height-Math.round(list.height/item.height))<.01,ui.overlay+" has partial rows");
                    if(++row<ui.panelRows(0).length){key(ui,Qt.Key_Down);return;}
                    console.log("NOVA_UI_REPAIR: "+ui.overlay+" all "+row+" focus rows clear footer");
                    row=0;
                    if(++panel<panels.length){
                        if(panels[panel] === "discs")ui.discTarget={discMembers:ui.rawEntries.slice(0,2)};
                        ui.openPanel(panels[panel],0);return;
                    }
                    ui.closeOverlay();ui.overlay="";ui.switchView("consoles");phase="consoles";return;
                }
                if(phase === "consoles") {
                    var grid=findItem(ui,"consoleGrid");
                    require(Math.abs(grid.height/grid.cellHeight-Math.round(grid.height/grid.cellHeight))<.01,"console viewport slices rows");
                    if(ui.width === 1280 && ui.height === 960 && ui.bottomInset === 48)require(grid.height>=3*grid.cellHeight,"device profile loses third console row");
                    ui.switchView("library");ui.setLibIndex(0);ui.zone="content";
                    ui.current.installations={nova:{state:"absent",scopeComplete:true,source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z"}};
                    ui.current.conflict=true;ui.current.status="playing";ui.current.checkpoint="Synthetic checkpoint";
                    var summary=ui.wideSummaryLines(ui.current,0);
                    require(summary.length<=4 && summary[0].t === "Not on Nova" && summary[1].t.indexOf("Progress conflict")===0,"wide summary hides absence or conflict");
                    ui.current.installations={};
                    require(ui.wideSummaryLines(ui.current,0)[0].t === "Install status not checked","wide summary invents installation");
                    var states=Qt.createComponent("../theme/DeviceStates.qml");
                    ["absent","partial","installed"].forEach(function(state){
                        var entry={installations:{nova:{state:state,scopeComplete:true,source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z",offline:false}}};
                        var block=states.createObject(ui,{entry:entry,visible:false});
                        var text=allText(block).join(" ");
                        require(text.indexOf("Install checked")!==-1 && text.indexOf("Install seen")===-1,"installation date mislabels "+state);
                        if(state === "absent")require(text.indexOf("Not installed")!==-1,"absence displayed as installed");
                        if(state === "partial")require(text.indexOf("Incomplete")!==-1,"partial displayed as installed");
                        block.destroy();
                    });
                    var offline=states.createObject(ui,{entry:{installations:{nova:{state:"installed",source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z",offline:true}}},visible:false});
                    require(allText(offline).join(" ").indexOf("Offline check")!==-1,"offline observation loses qualification");offline.destroy();
                    ui.openDetails();ui.current.checkpoint=new Array(180).join("Long synthetic note. ");ui.personalRev++;ui.overlay="facts";phase="facts";return;
                }
                if(phase === "facts") {
                    var facts=findItem(ui,"detailFacts");
                    // Wrapped text can need several polish turns under concurrent host load.
                    if(facts.contentHeight<=facts.height && ++factsLayoutTurns<25)return;
                    require(facts.contentHeight>facts.height && ui.hints().some(function(h){return h.a === "readfacts";}),"overflowing Info has no Read cue; content="+facts.contentHeight+" viewport="+facts.height);
                    ui.runHint("readfacts");require(facts.contentY>0,"Read hint does not scroll Info");
                    ui.rawEntries=ui.rawEntries.slice(0,2).map(function(e,i){
                        var member={};Object.keys(e).forEach(function(k){member[k]=e[k];});
                        member.discSetId="synthetic-disc-set";member.discSetName="Synthetic two-disc edition with a deliberately long selected title for caption coverage";member.discNumber=i+1;member.systemId="snes";member.launchable=true;
                        member.route="Synthetic long emulator route with configured local controls";member.status="playing";member.minutes="123h 45m";return member;
                    });
                    ui.setAppearance("time",true);
                    ui.rebuildPresentations();ui.rebuildLibrary("");ui.fromConsole=true;ui.switchView("library");ui.zone="content";ui.setLibIndex(0);phase="discFooter";return;
                }
                if(phase === "discFooter") {
                    var primary=findItem(ui,"primaryHints"),pager=findItem(ui,"pageHints");
                    require(primary.width<=primary.parent.width,"disc primary hints exceed viewport");
                    require(!pager.visible || primary.x+primary.width+ui.px(24)<=pager.x,"disc footer collides with page hints");
                    require(ui.hints().some(function(h){return h.a === "libraryback" && h.l === "Consoles";}),"disc footer loses reverse path");
                    require(ui.detailActions()[0].a==="play" && ui.detailActions()[0].l==="Choose disc","disc set no longer starts on Choose disc");
                    if(!ui.wide) {
                        var caption=findItem(ui,"libraryCaption"),quiet=findItem(ui,"libraryQuietLine");
                        require(quiet.text.indexOf("Disc ")>=0 && quiet.text.indexOf("Playing")>=0 && quiet.text.indexOf("123h 45m")>=0,"caption lost disc, status or optional time facts");
                        require(quiet.lineCount>1 && !quiet.truncated && quiet.contentWidth<=quiet.width+1,"long caption still elides or overflows");
                        require(caption.y+caption.height<=hints.y-ui.px(20),"wrapped caption overlaps footer");
                        require(caption.y>=ui.px(156),"caption exhausts cover area");
                    }
                    console.log("NOVA_UI_REPAIR: disc/Consoles primary footer contained; optional pager visible="+pager.visible);
                    timer.stop();timer.destroy();window.deviceLibrary=null;bridge.destroy();ui.appearance=savedAppearance;ui.discTarget=null;ui.fromConsole=false;ui.consoleFilter="";ui.overlay="";ui.rebuildEverything();done();
                }
            } catch(error){timer.stop();console.error("NOVA_DEMO_SMOKE_FAIL: "+error);Qt.exit(1);}});
            timer.start();
        }
        function allText(item) {
            var out=item.text !== undefined ? [String(item.text)] : [],children=item.children || [];
            for(var i=0;i<children.length;i++)out=out.concat(allText(children[i]));return out;
        }
        function findItem(item, name) {
            if (item.objectName === name) return item;
            var children=item.children || [];
            for (var i=0;i<children.length;i++) {var match=findItem(children[i],name);if(match)return match;}
            return null;
        }
        function pendingArtwork(item) {
            if(item.objectName === "coverArt" && item.loading)return true;
            var children=item.children || [];
            for(var i=0;i<children.length;i++)if(pendingArtwork(children[i]))return true;
            return false;
        }
        function checkRasterArtwork(item) {
            if(item.objectName === "coverArt" && item.entry && /\/art\/[^/]+\.png$/.test(item.entry.art))
                require(item.loaded && Math.abs(item.ratio-.75)<.001,"generated cover did not render at its natural shape");
            var children=item.children || [];
            for(var i=0;i<children.length;i++)checkRasterArtwork(children[i]);
        }
        function afterArtwork(ui, done) {
            var timer=Qt.createQmlObject('import QtQuick 2.15; Timer { interval:20; repeat:true; property int attempts:0 }',window);
            timer.triggered.connect(function(){
                if(pendingArtwork(ui) && ++timer.attempts<50)return;
                timer.stop();
                try {require(!pendingArtwork(ui),"artwork never settled");checkRasterArtwork(ui);done();}
                catch(error){console.error("NOVA_DEMO_SMOKE_FAIL: "+error);Qt.exit(1);}
                timer.destroy();
            });
            timer.start();
        }
        onTriggered: {
            try {
                require(themeLoader.status === Loader.Ready, "theme loader failed");
                var ui=themeLoader.item;
                checkRecorderLaunch(ui);
                checkIntegratedCloud(ui);
                checkPhoneAudio(ui);
                var artComponent=Qt.createComponent("../theme/ArtView.qml");
                require(artComponent.status === Component.Ready,"art component failed");
                var pendingArt=artComponent.createObject(ui,{width:200,height:300,opacity:0,entry:{title:"Pending artwork fixture",art:"http://127.0.0.1:9/synthetic-unavailable.png",launchable:false}});
                require(pendingArt && !pendingArt.loaded && findItem(pendingArt,"artFallback").visible,"pending artwork left a blank frame");
                pendingArt.destroy();
                require(ui.rawEntries.length === 4, "synthetic catalogue mismatch");
                ui.switchView("home");
                key(ui,Qt.Key_Right); key(ui,Qt.Key_Left);
                var pinCount=ui.pins.length;
                key(ui,Qt.Key_Y);
                require(ui.pins.length !== pinCount, "Y did not toggle keep");
                key(ui,Qt.Key_X);
                require(ui.overlay === "details", "X did not open details");
                var infoIndex=ui.detailActions().map(function(a){return a.a;}).indexOf("facts");
                require(infoIndex !== -1, "Info action missing");
                require(infoIndex === ui.detailActions().map(function(a){return a.a;}).indexOf("checks")+1,"Info is buried after editing actions");
                ui.current.novaGameplayNote="Menus worked; gameplay crashed";ui.current.novaGameplaySource="Synthetic audit";ui.current.novaGameplayObservedAt="2026-11-05";
                require(ui.overviewLines(ui.current,0).some(function(line){return line.t.indexOf("Menus worked; gameplay crashed")!==-1;}),"overview hides check result");
                ui.current.novaGameplayNote="";ui.current.novaGameplaySource="";ui.current.novaGameplayObservedAt="";
                ui.runDetailAction(infoIndex);
                require(ui.overlay === "facts", "Info did not open");
                key(ui,Qt.Key_Escape);
                require(ui.overlay === "details", "Info did not return to details");
                var checksIndex=ui.detailActions().map(function(a){return a.a;}).indexOf("checks");
                require(checksIndex !== -1, "Checks action missing");
                ui.runDetailAction(checksIndex);
                require(ui.overlay === "checks" && ui.panelRows(0)[1].value === "Not checked", "empty Checks invented evidence");
                key(ui,Qt.Key_Escape);
                require(ui.overlay === "details", "Checks did not return to details");
                var originalReceipts=ui.current.compatibilityReceipts, originalRecipe=ui.current.compatibilityRecipeId;
                var checkFixture=[{schemaVersion:1,editionId:ui.current.id,
                    recipe:{id:"fixture.v1",device:"Synthetic handheld",runtime:"Fixture emulator",version:"1.0",core:"Fixture core",driver:"Fixture driver",display:"Fit 4:3",input:"Fixture pad",settings:"Default synthetic settings"},
                    checks:[{stage:"menus",result:"pass",observedAt:"2026-11-03T10:00:00Z",method:"injected",source:"Synthetic QA",note:"Options opened and returned; no game started"}]}];
                ui.current.compatibilityReceipts=JSON.stringify(checkFixture);ui.current.compatibilityRecipeId="fixture.v1";
                ui.runDetailAction(checksIndex);
                key(ui,Qt.Key_Down);key(ui,Qt.Key_Down);
                require(ui.panelRows(0)[ui.panelIndex].label === "Menus" && ui.panelRows(0)[ui.panelIndex].value === "Passed in check", "menu evidence missing");
                require(ui.panelFooter(0).indexOf("injected") !== -1, "evidence method hidden");
                key(ui,Qt.Key_Return);
                require(ui.overlay === "facts" && ui.checkDetail.label === "Menus", "full check note did not open");
                key(ui,Qt.Key_Down);key(ui,Qt.Key_Escape);
                require(ui.overlay === "checks" && ui.panelIndex === 2 && ui.checkDetail === null, "full note did not return to selected check");
                key(ui,Qt.Key_Down);
                require(ui.panelRows(0)[ui.panelIndex].value === "Not checked", "menu check promoted to gameplay");
                key(ui,Qt.Key_Escape);
                ui.current.compatibilityRecipeId="different";ui.runDetailAction(checksIndex);
                require(ui.panelRows(0)[2].value === "Not checked", "old setup evidence promoted");
                key(ui,Qt.Key_Escape);
                ui.current.compatibilityReceipts=originalReceipts;ui.current.compatibilityRecipeId=originalRecipe;
                var guideIndex=ui.detailActions().map(function(a){return a.a;}).indexOf("guide");
                require(guideIndex !== -1, "unknown runtime has no Controls fallback");
                ui.runDetailAction(guideIndex);
                require(ui.overlay === "guide" && ui.panelRows(0)[0].value === "Not checked", "unknown runtime guide invented a mapping");
                key(ui,Qt.Key_Escape);
                require(ui.overlay === "details", "Controls did not return to details");
                var originalRoute=ui.current.route, originalProfile=ui.current.sessionProfile;
                ui.current.route="HakuX 1.2";
                ui.runDetailAction(guideIndex);
                require(ui.panelRows(0)[0].label === "HakuX", "legacy HakuX did not get its menu fallback");
                key(ui,Qt.Key_Escape);
                ui.current.sessionProfile="hakux-nova-v1";
                ui.runDetailAction(guideIndex);
                require(ui.panelRows(0)[0].label === "HakuX · Nova shortcuts", "explicit shortcut profile missing");
                key(ui,Qt.Key_Down); key(ui,Qt.Key_Down);
                require(ui.panelRows(0)[ui.panelIndex].value === "Select + R1", "guide navigation lost the save row");
                require(ui.panelFooter(0).indexOf("confirmation") !== -1, "save replacement detail missing");
                key(ui,Qt.Key_Escape);
                ui.current.route=originalRoute; ui.current.sessionProfile=originalProfile;
                var originals=ui.rawEntries;
                ui.rawEntries=originals.concat([{systemId:"androidapps",capacity:{id:"internal-data",total:100,used:90,free:5,observedAt:"2026-10-14T08:00:00Z",source:"Synthetic df"}}]);
                ui.openPanel("storage",0);
                require(ui.overlay === "storage", "Storage did not open");
                require(ui.storageRows()[0].label === "Known ROM files", "Storage ROM summary missing");
                ui.rawEntries=originals; ui.overlay="details";
                key(ui,Qt.Key_Escape);
                require(ui.overlay === "", "Escape did not close details");
                key(ui,Qt.Key_Return);
                require(!ui.current.launchable, "demo became launchable");
                require(ui.overlay === "details", "unavailable Enter did not explain route");
                key(ui,Qt.Key_Escape);
                key(ui,Qt.Key_PageDown);
                require(ui.view === "library", "PageDown did not switch views");
                key(ui,Qt.Key_Down); key(ui,Qt.Key_Up); key(ui,Qt.Key_Right); key(ui,Qt.Key_Left);
                ui.zone="content";
                key(ui,Qt.Key_Home); key(ui,Qt.Key_End); key(ui,Qt.Key_Return);
                require(ui.overlay === "details", "Library unavailable Enter failed");
                key(ui,Qt.Key_Escape);
                key(ui,Qt.Key_X);
                require(ui.overlay === "details", "Library X failed");
                key(ui,Qt.Key_Escape);ui.setLibIndex(0);key(ui,Qt.Key_Up);key(ui,Qt.Key_Y);
                require(ui.overlay === "filters", "filter panel did not open");
                var labelId=ui.libraryEntries[0].id;
                ui.overlay="";ui.zone="content";ui.setLibIndex(0);ui.openDetails();
                var sessionAction=ui.detailActions().map(function(a){return a.a;}).indexOf("session");
                require(sessionAction>=0,"session chooser unavailable without new permissions");
                ui.runDetailAction(sessionAction);require(ui.overlay === "session","session chooser did not open");
                key(ui,Qt.Key_Down);key(ui,Qt.Key_Return);
                require(ui.overlay === "details" && ui.entryById[labelId].sessionWindow === "five","session edit failed");
                ui.runDetailAction(sessionAction);key(ui,Qt.Key_Back);
                require(ui.overlay === "details","native Back did not dismiss session chooser");
                ui.openPanel("filters",6);key(ui,Qt.Key_Right);
                require(ui.filters.session === "five" && ui.libraryEntries.length === 1,"session shelf did not filter");
                var sessionComponent=Qt.createComponent("../theme/theme.qml");
                var sessionReopen=sessionComponent.createObject(window,{width:window.width,height:window.height,visible:false});
                require(sessionReopen && sessionReopen.filters.session === "five" && sessionReopen.libraryEntries.length === 1 && sessionReopen.entryById[labelId].sessionWindow === "five","session preferences lost on theme recreation");
                sessionReopen.destroy();
                var knownStore=window.api.memory.get("sessionWindows"),futureStore={version:2,labels:{"demo:orbit":"five"}};
                window.api.memory.set("sessionWindows",futureStore);
                var futureTheme=sessionComponent.createObject(window,{width:window.width,height:window.height,visible:false});
                require(futureTheme && futureTheme.sessions === null,"future session store was silently replaced");
                futureTheme.setSession("five");require(window.api.memory.get("sessionWindows").version === 2,"unreadable labels were overwritten");
                futureTheme.setFilter("session","unknown");require(futureTheme.libraryEntries.length === 0,"unreadable labels presented as unlabelled");
                futureTheme.destroy();window.api.memory.set("sessionWindows",knownStore);
                ui.overlay="";ui.setLibIndex(0);ui.openDetails();ui.runDetailAction(sessionAction);ui.panelActivate(0,1);
                require(ui.libraryEntries.length === 0 && ui.overlay === "","cleared filtered label left Details pointing at a different game");
                ui.clearFilters();ui.setLibIndex(0);ui.openPanel("filters",0);
                // Exercise actual metadata ingestion, not just a precomputed filter flag.
                var aspectGame=window.api.allGames.get(0), aspectExtra=aspectGame.extra;
                var aspectRecord={schemaVersion:1,editionId:aspectExtra["edition-id"],recipe:{id:"fixture.aspect.v1",device:"Synthetic handheld",runtime:"Fixture emulator",version:"1.0",core:"Fixture core",driver:"Fixture driver",display:"Native 4:3 fixture",input:"Fixture pad",settings:"Synthetic QA only"},checks:[{stage:"native-4-3",result:"pass",observedAt:"2026-11-03T10:00:00Z",method:"injected",source:"Synthetic QA",note:"Not a real game or hardware observation"}]};
                aspectExtra["original-aspect"]="4:3";aspectExtra["original-aspect-source"]="Invented fixture manual";
                aspectExtra["compatibility-recipe-id"]="fixture.aspect.v1";aspectExtra["compatibility-receipts"]=JSON.stringify([aspectRecord]);
                ui.rebuildEverything();ui.panelIndex=5;
                key(ui,Qt.Key_Right);require(ui.filters.aspect === "original-4-3" && ui.libraryEntries.length === 1,"original aspect filtering failed");
                key(ui,Qt.Key_Right);require(ui.filters.aspect === "native-4-3" && ui.libraryEntries.length === 1,"native aspect filtering failed");
                var component=Qt.createComponent("../theme/theme.qml");
                require(component.status === Component.Ready,"theme reopen component failed");
                var reopened=component.createObject(window,{width:window.width,height:window.height,visible:false});
                require(reopened && reopened.filters.aspect === "native-4-3" && reopened.libraryEntries.length === 1,"aspect preference did not survive theme recreation");
                reopened.destroy();
                ui.panelIndex=7;key(ui,Qt.Key_Right);key(ui,Qt.Key_Left);
                require(ui.filters.aspect === "native-4-3","directional input activated Clear");
                key(ui,Qt.Key_Return);require(!ui.filtering,"explicit Clear did not reset filters");
                ui.panelIndex=5;key(ui,Qt.Key_Right);key(ui,Qt.Key_Right);
                key(ui,Qt.Key_Right);require(ui.libraryEntries.length === 0,"stretch-only filter invented a match");
                key(ui,Qt.Key_Left);key(ui,Qt.Key_Escape);require(ui.overlay === "" && ui.filters.aspect === "native-4-3","Done lost aspect filter");
                key(ui,Qt.Key_Down);key(ui,Qt.Key_X);require(ui.overlay === "details","filtered game details did not open");
                ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("facts"));
                require(ui.overlay === "facts","filtered game Info did not open");
                var aspectInfo=ui.detailLines(ui.current,0).map(function(r){return r.t;}).join(" ");
                require(aspectInfo.indexOf("Original aspect: 4:3") !== -1 && aspectInfo.indexOf("Native 4:3 tested") !== -1,"Info lost original versus native evidence");
                key(ui,Qt.Key_Escape);key(ui,Qt.Key_Escape);ui.setLibIndex(0);key(ui,Qt.Key_Up);
                key(ui,Qt.Key_Y);key(ui,Qt.Key_X);require(!ui.filtering && ui.libraryEntries.length === 4,"Clear did not remove aspect filter");
                key(ui,Qt.Key_Escape);
                delete aspectExtra["original-aspect"];delete aspectExtra["original-aspect-source"];
                delete aspectExtra["compatibility-recipe-id"];delete aspectExtra["compatibility-receipts"];
                ui.rebuildEverything();
                key(ui,Qt.Key_PageDown);
                require(ui.view === "consoles", "Consoles view failed");
                require(ui.consoleColumns === (ui.width/ui.usableHeight >= 1.5 ? 3 : 2), "console columns ignore the viewport");
                ui.zone="content";ui.selectConsole(0);
                key(ui,Qt.Key_Down);
                require(ui.consoleIndex === Math.min(ui.consoleSystems.length-1,ui.consoleColumns),"console Down uses the wrong column stride");
                key(ui,Qt.Key_Up);
                require(ui.consoleSystems.length > ui.consoleColumns ? ui.consoleIndex === 0 : ui.zone === "nav", "console Up lost its column or top-row navigation");
                ui.zone="content";ui.selectConsole(0);
                key(ui,Qt.Key_Right); key(ui,Qt.Key_Left); key(ui,Qt.Key_Down); key(ui,Qt.Key_Up);
                ui.zone="content";
                var selectedConsole=ui.consoleIndex;
                key(ui,Qt.Key_Return);
                require(ui.view === "library" && ui.filters.system !== "", "console filtering failed");
                require(ui.hints().some(function(h){return h.a === "libraryback" && h.l === "Consoles";}),"console Library has no reverse-path hint");
                ui.runHint("libraryback");
                require(ui.view === "consoles" && ui.consoleIndex === selectedConsole,"Library Back hint lost its console context");
                ui.browseConsole();
                ui.setFilter("aspect","unverified");
                key(ui,Qt.Key_Escape);
                require(ui.view === "consoles", "console return failed");
                require(ui.consoleIndex === selectedConsole,"console return lost the selected system");
                key(ui,Qt.Key_PageUp);
                require(ui.view === "library", "PageUp failed");
                require(ui.filters.system === "" && ui.filters.aspect === "unverified","leaving console lost the independent aspect filter");
                ui.clearFilters();
                ui.openPanel("settings",0);key(ui,Qt.Key_Return);
                require(ui.overlay === "appearance" && ui.panelRows(0).length === 4,"Appearance motion setting missing");
                ui.panelIndex=3;var previousMotion=ui.reducedMotion;
                key(ui,Qt.Key_Right);require(ui.reducedMotion !== previousMotion,"reduced motion did not change");
                var appearanceReopen=component.createObject(window,{width:window.width,height:window.height,visible:false});
                require(appearanceReopen && appearanceReopen.reducedMotion === ui.reducedMotion,"reduced motion did not survive theme recreation");
                appearanceReopen.destroy();key(ui,Qt.Key_Left);
                require(ui.reducedMotion === previousMotion,"motion setting could not be reversed");
                key(ui,Qt.Key_Escape);require(ui.overlay === "settings" && ui.panelIndex === 0,"Appearance Back lost Settings focus");
                ui.panelIndex=7;key(ui,Qt.Key_Return);
                require(ui.overlay === "about" && ui.panelRows(0)[1].label === "Pegasus Frontend","About credits missing");
                key(ui,Qt.Key_Down);key(ui,Qt.Key_Escape);
                require(ui.overlay === "settings" && ui.panelIndex === 7,"About Back lost Settings focus");
                key(ui,Qt.Key_Escape);
                // Android Back must consume both edges; a release alone cannot
                // close a different panel after focus or overlay changes.
                ui.openDetails();
                var backPress={key:Qt.Key_Back,isAutoRepeat:false,accepted:false};
                ui.handleKey(backPress);require(backPress.accepted && ui.overlay === "details","Back press escaped or acted before release");
                var backRelease={key:Qt.Key_Back,accepted:false};ui.handleKeyRelease(backRelease);
                require(backRelease.accepted && ui.overlay === "","Back release did not close Details");
                ui.openPanel("settings",0);key(ui,Qt.Key_Back);require(ui.overlay === "","Back did not close Settings");
                ui.openDetails();ui.handleKey(backPress);ui.overlay="settings";ui.handleKeyRelease(backRelease);
                require(ui.overlay === "settings","Back release closed a different panel");
                ui.overlay="";ui.switchView("home");key(ui,Qt.Key_Back);require(ui.view === "home" && ui.overlay === "","Back escaped Home");
                var backThreads=ui.threads, backThreadIndex=ui.threadIndex, backMemberIndex=ui.memberIndex;
                ui.threads=[{id:"demo:first",name:"First collection",entries:[ui.rawEntries[0]]},{id:"demo:second",name:"Second collection",entries:ui.rawEntries.slice(0,2)}];
                ui.switchView("threads");ui.threadIndex=1;ui.memberIndex=1;ui.threadZone="members";
                ui.handleKey(backPress);require(ui.view === "threads" && ui.threadZone === "members","native Back acted on member press");
                ui.handleKeyRelease(backRelease);require(backRelease.accepted && ui.view === "threads" && ui.threadZone === "list" && ui.threadIndex===1 && ui.memberIndex===1,"native Back skipped Collections list or lost selection");
                ui.threadZone="members";ui.runHint("threadback");require(ui.threadZone === "list" && ui.threadIndex===1 && ui.memberIndex===1,"touch Back lost collection selection");
                ui.threadZone="members";key(ui,Qt.Key_Escape);require(ui.threadZone === "list" && ui.threadIndex===1 && ui.memberIndex===1,"mapped Back lost collection selection");
                ui.threads=backThreads;ui.threadIndex=backThreadIndex;ui.memberIndex=backMemberIndex;
                ["home","library","consoles","threads"].forEach(function(destination){
                    ui.switchView(destination);ui.switchView("apps");var libraryIndex=ui.libIndex;
                    ui.handleKey(backPress);require(ui.view === "apps","native Apps Back acted before release");
                    ui.handleKeyRelease(backRelease);require(ui.view === destination && ui.libIndex===libraryIndex,"native Apps Back lost recorded return destination");
                    ui.switchView("apps");ui.runHint("appsback");require(ui.view === destination,"touch Apps Back lost destination");
                    ui.switchView("apps");key(ui,Qt.Key_Escape);require(ui.view === destination,"mapped Apps Back lost destination");
                });
                ui.switchView("library");ui.fromConsole=true;key(ui,Qt.Key_Back);require(ui.view === "consoles","native Library Back lost console destination");
                key(ui,Qt.Key_Back);require(ui.view === "home","stale console context trapped native Back");ui.fromConsole=false;
                ui.switchView("apps");ui.handleKey(backPress);ui.switchView("library");ui.handleKeyRelease(backRelease);require(ui.view === "library","Back release navigated a different view");
                ui.zone="nav";key(ui,Qt.Key_Back);require(ui.view === "library" && ui.zone === "search","native nav Back skipped search");
                key(ui,Qt.Key_Back);require(ui.view === "library" && ui.zone === "content","native search Back skipped content");
                ui.switchView("home");key(ui,Qt.Key_Back);require(ui.view === "home","native Home Back escaped");
                console.log("NOVA_ANDROID_BACK_PASS: Collections and Apps preserve selection/destinations across mapped, hint and native press/release; view/overlay guards; nav/search, console and Home");
                // Cloud input uses the same real component and root key router.
                ui.openPanel("settings", 6);
                require(ui.panelRows(0)[6].value==="Not connected","absent Cloud bridge advertises downloads");
                ui.panelActivate(6, 1);
                require(ui.overlay === "cloud", "cloud shelf did not open");
                key(ui, Qt.Key_Escape);
                require(ui.overlay === "settings" && ui.panelIndex === 6, "cloud shelf return lost Settings focus");
                window.romCloud=syntheticCloud;
                ui.panelActivate(6,1);
                var cloudSetupUi=findItem(ui,"cloudLibrary");
                var setupGames=syntheticCloud.games;syntheticCloud.configured=false;syntheticCloud.games=[];syntheticCloud.called="";
                require(cloudSetupUi.setupRequired,"unconfigured bridge did not expose setup state");
                key(ui,Qt.Key_X);require(syntheticCloud.called === "","unconfigured Refresh still reached bridge");
                require(!findItem(cloudSetupUi,"cloudHint_refresh").visible,"unconfigured Refresh hint remained enabled");
                require(findItem(cloudSetupUi,"cloudNotice").text==="","unconfigured Cloud repeats setup in its footer");
                syntheticCloud.games=setupGames;cloudSetupUi.primary();require(syntheticCloud.called==="","unconfigured primary reached bridge");syntheticCloud.games=[];
                require(cloudSetupUi.setupText.indexOf("restart Library")!==-1,"cloud setup omitted restart boundary");
                syntheticCloud.configured=true;syntheticCloud.games=setupGames;
                require(findItem(cloudSetupUi,"coverArt").entry.systemId === "ps","native cloud platform identity lost in cover fallback");
                syntheticCloud.storagePlan=({spaceKnown:true,fits:false,remainingBytes:2048,freeBytes:0,headroomBytes:134217728,shortfallBytes:134219776,reason:"Not enough synthetic space"});
                syntheticCloud.called="";key(ui,Qt.Key_Return);
                require(syntheticCloud.called === "", "cloud download ignored measured insufficient space");
                syntheticCloud.storagePlan=({spaceKnown:true,fits:true,remainingBytes:2048,freeBytes:1073741824,headroomBytes:134217728,shortfallBytes:0,reason:"Synthetic measured space"});
                key(ui,Qt.Key_Return);require(syntheticCloud.called === "install:1", "cloud Download did not reach native bridge");
                var cloudUi=findItem(ui,"cloudLibrary");
                var recoveryGames=JSON.parse(JSON.stringify(syntheticCloud.games));
                recoveryGames[0].partial=true;syntheticCloud.games=recoveryGames;
                require(findItem(cloudUi,"cloudHintLabel_primary").text==="Check download","older bridge partial falsely promises Resume");
                recoveryGames=JSON.parse(JSON.stringify(recoveryGames));
                recoveryGames[0].resumeAvailable=true;recoveryGames[0].downloadState="partial";
                syntheticCloud.games=recoveryGames;syntheticCloud.called="";
                require(findItem(cloudUi,"cloudHintLabel_primary").text==="Resume","matching partial has no Resume action");
                key(ui,Qt.Key_Return);require(syntheticCloud.called==="install:1","Resume did not use the native install boundary");
                recoveryGames=JSON.parse(JSON.stringify(recoveryGames));recoveryGames[0].downloadBlocked=true;recoveryGames[0].resumeAvailable=false;
                recoveryGames[0].downloadReason="These partial files belong to a different library. They were kept.";
                syntheticCloud.games=recoveryGames;syntheticCloud.called="";
                require(!findItem(cloudUi,"cloudHint_primary").visible,"protected partial still offers a download");
                key(ui,Qt.Key_Return);require(syntheticCloud.called==="","protected partial reached install");
                require(findItem(cloudUi,"cloudNotice").text.indexOf("different library")!==-1,"protected partial has no explanation");
                key(ui,Qt.Key_Escape);require(ui.overlay==="settings" && ui.panelIndex===6,"recovery Back lost its originating selection");
                syntheticCloud.games=setupGames;ui.panelActivate(6,1);
                var keyMap=window.api.keys;
                keyMap.accept=[{name:function(){return "Start";}}];keyMap.cancel=[{name:function(){return "Select";}}];
                keyMap.details=[{name:function(){return "L3";}}];keyMap.filters=[{name:function(){return "R3";}}];
                require(cloudUi.kAccept === "Start" && cloudUi.kCancel === "Select" && cloudUi.kDetails === "L3" && cloudUi.kFilters === "R3","cloud ignores remapped labels");
                syntheticCloud.removalAllowed=false;syntheticCloud.called="";
                key(ui,Qt.Key_Y);require(cloudUi.cleanupOpen,"Make room did not open cleanup review");
                key(ui,Qt.Key_Return);require(!cloudUi.confirmRemove && syntheticCloud.called === "","unknown idle allowed removal");
                key(ui,Qt.Key_Escape);require(!cloudUi.cleanupOpen && cloudUi.selected === 0,"cleanup Back lost target selection");
                syntheticCloud.removalAllowed=true;
                key(ui,Qt.Key_Down);syntheticCloud.called="";
                key(ui,Qt.Key_Return);require(syntheticCloud.called === "", "unsupported cloud game installed");
                key(ui,Qt.Key_X);require(syntheticCloud.called === "refresh", "cloud refresh failed");
                key(ui,Qt.Key_Up);
                syntheticCloud.games=[{id:1,title:"Synthetic Adventure",system:"PlayStation",bytes:2048,installed:true,supported:true,cover:""}];
                key(ui,Qt.Key_Y);key(ui,Qt.Key_Escape);
                require(ui.overlay === "cloud", "cancel remove left cloud shelf");
                key(ui,Qt.Key_Y);
                require(findItem(cloudUi,"cloudNotice").text.indexOf("Press Start to confirm; Select keeps it")!==-1,"confirmation keeps fixed key labels");
                keyMap.accept=[{name:function(){return "Enter";}}];keyMap.cancel=[{name:function(){return "Esc";}}];
                keyMap.details=[{name:function(){return "X";}}];keyMap.filters=[{name:function(){return "Y";}}];
                syntheticCloud.removalGeneration++;syntheticCloud.called="";
                key(ui,Qt.Key_Return);require(syntheticCloud.called === "","stale preview reached removal");
                key(ui,Qt.Key_Y);syntheticCloud.games=JSON.parse(JSON.stringify(syntheticCloud.games));key(ui,Qt.Key_Return);require(syntheticCloud.called === "remove:1", "explicit cloud remove failed");
                key(ui,Qt.Key_Return);require(syntheticCloud.called === "play:1", "offline cloud play did not reach bridge");
                syntheticCloud.busy=true;key(ui,Qt.Key_X);require(syntheticCloud.called === "cancel", "pause download failed");
                key(ui,Qt.Key_Escape);window.romCloud=null;
                afterUIRepairs(ui,function(){afterHistoryRefresh(ui,function(){
                console.log("NOVA_DEMO_SMOKE_PASS: keyboard actions, session edit/filter/recreation/clear, aspect filters/persistence, launch-history refresh and return.");
                if(cloudScreenshotPath !== "") {
                    if (screenshotSurface === "session" || screenshotSurface === "session-filter") {
                        ui.overlay="";ui.clearFilters();ui.switchView("library");ui.setLibIndex(0);ui.zone="content";
                        ui.openDetails();ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("session"));
                        ui.panelActivate(2,1);
                        if(screenshotSurface === "session") {ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("session"));ui.panelIndex=2;}
                        else {ui.openPanel("filters",6);ui.setFilter("session","twenty");}
                    } else if (screenshotSurface === "aspect") {
                        var extra=window.api.allGames.get(0).extra;
                        extra["original-aspect"]="4:3";extra["original-aspect-source"]="Invented fixture manual";
                        ui.rebuildEverything();ui.switchView("library");ui.openPanel("filters",5);ui.setFilter("aspect","original-4-3");
                    } else if (screenshotSurface === "home") {
                        ui.rawEntries[0].lastPlayedHere=Date.parse("2026-11-03T10:00:00Z");ui.rawEntries[0].launchable=true;ui.rawEntries[0].route="Synthetic local shortcut";
                        ui.rawEntries[2].lastPlayedHere=Date.parse("2026-11-03T12:00:00Z");ui.rawEntries[2].launchable=true;ui.rawEntries[2].route="Synthetic local shortcut";
                        ui.rebuildHome("");ui.homeIndex=0;ui.overlay="";ui.switchView("home");
                    } else if (screenshotSurface === "library" || screenshotSurface === "details" || screenshotSurface === "details-nine") {
                        if(screenshotSurface === "details-nine") {window.deviceLibrary=Qt.createQmlObject('import QtQuick 2.15; QtObject { function read(query) { return {}; } function act(action) { return {ok:false,message:"Synthetic capture"}; } }',window);ui.refreshDevice();}
                        ui.overlay="";ui.clearFilters();ui.switchView("library");ui.zone="content";ui.setLibIndex(0);
                        ui.current.launchable=screenshotSurface === "details-nine";if(ui.current.launchable)ui.current.route="Synthetic launch stub";ui.current.installations={nova:{state:"absent",scopeComplete:true,source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z"},legion:{state:"installed",source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z"}};
                        ui.current.novaGameplayNote="Menus worked; gameplay not tested";ui.current.novaGameplaySource="Synthetic audit";ui.current.novaGameplayObservedAt="2026-11-05";
                        ui.rawEntries[1].launchable=true;ui.rawEntries[1].installations={nova:{state:"installed",source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z"}};
                        ui.rawEntries[2].launchable=false;ui.rawEntries[2].installations={nova:{state:"absent",scopeComplete:true,source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z"},legion:{state:"absent",scopeComplete:true,source:"Synthetic scan",observedAt:"2026-11-05T00:00:00Z"}};
                        var extra=[];["partial","installed"].forEach(function(state,i){var e={};Object.keys(ui.rawEntries[0]).forEach(function(k){e[k]=ui.rawEntries[0][k];});e.id="demo:install-"+state;e.title=i?"Downloaded adventure":"Partial adventure";e.sortKey=e.title.toLowerCase();e.launchable=false;e.installations={nova:{state:state,source:"Synthetic scan",observedAt:"2026-11-05"},legion:{state:"installed",source:"Synthetic scan",observedAt:"2026-11-05"}};extra.push(e);});
                        ui.rawEntries=ui.rawEntries.concat(extra);ui.rebuildPresentations();ui.rebuildLibrary("");ui.setLibIndex(0);ui.personalRev++;
                        if(screenshotSurface !== "library"){ui.openDetails();if(screenshotSurface === "details-nine"){require(ui.detailActions().length===9,"capture lost nine action fixture");ui.detailAction=8;}}
                    } else if (screenshotSurface === "apps" || screenshotSurface === "emulator-details") {
                        var app={};Object.keys(ui.rawEntries[0]).forEach(function(k){app[k]=ui.rawEntries[0][k];});
                        app.id="demo:emulator";app.title="Synthetic emulator";app.sortKey=app.title.toLowerCase();app.systemId="emulators";app.systemName="Emulators";app.developer="";app.genre="";app.launchable=true;
                        var apps=[app];["DroidDeck","Files","Synthetic media app"].forEach(function(title,i){var a={};Object.keys(app).forEach(function(k){a[k]=app[k];});a.id="demo:app-"+i;a.title=title;a.sortKey=title.toLowerCase();a.systemId="androidapps";a.appPackage="";apps.push(a);});
                        ui.rawEntries=ui.rawEntries.concat(apps);ui.rebuildPresentations();ui.overlay="";ui.switchView("apps");ui.zone="content";ui.setAppIndex(2);if(screenshotSurface === "emulator-details")ui.openDetails();
                    } else if (screenshotSurface === "storage" || screenshotSurface === "storage-file") {
                        ui.rawEntries.forEach(function(e,i){e.sizeBytes=i===0?0:i===1?null:1024*1024*(i+1);e.sizeObservedAt=Date.parse("2026-10-25T10:00:00Z");});
                        ui.rawEntries[0].capacity={id:"internal-data",total:128*1024*1024*1024,used:126*1024*1024*1024,free:2*1024*1024*1024,source:"Synthetic scan",observedAt:"2026-10-25T10:00:00Z"};
                        ui.rawEntries=ui.rawEntries.slice();ui.openPanel("storage",1);
                        if(screenshotSurface === "storage-file"){var fileIndex=ui.storageRows().map(function(row,i){return row.entry?i:-1;}).filter(function(i){return i>=0;})[0];ui.panelIndex=fileIndex;require(ui.panelFooter(0).indexOf("1 known file size ·")!==-1,"file footer lost singular or scope");}
                    } else if (screenshotSurface === "consoles") {
                        ui.rawEntries.forEach(function(e,i){e.systemId=i<2?"snes":i===2?"nds":"xbox";e.systemName=e.systemId.toUpperCase();e.launchable=i===0||i===3;e.missing=false;});
                        ui.rebuildPresentations();ui.overlay="";ui.switchView("consoles");ui.consoleIndex=0;
                    } else if (screenshotSurface === "settings" || screenshotSurface === "last-check" || screenshotSurface === "settings-absent") {
                        syntheticCloud.configured=false;window.romCloud=screenshotSurface === "settings-absent"?null:syntheticCloud;
                        ui.overlay="settings";ui.panelIndex=screenshotSurface === "last-check"?5:0;ui.health={checkedAt:"2026-10-25T10:00:00Z",issues:["Storage low: 0.9 GB free"]};
                    } else if (screenshotSurface === "collections" || screenshotSurface === "collections-members") {
                        ui.rawEntries[0].recReason="You kept this on your shelf";ui.rawEntries[0].recSource="manual-pin";
                        ui.threads=[{id:"demo:recs",name:"Suggested games",origin:"recommendations",reason:"Choose a game to see why it is here.",entries:[ui.rawEntries[0]]}];ui.threadIndex=0;ui.memberIndex=0;
                        ui.overlay="";ui.switchView("threads");ui.threadZone=screenshotSurface === "collections-members"?"members":"list";
                    } else if (screenshotSurface === "phone-audio") {
                        var phoneApp={};Object.keys(ui.rawEntries[0]).forEach(function(k){phoneApp[k]=ui.rawEntries[0][k];});
                        phoneApp.id="demo:phone-audio";phoneApp.systemId="androidapps";phoneApp.appPackage="io.github.jqssun.airplay";phoneApp.launchable=true;phoneApp.game={missing:false,launch:function(){}};
                        ui.rawEntries=ui.rawEntries.concat([phoneApp]);ui.rebuildPresentations();ui.overlay="";ui.switchView("apps");ui.openPanel("phoneaudio",0);
                    } else if (["cloud-library","cloud-install","cloud-details","cloud-home","download-resume","download-blocked","download-active","download-library"].indexOf(screenshotSurface)>=0) {
                        var recoverySurface=screenshotSurface.indexOf("download-")===0;
                        var cg=cloudFixture(!recoverySurface && screenshotSurface!=="cloud-install",ui.rawEntries[0].art);
                        if(recoverySurface){cg.partial=true;cg.resumeAvailable=true;cg.downloadState="partial";}
                        if(screenshotSurface==="download-blocked" || screenshotSurface==="download-library"){
                            cg.downloadBlocked=true;cg.resumeAvailable=false;cg.downloadState="blocked";
                            cg.downloadReason="These partial files belong to a different library. They were kept.";
                        }
                        if(screenshotSurface==="download-active")cg.downloadState="downloading";
                        syntheticCloud.message=recoverySurface ? "Retained files are checked before use. Cloud saves are off." : "Choose Download to install on this Nova. Cloud saves are off.";
                        syntheticCloud.storagePlan={spaceKnown:true,fits:true,remainingBytes:cg.bytes,freeBytes:1073741824,headroomBytes:134217728,shortfallBytes:0,reason:"Synthetic measured space"};
                        if(recoverySurface){syntheticCloud.storagePlan.retainedBytes=131072;syntheticCloud.storagePlan.remainingBytes=cg.bytes-131072;}
                        syntheticCloud.catalogueVersion=1;syntheticCloud.games=[cg];window.romCloud=syntheticCloud;
                        ui.overlay="";ui.rebuildEverything();ui.clearFilters();ui.switchView("library");ui.zone="content";
                        ui.setLibIndex(ui.libraryEntries.map(function(e){return e.id;}).indexOf(cg.editionId));
                        if(screenshotSurface==="download-library") {
                            require(ui.quietLine(ui.current,ui.personalRev).indexOf("files kept")!==-1,"Cloud caption hides the protected-copy state");
                            require(ui.wideSummaryLines(ui.current,ui.personalRev).filter(function(line){return line.t.indexOf("Download needs review")!==-1;}).length===1,"wide Cloud status repeats");
                            var navHints=findItem(ui,"pageHints"),navTexts=[];
                            for(var ni=0;ni<navHints.children.length;ni++)if(typeof navHints.children[ni].text==="string" && navHints.children[ni].visible)navTexts.push(navHints.children[ni]);
                            if(navHints.visible && navTexts.length===2)require(navTexts[1].x>=navTexts[0].x+navTexts[0].width+ui.px(20),"page hints overlap");
                        }
                        if(screenshotSurface==="cloud-install" || recoverySurface && screenshotSurface!=="download-library")ui.play(ui.current);
                        else if(screenshotSurface==="cloud-details")ui.openDetails();
                        else if(screenshotSurface==="cloud-home") {var opened={};opened[cg.editionId]=Date.now();ui.cloudOpened=opened;ui.rebuildEverything();ui.switchView("home");ui.homeIndex=ui.homeEntries.map(function(e){return e.id;}).indexOf(cg.editionId);}
                        if(screenshotSurface==="download-active"){
                            syntheticCloud.busy=true;syntheticCloud.message="Downloading Synthetic Adventure";
                            var activeUi=findItem(ui,"cloudLibrary"),content=findItem(activeUi,"cloudContent"),progress=findItem(activeUi,"cloudProgress");
                            require(content.y+content.height+ui.px(12)<=progress.y,"download progress crosses artwork");
                        }
                    } else if (screenshotSurface === "cloud-setup") {
                        syntheticCloud.configured=false;syntheticCloud.games=[];window.romCloud=syntheticCloud;
                        ui.openPanel("settings",6);ui.panelActivate(6,1);
                    } else if (screenshotSurface === "paused-status") {
                        ui.current.status="paused";ui.openPanel("status",0);
                        ui.panelIndex=ui.panelRows(ui.personalRev).map(function(row){return row.label;}).indexOf("Paused");
                        var pausedRow=ui.panelRows(ui.personalRev)[ui.panelIndex];
                        require(pausedRow.label === "Paused" && pausedRow.value === "Current","paused status picker lost its distinct current choice");
                    } else if (screenshotSurface === "checks") {
                        checkFixture[0].editionId=ui.current.id;
                        ui.current.compatibilityReceipts=JSON.stringify(checkFixture);ui.current.compatibilityRecipeId="fixture.v1";
                        ui.personalRev++;
                        ui.overlay="details";
                        ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("checks"));ui.panelIndex=2;
                    } else if (screenshotSurface === "controls") {
                        ui.current.route="HakuX 1.2";
                        ui.current.sessionProfile="hakux-nova-v1";
                        ui.overlay="details";
                        var controlsAction=ui.detailActions().map(function(a){return a.a;}).indexOf("guide");
                        ui.runDetailAction(controlsAction);ui.panelIndex=2;
                    } else {
                        window.romCloud=syntheticCloud;ui.panelActivate(6,1);
                        if (screenshotSurface === "space" || screenshotSurface === "cleanup") {
                            syntheticCloud.games=[{id:1,title:"Synthetic Adventure",system:"PlayStation",bytes:2048,installed:false,supported:true,cover:""}];
                            syntheticCloud.storagePlan=({spaceKnown:true,fits:false,remainingBytes:2048,freeBytes:0,headroomBytes:134217728,shortfallBytes:134219776,reason:"Not enough free space. Choose a download to remove first; saves are not cleanup targets."});
                            if(screenshotSurface === "cleanup"){syntheticCloud.removalAllowed=false;key(ui,Qt.Key_Y);}
                        }
                    }
                    ui.notice="";
                    afterArtwork(ui,function(){ui.grabToImage(function(result) {
                        var hints=findItem(ui,"buttonHints");
                        require(hints && hints.y+hints.height <= ui.usableHeight-ui.px(20),"button hints extend into the reserved screen edge");
                        if(ui.view === "consoles" && ui.overlay === "") {
                            ui.consoleSystems.forEach(function(system){
                                var label=findItem(ui,"consoleAvailability_"+system.id);
                                require(ui.consoleReady(system.id)<=system.count,"set-up count exceeds catalogue count");
                                require(label && label.lineCount===2 && label.contentWidth<=label.width,"console availability text clips");
                            });
                        }
                        if(ui.overlay === "filters") {
                            var list=findItem(ui,"panelList"), explanation=findItem(ui,"panelExplanation");
                            require(list && list.currentItem,"filter focus item missing");
                            require(list.currentItem.y-list.contentY >= -2 && list.currentItem.y-list.contentY+list.currentItem.height <= list.height+2,"selected filter row clipped");
                            require(explanation && explanation.y+explanation.height < hints.y,"filter explanation overlaps footer");
                        }
                        if(ui.overlay === "details") {
                            var actions=findItem(ui,"detailActions");
                            require(actions && actions.currentItem, "selected detail action missing");
                            var item=actions.currentItem;
                            require(item.x-actions.contentX >= -2 && item.x-actions.contentX+item.width <= actions.width+2, "selected detail action is clipped");
                        }
                        if(!result.saveToFile(cloudScreenshotPath)) {console.error("NOVA_DEMO_SMOKE_FAIL: screenshot save failed");Qt.exit(1);}
                        else Qt.exit(0);
                    });});
                } else Qt.exit(0);
                });});
            } catch(error) {
                console.error("NOVA_DEMO_SMOKE_FAIL: " + error);
                Qt.exit(1);
            }
        }
    }
