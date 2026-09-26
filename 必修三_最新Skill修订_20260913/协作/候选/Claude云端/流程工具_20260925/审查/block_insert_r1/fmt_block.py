import sys; sys.dont_write_bytecode=True
exec(open('gold_cmp3.py').read().split("res=[]")[0])
def show(path,title,label):
    d,bl=blocks(path); s,b=span(d,bl,title)
    print('==',label,title,'zone/style/runs')
    for i in s:
        p=d.paras[i]; it=d.items[i]
        rs=runs(p)
        desc=[(t[:10], ('B' if any(x[0]=='b' for x in sg) else '')+('/'+[x for x in sg if x[0]=='color'][0][1][0][1] if any(x[0]=='color' for x in sg) else '')) for t,sg in rs][:3]
        print(' ',i,it.get('zone'),it['style'],'|',desc)
import sys as _s
show(BOOK,'例题 5　2026门头沟一模第17题','ORIG')
show('gold/T1a_真实新题_带图_BJ-2023-XC-ERMO-Q16_out.docx','例题 90　2023西城二模第16题','T1a')
show('gold/T1b_真实新题_带表_BJ-2026-CY-YIMO-Q18_out.docx','例题 91　2026朝阳一模第18题','T1b')
show('gold/T1c_真实新题_纯文字_BJ-2024-HD-ERMO-Q19_out.docx','例题 92　2024海淀二模第19题','T1c')
show(BOOK,'例题 8　2026顺义二模第17题','ORIG-B0008 template')
