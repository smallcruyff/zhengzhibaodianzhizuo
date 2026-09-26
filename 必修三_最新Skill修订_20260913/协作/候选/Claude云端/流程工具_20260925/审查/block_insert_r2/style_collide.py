import sys
sys.dont_write_bytecode=True
import zipfile, re, json
from lxml import etree
from common import *
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def styles(p):
    root=etree.fromstring(zipfile.ZipFile(p).read('word/styles.xml'))
    return {s.get(W+'styleId'):(s.get(W+'type'), (s.find(W+'name').get(W+'val') if s.find(W+'name') is not None else None)) for s in root.findall(W+'style')}
def tables(p):
    root=etree.fromstring(zipfile.ZipFile(p).read('word/document.xml'))
    return [el for el in root.find(W+'body') if el.tag==W+'tbl']
def refs(t):
    out=[]
    for tag,kind in ((W+'tblStyle','tbl'),(W+'pStyle','p'),(W+'rStyle','r')):
        for el in t.iter(tag):
            out.append((kind, el.get(W+'val')))
    return out
book=styles(BOOK)
cases=[('21.docx', R/'00_共同资料/原材料/2024模拟题/东城二模/细则/分题细则/阅卷总结/21题/21.docx', 1),
       ('17(1).docx', R/'00_共同资料/原材料/2024模拟题/东城二模/细则/分题细则/阅卷总结/17题/17(1).docx', 1),
       ('海淀期中教师版', R/'00_共同资料/原材料/2023模拟题/2023各区模拟题(1)/期末和期中/2023北京海淀高三（上）期中政治（教师版）.docx', 5)]
res={}
for name,p,k in cases:
    src=styles(p); t=tables(p)[k-1]
    rs={}
    for kind,v in refs(t):
        key=f'{kind}:{v}'
        if key in rs: continue
        rs[key]={'source':src.get(v),'book_same_id':book.get(v),'kept_by_tool': v in book}
    res[name]=rs
print(json.dumps(res,ensure_ascii=False,indent=1))
