#!/usr/bin/env python3
"""第3步评测：拿不含 e 的评测口径三态结果对照现有收录与裁定。输出 eval_report.json。"""
import sys, os, re, json, collections
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lexicon as L  # noqa
from classify import truth_mods, sgroup, option_modules  # noqa
from truth import BOOKS  # noqa

MODS = L.MODS


def load(p):
    return [json.loads(l) for l in open(os.path.join(HERE, p))]


def ratio(a, b):
    return round(a / b, 3) if b else None


def main():
    units = {u['qid']: u for u in load('units.jsonl')}
    ev = load('classified_eval.jsonl')
    prod = load('classified_prod.jsonl')
    T = json.load(open(os.path.join(HERE, 'truth.json')))
    truth, bx3, book_keys = T['truth'], T['bx3'], T['book_keys']
    R = collections.OrderedDict()

    def unit_book(r):
        b = truth.get(r['qid'], {}).get('BOOK', {})
        return {m for m, subs in b.items() if r['subq'] is None or '' in subs or r['subq'] in subs}

    # ---------- 1 全集
    nq = len(units)
    nch = sum(1 for u in units.values() if u['type'] == '选择题')
    gaps = {}
    for e in sorted(set(u['exam'] for u in units.values())):
        nums = set(x['num'] for x in units.values() if x['exam'] == e)
        miss = sorted(set(range(1, max(nums) + 1)) - nums)
        if miss:
            gaps[e] = miss
    R['universe'] = dict(question_source_rows=4376, unique_questions=nq, choice=nch, subjective=nq - nch,
                         judging_units=len(ev), choice_units=sum(1 for r in ev if r['type'] == '选择题'),
                         subjective_units=sum(1 for r in ev if r['type'] == '主观题'),
                         subjective_units_setq_missing=sum(1 for r in ev if r['type'] == '主观题' and r['ev'].get('setq_missing')),
                         exams=len(set(u['exam'] for u in units.values())),
                         by_stage=dict(collections.Counter(u['stage'] for u in units.values())),
                         stem_missing=sum(1 for u in units.values() if not u['stem']),
                         stem_from_teacher_or_answer_or_lecture=sum(1 for u in units.values() if u['stem_mixed']),
                         choice_options_parsed_ge3=sum(1 for u in units.values() if u['type'] == '选择题' and len(u['options']) >= 3),
                         exams_with_number_gaps=gaps)

    # ---------- 2 信号命中率
    sub = [r for r in ev if r['type'] == '主观题']
    ch = [r for r in ev if r['type'] == '选择题']
    sig = collections.OrderedDict()
    sig['subjective_units'] = len(sub)
    sig['a_named_module(非综合)'] = sum(1 for r in sub if r['ev'].get('a_naming') and not r['ev'].get('a_generic'))
    sig['a_named_but_generic'] = sum(1 for r in sub if r['ev'].get('a_naming') and r['ev'].get('a_generic'))
    sig['a_generic_only'] = sum(1 for r in sub if r['ev'].get('a_generic') and not r['ev'].get('a_naming'))
    sig['a_none'] = sum(1 for r in sub if not r['ev'].get('a_naming') and not r['ev'].get('a_generic'))
    sig['b_rubric_readable'] = sum(1 for r in sub if r['ev'].get('rubric_readable'))
    sig['b_rubric_names_module'] = sum(1 for r in sub if r['ev'].get('b_naming'))
    sig['d_setq_lexicon_hit'] = sum(1 for r in sub if r['ev'].get('d_setq'))
    sig['choice_units'] = len(ch)
    sig['b_choice_kaocha_or_naming'] = sum(1 for r in ch if r['ev'].get('b_kaocha') or r['ev'].get('ab_naming'))
    tops = [max(list(r['ev']['c_prior'].values()) or [0]) for r in ch]
    sig['c_prior_top>=0.5'] = sum(1 for x in tops if x >= 0.5)
    sig['c_prior_top>=0.6'] = sum(1 for x in tops if x >= 0.6)
    nopt = sum(len(r['ev']['d_options']) for r in ch)
    sig['d_options_total'] = nopt
    sig['d_options_labeled'] = sum(1 for r in ch for v in r['ev']['d_options'].values() if v)
    sig['d_questions_all_options_labeled'] = sum(1 for r in ch if r['ev']['d_options'] and all(r['ev']['d_options'].values()))
    inbook = set(k for k, t in truth.items() if t.get('BOOK') and k in units)
    sig['e_questions_in_any_book'] = len(inbook)
    sig['e_by_type'] = dict(collections.Counter(units[k]['type'] for k in inbook))
    sig['e_questions_in_no_book'] = nq - len(inbook)
    sig['e_questions_in_no_book_by_type'] = dict(collections.Counter(u['type'] for k, u in units.items() if k not in inbook))
    R['signal_hits'] = sig

    # ---------- 2c 位置规律
    pt = json.load(open(os.path.join(HERE, 'position_prior.json')))
    pos = collections.OrderedDict()
    for g in ('GK', 'MOCK', 'TERM', 'ALL'):
        rows = []
        for n in range(1, 16):
            d = pt.get('%s-%d' % (g, n))
            if not d:
                continue
            ms = sorted(((v, m) for m, v in d.items() if m != 'n'), reverse=True)
            rows.append({'num': n, 'n': d['n'], 'top': ms[0][1], 'top_share': ms[0][0],
                         'second': ms[1][1] if len(ms) > 1 else None, 'second_share': ms[1][0] if len(ms) > 1 else 0,
                         'modules_ge_0.2': [m for v, m in ms if v >= 0.2]})
        pos[g] = rows
    loo = collections.defaultdict(collections.Counter)
    for r in ch:
        t = truth.get(r['qid'])
        tm = truth_mods(t) if t else set()
        p = r['ev']['c_prior']
        if not tm or not p:
            continue
        g = sgroup(r['stage'])
        top = max(p.items(), key=lambda x: x[1])
        loo[g]['n'] += 1
        loo[g]['top1_in_truth'] += top[0] in tm
        loo[g]['truth_single_module'] += len(tm) == 1
        loo[g]['top1_equals_single_truth'] += tm == {top[0]}
    R['position'] = {'table': pos, 'loo': {g: dict(c, top1_hit_rate=ratio(c['top1_in_truth'], c['n'])) for g, c in loo.items()}}
    rel = {}
    for g, rows in pos.items():
        rel[g] = {'mean_top_share': round(sum(x['top_share'] for x in rows) / len(rows), 3) if rows else None,
                  'positions_top>=0.6': sum(1 for x in rows if x['top_share'] >= 0.6),
                  'labeled_per_position_median': sorted(x['n'] for x in rows)[len(rows) // 2] if rows else 0}
    R['position_reliability'] = rel
    # 年份×卷型：同一题号 top 模块是否稳定（按卷看“该位置的书内模块是否等于该卷型该位置 top”）
    # ---------- 3 各模块三态与书内收录的关系（单元级）
    per = {}
    for m in MODS:
        c = collections.Counter()
        for r in ev:
            s = r['state'][m]
            c[s] += 1
            c[r['type'] + '|' + s] += 1
            if m in unit_book(r):
                c['book|' + s] += 1
                c['book|' + r['type'] + '|' + s] += 1
        bp = c['book|IN'] + c['book|MAYBE'] + c['book|OUT']
        per[m] = dict(IN=c['IN'], MAYBE=c['MAYBE'], OUT=c['OUT'],
                      choice_IN=c['选择题|IN'], choice_MAYBE=c['选择题|MAYBE'], choice_OUT=c['选择题|OUT'],
                      subj_IN=c['主观题|IN'], subj_MAYBE=c['主观题|MAYBE'], subj_OUT=c['主观题|OUT'],
                      book_units=bp, book_in_IN=c['book|IN'], book_in_MAYBE=c['book|MAYBE'], book_in_OUT=c['book|OUT'],
                      miss_rate_OUT=ratio(c['book|OUT'], bp),
                      choice_book_miss=ratio(c['book|选择题|OUT'], c['book|选择题|IN'] + c['book|选择题|MAYBE'] + c['book|选择题|OUT']),
                      subj_book_miss=ratio(c['book|主观题|OUT'], c['book|主观题|IN'] + c['book|主观题|MAYBE'] + c['book|主观题|OUT']))
    R['module_states_vs_books'] = per

    # ---------- 4 必修三题级二分类（对照：书收录/Codex 普查/主代理高考筛查）
    qstate = collections.defaultdict(lambda: collections.defaultdict(set))
    for r in ev:
        for m in MODS:
            qstate[r['qid']][m].add(r['state'][m])

    def qs(k, m):
        s = qstate[k][m]
        return 'IN' if 'IN' in s else ('MAYBE' if 'MAYBE' in s else 'OUT')
    cm = collections.Counter()
    ex = {'OUT_but_positive': [], 'IN_but_negative': []}
    for k, v in bx3.items():
        if k not in units or v['conflict']:
            continue
        s = qs(k, 'B3')
        y = 'pos' if v['label'] else 'neg'
        cm[(units[k]['type'], s, y)] += 1
        cm[('ALL', s, y)] += 1
        if s == 'OUT' and v['label']:
            ex['OUT_but_positive'].append(k)
        if s == 'IN' and not v['label']:
            ex['IN_but_negative'].append(k)
    b3 = {}
    for t in ('ALL', '选择题', '非选择题'):
        d = {'%s_%s' % (s, y): cm[(t, s, y)] for s in ('IN', 'MAYBE', 'OUT') for y in ('pos', 'neg')}
        n = sum(d.values())
        d['n'] = n
        d['IN_precision'] = ratio(d['IN_pos'], d['IN_pos'] + d['IN_neg'])
        d['OUT_npv'] = ratio(d['OUT_neg'], d['OUT_pos'] + d['OUT_neg'])
        d['positives_lost_in_OUT'] = ratio(d['OUT_pos'], d['IN_pos'] + d['MAYBE_pos'] + d['OUT_pos'])
        d['decided_share'] = ratio(n - d['MAYBE_pos'] - d['MAYBE_neg'], n)
        d['auto_accuracy_on_decided'] = ratio(d['IN_pos'] + d['OUT_neg'], n - d['MAYBE_pos'] - d['MAYBE_neg'])
        b3[t] = d
    R['bx3_vs_rulings'] = b3

    # ---------- 5 CX24（2024 各卷 Codex 结构化模块名，哲学/文化并为B4，思维/推理并为X3）
    merge = {'PH': 'B4', 'CU': 'B4', 'MI': 'X3', 'RE': 'X3'}
    mm = collections.defaultdict(collections.Counter)
    for k, t in truth.items():
        if 'CX24' not in t or k not in units:
            continue
        tm = set(merge.get(m, m) for it in t['CX24']['items'] for m in it['mods'])
        for M in sorted(set(merge.get(x, x) for x in MODS)):
            sub_m = [m for m in MODS if merge.get(m, m) == M]
            s = 'IN' if any(qs(k, m) == 'IN' for m in sub_m) else ('MAYBE' if any(qs(k, m) == 'MAYBE' for m in sub_m) else 'OUT')
            mm[M]['%s_%s' % (s, 'pos' if M in tm else 'neg')] += 1
    cx = {}
    for M, c in mm.items():
        cx[M] = dict(c, IN_precision=ratio(c['IN_pos'], c['IN_pos'] + c['IN_neg']),
                     OUT_npv=ratio(c['OUT_neg'], c['OUT_neg'] + c['OUT_pos']),
                     lost_in_OUT=ratio(c['OUT_pos'], c['IN_pos'] + c['MAYBE_pos'] + c['OUT_pos']))
    R['cx24_multilabel'] = cx

    # ---------- 6 ASM
    asm = collections.Counter()
    for k, t in truth.items():
        if 'ASM' in t and k in units:
            asm['n'] += 1
            st = [qs(k, m) for m in t['ASM']['mods']]
            asm['IN'] += 'IN' in st
            asm['MAYBE_only'] += ('IN' not in st) and ('MAYBE' in st)
            asm['OUT'] += all(s == 'OUT' for s in st)
    R['asm_2024yimo'] = dict(asm)

    # ---------- 7 逐肢词典 vs 书稿题肢单练
    lex = dict(L.seed_terms())
    for t, ms in json.load(open(os.path.join(HERE, 'lexicon_head.json'))).items():
        lex.setdefault(t, set(ms))
    dres = {}
    for b, f in BOOKS.items():
        d = json.load(open(f))
        items = [x for x in (d.get('drill_items') or []) if x.get('side') == 'A1' and x.get('stem')
                 and not re.search(r'跨册|跨模块|其他模块|补录|语境辨析', x.get('group') or '')]
        c = collections.Counter()
        for x in items:
            ms, _ = option_modules(x['stem'], lex)
            c['n'] += 1
            c['labeled'] += bool(ms)
            c['correct'] += b in ms
        if c['n']:
            dres[b] = dict(c, labeled_rate=ratio(c['labeled'], c['n']), precision_when_labeled=ratio(c['correct'], c['labeled']))
    R['option_lexicon_vs_book_drills'] = dres

    # ---------- 8 a 点名的准确率
    ac = collections.Counter()
    samp = []
    for r in sub:
        nm = set(r['ev'].get('a_naming') or [])
        if not nm or r['ev'].get('a_generic'):
            continue
        bm = unit_book(r)
        t = truth.get(r['qid'])
        tm = truth_mods(t) if t else set()
        if not tm:
            continue
        ac['n'] += 1
        ac['named_in_truth'] += bool(nm & tm)
        ac['book_includes_other_module'] += bool(bm - nm)
        if not (nm & tm) and len(samp) < 10:
            samp.append({'uid': r['uid'], 'named': sorted(nm), 'truth': sorted(tm), 'frag': r['ev'].get('a_frag')})
    R['a_naming_vs_truth'] = dict(ac, precision=ratio(ac['named_in_truth'], ac['n']))
    R['a_naming_mismatch_samples'] = samp

    # ---------- 9 档位
    R['tiers_eval(no_e)'] = {'%s|%s' % k: v for k, v in sorted(collections.Counter((r['type'], r['tier']) for r in ev).items())}
    R['tiers_prod(with_e)'] = {'%s|%s' % k: v for k, v in sorted(collections.Counter((r['type'], r['tier']) for r in prod).items())}
    R['prod_conflicts_book_vs_script_OUT'] = dict(collections.Counter(m for r in prod for m in r['ev'].get('e_conflict_script_out', [])))
    mayn = collections.Counter(len(r['mods_maybe']) for r in ev)
    R['maybe_count_per_unit_eval'] = dict(sorted(mayn.items()))
    R['units_with_any_maybe_eval'] = sum(1 for r in ev if r['mods_maybe'])
    R['units_with_any_maybe_prod'] = sum(1 for r in prod if r['mods_maybe'])
    R['maybe_pairs_eval'] = sum(len(r['mods_maybe']) for r in ev)
    R['maybe_pairs_prod'] = sum(len(r['mods_maybe']) for r in prod)

    # ---------- 10 样例
    def show(k):
        u = units[k]
        r0 = next(r for r in ev if r['qid'] == k)
        return {'qid': k, 'type': u['type'], 'B3_state': qs(k, 'B3'), 'truth_src': bx3[k]['why'],
                'setq': (u['setq'] or '')[-70:] if u['type'] == '选择题' else [x['setq'][:50] for x in u['subqs']] or (u['setq'] or '')[-70:],
                'options': {kk: [v[:26], r0['ev'].get('d_options', {}).get(kk)] for kk, v in (u.get('options') or {}).items()},
                'prior_top3': sorted(r0['ev'].get('c_prior', {}).items(), key=lambda x: -x[1])[:3],
                'a': r0['ev'].get('a_naming'), 'b': r0['ev'].get('b_naming')}
    R['bx3_OUT_but_positive_count'] = len(ex['OUT_but_positive'])
    R['bx3_IN_but_negative_count'] = len(ex['IN_but_negative'])
    R['bx3_OUT_but_positive_samples'] = [show(k) for k in ex['OUT_but_positive'][:12]]
    R['bx3_IN_but_negative_samples'] = [show(k) for k in ex['IN_but_negative'][:12]]
    json.dump(R, open(os.path.join(HERE, 'eval_report.json'), 'w'), ensure_ascii=False, indent=1)
    for k in R:
        if k.endswith('samples') or k == 'position':
            continue
        print('##', k)
        print(json.dumps(R[k], ensure_ascii=False)[:1500])


if __name__ == '__main__':
    main()
