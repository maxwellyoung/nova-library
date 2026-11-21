#!/usr/bin/env python3
"""Read enrolled Android filesystem capacity; never scan or delete game data."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess


MAX_CAPTURE = 65536
MAX_SAFE = 2**53 - 1
PUBLIC_LINE = re.compile(r'public:[0-9]+,[0-9]+ ([a-z_]+) (null|[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4})')
STATES = {'mounted', 'mounted_ro', 'unmounted', 'checking', 'ejecting',
          'unmountable', 'removed', 'bad_removal', 'formatting'}


def timestamp(value):
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Capacity capture needs an aware clock')
    return value.astimezone(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def mounted_public(raw):
    """Return mounted public volumes, refusing partial or ambiguous discovery."""
    if not isinstance(raw, str) or len(raw) > MAX_CAPTURE:
        raise ValueError('Public-volume discovery unavailable')
    volumes = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        match = PUBLIC_LINE.fullmatch(line.strip())
        if not match or match[1] not in STATES:
            raise ValueError('Public-volume discovery format unrecognised')
        state, identifier = match.groups()
        if state in {'mounted', 'mounted_ro'}:
            if identifier == 'null' or identifier.lower() in volumes:
                raise ValueError('Mounted public-volume identity is ambiguous')
            volumes[identifier.lower()] = (identifier, state)
    return sorted(volumes.values())


def parse_df(raw, mount, role, observed_at):
    """Decode a single toybox df -k table; available bytes are not all free blocks."""
    if role not in {'internal-data', 'sd-card'} or not isinstance(mount, str) or not isinstance(raw, str) or len(raw) > MAX_CAPTURE:
        raise ValueError('Capacity table unavailable')
    if (role == 'internal-data' and mount != '/data') or (role == 'sd-card' and not re.fullmatch(r'/storage/[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}', mount)):
        raise ValueError('Capacity mount is outside the selected role')
    lines = [line.split() for line in raw.splitlines() if line.strip()]
    if len(lines) != 2 or lines[0] not in [
            ['Filesystem', '1K-blocks', 'Used', 'Available', 'Use%', 'Mounted', 'on'],
            ['Filesystem', '1024-blocks', 'Used', 'Available', 'Use%', 'Mounted', 'on']]:
        raise ValueError('Capacity table units or layout unrecognised')
    row = lines[1]
    if len(row) != 6 or row[5] != mount or not all(re.fullmatch(r'[0-9]{1,16}', n) for n in row[1:4]) or not re.fullmatch(r'[0-9]{1,3}%', row[4]) or int(row[4][:-1]) > 100:
        raise ValueError('Capacity row is malformed or mounted elsewhere')
    total, used, free = [int(n) * 1024 for n in row[1:4]]
    if not 0 < total <= MAX_SAFE or used > MAX_SAFE or free > MAX_SAFE or used + free > total:
        raise ValueError('Capacity arithmetic is invalid')
    return {'id': role, 'total': total, 'used': used, 'free': free,
            'observedAt': timestamp(observed_at),
            'source': 'Android shell df -k; ' + ('internal /data' if role == 'internal-data' else 'mounted public volume')}


def capture(reader, expected_serial, clock=lambda: datetime.now(timezone.utc), *, sd_uuid=None):
    """Use an existing shell reader; each role may succeed independently.

    Mount discovery is checked again after reading SD capacity. Neither a failed
    path lookup nor a removed card may turn the internal filesystem into SD.
    """
    if not isinstance(expected_serial, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', expected_serial):
        raise ValueError('An explicit enrolled device is required')
    if sd_uuid is not None and (not isinstance(sd_uuid, str) or not re.fullmatch(r'[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}', sd_uuid)):
        raise ValueError('The selected card needs an explicit filesystem UUID')

    def read(command):
        try:
            code, output, error = reader.shell(command, timeout=15)
        except (OSError, subprocess.TimeoutExpired):
            raise ValueError('Capacity read failed') from None
        if code != 0 or not isinstance(error, str) or error.strip() or not isinstance(output, str) or len(output) > MAX_CAPTURE:
            raise ValueError('Capacity read failed')
        return output

    if read('getprop ro.serialno').strip() != expected_serial:
        raise ValueError('Enrolled device identity does not match')
    volumes, errors = [], []
    try:
        volumes.append(parse_df(read('df -k /data'), '/data', 'internal-data', clock()))
    except ValueError:
        errors.append({'volume': 'internal-data', 'reason': 'Internal capacity unavailable or invalid'})
    try:
        # A public volume could be a USB drive. Only the operator's explicitly
        # selected card may acquire the sd-card role; discovery alone is not it.
        if sd_uuid is None:
            raise ValueError('No card mount enrolled')
        before = mounted_public(read('sm list-volumes public'))
        if len(before) != 1 or before[0][0].lower() != sd_uuid.lower():
            raise ValueError('No single mounted public volume')
        identifier, _ = before[0]
        mount = '/storage/' + identifier
        snapshot = parse_df(read('df -k ' + mount), mount, 'sd-card', clock())
        after = mounted_public(read('sm list-volumes public'))
        if before != after:
            raise ValueError('Public volume changed during capture')
        volumes.append(snapshot)
    except ValueError:
        errors.append({'volume': 'sd-card', 'reason': 'No stable, uniquely mounted public-volume measurement'})
    return {'schemaVersion': 1, 'producer': 'android-df-k-v1', 'hardwareSerial': expected_serial,
            'sdVolumeUuid': sd_uuid, 'volumes': volumes, 'errors': errors}


def catalogue_fields(report, expected_serial, now=None):
    """Validate a private capture before exporting only its public capacity fields."""
    now = now or datetime.now(timezone.utc)
    timestamp(now)
    if not isinstance(expected_serial, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', expected_serial):
        raise ValueError('An explicit enrolled device is required')
    if not isinstance(report, dict) or type(report.get('schemaVersion')) is not int or report.get('schemaVersion') != 1 or report.get('producer') != 'android-df-k-v1' or report.get('hardwareSerial') != expected_serial:
        raise ValueError('Capacity capture belongs to an unsupported producer or device')
    volumes = report.get('volumes')
    if not isinstance(volumes, list) or len(volumes) > 2:
        raise ValueError('Capacity capture is not bounded')
    checked, seen = [], set()
    for row in volumes:
        if not isinstance(row, dict) or set(row) != {'id', 'total', 'used', 'free', 'source', 'observedAt'} or not isinstance(row['id'], str) or row['id'] not in {'internal-data', 'sd-card'} or row['id'] in seen:
            raise ValueError('Capacity capture roles are invalid or duplicated')
        seen.add(row['id'])
        if row['id'] == 'sd-card' and (not isinstance(report.get('sdVolumeUuid'), str) or not re.fullmatch(r'[A-Fa-f0-9]{4}-[A-Fa-f0-9]{4}', report['sdVolumeUuid'])):
            raise ValueError('The card role has no enrolled mount identity')
        if any(isinstance(row[k], bool) or not isinstance(row[k], int) or not 0 <= row[k] <= MAX_SAFE for k in ['total', 'used', 'free']) or row['total'] <= 0 or row['used'] + row['free'] > row['total']:
            raise ValueError('Capacity capture arithmetic is invalid')
        expected_source = 'Android shell df -k; ' + ('internal /data' if row['id'] == 'internal-data' else 'mounted public volume')
        if row['source'] != expected_source or not isinstance(row['observedAt'], str):
            raise ValueError('Capacity capture provenance is invalid')
        try:
            observed = datetime.fromisoformat(row['observedAt'].replace('Z', '+00:00'))
            if timestamp(observed) != row['observedAt'] or observed > now:
                raise ValueError('Capacity date is invalid')
        except (ValueError, TypeError):
            raise ValueError('Capacity date is invalid') from None
        checked.append(dict(row))
    fields = {'storage_volumes': checked}
    internal = next((row for row in checked if row['id'] == 'internal-data'), None)
    if internal:
        fields['storage_volume'] = dict(internal)
    return fields


class AdbReader:
    def __init__(self, serial):
        self.serial = serial

    def shell(self, command, timeout):
        result = subprocess.run(['adb', '-s', self.serial, 'shell', command], capture_output=True, text=True, timeout=timeout)
        return result.returncode, result.stdout, result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True, help='Explicit enrolled USB debugging serial')
    parser.add_argument('--sd-uuid', help='Filesystem UUID explicitly identified as the microSD; otherwise it stays unmeasured')
    parser.add_argument('--output', type=Path, required=True, help='New private capture file outside repositories')
    args = parser.parse_args()
    try:
        output = args.output.absolute()
        parent = output.parent.resolve(strict=True)
        if not parent.is_dir() or any((p / '.git').exists() for p in (parent, *parent.parents)):
            raise ValueError('Capacity captures stay outside repositories')
        report = capture(AdbReader(args.serial), args.serial, sd_uuid=args.sd_uuid)
        catalogue_fields(report, args.serial)
        with (parent / output.name).open('x') as stream:
            os.chmod(stream.fileno(), 0o600)
            json.dump(report, stream, indent=2); stream.write('\n')
        print('Private capacity capture saved. No game, catalogue or device setting changed.')
        if report['errors']:
            print('Some volumes remain unmeasured; inspect the private capture before export.')
    except (OSError, ValueError):
        parser.exit(1, 'Capacity capture refused; prior output and device settings retained.\n')


if __name__ == '__main__':
    main()
