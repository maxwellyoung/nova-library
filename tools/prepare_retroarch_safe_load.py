#!/usr/bin/env python3
"""Prepare a pinned RetroArch source guard; never build, install or load a state."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / 'native/retroarch-safe-load'
MAX_SOURCE = 256 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Pinned source anchor differs')
    return text.replace(old, new, 1)


def function(text, signature):
    if text.count(signature) != 1:
        raise ValueError('Pinned function boundary differs')
    start = text.index(signature)
    end = text.index('\n}\n', start) + 3
    return text[start:end]


def guard_text(text):
    """The same transform applies to pinned source and its exact test excerpts."""
    signature = 'bool content_undo_load_state(void)'
    before = function(text, signature)
    after = once(before,
        '   struct string_list *savefile_list = (struct string_list*)savefile_ptr_get();\n',
        '   struct string_list *savefile_list = (struct string_list*)savefile_ptr_get();\n\n'
        '   if (!undo_load_buf.data || !undo_load_buf.size)\n      return false;\n')
    start = after.index('   /* We need to make a temporary copy of the buffer, to allow the swap below */')
    end = after.index('    /* Flush back. */', start)
    after = after[:start] + '''   /* Keep the old state until a current-state backup actually succeeds. */
   temp_data = malloc(undo_load_buf.size);
   if (temp_data)
   {
      temp_data_size = undo_load_buf.size;
      memcpy(temp_data, undo_load_buf.data, temp_data_size);
      ret = content_save_state("RAM", false);
      if (ret)
         ret = content_deserialize_state(temp_data, temp_data_size);
      free(temp_data);
      temp_data = NULL;
   }

''' + after[end:]
    text = once(text, before, after)
    signature = 'static void content_load_state_cb('
    before = function(text, signature)
    after = once(before,
        '   content_save_state("RAM", false);\n\n   ret = content_deserialize_state(buf, _len);',
        '   ret = content_save_state("RAM", false);\n   if (ret)\n      ret = content_deserialize_state(buf, _len);')
    text = once(text, before, after)
    signature = 'bool content_save_state(const char *path, bool save_to_disk)'
    before = function(text, signature)
    after = once(before, '   else\n   {\n      if (!data)', '   else\n   {\n      void *replacement = NULL;\n      if (!data)')
    start = after.index('      /* If we were holding onto an old state already, clean it up first */')
    end = after.index('      undo_load_buf.size = _len;', start)
    after = after[:start] + '''      /* Allocate first: failed replacement must retain the previous undo. */
      if (!(replacement = malloc(_len)))
      {
         free(data);
         return false;
      }
      memcpy(replacement, data, _len);
      free(data);
      free(undo_load_buf.data);
      undo_load_buf.data = replacement;
''' + after[end:]
    return once(text, before, after)


def prepare(data):
    spec = json.loads((MODULE / 'source.json').read_text())
    if not isinstance(data, bytes) or not 0 < len(data) <= MAX_SOURCE or sha(data) != spec['beforeSha256']:
        raise ValueError('Exact pinned RetroArch task source required')
    if sha((MODULE / 'safe-load.patch').read_bytes()) != spec['patchSha256']:
        raise ValueError('Reviewed source patch changed')
    candidate = guard_text(data.decode('utf-8')).encode('utf-8')
    if sha(candidate) != spec['afterSha256']:
        raise ValueError('Guard result differs from its reviewed source hash')
    return candidate, spec


def receipt(spec):
    return {'schemaVersion': 1, 'adapter': spec['adapter'], 'sourceCommit': spec['commit'],
            'beforeSha256': spec['beforeSha256'], 'afterSha256': spec['afterSha256'],
            'built': False, 'installed': False, 'runtimeRestoreVerified': False,
            'durableCheckpoint': False, 'scope': ['disk-load-callback', 'undo-load', 'RAM-backup-replacement']}


def write_candidate(source, output):
    source, output = Path(source), Path(output).absolute()
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_SOURCE:
        raise ValueError('Bounded ordinary source file required')
    baseline = source.read_bytes()
    candidate, spec = prepare(baseline)
    parent = output.parent
    if not parent.is_dir() or any(p.is_symlink() for p in (parent, *parent.parents)) or any((p / '.git').exists() for p in (parent, *parent.parents)):
        raise ValueError('Use a new review directory outside repositories')
    output.mkdir(mode=0o700)
    record = receipt(spec)
    for name, data in [('baseline.c', baseline), ('candidate.c', candidate),
                       ('receipt.json', (json.dumps(record, indent=2)+'\n').encode())]:
        with (output / name).open('xb') as stream:
            os.chmod(stream.fileno(), 0o600); stream.write(data); stream.flush(); os.fsync(stream.fileno())
    if sha((output / 'baseline.c').read_bytes()) != spec['beforeSha256']:
        raise ValueError('Source changed during preparation; incomplete candidate retained')
    with (output / 'COMPLETE').open('x') as stream:
        os.chmod(stream.fileno(), 0o600); stream.write(spec['afterSha256']+'\n')
    return record


def verify_candidate(folder):
    folder = Path(folder).absolute()
    names = {'baseline.c', 'candidate.c', 'receipt.json', 'COMPLETE'}
    if not folder.is_dir() or any(p.is_symlink() for p in (folder, *folder.parents)) or {p.name for p in folder.iterdir()} != names:
        raise ValueError('Complete canonical candidate required')
    for path in [folder, *[folder / name for name in names]]:
        info = path.lstat()
        if info.st_uid != os.geteuid() or info.st_mode & 0o077 or (path != folder and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_SOURCE)):
            raise ValueError('Private ordinary candidate files required')
    candidate, spec = prepare((folder / 'baseline.c').read_bytes())
    record = json.loads((folder / 'receipt.json').read_text())
    if (folder / 'candidate.c').read_bytes() != candidate or (folder / 'COMPLETE').read_text() != spec['afterSha256']+'\n' or record != receipt(spec):
        raise ValueError('Candidate source or preparation receipt changed')
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    command = commands.add_parser('prepare')
    command.add_argument('--source', required=True, type=Path)
    command.add_argument('--output', required=True, type=Path)
    command = commands.add_parser('verify')
    command.add_argument('folder', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'prepare': write_candidate(args.source, args.output)
        else: verify_candidate(args.folder)
        print('Pinned source candidate verified; no emulator or save changed.')
    except (ValueError, OSError, UnicodeError):
        parser.exit(1, 'Source preparation refused or incomplete; existing targets preserved.\n')


if __name__ == '__main__': main()
