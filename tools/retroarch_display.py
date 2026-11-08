#!/usr/bin/env python3
"""Host-only, edition-scoped RetroArch 1.22.2 display config transactions.

This tool never launches an emulator, writes its existing profile, or runs config
text. CONFIGFILE selection in the Android launcher remains a separate integration.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid

RUNTIME = {'id': 'retroarch-android-aarch64', 'package': 'com.retroarch.aarch64',
           'version': '1.22.2', 'sourceCommit': '69a4f0ea1e8aaf442ae4858f2e7f2b31a1776576'}
ADAPTER = 'retroarch-display-v1'
LIMIT = 1024 * 1024
MARKER = {'schema': 1, 'kind': ADAPTER}
SETTINGS = {
    'fit': {'aspect_ratio_index': '22', 'video_force_aspect': 'true',
            'video_scale_integer': 'false', 'video_viewport_bias_x': '0.5', 'video_viewport_bias_y': '0.5'},
    'fill': {'aspect_ratio_index': '24', 'video_force_aspect': 'false',
             'video_scale_integer': 'false', 'video_viewport_bias_x': '0.5', 'video_viewport_bias_y': '0.5'},
}
IDENTIFIER = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z')
GENERATION = re.compile(r'[a-f0-9]{32}\Z')
SHA256 = re.compile(r'[a-f0-9]{64}\Z')
ASSIGNMENT = re.compile(r'\s*([A-Za-z0-9_]{1,128})\s*=\s*"([^"\\\r\n]*)"\s*(?:#.*)?\Z')


class DisplayError(ValueError):
    """Fixed, non-sensitive diagnostics; never include arbitrary config contents."""


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise DisplayError('Duplicate JSON field')
        out[key] = value
    return out


def decode_json(data):
    if not isinstance(data, bytes) or len(data) > 32768:
        raise DisplayError('JSON input is unavailable or oversized')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(DisplayError('Non-finite JSON number')))
    except (UnicodeError, json.JSONDecodeError):
        raise DisplayError('Invalid JSON input') from None


def _runtime(runtime):
    if type(runtime) is not dict or runtime != RUNTIME:
        raise DisplayError('Unknown runtime identity or source version; display configuration refused')


def _identity(game, edition):
    if not all(type(x) is str and IDENTIFIER.fullmatch(x) for x in (game, edition)):
        raise DisplayError('Game and edition IDs must be bounded stable identifiers')
    return _sha((game + '\0' + edition).encode())[:32]


def capabilities(runtime):
    _runtime(runtime)
    return {'adapter': ADAPTER, 'runtime': dict(RUNTIME), 'method': 'pinned-source-support',
            'installedRuntimeVerified': False, 'modes': {
                'native': {'available': False, 'reason': 'One-to-one native pixel geometry is not measured'},
                'fit': {'available': True, 'meaning': 'Fit the core-provided display aspect inside the viewport'},
                'fill': {'available': True, 'meaning': 'Stretch to the full viewport; aspect may change'},
                'crop': {'available': False, 'reason': 'Aspect-preserving crop requires measured geometry and driver acceptance'},
            }}


def parse_config(data):
    if not isinstance(data, bytes) or len(data) > LIMIT:
        raise DisplayError('Baseline config is unavailable or oversized')
    try:
        text = data.decode('utf-8')
    except UnicodeError:
        raise DisplayError('Baseline config must be UTF-8') from None
    if any(ord(c) < 32 and c not in '\r\n\t' or ord(c) == 127 for c in text):
        raise DisplayError('Control characters in config')
    values = {}
    for line in text.splitlines():
        if re.match(r'\s*#\s*include\b', line, re.I):
            raise DisplayError('Included configs need a separate precedence review')
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if not match:
            raise DisplayError('Unsupported config syntax; no config was changed')
        key, value = match.groups()
        if key in values:
            raise DisplayError('Duplicate config keys make precedence ambiguous')
        values[key] = value
    if any(values.get(k) != 'false' for k in ('auto_overrides_enable', 'config_save_on_exit')):
        raise DisplayError('A flat baseline with overrides and save-on-exit already disabled is required')
    for key in SETTINGS['fit']:
        value = values.get(key)
        if value is None:
            continue
        if key == 'aspect_ratio_index':
            valid = bool(re.fullmatch(r'[0-9]{1,2}', value)) and 0 <= int(value) <= 24
        elif key in ('video_force_aspect', 'video_scale_integer'):
            valid = value in ('true', 'false')
        else:
            try:
                number = float(value)
                valid = len(value) <= 16 and math.isfinite(number) and 0 <= number <= 1
            except ValueError:
                valid = False
        if not valid:
            raise DisplayError('Unrecognized or out-of-bounds display value')
    return text, values


def render_config(data, mode):
    if type(mode) is not str or mode not in SETTINGS:
        raise DisplayError('Display mode is unavailable for this adapter')
    text, _ = parse_config(data)
    settings, seen, lines = SETTINGS[mode], set(), []
    for line in text.splitlines(keepends=True):
        match = ASSIGNMENT.fullmatch(line.rstrip('\r\n'))
        key = match.group(1) if match else None
        if key in settings:
            lines.append(key + ' = "' + settings[key] + '"\n')
            seen.add(key)
        else:
            lines.append(line)
    output = ''.join(lines)
    if output and not output.endswith('\n'):
        output += '\n'
    output += ''.join(k + ' = "' + v + '"\n' for k, v in settings.items() if k not in seen)
    result = output.encode()
    if len(result) > LIMIT:
        raise DisplayError('Resulting config is oversized')
    return result


def import_recipe(data):
    recipe = decode_json(data)
    keys = {'schema', 'adapter', 'runtime', 'gameId', 'editionId', 'mode', 'settings'}
    if type(recipe) is not dict or set(recipe) != keys or type(recipe['schema']) is not int or recipe['schema'] != 1 or recipe['adapter'] != ADAPTER:
        raise DisplayError('Only the allowlisted display recipe schema can be imported')
    _runtime(recipe['runtime'])
    _identity(recipe['gameId'], recipe['editionId'])
    mode = recipe['mode']
    if type(mode) is not str or mode not in SETTINGS or recipe['settings'] != SETTINGS[mode]:
        raise DisplayError('Imported display settings are unavailable or not canonical')
    return recipe


def _sync(directory):
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read(path, limit=LIMIT):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise DisplayError('Linked, non-regular or oversized input is protected')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise DisplayError('Input exceeds its byte limit')
        return data
    finally:
        os.close(fd)


def _atomic(path, data):
    temporary = path.parent / ('.' + path.name + '.tmp-' + uuid.uuid4().hex)
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
        _sync(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _checkpoint(stage):
    """Fault boundary for disposable transaction tests; never executes input."""


class Store:
    def __init__(self, root):
        path = Path(root).absolute()
        if path.is_symlink():
            raise DisplayError('Linked workspace is protected')
        self.root = path.resolve()
        self._private_location(self.root)
        marker = decode_json(_read(self._path('workspace.json'), 32768))
        if type(marker) is not dict or type(marker.get('schema')) is not int or marker != MARKER:
            raise DisplayError('Not a managed display workspace')

    @staticmethod
    def _private_location(path):
        # Baseline profiles can contain credentials; only recipes belong in source control.
        if any((parent / '.git').exists() for parent in (path, *path.parents)):
            raise DisplayError('Private display configs cannot be stored in a Git checkout')

    @classmethod
    def create(cls, root):
        path = Path(root).absolute()
        if path.exists() or path.is_symlink():
            raise DisplayError('Workspace must be a new directory; existing profiles are protected')
        cls._private_location(path.resolve())
        path.mkdir(mode=0o700, parents=False)
        _atomic(path / 'workspace.json', _json(MARKER))
        _atomic(path / 'lock', b'')
        return cls(path)

    def _path(self, *parts):
        path = self.root
        for part in parts:
            if not isinstance(part, str) or part in ('', '.', '..') or '/' in part or '\\' in part:
                raise DisplayError('Invalid internal path component')
            path = path / part
            if path.is_symlink():
                raise DisplayError('Linked workspace entry is protected')
        return path

    @contextmanager
    def _locked(self, write=False, allow_pending=False):
        fd = os.open(self._path('lock'), os.O_RDWR | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise DisplayError('Linked workspace lock is protected')
            try:
                fcntl.flock(fd, (fcntl.LOCK_EX if write else fcntl.LOCK_SH) | fcntl.LOCK_NB)
            except BlockingIOError:
                raise DisplayError('Display workspace is busy') from None
            if not allow_pending and self._path('pending.json').exists():
                raise DisplayError('Interrupted transaction requires recover before further work')
            yield
        finally:
            os.close(fd)

    def _pointer(self, key):
        path = self._path('editions', key, 'current.json')
        if not path.exists():
            return None
        value = decode_json(_read(path, 32768))
        if type(value) is not dict or set(value) != {'generation'} or type(value['generation']) is not str or not GENERATION.fullmatch(value['generation']):
            raise DisplayError('Invalid config selection; preserve workspace for review')
        return value['generation']

    def _generation(self, game, edition, generation):
        if type(generation) is not str or not GENERATION.fullmatch(generation):
            raise DisplayError('Invalid config generation')
        key = _identity(game, edition)
        path = self._path('editions', key, 'generations', generation)
        receipt = decode_json(_read(path / 'receipt.json', 32768))
        keys = {'schema', 'gameId', 'editionId', 'runtime', 'mode', 'configSha256', 'previous'}
        if type(receipt) is not dict or set(receipt) != keys or type(receipt['schema']) is not int or receipt['schema'] != 1 or receipt['gameId'] != game or receipt['editionId'] != edition:
            raise DisplayError('Config generation identity changed')
        _runtime(receipt['runtime'])
        if receipt['mode'] not in ('original', *SETTINGS) or type(receipt['configSha256']) is not str or not SHA256.fullmatch(receipt['configSha256']):
            raise DisplayError('Invalid config receipt')
        if receipt['previous'] is not None and (type(receipt['previous']) is not str or not GENERATION.fullmatch(receipt['previous'])):
            raise DisplayError('Invalid rollback reference')
        data = _read(path / 'config.cfg')
        if _sha(data) != receipt['configSha256']:
            raise DisplayError('Config changed outside its transaction; preserve it for review')
        parse_config(data)
        return receipt, data, path / 'config.cfg'

    def _basis(self, game, edition, baseline):
        current = self._pointer(_identity(game, edition))
        if current is None:
            if baseline is None:
                raise DisplayError('First choice requires a reviewed flat baseline config')
            parse_config(baseline)
            return None, baseline
        if baseline is not None:
            raise DisplayError('Existing edition owns its baseline; omit a replacement baseline')
        return current, self._generation(game, edition, current)[1]

    def _plan(self, operation, runtime, game, edition, mode, baseline, issued):
        _runtime(runtime)
        current, before = self._basis(game, edition, baseline)
        if operation == 'set':
            after = render_config(before, mode)
        elif operation == 'revert':
            if current is None:
                raise DisplayError('No edition preference exists to revert')
            receipt = self._generation(game, edition, current)[0]
            target = receipt['previous']
            if target is None:
                raise DisplayError('Already at the original reviewed config')
            restored, after, _ = self._generation(game, edition, target)
            mode = restored['mode']
        else:
            raise DisplayError('Unknown display operation')
        _, old = parse_config(before)
        _, new = parse_config(after)
        plan = {'schema': 1, 'adapter': ADAPTER, 'operation': operation, 'runtime': dict(runtime),
                'gameId': game, 'editionId': edition, 'mode': mode, 'beforeGeneration': current,
                'beforeSha256': _sha(before), 'afterSha256': _sha(after), 'issuedAt': issued,
                'expiresAt': issued + 60, 'changes': {k: {'before': old.get(k), 'after': new.get(k)}
                  for k in SETTINGS['fit'] if old.get(k) != new.get(k)}}
        plan['token'] = _sha(_json(plan))
        return plan, before, after

    def preview(self, runtime, game, edition, mode, baseline=None):
        with self._locked():
            return self._plan('set', runtime, game, edition, mode, baseline, time.time())[0]

    def preview_revert(self, runtime, game, edition):
        with self._locked():
            return self._plan('revert', runtime, game, edition, None, None, time.time())[0]

    def preview_recipe(self, data, baseline=None):
        recipe = import_recipe(data)
        return self.preview(recipe['runtime'], recipe['gameId'], recipe['editionId'], recipe['mode'], baseline)

    def _new_generation(self, game, edition, mode, data, previous):
        key, generation = _identity(game, edition), uuid.uuid4().hex
        directory = self._path('editions', key, 'generations', generation)
        directory.mkdir(mode=0o700, parents=True, exist_ok=False)
        _atomic(directory / 'config.cfg', data)
        receipt = {'schema': 1, 'gameId': game, 'editionId': edition, 'runtime': dict(RUNTIME),
                   'mode': mode, 'configSha256': _sha(data), 'previous': previous}
        _atomic(directory / 'receipt.json', _json(receipt))
        current = directory
        while current != self.root:
            _sync(current)
            current = current.parent
        _sync(self.root)
        return generation

    def _select(self, key, generation):
        path = self._path('editions', key, 'current.json')
        if generation is None:
            path.unlink(missing_ok=True)
            _sync(path.parent)
        else:
            _atomic(path, _json({'generation': generation}))

    def _restore_pending(self, pending):
        keys = {'schema', 'gameId', 'editionId', 'before', 'after'}
        if type(pending) is not dict or set(pending) != keys or type(pending['schema']) is not int or pending['schema'] != 1:
            raise DisplayError('Invalid recovery journal; preserve workspace for review')
        game, edition = pending['gameId'], pending['editionId']
        key = _identity(game, edition)
        self._generation(game, edition, pending['after'])
        if pending['before'] is not None:
            self._generation(game, edition, pending['before'])
        current = self._pointer(key)
        if current not in (pending['before'], pending['after']):
            raise DisplayError('Selection changed after interruption; recovery refuses to overwrite it')
        if current == pending['after']:
            self._select(key, pending['before'])
        self._path('pending.json').unlink(missing_ok=True)
        _sync(self.root)

    def _switch(self, game, edition, before, after):
        pending = {'schema': 1, 'gameId': game, 'editionId': edition, 'before': before, 'after': after}
        _atomic(self._path('pending.json'), _json(pending))
        try:
            _checkpoint('journal_durable')
            self._select(_identity(game, edition), after)
            _checkpoint('selection_durable')
            self._path('pending.json').unlink()
            _sync(self.root)
        except Exception:
            try:
                self._restore_pending(pending)
            except Exception:
                # Retain/recreate recovery authority when rollback itself cannot finish.
                try:
                    _atomic(self._path('pending.json'), _json(pending))
                except Exception:
                    pass
                raise DisplayError('Transaction or rollback failed; preserve workspace and recover before reuse') from None
            raise DisplayError('Transaction failed; prior selection restored and backups retained') from None

    def confirm(self, plan, token, baseline=None):
        with self._locked(write=True):
            if type(plan) is not dict or type(token) is not str or type(plan.get('token')) is not str or not hmac.compare_digest(plan['token'], token):
                raise DisplayError('Confirmation must name the exact reviewed preview token')
            issued, expires = plan.get('issuedAt'), plan.get('expiresAt')
            if type(issued) not in (int, float) or type(expires) not in (int, float) or not math.isfinite(issued) or not math.isfinite(expires) or expires != issued + 60 or not issued <= time.time() <= expires:
                raise DisplayError('Preview expired or clock changed; review again')
            expected, before_data, after_data = self._plan(plan.get('operation'), plan.get('runtime'),
                plan.get('gameId'), plan.get('editionId'), plan.get('mode'), baseline, issued)
            if plan != expected:
                raise DisplayError('Config or preview changed; review again')
            game, edition, before = plan['gameId'], plan['editionId'], plan['beforeGeneration']
            if plan['operation'] == 'revert':
                target = self._generation(game, edition, before)[0]['previous']
            else:
                previous = before or self._new_generation(game, edition, 'original', before_data, None)
                target = self._new_generation(game, edition, plan['mode'], after_data, previous)
            self._switch(game, edition, before, target)
            return self._current(game, edition)

    def recover(self):
        with self._locked(write=True, allow_pending=True):
            path = self._path('pending.json')
            if not path.exists():
                return {'recovered': False, 'deviceApplied': False}
            self._restore_pending(decode_json(_read(path, 32768)))
            return {'recovered': True, 'priorSelectionRestored': True, 'deviceApplied': False}

    def _current(self, game, edition):
        generation = self._pointer(_identity(game, edition))
        if generation is None:
            return {'gameId': game, 'editionId': edition, 'mode': None, 'deviceApplied': False}
        receipt, _, path = self._generation(game, edition, generation)
        return {**receipt, 'generation': generation, 'configPath': str(path),
                'adapterPoint': {'kind': 'android-intent-extra', 'name': 'CONFIGFILE'},
                'deviceApplied': False, 'installedRuntimeVerified': False}

    def current(self, game, edition):
        with self._locked():
            return self._current(game, edition)

    def recipe(self, game, edition):
        with self._locked():
            current = self._current(game, edition)
            mode = current['mode']
            if mode not in SETTINGS:
                raise DisplayError('No supported display preference is selected')
            return {'schema': 1, 'adapter': ADAPTER, 'runtime': dict(RUNTIME), 'gameId': game,
                    'editionId': edition, 'mode': mode, 'settings': dict(SETTINGS[mode])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('capabilities')
    init = sub.add_parser('init'); init.add_argument('store', type=Path)
    for name in ('preview', 'preview-revert', 'current', 'recipe'):
        item = sub.add_parser(name); item.add_argument('store', type=Path)
        item.add_argument('--game', required=True); item.add_argument('--edition', required=True)
        item.add_argument('--runtime', type=Path, required=name.startswith('preview'))
        if name == 'preview':
            item.add_argument('--mode', choices=('native', 'fit', 'fill', 'crop'), required=True)
            item.add_argument('--baseline', type=Path)
    confirm = sub.add_parser('confirm'); confirm.add_argument('store', type=Path)
    confirm.add_argument('--plan', type=Path, required=True); confirm.add_argument('--token', required=True)
    confirm.add_argument('--baseline', type=Path)
    imported = sub.add_parser('preview-recipe'); imported.add_argument('store', type=Path)
    imported.add_argument('--recipe', type=Path, required=True); imported.add_argument('--baseline', type=Path)
    recover = sub.add_parser('recover'); recover.add_argument('store', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'capabilities':
            result = capabilities(RUNTIME)
        elif args.command == 'init':
            Store.create(args.store); result = {'created': True, 'deviceApplied': False}
        else:
            store = Store(args.store)
            baseline = _read(args.baseline) if getattr(args, 'baseline', None) else None
            if args.command == 'preview':
                result = store.preview(decode_json(_read(args.runtime, 32768)), args.game, args.edition, args.mode, baseline)
            elif args.command == 'preview-revert':
                result = store.preview_revert(decode_json(_read(args.runtime, 32768)), args.game, args.edition)
            elif args.command == 'confirm':
                result = store.confirm(decode_json(_read(args.plan, 32768)), args.token, baseline)
            elif args.command == 'preview-recipe':
                result = store.preview_recipe(_read(args.recipe, 32768), baseline)
            elif args.command == 'recover':
                result = store.recover()
            elif args.command == 'recipe':
                result = store.recipe(args.game, args.edition)
            else:
                result = store.current(args.game, args.edition)
        print(_json(result).decode(), end='')
    except (DisplayError, OSError, TypeError, KeyError, OverflowError) as error:
        message = str(error) if isinstance(error, DisplayError) else 'Unavailable or invalid private input (' + type(error).__name__ + ')'
        parser.exit(1, message + '\n')


if __name__ == '__main__':
    main()
