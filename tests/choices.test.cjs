const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const Lib = vm.createContext({});
vm.runInContext(fs.readFileSync(path.join(__dirname, '../theme/library.js'), 'utf8').replace(/^\.pragma library\s*/, ''), Lib);
const plain = x => JSON.parse(JSON.stringify(x));
const entry = (id, extra = {}, missing = false) => Lib.makeEntry({title:id, sortBy:id, extra:{'edition-id':[id], 'system-id':['snes'], launchable:['true'], ...extra}, missing, assets:{}, lastPlayed:'', files:{count:1}});

test('three distinct local choices rotate without changing input or personal records', () => {
  const entries = ['a','b','c','d','e','f'].map(x => entry('demo:'+x));
  const before = JSON.stringify(entries), pins = ['demo:b'], rotation = ['demo:f'];
  const first = Lib.threeChoices(entries, pins, rotation, ['demo:d'], 0);
  assert.equal(first.total, 6);
  assert.deepEqual(plain(first.choices.map(p => p.entry.id)), ['demo:f','demo:b','demo:d']);
  assert.deepEqual(plain(first.choices.map(p => p.reason)), ['In your rotation','You favourited this edition','Handpicked for Home']);
  const next = Lib.threeChoices(entries, pins, rotation, ['demo:d'], first.nextOffset);
  assert.deepEqual(plain(next.choices.map(p => p.entry.id)), ['demo:a','demo:c','demo:e']);
  assert.equal(JSON.stringify(entries), before);
  assert.deepEqual(pins, ['demo:b']);
});

test('uninstalled Cloud, missing files, apps, emulators and absent routes never enter the pool', () => {
  const entries = [entry('demo:ok'), entry('demo:missing',{},true), entry('demo:noroute',{launchable:['false']}),
    entry('cloud:uninstalled',{launchable:['false'],'cloud-id':['12']}), entry('demo:app',{'system-id':['androidapps']}), entry('demo:emu',{'system-id':['emulators']})];
  assert.deepEqual(plain(Lib.choicePool(entries,[],[],[]).map(p => p.entry.id)), ['demo:ok']);
  entries[0].game.missing = true;
  assert.equal(Lib.choicePool(entries,[],[],[]).length, 0);
});

test('hours played, recommendations and completion states never become inferred preference', () => {
  const entries = [entry('demo:a',{'minutes-value':['99999'],'recommendation-score':['999'],'progress-state':['finished']}), entry('demo:b')];
  const pool = Lib.choicePool(entries,[],[],[]);
  assert.deepEqual(plain(pool.map(p => p.reason)), ['Marked ready in Library','Marked ready in Library']);
  assert.equal(pool[0].entry.status, 'finished');
});

test('an explicit disc family appears once with its playable members and retains the picker identity', () => {
  const disc = (n, ready) => entry('demo:disc'+n, {'disc-set-id':['adventure'],'disc-set-name':['Adventure'],'disc-number':[String(n)], launchable:[ready?'true':'false']});
  const entries = [disc(1,true),disc(2,false)];
  const pool = Lib.choicePool(entries,['demo:disc2'],[],[]);
  assert.equal(pool.length,1); assert.equal(pool[0].entry.discMembers.length,2);
  assert.equal(pool[0].reason,'A disc you favourited');
  entries[0].game.missing=true;
  assert.equal(Lib.choicePool(entries,[],[],[]).length,0);
});

test('same-title distinct editions are not silently merged and reasons remain exact', () => {
  const a=entry('demo:a'),b=entry('demo:b');a.title=b.title='Same title';
  const pool=Lib.choicePool([a,b],['demo:b'],[],[]);
  assert.equal(pool.length,2);assert.notEqual(pool[0].key,pool[1].key);
  assert.equal(pool[0].entry.id,'demo:b');assert.equal(pool[0].reason,'You favourited this edition');
});

test('zero to two available games remain honest and repeated identities never fill missing choices', () => {
  assert.deepEqual(plain(Lib.threeChoices([],[],[],[],0)), {total:0,offset:0,nextOffset:0,choices:[]});
  const a=entry('demo:a'),b=entry('demo:b');
  const first=Lib.threeChoices([a,a,b],[],[],[],0);
  assert.equal(first.total,2);assert.equal(first.choices.length,2);
  assert.equal(first.nextOffset,1);
  const next=Lib.threeChoices([a,b],[],[],[],first.nextOffset);
  assert.deepEqual(plain(next.choices.map(p=>p.entry.id)),['demo:b','demo:a']);
});

test('invalid cursors reset safely and valid offsets wrap within the current pool', () => {
  const entries=[entry('demo:a'),entry('demo:b')];
  for(const offset of [-1,NaN,Infinity,1.2,'1',null]) assert.equal(Lib.threeChoices(entries,[],[],[],offset).offset,0);
  assert.equal(Lib.threeChoices(entries,[],[],[],13).offset,1);
});
