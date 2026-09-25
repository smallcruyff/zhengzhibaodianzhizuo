#!/usr/bin/env python3
"""qpack：题键 → 取材包（跨书通用；只读题库、只读书稿）。

把书中题源写法（“2024朝阳二模第18题”“2023海淀期中（下）第8题”“A 与 B”双题源行）解析成题库题键，
按角色从题库题级 MD 截取原文（默认只取 E1 正式细则与题面），逐条标证据等级，叠加可追溯到用户要求总账 REQ 的裁定，
记录失效指纹；一次建包，子代理只读自己的切片（q/<题键>.md）。

用法：
  python3 qpack.py resolve "2024朝阳二模第18题" "2022—2023学年第二学期海淀期中第17题" [--json]
  python3 qpack.py build --docx 本批.docx [--profile bixiu3] [--part TOPIC] [--node 政府 | --subject 政府]
                         [--kinds subjective,topic] --out <临时目录> [--layers stem,e1] [--ledger 看页账本.jsonl]
  python3 qpack.py build --keys 题键清单.txt --out <临时目录>      # 每行一个题键或题源写法，可写 KEY(1) 表示小问
  python3 qpack.py get BJ-2024-CY-ERMO-Q18 [--layers e1,stem] [--json]   # 单题切片打到 stdout，不写文件
  python3 qpack.py check <目录>/packet.json [--rehash]                  # 失效判定
  python3 qpack.py ledger-add --ledger 看页账本.jsonl --key K --layer e1 --by main|subagent --agent-id ID
                              (--page-png 本卷页图 | --source-id 本卷来源 --page N) [--verdict exact|corrected|mismatch]
  python3 qpack.py selftest [--n 30] [--out <临时目录>]   # 抽样对照 bank.py get --with-rubric（python3 -B，不写 pyc）

证据等级（逐小节、逐题标注，不互相冒充）：
  main_viewed      看页账本里主代理登记过原页、原页证据属于本卷且是图片（或本卷来源＋有效页码）、登记时 MD/小节/页图 SHA 与现在一致、
                   verdict=exact、且该层题库有正文
  subagent_viewed  同上，但只有子代理登记（主代理未核）
  bank_accepted    题库卷已验收、题级 MD SHA 等于验收记录、小节标题不带候选/OCR 标记（题库已验收 ≠ 主代理已核原页）
  bank_candidate   题库有这一层文字，但卷未验收、SHA 不符、小节本身是候选/OCR，或文字来自未绑定验收 SHA 的链接转写文件
  missing          题库没有这一层文字（“未找到/未提供正式细则”这类声明按空处理）
角色（role_basis）与等级分开：bank_alias（题库标准标题）、bank_guide（读取指引）、ruling:<REQ>（用户裁定）、
heading_regex / subheading_regex（脚本按标题推断，须模型确认）、+link（跟随卷内转写链接截取）。
E1 状态：ok / pointer_only（只有出处指针或工程说明）/ ruling_page_only（裁定指向原页、题库无正文）/ named_exception（具名例外）
/ missing；限定小问的裁定按小问记在 e1_by_subq。原页核对判 corrected/mismatch 的列入 view_conflicts，切片头警示、不升等级。
身份探针：书中题面取 5 个短片段比对题级 MD；自动定案门槛统一为“最高≥4 且领先≥2”。本卷命中≤1 而别卷达门槛时，
该落位记为“身份待定”（切片头警示、不计入解析率、不计入 E1 统计），加 --probe-redirect 才改映射。

只读承诺：不修改、不移动、不重存任何书稿、审阅入口、协作文件、题库文件；不 import bank.py（别名表用 ast 读取），
不调用 bank.py packet。写入只准系统临时目录或书册配置 qpack.out_dirs/qpack.ledger_dirs 登记的目录（白名单）；
题库、各书册工作区、协作、00_共同资料、.claude、后勤管理、审阅入口、书稿旁、冻结册一律拒绝。
脚本只截取原文、不生成归纳或摘要；截断处写明原文字数与行号。门全过只说明机械层没有回退，不代表内容已审。

退出码：build 0 全部落位解析成功；3 已建包但有未解析题源、缺题级 MD、身份待定、疑似题源行未收或同名多卷；2 输入错误（含
            书稿收到 0 个例题块、选择器命中 0、题键清单为空、拒绝写入）；
        get 0 E1 主代理已核原页，10 题库已验收（未经主代理核原页），15 子代理看过（主代理未核），20 只有候选/出处指针/裁定页图，
            25 看页账本判题库原文与原页不符，30 缺 E1，40 具名例外，2 输入错误；
        check 0 无失效，1 有失效，2 输入错误；resolve 0 全部解析，1 有未解析；ledger-add 0 已登记，2 证据不成立或拒绝写入。
"""
import argparse
import ast
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import profile_lib as PL  # noqa: E402

ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
DEFAULT_BANK = ROOT / 'DeepSeek_政治题库资料库_20260918'
DEFAULT_MANIFEST = ROOT / '后勤管理/MD全库流水线_20260921/conversion_manifest.json'
SRC_ROOT = ROOT / '00_共同资料/原材料'
REQ_LEDGER = HERE.parent / 'references/user-requirements-ledger.md'
DATA = HERE / 'qpack_data'
KEYMAP_FILE = DATA / 'keymap_overrides.json'
RULINGS_FILE = DATA / 'rulings.json'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

LEVELS = ['missing', 'bank_candidate', 'bank_accepted', 'subagent_viewed', 'main_viewed']
LEVEL_CN = {
    'missing': '缺', 'bank_candidate': '题库候选（须看原页）',
    'bank_accepted': '题库已验收（≠主代理已核原页）',
    'subagent_viewed': '子代理看过原页（主代理未核）', 'main_viewed': '主代理已核原页',
}
LAYER_CN = {'stem': '题面', 'stem_adj': '题面附图表', 'e1': 'E1 正式细则', 'e3': 'E3 参考答案',
            'candidate': '候选评分材料', 'student': '学生层', 'lecture': '讲评', 'meta': '工程信息'}
ALL_LAYERS = ['stem', 'e1', 'e3', 'candidate', 'student', 'lecture']
DEFAULT_LAYERS = ['stem', 'e1']

REGIONS = OrderedDict([('石景山', 'SJS'), ('门头沟', 'MTG'), ('海淀', 'HD'), ('西城', 'XC'), ('东城', 'DC'),
                       ('朝阳', 'CY'), ('丰台', 'FT'), ('顺义', 'SY'), ('昌平', 'CP'), ('房山', 'FS'),
                       ('延庆', 'YQ'), ('通州', 'TZ'), ('大兴', 'DX'), ('平谷', 'PG'), ('怀柔', 'HR'), ('密云', 'MY')])
STAGES = {'一模': 'YIMO', '二模': 'ERMO', '期末': 'QIMO', '期中': 'QIZHONG', '高考': 'GAOKAO'}
_REG = '|'.join(REGIONS)
EXAM_RX = (r'(?P<y>20\d\d)(?:届|年)?(?:北京市?)?(?P<reg>' + _REG + r')?区?(?:高三)?'
           r'(?P<stg>一模|二模|期末|期中|高考)(?:[（(](?P<half>[上下])[）)])?(?:练习|考试|试题|试卷|卷)?')
SY_RX = (r'(?P<y1>20\d\d)[—–\-~至](?P<y2>20\d\d)学年度?(?:第(?P<sem>[一二])学期)?(?:北京市?)?(?P<reg>' + _REG +
         r')?区?(?:高三)?(?P<stg>一模|二模|期末|期中)(?:练习|考试|试题|试卷|卷)?')
# 小问写法：第17(1)题、第17题第（1）问、17题（1）
Q_RX = (r'(?:选择题?|主观题?|非选择题)?第?(?P<n>\d{1,2})(?:[（(](?P<s1>\d)[）)])?题?'
        r'(?:第?[（(]?(?P<s2>\d)[）)]?问|[（(](?P<s3>\d)[）)])?')
TITLE_RX = re.compile(EXAM_RX + Q_RX)
SY_TITLE_RX = re.compile(SY_RX + Q_RX)
KEY_RX = re.compile(r'BJ-(20\d\d)-([A-Z]{2,3})-(YIMO|ERMO|QIMO|QIZHONG|GAOKAO)-Q(\d{1,2})(?:\((\d)\))?')
FW = str.maketrans('０１２３４５６７８９', '0123456789')
# 学年写法里各考次默认所在学期（身份更正表 school_year_corrections 可逐卷改）
STAGE_SEM = {'期中': '一', '期末': '一', '一模': '二', '二模': '二'}
# 身份探针自动定案门槛：最高命中不低于 PROBE_MIN 片段，且领先第二名至少 PROBE_LEAD 片段
PROBE_MIN, PROBE_LEAD = 4, 2

UNVERIFIED_RX = re.compile(r'OCR|候选|未逐字|待确认|未确认|待复核|未核|未晋升|不升格|须回原卷核实|含答案风险')
E1_RX = re.compile(r'正式评分|评分细则|阅卷细则|评分标准|评分主载体|题级评分|正式细则|E1')
E1_NEG_RX = re.compile(r'候选|不升格|非\s*E1|无\s*E1|N/A|不是正式|不等于正式|不得当作|不得视为|不得作为|错配|已隔离|无题级|未找到|未晋升|通用等级')
META_RX = re.compile(r'身份|读取指引|配对状态|来源定位|质量标记|复核|修复|审计|覆盖|证据状态|证据边界|证据裁决|边界|'
                     r'工程状态|父稿|父文件|父 MD|候选状态|候选生成|候选工位|整合记录|来源与|来源、|来源页|来源角色|'
                     r'页级|页/段|读取顺序|追溯|未决|视觉核验结论|视觉核定身份|复核提示|结论|^来源$')
IMG_RX = re.compile(r'((?:assets|evidence|rubric_pages|source_pages)/[^\s`)\]\'"<>]+?\.(?:png|jpe?g))', re.I)
LABEL_RX = re.compile(r'^【([^】]{1,8})】')
SOURCE_LABELS = {'题目', '材料', '设问'}
# 工程说明用词：E1 小节里这类词密集、又没有不含这些词的正文行时，按“只有出处指针/工程说明”处理
ENG_RX = re.compile(r'slide|native|XML|PPTX|PDF|DOCX|png|SHA|source_id|blocks?\b|lines?\s*\d|工位|复核|转写|视觉|渲染|'
                    r'候选|指针|配对|绑定|载体|分层|证据|边界|隔离|升格|升级|并入|N/A|原生|页图|物理页|题库|缓存|定位|见下方|见上方|详见',
                    re.I)
# E1 小节正文只是在声明“没有正式细则”
ABSENT_RX = re.compile(r'not_provided|未提供[^。；]{0,12}(细则|评分)|未找到[^。；]{0,20}(细则|评分)|未在[^。；]{0,60}定位|'
                       r'未定位[^。；]{0,20}(细则|评分)|无同卷[^。；]{0,10}(细则|评分)|没有正式|无正式(评分|细则)|^\s*[-*]?\s*`?N/A_with_basis|'
                       r'没有为本题提供[^。；]{0,20}(评分|细则)|不能升级为\s*E1|不能升格为\s*E1', re.M)
SCORE_RX = re.compile(r'\d\s*分')
# 渲染环境造成的页图空白（这类页图不能当原页看）
BLANK_RENDER_RX = re.compile(r'渲染为空白|未显示中文|字体替换|中文[^。；]{0,8}(空白|不显示|未显示)')
QTYPE_RX = re.compile(r'题型\s*[:：]\s*`?(非选择题|选择题)')


# ---------------------------------------------------------------- 通用小工具

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha256_text(t):
    return sha256_bytes(t.encode('utf-8'))


def canon(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


_FILE_SHA = {}


def file_sha(p):
    """整文件 SHA-256（本进程内按 路径+大小+mtime 缓存）。"""
    p = Path(p)
    try:
        st = p.stat()
    except OSError:
        return None
    k = (str(p), st.st_size, st.st_mtime_ns)
    if k not in _FILE_SHA:
        h = hashlib.sha256()
        with open(p, 'rb') as f:
            for blk in iter(lambda: f.read(1 << 20), b''):
                h.update(blk)
        _FILE_SHA[k] = h.hexdigest()
    return _FILE_SHA[k]


def is_under(p, d):
    try:
        Path(p).resolve().relative_to(Path(d).resolve())
        return True
    except ValueError:
        return False


def level_max(levels):
    levels = [x for x in levels if x]
    return max(levels, key=LEVELS.index) if levels else 'missing'


def norm_text(t):
    """探针比对用：只留汉字、字母、数字。"""
    return re.sub(r'[^0-9A-Za-z一-鿿]', '', t or '')


class InputError(Exception):
    """输入错误或拒绝写入：命令返回退出码 2。"""


def image_magic_ok(p):
    try:
        with open(p, 'rb') as f:
            head = f.read(8)
    except OSError:
        return False
    return head.startswith(b'\x89PNG\r\n\x1a\n') or head[:3] == b'\xff\xd8\xff'


def qnum_set(qid_text, key):
    """bounded_residual 等记录里的 qid 写法（BJ-…-Q17、Q16..Q21、Q16,Q18、多题（Q17/Q18）、全部21题）是否覆盖本题。"""
    exam, q = key.rsplit('-Q', 1)
    q = int(q)
    s = str(qid_text or '')
    other = re.findall(r'BJ-20\d\d-[A-Z]{2,3}-[A-Z]+', s)
    if other and exam not in other:
        return False
    if re.search(r'全部\s*\d*\s*题|全卷', s):
        return True
    for a, b in re.findall(r'Q(\d{1,2})\s*(?:\.\.|…|—|–|~|至|-)\s*Q?(\d{1,2})', s):
        if int(a) <= q <= int(b):
            return True
    return q in {int(x) for x in re.findall(r'Q(\d{1,2})(?!\d)', s)}


# ---------------------------------------------------------------- 题库只读接口

def _ast_eval(node, env):
    try:
        return ast.literal_eval(node)
    except Exception:
        pass
    # 只认 tuple(dict.fromkeys([...常量或已知名字...])) 这一种写法
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'tuple' and node.args:
        inner = node.args[0]
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute) and inner.func.attr == 'fromkeys':
            out = []
            for e in inner.args[0].elts:
                out.append(e.value if isinstance(e, ast.Constant) else env[e.id])
            return tuple(dict.fromkeys(out))
    raise ValueError('unsupported')


def load_bank_tables(bank_py):
    """用 ast 读 bank.py 的小节别名表（不执行、不 import，不在题库目录留 __pycache__）。"""
    env = {}
    tree = ast.parse(Path(bank_py).read_text(encoding='utf-8'))
    for n in tree.body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name):
            try:
                env[n.targets[0].id] = _ast_eval(n.value, env)
            except Exception:
                pass
    rs = env.get('ROLE_SECTION_ALIASES', {})
    t = {
        'e1': set(rs.get('e1', ())), 'e3': set(rs.get('e3', ())), 'student': set(rs.get('student', ())),
        'qid_e1': {k: set(v) for k, v in env.get('ROLE_SECTION_QID_ALIASES', {}).get('e1', {}).items()},
        'stem': list(env.get('STEM_ALIASES', ())), 'guided_stem': set(env.get('GUIDED_STEM_ALIASES', ())),
        'structure': set(env.get('STRUCTURE_SECTIONS', ())), 'passthrough': set(env.get('PASSTHROUGH_SECTIONS', ())),
        'unknown': set(env.get('UNKNOWN_ROLE_SECTIONS', ())),
        'default_passthrough': list(env.get('DEFAULT_PASSTHROUGH_SECTIONS', ())),
    }
    fp = sha256_text(canon({k: sorted(v) if isinstance(v, (set, list)) else {a: sorted(b) for a, b in v.items()}
                            for k, v in t.items()}))
    return t, fp


def read_csv(p):
    if not Path(p).exists():
        return []
    with open(p, encoding='utf-8-sig') as fh:
        return list(csv.DictReader(fh))


class Bank:
    def __init__(self, root=DEFAULT_BANK, manifest=DEFAULT_MANIFEST):
        self.root = Path(root)
        self.qdir = self.root / 'questions'
        self.manifest_path = Path(manifest)
        self.tables, self.tables_sha = load_bank_tables(self.root / 'scripts/bank.py')
        man = json.loads(self.manifest_path.read_text(encoding='utf-8'))
        self.manifest_updated = man.get('updated_at')
        self.manifest_sha = file_sha(self.manifest_path)
        self.tasks = {t['exam_id']: t for t in man.get('tasks', [])}
        self.exams = [r for r in read_csv(self.root / 'indexes/exams.csv') if r.get('is_assembly') != 'Y']
        self.sources = {r['source_id']: r for r in read_csv(self.root / 'indexes/source_manifest.csv')}
        self._state = {}

    def exam_known(self, exam_id):
        return (self.qdir / exam_id).is_dir() or exam_id in self.tasks

    def md_path(self, key):
        return self.qdir / key.rsplit('-Q', 1)[0] / (key + '.md')

    def state(self, exam_id):
        if exam_id not in self._state:
            p = self.qdir / exam_id / 'shared_conversion_state.json'
            try:
                self._state[exam_id] = json.loads(p.read_text(encoding='utf-8')) if p.exists() else None
            except Exception:
                self._state[exam_id] = {'_unreadable': True}
        return self._state[exam_id]

    def exam_sources(self, exam_id):
        out = []
        for role, lst in ((self.tasks.get(exam_id) or {}).get('sources') or {}).items():
            for s in lst or []:
                out.append(dict(s, role=role))
        return out

    def source_pages(self, sid, exam_id=None):
        """登记页数；docx 等无固定页数时返回 None。"""
        for s in self.exam_sources(exam_id) if exam_id else []:
            if s.get('source_id') == sid and isinstance(s.get('pages'), int) and s['pages'] > 0:
                return s['pages']
        v = (self.sources.get(sid) or {}).get('pages')
        try:
            v = int(v)
        except (TypeError, ValueError):
            return None
        return v if v > 0 else None

    def residuals(self, exam_id, key):
        """shared_conversion_state 与总清单里 bounded_residual / conversion_unresolved 中覆盖本题的条目（原样）。"""
        st = self.state(exam_id) or {}
        task = self.tasks.get(exam_id) or {}
        seen, out = set(), []
        for origin, d in (('shared_conversion_state', st), ('conversion_manifest', task)):
            for field in ('bounded_residual', 'conversion_unresolved'):
                for e in d.get(field) or []:
                    if not isinstance(e, dict):
                        e = {'qid': '', 'text': str(e)}
                    c = canon(e)
                    if c in seen:
                        continue
                    seen.add(c)
                    if qnum_set(e.get('qid') or e.get('question') or '', key):
                        out.append({'field': field, 'origin': origin, 'entry': e})
        return out

    def source_path(self, sid, rel_path=None):
        row = self.sources.get(sid)
        if row and row.get('original_path') and Path(row['original_path']).exists():
            return Path(row['original_path'])
        return SRC_ROOT / rel_path if rel_path else None

    def resolve_img(self, exam_id, rel):
        for base in (self.qdir / exam_id, self.qdir / exam_id / 'assets', self.root):
            p = base / rel
            if p.exists():
                return str(p)
        return None

    def school_year_candidates(self, sy, region, stage, sem, keymap):
        """学年写法 → 候选卷号。exams.csv 的 school_year 先按身份更正表 school_year_corrections 改正；
        返回 (候选, exams.csv 与身份核查冲突的卷)。"""
        corr = keymap.get('school_year_corrections') or {}
        out, conflict = [], []
        for r in self.exams:
            if r.get('region') != region or r.get('stage') != stage:
                continue
            eid = r['exam_id']
            c = corr.get(eid) or {}
            true_sy = c.get('school_year') or r.get('school_year')
            true_sem = c.get('semester') or STAGE_SEM.get(stage)
            raw_hit = r.get('school_year') == sy and (not sem or STAGE_SEM.get(stage) == sem)
            true_hit = true_sy == sy and (not sem or true_sem == sem)
            if true_hit:
                out.append(eid)
            if c and raw_hit != true_hit:
                conflict.append(eid)
        return sorted(out), sorted(conflict)


# ---------------------------------------------------------------- 身份更正表与用户裁定

def load_keymap(path=KEYMAP_FILE):
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    d['_sha'] = sha256_text(canon({k: v for k, v in d.items() if not k.startswith('_')}))
    d['_path'] = str(path)
    return d


def ledger_entry_text(ledger_text, req_id):
    """总账里 REQ 条目原文：标题式取到下一个二级标题，表格式取该行。找不到返回 None。"""
    m = re.search(r'^## ' + re.escape(req_id) + r'[：:].*?(?=^## |\Z)', ledger_text, re.M | re.S)
    if m:
        return m.group(0)
    m = re.search(r'^\|\s*`?' + re.escape(req_id) + r'`?\s*\|.*$', ledger_text, re.M)
    return m.group(0) if m else None


def load_rulings(path=RULINGS_FILE, ledger=REQ_LEDGER):
    """只收能在用户要求总账里找到 REQ 条目的裁定；找不到的列入 rejected。"""
    d = json.loads(Path(path).read_text(encoding='utf-8'))
    text = Path(ledger).read_text(encoding='utf-8') if Path(ledger).exists() else ''
    ok, rejected = [], []
    for r in d.get('rulings', []):
        ent = ledger_entry_text(text, r.get('req_id', ''))
        if not ent:
            rejected.append({'req_id': r.get('req_id'), 'reason': 'ledger_entry_not_found'})
            continue
        r = dict(r)
        r['_ledger_entry_sha256'] = sha256_text(ent)
        r['_sha'] = sha256_text(canon({k: v for k, v in r.items() if not k.startswith('_')}) + r['_ledger_entry_sha256'])
        r['_basis_missing'] = [b for b in r.get('basis', []) if isinstance(b, str) and b.startswith('/')
                               and not Path(b.split('#')[0]).exists()]
        ok.append(r)
    return {'version': d.get('version'), 'path': str(path), 'ledger': str(ledger),
            'ledger_sha256': sha256_text(text) if text else None, 'rulings': ok, 'rejected': rejected,
            '_sha': sha256_text(canon([r['_sha'] for r in ok]))}


def ruling_hits(rulings, key, subqs, book=None):
    """命中本题的裁定：[(裁定, 说明, 覆盖情况)]。覆盖情况 full=书中各落位全在裁定范围内；
    partial=裁定只限某几问，书中另有不在范围内的小问或整题落位（这些照常判定，不沾裁定）。"""
    exam = key.rsplit('-Q', 1)[0]
    out = []
    for r in rulings['rulings']:
        sc = r.get('scope', {})
        if sc.get('books') and book not in sc['books']:
            continue  # 只属某册的特批，不外推到别册
        if sc.get('keys') and key not in sc['keys']:
            continue
        if sc.get('exam_ids') and exam not in sc['exam_ids']:
            continue
        if not sc.get('keys') and not sc.get('exam_ids'):
            continue
        # subqs 里的 None 表示书中有不写小问的整题落位
        whole = (None in subqs) or not subqs
        sq = sorted({x for x in subqs if x})
        note, cover = None, {'mode': 'full', 'covered': sq, 'uncovered': []}
        if sc.get('subq'):
            inside = sorted(set(sq) & set(sc['subq']))
            outside = sorted(set(sq) - set(sc['subq'])) + (['整题'] if whole else [])
            if not inside and not whole:
                continue
            if outside:
                cover = {'mode': 'partial', 'covered': inside or list(sc['subq']), 'uncovered': outside}
                note = '裁定只覆盖第%s问；书中%s不在范围内、照常判定' % (
                    '、'.join(inside or sc['subq']), '、'.join(('第%s问' % x) if x != '整题' else '不写小问的整题落位' for x in outside))
        out.append((r, note, cover))
    return out


# ---------------------------------------------------------------- 题源写法 → 题键

def _sub(m):
    g = m.groupdict()
    return g.get('s1') or g.get('s2') or g.get('s3')


def norm_title(text):
    t = re.sub(r'\s+', '', (text or '').translate(FW))
    # “高考北京卷”“北京卷”都按北京高考；先换整词，避免变成“高考北京高考”
    return t.replace('高考北京卷', '北京高考').replace('北京卷', '北京高考')


def match_override(keymap, parsed):
    for ov in keymap.get('overrides', []):
        mt = ov.get('match', {})
        if all(parsed.get(k) == v for k, v in mt.items()):
            return ov
    return None


def exam_label(m, t):
    """题源写法里“卷名”那一段（不含题号），用于查同名多卷。"""
    s = t[m.start():m.start('n')] if m.group('n') else t[m.start():m.end()]
    return re.sub(r'(选择题?|主观题?|非选择题)?第?$', '', s)


def resolve_title(text, bank, keymap, probe_text=None):
    """返回解析结果 dict；status: ok / ambiguous / exam_not_in_bank / no_question_md / unparsed。只解析第一个题源。"""
    raw = text
    t = norm_title(text)
    r = {'raw': raw, 'key': None, 'subq': None, 'basis': None, 'status': 'unparsed', 'notes': []}
    m = KEY_RX.search(t)
    if m:
        r.update(key='BJ-%s-%s-%s-Q%s' % m.groups()[:4], subq=m.group(5), basis='direct_key')
        return _finish(r, bank, keymap)
    m = SY_TITLE_RX.search(t)
    if m and m.group('reg'):
        return _resolve_school_year(r, m, t, bank, keymap, probe_text)
    m = TITLE_RX.search(t)
    if not m:
        return r
    y, reg, stg, half, n = m.group('y'), m.group('reg'), m.group('stg'), m.group('half'), m.group('n')
    r['parsed'] = {'year': y, 'region': reg, 'stage': stg, 'half': half, 'q': n}
    r['exam_label'] = exam_label(m, t)
    r['subq'] = _sub(m)
    if stg == '高考':
        if reg:
            r['notes'].append('高考题源带区名，按北京高考处理')
        exam = 'BJ-%s-BJ-GAOKAO' % y
    elif not reg:
        r['notes'].append('缺区名')
        return r
    else:
        exam = 'BJ-%s-%s-%s' % (y, REGIONS[reg], STAGES[stg])
    r['basis'] = 'generic'
    ov = match_override(keymap, r['parsed'])
    if ov:
        r['override'] = ov['id']
        r['basis'] = 'override:' + ov['id']
        if ov.get('candidates'):
            return _pick(r, ['%s-Q%s' % (e, n) for e in ov['candidates']], bank, keymap, probe_text)
        exam = ov['exam_id']
    r['key'] = '%s-Q%s' % (exam, n)
    return _finish(r, bank, keymap)


def _resolve_school_year(r, m, t, bank, keymap, probe_text):
    """“2022—2023学年第二学期海淀期中”这类写法：先换算成年份＋上/下过身份更正表，再查学年候选。"""
    y1, y2, sem, reg, stg, n = (m.group(x) for x in ('y1', 'y2', 'sem', 'reg', 'stg', 'n'))
    sy = '%s-%s学年' % (y1, y2)
    r.update(subq=_sub(m), basis='school_year', semester=('第%s学期' % sem) if sem else None,
             exam_label=exam_label(m, t),
             parsed={'school_year': sy, 'semester': sem, 'region': reg, 'stage': stg, 'q': n})
    if sem:
        cal = {'year': y1 if sem == '一' else y2, 'region': reg, 'stage': stg, 'half': '上' if sem == '一' else '下'}
        ov = match_override(keymap, cal)
        if ov:
            r['override'] = ov['id']
            r['basis'] = 'school_year+override:' + ov['id']
            if ov.get('candidates'):
                return _pick(r, ['%s-Q%s' % (e, n) for e in ov['candidates']], bank, keymap, probe_text)
            r['key'] = '%s-Q%s' % (ov['exam_id'], n)
            return _finish(r, bank, keymap)
    cands, conflict = bank.school_year_candidates(sy, reg, stg, sem, keymap)
    force = []
    if stg == '期中' and (sem == '二' or (sem is None and reg == '海淀')):
        # 第二学期的“期中练习”，海淀惯例是一模；海淀不写学期时也列为候选，交探针区分
        yimo = 'BJ-%s-%s-YIMO' % (y2, REGIONS[reg])
        if bank.exam_known(yimo) and yimo not in cands:
            cands.append(yimo)
            r['notes'].append('第二学期期中练习按海淀惯例可能是一模（%s），列为候选' % yimo)
        if sem == '二' and reg != '海淀':
            force.append('second_semester_qizhong_non_haidian')
    if conflict:
        r['notes'].append('exams.csv 学年登记与身份核查冲突：%s（见身份更正表 school_year_corrections）' % '、'.join(conflict))
        cands += [c for c in conflict if c not in cands]
        force.append('school_year_conflict')
    keys = ['%s-Q%s' % (e, n) for e in cands]
    if force:
        r['candidates'] = [k for k in keys if bank.md_path(k).exists()] or keys
        r['status'] = 'ambiguous'
        r['ambiguous_reason'] = force
        if probe_text:
            r['probe_scores'] = {k: probe(probe_text, bank.md_path(k))[0] for k in r['candidates']}
        return r
    return _pick(r, keys, bank, keymap, probe_text)


def resolve_all(text, bank, keymap, probe_text=None):
    """一行里可能写了多个题源（“A 与 B”）：逐个解析，返回列表；只有一个时与 resolve_title 相同。"""
    t = norm_title(text)
    spans = []
    for rx in (KEY_RX, SY_TITLE_RX, TITLE_RX):
        for m in rx.finditer(t):
            if rx is SY_TITLE_RX and not m.group('reg'):
                continue
            if rx is not KEY_RX and not m.group('n'):
                continue
            a, b = m.span()
            if any(a < y and x < b for x, y in spans):
                continue
            spans.append((a, b))
    spans.sort()
    if len(spans) <= 1:
        return [resolve_title(text, bank, keymap, probe_text)]
    out = []
    for i, (a, b) in enumerate(spans):
        r = resolve_title(t[a:b], bank, keymap, probe_text)
        r['raw'] = text
        r['raw_part'] = t[a:b]
        r['multi_source'] = '%d/%d' % (i + 1, len(spans))
        out.append(r)
    return out


def _pick(r, cand_keys, bank, keymap, probe_text):
    cand_keys = [k for k in cand_keys if bank.md_path(k).exists()] or cand_keys
    r['candidates'] = cand_keys
    if len(cand_keys) == 1:
        r['key'] = cand_keys[0]
        return _finish(r, bank, keymap)
    if cand_keys and probe_text:
        scores = {k: probe(probe_text, bank.md_path(k))[0] for k in cand_keys}
        ranked = sorted(scores.values(), reverse=True)
        best, second = ranked[0], (ranked[1] if len(ranked) > 1 else 0)
        r['probe_scores'] = scores
        # 与 identity_alternative 同一门槛：最高≥PROBE_MIN 且领先≥PROBE_LEAD 才自动定案
        if best >= PROBE_MIN and best - second >= PROBE_LEAD:
            r['key'] = [k for k, v in scores.items() if v == best][0]
            r['basis'] += '+probe'
            return _finish(r, bank, keymap)
        r['notes'].append('探针分不出（最高 %d、次高 %d；门槛：≥%d 且领先≥%d）' % (best, second, PROBE_MIN, PROBE_LEAD))
    r['status'] = 'ambiguous'
    return r


def _finish(r, bank, keymap):
    exam = r['key'].rsplit('-Q', 1)[0]
    red = (keymap.get('redirect_exams') or {}).get(exam)
    if red:
        r['notes'].append('%s 为已撤销登记，按 %s 取（依据见 keymap_overrides.json）' % (exam, red['to']))
        r['key'] = red['to'] + '-Q' + r['key'].rsplit('-Q', 1)[1]
        r['basis'] = (r['basis'] or '') + '+redirect'
        exam = red['to']
    if not bank.exam_known(exam):
        r['status'] = 'exam_not_in_bank'
    elif not bank.md_path(r['key']).exists():
        r['status'] = 'no_question_md'
    else:
        r['status'] = 'ok'
    return r


# ---------------------------------------------------------------- 题级 MD 切分与角色

def split_md(text):
    lines = text.split('\n')
    heads = [i for i, ln in enumerate(lines) if ln.startswith('## ')]
    out = []
    for j, i in enumerate(heads):
        e = heads[j + 1] if j + 1 < len(heads) else len(lines)
        body = '\n'.join(lines[i + 1:e])
        out.append({'heading': lines[i][3:].strip(), 'line_start': i + 1, 'line_end': e, 'body': body})
    pre = '\n'.join(lines[:heads[0]]) if heads else text
    return pre, out


def body_empty(body):
    # 只去掉题库自加的警示引用行；细则原文本身也可能整段写成引用块
    t = '\n'.join(ln for ln in body.split('\n') if not re.match(r'^\s*>\s*(⚠|注意|说明)', ln)).strip()
    if len(norm_text(t)) < 15:
        return True
    return bool(re.fullmatch(r'[（(][^）)]*(未找到|无)[^）)]*[）)]', t))


def classify(h, T, key):
    """小节标题 → (层, 角色依据)。先认题库标准别名，再按标题推断。"""
    if h in T['e1'] or h in T['qid_e1'].get(key, ()):
        return 'e1', 'bank_alias'
    if h in T['e3']:
        return 'e3', 'bank_alias'
    if h in T['student']:
        return 'student', 'bank_alias'
    if h in T['stem'] or h in T['guided_stem']:
        return 'stem', 'bank_alias'
    if h in T['structure']:
        return 'stem_adj', 'bank_alias'
    if h in T['unknown']:
        return 'candidate', 'bank_alias'
    if h in T['default_passthrough']:
        return 'stem', 'bank_passthrough'
    return classify_regex(h)


def classify_regex(h):
    """题库未登记的标题：主体部分定角色，括注里的“与××分层”“来自××”只作限定，不定角色。"""
    main = re.sub(r'[（(][^）)]*[）)]', '', h).strip()
    if re.search(r'OFFICIAL_ANSWER|SCORING|RUBRIC', main, re.I):
        return 'e1', 'heading_regex'
    if '学生' in main or 'STUDENT' in main.upper():
        return 'student', 'heading_regex'
    if h.startswith(('评分材料来源块', '待确认材料来源块')):
        return 'candidate', 'heading_regex'
    if re.search(r'边界|覆盖|页级|状态|来源角色|审计|复核|修复|身份', main) and not re.search(r'原文|全文|细则|主载体', main):
        return 'meta', 'heading_regex'
    if E1_RX.search(main):
        return ('candidate' if E1_NEG_RX.search(h) else 'e1'), 'heading_regex'
    if '候选' in main and re.search(r'评分|细则|答案|材料', main):
        return 'candidate', 'heading_regex'
    if re.search(r'评分材料|评分参考|等级', main):
        # “评分材料（同卷正式材料…）”这类：主体只写评分材料，括注写明正式
        if '评分材料' in main and '正式' in h and not E1_NEG_RX.search(h):
            return 'e1', 'heading_regex'
        return 'candidate', 'heading_regex'
    if re.search(r'参考答案|答案键|E3|参考作答|内附答案|答案层|答案/讲评|答案及|答案与', main):
        return 'e3', 'heading_regex'
    if META_RX.search(main) and not re.search(r'题面|原题|题目', main):
        return 'meta', 'heading_regex'
    if re.search(r'讲评|教研|试题分析|解题提示|解析|详解|讲解|分析|教学建议', main):
        return 'lecture', 'heading_regex'
    if re.search(r'题面|原题|题目原文|题目|逐字转写|E0|原卷', main) and not re.search(r'页图|图像|资产|图文|图表|结构|框线|版面', main):
        return 'stem', 'heading_regex'
    if re.search(r'页图|图像|图文|图表|结构|框线|版面|题图', main):
        return 'stem_adj', 'heading_regex'
    return 'meta', 'heading_regex'


LINK_MD_RX = re.compile(r'\]\(((?:sources|coverage|lineage|transcripts)/[^)\s#]+\.md)(?:#([^)\s]+))?\)')


def _strip_refs(t):
    """去掉链接、图片、行内代码（不动代码块：细则原文常整段放在 ```text 里）。"""
    t = re.sub(r'!?\[[^\]]*\]\([^)]*\)', '', t)
    return re.sub(r'`[^`\n]{1,300}`', '', t)


TAG_RX = re.compile(r'^\s*(?:[-*]\s*)?\[(?:DOCX|PDF|PPTX|XML|OCR)?\s*[A-Za-z]{0,6}\s*[\d\-–—,，~]+[^\]]{0,12}\](?!\()', re.I)


META_KEY_RX = re.compile(r'^\s*[-*>]?\s*(?:\*\*)?(?:来源|证据|E1\s*来源|E1\s*源文件|E1\s*状态|正式细则来源|同卷正式评分载体|评分载体|载体事实|'
                         r'原件页|原图|去重\s*SHA|SHA-?256|已匹配细则|定位|配对状态|身份|状态|细则\s*PDF\s*关联页|正式细则渲染证据)'
                         r'[^：:\n]{0,10}[：:]')


def _is_eng_line(s):
    """一行是不是工程说明/出处行：带链接或行内代码、以“来源：/证据：/状态：”这类出处键开头，
    或工程词密度≥每百字 4 个（先去掉“[DOCX P103]”这类行首定位标签）。"""
    if re.search(r'\]\(|`', s) or META_KEY_RX.match(s):
        return True
    s2 = TAG_RX.sub('', s)
    n = len(ENG_RX.findall(s2))
    return n > 0 and n * 100.0 / max(len(re.findall(r'[一-鿿]', s2)), 1) >= 4


def section_features(body):
    """E1 小节的机械特征：正文汉字数、工程词密度、非工程行（“正文行”）汉字数与分值标记数。"""
    plain = _strip_refs(body)
    cjk = len(re.findall(r'[一-鿿]', plain))
    eng = len(ENG_RX.findall('\n'.join(TAG_RX.sub('', ln) for ln in plain.split('\n'))))
    content, content_marks = 0, 0
    in_code = False
    for ln in body.split('\n'):
        s = ln.strip()
        if s.startswith('```'):
            in_code = not in_code
            continue
        if not s or (not in_code and s.startswith('#')):
            continue
        if in_code or not _is_eng_line(s):
            content += len(re.findall(r'[一-鿿]', s))
            content_marks += len(SCORE_RX.findall(s))
    return {'cjk': cjk, 'eng': eng, 'eng_per100': round(eng * 100.0 / max(cjk, 1), 1), 'content_cjk': content,
            'content_score_marks': content_marks,
            'score_marks': len(SCORE_RX.findall(plain)),
            'refs': len(re.findall(r'\]\([^)]+\)', body)) + len(re.findall(r'`[^`\n]{1,300}`', body))}


def is_pointer_only(body):
    """E1 小节只写出处（“完整转写见[…](…)”“物理页N”）或工程说明、没有细则正文。
    判据：不含工程词与链接的“正文行”汉字<60 且正文行里没有分值标记，并且有出处指针或工程词密集。
    （原来只看全节有没有“N分”，工程说明里提到“2个点4分”就会被误收为 E1 正文。）"""
    f = section_features(body)
    ptr = re.search(r'\]\([^)]+\)|`[^`]+\.(?:pdf|docx?|pptx|md|png)`|物理页|载体|lines?\s*\d|见下方|见上方|详见', body, re.I)
    if f['content_cjk'] >= 60 or f['content_score_marks'] > 0:
        return False
    return bool(ptr) or (f['cjk'] < 400 and f['eng_per100'] >= 3.5)


def body_declares_absent(body):
    """E1 小节正文只是在说“未找到/未提供正式细则”：按空处理，不当 E1。"""
    f = section_features(body)
    return bool(ABSENT_RX.search(body)) and f['content_cjk'] < 150 and f['score_marks'] <= 1


def anchored_block(text, anchor):
    """链接目标文件里 <a id="X"> 到 <a id="X-end">（或下一个锚点）之间的原文；无锚点取全文。"""
    lines = text.split('\n')
    if not anchor:
        return 1, len(lines), text
    start = None
    for i, ln in enumerate(lines):
        if re.search(r'<a\s+(?:id|name)="%s"' % re.escape(anchor), ln):
            start = i
            break
    if start is None:
        return None
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if re.search(r'<a\s+(?:id|name)="%s-end"' % re.escape(anchor), lines[j]):
            end = j
            break
        if re.search(r'<a\s+(?:id|name)="(?![^"]*-end")', lines[j]):
            end = j
            break
    return start + 2, end, '\n'.join(lines[start + 1:end])


def question_blocks(text, q):
    """无锚点的链接文件（多题合一的转写/支持文件）里，只截标题点到本题（Q17、第17题）的小节原文。
    返回 [(起行, 止行, 原文)]；找不到本题小节返回 []（调用方退回整份文件）。"""
    lines = text.split('\n')
    heads = []
    for i, ln in enumerate(lines):
        m = re.match(r'^(#{1,4})\s', ln)
        if m:
            heads.append((i, len(m.group(1)), ln))
    qrx = re.compile(r'(?:Q|第)0?%d(?!\d)' % q)
    hits = [h for h in heads if qrx.search(h[2]) and len(set(re.findall(r'Q0?(\d{1,2})', h[2]))) <= 1]
    if not hits:
        return []
    lvl = min(h[1] for h in hits)
    out = []
    for i, l, ln in hits:
        if l != lvl:
            continue
        end = len(lines)
        for j, l2, ln2 in heads:
            if j > i and l2 <= lvl:
                end = j
                break
        out.append((i + 1, end, '\n'.join(lines[i:end])))
    return out


def linked_excerpts(exam_dir, sec, key=None, limit=20000):
    """跟随 E1 小节里的卷内 MD 链接，截取被指向的原文段（有锚点按锚点，无锚点先找本题小节）。只读卷目录内文件。"""
    out, notes = [], []
    q = int(key.rsplit('-Q', 1)[1]) if key else None
    for rel, anchor in dict.fromkeys(LINK_MD_RX.findall(sec['body'])):
        p = Path(exam_dir) / rel
        if not is_under(p, exam_dir) or not p.exists():
            notes.append('linked_missing:%s' % rel)
            continue
        raw = p.read_bytes()
        text = raw.decode('utf-8', errors='replace')
        pieces = []
        if not anchor and q:
            pieces = [(a, b, body, '本题小节') for a, b, body in question_blocks(text, q)]
        if not pieces:
            got = anchored_block(text, anchor)
            if not got:
                notes.append('anchor_not_found:%s#%s' % (rel, anchor))
                continue
            pieces = [got + (('锚点 #' + anchor) if anchor else '整份文件（未找到本题小节）',)]
        for l0, l1, body, how in pieces:
            if len(body) > limit:
                notes.append('linked_too_large:%s' % rel)
                continue
            out.append({'heading': '%s ／ 链接 %s%s（%s）' % (sec['heading'], rel, ('#' + anchor) if anchor else '', how),
                        'line_start': l0, 'line_end': l1, 'body': body, 'linked_file': str(p),
                        'linked_file_sha256': sha256_bytes(raw)})
    return out, notes


def e1_subsections(sec):
    """工程容器小节（如“来源角色：按证据单元分层”）里用 ### 标出的 E1 子节，单独切出。"""
    lines = sec['body'].split('\n')
    heads = [i for i, ln in enumerate(lines) if ln.startswith('### ')]
    out = []
    for j, i in enumerate(heads):
        sub = lines[i][4:].strip()
        main = re.sub(r'[（(][^）)]*[）)]', '', sub)
        if sub.startswith('来源') or not E1_RX.search(main) or E1_NEG_RX.search(sub):
            continue
        e = heads[j + 1] if j + 1 < len(heads) else len(lines)
        body = '\n'.join(lines[i + 1:e])
        out.append({'heading': '%s ／ %s' % (sec['heading'], sub), 'line_start': sec['line_start'] + i + 1,
                    'line_end': sec['line_start'] + e, 'body': body})
    return out


def guide_fields(sections):
    for s in sections:
        if s['heading'] == '读取指引（机器可读）':
            return {k.strip(): v.strip().strip('`') for k, v in
                    re.findall(r'^-\s*([^:：\n]+?)\s*[:：]\s*(.*)$', s['body'], re.M)}
    return {}


def adopted_stem_heading(sections, T, guide):
    """与 bank.py adopted_stem 同口径：读取指引点名的题面小节优先，其次按别名表顺序。"""
    have = {s['heading'] for s in sections}
    g = guide.get('采用题面小节', '')
    if g in T['guided_stem'] and g in have:
        return g, 'bank_guide'
    for t in T['stem']:
        if t in have:
            return t, 'bank_alias'
    return None, None


# ---------------------------------------------------------------- 看原页账本

VIEW_SCHEMA = 'qpack-view/1'
VIEW_REQUIRED = ('schema', 'key', 'layer', 'by', 'agent_id', 'at', 'md_sha256', 'verdict')


def view_row_problems(d):
    """看页账本一行的格式问题（ledger-add 追加前逐行校验用）。"""
    if not isinstance(d, dict):
        return ['not_object']
    why = ['missing:%s' % k for k in VIEW_REQUIRED if k not in d]
    if d.get('schema') != VIEW_SCHEMA:
        why.append('schema!=%s' % VIEW_SCHEMA)
    if d.get('by') not in ('main', 'subagent'):
        why.append('by_invalid')
    if d.get('verdict') not in ('exact', 'corrected', 'mismatch'):
        why.append('verdict_invalid')
    if not KEY_RX.fullmatch(str(d.get('key') or '')):
        why.append('key_invalid')
    return why


def load_view_ledger(paths):
    rows = []
    for p in paths or []:
        if not Path(p).exists():
            continue
        for i, ln in enumerate(open(p, encoding='utf-8')):
            ln = ln.strip()
            if not ln:
                continue
            try:
                d = json.loads(ln)
            except Exception:
                continue
            if not isinstance(d, dict):
                continue
            d['_file'], d['_line'] = str(p), i + 1
            d['_sha'] = sha256_text(ln)
            rows.append(d)
    by = defaultdict(list)
    for d in rows:
        by[(d.get('key'), (d.get('layer') or 'e1').lower())].append(d)
    return by, sha256_text(canon(sorted(d['_sha'] for d in rows)))


def unreadable_images(bank, exam, key, residual_rows=None):
    """bounded_residual 里写明“渲染为空白/未显示中文”的页图（渲染环境问题，不能当原页看）。返回 {绝对路径: 原文条目}。"""
    out = {}
    rows = residual_rows if residual_rows is not None else bank.residuals(exam, key)
    exam_dir = bank.qdir / exam
    for row in rows:
        e = row['entry']
        txt = canon(e)
        if not BLANK_RENDER_RX.search(txt):
            continue
        loc = str(e.get('location') or '') + ' ' + str(e.get('image') or e.get('source_image') or '')
        names = re.findall(r'[\w./-]+\.png', loc)
        # “rubric-01.png 至 rubric-07.png”展开成区间
        for a, b in re.findall(r'([\w./-]*?\d+)\.png\s*(?:至|到|—|–|-|~)\s*([\w./-]*?\d+)\.png', loc):
            pa = re.match(r'(.*?)(\d+)$', a)
            pb = re.match(r'(.*?)(\d+)$', b)
            if pa and pb:
                w = len(pa.group(2))
                for k in range(int(pa.group(2)), int(pb.group(2)) + 1):
                    names.append('%s%0*d.png' % (pa.group(1), w, k))
        hits = set()
        for nm in names:
            base = Path(nm).name
            for p in exam_dir.rglob(base):
                hits.add(str(p))
        # “PPTX s8 的静态渲染图”“slide 8”这类写法：按 s-08.png / slide-08.png 找
        for n in re.findall(r'(?:\bs|slide\s*)(\d{1,3})\b', loc, re.I):
            for pat in ('s-%02d.png' % int(n), 's-%d.png' % int(n), 'slide-%02d.png' % int(n)):
                for p in exam_dir.rglob(pat):
                    hits.add(str(p))
        for h in hits:
            out[h] = e
    return out


def view_evidence_problems(e, bank, key, unreadable=None):
    """账本条目的原页证据是否站得住：页图须是本卷目录（questions/<卷>/ 或 evidence/<本卷来源>/）里的 PNG/JPEG，
    且不是登记为渲染空白的页；或给出本卷来源 source_id 与不超过登记页数的页码。"""
    exam = key.rsplit('-Q', 1)[0]
    sids = {s['source_id'] for s in bank.exam_sources(exam)}
    st = bank.state(exam) or {}
    # 验收记录的 source_roles（角色→source_id）也算本卷来源
    sids |= set(re.findall(r'\bS[0-9a-f]{12}\b', canon(st.get('source_roles') or {})))
    why, warn = [], []
    png, sid = e.get('page_png'), e.get('source_id')
    if not png and not sid:
        why.append('no_page_evidence')
    if png:
        p = Path(png)
        if not p.exists():
            why.append('page_png_missing')
        else:
            if p.suffix.lower() not in ('.png', '.jpg', '.jpeg') or not image_magic_ok(p):
                why.append('page_png_not_image')
            in_exam = is_under(p, bank.qdir / exam) or any(is_under(p, bank.root / 'evidence' / s) for s in sids)
            if not in_exam:
                why.append('page_png_not_of_exam')
            if unreadable and str(p.resolve()) in {str(Path(x).resolve()) for x in unreadable}:
                why.append('page_png_unreadable(bounded_residual)')
            if in_exam and bank.md_path(key).exists() and p.name not in bank.md_path(key).read_text(encoding='utf-8', errors='replace'):
                warn.append('page_png_not_cited_in_md')
    if sid:
        if sid not in sids:
            why.append('source_not_of_exam')
        else:
            pg = e.get('page')
            total = bank.source_pages(sid, exam)
            if not isinstance(pg, int) or pg < 1:
                why.append('page_invalid')
            elif total and pg > total:
                why.append('page_out_of_range(>%d)' % total)
            elif not total:
                warn.append('page_count_unknown')
    return why, warn


def ledger_level(entries, md_sha, layer_secs, bank, key, unreadable=None):
    """账本条目 → (等级, 明细)。登记时的 MD/小节/页图/源 SHA 与现状不符、原页证据不属本卷或不是图片，一律判无效不计等级。
    该层题库没有正文时不给已核等级（切片里没有可核的文字）；verdict=corrected/mismatch 表示原页与题库原文不符，不升等级。"""
    best, detail = None, []
    text_secs = [s for s in layer_secs if not s.get('pointer_only')]
    cur_secs = {s['section_sha256'] for s in text_secs}
    for e in entries:
        why = []
        if e.get('md_sha256') and e['md_sha256'] != md_sha:
            if not (e.get('section_sha256') and e['section_sha256'] in cur_secs):
                why.append('md_changed')
        if e.get('section_sha256') and e['section_sha256'] not in cur_secs:
            why.append('section_changed')
        if not e.get('md_sha256') and not e.get('section_sha256'):
            why.append('unbound_no_sha')
        ev_why, ev_warn = view_evidence_problems(e, bank, key, unreadable)
        why += ev_why
        png = e.get('page_png')
        if png and e.get('page_png_sha256') and Path(png).exists() and file_sha(png) != e['page_png_sha256']:
            why.append('page_image_changed')
        if e.get('source_id') and e.get('source_sha256'):
            reg = (bank.sources.get(e['source_id']) or {}).get('sha256')
            if reg and reg != e['source_sha256']:
                why.append('source_changed')
        by = (e.get('by') or '').lower()
        lv = 'main_viewed' if by == 'main' else 'subagent_viewed'
        verdict = e.get('verdict') or 'exact'
        counts = not why and verdict == 'exact' and bool(text_secs)
        detail.append({'by': by, 'agent_id': e.get('agent_id'), 'at': e.get('at'), 'verdict': verdict,
                       'page_png': png, 'source_id': e.get('source_id'), 'page': e.get('page'),
                       'section_sha256': e.get('section_sha256'),
                       'valid': not why, 'stale_reasons': why, 'warnings': ev_warn, 'counts_for_level': counts,
                       'no_bank_text_in_layer': not text_secs, 'ledger': '%s:%s' % (e['_file'], e['_line'])})
        if counts:
            best = level_max([best, lv])
    return best, detail


# ---------------------------------------------------------------- 单题分析

def md_qtype(text, key):
    """题型：先认题级 MD 的“题型：选择题/非选择题”，没有时按北京卷结构（第1—15题为选择题）推断。"""
    m = QTYPE_RX.search(text or '')
    if m:
        return ('choice' if m.group(1) == '选择题' else 'subjective'), 'md'
    q = int(key.rsplit('-Q', 1)[1])
    return ('choice' if q <= 15 else 'subjective'), 'qnum'


def analyse_key(bank, key, rulings, ledger_by, subqs=(), layers=DEFAULT_LAYERS, max_chars=0,
                hash_sources=True, keep_text=True, book=None):
    exam = key.rsplit('-Q', 1)[0]
    mdp = bank.md_path(key)
    task = bank.tasks.get(exam) or {}
    st = bank.state(exam) or {}
    rec = OrderedDict(key=key, exam_id=exam, md_path=str(mdp), md_exists=mdp.exists(),
                      manifest_status=task.get('status'))
    fp = OrderedDict(tables_sha=bank.tables_sha)
    if not rec['md_exists']:
        rec.update(e1_status='missing', e1_level='missing', stem_level='missing', layers={},
                   reasons=['no_question_md'], qtype=md_qtype('', key)[0], qtype_basis='qnum')
        fp.update(md_sha256=None, manifest_status=task.get('status'))
        rec['fingerprint'] = fp
        return rec
    raw = mdp.read_bytes()
    text = raw.decode('utf-8', errors='replace')
    md_sha = sha256_bytes(raw)
    qhash = (st.get('question_hashes') or {}).get(key)
    accepted = task.get('status') == '已验收' and st.get('accepted') is True
    reasons = []
    if task.get('status') != '已验收':
        reasons.append('exam_not_accepted(manifest=%s)' % task.get('status'))
    elif not st:
        reasons.append('no_state_file')
    elif st.get('accepted') is not True:
        reasons.append('state_not_accepted')
    if accepted and not qhash:
        reasons.append('no_question_hash_in_state')
    elif accepted and qhash != md_sha:
        reasons.append('md_changed_after_acceptance')
    bank_ok = accepted and qhash == md_sha
    pre, secs = split_md(text)
    flags = []
    # 文件开头若还留着“候选/未晋升”横幅，只作提示，不改等级（验收记录以 SHA 为准），交题库线清理
    if UNVERIFIED_RX.search(pre) or re.search(r'blocked|不是整卷验收稿|隔离', pre):
        flags.append('md_preamble_says_candidate')
    guide = guide_fields(secs)
    T = bank.tables
    qtype, qtype_basis = md_qtype(text, key)
    residuals = bank.residuals(exam, key)
    unreadable = unreadable_images(bank, exam, key, residuals)
    rec.update(md_sha256=md_sha, state_question_sha256=qhash, state_status=st.get('status'),
               accepted_at=st.get('accepted_at'), bank_accept_ok=bank_ok, reasons=reasons, flags=flags,
               guide_rubric_status=guide.get('评分关系状态'), qtype=qtype, qtype_basis=qtype_basis,
               residuals=residuals)
    fp.update(md_sha256=md_sha, manifest_status=task.get('status'), state_status=st.get('status'),
              state_accepted=st.get('accepted'), accepted_at=st.get('accepted_at'), state_qhash=qhash,
              residuals_sha=sha256_text(canon(residuals)))

    stem_h, stem_basis = adopted_stem_heading(secs, T, guide)
    guide_e1 = guide.get('采用评分小节')
    items = []
    for s in secs:
        layer, basis = classify(s['heading'], T, key)
        if guide_e1 and s['heading'] == guide_e1:
            layer, basis = 'e1', 'bank_guide'
        if layer == 'stem' and stem_h and s['heading'] == stem_h:
            basis = stem_basis
        elif layer == 'stem' and not stem_h and s['heading'] == guide.get('采用题面小节'):
            basis = 'bank_guide_unlisted'
        s2 = dict(s, layer=layer, bank_layer=layer, role_basis=basis, empty=body_empty(s['body']),
                  section_sha256=sha256_text(s['body']))
        items.append(s2)
        if layer == 'meta' and basis == 'heading_regex':
            for sub in e1_subsections(s):
                items.append(dict(sub, layer='e1', bank_layer='meta', role_basis='subheading_regex',
                                  empty=body_empty(sub['body']), section_sha256=sha256_text(sub['body'])))
    # E1 小节正文只是在声明“未找到/未提供正式细则”的，按空处理
    for s in items:
        if s['layer'] == 'e1' and not s['empty'] and body_declares_absent(s['body']):
            s['empty'] = True
            s['declared_absent'] = True

    # 用户裁定叠加：只动角色，不改原文；限定小问的裁定只管范围内的小问
    rhits = ruling_hits(rulings, key, list(subqs), book)
    rec_rulings, e1_pointers, extra_layers, exception, exception_partial = [], [], set(), None, None
    for r, note, cover in rhits:
        eff = r.get('effect', {})
        entry = {'req_id': r['req_id'], 'type': eff.get('type'), 'note': eff.get('note'), 'scope_note': note,
                 'coverage': cover, 'bank_position': r.get('bank_position')}
        if eff.get('type') == 'promote_section':
            hrx, brx = re.compile(eff.get('heading_regex', '.')), re.compile(eff.get('body_regex', '.'))
            for s in items:
                if hrx.search(s['heading']) and brx.search(s['body']) and not s['empty']:
                    s['layer'], s['role_basis'] = eff.get('role', 'e1'), 'ruling:' + r['req_id']
                    entry.setdefault('promoted', []).append(s['heading'])
        elif eff.get('type') == 'page_pointer':
            for pg in eff.get('pages', []):
                p = bank.root / pg
                e1_pointers.append({'page_png': str(p), 'exists': p.exists(), 'req_id': r['req_id']})
        elif eff.get('type') == 'e1_exception':
            if qtype == 'choice':
                entry['not_applied'] = '选择题不涉及正式评分细则，具名例外不套用'
            elif cover['mode'] == 'partial':
                exception_partial = {'req_id': r['req_id'], 'covered': cover['covered'], 'uncovered': cover['uncovered']}
                extra_layers.update(eff.get('add_layers', []))
            else:
                exception = r['req_id']
                extra_layers.update(eff.get('add_layers', []))
        src = r.get('source') or {}
        if src.get('source_id'):
            reg = (bank.sources.get(src['source_id']) or {}).get('sha256')
            entry['source_registered_sha256'] = reg
            entry['source_sha_match'] = (reg == src.get('sha256')) if reg else None
        rec_rulings.append(entry)
    fp['rulings'] = {r['req_id']: r['_sha'] for r, _, _ in rhits}

    # 选小节：题面只取一节（外加附图表），E1 全取
    want = list(dict.fromkeys(list(layers) + sorted(extra_layers)))
    if 'stem' in want:
        want.append('stem_adj')
    picked = defaultdict(list)
    alternatives = defaultdict(list)
    stems = [s for s in items if s['layer'] == 'stem' and not s['empty']]
    stem_alts = []
    if stems:
        pri = {'bank_guide': 0, 'bank_alias': 1, 'bank_guide_unlisted': 2, 'heading_regex': 3, 'bank_passthrough': 4}
        g_stem = guide.get('采用题面小节')
        stems.sort(key=lambda s: (s['heading'] != stem_h, s['heading'] != g_stem, bool(UNVERIFIED_RX.search(s['heading'])),
                                  pri.get(s['role_basis'], 9), s['line_start']))
        picked['stem'].append(stems[0])
        alternatives['stem'] = [s['heading'] for s in stems[1:]]
        stem_alts = stems[1:]
    for s in items:
        if s['layer'] in ('stem',) or s['empty']:
            if s['layer'] == 'e1' and s['empty']:
                rec.setdefault('empty_e1_headings', []).append(s['heading'])
                if s.get('declared_absent'):
                    rec.setdefault('e1_declared_absent', []).append(s['heading'])
            continue
        picked[s['layer']].append(s)
    # E1 只写出处指针的，跟随卷内链接截取被指向的转写原文
    link_notes = []
    for s in list(picked.get('e1', [])):
        s['pointer_only'] = is_pointer_only(s['body'])
        if s['pointer_only']:
            got, notes = linked_excerpts(mdp.parent, s, key)
            link_notes += notes
            for g in got:
                picked['e1'].append(dict(g, layer='e1', bank_layer='e1', role_basis=s['role_basis'] + '+link',
                                         empty=body_empty(g['body']), section_sha256=sha256_text(g['body'])))
    if link_notes:
        rec['link_notes'] = link_notes

    def sec_level(s):
        if s['layer'] in ('meta',):
            return None
        if s.get('linked_file'):
            return 'bank_candidate'  # 链接转写文件不在验收记录的题级 SHA 里，按候选计
        if bank_ok and not UNVERIFIED_RX.search(s['heading']):
            return 'bank_accepted'
        return 'bank_candidate'

    unread_set = {str(Path(x).resolve()) for x in unreadable}
    layer_out = OrderedDict()
    view_detail = {}
    for L in ['stem', 'stem_adj', 'e1', 'e3', 'candidate', 'student', 'lecture']:
        secs_l = picked.get(L, [])
        out = []
        for s in secs_l:
            body = s['body'].strip('\n')
            truncated = None
            if max_chars and len(body) > max_chars:
                truncated = {'total_chars': len(body), 'kept_chars': max_chars}
            imgs = sorted(set(IMG_RX.findall(s['body'])))
            resolved = [x for x in (bank.resolve_img(exam, i) for i in imgs) if x]
            o = OrderedDict(heading=s['heading'], line_start=s['line_start'], line_end=s['line_end'],
                            chars=len(body), section_sha256=s['section_sha256'], role_basis=s['role_basis'],
                            bank_layer=s['bank_layer'], level=sec_level(s), bank_level=sec_level(s), truncated=truncated,
                            page_images=[x for x in resolved if str(Path(x).resolve()) not in unread_set],
                            page_images_unreadable=[x for x in resolved if str(Path(x).resolve()) in unread_set],
                            page_images_missing=[i for i in imgs if not bank.resolve_img(exam, i)])
            if s.get('pointer_only'):
                o['pointer_only'] = True
            if L == 'e1':
                o['features'] = section_features(s['body'])
            if s.get('linked_file'):
                o.update(linked_file=s['linked_file'], linked_file_sha256=s['linked_file_sha256'],
                         level_reason='linked_file_not_hash_bound')
            if keep_text:
                o['_text'] = body if not truncated else body[:max_chars]
            out.append(o)
        text_secs = [o for o in out if not o.get('pointer_only')]
        lv_view, det = (ledger_level(ledger_by.get((key, L), []), md_sha, out, bank, key, unreadable)
                        if L in ('stem', 'e1', 'e3', 'candidate') else (None, []))
        if det:
            view_detail[L] = det
            # 看页等级落到小节：绑定了小节 SHA 的只升那一节；没绑定的升该层全部正文小节（明细里标 unbound）
            for o in text_secs:
                vs = [d for d in det if d['counts_for_level'] and (not d.get('section_sha256') or d['section_sha256'] == o['section_sha256'])]
                if vs:
                    o['view_level'] = level_max(['main_viewed' if d['by'] == 'main' else 'subagent_viewed' for d in vs])
                    o['level'] = level_max([o['level'], o['view_level']])
                    if any(not d.get('section_sha256') for d in vs):
                        o['view_unbound_section'] = True
        lv_bank = level_max([o['bank_level'] for o in text_secs]) if text_secs else 'missing'
        layer_out[L] = {'level': level_max([o['level'] for o in text_secs]) if text_secs else 'missing',
                        'bank_level': lv_bank, 'sections': out, 'wanted': L in want}
    rec['layers'] = layer_out
    rec['views'] = view_detail
    # 主代理/子代理看原页后判定题库原文与原页不符：切片原文未改，不得按已核引用
    rec['view_conflicts'] = [dict(d, layer=L) for L, det in view_detail.items() for d in det
                             if d['valid'] and d['verdict'] in ('corrected', 'mismatch')]
    rec['views_without_bank_text'] = [dict(d, layer=L) for L, det in view_detail.items() for d in det
                                      if d['valid'] and d.get('no_bank_text_in_layer')]
    rec['alternatives'] = {k: v for k, v in alternatives.items() if v}
    rec['_stem_alts'] = [{'heading': s['heading'], 'line_start': s['line_start'], 'line_end': s['line_end'],
                          'role_basis': s['role_basis'], 'section_sha256': s['section_sha256'],
                          'level': sec_level(s), 'body': s['body'].strip('\n')} for s in stem_alts]
    rec['rulings'] = rec_rulings
    fp['sections'] = {L: [o['section_sha256'] for o in v['sections']] for L, v in layer_out.items() if v['sections']}
    fp['ledger'] = sorted(d['_sha'] for L in ('stem', 'e1', 'e3', 'candidate') for d in ledger_by.get((key, L), []))

    e1 = layer_out['e1']
    rec['e1_level'] = e1['level']
    rec['stem_level'] = layer_out['stem']['level']
    if any(not o.get('pointer_only') for o in e1['sections']):
        base = 'ok'
    elif e1['sections']:
        base = 'pointer_only'
    elif e1_pointers:
        base = 'ruling_page_only'
    else:
        base = 'missing'
    rec['e1_status'] = base
    if base == 'missing' and exception:
        rec['e1_status'] = 'named_exception'
    if exception_partial and base == 'missing':
        # 小问级：范围内的小问按具名例外，其余小问照常（缺）
        rec['e1_by_subq'] = OrderedDict([(q, 'named_exception') for q in exception_partial['covered']] +
                                        [(q, base) for q in exception_partial['uncovered']])
        rec['e1_exception_partial'] = exception_partial
    rec['e1_pointers'] = e1_pointers
    rec['e1_exception'] = exception
    rec['e1_role_basis'] = sorted({o['role_basis'] for o in e1['sections'] if not o.get('pointer_only')})
    rec['candidate_available'] = bool(layer_out['candidate']['sections'])
    # 待看原页用的页图：E1/候选小节里引用的优先，其次质量标记里的图像依赖；登记为渲染空白的页图另列
    imgs = []
    for L in ('e1', 'candidate'):
        for o in layer_out[L]['sections']:
            imgs += o['page_images']
    qm = next((s for s in secs if s['heading'] == '质量标记'), None)
    dep = [bank.resolve_img(exam, i) for i in IMG_RX.findall(qm['body'])] if qm else []
    allimgs = [p['page_png'] for p in e1_pointers if p['exists']] + imgs + [x for x in dep if x]
    rec['page_images'] = list(dict.fromkeys(x for x in allimgs if str(Path(x).resolve()) not in unread_set))
    rec['page_images_unreadable'] = sorted(unreadable)

    # 源文件指纹：只取 MD 里点到的本卷来源；点不到就取整卷来源
    srcs = bank.exam_sources(exam)
    used = [s for s in srcs if s['source_id'] in text or (s.get('rel_path') and s['rel_path'] in text)] or srcs
    sfp = OrderedDict()
    src_list = []
    for s in used:
        p = bank.source_path(s['source_id'], s.get('rel_path'))
        reg = (bank.sources.get(s['source_id']) or {}).get('sha256')
        ent = OrderedDict(source_id=s['source_id'], role=s.get('role'), rel_path=s.get('rel_path'),
                          path=str(p) if p else None, registered_sha256=reg)
        if p and p.exists():
            stt = p.stat()
            ent.update(size=stt.st_size, mtime_ns=stt.st_mtime_ns)
            if hash_sources:
                ent['sha256'] = file_sha(p)
                ent['sha_match_registered'] = (ent['sha256'] == reg) if reg else (ent['sha256'][:12] == s['source_id'][1:13])
        else:
            ent['missing_on_disk'] = True
        sfp[s['source_id']] = ent.get('sha256') or reg
        src_list.append(ent)
    rec['sources'] = src_list
    fp['sources'] = sfp
    rec['fingerprint'] = fp
    return rec



# ---------------------------------------------------------------- 书稿例题收集

GENERIC_PROFILE = {
    'book_id': '_generic', 'title': '未识别书册（通用口径）',
    'styles': {'h1': ['heading 1'], 'h2': ['heading 2'], 'example_title': ['heading 3', 'heading 4'],
               'method': ['具体考法'], 'group_heading': [], 'category_line': ['考法分类'],
               'source': ['题目材料', '题目设问', '题目选项']},
    'structure': {'parts': []},
    'example_titles': [
        {'kind': 'choice', 'regex': r'^选择例题\s*(?P<num>\d+)[\s　]+(?P<src>.+)$'},
        {'kind': 'ext', 'regex': r'^拓展例题\s*(?P<num>\d+)[\s　]+(?P<src>.+)$'},
        {'kind': 'subjective', 'regex': r'^例题\s*(?P<num>\d+)[\s　]+(?P<src>.+)$'},
        {'kind': 'topic', 'regex': r'^例(?P<num>\d+)[\s　]+(?P<src>.+)$'},
    ],
    '_generic': True,
}

# 书册配置没写到、但书里确有的题源行（代码默认，配置 qpack.extra_example_titles 可整组替换）。
# 只在配置的正则都不命中时才试；命中的落位标 matched_by=qpack_fallback。
QPACK_EXTRA_TITLES = [
    {'kind': 'topic_case', 'regex': r'^【(?:主例|变式[一二三四五六七八九十\d]*)】\s*(?P<src>.+)$', 'styles_role': 'category_line'},
    {'kind': 'topic_list', 'regex': r'^[①-⑳◆◇●■]\s*(?P<src>20\d\d.{0,30}?第\s*\d{1,2}.{0,20})$', 'styles_role': 'category_line'},
]


def _strip_head(t):
    t = re.sub(r'（\d+题）\s*$', '', t or '')
    return re.sub(r'^(考法\d+|\d+|[一二三四五六七八九十]+、|专题[一二三四五六七八九十]+|第[一二三四五六七八九十]+部分|A\d)[\s　]*', '', t).strip()


def has_source(t):
    """段落里是否有“20xx…第N题”式题源（或题键）。"""
    tt = norm_title(t)
    return bool(KEY_RX.search(tt) or TITLE_RX.search(tt) or (SY_TITLE_RX.search(tt) and SY_TITLE_RX.search(tt).group('reg')))


def open_docx(docx):
    if not Path(docx).exists():
        raise InputError('书稿不存在：%s' % docx)
    if not zipfile.is_zipfile(docx):
        raise InputError('不是 DOCX（zip）文件：%s' % docx)
    z = zipfile.ZipFile(docx)
    if 'word/document.xml' not in z.namelist():
        raise InputError('DOCX 缺 word/document.xml：%s' % docx)
    return z


def collect_examples(docx, prof, any_heading=False, diag=None):
    """按书册配置从 DOCX 收集例题落位：标题、题源写法、所在部分/节点、题面文字（供身份探针）。
    diag 传入 dict 时，另填：段落样式统计、含题源段落的样式统计、疑似题源行未收清单。"""
    from lxml import etree
    z = open_docx(docx)
    sty = {}
    if 'word/styles.xml' in z.namelist():
        for s in etree.fromstring(z.read('word/styles.xml')).iter(W + 'style'):
            n = s.find(W + 'name')
            sty[s.get(W + 'styleId')] = n.get(W + 'val') if n is not None else s.get(W + 'styleId')
    elif diag is not None:
        diag['no_styles_xml'] = True
    body = etree.fromstring(z.read('word/document.xml')).find(W + 'body')
    if body is None:
        raise InputError('DOCX 没有 w:body：%s' % docx)
    S = lambda role: PL.styles(prof, role)  # noqa: E731
    h1s, h2s, meth, grp, src_st = S('h1'), S('h2'), S('method'), S('group_heading'), S('source')
    ex_st, cat_st = S('example_title'), S('category_line')
    rx = []
    for d in prof.get('example_titles', []):
        rx.append((d['kind'], re.compile(d['regex']), set(d.get('styles') or ex_st), 'profile'))
    for d in (prof.get('qpack') or {}).get('extra_example_titles', QPACK_EXTRA_TITLES):
        stys = set(d.get('styles') or S(d.get('styles_role', 'example_title')))
        if stys:
            rx.append((d['kind'], re.compile(d['regex']), stys, 'qpack_fallback'))
    all_ex_styles = set().union(*[x[2] for x in rx]) if rx else set(ex_st)
    watch_styles = all_ex_styles | ex_st | grp | cat_st
    parts = [(p['id'], re.compile(p['match']), p) for p in prof.get('structure', {}).get('parts', [])]
    path = {'h1': '', 'h2': '', 'method': '', 'group': ''}
    part, part_cfg = '', {}
    blocks, cur = [], None
    idx = 0
    style_count, src_style_count, uncollected = Counter(), Counter(), []
    for e in body:
        if e.tag == W + 'tbl':
            if cur is not None:
                cells = [''.join(t.text or '' for t in tc.iter(W + 't')) for tc in e.iter(W + 'tc')]
                cur['lines'].append(('[表格]', ' / '.join(c for c in cells if c)))
            continue
        if e.tag != W + 'p':
            continue
        idx += 1
        ps = e.find(W + 'pPr/' + W + 'pStyle')
        s = sty.get(ps.get(W + 'val'), ps.get(W + 'val')) if ps is not None else '正文'
        t = ''.join(x.text or '' for x in e.iter(W + 't')).strip()
        if not t:
            continue
        style_count[s] += 1
        src_here = len(t) <= 160 and has_source(t)
        if src_here:
            src_style_count[s] += 1
        if s in h1s:
            path = {'h1': t, 'h2': '', 'method': '', 'group': ''}
            part, part_cfg = '', {}
            for pid, prx, cfg in parts:
                if prx.search(t):
                    part, part_cfg = pid, cfg
                    break
            cur = None
            continue
        if s in h2s:
            path.update(h2=t, method='', group='')
            cur = None
            continue
        if s in meth:
            path.update(method=t, group='')
            cur = None
            continue
        hit = None
        if s in all_ex_styles:
            for kind, r, stys, origin in rx:
                m = r.match(t)
                if m and s in stys:
                    hit = (kind, m, origin)
                    break
        if hit:
            kind, m, origin = hit
            kind = (part_cfg.get('kind_override') or {}).get(kind, kind)
            cur = {'title': t, 'src': m.group('src') if 'src' in m.groupdict() else t, 'kind': kind,
                   'part': part, 'path': dict(path), 'para_index': idx, 'style': s, 'matched_by': origin, 'lines': []}
            blocks.append(cur)
            continue
        if s in ex_st or s in grp:
            if any_heading and TITLE_RX.search(re.sub(r'\s+', '', t)):
                cur = {'title': t, 'src': t, 'kind': 'heading', 'part': part, 'path': dict(path),
                       'para_index': idx, 'style': s, 'matched_by': 'any_heading', 'lines': []}
                blocks.append(cur)
                continue
            if src_here:
                uncollected.append({'para_index': idx, 'style': s, 'text': t, 'part': part, 'path': dict(path)})
            path['group'] = t
            cur = None
            continue
        if src_here and s in watch_styles:
            uncollected.append({'para_index': idx, 'style': s, 'text': t, 'part': part, 'path': dict(path)})
        if cur is not None and len(cur['lines']) < 400:
            cur['lines'].append((s, t))
    for b in blocks:
        b['material'], b['material_basis'] = material_text(b['lines'], src_st, want_basis=True)
        if b['kind'] == 'topic_list':
            b['material_basis'] = 'commentary'  # “①/◆ 题源”行下面是本书写的设问摘录与给分说明，不是题面
        del b['lines']
    if diag is not None:
        diag['paragraph_styles_top'] = style_count.most_common(15)
        diag['source_paragraph_styles_top'] = src_style_count.most_common(10)
        diag['uncollected_source_lines'] = uncollected
        diag['watched_styles'] = sorted(watch_styles)
    return blocks


def material_text(lines, src_styles, want_basis=False):
    """书中题面文字（供身份探针）。want_basis=True 时另返回来源：style（题面样式）/label（【题目】【材料】栏目）/
    head（第一个栏目之前的段落，专题例题常是改写过的设问，只作身份旁证，不据此判题库题面有误）。"""
    if want_basis:
        txt = material_text(lines, src_styles)
        by_style = '\n'.join(t for s, t in lines if s in src_styles or s == '[表格]')
        if len(norm_text(by_style)) >= 40:
            return txt, 'style'
        return txt, ('label' if any(LABEL_RX.match(t) and LABEL_RX.match(t).group(1) in SOURCE_LABELS for _, t in lines) else 'head')
    by_style = [t for s, t in lines if s in src_styles or s == '[表格]']
    txt = '\n'.join(by_style)
    if len(norm_text(txt)) >= 40:
        return txt
    out, on = [], False
    for s, t in lines:
        m = LABEL_RX.match(t)
        if m:
            on = m.group(1) in SOURCE_LABELS
            t = t[m.end():]
        if on and t:
            out.append(t)
    if len(norm_text('\n'.join(out))) >= 40:
        return '\n'.join(out)
    # 书册没有【题目】标签、题面样式又不可靠时：取第一个【…】栏目之前的段落
    head = []
    for s, t in lines:
        if LABEL_RX.match(t):
            break
        head.append(t)
    return '\n'.join(head) if len(norm_text('\n'.join(head))) > len(norm_text('\n'.join(out))) else '\n'.join(out)


def probe_snippets(material, n=5, width=10):
    """从书中题面取 n 个短片段：先按省略号、换行、表格分隔切段（片段不跨“……”和表格单元），再在各段里等距取。"""
    segs = []
    for s in re.split(r'…+|\.{3,}|\n|\s/\s|\|', material or ''):
        s = norm_text(LABEL_RX.sub('', s.strip()))
        if len(s) >= width:
            segs.append(s)
    total = sum(len(s) for s in segs)
    if total < width * 3:
        return []
    step = total / float(n)
    out = []
    for i in range(n):
        pos, acc = int(step * i + step / 2), 0
        for s in segs:
            if pos < acc + len(s):
                off = min(max(0, pos - acc - width // 2), len(s) - width)
                out.append(s[off:off + width])
                break
            acc += len(s)
    return list(dict.fromkeys(out))


def probe_text(material, target, n=5, width=10):
    """身份探针：书中题面取 n 个短片段，看目标文字是否含有。只作旁证，不作核验。"""
    b = norm_text(target)
    snips = probe_snippets(material, n, width)
    if not snips or not b:
        return 0, 0
    return sum(1 for s in snips if s in b), len(snips)


def probe(material, md_path, n=5, width=10):
    if not Path(md_path).exists():
        return 0, 0
    return probe_text(material, Path(md_path).read_text(encoding='utf-8', errors='replace'), n, width)


def identity_alternative(bank, key, material):
    """书中题面与该题键题级 MD 对不上（5 片段命中≤1）时，在同区相邻年份、其他考次里找命中≥4 的唯一备选。
    只给证据，不改映射（除非 --probe-redirect）；各书对“期中”年份的写法不一，这里能查出来。"""
    m = KEY_RX.match(key or '')
    if not m or len(norm_text(material)) < 40:
        return None
    y, reg, q = int(m.group(1)), m.group(2), m.group(4)
    own = probe(material, bank.md_path(key)) if bank.md_path(key).exists() else (0, 5)
    if own[0] >= 2:
        return None
    stages = ['GAOKAO'] if reg == 'BJ' else ['YIMO', 'ERMO', 'QIMO', 'QIZHONG']
    cands = ['BJ-%d-%s-%s-Q%s' % (yy, reg, st, q) for yy in (y - 1, y, y + 1) for st in stages]
    cands = [k for k in cands if k != key and bank.md_path(k).exists()]
    scores = sorted(((probe(material, bank.md_path(k)), k) for k in cands), key=lambda x: -x[0][0])
    if not scores:
        return None
    best = scores[0][0][0]
    rival = max([own[0]] + ([scores[1][0][0]] if len(scores) > 1 else []))
    # 与 _pick 同一门槛：最高≥PROBE_MIN 且领先本卷与第二名都≥PROBE_LEAD
    if best >= PROBE_MIN and best - rival >= PROBE_LEAD:
        return {'generic_key': key, 'generic_probe': list(own), 'alternative_key': scores[0][1],
                'alternative_probe': list(scores[0][0]),
                'runner_up': ({'key': scores[1][1], 'probe': list(scores[1][0])} if len(scores) > 1 else None)}
    return None


def select_blocks(blocks, a, apply_kinds=True):
    kinds = set(a.kinds.split(',')) if (a.kinds and apply_kinds) else None
    out = []
    for b in blocks:
        if kinds and 'all' not in kinds and b['kind'] not in kinds:
            continue
        if a.part and b['part'] not in a.part.split(','):
            continue
        if a.subject:
            if _strip_head(b['path'].get('method')) != a.subject:
                continue
        if a.node:
            levels = [a.node_level] if a.node_level != 'any' else ['h1', 'h2', 'method', 'group']
            vals = [b['path'].get(L, '') for L in levels]
            ok = False
            for nd in a.node:
                for v in vals:
                    if (a.node_exact and _strip_head(v) == nd) or (not a.node_exact and nd in v):
                        ok = True
            if not ok:
                continue
        out.append(b)
    return out


# ---------------------------------------------------------------- 输出

E1_STATUS_CN = {'ok': '有正文', 'pointer_only': '只有出处指针或工程说明，没有细则正文',
                'ruling_page_only': '题库无正文，按用户裁定须看原页', 'named_exception': '具名例外（允许无正式细则）',
                'missing': '缺', 'identity_pending': '身份待定（书中题面更像别卷）'}
MECH_NOTICE = '机械层全过只说明没有回退，不代表内容已审；题库已验收≠主代理已核原页。'


def _rel(p, root):
    try:
        return str(Path(p).relative_to(root))
    except ValueError:
        return str(p)


def _clip(s, n=400):
    s = s if isinstance(s, str) else json.dumps(s, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + '〔截断：原文 %d 字，保留前 %d 字〕' % (len(s), n)


def slice_md(rec, want_layers, now, bank_root=DEFAULT_BANK, packet_id=None):
    """单题切片：头部几行是机器状态，其后各节是题库原文（不改一字，截断处标注）。"""
    L = ['# %s' % rec['key'], '',
         '> qpack 切片%s，只截题库原文、不含归纳（%s）。原文件 %s（题库根 %s）' % (
             (' packet_id=%s' % packet_id) if packet_id else '', now, _rel(rec['md_path'], bank_root), bank_root),
         '> ' + MECH_NOTICE]
    idp = rec.get('identity_pending')
    if idp:
        L.append('> ⚠ 身份待定：书中题面与本卷对不上（探针 %s），更像 %s（探针 %s）；须主代理裁定后再用本切片。落位：%s'
                 % ('/'.join(map(str, idp['generic_probe'])), idp['alternative_key'],
                    '/'.join(map(str, idp['alternative_probe'])), '；'.join(idp['titles'][:4])))
    for red in rec.get('identity_redirected') or []:
        L.append('> 按身份探针改映射：书中写法原解析为 %s（探针 %s），改取本卷（探针 %s）；须主代理确认。'
                 % (red['generic_key'], '/'.join(map(str, red['generic_probe'])), '/'.join(map(str, red['alternative_probe']))))
    if not rec.get('md_exists'):
        L.append('> 题库无此题级 MD。')
        return '\n'.join(L) + '\n'
    st = rec['e1_status']
    if st == 'ok':
        e1_txt = 'E1 有正文，等级 %s（%s）' % (rec['e1_level'], LEVEL_CN[rec['e1_level']])
    else:
        e1_txt = 'E1 %s（%s）' % (st, E1_STATUS_CN.get(st, st))
    L.append('> %s｜题面 %s（%s）｜题型 %s（依据 %s）｜卷 %s，题级MD SHA%s验收记录' % (
        e1_txt, rec['stem_level'], LEVEL_CN[rec['stem_level']], rec.get('qtype'), rec.get('qtype_basis'),
        rec.get('manifest_status'), '＝' if rec.get('bank_accept_ok') else '≠/无'))
    if rec.get('reasons'):
        L.append('> 未达题库已验收：' + '、'.join(rec['reasons']))
    for r in rec.get('rulings', []):
        L.append('> 用户裁定 %s（%s）：%s%s%s' % (r['req_id'], r['type'], r.get('note') or '',
                                            ('；' + r['scope_note']) if r.get('scope_note') else '',
                                            ('；' + r['not_applied']) if r.get('not_applied') else ''))
    if rec.get('e1_by_subq'):
        L.append('> E1 按小问：' + '；'.join('第%s问 %s' % (q, v) for q, v in rec['e1_by_subq'].items()))
    if st == 'ruling_page_only':
        L.append('> E1 题库无正文，按裁定须看原页：' + '；'.join(_rel(p['page_png'], bank_root) for p in rec['e1_pointers']))
    elif st == 'pointer_only':
        L.append('> E1：题库小节只有出处指针或工程说明，没有细则正文，须看原页或原转写。')
    elif st == 'named_exception':
        L.append('> E1：具名例外（%s），允许无正式细则；E3 只作方向。' % rec['e1_exception'])
    elif st == 'missing':
        L.append('> E1：题库无正式细则文字%s%s。' % (
            '（有候选评分材料，加 --layers candidate 可取）' if rec.get('candidate_available') else '',
            ('；以下 E1 小节只声明没有细则，按空处理：' + '、'.join(rec['e1_declared_absent'])) if rec.get('e1_declared_absent') else ''))
    for d in rec.get('view_conflicts') or []:
        L.append('> ⚠ 原页核对不符：%s（%s）判 %s，账本 %s——本切片原文未改，与原页不符，不得按已核引用。'
                 % (d['by'], d.get('agent_id'), d['verdict'], d['ledger']))
    for d in rec.get('views_without_bank_text') or []:
        L.append('> 已看原页（%s，%s，%s层），但题库此层没有正文；切片不含原页文字，不计已核等级，须转写后再用。'
                 % (d['by'], d.get('agent_id'), d['layer']))
    ss = rec.get('stem_selection')
    if ss:
        L.append('> ⚠ 采用的题面小节与书中题面对得较差（探针 %s），同一 MD 的另一题面小节「%s」命中 %s，已附在下方，须模型确认用哪一节。'
                 % ('/'.join(map(str, ss['adopted_probe'])), ss['alternative_heading'], '/'.join(map(str, ss['alternative_probe']))))
    pl = [p for p in (rec.get('placements') or []) if p.get('kind') != 'list']
    if pl:
        L.append('> 书中落位 %d 处：' % len(pl) + '；'.join(
            '%s｜%s' % (p['title'], ' / '.join(x for x in (p['path'].get('h2'), p['path'].get('method')) if x))
            for p in pl[:4]) + ('……' if len(pl) > 4 else ''))
    if rec.get('page_images'):
        L.append('> 原页图：' + '；'.join(_rel(x, bank_root) for x in rec['page_images'][:4]))
    if rec.get('page_images_unreadable'):
        L.append('> 以下页图题库登记为渲染空白（不能当原页看，须重渲染或看原件）：'
                 + '；'.join(_rel(x, bank_root) for x in rec['page_images_unreadable'][:8]))
    for x in rec.get('residuals') or []:
        L.append('> 题库残留记录（%s.%s，原文照录）：%s' % (x['origin'], x['field'], _clip(x['entry'])))
    order = ['e1', 'stem', 'stem_adj', 'e3', 'candidate', 'student', 'lecture']
    want = set(want_layers) | ({'stem_adj'} if 'stem' in want_layers else set()) | \
        ({'e3'} if (rec.get('e1_exception') or rec.get('e1_exception_partial')) else set())
    for layer in order:
        if layer not in want:
            continue
        v = rec['layers'].get(layer) or {}
        for s in v.get('sections', []):
            extra = []
            if s.get('linked_file'):
                extra.append('链接转写文件未绑定验收SHA，按候选计')
            if s.get('pointer_only'):
                extra.append('本节只有出处指针或工程说明，无细则正文')
            if s.get('view_level'):
                extra.append('看页账本：%s%s' % (s['view_level'], '（账本未绑定小节）' if s.get('view_unbound_section') else ''))
            if s.get('probe_matched_alternative'):
                extra.append('非采用小节；书中题面探针命中 %s' % '/'.join(map(str, s['probe_matched_alternative'])))
            L += ['', '## [%s] %s' % (LAYER_CN[layer], s['heading']),
                  '> %s行 %d–%d｜小节SHA %s｜角色依据 %s｜等级 %s%s' % (
                      ('文件 %s ' % _rel(s['linked_file'], bank_root)) if s.get('linked_file') else '', s['line_start'], s['line_end'],
                      s['section_sha256'][:12], s['role_basis'], s['level'], ('（%s）' % '；'.join(extra)) if extra else '')]
            L.append(s.get('_text', ''))
            if s.get('truncated'):
                L.append('〔以下截断：本节原文 %d 字，此处保留前 %d 字；全文见 %s 第 %d–%d 行〕'
                         % (s['truncated']['total_chars'], s['truncated']['kept_chars'], rec['md_path'],
                            s['line_start'], s['line_end']))
    return '\n'.join(L) + '\n'


def _deny_zones(bank_root):
    """任何情况下都不写的位置（即便书册配置登记了也拒绝）。"""
    z = [(Path(bank_root), '题库目录'), (ROOT / '00_共同资料', '00_共同资料（原材料/规则同步母版）'),
         (ROOT / '.claude', '.claude（技能副本）'), (ROOT / '后勤管理', '后勤管理'), (HERE.parent, '技能目录'),
         (ROOT / '00_协作入口.md', '协作入口'), (ROOT / 'CLAUDE.md', 'CLAUDE.md'), (ROOT / 'AGENTS.md', 'AGENTS.md')]
    for name in PL.list_profiles():
        prof = PL.load_profile(name)
        for k in ('workspace', 'aux_workspace', 'review_entry', 'review_history'):
            d = prof.get('paths', {}).get(k)
            if d:
                z.append((PL.resolve(prof, d), '%s 的 %s' % (name, k)))
    return z


def write_roots():
    """白名单：系统临时目录（含本会话 scratch），以及书册配置 qpack.out_dirs / qpack.ledger_dirs 明确登记的目录。"""
    roots = [Path(tempfile.gettempdir()), Path('/tmp'), Path('/private/tmp')]
    reg = []
    for name in PL.list_profiles():
        prof = PL.load_profile(name)
        for k in ('out_dirs', 'ledger_dirs'):
            for d in (prof.get('qpack') or {}).get(k) or []:
                reg.append(PL.resolve(prof, d))
    return roots, reg


def guard_out(out, docx=None, bank_root=DEFAULT_BANK, what='取材包'):
    """写入护栏（白名单）：只准写系统临时目录或书册配置登记的取材包/账本目录；题库、各书册工作区、协作、
    00_共同资料、.claude、后勤管理、审阅入口、书稿旁、冻结册一律拒绝。违反时抛 InputError（退出码 2）。"""
    p = Path(out).resolve()
    prof = PL.detect_profile(p)
    if prof and prof.get('frozen'):  # 冻结册：一律经 frozen_guard 拒绝
        try:
            PL.frozen_guard(prof, '写入' + what)
        except SystemExit as e:
            raise InputError(str(e))
    for d, name in _deny_zones(bank_root):
        if is_under(p, d):
            raise InputError('拒绝写入%s：%s（%s）' % (name, p, what))
    if docx and is_under(p, Path(docx).resolve().parent):
        raise InputError('拒绝把%s写到书稿旁边：%s' % (what, p))
    roots, reg = write_roots()
    if any(is_under(p, r) for r in roots) or any(is_under(p, r) for r in reg):
        return p
    raise InputError('拒绝写入白名单以外的位置：%s。只允许系统临时目录（%s）或书册配置 qpack.out_dirs/ledger_dirs 登记的目录'
                     % (p, '、'.join(str(r) for r in roots)))


def check_out_dir(out):
    """输出目录须不存在、为空，或是旧的 qpack 包（只含 packet.json、index.md、q/*.md）；其他一律拒绝。"""
    out = Path(out)
    if not out.exists():
        return
    if not out.is_dir():
        raise InputError('输出路径已存在且不是目录：%s' % out)
    entries = list(out.iterdir())
    if not entries:
        return
    pj = out / 'packet.json'
    ok = False
    if pj.exists():
        try:
            ok = json.loads(pj.read_text(encoding='utf-8'))['meta']['tool'] == 'qpack.py'
        except Exception:
            ok = False
    extra = [x.name for x in entries if x.name not in ('packet.json', 'index.md', 'q')]
    qd = out / 'q'
    bad = [x.name for x in qd.iterdir() if not (x.is_file() and x.suffix == '.md')] if qd.is_dir() else []
    if not ok or extra or bad:
        raise InputError('输出目录非空且不是 qpack 包（或含其他文件 %s），拒绝覆盖：%s' % ((extra + bad)[:5], out))


def summarize(recs, unresolved, placements_n, extra_lists=None):
    keys = list(recs.values())
    n = len(keys)

    def kstat(r):
        if r.get('identity_status') == 'pending':
            return 'identity_pending'
        return r['e1_level'] if r['e1_status'] == 'ok' else r['e1_status']
    c_e1 = Counter(kstat(r) for r in keys)
    pl_e1 = Counter()
    id_pending_pl = 0
    for r in keys:
        pls = r.get('placements') or [{}]
        for p in pls:
            if p.get('identity_pending'):
                pl_e1['identity_pending'] += 1
                id_pending_pl += 1
            elif r.get('e1_by_subq') and p.get('subq') in r['e1_by_subq']:
                pl_e1[r['e1_by_subq'][p['subq']]] += 1
            elif r.get('e1_by_subq') and not p.get('subq') and '整题' in r['e1_by_subq']:
                pl_e1[r['e1_by_subq']['整题']] += 1
            else:
                pl_e1[kstat(r)] += 1
    live = [r for r in keys if r.get('identity_status') != 'pending']

    def std_basis(r):
        return any(b in ('bank_alias', 'bank_guide') or b.startswith('ruling:') for b in r.get('e1_role_basis') or [])
    acc = [r for r in live if r['e1_status'] == 'ok' and r['e1_level'] == 'bank_accepted']
    lists = OrderedDict()
    lists['unresolved_titles'] = unresolved
    lists['no_question_md'] = [r['key'] for r in keys if not r.get('md_exists')]
    lists['identity_pending'] = [OrderedDict(key=r['key'], **r['identity_pending']) for r in keys if r.get('identity_pending')]
    lists['missing_e1'] = [{'key': r['key'], 'candidate_available': r.get('candidate_available'),
                            'guide_rubric_status': r.get('guide_rubric_status'), 'declared_absent': r.get('e1_declared_absent'),
                            'e1_by_subq': r.get('e1_by_subq'), 'page_images': r.get('page_images', [])[:4]}
                           for r in live if r.get('md_exists') and (r['e1_status'] == 'missing' or
                                                                    'missing' in (r.get('e1_by_subq') or {}).values())]
    lists['to_view_pages'] = [{'key': r['key'], 'why': (['e1_level=' + r['e1_level']] if r['e1_status'] == 'ok' else [r['e1_status']])
                               + [x['req_id'] for x in r.get('rulings', []) if x['type'] in ('promote_section', 'page_pointer')]
                               + (['view_conflict'] if r.get('view_conflicts') else [])
                               + list(r.get('reasons') or []),
                               'page_images': r.get('page_images', [])[:6],
                               'page_images_unreadable': r.get('page_images_unreadable', [])[:6]}
                              for r in live if (r['e1_status'] == 'ok' and r['e1_level'] in ('bank_candidate', 'subagent_viewed'))
                              or r['e1_status'] in ('ruling_page_only', 'pointer_only') or r.get('view_conflicts')]
    lists['accepted_not_main_viewed'] = [{'key': r['key'], 'role': 'standard' if std_basis(r) else 'inferred',
                                          'e1_role_basis': r['e1_role_basis']} for r in acc]
    lists['main_viewed'] = [r['key'] for r in live if r['e1_status'] == 'ok' and r['e1_level'] == 'main_viewed']
    lists['view_conflicts'] = [{'key': r['key'], 'entries': r['view_conflicts']} for r in keys if r.get('view_conflicts')]
    lists['views_without_bank_text'] = [{'key': r['key'], 'entries': r['views_without_bank_text']}
                                        for r in keys if r.get('views_without_bank_text')]
    lists['role_uncertain_e1'] = [{'key': r['key'], 'role_basis': r['e1_role_basis'],
                                   'headings': [s['heading'] for s in r['layers']['e1']['sections'] if not s.get('pointer_only')]}
                                  for r in live if r['e1_status'] == 'ok'
                                  and {b.replace('+link', '') for b in r['e1_role_basis']} <= {'heading_regex', 'subheading_regex'}]
    lists['e1_declared_absent'] = [{'key': r['key'], 'headings': r['e1_declared_absent']} for r in keys if r.get('e1_declared_absent')]
    lists['named_exception'] = [{'key': r['key'], 'req_id': r['e1_exception']} for r in live if r['e1_status'] == 'named_exception']
    lists['exception_partial'] = [{'key': r['key'], **r['e1_exception_partial'], 'e1_by_subq': r.get('e1_by_subq')}
                                  for r in live if r.get('e1_exception_partial')]
    lists['stem_missing'] = [r['key'] for r in live if r.get('md_exists') and r['stem_level'] == 'missing']
    # 书中题面与题库题面对不上：分“采用小节不当（同一 MD 另有匹配的题面小节）”和“题库题面有误或书稿改写过”
    lists['stem_section_misselected'] = [OrderedDict(key=r['key'], **r['stem_selection']) for r in live if r.get('stem_selection')]
    lists['stem_bank_mismatch'] = [{'key': r['key'], 'probe_stem': r['probe']['stem'], 'probe_md': r['probe']['md'],
                                    'stem_heading': [s['heading'] for s in r['layers']['stem']['sections']]}
                                   for r in live if r.get('probe') and r['probe'].get('stem') and r['probe']['stem'][1]
                                   and r['probe']['stem'][0] <= 1 and r['layers']['stem']['sections'] and not r.get('stem_selection')
                                   and r['probe'].get('material_basis') in ('style', 'label')]
    lists['preamble_says_candidate'] = [r['key'] for r in keys if 'md_preamble_says_candidate' in (r.get('flags') or [])
                                        and r.get('bank_accept_ok')]
    lists['page_images_unreadable'] = [{'key': r['key'], 'images': r['page_images_unreadable']} for r in keys if r.get('page_images_unreadable')]
    lists['residuals'] = [{'key': r['key'], 'n': len(r['residuals'])} for r in keys if r.get('residuals')]
    lists['stale_view_entries'] = [{'key': r['key'], 'layer': L, 'entries': [d for d in det if not d['valid']]}
                                   for r in keys for L, det in (r.get('views') or {}).items() if any(not d['valid'] for d in det)]
    lists['source_sha_mismatch'] = [{'key': r['key'], 'source_id': s['source_id']} for r in keys for s in r.get('sources', [])
                                    if s.get('sha_match_registered') is False]
    for k, v in (extra_lists or {}).items():
        lists[k] = v
    ok_pl = placements_n - len(unresolved) - id_pending_pl
    summ = OrderedDict(
        placements=placements_n, unique_keys=n, unresolved_titles=len(unresolved),
        identity_pending_placements=id_pending_pl,
        parse_ratio=round(ok_pl / placements_n, 4) if placements_n else None,
        parse_ratio_note='已解析＝落位数−未解析−身份待定',
        md_exists=sum(1 for r in keys if r.get('md_exists')),
        e1_by_key=dict(c_e1), e1_by_placement=dict(pl_e1),
        bank_accepted_e1_keys=len(acc),
        bank_accepted_standard_role=sum(1 for r in acc if std_basis(r)),
        bank_accepted_inferred_role=sum(1 for r in acc if not std_basis(r)),
        bank_accepted_ratio=round(len(acc) / n, 4) if n else None,
        stem_by_key=dict(Counter(r['stem_level'] for r in keys)),
        qtype_by_key=dict(Counter(r.get('qtype') for r in keys)),
        list_sizes={k: len(v) for k, v in lists.items()},
    )
    return summ, lists


def write_packet(out, meta, recs, lists, summ, want_layers, json_text=False):
    out = Path(out)
    check_out_dir(out)
    qd = out / 'q'
    if qd.is_dir():
        for x in qd.iterdir():  # 旧切片先清掉，免得子代理读到已不在包里的题
            x.unlink()
    qd.mkdir(parents=True, exist_ok=True)
    now = meta['generated_at']
    pid = meta['packet_id']
    for k, r in recs.items():
        (qd / (k + '.md')).write_text(slice_md(r, want_layers, now, meta['bank']['root'], pid), encoding='utf-8')
        r['slice'] = str(qd / (k + '.md'))
    for r in recs.values():
        r.pop('_stem_alts', None)
        if not json_text:
            for v in (r.get('layers') or {}).values():
                for s in v['sections']:
                    s.pop('_text', None)
    pk = OrderedDict(meta=meta, summary=summ, lists=lists, keys=list(recs.values()))
    (out / 'packet.json').write_text(json.dumps(pk, ensure_ascii=False, indent=1), encoding='utf-8')
    idx = ['# 取材包索引', '', '> packet_id=%s；只截题库原文；等级：' % pid + '；'.join('%s=%s' % (k, v) for k, v in LEVEL_CN.items()),
           '> ' + MECH_NOTICE, '',
           '| 题键 | 落位 | E1 | 题面 | 切片 |', '|---|---|---|---|---|']
    for k, r in recs.items():
        e1 = 'identity_pending' if r.get('identity_status') == 'pending' else (r['e1_level'] if r['e1_status'] == 'ok' else r['e1_status'])
        idx.append('| %s | %d | %s | %s | q/%s.md |' % (k, len(r.get('placements') or []), e1, r['stem_level'], k))
    for name, v in lists.items():
        if v:
            idx += ['', '## %s（%d）' % (name, len(v))]
            for x in v:
                idx.append('- ' + (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)))
    (out / 'index.md').write_text('\n'.join(idx) + '\n', encoding='utf-8')


def zh_summary(summ, meta):
    e1 = summ['e1_by_key']
    s = ('落位 %d 处 → 唯一题键 %d 个；题源解析 %s（身份待定 %d 处、未解析 %d 处不计入）；有题级 MD %d 个。'
         'E1：题库已验收 %d（其中按题库标准标题或读取指引认定 %d、按标题推断角色 %d）、题库候选 %d、子代理看过 %d、'
         '主代理已核 %d、缺 %d、只有出处指针 %d、裁定只给页图 %d、具名例外 %d、身份待定 %d。耗时 %.2f 秒。'
         % (summ['placements'], summ['unique_keys'],
            ('%.1f%%' % (summ['parse_ratio'] * 100)) if summ['parse_ratio'] is not None else '—',
            summ['identity_pending_placements'], summ['unresolved_titles'],
            summ['md_exists'], summ['bank_accepted_e1_keys'], summ['bank_accepted_standard_role'],
            summ['bank_accepted_inferred_role'], e1.get('bank_candidate', 0), e1.get('subagent_viewed', 0),
            e1.get('main_viewed', 0), e1.get('missing', 0), e1.get('pointer_only', 0), e1.get('ruling_page_only', 0),
            e1.get('named_exception', 0), e1.get('identity_pending', 0), meta['timing']['total_s']))
    ls = summ['list_sizes']
    tail = []
    for k, cn in (('uncollected_source_lines', '疑似题源行未收'), ('same_name_multi_exam', '同名多卷'),
                  ('stem_section_misselected', '题面采用小节不当'), ('view_conflicts', '原页核对不符'),
                  ('exam_inferred_from_context', '考次按标题推定')):
        if ls.get(k):
            tail.append('%s %d' % (cn, ls[k]))
    return s + ('须处理：' + '、'.join(tail) + '。' if tail else '') + MECH_NOTICE


# ---------------------------------------------------------------- 子命令

def _common_env(a):
    prof = None
    if getattr(a, 'profile', None):
        prof = PL.load_profile(a.profile)
    elif getattr(a, 'docx', None):
        prof = PL.detect_profile(a.docx)
    bank_root = Path(a.bank) if getattr(a, 'bank', None) else (
        PL.resolve(prof, prof['sources']['bank']['root']) if prof and prof.get('sources', {}).get('bank', {}).get('root')
        else DEFAULT_BANK)
    manifest = Path(a.manifest) if getattr(a, 'manifest', None) else (
        PL.resolve(prof, prof['sources']['bank']['manifest']) if prof and prof.get('sources', {}).get('bank', {}).get('manifest')
        else DEFAULT_MANIFEST)
    bank = Bank(bank_root, manifest)
    keymap = load_keymap(a.keymap if getattr(a, 'keymap', None) else KEYMAP_FILE)
    rulings = load_rulings(a.rulings if getattr(a, 'rulings', None) else RULINGS_FILE)
    return prof, bank, keymap, rulings


def parse_key_arg(s):
    """KEY 或 KEY(1)；也接受题源写法（交给 resolve_title）。"""
    m = re.fullmatch(r'\s*(BJ-20\d\d-[A-Z]{2,3}-[A-Z]+-Q\d{1,2})(?:\((\d)\))?\s*', s)
    return (m.group(1), m.group(2)) if m else (None, None)


def cmd_resolve(a):
    _, bank, keymap, _ = _common_env(a)
    rows = [r for t in a.titles for r in resolve_all(t, bank, keymap)]
    if a.json:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print('%s%s → %s%s｜%s｜%s%s%s' % (
                r['raw'], ('〔%s %s〕' % (r['multi_source'], r['raw_part'])) if r.get('multi_source') else '',
                r['key'] or '（未定）', ('(%s)' % r['subq']) if r['subq'] and r['key'] else '', r['status'], r['basis'],
                ('｜%s' % r['semester']) if r.get('semester') else '',
                ('｜' + '；'.join(r['notes'])) if r['notes'] else ''))
    return 0 if all(r['status'] == 'ok' for r in rows) else 1


def _label_norm(s):
    return re.sub(r'(?<=\d{4})(年|届)', '', s or '')


def _diag_print(msg, diag, extra=None):
    print(msg, file=sys.stderr)
    if diag.get('paragraph_styles_top'):
        print('  本书段落样式（前15）：' + '；'.join('%s×%d' % x for x in diag['paragraph_styles_top']), file=sys.stderr)
    if diag.get('source_paragraph_styles_top'):
        print('  含“20xx…第N题”的段落样式：' + '；'.join('%s×%d' % x for x in diag['source_paragraph_styles_top']), file=sys.stderr)
    for k, v in (extra or {}).items():
        print('  %s：%s' % (k, v), file=sys.stderr)
    print('  可写一份书册配置（styles.h1/h2/example_title/source、example_titles 正则）用 --profile <配置.json> 重跑。', file=sys.stderr)


def cmd_build(a):
    t0 = time.perf_counter()
    if not a.docx and not a.keys and not a.key:
        raise InputError('需要 --docx 或 --keys/--key')
    guard_out(a.out, a.docx)
    check_out_dir(a.out)
    for lp in a.ledger or []:
        if not Path(lp).exists():
            raise InputError('看页账本不存在：%s' % lp)
    prof, bank, keymap, rulings = _common_env(a)
    t_env = time.perf_counter()
    layers = ALL_LAYERS if a.layers == 'all' else [x.strip() for x in a.layers.split(',') if x.strip()]
    bad = [x for x in layers if x not in ALL_LAYERS]
    if bad:
        raise InputError('未知层：%s' % bad)
    ledger_by, ledger_sha = load_view_ledger(a.ledger)
    placements = defaultdict(list)
    unresolved, alts, kind_conflicts, reclassified, ctx_inferred = [], [], [], [], []
    n_pl = 0
    blocks_meta, diag = None, {}
    qtype_cache = {}

    def qtype_of(k):
        if k not in qtype_cache:
            mp = bank.md_path(k)
            qtype_cache[k] = md_qtype(mp.read_text(encoding='utf-8', errors='replace')[:3000] if mp.exists() else '', k)
        return qtype_cache[k]

    if a.docx:
        use_prof = prof or GENERIC_PROFILE
        blocks = collect_examples(a.docx, use_prof, any_heading=a.any_heading, diag=diag)
        if not blocks:
            _diag_print('书稿里按%s收到 0 个例题块（例题标题样式或正则与本书不符）。' % (
                '书册配置 %s' % use_prof.get('book_id')), diag)
            return 2
        if a.kinds is None:
            kinds = [d['kind'] for d in use_prof.get('example_titles', []) if d['kind'] != 'choice']
            kinds += [d['kind'] for d in (use_prof.get('qpack') or {}).get('extra_example_titles', QPACK_EXTRA_TITLES)]
            a.kinds = ','.join(dict.fromkeys(kinds + (['heading'] if a.any_heading else [])))
        pre = select_blocks(blocks, a, apply_kinds=False)
        if not pre:
            extra = {}
            if a.subject:
                topical = [b for b in blocks if b['kind'].startswith('topic')] or blocks
                names = list(dict.fromkeys(_strip_head(b['path'].get('method')) for b in topical if b['path'].get('method')))
                extra['本书主体（专题例题所在考法标题去编号，前40）'] = '、'.join(names[:40])
            if a.part:
                extra['本书部分 id'] = '、'.join(sorted({b['part'] for b in blocks if b['part']})) or '（配置未分部分）'
            if a.node:
                extra['本书二级节点（前30）'] = '、'.join(list(dict.fromkeys(b['path'].get('h2') for b in blocks if b['path'].get('h2')))[:30])
            _diag_print('选择器命中 0 个例题块：--subject=%s --part=%s --node=%s' % (a.subject, a.part, a.node), diag, extra)
            return 2
        kinds = set(a.kinds.split(','))
        for b in pre:
            results = resolve_all(b['src'], bank, keymap, probe_text=b['material'])
            ctx = ' '.join(b['path'].get(x) or '' for x in ('h1', 'h2', 'method', 'group'))
            m0 = re.match(r'^(20\d\d)年?第?(\d{1,2}.*)$', norm_title(re.sub(r'^[①-⑳◆◇●■]\s*', '', b['src'])))
            if len(results) == 1 and results[0]['status'] == 'unparsed' and m0 and re.search(r'高考|真题', ctx):
                # 题源行只写“2026年第21题”、所在标题写明高考/真题：按北京高考解析，另列清单须确认
                r2 = resolve_title('%s年北京高考第%s' % (m0.group(1), m0.group(2)), bank, keymap, b['material'])
                r2['raw'] = b['src']
                r2['basis'] = (r2.get('basis') or '') + '+context_gaokao'
                r2['notes'].append('题源行未写考次，按所在标题（%s）推定为北京高考，须确认' % ctx.strip()[:40])
                results = [r2]
                ctx_inferred.append({'title': b['title'], 'key': r2.get('key'), 'context': ctx.strip()[:80]})
            for r in results:
                kind, orig = b['kind'], b['kind']
                if r.get('key'):
                    qt = qtype_of(r['key'])
                elif (r.get('parsed') or {}).get('q'):
                    qt = md_qtype('', 'X-Q%s' % r['parsed']['q'])  # 未定卷号时按题号推断
                else:
                    qt = (None, None)
                if qt[0] == 'choice' and kind != 'choice':
                    if use_prof.get('_generic'):
                        kind = 'choice'  # 通用口径不分题型：按题库 MD 的题型（或题号≤15）改判
                        reclassified.append({'title': b['title'], 'key': r['key'], 'qtype_basis': qt[1]})
                    else:
                        kind_conflicts.append({'title': b['title'], 'key': r['key'], 'book_kind': kind, 'qtype': qt[0], 'qtype_basis': qt[1]})
                elif qt[0] == 'subjective' and kind == 'choice' and qt[1] == 'md':
                    kind_conflicts.append({'title': b['title'], 'key': r['key'], 'book_kind': kind, 'qtype': qt[0], 'qtype_basis': qt[1]})
                if 'all' not in kinds and kind not in kinds:
                    continue
                n_pl += 1
                alt = identity_alternative(bank, r.get('key'), b['material']) if r.get('key') and not a.no_identity_check else None
                pl = {'title': b['title'], 'kind': kind, 'book_kind': orig, 'part': b['part'], 'path': b['path'],
                      'para_index': b['para_index'], 'subq': r.get('subq'), 'resolve_basis': r.get('basis'),
                      'notes': r.get('notes'), 'matched_by': b.get('matched_by'), 'exam_label': _label_norm(r.get('exam_label')),
                      'semester': r.get('semester'), '_material': b['material'], 'material_basis': b.get('material_basis')}
                if r.get('multi_source'):
                    pl.update(multi_source=r['multi_source'], raw_part=r['raw_part'])
                if alt:
                    alts.append(dict(alt, title=b['title'], applied=bool(a.probe_redirect)))
                    if a.probe_redirect:
                        pl['identity_redirected'] = alt
                        r['key'] = alt['alternative_key']
                        r['basis'] = (r.get('basis') or '') + '+probe_redirect'
                        r['status'] = 'ok'
                    else:
                        pl['identity_alternative'] = alt
                        pl['identity_pending'] = True
                if r['status'] != 'ok':
                    unresolved.append({'title': b['title'], 'status': r['status'], 'key': r.get('key'),
                                       'candidates': r.get('candidates'), 'probe_scores': r.get('probe_scores'),
                                       'notes': r.get('notes'), 'exam_label': pl['exam_label']})
                    if r['status'] != 'no_question_md':
                        continue
                placements[r['key']].append(pl)
        if not n_pl:
            _diag_print('选择器命中 %d 个例题块，但按种类 --kinds=%s 过滤后 0 个落位。本书例题种类：%s' % (
                len(pre), a.kinds, dict(Counter(b['kind'] for b in pre))), diag)
            return 2
        blocks_meta = {'all_blocks': len(blocks), 'selected': len(pre), 'kinds': a.kinds,
                       'by_kind': dict(Counter(p['kind'] for pls in placements.values() for p in pls)),
                       'matched_by': dict(Counter(b.get('matched_by') for b in pre)),
                       'profile_generic': bool(use_prof.get('_generic'))}
    key_lines = []
    if a.keys:
        key_lines = [ln.split('#', 1)[0].strip() for ln in Path(a.keys).read_text(encoding='utf-8').splitlines()]
    key_lines = [x for x in key_lines + (a.key or []) if x and x.strip()]
    if (a.keys or a.key) and not key_lines and not a.docx:
        raise InputError('题键清单为空：%s' % (a.keys or a.key))
    for line in key_lines:
        k, sq = parse_key_arg(line)
        res = [{'key': k, 'subq': sq, 'status': 'ok'}] if k else resolve_all(line, bank, keymap)
        for r in res:
            n_pl += 1
            if r['status'] not in ('ok', 'no_question_md'):
                unresolved.append({'title': line, 'status': r['status'], 'key': r.get('key'), 'candidates': r.get('candidates'),
                                   'notes': r.get('notes')})
                continue
            placements[r['key']].append({'title': line, 'kind': 'list', 'part': '', 'path': {}, 'subq': r.get('subq'),
                                         'resolve_basis': 'list', '_material': ''})
    t_res = time.perf_counter()
    book_id = (prof or {}).get('book_id')
    recs = OrderedDict()
    for k, pls in placements.items():
        subqs = list(dict.fromkeys(p.get('subq') for p in pls))
        r = analyse_key(bank, k, rulings, ledger_by, subqs=subqs, layers=layers, max_chars=a.max_chars, book=book_id,
                        hash_sources=not a.no_source_hash)
        pend = [p for p in pls if p.get('identity_pending')]
        if pend:
            alt = pend[0]['identity_alternative']
            r['identity_pending'] = OrderedDict(generic_probe=alt['generic_probe'], alternative_key=alt['alternative_key'],
                                                alternative_probe=alt['alternative_probe'], placements=len(pend),
                                                titles=[p['title'] for p in pend])
            if len(pend) == len(pls):
                r['identity_status'] = 'pending'
        red = [p['identity_redirected'] for p in pls if p.get('identity_redirected')]
        if red:
            r['identity_redirected'] = red
        # 题面比对优先用题面样式/【题目】栏目取到的文字；只有“栏目前段落”时记下来源，不据此判题库题面有误
        good = [p for p in pls if p.get('_material') and not p.get('identity_pending')]
        good.sort(key=lambda p: {'style': 0, 'label': 1}.get(p.get('material_basis'), 2))
        mat = good[0]['_material'] if good else next((p['_material'] for p in pls if p.get('_material')), '')
        mat_basis = good[0].get('material_basis') if good else None
        r['probe'] = None
        if mat and r.get('md_exists'):
            stem_txt = '\n'.join(s.get('_text', '') for L in ('stem', 'stem_adj') for s in r['layers'][L]['sections'])
            ps = list(probe_text(mat, stem_txt)) if stem_txt else None
            r['probe'] = {'stem': ps, 'md': list(probe(mat, bank.md_path(k))), 'material_basis': mat_basis}
            # 同一 MD 另一题面小节比采用的那节更对得上（≥PROBE_MIN 且领先≥PROBE_LEAD）：附上那一节，交模型确认
            if ps and ps[1] and r.get('identity_status') != 'pending':
                best = None
                for alt_s in r.get('_stem_alts') or []:
                    sc = probe_text(mat, alt_s['body'])
                    if sc[0] >= PROBE_MIN and sc[0] - ps[0] >= PROBE_LEAD and (best is None or sc[0] > best[0][0]):
                        best = (sc, alt_s)
                if best:
                    sc, alt_s = best
                    body = alt_s['body']
                    tr = {'total_chars': len(body), 'kept_chars': a.max_chars} if a.max_chars and len(body) > a.max_chars else None
                    r['stem_selection'] = OrderedDict(
                        adopted_heading=[s['heading'] for s in r['layers']['stem']['sections']], adopted_probe=ps,
                        alternative_heading=alt_s['heading'], alternative_probe=list(sc),
                        alternative_lines=[alt_s['line_start'], alt_s['line_end']])
                    r['layers']['stem']['sections'].append(OrderedDict(
                        heading=alt_s['heading'], line_start=alt_s['line_start'], line_end=alt_s['line_end'], chars=len(body),
                        section_sha256=alt_s['section_sha256'], role_basis=alt_s['role_basis'], bank_layer='stem',
                        level=alt_s['level'], bank_level=alt_s['level'], truncated=tr, page_images=[], page_images_unreadable=[],
                        page_images_missing=[], probe_matched_alternative=list(sc),
                        _text=body if not tr else body[:a.max_chars]))
        for p in pls:
            p.pop('_material', None)
        r['placements'] = pls
        r['subqs'] = sorted({s for s in subqs if s})
        recs[k] = r
    t_an = time.perf_counter()
    # 同一个书名写法（卷名段）解析到多个卷号：多半是题库或书对“期中”年份的写法不一
    by_label = defaultdict(lambda: defaultdict(list))
    for k, r in recs.items():
        for p in r.get('placements') or []:
            if p.get('exam_label'):
                by_label[p['exam_label']][k.rsplit('-Q', 1)[0]].append(p['title'])
    for u in unresolved:
        for c in u.get('candidates') or []:
            if u.get('exam_label'):
                by_label[u['exam_label']][c.rsplit('-Q', 1)[0] + '（候选）'].append(u['title'])
    same_name = [{'exam_label': lab, 'exams': {e: len(v) for e, v in ex.items()},
                  'titles': {e: v[:3] for e, v in ex.items()}}
                 for lab, ex in sorted(by_label.items()) if len({e.replace('（候选）', '') for e in ex}) > 1]
    # 疑似题源行未收：只报与本次选择器同范围的行（按部分/节点/主体过滤）
    unc = [u for u in diag.get('uncollected_source_lines', [])
           if select_blocks([dict(u, kind='?')], a, apply_kinds=False)] if a.docx else []
    extra = OrderedDict(identity_alternatives=alts, uncollected_source_lines=unc,
                        same_name_multi_exam=same_name, kind_qtype_conflict=kind_conflicts, kind_reclassified_by_qtype=reclassified,
                        exam_inferred_from_context=ctx_inferred)
    summ, lists = summarize(recs, unresolved, n_pl, extra)
    gen_at = time.strftime('%Y-%m-%dT%H:%M:%S%z')
    docx_sha = file_sha(a.docx) if a.docx else None
    pid = sha256_text(canon([gen_at, docx_sha, sorted(recs)]))[:16]
    meta = OrderedDict(
        tool='qpack.py', schema='qpack-packet/2', packet_id=pid, generated_at=gen_at,
        docx=str(Path(a.docx).resolve()) if a.docx else None, docx_sha256=docx_sha,
        profile=(prof or {}).get('book_id') or ('_generic' if a.docx else None),
        selector={'part': a.part, 'node': a.node, 'node_level': a.node_level, 'node_exact': a.node_exact,
                  'subject': a.subject, 'kinds': a.kinds, 'keys_file': a.keys, 'key': a.key},
        blocks=blocks_meta, layers=layers, max_chars=a.max_chars,
        bank={'root': str(bank.root), 'manifest': str(bank.manifest_path), 'manifest_updated_at': bank.manifest_updated,
              'manifest_sha256': bank.manifest_sha, 'bank_py_sha256': file_sha(bank.root / 'scripts/bank.py'),
              'role_tables_sha256': bank.tables_sha},
        keymap={'path': keymap['_path'], 'version': keymap.get('version'), 'sha256': keymap['_sha']},
        rulings={'path': rulings['path'], 'version': rulings['version'], 'sha256': rulings['_sha'],
                 'accepted': [r['req_id'] for r in rulings['rulings']], 'rejected': rulings['rejected']},
        view_ledger={'paths': a.ledger or [], 'sha256': ledger_sha},
        probe_threshold={'min': PROBE_MIN, 'lead': PROBE_LEAD},
        notice='只截取原文，不含归纳；' + MECH_NOTICE,
        timing={'load_s': round(t_env - t0, 3), 'resolve_s': round(t_res - t_env, 3),
                'analyse_s': round(t_an - t_res, 3)},
    )
    write_packet(a.out, meta, recs, lists, summ, layers, json_text=a.json_text)
    meta['timing']['total_s'] = round(time.perf_counter() - t0, 3)
    # 把总耗时补写进 packet.json
    pj = Path(a.out) / 'packet.json'
    d = json.loads(pj.read_text(encoding='utf-8'))
    d['meta']['timing'] = meta['timing']
    d['summary_zh'] = zh_summary(summ, meta)
    pj.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({'out': str(Path(a.out).resolve()), 'summary': summ, 'timing': meta['timing']},
                     ensure_ascii=False, indent=1))
    print(d['summary_zh'])
    need = (lists['unresolved_titles'] or lists['no_question_md'] or lists['identity_pending']
            or lists['uncollected_source_lines'] or lists['same_name_multi_exam'])
    return 3 if need else 0


def get_exit_code(r, sq=None):
    """退出码只表达等级，不表达“可以直接引用”：bank_accepted 也不等于主代理已核原页。"""
    st = r['e1_status']
    if r.get('e1_by_subq'):
        st = r['e1_by_subq'].get(sq or '整题', st)
    if r.get('view_conflicts'):
        return 25
    if st == 'named_exception':
        return 40
    if st in ('pointer_only', 'ruling_page_only'):
        return 20
    if st != 'ok':
        return 30
    return {'main_viewed': 0, 'subagent_viewed': 15, 'bank_accepted': 10}.get(r['e1_level'], 20)


def cmd_get(a):
    prof, bank, keymap, rulings = _common_env(a)
    for lp in a.ledger or []:
        if not Path(lp).exists():
            raise InputError('看页账本不存在：%s' % lp)
    k, sq = parse_key_arg(a.key)
    if not k:
        r = resolve_title(a.key, bank, keymap)
        if r['status'] != 'ok':
            raise InputError('无法解析：%s（%s）' % (a.key, r['status']))
        k, sq = r['key'], r.get('subq')
    ledger_by, _ = load_view_ledger(a.ledger)
    layers = ALL_LAYERS if a.layers == 'all' else [x.strip() for x in a.layers.split(',') if x.strip()]
    r = analyse_key(bank, k, rulings, ledger_by, subqs=[sq], layers=layers, book=(prof or {}).get('book_id'),
                    max_chars=a.max_chars, hash_sources=False)
    r['placements'] = []
    r.pop('_stem_alts', None)
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    else:
        print(slice_md(r, layers, time.strftime('%Y-%m-%dT%H:%M:%S'), str(bank.root)))
    return get_exit_code(r, sq)


def cmd_check(a):
    t0 = time.perf_counter()
    p = Path(a.packet)
    if p.is_dir():
        p = p / 'packet.json'
    if not p.exists():
        raise InputError('取材包不存在：%s' % p)
    try:
        pk = json.loads(p.read_text(encoding='utf-8'))
        meta = pk['meta']
    except (ValueError, KeyError) as e:
        raise InputError('不是 qpack 取材包：%s（%s）' % (p, e))
    bank = Bank(meta['bank']['root'], meta['bank']['manifest'])
    rulings = load_rulings(meta['rulings']['path'])
    ledger_by, ledger_sha = load_view_ledger(meta['view_ledger']['paths'])
    keymap = load_keymap(meta['keymap']['path'])
    stale = []
    global_changes = []
    if keymap['_sha'] != meta['keymap']['sha256']:
        global_changes.append('keymap_changed')
    if bank.tables_sha != meta['bank']['role_tables_sha256']:
        global_changes.append('bank_role_tables_changed')
    if meta.get('docx'):
        if not Path(meta['docx']).exists():
            global_changes.append('docx_missing')
        elif file_sha(meta['docx']) != meta.get('docx_sha256'):
            global_changes.append('docx_changed')  # 书稿改了：例题落位可能变了，须重建包
    # 切片与包对不上（目录被别的包复用、切片被改名或残留）
    qd = p.parent / 'q'
    if meta.get('packet_id') and qd.is_dir():
        keys = {r['key'] for r in pk['keys']}
        foreign, missing = [], []
        for f in qd.glob('*.md'):
            head = f.read_text(encoding='utf-8', errors='replace')[:600]
            if f.stem not in keys or ('packet_id=%s' % meta['packet_id']) not in head:
                foreign.append(f.name)
        missing = [k for k in keys if not (qd / (k + '.md')).exists()]
        if foreign:
            global_changes.append('slices_foreign(%d)' % len(foreign))
        if missing:
            global_changes.append('slices_missing(%d)' % len(missing))
    for old in pk['keys']:
        k = old['key']
        subqs = list(dict.fromkeys(pl.get('subq') for pl in old.get('placements') or [])) or [None]
        new = analyse_key(bank, k, rulings, ledger_by, subqs=subqs, layers=meta['layers'], book=meta.get('profile'),
                          max_chars=meta.get('max_chars') or 0, hash_sources=False, keep_text=False)
        of, nf = old.get('fingerprint', {}), new['fingerprint']
        why = []
        if of.get('md_sha256') != nf.get('md_sha256'):
            same_e1 = of.get('sections', {}).get('e1') == nf.get('sections', {}).get('e1')
            why.append('md_sha_changed' + ('(E1小节未变)' if same_e1 else ''))
        for f in ('manifest_status', 'state_status', 'state_accepted', 'accepted_at', 'state_qhash'):
            if of.get(f) != nf.get(f):
                why.append('acceptance_changed:%s' % f)
        if of.get('residuals_sha') and of.get('residuals_sha') != nf.get('residuals_sha'):
            why.append('residuals_changed')
        for L in set(of.get('sections', {})) | set(nf.get('sections', {})):
            if of.get('sections', {}).get(L) != nf.get('sections', {}).get(L):
                why.append('section_changed:%s' % L)
        if of.get('rulings') != nf.get('rulings'):
            why.append('ruling_changed')
        if of.get('ledger') != nf.get('ledger'):
            why.append('view_ledger_changed')
        if of.get('tables_sha') != nf.get('tables_sha'):
            why.append('bank_role_tables_changed')
        # 源文件：大小与 mtime 未变视为未变；变了（或 --rehash）才重算 SHA
        for s in old.get('sources', []):
            pth = s.get('path')
            if not pth or not Path(pth).exists():
                if not s.get('missing_on_disk'):
                    why.append('source_missing:%s' % s['source_id'])
                continue
            stt = Path(pth).stat()
            if a.rehash or stt.st_size != s.get('size') or stt.st_mtime_ns != s.get('mtime_ns'):
                if s.get('sha256') and file_sha(pth) != s['sha256']:
                    why.append('source_sha_changed:%s' % s['source_id'])
            reg = (bank.sources.get(s['source_id']) or {}).get('sha256')
            if reg != s.get('registered_sha256'):
                why.append('source_registration_changed:%s' % s['source_id'])
        if old.get('placements') and any((pl.get('resolve_basis') or '').find('override') >= 0 for pl in old['placements']) \
                and 'keymap_changed' in global_changes:
            why.append('keymap_changed')
        if why:
            stale.append({'key': k, 'reasons': why, 'old_e1_level': old.get('e1_level'), 'new_e1_level': new.get('e1_level'),
                          'old_e1_status': old.get('e1_status'), 'new_e1_status': new.get('e1_status')})
    res = OrderedDict(packet=str(p), packet_id=meta.get('packet_id'), checked=len(pk['keys']), stale=len(stale),
                      global_changes=global_changes, stale_keys=stale, seconds=round(time.perf_counter() - t0, 3),
                      notice=MECH_NOTICE)
    if a.out:
        guard_out(a.out, what='检查结果')
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(res if a.json else {k: v for k, v in res.items() if k != 'stale_keys'}, ensure_ascii=False, indent=1))
    print('检查 %d 题，失效 %d 题%s。%s' % (res['checked'], res['stale'],
                                        ('；全局变化：' + '、'.join(global_changes)) if global_changes else '', MECH_NOTICE))
    return 1 if stale or global_changes else 0


def cmd_ledger_add(a):
    guard_out(a.ledger, what='看页账本')
    lp = Path(a.ledger)
    if lp.exists():
        # 只往 qpack-view/1 格式的账本里追加：逐行校验，有一行不合格就拒绝
        for i, ln in enumerate(lp.read_text(encoding='utf-8').splitlines()):
            if not ln.strip():
                continue
            try:
                d = json.loads(ln)
            except ValueError:
                raise InputError('账本第 %d 行不是 JSON，拒绝追加：%s' % (i + 1, lp))
            why = view_row_problems(d)
            if why:
                raise InputError('账本第 %d 行不是 %s 格式（%s），拒绝追加：%s' % (i + 1, VIEW_SCHEMA, '、'.join(why), lp))
    _, bank, keymap, rulings = _common_env(a)
    k, _ = parse_key_arg(a.key)
    if not k:
        r = resolve_title(a.key, bank, keymap)
        if r['status'] != 'ok':
            raise InputError('无法解析：%s' % a.key)
        k = r['key']
    if not bank.md_path(k).exists():
        raise InputError('题库无此题级 MD：%s' % k)
    if not a.page_png and not (a.source_id and a.page):
        raise InputError('必须给出原页证据：--page-png 或 --source-id＋--page')
    rec = analyse_key(bank, k, rulings, {}, layers=ALL_LAYERS, hash_sources=False, keep_text=False)
    layer = a.layer.lower()
    secs = [s for s in (rec.get('layers') or {}).get(layer, {}).get('sections', []) if not s.get('pointer_only')]
    if a.section:
        secs = [s for s in secs if s['heading'] == a.section]
        if not secs:
            raise InputError('该层没有标题为“%s”的正文小节' % a.section)
    ent = OrderedDict(schema=VIEW_SCHEMA, key=k, layer=layer, by=a.by, agent_id=a.agent_id, model=a.model,
                      at=time.strftime('%Y-%m-%dT%H:%M:%S%z'), md_sha256=rec.get('md_sha256'),
                      section_heading=secs[0]['heading'] if len(secs) == 1 else None,
                      section_sha256=secs[0]['section_sha256'] if len(secs) == 1 else None,
                      page_png=str(Path(a.page_png).resolve()) if a.page_png else None,
                      page_png_sha256=file_sha(a.page_png) if a.page_png else None,
                      source_id=a.source_id, page=a.page,
                      source_sha256=(bank.sources.get(a.source_id) or {}).get('sha256') if a.source_id else None,
                      verdict=a.verdict, note=a.note)
    exam = k.rsplit('-Q', 1)[0]
    why, warn = view_evidence_problems(ent, bank, k, unreadable_images(bank, exam, k))
    if why:
        raise InputError('原页证据不成立（%s），未登记' % '、'.join(why))
    if warn:
        ent['warnings'] = warn
    if not secs:
        ent['warning'] = '该层题库没有正文小节：本条只记“看过原页”，不计已核等级'
    elif len(secs) > 1:
        ent['warning'] = '该层有 %d 个正文小节，未绑定小节SHA（将升该层全部正文小节）；用 --section 指定标题' % len(secs)
    lp.parent.mkdir(parents=True, exist_ok=True)
    with open(lp, 'a', encoding='utf-8') as f:
        f.write(json.dumps(ent, ensure_ascii=False) + '\n')
    print(json.dumps(ent, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a):
    """抽样对照 bank.py get --with-rubric：比较两边认定的 E1 标准标题与输出字数。"""
    if a.out:
        guard_out(a.out, what='自检结果')
    _, bank, keymap, rulings = _common_env(a)
    keys = []
    for exam in sorted(bank.tasks):
        for q in (16, 17, 18, 19, 20, 21):
            k = '%s-Q%d' % (exam, q)
            if bank.md_path(k).exists():
                keys.append(k)
    step = max(1, len(keys) // a.n)
    keys = keys[::step][:a.n]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    rows, agree = [], 0
    for k in keys:
        t0 = time.perf_counter()
        out = subprocess.run([sys.executable, '-B', 'bank.py', 'get', k, '--with-rubric'], cwd=str(bank.root / 'scripts'),
                             capture_output=True, text=True, env=env, timeout=120).stdout
        dt = time.perf_counter() - t0
        heads = set(re.findall(r'^## (.+)$', out, re.M))
        bank_e1 = sorted(h.strip() for h in heads if h.strip() in bank.tables['e1'] or h.strip() in bank.tables['qid_e1'].get(k, ()))
        r = analyse_key(bank, k, rulings, {}, layers=DEFAULT_LAYERS, hash_sources=False)
        ours = sorted(s['heading'] for s in r['layers']['e1']['sections'] if s['role_basis'] == 'bank_alias')
        ours_all = [s['heading'] for s in r['layers']['e1']['sections']]
        empty = sorted(h for h in r.get('empty_e1_headings', []) if h in bank.tables['e1'])
        # bank.py 会原样输出“（未找到已确认的正式评分材料）”这类空 E1 标题；qpack 把它记为空而不当 E1
        ok = bank_e1 == sorted(ours + empty)
        agree += ok
        slice_chars = sum(s['chars'] for L in ('e1', 'stem', 'stem_adj') for s in r['layers'][L]['sections'])
        rows.append({'key': k, 'agree_alias_e1': ok, 'bank_get_e1': bank_e1, 'qpack_alias_e1': ours, 'qpack_e1_all': ours_all,
                     'bank_e1_heading_but_empty': empty, 'declared_absent': r.get('e1_declared_absent'),
                     'bank_get_chars': len(out), 'qpack_e1_stem_chars': slice_chars, 'bank_get_s': round(dt, 3)})
    res = {'n': len(rows), 'alias_e1_agree': agree, 'bank_e1_heading_but_empty': sum(1 for x in rows if x['bank_e1_heading_but_empty']),
           'qpack_extra_e1_by_regex_or_ruling': sum(1 for x in rows if len(x['qpack_e1_all']) > len(x['qpack_alias_e1'])),
           'bank_get_chars': sum(x['bank_get_chars'] for x in rows),
           'qpack_e1_stem_chars': sum(x['qpack_e1_stem_chars'] for x in rows),
           'bank_get_seconds': round(sum(x['bank_get_s'] for x in rows), 2), 'rows': rows}
    if a.out:
        Path(a.out).mkdir(parents=True, exist_ok=True)
        (Path(a.out) / 'selftest.json').write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in res.items() if k != 'rows'}, ensure_ascii=False, indent=1))
    print('抽样 %d 题：E1 标准标题与 bank.py get 一致 %d 题。' % (res['n'], agree))
    return 0 if agree == len(rows) else 1


def build_parser():
    ap = argparse.ArgumentParser(description='题键→取材包：解析题源、按角色截取题库原文、标证据等级、叠加用户裁定、判失效（只读）。')
    ap.add_argument('--bank', help='题库根目录（默认按书册配置或 %s）' % DEFAULT_BANK)
    ap.add_argument('--manifest', help='题库总清单 conversion_manifest.json')
    ap.add_argument('--keymap', help='身份更正表（默认 qpack_data/keymap_overrides.json）')
    ap.add_argument('--rulings', help='用户裁定表（默认 qpack_data/rulings.json）')
    sub = ap.add_subparsers(dest='cmd')

    p = sub.add_parser('resolve', help='题源写法→题键（一行多个题源会逐个列出）')
    p.add_argument('titles', nargs='+', help='题源写法或题键')
    p.add_argument('--json', action='store_true', help='输出 JSON')
    p.set_defaults(f=cmd_resolve)

    p = sub.add_parser('build', help='批量建包（题键清单或书稿＋节点/主体）')
    p.add_argument('--docx', help='书稿 DOCX（只读）')
    p.add_argument('--profile', help='书册配置名或路径（默认按 DOCX 路径识别；识别不到用通用口径）')
    p.add_argument('--part', help='只收这些部分（配置 structure.parts 的 id，逗号分隔）')
    p.add_argument('--node', action='append', help='节点名（在 h1/h2/考法/组标题里查找，可重复）')
    p.add_argument('--node-level', default='any', choices=['any', 'h1', 'h2', 'method', 'group'], help='节点所在层级')
    p.add_argument('--node-exact', action='store_true', help='节点名去编号后完全相等才算')
    p.add_argument('--subject', help='主体名（考法样式标题去编号后完全相等，如 政府）；找不到时列出本书主体名')
    p.add_argument('--kinds', default=None, help='例题种类，逗号分隔（默认配置里除 choice 外的全部，加 topic_case、topic_list；all=全部）')
    p.add_argument('--any-heading', action='store_true', help='例题标题样式里凡能解析出题源的都收（非标准书册用）')
    p.add_argument('--keys', help='题键清单文件：每行一个题键、KEY(小问) 或题源写法，# 后为注释')
    p.add_argument('--key', action='append', help='直接给题键或题源写法（可重复）')
    p.add_argument('--out', required=True, help='输出目录（只准系统临时目录或书册配置 qpack.out_dirs 登记的目录）')
    p.add_argument('--layers', default='stem,e1', help='要截取的层：stem,e1,e3,candidate,student,lecture 或 all（默认 stem,e1）')
    p.add_argument('--max-chars', type=int, default=0, help='每节最多保留字数，0=不截断；截断处会标注')
    p.add_argument('--ledger', action='append', help='看原页账本 JSONL（可重复）')
    p.add_argument('--no-source-hash', action='store_true', help='不计算源文件 SHA（只记大小与修改时间）')
    p.add_argument('--json-text', action='store_true', help='packet.json 里也保存截取的原文')
    p.add_argument('--no-identity-check', action='store_true', help='不做书中题面↔题库题面的身份探针')
    p.add_argument('--probe-redirect', action='store_true',
                   help='探针找到唯一更好的备选卷时改用备选题键（默认只列为身份待定，不改映射）')
    p.set_defaults(f=cmd_build)

    p = sub.add_parser('get', help='单题切片输出到 stdout（不写文件）')
    p.add_argument('key', help='题键、KEY(小问) 或题源写法')
    p.add_argument('--layers', default='stem,e1', help='同 build')
    p.add_argument('--max-chars', type=int, default=0, help='每节最多保留字数')
    p.add_argument('--ledger', action='append', help='看原页账本 JSONL')
    p.add_argument('--profile', help='书册配置名（只影响限定某册的裁定）')
    p.add_argument('--json', action='store_true', help='输出 JSON 明细')
    p.set_defaults(f=cmd_get)

    p = sub.add_parser('check', help='失效判定：书稿、源文件、题级MD、验收状态、残留记录、裁定、账本任一变化即 stale')
    p.add_argument('packet', help='packet.json 或其所在目录')
    p.add_argument('--rehash', action='store_true', help='源文件一律重算 SHA（默认大小与 mtime 未变即视为未变）')
    p.add_argument('--out', help='把检查结果另存 JSON（同样受写入白名单约束）')
    p.add_argument('--json', action='store_true', help='stdout 输出完整明细')
    p.set_defaults(f=cmd_check)

    p = sub.add_parser('ledger-add', help='往看原页账本追加一条（校验原页属于本卷，自动绑定当前 MD/小节/页图 SHA）')
    p.add_argument('--ledger', required=True, help='账本 JSONL 路径（受写入白名单约束；已存在时须为 qpack-view/1 格式）')
    p.add_argument('--key', required=True, help='题键或题源写法')
    p.add_argument('--layer', default='e1', help='stem/e1/e3/candidate')
    p.add_argument('--section', help='小节标题（该层有多个小节时建议指定）')
    p.add_argument('--by', required=True, choices=['main', 'subagent'], help='谁看的原页')
    p.add_argument('--agent-id', required=True, help='会话或代理 ID（如 claude:<session>）')
    p.add_argument('--model', help='实际模型')
    p.add_argument('--page-png', help='看过的原页图（须在本卷 questions/<卷>/ 或 evidence/<本卷来源>/ 下，PNG/JPEG）')
    p.add_argument('--source-id', help='本卷来源 source_id（与 --page 一起用）')
    p.add_argument('--page', type=int, help='源文件页码（不超过登记页数）')
    p.add_argument('--verdict', default='exact', choices=['exact', 'corrected', 'mismatch'],
                   help='核对结论：exact 与题库原文一致；corrected/mismatch 表示题库原文与原页不符（不升等级）')
    p.add_argument('--note', help='备注（照录，不做归纳）')
    p.set_defaults(f=cmd_ledger_add)

    p = sub.add_parser('selftest', help='抽样对照 bank.py get --with-rubric（子进程 -B，不写 pyc）')
    p.add_argument('--n', type=int, default=30, help='抽样题数')
    p.add_argument('--out', help='结果目录')
    p.set_defaults(f=cmd_selftest)
    return ap


def main(argv=None):
    ap = build_parser()
    a = ap.parse_args(argv)
    if not getattr(a, 'f', None):
        ap.print_help()
        return 2
    try:
        return a.f(a)
    except InputError as e:
        print('输入错误：%s' % e, file=sys.stderr)
        return 2
    except (zipfile.BadZipFile, FileNotFoundError, IsADirectoryError, NotADirectoryError, UnicodeDecodeError) as e:
        print('输入错误：%s: %s' % (type(e).__name__, e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
