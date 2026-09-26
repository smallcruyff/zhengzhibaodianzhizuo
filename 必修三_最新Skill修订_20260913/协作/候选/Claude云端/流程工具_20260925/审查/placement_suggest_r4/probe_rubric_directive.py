import sys
sys.dont_write_bytecode = True
import re, json
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
RX = re.compile(r'(采用评分小节|正式评分优先读取|采用正式评分|评分小节)[：:]\s*`?([^`\n]+?)`?\s*(?:\n|$)')
out = []
cnt = Counter()
for p in sorted((BANK/'questions').glob('*/*.md')):
    if p.name == 'README.md': continue
    text = p.read_text(encoding='utf-8', errors='replace')
    ms = RX.findall(text)
    if not ms: continue
    try:
        q = ps.parse_question_md(text, p.stem)
    except ps.InputError as e:
        out.append(f'{p.stem}\tINPUTERROR\t{ms}'); continue
    cnt[(q['kind'], q['e1_present'])] += 1
    d = ms[0][1].strip()
    heads = [h for _,h,_,_ in ps.all_headings(text)]
    same = (q['e1_header'] or '').strip() == d
    out.append(f"{p.stem}\t{q['kind']}\te1={q['e1_present']}\tdirective={ms}\ttool_e1_header={q['e1_header']}\tsame={same}\tdirective_exists={d in heads}")
Path(__file__).with_suffix('.log').write_text(json.dumps({str(k):v for k,v in cnt.items()}, ensure_ascii=False)+'\n'+'\n'.join(out), encoding='utf-8')
print(json.dumps({str(k):v for k,v in cnt.items()}, ensure_ascii=False)); print('\n'.join(out[:80]))
