"""R4 探针：R3-B1 位置信号在真实插入路径（plan_inserts，content 由整块原文构成、不给 style/like/kind）
下的保真度。三种样板：self（最有利）、prev（前一个同类题块，贴近“相邻样板题块”）、next。
统计 source 段：原宋体→新非宋体、原楷体→新宋体、段落样式变化（如 题目选项→题目材料）。"""
from common import *
import collections, time
t0 = time.time()
prof = bi.load_profile(str(PROF))
d = dl.open_docx(BOOK)
S = style_ctx()[4]
_z = ap.zones_of(d, prof)
ap_zones_cache = _z
bi.ap.zones_of = lambda dd, pp: ap_zones_cache  # 只读缓存（同一棵树）
zone, _, blocks, _ = _z
_sp = bi._stem_position_index(d, S, prof, blocks)
bi._stem_position_index = lambda *a, **k: _sp
import functools
src_ids = bi._style_ids_for_bucket(prof, S, 'source')
buckets = {}
for b_ in ('source', 'teaching', 'rubric'):
    for n in prof['styles'].get(b_, []):
        buckets[n] = b_
media_ctx = bi.MediaCtx(d)
OPT = re.compile(r'^[A-D][.．]')

def is_choice(b):
    return any(OPT.match(dl.para_text(d.paras[i]).strip()) for i in (b.get('paras') or [])
               if not d.items[i].get('tbl'))

def content_of(b):
    items, idxs = [], []
    for i in sorted(b.get('paras') or []):
        it = d.items[i]
        if it.get('tbl') or it.get('img'):
            continue
        t = dl.para_text(d.paras[i])
        if not t.strip():
            continue
        role = buckets.get(it['style'])
        if role is None:
            continue
        items.append({'role': role, 'text': t})
        idxs.append(i)
    return items, idxs

titles = collections.Counter(b['title'] for b in blocks)
uniq = [b for b in blocks if titles[b['title']] == 1 and sum(1 for x in blocks if b['title'] in x['title']) == 1]
anchor_title = uniq[0]['title']
res = {}
MODES = sys.argv[1:] or ['self']
for mode in MODES:
    stats = collections.Counter()
    examples = collections.defaultdict(list)
    for k, b in enumerate(uniq[:int(os.environ.get('LIMIT', '100000'))]):
        ch = is_choice(b)
        if mode == 'self':
            tb = b
        else:
            pool = [x for x in uniq if is_choice(x) == ch and x is not b]
            pos = [x['title_i'] for x in pool]
            if mode == 'prev':
                cands = [x for x in pool if x['title_i'] < b['title_i']]
                tb = max(cands, key=lambda x: x['title_i']) if cands else None
            else:
                cands = [x for x in pool if x['title_i'] > b['title_i']]
                tb = min(cands, key=lambda x: x['title_i']) if cands else None
            if tb is None:
                continue
        content, idxs = content_of(b)
        if not any(c['role'] == 'source' for c in content):
            continue
        unit = {'inserts': [{'id': f'P{k}', 'anchor': {'after_block': {'title_contains': anchor_title}},
                             'template_block': {'title_contains': tb['title']},
                             'title': f'例题 {k+900}　探针卷第{k}题', 'source_zone': 'restore', 'reason': 'probe',
                             'content': content}]}
        try:
            plans = bi.plan_inserts(d, prof, unit, media_ctx)
        except Exception as e:
            stats['abort'] += 1
            examples['abort'].append((b['title'][:30], str(e)[:120]))
            continue
        els = [e for kind, e in plans[0]['elements'][1:]]
        for c, i, newp in zip(content, idxs, els):
            if c['role'] != 'source':
                continue
            of, nf = eff_font(d.paras[i]), eff_font(newp)
            osn, nsn = pstyle_name(d.paras[i]), pstyle_name(newp)
            tag = 'choice' if ch else 'subj'
            stats[f'{tag}_n'] += 1
            if of == 'Songti SC' and nf != 'Songti SC':
                stats[f'{tag}_Songti->{nf}'] += 1
                examples[f'{tag}_Songti->x'].append((i, b['title'][:26], dl.para_text(d.paras[i])[:40], nf, 'tpl=' + tb['title'][:20]))
            if of != 'Songti SC' and nf == 'Songti SC':
                stats[f'{tag}_{of}->Songti'] += 1
                examples[f'{tag}_x->Songti'].append((i, b['title'][:26], dl.para_text(d.paras[i])[:40], of, 'tpl=' + tb['title'][:20]))
            if osn != nsn:
                stats[f'{tag}_style {osn}->{nsn}'] += 1
                examples[f'{tag}_style'].append((i, b['title'][:26], dl.para_text(d.paras[i])[:40], osn, nsn, 'tpl=' + tb['title'][:20]))
    res[mode] = {'stats': dict(stats), 'examples': {k: v[:25] for k, v in examples.items()}}
    print(mode, dict(stats), flush=True)
out = HERE / ('probe_stem_fidelity_' + '_'.join(MODES) + '.json')
out.write_text(json.dumps(res, ensure_ascii=False, indent=1))
print('blocks', len(blocks), 'uniq', len(uniq), 'secs', round(time.time() - t0))
