"""S01 controlled transaction-scale test, distinct from historical file-inventory check."""
from pathlib import Path
import importlib.util,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]

class FinancialScaleTests(unittest.TestCase):
    def test_actual_calculation_recovery_pending_and_inflight_dispositions(self):
        path=ROOT/'tools/run_financial_scale_check.py'
        self.assertTrue(path.exists())
        spec=importlib.util.spec_from_file_location('financial_scale',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
        with tempfile.TemporaryDirectory() as t:
            r=m.run(Path(t))
            self.assertEqual(r['counts'],{'processable':860,'duplicate':80,'rights_blocked':30,'unreadable':20,'unsupported':10})
            self.assertEqual(r['intermediate_counts'],{'ready':600,'awaiting_human':120,'budget_paused':80,'extraction_recovery':40,'running':20})
            self.assertEqual(r['calculated_records'],660)
            self.assertEqual(r['actual_reconciliation_rows'],660)
            self.assertEqual(r['independent_numeric_checks'],660)
            self.assertEqual(r['still_waiting'],{'awaiting_human':120,'budget_paused':80})
            self.assertEqual(len(r['items']),1000)
            self.assertEqual(len({x['id'] for x in r['items']}),1000)
            self.assertTrue(r['source_files_unchanged'])
            self.assertFalse(r['external_execution'])

if __name__=='__main__':unittest.main()
