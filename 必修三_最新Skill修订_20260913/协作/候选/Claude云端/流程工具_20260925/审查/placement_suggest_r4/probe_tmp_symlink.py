"""_atomic_write_text 的临时文件名可预测（.<name>.tmp<pid>）且不用 O_EXCL：若该路径预先是指向别处的
符号链接，write_text 会顺着链接写穿目标文件。只在系统临时目录里用自建的 victim 文件演示，不碰真实文件。"""
import sys, os
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
S = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_placement_suggest_r4/symlink_demo')
S.mkdir(parents=True, exist_ok=True)
for p in S.iterdir(): p.unlink()
victim = S / 'victim_protected.txt'
victim.write_text('ORIGINAL', encoding='utf-8')
target = S / 'report.json'
tmp = target.with_name(f'.{target.name}.tmp{os.getpid()}')
os.symlink(str(victim), str(tmp))
ps._atomic_write_text(target, '{"x": 1}')
print('victim now:', victim.read_text(encoding='utf-8'), '| report is symlink:', target.is_symlink())
