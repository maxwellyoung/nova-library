import QtQuick 2.15

Item {
    id: root
    objectName: "failurePreview"
    property var report: ({})
    property var bridge: null
    property string sans: ""
    property real unit: 1
    property real textScale: 1
    property real usableHeight: height
    property color ground: "#0c0d0e"
    property color ink: "#e9eaea"
    property color quiet: "#999999"
    property int selected: 0
    property string notice: ""
    property bool exported: false
    property string copyToken: ""
    property string copyRequest: ""
    readonly property string summary: {
        try {
            var data=JSON.parse(report.text || "{}");
            if(data.facts && data.facts.length) {
                if(data.facts[0].code==="runtime-request-refused")return "The launch request was refused.";
                return data.facts[0].statement;
            }
        } catch(error) {}
        return "The operation reported a failure.";
    }
    readonly property string storageSummary: {
        try {
            var data=JSON.parse(report.text || "{}"),space=data.localEvidence && data.localEvidence.appDataStorage;
            if(!space)return "";
            if(space.status==="measured" && space.scope==="app-data-volume" && space.method==="fstatvfs"
                    && typeof space.totalBytes==="number" && space.totalBytes>0 && space.totalBytes<=9007199254740991
                    && Math.floor(space.totalBytes)===space.totalBytes && typeof space.availableBytes==="number"
                    && isFinite(space.availableBytes) && space.availableBytes>=0 && space.availableBytes<=space.totalBytes
                    && Math.floor(space.availableBytes)===space.availableBytes) {
                var amount=space.availableBytes,units=["B","KiB","MiB","GiB","TiB","PiB"],index=0;
                while(amount>=1024 && index<units.length-1){amount/=1024;index++;}
                return "Launcher data volume: "+(index?amount.toFixed(1):String(amount))+" "+units[index]+" available at capture.";
            }
            return "Launcher data volume: free space unavailable.";
        } catch(error) {return "";}
    }
    readonly property bool canExport: {
        try{return bridge && bridge.capabilities().exportAvailable===true;}catch(error){return false;}
    }
    readonly property bool copySupported: {
        try{return bridge && typeof bridge.copyPrivateExport==="function" && bridge.capabilities().documentCopyAvailable===true;}catch(error){return false;}
    }
    readonly property bool canCopy: exported && copyToken!=="" && copySupported
    readonly property bool copyBusy: !!(canCopy && bridge.documentCopyBusy)
    signal back()
    function px(v){return Math.round(v*unit);}
    function fs(v){return Math.round(v*unit*textScale);}
    onReportChanged: {selected=0;notice="";exported=false;copyToken="";copyRequest="";body.contentY=0;}
    function exportReport() {
        if(exported || !canExport || !report.ticket)return;
        var result;
        try{result=bridge.exportPreview(report.ticket,report.sha256);}catch(error){result=null;}
        selected=0;
        if(result && result.ok===true && result.exported===true && result.sent===false) {
            copyToken=/^[a-f0-9]{32}$/.test(result.copyToken || "")?result.copyToken:"";
            exported=true;notice="Saved privately"+(/^failure-[a-f0-9]{32}\.json$/.test(result.fileName || "")?" as "+result.fileName:"")+". Nothing was sent.";
            if(copyToken!=="" && copySupported)notice+=" Save a copy opens the system chooser; its destination may be outside private storage.";
        } else notice=result && result.error==="preview_changed"?"This preview is no longer current. Go Back and review the failure again.":"The report could not be saved privately. Existing files were kept. Go Back to review again.";
    }
    function copyReport() {
        if(!canCopy || copyBusy)return;
        var result;
        try{result=bridge.copyPrivateExport(copyToken,report.sha256);}catch(error){result=null;}
        selected=0;
        if(result && result.ok===true && result.pending===true && /^[a-f0-9]{32}$/.test(result.request || "")) {
            copyRequest=result.request;notice="Choose a new document for this exact report. Its provider controls storage and sync.";
        } else notice=result && result.error==="export_changed"?"This report is no longer current. Go Back and review again. The private report was kept."
            :result && result.error==="document_copy_busy"?"A document copy is already in progress. The private report was kept."
            :"The document chooser could not open for this report. The private report was kept.";
    }
    function secondaryAction(){if(exported)copyReport();else exportReport();}
    Connections {
        target:root.bridge;ignoreUnknownSignals:true
        function onDocumentCopyFinished(request,result){
            if(request!==root.copyRequest)return;
            root.copyRequest="";root.selected=0;
            root.notice=result && typeof result.message==="string"?result.message:"The document copy could not be verified. The private report was kept.";
        }
    }
    function handleKey(event,keys) {
        event.accepted=true;
        if(event.isAutoRepeat && !(keys.isUp(event)||keys.isDown(event)))return;
        if(keys.isCancel(event)){back();return;}
        if(keys.isLeft(event))selected=0;
        else if(keys.isRight(event) && (canCopy && !copyBusy || !exported && canExport))selected=1;
        else if(keys.isUp(event))body.contentY=Math.max(0,body.contentY-px(100));
        else if(keys.isDown(event))body.contentY=Math.min(Math.max(0,body.contentHeight-body.height),body.contentY+px(100));
        else if(keys.isAccept(event)){if(selected===0)back();else secondaryAction();}
    }
    Rectangle {anchors.fill:parent;color:root.ground}
    MouseArea {anchors.fill:parent}
    Column {
        id: heading
        x:root.px(64);y:root.px(42);width:root.width-root.px(128);spacing:root.px(10)
        Text {text:"Failure report preview";width:parent.width;color:root.ink;font.family:root.sans;font.pixelSize:root.fs(34);wrapMode:Text.Wrap}
        Text {text:root.summary+" Cause unknown. Current setup is unverified.";width:parent.width;color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(21);wrapMode:Text.Wrap}
        Text {objectName:"failurePreviewStorage";text:root.storageSummary;visible:text!=="";width:parent.width;color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(21);wrapMode:Text.Wrap}
    }
    Flickable {
        id:body;objectName:"failurePreviewBody"
        x:root.px(64);y:heading.y+heading.height+root.px(20);width:root.width-root.px(128)
        height:Math.max(0,status.y-root.px(16)-y);contentWidth:width;contentHeight:json.height;clip:true;boundsBehavior:Flickable.StopAtBounds
        Text {id:json;objectName:"failurePreviewJson";width:body.width;text:root.report.text || "";textFormat:Text.PlainText;wrapMode:Text.WrapAnywhere;color:root.ink;font.family:"monospace";font.pixelSize:root.fs(17)}
    }
    Text {
        id:status;objectName:"failurePreviewStatus"
        x:root.px(64);width:root.width-root.px(128);y:buttons.y-root.px(16)-height
        text:root.notice || (root.canExport?"Review the complete report above. Export creates a new private file; it does not share or repair anything. ↑ ↓ to read.":"Private export is unavailable in this build. You can review the report here; nothing was sent.")
        textFormat:Text.PlainText;wrapMode:Text.Wrap;color:root.quiet;font.family:root.sans;font.pixelSize:root.fs(20)
    }
    Row {
        id:buttons;x:root.px(64);y:root.usableHeight-root.px(32)-height;spacing:root.px(24)
        Repeater {
            model:root.canCopy?["Back",root.copyBusy?"Choosing document…":"Save a copy…"]:root.exported || !root.canExport?["Back"]:["Back","Export privately"]
            delegate:Rectangle {
                objectName:index===0?"failurePreviewBack":root.exported?"failurePreviewCopy":"failurePreviewExport"
                width:Math.max(root.px(130),label.implicitWidth+root.px(40));height:Math.max(44,root.px(56))
                color:"transparent";border.width:root.selected===index?Math.max(1,root.px(2)):0;border.color:root.ink
                Text {id:label;anchors.centerIn:parent;text:modelData;color:root.ink;font.family:root.sans;font.pixelSize:root.fs(22)}
                enabled:index===0 || !root.copyBusy
                MouseArea {anchors.fill:parent;onClicked:{root.selected=index;if(index===0)root.back();else root.secondaryAction();}}
                Accessible.role:Accessible.Button
                Accessible.name:modelData
                Accessible.onPressAction:{if(index===0)root.back();else root.secondaryAction();}
            }
        }
    }
}
