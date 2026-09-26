import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import block_insert as bi
import docx_lib as dl, apply_patch as ap
prof, book, idx, fa, mi = load()
B = book['blocks']
# find a subjective group whose last block title is non-unique, and craft the query from one of its blocks
titles = [b['title'] for b in B]
d = dl.open_docx(str(BOOK3))
_, _, bhb, _ = ap.zones_of(d, prof)
for want in ['例题 4　2024海淀期中第19题', '例题 5　2026西城期末第18题']:
    try:
        bi.resolve_insert_anchor(bhb, {'after_block': {'title_contains': want}})
        print('resolved', want)
    except Exception as e:
        print(type(e).__name__, str(e)[:300])
# which real query yields such anchor in top-3?
import itertools
keys = sorted({b['key'] for b in B if b['key']})
found = 0
for k in keys:
    q = mdq(k)
    if q is None: continue
    q = dict(q); q['base_key']=k; q['subq']=None
    r = ps.build_query_result(q, book, idx, ps.DEFAULT_PARAMS, 3, 100, [])
    for c in r['candidates']:
        a = c['insert_after']['anchor_title_contains']
        if sum(1 for u in titles if a in u) != 1:
            found += 1
            if found <= 3: print('query', k, '-> anchor', a, 'hits', sum(1 for u in titles if a in u))
print('total non-unique anchors emitted over all', len(keys), 'keys x top3:', found)
