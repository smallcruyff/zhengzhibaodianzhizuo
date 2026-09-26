"""对抗探针：按规格把工具装进 Skill 母版 ~/.codex/skills/beijing-gaokao-politics/scripts/（本地真实安装位置，
见 00_规格.md 一、1 与 00_协作入口.md），在临时目录模拟：fakehome/.codex/skills/beijing-gaokao-politics/scripts/
= SK 全部脚本副本 + intake_run.py/exam_register.py 等。看 REPO_ROOT、默认题库/归属表路径与 status 结论。"""
import json, shutil, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
SK = R / '.claude/skills/beijing-gaokao-politics/scripts'
S = Path(sys.argv[1]); home = S / 'fakehome'
if home.exists(): shutil.rmtree(home)
dst = home / '.codex/skills/beijing-gaokao-politics/scripts'
shutil.copytree(SK, dst, ignore=shutil.ignore_patterns('__pycache__'))
for f in ('intake_run.py', 'exam_register.py', 'placement_suggest.py', 'block_insert.py'):
    shutil.copy2(C / f, dst / f)
code = ('import sys; sys.dont_write_bytecode=True; sys.path.insert(0, %r); import intake_run as ir; '
        'print("SK_DIR", ir.SK_DIR); print("REPO_ROOT", ir.REPO_ROOT); print("DEFAULT_BANK", ir.DEFAULT_BANK, ir.DEFAULT_BANK.is_dir()); '
        'print("DEFAULT_ATTRIBUTION_CSV exists", ir.DEFAULT_ATTRIBUTION_CSV.is_file())') % str(dst)
p = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True, text=True)
print(p.stdout, p.stderr[-500:])
wd = S / 'fake_wd'; wd.mkdir(exist_ok=True)
m = S / 'fake_manifest.json'
m.write_text(json.dumps({'schema': 'baodian_intake_v1', 'batch': 'fake', 'exams': [{'exam_id': 'BJ-2026-HD-QIZHONG'}],
                          'books': ['bixiu3'], 'profiles': {'bixiu3': str(C / 'profiles_cloud/bixiu3.json')}, 'workdir': str(wd)}), encoding='utf-8')
rep = S / 'fake_report.json'
if rep.exists(): rep.unlink()
p = subprocess.run([sys.executable, '-B', str(dst / 'intake_run.py'), 'status', '--manifest', str(m), '--report', str(rep), '--quiet'],
                   capture_output=True, text=True, timeout=300)
print('rc', p.returncode, p.stderr[-300:])
if rep.is_file():
    d = json.loads(rep.read_text())
    for s in d['rows'][0]['steps']:
        print(s['step'], s['status'], s['reason'][:110])
shutil.rmtree(home)
