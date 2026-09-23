from pathlib import Path
from lxml import etree as E
import zipfile,hashlib,json,re
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');S=R/'必修三政治与法治宝典_R31续修_第43批_阶段审查稿.docx';N={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'};W='{'+N['w']+'}'
z=zipfile.ZipFile(S);root=E.fromstring(z.read('word/document.xml'));b=root.find('w:body',N);texts=[''.join(p.xpath('.//w:t/text()',namespaces=N)) for p in b]
h3=[i for i,p in enumerate(b) if p.xpath('./w:pPr/w:pStyle[@w:val="31"]',namespaces=N)];assert len(h3)==385
labels=['【题目】','【为什么能想到】','【答案落点】','【细则说明】'];blocks=[]
for j,i in enumerate(h3):
 end=h3[j+1] if j+1<len(h3) else next(k for k in range(i+1,len(b)) if texts[k].startswith('附录一'))
 hits=[(k,label) for k in range(i,end) for label in labels if texts[k].startswith(label)]
 assert [l for k,l in hits]==labels,(j,hits)
 blocks.append({'seq':j+1,'title':texts[i],'h3_body_i':i,'labels':dict((l,k) for k,l in hits)})
a1=next(i for i,t in enumerate(texts) if t=='A1　错肢单练（打印）');a2=next(i for i,t in enumerate(texts) if t=='A2　错肢单练（答案）')
claims=[]
for start,end in [(a1,a2),(a2,len(b))]:
 rows={}
 for i in range(start,end):
  for p in ([b[i]] if b[i].tag==W+'p' else b[i].xpath('.//w:p',namespaces=N)):
   tx=''.join(p.xpath('.//w:t/text()',namespaces=N));match=re.match(r'^(\d+(?:（补\d+）)?)、',tx)
   if match:
    key=match.group(1);assert key not in rows,key;rows[key]={'text':tx,'body_i':i}
 claims.append(rows)
assert len(claims[0])==len(claims[1])==731,(len(claims[0]),len(claims[1]));assert set(claims[0])==set(claims[1]);assert all(claims[0][k]['text']==claims[1][k]['text'] for k in claims[0])
assert '449' not in claims[0] and '675（补4）' not in claims[0]
bookmarks=root.xpath('//w:bookmarkStart/@w:name',namespaces=N);ids=root.xpath('//w:bookmarkStart/@w:id',namespaces=N);endids=root.xpath('//w:bookmarkEnd/@w:id',namespaces=N);assert len(ids)==len(set(ids))==33 and sorted(ids)==sorted(endids)
fields=root.xpath('//w:instrText/text()',namespaces=N);refs=[re.search(r'PAGEREF\s+(\S+)',x).group(1) for x in fields if 'PAGEREF' in x];assert len(refs)==32 and set(refs)<=set(bookmarks)
assert len(root.xpath('//w:drawing',namespaces=N))==95;assert len(b.findall('w:tbl',N))==234;assert not root.xpath('//w:tbl/w:r',namespaces=N)
def media(f):
 q=zipfile.ZipFile(f);t=E.fromstring(q.read('word/document.xml'));rm={x.get('Id'):x.get('Target') for x in E.fromstring(q.read('word/_rels/document.xml.rels'))}
 return [hashlib.sha256(q.read('word/'+rm[x.get('{'+N['r']+'}embed')])).hexdigest() for x in t.xpath('//a:blip',namespaces=N)]
assert media(S)==media(R/'必修三政治与法治宝典_R31续修_第43批_候选6.docx')
orig=Path('/Users/wanglifei/Desktop/gpt6/00_必修三最新审查稿/必修三政治与法治宝典_R31续修_第42批_当前工作稿.docx');origsha=hashlib.sha256(orig.read_bytes()).hexdigest();assert origsha=='f4d5b295e73bebfa67cf86eb8cf3719c91752ff9a7d80ac6381e2c0298359946'
out={'docx':str(S),'sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'original_sha256':origsha,'body_placements':385,'four_columns_ordered':385,'claims_each':731,'excluded':81,'tables':234,'images':95,'used_image_bytes_identical_to_pre_word':True,'bookmarks':33,'pageref_targets_resolved':32,'blocks':blocks,'claims':claims,'visual_review':'separate pending','whole_book_evidence':'not certified'}
(R/'主代理修订/最终技术核验.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print({k:v for k,v in out.items() if k not in ['blocks','claims']})
