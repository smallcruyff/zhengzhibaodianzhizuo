import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import re
prof, book, idx, fa, mi = load()
B = book['blocks']
REG = {'HD':0,'XC':1,'DC':2,'CY':3,'FT':4}
STG = {'YIMO':0,'ERMO':1,'QIMO':2,'QIZHONG':3,'GAOKAO':-1}
def skey(b):
    k = b['key']
    m = re.match(r'BJ-(\d{4})-([A-Z]+)-([A-Z]+)-Q(\d+)', k or '')
    if not m: return None
    y, r, s, q = int(m.group(1)), m.group(2), m.group(3), int(m.group(4))
    kind = 0 if b['kind']!='choice' else 1
    src = 0 if s=='GAOKAO' else 1
    reg = -1 if s=='GAOKAO' else REG.get(r, 5)
    return (kind, src, reg, STG.get(s,9) if s!='GAOKAO' else 0, -y, q, b['subq'] or '')
groups = {}
for i,b in enumerate(B):
    groups.setdefault(ps.group_key_of(b), []).append(b)
tot=ok=0; bad=[]
pairs=okp=0
for g, bs in groups.items():
    bs = sorted(bs, key=lambda b: b['p_range'][0])
    ks = [skey(b) for b in bs]
    if any(k is None for k in ks) or len(bs)<2: continue
    tot += 1
    # suburbs have no fixed order: treat reg==5 ties as equal by ignoring region within suburbs
    def norm(k): return k
    srt = all(ks[i] <= ks[i+1] for i in range(len(ks)-1))
    for i in range(len(ks)-1):
        pairs += 1; okp += ks[i] <= ks[i+1]
    ok += srt
    if not srt: bad.append((g[2][:20], [b['title'][-20:] for b in bs][:8]))
print('groups with >=2 keyed blocks', tot, 'fully sorted by 受控排序 key', ok)
print('adjacent pairs in order', okp, '/', pairs)
for x in bad[:8]: print(x)
# P1 only, choice vs subjective separately
