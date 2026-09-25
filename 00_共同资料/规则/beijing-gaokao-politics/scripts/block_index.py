#!/usr/bin/env python3
"""题块索引：按书册配置把宝典 DOCX 导出为题块索引，可附 PDF 页码，可按题键/节点抽出题块原文切片。

用途
  1. 索引：每个例题块的部分、节点、考法、题型、编号、题源、题键、各栏目有无、正文哈希、
     document.xml 段落序号范围；题肢单练（附录）逐行索引。
  2. --pdf：给每个题块/题肢/标题附 PDF 页码（题块→页码、页码→题块双向，每页附所在标题上下文），
     并查同版登记、用 PDF 书签大纲自检。
  3. --extract / --where：按题键、题源、节点、题块号、页码选出题块，输出原文切片或位置，
     给子代理读，免得每个子代理自己翻整本 DOCX、每轮临时写 fitz 定位脚本。

用法
  python3 block_index.py --docx 本批.docx [--profile bixiu3] [--pdf 本批.pdf] [--out 索引.json]
  python3 block_index.py --docx 本批.docx --pdf 本批.pdf --where --key BJ-2024-CY-ERMO-Q18
  python3 block_index.py --docx 本批.docx --extract --node 人民代表大会 --extract-out 切片.md
  python3 block_index.py --docx 本批.docx --pdf 本批.pdf --where --page 45 --page 46
  python3 block_index.py --docx x.docx --pdf x.pdf --binding 同版身份.json   # 同版记录不在默认查找位置时显式给出
  作为模块：from block_index import build_index; idx = build_index(docx, prof, pdf=None)

口径
  - 段落序号 p = lxml `list(body.iter(w:p))` 的 0 起下标（含表格内、文本框内段落；mc:Fallback 内的
    重复段落计入序号但不计入正文）；body = w:body 顶层子元素下标。
  - 栏目只数段首（含软回车后行首）的【…】标签。紧跟句号等句末标点写在行中的同名栏目标签单列为
    missing_inline（“标签在行中”，不算缺栏）；配置 labels_inline=true 时计入栏目。
  - 题键由标题文字机器解析（key_by=标题解析（机器）），不代表已核原卷；本工具不判证据等级。
    “YYYY—YYYY学年”写法不自行推年份（key 留空，key_note 列题库同学年候选）；题库 questions/ 下没有的卷
    在 key_note 标“题库无此卷”。
  - batch_key 是批内唯一键（“部分|题型|题源 #出现序号”），增删一处落位后序号会移动，不能跨批对齐；
    跨批配对请用 align_key（部分|题型|题源|节点）加 body_sha1。
  - 页码为 PDF 物理页（第1页=封面），靠 DOCX 段落文字与 PDF 文字层对位得到。
    同版判定只认同版登记：同一条 JSON 记录里 docx 角色 SHA 与 pdf 角色 SHA 同时等于这对文件
    （如 docx_sha256+pdf_sha256，或 rendered_from_docx_sha256+pdf_sha256）。只命中一个 SHA 不算。
    登记里本 DOCX 对应另一份 PDF、或这份 PDF 登记为另一份 DOCX 的渲染时，另报“很可能不同版”。
    对位率、标题对上比例、书签大纲只是辅助信号：第51/52批互配时对位率仍有 90.6%–91.5%、已比对的大纲项全部一致，
    单靠它们判不了近版错配。
  - 抽取只截取原文，不改写、不归纳；--max-chars 截断处写明截断。
  - 机械层全过只说明结构没有回退，不代表内容已审。

只读承诺：只用 zipfile 读 DOCX、fitz 读 PDF、只读 JSON 查同版登记与题库卷目录，不修改、移动、重存任何输入；
输出默认写系统临时目录。拒绝写到：书稿所在目录、各登记书册的工作区/审阅入口/历史目录/协作目录/状态目录、
题库根、项目根、_house.json output_guard.protected_roots 所列根（书稿/题源/Skill）、Skill 母版（含 profiles/）；
目标属于冻结册时经该册 frozen_guard 拒绝；临时目录以外，目标目录里有 .docx/.pdf 时拒绝，目标文件已存在且不是
本工具以前的产物时拒绝覆盖。与 batch_health 不同，本工具不放行“…/构建/体检/”子目录（索引不是体检报告）。
退出码：0 正常；1 已生成索引但有需注意项（未确认同版、PDF 对位率低、大纲不一致、切出 0 块、选择器无匹配）；
2 输入/参数错误（DOCX/PDF 损坏、为空、参数非法）、拒绝写入或内部错误。
"""
import sys
sys.dont_write_bytecode = True  # 不在 Skill 母版 scripts/ 里留下 __pycache__

import argparse, bisect, csv, glob, hashlib, json, re, tempfile, time, traceback, unicodedata, zipfile
from collections import Counter, OrderedDict
from pathlib import Path
from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import load_profile, list_profiles, resolve, frozen_guard, PROFILE_DIR  # noqa: E402

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
MC = '{http://schemas.openxmlformats.org/markup-compatibility/2006}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
V = '{urn:schemas-microsoft-com:vml}'
PKG_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'

LABEL_AT = re.compile(r'^\s*(【[^】\n]{1,16}】)')
LABEL_ANY = re.compile(r'【[^】\n]{1,16}】')
INLINE_AFTER = '。．.！？!?；;'  # 行中栏目标签须紧跟这些句末标点（可隔空白）
ALIGN_MIN = 4          # 签名短于此长度的段落不参与对位
ALIGN_PROBE = 24       # 对位探针长度
ALIGN_FAIL = 0.90      # 低于此值：PDF 大概率不是这份 DOCX 的渲染
ALIGN_NEAR = 0.97      # 低于此值：可能是相邻版本（同版实测 98.3%–100%，近版错配实测 90.6%–91.5%）
NOTE = ('本索引是机器按书册配置切出的结构索引：题型、题源、题键均由标题/样式推断，未核原卷；'
        '栏目缺失或重复只是候选，是否缺陷由主代理判断；机械层全过只说明结构没有回退。')
SKILL_DIR = Path(__file__).resolve().parent.parent
# 书稿、题源原件所在根（未登记为书册配置的其他册也在这里）；配置可用 paths.protected_roots 追加
PROTECTED_GLOBS = ['~/GaokaoPolitics', '~/Desktop/20*模拟题*', '~/Desktop/历年高考题及细则', '~/.codex/skills']

# ---------------------------------------------------------------- 题键解析
REGION = {'海淀': 'HD', '西城': 'XC', '东城': 'DC', '朝阳': 'CY', '丰台': 'FT', '石景山': 'SJS', '顺义': 'SY',
          '昌平': 'CP', '房山': 'FS', '门头沟': 'MTG', '延庆': 'YQ', '通州': 'TZ', '大兴': 'DX', '平谷': 'PG',
          '怀柔': 'HR', '密云': 'MY'}
STAGE = {'一模': 'YIMO', '二模': 'ERMO', '期末': 'QIMO', '期中': 'QIZHONG', '高考': 'GAOKAO'}
# 书稿写法与题库卷身份不一致的具名别名（依据题库 HD2023 identity_report：2022—2023第二学期期中练习=海淀一模）。
# 配置可用 sources.key_aliases 覆盖/追加：{"2023|海淀|期中|下": "BJ-2023-HD-YIMO"}
KEY_ALIASES = {'2023|海淀|期中|下': 'BJ-2023-HD-YIMO', '2023|海淀|期中|上': 'BJ-2023-HD-QIZHONG'}
_RG = '|'.join(sorted(REGION, key=len, reverse=True))
KEY_RX = re.compile(
    r'(?P<y>20\d{2})(?:[—\-–~至](?P<y2>20\d{2})学年(?:度)?(?:第[一二]学期)?)?年?(?:北京市?)?(?P<reg>' + _RG + r')?区?'
    r'(?P<stg>一模|二模|期末|期中|高考)(?:练习|考试|检测)?(?:[（(](?P<half>[上下])[）)])?(?:卷|试题|试卷)?'
    r'(?:非?选择题?|主观题?|单选题?)?第?(?P<q>\d{1,2})(?:[（(](?P<sq1>\d{1,2})[）)])?题?'
    r'(?:[·・,，、]?第?[（(](?P<sq2>\d{1,2})[）)]问?)?')
BANK_KEY_RX = re.compile(r'BJ-20\d\d-[A-Z]{2,3}-(?:YIMO|ERMO|QIMO|QIZHONG|GAOKAO)-Q\d{1,2}')
_BANK_CACHE = {}


def bank_index(prof):
    """题库卷身份（只读）：questions/ 下的卷目录名，及 indexes/exams.csv 的学年登记。取不到返回 None。"""
    rel = (((prof or {}).get('sources') or {}).get('bank') or {}).get('root')
    if not rel or not ((prof.get('paths') or {}).get('root') or Path(str(rel)).expanduser().is_absolute()):
        return None
    try:
        root = resolve(prof, rel)
    except (KeyError, TypeError):
        return None
    key = str(root)
    if key in _BANK_CACHE:
        return _BANK_CACHE[key]
    qd = root / 'questions'
    if not qd.is_dir():
        _BANK_CACHE[key] = None
        return None
    exams = {p.name for p in qd.iterdir() if p.is_dir() and p.name.startswith('BJ-')}
    by_sy = {}
    ec = root / 'indexes' / 'exams.csv'
    if ec.is_file():
        try:
            with open(ec, encoding='utf-8-sig', newline='') as f:
                for row in csv.DictReader(f):
                    sy = re.sub(r'\D', '', row.get('school_year') or '')
                    if len(sy) == 8 and (row.get('exam_id') or '').startswith('BJ-'):
                        by_sy.setdefault((sy, row.get('region') or '', row.get('stage') or ''), []).append(row['exam_id'])
        except (OSError, csv.Error):
            pass
    _BANK_CACHE[key] = {'root': key, 'exams': exams, 'by_school_year': by_sy}
    return _BANK_CACHE[key]


def parse_keys(src, aliases=None, bank=None):
    """从题源文字解析题库题键；返回 [{key, subq, raw, note, in_bank}]，key 可为 None（如学年写法）。"""
    al = dict(KEY_ALIASES)
    al.update(aliases or {})
    s = re.sub(r'\s+', '', src or '')
    out = []
    for m in BANK_KEY_RX.finditer(s):
        exam = m.group(0).rsplit('-Q', 1)[0]
        out.append({'key': m.group(0), 'subq': None, 'raw': m.group(0), 'note': None,
                    'in_bank': (exam in bank['exams']) if bank else None})
    for m in KEY_RX.finditer(s):
        y, y2, reg, stg, half = m.group('y'), m.group('y2'), m.group('reg'), m.group('stg'), m.group('half')
        q, subq = int(m.group('q')), m.group('sq1') or m.group('sq2')
        if y2:
            # 学年写法不推年份：题库里同一学年同区同类可能登记了两套卷（如海淀期中 2024/2025 都记 2024—2025 学年）
            note = f'学年写法（{y}—{y2}学年）不自行推年份，未给题键'
            if bank and reg:
                cands = bank['by_school_year'].get((y + y2, reg, stg), [])
                if cands:
                    note += '；题库同学年同区同类卷：' + '、'.join(f'{c}-Q{q}' for c in sorted(cands)) + '（候选，需核）'
            out.append({'key': None, 'subq': subq, 'raw': m.group(0), 'note': note, 'in_bank': None})
            continue
        note = None
        if stg == '高考':
            exam = f'BJ-{y}-BJ-GAOKAO'
        elif reg:
            ak = f'{y}|{reg}|{stg}|{half or ""}'
            exam = al.get(ak) or f'BJ-{y}-{REGION[reg]}-{STAGE[stg]}'
            if ak in al:
                note = '按具名别名映射'
        else:
            continue
        in_bank = (exam in bank['exams']) if bank else None
        if in_bank is False:
            note = (note + '；' if note else '') + '题库无此卷'
        out.append({'key': f'{exam}-Q{q}', 'subq': subq, 'raw': m.group(0), 'note': note, 'in_bank': in_bank})
    return out


# ---------------------------------------------------------------- 基础工具
def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def sig(t):
    """对位签名：NFKC 后只留文字、字母、数字（去空白与标点，容忍 PDF 断行与全半角差异）。"""
    return ''.join(ch for ch in unicodedata.normalize('NFKC', t or '') if ch.isalnum())


def squash(t):
    return re.sub(r'\s+', '', t or '')


def _sym_char(el):
    c = el.get(W + 'char') or ''
    try:
        v = int(c, 16)
    except ValueError:
        return '〔符号〕'
    if 0xF000 <= v <= 0xF0FF:  # 符号字体私用区，字形取决于字体，不猜
        return f'〔符号:{c}〕'
    return chr(v)


def _own(el, out, media):
    """收集段落自身文字（不进嵌套段落、不进 mc:Fallback）；顺带收集图片 rId。"""
    for ch in el:
        tag = ch.tag
        if not isinstance(tag, str) or tag == W + 'p' or tag == MC + 'Fallback':
            continue
        if tag == W + 't':
            out.append(ch.text or '')
        elif tag == W + 'tab' or tag == W + 'ptab':
            out.append('\t')
        elif tag in (W + 'br', W + 'cr'):
            out.append('\n')
        elif tag == W + 'noBreakHyphen':
            out.append('-')
        elif tag == W + 'sym':
            out.append(_sym_char(ch))
        elif tag in (W + 'instrText', W + 'delText', W + 'rPr', W + 'pPr'):
            continue
        elif tag == A + 'blip':
            rid = ch.get(R + 'embed') or ch.get(R + 'link')
            if rid:
                media.append(rid)
        elif tag == V + 'imagedata':
            rid = ch.get(R + 'id')
            if rid:
                media.append(rid)
        else:
            _own(ch, out, media)


class InputError(Exception):
    """输入文件不可读（损坏、为空、缺部件）；main 统一转成退出码 2。"""


def check_docx(path):
    try:
        z = zipfile.ZipFile(path)
        names = set(z.namelist())
    except (zipfile.BadZipFile, OSError) as e:
        raise InputError(f'DOCX 不是有效的 Word 压缩包（可能为空或损坏）：{path}（{e}）')
    miss = [n for n in ('word/document.xml', 'word/styles.xml') if n not in names]
    if miss:
        raise InputError(f'DOCX 缺少必要部件 {miss}：{path}')
    try:
        etree.fromstring(z.read('word/document.xml'))
        etree.fromstring(z.read('word/styles.xml'))
    except (etree.XMLSyntaxError, zipfile.BadZipFile, OSError) as e:
        raise InputError(f'DOCX 内的 XML 无法解析：{path}（{e}）')


def check_pdf(path):
    import fitz
    try:
        d = fitz.open(path)
        n = d.page_count
        d.close()
    except (RuntimeError, ValueError, OSError) as e:  # fitz.FileDataError/EmptyFileError 均派生自 RuntimeError
        raise InputError(f'PDF 无法打开（可能为空或损坏）：{path}（{type(e).__name__}: {e}）')
    if n < 1:
        raise InputError(f'PDF 没有页面：{path}')


# ---------------------------------------------------------------- 读 DOCX
def load_docx(path):
    """返回 {'styles','default_style','paras','rels','media_sha1','n_body'}；paras 为全部 w:p 的记录。"""
    z = zipfile.ZipFile(path)
    names, default = {}, None
    for st in etree.fromstring(z.read('word/styles.xml')).iter(W + 'style'):
        n = st.find(W + 'name')
        sid = st.get(W + 'styleId')
        names[sid] = n.get(W + 'val') if n is not None else sid
        if st.get(W + 'type') == 'paragraph' and st.get(W + 'default') in ('1', 'true'):
            default = names[sid]
    rels = {}
    try:
        for r in etree.fromstring(z.read('word/_rels/document.xml.rels')).iter(PKG_REL + 'Relationship'):
            rels[r.get('Id')] = r.get('Target')
    except KeyError:
        pass
    body = etree.fromstring(z.read('word/document.xml')).find(W + 'body')
    if body is None:
        body = etree.Element(W + 'body')
    tbl_list = list(body.iter(W + 'tbl'))  # 保持代理对象存活，id() 才稳定
    tbl_no = {id(t): i + 1 for i, t in enumerate(tbl_list)}
    paras = []
    for bi, child in enumerate(body):
        for p in child.iter(W + 'p'):
            anc = list(p.iterancestors())
            fallback = any(a.tag == MC + 'Fallback' for a in anc)
            txbx = any(a.tag == W + 'txbxContent' for a in anc)
            tbl = row = col = None
            for a in anc:
                if a.tag == W + 'tc' and col is None:
                    col = sum(1 for s in a.itersiblings(W + 'tc', preceding=True))
                elif a.tag == W + 'tr' and row is None:
                    row = sum(1 for s in a.itersiblings(W + 'tr', preceding=True))
                elif a.tag == W + 'tbl':
                    tbl = tbl_no.get(id(a))
                    break
            ps = p.find(f'{W}pPr/{W}pStyle')
            style = names.get(ps.get(W + 'val'), ps.get(W + 'val')) if ps is not None else (default or '(默认)')
            buf, media = [], []
            _own(p, buf, media)
            text = ''.join(buf)
            hl = p.find(W + 'hyperlink')
            instr = ''.join(t.text or '' for t in p.iter(W + 'instrText'))
            colors = {(c.get(W + 'val') or '').upper() for c in p.iter(W + 'color')} - {''}
            ppr = p.find(W + 'pPr')
            paras.append({
                'p': len(paras), 'body': bi, 'style': style, 'text': text, 'explicit_style': ps is not None,
                'keep_next': ppr is not None and ppr.find(W + 'keepNext') is not None,
                'page_break_before': ppr is not None and ppr.find(W + 'pageBreakBefore') is not None,
                'tbl': tbl, 'row': row, 'col': col, 'txbx': txbx, 'fallback': fallback,
                'media': media, 'anchor': hl.get(W + 'anchor') if hl is not None else None,
                'bookmarks': [b.get(W + 'name') for b in p.iter(W + 'bookmarkStart')],
                'instr': instr, 'colors': sorted(colors),
                'outline': (p.find(f'{W}pPr/{W}outlineLvl').get(W + 'val')
                            if p.find(f'{W}pPr/{W}outlineLvl') is not None else None),
            })
    media_sha = {}
    for rid, tgt in rels.items():
        if tgt and tgt.startswith('media/'):
            try:
                media_sha[rid] = hashlib.sha1(z.read('word/' + tgt)).hexdigest()
            except KeyError:
                media_sha[rid] = None
    return {'styles': names, 'default_style': default, 'paras': paras, 'rels': rels,
            'media_sha1': media_sha, 'n_body': len(body)}


# ---------------------------------------------------------------- 配置适配
class BookCfg:
    """把书册配置翻成切块所需的规则；配置缺的字段给默认值（见 FIELDS_WITH_DEFAULTS）。"""

    def __init__(self, prof):
        self.prof = prof
        S = prof.get('styles', {})
        g = lambda k, d=(): set(S.get(k, list(d)) if isinstance(S.get(k, list(d)), list) else [S.get(k)])
        self.h1, self.h2 = g('h1', ['heading 1']), g('h2', ['heading 2'])
        self.example_styles = g('example_title')
        self.group, self.method = g('group_heading'), g('method')
        self.node_styles = g('method_desc') | g('category_line') | g('trigger_box')
        self.toc = g('toc')
        self.drill_group = g('drill_group')
        self.titles = []
        for t in prof.get('example_titles', []):
            self.titles.append({'kind': t['kind'], 'rx': re.compile(t['regex']),
                                'styles': set(t.get('styles', [])) or None, 'numbered': t.get('numbered', True)})
        self.title_styles = self.example_styles | {s for t in self.titles if t['styles'] for s in t['styles']}
        self.parts = [dict(p, _rx=re.compile(p['match'])) for p in prof.get('structure', {}).get('parts', [])
                      if p.get('match')]
        # 结束上一题块的普通段落（如专题里“▪ 小标题”），与 batch_health 同一口径
        self.block_end = [(set(b.get('styles', [])), re.compile(b['regex']))
                          for b in prof.get('structure', {}).get('block_end', []) if b.get('regex')]
        self.schemas = prof.get('column_schemas', {})
        self.section_labels = set(prof.get('section_labels', []))
        self.drill = prof.get('drill') or {}
        lr = prof.get('labels_rules') or {}
        self.rubric_labels = set(lr.get('rubric_labels') or [])
        self.labels_inline = bool(lr.get('labels_inline', False))
        # 可选字段：题型按栏目标签改判（哲学、选必一等主观/选择都叫“例题N”）
        self.kind_by_labels = prof.get('example_kind_by_labels') or {}
        self.key_aliases = (prof.get('sources') or {}).get('key_aliases') or {}
        self.bank = bank_index(prof)
        mc = prof.get('method_count') or {}
        self.count_rx = re.compile(mc['regex']) if mc.get('regex') else None
        f = prof.get('footer') or {}
        self.footer_rx = re.compile(f.get('regex') or r'^\s*[—\-–]*\s*\d{1,4}\s*[—\-–]*\s*$')
        d = self.drill
        self.drill_src_rx = re.compile(d.get('source_line_regex') or
                                       r'^\s*20\d\d\s*年?.{0,16}?(?:高考|一模|二模|期末|期中|适应性|练习).{0,16}?第\s*\d{1,2}\s*题.{0,24}$')
        self.drill_src_styles = set(d.get('source_styles') or [])
        self.boundary = self.h1 | self.h2 | self.group | self.method | self.node_styles | self.toc | self.title_styles

    def part_of(self, h1text):
        for p in self.parts:
            if p['_rx'].search(h1text):
                return p
        return {'id': '(未配置)', 'schema': {}}

    def title_of(self, r):
        if r['tbl'] or r['txbx'] or r['style'] not in self.title_styles:
            return None
        t = r['text'].replace('\n', ' ').strip()
        for d in self.titles:
            if d['styles'] is not None:
                if r['style'] not in d['styles']:
                    continue
            elif r['style'] not in self.example_styles:
                continue
            m = d['rx'].match(t)
            if m:
                gi = d['rx'].groupindex
                num = int(m.group('num')) if 'num' in gi and m.group('num') else None
                src = m.group('src').strip() if 'src' in gi and m.group('src') else ''
                return d['kind'], num, src, d['numbered']
        return None


FIELDS_WITH_DEFAULTS = {
    'example_kind_by_labels': '题型按栏目标签改判，如 {"choice": ["【错肢分析】"], "_apply_to": ["subjective"]}；缺省不改判（哲学/选必一等主观与选择同叫“例题N”时需要）',
    'sources.key_aliases': '书稿题源写法→题库卷身份的具名别名，缺省只含 2023海淀期中（上/下）两条',
    'labels_rules.labels_inline / column_schemas.*.labels_inline': '紧跟句末标点写在行中的栏目标签是否计入栏目；缺省 false（单列为 missing_inline，不算缺栏）',
    'drill.layout=paragraph': '段落式单练（错肢训练/错肢纠正）按 item_regex 取条目、按所在二级标题分 A1/A2',
    'drill.a2_heading': 'A2 所在二级标题（段落式单练用；缺省＝不是 A1 标题的都算 A2）',
    'drill.source_line_regex / drill.source_styles': '段落式单练里条目前的题源行（如文化“2020年北京高考第1题”）；缺省按“20xx…第N题”短行识别',
    'paths.protected_roots': '本册额外拒绝写入的根目录（可选）；共用的 _house.json output_guard.protected_roots 已读取，'
                             '代码另含 ~/GaokaoPolitics、~/Desktop/20*模拟题*、~/Desktop/历年高考题及细则、~/.codex/skills',
    'same_version.title_found_min': '标题对上比例阈值，读 _house.json（与 batch_health 同），缺省 0.98',
}


# ---------------------------------------------------------------- 切块
def _labels_in(text):
    out = []
    for line in text.split('\n'):
        m = LABEL_AT.match(line)
        if m:
            out.append(m.group(1))
    return out


def _labels_inline(text):
    """行中（非行首）且紧跟句末标点的【…】标签，如“【答案】 D。【解析】 …”里的【解析】。"""
    out = []
    for line in text.split('\n'):
        for m in LABEL_ANY.finditer(line):
            pre = line[:m.start()].rstrip(' \t　')
            if pre and pre[-1] in INLINE_AFTER:
                out.append(m.group(0))
    return out


def walk(doc, cfg):
    """切出例题块、题肢条目和标题大纲。"""
    blocks, drill_rows, heads = [], OrderedDict(), []
    part = cfg.part_of('(前置)')
    ctx = {'h1': '', 'h2': '', 'group': '', 'method': ''}
    cur = None
    drill_group, drill_h2, last_item, pending_src = '', '', None, None
    item_rx = re.compile(cfg.drill.get('item_regex') or r'^(\d+)[、.．]\s*(.*)$', re.S)
    marker = cfg.drill.get('correction_marker', '纠正：')
    stats = Counter()

    def close():
        nonlocal cur
        if cur is not None:
            blocks.append(cur)
            cur = None

    for r in doc['paras']:
        if r['fallback']:
            continue
        t = r['text'].strip()
        st = r['style']
        if r['tbl'] is not None:
            if part.get('drill') and cfg.drill.get('layout', 'table3') == 'table3':
                key = (r['tbl'], r['row'])
                row = drill_rows.setdefault(key, {'cells': {}, 'group': drill_group, 'h2': drill_h2,
                                                  'body': r['body'], 'p': []})
                row['cells'].setdefault(r['col'], []).append(r)
                row['p'].append(r['p'])
            elif cur is not None:
                cur['_recs'].append(r)
            continue
        if st in cfg.h1 and t:
            close()
            part = cfg.part_of(t)
            ctx = {'h1': t, 'h2': '', 'group': '', 'method': ''}
            heads.append({'level': 'h1', 'text': t, 'p': r['p'], 'part': part['id']})
            continue
        if st in cfg.h2 and t:
            close()
            ctx.update(h2=t, group='', method='')
            drill_h2, last_item, pending_src = t, None, None
            heads.append({'level': 'h2', 'text': t, 'p': r['p'], 'part': part['id']})
            continue
        if st in cfg.toc:
            close()
            stats['toc_paras'] += 1
            continue
        if part.get('drill'):
            if st in cfg.drill_group and t:
                drill_group, last_item, pending_src = t, None, None
            elif cfg.drill.get('layout', 'table3') != 'table3' and t:
                # 段落式单练：条目段起一条，其后的非条目段（纠正等）挂到这一条；条目前的题源行记为下一条的来源
                if item_rx.match(t):
                    # 题源行对其后各条都有效（同一道题可出多条题肢），到下一题源行、分组或二级标题为止
                    last_item = {'cells': {0: [r]}, 'group': drill_group, 'h2': drill_h2,
                                 'body': r['body'], 'p': [r['p']], 'src_line': pending_src}
                    drill_rows[('para', r['p'])] = last_item
                elif (not t.startswith(marker) and len(t) <= 60 and cfg.drill_src_rx.match(t)
                      and (not cfg.drill_src_styles or st in cfg.drill_src_styles)):
                    pending_src, last_item = t, None
                elif last_item is not None:
                    last_item['cells'].setdefault(1, []).append(r)
                    last_item['p'].append(r['p'])
            continue
        ti = cfg.title_of(r)
        if ti:
            close()
            kind, num, src, numbered = ti
            kind = part.get('kind_override', {}).get(kind, kind)
            cur = {'kind': kind, 'num': num, 'src': src, 'numbered': numbered, 'title': t, 'style': st,
                   'part': part['id'], '_partdef': part, 'h1': ctx['h1'], 'h2': ctx['h2'], 'group': ctx['group'],
                   'method': ctx['method'], 'p0': r['p'], 'body0': r['body'], '_recs': [], '_title_rec': r}
            continue
        if t and st in cfg.method:
            close()
            ctx['method'] = t
            heads.append({'level': 'method', 'text': t, 'p': r['p'], 'part': part['id']})
            continue
        if t and (st in cfg.group or st in cfg.title_styles):
            close()
            ctx['group'] = t
            heads.append({'level': 'group', 'text': t, 'p': r['p'], 'part': part['id']})
            continue
        if t and (st in cfg.node_styles or (_labels_in(t)[:1] and _labels_in(t)[0] in cfg.section_labels)):
            close()
            stats['node_level_paras'] += 1
            continue
        if t and cur is not None and any((not sts or st in sts) and rx.search(t) for sts, rx in cfg.block_end):
            close()
            stats['block_end_paras'] += 1
            continue
        if cur is not None:
            cur['_recs'].append(r)
        elif t:
            stats['outside_paras'] += 1
    close()
    return blocks, drill_rows, heads, stats


def _exempt(src, prof, ref):
    """ref 形如 'sources.no_e1_exceptions'：题源含整卷名或具名题即豁免。"""
    node = prof
    for k in ref.split('.'):
        node = (node or {}).get(k) if isinstance(node, dict) else None
    if not isinstance(node, dict):
        return False
    s = squash(src)
    return (any(squash(w) and squash(w) in s for w in node.get('whole_papers', []))
            or any(squash(q) and squash(q) in s for q in node.get('questions', [])))


def _is_rubric(L, cfg):
    return L in cfg.rubric_labels or '细则' in L


def finish_blocks(blocks, doc, cfg):
    occ = Counter()
    out = []
    for i, b in enumerate(blocks, 1):
        recs = b.pop('_recs')
        trec = b.pop('_title_rec')
        partdef = b.pop('_partdef')
        texts = [r['text'].strip() for r in recs if r['text'].strip()]
        labels, inline = Counter(), Counter()
        for r in recs:
            labels.update(_labels_in(r['text']))
            inline.update(_labels_inline(r['text']))
        # 题型按栏目改判（仅当配置给出；只改 _apply_to 里的题型，缺省只改 subjective）
        apply_to = cfg.kind_by_labels.get('_apply_to') or ['subjective']
        for k, labs in cfg.kind_by_labels.items():
            if k.startswith('_') or b['kind'] not in apply_to:
                continue
            if any(labels.get(L) for L in labs):
                b['kind'] = k
                break
        sname = (partdef.get('schema') or {}).get(b['kind'])
        sc = cfg.schemas.get(sname) if sname else None
        cols, missing, repeated, exempted, miss_inline = OrderedDict(), [], [], [], []
        if sc:
            use_inline = bool(sc.get('labels_inline', cfg.labels_inline))
            cnt = lambda L: labels.get(L, 0) + (inline.get(L, 0) if use_inline else 0)
            for L in sc.get('labels', []):
                n = cnt(L)
                cols[L] = n
                if n == 0 and L not in sc.get('optional', []):
                    (miss_inline if inline.get(L) else missing).append(L)
                if n > 1 and sc.get('mode', 'each_once') == 'each_once' and L not in sc.get('repeatable', []):
                    repeated.append(L)
            for grp in sc.get('require_one_of', []):
                present = [L for L in grp if cnt(L)]
                for L in grp:
                    cols[L] = cnt(L)
                if not present:
                    (miss_inline if any(inline.get(L) for L in grp) else missing).append('|'.join(grp))
                elif len(present) > 1:
                    repeated.append('+'.join(present))
            # 具名例外（无 E1 例外名单里的卷/题）只豁免细则类栏目，其余缺栏照常列为候选
            if missing and sc.get('exempt_if_source_in') and _exempt(b['src'], cfg.prof, sc['exempt_if_source_in']):
                exempted = [L for L in missing if _is_rubric(L, cfg)]
                missing = [L for L in missing if L not in exempted]
        other = {L: n for L, n in labels.items() if L not in cols}
        media = [m for r in [trec] + recs for m in r['media']]
        msha = [doc['media_sha1'].get(m) or '' for m in media]
        pk = parse_keys(b['src'], cfg.key_aliases, cfg.bank)
        keys = [k for k in pk if k['key']]
        base = (b['part'], b['kind'], squash(b['src']))
        occ[base] += 1
        last = recs[-1] if recs else trec
        tables = sorted({r['tbl'] for r in recs if r['tbl'] is not None})
        mno = re.match(r'^考法\s*(\d+)', b['method'] or '')
        node = b['h2'] or b['h1']
        rec = OrderedDict([
            ('id', f'B{i:04d}'), ('part', b['part']), ('kind', b['kind']), ('num', b['num']),
            ('src', b['src']), ('title', b['title']),
            ('h1', b['h1']), ('h2', b['h2']), ('node', node), ('group', b['group']),
            ('method', b['method']), ('method_no', int(mno.group(1)) if mno else None),
            ('key', keys[0]['key'] if keys else None), ('subq', keys[0]['subq'] if keys else None),
            ('keys_all', [k['key'] + (f"({k['subq']})" if k['subq'] else '') for k in keys]),
            ('key_note', '; '.join(k['note'] for k in pk if k['note']) or None),
            ('key_by', '标题解析（机器）' if keys else None),
            ('key_in_bank', keys[0]['in_bank'] if keys else None),
            ('cross_module', '跨模块' in b['src']),
            ('schema', sname), ('columns', cols), ('missing', missing), ('repeated', repeated),
            ('missing_inline', miss_inline), ('missing_exempted', exempted),
            ('other_labels', other), ('inline_labels', dict(inline)),
            ('p_range', [b['p0'], last['p']]), ('body_range', [b['body0'], last['body']]),
            ('n_paras', len(texts)), ('n_chars', sum(len(x) for x in texts)), ('tables', tables),
            ('media', [doc['rels'].get(m, m) for m in media]),
            ('body_sha1', hashlib.sha1('\n'.join(texts).encode('utf-8')).hexdigest()[:16]),
            ('media_sha1', hashlib.sha1('|'.join(msha).encode()).hexdigest()[:16] if media else None),
            ('batch_key', ' | '.join(base) + f' #{occ[base]}'),
            ('align_key', ' | '.join(base + (squash(node),))),
        ])
        rec['_recs'] = [trec] + recs  # 抽取/对位用，输出前去掉
        out.append(rec)
    return out


def finish_drill(drill_rows, cfg):
    d = cfg.drill
    item_rx = re.compile(d.get('item_regex') or r'^(\d+)[、.．]\s*(.*)$', re.S)
    ncols = d.get('columns', 3)
    ac, sc = d.get('answer_col', 1), d.get('source_col', 2)
    blank = squash(d.get('a1_blank', '（　）'))
    marker = d.get('correction_marker', '纠正：')
    a1h = squash(d.get('a1_heading') or '')
    items, other, occ = [], 0, Counter()
    for key, row in drill_rows.items():
        cells = row['cells']
        cell_text = {c: '\n'.join(r['text'] for r in rs).strip() for c, rs in cells.items()}
        if key[0] == 'para':
            stem_all, ans, src = cell_text[0], '', (row.get('src_line') or '')
            extra = cell_text.get(1, '')
            if extra:
                stem_all = stem_all + ('\n' + extra if marker in extra else '')
        else:
            if len(cells) != ncols:
                other += 1
                continue
            stem_all, ans, src = cell_text.get(0, ''), cell_text.get(ac, ''), cell_text.get(sc, '')
        m = item_rx.match(stem_all)
        if not m:
            other += 1
            continue
        body_txt = m.group(2) if m.lastindex and m.lastindex >= 2 else stem_all
        stem, _, corr = body_txt.partition(marker)
        if key[0] == 'para':
            side = 'A1' if a1h and squash(row['h2']).startswith(a1h) else 'A2'
        else:
            side = 'A1' if squash(ans) == blank else 'A2'
        recs = [r for c in sorted(cells) for r in cells[c]]
        stem_cells = recs if key[0] == 'para' else cells.get(0, [])
        red = any(cfg.drill.get('colors', {}).get('error_run', 'C00000') in r['colors'] for r in stem_cells)
        green = any(cfg.drill.get('colors', {}).get('correction', '008000') in r['colors'] for r in stem_cells)
        k = (side, squash(src), squash(stem)[:40])
        occ[k] += 1
        pk = parse_keys(src, cfg.key_aliases, cfg.bank)
        keys = [x for x in pk if x['key']]
        items.append(OrderedDict([
            ('id', f'D{len(items) + 1:04d}'), ('side', side), ('no', m.group(1)), ('group', row['group']),
            ('stem', stem.strip()), ('correction', corr.strip() or None), ('answer', ans), ('src', src),
            ('key', keys[0]['key'] if keys else None), ('subq', keys[0]['subq'] if keys else None),
            ('key_note', '; '.join(x['note'] for x in pk if x['note']) or None),
            ('key_by', '题源解析（机器）' if keys else None),
            ('red', red), ('green', green),
            ('tbl', key[0] if key[0] != 'para' else None), ('row', key[1] if key[0] != 'para' else None),
            ('p_range', [min(row['p']), max(row['p'])]), ('body', row['body']),
            ('text_sha1', hashlib.sha1((body_txt + '|' + ans).encode('utf-8')).hexdigest()[:16]),
            ('batch_key', f'{side} | {k[1]} | {k[2]} #{occ[k]}'),
        ]))
        items[-1]['_recs'] = recs
    return items, other


# ---------------------------------------------------------------- PDF 对位
def pdf_stream(pdf, cfg):
    import fitz
    d = fitz.open(pdf)
    starts, chunks, pos, footers = [], [], 0, []
    for pg in d:
        lines = pg.get_text('text').split('\n')
        keep, foot = [], None
        for ln in lines:
            s = ln.strip()
            m = cfg.footer_rx.search(s) if len(s) <= 16 else None
            if m and foot is None:
                foot = m.group(1) if m.groups() else s
                continue
            keep.append(ln)
        s = sig('\n'.join(keep))
        starts.append(pos)
        chunks.append(s)
        pos += len(s)
        footers.append(foot)
    toc = d.get_toc(simple=True)
    n = d.page_count
    d.close()
    return ''.join(chunks), starts, footers, toc, n


def _lis(seq):
    """最长严格递增子序列（按值），返回所选下标。"""
    tails, tails_i, prev = [], [], [-1] * len(seq)
    for i, v in enumerate(seq):
        k = bisect.bisect_left(tails, v)
        if k == len(tails):
            tails.append(v)
            tails_i.append(i)
        else:
            tails[k] = v
            tails_i[k] = i
        prev[i] = tails_i[k - 1] if k else -1
    out, i = [], tails_i[-1] if tails_i else -1
    while i >= 0:
        out.append(i)
        i = prev[i]
    return out[::-1]


def align(paras, stream, starts):
    """把段落签名对到 PDF 文字流；返回 ({p: (起页, 止页)}, 参与段落数, 锚点数)。

    先取“探针在全书 PDF 文字里只出现一次、在 DOCX 里也只出现一次”的段落作锚点，按最长递增子序列
    去掉乱序锚点；其余段落只在前后两个锚点之间找（同一道题在多个节点重复落位时不会跳错位置）。"""
    page_of = lambda off: bisect.bisect_right(starts, off)
    cand = []
    for r in paras:
        if r['fallback']:
            continue
        s = sig(r['text'])
        if len(s) >= ALIGN_MIN:
            cand.append((r['p'], s))
    L = 16
    probes = Counter(s[:L] for _, s in cand if len(s) >= L)
    want = {k for k, n in probes.items() if n == 1}
    occ = {}
    for i in range(len(stream) - L + 1):
        sub = stream[i:i + L]
        if sub in want:
            occ.setdefault(sub, []).append(i)
    anchors = [(ci, occ[s[:L]][0]) for ci, (_, s) in enumerate(cand)
               if len(s) >= L and s[:L] in want and len(occ.get(s[:L], ())) == 1]
    keep = _lis([pos for _, pos in anchors])
    anchor_pos = {anchors[k][0]: anchors[k][1] for k in keep}
    a_idx = sorted(anchor_pos)
    res = {}
    lo, local = 0, 0
    nxt = 0
    for ci, (p, s) in enumerate(cand):
        while nxt < len(a_idx) and a_idx[nxt] < ci:
            nxt += 1
        if ci in anchor_pos:
            pos = anchor_pos[ci]
            nxt += 1
        else:
            hi = anchor_pos[a_idx[nxt]] if nxt < len(a_idx) else len(stream)
            probe = s[:ALIGN_PROBE]
            pos = stream.find(probe, local, hi + len(probe))
            if pos < 0:
                pos = stream.find(probe, lo, hi + len(probe))
            if pos < 0:
                continue
        end = pos + len(s) - 1
        if len(s) > ALIGN_PROBE:
            tail = s[-ALIGN_PROBE:]
            tp = stream.find(tail, pos, pos + len(s) + 3000)
            if tp >= 0:
                end = tp + len(tail) - 1
        res[p] = (page_of(pos), page_of(min(end, len(stream) - 1)))
        if ci in anchor_pos:
            lo = pos
        local = max(local, pos + min(len(s), ALIGN_PROBE))
    return res, len(cand), len(anchor_pos)


def attach_pages(idx, blocks, items, heads, doc, pdf, cfg, binding_files=()):
    t0 = time.time()
    stream, starts, footers, toc, npages = pdf_stream(pdf, cfg)
    pmap, tried, n_anchor = align(doc['paras'], stream, starts)

    def span(recs):
        ps = [pmap[r['p']] for r in recs if r['p'] in pmap]
        return [min(a for a, _ in ps), max(b for _, b in ps)] if ps else None

    no_page, run, max_run = [], 0, 0
    for b in blocks:
        tp = pmap.get(b['_recs'][0]['p'])
        sp = span(b['_recs'])
        b['pages'] = [tp[0], sp[1]] if tp and sp else sp
        b['page_by'] = '标题对位' if tp else ('正文对位' if sp else None)
        if not sp:
            no_page.append(b['id'])
            run += 1
            max_run = max(max_run, run)
        else:
            run = 0
    for it in items:
        it['pages'] = span(it['_recs'])
    for h in heads:
        pr = pmap.get(h['p'])
        h['page'] = pr[0] if pr else None
    # 用 PDF 书签大纲自检：大纲项按顺序对到同文字的标题段落，比页码
    heading_recs = [{'p': b['_recs'][0]['p'], 'text': b['title'], 'page': b['pages'][0] if b['pages'] else None}
                    for b in blocks] + [{'p': h['p'], 'text': h['text'], 'page': h['page']} for h in heads]
    heading_recs.sort(key=lambda x: x['p'])
    j, cmp_, agree, bad, unmatched = 0, 0, 0, [], 0
    for lvl, title, page in toc:
        s = sig(title)[:12]
        if len(s) < 4:
            continue
        k = j
        while k < len(heading_recs) and not sig(heading_recs[k]['text']).startswith(s):
            k += 1
            if k - j > 400:
                break
        if k >= len(heading_recs) or not sig(heading_recs[k]['text']).startswith(s):
            unmatched += 1
            continue
        j = k + 1
        mine = heading_recs[k]['page']
        if mine is None:
            continue
        cmp_ += 1
        if mine == page:
            agree += 1
        elif len(bad) < 30:
            bad.append({'title': title[:30], 'outline_page': page, 'index_page': mine})
    page_index = OrderedDict((str(n), {'context': '', 'blocks': [], 'drill': [], 'headings': []})
                             for n in range(1, npages + 1))
    for b in blocks:
        if b['pages']:
            for n in range(b['pages'][0], b['pages'][1] + 1):
                page_index[str(n)]['blocks'].append(b['id'])
    for it in items:
        if it['pages']:
            for n in range(it['pages'][0], it['pages'][1] + 1):
                page_index[str(n)]['drill'].append(it['id'])
    for h in heads:
        if h['page']:
            page_index[str(h['page'])]['headings'].append(h['text'][:40])
    # 每页的标题上下文：本页开始时所在的一级/二级/分组/考法（只含节点级正文的页也能定位）
    state, hs, i = OrderedDict(h1='', h2='', group='', method=''), [h for h in heads if h['page']], 0
    for n in range(1, npages + 1):
        while i < len(hs) and hs[i]['page'] < n:
            lv = hs[i]['level']
            state[lv] = hs[i]['text'][:40]
            for lower in {'h1': ('h2', 'group', 'method'), 'h2': ('group', 'method'), 'group': ('method',)}.get(lv, ()):
                state[lower] = ''
            i += 1
        page_index[str(n)]['context'] = ' ＞ '.join(v for v in state.values() if v)
    probe_ps = [b['_recs'][0]['p'] for b in blocks] + [h['p'] for h in heads if h['level'] in ('h1', 'h2', 'method')]
    probe_ps = [p for p in probe_ps if len(sig(doc['paras'][p]['text'])) >= ALIGN_MIN]
    title_ratio = sum(1 for p in probe_ps if p in pmap) / len(probe_ps) if probe_ps else 1.0
    title_min = float(((cfg.prof.get('same_version') or {}).get('title_found_min')) or 0.98)
    rate = len(pmap) / tried if tried else 0.0
    binding = find_binding(pdf, idx['docx']['sha256'], idx['docx']['path'], cfg.prof, binding_files)
    confirmed = binding['status'] == 'confirmed'
    idx['pdf'] = OrderedDict([
        ('path', str(Path(pdf).resolve())), ('sha256', binding['pdf_sha256']), ('pages', npages),
        ('page_basis', 'PDF 物理页（1 起）'), ('footer_labels_found', sum(1 for f in footers if f)),
        ('same_version', confirmed),
        ('page_status', '同版已确认' if confirmed else '未确认同版'),
        ('binding', binding),
        ('align', {'paras_tried': tried, 'aligned': len(pmap), 'rate': round(rate, 4), 'anchors': n_anchor,
                   'blocks_without_page': no_page[:50], 'blocks_without_page_count': len(no_page),
                   'max_consecutive_blocks_without_page': max_run,
                   'note': '对位率只是辅助信号：相邻批次近版错配实测仍有 90%–92%，不能据此判同版'}),
        ('title_check', {'titles_probed': len(probe_ps), 'found_ratio': round(title_ratio, 4), 'threshold': title_min,
                         'note': '一二级标题、考法与例题标题在 PDF 里对上的比例（阈值取配置 same_version.title_found_min，与 batch_health 同）'}),
        ('outline_check', {'outline_entries': len(toc), 'compared': cmp_, 'agree': agree, 'disagree': bad,
                           'unmatched_entries': unmatched,
                           'note': 'PDF 书签大纲由渲染器按标题样式生成，与文字对位是两条独立途径；同样识别不了近版错配'}),
        ('seconds', round(time.time() - t0, 2)),
    ])
    idx['page_index'] = page_index
    warn = []
    if not confirmed:
        warn.append('未确认同版：' + binding['note'] + '；以下页码均为“未确认同版”的对位结果')
    if rate < ALIGN_FAIL:
        warn.append(f'PDF 对位率 {rate:.1%} 低于 {ALIGN_FAIL:.0%}，PDF 大概率不是这份 DOCX 的渲染')
    elif rate < ALIGN_NEAR:
        warn.append(f'PDF 对位率 {rate:.1%} 低于 {ALIGN_NEAR:.0%}，可能是相邻版本的渲染（同版实测 98% 以上）')
    if title_ratio < title_min:
        warn.append(f'标题在 PDF 里只对上 {title_ratio:.1%}（阈值 {title_min:.0%}），疑似非同版')
    if cmp_ and agree < cmp_:
        warn.append(f'书签大纲页码不一致 {cmp_ - agree}/{cmp_} 处')
    if unmatched > max(3, 0.01 * len(toc)):
        warn.append(f'PDF 书签大纲有 {unmatched} 项在 DOCX 标题里找不到（同版实测为 0），疑似非同版')
    if no_page:
        warn.append(f'{len(no_page)} 个题块没有对到页码（最长连续 {max_run} 块）' +
                    ('，连续整段对不上常见于 PDF 与 DOCX 内容不同版' if max_run >= 5 else ''))
    return warn


SHA_RX = re.compile(r'^[0-9a-f]{64}$')
BINDING_PATTERNS = ('*同版*.json', '*身份*.json', '*验收*.json', '.review-manifest.json')


def _records(o, path='$'):
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from _records(v, f'{path}.{k}')
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _records(v, f'{path}[{i}]')


def _binding_candidates(pdf, docx, prof, extra):
    """同版登记的查找位置：显式 --binding、PDF/DOCX 所在目录及上一级、配置登记的审阅清单、审阅历史各批目录、
    候选/构建目录（按配置的目录模式展开）。"""
    files = [Path(x).expanduser() for x in extra]
    dirs = []
    for f in (pdf, docx):
        if f:
            d = Path(f).resolve().parent
            dirs += [d, d.parent]
    paths = (prof or {}).get('paths') or {}
    if paths.get('root'):
        if paths.get('review_manifest'):
            files.append(resolve(prof, paths['review_manifest']))
        if paths.get('review_history'):
            dirs += [Path(x) for x in sorted(glob.glob(str(resolve(prof, paths['review_history']) / '*')))]
        for k in ('candidate_dir_pattern', 'build_dir_pattern'):
            if paths.get(k):
                pat = re.sub(r'\{[^}]*\}', '*', str(resolve(prof, paths[k])))
                sub = paths.get('build_subdir') if k == 'candidate_dir_pattern' else None
                for d in sorted(glob.glob(pat)):
                    dirs.append(Path(d))
                    if sub:
                        dirs.append(Path(d) / sub)
    seen, out = set(), []
    for f in files:
        if f.is_file() and str(f) not in seen:
            seen.add(str(f))
            out.append(f)
    for d in dirs:
        if not d.is_dir():
            continue
        for pat in BINDING_PATTERNS:
            for f in sorted(d.glob(pat)):
                if str(f) not in seen and f.is_file() and f.stat().st_size < 8 << 20:
                    seen.add(str(f))
                    out.append(f)
    return out


def find_binding(pdf, docx_sha, docx_path=None, prof=None, extra=()):
    """查同版登记（只读）。同一条 JSON 记录里 docx 角色 SHA 与 pdf 角色 SHA 同时等于这对文件才算同版；
    记录里若另有 rendered_from* 且不等于 DOCX SHA，视为不一致。只命中一个 SHA 时报“未登记同版”。"""
    pdf_sha = sha256_file(pdf)
    cands = _binding_candidates(pdf, docx_path, prof, extra)
    partial, inconsistent = [], []
    for c in cands:
        try:
            s = c.read_text(encoding='utf-8', errors='replace')
        except OSError:
            continue
        has_d, has_p = docx_sha in s, pdf_sha in s
        if not (has_d or has_p):
            continue
        try:
            data = json.loads(s)
        except ValueError:
            partial.append({'file': str(c), 'docx_sha_listed': has_d, 'pdf_sha_listed': has_p, 'record': '（非 JSON）'})
            continue
        hit_record = False
        for path, rec in _records(data):
            sha_items = [(k, v) for k, v in rec.items() if isinstance(v, str) and SHA_RX.match(v)]
            dvals = {v for k, v in sha_items if 'docx' in k.lower()}
            pvals = {v for k, v in sha_items if 'pdf' in k.lower()}
            rfrom = {v for k, v in sha_items if 'rendered_from' in k.lower()}
            if docx_sha in dvals and pdf_sha in pvals:
                if rfrom and docx_sha not in rfrom:
                    inconsistent.append({'file': str(c), 'record': path, 'note': 'rendered_from 与 DOCX SHA 不同'})
                    continue
                return OrderedDict([('status', 'confirmed'), ('file', str(c)), ('record', path),
                                    ('pdf_sha256', pdf_sha), ('searched_files', len(cands)),
                                    ('note', '同一条记录同时登记了这对 DOCX/PDF 的 SHA')])
            if (docx_sha in dvals or pdf_sha in pvals) and not hit_record:
                hit_record = True
                conflict = None
                if docx_sha in dvals and pvals and pdf_sha not in pvals:
                    conflict = '这条记录里本 DOCX 对应的是另一份 PDF'
                elif pdf_sha in pvals and dvals and docx_sha not in dvals:
                    conflict = '这条记录显示这份 PDF 由另一份 DOCX 渲染'
                partial.append({'file': str(c), 'record': path, 'docx_sha_listed': docx_sha in dvals,
                                'pdf_sha_listed': pdf_sha in pvals, 'conflict': conflict})
        if not hit_record:
            partial.append({'file': str(c), 'docx_sha_listed': has_d, 'pdf_sha_listed': has_p,
                            'record': '（SHA 只出现在无角色字段或清单附属段，如 archive）'})
    if inconsistent:
        note = '找到登记这对 SHA 的记录，但 rendered_from 与 DOCX 不一致'
    elif partial:
        which = '、'.join(sorted({('DOCX' if x['docx_sha_listed'] else '') + ('PDF' if x['pdf_sha_listed'] else '')
                                  for x in partial} - {''}))
        conf = [x for x in partial if x.get('conflict')]
        note = f'只找到登记单个 SHA 的记录（{which}），没有同一条记录同时登记这对 SHA，未登记同版'
        if conf:
            note += f'；且{conf[0]["conflict"]}（{Path(conf[0]["file"]).name} {conf[0]["record"]}），这对文件很可能不同版'
    else:
        note = f'在 {len(cands)} 个候选登记文件里没有找到这对 SHA；可用 --binding 指定同版身份文件'
    return OrderedDict([('status', 'unconfirmed'), ('file', None), ('pdf_sha256', pdf_sha),
                        ('searched_files', len(cands)), ('partial', partial[:8]),
                        ('inconsistent', inconsistent[:4]), ('note', note)])


# ---------------------------------------------------------------- 总入口
def build_index(docx, prof, pdf=None, binding_files=()):
    t0 = time.time()
    cfg = BookCfg(prof)
    doc = load_docx(docx)
    blocks, drill_rows, heads, stats = walk(doc, cfg)
    blocks = finish_blocks(blocks, doc, cfg)
    items, other_rows = finish_drill(drill_rows, cfg) if drill_rows else ([], 0)
    idx = OrderedDict()
    idx['tool'] = 'block_index.py'
    idx['note'] = NOTE
    idx['profile'] = {'book_id': prof.get('book_id'), 'path': prof.get('_profile_path'), 'frozen': bool(prof.get('frozen'))}
    idx['docx'] = {'path': str(Path(docx).resolve()), 'sha256': sha256_file(docx),
                   'paragraphs': len(doc['paras']), 'body_children': doc['n_body']}
    by = Counter((b['part'], b['kind']) for b in blocks)
    lab = {}
    for b in blocks:
        d = lab.setdefault(f"{b['part']}|{b['kind']}", Counter())
        d.update({k: v for k, v in b['columns'].items()})
    idx['summary'] = OrderedDict([
        ('blocks', len(blocks)),
        ('by_part_kind', {f'{p}|{k}': n for (p, k), n in sorted(by.items())}),
        ('by_kind', dict(Counter(b['kind'] for b in blocks))),
        ('label_totals', {k: dict(v) for k, v in lab.items()}),
        ('blocks_missing_label', sum(1 for b in blocks if b['missing'])),
        ('blocks_repeated_label', sum(1 for b in blocks if b['repeated'])),
        ('blocks_missing_inline', sum(1 for b in blocks if b['missing_inline'])),
        ('blocks_missing_exempted', sum(1 for b in blocks if b['missing_exempted'])),
        ('keys_parsed', sum(1 for b in blocks if b['key'])), ('keys_unique', len({b['key'] for b in blocks if b['key']})),
        ('keys_not_in_bank', sum(1 for b in blocks if b['key_in_bank'] is False)),
        ('srcs_unparsed', sum(1 for b in blocks if b['src'] and not b['key'])),
        ('bank', cfg.bank['root'] if cfg.bank else None),
        ('drill_items', len(items)), ('drill_by_side', dict(Counter(i['side'] for i in items))),
        ('drill_src_empty', sum(1 for i in items if not i['src'])),
        ('drill_non_item_rows', other_rows), ('headings', len(heads)), ('walk_stats', dict(stats)),
        ('key_semantics', 'batch_key 为批内唯一键，不能跨批对齐；跨批配对用 align_key＋body_sha1'),
    ])
    warn = []
    if not blocks:
        warn.append('按本配置切出 0 个题块：配置可能不适用这本书（样式名或例题标题写法对不上），或正文为空')
    if items and idx['summary']['drill_src_empty'] == len(items):
        idx['summary']['drill_src_note'] = '本书题肢条目不带题源，--key/--src 选不到题肢；请按 --node（错肢分组）或 --block 选'
    if pdf:
        warn += attach_pages(idx, blocks, items, heads, doc, pdf, cfg, binding_files)
    idx['warnings'] = warn
    idx['headings'] = heads
    idx['blocks'] = blocks
    idx['drill_items'] = items
    idx['seconds'] = round(time.time() - t0, 2)
    return idx


def strip_private(idx):
    out = OrderedDict((k, v) for k, v in idx.items())
    out['blocks'] = [OrderedDict((k, v) for k, v in b.items() if not k.startswith('_')) for b in idx['blocks']]
    out['drill_items'] = [OrderedDict((k, v) for k, v in i.items() if not k.startswith('_')) for i in idx['drill_items']]
    return out


# ---------------------------------------------------------------- 选择与抽取
def select(idx, keys=(), srcs=(), nodes=(), ids=(), pages=(), kinds=(), parts=(), with_drill=True):
    sel_b, sel_d = [], []
    keyset = {k.upper() for k in keys}
    pages = {int(p) for p in pages}

    def key_hit(obj):
        if not keyset:
            return False
        full = {(obj.get('key') or '').upper()}
        full |= {k.upper() for k in obj.get('keys_all', [])}
        if obj.get('key') and obj.get('subq'):
            full.add(f"{obj['key']}({obj['subq']})".upper())
        return bool(full & keyset)

    for b in idx['blocks']:
        hit = (key_hit(b) or b['id'] in ids
               or any(squash(s) in squash(b['src']) for s in srcs)
               or any(squash(n) in squash(' '.join([b['h1'], b['h2'], b['group'], b['method']])) for n in nodes)
               or (pages and b.get('pages') and any(b['pages'][0] <= p <= b['pages'][1] for p in pages)))
        if hit and (not kinds or b['kind'] in kinds) and (not parts or b['part'] in parts):
            sel_b.append(b)
    if with_drill:
        for it in idx['drill_items']:
            hit = (key_hit(it) or it['id'] in ids or any(squash(s) in squash(it['src']) for s in srcs if it['src'])
                   or any(squash(n) in squash(it['group']) for n in nodes)
                   or (pages and it.get('pages') and any(it['pages'][0] <= p <= it['pages'][1] for p in pages)))
            if hit and not kinds and not parts:
                sel_d.append(it)
    return sel_b, sel_d


def render_recs(recs, rels):
    """原文切片：表格按行写成“格｜格”，图片写占位，不改写文字。"""
    lines, row_key, row_cells = [], None, {}

    def flush():
        nonlocal row_key, row_cells
        if row_key is not None:
            lines.append('｜'.join(' / '.join(x for x in row_cells[c] if x) for c in sorted(row_cells)))
        row_key, row_cells = None, {}

    in_tbl = None
    for r in recs:
        if r['tbl'] is not None:
            if in_tbl != r['tbl']:
                flush()
                lines.append('〔表格开始〕')
                in_tbl = r['tbl']
            if row_key != (r['tbl'], r['row']):
                flush()
                row_key = (r['tbl'], r['row'])
            row_cells.setdefault(r['col'], []).append(r['text'].strip())
            continue
        flush()
        if in_tbl is not None:
            lines.append('〔表格结束〕')
            in_tbl = None
        t = r['text'].rstrip()
        for m in r['media']:
            lines.append(f'〔图片：{rels.get(m, m)}〕')
        if t.strip():
            lines.append(t)
    flush()
    if in_tbl is not None:
        lines.append('〔表格结束〕')
    return '\n'.join(lines)


def _page_label(obj, idx):
    if not obj.get('pages'):
        return 'PDF 页码未附'
    tag = '' if (idx.get('pdf') or {}).get('same_version') else '（未确认同版）'
    return f"PDF 第{obj['pages'][0]}–{obj['pages'][1]}页{tag}"


def extract_text(idx, doc_rels, sel_b, sel_d, max_chars=0, pages=()):
    out = [f"〔以下为 block_index.py 从 DOCX 机器截取的原文切片：未改写、未归纳、未核原卷。"
           f"DOCX sha256 {idx['docx']['sha256'][:16]}…；题键为标题机器解析。〕", '']
    for n in pages:
        pi = (idx.get('page_index') or {}).get(str(n))
        if pi:
            out.append(f"--- PDF 第{n}页{'' if idx['pdf']['same_version'] else '（未确认同版）'}｜所在：{pi['context'] or '—'}"
                       f"｜本页标题：{'；'.join(pi['headings']) or '无'}｜题块 {len(pi['blocks'])}｜题肢 {len(pi['drill'])}")
    if pages:
        out.append('')
    for b in sel_b:
        out.append(f"=== {b['id']}｜{b['title']}")
        out.append(f"部分 {b['part']}｜节点 {b['node']}｜考法 {b['method'] or b['group'] or '—'}｜题型 {b['kind']}｜"
                   f"题键 {b['key'] or '未解析'}{'(' + b['subq'] + ')' if b['subq'] else ''}"
                   f"{'〔' + b['key_by'] + '〕' if b['key_by'] else ''}"
                   f"｜段落 p{b['p_range'][0]}–p{b['p_range'][1]}｜{_page_label(b, idx)}")
        body = render_recs(b['_recs'][1:], doc_rels)
        if max_chars and len(body) > max_chars:
            cut = max_chars
            if body.rfind('〔', 0, cut) > body.rfind('〕', 0, cut):  # 不把图片/表格占位切成半截
                cut = body.find('〕', cut) + 1 or cut
            body = (body[:cut] + f"\n〔截断：本题块原文共 {len(body)} 字，此处只给前 {cut} 字；"
                    f"要全文请去掉 --max-chars 或设为 0〕")
        out.extend([body, ''])
    for it in sel_d:
        out.append(f"=== {it['id']}｜{it['side']} 第{it['no']}条｜{it['group']}｜来源 {it['src'] or '（条目未带题源）'}"
                   f"{'〔' + it['key_by'] + '〕' if it.get('key_by') else ''}｜{_page_label(it, idx)}")
        out.append(it['stem'] + (f"\n纠正：{it['correction']}" if it['correction'] else '') +
                   (f"\n判定：{it['answer']}" if it['answer'] else ''))
        out.append('')
    return '\n'.join(out)


def where_rows(sel_b, sel_d, idx=None, pages=()):
    conf = bool(((idx or {}).get('pdf') or {}).get('same_version'))
    rows = []
    for n in pages:
        pi = ((idx or {}).get('page_index') or {}).get(str(n))
        if pi:
            rows.append(OrderedDict([('page', n), ('pages_confirmed', conf), ('context', pi['context']),
                                     ('headings', pi['headings']), ('blocks', pi['blocks']), ('drill', pi['drill'])]))
    for b in sel_b:
        rows.append(OrderedDict([('id', b['id']), ('title', b['title']), ('node', b['node']),
                                 ('method', b['method'] or b['group']), ('kind', b['kind']), ('key', b['key']),
                                 ('subq', b['subq']), ('key_by', b['key_by']), ('key_note', b['key_note']),
                                 ('p_range', b['p_range']), ('pages', b.get('pages')),
                                 ('pages_confirmed', conf if b.get('pages') else None)]))
    for it in sel_d:
        rows.append(OrderedDict([('id', it['id']), ('title', f"{it['side']} 第{it['no']}条 {it['stem'][:24]}"),
                                 ('node', it['group']), ('key', it['key']), ('key_by', it.get('key_by')),
                                 ('src', it['src']), ('p_range', it['p_range']), ('pages', it.get('pages')),
                                 ('pages_confirmed', conf if it.get('pages') else None)]))
    return rows


# ---------------------------------------------------------------- 书册识别与写出保护
def safe_profiles(extra=None):
    """读全部登记配置；读不了的跳过（profiles/ 里混入的非配置 JSON 不会让工具崩溃）。"""
    out = []
    for name in list_profiles():
        try:
            p = load_profile(name)
        except Exception:  # noqa: BLE001  配置坏了只跳过，由配置负责人处理
            continue
        if isinstance(p, dict) and isinstance(p.get('paths'), dict):
            out.append(p)
    if extra and extra.get('_profile_path') not in {p.get('_profile_path') for p in out}:
        out.append(extra)
    return out


def _under(o, d):
    return o == d or d in o.parents


def detect_book(path):
    """按文件落在哪本登记书册的工作区/审阅入口/历史目录里判断书册（比 profile_lib.detect_profile 多容错）。"""
    s = Path(path).resolve()
    for prof in safe_profiles():
        if not prof['paths'].get('root'):
            continue
        for k in ('workspace', 'aux_workspace', 'review_entry', 'review_history'):
            v = prof['paths'].get(k)
            if v and _under(s, resolve(prof, v).resolve()):
                return prof
    return None


def _temp_roots():
    out = set()
    for d in (tempfile.gettempdir(), '/tmp', '/private/tmp', '/var/folders', '/private/var/folders'):
        try:
            out.add(Path(d).resolve())
        except OSError:
            pass
    return out


def protected_dirs(prof=None):
    """[(目录, 原因, 所属配置)]：书册登记目录、协作/状态目录、题库根、项目根、书稿根、Skill 母版。"""
    rows = [(PROFILE_DIR.resolve(), 'Skill 母版 profiles/（只放经确认的书册配置）', None),
            (SKILL_DIR, 'Skill 母版', None)]
    pats = list(PROTECTED_GLOBS)
    for P in safe_profiles(prof):  # 与 batch_health 共用 _house.json 的 output_guard.protected_roots
        pats += [x for x in ((P.get('output_guard') or {}).get('protected_roots') or []) if x not in pats]
    for pat in pats:
        for d in glob.glob(str(Path(pat).expanduser())):
            rows.append((Path(d).resolve(), '受保护根目录（书稿/题源原件/Skill）', None))
    for P in safe_profiles(prof):
        paths = P['paths']
        if not paths.get('root'):
            continue
        name = P.get('title') or P.get('book_id')

        def add(rel, why, parent=False):
            if not rel:
                return
            templ = '{' in str(rel)
            q = resolve(P, str(rel).split('{')[0]) if templ else resolve(P, rel)
            q = q.parent if parent or templ else q
            rows.append((q.resolve(), f'{name}{why}', P))

        for k, why in (('workspace', '工作区'), ('aux_workspace', '辅助工作区'), ('review_entry', '审阅入口'),
                       ('review_history', '审阅历史')):
            add(paths.get(k), why)
        for k, why in (('handoff', '协作目录'), ('central_state', '中央状态目录'), ('review_manifest', '审阅入口'),
                       ('progress_note', '工作区')):
            add(paths.get(k), why, parent=True)
        for k in ('candidate_dir_pattern', 'build_dir_pattern'):
            add(paths.get(k), '候选/构建目录')
        for extra in paths.get('protected_roots') or []:
            add(extra, '登记的保护目录')
        bank = ((P.get('sources') or {}).get('bank') or {}).get('root')
        if bank:
            rows.append((resolve(P, bank).resolve(), '题库目录（写权属于题库负责人）', None))
        rootp = Path(paths['root']).expanduser().resolve()
        if P.get('frozen') and P.get('collab_key') and rootp.is_dir():
            for d in rootp.iterdir():  # 冻结册的其余目录（封面替换、接续、旧审阅入口等）按册名归属
                if d.is_dir() and P['collab_key'] in d.name:
                    rows.append((d.resolve(), f'{name}相关目录', P))
        rows.append((rootp, '项目根目录（共享书稿、协作与同步目录所在）', None))
    return rows


def guard_out(out, docx=None, prof=None, inputs=(), is_dir=False):
    """写出前检查；拒绝时抛 SystemExit（冻结册经 frozen_guard 抛出）。"""
    o = Path(out).expanduser().resolve()
    ins = [Path(x).resolve() for x in (docx,) + tuple(inputs) if x]
    if o in ins:
        raise SystemExit(f'拒绝写入：输出 {o} 与输入文件相同')
    rows = protected_dirs(prof)
    for d, why, P in rows:  # 先查冻结册，拒绝消息由该册 frozen_guard 给出
        if P is not None and P.get('frozen') and _under(o, d):
            frozen_guard(P, f'把输出写进 {d}')
    if _under(o, PROFILE_DIR.resolve()):
        raise SystemExit(f'拒绝写入：{o} 位于 profiles/（草案与索引不进配置目录）')
    for f in ins:
        if _under(o, f.parent):
            raise SystemExit(f'拒绝写入：{o} 位于输入文件所在目录 {f.parent}（不把输出写到书稿旁边）；请用 --out 指到临时目录')
    for d, why, P in sorted(rows, key=lambda x: -len(str(x[0]))):
        if _under(o, d):
            raise SystemExit(f'拒绝写入：{o} 位于{why} {d} 之下；请用 --out 指到临时目录或本会话 scratch')
    in_temp = any(_under(o, t) for t in _temp_roots())
    par = o if is_dir else o.parent
    if not in_temp and par.is_dir():
        near = [x.name for x in par.iterdir() if x.suffix.lower() in ('.docx', '.pdf') and not x.name.startswith('~$')]
        if near:
            raise SystemExit(f'拒绝写入：目标目录 {par} 里有书稿/PDF（{near[0]} 等），不把输出写到书稿旁边')
    if not is_dir and o.exists() and not in_temp and not _own_output(o):
        raise SystemExit(f'拒绝写入：{o} 已存在、不在临时目录且不是本工具以前的输出，不覆盖')


OWN_MARKS = ('"tool": "block_index.py"', '"tool": "profile_probe.py"', '〔以下为 block_index.py')


def _own_output(p):
    """已存在的目标是否为 block_index/profile_probe 以前写出的产物（这类文件允许重写）。"""
    try:
        with open(p, 'rb') as f:
            head = f.read(600)
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 6000))
            tail = f.read()
    except OSError:
        return False
    txt = head.decode('utf-8', 'ignore') + tail.decode('utf-8', 'ignore')
    return any(m in txt for m in OWN_MARKS)


# ---------------------------------------------------------------- 命令行
def _pos_int(s):
    try:
        v = int(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f'须为正整数：{s}')
    if v < 1:
        raise argparse.ArgumentTypeError(f'须为正整数：{s}')
    return v


def _nonneg_int(s):
    try:
        v = int(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f'须为非负整数：{s}')
    if v < 0:
        raise argparse.ArgumentTypeError(f'须为非负整数：{s}')
    return v


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docx', required=True, help='书稿 DOCX（只读）')
    ap.add_argument('--profile', help='书册配置名（如 bixiu3）或配置 JSON 路径；缺省按 DOCX 路径自动判断')
    ap.add_argument('--pdf', help='同版 PDF（只读）；给出后附页码、查同版登记并做大纲自检')
    ap.add_argument('--binding', action='append', default=[], help='同版身份 JSON（只读，可多次给）；默认查找位置之外的登记')
    ap.add_argument('--out', help='索引 JSON 输出路径（缺省写系统临时目录 block_index/）')
    g = ap.add_argument_group('选择（可叠加，取并集）')
    g.add_argument('--key', action='append', default=[], help='题库题键，如 BJ-2024-CY-ERMO-Q18 或 …-Q17(1)')
    g.add_argument('--src', action='append', default=[], help='题源文字片段，如 2024朝阳二模第18题')
    g.add_argument('--node', action='append', default=[], help='节点/考法文字片段（匹配一级、二级标题、分组、考法、错肢分组）')
    g.add_argument('--block', action='append', default=[], help='题块号 B0001 或题肢号 D0001')
    g.add_argument('--page', action='append', default=[], type=_pos_int, help='PDF 页码（需 --pdf），正整数')
    g.add_argument('--kind', action='append', default=[], help='只要这些题型（subjective/choice/topic…）')
    g.add_argument('--part', action='append', default=[], help='只要这些部分（配置里的 part id）')
    g.add_argument('--no-drill', action='store_true', help='选择结果不含题肢条目')
    g2 = ap.add_argument_group('输出方式')
    g2.add_argument('--extract', action='store_true', help='输出所选题块原文切片')
    g2.add_argument('--where', action='store_true', help='只输出所选题块的位置（段落范围、页码）')
    g2.add_argument('--extract-out', help='切片写到此文件（缺省打印到标准输出）')
    g2.add_argument('--max-chars', type=_nonneg_int, default=0, help='每块最多给多少字，超出处注明截断；0=不截断')
    g2.add_argument('--quiet', action='store_true', help='不打印摘要')
    a = ap.parse_args(argv)

    for f in (a.docx, a.pdf):
        if f and not Path(f).is_file():
            print('找不到文件：', f, file=sys.stderr)
            return 2
    if a.page and not a.pdf:
        print('--page 需要同时给 --pdf', file=sys.stderr)
        return 2
    if (a.extract or a.where) and not (a.key or a.src or a.node or a.block or a.page):
        print('--extract/--where 需要至少一个选择条件（--key/--src/--node/--block/--page）', file=sys.stderr)
        return 2
    try:
        prof = load_profile(a.profile) if a.profile else detect_book(a.docx)
    except (OSError, ValueError, KeyError) as e:
        print('读不了书册配置：', e, file=sys.stderr)
        return 2
    if prof is None:
        print('按路径判断不出书册，请用 --profile 指定（新书先用 profile_probe.py 生成草案）', file=sys.stderr)
        return 2
    out = Path(a.out) if a.out else Path(tempfile.gettempdir()) / 'block_index' / (Path(a.docx).stem + '.index.json')
    try:
        guard_out(out, a.docx, prof, inputs=[a.pdf] if a.pdf else [])
        if a.extract_out:
            guard_out(a.extract_out, a.docx, prof, inputs=[a.pdf] if a.pdf else [])
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2
    try:
        check_docx(a.docx)
        if a.pdf:
            check_pdf(a.pdf)
    except InputError as e:
        print('输入错误：', e, file=sys.stderr)
        return 2
    try:
        idx = build_index(a.docx, prof, a.pdf, a.binding)
    except Exception:  # noqa: BLE001  内部错误也给 2，不与“有警告的成功(1)”混淆
        traceback.print_exc()
        print('内部错误：索引未生成（退出码 2）', file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(strip_private(idx), ensure_ascii=False, indent=1), encoding='utf-8')
    code = 1 if idx['warnings'] else 0

    s = idx['summary']
    if not a.quiet:
        print(f"{idx['profile']['book_id']}｜题块 {s['blocks']}（{', '.join(f'{k} {v}' for k, v in s['by_kind'].items())}）"
              f"｜题肢 {s['drill_items']} {s['drill_by_side']}｜题键解析 {s['keys_parsed']}（唯一 {s['keys_unique']}，题库无此卷 {s['keys_not_in_bank']}）"
              f"｜缺栏候选 {s['blocks_missing_label']} 块（另标签在行中 {s['blocks_missing_inline']} 块）｜用时 {idx['seconds']}s")
        if a.pdf:
            p = idx['pdf']
            print(f"  PDF {p['pages']} 页｜{p['page_status']}（{p['binding']['note']}）"
                  f"｜段落对位 {p['align']['aligned']}/{p['align']['paras_tried']}（{p['align']['rate']:.1%}）"
                  f"｜大纲自检 {p['outline_check']['agree']}/{p['outline_check']['compared']} 一致")
        for w in idx['warnings']:
            print('  注意：', w)
        print('  说明：索引只反映机械结构，机械层全过只说明结构没有回退，不代表内容已审；题键为机器解析。')
        print('明细：', out)

    if a.extract or a.where:
        sb, sd = select(idx, a.key, a.src, a.node, set(a.block), a.page, set(a.kind), set(a.part), not a.no_drill)
        pages_ok = [n for n in a.page if str(n) in (idx.get('page_index') or {})]
        if not sb and not sd and not pages_ok:
            print('选择条件没有匹配到题块' + ('（页码超出 PDF 页数）' if a.page else ''), file=sys.stderr)
            code = 1
        if a.where:
            txt = json.dumps(where_rows(sb, sd, idx, pages_ok), ensure_ascii=False, indent=1)
        else:
            rels = load_docx_rels(a.docx)
            txt = extract_text(idx, rels, sb, sd, a.max_chars, pages_ok)
        if a.extract_out:
            Path(a.extract_out).parent.mkdir(parents=True, exist_ok=True)
            Path(a.extract_out).write_text(txt, encoding='utf-8')
            if not a.quiet:
                print(f'切片：{a.extract_out}（题块 {len(sb)}，题肢 {len(sd)}）')
        else:
            print(txt)
    return code


def load_docx_rels(docx):
    z = zipfile.ZipFile(docx)
    try:
        return {r.get('Id'): r.get('Target') for r in
                etree.fromstring(z.read('word/_rels/document.xml.rels')).iter(PKG_REL + 'Relationship')}
    except KeyError:
        return {}


if __name__ == '__main__':
    sys.exit(main())
