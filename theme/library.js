.pragma library

// Pure helpers for the Personal Library theme. No QML objects are created here.

var STATUSES = ["unknown", "backlog", "playing", "finished", "abandoned"];
var STATUS_LABELS = {
    unknown: "No status",
    backlog: "Backlog",
    playing: "Playing",
    finished: "Finished",
    abandoned: "Left behind"
};
var SORTS = ["alpha", "recent", "lifetime", "recommended"];
var SORT_LABELS = {
    alpha: "A to Z",
    recent: "Recently played",
    lifetime: "Lifetime time",
    recommended: "Recommended"
};
var DEVICES = ["", "here", "nova", "legion"];
var DEVICE_LABELS = { "": "Any device", here: "Route here", nova: "Route on Nova", legion: "Route on Legion" };

// Pegasus stores every x-field as a string list. Join it back into one string.
function extra(game, key) {
    if (!game || !game.extra)
        return "";
    var value = game.extra[key];
    if (value === undefined || value === null)
        return "";
    if (typeof value === "string")
        return value.trim();
    if (value.length !== undefined) {
        var parts = [];
        for (var i = 0; i < value.length; i++)
            parts.push(String(value[i]));
        return parts.join(" ").trim();
    }
    return String(value).trim();
}

function stableId(game) {
    var id = extra(game, "edition-id");
    if (id)
        return id;
    // Fallback only for games the exporter did not tag; the title alone is not unique.
    var path = "";
    if (game.files && game.files.count > 0)
        path = game.files.get(0).path || "";
    return "untagged:" + game.title + (path ? "|" + path : "");
}

function artUrl(game) {
    var a = game.assets;
    if (!a)
        return "";
    return a.boxFront || a.poster || a.steam || a.banner || "";
}

// A number, or null when the field is empty or not a number. Zero stays zero.
function number(raw) {
    if (raw === undefined || raw === null)
        return null;
    var s = String(raw).trim();
    if (!/^-?\d+(\.\d+)?$/.test(s))
        return null;
    return parseFloat(s);
}

function minutesText(raw) {
    var total = typeof raw === "number" ? raw : number(raw);
    if (total === null || total < 0)
        return "";
    total = Math.round(total);
    var h = Math.floor(total / 60);
    var m = total % 60;
    if (h === 0)
        return m + " min";
    return h + "h" + (m ? " " + m + "m" : "");
}

// Milliseconds since the epoch, or null for an empty or unreadable date.
function time(raw) {
    if (!raw)
        return null;
    var t = Date.parse(raw);
    return isNaN(t) ? null : t;
}

function list(raw) {
    if (!raw)
        return [];
    var s = String(raw).trim();
    if (s.charAt(0) === "[") {
        try {
            var parsed = JSON.parse(s);
            if (parsed && parsed.length !== undefined)
                return parsed.map(function(x) { return String(x).trim(); }).filter(function(x) { return x; });
        } catch (err) {
            return [];
        }
        return [];
    }
    return s.split(",").map(function(x) { return x.trim(); }).filter(function(x) { return x; });
}

// Older exports have no x-system-id. Only these two edition shapes say what they are.
function legacySystem(editionId) {
    if (editionId.indexOf("nova:snes:") === 0)
        return { id: "snes", name: "Super Nintendo" };
    if (editionId.indexOf("steam:") === 0)
        return { id: "pc", name: "PC" };
    return { id: "", name: "" };
}

function progressState(raw) {
    var s = String(raw || "").trim().toLowerCase();
    return STATUS_LABELS[s] !== undefined ? s : "unknown";
}

// ROM bytes come from a captured file observation, not a current disk query.
function fileBytes(raw) {
    var value = String(raw === undefined || raw === null ? "" : raw).trim();
    if (!/^\d+$/.test(value)) return null;
    var n = Number(value);
    return isFinite(n) && n <= 9007199254740991 ? n : null;
}

function isoTime(raw) {
    var value = String(raw || "").trim();
    return /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) ? time(value) : null;
}

function utcDateText(stamp) {
    if (stamp === null || stamp === undefined) return "Date unknown";
    var value = new Date(stamp);
    if (typeof stamp === "string" && /^\d{4}-\d{2}-\d{2}$/.test(stamp))
        return !isNaN(value.getTime()) && value.toISOString().slice(0, 10) === stamp ? stamp : "Date unknown";
    return isNaN(value.getTime()) ? "Date unknown" : value.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}

function dateEvidenceText(raw) {
    var value = String(raw || "").trim();
    if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return utcDateText(value);
    var stamp = isoTime(value);
    return stamp === null ? "Date unknown" : utcDateText(stamp);
}

function bytesText(n) {
    if (n === null || n === undefined) return "Unknown";
    var units = ["B", "KiB", "MiB", "GiB", "TiB"];
    var i = 0;
    while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
    return (i === 0 ? String(n) : n.toFixed(n >= 10 ? 1 : 2).replace(/\.?0+$/, "")) + " " + units[i];
}

function storageSummary(entries) {
    var out = { groups: [], largest: [], known: 0, unknown: 0, bytes: 0, oldest: null, newest: null, undated: 0, exported: null };
    var bySystem = {};
    entries.forEach(function(e) {
        if (e.systemId === "androidapps" || e.systemId === "emulators") return;
        var id = e.systemId || "?";
        var g = bySystem[id];
        if (!g) {
            g = { id: id, name: e.systemName || "Unknown system", known: 0, unknown: 0, bytes: 0, oldest: null, newest: null, undated: 0 };
            bySystem[id] = g; out.groups.push(g);
        }
        if (e.sizeBytes === null || e.sizeBytes === undefined) { g.unknown++; out.unknown++; }
        else {
            g.known++; g.bytes += e.sizeBytes; out.known++; out.bytes += e.sizeBytes;
            out.largest.push(e);
            if (e.sizeObservedAt !== null && e.sizeObservedAt !== undefined) {
                g.oldest = g.oldest === null ? e.sizeObservedAt : Math.min(g.oldest, e.sizeObservedAt);
                g.newest = g.newest === null ? e.sizeObservedAt : Math.max(g.newest, e.sizeObservedAt);
                out.oldest = out.oldest === null ? e.sizeObservedAt : Math.min(out.oldest, e.sizeObservedAt);
                out.newest = out.newest === null ? e.sizeObservedAt : Math.max(out.newest, e.sizeObservedAt);
            } else { g.undated++; out.undated++; }
        }
        if (e.catalogueGeneratedAt !== null && e.catalogueGeneratedAt !== undefined)
            out.exported = out.exported === null ? e.catalogueGeneratedAt : Math.max(out.exported, e.catalogueGeneratedAt);
    });
    out.groups.sort(function(a, b) { return a.name.localeCompare(b.name); });
    out.largest.sort(function(a, b) { return b.sizeBytes - a.sizeBytes || a.title.localeCompare(b.title); });
    return out;
}

// Grouping is presentation only: member edition IDs, routes and progress never change.
function discNumber(raw) {
    var n = fileBytes(raw);
    return n !== null && n > 0 ? n : null;
}

function defaultDisc(members) {
    return members.slice().sort(function(a, b) {
        var aa = a.lastPlayedHere === null || a.lastPlayedHere === undefined ? -1 : a.lastPlayedHere;
        var bb = b.lastPlayedHere === null || b.lastPlayedHere === undefined ? -1 : b.lastPlayedHere;
        return bb - aa || a.discNumber - b.discNumber;
    })[0] || null;
}

function discPresentation(members, scope) {
    var preferred = defaultDisc(members);
    var base = scope || preferred;
    var out = {};
    Object.keys(base).forEach(function(k) { out[k] = base[k]; });
    out.discMembers = members.slice().sort(function(a, b) { return a.discNumber - b.discNumber; });
    out.discEdition = base;
    out.discDefaultId = preferred.id;
    out.title = base.discSetName;
    if (!out.art) {
        var art = members.filter(function(e) { return !!e.art; });
        if (art.length) out.art = art[0].art;
    }
    out.sortKey = out.title.toLowerCase();
    out.launchable = members.some(function(e) { return e.launchable && !e.game.missing; });
    out.missing = members.every(function(e) { return e.game.missing; });
    out.lastPlayedHere = preferred.lastPlayedHere;
    return out;
}

function presentationKey(e) {
    return e.discMembers ? "disc-set:" + e.discSetId : "edition:" + e.id;
}

function groupEntries(entries) {
    var candidates = {}, groups = {}, out = [], seen = {};
    entries.forEach(function(e) {
        if (!e.discSetId || !e.discSetName || e.discNumber === null || e.discNumber === undefined) return;
        var key = "$" + e.discSetId;
        if (!candidates[key]) candidates[key] = [];
        candidates[key].push(e);
    });
    Object.keys(candidates).forEach(function(key) {
        var members = candidates[key], numbers = {};
        var valid = members.length >= 2 && members.every(function(e) {
            if (numbers[e.discNumber] || e.systemId !== members[0].systemId || e.discSetName !== members[0].discSetName) return false;
            numbers[e.discNumber] = true;
            return true;
        });
        if (valid) groups[key] = discPresentation(members);
    });
    entries.forEach(function(e) {
        var group = groups["$" + e.discSetId];
        var belongs = group && group.discMembers.some(function(m) { return m.id === e.id; });
        if (!belongs) { out.push(e); return; }
        var key = presentationKey(group);
        if (!seen[key]) { seen[key] = true; out.push(group); }
    });
    return out;
}

function presentEdition(e, presentations) {
    for (var i = 0; i < presentations.length; i++) {
        var p = presentations[i];
        if (p.discMembers && p.discMembers.some(function(m) { return m.id === e.id; }))
            return discPresentation(p.discMembers, e);
    }
    return e;
}

function discReadyCount(e) {
    return e.discMembers ? e.discMembers.filter(function(m) { return m.launchable && !m.game.missing; }).length : 0;
}

function makeEntry(game) {
    var id = stableId(game);
    var systemId = extra(game, "system-id").toLowerCase();
    var systemName = extra(game, "system-name");
    if (!systemId) {
        var legacy = legacySystem(id);
        systemId = legacy.id;
        systemName = systemName || legacy.name;
    }
    var minutesRaw = extra(game, "minutes-value");
    var minutesSource = "lifetime";
    if (minutesRaw === "") {
        minutesRaw = extra(game, "canon-minutes");
        minutesSource = "steam";
    }
    var minutesValue = number(minutesRaw);
    var lastRaw = extra(game, "last-played");
    var localPlayed = time(game.lastPlayed);
    if (localPlayed !== null && localPlayed <= 0) localPlayed = null;
    var score = number(extra(game, "recommendation-score"));
    var reason = extra(game, "recommendation-reason");
    var catalogStatus = progressState(extra(game, "progress-state"));
    var story = extra(game, "story");
    return {
        game: game,
        id: id,
        title: game.title,
        sortKey: (game.sortBy || game.title || "").toLowerCase(),
        art: artUrl(game),
        developer: game.developer || "",
        appPackage: extra(game, "app-package"),
        installations: installationData(extra(game, "installations")),
        capacity: capacityData(extra(game, "storage-volume")),
        novaGameplayNote: extra(game, "nova-gameplay-note"),
        novaGameplaySource: extra(game, "nova-gameplay-source"),
        novaGameplayObservedAt: extra(game, "nova-gameplay-observed-at"),
        displayAspect: extra(game, "display-aspect"),
        displayAspectSource: extra(game, "display-aspect-source"),
        genre: game.genre || "",
        home: extra(game, "home") === "true",
        launchable: extra(game, "launchable") === "true" && !game.missing,
        missing: game.missing,
        route: extra(game, "route-label"),
        discSetId: extra(game, "disc-set-id"),
        discSetName: extra(game, "disc-set-name"),
        discNumber: discNumber(extra(game, "disc-number")),
        systemId: systemId,
        systemName: systemName || (systemId ? systemId.toUpperCase() : ""),
        readyDevices: list(extra(game, "ready-devices")).map(function(d) { return d.toLowerCase(); }),
        minutesValue: minutesValue,
        minutes: minutesText(minutesValue),
        minutesSource: minutesSource,
        lastPlayed: time(lastRaw),
        lastPlayedHere: localPlayed,
        nova: extra(game, "nova-location"),
        legion: extra(game, "legion-location"),
        story: story,
        sizeBytes: fileBytes(extra(game, "size-bytes")),
        sizeObservedAt: isoTime(extra(game, "size-observed-at")),
        catalogueGeneratedAt: isoTime(extra(game, "catalogue-generated-at")),
        source: extra(game, "catalog-source"),
        deviceFit: extra(game, "device-fit"),
        threadIds: list(extra(game, "thread-ids")),
        catalogStatus: catalogStatus,
        catalogScore: score,
        catalogReason: reason,
        // Effective personal values; applyPersonal() replaces these when the bridge reports.
        status: catalogStatus,
        statusSource: catalogStatus !== "unknown" ? "catalogue" : "",
        checkpoint: story,
        checkpointSource: story ? "catalogue" : "",
        revision: null,
        pending: false,
        conflict: false,
        recScore: score,
        recReason: reason,
        recSource: score !== null || reason ? "catalogue" : ""
    };
}

function indexOfId(list, id) {
    if (!id)
        return -1;
    for (var i = 0; i < list.length; i++)
        if (list[i].id === id || (list[i].discMembers && list[i].discMembers.some(function(m) { return m.id === id; })))
            return i;
    return -1;
}

// Equal-area sizing at the art's natural ratio, then shrunk to fit the box.
function fitArea(ratio, area, maxW, maxH) {
    if (!(ratio > 0))
        ratio = 2 / 3;
    var h = Math.sqrt(area / ratio);
    var w = h * ratio;
    var k = Math.min(1, maxW / w, maxH / h);
    return { w: Math.round(w * k), h: Math.round(h * k) };
}

// "Gamepad 2 (X)" becomes "X"; keyboard names pass through.
function keyLabel(keylist, fallback) {
    if (!keylist)
        return fallback;
    var keyboard = "";
    for (var i = 0; i < keylist.length; i++) {
        var name = keylist[i].name();
        var m = /\(([^)]+)\)$/.exec(name);
        if (m)
            return m[1];
        if (!keyboard && name)
            keyboard = name;
    }
    return keyboard || fallback;
}

function isSteamGame(e) {
    return !!(e && e.systemId === "pc" && e.id.indexOf("steam:") === 0);
}

function appMatches(e, packageName, title) {
    return e.systemId === "androidapps" && (e.appPackage ? e.appPackage === packageName : e.title === title);
}

function configuredApp(entries, packageName, title) {
    var available = entries.filter(function(e) { return e.launchable && !e.game.missing && appMatches(e, packageName, title); });
    available.sort(function(a, b) {
        var aa = a.appPackage === packageName ? 0 : 1, bb = b.appPackage === packageName ? 0 : 1;
        return aa - bb || byTitle(a, b);
    });
    return available[0] || null;
}

function appPurpose(e) {
    if (!e) return "";
    if (appMatches(e, "com.droiddeck.launcher", "DroidDeck")) return "Steam library, installs and game setup";
    if (appMatches(e, "dev.jdtech.jellyfin", "Findroid") || appMatches(e, "org.jellyfin.mobile", "Jellyfin")) return "Jellyfin films and shows";
    if (e.title === "Files" && e.systemId === "androidapps") return "Browse files on this device";
    return "Android app";
}

function routeSentence(e) {
    if (e.systemId === "androidapps")
        return e.game.missing ? "This app shortcut is unavailable here."
             : e.launchable ? "App shortcut set up here."
             : "This app is not set up in Library yet.";
    if (e.discMembers)
        return e.discMembers.length + " discs · " + discReadyCount(e) + " set up here. Choose a disc before launching. File presence does not prove every disc runs.";
    if (e.missing)
        return "The file isn't where the library expects it on this device, so Play is off.";
    if (!e.launchable)
        return "No launch route is set up for this here yet, so Play is off.";
    var via = e.route ? "Opens in " + e.route + "." : "Has a launch route on this device.";
    return via + " A configured route does not prove compatibility or performance.";
}

function shortRoute(e) {
    if (e.discMembers) return e.discMembers.length + " discs · " + discReadyCount(e) + " set up here";
    if (e.missing)
        return "File not found here";
    if (!e.launchable)
        return "Not set up here";
    return e.route;
}

function initialOf(e) {
    var c = e.sortKey.charAt(0);
    return /[a-z]/.test(c) ? c : "#";
}

function deviceName(d) {
    return d === "nova" ? "Nova" : d === "legion" ? "Legion" : d.charAt(0).toUpperCase() + d.slice(1);
}

// ---------- the optional native bridge ----------

function str(v) {
    return v === undefined || v === null ? "" : String(v);
}

function memberIds(raw) {
    var out = [];
    if (!raw || raw.length === undefined)
        return out;
    for (var i = 0; i < raw.length; i++) {
        var m = raw[i];
        var id = typeof m === "string" ? m : m ? str(m.editionId || m.id) : "";
        if (id && out.indexOf(id) === -1)
            out.push(id);
    }
    return out;
}

function normalThread(t, origin) {
    if (!t)
        return null;
    var id = str(t.id || t.threadId || t.suggestedId);
    if (!id)
        return null;
    return {
        id: id,
        name: str(t.name || t.title) || id,
        reason: str(t.reason || t.explanation),
        source: str(t.source || t.basis),
        origin: origin,
        suggestedId: str(t.suggestedId),
        members: memberIds(t.members || t.editionIds || t.editions)
    };
}

// read({}) comes back as a plain object. Anything malformed becomes empty, not invented.
function normalizeDevice(raw) {
    var out = { entries: {}, kept: [], suggested: [], recs: {}, recOrder: [], sync: { state: "", message: "", pending: 0 } };
    if (!raw)
        return out;
    var personal = raw.personal || {};
    var entries = personal.entries || {};
    for (var id in entries) {
        var p = entries[id] || {};
        var cp = p.checkpoint;
        if (cp && typeof cp === "object")
            cp = cp.text;
        out.entries[id] = {
            checkpoint: str(cp).trim(),
            status: progressState(p.status),
            revision: p.revision === undefined ? null : p.revision,
            pending: p.pending === true || (typeof p.pending === "number" && p.pending > 0),
            conflict: p.conflict === true || (!!p.conflict && typeof p.conflict === "object")
        };
    }
    var kept = personal.threads || [];
    for (var k = 0; k < kept.length; k++) {
        var kt = normalThread(kept[k], "kept");
        if (kt) out.kept.push(kt);
    }
    var keptIds = {};
    out.kept.forEach(function(t) { keptIds[t.id] = true; if (t.suggestedId) keptIds[t.suggestedId] = true; });
    var sugg = raw.threads || [];
    for (var s = 0; s < sugg.length; s++) {
        var st = normalThread(sugg[s], "suggested");
        if (st && !keptIds[st.id]) out.suggested.push(st);
    }
    var recs = raw.recommendations || [];
    for (var r = 0; r < recs.length; r++) {
        var rec = recs[r] || {};
        var rid = str(rec.editionId || rec.id);
        if (!rid || out.recs[rid])
            continue;
        out.recs[rid] = { score: number(rec.score), reason: str(rec.reason || rec.explanation),
                          source: str(rec.source || (rec.sources || []).map(function(source) { return typeof source === "string" ? source : str(source.kind); }).join(", ")) };
        out.recOrder.push(rid);
    }
    var sync = raw.sync || {};
    out.sync = { state: str(sync.state), message: str(sync.message), pending: number(sync.pending) || 0 };
    return out;
}

// Write the bridge's personal record over the catalogue's. The bridge wins whenever it has a
// record for the edition, including an explicit "unknown" the user chose.
function applyPersonal(entries, device) {
    for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        var p = device ? device.entries[e.id] : null;
        if (p) {
            e.status = p.status;
            e.statusSource = p.status !== "unknown" ? "you" : "";
            e.checkpoint = p.checkpoint;
            e.checkpointSource = p.checkpoint ? "you" : "";
            e.revision = p.revision;
            e.pending = p.pending;
            e.conflict = p.conflict;
        } else {
            e.status = e.catalogStatus;
            e.statusSource = e.catalogStatus !== "unknown" ? "catalogue" : "";
            e.checkpoint = e.story;
            e.checkpointSource = e.story ? "catalogue" : "";
            e.revision = null;
            e.pending = false;
            e.conflict = false;
        }
        var rec = device ? device.recs[e.id] : null;
        if (rec) {
            e.recScore = rec.score;
            e.recReason = rec.reason;
            e.recSource = rec.source || "Device Library";
        } else {
            e.recScore = e.catalogScore;
            e.recReason = e.catalogReason;
            e.recSource = e.catalogScore !== null || e.catalogReason ? "catalogue" : "";
        }
    }
}

// ---------- filtering and sorting ----------

function emptyFilters() {
    return { system: "", device: "", kept: false, status: "" };
}

function filtersActive(f) {
    return !!(f && (f.system || f.device || f.kept || f.status));
}

function readyOn(e, device) {
    if (!device)
        return true;
    if (device === "here")
        return e.launchable;
    return e.readyDevices.indexOf(device) !== -1;
}

function matches(e, f, pinned, query) {
    if (f.system === "?" ? e.systemId !== "" : f.system && e.systemId !== f.system)
        return false;
    if (!readyOn(e, f.device))
        return false;
    if (f.kept && !pinned[e.id])
        return false;
    if (f.status && e.status !== f.status)
        return false;
    if (query && e.title.toLowerCase().indexOf(query) === -1 && e.sortKey.indexOf(query) === -1)
        return false;
    return true;
}

function filterEntries(entries, f, pins, query) {
    var pinned = {};
    for (var i = 0; i < pins.length; i++)
        pinned[pins[i]] = true;
    var q = (query || "").trim().toLowerCase();
    var out = [];
    entries.forEach(function(e) {
        if (!e.discMembers) { if (matches(e, f, pinned, q)) out.push(e); return; }
        var nameMatch = q && e.title.toLowerCase().indexOf(q) !== -1;
        var matching = e.discMembers.filter(function(m) { return matches(m, f, pinned, nameMatch ? "" : q); });
        if (matching.length) out.push(discPresentation(e.discMembers, defaultDisc(matching)));
    });
    return out;
}

function byTitle(a, b) {
    if (a.sortKey < b.sortKey) return -1;
    if (a.sortKey > b.sortKey) return 1;
    return a.order - b.order;
}

// Larger first; unknown values always after every known one, then by title.
function byValue(key) {
    return function(a, b) {
        var va = a[key], vb = b[key];
        var ka = va !== null && va !== undefined, kb = vb !== null && vb !== undefined;
        if (ka && !kb) return -1;
        if (!ka && kb) return 1;
        if (ka && kb && va !== vb) return vb - va;
        return byTitle(a, b);
    };
}

function sortEntries(entries, mode) {
    var out = entries.slice();
    if (mode === "local-recent") out.sort(byValue("lastPlayedHere"));
    else if (mode === "recent") out.sort(byValue("lastPlayed"));
    else if (mode === "lifetime") out.sort(byValue("minutesValue"));
    else if (mode === "recommended") out.sort(byValue("recScore"));
    else out.sort(byTitle);
    return out;
}

// Systems present in the catalogue, by name, for the filter to cycle through.
function systemsOf(entries) {
    var seen = {};
    var out = [];
    var unknown = 0;
    for (var i = 0; i < entries.length; i++) {
        var e = entries[i];
        if (!e.systemId) { unknown++; continue; }
        if (!seen[e.systemId]) {
            seen[e.systemId] = { id: e.systemId, name: e.systemName, count: 0 };
            out.push(seen[e.systemId]);
        }
        seen[e.systemId].count++;
    }
    out.sort(function(a, b) { return a.name.toLowerCase() < b.name.toLowerCase() ? -1 : a.name.toLowerCase() > b.name.toLowerCase() ? 1 : 0; });
    if (unknown)
        out.push({ id: "?", name: "Unknown system", count: unknown });
    return out;
}

function cycle(values, current, step) {
    var i = values.indexOf(current);
    if (i < 0) i = 0;
    return values[(i + step + values.length) % values.length];
}

// After the list changes, keep the same edition, else the nearest one that was beside it.
function stableIndex(next, previous, anchorId, currentId) {
    var i = indexOfId(next, anchorId);
    if (i >= 0) return i;
    i = indexOfId(next, currentId);
    if (i >= 0) return i;
    var at = indexOfId(previous, currentId);
    if (at < 0) return 0;
    var present = {};
    for (var n = 0; n < next.length; n++) present[next[n].id] = n;
    for (var f = at + 1; f < previous.length; f++)
        if (present[previous[f].id] !== undefined) return present[previous[f].id];
    for (var b = at - 1; b >= 0; b--)
        if (present[previous[b].id] !== undefined) return present[previous[b].id];
    return 0;
}

function sortValueText(e, mode, now) {
    if (mode === "recent")
        return e.lastPlayed !== null ? ago(e.lastPlayed, now) : "";
    if (mode === "lifetime")
        return e.minutes;
    return "";
}

var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function ago(t, now) {
    var days = Math.floor((now - t) / 86400000);
    if (days < 1) return "Today";
    if (days < 2) return "Yesterday";
    if (days < 14) return days + " days ago";
    var d = new Date(t);
    var year = new Date(now).getFullYear() === d.getFullYear() ? "" : " " + d.getFullYear();
    return d.getDate() + " " + MONTHS[d.getMonth()] + year;
}

// ---------- threads ----------

// Kept threads first, then explained suggestions, then catalogue groupings the bridge didn't
// name. Recommendations become one suggested group when anything has a reason or score.
function buildThreads(entries, device) {
    var byId = {};
    for (var i = 0; i < entries.length; i++)
        if (!byId[entries[i].id]) byId[entries[i].id] = entries[i];

    function resolve(t) {
        var ids = t.members.slice();
        for (var j = 0; j < entries.length; j++)
            if (entries[j].threadIds.indexOf(t.id) !== -1 && ids.indexOf(entries[j].id) === -1)
                ids.push(entries[j].id);
        var members = [];
        var absent = 0;
        ids.forEach(function(id) { if (byId[id]) members.push(byId[id]); else absent++; });
        members.sort(byTitle);
        var copy = {};
        for (var k in t) copy[k] = t[k];
        copy.entries = members;
        copy.absent = absent;
        return copy;
    }

    var out = [];
    var known = {};
    var kept = device ? device.kept : [];
    var suggested = device ? device.suggested : [];
    // A kept thread stands in for the suggestion it came from, so that id isn't shown twice.
    kept.forEach(function(t) {
        known[t.id] = true;
        if (t.suggestedId) known[t.suggestedId] = true;
        out.push(resolve(t));
    });

    var recs = entries.filter(function(e) { return e.recScore !== null || e.recReason; });
    if (recs.length) {
        var g = resolve({ id: "recommended", name: "Suggested games", origin: "recommendations",
                          reason: "Each game says why it's here.", source: "", suggestedId: "",
                          members: [] });
        g.entries = recs.sort(byValue("recScore"));
        out.push(g);
    }

    suggested.forEach(function(t) { known[t.id] = true; out.push(resolve(t)); });

    var loose = [];
    entries.forEach(function(e) {
        e.threadIds.forEach(function(id) { if (!known[id] && loose.indexOf(id) === -1) loose.push(id); });
    });
    loose.sort();
    loose.forEach(function(id) {
        out.push(resolve({ id: id, name: id, origin: "catalogue", reason: "",
                           source: "catalogue export", suggestedId: "", members: [] }));
    });
    return out;
}

function threadNamesFor(e, threads) {
    var names = [];
    for (var i = 0; i < threads.length; i++) {
        var t = threads[i];
        if (t.origin === "recommendations")
            continue;
        if (indexOfId(t.entries, e.id) !== -1)
            names.push(t.name);
    }
    return names;
}

function originLabel(t) {
    if (t.origin === "kept") return "Kept";
    if (t.origin === "catalogue") return "Catalogue";
    return "Suggested";
}


// Installation observations are independent of launch routes and gameplay checks.
function installationData(raw) {
    if (!raw || raw.length > 16384) return {};
    try { var data = JSON.parse(raw); return data && typeof data === "object" && !Array.isArray(data) ? data : {}; }
    catch (err) { return {}; }
}

function installation(e, device) {
    if (e && e.discMembers) {
        var members = e.discMembers.map(function(m) { return installation(m, device); });
        var installed = members.filter(function(m) { return m.state === "installed"; }).length;
        var absent = members.filter(function(m) { return m.state === "absent"; }).length;
        var state = installed === members.length ? "installed" : absent === members.length ? "absent"
                  : installed || members.some(function(m) { return m.state === "partial"; }) ? "partial" : "unknown";
        return { state: state, observedAt: members.map(function(m) { return m.observedAt; }).filter(Boolean).sort()[0] || "",
                 source: "Per-disc observations", scopeComplete: absent === members.length, offline: members.some(function(m) { return m.offline; }) };
    }
    var raw = e && e.installations ? e.installations[device] : null;
    var valid = raw && ["installed", "absent", "partial"].indexOf(raw.state) !== -1
                && typeof raw.source === "string" && raw.source.trim() && dateEvidenceText(raw.observedAt) !== "Date unknown"
                && (raw.state !== "absent" || raw.scopeComplete === true);
    return valid ? { state: raw.state, observedAt: raw.observedAt, source: raw.source, scopeComplete: raw.scopeComplete === true, offline: raw.offline === true }
                 : { state: "unknown", observedAt: "", source: "", scopeComplete: false, offline: false };
}

function installLabel(e, device) {
    var v = installation(e, device);
    return { installed: "Installed", absent: "Not installed", partial: "Incomplete", unknown: "Not checked" }[v.state];
}

function availabilityText(e) {
    var nova = installation(e, "nova"), legion = installation(e, "legion");
    if (nova.state === "installed" && legion.state === "installed") return "Nova + Legion";
    if (nova.state === "installed") return "On Nova";
    if (legion.state === "installed") return "Seen on Legion";
    if (nova.state === "absent" && legion.state === "absent") return "Absent in both scans";
    if (nova.state === "partial") return "Part of this game is on Nova";
    if (nova.state === "absent") return "Not on Nova";
    return "Install status not checked";
}

function capacityData(raw) {
    if (!raw || raw.length > 4096) return null;
    try {
        var v = JSON.parse(raw);
        if (!v || v.id !== "internal-data" || !v.source || dateEvidenceText(v.observedAt) === "Date unknown") return null;
        for (var i = 0; i < 3; i++) {
            var n = v[["total", "used", "free"][i]];
            if (typeof n !== "number" || !isFinite(n) || Math.floor(n) !== n || n < 0 || n > 9007199254740991) return null;
        }
        return v.total > 0 && v.used + v.free <= v.total ? v : null;
    } catch (err) { return null; }
}

function storageCapacity(entries) {
    var captured = entries.map(function(e) { return e.capacity; }).filter(function(v) { return v !== null && v !== undefined; });
    captured.sort(function(a, b) { return time(b.observedAt) - time(a.observedAt); });
    if (!captured.length) return null;
    var newest = captured[0];
    if (captured.some(function(v) { return v.observedAt === newest.observedAt && (v.total !== newest.total || v.used !== newest.used || v.free !== newest.free); })) return null;
    return newest;
}
