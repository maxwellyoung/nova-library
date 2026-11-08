#!/usr/bin/env node
'use strict';
// Validate or make a portable allowlisted copy. This never runs a recipe or changes a catalogue.
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const C=vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../theme/Compatibility.js'),'utf8').replace(/^\.pragma library\s*/,''),C);
const [command,input,output,...extra]=process.argv.slice(2);
try {
 if(!['validate','export'].includes(command) || !input || extra.length || (command==='export' ? !output : output))
  throw new Error('Usage: node tools/compatibility_receipts.cjs validate input.json | export input.json new-output.json');
 const info=fs.statSync(input);
 if(!info.isFile() || info.size>262144) throw new Error('Receipt input must be a regular file no larger than 256 KiB.');
 const parsed=C.parse(fs.readFileSync(input,'utf8'));
 if(parsed.rejected || !parsed.records.length) throw new Error('Invalid, unsupported or empty receipt file; nothing was written.');
 const configurations=new Map();
 for(const r of parsed.records) {
  const id=JSON.stringify([r.editionId,r.recipe.id]),fingerprint=C.fingerprint(r.recipe);
  if(configurations.has(id) && configurations.get(id)!==fingerprint) throw new Error('One recipe ID has conflicting configurations; nothing was written.');
  configurations.set(id,fingerprint);
 }
 if(command==='export') {
  const data=JSON.stringify(parsed.records.map(r=>C.exportRecord(r)),null,2)+'\n';
  fs.writeFileSync(output,data,{flag:'wx',mode:0o600});
 }
 console.log(`${parsed.records.length} valid record(s), ${configurations.size} edition/setup pair(s).${command==='export' ? ' Wrote new portable copy; review text for privacy before sharing.' : ''}`);
} catch(error) {
 console.error(error.code==='EEXIST' ? 'Output already exists; it was not changed.' : error.code ? `File operation failed (${error.code}); no existing output was changed.` : error.message);
 process.exitCode=1;
}
