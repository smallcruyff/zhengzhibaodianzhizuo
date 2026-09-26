import sys
sys.dont_write_bytecode = True
from common import *
import block_insert as bi, apply_patch as ap, docx_lib as dl
prof, book, idx = load()
blocks = book['blocks']
d = dl.open_docx(str(BOOK3))
_, _, bh, _ = ap.zones_of(d, prof)
assert [b['title'] for b in blocks] == [b['title'] for b in bh]
comb = [0.0] * len(blocks)
tot = ok = nonuniq = 0; bad = []
for qk, ks in ps.KIND_GROUPS.items():
    for g in ps.aggregate_methods(blocks, comb, ks, set(), ps.DEFAULT_PARAMS):
        li = max(g['block_idxs'], key=lambda i: blocks[i]['p_range'][0])
        lb = blocks[li]
        anchor, uniq, _ = ps.anchor_for_group(blocks, g['group_key'], lb, blocks[g['block_idxs'][0]]['kind'] == 'choice')
        tot += 1
        if not uniq:
            nonuniq += 1
            try:
                bi.resolve_insert_anchor(bh, anchor); bad.append(('nonunique-but-resolved', g['group_key']))
            except bi.Abort:
                pass
            continue
        k = next(iter(anchor))
        try:
            _, rb, pos = bi.resolve_insert_anchor(bh, anchor)
        except bi.Abort as e:
            bad.append((g['group_key'], str(e)[:80])); continue
        ri = bh.index(rb)
        good = (ri == li) if k != 'before_block' else (ri > li and rb['title'] == anchor['before_block']['title_contains'])
        ok += good
        if not good: bad.append((g['group_key'], k))
print('groups', tot, 'unique-ok', ok, 'nonunique', nonuniq, 'bad', bad)
