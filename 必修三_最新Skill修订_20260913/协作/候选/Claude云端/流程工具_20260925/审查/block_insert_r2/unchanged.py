import sys
sys.dont_write_bytecode=True
import zipfile, difflib, json
from common import *
sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import docx_lib as dl
from lxml import etree
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
def seq(p):
    d=dl.open_docx(p)
    return [dl.para_sha(x) for x in d.paras], d
res={}
for name in ('T1a_真实新题_带图_BJ-2023-XC-ERMO-Q16_out','T1b_真实新题_带表_BJ-2026-CY-YIMO-Q18_out','T1c_真实新题_纯文字_BJ-2024-HD-ERMO-Q19_out','b2m1_out','m1docpr_out','gold_img_out','gold_tbl_out'):
    out=Path('test_outputs')/(name+'.docx')
    parent = BOOK if not name.startswith('gold') else Path('test_outputs')/('gold_target_%s_deleted.docx' % name.split('_')[1])
    a,_=seq(parent); b,db=seq(out)
    ops=[op for op in difflib.SequenceMatcher(a=a,b=b,autojunk=False).get_opcodes() if op[0]!='equal']
    za=zipfile.ZipFile(parent); zb=zipfile.ZipFile(out)
    na=[i.filename for i in za.infolist()]; nb=[i.filename for i in zb.infolist()]
    changed=[n for n in na if za.read(n)!=zb.read(n)]
    added=[n for n in nb if n not in na]
    # rel integrity (independent)
    rels=etree.fromstring(zb.read('word/_rels/document.xml.rels'))
    rmap={r.get('Id'):(r.get('Target'),r.get('TargetMode'),r.get('Type').rsplit('/',1)[-1]) for r in rels}
    RN='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
    bad=[]
    root=etree.fromstring(zb.read('word/document.xml'))
    for el in root.iter():
        for k,v in el.attrib.items():
            if k.startswith(RN):
                t=rmap.get(v)
                if t is None: bad.append(('norel',v)); continue
                if t[1]!='External':
                    pth='word/'+t[0] if not t[0].startswith('/') else t[0][1:]
                    if pth not in nb: bad.append(('nomember',v,pth))
                # type sanity
                tag=etree.QName(el).localname
                if tag=='blip' and t[2]!='image': bad.append(('blip->',t[2],v))
                if tag=='hyperlink' and t[2]!='hyperlink': bad.append(('hl->',t[2],v))
    ct=etree.fromstring(zb.read('[Content_Types].xml'))
    exts={c.get('Extension').lower() for c in ct if c.get('Extension')}
    media_ext={n.rsplit('.',1)[-1].lower() for n in nb if n.startswith('word/media/')}
    res[name]={'para_ops':[(o[0],o[1],o[2],o[3],o[4]) for o in ops],'changed_members':changed,'added':added,
               'rel_bad':bad[:5],'ct_uncovered':sorted(media_ext-exts)}
print(json.dumps(res,ensure_ascii=False,indent=0))
