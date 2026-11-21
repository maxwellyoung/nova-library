#!/usr/bin/env python3
"""Replay attached-copy pictures through the real native bridge and full theme."""
import argparse,json,os,shutil,struct,subprocess,tempfile,zlib
from pathlib import Path
from make_demo import generate
from smoke_save_copies import PROFILES
import export_save_copies as exporter
import save_catalogue as history
import save_passport as passport

ROOT=Path(__file__).resolve().parents[1]

def fixture(root,edition='demo:orbit'):
    root.mkdir(mode=0o700)
    source=root/'source';source.mkdir(mode=0o700);(source/'save.sav').write_bytes(b'synthetic progress only')
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    catalogue=history.Catalogue(root/'history',create=True)
    try:
        for i,kind in enumerate(['native-save','emulator-state']):
            selection={'schemaVersion':1,'editionId':edition,'recipeId':'fixture.v1','kind':kind,
                       'runtime':{'name':'Fixture','version':'1.0','core':'standalone'},'files':['save.sav']}
            archive=root/f'{i}.nvs';passport.pack(source,selection,archive,source_idle=True)
            pixels=b''.join(b'\0'+b''.join(bytes(((x+i*80)%256,(y*2)%256,(x+y+i*100)%256)) for x in range(320)) for y in range(200))
            data=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',320,200,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b'')
            picture=root/f'{i}.png';picture.write_bytes(data);picture.chmod(0o600)
            catalogue.import_passport(archive,name='Game save picture' if i==0 else 'Emulator state picture',pinned=True,thumbnail_path=picture)
        exporter.export(catalogue,root/'bundle',include_thumbnails=True)
    finally:
        catalogue.close()
    return root/'bundle'

def run(args):
    if not args.host.is_file():raise ValueError('Use the existing isolated native Qt host')
    args.output.mkdir(parents=True,exist_ok=False);bundle=fixture(args.output/'fixture');results=[]
    jobs=[(p,'flow') for p in PROFILES]+[('nova',s) for s in ('corrupt','missing','stale','link','shared','decoder','focus')]
    for profile,scenario in jobs:
        width,height,inset,flags=PROFILES[profile];out=args.output/(profile+'-'+scenario);out.mkdir();store=out/'store';shutil.copytree(bundle,store)
        with tempfile.TemporaryDirectory(prefix='nova-copy-picture-') as temporary:
            work=Path(temporary);shutil.copytree(ROOT/'theme',work/'theme');owner=work/'theme/Owner.js';owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {inset};'))
            (work/'demo').mkdir();generate(work/'demo/generated');demo=(ROOT/'demo/Demo.qml').read_text()
            (work/'demo/Demo.qml').write_text(demo.rsplit('}',1)[0]+(ROOT/'demo/savecopies/Pictures.qml.inc').read_text()+'}\n')
            command=[str(args.host),'--qml',str(work/'demo/Demo.qml'),'--store',str(store),'--output',str(out),'--scenario',scenario,'--width',str(width),'--height',str(height)]+flags
            done=subprocess.run(command,env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software'),capture_output=True,text=True,timeout=25)
        log=done.stdout+done.stderr;(out/'log.txt').write_text(log)
        warnings=[s for s in log.splitlines() if any(k in s for k in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','Expected token','polish() loop'])]
        expected=[s for s in warnings if scenario=='decoder' and 'image://nova-save-copies/' in s and 'Failed to get image from provider' in s]
        unexpected=[s for s in warnings if s not in expected];safe_log='data:image/' not in log and 'base64,' not in log
        passed=done.returncode==0 and 'COPY_PICTURES_PASS '+scenario in log and not unexpected and safe_log
        results.append({'profile':profile,'scenario':scenario,'passed':passed,'exitCode':done.returncode,'warnings':unexpected,'expectedDecoderWarningCount':len(expected),'noInlineImageBytesInLog':safe_log});print(profile,scenario,'pass' if passed else 'FAIL',flush=True)
        if not passed:print(log[-2500:],flush=True);break
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    return len(results)==len(jobs) and all(r['passed'] for r in results)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',type=Path,required=True);p.add_argument('--output',type=Path,required=True);raise SystemExit(0 if run(p.parse_args()) else 1)
