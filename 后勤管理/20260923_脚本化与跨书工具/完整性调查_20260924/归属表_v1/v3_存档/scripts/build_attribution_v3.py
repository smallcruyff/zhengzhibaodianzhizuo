#!/usr/bin/env python3
"""build_attribution_v3.py —— 修复确认意见_v2.json blocker①、major①②③ 后的题级/小问级归属表。

相对 v2 (build_attribution_v2.py) 的关键变更（详见 确认意见_v2.json / 返修回执_v3.json）：
  1.【blocker①修复】COLLECTED 判断不再自己读 matrix.csv 的 dup_covered_by 字符串猜"是否该合并"——
     那一列对"跨卷复用/串题"(shared_or_reused_questions，例如2022/2024高考Q8/Q13、2024高考Q18↔
     2026海淀期中Q8)也会填值，v2 直接信它，等于把串题也当孪生题合并，产生假收录。
     v3 只信 exam_identity.json 的 dup_alias_qid_pairs（只覆盖真正的 duplicate_registration_alias，
     本轮唯一一对 BJ-2024/2025-HD-QIZHONG），且孪生题任一侧的 matrix.csv 模块列本身是 S/F/M
     （不管 dup_covered_by 是否为空——M 值不产生 dup_covered_by，这是 v2 假漏收的直接原因）都算覆盖。
     跨卷复用/串题只在 downgrade_notes 里标注"关联但不合并"，不改 COLLECTED。
  2.【blocker①修复】新增 canonical_qid 列：别名侧qid的 canonical_qid 指向其孪生正式qid；
     build_diffs_v3.py 按 canonical_qid 去重，避免同一等价类在漏收/OUT差集里被列两次。
  3.【blocker①修复】build_diffs 排除的"身份错误/身份未确认"行，本文件统一用
     admission.startswith('身份') 标记（伪Q18、汇编待复核未定年份两类）。
  4. 证据判定改为逐题（question_id 粒度）用 rubric_links.csv 的 pair_status + material_kind 精确判断，
     不做卷级回退。
  5.【major①修复】主观题在 rubric_links.csv 里"一行都没有"(未核实,不是已确认无) 时，admission 落
     待裁决-证据未核实，不再和"缺细则-已核实"(明确负例记录)一起被机械判"不收-无E1"。
  6.【major①修复】新增/扩充 skill_overrides.json 逐题E1覆盖：exams.csv notes 与
     book-xuanbi-1.md/book-xuanbi-3.md 里逐题写明的E1闭环/未闭环结论、官方答案键，逐条带出处覆盖
     rubric_links.csv 的自动匹配结果（例如 BJ-2026-FT-YIMO-Q19 自动匹配到"正式评分材料"但书稿反复
     核验只有方向/样例/整题赋分，应为confirmed-negative而非E1）。
  7.【major③修复】只在汇编中出现的卷（compilation_only_*）候选行：
     a) 题型改按北京卷题号区间判定（Q1-15选择题，Q16+主观题），不用文本粗推（原文括号可能全角/半角
        混排导致"(11分)"类正则漏判，见BJ-2024-FS-YIMO-Q17）；
     b) 纳入 assembly_blocks.csv 里 status=待复核 的门头沟/房山区块（能用Skill官方答案键反向核实年份的
        并入对应卷候选行，不能确定年份的单列一类，admission=待裁决-证据未核实、归属_<模块>不计入分母）；
     c) 新增4个书稿已确认收录、但 assembly_blocks.csv/questions.csv 都没有独立行的题
        （门头沟一模Q10/Q18、房山一模Q14/Q18(2)），来源标注为 book-xuanbi-1.md 具名核实，
        不冒充分类器/汇编产物。
  8.【major⑤修复】--inputs-dir 默认读交付目录本地 inputs_snapshot/（不再硬编码另一次会话的
     /private/tmp 分类器目录），可用该参数改读其它位置重新生成。

用法：
  python3 build_attribution_v3.py --identity exam_identity.json --overrides skill_overrides.json \
      --out attribution.csv --options-out attribution_options.csv [--inputs-dir inputs_snapshot] \
      [--bank-dir <题库根目录>]
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, hashlib, json, re
from pathlib import Path
from collections import defaultdict

BANK_DEFAULT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918')

MODS = ['B1', 'B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']
MOD_TO_MATRIXCOL = {'B2': 'bixiu2', 'B3': 'bixiu3', 'PH': 'philosophy', 'CU': 'culture',
                    'X1': 'xuanbi1', 'X2': 'xuanbi2', 'MI': 'mind', 'RE': 'reasoning'}
RULE_VERSION = '2026-09-24-attribution-v3'

BOILERPLATE = '本节只放原卷角色的原生文字层；OCR 候选与其它角色另列下方各节。'

# rubric_links.csv material_kind 里明确“已检查、本题不适用”的负例（不是“没查过”）
NEG_KINDS_SUBJ = {'同卷正式细则无本题内容', '同卷PPT无本题评分内容'}
NEG_KINDS_CHOICE = {'无逐题E1；选项分布不作答案键', '主观题细则不覆盖本选择题', '正式细则不覆盖选择题'}
AMBIGUOUS_PAIR = {'存在候选', '存在冲突'}
EXCLUDED_PAIR = {'已排除', '已排除（文件名指向他题）'}

# ---- major③：只在汇编中出现的卷，书稿已确认收录但 assembly_blocks.csv/questions.csv 均无独立行的题 ----
# 每条都带 book-xuanbi-1.md 的行号出处，不冒充分类器/汇编产物；content_fingerprint 留空（无可核实原文）。
BOOK_CONFIRMED_EXTRA_QIDS = [
    {'exam_id': 'BJ-2024-MTG-YIMO', 'num': '10', 'type': '选择题',
     'cite': 'book-xuanbi-1.md:308 “门头沟一模Q10=D”（本轮客观正式键闭环10项之一，正文9个实际题块与正式键9/9一致）'},
    {'exam_id': 'BJ-2024-MTG-YIMO', 'num': '18', 'type': '主观题',
     'cite': 'book-xuanbi-1.md:401 “2024门头沟一模Q18已确认属于本项目选必一题源…当前载体仍只提供E3参考答案，'
             '没有同卷独立正式E1”'},
    {'exam_id': 'BJ-2024-FS-YIMO', 'num': '14', 'type': '选择题',
     'cite': 'book-xuanbi-1.md:308 “2024房山一模Q14=C”（本轮客观正式键闭环10项之一）'},
    {'exam_id': 'BJ-2024-FS-YIMO', 'num': '18', 'subq': '2', 'type': '主观题',
     'cite': 'book-xuanbi-1.md:307 “本轮主观E1新闭环7题…房山一模Q18(2)”；book-xuanbi-1.md:51 '
             '“房山一模Q18（2）的‘开源’释义在7个重复落位全部恢复四边框”（已在选必一正文多处落位）'},
]

# ---- major②/③：assembly_blocks.csv 里 status=待复核 且能用 book-xuanbi-1.md 官方答案键反向核实年份的区块 ----
# 键=(region_label, num)，需与 exam_identity.json 的 assembly_pending_review.resolved 对应
PENDING_REVIEW_RESOLVE_TO_TYPE = {
    ('门头沟一模', '8'): '选择题', ('门头沟一模', '11'): '选择题', ('房山一模', '15'): '选择题',
}


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
    dup_alias_pairs = d.get('dup_alias_qid_pairs', [])
    pending_review = d.get('assembly_pending_review', {'resolved': [], 'unresolved': []})
    return d, exams, canon, named_exc, comp_only, qid_redirects, dup_alias_pairs, pending_review


def load_overrides(path):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    by_exam = defaultdict(list)
    for o in d.get('overrides', []):
        by_exam[o['exam_id']].append(o)
    return by_exam


def build_rubric_index(bank_dir):
    """question_id -> 该题在 rubric_links.csv 里的全部行（逐题，不做卷级聚合/回退）。"""
    rows = read_csv(bank_dir / 'indexes/rubric_links.csv')
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
            if o_num is not None and num is not None and int(num) == o_num:
                if o_subq is None or str(subq) == str(o_subq):
                    return o
    return None


def infer_type_by_position(num, preview):
    """major③修复：题型优先按北京卷题号区间判（Q1-15选择题，Q16+主观题），只在题号解析不出来时
    才退回文本粗推（原文括号全角/半角混排会让正则漏判，见BJ-2024-FS-YIMO-Q17（11分)被误判选择题）。"""
    if num:
        try:
            n = int(num)
            return '选择题' if n <= 15 else '主观题'
        except ValueError:
            pass
    is_subj = bool(re.search(r'\(\s*\d+\s*分\s*\)|（\s*\d+\s*分\s*）|\(\s*\d+\s*分\s*）|（\s*\d+\s*分\s*\)'
                              r'|结合材料|运用.*知识', preview)) or len(preview or '') > 500
    return '主观题' if is_subj else '选择题'


def load_assembly_candidates(bank_dir, comp_only, pending_review):
    """只在汇编中出现的卷：从 assembly_blocks.csv 生成候选行（缺行，非分类器产物）；major②③修复版。
    选择题照收；主观题固定 待裁决-证据未核实，除非 skill_overrides.json 有逐题覆盖。
    题号用汇编标注文本粗略推断（这一步无法改进，原文本身只给"(区县一模N)"标注），题型改按题号区间判定。"""
    if not comp_only:
        return []
    asm_rows = read_csv(bank_dir / 'indexes/assembly_blocks.csv')
    by_exam = defaultdict(list)
    for r in asm_rows:
        eid = (r.get('matched_exam_id') or '').strip()
        if eid in comp_only:
            by_exam[eid].append(r)

    out = []
    made_keys = set()  # (exam_id, num) 去重，供后面待复核解析/book-confirmed补充跳过已存在的

    def emit(eid, num, typ, preview, source, subq='', extra_downgrade=''):
        key = (eid, num, subq)
        if key in made_keys:
            return
        made_keys.add(key)
        qid = f'{eid}-Q{num}' if num else f'{eid}-BLOCK{source}'
        out.append({
            'unit_id': qid + (('#' + subq) if subq else ''), 'qid': qid, 'exam_id_raw': eid, 'exam_id_canonical': eid,
            'num': num or '', 'type': typ, 'subq': subq, 'grain': ('小问' if subq else '整题'),
            'content_fingerprint': fp(preview),
            'script_tier': '汇编候选-未分类器处理',
            **{('归属_' + m): 'MAYBE' for m in MODS},
            'admission': ('完整题-选择题照收' if typ == '选择题' else '待裁决-证据未核实'),
            'evidence': '汇编片段(assembly_blocks.csv)，原卷/正式评分载体尚未取得',
            'downgrade_notes': ('assembly_only_unclassified：题号按北京卷题号区间判定题型'
                                 '（Q1-15选择题/Q16+主观题），未经classify.py九模块判定，'
                                 '全部模块列MAYBE，需人工/模型核实模块归属' + extra_downgrade),
            'dup_of': '', 'dup_covered_by': '', 'conflict_script_out': '',
            'rule_version': RULE_VERSION,
            'source': source,
        })

    for eid, rows in by_exam.items():
        for r in rows:
            ev = r.get('evidence', '') + ' ' + r.get('preview', '')
            m = re.search(r'(?:一模|二模|期中|期末)\s*）?\s*(\d+)', ev)
            num = m.group(1) if m else None
            preview = r.get('preview', '')
            typ = infer_type_by_position(num, preview)
            emit(eid, num, typ, preview, f'assembly_blocks.csv:{r.get("assembly_id","")}#{r.get("block_index","")}')

    # ---- major②：待复核区块，能用Skill官方答案键反向核实年份的并入对应卷 ----
    for item in pending_review.get('resolved', []):
        region, num = item['region_label'], item['num']
        eid = item['resolved_exam_id']
        typ = PENDING_REVIEW_RESOLVE_TO_TYPE.get((region, num), infer_type_by_position(num, ''))
        emit(eid, num, typ, '', 'assembly_blocks.csv(待复核，已用book-xuanbi-1.md官方答案键反向核实年份)',
             extra_downgrade='；该题原在assembly_blocks.csv标"待复核"（本身matched_exam_id为空），'
                             '本表用book-xuanbi-1.md官方答案键反向核实年份并入' + eid + '，见identity层'
                             'assembly_pending_review.resolved的resolution_evidence')

    # ---- major②：待复核但无法确定年份的区块，仍纳入候选，标"身份未确认"，不计入任何模块分母 ----
    for item in pending_review.get('unresolved', []):
        region, num = item['region_label'], item['num']
        pseudo_eid = f'UNRESOLVED-{region}'
        typ = infer_type_by_position(num, '')
        qid = f'{pseudo_eid}-Q{num}'
        out.append({
            'unit_id': qid, 'qid': qid, 'exam_id_raw': pseudo_eid, 'exam_id_canonical': pseudo_eid,
            'num': num, 'type': typ, 'subq': '', 'grain': '整题', 'content_fingerprint': '',
            'script_tier': '汇编候选-待复核-年份未确认',
            **{('归属_' + m): 'MAYBE' for m in MODS},
            'admission': '身份未确认-不计入分母-待复核',
            'evidence': '汇编标注"待复核"，候选年份未达匹配门槛，book-xuanbi-1.md无可核实的具体结论',
            'evidence_detail': item.get('note', ''),
            'downgrade_notes': 'assembly_pending_review.unresolved：题型按题号区间粗判，仅供人工核实年份后改判，'
                                '不计入任何模块的漏收/错收/OUT分母',
            'dup_of': '', 'dup_covered_by': '', 'conflict_script_out': '', 'identity_redirect': 'pending_review_unresolved',
            'rule_version': RULE_VERSION,
            'source': f'assembly_blocks.csv(待复核,{region}{num})',
        })

    # ---- major③：书稿已确认收录、但汇编/questions.csv均无独立行的题（门头沟Q10/Q18、房山Q14/Q18(2)）----
    for item in BOOK_CONFIRMED_EXTRA_QIDS:
        eid = item['exam_id']
        if eid not in comp_only:
            continue
        num = item['num']
        typ = item['type']
        subq = item.get('subq', '')
        key = (eid, num, subq)
        if key in made_keys:
            continue
        made_keys.add(key)
        qid = f'{eid}-Q{num}'
        row = {
            'unit_id': qid + (('#' + subq) if subq else ''), 'qid': qid, 'exam_id_raw': eid, 'exam_id_canonical': eid,
            'num': num, 'type': typ, 'subq': subq, 'grain': ('小问' if subq else '整题'), 'content_fingerprint': '',
            'script_tier': '书稿具名核实-无汇编/题库独立行',
            **{('归属_' + m): 'MAYBE' for m in MODS},
            'admission': '待裁决-证据未核实',  # 会被下面 override 覆盖（如已配置）
            'evidence': '待裁决-证据未核实',
            'evidence_detail': item['cite'],
            'downgrade_notes': 'book_confirmed_extra_qid：questions.csv/assembly_blocks.csv均无该题独立行，'
                                '本行仅登记书稿具名核实的事实，不冒充分类器/汇编产物；'
                                '已列入回传题库线_v3.json（补登questions.csv/matrix.csv）',
            'dup_of': '', 'dup_covered_by': '', 'conflict_script_out': '',
            'rule_version': RULE_VERSION,
            'source': 'book-xuanbi-1.md(具名核实)+skill_overrides.json',
        }
        out.append(row)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--identity', default='exam_identity.json')
    ap.add_argument('--overrides', default='skill_overrides.json')
    ap.add_argument('--out', default='attribution.csv')
    ap.add_argument('--options-out', default='attribution_options.csv')
    ap.add_argument('--inputs-dir', default='inputs_snapshot',
                     help='classified_prod.jsonl/units.jsonl/matrix.csv/bank_duplicate_exams.csv 所在目录，'
                          '默认读交付目录本地快照；重新对照线上分类器输出时可指向其它目录')
    ap.add_argument('--bank-dir', default=str(BANK_DEFAULT),
                     help='题库根目录（提供 indexes/rubric_links.csv、indexes/assembly_blocks.csv）；'
                          '默认线上题库，可指向 inputs_snapshot 里的快照副本做纯离线重放')
    a = ap.parse_args()

    inputs_dir = Path(a.inputs_dir)
    bank_dir = Path(a.bank_dir)

    classified = read_jsonl(inputs_dir / 'classified_prod.jsonl')
    units = read_jsonl(inputs_dir / 'units.jsonl')
    stem_by_qid = {u['qid']: u.get('stem', '') for u in units}
    matrix_rows = read_csv(inputs_dir / 'matrix.csv')
    matrix_by_qid = {r['qid']: r for r in matrix_rows}
    (identity_doc, exams_identity, canon_map, named_exc, comp_only, qid_redirects,
     dup_alias_pairs, pending_review) = load_identity(a.identity)
    overrides_by_exam = load_overrides(a.overrides)
    rubric_by_q = build_rubric_index(bank_dir)

    # ---- blocker①核心：只信 identity 给的 dup_alias_qid_pairs 做题级等价类合并，不再自己猜 dup_covered_by ----
    canonical_of_qid = {}   # alias_qid -> canonical_qid（仅真正的重复登记别名）
    partner_of_qid = {}     # 任一侧 -> 另一侧 qid（供COLLECTED合并读取对方matrix行）
    for pr in dup_alias_pairs:
        cq, aq = pr['canonical_qid'], pr['alias_qid']
        canonical_of_qid[aq] = cq
        partner_of_qid[aq] = cq
        partner_of_qid[cq] = aq

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
        canonical_qid = canonical_of_qid.get(qid, qid)

        # ---- 归属_<模块> 列：只用 dup_alias_qid_pairs 给出的真等价类合并，跨卷复用/串题只标注不合并 ----
        mod_cols = {}
        downgrades = []
        partner_qid = partner_of_qid.get(qid)
        partner_row = matrix_by_qid.get(partner_qid, {}) if partner_qid else {}
        for m in MODS:
            st = state.get(m, 'MAYBE')
            book = MOD_TO_MATRIXCOL.get(m)
            collected_direct = bool(book and mrow.get(book))
            collected_partner = bool(book and partner_row.get(book))
            collected = collected_direct or collected_partner
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
        if partner_qid:
            downgrades.append(f'identity:dup_alias_qid_pairs合并(pair={partner_qid})')
        # 跨卷复用/串题（matrix.csv自带但不属于dup_alias_qid_pairs的dup_of/dup_covered_by）只标注，不合并
        raw_dup_of = mrow.get('dup_of', '')
        if raw_dup_of and raw_dup_of != partner_qid:
            downgrades.append(f'关联但不合并(疑似跨卷复用/串题,非duplicate_registration_alias):dup_of={raw_dup_of}')

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
                elif evidence == '缺细则':
                    # major①修复：rubric_links.csv里"一行都没有"是未核实，不是已确认无，不能判"不收"
                    admission = '待裁决-证据未核实'
                elif evidence in ('E3', '缺细则-已核实'):
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
            'canonical_qid': canonical_qid,
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
        elif admission.startswith('身份'):
            stat['identity_excluded'] += 1
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

    # ---- 只在汇编中出现的卷：补候选行（major①③）----
    asm_candidates = load_assembly_candidates(bank_dir, comp_only, pending_review)
    # 汇编候选也要过 override_for（门头沟/房山具名核实的行靠这一步拿到真实evidence/admission）
    for r in asm_candidates:
        if r.get('identity_redirect') == 'pending_review_unresolved':
            continue  # 身份未确认的行不查override，保持"待裁决-不计入分母"
        exam = r['exam_id_raw']
        ovr = override_for(overrides_by_exam, exam, exam, r.get('num'), r.get('subq', ''), r['type'])
        if ovr:
            r['evidence'] = ovr['evidence']
            prior_detail = r.get('evidence_detail', '')
            r['evidence_detail'] = (prior_detail + ' | ' if prior_detail else '') + ovr.get('evidence_detail', '') + ' | ' + '; '.join(ovr.get('cite', []))
            r['admission'] = ovr['admission']
            if ovr['admission'] == '完整题-有E1':
                r['downgrade_notes'] = r.get('downgrade_notes', '') + ';skill_overrides覆盖为E1(不再是汇编候选默认待裁决)'
            elif ovr['admission'] == '不收-无E1':
                r['downgrade_notes'] = r.get('downgrade_notes', '') + ';skill_overrides覆盖为确认负例(不再是汇编候选默认待裁决)'
            # X1/其它模块的 COLLECTED 覆盖：具名核实行如果书稿已确认落位，按override提供的module_collected标注
            if ovr.get('module_collected'):
                for mm in ovr['module_collected']:
                    r['归属_' + mm] = 'COLLECTED'
    out_rows.extend(asm_candidates)
    stat['assembly_only_rows'] = len(asm_candidates)
    for r in asm_candidates:
        stat['rows'] += 1
        if r['admission'].startswith('身份'):
            stat['identity_excluded'] += 1
        elif r['admission'].startswith('待裁决'):
            stat['pending'] += 1
        elif r['admission'].startswith('不收'):
            stat['not_admit'] += 1
        else:
            stat['admit'] += 1

    fieldnames = (['unit_id', 'qid', 'exam_id_raw', 'exam_id_canonical', 'num', 'type', 'subq', 'grain',
                   'content_fingerprint', 'script_tier'] +
                  ['归属_' + m for m in MODS] +
                  ['admission', 'evidence', 'evidence_detail', 'downgrade_notes', 'dup_of', 'dup_covered_by',
                   'conflict_script_out', 'identity_redirect', 'canonical_qid', 'rule_version', 'source'])
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
          f"pending(待裁决)={stat['pending']} identity_excluded={stat['identity_excluded']} "
          f"option_rows={len(opt_rows)}")


if __name__ == '__main__':
    main()
