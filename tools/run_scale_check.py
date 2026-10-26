"""Exercise a 1000-item synthetic inventory, including explicit denied references."""
from pathlib import Path
import json
import sys
from collections import Counter
SCRIPTS=Path(__file__).resolve().parents[1]/'skills/build-role-workspace/scripts'
sys.path.insert(0,str(SCRIPTS))
from manifest import scan

def run(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True);source=out/'inputs';source.mkdir(exist_ok=True)
    # Rights-denied references are never opened or hashed. They are not created as files.
    denied=[{'manifest_item_id':f'rights-{i:03d}','path':f'denied/{i}.txt','status':'rights_blocked'} for i in range(30)]
    for i in range(860):(source/f'a-{i:04d}.txt').write_text(f'synthetic unique {i}\n',encoding='utf-8')
    for i in range(80):(source/f'b-{i:04d}.txt').write_text(f'synthetic unique {i}\n',encoding='utf-8')
    for i in range(20):(source/f'c-{i:04d}.txt').write_bytes(b'\xff\xfe'+str(i).encode())
    for i in range(10):(source/f'd-{i:04d}.bin').write_bytes(b'binary'+str(i).encode())
    items=scan(source)+denied
    mapping={'ready':'processable','requires_host_extraction':'unsupported'}
    counts=Counter(mapping.get(x['status'],x['status']) for x in items)
    partial=['ready']*600+['awaiting_human']*120+['budget_paused']*80+['extraction_recovery']*40+['running']*20
    processable=[x for x in items if x['status']=='ready']
    for item,state in zip(processable,partial):item['seeded_processing_state']=state
    result=dict(is_synthetic=True,real_media_test=False,counts=dict(counts),items=items,
                intermediate_snapshot=dict(Counter(partial)),
                limitations=['Processing states are controlled fault-fixture states, not 860 completed business tasks.',
                             'Only inventory and ledger were run; human decisions, real paid extraction and external execution are not implied.'])
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    return result
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output');a=p.parse_args()
    r=run(Path(a.output));print(json.dumps({k:r[k] for k in ['counts','intermediate_snapshot','limitations']},ensure_ascii=False,indent=2))
