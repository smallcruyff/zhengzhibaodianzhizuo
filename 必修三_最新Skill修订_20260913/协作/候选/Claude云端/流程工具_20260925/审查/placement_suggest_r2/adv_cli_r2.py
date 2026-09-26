#!/usr/bin/env python3
"""审查 r2 对抗用例（CLI 子进程）。产物只落系统临时目录 SCR 与 C/构建/placement_suggest/review_r2_*（用后删除）。
逐条打印 exit、是否有 Traceback、是否落盘、stderr 摘要；结果写 adv_cli_r2.json（本目录）。"""
import sys, json, subprocess, shutil, time
sys.dont_write_bytecode = True
from pathlib import Path
C = Path(__file__).resolve().parents[2]
TOOL = C / 'placement_suggest.py'
R = Path('/home/user/zhengzhibaodianzhizuo')
BOOK = R / '必修三_最新Skill修订_20260913' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
PROF = C / 'profiles_cloud' / 'bixiu3.json'
FROZEN = C / 'profiles_cloud' / 'bixiu2_frozen_test.json'
PHIL = R / '其他书工作头' / '哲学' / '哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx'
SCR = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_placement_suggest_r2/adv')
if SCR.exists():
    shutil.rmtree(SCR)
SCR.mkdir(parents=True)
BUILD = C / '构建' / 'placement_suggest'
base = ['--docx', str(BOOK), '--profile', str(PROF)]
K = ['--key', 'BJ-2020-BJ-GAOKAO-Q1']
rows = []
def case(cid, desc, args, expect, check_paths=(), cwd=None):
    t0 = time.time()
    p = subprocess.run([sys.executable, str(TOOL)] + args, capture_output=True, text=True, timeout=300, cwd=cwd)
    wrote = [str(x) for x in check_paths if Path(x).exists()]
    tb = 'Traceback' in p.stderr
    ok = (p.returncode in expect) and not tb and not wrote
    row = {'id': cid, 'desc': desc, 'exit': p.returncode, 'expect': list(expect), 'traceback': tb,
           'left_files': wrote, 'ok': ok, 'stderr': p.stderr.strip()[-260:], 'stdout_head': p.stdout[:160],
           'seconds': round(time.time() - t0, 2)}
    rows.append(row)
    print(('OK  ' if ok else 'BAD '), cid, desc, '| exit', p.returncode, '| tb', tb, '| left', wrote, '|', row['stderr'][-160:].replace('\n', ' '))
    for x in check_paths:
        if Path(x).exists():
            Path(x).unlink()
# 参数文件
bad_json = SCR / 'bad.json'; bad_json.write_text('{not json', encoding='utf-8')
bad_type = SCR / 'bad_type.json'; bad_type.write_text(json.dumps({'agg_mix': 'x'}), encoding='utf-8')
bad_ngram = SCR / 'bad_ngram.json'; bad_ngram.write_text(json.dumps({'ngram_sizes': []}), encoding='utf-8')
case('A01', '--params 非法 JSON → 2，中文、非“内部错误”英文', base + K + ['--params', str(bad_json)], {2})
case('A02', '--params 文件不存在 → 2', base + K + ['--params', str(SCR / 'nope.json')], {2})
case('A03', '--params agg_mix 为字符串 → 2', base + K + ['--params', str(bad_type)], {2})
case('A04', '--params ngram_sizes=[] → 应报错或 flag（全零信号）', base + K + ['--params', str(bad_ngram)], {1, 2})
# 冻结册
fz_out = BUILD / 'review_r2_frozen.md'
case('A05', '冻结配置 + --format md --out 合法路径 → 3，且不落盘', ['--docx', str(BOOK), '--profile', str(FROZEN)] + K + ['--format', 'md', '--out', str(fz_out)], {3}, [fz_out])
case('A06', '冻结配置只读（不写）→ 0/1 可跑', ['--docx', str(BOOK), '--profile', str(FROZEN)] + K, {0, 1})
# 守卫
case('A07', '--report 落 Skill 目录 → 3', base + K + ['--report', str(R / '.claude/skills/beijing-gaokao-politics/scripts/review_r2.json')], {3}, [R / '.claude/skills/beijing-gaokao-politics/scripts/review_r2.json'])
case('A08', '--report 落题库目录 → 3', base + K + ['--report', str(R / 'DeepSeek_政治题库资料库_20260918/review_r2.json')], {3}, [R / 'DeepSeek_政治题库资料库_20260918/review_r2.json'])
lnk = SCR / 'lnk'; lnk.symlink_to(R / '必修三_最新Skill修订_20260913')
case('A09', '--report 经临时目录符号链接绕进书稿工作区 → 3', base + K + ['--report', str(lnk / 'review_r2.json')], {3}, [R / '必修三_最新Skill修订_20260913/review_r2.json'])
case('A10', '--report 父目录不存在 → 3', base + K + ['--report', str(SCR / 'no_dir' / 'x.json')], {3})
case('A11', '--report 后缀不是 .json → 3', base + K + ['--report', str(SCR / 'x.txt')], {3}, [SCR / 'x.txt'])
exist = SCR / 'exists.json'; exist.write_text('{}', encoding='utf-8')
p = subprocess.run([sys.executable, str(TOOL)] + base + K + ['--report', str(exist)], capture_output=True, text=True)
rows.append({'id': 'A12', 'desc': '--report 目标已存在 → 3 且原文件不被覆盖', 'exit': p.returncode,
             'ok': p.returncode == 3 and exist.read_text(encoding='utf-8') == '{}', 'stderr': p.stderr.strip()[-200:]})
print('OK  ' if rows[-1]['ok'] else 'BAD ', 'A12', rows[-1]['desc'], '| exit', p.returncode)
# 输入
case('A13', '--docx 是目录 → 2', ['--docx', str(SCR), '--profile', str(PROF)] + K, {2})
case('A14', '--docx 是 PDF → 2', ['--docx', str(BOOK.with_suffix('.pdf')), '--profile', str(PROF)] + K, {2})
prof_nop = SCR / 'prof_no_parts.json'
d = json.loads(PROF.read_text(encoding='utf-8')); d.pop('parts', None); prof_nop.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
case('A15', '配置缺 parts → 2，中文', ['--docx', str(BOOK), '--profile', str(prof_nop)] + K, {2})
prof_nost = SCR / 'prof_no_styles.json'
d = json.loads(PROF.read_text(encoding='utf-8')); d.pop('styles', None); prof_nost.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
case('A16', '配置缺 styles → 2（或 0 题块→2）', ['--docx', str(BOOK), '--profile', str(prof_nost)] + K, {2})
case('A17', '--profile 是垃圾文件 → 2', ['--docx', str(BOOK), '--profile', str(bad_json)] + K, {2})
empty_keys = SCR / 'empty_keys.txt'; empty_keys.write_text('# only comment\n\n', encoding='utf-8')
case('A18', '--keys-file 只有注释/空行 → 2', base + ['--keys-file', str(empty_keys)], {2})
mixed = SCR / 'mixed_keys.txt'; mixed.write_text('BJ-2020-BJ-GAOKAO-Q1\nBJ-2099-NOSUCH-YIMO-Q1\n', encoding='utf-8')
rep_mixed = BUILD / 'review_r2_mixed.json'
case('A19', '--keys-file 第2行坏题键 → 整批 2，--report 不落盘', base + ['--keys-file', str(mixed), '--report', str(rep_mixed)], {2}, [rep_mixed])
case('A20', '--md 指向卷 README（非逐题 MD）→ 2', base + ['--md', str(R / 'DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/README.md')], {2})
empty_txt = SCR / 'empty.txt'; empty_txt.write_text('', encoding='utf-8')
case('A21', '--text 空文件 → 2（或 flag 1）', base + ['--text', str(empty_txt)], {1, 2})
case('A22', '--key 两层小问 Q21(1)(2) → 2', base + ['--key', 'BJ-2024-DC-ERMO-Q21(1)(2)'], {2})
case('A23', '--key 带 NUL/空格 → 2', base + ['--key', 'BJ 2024'], {2})
case('A24', '--bank 不存在 → 2', base + K + ['--bank', str(SCR / 'nobank')], {2})
case('A25', '题库“采用题面小节: 无”的题键 → 2', base + ['--key', 'BJ-2025-CY-YIMO-Q8'], {2})
case('A26', '2026石景山期末（题面节名“原题转录”）→ 2（工具认不出题面）', base + ['--key', 'BJ-2026-SJS-QIMO-Q18'], {2})
case('A27', '--md 已在本书的题（BJ-2024-DC-ERMO-Q21）→ 应 1（已落位 flag）', base + ['--md', str(R / 'DeepSeek_政治题库资料库_20260918/questions/BJ-2024-DC-ERMO/BJ-2024-DC-ERMO-Q21.md')], {1})
case('A28', '题库只有 E3（参考答案（E3；不得视为正式评分细则））的主观题 BJ-2023-FT-ERMO-Q17 → 应 1（无细则不收）', base + ['--key', 'BJ-2023-FT-ERMO-Q17'], {1})
case('A29', 'E1_candidate_pending 的主观题 BJ-2025-BJ-GAOKAO-Q18 → 应 1（无细则不收）', base + ['--key', 'BJ-2025-BJ-GAOKAO-Q18'], {1})
case('A30', '正文写“没有为本题提供…正式评分槽…按E3保留”的 BJ-2023-DC-ERMO-Q18 → 应 1', base + ['--key', 'BJ-2023-DC-ERMO-Q18'], {1})
case('A31', '--debug 下异常才出 traceback（非 debug 无）：--docx 不是 zip', ['--docx', str(bad_json), '--profile', str(PROF)] + K, {2})
case('A32', '哲学草案配置 + 哲学书 + 题库题键 --format md', ['--docx', str(PHIL), '--profile', str(C / 'profiles_cloud/philosophy.draft.json'), '--key', 'BJ-2024-HD-YIMO-Q17', '--format', 'md'], {0, 1})
json.dump(rows, open(Path(__file__).with_suffix('.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('BAD =', sum(1 for r in rows if not r['ok']), '/', len(rows))
