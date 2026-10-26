import importlib.util
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
import json
import shutil
ROOT=Path(__file__).resolve().parents[1]
class DeliveryTests(unittest.TestCase):
    def builder(self):
        p=ROOT/'tools/build_release.py';self.assertTrue(p.exists(),'Missing release builder')
        spec=importlib.util.spec_from_file_location('build_release',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
    def copy_public_fixture(self,m,path):
        path.mkdir()
        for rel,source in m.collect().items():
            dest=path/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
        return path
    def test_release_rejects_symlinked_allowlist_ancestor(self):
        m=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);root=self.copy_public_fixture(m,temp/'root')
            shutil.move(root/'tests',temp/'external');(root/'tests').symlink_to(temp/'external',target_is_directory=True)
            m.ROOT=root
            with self.assertRaises(ValueError):m.collect()
    def test_unlisted_hidden_file_never_enters_source_bundle(self):
        m=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);root=self.copy_public_fixture(m,temp/'root')
            (root/'tests/.env').write_text('SYNTHETIC_PRIVATE_VALUE=demo')
            m.ROOT=root;out=m.build(temp/'out')
            with zipfile.ZipFile(out['source']) as z:
                self.assertFalse(any(n.endswith('/.env') for n in z.namelist()))
    def test_changed_public_document_needs_fresh_content_review(self):
        m=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            root=self.copy_public_fixture(m,Path(temp)/'root')
            report=root/'docs/release/acceptance-report.md'
            report.write_text(report.read_text()+'\nSYNTHETIC_NONPUBLIC_VENDOR_MEMO: derived business observation.\n')
            m.ROOT=root
            with self.assertRaisesRegex(ValueError,'content review'):
                m.collect()
    def test_changed_attachment_metadata_needs_fresh_content_review(self):
        m=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            root=self.copy_public_fixture(m,Path(temp)/'root')
            metadata=root/'examples/synthetic/media/metadata.json'
            data=json.loads(metadata.read_text())
            data['internal_notes']='SYNTHETIC_NONPUBLIC_INTERVIEW_NOTE'
            metadata.write_text(json.dumps(data))
            m.ROOT=root
            with self.assertRaisesRegex(ValueError,'content review'):
                m.collect()
    def test_review_metadata_is_not_an_unchecked_text_channel(self):
        m=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            root=self.copy_public_fixture(m,Path(temp)/'root')
            path=root/'tools/public-content-approvals.json'
            data=json.loads(path.read_text()) if path.exists() else {}
            data['unreviewed_note']='SYNTHETIC_NONPUBLIC_REVIEW_NOTE'
            path.write_text(json.dumps(data))
            m.ROOT=root
            with self.assertRaisesRegex(ValueError,'content review'):
                m.collect()
    def test_publish_bundle_excludes_private_sources_and_evals(self):
        m=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            out=m.build(Path(temp))
            with zipfile.ZipFile(out['skill']) as skill:
                self.assertIn('build-role-workspace/LICENSE',skill.namelist())
                for name in ['START_HERE.md','USER_GUIDE.md','COMPATIBILITY.md']:
                    self.assertIn('build-role-workspace/'+name,skill.namelist())
                self.assertEqual(skill.read('build-role-workspace/USER_GUIDE.md'),(ROOT/'docs/user-guide.md').read_bytes())
                self.assertEqual(skill.read('build-role-workspace/COMPATIBILITY.md'),(ROOT/'docs/compatibility.md').read_bytes())
                self.assertIn(b'MIT License',skill.read('build-role-workspace/LICENSE'))
            with zipfile.ZipFile(out['source']) as z:
                names=z.namelist()
                self.assertTrue(any(n.endswith('/LICENSE') for n in names))
                self.assertTrue(any(n.endswith('/SKILL.md') for n in names))
                self.assertFalse(any('/business/' in n or '/evals/' in n or 'v3-original' in n for n in names))
                for n in names:
                    if n.endswith(('.md','.json','.py','.yaml')):
                        self.assertNotIn(b'/' + b'Users/',z.read(n))
    def test_skill_can_run_after_clean_unpack_and_preserve_private_workspace(self):
        m=self.builder()
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);out=m.build(temp/'packages')
            with zipfile.ZipFile(out['skill']) as z:z.extractall(temp/'clean')
            skill=temp/'clean/build-role-workspace';sys.path.insert(0,str(skill/'scripts'))
            try:
                spec=importlib.util.spec_from_file_location('installed_workspace',skill/'scripts/workspace.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                w=module.Workspace(temp/'user-work');w.initialize('administration','资料登记');w.save_artifact('work.md','用户工作')
                with zipfile.ZipFile(out['skill']) as z:z.extractall(temp/'clean-upgrade')
                fresh=module.Workspace(temp/'user-work')
                self.assertEqual(fresh.read()['goal'],'资料登记')
                self.assertEqual((temp/'user-work/results/work.md').read_text(),'用户工作')
            finally:sys.path.remove(str(skill/'scripts'))
    def test_thousand_item_ledger_has_individual_dispositions(self):
        p=ROOT/'tools/run_scale_check.py';self.assertTrue(p.exists(),'Missing scale runner')
        spec=importlib.util.spec_from_file_location('scale',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as temp:
            result=m.run(Path(temp))
            self.assertEqual(result['counts'],{'duplicate':80,'rights_blocked':30,'unreadable':20,'unsupported':10,'processable':860})
            self.assertEqual(len(result['items']),1000)
            self.assertEqual(len({x['manifest_item_id'] for x in result['items']}),1000)
            self.assertFalse(result['real_media_test'])
if __name__=='__main__':unittest.main()
