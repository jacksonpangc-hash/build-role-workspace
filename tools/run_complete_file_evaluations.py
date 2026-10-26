"""Opt-in positive-file supplements. Earlier missing/correction/resume evidence remains immutable."""
import argparse,csv,hashlib,json,shutil,time
from pathlib import Path
from run_model_evaluations import ROOT,prepare,bounded_invoke


def csvfile(path,fields,rows):
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(fields);w.writerows(rows)


def structured_inputs(folder,flows):
    for case in flows:
        dest=folder/'inputs/complete'/case['id'];dest.mkdir(parents=True)
        (dest/'source.md').write_text('# 完整合成来源\n\n'+case['complete_source']+'\n\n'+case['qualification']+'\n')
        i=case['id']
        if i=='03-W1':
            csvfile(dest/'orders.csv',['order_id','date','currency','payable'],[['O1','2025-05-01','CNY','30']])
            csvfile(dest/'lines.csv',['line_id','order_id','sku','purchased_quantity','bags_per_unit'],[['L1','O1','A','2','1']])
            csvfile(dest/'payments.csv',['event_id','order_id','date','currency','amount'],[['P1','O1','2025-05-01','CNY','30']])
            csvfile(dest/'refunds.csv',['event_id','order_id','date','currency','amount'],[['R1','O1','2025-06-01','CNY','5']])
            csvfile(dest/'ads.csv',['attribution_id','order_id','currency','attributed_payments','spend'],[['AD1','O1','CNY','20','6'],['AD2','O1','CNY','15','4']])
        if i=='05-W1':
            csvfile(dest/'bank.csv',['id','currency','amount'],[['B1','CNY','100'],['B2','CNY','50'],['B3','USD','5']])
            csvfile(dest/'book.csv',['id','currency','amount'],[['B1','CNY','100'],['B2','CNY','40'],['B3','USD','5']])
        if i=='06-W1':
            (dest/'contract-C1.md').write_text('# 合成合同C1 v1\n\n主体：Synthetic Buyer与Synthetic Supplier。条款：交付后30个自然日付款，本例不顺延。附件A属于本合同。仅测试文书，不构成真实合同。\n')
            (dest/'attachment-A.md').write_text('# 合成附件A v1\n\n关联C1，交付日期2025-05-15，模拟接收记录DEL1确认交付。仅用于算法演练。\n')
            (dest/'signature-receipt.json').write_text(json.dumps({'simulation_only':True,'contract':'C1','version':'v1','status':'both_parties_confirmed_in_fixture','date':'2025-05-10','authentic_person_signature':'NOT_VALIDATED'},indent=2))
        if i=='06-W2':
            (dest/'receipts.json').write_text(json.dumps({'simulation_only':True,'person':'E1','approved_transfer':'AP1','effective':'2025-06-01','asset_receipts':[{'asset':'A1','received':True,'accepted':True},{'asset':'A2','received':True,'accepted':True}],'documents_received':True,'documents_accepted':True,'ledger_version':'F2'},indent=2))
        if i=='06-W3':
            csvfile(dest/'tickets.csv',['ticket_id','person','period','currency','amount','category'],[['T1','E1','2025-06','CNY','120','交通'],['T1','E1','2025-06','CNY','120','交通'],['T2','E1','2025-06','CNY','70','交通']])
        if i=='09-W2':
            csvfile(dest/'attendance.csv',['person','date','planned_hours','clocked_hours','approved_leave_hours'],[['E1','2025-06-01','8','6','2'],['E2','2025-06-01','8','8','0']])
        if i=='11-W2':
            csvfile(dest/'shipment-events.csv',['event_id','order_id','parcel_id','state','quantity'],[['D1','O1','P1','dispatched','5'],['D2','O1','P2','dispatched','5'],['S1','O1','P1','signed','5'],['S1','O1','P1','signed','5'],['S2','O1','P2','signed','5']])
        if i=='13-W1':
            csvfile(dest/'events.csv',['event_id','occurred','currency','kind','amount'],[['P1','2025-05-01','CNY','payment','100'],['P2','2025-05-02','CNY','payment','50'],['P1','2025-05-01','CNY','payment','100'],['R2','2025-05-03','CNY','refund','10'],['P3','2025-05-04','USD','payment','5'],['R1','2025-06-01','CNY','refund','30']])
        if i=='13-W3':
            csvfile(dest/'lines.csv',['order_id','purchased_quantity'],[['O1','2'],['O2','4']])
            (dest/'old-report.md').write_text('旧版v1：五月订单数2。\n\n人工备注（合成编辑测试）：保留我这句话。\n')


def run(output,previous):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    if any(output.iterdir()):raise ValueError('Fresh output required')
    previous=Path(previous).resolve()
    cases=json.loads((ROOT/'examples/synthetic/complete-file-sources.json').read_text())
    results=[]
    for role in sorted({x['role'] for x in cases}):
        done=previous/(role+'.summary.json')
        deadline=time.monotonic()+3*60*60
        while not done.exists() and time.monotonic()<deadline:time.sleep(5)
        if not done.exists():
            result={'role':role,'result':'blocked_previous_run_not_finished'}
        else:
            folder=output/role/'host';prepare(folder)
            before=previous/role/'host/results'
            if before.exists():shutil.copytree(before,folder/'previous-results')
            old_inputs=previous/role/'host/inputs'
            if old_inputs.exists():
                for old in old_inputs.rglob('*'):
                    if old.is_file():
                        dest=folder/'inputs'/old.relative_to(old_inputs);dest.parent.mkdir(parents=True,exist_ok=True)
                        if dest.exists():raise ValueError('Input collision; do not overwrite')
                        shutil.copy2(old,dest)
            flows=[x for x in cases if x['role']==role];structured_inputs(folder,flows)
            if role=='video_analysis':shutil.copytree(ROOT/'examples/synthetic/media',folder/'inputs/media')
            prompt='请从当前目录接手这个岗位的三项工作。previous-results保留上轮受限来源结果，不能改写成当时资料完整。现在inputs/complete给了另一个完整合成来源分支；请实际完成各ID工作，而不只交计划或空模板，每项保存results/<ID>/normal-complete.md及可追的来源、计算/判断、范围和交接。旧缺件分支不得套用新分支事实。正文一屏、一个主要行动，技术明细另存。模拟批准/回证不是真实账号或专业签核，本轮仅文件。图像/字幕/音轨只报实际读到的内容。'
            if role=='video_analysis':prompt+=' 实际媒体在inputs/media，PNG由MP4真实解码；请实际查看画面而非只复述文件名，静音源不存在声音，字幕是侧车文件，不是实拍产品证明。'
            r=bounded_invoke(folder,prompt,output/role/'logs','complete-positive',300 if role=='video_analysis' else 240,8 if role=='video_analysis' else 6)
            artifacts=[]
            for c in flows:
                p=folder/'results'/c['id']/'normal-complete.md'
                if p.exists():artifacts.append({'flow':c['id'],'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
            result={'role':role,'run':r,'artifacts':artifacts,'result':'executed_awaiting_semantic_review' if r['returncode']==0 and len(artifacts)==3 else 'failed_or_incomplete'}
        results.append(result);(output/(role+'.summary.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(role,result['result'],flush=True)
        (output/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    return results


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--previous',required=True);a=p.parse_args();run(a.output,a.previous)
