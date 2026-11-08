.pragma library

// Informational records only. Never authorise a launch, setting change or save operation.
var STAGES = ["boot", "menus", "gameplay", "physical-controls", "audio", "save-restore", "exit-return", "sustained", "native-4-3", "stretch-only"];
var LABELS = {boot:"Boot", menus:"Menus", gameplay:"Gameplay", "physical-controls":"Physical controls", audio:"Sound", "save-restore":"Save and restore", "exit-return":"Exit and return", sustained:"Sustained play", "native-4-3":"Native 4:3 render", "stretch-only":"Stretch-only setup"};
var METHODS = ["physical", "owner", "observed", "injected", "log", "test"];

function text(value, limit) {
    return typeof value === "string" && value.trim().length > 0 && value.length <= limit
        && !/[<>\x00-\x1f\x7f]/.test(value) ? value.trim() : null;
}

function stamp(value, now) {
    if (typeof value !== "string" || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/.test(value)) return null;
    var n = Date.parse(value);
    if (!isFinite(n) || new Date(n).toISOString().slice(0,19) !== value.slice(0,19) || n > now) return null;
    return n;
}

function recipe(raw) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
    if (typeof raw.id !== "string" || !/^[a-zA-Z0-9][a-zA-Z0-9._:-]{0,127}$/.test(raw.id)) return null;
    var out = {id:raw.id};
    var required = ["device", "runtime", "version", "core", "driver", "display", "input", "settings"];
    for (var i = 0; i < required.length; i++) {
        var key = required[i], value = text(raw[key], key === "settings" ? 500 : 160);
        if (value === null) return null;
        out[key] = value;
    }
    return out;
}

function check(raw, now) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw) || STAGES.indexOf(raw.stage) === -1
            || ["pass", "fail"].indexOf(raw.result) === -1 || METHODS.indexOf(raw.method) === -1) return null;
    var observed = stamp(raw.observedAt, now), source = text(raw.source, 160), note = text(raw.note, 500);
    if (observed === null || source === null || note === null) return null;
    if (raw.result === "pass" && ["physical-controls", "audio"].indexOf(raw.stage) !== -1
            && ["physical", "owner"].indexOf(raw.method) === -1) return null;
    if (raw.result === "pass" && ["native-4-3", "stretch-only"].indexOf(raw.stage) !== -1
            && ["physical", "owner", "observed", "injected"].indexOf(raw.method) === -1) return null;
    var duration = raw.durationSeconds;
    if (duration !== undefined && (typeof duration !== "number" || !isFinite(duration)
            || Math.floor(duration) !== duration || duration <= 0 || duration > 604800)) return null;
    if (raw.stage === "sustained" && duration === undefined) return null;
    var out = {stage:raw.stage, result:raw.result, observedAt:raw.observedAt, timestamp:observed,
               method:raw.method, source:source, note:note};
    if (duration !== undefined) out.durationSeconds=duration;
    return out;
}

function record(raw, now) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw) || raw.schemaVersion !== 1) return null;
    var editionId=text(raw.editionId, 200), setup=recipe(raw.recipe);
    if (!editionId || !setup || !Array.isArray(raw.checks) || !raw.checks.length || raw.checks.length > 64) return null;
    var checks=[];
    for (var i=0; i<raw.checks.length; i++) {
        var value=check(raw.checks[i],now);
        if (!value) return null;
        checks.push(value);
    }
    return {schemaVersion:1, editionId:editionId, recipe:setup, checks:checks};
}

function parse(raw, now) {
    var out={records:[],rejected:0};
    if (raw === undefined || raw === null || raw === "") return out;
    if (typeof raw === "string") {
        if (raw.length > 262144) { out.rejected=1;return out; }
        try { raw=JSON.parse(raw); } catch (error) { out.rejected=1;return out; }
    }
    if (!Array.isArray(raw) || raw.length > 32) {out.rejected=1;return out;}
    now = typeof now === "number" && isFinite(now) ? now : Date.now();
    raw.forEach(function(r) {var value=record(r,now);if(value) out.records.push(value);else out.rejected++;});
    return out;
}

function fingerprint(r) {
    return JSON.stringify([r.device,r.runtime,r.version,r.core,r.driver,r.display,r.input,r.settings]);
}

function view(entry, now) {
    var parsed=parse(entry ? entry.compatibilityReceipts : "",now);
    var matching=parsed.records.filter(function(r){return entry && r.editionId === entry.id;});
    var active=entry && entry.compatibilityRecipeId || "";
    var scoped=active ? matching.filter(function(r){return r.recipe.id === active;}) : [];
    var setups={};
    scoped.forEach(function(r){setups[fingerprint(r.recipe)]=true;});
    var ambiguous=Object.keys(setups).length > 1;
    if(ambiguous) scoped=[];
    var checks={};
    scoped.forEach(function(r){r.checks.forEach(function(c){
        var old=checks[c.stage];
        if(!old || c.timestamp > old.timestamp || (c.timestamp === old.timestamp && c.result === "fail")) checks[c.stage]=c;
    });});
    return {recipe:scoped.length ? scoped[0].recipe : null,checks:checks,rejected:parsed.rejected,
            historical:matching.length-scoped.length,ambiguous:ambiguous,linked:scoped.length > 0};
}

function summary(entry, now) {
    var v=view(entry,now), failed=STAGES.filter(function(s){return v.checks[s] && v.checks[s].result === "fail";});
    if(v.ambiguous) return "Setup records conflict";
    if(failed.length) return LABELS[failed[0]] + " failed in a recorded check";
    if(v.checks.gameplay) return "Gameplay recorded · " + v.checks.gameplay.observedAt.slice(0,10);
    if(v.linked) return "Partial checks recorded";
    if(v.historical) return "Checks belong to another setup";
    return "No compatibility checks recorded";
}

// These describe the linked setup, never every possible configuration of a game.
function displayEvidence(entry, now) {
    var v=view(entry,now), native=v.checks["native-4-3"], stretch=v.checks["stretch-only"];
    var conflict=!!(native && stretch && native.result === "pass" && stretch.result === "pass");
    return {native43:!conflict && !!native && native.result === "pass",
        stretchOnly:!conflict && !!stretch && stretch.result === "pass",
        unknown:conflict || !((native && native.result === "pass") || (stretch && stretch.result === "pass")), conflict:conflict,
        nativeCheck:native || null, stretchCheck:stretch || null};
}

function displaySummary(entry, now) {
    var d=displayEvidence(entry,now);
    if(d.conflict) return "Display checks conflict";
    if(d.native43) return "Native 4:3 tested · "+d.nativeCheck.observedAt.slice(0,10);
    if(d.stretchOnly) return "Stretch-only setup · "+d.stretchCheck.observedAt.slice(0,10);
    return "4:3 render not confirmed for this setup";
}

function rows(entry, now) {
    var v=view(entry,now), out=[];
    out.push({label:"Tested setup",value:v.ambiguous ? "Conflicting records" : v.recipe ? v.recipe.runtime+" "+v.recipe.version : "Not linked",
        detail:v.ambiguous ? "The same recipe ID describes different settings. Correct the records before using them as evidence."
        : v.recipe ? v.recipe.device+" · Core: "+v.recipe.core+" · Driver: "+v.recipe.driver+". Display: "+v.recipe.display+". Input: "+v.recipe.input+". Settings: "+v.recipe.settings
        : "No records match this edition and its explicitly linked setup. A configured launch route is separate from gameplay evidence."});
    STAGES.forEach(function(s){var c=v.checks[s];out.push({label:LABELS[s], value:!c ? "Not checked" : c.result === "pass" ? "Passed in check" : "Failed in check",
        detail:!c ? "No observation for this stage in the linked setup. Later stages never imply earlier checks."
        : c.observedAt.slice(0,19).replace("T"," ")+" UTC · "+c.source+" · "+c.method+". "+c.note
          +(c.durationSeconds !== undefined ? " Duration: "+c.durationSeconds+" seconds." : "")});});
    if(v.historical) out.push({label:"Other setup records",value:String(v.historical),detail:"These belong to this edition but are not used for the linked setup. Relink only after checking the actual runtime, device and settings."});
    if(v.rejected) out.push({label:"Unreadable records",value:String(v.rejected),detail:"Invalid or unsupported records were excluded. They do not establish that a game passed or failed."});
    return out;
}

function exportRecord(value) {
    var out={schemaVersion:1,editionId:value.editionId,recipe:recipe(value.recipe),checks:[]};
    value.checks.forEach(function(c){var x={stage:c.stage,result:c.result,observedAt:c.observedAt,method:c.method,source:c.source,note:c.note};if(c.durationSeconds!==undefined)x.durationSeconds=c.durationSeconds;out.checks.push(x);});
    return out;
}
