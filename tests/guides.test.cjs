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
