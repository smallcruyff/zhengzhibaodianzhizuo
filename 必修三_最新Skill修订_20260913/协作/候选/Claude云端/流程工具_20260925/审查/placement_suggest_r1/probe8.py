import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import docx_lib as dl, apply_patch as ap
prof, book, idx, fa, mi = load()
B = book['blocks']
titles = [b['title'] for b in B]
nonuniq = [t for t in titles if sum(1 for u in titles if t in u) != 1]
print('block_index titles: total', len(titles), 'not unique as substring', len(nonuniq))
for t in nonuniq[:10]: print('   ', repr(t))
d = dl.open_docx(str(BOOK3))
_, _, bhb, _ = ap.zones_of(d, prof)
bt = [b['title'] or '' for b in bhb]
print('bh blocks', len(bhb))
bad = []
for t in titles:
    n = sum(1 for u in bt if t in u)
    if n != 1: bad.append((t, n))
print('block_index titles that block_insert would NOT resolve to exactly 1 block:', len(bad))
for x in bad[:15]: print('   ', x)
