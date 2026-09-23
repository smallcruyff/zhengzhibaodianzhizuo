from pathlib import Path
from lxml import etree as E
import zipfile,hashlib,json
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');S=R/'必修三政治与法治宝典_R31续修_第43批_原生核验4.docx';z=zipfile.ZipFile(S);raw=z.read('word/document.xml');root=E.fromstring(raw);n={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};w='{'+n['w']+'}';b=root.find('w:body',n);text=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=n));log=[]
ps=[p for p in b if text(p)=='资料卡一  “五篇大文章”'];assert len(ps)==3
for p in ps:
 pp=p.find('w:pPr',n);kn=pp.find('w:keepNext',n)
 if kn is None:kn=E.SubElement(pp,w+'keepNext')
 kn.set(w+'val','1');log.append({'body_i':list(b).index(p),'text':text(p),'change':'资料卡标题与紧接图片同页'})
p=next(p for p in b if text(p).startswith('● 统筹中华民族伟大复兴战略全局'));pp=p.find('w:pPr',n);ind=pp.find('w:ind',n)
if ind is None:ind=E.SubElement(pp,w+'ind')
ind.set(w+'firstLine','0')
for k in ['firstLineChars','hanging','hangingChars']:
 if w+k in ind.attrib:del ind.attrib[w+k]
log.append({'body_i':list(b).index(p),'text':text(p),'change':'清单各行项目符号同一左边界'})
O=R/'必修三政治与法治宝典_R31续修_第43批_候选9.docx'
with zipfile.ZipFile(O,'w',zipfile.ZIP_DEFLATED) as out:
 for info in z.infolist():out.writestr(info,E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
assert [text(p) for p in E.fromstring(raw).find('w:body',n)]==[text(p) for p in b]
(R/'主代理修订/第九组图题衔接记录.json').write_text(json.dumps({'parent_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(O.read_bytes()).hexdigest(),'changes':log},ensure_ascii=False,indent=2));print('saved')
