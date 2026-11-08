#!/usr/bin/env python3
"""Build a paired-source arm64 Qt 5 Android review APK, using provisioned tools.

No downloads, installation, service access or release signing. The resulting
debug APK is not a device update: optional private integrations are absent.
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import zipfile
from pathlib import Path
from urllib.parse import urlparse

from prepare_native import verify


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def gradle_properties(heap_mib=None):
    properties = 'org.gradle.daemon=false\norg.gradle.workers.max=2\n'
    if heap_mib is not None:
        if type(heap_mib) is not int or not 512 <= heap_mib <= 8192:
            raise ValueError('Gradle heap must be an integer from 512 to 8192 MiB')
        properties += ('org.gradle.jvmargs=-Xmx' + str(heap_mib)
                       + 'm -XX:MaxMetaspaceSize=512m\n')
    return properties


def cached_gradle(cache, template):
    """Fail before invoking the wrapper if its distribution would be downloaded."""
    props = dict(line.split('=', 1) for line in template.read_text().splitlines()
                 if '=' in line and not line.startswith('#'))
    url = props.get('distributionUrl', '').replace('\\:', ':')
    name = Path(urlparse(url).path).name
    if not re.fullmatch(r'gradle-[0-9][A-Za-z0-9.\-]*-(?:bin|all)\.zip', name):
        raise ValueError('Unsupported Gradle wrapper distribution')
    number = int.from_bytes(hashlib.md5(url.encode()).digest(), 'big')
    digits = ''
    while number:
        number, digit = divmod(number, 36)
        digits = '0123456789abcdefghijklmnopqrstuvwxyz'[digit] + digits
    directory = cache / 'wrapper/dists' / name[:-4] / (digits or '0')
    version = name[7:].rsplit('-', 1)[0]
    executable = directory / ('gradle-' + version) / 'bin/gradle'
    if not executable.is_file() or not (directory / (name + '.ok')).is_file():
        raise ValueError('Gradle wrapper distribution is not provisioned; no download attempted')
    return executable


def runtime_sections(data):
    if data[:6] != b'\x7fELF\x02\x01' or len(data) < 64:
        raise ValueError('Expected a little-endian ELF64 library')
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    offset, size, count, names_index = header[6], header[11], header[12], header[13]
    if size != 64 or not count or names_index >= count or offset + size * count > len(data):
        raise ValueError('Invalid ELF section table')
    sections = [struct.unpack_from('<IIQQQQIIQQ', data, offset + i * size) for i in range(count)]
    names_section = sections[names_index]
    if names_section[4] + names_section[5] > len(data):
        raise ValueError('Invalid ELF section names')
    names = data[names_section[4]:names_section[4] + names_section[5]]
    result = {}
    for s in sections:
        if s[2] & 2 and s[1] != 8:
            if s[0] >= len(names) or s[4] + s[5] > len(data):
                raise ValueError('Invalid allocated ELF section')
            name = names[s[0]:].split(b'\0', 1)[0]
            if name in result:
                raise ValueError('Duplicate allocated ELF section')
            result[name] = (s[3], data[s[4]:s[4] + s[5]])
    if not result:
        raise ValueError('ELF has no allocated sections')
    return result


def verify_packaged_native(linked, staged, apk):
    if runtime_sections(linked.read_bytes()) != runtime_sections(staged.read_bytes()):
        raise ValueError('Staged native library differs from linked runtime sections')
    name = 'lib/arm64-v8a/libpegasus-fe_arm64-v8a.so'
    with zipfile.ZipFile(apk) as archive:
        if archive.namelist().count(name) != 1 or archive.read(name) != staged.read_bytes():
            raise ValueError('APK does not contain the exact staged native library')
        dex = {n: hashlib.sha256(archive.read(n)).hexdigest() for n in archive.namelist()
               if n.startswith('classes') and n.endswith('.dex')}
    return dex


def build(args):
    heap_mib = getattr(args, 'gradle_heap_mib', None)
    scoped_properties = gradle_properties(heap_mib)
    workspace = args.workspace.resolve()
    manifest = verify(workspace)
    build_dir = args.build_dir.resolve()
    if build_dir.exists() or build_dir == workspace or workspace / 'source' in build_dir.parents:
        raise ValueError('Use a new build directory outside the source tree')
    paths = {name: getattr(args, name).resolve() for name in
             ['qmake', 'qt_conf', 'qt_android', 'sdk', 'ndk', 'openssl', 'androiddeployqt', 'java_home']}
    for name, path in paths.items():
        if not path.exists():
            raise ValueError('Missing provisioned tool: ' + name)
    llvm = paths['ndk'] / 'toolchains/llvm/prebuilt' / args.ndk_host / 'bin'
    for tool in ['llvm-ar', 'llvm-strip']:
        if not (llvm / tool).is_file():
            raise ValueError('Missing NDK tool: ' + tool)
    cache = args.gradle_user_home.resolve()
    cached_gradle(cache, paths['qt_android'] / 'src/3rdparty/gradle/gradle/wrapper/gradle-wrapper.properties')
    env = os.environ.copy()
    env.update(ANDROID_NDK_HOST=args.ndk_host, ANDROID_NDK_ROOT=str(paths['ndk']),
               JAVA_HOME=str(paths['java_home']), ANDROID_SDK_ROOT=str(paths['sdk']),
               ANDROID_HOME=str(paths['sdk']), GRADLE_USER_HOME=str(build_dir / 'gradle-home'),
               ANDROID_USER_HOME=str(args.android_user_home.resolve()))
    build_dir.mkdir(parents=True, exist_ok=False)
    incomplete = build_dir / 'BUILD-INCOMPLETE'
    incomplete.write_text('Review build has not completed and verified.\n')
    # Scope offline policy to this build. Do not install an init script into the
    # user's existing Gradle profile. Only its provisioned caches are shared.
    gradle_home = build_dir / 'gradle-home'
    (gradle_home / 'init.d').mkdir(parents=True)
    for folder in ['caches', 'wrapper']:
        if not (cache / folder).is_dir():
            raise ValueError('Missing provisioned Gradle cache: ' + folder)
        (gradle_home / folder).symlink_to(cache / folder, target_is_directory=True)
    (gradle_home / 'init.d/offline.gradle').write_text('gradle.startParameter.offline = true\n')
    (gradle_home / 'gradle.properties').write_text(scoped_properties)
    source_receipt = workspace / 'nova-build-inputs.json'
    input_sha = sha(source_receipt)
    with (build_dir / 'build.log').open('w') as log:
        def run(command, cwd=build_dir):
            subprocess.run([str(x) for x in command], cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        version = subprocess.check_output([str(paths['qmake']), '-query', 'QT_VERSION'], text=True).strip()
        if not version.startswith('5.15.'):
            raise ValueError('This reviewed recipe requires Qt 5.15')
        run([paths['qmake'], '-r', workspace / 'source/pegasus.pro', '-qtconf', paths['qt_conf'],
             '-spec', paths['qt_android'] / 'mkspecs/android-clang', 'ANDROID_ABIS=arm64-v8a',
             'OPENSSL_ANDROID_ROOT=' + str(paths['openssl']),
             'QMAKE_RANLIB=' + str(llvm / 'llvm-ar') + ' s', 'CONFIG+=debug', 'CONFIG-=release'])
        run(['make', '-j' + str(args.jobs)])
        # Force the final link even on hosts where the static backend archive's
        # timestamp did not trigger qmake's app target.
        run(['make', '-C', 'src/app', '-W', 'main.o'])
        linked = build_dir / 'src/app/libpegasus-fe_arm64-v8a.so'
        staged = build_dir / 'apk/libs/arm64-v8a/libpegasus-fe_arm64-v8a.so'
        # A fresh deployment directory has no app library. androiddeployqt's
        # dependency scan requires it before deployment, not just before Gradle.
        staged.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(linked, staged)
        run([paths['androiddeployqt'], '--input', 'src/app/android-pegasus-fe-deployment-settings.json',
             '--output', build_dir / 'apk', '--android-platform', 'android-30',
             '--jdk', paths['java_home'], '--debug'])
        shutil.copyfile(linked, staged)
        run([llvm / 'llvm-strip', '--strip-unneeded', staged])
        if runtime_sections(linked.read_bytes()) != runtime_sections(staged.read_bytes()):
            raise ValueError('Stripping changed runtime sections')
        run(['./gradlew', '--offline', '--no-daemon', 'clean', 'assembleDebug'], build_dir / 'apk')
    apk = build_dir / 'apk/build/outputs/apk/debug/apk-debug.apk'
    dex = verify_packaged_native(linked, staged, apk)
    if sha(source_receipt) != input_sha or verify(workspace) != manifest:
        raise ValueError('Build input changed during compilation')
    receipt = {'schemaVersion': 1, 'kind': 'private-review-debug-apk', 'installed': False,
               'sourceManifestSha256': input_sha, 'components': manifest['components'],
               'apkSha256': sha(apk), 'apkBytes': apk.stat().st_size,
               'nativeSha256': sha(staged), 'runtimeSectionsMatchLinkedOutput': True, 'dexSha256': dex,
               'toolFiles': {name: sha(paths[name]) for name in ['qmake', 'qt_conf', 'androiddeployqt']},
               'qtVersion': version, 'gradleMaxHeapMiB': heap_mib,
               'limits': ['External theme is separately paired by the input manifest.',
                          'No physical-device, gameplay or save-restoration proof.',
                          'Not approved for public distribution or an existing-app update.']}
    (build_dir / 'nova-build-result.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    incomplete.unlink()
    return receipt


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('workspace', type=Path)
    for name in ['build-dir', 'qmake', 'qt-conf', 'qt-android', 'sdk', 'ndk', 'openssl',
                 'androiddeployqt', 'java-home', 'gradle-user-home', 'android-user-home']:
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--ndk-host', default='darwin-x86_64')
    p.add_argument('--jobs', type=int, choices=range(1, 17), default=2)
    p.add_argument('--gradle-heap-mib', type=int,
                   help='Optional 512–8192 MiB heap, confined to this build; combined optional builds used 1536')
    args = p.parse_args()
    try:
        print(json.dumps(build(args)))
    except (ValueError, OSError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        p.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()
