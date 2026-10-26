"""Opt-in three-round model comparison on synthetic sources; actual account usage, no business executor."""
from pathlib import Path
import sys, json, csv, hashlib
root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'tools'))
from run_model_evaluations import prepare, bounded_invoke as invoke
rows = [{'event_id': 'P1', 'occurred': '2025-05-01', 'currency': 'CNY', 'kind': 'payment', 'amount': '100'}, {'event_id': 'P2', 'occurred': '2025-05-02', 'currency': 'CNY', 'kind': 'payment', 'amount': '50'}, {'event_id': 'P1', 'occurred': '2025-05-01', 'currency': 'CNY', 'kind': 'payment', 'amount': '100'}, {'event_id': 'P3', 'occurred': '2025-05-03', 'currency': 'USD', 'kind': 'payment', 'amount': '5'}, {'event_id': 'R1', 'occurred': '2025-06-01', 'currency': 'CNY', 'kind': 'refund', 'amount': '20'}]

def write(folder, data):
    with (folder / 'inputs/events.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(data[0]))
        w.writeheader()
        w.writerows(data)

def grade(folder, round):
    p = folder / 'results/totals.json'
    try:
        data = json.loads(p.read_text())
        actual = {r['currency']: (str(r['payments']), str(r['refunds']), str(r['net'])) for r in data['rows']}
        from decimal import Decimal
        expected = {'CNY': ('170', '10', '160'), 'USD': ('5', '0', '5')} if round == 3 else {'CNY': ('150', '0', '150'), 'USD': ('5', '0', '5')}
        ok = set(actual) == set(expected) and all((tuple(map(Decimal, actual[k])) == tuple(map(Decimal, v)) for k, v in expected.items()))
        return {'numeric_pass': ok, 'actual': actual, 'expected': expected}
    except Exception as e:
        return {'numeric_pass': False, 'error': repr(e), 'expected_missing_output': not p.exists()}

def run(output):
    out = Path(output).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('Use a fresh output directory; preserve prior attempts')
    results = []
    for arm in ['baseline', 'candidate']:
        folder = out / arm / 'host'
        prepare(folder, skill=arm == 'candidate')
        write(folder, rows)
        (folder / 'inputs/definitions.md').write_text('本公司本次报告为2025年5月按事件发生月核支付与退款，币种分别列出。event_id相同且内容相同是重复快照，按唯一事件计。退款按其发生月。金额仅原表单位，不推利润。资料有就有，没有就留缺口。只做文件，不能发送或修改账号。\n')
        initial = '请把inputs里的文件做成五月支付退款报告，保存results/report.md和可复用续接记录。另存results/totals.json，格式为{"rows":[{"currency":"币种","payments":"支付合计","refunds":"退款合计","net":"支付减退款"}]}，数值用字符串。请先查资料，按已给定义，重复事件不重复算，币种分开。所有资料为合成，不执行业务动作。'
        prompts = [initial, '这是新会话，请从保存的资料和定义接手，做上次那份五月报告，核源后继续，保留原结果和备注；结果仍保存同一约定位置。', '这是新会话，inputs/events.csv已更新。请按原已确认月份与口径重做受影响报告，保留旧版与合成用户备注，不重复业务动作；结果仍保存同一约定位置。']
        for i, prompt in enumerate(prompts, 1):
            if i == 2:
                p = folder / 'results/report.md'
                if p.exists():
                    p.write_text(p.read_text() + '\n合成用户备注：保留这一句，不是政策。\n')
            if i == 3:
                changed = [dict(x, amount='70') if x['event_id'] == 'P2' else x for x in rows]
                changed.append({'event_id': 'R2', 'occurred': '2025-05-20', 'currency': 'CNY', 'kind': 'refund', 'amount': '10'})
                write(folder, changed)
            input_hash = hashlib.sha256((folder / 'inputs/events.csv').read_bytes()).hexdigest()
            r = invoke(folder, prompt, out / arm / 'logs', f'round-{i}', 180, tool_budget=8)
            g = grade(folder, i)
            g['execution_accepted'] = r['returncode'] == 0 and (not r.get('tool_budget_exceeded', False))
            g['accepted_numeric_result'] = g['numeric_pass'] and g['execution_accepted']
            report = folder / 'results/report.md'
            note = '合成用户备注：保留这一句' in report.read_text() if report.exists() else False
            snapshot = out / arm / f'round-{i}-outputs'
            snapshot.mkdir(parents=True, exist_ok=True)
            import shutil
            for file in (folder / 'results').iterdir():
                if file.is_file():
                    shutil.copy2(file, snapshot / file.name)
            result = {'arm': arm, 'round': i, 'source_sha256': input_hash, 'run': r, 'grade': g, 'synthetic_edit_preserved': note if i > 1 else 'not_applicable', 'human_preparation_verification_correction_maintenance_time': 'NOT_MEASURED', 'real_user_feedback': 'separate human-usability.json; not a timed study'}
            results.append(result)
            print(arm, i, 'numeric_pass', g['numeric_pass'], flush=True)
            (out / 'results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2))
    return results
if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    run(a.output)
