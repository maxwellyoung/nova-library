import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from tools import apply_pc_runtime as pc
from tools import prepare_native

CPP='''#include "library/DeviceLibrary.h"
void FrontendLayer::rebuild() {
    m_engine = new QQmlApplicationEngine(this);
    m_engine->rootContext()->setContextProperty(QStringLiteral("deviceLibrary"), m_device_library);
    m_engine->load(QUrl(QStringLiteral("qrc:/frontend/main.qml")));
}
'''
PRO='SOURCES += library/DeviceLibrary.cpp\n'
CMAKE='add_library(pegasus-backend library/DeviceLibrary.cpp)\n'
MANIFEST='<manifest xmlns:android="http://schemas.android.com/apk/res/android"><application android:label="Existing" /></manifest>'

def snapshot(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}

class PcApplyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name).resolve();self.source=self.root/'source';self.backup=self.root/'before'
        (self.source/pc.TARGET.parent).mkdir(parents=True);(self.source/pc.JAVA).mkdir(parents=True)
        for p,text in [(pc.CPP,CPP),(pc.PRO,PRO),(pc.CMAKE,CMAKE),(pc.MANIFEST,MANIFEST)]:
            (self.source/p).parent.mkdir(parents=True,exist_ok=True);(self.source/p).write_text(text)
    def tearDown(self):self.temp.cleanup()
    def test_fresh_pair_contains_exact_source_and_two_package_queries(self):
        before=snapshot(self.source);r=pc.apply(self.source,self.backup);self.assertEqual(r['state'],'applied')
        for p,b in before.items():self.assertEqual((self.backup/p).read_bytes(),b)
        for name in pc.MODULE_FILES:self.assertEqual((self.source/pc.TARGET/name).read_bytes(),(pc.ROOT/'native/pcgames'/name).read_bytes())
        for name in pc.JAVA_FILES:self.assertEqual((self.source/pc.JAVA/name).read_bytes(),(pc.ROOT/'native/pcgames'/name).read_bytes())
        text=(self.source/pc.MANIFEST).read_text();self.assertEqual(text.count('<package '),2);self.assertNotIn('uses-permission',text)
        self.assertIn('new library::PcRuntime(m_engine)',(self.source/pc.CPP).read_text())
        self.assertIn('Existing',text)
    def test_reapply_and_partial_module_refuse_without_replacing_anything(self):
        pc.apply(self.source,self.backup);before=snapshot(self.source)
        with self.assertRaises(ValueError):pc.apply(self.source,self.root/'unused')
        self.assertEqual(snapshot(self.source),before);self.assertFalse((self.root/'unused').exists())
    def test_existing_queries_are_retained_and_conflicting_entries_require_review(self):
        (self.source/pc.MANIFEST).write_text(MANIFEST.replace('<application','<queries><package android:name="example.other" /></queries><application'))
        pc.apply(self.source,self.backup);text=(self.source/pc.MANIFEST).read_text();self.assertEqual(text.count('<queries>'),1);self.assertIn('example.other',text)
    def test_anchor_and_backup_refusals_have_no_mutation(self):
        for text in [CPP+CPP,CPP.replace('DeviceLibrary.h','Other.h'),CPP+'\n// NOVA_PC_RUNTIME_V1\n']:
            (self.source/pc.CPP).write_text(text);before=snapshot(self.source)
            with self.assertRaises(ValueError):pc.apply(self.source,self.backup)
            self.assertEqual(snapshot(self.source),before);self.assertFalse(self.backup.exists())
        (self.source/pc.CPP).write_text(CPP)
        with self.assertRaises(ValueError):pc.apply(self.source,self.source/'backup')
    def test_owned_shared_writes_roll_back_after_write_failure(self):
        before=snapshot(self.source);replace=pc.os.replace;calls=0
        def fail_once(a,b):
            nonlocal calls
            calls+=1
            if calls==2:raise OSError('injected publication failure')
            return replace(a,b)
        with mock.patch.object(pc.os,'replace',side_effect=fail_once):
            with self.assertRaises(OSError):pc.apply(self.source,self.backup)
        self.assertEqual(snapshot(self.source),before)
        self.assertEqual(json.loads((self.backup/'receipt.json').read_text())['state'],'failed')
    def test_java_contract_has_only_the_two_reviewed_dispatch_targets(self):
        if not shutil.which('javac') or not shutil.which('java'):self.skipTest('Installed JDK required')
        module=pc.ROOT/'native/pcgames';classes=self.root/'classes';classes.mkdir()
        harness=self.root/'PcContractTest.java'
        harness.write_text('''import org.pegasus_frontend.android.PcLaunchContract;
public class PcContractTest {
 public static void main(String[] a) {
  if (!PcLaunchContract.supported("droiddeck","0.7.0") || !PcLaunchContract.supported("gamenative","1.4.0"))throw new AssertionError();
  for(String bad:new String[]{"","0.7.1","0.7.0-beta","0.7.0\\n","1.4.0"})if(PcLaunchContract.supported("droiddeck",bad))throw new AssertionError();
  for(String bad:new String[]{"other","../game","DROIDDECK","droiddeck;sh",null})if(PcLaunchContract.action(bad)!=null || PcLaunchContract.activity(bad)!=null || PcLaunchContract.packageName(bad)!=null)throw new AssertionError();
  if (!"com.droiddeck.launcher.FrontEndActivity".equals(PcLaunchContract.activity("droiddeck")))throw new AssertionError();
  if (!"app.gamenative.MainActivity".equals(PcLaunchContract.activity("gamenative")))throw new AssertionError();
  if (!"app.gamenative.LAUNCH_GAME".equals(PcLaunchContract.action("gamenative")))throw new AssertionError();
  System.out.println("PC_CONTRACT_PASS");
 }
}''')
        subprocess.run(['javac','-d',str(classes),str(module/'PcLaunchContract.java'),str(harness)],check=True,capture_output=True)
        r=subprocess.run(['java','-cp',str(classes),'PcContractTest'],check=True,capture_output=True,text=True);self.assertIn('PC_CONTRACT_PASS',r.stdout)
