#!/usr/bin/env python3
"""Exercise exact collection-member focus across real QML theme recreation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from make_demo import generate
from smoke_offline import PROFILES

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    if not args.host.is_file() or not args.bundle.is_dir():
        raise ValueError('Use the existing isolated Qt host and synthetic bundle')
    args.output.mkdir(parents=True, exist_ok=False)
    jobs = [(profile, 'flow') for profile in PROFILES]
    jobs += [(PROFILES[0], scenario) for scenario in ('reordered', 'missing', 'other-collection', 'legacy', 'list', 'library-search')]
    if args.before:
        jobs = jobs[:1]
    seed = {'rotationV1': {'version': 1, 'editions': [
        {'id': 'demo:garden', 'title': 'The Moss Garden'}, {'id': 'demo:orbit', 'title': 'Amber Orbit'}]}}
    results = []
    for (profile, width, height, inset, flags), scenario in jobs:
        out = args.output / (profile + '-' + scenario)
        out.mkdir()
        with tempfile.TemporaryDirectory(prefix='nova-focus-ui-') as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / 'theme', work / 'theme')
            if args.before:
                shutil.copyfile(args.before, work / 'theme/theme.qml')
            owner = work / 'theme/Owner.js'
            owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;', f'var bottomInsetPixels = {inset};'))
            (work / 'demo').mkdir()
            generate(work / 'demo/generated')
            demo = (ROOT / 'demo/Demo.qml').read_text().replace('property var values: ({})', 'property var values: (' + json.dumps(seed) + ')')
            (work / 'demo/Demo.qml').write_text(demo.rsplit('}', 1)[0] + (ROOT / 'demo/focus/Smoke.qml.inc').read_text() + '}\n')
            done = subprocess.run([str(args.host), '--qml', str(work / 'demo/Demo.qml'), '--store', str(args.bundle),
                                   '--output', str(out), '--scenario', scenario, '--width', str(width), '--height', str(height)] + flags,
                                  env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software'),
                                  capture_output=True, text=True, timeout=25)
        log = done.stdout + done.stderr
        (out / 'log.txt').write_text(log)
        warnings = [line for line in log.splitlines() if any(x in line for x in ('QML_WARNING', 'TypeError', 'ReferenceError', 'Unable to assign', 'polish() loop'))]
        passed = done.returncode == 0 and 'FOCUS_THEME_PASS ' + scenario in log and not warnings
        results.append({'profile': profile, 'scenario': scenario, 'passed': passed, 'exitCode': done.returncode, 'warnings': warnings})
        print(profile, scenario, 'pass' if passed else 'FAIL', flush=True)
        if not passed:
            print(log[-3000:], flush=True)
            break
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return len(results) == len(jobs) and all(r['passed'] for r in results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'bundle', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--before', type=Path, help='Retained theme for the negative control')
    raise SystemExit(0 if run(parser.parse_args()) else 1)
