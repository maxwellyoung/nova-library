#!/usr/bin/env python3
"""Run the real theme's restore-guidance paths with the existing isolated Qt host."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from make_demo import generate

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [('nova',1280,960,0,[]),('light',1280,960,0,['--light']),
            ('large',960,720,0,['--large']),('wide',1280,720,0,[]),('inset',1280,960,48,[])]

def run(args):
    if not args.host.is_file() or not args.bundle.is_dir():
        raise ValueError('Use the existing isolated theme host and a synthetic save-copy fixture')
    args.output.mkdir(parents=True,exist_ok=False)
    results=[]
    for name,width,height,inset,flags in PROFILES:
        out=args.output/name;out.mkdir()
        with tempfile.TemporaryDirectory(prefix='nova-restore-ui-') as temp:
            work=Path(temp);shutil.copytree(ROOT/'theme',work/'theme')
            owner=work/'theme/Owner.js';owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {inset};'))
            (work/'demo').mkdir();generate(work/'demo/generated')
            demo=(ROOT/'demo/Demo.qml').read_text()
            (work/'demo/Demo.qml').write_text(demo.rsplit('}',1)[0]+(ROOT/'demo/restore/Smoke.qml.inc').read_text()+'}\n')
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
            result=subprocess.run([str(args.host),'--qml',str(work/'demo/Demo.qml'),'--store',str(args.bundle),'--output',str(out),'--width',str(width),'--height',str(height)]+flags,env=env,capture_output=True,text=True,timeout=25)
        log=result.stdout+result.stderr;(out/'log.txt').write_text(log)
        warnings=[line for line in log.splitlines() if any(x in line for x in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop'])]
        passed=result.returncode==0 and 'RESTORE_GUIDE_PASS' in log and not warnings
        results.append({'profile':name,'passed':passed,'code':result.returncode,'warnings':warnings})
        print(name,'pass' if passed else 'FAIL',flush=True)
        if not passed:print(log[-2500:],flush=True)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    return all(r['passed'] for r in results)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['host','bundle','output']:parser.add_argument('--'+name,required=True,type=Path)
    args=parser.parse_args()
    try:raise SystemExit(0 if run(args) else 1)
    except (ValueError,OSError,subprocess.TimeoutExpired):parser.exit(1,'Restore guidance verification did not complete; inspect the partial evidence.\n')
