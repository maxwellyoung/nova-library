const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const Lib = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../theme/library.js'), 'utf8').replace(/^\.pragma library\s*/, ''), Lib);
const plain = value => JSON.parse(JSON.stringify(value));
function game(title, extra = {}, missing = false) {
  return {title, sortBy: title, extra, missing, assets: {}, lastPlayed: '', files: {count: 0}};
}

test('stable edition identities distinguish same-title games', () => {
  const a = Lib.makeEntry(game('Same title', {'edition-id': ['demo:first']}));
  const b = Lib.makeEntry(game('Same title', {'edition-id': ['demo:second']}));
  assert.notEqual(a.id, b.id);
});

test('Play requires explicit local route and a non-missing file', () => {
  assert.equal(Lib.makeEntry(game('Unknown route')).launchable, false);
  assert.equal(Lib.makeEntry(game('Local', {'launchable': ['true']})).launchable, true);
  assert.equal(Lib.makeEntry(game('Missing', {'launchable': ['true']}, true)).launchable, false);
});

test('unknown time remains distinct from recorded zero', () => {
  assert.equal(Lib.makeEntry(game('Unknown')).minutesValue, null);
  assert.equal(Lib.makeEntry(game('Zero', {'minutes-value': ['0']})).minutesValue, 0);
  assert.equal(Lib.minutesText(''), '');
  assert.equal(Lib.minutesText('0'), '0 min');
  assert.equal(Lib.minutesText('125'), '2h 5m');
});

test('explicit personal unknown clears catalogue progress without inferring a checkpoint', () => {
  const entry = Lib.makeEntry(game('Game', {'edition-id': ['demo:one'], 'progress-state': ['finished'], story: ['Old checkpoint']}));
  const device = Lib.normalizeDevice({personal: {entries: {'demo:one': {status: 'unknown', checkpoint: '', pending: true, revision: 4}}}});
  Lib.applyPersonal([entry], device);
  assert.equal(entry.status, 'unknown');
  assert.equal(entry.checkpoint, '');
  assert.equal(entry.pending, true);
  assert.equal(entry.revision, 4);
});

test('combined system, kept and local-ready filters preserve entry identity', () => {
  const entries = [
    Lib.makeEntry(game('Amber', {'edition-id': ['demo:a'], 'system-id': ['handheld'], launchable: ['true']})),
    Lib.makeEntry(game('Birch', {'edition-id': ['demo:b'], 'system-id': ['pc'], launchable: ['true']})),
    Lib.makeEntry(game('Cedar', {'edition-id': ['demo:c'], 'system-id': ['handheld']})),
  ];
  const selected = Lib.filterEntries(entries, {system: 'handheld', device: 'here', kept: true, status: ''}, ['demo:a', 'demo:c'], 'AM');
  assert.deepEqual(plain(selected.map(e => e.id)), ['demo:a']);
});

test('lifetime sorting places known zero before unknown without mutating the input', () => {
  const entries = [Lib.makeEntry(game('Unknown')), Lib.makeEntry(game('Zero', {'minutes-value': ['0']})), Lib.makeEntry(game('Played', {'minutes-value': ['9']}))];
  const sorted = Lib.sortEntries(entries, 'lifetime');
  assert.deepEqual(plain(sorted.map(e => e.title)), ['Played', 'Zero', 'Unknown']);
  assert.equal(entries[0].title, 'Unknown');
});


test('observed storage keeps zero, rejects invalid sizes and separates capture from export', () => {
  for (const raw of ['', true, '-1', '1.5', '9007199254740992']) assert.equal(Lib.fileBytes(raw), null);
  assert.equal(Lib.fileBytes('0'), 0);
  const entry = Lib.makeEntry(game('Observed', {'size-bytes': ['1024'], 'size-observed-at': ['2026-10-14T09:15:24Z'], 'catalogue-generated-at': ['2026-10-15T10:00:00Z']}));
  assert.equal(entry.sizeBytes, 1024);
  assert.ok(entry.sizeObservedAt < entry.catalogueGeneratedAt);
  assert.equal(Lib.utcDateText(entry.sizeObservedAt), '2026-10-14 09:15 UTC');
});

test('storage totals exclude utilities and retain entries with unknown size', () => {
  const entries = [
    Lib.makeEntry(game('Zero', {'system-id': ['snes'], 'size-bytes': ['0']})),
    Lib.makeEntry(game('Known', {'system-id': ['snes'], 'size-bytes': ['1024']})),
    Lib.makeEntry(game('Unknown', {'system-id': ['pc']})),
    Lib.makeEntry(game('Utility', {'system-id': ['androidapps'], 'size-bytes': ['4096']})),
  ];
  const summary = Lib.storageSummary(entries);
  assert.equal(summary.bytes, 1024);
  assert.equal(summary.known, 2);
  assert.equal(summary.unknown, 1);
  assert.equal(summary.groups.length, 2);
  assert.equal(summary.largest[0].title, 'Known');
  assert.equal(summary.undated, 2);
});


test('explicit disc grouping preserves raw identity, per-disc readiness and latest default', () => {
  function disc(id, n, ready) {
    return Lib.makeEntry(game('A game (Disc '+n+')', {'edition-id':[id], 'system-id':['handheld'], 'disc-set-id':['demo:set'], 'disc-set-name':['A game'], 'disc-number':[String(n)], launchable:[String(ready)]}));
  }
  const first=disc('demo:disc1',1,true), second=disc('demo:disc2',2,false);
  second.lastPlayedHere=1000;
  const raw=[first,second], grouped=Lib.groupEntries(raw);
  assert.equal(grouped.length,1);
  assert.equal(grouped[0].title,'A game');
  assert.equal(Lib.defaultDisc(grouped[0].discMembers).id,'demo:disc2');
  assert.equal(Lib.discReadyCount(grouped[0]),1);
  assert.equal(grouped[0].discMembers[1].launchable,false);
  assert.equal(Lib.indexOfId(grouped,'demo:disc2'),0);
  assert.deepEqual(plain(raw.map(e=>e.id)),['demo:disc1','demo:disc2']);
  first.lastPlayedHere=null; second.lastPlayedHere=null;
  assert.equal(Lib.defaultDisc([second,first]).id,'demo:disc1');
});

test('same titles and malformed or duplicate disc numbers do not merge editions', () => {
  const row=(id,n,set='demo:set')=>Lib.makeEntry(game('Same',{'edition-id':[id],'system-id':['handheld'],'disc-set-id':[set],'disc-set-name':['Same'],'disc-number':[n]}));
  assert.equal(Lib.groupEntries([row('demo:a','1'),row('demo:b','1')]).length,2);
  assert.equal(Lib.groupEntries([row('demo:a','1'),row('demo:b','0')]).length,2);
  assert.equal(Lib.groupEntries([row('demo:a','1'),row('demo:b','2','demo:other')]).length,2);
  assert.equal(Lib.groupEntries([Lib.makeEntry(game('Same')),Lib.makeEntry(game('Same'))]).length,2);
});


test('DroidDeck app action requires an exact configured Android app identity', () => {
  const app=(title,pkg,ready=true,system='androidapps')=>Lib.makeEntry(game(title,{'edition-id':['demo:'+title+pkg+system],'system-id':[system],'app-package':[pkg],launchable:[String(ready)]}));
  const correct=app('Steam app','com.droiddeck.launcher'), wrong=app('DroidDeck','other.package'), pc=app('DroidDeck','',true,'pc');
  assert.equal(Lib.configuredApp([wrong,pc],'com.droiddeck.launcher','DroidDeck'),null);
  assert.equal(Lib.configuredApp([correct,wrong,pc],'com.droiddeck.launcher','DroidDeck').id,correct.id);
  assert.equal(Lib.configuredApp([app('DroidDeck','',false)],'com.droiddeck.launcher','DroidDeck'),null);
  assert.equal(Lib.configuredApp([app('DroidDeck','')],'com.droiddeck.launcher','DroidDeck').title,'DroidDeck');
});

test('gameplay date evidence preserves precision and does not replace route readiness', () => {
  const entry=Lib.makeEntry(game('Recorded',{'edition-id':['demo:checked'],'system-id':['pc'],'nova-gameplay-note':['Short check'],'nova-gameplay-source':['Synthetic audit'],'nova-gameplay-observed-at':['2026-10-14']}));
  assert.equal(entry.launchable,false);
  assert.equal(Lib.dateEvidenceText(entry.novaGameplayObservedAt),'2026-10-14');
  for(const raw of ['', 'garbage','2026-02-30']) assert.equal(Lib.dateEvidenceText(raw),'Date unknown');
  assert.equal(entry.displayAspect,'');
});


test('a Steam catalogue marker never becomes a claimed local game-file observation', () => {
  const entry=Lib.makeEntry(game('Steam title',{'edition-id':['steam:123'],'system-id':['pc'],'launchable':['true'],'route-label':['DroidDeck (Steam)']}));
  assert.match(Lib.routeSentence(entry), /configured route/);
  assert.doesNotMatch(Lib.routeSentence(entry), /file was found/);
});
