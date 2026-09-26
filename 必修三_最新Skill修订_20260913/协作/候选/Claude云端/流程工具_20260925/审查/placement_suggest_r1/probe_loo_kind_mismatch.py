import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
prof, book, idx, fa, mi = load()
B = book['blocks']
cache = {}
tot = h1 = h3 = 0; mis = mis_h1 = mis_h3 = 0; fix_h1 = fix_h3 = 0
unreach = 0
for i, b in enumerate(B):
    if not b['key']: continue
    if b['key'] not in cache: cache[b['key']] = mdq(b['key'])
    q = cache[b['key']]
    if q is None: continue
    q = dict(q); q['base_key'] = b['key']; tg = {ps.group_key_of(b)}
    ranked, excl, _ = ps.rank_for_query(q, book, idx, ps.DEFAULT_PARAMS)
    r = ps.true_rank_of(ranked, tg)
    tot += 1; h1 += r == 1; h3 += (r is not None and r <= 3)
    bookchoice = b['kind'] == 'choice'
    if (q['kind'] == 'choice') != bookchoice:
        mis += 1; mis_h1 += r == 1; mis_h3 += (r is not None and r <= 3)
    if r is None: unreach += 1
    # corrected: use book kind
    q2 = dict(q); q2['kind'] = 'choice' if bookchoice else 'subjective'
    ranked2, _, _ = ps.rank_for_query(q2, book, idx, ps.DEFAULT_PARAMS)
    r2 = ps.true_rank_of(ranked2, tg)
    fix_h1 += r2 == 1; fix_h3 += (r2 is not None and r2 <= 3)
print(f'LOO total {tot}: hit1 {h1} hit3 {h3}')
print(f'  kind-mismatched queries {mis}: of which counted hit1 {mis_h1} hit3 {mis_h3}')
print(f'  true group unreachable (all its blocks excluded / other kind) {unreach}')
print(f'  with kind forced to book kind: hit1 {fix_h1} hit3 {fix_h3}')
