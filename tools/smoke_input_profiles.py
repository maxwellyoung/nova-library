#!/usr/bin/env python3
"""Real-theme profile flow using the isolated checked native Memory implementation."""
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
    args.output.mkdir(parents=True,exist_ok=False);results=[]
    for profile,width,height,inset,flags in PROFILES:
        for scenario in ['flow','reopen','corrupt','future','unlinked'] if profile=='nova' else ['flow']:
            out=args.output/(profile+'-'+scenario);out.mkdir();memory=out/'memory';memory.mkdir()
            # Reopen is a new process with the exact committed file, not mock QML memory.
            if scenario=='reopen':
                # The flow's exact committed JSON is saved before its deliberate external edit.
                committed=args.output/'nova-flow/committed.json'
                if not committed.is_file():raise ValueError('Flow did not retain the committed file')
                shutil.copyfile(committed,memory/'nova.json')
            elif scenario=='corrupt':(memory/'nova.json').write_text('{broken')
            elif scenario=='future':(memory/'nova.json').write_text(json.dumps({'inputProfilesV1':{'version':99,'profiles':[]}}))
            with tempfile.TemporaryDirectory(prefix='nova-profile-ui-') as temp:
                work=Path(temp);shutil.copytree(ROOT/'theme',work/'theme');(work/'demo').mkdir();generate(work/'demo/generated')
                owner=work/'theme/Owner.js';owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {inset};'))
                demo=(ROOT/'demo/Demo.qml').read_text();start=demo.index('        property QtObject memory: QtObject {');end=demo.index('        property QtObject keys:',start)
                demo=demo[:start]+'        property QtObject memory: checkedMemory\n'+demo[end:]
                demo=demo.replace('import QtQuick 2.15','import QtQuick 2.15\nimport "../theme/InputProfiles.js" as ProfilesFixture',1)
                (work/'demo/Demo.qml').write_text(demo.rsplit('}',1)[0]+(ROOT/'demo/inputprofiles/Smoke.qml.inc').read_text()+'}\n')
                done=subprocess.run([str(args.host),'--qml',str(work/'demo/Demo.qml'),'--memory-dir',str(memory),'--store',str(args.bundle),'--output',str(out),'--scenario',scenario,'--width',str(width),'--height',str(height)]+flags,env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software'),capture_output=True,text=True,timeout=40)
            log=done.stdout+done.stderr;(out/'log.txt').write_text(log)
            warnings=[line for line in log.splitlines() if any(s in line for s in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop'])]
            passed=done.returncode==0 and 'INPUT_PROFILE_THEME_PASS '+scenario in log and not warnings
            results.append({'profile':profile,'scenario':scenario,'passed':passed,'code':done.returncode,'warnings':warnings});print(profile,scenario,'pass' if passed else 'FAIL',flush=True)
            if not passed:print(log[-3000:],flush=True)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n');return all(r['passed'] for r in results)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['host','bundle','output']:p.add_argument('--'+name,type=Path,required=True)
    args=p.parse_args()
    try:raise SystemExit(0 if run(args) else 1)
    except (ValueError,OSError,subprocess.TimeoutExpired) as e:p.exit(1,'Profile fixture did not finish: '+str(e)+'\n')
