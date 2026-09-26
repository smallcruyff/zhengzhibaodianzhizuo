"""不加 --debug 的异常路径：看退出码、是否有 traceback、提示是否中文。"""
from common import *
base = {'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':BOOK_SHA,'approved_by':'claude:review-r3','approval_ref':'审查探针',
  'inserts':[{'id':'E1','anchor':{'after_block':{'title_contains':'例题 3　2024朝阳二模第18题'}},'template_block':{'title_contains':'例题 3　2024朝阳二模第18题'},
   'title':'例题 93　2099探针卷第1题','source_zone':'approved_edit','reason':'审查探针',
   'content':[{'role':'source','text':'【题目】材料。'},{'role':'teaching','like':'思维链条','text':'【思维链条】'},{'role':'teaching','like':'答案落点','text':'【答案落点】'},{'role':'rubric','text':'【细则说明】 说明。'}]}]}
import copy
cases = []
cases.append(('docx不存在', None, ['check','--docx',WORK/'nope.docx','--insert',None,'--profile',PROF]))
u = [1,2]; cases.append(('插入单顶层是数组', u, None))
u = copy.deepcopy(base); u['inserts'] = [ 'abc' ]; cases.append(('inserts元素不是对象', u, None))
u = copy.deepcopy(base); u['inserts'][0]['content'][0] = {'role':'source','runs':['x']}; cases.append(('runs元素不是对象', u, None))
u = copy.deepcopy(base); u['inserts'][0]['content'].insert(1, {'role':'image','file':str(WORK/'x.png'),'width_cm':'5'}); cases.append(('width_cm是字符串', u, None))
u = copy.deepcopy(base); u['inserts'][0]['anchor'] = 'after'; cases.append(('anchor不是对象', u, None))
u = copy.deepcopy(base); u['inserts'][0]['content'][0]['runs'] = [{'text':'【题目】材料。','bogus':1}]; del u['inserts'][0]['content'][0]['text']; cases.append(('runs里未知键', u, None))
u = copy.deepcopy(base); u['inserts'][0]['title'] = 123; cases.append(('title不是字符串', u, None))
u = copy.deepcopy(base); u['inserts'][0]['content'][1]['like'] = ['思维链条']; cases.append(('like是数组', u, None))
u = copy.deepcopy(base); u['parent_docx_sha256'] = 'f'*64; cases.append(('SHA不符', u, None))
# make a valid png for width_cm case
import fitz
pm = fitz.Pixmap(fitz.csRGB, fitz.IRect(0,0,20,10), False); pm.clear_with(200); (WORK/'x.png').write_bytes(pm.tobytes('png'))
docx = copy_book('err_parent.docx')
for name, u, argv in cases:
    up = wjson(f'err_{name}.json', u if u is not None else base)
    if argv is None: argv = ['check','--docx',docx,'--insert',up,'--profile',PROF]
    argv = [up if a is None else a for a in argv]
    rc, so, se = run(argv)
    tb = 'Traceback' in se
    print(f'{name}: rc={rc} traceback={tb} stderr={se.strip()[-160:]!r} stdout={so.strip()[:80]!r}')
