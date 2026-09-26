"""R4：self 样板默认路径重建 source 段，逐项统计 pPr 可见差异（首行缩进、keepNext、对齐、样式），区分选择/主观、最后一段/其他。"""
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
OPT = re.compile(r'^[A-D][.．]')
FIELDS = ['pStyle', 'jc', 'keepNext', 'ind_left', 'firstLine', 'firstLineChars', 'sp_before', 'sp_after', 'sp_line']
st = collections.Counter(); ex = collections.defaultdict(list)
for k, b in enumerate(uniq):
    ps = [i for i in sorted(b.get('paras') or []) if not d.items[i].get('tbl') and not d.items[i].get('img') and dl.para_text(d.paras[i]).strip() and buckets.get(d.items[i]['style']) == 'source']
    if not ps: continue
    ch = any(OPT.match(dl.para_text(d.paras[i]).strip()) for i in ps)
    content = [{'role': 'source', 'text': dl.para_text(d.paras[i])} for i in ps]
    unit = {'inserts': [{'id': 'P', 'anchor': {'after_block': {'title_contains': anchor_title}}, 'template_block': {'title_contains': b['title']},
                         'title': f'例题 {k+900}　探针卷第{k}题', 'source_zone': 'restore', 'reason': 'probe', 'content': content}]}
    try: plans = bi.plan_inserts(d, prof, unit, media_ctx)
    except Exception: st['abort'] += 1; continue
    for j, (i, (_, np_)) in enumerate(zip(ps, plans[0]['elements'][1:])):
        a = rt._visual_ppr(d.paras[i].find(W + 'pPr')) or (None,) * 9
        c = rt._visual_ppr(np_.find(W + 'pPr')) or (None,) * 9
        tag = ('choice' if ch else 'subj') + ('_last' if j == len(ps) - 1 else '_other')
        st[tag + '_n'] += 1
        for f, x, y in zip(FIELDS, a, c):
            if x != y:
                st[f'{tag}:{f} {x}->{y}'] += 1
                if f in ('firstLine',) and len(ex[tag]) < 8:
                    ex[tag].append((i, b['title'][:22], dl.para_text(d.paras[i])[:26], x, y))
for kk in sorted(st): print(kk, st[kk])
for kk, v in ex.items():
    print('==', kk)
    for x in v: print('  ', x)
