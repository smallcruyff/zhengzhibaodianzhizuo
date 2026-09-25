#!/usr/bin/env python3
"""第2—3步：五类确定性信号 → 每个判定单元对每个模块的三态（确定相关 / 可能 / 确定无关），再汇成单元三档。

判定单元：选择题 = 整题（另给逐肢模块）；主观题 = 小问（无小问则整题；题库小问提示有、题面没切出的补空单元）。
信号：a 设问点名  b 细则点名/考查语/细则词频  c 选择题题号位置先验（留一卷估计）
      d 关键词词典（人工种子 SEED + 书稿标题自动抽词 HEAD）  e 书稿已收录
单元对模块 m 的三态规则（阈值见常量；评测口径不含 e）：
  选择题  IN : 词典判给 m 的题肢≥2；或≥1 且位置先验≥0.5；或设问/解析点名 m
          OUT: 位置先验<0.1 且无题肢、题干判给 m 且未点名
  主观题  IN : 设问点名 m（非“综合运用”）；单小问题的细则点名 m
          OUT: 设问点名了别的模块且细则里 m 的词典分=0；或未点名但细则可读且细则、设问里 m 的词典分都=0
  其余为 MAYBE（交模型）。e（已收录）在生产口径里把该模块直接置 IN；若脚本判 OUT 则记“疑似错收”。
单元三档：确定 = 没有 MAYBE；倾向 = 有 IN 且 MAYBE≤3，或无 IN 且 MAYBE≤2；不明 = 其余。
输出：classified_{prod,eval}.jsonl、position_prior.json、lexicon_head.json
"""
import sys, os, re, json, collections, argparse
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lexicon as L  # noqa
from truth import BOOKS  # noqa

MODS = L.MODS
P_IN, P_OUT = 0.5, 0.1


def sgroup(stage):
    return {'高考': 'GK', '一模': 'MOCK', '二模': 'MOCK', '期中': 'TERM', '期末': 'TERM'}.get(stage, 'MOCK')


def truth_mods(t):
    s = set()
    for b in t.get('BOOK', {}):
        s.add(b)
    for it in t.get('CX24', {}).get('items', []):
        s |= set(it['mods'])
    for src in ('CX25', 'CX26', 'ASM', 'GK'):
        s |= set(t.get(src, {}).get('mods', []))
        if t.get(src, {}).get('bx3') is True:
            s.add('B3')
    return s


def build_prior(units, truth):
    cnt = collections.defaultdict(collections.Counter)
    tot = collections.Counter()
    per_exam = collections.defaultdict(list)
    for u in units:
        if u['type'] != '选择题':
            continue
        t = truth.get(u['qid'])
        if not t:
            continue
        ms = truth_mods(t)
        if not ms:
            continue
        g = sgroup(u['stage'])
        for key in ((g, u['num']), ('ALL', u['num'])):
            tot[key] += 1
            for m in ms:
                cnt[key][m] += 1
        per_exam[u['exam']].append((g, u['num'], ms))

    def prior(u, loo=True):
        g = sgroup(u['stage'])
        own = [x for x in per_exam.get(u['exam'], []) if x[1] == u['num']] if loo else []
        for key in ((g, u['num']), ('ALL', u['num'])):
            n = tot[key] - len(own)
            if n >= 8:
                c = collections.Counter(cnt[key])
                for (_, _, ms) in own:
                    for m in ms:
                        c[m] -= 1
                res = {m: c[m] / n for m in MODS if c[m] > 0}
                res['_n'] = n
                res['_key'] = '%s-%s' % key
                return res
        return {'_n': 0, '_key': 'none'}
    table = {}
    for (g, n), c in sorted(cnt.items(), key=lambda x: (x[0][0], x[0][1])):
        table['%s-%d' % (g, n)] = {'n': tot[(g, n)], **{m: round(c[m] / tot[(g, n)], 3) for m in MODS if c[m]}}
    return prior, table


def option_modules(text, lex):
    sc, hits = L.score_text(text, lex)
    if not sc:
        return [], {}
    top = max(sc.values())
    if top < 1.0:
        return [], {m: hits[m] for m in sc}
    return sorted(m for m, v in sc.items() if v >= top - 1e-9), {m: hits[m] for m in sc}


def rubric_readable(r):
    """细则可读 = 有足够中文且像评分文字（有“分/角度/知识/要点/水平/等级”等评分记号），不是只把题面抄了一遍。"""
    t = re.sub(r'未找到[^\n]{0,40}|（无）|见下方候选区', '', r or '')
    marks = len(re.findall(r'\d\s*分|角度|知识|要点|水平|等级|观点|给分|得分|赋分|踩点|评分标准', t))
    return len(re.findall(r'[\u4e00-\u9fff]', t)) >= 120 and marks >= 3


def states_choice(u, prior, lex):
    ev = {}
    pr = prior(u)
    p = {m: v for m, v in pr.items() if not m.startswith('_')}
    ev['c_prior'] = {m: round(v, 2) for m, v in p.items()}
    ev['c_n'] = pr.get('_n', 0)
    per_opt = {}
    for k, v in (u.get('options') or {}).items():
        per_opt[k] = option_modules(v, lex)[0]
    ev['d_options'] = per_opt
    votes = collections.Counter(m for ms in per_opt.values() for m in ms)
    stem_sc, _ = L.score_text(u.get('setq') or '', lex)
    ev['d_stem'] = {m: round(v, 1) for m, v in stem_sc.items()}
    rub = u.get('rubric') or ''
    kaocha = '\n'.join(re.findall(r'(?:考查|考察|考点)[^\n。]{0,60}', rub))
    nm, gen, frag, pend = L.naming((u.get('setq') or '') + '\n' + kaocha)
    if nm:
        ev['ab_naming'] = sorted(nm)
    # 设问直接问推理/逻辑规则或点名某种思维：该模块定为 IN，题肢里的法律、经济等词多是材料语境，降为待定
    sq = u.get('setq') or ''
    lead = set()
    tail = sq[-60:]
    if re.search(r'推理|逻辑规则|逻辑思维的基本要求|合乎逻辑|符合逻辑|一定为真|概念(?:的)?(?:外延|内涵|关系)|判断(?:的)?(?:类型|种类)', tail):
        lead.add('RE')
    if re.search(r'科学思维|辩证思维|创新思维|超前思维|联想思维|发散思维|聚合思维|思维方法', sq):
        lead.add('MI')
    if lead:
        ev['setq_lead'] = sorted(lead)
    ksc, _ = L.score_text(kaocha, lex)
    kin = {m for m, v in ksc.items() if v >= 1}
    if kin:
        ev['b_kaocha'] = sorted(kin)
    st = {}
    for m in MODS:
        v, pm, h = votes.get(m, 0), p.get(m, 0), stem_sc.get(m, 0)
        if m in lead or m in nm:
            st[m] = 'IN'
        elif lead and (v >= 1 or pm >= P_OUT or m in pend):
            st[m] = 'MAYBE'
        elif m in kin or v >= 2 or (v >= 1 and pm >= P_IN):
            st[m] = 'IN'
        elif m in pend:
            st[m] = 'MAYBE'
        elif pm < P_OUT and v == 0 and h < 1:
            st[m] = 'OUT'
        else:
            st[m] = 'MAYBE'
    return st, ev


def states_subj(u, setq, lex, multi_subq, missing_setq):
    ev = {}
    nm, gen, frag, pend = L.naming(setq)
    if nm:
        ev['a_naming'] = sorted(nm)
    if frag:
        ev['a_frag'] = frag[:4]
    if pend:
        ev['a_pending'] = sorted(pend)
    if gen:
        ev['a_generic'] = True
    if missing_setq:
        ev['setq_missing'] = True
    sq_sc, _ = L.score_text(setq, lex)
    ev['d_setq'] = {m: round(v, 1) for m, v in sq_sc.items() if v >= 1}
    rub = u.get('rubric') or ''
    readable = rubric_readable(rub)
    ev['rubric_readable'] = readable
    rnm, rpend = L.title_naming(rub[:3000])
    if rnm or rpend:
        ev['b_naming'] = sorted(rnm | rpend)
    rsc, _ = L.score_text(rub[:3000], lex)
    ev['b_lex'] = {m: round(v, 1) for m, v in rsc.items() if v >= 1}
    st = {}
    named_ok = bool(nm or pend) and not gen
    for m in MODS:
        if named_ok and m in nm:
            st[m] = 'IN'
        elif m in pend:
            st[m] = 'MAYBE'
        elif (not multi_subq) and m in rnm and not missing_setq:
            st[m] = 'IN'
        elif named_ok and readable and rsc.get(m, 0) == 0:
            st[m] = 'OUT'
        elif named_ok and not readable and sq_sc.get(m, 0) < 1 and rsc.get(m, 0) == 0:
            st[m] = 'OUT'
        elif (not named_ok) and (not gen) and readable and rsc.get(m, 0) == 0 and sq_sc.get(m, 0) < 1 and not missing_setq:
            st[m] = 'OUT'
        else:
            st[m] = 'MAYBE'
    return st, ev


def tier_of(st):
    nin = sum(1 for v in st.values() if v == 'IN')
    nmay = sum(1 for v in st.values() if v == 'MAYBE')
    if nmay == 0 and nin > 0:
        return '确定'
    if (nin and nmay <= 3) or (not nin and 1 <= nmay <= 2):
        return '倾向'
    return '不明'


def apply_e(st, ev, book):
    conflict = []
    for m in book:
        if st.get(m) == 'OUT':
            conflict.append(m)
        st[m] = 'IN'
    if book:
        ev['e_book'] = sorted(book)
    if conflict:
        ev['e_conflict_script_out'] = conflict
    return st


def book_mods_for(qid, subq, truth):
    b = truth.get(qid, {}).get('BOOK', {})
    return {m for m, subs in b.items() if subq is None or '' in subs or subq in subs}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--with-e', action='store_true')
    ap.add_argument('--lex', default='seed+head')
    ap.add_argument('--out')
    a = ap.parse_args()
    units = [json.loads(l) for l in open(os.path.join(HERE, 'units.jsonl'))]
    T = json.load(open(os.path.join(HERE, 'truth.json')))
    truth = T['truth']
    prior, table = build_prior(units, truth)
    json.dump(table, open(os.path.join(HERE, 'position_prior.json'), 'w'), ensure_ascii=False, indent=1)
    lex = {}
    if 'seed' in a.lex:
        lex.update(L.seed_terms())
    if 'head' in a.lex:
        head = L.heading_terms(BOOKS, [u['stem'] for u in units])
        for t, ms in head.items():
            lex.setdefault(t, ms)
        json.dump({t: sorted(ms) for t, ms in sorted(head.items())}, open(os.path.join(HERE, 'lexicon_head.json'), 'w'),
                  ensure_ascii=False, indent=0)
    out = open(a.out or os.path.join(HERE, 'classified_%s.jsonl' % ('prod' if a.with_e else 'eval')), 'w')
    stat = collections.Counter()

    def emit(rec, st, ev):
        rec['state'] = st
        rec['ev'] = ev
        rec['tier'] = tier_of(st)
        rec['mods_in'] = sorted(m for m, v in st.items() if v == 'IN')
        rec['mods_maybe'] = sorted(m for m, v in st.items() if v == 'MAYBE')
        out.write(json.dumps(rec, ensure_ascii=False) + '\n')
        stat[(rec['type'], rec['tier'])] += 1

    for u in units:
        base = dict(qid=u['qid'], exam=u['exam'], stage=u['stage'], num=u['num'], stem_len=u['stem_len'])
        if u['type'] == '选择题':
            st, ev = states_choice(u, prior, lex)
            if a.with_e:
                st = apply_e(st, ev, book_mods_for(u['qid'], None, truth))
            rec = dict(base, uid=u['qid'], subq=None, type='选择题',
                       slice_chars=len(u.get('setq') or '') + sum(len(v) for v in (u.get('options') or {}).values()))
            emit(rec, st, ev)
        else:
            det = {s['label']: s['setq'] for s in u['subqs']}
            hint = set()
            for h in u.get('subq_hint') or []:
                hint |= set(re.findall(r'[1-6]', h))
            labels = sorted(set(det) | hint)
            if not labels:
                subs = [(None, u['setq'] or '', False)]
            else:
                subs = [(l, det.get(l, ''), l not in det) for l in labels]
            for lab, sq, miss in subs:
                st, ev = states_subj(u, sq, lex, multi_subq=len(subs) > 1, missing_setq=miss or not sq)
                if a.with_e:
                    st = apply_e(st, ev, book_mods_for(u['qid'], lab, truth))
                rec = dict(base, uid=u['qid'] + ('(%s)' % lab if lab else ''), subq=lab, type='主观题',
                           slice_chars=len(sq) + min(400, len(u.get('rubric') or '')))
                emit(rec, st, ev)
    out.close()
    for k, v in sorted(stat.items()):
        print(k, v)
    print('lexicon terms', len(lex))


if __name__ == '__main__':
    main()
