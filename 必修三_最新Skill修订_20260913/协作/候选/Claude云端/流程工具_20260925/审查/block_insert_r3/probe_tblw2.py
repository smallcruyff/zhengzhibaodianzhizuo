from common import *
d = dl.open_docx(BOOK)
prof = bi.load_profile(str(PROF))
_,_,blocks,_ = ap.zones_of(d, prof)
tops = bi._top_tables(d.body)
for b in blocks:
    nums = sorted({d.items[i]['tbl'] for i in (b.get('paras') or []) if d.items[i]['tbl']})
    if not nums: continue
    t = tops[nums[0]-1]
    tw = t.find(f'{W}tblPr/{W}tblW'); lay = t.find(f'{W}tblPr/{W}tblLayout')
    typ = tw.get(W+'type') if tw is not None else None
    if typ != 'dxa':
        grid = [int(g.get(W+'w') or 0) for g in t.findall(f'{W}tblGrid/{W}gridCol')]
        print(b['title'][:40], 'tblW', typ, tw.get(W+'w') if tw is not None else None, 'layout', lay.get(W+'type') if lay is not None else None, 'grid_sum', sum(grid))
