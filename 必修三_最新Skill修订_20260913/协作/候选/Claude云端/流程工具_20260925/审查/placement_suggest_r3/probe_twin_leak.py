from common import *
from block_index import render_recs
prof, book, idx = load()
blocks = book['blocks']
bset = [ps._ngram_set(render_recs(b['_recs'][1:], book['doc']['rels']), 3) for b in blocks]
def contain(q, r):
    return len(q & r) / len(q) if q else 0.0
rows = []
twin_keys = {}
keys = sorted({b['key'] for b in blocks if b.get('key')})
for k in keys:
    q, _ = md(k)
    if q is None: continue
    qs = ps._ngram_set(q['stem_full'], 3)
    ex = ps.matching_block_idxs(blocks, k)
    best = max(((contain(qs, bset[i]), i) for i in range(len(blocks)) if i not in ex), default=(0, None))
    if best[0] >= 0.6:
        b = blocks[best[1]]
        twin_keys[k] = (round(best[0], 2), b['id'], b.get('key'), b['title'][:40])
print('in-book keys whose stem is >=60% contained in a block of a DIFFERENT key (twin/串题 candidates):', len(twin_keys))
for k, v in twin_keys.items(): print('  ', k, v)
# LOO impact (strict, block-level, default params)
import sys
sys.path.insert(0, str(C))
n = h1 = h3 = tn = th1 = th3 = 0
for i, b in enumerate(blocks):
    if not b.get('key'): continue
    q, _ = md(b['key'])
    if q is None: continue
    if ('choice' if q['kind']=='choice' else 's') != ('choice' if b['kind']=='choice' else 's'): continue
    q = dict(q); q['base_key'] = b['key']
    ranked, exclude, _ = ps.rank_for_query(q, book, idx, ps.DEFAULT_PARAMS)
    r = ps.true_rank_of(ranked, {ps.group_key_of(b)})
    n += 1; h1 += (r == 1); h3 += (r is not None and r <= 3)
    if b['key'] in twin_keys:
        tn += 1; th1 += (r == 1); th3 += (r is not None and r <= 3)
print(f'LOO strict default: n={n} hit1={h1} hit3={h3}; of which twin-key rows n={tn} hit1={th1} hit3={th3}; without twins hit1={h1-th1}/{n-tn} hit3={h3-th3}/{n-tn}')
