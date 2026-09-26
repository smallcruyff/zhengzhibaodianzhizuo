import sys
sys.dont_write_bytecode=True
import json, shutil
from common import *
T=Path(__file__).parent/'test_outputs'
u=json.load(open(T/'gold_img_insert.json'))
c=u['inserts'][0]['content']
for it in c:
    t=it.get('text') or ''
    if t.startswith('从设问定层次'):
        it.pop('style',None); it['like']='从设问定层次'
    if it.get('role')=='image': it['from']['docx']=str((T/'gold_pristine_img.docx').resolve())
parent=WORK/'gold_like_parent.docx'; shutil.copyfile(T/'gold_target_img_deleted.docx', parent)
up=WORK/'gold_like_insert.json'; up.write_text(json.dumps(u,ensure_ascii=False),encoding='utf-8')
out=WORK/'gold_like_out.docx'
if out.exists(): out.unlink()
rc,so,se=run(['apply','--docx',parent,'--insert',up,'--out',out,'--profile',PROF])
print('rc',rc,se[-400:])
