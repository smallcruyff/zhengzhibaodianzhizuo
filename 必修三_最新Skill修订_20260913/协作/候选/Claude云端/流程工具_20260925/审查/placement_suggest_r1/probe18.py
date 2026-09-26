import sys; sys.dont_write_bytecode = True
from common import *
prof, book, idx, fa, mi = load()
B = book['blocks']
k = 'BJ-2026-BJ-GAOKAO-Q18'
q = dict(mdq(k)); q['base_key'] = k
tg = {ps.group_key_of(b) for b in B if b['key'] == k}
for kind in ('choice', 'subjective'):
    q['kind'] = kind
    if kind == 'subjective':
        q['material'], q['ask'], _ = ps.split_ask(q['stem_full'])
    ranked, _, _ = ps.rank_for_query(q, book, idx, ps.DEFAULT_PARAMS)
    print(kind, 'true rank', ps.true_rank_of(ranked, tg), 'of', len(ranked))
