.pragma library

// Offline preferences only. No adapter or runtime application is implied.
var LIMIT = 256;
var IMPORT_LIMIT = 16384;
function object(value, keys) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    var actual = Object.keys(value);
    return actual.length === keys.length && keys.every(function(k) {
        return Object.prototype.hasOwnProperty.call(value, k);
    });
}
function editionId(value) {
    return typeof value === "string" && value.length > 0 && value.length <= 512
        && value === value.trim() && value.indexOf("untagged:") !== 0
        && ["__proto__", "constructor", "prototype"].indexOf(value) < 0
        && !/[<>\x00-\x1f\x7f]/.test(value);
}
function token(value) {
    return typeof value === "string" && value === value.trim() && /^[A-Za-z0-9][A-Za-z0-9.+_-]{0,79}$/.test(value)
        && ["unknown", "unverified", "unspecified", "pending", "none", "null", "latest", "current"].indexOf(value.toLowerCase()) < 0;
}
function runtimeId(value) {
    // Compatibility recipes retain a literal runtime name, including spaces.
    // Keep that exact identity; slugging names could merge different setups.
    return typeof value === "string" && value === value.trim() && /^[A-Za-z0-9][A-Za-z0-9 .+_-]{0,159}$/.test(value)
        && ["unknown", "unverified", "unspecified", "pending", "none", "null", "latest", "current"].indexOf(value.toLowerCase()) < 0;
}
function binding(value) {
    return object(value, ["editionId", "runtimeId", "runtimeVersion"])
        && editionId(value.editionId) && runtimeId(value.runtimeId) && token(value.runtimeVersion);
}
function same(a, b) {
    return a.editionId === b.editionId && a.runtimeId === b.runtimeId && a.runtimeVersion === b.runtimeVersion;
}
function number(value, min, max) {
    return typeof value === "number" && isFinite(value) && value >= min && value <= max;
}
function pair(value, keys, check) {
    return object(value, keys) && keys.every(function(k) { return check(value[k]); });
}
function preferences(value) {
    return object(value, ["sensitivity", "deadzone", "inversion", "triggers", "holdToggle"])
        && pair(value.sensitivity, ["x", "y"], function(v) { return number(v, 0.1, 10); })
        && pair(value.deadzone, ["left", "right"], function(v) { return number(v, 0, 0.95); })
        && pair(value.inversion, ["x", "y"], function(v) { return typeof v === "boolean"; })
        && pair(value.triggers, ["left", "right"], function(v) { return number(v, 0, 1); })
        && pair(value.holdToggle, ["aim", "sprint", "crouch"], function(v) { return v === "hold" || v === "toggle"; });
}
function copy(value) { return JSON.parse(JSON.stringify(value)); }
function record(value) {
    return object(value, ["binding", "preferences"]) && binding(value.binding) && preferences(value.preferences);
}
function store(raw) {
    if (raw === undefined) return {version: 1, profiles: []};
    if (!object(raw, ["version", "profiles"]) || raw.version !== 1
            || !Array.isArray(raw.profiles) || raw.profiles.length > LIMIT) return null;
    var profiles = [];
    for (var i = 0; i < raw.profiles.length; i++) {
        var p = raw.profiles[i];
        if (!record(p) || profiles.some(function(old) { return same(old.binding, p.binding); })) return null;
        profiles.push(copy(p));
    }
    return {version: 1, profiles: profiles};
}
function index(state, key) {
    for (var i = 0; i < state.profiles.length; i++) if (same(state.profiles[i].binding, key)) return i;
    return -1;
}
function profile(state, key) {
    var valid = store(state);
    if (!valid || !binding(key)) return null;
    var i = index(valid, key);
    return i < 0 ? null : valid.profiles[i];
}
function edit(state, key, value) {
    // Do not normalize broken/future storage into a writable empty preference set.
    if (state === undefined) return null;
    var next = store(state);
    if (!next || !binding(key) || !preferences(value)) return null;
    var i = index(next, key), p = {binding: copy(key), preferences: copy(value)};
    if (i >= 0) next.profiles[i] = p;
    else {
        if (next.profiles.length >= LIMIT) return null;
        next.profiles.push(p);
    }
    return next;
}
function clear(state, key) {
    if (state === undefined) return null;
    var next = store(state);
    if (!next || !binding(key)) return null;
    var i = index(next, key);
    if (i < 0) return null;
    next.profiles.splice(i, 1);
    return next;
}
function exportProfile(state, key) {
    var p = profile(state, key);
    return p ? JSON.stringify({version: 1, profile: p}, null, 2) : null;
}
function parseImport(text) {
    if (typeof text !== "string" || text.length > IMPORT_LIMIT) return null;
    try {
        var parsed = JSON.parse(text);
        // JSON.parse accepts duplicate keys. Scan the already-valid JSON grammar
        // so ambiguous imports cannot silently discard an earlier preference.
        var tokens = text.match(/"(?:[^"\\]|\\.)*"|[{}\[\],:]|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null/g), at = 0;
        function walk() {
            var t = tokens[at++];
            if (t === "{") {
                var seen = [];
                if (tokens[at] === "}") { at++; return; }
                while (true) {
                    var key = JSON.parse(tokens[at++]);
                    if (seen.indexOf(key) >= 0) throw new Error("duplicate key");
                    seen.push(key); at++; walk();
                    if (tokens[at++] === "}") break;
                }
            } else if (t === "[") {
                if (tokens[at] === "]") { at++; return; }
                while (true) { walk(); if (tokens[at++] === "]") break; }
            }
        }
        walk();
        return parsed;
    } catch (e) { return null; }
}
function importProfile(state, key, text) {
    var envelope = parseImport(text);
    if (!object(envelope, ["version", "profile"]) || envelope.version !== 1
            || !record(envelope.profile) || !binding(key) || !same(key, envelope.profile.binding)) return null;
    return edit(state, key, envelope.profile.preferences);
}
function status(state, key) {
    var valid = state === undefined ? null : store(state);
    return {storage: valid ? "readable" : "unavailable", saved: valid ? !!profile(valid, key) : false,
        support: "unknown", application: "not-applied",
        message: "Offline preferences only. Runtime support is unknown; these values have not been applied."};
}

// Editor starting preferences, not detected values or runtime defaults.
var KEY = "inputProfilesV1";
var FIELDS = [
    {group:"sensitivity",key:"x",label:"Horizontal sensitivity",min:0.1,max:10,step:0.1},
    {group:"sensitivity",key:"y",label:"Vertical sensitivity",min:0.1,max:10,step:0.1},
    {group:"deadzone",key:"left",label:"Left-stick deadzone",min:0,max:0.95,step:0.05},
    {group:"deadzone",key:"right",label:"Right-stick deadzone",min:0,max:0.95,step:0.05},
    {group:"inversion",key:"x",label:"Invert horizontal"},
    {group:"inversion",key:"y",label:"Invert vertical"},
    {group:"triggers",key:"left",label:"Left-trigger threshold",min:0,max:1,step:0.05},
    {group:"triggers",key:"right",label:"Right-trigger threshold",min:0,max:1,step:0.05},
    {group:"holdToggle",key:"aim",label:"Aim"},
    {group:"holdToggle",key:"sprint",label:"Sprint"},
    {group:"holdToggle",key:"crouch",label:"Crouch"}
];
function defaults() {
    return {sensitivity:{x:1,y:1},deadzone:{left:0,right:0},inversion:{x:false,y:false},
        triggers:{left:0.5,right:0.5},holdToggle:{aim:"hold",sprint:"hold",crouch:"hold"}};
}
function adjust(value, field, direction) {
    if (!preferences(value) || Math.floor(field)!==field || field<0 || field>=FIELDS.length || [1,-1].indexOf(direction)<0) return null;
    var out=copy(value),f=FIELDS[field],v=out[f.group][f.key];
    if (f.group==="inversion") v=!v;
    else if(f.group==="holdToggle") v=v==="hold"?"toggle":"hold";
    else v=Math.max(f.min,Math.min(f.max,Math.round((v+f.step*direction)*1000)/1000));
    out[f.group][f.key]=v;return out;
}
function display(value,field) {
    var f=FIELDS[field],v=value[f.group][f.key];
    return f.group==="sensitivity"?v.toFixed(1)+"×":f.group==="inversion"?(v?"Yes":"No")
        :f.group==="holdToggle"?(v==="hold"?"Hold":"Toggle"):Math.round(v*100)+"%";
}
function setup(entry,pcChoice,recipe) {
    if(!entry || entry.discMembers || entry.systemId==="emulators" || entry.systemId==="androidapps")return null;
    var key={editionId:entry.id,runtimeId:pcChoice?pcChoice.runtime:recipe?recipe.runtime:"",runtimeVersion:pcChoice?pcChoice.version:recipe?recipe.version:""};
    return binding(key)?key:null;
}
// QVariantMap orders object keys differently from JavaScript. Compare validated
// fields, while preserving the order and exact bindings of the profile list.
function equalState(a,b) {
    a=store(a);b=store(b);
    if(!a || !b || a.profiles.length!==b.profiles.length)return false;
    for(var i=0;i<a.profiles.length;i++) {
        if(!same(a.profiles[i].binding,b.profiles[i].binding))return false;
        for(var j=0;j<FIELDS.length;j++){
            var f=FIELDS[j];
            if(a.profiles[i].preferences[f.group][f.key]!==b.profiles[i].preferences[f.group][f.key])return false;
        }
    }return true;
}
