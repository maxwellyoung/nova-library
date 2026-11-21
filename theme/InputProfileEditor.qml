import QtQuick 2.15
import "InputProfiles.js" as Profiles

FocusScope {
    id: root
    focus: true
    property var memory: null
    property var binding: null
    property string editionTitle: ""
    property var savedState: null
    property var draft: Profiles.defaults()
    property var original: Profiles.defaults()
    property bool hadProfile: false
    property string mode: "edit"
    property string message: ""
    property int index: 0
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property string sans: "sans-serif"
    property real textScale: 1
    property string acceptLabel: "A"
    property string cancelLabel: "B"
    property real s: 1
    readonly property color quiet: Qt.rgba(ink.r,ink.g,ink.b,0.66)
    readonly property bool dirty: JSON.stringify(draft)!==JSON.stringify(original)
    readonly property bool ready: savedState!==null && Profiles.binding(binding)
    signal closed()
    function px(n){return Math.round(n*s);}
    function fs(n){return Math.round(n*s*textScale);}
    function read() {
        try {
            var value=memory.checkedRead(Profiles.KEY);
            if(!value || value.ok!==true || typeof value.exists!=="boolean")return null;
            return Profiles.store(value.exists?value.value:undefined);
        }catch(e){return null;}
    }
    function open(store,key,title) {
        memory=store;binding=Profiles.copy(key);editionTitle=title;savedState=read();mode="edit";index=0;message="";
        var p=savedState?Profiles.profile(savedState,binding):null;hadProfile=!!p;
        draft=p?p.preferences:Profiles.defaults();original=Profiles.copy(draft);
        if(!ready)message="Saved preferences could not be read. Nothing will be overwritten.";
        forceActiveFocus();
    }
    function rows() {
        if(mode==="clear")return [{label:"Clear this setup’s preferences",value:"Other games stay"},{label:"Keep preferences",value:"Back"}];
        if(mode==="discard")return [{label:"Keep editing",value:"Back"},{label:"Discard unsaved changes",value:"Controls"}];
        if(!ready)return [];
        return Profiles.FIELDS.map(function(f,i){return {label:f.label,value:Profiles.display(draft,i)};})
            .concat([{label:"Save preferences",value:dirty?"Draft changes":hadProfile?"Saved here":"Starting preferences"},
                     {label:"Clear saved preferences",value:hadProfile?"This setup only":"None saved",dim:!hadProfile}]);
    }
    function persist(next) {
        var fresh=read();
        if(!fresh){message="Preferences became unavailable. Restart Library to review them; nothing was overwritten.";return false;}
        if(!Profiles.equalState(fresh,savedState)){
            message="Saved profiles changed. Go back and reopen; nothing was overwritten.";return false;
        }
        try {
            if(memory.checkedSet(Profiles.KEY,next)!==true){message="Preferences could not be saved. Your previous copy is kept.";return false;}
        }catch(e){message="Preferences could not be saved. Your previous copy is kept.";return false;}
        savedState=next;return true;
    }
    function change(direction) {
        if(mode!=="edit" || !ready || index>=Profiles.FIELDS.length)return;
        var next=Profiles.adjust(draft,index,direction);if(next)draft=next;message="";
    }
    function activate() {
        if(mode==="discard") {if(index===1)closed();else {mode="edit";index=0;}return;}
        if(mode==="clear") {
            if(index===1){mode="edit";index=Profiles.FIELDS.length+1;return;}
            var cleared=Profiles.clear(savedState,binding);
            if(cleared && persist(cleared)){
                hadProfile=false;draft=Profiles.defaults();original=Profiles.copy(draft);mode="edit";index=Profiles.FIELDS.length;
                message="Saved preferences cleared. No runtime settings changed.";
            }return;
        }
        if(!ready)return;
        if(index<Profiles.FIELDS.length){change(1);return;}
        if(index===Profiles.FIELDS.length){
            var next=Profiles.edit(savedState,binding,draft);
            if(!next){message="Profile limit or invalid preferences. Your previous copy is kept.";return;}
            if(persist(next)){hadProfile=true;original=Profiles.copy(draft);message="Saved on this device. Not applied to the game.";}return;
        }
        if(hadProfile){mode="clear";index=1;message="Only this exact edition and runtime version will be cleared.";}
    }
    function back() {
        if(mode!=="edit"){mode="edit";index=0;message="";return;}
        if(dirty){mode="discard";index=0;message="Your saved preferences are unchanged.";return;}
        closed();
    }
    function hints() {
        var out=[];
        if(ready)out.push({k:acceptLabel,l:mode!=="edit"?"Choose":index<Profiles.FIELDS.length?"Change":index===Profiles.FIELDS.length?"Save":"Review clear",a:"input:activate"});
        if(ready && mode==="edit" && index<Profiles.FIELDS.length)out.push({k:"←",l:"Less",a:"input:less"},{k:"→",l:"More",a:"input:more"});
        return out.concat([{k:cancelLabel,l:mode==="edit"?"Controls":"Back",a:"input:back"}]);
    }
    function handle(event,keys) {
        event.accepted=true;
        if(keys.isCancel(event) || event.key===Qt.Key_Back)back();
        else if(keys.isUp(event))index=Math.max(0,index-1);
        else if(keys.isDown(event))index=Math.min(rows().length-1,index+1);
        else if(keys.isLeft(event))change(-1);
        else if(keys.isRight(event))change(1);
        else if(keys.isAccept(event))activate();
        else event.accepted=false;
    }
    Rectangle { anchors.fill: parent;color:root.ground }
    Column {
        id: heading;x:root.px(64);y:root.px(50);width:parent.width-2*x;spacing:root.px(12)
        Text { width:parent.width;text:"Input preferences";font.family:root.sans;font.pixelSize:root.fs(30);font.bold:true;color:root.ink }
        Text { width:parent.width;text:root.editionTitle;font.family:root.sans;font.pixelSize:root.fs(22);color:root.ink;wrapMode:Text.Wrap;maximumLineCount:2;elide:Text.ElideRight }
        Text { width:parent.width;text:root.binding?root.binding.runtimeId+" · "+root.binding.runtimeVersion+" · Not applied":"Setup unavailable";font.family:root.sans;font.pixelSize:root.fs(19);color:root.quiet;wrapMode:Text.Wrap }
    }
    Text {
        anchors.right:parent.right;anchors.rightMargin:root.px(64);y:heading.y
        visible:root.rows().length>0;text:(root.index+1)+" / "+root.rows().length
        color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(18)
    }
    ListView {
        id:list;objectName:"inputProfileList";x:heading.x-root.px(20);y:heading.y+heading.height+root.px(24);width:heading.width+root.px(20)
        height:Math.max(0,Math.floor((footer.y-root.px(24)-y)/root.px(52))*root.px(52));clip:true;model:root.rows();currentIndex:root.index
        highlightRangeMode:ListView.ApplyRange;highlightMoveDuration:0;snapMode:ListView.SnapToItem;boundsBehavior:Flickable.StopAtBounds
        onCurrentIndexChanged:positionViewAtIndex(currentIndex,ListView.Contain)
        delegate: Item {
            objectName:"inputProfileRow_"+index
            width:list.width;height:root.px(52)
            Rectangle {x:0;y:root.px(14);width:root.px(3);height:root.px(23);color:root.ink;visible:index===root.index}
            Text {x:root.px(20);width:parent.width*0.62-root.px(20);text:modelData.label;elide:Text.ElideRight;anchors.verticalCenter:parent.verticalCenter;font.family:root.sans;font.pixelSize:root.fs(23);font.bold:index===root.index;color:index===root.index?root.ink:root.quiet}
            Text {x:parent.width*0.64;width:parent.width*0.36;text:modelData.value;elide:Text.ElideRight;anchors.verticalCenter:parent.verticalCenter;font.family:root.sans;font.pixelSize:root.fs(21);color:modelData.dim?root.quiet:root.ink}
            MouseArea {objectName:"inputProfileTouch_"+index;anchors.fill:parent;onClicked:{var panel=root;panel.index=index;panel.forceActiveFocus();panel.activate();}}
        }
    }
    Column {
        id:footer;x:heading.x;width:heading.width;y:parent.height-height-root.px(26);spacing:root.px(12)
        Text {width:parent.width;text:root.message || (root.hadProfile?"Saved preferences for this setup. Runtime support has not been checked.":"Starting preferences, not detected game settings. Saving does not apply them.");color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(18);wrapMode:Text.Wrap}

    }
}
