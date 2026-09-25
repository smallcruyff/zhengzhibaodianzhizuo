#!/usr/bin/env python3
"""第2步前置：汇总现有“归属事实/裁定”作对照集（只读）。

来源
  BOOK   8 本书稿题块索引（block_index 输出）里的题键 = 已收录事实（信号 e，同时是对照集）
  CX24   Codex 2024 逐卷正向普查 module_classification（每题/小问，结构化模块名）
  CX25   Codex 2025 逐卷普查 module_decision + module_reason（必修三视角）
  CX26   Codex 2026 选择题复核 bixiu3_judgment + knowledge_basis；主观题 inclusion_status
  GK     主代理 2020—2025 高考逐卷筛查脚本里的本册选择题号、主观题排除原因
  ASM    2024 各区一模按模块分类汇编（题库 assembly_blocks 已定位部分）
输出 truth.json：{qid: {src: {...}}} 与 per-book 键集合、必修三二分类对照。
"""
import sys, os, re, csv, json, collections
sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
SP = os.path.dirname(os.path.dirname(HERE))
BANK = '/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918'
SKILL = '/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts'
EV = '/Users/wanglifei/Desktop/gpt和claude共同的小窝/必修三_最新Skill修订_20260913/协作/外部证据副本/检查资料'
sys.path.insert(0, SKILL)
import qpack  # noqa

BOOKS = {
    'B2': SP + '/build/book_probe/bixiu2_r230.index.json',
    'B3': SP + '/build/book_probe/bixiu3_b52.index.json',
    'PH': HERE + '/book_index/philosophy.index.json',
    'CU': HERE + '/book_index/culture.index.json',
    'X1': HERE + '/book_index/xuanbi1.index.json',
    'X2': HERE + '/book_index/xuanbi2.index.json',
    'MI': HERE + '/book_index/mind.index.json',
    'RE': HERE + '/book_index/reasoning.index.json',
}
MODS = ['B1', 'B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']
MOD_NAME = {'B1': '必修一', 'B2': '必修二', 'B3': '必修三', 'PH': '必修四·哲学', 'CU': '必修四·文化',
            'X1': '选必一', 'X2': '选必二', 'MI': '选必三·思维', 'RE': '选必三·推理'}


def mods_from_label(t):
    """把人写的模块描述（Codex 普查、汇编名）转成模块集合。只认模块名，不认知识点。"""
    t = t or ''
    s = set()
    if re.search(r'必修一|必一|必修1|中特|中国特色社会主义》', t): s.add('B1')
    if re.search(r'必修二|必二|必修2|经济与社会|经济生活', t): s.add('B2')
    if re.search(r'必修三|必三|必修3|政治与法治|政治生活|本册', t): s.add('B3')
    if re.search(r'必修四|必四|必修4|哲学与文化', t):
        if re.search(r'哲学', t): s.add('PH')
        if re.search(r'文化', t): s.add('CU')
        if not re.search(r'哲学|文化', t): s.update(['PH', 'CU'])
    elif re.search(r'哲学', t): s.add('PH')
    if re.search(r'文化生活|文化知识|传统文化|文化自信|文化载体|文化传承', t): s.add('CU')
    if re.search(r'选必一|选择性必修一|选必1|国际政治|当代国际|国际经济', t): s.add('X1')
    if re.search(r'选必二|选择性必修二|选必2|法律与生活|具体民事|民事|民法', t): s.add('X2')
    if re.search(r'选必三|选择性必修三|选必3|逻辑与思维', t):
        if re.search(r'推理|逻辑(?!与思维)', t): s.add('RE')
        if re.search(r'思维(?!》)', re.sub(r'逻辑与思维', '', t)): s.add('MI')
        if not s & {'RE', 'MI'}: s.update(['RE', 'MI'])
    else:
        if re.search(r'推理|逻辑', t): s.add('RE')
        if re.search(r'辩证思维|创新思维|科学思维|超前思维|发散|聚合|联想', t): s.add('MI')
    return s


def base_key(k):
    return re.sub(r'\(.*$', '', k)


def main():
    bank = qpack.Bank()
    keymap = qpack.load_keymap()

    def resolve(text):
        rs = qpack.resolve_all(text, bank, keymap)
        return rs[0] if rs else {}

    units = {json.loads(l)['qid']: json.loads(l) for l in open(os.path.join(HERE, 'units.jsonl'))}
    truth = collections.defaultdict(dict)
    stats = collections.Counter()

    # ---- BOOK
    book_keys = {}
    for b, f in BOOKS.items():
        d = json.load(open(f))
        ks = collections.defaultdict(set)  # base -> set(subq or '')
        unresolved = []
        for x in d['blocks'] + (d.get('drill_items') or []):
            kall = x.get('keys_all') or ([x['key']] if x.get('key') else [])
            if not kall and x.get('src'):
                r = resolve(x['src'])
                if r.get('key'):
                    kall = [r['key'] + ('(%s)' % r['subq'] if r.get('subq') else '')]
                else:
                    unresolved.append(x['src'])
                    continue
            for k in kall:
                m = re.match(r'^(.*?-Q\d+)(?:\((.+)\))?$', k)
                if not m:
                    continue
                ks[m.group(1)].add(m.group(2) or '')
        book_keys[b] = {k: sorted(v) for k, v in ks.items()}
        stats['book_%s_keys' % b] = len(ks)
        stats['book_%s_keys_not_in_bank' % b] = sum(1 for k in ks if k not in units)
        stats['book_%s_unresolved_src' % b] = len(unresolved)
        for k, v in ks.items():
            truth[k].setdefault('BOOK', {})[b] = sorted(v)

    # ---- CX24
    d4 = json.load(open(EV + '/agent_1_110/source_forward_2024.json'))
    for p in d4['papers']:
        for q in p['read_question_records']:
            r = resolve(q['unique_question_key'].replace('(', '（').replace(')', '）'))
            k = r.get('key')
            if not k:
                stats['cx24_unresolved'] += 1
                continue
            sub = r.get('subq') or ''
            m = re.search(r'第\d+[(（](\d)[)）]题', q['unique_question_key'])
            if m:
                sub = m.group(1)
            ent = truth[k].setdefault('CX24', {'items': []})
            ent['items'].append({'subq': sub, 'label': q['module_classification'],
                                 'mods': sorted(mods_from_label(q['module_classification'])),
                                 'bx3': bool(q['bixiu3_candidate']), 'type': q['question_type'],
                                 'option_boundary': q.get('option_boundary')})
            stats['cx24_items'] += 1

    # ---- CX25
    d5 = json.load(open(EV + '/agent_111_220/source_forward_2025.json'))
    for s in d5['sources']:
        for q in s['unique_questions'] + s['excluded_questions']:
            r = resolve(q['question_key'])
            k = r.get('key')
            if not k:
                stats['cx25_unresolved'] += 1
                continue
            dec = q.get('module_decision')
            txt = (q.get('module_reason') or '')
            mods = mods_from_label(txt)
            if dec in ('必修三可判', '跨模块可判'):
                mods.add('B3')
            truth[k]['CX25'] = {'decision': dec, 'reason': txt[:300], 'mods': sorted(mods),
                                'bx3': {'必修三可判': True, '跨模块可判': True, '纯外模块': False}.get(dec),
                                'option_scope': q.get('option_scope')}
            stats['cx25_items'] += 1

    # ---- CX26
    d6c = json.load(open(EV + '/agent_221_326/source_forward_2026_choice_review.json'))
    d6 = json.load(open(EV + '/agent_221_326/source_forward_2026.json'))
    allq = {}
    for p in d6['paper_entries']:
        for q in p['independent_question_judgments']:
            allq[q['question_key']] = q
    for q in d6c['questions']:
        allq[q['question_key']] = q  # 选择题以复核表为准
    for qk, q in allq.items():
        m = re.match(r'(\d{4})-?(.+?)-?(一模|二模|期末|期中)-Q(\d+)', qk)
        if m:
            text = '%s%s%s第%s题' % m.groups()
        else:
            text = qk
        r = resolve(text)
        k = r.get('key')
        if not k:
            stats['cx26_unresolved'] += 1
            continue
        j = q.get('bixiu3_judgment') or ''
        inc = q.get('inclusion_status') or ''
        if j.startswith(('include', 'candidate_independently', 'candidate_bixiu3', 'candidate_partial')):
            bx3 = True
        elif j.startswith('exclude'):
            bx3 = False
        elif q.get('type') == 'subjective' and not j:
            bx3 = True if re.match(r'(R31)?已收', inc) else (False if re.match(r'(未收|不要求)', inc) else None)
        else:
            bx3 = None
        kb = q.get('knowledge_basis') or ''
        prev = truth[k].get('CX26')
        mods = mods_from_label(kb) | ({'B3'} if bx3 else set())
        if prev:  # 同题多小问：任一小问判正即正
            bx3 = True if (prev['bx3'] or bx3) else (False if (prev['bx3'] is False or bx3 is False) else None)
            mods |= set(prev['mods'])
            j = prev['judgment'] + ';' + j
            kb = prev['basis'] + ' || ' + kb
        truth[k]['CX26'] = {'judgment': j, 'inclusion': inc[:60], 'basis': kb[:400], 'bx3': bx3,
                            'mods': sorted(mods)}
        stats['cx26_items'] += 1

    # ---- GK：主代理高考逐卷筛查（脚本常量，只读解析）
    src = open(EV + '/build_gaokao_source_forward.py', encoding='utf-8').read()
    cfg = eval(re.search(r'^config=(\{.*?\})\nnotes=', src, re.S | re.M).group(1))
    excl = eval(re.search(r'^main_exclusion=(\{.*?\})\nrows=', src, re.S | re.M).group(1))
    for y, (prefix, last, maxq, choices, main_) in cfg.items():
        for q in range(1, maxq + 1):
            k = 'BJ-%d-BJ-GAOKAO-Q%d' % (y, q)
            if q <= 15:
                truth[k]['GK'] = {'bx3': q in choices, 'label': '本册或跨模块候选' if q in choices else '非本册候选'}
            else:
                lab = main_.get(q) or excl.get(y, {}).get(q, '')
                truth[k]['GK'] = {'bx3': q in main_, 'label': lab,
                                  'mods': sorted(mods_from_label(lab) | ({'B3'} if q in main_ else set()))}
            stats['gk_items'] += 1

    # ---- ASM：2024 一模分类汇编
    amap = {'必修1': 'B1', '必修2': 'B2', '必修3': 'B3', '必修4': 'PH|CU', '选必1': 'X1', '选必2': 'X2', '选必3': 'MI|RE'}
    for r in csv.DictReader(open(BANK + '/indexes/assembly_blocks.csv', encoding='utf-8-sig')):
        k = r['matched_question_id']
        if not k:
            continue
        lab = next((v for a, v in amap.items() if a in r['assembly_id']), None)
        if not lab:
            continue
        truth[k].setdefault('ASM', {'mods': []})
        truth[k]['ASM']['mods'] = sorted(set(truth[k]['ASM']['mods']) | set(lab.split('|')))
        stats['asm_items'] += 1

    # ---- 必修三二分类对照（题级）：书中已收 = 正；普查判正 = 正；普查判负且书未收 = 负
    bx3 = {}
    for k, t in truth.items():
        pos = neg = False
        why = []
        if 'B3' in t.get('BOOK', {}):
            pos = True; why.append('BOOK')
        for s in ('CX25', 'CX26', 'GK'):
            v = t.get(s, {}).get('bx3')
            if v is True: pos = True; why.append(s)
            elif v is False: neg = True; why.append(s + '-')
        if 'CX24' in t:
            v = any(i['bx3'] for i in t['CX24']['items'])
            if v: pos = True; why.append('CX24')
            else: neg = True; why.append('CX24-')
        if pos or neg:
            bx3[k] = {'label': pos, 'why': why, 'conflict': pos and neg}
    stats['bx3_truth_total'] = len(bx3)
    stats['bx3_truth_pos'] = sum(1 for v in bx3.values() if v['label'])
    stats['bx3_truth_conflict'] = sum(1 for v in bx3.values() if v['conflict'])
    stats['truth_keys_not_in_bank'] = sum(1 for k in truth if k not in units)
    json.dump({'truth': truth, 'book_keys': book_keys, 'bx3': bx3, 'stats': stats},
              open(os.path.join(HERE, 'truth.json'), 'w'), ensure_ascii=False, indent=0)
    for k, v in sorted(stats.items()):
        print(k, v)


if __name__ == '__main__':
    main()
