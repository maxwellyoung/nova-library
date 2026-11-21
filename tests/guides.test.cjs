const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const guides = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../theme/Guides.js'), 'utf8').replace(/^\.pragma library\s*/, ''), guides);
const entry = (route, sessionProfile = '') => ({title:'Halo: Combat Evolved', systemId:'xbox', route, sessionProfile});
const text = rows => rows.map(r => `${r.label} ${r.value} ${r.detail || ''}`).join('\n');

test('ordinary HakuX routes never advertise undeployed shortcut parity', () => {
  for (const route of ['HakuX (Xbox)', 'HakuX 1.2 (Halo compatibility)', '  hakux  ']) {
    const rows = guides.rows(entry(route));
    assert.equal(rows[0].label, 'HakuX');
    assert.match(text(rows), /Android Back/);
    assert.match(text(rows), /not configured/);
    assert.ok(!rows.some(r => r.value === 'Select + R1'));
  }
});
test('an explicit matching shortcut profile enables the correct safe-slot guide', () => {
  const rows = guides.rows(entry('HakuX 1.2', 'hakux-nova-v1'));
  assert.equal(rows[0].label, 'HakuX · Nova shortcuts');
  assert.ok(rows.some(r => r.value === 'Select + R1'));
  assert.match(text(rows), /all ten slots/);
  assert.match(text(rows), /confirmation/);
});
test('unknown or cross-runtime profiles do not manufacture capabilities', () => {
  assert.equal(guides.rows(entry('HakuX', 'future-build'))[0].label, 'HakuX');
  assert.equal(guides.rows(entry('Unidentified', 'hakux-nova-v1'))[0].value, 'Not checked');
  assert.equal(guides.rows(entry('RetroArch', 'hakux-nova-v1'))[0].label, 'RetroArch');
});
test('unknown routes still offer useful help, and apps stay out of game controls', () => {
  assert.equal(guides.available(entry('')), true);
  assert.match(text(guides.rows(entry(''))), /not identify a supported emulator/);
  assert.equal(guides.available({systemId:'androidapps',route:'HakuX'}), false);
  assert.equal(guides.rows(null).length, 0);
});
test('session saving appears before game controls and technical disc help has no story spoilers', () => {
  const rows = guides.rows({title:'Metal Gear Solid (USA)', systemId:'psx', route:'RetroArch SwanStation'});
  assert.ok(rows.findIndex(r => r.label === 'Save checkpoint') < rows.findIndex(r => r.label === 'In the game'));
  assert.match(text(rows), /Disc Control/);
  assert.doesNotMatch(text(rows), /140\.15|which ending|Boss order|Sniper Wolf/);
});

test('the three checked native routes offer their own menus and preserve save boundaries', () => {
  const cases = [
    ['Ship of Harkinian 9.3.1-android.4', /Android Back/, /RetroArch checkpoints/],
    ['SM64 Coop Deluxe Android 1.5.1', /Start, then R/, /has not been checked yet/],
    ['DevilutionX Android 1.5.5 · shareware', /Select \+ Start/, /shareware portion/],
  ];
  for (const [route, menu, boundary] of cases) {
    const rows = guides.rows({title:'Native fixture', systemId:'n64', route});
    assert.match(rows[0].label, /native/);
    assert.match(text(rows), menu);
    assert.match(text(rows), boundary);
    assert.ok(!rows.some(r => /Select \+ [LR]1/.test(r.value)));
    assert.ok(!rows.some(r => r.label === 'Emulator controls' && r.value === 'Not checked'));
  }
});

test('native instructions stay scoped to their observed runtime versions', () => {
  for (const route of ['Ship of Harkinian 10.0', 'SM64 Coop Deluxe Android 2.0', 'DevilutionX Android 1.6.0 · shareware'])
    assert.equal(guides.rows({title:'Fixture', systemId:'pc', route})[0].value, 'Not checked');
  assert.equal(guides.rows({title:'Super Mario 64',systemId:'n64',route:'RetroArch Mupen64Plus'})[0].label, 'RetroArch');
});

test('an MGS title does not establish an active playlist or a RetroArch disc route',()=>{
 const e={title:'Metal Gear Solid',systemId:'psx',route:'Unknown runtime'};
 const rows=guides.rows(e);
 assert.doesNotMatch(text(rows),/Both discs are in the playlist|Current Disc Index|Disc Control/);
 assert.match(text(rows),/Disc swap|Changing discs/);
});

test('RetroArch swap guidance stays conditional and has an explicit official source',()=>{
 const e={title:'Metal Gear Solid',systemId:'psx',route:'RetroArch SwanStation'};
 const rows=guides.discRows(e),t=text(rows);
 assert.match(t,/Quick Menu → Disc Control/);
 assert.match(t,/If the next disc is listed/);assert.match(t,/If the disc is not listed/);
 assert.match(t,/No Disk/);assert.match(t,/RGUI/);
 assert.match(t,/https:\/\/docs.libretro.com\/guides\/disc-swapping\//);
 assert.doesNotMatch(t,/Both discs are in the playlist/);
 assert.match(t,/not a live disc swap/);assert.match(t,/does not create a checkpoint/);
});
test('explicit disc sets get generic help without borrowing MGS workarounds or runtime support',()=>{
 const e={title:'Invented disc title',systemId:'psx',discSetId:'demo:set',route:'Unknown'};
 let rows=guides.discRows(e);assert.equal(rows.length,2);assert.match(text(rows),/Not checked/);
 assert.doesNotMatch(text(rows),/RGUI|Current Disc Index|Quick Menu|Select \+ Y/);
 rows=guides.discRows({...e,route:'RetroArch checked route'});
 assert.match(text(rows),/Current Disc Index/);assert.doesNotMatch(text(rows),/If MGS|No Disk/);
});
test('disc help is informational and does not appear for unrelated games/apps',()=>{
 for(const e of [null,{title:'Single game',systemId:'snes',route:'RetroArch'},
 {title:'Metal Gear Solid',systemId:'androidapps',route:'RetroArch'},
 {title:'Metal Gear Solid',systemId:'ps2',route:'RetroArch'}])assert.equal(guides.discRows(e).length,0);
 const e={title:'Metal Gear Solid',systemId:'psx',route:'Unknown',missing:true,launchable:false};
 const before=JSON.stringify(e);guides.rows(e);assert.equal(JSON.stringify(e),before);
});

test('quick-load guidance never promises that a title or route selects the newest state',()=>{
 for(const title of ['Super Mario All-Stars','Metal Gear Solid','Invented game']) {
  const rows=guides.rows({title,systemId:title==='Super Mario All-Stars'?'snes':'psx',route:'RetroArch'});
  assert.doesNotMatch(text(rows),/picks up where your last checkpoint|jump to your newest|selects your newest/);
  assert.match(text(rows),/selected slot/);assert.match(text(rows),/confirm the result/);
  assert.ok(rows.findIndex(r=>r.label==='Loading and undo')<rows.findIndex(r=>r.label==='In the game') || !rows.some(r=>r.label==='In the game'));
 }
});
test('RetroArch undo is conditional and volatile, and never claims the source guard is installed',()=>{
 const rows=guides.restoreRows({title:'Fixture',systemId:'psx',route:'RetroArch'});
 assert.match(rows.find(r=>r.label==='Undo a load').value,/if offered/);assert.match(text(rows),/Undo Load State/);assert.match(text(rows),/in memory/);
 assert.match(text(rows),/not a durable checkpoint/);assert.match(text(rows),/Hardcore/);
 assert.match(text(rows),/not presumed built, installed or active/);
 assert.ok(!rows.some(r=>r.command || r.restore || r.save));
});
test('unsupported undo stays explicit without borrowing another runtime from a game title',()=>{
 for(const route of ['HakuX','Unknown','Ship of Harkinian 9.3.1-android.4']) {
  const e={title:'Metal Gear Solid',systemId:'psx',route};const before=JSON.stringify(e),rows=guides.restoreRows(e);
  assert.equal(rows[0].value,'Not checked');assert.doesNotMatch(text(rows),/Quick Menu|Undo Load State/);
  assert.equal(JSON.stringify(e),before);
 }
 assert.equal(guides.restoreRows(entry('HakuX','hakux-nova-v1'))[0].value,'Not in this shortcut profile');
 assert.equal(guides.restoreRows({systemId:'androidapps',route:'RetroArch'}).length,0);
});
