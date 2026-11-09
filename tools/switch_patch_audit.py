#!/usr/bin/env python3
"""Read-only audit of a bounded IPSwitch text subset; never applies a patch."""
import argparse
import hashlib
import json
from pathlib import Path
import re


class AuditError(ValueError):
    pass


def build_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9A-Fa-f]{32,64}', value) or len(value) % 2 or not int(value, 16):
        raise AuditError('A nonzero 16–32 byte NSO build ID is required')
    return value.upper().ljust(64, '0')


def identity(title, version, build):
    if not isinstance(title, str) or not re.fullmatch(r'010[0-9A-Fa-f]{13}', title):
        raise AuditError('An exact Switch program ID is required')
    if not isinstance(version, str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2,3}', version):
        raise AuditError('An exact numeric game version is required')
    return title.upper(), version, build_id(build)


def inspect(data, filename):
    if not isinstance(data, bytes) or len(data) > 65536:
        raise AuditError('Patch input is missing or too large')
    try:
        source = data.decode('utf-8').replace('\r\n', '\n')
    except UnicodeError as error:
        raise AuditError('Patch input must be UTF-8 text') from error
    if '\x00' in source:
        raise AuditError('Binary input is not a text patch')
    issues = []
    warnings = ['Source audit only; no game, emulator, visual result or save compatibility was tested.']
    headers = re.findall(r'^@nsobid-([0-9a-fA-F]+)$', source, re.M)
    bid = None
    try:
        if len(headers) != 1:
            raise AuditError('one-build-header-required')
        bid = build_id(headers[0])
    except AuditError:
        issues.append('invalid-or-ambiguous-build-header')
    titles = sorted(set(re.findall(r'\[(010[0-9A-Fa-f]{13})\]', source)))
    title = titles[0].upper() if len(titles) == 1 else None
    if title is None:
        issues.append('missing-or-ambiguous-program-id')
    version = Path(filename).stem
    if not re.fullmatch(r'[0-9]+(?:\.[0-9]+){2,3}', version):
        version = None
        issues.append('missing-game-version')
    comments = set(re.findall(r'\bv([0-9]+(?:\.[0-9]+){2,3})\b', source))
    if comments and comments != {version}:
        issues.append('version-comment-conflict')
    active = False
    stopped = False
    ranges = []
    shift = 0
    for line_number, raw in enumerate(source.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(('#', '//', 'https://')):
            continue
        if raw != raw.lstrip():
            issues.append('indented-directive-or-write')
        if stopped:
            if re.match(r'[0-9A-Fa-f]{8}\s', line) or line.startswith(('@enabled', '@disabled', '@flag', '@nsobid-')):
                issues.append('patch-content-after-stop-requires-review')
            continue
        if line.startswith('@nsobid-'):
            continue
        if line == '@stop':
            active = False
            stopped = True
            continue
        if line in ('@enabled', '@disabled'):
            active = line == '@enabled'
            continue
        if line == '@flag print_values':
            continue
        if line.startswith('@flag offset_shift '):
            text = line[len('@flag offset_shift '):]
            if re.fullmatch(r'0x[0-9A-Fa-f]+|[0-9]+', text):
                shift = int(text, 16 if text.startswith('0x') else 10)
                if shift > 0x100000:
                    issues.append('unsupported-offset-shift')
            else:
                issues.append('invalid-offset-shift')
            continue
        if line.startswith('@'):
            issues.append('unsupported-or-case-mismatched-directive')
            continue
        if not active:
            continue
        match = re.fullmatch(r'([0-9A-Fa-f]{8}) ([0-9A-Fa-f]+)(?:\s*//.*)?', line)
        if not match or len(match[2]) % 2:
            issues.append('unsupported-write-syntax')
            continue
        start = int(match[1], 16) + shift
        end = start + len(match[2]) // 2
        if end > 0x100000000:
            issues.append('write-outside-32-bit-range')
        if any(start < old_end and old_start < end for old_start, old_end in ranges):
            issues.append('overlapping-writes-require-review')
        ranges.append((start, end))
    if not ranges:
        issues.append('no-enabled-writes')
    if re.search(r'\b(?:HUD|UI)\b.*\b(?:messy|issue|crop)', source, re.I):
        warnings.append('Patch comments describe a HUD/UI limitation; review the original notes.')
    if re.search(r'21:9|16:9', source):
        warnings.append('Other aspect ratios appear in the patch text; resolve the description before testing.')
    return {'schemaVersion': 1, 'sha256': hashlib.sha256(data).hexdigest(),
            'programId': title, 'gameVersion': version, 'nsoBuildId': bid,
            'enabledWriteCount': len(ranges), 'requiresStretchSetting': bool(re.search(r'stretch', source, re.I)),
            'issues': sorted(set(issues)), 'warnings': warnings, 'runtimeTested': False}


def preview(data, filename, title, version, build):
    title, version, build = identity(title, version, build)
    report = inspect(data, filename)
    mismatches = [name for name, expected in [('programId', title), ('gameVersion', version), ('nsoBuildId', build)]
                  if report[name] != expected]
    return {'patch': report, 'identityMismatches': mismatches,
            'sourceCandidate': not report['issues'] and not mismatches,
            'deviceApplied': False, 'gameplayVerified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('patch', type=Path)
    parser.add_argument('--program-id')
    parser.add_argument('--game-version')
    parser.add_argument('--build-id')
    args = parser.parse_args()
    try:
        if args.patch.is_symlink() or not args.patch.is_file() or args.patch.stat().st_size > 65536:
            raise AuditError('A regular bounded text patch is required')
        data = args.patch.read_bytes()
        values = (args.program_id, args.game_version, args.build_id)
        if any(values) and not all(values):
            raise AuditError('Matching requires program ID, game version and NSO build ID together')
        report = preview(data, args.patch.name, *values) if all(values) else inspect(data, args.patch.name)
        print(json.dumps(report, indent=2))
        return 0 if (report['sourceCandidate'] if all(values) else not report['issues']) else 1
    except (OSError, AuditError):
        parser.exit(2, 'Patch audit refused the input; supply a regular text patch and complete exact identity.\n')


if __name__ == '__main__':
    raise SystemExit(main())
