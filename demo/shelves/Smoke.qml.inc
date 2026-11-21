    // Drives Your shelves through the real theme with synthetic games and in-process memory.
    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        property int countBefore:0
        property string pinsBefore:""
        property string rawBefore:""
        property string homeBefore:""
        property string rotationBefore:""
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Unaccepted key "+k);driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function capture(name,next){capturing=true;themeLoader.item.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        // Inspect the backing fixture value even when its public getter deliberately refuses reads.
        function stored(){return JSON.stringify(api.memory.has("shelvesV1")?api.memory.values["shelvesV1"]:null);}
        function shelfIds(ui){return ui.shelves.shelves.map(function(s){return s.id;}).join(",");}
        function members(ui,id){var s=ui.shelves.shelves.filter(function(x){return x.id===id;})[0];return s?s.editions.map(function(e){return e.id;}).join(","):"";}
        function hasText(item,text){if(item.text===text && item.visible)return true;for(var i=0;i<item.children.length;i++)if(hasText(item.children[i],text))return true;return false;}
        function hint(ui,label){return ui.hints().some(function(h){return h.l===label;});}
        function rowIndex(ui,test){var rows=ui.panelRows(ui.personalRev);for(var i=0;i<rows.length;i++)if(test(rows[i]))return i;return -1;}
        function moveTo(ui,index){require(index>=0,"Row missing");while(ui.panelIndex<index)key(Qt.Key_Down);while(ui.panelIndex>index)key(Qt.Key_Up);}
        function picker(ui,id){
            ui.overlay="";ui.switchView("library");ui.zone="content";
            var index=ui.libraryEntries.map(function(e){return e.id;}).indexOf(id);require(index>=0,"Fixture edition missing");ui.setLibIndex(index);ui.openDetails();
            var a=ui.detailActions().map(function(e){return e.a;}).indexOf("thread");require(a>=0,"Offline Collections action missing");ui.runDetailAction(a);
            require(ui.overlay==="threadpick" && ui.panelRows(0)[0].rotation,"Local picker missing");
        }
        function collections(ui){ui.overlay="";ui.switchView("threads");ui.zone="content";ui.threadIndex=0;require(ui.currentThread.origin==="rotation","Rotation is not first");}
        function selectShelf(ui,id){
            collections(ui);var i=ui.threads.map(function(t){return t.shelfId;}).indexOf(id);require(i>0,"Shelf missing from Collections");
            while(ui.threadIndex<i)key(Qt.Key_Down);require(ui.currentThread.shelfId===id,"Shelf not selected");
        }
        function newShelf(ui,id,name){
            picker(ui,id);moveTo(ui,rowIndex(ui,function(r){return r.newshelf;}));key(Qt.Key_Return);
            require(ui.overlay==="text" && ui.textMode==="shelf-new","New shelf did not open naming");
            find(ui,"textInput").text=name;key(Qt.Key_Return);
        }
        function finish(ui){
            require(ui.gameCount===countBefore && JSON.stringify(ui.rawEntries.map(function(e){return e.id;}))===rawBefore,"Shelves altered the library");
            require(JSON.stringify(ui.pins)===pinsBefore,"Shelves altered favourites");
            require(JSON.stringify(ui.homeEntries.map(function(e){return e.id;}))===homeBefore,"Shelves altered Home");
            require(JSON.stringify(api.memory.has("rotationV1")?api.memory.get("rotationV1"):null)===rotationBefore,"Shelves altered the rotation");
            stop();console.log("SHELVES_THEME_PASS "+fixtureScenario);Qt.exit(0);
        }
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};
                require(!ui.canEdit,"Fixture accidentally enables sync");countBefore=ui.gameCount;pinsBefore=JSON.stringify(ui.pins);
                rawBefore=JSON.stringify(ui.rawEntries.map(function(e){return e.id;}));homeBefore=JSON.stringify(ui.homeEntries.map(function(e){return e.id;}));
                rotationBefore=JSON.stringify(api.memory.has("rotationV1")?api.memory.get("rotationV1"):null);
                collections(ui);
                if(fixtureScenario==="reopen"){
                    var saved=ui.shelves.shelves;require(saved.length===2,"Fresh process lost shelves");
                    require(ui.threads.slice(1,3).map(function(t){return t.shelfId;}).join(",")===shelfIds(ui),"Collections ignored authored shelf order");
                    require(saved[0].name==="Ten-minute adrenaline" && saved[1].name==="Dreamlike worlds" && saved[1].kind==="purpose","Names or kind not reapplied");
                    require(ui.threads[2].entries.map(function(e){return e.id;}).join(",")===members(ui,saved[1].id),"Member order not reapplied");
                    require(ui.threads.slice(1,3).every(function(t){return t.origin==="shelf" && t.reason.indexOf("Not a suggestion")>=0;}),"Authored shelf looks like a suggestion");
                    key(Qt.Key_Down);key(Qt.Key_Down);require(hint(ui,"Edit shelf"),"Edit shelf hint missing");
                    key(Qt.Key_Return);require(ui.threadZone==="members" && ui.current.id===saved[1].editions[0].id,"Open did not select first authored member");
                    key(Qt.Key_Escape);require(ui.threadZone==="list" && ui.currentThread.shelfId===saved[1].id,"Back left shelf context");
                    capture("reopened",20);return;
                }
                if(fixtureScenario==="corrupt" || fixtureScenario==="emptyname" || fixtureScenario==="readrefusal"){
                    var before=stored();require(ui.shelves===null,"Unreadable shelves became empty");
                    require(ui.threads[1].unreadable && !ui.threads[1].entries.length,"Unreadable state not explicit in Collections");
                    key(Qt.Key_Down);require(!hint(ui,"Edit shelf"),"Unreadable shelves offered editing");key(Qt.Key_X);require(ui.overlay==="","Unreadable shelves opened an editor");
                    picker(ui,"demo:orbit");var i=rowIndex(ui,function(r){return r.shelfUnreadable;});require(i===1 && rowIndex(ui,function(r){return r.newshelf;})<0,"Picker offered writes over unreadable shelves");
                    moveTo(ui,i);key(Qt.Key_Return);require(stored()===before && ui.shelves===null && ui.overlay==="threadpick","Unreadable shelves overwritten");
                    capture("unreadable",20);return;
                }
                if(fixtureScenario==="missing"){
                    require(ui.threads[1].absent===1 && ui.threads[1].entries.length===1,"Absent edition disappeared or became launchable");
                    key(Qt.Key_Down);key(Qt.Key_X);require(ui.overlay==="shelf","Editor missing");
                    var row=ui.panelRows(0)[3];require(row.label==="Absent edition" && row.value.indexOf("Not in catalogue")>=0,"Absent edition has no cached context");
                    ui.panelIndex=4;step=32;return;
                }
                if(fixtureScenario==="long"){
                    key(Qt.Key_Down);key(Qt.Key_X);moveTo(ui,3);require(ui.panelFooter(0).indexOf(ui.shelves.shelves[0].editions[0].title)>=0,"Full selected title lost");step=31;return;
                }
                if(fixtureScenario==="full"){
                    require(ui.shelves.shelves.length===8,"Capacity fixture wrong");picker(ui,"demo:orbit");var full=rowIndex(ui,function(r){return r.newshelf;});
                    require(ui.panelRows(0)[full].dim,"Full shelf list not explained");var was=stored();moveTo(ui,full);key(Qt.Key_Return);
                    require(ui.overlay==="threadpick" && stored()===was && ui.notice.indexOf("up to 8")>=0,"Limit did not refuse a new shelf");
                    moveTo(ui,1);key(Qt.Key_Return);require(stored()===was && ui.notice.indexOf("up to 24")>=0,"Full shelf accepted another edition");
                    collections(ui);key(Qt.Key_Down);key(Qt.Key_X);for(var n=0;n<27;n++)key(Qt.Key_Down);step=30;return;
                }
                require(ui.shelves.shelves.length===0 && ui.threads.every(function(t){return t.origin!=="shelf";}),"Empty shelves invented a row");
                picker(ui,"demo:garden");var create=rowIndex(ui,function(r){return r.newshelf;});require(create===1,"New shelf is not offered offline");
                moveTo(ui,create);key(Qt.Key_Return);require(ui.overlay==="text" && ui.textMode==="shelf-new","Naming did not open");
                find(ui,"textInput").text="  Dreamlike ";capture("naming",1);return;
            }
            if(step===1){
                key(Qt.Key_Return);
                require(ui.overlay==="details" && ui.current.id==="demo:garden","Naming did not return to the same Details");
                require(shelfIds(ui)==="shelf:1" && ui.shelves.shelves[0].name==="Dreamlike" && members(ui,"shelf:1")==="demo:garden","Create+add was not one exact write");
                picker(ui,"demo:orbit");require(ui.panelRows(0)[1].value==="Add here","Shelf row state wrong");moveTo(ui,1);key(Qt.Key_Return);
                require(members(ui,"shelf:1")==="demo:garden,demo:orbit" && ui.panelRows(0)[1].value==="On this shelf","Add appended out of order");
                key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id==="demo:orbit","Picker Back lost edition");
                newShelf(ui,"demo:orbit","Ten-minute adrenaline");require(shelfIds(ui)==="shelf:1,shelf:2" && members(ui,"shelf:2")==="demo:orbit","Second shelf failed");
                var was=stored();newShelf(ui,"demo:garden","dreamLIKE");
                require(stored()===was && ui.notice.indexOf("already have")>=0,"Duplicate name accepted");
                newShelf(ui,"demo:garden","   ");require(stored()===was,"Blank name wrote a shelf");
                picker(ui,"demo:garden");capture("picker",2);return;
            }
            if(step===2){
                selectShelf(ui,"shelf:1");require(ui.currentThread.origin==="shelf" && hasText(ui,"Yours") && ui.currentThread.reason.indexOf("Not a suggestion")>=0,"Shelf not labelled as yours");
                require(hint(ui,"Edit shelf"),"Edit shelf hint missing");key(Qt.Key_X);require(ui.overlay==="shelf" && ui.shelfEditId==="shelf:1","Controller edit failed");
                key(Qt.Key_Return);require(ui.overlay==="text" && ui.textMode==="shelf-rename" && find(ui,"textInput").text==="Dreamlike","Rename not prefilled");
                find(ui,"textInput").text="Dreamlike worlds";key(Qt.Key_Return);
                require(ui.overlay==="shelf" && ui.shelves.shelves[0].name==="Dreamlike worlds" && members(ui,"shelf:1")==="demo:garden,demo:orbit","Rename lost membership or editor");
                require(ui.currentThread.name==="Dreamlike worlds","Collections kept stale name");
                key(Qt.Key_Down);key(Qt.Key_Right);require(ui.shelves.shelves[0].kind==="purpose","Right did not change kind");
                key(Qt.Key_Left);require(ui.shelves.shelves[0].kind==="feeling","Left did not change kind back");
                key(Qt.Key_Return);require(ui.shelves.shelves[0].kind==="purpose","Accept did not change kind");
                key(Qt.Key_Down);require(hint(ui,"Later"),"Order hints missing");key(Qt.Key_Right);
                require(shelfIds(ui)==="shelf:2,shelf:1" && ui.currentThread.shelfId==="shelf:1" && ui.panelIndex===2,"Shelf move lost focus or order");
                key(Qt.Key_Right);require(shelfIds(ui)==="shelf:2,shelf:1","Boundary shelf move changed order");
                key(Qt.Key_Left);require(shelfIds(ui)==="shelf:1,shelf:2","Left did not move shelf earlier");ui.runHint("shelflater");require(shelfIds(ui)==="shelf:2,shelf:1","Touch hint did not move shelf");
                key(Qt.Key_Down);key(Qt.Key_Right);require(members(ui,"shelf:1")==="demo:orbit,demo:garden" && ui.panelIndex===4,"Member move lost selection");
                ui.runHint("shelfearlier");require(members(ui,"shelf:1")==="demo:garden,demo:orbit","Touch hint did not move member");
                capture("editor",3);return;
            }
            if(step===3){
                moveTo(ui,4);key(Qt.Key_Return);require(members(ui,"shelf:1")==="demo:garden" && ui.panelIndex===4,"Member removal failed or focus escaped");
                require(ui.panelRows(0)[4].act==="delete" && ui.panelRows(0)[4].dim && !hint(ui,"Delete"),"Delete offered on a shelf with games");
                var was=stored();key(Qt.Key_Return);require(stored()===was && ui.notice.indexOf("Remove its games first")>=0,"Non-empty shelf deleted");
                moveTo(ui,1);was=stored();var kind=ui.shelves.shelves[1].kind;api.memory.refuseAllWrites=true;key(Qt.Key_Return);api.memory.refuseAllWrites=false;
                require(stored()===was && ui.shelves.shelves[1].kind===kind && ui.notice.indexOf("previous shelves were kept")>=0,"Refused write changed UI or preferences");
                capture("write-refusal",4);return;
            }
            if(step===4){
                var other=JSON.parse(stored());other.serial=3;other.shelves.push({id:"shelf:3",name:"Elsewhere",kind:"feeling",editions:[]});api.memory.set("shelvesV1",other);
                var external=stored();key(Qt.Key_Return);
                require(stored()===external && shelfIds(ui)==="shelf:2,shelf:1,shelf:3" && ui.notice.indexOf("reloaded")>=0,"Conflicting stored shelves were overwritten");
                capture("conflict",5);return;
            }
            if(step===5){
                require(driver.key(Qt.Key_Back),"Android Back press unaccepted");driver.key(Qt.Key_Back,false);require(ui.overlay==="" && ui.view==="threads","Android Back left Collections");
                selectShelf(ui,"shelf:3");key(Qt.Key_X);moveTo(ui,rowIndex(ui,function(r){return r.act==="delete";}));require(hint(ui,"Delete"),"Empty shelf not deletable");
                key(Qt.Key_Return);require(shelfIds(ui)==="shelf:2,shelf:1" && ui.overlay==="" && ui.threadZone==="list","Empty shelf delete failed");
                selectShelf(ui,"shelf:1");key(Qt.Key_Return);require(ui.current.id==="demo:garden","Member open wrong");
                key(Qt.Key_X);ui.runDetailAction(ui.detailActions().map(function(e){return e.a;}).indexOf("thread"));
                moveTo(ui,rowIndex(ui,function(r){return r.shelf==="shelf:1";}));key(Qt.Key_Return);
                require(members(ui,"shelf:1")==="" && ui.overlay==="" && ui.threadZone==="list","Removing an open member silently switched Details");
                picker(ui,"demo:orbit");moveTo(ui,rowIndex(ui,function(r){return r.shelf==="shelf:1";}));key(Qt.Key_Return);
                picker(ui,"demo:garden");moveTo(ui,rowIndex(ui,function(r){return r.shelf==="shelf:1";}));key(Qt.Key_Return);
                require(members(ui,"shelf:1")==="demo:orbit,demo:garden","Final membership wrong");
                selectShelf(ui,"shelf:1");ui.notice="";
                console.log("SHELVES_SAVED "+stored());capture("collection",20);return;
            }
            if(step===20){finish(ui);return;}
            if(step===30){
                var list=find(ui,"panelList"),selected=list.currentItem,top=selected.y-list.contentY;
                require(ui.panelRows(0)[ui.panelIndex].act==="delete" && top>=-1 && top+selected.height<=list.height+1,"Last editor row is offscreen");
                var notice=find(ui,"footerNotice"),hints=find(ui,"primaryHints");
                require(!notice.visible || notice.x>=hints.x+hints.width+ui.px(20),"Status notice overlaps the Back controls");capture("full",20);return;
            }
            if(step===32){
                var tapped=find(ui,"panelRow_3");require(tapped,"Member delegate was not laid out");tapped.clicked(null);
                require(members(ui,"shelf:1")==="demo:orbit","Touch removed the focused row instead of the tapped one");
                capture("missing-removed",20);return;
            }
            if(step===31){
                var list=find(ui,"panelList"),selected=list.currentItem,top=selected.y-list.contentY,footer=find(ui,"panelExplanation");
                require(top>=-1 && top+selected.height<=list.height+1,"Long-title selection is offscreen");
                require(footer.y+footer.height<=ui.usableHeight-ui.px(80),"Long-title explanation collides with controls");capture("long-title",20);return;
            }
        }catch(error){stop();console.error("SHELVES_THEME_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
