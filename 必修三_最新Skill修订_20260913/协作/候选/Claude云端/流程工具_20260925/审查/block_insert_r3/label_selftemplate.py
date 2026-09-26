"""材料内【X】正文段（source 区、非【题目】开场行）：用该块自己作样板、按默认路径（ci>0，排除开场段）
模拟 block_insert 造段，比较正文部分有效字体与原段是否一致。"""
from common import *
sys.path.insert(0, str(C))
import run_tests_block_insert as rt
import zipfile
from lxml import etree
from collections import Counter
b = dl.open_docx(BOOK); prof = bi.load_profile(str(PROF))
with zipfile.ZipFile(BOOK) as z: st = etree.fromstring(z.read('word/styles.xml'))
S = bh.Styles(st)
zone, p2b, blocks, _ = ap.zones_of(b, prof)
def body_font(p):
    spans = [(r, tx) for r, tx in ap._run_spans(p) if tx.strip()]
    r, tx = max(spans, key=lambda s: len(s[1]))
    return rt._effective_font_sz(p, r.find(W+'rPr'))[0]
c = Counter(); bad = []
src_ids = bi._style_ids_for_bucket(prof, S, 'source')
for i, p in enumerate(b.paras):
    t = dl.para_text(p).strip()
    if b.items[i].get('tbl') or zone[i] != 'source' or i not in p2b: continue
    if bi._para_style_id(S, p) not in src_ids: continue
    if bi._para_shape(t) != 'label_prefix' or t.startswith('【题目】'): continue
    blk = p2b[i]
    fb = []
    tp, _ = bi.find_role_template(b, S, prof, blk, 'source', None, None, t, fb, exclude_idx=min(blk['paras']))
    newp = bi.build_text_paragraph({'text': t}, tp, S)
    of, nf = body_font(p), body_font(newp)
    tshape = bi._para_shape(dl.para_text(tp))
    c[(of, nf, 'tpl=' + tshape)] += 1
    if of != nf: bad.append((i, of, nf, tshape, t[:30]))
print(c)
for x in bad[:15]: print('  ', x)
