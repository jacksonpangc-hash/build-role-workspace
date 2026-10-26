"""Opt-in local Codex model evaluations on synthetic inputs; never runs on import or builds."""
import argparse,concurrent.futures,hashlib,json,os,re
from datetime import datetime,timezone,timedelta
from pathlib import Path
import shutil,signal,subprocess,time

ROOT=Path(__file__).resolve().parents[1]
MODEL='gpt-6.1-sol'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def invoke(folder,prompt,logroot,name,seconds=240,tool_budget=6):
    logroot=Path(logroot);logroot.mkdir(parents=True,exist_ok=True)
    final=logroot/(name+'.response.txt');event=logroot/(name+'.events.jsonl');err=logroot/(name+'.stderr')
    command=['codex','exec','--ignore-user-config','--ephemeral','--skip-git-repo-check','-m',MODEL,
             '-s','workspace-write','-c','model_reasoning_effort="low"','--json','-C',str(Path(folder).resolve()),'-o',str(final.resolve()),'-']
    prompt += f'\n本轮评估预算：最多{tool_budget}次工具调用，{seconds}秒内完成可做部分；每份给普通用户的报告首屏控制在250字左右，来源明细和机器续接另存。不要因缺件把独立可做部分停掉。预算不足如实留未完成，不编通过。'
    (logroot/(name+'.prompt.txt')).write_text(prompt)
    input_root=Path(folder)/'inputs'
    input_before={str(p.relative_to(input_root)):digest(p) for p in input_root.rglob('*') if p.is_file() and not p.is_symlink()} if input_root.exists() else {}
    (logroot/(name+'.inputs-before.json')).write_text(json.dumps(input_before,ensure_ascii=False,indent=2))
    started=time.monotonic();timed_out=False;provider_retry_not_before=None;tool_budget_exceeded=False
    with event.open('w') as output,err.open('w') as errors:
        process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=output,stderr=errors,text=True,start_new_session=True)
        sent=False
        while True:
            try:
                process.communicate(prompt if not sent else None,timeout=min(5,max(0.1,seconds-(time.monotonic()-started))))
                break
            except subprocess.TimeoutExpired:
                sent=True
                for line in err.read_text(errors='replace').splitlines():
                    if '429 Too Many Requests' in line:
                        match=re.search(r'^(\S+).*in ([0-9.]+)s',line)
                        if match:
                            until=datetime.fromisoformat(match[1].replace('Z','+00:00'))+timedelta(seconds=float(match[2]))
                            provider_retry_not_before=until.isoformat()
                observed_tools=set()
                for event_line in event.read_text(errors='replace').splitlines():
                    try:record=json.loads(event_line)
                    except json.JSONDecodeError:continue
                    item=record.get('item',{})
                    if record.get('type') in {'item.started','item.completed'} and item.get('type') not in {None,'agent_message','reasoning','error'}:
                        observed_tools.add(item.get('id'))
                tool_budget_exceeded=len(observed_tools)>tool_budget
                timed_out=time.monotonic()-started>=seconds
                if timed_out or provider_retry_not_before or tool_budget_exceeded:
                    os.killpg(process.pid,signal.SIGTERM)
                    try:process.wait(timeout=5)
                    except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait()
                    break
    events=[]
    for line in event.read_text().splitlines():
        try:events.append(json.loads(line))
        except json.JSONDecodeError:pass
    completed_tools={e.get('item',{}).get('id') for e in events if e.get('type') in {'item.started','item.completed'} and e.get('item',{}).get('type') not in {None,'agent_message','reasoning','error'}}
    tool_budget_exceeded=tool_budget_exceeded or len(completed_tools)>tool_budget
    input_after={str(p.relative_to(input_root)):digest(p) for p in input_root.rglob('*') if p.is_file() and not p.is_symlink()} if input_root.exists() else {}
    input_unchanged=all(input_after.get(k)==v for k,v in input_before.items())
    (logroot/(name+'.inputs-after.json')).write_text(json.dumps(input_after,ensure_ascii=False,indent=2))
    usage=[e.get('usage') for e in events if e.get('type')=='turn.completed']
    thread=next((e.get('thread_id') for e in events if e.get('type')=='thread.started'),None)
    result=dict(name=name,model=MODEL,reasoning_effort='low',thread_id=thread,ephemeral=True,returncode=process.returncode,
                timed_out=timed_out,input_sources_preserved=input_unchanged,observed_tool_items=len(completed_tools),tool_budget_exceeded=tool_budget_exceeded,tool_budget_enforcement='monitor logged runtime tool items; exceeded runs rejected',provider_retry_not_before=provider_retry_not_before,elapsed_seconds=round(time.monotonic()-started,3),wall_budget_seconds=seconds,tool_call_budget=tool_budget,usage=usage,
                billing_amount=None,billing_status='UNKNOWN: token counts are usage, not billed currency',
                files={p.name:digest(p) for p in [final,event,err] if p.exists()})
    (logroot/(name+'.run.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


def bounded_invoke(folder,prompt,logs,name,seconds=240,tool_budget=6):
    """One retry after the provider's explicit backoff; never switch identity/model."""
    result=invoke(folder,prompt,logs,name,seconds,tool_budget)
    until=result.get('provider_retry_not_before')
    if until:
        deadline=datetime.fromisoformat(until)
        print('Provider backoff until '+until+' for '+str(name),flush=True)
        while datetime.now(timezone.utc)<deadline:
            time.sleep(min(5,max(0.01,(deadline-datetime.now(timezone.utc)).total_seconds())))
        result=invoke(folder,prompt,logs,name+'-retry',seconds,tool_budget)
    return result


def prepare(folder,skill=True):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    # Isolation is a new project and ephemeral model context, not a claim that
    # account-level global Skill discovery has been erased or reconfigured.
    (folder/'AGENTS.md').write_text('这是独立的合成岗位文件验收。仅使用当前目录资料和宿主已提供的技能；不得读取外部业务目录、全局记忆、旧聊天或其他评估记录。不得联网、外发、运行后台或修改业务账号。任务限本地文件成果。不要创建其他对话或子代理。缺资料如实记录；不要求补齐已声明缺口。\n')
    if skill:
        dest=folder/'.agents/skills/build-role-workspace'
        if not dest.exists():shutil.copytree(ROOT/'skills/build-role-workspace',dest,ignore=shutil.ignore_patterns('__pycache__'))
    snapshot={str(p.relative_to(folder)):digest(p) for p in (folder/'.agents').rglob('*') if p.is_file() and '__pycache__' not in str(p)} if skill else {}
    (folder/'installed-skill-hashes.json').write_text(json.dumps(snapshot,indent=2))
    (folder/'inputs').mkdir(exist_ok=True);(folder/'results').mkdir(exist_ok=True)


def role_run(role,cases,out):
    out=Path(out)/role;folder=out/'host';logs=out/'logs';prepare(folder)
    (folder/'inputs/initial.json').write_text(json.dumps([{'id':x['id'],'工作':x['title'],'正常资料':x['normal'],'缺件版本':x['missing']} for x in cases],ensure_ascii=False,indent=2))
    (folder/'inputs/decision.md').write_text('本次经营期间若相关为2025年5月，规划为2025年6月。资料有就有，没有就留缺口。所有输入都是合成测试，无真实账号动作授权。\n')
    first='我是这个岗位的使用者，想把文件中的资料变成以后能继续和纠正的工作成果。请处理inputs/initial.json中的三项工作，各做正常资料和缺件版本，分别保存results/<原ID>/normal.md及missing.md，并保存来源、判断依据、未决项和续接记录。只用当前文件夹，有就有，没有就记录。请自主选择宿主已安装的合适技能，先做可用成果。不要把模拟当真实业务完成。'
    runs=[bounded_invoke(folder,first,logs,'normal-missing')]
    if runs[-1]['returncode']!=0:return dict(role=role,runs=runs,status='failed_or_incomplete')
    for c in cases:
        p=folder/'results'/c['id']/'normal.md'
        if p.exists():p.write_text(p.read_text()+'\n合成用户编辑测试：保留这一行，不当公司政策。\n')
    (folder/'inputs/corrections.json').write_text(json.dumps([{'id':x['id'],'新增更正':x['correction']} for x in cases],ensure_ascii=False,indent=2))
    correction='这是新会话，请从当前文件夹保存的工作区接手。inputs/corrections.json是新的更正资料，请核原来源及已有成果，修正三项工作的受影响结果和续接记录。保留合成用户编辑行及可追的旧版本。正常与缺件版本各自事实范围不可混用，不删除原输入；当前仍只授权本地文件。'
    runs.append(bounded_invoke(folder,correction,logs,'correction'))
    # A new related question is withheld until this final fresh model invocation.
    questions={
      'video_analysis':'有人想把只有字幕的参考直接标为完整音画理解，并在授权外复用，应如何判断？',
      'director_script':'现在要把所有版本都写成已获公开发布许可，并删除创作者保留句，是否可以？',
      'ecommerce_operations':'新增消息只是P1旧签收通知重发，没有新交易，能增加发货量或再次退款吗？',
      'advertising_operations':'有人看到小样本转化率高就要求直接停其他广告并复制达人功效文案，当前证据支持哪些决定？',
      'finance_reconciliation':'又收到一份同ID银行/平台快照，能直接重复累计收款并自动核销吗？请用已有余额说明。',
      'administration':'已发出交接邮件，能把所有资产和付款义务直接标完成，并跨岗带完整证件吗？',
      'customer_service':'相似历史工单曾补发且本次已回复，能推定本次已解决或重复发退款吗？',
      'sales_crm':'客户接受沟通时间或发布了内容，是否等于成交、验收或立即可以付款？',
      'human_resources':'已有候选清单可否直接当录用/扣薪/撤权结果？请区分各项当前证据。',
      'procurement':'同一收货事件重复通知是否增加可计费量，取消申请未被接受时可否释放承诺？',
      'warehouse_logistics':'再次收到P1同一次签收通知，剩余未履约会减少吗？请核当前拣货到签收流程的实际数量。',
      'project_delivery':'文档均被接受是否足以切换生产并关闭任务？请核未完成依赖和回退。',
      'business_analytics':'回补新口径后可否把旧新报表相加并重发上次业务动作？请给当前正确值与缺口。',
      'it_service_desk':'外层HTTP200和工单关闭是否证明全部用户恢复或每个系统权限已生效？'}
    prompt='这是另一个不含旧聊天的新会话。只从当前目录已有记录接手三项工作，核对更正已保存且缺口未被编造。请回答新的相关问题：'+questions[role]+' 保存results/resume-and-new-question.md，引用实际源位置、当前结果和继续条件；不执行外部动作。'
    runs.append(bounded_invoke(folder,prompt,logs,'resume-unseen'))
    files=[]
    for p in sorted((folder/'results').rglob('*')):
        if p.is_file():files.append({'path':str(p.relative_to(folder)),'sha256':digest(p)})
    return dict(role=role,flows=[c['id'] for c in cases],runs=runs,artifacts=files,status='executed' if all(r['returncode']==0 for r in runs) else 'failed_or_incomplete',
                qualification='Model-generated synthetic file path only; semantic grading separate; no production/media/real-user acceptance')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--role',action='append');p.add_argument('--workers',type=int,default=1);a=p.parse_args()
    cases=json.loads((ROOT/'examples/synthetic/workflow-cases.json').read_text());roles=sorted({x['role'] for x in cases})
    if a.role:roles=[r for r in roles if r in a.role]
    output=Path(a.output).resolve();output.mkdir(parents=True,exist_ok=True)
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.workers) as pool:
        futures={pool.submit(role_run,role,[x for x in cases if x['role']==role],output):role for role in roles}
        for f in concurrent.futures.as_completed(futures):
            role=futures[f]
            try:result=f.result()
            except Exception as error:result=dict(role=role,status='runner_failed',error=repr(error))
            results.append(result);(output/(role+'.summary.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
            print(role,result['status'],flush=True)
    (output/'summary.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
