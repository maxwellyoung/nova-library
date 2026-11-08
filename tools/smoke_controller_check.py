#!/usr/bin/env python3
"""Run theme/ControllerCheck.qml scenarios in the isolated desktop host. Nothing launches or attaches a device.

Build demo/controllercheck/host.pro with a Qt 5.15 toolchain first and pass that binary as --host.
Each job is profile:scenario[:bridge[:kb]]; injected data stays labelled in the report and on screen.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from make_demo import generate  # noqa: E402

PROFILES = {
    'n0': (1280, 960, 0, []), 'n48': (1280, 960, 48, []),
    'light48': (1280, 960, 48, ['--light']), 'light0': (1280, 960, 0, ['--light']),
    'large': (960, 720, 0, ['--large']), 'lightlarge': (960, 720, 0, ['--light', '--large']),
    'wide': (1280, 720, 0, []), 'largewide': (1280, 720, 0, ['--large']),
}
DEFAULT_JOBS = ['n0:flow', 'n48:flow', 'light48:flow', 'large:flow', 'lightlarge:flow', 'wide:flow', 'largewide:flow',
                'n48:order', 'n48:nodevice', 'n48:missing', 'wide:missing', 'n48:multi', 'large:multi',
                'n48:absent:absent', 'n48:absent:partial', 'n48:unconfigured:unconfigured', 'n48:ready:model:kb',
                'n0:settingsback', 'n48:reviewfocus']
BAD = ('QML_WARNING', 'TypeError', 'ReferenceError', 'Unable to assign', 'polish() loop', 'depends on non-bindable')


def run(host, output, jobs, font, timeout):
    results = []
    for job in jobs:
        parts = job.split(':')
        profile, scenario = parts[0], parts[1]
        bridge = parts[2] if len(parts) > 2 else 'model'
        keyboard = len(parts) > 3
        width, height, inset, flags = PROFILES[profile]
        folder = output / job.replace(':', '-')
        folder.mkdir(parents=True, exist_ok=False)
        with tempfile.TemporaryDirectory(prefix='nova-controller-ui-') as temporary:
            work = Path(temporary)
            shutil.copytree(ROOT / 'theme', work / 'theme', ignore=shutil.ignore_patterns('._*', '.DS_Store'))
            owner = work / 'theme/Owner.js'
            owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;', f'var bottomInsetPixels = {inset};'))
            (work / 'demo').mkdir()
            generate(work / 'demo/generated')
            shutil.copy2(ROOT / 'demo/ControllerCheckDemo.qml', work / 'demo/ControllerCheckDemo.qml')
            env = dict(os.environ, QT_QUICK_BACKEND='software', QT_MAC_DISABLE_FOREGROUND_APPLICATION_TRANSFORM='1')
            command = [str(host), '--qml', str(work / 'demo/ControllerCheckDemo.qml'), '--output', str(folder),
                       '--scenario', scenario, '--width', str(width), '--height', str(height), '--bridge', bridge]
            command += flags + (['--font', str(font)] if font else []) + (['--keyboard-labels'] if keyboard else [])
            started = time.time()
            try:
                done = subprocess.run(command, env=env, cwd=work, capture_output=True, text=True, timeout=timeout)
                code, log = done.returncode, done.stdout + done.stderr
            except subprocess.TimeoutExpired as error:
                code, log = 124, str(error.stdout or '') + str(error.stderr or '')
        (folder / 'log.txt').write_text(log)
        warnings = [line for line in log.splitlines() if any(mark in line for mark in BAD)]
        passed = code == 0 and f'CONTROLLER_FIXTURE_PASS {scenario}' in log and not warnings
        results.append({'job': job, 'passed': passed, 'code': code, 'seconds': round(time.time() - started, 1),
                        'warnings': warnings[:8], 'images': sorted(p.name for p in folder.glob('*.png'))})
        print(job, 'pass' if passed else f'FAIL code={code}', flush=True)
        if not passed:
            print(log[-1500:], flush=True)
    (output / 'results.json').write_text(json.dumps(results, indent=1) + '\n')
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True, help='Built controller-check-theme-host binary')
    parser.add_argument('--output', type=Path, required=True, help='New folder for images and logs')
    parser.add_argument('--font', type=Path, help='Optional review font file')
    parser.add_argument('--timeout', type=int, default=90)
    parser.add_argument('jobs', nargs='*', default=DEFAULT_JOBS)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    outcome = run(args.host, args.output, args.jobs, args.font, args.timeout)
    failed = [row['job'] for row in outcome if not row['passed']]
    print(f'{len(outcome) - len(failed)} of {len(outcome)} passed')
    sys.exit(1 if failed else 0)
