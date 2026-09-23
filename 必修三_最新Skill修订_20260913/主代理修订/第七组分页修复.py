from pathlib import Path
import zipfile,hashlib,json
from lxml import etree as E
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');s=R/'必修三政治与法治宝典_R31续修_第43批_原生核验.docx';z=zipfile.ZipFile(s);root=E.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};w='{'+ns['w']+'}';p=root.xpath('//w:body/w:p[w:pPr/w:pStyle[@w:val="21"] and w:pPr/w:keepNext[@w:val="0"]]',namespaces=ns);assert len(p)==5;log=[]
for el in p:
 log.append(''.join(el.xpath('.//w:t/text()',namespaces=ns)));el.find('w:pPr/w:keepNext',ns).set(w+'val','1')
o=R/'必修三政治与法治宝典_R31续修_第43批_候选7.docx'
with zipfile.ZipFile(o,'w',zipfile.ZIP_DEFLATED) as out:
 for info in z.infolist():out.writestr(info,E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
record={'parent_sha256':hashlib.sha256(s.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'heading_keep_next_false_to_true':log,'reason':'第20页出现孤立二级标题；修复五处同类直接取消与下段同页的格式，其余正文与图片不变。'};(R/'主代理修订/第七组分页修复记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(record)
