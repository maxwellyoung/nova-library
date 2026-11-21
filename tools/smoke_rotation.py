#!/usr/bin/env python3
"""Exercise offline rotation preferences and the real theme using an existing Qt host."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from make_demo import generate
from smoke_offline import PROFILES

ROOT=Path(__file__).resolve().parents[1]


def run(args):
    if not args.host.is_file() or not args.bundle.is_dir():
        raise ValueError('Use the existing isolated host and a synthetic bundle')
    args.output.mkdir(parents=True,exist_ok=False)
    results=[]
    saved=None
    jobs=[(p,'flow') for p in PROFILES]+[(PROFILES[0],'reopen'),(PROFILES[0],'corrupt'),(PROFILES[0],'readrefusal'),(PROFILES[0],'missing'),(PROFILES[2],'full'),(PROFILES[2],'long')]
    if args.scenario:jobs=[job for job in jobs if job[1]==args.scenario or args.scenario=='reopen' and job[1]=='flow' and job[0][0]=='nova']
    for (profile,width,height,inset,flags),scenario in jobs:
        out=args.output/(profile+'-'+scenario);out.mkdir()
        seed=None
        if scenario=='reopen':
            if saved is None:raise ValueError('No completed preference roundtrip to reopen')
            seed=saved
        elif scenario=='corrupt':seed={'version':99,'editions':[]}
        elif scenario=='readrefusal':seed={'version':1,'editions':[]}
        elif scenario=='long':seed={'version':1,'editions':[{'id':'demo:long','title':'An archived edition with a very long title, its regional subtitle and a distinct revision kept for a different playthrough, without confusing this one with another edition of the same game'},{'id':'demo:orbit','title':'Amber Orbit'}]}
        elif scenario=='missing':seed={'version':1,'editions':[{'id':'demo:absent','title':'Absent edition'},{'id':'demo:orbit','title':'Amber Orbit'}]}
        elif scenario=='full':seed={'version':1,'editions':[{'id':f'demo:slot{i}','title':f'Chosen game {i+1}'} for i in range(12)]}
        with tempfile.TemporaryDirectory(prefix='nova-rotation-ui-') as temp:
            work=Path(temp);shutil.copytree(ROOT/'theme',work/'theme')
            owner=work/'theme/Owner.js';owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {inset};'))
            (work/'demo').mkdir();generate(work/'demo/generated')
            demo=(ROOT/'demo/Demo.qml').read_text()
            if seed is not None:demo=demo.replace('property var values: ({})','property var values: ('+json.dumps({'rotationV1':seed})+')')
            if scenario=='readrefusal':demo=demo.replace('function get(key) { return values[key]; }','function get(key) { if(key==="rotationV1")throw new Error("Synthetic rotation read refusal");return values[key]; }')
            (work/'demo/Demo.qml').write_text(demo.rsplit('}',1)[0]+(ROOT/'demo/rotation/Smoke.qml.inc').read_text()+'}\n')
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
            done=subprocess.run([str(args.host),'--qml',str(work/'demo/Demo.qml'),'--store',str(args.bundle),'--output',str(out),'--scenario',scenario,'--width',str(width),'--height',str(height)]+flags,env=env,capture_output=True,text=True,timeout=25)
        log=done.stdout+done.stderr;(out/'log.txt').write_text(log)
        warnings=[line for line in log.splitlines() if any(x in line for x in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop','Synthetic demo has no launch route'])]
        passed=done.returncode==0 and 'ROTATION_THEME_PASS '+scenario in log and not warnings
        if passed and scenario=='flow':
            lines=[line.split('ROTATION_SAVED ',1)[1] for line in log.splitlines() if 'ROTATION_SAVED ' in line]
            if len(lines)!=1:passed=False
            else:saved=json.loads(lines[0])
        results.append({'profile':profile,'scenario':scenario,'passed':passed,'code':done.returncode,'warnings':warnings})
        print(profile,scenario,'pass' if passed else 'FAIL',flush=True)
        if not passed:print(log[-3500:],flush=True)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    return all(r['passed'] for r in results)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['host','bundle','output']:parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--scenario',choices=['flow','reopen','corrupt','readrefusal','missing','full','long'])
    args=parser.parse_args()
    try:raise SystemExit(0 if run(args) else 1)
    except (ValueError,OSError,subprocess.TimeoutExpired):parser.exit(1,'Rotation verification did not complete; inspect partial evidence.\n')
