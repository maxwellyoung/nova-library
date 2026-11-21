#!/usr/bin/env python3
"""Run the real Home choice panel with synthetic routes and injected input."""
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
    args.output.mkdir(parents=True, exist_ok=False)
    results = []
    jobs = [(p, 'flow') for p in PROFILES] + [(PROFILES[0], s) for s in ('empty', 'fewer', 'discs')] + [(PROFILES[2], 'long')]
    for (profile, width, height, inset, flags), scenario in jobs:
        out = args.output / (profile + '-' + scenario)
        out.mkdir()
        with tempfile.TemporaryDirectory(prefix='nova-choices-ui-') as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / 'theme', work / 'theme')
            owner = work / 'theme/Owner.js'
            owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;', f'var bottomInsetPixels = {inset};'))
            (work / 'demo').mkdir()
            generate(work / 'demo/generated')
            demo = (ROOT / 'demo/Demo.qml').read_text().replace('import QtQuick 2.15', 'import QtQuick 2.15\nimport "../theme/library.js" as ChoicesFixture', 1)
            (work / 'demo/Demo.qml').write_text(demo.rsplit('}', 1)[0] + (ROOT / 'demo/choices/Smoke.qml.inc').read_text() + '}\n')
            command = [str(args.host), '--qml', str(work / 'demo/Demo.qml'), '--memory-dir', str(out / 'unused-native-memory'),
                       '--store', str(args.bundle), '--output', str(out), '--scenario', scenario,
                       '--width', str(width), '--height', str(height)] + flags
            done = subprocess.run(command, env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software'),
                                  capture_output=True, text=True, timeout=30)
        log = done.stdout + done.stderr
        (out / 'log.txt').write_text(log)
        warnings = [s for s in log.splitlines() if any(t in s for t in ('QML_WARNING', 'TypeError', 'ReferenceError', 'Unable to assign', 'polish() loop'))]
        passed = done.returncode == 0 and 'CHOICES_THEME_PASS ' + scenario in log and not warnings
        results.append({'profile': profile, 'scenario': scenario, 'passed': passed, 'code': done.returncode, 'warnings': warnings})
        print(profile, scenario, 'pass' if passed else 'FAIL', flush=True)
        if not passed:
            print(log[-4000:], flush=True)
            break
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return len(results) == len(jobs) and all(r['passed'] for r in results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'bundle', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    raise SystemExit(0 if run(parser.parse_args()) else 1)
