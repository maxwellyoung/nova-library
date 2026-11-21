.pragma library
.import "Rotation.js" as Rotation

// Owner-named discovery shelves ("dreamlike", "ten-minute adrenaline"), saved in theme memory
// on this device. A shelf is only ever made, named, filled and ordered by the owner. Nothing here
// infers taste, ranks games or reads play history, so a shelf can never be mistaken for a
// suggestion. Membership is per exact edition, like the rotation; same-title editions stay apart.
var KEY = "shelvesV1";
var SHELF_LIMIT = 8;
var EDITION_LIMIT = 24;
var NAME_MAX = 40;
var KINDS = ["feeling", "purpose"];
var KIND_LABELS = {feeling: "Feeling", purpose: "Purpose"};
var SERIAL_MAX = 999999;

function plainObject(v) { return !!v && typeof v === "object" && !Array.isArray(v); }
function keysAre(v, keys) {
    var own = Object.keys(v);
    return own.length === keys.length && keys.every(function(k) { return own.indexOf(k) >= 0; });
}
function fold(name) { return name.toLowerCase(); }

// Collapses inner whitespace so "  ten   minute " and "ten minute" are one label.
function cleanName(value) {
    if (typeof value !== "string") return "";
    var v = value.replace(/\s+/g, " ").trim();
    return v.length > 0 && v.length <= NAME_MAX && !/[<>\x00-\x1f\x7f]/.test(v) ? v : "";
}
function validId(id, serial) {
    var m = typeof id === "string" ? /^shelf:([1-9][0-9]{0,5})$/.exec(id) : null;
    return !!m && Number(m[1]) <= serial;
}

function empty() { return {version: 1, serial: 0, shelves: []}; }

// Returns a fresh validated copy, or null when the saved value is unreadable. Null is never
// replaced by an empty store: the theme refuses to write instead of discarding shelves.
function store(raw) {
    if (raw === undefined) return empty();
    if (!plainObject(raw) || !keysAre(raw, ["version", "serial", "shelves"]) || raw.version !== 1
            || typeof raw.serial !== "number" || raw.serial % 1 !== 0 || raw.serial < 0 || raw.serial > SERIAL_MAX
            || !Array.isArray(raw.shelves) || raw.shelves.length > SHELF_LIMIT) return null;
    var ids = [], names = [], shelves = [];
    for (var i = 0; i < raw.shelves.length; i++) {
        var s = raw.shelves[i];
        if (!plainObject(s) || !keysAre(s, ["id", "name", "kind", "editions"]) || !validId(s.id, raw.serial)
                || ids.indexOf(s.id) >= 0 || !cleanName(s.name) || cleanName(s.name) !== s.name || names.indexOf(fold(s.name)) >= 0
                || KINDS.indexOf(s.kind) < 0 || !Array.isArray(s.editions) || s.editions.length > EDITION_LIMIT) return null;
        var seen = [], editions = [];
        for (var j = 0; j < s.editions.length; j++) {
            var e = s.editions[j];
            if (!plainObject(e) || !keysAre(e, ["id", "title"]) || !Rotation.identity(e.id)
                    || !Rotation.title(e.title) || seen.indexOf(e.id) >= 0) return null;
            seen.push(e.id); editions.push({id: e.id, title: e.title});
        }
        ids.push(s.id); names.push(fold(s.name));
        shelves.push({id: s.id, name: s.name, kind: s.kind, editions: editions});
    }
    return {version: 1, serial: raw.serial, shelves: shelves};
}

function same(a, b) { return JSON.stringify(a === undefined ? null : a) === JSON.stringify(b === undefined ? null : b); }
function find(state, id) {
    if (!state) return null;
    for (var i = 0; i < state.shelves.length; i++) if (state.shelves[i].id === id) return state.shelves[i];
    return null;
}
function indexOf(state, id) { return state ? state.shelves.map(function(s) { return s.id; }).indexOf(id) : -1; }
function contains(state, shelfId, editionId) {
    var s = find(state, shelfId);
    return !!s && s.editions.some(function(e) { return e.id === editionId; });
}
function eligible(entry) { return Rotation.eligible(entry); }

// The owner-facing reason a name can't be used, or "" when it can.
function nameProblem(state, value, exceptId) {
    if (!state) return "Saved shelves could not be read, so nothing was changed.";
    var name = cleanName(value);
    if (!name) {
        if (typeof value === "string" && value.replace(/\s+/g, " ").trim().length > NAME_MAX)
            return "Shelf names are up to " + NAME_MAX + " characters.";
        return "Name the shelf with a few plain words.";
    }
    for (var i = 0; i < state.shelves.length; i++)
        if (state.shelves[i].id !== exceptId && fold(state.shelves[i].name) === fold(name))
            return "You already have a shelf called “" + state.shelves[i].name + "”.";
    return "";
}

function create(state, value, kind) {
    var next = store(state);
    if (!next || nameProblem(next, value, "") || next.shelves.length >= SHELF_LIMIT || next.serial >= SERIAL_MAX) return null;
    next.serial++;
    var id = "shelf:" + next.serial;
    next.shelves.push({id: id, name: cleanName(value), kind: KINDS.indexOf(kind) >= 0 ? kind : "feeling", editions: []});
    return {state: next, id: id};
}

function rename(state, id, value) {
    var next = store(state), s = find(next, id);
    if (!s || nameProblem(next, value, id) || cleanName(value) === s.name) return null;
    s.name = cleanName(value);
    return next;
}

function cycleKind(state, id, step) {
    var next = store(state), s = find(next, id);
    if (!s) return null;
    s.kind = KINDS[(KINDS.indexOf(s.kind) + (step < 0 ? KINDS.length - 1 : 1)) % KINDS.length];
    return next;
}

function moveShelf(state, id, direction) {
    var next = store(state), i = indexOf(next, id), j = i + direction;
    if (!next || [1, -1].indexOf(direction) < 0 || i < 0 || j < 0 || j >= next.shelves.length) return null;
    var s = next.shelves[i]; next.shelves[i] = next.shelves[j]; next.shelves[j] = s;
    return next;
}

// Deleting is limited to an empty shelf, so a shelf's membership is never discarded by one press.
function removeShelf(state, id) {
    var next = store(state), s = find(next, id);
    if (!s || s.editions.length) return null;
    next.shelves = next.shelves.filter(function(x) { return x.id !== id; });
    return next;
}

function add(state, shelfId, entry) {
    var next = store(state), s = find(next, shelfId);
    if (!s || !eligible(entry) || contains(next, shelfId, entry.id) || s.editions.length >= EDITION_LIMIT) return null;
    s.editions.push({id: entry.id, title: entry.title});
    return next;
}

function remove(state, shelfId, editionId) {
    var next = store(state), s = find(next, shelfId);
    if (!s || !contains(next, shelfId, editionId)) return null;
    s.editions = s.editions.filter(function(e) { return e.id !== editionId; });
    return next;
}

function moveEdition(state, shelfId, editionId, direction) {
    var next = store(state), s = find(next, shelfId);
    if (!s || [1, -1].indexOf(direction) < 0) return null;
    var i = s.editions.map(function(e) { return e.id; }).indexOf(editionId), j = i + direction;
    if (i < 0 || j < 0 || j >= s.editions.length) return null;
    var e = s.editions[i]; s.editions[i] = s.editions[j]; s.editions[j] = e;
    return next;
}

// An exact, unique catalogue identity only. Absent or duplicated identities keep their place
// and cached title without becoming a launch target.
function resolve(saved, entries) {
    var matches = entries.filter(function(e) { return e.id === saved.id; });
    return matches.length === 1 ? matches[0] : null;
}

function reason(s) {
    return KIND_LABELS[s.kind] + " shelf you named. Chosen by you, in your order, saved only on this device. Not a suggestion.";
}

// Collections rows for the theme's thread list. Ids are prefixed "local:" so the optional
// service never receives a membership action for them.
function collections(state, entries) {
    if (!state) return [{id: "local:shelves", shelfId: "", name: "Your shelves", kind: "", origin: "shelf",
        suggestedId: "", source: "", members: [], entries: [], absent: 0, unreadable: true,
        reason: "Saved shelves could not be read. They have been kept unchanged."}];
    return state.shelves.map(function(s) {
        var members = [];
        s.editions.forEach(function(saved) { var e = resolve(saved, entries); if (e) members.push(e); });
        return {id: "local:" + s.id, shelfId: s.id, name: s.name, kind: s.kind, origin: "shelf",
            suggestedId: "", source: "", members: [], entries: members, absent: s.editions.length - members.length,
            reason: s.editions.length ? reason(s) : KIND_LABELS[s.kind] + " shelf you named. Add games from Details → Collections."};
    });
}

// Editor rows for one shelf: its name, kind and order, then members, then delete.
function editorRows(state, shelfId, entries) {
    if (!state) return [{label: "Saved shelves unavailable", value: "Kept unchanged", dim: true}];
    var s = find(state, shelfId);
    if (!s) return [{label: "This shelf is no longer saved", value: "", dim: true}];
    var rows = [{label: "Name", value: s.name, act: "rename"},
                {label: "Kind", value: KIND_LABELS[s.kind], act: "kind"},
                {label: "Shelf order", value: (indexOf(state, shelfId) + 1) + " of " + state.shelves.length, act: "order"}];
    s.editions.forEach(function(saved, i) {
        var e = resolve(saved, entries);
        rows.push({label: e ? e.title : saved.title, entry: e, id: saved.id, act: "member",
                   value: (i + 1) + " / " + s.editions.length + (e ? "" : " · Not in catalogue")});
    });
    rows.push({label: "Delete shelf", value: s.editions.length ? "Empty it first" : "", act: "delete", dim: s.editions.length > 0});
    return rows;
}
