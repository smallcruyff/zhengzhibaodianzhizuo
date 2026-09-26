import sys
sys.dont_write_bytecode=True
import json
from common import *
sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import docx_lib as dl, apply_patch as ap, batch_health as bh
W=bh.W
def seg(p):
    out=[]
    for r,t in ap._run_spans(p):
        if not t: continue
        rp=r.find(W+'rPr')
        def g(tag, attr='val'):
            e=rp.find(W+tag) if rp is not None else None
            return None if e is None else (e.get(W+attr) if attr else True)
        v=(bool(g('b',None)), g('color'), g('rFonts','eastAsia'), g('sz'))
        if out and out[-1][0]==v: out[-1][1]+=len(t)
        else: out.append([v,len(t)])
    return [tuple(x) for x in out]
res={}
for case, title in (('img','例题 5　2026门头沟一模第17题'),('tbl','例题 3　2024朝阳二模第18题')):
    a=dl.open_docx(Path('test_outputs')/f'gold_pristine_{case}.docx'); b=dl.open_docx(Path('test_outputs')/f'gold_{case}_out.docx')
    ia=[i for i,it in enumerate(a.items) if it['text']==title][0]; ib=[i for i,it in enumerate(b.items) if it['text']==title][0]
    diffs=[]
    k=0
    while True:
        i,j=ia+k,ib+k
        if k>0 and (a.items[i]['text'].startswith('例题 ') or a.items[i]['text'].startswith('考法')): break
        sa,sb=seg(a.paras[i]),seg(b.paras[j])
        fa=[(x[0][2],x[1]) for x in sa]; fb=[(x[0][2],x[1]) for x in sb]
        if fa!=fb: diffs.append({'offset':k,'text':a.items[i]['text'][:20],'orig_font':fa,'new_font':fb})
        k+=1
    res[case]={'n_paras':k,'eastAsia_font_diffs':diffs}
print(json.dumps(res,ensure_ascii=False,indent=1))
