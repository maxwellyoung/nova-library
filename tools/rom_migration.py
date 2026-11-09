#!/usr/bin/env python3
"""Verified copy into a new destination; never delete originals or rewrite a catalogue."""
import hashlib
import json
import os
from pathlib import Path
import stat

if __package__:
    from . import save_passport as paths
else:
    import save_passport as paths

MAX_FILES = 8192
MAX_PLAN = 8 * 1024 * 1024
CHUNK = 1024 * 1024


class MigrationError(ValueError):
    pass


def need(ok,message):
    if not ok:raise MigrationError(message)


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def file_hash(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'Linked or non-regular source is protected')
        h=hashlib.sha256()
        with os.fdopen(fd,'rb',closefd=False) as f:
            while chunk:=f.read(CHUNK):h.update(chunk)
        need(paths.file_state(before)==paths.file_state(os.fstat(fd)),'File changed while reading')
        return before.st_size,h.hexdigest()
    finally:os.close(fd)


def canonical(root):
    root=Path(root).absolute();paths.directory(root);return root


def plan(source,entries):
    source=canonical(source)
    need(isinstance(entries,list) and 0<len(entries)<=MAX_FILES,'Explicit bounded file selection required')
    names=[];files=[]
    for entry in entries:
        need(isinstance(entry,dict) and set(entry)=={'editionId','path'},'Exact edition/file selection required')
        paths.label(entry['editionId']);paths.relative(entry['path']);names.append(entry['path'])
        need(entry['path'].split('/')[0].casefold() not in ('migration-incomplete','migration-receipt.json'),'Migration control names are reserved')
        file=paths.source_file(source,entry['path']);size,sha=file_hash(file)
        files.append({'editionId':entry['editionId'],'path':entry['path'],'bytes':size,'sha256':sha})
    paths.paths_unique(names)
    body={'schemaVersion':1,'source':str(source),'files':files,'bytes':sum(f['bytes'] for f in files)}
    return {**body,'planSha256':digest(body),'originalsRetained':True,'catalogueChanged':False,'deviceApplied':False}


def copy(plan_value,destination,*,approved_digest):
    need(isinstance(plan_value,dict) and plan_value.get('schemaVersion')==1,'Migration plan required')
    body={k:plan_value[k] for k in ['schemaVersion','source','files','bytes']}
    need(digest(body)==plan_value.get('planSha256')==approved_digest,'Reviewed plan digest differs')
    source=canonical(body['source']);destination=Path(destination).absolute()
    need(not destination.exists() and not destination.is_symlink(),'New empty destination required')
    parent=canonical(destination.parent)
    need(destination!=source and source not in destination.parents and destination not in source.parents,'Source and destination must be separate')
    # Refresh every source before allocating or publishing any destination files.
    entries=[{'editionId':f['editionId'],'path':f['path']} for f in body['files']]
    fresh=plan(source,entries);need(fresh['planSha256']==approved_digest,'Source changed since review')
    available=os.statvfs(parent).f_bavail*os.statvfs(parent).f_frsize
    need(available>=body['bytes']+1024*1024,'Insufficient destination space; originals retained')
    destination.mkdir(mode=0o700)
    marker=destination/'MIGRATION-INCOMPLETE';marker.write_text(approved_digest+'\n');marker.chmod(0o600)
    for item in body['files']:
        source_file=paths.source_file(source,item['path']);target=destination/item['path'];target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        source_fd=os.open(source_file,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(source_fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'Source changed before copy')
            fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as out,os.fdopen(source_fd,'rb',closefd=False) as src:
                while chunk:=src.read(CHUNK):out.write(chunk)
                out.flush();os.fsync(out.fileno())
            need(paths.file_state(before)==paths.file_state(os.fstat(source_fd)),'Source changed during copy')
        finally:os.close(source_fd)
        need(file_hash(target)==(item['bytes'],item['sha256']),'Copied file verification failed; originals retained')
    # Recheck sources too, so a changed source never receives a complete receipt.
    need(plan(source,entries)['planSha256']==approved_digest,'Source changed before completion')
    receipt={'schemaVersion':1,'planSha256':approved_digest,'files':body['files'],'originalsRetained':True,
             'catalogueChanged':False,'historyIdentityChanged':False,'deviceApplied':False,'copiedAndVerified':True}
    fd=os.open(destination/'migration-receipt.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(receipt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
    marker.unlink()
    d=os.open(destination,os.O_RDONLY)
    try:os.fsync(d)
    finally:os.close(d)
    return receipt


def verify(destination):
    root=canonical(destination);need(not (root/'MIGRATION-INCOMPLETE').exists(),'Incomplete copy is protected')
    receipt=paths.read_json(root/'migration-receipt.json')
    need(receipt.get('schemaVersion')==1 and receipt.get('copiedAndVerified') is True,'Complete copy receipt required')
    for item in receipt['files']:
        paths.relative(item['path']);need(file_hash(paths.source_file(root,item['path']))==(item['bytes'],item['sha256']),'Destination changed since copy')
    return receipt


def read_plan(path):
    with paths.open_archive(path) as source:
        need(os.fstat(source.fileno()).st_size <= MAX_PLAN, "Migration plan exceeds bound")
        return paths.parse_json(source.read(MAX_PLAN+1))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    a=commands.add_parser('plan');a.add_argument('source',type=Path);a.add_argument('--entries',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=commands.add_parser('copy');a.add_argument('--plan',type=Path,required=True);a.add_argument('--destination',type=Path,required=True);a.add_argument('--approve-digest',required=True)
    a=commands.add_parser('verify');a.add_argument('destination',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='plan':
            entries=read_plan(args.entries);report=plan(args.source,entries)
            need(not any((p/'.git').exists() for p in (args.output.absolute().parent,*args.output.absolute().parents)),'Private migration plans stay outside repositories')
            fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as f:json.dump(report,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
            print('Private copy plan prepared; no game or catalogue changed.')
        elif args.command=='copy':
            report=read_plan(args.plan);copy(report,args.destination,approved_digest=args.approve_digest);print('Selected files copied and verified; originals and catalogue retained.')
        else:verify(args.destination);print('Destination files match the retained copy receipt.')
    except (ValueError,OSError,KeyError,TypeError):parser.exit(1,'Migration refused or incomplete; originals retained and catalogue unchanged.\n')


if __name__=='__main__':main()
