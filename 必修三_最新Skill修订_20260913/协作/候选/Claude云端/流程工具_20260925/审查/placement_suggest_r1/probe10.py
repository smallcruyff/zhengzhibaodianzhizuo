import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import time, random
prof, book, idx, fa, mi = load()
B = book['blocks']
keys = sorted({b['key'] for b in B if b['key'] and mdq(b['key'])})
t0=time.time()
for k in keys[:40]:
    q = dict(mdq(k)); q['base_key']=k
    ps.rank_for_query(q, book, idx, ps.DEFAULT_PARAMS)
dt = time.time()-t0
print('40 rank_for_query: %.2fs -> 20-grid x 40 keys est %.1fs' % (dt, dt*20))
