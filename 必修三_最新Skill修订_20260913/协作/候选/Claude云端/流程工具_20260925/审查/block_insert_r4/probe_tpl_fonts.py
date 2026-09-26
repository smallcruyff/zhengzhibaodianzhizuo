from common import *
prof = bi.load_profile(str(PROF))
d = dl.open_docx(BOOK)
S = style_ctx()[4]
zone, _, blocks, _ = ap.zones_of(d, prof)
sp = bi._stem_position_index(d, S, prof, blocks)
src = bi._style_ids_for_bucket(prof, S, 'source')
for want in sys.argv[1:]:
    b = [x for x in blocks if want in x['title']][0]
    print('==', b['title'])
    for i in sorted(b.get('paras') or []):
        if d.items[i].get('tbl'):
            continue
        if bi._para_style_id(S, d.paras[i]) not in src: continue
        t = dl.para_text(d.paras[i])
        print(' ', i, pstyle_name(d.paras[i]), bi._para_shape_ctx(t, i in sp), eff_font(d.paras[i]), repr(t[:40]))
