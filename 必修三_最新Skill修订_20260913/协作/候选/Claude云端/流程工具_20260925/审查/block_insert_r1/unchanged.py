import sys; sys.dont_write_bytecode=True
exec(open('gold_cmp3.py').read().split("res=[]")[0])
import difflib
d0=dl.open_docx(BOOK); s0=[dl.para_sha(p) for p in d0.paras]
for name,title in [('T1a_真实新题_带图_BJ-2023-XC-ERMO-Q16','例题 90　2023西城二模第16题'),('T1b_真实新题_带表_BJ-2026-CY-YIMO-Q18','例题 91　2026朝阳一模第18题'),('T1c_真实新题_纯文字_BJ-2024-HD-ERMO-Q19','例题 92　2024海淀二模第19题')]:
    d1,b1=blocks(f'gold/{name}_out.docx'); s1=[dl.para_sha(p) for p in d1.paras]
    sm=difflib.SequenceMatcher(a=s0,b=s1,autojunk=False)
    ops=[o for o in sm.get_opcodes() if o[0]!='equal']
    sp,_=span(d1,b1,title)
    print(name,'non-equal opcodes',ops,'inserted block span',sp[0],sp[-1])
    # body-level order of other elements (sectPr etc.)
    z0=zipfile.ZipFile(BOOK); z1=zipfile.ZipFile(f'gold/{name}_out.docx')
    for m in z0.namelist():
        if m in ('word/document.xml','word/_rels/document.xml.rels','[Content_Types].xml'): continue
        if z0.read(m)!=z1.read(m): print('  member changed',m)
