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
