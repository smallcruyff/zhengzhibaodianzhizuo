#!/usr/bin/env python3
"""每批体检（按书册配置运行的通用版）：只读 DOCX，可加同版 PDF、上一批基线，输出确定性检查结果。

用途
  把每批都要做的机械核对（栏目、编号、考法题数、学生正文工程词、单练 A1/A2、目录、页脚、PDF 字体回退、
  PDF 与 DOCX 同版、题面零改写、教学正文误蓝、答案不标分、选择题答案与逐肢判定、回退棘轮、例题块差异）
  交给脚本，模型只看脚本列出的 CANDIDATE 与 FAIL 明细做教学判断。书册差异全部来自 profiles/<book>.json
  （共享默认值在 profiles/_house.json），字段说明见 profiles/schema.md（其中写明本工具实际读取哪些字段）。

用法
  python3 batch_health.py --docx 本批.docx [--pdf 本批.pdf] [--baseline 上批.docx] [--baseline-pdf 上批.pdf]
                          [--profile bixiu3|配置路径] [--identity 同版身份.json] [--source-restore-list 清单]
                          [--out 体检.json] [--max-items 60] [--quiet]
  不给 --profile 时按 DOCX 路径自动判断书册（profile_lib.detect_profile），判断不出就报错退出。
  作为库使用： from batch_health import run_health; rep = run_health(docx, pdf=..., baseline=..., profile='bixiu3')

只读承诺
  DOCX 只用 zipfile 读取，PDF 只用 fitz 打开；不改、不移动、不重存任何输入文件。
  唯一写出的是 --out 指定的 JSON（先写临时文件再原子替换）；不给 --out 时写到系统临时目录。
  输出路径守卫（_unsafe_out）：必须是 .json；不得等于任何输入；不覆盖已有的非体检报告文件；
  冻结册（profile.frozen）目录经 frozen_guard 拒绝；落在项目根、Skill 目录等受保护目录内时，只允许
  “…/协作/候选/<谁>/<批次>/构建/体检/”；目标目录里有 .docx/.pdf（书稿旁边）时拒绝；系统临时目录放行。
  路径比较在 macOS 上做大小写折叠。

分级
  FAIL       确定违规（按现行规则可机械判定）
  CANDIDATE  需主代理判断的候选清单（脚本不裁定）
  WARN       提示
  INFO       统计与差异，不作门槛
  门全过只说明机械层没有回退，不等于内容已审；全部明细都是机器提取，未经主代理核原页。
  明细里的文字一律是原文截取，截断处标“〔截断〕”，脚本不生成归纳或摘要；经过处理的截取另有字段说明。

退出码
  0 无 FAIL（可以有 CANDIDATE/WARN）；1 有 FAIL；2 输入、配置错误或运行中崩溃（不留下报告文件）；
  3 拒绝写出（输出路径不安全或冻结册）。
"""
import argparse
import difflib
import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile
import time
import zipfile
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

from lxml import etree

sys.dont_write_bytecode = True  # 只读工具：不在 Skill 目录留下 __pycache__
sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import load_profile, detect_profile, frozen_guard, resolve, list_profiles  # noqa: E402

TOOL_VERSION = '2.1.0'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
V_NS = '{urn:schemas-microsoft-com:vml}'
LEVELS = ('FAIL', 'CANDIDATE', 'WARN', 'INFO')
NOTICE = ('门全过只说明机械层没有回退，不等于内容已审。全部明细均为机器提取（evidence=machine_extracted），'
          '未经主代理核原页；CANDIDATE 须主代理逐条判断，脚本不裁定。')
CUT = '〔截断〕'
CJK = re.compile('[㐀-䶿一-鿿豈-﫿]')
# 词连接符、零宽字符、软连字符：比较与词表匹配前去掉（哲学稿有数千个 U+2060）
ZW_CHARS = '⁠​‌‍﻿­'
ZW = dict.fromkeys(map(ord, ZW_CHARS), None)
PAPER_RX = re.compile(r'(20\d{2}|\d{2})\s*[一-龥]{0,4}(一模|二模|期中|期末|高考|适应性)|第\d+(\(\d\))?题|第\d+（\d）题')

# 配置缺省值：profile 与 _house.json 都没写时才用（新书册需要的字段见 profiles/schema.md）
DEFAULTS = {
    'labels_rules': {'answer_labels': ['【答案落点】'], 'answer_score_level': 'WARN',
                     'answer_score_regex': r'[（(]\s*\d+(?:\.\d+)?\s*分\s*[)）]', 'forbid_line_level': 'FAIL'},
    'structure': {'block_end': [], 'teaching_leadin_regex': None, 'unmatched_title_style_ends_block': True,
                  'source_style_reenter': [], 'copy_check': None},
    'student_text': {'forbidden_word_groups': {}, 'warn_words': [], 'line_start_forbidden': [],
                     'engineering_tags': [], 'trailing_tag_levels': {'default': 'FAIL', 'parts': {}},
                     'collateral_patterns': [], 'source_suspect_words': [],
                     'four_rights': None, 'warn_patterns': {},
                     'forbidden_word_zones': ['teaching', 'rubric', 'outside', 'heading']},
    'colors': {'blue': ['1F4E79', '1F3864', '17365D', '0070C0', '2F5496', '002060', '0000FF'],
               'blue_exempt_prefix': ['▪', '◆'], 'blue_exempt_styles': []},
    'choice_check': {'reverse_regex': r'(不正确|错误|不符合|不能|不属于|不恰当|不准确|有误|不合理|不宜|不应当?)[^，。；]{0,8}(的是|的一项|的有|的选项)',
                     'verdict_regex': r'^([①-⑨]|[A-D](?=[．.、\s])).{0,200}?[（(](正确|错误|不选)[)）]',
                     'option_combo_regex': r'([A-D])[．.、]\s*([①-⑨]{2,5})', 'reverse_hint_regex': None,
                     'answer_regex': r'^\s*【答案】\s*([A-D]+)'},
    'pdf_fonts': {'expected_cjk_regex': r'^(STSongti|STKaiti)', 'fail_min_chars_page': 20},
    'pagination': {'keep_next_label_regex': None, 'keep_next_target_style': None, 'keep_next_title_required': True},
    'baseline': {'near_edit_ratio': 0.85},
    'same_version': {'title_found_min': 0.98},
    'drill': {'max_non_item_ratio': 0.3},
    'pixel': {'policy': 'same_page_full_pixels', 'report_body_only_equal': False},
    'output_guard': {'protected_roots': [], 'allowed_subpath_regex': r'/协作/候选/[^/]+/[^/]+/构建/体检(/|$)'},
}


# ---------------------------------------------------------------- 通用小工具
def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def norm(t):
    return re.sub(r'\s+', '', (t or '').translate(ZW))


def clip(t, n=80):
    t = t or ''
    return t if len(t) <= n else t[:n] + '…' + CUT


def window(t, a, b, r=24):
    s, e = max(0, a - r), min(len(t), b + r)
    out = t[s:e]
    return (CUT + '…' if s > 0 else '') + out + ('…' + CUT if e < len(t) else '')


def cfg(prof, dotted, default=None):
    """按“a.b.c”取配置；profile/_house 没有时取 DEFAULTS，再没有取 default。"""
    for src in (prof, DEFAULTS):
        cur, ok = src, True
        for k in dotted.split('.'):
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok:
            return cur
    return default


_FW = str.maketrans('０１２３４５６７８９（）', '0123456789()')


def src_key(src):
    """题源归一成题键：去空白、全角数字括号转半角、去“年”、去末尾（N分/跨模块/…栏）括注，17(1)题→17题第(1)问。"""
    s = norm(src).translate(_FW)
    s = re.sub(r'^(20\d{2})年', r'\1', s)
    for _ in range(3):
        s2 = re.sub(r'\([^()]*(分|跨模块|栏|选学|补)[^()]*\)$', '', s)
        if s2 == s:
            break
        s = s2
    s = re.sub(r'第(\d+)\((\d+)\)题', r'第\1题第(\2)问', s)
    return s


# ---------------------------------------------------------------- DOCX 读取
def _on(el):
    if el is None:
        return None
    return (el.get(W + 'val') or 'true') not in ('0', 'false', 'off')


def _color(el):
    if el is None:
        return None
    v = el.get(W + 'val')
    return v.upper() if v else None


class Styles:
    def __init__(self, root):
        self.name, self.based, self.color, self.keepnext = {}, {}, {}, {}
        self.default_pstyle = None
        self.default_color, self.default_keepnext = 'AUTO', False
        if root is None:
            return
        for st in root.iter(W + 'style'):
            sid = st.get(W + 'styleId')
            n = st.find(W + 'name')
            self.name[sid] = n.get(W + 'val') if n is not None else sid
            b = st.find(W + 'basedOn')
            self.based[sid] = b.get(W + 'val') if b is not None else None
            self.color[sid] = _color(st.find(f'{W}rPr/{W}color'))
            self.keepnext[sid] = _on(st.find(f'{W}pPr/{W}keepNext'))
            if st.get(W + 'type') == 'paragraph' and st.get(W + 'default') in ('1', 'true'):
                self.default_pstyle = sid
        self.default_color = _color(root.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}color')) or 'AUTO'
        self.default_keepnext = bool(_on(root.find(f'{W}docDefaults/{W}pPrDefault/{W}pPr/{W}keepNext')))

    def chain(self, sid, table):
        seen = set()
        while sid and sid not in seen:
            seen.add(sid)
            v = table.get(sid)
            if v is not None:
                return v
            sid = self.based.get(sid)
        return None


def _sym_char(el):
    c = el.get(W + 'char')
    try:
        return chr(int(c, 16))
    except (TypeError, ValueError):
        return ''


def read_docx(path):
    """段落流（含表格内段落），每段带样式名、文字、有效颜色的 run、keepNext、超链接锚点、书签、域代码、图片哈希。
    文字抽取：w:t、w:tab、w:sym（按字符码）；跳过 mc:Fallback 里的重复内容；去掉词连接符等零宽字符。"""
    z = zipfile.ZipFile(path)
    names = set(z.namelist())
    if 'word/document.xml' not in names:
        raise ValueError('不是 Word 正文包：缺 word/document.xml')
    st = Styles(etree.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in names else None)
    body = etree.fromstring(z.read('word/document.xml')).find(W + 'body')
    if body is None:
        raise ValueError('document.xml 没有 w:body')
    rels = {}
    if 'word/_rels/document.xml.rels' in names:
        for r in etree.fromstring(z.read('word/_rels/document.xml.rels')):
            rels[r.get('Id')] = (r.get('Target') or '', r.get('TargetMode'))
    mcache = {}

    def mhash(rid):
        if rid not in mcache:
            tgt = rels.get(rid)
            if not tgt:
                h = 'norel:' + rid
            elif tgt[1] == 'External':
                h = 'external:' + tgt[0]
            else:
                p = tgt[0].lstrip('/') if tgt[0].startswith('/') else posixpath.normpath(posixpath.join('word', tgt[0]))
                h = hashlib.sha1(z.read(p)).hexdigest()[:12] if p in names else 'missing:' + p
            mcache[rid] = h
        return mcache[rid]

    items, pending_bm = [], []
    tcount = [0]
    zw = [0]

    def para(p, tbl=None, row=None, col=None, depth=0):
        ps = p.find(f'{W}pPr/{W}pStyle')
        sid = ps.get(W + 'val') if ps is not None else st.default_pstyle
        pcol = st.chain(sid, st.color)
        skip = set()
        for fb in p.iter(MC + 'Fallback'):
            skip.update(fb.iter())
        runs, parts = [], []
        for r in p.iter(W + 'r'):
            if skip and r in skip:
                continue
            buf = []
            for ch in r:
                tag = ch.tag
                if tag == W + 't':
                    buf.append(ch.text or '')
                elif tag == W + 'tab':
                    buf.append('\t')
                elif tag == W + 'sym':
                    buf.append(_sym_char(ch))
            t = ''.join(buf)
            if not t:
                continue
            t2 = t.translate(ZW)
            if t2 != t:
                zw[0] += len(t) - len(t2)
                t = t2
                if not t:
                    continue
            c = _color(r.find(f'{W}rPr/{W}color'))
            if not c:
                rs = r.find(f'{W}rPr/{W}rStyle')
                c = st.chain(rs.get(W + 'val'), st.color) if rs is not None else None
            c = c or pcol or st.default_color
            runs.append((t, c))
            parts.append(t)
        imgs = []
        for b in p.iter(A_NS + 'blip'):
            if not (skip and b in skip):
                rid = b.get(R_NS + 'embed') or b.get(R_NS + 'link')
                if rid:
                    imgs.append(mhash(rid))
        for v in p.iter(V_NS + 'imagedata'):
            if not (skip and v in skip):
                rid = v.get(R_NS + 'id')
                if rid:
                    imgs.append(mhash(rid))
        instr = ''.join(t.text or '' for t in p.iter(W + 'instrText'))
        instr += ' '.join(f.get(W + 'instr') or '' for f in p.iter(W + 'fldSimple'))
        anchors = [h.get(W + 'anchor') for h in p.iter(W + 'hyperlink') if h.get(W + 'anchor')]
        anchors += re.findall(r'HYPERLINK\s+\\l\s+"([^"]+)"', instr)
        kn = _on(p.find(f'{W}pPr/{W}keepNext'))
        if kn is None:
            kn = st.chain(sid, st.keepnext)
        bms = pending_bm[:] + [b.get(W + 'name') for b in p.iter(W + 'bookmarkStart')]
        del pending_bm[:]
        raw = ''.join(parts)
        items.append({'i': len(items), 'style': st.name.get(sid, sid) if sid else '(默认)', 'text': raw.strip(),
                      'runs': runs, 'instr': instr, 'anchors': anchors, 'bookmarks': bms,
                      'keepnext': bool(kn if kn is not None else st.default_keepnext),
                      'tbl': tbl, 'row': row, 'col': col, 'depth': depth,
                      'img': bool(imgs) or p.find(f'.//{W}drawing') is not None or p.find(f'.//{W}pict') is not None,
                      'imgs': imgs})

    def block(el, tbl=None, row=None, col=None, depth=0):
        tag = el.tag
        if tag == W + 'p':
            para(el, tbl, row, col, depth)
        elif tag == W + 'tbl':
            if depth == 0:
                tcount[0] += 1
                tno = tcount[0]
            else:
                tno = tbl
            for ri, tr in enumerate(el.findall(W + 'tr')):
                for ci, tc in enumerate(tr.findall(W + 'tc')):
                    for ch in tc:
                        block(ch, tno, ri if depth == 0 else row, ci if depth == 0 else col, depth + 1)
        elif tag == W + 'bookmarkStart':
            pending_bm.append(el.get(W + 'name'))
        elif tag in (W + 'sdt', W + 'sdtContent', W + 'customXml', W + 'smartTag'):
            for ch in el:
                block(ch, tbl, row, col, depth)
        elif tag == MC + 'AlternateContent':
            ch = el.find(MC + 'Choice')
            for x in (ch if ch is not None else []):
                block(x, tbl, row, col, depth)

    for el in body:
        block(el)
    read_docx.last_zero_width = zw[0]
    return items, tcount[0]


read_docx.last_zero_width = 0


# ---------------------------------------------------------------- 书册配置
class Prof:
    def __init__(self, d):
        self.d = d
        S = d.get('styles', {})
        g = lambda k: set(S.get(k, []) or [])
        self.h1, self.h2 = g('h1'), g('h2')
        self.base_title_styles = g('example_title')
        self.title_styles = set(self.base_title_styles)
        self.group_styles, self.method_styles = g('group_heading'), g('method')
        self.toc_styles = set(cfg(d, 'toc.styles', []) or []) | g('toc')
        self.rubric_styles = g('rubric')
        self.category_styles = g('category_line')
        dg = (d.get('drill') or {}).get('group_style')
        self.drill_group_styles = g('drill_group') | ({dg} if dg else set())
        self.zone_switch = {k: v for k, v in (cfg(d, 'structure.style_zone_switch', {}) or {}).items() if not k.startswith('_')}
        self.heading_like = self.h1 | self.h2 | self.group_styles | self.method_styles | g('category_line') | g('front_heading')
        self.titles = []
        for t in d.get('example_titles', []):
            sts = set(t.get('styles', []))
            self.title_styles |= sts
            self.titles.append((t['kind'], re.compile(t['regex']), sts, t.get('numbered', True)))
        st = d.get('structure', {})
        self.parts = [dict(p, _rx=re.compile(p['match'])) for p in st.get('parts', d.get('parts', []))]
        self.schemas = {k: v for k, v in d.get('column_schemas', {}).items() if isinstance(v, dict)}
        lr = d.get('labels_rules', {})
        self.source_labels = set(lr.get('source_labels', []) or [])
        self.rubric_labels = set(lr.get('rubric_labels', []) or [])
        self.answer_labels = set(cfg(d, 'labels_rules.answer_labels'))
        self.section_labels = set(d.get('section_labels') or [])
        self.hidden_labels = set(d.get('hidden_labels') or [])
        ok = cfg(d, 'labels_rules.block_label_allow_regex', []) or []
        self.label_ok = re.compile('|'.join('(?:%s)' % x for x in ok)) if ok else None
        known = set()
        for sc in self.schemas.values():
            known |= set(sc.get('labels', [])) | set(sc.get('extra_labels', [])) | set(sc.get('optional', []))
            known |= {k for k in (sc.get('forbidden_labels') or {}) if not k.startswith('_')}
            for grp in sc.get('require_one_of', []):
                known |= set(grp)
        self.block_labels = known | self.source_labels | self.rubric_labels | self.answer_labels | self.hidden_labels
        self.teaching_labels = self.block_labels - self.source_labels - self.rubric_labels
        self.block_end = [(set(b.get('styles', [])), re.compile(b['regex'])) for b in cfg(d, 'structure.block_end', []) if b.get('regex')]
        lead = cfg(d, 'structure.teaching_leadin_regex')
        self.leadin = re.compile(lead) if lead else None
        self.unmatched_title_ends = bool(cfg(d, 'structure.unmatched_title_style_ends_block', True))
        self.source_reenter = set(cfg(d, 'structure.source_style_reenter', []) or [])
        self.count_rx = re.compile(cfg(d, 'method_count.regex', r'（(\d+)题）\s*$'))
        kbl = cfg(d, 'example_kind_by_labels', {}) or {}
        self.kind_apply_to = set(kbl.get('_apply_to') or ['subjective'])
        self.kind_by_labels = [(k, list(v)) for k, v in kbl.items() if not k.startswith('_')]

    def title(self, it):
        if it['tbl'] is not None or it['style'] not in self.title_styles:
            return None
        for kind, rx, sts, numbered in self.titles:
            if (sts and it['style'] not in sts) or (not sts and it['style'] not in self.base_title_styles):
                continue
            m = rx.match(it['text'])
            if m:
                num = m.group('num') if 'num' in rx.groupindex else None
                return kind, int(num) if num else 0, m.group('src').strip(), numbered
        return None

    def part_of(self, h1text):
        for p in self.parts:
            if p['_rx'].search(h1text):
                return p
        return {'id': '(未配置)', 'schema': {}}


LABEL_START = re.compile(r"^\s*(【[^】]{1,40}】)")


def norm_label(lab):
    return re.sub(r'[（(][^）)]*[）)]', '', lab)


# ---------------------------------------------------------------- 结构标注
def walk(items, P):
    """给每段标注 part/node/method/ex/zone/label。zone ∈ cover/heading/toc/title/source/teaching/rubric/outside/drill。
    例题块内：标题→首个教学标签=题面区(source)；细则标签→下一标签=细则区(rubric)；其余教学标签=teaching。
    例题标题样式里认不出题号的段（如专题“任务五 时评短文与发言稿”）结束上一块，记为 heading。
    最后按 example_kind_by_labels 用栏目标签改判题型（哲学、选必一等主观题与选择题都叫“例题N”）。"""
    part = P.part_of('(前置)')
    node, method, ex = '', '', None
    zone, label, seen_h1 = 'cover', None, False
    drill_sec, drill_has_a1 = None, False
    blocks = []
    a1h = norm(cfg(P.d, 'drill.a1_heading', '') or '')
    a2h = norm(cfg(P.d, 'drill.a2_heading', '') or '')
    for it in items:
        st, t, intbl = it['style'], it['text'], it['tbl'] is not None
        it['_title'] = it['_method'] = it['_group'] = it['_subtitle'] = None
        it['_subhead'] = bool(t) and not intbl and any((not s or st in s) and rx.search(t) for s, rx in P.block_end)
        if st in P.h1 and not intbl:
            seen_h1 = True
            part = P.part_of(t)
            node, method, ex, zone, label = t, '', None, 'heading', None
            drill_sec = None
        elif st in P.h2 and not intbl:
            node, method, ex, zone, label = t, '', None, 'heading', None
            if part.get('drill'):
                nt = norm(t)
                if a1h and a1h in nt:
                    drill_sec, drill_has_a1 = 'A1', True
                elif (a2h and a2h in nt) or drill_has_a1:
                    drill_sec = 'A2'
        elif st in P.toc_styles:
            zone = 'toc'
        elif not seen_h1 and not intbl and not P.title(it):
            zone = 'cover'
        else:
            ti = P.title(it)
            if ti:
                kind, num, src, numbered = ti
                kind = part.get('kind_override', {}).get(kind, kind)
                ex = {'kind': kind, 'title_kind': kind, 'num': num, 'src': src, 'key': src_key(src), 'numbered': numbered,
                      'part': part['id'], 'node': node, 'method': method, 'title': t, 'title_i': it['i'],
                      'labels': Counter(), 'label_seq': [], 'unknown_labels': [], 'paras': []}
                blocks.append(ex)
                it['_title'] = ex
                zone, label = 'title', None
            elif not intbl and t and st in P.method_styles:
                method, ex, zone, label = t, None, 'heading', None
                it['_method'] = True
            elif not intbl and t and st in P.group_styles:
                ex, zone, label = None, 'heading', None
                it['_group'] = True
            elif part.get('drill'):
                zone = 'drill'
            elif not intbl and t and P.unmatched_title_ends and st in P.base_title_styles:
                ex, zone, label = None, 'heading', None
                it['_subtitle'] = True
            elif ex is not None and not intbl and t and (st in P.category_styles or it['_subhead']):
                ex, zone, label = None, 'outside', None
                it['_block_end'] = True
            elif ex is not None:
                m = LABEL_START.match(t)
                lab = norm_label(m.group(1)) if m else None
                if lab and P.label_ok and P.label_ok.search(lab) and lab not in P.block_labels:
                    lab = None
                if lab and lab in P.section_labels and lab not in P.block_labels:
                    ex, zone, label = None, 'outside', None
                elif lab and lab in P.block_labels:
                    ex['labels'][lab] += 1
                    ex['label_seq'].append(lab)
                    label = lab
                    zone = 'source' if lab in P.source_labels else ('rubric' if lab in P.rubric_labels else 'teaching')
                elif lab and zone not in ('source', 'title') and not intbl:
                    ex['unknown_labels'].append({'label': m.group(1), 'i': it['i']})
                    label = lab
                    zone = 'rubric' if st in P.rubric_styles else 'teaching'
                elif not lab and not intbl and zone in ('teaching', 'rubric') and st in P.source_reenter:
                    zone, label = 'source', '(按样式回到题面)'   # 专题任务型：块内后一道小题的设问
                elif P.leadin and not intbl and P.leadin.match(t):
                    zone, label = 'teaching', '(引导语)'
                elif zone in ('title', 'source') and not intbl and st in P.zone_switch:
                    zone, label = P.zone_switch[st], '(按样式)'
                elif zone == 'title':
                    zone = 'source'
            else:
                zone, label = 'outside', None
        it['zone'], it['label'] = zone, label
        it['part'], it['node'], it['method'], it['ex'] = part['id'], node, method, ex
        it['drill_sec'] = drill_sec if part.get('drill') else None
        if ex is not None and not it['_title']:
            ex['paras'].append(it['i'])
    for e in blocks:
        if e['kind'] in P.kind_apply_to:
            for k, labs in P.kind_by_labels:
                if any(e['labels'][L] for L in labs):
                    e['kind'], e['kind_by'] = k, 'labels'
                    break
    return blocks


# ---------------------------------------------------------------- 发现项
class Findings:
    def __init__(self):
        self.items = []
        self.src = 'docx'      # 发现项来源：docx / pdf / baseline（相对上批才有的比较，不进棘轮）

    def add(self, check, level, rule, it=None, text=None, **extra):
        f = OrderedDict([('check', check), ('level', level), ('rule', rule), ('src', self.src)])
        if it is not None:
            ex = it.get('ex') or it.get('_title')
            f['where'] = OrderedDict([('para', it['i']), ('part', it.get('part')), ('node', clip(it.get('node'), 30)),
                                      ('example', clip(ex['title'], 40) if ex else None), ('style', it['style']),
                                      ('zone', it.get('zone'))])
        if text is not None:
            f['excerpt'] = text
        f.update(extra)
        self.items.append(f)
        return f


def _where_ex(ex):
    return OrderedDict([('para', ex['title_i']), ('part', ex['part']), ('node', clip(ex['node'], 30)),
                        ('example', clip(ex['title'], 40))])


# ---------------------------------------------------------------- 检查 0：结构识别（配置是否对得上这本书）
def check_structure(items, blocks, P, F):
    h1 = [it for it in items if it['style'] in P.h1 and it['tbl'] is None and it['text']]
    unmatched = [it for it in h1 if P.part_of(it['text'])['id'] == '(未配置)']
    for it in unmatched:
        F.add('structure', 'CANDIDATE', '一级标题没有匹配任何已配置的部分', it, text=clip(it['text'], 40))
    if not blocks:
        F.add('structure', 'FAIL', '没有识别出任何例题标题（检查 styles.example_title 与 example_titles 正则）', None)
    kinds = Counter(e['kind'] for e in blocks)
    sub = [it for it in items if it.get('_subtitle')]
    return {'h1': len(h1), 'h1_unmatched': len(unmatched), 'blocks_by_kind': dict(kinds),
            'kind_changed_by_labels': sum(1 for e in blocks if e.get('kind_by') == 'labels'),
            'title_style_non_example_headings': len(sub),
            'parts_seen': sorted({it['part'] for it in items})}


# ---------------------------------------------------------------- 检查 1：栏目模式
def _exempt_rules(P):
    """具名例外：column_exemptions 列表 + schema.exempt_if_source_in 指向的 sources.no_e1_exceptions。"""
    out = []
    for e in P.d.get('column_exemptions', []) or []:
        out.append((re.compile(e['src_regex']), set(e.get('labels', [])), e.get('reason', '')))
    return out


def _no_e1(P, ex):
    ne = cfg(P.d, 'sources.no_e1_exceptions', {}) or {}
    k = ex['key']
    for w in ne.get('whole_papers', []) or []:
        if src_key(w) and k.startswith(src_key(w)):
            return '整卷无正式细则：' + w
    for q in ne.get('questions', []) or []:
        if src_key(q) == k:
            return '具名无正式细则：' + q
    return None


def check_columns(items, blocks, P, F):
    parts = {p['id']: p for p in P.parts}
    stats, exempted = OrderedDict(), []
    ex_rules = _exempt_rules(P)
    for e in blocks:
        pc = parts.get(e['part'], {})
        sname = pc.get('schema', {}).get(e['kind'])
        key = f"{e['part']}|{e['kind']}"
        s = stats.setdefault(key, {'titles': 0, 'schema': sname, 'blocks_bad': 0})
        s['titles'] += 1
        if not sname:
            continue
        sc = P.schemas[sname]
        mode = sc.get('mode', 'each_once')
        optional, repeatable = set(sc.get('optional', [])), set(sc.get('repeatable', []))
        forb = {k: v for k, v in (sc.get('forbidden_labels') or {}).items() if not k.startswith('_')}
        used_forb = [L for L in OrderedDict.fromkeys(e['label_seq']) if L in forb]
        covered = {(forb[L] or {}).get('instead') for L in used_forb if isinstance(forb[L], dict)}
        probs = []
        for L in sc.get('labels', []):
            n = e['labels'][L]
            if n == 0 and L in covered:
                continue          # 用了被禁止的替代标签，下面一并报，不重复报缺栏
            if L in optional:
                ok = n <= 1 or L in repeatable
            elif mode == 'at_least_once' or L in repeatable:
                ok = n >= 1
            else:
                ok = n == 1
            if not ok:
                probs.append((L, n))
        for grp in sc.get('require_one_of', []):
            tot = sum(e['labels'][L] for L in grp)
            if tot != 1:
                probs.append(('/'.join(grp), tot))
        if used_forb:
            s['blocks_bad'] += 1
            f0 = forb[used_forb[0]] if isinstance(forb[used_forb[0]], dict) else {}
            F.add('columns', 'FAIL', '使用了本栏目模式禁止的标签', None, where=_where_ex(e), labels=used_forb,
                  instead=sorted(x for x in covered if x), basis=f0.get('reason'), label_seq=e['label_seq'][:12])
        if probs:
            reason = None
            for rx, labs, why in ex_rules:
                if rx.search(e['key']) and all(L in labs for L, _ in probs):
                    reason = why
            if not reason and sc.get('exempt_if_source_in') and all(L in P.rubric_labels for L, _ in probs):
                reason = _no_e1(P, e)
            if reason:
                exempted.append({'example': e['title'], 'labels': dict(probs), 'reason': reason})
            else:
                if not used_forb:
                    s['blocks_bad'] += 1
                for L, n in probs:
                    F.add('columns', 'FAIL', '栏目缺失或重复', None, where=_where_ex(e), label=L, count=n,
                          label_seq=e['label_seq'][:12])
        # 顺序：各标签首次出现的顺序应与 schema 一致
        order = [L for L in sc.get('labels', []) if e['labels'][L]]
        seq = []
        for L in e['label_seq']:
            if L in order and L not in seq:
                seq.append(L)
        if seq != order:
            F.add('columns', 'CANDIDATE', '栏目顺序与配置不同', None, where=_where_ex(e), label_seq=e['label_seq'][:12])
        others = set()
        for other, osc in P.schemas.items():
            if other != sname:
                others |= set(osc.get('labels', []))
        allowed = set(sc.get('labels', [])) | set(sc.get('extra_labels', [])) | set(sc.get('optional', [])) | set(forb)
        for grp in sc.get('require_one_of', []):
            allowed |= set(grp)
        stray = [L for L in OrderedDict.fromkeys(e['label_seq']) if L in others and L not in allowed]
        for L in e['label_seq']:
            if L in P.hidden_labels:
                F.add('columns', 'FAIL', '出现已删除的可见标签', None, where=_where_ex(e), label=L)
        for u in e['unknown_labels']:
            F.add('columns', 'CANDIDATE', '例题块内非本栏目标签', items[u['i']], text=clip(items[u['i']]['text'], 60), label=u['label'])
        for L in stray:
            F.add('columns', 'CANDIDATE', '例题块内出现其他题型的栏目', None, where=_where_ex(e), label=L)
    return {'by_part_kind': stats, 'exempted': exempted}


# ---------------------------------------------------------------- 检查 2：例题编号
def check_numbering(items, blocks, P, F):
    parts = {p['id']: p for p in P.parts}
    unnumbered = set(cfg(P.d, 'numbering.unnumbered_kinds', []) or [])
    per_kind = cfg(P.d, 'numbering.per_kind', True)
    seen, n_checked = {}, 0
    order_rule = defaultdict(list)
    for it in items:
        pr = parts.get(it['part'], {})
        resets = set(pr.get('numbering_reset', ['h2']))
        if it['zone'] == 'heading':
            if (it['style'] in P.h1 and it['tbl'] is None) or ('h2' in resets and it['style'] in P.h2 and it['tbl'] is None) \
                    or ('method' in resets and it['_method']) or ('group_heading' in resets and it['_group']):
                seen = {}
            if it['style'] in P.h1 or it['style'] in P.h2:
                order_rule.clear()
        e = it['_title']
        if not e:
            continue
        if pr.get('choice_after_subjective_in_node'):
            order_rule[it['node']].append(e)
        if e['kind'] in unnumbered or e['title_kind'] in unnumbered or not e['numbered']:
            continue
        n_checked += 1
        # 按标题写法（title_kind）连号：标签改判题型不改变编号序列
        k = e['title_kind'] if per_kind else '*'
        exp = seen.get(k, 0) + 1
        if e['num'] != exp:
            F.add('numbering', 'FAIL', '例题编号不连续', it, text=clip(it['text'], 50), expected=exp, actual=e['num'])
        seen[k] = e['num']
        if pr.get('choice_after_subjective_in_node') and e['kind'] == 'subjective':
            if any(x['kind'] == 'choice' for x in order_rule[it['node']][:-1]):
                F.add('numbering', 'FAIL', '选择例题须排在本节点主观例题之后', it, text=clip(it['text'], 50))
    return {'titles_checked': n_checked}


# ---------------------------------------------------------------- 检查 3：考法标称题数
def check_method_counts(items, P, F):
    parts = {p['id']: p for p in P.parts}
    kinds = set(cfg(P.d, 'method_count.count_kinds', ['subjective']))
    bearers = set(cfg(P.d, 'method_count.bearer_styles', list(P.method_styles)))
    unit = cfg(P.d, 'method_count.unit', 'blocks')
    cur, n_b, n_nocount = None, 0, 0

    def close():
        if cur and cur['claimed'] is not None:
            actual = len(set(cur['keys'])) if unit == 'unique_questions' else len(cur['keys'])
            if actual != cur['claimed']:
                F.add('method_counts', 'FAIL', '考法标称题数与实际例题数不符', cur['it'], text=clip(cur['it']['text'], 50),
                      claimed=cur['claimed'], actual=actual)
    for it in items:
        if it['zone'] == 'heading' and it['tbl'] is None:
            if it['style'] in bearers:
                m = P.count_rx.search(it['text'])
                if m or it['_method']:
                    close()
                    n_b += 1
                    if not m:
                        n_nocount += 1
                        if not parts.get(it['part'], {}).get('method_without_count_allowed'):
                            F.add('method_counts', 'CANDIDATE', '考法标题未写（N题）', it, text=clip(it['text'], 50))
                    cur = {'it': it, 'claimed': int(m.group(1)) if m else None, 'keys': []}
                    continue
            if it['style'] in P.h1 or it['style'] in P.h2 or it['_group'] or it['_method']:
                close()
                cur = None
        elif it['_title'] and cur is not None and it['_title']['kind'] in kinds:
            cur['keys'].append(it['_title']['key'])
    close()
    return {'bearers': n_b, 'bearers_without_count': n_nocount}


# ---------------------------------------------------------------- 检查 4：学生正文
def _word_lists(d):
    """工程标签（全区扫描）＋分组词表与工程词（只扫教学/细则/节内正文/标题）。同一个词只归一组。"""
    tags = list(cfg(d, 'student_text.engineering_tags', []) or [])
    words = list(cfg(d, 'student_text.forbidden_words_common', []) or []) + list(cfg(d, 'student_text.forbidden_words_book', []) or [])
    groups = cfg(d, 'student_text.forbidden_word_groups', {}) or {}
    seen, full = set(), []
    tag_list = []
    for w in tags:
        if w not in seen:
            seen.add(w)
            tag_list.append(('工程标签', w))
    full += tag_list
    for g, ws in list((k, v) for k, v in groups.items() if not k.startswith('_')):
        for w in ws:
            if w not in seen:
                seen.add(w)
                full.append((g, w))
    for w in words:
        if w not in seen:
            seen.add(w)
            full.append(('工程词', w))
    return tag_list, full


def check_student_text(items, P, F):
    d = P.d
    tag_list, wlist = _word_lists(d)
    warn_words = list(cfg(d, 'student_text.warn_words', []) or [])
    glv = cfg(d, 'student_text.forbidden_word_group_levels', {}) or {}
    allow = cfg(d, 'student_text.allow_contexts', {}) or {}
    line_start = [re.compile(x) for x in cfg(d, 'student_text.line_start_forbidden', []) or []]
    trail = re.compile(cfg(d, 'student_text.trailing_tag_regex'))
    tl = cfg(d, 'student_text.trailing_tag_levels', {}) or {}
    trail_default, trail_parts = tl.get('default', 'FAIL'), tl.get('parts', {})
    wz = set(cfg(d, 'student_text.forbidden_word_zones', ['teaching', 'rubric', 'outside', 'heading']))
    tz = set(cfg(d, 'student_text.trailing_tag_zones', ['teaching', 'outside']))
    t_ex = set(cfg(d, 'student_text.trailing_tag_exempt_styles', []) or [])
    warnp = {k: re.compile(v) for k, v in (cfg(d, 'student_text.warn_patterns', {}) or {}).items()}
    forbid_lines = [re.compile(x) for x in cfg(d, 'labels_rules.forbid_line_regex', []) or []]
    fl_level = cfg(d, 'labels_rules.forbid_line_level', 'FAIL')
    fr = cfg(d, 'student_text.four_rights')
    dr = d.get('drill') or {}
    marker = dr.get('correction_marker', '纠正：')
    item_rx = re.compile(dr.get('item_regex') or r'^(\d+)[、.．]\s*(.*)$', re.S)
    n_full, n_tags = 0, 0
    for it in items:
        t, z = it['text'], it['zone']
        if not t or z == 'toc' or it['style'] in P.toc_styles:
            continue
        # 分段：scope=full 扫全部词表，scope=tags 只扫工程标签（题面、标题、单练题肢与题源等原卷文字）
        if z == 'drill':
            p = t.find(marker)
            if it['tbl'] is not None:
                segs = [(t[:p], 'tags'), (t[p:], 'full')] if p > 0 else [(t, 'full' if p == 0 else 'tags')]
            elif p == 0 or it.get('drill_sec') is None or not item_rx.match(t):
                segs = [(t, 'full')]
            else:
                segs = [(t[:p], 'tags'), (t[p:], 'full')] if p > 0 else [(t, 'tags')]
        elif z in wz:
            segs = [(t, 'full')]
        else:
            segs = [(t, 'tags')]
        for seg, scope in segs:
            if not seg:
                continue
            if scope == 'full':
                n_full += 1
            else:
                n_tags += 1
            for g, w in (wlist if scope == 'full' else tag_list):
                q = seg.find(w)
                if q >= 0 and not any(a in t for a in allow.get(w, [])):
                    gl = glv.get(g, {})
                    F.add('student_text', gl.get('parts', {}).get(it['part'], gl.get('default', 'FAIL')), f'{g}:{w}', it,
                          text=window(seg, q, q + len(w)), scope='全部词表' if scope == 'full' else '仅工程标签（原卷文字区）')
            if scope != 'full':
                continue
            for w in warn_words:
                q = seg.find(w)
                if q >= 0:
                    F.add('student_text', 'WARN', f'待裁定词:{w}', it, text=window(seg, q, q + len(w)))
            for rx in line_start:
                if rx.search(seg):
                    F.add('student_text', 'FAIL', f'行首禁用:{rx.pattern}', it, text=clip(seg, 50))
            for name, rx in warnp.items():
                m = rx.search(seg)
                if m:
                    F.add('student_text', 'WARN', f'句式提示:{name}', it, text=window(seg, m.start(), m.end(), 10))
        if z in tz and it['tbl'] is None and it['style'] not in t_ex:
            m = trail.search(t)
            if m:
                score_only = bool(re.fullmatch(r'[（(]\s*\d+(\.\d+)?\s*分\s*[)）][。；]?', m.group(0)))
                is_ans = it.get('label') in P.answer_labels
                # 答案落点里只含分值的括注交给“答案落点不标分”，这里只报试卷/题号括注
                if not (is_ans and not PAPER_RX.search(m.group(0).translate(_FW))):
                    lvl = trail_parts.get(it['part'], trail_default)
                    F.add('student_text', lvl, '条目末尾带分值' if score_only else '条目末尾带试卷/题号', it,
                          text=(CUT + '…' if len(t) > 60 else '') + t[-60:])
        if z in ('teaching', 'rubric', 'outside') and it['tbl'] is None:
            for rx in forbid_lines:
                if rx.search(t):
                    F.add('student_text', fl_level, f'已撤销的独立行:{rx.pattern}', it, text=clip(t, 40))
        if fr and z in ('teaching', 'rubric', 'outside') and not (z == 'drill' and it['tbl'] is not None):
            _four_rights(it, t, fr, F)
    return {'segments_full_wordlist': n_full, 'segments_tags_only': n_tags,
            'engineering_tags': [w for _, w in tag_list]}


def _four_rights(it, t, fr, F):
    names = fr.get('rights', ['知情权', '参与权', '表达权', '监督权'])
    have = [r for r in names if r in t]
    if not have or len(have) == len(names) or set(have) <= set(fr.get('alone_ok', ['监督权'])):
        return
    if any(re.search(rx, t) for rx in fr.get('exempt_if_regex', [])):
        return
    F.add('four_rights', fr.get('level', 'WARN'), '四权未一串写', it, text=clip(t, 60), present=have)


# ---------------------------------------------------------------- 检查 5：单练 A1/A2
def collect_drill(items, P):
    """按 drill.layout 取单练条目：table3（三列表：题肢｜判断｜题源）或 paragraph（段落式：条目段＋其后的“纠正：”段）。
    返回 dict(layout, recs, other, total, intro, drill_paras)。recs 每条带 sec(A1/A2)、no、stem、ans、src、red/green/marker。"""
    c = P.d.get('drill') or {}
    layout = c.get('layout', 'table3')
    item_rx = re.compile(c.get('item_regex') or r'^(\d+)[、.．]\s*(.*)$', re.S)
    marker = c.get('correction_marker', '纠正：')
    colors = c.get('colors', {}) or {}
    err_c, cor_c = colors.get('error_run', 'C00000').upper(), colors.get('correction', '008000').upper()
    blank = norm(c.get('a1_blank', '（　）'))
    has_sec = any(it.get('drill_sec') for it in items)
    drill_paras = [it for it in items if it['zone'] == 'drill' and it['text']]
    recs, other, total, intro = [], 0, 0, []
    if layout == 'table3':
        rows = OrderedDict()
        for it in items:
            if it['zone'] != 'drill':
                continue
            if it['tbl'] is None:
                intro.append(it)
                continue
            r = rows.setdefault((it['tbl'], it['row']), {'cells': defaultdict(lambda: {'text': '', 'runs': []}),
                                                         'sec': it.get('drill_sec'), 'it': it})
            cell = r['cells'][it['col']]
            cell['text'] += it['text']
            cell['runs'] += it['runs']
        sc, ac, rc = c.get('stem_col', 0), c.get('answer_col', 1), c.get('source_col', 2)
        for k, r in rows.items():
            total += 1
            cells = r['cells']
            stem = cells[sc]['text'] if sc in cells else ''
            m = item_rx.match(stem)
            if len(cells) != c.get('columns', 3) or not m:
                other += 1
                continue
            ans = norm(cells[ac]['text']) if ac in cells else ''
            cols = {x for _, x in cells[sc]['runs']}
            recs.append({'no': m.group(1), 'stem': norm(m.group(2).split(marker)[0]), 'body': norm(m.group(2)), 'ans': ans,
                         'src': norm(cells[rc]['text']) if rc in cells else '',
                         'red': err_c in cols, 'green': cor_c in cols, 'marker': marker in stem, 'tbl': k[0],
                         'it': r['it'], 'text': stem, 'derived': False,
                         'sec': r['sec'] if has_sec else ('A1' if ans == blank else 'A2')})
    else:
        item_styles = set(c.get('item_styles') or [])
        corr_styles = set(c.get('correction_styles') or [])
        grp_rx = re.compile(c['group_label_regex']) if c.get('group_label_regex') else None
        vrx = re.compile(c.get('paragraph_verdict_regex') or r'[（(]\s*(正确|错误|不选)\s*[)）]\s*$')
        last, grp = None, 0
        for it in drill_paras:
            t = it['text']
            if it.get('drill_sec') is None:
                intro.append(it)
                continue
            if it['style'] in P.drill_group_styles or (grp_rx and grp_rx.match(t)):
                grp += 1
                last = None
                continue
            cols = {x for _, x in it['runs']}
            if t.startswith(marker):
                total += 1
                if last is None:
                    other += 1
                else:
                    last['marker'] = True
                    last['green'] = last['green'] or cor_c in cols
                    last['corr_it'] = it
                continue
            if it['style'] in corr_styles:
                # 纠正样式却不以“纠正：”开头（如“提示：表述本身成立……材料未体现”）：记为附注，不当纠正
                total += 1
                if last is None:
                    other += 1
                else:
                    last.setdefault('notes', []).append(it)
                continue
            total += 1
            m = item_rx.match(t)
            if not m or (item_styles and it['style'] not in item_styles):
                other += 1
                last = None
                continue
            vm = vrx.search(t)
            body = m.group(2)[:vm.start() - m.start(2)] if vm else m.group(2)
            last = {'no': m.group(1), 'stem': norm(body.split(marker)[0]), 'body': norm(m.group(2)),
                    'ans': vm.group(1) if vm else None, 'src': '',
                    'red': err_c in cols, 'green': False, 'marker': False, 'tbl': ('组', it['drill_sec'], grp),
                    'it': it, 'text': t, 'derived': vm is None, 'sec': it['drill_sec']}
            recs.append(last)
        for r in recs:
            if r['ans'] is None:
                # 段落式 A2 没有判断栏：有纠正或红色错处即“错误”，否则“正确”（机器推断，derived=True）
                r['ans'] = '' if r['sec'] == 'A1' else ('错误' if (r['marker'] or r['red']) else '正确')
    return {'layout': layout, 'recs': recs, 'other': other, 'total': total, 'intro': intro, 'drill_paras': len(drill_paras)}


def check_drill(items, P, F):
    c = P.d.get('drill')
    if not c:
        return {'note': '本册未配置单练'}
    D = collect_drill(items, P)
    layout = D['layout']
    for it in D['intro']:
        if it['tbl'] is not None:
            continue
        for w in c.get('intro_forbidden', []) or []:
            p = it['text'].find(w)
            if p >= 0:
                F.add('drill', 'CANDIDATE', f'单练导语出现“{w}”', it, text=window(it['text'], p, p + len(w)))
    A1 = [x for x in D['recs'] if x['sec'] == 'A1']
    A2 = [x for x in D['recs'] if x['sec'] != 'A1']
    # 结构识别：配置了单练、文中有单练段落，却认不出条目（或多数行不是条目）时判 FAIL，不静默通过
    ratio_max = float(cfg(P.d, 'drill.max_non_item_ratio', 0.3))
    if D['drill_paras'] == 0:
        F.add('drill', 'WARN', '配置了单练，文中没有找到单练部分（structure.parts[].drill）', None)
    elif not D['recs']:
        F.add('drill', 'FAIL', '单练结构未识别：配置的版式认不出任何条目', None, layout=layout, drill_paragraphs=D['drill_paras'],
              rows_seen=D['total'])
    elif D['total'] >= 20 and D['other'] / D['total'] > ratio_max:
        F.add('drill', 'FAIL', '单练结构未识别：多数行不是条目', None, layout=layout, rows_seen=D['total'], non_item=D['other'],
              limit=ratio_max)
    blank = norm(c.get('a1_blank', '（　）'))
    allowed = set(c.get('a2_allowed', ['正确', '错误']))
    a1f = c.get('a1_forbid', []) or []
    for x in A1:
        if layout == 'table3' and x['ans'] != blank:
            F.add('drill', 'FAIL', 'A1 判断栏不是空括号', x['it'], text=clip(x['text'], 40), answer=x['ans'])
        for w in a1f:
            if w in x['text']:
                F.add('drill', 'FAIL', f'A1 出现答案提示“{w}”', x['it'], text=clip(x['text'], 50))
        if x['red'] or x['green'] or x['marker']:
            F.add('drill', 'FAIL', 'A1 带正误颜色或纠正', x['it'], text=clip(x['text'], 40))
    for x in A2:
        if not x['derived'] and x['ans'] not in allowed:
            F.add('drill', 'FAIL', 'A2 判断只允许“' + '/'.join(sorted(allowed)) + '”', x['it'], text=clip(x['text'], 40), answer=x['ans'])
        if x['ans'] == '错误':
            if not x['red']:
                F.add('drill', 'FAIL', 'A2 错误行缺红色错处', x['it'], text=clip(x['text'], 40))
            if not (x['green'] and x['marker']):
                F.add('drill', 'FAIL', 'A2 错误行缺绿色“纠正”', x['it'], text=clip(x['text'], 40))
        elif x['ans'] == '正确' and (x['red'] or x['green'] or x['marker']):
            F.add('drill', 'CANDIDATE', 'A2 正确行带红绿或纠正', x['it'], text=clip(x['text'], 40))
        if x.get('notes') and not x['marker']:
            F.add('drill', 'CANDIDATE', 'A2 条目后有非“纠正：”附注（可能是“不选”类题肢，单练只分正确/错误）', x['it'],
                  text=clip(x['text'], 40), note_excerpt=clip(x['notes'][0]['text'], 60))
    for x in A1:
        if x.get('notes'):
            F.add('drill', 'FAIL', 'A1 条目后带附注或提示', x['it'], text=clip(x['text'], 40), note_excerpt=clip(x['notes'][0]['text'], 60))
    if len(A1) != len(A2):
        F.add('drill', 'FAIL', 'A1 与 A2 条数不同', None, a1=len(A1), a2=len(A2))
    mism = 0
    for x, y in zip(A1, A2):
        if (x['no'], x['stem'][:20], x['src']) != (y['no'], y['stem'][:20], y['src']):
            mism += 1
            if mism <= 20:
                F.add('drill', 'FAIL', 'A1/A2 同序号条目不一致', y['it'], text=clip(y['text'], 40), a1=clip(x['text'], 40))
    if mism > 20:
        F.add('drill', 'FAIL', 'A1/A2 同序号条目不一致（其余）', None, more=mism - 20)
    alt = c.get('alternation', {}) or {}
    by_tbl = defaultdict(list)
    for x in A2:
        by_tbl[x['tbl']].append(x['ans'])
    max_run = 0
    for tno, ans in by_tbl.items():
        run, last, mx = 0, None, 0
        for a in ans:
            run = run + 1 if a == last else 1
            last, mx = a, max(mx, run)
        max_run = max(max_run, mx)
        if alt.get('required') and mx > alt.get('max_same_run_per_table', 3):
            # 用户规则只说“总体交替、不成固定规律”，没有给阈值：缺省只 WARN（alternation.level 可改）
            F.add('drill', alt.get('level', 'WARN'), 'A2 同一判断连续过长', None, table=str(tno), max_run=mx,
                  limit=alt.get('max_same_run_per_table', 3), limit_basis=alt.get('_level_note') or '工具提示值，非用户原话阈值')
        if c.get('each_table_has_both') and len(ans) > 1 and len(set(ans)) < 2:
            F.add('drill', 'FAIL', 'A2 表内正误不齐', None, table=str(tno), answers=sorted(set(ans)))
    return {'layout': layout, 'a1': len(A1), 'a2': len(A2), 'rows_seen': D['total'], 'non_item_rows': D['other'],
            'a1_a2_mismatch': mism, 'a2_groups': len(by_tbl), 'a2_max_same_run': max_run,
            'a2_answers': dict(Counter(x['ans'] for x in A2)),
            'a2_answers_derived': sum(1 for x in A2 if x['derived'])}


# ---------------------------------------------------------------- 检查 6：目录（DOCX 部分）
def toc_entries(items, P):
    bm = {}
    for it in items:
        for b in it['bookmarks']:
            bm.setdefault(b, it['i'])
    out = []
    for it in items:
        if it['style'] not in P.toc_styles:
            continue
        m = re.match(r'^(.*?)[\s\t.…·]*(\d+)$', it['text'])
        if not m:
            continue
        pr = re.findall(r'PAGEREF\s+(\S+)', it['instr'] or '')
        out.append({'it': it, 'label': m.group(1).strip(), 'cached': int(m.group(2)),
                    'anchor': it['anchors'][0] if it['anchors'] else None, 'pageref': pr[0] if pr else None,
                    'target_i': bm.get(it['anchors'][0]) if it['anchors'] else None})
    return out, bm


def check_toc_docx(items, P, F):
    ents, bm = toc_entries(items, P)
    differs = cfg(P.d, 'toc.label_differs_from_heading', False)
    for e in ents:
        it = e['it']
        if not e['anchor']:
            F.add('toc', 'FAIL', '目录条目没有超链接锚点', it, text=clip(it['text'], 40))
            continue
        if e['target_i'] is None:
            F.add('toc', 'FAIL', '超链接锚点在文档中没有书签', it, text=clip(it['text'], 40), anchor=e['anchor'])
            continue
        if cfg(P.d, 'toc.check_pageref_equals_hyperlink_anchor', True) and e['pageref'] and e['pageref'] != e['anchor']:
            tgt = bm.get(e['pageref'])
            F.add('toc', 'FAIL', 'PAGEREF 目标与超链接锚点不一致', it, text=clip(it['text'], 40), hyperlink=e['anchor'],
                  pageref=e['pageref'], pageref_heading=clip(items[tgt]['text'], 30) if tgt is not None else None,
                  anchor_heading=clip(items[e['target_i']]['text'], 30))
        head = items[e['target_i']]['text']
        if not differs and norm(e['label']) != norm(head):
            F.add('toc', 'CANDIDATE', '目录文字与书签所在标题不同', it, text=clip(it['text'], 40), heading=clip(head, 40))
    exp = cfg(P.d, 'toc.entries_expected')
    if exp and exp != len(ents):
        F.add('toc', 'WARN', '目录条目数与配置不同', None, expected=exp, actual=len(ents))
    return ents, {'entries': len(ents)}


# ---------------------------------------------------------------- 检查 9：题面零改写、替换误伤、同批副本
def check_collateral(items, P, F):
    pats = [re.compile(x) for x in cfg(P.d, 'student_text.collateral_patterns', []) or []]
    sus = list(cfg(P.d, 'student_text.source_suspect_words', []) or [])
    for it in items:
        t = it['text']
        if not t or it['zone'] in ('toc', 'cover'):
            continue
        hit = False
        for rx in pats:
            m = rx.search(t)
            if m:
                hit = True
                F.add('source_fidelity', 'CANDIDATE', '疑似全局替换误伤', it, text=window(t, m.start(), m.end()), match=m.group(0))
                break
        if not hit and it['zone'] in ('source', 'title', 'drill'):
            for w in sus:
                p = t.find(w)
                if p >= 0:
                    F.add('source_fidelity', 'CANDIDATE', f'题面区出现“{w}”', it, text=window(t, p, p + len(w)))
                    break


def _strip_label_raw(t, P, any_label=False):
    m = LABEL_START.match(t)
    if m and (any_label or norm_label(m.group(1)) in P.source_labels):
        t = t[m.end():]
    return t.strip()


def block_source(items, e, P):
    """一个例题块的题面区：段落列表 [(比较用文字, 原文, it, 去任意段首标签后的比较文字)] 与图片哈希列表。"""
    paras, imgs = [], []
    for i in e['paras']:
        it = items[i]
        if it['zone'] != 'source':
            continue
        imgs += it.get('imgs', [])
        raw = _strip_label_raw(it['text'], P)
        s = norm(raw)
        if s:
            paras.append((s, raw, it, norm(_strip_label_raw(it['text'], P, True))))
    return paras, imgs


def _frag(a, b, n=6):
    """原文（去段首题面标签、保留空白）上的差异片段。"""
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    ops = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op != 'equal':
            ops.append(OrderedDict([('op', op), ('base', clip(a[i1:i2], 30)), ('cur', clip(b[j1:j2], 30)),
                                    ('context', window(b, j1, j2, 12))]))
    return ops[:n]


def _sim(a, b):
    if a == b:
        return 1.0
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sm.quick_ratio()


def _best_run(target, seq, idxs, ratio):
    """idxs 里相邻编号的至少两段拼起来与 target 相似度 ≥ ratio 的最佳一段。"""
    best, L = None, len(target)
    for a in range(len(idxs)):
        acc, run = seq[idxs[a]], [idxs[a]]
        for b in range(a + 1, len(idxs)):
            if idxs[b] != idxs[b - 1] + 1:
                break
            acc += seq[idxs[b]]
            run.append(idxs[b])
            if len(acc) > L * 1.3 + 10:
                break
            if len(acc) < L * 0.7:
                continue
            sm = difflib.SequenceMatcher(None, acc, target, autojunk=False)
            if sm.quick_ratio() < ratio:
                continue
            r = sm.ratio()
            if r >= ratio and (best is None or r > best[1]):
                best = (list(run), r)
    return best


def diff_source(bsrc, csrc, ratio):
    """两份题面段落列表的差异事件：ws 仅空白、label 仅段首标签、edit 改字、merge 几段并一段、split 一段拆几段、
    miss 上批段缺失、new 本批新段。"""
    b, c = [x[0] for x in bsrc], [x[0] for x in csrc]
    ev = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, b, c, autojunk=False).get_opcodes():
        if op == 'equal':
            for k in range(i2 - i1):
                if bsrc[i1 + k][1] != csrc[j1 + k][1]:
                    ev.append(('ws', i1 + k, j1 + k))
            continue
        B, C = list(range(i1, i2)), list(range(j1, j2))
        uB, uC = set(), set()
        if len(B) * len(C) <= 400:
            for j in C:
                best = _best_run(c[j], b, [i for i in B if i not in uB], ratio) if len(B) >= 2 else None
                if best:
                    ev.append(('merge', best[0], j, best[1]))
                    uB |= set(best[0])
                    uC.add(j)
            for i in B:
                if i in uB or len(C) < 2:
                    continue
                best = _best_run(b[i], c, [j for j in C if j not in uC], ratio)
                if best:
                    ev.append(('split', i, best[0], best[1]))
                    uB.add(i)
                    uC |= set(best[0])
        pairs = []
        for i in B:
            if i in uB:
                continue
            for j in C:
                if j in uC:
                    continue
                if bsrc[i][3] == csrc[j][3]:
                    pairs.append((2.0, i, j))
                    continue
                sm = difflib.SequenceMatcher(None, b[i], c[j], autojunk=False)
                if sm.real_quick_ratio() < ratio or sm.quick_ratio() < ratio:
                    continue
                r = sm.ratio()
                if r >= ratio:
                    pairs.append((r, i, j))
        for r, i, j in sorted(pairs, reverse=True):
            if i in uB or j in uC:
                continue
            uB.add(i)
            uC.add(j)
            ev.append(('label', i, j) if r == 2.0 else ('edit', i, j, r))
        ev += [('miss', i) for i in B if i not in uB]
        ev += [('new', j) for j in C if j not in uC]
    return ev


# 事件 → (规则名, 级别)。restored=True（已登记恢复原题的题键）时 FAIL/CANDIDATE 降为 INFO
SRC_RULES = OrderedDict([
    ('ws', ('题面仅空白不同', 'INFO')),
    ('label', ('题面区仅段首【标签】与上批不同', 'CANDIDATE')),
    ('edit', ('同题键题面相对上批被改字', 'FAIL')),
    ('merge', ('题面几段被合并成一段', 'FAIL')),
    ('merge_edit', ('题面几段被合并成一段且文字有改动', 'FAIL')),
    ('split', ('题面一段被拆成几段', 'CANDIDATE')),
    ('split_edit', ('题面一段被拆成几段且文字有改动', 'FAIL')),
    ('miss', ('上批题面段在本批缺失', 'FAIL')),
    ('new', ('同题键题面出现上批没有的段落', 'CANDIDATE')),
    ('img_fewer', ('题面图片比上批少', 'CANDIDATE')),
    ('img_changed', ('题面图片与上批不同', 'CANDIDATE')),
])


def _refinfo(cb, ref):
    same = (ref['part'], ref['kind'], norm(ref['node'])) == (cb['part'], cb['kind'], norm(cb['node']))
    return OrderedDict([('ref_part', ref['part']), ('ref_title', clip(ref['title'], 40)),
                        ('ref_relation', '同一位置' if same else '同题另一处')])


class _Dedup:
    """同题键、同一差异内容在多个例题块里重复出现时只列一条，其余位置记在 also_in（计 occurrences）。"""
    def __init__(self, F):
        self.F, self.seen = F, {}

    def add(self, sig, cb, check, level, rule, it=None, text=None, **kw):
        f = self.seen.get(sig)
        if f is not None:
            f['occurrences'] += 1
            if len(f['also_in']) < 12:
                f['also_in'].append(OrderedDict([('para', cb['title_i']), ('part', cb['part']), ('example', clip(cb['title'], 40))]))
            return f
        f = self.F.add(check, level, rule, it, text, **kw)
        f['occurrences'], f['also_in'] = 1, []
        self.seen[sig] = f
        return f


def _event_kind(e):
    k = e[0]
    if k in ('merge', 'split') and e[3] < 0.9999:
        return k + '_edit'          # 拼接后与原段不完全相同：不只是分段变化，还改了字
    return k


def emit_source_events(ev, bsrc, csrc, bimgs, cimgs, cb, ref, dd, st, restored):
    """相对上批的差异写成发现项：改字、合并、拆分逐段列；缺失段与新段按块汇总（附原文截取）；图片按块比。"""
    refinfo = _refinfo(cb, ref)
    key = cb['key']

    def rl(k):
        r, l = SRC_RULES[k]
        if restored and l in ('FAIL', 'CANDIDATE'):
            return '已登记恢复原题：' + r, 'INFO'
        return r, l
    miss, new = [], []
    for e in ev:
        k = _event_kind(e)
        st[k] += 1
        if k == 'miss':
            miss.append(e[1])
            continue
        if k == 'new':
            new.append(e[1])
            continue
        r, l = rl(k)
        if k in ('ws', 'label', 'edit'):
            b, c = bsrc[e[1]], csrc[e[2]]
            extra = {'ratio': round(e[3], 3), 'edits': _frag(b[1], c[1]), 'text_basis': '原文（去段首题面标签，保留空白）',
                     'note': '若是恢复原题，须对原卷确认后登记；脚本不判断哪一版是原题'} if k == 'edit' else {}
            dd.add((k, key, b[1], c[1]), cb, 'source_fidelity', l, r, c[2],
                   text=clip(c[2]['text'] if k == 'label' else c[1], 60), key=key,
                   base_excerpt=clip(b[2]['text'] if k == 'label' else b[1], 60), **dict(refinfo, **extra))
        elif k in ('merge', 'merge_edit'):
            bs, c = [bsrc[i][1] for i in e[1]], csrc[e[2]]
            extra = {'edits': _frag(''.join(bs), c[1]), 'text_basis': '上批几段原文直接相接 对 本批一段原文'} if k == 'merge_edit' else {}
            dd.add((k, key, tuple(bs), c[1]), cb, 'source_fidelity', l, r, c[2], text=clip(c[1], 60), key=key,
                   ratio=round(e[3], 3), base_paragraphs=len(bs), base_excerpts=[clip(x, 30) for x in bs[:4]],
                   **dict(refinfo, **extra))
        elif k in ('split', 'split_edit'):
            b, cs = bsrc[e[1]], [csrc[j][1] for j in e[2]]
            extra = {'edits': _frag(b[1], ''.join(cs)), 'text_basis': '上批一段原文 对 本批几段原文直接相接'} if k == 'split_edit' else {}
            dd.add((k, key, b[1], tuple(cs)), cb, 'source_fidelity', l, r, csrc[e[2][0]][2], text=clip(cs[0], 60), key=key,
                   ratio=round(e[3], 3), cur_paragraphs=len(cs), base_excerpt=clip(b[1], 60), **dict(refinfo, **extra))
    if miss:
        r, l = rl('miss')
        bs = [bsrc[i][1] for i in miss]
        dd.add(('miss', key, tuple(bs)), cb, 'source_fidelity', l, r, None, where=_where_ex(cb), key=key,
               paragraphs=len(bs), base_excerpts=[clip(x, 60) for x in bs[:8]],
               base_paras=[bsrc[i][2]['i'] for i in miss[:8]], **refinfo)
    if new:
        r, l = rl('new')
        cs = [csrc[j][1] for j in new]
        dd.add(('new', key, tuple(cs)), cb, 'source_fidelity', l, r, csrc[new[0]][2], text=clip(cs[0], 60), key=key,
               paragraphs=len(cs), excerpts=[clip(x, 60) for x in cs[:8]], **refinfo)
    if len(cimgs) < len(bimgs) or (len(cimgs) == len(bimgs) and Counter(cimgs) != Counter(bimgs)):
        k = 'img_fewer' if len(cimgs) < len(bimgs) else 'img_changed'
        st[k] += 1
        r, _ = SRC_RULES[k]
        dd.add((k, key, len(bimgs), len(cimgs), tuple(sorted(cimgs))), cb, 'source_fidelity', 'CANDIDATE', r, None,
               where=_where_ex(cb), key=key, base_images=len(bimgs), cur_images=len(cimgs), **refinfo)


def _closest(cb, cjoin, cands, joins):
    """同题键的参照块：题面最相近者；相近度相同时取同部分、同题型、同节点。"""
    best, bs = None, None
    for b in cands:
        s = (_sim(joins[id(b)], cjoin), (b['part'], b['kind']) == (cb['part'], cb['kind']), norm(b['node']) == norm(cb['node']))
        if bs is None or s > bs:
            best, bs = b, s
    return best


def check_source_vs_baseline(cur_items, cur_blocks, base_items, base_blocks, P, F, restored=None):
    """逐块比较：本批每个例题块与上批同题键里题面最相近的一块比（不再把同题键各块段落合并，避免互相掩盖）。
    返回 (统计, 相对上批另一部分作参照且有差异的块的标题段号集合)。"""
    ratio = cfg(P.d, 'baseline.near_edit_ratio', 0.85)
    restored = set(restored or [])
    st = Counter()
    dd = _Dedup(F)
    bsrc, bj = {}, {}
    bykey = defaultdict(list)
    for b in base_blocks:
        bsrc[id(b)] = block_source(base_items, b, P)
        bj[id(b)] = ''.join(x[0] for x in bsrc[id(b)][0])
        if bsrc[id(b)][0] or bsrc[id(b)][1]:
            bykey[b['key']].append(b)
    keys, cross_reported = set(), set()
    for cb in cur_blocks:
        csrc, cimgs = block_source(cur_items, cb, P)
        if not csrc and not cimgs:
            st['blocks_without_source'] += 1
            continue
        cands = bykey.get(cb['key'])
        if not cands:
            st['blocks_new_key'] += 1
            continue
        keys.add(cb['key'])
        cjoin = ''.join(x[0] for x in csrc)
        ref = _closest(cb, cjoin, cands, bj)
        st['blocks_compared'] += 1
        cross = (ref['part'], ref['kind']) != (cb['part'], cb['kind'])
        if cross:
            st['blocks_compared_cross_part'] += 1
        rsrc, rimgs = bsrc[id(ref)]
        if cjoin == bj[id(ref)] and [x[1] for x in rsrc] == [x[1] for x in csrc] and Counter(rimgs) == Counter(cimgs):
            st['blocks_identical'] += 1
            continue
        ev = diff_source(rsrc, csrc, ratio)
        if cross:
            cross_reported.add(cb['title_i'])
        emit_source_events(ev, rsrc, csrc, rimgs, cimgs, cb, ref, dd, st, cb['key'] in restored)
    st['keys_compared'] = len(keys)
    st['findings_merged_as_repeats'] = sum(f['occurrences'] - 1 for f in dd.seen.values())
    if restored:
        st['restore_list_keys'] = len(restored)
    return dict(st), cross_reported


def check_copy_consistency(items, blocks, P, F):
    """同批副本：配置了 structure.copy_check 时，把 copy_parts 里的例题与 ref_parts 里同题键的题面比较
    （必修三：专题例题题面须沿用第一部分同题原排版，style-spec 2026-09-23）。不需要基线；每块最多两条 CANDIDATE。"""
    cc = cfg(P.d, 'structure.copy_check')
    if not cc:
        return None
    ratio = cfg(P.d, 'baseline.near_edit_ratio', 0.85)
    cparts, rparts = set(cc.get('copy_parts', [])), set(cc.get('ref_parts', []))
    ckinds = set(cc.get('copy_kinds') or [])
    src, joins = {}, {}
    refs = defaultdict(list)
    for b in blocks:
        if b['part'] in rparts:
            src[id(b)] = block_source(items, b, P)
            joins[id(b)] = ''.join(x[0] for x in src[id(b)][0])
            refs[b['key']].append(b)
    st = Counter()
    for cb in blocks:
        if cb['part'] not in cparts or (ckinds and cb['kind'] not in ckinds) or cb['key'] not in refs:
            continue
        csrc, cimgs = block_source(items, cb, P)
        if not csrc and not cimgs:
            continue
        cjoin = ''.join(x[0] for x in csrc)
        ref = _closest(cb, cjoin, refs[cb['key']], joins)
        rsrc, rimgs = src[id(ref)]
        st['copies_compared'] += 1
        if cjoin == joins[id(ref)] and Counter(rimgs) == Counter(cimgs):
            st['copies_identical'] += 1
            continue
        ev = [e for e in diff_source(rsrc, csrc, ratio) if e[0] != 'ws']
        refinfo = _refinfo(cb, ref)
        if ev:
            st['copies_text_differs'] += 1
            cnt = Counter(_event_kind(e) for e in ev)
            miss = [clip(rsrc[e[1]][1], 40) for e in ev if e[0] == 'miss'][:4]
            new = [clip(csrc[e[1]][1], 40) for e in ev if e[0] == 'new'][:4]
            edits = [_frag(rsrc[e[1]][1], csrc[e[2]][1], 3) for e in ev if e[0] == 'edit'][:3]
            F.add('source_fidelity', 'CANDIDATE', '同批副本：题面文字与原题不同', None, where=_where_ex(cb), key=cb['key'],
                  events={SRC_RULES[k][0].replace('上批', '原题'): n for k, n in cnt.items()},
                  ref_missing_excerpts=miss, copy_new_excerpts=new, edits=edits, basis=cc.get('basis'), **refinfo)
        if len(cimgs) < len(rimgs):
            st['copies_fewer_images'] += 1
            F.add('source_fidelity', 'CANDIDATE', '同批副本：题面图片比原题少', None, where=_where_ex(cb), key=cb['key'],
                  ref_images=len(rimgs), copy_images=len(cimgs), basis=cc.get('basis'), **refinfo)
    return dict(st)


# ---------------------------------------------------------------- 检查 10：教学正文误蓝
def check_blue(items, P, F):
    blue = {x.upper() for x in cfg(P.d, 'colors.blue', [])}
    lb = cfg(P.d, 'typography.colors.label_blue')
    if lb:
        blue.add(lb.upper())
    ex_pre = tuple(cfg(P.d, 'colors.blue_exempt_prefix', []) or [])
    ex_sty = set(cfg(P.d, 'colors.blue_exempt_styles', []) or []) | P.heading_like | P.title_styles | P.toc_styles
    stat = Counter()
    for it in items:
        z = it['zone']
        if z not in ('teaching', 'rubric', 'source', 'outside') or it['style'] in ex_sty:
            continue
        if not it['text'] or it.get('_subhead') or (ex_pre and it['text'].startswith(ex_pre)):
            continue
        raw = ''.join(t for t, _ in it['runs'])
        spans = [m.span() for m in re.finditer(r'【[^】]{1,40}】', raw)
                 if z != 'source' or norm_label(m.group(0)) in P.block_labels]
        leak, o = [], 0
        for t, c in it['runs']:
            a, o = o, o + len(t)
            if c not in blue:
                continue
            # 去掉落在【标签】范围内的字符（标签可能被拆成几个 run）
            rest = ''.join(ch for k, ch in enumerate(t) if not any(x <= a + k < y for x, y in spans))
            if CJK.search(rest) or re.search(r'[A-Za-z0-9]', rest):
                leak.append(rest)
        if not leak:
            continue
        if z in ('teaching', 'rubric'):
            lvl, rule = 'FAIL', '教学正文误蓝'
        elif z == 'source':
            lvl, rule = 'CANDIDATE', '题面正文蓝色'
        else:
            lvl, rule = 'CANDIDATE', '节内正文蓝色'
        stat[rule] += 1
        F.add('blue', lvl, rule, it, text=clip(''.join(leak), 40), runs=len(leak),
              excerpt_kind='蓝色 run 的文字拼接（已剔除【标签】，非连续原文）', para_excerpt=clip(it['text'], 60))
    return dict(stat)


# ---------------------------------------------------------------- 检查 11：答案落点不标分
def check_answer_score(items, P, F):
    rx = re.compile(cfg(P.d, 'labels_rules.answer_score_regex'))
    lvl = cfg(P.d, 'labels_rules.answer_score_level', 'WARN')
    n = 0
    for it in items:
        if it.get('label') in P.answer_labels and it['zone'] == 'teaching' and it['text']:
            n += 1
            m = rx.search(it['text'])
            if m:
                F.add('answer_score', lvl, '答案落点标了分值', it, text=window(it['text'], m.start(), m.end()))
    return {'answer_paragraphs': n}


# ---------------------------------------------------------------- 检查 12：选择题答案与逐肢判定
def _derive_choice(verd, combos, want):
    """按逐肢判定反推答案：返回 (状态, 推出的字母, 详情)。状态 ∈ ok/none/multi/unparsed。"""
    circ = all(k in '①②③④⑤⑥⑦⑧⑨' for k in verd)
    lett = all(k in 'ABCD' for k in verd)
    if circ and combos:
        pick = ''.join(k for k in '①②③④⑤⑥⑦⑧⑨' if verd.get(k) == want)
        hit = [L for L, cmb in combos.items() if cmb == pick]
        return ('ok', hit[0], pick) if hit else ('none', None, pick)
    if lett:
        pick = [k for k in 'ABCD' if verd.get(k) == want]
        return ('ok', ''.join(pick), pick) if len(pick) == 1 else ('multi', None, pick)
    return ('unparsed', None, list(verd))


def check_choice(items, blocks, P, F):
    cc = lambda k: cfg(P.d, 'choice_check.' + k)
    rev_rx, ver_rx, combo_rx = re.compile(cc('reverse_regex')), re.compile(cc('verdict_regex')), re.compile(cc('option_combo_regex'))
    kinds = set(cfg(P.d, 'choice_check.kinds', ['choice']))
    hint = cc('reverse_hint_regex')
    ans_rx = re.compile(cc('answer_regex') or r'^\s*【答案】\s*([A-D]+)')
    st = Counter()
    for e in blocks:
        if e['kind'] not in kinds:
            continue
        st['blocks'] += 1
        ans, combos, verd, stem = None, {}, OrderedDict(), []
        for i in e['paras']:
            it = items[i]
            t = it['text']
            if it['zone'] == 'source':
                stem.append(t)
                for m in combo_rx.finditer(t):
                    combos.setdefault(m.group(1), m.group(2))
            elif it['zone'] == 'teaching':
                m = ans_rx.match(t)
                if m and ans is None:
                    ans = m.group(1)
                m = ver_rx.match(t)
                if m and m.group(1) not in verd:
                    verd[m.group(1)] = m.group(2)
        opt_rx = re.compile(r'^\s*([A-D][．.、]|[①-⑨])')
        qtext = ''.join(t for t in stem if not opt_rx.match(t))
        teach = ''.join(items[i]['text'] for i in e['paras'] if items[i]['zone'] == 'teaching')[:400]
        rev_stem = bool(rev_rx.search(qtext))
        rev_hint = bool(hint and re.search(hint, teach))
        reverse = rev_stem or rev_hint
        if reverse:
            st['reverse_questions'] += 1
        if not ans:
            st['no_answer'] += 1
            F.add('choice', 'WARN', '未解析出【答案】字母', None, where=_where_ex(e))
            continue
        if not verd:
            st['no_verdict'] += 1
            F.add('choice', 'WARN', '未解析出逐肢判定', None, where=_where_ex(e), answer=ans)
            continue
        if rev_hint and not rev_stem:
            # 设问正则看不出反向，解析却自述“逆向选择”：两种方向都推一遍，交主代理判断，不据此判一致或矛盾
            st['direction_conflict'] += 1
            fwd, rev = _derive_choice(verd, combos, '正确'), _derive_choice(verd, combos, '错误')
            F.add('choice', 'CANDIDATE', '设问方向与解析自述不一致', None, where=_where_ex(e), answer=ans,
                  stem_reverse=False, analysis_says_reverse=True, derived_if_forward=fwd[1], derived_if_reverse=rev[1],
                  stem_excerpt=clip(qtext, 60))
            continue
        want = '错误' if reverse else '正确'
        state, derived, detail = _derive_choice(verd, combos, want)
        if state == 'ok':
            if derived == ans:
                st['consistent'] += 1
            else:
                st['mismatch'] += 1
                F.add('choice', 'FAIL', '【答案】与逐肢判定推出的选项不同', None, where=_where_ex(e),
                      answer=ans, derived=derived, picked=detail, reverse_question=reverse, verdicts=dict(verd))
        elif state == 'none':
            st['combo_not_found'] += 1
            F.add('choice', 'CANDIDATE', '判为' + want + '的题肢组合没有对应选项', None, where=_where_ex(e),
                  answer=ans, picked=detail, combos=combos, reverse_question=reverse)
        elif state == 'multi':
            st['ambiguous'] += 1
            F.add('choice', 'CANDIDATE', '逐肢判定推不出唯一答案', None, where=_where_ex(e),
                  answer=ans, picked=detail, reverse_question=reverse, verdicts=dict(verd))
        else:
            st['unparsed'] += 1
            F.add('choice', 'WARN', '题肢写法无法机械核对', None, where=_where_ex(e), answer=ans, verdict_keys=detail)
    return dict(st)


# ---------------------------------------------------------------- keepNext
def check_keepnext(items, P, F):
    lrx = cfg(P.d, 'pagination.keep_next_label_regex')
    tgt = cfg(P.d, 'pagination.keep_next_target_style')
    lrx = re.compile(lrx) if lrx else None
    st = Counter()
    for it in items:
        if not it['text']:
            continue
        if cfg(P.d, 'pagination.keep_next_title_required', True) and (it['_title'] or it['_method']) and it['tbl'] is None:
            if not it['keepnext']:
                st['titles'] += 1
                F.add('keepnext', 'WARN', '例题/考法标题未设 keepNext', it, text=clip(it['text'], 40))
        elif lrx and (not tgt or it['style'] == tgt) and it['zone'] == 'source' and lrx.search(it['text']) \
                and len(it['text']) <= 16 and not it['keepnext']:
            st['material_heads'] += 1
            F.add('keepnext', 'WARN', '材料小标题未设 keepNext', it, text=clip(it['text'], 20), in_table=it['tbl'] is not None)
    return dict(st)


# ---------------------------------------------------------------- 例题块与单练行（基线差异用）
def block_signatures(items, blocks, P):
    sig = OrderedDict()
    for e in blocks:
        body = '\n'.join(items[i]['text'] for i in e['paras'])
        imgs = [h for i in [e['title_i']] + e['paras'] for h in items[i].get('imgs', [])]
        sig.setdefault((e['kind'], e['key']), []).append(
            {'h': hashlib.sha1(body.encode()).hexdigest()[:16], 'm': hashlib.sha1('|'.join(imgs).encode()).hexdigest()[:12],
             'imgs': len(imgs), 'pos': (e['part'], norm(e['node'])[:20], norm(e['method'])[:20], e['num']), 'title': e['title']})
    if P.d.get('drill'):
        for x in collect_drill(items, P)['recs']:
            body = x['body']                      # 不含条目序号：重新分组编号不算正文改动
            corr = norm(x.get('corr_it', {}).get('text', ''))
            k = ('drill_' + ('A1' if x['sec'] == 'A1' else 'A2'), x['src'] + '|' + x['stem'][:40])
            sig.setdefault(k, []).append({'h': hashlib.sha1((body + '|' + (x['ans'] or '') + '|' + corr).encode()).hexdigest()[:16],
                                          'm': '', 'imgs': 0, 'pos': (x['no'],), 'title': clip(x['text'], 40), 'tbl': str(x['tbl'])})
    return sig


def diff_blocks(cur, base, cap):
    """按（题型, 题键）比较例题块与单练行：新增、删除、正文改动、仅图片改动、仅换位（正文与图片相同、位置或编号变）、未变。计数按块。"""
    out = {'by_kind': defaultdict(Counter), 'samples': defaultdict(list)}

    def add(kind, cat, sample, n=1):
        out['by_kind'][kind][cat] += n
        if len(out['samples'][cat]) < cap:
            out['samples'][cat].append(dict(sample, n=n))
    for k in cur.keys() | base.keys():
        kind = k[0]
        c, b = cur.get(k, []), base.get(k, [])
        if not b:
            add(kind, 'added', {'kind': kind, 'key': k[1], 'title': c[0]['title']}, len(c))
            continue
        if not c:
            add(kind, 'removed', {'kind': kind, 'key': k[1], 'title': b[0]['title']}, len(b))
            continue
        hm = lambda x: x['h'] + '|' + x['m']
        ch, bh = Counter(hm(x) for x in c), Counter(hm(x) for x in b)
        common = sum((ch & bh).values())
        moved = common and sorted(x['pos'] for x in c if hm(x) in bh) != sorted(x['pos'] for x in b if hm(x) in ch)
        rest_c = list((ch - bh).elements())
        rest_b = list((bh - ch).elements())
        # 剩余里正文相同、图片不同的，记“仅图片改动”
        tc = Counter(x.split('|')[0] for x in rest_c)
        tb = Counter(x.split('|')[0] for x in rest_b)
        media_only = sum((tc & tb).values())
        changed = min(len(rest_c), len(rest_b)) - media_only
        extra_c = len(rest_c) - media_only - changed
        extra_b = len(rest_b) - media_only - changed
        smp = {'kind': kind, 'key': k[1], 'title': c[0]['title']}
        if media_only:
            imgs_c = [x['imgs'] for x in c if hm(x) in (ch - bh)]
            imgs_b = [x['imgs'] for x in b if hm(x) in (bh - ch)]
            add(kind, 'media_changed', dict(smp, images_cur=imgs_c[:4], images_base=imgs_b[:4]), media_only)
        if changed:
            add(kind, 'body_changed', smp, changed)
        if extra_c:
            add(kind, 'added', smp, extra_c)
        if extra_b:
            add(kind, 'removed', {'kind': kind, 'key': k[1], 'title': b[0]['title']}, extra_b)
        if common:
            add(kind, 'moved_only' if moved else 'unchanged', smp, common)
    out['by_kind'] = {k: dict(v) for k, v in out['by_kind'].items()}
    tot = Counter()
    for v in out['by_kind'].values():
        tot.update(v)
    out['totals'] = dict(tot)
    out['samples'] = {k: v for k, v in out['samples'].items() if k != 'unchanged'}
    out['note'] = ('仅换位＝正文逐字相同且图片相同、所在部分/节点/考法/编号变化；仅图片改动＝正文相同、图片（按媒体字节哈希）不同；'
                   '单练行按判断栏＋题源＋题肢前40字配对')
    return out


# ---------------------------------------------------------------- PDF：页脚、目录落页、字体回退、同版
def pdf_scan(doc, P):
    """一次遍历 PDF：每页全文（span 拼接）、页底文字、各字体承载的汉字数与样例。"""
    band = cfg(P.d, 'footer.bottom_band', 0.12)
    pages = []
    for pg in doc:
        ybot = pg.rect.y1 - pg.rect.height * band
        parts, foot, fonts, sample = [], [], Counter(), {}
        for b in pg.get_text('dict', flags=0)['blocks']:
            for ln in b.get('lines', []):
                for sp in ln['spans']:
                    t = sp['text']
                    parts.append(t)
                    if sp['bbox'][1] >= ybot:
                        foot.append(t)
                    n = len(CJK.findall(t))
                    if n:
                        f = re.sub(r'^[A-Z]{6}\+', '', sp['font'])
                        fonts[f] += n
                        sample.setdefault(f, clip(t.strip(), 20))
                parts.append('\n')
        pages.append({'text': ''.join(parts), 'foot': ''.join(foot), 'fonts': fonts, 'sample': sample})
    return pages


def pdf_pages_text(scan):
    return [p['text'] for p in scan]


def pdf_meta(doc):
    md = doc.metadata or {}
    return OrderedDict((k, md.get(k)) for k in ('producer', 'creator', 'creationDate', 'modDate') if md.get(k))


def check_footer(scan, P, F):
    rx = re.compile(cfg(P.d, 'footer.regex', r'—\s*(\d+)\s*—'))
    exempt = set(cfg(P.d, 'footer.exempt_pages', []) or [])
    off = cfg(P.d, 'footer.page_offset', 0) or 0
    got = []
    for pg in scan:
        m = rx.search(pg['foot'])
        got.append(int(m.group(1)) if m else None)
    for i, n in enumerate(got):
        pno = i + 1
        if pno in exempt:
            if n is not None:
                F.add('footer', 'INFO', '豁免页也有页脚', None, page=pno, footer=n)
            continue
        if n is None:
            F.add('footer', 'FAIL', '非豁免页缺页脚', None, page=pno)
        elif cfg(P.d, 'footer.continuous', True) and n != pno + off:
            F.add('footer', 'FAIL', '页脚页码不连续', None, page=pno, footer=n, expected=pno + off)
    return {'pages': len(got), 'with_footer': sum(1 for n in got if n is not None)}


def check_toc_pdf(doc, ents, items, P, F, texts):
    import fitz
    pages = cfg(P.d, 'toc.toc_pdf_pages') or list(range(1, min(cfg(P.d, 'toc.scan_first_pages', 8), len(doc)) + 1))
    links = []
    for pno in pages:
        if pno - 1 >= len(doc):
            continue
        pg = doc[pno - 1]
        for l in sorted(pg.get_links(), key=lambda l: (round(l['from'].y0), l['from'].x0)):
            if l.get('kind') != fitz.LINK_GOTO:
                continue
            y = round(l['from'].y0)
            if links and links[-1]['p'] == pno and abs(links[-1]['y'] - y) <= 3:
                continue
            links.append({'p': pno, 'y': y, 'dest': l.get('page', -1) + 1,
                          'text': norm(pg.get_textbox(l['from']))})
    links.sort(key=lambda x: (x['p'], x['y']))
    npages = [norm(t) for t in texts]
    tocset = set(pages)
    used, mapped = set(), 0
    if len(links) != len(ents):
        F.add('toc', 'FAIL', 'PDF 目录链接行数与 DOCX 目录条目数不同', None, pdf_links=len(links), docx_entries=len(ents))
    for idx, e in enumerate(ents):
        lab = norm(e['label'])
        cand = [j for j, l in enumerate(links) if j not in used and l['text'].startswith(lab[:10])]
        j = cand[0] if cand else (idx if idx < len(links) and idx not in used else None)
        if j is None:
            F.add('toc', 'FAIL', '目录条目在 PDF 里找不到链接', e['it'], text=clip(e['it']['text'], 40))
            continue
        used.add(j)
        mapped += 1
        l = links[j]
        head = norm(items[e['target_i']]['text'])[:12] if e['target_i'] is not None else ''
        on_page = bool(head) and 0 < l['dest'] <= len(doc) and head in npages[l['dest'] - 1]
        actual = None
        if head:
            actual = next((i + 1 for i, t in enumerate(npages) if (i + 1) not in tocset and head in t), None)
        if e['cached'] != l['dest']:
            F.add('toc', 'FAIL', '目录页码与 PDF 链接落页不同', e['it'], text=clip(e['it']['text'], 40),
                  cached=e['cached'], link_page=l['dest'], heading_first_page=actual)
        if not on_page:
            F.add('toc', 'FAIL', 'PDF 链接落页上找不到对应标题', e['it'], text=clip(e['it']['text'], 40),
                  link_page=l['dest'], heading_first_page=actual)
    return {'pdf_link_lines': len(links), 'mapped': mapped}


def check_fonts(scan, P, F):
    exp = re.compile(cfg(P.d, 'pdf_fonts.expected_cjk_regex'))
    th = cfg(P.d, 'pdf_fonts.fail_min_chars_page', 20)
    byfont, pages = Counter(), []
    for i, pg in enumerate(scan):
        byfont.update(pg['fonts'])
        bad = Counter({f: n for f, n in pg['fonts'].items() if not exp.search(f)})
        sample = {f: pg['sample'][f] for f in bad}
        if bad:
            tot = sum(bad.values())
            pages.append(i + 1)
            F.add('pdf_fonts', 'FAIL' if tot >= th else 'WARN', '汉字落在非预期字体（回退）', None, page=i + 1,
                  fonts=dict(bad), sample=sample)
    return {'cjk_by_font': dict(byfont.most_common()), 'fallback_pages': pages}


def _identity_records(P, docx, pdf, identity=None):
    """同版身份记录：--identity 指定的文件，或 PDF/DOCX 所在目录及上两级的 render.identity_file 与审阅清单。"""
    name = cfg(P.d, 'render.identity_file', '同版身份.json') or '同版身份.json'
    man = Path(cfg(P.d, 'publish.manifest', '.review-manifest.json') or '.review-manifest.json').name
    files = [Path(identity)] if identity else []      # 明确指定时只认这一份
    pp, dp = Path(pdf).resolve(), Path(docx).resolve()
    for d in (() if identity else (pp.parent, pp.parent.parent, pp.parent.parent.parent, dp.parent, dp.parent.parent)):
        for f in (d / name, d / man):
            if f not in files:
                files.append(f)
    recs = []
    for f in files:
        if not f.is_file():
            continue
        try:
            j = json.loads(f.read_text(encoding='utf-8'))
        except (ValueError, OSError):
            continue
        if isinstance(j, dict) and (j.get('docx_sha256') or j.get('pdf_sha256')):
            recs.append({'file': str(f), 'docx_sha256': j.get('docx_sha256'), 'pdf_sha256': j.get('pdf_sha256')})
    return recs


def check_same_version(items, P, F, texts, docx, docx_sha, pdf, pdf_sha, identity=None):
    """PDF 与 DOCX 是否同版：①同版身份记录的 SHA 核对；②DOCX 的一二级标题、考法与例题标题在 PDF 文字里能否按序找到。"""
    st = OrderedDict()
    recs = _identity_records(P, docx, pdf, identity)
    st['identity_files_seen'] = [r['file'] for r in recs]
    both = [r for r in recs if r['docx_sha256'] == docx_sha and r['pdf_sha256'] == pdf_sha]
    d_only = [r for r in recs if r['docx_sha256'] == docx_sha and r['pdf_sha256'] and r['pdf_sha256'] != pdf_sha]
    p_only = [r for r in recs if r['pdf_sha256'] == pdf_sha and r['docx_sha256'] and r['docx_sha256'] != docx_sha]
    if both:
        st['identity'] = 'match'
        st['identity_file'] = both[0]['file']
    elif d_only:
        st['identity'] = 'pdf_mismatch'
        F.add('same_version', 'FAIL', '同版身份记录里本 DOCX 对应的不是这份 PDF', None, identity_file=d_only[0]['file'],
              recorded_pdf_sha256=d_only[0]['pdf_sha256'], pdf_sha256=pdf_sha)
    elif p_only:
        st['identity'] = 'docx_mismatch'
        F.add('same_version', 'FAIL', '同版身份记录显示这份 PDF 由另一份 DOCX 渲染', None, identity_file=p_only[0]['file'],
              recorded_docx_sha256=p_only[0]['docx_sha256'], docx_sha256=docx_sha)
    elif recs:
        st['identity'] = 'unrelated'
        F.add('same_version', 'WARN', '找到同版身份记录，但与本批 DOCX/PDF 都不对应', None, identity_files=[r['file'] for r in recs][:4])
    else:
        st['identity'] = 'not_found'
        F.add('same_version', 'WARN', '未找到同版身份记录（render.identity_file），只能按标题对照判断同版', None)
    probes = []
    for it in items:
        if it['tbl'] is None and it['text'] and (it['_title'] or it['_method'] or
                                                 ((it['style'] in P.h1 or it['style'] in P.h2) and it['zone'] == 'heading')):
            s = norm(it['text'])[:20]
            if len(s) >= 4:
                probes.append((s, it))
    joined = norm(''.join(texts))
    pos, miss = 0, []
    for s, it in probes:
        k = joined.find(s, pos)
        if k < 0:
            k = joined.find(s)
        if k < 0:
            miss.append(it)
        else:
            pos = k
    found = 1 - len(miss) / len(probes) if probes else 1.0
    thr = float(cfg(P.d, 'same_version.title_found_min', 0.98))
    st.update(titles_probed=len(probes), titles_missing=len(miss), titles_found_ratio=round(found, 4), threshold=thr)
    if probes and found < thr:
        F.add('same_version', 'FAIL', 'DOCX 标题在 PDF 里找不到的比例过高（疑似非同版）', None, missing=len(miss), probed=len(probes),
              samples=[clip(it['text'], 30) for it in miss[:8]])
    elif miss:
        for it in miss[:20]:
            F.add('same_version', 'CANDIDATE', 'DOCX 标题在 PDF 文字里找不到', it, text=clip(it['text'], 40))
    return st


def locate_pages(findings, items, texts):
    """给带段落号的发现项猜 PDF 页码（按段落开头文字在页面文字里顺序查找；机器猜测，仅供定位）。"""
    npages = [norm(t) for t in texts]
    cache = {}
    last = 0
    for f in sorted((f for f in findings if f.get('where') and f['where'].get('para') is not None),
                    key=lambda f: f['where']['para']):
        i = f['where']['para']
        if i in cache:
            f['pdf_page_guess'] = cache[i]
            continue
        probe = norm(items[i]['text'])[:18]
        pg = None
        if len(probe) >= 6:
            for j in list(range(last, len(npages))) + list(range(0, last)):
                if probe in npages[j]:
                    pg = j + 1
                    break
        if pg:
            last = pg - 1
        cache[i] = pg
        f['pdf_page_guess'] = pg


# ---------------------------------------------------------------- 汇总与棘轮
CHECK_NAMES = OrderedDict([
    ('structure', '0 结构识别'), ('columns', '1 栏目模式'), ('numbering', '2 例题编号'), ('method_counts', '3 考法标称题数'),
    ('student_text', '4 学生正文工程词与末尾括注'), ('drill', '5 单练A1/A2'), ('toc', '6 目录'),
    ('footer', '7 页脚'), ('pdf_fonts', '8 PDF字体回退'), ('same_version', '8b PDF与DOCX同版'),
    ('source_fidelity', '9 题面零改写、替换误伤与同批副本'),
    ('blue', '10 教学正文误蓝'), ('answer_score', '11 答案落点不标分'), ('choice', '12 选择题答案与逐肢判定'),
    ('ratchet', '13 回退棘轮'), ('baseline_blocks', '14 例题块差异'), ('four_rights', '四权一串写（提示）'),
    ('keepnext', 'keepNext（提示，棘轮）'),
])
# 棘轮：只有明文列出的计数（keepNext 缺失，本身是 WARN）增加才另判 FAIL；FAIL 级计数增加已在原门判过，只记 INFO；
# CANDIDATE 级增加记 WARN“较上批新增 N 条待判”；其余 WARN 级增加记 WARN。四权按规则只做 WARN。
RATCHET_FAIL_COUNTERS = {'keepnext'}
RATCHET_SKIP_CHECKS = {'ratchet', 'baseline_blocks', 'same_version'}
RATCHET_SKIP_RULE = ('句式提示:',)


def _block_id(f):
    w = f.get('where') or {}
    return (w.get('part'), w.get('node'), w.get('example')) if w.get('example') else None


def counters_of(findings):
    """（检查, 规则, 级别, 部分）计数。同一例题块在本检查已有 FAIL 的，其 CANDIDATE/WARN 不再计（不重复计）。"""
    fail_blocks = {(f['check'], _block_id(f)) for f in findings if f['level'] == 'FAIL' and _block_id(f)}
    c = Counter()
    for f in findings:
        if f['level'] == 'INFO' or f['check'] in RATCHET_SKIP_CHECKS or f['rule'].startswith(RATCHET_SKIP_RULE):
            continue
        if f['level'] != 'FAIL' and _block_id(f) and (f['check'], _block_id(f)) in fail_blocks:
            continue
        part = (f.get('where') or {}).get('part') or '-'
        c[(f['check'], f['rule'], f['level'], part)] += 1
    return c


def ratchet(cur_f, base_f, F):
    ca, ba = counters_of(cur_f), counters_of(base_f)
    rows = []
    for k in sorted(set(ca) | set(ba)):
        ck, rule, lv, part = k
        cur, base = ca.get(k, 0), ba.get(k, 0)
        row = OrderedDict([('check', ck), ('rule', rule), ('level', lv), ('part', part), ('base', base), ('cur', cur),
                           ('delta', cur - base)])
        if cur > base:
            ctr = f'{ck}|{rule}|{lv}|{part}'
            if ck in RATCHET_FAIL_COUNTERS:
                row['verdict'] = '回退（明文棘轮计数）'
                F.add('ratchet', 'FAIL', '计数比上批增加（回退）', None, counter=ctr, base=base, cur=cur)
            elif lv == 'FAIL':
                row['verdict'] = '回退（原门已判 FAIL，不重复计）'
                F.add('ratchet', 'INFO', '计数比上批增加（原门已判 FAIL，不重复计）', None, counter=ctr, base=base, cur=cur)
            elif lv == 'CANDIDATE':
                row['verdict'] = '较上批新增待判'
                F.add('ratchet', 'WARN', f'较上批新增 {cur - base} 条待判（明细见原门 CANDIDATE）', None, counter=ctr,
                      base=base, cur=cur)
            else:
                row['verdict'] = '提示增加'
                F.add('ratchet', 'WARN', '计数比上批增加', None, counter=ctr, base=base, cur=cur)
        rows.append(row)
    return rows


class Analysis:
    """单个 DOCX 的全部 DOCX 层检查。items 可传入已读好的段落流（测试或别的工具复用）。"""
    def __init__(self, path, P, items=None):
        t0 = time.time()
        self.path = path
        if items is None:
            self.items, self.tables = read_docx(path)
            self.zero_width = read_docx.last_zero_width
        else:
            self.items, self.tables = items, len({it['tbl'] for it in items if it['tbl'] is not None})
            self.zero_width = None
        self.blocks = walk(self.items, P)
        self.F = Findings()
        s = OrderedDict()
        s['structure'] = check_structure(self.items, self.blocks, P, self.F)
        s['columns'] = check_columns(self.items, self.blocks, P, self.F)
        s['numbering'] = check_numbering(self.items, self.blocks, P, self.F)
        s['method_counts'] = check_method_counts(self.items, P, self.F)
        s['student_text'] = check_student_text(self.items, P, self.F)
        s['drill'] = check_drill(self.items, P, self.F)
        self.toc, s['toc'] = check_toc_docx(self.items, P, self.F)
        check_collateral(self.items, P, self.F)
        cc = check_copy_consistency(self.items, self.blocks, P, self.F)
        if cc is not None:
            s['copy_consistency'] = cc
        s['blue'] = check_blue(self.items, P, self.F)
        s['answer_score'] = check_answer_score(self.items, P, self.F)
        s['choice'] = check_choice(self.items, self.blocks, P, self.F)
        s['keepnext'] = check_keepnext(self.items, P, self.F)
        self.stats = s
        self.seconds = round(time.time() - t0, 2)


def load_restore_list(path):
    """本批登记“恢复原题”的题键清单：txt 每行一个题源/题键，或 JSON 列表。返回归一后的题键集合。"""
    if not path:
        return set()
    txt = Path(path).read_text(encoding='utf-8')
    try:
        keys = json.loads(txt)
    except ValueError:
        keys = [x for x in txt.splitlines() if x.strip() and not x.startswith('#')]
    return {src_key(k) for k in keys}


def run_health(docx, pdf=None, baseline=None, baseline_pdf=None, profile=None, max_items=60, restore_list=None, identity=None):
    """库入口：返回报告 dict（不写文件）。profile 可为书册名、配置路径或已加载的 dict；None 时按路径判断。"""
    T = OrderedDict()
    t0 = time.time()
    if isinstance(profile, dict):
        pd, how = profile, 'dict'
    elif profile:
        pd, how = load_profile(profile), 'arg'
    else:
        pd, how = detect_profile(docx), 'path'
        if pd is None:
            raise ValueError('无法按路径判断书册，请用 --profile 指定（可选：%s）' % '、'.join(list_profiles()))
    P = Prof(pd)
    cur = Analysis(docx, P)
    T['docx'] = cur.seconds
    F = cur.F
    docx_sha = sha256(docx)
    rep = OrderedDict()
    rep['tool'] = OrderedDict([('name', 'batch_health'), ('version', TOOL_VERSION), ('python', sys.version.split()[0])])
    rep['notice'] = NOTICE
    rep['evidence_level'] = 'machine_extracted'
    rep['profile'] = OrderedDict([('book_id', pd.get('book_id')), ('title', pd.get('title')), ('path', pd.get('_profile_path')),
                                  ('frozen', bool(pd.get('frozen'))), ('selected_by', how)])
    rep['inputs'] = OrderedDict([('docx', OrderedDict([('path', str(Path(docx).resolve())), ('sha256', docx_sha),
                                                       ('paragraphs', len(cur.items)), ('tables', cur.tables),
                                                       ('example_blocks', len(cur.blocks)),
                                                       ('zero_width_chars_removed', cur.zero_width)]))])
    texts = None
    if pdf:
        import fitz
        t1 = time.time()
        doc = fitz.open(pdf)
        scan = pdf_scan(doc, P)
        texts = pdf_pages_text(scan)
        pdf_sha = sha256(pdf)
        rep['inputs']['pdf'] = OrderedDict([('path', str(Path(pdf).resolve())), ('sha256', pdf_sha), ('pages', len(doc)),
                                            ('metadata', pdf_meta(doc))])
        F.src = 'pdf'
        cur.stats['same_version'] = check_same_version(cur.items, P, F, texts, docx, docx_sha, pdf, pdf_sha, identity)
        cur.stats['footer'] = check_footer(scan, P, F)
        cur.stats['toc'].update(check_toc_pdf(doc, cur.toc, cur.items, P, F, texts))
        cur.stats['pdf_fonts'] = check_fonts(scan, P, F)
        F.src = 'docx'
        T['pdf'] = round(time.time() - t1, 2)
    base = None
    if baseline:
        t1 = time.time()
        base = Analysis(baseline, P)
        rep['inputs']['baseline'] = OrderedDict([('path', str(Path(baseline).resolve())), ('sha256', sha256(baseline)),
                                                 ('paragraphs', len(base.items)), ('example_blocks', len(base.blocks))])
        base_f = list(base.F.items)
        if baseline_pdf:
            import fitz
            bdoc = fitz.open(baseline_pdf)
            bF = Findings()
            bF.src = 'pdf'
            bscan = pdf_scan(bdoc, P)
            check_toc_pdf(bdoc, base.toc, base.items, P, bF, pdf_pages_text(bscan))
            check_fonts(bscan, P, bF)
            check_footer(bscan, P, bF)
            base_f += bF.items
            rep['inputs']['baseline_pdf'] = OrderedDict([('path', str(Path(baseline_pdf).resolve())), ('sha256', sha256(baseline_pdf)),
                                                         ('pages', len(bdoc)), ('metadata', pdf_meta(bdoc))])
        restored = load_restore_list(restore_list)
        F.src = 'baseline'
        cur.stats['source_fidelity'], cross = check_source_vs_baseline(cur.items, cur.blocks, base.items, base.blocks, P, F, restored)
        F.src = 'docx'
        # 本批新出现、以上批另一部分同题作参照且已报差异的块：同批副本比较报的是同一件事，去掉不重复列
        dup = [f for f in F.items if f['rule'].startswith('同批副本：') and (f.get('where') or {}).get('para') in cross]
        if dup:
            ids = {id(f) for f in dup}
            F.items = [f for f in F.items if id(f) not in ids]
            cur.stats.setdefault('copy_consistency', {})['suppressed_as_reported_vs_baseline'] = len(dup)
        # 棘轮只比两边都跑过的检查：DOCX 项总比；PDF 项仅在给了 --baseline-pdf 时比；相对上批的比较项不进棘轮
        keep = {'docx', 'pdf'} if baseline_pdf else {'docx'}
        cur_f = [f for f in F.items if f['src'] in keep]
        base_f = [f for f in base_f if f['src'] in keep]
        rows = ratchet(cur_f, base_f, F)
        sf = cur.stats['source_fidelity']
        rel = [OrderedDict([('check', 'source_fidelity'), ('rule', SRC_RULES[k][0]), ('events', sf.get(k, 0)),
                            ('note', '相对上批的比较项（按段计的事件数；门9按块汇总、同题重复合并后列出）：出现即回退，不在棘轮重复计')])
               for k in ('miss', 'merge', 'merge_edit', 'split_edit', 'edit', 'img_fewer') if sf.get(k)]
        cur.stats['ratchet'] = OrderedDict([('rows', rows), ('relative_items', rel),
                                            ('regressions', dict(Counter(r['verdict'] for r in rows if r.get('verdict'))))])
        F.src = 'baseline'
        cur.stats['baseline_blocks'] = diff_blocks(block_signatures(cur.items, cur.blocks, P),
                                                   block_signatures(base.items, base.blocks, P), max_items)
        F.src = 'docx'
        T['baseline'] = round(time.time() - t1, 2)
    if texts is not None:
        locate_pages(F.items, cur.items, texts)
    # 汇总
    by = OrderedDict()
    for k in CHECK_NAMES:
        by[k] = Counter()
    for f in F.items:
        by.setdefault(f['check'], Counter())[f['level']] += 1
    not_same = any(f['check'] == 'same_version' and f['level'] == 'FAIL' for f in F.items)
    gates = []
    for k, name in CHECK_NAMES.items():
        c = by.get(k, Counter())
        ran = k in cur.stats or (k == 'source_fidelity') or (k in ('four_rights',) and cfg(pd, 'student_text.four_rights'))
        if k in ('footer', 'pdf_fonts', 'same_version') and not pdf:
            ran = False
        if k in ('ratchet', 'baseline_blocks') and not baseline:
            ran = False
        status = 'NOT_RUN' if not ran else next((lv for lv in LEVELS[:3] if c.get(lv)), 'PASS')
        g = OrderedDict([('check', k), ('name', name), ('status', status),
                         ('counts', {lv: c[lv] for lv in LEVELS if c.get(lv)})])
        if not_same and k in ('footer', 'pdf_fonts', 'toc'):
            g['note'] = 'PDF 与 DOCX 疑似非同版：本门来自 PDF 的结论不能记在本批名下'
        gates.append(g)
    rep['gates'] = gates
    tot = Counter(f['level'] for f in F.items)
    rep['summary'] = OrderedDict([('FAIL', tot['FAIL']), ('CANDIDATE', tot['CANDIDATE']), ('WARN', tot['WARN']), ('INFO', tot['INFO']),
                                  ('pass', tot['FAIL'] == 0),
                                  ('pdf_same_version', None if not pdf else not not_same),
                                  ('meaning', ('无FAIL：只说明机械层没有回退，不等于内容已审' if tot['FAIL'] == 0 else '有FAIL'))])
    rep['stats'] = cur.stats
    # 明细：每个（检查, 级别, 规则）最多 max_items 条，另给总数
    groups = OrderedDict()
    for f in F.items:
        groups.setdefault((f['check'], f['level'], f['rule']), []).append(f)
    rep['findings'] = []
    rep['findings_by_rule'] = []
    order = {k: i for i, k in enumerate(CHECK_NAMES)}
    for (ck, lv, rule), fs in sorted(groups.items(), key=lambda kv: (LEVELS.index(kv[0][1]), order.get(kv[0][0], 99))):
        rep['findings_by_rule'].append(OrderedDict([('check', ck), ('level', lv), ('rule', rule), ('count', len(fs)),
                                                    ('shown', min(len(fs), max_items))]))
        rep['findings'].extend(fs[:max_items])
    rep['config_used'] = OrderedDict([
        ('pixel_policy', cfg(pd, 'pixel.policy')),
        ('pixel_note', '本工具不做已看页复用判定；复用仍按“同页、完整像素完全一致”，放宽须用户裁定'),
        ('pdf_expected_cjk_regex', cfg(pd, 'pdf_fonts.expected_cjk_regex')),
        ('answer_score_level', cfg(pd, 'labels_rules.answer_score_level')),
        ('trailing_tag_levels', cfg(pd, 'student_text.trailing_tag_levels')),
        ('drill_layout', cfg(pd, 'drill.layout')),
        ('drill_a2_allowed', cfg(pd, 'drill.a2_allowed')),
        ('example_kind_by_labels', cfg(pd, 'example_kind_by_labels')),
        ('notsel_rule', '“不选”只在单练 A2 判断栏拦截；选择题解析里的（不选）不检查'),
        ('chain_line_rule', '不检查“【思维链条】后必须有‘链：’行”（用户已撤销）'),
        ('ratchet_rule', 'FAIL 级计数增加只记 INFO（原门已判）；CANDIDATE 级增加记 WARN；只有 keepNext 缺失这类明文计数增加才判 FAIL'),
    ])
    T['total'] = round(time.time() - t0, 2)
    rep['timing_s'] = T
    return rep


# ---------------------------------------------------------------- 输出路径守卫
def _cf(p):
    s = str(p)
    return s.casefold() if sys.platform == 'darwin' else s


def _within(child, parent):
    c, p = _cf(child).rstrip('/'), _cf(parent).rstrip('/')
    return c == p or c.startswith(p + '/')


def _is_report(p):
    try:
        with open(p, 'rb') as f:
            head = f.read(600).decode('utf-8', 'ignore')
    except OSError:
        return False
    return bool(re.search(r'"name":\s*"batch_health"', head))


def _temp_roots():
    out = []
    for d in (tempfile.gettempdir(), '/tmp', '/private/tmp', '/private/var/folders', '/var/folders'):
        try:
            out.append(Path(d).resolve())
        except OSError:
            pass
    return out


def _unsafe_out(out, inputs, prof):
    """输出路径不安全时返回原因（字符串）；冻结册目录直接经 frozen_guard 抛 SystemExit；安全返回 None。
    inputs 可以是单个 DOCX 路径（旧接口）或输入路径列表。"""
    if isinstance(inputs, (str, Path)):
        inputs = [inputs]
    o = Path(out).expanduser().resolve()
    if o.suffix.lower() != '.json':
        return '输出必须是 .json 文件'
    for p in inputs:
        if not p:
            continue
        q = Path(p).expanduser().resolve()
        if _cf(q) == _cf(o) or (o.exists() and q.exists() and os.path.samefile(q, o)):
            return f'与输入文件相同（{q.name}）'
    if o.exists():
        if not o.is_file():
            return '目标已存在且不是普通文件'
        if not _is_report(o):
            return '目标已存在且不是 batch_health 报告（不覆盖已有文件）'
    roots, frozen = [], []
    for name in list_profiles():
        try:
            pr = load_profile(name)
        except Exception:
            continue
        paths = pr.get('paths', {}) or {}
        if not paths.get('root'):
            continue
        root = Path(paths['root']).expanduser().resolve()
        roots.append(root)
        if pr.get('frozen'):
            dirs = [resolve(pr, paths[k]).resolve() for k in ('workspace', 'aux_workspace', 'review_entry', 'review_history') if paths.get(k)]
            ck = pr.get('collab_key')
            hit = any(_within(o, d) for d in dirs)
            if not hit and ck and _within(o, root) and _cf(o) != _cf(root):
                rel = Path(_cf(o)[len(_cf(root).rstrip('/')) + 1:])
                hit = bool(rel.parts) and _cf(ck) in rel.parts[0]
            if hit:
                frozen.append(pr)
    for pr in frozen:
        frozen_guard(pr, '写出体检报告到本册目录')
    for r in cfg(prof, 'output_guard.protected_roots', []) or []:
        roots.append(Path(r).expanduser().resolve())
    roots.append(Path(__file__).resolve().parent.parent)          # 本 Skill 目录
    if any(_within(o, t) for t in _temp_roots()):
        return None
    allow = re.compile(cfg(prof, 'output_guard.allowed_subpath_regex') or r'/协作/候选/[^/]+/[^/]+/构建/体检(/|$)')
    for r in roots:
        if _within(o, r):
            rel = '/' + _cf(o)[len(_cf(r).rstrip('/')) + 1:]
            if not allow.search(str(Path(rel).parent) + '/'):
                return f'落在受保护目录 {r} 内（只允许 …/协作/候选/<谁>/<批次>/构建/体检/ 或系统临时目录）'
    par = o.parent
    if par.is_dir():
        try:
            near = [x.name for x in par.iterdir() if x.suffix.lower() in ('.docx', '.pdf') and not x.name.startswith('~$')]
        except OSError:
            near = []
        if near:
            return f'目标目录里有书稿/PDF（{near[0]} 等），不把体检写到书稿旁边'
    return None


def print_summary(rep):
    s = rep['stats']
    d = rep['inputs']['docx']
    line = f"[{rep['profile']['book_id']}] 段落 {d['paragraphs']}｜例题块 {d['example_blocks']}"
    if 'pdf' in rep['inputs']:
        line += f"｜PDF {rep['inputs']['pdf']['pages']} 页"
    print(line)
    for g in rep['gates']:
        c = g['counts']
        extra = '，'.join(f'{k}{v}' for k, v in c.items())
        print(f"  {g['status']:<9} {g['name']}" + (f'（{extra}）' if extra else ''))
    top = [r for r in rep['findings_by_rule'] if r['level'] in ('FAIL', 'CANDIDATE')][:14]
    for r in top:
        print(f"    - {r['level']} {r['check']}：{r['rule']} ×{r['count']}")
    if 'baseline_blocks' in s:
        print('  对上批例题块/单练行：', s['baseline_blocks']['totals'])
    print(f"  合计 FAIL {rep['summary']['FAIL']}｜CANDIDATE {rep['summary']['CANDIDATE']}｜WARN {rep['summary']['WARN']}"
          f"｜用时 {rep['timing_s']['total']} 秒")
    print('  ' + NOTICE)


def main(argv=None):
    ap = argparse.ArgumentParser(description='每批体检（按书册配置运行，只读）。详见文件开头说明。',
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docx', required=True, help='本批 DOCX（只读）')
    ap.add_argument('--pdf', help='本批同版 PDF（只读）：同版核对、页脚、目录落页、字体回退')
    ap.add_argument('--baseline', help='上一批 DOCX（只读）：题面零改写、回退棘轮、例题块差异')
    ap.add_argument('--baseline-pdf', help='上一批 PDF（可选）：让字体回退、页脚也进棘轮')
    ap.add_argument('--profile', help='书册名（如 bixiu3）或配置文件路径；缺省按 DOCX 路径判断')
    ap.add_argument('--identity', help='同版身份.json（可选）；缺省在 PDF/DOCX 所在目录及上两级查找')
    ap.add_argument('--out', help='输出 JSON 路径；缺省写到系统临时目录。受保护目录内只允许 …/协作/候选/<谁>/<批次>/构建/体检/')
    ap.add_argument('--source-restore-list', help='本批登记“恢复原题”的题键清单（txt 每行一个或 JSON 列表）；这些题键的题面差异降为 INFO')
    ap.add_argument('--max-items', type=int, default=60, help='每条规则最多列出多少条明细（计数不受影响），默认 60')
    ap.add_argument('--quiet', action='store_true', help='只打印结论行')
    a = ap.parse_args(argv)
    ins = [a.docx, a.pdf, a.baseline, a.baseline_pdf, a.source_restore_list, a.identity]
    for f in ins:
        if f and not Path(f).is_file():
            print('找不到文件：', f, file=sys.stderr)
            return 2
    out = Path(a.out) if a.out else Path(tempfile.gettempdir()) / (Path(a.docx).stem + '.体检.json')
    try:
        pd = load_profile(a.profile) if a.profile else detect_profile(a.docx)
    except Exception as e:
        print('配置读取失败：', e, file=sys.stderr)
        return 2
    if pd is None:
        print('无法按路径判断书册，请用 --profile 指定（可选：%s）' % '、'.join(list_profiles()), file=sys.stderr)
        return 2
    try:
        why = _unsafe_out(out, ins, pd)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 3
    if why:
        print(f'拒绝写出 {out}：{why}。请用 --out 指到临时目录或 …/构建/体检/。', file=sys.stderr)
        return 3
    out = out.expanduser().resolve()
    if out.exists():
        out.unlink()          # 守卫已确认是旧体检报告：先删，崩溃时不留下上次的结论
    try:
        rep = run_health(a.docx, a.pdf, a.baseline, a.baseline_pdf, pd, a.max_items, a.source_restore_list, a.identity)
    except Exception as e:  # noqa: BLE001  任何崩溃都按“输入或运行错误”退出 2，不写报告
        print('输入、配置或运行错误（未写报告）：', type(e).__name__, e, file=sys.stderr)
        return 2
    rep['output'] = str(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name('.' + out.name + f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(rep, ensure_ascii=False, indent=1, default=list), encoding='utf-8')
    os.replace(str(tmp), str(out))
    if a.quiet:
        print(f"{'PASS' if rep['summary']['pass'] else 'FAIL'} FAIL={rep['summary']['FAIL']} CANDIDATE={rep['summary']['CANDIDATE']} "
              f"WARN={rep['summary']['WARN']} → {out}")
    else:
        print_summary(rep)
        print('明细：', out)
    return 0 if rep['summary']['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
