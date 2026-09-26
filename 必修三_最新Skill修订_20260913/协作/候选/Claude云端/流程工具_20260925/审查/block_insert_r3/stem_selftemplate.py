"""对全书每个主观题块里的每个宋体设问段，用"该块自己"作样板（最有利情形），按默认路径（不给 like/style）
模拟 block_insert 为同一段文字选模板、造段落，比较新段有效字体与原段有效字体。"""
from common import *
import zipfile, re
from lxml import etree
from collections import Counter
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
_, _, blocks, _ = ap.zones_of(d, prof)
res = Counter(); bad = []
for b in blocks:
    ps = [i for i in (b.get('paras') or []) if not d.items[i].get('tbl') and bi._para_style_id(S, d.paras[i]) in src_ids and dl.para_text(d.paras[i]).strip()]
    fonts = {i: eff_font(d.paras[i]) for i in ps}
    if any(re.match(r'^[A-D][．.]', dl.para_text(d.paras[i]).strip()) for i in ps): continue
    if not any(f == 'Kaiti SC' for f in fonts.values()): continue
    tb = b.get('paras') or []
    opening = min(tb) if tb else None
    for i in ps:
        if fonts[i] != 'Songti SC': continue
        t = dl.para_text(d.paras[i]).strip()
        shape = bi._para_shape(t)
        if shape.startswith('label'): continue
        fb = []
        tp, sid = bi.find_role_template(d, S, prof, b, 'source', None, None, t, fb, exclude_idx=opening)
        newp = bi.build_text_paragraph({'role':'source','text':t}, tp, S)
        nf = eff_font(newp)
        key = (shape, 'ok' if nf == 'Songti SC' else 'FLIP->' + str(nf))
        res[key] += 1
        if nf != 'Songti SC': bad.append((i, b['title'][:30], t[:40]))
print(res)
print('flipped examples:')
for x in bad[:30]: print('  ', x)
