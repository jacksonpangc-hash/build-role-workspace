"""Behavioral tests: source integrity, persistent recovery, exact math and action boundaries."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from decimal import Decimal

SCRIPTS = Path(__file__).resolve().parents[1] / 'skills/build-role-workspace/scripts'
sys.path.insert(0, str(SCRIPTS))

def implementation(name):
    path = SCRIPTS / (name + '.py')
    if not path.exists():
        raise AssertionError('Missing implementation: ' + name)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / 'inputs'; self.inputs.mkdir()

    def workspace(self):
        m = implementation('workspace')
        w = m.Workspace(self.root / 'work')
        w.initialize('ecommerce_operations', '复盘')
        return w

    def test_manifest_keeps_duplicate_references_but_blocks_symlinks(self):
        m = implementation('manifest')
        (self.inputs/'a.txt').write_text('事实')
        (self.inputs/'b.txt').write_text('事实')
        (self.inputs/'secret.txt').symlink_to(self.root/'outside.txt')
        rows = m.scan(self.inputs)
        self.assertEqual(len(rows), 3)
        self.assertEqual(sorted(x['status'] for x in rows), ['blocked_symlink','duplicate','ready'])
        self.assertEqual(len({x['manifest_item_id'] for x in rows}), 3)

    def test_restart_search_has_original_line_and_version(self):
        w = self.workspace();(self.inputs/'policy.md').write_text('现行规则\n退款窗口为7天\n')
        w.ingest(self.inputs)
        fresh = implementation('workspace').Workspace(self.root/'work')
        hit = fresh.search('退款')[0]
        self.assertEqual(hit['line'], 2)
        self.assertEqual(hit['quote'], '退款窗口为7天')
        self.assertEqual(len(hit['sha256']), 64)

    def test_changed_same_name_is_not_silently_used(self):
        w = self.workspace();f=self.inputs/'policy.md';f.write_text('退款7天')
        w.ingest(self.inputs);f.write_text('退款14天')
        self.assertEqual(w.search('退款'), [])
        w.ingest(self.inputs)
        self.assertEqual(w.search('退款')[0]['quote'], '退款14天')
        self.assertEqual(len(w.read()['sources']),2)

    def test_source_update_invalidates_derived_artifact(self):
        w=self.workspace();f=self.inputs/'policy.md';f.write_text('退款7天');w.ingest(self.inputs)
        ref=w.search('退款')[0]['source_ref']
        w.save_artifact('report.md','7天',source_refs=[ref])
        f.write_text('退款14天');w.ingest(self.inputs)
        self.assertEqual(w.read()['artifacts']['report.md']['status'],'stale')

    def test_manual_edit_is_not_overwritten(self):
        w=self.workspace();w.save_artifact('report.md','original')
        (w.root/'results/report.md').write_text('my edit')
        with self.assertRaises(ValueError):w.save_artifact('report.md','replacement')
        self.assertEqual((w.root/'results/report.md').read_text(),'my edit')

    def test_replacing_result_preserves_previous_content(self):
        w=self.workspace();w.save_artifact('r.md','old report')
        old=w.read()['artifacts']['r.md']['sha256']
        w.save_artifact('r.md','new report',expected_hash=old)
        history=w.read()['artifacts']['r.md']['history'][0]
        self.assertEqual((w.root/history['snapshot']).read_text(),'old report')

    def test_status_exposes_stale_sources_without_reimporting(self):
        w=self.workspace();f=self.inputs/'p.md';f.write_text('old');w.ingest(self.inputs)
        ref=w.search('old')[0]['source_ref'];w.save_artifact('r.md','result',source_refs=[ref])
        f.write_text('new')
        report=w.inspect()
        self.assertEqual(report['artifacts']['r.md']['status'],'stale')
        self.assertNotIn('text',report['sources'][ref])

    def test_empty_extraction_is_not_ready(self):
        m=implementation('manifest');(self.inputs/'empty.md').write_text('')
        self.assertEqual(m.scan(self.inputs)[0]['status'],'empty_extraction')

    def test_artifact_parent_traversal_and_symlinks_rejected(self):
        w=self.workspace()
        for p in ['../escape.md','/tmp/escape.md']:
            with self.assertRaises(ValueError):w.save_artifact(p,'bad')
        (w.root/'results/link').symlink_to(self.inputs,target_is_directory=True)
        with self.assertRaises(ValueError):w.save_artifact('link/escape.md','bad')

    def test_revision_conflict_preserves_new_state(self):
        w=self.workspace();rev=w.read()['revision']
        w.update({'next_action':'new'},expected_revision=rev)
        with self.assertRaises(ValueError):w.update({'next_action':'old'},expected_revision=rev)
        self.assertEqual(w.read()['next_action'],'new')

    def test_rule_activation_requires_real_approval_fields(self):
        w=self.workspace()
        with self.assertRaises(ValueError):w.put_rule('r1','一个政策',status='active')
        w.put_rule('r1','一个候选')
        self.assertEqual(w.read()['rules']['r1']['status'],'candidate')

    def test_revocation_removes_search_and_restricts_outputs(self):
        w=self.workspace();(self.inputs/'p.md').write_text('合同甲方');w.ingest(self.inputs)
        ref=w.search('甲方')[0]['source_ref'];w.save_artifact('r.md','甲方',source_refs=[ref]);w.revoke(ref)
        self.assertEqual(w.search('甲方'),[])
        self.assertEqual(w.read()['artifacts']['r.md']['status'],'restricted')

    def test_revoked_source_identity_stays_denied_after_content_change(self):
        w=self.workspace();f=self.inputs/'p.md';f.write_text('old policy');w.ingest(self.inputs)
        w.revoke(w.search('policy')[0]['source_ref'])
        f.write_text('new policy');w.ingest(self.inputs)
        self.assertEqual(w.search('policy'),[])

    def test_artifact_aliases_share_one_history_and_dependency(self):
        w=self.workspace();w.save_artifact('r.md','old')
        old=w.read()['artifacts']['r.md']['sha256']
        w.save_artifact('./r.md','new',expected_hash=old)
        self.assertEqual(set(w.read()['artifacts']),{'r.md'})
        self.assertEqual(len(w.read()['artifacts']['r.md']['history']),1)

    def test_case_insensitive_filesystem_aliases_do_not_split_artifacts(self):
        w=self.workspace();w.save_artifact('r.md','old')
        if not (w.root/'results/R.MD').exists():self.skipTest('Case-sensitive filesystem')
        old=w.read()['artifacts']['r.md']['sha256']
        w.save_artifact('R.MD','new',expected_hash=old)
        self.assertEqual(list(w.read()['artifacts']),['r.md'])

    def test_revoked_source_directory_case_alias_cannot_restore_access(self):
        w=self.workspace();(self.inputs/'p.md').write_text('private policy');w.ingest(self.inputs)
        alias=self.inputs.with_name('INPUTS')
        if not alias.exists():self.skipTest('Case-sensitive filesystem')
        w.revoke(w.search('policy')[0]['source_ref']);w.ingest(alias)
        self.assertEqual(w.search('policy'),[])

    def test_status_checks_modified_artifacts_and_stale_rule_sources(self):
        w=self.workspace();f=self.inputs/'p.md';f.write_text('policy');w.ingest(self.inputs)
        ref=w.search('policy')[0]['source_ref'];w.save_artifact('r.md','old',source_refs=[ref])
        w.put_rule('r','rule',status='active',source_refs=[ref],owner='owner',scope='test',approval_ref='decision-1')
        (w.root/'results/r.md').write_text('user edit');f.write_text('new policy')
        status=w.inspect()
        self.assertEqual(status['artifacts']['r.md']['disk_state'],'modified_by_user')
        self.assertEqual(status['rules']['r']['effective_status'],'needs_review')
        (w.root/'results/r.md').unlink()
        self.assertEqual(w.inspect()['artifacts']['r.md']['disk_state'],'missing')

    def test_history_namespace_cannot_be_written_as_user_artifact(self):
        w=self.workspace()
        with self.assertRaises(ValueError):w.save_artifact('.history/overwrite.txt','bad')

    def test_weighted_rate_and_zero_denominator(self):
        m=implementation('reconcile')
        f=self.inputs/'r.csv';f.write_text('sku,clicks,conversions,currency,period\nA,100,10,CNY,09\nB,1000,20,CNY,09\n')
        out=m.aggregate_rates(f)
        self.assertEqual(out['numerator'],'30');self.assertEqual(out['denominator'],'1100')
        self.assertEqual(out['rate'],'0.02727273')
        f.write_text('sku,clicks,conversions,currency,period\nA,0,0,CNY,09\n')
        self.assertIsNone(m.aggregate_rates(f)['rate'])

    def test_blank_nonfinite_mixed_period_and_duplicate_grain_rejected(self):
        m=implementation('reconcile');f=self.inputs/'r.csv'
        for rows in ['A,,1,CNY,09','A,NaN,1,CNY,09','A,100,10,CNY,09\nB,100,10,CNY,10','A,100,10,CNY,09\nA,100,10,CNY,09']:
            f.write_text('sku,clicks,conversions,currency,period\n'+rows+'\n')
            with self.assertRaises(ValueError):m.aggregate_rates(f)

    def test_money_comparison_does_not_merge_different_currencies(self):
        m=implementation('reconcile');a=self.inputs/'a.csv';b=self.inputs/'b.csv'
        a.write_text('id,amount,currency\n1,0.1,CNY\n2,0.2,USD\n')
        b.write_text('id,amount,currency\n1,0.10,CNY\n2,0.21,USD\n')
        rows=m.compare_amounts(a,b)
        self.assertEqual(rows[0]['status'],'matched')
        self.assertEqual(Decimal(rows[1]['difference']),Decimal('-0.01'))

    def test_duplicate_csv_headers_and_ragged_rows_cannot_change_money(self):
        m=implementation('reconcile');a=self.inputs/'a.csv';b=self.inputs/'b.csv'
        b.write_text('id,amount,currency\n1,0.00,CNY\n')
        for text in ['id,amount,amount,currency\n1,100.00,0.00,CNY\n', 'id,amount,currency\n1,0.00,CNY,100.00\n']:
            a.write_text(text)
            with self.assertRaises(ValueError):m.compare_amounts(a,b)

    def test_action_timeout_never_means_safe_retry(self):
        m=implementation('actions');a=m.make_action('sku1','v1','set-stock',{'quantity':5})
        self.assertEqual(m.retry_decision(a,{'status':'execution_unknown'})['decision'],'query_first')

    def test_legacy_unknown_and_verified_states_preserve_retry_boundary(self):
        m=implementation('actions');a=m.make_action('sku1','v1','stock',{'quantity':5})
        for status in ['outcome_unknown','pending_unknown','executing']:
            self.assertEqual(m.retry_decision(a,{'status':status})['decision'],'query_first')
        self.assertEqual(m.retry_decision(a,{'status':'succeeded_verified'})['decision'],'do_not_repeat')

    def test_missing_or_corrupt_outcome_must_be_queried_first(self):
        m=implementation('actions');a=m.make_action('sku1','v1','stock',{'quantity':5})
        for outcome in [{},{'status':None},{'status':'new_unrecognized_status'}]:
            self.assertEqual(m.retry_decision(a,outcome)['decision'],'query_first')

    def test_action_identity_changes_with_parameters_and_version(self):
        m=implementation('actions')
        a=m.make_action('sku1','v1','stock',{'quantity':5})
        self.assertEqual(a,m.make_action('sku1','v1','stock',{'quantity':5}))
        self.assertNotEqual(a['action_id'],m.make_action('sku1','v2','stock',{'quantity':5})['action_id'])
        self.assertNotEqual(a['action_id'],m.make_action('sku1','v1','stock',{'quantity':6})['action_id'])

    def test_action_approval_stale_version_and_expiry(self):
        m=implementation('actions');a=m.make_action('sku1','v1','stock',{'quantity':5})
        auth={'object_id':'sku1','operation':'stock','parameter_hash':a['parameter_hash'],'version':'v1','expires_at':'2030-01-01T00:00:00+00:00','evidence_ref':'approval-1'}
        self.assertEqual(m.assess(a,'v1',auth,now='2026-10-25T00:00:00+00:00')['decision'],'ready_for_authorized_executor')
        self.assertEqual(m.assess(a,'v2',auth,now='2026-10-25T00:00:00+00:00')['decision'],'blocked')
        self.assertEqual(m.assess(a,'v1',auth,now='2031-10-25T00:00:00+00:00')['decision'],'blocked')

    def test_mutated_action_parameters_cannot_reuse_old_approval(self):
        m=implementation('actions');a=m.make_action('sku1','v1','stock',{'quantity':5})
        auth={'object_id':'sku1','operation':'stock','parameter_hash':a['parameter_hash'],'version':'v1','expires_at':'2030-01-01T00:00:00+00:00','evidence_ref':'approval-1'}
        a['parameters']['quantity']=500
        self.assertEqual(m.assess(a,'v1',auth,now='2026-10-25T00:00:00+00:00')['decision'],'blocked')

if __name__=='__main__':unittest.main()
