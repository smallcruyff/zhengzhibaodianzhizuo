"""R4 独立核对测试输出：rel 完整、docPr/cNvPr 唯一、w14:paraId 是否重复（相对父稿新增的重复）、书签配对、
Content_Types 覆盖、除 document/rels/CT 外成员逐字节一致、段落序列相对父稿只有一处连续插入。"""
from common import *
import collections
W14 = '{http://schemas.microsoft.com/office/word/2010/wordml}'
WP = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
PIC = '{http://schemas.openxmlformats.org/drawingml/2006/picture}'
RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
def check(parent, out):
    res = {}
    zp, zo = zipfile.ZipFile(parent), zipfile.ZipFile(out)
    rp = etree.fromstring(zp.read('word/document.xml')); ro = etree.fromstring(zo.read('word/document.xml'))
    def dup(vals):
        c = collections.Counter(v for v in vals if v)
        return {k for k, n in c.items() if n > 1}
    pid_p = dup(p.get(W14 + 'paraId') for p in rp.iter(W + 'p'))
    pid_o = dup(p.get(W14 + 'paraId') for p in ro.iter(W + 'p'))
    res['paraId_dup_new'] = sorted(pid_o - pid_p)[:10]
    dp_p = dup(x.get('id') for x in rp.iter(WP + 'docPr')); dp_o = dup(x.get('id') for x in ro.iter(WP + 'docPr'))
    res['docPr_dup_new'] = sorted(dp_o - dp_p)
    rels = {r.get('Id'): (r.get('Target'), r.get('TargetMode'), r.get('Type').rsplit('/', 1)[-1]) for r in etree.fromstring(zo.read('word/_rels/document.xml.rels'))}
    names = set(zo.namelist())
    bad = []
    for el in ro.iter():
        for k, v in el.attrib.items():
            if k.startswith(RNS):
                if v not in rels: bad.append(('norel', v))
                else:
                    t, mode, typ = rels[v]
                    if mode != 'External' and ('word/' + t.lstrip('/')) not in names and t.lstrip('/') not in names: bad.append(('notarget', v, t))
                    if el.tag.endswith('}blip') and typ != 'image': bad.append(('blip->' + typ, v))
    res['rel_problems'] = bad[:10]
    bs = [b.get(W + 'id') for b in ro.iter(W + 'bookmarkStart')]; be = [b.get(W + 'id') for b in ro.iter(W + 'bookmarkEnd')]
    res['bookmark_pair'] = sorted(bs) == sorted(be) and len(set(bs)) == len(bs)
    ct = etree.fromstring(zo.read('[Content_Types].xml'))
    exts = {c.get('Extension').lower() for c in ct if c.get('Extension')}
    res['ct_uncovered'] = sorted({Path(n).suffix.lstrip('.').lower() for n in names if n.startswith('word/media/')} - exts)
    changed = [n for n in zp.namelist() if n in names and zp.read(n) != zo.read(n)]
    res['changed_members'] = changed
    pp = [dl.para_sha(p) for p in dl.para_elements(rp.find(W + 'body'))]
    po = [dl.para_sha(p) for p in dl.para_elements(ro.find(W + 'body'))]
    i = 0
    while i < min(len(pp), len(po)) and pp[i] == po[i]: i += 1
    j = 0
    while j < min(len(pp), len(po)) - i and pp[-1 - j] == po[-1 - j]: j += 1
    res['single_contiguous_insert'] = (i + j == len(pp))
    res['n_new_paras'] = len(po) - len(pp)
    return res
if __name__ == '__main__':
    base = Path(sys.argv[1])
    pairs = [(base / a, base / b) for a, b in (x.split(':') for x in sys.argv[2:])]
    for p, o in pairs:
        print(o.name, json.dumps(check(p, o), ensure_ascii=False))
