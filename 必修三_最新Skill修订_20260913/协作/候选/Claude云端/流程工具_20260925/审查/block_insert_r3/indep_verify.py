"""独立复核测试产物：r: 引用都有关系、目标成员都在包里、Content_Types 覆盖、docPr/cNvPr id 唯一、书签配对、
除 document.xml/rels/CT 外其余成员逐字节不变、未点名段落不变（只一处连续插入）。"""
from common import *
import zipfile, difflib
from lxml import etree
T = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/block_insert')
R_NS = bi.R_NS
outs = sorted(p for p in T.glob('*_out.docx'))
with zipfile.ZipFile(BOOK) as z0:
    base_members = {n: z0.read(n) for n in z0.namelist()}
d0 = dl.open_docx(BOOK)
base_sha = [dl.para_sha(p) for p in d0.paras]
for out in outs:
    parent = None
    for cand in (out.with_name(out.name.replace('_out.docx', '_parent.docx')),):
        if cand.exists(): parent = cand
    with zipfile.ZipFile(out) as z:
        names = set(z.namelist())
        root = etree.fromstring(z.read('word/document.xml'))
        rels = {r.get('Id'): (r.get('Target'), r.get('TargetMode'), r.get('Type')) for r in etree.fromstring(z.read('word/_rels/document.xml.rels'))}
        ct = etree.fromstring(z.read('[Content_Types].xml'))
        probs = []
        for el in root.iter():
            for k, v in el.attrib.items():
                if k.startswith(R_NS) and v:
                    if v not in rels: probs.append(f'missing rel {v}')
                    else:
                        tgt, mode, typ = rels[v]
                        if mode != 'External':
                            p = tgt.lstrip('/') if tgt.startswith('/') else 'word/' + tgt
                            if p not in names: probs.append(f'missing target {p}')
                        if etree.QName(el).localname == 'blip' and not typ.endswith('/image'): probs.append(f'blip->{typ}')
                        if etree.QName(el).localname == 'hyperlink' and not typ.endswith('/hyperlink'): probs.append(f'hyperlink->{typ}')
        exts = {Path(n).suffix.lstrip('.').lower() for n in names if n.startswith('word/media/')}
        defs = {c.get('Extension','').lower() for c in ct if c.tag.endswith('Default')}
        ovr = {c.get('PartName') for c in ct if c.tag.endswith('Override')}
        unc = [e for e in exts if e not in defs and not any((o or '').endswith('.'+e) for o in ovr)]
        if unc: probs.append(f'CT uncovered {unc}')
        dp = [e.get('id') for e in root.iter(bi.WP_NS+'docPr')]
        dups = {x for x in dp if dp.count(x) > 1}
        bs = [b.get(W+'id') for b in root.iter(W+'bookmarkStart')]; be = [b.get(W+'id') for b in root.iter(W+'bookmarkEnd')]
        if sorted(bs) != sorted(be): probs.append('bookmark unpaired')
        if len(bs) != len(set(bs)): probs.append('bookmark id dup')
        changed_members = sorted(n for n in base_members if n in names and z.read(n) != base_members[n])
        added = sorted(names - set(base_members))
    # paragraph-level: only contiguous insert(s)
    if parent is not None and dl.sha256_file(parent) == BOOK_SHA:
        d1 = dl.open_docx(out)
        sm = difflib.SequenceMatcher(a=base_sha, b=[dl.para_sha(p) for p in d1.paras], autojunk=False)
        ops = [(o[0], o[2]-o[1], o[4]-o[3]) for o in sm.get_opcodes() if o[0] != 'equal']
    else:
        ops = 'parent differs from book (gold/other)'
    print(out.name[:48], 'PROBLEMS=' + (';'.join(sorted(set(probs))) or 'none'), '| dup_docPr(existing?)=', sorted(dups)[:5], '| changed=', changed_members, '| added=', added[:3], '| para_ops=', ops)
