"""Offline action plans only. This module has no business-system write or network executor."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def make_action(object_id,version,operation,parameters):
    if not all(isinstance(v,str) and v.strip() for v in [object_id,version,operation]) or not isinstance(parameters,dict):
        raise ValueError('Explicit object, current version, operation and parameters required')
    item=dict(object_id=object_id,version=version,operation=operation,parameter_hash=digest(parameters),parameters=parameters)
    return dict(item,action_id=digest(item),status='proposed')


def instant(value):
    t=datetime.fromisoformat(value.replace('Z','+00:00'))
    if t.tzinfo is None:raise ValueError('Timezone required')
    return t


def assess(action,live_version,authorization,now=None):
    reasons=[]
    if digest(action.get('parameters')) != action.get('parameter_hash'):
        reasons.append('Action parameters changed after planning')
    expected = make_action(action.get('object_id'), action.get('version'), action.get('operation'), action.get('parameters'))
    if expected['action_id'] != action.get('action_id'):
        reasons.append('Action identity inconsistent')
    for k in ['object_id','version','operation','parameter_hash']:
        if authorization.get(k)!=action.get(k):reasons.append('Authorization mismatch: '+k)
    if live_version!=action['version']:reasons.append('Object changed')
    if not authorization.get('evidence_ref'):reasons.append('Missing real authorization evidence')
    try:
        if instant(authorization.get('expires_at',''))<=instant(now or datetime.now(timezone.utc).isoformat()):reasons.append('Authorization expired')
    except ValueError:reasons.append('Invalid authorization expiry')
    return dict(decision='blocked' if reasons else 'ready_for_authorized_executor',reasons=reasons,
                limitation='Checks record consistency only; host must validate identity, authority, side effects and execute separately')


def retry_decision(action,outcome):
    status=outcome.get('status')
    status={'outcome_unknown':'execution_unknown','pending_unknown':'execution_unknown',
            'executing':'running','succeeded_verified':'verified_executed'}.get(status,status)
    if status in ['execution_unknown','submitted','running']:
        return dict(decision='query_first',action_id=action['action_id'])
    if status in ['verified_executed','business_closed']:
        return dict(decision='do_not_repeat',action_id=action['action_id'])
    if status in ['failed_known','proposed','awaiting_action_authorization','ready_for_authorized_executor']:
        return dict(decision='revalidate_before_retry',action_id=action['action_id'])
    return dict(decision='query_first',action_id=action['action_id'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--object-id',required=True);p.add_argument('--version',required=True);p.add_argument('--operation',required=True);p.add_argument('--parameters',required=True)
    a=p.parse_args()
    try:print(json.dumps(make_action(a.object_id,a.version,a.operation,json.loads(Path(a.parameters).read_text())),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as error:p.exit(2,str(error)+'\n')
