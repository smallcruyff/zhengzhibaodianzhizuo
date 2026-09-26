"""原子性：--out 已写成功、--report 写入时失败（模拟磁盘错误）→ 退出码与残留文件。"""
import sys, os, io, contextlib
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
S = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_placement_suggest_r4/atomic')
if S.exists():
    for p in S.iterdir(): p.unlink()
S.mkdir(parents=True, exist_ok=True)
B = '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
orig = ps._atomic_write_text
calls = []
def flaky(path, text):
    calls.append(str(path))
    if str(path).endswith('.json'):
        raise OSError(28, '模拟：No space left on device')
    return orig(path, text)
ps._atomic_write_text = flaky
buf_o, buf_e = io.StringIO(), io.StringIO()
with contextlib.redirect_stdout(buf_o), contextlib.redirect_stderr(buf_e):
    code = ps.main(['--docx', B, '--profile', str(C/'profiles_cloud'/'bixiu3.json'), '--key', 'BJ-2020-BJ-GAOKAO-Q1',
                    '--format', 'md', '--out', str(S/'a.md'), '--report', str(S/'a.json')])
left = sorted(p.name for p in S.iterdir())
print('exit', code, 'calls', [Path(c).name for c in calls], 'left_files', left)
print('stderr:', buf_e.getvalue().strip()[:300])
