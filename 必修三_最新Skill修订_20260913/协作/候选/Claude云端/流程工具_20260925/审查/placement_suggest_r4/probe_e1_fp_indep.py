import sys
sys.dont_write_bytecode = True
import re, json, csv
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
idx = {}
with (BANK/'indexes'/'rubric_links.csv').open(encoding='utf-8-sig', newline='') as f:
    for row in csv.DictReader(f):
        idx.setdefault(row.get('question_id','').strip(), set()).add((row.get('pair_status') or '').strip())
NEG = re.compile(r'未确认|尚未|候选|未找到|（无）|^\(无\)|不适用|暂缺|未匹配|未提供|无正式|不得|非\s*E1|E3|仅供参考|参考答案|答案要点')
PTS = re.compile(r'[（(]\s*\d+\s*分\s*[)）]|\d+\s*分[；;，,。]|得\s*\d+\s*分|给\s*\d+\s*分|\d分')
rows=[]; cnt=Counter()
for p in sorted((BANK/'questions').glob('*/*.md')):
    if p.name=='README.md': continue
    text = p.read_text(encoding='utf-8', errors='replace')
    try: q = ps.parse_question_md(text, p.stem)
    except ps.InputError: continue
    if q['kind']=='choice' or not q['e1_present']: continue
    r = q['rubric'] or ''
    head = '\n'.join([l for l in r.splitlines() if l.strip()][:3])[:200]
    npts = len(PTS.findall(r))
    st = sorted(idx.get(p.stem, []))
    neg = NEG.search(head)
    cnt[('idx_formal' if '已匹配正式材料' in st else 'idx_other', 'neg' if neg else 'ok', 'pts>=1' if npts else 'pts0')] += 1
    if neg or npts == 0:
        rows.append({'key':p.stem,'idx':st,'e1_header':q['e1_header'],'npts':npts,'neg':neg.group(0) if neg else None,'head':head[:160]})
log = Path(__file__).with_suffix('.log')
log.write_text(json.dumps({str(k):v for k,v in cnt.items()},ensure_ascii=False,indent=0)+'\n'+'\n'.join(json.dumps(r,ensure_ascii=False) for r in rows), encoding='utf-8')
print(log.read_text()[:9000])
