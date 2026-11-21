.pragma library

// An authored local order, independent of favourites, history and synced collections.
var ID = "local:rotation-v1";
var LIMIT = 12;
function identity(id) {
    return typeof id === "string" && id.length>0 && id.length<=512 && id.indexOf("untagged:")!==0
        && ["__proto__","constructor","prototype"].indexOf(id)<0 && !/[<>\x00-\x1f\x7f]/.test(id);
}
function title(value) {
    return typeof value === "string" && value.length>0 && value.length<=240
        && value===value.trim() && !/[<>\x00-\x1f\x7f]/.test(value);
}
function store(raw) {
    if(raw===undefined)return {version:1,editions:[]};
    if(!raw || Array.isArray(raw) || raw.version!==1 || Object.keys(raw).length!==2
            || !Array.isArray(raw.editions) || raw.editions.length>LIMIT)return null;
    var seen=[],editions=[];
    for(var i=0;i<raw.editions.length;i++) {
        var e=raw.editions[i];
        if(!e || Array.isArray(e) || Object.keys(e).length!==2 || !identity(e.id)
                || !title(e.title) || seen.indexOf(e.id)>=0)return null;
        seen.push(e.id);editions.push({id:e.id,title:e.title});
    }
    return {version:1,editions:editions};
}
function contains(state,id){return !!state && state.editions.some(function(e){return e.id===id;});}
function eligible(e){return !!e && !e.discMembers && e.systemId!=="androidapps" && e.systemId!=="emulators" && identity(e.id) && title(e.title);}
function add(state,entry) {
    var next=store(state);
    if(!next || !eligible(entry) || contains(next,entry.id) || next.editions.length>=LIMIT)return null;
    next.editions.push({id:entry.id,title:entry.title});return next;
}
function remove(state,id) {
    var next=store(state);if(!next || !contains(next,id))return null;
    next.editions=next.editions.filter(function(e){return e.id!==id;});return next;
}
function move(state,id,direction) {
    var next=store(state);if(!next || [1,-1].indexOf(direction)<0)return null;
    var i=next.editions.map(function(e){return e.id;}).indexOf(id),j=i+direction;
    if(i<0 || j<0 || j>=next.editions.length)return null;
    var e=next.editions[i];next.editions[i]=next.editions[j];next.editions[j]=e;return next;
}
function rows(state,entries) {
    if(!state)return [{label:"Saved rotation unavailable",value:"Kept unchanged",dim:true}];
    if(!state.editions.length)return [{label:"No games in your rotation",value:"Add from Details → Collections",dim:true}];
    return state.editions.map(function(saved,i){
        var matches=entries.filter(function(e){return e.id===saved.id;});
        var entry=matches.length===1?matches[0]:null;
        return {id:saved.id,label:entry?entry.title:saved.title,entry:entry,
            value:String(i+1)+" / "+state.editions.length+(entry?"":" · Not in catalogue")};
    });
}
function collection(state,entries) {
    var resolved=rows(state,entries),members=resolved.filter(function(r){return !!r.entry;}).map(function(r){return r.entry;});
    return {id:ID,name:"Your rotation",origin:"rotation",suggestedId:"",source:"",members:[],entries:members,
        absent:state?state.editions.length-members.length:0,
        reason:!state?"Saved rotation could not be read. It has been kept unchanged.":state.editions.length?
            "Chosen by you, in your order. Saved only on this device.":"Add games from Details → Collections. Your wider library stays available."};
}
