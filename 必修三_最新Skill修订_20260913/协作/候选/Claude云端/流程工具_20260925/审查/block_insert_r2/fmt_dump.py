import sys
sys.dont_write_bytecode=True
from common import *
sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import docx_lib as dl, batch_health as bh, apply_patch as ap
W=bh.W
def vr(rpr):
    if rpr is None: return ('-',)
    b=rpr.find(W+'b'); c=rpr.find(W+'color'); f=rpr.find(W+'rFonts'); sz=rpr.find(W+'sz')
    return ('B' if b is not None and b.get(W+'val') not in ('0','false') else '',
            c.get(W+'val') if c is not None else '', (f.get(W+'eastAsia') or '') if f is not None else '', sz.get(W+'val') if sz is not None else '')
def vp(ppr):
    if ppr is None: return '-'
    parts=[]
    for tag in ('keepNext','keepLines'):
        if ppr.find(W+tag) is not None: parts.append(tag)
    ind=ppr.find(W+'ind')
    if ind is not None: parts.append('ind'+str({k.split('}')[1]:v for k,v in ind.attrib.items()}))
    jc=ppr.find(W+'jc')
    if jc is not None: parts.append('jc='+jc.get(W+'val'))
    sp=ppr.find(W+'spacing')
    if sp is not None: parts.append('sp'+str({k.split('}')[1]:v for k,v in sp.attrib.items()}))
    return ' '.join(parts)
def segs(p):
    out=[]
    for r,t in ap._run_spans(p):
        if not t: continue
        v=vr(r.find(W+'rPr'))
        if out and out[-1][0]==v: out[-1][1]+=len(t)
        else: out.append([v,len(t)])
    return out
def dump(path, title, n=40):
    d=dl.open_docx(path)
    idx=[i for i,it in enumerate(d.items) if it['text'].startswith(title)]
    i0=idx[0]
    print('#####', Path(path).name, title, 'at', i0)
    for i in range(i0, i0+n):
        it=d.items[i]
        if i>i0 and it['text'].startswith('例题 ') and it['tbl'] is None: break
        if it['text'].startswith('考法'): break
        print(f"{i:5d} tbl={it['tbl']} {it['style'][:6]:6s} | {vp(d.paras[i].find(W+'pPr'))[:70]:70s} | {segs(d.paras[i])} | {it['text'][:22]}")
path=sys.argv[1]
for t in sys.argv[2:]:
    dump(path, t)
