from pathlib import Path
from copy import deepcopy
import zipfile,json,hashlib,shutil
from lxml import etree as E
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913')
s=R/'必修三政治与法治宝典_R31续修_第43批_候选4.docx'
z=zipfile.ZipFile(s); root=E.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};w='{'+ns['w']+'}';b=root.find('w:body',ns)
old=Path('/Users/wanglifei/Desktop/gpt6/00_必修三最新审查稿/必修三政治与法治宝典_R31续修_第42批_当前工作稿.docx');oz=zipfile.ZipFile(old);ob=E.fromstring(oz.read('word/document.xml')).find('w:body',ns)
template=ob[6357];assert template.tag==w+'p'
malformed=b.xpath('./w:tbl[w:r]',namespaces=ns);assert len(malformed)==14
logs=[]
for tb in malformed:
 tx=''.join(tb.xpath('./w:r/w:t/text()',namespaces=ns));assert tx
 p=deepcopy(template)
 for c in list(p):
  if c.tag!=w+'pPr':p.remove(c)
 r=E.SubElement(p,w+'r');t=E.SubElement(r,w+'t');t.text=tx
 logs.append({'body_i':list(b).index(tb),'text':tx});b.replace(tb,p)
assert len(b.findall('w:tbl',ns))==234
assert len(b.findall('w:p',ns))==6183
assert not root.xpath('//w:tbl/w:r',namespaces=ns)
o=R/'必修三政治与法治宝典_R31续修_第43批_候选5.docx'
with zipfile.ZipFile(o,'w',zipfile.ZIP_DEFLATED) as out:
 for info in z.infolist():out.writestr(info,E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
record={'parent_sha256':hashlib.sha256(s.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'repair':'14 inserted material blocks changed from invalid table clone to neutral paragraphs','changes':logs,'paragraphs':6183,'tables':234}
(R/'主代理修订/第五组结构修复记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));shutil.copy2(o,R/'必修三政治与法治宝典_R31续修_第43批_阶段审查稿.docx');print(json.dumps(record,ensure_ascii=False))
