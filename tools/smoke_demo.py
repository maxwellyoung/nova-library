#!/usr/bin/env python3
"""Exercise the actual QML theme in an isolated synthetic offscreen demo."""
import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from make_demo import generate


def smoke(qml, imports):
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='nova-demo-smoke-') as temporary:
        isolated = Path(temporary)
        shutil.copytree(root / 'theme', isolated / 'theme', ignore=shutil.ignore_patterns('._*', '.DS_Store'))
        demo = isolated / 'demo'
        demo.mkdir()
        generate(demo / 'generated')
        source = (root / 'demo/Demo.qml').read_text()
        harness = (root / 'demo/Smoke.qml.inc').read_text()
        (demo / 'Demo.qml').write_text(source.rsplit('}', 1)[0] + harness + '}\n')
        env = os.environ.copy()
        env.update(QT_QPA_PLATFORM='offscreen', QT_QUICK_BACKEND='software')
        if imports:
            env['QML_IMPORT_PATH'] = os.pathsep.join(str(p) for p in imports)
            env['QML2_IMPORT_PATH'] = env['QML_IMPORT_PATH']
        result = subprocess.run([qml, str(demo / 'Demo.qml')], env=env, cwd=isolated,
                                capture_output=True, text=True, timeout=25)
        print(result.stdout, end='')
        print(result.stderr, end='')
        diagnostics = result.stdout + result.stderr
        if any(marker in diagnostics for marker in ['TypeError:', 'ReferenceError:', 'possible QQuickItem::polish() loop', 'depends on non-bindable properties']):
            raise RuntimeError('Synthetic QML smoke reported runtime errors')
        if result.returncode or 'NOVA_DEMO_SMOKE_PASS' not in diagnostics:
            raise RuntimeError('Synthetic QML smoke did not pass')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qml', default='qml', help='Path to the Qt QML runner')
    parser.add_argument('--import-path', type=Path, action='append', default=[], help='Optional Qt QML module directory; repeatable')
    args = parser.parse_args()
    try:
        smoke(args.qml, args.import_path)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f'{error}\n')
