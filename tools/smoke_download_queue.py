#!/usr/bin/env python3
"""Exercise the actual Downloads component without network, games or device input."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
PROFILES = [('nova',1280,960,0,[]),('light',1280,960,0,['--light']),
            ('large',960,720,0,['--large']),('wide',1280,720,0,[]),('inset',1280,960,48,[])]


def run(args):
    if not args.host.is_file() or not args.bundle.is_dir():
        raise ValueError('Use the existing isolated input-preferences Qt host and synthetic bundle')
    args.output.mkdir(parents=True, exist_ok=False)
    results=[]
    jobs=[(profile,scenario) for profile in PROFILES for scenario in args.scenarios]
    for (name,width,height,inset,flags),scenario in jobs:
        out=args.output/(name+'-'+scenario);out.mkdir()
        with tempfile.TemporaryDirectory(prefix='nova-download-queue-') as temporary:
            work=Path(temporary);shutil.copytree(ROOT/'theme',work/'theme')
            if args.before:shutil.copyfile(args.before,work/'theme/DownloadQueue.qml')
            source=work/'theme/DownloadQueue.qml';text=source.read_text()
            # Instrument the old source for the same row visibility assertions.
            if 'objectName:"queueRows"' not in text:
                source.write_text(text.replace('id:list;', 'id:list;objectName:"queueRows";',1))
            (work/'demo/downloadqueue').mkdir(parents=True)
            demo=(ROOT/'demo/downloadqueue/Queue.qml').read_text().replace('property int bottomInset: 0',f'property int bottomInset: {inset}')
            (work/'demo/downloadqueue/Queue.qml').write_text(demo)
            done=subprocess.run([str(args.host),'--qml',str(work/'demo/downloadqueue/Queue.qml'),
                                 '--store',str(args.bundle),'--memory-dir',str(work/'memory'),
                                 '--output',str(out),'--scenario',scenario,'--width',str(width),'--height',str(height)]+flags,
                                env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software'),
                                capture_output=True,text=True,timeout=20)
        log=done.stdout+done.stderr;(out/'log.txt').write_text(log)
        warnings=[line for line in log.splitlines() if any(marker in line for marker in
                   ('QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop'))]
        passed=done.returncode==0 and 'DOWNLOAD_QUEUE_PASS '+scenario in log and not warnings
        results.append({'profile':name,'scenario':scenario,'passed':passed,'exitCode':done.returncode,'warnings':warnings})
        print(name,scenario,'pass' if passed else 'FAIL',flush=True)
        if not passed:print(log[-2000:],flush=True)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    source={str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [ROOT/'theme/DownloadQueue.qml',ROOT/'demo/downloadqueue/Queue.qml',Path(__file__)]}
    source['executedQueueSha256']=hashlib.sha256((args.before or ROOT/'theme/DownloadQueue.qml').read_bytes()).hexdigest()
    source['queueOrigin']='before' if args.before else 'current'
    (args.output/'source.json').write_text(json.dumps(source,indent=2)+'\n')
    return all(result['passed'] for result in results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('host','bundle','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--before',type=Path)
    parser.add_argument('--scenarios',nargs='+',choices=('layout','continuity','actions','pointer'),default=['layout','continuity','actions','pointer'])
    args=parser.parse_args()
    try:raise SystemExit(0 if run(args) else 1)
    except (ValueError,OSError,subprocess.TimeoutExpired):parser.exit(1,'Downloads verification did not complete; preserve and inspect partial evidence.\n')
