from common import *
import zipfile, re
from lxml import etree
d = dl.open_docx(BOOK)
prof = bi.load_profile(str(PROF))
with zipfile.ZipFile(BOOK) as z:
    st = etree.fromstring(z.read('word/styles.xml'))
S = bh.Styles(st)
font_idx, based = {}, {}
for s in st.iter(W+'style'):
    sid = s.get(W+'styleId'); rf = s.find(f'{W}rPr/{W}rFonts'); b = s.find(W+'basedOn')
    font_idx[sid] = rf.get(W+'eastAsia') if rf is not None else None
    based[sid] = b.get(W+'val') if b is not None else None
rf0 = st.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}rFonts')
dfont = rf0.get(W+'eastAsia') if rf0 is not None else None
def chain(sid):
    seen=set()
    while sid and sid not in seen:
        seen.add(sid)
        if font_idx.get(sid): return font_idx[sid]
        sid = based.get(sid)
    return dfont
def eff_font(p):
    sid = bi._para_style_id(S, p)
    for r, t in ap._run_spans(p):
        if not t.strip(): continue
        rpr = r.find(W+'rPr'); rf = rpr.find(W+'rFonts') if rpr is not None else None
        if rf is not None and rf.get(W+'eastAsia'): return rf.get(W+'eastAsia')
        return chain(sid)
    return None
src_ids = bi._style_ids_for_bucket(prof, S, 'source')
print({sid: (S.name.get(sid), chain(sid)) for sid in src_ids})
_, _, blocks, _ = ap.zones_of(d, prof)
subj_stem_match, subj_stem_nomatch, kaiti_match = [], [], []
nblocks_subj = 0
for b in blocks:
    ps = [i for i in (b.get('paras') or []) if not d.items[i].get('tbl') and bi._para_style_id(S, d.paras[i]) in src_ids and dl.para_text(d.paras[i]).strip()]
    fonts = {i: eff_font(d.paras[i]) for i in ps}
    has_opts = any(re.match(r'^[A-D][．.]', dl.para_text(d.paras[i]).strip()) for i in ps)
    if has_opts: continue  # choice question
    if not any(f == 'Kaiti SC' for f in fonts.values()): continue
    nblocks_subj += 1
    for i in ps:
        t = dl.para_text(d.paras[i]).strip()
        shape = bi._para_shape(t)
        if fonts[i] == 'Songti SC':
            (subj_stem_match if shape == 'stem' else subj_stem_nomatch).append((i, shape, t[:50]))
        elif fonts[i] == 'Kaiti SC' and shape == 'stem':
            kaiti_match.append((i, t[:50]))
print('subjective blocks (have Kaiti material, no A-D options):', nblocks_subj)
print('Songti paragraphs in subjective blocks: shape==stem', len(subj_stem_match), ' shape!=stem', len(subj_stem_nomatch))
from collections import Counter
print(Counter(s for _, s, _ in subj_stem_nomatch))
for x in subj_stem_nomatch[:60]: print('  NOMATCH', x)
print('Kaiti (material-font) paragraphs in subjective blocks that regex classifies as stem:', len(kaiti_match))
for x in kaiti_match[:20]: print('  KAITI-STEM', x)
print('==== all plain-shape Songti in subjective blocks ====')
for x in subj_stem_nomatch:
    if x[1] == 'plain': print('  ', x[0], x[2])
