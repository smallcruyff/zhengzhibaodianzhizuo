import sys
sys.dont_write_bytecode = True
import zipfile, json
from pathlib import Path
from lxml import etree
R = Path('/home/user/zhengzhibaodianzhizuo/00_共同资料/原材料')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
V = '{urn:schemas-microsoft-com:vml}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
RN = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
stats = {'docx': 0, 'top_vml_img_docs': 0, 'tbl_vml_img_docs': 0, 'tbl_blip_docs': 0, 'tbl_hl_noimg_docs': 0,
         'top_drawing_docs': 0, 'examples_tbl_vml': [], 'examples_top_vml_only': [], 'examples_hl_noimg': []}
for p in R.rglob('*.docx'):
    if p.name.startswith('~$'): continue
    try:
        with zipfile.ZipFile(p) as z:
            root = etree.fromstring(z.read('word/document.xml'))
    except Exception:
        continue
    stats['docx'] += 1
    body = root.find(W + 'body')
    tbl_vml = tbl_blip = hl_noimg = False
    for t in body.iter(W + 'tbl'):
        has_vml = any(True for _ in t.iter(V + 'imagedata'))
        has_blip = any(True for _ in t.iter(A + 'blip'))
        has_hl = any(h.get(RN + 'id') for h in t.iter(W + 'hyperlink'))
        tbl_vml |= has_vml; tbl_blip |= has_blip
        if has_hl and not has_vml and not has_blip: hl_noimg = True
    top_vml = any(True for _ in body.iter(V + 'imagedata'))
    top_draw = any(True for _ in body.iter(A + 'blip'))
    stats['tbl_vml_img_docs'] += tbl_vml; stats['tbl_blip_docs'] += tbl_blip; stats['tbl_hl_noimg_docs'] += hl_noimg
    stats['top_vml_img_docs'] += top_vml; stats['top_drawing_docs'] += top_draw
    rel = str(p.relative_to(R))
    if tbl_vml and len(stats['examples_tbl_vml']) < 5: stats['examples_tbl_vml'].append(rel)
    if top_vml and not top_draw and len(stats['examples_top_vml_only']) < 5: stats['examples_top_vml_only'].append(rel)
    if hl_noimg and len(stats['examples_hl_noimg']) < 5: stats['examples_hl_noimg'].append(rel)
print(json.dumps(stats, ensure_ascii=False, indent=1))
