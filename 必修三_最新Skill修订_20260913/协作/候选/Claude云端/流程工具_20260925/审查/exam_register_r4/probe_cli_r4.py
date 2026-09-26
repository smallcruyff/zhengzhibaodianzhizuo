#!/usr/bin/env python3
"""r4 审查 CLI 探针（只读真实输入；合成件与报告只写 scratchpad/review_exam_register_r4/）。
用法：python3 -B probe_cli_r4.py <out.json> [探针名 ...]"""
import sys
sys.dont_write_bytecode = True
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
TOOL = C / 'exam_register.py'
PROFILE = C / 'profiles_cloud' / 'bixiu3.json'
FROZEN = C / 'profiles_cloud' / 'bixiu2_frozen_test.json'
REPO = C.parents[4]
BANK = REPO / 'DeepSeek_政治题库资料库_20260918'
RAW = REPO / '00_共同资料' / '原材料'
SP = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_exam_register_r4')
SP.mkdir(parents=True, exist_ok=True)

FILLER = [
    '某市推行“接诉即办”改革，市民热线诉求当天响应、限期办结，并将办理结果纳入部门考核。这一做法'
    '①坚持以人民为中心的发展思想②说明政府职能已经由管理转向服务③有利于提高政府的公信力和执行力'
    '④表明群众可以直接决定政府的施政方向A．①②B．①③C．②④D．③④',
    '某县探索“党建引领、村民议事、乡贤助力”的乡村治理模式，村内公共事务由村民议事会讨论决定。这一模式'
    '①丰富了基层民主的实现形式②改变了村民委员会的性质③有利于调动村民参与治理的积极性④说明村民议事会是基层政权组织'
    'A．①③B．①④C．②③D．②④',
    '某省人大常委会在制定地方性法规过程中，通过基层立法联系点广泛收集群众意见，并对意见采纳情况予以反馈。这体现了'
    '①全过程人民民主的实践②地方人大享有国家立法权③科学立法、民主立法的要求④人民群众直接行使立法权'
    'A．①③B．①④C．②③D．②④',
]


def run(args, env=None, timeout=300):
    t0 = time.time()
    p = subprocess.run([sys.executable, '-B', str(TOOL)] + [str(a) for a in args], capture_output=True, text=True,
                       timeout=timeout, env=env)
    try:
        js = json.loads(p.stdout)
    except Exception:
        js = None
    return {'args': [str(a) for a in args], 'exit': p.returncode, 'json': js, 'stdout_head': p.stdout[:300] if js is None else None,
            'stderr': p.stderr[-800:], 'seconds': round(time.time() - t0, 1)}


def short(r):
    j = r['json'] or {}
    keep = {k: j.get(k) for k in ('exam_id', 'cohort_year', 'cohort_status', 'suggestion', 'chain_kind', 'rename_plan',
                                  'redirects', 'reused_ids', 'duplicates', 'fingerprint_coverage', 'issues')}
    return {'exit': r['exit'], 'stderr': r['stderr'][-300:], **keep}


def make_docx(path, header, qs, numfmt='{n}．'):
    import docx
    d = docx.Document()
    for h in header:
        d.add_paragraph(h)
    for i, q in enumerate(qs):
        d.add_paragraph(numfmt.format(n=i + 1) + q)
    d.save(str(path))
    return path


P = {}


def probe(fn):
    P[fn.__name__] = fn
    return fn


@probe
def N1_real_hd2023_yimo_decimal_table():
    """真实原件 BJ-2023-HD-YIMO 原卷（21 题全部切对，但材料里有“68.5%”数据行）当新卷输入。"""
    f = RAW / '2023模拟题/2023各区模拟题(1)/各区一模/海淀/2022-2023年第二学期高三政治期中试题(3).pdf'
    return short(run(['check', '--files', f, '--region', '海淀', '--stage', '一模', '--profile', PROFILE]))


@probe
def N2_real_cy2026_ermo_teacher_decimal_table():
    f = RAW / '2026模拟题/2026各区二模/2026朝阳二模/试卷/2026北京朝阳高三二模政治（教师版）.docx'
    return short(run(['check', '--files', f, '--region', '朝阳', '--stage', '二模', '--profile', PROFILE]))


@probe
def N3_examid_correct_hd2025_already_registered_as():
    r = run(['check', '--exam-id', 'BJ-2025-HD-QIZHONG', '--profile', PROFILE])
    return short(r)


@probe
def N4_files_hd25_already_registered_as():
    f = RAW / '2025模拟题/2025各区期末/2025海淀期中/试卷/试卷.pdf'
    return short(run(['check', '--files', f, '--region', '海淀', '--stage', '期中', '--profile', PROFILE]))


@probe
def N5_examdir_nonstandard_qfile_names():
    """刚产出的逐题目录，文件名不是 <卷号>-Q<n>.md（如 Q1.md / 第1题.md）：内容是 BJ-2024-HD-QIZHONG 的逐题 MD。"""
    dst = SP / 'examdir_q_names'
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    src = BANK / 'questions' / 'BJ-2024-HD-QIZHONG'
    for p in sorted(src.glob('BJ-2024-HD-QIZHONG-Q*.md')):
        n = p.stem.split('-Q')[-1]
        shutil.copy(p, dst / f'Q{n}.md')
    return short(run(['check', '--exam-dir', dst, '--region', '海淀', '--stage', '期中', '--profile', PROFILE]))


@probe
def N5b_examdir_standard_names_control():
    dst = SP / 'examdir_q_names_ctrl'
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    src = BANK / 'questions' / 'BJ-2024-HD-QIZHONG'
    for p in sorted(src.glob('BJ-2024-HD-QIZHONG-Q*.md')):
        shutil.copy(p, dst / p.name.replace('BJ-2024-HD-QIZHONG', 'NEW-EXAM'))
    return short(run(['check', '--exam-dir', dst, '--region', '海淀', '--stage', '期中', '--profile', PROFILE]))


@probe
def N6_examdir_only_front_matter():
    dst = SP / 'examdir_fm_only'
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    shutil.copy(BANK / 'questions' / 'BJ-2026-CY-QIMO' / '00_exam_front_matter.md', dst / '00_exam_front_matter.md')
    return short(run(['check', '--exam-dir', dst, '--region', '朝阳', '--stage', '期末', '--profile', PROFILE]))


@probe
def N7_files_all_chunks_short():
    """有可读文字层、题号切分正常（>=3 块），但每块归一化后都短于 MIN_STEM_LEN（如只有答案表/题面为图片）。"""
    p = make_docx(SP / 'n7_answer_key.docx', ['海淀区2026—2027学年第一学期期中练习', '高三思想政治参考答案', '2026.11'],
                  ['B', 'C', 'A', 'D', 'B', 'C', 'A', 'D', 'B', 'C', 'A', 'D', 'B', 'C', 'A'])
    return short(run(['check', '--files', p, '--region', '海淀', '--stage', '期中', '--profile', PROFILE]))


@probe
def N8_frozen_profile_readonly():
    r = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', FROZEN])
    return {'exit': r['exit'], 'stderr': r['stderr'][-300:], 'has_json': r['json'] is not None}


@probe
def N9_guard_variants():
    out = {}
    cases = {
        'traversal_构建_to_回执': C / '构建' / '..' / '回执' / 'r4_probe.json',
        'candidate_root': C / 'r4_probe.json',
        'txt_suffix_in_构建': C / '构建' / 'exam_register' / 'r4_probe.txt',
        'raw_root': RAW / 'r4_probe.json',
        'other_book_dir': REPO / '其他书工作头' / 'r4_probe.json',
        'cloud_dir': REPO / '云端' / 'r4_probe.json',
    }
    link = SP / 'link_to_skill'
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(REPO / '.claude' / 'skills' / 'beijing-gaokao-politics')
    cases['symlink_to_skill_noprofile'] = link / 'r4_probe.json'
    for name, target in cases.items():
        args = ['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', target]
        if name != 'symlink_to_skill_noprofile':
            args += ['--profile', PROFILE]
        r = run(args)
        real = Path(os.path.realpath(target))
        wrote = real.exists()
        if wrote and 'scratchpad' not in str(real):
            real.unlink()
        out[name] = {'exit': r['exit'], 'wrote': wrote, 'stderr': r['stderr'][-200:]}
    link.unlink()
    # 合法位置
    ok_t = SP / 'ok_report.json'
    r = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', ok_t, '--profile', PROFILE])
    rep = json.loads(ok_t.read_text(encoding='utf-8')) if ok_t.is_file() else None
    out['scratch_ok'] = {'exit': r['exit'], 'wrote': ok_t.is_file(),
                         'keys': sorted(rep.keys()) if rep else None,
                         'inputs': rep.get('inputs') if rep else None,
                         'thresholds': rep.get('thresholds') if rep else None}
    # 报告落到不存在的父目录（原子性：失败时不留半成品）
    r = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--report', SP / 'no_such_dir' / 'x.json', '--profile', PROFILE])
    out['missing_parent'] = {'exit': r['exit'], 'stderr': r['stderr'][-200:], 'dir_created': (SP / 'no_such_dir').exists()}
    return out


@probe
def N10_scanned_examid_exit_and_text():
    return short(run(['check', '--exam-id', 'BJ-2026-HD-YIMO', '--profile', PROFILE]))


@probe
def N11_examid_bj2023_hd_qizhong():
    return short(run(['check', '--exam-id', 'BJ-2023-HD-QIZHONG', '--profile', PROFILE]))


@probe
def N12_decimal_table_synthetic_dup():
    """合成：把 BJ-2026-HD-QIZHONG 全部采用题面做成“新卷”（真实重复登记），只在第 2 题材料里加一行以
    “35.6%”开头的数据表行——看 duplicate_registration 是否因 M-I 新信号被降级。"""
    sys.path.insert(0, str(C))
    import exam_register as er
    T, _ = er.load_bank_alias_tables(BANK)
    stems = []
    for p in sorted((BANK / 'questions' / 'BJ-2026-HD-QIZHONG').glob('BJ-2026-HD-QIZHONG-Q*.md'),
                    key=lambda x: int(x.stem.split('-Q')[-1])):
        s, _b = er.extract_stem_from_md(p.read_text(encoding='utf-8'), T)
        stems.append(s.replace('\n', ' '))
    import docx
    out = {}
    for label, inject in (('no_table', False), ('with_table_line', True)):
        d = docx.Document()
        for h in ['北京市海淀区2026—2027学年第一学期期中练习', '高三思想政治', '2026.11']:
            d.add_paragraph(h)
        for i, s in enumerate(stems):
            d.add_paragraph(f'{i + 1}．{s}')
            if inject and i == 1:
                d.add_paragraph('指标 2024年 2025年')
                d.add_paragraph('35.6% 41.2%')
        fp = SP / f'n12_{label}.docx'
        d.save(str(fp))
        r = run(['check', '--files', fp, '--region', '海淀', '--stage', '期中', '--profile', PROFILE])
        j = r['json'] or {}
        out[label] = {'exit': r['exit'], 'duplicates': j.get('duplicates'), 'chain_kind': j.get('chain_kind'),
                      'suggestion': j.get('suggestion'), 'issues': j.get('issues')}
    return out


@probe
def N13_debug_positions():
    a = run(['--debug', 'check', '--exam-id', 'BJ-NOPE', '--profile', PROFILE])
    b = run(['check', '--exam-id', 'BJ-NOPE', '--profile', PROFILE])
    c = run(['check', '--exam-id', 'BJ-2026-HD-QIZHONG', '--profile', PROFILE, '--bank', '/no/such'])
    return {'debug_before': {'exit': a['exit'], 'tb': 'Traceback' in a['stderr']},
            'no_debug': {'exit': b['exit'], 'tb': 'Traceback' in b['stderr'], 'stderr': b['stderr'][-200:]},
            'bad_bank': {'exit': c['exit'], 'tb': 'Traceback' in c['stderr'], 'stderr': c['stderr'][-200:]}}


@probe
def N14_audit_report():
    t = SP / 'audit_r4.json'
    r = run(['audit', '--profile', PROFILE, '--report', t], timeout=600)
    rep = json.loads(t.read_text(encoding='utf-8'))
    items = rep['items']
    by = {}
    for it in items:
        by.setdefault(it.get('cohort_status'), []).append(it['exam_id'])
    ev_nl = {}
    for it in items:
        if it.get('cohort_status') in ('NEEDS_LOCAL', 'WEAK_ONLY'):
            ev_nl[it['exam_id']] = {'status': it['cohort_status'], 'weak_hint': it.get('cohort_weak_hint'),
                                    'raw': [(Path(x['path']).name, x['has_text_layer'], x.get('readable_ratio'))
                                            for x in it.get('raw_files', [])],
                                    'issues': it['issues'][:2]}
    r3_13 = ['BJ-2023-DC-ERMO', 'BJ-2023-DC-YIMO', 'BJ-2024-DC-ERMO', 'BJ-2024-DC-YIMO', 'BJ-2025-HD-ERMO',
             'BJ-2026-CY-QIMO', 'BJ-2026-FS-YIMO', 'BJ-2026-FT-QIMO', 'BJ-2026-FT-YIMO', 'BJ-2026-HD-YIMO',
             'BJ-2026-SJS-QIMO', 'BJ-2026-SY-ERMO', 'BJ-2026-TZ-YIMO']
    moved = {}
    for eid in r3_13:
        it = next(x for x in items if x['exam_id'] == eid)
        ok_ev = [(e['tier'], e['kind'], e['raw'], Path(e['source']).name if '/' in e['source'] else e['source'])
                 for e in it['evidence'] if e.get('cohort_year') is not None and e['tier'] in 'AB']
        moved[eid] = {'status': it['cohort_status'], 'cohort': it['cohort_year'], 'AB_evidence': ok_ev[:4]}
    return {'exit': r['exit'], 'summary': rep['summary'], 'by_status': {k: (len(v), v if k != 'OK' else None) for k, v in by.items()},
            'nl_wo_detail': ev_nl, 'r3_13_now': moved}


@probe
def N7b_files_readable_but_all_chunks_short():
    """有可读中文文字层、题号 1..15 切分正常（reliable），但每块归一化后都短于 MIN_STEM_LEN——
    例如题面主体是图片、文字层只剩题号和一句设问；questions 为空时看是否明说“查重未执行”。"""
    qs = ['下列说法正确的是（图略）', '对此理解正确的是（图略）', '这表明（材料见图）', '由此可见（图表略）',
          '下列选项正确的是（图略）'] * 3
    p = make_docx(SP / 'n7b_short_chunks.docx', ['北京市海淀区2026—2027学年第一学期期中练习', '高三思想政治', '2026.11'], qs)
    return short(run(['check', '--files', p, '--region', '海淀', '--stage', '期中', '--profile', PROFILE]))


@probe
def N5c_examdir_nonstandard_names_with_readme_exit0():
    """BJ-2024-CY-QIZHONG 的 README + 逐题 MD，逐题文件名改为 Q<n>.md（非 <卷号>-Q<n>.md）；
    对照组 N5d 用标准文件名。内容与题库 BJ-2024-CY-QIZHONG 完全相同，应拦为重复登记。"""
    out = {}
    src = BANK / 'questions' / 'BJ-2024-CY-QIZHONG'
    for label, namer in (('nonstandard_Qn', lambda n: f'Q{n}.md'), ('standard', lambda n: f'NEW-CY-Q{n}.md')):
        dst = SP / f'examdir_cy_{label}'
        if dst.exists():
            shutil.rmtree(dst)
        dst.mkdir(parents=True)
        shutil.copy(src / 'README.md', dst / 'README.md')
        for p in sorted(src.glob('BJ-2024-CY-QIZHONG-Q*.md')):
            n = p.stem.split('-Q')[-1]
            shutil.copy(p, dst / namer(n))
        out[label] = short(run(['check', '--exam-dir', dst, '--region', '朝阳', '--stage', '期中', '--profile', PROFILE]))
    return out


@probe
def N15_reregister_ocr_stem_exams():
    """把题库在册卷的真实原件当新卷再登记一次（真实的重复登记），对手卷题面多为 OCR 候选节（fallback_low_confidence）。"""
    out = {}
    for label, f, region, stage in (
            ('HD-ERMO-2026', RAW / '2026模拟题/2026各区二模/2026海淀二模/试卷/2026北京海淀高三二模政治（教师版）.docx', '海淀', '二模'),
            ('XC-ERMO-2026', RAW / '2026模拟题/2026各区二模/2026西城二模/试卷/2026北京西城高三二模政治（教师版）.docx', '西城', '二模'),
            ('GAOKAO-2024', RAW / '历年高考题及细则/2024北京高考真题政治（教师版）.pdf', None, '高考')):
        args = ['check', '--files', f, '--stage', stage, '--profile', PROFILE]
        if region:
            args += ['--region', region]
        out[label] = short(run(args))
    return out


if __name__ == '__main__':
    outp = Path(sys.argv[1])
    names = sys.argv[2:] or list(P)
    res = json.loads(outp.read_text(encoding='utf-8')) if outp.is_file() else {}
    for n in names:
        t0 = time.time()
        try:
            res[n] = P[n]()
        except Exception as e:
            res[n] = {'probe_error': repr(e)}
        print(n, round(time.time() - t0, 1), json.dumps(res[n], ensure_ascii=False)[:1500], flush=True)
        outp.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
