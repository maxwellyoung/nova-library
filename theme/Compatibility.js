.pragma library

// Informational records only. Never authorise a launch, setting change or save operation.
var STAGES = ["boot", "menus", "gameplay", "physical-controls", "audio", "save-restore", "exit-return", "sustained", "native-4-3", "stretch-only", "offline-launch"];
var LABELS = {boot:"Boot", menus:"Menus", gameplay:"Gameplay", "physical-controls":"Physical controls", audio:"Sound", "save-restore":"Save and restore", "exit-return":"Exit and return", sustained:"Sustained play", "native-4-3":"Native 4:3 render", "stretch-only":"Stretch-only setup", "offline-launch":"Offline launch"};
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

function performance(raw, stage) {
    if(!raw || typeof raw!=="object" || Array.isArray(raw) || Object.keys(raw).sort().join(",")!=="context,measurement,metrics,scene")return null;
    var contexts={menus:["menus"],gameplay:["gameplay","cutscene","mixed"],sustained:["gameplay","mixed"]};
    if(!contexts[stage] || contexts[stage].indexOf(raw.context)<0)return null;
    var scene=text(raw.scene,160), measurement=text(raw.measurement,200), m=raw.metrics;
    if(!scene || !measurement || !m || typeof m!=="object" || Array.isArray(m))return null;
    var keys=Object.keys(m), supported=["averageFps","p95FrameMs","p99FrameMs"];
    if(!keys.length || keys.some(function(k){return supported.indexOf(k)<0 || typeof m[k]!=="number" || !isFinite(m[k])
            || (k==="averageFps" ? m[k]<0 || m[k]>1000 : m[k]<=0 || m[k]>60000);}))return null;
    if(m.p95FrameMs!==undefined && m.p99FrameMs!==undefined && m.p99FrameMs<m.p95FrameMs)return null;
    var metrics={};supported.forEach(function(k){if(m[k]!==undefined)metrics[k]=m[k];});
    return {context:raw.context,scene:scene,measurement:measurement,metrics:metrics};
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
    if (raw.stage === "offline-launch" && (raw.network !== "disconnected" || raw.coldStart !== true
            || raw.result === "pass" && ["physical", "owner", "observed", "injected"].indexOf(raw.method) === -1)) return null;
    var duration = raw.durationSeconds;
    if (duration !== undefined && (typeof duration !== "number" || !isFinite(duration)
            || Math.floor(duration) !== duration || duration <= 0 || duration > 604800)) return null;
    if (raw.stage === "sustained" && duration === undefined) return null;
    var out = {stage:raw.stage, result:raw.result, observedAt:raw.observedAt, timestamp:observed,
               method:raw.method, source:source, note:note};
    if (duration !== undefined) out.durationSeconds=duration;
    if (raw.performance !== undefined) {
        var measured=performance(raw.performance,raw.stage);
        if(!measured || duration===undefined)return null;
        out.performance=measured;
    }
    if (raw.stage === "offline-launch") {out.network="disconnected";out.coldStart=true;}
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
        if(old && c.timestamp===old.timestamp && c.result===old.result
                && (old.performanceConflict || JSON.stringify([old.performance||null,old.performance?old.durationSeconds:null])
                    !==JSON.stringify([c.performance||null,c.performance?c.durationSeconds:null]))) {
            // Keep original portable records intact; the selected view cannot
            // arbitrarily choose one of two equal-time measurement claims.
            var conflict={};Object.keys(checks[c.stage]).forEach(function(k){conflict[k]=checks[c.stage][k];});
            delete conflict.performance;conflict.performanceConflict=true;checks[c.stage]=conflict;
        }
    });});
    return {recipe:scoped.length ? scoped[0].recipe : null,checks:checks,rejected:parsed.rejected,
            historical:matching.length-scoped.length,ambiguous:ambiguous,linked:scoped.length > 0};
}

function summary(entry, now) {
    var v=view(entry,now), failed=failureGuide(entry,now);
    if(v.ambiguous) return "Setup records conflict";
    if(failed) return LABELS[failed.stage] + " failed in a recorded check · " + failed.check.observedAt.slice(0,10);
    if(v.checks.gameplay) return "Gameplay recorded · " + v.checks.gameplay.observedAt.slice(0,10);
    if(v.linked) return "Partial checks recorded";
    if(v.historical) return "Checks belong to another setup";
    return "No compatibility checks recorded";
}

// Guidance follows a recorded stage, never an inferred crash cause or a repair command.
function failureGuide(entry, now) {
    var v=view(entry,now), latest=null, count=0;
    STAGES.forEach(function(stage){
        var c=v.checks[stage];
        if(c && c.result === "fail") {count++;if(!latest || c.timestamp>latest.timestamp)latest=c;}
    });
    if(!latest)return null;
    var next="Review this observation against the current setup before changing settings. Keep existing saves and the working configuration.";
    if(latest.stage === "boot" || latest.stage === "menus")
        next="Check the configured launch route and the runtime's own result screen. Keep saves and profiles; do not reset or reinstall to guess at a fix.";
    else if(latest.stage === "save-restore")
        next="Keep current progress and the copied save. Compare the exact edition, runtime version and save kind before attempting another load; do not overwrite either copy.";
    else if(latest.stage === "exit-return")
        next="Check whether the runtime is still running and exit normally when safe. Returning to Library does not prove it stopped; leave cleanup blocked.";
    else if(latest.stage === "physical-controls" || latest.stage === "audio")
        next="Check the runtime's input or audio settings without changing your saved profile. A real button or listening check is needed to confirm a fix.";
    else if(latest.stage === "offline-launch")
        next="Keep the local game and saves. Review the runtime's offline requirements while connected before repeating a closed-runtime offline launch test.";
    return {stage:latest.stage,check:latest,remainingFailures:count,detail:
        "Recorded observation · "+LABELS[latest.stage]+" failed. "+latest.note+"\n\n"+
        "Evidence · "+latest.observedAt.slice(0,19).replace("T"," ")+" UTC · "+latest.source+" · "+latest.method+
        ". This is an imported observation, not a live diagnosis.\n\n"+
        "Cause · Not established by these checks.\n\nNext step · "+next+
        (count>1?" "+count+" stages retain a failure; each stage's latest observation is listed below.":"")};
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

// A dated cold-launch observation, not current network telemetry or save protection.
function offlineEvidence(entry, now) {
    if(entry && entry.discMembers) {
        var member=entry.discEdition;
        var disc=member && !member.discMembers ? offlineEvidence(member,now) : {tested:false,check:null,reason:"not-checked"};
        return {tested:false,selectedDiscTested:disc.tested,check:disc.check,reason:disc.reason,discNumber:entry.discNumber};
    }
    var v=view(entry,now), c=v.checks["offline-launch"] || null;
    if(!c)return {tested:false,check:null,reason:v.ambiguous?"conflicting-setup":"not-checked"};
    if(c.result!=="pass")return {tested:false,check:c,reason:"failed"};
    if(!entry || entry.missing!==false || !entry.game || entry.game.missing!==false)
        return {tested:false,check:c,reason:"file-not-confirmed"};
    if(entry.launchable!==true)return {tested:false,check:c,reason:"no-local-route"};
    return {tested:true,check:c,reason:"tested"};
}

function offlineSummary(entry, now) {
    var v=offlineEvidence(entry,now), prefix=v.selectedDiscTested !== undefined ? (v.discNumber?"Disc "+v.discNumber:"Selected disc")+" · " : "";
    if(v.tested || v.selectedDiscTested)return prefix+"Offline launch tested · "+v.check.observedAt.slice(0,10);
    if(v.reason==="file-not-confirmed")return prefix+"Offline check retained; local file not confirmed";
    if(v.reason==="no-local-route")return prefix+"Offline check retained; no local launch route";
    if(v.reason==="failed")return prefix+"Offline launch failed in a recorded check";
    return prefix+"Offline launch not checked for this setup";
}

function performanceRow(c, setup) {
    if(!c || (!c.performance && !c.performanceConflict))return null;
    var names={menus:"Menu measurement",gameplay:"Gameplay measurement",sustained:"Sustained measurement"};
    if(c.performanceConflict)return {label:names[c.stage],value:"Conflicting samples",detail:
        "Equal-time observations disagree about measured figures or duration; figures withheld. Keep both original records and resolve the measurements before choosing one. This does not change the recorded stage result."};
    var p=c.performance,m=p.metrics,contexts={menus:"Menu sample",gameplay:"Gameplay sample",cutscene:"Cutscene sample",mixed:"Mixed-scene sample"};
    var pacing=[];if(m.p95FrameMs!==undefined)pacing.push("95th percentile "+m.p95FrameMs+" ms");if(m.p99FrameMs!==undefined)pacing.push("99th percentile "+m.p99FrameMs+" ms");
    return {label:names[c.stage],value:contexts[p.context]+" · "+c.durationSeconds+" s",detail:
        contexts[p.context]+" · "+p.scene+" · "+c.durationSeconds+" seconds. "+(c.result==="pass"?"Recorded pass":"A failed observation")+"; limited to this scene and setup.\n\n"+
        "Average FPS · "+(m.averageFps!==undefined?m.averageFps:"Not measured")+". Frame pacing · "+(pacing.length?pacing.join("; "):"Not measured")+".\n\n"+
        "Measurement · "+p.measurement+". Evidence · "+c.observedAt.slice(0,19).replace("T"," ")+" UTC · "+c.source+" · "+c.method+".\n\n"+
        "Setup · "+setup.device+" · "+setup.runtime+" "+setup.version+". Core: "+setup.core+". Driver: "+setup.driver+". Display: "+setup.display+". Input: "+setup.input+". Settings: "+setup.settings+".\n\n"+
        "Imported measurements, not a live benchmark or a score for the whole game. Menu and cutscene samples do not establish sustained gameplay. Unreported scenes and frame-time statistics remain unmeasured."};
}

function rows(entry, now) {
    var v=view(entry,now), out=[], failed=failureGuide(entry,now);
    if(failed)out.push({label:"Recorded failure",value:LABELS[failed.stage],detail:failed.detail});
    out.push({label:"Tested setup",value:v.ambiguous ? "Conflicting records" : v.recipe ? v.recipe.runtime+" "+v.recipe.version : "Not linked",
        detail:v.ambiguous ? "The same recipe ID describes different settings. Correct the records before using them as evidence."
        : v.recipe ? v.recipe.device+" · Core: "+v.recipe.core+" · Driver: "+v.recipe.driver+". Display: "+v.recipe.display+". Input: "+v.recipe.input+". Settings: "+v.recipe.settings
        : "No records match this edition and its explicitly linked setup. A configured launch route is separate from gameplay evidence."});
    STAGES.forEach(function(s){var c=v.checks[s];out.push({label:LABELS[s], value:!c ? "Not checked" : c.result === "pass" ? "Passed in check" : "Failed in check",
        detail:!c ? "No observation for this stage in the linked setup. Later stages never imply earlier checks."
        : c.observedAt.slice(0,19).replace("T"," ")+" UTC · "+c.source+" · "+c.method+". "+c.note
          +(s === "offline-launch" ? " Reported network disconnected; started from a closed runtime. This does not verify offline saves or every game mode." : "")
          +(c.durationSeconds !== undefined && !c.performanceConflict ? " Duration: "+c.durationSeconds+" seconds." : "")});
        var measured=performanceRow(c,v.recipe);if(measured)out.push(measured);
    });
    if(v.historical) out.push({label:"Other setup records",value:String(v.historical),detail:"These belong to this edition but are not used for the linked setup. Relink only after checking the actual runtime, device and settings."});
    if(v.rejected) out.push({label:"Unreadable records",value:String(v.rejected),detail:"Invalid or unsupported records were excluded. They do not establish that a game passed or failed."});
    return out;
}

function exportRecord(value) {
    var out={schemaVersion:1,editionId:value.editionId,recipe:recipe(value.recipe),checks:[]};
    value.checks.forEach(function(c){var x={stage:c.stage,result:c.result,observedAt:c.observedAt,method:c.method,source:c.source,note:c.note};if(c.durationSeconds!==undefined)x.durationSeconds=c.durationSeconds;if(c.performance)x.performance=performance(c.performance,c.stage);if(c.stage==="offline-launch"){x.network=c.network;x.coldStart=c.coldStart;}out.checks.push(x);});
    return out;
}
