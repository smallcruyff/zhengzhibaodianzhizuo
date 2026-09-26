#!/usr/bin/env python3
"""exam_register.py 回归测试（返修 r3，2026-09-25）。

只读真实输入（题库、原材料、exams.csv）；全部输出只写系统临时目录（本脚本所在目录下的
scratch/，每次运行先清空）。用真实子进程调用 exam_register.py，核对 stdout JSON、退出码、
以及（负例）--report 守卫。baseline_guard 在测试前后各跑一次，证明真实输入未被本轮测试改动。

按 任务_新卷入书流水线_20260925.md 里 exam_register.py 的 5 组验收组织，第 6 组是返修 r1 的
定向回归，第 7/8/9 组是返修 r2 针对审查意见 exam_register_审查_r2.json 的 7 个 major（M-A～
M-G）与部分 minor 的可复现回归用例，第 10 组是返修 r3 针对 exam_register_审查_r3.json 的 5 个
major（M-H～M-L）与全部 minor 的回归用例（修前失败、修后通过——除非另注明“已顺带修复，此处只是
补断言”）。本文件不依赖 审查/ 目录下的探针脚本或合成件，所有合成输入用 make_docx() 现造，
仅读真实题库时用 shutil.copytree 复制到系统临时目录，不改题库本身。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True  # 本文件也会 import exam_register，不给候选目录留 __pycache__（m12）

HERE = Path(__file__).resolve().parent
TOOL = HERE / 'exam_register.py'
PROFILE = HERE / 'profiles_cloud' / 'bixiu3.json'
FROZEN_PROFILE = HERE / 'profiles_cloud' / 'bixiu2_frozen_test.json'
BASELINE_GUARD = HERE / 'tools' / 'baseline_guard.py'
BASELINE_BASE = HERE / '构建' / 'baseline_20260925.json'

sys.path.insert(0, str(HERE))
import exam_register as er  # noqa: E402  复用其 REPO_ROOT 定位（m12：不再硬编码云端路径）、
                             # extract_stem_from_md/load_bank_alias_tables（合成复用题）、
                             # scan_duplicates（m6/m7 的纯函数单测）

REPO_ROOT = er.REPO_ROOT
BANK = REPO_ROOT / 'DeepSeek_政治题库资料库_20260918'

# 系统临时目录（m12：不再硬编码本次会话的 scratchpad 路径，拷回本地/换一台机器也能直接重跑）
SCRATCH = Path(tempfile.gettempdir()) / 'exam_register_test_scratch'
BUILD_OUT = HERE / '构建' / 'exam_register'

results = []


def record(name, ok, detail='', seconds=None):
    t = f'{seconds:.1f}s' if seconds is not None else ''
    results.append({'test': name, 'ok': bool(ok), 'detail': detail, 'seconds': seconds})
    print(('PASS' if ok else 'FAIL'), name, t, ('- ' + detail) if detail else '')


def run(args, timeout=180):
    t0 = time.time()
    p = subprocess.run([sys.executable, '-B', str(TOOL)] + args, capture_output=True, text=True, timeout=timeout)
    dt = time.time() - t0
    return p.returncode, p.stdout, p.stderr, dt


def run_json(args, timeout=180):
    code, out, err, dt = run(args, timeout=timeout)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = None
    return code, data, err, dt


def baseline_check(label):
    t0 = time.time()
    p = subprocess.run([sys.executable, '-B', str(BASELINE_GUARD), 'check', '--base', str(BASELINE_BASE)],
                        capture_output=True, text=True, timeout=180)
    dt = time.time() - t0
    ok = p.returncode == 0
    record(f'baseline_guard（真实输入未变，{label}）', ok, p.stdout.strip()[:400] if not ok else '', dt)
    return ok, p.stdout


def setup():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    (SCRATCH / 'synth').mkdir(parents=True, exist_ok=True)
    BUILD_OUT.mkdir(parents=True, exist_ok=True)
    for old in BUILD_OUT.glob('test_*.json'):
        old.unlink()


# ---------------------------------------------------------------- 合成原件（自包含：不依赖 审查/ 目录）
FILLER_QS = [
    '某市推行“接诉即办”改革，市民热线诉求当天响应、限期办结，并将办理结果纳入部门考核。这一做法'
    '①坚持以人民为中心的发展思想②说明政府职能已经由管理转向服务③有利于提高政府的公信力和执行力'
    '④表明群众可以直接决定政府的施政方向A．①②B．①③C．②④D．③④',
    '某县探索“党建引领、村民议事、乡贤助力”的乡村治理模式，村内公共事务由村民议事会讨论决定。这一模式'
    '①丰富了基层民主的实现形式②改变了村民委员会的性质③有利于调动村民参与治理的积极性④说明村民议事会是基层政权组织'
    'A．①③B．①④C．②③D．②④',
    '某省人大常委会在制定地方性法规过程中，通过基层立法联系点广泛收集群众意见，并对意见采纳情况予以反馈。这体现了'
    '①全过程人民民主的实践②地方人大享有国家立法权③科学立法、民主立法的要求④人民群众直接行使立法权'
    'A．①③B．①④C．②③D．②④',
    '某区检察院针对校园周边食品安全问题发出检察建议，督促相关行政机关依法履职并开展专项整治。这说明'
    '①检察机关是国家的法律监督机关②检察机关可以直接行使行政处罚权③检察建议有助于推动依法行政④检察机关领导行政机关开展工作'
    'A．①③B．①④C．②③D．②④',
    '某市政协围绕“老旧小区改造”开展专题协商，委员们深入调研并提出多项建议，被有关部门吸收采纳。这表明'
    '①人民政协是专门协商机构②人民政协是国家权力机关③政协协商有助于科学民主决策④政协委员可以代替政府作出决策'
    'A．①③B．①④C．②③D．②④',
    '某地法院设立“共享法庭”，把诉讼服务延伸到村社网格，就地化解矛盾纠纷。这一做法'
    '①便利群众参与诉讼②改变了法院的审判职能③推动矛盾纠纷源头化解④意味着调解可以替代审判'
    'A．①③B．①④C．②③D．②④',
]


def make_docx(name, header_lines, questions):
    import docx
    d = docx.Document()
    for h in header_lines:
        d.add_paragraph(h)
    for i, q in enumerate(questions):
        d.add_paragraph(f'{i + 1}．{q}')
    out = SCRATCH / 'synth' / name
    d.save(str(out))
    return out


def make_table_header_docx(name, header_cells, questions):
    """m2 正例：卷首日期/学年放在表格单元格里，不在正文段落——python-docx 直读（d.paragraphs）
    看不到表格内容，必须走 bh.read_docx 才能取到。"""
    import docx
    d = docx.Document()
    t = d.add_table(rows=1, cols=len(header_cells))
    for i, c in enumerate(header_cells):
        t.cell(0, i).text = c
    for i, q in enumerate(questions):
        d.add_paragraph(f'{i + 1}．{q}')
    out = SCRATCH / 'synth' / name
    d.save(str(out))
    return out


def make_blank_pdf(name):
    import fitz
    out = SCRATCH / 'synth' / name
    doc = fitz.open()
    page = doc.new_page()
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 100))
    pix.set_rect(pix.irect, (200, 200, 200))
    page.insert_image(fitz.Rect(50, 50, 500, 700), pixmap=pix)
    doc.save(str(out))
    doc.close()
    return out


def make_corrupt_pdf(name):
    out = SCRATCH / 'synth' / name
    out.write_bytes(b'%PDF-1.4\ngarbage not a real pdf, no xref table')
    return out


def bank_question_stem(exam_id, qno):
    """取题库一道真题的“采用题面”原文，供合成“复用题”用例——真实内容，不是编造。"""
    T, _ = er.load_bank_alias_tables(BANK)
    p = BANK / 'questions' / exam_id / f'{exam_id}-Q{qno}.md'
    stem, _basis = er.extract_stem_from_md(p.read_text(encoding='utf-8'), T)
    return stem.strip()


# ---------------------------------------------------------------- 1. 三张已知错号卷（含 B1/M-A/M-B：链式改号顺序/重定向表）
def group1():
    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2023-HD-QIZHONG', '--profile', str(PROFILE)])
    plan = d.get('rename_plan') if d else None
    redirects = d.get('redirects') if d else None
    reused = d.get('reused_ids') if d else None
    ok = (code == 1 and d and d['cohort_year'] == 2024 and d['cohort_status'] == 'OK'
          and d['suggestion']['suggested_id'] == 'BJ-2024-HD-QIZHONG' and d['suggestion']['occupied']
          and plan and plan[0]['old'] == 'BJ-2024-HD-QIZHONG' and plan[0]['retire_into'] == 'BJ-2025-HD-QIZHONG'
          and plan[1] == {'old': 'BJ-2023-HD-QIZHONG', 'new': 'BJ-2024-HD-QIZHONG',
                            'reason': '上述步骤腾出 BJ-2024-HD-QIZHONG 后，本卷（现卷号 BJ-2023-HD-QIZHONG）改为该号'}
          and redirects == [{'old': 'BJ-2024-HD-QIZHONG', 'new': 'BJ-2025-HD-QIZHONG', 'after_step': 1},
                              {'old': 'BJ-2023-HD-QIZHONG', 'new': 'BJ-2024-HD-QIZHONG', 'after_step': 2}]
          and reused == ['BJ-2024-HD-QIZHONG'])
    record('1a BJ-2023-HD-QIZHONG → 届别2024，占用+链式改号顺序（先2024→2025去重，再2023→2024），'
           'redirects 含本卷自己的旧→新（M-B），reused_ids 标出 BJ-2024-HD-QIZHONG 前后指不同的考试', ok,
           f'cohort={d.get("cohort_year") if d else None} plan={plan} redirects={redirects} reused={reused}', dt)

    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2024-HD-QIZHONG', '--profile', str(PROFILE)])
    dup = next((a for a in (d['duplicates'] if d else []) if a['exam_id'] == 'BJ-2025-HD-QIZHONG'), None)
    already = d.get('chain_kind') if d else None
    ok = (code == 1 and d and d['cohort_year'] == 2025 and dup and dup['kind'] == 'duplicate_registration'
          and dup['matched'] == 21 and already == 'already_registered'
          and d.get('id_mismatch') == {'registered_year': 2024, 'evidence_cohort_year': 2025})  # M-G：stdout 真有这个键
    record('1b BJ-2024-HD-QIZHONG → 届别2025，与BJ-2025-HD-QIZHONG重复登记21/21，占用链判"已登记不要重复注册"，'
           'id_mismatch 键真实存在（M-G）', ok,
           f'cohort={d.get("cohort_year") if d else None} dup={dup} chain_kind={already} '
           f'id_mismatch={d.get("id_mismatch") if d else None}', dt)

    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2024-CY-QIZHONG', '--profile', str(PROFILE)])
    ok = (code == 1 and d and d['cohort_year'] == 2025
          and d['suggestion']['suggested_id'] == 'BJ-2025-CY-QIZHONG' and not d['suggestion']['occupied'])
    record('1c BJ-2024-CY-QIZHONG → 届别2025，建议BJ-2025-CY-QIZHONG（未占用）', ok,
           f'cohort={d.get("cohort_year") if d else None}', dt)


# ---------------------------------------------------------------- 2. 对照组 + M-C（OCR 串题不算复用）
CONTROL_CLEAN = [
    'BJ-2026-CY-QIZHONG', 'BJ-2026-HD-QIZHONG',
    'BJ-2026-XC-QIMO', 'BJ-2025-XC-YIMO', 'BJ-2026-CY-ERMO',
    'BJ-2025-BJ-GAOKAO', 'BJ-2026-BJ-GAOKAO',
]


def group2():
    bad = []
    t0 = time.time()
    for eid in CONTROL_CLEAN:
        code, d, err, dt = run_json(['check', '--exam-id', eid, '--profile', str(PROFILE)])
        if d is None:
            bad.append(f'{eid}: 无法解析输出 exit={code} err={err[:200]}')
            continue
        if d.get('id_mismatch') is not None:  # M-G：stdout 现在真有 id_mismatch 键，这条断言不再恒真
            bad.append(f'{eid}: 误报届别不符 {d["id_mismatch"]}')
        if d.get('cohort_status') != 'OK':
            bad.append(f'{eid}: cohort_status 不是 OK：{d.get("cohort_status")}')
        false_dup = [a for a in d.get('duplicates', []) if a['kind'] == 'duplicate_registration']
        if false_dup:
            bad.append(f'{eid}: 误报 duplicate_registration {false_dup}')
    record('2a 对照组（2026期中/期末/一模二模/高考）cohort_status=OK、不误报 id_mismatch（M-G：断言现在查真实存在'
           '的键）、不误报重复登记', not bad, '; '.join(bad)[:600], time.time() - t0)

    # M-C：题库里“BJ-2022~2024-BJ-GAOKAO”这一对经审查核实是 OCR 候选节混入往年对照例题（串题），
    # 不是真复用——必须被单列为 needs_verification_low_confidence，不能再算进 shared_or_reused_questions
    # （r1 回执曾误称其为“真实正例”，本轮撤回，见返修回执）。
    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2022-BJ-GAOKAO', '--profile', str(PROFILE)])
    hit = next((x for x in (d['duplicates'] if d else []) if x['exam_id'] == 'BJ-2024-BJ-GAOKAO'), None)
    ok = (bool(hit) and hit['kind'] == 'needs_verification_low_confidence' and hit['matched'] == 0
          and hit['low_confidence_count'] >= 3 and not hit['fraction_reliable'])
    record('2b M-C 修复：BJ-2022~2024-BJ-GAOKAO（曾被 r1 误称“真实复用”）实为 OCR 串题，单列'
           'needs_verification_low_confidence，不计入正式 kind、matched=0', ok, f'hit={hit}', dt)

    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2024-BJ-GAOKAO', '--profile', str(PROFILE)])
    false_dup = [a for a in (d['duplicates'] if d else []) if a['kind'] == 'duplicate_registration']
    record('2c BJ-2024-BJ-GAOKAO 的全部复用对都不误判为 duplicate_registration', not false_dup,
           f'duplicates={d.get("duplicates") if d else None}', dt)


# ---------------------------------------------------------------- 3. audit 全库（M4：summary/退出码/撤销登记；M-C 汇总口径）
def group3():
    out_report = BUILD_OUT / 'test_audit_full.json'
    if out_report.exists():
        out_report.unlink()
    code, out, err, dt = run(['audit', '--profile', str(PROFILE), '--report', str(out_report)], timeout=240)
    if not out_report.is_file():
        record('3a audit 全库可运行并写出报告', False, f'exit={code} err={err[:300]}', dt)
        return
    rep = json.loads(out_report.read_text(encoding='utf-8'))
    record('3a audit 全库可运行并写出报告', True, f'{rep["summary"]}', dt)

    mismatched = {it['exam_id'] for it in rep['items'] if it.get('id_mismatch')}
    known = {'BJ-2023-HD-QIZHONG', 'BJ-2024-HD-QIZHONG', 'BJ-2024-CY-QIZHONG'}
    missing = known - mismatched
    extra = mismatched - known
    qizhong_qimo_2026 = {it['exam_id'] for it in rep['items']
                          if it['exam_id'].split('-')[-1] in ('QIZHONG', 'QIMO')
                          and it['exam_id'].startswith('BJ-2026-')}
    ledger_violation = qizhong_qimo_2026 & mismatched
    ok = (not missing) and (not ledger_violation) and (not extra)
    record('3b audit 命中且仅命中 3 张已知错号卷；不与 ledger“2026期中/期末无误”结论冲突（M1 修复前会多报）', ok,
           f'漏报={sorted(missing)} 多报={sorted(extra)} 违反ledger={sorted(ledger_violation)}')

    # M4：summary 要有 weak_only 计数，且不能用循环论证（WEAK_ONLY 状态本身单列，不计入“无误”）
    s = rep['summary']
    ok = all(k in s for k in ('weak_only', 'retired', 'verified_by_A', 'verified_by_B', 'low_fingerprint_coverage',
                                'needs_verification_low_confidence_only'))
    record('3c summary 含 weak_only/retired/verified_by_A/verified_by_B/low_fingerprint_coverage/'
           'needs_verification_low_confidence_only（M4/M-C）', ok, str(s))

    # m10：exams.csv 标记 retired_duplicate_registration 的卷（BJ-2023-HD-QIMO）要被识别，不当普通 OK 报
    retired_item = next((it for it in rep['items'] if it['exam_id'] == 'BJ-2023-HD-QIMO'), None)
    ok = bool(retired_item and retired_item.get('retired') and
              retired_item['retired'].get('extract_status') == 'retired_duplicate_registration')
    record('3d BJ-2023-HD-QIMO（exams.csv 标记已撤销登记）被识别为 retired，不当普通 OK 报（m10）', ok,
           f'retired={retired_item.get("retired") if retired_item else None}')

    conflicts = [it['exam_id'] for it in rep['items'] if it.get('cohort_status') == 'CONFLICT']
    record('3e 全库 CONFLICT=0（此前 BJ-2026-YQ-YIMO 的假冲突已随 M1 头部窗口修复消失，人工复核见回执）',
           len(conflicts) == 0, f'conflicts={conflicts}')

    # M-C：BJ-2022~2024-BJ-GAOKAO 这一对在全库汇总里也要落在“低置信”桶，不落进 has_duplicate_or_reuse
    ocr_item = next((it for it in rep['items'] if it['exam_id'] == 'BJ-2022-BJ-GAOKAO'), None)
    ocr_kinds = {a['kind'] for a in (ocr_item.get('duplicates') or [])} if ocr_item else set()
    ok = ocr_item is not None and ocr_kinds == {'needs_verification_low_confidence'}
    record('3f audit 全库口径下 BJ-2022-BJ-GAOKAO 与 2024 高考那对也只落 needs_verification_low_confidence（M-C）',
           ok, f'kinds={ocr_kinds}')


# ---------------------------------------------------------------- 4. --files 新卷模式（B2：双登记不再随哈希抖动；M6：一对一匹配）
def group4():
    dup_file = REPO_ROOT / '00_共同资料/原材料/2025模拟题/2025各区期末/2025海淀期中/试卷/试卷.pdf'
    code, d, err, dt = run_json(['check', '--files', str(dup_file), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    by_id = {a['exam_id']: a for a in (d['duplicates'] if d else [])}
    ok = (code == 1 and d and d['cohort_year'] == 2025
          and by_id.get('BJ-2024-HD-QIZHONG', {}).get('kind') == 'duplicate_registration'
          and by_id.get('BJ-2025-HD-QIZHONG', {}).get('kind') == 'duplicate_registration')
    record('4a --files 把 BJ-2025-HD-QIZHONG 原卷当新卷 → 届别2025，两张已有登记都判 duplicate_registration', ok,
           f'cohort={d.get("cohort_year") if d else None} dup={by_id}', dt)

    # B2：同一比对换 3 个不同的 PYTHONHASHSEED 各跑一次，结果必须一致（修复前会在 dup/reuse 间随机摆动）
    import os
    seeds_ok = True
    seed_detail = []
    t0 = time.time()
    for seed in ('11', '23', '97'):
        env = dict(os.environ)
        env['PYTHONHASHSEED'] = seed
        p = subprocess.run([sys.executable, '-B', str(TOOL), 'check', '--files', str(dup_file),
                             '--region', '海淀', '--stage', '期中', '--profile', str(PROFILE)],
                            capture_output=True, text=True, timeout=180, env=env)
        try:
            dd = json.loads(p.stdout)
        except json.JSONDecodeError:
            dd = None
        kinds = sorted((a['exam_id'], a['kind']) for a in (dd['duplicates'] if dd else []))
        seed_detail.append((seed, kinds))
        if kinds != [('BJ-2024-HD-QIZHONG', 'duplicate_registration'), ('BJ-2025-HD-QIZHONG', 'duplicate_registration')]:
            seeds_ok = False
    record('4b PYTHONHASHSEED 11/23/97 三次结果一致（B2 修复前会有一张被误标为 shared_or_reused）', seeds_ok,
           str(seed_detail)[:500], time.time() - t0)

    synth = make_docx('synthetic_new_exam.docx',
                       ['海淀区2026—2027学年第一学期期中练习', '高三思想政治', '2026.11'], FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(synth), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = (code == 0 and d and d['cohort_year'] == 2027 and not d['duplicates']
          and d['suggestion']['suggested_id'] == 'BJ-2027-HD-QIZHONG' and not d['suggestion']['occupied'])
    record('4c 合成“确实新”的卷 → 届别正确、不报重复、给出未占用的建议卷号', ok,
           f'cohort={d.get("cohort_year") if d else None} dup={d.get("duplicates") if d else None}', dt)

    # M6 正例：部分复用（9 题里 3 题取自真实库卷 BJ-2026-HD-QIZHONG）——必须切出多题、按占比判复用，
    # 不能退回“整卷”把 1 题命中就当 duplicate_registration（修复前的真实表现）；basis 非 OCR，
    # low_confidence_count 应为 0（M-C：真实复用与串题分得开）
    reused_stem = bank_question_stem('BJ-2026-HD-QIZHONG', 1)
    filler8 = (FILLER_QS + FILLER_QS)[:8]  # FILLER_QS 只有 6 条，循环补足到 8 条，凑够 1+8=9 题
    partial_qs = [reused_stem] + filler8
    synth2 = make_docx('s9_partial_reuse.docx', ['海淀区2026—2027学年第一学期期中练习', '高三思想政治', '2026.11'], partial_qs)
    code, d, err, dt = run_json(['check', '--files', str(synth2), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    hit = next((a for a in (d['duplicates'] if d else []) if a['exam_id'] == 'BJ-2026-HD-QIZHONG'), None)
    ok = (bool(hit) and hit['total'] == 9 and hit['matched'] == 1 and hit['kind'] == 'shared_or_reused_questions'
          and hit['low_confidence_count'] == 0)
    record('4d M6 正例：9 题中 1 题复用 → 切出 9 题、判 shared_or_reused_questions 1/9（不是整卷 1/1 '
           'duplicate_registration），low_confidence_count=0（不是 M-C 的串题，是真复用）',
           ok, f'hit={hit}', dt)

    # M6/M-G 正例二：复用题放在第 4500 字之后（旧版只读前约 4000 字/2 页会漏检；r1 的 4e 断言复用点仍在
    # 4000 字以内，修复前也能通过，本轮把复用点推到 4500 字以后，测试才真正针对 M6 的“全文抽取”）
    filler_long = FILLER_QS * 10  # 撑够长度，确保复用题落在 4500 字之后
    late_qs = filler_long[:40] + [reused_stem]
    synth3 = make_docx('s11_reuse_after_4500_chars.docx',
                        ['海淀区2026—2027学年第一学期期中练习', '高三思想政治', '2026.11'], late_qs)
    offset = sum(len(q) for q in filler_long[:40])
    code, d, err, dt = run_json(['check', '--files', str(synth3), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    hit2 = next((a for a in (d['duplicates'] if d else []) if a['exam_id'] == 'BJ-2026-HD-QIZHONG'), None)
    record(f'4e M6/M-G 正例：复用题在第 {offset} 字之后（{"确实" if offset > 4500 else "未达到"} 4500 字上限，'
           'm5 修复前 4000 字窗口读不到）仍能检出', bool(hit2) and offset > 4500, f'hit={hit2} offset={offset}', dt)


# ---------------------------------------------------------------- 5. 负例
def group5():
    code, out, err, dt = run(['check', '--exam-id', 'BJ-NOTYEAR-XX-YIMO', '--profile', str(PROFILE)])
    record('5a 卷号格式错 → 退出2', code == 2, f'exit={code} err={err.strip()[:200]}', dt)

    code, out, err, dt = run(['check', '--exam-id', 'BJ-2025-HD-GAOKAO', '--profile', str(PROFILE)])
    record('5a2 高考卷号区县位必须是 BJ（HD 应拒绝）→ 退出2', code == 2, f'exit={code} err={err.strip()[:200]}', dt)

    code, out, err, dt = run(['check', '--files', '/no/such/exam.pdf', '--region', '海淀', '--stage', '期中',
                               '--profile', str(PROFILE)])
    record('5b 文件不存在 → 退出2', code == 2, f'exit={code} err={err.strip()[:200]}', dt)

    scanned = make_blank_pdf('scanned_no_text.pdf')
    code, d, err, dt = run_json(['check', '--files', str(scanned), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = (code == 1 and d and d['cohort_status'] == 'NEEDS_LOCAL' and d['cohort_year'] is None)
    record('5c 无文字层 PDF（文件名不含日期）→ NEEDS_LOCAL，退出1', ok,
           f'status={d.get("cohort_status") if d else None} exit={code}', dt)

    scanned2_src = make_blank_pdf('scanned_tmp.pdf')
    scanned2 = scanned2_src.with_name('2024.11海淀高三期中试卷.pdf')
    shutil.copy(scanned2_src, scanned2)
    code, d, err, dt = run_json(['check', '--files', str(scanned2), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = (code == 1 and d and d['cohort_status'] == 'NEEDS_LOCAL' and d['cohort_year'] is None
          and d.get('suggestion') is None)
    record('5d M3 修复：无文字层 PDF 即使文件名带日期也判 NEEDS_LOCAL，不据文件名下断（不给建议卷号）', ok,
           f'status={d.get("cohort_status") if d else None} suggestion={d.get("suggestion") if d else None}', dt)

    corrupt = make_corrupt_pdf('corrupt.pdf')
    code, out, err, dt = run(['check', '--files', str(corrupt), '--region', '海淀', '--stage', '期中',
                               '--profile', str(PROFILE)])
    record('5e m6(r1) 修复：损坏的 PDF（--files 直接给的文件）→ 输入错误退出2，不当“需本地看图”', code == 2,
           f'exit={code} err={err.strip()[:200]}', dt)

    txt = SCRATCH / 'synth' / 'note.txt'
    txt.write_text('hello', encoding='utf-8')
    code, out, err, dt = run(['check', '--files', str(txt), '--region', '海淀', '--stage', '期中',
                               '--profile', str(PROFILE)])
    record('5f m6(r1) 修复：.txt 输入 → 退出2（CLI 层直接拒绝，不再当“不支持的格式”走到需本地看图）', code == 2,
           f'exit={code} err={err.strip()[:200]}', dt)

    code, d, err, dt = run_json(['check', '--files', str(dup_file_for_region_test()), '--stage', '期中',
                                  '--profile', str(PROFILE)])
    record('5g m4(r1) 修复：--files 不给 --region 也能跑（region 是可选的，只是不生成建议卷号）',
           code in (0, 1) and d is not None and d.get('suggestion') is None,
           f'exit={code} suggestion={d.get("suggestion") if d else None}', dt)

    for label, target in [
        ('书稿目录（仓库根）', REPO_ROOT / '必修三_最新Skill修订_20260913' / 'test_report.json'),
        ('题库目录', REPO_ROOT / 'DeepSeek_政治题库资料库_20260918' / 'test_report.json'),
        ('Skill目录', REPO_ROOT / '.claude' / 'skills' / 'beijing-gaokao-politics' / 'test_report.json'),
    ]:
        code, out, err, dt = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', str(PROFILE),
                                   '--report', str(target)])
        wrote = target.exists()
        if wrote:
            target.unlink()
        ok = (code == 3 and not wrote)
        record(f'5h --report 落受保护目录（{label}，带 --profile）→ 退出3，且未落盘', ok, f'exit={code} wrote={wrote}', dt)

    # M8 正例：不传 --profile 时，云端补充守卫仍要挡住受保护目录（修复前 prof=None 会放行）
    target = REPO_ROOT / 'DeepSeek_政治题库资料库_20260918' / 'test_report_noprofile.json'
    code, out, err, dt = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', str(target)])
    wrote = target.exists()
    if wrote:
        target.unlink()
    record('5i M8 修复：不传 --profile 时 --report 落题库目录仍退出3（修复前会放行写入）', code == 3 and not wrote,
           f'exit={code} wrote={wrote}', dt)

    code, out, err, dt = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', str(FROZEN_PROFILE),
                               '--report', str(BUILD_OUT / 'test_frozen.json')])
    wrote = (BUILD_OUT / 'test_frozen.json').exists()
    record('5j 冻结册配置 --report → 退出3（附加负例，非规格必测但同规则）', code == 3 and not wrote,
           f'exit={code} wrote={wrote}', dt)

    good = BUILD_OUT / 'test_good_report.json'
    if good.exists():
        good.unlink()
    code, out, err, dt = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', str(PROFILE),
                               '--report', str(good)])
    rep_ok = False
    if good.is_file():
        rep = json.loads(good.read_text(encoding='utf-8'))
        rep_ok = (rep.get('inputs', {}).get('exams_csv_sha256') is not None and 'summary' in rep
                  and 'min_stem_len' in rep.get('thresholds', {}) and 'header_window' in rep.get('thresholds', {})
                  and rep.get('inputs', {}).get('profile_sha256') is not None  # m11
                  and rep.get('inputs', {}).get('profile_book_id') is not None)  # m11
        raw_files = (rep.get('items') or [{}])[0].get('raw_files') or []
        rep_ok = rep_ok and all('sha256' in rf for rf in raw_files) if raw_files else rep_ok  # m11
    record('5k M9/m11 修复：--report 含 inputs SHA（含 profile_sha256/profile_book_id）/ summary（check 模式）/ '
           '完整 thresholds / raw_files 各自的 sha256', rep_ok, f'exit={code} exists={good.is_file()}', dt)
    record('5l --report 时 stdout 是纯 JSON（“报告已写”改到 stderr，m6(r1) 修复）',
           bool(out) and out.strip().startswith('{'), out.strip()[:60])


def dup_file_for_region_test():
    return REPO_ROOT / '00_共同资料/原材料/2025模拟题/2025各区期末/2025海淀期中/试卷/试卷.pdf'


# ---------------------------------------------------------------- 6. 定向回归：M1（卷首窗口/高二判定）、M7（--exam-dir 自排除）、m4(r1)（--stage 不再默认）
def group6():
    # M1-a：高三卷首 + Q1 题干里出现“高二”（题干正文引用，不是卷子自身年级）→ 不应被当成高二卷
    g3_header_g2_body = make_docx(
        's2_g3_header_g2_body.docx', ['海淀区2024—2025学年第一学期期中练习', '高三思想政治', '2024.11'],
        ['某校高二学生开展“模拟政协”活动，围绕校园周边交通拥堵问题撰写提案并提交区政协。这一活动'
         '①有利于增强学生的公民意识②说明学生可以直接参与国家立法③体现了人民政协履行职能的开放性④表明政协提案具有法律效力'
         'A．①③B．①④C．②③D．②④'] + FILLER_QS[1:])
    code, d, err, dt = run_json(['check', '--files', str(g3_header_g2_body), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = d and d['cohort_year'] == 2025 and not d.get('grade2')
    record('6a M1 修复：卷首写“高三”，Q1 题干出现“高二”（题干引用）→ 按高三算，届别2025，不误判高二', bool(ok),
           f'cohort={d.get("cohort_year") if d else None} grade2={d.get("grade2") if d else None}', dt)

    # M1-b：真高二卷（卷首本身写“高二”）→ 应比同一日期的高三卷晚一届
    g2_real = make_docx('s3_grade2.docx', ['海淀区2024—2025学年第一学期期中练习', '高二思想政治', '2024.11'], FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(g2_real), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = d and d['cohort_year'] == 2026 and d.get('grade2')
    record('6b M1 修复：真高二卷（卷首本身写“高二”）→ 届别2026（比同期高三卷晚一届），且 grade2=true 写进结果', bool(ok),
           f'cohort={d.get("cohort_year") if d else None} grade2={d.get("grade2") if d else None}', dt)
    diff_ok = False
    dt2 = None
    try:
        code2, d2, err2, dt2 = run_json(['check', '--files', str(g3_header_g2_body), '--region', '海淀', '--stage', '期中',
                                          '--profile', str(PROFILE)])
        diff_ok = d2 and d and d2['cohort_year'] != d['cohort_year']
    except Exception:
        pass
    record('6c M1 修复：“高三卷首+题干提高二”与“真高二卷”不再输出相同结果（修复前两者完全一样）', diff_ok, '', dt2)

    # M1-c：网站式标题（考试日历年）+ Q1 题干引用去年日期 → 按标题年+1 算，不被题干日期带偏
    webtitle = make_docx('s4_webtitle_bodydate.docx', ['2025北京朝阳高三（上）期中', '政  治',
                                                         '（考试时间90分钟 满分100分）'],
                          ['2024年10月，某市出台《促进民营经济高质量发展若干措施》，从市场准入、要素获取、公平执法等方面提出具体举措。这表明'
                           '①我国坚持“两个毫不动摇”②民营经济是国民经济的主导力量③优化营商环境有利于激发市场活力④政府直接配置民营企业的生产要素'
                           'A．①③B．①④C．②③D．②④'] + FILLER_QS[1:])
    code, d, err, dt = run_json(['check', '--files', str(webtitle), '--region', '朝阳', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = d and d['cohort_year'] == 2026
    record('6d M1 修复：网站式标题“2025北京朝阳高三（上）期中”+题干引用2024年10月 → 届别2026（标题年+1），不被题干日期带成2025', bool(ok),
           f'cohort={d.get("cohort_year") if d else None} issues={d.get("issues") if d else None}', dt)

    # M7：--exam-dir 指向题库自身目录，不应把自己判成“占用自己”或“与自己重复登记”
    d1 = BANK / 'questions' / 'BJ-2026-HD-QIZHONG'
    code, d, err, dt = run_json(['check', '--exam-dir', str(d1), '--profile', str(PROFILE)])
    ok = code == 0 and d and not d['issues'] and not d['duplicates']
    record('6e M7 修复：--exam-dir 指向题库自身目录 → 不自占用、不自重复（修复前退出1，报“已被占用”）', bool(ok),
           f'exit={code} issues={d.get("issues") if d else None}', dt)
    code, d, err, dt = run_json(['check', '--exam-dir', str(d1), '--claimed-id', 'BJ-2027-HD-QIZHONG',
                                  '--profile', str(PROFILE)])
    self_dup = next((a for a in (d['duplicates'] if d else []) if a['exam_id'] == 'BJ-2026-HD-QIZHONG'), None)
    record('6f M7 修复：同目录换 --claimed-id 仍不与自身数据重复比对（修复前会报 22/22 自重复）', self_dup is None,
           f'dup={d.get("duplicates") if d else None}', dt)

    # m4(r1) 修复：--files 不给 --stage 且不给 --claimed-id → 报输入错误，不再静默当“期中”处理
    code, out, err, dt = run(['check', '--files', str(dup_file_for_region_test()), '--region', '海淀',
                               '--profile', str(PROFILE)])
    record('6g m4(r1) 修复：--files 不给 --stage 也不给 --claimed-id → 退出2（不再静默按“期中”处理）', code == 2,
           f'exit={code} err={err.strip()[:150]}', dt)


# ---------------------------------------------------------------- 7. r2 返修：majors（M-A ~ M-G）定向回归
def group7():
    # M-A：内容全新的“新卷”，届别推算恰好落在 BJ-2025-HD-QIZHONG（正确登记）——不能建议把它并入错号
    # BJ-2024-HD-QIZHONG；也不能给出以 BJ-2025-HD-QIZHONG 为 old 的 redirects。
    new_hd_2025 = make_docx('r2_new_hd_2025_qizhong.docx',
                             ['海淀区2024—2025学年第一学期期中练习', '高三思想政治', '2024.11'], FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(new_hd_2025), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    redirects = d.get('redirects') or [] if d else []
    bad_old = [r for r in redirects if r.get('old') == 'BJ-2025-HD-QIZHONG']
    ok = (d and d['cohort_year'] == 2025 and d.get('chain_kind') != 'chain' and not bad_old
          and d.get('chain_kind') == 'blocked_conflict')
    record('7a M-A 修复：内容全新的候选卷、建议号落在 BJ-2025-HD-QIZHONG（正确登记）→ chain_kind='
           'blocked_conflict（不是 chain），redirects 里不出现以 2025 为 old 的条目（不再把正确卷号并入错号）',
           bool(ok), f'chain_kind={d.get("chain_kind") if d else None} redirects={redirects}', dt)

    # M-A：规格点名的“高二卷”场景——同一天期，真高二卷推出的届别（学年末年+1）恰好也落在 BJ-2025-HD-QIZHONG
    grade2_hd = make_docx('r2_grade2_hd_2025.docx',
                           ['海淀区2023—2024学年第一学期期中练习', '高二思想政治', '2023.11'], FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(grade2_hd), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    redirects2 = d.get('redirects') or [] if d else []
    bad_old2 = [r for r in redirects2 if r.get('old') == 'BJ-2025-HD-QIZHONG']
    ok = (d and d['cohort_year'] == 2025 and d.get('grade2') and d.get('chain_kind') != 'chain' and not bad_old2)
    record('7b M-A 修复：规格点名的高二卷（届别按学年末年+1 推出，恰好落在 BJ-2025-HD-QIZHONG）同样不触发'
           '反向改号', bool(ok), f'cohort={d.get("cohort_year") if d else None} grade2={d.get("grade2") if d else None} '
           f'chain_kind={d.get("chain_kind") if d else None} redirects={redirects2}', dt)

    # M-E：原件确认有文字层，但卷首窗口内没有任何日期/学年写法，文件名却带日期——不能单凭文件名（D 层）
    # 定届别、生成建议号；必须 NEEDS_LOCAL。
    nodate = make_docx('nodate_header_only.docx',
                        ['北京市海淀区高三思想政治期中练习', '思想政治'], FILLER_QS)
    nodate_named = nodate.with_name('2024.11海淀高三期中试卷_M-E.docx')
    shutil.copy(nodate, nodate_named)
    code, d, err, dt = run_json(['check', '--files', str(nodate_named), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = (d and d['cohort_year'] is None and d['cohort_status'] == 'NEEDS_LOCAL' and d.get('suggestion') is None
          and d.get('chain_kind') is None)
    record('7c M-E 修复：有文字层但卷首无日期/学年，文件名带日期 → NEEDS_LOCAL，不生成建议号、不展开改号链'
           '（修复前会单凭文件名定届别）', bool(ok),
           f'cohort={d.get("cohort_year") if d else None} status={d.get("cohort_status") if d else None} '
           f'suggestion={d.get("suggestion") if d else None}', dt)

    # M-D：--exam-dir 复制一份覆盖率很低的真实卷（BJ-2025-CY-YIMO，21 题只有 1 题抽得出题面），把那唯一
    # 一题换成另一张真实卷的题——分母必须用覆盖率的 total（21），不能用“抽得出题面的题数”（1），
    # 不能判 duplicate_registration 1/1。
    src_dir = BANK / 'questions' / 'BJ-2025-CY-YIMO'
    dst_dir = SCRATCH / 'examdir_low_coverage'
    if dst_dir.exists():
        shutil.rmtree(dst_dir)
    shutil.copytree(src_dir, dst_dir)
    only_stem_file = next(iter(dst_dir.glob('BJ-2025-CY-YIMO-Q*.md')))
    replacement = (BANK / 'questions' / 'BJ-2026-HD-QIZHONG' / 'BJ-2026-HD-QIZHONG-Q17.md').read_text(encoding='utf-8')
    # 只覆盖“抽得出题面”的那一题（覆盖率探测已知只有 1 题能抽出，见 known_limits 里的复现方法）；
    # 为稳妥起见，把全部题面文件都探测一遍，取第一个抽得出题面的文件来替换。
    T, _ = er.load_bank_alias_tables(BANK)
    target_file = None
    for p in sorted(dst_dir.glob('BJ-2025-CY-YIMO-Q*.md')):
        stem, _ = er.extract_stem_from_md(p.read_text(encoding='utf-8'), T)
        if stem and len(stem.strip()) >= 40:
            target_file = p
            break
    if target_file is not None:
        target_file.write_text(replacement.replace('BJ-2026-HD-QIZHONG-Q17', target_file.stem), encoding='utf-8')
    code, d, err, dt = run_json(['check', '--exam-dir', str(dst_dir), '--region', '朝阳', '--stage', '一模',
                                  '--profile', str(PROFILE)])
    hit = next((a for a in (d['duplicates'] if d else []) if a['exam_id'] == 'BJ-2026-HD-QIZHONG'), None)
    ok = (target_file is not None and hit is not None and hit['total'] > 5  # 分母是覆盖率 total，不是 1
          and hit['kind'] != 'duplicate_registration' and not hit['fraction_reliable'])
    record('7d M-D 修复：低覆盖率卷（题库 BJ-2025-CY-YIMO 类似情形）只复用 1 题不再判 duplicate_registration '
           '1/1，分母改用覆盖率 total、fraction_reliable=False', bool(ok),
           f'hit={hit} target_file={target_file}', dt)

    # M-F：--exam-dir 指向题库外的一份副本（README 写明学年），必须读到该 README（B 层），不能报
    # “题库无可查文字证据”。同时复制一份错号副本（BJ-2024-HD-QIZHONG），验证 --exam-dir 下也能查出
    # 届别不符（此前只有 --exam-id 能查出）。
    ok_dir = SCRATCH / 'examdir_readme_ok'
    if ok_dir.exists():
        shutil.rmtree(ok_dir)
    shutil.copytree(BANK / 'questions' / 'BJ-2026-HD-QIMO', ok_dir)
    code, d, err, dt = run_json(['check', '--exam-dir', str(ok_dir), '--region', '海淀', '--stage', '期末',
                                  '--profile', str(PROFILE)])
    ok = d and d['cohort_status'] == 'OK' and d['cohort_year'] == 2026
    record('7e M-F 修复：--exam-dir 指向题库外副本（README 写明学年）→ 读到 B 层证据，cohort_status=OK'
           '（修复前 NEEDS_LOCAL，还误称“题库无可查文字证据”）', bool(ok),
           f'status={d.get("cohort_status") if d else None} cohort={d.get("cohort_year") if d else None} '
           f'issues={d.get("issues") if d else None}', dt)

    bad_dir = SCRATCH / 'examdir_id_mismatch'
    if bad_dir.exists():
        shutil.rmtree(bad_dir)
    shutil.copytree(BANK / 'questions' / 'BJ-2024-HD-QIZHONG', bad_dir)
    code, d, err, dt = run_json(['check', '--exam-dir', str(bad_dir), '--claimed-id', 'BJ-2024-HD-QIZHONG',
                                  '--region', '海淀', '--stage', '期中', '--profile', str(PROFILE)])
    ok = d and d.get('id_mismatch') == {'registered_year': 2024, 'evidence_cohort_year': 2025}
    record('7f M-F 修复：--exam-dir 下同一份错号副本也能查出届别不符（修复前 --exam-dir 查不出，只有 '
           '--exam-id 能）', bool(ok), f'id_mismatch={d.get("id_mismatch") if d else None}', dt)

    # m10：改号链终止语——占用卷为已撤销登记时要点明“已撤销”，不是笼统的“真实冲突”
    retired_target = make_docx('r2_hd_2023_qimo_target.docx',
                                ['海淀区2022—2023学年第一学期期末练习', '高三思想政治', '2023.01'],
                                FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(retired_target), '--region', '海淀', '--stage', '期末',
                                  '--profile', str(PROFILE)])
    note = ((d.get('chain') or {}).get('note') or '') if d else ''
    plan10 = (d.get('rename_plan') or []) if d else []
    plan10_reason = plan10[0]['reason'] if plan10 else ''
    ok = d and d['suggestion'] and d['suggestion'].get('occupied') and '撤销' in plan10_reason
    record('m10 修复：占用卷号是已撤销登记（BJ-2023-HD-QIMO）时，rename_plan 的说明里点明“已撤销”，'
           '不是笼统的“真实冲突”', bool(ok), f'suggestion={d.get("suggestion") if d else None} plan={plan10}', dt)


# ---------------------------------------------------------------- 8. r2 返修：minors 的纯函数单测（m6/m7），不必跑子进程
class _FakeIndex:
    """scan_duplicates 只需要 index.match_question(exam_id, qid, ng, exclude_exam=None) 这一个接口，
    这里造一个假的，绕开真实题库，专门测阈值/一对一匹配这两条纯函数逻辑（m6/m7），比生成真实合成
    docx 快得多、也更确定。"""

    def __init__(self, table):
        self.table = table  # qid -> [{'exam_id','qid','sim','basis'}, ...]

    def match_question(self, exam_id, qid, ng, exclude_exam=None):
        return self.table.get(qid, [])


def group8():
    # m7：占比恰好 0.5 → shared_or_reused_questions（严格 > 才算 duplicate_registration，规格原文
    # “大部分题相同”不含恰好一半）
    questions = [{'qid': f'Q{i}', 'ngrams': set(), 'basis': 'bank_alias'} for i in range(1, 11)]
    table = {f'Q{i}': [{'exam_id': 'BJ-OPP', 'qid': f'OQ{i}', 'sim': 0.9, 'basis': 'bank_alias'}]
             for i in range(1, 6)}  # 10 题里 5 题命中 → 恰好一半
    against = er.scan_duplicates(_FakeIndex(table), 'CAND', questions)
    entry = against[0] if against else {}
    ok = (entry.get('matched_questions') == 5 and entry.get('total_questions') == 10
          and entry.get('fraction') == 0.5 and entry.get('kind') == 'shared_or_reused_questions')
    record('8a m7 修复：占比恰好 0.5 → shared_or_reused_questions（阈值改用严格 >，不是 >=）', ok, str(entry))

    table51 = {f'Q{i}': [{'exam_id': 'BJ-OPP', 'qid': f'OQ{i}', 'sim': 0.9, 'basis': 'bank_alias'}]
               for i in range(1, 7)}  # 10 题里 6 题命中 → 0.6，超过一半
    against51 = er.scan_duplicates(_FakeIndex(table51), 'CAND', questions)
    entry51 = against51[0] if against51 else {}
    ok51 = entry51.get('kind') == 'duplicate_registration' and entry51.get('fraction') == 0.6
    record('8a2 m7 对照：占比 0.6（超过一半）→ duplicate_registration（阈值本身没被误改宽）', ok51, str(entry51))

    # m6：两道候选题都命中对手卷同一道题（相似度不同）——必须一对一贪心匹配，只取分数更高的那对，
    # 不能让对手卷的匹配数超过它自己的题数（修复前会出现 22/21 这类不可能的比例）
    questions2 = [{'qid': 'C1', 'ngrams': set(), 'basis': 'bank_alias'},
                  {'qid': 'C2', 'ngrams': set(), 'basis': 'bank_alias'}]
    table2 = {
        'C1': [{'exam_id': 'BJ-OPP2', 'qid': 'O1', 'sim': 0.99, 'basis': 'bank_alias'}],
        'C2': [{'exam_id': 'BJ-OPP2', 'qid': 'O1', 'sim': 0.60, 'basis': 'bank_alias'}],  # 与 C1 抢同一道对手题，分数更低
    }
    against2 = er.scan_duplicates(_FakeIndex(table2), 'CAND2', questions2)
    entry2 = against2[0] if against2 else {}
    ok2 = (entry2.get('matched_questions') == 1 and entry2.get('contested_matches') == 1
           and entry2.get('pairs') and entry2['pairs'][0]['qid'] == 'C1')  # 分数更高的 C1 胜出
    record('8b m6 修复：两道候选题抢同一道对手题时一对一匹配，只取分数更高的一对，另一对计入 '
           'contested_matches（不再让匹配数超过对手卷题数）', ok2, str(entry2))

    # M-C 单测：任一侧 basis 为 fallback_low_confidence 时单列 low_confidence_pairs，不计入 kind 判定
    questions3 = [{'qid': 'C1', 'ngrams': set(), 'basis': 'bank_alias'},
                  {'qid': 'C2', 'ngrams': set(), 'basis': 'fallback_low_confidence'}]
    table3 = {
        'C1': [{'exam_id': 'BJ-OPP3', 'qid': 'O1', 'sim': 0.99, 'basis': 'bank_alias'}],
        'C2': [{'exam_id': 'BJ-OPP3', 'qid': 'O2', 'sim': 0.99, 'basis': 'bank_alias'}],
    }
    against3 = er.scan_duplicates(_FakeIndex(table3), 'CAND3', questions3, total_questions=2)
    entry3 = against3[0] if against3 else {}
    ok3 = (entry3.get('matched_questions') == 1 and len(entry3.get('low_confidence_pairs') or []) == 1
           and entry3.get('low_confidence_pairs')[0]['qid'] == 'C2')
    record('8c M-C 单测：候选题一侧标 fallback_low_confidence 时该配对单列 low_confidence_pairs，不计入 '
           'matched_questions', ok3, str(entry3))

    # m2：卷首日期/学年放在表格单元格里，python-docx 直读会漏掉，必须走 bh.read_docx 才能取到
    tbl_doc = make_table_header_docx('m2_table_header.docx',
                                      ['海淀区2026—2027学年第一学期期中练习', '2026.11'], FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(tbl_doc), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = d and d['cohort_year'] == 2027 and d['cohort_status'] == 'OK'
    record('8d m2 修复：卷首日期/学年放在表格单元格里也能识别（改走 bh.read_docx，不再只用 python-docx '
           '直读段落）', bool(ok), f'cohort={d.get("cohort_year") if d else None} status={d.get("cohort_status") if d else None}', dt)

    # m5：日期排在“考生须知 1．…2．…3．…”之后 → 不能在须知处截断丢掉日期
    notice_doc = make_docx('m5_notice_then_date.docx',
                            ['海淀区高三年级第一学期期中练习', '考生须知', '1．本试卷共8页。',
                             '2．考试时长90分钟。', '3．请在答题纸上作答。', '2026.11'], FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(notice_doc), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = d and d['cohort_year'] == 2027 and d['cohort_status'] == 'OK'
    record('8e m5 修复：日期排在“考生须知 1．2．3．”之后仍能取到（不再在须知处截断丢掉日期）', bool(ok),
           f'cohort={d.get("cohort_year") if d else None} status={d.get("cohort_status") if d else None}', dt)

    # m8：候选目录 构建/ 下、输入与报告同目录也应放行（此前会被“输入所在目录也算受保护根”误拒）
    p_in = BUILD_OUT / 'm8_probe'
    p_in.mkdir(parents=True, exist_ok=True)
    in_doc = make_docx('m8_in.docx', ['海淀区2026—2027学年第一学期期中练习', '2026.11'], FILLER_QS)
    shutil.copy(in_doc, p_in / 'in.docx')
    report_path = p_in / 'r.json'
    if report_path.exists():
        report_path.unlink()
    code, out, err, dt = run(['check', '--files', str(p_in / 'in.docx'), '--region', '海淀', '--stage', '期中',
                               '--profile', str(PROFILE), '--report', str(report_path)])
    ok = code == 0 and report_path.is_file()
    if report_path.is_file():
        report_path.unlink()
    shutil.rmtree(p_in, ignore_errors=True)
    record('8f m8 修复：--files 与 --report 都在候选 构建/ 同一子目录下也放行，不再把“输入所在目录”'
           '当成需要再嵌套一层的受保护根', ok, f'exit={code} err={err.strip()[:200]}', dt)


# ---------------------------------------------------------------- 9. r2 返修：CLI 边角（m9）
def group9():
    code, out, err, dt = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', '/no/such/profile.json'])
    record('9a m9 修复：--profile 路径不存在 → 输入错误退出2（不是“内部错误”）', code == 2,
           f'exit={code} err={err.strip()[:200]}', dt)

    code, out, err, dt = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', str(PROFILE),
                               '--raw-root', '/no/such/raw'])
    record('9b m9 修复：--raw-root 不存在 → 输入错误退出2（修复前静默降级为 NEEDS_LOCAL、退出1）', code == 2,
           f'exit={code} err={err.strip()[:200]}', dt)

    empty_dir = SCRATCH / 'empty_examdir'
    empty_dir.mkdir(parents=True, exist_ok=True)
    code, out, err, dt = run(['check', '--exam-dir', str(empty_dir), '--region', '海淀', '--stage', '期中',
                               '--profile', str(PROFILE)])
    record('9c m9 修复：--exam-dir 空目录（无逐题 MD）→ 输入错误退出2（修复前 NEEDS_LOCAL、退出1）', code == 2,
           f'exit={code} err={err.strip()[:200]}', dt)

    code, out, err, dt = run(['audit', '--profile', str(PROFILE), '--limit', '-1'])
    record('9d m9 修复：audit --limit -1 → 输入错误退出2（修复前静默当“不限”跑全库 84 张）', code == 2,
           f'exit={code} err={err.strip()[:200]}', dt)

    d1 = BANK / 'questions' / 'BJ-2026-HD-QIZHONG'
    code, out, err, dt = run(['check', '--exam-dir', str(d1), '--region', '火星', '--profile', str(PROFILE)])
    record('9e m9 修复：--exam-dir 模式下 --region 非法值也要报输入错误（此前不校验，照样跑）', code == 2,
           f'exit={code} err={err.strip()[:200]}', dt)


# ---------------------------------------------------------------- 10. r3 返修：majors（M-H~M-L）与全部 minor 的定向回归
RAW_ROOT = REPO_ROOT / '00_共同资料' / '原材料'


def group10():
    # M-H：同一原卷的两份同 SHA 副本（exam_files.csv 里 BJ-2024-CY-QIZHONG 的真实情形）一起传，
    # 分母不应合并稀释——仍应判 duplicate_registration 20/20，不是降级成 shared_or_reused 20/40
    cy24a = RAW_ROOT / '2024模拟题/2024朝阳期中/试卷/试卷.pdf'
    cy24b = RAW_ROOT / '2024模拟题/2024朝阳期中/试卷/补充材料/202411朝阳高三政治 期中1试题(1).pdf'
    code, d, err, dt = run_json(['check', '--files', str(cy24a), str(cy24b), '--region', '朝阳', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    hit = next((a for a in (d['duplicates'] if d else []) if a['exam_id'] == 'BJ-2024-CY-QIZHONG'), None)
    ok = bool(hit) and hit['kind'] == 'duplicate_registration' and hit['matched'] == 20 and hit['total'] == 20
    record('10a M-H 修复：同一原卷的两份同 SHA 副本一起传 → 仍是 duplicate_registration 20/20（修复前'
           '分母合并成 40，降级为 shared_or_reused_questions 20/40）', ok, f'hit={hit}', dt)

    # M-H：同一文件给两次（真实场景：清单里同一路径重复列出）——两张已有登记都应仍是 duplicate_
    # registration，chain_kind 应为 already_registered（与只传一次时一致），不是被稀释后的
    # blocked_conflict
    hd25 = RAW_ROOT / '2025模拟题/2025各区期末/2025海淀期中/试卷/试卷.pdf'
    code, d, err, dt = run_json(['check', '--files', str(hd25), str(hd25), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    by_id = {a['exam_id']: a for a in (d['duplicates'] if d else [])}
    ok = (d and d.get('chain_kind') == 'already_registered'
          and by_id.get('BJ-2024-HD-QIZHONG', {}).get('kind') == 'duplicate_registration'
          and by_id.get('BJ-2025-HD-QIZHONG', {}).get('kind') == 'duplicate_registration')
    record('10b M-H 修复：同一份文件给两次 → 结果与只给一次一致（duplicate_registration + '
           'chain_kind=already_registered），不因“文件更多”被稀释成 blocked_conflict', bool(ok),
           f'chain_kind={d.get("chain_kind") if d else None} dup={by_id}', dt)

    # M-I：20 题里只复用 2 题（BJ-2025-BJ-GAOKAO 的 Q1/Q5），但第 4 题题号漏了句点，切题只切出 3 块
    # （第 3 块吞掉 Q3~Q20）——不能把“少数题复用”判成 duplicate_registration
    T, _ = er.load_bank_alias_tables(BANK)
    r1 = bank_question_stem('BJ-2025-BJ-GAOKAO', 1)
    r5 = bank_question_stem('BJ-2025-BJ-GAOKAO', 5)
    import docx
    d10c = docx.Document()
    for h in ['海淀区2026—2027学年第一学期期末练习', '高三思想政治', '2027.01']:
        d10c.add_paragraph(h)
    filler18 = (FILLER_QS * 4)[:18]
    qs10c = [r1] + filler18 + [r5]
    for i, q in enumerate(qs10c):
        n = i + 1
        d10c.add_paragraph((f'{n} ' if n == 4 else f'{n}．') + q)  # 第4题漏句点
    p10c = SCRATCH / 'synth' / 's10c_poor_split_2_reused_of_20.docx'
    d10c.save(str(p10c))
    code, d, err, dt = run_json(['check', '--files', str(p10c), '--region', '海淀', '--stage', '期末',
                                  '--profile', str(PROFILE)])
    hit = next((a for a in (d['duplicates'] if d else []) if a['exam_id'] == 'BJ-2025-BJ-GAOKAO'), None)
    ok = bool(hit) and hit['kind'] != 'duplicate_registration' and not hit['fraction_reliable']
    record('10c M-I 修复：20 题中途漏一个题号、切出 3 块，其中 2 题复用 → 不再误判 duplicate_'
           'registration（修复前 2/3、fraction_reliable=true）', ok, f'hit={hit}', dt)

    # M-J：2024海淀期中原件是乱码文字层（印厂专用编码），真实登记里正是与 BJ-2025-HD-QIZHONG 重复的
    # 那份——不能报“无日期/学年写法”“已整卷粗略比对”，要明说无可用文字层、查重未执行
    hd24 = RAW_ROOT / '2024模拟题/2024海淀期中/试卷/试卷.pdf'
    code, d, err, dt = run_json(['check', '--files', str(hd24), '--region', '海淀', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    issues_txt = ' '.join(d.get('issues') or []) if d else ''
    ok = (d and d['cohort_status'] == 'NEEDS_LOCAL' and not d['duplicates']
          and '看图' in issues_txt and '查重' in issues_txt and '粗略比对' not in issues_txt)
    record('10d M-J 修复：真实乱码文字层原件（2024海淀期中）→ NEEDS_LOCAL，issues 说明未能查重'
           '（不是“无日期/学年写法”+“已整卷粗略比对”）', bool(ok), f'status={d.get("cohort_status") if d else None} '
           f'issues={d.get("issues") if d else None}', dt)

    # M-K：exam-id 模式下，原件为无文字层扫描件、只有 exams.csv 弱证据的卷 → 应为 NEEDS_LOCAL，不是
    # 靠 exams.csv 单独定届别的 WEAK_ONLY（回归 r1 M3 的状态）
    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2025-HD-ERMO', '--profile', str(PROFILE)])
    ok = (d and d['cohort_status'] == 'NEEDS_LOCAL' and d['cohort_year'] is None and d.get('suggestion') is None
          and not any(rf['has_text_layer'] for rf in (d.get('raw_files') or [])))
    record('10e M-K 修复：BJ-2025-HD-ERMO（扫描件，仅 exams.csv 弱证据）→ NEEDS_LOCAL、不给建议号'
           '（修复前由 exams.csv 单独定届别为 WEAK_ONLY）', bool(ok),
           f'status={d.get("cohort_status") if d else None} year={d.get("cohort_year") if d else None}', dt)

    # M-L：--files 新卷改号链里，本卷最终要接手的 want_id 如果在链中先被作为“旧号”重定向出去，
    # reused_ids 要把它纳入（修复前永远漏掉，因为它不进 redirects 的 new 列）
    new_cy2023 = make_docx('s10f_new_cy_2023_11_qizhong.docx',
                            ['北京市朝阳区2023～2024学年度第一学期期中质量检测', '高三思想政治试卷', '2023.11'],
                            FILLER_QS)
    code, d, err, dt = run_json(['check', '--files', str(new_cy2023), '--region', '朝阳', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = d and d.get('reused_ids') == ['BJ-2024-CY-QIZHONG']
    record('10f M-L 修复：--files 新卷（2023.11朝阳期中）改号链 → reused_ids 纳入本卷将接手的 '
           'BJ-2024-CY-QIZHONG（修复前 reused_ids=[]）', bool(ok), f'reused_ids={d.get("reused_ids") if d else None}', dt)

    # m1：两层链、末端 conflict（纯函数单测，不读题库）——redirects 应置空，note 应指向“第一步”
    occ = {
        'BJ-2024-XX': {'id_mismatch': {'registered_year': 2024, 'evidence_cohort_year': 2025},
                        'cohort_status': 'OK', 'cohort_year': 2025, 'duplicates': [],
                        'suggestion': {'suggested_id': 'BJ-2025-XX', 'occupied': True}},
        'BJ-2025-XX': {'id_mismatch': None, 'cohort_status': 'OK', 'cohort_year': 2025, 'duplicates': [],
                        'suggestion': {'suggested_id': 'BJ-2025-XX', 'occupied': False}},
    }
    r = er.build_rename_chain([], 'BJ-2024-XX', lambda x: occ.get(x), own_id=None)
    ok = r['kind'] == 'blocked_conflict' and r['redirects'] == [] and '第一步' in r['note']
    record('10g m1 修复：两层链末端 conflict → redirects 置空（修复前非空但 note 说“不给出重定向表”），'
           'note 指向 rename_plan 第一步（冲突点，不是最后一步）', ok, str(r))

    # m2：--debug 放在子命令前面也要生效（修复前子解析器的默认值会覆盖主解析器已解析出的 True）
    code, out, err, dt = run(['--debug', 'check', '--exam-id', 'BJ-2024-HD-QIZHONG', '--raw-root', '/no/such',
                               '--profile', str(PROFILE)])
    record('10h m2 修复：--debug 放在子命令前面也打印 traceback', 'Traceback' in err, err.strip()[-200:], dt)

    # m3/m4：--exam-dir 复制一份带 00_exam_front_matter.md 的卷（BJ-2026-CY-QIMO）——B 层要读到这份
    # 卷首说明文件（不是只读 README），total 应与 --exam-id 模式一致（21），不把工程文件也算进题数
    fm_dir = SCRATCH / 'examdir_front_matter'
    if fm_dir.exists():
        shutil.rmtree(fm_dir)
    shutil.copytree(BANK / 'questions' / 'BJ-2026-CY-QIMO', fm_dir)
    code, d, err, dt = run_json(['check', '--exam-dir', str(fm_dir), '--region', '朝阳', '--stage', '期末',
                                  '--profile', str(PROFILE)])
    ok = (d and d['cohort_status'] == 'OK' and d['cohort_year'] == 2026
          and (d.get('fingerprint_coverage') or {}).get('total') == 21)
    record('10i m3/m4 修复：--exam-dir 读到卷首说明文件 00_exam_front_matter.md（B 层证据，修复前只读'
           'README）、total=21 不含 5 个工程文件（修复前 26）', bool(ok),
           f'status={d.get("cohort_status") if d else None} coverage={d.get("fingerprint_coverage") if d else None}', dt)

    # m5：日期紧跟在“与本卷（……）”括注里，即使同一长句后文出现排除标记（针对另一份文件），也不能
    # 把本卷自己的日期一起排除掉——用 BJ-2023-HD-QIZHONG 的 README 真实原文单测 extract_year_signals
    text_m5 = ('共享库合并前登记在本卷名下的"原卷"文件——`path`——卷首原文是"海淀区2022—2023学年第二'
               '学期期中练习／高三思想政治 2023.04"，是2023年4月的一模（21题/100分），与本卷（2023年'
               '11月高三上期中，23题/100分）选择题答案序列完全不同，不是同一场考试，已正确归属到 '
               '`BJ-2023-HD-YIMO`，本包不再采用。')
    evs = er.extract_year_signals(text_m5, 'test', 'B', '期中')
    own_date_kept = any(e['kind'] == 'exam_date' and e['raw'] == '2023年11月' for e in evs)
    other_date_excluded = any(e['kind'] == 'exam_date_excluded_ref' and '2023' in e['raw'] and '4' in e['raw']
                               for e in evs)
    record('10j m5 修复：“与本卷（2023年11月……）”不被同句后文的排除标记误伤（仍算本卷证据），'
           '另一份文件的日期（2023.04）仍按排除处理', own_date_kept and other_date_excluded,
           f'evs={[(e["kind"], e.get("raw")) for e in evs]}')

    # m8：WEAK_ONLY 的 issue 文案不应再提“目录名”（D 层从不参与裁决）；用真实的、原件可读但无日期/
    # 学年写法、只靠 exams.csv 弱证据支持的卷（BJ-2025-DC-QIMO）
    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2025-DC-QIMO', '--profile', str(PROFILE)])
    issues_txt = ' '.join(d.get('issues') or []) if d else ''
    ok = (d and d['cohort_status'] == 'WEAK_ONLY' and 'exams.csv' in issues_txt and '目录名' not in issues_txt)
    record('10k m8 修复：真实 WEAK_ONLY 卷（BJ-2025-DC-QIMO）issue 文案只提 exams.csv，不再提“目录名”'
           '（D 层从不参与裁决）', bool(ok), f'status={d.get("cohort_status") if d else None} issues={d.get("issues") if d else None}', dt)

    # m9：Skill 模块 import 失败时要给中文提示、退出2，不是英文 traceback——用假的 BAODIAN_SKILL_
    # SCRIPTS 指向一个 docx_lib.py 会直接抛异常的目录，不碰真实 Skill 目录/依赖
    m9_copy_dir = SCRATCH / 'm9_probe'
    if m9_copy_dir.exists():
        shutil.rmtree(m9_copy_dir)
    m9_copy_dir.mkdir(parents=True)
    shutil.copy(TOOL, m9_copy_dir / 'exam_register.py')
    m9_fake_sk = SCRATCH / 'm9_fake_sk'
    if m9_fake_sk.exists():
        shutil.rmtree(m9_fake_sk)
    m9_fake_sk.mkdir(parents=True)
    (m9_fake_sk / 'docx_lib.py').write_text("raise ImportError('m9 探针：模拟环境缺依赖')\n", encoding='utf-8')
    env = dict(os.environ)
    env['BAODIAN_SKILL_SCRIPTS'] = str(m9_fake_sk)
    p = subprocess.run([sys.executable, '-B', str(m9_copy_dir / 'exam_register.py'), 'check',
                         '--exam-id', 'BJ-2026-HD-QIZHONG'], capture_output=True, text=True, timeout=60, env=env)
    ok = (p.returncode == 2 and 'Skill 依赖模块加载失败' in p.stderr and 'Traceback' not in p.stderr)
    record('10l m9 修复：Skill 模块 import 失败 → 中文提示、退出2、不打印英文 traceback（修复前模块级'
           'import 在 main() 的 try 之外，会抛原始 traceback）', ok, f'exit={p.returncode} err={p.stderr.strip()[:200]}')
    p2 = subprocess.run([sys.executable, '-B', str(m9_copy_dir / 'exam_register.py'), '--debug', 'check',
                          '--exam-id', 'BJ-2026-HD-QIZHONG'], capture_output=True, text=True, timeout=60, env=env)
    record('10l2 m9 对照：同一场景加 --debug 时打印 traceback', p2.returncode == 2 and 'Traceback' in p2.stderr,
           f'exit={p2.returncode}')

    # m11：exam-id 复核已登记的错号重复卷本身（BJ-2024-HD-QIZHONG）——应给出 retire own_id → want_id
    # 的 plan/redirect，不是空的 redirects
    code, d, err, dt = run_json(['check', '--exam-id', 'BJ-2024-HD-QIZHONG', '--profile', str(PROFILE)])
    plan = (d.get('rename_plan') or []) if d else []
    ok = (d and d.get('chain_kind') == 'already_registered' and plan and plan[0].get('old') == 'BJ-2024-HD-QIZHONG'
          and plan[0].get('retire_into') == 'BJ-2025-HD-QIZHONG'
          and d.get('redirects') == [{'old': 'BJ-2024-HD-QIZHONG', 'new': 'BJ-2025-HD-QIZHONG', 'after_step': 1}])
    record('10m m11 修复：exam-id 复核 BJ-2024-HD-QIZHONG 本身 → 给出 retire own_id→BJ-2025-HD-QIZHONG '
           '的 plan/redirect（修复前 redirects=[]）', bool(ok), f'plan={plan} redirects={d.get("redirects") if d else None}', dt)

    # m12：建议号未被占用、但候选与某已有卷可靠重复时，suggestion 要带 already_registered_as
    code, d, err, dt = run_json(['check', '--files', str(cy24a), '--region', '朝阳', '--stage', '期中',
                                  '--profile', str(PROFILE)])
    ok = d and (d.get('suggestion') or {}).get('already_registered_as') == 'BJ-2024-CY-QIZHONG'
    record('10n m12 修复：2024朝阳期中新卷（建议号未占用但与 BJ-2024-CY-QIZHONG 可靠重复）→ suggestion '
           '带 already_registered_as（修复前建议号被表述成“可用的新登记”）', bool(ok),
           f'suggestion={d.get("suggestion") if d else None}', dt)


def main():
    setup()
    t0 = time.time()
    baseline_check('测试前')
    for grp in (group1, group2, group3, group4, group5, group6, group7, group8, group9, group10):
        grp()
    baseline_check('测试后')
    dt = time.time() - t0
    total = len(results)
    failed = [r for r in results if not r['ok']]
    print(f'\n合计 {total} 条，失败 {len(failed)} 条，用时 {dt:.1f}s')
    (BUILD_OUT / 'test_results.json').write_text(
        json.dumps({'total': total, 'failed': len(failed), 'seconds': round(dt, 1), 'results': results},
                    ensure_ascii=False, indent=1), encoding='utf-8')
    return len(failed)


if __name__ == '__main__':
    sys.exit(main())
