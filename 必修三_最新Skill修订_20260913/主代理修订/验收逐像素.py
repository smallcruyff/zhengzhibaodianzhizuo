from pathlib import Path
from PIL import Image,ImageChops
import json,hashlib
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');a=R/'第43批页面';b=R/'第43批页面_验收';same=[];changed=[]
for n in range(1,533):
 p=a/f'page-{n}.png';q=b/p.name
 with Image.open(p) as x,Image.open(q) as y:
  ok=x.size==y.size and ImageChops.difference(x.convert('RGB'),y.convert('RGB')).getbbox() is None
 (same if ok else changed).append(n)
d={'baseline_pdf_sha256':'9b881b6b740e9f219aec8aba581dac66bd0cade749224d1291fb350b3d0cb504','final_pdf_sha256':hashlib.sha256((R/'必修三政治与法治宝典_R31续修_第43批_阶段审查稿.pdf').read_bytes()).hexdigest(),'renderer':'same installed render_docx.py native PDF adapter at 120dpi','comparison':'same physical page, decoded RGB, zero tolerance','identical_pages':same,'changed_pages':changed};(R/'页面检查/验收逐像素核验.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print('same',len(same),'changed',changed)
