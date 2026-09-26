"""原材料 DOCX 表格里带"有语义的"run 格式（下划线空格填空、上下标、着重号、删除线）的情况——
_reformat_table_cells 会把每个 run 的 rPr 整体换成样板行格式，这些格式随之丢失。"""
from common import *
import glob
from collections import Counter
files = sorted(Path(p) for p in glob.glob(str(R/'00_共同资料/原材料/**/*.docx'), recursive=True))
c = Counter(); ex = {}
for f in files:
    try: src = bi._SourceDocx(f)
    except Exception: continue
    for ti, t in enumerate(bi._top_tables(src.body), 1):
        tag = f'{f.relative_to(R/"00_共同资料/原材料")}#t{ti}'
        feats = set()
        for r in t.iter(W+'r'):
            rpr = r.find(W+'rPr')
            if rpr is None: continue
            txt = ''.join(x.text or '' for x in r.iter(W+'t'))
            u = rpr.find(W+'u')
            if u is not None and u.get(W+'val') not in ('none', None) :
                if txt and not txt.strip(): feats.add('underlined_blank_spaces')
                elif txt: feats.add('underline_text')
            va = rpr.find(W+'vertAlign')
            if va is not None and va.get(W+'val') in ('superscript','subscript') and txt: feats.add('sup/sub')
            if rpr.find(W+'em') is not None and rpr.find(W+'em').get(W+'val') not in ('none',None) and txt: feats.add('emphasis_dot')
            if rpr.find(W+'strike') is not None and txt: feats.add('strike')
            b = rpr.find(W+'b')
            if b is not None and b.get(W+'val') not in ('0','false') and txt.strip(): feats.add('bold_run')
        for ft in feats:
            c[ft] += 1; ex.setdefault(ft, []).append(tag)
    src.z.close()
print(dict(c))
for k, v in ex.items(): print(k, v[:6])
