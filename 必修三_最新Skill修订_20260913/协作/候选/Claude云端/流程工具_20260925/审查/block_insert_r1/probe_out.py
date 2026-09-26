import sys; sys.dont_write_bytecode=True
import zipfile, collections, posixpath
from lxml import etree
C='/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0,C)
import block_insert as bi
W=bi.W; A=bi.A_NS; R=bi.R_NS; WP=bi.WP_NS
out=sys.argv[1]
z=zipfile.ZipFile(out); names=set(z.namelist())
root=etree.fromstring(z.read('word/document.xml'))
print('bi._scan_rids(root) ->', len(bi._scan_rids(root)), '(工具写后复核用的扫描)')
blips=[b.get(R+'embed') for b in root.iter(A+'blip')]
print('actual a:blip r:embed count ->', len(blips))
rels={r.get('Id'):(r.get('Target'),r.get('Type')) for r in etree.fromstring(z.read('word/_rels/document.xml.rels'))}
bad=[]
for rid in set(blips):
    t=rels.get(rid)
    if not t: bad.append((rid,'norel')); continue
    p=posixpath.normpath(posixpath.join('word',t[0]))
    if p not in names: bad.append((rid,'missing',p))
    if not t[1].endswith('/image'): bad.append((rid,'type',t[1]))
print('blip rel problems', bad)
# all r:* attributes anywhere
allr=[(el.tag.split('}')[1],k.split('}')[1],v) for el in root.iter() for k,v in el.attrib.items() if k.startswith(R)]
cnt=collections.Counter((t,a) for t,a,_ in allr); print('r:* attrs', cnt)
dang=[x for x in allr if x[2] not in rels]; print('dangling r:* ->', dang[:10])
ct=etree.fromstring(z.read('[Content_Types].xml'))
print('CT defaults', sorted(c.get('Extension') for c in ct if c.tag.endswith('Default')))
ids=[e.get('id') for e in root.iter(WP+'docPr')]
print('docPr dup', {k:v for k,v in collections.Counter(ids).items() if v>1})
