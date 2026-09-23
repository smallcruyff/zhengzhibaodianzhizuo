from pathlib import Path
from copy import deepcopy
import zipfile,json,hashlib
from lxml import etree as E
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');s=R/'必修三政治与法治宝典_R31续修_第43批_原生核验3.docx';z=zipfile.ZipFile(s);root=E.fromstring(z.read('word/document.xml'));n={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};w='{'+n['w']+'}';b=root.find('w:body',n);tx=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=n));logs=[]
ps=[p for p in b if tx(p).startswith('● 统筹中华民族伟大复兴战略全局')];assert len(ps)==1
p=ps[0];pp=p.find('w:pPr',n);jc=pp.find('w:jc',n)
if jc is None:jc=E.SubElement(pp,w+'jc')
jc.set(w+'val','left');logs.append({'text':tx(p),'change':'清单段落左对齐，保留五行原文与手动换行，避免两端对齐拉大字距'})
headers=[p for p in b if tx(p)=='2024东城一模第4题（第494—497肢依次对应原题①—④）'];assert len(headers)==2
template=next(p for p in b if tx(p)=='2024朝阳一模第8题')
for p in headers:
 pp=p.find('w:pPr',n)
 if pp is not None:p.remove(pp)
 p.insert(0,deepcopy(template.find('w:pPr',n)))
 for r in p.findall('w:r',n):
  rp=r.find('w:rPr',n)
  if rp is None:rp=E.Element(w+'rPr');r.insert(0,rp)
  bold=rp.find('w:b',n)
  if bold is None:bold=E.SubElement(rp,w+'b')
  bold.set(w+'val','1')
 logs.append({'text':tx(p),'change':'与邻接题源标题采用相同段落格式并加粗'})
o=R/'必修三政治与法治宝典_R31续修_第43批_候选8.docx'
with zipfile.ZipFile(o,'w',zipfile.ZIP_DEFLATED) as out:
 for info in z.infolist():out.writestr(info,E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
assert [''.join(p.xpath('.//w:t/text()',namespaces=n)) for p in E.fromstring(zipfile.ZipFile(s).read('word/document.xml')).find('w:body',n)]==[tx(p) for p in b]
(R/'主代理修订/第八组局部版式记录.json').write_text(json.dumps({'parent_sha256':hashlib.sha256(s.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'changes':logs},ensure_ascii=False,indent=2));print('saved',o)
