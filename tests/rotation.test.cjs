const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const R=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../theme/Rotation.js'),'utf8').replace(/^\.pragma library\s*/,''),R);
const plain=x=>JSON.parse(JSON.stringify(x));
const game=(id,title=id)=>({id,title,systemId:'snes',launchable:true});
const start=()=>R.store(undefined);
test('local order is authored, independent and survives a serialized reopen',()=>{
 let s=R.add(start(),game('demo:z'));s=R.add(s,game('demo:a'));
 const reopened=R.store(JSON.parse(JSON.stringify(s)));
 assert.deepEqual(plain(reopened.editions).map(e=>e.id),['demo:z','demo:a']);
 const source=[game('demo:a'),game('demo:z')], before=JSON.stringify(source);
 const c=R.collection(reopened,source);assert.equal(c.origin,'rotation');
 assert.deepEqual(plain(c.entries).map(e=>e.id),['demo:z','demo:a']);
 assert.equal(JSON.stringify(source),before);assert.match(c.reason,/Chosen by you/);
});
test('add, move and remove return copies without changing the preceding state',()=>{
 let s=R.add(R.add(start(),game('demo:a')),game('demo:b'));const before=JSON.stringify(s);
 const moved=R.move(s,'demo:b',-1);assert.equal(JSON.stringify(s),before);
 assert.deepEqual(plain(moved.editions).map(e=>e.id),['demo:b','demo:a']);
 assert.deepEqual(plain(R.remove(moved,'demo:b').editions).map(e=>e.id),['demo:a']);
 for(const [id,d] of [['demo:a',-1],['demo:b',1],['absent',-1],['demo:a',0],['demo:a',2]])assert.equal(R.move(s,id,d),null);
 assert.equal(R.add(s,game('demo:a')),null);assert.equal(R.remove(s,'absent'),null);
});
test('missing catalogue editions retain cached names and their exact place',()=>{
 const s=R.add(R.add(start(),game('demo:a','Amber')),game('demo:b','Blue'));
 const c=R.collection(s,[game('demo:b','Blue revised')]);
 assert.equal(c.absent,1);assert.deepEqual(plain(c.entries).map(e=>e.id),['demo:b']);
 const rows=R.rows(s,[game('demo:b','Blue revised')]);
 assert.equal(rows[0].label,'Amber');assert.match(rows[0].value,/Not in catalogue/);
 assert.equal(rows[1].label,'Blue revised');assert.equal(s.editions[0].id,'demo:a');
 const returned=R.collection(s,[game('demo:b'),game('demo:a')]);assert.deepEqual(plain(returned.entries).map(e=>e.id),['demo:a','demo:b']);
 assert.equal(R.remove(s,'demo:a').editions[0].id,'demo:b');
});
test('duplicate catalogue identities cannot pick an arbitrary launch target',()=>{
 const s=R.add(start(),game('demo:a'));
 const c=R.collection(s,[game('demo:a','A'),game('demo:a','Other')]);assert.equal(c.entries.length,0);assert.equal(c.absent,1);
});
test('capacity bounds the rotation while wider catalogue and save metadata remain unchanged',()=>{
 let s=start();for(let i=0;i<R.LIMIT;i++)s=R.add(s,game('demo:'+i));
 assert.equal(s.editions.length,R.LIMIT);assert.equal(R.add(s,game('demo:extra')),null);
 const g={...game('demo:new'),checkpoint:'untouched',status:'paused',lastPlayed:5};const before=JSON.stringify(g);
 assert.ok(R.add(R.remove(s,'demo:0'),g));assert.equal(JSON.stringify(g),before);
});
test('corrupt/future/duplicate preferences stay unreadable instead of becoming empty',()=>{
 for(const raw of [null,false,{},[],{version:2,editions:[]},{version:1,editions:[],extra:1},
 {version:1,editions:[{id:'demo:a',title:'A',extra:1}]},
 {version:1,editions:[{id:'demo:a',title:'A'},{id:'demo:a',title:'Again'}]},
 {version:1,editions:Array(R.LIMIT+1).fill({id:'demo:a',title:'A'})}]){
  const before=JSON.stringify(raw);assert.equal(R.store(raw),null);assert.equal(JSON.stringify(raw),before);
 }
 assert.equal(R.add(null,game('demo:a')),null);assert.equal(R.remove(null,'demo:a'),null);
 assert.match(R.collection(null,[]).reason,/kept unchanged/);
});
test('apps, disc groups, unstable ids and unsafe labels cannot enter the rotation',()=>{
 for(const entry of [{...game('demo:a'),systemId:'androidapps'},{...game('demo:a'),systemId:'emulators'},
 {...game('demo:a'),discMembers:[]},game('untagged:example'),game('__proto__'),game('demo:a','<img>'),game('demo:a','x'.repeat(241)),game('demo:a',' A'),game('demo:a\n')])assert.equal(R.add(start(),entry),null);
});
test('same-title editions stay separate and no missing file is promoted to launchable',()=>{
 const a=game('demo:us','Same game'),b={...game('demo:eu','Same game'),launchable:false,missing:true};
 const s=R.add(R.add(start(),a),b),c=R.collection(s,[a,b]);assert.equal(c.entries.length,2);
 assert.equal(c.entries[1].launchable,false);assert.equal(c.entries[1].missing,true);
 assert.equal(R.remove(s,a.id).editions[0].id,b.id);
});
