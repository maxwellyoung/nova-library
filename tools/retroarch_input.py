#!/usr/bin/env python3
"""Reviewed exact-setup RetroArch input configs; no emulator launch or live-profile writes."""
import argparse
import copy
import math
from pathlib import Path
import re
import time

if __package__:
    from . import retroarch_display as tx
else:
    import retroarch_display as tx

RUNTIME=tx.RUNTIME
ADAPTER='retroarch-input-v1'
GROUPS=('sensitivity','deadzone')
FIELDS={'sensitivity':('x','y'),'deadzone':('left','right'),'inversion':('x','y'),
        'triggers':('left','right'),'holdToggle':('aim','sprint','crouch')}
SETTINGS={'sensitivity':'input_analog_sensitivity','deadzone':'input_analog_deadzone'}
SCOPE='Shared analog sticks and analog buttons; not independent axes, sticks or per-button thresholds.'

class InputError(tx.DisplayError):
    pass

def need(value,message):
    if not value:raise InputError(message)

def obj(v,keys):return type(v) is dict and set(v)==set(keys)
def number(v,lo,hi):return type(v) in (int,float) and lo<=v<=hi and math.isfinite(v)
def token(v):return type(v) is str and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.+_-]{0,79}',v)) and v.lower() not in ('unknown','unverified','unspecified','pending','none','null','latest','current')

def binding(v):
    need(obj(v,('editionId','runtimeId','runtimeVersion')),'Exact edition/runtime/version binding required')
    edition=v['editionId']
    need(type(edition) is str and 0<len(edition)<=512 and edition==edition.strip() and not edition.startswith('untagged:')
         and edition not in ('__proto__','constructor','prototype') and not re.search(r'[<>\x00-\x1f\x7f]',edition),'Stable bounded edition identity required')
    try:need(len(edition.encode('utf-16-le'))//2<=512,'Edition identity exceeds bound')
    except UnicodeError:raise InputError('Portable Unicode identity required') from None
    need(token(v['runtimeId']) and token(v['runtimeVersion']),'Known runtime tokens required')
    need(v['runtimeId']==RUNTIME['id'] and v['runtimeVersion']==RUNTIME['version'],'Profile does not name the exact supported runtime/version')
    return copy.deepcopy(v)

def profile(value):
    need(obj(value,('version','profile')) and type(value['version']) is int and value['version']==1,'Version-one single-profile export required')
    p=value['profile'];need(obj(p,('binding','preferences')),'Exact profile envelope required');binding(p['binding'])
    prefs=p['preferences'];need(obj(prefs,FIELDS),'Complete portable preferences required')
    for group,keys in FIELDS.items():need(obj(prefs[group],keys),'Unknown or incomplete preference group')
    need(all(number(v,0.1,10) for v in prefs['sensitivity'].values()),'Sensitivity outside portable bounds')
    need(all(number(v,0,0.95) for v in prefs['deadzone'].values()),'Deadzone outside portable bounds')
    need(all(type(v) is bool for v in prefs['inversion'].values()),'Explicit inversion booleans required')
    need(all(number(v,0,1) for v in prefs['triggers'].values()),'Trigger threshold outside portable bounds')
    need(all(type(v) is str and v in ('hold','toggle') for v in prefs['holdToggle'].values()),'Explicit hold/toggle values required')
    return copy.deepcopy(value)

def decode_profile(data):
    need(type(data) is bytes and len(data)<=16384,'Bounded single-profile JSON required')
    try:decoded=tx.decode_json(data)
    except tx.DisplayError:raise
    except (ValueError,OverflowError,RecursionError):raise InputError('Invalid or overly complex profile JSON') from None
    return profile(decoded)

def identity(key):
    key=binding(key)
    # The inherited transaction indexes by portable short identifiers. Hash the full
    # exact binding instead of truncating long Cloud IDs or aliasing runtime versions.
    return 'input-profile',tx._sha(tx._json(key))

def mapping(value):
    p=profile(value)['profile']['preferences'];supported={};unavailable=[]
    for group in GROUPS:
        vals=list(p[group].values())
        if vals[0]==vals[1]:supported[group]={'key':SETTINGS[group],'value':format(vals[0],'.17g'),'scope':SCOPE}
        else:unavailable.append({'field':group,'reason':'This runtime has one shared value; the two requested values differ.'})
    for group in ('inversion','triggers','holdToggle'):
        unavailable.append({'field':group,'reason':'No mapped exact-runtime adapter; these preferences are not applied.'})
    return {'adapter':ADAPTER,'runtime':dict(RUNTIME),'supported':supported,'unsupported':unavailable,'effectScope':SCOPE,
            'method':'pinned-source-support','installedRuntimeVerified':False,'deviceApplied':False,'gameplayVerified':False}

def selected(value,fields,allow_shared_analog):
    info=mapping(value)
    need(type(fields) is list and fields and len(fields)<=2 and all(type(x) is str and x in GROUPS for x in fields)
         and len(set(fields))==len(fields),'Choose sensitivity and/or deadzone explicitly')
    need(allow_shared_analog is True,'Shared analog-stick/button effect must be explicitly acknowledged')
    need(all(x in info['supported'] for x in fields),'Selected preferences cannot be represented by this runtime')
    return {'profile':profile(value),'fields':sorted(fields),'allowSharedAnalog':True}

def mode(value):
    need(obj(value,('profile','fields','allowSharedAnalog')),'Exact reviewed input choice required')
    return selected(value['profile'],value['fields'],value['allowSharedAnalog'])

def parse_config(data):
    text,values=tx.parse_config(data)
    need(not any(c in text for c in ('\u0085','\u2028','\u2029')),'Unsupported config line separators require review')
    for line in text.split('\n'):
        line=line.rstrip('\r')
        if not line.strip(' \t') or line.lstrip(' \t').startswith('#'):continue
        need(re.fullmatch(r'[ \t]*[A-Za-z0-9_]{1,128}[ \t]*=[ \t]*"[^"\\\r\n]*"[ \t]*(?:#.*)?',line),'Unsupported config whitespace requires review')
    for group,key in SETTINGS.items():
        if key not in values:continue
        try:v=float(values[key])
        except ValueError:raise InputError('Existing analog setting is unrecognised') from None
        lo,hi=(0,0.95) if group=='deadzone' else (0.1,10)
        need(len(values[key])<=32 and number(v,lo,hi),'Existing analog setting is outside supported bounds')
    return text,values

def render_config(data,choice):
    choice=mode(choice);info=mapping(choice['profile']);settings={info['supported'][g]['key']:info['supported'][g]['value'] for g in choice['fields']}
    text,_=parse_config(data);seen=set();out=[]
    for line in text.splitlines(keepends=True):
        match=tx.ASSIGNMENT.fullmatch(line.rstrip('\r\n'));key=match.group(1) if match else None
        if key in settings:
            ending='\r\n' if line.endswith('\r\n') else '\n';out.append(key+' = "'+settings[key]+'"'+ending);seen.add(key)
        else:out.append(line)
    result=''.join(out)
    if result and not result.endswith('\n'):result+='\n'
    result+=''.join(k+' = "'+v+'"\n' for k,v in settings.items() if k not in seen)
    data=result.encode('utf-8');need(len(data)<=tx.LIMIT,'Input config exceeds bound');return data

class Store(tx.Store):
    marker={'schema':1,'kind':ADAPTER}

    def _generation(self,game,edition,generation):
        need(type(generation) is str and tx.GENERATION.fullmatch(generation),'Invalid input config generation')
        tx._identity(game,edition);path=self._path('editions',tx._identity(game,edition),'generations',generation)
        receipt=tx.decode_json(tx._read(path/'receipt.json',32768))
        keys=('schema','gameId','editionId','runtime','mode','configSha256','previous')
        need(obj(receipt,keys) and type(receipt['schema']) is int and receipt['schema']==1
             and receipt['gameId']==game and receipt['editionId']==edition and game=='input-profile','Input generation identity changed')
        tx._runtime(receipt['runtime']);choice=receipt['mode']
        if choice!='original':
            choice=mode(choice);need(identity(choice['profile']['profile']['binding'])==(game,edition),'Input generation binding differs')
        need(type(receipt['configSha256']) is str and tx.SHA256.fullmatch(receipt['configSha256']),'Invalid input config digest')
        need(receipt['previous'] is None or type(receipt['previous']) is str and tx.GENERATION.fullmatch(receipt['previous']),'Invalid prior generation')
        data=tx._read(path/'config.cfg');need(tx._sha(data)==receipt['configSha256'],'Input config changed outside its transaction')
        _,values=parse_config(data)
        if choice!='original':
            info=mapping(choice['profile'])
            need(all(values.get(info['supported'][g]['key'])==info['supported'][g]['value'] for g in choice['fields']),'Selected input settings differ from reviewed preferences')
        return receipt,data,path/'config.cfg'

    def _plan(self,operation,runtime,game,edition,choice,baseline,issued):
        tx._runtime(runtime);need(game=='input-profile','Input workspace requires an exact profile binding')
        current,before=self._basis(game,edition,baseline);parse_config(before)
        if operation=='set':
            choice=mode(choice);need(identity(choice['profile']['profile']['binding'])==(game,edition),'Reviewed input binding differs')
            key=choice['profile']['profile']['binding'];after=render_config(before,choice)
        elif operation=='revert':
            need(current is not None,'No selected input config to revert')
            current_receipt=self._generation(game,edition,current)[0]
            prior=current_receipt['previous'];need(prior is not None,'Already at original input config')
            key=mode(current_receipt['mode'])['profile']['profile']['binding']
            receipt,after,_=self._generation(game,edition,prior);choice=receipt['mode']
        else:raise InputError('Unsupported input operation')
        _,old=parse_config(before);_,new=parse_config(after)
        plan={'schema':1,'adapter':ADAPTER,'operation':operation,'runtime':dict(runtime),'gameId':game,'editionId':edition,'mode':choice,
              'beforeGeneration':current,'beforeSha256':tx._sha(before),'afterSha256':tx._sha(after),'issuedAt':issued,'expiresAt':issued+60,
              'binding':binding(key),
              'notApplied':list(FIELDS) if choice=='original' else [g for g in FIELDS if g not in choice['fields']],
              'changes':{k:{'before':old.get(k),'after':new.get(k)} for k in SETTINGS.values() if old.get(k)!=new.get(k)},
              'effectScope':SCOPE,'deviceApplied':False,'installedRuntimeVerified':False,'gameplayVerified':False}
        plan['token']=tx._sha(tx._json(plan));return plan,before,after

    def preview_profile(self,value,fields,*,baseline=None,allow_shared_analog=False):
        choice=selected(value,fields,allow_shared_analog);game,edition=identity(choice['profile']['profile']['binding'])
        with self._locked():return self._plan('set',RUNTIME,game,edition,choice,baseline,time.time())[0]

    def preview_revert_profile(self,key):
        game,edition=identity(key)
        return super().preview_revert(RUNTIME,game,edition)

    def current_profile(self,key):
        game,edition=identity(key);value=super().current(game,edition)
        return {**value,'binding':binding(key),'effectScope':SCOPE,'gameplayVerified':False}

    def recipe(self,*args):
        raise InputError('Use the strict portable single-profile export; display recipes are not input choices')

    def preview_recipe(self,*args,**kwargs):
        raise InputError('Imported preferences require explicit field selection and shared-effect review')

def main():
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(dest='command',required=True)
    init=subs.add_parser('init');init.add_argument('store',type=Path)
    caps=subs.add_parser('mapping');caps.add_argument('--profile',type=Path,required=True)
    for name in ('preview','current','preview-revert'):
        cmd=subs.add_parser(name);cmd.add_argument('store',type=Path);cmd.add_argument('--profile',type=Path,required=True)
        if name=='preview':
            cmd.add_argument('--field',choices=GROUPS,action='append',required=True);cmd.add_argument('--baseline',type=Path)
            cmd.add_argument('--allow-shared-analog',action='store_true')
    cmd=subs.add_parser('confirm');cmd.add_argument('store',type=Path);cmd.add_argument('--plan',type=Path,required=True);cmd.add_argument('--token',required=True);cmd.add_argument('--baseline',type=Path)
    cmd=subs.add_parser('recover');cmd.add_argument('store',type=Path)
    args=p.parse_args()
    try:
        if args.command=='init':Store.create(args.store);result={'created':True,'deviceApplied':False}
        elif args.command=='mapping':result=mapping(decode_profile(tx._read(args.profile,16384)))
        else:
            store=Store(args.store)
            if args.command=='confirm':result=store.confirm(tx.decode_json(tx._read(args.plan,32768)),args.token,tx._read(args.baseline) if args.baseline else None)
            elif args.command=='recover':result=store.recover()
            else:
                value=decode_profile(tx._read(args.profile,16384))
                if args.command=='preview':result=store.preview_profile(value,args.field,baseline=tx._read(args.baseline) if args.baseline else None,allow_shared_analog=args.allow_shared_analog)
                elif args.command=='current':result=store.current_profile(value['profile']['binding'])
                else:result=store.preview_revert_profile(value['profile']['binding'])
        print(tx._json(result).decode(),end='')
    except (ValueError,OSError,TypeError,KeyError,OverflowError,RecursionError) as e:
        p.exit(1,(str(e) if isinstance(e,tx.DisplayError) else 'Unavailable or invalid private input')+'\n')
if __name__=='__main__':main()
