from common import *
import zipfile, glob
from lxml import etree
from collections import Counter
files = [Path(p) for p in glob.glob(str(R/'00_共同资料/原材料/**/*.docx'), recursive=True)]
print('docx files', len(files))
c = Counter(); ex = {}
WPS = '{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}wsp'
for f in files:
    try:
        with zipfile.ZipFile(f) as z: root = etree.fromstring(z.read('word/document.xml'))
    except Exception as e:
        c['open_fail'] += 1; continue
    body = root.find(W+'body')
    for ti, t in enumerate(bi._top_tables(body), 1):
        c['tables'] += 1
        feats = []
        if t.find(f'.//{W}tbl') is not None: feats.append('nested_tbl')
        if any(tc.find(W+'sdt') is not None for tc in t.iter(W+'tc')): feats.append('sdt_in_cell')
        if t.find(f'{W}tblPr/{W}tblpPr') is not None: feats.append('floating_tblpPr')
        drs = [dr for dr in t.iter() if dr.tag in (bi.WP_NS+'inline', bi.WP_NS+'anchor')]
        noblip = [dr for dr in drs if dr.find(f'.//{bi.A_NS}blip') is None]
        if noblip: feats.append('drawing_without_blip')
        if t.find(f'.//{W}pict') is not None: feats.append('vml_pict')
        if t.find(f'.//{W}object') is not None: feats.append('ole_object')
        if t.find(f'.//{W}fldChar') is not None or t.find(f'.//{W}fldSimple') is not None: feats.append('field')
        if t.find(f'.//{W}footnoteReference') is not None: feats.append('footnote')
        if t.find(f'.//{{http://schemas.openxmlformats.org/officeDocument/2006/math}}oMath') is not None: feats.append('omath')
        if t.find(f'.//{W}numPr') is not None: feats.append('numPr')
        for ft in feats:
            c[ft] += 1
            ex.setdefault(ft, []).append(f'{f.relative_to(R/"00_共同资料/原材料")}#t{ti}')
print(dict(c))
for k, v in ex.items(): print(k, v[:4])
