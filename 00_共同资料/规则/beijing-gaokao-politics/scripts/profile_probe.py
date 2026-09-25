#!/usr/bin/env python3
"""书册配置草案：对一本新书的 DOCX 自动普查，生成与 profiles/bixiu3.json 同结构的配置草案。

普查内容：样式名与使用量、一二级标题样式、例题标题写法（例题N/选择例题N/选择题N/例N/【主例】/A1-01 卡片/
无编号题源标题）、题型（按标题前缀，混用时按栏目标签改判）、各部分栏目模式（含行中栏目标签）、编号重置层级、
考法（N题）口径、节点级栏目、目录模式、页脚格式、单练形态（三列表/段落式/题卡）、字体角色、分页标记。
推断出的字段附证据（出现次数、比例）；推断不了、推断存疑或属于用户/主代理裁定的字段登记在 _needs_confirm，
值写“需人工确认：原因”。草案随后用 block_index 按草案重切一遍，把题块数、缺栏候选写进自检，便于判断草案是否可用。

书册识别：先看书名段（第一个一级标题前的封面段、Cover/Title 样式段）和文件名，收集全部命中的书名关键词；
只命中一本才认书，命中多本或只在正文命中时不自动选，候选列进 _needs_confirm，班课、规则文件、协作册名、
题库模块等随书册走的字段留空。--book-id 给出已知书册编号时按其取这些字段，与书名段不一致会列为待确认。

用法
  python3 profile_probe.py --docx 新书.docx [--book-id philosophy] [--out 目录] [--template bixiu3]
  python3 profile_probe.py --docx 新书.docx --census-only          # 只出普查，不出草案
  python3 profile_probe.py --docx 已登记册.docx --calibrate --out 目录   # 对已登记（含冻结）册只做校准对照
  作为模块：from profile_probe import probe; draft, report = probe(docx)
输出：<out>/<book_id>.draft.json（配置草案）与 <out>/<book_id>.probe.json（普查证据、需确认清单、自检、校准）。
缺省输出目录：系统临时目录/book_probe（建议显式给 --out）。

只读承诺：只用 zipfile 读 DOCX；不改任何输入；输出保护与 block_index.guard_out 同一套：拒绝把草案写进
scripts/profiles/（草案须经人工确认后，由 profiles 负责人另行登记）、DOCX 所在目录、各登记书册的工作区/审阅入口/
协作目录、题库根、项目根、_house.json output_guard.protected_roots 所列根，临时目录以外有 .docx/.pdf 的目录；
DOCX 属于冻结册时拒绝生成草案（冻结册只读；需要校准对照时加 --calibrate，草案保留该册 frozen 标记）。
退出码：0 已生成草案；1 已生成但自检发现题块为 0 或一二级标题缺失（草案不可直接用）；
2 输入/参数错误（DOCX 损坏、book_id 非法）、拒绝写入或内部错误。
"""
import sys
sys.dont_write_bytecode = True  # 不在 Skill 母版 scripts/ 里留下 __pycache__

import argparse, bisect, json, re, statistics, tempfile, time, traceback, zipfile
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import load_profile, frozen_guard, PROFILE_DIR  # noqa: E402
import block_index as BI  # noqa: E402

W = BI.W
CONFIRM = '需人工确认'
DEFAULT_OUT = Path(tempfile.gettempdir()) / 'book_probe'
BOOK_ID_RX = re.compile(r'^[\w][\w\-]{0,63}$')

# 例题标题写法族：(题型, 正则, 是否编号)。顺序即匹配优先级。
FAMILIES = [
    ('ext', r'^拓展例题\s*(?P<num>\d+)[\s　]+(?P<src>.+)$', True),
    ('choice', r'^选择例题\s*(?P<num>\d+)[\s　]+(?P<src>.+)$', True),
    ('choice', r'^选择题\s*(?P<num>\d+)[\s　]+(?P<src>.+)$', True),
    ('subjective', r'^例题\s*(?P<num>\d+)[\s　]+(?P<src>.+)$', True),
    ('topic', r'^例(?P<num>\d+)[\s　]+(?P<src>.+)$', True),
    ('topic_case', r'^【(主例|变式[一二三四五六]?)】\s*(?P<src>.+)$', False),
    ('drill_card_a1', r'^A1-(?P<num>\d+)[\s｜|]+(?P<src>.+)$', True),
    ('drill_card_a2', r'^A2-(?P<num>\d+)[\s｜|]+(?P<src>.+)$', True),
    ('subjective', r'^(?P<src>20\d\d\s*(?:[—\-–]\s*20\d\d\s*学年)?\s*年?\s*\S{0,8}?(?:一模|二模|期末|期中|高考|适应性)\s*第\s*\d.*)$', False),
    # 兜底：其他“某某题 N　20xx…”写法（如选必二“例外题 1”），题型名取前缀，需人工确认
    ('other', r'^(?P<prefix>[一-龥]{1,5})\s*(?P<num>\d+)[\s　]+(?P<src>20\d\d.+)$', True),
]
FAM_RX = [(k, re.compile(rx), n) for k, rx, n in FAMILIES]
SOURCE_LABELS = ['【题目】', '【材料】', '【材料原文】', '【原题材料】', '【设问】']
# 书册编号 → (协作册名, 题库模块提示, 规则文件, 班课文件名关键词, 书名关键词)。书名关键词须能区分各册：
# 不用“推理”“思维”“法律”这类会出现在别册正文里的单词（文化宝典导语里就有“推理桥梁”）。
BOOKS = OrderedDict([
    ('bixiu2', ('必修二', '经济与社会', 'book-bixiu-2.md', ['必修二'], ['经济与社会', '必修二'])),
    ('bixiu3', ('必修三', '政治与法治', 'book-bixiu-3.md', ['必修三'], ['政治与法治', '必修三'])),
    ('philosophy', ('必修四哲学', '哲学与文化', 'book-philosophy.md', ['必修四哲学', '哲学'], ['哲学宝典', '必修四哲学'])),
    ('culture', ('必修四文化', '哲学与文化', 'book-culture.md', ['必修四文化', '文化'], ['文化宝典', '必修四文化'])),
    ('xuanbi1', ('选必一', '当代国际政治与经济', 'book-xuanbi-1.md', ['选必一'], ['选必一', '当代国际政治与经济'])),
    ('xuanbi2', ('选必二', '法律与生活', 'book-xuanbi-2.md', ['选必二'], ['选必二', '法律与生活', '法律宝典'])),
    ('mind', ('选必三思维', '逻辑与思维', 'book-xuanbi-3.md', ['选必三思维'], ['思维宝典', '选必三思维'])),
    ('reasoning', ('选必三推理', '逻辑与思维', 'book-reasoning.md', ['选必三推理'], ['推理宝典', '选必三推理'])),
])


class Draft:
    """记录需确认字段与推断证据。"""

    def __init__(self):
        self.confirm = OrderedDict()
        self.evidence = OrderedDict()

    def ask(self, path, reason):
        self.confirm[path] = f'{CONFIRM}：{reason}'
        return None

    def ev(self, path, info):
        self.evidence[path] = info


# ---------------------------------------------------------------- 普查
def style_info(z):
    names, info = {}, {}
    root = etree.fromstring(z.read('word/styles.xml'))
    for st in root.iter(W + 'style'):
        n = st.find(W + 'name')
        names[st.get(W + 'styleId')] = n.get(W + 'val') if n is not None else st.get(W + 'styleId')
    for st in root.iter(W + 'style'):
        nm = names[st.get(W + 'styleId')]
        f = lambda path: st.find(path)
        rf, sz, col, b = f(f'{W}rPr/{W}rFonts'), f(f'{W}rPr/{W}sz'), f(f'{W}rPr/{W}color'), f(f'{W}rPr/{W}b')
        ol, kn, based = f(f'{W}pPr/{W}outlineLvl'), f(f'{W}pPr/{W}keepNext'), f(W + 'basedOn')
        info[nm] = {'type': st.get(W + 'type'),
                    'ea': rf.get(W + 'eastAsia') if rf is not None else None,
                    'ascii': rf.get(W + 'ascii') if rf is not None else None,
                    'pt': int(sz.get(W + 'val')) / 2 if sz is not None and (sz.get(W + 'val') or '').isdigit() else None,
                    'color': col.get(W + 'val') if col is not None else None,
                    'bold': b is not None and b.get(W + 'val') not in ('0', 'false'),
                    'outline': ol.get(W + 'val') if ol is not None else None,
                    'keepNext': kn is not None,
                    'basedOn': names.get(based.get(W + 'val')) if based is not None else None}
    return info


def doc_parts(z):
    body = etree.fromstring(z.read('word/document.xml')).find(W + 'body')
    if body is None:
        body = etree.Element(W + 'body')
    sects = body.findall('.//' + W + 'sectPr')
    n_tables = len(body.findall('.//' + W + 'tbl'))
    title_pg = any(s.find(W + 'titlePg') is not None for s in sects)
    fields = Counter()
    for it in body.iter(W + 'instrText'):
        k = (it.text or '').strip().split(' ')[0]
        if k:
            fields[k] += 1
    for fs in body.iter(W + 'fldSimple'):
        k = (fs.get(W + 'instr') or '').strip().split(' ')[0]
        if k:
            fields[k] += 1
    footers = OrderedDict()
    for n in sorted(z.namelist()):
        if re.match(r'word/(footer|header)\d*\.xml$', n):
            fx = etree.fromstring(z.read(n))
            instr = [(i.text or '').strip() for i in fx.iter(W + 'instrText')] + \
                    [(x.get(W + 'instr') or '').strip() for x in fx.iter(W + 'fldSimple')]
            footers[n] = {'text': ''.join(t.text or '' for t in fx.iter(W + 't')), 'fields': [i for i in instr if i]}
    media = [n for n in z.namelist() if n.startswith('word/media/')]
    return {'sections': len(sects), 'title_pg': title_pg, 'fields': fields, 'footers': footers, 'media': len(media),
            'tables': n_tables}


def basic_census(doc, dp, sinfo):
    use, labels = Counter(), Counter()
    kn, pbb = Counter(), Counter()
    h3 = 0
    for r in doc['paras']:
        nm = r['style'] if r['explicit_style'] else '(默认)'
        use[nm] += 1
        if r['keep_next']:
            kn[nm] += 1
        if r['page_break_before']:
            pbb[nm] += 1
        if sinfo.get(r['style'], {}).get('outline') == '2' or r['style'].lower() == 'heading 3':
            h3 += 1
        if not r['fallback']:
            labels.update(re.findall(r'【[^】]{1,14}】', r['text']))
    tables = dp['tables']
    return OrderedDict([
        ('tool', 'profile_probe.py'), ('paragraphs', len(doc['paras'])), ('tables', tables), ('sections', dp['sections']), ('media', dp['media']),
        ('style_use', use.most_common(60)), ('labels', labels.most_common(60)), ('h3_count', h3),
        ('keepNext_direct', kn.most_common(20)), ('keepNext_total', sum(kn.values())),
        ('pageBreakBefore', pbb.most_common(15)), ('fields', dp['fields'].most_common(15)),
        ('footers', dp['footers']), ('title_pg', dp['title_pg']), ('default_style', doc['default_style']),
    ])


# ---------------------------------------------------------------- 推断工具
def heading_like(name, sinfo):
    n = name.lower()
    if 'toc' in n or '目录' in name:
        return False
    return bool(re.search(r'heading|标题|title|subgroup|^h\d', n)) or sinfo.get(name, {}).get('outline') is not None


def label_start(t):
    return bool(BI.LABEL_AT.match(t or ''))


def pick_headings(paras, sinfo, level):
    use = Counter(r['style'] for r in paras if r['text'].strip() and r['tbl'] is None)
    out = []
    for name, n in use.items():
        nl = name.lower()
        if 'toc' in nl or '目录' in name:
            continue
        if re.fullmatch(rf'heading {level}|标题 ?{level}', nl) or re.match(rf'^h{level}(?!\d)', nl):
            out.append((n, name))
    if not out:  # 退回按样式大纲级别
        for name, n in use.items():
            if sinfo.get(name, {}).get('outline') == str(level - 1) and 'toc' not in name.lower():
                out.append((n, name))
    return [nm for n, nm in sorted(out, reverse=True)]


def ordered_labels(recs):
    seen = []
    for r in recs:
        for L in BI._labels_in(r['text']):
            if L not in seen:
                seen.append(L)
    return seen


def identify_book(paras, h1s, docx):
    """书名段（封面、Cover/Title 样式段）＋文件名优先；正文前 12 段只作候选。返回识别结果与全部命中。"""
    first_h1 = next((i for i, r in enumerate(paras) if r['style'] in h1s and r['text'].strip()), len(paras))
    cover = [r['text'].strip() for r in paras[:first_h1] if r['text'].strip() and r['tbl'] is None][:10]
    styled = [r['text'].strip() for r in paras[:80] if r['text'].strip()
              and re.match(r'(?i)^(cover|title|书名|封面)', r['style'])]
    title_zone = cover + [t for t in styled if t not in cover] + [Path(docx).stem]
    body_zone = [r['text'].strip() for r in paras[first_h1:first_h1 + 40] if r['text'].strip()][:12]

    def hits(texts):
        out = OrderedDict()
        blob = ' '.join(texts)
        for bid, meta in BOOKS.items():
            kws = [k for k in meta[4] if k in blob]
            if kws:
                out[bid] = kws
        return out

    th, bh = hits(title_zone), hits(body_zone)
    book = next(iter(th)) if len(th) == 1 else None
    return OrderedDict([('book', book), ('by', '书名段/文件名' if book else None),
                        ('title_hits', th), ('body_hits', bh), ('title_zone', [t[:40] for t in title_zone[:6]])])


def cn_part_ids(h1s):
    """一级标题 → 部分：连续的“一、二、……”并成一个部分；其余按前缀各成一部分。"""
    parts, used = [], Counter()
    run = []

    def flush_run():
        if run:
            nums = ''.join(sorted({t[0] for t in run}, key='一二三四五六七八九十'.find))
            used['P'] += 1
            pid = 'P%d' % used['P']
            parts.append({'id': pid, 'match': '^[%s]、' % nums, '_h1': list(run)})
            run.clear()

    for t in h1s:
        if re.match(r'^[一二三四五六七八九十]、', t):
            run.append(t)
            continue
        flush_run()
        if re.fullmatch(r'(目录|前言|目\s*录|\(前置\))', t):
            front = next((p for p in parts if p['id'] == 'FRONT'), None)
            if front is None:
                parts.insert(0, {'id': 'FRONT', 'match': None, '_h1': [t]})
            else:
                front['_h1'].append(t)
            continue
        m = re.match(r'^(附录\s?[一二三四五六七八九十A-Z0-9]*|第[一二三四五六七八九十]+部分|第[一二三四五六七八九十]+轮拓展|A[1-9]|专题[一二三四五六七八九十]+)', t)
        if m:
            key = m.group(1)
            pid = next(v for k, v in (('附录', 'APPX'), ('第', 'PART'), ('A', 'A'), ('专题', 'TOPIC')) if key.startswith(k))
            used[pid] += 1
            pid = pid + str(used[pid]) if pid != 'A' else key
            parts.append({'id': pid, 'match': '^' + re.escape(key), '_h1': [t]})
        else:
            used['X'] += 1
            parts.append({'id': 'X%d' % used['X'], 'match': '^' + re.escape(t[:6]), '_h1': [t]})
    flush_run()
    for p in parts:
        if p['id'] == 'FRONT':
            alts = sorted({re.escape(x) for x in p['_h1']} | {r'\(前置\)'})
            p['match'] = '^(%s)$' % '|'.join(alts)
    if not any(p['id'] == 'FRONT' for p in parts):
        parts.insert(0, {'id': 'FRONT', 'match': r'^\(前置\)$', '_h1': []})
    # 消除遮蔽：每个一级标题必须落到自己的部分；被前面部分抢走时，把抢的那个部分改成按标题前缀精确匹配
    for _ in range(len(parts)):
        changed = False
        for p in parts:
            for t in p['_h1']:
                q = next((x for x in parts if x['match'] and re.search(x['match'], t)), None)
                if q is not p and q is not None:
                    q['match'] = '^(%s)' % '|'.join(re.escape(x[:10]) for x in q['_h1'])
                    changed = True
        if not changed:
            break
    return parts


METHOD_LINE = r'[（(]共?\s*\d+\s*题[）)]\s*$|^其他例题'
BULLET_LINE = r'^[▪•·◆■]'


def _trailing_leadin(t):
    """题块末尾、紧挨下一题标题的短引导行（如“文化载体：用文化关系拆解观点”“书末细则例外题”）；选项行不算。"""
    return (1 <= len(t) <= 30 and not label_start(t) and not re.search(r'[。！？!?；;]$', t)
            and not re.match(r'^[A-DＡ-Ｄ]\s*[.．、]', t) and not re.search(r'[①-⑳]', t))


# ---------------------------------------------------------------- 主流程
def probe(docx, book_id=None, template='bixiu3', self_check=True, out_dir=None, calibrate=False):
    t0 = time.time()
    D = Draft()
    reg = BI.detect_book(docx)
    if reg and reg.get('frozen') and not calibrate:
        frozen_guard(reg, '对冻结册的 DOCX 生成配置草案（只做校准对照时加 --calibrate）')
    tpl = load_profile(template)
    z = zipfile.ZipFile(docx)
    sinfo = style_info(z)
    dp = doc_parts(z)
    doc = BI.load_docx(docx)
    paras = [r for r in doc['paras'] if not r['fallback']]
    census = basic_census(doc, dp, sinfo)
    use = Counter(r['style'] for r in paras if r['text'].strip())
    pos = {r['p']: i for i, r in enumerate(paras)}

    # ---- 一二级标题
    h1s, h2s = pick_headings(paras, sinfo, 1), pick_headings(paras, sinfo, 2)
    D.ev('styles.h1', {s: use[s] for s in h1s})
    D.ev('styles.h2', {s: use[s] for s in h2s})
    if not h1s:
        D.ask('styles.h1', '没有找到 heading 1/H1 类样式或大纲0级样式')
    if not h2s:
        D.ask('styles.h2', '没有找到 heading 2/H2 类样式或大纲1级样式')

    # ---- 书册识别（书名段优先；命中多本或只在正文命中时不自动选）
    ident = identify_book(paras, set(h1s), docx)
    meta_id, meta_by = None, None
    if book_id in BOOKS:
        meta_id, meta_by = book_id, '--book-id 指定'
        if ident['book'] and ident['book'] != book_id:
            D.ask('book_identity', f'--book-id={book_id}，但书名段/文件名识别为 {ident["book"]}'
                                   f'（命中 {ident["title_hits"]}）；随书册走的班课、规则文件等按 --book-id 取，需确认')
    elif ident['book']:
        meta_id, meta_by = ident['book'], ident['by']
    else:
        cands = list(ident['title_hits']) or list(ident['body_hits'])
        D.ask('book_identity', ('书名段/文件名命中多本：' + str(ident['title_hits']) if len(ident['title_hits']) > 1 else
                                '书名段/文件名没有命中书名关键词' + (f'，正文命中 {ident["body_hits"]}（正文命中不自动认书）'
                                                               if ident['body_hits'] else '')) +
              f'；候选 {cands or "无"}；班课、规则文件、协作册名、题库模块均留空，待确认书册后再填')
    ident['resolved'], ident['resolved_by'] = meta_id, meta_by
    meta = BOOKS.get(meta_id)
    bid = book_id or meta_id or re.sub(r'\W+', '_', Path(docx).stem)[:24]
    title_guess = next((r['text'].strip() for r in paras[:40] if r['text'].strip() and r['style'] not in h1s), None)
    if reg:
        D.ask('registered_profile', f'这份 DOCX 位于已登记书册 {reg.get("book_id")} 的目录里；草案只作校准对照，'
                                    f'不替代 profiles/{reg.get("book_id")}.json')

    # ---- 例题标题写法
    hits, fam_style = {}, defaultdict(Counter)
    for r in paras:
        t = r['text'].replace('\n', ' ').strip()
        if not t or r['tbl'] is not None or r['txbx'] or r['style'] in h1s or r['style'] in h2s:
            continue
        for fi, (k, rx, _) in enumerate(FAM_RX):
            if rx.match(t):
                hits[r['p']] = fi
                fam_style[fi][r['style']] += 1
                break
    stop_styles = set(h1s) | set(h2s)
    follow = defaultdict(Counter)
    for p, fi in hits.items():
        i = pos[p]
        ok = False
        for q in paras[i + 1:i + 41]:  # 选择题题干+选项表可能有几十段才到第一个栏目
            if q['p'] in hits or q['style'] in stop_styles:
                break
            if any(label_start(line) for line in q['text'].split('\n')):
                ok = True
                break
        follow[fi][paras[i]['style']] += ok
    accepted = defaultdict(list)
    fam_ev = []
    for fi, sc in fam_style.items():
        for st, n in sc.items():
            rate = follow[fi][st] / n
            # 题卡标题（A1-001｜…）写法独特，A1 卡片不带栏目标签，按数量认
            keep = n >= 3 and (rate >= 0.5 or FAMILIES[fi][0] in ('drill_card_a1', 'drill_card_a2'))
            fam_ev.append({'family': FAMILIES[fi][1], 'kind': FAMILIES[fi][0], 'style': st, 'count': n,
                           'label_follow_rate': round(rate, 3), 'accepted': keep})
            if keep:
                accepted[fi].append(st)
    # 兜底族数量少也认，但只认已是例题标题样式、且后面跟栏目标签的
    oth = next(i for i, f in enumerate(FAMILIES) if f[0] == 'other')
    known = {st for fi, sts in accepted.items() if fi != oth for st in sts}
    accepted.pop(oth, None)
    for e in fam_ev:
        if e['kind'] == 'other' and e['style'] in known and e['label_follow_rate'] >= 0.5:
            e['accepted'] = True
            accepted[oth].append(e['style'])
    D.ev('example_titles', fam_ev)
    title_styles_heading = sorted({st for fi, sts in accepted.items() for st in sts if heading_like(st, sinfo)})
    example_titles = []
    extra_fams = []
    for fi in sorted(accepted):
        k, rx, numbered = FAMILIES[fi]
        sts = accepted[fi]
        if k == 'other':
            # 兜底族按实际前缀拆成具名写法
            prefs = Counter(FAM_RX[fi][1].match(paras[pos[p]]['text'].replace('\n', ' ').strip()).group('prefix')
                            for p, f2 in hits.items() if f2 == fi and paras[pos[p]]['style'] in sts)
            for pref, n in prefs.items():
                if n >= 1:
                    e = OrderedDict([('kind', 'other_' + pref),
                                     ('regex', '^' + re.escape(pref) + r'\s*(?P<num>\d+)[\s　]+(?P<src>.+)$')])
                    if not all(s2 in title_styles_heading for s2 in sts):
                        e['styles'] = sorted(sts)
                    extra_fams.append(e)
                    D.ask(f'example_titles[other_{pref}]', f'兜底识别到“{pref} N”写法 {n} 处，题型归属需确认')
            continue
        e = OrderedDict([('kind', k), ('regex', rx)])
        if not all(s in title_styles_heading for s in sts):
            e['styles'] = sorted(sts)
        if not numbered:
            e['numbered'] = False
        example_titles.append(e)
    example_titles.extend(extra_fams)
    if not example_titles:
        D.ask('example_titles', '没有识别出例题标题写法')
    title_sample = next((paras[pos[p]]['text'].strip() for p, fi in hits.items()
                         if fi in accepted and paras[pos[p]]['style'] in accepted[fi]), None)
    sep = None
    if title_sample:
        m = re.match(r'^\D*?\d+([\s　]+)', title_sample)
        sep = m.group(1) if m else None

    # ---- 其余标题类角色
    title_pids = {p for p, fi in hits.items() if fi in accepted and paras[pos[p]]['style'] in accepted[fi]}
    method = ['具体考法'] if use.get('具体考法') else []
    if not method:
        mc = Counter(r['style'] for r in paras if r['tbl'] is None and re.match(r'^考法\s*\d+', r['text'].strip())
                     and r['style'] not in stop_styles and r['p'] not in title_pids)
        method = [s for s, n in mc.items() if n >= 3 and n >= 0.3 * use[s]]
    group = []
    gc, glab = Counter(), Counter()
    for r in paras:
        t = r['text'].strip()
        if not t or r['tbl'] is not None or r['p'] in title_pids or r['style'] in stop_styles or r['style'] in method:
            continue
        if heading_like(r['style'], sinfo) or r['style'] in title_styles_heading:
            gc[r['style']] += 1
            glab[r['style']] += label_start(t)
    group = sorted(s for s, n in gc.items() if n >= 2 and glab[s] / n < 0.5)
    D.ev('styles.group_heading', {s: gc[s] for s in group})
    trig = Counter(r['style'] for r in paras if r['text'].strip().startswith('【触发词速查】') and r['tbl'] is None)
    lstart = Counter(r['style'] for r in paras if r['tbl'] is None and label_start(r['text'].strip()))
    # 只认专用样式：该样式的段落里触发词行占一成以上或多数以栏目标签开头（正文样式不算）
    trigger_box = [s for s, n in trig.most_common() if s not in stop_styles and s not in title_styles_heading
                   and (n >= 0.1 * use[s] or lstart[s] >= 0.6 * use[s])][:2]
    if not trigger_box and use.get('触发词速查'):
        trigger_box = ['触发词速查']
    category_line = ['考法分类'] if use.get('考法分类') else []
    method_desc = ['考法说明'] if use.get('考法说明') else []
    toc_styles = sorted(s for s in use if ('toc' in s.lower() or '目录' in s) and s not in h1s)
    drill_group = ['错肢分组'] if use.get('错肢分组') else []

    # ---- 部分划分
    h1_texts = [r['text'].strip() for r in paras if r['style'] in h1s and r['text'].strip() and r['tbl'] is None]
    parts = cn_part_ids(h1_texts)
    card_kinds = {'drill_card_a1', 'drill_card_a2'}
    # 每个一级标题下是否有题卡/三列表/段落式单练
    h1_pos = [(pos[r['p']], r['text'].strip()) for r in paras if r['style'] in h1s and r['text'].strip() and r['tbl'] is None]
    item_rx = re.compile(r'^(\d+(?:（补\d+）)?)[、.．]\s*(.*)$', re.S)
    part_of_h1 = {}
    for p in parts:
        for t in p['_h1']:
            part_of_h1[t] = p
    drill_obs = {}
    for k, (i, t) in enumerate(h1_pos):
        j = h1_pos[k + 1][0] if k + 1 < len(h1_pos) else len(paras)
        seg = paras[i + 1:j]
        p = part_of_h1.get(t)
        if p is None:
            continue
        cards = sum(1 for r in seg if r['p'] in hits and FAMILIES[hits[r['p']]][0] in card_kinds)
        blanks = sum(1 for r in seg if r['tbl'] is not None and BI.squash(r['text']) in ('（　）', '()', '（）'))
        a2vals = Counter(BI.squash(r['text']) for r in seg if r['tbl'] is not None and r['col'] == 1
                         and BI.squash(r['text']) in ('正确', '错误', '不选', '对', '错'))
        para_items = sum(1 for r in seg if r['tbl'] is None and item_rx.match(r['text'].strip())
                         and r['style'] not in stop_styles)
        drillish = bool(re.search(r'题肢|单练|错肢', t))
        if drillish and not cards and (blanks >= 5 or para_items >= 10):
            p['drill'] = True
            src_lines = Counter(r['style'] for r in seg if r['tbl'] is None and len(r['text'].strip()) <= 60
                                and re.match(r'^\s*20\d\d.*第\s*\d{1,2}\s*题', r['text'].strip())
                                and not item_rx.match(r['text'].strip()))
            drill_obs[p['id']] = {'h1': t, 'table_blank_cells': blanks, 'table_answer_values': dict(a2vals),
                                  'paragraph_items': para_items,
                                  'layout': 'table3' if blanks >= 5 else 'paragraph',
                                  'item_styles': dict(Counter(r['style'] for r in seg if r['tbl'] is None
                                                              and item_rx.match(r['text'].strip())).most_common(4)),
                                  'source_line_styles': dict(src_lines.most_common(3)),
                                  'h2': [r['text'].strip() for r in seg if r['style'] in h2s][:6],
                                  'colors': dict(Counter(c for r in seg for c in r['colors']).most_common(6))}
        elif cards:
            p.setdefault('_cards', 0)
            p['_cards'] += cards

    # ---- 第一遍切块（暂不设栏目模式）
    prov_styles = {'h1': h1s, 'h2': h2s, 'example_title': title_styles_heading, 'group_heading': group,
                   'method': method, 'method_desc': method_desc, 'category_line': category_line,
                   'trigger_box': trigger_box, 'toc': toc_styles, 'drill_group': drill_group}
    first_drill = next(iter(drill_obs.values()), None)
    prov = {'styles': prov_styles, 'example_titles': example_titles,
            'structure': {'parts': [{k: v for k, v in p.items() if not k.startswith('_')} for p in parts]},
            'column_schemas': {}, 'drill': {'layout': first_drill['layout']} if first_drill else {}}
    cfg = BI.BookCfg(prov)
    raw_blocks, drill_rows, heads, wstats = BI.walk(doc, cfg)
    blocks = BI.finish_blocks(raw_blocks, doc, cfg)
    drill_pids = {p['id'] for p in parts if p.get('drill')}
    part_at, cur_part = {}, 'FRONT'
    for r in paras:
        if r['style'] in h1s and r['text'].strip():
            cur_part = cfg.part_of(r['text'].strip())['id']
        part_at[r['p']] = cur_part

    # ---- 题型按栏目改判（主观/选择同名“例题N”时）
    kind_by_labels = {}
    for fk in {e['kind'] for e in example_titles}:
        bs = [b for b in blocks if b['kind'] == fk]
        if len(bs) < 10 or fk in ('choice',) or fk in card_kinds:
            continue
        has_ans = [b for b in bs if b['other_labels'].get('【答案落点】')]
        without = [b for b in bs if not b['other_labels'].get('【答案落点】')]
        if len(has_ans) >= 0.05 * len(bs) and len(without) >= 0.05 * len(bs):
            lab_w = Counter(L for b in without for L in b['other_labels'])
            lab_a = Counter(L for b in has_ans for L in b['other_labels'])
            marks = [L for L, n in lab_w.most_common() if n >= 0.8 * len(without) and lab_a.get(L, 0) <= 0.05 * len(has_ans)
                     and L not in SOURCE_LABELS]
            if marks:
                kind_by_labels['choice'] = marks
                kind_by_labels.setdefault('_apply_to', []).append(fk)
                D.ev('example_kind_by_labels', {'title_kind': fk, 'with_答案落点': len(has_ans),
                                                'without': len(without), 'choice_markers': marks})
                D.ask('example_kind_by_labels', f'“{fk}”写法的标题下有 {len(without)} 块带 {marks}、无【答案落点】，'
                                                f'草案按栏目把它们改判为选择题（{len(has_ans)} 块保持主观题）；本册题型划分需确认')
    if kind_by_labels:
        for b in blocks:
            if b['kind'] in kind_by_labels['_apply_to'] and any(b['other_labels'].get(L) for L in kind_by_labels['choice']):
                b['kind'] = 'choice'

    # ---- 各部分栏目模式（行首标签为主；紧跟句末标点写在行中的同名标签也计入出现）
    schemas, schema_names, part_schema = OrderedDict(), {}, defaultdict(dict)
    by_pk = defaultdict(list)
    for b in blocks:
        by_pk[(b['part'], b['kind'])].append(b)
    sc_ev = {}
    for (pid, kind), bs in by_pk.items():
        n = len(bs)
        if n < 3:
            sc_ev[f'{pid}|{kind}'] = {'blocks': n, 'note': '题块少于3个，不推栏目模式'}
            D.ask(f'structure.parts[{pid}].schema.{kind}', f'该部分“{kind}”只有 {n} 个题块，栏目模式无法统计')
            continue
        freq, inl_only, rep, order = Counter(), Counter(), Counter(), defaultdict(list)
        for b in bs:
            labs, inl = b['other_labels'], b['inline_labels']
            for L in set(labs) | set(inl):
                if labs.get(L):
                    freq[L] += 1
                    rep[L] += labs[L] > 1
                else:
                    inl_only[L] += 1
            for k2, L in enumerate(ordered_labels(b['_recs'])):
                order[L].append(k2)
        anyf = freq + inl_only
        core = [L for L in anyf if anyf[L] >= 0.6 * n]
        optional = [L for L in anyf if 0.25 * n <= anyf[L] < 0.6 * n and (L in SOURCE_LABELS or anyf[L] >= 5)]
        labels = sorted(core + optional, key=lambda L: statistics.median(order[L]) if order[L] else 10 ** 6)
        repeatable = [L for L in core if rep[L] >= 0.1 * n]
        sd = OrderedDict([('labels', labels), ('mode', 'at_least_once' if repeatable else 'each_once')])
        if optional:
            sd['optional'] = optional
        if repeatable:
            sd['repeatable'] = repeatable
        inl_used = {L: inl_only[L] for L in labels if inl_only[L]}
        if inl_used:
            sd['labels_inline'] = True
        sig_ = json.dumps(sd, ensure_ascii=False, sort_keys=True)
        if sig_ not in schema_names:
            name = f'{pid.lower()}_{kind}'
            schema_names[sig_] = name
            schemas[name] = sd
        part_schema[pid][kind] = schema_names[sig_]
        sc_ev[f'{pid}|{kind}'] = {'blocks': n, 'label_block_freq': {L: freq[L] for L in labels},
                                  'label_inline_only_blocks': inl_used,
                                  'repeat_blocks': {L: rep[L] for L in labels if rep[L]}}
        if optional:
            D.ask(f'column_schemas.{schema_names[sig_]}.optional',
                  f'这些栏目只在 25%–60% 的题块出现：{"、".join(optional)}；是可选栏目还是缺栏，需主代理判断')
        if inl_used:
            D.ask(f'column_schemas.{schema_names[sig_]}.labels_inline',
                  '、'.join(f'{L} 在 {c}/{n} 块里写在行中（紧跟句末标点，如“【答案】 D。【解析】 …”）' for L, c in inl_used.items())
                  + '；草案设 labels_inline=true 计入栏目，本册是否允许这种写法需确认')
    D.ev('column_schemas', sc_ev)

    # ---- 题块外的题面类栏目段、题块末尾的短引导行（常见于标题样式不在草案里、或分组行被并进前一块）
    in_block = {r['p'] for b in blocks for r in b['_recs'][1:]}
    title_p = {b['_recs'][0]['p'] for b in blocks}
    bcount = Counter(b['part'] for b in blocks)
    out_src, out_src_ex = Counter(), defaultdict(list)
    last_head = ''
    for r in paras:
        t = r['text'].strip()
        if r['style'] in stop_styles and t:
            last_head = t
        if not t or r['p'] in in_block or r['p'] in title_p or part_at.get(r['p']) in drill_pids or r['style'] in toc_styles:
            continue
        labs = BI._labels_in(r['text'])
        if labs and labs[0] in SOURCE_LABELS:
            pid = part_at.get(r['p'])
            out_src[pid] += 1
            if len(out_src_ex[pid]) < 3:
                out_src_ex[pid].append({'p': r['p'], 'label': labs[0], 'under_heading': last_head[:40]})
    for pid, n in out_src.items():
        if bcount.get(pid, 0) == 0:
            D.ask(f'structure.parts[{pid}]', f'该部分有 {n} 个题面类栏目段（{out_src_ex[pid][0]["label"]}等）却切出 0 个题块；'
                                             f'题目标题可能用了二级标题等未进草案的样式，如“{out_src_ex[pid][0]["under_heading"]}”')
        else:
            D.ask(f'structure.parts[{pid}].blocks_outside', f'该部分有 {n} 个题面类栏目段落在题块外（首例 p{out_src_ex[pid][0]["p"]}，'
                                                            f'所在标题“{out_src_ex[pid][0]["under_heading"]}”），可能漏切题块')
    D.ev('source_labels_outside_blocks', {pid: {'count': n, 'examples': out_src_ex[pid]} for pid, n in out_src.items()})
    skip_st = stop_styles | set(title_styles_heading) | set(group) | set(method) | set(method_desc) | \
        set(category_line) | set(trigger_box) | set(toc_styles) | set(drill_group)
    s_in, s_out, s_tail, s_meth, s_bul, s_ex = Counter(), Counter(), Counter(), Counter(), Counter(), defaultdict(list)
    tail_p = {}
    nonempty = [r for r in paras if r['text'].strip()]
    next_ne = {nonempty[i]['p']: nonempty[i + 1]['p'] for i in range(len(nonempty) - 1)}
    for b in blocks:
        ne = [r for r in b['_recs'][1:] if r['text'].strip()]
        if ne and next_ne.get(ne[-1]['p']) in title_p:  # 块末段紧挨下一题标题
            tail_p[ne[-1]['p']] = b['id']
    for r in paras:
        t = r['text'].strip()
        if not t or r['tbl'] is not None or r['p'] in title_p or r['style'] in skip_st or part_at.get(r['p']) in drill_pids:
            continue
        if r['p'] in in_block:
            s_in[r['style']] += 1
            if r['p'] in tail_p and _trailing_leadin(t):
                s_tail[r['style']] += 1
                s_meth[r['style']] += bool(re.search(METHOD_LINE, t))
                s_bul[r['style']] += bool(re.match(BULLET_LINE, t))
                if len(s_ex[r['style']]) < 3:
                    s_ex[r['style']].append({'block': tail_p[r['p']], 'p': r['p'], 'text': t[:30]})
        else:
            s_out[r['style']] += 1
    block_end = []
    for st, nt in s_tail.items():
        tot = s_in[st] + s_out[st]
        if s_out[st] < 0.1 * tot and s_meth[st] < 3 and s_bul[st] < 3:
            continue  # 几乎只在题块内用的正文样式（如分析过程），块末短句是正文，不报
        if s_out[st] >= 3 and s_out[st] >= 0.8 * tot and nt == s_in[st]:
            # 专用样式多在题块外，题块内的几处全是块末短引导行：推断为分组/边界样式
            block_end.append(OrderedDict([('styles', [st]), ('regex', r'^(?!【)[^。！？!?；;]{1,30}$'),
                                          ('_note', 'profile_probe 推断：此样式多在题块外，题块内只出现在块末、紧挨下一题标题')]))
            D.ask(f'structure.block_end[{st}]', f'样式“{st}”共 {tot} 段，{s_out[st]} 段在题块外，题块内 {nt} 段都是块末短引导行'
                                                f'（如 {s_ex[st][0]["block"]} 末尾“{s_ex[st][0]["text"]}”），草案设为题块边界；'
                                                f'也可能是分组/考法行，需确认')
        elif s_bul[st] >= 3 and s_bul[st] >= 0.5 * nt:
            block_end.append(OrderedDict([('styles', [st]), ('regex', BULLET_LINE),
                                          ('_note', 'profile_probe 推断：“▪ 小标题”一类分组行，结束上一题块')]))
            D.ask(f'structure.block_end[{st}]', f'样式“{st}”有 {s_bul[st]} 段“▪ …”分组行落在题块末尾'
                                                f'（如 {s_ex[st][0]["block"]} 末尾“{s_ex[st][0]["text"]}”），草案设为题块边界，需确认'
                                                + (f'；另有 {nt - s_bul[st]} 段其他短引导行未处理' if nt > s_bul[st] else ''))
        elif s_meth[st] >= 3 and s_meth[st] >= 0.5 * nt:
            # 正文样式写的考法/分组行（“……（共N题）”“其他例题……”）被并进前一块：按行文模式设边界
            block_end.append(OrderedDict([('styles', [st]), ('regex', METHOD_LINE),
                                          ('_note', 'profile_probe 推断：正文样式写的考法/分组行，结束上一题块')]))
            D.ask(f'structure.block_end[{st}]', f'样式“{st}”有 {s_meth[st]} 段形如“……（共N题）/其他例题……”的考法/分组行落在题块末尾'
                                                f'（如 {s_ex[st][0]["block"]} 末尾“{s_ex[st][0]["text"]}”），草案按行文模式设为题块边界；'
                                                f'也可改登记为考法样式，需确认'
                                                + (f'；另有 {nt - s_meth[st]} 段其他短引导行未处理' if nt > s_meth[st] else ''))
        else:
            D.ask(f'structure.trailing_leadin[{st}]', f'样式“{st}”有 {nt} 段短引导行落在题块末尾、紧挨下一题标题'
                                                      f'（如 {s_ex[st][0]["block"]} 末尾“{s_ex[st][0]["text"]}”），'
                                                      f'可能属于下一题的分组/考法行而被并进前一块；草案未改，需确认')
    D.ev('trailing_leadins', {st: {'in_block': s_in[st], 'outside': s_out[st], 'trailing': n, 'examples': s_ex[st]}
                              for st, n in s_tail.items()})

    # ---- 编号重置层级
    heads_by_p = sorted((h['p'], h['level']) for h in heads)
    hp = [p for p, _ in heads_by_p]
    reset_ev = {}
    for p in parts:
        res, non = Counter(), Counter()
        last = {}
        for b in blocks:
            if b['part'] != p['id'] or b['num'] is None:
                continue
            k = b['kind']
            prev = last.get(k)
            lo = prev if prev is not None else -1
            a, z2 = bisect.bisect_right(hp, lo), bisect.bisect_left(hp, b['p_range'][0])
            lv = {heads_by_p[x][1] for x in range(a, z2)}
            if prev is None:
                lv |= {'h1'}
            (res if b['num'] == 1 else non).update(lv)
            last[k] = b['p_range'][0]
        levels = [L for L in ('h2', 'group', 'method') if res[L] and not non[L]]
        if res or non:
            reset_ev[p['id']] = {'reset_after': dict(res), 'no_reset_after': dict(non)}
            p['numbering_reset'] = [{'group': 'group_heading'}.get(L, L) for L in levels]
            if not levels and non:
                D.ask(f'structure.parts[{p["id"]}].numbering_reset', '看不出编号在哪一级标题处重新起算（可能全部分连续编号）')
    D.ev('numbering', reset_ev)

    # 按题型分开编号还是混编
    per_kind_ok = mixed_ok = 0
    seen_k, seen_all, cur_scope = {}, 0, None
    for b in blocks:
        if b['num'] is None:
            continue
        scope = (b['part'], b['h1'], b['h2'])
        if scope != cur_scope:
            seen_k, seen_all, cur_scope = {}, 0, scope
        per_kind_ok += b['num'] == seen_k.get(b['kind'], 0) + 1
        mixed_ok += b['num'] == seen_all + 1
        seen_k[b['kind']] = b['num']
        seen_all = b['num']
    per_kind = per_kind_ok >= mixed_ok
    if not per_kind:
        D.ask('numbering.per_kind', f'编号按“主观、选择混编”吻合 {mixed_ok} 处、按题型分开吻合 {per_kind_ok} 处，'
                                    f'草案设 per_kind=false；是否为本册既定编号规则需确认')

    # ---- 考法（N题）口径
    count_rx = re.compile(r'（(\d+)题）\s*$')
    bearers = [h for h in heads if h['level'] in ('method', 'group')]
    with_n = [h for h in bearers if count_rx.search(h['text'])]
    method_count = OrderedDict()
    if with_n:
        bstyles = sorted({paras[pos[h['p']]]['style'] for h in with_n})
        hyp = {'subjective': {'subjective'}, 'subjective+choice': {'subjective', 'choice'},
               'all': {b['kind'] for b in blocks}}
        scores = {}
        for name, kinds in hyp.items():
            for unit in ('blocks', 'unique_questions'):
                ok = 0
                for h in with_n:
                    claimed = int(count_rx.search(h['text']).group(1))
                    a = h['p']
                    nxt = next((x['p'] for x in heads if x['p'] > a and x['level'] in ('h1', 'h2', 'method', 'group')), 10 ** 9)
                    bs = [b for b in blocks if a < b['p_range'][0] < nxt and b['kind'] in kinds]
                    actual = len(bs) if unit == 'blocks' else len({b['key'] or b['src'] for b in bs})
                    ok += actual == claimed
                scores[(name, unit)] = ok
        (bk, bu), best = max(scores.items(), key=lambda kv: kv[1])
        method_count = OrderedDict([('regex', count_rx.pattern), ('bearer_styles', bstyles),
                                    ('count_kinds', sorted(hyp[bk])), ('unit', bu),
                                    ('scope_end', ['h1', 'h2', 'method'] + (['group_heading'] if group else []))])
        D.ev('method_count', {'bearers_with_count': len(with_n), 'bearers_total': len(bearers),
                              'match_by_hypothesis': {f'{a}|{b}': v for (a, b), v in scores.items()}})
        if best < len(with_n):
            D.ask('method_count.count_kinds', f'最佳口径下仍有 {len(with_n) - best}/{len(with_n)} 个考法标称题数对不上')

    # ---- 节点级栏目
    sec = Counter()
    for r in paras:
        if r['p'] in in_block or r['p'] in title_p or part_at.get(r['p']) in drill_pids or r['style'] in toc_styles:
            continue
        sec.update(BI._labels_in(r['text']))
    schema_labels = {L for s in schemas.values() for L in s['labels']}
    section_labels = [L for L, n in sec.most_common(30) if n >= 2 and L not in schema_labels]

    # ---- 题面/教学/细则区的样式
    zone_st = defaultdict(Counter)
    rub = {L for L in schema_labels if '细则' in L}
    for b in blocks:
        zone = 'source'
        for r in b['_recs'][1:]:
            if r['tbl'] is not None:
                continue
            labs = BI._labels_in(r['text'])
            if labs:
                L = labs[0]
                zone = 'source' if L in SOURCE_LABELS else ('rubric' if L in rub else 'teaching')
            if r['text'].strip():
                zone_st[zone][r['style']] += 1

    def role(zone):
        tot = sum(zone_st[zone].values())
        return [s for s, n in zone_st[zone].most_common(6) if tot and n >= 0.02 * tot]
    D.ev('styles.zones', {z: dict(c.most_common(6)) for z, c in zone_st.items()})

    # ---- 目录
    first_body = next((pos[r['p']] for r in paras if r['style'] in h1s and part_at.get(r['p']) not in ('FRONT',)), len(paras))
    toc_entries = [r for r in paras[:first_body] if (r['style'] in toc_styles or r['anchor']) and re.search(r'\d+\s*$', r['text'])]
    toc = OrderedDict()
    if toc_entries:
        pageref = sum(1 for r in toc_entries if 'PAGEREF' in (r['instr'] or ''))
        anchors = sum(1 for r in toc_entries if r['anchor'])
        tocfield = any('TOC' in (r['instr'] or '') for r in paras[:first_body])
        mode = 'pageref_in_hyperlink' if pageref else ('hyperlink_static' if anchors else ('toc_field' if tocfield else 'static_text'))
        # 目录条目若用正文样式，不写进 toc.styles（下游体检会把这些样式整段跳过）
        toc = OrderedDict([('mode', mode), ('styles', sorted({r['style'] for r in toc_entries} & set(toc_styles))),
                           ('entries_expected', len(toc_entries)), ('page_from', 'pdf_link_destination' if anchors else None)])
        if not toc_styles:
            toc['entry_by'] = 'hyperlink_anchor'
        D.ev('toc', {'entries': len(toc_entries), 'with_anchor': anchors, 'with_pageref': pageref,
                     'entry_styles': dict(Counter(r['style'] for r in toc_entries)),
                     'dedicated_styles': toc_styles, 'sample': [r['text'][:30] for r in toc_entries[:3]]})
        if not toc_styles:
            D.ask('toc.styles', '目录条目用的是正文样式（无专用目录样式），体检时按超链接识别还是改样式，需确认')
        D.ask('toc.toc_pdf_pages', '目录在 PDF 第几页需对照同版 PDF 确认')
    else:
        D.ask('toc', '没有识别出目录条目')

    # ---- 页脚
    ft = [v for k, v in census['footers'].items() if 'footer' in k and (v['text'].strip() or v['fields'])]
    has_page = any(any('PAGE' in f for f in v['fields']) for v in ft)
    dash = any('—' in v['text'] for v in ft)
    footer = OrderedDict([('regex', r'—\s*(\d+)\s*—' if dash else (r'^\s*(\d+)\s*$' if has_page or ft else None)),
                          ('exempt_pages', [1] if dp['title_pg'] else []), ('page_offset', 0), ('continuous', True)])
    D.ev('footer', {'footer_parts': {k: v for k, v in census['footers'].items() if 'footer' in k},
                    'sections': dp['sections'], 'title_pg': dp['title_pg']})
    if not ft:
        D.ask('footer.regex', '页脚里没有页码域或文字')
    D.ask('footer.exempt_pages', '封面是否显示页码属用户规则（必修二豁免第1页、必修三未豁免），需确认' +
          ('；本稿首节设了首页不同' if dp['title_pg'] else ''))
    if dp['sections'] > 1:
        D.ask('footer.continuous', f'本稿有 {dp["sections"]} 节，页码是否连续需对照 PDF')

    # ---- 单练
    drill = OrderedDict()
    if drill_obs:
        pid, ob = next(iter(drill_obs.items()))
        tdr = tpl.get('drill', {})
        drill = OrderedDict([('layout', ob['layout'])])
        if ob['layout'] == 'table3':
            drill.update([('columns', 3), ('stem_col', 0), ('answer_col', 1), ('source_col', 2)])
        drill['item_regex'] = tdr.get('item_regex')
        if ob['layout'] == 'table3':
            drill['a1_blank'] = '（　）'
        drill['a2_allowed'] = ['正确', '错误']
        drill['correction_marker'] = '纠正：'
        drill['colors'] = OrderedDict([('error_run', 'C00000'), ('correction', '008000')])
        drill['a1_forbid'] = tdr.get('a1_forbid')
        drill['intro_forbidden'] = tdr.get('intro_forbidden')
        drill['part'] = pid
        a1 = [h for h in ob['h2'] if 'A1' in h or '打印' in h]
        a2 = [h for h in ob['h2'] if 'A2' in h or '答案' in h or '纠正' in h]
        drill['a1_heading'] = a1[0] if a1 else D.ask('drill.a1_heading', '单练部分没有找到 A1/打印 二级标题')
        drill['a2_heading'] = a2[0] if a2 else D.ask('drill.a2_heading', '单练部分没有找到 A2/答案 二级标题')
        if drill_group:
            drill['group_style'] = drill_group[0]
        if ob['layout'] == 'paragraph' and ob['source_line_styles']:
            drill['source_styles'] = sorted(ob['source_line_styles'])
        drill['alternation'] = {'required': False}
        drill['each_table_has_both'] = False
        D.ev('drill', ob)
        D.ask('drill.alternation', '正误交替规则只登记在必修二，本册是否推广由用户定')
        if ob['table_answer_values'].get('不选'):
            D.ask('drill.a2_allowed', f'单练答案列出现“不选”{ob["table_answer_values"]["不选"]}处；单练不用“不选”（解析里可用），需主代理处理')
        if ob['layout'] == 'paragraph':
            D.ask('drill.layout', '段落式单练（错肢训练/错肢纠正），正误由红色与纠正段表示，block_index 只取条目不判正误'
                                  + ('；条目前有题源行，按 source_styles 取为条目来源' if ob['source_line_styles']
                                     else '；条目不带题源，--key/--src 选不到题肢'))
    else:
        cards = [p['id'] for p in parts if p.get('_cards')]
        if cards:
            drill = OrderedDict([('layout', 'cards'), ('part', cards),
                                 ('_note', 'A1/A2 以整题卡片呈现（题卡标题作例题块索引），不是逐肢三列表')])
            D.ask('drill', f'单练为题卡形式（部分 {cards}），A1/A2 闭环口径需按本册规则另定')
        else:
            D.ask('drill', '没有识别出题肢单练部分')

    # ---- 字体角色（样式级观测值）
    def tinfo(st):
        i = sinfo.get(st) or {}
        return OrderedDict((k, i.get(k)) for k in ('ea', 'ascii', 'pt', 'bold', 'color') if i.get(k) not in (None, False))
    src_role, teach_role, rub_role = role('source'), role('teaching'), role('rubric')
    typography = OrderedDict([('_note', 'style 级观测值；运行级格式可能覆盖，改字体前须同时扫运行级')])
    for k, sts in (('h1', h1s), ('h2', h2s), ('example_title', title_styles_heading), ('material', src_role),
                   ('stem_teaching', teach_role), ('rubric', rub_role)):
        if sts:
            typography[k] = tinfo(sts[0])
            typography[k]['_style'] = sts[0]

    # ---- 分页
    kn = Counter(r['style'] for r in paras if r['keep_next'])
    pb = Counter(r['style'] for r in paras if r['page_break_before'])
    pagination = OrderedDict([
        ('keep_next', None), ('keep_next_label_regex', tpl.get('pagination', {}).get('keep_next_label_regex')),
        ('keep_next_target_style', src_role[0] if src_role else None), ('forbid_long_chains', True),
        ('forced_breaks_only', None), ('blank_threshold_ratio', tpl.get('pagination', {}).get('blank_threshold_ratio'))])
    D.ev('pagination', {'keepNext_direct_by_style': dict(kn.most_common(10)), 'pageBreakBefore_by_style': dict(pb)})
    D.ask('pagination.keep_next', '本册与标题/材料小标题的 keepNext 口径需按本册排版规则确认')
    D.ask('pagination.forced_breaks_only', f'本稿强制分页出现在样式 {dict(pb)}，哪些是允许的强制分页需确认')

    # ---- 路径、题源、规则引用等只能人工给的字段（书册未确认时随书册走的字段一律留空）
    root = Path(tpl['paths']['root'])
    dpar = Path(docx).resolve().parent
    try:
        ws = str(dpar.relative_to(root))
    except ValueError:
        ws = str(dpar)
    state = next((str(c) for c in (dpar / '当前状态.json', dpar.parent / '当前状态.json') if c.exists()), None)
    refs = root / '00_共同资料/原材料/宝典制作原料'
    banke = []
    if meta and refs.is_dir():
        banke = sorted(str(Path('00_共同资料/原材料/宝典制作原料') / f.name) for f in refs.iterdir()
                       if f.suffix.lower() == '.pdf' and any(k in f.name for k in meta[3]) and '班课' in f.name)
    skill_refs = Path(__file__).resolve().parent.parent / 'references'
    rule_book = f'references/{meta[2]}' if meta and (skill_refs / meta[2]).exists() else None
    act = rule_book.replace('references/', 'references/active/').replace('.md', '-current.md') if rule_book else None
    if act and not (skill_refs.parent / act).exists():
        act = None
    collab = meta[0] if meta else None

    draft = OrderedDict()
    draft['schema'] = tpl.get('schema', 'baodian-book-profile/0.1')
    draft['book_id'] = bid
    draft['title'] = title_guess
    D.ask('title', '书名取自封面首段，需按本册正式书名确认')
    draft['collab_key'] = collab
    D.ask('collab_key', (f'按书册 {meta_id}（{meta_by}）取为“{collab}”，需与 collab books.json 对齐' if collab
                         else '书册未确认，协作册名（books.json 键）留空'))
    draft['frozen'] = bool(reg.get('frozen')) if (reg and calibrate) else False
    if reg and calibrate and reg.get('frozen'):
        draft['frozen_note'] = reg.get('frozen_note')
    draft['rule_refs'] = OrderedDict([('book', rule_book), ('active', act), ('style', None)])
    D.ask('rule_refs', ('规则文件按书册取' if rule_book else ('书册未确认，规则文件留空' if not meta else '未找到对应 book-*.md'))
          + '；style-spec 锚点需人工指定')
    draft['paths'] = OrderedDict([('root', str(root)), ('workspace', ws), ('central_state', state),
                                  ('review_entry', None), ('review_manifest', None), ('review_history', None),
                                  ('candidate_dir_pattern', None), ('build_subdir', '构建'), ('handoff', None)])
    for k, why in (('workspace', '取自样稿所在目录；本册真实工作头未核定（books.json 标“未核定真实工作头”）'),
                   ('central_state', '中央状态文件' + ('按样稿旁的当前状态.json 猜测' if state else '未找到')),
                   ('review_entry', '本册审阅入口尚未设立'), ('review_manifest', '随审阅入口定'),
                   ('review_history', '随审阅入口定'), ('candidate_dir_pattern', '候选目录命名需按协作规则定'),
                   ('handoff', '协作/接管.json 位置需定')):
        D.ask(f'paths.{k}', why)
    draft['naming'] = OrderedDict([('batch_label', None), ('docx_stem', None), ('feedback_hint', None)])
    D.ask('naming', f'批次与文件命名需按本册习惯定（样稿文件名：{Path(docx).name}）')
    tsrc = tpl.get('sources', {})
    draft['sources'] = OrderedDict([
        ('roots', tsrc.get('roots')), ('banke', banke),
        ('banke_priority', tsrc.get('banke_priority')),
        ('bank', OrderedDict([('root', (tsrc.get('bank') or {}).get('root')), ('module_hint', meta[1] if meta else None)])),
        ('answer_only_choice_only', tsrc.get('answer_only_choice_only')),
        ('no_e1_exceptions', None), ('stem_module_guard', None)])
    if not meta:
        D.ask('sources.banke', '书册未确认，班课讲义留空；班课是最高优先级原料，确认书册后再按书名找')
    elif banke:
        D.ask('sources.banke', f'按书册 {meta_id} 的文件名关键词 {meta[3]} 找到班课讲义：' + '、'.join(Path(b).name for b in banke))
    else:
        D.ask('sources.banke', f'宝典制作原料里没找到 {meta_id} 的班课讲义（关键词 {meta[3]}）；'
                               '班课是最高优先级原料，需用户提供或确认本册没有')
    D.ask('sources.bank.module_hint', f'题库模块提示按书册 {meta_id} 取' if meta else '书册未确认，题库模块提示留空')
    D.ask('sources.no_e1_exceptions', '无 E1 例外名单是本册证据裁定，不能从样稿推')
    D.ask('sources.stem_module_guard', '设问限定他册的过滤名单需主代理定')
    styles_out = OrderedDict([('_note', '按 w:name 匹配；由 profile_probe 按使用量与结构推断')])
    styles_out.update(OrderedDict([
        ('h1', h1s), ('h2', h2s), ('example_title', title_styles_heading), ('group_heading', group),
        ('method', method), ('method_desc', method_desc), ('category_line', category_line),
        ('trigger_box', trigger_box), ('toc', toc_styles), ('source', src_role), ('teaching', teach_role),
        ('rubric', rub_role), ('drill_group', drill_group)]))
    if doc['default_style'] and any(doc['default_style'] in x for x in (src_role, teach_role, rub_role)):
        D.ask('styles.source', f'题面/教学区有大量默认样式“{doc["default_style"]}”段落，不能据样式判断分区，体检应按结构分区')
    draft['styles'] = styles_out
    parts_out = []
    for p in parts:
        q = OrderedDict([('id', p['id']), ('match', p['match'])])
        if p.get('drill'):
            q['drill'] = True
        else:
            q['schema'] = dict(part_schema.get(p['id'], {}))
        if p.get('numbering_reset'):
            q['numbering_reset'] = p['numbering_reset']
        q['_h1'] = p['_h1'][:6]
        parts_out.append(q)
    draft['structure'] = OrderedDict([('framework', None), ('parts', parts_out), ('block_end', block_end)])
    D.ask('structure.framework', '本册框架描述需人工写')
    D.ask('structure.parts', '部分按一级标题前缀自动归并（连续“一、二、……”并为一部分），部分名与边界需确认')
    draft['example_titles'] = example_titles
    draft['title_format'] = OrderedDict([('sep', sep), ('example', title_sample),
                                         ('cross_module_suffix', '（跨模块）' if any('跨模块' in b['src'] for b in blocks) else None)])
    draft['column_schemas'] = schemas
    draft['section_labels'] = section_labels
    draft['labels_rules'] = OrderedDict([('rubric_labels', sorted(rub)),
                                         ('source_labels', [L for L in SOURCE_LABELS if L in schema_labels])])
    unnum = sorted({e['kind'] for e in example_titles if e.get('numbered') is False})
    draft['numbering'] = OrderedDict([('per_kind', per_kind), ('scope_default', 'h2')] +
                                     ([('unnumbered_kinds', unnum)] if unnum else []))
    D.ev('numbering.per_kind', {'per_kind_consistent': per_kind_ok, 'mixed_consistent': mixed_ok})
    draft['method_count'] = method_count
    if not method_count:
        D.ask('method_count', '没有带（N题）的考法标题；本册是否标题数需确认')
    tst = tpl.get('student_text', {})
    draft['student_text'] = OrderedDict([
        ('forbidden_words_book', []), ('allow_contexts', {}),
        ('trailing_tag_exempt_styles', sorted(set(category_line + rub_role + h1s + h2s))),
        ('_common_note', tst.get('_common_note') or '通用禁用词在 _house.json')])
    D.ask('student_text.forbidden_words_book', '本册专属禁用词需按本册规则登记')
    if kind_by_labels:
        draft['example_kind_by_labels'] = kind_by_labels
    draft['drill'] = drill
    draft['toc'] = toc
    draft['footer'] = footer
    cover = [s for s in use if s.lower().startswith('cover')]
    pre = next((r for r in paras if r['style'] in h1s and r['text'].strip() == '前言'), None)
    draft['cover_preface'] = OrderedDict([('cover', None), ('preface', None)])
    D.ask('cover_preface.cover', '封面由用户手工处理还是用稿内封面' + (f'（稿内有封面样式 {cover}）' if cover else ''))
    D.ask('cover_preface.preface', ('稿内有“前言”一级标题' if pre else '稿内没有“前言”一级标题') + '；前言保留与否属用户规则')
    draft['typography'] = typography
    draft['pagination'] = pagination
    rnd = json.loads(json.dumps(tpl.get('render', {}), ensure_ascii=False))
    if rnd.get('fontconfig'):
        rnd['fontconfig']['historical_file'] = None
        rnd['fontconfig']['historical_sha256_prefix'] = None
    draft['render'] = rnd
    D.ask('render.fontconfig', '本册 fontconfig（字体目录与别名）需按本册字体环境确认；沿用了必修三的渲染器配置')
    draft['pixel'] = tpl.get('pixel')
    pub = json.loads(json.dumps(tpl.get('publish', {}), ensure_ascii=False))
    pub['entry'] = None
    pub['archive_to'] = None
    pub.pop('central_state_backup', None)
    draft['publish'] = pub
    D.ask('publish.entry', '发布入口随审阅入口定')
    D.ask('publish.archive_to', '归档目录随审阅历史目录定')
    draft['handoff'] = OrderedDict([('collab_book', collab), ('owner_file', '协作/接管.json'),
                                    ('checkpoint_fields', (tpl.get('handoff') or {}).get('checkpoint_fields'))])
    D.ask('handoff.collab_book', '协作册名需与 collab books.json 对齐' if collab else '书册未确认，协作册名留空')
    draft['pdf_fonts'] = OrderedDict([('expected_cjk_regex', None),
                                      ('_note', '本册 PDF 嵌入中文字体的预期；_house.json 缺省 ^(STSongti|STKaiti)')])
    D.ask('pdf_fonts.expected_cjk_regex', '本册 PDF 嵌入中文字体预期需对照同版 PDF 与本册 fontconfig 确认')
    draft['_needs_confirm'] = D.confirm
    draft['_probe'] = OrderedDict([
        ('tool', 'profile_probe.py'), ('docx', str(Path(docx).resolve())), ('docx_sha256', BI.sha256_file(docx)),
        ('template', template), ('generated', time.strftime('%Y-%m-%d %H:%M:%S')),
        ('book_identity', ident), ('registered_profile', reg.get('book_id') if reg else None),
        ('calibration_only', bool(calibrate and reg)),
        ('note', '草案：推断字段附证据见 .probe.json；_needs_confirm 里的字段须人工确认后才能登记进 profiles/')])

    admin = ('title', 'collab_key', 'rule_refs', 'paths.', 'naming', 'sources.', 'structure.framework', 'student_text.',
             'cover_preface.', 'render.', 'publish.', 'handoff.', 'pagination.', 'pdf_fonts', 'book_identity',
             'registered_profile')
    kinds = Counter('人工登记（样稿推不出）' if k.startswith(admin) else '结构推断存疑' for k in D.confirm)
    report = OrderedDict([('tool', 'profile_probe.py'), ('docx', draft['_probe']['docx']), ('book_id', bid), ('book_identity', ident),
                          ('census', census), ('evidence', D.evidence), ('needs_confirm', D.confirm),
                          ('needs_confirm_count', len(D.confirm)), ('needs_confirm_by_kind', dict(kinds)),
                          ('first_pass', {'blocks': len(blocks), 'by_part_kind': {f'{a}|{b}': len(v) for (a, b), v in by_pk.items()},
                                          'walk_stats': dict(wstats), 'drill_rows_seen': len(drill_rows)})])
    report['seconds_probe'] = round(time.time() - t0, 2)
    if reg and calibrate:
        report['calibration'] = compare_to_profile(draft, reg)

    if self_check and out_dir is not None:
        # 用草案重切一遍：草案能否直接驱动 block_index
        dpath = Path(out_dir) / f'{bid}.draft.json'
        BI.guard_out(dpath, docx)
        dpath.write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding='utf-8')
        t1 = time.time()
        idx = BI.build_index(docx, load_profile(str(dpath)))
        s = idx['summary']
        report['self_check'] = OrderedDict([
            ('blocks', s['blocks']), ('by_part_kind', s['by_part_kind']), ('by_kind', s['by_kind']),
            ('blocks_missing_label', s['blocks_missing_label']), ('blocks_repeated_label', s['blocks_repeated_label']),
            ('blocks_missing_inline', s['blocks_missing_inline']),
            ('keys_parsed', s['keys_parsed']), ('drill_items', s['drill_items']), ('drill_by_side', s['drill_by_side']),
            ('drill_src_empty', s['drill_src_empty']),
            ('missing_by_label', dict(Counter(L for b in idx['blocks'] for L in b['missing']))),
            ('missing_blocks', [OrderedDict([('id', b['id']), ('title', b['title'][:30]), ('missing', b['missing'])])
                                for b in idx['blocks'] if b['missing']][:30]),
            ('seconds', round(time.time() - t1, 2)),
            ('note', '自检只说明草案能切出题块、机械层口径自洽，不代表内容已审；栏目缺失是候选，题型与部分划分仍需人工确认')])
    return draft, report


def compare_to_profile(draft, prof):
    """校准：草案与已登记配置逐项比（只比能从样稿推出的结构字段）。"""
    def g(d, path):
        for k in path.split('.'):
            d = (d or {}).get(k) if isinstance(d, dict) else None
        return d

    def norm(v):
        if v is None:
            v = []
        if isinstance(v, list):
            return sorted(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in v)
        return v
    fields = ['styles.h1', 'styles.h2', 'styles.example_title', 'styles.group_heading', 'styles.method',
              'styles.method_desc', 'styles.category_line', 'styles.trigger_box', 'styles.toc', 'styles.drill_group',
              'numbering.per_kind', 'method_count.count_kinds', 'method_count.unit', 'method_count.bearer_styles',
              'toc.mode', 'drill.layout', 'drill.a1_heading', 'drill.a2_heading', 'title_format.sep']
    rows = OrderedDict()
    for f in fields:
        a, b = g(draft, f), g(prof, f)
        rows[f] = {'equal': norm(a) == norm(b), 'draft': a, 'profile': b}
    ek = lambda P: sorted((e['kind'], e['regex']) for e in P.get('example_titles', []))
    rows['example_titles(kind,regex)'] = {'equal': ek(draft) == ek(prof), 'draft': ek(draft), 'profile': ek(prof)}
    lab = lambda P: sorted(json.dumps(sorted(s.get('labels', [])), ensure_ascii=False) for s in P.get('column_schemas', {}).values())
    rows['column_schemas.labels'] = {'equal': set(lab(prof)) <= set(lab(draft)), 'draft': lab(draft), 'profile': lab(prof),
                                     'rule': '现行各栏目组合都被草案复现'}
    sl = lambda P: sorted(P.get('section_labels', []))
    rows['section_labels'] = {'equal': set(sl(prof)) <= set(sl(draft)), 'draft_extra': sorted(set(sl(draft)) - set(sl(prof))),
                              'profile_missing_in_draft': sorted(set(sl(prof)) - set(sl(draft))), 'rule': '现行节点级栏目都被草案认出'}
    pid = lambda P: [p['id'] for p in P.get('structure', {}).get('parts', [])]
    rows['structure.parts.count'] = {'equal': len(pid(draft)) == len(pid(prof)), 'draft': pid(draft), 'profile': pid(prof)}
    agree = sum(1 for v in rows.values() if v['equal'])
    return OrderedDict([('profile', prof.get('book_id')), ('comparable_fields', len(rows)), ('agree', agree),
                        ('disagree', [k for k, v in rows.items() if not v['equal']]), ('fields', rows)])


def guard_dir(out_dir, docx):
    """草案输出目录检查：不进 profiles/、不写书稿旁边与各册登记目录、项目根、书稿根（与 block_index 同一套保护）。"""
    BI.guard_out(out_dir, docx, is_dir=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docx', required=True, help='新书 DOCX（只读）')
    ap.add_argument('--book-id', help='书册编号（只允许字母、数字、汉字、下划线、连字符；已知编号如 culture 会据此取班课等字段）')
    ap.add_argument('--out', default=str(DEFAULT_OUT), help=f'输出目录（缺省 {DEFAULT_OUT}，建议显式给出）')
    ap.add_argument('--template', default='bixiu3', help='结构模板与共用默认值取自哪份现有配置（缺省 bixiu3）')
    ap.add_argument('--census-only', action='store_true', help='只输出普查，不生成草案')
    ap.add_argument('--no-self-check', action='store_true', help='不用草案重切自检')
    ap.add_argument('--calibrate', action='store_true', help='DOCX 属已登记书册（含冻结册）时只做校准对照：草案保留 frozen 标记，并与登记配置逐项比')
    a = ap.parse_args(argv)
    if not Path(a.docx).is_file():
        print('找不到文件：', a.docx, file=sys.stderr)
        return 2
    if a.book_id is not None and not BOOK_ID_RX.match(a.book_id):
        print(f'book_id 非法：{a.book_id!r}（只允许字母、数字、汉字、下划线、连字符，不能含路径符号）', file=sys.stderr)
        return 2
    try:
        guard_dir(a.out, a.docx)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    try:
        BI.check_docx(a.docx)
    except BI.InputError as e:
        print('输入错误：', e, file=sys.stderr)
        return 2
    out = Path(a.out)
    try:
        if a.census_only:
            z = zipfile.ZipFile(a.docx)
            c = basic_census(BI.load_docx(a.docx), doc_parts(z), style_info(z))
            p = out / (re.sub(r'[^\w\-]+', '_', Path(a.docx).stem)[:40] + '.census.json')
            BI.guard_out(p, a.docx)
            out.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(c, ensure_ascii=False, indent=1), encoding='utf-8')
            print(f"段落 {c['paragraphs']}｜表格 {c['tables']}｜图片 {c['media']}｜节 {c['sections']}\n明细：{p}")
            return 0
        out.mkdir(parents=True, exist_ok=True)
        draft, rep = probe(a.docx, a.book_id, a.template, not a.no_self_check, out, a.calibrate)
        bid = draft['book_id']
        dpath, rpath = out / f'{bid}.draft.json', out / f'{bid}.probe.json'
        for p in (dpath, rpath):
            BI.guard_out(p, a.docx)
        dpath.write_text(json.dumps(draft, ensure_ascii=False, indent=1), encoding='utf-8')
        rpath.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    except SystemExit as e:  # 冻结册、写入保护
        print(e, file=sys.stderr)
        return 2
    except Exception:  # noqa: BLE001  内部错误给 2
        traceback.print_exc()
        print('内部错误：草案未生成（退出码 2）', file=sys.stderr)
        return 2
    sc = rep.get('self_check') or {}
    idn = rep['book_identity']
    print(f"{bid}｜书册识别 {idn['resolved'] or '未确认'}（{idn['resolved_by'] or '候选 ' + str(list(idn['title_hits']) or list(idn['body_hits']))}）"
          f"｜样式 {len(rep['census']['style_use'])} 种｜例题标题写法 {len(draft['example_titles'])} 种"
          f"｜部分 {len(draft['structure']['parts'])}｜栏目模式 {len(draft['column_schemas'])}"
          f"｜单练 {draft['drill'].get('layout') if draft['drill'] else '未识别'}｜需人工确认 {rep['needs_confirm_count']} 项"
          f"（{'，'.join(f'{k}{v}' for k, v in rep['needs_confirm_by_kind'].items())}）")
    if sc:
        print(f"  自检：题块 {sc['blocks']} {sc['by_kind']}｜题肢 {sc['drill_items']}｜缺栏候选 {sc['blocks_missing_label']} 块"
              f"（另标签在行中 {sc['blocks_missing_inline']} 块）｜用时 {rep['seconds_probe']}+{sc['seconds']}s")
    if rep.get('calibration'):
        cal = rep['calibration']
        print(f"  校准：与 profiles/{cal['profile']}.json 可比字段 {cal['agree']}/{cal['comparable_fields']} 一致；不一致 {cal['disagree']}")
    print('  说明：草案未经确认不得登记进 profiles/；自检只说明机械层自洽，不代表内容已审。')
    print('草案：', dpath)
    print('证据：', rpath)
    bad = not draft['styles']['h1'] or not draft['styles']['h2'] or (sc and sc['blocks'] == 0)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
