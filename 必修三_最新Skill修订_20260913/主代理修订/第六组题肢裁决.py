from pathlib import Path
import zipfile,json,hashlib,shutil
from lxml import etree as E
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');s=R/'必修三政治与法治宝典_R31续修_第43批_候选5.docx';z=zipfile.ZipFile(s);root=E.fromstring(z.read('word/document.xml'));ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};b=root.find('w:body',ns);tx=lambda p:''.join(p.xpath('.//w:t/text()',namespaces=ns))
ps=[p for p in b if tx(p)=='449、全国统一的市场准入有利于促进民营经 济组织公平竞争'];assert len(ps)==2
log=[]
for p in ps:log.append({'i':list(b).index(p),'before':tx(p),'after':None});b.remove(p)
for p in b:
 if '732' in tx(p):
  print('COUNT',tx(p))
  for t in p.xpath('.//w:t',namespaces=ns):
   if t.text and '732' in t.text:t.text=t.text.replace('732','731')
o=R/'必修三政治与法治宝典_R31续修_第43批_候选6.docx'
with zipfile.ZipFile(o,'w',zipfile.ZIP_DEFLATED) as out:
 for info in z.infolist():out.writestr(info,E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
record={'parent_sha256':hashlib.sha256(s.read_bytes()).hexdigest(),'output_sha256':hashlib.sha256(o.read_bytes()).hexdigest(),'changes':log,'decision':'449移出A1/A2：判定关键为统一市场准入促进民营经济公平竞争，属于必修二；不因同题另一肢考公民参与就成组收入。','source':'/Users/wanglifei/Desktop/2025模拟题/2025各区二模/2025丰台二模/试卷/试卷.pdf','page':3,'question':8,'option':'②','source_seen':'主代理已查看完整原页','retained_claims':731,'excluded_claims':81}
(R/'主代理修订/第六组题肢裁决记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));shutil.copy2(o,R/'必修三政治与法治宝典_R31续修_第43批_阶段审查稿.docx');print(record['output_sha256'])
