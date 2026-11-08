#!/usr/bin/env python3
"""Exercise the actual QML theme in an isolated synthetic offscreen demo."""
import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from make_demo import generate


def smoke(qml, imports, platform="offscreen", width=1280, height=800, screenshot=None, surface="cloud", appearance="dark", text_size="standard", bottom_inset=0):
    root = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory(prefix='nova-demo-smoke-') as temporary:
        isolated = Path(temporary)
        shutil.copytree(root / 'theme', isolated / 'theme', ignore=shutil.ignore_patterns('._*', '.DS_Store'))
        owner = isolated / 'theme/Owner.js'
        owner.write_text(owner.read_text().replace('var bottomInsetPixels = 0;', 'var bottomInsetPixels = '+str(bottom_inset)+';'))
        demo = isolated / 'demo'
        demo.mkdir()
        generate(demo / 'generated')
        source = (root / 'demo/Demo.qml').read_text().replace('width: 1280', 'width: '+str(width), 1).replace('height: 800', 'height: '+str(height), 1)
        harness = (root / 'demo/Smoke.qml.inc').read_text()
        harness = harness.replace('var ui=themeLoader.item;', 'var ui=themeLoader.item; ui.setAppearance("surface", '+json.dumps(appearance)+'); ui.setAppearance("size", '+json.dumps(text_size)+');', 1)
        if screenshot:
            harness = harness.replace('property string cloudScreenshotPath: ""', 'property string cloudScreenshotPath: '+json.dumps(str(screenshot.resolve())))
        harness = harness.replace('property string screenshotSurface: "cloud"', 'property string screenshotSurface: '+json.dumps(surface))
        (demo / 'Demo.qml').write_text(source.rsplit('}', 1)[0] + harness + '}\n')
        env = os.environ.copy()
        env.update(QT_QPA_PLATFORM=platform, QT_QUICK_BACKEND='software')
        if imports:
            env['QML_IMPORT_PATH'] = os.pathsep.join(str(p) for p in imports)
            env['QML2_IMPORT_PATH'] = env['QML_IMPORT_PATH']
        result = subprocess.run([qml, str(demo / 'Demo.qml')], env=env, cwd=isolated,
                                capture_output=True, text=True, timeout=25)
        print(result.stdout, end='')
        print(result.stderr, end='')
        diagnostics = result.stdout + result.stderr
        if any(marker in diagnostics for marker in ['Unable to assign', 'TypeError:', 'ReferenceError:', 'possible QQuickItem::polish() loop', 'depends on non-bindable properties']):
            raise RuntimeError('Synthetic QML smoke reported runtime errors')
        if result.returncode or 'NOVA_DEMO_SMOKE_PASS' not in diagnostics:
            raise RuntimeError('Synthetic QML smoke did not pass')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qml', default='qml', help='Path to the Qt QML runner')
    parser.add_argument('--import-path', type=Path, action='append', default=[], help='Optional Qt QML module directory; repeatable')
    parser.add_argument('--platform', choices=['offscreen', 'cocoa'], default='offscreen', help='Qt platform used by this isolated GUI check')
    parser.add_argument('--width', type=int, default=1280)
    parser.add_argument('--height', type=int, default=800)
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--surface', choices=['cloud', 'controls', 'checks', 'space', 'cleanup', 'aspect', 'home', 'session', 'session-filter', 'consoles', 'settings', 'collections', 'cloud-setup', 'last-check', 'library', 'details', 'apps', 'storage', 'collections-members', 'details-nine', 'emulator-details', 'storage-file', 'settings-absent', 'paused-status', 'cloud-library', 'cloud-install', 'cloud-details', 'cloud-home', 'phone-audio', 'download-resume', 'download-blocked', 'download-active', 'download-library'], default='cloud', help='Synthetic surface to capture after navigation checks')
    parser.add_argument('--appearance', choices=['dark','light'], default='dark')
    parser.add_argument('--text-size', choices=['standard','large'], default='standard')
    parser.add_argument('--bottom-inset', type=int, default=0, help='Synthetic measured bottom clearance in QML pixels')
    args = parser.parse_args()
    try:
        smoke(args.qml, args.import_path, args.platform, args.width, args.height, args.screenshot, args.surface, args.appearance, args.text_size, args.bottom_inset)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f'{error}\n')
