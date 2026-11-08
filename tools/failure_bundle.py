#!/usr/bin/env python3
"""Preview and explicitly export a bounded, structured failure observation.

No log collection, attachments, network access, device commands or repairs. Free
text is excluded: facts, hypotheses and hints use the reviewed vocabulary below.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

if __package__:
    from .privacy_scan import findings
    from .save_passport import directory, parse_json
else:
    from privacy_scan import findings
    from save_passport import directory, parse_json

MAX_INPUT = 16 * 1024
MAX_OUTPUT = 8 * 1024
MAX_FACTS = 16
MAX_HYPOTHESES = 8
# Existing compatibility-receipt methods and stages are retained. Install stages
# are additional diagnostic stages; they do not become compatibility passes.
METHODS = {'physical', 'owner', 'observed', 'injected', 'log', 'test'}
STAGES = {'unknown', 'catalogue', 'preflight', 'download', 'activation', 'boot',
          'menus', 'gameplay', 'physical-controls', 'audio', 'save-restore',
          'exit-return', 'sustained', 'native-4-3', 'stretch-only'}
FACTS = {
    'route-unavailable': ({'catalogue', 'boot'}, 'No usable launch route was reported.',
                          'Review the configured route without changing saves or starting another runtime.'),
    'file-missing': ({'preflight', 'boot'}, 'A required local file was reported missing.',
                     'Check the local installation. A cached cover does not establish file presence.'),
    'storage-insufficient': ({'preflight', 'download'}, 'The measured install preflight reported insufficient space.',
                             'Use the existing storage review. Do not delete unreviewed files or saves.'),
    'network-unavailable': ({'catalogue', 'download'}, 'The requested network operation reported unavailable.',
                            'Retain local data and retry through the existing client when connected.'),
    'transfer-interrupted': ({'download'}, 'The transfer reported an interruption.',
                             'Retain partial bytes and resume through the existing verified client.'),
    'checksum-mismatch': ({'download', 'activation'}, 'The transferred payload failed its expected checksum.',
                          'Keep the working installation and saves. Do not activate failed payload bytes.'),
    'activation-refused': ({'activation'}, 'Installation activation was refused.',
                           'Keep the working installation. Inspect the install result before retrying.'),
    'runtime-idle-unknown': ({'preflight', 'exit-return'}, 'The runtime idle boundary was not established.',
                             'Keep cleanup blocked. Returning to Library alone does not prove runtime exit.'),
    'runtime-active': ({'preflight', 'exit-return'}, 'The runtime was reported active.',
                       'Leave the active session intact; finish it normally before considering cleanup.'),
    'save-result-unknown': ({'save-restore'}, 'The save or restore result was not established.',
                            'Keep the active session and current saves. Verify the outcome in the runtime before leaving.'),
    'save-identity-mismatch': ({'save-restore'}, 'The requested save identity did not match the declared target.',
                               'Do not overwrite progress. Compare edition, runtime, core and save kind first.'),
    'configuration-mismatch': (STAGES, 'The observation reported a configuration mismatch.',
                               'Compare the declared setup with the active configuration before changing settings.'),
    'permission-unavailable': (STAGES, 'The requested capability reported unavailable permission.',
                               'Keep the capability disabled. Any new permission requires its own explicit authorization.'),
    'operation-failed': (STAGES, 'The operation reported failure without an established cause.',
                         'Preserve current data and inspect the supported result screen; do not reset a profile.'),
    'result-unknown': (STAGES, 'The operation result was not established.',
                       'Keep the result unknown. Do not infer success or repeat a save-affecting action blindly.'),
}
HYPOTHESES = {
    'setup-changed': 'The active setup may differ from the observed setup.',
    'temporary-network-failure': 'A temporary network failure may have contributed.',
    'interrupted-transfer': 'An interrupted transfer may have contributed.',
    'runtime-unavailable': 'The expected runtime may be unavailable.',
    'unknown-cause': 'No cause is established.',
}
REQUIRED = {'schemaVersion', 'editionId', 'observedRecipeId', 'activeRecipeId',
            'observedAt', 'stage', 'facts', 'hypotheses'}
# Recognized sensitive fields are deliberately discarded in their entirety.
# Unexpected fields fail closed, rather than being copied into a portable file.
DISCARDED = {'logs', 'rawLog', 'token', 'tokens', 'account', 'accountId', 'path',
             'paths', 'rom', 'save', 'payload', 'config', 'endpoint', 'url',
             'device', 'runtime', 'attachments'}


class BundleError(ValueError):
    """A fixed diagnostic that never contains input values or filesystem paths."""


def require(condition, message):
    if not condition:
        raise BundleError(message)


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}', value)
            and not findings('failure-identity', value), 'Invalid or sensitive identity')
    # Identity is useful locally but never copied verbatim into this bundle.
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def build(raw, *, now=None):
    """Return an allowlisted private report; input claims are never authenticated."""
    require(isinstance(raw, dict) and REQUIRED <= set(raw) and set(raw) <= REQUIRED | DISCARDED,
            'Missing or unexpected descriptor fields')
    require(type(raw['schemaVersion']) is int and raw['schemaVersion'] == 1, 'Unsupported descriptor schema')
    edition = identifier(raw['editionId'])
    observed = identifier(raw['observedRecipeId'])
    active = None if raw['activeRecipeId'] is None else identifier(raw['activeRecipeId'])
    stamp = raw['observedAt']
    require(isinstance(stamp, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', stamp),
            'Invalid observation date')
    try:
        date = dt.datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
    except ValueError:
        raise BundleError('Invalid observation date') from None
    require(date <= (now or dt.datetime.now(dt.timezone.utc)), 'Observation date is in the future')
    stage = raw['stage']
    require(isinstance(stage, str) and stage in STAGES, 'Invalid failure stage')
    facts = raw['facts']
    require(isinstance(facts, list) and 1 <= len(facts) <= MAX_FACTS, 'Invalid fact count')
    out_facts, codes, hints = [], set(), []
    for fact in facts:
        require(isinstance(fact, dict) and set(fact) == {'code', 'method'}, 'Invalid structured fact')
        code, method = fact['code'], fact['method']
        require(isinstance(code, str) and code in FACTS and code not in codes,
                'Unsupported or duplicate fact code')
        require(isinstance(method, str) and method in METHODS, 'Invalid observation method')
        stages, text, hint = FACTS[code]
        require(stage in stages, 'Fact does not match the reported stage')
        codes.add(code)
        out_facts.append({'code': code, 'method': method, 'statement': text})
        if hint not in hints:
            hints.append(hint)
    hypotheses = raw['hypotheses']
    require(isinstance(hypotheses, list) and len(hypotheses) <= MAX_HYPOTHESES, 'Invalid hypothesis count')
    out_hypotheses, seen = [], set()
    for hypothesis in hypotheses:
        require(isinstance(hypothesis, dict) and set(hypothesis) == {'code', 'basedOn'}, 'Invalid structured hypothesis')
        code, basis = hypothesis['code'], hypothesis['basedOn']
        require(isinstance(code, str) and code in HYPOTHESES and code not in seen,
                'Unsupported or duplicate hypothesis code')
        require(isinstance(basis, list) and 1 <= len(basis) <= MAX_FACTS
                and all(isinstance(c, str) and c in codes for c in basis)
                and len(set(basis)) == len(basis), 'Hypothesis requires retained fact references')
        seen.add(code)
        out_hypotheses.append({'code': code, 'status': 'unconfirmed',
                               'statement': HYPOTHESES[code], 'basedOn': basis[:]})
    scope = 'unlinked' if active is None else 'same-declared-recipe' if active == observed else 'historical-recipe'
    if scope != 'same-declared-recipe':
        hints.insert(0, 'This observation does not establish the current setup. Compare its declared recipe before applying any guidance.')
    return {'schemaVersion': 1, 'kind': 'nova-structured-failure', 'observedAt': stamp,
            'editionSha256': edition, 'observedRecipeSha256': observed, 'activeRecipeSha256': active,
            'recipeScope': scope, 'currentSetupVerified': False, 'stage': stage,
            'source': 'operator-supplied-structured-observation', 'facts': out_facts,
            'hypotheses': out_hypotheses, 'recoveryHints': hints,
            'discardedFieldCount': len(set(raw) & DISCARDED),
            'limits': 'No raw logs, attachments, config, ROMs, saves, credentials or commands. No repair or send was performed.'}


def preview(raw, *, now=None):
    """Produce complete inspectable bytes and their approval digest, without I/O."""
    bundle = build(raw, now=now)
    data = (json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode('utf-8')
    require(len(data) <= MAX_OUTPUT, 'Portable report exceeds its byte bound')
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'bundle': bundle}


def read_descriptor(path):
    path = Path(path).absolute()
    try:
        directory(path.parent)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as source:
            before = os.fstat(source.fileno())
            require(stat.S_ISREG(before.st_mode) and before.st_size <= MAX_INPUT,
                    'Descriptor must be a bounded regular file')
            data = source.read(MAX_INPUT + 1)
            after = os.fstat(source.fileno())
            require(len(data) <= MAX_INPUT and
                    (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                    (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                    'Descriptor changed or exceeds its byte bound')
        return parse_json(data)
    except BundleError:
        raise
    except (OSError, ValueError, RecursionError):
        raise BundleError('Descriptor is unavailable, unsafe or invalid JSON') from None


def export(raw, output, *, approve_sha256=None, now=None):
    """Write exactly previewed bytes to a new private file after explicit approval."""
    report = preview(raw, now=now)
    require(isinstance(approve_sha256, str) and re.fullmatch(r'[0-9a-f]{64}', approve_sha256)
            and approve_sha256 == report['sha256'], 'Explicit approval of the current preview digest is required')
    data = (json.dumps(report['bundle'], indent=2, sort_keys=True, ensure_ascii=True) + '\n').encode('utf-8')
    output = Path(output).absolute()
    require('..' not in output.parts, 'Output must use a canonical parent directory')
    directory_fd, created = None, None
    try:
        directory(output.parent)
        directory_fd = os.open(output.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fd = os.open(output.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=directory_fd)
        created = os.fstat(fd)
        with os.fdopen(fd, 'wb') as target:
            target.write(data)
            target.flush()
            os.fsync(target.fileno())
        return {'bytes': report['bytes'], 'sha256': report['sha256'], 'exported': True, 'sent': False}
    except (OSError, ValueError):
        if created is not None:
            try:
                current = os.stat(output.name, dir_fd=directory_fd, follow_symlinks=False)
                if (current.st_dev, current.st_ino) == (created.st_dev, created.st_ino):
                    os.unlink(output.name, dir_fd=directory_fd)
            except OSError:
                pass
        raise BundleError('Export failed; no existing output was replaced') from None
    finally:
        if directory_fd is not None:
            os.close(directory_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('preview')
    p.add_argument('descriptor', type=Path)
    p = sub.add_parser('export')
    p.add_argument('descriptor', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--approve-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        raw = read_descriptor(args.descriptor)
        result = preview(raw) if args.command == 'preview' else export(raw, args.output, approve_sha256=args.approve_sha256)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (BundleError, ValueError, TypeError, RecursionError):
        # Do not print exception details: even OS and parser errors can contain paths or input.
        print('Failure bundle refused: invalid/unsafe input, stale approval or unavailable new output. Nothing was sent.', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
