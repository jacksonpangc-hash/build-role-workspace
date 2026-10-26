"""Persistent offline per-action event ledger. No executor, scheduler or account authentication."""
from copy import deepcopy
from records import Records
from actions import make_action, retry_decision, digest

STATES={'submitted','running','execution_unknown','verified_executed','failed_known','business_closed'}


class Ledger:
    def __init__(self,root,scope):self.records=Records(root,scope)

    def register(self,action):
        expected=make_action(action['object_id'],action['version'],action['operation'],action['parameters'])
        if expected['action_id']!=action['action_id'] or expected['parameter_hash']!=action['parameter_hash']:raise ValueError('Invalid action identity')
        name=action['action_id'];old=self.records.get('action',name)
        if old:return old
        return self.records.put('action',name,dict(action=deepcopy(action),sequence=0,state='proposed',events={}))

    def event(self,action_id,event_id,sequence,state,evidence):
        record=self.records.get('action',action_id)
        if not record:raise ValueError('Unknown action')
        if record['effective_status']=='restricted' or record['value'].get('revocation_ref'):raise ValueError('Revoked action')
        value=deepcopy(record['value'])
        if not isinstance(event_id,str) or not event_id.strip() or type(sequence)!=int or sequence<=0 or state not in STATES or not isinstance(evidence,dict):raise ValueError('Invalid event')
        event=dict(sequence=sequence,state=state,evidence=deepcopy(evidence));hashed=digest(event)
        if event_id in value['events']:
            if value['events'][event_id]!=hashed:raise ValueError('Event ID reused with different data')
            return dict(decision='duplicate_ignored')
        if sequence<=value['sequence']:return dict(decision='out_of_order_ignored')
        if sequence!=value['sequence']+1:raise ValueError('Sequence gap; reconcile events first')
        if value['state']=='business_closed' or (value['state']=='verified_executed' and state!='business_closed'):raise ValueError('Terminal outcome cannot regress')
        if state in {'verified_executed','business_closed'} and not evidence.get('receipt'):raise ValueError('Query/acceptance receipt required')
        if state=='business_closed' and value['state']!='verified_executed':raise ValueError('Execution must be verified first')
        value.update(sequence=sequence,state=state);value['events'][event_id]=hashed
        value['last_evidence']=evidence
        return self.records.put('action',action_id,value,expected_revision=record['revision'])

    def revoke(self,action_id,evidence_ref):
        if not evidence_ref:raise ValueError('Revocation evidence required')
        record=self.records.get('action',action_id)
        if not record:raise ValueError('Unknown action')
        if record['effective_status']=='restricted':return
        value=deepcopy(record['value']);value['revocation_ref']=evidence_ref
        self.records.put('action',action_id,value,expected_revision=record['revision'])
        self.records.revoke('action',action_id)

    def decision(self,action_id):
        record=self.records.get('action',action_id)
        if not record:raise ValueError('Unknown action')
        if record['effective_status']=='restricted' or record['value'].get('revocation_ref'):return dict(decision='blocked_revoked')
        value=record['value'];return retry_decision(value['action'],{'status':value['state']})
