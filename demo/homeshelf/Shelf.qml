import QtQuick 2.15
import QtQuick.Window 2.15
import "../../theme" as Nova
import "../generated/games.js" as Data

Window {
    id: window
    visible: true; width: 1280; height: 960
    color: shelf.ground
    property int inset: 0
    property int details: 0
    property int notebooks: 0
    property bool fixtureMotion: false
    Rectangle { anchors.fill: parent; color: shelf.ground }
    property var games: Data.games.map(function(game,index){return {
        id:game.extra["edition-id"], title:game.title, systemId:index===2?"pc":"snes", systemName:index===2?"PC":"Super Nintendo",
        art:Qt.resolvedUrl(index===1?"../generated/art/square.png":index===2?"../generated/art/wide.png":"../generated/"+game.cover).toString(),launchable:true
    };})
    FocusScope {
        anchors.fill:parent;focus:true
        Keys.onPressed: {
            event.accepted=true;
            if(event.key===Qt.Key_Left)shelf.select(shelf.currentIndex-1);
            else if(event.key===Qt.Key_Right)shelf.select(shelf.currentIndex+1);
            else if(event.key===Qt.Key_X)window.details++;
        }
        Text {x:shelf.px(64);y:shelf.px(28);text:"Home     Library     Consoles     Collections     Apps     Settings";color:shelf.quiet;font.pixelSize:shelf.fs(22)}
        Nova.HomeShelf {
            id:shelf
            width:parent.width;height:parent.height-window.inset
            entries:window.games;heading:"Your games"
            contextText:current?(current.systemName+" · Layout specimen"):""
            statusText:"";checkpointText:"";canOpenNotebook:true
            ground:fixtureLight?"#f3f3f1":"#0c0d0e";ink:fixtureLight?"#151617":"#e9eaea"
            quiet:Qt.rgba(ink.r,ink.g,ink.b,0.62);slab:fixtureLight?"#e1e1de":"#1a1c1e"
            textScale:fixtureLarge?1.12:1;reducedMotion:!window.fixtureMotion
            fontFamily:Qt.application.font.family
            onSelectionRequested:selectedIndex=index
            onDetailsRequested:window.details++
            onNotebookRequested:window.notebooks++
        }
        Text {x:shelf.px(64);y:shelf.height-shelf.px(64);text:"A Play     X Details     Y Favourite     ↓ Three to try";color:shelf.ink;font.pixelSize:shelf.fs(22)}
    }
    Timer {
        interval:180;running:true;repeat:true
        property int step:0
        property bool capturing:false
        function require(value,why){if(!value)throw new Error(why);}
        function find(item,name){if(item.objectName===name)return item;for(var i=0;i<item.children.length;i++){var found=find(item.children[i],name);if(found)return found;}return null;}
        function key(code){require(driver.key(code),"Key was not accepted");driver.key(code,false);}
        function capture(name,next){capturing=true;window.contentItem.grabToImage(function(image){require(image.saveToFile(fixtureOutput+"/"+name+".png"),"Capture failed");capturing=false;step=next;});}
        function layout(){
            var info=find(shelf,"homeShelfInformation"),stage=find(shelf,"homeShelfStage"),cell=find(shelf,"homeShelfCell_"+shelf.currentIndex);
            require(info.y+info.height<=shelf.height-shelf.px(110),"Information crosses footer");
            require(stage.y+stage.height<=info.y-shelf.px(20),"Artwork overlaps information");
            require(cell && cell.caseItem.height>0,"Current cover has no area");
            var point=cell.caseItem.mapToItem(shelf,0,0);
            require(point.x>=shelf.px(25) && point.x+cell.caseItem.width<=shelf.width-shelf.px(25),"Focused case crosses side bounds");
            require(point.y>=stage.y && point.y+cell.caseItem.height<=stage.y+stage.height,"Focused case crosses stage");
        }
        onTriggered:{try{
            if(capturing)return;
            if(step===0){shelf.forceActiveFocus();step=1;return;}
            if(step===1){var first=find(shelf,"homeShelfCell_0");if(!first || !first.caseArt || !first.caseArt.loaded)return;layout();capture("initial",2);return;}
            if(step===2){key(Qt.Key_Right);key(Qt.Key_Right);step=3;return;}
            if(step===3){var wide=find(shelf,"homeShelfCell_2");if(!wide || !wide.caseArt || !wide.caseArt.loaded)return;require(shelf.current.id==="demo:horizon" && Math.abs(wide.ratio-640/360)<0.02,"Keyboard selection or original wide cover ratio changed");layout();capture("selected",4);return;}
            if(step===4){
                var target=find(shelf,"homeShelfObject_2"),point=target.mapToItem(null,target.width/2,target.height/2);
                driver.tap(Math.round(point.x),Math.round(point.y));require(window.details===1,"Selected cover did not open Details");
                shelf.checkpointText="Where I left off · A real authored note would appear here. This is a synthetic fixture for long text containment.";
                var copy=window.games.map(function(entry){var x={};Object.keys(entry).forEach(function(k){x[k]=entry[k];});return x;});
                copy[2].title="A deliberately long edition title that needs two lines without hiding the selected game";copy[2].launchable=false;window.games=copy;step=5;return;
            }
            if(step===5){layout();capture("long-note",6);return;}
            if(step===6){var note=find(shelf,"homeNote"),point=note.mapToItem(null,note.width/2,note.height/2);driver.tap(Math.round(point.x),Math.round(point.y));require(window.notebooks===1,"Notebook pointer action missing");
                var copy=window.games.slice();copy[2]={id:"demo:no-art",title:"Missing artwork",systemId:"snes",systemName:"Super Nintendo",art:"",launchable:false};window.games=copy;shelf.checkpointText="";step=7;return;}
            if(step===7){layout();capture("missing-art",8);return;}
            if(step===8){window.fixtureMotion=true;for(var i=0;i<14;i++)key(i%2?Qt.Key_Left:Qt.Key_Right);step=9;return;}
            if(step===9){require(shelf.current.id==="demo:no-art","Rapid navigation drifted");layout();window.fixtureMotion=false;window.games=[window.games[2]];shelf.selectedIndex=9;step=10;return;}
            if(step===10){require(shelf.currentIndex===0 && shelf.current.id==="demo:no-art","Single entry clamp failed");layout();window.games=[];step=11;return;}
            if(step===11){require(shelf.current===null && shelf.currentIndex===-1,"Empty state kept an edition");capture("empty",12);return;}
            if(step===12){key(Qt.Key_Right);require(shelf.current===null && window.details===1,"Empty state dispatched an action");stop();console.log("HOME_SHELF_PASS");Qt.exit(0);}
        }catch(error){stop();console.error("HOME_SHELF_FAIL "+error);shelf.grabToImage(function(image){image.saveToFile(fixtureOutput+"/failure.png");Qt.exit(1);});}}
    }
}
