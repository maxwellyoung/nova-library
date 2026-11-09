const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const PC=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../theme/PcGames.js'),'utf8').replace(/^\.pragma library\s*/,''),PC);
const plain=x=>JSON.parse(JSON.stringify(x));
const entry={id:'steam:123',systemId:'pc',launchable:false,game:{missing:true}};
test('only exact positive signed32-bit Steam identities enter a runtime',()=>{
 assert.equal(PC.steamId(entry),'123');assert.equal(PC.steamId({...entry,id:'steam:2147483647'}),'2147483647');
 for(const id of ['steam:0','steam:01','steam:-1','steam:123\n','steam:2147483648','STEAM:1','steam:1?exec=other','https://example.test'])assert.equal(PC.steamId({...entry,id}),'');
 assert.equal(PC.steamId({...entry,systemId:'androidapps'}),'');assert.equal(PC.steamId({...entry,discMembers:[]}), '');
});
test('remembered runtime is edition-specific and never retargets or mutates its input',()=>{
 const a=PC.freshChoices(),b=PC.editChoice(a,entry.id,{runtime:'droiddeck',version:'0.7.0'});
 assert.equal(PC.choice(entry,a),null);assert.deepEqual(plain(PC.choice(entry,b)),{runtime:'droiddeck',version:'0.7.0'});
 assert.equal(PC.choice({...entry,id:'steam:124'},b),null);assert.equal(PC.chosenName(entry,b),'DroidDeck');
 assert.equal(PC.choice(entry,PC.editChoice(b,entry.id,null)),null);assert.notEqual(PC.choice(entry,b),null);
});
test('invalid saved data remains unreadable and cannot be silently overwritten',()=>{
 for(const raw of [null,[],{},'broken',{version:2,choices:{}},{version:1,choices:{},secret:'drop'},{version:1,choices:{'steam:123':{runtime:'other',version:'1'}}},{version:1,choices:{'steam:123':{runtime:'droiddeck',version:'0.7.0',command:'never'}}}]){
  const s=PC.readChoices(raw);assert.equal(s.readable,false);assert.equal(PC.editChoice(s,entry.id,{runtime:'droiddeck',version:'0.7.0'}),null);
 }
 assert.equal(PC.readChoices(undefined).readable,true);
});
test('preference import and edits are bounded and accept no commands or paths',()=>{
 for(const version of ['', '/private/path','1\n2','x'.repeat(81)])assert.equal(PC.editChoice(PC.freshChoices(),entry.id,{runtime:'gamenative',version}),null);
 const choices={};for(let i=1;i<=2000;i++)choices['steam:'+i]={runtime:'droiddeck',version:'0.7.0'};
 const s=PC.readChoices({version:1,choices});assert.equal(s.readable,true);
 assert.equal(PC.editChoice(s,'steam:2001',{runtime:'droiddeck',version:'0.7.0'}),null);
 choices['steam:2001']={runtime:'droiddeck',version:'0.7.0'};assert.equal(PC.readChoices({version:1,choices}).readable,false);
});
test('backend app availability never promotes a game file or installation',()=>{
 const rows=PC.rows([{id:'droiddeck',available:true,supported:true,version:'0.7.0'}],entry,PC.freshChoices());
 assert.equal(rows[0].available,true);assert.match(rows[0].reason,/install or configure/);assert.equal(rows[1].available,false);
 assert.equal(entry.launchable,false);assert.equal(entry.game.missing,true);assert.equal(PC.actionLabel(entry,PC.freshChoices()),'PC options');
});
test('old versions, duplicate identities and absent bridge states remain explicit',()=>{
 const rows=PC.rows([{id:'droiddeck',available:true,supported:false,version:'0.6.9'}],entry,PC.freshChoices());assert.equal(rows[0].available,false);assert.match(rows[0].value,/Needs adapter check/);
 const duplicate=PC.rows([{id:'droiddeck',available:true,supported:true},{id:'droiddeck',available:true,supported:true}],entry,PC.freshChoices());assert.equal(duplicate[0].available,false);
 assert.equal(PC.rows(null,entry,PC.freshChoices())[0].available,false);
});
test('changed backend version preserves choice and requires explicit review',()=>{
 const s=PC.editChoice(PC.freshChoices(),entry.id,{runtime:'gamenative',version:'1.3.0'});
 const rows=PC.rows([{id:'gamenative',available:true,supported:true,version:'1.4.0'}],entry,s);
 assert.match(rows[1].reason,/version changed/);assert.equal(PC.choice(entry,s).version,'1.3.0');assert.equal(rows.at(-1).forget,true);
});
test('existing shortcut is offered explicitly and not inferred from a backend',()=>{
 const ready={...entry,launchable:true,game:{missing:false},route:'Existing route'};
 assert.equal(PC.rows([],entry,PC.freshChoices()).length,2);
 const row=PC.rows([],ready,PC.freshChoices()).at(-1);assert.equal(row.legacy,true);assert.equal(row.value,'Existing route');
});

test('native QVariant sequence-shaped states are supported without assuming a JS array',()=>{
 const row=PC.rows({0:{id:'droiddeck',available:true,supported:true,version:'0.7.0'},length:1},entry,PC.freshChoices())[0];assert.equal(row.available,true);
});
