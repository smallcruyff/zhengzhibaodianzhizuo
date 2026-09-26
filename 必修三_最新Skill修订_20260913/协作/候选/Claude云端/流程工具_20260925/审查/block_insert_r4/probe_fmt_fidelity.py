"""R4 探针：默认路径（不给 style/like/kind）整块原文重建后，逐段完整格式签名（测试自己的
_para_fmt_sig：pStyle/jc/keepNext/缩进/间距 + 可见 run 格式）与原段比较。self 样板为最有利情形。
分选择题块/主观题块、是否“最后一个 source 段”统计差异。"""
from common import *
import collections, time
sys.path.insert(0, str(C))
import run_tests_block_insert as rt
t0 = time.time()
prof = bi.load_profile(str(PROF))
d = dl.open_docx(BOOK)
S = style_ctx()[4]
_z = ap.zones_of(d, prof)
bi.ap.zones_of = lambda dd, pp: _z
zone, _, blocks, _ = _z
_sp = bi._stem_position_index(d, S, prof, blocks)
bi._stem_position_index = lambda *a, **k: _sp
buckets = {}
for b_ in ('source', 'teaching', 'rubric'):
    for n in prof['styles'].get(b_, []):
        buckets[n] = b_
media_ctx = bi.MediaCtx(d)
OPT = re.compile(r'^[A-D][.．]')
def is_choice(b):
    return any(OPT.match(dl.para_text(d.paras[i]).strip()) for i in (b.get('paras') or []) if not d.items[i].get('tbl'))
titles = collections.Counter(b['title'] for b in blocks)
uniq = [b for b in blocks if titles[b['title']] == 1 and sum(1 for x in blocks if b['title'] in x['title']) == 1]
anchor_title = uniq[0]['title']
mode = sys.argv[1] if len(sys.argv) > 1 else 'self'
stats = collections.Counter(); ex = collections.defaultdict(list)
for k, b in enumerate(uniq):
    ch = is_choice(b)
    if mode == 'self':
        tb = b
    else:
        cands = [x for x in uniq if is_choice(x) == ch and x['title_i'] < b['title_i']]
        if not cands: continue
        tb = max(cands, key=lambda x: x['title_i'])
    content, idxs = [], []
    for i in sorted(b.get('paras') or []):
        it = d.items[i]
        if it.get('tbl') or it.get('img') or not dl.para_text(d.paras[i]).strip(): continue
        role = buckets.get(it['style'])
        if role != 'source': continue   # 只比题面段（教学段另有 R2-m4 已知限制）
        content.append({'role': role, 'text': dl.para_text(d.paras[i])}); idxs.append(i)
    if not content: continue
    unit = {'inserts': [{'id': 'P', 'anchor': {'after_block': {'title_contains': anchor_title}},
                         'template_block': {'title_contains': tb['title']}, 'title': f'例题 {k+900}　探针卷第{k}题',
                         'source_zone': 'restore', 'reason': 'probe', 'content': content}]}
    try:
        plans = bi.plan_inserts(d, prof, unit, media_ctx)
    except Exception as e:
        stats['abort'] += 1; continue
    els = [e for _, e in plans[0]['elements'][1:]]
    last = len(content) - 1
    for j, (i, newp) in enumerate(zip(idxs, els)):
        tag = ('choice' if ch else 'subj') + ('_last' if j == last else '_other')
        stats[tag + '_n'] += 1
        a, bb = rt._para_fmt_sig(d.paras[i]), rt._para_fmt_sig(newp)
        if a != bb:
            stats[tag + '_diff'] += 1
            which = []
            if a[0] != bb[0]: which.append('ppr')
            if a[1] != bb[1]: which.append('runs')
            stats[tag + '_diff_' + '+'.join(which)] += 1
            if len(ex[tag]) < 12:
                ex[tag].append({'i': i, 'block': b['title'][:28], 'text': dl.para_text(d.paras[i])[:36],
                                'orig': str(a)[:300], 'new': str(bb)[:300]})
print(mode, dict(sorted(stats.items())))
(HERE / f'probe_fmt_fidelity_{mode}.json').write_text(json.dumps({'stats': dict(stats), 'examples': ex}, ensure_ascii=False, indent=1))
print('secs', round(time.time() - t0))
