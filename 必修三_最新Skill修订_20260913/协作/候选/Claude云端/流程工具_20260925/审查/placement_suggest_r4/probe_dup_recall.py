import sys, time, json
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
from profile_lib import load_profile
from block_index import render_recs
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
B = '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
prof = load_profile(str(C/'profiles_cloud'/'bixiu3.json'))
book = ps.load_book(B, prof)
blocks = book['blocks']
btxt = [render_recs(b['_recs'][1:], book['doc']['rels']) for b in blocks]
bsets = [ps._ngram_set(t) for t in btxt]
keys = sorted({b['key'] for b in blocks if b.get('key')})
res = Counter(); miss = []
for k in keys:
    mdp = ps.find_md_path(BANK, k)
    if not mdp.is_file(): res['no_md'] += 1; continue
    try: q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
    except ps.InputError: res['input_error'] += 1; continue
    qs = ps._ngram_set(q['stem_full'])
    own = ps.matching_block_idxs(blocks, k)
    best_own = max((len(qs & bsets[i])/len(qs) if qs and bsets[i] else 0) for i in own)
    kind = q['kind']
    res[(kind, 'detected' if best_own >= ps.DUP_SCAN_THRESHOLD else 'missed')] += 1
    if best_own < ps.DUP_SCAN_THRESHOLD:
        miss.append((k, kind, round(best_own, 3), [blocks[i]['title'][:30] for i in sorted(own)][:3], len(q['stem_full'])))
out = Path(__file__).with_suffix('.log')
with out.open('w', encoding='utf-8') as f:
    f.write('若同题以异键（错号重卷）再来，用书中本题块测 find_suspected_duplicate 的召回（阈值 %.2f）\n' % ps.DUP_SCAN_THRESHOLD)
    f.write(json.dumps({str(a): b for a, b in res.items()}, ensure_ascii=False) + '\n')
    for m in sorted(miss, key=lambda x: x[2]):
        f.write(json.dumps(m, ensure_ascii=False) + '\n')
print(out.read_text()[:6000])

# ---- 对照：去掉题库元数据说明行/页脚后再测（不改工具，只看改进空间）
import re
META = re.compile(r'^(本节|OCR 候选存在|教师版把题面|来源[：:]|- 来源|\*\*核验依据|下列文字是由原卷|表格保真说明)')
FOOT = re.compile(r'第\s*\d+\s*页\s*/\s*共\s*\d+\s*页')
res2 = Counter()
for k in keys:
    mdp = ps.find_md_path(BANK, k)
    if not mdp.is_file(): continue
    try: q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
    except ps.InputError: continue
    clean = '\n'.join(FOOT.sub('', l) for l in q['stem_full'].splitlines() if not META.match(l.strip()))
    qs = ps._ngram_set(clean)
    own = ps.matching_block_idxs(blocks, k)
    best_own = max((len(qs & bsets[i])/len(qs) if qs and bsets[i] else 0) for i in own)
    res2[(q['kind'], 'detected' if best_own >= ps.DUP_SCAN_THRESHOLD else 'missed')] += 1
with out.open('a', encoding='utf-8') as f:
    f.write('\n去元数据行/页脚后的召回（对照）：' + json.dumps({str(a): b for a, b in res2.items()}, ensure_ascii=False) + '\n')
print('cleaned:', dict(res2))
