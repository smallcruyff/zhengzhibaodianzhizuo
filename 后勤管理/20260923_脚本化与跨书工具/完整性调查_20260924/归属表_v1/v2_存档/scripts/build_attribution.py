#!/usr/bin/env python3
"""build_attribution.py —— 题级/小问级模块归属表（缺口2）。只读，零模型token。

复用（不改）:
  分类器产物 classifier/classified_prod.jsonl（uid、subq、九模块三态 state、证据 ev、tier）——已含信号e（书稿已收）
  分类器产物 classifier/units.jsonl（stem 全文，用于内容指纹）
  coverage.py 产物 matrix.csv（各书 S/F/M 收录层级、dup_of/dup_covered_by 等价类）
  题库 indexes/rubric_links.csv、indexes/questions.csv（E1/E3 证据判定）
  本表 exam_identity.json（卷别名重定向、具名例外、身份状态）

三列分开（每条判断都带 rule_version）：
  归属_<模块>   9列，值取 {COLLECTED, IN, OUT, MAYBE}；已收的一律标 COLLECTED（“已收待复核”）而不是“已定”。
  准入         {完整题-选择题照收 / 完整题-有E1 / 收-具名例外 / 不收-无E1 / 待裁决-证据未核实}
  证据         {E1 / E3 / 具名例外 / 缺细则 / 缺答案键}
downgrade_notes：记录哪些模块的 OUT 因“主观题细则不可读”被降级为 MAYBE（缺口=blind_spot 第124条）。

用法：
  python3 build_attribution.py --out attribution.csv [--options-out attribution_options.csv]
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, hashlib, json
from pathlib import Path
from collections import defaultdict

REVIEW_DIR = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924')
CLASSIFIER = Path('/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/completeness/classifier')
BANK = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918')

MODS = ['B1', 'B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']
MOD_NAME = {'B1': '必修一(无书,仅剔除)', 'B2': '必修二', 'B3': '必修三', 'PH': '哲学', 'CU': '文化',
            'X1': '选必一', 'X2': '选必二', 'MI': '思维', 'RE': '推理'}
# classify.py 的书 -> matrix.csv 的书列名
MOD_TO_MATRIXCOL = {'B2': 'bixiu2', 'B3': 'bixiu3', 'PH': 'philosophy', 'CU': 'culture',
                    'X1': 'xuanbi1', 'X2': 'xuanbi2', 'MI': 'mind', 'RE': 'reasoning'}
RULE_VERSION = '2026-09-24-attribution-v1'


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


def fp(text):
    if not text:
        return ''
    norm = ''.join(text.split())[:200]
    return hashlib.sha1(norm.encode('utf-8')).hexdigest()[:16]


def load_identity(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    exams = d['exams']
    canon = {}
    named_exc = {}
    for eid, e in exams.items():
        if e.get('canonical_of'):
            canon[eid] = e['canonical_of']
        if e.get('named_exceptions'):
            named_exc[eid] = e['named_exceptions']
    return exams, canon, named_exc


def build_rubric_index(bank):
    """question_id -> {'E1': bool, 'E3': bool}；exam_id -> 同样聚合（部分卷证据只到卷级）。"""
    rows = read_csv(bank / 'indexes/rubric_links.csv')
    by_q = defaultdict(lambda: {'E1': False, 'E3': False})
    by_exam = defaultdict(lambda: {'E1': False, 'E3': False})
    for r in rows:
        kind = r.get('material_kind', '')
        status = r.get('exam_rubric_status', '') or r.get('pair_status', '')
        matched = ('已匹配' in status) or ('accepted' in status.lower())
        is_e1 = matched and ('评分材料' in kind or '细则' in kind or '评分标准' in kind)
        is_e3 = matched and ('参考答案' in kind)
        q = r.get('question_id', '')
        ex = r.get('exam_id', '')
        if is_e1:
            by_q[q]['E1'] = True
            by_exam[ex]['E1'] = True
        if is_e3:
            by_q[q]['E3'] = True
            by_exam[ex]['E3'] = True
    return by_q, by_exam


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--identity', default='exam_identity.json')
    ap.add_argument('--out', default='attribution.csv')
    ap.add_argument('--options-out', default='attribution_options.csv')
    a = ap.parse_args()

    classified = read_jsonl(CLASSIFIER / 'classified_prod.jsonl')
    units = read_jsonl(CLASSIFIER / 'units.jsonl')
    stem_by_qid = {u['qid']: u.get('stem', '') for u in units}
    matrix_rows = read_csv(REVIEW_DIR / 'matrix.csv')
    matrix_by_qid = {r['qid']: r for r in matrix_rows}
    exams_identity, canon_map, named_exc = load_identity(a.identity)
    rubric_by_q, rubric_by_exam = build_rubric_index(BANK)

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
        content_fp = fp(stem)

        # ---- 归属_<模块> 列 ----
        mod_cols = {}
        downgrades = []
        for m in MODS:
            st = state.get(m, 'MAYBE')
            book = MOD_TO_MATRIXCOL.get(m)
            collected = bool(book and mrow.get(book))
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

        # ---- 证据列（E1/E3/具名例外/缺细则/缺答案键）----
        rq = rubric_by_q.get(qid) or rubric_by_exam.get(exam) or rubric_by_exam.get(exam_canon) or {}
        exc = named_exc.get(exam) or named_exc.get(exam_canon)
        if rq.get('E1'):
            evidence = 'E1'
        elif exc:
            evidence = '具名例外:' + ';'.join(x['kind'] for x in exc)
        elif rq.get('E3'):
            evidence = 'E3'
        elif typ == '选择题':
            evidence = '缺答案键' if not rq else 'E3'
        else:
            evidence = '缺细则'

        # ---- 准入列（按 2026-09-24 纳入范围裁定①）----
        if typ == '选择题':
            admission = '完整题-选择题照收'
        else:
            if evidence == 'E1':
                admission = '完整题-有E1'
            elif evidence.startswith('具名例外'):
                admission = '收-具名例外'
            elif evidence in ('E3', '缺细则'):
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
            'downgrade_notes': ';'.join(downgrades),
            'dup_of': mrow.get('dup_of', ''),
            'dup_covered_by': mrow.get('dup_covered_by', ''),
            'conflict_script_out': ';'.join(ev.get('e_conflict_script_out', [])),
            'rule_version': RULE_VERSION,
            'source': 'classify.py:classified_prod.jsonl+matrix.csv+exam_identity.json',
        }
        for m in MODS:
            row['归属_' + m] = mod_cols[m]
        out_rows.append(row)
        stat['rows'] += 1
        stat['admit'] += 1 if not admission.startswith('不收') else 0
        stat['not_admit'] += 1 if admission.startswith('不收') else 0
        stat['pending'] += 1 if admission.startswith('待裁决') else 0

        # ---- 题肢级辅助表（仅选择题；弱信号，仅词典命中，不构成准入依据）----
        if typ == '选择题':
            d_options = ev.get('d_options') or {}
            for mark, hit_mods in d_options.items():
                opt_rows.append({
                    'qid': qid,
                    'option_mark': mark,
                    'dict_hit_modules': ';'.join(hit_mods),
                    'c_prior_top_module': max(ev.get('c_prior', {}), key=ev.get('c_prior', {}).get) if ev.get('c_prior') else '',
                    'note': '仅词典命中弱信号(精度约0.66-0.88)，不构成准入依据；本册是否可独立判整个题肢、官方正误需模型/人工阶段核定',
                    'rule_version': RULE_VERSION,
                })

    fieldnames = (['unit_id', 'qid', 'exam_id_raw', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                   'content_fingerprint', 'script_tier'] +
                  ['归属_' + m for m in MODS] +
                  ['admission', 'evidence', 'downgrade_notes', 'dup_of', 'dup_covered_by',
                   'conflict_script_out', 'rule_version', 'source'])
    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    opt_fields = ['qid', 'option_mark', 'dict_hit_modules', 'c_prior_top_module', 'note', 'rule_version']
    with open(a.options_out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=opt_fields)
        w.writeheader()
        w.writerows(opt_rows)

    print(f"attribution rows={stat['rows']} admit(non-不收)={stat['admit']} not_admit(不收)={stat['not_admit']} "
          f"pending(待裁决)={stat['pending']} option_rows={len(opt_rows)}")


if __name__ == '__main__':
    main()
