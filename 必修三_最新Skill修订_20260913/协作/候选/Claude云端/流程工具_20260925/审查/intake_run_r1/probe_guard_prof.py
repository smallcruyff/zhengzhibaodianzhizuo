"""对抗探针：intake_run.write_guarded 调 guard_write 时 prof=None，_house.json 的 output_guard.protected_roots
（~/GaokaoPolitics、~/.codex/skills、~/.claude/skills、~/Desktop）因此不生效；_extra_guard_check 只补仓库根。
只调守卫函数、不真正写文件。"""
import sys
sys.dont_write_bytecode = True
from pathlib import Path
R='/home/user/zhengzhibaodianzhizuo'
C=R+'/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0, C)
import intake_run as ir
dl = ir.dl
prof = ir.load_profile(C+'/profiles_cloud/bixiu3.json')
print('house protected_roots via profile:', (prof.get('output_guard') or {}).get('protected_roots'))
for target in ['/root/.claude/skills/intake_probe_never_written.json', '/root/.claude/skills/synced/intake_probe_never_written.json']:
    t = Path(target)
    try:
        o = dl.guard_write(t, None, kind='.json'); ir._extra_guard_check(o, {ir.REPO_ROOT})
        r1 = 'intake_run 同款守卫（prof=None）：放行'
    except dl.GuardError as e:
        r1 = 'intake_run 同款守卫：拒绝 ' + str(e)[:80]
    try:
        dl.guard_write(t, prof, kind='.json'); r2 = '带 profile 守卫：放行'
    except dl.GuardError as e:
        r2 = '带 profile 守卫（同伴工具做法）：拒绝 ' + str(e)[:80]
    print(target, '\n   ', r1, '\n   ', r2, '\n    exists_after=', t.exists())
# init 的 workdir 守卫：仓库外一律放行（只查 REPO_ROOT）
for wd in ['/root/.claude/skills/x_workdir', '/home/user/other_project/x']:
    try:
        print('init workdir', wd, '->', ir._check_workdir_allowed(wd), '（放行，随后会 mkdir -p 9 个子目录）')
    except dl.GuardError as e:
        print('init workdir', wd, '-> 拒绝', e)
