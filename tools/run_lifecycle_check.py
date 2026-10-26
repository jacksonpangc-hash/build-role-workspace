"""Opt-in isolated Codex host lifecycle evaluation. Never changes personal Skill/config directories."""
import argparse,hashlib,json,shutil,sys
from pathlib import Path
from install_release import install
from run_model_evaluations import prepare,bounded_invoke

ROOT=Path(__file__).resolve().parents[1]

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(output,package,package_hash,old_package,old_hash):
    out=Path(output).resolve();out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):raise ValueError('Use an empty isolated output folder')
    parent=out/'parent';child=parent/'project';prepare(child,skill=False)
    other=parent/'.agents/skills/build-role-workspace'
    target=child/'.agents/skills/build-role-workspace'
    install(old_package,other,old_hash);install(old_package,target,old_hash)
    (target/'personal-note.md').write_text('SYNTHETIC_USER_CUSTOMIZATION: preserve on upgrade/rollback')
    other_before={str(p.relative_to(other)):sha(p) for p in other.rglob('*') if p.is_file()}
    policy=child/'workspace/human-policy.md';policy.parent.mkdir();policy.write_text('合成用户规则：订单应付不能叫已到账；不自动外发。\n')
    policy_hash=sha(policy)
    (child/'inputs/events.csv').write_text('id,period,currency,amount\nP1,2025-05,CNY,100\nP2,2025-05,CNY,50\n')
    (child/'inputs/context.md').write_text('本次期间2025年5月，资料有就有，没有就留缺口。仅做文件，保留工作区和个人规则。\n')
    collision_rejected=False
    try:install(package,target,package_hash)
    except ValueError:collision_rejected=True
    if not collision_rejected:raise AssertionError('Same-name directory overwritten')
    backup=out/'backups';backup.mkdir();old_copy=backup/'old-project-skill';target.rename(old_copy)
    install(package,target,package_hash)
    logs=out/'logs';results=[]
    request='请整理当前inputs文件夹，按已给期间做一份支付摘要，保存结果并留下下次能继续的记录；工作区在workspace。资料有就有，没有就记录，先交能用的报告。只处理本地文件，不要改别的岗位工具或外发。'
    results.append(bounded_invoke(child,request,logs,'new-package-natural',240,8))
    explicit='请用 $build-role-workspace 从workspace及已保存结果继续，核输入是否变化，回答五月已给支付记录合计是多少，并保存依据和仍不能判断的事项。保留个人规则，不要靠上次聊天。'
    results.append(bounded_invoke(child,explicit,logs,'new-package-explicit-fresh',240,8))
    new_copy=backup/'new-project-skill';target.rename(new_copy);old_copy.rename(target)
    assert (target/'personal-note.md').read_text()=='SYNTHETIC_USER_CUSTOMIZATION: preserve on upgrade/rollback'
    results.append(bounded_invoke(child,'这是新会话，项目助手已回退到保留旧版。请从原workspace和已有成果继续，核已给五月支付记录，保留原规则和人工定制；旧版不具备的新检查要明确说明，不外发或改账号。',logs,'rollback-fresh',240,8))
    # Remove only the owned project installation. An ancestor same-name copy
    # deliberately remains: uninstall must not pretend every installation vanished.
    uninstalled_backup=backup/'uninstalled-project-skill'
    target.rename(uninstalled_backup)
    results.append(bounded_invoke(child,'请只读检查当前项目的岗位助手安装位置和已有workspace：项目级build-role-workspace已卸载，确认工作成果/个人规则是否保留，并说明仍存在的同名副本。不要删除父目录工具、修改全局配置或重新安装。把检查结果存results/uninstall-check.md。',logs,'uninstall-fresh',240,8))
    assert not target.exists()
    assert (uninstalled_backup/'personal-note.md').read_text()=='SYNTHETIC_USER_CUSTOMIZATION: preserve on upgrade/rollback'
    assert policy.exists() and sha(policy)==policy_hash
    assert {str(p.relative_to(other)):sha(p) for p in other.rglob('*') if p.is_file()}==other_before
    assert (target.parent.parent.parent/'results').is_dir()
    result={'package_sha256':package_hash,'old_package_sha256':old_hash,'runs':results,
            'same_name_overwrite_refused':collision_rejected,'customization_preserved_in_old_backup':True,
            'workspace_policy_preserved':True,'other_same_name_skill_unchanged':True,'project_install_removed':True,
            'host':'actual local Codex CLI; new project dirs and ephemeral contexts; account-level global Skill catalog still present',
            'acceptance':'model content/path traces require semantic review; process completion alone is not natural invocation success'}
    (out/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',required=True);p.add_argument('--package',required=True);p.add_argument('--sha256',required=True)
    p.add_argument('--old-package',required=True);p.add_argument('--old-sha256',required=True);a=p.parse_args()
    run(a.output,a.package,a.sha256,a.old_package,a.old_sha256)
