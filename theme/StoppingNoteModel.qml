import QtQml 2.15

// Receipt-driven adapter. Unsaved text/marks stay in draft when storage refuses a write.
QtObject {
    id: model
    property var storage: null
    property string editionId: ""
    property var legacyCheckpoint: ({})
    property var notebook: ({revision:0,notes:[],stoppingNoteId:"",originals:{}})
    property string selectedNoteId: ""
    property var draft: ({text:"",imageId:"",annotations:[]})
    property string previewUrl: ""
    property bool dirty: false
    property string lastError: ""
    property var conflictingNotebook: null
    readonly property int revision: notebook.revision || 0
    readonly property var selectedNote: {
        var rows=notebook.notes || [];
        for(var i=0;i<rows.length;i++)if(rows[i].id===selectedNoteId)return rows[i];
        return null;
    }
    function reject(receipt) {
        lastError=receipt && receipt.error ? receipt.error : "storage_unavailable";
        conflictingNotebook=receipt && receipt.current ? receipt.current : null;
        return false;
    }
    function call(method, args) {
        if (!storage || typeof storage[method] !== "function") return {ok:false,error:"storage_unavailable"};
        try { var result=storage[method].apply(storage,args);return result && typeof result === "object" ? result : {ok:false,error:"storage_unavailable"}; }
        catch (error) { return {ok:false,error:"storage_unavailable"}; }
    }
    function available() { var c=call("capabilities",[]);return c && c.ok === true; }
    function open(id, legacy) {
        if(!available())return reject(null);
        var receipt=call("openEdition",[id,legacy || {}]);
        if(!receipt.ok)return reject(receipt);
        editionId=id;legacyCheckpoint=receipt.legacyCheckpoint || {};
        notebook=receipt.notebook;lastError="";conflictingNotebook=null;
        if(notebook.stoppingNoteId)select(notebook.stoppingNoteId);else beginNew();
        return true;
    }
    function select(id) {
        var rows=notebook.notes || [];
        for(var i=0;i<rows.length;i++)if(rows[i].id===id) {
            selectedNoteId=id;
            draft={text:rows[i].text,imageId:rows[i].imageId,annotations:JSON.parse(JSON.stringify(rows[i].annotations))};
            previewUrl=rows[i].imageUrl;dirty=false;lastError="";conflictingNotebook=null;return true;
        }
        return reject({error:"note_not_found"});
    }
    function beginNew() { selectedNoteId="";draft={text:"",imageId:"",annotations:[]};previewUrl="";dirty=false;lastError="";conflictingNotebook=null; }
    function setText(value) { draft={text:value,imageId:draft.imageId,annotations:draft.annotations};dirty=true; }
    function setAnnotations(marks) { draft={text:draft.text,imageId:draft.imageId,annotations:JSON.parse(JSON.stringify(marks))};dirty=true; }
    function addAnnotation(mark) { var marks=draft.annotations.slice();marks.push(mark);setAnnotations(marks); }
    function detachImage() { draft={text:draft.text,imageId:"",annotations:[]};previewUrl="";dirty=true; }
    function receipt(result, selectId) {
        if(!result || !result.ok)return reject(result);
        notebook=result.notebook;lastError="";conflictingNotebook=null;
        if(selectId || result.noteId)select(selectId || result.noteId);
        return true;
    }
    function save() {
        if(!available())return reject(null);
        return receipt(selectedNoteId ? call("editNote",[editionId,selectedNoteId,draft,revision]) : call("createNote",[editionId,draft,revision]));
    }
    function importOriginal(localUrl) {
        if(!available())return reject(null);
        var result=call("importOriginal",[editionId,localUrl,revision]);
        if(!result.ok)return reject(result);
        notebook=result.notebook;
        draft={text:draft.text,imageId:result.imageId,annotations:[]};previewUrl=result.imageUrl;
        dirty=true;lastError="";conflictingNotebook=null;return true;
    }
    function clear() {
        if(!available() || !selectedNoteId)return reject({error:"note_not_found"});
        var result=call("clearNote",[editionId,selectedNoteId,revision]);
        if(!receipt(result))return false;
        beginNew();return true;
    }
    function restore(id) { return available() ? receipt(call("restoreNote",[editionId,id,revision]),id) : reject(null); }
    function makeStopping(id) { return available() ? receipt(call("setStoppingNote",[editionId,id,revision]),id) : reject(null); }
    function adoptLegacy() { return available() ? receipt(call("adoptLegacy",[editionId,legacyCheckpoint,revision])) : reject(null); }
    function search(query, includeCleared) {
        if(!available())return {ok:false,error:"storage_unavailable"};
        return call("search",[editionId,query,!!includeCleared]);
    }
    function exportTo(newLocalDirectory) {
        if(!available())return {ok:false,error:"storage_unavailable"};
        var result=call("exportEdition",[editionId,newLocalDirectory]);
        if(!result.ok)reject(result);else lastError="";return result;
    }
    // Explicit conflict choice retains the stored note and saves this draft as a new branch.
    function keepDraftAsNew() {
        if(!available() || !conflictingNotebook)return reject({error:"no_revision_conflict"});
        return receipt(call("createNote",[editionId,draft,conflictingNotebook.revision]));
    }
}
