from common import *
prof = bi.load_profile(str(PROF))
d = dl.open_docx(BOOK)
S = style_ctx()[4]
zone, _, blocks, _ = ap.zones_of(d, prof)
OPT = re.compile(r'^[A-D][.．]')
n = 0
for b in blocks:
    ps = [i for i in (b.get('paras') or []) if not d.items[i].get('tbl')]
    if any(OPT.match(dl.para_text(d.paras[i]).strip()) for i in ps):
        n += 1
        if n <= 2:
            print('==', b['title'])
            for i in sorted(ps)[:14]:
                print(i, d.items[i]['style'], d.items[i].get('zone'), repr(dl.para_text(d.paras[i])[:50]), eff_font(d.paras[i]))
print('choice blocks', n, 'total', len(blocks))
