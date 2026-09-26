from common import *
import zipfile
from lxml import etree
d = dl.open_docx(BOOK)
prof = bi.load_profile(str(PROF))
with zipfile.ZipFile(BOOK) as z:
    st = etree.fromstring(z.read('word/styles.xml'))
S = bh.Styles(st)
src_ids = bi._style_ids_for_bucket(prof, S, 'source')
print('source bucket', prof['styles']['source'], src_ids)
def first_font(p):
    for r, t in ap._run_spans(p):
        if not t.strip(): continue
        rpr = r.find(W+'rPr')
        rf = rpr.find(W+'rFonts') if rpr is not None else None
        return rf.get(W+'eastAsia') if rf is not None else None
    return 'EMPTY'
_, _, blocks, _ = ap.zones_of(d, prof)
inblock = set()
for b in blocks:
    inblock.update(b.get('paras') or [])
songti_nonstem, kaiti_stem = [], []
cnt = {'songti_total':0,'songti_stem':0,'none_total':0,'none_stem':0}
for i, p in enumerate(d.paras):
    if d.items[i].get('tbl') or i not in inblock: continue
    if bi._para_style_id(S, p) not in src_ids: continue
    t = dl.para_text(p).strip()
    if not t: continue
    f = first_font(p)
    shape = bi._para_shape(t)
    if f == 'Songti SC':
        cnt['songti_total'] += 1
        if shape == 'stem': cnt['songti_stem'] += 1
        elif shape == 'plain': songti_nonstem.append((i, t[:40]))
    elif f is None:
        cnt['none_total'] += 1
        if shape == 'stem':
            cnt['none_stem'] += 1; kaiti_stem.append((i, t[:40]))
print(cnt)
print('Songti SC (stem-format) paragraphs whose shape is plain (tool would NOT treat as stem):', len(songti_nonstem))
for x in songti_nonstem[:40]: print('  ', x)
print('Default-font (material-format) paragraphs whose shape is stem (tool would give Songti):', len(kaiti_stem))
for x in kaiti_stem[:25]: print('  ', x)
