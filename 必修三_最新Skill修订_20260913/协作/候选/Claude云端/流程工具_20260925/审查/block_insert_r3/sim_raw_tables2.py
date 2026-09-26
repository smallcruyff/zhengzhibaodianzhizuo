"""同 sim_raw_tables.py，但只看"没被 _reformat_table_cells 覆盖到的"源引用：嵌套表格内的 pStyle/rStyle/
tblStyle/numPr，以及 tc 下 w:sdt 包着的段落。按 (type,name) 判断它们在本书里被改绑成了什么。"""
from common import *
import zipfile, glob
from lxml import etree
from collections import Counter
d = dl.open_docx(BOOK)
prof = bi.load_profile(str(PROF))
with zipfile.ZipFile(BOOK) as z:
    st_root = etree.fromstring(z.read('word/styles.xml'))
    num_xml = z.read('word/numbering.xml') if 'word/numbering.xml' in z.namelist() else None
book_map = bi._style_type_name_map(st_root)
name_to_id = bi._name_to_id_index(book_map)
book_nums = set()
if num_xml is not None:
    nroot = etree.fromstring(num_xml)
    book_nums = {n.get(W+'numId') for n in nroot.iter(W+'num')}
_,_,blocks,_ = ap.zones_of(d, prof)
tb = [b for b in blocks if '例题 3　2024朝阳二模第18题' in b['title']][0]
tpl = bi.find_table_template(d, tb, d.body, [])
files = sorted(Path(p) for p in glob.glob(str(R/'00_共同资料/原材料/**/*.docx'), recursive=True))
c = Counter(); ex = {}
def add(k, v):
    c[k] += 1; ex.setdefault(k, []).append(v)
for f in files:
    try: src = bi._SourceDocx(f)
    except Exception: continue
    src_map = src.style_type_name()
    for ti, t in enumerate(bi._top_tables(src.body), 1):
        tag = f'{f.relative_to(R/"00_共同资料/原材料")}#t{ti}'
        try:
            out = bi.build_table_from_source(t, tpl, name_to_id, src, bi.MediaCtx(d), bi.IdAllocator(d.root), [])
        except bi.Abort:
            continue
        for nested in out.iter(W+'tbl'):
            if nested is out: continue
            for el in nested.iter(W+'pStyle', W+'rStyle', W+'tblStyle'):
                sid = el.get(W+'val'); s_info = src_map.get(sid); b_info = book_map.get(sid)
                if b_info is None: add('nested_dangling', f'{tag} {etree.QName(el).localname}={sid} src={s_info}')
                elif s_info != b_info: add('NESTED_COLLIDE', f'{tag} {etree.QName(el).localname}={sid} src={s_info} -> book={b_info}')
                else: add('nested_same', tag)
            for n in nested.iter(W+'numId'):
                add('nested_numId_left', f'{tag} numId={n.get(W+"val")} in_book_numbering={n.get(W+"val") in book_nums}')
        for tc in out.iter(W+'tc'):
            for sdt in tc.findall(W+'sdt'):
                add('sdt_in_cell_left', tag)
        tp = out.find(f'{W}tblPr/{W}tblpPr')
        if tp is not None:
            add('floating_left', f'{tag} tblpPr={dict((etree.QName(k).localname, v) for k, v in tp.attrib.items())}')
    src.z.close()
print(dict(c))
for k, v in ex.items():
    print('==', k, len(v))
    for x in sorted(set(v))[:12]: print('   ', x)
