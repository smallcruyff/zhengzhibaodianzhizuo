import sys; sys.dont_write_bytecode=True
import zipfile, collections
from lxml import etree
SK='/home/user/zhengzhibaodianzhizuo/.claude/skills/beijing-gaokao-politics/scripts'
sys.path.insert(0,SK)
import batch_health as bh, docx_lib as dl, profile_lib
R='/home/user/zhengzhibaodianzhizuo/'
B=R+'必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
prof=profile_lib.load_profile(R+'必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925/profiles_cloud/bixiu3.json')
W=bh.W; WP='{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
PIC='{http://schemas.openxmlformats.org/drawingml/2006/picture}'
z=zipfile.ZipFile(B); root=etree.fromstring(z.read('word/document.xml'))
ids=[e.get('id') for e in root.iter(WP+'docPr')]
c=collections.Counter(ids); print('docPr total',len(ids),'dups',{k:v for k,v in c.items() if v>1})
cn=[e.get('id') for e in root.iter(PIC+'cNvPr')]; print('pic:cNvPr ids',collections.Counter(cn).most_common(5))
print('inline',len(list(root.iter(WP+'inline'))),'anchor',len(list(root.iter(WP+'anchor'))))
bs=[(b.get(W+'id'),b.get(W+'name')) for b in root.iter(W+'bookmarkStart')]
be=[b.get(W+'id') for b in root.iter(W+'bookmarkEnd')]
print('bm start',len(bs),'end',len(be),'paired',sorted(i for i,_ in bs)==sorted(be))
d=dl.open_docx(B)
P=bh.Prof(prof); blocks=bh.walk(d.items,P)
print('blocks',len(blocks))
for b in blocks[:10]:
    tp=d.paras[b['title_i']]
    print(b['title_i'],repr(b['title']),'| method',repr(b['method'][:30]),'| node',repr(b['node'][:20]),'| bm',[x.get(W+'name') for x in tp.findall(W+'bookmarkStart')],'| last',max([b['title_i']]+b['paras']))
meth=collections.Counter((b['node'],b['method']) for b in blocks)
ms=collections.Counter(b['method'] for b in blocks)
print('distinct methods containing 考法1:',[m for m in ms if '考法1' in m][:20])
print('n distinct (node,method) with 考法1 substring:',len([k for k in meth if '考法1' in k[1]]))
