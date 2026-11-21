#!/usr/bin/env python3
"""Capture checked native saves as private passports; never launch or restore apps."""
import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import stat
import subprocess
import tempfile

if __package__:
    from . import save_passport as passport
else:
    import save_passport as passport

MAX_FILE_BYTES = 4 * 1024 * 1024


class CaptureError(ValueError):
    """Path-free operator diagnostic."""


def require(value, message):
    if not value:
        raise CaptureError(message)


@dataclass(frozen=True)
class Profile:
    package: str
    apk_sha256: str
    edition: str
    recipe: str
    runtime: str
    version: str
    source: str
    files: tuple
    data_checks: tuple

    def identity(self):
        return {'editionId': self.edition, 'recipeId': self.recipe, 'kind': 'native-save',
                'runtime': {'name': self.runtime, 'version': self.version,
                            'core': 'Native Android port; no emulator core'}}


# These are the specific native slots exercised on Nova, not directory globs.
# Adding a runtime/slot requires an actual save and recovery check first.
PROFILES = {
    'soh-nova-slot1': Profile(
        'com.linkzenic.soh',
        '99f215007984b06adf0758256d044599f2079825af5e142b1c967215bd6bd267',
        'native:com.linkzenic.soh:oot-us12', 'save-soh-us12-9.3.1-slot1-v1',
        'Ship of Harkinian Android', '9.3.1-android.4', '/storage/emulated/0/SOH',
        ('Save/file1.sav', 'Save/global.sav'),
        (('oot.o2r', '9d750a0463aa224442290e50fdbef2e5474bd3923af13ce5833307a50822211e'),
         ('soh.o2r', 'd5abfa83d2806edd50f897338145fecbc087f1ad04f6182eb7ad715828a0d2a1'))),
    'diablo-shareware-hero0': Profile(
        'org.diasurgical.devilutionx',
        'c5a53ff35223e367eba75ef8ed2caa31ea8e78792d8aff00f2cee51a0566b28f',
        'native:org.diasurgical.devilutionx:shareware', 'save-devilutionx-1.5.5-shareware-hero0-v1',
        'DevilutionX Android', '1.5.5',
        '/storage/emulated/0/Android/data/org.diasurgical.devilutionx/files',
        ('spawn_0.sv',),
        (('spawn.mpq', '64427cd7c1ba904eaa2e0031c16a6b136d0ecef9abc888c5ff8344b459356e38'),
         ('devilutionx.mpq', '190701ca282fef8fa8b3f165322760813d6b199462bb4e2587a20068c08accd3'))),
}


class Adb:
    def __init__(self, serial):
        require(isinstance(serial, str) and re.fullmatch(r'[A-Za-z0-9_.:-]{1,160}', serial),
                'Select an explicit valid device serial')
        self.command = ['adb', '-s', serial]

    def _run(self, *args, allowed=(0,)):
        try:
            result = subprocess.run(self.command + list(args), capture_output=True, timeout=20)
        except (OSError, subprocess.TimeoutExpired):
            raise CaptureError('Device read unavailable or timed out; no backup published') from None
        require(result.returncode in allowed, 'Device read failed; no backup published')
        return result

    def _shell(self, *args, allowed=(0,)):
        return self._run('shell', shlex.join(args), allowed=allowed)

    def idle(self, package):
        result = self._shell('pidof', package, allowed=(0, 1))
        require(result.returncode == 1 and not result.stdout.strip(),
                'Close the native game normally before capturing its saves')

    def apk(self, package):
        lines = self._shell('pm', 'path', package).stdout.decode('utf-8').splitlines()
        require(len(lines) == 1 and lines[0].startswith('package:'),
                'Installed native package is missing or uses an unsupported split layout')
        path = lines[0][8:]
        require(path.startswith('/data/app/') and path.endswith('/base.apk')
                and '..' not in PurePosixPath(path).parts and not re.search(r'[\x00-\x20]', path),
                'Installed native package path is unsupported')
        return self._digest(path)

    def _digest(self, path):
        values = self._shell('sha256sum', path).stdout.decode('utf-8').split()
        require(values and re.fullmatch('[0-9a-f]{64}', values[0]),
                'Device checksum is unavailable')
        return values[0]

    def data_digest(self, path):
        canonical = self._shell('readlink', '-f', path).stdout.decode('utf-8').strip()
        require(canonical == path, 'Linked game data needs a separately verified adapter')
        return self._digest(path)

    def snapshot(self, path):
        # The fixed source roots use the canonical Android path, not /sdcard.
        # Refuse links in the selected file or an ancestor below that root.
        canonical = self._shell('readlink', '-f', path).stdout.decode('utf-8').strip()
        require(canonical == path, 'Linked save sources need a separately verified adapter')
        raw = self._shell('stat', '-c', '%F:%s:%i:%Y', path).stdout.decode('utf-8').strip()
        values = raw.split(':')
        require(len(values) == 4 and values[0] == 'regular file'
                and all(re.fullmatch('[0-9]+', item) for item in values[1:]),
                'Native save source is not an ordinary readable file')
        size, inode, modified = map(int, values[1:])
        require(0 < size <= MAX_FILE_BYTES, 'Native save is empty or exceeds this adapter limit')
        return (size, inode, modified, self._digest(path))

    def read(self, path):
        # Bound output even if an idle/source observation becomes stale.
        return self._run('exec-out', 'head', '-c', str(MAX_FILE_BYTES + 1), path).stdout


def profile(name):
    require(isinstance(name, str) and name in PROFILES,
            'Unsupported native save profile; no paths were inferred')
    return PROFILES[name]


def observe(device, selected):
    device.idle(selected.package)
    require(device.apk(selected.package) == selected.apk_sha256,
            'Installed APK differs from the checked native save profile')
    for name, expected in selected.data_checks:
        require(device.data_digest(selected.source + '/' + name) == expected,
                'Game data differs from the checked native save profile')
    files = {name: device.snapshot(selected.source + '/' + name) for name in selected.files}
    device.idle(selected.package)
    return files


def inspect(device, name):
    selected = profile(name)
    files = observe(device, selected)
    return {'profile': name, 'identity': selected.identity(), 'files': len(files),
            'bytes': sum(value[0] for value in files.values()), 'pinnedApkMatch': True,
            'pinnedGameDataMatch': True, 'idleObserved': True,
            'captureState': 'observation-only; not a runtime lock'}


def private_output(output):
    output = Path(output).absolute()
    parent = passport.directory(output.parent)
    require(stat.S_IMODE(parent.stat().st_mode) & 0o077 == 0,
            'Choose an owner-only output directory')
    repo = Path(__file__).resolve().parents[1]
    require(parent != repo and repo not in parent.parents
            and not any((p / '.git').exists() for p in (parent, *parent.parents)),
            'Private native backups must stay outside repositories')
    require(not output.exists() and not output.is_symlink(),
            'Backup output already exists; it was not changed')
    return output


def capture(device, name, output, *, confirm_idle=False):
    require(confirm_idle is True, 'Confirm the native game was closed normally before capture')
    selected = profile(name)
    output = private_output(output)
    before = observe(device, selected)
    with tempfile.TemporaryDirectory(prefix='.native-save-', dir=output.parent) as temporary:
        temporary = Path(temporary)
        source = temporary / 'source'
        source.mkdir(mode=0o700)
        for name in selected.files:
            data = device.read(selected.source + '/' + name)
            require(len(data) == before[name][0] and len(data) <= MAX_FILE_BYTES
                    and hashlib.sha256(data).hexdigest() == before[name][3],
                    'Native save changed during capture; no backup published')
            target = source / name
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with target.open('xb') as stream:
                os.chmod(target, 0o600)
                stream.write(data)
        candidate = temporary / 'checkpoint.nvs'
        selection = {'schemaVersion': 1, **selected.identity(), 'files': list(selected.files)}
        manifest = passport.pack(source, selection, candidate, source_idle=True)
        require(observe(device, selected) == before,
                'Native app or saves changed before publication; no backup published')
        passport.verify(candidate)
        # No replacement window: a competing writer's destination wins intact.
        os.link(candidate, output)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'capture'])
    parser.add_argument('--profile', required=True, choices=sorted(PROFILES))
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--confirm-closed', action='store_true')
    args = parser.parse_args()
    try:
        device = Adb(args.serial)
        if args.command == 'inspect':
            require(args.output is None, 'Inspection does not create output files')
            result = inspect(device, args.profile)
            print(f"Native profile checked: {result['files']} save file(s), {result['bytes']} bytes; idle observed.")
        else:
            require(args.output is not None, 'Choose a new private backup file')
            result = capture(device, args.profile, args.output, confirm_idle=args.confirm_closed)
            print(f"Native passport verified: {len(result['files'])} save file(s). No live saves changed.")
    except (CaptureError, passport.PassportError) as error:
        print(str(error), file=__import__('sys').stderr)
        return 1
    except (OSError, UnicodeError):
        print('Native backup unavailable; existing outputs and live saves were kept.',
              file=__import__('sys').stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
