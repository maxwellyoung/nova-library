const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const crypto=require('node:crypto');
const root=path.resolve(__dirname,'..');
function load(file){const scope={};vm.createContext(scope);vm.runInContext(fs.readFileSync(path.join(root,file),'utf8').replace(/^\.pragma library\s*/m,''),scope);return scope;}
const lib=load('theme/library.js'),marks=load('theme/PlatformMarks.js');

test('Xbox and named platform identities never fall through to an information glyph',()=>{
  for(const id of ['xbox','xbox360','gc','psx','ps2','psp','nds','n3ds','switch']){
    assert.ok(marks.commands(lib.consoleGlyph(id)),id);
    assert.ok(lib.consoleShortName({id}));
  }
  assert.equal(lib.consoleShortName({id:'xbox'}),'Xbox');
  assert.equal(lib.consoleShortName({id:'xbox360'}),'Xbox 360');
  assert.equal(lib.consoleGlyph('new-system'),'system');
  assert.equal(lib.consoleShortName({id:'new-system',name:'A future system'}),'A future system');
  assert.equal(lib.consoleGlyph('gba'),'gba');
  assert.notEqual(lib.consoleGlyph('gba'),lib.consoleGlyph('psp'));
});

test('compact console identities keep square 3DS geometry and sort by visible names',()=>{
  assert.equal(lib.consoleWordmark('n3ds'),false);
  for(const id of ['ps2','ps3','psp','vita'])assert.equal(lib.consoleCardGlyph(id),'psx');
  assert.equal(lib.consoleCardGlyph('nds'),'ds-hardware');
  assert.equal(lib.consoleGlyph('psp'),'psp');
  const systems=lib.systemsOf([{systemId:'xbox',systemName:'Microsoft Xbox'},
    {systemId:'gc',systemName:'Nintendo GameCube'},{systemId:'n64',systemName:'Nintendo 64'}]);
  assert.deepEqual(Array.from(systems,s=>lib.consoleShortName(s)),['GameCube','Nintendo 64','Xbox']);
});

test('a mixed Home shelf does not claim every entry was recently opened',()=>{
  const entries=[{id:'recent'},{id:'favourite'}];
  assert.equal(lib.homeHeading(entries,{recent:'Last opened here',favourite:'Favourite'},false,'Good evening'),'Your library');
  assert.equal(lib.homeHeading(entries,{recent:'Last opened here',favourite:'Last opened here'},false,'Good evening'),'Recently opened');
  assert.equal(lib.homeHeading([],{},true,'Good evening'),'Your library');
  assert.equal(lib.homeHeading(entries,{recent:'Playing',favourite:'Favourite'},false,'Good evening'),'Good evening');
});

test('collection previews are bounded, omit unavailable art/apps and preserve the input',()=>{
  const entries=[{id:'a',systemId:'xbox',art:''},{id:'b',systemId:'psx',art:'one'},
    {id:'c',systemId:'psx',art:'two'},{id:'d',systemId:'psx',art:'three'},
    {id:'e',systemId:'psx',art:'four'},{id:'app',systemId:'androidapps',art:'icon'}];
  const before=JSON.stringify(entries),result=lib.consolePreviews(entries);
  assert.equal(result.psx.length,3);assert.equal(result.psx[0].id,'b');
  assert.equal(result.xbox,undefined);assert.equal(result.androidapps,undefined);
  assert.equal(JSON.stringify(entries),before);
});

test('display cleanup removes a recognized pack suffix while retaining editions and disc identity',()=>{
  assert.equal(lib.cleanTitle('F-Zero GX (EU) (2003) (Racing) (GameCube)'),'F-Zero GX');
  assert.equal(lib.cleanTitle("Luigi's Mansion (USA).nkit"),"Luigi's Mansion");
  assert.equal(lib.cleanTitle('A Game (USA) (2001) (Action) (GameCube) (Disc 2)'),'A Game (Disc 2)');
  for(const title of ['Gran Turismo 4 Spec II 1.10',"A Game (Director’s Cut)",'Metal Gear Solid (Disc 2)','A Game (2003) (Racing)'])assert.equal(lib.cleanTitle(title),title);
});

test('console previews show different works without merging same-title editions in the library',()=>{
  const entries=[{id:'eu',systemId:'gc',title:'A game',art:'eu'},
    {id:'us',systemId:'gc',title:'A Game',art:'us'},
    {id:'copy',systemId:'gc',title:'Another edition',art:'eu'},
    {id:'other',systemId:'gc',title:'Other game',art:'other'},
    {id:'third',systemId:'gc',title:'Third game',art:'third'}];
  const before=JSON.stringify(entries),sample=lib.consolePreviews(entries).gc;
  assert.deepEqual(Array.from(sample,e=>e.id),['eu','other','third']);
  assert.equal(JSON.stringify(entries),before);assert.equal(entries.length,5);
});

test('platform vectors are finite Canvas commands, retain their pinned originals and attribution',()=>{
  const sources=JSON.parse(fs.readFileSync(path.join(root,'assets/platforms/sources.json'),'utf8'));
  for(const [name,item] of Object.entries(sources)){
    const raw=fs.readFileSync(path.join(root,'assets/platforms',item.file));
    assert.equal(crypto.createHash('sha256').update(raw).digest('hex'),item.sha256,name);
    const commands=marks.commands(name);assert.ok(commands.length>2,name);
    for(const [command,...numbers] of commands){
      assert.equal(numbers.length,{M:2,L:2,C:6,Q:4,Z:0}[command],name);
      assert.ok(numbers.every(Number.isFinite),name);
    }
    const calls=[];const ctx={};
    for(const method of ['save','restore','translate','scale','beginPath','moveTo','lineTo','bezierCurveTo','quadraticCurveTo','closePath','fill'])ctx[method]=(...args)=>calls.push([method,...args]);
    assert.equal(marks.draw(ctx,name),true);assert.equal(calls.filter(x=>x[0]==='fill').length,1);
    assert.equal(calls.at(-1)[0],'restore');
  }
  assert.equal(marks.draw({},'new-system'),false);
  const source=fs.readFileSync(path.join(root,'theme/PlatformMarks.js'),'utf8');
  assert.match(source,/Fonticons, Inc/);assert.match(source,/creativecommons.org\/licenses\/by\/4.0/);
});

test('classic PC, N64, DS and console navigation use separate pinned filled silhouettes',()=>{
  const requested=['pc','n64','ds-hardware','consoles'];
  for(const name of requested){
    assert.ok(marks.commands(name),name);
    const b=Array.from(marks.bounds[name]);
    assert.ok(b.every(Number.isFinite),name);
    assert.ok(b[2]>0&&b[3]>0,name);
    // Both real display sizes must preserve the source ratio and fit their Canvas.
    for(const size of [22,44]){
      let translate,scale;
      const ctx={save(){},restore(){},beginPath(){},moveTo(){},lineTo(){},bezierCurveTo(){},quadraticCurveTo(){},closePath(){},fill(){},
        translate(x,y){translate=[x,y];},scale(x,y){scale=[x,y];}};
      assert.equal(marks.draw(ctx,name,size,size),true);
      assert.equal(scale[0],scale[1],name);
      const left=translate[0]+b[0]*scale[0],top=translate[1]+b[1]*scale[1];
      assert.ok(left>=-1e-9&&top>=-1e-9,name);
      assert.ok(left+b[2]*scale[0]<=size+1e-9&&top+b[3]*scale[1]<=size+1e-9,name);
    }
  }
  assert.equal(new Set(requested.map(name=>JSON.stringify(marks.commands(name)))).size,4);
  assert.equal(marks.commands('nova'),null);
  assert.equal(lib.consoleCardGlyph('nds'),'ds-hardware');
  assert.equal(lib.consoleCardGlyph('n64'),'n64');
  assert.equal(lib.consoleCardGlyph('pc'),'pc');
  const source=fs.readFileSync(path.join(root,'theme/PlatformMarks.js'),'utf8');
  assert.match(source,/Libretro RetroArch assets Monochrome, CC BY 4.0/);
});

test('SNES, GBA, Dreamcast and the Game Boy family are pinned filled hardware, not hand-drawn cases',()=>{
  const sources=JSON.parse(fs.readFileSync(path.join(root,'assets/platforms/sources.json'),'utf8'));
  const icon=fs.readFileSync(path.join(root,'theme/Icon.qml'),'utf8');
  const names=['snes','nes','gb','gbc','gba','dreamcast'];
  for(const name of names){
    assert.match(sources[name].source,/retroarch-assets\/d9f969054dc7fbb6fa89519036d2b971e0855b51\/src\/xmb\/monochrome\//,name);
    assert.match(sources[name].license,/CC-BY-4.0/,name);
    assert.equal(lib.consoleCardGlyph(name),name);
    assert.ok(marks.commands(name),name);
    assert.ok(!icon.includes('case "'+name+'"'),name);
  }
  assert.equal(new Set(names.map(name=>JSON.stringify(marks.commands(name)))).size,names.length);
  const source=fs.readFileSync(path.join(root,'theme/PlatformMarks.js'),'utf8');
  assert.match(source,/SNES\/NES\/GB\/GBC\/GBA\/Dreamcast: Libretro RetroArch/);
  assert.match(fs.readFileSync(path.join(root,'theme/theme.qml'),'utf8'),/SNES, NES, Game Boy family and Dreamcast artwork: RetroArch/);
});

test('the shared keyline keeps the 56x44 card and 28x22 caption marks optically close and inside their slot',()=>{
  const cards=['snes','gba','dreamcast','gbc','psx','xbox','gc','n64','ds-hardware','pc','switch'];
  for(const [w,h] of [[56,44],[28,22]]){
    const sizes=cards.map(name=>{
      let scale,left,top;const ctx={save(){},restore(){},beginPath(){},moveTo(){},lineTo(){},bezierCurveTo(){},quadraticCurveTo(){},closePath(){},fill(){},
        translate(x,y){left=x;top=y;},scale(x){scale=x;}};
      assert.equal(marks.draw(ctx,name,w,h),true);
      const b=Array.from(marks.bounds[name]),px=b[0]*scale+left,py=b[1]*scale+top;
      assert.ok(px>=-1e-9&&py>=-1e-9&&px+b[2]*scale<=w+1e-9&&py+b[3]*scale<=h+1e-9,name);
      return Math.sqrt(b[2]*b[3])*scale;
    });
    assert.ok(Math.max(...sizes)/Math.min(...sizes)<1.25,JSON.stringify(sizes));
  }
});

test('a left-aligned mark starts at its slot edge beside a text column',()=>{
  let left,scale;const ctx={save(){},restore(){},beginPath(){},moveTo(){},lineTo(){},bezierCurveTo(){},quadraticCurveTo(){},closePath(){},fill(){},
    translate(x){left=x;},scale(x){scale=x;}};
  assert.equal(marks.draw(ctx,'pc',28,22,0),true);
  assert.ok(Math.abs(left+marks.bounds.pc[0]*scale)<1e-9);
});

test('fallback line drawings use one scale so a wide console slot cannot stretch them',()=>{
  const icon=fs.readFileSync(path.join(root,'theme/Icon.qml'),'utf8');
  assert.match(icon,/c\.scale\(unit, unit\)/);
  assert.doesNotMatch(icon,/c\.scale\(width \/ 24, height \/ 24\)/);
});
