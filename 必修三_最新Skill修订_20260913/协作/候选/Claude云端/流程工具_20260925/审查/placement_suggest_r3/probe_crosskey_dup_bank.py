from common import *
from block_index import render_recs
from collections import Counter
prof, book, idx = load()
blocks = book['blocks']
bset = [ps._ngram_set(render_recs(b['_recs'][1:], book['doc']['rels']), 3) for b in blocks]
inbook = set()
for b in blocks:
    for k in [b.get('key')] + list(b.get('keys_all') or []):
        if k: inbook.add(k.split('(')[0])
hits = []
n = 0
for p in sorted((BANK/'questions').glob('*/*-Q*.md')):
    k = p.stem
    if k in inbook: continue
    q, _ = md(k)
    if q is None: continue
    qs = ps._ngram_set(q['stem_full'], 3)
    if len(qs) < 30: continue
    n += 1
    best = max(((len(qs & bset[i]) / len(qs), i) for i in range(len(blocks))), default=(0, None))
    if best[0] >= 0.8:
        b = blocks[best[1]]
        hits.append((k, round(best[0], 2), b['id'], b.get('key'), b['title'][:36]))
print('bank questions NOT in book (by key) scanned:', n)
print('... whose stem is >=80% contained in an existing book block of another key:', len(hits))
print('by exam:', Counter(h[0].rsplit('-Q',1)[0] for h in hits).most_common())
for h in hits[:40]: print('  ', h)
