#!/usr/bin/env python3
"""Exercise actual disc-picker/help/Back paths with synthetic, non-executable routes."""
import argparse,json,os
from pathlib import Path
import shutil,subprocess,tempfile
from make_demo import generate
from smoke_offline import PROFILES
ROOT=Path(__file__).resolve().parents[1]


def run(args):
    if not args.host.is_file() or not args.bundle.is_dir():raise ValueError('Use the existing isolated Qt host and synthetic bundle')
    args.output.mkdir(parents=True,exist_ok=False);results=[]
    jobs=[(p,'flow') for p in PROFILES]+[(PROFILES[0],s) for s in ['missing','unknown','mixed','nohistory']]+[(PROFILES[2],'long')]
    for (profile,width,height,inset,flags),scenario in jobs:
        out=args.output/(profile+'-'+scenario);out.mkdir()
        with tempfile.TemporaryDirectory(prefix='nova-discs-ui-') as temp:
            work=Path(temp);shutil.copytree(ROOT/'theme',work/'theme');owner=work/'theme/Owner.js';owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {inset};'))
            (work/'demo').mkdir();games=generate(work/'demo/generated')
            name='Metal Gear Solid' if scenario!='long' else 'An unusually long explicit disc-set name with a regional subtitle and a separately identified edition'
            for i in range(2):
                g=games[i];g['title']=name+f' (Disc {i+1})';g['sortBy']=g['title']
                g['extra'].update({'edition-id':f'demo:disc{i+1}','system-id':'psx','system-name':'PlayStation','disc-set-id':'demo:set','disc-set-name':name,'disc-number':str(i+1),'launchable':'true','route-label':'Unknown runtime' if scenario=='unknown' or scenario=='mixed' and i==1 else 'RetroArch SwanStation'})
                g['lastPlayed']='2026-11-10T10:00:00Z' if i==1 and scenario!='nohistory' else ''
                g['missing']=scenario=='missing' and i==1
            games[2]['title']=name;games[2]['extra'].update({'edition-id':'demo:other-edition','system-id':'psx','launchable':'false'})
            games[3]['extra'].update({'edition-id':'demo:playlist','system-id':'psx','disc-alias-for':'demo:set'})
            (work/'demo/generated/games.js').write_text('.pragma library\nvar games = '+json.dumps(games)+';\n')
            demo=(ROOT/'demo/Demo.qml').read_text().replace('property var observedPlayDates: ({})','property var launches: []\n            property var observedPlayDates: ({})')
            demo=demo.replace('console.log("Synthetic demo has no launch route.");','api.allGames.launches.push(source.extra["edition-id"]);')
            (work/'demo/Demo.qml').write_text(demo.rsplit('}',1)[0]+(ROOT/'demo/discs/Smoke.qml.inc').read_text()+'}\n')
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
            done=subprocess.run([str(args.host),'--qml',str(work/'demo/Demo.qml'),'--store',str(args.bundle),'--output',str(out),'--scenario',scenario,'--width',str(width),'--height',str(height)]+flags,env=env,text=True,capture_output=True,timeout=25)
        log=done.stdout+done.stderr;(out/'log.txt').write_text(log)
        warnings=[line for line in log.splitlines() if any(s in line for s in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop'])]
        passed=done.returncode==0 and 'DISC_THEME_PASS '+scenario in log and not warnings
        results.append({'profile':profile,'scenario':scenario,'passed':passed,'code':done.returncode,'warnings':warnings})
        print(profile,scenario,'pass' if passed else 'FAIL',flush=True)
        if not passed:print(log[-3000:],flush=True)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n');return all(r['passed'] for r in results)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['host','bundle','output']:p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args()
    try:raise SystemExit(0 if run(a) else 1)
    except (OSError,ValueError,subprocess.TimeoutExpired):p.exit(1,'Disc verification did not complete; inspect partial evidence.\n')
