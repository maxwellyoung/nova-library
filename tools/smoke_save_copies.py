#!/usr/bin/env python3
"""Exercise the actual theme and read-only native bridge with synthetic bundles."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from make_demo import generate

PROFILES={'nova':(1280,960,0,[]),'light':(1280,960,0,['--light']),
          'large':(960,720,0,['--large']),'wide':(1280,720,0,[]),'inset':(1280,960,48,[])}

def run(args):
    if not args.host.is_file(): raise ValueError("Build the isolated save-copy host before running UI checks")
    args.output.mkdir(parents=True,exist_ok=False);results=[]
    jobs=[('nova','flow'),('light','flow'),('large','flow'),('wide','flow'),('inset','flow'),
          ('nova','absent'),('nova','partial'),('nova','empty'),('nova','missing'),('nova','corrupt'),('nova','focus')]
    jobs += [(profile,'shared-index') for profile in PROFILES]
    jobs += [('nova',scenario) for scenario in ('shared-directory','parent-alias','index-link','index-type')]
    jobs += [(profile,scenario) for profile in PROFILES for scenario in ('stale-review','legacy-review')]
    for profile,scenario in jobs:
        width,height,inset,flags=PROFILES[profile];out=args.output/(profile+'-'+scenario);out.mkdir()
        store=out/'store';shutil.copytree(args.bundle,store)
        if scenario=='shared-directory':store.chmod(0o750)
        elif scenario=='shared-index':(store/'catalogue.json').chmod(0o640)
        elif scenario=='parent-alias':
            alias=out/'alias';alias.symlink_to(out.resolve(),target_is_directory=True);store=alias/'store'
        elif scenario in ('index-link','index-type'):
            (store/'catalogue.json').rename(store/'retained-index')
            if scenario=='index-link':(store/'catalogue.json').symlink_to('retained-index')
            else:(store/'catalogue.json').mkdir()

        if scenario=='empty':
            index=json.loads((store/'catalogue.json').read_text());index['entries']=[]
            (store/'catalogue.json').write_text(json.dumps(index,sort_keys=True,separators=(',',':')))
        with tempfile.TemporaryDirectory(prefix='nova-save-copies-ui-') as temporary:
            work=Path(temporary);shutil.copytree(ROOT/'theme',work/'theme')
            p=work/'theme/Owner.js';p.write_text(p.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {inset};'))
            (work/'demo').mkdir();generate(work/'demo/generated');demo=(ROOT/'demo/Demo.qml').read_text()
            (work/'demo/Demo.qml').write_text(demo.rsplit('}',1)[0]+(ROOT/'demo/savecopies/Smoke.qml.inc').read_text()+'}\n')
            command=[str(args.host),'--qml',str(work/'demo/Demo.qml'),'--store',str(store),'--output',str(out),'--scenario',scenario,'--width',str(width),'--height',str(height)]+flags
            if scenario in ('absent','partial'):command+=['--bridge',scenario]
            if scenario=='legacy-review':command+=['--bridge','legacy']
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software')
            try:
                done=subprocess.run(command,env=env,capture_output=True,text=True,timeout=20);code=done.returncode;log=done.stdout+done.stderr
            except subprocess.TimeoutExpired:code=124;log='Synthetic save-copy UI timed out.'
        (out/'log.txt').write_text(log)
        warnings=[line for line in log.splitlines() if any(x in line for x in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop'])]
        passed=code==0 and ('SAVE_COPIES_THEME_PASS '+scenario) in log and not warnings
        results.append({'profile':profile,'scenario':scenario,'passed':passed,'code':code,'warnings':warnings})
        print(profile,scenario,'pass' if passed else 'FAIL',flush=True)
        if not passed:
            print(log[-3000:],flush=True)
            break
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n');return all(r['passed'] for r in results)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',required=True,type=Path);p.add_argument('--bundle',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();raise SystemExit(0 if run(a) else 1)
