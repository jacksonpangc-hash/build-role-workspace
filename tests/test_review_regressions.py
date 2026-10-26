"""Independent-review counterexamples and adjacent business invariants; all synthetic."""
from pathlib import Path
import sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/build-role-workspace/scripts'))
from records import Records
from planning import inventory


def scenario(**overrides):
    data=dict(demand=100,buffer=0,on_hand=10,inbound=[{'day':9,'quantity':80}],commitments=0,
              reservations_already_deducted=False,lead_days=1,horizon_days=10,daily_demand=10,
              moq=1,multiple=1,unit_cost=1,budget=100,sellable_days=30,unit='item',
              as_of='2025-05-31',assumption_ref='synthetic-independent-review')
    data.update(overrides);return data


class RevocationPrecedenceTests(unittest.TestCase):
    def test_revoked_dependency_dominates_changed_missing_and_other_stale_branches(self):
        for mutation in ['changed','missing','unchanged']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as t:
                t=Path(t).resolve();p=t/'derived.txt';p.write_text('original')
                r=Records(t/'private','scope');r.put('source','raw',{'content':'SYNTHETIC_SECRET'})
                r.put('source','other',{'version':'1'})
                r.put('artifact','derived',{'file_ref':{'path':str(p),'sha256':__import__('hashlib').sha256(p.read_bytes()).hexdigest()},'content':'SYNTHETIC_DERIVATIVE'},['source:raw','source:other'])
                r.put('report','grandchild',{'content':'SYNTHETIC_GRANDCHILD'},['artifact:derived'])
                r.put('source','other',{'version':'2'},expected_revision=1)
                r.revoke('source','raw')
                if mutation=='changed':p.write_text('changed')
                if mutation=='missing':p.unlink()
                for kind,name in [('artifact','derived'),('report','grandchild')]:
                    self.assertEqual(r.get(kind,name)['effective_status'],'restricted')
                    self.assertEqual(r.get(kind,name)['value'],{})
                    self.assertTrue(all(x['value']=={} for x in r.history(kind,name)))
                # Raw historical content is preserved on disk, but not returned through restricted reads.
                self.assertIn('SYNTHETIC_DERIVATIVE',r.path.read_text())
                with self.assertRaises(ValueError):r.put('artifact','derived',{'content':'copied secret'},expected_revision=1)

    def test_history_checks_each_revision_ancestry_after_clean_reparent(self):
        with tempfile.TemporaryDirectory() as t:
            r=Records(t,'scope');r.put('source','old',{'text':'old'})
            r.put('source','new',{'text':'new'})
            r.put('artifact','answer',{'text':'OLD_RESTRICTED'},['source:old'])
            r.put('artifact','answer',{'text':'NEW_CLEAN'},['source:new'],expected_revision=1,provenance_change_ref='synthetic-new-source-rederive-evidence')
            r.revoke('source','old')
            self.assertEqual(r.get('artifact','answer')['effective_status'],'current')
            history=r.history('artifact','answer')
            self.assertEqual(history[0]['value'],{})
            self.assertEqual(history[1]['value']['text'],'NEW_CLEAN')

    def test_plain_stale_and_current_still_readable(self):
        with tempfile.TemporaryDirectory() as t:
            t=Path(t).resolve();p=t/'a';p.write_text('1')
            r=Records(t/'w','scope');r.observe_file('source','a',p)
            r.put('artifact','answer',{'text':'retain'},['source:a'])
            self.assertEqual(r.get('artifact','answer')['effective_status'],'current')
            p.write_text('2')
            self.assertEqual(r.get('artifact','answer')['effective_status'],'stale')
            self.assertEqual(r.get('artifact','answer')['value']['text'],'retain')


class InventoryTimelineTests(unittest.TestCase):
    def assert_daily_conservation(self,result,data):
        self.assertEqual(len(result['daily_projection']),data['horizon_days'])
        balance=data['on_hand']-(0 if data['reservations_already_deducted'] else data['commitments'])
        from decimal import Decimal
        balance=Decimal(str(balance));q=Decimal(result['candidate_quantity'])
        for row in result['daily_projection']:
            d=row['day'];receipts=sum(Decimal(str(x['quantity'])) for x in data['inbound'] if x['day']==d)
            balance+=receipts+(q if d==data['lead_days'] else 0)-Decimal(str(data['daily_demand']))
            self.assertEqual(Decimal(row['closing_balance']),balance)

    def test_independent_counterexample_seven_mid_horizon_shortages(self):
        data=scenario();r=inventory(data)
        self.assertEqual(r['position'],'90');self.assertEqual(r['candidate_quantity'],'10')
        self.assertEqual([x['day'] for x in r['planning_shortages']],list(range(2,9)))
        self.assertEqual(r['decision'],'needs_review');self.assert_daily_conservation(r,data)

    def test_zero_order_still_checks_late_receipts_and_horizon_end(self):
        data=scenario(inbound=[{'day':9,'quantity':90}]);r=inventory(data)
        self.assertEqual(r['candidate_quantity'],'0');self.assertTrue(r['planning_shortages'])
        # horizon=10 covers days0..9; day10 receipt cannot support this period.
        data=scenario(inbound=[{'day':10,'quantity':100}]);r=inventory(data)
        self.assertEqual(r['position'],'10');self.assertEqual(r['candidate_quantity'],'90')
        self.assert_daily_conservation(r,data)

    def test_no_inbound_multiple_batches_reservations_and_late_candidate(self):
        for data in [scenario(inbound=[]),scenario(inbound=[{'day':2,'quantity':30},{'day':6,'quantity':20}]),
                     scenario(commitments=5),scenario(commitments=5,reservations_already_deducted=True),
                     scenario(lead_days=12,inbound=[])]:
            with self.subTest(data=data):
                r=inventory(data);self.assert_daily_conservation(r,data)
                if data['lead_days']>=data['horizon_days'] and r['candidate_quantity']!='0':self.assertIn('late_candidate_arrival',r['constraint_failures'])

    def test_frozen_example_moq_budget_life_missing_and_bad_period(self):
        data=scenario(demand=100,buffer=20,on_hand=40,inbound=[{'day':3,'quantity':30}],commitments=10,
                      lead_days=5,moq=48,multiple=24,unit_cost=2,budget=200,sellable_days=20)
        r=inventory(data);self.assertEqual((r['position'],r['raw_gap'],r['candidate_quantity']),('60','60','72'))
        self.assert_daily_conservation(r,data)
        self.assertIn('budget',inventory(dict(data,budget=100))['constraint_failures'])
        self.assertIn('sellable_life',inventory(dict(data,sellable_days=1))['constraint_failures'])
        missing=dict(data);missing.pop('on_hand');self.assertIsNone(inventory(missing)['candidate_quantity'])
        with self.assertRaises(ValueError):inventory(dict(data,horizon_days=0))
        with self.assertRaises(ValueError):inventory(dict(data,demand=200))


class RecordDisplayBoundaryTests(unittest.TestCase):
    def test_read_redacts_each_restricted_historical_value_without_altering_storage(self):
        with tempfile.TemporaryDirectory() as t:
            r=Records(t,'scope');r.put('source','raw',{'text':'RAW_SECRET'})
            r.put('artifact','derived',{'text':'DERIVED_SECRET'},['source:raw'])
            r.revoke('source','raw')
            displayed=r.read()
            self.assertTrue(all(row['value']=={} for rows in displayed['records'].values() for row in rows))
            self.assertIn('DERIVED_SECRET',r.path.read_text())

    def test_stale_provenance_removal_needs_explicit_replacement_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            r=Records(t,'scope');r.put('source','a',{'v':1});r.put('artifact','answer',{'text':'old'},['source:a'])
            r.put('source','a',{'v':2},expected_revision=1)
            with self.assertRaises(ValueError):r.put('artifact','answer',{'text':'old'},expected_revision=1)
            p=Path(t).resolve()/'source.txt';p.write_text('1');r.observe_file('source','file',p)
            p.write_text('2')
            with self.assertRaises(ValueError):r.put('source','file',{'text':'old'},expected_revision=1)

class DependencyReadCostTests(unittest.TestCase):
    def test_current_chain_checks_a_leaf_file_once_instead_of_exponential_rereads(self):
        import records
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as t:
            t=Path(t).resolve();p=t/'source.csv';p.write_text('id,amount\n1,10')
            r=Records(t/'w','scope');r.observe_file('source','leaf',p)
            dep='source:leaf'
            for i in range(8):
                r.put('artifact','layer'+str(i),{},[dep]);dep='artifact:layer'+str(i)
            with patch.object(records,'sha256',wraps=records.sha256) as hashing:
                self.assertEqual(r.get('artifact','layer7')['effective_status'],'current')
                self.assertEqual(hashing.call_count,1)


if __name__=='__main__':unittest.main()
