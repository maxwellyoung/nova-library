import copy
import ctypes
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import retroarch_input as m

ROOT=Path(__file__).resolve().parents[1]
BASE=(b'# private disposable baseline\r\nauto_overrides_enable = "false"\r\n'
      b'config_save_on_exit = "false"\r\ninput_menu_toggle_btn = "3"\r\n'
      b'savefile_directory = "/synthetic/saves"\r\nsavestate_auto_load = "false"\r\n'
      b'input_analog_sensitivity = "1"\r\ninput_analog_deadzone = "0"\r\n')

def value(edition='demo:orbit',sensitivity=1.5,deadzone=0.2):
    return {'version':1,'profile':{'binding':{'editionId':edition,'runtimeId':m.RUNTIME['id'],'runtimeVersion':m.RUNTIME['version']},
        'preferences':{'sensitivity':{'x':sensitivity,'y':sensitivity},'deadzone':{'left':deadzone,'right':deadzone},
          'inversion':{'x':False,'y':True},'triggers':{'left':0.25,'right':0.75},'holdToggle':{'aim':'toggle','sprint':'hold','crouch':'toggle'}}}}

class InputTransactions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.store=m.Store.create(self.root/'input');self.owner=self.root/'owner.cfg';self.owner.write_bytes(BASE)
    def tree(self):return {str(p.relative_to(self.store.root)):p.read_bytes() for p in self.store.root.rglob('*') if p.is_file()}
    def preview(self,v=None,fields=None,baseline=BASE):
        return self.store.preview_profile(v or value(),fields or ['sensitivity','deadzone'],baseline=baseline,allow_shared_analog=True)
    def choose(self,v=None,fields=None,baseline=BASE):
        plan=self.preview(v,fields,baseline);return self.store.confirm(plan,plan['token'],baseline)
    def test_mapping_discloses_shared_scope_and_unmapped_preferences(self):
        mapped=m.mapping(value());self.assertEqual(set(mapped['supported']),{'sensitivity','deadzone'})
        self.assertEqual({x['field'] for x in mapped['unsupported']},{'inversion','triggers','holdToggle'})
        self.assertIn('analog buttons',mapped['effectScope']);self.assertFalse(mapped['deviceApplied']);self.assertFalse(mapped['gameplayVerified'])
        v=value();v['profile']['preferences']['sensitivity']['y']=2
        self.assertNotIn('sensitivity',m.mapping(v)['supported'])
        before=self.tree()
        with self.assertRaises(m.InputError):self.preview(v)
        self.assertEqual(self.tree(),before)
        self.assertEqual(set(self.preview(v,['deadzone'])['changes']),{'input_analog_deadzone'})
    def test_explicit_fields_and_shared_effect_consent_are_required(self):
        before=self.tree()
        for fields,consent in [([],True),(['sensitivity']*2,True),(['inversion'],True),([{}],True),(['sensitivity'],False),(['deadzone'],'true')]:
            with self.subTest(fields=fields,consent=consent),self.assertRaises(m.InputError):
                self.store.preview_profile(value(),fields,baseline=BASE,allow_shared_analog=consent)
        self.assertEqual(self.tree(),before)
    def test_strict_envelope_runtime_and_nonfinite_preferences_refuse(self):
        invalid=[]
        for mutation in [lambda v:v.update(version=True),lambda v:v.update(extra=1),lambda v:v['profile']['binding'].update(runtimeVersion='1.22.3'),
                         lambda v:v['profile']['binding'].update(runtimeId='RetroArch'),lambda v:v['profile']['preferences']['deadzone'].update(left=True),
                         lambda v:v['profile']['preferences']['sensitivity'].update(x=float('nan')),lambda v:v['profile']['preferences']['inversion'].update(y=1),
                         lambda v:v['profile']['preferences']['holdToggle'].update(aim='macro')]:
            v=value();mutation(v);invalid.append(v)
        for v in invalid:
            with self.assertRaises(m.InputError):m.profile(v)
        raw=json.dumps(value()).encode()
        for data in [b'{"version":1,"version":1,"profile":{}}',raw+b'x',b'x'*16385]:
            with self.assertRaises(m.tx.DisplayError):m.decode_profile(data)
        self.assertEqual(m.decode_profile(raw),value())
    def test_oversized_numbers_and_deep_json_refuse_without_parser_tracebacks(self):
        for data in [b'{"version":'+b'9'*5000+b'}',b'['*2000+b']'*2000]:
            with self.assertRaises(m.tx.DisplayError):m.decode_profile(data)
        v=value();v['profile']['preferences']['sensitivity']['x']=10**2000
        with self.assertRaises(m.InputError):m.profile(v)
    def test_non_ascii_line_or_assignment_whitespace_requires_review(self):
        for text in [BASE.decode().replace('input_analog_sensitivity','\u00a0input_analog_sensitivity'),BASE.decode()+'\u2028input_axis_threshold = "0.2"',BASE.decode()+'\u0085']:
            with self.assertRaises(m.tx.DisplayError):self.preview(baseline=text.encode())
        permitted=BASE+b'system_directory = "/synthetic/'+"雪".encode()+b'"\r\n'
        candidate=m.render_config(permitted,m.selected(value(),['sensitivity'],True))
        self.assertIn('雪'.encode(),candidate)
    def test_preview_is_read_only_and_has_no_baseline_paths(self):
        before=self.tree();plan=self.preview();self.assertEqual(self.tree(),before)
        self.assertNotIn('/synthetic',json.dumps(plan));self.assertEqual(plan['binding'],value()['profile']['binding'])
        self.assertEqual(plan['notApplied'],['inversion','triggers','holdToggle'])
        with self.assertRaises(m.tx.DisplayError):self.store.confirm(plan,'0'*64,BASE)
        self.assertEqual(self.tree(),before);self.assertEqual(self.owner.read_bytes(),BASE)
    def test_render_changes_only_explicit_selected_settings(self):
        choice=m.selected(value(),['sensitivity'],True);candidate=m.render_config(BASE,choice)
        for line in BASE.splitlines(keepends=True):
            if not line.startswith(b'input_analog_sensitivity'):self.assertIn(line,candidate)
        self.assertIn(b'input_analog_sensitivity = "1.5"',candidate)
        self.assertNotIn(b'input_analog_deadzone = "0.2"',candidate)
        self.assertEqual(self.owner.read_bytes(),BASE)
    def test_precedence_unknown_existing_values_and_duplicate_keys_refuse(self):
        for data in [BASE+b'#include "other.cfg"\n',BASE+b'input_analog_deadzone = "0.2"\n',
                     BASE.replace(b'input_analog_deadzone = "0"',b'input_analog_deadzone = "nan"'),
                     BASE.replace(b'auto_overrides_enable = "false"',b'auto_overrides_enable = "true"'),
                     BASE.replace(b'input_analog_sensitivity = "1"',b'input_analog_sensitivity = "-1"')]:
            with self.assertRaises(m.tx.DisplayError):self.preview(baseline=data)
    def test_restart_exact_revert_and_edition_isolation(self):
        first=self.choose();first_bytes=Path(first['configPath']).read_bytes()
        other=value('demo:orbit-eu',0.5,0.1);other_current=self.choose(other)
        next_value=value(sensitivity=2,deadzone=0.3);second=self.choose(next_value,baseline=None)
        self.assertNotEqual(first['generation'],second['generation'])
        reopened=m.Store(self.store.root);key=value()['profile']['binding'];self.assertEqual(reopened.current_profile(key)['generation'],second['generation'])
        plan=reopened.preview_revert_profile(key);reverted=reopened.confirm(plan,plan['token'])
        self.assertEqual(Path(reverted['configPath']).read_bytes(),first_bytes)
        plan=reopened.preview_revert_profile(key);original=reopened.confirm(plan,plan['token'])
        self.assertEqual(Path(original['configPath']).read_bytes(),BASE)
        self.assertEqual(reopened.current_profile(other['profile']['binding'])['generation'],other_current['generation'])
        with self.assertRaises(m.tx.DisplayError):reopened.preview_revert_profile(key)
        self.assertEqual(self.owner.read_bytes(),BASE)
    def test_long_cloud_ids_are_bound_without_prefix_aliasing(self):
        a=value('nova:cloud_'+'a'*64+':41_'+'b'*64);b=value(a['profile']['binding']['editionId']+'-other')
        first=self.choose(a);second=self.choose(b)
        self.assertNotEqual(first['configPath'],second['configPath'])
        self.assertEqual(self.store.current_profile(a['profile']['binding'])['binding'],a['profile']['binding'])
    def test_stale_expired_or_modified_preview_cannot_apply(self):
        plan=self.preview();changed=copy.deepcopy(plan);changed['mode']['profile']['profile']['preferences']['sensitivity']['x']=9
        with self.assertRaises(m.tx.DisplayError):self.store.confirm(changed,plan['token'],BASE)
        with patch.object(m.tx.time,'time',return_value=plan['expiresAt']+1):
            with self.assertRaises(m.tx.DisplayError):self.store.confirm(plan,plan['token'],BASE)
        self.choose()
        with self.assertRaises(m.tx.DisplayError):self.store.confirm(plan,plan['token'],BASE)
    def test_nonregular_profile_and_workspace_marker_refuse_without_blocking(self):
        fifo=self.root/'named-input';os.mkfifo(fifo)
        done=subprocess.run([sys.executable,str(ROOT/'tools/retroarch_input.py'),'mapping','--profile',str(fifo)],capture_output=True,text=True,timeout=3)
        self.assertEqual(done.returncode,1);self.assertNotIn('Traceback',done.stderr)
        marker=self.store.root/'workspace.json';marker.unlink();os.mkfifo(marker)
        script='from tools import retroarch_input as m;import sys;m.Store(sys.argv[1])'
        done=subprocess.run([sys.executable,'-c',script,str(self.store.root)],cwd=ROOT,capture_output=True,text=True,timeout=3)
        self.assertNotEqual(done.returncode,0)
    def test_display_and_input_workspaces_cannot_be_adopted_by_each_other(self):
        with self.assertRaises(m.tx.DisplayError):m.tx.Store(self.store.root)
        d=m.tx.Store.create(self.root/'display')
        with self.assertRaises(m.tx.DisplayError):m.Store(d.root)
        with self.assertRaises(m.InputError):self.store.preview_recipe(json.dumps(value()).encode())
    def test_corrupted_config_and_binding_receipts_remain_protected(self):
        chosen=self.choose();p=Path(chosen['configPath']);original=p.read_bytes();p.write_bytes(original+b'# change\n')
        with self.assertRaises(m.tx.DisplayError):self.store.current_profile(value()['profile']['binding'])
        p.write_bytes(original);receipt=p.parent/'receipt.json';r=json.loads(receipt.read_text());r['mode']['profile']['profile']['binding']['editionId']='other';receipt.write_text(json.dumps(r))
        with self.assertRaises(m.tx.DisplayError):self.store.current_profile(value()['profile']['binding'])
    def test_busy_lock_and_failed_write_do_not_report_success(self):
        with (self.store.root/'lock').open('rb+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(m.tx.DisplayError):self.preview()
        plan=self.preview();before=self.tree()
        with patch.object(m.tx,'_atomic',side_effect=OSError('synthetic failure')):
            with self.assertRaises(OSError):self.store.confirm(plan,plan['token'],BASE)
        self.assertEqual(self.store.current_profile(value()['profile']['binding'])['mode'],None)
        self.assertEqual(self.owner.read_bytes(),BASE)
    def test_real_process_interruptions_require_recovery_and_restore_prior_selection(self):
        script='''from tools import retroarch_input as m
import json,os,sys
s=m.Store(sys.argv[1]);v=json.loads(sys.argv[2]);baseline=bytes.fromhex(sys.argv[3]);p=s.preview_profile(v,['sensitivity','deadzone'],baseline=baseline,allow_shared_analog=True)
def crash(stage):
 if stage==sys.argv[4]:os._exit(77)
m.tx._checkpoint=crash
s.confirm(p,p['token'],baseline)
'''
        for stage in ['journal_durable','selection_durable']:
            with self.subTest(stage=stage):
                path=self.root/stage;s=m.Store.create(path)
                done=subprocess.run([sys.executable,'-c',script,str(path),json.dumps(value()),BASE.hex(),stage],cwd=ROOT,capture_output=True,text=True)
                self.assertEqual(done.returncode,77,done.stderr);s=m.Store(path)
                with self.assertRaises(m.tx.DisplayError):s.current_profile(value()['profile']['binding'])
                self.assertTrue(s.recover()['recovered']);self.assertEqual(s.current_profile(value()['profile']['binding'])['mode'],None)
        self.assertEqual(self.owner.read_bytes(),BASE)
    def test_javascript_export_interoperates_without_retargeting(self):
        node=shutil.which('node');self.assertIsNotNone(node)
        script="const fs=require('fs'),vm=require('vm');const c=vm.createContext({});vm.runInContext(fs.readFileSync('theme/InputProfiles.js','utf8').replace(/^\\.pragma library\\s*/,''),c);const v=JSON.parse(process.argv[1]);const s=c.edit(c.store(undefined),v.profile.binding,v.profile.preferences);process.stdout.write(c.exportProfile(s,v.profile.binding));"
        done=subprocess.run([node,'-e',script,json.dumps(value())],cwd=ROOT,capture_output=True,check=True)
        self.assertEqual(m.decode_profile(done.stdout),value())

class PinnedAnalogConsumer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name).resolve()
        module=ROOT/'native/retroarch-input';cls.spec=json.loads((module/'source.json').read_text())
        fragment=(module/'input_joypad_axis.inc').read_bytes()
        if hashlib.sha256(fragment).hexdigest()!=cls.spec['functionSha256']:raise AssertionError('Pinned analog function changed')
        cls.source=cls.root/'probe.c';cls.source.write_text('''#include <stdint.h>
#define MAX(a,b) ((a)>(b)?(a):(b))
#define MIN(a,b) ((a)<(b)?(a):(b))
#define AXIS_NONE UINT32_MAX
typedef struct {int16_t (*axis)(unsigned,uint32_t);} input_device_driver_t;
static int16_t raw;
static int16_t axis(unsigned port,uint32_t joyaxis){return raw;}
'''+fragment.decode()+'''
int nova_axis(float deadzone,float sensitivity,int v,float magnitude){raw=v;const input_device_driver_t d={axis};return input_joypad_axis(deadzone,sensitivity,&d,0,0,magnitude);}
''')
        compiler=shutil.which('cc')
        if not compiler:raise RuntimeError('A C compiler is required for pinned input-consumption verification')
        lib=cls.root/('probe.dylib' if sys.platform=='darwin' else 'probe.so')
        subprocess.run([compiler,'-dynamiclib' if sys.platform=='darwin' else '-shared','-fPIC','-O0',str(cls.source),'-o',str(lib)],capture_output=True,check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.nova_axis.argtypes=[ctypes.c_float,ctypes.c_float,ctypes.c_int,ctypes.c_float];cls.lib.nova_axis.restype=ctypes.c_int
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_translated_config_reaches_the_pinned_axis_function(self):
        cfg=m.render_config(BASE,m.selected(value(sensitivity=2,deadzone=0.2),['sensitivity','deadzone'],True));_,settings=m.parse_config(cfg)
        d=float(settings['input_analog_deadzone']);s=float(settings['input_analog_sensitivity'])
        self.assertEqual(self.lib.nova_axis(d,s,3000,0.1),0)
        self.assertAlmostEqual(self.lib.nova_axis(d,s,16384,0.5),24576,delta=3)
        self.assertEqual(self.lib.nova_axis(d,s,30000,0.95),32767)
        self.assertEqual(self.lib.nova_axis(d,s,-30000,0.95),-32767)
    def test_sensitivity_and_zero_deadzone_preserve_sign_and_bound_output(self):
        for raw in [-32767,-20000,0,20000,32767]:
            self.assertEqual(self.lib.nova_axis(0,1,raw,abs(raw)/32767),raw)
            self.assertAlmostEqual(self.lib.nova_axis(0,0.5,raw,abs(raw)/32767),raw*0.5,delta=1)
    def test_source_contract_is_exact_and_not_an_installed_runtime_claim(self):
        self.assertEqual(self.spec['version'],m.RUNTIME['version']);self.assertEqual(self.spec['commit'],m.RUNTIME['sourceCommit'])
        self.assertFalse(m.mapping(value())['installedRuntimeVerified'])
