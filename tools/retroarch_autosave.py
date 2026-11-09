#!/usr/bin/env python3
"""Prepare a private, reversible autosave profile; never apply it to an emulator."""
import hashlib
import json
import os
from pathlib import Path
import re

if __package__:
    from .retroarch_display import RUNTIME, render_config, SETTINGS as DISPLAY_SETTINGS
else:
    from retroarch_display import RUNTIME, render_config, SETTINGS as DISPLAY_SETTINGS

SETTINGS = {'autosave_interval':'30', 'savestate_auto_save':'true', 'savestate_auto_load':'false'}
LIMIT = 1024 * 1024


class AutosaveError(ValueError):
    pass


def need(value,message):
    if not value:raise AutosaveError(message)


def prepare(source,runtime,edition_id,*,display_mode=None):
    need(runtime == RUNTIME and type(runtime) is dict, 'Exact supported RetroArch source identity required')
    need(isinstance(edition_id,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,199}',edition_id), 'Exact edition identity required')
    need(isinstance(source,bytes) and 0 < len(source) <= LIMIT,'Bounded baseline config required')
    try:text=source.decode('utf-8')
    except UnicodeError:raise AutosaveError('Text baseline required') from None
    need('\x00' not in text,'Text baseline required')
    observed={};lines=text.splitlines();positions={}
    for i,line in enumerate(lines):
        need(not re.match(r'\s*#\s*include\b',line,re.I),'Included configs require effective-setting review')
        if not line.strip() or line.lstrip().startswith('#'):continue
        match=re.fullmatch(r'\s*([A-Za-z0-9_]+)\s*=\s*"([^"\\\r\n]*)"\s*(?:#.*)?',line)
        need(match is not None,'Unrecognised baseline syntax requires review')
        key,value=match.groups();need(key not in observed,'Duplicate settings require review');observed[key]=value;positions[key]=i
    need(observed.get('auto_overrides_enable')=='false' and observed.get('config_save_on_exit')=='false',
         'Explicit flat profile with overrides and config-save disabled required')
    for key in SETTINGS:
        old=observed.get(key)
        if old is not None:
            need(bool(re.fullmatch(r'[0-9]{1,6}',old)) if key=='autosave_interval' else old in ('true','false'), 'Unrecognised autosave setting')
    if display_mode is not None:
        # The existing exact-version display adapter supplies only its reviewed Fit/Fill delta.
        displayed=render_config(source,display_mode)
        candidate,receipt=prepare(displayed,runtime,edition_id)
        receipt['baselineSha256']=hashlib.sha256(source).hexdigest()
        receipt['changes']=[{'key':key,'before':observed.get(key),'after':value} for key,value in DISPLAY_SETTINGS[display_mode].items() if observed.get(key)!=value]+receipt['changes']
        receipt['displayMode']=display_mode
        receipt['displayCandidateSha256']=hashlib.sha256(displayed).hexdigest()
        receipt['displayChangesSource']='retroarch-display-v1; Fit/Fill source settings only'
        return candidate,receipt
    changes=[]
    for key,value in SETTINGS.items():
        if observed.get(key)!=value:changes.append({'key':key,'before':observed.get(key),'after':value})
        replacement=f'{key} = "{value}"'
        if key in positions:lines[positions[key]]=replacement
        else:lines.append(replacement)
    candidate=('\n'.join(lines)+'\n').encode()
    receipt={'schemaVersion':1,'editionId':edition_id,'runtime':dict(RUNTIME),'baselineSha256':hashlib.sha256(source).hexdigest(),
             'candidateSha256':hashlib.sha256(candidate).hexdigest(),'changes':changes,'deviceApplied':False,'runtimeVerified':False,
             'automaticCloudRestore':False,'semantics':['Flush core-exposed nonvolatile memory every 30 seconds where supported.',
             'Request one automatic state on a clean supported content exit; this is not periodic state capture or crash protection.',
             'Never automatically load the state; core/version compatibility still needs review.',
             'The auto-state slot can be replaced; back up existing auto states and native saves before application.']}
    return candidate,receipt


def write_candidate(parent,name,source,runtime,edition_id,*,display_mode=None):
    parent=Path(parent).absolute();target=parent/name
    need(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',name),'Plain new profile name required')
    need(parent.is_dir() and not any(p.is_symlink() for p in (parent,*parent.parents)),'Canonical parent required')
    need(not any((p/'.git').exists() for p in (parent,*parent.parents)),'Private profiles must stay outside repositories')
    candidate,receipt=prepare(source,runtime,edition_id,display_mode=display_mode)
    target.mkdir(mode=0o700)
    try:
        for name,data in [('baseline.cfg',source),('candidate.cfg',candidate),('receipt.json',(json.dumps(receipt,indent=2)+'\n').encode())]:
            fd=os.open(target/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        receipt['complete']=True
        # An exclusive completion marker distinguishes interrupted preparation.
        fd=os.open(target/'COMPLETE',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:f.write(receipt['candidateSha256']+'\n');f.flush();os.fsync(f.fileno())
    except BaseException:
        # Partial files are retained, never promoted to a deployable profile.
        raise
    return receipt


def verify_candidate(folder):
    folder=Path(folder).absolute()
    need(folder.is_dir() and not any(p.is_symlink() for p in (folder,*folder.parents)),'Canonical private profile required')
    files=['baseline.cfg','candidate.cfg','receipt.json','COMPLETE']
    need({p.name for p in folder.iterdir()}==set(files),'Complete managed profile required')
    for name in files:
        p=folder/name;s=p.lstat()
        import stat
        need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==os.geteuid() and not s.st_mode&0o077 and s.st_size<=LIMIT,'Private bounded profile files required')
    receipt=json.loads((folder/'receipt.json').read_text());baseline=(folder/'baseline.cfg').read_bytes();candidate=(folder/'candidate.cfg').read_bytes()
    need(hashlib.sha256(baseline).hexdigest()==receipt['baselineSha256'] and hashlib.sha256(candidate).hexdigest()==receipt['candidateSha256'],'Profile bytes changed')
    need((folder/'COMPLETE').read_text()==receipt['candidateSha256']+'\n','Profile completion differs')
    expected,_=prepare(baseline,receipt['runtime'],receipt['editionId'],display_mode=receipt.get('displayMode'))
    need(expected==candidate,'Profile no longer matches the reviewed adapter')
    return receipt


def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('prepare');a.add_argument('--baseline',type=Path,required=True);a.add_argument('--parent',type=Path,required=True);a.add_argument('--name',required=True);a.add_argument('--edition',required=True);a.add_argument('--display-mode',choices=['fit','fill'])
    a=sub.add_parser('verify');a.add_argument('folder',type=Path)
    args=p.parse_args()
    try:
        if args.command=='prepare':
            need(args.baseline.is_file() and not args.baseline.is_symlink() and args.baseline.stat().st_size<=LIMIT,'Bounded regular baseline required')
            write_candidate(args.parent,args.name,args.baseline.read_bytes(),RUNTIME,args.edition,display_mode=args.display_mode);print('Private autosave candidate prepared; emulator unchanged.')
        else:verify_candidate(args.folder);print('Private autosave candidate and baseline verified; not applied.')
    except (ValueError,OSError,KeyError,TypeError):p.exit(1,'Autosave preparation refused; original profile and saves unchanged.\n')


if __name__=='__main__':main()
