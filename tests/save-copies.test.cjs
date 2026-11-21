const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const C=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../theme/SaveCopies.js'),'utf8').replace(/^\.pragma library\s*/,''),C);
const row={checkpointId:'a'.repeat(32),copyState:'not-rechecked',name:'Before the lift',pinned:true,files:2,capturedAt:'2026-11-10T10:00:00Z',identity:{kind:'native-save',runtime:{name:'Fixture',version:'1.0'}}};
test('only the complete read-only bridge enables the Details action',()=>{
 const b={capabilities:()=>({schemaVersion:1,readOnly:true,capture:false,runtimeRestoreAvailable:false}),openEdition(){},review(){},cancelReview(){},reviewFinished(){}};
 assert.equal(C.bridge(b),b);assert.equal(C.bridge(null),null);assert.equal(C.bridge({...b,reviewFinished:undefined}),null);
 assert.equal(C.bridge({...b,capabilities:()=>({schemaVersion:1,readOnly:true})}),null);
 assert.equal(C.bridge({...b,capabilities:()=>{throw Error('unavailable');}}),null);
});
test('native saves and emulator states stay distinct with no restore promise',()=>{
 const rows=C.rows({ok:true,copies:[row,{...row,checkpointId:'b'.repeat(32),identity:{...row.identity,kind:'emulator-state'}}]},{});
 assert.match(rows[0].value,/Game save · Not rechecked/);assert.match(rows[1].value,/Emulator state/);
 assert.match(C.footer(rows[1],null,false),/depend on their exact runtime/);
 assert.match(C.footer(rows[0],{ok:true},false),/Loading this copy in the game has not been verified/);
 assert.match(C.footer(rows[0],{ok:true},false),/does not load or replace progress/);
});
test('missing copies and absent history never look like checked backups',()=>{
 assert.equal(C.rows({ok:true,copies:[]},{})[0].label,'No save copies here');
 assert.equal(C.rows({ok:false},{})[0].label,'Save copies unavailable');
 const r=C.rows({ok:true,copies:[{...row,copyState:'missing'}]},{});assert.match(r[0].value,/Missing/);assert.equal(r[0].dim,true);
});
test('review result belongs to its original checkpoint and existing results are immutable',()=>{
 const before={other:{ok:true}},next=C.withResult(before,row.checkpointId,{ok:false,error:'checksum_mismatch'});
 assert.equal(before[row.checkpointId],undefined);assert.equal(next.other,before.other);
 assert.match(C.rows({ok:true,copies:[row]},next)[0].value,/Check failed/);
 assert.match(C.footer({copy:row},next[row.checkpointId],false),/stored files were kept/);
 assert.match(C.footer({copy:row},null,true),/Checking the stored archive/);
});
test('checking a displayed copy requires an explicit snapshot-capable reader',()=>{
 const b={reviewSnapshot(){},capabilities:()=>({reviewSnapshotVersion:1})},data={ok:true,indexSha256:'a'.repeat(64)},r={copy:row};
 assert.equal(C.canReview(b,data,r),true);
 for(const bridge of [null,{...b,reviewSnapshot:undefined},{...b,capabilities:()=>({})},{...b,capabilities:()=>{throw Error('offline');}}])assert.equal(C.canReview(bridge,data,r),false);
 for(const indexSha256 of ['', '../path','a'.repeat(63),'A'.repeat(64),'a'.repeat(64)+'\n'])assert.equal(C.canReview(b,{...data,indexSha256},r),false);
 assert.equal(C.canReview(b,{...data,ok:false},r),false);
 assert.equal(C.canReview(b,data,{copy:{...row,copyState:'missing'}}),false);
 assert.match(C.footer(r,null,false,false),/matching Library build/);
 assert.doesNotMatch(C.footer({copy:{...row,copyState:'missing'}},null,false,false),/matching Library build/);
 assert.match(C.error('invalid_snapshot'),/Close and reopen/);
});

test('a failed private-storage check has a bounded factual stage without a repair promise',()=>{
 const data={ok:false,error:'storage_unavailable',storageStage:'copy-index',storageCheck:'shared_permissions',storageRootSha256:'a'.repeat(64)};
 const unavailable=C.rows(data,{})[0];assert.equal(unavailable.value,'Index check stopped');assert.equal(unavailable.dim,true);
 const text=C.footer(unavailable,null,false);assert.match(text,/Copy index owner-only permissions check did not pass/);
 assert.match(text,/No restore was attempted/);assert.doesNotMatch(text,/aaaaaaaa|repair|chmod|permission grant/i);
 assert.match(C.error('storage_unavailable',{...data,storageStage:'copy-directory',storageCheck:'canonical_mismatch'}),/folder path did not match its canonical location/);
 assert.match(C.footer({copy:row},{ok:false,...data},false),/No restore was attempted|Copy index/);
});
test('unknown diagnostic fields never become displayed paths, hypotheses or instructions',()=>{
 const data={ok:false,error:'storage_unavailable',storageStage:'/private/do-not-echo',storageCheck:'<script>repair</script>',storageRootSha256:'b'.repeat(64)};
 const text=C.footer(C.rows(data,{})[0],null,false);assert.match(text,/could not be read/);
 assert.doesNotMatch(text,/private|script|repair|bbbb/i);
 for(const code of ['not_found','symbolic_link','wrong_type','canonical_mismatch','stat_unavailable','shared_permissions']){
  assert.ok(C.storageDetail({...data,storageStage:'copy-directory',storageCheck:code}));
 }
 assert.match(C.error('invalid_index'),/expected format/);assert.match(C.error('bundle_incomplete'),/index is missing/);
});
test('pictures need an explicit capable bridge, bound index and exact attached record',()=>{
 const data={indexSha256:'a'.repeat(64)},r={copy:{...row,picture:{state:'available'}}};
 const b={picture(){},clearPicture(){},capabilities:()=>({pictureVersion:2})};
 assert.equal(C.canPicture(b,data,r),true);
 assert.equal(C.canPicture({...b,picture:undefined},data,r),false);
 assert.equal(C.canPicture({...b,capabilities:()=>({})},data,r),false);
 assert.equal(C.canPicture(b,{indexSha256:'../path'},r),false);
 for(const state of ['missing','unavailable'])assert.equal(C.canPicture(b,data,{copy:{...row,picture:{state}}}),false);
});
test('picture viewer accepts only bounded private-provider tokens, never file/network/data URLs',()=>{
 const r={ok:true,imageUrl:'image://nova-save-copies/'+'a'.repeat(32),imageChecksumMatched:true,runtimeRestoreAvailable:false};
 assert.equal(C.pictureUrl(r),r.imageUrl);
 for(const imageUrl of ['file:///private/save','https://example.test/image.png','data:image/png;base64,YWJjZA==','image://other/'+'a'.repeat(32),r.imageUrl+'\n',r.imageUrl+'?query'])assert.equal(C.pictureUrl({...r,imageUrl}),'');
 assert.equal(C.pictureUrl({...r,imageChecksumMatched:false}),'');assert.equal(C.pictureUrl({...r,runtimeRestoreAvailable:true}),'');
});
