const test = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const I = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../theme/InputProfiles.js'), 'utf8').replace(/^\.pragma library\s*/, ''), I);
const plain = x => JSON.parse(JSON.stringify(x));
const key = {editionId: 'demo:orbit-us', runtimeId: 'demo-runtime', runtimeVersion: '1.2.3'};
const prefs = () => ({sensitivity: {x: 1, y: 1.5}, deadzone: {left: 0.1, right: 0.2},
    inversion: {x: false, y: true}, triggers: {left: 0.25, right: 0.75},
    holdToggle: {aim: 'hold', sprint: 'toggle', crouch: 'hold'}});
const start = () => I.store(undefined);
const envelope = (p = prefs(), binding = key) => JSON.stringify({version: 1, profile: {binding, preferences: p}});

test('offline edit, serialized reopen, replacement and clear preserve preceding states', () => {
    const empty = start(), first = I.edit(empty, key, prefs()), original = JSON.stringify(first);
    assert.equal(empty.profiles.length, 0);
    assert.deepEqual(plain(I.profile(I.store(JSON.parse(original)), key).preferences), prefs());
    const changed = prefs(); changed.sensitivity.x = 2;
    const next = I.edit(first, key, changed); changed.sensitivity.x = 9;
    assert.equal(next.profiles.length, 1); assert.equal(I.profile(next, key).preferences.sensitivity.x, 2);
    const detached = I.profile(next, key); detached.preferences.sensitivity.x = 8;
    assert.equal(I.profile(next, key).preferences.sensitivity.x, 2);
    assert.equal(I.clear(next, key).profiles.length, 0); assert.equal(JSON.stringify(first), original);
    assert.equal(next.profiles.length, 1); assert.equal(I.clear(empty, key), null);
});
test('exact edition, runtime and version stay separate with no fuzzy title matching', () => {
    let s = I.edit(start(), key, prefs());
    const alternatives = [{...key, editionId: 'demo:orbit-eu'}, {...key, runtimeId: 'other-runtime'}, {...key, runtimeVersion: '1.2.4'}];
    for (const other of alternatives) {
        assert.equal(I.profile(s, other), null); assert.equal(I.importProfile(s, other, envelope()), null);
        s = I.edit(s, other, prefs());
    }
    assert.equal(s.profiles.length, 4); assert.equal(I.clear(s, key).profiles.length, 3);
});
test('single-profile strict export/import round trip replaces only its exact binding', () => {
    const source = I.edit(start(), key, prefs()), text = I.exportProfile(source, key);
    const other = {...key, editionId: 'demo:other'};
    const target = I.edit(start(), other, prefs()), before = JSON.stringify(target);
    const imported = I.importProfile(target, key, text);
    assert.equal(imported.profiles.length, 2); assert.equal(JSON.stringify(target), before);
    assert.deepEqual(plain(I.profile(imported, other)), plain(I.profile(target, other)));
    assert.equal(I.importProfile(imported, key, text).profiles.length, 2);
    assert.equal(I.exportProfile(target, key), null);
});
test('bounded numeric settings accept endpoints and refuse coercion/nonfinite/out-of-range values', () => {
    for (const [group, field, min, max] of [['sensitivity','x',0.1,10], ['sensitivity','y',0.1,10],
        ['deadzone','left',0,0.95], ['deadzone','right',0,0.95], ['triggers','left',0,1], ['triggers','right',0,1]]) {
        for (const value of [min, max]) { const p = prefs(); p[group][field] = value; assert.ok(I.edit(start(), key, p)); }
        for (const value of [min - 0.01, max + 0.01, NaN, Infinity, -Infinity, '1', null, true]) {
            const p = prefs(); p[group][field] = value; assert.equal(I.edit(start(), key, p), null);
        }
    }
    for (const [group, field, value] of [['inversion','x',1], ['inversion','y','true'], ['holdToggle','aim','auto'],
        ['holdToggle','sprint',true], ['holdToggle','crouch','HOLD']]) {
        const p = prefs(); p[group][field] = value; assert.equal(I.edit(start(), key, p), null);
    }
});
test('malformed/future storage refuses edits/import/clear/export without mutation', () => {
    const record = {binding: key, preferences: prefs()};
    for (const raw of [null, false, [], {}, 'broken', {version:2, profiles:[]}, {version:1,profiles:[],extra:1},
        {version:1,profiles:[record,record]}, {version:1,profiles:[{...record,applied:true}]},
        {version:1,profiles:[{...record,preferences:{...prefs(),command:'never'}}]}]) {
        const before = JSON.stringify(raw); assert.equal(I.store(raw), null);
        assert.equal(I.edit(raw, key, prefs()), null); assert.equal(I.importProfile(raw, key, envelope()), null);
        assert.equal(I.clear(raw, key), null); assert.equal(I.exportProfile(raw, key), null);
        assert.equal(JSON.stringify(raw), before); assert.equal(I.status(raw, key).storage, 'unavailable');
    }
    assert.equal(I.edit(undefined, key, prefs()), null);
    assert.equal(I.importProfile(undefined, key, envelope()), null);
});
test('invalid imports refuse atomically including duplicate and escaped duplicate keys', () => {
    const s = I.edit(start(), key, prefs()), before = JSON.stringify(s), valid = envelope();
    for (const text of ['', '{', 'null', '[]', valid + ' trailing', ' '.repeat(I.IMPORT_LIMIT + 1),
        valid.replace('"version":1', '"version":2'), valid.replace('"version":1', '"version":1,"version":1'),
        valid.replace('"version":1', '"version":1,"ver\\u0073ion":1'),
        valid.replace('"x":1', '"x":1,"x":2'), valid.replace('"x":1', '"x":1e999'),
        valid.replace('"profile":', '"extra":true,"profile":'), valid.replace('"x":1', '"command":"never","x":1')]) {
        assert.equal(I.importProfile(s, key, text), null, text.slice(0,100)); assert.equal(JSON.stringify(s), before);
    }
});
test('strict bindings refuse unstable ids, unknown versions, extra fields and unsafe tokens', () => {
    for (const binding of [{...key,editionId:''}, {...key,editionId:'untagged:thing'}, {...key,editionId:'__proto__'},
        {...key,editionId:'demo:bad\n'}, {...key,runtimeId:'/path'}, {...key,runtimeId:'unknown'},
        {...key,runtimeVersion:'latest'}, {...key,runtimeVersion:'1\n'}, {...key,runtimeVersion:'v'.repeat(81)},
        {...key,title:'Same title'}]) assert.equal(I.edit(start(), binding, prefs()), null);
    const p = prefs(); delete p.deadzone.left; assert.equal(I.edit(start(), key, p), null);
});
test('profile capacity refuses only new bindings and leaves replacement/clear available', () => {
    const raw = {version:1,profiles:Array.from({length:I.LIMIT}, (_,i) => ({binding:{...key,editionId:'demo:'+i},preferences:prefs()}))};
    const s = I.store(raw); assert.ok(s); assert.equal(I.edit(s,key,prefs()), null);
    const existing = {...key,editionId:'demo:0'}; assert.ok(I.edit(s,existing,prefs())); assert.ok(I.clear(s,existing));
    raw.profiles.push({binding:key,preferences:prefs()}); assert.equal(I.store(raw), null);
});
test('saved preferences and any imported support claims never imply runtime application', () => {
    const s = I.importProfile(start(), key, envelope()), status = I.status(s,key);
    assert.equal(status.saved,true); assert.equal(status.support,'unknown'); assert.equal(status.application,'not-applied');
    assert.match(status.message,/have not been applied/);
    const raw = JSON.parse(envelope()); raw.profile.support = 'verified';
    assert.equal(I.importProfile(s,key,JSON.stringify(raw)),null);
    assert.equal(I.status(start(),key).saved,false);
});

test('editor adjustments are bounded, exact and independent of saved values', () => {
    const first=I.defaults();assert.equal(I.preferences(first),true);
    for(let f=0;f<I.FIELDS.length;f++){
        let value=I.copy(first);
        for(let n=0;n<150;n++)value=I.adjust(value,f,1);
        assert.equal(I.preferences(value),true);assert.ok(I.display(value,f));
        for(let n=0;n<150;n++)value=I.adjust(value,f,-1);
        assert.equal(I.preferences(value),true);
    }
    assert.deepEqual(plain(first),plain(I.defaults()));
    assert.equal(I.adjust(first,-1,1),null);assert.equal(I.adjust(first,1,0),null);
    assert.equal(I.adjust(first,1.5,1),null);
});
test('editor binding uses the declared exact setup and refuses ambiguous runtime placeholders', () => {
    const entry={id:'demo:orbit',systemId:'snes'};
    assert.deepEqual(plain(I.setup(entry,null,{runtime:'demo-runtime',version:'1.2.3'})),{editionId:entry.id,runtimeId:'demo-runtime',runtimeVersion:'1.2.3'});
    assert.equal(I.setup(entry,null,{runtime:'demo-runtime',version:'unknown'}),null);
    assert.equal(I.setup({...entry,discMembers:[]},null,{runtime:'demo',version:'1'}),null);
    assert.equal(I.setup({...entry,systemId:'androidapps'},null,{runtime:'demo',version:'1'}),null);
    assert.equal(I.setup(entry,null,null),null);
    const key=I.setup(entry,{runtime:'droiddeck',version:'0.4'},{runtime:'stale-runtime',version:'1'});
    assert.equal(key.runtimeId,'droiddeck');assert.equal(key.runtimeVersion,'0.4');
});
test('recorded multiword runtime names retain their exact identity without slug collisions', () => {
    const entry={id:'native:fixture:edition',systemId:'native'};
    for(const runtime of ['Ship of Harkinian Android','SM64 Coop Deluxe Android','DevilutionX Android']) {
        const key=I.setup(entry,null,{runtime,version:'1.2.3'});assert.ok(key);assert.equal(key.runtimeId,runtime);
        const saved=I.edit(start(),key,I.defaults());assert.ok(saved);
        assert.ok(I.importProfile(start(),key,I.exportProfile(saved,key)));
        assert.equal(I.importProfile(start(),{...key,runtimeId:runtime.replaceAll(' ','-')},I.exportProfile(saved,key)),null);
        assert.equal(I.profile(saved,{...key,runtimeVersion:'1.2.4'}),null);
    }
    const a=I.setup(entry,null,{runtime:'Fixture Runtime',version:'1.2.3'}),b=I.setup(entry,null,{runtime:'Fixture-Runtime',version:'1.2.3'});
    const saved=I.edit(I.edit(start(),a,I.defaults()),b,I.defaults());assert.equal(saved.profiles.length,2);
    for(const runtime of [' Fixture Runtime','Fixture Runtime ','Fixture\nRuntime','/Fixture','unknown','x'.repeat(161)])
        assert.equal(I.setup(entry,null,{runtime,version:'1.2.3'}),null);
});
test('native map key ordering is equivalent without hiding a changed preference or binding', () => {
    const saved=I.edit(start(),key,prefs());
    const ordered=value=>Array.isArray(value)?value.map(ordered):value && typeof value==='object'?Object.fromEntries(Object.keys(value).sort().map(k=>[k,ordered(value[k])])):value;
    const native=ordered(plain(saved));assert.equal(I.equalState(saved,native),true);
    native.profiles[0].preferences.triggers.left=0.5;assert.equal(I.equalState(saved,native),false);
    native.profiles[0].preferences.triggers.left=0.25;native.profiles[0].binding.runtimeVersion='1.2.4';assert.equal(I.equalState(saved,native),false);
    assert.equal(I.equalState(null,saved),false);
});
