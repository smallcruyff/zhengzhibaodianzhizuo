"""R4：多少主观题块“块内（非表格）source 段没有 plain 形状”——拿它们当样板时，材料段会在块内退化成
stem 段格式（宋体/题目设问），且不记 fallbacks。"""
from common import *
prof = bi.load_profile(str(PROF)); d = dl.open_docx(BOOK); S = style_ctx()[4]
_, _, blocks, _ = ap.zones_of(d, prof)
sp = bi._stem_position_index(d, S, prof, blocks)
src = bi._style_ids_for_bucket(prof, S, 'source')
OPT = re.compile(r'^[A-D][.．]')
n_subj = 0; noplain = []
for b in blocks:
    ps = [i for i in (b.get('paras') or []) if not d.items[i].get('tbl') and bi._para_style_id(S, d.paras[i]) in src and dl.para_text(d.paras[i]).strip()]
    if not ps or any(OPT.match(dl.para_text(d.paras[i]).strip()) for i in ps):
        continue
    n_subj += 1
    shapes = [bi._para_shape_ctx(dl.para_text(d.paras[i]), i in sp) for i in ps]
    if 'plain' not in shapes:
        stem_i = [i for i, s in zip(ps, shapes) if s == 'stem']
        noplain.append((b['title'][:30], shapes, [eff_font(d.paras[i]) for i in stem_i]))
print('主观题块', n_subj, '块内无 plain 形状 source 段的', len(noplain))
for x in noplain[:15]: print(' ', x)
