#!/usr/bin/env python3
"""Immutable private save transport. No emulator import, launch or auto-restore."""
import base64
from contextlib import contextmanager
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
import stat
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request

if __package__:
    from . import save_sync_model as sync
    from . import save_passport as passport
else:
    import save_sync_model as sync
    import save_passport as passport

MAX_ARCHIVE = 64 * 1024 * 1024
MAX_TOTAL = 1024 * 1024 * 1024
MAX_REVISIONS = 4096


class VaultError(ValueError):
    """Fixed diagnostics, without save metadata, source paths or account values."""


def need(condition, message):
    if not condition:
        raise VaultError(message)


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def decode(data):
    try:
        value = passport.parse_json(data)
        need(encode(value) is not None, 'Invalid save metadata')
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise VaultError('Invalid save metadata') from None


class Vault:
    """SQLite is the atomic blob/metadata/ack owner. Revisions are never replaced."""
    def __init__(self, root, *, create=False):
        self.root = Path(root).absolute()
        need(not any(p.is_symlink() for p in (self.root, *self.root.parents)), 'Canonical private directory required')
        need(not any((p / '.git').exists() for p in (self.root, *self.root.parents)), 'Save vault must remain outside repositories')
        if create:
            need(self.root.parent.is_dir(), 'Existing private parent required')
            self.root.mkdir(mode=0o700)
            fd = os.open(self.root/'vault.sqlite3', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        need(self.root.is_dir() and self.root.stat().st_uid == os.geteuid() and self.root.stat().st_mode & 0o077 == 0,
             'Save vault must be private and owned')
        for p in self.root.iterdir():
            need(p.name in ('vault.sqlite3', 'vault.sqlite3-journal', 'vault.sqlite3-wal', 'vault.sqlite3-shm'), 'Foreign vault files require review')
            s = p.lstat()
            need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_uid == os.geteuid() and not s.st_mode & 0o077,
                 'Vault files must be private owned regular files')
        self.path = self.root/'vault.sqlite3'
        need(self.path.is_file(), 'Vault database unavailable')
        with self.connection() as db:
            if create:
                db.execute('CREATE TABLE revisions (id TEXT PRIMARY KEY, scope TEXT NOT NULL, meta BLOB NOT NULL, archive BLOB NOT NULL)')
                db.execute('PRAGMA user_version=1')
            need(db.execute('PRAGMA user_version').fetchone()[0] == 1, 'Unsupported vault schema')
            tables = set(db.execute("SELECT type,name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"))
            need(tables == {('table', 'revisions')}, 'Unexpected vault schema')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path.as_uri()+'?mode=rw', uri=True, timeout=2)
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA busy_timeout=2000')
        try:
            with db:
                yield db
        finally:
            db.close()

    def put(self, intent):
        try:
            meta = sync.revision(intent['revision'], intent['revision']['identity'])
            archive = intent['archive']
            need(isinstance(archive, bytes) and 0 < len(archive) <= MAX_ARCHIVE, 'Archive exceeds transport limit')
            need(intent['operationId'] == 'put:'+meta['revisionId'], 'Idempotency identity differs')
            need(len(archive) == meta['bytes'] and hashlib.sha256(archive).hexdigest() == meta['passportSha256'], 'Archive transport checksum differs')
            need(sync.inspect_archive(archive, meta['identity']) == meta['saveDataSha256'], 'Archive payload differs')
        except (KeyError, TypeError, ValueError):
            raise VaultError('Save revision or archive verification failed') from None
        scope = sync.digest(meta['identity'])
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT scope,meta,archive FROM revisions WHERE id=?', (meta['revisionId'],)).fetchone()
            if old:
                need(old == (scope, encode(meta), archive), 'Immutable revision differs')
            else:
                for parent in meta['parentIds']:
                    need(db.execute('SELECT 1 FROM revisions WHERE id=? AND scope=?', (parent, scope)).fetchone() is not None,
                         'Publish exact parents before their child')
                count, used = db.execute('SELECT count(*),coalesce(sum(length(archive)),0) FROM revisions').fetchone()
                need(count < MAX_REVISIONS and used + len(archive) <= MAX_TOTAL, 'Vault capacity requires explicit retention review')
                db.execute('INSERT INTO revisions VALUES (?,?,?,?)', (meta['revisionId'], scope, encode(meta), archive))
        return (intent['operationId'], meta['revisionId'], meta['passportSha256'])

    def inventory(self, scope):
        sync.sha(scope)
        with self.connection() as db:
            rows = db.execute('SELECT meta FROM revisions WHERE scope=? ORDER BY id', (scope,)).fetchall()
        revisions = [decode(row[0]) for row in rows]
        parents = {p for r in revisions for p in r['parentIds']}
        heads = sorted(r['revisionId'] for r in revisions if r['revisionId'] not in parents)
        token = sync.digest({'revisionIds': sorted(r['revisionId'] for r in revisions), 'heads': heads})
        return {'revisions': revisions, 'heads': heads, 'inventoryToken': token}

    def archive(self, revision_id, offset=0, count=1024*1024):
        sync.sha(revision_id)
        need(type(offset) is int and offset >= 0 and type(count) is int and 0 < count <= MAX_ARCHIVE, 'Invalid archive range')
        with self.connection() as db:
            row = db.execute('SELECT length(archive),substr(archive,?,?) FROM revisions WHERE id=?', (offset+1,count,revision_id)).fetchone()
        need(row is not None and offset <= row[0], 'Archive or range unavailable')
        return bytes(row[1]), row[0]


def server(root, token, *, port=0):
    """Loopback only. The caller owns shutdown; no scheduler or deployment exists."""
    need(isinstance(token, str) and 32 <= len(token) <= 128 and token.isascii() and token.isalnum(), 'A private transport token is required')
    vault = Vault(root)
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.0'
        def log_message(self, *_):
            pass
        def reply(self, code, data, content='application/json', headers=None):
            self.send_response(code);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            for key,value in (headers or {}).items():self.send_header(key,value)
            self.end_headers();self.wfile.write(data)
        def allowed(self):
            if not hmac.compare_digest(self.headers.get('Authorization','').encode('utf-8'), ('Bearer '+token).encode('utf-8')):
                self.reply(401,b'{"error":"Authentication required"}');return False
            return True
        def do_GET(self):
            if not self.allowed():return
            try:
                if self.path == '/v1/capabilities':
                    self.reply(200,encode({'immutableSaves':True,'rangeDownload':True,'loadGuard':False,'automaticRestore':False,'maxArchiveBytes':MAX_ARCHIVE}));return
                prefix='/v1/inventory/'
                if self.path.startswith(prefix):
                    self.reply(200,encode(vault.inventory(self.path[len(prefix):])));return
                prefix='/v1/revision/'
                need(self.path.startswith(prefix), 'Unknown save route')
                identifier=self.path[len(prefix):];offset=0
                value=self.headers.get('Range')
                if value:
                    import re
                    match=re.fullmatch(r'bytes=(\d+)-(\d*)',value);need(match is not None,'Invalid save range');offset=int(match[1])
                    end=int(match[2]) if match[2] else offset+MAX_ARCHIVE-1
                    need(end>=offset and end-offset<MAX_ARCHIVE,'Invalid save range')
                chunk,total=vault.archive(identifier,offset,end-offset+1 if value else MAX_ARCHIVE)
                headers={'ETag':'"'+identifier+'"','Accept-Ranges':'bytes'}
                if value:headers['Content-Range']=f'bytes {offset}-{offset+len(chunk)-1}/{total}'
                self.reply(206 if value else 200,chunk,'application/octet-stream',headers)
            except (ValueError, TypeError, sqlite3.Error):
                self.reply(409,b'{"error":"Save request refused; retained revisions unchanged"}')
        def do_PUT(self):
            if not self.allowed():return
            try:
                need(self.path.startswith('/v1/revision/'),'Unknown save route')
                identifier=self.path[len('/v1/revision/'):];sync.sha(identifier)
                need(len(self.headers.get_all('Content-Length',[]))==1 and not self.headers.get('Transfer-Encoding'),'Explicit bounded upload length required')
                size=int(self.headers.get('Content-Length','0'));need(0 < size <= MAX_ARCHIVE,'Archive exceeds transport limit')
                header=self.headers.get('X-Save-Revision','');need(len(header)<=16384,'Metadata too large')
                meta=decode(base64.b64decode(header,validate=True));need(meta.get('revisionId')==identifier,'Request identity differs')
                self.connection.settimeout(10);archive=self.rfile.read(size);need(len(archive)==size,'Incomplete save upload')
                receipt=vault.put({'operationId':'put:'+identifier,'revision':meta,'archive':archive})
                self.reply(200,encode({'ack':receipt}))
            except (ValueError,TypeError,sqlite3.Error,OSError):
                self.reply(409,b'{"error":"Save upload refused; retained revisions unchanged"}')
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)


class Client:
    def __init__(self, origin, token):
        url=urlsplit(origin)
        need(url.scheme in ('http','https') and url.hostname and not url.username and not url.password and url.path in ('','/') and not url.query and not url.fragment,
             'An exact save-service origin is required')
        need(url.scheme=='https' or url.hostname=='127.0.0.1','Unencrypted save transport is loopback only')
        need(isinstance(token,str) and token.isascii() and token.isalnum() and 32 <= len(token) <=128,'A private transport token is required')
        self.origin=origin.rstrip('/');self.token=token
    def request(self,path,*,data=None,headers=None):
        request=Request(self.origin+path,data=data,headers={'Authorization':'Bearer '+self.token,**(headers or {})},method='PUT' if data is not None else 'GET')
        # Never forward a save or credential through a redirect.
        from urllib.request import HTTPRedirectHandler, build_opener
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self,*_):return None
        try:
            with build_opener(NoRedirect).open(request,timeout=15) as response:
                limit=MAX_ARCHIVE+1 if path.startswith('/v1/revision/') and data is None else 4*1024*1024
                raw=response.read(limit+1);need(len(raw)<=limit,'Save response exceeds bound');return raw
        except HTTPError as error:
            error.close()
            raise VaultError('Save transport unavailable or request refused') from None
        except (OSError,ValueError):
            raise VaultError('Save transport unavailable or request refused') from None
    def put(self,intent):
        meta=intent['revision'];sync.sha(meta['revisionId'])
        need(intent['operationId']=='put:'+meta['revisionId'],'Idempotency identity differs')
        reply=decode(self.request('/v1/revision/'+meta['revisionId'],data=intent['archive'],headers={'X-Save-Revision':base64.b64encode(encode(meta)).decode()}))
        expected=[intent['operationId'],meta['revisionId'],meta['passportSha256']]
        need(reply=={'ack':expected},'Save acknowledgement differs');return tuple(expected)
    def inventory(self,model,session=None):
        result=decode(self.request('/v1/inventory/'+sync.digest(model.identity)))
        model.observe_inventory(result['revisions'],result['heads'],result['inventoryToken'],session_id=session)
        return result
    def fetch(self,revision_id,offset=0,count=1024*1024):
        sync.sha(revision_id);need(type(offset) is int and offset>=0 and type(count) is int and 0<count<=1024*1024,'Invalid save range')
        return self.request('/v1/revision/'+revision_id,headers={'Range':f'bytes={offset}-{offset+count-1}'})


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['init','serve']);parser.add_argument('root',type=Path)
    parser.add_argument('--port',type=int,default=8768)
    args=parser.parse_args()
    try:
        if args.command=='init':
            Vault(args.root,create=True);print('Private save vault created; no service started.');return
        token_path=Path(os.environ.get('NOVA_SAVE_TOKEN_FILE',''))
        need(token_path.is_file() and not token_path.is_symlink(),'Private token file required')
        s=token_path.stat();need(s.st_uid==os.geteuid() and s.st_nlink==1 and not s.st_mode&0o077 and s.st_size<=256,'Private token file required')
        token=token_path.read_text().strip();need(1024<=args.port<=65535,'Explicit unprivileged port required')
        host=server(args.root,token,port=args.port)
        try:host.serve_forever()
        finally:host.server_close()
    except (ValueError,OSError,sqlite3.Error):
        parser.exit(1,'Save vault refused configuration; existing revisions retained.\n')


if __name__=='__main__':main()
