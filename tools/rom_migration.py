#!/usr/bin/env python3
"""Verified copies and reviewed route candidates; originals and live catalogues stay intact."""
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import stat

if __package__:
    from . import save_passport as paths
else:
    import save_passport as paths

MAX_FILES = 8192
MAX_PLAN = 8 * 1024 * 1024
CHUNK = 1024 * 1024
MAX_ROUTES = 128
DIRECT_IMAGES = {'.bin','.iso','.chd','.rvz','.gcz','.cso','.pbp','.nes','.sfc','.smc',
                 '.gb','.gbc','.gba','.nds','.3ds','.n64','.z64','.v64','.sms','.gg',
                 '.gen','.md','.pce','.a26','.a78','.lnx','.ws','.wsc','.ngp','.ngc','.vb'}


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
    root=Path(root).absolute();paths.directory(root)
    need(root==root.resolve(),'Select a canonical directory without parent traversal')
    return root


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


def copy(plan_value,destination,*,approved_digest,resume=False):
    need(isinstance(plan_value,dict) and plan_value.get('schemaVersion')==1,'Migration plan required')
    body={k:plan_value[k] for k in ['schemaVersion','source','files','bytes']}
    need(digest(body)==plan_value.get('planSha256')==approved_digest,'Reviewed plan digest differs')
    source=canonical(body['source']);destination=Path(destination).absolute();parent=canonical(destination.parent)
    need(destination!=source and source not in destination.parents and destination not in source.parents,'Source and destination must be separate')
    entries=[{'editionId':f['editionId'],'path':f['path']} for f in body['files']]
    need(plan(source,entries)['planSha256']==approved_digest,'Source changed since review')
    marker=destination/'MIGRATION-INCOMPLETE'
    if destination.exists() or destination.is_symlink():
        need(resume and not destination.is_symlink(),'New destination or explicit interrupted-copy resume required')
        canonical(destination)
        if not marker.exists():
            receipt=verify(destination)
            need(receipt['planSha256']==approved_digest and receipt['files']==body['files'],'Completed copy belongs to another plan')
            return receipt
        need(not marker.is_symlink() and marker.stat().st_nlink==1 and marker.read_text()==approved_digest+'\n','Interrupted copy belongs to another plan')
        allowed={item['path'] for item in body['files']}|{'MIGRATION-INCOMPLETE','migration-receipt.json'}
        dirs={str(p) for item in body['files'] for p in Path(item['path']).parents if str(p)!='.'}
        for path in destination.rglob('*'):
            rel=str(path.relative_to(destination));need(not path.is_symlink() and (rel in dirs if path.is_dir() else rel in allowed),'Unmanaged destination files are protected')
    else:
        destination.mkdir(mode=0o700)
        fd=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as f:f.write(approved_digest+'\n');f.flush();os.fsync(f.fileno())
    lock=os.open(marker,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise MigrationError('Migration already in progress') from None
        remaining=0
        for item in body['files']:
            target=destination/item['path'];size=0
            if target.exists():
                info=target.lstat();need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'Linked destination is protected');size=info.st_size
            need(size<=item['bytes'],'Destination exceeds planned bytes');remaining+=item['bytes']-size
        available=os.statvfs(parent).f_bavail*os.statvfs(parent).f_frsize
        need(available>=remaining+1024*1024,'Insufficient destination space; originals retained')
        for item in body['files']:
            source_file=paths.source_file(source,item['path']);target=destination/item['path'];target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            source_fd=os.open(source_file,os.O_RDONLY|os.O_NOFOLLOW)
            try:
                before=os.fstat(source_fd);need(stat.S_ISREG(before.st_mode) and before.st_nlink==1,'Source changed before copy')
                exists=target.exists();flags=os.O_RDWR|os.O_NOFOLLOW|(0 if exists else os.O_CREAT|os.O_EXCL)
                fd=os.open(target,flags,0o600)
                with os.fdopen(fd,'r+b') as out,os.fdopen(source_fd,'rb',closefd=False) as src:
                    size=os.fstat(out.fileno()).st_size
                    need(size<=item['bytes'],'Destination exceeds planned bytes')
                    left=size
                    while left:
                        count=min(left,CHUNK);need(src.read(count)==out.read(count),'Existing destination prefix differs; retained for review');left-=count
                    while chunk:=src.read(CHUNK):out.write(chunk)
                    out.flush();os.fsync(out.fileno())
                need(paths.file_state(before)==paths.file_state(os.fstat(source_fd)),'Source changed during copy')
            finally:os.close(source_fd)
            need(file_hash(target)==(item['bytes'],item['sha256']),'Copied file verification failed; originals retained')
        need(plan(source,entries)['planSha256']==approved_digest,'Source changed before completion')
        receipt={'schemaVersion':1,'planSha256':approved_digest,'files':body['files'],'originalsRetained':True,
                 'catalogueChanged':False,'historyIdentityChanged':False,'deviceApplied':False,'copiedAndVerified':True}
        receipt_path=destination/'migration-receipt.json'
        if receipt_path.exists():
            need(read_plan(receipt_path)==receipt,'Existing receipt differs; retained for review')
        else:
            fd=os.open(receipt_path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'w') as f:json.dump(receipt,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
        marker.unlink()
        d=os.open(destination,os.O_RDONLY)
        try:os.fsync(d)
        finally:os.close(d)
        return receipt
    finally:os.close(lock)


def verify(destination):
    root=canonical(destination);marker=root/'MIGRATION-INCOMPLETE'
    need(not marker.exists() and not marker.is_symlink(),'Incomplete copy is protected')
    receipt=read_plan(root/'migration-receipt.json')
    need(isinstance(receipt,dict) and set(receipt)=={'schemaVersion','planSha256','files','originalsRetained',
         'catalogueChanged','historyIdentityChanged','deviceApplied','copiedAndVerified'},'Complete copy receipt required')
    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion']==1 and receipt['copiedAndVerified'] is True
         and receipt['originalsRetained'] is True and all(receipt[k] is False for k in
         ('catalogueChanged','historyIdentityChanged','deviceApplied')),'Complete copy receipt required')
    need(isinstance(receipt['planSha256'],str) and re.fullmatch('[0-9a-f]{64}',receipt['planSha256']), 'Invalid copy identity')
    need(isinstance(receipt['files'],list) and 0<len(receipt['files'])<=MAX_FILES,'Bounded copy inventory required')
    for item in receipt['files']:
        need(isinstance(item,dict) and set(item)=={'editionId','path','bytes','sha256'},'Exact copied file identity required')
        paths.label(item['editionId']);paths.relative(item['path'])
        need(type(item['bytes']) is int and item['bytes']>=0 and isinstance(item['sha256'],str)
             and re.fullmatch('[0-9a-f]{64}',item['sha256']),'Invalid copied file identity')
        need(file_hash(paths.source_file(root,item['path']))==(item['bytes'],item['sha256']),'Destination changed since copy')
    paths.paths_unique([item['path'] for item in receipt['files']])
    return receipt


def snapshot(path, *, directory=False):
    """Bind a local review to filesystem objects, including same-byte replacements."""
    if directory:
        root=canonical(path);info=root.stat()
        return {'device':info.st_dev,'inode':info.st_ino}
    size,sha=file_hash(path)
    info=Path(path).lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,'Linked route input is protected')
    # Hash again after capturing identity so concurrent edits cannot bind old bytes to a new object.
    need(file_hash(path)==(size,sha) and paths.file_state(info)==paths.file_state(Path(path).lstat()),'Route input changed while reading')
    return {'state':list(paths.file_state(info)),'bytes':size,'sha256':sha}


def catalogue_records(text):
    """Locate simple Pegasus file fields without normalizing unrelated metadata."""
    need(isinstance(text,str) and '\x00' not in text and len(text.encode())<=MAX_PLAN,'Bounded UTF-8 catalogue required')
    lines=text.splitlines(keepends=True);records=[];current=None;collection={};previous=None
    for index,line in enumerate(lines):
        field=re.fullmatch(r'([A-Za-z][A-Za-z0-9_.-]*):[ \t]*(.*?)(?:\r?\n)?',line)
        if field:
            key,value=field.groups();key=key.lower()
            if key=='game':
                current={};records.append(current)
            target=collection if current is None else current
            target.setdefault(key,[]).append((index,value))
            previous=key
        elif line.strip() and not line.lstrip().startswith('#'):
            need(previous not in ('file','files','x-edition-id','launch','collection','game'),'Multiline route identity is unsupported')
    need(0<len(records)<=MAX_FILES and len(collection.get('collection',[]))==1,'Single bounded collection required')
    need(not any('collection' in record for record in records),'Multiple collections need a separate route adapter')
    identities={}
    for record in records:
        ids=record.get('x-edition-id',[])
        need(len(ids)==1,'Every record needs one exact edition identity')
        identity=paths.label(ids[0][1]);need(identity not in identities,'Ambiguous catalogue edition identity')
        identities[identity]=record
    return lines,collection,identities


def route_plan(copy_plan,destination,catalogue,selections):
    """Prepare an inert Pegasus route/rollback candidate from a completed copy.

    Save bindings are explicit operator evidence, not an emulator probe. Only an
    unchanged, independent save directory is supported; content-relative saves
    require a runtime-specific adapter before a route candidate can be made.
    """
    need(isinstance(copy_plan,dict) and copy_plan.get('schemaVersion')==1,'Original copy plan required')
    source=canonical(copy_plan['source']);destination=canonical(destination)
    need(destination!=source and source not in destination.parents and destination not in source.parents,'Separate migration roots required')
    receipt=verify(destination)
    entries=[{'editionId':item['editionId'],'path':item['path']} for item in receipt['files']]
    fresh=plan(source,entries)
    need(fresh==copy_plan and receipt['planSha256']==fresh['planSha256'] and receipt['files']==fresh['files'],
         'Copy receipt and current source must match the reviewed copy plan')
    need(isinstance(selections,list) and 0<len(selections)<=MAX_ROUTES,'Explicit bounded route selection required')
    catalogue=Path(catalogue).absolute();canonical(catalogue.parent)
    catalogue_state=snapshot(catalogue)
    with paths.open_archive(catalogue) as stream:
        text=stream.read(MAX_PLAN+1).decode('utf-8')
    need(snapshot(catalogue)==catalogue_state,'Catalogue changed while reading')
    lines,collection,records=catalogue_records(text)
    inventory={item['path']:item for item in receipt['files']};selected=set();changes=[];bindings=[]
    file_states={}
    for selection in selections:
        need(isinstance(selection,dict) and set(selection)=={'editionId','path','familyPaths','saveBinding'},'Exact route and save binding required')
        edition=paths.label(selection['editionId']);name=paths.relative(selection['path'])
        need(edition not in selected and edition in records,'Missing or duplicate selected edition');selected.add(edition)
        family=selection['familyPaths']
        need(isinstance(family,list) and 0<len(family)<=MAX_FILES and name in family,'Explicit complete launch family required')
        paths.paths_unique(family)
        need(set(family)=={p for p,item in inventory.items() if item['editionId']==edition},'Entire exact-edition copy family required')
        for member in family:
            need(member in inventory and inventory[member]['editionId']==edition,'Unverified or mismatched launch family')
            need(Path(member).suffix.lower() in DIRECT_IMAGES|{'.m3u'}, 'Content format needs a tested route adapter')
            file_states[member]={'source':snapshot(paths.source_file(source,member)),
                                 'destination':snapshot(paths.source_file(destination,member))}
            need(all((state['bytes'],state['sha256'])==(inventory[member]['bytes'],inventory[member]['sha256'])
                     for state in file_states[member].values()),'Launch family changed after copy verification')
        playlists=[p for p in family if Path(p).suffix.lower()=='.m3u']
        if playlists:
            need(playlists==[name],'Only one explicitly launched playlist is supported')
            playlist=paths.source_file(source,name)
            need(playlist.stat().st_size<=128*1024,'Playlist exceeds bound')
            members=[]
            for line in playlist.read_text(encoding='utf-8-sig').splitlines():
                if not line.strip() or line.startswith('#'):continue
                paths.relative(line)
                member=str(Path(name).parent/line);paths.relative(member);members.append(member)
            paths.paths_unique(members)
            need(set(members)==set(family)-{name},'Playlist references must match the complete copied family')
        else:
            need(family==[name],'Companion files need an explicit supported playlist')
        record=records[edition]
        need(len(record.get('file',[]))==1 and 'files' not in record,'Single exact launch file required')
        index,old=record['file'][0]
        need(old==str(source/name),'Catalogue source route differs from exact copied path')
        launch=record.get('launch',collection.get('launch',[]))
        need(len(launch)==1 and launch[0][1].count('{file.path}')==1,'File-path launch adapter required')
        need(str(source) not in launch[0][1] and str(destination) not in launch[0][1], 'Hard-coded content roots need a route adapter')
        binding=selection['saveBinding']
        need(isinstance(binding,dict) and set(binding)=={'mode','identity','directory','evidence'},'Explicit independent save-path evidence required')
        need(binding['mode']=='explicit-independent-directory','Content-relative or unknown save paths are unsupported')
        identity=paths.identity(binding['identity']);need(identity['editionId']==edition,'Save edition differs from route edition')
        need(all(label.casefold() not in paths.UNKNOWN_LABELS for label in
                 (identity['editionId'],identity['recipeId'],*identity['runtime'].values())),'Known save runtime identity required')
        paths.label(binding['evidence']);need(binding['evidence'].casefold() not in paths.UNKNOWN_LABELS,'Save binding evidence required')
        need(isinstance(binding['directory'],str) and Path(binding['directory']).is_absolute(),'Absolute save directory required')
        save_root=canonical(binding['directory'])
        need(save_root!=source and save_root!=destination and source not in save_root.parents and destination not in save_root.parents
             and save_root not in source.parents and save_root not in destination.parents,'Save directory must be independent of both content roots')
        bindings.append({'editionId':edition,'identity':identity,'directory':str(save_root),
                         'directoryIdentity':snapshot(save_root,directory=True),'evidence':binding['evidence']})
        ending='\r\n' if lines[index].endswith('\r\n') else ('\n' if lines[index].endswith('\n') else '')
        target=str(destination/name)
        need(all(re.fullmatch(r'[/\w .+-]+',p) for p in (old,target)), 'Content path needs a tested quoting adapter')
        lines[index]='file: '+target+ending
        changes.append({'editionId':edition,'before':old,'after':target,'familyPaths':family})
    after=''.join(lines)
    body={'schemaVersion':1,'kind':'pegasus-route-candidate','copyPlan':copy_plan,'destination':str(destination),
          'sourceIdentity':snapshot(source,directory=True),'destinationIdentity':snapshot(destination,directory=True),
          'receiptIdentity':snapshot(destination/'migration-receipt.json'),'catalogue':str(catalogue),
          'catalogueIdentity':catalogue_state,'selections':selections,'files':file_states,'saveBindings':bindings,
          'changes':changes,'before':text,'after':after,'originalsRetained':True,'catalogueChanged':False,
          'historyIdentityChanged':False,'deviceApplied':False,'runtimeSaveContinuityVerified':False}
    need(len(json.dumps(body).encode())<MAX_PLAN-1024,'Route review exceeds bound; select a smaller catalogue or family')
    return {**body,'routePlanSha256':digest(body)}


def review_routes(value,*,approved_digest):
    """Revalidate a review and return forward/rollback text without applying either."""
    need(isinstance(value,dict) and value.get('kind')=='pegasus-route-candidate','Route candidate plan required')
    body={k:v for k,v in value.items() if k!='routePlanSha256'}
    need(digest(body)==value.get('routePlanSha256')==approved_digest,'Reviewed route digest differs')
    fresh=route_plan(value['copyPlan'],value['destination'],value['catalogue'],value['selections'])
    need(fresh==value,'Route inputs changed since review')
    return {'candidate':fresh['after'],'rollback':fresh['before'],'planSha256':approved_digest,
            'catalogueChanged':False,'deviceApplied':False,'runtimeSaveContinuityVerified':False}


def private_output(path,value):
    path=Path(path).absolute();canonical(path.parent)
    need(not any((p/'.git').exists() for p in (path.parent,*path.parents)),'Private migration plans stay outside repositories')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())


def read_plan(path):
    with paths.open_archive(path) as source:
        need(os.fstat(source.fileno()).st_size <= MAX_PLAN, "Migration plan exceeds bound")
        return paths.parse_json(source.read(MAX_PLAN+1))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);commands=parser.add_subparsers(dest='command',required=True)
    a=commands.add_parser('plan');a.add_argument('source',type=Path);a.add_argument('--entries',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=commands.add_parser('copy');a.add_argument('--plan',type=Path,required=True);a.add_argument('--destination',type=Path,required=True);a.add_argument('--approve-digest',required=True);a.add_argument('--resume',action='store_true')
    a=commands.add_parser('verify');a.add_argument('destination',type=Path)
    a=commands.add_parser('route-plan');a.add_argument('--plan',type=Path,required=True);a.add_argument('--destination',type=Path,required=True);a.add_argument('--catalogue',type=Path,required=True);a.add_argument('--selections',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=commands.add_parser('route-review');a.add_argument('--plan',type=Path,required=True);a.add_argument('--approve-digest',required=True);a.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='plan':
            entries=read_plan(args.entries);report=plan(args.source,entries)
            private_output(args.output,report)
            print('Private copy plan prepared; no game or catalogue changed.')
        elif args.command=='copy':
            report=read_plan(args.plan);copy(report,args.destination,approved_digest=args.approve_digest,resume=args.resume);print('Selected files copied and verified; originals and catalogue retained.')
        elif args.command=='verify':verify(args.destination);print('Destination files match the retained copy receipt.')
        elif args.command=='route-plan':
            report=route_plan(read_plan(args.plan),args.destination,args.catalogue,read_plan(args.selections))
            private_output(args.output,report);print('Private route candidate and rollback prepared; live catalogue unchanged.')
        else:
            report=review_routes(read_plan(args.plan),approved_digest=args.approve_digest)
            private_output(args.output,report);print('Route candidate and rollback revalidated; live catalogue unchanged.')
    except (ValueError,OSError,KeyError,TypeError):parser.exit(1,'Migration refused or incomplete; originals retained and catalogue unchanged.\n')


if __name__=='__main__':main()
