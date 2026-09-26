import sys
sys.dont_write_bytecode = True
import json, zipfile
from lxml import etree
from common import *
sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import docx_lib as dl, batch_health as bh
W = bh.W
SRC = R / '00_共同资料/原材料/2023模拟题/2023各区模拟题(1)/期末和期中/2023北京海淀高三（上）期中政治（教师版）.docx'
content = [
 {'role': 'source', 'text': '【题目】18．（9分）民营经济是推进中国式现代化的生力军，是高质量发展的重要基础，是推动我国全面建成社会主义现代化强国、实现第二个百年奋斗目标的重要力量。'},
 {'role': 'source', 'text': '结合当前民营经济发展面临的形势和民营经济工作现状，我国先后推出系列促进民营经济发展壮大的政策举措，以下是部分摘录。'},
 {'role': 'table', 'from': {'docx': str(SRC), 'table_index': 5}},
 {'role': 'source', 'text': '（1）阅读材料，在上表中的横线处填写适当内容。（2分）'},
 {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】'},
 {'role': 'teaching', 'like': '从材料选知识', 'text': '从材料选知识：最高人民法院发布典型案例、最高人民检察院印发意见，提示司法机关依法保护民营企业产权和企业家权益。'},
 {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】'},
 {'role': 'teaching', 'like': '总述', 'text': '①强化法治保障。'},
 {'role': 'rubric', 'text': '【细则说明】 （1）强化法治保障（2分）。'},
]
u = unit(content, title='例题 91　2024海淀期中第18(1)题', sz='restore',
         anchor={'after_block': {'title_contains': '例题 3　2024朝阳二模第18题'}})
rc, so, se, out, rep = apply(u, 'real_docx_tbl', ['--health', '--renumber'])
res = {'rc': rc, 'stderr': se[-600:], 'stdout': so[-300:], 'health': {k: v for k, v in (rep.get('health') or {}).items() if k != 'new_FAIL'},
       'new_FAIL': [(f['check'], f['rule'], f.get('excerpt')) for f in (rep.get('health') or {}).get('new_FAIL', [])],
       'bic': rep.get('verify', {}).get('block_index_check'), 'fallbacks': [p.get('fallbacks') for p in rep.get('plan', [])],
       'renumber_ok': (rep.get('renumber') or {}).get('ok')}
print(json.dumps(res, ensure_ascii=False, indent=1))
# 格式比较：新表 vs 样板表（B0003 表）
if out.exists():
    d = dl.open_docx(out)
    tops = [el for el in d.body.iter(W + 'tbl') if el.getparent() is d.body]
    def tblinfo(t):
        tp = t.find(W + 'tblPr')
        rows = t.findall(W + 'tr')
        cells = []
        for tr in rows[:2]:
            for tc in tr.findall(W + 'tc'):
                p = tc.find(W + 'p')
                ppr = p.find(W + 'pPr') if p is not None else None
                r = p.find(W + 'r') if p is not None else None
                rpr = r.find(W + 'rPr') if r is not None else None
                cells.append({'text': dl.para_text(p)[:12] if p is not None else None,
                              'pPr': etree.tostring(ppr, encoding=str)[:300] if ppr is not None else None,
                              'rPr': etree.tostring(rpr, encoding=str)[:300] if rpr is not None else None})
        return {'tblPr': etree.tostring(tp, encoding=str)[:800] if tp is not None else None, 'cells': cells[:4]}
    new_t = [t for t in tops if '政策聚焦' in ''.join(x.text or '' for x in t.iter(W + 't'))]
    tmpl_t = [t for t in tops if '政府工作报告' in ''.join(x.text or '' for x in t.iter(W + 't'))][:1]
    print('NEW TABLE', json.dumps(tblinfo(new_t[0]), ensure_ascii=False, indent=1) if new_t else None)
    print('TEMPLATE TABLE', json.dumps(tblinfo(tmpl_t[0]), ensure_ascii=False, indent=1) if tmpl_t else None)
    # 新表单元格段落的样式名
    for i, it in enumerate(d.items):
        if it['tbl'] is not None and ('政策聚焦' in it['text'] or '优化营商环境' in it['text']):
            print('cell style:', it['style'], it['text'][:10])
