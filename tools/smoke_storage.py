#!/usr/bin/env python3
"""Exercise volume/category visualization in the real theme, using supplied synthetic snapshots."""
import argparse,copy,json,os
from pathlib import Path
import shutil,subprocess,tempfile
from make_demo import generate
from smoke_offline import PROFILES
ROOT=Path(__file__).resolve().parents[1]
GIB=1073741824


def run(args):
    if not args.host.is_file() or not args.bundle.is_dir():raise ValueError('Use the existing isolated host and synthetic bundle')
    args.output.mkdir(parents=True,exist_ok=False);results=[]
    jobs=[(p,'flow') for p in PROFILES]+[(PROFILES[0],s) for s in ['legacy','sd-unknown','zero','conflict','invalid','category-conflict']]
    for (profile,width,height,inset,flags),scenario in jobs:
        out=args.output/(profile+'-'+scenario);out.mkdir()
        internal={'id':'internal-data','total':64*GIB,'used':40*GIB,'free':20*GIB,'source':'Synthetic disjoint allocated-byte observation','observedAt':'2026-11-10T10:00:00Z','breakdown':{'basis':'allocated-bytes','disjoint':True,'categories':{'game-data':12*GIB,'app-data':8*GIB,'cache':0,'save-data':GIB}}}
        sd={'id':'sd-card','total':256*GIB,'used':64*GIB,'free':192*GIB,'source':'Synthetic removable-volume observation','observedAt':'2026-11-10T09:00:00Z','breakdown':{'basis':'allocated-bytes','disjoint':True,'categories':{'game-data':48*GIB,'save-data':2*GIB}}}
        if scenario=='zero':internal.update(used=64*GIB,free=0)
        if scenario=='invalid':internal['breakdown']['disjoint']=False
        if scenario=='legacy':internal.pop('breakdown')
        with tempfile.TemporaryDirectory(prefix='nova-storage-ui-') as temp:
            work=Path(temp);shutil.copytree(ROOT/'theme',work/'theme');owner=work/'theme/Owner.js';owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {inset};'))
            (work/'demo').mkdir();games=generate(work/'demo/generated')
            games[0]['extra'].update({'size-bytes':str(80*GIB),'size-observed-at':'2026-11-09T08:00:00Z'})
            utility=copy.deepcopy(games[-1]);utility['extra'].update({'edition-id':'demo:capacity','system-id':'emulators','system-name':'Utilities'});utility['title']='Synthetic capacity observation'
            utility['extra']['storage-volume']=json.dumps(internal)
            if scenario!='legacy':utility['extra']['storage-volumes']=json.dumps([internal] if scenario=='sd-unknown' else [internal,sd])
            games.append(utility)
            if scenario in ['conflict','category-conflict']:
                other=copy.deepcopy(utility);other['extra']['edition-id']='demo:capacity-conflict';changed=copy.deepcopy(internal)
                if scenario=='conflict':changed['free']-=GIB
                else:changed['breakdown']['categories']['cache']=GIB
                other['extra']['storage-volumes']=json.dumps([changed]);games.append(other)
            (work/'demo/generated/games.js').write_text('.pragma library\nvar games = '+json.dumps(games)+';\n')
            demo=(ROOT/'demo/Demo.qml').read_text();(work/'demo/Demo.qml').write_text(demo.rsplit('}',1)[0]+(ROOT/'demo/storage/Smoke.qml.inc').read_text()+'}\n')
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
            done=subprocess.run([str(args.host),'--qml',str(work/'demo/Demo.qml'),'--store',str(args.bundle),'--output',str(out),'--scenario',scenario,'--width',str(width),'--height',str(height)]+flags,env=env,text=True,capture_output=True,timeout=25)
        log=done.stdout+done.stderr;(out/'log.txt').write_text(log)
        warnings=[line for line in log.splitlines() if any(s in line for s in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop','Synthetic demo has no launch route'])]
        passed=done.returncode==0 and 'STORAGE_THEME_PASS '+scenario in log and not warnings
        results.append({'profile':profile,'scenario':scenario,'passed':passed,'code':done.returncode,'warnings':warnings});print(profile,scenario,'pass' if passed else 'FAIL',flush=True)
        if not passed:print(log[-3000:],flush=True)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n');return all(r['passed'] for r in results)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['host','bundle','output']:p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args()
    try:raise SystemExit(0 if run(a) else 1)
    except (ValueError,OSError,subprocess.TimeoutExpired):p.exit(1,'Storage verification did not complete; inspect partial evidence.\n')
