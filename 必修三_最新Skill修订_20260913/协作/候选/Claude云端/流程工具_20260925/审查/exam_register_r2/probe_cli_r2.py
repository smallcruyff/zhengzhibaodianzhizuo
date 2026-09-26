"""r2 审查 CLI 探针：逐条跑被审工具（子进程、-B），记录退出码、stdout 关键字段、stderr 是否含 Traceback。
输出写到本会话临时区与 审查/exam_register_r2/probe_cli_r2_<组>.json。只读真实输入。"""
import json, subprocess, sys, time, os
from pathlib import Path
C = Path(__file__).resolve().parents[2]
TOOL = C / 'exam_register.py'
P = str(C / 'profiles_cloud' / 'bixiu3.json')
R = Path('/home/user/zhengzhibaodianzhizuo')
S = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_exam_register_r2')
SY = S / 'synth'
R1 = C / '审查' / 'exam_register_r1' / 'synth'
HDQZ = R / '00_共同资料/原材料/2025模拟题/2025各区期末/2025海淀期中'
def run(name, args, env=None):
    t0 = time.time()
    p = subprocess.run([sys.executable, '-B', str(TOOL)] + args, capture_output=True, text=True, timeout=400, env=env)
    try:
        d = json.loads(p.stdout)
    except Exception:
        d = None
    keep = None
    if isinstance(d, dict):
        keep = {k: d.get(k) for k in ('cohort_year', 'cohort_status', 'grade2', 'suggestion', 'chain_kind', 'rename_plan', 'redirects', 'duplicates', 'issues', 'fingerprint_coverage')}
    rec = {'case': name, 'args': args, 'exit': p.returncode, 'sec': round(time.time() - t0, 1),
           'traceback_in_stderr': 'Traceback' in p.stderr, 'stderr': p.stderr.strip()[:400], 'out': keep if keep is not None else p.stdout[:600]}
    print(json.dumps(rec, ensure_ascii=False)[:1800]); sys.stdout.flush()
    return rec
group = sys.argv[1]
recs = []
if group == 'logic':
    recs.append(run('L1 新高三卷(届别2025海淀期中,题面全新)→建议号被正确登记卷占用', ['check', '--files', str(SY/'r1_new_hd_2025_qizhong.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L2 真高二卷(2023—2024学年高二)→届别2025', ['check', '--files', str(SY/'r2_grade2_hd.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L3 有文字层无日期,文件名含2024.11', ['check', '--files', str(SY/'2024.11海淀高三期中试卷.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L4 试卷.pdf+细则.docx(规格用法)', ['check', '--files', str(HDQZ/'试卷/试卷.pdf'), str(HDQZ/'细则/细则.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L5 r1 s11 复用题在第4433字', ['check', '--files', str(R1/'s11_reuse_after_4000_chars.docx'), '--region', '海淀', '--stage', '期末', '--profile', P]))
    recs.append(run('L6 考生须知编号+22题整卷复印', ['check', '--files', str(SY/'r4_notice_numbered_copy_of_2026hd.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L7 真卷改掉大部分题面(4/22保留)', ['check', '--files', str(SY/'r5_mostly_rewritten_2026hd.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L8 半数复用11/22', ['check', '--files', str(SY/'r6_half_reuse.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L9 须知在前、日期在须知之后', ['check', '--files', str(SY/'r7_header_date_after_notice.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L10 r1 s1 无日期', ['check', '--files', str(R1/'s1_nodate.docx'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('L11 r1 s5 全角+PUA', ['check', '--files', str(R1/'s5_fullwidth.docx'), '--region', '朝阳', '--stage', '期中', '--profile', P]))
    recs.append(run('L12 r1 s8 HD-YIMO 文字版新卷', ['check', '--files', str(R1/'s8_hd_yimo_text_copy.docx'), '--region', '海淀', '--stage', '一模', '--profile', P]))
    recs.append(run('L13 exam-id BJ-2025-HD-QIZHONG', ['check', '--exam-id', 'BJ-2025-HD-QIZHONG', '--profile', P]))
    recs.append(run('L14 exam-id BJ-2023-HD-QIZHONG --claimed-id BJ-2024-HD-QIZHONG', ['check', '--exam-id', 'BJ-2023-HD-QIZHONG', '--claimed-id', 'BJ-2024-HD-QIZHONG', '--profile', P]))
elif group == 'examdir':
    recs.append(run('E1 题库外副本 BJ-2026-HD-QIMO(README 有学年)', ['check', '--exam-dir', str(S/'examdir'/'新卷_HDQIMO'), '--region', '海淀', '--stage', '期末', '--profile', P]))
    recs.append(run('E2 题库外副本 BJ-2025-HD-QIZHONG(整卷)', ['check', '--exam-dir', str(S/'examdir'/'新卷_HDQZ25'), '--region', '海淀', '--stage', '期中', '--profile', P]))
    recs.append(run('E3 题库外副本 BJ-2024-HD-QIZHONG 目录名即卷号', ['check', '--exam-dir', str(S/'examdir'/'BJ-2024-HD-QIZHONG'), '--profile', P]))
elif group == 'neg':
    recs.append(run('N1 profile 不存在', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', '/no/such.json']))
    recs.append(run('N2 冻结册只读', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', str(C/'profiles_cloud'/'bixiu2_frozen_test.json')]))
    recs.append(run('N3 exam-dir 指向文件', ['check', '--exam-dir', str(SY/'r6_half_reuse.docx'), '--profile', P]))
    (S/'emptydir').mkdir(exist_ok=True)
    recs.append(run('N4 exam-dir 空目录', ['check', '--exam-dir', str(S/'emptydir'), '--stage', '期中', '--profile', P]))
    recs.append(run('N5 files 给目录', ['check', '--files', str(SY), '--stage', '期中', '--profile', P]))
    recs.append(run('N6 audit --limit -1', ['audit', '--limit', '-1', '--profile', P, '--bank', str(R/'DeepSeek_政治题库资料库_20260918')]))
    recs.append(run('N7 files --claimed-id 乱写', ['check', '--files', str(SY/'r6_half_reuse.docx'), '--claimed-id', 'hello', '--stage', '期中', '--profile', P]))
    recs.append(run('N8 ASM 卷号', ['check', '--exam-id', 'ASM-2024届各区一模试题分类汇编必修1', '--profile', P]))
    recs.append(run('N9 小写卷号', ['check', '--exam-id', 'bj-2026-hd-qizhong', '--profile', P]))
    recs.append(run('N10 --debug 在子命令后+错误卷号', ['check', '--exam-id', 'BJ-XX', '--debug', '--profile', P]))
    (SY/'fake.docx').write_bytes(b'PK\x03\x04garbage')
    recs.append(run('N11 伪 docx', ['check', '--files', str(SY/'fake.docx'), '--stage', '期中', '--profile', P]))
    recs.append(run('N12 --stage 非法值 exam-dir', ['check', '--exam-dir', str(S/'emptydir'), '--stage', '春季', '--region', '火星', '--profile', P]))
    recs.append(run('N13 --bank 不存在', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--bank', '/no/bank']))
    recs.append(run('N14 --raw-root 不存在', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--raw-root', '/no/raw', '--profile', P]))
elif group == 'guard':
    good_dir = C / '构建' / 'exam_register_r2probe'
    good_dir.mkdir(exist_ok=True)
    for f in good_dir.glob('*.json'):
        f.unlink()
    (S/'out').mkdir(exist_ok=True)
    for f in (S/'out').glob('*.json'):
        f.unlink()
    link = S / 'link_to_bank'
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(R / 'DeepSeek_政治题库资料库_20260918')
    cases = [
        ('G1 临时区（输入也在临时区）', ['check', '--files', str(SY/'r6_half_reuse.docx'), '--stage', '期中', '--report', str(S/'out'/'g1.json'), '--profile', P], S/'out'/'g1.json'),
        ('G1b 临时区（输入也在临时区，不给 profile）', ['check', '--files', str(SY/'r6_half_reuse.docx'), '--stage', '期中', '--report', str(S/'out'/'g1b.json')], S/'out'/'g1b.json'),
        ('G2 候选 构建/（输入在临时区）', ['check', '--files', str(SY/'r6_half_reuse.docx'), '--stage', '期中', '--report', str(good_dir/'g2.json'), '--profile', P], good_dir/'g2.json'),
        ('G3 符号链接目录→题库', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(link/'g3.json')], R/'DeepSeek_政治题库资料库_20260918'/'g3.json'),
        ('G4 原材料目录 无profile', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(R/'00_共同资料/原材料/g4.json')], R/'00_共同资料/原材料/g4.json'),
        ('G5 后勤管理 无profile', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(R/'后勤管理/g5.json')], R/'后勤管理/g5.json'),
        ('G6 云端/ 无profile', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(R/'云端/g6.json')], R/'云端/g6.json'),
        ('G7 候选目录根（非构建）', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(C/'g7.json'), '--profile', P], C/'g7.json'),
        ('G8 ../ 逃逸', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(good_dir) + '/../../../../g8.json', '--profile', P], C.parents[1]/'g8.json'),
        ('G9 .txt 后缀', ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(good_dir/'g9.txt'), '--profile', P], good_dir/'g9.txt'),
        ('G10 audit 冻结册 --report', ['audit', '--limit', '1', '--profile', str(C/'profiles_cloud'/'bixiu2_frozen_test.json'), '--report', str(good_dir/'g10.json')], good_dir/'g10.json'),
        ('G11 audit --limit 2 --report 构建', ['audit', '--limit', '2', '--profile', P, '--report', str(good_dir/'g11.json')], good_dir/'g11.json'),
        ('G12 --exam-dir 在临时区 → 报告写临时区另一子目录', ['check', '--exam-dir', str(S/'examdir'/'新卷_HDQZ25'), '--stage', '期中', '--report', str(S/'out'/'g12.json'), '--profile', P], S/'out'/'g12.json'),
    ]
    for name, args, target in cases:
        rec = run(name, args)
        rec['target_written'] = target.exists()
        if target.exists() and not (str(target).startswith(str(S)) or str(target).startswith(str(good_dir))):
            target.unlink()
            rec['cleanup'] = 'removed stray write'
        recs.append(rec)
    link.unlink()
out = C / '审查' / 'exam_register_r2' / f'probe_cli_r2_{group}.json'
out.write_text(json.dumps(recs, ensure_ascii=False, indent=1), encoding='utf-8')
