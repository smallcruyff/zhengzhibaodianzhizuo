#!/usr/bin/env python3
"""写书侧通用工具（apply_patch、layout_prepare、drill_tool 等）共用的 DOCX 底层。

读：open_docx() 返回 Doc，其中 d.items 是 batch_health.read_docx 的段落流（样式名、文字、颜色 run、keepNext……），
    d.paras 是与之一一对应的 w:p 元素（同一遍历顺序：正文、表格单元格递归、sdt/customXml/smartTag 展开、
    mc:AlternateContent 只取 Choice）。打开时逐段比对文字，对不上就抛 AlignmentError，不猜。
    这样“认题块/认栏目/认单练”的判定与每批体检完全同源，写工具只负责按判定结果改 XML。
写：write_docx() 只替换 word/document.xml（可选再替换显式点名的成员），其余 ZIP 成员按原顺序、原压缩方式逐字节
    照抄；写到同目录临时文件再原子替换，写后重开核对。输出路径先过 guard_write()。
守卫：guard_write() 与 batch_health 的输出守卫同一口径——冻结册目录一律拒写；受保护根（项目根、~/GaokaoPolitics、
    Skill 目录、桌面等）内只允许 …/协作/候选/<谁>/<批次>/构建/ 之下；系统临时目录放行；不得等于任何输入；
    默认不覆盖已存在文件。拒绝时抛 GuardError（调用方以退出码 3 结束）。

  import docx_lib as dl
  d = dl.open_docx(path, expect_sha256=parent_sha)   # 父稿 SHA 不符抛 ParentMismatch
  p = d.paras[i]; ... 改 XML ...
  out = dl.guard_write(out_path, prof, inputs=[path], kind='.docx')
  receipt = dl.write_docx(d, out)                      # {'out','sha256','bytes','changed_members'}
"""
import hashlib
import os
import re
import sys
import tempfile
import zipfile
from pathlib import Path

from lxml import etree

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import batch_health as bh  # noqa: E402
from profile_lib import list_profiles, load_profile, resolve  # noqa: E402

W = bh.W
MC = bh.MC
DOC_XML = 'word/document.xml'
WRITE_ALLOW_RX = r'/协作/候选/[^/]+/[^/]+/构建(/|$)'


class AlignmentError(Exception):
    pass


class ParentMismatch(Exception):
    pass


class GuardError(Exception):
    pass


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- 段落元素（与 batch_health.read_docx 同序）
def para_elements(body):
    out = []

    def block(el, depth=0):
        tag = el.tag
        if tag == W + 'p':
            out.append(el)
        elif tag == W + 'tbl':
            for tr in el.findall(W + 'tr'):
                for tc in tr.findall(W + 'tc'):
                    for ch in tc:
                        block(ch, depth + 1)
        elif tag in (W + 'sdt', W + 'sdtContent', W + 'customXml', W + 'smartTag'):
            for ch in el:
                block(ch, depth)
        elif tag == MC + 'AlternateContent':
            ch = el.find(MC + 'Choice')
            for x in (ch if ch is not None else []):
                block(x, depth)

    for el in body:
        block(el)
    return out


def para_text(p):
    """与 batch_health.read_docx 相同的取字口径（w:t、w:tab、w:sym；跳过 mc:Fallback；去零宽字符；两端去空白）。"""
    skip = set()
    for fb in p.iter(MC + 'Fallback'):
        skip.update(fb.iter())
    parts = []
    for r in p.iter(W + 'r'):
        if skip and r in skip:
            continue
        for ch in r:
            if ch.tag == W + 't':
                parts.append(ch.text or '')
            elif ch.tag == W + 'tab':
                parts.append('\t')
            elif ch.tag == W + 'sym':
                parts.append(bh._sym_char(ch))
    return ''.join(parts).translate(bh.ZW).strip()


def para_sha(p):
    """段落 XML 指纹（C14N），用来证明“没点名的段落没动”。"""
    return sha256_bytes(etree.tostring(p, method='c14n'))


class Doc:
    def __init__(self, path):
        self.path = Path(path).expanduser().resolve()
        self.sha256 = sha256_file(self.path)
        with zipfile.ZipFile(self.path) as z:
            self.infos = z.infolist()
            if DOC_XML not in {i.filename for i in self.infos}:
                raise ValueError('不是 Word 正文包：缺 word/document.xml')
            self.doc_xml_orig = z.read(DOC_XML)
        self.root = etree.fromstring(self.doc_xml_orig)
        self.body = self.root.find(W + 'body')
        if self.body is None:
            raise ValueError('document.xml 没有 w:body')
        self.items, self.tables = bh.read_docx(str(self.path))
        self.paras = para_elements(self.body)
        self.check_alignment()
        self.replaced = {}   # 额外替换的 ZIP 成员 {name: bytes}

    def check_alignment(self, items=None):
        items = self.items if items is None else items
        if len(items) != len(self.paras):
            raise AlignmentError(f'段落数对不上：read_docx {len(items)}，元素 {len(self.paras)}')
        for i, (it, p) in enumerate(zip(items, self.paras)):
            t = para_text(p)
            if t != it['text']:
                raise AlignmentError(f'第 {i} 段文字对不上：read_docx={it["text"][:40]!r} 元素={t[:40]!r}')

    def refresh(self):
        """改过 XML 后重建 paras（items 仍是原稿的，只用于定位原稿）。"""
        self.paras = para_elements(self.body)
        return self.paras

    def document_xml(self):
        return etree.tostring(self.root, xml_declaration=True, encoding='UTF-8', standalone=True)


def open_docx(path, expect_sha256=None):
    d = Doc(path)
    if expect_sha256 and d.sha256 != expect_sha256.lower():
        raise ParentMismatch(f'父稿 SHA 不符：期望 {expect_sha256[:16]}…，实际 {d.sha256[:16]}…（{d.path.name}）')
    return d


# ---------------------------------------------------------------- 写出
def write_docx(d, out, extra_members=None):
    """只替换 document.xml（及 extra_members 点名的成员），其余成员逐字节照抄；原子写出并复核。"""
    out = Path(out)
    new_doc = d.document_xml()
    repl = {DOC_XML: new_doc}
    repl.update(d.replaced)
    repl.update(extra_members or {})
    fd, tmp = tempfile.mkstemp(prefix='.docx_lib_', suffix='.docx', dir=str(out.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(d.path) as zin, zipfile.ZipFile(tmp, 'w') as zout:
            for info in zin.infolist():
                data = repl.get(info.filename)
                if data is None:
                    data = zin.read(info.filename)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.create_system = info.create_system
                zout.writestr(zi, data)
            missing = set(repl) - {i.filename for i in zin.infolist()}
            if missing:
                raise ValueError(f'要替换的成员在原包里不存在：{sorted(missing)}')
        changed = []
        with zipfile.ZipFile(d.path) as zin, zipfile.ZipFile(tmp) as zchk:
            if [i.filename for i in zin.infolist()] != [i.filename for i in zchk.infolist()]:
                raise ValueError('写后成员顺序与原包不同')
            for info in zin.infolist():
                a, b = zin.read(info.filename), zchk.read(info.filename)
                if a != b:
                    if info.filename not in repl:
                        raise ValueError(f'未点名的成员被改动：{info.filename}')
                    changed.append(info.filename)
            etree.fromstring(zchk.read(DOC_XML))
        os.replace(tmp, out)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return {'out': str(out.resolve()), 'sha256': sha256_file(out), 'bytes': out.stat().st_size,
            'changed_members': changed}


def unchanged_paragraphs(before_paras, after_paras, touched_before, touched_after):
    """核对“没点名的段落没动”：去掉两侧点名的下标后，剩余段落按顺序 C14N 相同。返回不一致的前 20 处。"""
    a = [para_sha(p) for i, p in enumerate(before_paras) if i not in touched_before]
    b = [para_sha(p) for i, p in enumerate(after_paras) if i not in touched_after]
    bad = []
    if len(a) != len(b):
        bad.append({'kind': 'count', 'before': len(a), 'after': len(b)})
    for k, (x, y) in enumerate(zip(a, b)):
        if x != y:
            bad.append({'kind': 'xml', 'ordinal': k})
            if len(bad) >= 20:
                break
    return bad


# ---------------------------------------------------------------- 输出守卫
_cf, _within, _temp_roots = bh._cf, bh._within, bh._temp_roots


def _frozen_hits(o):
    hits = []
    for name in list_profiles():
        try:
            pr = load_profile(name)
        except Exception:
            continue
        paths = pr.get('paths', {}) or {}
        if not pr.get('frozen') or not paths.get('root'):
            continue
        root = Path(paths['root']).expanduser().resolve()
        dirs = [resolve(pr, paths[k]).resolve() for k in ('workspace', 'aux_workspace', 'review_entry', 'review_history')
                if paths.get(k)]
        hit = any(_within(o, x) for x in dirs)
        ck = pr.get('collab_key')
        if not hit and ck and _within(o, root) and _cf(o) != _cf(root):
            rel = Path(_cf(o)[len(_cf(root).rstrip('/')) + 1:])
            hit = bool(rel.parts) and _cf(ck) in rel.parts[0]
        if hit:
            hits.append(pr)
    return hits


def guard_write(out, prof, inputs=(), kind='.docx', overwrite=False, allowed_regex=WRITE_ALLOW_RX):
    """写工具的输出守卫；安全时返回解析后的 Path，否则抛 GuardError。冻结册本身（prof.frozen）也拒绝。"""
    o = Path(out).expanduser().resolve()
    kinds = (kind,) if isinstance(kind, str) else tuple(kind)
    if o.suffix.lower() not in kinds:
        raise GuardError(f'输出必须是 {"/".join(kinds)} 文件：{o.name}')
    if prof and prof.get('frozen'):
        raise GuardError(f'{prof.get("title", prof.get("book_id"))} 已冻结，拒绝写出：{prof.get("frozen_note", "")}')
    for p in inputs or ():
        if not p:
            continue
        q = Path(p).expanduser().resolve()
        if _cf(q) == _cf(o) or (o.exists() and q.exists() and os.path.samefile(q, o)):
            raise GuardError(f'输出与输入是同一个文件（{q.name}）')
    if o.exists() and not overwrite:
        raise GuardError(f'目标已存在，不覆盖：{o}')
    if not o.parent.is_dir():
        raise GuardError(f'输出目录不存在：{o.parent}')
    fz = _frozen_hits(o)
    if fz:
        raise GuardError(f'落在冻结册目录（{fz[0].get("title")}），拒绝写出')
    if any(_within(o, t) for t in _temp_roots()):
        return o
    roots = []
    for name in list_profiles():
        try:
            r = load_profile(name).get('paths', {}).get('root')
        except Exception:
            r = None
        if r:
            roots.append(Path(r).expanduser().resolve())
    for r in bh.cfg(prof, 'output_guard.protected_roots', []) if prof else []:
        roots.append(Path(r).expanduser().resolve())
    roots.append(Path(__file__).resolve().parent.parent)
    allow = re.compile(allowed_regex)
    for r in roots:
        if _within(o, r):
            rel = '/' + _cf(o)[len(_cf(r).rstrip('/')) + 1:]
            if not allow.search(str(Path(rel).parent) + '/'):
                raise GuardError(f'落在受保护目录 {r} 内（只允许 …/协作/候选/<谁>/<批次>/构建/ 之下或系统临时目录）')
    return o
