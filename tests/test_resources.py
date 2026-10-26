import json
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
SKILL=ROOT/'skills/build-role-workspace'

class ResourcesTests(unittest.TestCase):
    def read(self,name):
        p=SKILL/'references/catalog'/name
        self.assertTrue(p.exists(),'Missing runtime catalog '+name)
        return json.loads(p.read_text())
    def test_all_original_ids_map_to_runtime_role_and_resolvable_card(self):
        data=self.read('scenarios.json')
        historical=ROOT/'references/v3-original/catalog/role_scenarios.json'
        if historical.exists():
            original=json.loads(historical.read_text())
            self.assertEqual({(x['role_id'],x['scenario_id']) for x in data},{(x['role_id'],x['scenario_id']) for x in original})
        self.assertEqual(len({(x['role_id'],x['scenario_id']) for x in data}),198)
        self.assertEqual(len(data),198)
        self.assertEqual(sum(x['origin']=='baseline' for x in data),133)
        self.assertEqual(len({x['runtime_role_id'] for x in data}),14)
        for x in data:self.assertTrue((SKILL/x['reference']).is_file())
    def test_blueprints_include_required_and_conditional_scenarios(self):
        cards={x['id']:x for x in self.read('blueprints.json')}
        self.assertIn('A16',cards['APP-C01']['required'])
        self.assertIn('E04',cards['APP-C02']['required'])
        self.assertIn('A12',cards['APP-C03']['required'])
        self.assertNotIn('D01',cards['APP-C03']['required'])
        self.assertEqual(cards['APP-C06']['conditional']['creator_cooperation'],['SAL-15','SAL-16'])
    def test_all_deep_workflows_have_execution_and_recovery_contracts(self):
        flows=self.read('workflows.json');self.assertEqual(len(flows),42)
        counts={}
        for f in flows:
            counts[f['role_id']]=counts.get(f['role_id'],0)+1
            for field in ['inputs','steps','exceptions','output','acceptance']:
                self.assertTrue(f[field],(f['id'],field))
            self.assertEqual(f['execution_status'],'not_run')
        self.assertEqual(set(counts.values()),{3})
    def test_legal_reference_does_not_become_fifteenth_runtime_role(self):
        cards=self.read('legal.json');self.assertEqual(len(cards),8)
        self.assertTrue(all(x['readiness']=='reference_only' for x in cards))

if __name__=='__main__':unittest.main()
