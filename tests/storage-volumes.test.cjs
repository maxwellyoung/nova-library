const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const L=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../theme/library.js'),'utf8').replace(/^\.pragma library\s*/,''),L);
const plain=x=>JSON.parse(JSON.stringify(x));
const snapshot=(id='internal-data',more={})=>({id,total:1000,used:800,free:100,source:'Synthetic allocated scan',observedAt:'2026-11-10T10:00:00Z',...more});
const breakdown={basis:'allocated-bytes',disjoint:true,categories:{'game-data':300,'app-data':200,cache:0,'save-data':50}};
const entries=(...v)=>v.map(c=>({capacity:c}));
test('internal and SD capacity remain independent and legacy internal data stays readable',()=>{
 const a=snapshot(),b=snapshot('sd-card',{total:2000,used:500,free:1500});
 const parsed=L.capacityVolumesData(JSON.stringify([a,b]));assert.equal(parsed.length,2);
 assert.equal(L.storageCapacity([{capacities:parsed}]).total,1000);
 assert.equal(L.storageCapacity([{capacities:parsed}],'sd-card').total,2000);
 assert.equal(L.storageCapacity(entries(a)).free,100);assert.equal(L.storageCapacity(entries(a),'sd-card'),null);
});
test('missing SD observations never claim an absent or empty card',()=>{
 const state=L.capacityEvidence(entries(snapshot()),'sd-card');assert.equal(state.status,'unknown');assert.equal(state.snapshot,null);
 assert.ok(L.capacityRows(null).every(r=>r.value==='Not measured'));
});
test('measured zero categories differ from unmeasured categories and the used remainder stays unclassified',()=>{
 const cap=L.capacityValue(snapshot('internal-data',{breakdown}));
 const rows=L.capacityRows(cap);
 assert.equal(rows.find(r=>r.category==='cache').value,'0 B');
 assert.equal(rows.find(r=>r.category==='unclassified').bytes,250);
 const partial=L.capacityValue(snapshot('internal-data',{breakdown:{...breakdown,categories:{cache:0}}}));
 assert.equal(L.capacityRows(partial).find(r=>r.category==='game-data').value,'Not measured');
 assert.equal(L.capacityRows(partial).find(r=>r.category==='unclassified').bytes,800);
});
test('the chart partitions exact capacity with no minimum-width inflation',()=>{
 const cap=L.capacityValue(snapshot('internal-data',{breakdown})),parts=plain(L.capacitySegments(cap));
 assert.equal(parts.reduce((sum,p)=>sum+p.bytes,0),1000);
 let offset=0;for(const p of parts){assert.equal(p.offset,offset);offset+=p.bytes;assert.equal(p.fraction,p.bytes/1000);}
 assert.equal(parts.find(p=>p.id==='cache').fraction,0);
 assert.equal(parts.find(p=>p.id==='unclassified').bytes,250);
 assert.equal(parts.find(p=>p.id==='unavailable').bytes,100);
});
test('unsafe, overlapping, unknown and logical-byte breakdowns cannot classify used space',()=>{
 for(const bad of [{...breakdown,disjoint:false},{...breakdown,basis:'logical-file-bytes'},{...breakdown,categories:{'game-data':801}},
 {...breakdown,categories:{cache:-1}},{...breakdown,categories:{cache:true}},{...breakdown,categories:{other:1}},
 {...breakdown,categories:[]},null]){
  const cap=L.capacityValue(snapshot('internal-data',{breakdown:bad}));assert.ok(cap);assert.equal(cap.breakdownState,'invalid');
  assert.equal(L.capacityRows(cap).find(r=>r.category==='unclassified').bytes,800);
 }
});
test('newest observations and equal-instant conflicts are scoped to one volume',()=>{
 const old=snapshot(),newer=snapshot('internal-data',{observedAt:'2026-11-10T11:00:00Z',free:90});
 assert.equal(L.capacityEvidence(entries(old,newer),'internal-data').snapshot.free,90);
 const conflict=snapshot('internal-data',{free:99});
 assert.equal(L.capacityEvidence(entries(old,conflict),'internal-data').status,'conflict');
 const sd=snapshot('sd-card');assert.equal(L.capacityEvidence(entries(old,conflict,sd),'sd-card').status,'known');
});
test('breakdown disagreements retain agreed capacity but not arbitrary category values',()=>{
 const a=snapshot('internal-data',{breakdown}),b=snapshot('internal-data',{breakdown:{...breakdown,categories:{cache:20}}});
 const cap=L.storageCapacity(entries(a,b));assert.ok(cap);assert.equal(cap.breakdownState,'conflict');
 assert.equal(L.capacityRows(cap).find(r=>r.category==='unclassified').bytes,800);
 const compatible=L.storageCapacity(entries(snapshot(),a));assert.equal(compatible.breakdownState,'measured');
});
test('malformed multi-volume inputs and untrusted source labels fail closed without mutating inputs',()=>{
 for(const raw of ['{',{},JSON.stringify([snapshot(),snapshot()]),JSON.stringify([snapshot('other')]),'x'.repeat(16385)])assert.equal(L.capacityVolumesData(raw).length,0);
 for(const source of ['',{},'<script>','bad\nvalue','x'.repeat(201)])assert.equal(L.capacityValue(snapshot('internal-data',{source})),null);
 for(const v of [{total:0},{used:-1},{free:true},{free:201},{total:Number.MAX_SAFE_INTEGER+1},{observedAt:'2999-01-01T00:00:00Z'}])assert.equal(L.capacityValue(snapshot('internal-data',v)),null);
 const raw=snapshot('internal-data',{breakdown}),before=JSON.stringify(raw);L.capacityValue(raw);assert.equal(JSON.stringify(raw),before);
});

test('equivalent timezone instants conflict and older categories are not borrowed by a newer snapshot',()=>{
 const a=snapshot('internal-data',{breakdown}),b=snapshot('internal-data',{observedAt:'2026-11-10T11:00:00+01:00',free:99});
 assert.equal(L.capacityEvidence(entries(a,b),'internal-data').status,'conflict');
 const newer=snapshot('internal-data',{observedAt:'2026-11-10T11:00:00Z'});
 assert.equal(L.storageCapacity(entries(a,newer)).breakdownState,'unmeasured');
 assert.equal(L.capacityRows(L.storageCapacity(entries(a,newer))).find(r=>r.category==='game-data').value,'Not measured');
});
