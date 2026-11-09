.pragma library

var BACKENDS = [{id:"droiddeck",name:"DroidDeck"},{id:"gamenative",name:"GameNative"}];
function steamId(entry) {
    if(!entry || entry.systemId!=="pc" || entry.discMembers || typeof entry.id!=="string")return "";
    var match=/^steam:([1-9][0-9]{0,9})$/.exec(entry.id);
    return match && Number(match[1])<=2147483647?match[1]:"";
}
function runtimeId(id){return id==="droiddeck" || id==="gamenative";}
function freshChoices(){return {readable:true,value:{version:1,choices:{}}};}
function readChoices(raw) {
    if(raw===undefined)return freshChoices();
    var empty=freshChoices();empty.readable=false;
    if(!raw || Array.isArray(raw) || raw.version!==1 || !raw.choices || Array.isArray(raw.choices) || typeof raw.choices!=="object" || Object.keys(raw).length!==2)return empty;
    var ids=Object.keys(raw.choices);if(ids.length>2000)return empty;var out=freshChoices();
    for(var i=0;i<ids.length;i++){
        var id=ids[i],choice=raw.choices[id];
        if(!steamId({systemId:"pc",id:id}) || !choice || Array.isArray(choice) || Object.keys(choice).length!==2 || !runtimeId(choice.runtime)
            || typeof choice.version!=="string" || !/^[A-Za-z0-9.+_-]{1,80}$/.test(choice.version))return empty;
        out.value.choices[id]={runtime:choice.runtime,version:choice.version};
    }
    return out;
}
function choice(entry,stored){return steamId(entry) && stored && stored.readable ? stored.value.choices[entry.id] || null : null;}
function editChoice(stored,editionId,value) {
    if(!stored || !stored.readable || !steamId({systemId:"pc",id:editionId}))return null;
    var out=readChoices(stored.value);if(!out.readable)return null;
    if(value===null)delete out.value.choices[editionId];
    else {
        if(!runtimeId(value.runtime) || typeof value.version!=="string" || !/^[A-Za-z0-9.+_-]{1,80}$/.test(value.version))return null;
        if(!out.value.choices[editionId] && Object.keys(out.value.choices).length>=2000)return null;
        out.value.choices[editionId]={runtime:value.runtime,version:value.version};
    }
    return out;
}
function rows(observed,entry,stored) {
    var list=observed && typeof observed.length==="number" && observed.length<=8 ? Array.prototype.slice.call(observed) : [],saved=choice(entry,stored);
    var result=BACKENDS.map(function(backend){
        var matches=list.filter(function(s){return s && s.id===backend.id;}),s=matches.length===1?matches[0]:{};
        var available=s.available===true,supported=available && s.supported===true;
        var version=typeof s.version==="string" && /^[A-Za-z0-9.+_-]{1,80}$/.test(s.version)?s.version:"";
        return {label:backend.name,value:!available?"App unavailable":(version || "Version unknown")+(supported?" · Installed":" · Needs adapter check")+(saved && saved.runtime===backend.id?" · Chosen":""),
            runtime:backend.id,version:version,available:supported,dim:!supported,
            reason:!available?"The app is missing, disabled or could not be checked.":!supported?"This app version has no checked launch adapter. Your existing shortcut is unchanged.":saved && saved.runtime===backend.id && saved.version!==version?"The app version changed. Opening here explicitly reviews and remembers the new version.":"Open this game in "+backend.name+". It may ask you to install or configure the game."};
    });
    if(entry && entry.launchable && entry.game && !entry.game.missing)result.push({label:"Existing shortcut",value:entry.route || "Catalogue route",legacy:true,available:true,reason:"Use the existing catalogue shortcut and forget the separate runtime choice."});
    if(saved)result.push({label:"Forget runtime choice",value:"Keep games and saves",forget:true,available:true,reason:"Only removes this game's remembered runtime. No game, runtime or save files are changed."});
    return result;
}
function chosenName(entry,stored) {var saved=choice(entry,stored);return saved ? saved.runtime==="droiddeck"?"DroidDeck":"GameNative" : "";}
function actionLabel(entry,stored) {
    var saved=choice(entry,stored);if(!saved)return "PC options";
    return saved.runtime==="droiddeck"?"Open in DroidDeck":"Open in GameNative";
}
