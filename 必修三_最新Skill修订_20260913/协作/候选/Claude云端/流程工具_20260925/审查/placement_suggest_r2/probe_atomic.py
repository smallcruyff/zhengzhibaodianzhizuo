#!/usr/bin/env python3
"""审查 r2：原子性（进程内）。让第二个落盘（--report）在 os.replace 时失败，核第一个（--out .md）被清理、无 .tmp 残留、退出 2。只读真实输入。"""
import sys, os, shutil
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
S = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_placement_suggest_r2/atomic')
if S.exists(): shutil.rmtree(S)
S.mkdir(parents=True)
BOOK = '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
real_replace = os.replace
calls = {'n': 0}
def flaky_replace(a, b):
    calls['n'] += 1
    if calls['n'] == 2:
        raise OSError('模拟：第二个文件改名失败')
    return real_replace(a, b)
os.replace = flaky_replace
code = ps.main(['--docx', BOOK, '--profile', str(C / 'profiles_cloud/bixiu3.json'), '--key', 'BJ-2020-BJ-GAOKAO-Q1',
                '--format', 'md', '--out', str(S / 'o.md'), '--report', str(S / 'r.json')])
os.replace = real_replace
left = sorted(p.name for p in S.iterdir())
print('exit', code, 'left files', left)
print('RESULT', 'OK' if code == 2 and not [x for x in left if not x.startswith('.r.json.tmp')] else 'BAD')
