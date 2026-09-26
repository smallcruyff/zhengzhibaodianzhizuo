import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
prof, book, idx, fa, mi = load()
B = book['blocks']; heads = book['heads']; doc = book['doc']
ch = [b for b in B if b['kind']=='choice']
print('choice groups:', Counter(ps.group_key_of(b)[1:] for b in ch).most_common(25))
# show heads + blocks sequence near first choice block
b0 = ch[0]; p0 = b0['p_range'][0]
seq = [(h['p'], 'HEAD-'+h['level'], h['text'][:40]) for h in heads] + [(b['p_range'][0], 'BLOCK-'+b['kind'], b['title'][:40]+' | m='+(b['method'] or '')[:20]+' | g='+(b['group'] or '')[:20]) for b in B]
seq.sort()
i = [k for k,x in enumerate(seq) if x[0]==p0][0]
for x in seq[max(0,i-12):i+6]: print(x)
# paragraphs styles right before the first choice block
for r in doc['paras'][p0-6:p0+1]:
    print('   p', r['p'], r['style'], r['text'][:50])
