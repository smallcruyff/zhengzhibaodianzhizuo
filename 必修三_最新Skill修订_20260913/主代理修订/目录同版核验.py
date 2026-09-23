from pathlib import Path
from lxml import etree as E
from pypdf import PdfReader
import zipfile,json,re,logging,unicodedata
logging.getLogger('pypdf').setLevel(logging.ERROR)
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');p=R/'必修三政治与法治宝典_R31续修_第43批_阶段审查稿.docx';z=zipfile.ZipFile(p);ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'};root=E.fromstring(z.read('word/document.xml'));pages=[x.extract_text() for x in PdfReader(p.with_suffix('.pdf')).pages];norm=lambda x:re.sub(r'\s+','',unicodedata.normalize('NFKC',x).translate(str.maketrans({'⺠':'民','⻆':'角'})))
rows=[]
for instr in root.xpath('//w:instrText[contains(text(),"PAGEREF")]',namespaces=ns):
 ref=re.search(r'PAGEREF\s+(\S+)',instr.text).group(1);para=instr.getparent().getparent();t=''.join(para.xpath('.//w:t/text()',namespaces=ns));v=re.search(r'(\d+)\s*$',t);assert v,t;n=int(v.group(1));bm=root.xpath('//w:bookmarkStart[@w:name=$ref]',namespaces=ns,ref=ref)[0];head=''.join(bm.getparent().xpath('.//w:t/text()',namespaces=ns));ok=norm(head) in norm(pages[n-1]);rows.append({'bookmark':ref,'heading':head,'cached_page':n,'heading_present_on_pdf_page':ok})
assert len(rows)==32;assert all(x['heading_present_on_pdf_page'] for x in rows),[x for x in rows if not x['heading_present_on_pdf_page']]
(R/'主代理修订/验收PDF全文.json').write_text(json.dumps(pages,ensure_ascii=False));(R/'主代理修订/目录同版核验.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2));print('32目录缓存页码与PDF实际标题页全部匹配')
