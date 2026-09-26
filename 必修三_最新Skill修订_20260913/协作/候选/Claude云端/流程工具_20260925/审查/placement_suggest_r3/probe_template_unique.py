from common import *
from collections import Counter
prof, book, idx = load()
blocks = book['blocks']
nonuniq_titles = {b['title'] for b in blocks if ps._title_hit_count(blocks, b['title']) != 1}
print('blocks', len(blocks), 'blocks whose title is not unique (substring):', sum(1 for b in blocks if b['title'] in nonuniq_titles))
# production-like: every in-book key queried once via build_query_result, top-3 candidates
keys = sorted({b['key'] for b in blocks if b.get('key')})
tot = bad = 0; bad_top1 = 0; nq = 0; ex = []
for k in keys:
    q, _ = md(k)
    if q is None: continue
    q = dict(q); q['base_key'] = k; q['true_group_keys'] = None; q['subq'] = None
    r = ps.build_query_result(q, book, idx, ps.DEFAULT_PARAMS, 3, 50, [])
    nq += 1
    for ci, c in enumerate(r['candidates']):
        tot += 1
        t = c['most_similar_block']['title']
        if ps._title_hit_count(blocks, t) != 1:
            bad += 1
            if ci == 0: bad_top1 += 1
            if len(ex) < 6: ex.append((k, ci+1, c['most_similar_block']['id'], t, ps._title_hit_count(blocks, t)))
print('queries', nq, 'candidates', tot, 'most_similar_block title NOT unique:', bad, 'of which rank1:', bad_top1)
for e in ex: print('  ', e)
print('candidate keys:', list(r['candidates'][0].keys()))
print('any template_block field:', any('template' in k for k in r['candidates'][0].keys()))
