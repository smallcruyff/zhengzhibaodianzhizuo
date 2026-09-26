from common import *
import block_insert as bi, apply_patch as ap, docx_lib as dl
prof, book, idx = load()
blocks = book['blocks']
d = dl.open_docx(str(BOOK3))
_, _, bh_blocks, _ = ap.zones_of(d, prof)
assert [b['title'] for b in blocks] == [b['title'] for b in bh_blocks]
combined = [0.0]*len(blocks)
n = 0
for qkind, kset in ps.KIND_GROUPS.items():
    for g in ps.aggregate_methods(blocks, combined, kset, set(), ps.DEFAULT_PARAMS):
        last_idx = max(g['block_idxs'], key=lambda i: blocks[i]['p_range'][0])
        last_b = blocks[last_idx]
        is_choice = blocks[g['block_idxs'][0]]['kind'] == 'choice'
        anchor, uniq, note = ps.anchor_for_group(blocks, g['group_key'], last_b, is_choice)
        k = next(iter(anchor))
        if k != 'before_block':
            continue
        n += 1
        kind, rb, pos = bi.resolve_insert_anchor(bh_blocks, anchor)
        lb = bh_blocks[last_idx]
        end = bi.block_extent_end(lb)
        print('==', qkind, g['group_key'][1], '|', g['group_key'][2][:30], 'last=', last_b['id'], last_b['title'][:30], 'extent_end=', end, 'before=', rb['title'][:30], 'title_i=', rb['title_i'])
        for p in range(end + 1, rb['title_i']):
            para = d.paras[p]
            txt = ''.join(t.text or '' for t in para.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t'))
            st = para.find('.//{http://schemas.openxmlformats.org/wordprocessingml/2006/main}pStyle')
            sid = st.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val') if st is not None else None
            print('   gap p%d style=%s text=%r' % (p, sid, txt[:60]))
print('before_block groups:', n)
