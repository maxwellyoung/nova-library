.pragma library

function bridge(value) {
    if (!value || typeof value.capabilities !== "function" || typeof value.openEdition !== "function"
            || typeof value.review !== "function" || typeof value.cancelReview !== "function"
            || typeof value.reviewFinished !== "function") return null;
    try { var c=value.capabilities(); return c && c.schemaVersion===1 && c.readOnly===true && c.capture===false && c.runtimeRestoreAvailable===false ? value : null; }
    catch (error) { return null; }
}
function withResult(previous,id,result) {
    var next={};Object.keys(previous).forEach(function(key){next[key]=previous[key];});next[id]=result;return next;
}
function canReview(value, data, row) {
    if(!value || typeof value.reviewSnapshot!=="function" || !data || data.ok!==true || !/^[a-f0-9]{64}$/.test(data.indexSha256 || "")
       || !row || !row.copy || row.copy.copyState!=="not-rechecked")return false;
    try{return value.capabilities().reviewSnapshotVersion===1;}catch(error){return false;}
}
function canPicture(value, data, row) {
    if(!value || typeof value.picture!=="function" || typeof value.clearPicture!=="function" || !data || !/^[a-f0-9]{64}$/.test(data.indexSha256 || "")
       || !row || !row.copy || !row.copy.picture || row.copy.picture.state!=="available")return false;
    try{return value.capabilities().pictureVersion===2;}catch(error){return false;}
}
function pictureUrl(result) {
    if(!result || result.ok!==true || result.imageChecksumMatched!==true || result.runtimeRestoreAvailable!==false
       || typeof result.imageUrl!=="string")return "";
    return /^image:\/\/nova-save-copies\/[a-f0-9]{32}$/.test(result.imageUrl)?result.imageUrl:"";
}
function storageDetail(data) {
    if(!data || data.error!=="storage_unavailable")return "";
    var location=data.storageStage==="copy-directory"?"Copied-save folder":data.storageStage==="copy-index"?"Copy index":"";
    if(!location)return "";
    var check=data.storageCheck;
    if(check==="not_found")return location+" was not found during the check.";
    if(check==="symbolic_link")return location+" is a symbolic link; this check does not follow it.";
    if(check==="wrong_type")return location+" has an unexpected file type.";
    if(check==="canonical_mismatch")return location+" path did not match its canonical location.";
    if(check==="stat_unavailable")return location+" system file check could not be completed.";
    if(check==="shared_permissions")return location+" owner-only permissions check did not pass.";
    return location+" check could not be completed.";
}
function error(code, context) {
    if(code==="storage_unavailable" && storageDetail(context))return storageDetail(context);
    if(code==="bundle_incomplete")return "The copied-save index is missing. Existing files were kept.";
    if(code==="invalid_index")return "The copied-save index did not match its expected format. Existing files were kept.";
    if(code==="index_unavailable")return "The copied-save index could not be opened. Existing files were kept.";
    if(code==="invalid_snapshot")return "The displayed save history could not be checked. Close and reopen Save copies.";
    if (code==="cancelled") return "Check cancelled. Your save copies were kept.";
    if (code==="history_changed" || code==="index_changed") return "Save history changed. Close and reopen it before checking again.";
    if (code==="checksum_mismatch" || code==="copy_unavailable_or_changed") return "This copy could not be verified. Its stored files were kept.";
    if (code==="review_busy") return "Another copy is being checked.";
    return "Save copies could not be read. Existing files were kept.";
}
function rows(data, results) {
    if (!data || data.ok!==true) return [{label:"Save copies unavailable",
        value:data && data.storageStage==="copy-directory"?"Folder check stopped":data && data.storageStage==="copy-index"?"Index check stopped":"",
        dim:true,failure:data || {}}];
    var copies=data.copies || [];
    if (!copies.length) return [{label:"No save copies here",value:"",dim:true}];
    return copies.map(function(c) {
        var kind=c.identity.kind==="native-save"?"Game save":"Emulator state";
        var result=results[c.checkpointId], state=c.copyState;
        var status=result ? result.ok===true?"Checksum matched":"Check failed" : state==="not-rechecked"?"Not rechecked":state==="missing"?"Missing":"Unavailable";
        return {label:c.name || c.capturedAt.slice(0,10),value:kind+" · "+status,copy:c,dim:state!=="not-rechecked"};
    });
}
function footer(row, result, busy, reviewAvailable) {
    if(row && row.failure)return error(row.failure.error,row.failure)+" No restore was attempted.";
    if(!row || !row.copy) return "Save copies transferred from your computer appear here. Checking a copy is separate from loading it in a game.";
    var c=row.copy,r=c.identity.runtime;
    var text=(c.name?c.name+". ":"")+"Captured "+c.capturedAt.slice(0,10)+" · "+r.name+" "+r.version+" · "+c.files+" file"+(c.files===1?"":"s")+(c.pinned?" · Kept anchor":"")+". ";
    if(busy) return text+"Checking the stored archive…";
    if(reviewAvailable===false && !result && c.copyState==="not-rechecked")return text+"Checking this displayed copy needs the matching Library build. This view does not load or replace progress.";
    if(result)text+=result.ok===true?"Archive checksum matched. Loading this copy in the game has not been verified. ":error(result.error,result)+" ";
    else text+="Archive checksum has not been rechecked here. ";
    return text+(c.identity.kind==="emulator-state"?"Emulator states depend on their exact runtime. ":"")+"This view does not load or replace progress.";
}
