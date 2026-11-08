const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const Lib=vm.createContext({});
vm.runInContext(fs.readFileSync(require('node:path').join(__dirname,'../theme/library.js'),'utf8').replace(/^\.pragma library\s*/,''),Lib);
const plain=x=>JSON.parse(JSON.stringify(x));
const entry=(id,systemId='snes')=>({id,systemId,title:id,sortKey:id,readyDevices:[],status:'playing',launchable:true});
test('session labels are explicit; telemetry and profile names never supply a duration',()=>{
 const a=entry('demo:a');a.minutesValue=5;a.sessionProfile='five';
 Lib.applySessions([a],Lib.sessionStore(null));assert.equal(Lib.sessionValue(a),'unknown');
 const store=Lib.changeSession(Lib.sessionStore(null),a,'twenty');Lib.applySessions([a],store);
 assert.equal(Lib.sessionValue(a),'twenty');assert.equal(a.minutesValue,5);
});
test('every disc is edited and cleared together without changing unrelated editions',()=>{
 const a=entry('demo:disc1'),b=entry('demo:disc2'),set={...a,discMembers:[a,b]};
 const before={version:1,labels:{'demo:other':'evening'}};
 const after=Lib.changeSession(before,set,'five');
 assert.deepEqual(plain(after.labels),{'demo:other':'evening','demo:disc1':'five','demo:disc2':'five'});
 assert.deepEqual(before.labels,{'demo:other':'evening'});
 assert.deepEqual(plain(Lib.changeSession(after,set,'').labels),{'demo:other':'evening'});
});
test('unknown and mixed discs stay distinct and cannot masquerade as a matching session',()=>{
 const a=entry('demo:a'),b=entry('demo:b');a.sessionWindow='five';
 const set={...a,discMembers:[a,b]};
 assert.equal(Lib.sessionValue(set),'mixed');
 for(const value of ['five','twenty','evening','unknown']) assert.equal(Lib.sessionMatches(set,value),false);
 assert.equal(Lib.sessionMatches(set,''),true);
});
test('session shelf intersects existing search, status, device and favourites',()=>{
 const a=entry('demo:a'),b=entry('demo:b');a.sessionWindow='five';b.sessionWindow='twenty';
 const f={...plain(Lib.emptyFilters()),session:'five',system:'snes',status:'playing',device:'here',kept:true};
 assert.deepEqual(plain(Lib.filterEntries([a,b],f,['demo:a'],'demo:a').map(e=>e.id)),['demo:a']);
 assert.deepEqual(plain(Lib.filterEntries([a,b],f,[],'').map(e=>e.id)),[]);
 assert.equal(Lib.filtersActive(f),true);assert.equal(Lib.filtersActive(Lib.emptyFilters()),false);
});
test('future or corrupt stores and unsupported identities fail closed without mutating input',()=>{
 for(const raw of [{version:2,labels:{}},{version:1,labels:[]},{version:1,labels:{'demo:a':'instant'}},JSON.parse('{"version":1,"labels":{"__proto__":"five"}}')]) {
  const before=JSON.stringify(raw);assert.equal(Lib.sessionStore(raw),null);assert.equal(Lib.changeSession(raw,entry('demo:a'),'five'),null);assert.equal(JSON.stringify(raw),before);
 }
 for(const e of [entry('untagged:hello|/private/path'),entry(''),entry('demo:app','androidapps'),entry('demo:emu','emulators'),{discMembers:[entry('demo:a'),entry('untagged:other')]}]) assert.equal(Lib.changeSession(Lib.sessionStore(null),e,'five'),null);
});
test('versioned JSON roundtrip retains valid labels and clearing does not invent unknown records',()=>{
 const a=entry('demo:a');const first=Lib.changeSession(Lib.sessionStore(null),a,'evening');
 const reopened=Lib.sessionStore(JSON.parse(JSON.stringify(first)));assert.deepEqual(plain(first),plain(reopened));
 const cleared=Lib.changeSession(reopened,a,'');assert.deepEqual(plain(cleared),{version:1,labels:{}});
});

test('unreadable preferences never appear as a deliberately unlabelled game',()=>{
 const a=entry('demo:a');Lib.applySessions([a],null);
 assert.equal(Lib.sessionValue(a),'unavailable');assert.equal(Lib.sessionMatches(a,'unknown'),false);
 assert.equal(Lib.sessionMatches(entry('demo:app','androidapps'),'unknown'),false);
});
