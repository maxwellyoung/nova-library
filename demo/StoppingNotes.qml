import QtQuick 2.15
import QtQuick.Window 2.15
import "../theme"

// Standalone adapter fixture. It has no catalogue, launch, capture or sync capability.
Window {
    id: window
    width: 1100; height: 900; visible: true; color: "#101214"
    title: "Stopping notebook — local adapter fixture"
    property string notice: "Private local fixture. Drag on an imported image to add an ellipse."
    StoppingNoteModel { id: notes; storage: stoppingNotes }
    Component.onCompleted: notes.open("fixture:edition:one",{})
    property var actions: [
        {label:"New note",run:function(){notes.beginNew();editor.text="";}},
        {label:"Save draft",run:function(){notice=notes.save()?"Saved on local storage.":notes.lastError;}},
        {label:"Reopen stored",run:function(){notes.open(notes.editionId,notes.legacyCheckpoint);editor.text=notes.draft.text;}},
        {label:"Clear selected",run:function(){notice=notes.clear()?"Cleared; retained original and note can be restored.":notes.lastError;}},
        {label:"Detach image",run:function(){notes.detachImage();}},
        {label:"Export private",run:function(){var r=notes.exportTo(exportPath.text);notice=r.ok?"Private export created; nothing sent.":r.error;}}
    ]
    Column {
        x: 32; y: 28; width: parent.width-64; spacing: 10
        Text { textFormat:Text.PlainText; text:"Stopping notebook · standalone fixture"; color:"#eff0ee";font.pixelSize:28 }
        Text { textFormat:Text.PlainText; text:"Exact edition: "+notes.editionId+" · local revision "+notes.revision; color:"#aaaead";font.pixelSize:17 }
        Row {
            spacing:12
            Repeater { model:window.actions;delegate:Rectangle {
                width:actionText.implicitWidth+20;height:38;color:"#262b2e"
                Text { textFormat:Text.PlainText;id:actionText;text:modelData.label;color:"#eff0ee";font.pixelSize:16;anchors.centerIn:parent}
                MouseArea {anchors.fill:parent;onClicked:modelData.run()}
            }}
        }
        Rectangle {
            width:parent.width;height:38;color:"#262b2e"
            TextInput {id:importPath;anchors.fill:parent;anchors.margins:8;color:"#eff0ee";font.pixelSize:16;clip:true;selectByMouse:true;text:"file:///explicit/local/image.png";onAccepted:{notice=notes.importOriginal(text)?"Original copied privately; save draft to attach it.":notes.lastError;}}
        }
        Text { textFormat:Text.PlainText;text:"Import: enter the exact local image URL above, then press Enter. No folders are scanned.";color:"#aaaead";font.pixelSize:15}
        Rectangle {
            width:parent.width;height:38;color:"#262b2e"
            TextInput {id:exportPath;anchors.fill:parent;anchors.margins:8;color:"#eff0ee";font.pixelSize:16;clip:true;selectByMouse:true;text:fixtureExportUrl}
        }
        Row {
            width:parent.width;spacing:24
            Rectangle {
                id:preview;width:440;height:280;color:"#202426"
                Image {id:original;anchors.fill:parent;source:notes.previewUrl;fillMode:Image.PreserveAspectFit;cache:false;onStatusChanged:marks.requestPaint()}
                Text { textFormat:Text.PlainText;visible:original.status!==Image.Ready;anchors.centerIn:parent;width:parent.width-32;horizontalAlignment:Text.AlignHCenter;wrapMode:Text.Wrap;text:notes.selectedNote && notes.selectedNote.imageStatus!=="none"?"Image "+notes.selectedNote.imageStatus+". Written note is retained.":"No image attached";color:"#aaaead";font.pixelSize:19}
                Canvas {
                    id:marks;anchors.fill:parent
                    property var annotations:notes.draft.annotations
                    onAnnotationsChanged:requestPaint()
                    onPaint:{
                        var c=getContext("2d");c.clearRect(0,0,width,height);if(original.status!==Image.Ready)return;
                        var w=original.paintedWidth,h=original.paintedHeight,ox=(width-w)/2,oy=(height-h)/2;
                        annotations.forEach(function(m){var x=ox+m.x1*w,y=oy+m.y1*h,x2=ox+m.x2*w,y2=oy+m.y2*h;c.strokeStyle=m.colour==="dark"?"#101214":m.colour==="light"?"#ffffff":"#ffc057";c.fillStyle=c.strokeStyle;c.lineWidth=3;c.beginPath();
                            if(m.kind==="ellipse")c.ellipse(x,y,x2-x,y2-y);
                            else if(m.kind==="rectangle")c.rect(x,y,x2-x,y2-y);
                            else if(m.kind==="arrow"){c.moveTo(x,y);c.lineTo(x2,y2);var a=Math.atan2(y2-y,x2-x);c.moveTo(x2,y2);c.lineTo(x2-14*Math.cos(a-.45),y2-14*Math.sin(a-.45));c.moveTo(x2,y2);c.lineTo(x2-14*Math.cos(a+.45),y2-14*Math.sin(a+.45));}
                            if(m.kind==="text"){c.font="16px sans-serif";c.fillText(m.text,x,y);}else c.stroke();
                        });
                    }
                }
                MouseArea {
                    anchors.fill:parent;property var start:null
                    function point(x,y){var w=original.paintedWidth,h=original.paintedHeight;return {x:Math.max(0,Math.min(1,(x-(width-w)/2)/w)),y:Math.max(0,Math.min(1,(y-(height-h)/2)/h))};}
                    onPressed:if(original.status===Image.Ready)start=point(mouse.x,mouse.y)
                    onReleased:if(start){var end=point(mouse.x,mouse.y);if(Math.abs(end.x-start.x)>.01&&Math.abs(end.y-start.y)>.01)notes.addAnnotation({kind:"ellipse",x1:Math.min(start.x,end.x),y1:Math.min(start.y,end.y),x2:Math.max(start.x,end.x),y2:Math.max(start.y,end.y),text:"",colour:"amber"});start=null;}
                }
            }
            Rectangle {
                width:parent.width-preview.width-24;height:280;color:"#202426"
                TextEdit {id:editor;textFormat:TextEdit.PlainText;anchors.fill:parent;anchors.margins:14;text:notes.draft.text;color:"#eff0ee";font.pixelSize:21;wrapMode:TextEdit.Wrap;selectByMouse:true;onTextChanged:if(text!==notes.draft.text)notes.setText(text)}
            }
        }
        Rectangle {
            width:parent.width;height:38;color:"#262b2e"
            TextInput {id:query;anchors.fill:parent;anchors.margins:8;color:"#eff0ee";font.pixelSize:16;clip:true;selectByMouse:true;onTextChanged:rows.model=notes.search(text,true).matches || []}
        }
        ListView {
            id:rows;width:parent.width;height:96;clip:true;model:notes.notebook.notes
            delegate:Item {
                width:rows.width;height:34
                Text { textFormat:Text.PlainText;width:parent.width-130;elide:Text.ElideRight;text:(modelData.cleared?"Cleared · ":"")+modelData.text;color:"#eff0ee";font.pixelSize:17}
                Text { textFormat:Text.PlainText;anchors.right:parent.right;text:modelData.cleared?"Restore":"Open";color:"#aaaead";font.pixelSize:17}
                MouseArea {anchors.fill:parent;onClicked:{if(modelData.cleared)notes.restore(modelData.id);else notes.select(modelData.id);editor.text=notes.draft.text;}}
            }
        }
        Text { textFormat:Text.PlainText;width:parent.width;wrapMode:Text.Wrap;text:notes.lastError || window.notice;color:notes.lastError?"#ffc057":"#aaaead";font.pixelSize:17}
    }
    Timer {
        interval:300;repeat:true;running:fixtureSmoke||fixtureReopen;property int stage:0
        onTriggered:{try {
            if(stage===0&&fixtureReopen){
                if(!notes.open("fixture:edition:one",{})||!notes.selectedNote||notes.draft.text!=="Synthetic edited note. Written by the fixture."||notes.draft.annotations.length!==1)throw new Error("Stored note or annotation did not survive a fresh process");
                editor.text=notes.draft.text;stage=2;return;
            }
            if(stage===0){if(!notes.open("fixture:edition:one",{}))throw new Error(notes.lastError);notes.setText("Synthetic stopping note. No game observation.");if(!notes.importOriginal(fixtureImageUrl))throw new Error(notes.lastError);notes.addAnnotation({kind:"ellipse",x1:.15,y1:.2,x2:.55,y2:.65,text:"",colour:"amber"});if(!notes.save())throw new Error(notes.lastError);stage++;return;}
            if(stage===1){notes.setText("Synthetic edited note. Written by the fixture.");if(!notes.save())throw new Error(notes.lastError);var id=notes.selectedNoteId;if(!notes.clear()||!notes.restore(id)||!notes.makeStopping(id))throw new Error(notes.lastError);if(!notes.open(notes.editionId,{}))throw new Error(notes.lastError);editor.text=notes.draft.text;stage++;return;}
            if(original.status!==Image.Ready && stage++<20)return;
            if(original.status!==Image.Ready)throw new Error("Synthetic imported image did not render");
            if(!fixtureReopen){var exported=notes.exportTo(fixtureExportUrl);if(!exported.ok)throw new Error(exported.error);}
            stop();window.contentItem.grabToImage(function(result){if(!result.saveToFile(fixtureScreenshotPath)){console.error("STOPPING_FIXTURE_FAIL: capture");Qt.exit(1);}else{console.log(fixtureReopen?"STOPPING_FIXTURE_REOPEN_PASS: fresh process reopened original, note and annotation":"STOPPING_FIXTURE_PASS: real local storage, explicit original, annotation, edit, clear/restore/reopen and private export");Qt.exit(0);}});
        }catch(error){console.error("STOPPING_FIXTURE_FAIL: "+error);Qt.exit(1);}}
    }
}
