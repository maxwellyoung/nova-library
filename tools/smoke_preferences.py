#!/usr/bin/env python3
"""Exercise favourite/session/appearance commits with the actual native store."""
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
    seed = {'pins': ['demo:garden'], 'sessionWindows': {'version': 1, 'labels': {'demo:garden': 'evening'}},
            'theme': {'surface': 'dark', 'size': 'standard', 'time': False, 'motion': False}, 'unrelated': 'keep'}
    jobs = [(p, 'flow') for p in PROFILES] + [(PROFILES[0], s) for s in ('reopen', 'corrupt', 'bad-pins', 'launch-refusal')]
    if getattr(args, 'scenario', None):
        jobs = [job for job in jobs if job[1] == args.scenario]
    if args.before:
        jobs = jobs[:1]
    for (profile, width, height, inset, flags), scenario in jobs:
        out = args.output / (profile + '-' + scenario)
        out.mkdir()
        memory = out / 'memory'
        memory.mkdir()
        if scenario == 'reopen':
            shutil.copyfile(args.output / 'nova-flow/committed.json', memory / 'nova.json')
        else:
            values = json.loads(json.dumps(seed))
            values['theme']['surface'] = 'light' if '--light' in flags else 'dark'
            values['theme']['size'] = 'large' if '--large' in flags else 'standard'
            if scenario == 'bad-pins': values['pins'] = {'invalid': 'shape'}
            (memory / 'nova.json').write_text('{broken' if scenario == 'corrupt' else json.dumps(values))
        with tempfile.TemporaryDirectory(prefix='nova-preferences-ui-') as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / 'theme', work / 'theme')
            if args.before:
                shutil.copyfile(args.before, work / 'theme/theme.qml')
            owner = work / 'theme/Owner.js'
            owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;', f'var bottomInsetPixels = {inset};'))
            (work / 'demo').mkdir()
            generate(work / 'demo/generated')
            demo = (ROOT / 'demo/Demo.qml').read_text()
            start = demo.index('        property QtObject memory: QtObject {')
            end = demo.index('        property QtObject keys:', start)
            demo = demo[:start] + '        property QtObject memory: checkedMemory\n' + demo[end:]
            demo = demo.replace('property var deviceLibrary: null', '''property int pinActions: 0
    property int romStages: 0
    property QtObject deviceLibrary: QtObject {
        signal changed()
        function read(){return {};}
        function act(action){if(action.type==="pin")window.pinActions++;return {};}
        function recordRomLaunch(edition,title,system){window.romStages++;}
    }''')
            (work / 'demo/Demo.qml').write_text(demo.rsplit('}', 1)[0] + (ROOT / 'demo/preferences/Smoke.qml.inc').read_text() + '}\n')
            command = [str(args.host), '--qml', str(work / 'demo/Demo.qml'), '--memory-dir', str(memory),
                       '--store', str(args.bundle), '--output', str(out), '--scenario', scenario,
                       '--width', str(width), '--height', str(height)] + flags
            done = subprocess.run(command, env=dict(os.environ, QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software'),
                                  capture_output=True, text=True, timeout=30)
        log = done.stdout + done.stderr
        (out / 'log.txt').write_text(log)
        warnings = [s for s in log.splitlines() if any(t in s for t in ('QML_WARNING', 'TypeError', 'ReferenceError', 'Unable to assign', 'polish() loop'))]
        passed = done.returncode == 0 and 'PREFERENCES_THEME_PASS ' + scenario in log and not warnings
        results.append({'profile': profile, 'scenario': scenario, 'passed': passed, 'code': done.returncode, 'warnings': warnings})
        print(profile, scenario, 'pass' if passed else 'FAIL', flush=True)
        if not passed:
            print(log[-3500:], flush=True)
            break
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    return len(results) == len(jobs) and all(r['passed'] for r in results)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('host', 'bundle', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--scenario', choices=('flow', 'reopen', 'corrupt', 'bad-pins', 'launch-refusal'))
    parser.add_argument('--before', type=Path, help='Retained theme for one negative control')
    raise SystemExit(0 if run(parser.parse_args()) else 1)
