from common import *
from lxml import etree
import zipfile
for wcm in (-5, 1e-9):
    u = {'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':BOOK_SHA,'approved_by':'claude:review-r3','approval_ref':'审查探针',
     'inserts':[{'id':'W1','anchor':{'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}},
       'template_block':{'title_contains':'例题 5　2026门头沟一模第17题'},
       'title':'例题 90　2099审查探针宽度第1题','source_zone':'restore','reason':'审查探针：width_cm 取值校验',
       'content':[{'role':'source','text':'【题目】17．（8分）'},{'role':'source','text':'某市推进社区治理创新。'},
        {'role':'image','from':{'docx':str(R/'00_共同资料/原材料/2023模拟题/2023各区模拟题(1)/各区二模/√西城/西城-高三政治二模试卷-定(2).docx'),'rid':'rId14'},'width_cm':wcm},
        {'role':'source','text':'结合材料，运用《政治与法治》知识，说明其意义。'},
        {'role':'teaching','like':'思维链条','text':'【思维链条】'},{'role':'teaching','like':'答案落点','text':'【答案落点】'},
        {'role':'teaching','text':'①发展基层民主。'},{'role':'rubric','text':'【细则说明】 每点2分。'}]}]}
    docx = copy_book('w_parent.docx'); up = wjson('w_insert.json', u)
    out = WORK/'w_out.docx'; out.unlink(missing_ok=True)
    rc, so, se = run(['apply','--docx',docx,'--insert',up,'--out',out,'--profile',PROF])
    print('width_cm=',wcm,'rc=',rc,'out_exists=',out.exists(),'stdout=',so.strip()[:200],'stderr=',se.strip()[-300:])
    if out.exists():
        with zipfile.ZipFile(out) as z: root = etree.fromstring(z.read('word/document.xml'))
        for ext in root.iter(bi.WP_NS+'extent'):
            cx = int(ext.get('cx')); cy = int(ext.get('cy'))
            if cx <= 0 or cy <= 0: print('   INVALID extent in output:', cx, cy)
        try:
            import docx as pd
            doc = pd.Document(str(out))
            print('   python-docx opens OK (verify_output passed)')
        except Exception as e: print('   python-docx fail', e)
