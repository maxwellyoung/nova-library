import importlib.util
from pathlib import Path
import tempfile
import unittest
import shutil

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('checked_memory',ROOT/'tools/apply_theme_memory.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class CheckedMemoryPreparation(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
        self.source=self.root/'source';self.target=self.source/module.TARGET;self.target.mkdir(parents=True)
        for n in module.FILES:shutil.copyfile(ROOT/'native/theme-memory/upstream'/n,self.target/n)
        self.backup=self.root/'backup'
    def snapshot(self):return {n:(self.target/n).read_bytes() for n in module.FILES}
    def test_exact_apply_keeps_rollback_and_other_files(self):
        before=self.snapshot();(self.target/'other').write_text('preserve')
        receipt=module.apply(self.source,self.backup)
        for n in module.FILES:
            self.assertEqual((self.backup/n).read_bytes(),before[n])
            self.assertEqual((self.target/n).read_bytes(),(ROOT/'native/theme-memory'/n).read_bytes())
        self.assertFalse(receipt['installed']);self.assertFalse(receipt['built']);self.assertEqual((self.target/'other').read_text(),'preserve')
    def test_changed_input_refuses_before_backup_or_mutation(self):
        (self.target/'Memory.cpp').write_text('changed');before=self.snapshot()
        with self.assertRaises(ValueError):module.apply(self.source,self.backup)
        self.assertFalse(self.backup.exists());self.assertEqual(self.snapshot(),before)
    def test_reapply_refuses_and_keeps_both_generations(self):
        module.apply(self.source,self.backup);before=self.snapshot()
        with self.assertRaises(ValueError):module.apply(self.source,self.root/'again')
        self.assertFalse((self.root/'again').exists());self.assertEqual(self.snapshot(),before)
    def test_existing_backup_refuses(self):
        self.backup.mkdir();(self.backup/'owner').write_text('preserve');before=self.snapshot()
        with self.assertRaises(ValueError):module.apply(self.source,self.backup)
        self.assertEqual(self.snapshot(),before);self.assertEqual((self.backup/'owner').read_text(),'preserve')
    def test_linked_input_refuses(self):
        name=self.target/'Memory.cpp';name.rename(self.root/'saved');name.symlink_to(self.root/'saved')
        with self.assertRaises(ValueError):module.apply(self.source,self.backup)
        self.assertFalse(self.backup.exists())
