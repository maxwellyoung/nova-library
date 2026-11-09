import copy
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from tools import save_vault as v
from tools.save_catalogue import Catalogue
from tools.save_sync_model import SyncModel,digest,SyncError
from test_save_sync_model import IDENTITY,archive,local


class SaveVaultTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()/'vault';self.vault=v.Vault(self.root,create=True)
        self.model=SyncModel(IDENTITY);self.rev=local(self.model,archive());self.op=self.model.queue_upload(self.rev);self.intent=self.model.upload_intent(self.op)
    def tearDown(self):self.tmp.cleanup()
    def test_durable_idempotent_upload_and_range_after_restart(self):
        ack=self.vault.put(self.intent);self.assertEqual(ack[1],self.rev)
        again=v.Vault(self.root);self.assertEqual(again.put(self.intent),ack)
        inv=again.inventory(digest(IDENTITY));self.assertEqual(inv['heads'],[self.rev]);self.assertEqual(len(inv['revisions']),1)
        data,size=again.archive(self.rev,100,500);self.assertEqual(data,self.intent['archive'][100:600]);self.assertEqual(size,len(self.intent['archive']))
    def test_corruption_and_wrong_operation_do_not_modify_history(self):
        self.vault.put(self.intent)
        for field,value in [('archive',b'wrong'),('operationId','put:'+'0'*64)]:
            broken=copy.deepcopy(self.intent);broken[field]=value
            with self.assertRaises(v.VaultError):self.vault.put(broken)
        self.assertEqual(self.vault.inventory(digest(IDENTITY))['heads'],[self.rev])
    def test_two_offline_children_remain_two_branches_and_scopes_do_not_mix(self):
        self.model.acknowledge_upload(*self.vault.put(self.intent))
        for payload,number in [(b'left',2),(b'right',3)]:
            child=local(self.model,archive(payload),number,[self.rev]);op=self.model.queue_upload(child)
            self.vault.put(self.model.upload_intent(op))
        inv=self.vault.inventory(digest(IDENTITY));self.assertEqual(len(inv['revisions']),3);self.assertEqual(len(inv['heads']),2)
        other=copy.deepcopy(IDENTITY);other['editionId']='fixture:other';self.assertEqual(self.vault.inventory(digest(other))['heads'],[])
    def test_missing_parents_and_linked_or_public_roots_refuse(self):
        self.model.acknowledge_upload(self.op,self.rev,self.intent['revision']['passportSha256'])
        child=local(self.model,archive(b'child'),2,[self.rev]);op=self.model.queue_upload(child)
        with self.assertRaises(v.VaultError):self.vault.put(self.model.upload_intent(op))
        link=Path(self.tmp.name)/'linked';link.symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(v.VaultError):v.Vault(link)
        self.root.chmod(0o755)
        with self.assertRaises(v.VaultError):v.Vault(self.root)
        self.root.chmod(0o700)
    def test_real_http_upload_inventory_resumed_download_and_verification(self):
        token='A'*40;server=v.server(self.root,token);thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            origin='http://127.0.0.1:'+str(server.server_port);client=v.Client(origin,token)
            original_request=client.request
            def lose_reply(*args,**kwargs):
                original_request(*args,**kwargs)
                raise v.VaultError('Synthetic lost reply after real durable commit')
            with patch.object(client,'request',side_effect=lose_reply):
                with self.assertRaises(v.VaultError):client.put(self.intent)
            self.assertIn('queued',self.model.statuses(self.rev))
            ack=client.put(self.intent);self.model.acknowledge_upload(*ack)
            self.assertEqual(client.put(self.intent),ack)
            reader=SyncModel(IDENTITY);client.inventory(reader)
            data=client.fetch(self.rev);self.assertEqual(data,self.intent['archive'])
            self.assertEqual(client.fetch(self.rev,123),data[123:])
            self.assertEqual(v.sync.inspect_archive(data,IDENTITY),self.intent['revision']['saveDataSha256'])
            offset=reader.begin_download(self.rev,'download:one')
            reader.append_download(self.rev,'download:one',offset,data[:123])
            reader=SyncModel.restart(reader.snapshot());offset=reader.begin_download(self.rev,'download:two')
            reader.append_download(self.rev,'download:two',offset,client.fetch(self.rev,offset));reader.verify_download(self.rev)
            path=self.root.parent/'download.tar';path.write_bytes(reader.records[self.rev]['buffer'])
            catalogue=Catalogue(self.root.parent/'catalogue',create=True)
            try:
                checkpoint=catalogue.import_passport(path);reader.attach_checkpoint(self.rev,checkpoint)
                staged=self.root.parent/'staged';catalogue.stage(checkpoint['checkpointId'],IDENTITY,staged)
                self.assertEqual((staged/'memory.srm').read_bytes(),b'initial')
                self.assertIn('verified',reader.statuses(self.rev));self.assertIn('local',reader.statuses(self.rev))
            finally:catalogue.close()
            caps=v.decode(client.request('/v1/capabilities'));self.assertFalse(caps['loadGuard']);self.assertFalse(caps['automaticRestore'])
            with self.assertRaises(v.VaultError):v.Client(origin,'B'*40).put(self.intent)
        finally:server.shutdown();server.server_close();thread.join()
    def test_private_database_and_no_deletion_or_latest_timestamp_operation(self):
        self.vault.put(self.intent);self.assertEqual(self.vault.path.stat().st_mode&0o777,0o600)
        self.assertFalse(hasattr(self.vault,'delete'));self.assertFalse(hasattr(self.vault,'restore'))
