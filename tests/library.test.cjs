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

test('compatibility metadata remains informational and does not create a local launch route', () => {
  const entry = Lib.makeEntry(game('Fixture', {'edition-id':['demo:receipt'], 'compatibility-recipe-id':['fixture.v1'], 'compatibility-receipts':['[]']}));
  assert.equal(entry.compatibilityRecipeId, 'fixture.v1');
  assert.equal(entry.compatibilityReceipts, '[]');
  assert.equal(entry.launchable, false);
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

test('session shortcuts require explicit catalogue metadata, not a matching game title', () => {
  const plain=Lib.makeEntry(game('Halo',{'system-id':['xbox'],'route-label':['HakuX 1.2']}));
  const opted=Lib.makeEntry(game('Halo',{'system-id':['xbox'],'route-label':['HakuX 1.2'],'session-profile':['hakux-nova-v1']}));
  assert.equal(plain.sessionProfile,'');
  assert.equal(opted.sessionProfile,'hakux-nova-v1');
});

test('explicit playlist aliases collapse into an existing same-system disc set without deleting records', () => {
  const members = [1, 2].map(n => Lib.makeEntry(game('Example disc '+n, {'edition-id':['demo:disc'+n], 'system-id':['psx'], 'disc-set-id':['demo:set'], 'disc-set-name':['Example'], 'disc-number':[String(n)]})));
  const alias = Lib.makeEntry(game('Playlist', {'edition-id':['demo:playlist'], 'system-id':['psx'], 'disc-alias-for':['demo:set']}));
  const raw = [alias,...members]; const grouped=Lib.groupEntries(raw);
  assert.equal(grouped.length,1); assert.equal(raw.length,3); assert.equal(grouped[0].discMembers.length,2);
  assert.equal(Lib.presentEdition(alias,grouped).discMembers.length,2);
});
test('unresolved and cross-system playlist aliases remain visible', () => {
  const alias=Lib.makeEntry(game('Unresolved', {'edition-id':['demo:alias'], 'system-id':['pc'], 'disc-alias-for':['demo:set']}));
  assert.equal(Lib.groupEntries([alias]).length,1);
  const members=[1,2].map(n=>Lib.makeEntry(game('Disc '+n,{'edition-id':['demo:d'+n], 'system-id':['psx'], 'disc-set-id':['demo:set'], 'disc-set-name':['Example'], 'disc-number':[String(n)]})));
  assert.equal(Lib.groupEntries([...members,alias]).length,2);
});

test('cleanTitle drops dump tags but keeps disc numbers', () => {
  assert.equal(Lib.cleanTitle('Super Mario All-Stars (U) [!]'), 'Super Mario All-Stars');
  assert.equal(Lib.cleanTitle('Metal Gear Solid (USA) (Disc 1)'), 'Metal Gear Solid (Disc 1)');
  assert.equal(Lib.cleanTitle('Metal Gear Solid - Peace Walker (USA) (PSP) (PSN)'), 'Metal Gear Solid - Peace Walker');
  assert.equal(Lib.cleanTitle('(USA)'), '(USA)');
  assert.equal(Lib.cleanTitle('SSX 3'), 'SSX 3');
});

test('Home leads with real local recents, before handpicked games, without duplicate presentations',()=>{
 const entries=[
  Lib.makeEntry(game('Handpicked',{'edition-id':'demo:picked','launchable':'true'})),
  Lib.makeEntry({...game('Older',{'edition-id':'demo:older','launchable':'true'}),lastPlayed:'2026-11-02T10:00:00Z'}),
  Lib.makeEntry({...game('Newest',{'edition-id':'demo:new','launchable':'true','last-played':'2026-01-01T00:00:00Z'}),lastPlayed:'2026-11-03T10:00:00Z'}),
  Lib.makeEntry({...game('Utility',{'edition-id':'demo:app','system-id':'androidapps','launchable':'true'}),lastPlayed:'2026-11-04T10:00:00Z'})];
 entries.forEach((e,i)=>e.order=i);
 const shelf=Lib.homeShelf(entries,['demo:new'],['demo:picked','demo:new']);
 assert.deepEqual(plain(shelf.entries.map(e=>e.id)),['demo:new','demo:older','demo:picked']);
 assert.equal(shelf.captions['demo:new'],'Last opened here');assert.equal(shelf.captions['demo:picked'],'Right now');
 assert.equal(entries[0].id,'demo:picked');assert.equal(entries[0].lastPlayedHere,null);
});
test('Home fallback remains explicitly labelled and imported activity is not local history',()=>{
 const seeded=Lib.makeEntry(game('Starter',{'edition-id':'demo:seed','home':'true'}));seeded.order=0;
 assert.equal(Lib.homeShelf([seeded],[],[]).captions[seeded.id],'Starter pick');
 const imported=Lib.makeEntry(game('Imported',{'edition-id':'demo:import','last-played':'2026-11-01T00:00:00Z'}));imported.order=1;
 assert.equal(Lib.homeShelf([imported],[],[]).captions[imported.id],'Recent from catalogue');
});
test('original aspect requires explicit sourced metadata and never inherits screen fit or console identity',()=>{
 const old=Lib.makeEntry(game('Old note',{'system-id':'snes','display-aspect':'4:3','display-aspect-source':'Fixture source','device-fit':'4:3'}));
 assert.equal(Lib.aspectMatches(old,'original-4-3'),false);
 for(const source of ['', '<b>source</b>','source\nline']) {
  const e=Lib.makeEntry(game('Untrusted',{'original-aspect':'4:3','original-aspect-source':source}));
  assert.equal(Lib.originalAspect(e),'');
 }
 const e=Lib.makeEntry(game('Sourced',{'original-aspect':'4:3','original-aspect-source':'Synthetic manual citation'}));
 assert.equal(Lib.aspectMatches(e,'original-4-3'),true);assert.equal(Lib.aspectMatches(e,'native-4-3'),false);
});
test('aspect intersects search, system, device, status and favourites; unknowns remain findable',()=>{
 const a=Lib.makeEntry(game('Amber',{'edition-id':'demo:a','system-id':'snes','launchable':'true','progress-state':'playing'}));
 const b=Lib.makeEntry(game('Birch',{'edition-id':'demo:b','system-id':'snes','launchable':'true'}));
 a.displayEvidence={native43:true,stretchOnly:false,unknown:false};
 const f={...plain(Lib.emptyFilters()),aspect:'native-4-3',system:'snes',device:'here',status:'playing',kept:true};
 assert.deepEqual(plain(Lib.filterEntries([a,b],f,[a.id],'amb').map(e=>e.id)),[a.id]);
 assert.equal(Lib.filtersActive({aspect:'native-4-3'}),true);
 assert.deepEqual(plain(Lib.filterEntries([a,b],{...plain(Lib.emptyFilters()),aspect:'unverified'},[],'').map(e=>e.id)),[b.id]);
 assert.equal(Lib.filterEntries([a,b],{...f,aspect:'stretch-only'},[a.id],'').length,0);
});
test('a disc set needs every member for a confirmed aspect, and untested members remain discoverable',()=>{
 const make=(n)=>Lib.makeEntry(game('Fixture Disc '+n,{'edition-id':'demo:disc'+n,'system-id':'ps','disc-set-id':'fixture.set','disc-set-name':'Fixture set','disc-number':String(n),'launchable':'true'}));
 const a=make(1),b=make(2);a.displayEvidence={native43:true,unknown:false};
 const grouped=Lib.groupEntries([a,b]);assert.equal(grouped.length,1);
 const f={...plain(Lib.emptyFilters()),aspect:'native-4-3'};
 assert.equal(Lib.filterEntries(grouped,f,[],'').length,0);
 assert.equal(Lib.filterEntries(grouped,{...f,aspect:'unverified'},[],'').length,1);
 b.displayEvidence={native43:true,unknown:false};assert.equal(Lib.filterEntries(Lib.groupEntries([a,b]),f,[],'').length,1);
});

test('reading and adopting an existing checkpoint preserves its exact text and unresolved provenance', () => {
  for (const checkpoint of ['  Existing checkpoint.  ', {text:'\nExisting checkpoint.\n'}]) {
    const text=typeof checkpoint==='string'?checkpoint:checkpoint.text;
    const e=Lib.makeEntry(game('Original', {'edition-id':['demo:verbatim']}));
    const d=Lib.normalizeDevice({personal:{entries:{'demo:verbatim':{checkpoint,revision:7,pending:true,conflict:true,status:'playing'}}}});
    Lib.applyPersonal([e],d);
    assert.equal(e.checkpoint,text);
    assert.equal(e.revision,7);assert.equal(e.pending,true);assert.equal(e.conflict,true);
    assert.equal(e.checkpointSource,'you');
  }
});


test('game discovery excludes app routes while explicit system filters keep them reachable', () => {
  const entries = ['snes', 'androidapps', 'emulators'].map(system => Lib.makeEntry(game('Shared ' + system, {'edition-id':['demo:'+system], 'system-id':[system], launchable:['true']})));
  const filters = plain(Lib.emptyFilters());
  assert.deepEqual(plain(Lib.filterEntries(entries, filters, [], 'Shared').map(e => e.systemId)), ['snes']);
  for (const system of ['androidapps', 'emulators']) {
    assert.deepEqual(plain(Lib.filterEntries(entries, {...filters, system}, [], '').map(e => e.systemId)), [system]);
  }
  assert.deepEqual(plain(entries.filter(Lib.isApp).map(e => e.systemId)), ['androidapps', 'emulators']);
  assert.equal(Lib.appPurpose(entries[2]), '');
  assert.match(Lib.routeSentence(entries[2]), /App shortcut set up here/);
});

test('installation badges preserve evidence boundaries independently of launch readiness', () => {
  const observation = (state, complete = true) => ({state, scopeComplete:complete, source:'Synthetic scan', observedAt:'2026-11-05T00:00:00Z'});
  const badge = (nova, legion, launchable = false) => Lib.installBadge({installations:{nova,legion},launchable});
  assert.equal(badge(undefined, undefined), 'Install not checked');
  assert.equal(badge(undefined, undefined, true), 'Install not checked');
  assert.equal(badge(observation('absent',false), undefined), 'Install not checked');
  assert.equal(badge(observation('absent'), observation('installed')), 'Seen on Legion');
  assert.equal(badge(observation('partial'), observation('installed')), 'Incomplete on Nova');
  assert.equal(badge(observation('absent'), observation('absent')), 'Absent in both scans');
  assert.equal(badge(observation('absent'), undefined), 'Not on Nova');
  assert.equal(badge(observation('installed'), observation('installed')), 'Nova + Legion');
  assert.equal(badge(observation('installed'), undefined), 'On Nova');
  assert.equal(badge({state:'installed',source:'Synthetic scan',observedAt:'bad'}, undefined), 'Install not checked');
});

test('storage orders observed sizes largest first and distinguishes zero from unknown', () => {
  const entries = [
    {systemId:'a',systemName:'Alpha unknown',sizeBytes:null},
    {systemId:'z',systemName:'Zero',sizeBytes:0},
    {systemId:'big',systemName:'Big',sizeBytes:900,title:'Large'},
    {systemId:'mixed',systemName:'Mixed',sizeBytes:null},
    {systemId:'mixed',systemName:'Mixed',sizeBytes:90,title:'Small'},
    {systemId:'emulators',systemName:'Emulator',sizeBytes:9000,title:'Utility'}
  ];
  const before = JSON.stringify(entries);
  assert.deepEqual(plain(Lib.storageSummary(entries).groups.map(g=>g.id)), ['big','mixed','z','a']);
  assert.equal(JSON.stringify(entries), before);
});


test('all install summaries share state priority and route labels remain explicit', () => {
  const observation = state => state === 'unknown' ? undefined : ({state, scopeComplete:true, source:'Synthetic scan', observedAt:'2026-11-05'});
  for (const nova of ['unknown','partial','installed','absent']) for (const legion of ['unknown','partial','installed','absent']) {
    const e={installations:{nova:observation(nova),legion:observation(legion)},launchable:false};
    const known=nova!=='unknown'||legion!=='unknown';
    assert.equal(Lib.hasInstallObservation(e),known);
    assert.equal(Lib.availabilityText(e),known?Lib.installBadge(e):'Install status not checked');
    assert.equal(Lib.libraryBadge(e,''),Lib.installBadge(e)+(nova==='installed'?' · no route':''));
    e.launchable=true;
    assert.equal(Lib.libraryBadge(e,''),Lib.installBadge(e));
    assert.equal(Lib.libraryBadge(e,'0 min'),'0 min');
  }
  const partial={installations:{nova:observation('partial'),legion:observation('installed')}};
  assert.equal(Lib.availabilityText(partial),'Incomplete on Nova');
});

test('colliding cleaned titles retain distinguishable file evidence and stable identities', () => {
  const entry = (id, title, file, system='gc') => Lib.makeEntry({...game(title, {'edition-id':[id], 'system-id':[system], launchable:['true']}),files:{count:1,get:()=>({path:file})}});
  const a=entry('demo:a',"Haunted House",'/roms/Haunted House (USA, Canada).ciso');
  const b=entry('demo:b',"Haunted House (USA).nkit",'/roms/Haunted House (USA).nkit.iso');
  const other=entry('demo:c','Other (USA)','/roms/Other (USA).iso');
  const crossSystem=entry('demo:d','Haunted House','/roms/Haunted House.iso','ps2');
  const rows=[a,b,other,crossSystem];
  Lib.distinguishEditions(rows);
  assert.equal(a.title,'Haunted House');
  assert.equal(b.title,'Haunted House');
  assert.equal(Lib.displayTitle(a),'Haunted House · USA/Canada · CISO');
  assert.equal(Lib.displayTitle(b),'Haunted House · USA · NKit');
  assert.equal(Lib.displayTitle(other),'Other');
  assert.equal(Lib.displayTitle(crossSystem),'Haunted House');
  assert.deepEqual(rows.map(e=>e.id),['demo:a','demo:b','demo:c','demo:d']);
  assert.equal(a.game.files.get(0).path,'/roms/Haunted House (USA, Canada).ciso');
  assert.equal(a.launchable,true);
  const x=entry('demo:z','Same','/one/Same.iso'),y=entry('demo:y','Same','/two/Same.iso');
  Lib.distinguishEditions([x,y]);const labels=[Lib.displayTitle(x),Lib.displayTitle(y)];
  Lib.distinguishEditions([y,x]);assert.deepEqual([Lib.displayTitle(x),Lib.displayTitle(y)],labels);
  assert.notEqual(labels[0],labels[1]);assert.ok(labels.every(s=>!s.includes('/')));
});

test('catalogue observation prose formats valid dates without inventing new observations', () => {
  assert.equal(Lib.observationText('Local file observed, 2026-10-15T20:16:52+00:00'),'Local file observed, 2026-10-15 20:16 UTC');
  assert.equal(Lib.observationText('Location not checked'),'Location not checked');
  assert.equal(Lib.observationText('Seen 2026-99-99T20:16:52Z'),'Seen 2026-99-99T20:16:52Z');
});


test('paused stays distinct from playing and abandoned through personal overlay and filtering', () => {
  assert.equal(Lib.STATUS_LABELS.paused, 'Paused');
  assert.ok(Lib.STATUSES.includes('paused'));
  const entry = Lib.makeEntry(game('Pause me', {'edition-id':['demo:paused'], 'progress-state':['playing']}));
  const paused = entry;
  Lib.applyPersonal([paused], Lib.normalizeDevice({personal:{entries:{'demo:paused':{status:'paused',checkpoint:'At the lift',revision:2,pending:true}}}}));
  assert.equal(paused.status, 'paused');
  assert.equal(paused.checkpoint, 'At the lift');
  assert.equal(Lib.filterEntries([paused], {status:'paused'}, []).length, 1);
  assert.equal(Lib.filterEntries([paused], {status:'playing'}, []).length, 0);
  assert.equal(Lib.filterEntries([paused], {status:'abandoned'}, []).length, 0);
});

function cloudGame(id=1, overrides={}) {
  const scope='a'.repeat(64), revision='b'.repeat(64);
  return {id,title:'A Cloud Game',platform:'snes',system:'Super Nintendo',editionId:`nova:cloud_${scope}:${id}_${revision}`,
    cloudKey:`cloud:${scope}:${id}`,installed:false,partial:false,supported:true,bytes:1234,
    observedAt:'2026-11-06T00:00:00Z',...overrides};
}

test('cloud editions enter ordinary discovery without manufacturing a ready route or usage', () => {
  const g=cloudGame(), e=Lib.cloudEntry(g,{});
  assert.equal(e.id,g.editionId);assert.equal(e.cloudKey,g.cloudKey);
  assert.equal(e.launchable,false);assert.equal(e.lastPlayedHere,null);assert.equal(e.minutesValue,null);
  assert.equal(Lib.installation(e,'nova').state,'absent');assert.equal(Lib.installBadge(e),'In cloud');
  assert.equal(Lib.filterEntries([e],Lib.emptyFilters(),[],'cloud').length,1);
  const ready={...Lib.emptyFilters(),device:'here'};
  assert.equal(Lib.filterEntries([e],ready,[],'').length,0);
  const installed=Lib.cloudEntry({...g,installed:true},{[g.editionId]:1770000000000});
  assert.equal(installed.launchable,true);assert.equal(installed.lastPlayedHere,1770000000000);
  assert.equal(installed.lastPlayed,null);assert.equal(installed.status,'unknown');
  assert.equal(Lib.filterEntries([installed],ready,[],'').length,1);
});

test('cloud metadata cannot choose a legacy identity or executable and cannot overwrite an existing edition', () => {
  for(const bad of [{editionId:'nova:snes:owner'}, {cloudKey:'other'}, {id:1.5}, {platform:'../path'}, {platform:'androidapps'}, {platform:'emulators'}, {editionId:cloudGame().editionId.replace(':1_',':2_')}])
    assert.equal(Lib.cloudEntry(cloudGame(1,bad),{}),null);
  const g=cloudGame(1,{launch:'server command',cover:'https://remote.test/image'}), e=Lib.cloudEntry(g,{});
  assert.equal(e.game.launch,undefined);assert.equal(e.art,'');
  const existing=Lib.makeEntry(game('Existing',{'edition-id':[g.editionId]}));
  const merged=Lib.mergeCloudEntries([existing],[g],{});
  assert.equal(merged.length,1);assert.equal(merged[0],existing);
});

test('cloud copies with matching titles stay distinct and focus survives a scanned identity revision', () => {
  const first=cloudGame(), second=cloudGame(2), old=Lib.cloudEntry(first,{});
  const raw=Lib.makeEntry(game(first.title,{'edition-id':['nova:snes:local']}));
  const merged=Lib.mergeCloudEntries([raw],[first,second],{});Lib.distinguishEditions(merged);
  assert.equal(merged.length,3);assert.notEqual(merged[1].id,merged[2].id);
  assert.match(merged[1].editionLabel,/Cloud copy/);
  const scanned=Lib.cloudEntry({...first,editionId:first.editionId.slice(0,-64)+'c'.repeat(64)},{});
  assert.equal(Lib.retainedEntryId([scanned],old,old.id),scanned.id);
  assert.equal(Lib.retainedEntryId([old,scanned],old,old.id),old.id);
  assert.equal(Lib.retainedEntryId([Lib.cloudEntry(second,{})],old,old.id),old.id);
});

test('cloud refresh signatures ignore scan timestamps while tracking actual UI state', () => {
  const g=cloudGame();
  assert.equal(Lib.cloudSignature([g]),Lib.cloudSignature([{...g,observedAt:'2026-11-06T01:00:00Z'}]));
  assert.notEqual(Lib.cloudSignature([g]),Lib.cloudSignature([{...g,installed:true}]));
  assert.notEqual(Lib.cloudSignature([g]),Lib.cloudSignature([{...g,cover:'file:///synthetic/cover'}]));
});

test('phone audio uses an exact configured receiver package and never a matching title alone', () => {
  const app=Lib.makeEntry(game('AirPlay Server',{'edition-id':['demo:receiver'],'system-id':['androidapps'],'app-package':['io.github.jqssun.airplay'],launchable:['true']}));
  assert.equal(Lib.phoneAudioApp([app]),app);
  assert.equal(Lib.phoneAudioApp([{...app,appPackage:'other.package'}]),null);
  assert.equal(Lib.phoneAudioApp([{...app,launchable:false}]),null);
  assert.equal(Lib.phoneAudioApp([{...app,game:{...app.game,missing:true}}]),null);
});

test('cloud download actions separate observed partial bytes from a resumable plan', () => {
  const entry=values=>Lib.cloudEntry({...cloudGame(),...values},{});
  assert.equal(Lib.cloudActionLabel(entry({})), 'Install');
  assert.equal(Lib.cloudActionLabel(entry({partial:true})), 'Check download');
  assert.equal(Lib.cloudActionLabel(entry({partial:true,resumeAvailable:true})), 'Resume download');
  const protectedEntry=entry({partial:true,downloadBlocked:true,downloadState:'blocked',downloadReason:'Files belong to another library'});
  assert.equal(Lib.cloudActionLabel(protectedEntry),'Review download');
  assert.equal(Lib.installBadge(protectedEntry),'Needs review');
  assert.match(Lib.availabilityText(protectedEntry),/files kept/);
  const active=entry({partial:true,resumeAvailable:true,downloadState:'downloading'});
  assert.equal(Lib.installBadge(active),'Downloading');
  assert.doesNotMatch(Lib.availabilityText(active),/paused/);
  assert.equal(Lib.cloudActionLabel(entry({installed:true,downloadBlocked:true})), 'Play');
});

test('cloud recovery facts refresh the model without rebuilding on every retained byte', () => {
  const g=cloudGame(),signature=Lib.cloudSignature([g]);
  for(const change of [{resumeAvailable:true},{downloadBlocked:true},{downloadState:'downloading'},{downloadReason:'Needs review'}])
    assert.notEqual(Lib.cloudSignature([{...g,...change}]),signature);
  assert.equal(Lib.cloudSignature([{...g,retainedBytes:123}]),signature);
});

test('cloud recent history roundtrips and refuses unknown or corrupt stores without replacing them', () => {
  const id=cloudGame().editionId, now=1770000000000;
  const empty=Lib.cloudHistoryStore(null,now), stored=Lib.rememberCloudOpening(empty,id,now);
  assert.equal(Object.keys(empty.opened).length,0);assert.equal(stored.version,1);
  assert.equal(Lib.cloudHistoryStore(JSON.parse(JSON.stringify(stored)),now).opened[id],now);
  for(const bad of [{version:2,opened:{[id]:now}}, {version:1,opened:{[id]:'today'}}, {version:1,opened:{[id]:now+900000}}, {version:1,opened:{unrecognized:now}}]) {
    const before=JSON.stringify(bad);
    assert.equal(Lib.cloudHistoryStore(bad,now),null);
    assert.equal(Lib.rememberCloudOpening(bad,id,now),null);
    assert.equal(JSON.stringify(bad),before);
  }
});
