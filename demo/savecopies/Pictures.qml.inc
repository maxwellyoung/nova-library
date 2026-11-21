    Timer {
        interval:200;running:true;repeat:true
        property int step:0
        property int waits:0
        property bool capturing:false
        property string firstSource:""
        property string selected:""
        function require(v,m){if(!v)throw new Error(m);}
        function key(k){require(driver.key(k),"Key not consumed");driver.key(k,false);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var got=find(item.children[i],name);if(got)return got;}return null;}
        function finish(){stop();console.log("COPY_PICTURES_PASS "+fixtureScenario);Qt.exit(0);}
        onTriggered:{try{
            if(capturing)return;var ui=themeLoader.item;
            if(step===0){
                ui.appearance={surface:fixtureLight?"light":"dark",size:fixtureLarge?"large":"standard",motion:false,time:false};ui.switchView("library");ui.zone="content";
                ui.setLibIndex(ui.libraryEntries.map(function(e){return e.id;}).indexOf("demo:orbit"));ui.openDetails();
                if(fixtureScenario==="decoder")driver.damagePicture("decoder");
                ui.runDetailAction(ui.detailActions().map(function(a){return a.a;}).indexOf("savecopies"));
                require(ui.panelRows(0).length===2 && ui.hints().some(function(h){return h.a==="copypicture";}),"Attached image action missing");
                selected=ui.panelRows(0)[0].copy.checkpointId;
                if(["flow","decoder","focus"].indexOf(fixtureScenario)<0){
                    driver.damagePicture(fixtureScenario);key(Qt.Key_X);
                    require(ui.overlay==="savecopies" && ui.saveCopyPictureSource==="","Changed/unreadable image was shown");
                    require(ui.notice.indexOf(fixtureScenario==="stale"?"history changed":"could not be read")>=0,"Image refusal hidden");
                    require(ui.panelIndex===0 && !ui.saveCopyToken,"Image refusal changed selection or started archive review");key(Qt.Key_Escape);require(ui.overlay==="details","Refusal Back lost parent");finish();return;
                }
                key(Qt.Key_X);require(ui.overlay==="copypicture" && ui.saveCopyPictureRow.checkpointId===selected,"Wrong attached checkpoint opened");firstSource=ui.saveCopyPictureSource;step=1;return;
            }
            var image=find(ui,"saveCopyPicture"),caption=find(ui,"saveCopyPictureCaption");
            if(image.status===Image.Loading || image.status===Image.Null){require(++waits<40,"Image decode timed out");return;}
            if(fixtureScenario==="decoder"){
                require(image.status===Image.Error && find(ui,"saveCopyPictureUnavailable").visible,"Decoder failure became a blank or successful preview");
                require(/^image:\/\/nova-save-copies\/[a-f0-9]{32}$/.test(ui.saveCopyPictureSource),"Decoder URL exposed image bytes/path");key(Qt.Key_Escape);
                require(ui.overlay==="savecopies" && !ui.saveCopyPictureSource,"Decoder failure Back lost parent");finish();return;
            }
            require(image.status===Image.Ready && image.paintedWidth>0 && image.paintedHeight>0,"Verified image failed actual Qt decode");
            if(fixtureScenario==="focus"){
                ui.applicationActive(false);require(ui.overlay==="savecopies" && !ui.saveCopyPictureSource && ui.saveCopyPictureRow===null,"Focus loss retained the private image");ui.applicationActive(true);finish();return;
            }
            require(caption.y+caption.height<=ui.usableHeight && image.y+image.height<=caption.y,"Picture/caption overflow");
            require(caption.text.indexOf("does not prove")>=0 && !ui.saveCopyToken,"Picture manufactured save/load proof");
            if(step===1){
                capturing=true;ui.grabToImage(function(im){require(im.saveToFile(fixtureOutput+"/picture.png"),"Image frame failed");capturing=false;step=2;});return;
            }
            if(step===2){
                key(Qt.Key_Escape);require(ui.overlay==="savecopies" && ui.panelIndex===0 && ui.saveCopyPictureSource==="" && ui.saveCopyPictureRow===null,"Back retained private image or lost selected copy");
                key(Qt.Key_Down);key(Qt.Key_X);require(ui.overlay==="copypicture" && ui.saveCopyPictureRow.checkpointId!==selected && ui.saveCopyPictureSource!==firstSource,"A different checkpoint reused the first picture");step=3;return;
            }
            key(Qt.Key_Back);require(ui.overlay==="savecopies" && ui.panelIndex===1 && !ui.saveCopyPictureSource,"Android Back did not return to exact second copy");
            key(Qt.Key_Escape);require(ui.overlay==="details" && ui.current.id==="demo:orbit","Picture/list Back lost exact edition");finish();
        }catch(error){stop();console.error("COPY_PICTURES_FAIL "+fixtureScenario+": "+error);Qt.exit(1);}}
    }
