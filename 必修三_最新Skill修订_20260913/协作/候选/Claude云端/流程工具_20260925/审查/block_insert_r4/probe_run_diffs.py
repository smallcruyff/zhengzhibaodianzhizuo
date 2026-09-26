"""R4：self 样板默认路径重建 source 段后，逐字符比较可见格式（加粗/颜色/字体），统计“多于 1 个字符变格式”的段。"""
from common import *
import collections
sys.path.insert(0, str(C))
import run_tests_block_insert as rt
prof = bi.load_profile(str(PROF)); d = dl.open_docx(BOOK); S = style_ctx()[4]
_z = ap.zones_of(d, prof); bi.ap.zones_of = lambda dd, pp: _z
zone, _, blocks, _ = _z
_sp = bi._stem_position_index(d, S, prof, blocks); bi._stem_position_index = lambda *a, **k: _sp
buckets = {n: b_ for b_ in ('source', 'teaching', 'rubric') for n in prof['styles'].get(b_, [])}
media_ctx = bi.MediaCtx(d)
titles = collections.Counter(b['title'] for b in blocks)
uniq = [b for b in blocks if titles[b['title']] == 1 and sum(1 for x in blocks if b['title'] in x['title']) == 1]
anchor_title = uniq[0]['title']
def charfmt(p):
    out = []
    for vf, n in rt._visual_segments(p):
        out += [vf] * n
    return out
stats = collections.Counter(); ex = collections.defaultdict(list)
for k, b in enumerate(uniq):
    content, idxs = [], []
    for i in sorted(b.get('paras') or []):
        it = d.items[i]
        if it.get('tbl') or it.get('img') or not dl.para_text(d.paras[i]).strip(): continue
        if buckets.get(it['style']) != 'source': continue
        content.append({'role': 'source', 'text': dl.para_text(d.paras[i])}); idxs.append(i)
    if not content: continue
    unit = {'inserts': [{'id': 'P', 'anchor': {'after_block': {'title_contains': anchor_title}},
                         'template_block': {'title_contains': b['title']}, 'title': f'例题 {k+900}　探针卷第{k}题',
                         'source_zone': 'restore', 'reason': 'probe', 'content': content}]}
    try:
        plans = bi.plan_inserts(d, prof, unit, media_ctx)
    except Exception as e:
        stats['abort'] += 1; continue
    for i, (_, newp) in zip(idxs, plans[0]['elements'][1:]):
        a, c = charfmt(d.paras[i]), charfmt(newp)
        stats['n'] += 1
        if len(a) != len(c):
            stats['len_mismatch'] += 1; continue
        nb = sum(1 for x, y in zip(a, c) if x[0] != y[0])
        nc = sum(1 for x, y in zip(a, c) if x[3] != y[3])
        nf = sum(1 for x, y in zip(a, c) if x[4] != y[4])
        gained = sum(1 for x, y in zip(a, c) if (not x[0]) and y[0])
        lost = sum(1 for x, y in zip(a, c) if x[0] and not y[0])
        if gained > 1:
            stats['bold_gained>1'] += 1
            ex['bold_gained'].append((i, b['title'][:24], dl.para_text(d.paras[i])[:30], f'gained={gained}/{len(a)}', gained, b['title']))
        if lost > 1:
            stats['bold_lost>1'] += 1
            if len(ex['bold_lost']) < 15: ex['bold_lost'].append((i, b['title'][:24], dl.para_text(d.paras[i])[:30], f'lost={lost}/{len(a)}'))
        if nc > 1: stats['color>1'] += 1; ex['color'].append((i, b['title'][:24], dl.para_text(d.paras[i])[:30], nc))
        if nf > 1: stats['font>1'] += 1; ex['font'].append((i, b['title'][:24], dl.para_text(d.paras[i])[:30], nf))
print(dict(stats))
g10 = [x for x in ex['bold_gained'] if x[4] >= 10]
print('bold_gained>=10 段数', len(g10), '涉及题块', len({x[5] for x in g10}), '其中【题目】行', sum(1 for x in g10 if x[2].startswith('【')))
json.dump(ex, open(HERE / 'probe_run_diffs.json', 'w'), ensure_ascii=False, indent=1)
for k2, v in ex.items():
    print('==', k2, len(v))
    for x in v[:15]: print('  ', x)
