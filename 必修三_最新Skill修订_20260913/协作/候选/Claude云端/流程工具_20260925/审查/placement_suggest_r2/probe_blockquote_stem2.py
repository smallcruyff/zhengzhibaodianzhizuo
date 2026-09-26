#!/usr/bin/env python3
"""审查 r2（v2）：题面节里写在“>”引用块中的题目文字被 clean_prose 整行丢弃。
统计：选中题面节里引用行合计 >=40 字的 MD（题目文字被丢）；其中题目文字全在引用块、清洗后只剩来源/页图元数据的；
在必修三书中的题键与题块数；这些题块在默认参数留一评估中的前1/前3 命中率 vs 其余题块。只读。"""
import sys, re
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
prof = load_profile(str(C / 'profiles_cloud' / 'bixiu3.json'))
book = ps.load_book('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx', prof)
blocks = book['blocks']
mi = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
idx = ps.build_indices(ps.block_fields_all(blocks, mi), [2, 3])
book_keys = Counter(b['key'] for b in blocks if b.get('key'))
dropped = {}
META = re.compile(r'来源|渲染|原页|SHA|页图|视觉|媒体|assets|source|png', re.I)
for p in sorted((BANK / 'questions').glob('*/*.md')):
    if p.name == 'README.md':
        continue
    text = p.read_text(encoding='utf-8', errors='replace')
    try:
        q = ps.parse_question_md(text, p.stem)
    except ps.InputError:
        continue
    heads = ps.all_headings(text)
    si = [i for i, h in enumerate(heads) if h[1] == q['stem_header']][0]
    raw = ps.section_body(text, heads, si)
    quoted = sum(len(re.sub(r'\s', '', l.strip()[1:])) for l in raw.splitlines() if l.strip().startswith('>'))
    if quoted >= 40:
        kept_lines = [l for l in (q['material'] + '\n' + q['ask']).splitlines() if l.strip()]
        only_meta = all(META.search(l) for l in kept_lines) if kept_lines else True
        dropped[p.stem] = (q['kind'], quoted, only_meta)
print('选中题面节里引用块文字>=40字（被 clean_prose 丢弃）的 MD:', len(dropped))
print('  其中清洗后只剩来源/页图元数据（题目文字全丢）:', sum(1 for v in dropped.values() if v[2]))
print('  题型:', Counter(v[0] for v in dropped.values()))
inb = [k for k in dropped if book_keys.get(k)]
print('  在必修三书中的题键', len(inb), '题块', sum(book_keys[k] for k in inb))
print('  按卷:', Counter(k.rsplit('-Q', 1)[0] for k in dropped).most_common(20))
# 留一命中对比
def loo(sel):
    h1 = h3 = n = 0
    for i, b in enumerate(blocks):
        k = b.get('key')
        if not k or not sel(k):
            continue
        mdp = ps.find_md_path(BANK, k)
        if not mdp.is_file():
            continue
        try:
            q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
        except ps.InputError:
            continue
        if (q['kind'] == 'choice') != (b['kind'] == 'choice'):
            continue
        q['base_key'] = k
        ranked, _, _ = ps.rank_for_query(q, book, idx, ps.DEFAULT_PARAMS)
        r = ps.true_rank_of(ranked, {ps.group_key_of(b)})
        n += 1; h1 += (r == 1); h3 += (r is not None and r <= 3)
    return n, h1, h3
print('  留一（默认参数）题面被丢的题块 n/前1/前3:', loo(lambda k: k in dropped))
print('  留一（默认参数）其余题块       n/前1/前3:', loo(lambda k: k not in dropped))
