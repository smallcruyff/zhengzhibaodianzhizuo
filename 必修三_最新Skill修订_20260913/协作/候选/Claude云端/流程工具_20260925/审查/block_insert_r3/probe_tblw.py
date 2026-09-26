from common import *
import zipfile, glob
from lxml import etree
from collections import Counter
books = [BOOK] + sorted(Path(p) for p in glob.glob(str(R/'其他书工作头/*/*.docx')))
for b in books:
    with zipfile.ZipFile(b) as z: root = etree.fromstring(z.read('word/document.xml'))
    body = root.find(W+'body')
    tops = bi._top_tables(body)
    c = Counter()
    for t in tops:
        tw = t.find(f'{W}tblPr/{W}tblW')
        c[(tw.get(W+'type'), 'w=0' if tw is not None and tw.get(W+'w') in ('0',None) else 'w>0') if tw is not None else ('NONE',)] += 1
    print(b.parent.name, b.name[:30], 'tables', len(tops), dict(c))
