import sys, json, subprocess, time
sys.dont_write_bytecode = True
from pathlib import Path
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
S = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_exam_register_r1')
TOOL = C / 'exam_register.py'
PROF = C / 'profiles_cloud/bixiu3.json'
FROZ = C / 'profiles_cloud/bixiu2_frozen_test.json'
out = {}
def run(name, args):
    t0 = time.time()
    p = subprocess.run([sys.executable, str(TOOL)] + args, capture_output=True, text=True, timeout=300)
    dt = time.time() - t0
    txt = p.stdout
    d = None
    try:
        d = json.loads(txt[txt.index('{'):]) if '{' in txt else None
    except Exception:
        d = None
    short = None
    if d:
        short = {k: d.get(k) for k in ('cohort_year', 'cohort_status')}
        short['suggested'] = (d.get('suggestion') or {}).get('suggested_id')
        short['dups'] = [(a['exam_id'], a['kind'], a['matched'], a['total']) for a in d.get('duplicates', [])]
        short['issues'] = d.get('issues')
    err = '\n'.join(l for l in p.stderr.splitlines() if 'fitz' not in l)
    print(f'--- {name} exit={p.returncode} t={dt:.1f}s traceback={"Traceback" in p.stderr}')
    print('   ', json.dumps(short, ensure_ascii=False)[:900] if short else txt[:300])
    if err.strip(): print('    stderr:', err.strip()[:300])
    out[name] = {'exit': p.returncode, 'short': short, 'stderr': err[:500], 'seconds': round(dt, 1)}
syn = S / 'synth'
F = ['--profile', str(PROF)]
cases = sys.argv[1:] or ['all']
if 'all' in cases or 'synth' in cases:
    run('S1 无任何日期的新卷（有文字层）', ['check', '--files', str(syn/'s1_nodate.docx'), '--region', '海淀', '--stage', '期中'] + F)
    run('S2 高三卷首+题干含“高二”', ['check', '--files', str(syn/'s2_g3_header_g2_body.docx'), '--region', '海淀', '--stage', '期中'] + F)
    run('S3 真高二卷', ['check', '--files', str(syn/'s3_grade2.docx'), '--region', '海淀', '--stage', '期中'] + F)
    run('S4 网站标题(考试年)+题干上年日期', ['check', '--files', str(syn/'s4_webtitle_bodydate.docx'), '--region', '朝阳', '--stage', '期中'] + F)
    run('S5 全角数字卷首日期', ['check', '--files', str(syn/'s5_fullwidth.docx'), '--region', '朝阳', '--stage', '期中'] + F)
if 'all' in cases or 'modes' in cases:
    yimo = R / '00_共同资料/原材料'
    import csv
    rows = list(csv.DictReader(open(R/'DeepSeek_政治题库资料库_20260918/indexes/exam_files.csv', encoding='utf-8-sig')))
    xc = [r for r in rows if r['exam_id']=='BJ-2025-XC-YIMO' and r['role']=='原卷' and r['format'] in ('pdf','docx')][0]
    run('S7 一模原卷 --files 不给 --stage', ['check', '--files', str(yimo/xc['rel_path']), '--region', '西城'] + F)
    run('S7b 一模原卷 --files --stage 一模', ['check', '--files', str(yimo/xc['rel_path']), '--region', '西城', '--stage', '一模'] + F)
    qd = R/'DeepSeek_政治题库资料库_20260918/questions'
    run('S6a --exam-dir 题库自身目录（默认 claim=目录名）', ['check', '--exam-dir', str(qd/'BJ-2026-HD-QIZHONG')] + F)
    run('S6b --exam-dir 题库自身目录 + --claimed-id 另一号', ['check', '--exam-dir', str(qd/'BJ-2026-HD-QIZHONG'), '--claimed-id', 'BJ-2027-HD-QIZHONG'] + F)
    run('S6c --exam-dir BJ-2024-CY-QIZHONG（已知错号）', ['check', '--exam-dir', str(qd/'BJ-2024-CY-QIZHONG')] + F)
    run('S6d --exam-dir BJ-2026-FT-QIMO（全 OCR 题面）', ['check', '--exam-dir', str(qd/'BJ-2026-FT-QIMO')] + F)
if 'all' in cases or 'neg' in cases:
    run('N1 --profile 不存在', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', '/no/such/profile.json'])
    run('N2 冻结册 无 --report（应可只读运行）', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', str(FROZ)])
    run('N3 两种输入同时给', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--files', str(syn/'s1_nodate.docx')] + F)
    run('N4 合法格式但题库无此卷', ['check', '--exam-id', 'BJ-2019-HD-QIZHONG'] + F)
    run('N5 未知区县码', ['check', '--exam-id', 'BJ-2025-XX-YIMO'] + F)
    run('N6 --report 后缀非 .json', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(S/'x.txt')] + F)
    (S/'exists.json').write_text('{}')
    run('N7 --report 已存在不覆盖', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(S/'exists.json')] + F)
    run('N8 --report 目录不存在', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(S/'nodir/x.json')] + F)
    run('N9 --files 给目录', ['check', '--files', str(syn), '--region', '海淀', '--stage', '期中'] + F)
    run('N10 --files 给 .txt', ['check', '--files', str(S/'exists.json'), '--region', '海淀', '--stage', '期中'] + F)
    run('N11 --stage 非法', ['check', '--files', str(syn/'s1_nodate.docx'), '--region', '海淀', '--stage', '三模'] + F)
    run('N12 --bank 不存在', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--bank', '/no/bank'] + F)
    run('N13 ASM 汇编卷号', ['check', '--exam-id', 'ASM-2024届各区一模试题分类汇编必修1'] + F)
    (S/'corrupt.pdf').write_bytes(b'%PDF-1.4 garbage not a pdf')
    run('N14 损坏 PDF', ['check', '--files', str(S/'corrupt.pdf'), '--region', '海淀', '--stage', '期中'] + F)
json.dump(out, open(S/f'probe_cli_{"_".join(cases)}.json', 'w'), ensure_ascii=False, indent=1)
