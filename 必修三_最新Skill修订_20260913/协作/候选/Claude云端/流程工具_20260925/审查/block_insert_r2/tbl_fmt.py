import sys
sys.dont_write_bytecode = True
import json, re
from lxml import etree
from common import *
sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import docx_lib as dl, batch_health as bh
W = bh.W
def strip(x):
    s = etree.tostring(x, encoding=str) if x is not None else ''
    s = re.sub(r' xmlns:\w+="[^"]*"', '', s)
    return s
def show(path, key, n=4):
    d = dl.open_docx(path)
    tops = [el for el in d.body if el.tag == W + 'tbl']
    t = [t for t in tops if key in ''.join(x.text or '' for x in t.iter(W + 't'))][0]
    print('tblPr:', strip(t.find(W + 'tblPr'))[:700])
    print('tblGrid:', strip(t.find(W + 'tblGrid'))[:300])
    k = 0
    for tr in t.findall(W + 'tr')[:3]:
        for tc in tr.findall(W + 'tc')[:2]:
            print(' tcPr:', strip(tc.find(W + 'tcPr'))[:200])
            for p in tc.findall(W + 'p')[:1]:
                print('  pPr:', strip(p.find(W + 'pPr'))[:300])
                for r in p.findall(W + 'r')[:2]:
                    print('  rPr:', strip(r.find(W + 'rPr'))[:300], '|', ''.join(x.text or '' for x in r.iter(W+'t'))[:15])
path = sys.argv[1]; key = sys.argv[2]
show(path, key)
