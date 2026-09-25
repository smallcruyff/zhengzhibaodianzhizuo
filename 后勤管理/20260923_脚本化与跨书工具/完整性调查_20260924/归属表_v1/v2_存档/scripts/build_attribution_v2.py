#!/usr/bin/env python3
"""build_attribution_v2.py —— 修复对抗审查 blocker①②(部分)③(部分) 与 major③ 后的题级/小问级归属表。

相对 v1 (build_attribution.py) 的关键变更（详见 审查意见.json / 返修回执_v2.json）：
  1. 证据判定改为逐题（question_id 粒度）用 rubric_links.csv 的 pair_status + material_kind 精确判断，
     去掉“同卷任一行 exam_rubric_status 已匹配就整卷继承”的卷级回退。
  2. 证据状态四分：E1(已匹配正式材料) / E3(仅已匹配参考答案) / 缺证据-已核实(有明确“不覆盖本题”负例记录)
     / 缺证据-未核实(题库里根本没有该题的 rubric_links 行，不能证明“确认没有”)。
     若同一题同时存在“存在候选”或“存在冲突”的正式材料候选行、且没有已匹配正式材料行，
     一律落到 admission=待裁决-证据未核实（不收也不丢，留在候选队列），不再机械判“不收”或“已收”。
  3. 叠加 skill_overrides.json 里逐条带 Skill/宪法/exams.csv 原文出处的覆盖判断（具名例外、题库线缺口），
     且例外按 scope 精确到题/小问，不再对整卷广播。
  4. 归属_<模块> 的 COLLECTED 判断改为同时看 matrix.csv 当前题的收录列 **和** dup_covered_by
     （身份层已给出的题级等价类），修复别名孪生题产生的假漏收（blocker③核心机制部分）。
  5. 只在汇编中出现的卷（exam_identity.json 里 status=compilation_only_*）用 assembly_blocks.csv
     生成候选行：选择题照收，主观题固定标“待裁决-证据未核实”（major①）。
  6. content_fingerprint 去除固定样板前缀后再取全文哈希，subq 行把 subq 编号并入哈希输入，避免碰撞和空值。
  7. BJ-2025-FT-YIMO-Q18 标记为切分错误产生的伪选择题（题库把 Q12 的 BMI 表尾部与另一题选项拼成假题），
     不计入选择题“照收”分母，只登记 identity 层 qid_redirect，供回传题库线。

用法：
  python3 build_attribution_v2.py --identity exam_identity.json --overrides skill_overrides.json \
      --out attribution.csv --options-out attribution_options.csv
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, hashlib, json, re
from pathlib import Path
from collections import defaultdict

REVIEW_DIR = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924')
CLASSIFIER = Path('/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/completeness/classifier')
BANK = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918')

MODS = ['B1', 'B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']
MOD_TO_MATRIXCOL = {'B2': 'bixiu2', 'B3': 'bixiu3', 'PH': 'philosophy', 'CU': 'culture',
                    'X1': 'xuanbi1', 'X2': 'xuanbi2', 'MI': 'mind', 'RE': 'reasoning'}
RULE_VERSION = '2026-09-24-attribution-v2'

BOILERPLATE = '本节只放原卷角色的原生文字层；OCR 候选与其它角色另列下方各节。'

# rubric_links.csv material_kind 里明确“已检查、本题不适用”的负例（不是“没查过”）
NEG_KINDS_SUBJ = {'同卷正式细则无本题内容', '同卷PPT无本题评分内容'}
NEG_KINDS_CHOICE = {'无逐题E1；选项分布不作答案键', '主观题细则不覆盖本选择题', '正式细则不覆盖选择题'}
AMBIGUOUS_PAIR = {'存在候选', '存在冲突'}
EXCLUDED_PAIR = {'已排除', '已排除（文件名指向他题）'}


def read_jsonl(p):
    out = []
    with open(p, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def read_csv(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def fp(text, subq=''):
    if not text:
        return ''
    norm = text.replace(BOILERPLATE, '')
    norm = ''.join(norm.split())
    if not norm:
        return ''
    if subq:
        norm = norm + '#SUBQ' + str(subq)
    return hashlib.sha1(norm.encode('utf-8')).hexdigest()[:16]


def load_identity(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    exams = d['exams']
    canon = {}
    named_exc = {}
    comp_only = {}
    qid_redirects = d.get('qid_redirects', {})
    for eid, e in exams.items():
        if e.get('canonical_of'):
            canon[eid] = e['canonical_of']
        if e.get('named_exceptions'):
            named_exc[eid] = e['named_exceptions']
        if str(e.get('status', '')).startswith('compilation_only'):
            comp_only[eid] = e
    return d, exams, canon, named_exc, comp_only, qid_redirects


def load_overrides(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    by_exam = defaultdict(list)
    for o in d.get('overrides', []):
        by_exam[o['exam_id']].append(o)
    return by_exam


def build_rubric_index(bank):
    """question_id -> 该题在 rubric_links.csv 里的全部行（逐题，不做卷级聚合/回退）。"""
    rows = read_csv(bank / 'indexes/rubric_links.csv')
    by_q = defaultdict(list)
    for r in rows:
        by_q[r.get('question_id', '')].append(r)
    return by_q


def eval_rubric_rows(rows, typ):
    """对同一 question_id 的全部 rubric_links 行做逐题判定（不看同卷其它题）。
    返回 (evidence, evidence_detail, ambiguous_bool)。"""
    if not rows:
        return ('缺细则' if typ != '选择题' else '缺答案键'), '未在rubric_links.csv找到该题任何行(未核实,不是已确认无)', False

    e1 = any(r.get('material_kind') == '正式评分材料' and r.get('pair_status') == '已匹配正式材料' for r in rows)
    e3 = any(r.get('material_kind') == '参考答案' and r.get('pair_status') == '已匹配参考答案' for r in rows)
    ambiguous = any(
        r.get('material_kind') == '正式评分材料' and (
            r.get('pair_status') in AMBIGUOUS_PAIR or r.get('exam_rubric_status') == '存在冲突'
        ) for r in rows
    )
    neg_kinds = NEG_KINDS_SUBJ if typ != '选择题' else NEG_KINDS_CHOICE
    confirmed_negative = any(r.get('material_kind') in neg_kinds for r in rows)

    if e1:
        return 'E1', '逐题已匹配正式评分材料', False
    if ambiguous:
        detail = '该题正式评分材料候选存在候选/存在冲突，未确认匹配，不下判'
        if typ != '选择题':
            return '待裁决-证据未核实候选', detail, True
        if e3:
            return 'E3', detail + '（同时已有匹配参考答案，选择题按E3计，正式评分材料候选仍待核实）', True
        return '答案键来源未核实(候选未确认)', detail, True
    if e3:
        return 'E3', '逐题已匹配参考答案', False
    if confirmed_negative:
        base = '缺细则-已核实' if typ != '选择题' else '缺答案键-已核实'
        return base, '题库rubric_links.csv对该题有明确负例记录(已检查,本题不适用)', False
    base = '缺细则' if typ != '选择题' else '缺答案键'
    return base, '该题在rubric_links.csv里有行但均为已排除/无关状态', False


def parse_scope_num_subq(scope):
    m = re.match(r'Q(\d+)(?:\((\d+)\))?', scope or '')
    if not m:
        return None, None
    return int(m.group(1)), m.group(2)


def override_for(overrides_by_exam, exam, exam_canon, num, subq, typ):
    for eid in (exam, exam_canon):
        for o in overrides_by_exam.get(eid, []):
            if o['scope'] == 'all_subjective':
                if typ != '选择题':
                    return o
                continue
            if o['scope'] in ('Q1-Q20',):
                lo, hi = 1, 20
                if num is not None and lo <= int(num) <= hi:
                    return o
                continue
            o_num, o_subq = parse_scope_num_subq(o['scope'])
            if o_num is not None and int(num) == o_num:
                if o_subq is None or str(subq) == str(o_subq):
                    return o
    return None


def load_assembly_candidates(bank, comp_only, exams_identity):
    """只在汇编中出现的卷：从 assembly_blocks.csv 生成候选行（缺行，非分类器产物）。
    选择题照收；主观题固定 待裁决-证据未核实（按纳入范围裁定②与用户2026-09-24补充裁定）。
    题号/题型只能用汇编标注文本粗略推断，标注在 note 里，供人工核实，不冒充分类器判定。"""
    if not comp_only:
        return []
    asm_rows = read_csv(bank / 'indexes/assembly_blocks.csv')
    by_exam = defaultdict(list)
    for r in asm_rows:
        eid = (r.get('matched_exam_id') or '').strip()
        if eid in comp_only:
            by_exam[eid].append(r)

    out = []
    for eid, rows in by_exam.items():
        seen_num = set()
        for r in rows:
            ev = r.get('evidence', '') + ' ' + r.get('preview', '')
            m = re.search(r'(?:一模|二模|期中|期末)\s*）?\s*(\d+)', ev)
            num = m.group(1) if m else None
            chars = int(r.get('chars') or 0)
            preview = r.get('preview', '')
            is_subj = bool(re.search(r'\(\d+分\)|（\d+分）|结合材料|运用.*知识', preview)) or chars > 500
            typ = '主观题' if is_subj else '选择题'
            key = (num, typ)
            if num and key in seen_num:
                continue
            if num:
                seen_num.add(key)
            qid = f'{eid}-Q{num}' if num else f'{eid}-BLOCK{r["block_index"]}'
            out.append({
                'unit_id': qid, 'qid': qid, 'exam_id_raw': eid, 'exam_id_canonical': eid,
                'num': num or '', 'type': typ, 'subq': '', 'grain': '整题',
                'content_fingerprint': fp(preview),
                'script_tier': '汇编候选-未分类器处理',
                **{('归属_' + m): 'MAYBE' for m in MODS},
                'admission': ('完整题-选择题照收' if typ == '选择题' else '待裁决-证据未核实'),
                'evidence': '汇编片段(assembly_blocks.csv)，原卷/正式评分载体尚未取得',
                'downgrade_notes': 'assembly_only_unclassified：题号/题型由汇编标注文本粗略推断，未经classify.py九模块判定，全部模块列MAYBE，需人工/模型核实模块归属',
                'dup_of': '', 'dup_covered_by': '', 'conflict_script_out': '',
                'rule_version': RULE_VERSION,
                'source': f'assembly_blocks.csv:{r.get("assembly_id","")}#{r.get("block_index","")}',
            })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--identity', default='exam_identity.json')
    ap.add_argument('--overrides', default='skill_overrides.json')
    ap.add_argument('--out', default='attribution.csv')
    ap.add_argument('--options-out', default='attribution_options.csv')
    a = ap.parse_args()

    classified = read_jsonl(CLASSIFIER / 'classified_prod.jsonl')
    units = read_jsonl(CLASSIFIER / 'units.jsonl')
    stem_by_qid = {u['qid']: u.get('stem', '') for u in units}
    matrix_rows = read_csv(REVIEW_DIR / 'matrix.csv')
    matrix_by_qid = {r['qid']: r for r in matrix_rows}
    identity_doc, exams_identity, canon_map, named_exc, comp_only, qid_redirects = load_identity(a.identity)
    overrides_by_exam = load_overrides(a.overrides)
    rubric_by_q = build_rubric_index(BANK)

    out_rows = []
    opt_rows = []
    stat = defaultdict(int)

    for u in classified:
        qid = u['qid']
        exam = u.get('exam', qid.rsplit('-Q', 1)[0])
        exam_canon = canon_map.get(exam, exam)
        subq = u.get('subq') or ''
        typ = u['type']
        state = u['state']
        ev = u.get('ev', {})
        mrow = matrix_by_qid.get(qid, {})
        stem = stem_by_qid.get(qid, '')
        content_fp = fp(stem, subq)
        redirect = qid_redirects.get(qid)

        # ---- 归属_<模块> 列（含 dup_covered_by 等价类合并，修复别名孪生题假漏收） ----
        mod_cols = {}
        downgrades = []
        dup_covered_mods = set((mrow.get('dup_covered_by') or '').split(';')) - {''}
        for m in MODS:
            st = state.get(m, 'MAYBE')
            book = MOD_TO_MATRIXCOL.get(m)
            collected = bool(book and (mrow.get(book) or book in dup_covered_mods))
            if collected:
                mod_cols[m] = 'COLLECTED'
            elif st == 'OUT':
                if typ == '主观题' and ev.get('rubric_readable') is False:
                    mod_cols[m] = 'MAYBE'
                    downgrades.append(f'{m}:rubric_unreadable_not_OUT')
                else:
                    mod_cols[m] = 'OUT'
            else:
                mod_cols[m] = st  # IN / MAYBE
        if dup_covered_mods:
            downgrades.append('identity:dup_covered_by=' + ';'.join(sorted(dup_covered_mods)) + '(等价类合并生效)')

        # ---- 证据/准入：先查 skill_overrides（逐题/逐小问出处覆盖），否则逐题查 rubric_links ----
        ovr = override_for(overrides_by_exam, exam, exam_canon, u.get('num'), subq, typ)
        if ovr:
            evidence = ovr['evidence']
            evidence_detail = ovr.get('evidence_detail', '') + ' | ' + '; '.join(ovr.get('cite', []))
            admission = ovr['admission']
        elif redirect and redirect.get('exclude_from_admission'):
            evidence = '身份层标记:' + redirect.get('kind', 'split_error')
            evidence_detail = redirect.get('note', '')
            admission = '身份错误-不计入分母'
        else:
            evidence, evidence_detail, _amb = eval_rubric_rows(rubric_by_q.get(qid, []), typ)
            if typ == '选择题':
                admission = '完整题-选择题照收'
            else:
                if evidence == 'E1':
                    admission = '完整题-有E1'
                elif evidence == '待裁决-证据未核实候选':
                    admission = '待裁决-证据未核实'
                elif evidence in ('E3', '缺细则', '缺细则-已核实'):
                    admission = '不收-无E1'
                else:
                    admission = '待裁决-证据未核实'

        row = {
            'unit_id': qid + (('#' + subq) if subq else ''),
            'qid': qid,
            'exam_id_raw': exam,
            'exam_id_canonical': exam_canon,
            'num': u.get('num'),
            'type': typ,
            'subq': subq,
            'grain': ('小问' if subq else '整题'),
            'content_fingerprint': content_fp,
            'script_tier': u.get('tier', ''),
            'admission': admission,
            'evidence': evidence,
            'evidence_detail': evidence_detail,
            'downgrade_notes': ';'.join(downgrades),
            'dup_of': mrow.get('dup_of', ''),
            'dup_covered_by': mrow.get('dup_covered_by', ''),
            'conflict_script_out': ';'.join(ev.get('e_conflict_script_out', [])),
            'identity_redirect': (redirect.get('kind') if redirect else ''),
            'rule_version': RULE_VERSION,
            'source': 'classify.py:classified_prod.jsonl+matrix.csv+exam_identity.json+skill_overrides.json',
        }
        for m in MODS:
            row['归属_' + m] = mod_cols[m]
        out_rows.append(row)
        stat['rows'] += 1
        if admission.startswith('不收'):
            stat['not_admit'] += 1
        elif admission.startswith('待裁决'):
            stat['pending'] += 1
        elif admission.startswith('身份错误'):
            stat['identity_error_excluded'] += 1
        else:
            stat['admit'] += 1

        # ---- 题肢级辅助表（仅选择题；弱信号，仅词典命中，不构成准入依据）----
        if typ == '选择题':
            d_options = ev.get('d_options') or {}
            for mark, hit_mods in d_options.items():
                opt_rows.append({
                    'qid': qid,
                    'option_mark': mark,
                    'dict_hit_modules': ';'.join(hit_mods),
                    'c_prior_top_module': max(ev.get('c_prior', {}), key=ev.get('c_prior', {}).get) if ev.get('c_prior') else '',
                    'note': '仅词典命中弱信号(精度约0.66-0.88)，不构成准入依据；本册是否可独立判断整个题肢、官方正误需模型/人工阶段核定',
                    'rule_version': RULE_VERSION,
                })

    # ---- 只在汇编中出现的卷：补候选行（major①）----
    asm_candidates = load_assembly_candidates(BANK, comp_only, exams_identity)
    out_rows.extend(asm_candidates)
    stat['assembly_only_rows'] = len(asm_candidates)
    for r in asm_candidates:
        stat['rows'] += 1
        if r['admission'].startswith('待裁决'):
            stat['pending'] += 1
        else:
            stat['admit'] += 1

    fieldnames = (['unit_id', 'qid', 'exam_id_raw', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                   'content_fingerprint', 'script_tier'] +
                  ['归属_' + m for m in MODS] +
                  ['admission', 'evidence', 'evidence_detail', 'downgrade_notes', 'dup_of', 'dup_covered_by',
                   'conflict_script_out', 'identity_redirect', 'rule_version', 'source'])
    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        for r in out_rows:
            for k in fieldnames:
                r.setdefault(k, '')
            w.writerow(r)

    opt_fields = ['qid', 'option_mark', 'dict_hit_modules', 'c_prior_top_module', 'note', 'rule_version']
    with open(a.options_out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=opt_fields)
        w.writeheader()
        w.writerows(opt_rows)

    print(f"attribution rows={stat['rows']} (含+{stat['assembly_only_rows']} 汇编候选) "
          f"admit={stat['admit']} not_admit(不收)={stat['not_admit']} "
          f"pending(待裁决)={stat['pending']} identity_error_excluded={stat['identity_error_excluded']} "
          f"option_rows={len(opt_rows)}")


if __name__ == '__main__':
    main()
