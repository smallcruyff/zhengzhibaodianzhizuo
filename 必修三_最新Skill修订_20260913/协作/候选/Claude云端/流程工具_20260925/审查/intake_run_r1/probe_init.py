import json, os, shutil, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode = True
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
TOOL = C / 'intake_run.py'
S = Path(sys.argv[1]); W = S / 'adv_init'
if W.exists(): shutil.rmtree(W)
W.mkdir(parents=True)
def run(args):
    p = subprocess.run([sys.executable, '-B', str(TOOL)] + [str(a) for a in args], capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout, p.stderr
for d in ('i16', 'i17', 'i19', 'i20'): (W / d).mkdir()
rc, o, e = run(['init', '--out', W / 'i16/m.json', '--batch', 'x', '--book', 'no_such_book', '--exam-id', '乱写'])
print('A16 init 未知书名/乱写卷号 rc=', rc, 'written=', (W / 'i16/m.json').is_file(), e.strip()[-200:])
if (W / 'i16/m.json').is_file(): print('   manifest:', (W / 'i16/m.json').read_text()[:300])
evil = Path('/home/user/intake_review_probe_outside_repo')
rc, o, e = run(['init', '--out', W / 'i17/m.json', '--batch', 'x', '--workdir', evil])
print('A17 init --workdir 仓库外非临时目录 rc=', rc, 'created=', evil.exists(), e.strip()[-200:])
if evil.exists(): shutil.rmtree(evil)
rc, o, e = run(['init', '--out', W / 'i19/m.json', '--batch', 'b19', '--book', 'bixiu3', '--exam-id', 'BJ-2026-CY-QIZHONG'])
wd = W / 'i19' / '入书_b19'
print('A19 init 目录骨架 rc=', rc, sorted(str(p.relative_to(wd)) for p in wd.rglob('*') if p.is_dir()))
# A20 init 相对 --workdir：清单里存相对串，status 在别的 cwd 下解析到别处
rc, o, e = run(['init', '--out', W / 'i20/m.json', '--batch', 'b20', '--workdir', 'rel_wd'])
print('A20 init 相对 workdir rc=', rc, 'manifest.workdir=', json.loads((W / 'i20/m.json').read_text())['workdir'] if (W/'i20/m.json').is_file() else None, 'created_under_cwd=', (Path.cwd() / 'rel_wd').exists())
if (Path.cwd() / 'rel_wd').exists(): shutil.rmtree(Path.cwd() / 'rel_wd')
