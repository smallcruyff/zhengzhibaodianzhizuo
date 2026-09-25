#!/usr/bin/env python3
"""第1步：从题库只读抽出“卷×题号”唯一题集合与分类所需的精简切片。

输出 units.jsonl：每题一行
  qid, exam, year, stage, region, num, type, type_votes, stem, setq(设问), options{标号:文字},
  subqs[{label, setq}], rubric(E1+E3 文字，截断), sizes
只读：题库 indexes/ 与 questions/<卷>/<题>.md；借用 Skill 母版 qpack.py 的小节角色判定（import，不写 pyc）。
"""
import sys, os, re, csv, json, collections
sys.dont_write_bytecode = True
BANK = '/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918'
SKILL = '/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts'
OUT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SKILL)
import qpack  # noqa

T, _ = qpack.load_bank_tables(os.path.join(BANK, 'scripts', 'bank.py'))


def clean(t):
    t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
    t = re.sub(r'!\[[^\]]*\]\([^)]*\)', '', t)
    t = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', t)
    t = re.sub(r'`[^`\n]{1,300}`', '', t)
    out = []
    for ln in t.split('\n'):
        s = ln.strip()
        if not s:
            continue
        if s.startswith('>'):
            if re.match(r'^>\s*(⚠|注意|说明|本题|本文件|来源|OCR)', s):
                continue
            s = s.lstrip('>').strip()
            if not s:
                continue
        if s.startswith('```'):
            continue
        if re.match(r'^#{3,6}\s', s):  # 三级以下小标题多为工程说明
            continue
        if re.match(r'^[-*]\s*(来源|状态|角色|SHA|sha|E1 状态|细则 PDF|原卷|位置|rubric_status|答案来源|页级|生成期)', s):
            continue
        out.append(s)
    return '\n'.join(out)


SUBQ_RX = re.compile(r'(?:^|[\s。；;）)*|])[（(]\s*([1-9一二三四五六])\s*[）)]')


def split_subqs(stem):
    """在题面里找（1）（2）…设问；返回 [(label, 设问文字)]，设问取标号到“分）”或段末，限 220 字。"""
    res = []
    seen = set()
    for m in SUBQ_RX.finditer(stem):
        lab = m.group(1)
        lab = {'一': '1', '二': '2', '三': '3', '四': '4', '五': '5', '六': '6'}.get(lab, lab)
        if lab in seen:
            continue
        tail = stem[m.end():m.end() + 260]
        cut = re.search(r'[（(]\s*\d+\s*分\s*[）)]', tail)
        seg = tail[:cut.end()] if cut else tail.split('\n')[0]
        seg = seg.strip()
        if len(seg) < 6:
            continue
        # 选项里的（1）很少见；设问一般含动词
        if not re.search(r'说明|分析|阐述|阐释|谈谈|运用|结合|概括|指出|评析|简析|提出|写出|论证|推断|判断|解释|理解|认识|体现|为什么|如何|怎样|哪些|补全|完成|撰写|拟|设计|回答|证明|比较|依据|属于|哪种|哪一|什么|补充|？|\?', seg):
            continue
        seen.add(lab)
        res.append({'label': lab, 'setq': seg[:220]})
    return res


def whole_setq(stem):
    """无小问时：取题面最后含设问动词的一段（限 240 字）。"""
    paras = [p for p in stem.split('\n') if p.strip()]
    for p in reversed(paras[-6:]):
        if re.search(r'说明|分析|阐述|阐释|谈谈|运用|结合|概括|指出|评析|简析|提出|论证|推断|解释|为什么|如何|怎样', p):
            return p[-240:]
    return (paras[-1][-240:] if paras else '')


OPT_CIRC = re.compile(r'([①②③④⑤⑥])\s*([^①②③④⑤⑥\n]{2,120})')
OPT_LET = re.compile(r'(?:^|\n|\s)([A-D])\s*[．.、:：]\s*([^\n]{1,160}?)(?=\s+[A-D]\s*[．.、:：]|\n|$)')


def parse_options(stem):
    opts = collections.OrderedDict()
    for m in OPT_CIRC.finditer(stem):
        k = m.group(1)
        if k not in opts:
            v = m.group(2).strip()
            v = re.split(r'\s+A\s*[．.、]', v)[0]
            opts[k] = v
    if len(opts) >= 3:
        return opts, 'circled'
    opts = collections.OrderedDict()
    for m in OPT_LET.finditer(stem):
        k = m.group(1)
        if k not in opts:
            opts[k] = m.group(2).strip()
    return opts, 'letter'


def main():
    exams = {r['exam_id']: r for r in csv.DictReader(open(os.path.join(BANK, 'indexes', 'exams.csv'), encoding='utf-8-sig'))}
    rows = list(csv.DictReader(open(os.path.join(BANK, 'indexes', 'questions.csv'), encoding='utf-8-sig')))
    by = collections.OrderedDict()
    for r in rows:
        by.setdefault(r['question_id'], []).append(r)
    # 每卷选择题最大题号（用已判型的行推断）
    maxchoice = collections.defaultdict(int)
    for r in rows:
        if r['type'] == '选择题':
            try:
                maxchoice[r['exam_id']] = max(maxchoice[r['exam_id']], int(r['num']))
            except ValueError:
                pass
    stats = collections.Counter()
    out = open(os.path.join(OUT, 'units.jsonl'), 'w', encoding='utf-8')
    for qid, rs in by.items():
        ex = rs[0]['exam_id']
        e = exams.get(ex, {})
        num = int(re.sub(r'\D', '', rs[0]['num']) or 0)
        votes = collections.Counter(r['type'] for r in rs if r['type'] in ('选择题', '非选择题'))
        fp = os.path.join(BANK, 'questions', ex, qid + '.md')
        md = open(fp, encoding='utf-8').read() if os.path.isfile(fp) else ''
        pre, secs = qpack.split_md(md)
        roles = collections.defaultdict(list)
        for s in secs:
            role, basis = qpack.classify(s['heading'], T, qid)
            roles[role].append(s)
        guide = qpack.guide_fields(secs)
        h, _ = qpack.adopted_stem_heading(secs, T, guide)
        for s in secs:
            if re.search(r'ORIGINAL_QUESTION|原卷完整题面|原题完整候选', s['heading']) and s not in roles.get('stem', []):
                roles['stem'].append(s)
        stem_secs = [s for s in secs if s['heading'] == h] if h else []
        if not stem_secs or len(clean(stem_secs[0]['body'])) < 60:
            cands = sorted(roles.get('stem', []), key=lambda s: -len(clean(s['body'])))
            if cands and len(clean(cands[0]['body'])) > 20:
                stem_secs = cands[:1]
        if not stem_secs:
            cands = sorted(roles.get('lecture', []) + roles.get('candidate', []) + roles.get('e3', []),
                           key=lambda s: -len(clean(s['body'])))
            stem_secs = [c for c in cands if len(clean(c['body'])) > 40][:1]
            if stem_secs:
                stats['stem_from_answer_or_lecture'] += 1
        stem = clean(stem_secs[0]['body']) if stem_secs else ''
        stem_src = stem_secs[0]['heading'] if stem_secs else ''
        # 教师版/讲评混排题面可能夹答案，标记出来
        stem_mixed = bool(re.search(r'教师版|OCR|讲评|答案|评分|细则', stem_src))
        rub = []
        for role in ('e1', 'e3'):
            for s in roles.get(role, []):
                rub.append(clean(s['body']))
        if not rub:
            for s in roles.get('candidate', []) + roles.get('lecture', []):
                rub.append(clean(s['body']))
        rubric = '\n'.join(rub)
        if votes:
            typ = votes.most_common(1)[0][0]
        else:
            typ = '选择题' if num and num <= (maxchoice.get(ex) or 15) else '非选择题'
            stats['type_inferred'] += 1
        if len(votes) > 1:
            stats['type_conflict'] += 1
        if typ == '选择题' and num >= 16 and len(parse_options(stem)[0]) < 2 and re.search(r'谈谈|分析|说明|阐述|阐释|评析', stem[-300:]):
            typ = '非选择题'
            stats['type_fixed_to_subjective'] += 1
        opts, optkind = parse_options(stem) if typ == '选择题' else ({}, '')
        subqs = split_subqs(stem) if typ == '非选择题' else []
        setq = whole_setq(stem) if typ == '非选择题' and not subqs else ''
        if typ == '选择题':
            # 选择题“设问”= 题干末句（选项之前）
            head = re.split(r'[①A]\s*[．.、]?', stem, maxsplit=1)[0]
            setq = head[-160:]
        u = dict(qid=qid, exam=ex, year=e.get('year'), stage=e.get('stage'), region=e.get('region'),
                 school_year=e.get('school_year'), num=num, type=typ, type_votes=dict(votes),
                 stem_src=stem_src, stem_mixed=stem_mixed, stem=stem[:4000], stem_len=len(stem),
                 setq=setq, options=opts, optkind=optkind, subqs=subqs,
                 subq_hint=sorted(set(r['subq_hint'] for r in rs if r['subq_hint'])),
                 rubric=rubric[:6000], rubric_len=len(rubric), md_len=len(md),
                 conv_status=sorted(set(r['extraction_status'] for r in rs)))
        stats['q'] += 1
        stats['stem_ok' if stem else 'stem_missing'] += 1
        stats['rubric_ok' if rubric else 'rubric_missing'] += 1
        out.write(json.dumps(u, ensure_ascii=False) + '\n')
    out.close()
    print(dict(stats))


if __name__ == '__main__':
    main()
