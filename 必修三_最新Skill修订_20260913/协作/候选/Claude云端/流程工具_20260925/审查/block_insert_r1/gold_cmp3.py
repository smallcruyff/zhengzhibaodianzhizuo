import sys; sys.dont_write_bytecode=True
exec(open('gold_cmp.py').read().split("def rsig")[0])
def sig(el):
    if el is None: return ()
    return tuple(sorted((c.tag.split('}')[1], tuple(sorted((k.split('}')[-1],v) for k,v in c.attrib.items()))) for c in el))
def runs(p):
    out=[]
    for r in p.iter(W+'r'):
        t=''.join(x.text or '' for x in r.iter(W+'t'))
        s=sig(r.find(W+'rPr'))
        if out and out[-1][1]==s: out[-1]=(out[-1][0]+t,s)
        else: out.append((t,s))
    return out
res=[]
for name,title,out in [('img','例题 5　2026门头沟一模第17题','gold/gold_img_out.docx'),('tbl','例题 3　2024朝阳二模第18题','gold/gold_tbl_out.docx')]:
    d0,b0=blocks(BOOK); d1,b1=blocks(out)
    s0,_=span(d0,b0,title); s1,_=span(d1,b1,title)
    print('==',name)
    for a,b in zip(s0,s1):
        pa,pb=d0.paras[a],d1.paras[b]
        A,B=sig(pa.find(W+'pPr')),sig(pb.find(W+'pPr'))
        if A!=B: print(' pPr',repr(d0.items[a]['text'][:12]),'only-orig',set(A)-set(B),'only-new',set(B)-set(A))
        ra,rb=runs(pa),runs(pb)
        if ra!=rb:
            if len(ra)!=len(rb): print(' runs',repr(d0.items[a]['text'][:12]),'orig segs',[(t[:8],dict((x[0],x[1]) for x in s).keys()) for t,s in ra][:3],'-> new segs',[(t[:8],) for t,s in rb][:3])
            else:
                for (ta,sa),(tb,sb) in zip(ra,rb):
                    if sa!=sb: print(' rPr',repr(ta[:10]),'only-orig',set(sa)-set(sb),'only-new',set(sb)-set(sa))
