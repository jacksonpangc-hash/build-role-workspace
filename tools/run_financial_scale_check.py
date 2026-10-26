"""S01 synthetic transaction calculation/recovery fixture. No accounts, payments or human approvals."""
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv,hashlib,json,sys,threading
from decimal import Decimal
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/build-role-workspace/scripts'))
from manifest import scan,sha256
from reconcile import compare_amounts,number


def write_rows(path,rows,fields):
    with Path(path).open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)


def run(out):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise ValueError('Use a new empty synthetic output directory; existing work is never overwritten')
    source=out/'inputs';source.mkdir(exist_ok=True)
    fields=['id','amount','currency'];expected={}
    for i in range(860):
        key=f'TX{i:04d}';amount=Decimal(i+1)/100;currency='USD' if i%5==0 else 'CNY'
        expected[key]=dict(id=key,amount=str(amount),currency=currency)
        # 40 parsable text sources lack a numeric field, then obtain a separate
        # corrected extraction fixture. Never alter original evidence to recover.
        row=dict(expected[key],amount='' if 800<=i<840 else str(amount))
        write_rows(source/f'a-{i:04d}.csv',[row],fields)
    for i in range(80):(source/f'b-{i:04d}.csv').write_bytes((source/f'a-{i:04d}.csv').read_bytes())
    for i in range(20):(source/f'c-{i:04d}.csv').write_bytes(b'\xff\xfe'+str(i).encode())
    for i in range(10):(source/f'd-{i:04d}.bin').write_bytes(b'unsupported-'+str(i).encode())
    inventory=scan(source)
    initial_hashes={x['path']:x['sha256'] for x in inventory if x.get('sha256')}
    items=[];processable=[]
    for n,row in enumerate(inventory):
        status={'ready':'processable','requires_host_extraction':'unsupported'}.get(row['status'],row['status'])
        item=dict(id=f'REF{n:04d}',source=row['path'],sha256=row.get('sha256'),status=status)
        items.append(item)
        if status=='processable':processable.append(item)
    # Thirty synthetic rights-denied descriptors have no file: never opened/hashed.
    items.extend(dict(id=f'DENIED{i:04d}',source=f'denied/{i}',status='rights_blocked') for i in range(30))
    counts=dict(Counter(x['status'] for x in items))
    assert len(processable)==860
    def read(item):
        with (source/item['source']).open(newline='') as f:r=next(csv.DictReader(f))
        number(r['amount'])
        return r
    ready=processable[:600];human=processable[600:720];paused=processable[720:800];recovery=processable[800:840];running=processable[840:]
    # Calculation job budget is 620: 600 run synchronously and 20 were reserved
    # and are genuinely in flight. Remaining 80 are not silently processed.
    for item in ready:item['processing']='ready'
    for item in human:item['processing']='awaiting_human'
    for item in paused:item['processing']='budget_paused'
    parse_failures=[]
    for item in recovery:
        try:read(item)
        except ValueError as error:item['processing']='extraction_recovery';parse_failures.append({'id':item['id'],'reason':str(error)})
        else:raise AssertionError('Fault fixture failed to trigger missing amount')
    rendezvous=threading.Barrier(21);release=threading.Event()
    def pending(item):
        item['processing']='running';rendezvous.wait(timeout=10);release.wait(timeout=10)
        return read(item)
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures=[pool.submit(pending,item) for item in running]
        rendezvous.wait(timeout=10)
        middle=dict(Counter(x['processing'] for x in processable))
        # Actual compare_amounts runs on 600 normalized transactions.
        left=[read(item) for item in ready]
        right=[dict(r,amount=str(number(r['amount'])+(Decimal('0.01') if int(r['id'][2:])%3==0 else 0))) for r in left]
        write_rows(out/'left.csv',left,fields);write_rows(out/'right.csv',right,fields)
        compared=compare_amounts(out/'left.csv',out/'right.csv')
        checks=[]
        for row in compared:
            key=row['key']['id'];delta=Decimal('-0.01') if int(key[2:])%3==0 else Decimal(0)
            assert number(row['difference'])==delta
            assert row['status']==('difference' if delta else 'matched')
            checks.append(key)
        release.set();inflight=[f.result(timeout=10) for f in futures]
    for row in inflight:assert row==expected[row['id']]
    # Recovery has an explicit new synthetic extraction source, kept independently.
    repairs=[expected[f'TX{i:04d}'] for i in range(800,840)]
    write_rows(out/'corrected-extraction.csv',repairs,fields)
    for row,item in zip(repairs,recovery):
        assert row==expected[row['id']];item['processing']='calculated_after_extraction_recovery'
    remaining=repairs+inflight
    other=[dict(row,amount=str(number(row['amount'])+(Decimal('0.01') if int(row['id'][2:])%3==0 else 0))) for row in remaining]
    write_rows(out/'recovered-left.csv',remaining,fields);write_rows(out/'recovered-right.csv',other,fields)
    recovered_comparison=compare_amounts(out/'recovered-left.csv',out/'recovered-right.csv')
    for row in recovered_comparison:
        key=row['key']['id'];delta=Decimal('-0.01') if int(key[2:])%3==0 else Decimal(0)
        assert number(row['difference'])==delta
        assert row['status']==('difference' if delta else 'matched')
        checks.append(key)
    for item in ready+running:item['processing']='calculated'
    assert len(set(checks))==660
    unchanged=all(sha256(source/name)==value for name,value in initial_hashes.items())
    result=dict(seed='deterministic TX0..859, cent amounts, USD every fifth ID',synthetic_only=True,
                counts=counts,intermediate_counts=middle,parse_failures=parse_failures,calculated_records=660,
                independent_numeric_checks=len(checks),actual_reconciliation_rows=len(compared)+len(recovered_comparison),
                actual_inflight_jobs_observed=20,still_waiting={'awaiting_human':120,'budget_paused':80},
                source_files_unchanged=unchanged,external_execution=False,items=items,
                qualification='Permission/review/budget categories are declared synthetic controls, not real company decisions. 660 local calculations/recoveries, not 860 completed business tasks. No denied reference read, no human approval fabricated.')
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');a=p.parse_args()
    r=run(a.output);print(json.dumps({k:r[k] for k in ['counts','intermediate_counts','calculated_records','still_waiting','source_files_unchanged','qualification']},ensure_ascii=False,indent=2))
