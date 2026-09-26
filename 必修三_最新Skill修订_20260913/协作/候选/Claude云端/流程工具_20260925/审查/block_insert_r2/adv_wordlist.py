import sys
sys.dont_write_bytecode = True
import json
from common import *
sys.path.insert(0, str(C)); sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import block_insert as bi
import docx_lib as dl
res = {}
# 1) role=source + style=分析过程（教学样式）+ restore：词表豁免被用到教学栏目
content = [{'role': 'source', 'text': '【题目】审查探针材料一句。'},
           {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】'},
           {'role': 'source', 'style': '分析过程', 'text': '从材料选知识：此处待核，TODO 占位，本落位示例。'}]
u = unit(content, sz='restore')
rc, so, se, out, rep = apply(u, 'wl_style_bypass', ['--health'])
info = {'rc': rc, 'stderr': se.strip()[-400:], 'out_exists': out.exists()}
if out.exists():
    d = dl.open_docx(out)
    for i, it in enumerate(d.items):
        if '待核' in it['text']:
            info['landed_style'] = it['style']; info['text'] = it['text']
    info['new_FAIL'] = [ (f['check'], f['rule'], f.get('excerpt')) for f in rep.get('health', {}).get('new_FAIL', [])]
res['style_override_bypass_restore'] = info
# 2) 同样内容但不带 --health：退出码？
rc, so, se, out, rep = apply(u, 'wl_style_bypass_nohealth')
res['style_override_bypass_restore_nohealth'] = {'rc': rc, 'out_exists': out.exists(), 'stderr': se.strip()[-200:]}
# 3) 对照：role=teaching 同一文字 → 应中止
content2 = [{'role': 'source', 'text': '【题目】审查探针材料一句。'},
            {'role': 'teaching', 'style': '分析过程', 'text': '从材料选知识：此处待核，TODO 占位，本落位示例。'}]
rc, so, se, out, rep = apply(unit(content2, sz='restore'), 'wl_control')
res['control_teaching_role'] = {'rc': rc, 'stderr': se.strip()[-200:]}
print(json.dumps(res, ensure_ascii=False, indent=1))
