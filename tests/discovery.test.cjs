const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const load=file=>fs.readFileSync(path.join(__dirname,'../theme',file),'utf8').replace(/^\.pragma library\s*/,'').replace(/^\.import .*$/mg,'');
const Rotation=vm.createContext({});vm.runInContext(load('Rotation.js'),Rotation);
const D=vm.createContext({Rotation});vm.runInContext(load('Discovery.js'),D);
const Lib=vm.createContext({});vm.runInContext(load('library.js'),Lib);
const plain=x=>JSON.parse(JSON.stringify(x));
const game=(id,title=id,extra={})=>({id,title,systemId:'snes',launchable:true,...extra});
const ids=(s,shelf)=>D.find(s,shelf).editions.map(e=>e.id);
const names=s=>s.shelves.map(x=>x.name);
function made(state,name,kind){const r=D.create(state,name,kind);assert.ok(r,'create '+name);return r;}

test('owner creates, names, re-kinds and reorders shelves; a serialized reopen keeps every choice',()=>{
 let a=made(D.store(undefined),'Dreamlike'),b=made(a.state,'  Ten-minute   adrenaline ','purpose');
 assert.equal(a.id,'shelf:1');assert.equal(b.id,'shelf:2');
 let s=D.rename(b.state,'shelf:1','Beautiful old menus');s=D.cycleKind(s,'shelf:1',1);s=D.moveShelf(s,'shelf:2',-1);
 const reopened=D.store(JSON.parse(JSON.stringify(s)));
 assert.deepEqual(plain(names(reopened)),['Ten-minute adrenaline','Beautiful old menus']);
 assert.deepEqual(plain(reopened.shelves.map(x=>x.kind)),['purpose','purpose']);
 assert.equal(reopened.serial,2);
 assert.equal(D.cycleKind(reopened,'shelf:2',-1).shelves[0].kind,'feeling');
});

test('membership is edition-scoped and ordered by the owner, never alphabetised or inferred',()=>{
 let s=made(D.store(undefined),'Funny').state;
 s=D.add(s,'shelf:1',game('demo:z','Zed'));s=D.add(s,'shelf:1',game('demo:a','Able'));
 const catalogue=[game('demo:a','Able'),game('demo:z','Zed'),game('demo:other','Other',{recScore:9,recReason:'Trending'})];
 const before=JSON.stringify(catalogue);
 const c=D.collections(s,catalogue)[0];
 assert.equal(c.origin,'shelf');assert.equal(c.id,'local:shelf:1');
 assert.deepEqual(plain(c.entries).map(e=>e.id),['demo:z','demo:a']);
 assert.match(c.reason,/Not a suggestion/);assert.equal(JSON.stringify(catalogue),before);
 s=D.moveEdition(s,'shelf:1','demo:a',-1);assert.deepEqual(plain(ids(s,'shelf:1')),['demo:a','demo:z']);
 assert.equal(D.moveEdition(s,'shelf:1','demo:a',-1),null);assert.equal(D.moveEdition(s,'shelf:1','demo:z',1),null);
 assert.equal(D.add(s,'shelf:1',game('demo:a')),null,'duplicate add');
 s=D.remove(s,'shelf:1','demo:a');assert.deepEqual(plain(ids(s,'shelf:1')),['demo:z']);
});

test('same-title regional editions stay distinct; absent and duplicated identities never become launch targets',()=>{
 const us=game('demo:us','Same game'),eu=game('demo:eu','Same game',{launchable:false,missing:true});
 let s=made(D.store(undefined),'Tight mechanics').state;s=D.add(D.add(s,'shelf:1',us),'shelf:1',eu);
 let c=D.collections(s,[us,eu])[0];assert.equal(c.entries.length,2);assert.equal(c.entries[1].launchable,false);
 assert.deepEqual(plain(ids(D.remove(s,'shelf:1','demo:us'),'shelf:1')),['demo:eu']);
 c=D.collections(s,[eu])[0];assert.equal(c.absent,1);assert.deepEqual(plain(c.entries).map(e=>e.id),['demo:eu']);
 const rows=D.editorRows(s,'shelf:1',[eu]);
 assert.equal(rows[3].label,'Same game');assert.match(rows[3].value,/Not in catalogue/);assert.equal(rows[3].entry,null);
 c=D.collections(s,[us,{...us,title:'Imposter route'},eu])[0];assert.equal(c.absent,1);
});

test('names are bounded, plain and unique ignoring case and spacing',()=>{
 const s=made(D.store(undefined),'Dreamlike').state;
 assert.match(D.nameProblem(s,'dreamLIKE',''),/already have/);
 assert.match(D.nameProblem(s,'  ',''),/few plain words/);
 assert.match(D.nameProblem(s,'x'.repeat(41),''),/40 characters/);
 assert.match(D.nameProblem(s,'<b>',''),/few plain words/);
 assert.match(D.nameProblem(null,'Calm',''),/could not be read/);
 assert.equal(D.nameProblem(s,'Dreamlike','shelf:1'),'','own name is not a duplicate of itself');
 assert.equal(D.create(s,'DREAMLIKE'),null);
 assert.equal(D.rename(s,'shelf:1','Dreamlike'),null,'no-op rename writes nothing');
 assert.equal(D.create(s,'Calm','unknown-kind').state.shelves[1].kind,'feeling');
});

test('operations return copies and leave the previous state untouched',()=>{
 const s=D.add(made(D.store(undefined),'Calm').state,'shelf:1',game('demo:a')),before=JSON.stringify(s);
 for(const f of [()=>D.rename(s,'shelf:1','Quiet'),()=>D.cycleKind(s,'shelf:1',1),()=>D.add(s,'shelf:1',game('demo:b')),
  ()=>D.remove(s,'shelf:1','demo:a'),()=>D.create(s,'Loud'),()=>D.moveEdition(D.add(s,'shelf:1',game('demo:b')),'shelf:1','demo:b',-1)])assert.ok(f());
 assert.equal(JSON.stringify(s),before);
});

test('deleting requires an empty shelf; ids are never reused after deletion',()=>{
 let s=D.add(made(D.store(undefined),'Calm').state,'shelf:1',game('demo:a'));
 assert.equal(D.removeShelf(s,'shelf:1'),null);
 s=D.removeShelf(D.remove(s,'shelf:1','demo:a'),'shelf:1');assert.equal(s.shelves.length,0);
 assert.equal(made(s,'Calm').id,'shelf:2');
 assert.equal(D.editorRows(s,'shelf:1',[])[0].dim,true);
});

test('shelf and membership limits refuse instead of displacing anything',()=>{
 let s=D.store(undefined);for(let i=0;i<D.SHELF_LIMIT;i++)s=made(s,'Shelf '+i).state;
 assert.equal(D.create(s,'One more'),null);
 for(let i=0;i<D.EDITION_LIMIT;i++)s=D.add(s,'shelf:1',game('demo:'+i));
 assert.equal(D.add(s,'shelf:1',game('demo:extra')),null);assert.equal(D.find(s,'shelf:1').editions.length,D.EDITION_LIMIT);
 assert.equal(D.create({version:1,serial:D.SERIAL_MAX,shelves:[]},'Late'),null);
});

test('corrupt, future or ambiguous preferences stay unreadable and are not silently emptied',()=>{
 const good={version:1,serial:1,shelves:[{id:'shelf:1',name:'Calm',kind:'feeling',editions:[]}]};
 assert.ok(D.store(good));
 const bad=[null,false,[],{},{version:2,serial:0,shelves:[]},{version:1,shelves:[]},{version:1,serial:-1,shelves:[]},{version:1,serial:0.5,shelves:[]},
  {version:1,serial:0,shelves:[],extra:1},{...good,serial:0},
  {version:1,serial:2,shelves:[good.shelves[0],{...good.shelves[0],id:'shelf:2',name:'calm'}]},
  {version:1,serial:2,shelves:[good.shelves[0],{...good.shelves[0]}]},
  {version:1,serial:1,shelves:[{...good.shelves[0],kind:'mood'}]},
  {version:1,serial:1,shelves:[{...good.shelves[0],name:' Calm'}]},
  {version:1,serial:1,shelves:[{...good.shelves[0],name:''}]},
  {version:1,serial:1,shelves:[{...good.shelves[0],note:'x'}]},
  {version:1,serial:1,shelves:[{...good.shelves[0],editions:[{id:'demo:a',title:'A'},{id:'demo:a',title:'B'}]}]},
  {version:1,serial:1,shelves:[{...good.shelves[0],editions:[{id:'untagged:x',title:'A'}]}]},
  {version:1,serial:1,shelves:[{...good.shelves[0],id:'shelf:01'}]},
  {version:1,serial:9,shelves:Array.from({length:9},(_,i)=>({id:'shelf:'+(i+1),name:'S'+i,kind:'feeling',editions:[]}))}];
 for(const raw of bad){const before=JSON.stringify(raw);assert.equal(D.store(raw),null,before);assert.equal(JSON.stringify(raw),before);}
 for(const f of [()=>D.create(null,'A'),()=>D.add(null,'shelf:1',game('demo:a')),()=>D.rename(null,'shelf:1','A'),()=>D.moveShelf(null,'shelf:1',1),()=>D.removeShelf(null,'shelf:1')])assert.equal(f(),null);
 const c=D.collections(null,[]);assert.equal(c.length,1);assert.equal(c[0].unreadable,true);assert.match(c[0].reason,/kept unchanged/);
 assert.equal(D.editorRows(null,'shelf:1',[])[0].dim,true);
});

test('apps, disc groups, untagged ids and unsafe titles cannot join a shelf',()=>{
 const s=made(D.store(undefined),'Calm').state;
 for(const entry of [game('demo:a','A',{systemId:'androidapps'}),game('demo:a','A',{systemId:'emulators'}),game('demo:a','A',{discMembers:[]}),
  game('untagged:x'),game('constructor'),game('demo:a','<i>'),game('demo:a','x'.repeat(241))])assert.equal(D.add(s,'shelf:1',entry),null);
});

test('conflict check compares the stored value with what the editor opened',()=>{
 const s=made(D.store(undefined),'Calm').state;
 assert.ok(D.same(D.store(JSON.parse(JSON.stringify(s))),s));
 assert.equal(D.same(made(s,'Other').state,s),false);
 assert.equal(D.same(null,undefined),true);
});

test('editor rows expose name, kind, order, members and a guarded delete',()=>{
 let s=made(made(D.store(undefined),'Calm').state,'Loud','purpose').state;s=D.add(s,'shelf:2',game('demo:a','Able'));
 const rows=D.editorRows(s,'shelf:2',[game('demo:a','Able')]);
 assert.deepEqual(plain(rows.map(r=>r.act)),['rename','kind','order','member','delete']);
 assert.equal(rows[1].value,'Purpose');assert.equal(rows[2].value,'2 of 2');assert.equal(rows[3].value,'1 / 1');
 assert.equal(rows[4].dim,true);assert.equal(D.editorRows(s,'shelf:1',[]).at(-1).dim,false);
});

test('Collections labels authored shelves apart from suggestions and lists them in Details',()=>{
 assert.equal(Lib.originLabel({origin:'shelf'}),'Yours');
 assert.equal(Lib.originLabel({origin:'suggested'}),'Suggested');
 assert.equal(Lib.originLabel({origin:'kept'}),'Kept');
 const s=D.add(made(D.store(undefined),'Dreamlike').state,'shelf:1',game('demo:a'));
 const threads=D.collections(s,[game('demo:a')]).concat([{origin:'recommendations',name:'Suggested games',entries:[game('demo:a')]}]);
 assert.deepEqual(plain(Lib.threadNamesFor(game('demo:a'),threads)),['Dreamlike']);
});
