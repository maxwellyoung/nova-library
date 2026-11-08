const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const C=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../theme/Compatibility.js'),'utf8').replace(/^\.pragma library\s*/,''),C);
const now=Date.parse('2026-11-04T12:00:00Z');
const clone=x=>JSON.parse(JSON.stringify(x));
const setup={id:'fixture.v1',device:'Synthetic handheld',runtime:'Fixture emulator',version:'1.0',core:'Fixture core',driver:'Fixture driver',display:'Fit 4:3',input:'Physical pad profile',settings:'Default fixture settings'};
const observation=(stage='gameplay',result='pass',method='injected',observedAt='2026-11-03T10:00:00Z')=>({stage,result,method,observedAt,source:'Synthetic QA',note:'Fixture scene only'});
const receipt=(checks=[observation()])=>({schemaVersion:1,editionId:'demo:fixture',recipe:clone(setup),checks});
const entry=(records=[receipt()],recipeId='fixture.v1')=>({id:'demo:fixture',compatibilityRecipeId:recipeId,compatibilityReceipts:JSON.stringify(records),launchable:false,missing:true});

test('a gameplay observation does not imply boot, controls, audio, saves, return or sustained play',()=>{
 const v=C.view(entry(),now);
 assert.equal(v.checks.gameplay.result,'pass');
 assert.deepEqual(Object.keys(v.checks),['gameplay']);
 const rows=clone(C.rows(entry(),now));
 assert.equal(rows.find(r=>r.label==='Save and restore').value,'Not checked');
 assert.equal(entry().launchable,false);
});
test('edition identity and an explicit recipe link are both required for current evidence',()=>{
 assert.equal(C.view(entry([receipt()],''),now).linked,false);
 assert.equal(C.view(entry([receipt()],'different'),now).historical,1);
 const other=entry();other.id='demo:other';
 assert.equal(C.view(other,now).historical,0);
 assert.equal(C.view(other,now).linked,false);
});
test('a changed driver or other settings under one recipe ID invalidate the combined evidence',()=>{
 for(const field of ['device','runtime','version','core','driver','display','input','settings']) {
  const changed=receipt();changed.recipe[field]+=' changed';
  const v=C.view(entry([receipt(),changed]),now);
  assert.equal(v.ambiguous,true,field);assert.equal(v.linked,false);assert.deepEqual(Object.keys(v.checks),[]);
 }
});
test('latest observation wins independently for each stage, regardless of file order',()=>{
 const failed=receipt([observation('gameplay','fail','observed','2026-11-04T10:00:00Z')]);
 for(const records of [[receipt(),failed],[failed,receipt()]]) {
  assert.equal(C.view(entry(records),now).checks.gameplay.result,'fail');
  assert.match(C.summary(entry(records),now),/Gameplay failed/);
 }
 const tied=receipt([observation('gameplay','fail')]);
 assert.equal(C.view(entry([tied,receipt()]),now).checks.gameplay.result,'fail');
});
test('injected input and logs cannot certify physical controls or audible sound',()=>{
 for(const stage of ['physical-controls','audio']) for(const method of ['injected','observed','log','test']) {
  assert.equal(C.parse([receipt([observation(stage,'pass',method)])],now).rejected,1);
 }
 for(const method of ['physical','owner']) assert.equal(C.parse([receipt([observation('physical-controls','pass',method)])],now).records.length,1);
});
test('sustained checks require a finite positive bounded duration and an explicit scene note',()=>{
 const check=observation('sustained','pass','physical');
 assert.equal(C.parse([receipt([check])],now).rejected,1);
 for(const durationSeconds of [0,-1,1.5,NaN,Infinity,604801,'900']) {
  assert.equal(C.record(receipt([{...check,durationSeconds}]),now),null);
 }
 assert.equal(C.record(receipt([{...check,durationSeconds:900}]),now).checks[0].durationSeconds,900);
 assert.equal(C.record(receipt([{...check,durationSeconds:900,note:''}]),now),null);
});
test('malformed, impossible and future dates cannot become evidence',()=>{
 for(const date of ['', '2026-02-30T10:00:00Z','2026-11-03','2026-11-03T10:00:00+00:00','2026-11-05T00:00:00Z','2026-11-03T25:00:00Z']) {
  assert.equal(C.parse([receipt([observation('gameplay','pass','injected',date)])],now).rejected,1,date);
 }
});
test('limits, untrusted markup and unsupported schema fail closed with an explanation',()=>{
 for(const value of ['{',{},null,Array(33).fill(receipt()),'x'.repeat(262145)]) {
  const p=C.parse(value,now);assert.equal(p.records.length,0);
 }
 const r=receipt();r.recipe.settings='<img src="https://example.test/tracker">';
 assert.equal(C.parse([r],now).rejected,1);
 r.recipe.settings='Normal';r.schemaVersion=2;
 assert.equal(C.parse([r],now).rejected,1);
 const rows=clone(C.rows({...entry(),compatibilityReceipts:'{'},now));
 assert.ok(rows.some(r=>r.label==='Unreadable records'));
});
test('export drops unknown fields without losing recipe or valid observations',()=>{
 const r=receipt();r.privatePayload='must not travel';r.recipe.extra='must not travel';r.checks[0].extra='must not travel';
 const parsed=C.record(r,now), exported=clone(C.exportRecord(parsed));
 assert.deepEqual(exported,receipt());
 assert.ok(!JSON.stringify(exported).includes('must not travel'));
 assert.equal(C.parse([exported],now).records.length,1);
});
test('unreadable sibling records do not overwrite valid checks and are visibly counted',()=>{
 const e=entry([receipt(),{schemaVersion:4}]);
 assert.equal(C.view(e,now).checks.gameplay.result,'pass');
 assert.equal(C.view(e,now).rejected,1);
});

test('portable CLI validates, round-trips, refuses overwrite and rejects conflicting or malformed input',()=>{
 const os=require('node:os'),cp=require('node:child_process');
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'nova-receipt-'));
 const tool=path.join(__dirname,'../tools/compatibility_receipts.cjs');
 const input=path.join(dir,'input.json'),output=path.join(dir,'copy.json');
 const run=(...args)=>cp.spawnSync(process.execPath,[tool,...args],{encoding:'utf8'});
 try {
  fs.writeFileSync(input,JSON.stringify([receipt()]));
  assert.equal(run('validate',input).status,0);
  assert.equal(run('export',input,output).status,0);
  assert.deepEqual(JSON.parse(fs.readFileSync(output,'utf8')),[receipt()]);
  const before=fs.readFileSync(output);
  assert.equal(run('export',input,output).status,1);
  assert.deepEqual(fs.readFileSync(output),before);
  const changed=receipt();changed.recipe.driver='Another driver';
  fs.writeFileSync(input,JSON.stringify([receipt(),changed]));
  assert.equal(run('export',input,path.join(dir,'bad.json')).status,1);
  assert.equal(fs.existsSync(path.join(dir,'bad.json')),false);
  fs.writeFileSync(input,'{');
  assert.equal(run('validate',input).status,1);
 } finally {fs.rmSync(dir,{recursive:true,force:true});}
});

test('native aspect needs its own current display check, independent of gameplay or recipe prose',()=>{
 assert.equal(C.displayEvidence(entry(),now).native43,false);
 const r=receipt([observation('native-4-3')]);
 assert.equal(C.displayEvidence(entry([r]),now).native43,true);
 assert.equal(C.displayEvidence(entry([r],'another.recipe'),now).native43,false);
 const changed=clone(r);changed.recipe.display='Changed display setting';
 assert.equal(C.displayEvidence(entry([r,changed]),now).unknown,true);
 const wrong=entry([r]);wrong.id='demo:other';assert.equal(C.displayEvidence(wrong,now).unknown,true);
});
test('conflicting display passes stay unconfirmed while failed and historical checks never become positives',()=>{
 const r=receipt([observation('native-4-3'),observation('stretch-only')]);
 const v=C.displayEvidence(entry([r]),now);assert.equal(v.conflict,true);assert.equal(v.native43,false);assert.equal(v.stretchOnly,false);
 assert.equal(C.displayEvidence(entry([receipt([observation('native-4-3','fail')])]),now).unknown,true);
 assert.match(C.displaySummary(entry([r]),now),/conflict/);
 const stretch=receipt([observation('stretch-only')]);assert.equal(C.displayEvidence(entry([stretch]),now).stretchOnly,true);
});
test('logs and pure test reports cannot establish a native display render',()=>{
 for(const stage of ['native-4-3','stretch-only']) for(const method of ['log','test'])
  assert.equal(C.parse([receipt([observation(stage,'pass',method)])],now).rejected,1);
 const failed=entry([receipt([observation('native-4-3','fail','log')])]);
 assert.equal(C.view(failed,now).checks['native-4-3'].result,'fail');
 assert.equal(C.displayEvidence(failed,now).unknown,true);
 const future=receipt([observation('native-4-3','pass','observed','2026-11-05T00:00:00Z')]);
 assert.equal(C.displayEvidence(entry([future]),now).unknown,true);
});
