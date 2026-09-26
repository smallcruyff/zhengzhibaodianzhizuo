import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
from block_index import sig, render_recs
prof, book, idx, fa, mi = load()
B = book['blocks']; doc = book['doc']
def grams(s, n=4):
    s = sig(s); return {s[i:i+n] for i in range(len(s)-n+1)}
btext = [grams(render_recs(b['_recs'][1:], doc['rels'])) for b in B]
cache = {}
leaks = []
n_eval = 0
for i, b in enumerate(B):
    if not b['key']: continue
    if b['key'] not in cache: cache[b['key']] = mdq(b['key'])
    q = cache[b['key']]
    if q is None: continue
    n_eval += 1
    q = dict(q); q['base_key'] = b['key']
    qg = grams(q['stem_full'])
    if len(qg) < 30: continue
    excl = ps.matching_block_idxs(B, b['key'])
    # best containment among non-excluded blocks
    best = max(((len(qg & btext[j]) / len(qg), j) for j in range(len(B)) if j not in excl), default=(0, None))
    if best[0] >= 0.5:
        leaks.append((b['id'], b['key'], round(best[0],2), B[best[1]]['id'], B[best[1]]['key'], B[best[1]]['title'][:40]))
print('evaluated', n_eval)
seen=set()
for l in leaks:
    if (l[1], l[4]) in seen: continue
    seen.add((l[1], l[4])); print(l)
print('blocks whose question text is >=50% contained in a NON-excluded block:', len(leaks))
