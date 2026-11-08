#!/usr/bin/env python3
"""Exercise the full Nova theme against real local notebook storage. No device or games."""
import argparse,json,os,shutil,subprocess,tempfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0,str(ROOT/'tools'))
from make_demo import generate

def run(args):
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=False)
    store=output/'private-store'
    with tempfile.TemporaryDirectory(prefix='nova-notebook-theme-') as tmp:
        work=Path(tmp);shutil.copytree(ROOT/'theme',work/'theme',ignore=shutil.ignore_patterns('._*','.DS_Store'))
        p=work/'theme/Owner.js';p.write_text(p.read_text().replace('var bottomInsetPixels = 0;',f'var bottomInsetPixels = {args.inset};'))
        (work/'demo').mkdir();generate(work/'demo/generated')
        s=(ROOT/'demo/Demo.qml').read_text().replace('sans: Qt.application.font.family','sans: notebookFont.name || Qt.application.font.family')
        s=s.replace('return e.key === Qt.Key_Return || e.key === Qt.Key_Enter;','return e.key === Qt.Key_Return || e.key === Qt.Key_Enter || e.key === 0x100000;')
        s=s.replace('return e.key === Qt.Key_Escape;','return e.key === Qt.Key_Escape || e.key === 0x100001;')
        s=s.replace('return e.key === Qt.Key_X;','return e.key === Qt.Key_X || e.key === 0x100002;')
        s=s.replace('return "Enter";','return "A";').replace('return "Esc";','return "B";')
        (work/'demo/Demo.qml').write_text(s.rsplit('}',1)[0]+(ROOT/'demo/notebook/Smoke.qml.inc').read_text()+'}\n')
        inputs={str(f.relative_to(work)):hashlib.sha256(f.read_bytes()).hexdigest()for f in work.rglob('*')if f.is_file()}
        (output/'tested-inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
        env=dict(os.environ,QT_QUICK_BACKEND='software',QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM='1')
        results=[]
        for scenario in (['absent'] if args.absent else args.scenarios):
            if scenario=='missing':
                doc=store/hashlib.sha256(b'demo:orbit').hexdigest()/'notebook.json'
                book=json.loads(doc.read_text());note=next(n for n in book['notes'] if n['id']==book['stoppingNoteId'])
                source=doc.parent/'originals'/note['imageId'];source.rename(output/'retained-original-for-missing-test')
            if scenario=='corrupt':
                doc=store/hashlib.sha256(b'demo:orbit').hexdigest()/'notebook.json'
                shutil.copy2(doc,output/'retained-metadata-before-corrupt.json');doc.write_text('{synthetic invalid metadata')
            folder=output/scenario;folder.mkdir()
            cmd=[str(args.host),'--qml',str(work/'demo/Demo.qml'),'--store',str(store),'--output',str(folder),'--scenario',scenario,'--width',str(args.width),'--height',str(args.height)]
            if args.font:cmd+=['--font',str(args.font)]
            if args.light:cmd+=['--light']
            if args.large:cmd+=['--large']
            if args.absent:cmd+=['--bridge','absent']
            r=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True,timeout=30)
            log=r.stdout+r.stderr;(folder/'log.txt').write_text(log)
            bad=[line for line in log.splitlines() if any(t in line for t in ['QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop'])]
            passed=r.returncode==0 and f'NOTEBOOK_THEME_PASS {scenario}' in log and not bad
            results.append({'scenario':scenario,'passed':passed,'code':r.returncode,'warnings':bad})
            print(scenario,'pass' if passed else 'FAIL',flush=True)
            if not passed:print(log[-5000:]);break
        (output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
        return all(x['passed'] for x in results)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--font',type=Path);p.add_argument('--width',type=int,default=1280);p.add_argument('--height',type=int,default=960);p.add_argument('--inset',type=int,default=0);p.add_argument('--light',action='store_true');p.add_argument('--large',action='store_true');p.add_argument('--absent',action='store_true');p.add_argument('--scenarios',nargs='+',choices=['flow','reopen','failures','missing','corrupt','discs','legacy'],default=['flow','reopen','failures','missing','corrupt']);args=p.parse_args()
    raise SystemExit(0 if run(args) else 1)
