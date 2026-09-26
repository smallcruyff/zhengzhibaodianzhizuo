import sys; sys.dont_write_bytecode=True
import zipfile, json, difflib
from lxml import etree
from pathlib import Path
SK='/home/user/zhengzhibaodianzhizuo/.claude/skills/beijing-gaokao-politics/scripts'
sys.path.insert(0,SK)
import batch_health as bh, docx_lib as dl, profile_lib
BOOK='/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
prof=profile_lib.load_profile('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925/profiles_cloud/bixiu3.json')
W=bh.W
def blocks(path):
    d=dl.open_docx(path); P=bh.Prof(prof); bl=bh.walk(d.items,P); return d,bl
def span(d,bl,title):
    b=[x for x in bl if x['title']==title][0]; idx=[b['title_i']]+b['paras']; return list(range(min(idx),max(idx)+1)), b
def rsig(p):
    out=[]
    for r in p.iter(W+'r'):
        t=''.join(x.text or '' for x in r.iter(W+'t'))
        rpr=r.find(W+'rPr'); s=etree.tostring(rpr,method='c14n').decode() if rpr is not None else ''
        out.append((t,s))
    # merge adjacent runs with same fmt
    m=[]
    for t,s in out:
        if m and m[-1][1]==s: m[-1]=(m[-1][0]+t,s)
        else: m.append((t,s))
    return m
def ppr(p):
    x=p.find(W+'pPr'); return etree.tostring(x,method='c14n').decode() if x is not None else ''
for name,title,out in [('img','例题 5　2026门头沟一模第17题','gold/gold_img_out.docx'),('tbl','例题 3　2024朝阳二模第18题','gold/gold_tbl_out.docx')]:
    d0,b0=blocks(BOOK); d1,b1=blocks(out)
    t0=[it['text'] for it in d0.items]; t1=[it['text'] for it in d1.items]
    print('==',name,'whole-doc text flow equal:',t0==t1, 'n',len(t0),len(t1))
    if t0!=t1:
        sm=difflib.SequenceMatcher(a=t0,b=t1,autojunk=False)
        ops=[o for o in sm.get_opcodes() if o[0]!='equal']
        print(' diff opcodes',[(o[0],o[1],o[2],o[3],o[4]) for o in ops][:6])
    titles0=[x['title'] for x in b0]; titles1=[x['title'] for x in b1]
    i0=titles0.index(title); i1=titles1.index(title)
    print(' block order: orig neighbors',titles0[i0-1:i0+2],' new neighbors',titles1[i1-1:i1+2])
    s0,_=span(d0,b0,title); s1,_=span(d1,b1,title)
    fmt_run=fmt_ppr=0; ex=[]
    for a,b in zip(s0,s1):
        pa,pb=d0.paras[a],d1.paras[b]
        if ppr(pa)!=ppr(pb): fmt_ppr+=1
        ra,rb=rsig(pa),rsig(pb)
        if ra!=rb:
            fmt_run+=1
            if len(ex)<4: ex.append({'text':d0.items[a]['text'][:30],'orig_runs':len(ra),'new_runs':len(rb),'orig_fmt_segments':[x[0][:12] for x in ra][:6]})
    print(' paras',len(s0),len(s1),' pPr differ',fmt_ppr,' run-format differ',fmt_run)
    for e in ex: print('   ',e)
