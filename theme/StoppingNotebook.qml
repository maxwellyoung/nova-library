import QtQuick 2.15
import QtQml 2.15
import "library.js" as Lib

// A local notebook for an exact edition. Existing synced checkpoints are read-only
// context here; copying one is explicit and does not resolve its original conflict.
Item {
    id: panel
    objectName: "stoppingNotebook"
    property var storage: null
    property var keyMap: null
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property color quiet: "#9a9b9b"
    property color slab: "#1a1c1e"
    property string fontFamily: ""
    property real unit: 1
    property real textScale: 1
    property real bottomLimit: height
    property string title: ""
    property string edition: ""
    property var legacy: ({})
    property bool legacyEditable: false
    readonly property bool showingLegacy: opened && !notes.dirty && !notes.selectedNoteId && !notes.notebook.notes.length && !!legacy.text
    property string mode: "read" // read | edit | history | confirm | mark
    property real markerX: 0.5
    property real markerY: 0.5
    property var markerStart: null
    property string confirmKind: ""
    property string pendingAction: ""
    property int actionIndex: 0
    property int historyIndex: 0
    property var history: []
    property var imageChoices: []
    property bool searching: false
    property string query: ""
    property string message: ""
    property bool opened: false
    property bool backArmed: false
    readonly property bool hasImage: opened && notes.draft.imageId !== ""
    readonly property bool cleared: opened && notes.selectedNote && notes.selectedNote.cleared === true
    readonly property string kAccept: Lib.keyLabel(keyMap ? keyMap.accept : null,"A")
    readonly property string kCancel: Lib.keyLabel(keyMap ? keyMap.cancel : null,"B")
    readonly property string kDetails: Lib.keyLabel(keyMap ? keyMap.details : null,"X")
    readonly property var model: notes
    signal editCheckpoint(string editionId)
    signal closed()
    signal changed(string editionId)
    signal editingChanged(bool active)
    function px(v) { return Math.round(v*unit); }
    function fs(v) { return Math.round(v*unit*textScale); }
    StoppingNoteModel { id: notes; storage: panel.storage }

    function open(entry, descriptor, displayLabel) {
        if (notes.dirty) return false;
        edition=entry.id;title=displayLabel || Lib.displayTitle(entry);legacy=descriptor || {};
        mode="read";message="";query="";actionIndex=0;historyIndex=0;backArmed=false;
        opened=notes.open(edition,legacy);body.contentY=0;
        return opened;
    }
    Connections {target:notes;function onDraftChanged(){if(editor.text!==notes.draft.text)editor.text=notes.draft.text;}}
    function errorText(code) {
        var messages={revision_conflict:"This notebook changed while you were writing. Your draft is still here.",
            write_failed:"The note could not be saved. Your draft is still here.",storage_busy:"The notebook is busy. Try again; your draft is still here.",
            storage_unavailable:"The local notebook is unavailable.",corrupt_metadata:"This notebook could not be read. Its stored files have been preserved.",
            explicit_edition_id_required:"This game needs a stable edition identity before it can have a notebook.",
            invalid_note:"The note could not be saved. Check its text and attached image.",note_limit:"This edition has reached its retained-note limit.",
            image_unreadable_or_too_large:"That image could not be read or is too large.",unsupported_or_corrupt_image:"Choose a valid PNG, JPEG or WebP image.",
            original_storage_limit:"This edition has reached its original-image limit.",original_copy_conflict:"The stored original differs from the selected image. Neither has been replaced."};
        return messages[code] || "That action could not be completed. Your stored notes and draft have been kept.";
    }
    function notify() { changed(edition); }
    function save() {
        if (!opened || cleared || notes.draft.text.length>4000) return;
        if (!notes.draft.text.trim() && !hasImage) {message="Write a note or attach an image first.";return;}
        if (notes.save()) {message="Saved on this device.";stopEditing();mode="read";actionIndex=0;notify();}
    }
    function edit() { if (!opened || cleared) return;mode="edit";editingChanged(true);editor.forceActiveFocus();Qt.inputMethod.show(); }
    function stopEditing() { if(mode === "edit")mode="read";editor.focus=false;historySearch.focus=false;searching=false;Qt.inputMethod.commit();Qt.inputMethod.hide();editingChanged(false); }
    function request(action) {
        stopEditing();
        if (notes.dirty) {pendingAction=action;confirmKind="discard";mode="confirm";actionIndex=0;return;}
        perform(action);
    }
    function perform(action) {
        mode="read";actionIndex=0;
        if (action === "close") {closed();return;}
        if (action === "legacy") {editCheckpoint(edition);return;}
        if (action === "new") {notes.beginNew();edit();return;}
        if (action === "history") {query="";refreshHistory();mode="history";historyIndex=0;return;}
        if (action === "reload") {opened=notes.open(edition,legacy);message=opened?"Stored notebook reopened.":"";return;}
    }
    function refreshHistory() {
        // Filter the already-open bounded notebook snapshot; typing never rereads
        // every immutable original from storage or replaces a dirty draft.
        var q=query.toLowerCase();
        history=(notes.notebook.notes || []).filter(function(n){
            var content=n.text+"\n"+(n.annotations || []).map(function(m){return m.text;}).join("\n");
            return !q || content.toLowerCase().indexOf(q)>=0;
        }).slice().reverse();
        historyIndex=Math.min(historyIndex,Math.max(0,history.length-1));
    }
    function beginFind(){searching=true;historySearch.forceActiveFocus();Qt.inputMethod.show();}
    onQueryChanged:if(mode === "history")refreshHistory()
    function chooseHistory(index) {
        if (index<0 || index>=history.length) return;
        if (notes.select(history[index].id)) {mode="read";actionIndex=0;body.contentY=0;message="";}
    }
    function back() {
        if (mode === "confirm") {mode="read";actionIndex=0;return;}
        if (mode === "images") {mode="read";actionIndex=0;return;}
        if (mode === "mark") {mode="read";markerStart=null;return;}
        if (mode === "edit") {stopEditing();mode="read";actionIndex=0;return;}
        if (mode === "history" && searching) {stopEditing();return;}
        if (mode === "history") {mode="read";actionIndex=0;return;}
        request("close");
    }
    function actions() {
        if (mode === "confirm") return [{id:"keep",label:confirmKind === "clear"?"Keep note":"Keep draft"},
            {id:"confirm",label:confirmKind === "clear"?"Clear note":"Discard draft"}];
        if (!opened) return [{id:"reload",label:"Try again"}].concat(legacyEditable?[{id:"legacy",label:legacy.text?"Edit checkpoint":"Write checkpoint"}]:[]);
        if (cleared) return [{id:"restore",label:"Restore note"},{id:"history",label:"Earlier notes"},{id:"new",label:"New note"}];
        var list=[];
        if (notes.dirty) list.push({id:"save",label:"Save note"});
        if (notes.conflictingNotebook) list.push({id:"branch",label:"Keep as new note"},{id:"reload",label:"Reopen stored"});
        if(showingLegacy)list.push({id:"adopt",label:"Keep this note locally"});
        list.push({id:"edit",label:notes.selectedNoteId?"Edit text":legacy.text?"Write new note":"Write note"});
        if (notes.selectedNoteId && notes.notebook.stoppingNoteId!==notes.selectedNoteId && !notes.dirty)
            list.push({id:"stopping",label:"Show on Home"});
        if (notes.notebook.notes.length) list.push({id:"history",label:"Earlier notes"});
        if (notes.selectedNoteId || notes.dirty) list.push({id:"new",label:"New note"});
        if (typeof storage.imageChoices === "function")list.push({id:"attach",label:"Attach screenshot"});
        if (hasImage && notes.previewUrl && notes.draft.annotations.length<32) list.push({id:"mark",label:"Mark image"});
        if (hasImage) list.push({id:"detach",label:"Remove image"});
        if (legacy.text && !showingLegacy) list.push({id:"adopt",label:"Copy checkpoint"});
        if (legacy.text && legacyEditable) list.push({id:"legacy",label:"Edit checkpoint"});
        if (notes.selectedNoteId && !notes.dirty) list.push({id:"clear",label:"Clear note"});
        return list;
    }
    function activate(index) {
        var a=actions()[index];if (!a) return;
        var id=a.id;
        if (id === "keep") {mode="read";actionIndex=0;return;}
        if (id === "confirm") {
            if (confirmKind === "clear") {if(notes.clear()){mode="read";message="Cleared. Restore it from Earlier notes.";notify();}}
            else {if(notes.open(edition,legacy))perform(pendingAction);else mode="read";}
            actionIndex=0;return;
        }
        if (id === "save") save();
        else if (id === "edit") edit();
        else if (id === "history" || id === "new" || id === "reload" || id === "legacy") request(id);
        else if (id === "clear") {confirmKind="clear";mode="confirm";actionIndex=0;}
        else if (id === "restore") {if(notes.restore(notes.selectedNoteId)){message="Restored. Choose Show on Home to use it there.";notify();}}
        else if (id === "stopping") {if(notes.makeStopping(notes.selectedNoteId)){message="Shown on Home.";notify();}}
        else if (id === "attach") {
            var result=notes.call("imageChoices",[]);
            if(result.ok){imageChoices=result.choices;historyIndex=0;mode="images";message=result.more?"Showing the latest 64 readable images in Pictures/Screenshots.":"From Pictures/Screenshots. Choose one original to copy locally.";}
            else message="The screenshot folder isn't accessible here. No permissions were changed.";
        }
        else if (id === "mark") {mode="mark";markerStart=null;markerX=.5;markerY=.5;}
        else if (id === "detach") {notes.detachImage();actionIndex=0;}
        else if (id === "adopt") {
            if (notes.dirty) {message="Save or discard your draft before copying a checkpoint.";return;}
            if (notes.adoptLegacy()){message="Copied locally. The original checkpoint is unchanged.";notify();}
        } else if (id === "branch") {if(notes.keepDraftAsNew()){message="Saved as another note. Both versions are retained.";actionIndex=0;notify();}}
    }
    // Called only with an explicitly selected original, never a title/cover guess.
    function importSelectedOriginal(url) {
        if (!opened || cleared) return false;
        var ok=notes.importOriginal(url);if(ok){message="Image attached to draft. Save note to keep the association.";actionIndex=0;}
        return ok;
    }
    function markPoint() {
        if(notes.draft.annotations.length>=32){message="This note already has 32 marks.";mode="read";return;}
        if(!markerStart){markerStart={x:markerX,y:markerY};return;}
        if(Math.abs(markerX-markerStart.x)<.01 || Math.abs(markerY-markerStart.y)<.01){message="Choose an opposite corner with some width and height.";return;}
        notes.addAnnotation({kind:"ellipse",x1:Math.min(markerStart.x,markerX),y1:Math.min(markerStart.y,markerY),x2:Math.max(markerStart.x,markerX),y2:Math.max(markerStart.y,markerY),text:"",colour:"amber"});
        mode="read";markerStart=null;actionIndex=0;message="Mark added to the draft. Save note to keep it.";
    }
    function chooseImage(index){
        if(index<0 || index>=imageChoices.length)return;
        if(importSelectedOriginal(imageChoices[index].fileUrl))mode="read";
    }
    function hints() {
        if(mode === "images")return [{k:kAccept,l:"Attach image",a:"notebook:image"},{k:"↑ ↓",l:"Browse",a:"notebook:imagedown"},{k:kCancel,l:"Back",a:"notebook:back"}];
        if(mode === "mark")return [{k:"↑ ↓ ← →",l:"Move",a:"notebook:move"},{k:kAccept,l:markerStart?"Opposite corner":"First corner",a:"notebook:mark"},{k:kCancel,l:"Done marking",a:"notebook:back"}];
        if(mode === "edit")return [{k:kDetails,l:"Save note",a:"notebook:save"},{k:kCancel,l:"Done typing",a:"notebook:back"}];
        if(mode === "history" && searching)return [{k:kCancel,l:"Done typing",a:"notebook:back"}];
        if(mode === "history")return [{k:kDetails,l:"Find",a:"notebook:find"},{k:kAccept,l:"Open note",a:"notebook:choose"},{k:"↑ ↓",l:"Browse",a:"notebook:down"},{k:kCancel,l:"Back",a:"notebook:back"}];
        return [{k:kAccept,l:"Select",a:"notebook:activate"},
            {k:kCancel,l:"Back",a:"notebook:back"}];
    }
    function runHint(id) {
        if(id === "image")chooseImage(historyIndex);else if(id === "imagedown")historyIndex=Math.min(imageChoices.length-1,historyIndex+1);else if(id === "mark")markPoint();else if(id === "find")beginFind();else if(id === "save")save();else if(id === "back")back();else if(id === "choose")chooseHistory(historyIndex);
        else if(id === "down")historyIndex=Math.min(history.length-1,historyIndex+1);else activate(actionIndex);
    }
    function handleKey(event) {
        event.accepted=true;
        if(event.key === Qt.Key_Back){backArmed=true;return;}
        if(keyMap.isCancel(event)){back();return;}
        if(mode === "images"){
            if(keyMap.isUp(event))historyIndex=Math.max(0,historyIndex-1);
            else if(keyMap.isDown(event))historyIndex=Math.min(imageChoices.length-1,historyIndex+1);
            else if(keyMap.isAccept(event)&&!event.isAutoRepeat)chooseImage(historyIndex);
            return;
        }
        if(mode === "mark"){
            if(keyMap.isLeft(event))markerX=Math.max(0,markerX-.025);
            else if(keyMap.isRight(event))markerX=Math.min(1,markerX+.025);
            else if(keyMap.isUp(event))markerY=Math.max(0,markerY-.025);
            else if(keyMap.isDown(event))markerY=Math.min(1,markerY+.025);
            else if(keyMap.isAccept(event)&&!event.isAutoRepeat)markPoint();
            return;
        }
        if(mode === "edit") {if(keyMap.isDetails(event))save();return;}
        if(mode === "history") {
            if(keyMap.isDetails(event)){beginFind();return;}
            if(searching)return;
            if(keyMap.isUp(event))historyIndex=Math.max(0,historyIndex-1);
            else if(keyMap.isDown(event))historyIndex=Math.min(history.length-1,historyIndex+1);
            else if(keyMap.isAccept(event))chooseHistory(historyIndex);
            return;
        }
        if(keyMap.isLeft(event))actionIndex=Math.max(0,actionIndex-1);
        else if(keyMap.isRight(event))actionIndex=Math.min(actions().length-1,actionIndex+1);
        else if(keyMap.isAccept(event)&&!event.isAutoRepeat)activate(actionIndex);
        else if(keyMap.isUp(event))body.contentY=Math.max(0,body.contentY-px(96));
        else if(keyMap.isDown(event))body.contentY=Math.min(Math.max(0,body.contentHeight-body.height),body.contentY+px(96));
    }
    function handleKeyRelease(event) {
        if(event.key === Qt.Key_Back){event.accepted=true;var armed=backArmed;backArmed=false;if(armed)back();}
    }
    onActionIndexChanged: rail.positionViewAtIndex(actionIndex,ListView.Contain)
    onHistoryIndexChanged: historyList.positionViewAtIndex(historyIndex,ListView.Contain)
    onEnabledChanged: if(!enabled){stopEditing();backArmed=false;}
    Connections {target:Qt.application;function onStateChanged(){if(Qt.application.state!==Qt.ApplicationActive){panel.stopEditing();panel.backArmed=false;}}}
    onVisibleChanged: if(!visible){stopEditing();backArmed=false;}
    Component.onDestruction: Qt.inputMethod.hide()

    Text {
        id:heading;x:px(64);y:px(54);width:parent.width-px(128)
        text: mode === "images"?"Attach a screenshot":mode === "history"?"Earlier notes":mode === "confirm"?(confirmKind === "clear"?"Clear this note?":"Keep your draft?"):"Where was I?"
        textFormat:Text.PlainText;color:ink;font.family:fontFamily;font.pixelSize:fs(38);font.weight:Font.DemiBold
    }
    Text {
        id:subtitle;anchors.top:heading.bottom;anchors.topMargin:px(10);x:px(64);width:parent.width-px(128)
        text:title+(cleared?" · Cleared":notes.dirty?" · Unsaved draft":"")
        textFormat:Text.PlainText;color:quiet;font.family:fontFamily;font.pixelSize:fs(22);maximumLineCount:2;elide:Text.ElideRight;wrapMode:Text.Wrap
    }
    Item {
        id:content;x:px(64);y:subtitle.y+subtitle.height+px(24);width:parent.width-px(128)
        height:Math.max(0,bottomLimit-px(222)-y)
        visible:mode!=="history" && mode!=="images" && mode!=="confirm"
        Item {
            id:imageArea;width:panel.hasImage && mode!=="edit"?Math.floor(parent.width*.45):0;height:parent.height
            visible:width>0
            Image {id:original;objectName:"notebookOriginal";anchors.fill:parent;source:notes.previewUrl || "";fillMode:Image.PreserveAspectFit;verticalAlignment:Image.AlignTop;asynchronous:true;cache:false}
            Canvas {
                id:annotationsCanvas
                anchors.fill:parent;property var marks:notes.draft.annotations
                onMarksChanged:requestPaint()
                Connections {target:original;function onStatusChanged(){annotationsCanvas.requestPaint();}}
                onWidthChanged:requestPaint();onHeightChanged:requestPaint()
                onPaint:{var c=getContext("2d");c.clearRect(0,0,width,height);if(original.status!==Image.Ready)return;
                    var w=original.paintedWidth,h=original.paintedHeight,ox=(width-w)/2,oy=0;
                    marks.forEach(function(m){var x=ox+m.x1*w,y=oy+m.y1*h,x2=ox+m.x2*w,y2=oy+m.y2*h;
                        c.strokeStyle=m.colour==="dark"?"#101214":m.colour==="light"?"#ffffff":"#ffc057";c.fillStyle=c.strokeStyle;c.lineWidth=Math.max(2,panel.px(3));c.beginPath();
                        if(m.kind==="ellipse")c.ellipse(x,y,x2-x,y2-y);else if(m.kind==="rectangle")c.rect(x,y,x2-x,y2-y);
                        else if(m.kind==="arrow"){c.moveTo(x,y);c.lineTo(x2,y2);var a=Math.atan2(y2-y,x2-x);c.moveTo(x2,y2);c.lineTo(x2-12*Math.cos(a-.45),y2-12*Math.sin(a-.45));c.moveTo(x2,y2);c.lineTo(x2-12*Math.cos(a+.45),y2-12*Math.sin(a+.45));}
                        if(m.kind==="text"){c.font=panel.fs(18)+"px sans-serif";c.fillText(m.text,x,y);}else c.stroke();});}
            }
            Item {
                visible:mode === "mark" && original.status===Image.Ready
                x:(imageArea.width-original.paintedWidth)/2+panel.markerX*original.paintedWidth
                y:panel.markerY*original.paintedHeight
                Rectangle {x:-panel.px(10);y:-1;width:panel.px(20);height:2;color:panel.ink}
                Rectangle {x:-1;y:-panel.px(10);width:2;height:panel.px(20);color:panel.ink}
            }
            MouseArea {
                anchors.fill:parent;enabled:mode === "mark" && original.status===Image.Ready
                property bool dragging:false
                function point(x,y){panel.markerX=Math.max(0,Math.min(1,(x-(width-original.paintedWidth)/2)/original.paintedWidth));panel.markerY=Math.max(0,Math.min(1,y/original.paintedHeight));}
                onPressed:{point(mouse.x,mouse.y);panel.markerStart=null;panel.markPoint();dragging=true;}
                onPositionChanged:if(dragging)point(mouse.x,mouse.y)
                onReleased:if(dragging){point(mouse.x,mouse.y);panel.markPoint();dragging=false;}
                onCanceled:{dragging=false;panel.markerStart=null;}
            }
            Text {anchors.centerIn:parent;width:parent.width;visible:!notes.previewUrl || original.status===Image.Error;text:"Original image unavailable.\nYour text and annotations are retained.";textFormat:Text.PlainText;wrapMode:Text.Wrap;color:quiet;font.family:fontFamily;font.pixelSize:fs(22)}
        }
        Flickable {
            id:body;objectName:"notebookBody";x:imageArea.width?imageArea.width+px(32):0;width:parent.width-x;height:parent.height;clip:true
            contentWidth:width;contentHeight:mode==="edit"?editor.height:reading.implicitHeight;boundsBehavior:Flickable.StopAtBounds
            Text {
                id:reading;objectName:"notebookReading";width:parent.width;visible:mode!=="edit";textFormat:Text.PlainText
                text:!opened?panel.errorText(notes.lastError):panel.showingLegacy?"Existing checkpoint:\n"+panel.legacy.text:notes.draft.text || (panel.hasImage?"":"Write down the room, objective or clue you want to return to.")
                color:!opened||(!notes.draft.text&&!showingLegacy)?quiet:ink;font.family:fontFamily;font.pixelSize:fs(28);wrapMode:Text.Wrap
            }
            TextEdit {
                id:editor;objectName:"notebookEditor";width:parent.width;height:Math.max(body.height,implicitHeight);visible:mode==="edit";textFormat:TextEdit.PlainText
                color:ink;selectionColor:quiet;selectedTextColor:ground;font.family:fontFamily;font.pixelSize:fs(28);wrapMode:TextEdit.Wrap;selectByMouse:true
                text:"";onTextChanged:if(panel.opened && text!==notes.draft.text)notes.setText(text)
                onCursorRectangleChanged:{if(cursorRectangle.y<body.contentY)body.contentY=cursorRectangle.y;else if(cursorRectangle.y+cursorRectangle.height>body.contentY+body.height)body.contentY=cursorRectangle.y+cursorRectangle.height-body.height;}
            }
        }
    }
    Text {
        visible:mode==="confirm";x:px(64);y:subtitle.y+subtitle.height+px(40);width:parent.width-px(128)
        text:confirmKind === "clear"?"The note and original image will be retained. You can restore the note from Earlier notes.":"Your changes have not been saved. Keep the draft, or discard it before continuing."
        color:ink;textFormat:Text.PlainText;font.family:fontFamily;font.pixelSize:fs(26);wrapMode:Text.Wrap
    }
    Item {
        id:findField;visible:mode === "history";x:px(64);y:subtitle.y+subtitle.height+px(20);width:parent.width-px(128);height:px(52)
        TextInput {id:historySearch;objectName:"notebookSearch";anchors.fill:parent;color:ink;selectedTextColor:ground;selectionColor:quiet;font.family:fontFamily;font.pixelSize:fs(23);clip:true;selectByMouse:true;text:panel.query;onTextChanged:if(text!==panel.query)panel.query=text;onActiveFocusChanged:if(activeFocus)panel.searching=true}
        Text {visible:historySearch.text.length===0;text:"Find in these notes";color:quiet;font.family:fontFamily;font.pixelSize:fs(23)}
        Rectangle {y:parent.height-px(4);width:parent.width;height:px(1);color:quiet}
        MouseArea {anchors.fill:parent;enabled:!panel.searching;onClicked:panel.beginFind()}
    }
    ListView {
        id:historyList;objectName:"notebookHistory";visible:mode==="history" || mode==="images";x:px(64);y:mode==="images"?subtitle.y+subtitle.height+px(24):findField.y+findField.height+px(16);width:parent.width-px(128)
        height:Math.max(0,bottomLimit-px(170)-y);clip:true;model:mode==="images"?imageChoices:panel.history;currentIndex:historyIndex;boundsBehavior:Flickable.StopAtBounds
        delegate:Item {
            objectName:"notebookRow-"+index
            width:historyList.width;height:panel.px(94)
            Rectangle {x:0;y:panel.px(12);width:panel.px(3);height:parent.height-panel.px(24);color:ink;visible:index===historyIndex}
            Text {x:panel.px(8);width:parent.width-panel.px(16);text:mode==="images"?modelData.label:(modelData.cleared?"Cleared · ":"")+(modelData.text || "Image note");textFormat:Text.PlainText;color:index===historyIndex?ink:quiet;font.family:fontFamily;font.pixelSize:panel.fs(24);maximumLineCount:1;elide:Text.ElideRight}
            Text {x:panel.px(8);y:panel.px(36);width:parent.width-panel.px(16);text:modelData.updatedAt.slice(0,10)+(notes.notebook.stoppingNoteId===modelData.id?" · On Home":"");color:quiet;font.family:fontFamily;font.pixelSize:panel.fs(19)}
            MouseArea {anchors.fill:parent;onClicked:mode==="images"?panel.chooseImage(index):panel.chooseHistory(index)}
        }
        Text {visible:historyList.count===0;text:mode==="images"?"No readable images in Pictures/Screenshots.":"No earlier notes.";textFormat:Text.PlainText;color:quiet;font.family:fontFamily;font.pixelSize:fs(26)}
    }
    Text {
        id:feedback;objectName:"notebookFeedback";x:px(64);y:bottomLimit-px(214);width:parent.width-px(128)
        text:(mode==="edit"?notes.draft.text.length+" / 4000 characters. ":"")+(notes.lastError?errorText(notes.lastError):message || (showingLegacy?legacy.conflict?"This existing checkpoint has a sync conflict. It is unchanged here.":legacy.pending?"This existing checkpoint is waiting to sync.":"Existing checkpoint. Keep it locally to start a notebook.":""))
        color:quiet;textFormat:Text.PlainText;font.family:fontFamily;font.pixelSize:fs(20);wrapMode:Text.Wrap;maximumLineCount:2;elide:Text.ElideRight
    }
    ListView {
        id:rail;objectName:"notebookActions";visible:mode==="read" || mode==="confirm";x:px(64);y:bottomLimit-px(140);width:parent.width-px(128)-(contentWidth>parent.width-px(128)?px(112):0);height:px(44)
        orientation:ListView.Horizontal;spacing:px(30);clip:true;model:panel.actions();currentIndex:actionIndex;boundsBehavior:Flickable.StopAtBounds
        onModelChanged:Qt.callLater(function(){panel.actionIndex=Math.min(panel.actionIndex,Math.max(0,rail.count-1));rail.positionViewAtIndex(panel.actionIndex,ListView.Contain);})
        delegate:Item {
            objectName:"notebookAction-"+modelData.id
            width:Math.min(actionLabel.implicitWidth+panel.px(6),rail.width);height:rail.height
            opacity:x>=rail.contentX-1 && x+width<=rail.contentX+rail.width+1?1:0
            enabled:opacity===1
            Text {id:actionLabel;width:parent.width;text:modelData.label;elide:Text.ElideRight;textFormat:Text.PlainText;color:index===actionIndex?ink:quiet;font.family:fontFamily;font.pixelSize:panel.fs(24);font.weight:index===actionIndex?Font.DemiBold:Font.Normal}
            Rectangle {y:parent.height-panel.px(5);width:parent.width;height:panel.px(2);color:ink;visible:index===actionIndex}
            MouseArea {anchors.fill:parent;onClicked:{panel.actionIndex=index;panel.activate(index);}}
        }
    }
    Text {x:parent.width-px(64)-width;y:rail.y;visible:rail.visible && rail.contentWidth>rail.width;text:"← →  "+(actionIndex+1)+" / "+rail.count;color:quiet;font.family:fontFamily;font.pixelSize:fs(18)}
}
