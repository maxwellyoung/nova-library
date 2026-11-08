#!/usr/bin/env python3
"""Prepare a private RetroArch cloud-sync config without modifying its input.

Credentials arrive on stdin as JSON. The output contains the native client's
password and is created owner-only; it must never be committed or published.
Apply only after backing up actual memory cards and closing RetroArch.
"""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit


class SyncError(ValueError):
    """A fixed diagnostic that never includes credentials or private input."""


def prepare(source, endpoint, username, password, enable=False):
    if enable is not False:
        raise SyncError('Automatic save sync remains disabled until the installed pre-launch barrier and copied-save restore are verified')
    if not isinstance(source,str) or not isinstance(endpoint,str) or any(ord(c)<=32 or ord(c)==127 for c in endpoint):
        raise SyncError('Save sync requires the approved HTTPS server origin')
    try:
        url=urlsplit(endpoint)
        port=url.port
    except ValueError:
        raise SyncError('Save sync requires a valid HTTPS server origin') from None
    if url.scheme!='https' or not url.hostname or url.username is not None or url.password is not None or '?' in endpoint or '#' in endpoint or url.path not in ('','/'):
        raise SyncError('Save sync requires the approved HTTPS server origin')
    if port == 0 or url.netloc.endswith(':'):
        raise SyncError('Save sync requires a valid HTTPS server origin')
    def quoted(value):
        if not isinstance(value,str) or not value or any(ord(c)<32 or ord(c)==127 for c in value) or '"' in value or '\\' in value:
            raise SyncError('Credential needs a valid single-line RetroArch string')
        return '"'+value+'"'
    safety_keys={'savefiles_in_content_dir','savestates_in_content_dir'}
    current={}
    for line in source.splitlines():
        if re.match(r'^\s*#\s*include\b',line,re.I):
            raise SyncError('Included configurations require an explicit layout review before cloud sync')
        key_match=re.match(r'^\s*([a-zA-Z0-9_]+)\s*=',line)
        key=key_match.group(1) if key_match else None
        if key in safety_keys:
            if key in current:
                raise SyncError('Duplicate save-layout setting; migration requirements are ambiguous')
            value_match=re.fullmatch(r'\s*[a-zA-Z0-9_]+\s*=\s*"(true|false)"\s*(?:#.*)?',line)
            if not value_match:
                raise SyncError('Unrecognized save-layout setting; migration requirements are unknown')
            current[key]=value_match.group(1)
            if current[key]=='true':
                raise SyncError('Content-directory saves need a backed-up migration before cloud sync')
    # Keep the existing save layout: changing sorting here could orphan a memory card.
    settings={
        'cloud_sync_enable':'"false"','cloud_sync_driver':'"webdav"',
        'webdav_url':quoted(endpoint.rstrip('/')+'/api/sync/retroarch/'),
        'webdav_username':quoted(username),'webdav_password':quoted(password),
        'cloud_sync_destructive':'"false"','cloud_sync_sync_saves':'"true"',
        'cloud_sync_sync_configs':'"false"','cloud_sync_sync_thumbs':'"false"',
        'cloud_sync_sync_system':'"false"',
    }
    seen=set();lines=[]
    for line in source.splitlines():
        match=re.match(r'^\s*([a-zA-Z0-9_]+)\s*=',line)
        key=match.group(1) if match else None
        if key in settings:
            if key in seen: raise SyncError('Duplicate cloud setting; configuration is ambiguous')
            seen.add(key);lines.append(key+' = '+settings[key])
        else: lines.append(line)
    lines.extend(k+' = '+v for k,v in settings.items() if k not in seen)
    return '\n'.join(lines)+'\n'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--endpoint',required=True);p.add_argument('--enable-after-launch-barrier-verified',action='store_true');a=p.parse_args()
    try:
        if a.output.resolve().is_relative_to(Path(__file__).resolve().parents[1]):raise SyncError('Private emulator credentials cannot be written inside this repository')
        secret=json.load(__import__('sys').stdin)
        text=prepare(a.source.read_text(),a.endpoint,secret['username'],secret['password'],a.enable_after_launch_barrier_verified)
        # O_EXCL also refuses symlinks and avoids replacing an existing checkpoint/config.
        fd=os.open(a.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f: f.write(text)
        print('Private candidate written. Emulator configuration is unchanged.')
    except (ValueError,OSError,KeyError,TypeError) as e:
        reason=str(e) if isinstance(e,SyncError) else 'Invalid or unavailable private input ('+type(e).__name__+')'
        p.exit(1,reason+'. No existing configuration was replaced.\n')
