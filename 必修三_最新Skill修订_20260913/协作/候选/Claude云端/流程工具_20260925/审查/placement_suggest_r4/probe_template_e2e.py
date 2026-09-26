import sys, json
sys.dont_write_bytecode = True
from pathlib import Path
from collections import Counter
C = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(C))
import placement_suggest as ps
import block_insert as bi
import docx_lib as dl
import apply_patch as ap
from profile_lib import load_profile
B = '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
prof = load_profile(str(C/'profiles_cloud'/'bixiu3.json'))
book = ps.load_book(B, prof)
blocks = book['blocks']
d = dl.open_docx(B)
_, _, bh_blocks, _ = ap.zones_of(d, prof)
assert [b['title'] for b in blocks] == [b['title'] for b in bh_blocks]
intro = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
idx = ps.build_indices(ps.block_fields_all(blocks, intro), [2, 3])
res = Counter(); bad = []
for qkind, kset in ps.KIND_GROUPS.items():
    # 每个组都当一次“第一名”：用该组每个题块当最像块（覆盖 _pick_template_block 的所有分支）
    combined = [0.0] * len(blocks)
    ranked = ps.aggregate_methods(blocks, combined, kset, set(), ps.DEFAULT_PARAMS)
    for g in ranked:
        for top in g['block_idxs']:
            g2 = dict(g); g2['block_idxs'] = [top] + [i for i in g['block_idxs'] if i != top]
            det = ps.candidate_detail(book, g2, {'material': '', 'ask': '', 'rubric': ''}, idx, 50)
            tb = det['template_block']
            hits = [b for b in bh_blocks if tb['title_contains'] in (b['title'] or '')]
            ok_unique = (len(hits) == 1)
            res[(qkind, 'claims_unique' if tb['template_unique'] else 'claims_not_unique', 'bi_unique' if ok_unique else 'bi_not_unique')] += 1
            if tb['template_unique'] != ok_unique:
                bad.append((qkind, tb['id'], tb['title']))
            # 原样把 template_block 字典塞进 block_insert 插入单，看 schema 校验
try:
    bi._check_keys(det['template_block'], bi._BLOCK_SPEC_KEYS, 'I001.template_block')
    schema = 'accepted'
except bi.Abort as e:
    schema = f'Abort: {e}'
out = Path(__file__).with_suffix('.log')
out.write_text(json.dumps({str(k): v for k, v in res.items()}, ensure_ascii=False, indent=1)
               + f'\nmismatch(template_unique vs block_insert 实际命中数): {len(bad)} {bad[:10]}'
               + f'\n把 candidates[*].template_block 原样放进 block_insert 插入单：{schema}\n', encoding='utf-8')
print(out.read_text())
