#!/usr/bin/env python3
"""Run the original Home presentation in a synthetic existing Qt host."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import zlib
from make_demo import generate

ROOT=Path(__file__).resolve().parents[1]
PROFILES=[('nova',1280,960,0,[]),('light',1280,960,0,['--light']),('large',960,720,0,['--large']),
          ('wide',1280,720,0,[]),('compact',960,544,0,[]),('inset',1280,960,48,[])]

def specimen(path,width,height,color):
    def chunk(kind,body):
        return struct.pack('>I',len(body))+kind+body+struct.pack('>I',zlib.crc32(kind+body)&0xffffffff)
    rows=b''.join(b'\0'+bytes(color if y<height*0.7 else tuple(min(255,c+35) for c in color))*width for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))

def run(args):
    if not args.host.is_file() or not args.bundle.is_dir():
        raise ValueError('Use the existing input-preferences host and a synthetic bundle')
    args.output.mkdir(parents=True,exist_ok=False);results=[]
    for name,width,height,inset,flags in PROFILES:
        out=args.output/name;out.mkdir()
        with tempfile.TemporaryDirectory(prefix='nova-home-shelf-') as temporary:
            work=Path(temporary);shutil.copytree(ROOT/'theme',work/'theme')
            (work/'demo/homeshelf').mkdir(parents=True);generate(work/'demo/generated')
            specimen(work/'demo/generated/art/square.png',480,480,(113,155,138))
            specimen(work/'demo/generated/art/wide.png',640,360,(136,115,166))
            source=(ROOT/'demo/homeshelf/Shelf.qml').read_text().replace('property int inset: 0',f'property int inset: {inset}')
            (work/'demo/homeshelf/Shelf.qml').write_text(source)
            done=subprocess.run([str(args.host),'--qml',str(work/'demo/homeshelf/Shelf.qml'),
                                 '--store',str(args.bundle),'--memory-dir',str(work/'memory'),'--output',str(out),
                                 '--width',str(width),'--height',str(height)]+flags,
                                env=dict(os.environ,QT_QPA_PLATFORM='offscreen',QT_QUICK_BACKEND='software'),
                                capture_output=True,text=True,timeout=25)
        log=done.stdout+done.stderr;(out/'log.txt').write_text(log)
        warnings=[line for line in log.splitlines() if any(x in line for x in ('QML_WARNING','TypeError','ReferenceError','Unable to assign','polish() loop'))]
        passed=done.returncode==0 and 'HOME_SHELF_PASS' in log and not warnings
        results.append({'profile':name,'passed':passed,'exitCode':done.returncode,'warnings':warnings})
        print(name,'pass' if passed else 'FAIL',flush=True)
        if not passed:print(log[-3000:],flush=True)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'theme').rglob('*')) if p.is_file()}
    for name in ('demo/homeshelf/Shelf.qml','tools/smoke_home_shelf.py'):
        manifest[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    (args.output/'source.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return all(item['passed'] for item in results)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('host','bundle','output'):parser.add_argument('--'+name,type=Path,required=True)
    try:raise SystemExit(0 if run(parser.parse_args()) else 1)
    except (ValueError,OSError,subprocess.TimeoutExpired):parser.exit(1,'Home shelf verification did not complete; inspect retained partial evidence.\n')
