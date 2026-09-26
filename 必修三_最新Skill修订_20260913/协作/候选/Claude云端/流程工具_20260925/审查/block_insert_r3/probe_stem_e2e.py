"""端到端：以 例题 40　2026通州一模第21题（跨模块）为样板，默认路径（source 不给 like/style）插入两个设问：
A 引号开头设问（原书该块第 933 段原文，原书显式宋体）；B 对照组“结合材料……”开头。读回输出核有效字体。"""
from common import *
import zipfile
from lxml import etree
TPL = '例题 40　2026通州一模第21题（跨模块）'
stemA = '“中国式现代化是干出来的，伟大事业都成于实干。”结合材料，综合运用所学，谈谈你对这一观点的理解。'
stemB = '结合材料，综合运用所学，谈谈你对这一观点的理解。'
u = {'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':BOOK_SHA,'approved_by':'claude:review-r3','approval_ref':'审查探针',
  'inserts':[{'id':'S1','anchor':{'after_block':{'title_contains':TPL}},'template_block':{'title_contains':TPL},
   'title':'例题 41　2099审查探针卷第21题','source_zone':'restore','reason':'审查探针：设问字体',
   'content':[{'role':'source','text':'【题目】21．（9分）'},
              {'role':'source','text':'某地坚持实干担当，推动重大项目落地见效。'},
              {'role':'source','text':stemA},
              {'role':'source','text':stemB},
              {'role':'teaching','like':'思维链条','text':'【思维链条】'},
              {'role':'teaching','like':'答案落点','text':'【答案落点】'},
              {'role':'teaching','text':'①实干推动发展。'},
              {'role':'rubric','text':'【细则说明】 观点明确1分。'}]}]}
docx = copy_book('se_parent.docx'); up = wjson('se_insert.json', u)
out = WORK/'se_out.docx'; out.unlink(missing_ok=True)
rc, so, se = run(['apply','--docx',docx,'--insert',up,'--out',out,'--profile',PROF])
print('rc=', rc, 'out_exists=', out.exists(), se.strip()[-300:])
with zipfile.ZipFile(BOOK) as z: st = etree.fromstring(z.read('word/styles.xml'))
S = bh.Styles(st)
font_idx = {s.get(W+'styleId'): (s.find(f'{W}rPr/{W}rFonts').get(W+'eastAsia') if s.find(f'{W}rPr/{W}rFonts') is not None else None) for s in st.iter(W+'style')}
def eff(p):
    for r, t in ap._run_spans(p):
        if t.strip():
            rpr = r.find(W+'rPr'); rf = rpr.find(W+'rFonts') if rpr is not None else None
            if rf is not None and rf.get(W+'eastAsia'): return rf.get(W+'eastAsia'), 'explicit'
            return font_idx.get(bi._para_style_id(S, p)), 'style-default'
d0 = dl.open_docx(BOOK)
for i, p in enumerate(d0.paras):
    if dl.para_text(p).strip() == stemA: print('ORIGINAL book para', i, 'font', eff(p)); break
if out.exists():
    d1 = dl.open_docx(out)
    for i, p in enumerate(d1.paras):
        t = dl.para_text(p).strip()
        if t in (stemA, stemB) and i > 900 and i < 1100:
            print('OUTPUT para', i, 'shape', bi._para_shape(t), 'font', eff(p), t[:24])
