"""逐类构造 intake_run 会给出的“下一条命令”（直接调用各 check_step* 判定函数喂状态），用 argparse_harness 只解析不执行。"""
import json, shlex, subprocess, sys, shutil
from pathlib import Path
sys.dont_write_bytecode = True
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0, str(C))
import intake_run as ir
S = Path(sys.argv[1]); W = S / 'cmds'
if W.exists(): shutil.rmtree(W)
W.mkdir(parents=True); ir._mkdirs(W)
P3 = str(C / 'profiles_cloud/bixiu3.json')
prof = ir.load_book_profile('bixiu3', P3)
docx, _ = ir.current_docx_for_book(prof)
cmds = []
e_files = {'files': [str(R / '00_共同资料/原材料/a.pdf'), str(R / '00_共同资料/原材料/b.docx')], 'claimed_id': 'BJ-2027-HD-QIZHONG'}
cmds.append(('1 source_intake(files)', ir.check_step1(e_files, ir.DEFAULT_BANK, W)['next_command']))
cmds.append(('1 source_intake(exam_id 未入库)', ir.check_step1({'exam_id': 'BJ-2027-HD-QIZHONG'}, ir.DEFAULT_BANK, W)['next_command']))
cmds.append(('2 exam_register(files)', ir.check_step2(e_files, P3, W)['next_command']))
cmds.append(('2 exam_register(exam_id)', ir.check_step2({'exam_id': 'BJ-2026-CY-QIZHONG'}, P3, W)['next_command']))
cmds.append(('3 bank_compile', ir.check_step3({'exam_id': 'BJ-2026-HD-QIZHONG'}, ir.DEFAULT_BANK)['next_command']))
rows = [{'unit_id': 'BJ-2026-CY-QIZHONG-Q9', '归属_B3': 'IN', 'type': '选择题'}, {'unit_id': 'BJ-2023-HD-QIZHONG-Q18#1', '归属_B3': 'IN', 'type': '主观题'}]
cmds.append(('5 placement_suggest', ir.check_step5('BJ-2026-CY-QIZHONG', 'bixiu3', 'B3', rows, 'DONE', W, P3, docx)['next_command']))
cmds.append(('6 qpack get', ir.check_step6('BJ-2026-CY-QIZHONG', 'bixiu3', 'B3', rows, 'DONE', W)['next_command']))
cmds.append(('7 check_drill_admission', ir.check_step7('BJ-2026-CY-QIZHONG', 'bixiu3', 'B3', rows, 'DONE', W)['next_command']))
cache = ir.BookIndexCache()
cmds.append(('8 block_insert check', ir.check_step8('BJ-2026-CY-QIZHONG', 'bixiu3', 'B3', rows, cache, prof, docx, None, {})['next_command']))
cmds.append(('9a layout check', ir.check_step9('bixiu3', prof, docx, None, W)['next_command']))
(W / '09_layout/bixiu3.json').write_text(json.dumps({'pending': 3, 'blocked_count': {'keepnext': 0}, 'toc_version_problems': []}))
cmds.append(('9b layout repair', ir.check_step9('bixiu3', prof, docx, None, W)['next_command']))
(W / '09_layout/bixiu3.json').write_text(json.dumps({'pending': 0, 'blocked_count': {'keepnext': 0}, 'toc_version_problems': []}))
cmds.append(('9c batch_health', ir.check_step9('bixiu3', prof, docx, None, W)['next_command']))
(W / '09_health/bixiu3.json').write_text('{}')
cmds.append(('9d publish_review', ir.check_step9('bixiu3', prof, docx, None, W)['next_command']))
(W / '09_publish/bixiu3.json').write_text('{}')
s9 = ir.check_step9('bixiu3', prof, docx, None, W)
cmds.append(('9e 全齐', s9['next_command']))
print('9e status =', s9['status'])
res = []
for name, cmd in cmds:
    first = cmd.split('；')[0].split(' 等（')[0].strip() if cmd else ''
    if not first.startswith('python3 '):
        print(f'[{name}] 非命令行：{cmd}'); res.append({'cmd': name, 'text': cmd, 'parsed': None}); continue
    parts = shlex.split(first)
    p = subprocess.run([sys.executable, '-B', str(S / 'argparse_harness.py')] + parts[1:], capture_output=True, text=True, timeout=120)
    ok = p.returncode == 0 and 'PARSED' in p.stdout
    ph = [t for t in parts if t.startswith('<') and t.endswith('>')]
    print(f'[{name}] parsed={ok} rc={p.returncode} placeholders={ph}\n    {first[:260]}\n    {(p.stdout + p.stderr).strip()[-220:]}')
    res.append({'cmd': name, 'text': first, 'parsed': ok, 'rc': p.returncode, 'placeholders': ph, 'tail': (p.stdout + p.stderr).strip()[-300:]})
json.dump(res, open(S / 'probe_cmds.json', 'w'), ensure_ascii=False, indent=1)
