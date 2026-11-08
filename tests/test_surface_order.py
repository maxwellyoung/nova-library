"""Exercise the actual Java helper extracted from the pinned native patch."""
import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER = 'src/app/platform/android/src/org/pegasus_frontend/android/QtSurfaceOrder.java'


@unittest.skipUnless(shutil.which('javac') and shutil.which('java'),
                     'Surface policy checks require an installed JDK; no download attempted')
class SurfaceOrderTests(unittest.TestCase):
    def test_pinned_helper_lifecycle_and_accessibility_policy(self):
        pin = json.loads((ROOT / 'native/upstream.json').read_text())
        patch = ROOT / 'native' / pin['patch']
        self.assertEqual(hashlib.sha256(patch.read_bytes()).hexdigest(), pin['patchSha256'])
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            # This file is a complete new-file patch. Applying just that section
            # tests the shipped helper without maintaining a second source copy.
            result = subprocess.run(['git', 'apply', '--include=' + HELPER, str(patch)],
                                    cwd=work, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(result.returncode, 0, result.stdout)
            helper = work / HELPER
            self.assertEqual(hashlib.sha256(helper.read_bytes()).hexdigest(), pin['resultSha256'][HELPER])
            source = work / 'fixtures'
            shutil.copytree(ROOT / 'native/surfaceorder/tests/src', source)
            shutil.copyfile(helper, source / 'org/pegasus_frontend/android/QtSurfaceOrder.java')
            classes = work / 'classes'
            commands = [
                ['javac', '--release', '8', '-d', str(classes)]
                + [str(p) for p in sorted(source.rglob('*.java'))],
                ['java', '-cp', str(classes), 'org.pegasus_frontend.android.QtSurfaceOrderTest'],
            ]
            for command in commands:
                result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(result.returncode, 0, result.stdout)
            self.assertIn('39 surface-order lifecycle checks passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
