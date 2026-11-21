const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const C=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../theme/Compatibility.js'),'utf8').replace(/^\.pragma library\s*/,''),C);
const now=Date.parse('2026-11-11T12:00:00Z'),clone=x=>JSON.parse(JSON.stringify(x));
const recipe={id:'fixture.measured.v1',device:'Synthetic handheld',runtime:'Fixture runtime',version:'1.0',core:'Fixture core',driver:'Fixture driver',display:'Fit 4:3',input:'Fixture pad',settings:'Synthetic 2x render setup'};
const sample=(stage='gameplay',context='gameplay')=>({stage,result:'pass',observedAt:'2026-11-10T10:00:00Z',method:'observed',source:'Synthetic measurement fixture',note:'Limited to the named test scene',durationSeconds:120,
 performance:{context,scene:'Courtyard fight',measurement:'Synthetic frame-time log, whole scene',metrics:{averageFps:59.8,p95FrameMs:18.2,p99FrameMs:24.5}}});
const record=checks=>({schemaVersion:1,editionId:'demo:measured',recipe:clone(recipe),checks});
const entry=checks=>({id:'demo:measured',compatibilityRecipeId:recipe.id,compatibilityReceipts:JSON.stringify([record(checks)]),launchable:false});
test('scene metrics survive validation and allowlisted portable export with exact setup and duration',()=>{
 const raw=record([sample()]),parsed=C.record(raw,now);assert.ok(parsed);
 assert.deepEqual(clone(parsed.checks[0].performance),raw.checks[0].performance);
 assert.deepEqual(clone(C.exportRecord(parsed)),raw);
 assert.equal(C.record(C.exportRecord(parsed),now).checks[0].performance.scene,'Courtyard fight');
});
test('menu samples are explicitly menu-only and never establish sustained gameplay',()=>{
 const c=sample('menus','menus');c.performance.scene='Options screen';const e=entry([c]);
 const rows=clone(C.rows(e,now));assert.equal(C.view(e,now).checks.sustained,undefined);
 assert.equal(rows.find(r=>r.label==='Gameplay').value,'Not checked');
 const measurement=rows.find(r=>r.label==='Menu measurement');assert.ok(measurement);assert.match(measurement.detail,/Options screen/);assert.match(measurement.detail,/menu sample/i);
 assert.ok(!C.summary(e,now).includes('59.8'));
 assert.equal(C.record(record([{...c,stage:'sustained'}]),now),null);
});
test('measurement needs an explicit scene, instrument, bounded metrics and sample duration',()=>{
 for(const performance of [{}, {...sample().performance,scene:''}, {...sample().performance,measurement:''},
  {...sample().performance,context:'unknown'}, {...sample().performance,metrics:{}},
  {...sample().performance,metrics:{averageFps:-1}}, {...sample().performance,metrics:{averageFps:Infinity}},
  {...sample().performance,metrics:{averageFps:1001}}, {...sample().performance,metrics:{p95FrameMs:0}},
  {...sample().performance,metrics:{p95FrameMs:20,p99FrameMs:10}},
  {...sample().performance,metrics:{p99FrameMs:60001}}, {...sample().performance,metrics:{score:100}},
  {...sample().performance,command:'never execute'}, {...sample().performance,scene:'<b>scene</b>'}]) {
  assert.equal(C.record(record([{...sample(),performance}]),now),null,JSON.stringify(performance));
 }
 const c=sample();delete c.durationSeconds;assert.equal(C.record(record([c]),now),null);
 assert.equal(C.record(record([{...sample(),stage:'audio'}]),now),null);
});
test('zero measured FPS differs from unknown frame pacing and legacy checks invent no metrics',()=>{
 const c=sample();c.performance.metrics={averageFps:0};const rows=clone(C.rows(entry([c]),now));
 const measurement=rows.find(r=>r.label==='Gameplay measurement');assert.ok(measurement);
 assert.match(measurement.detail,/Average FPS · 0/);assert.match(measurement.detail,/Frame pacing · Not measured/);
 delete c.performance;assert.ok(!C.rows(entry([c]),now).some(r=>/measurement$/.test(r.label)));
});
test('current samples require exact edition and nonconflicting recipe without granting routes or other checks',()=>{
 const c=sample(),e=entry([c]),before=JSON.stringify(e);C.rows(e,now);assert.equal(JSON.stringify(e),before);assert.equal(e.launchable,false);
 for(const changed of [{...e,id:'demo:other'},{...e,compatibilityRecipeId:'changed'},
  {...e,compatibilityReceipts:JSON.stringify([record([c]),{...record([c]),recipe:{...recipe,driver:'Changed driver'}}])}]) {
  assert.ok(!C.rows(changed,now).some(r=>/measurement$/.test(r.label)));
 }
 assert.equal(C.view(e,now).checks['physical-controls'],undefined);
});
test('equal-time contradictory samples hide figures regardless of input order and preserve both originals',()=>{
 const a=sample(),b=clone(a);b.performance.metrics.averageFps=42;
 for(const checks of [[a,b],[b,a]]) {
  const raw=record(checks),rows=clone(C.rows(entry(checks),now));
  const measurement=rows.find(r=>r.label==='Gameplay measurement');assert.ok(measurement);
  assert.equal(measurement.value,'Conflicting samples');assert.match(measurement.detail,/figures withheld/i);
  assert.ok(!measurement.detail.includes('59.8'));assert.ok(!measurement.detail.includes('42'));
  assert.deepEqual(clone(C.exportRecord(C.record(raw,now))),raw);
 }
});
test('duration and missing-measurement ties stay ambiguous while equal-time failure still wins',()=>{
 const a=sample(),b=clone(a);b.durationSeconds=300;
 const absent=clone(a);delete absent.performance;
 for(const other of [b,absent]) for(const checks of [[a,other],[other,a]]) {
  const row=C.rows(entry(checks),now).find(r=>r.label==='Gameplay measurement');
  assert.equal(row.value,'Conflicting samples');assert.match(row.detail,/figures withheld/);
 }
 const failed=clone(a);failed.result='fail';failed.performance.metrics.averageFps=0;
 for(const checks of [[a,failed],[failed,a]]) {
  const row=C.rows(entry(checks),now).find(r=>r.label==='Gameplay measurement');
  assert.match(row.detail,/failed observation/);assert.match(row.detail,/Average FPS · 0/);
 }
});
test('a newer stage result replaces older numeric evidence; failure and cutscene scope remain explicit',()=>{
 const old=sample(),newer={...sample(),observedAt:'2026-11-10T11:00:00Z'};delete newer.performance;
 assert.ok(!C.rows(entry([old,newer]),now).some(r=>r.label==='Gameplay measurement'));
 const failed=sample();failed.result='fail';failed.performance.context='cutscene';failed.performance.scene='Opening cinematic';
 const rows=clone(C.rows(entry([failed]),now)),m=rows.find(r=>r.label==='Gameplay measurement');assert.ok(m);
 assert.match(m.detail,/Cutscene sample/);assert.match(m.detail,/failed observation/);
 assert.equal(C.view(entry([failed]),now).checks.sustained,undefined);
});
test('portable CLI preserves scene measurements, refuses bad samples and never overwrites exports',()=>{
 const os=require('node:os'),cp=require('node:child_process'),dir=fs.mkdtempSync(path.join(os.tmpdir(),'nova-measured-'));
 const input=path.join(dir,'input.json'),out=path.join(dir,'portable.json'),tool=path.join(__dirname,'../tools/compatibility_receipts.cjs');
 const run=(...args)=>cp.spawnSync(process.execPath,[tool,...args],{encoding:'utf8'});
 try{
  const raw=[record([sample()])];fs.writeFileSync(input,JSON.stringify(raw));
  assert.equal(run('export',input,out).status,0);assert.deepEqual(JSON.parse(fs.readFileSync(out,'utf8')),raw);
  assert.equal(fs.statSync(out).mode&0o777,0o600);const before=fs.readFileSync(out);
  assert.equal(run('export',input,out).status,1);assert.deepEqual(fs.readFileSync(out),before);
  raw[0].checks[0].performance.metrics.averageFps=-1;fs.writeFileSync(input,JSON.stringify(raw));
  assert.equal(run('export',input,path.join(dir,'bad.json')).status,1);assert.equal(fs.existsSync(path.join(dir,'bad.json')),false);
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
