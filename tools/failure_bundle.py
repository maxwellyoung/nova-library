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
          'exit-return', 'sustained', 'native-4-3', 'stretch-only', 'offline-launch'}
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
FACTS.update({
    'copy-directory-owner-check-failed': ({'preflight'}, "The copied-save folder did not pass the reader's owner-only permissions check.",
        'Review the observed file-access check without granting new permissions or changing saves automatically.'),
    'copy-index-owner-check-failed': ({'preflight'}, "The copied-save index did not pass the reader's owner-only permissions check.",
        'Review the observed file-access check without granting new permissions or changing saves automatically.'),
    'copy-history-unavailable': ({'preflight'}, 'The copied-save history reader reported unavailable.',
        'Keep the copied history and current progress. Review the reader result without restoring or resetting saves.'),
    'copy-history-changed': ({'preflight'}, 'The copied-save history changed before the requested check completed.',
        'Reopen copied history before checking again. Keep all current copies and progress.'),
    'copy-archive-unverified': ({'preflight'}, 'The requested copied-save archive could not be verified.',
        'Keep the archive and current progress. This result does not authorize loading or replacing a save.'),
})
FACTS.update({
    'download-file-unverified': ({'preflight'}, 'A downloaded file could not pass the native identity check before opening.',
        'Keep the downloaded files and saves. Review the local copy before trying to open it again.'),
    'download-changed-before-open': ({'preflight'}, 'The downloaded file record or payload changed during the native opening check.',
        'Keep all current files and progress. Review the changed download before a fresh deliberate attempt.'),
    'download-checksum-unverified': ({'preflight'}, 'A downloaded file did not pass its expected checksum before opening.',
        'Keep the download and current saves. Do not open or replace a save on the strength of this failed check.'),
    'runtime-request-refused': ({'preflight'}, 'The platform launch adapter did not accept the verified-file request.',
        'Review the supported runtime and core installation. This refusal does not establish its cause or authorize a new installation.'),
})
FACTS['selected-theme-load-failed'] = ({'preflight'}, 'The native launcher could not load the selected theme.',
    'Keep the selected theme and current progress. Review the failure or deliberately choose the built-in theme; no cause or repair is established.')
FACTS['selected-theme-construction-failed'] = ({'preflight'}, 'The selected theme failed while creating its interface.',
    'Keep the selected theme and current progress. Review the failure or deliberately choose the built-in theme; no cause or repair is established.')
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
CONTEXT_FIELDS = {'editionId', 'recipeId', 'sourceSha256', 'buildSha256',
                  'runtimeId', 'runtimeVersion'}
COLLECTION_STATUSES = {'supplied', 'collected', 'unsupported', 'refused', 'unavailable'}
COLLECTION_METHODS = {'operator', 'adapter', 'synthetic'}
THEME_ERROR_CODES = {'required-property-uninitialized', 'qml-syntax-error', 'qml-type-unavailable',
                     'javascript-type-error', 'javascript-reference-error', 'qml-error-unclassified'}
LOCAL_EVIDENCE_LIMITS = ('Only bounded error categories/positions and fixed configuration facts. '
                       'No raw log/config text, paths, attachments, ROMs, saves, credentials or commands. '
                       'No repair or send was performed.')

APP_DATA_EVIDENCE_LIMITS = ('Only bounded error categories/positions, fixed configuration facts and app-data volume capacity. '
                            'No raw log/config text, paths, attachments, ROMs, saves, credentials or commands. '
                            'No repair or send was performed.')


class BundleError(ValueError):
    """A fixed diagnostic that never contains input values or filesystem paths."""


def require(condition, message):
    if not condition:
        raise BundleError(message)


def identifier(value, *, version=False, edition=False):
    pattern = (r'[A-Za-z0-9][A-Za-z0-9.+_-]{0,79}' if version else
               r'[A-Za-z0-9][A-Za-z0-9._:-]{0,511}' if edition else
               r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}')
    require(isinstance(value, str) and re.fullmatch(pattern, value)
            and not findings('failure-identity', value), 'Invalid or sensitive identity')
    # Identity is useful locally but never copied verbatim into this bundle.
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def timestamp(value, now):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value),
            'Invalid observation date')
    try:
        date = dt.datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=dt.timezone.utc)
    except ValueError:
        raise BundleError('Invalid observation date') from None
    require(date <= now, 'Observation date is in the future')
    return date


def context(raw):
    require(isinstance(raw, dict) and set(raw) == CONTEXT_FIELDS, 'Invalid provenance context')
    out = {'editionSha256': identifier(raw['editionId'], edition=True), 'recipeSha256': identifier(raw['recipeId'])}
    for field in ('sourceSha256', 'buildSha256'):
        value = raw[field]
        require(value is None or (isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)),
                'Invalid provenance digest')
        out[field] = value
    for field in ('runtimeId', 'runtimeVersion'):
        value = raw[field]
        require(value is None or isinstance(value, str) and value.casefold() not in
                {'unknown', 'unverified', 'unspecified', 'pending', 'none', 'null', 'latest', 'current'},
                'Use null for unknown runtime provenance')
        out[field + 'Sha256'] = None if value is None else identifier(value, version=field == 'runtimeVersion')
    return out


def provenance(raw, edition, observed_recipe, active_recipe, observed_date, now):
    require(isinstance(raw, dict) and set(raw) == {'observed', 'active', 'collection'},
            'Invalid provenance fields')
    observed = context(raw['observed'])
    active = None if raw['active'] is None else context(raw['active'])
    require(observed['editionSha256'] == edition and observed['recipeSha256'] == observed_recipe,
            'Observation provenance does not match descriptor')
    require((active is None and active_recipe is None) or
            (active is not None and active['recipeSha256'] == active_recipe),
            'Active provenance does not match descriptor')
    collection = raw['collection']
    require(isinstance(collection, dict) and set(collection) == {'status', 'method', 'collectedAt'},
            'Invalid collection provenance')
    require(isinstance(collection['status'], str) and collection['status'] in COLLECTION_STATUSES
            and isinstance(collection['method'], str) and collection['method'] in COLLECTION_METHODS,
            'Unsupported collection provenance')
    require(timestamp(collection['collectedAt'], now) >= observed_date,
            'Collection predates observation')
    # A known mismatch stays visible even when other context fields are unknown.
    mismatch = active is not None and any(observed[k] is not None and active[k] is not None
                                          and observed[k] != active[k] for k in observed)
    complete = active is not None and all(v is not None for v in observed.values()) \
        and all(v is not None for v in active.values())
    scope = ('unlinked' if active is None else 'historical-context' if mismatch
             else 'same-declared-context' if complete else 'unknown-context')
    return {'observed': observed, 'active': active, 'contextScope': scope,
            'collection': dict(collection), 'authenticated': False}


def local_evidence(raw, fact_codes, observed_date, now):
    require(isinstance(raw, dict) and {'configuration', 'errorLog', 'lastCloudPreflight'} <= set(raw)
            and set(raw) <= {'configuration', 'errorLog', 'lastCloudPreflight', 'appDataStorage'},
            'Invalid local evidence fields')
    config = raw['configuration']
    require(isinstance(config, dict) and set(config) ==
            {'framework', 'frameworkVersion', 'selectionKind', 'loaderStatus', 'failureStage'},
            'Invalid configuration facts')
    require(config['framework'] == 'Qt' and isinstance(config['frameworkVersion'], str)
            and re.fullmatch(r'[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}', config['frameworkVersion'])
            and config['selectionKind'] in ('local-file', 'bundled', 'other')
            and config['loaderStatus'] == 'error', 'Invalid configuration values')
    expected = 'interface-creation' if 'selected-theme-construction-failed' in fact_codes else 'theme-load'
    require(config['failureStage'] == expected, 'Configuration stage differs from retained fact')
    log = raw['errorLog']
    require(isinstance(log, dict) and set(log) == {'status', 'maxEntries', 'truncated', 'entries'}
            and type(log['maxEntries']) is int and log['maxEntries'] == 8
            and type(log['truncated']) is bool and isinstance(log['entries'], list)
            and len(log['entries']) <= 8, 'Invalid bounded error log')
    require(log['status'] == ('collected' if log['entries'] else 'unavailable')
            and (not log['truncated'] or len(log['entries']) == 8), 'Invalid error collection state')
    entries = []
    for entry in log['entries']:
        require(isinstance(entry, dict) and set(entry) == {'code', 'line', 'column'}
                and isinstance(entry['code'], str) and entry['code'] in THEME_ERROR_CODES
                and type(entry['line']) is int and 0 <= entry['line'] <= 1000000
                and type(entry['column']) is int and 0 <= entry['column'] <= 10000
                and entry not in entries, 'Invalid typed error entry')
        entries.append(dict(entry))
    last = raw['lastCloudPreflight']
    require(isinstance(last, dict), 'Invalid previous Cloud preflight')
    if last.get('status') == 'unavailable':
        require(set(last) == {'status'}, 'Unavailable result has extra fields')
    else:
        require(set(last) == {'status', 'code', 'editionSha256', 'observedAt'}
                and last['status'] == 'observed-refusal'
                and last['code'] in ('download-file-unverified', 'download-changed-before-open',
                                     'download-checksum-unverified', 'runtime-request-refused')
                and isinstance(last['editionSha256'], str)
                and re.fullmatch(r'[0-9a-f]{64}', last['editionSha256']), 'Invalid previous refusal')
        require(timestamp(last['observedAt'], now) <= observed_date, 'Previous refusal postdates failure')
    result = {'configuration': dict(config), 'errorLog': dict(log, entries=entries),
              'lastCloudPreflight': dict(last)}
    if 'appDataStorage' in raw:
        storage = raw['appDataStorage']
        require(isinstance(storage, dict), 'Invalid app-data capacity')
        if storage.get('status') == 'unavailable':
            require(set(storage) == {'status'}, 'Unavailable capacity has extra fields')
        else:
            require(set(storage) == {'status', 'scope', 'method', 'totalBytes', 'availableBytes', 'observedAt'}
                    and storage['status'] == 'measured' and storage['scope'] == 'app-data-volume'
                    and storage['method'] == 'fstatvfs'
                    and type(storage['totalBytes']) is int and 0 < storage['totalBytes'] <= 2**53 - 1
                    and type(storage['availableBytes']) is int and 0 <= storage['availableBytes'] <= storage['totalBytes'],
                    'Invalid app-data capacity values')
            require(timestamp(storage['observedAt'], now) <= observed_date, 'Capacity postdates failure')
        result['appDataStorage'] = dict(storage)
    return result


def build(raw, *, now=None):
    """Return an allowlisted private report; input claims are never authenticated."""
    require(isinstance(raw, dict), 'Missing or unexpected descriptor fields')
    version = raw.get('schemaVersion')
    require(type(version) is int and version in (1, 2), 'Unsupported descriptor schema')
    required = REQUIRED | ({'provenance'} if version == 2 else set())
    require(required <= set(raw) and set(raw) <= required | DISCARDED | ({'origin', 'localEvidence'} if version == 2 else set()),
            'Missing or unexpected descriptor fields')
    now = now or dt.datetime.now(dt.timezone.utc)
    edition = identifier(raw['editionId'], edition=version == 2)
    observed = identifier(raw['observedRecipeId'])
    active = None if raw['activeRecipeId'] is None else identifier(raw['activeRecipeId'])
    stamp = raw['observedAt']
    date = timestamp(stamp, now)
    require(raw.get('origin', 'operator') in ('operator', 'native-save-copies', 'native-cloud-play', 'native-theme-load'), 'Unsupported observation origin')
    captured = provenance(raw['provenance'], edition, observed, active, date, now) if version == 2 else None
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
    if captured is not None and captured['contextScope'] != 'same-declared-context':
        hints.insert(0, 'The declared edition, source, build or runtime context is changed or incomplete. This retained observation does not establish the current context.')
    if captured is not None and captured['collection']['status'] != 'collected':
        hints.insert(0, 'This capture did not collect evidence. Retained facts remain supplied observations; collection status does not establish a cause or a successful check.')
    result = {'schemaVersion': version, 'kind': 'nova-structured-failure', 'observedAt': stamp,
            'editionSha256': edition, 'observedRecipeSha256': observed, 'activeRecipeSha256': active,
            'recipeScope': scope, 'currentSetupVerified': False, 'stage': stage,
            'source': {'native-save-copies': 'native-save-copies-observation', 'native-cloud-play': 'native-cloud-play-observation', 'native-theme-load': 'native-theme-load-observation'}.get(raw.get('origin'), 'operator-supplied-structured-observation'), 'facts': out_facts,
            'hypotheses': out_hypotheses, 'recoveryHints': hints,
            'discardedFieldCount': len(set(raw) & DISCARDED),
            'limits': 'No raw logs, attachments, config, ROMs, saves, credentials or commands. No repair or send was performed.'}
    if captured is not None:
        result['provenance'] = captured
    if 'localEvidence' in raw:
        require(raw.get('origin') == 'native-theme-load' and stage == 'preflight'
                and codes <= {'selected-theme-load-failed', 'selected-theme-construction-failed'}
                and len(codes) == 1, 'Local evidence requires one native theme failure')
        result['localEvidence'] = local_evidence(raw['localEvidence'], codes, date, now)
        result['limits'] = APP_DATA_EVIDENCE_LIMITS if 'appDataStorage' in raw['localEvidence'] else LOCAL_EVIDENCE_LIMITS
    return result


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
