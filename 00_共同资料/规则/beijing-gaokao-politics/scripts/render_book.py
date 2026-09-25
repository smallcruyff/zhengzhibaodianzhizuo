#!/usr/bin/env python3
"""render_book.py：按书册配置把 DOCX 渲染成 PDF，带渲染缓存、同版身份、嵌入字体审计和写入边界保护。

合并了 measure/render/render_cache.py 与各批 render_b5x.py 的 03/05 两步：
  - 从 profile.render 读 soffice、render_docx.py 的 glob（取纯数字版本号最大的一份，记录路径、版本、内容哈希）、
    PATH 前置、lo_profile；另记 LibreOffice 构建号（Resources/versionrc 的 buildid）、运行时 manifest.json
    （version/sourceRef/patchSha256）、soffice 可执行文件 SHA 与程序包文件指纹，全部进缓存键和同版身份；
  - 按 profile.render.fontconfig 生成私有 fontconfig（historical_file 派生或 house 模板），cachedir 一律改到缓存目录；
    源文件含 <include>、带 prefix 或非绝对路径的 <dir> 时拒绝（本工具不展开这些写法）；
  - 默认只出 PDF：导入 render_docx.py，只调 make_renderable_docx_copy 与 convert_to_pdf，跳过整书转 PNG；
    --png 才转图，可用 --pages 只转指定页；图放在 png/<PDF哈希前16位>_<dpi>dpi_<光栅器>/，每次先清掉该目录里的旧页图；
  - 缓存键 = DOCX SHA256 + 渲染环境 env_sha256 + 模式 + 是否允许 ODT 回退；命中直接复用；缓存 PDF 与输出 PDF
    尽量用硬链接，不重复占盘；--prune-cache 清旧条目；
  - 写同版身份 JSON（字段按 profile.render.record，另加 env_sha256、门结果 gates、对照历史）；status 由门结果决定；
  - 字体审计：①汉字回退门，与 batch_health 共用 profile.pdf_fonts（expected_cjk_regex、fail_min_chars_page，符号不计）；
    ②请求与实得核对：按 DOCX 片段请求的东亚字体抽样，在 PDF 里定位同一段文字，看实际字体是否属于请求字族或书册别名目标；
    ③其余非书册字体（符号等）只列出，不计门。profile.render.font_embed_audit=false 时整项跳过。

同版身份里 fontconfig_sha256 的含义：与书册 historical_file 语义等价（去掉注释与 cachedir 后逐项相同）时取历史文件本身
的 SHA256（与旧 render_b5x 同版身份可比）；否则取规范化语义签名的 SHA256。两者都与输出目录无关。派生文件本身的 SHA
另记 fontconfig_file_sha256，纯语义签名另记 fontconfig_semantic_sha256。

用法：
  python3 render_book.py --docx 本批.docx --out-dir 构建/rendered [--book bixiu3]
  python3 render_book.py --docx X.docx --out-dir D --compare-pdf 上次同一DOCX的.pdf     # 页数、逐页文本、逐页字体用字量
  python3 render_book.py --docx X.docx --out-dir D --png --pages 1-4,321               # 只给指定页出 PNG
  python3 render_book.py --docx X.docx --out-dir D --mode soffice                       # 目录定位用的直接 soffice 转换
  python3 render_book.py --docx X.docx --out-dir D --key-only                           # 只算缓存键、看是否命中，不写盘
  python3 render_book.py --out-dir D --prune-cache --keep 3                             # 只清缓存旧条目
  作为模块：from render_book import render_book; res = render_book(docx, out_dir, book='bixiu3')

写入边界（只读承诺）：源 DOCX 先复制到 <out-dir>/.work 再交给 LibreOffice，锁文件不会落在书稿旁边；不修改、移动、重存
任何书稿、审阅入口、协作文件。所有写入目标（输出目录、PDF、同版身份、缓存、lo_profile、PNG 目录）在写盘前统一检查，
按文件身份（inode）比较，大小写或符号链接改写绕不过去：
  - 任一冻结册（profiles/ 下所有 frozen=true 的书册，不论本次选的是哪本）的目录，以及名称匹配其 paths.frozen_globs
    （未配置时按工作区名前缀，如 必修二*、00_必修二*）的任何目录，一律拒写；渲染冻结册的 DOCX 时只允许写到项目根以外；
  - 所有书册的审阅入口与审阅历史、中心状态目录、协作目录（只允许 协作/候选/<执行者>/<批次>/<子目录> 以下）、
    接管.json 等协作状态文件、工作区根目录、书稿同目录、任何直接含 DOCX 的目录、本 Skill 目录，一律拒写；
  - 项目根内只允许写到非冻结册的工作区里；
  - --pdf-name 只接受纯文件名，--identity 必须在输出目录内；已存在且不是本工具写的同版身份或 PDF 不覆盖。
失败不静默重跑：render_docx 内部的 DOCX→ODT→PDF 回退默认被拦下并报告（--allow-odt-fallback 才放行）。
门全过只说明机械层没有回退，不代表版面或内容已审；对照测不到纯像素差异，逐页文本与字体一致也不等于像素一致，
不能据此继承已看页（已看页复用仍按“同页、完整像素完全一致”）。

退出码：0 成功（渲染或命中缓存；status 里可能仍有 WARN）；1 未预期异常；2 输入、配置或渲染环境缺失（含书册不一致、
页码写法错误、fontconfig 写法不支持、运行时 Python 不合用）；3 渲染失败（超时、无 PDF、被拦下的 ODT 回退、渲染器
接口不符）；4 拒绝写入；5 本次 --compare-pdf 不一致（页数、逐页文本或逐页字体用字量）；6 给了 --fail-on-fallback
且有汉字字体回退（FAIL 或 WARN 页）；7 给了 --fail-on-substitution 且请求与实得字族不符。
"""
import argparse
import copy
import datetime
import fcntl
import fnmatch
import glob
import hashlib
import json
import os
import plistlib
import re
import shutil
import signal
import struct
import subprocess
import sys
import time
import unicodedata
import zipfile
from bisect import bisect_right
from collections import Counter, OrderedDict
from pathlib import Path

sys.dont_write_bytecode = True  # 不在 Skill 目录里留 __pycache__
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from profile_lib import load_profile, list_profiles, resolve, frozen_guard  # noqa: E402

TOOL = 'render_book.py/2.0'
AUDIT_REV = 'audit-5'  # 审计算法变了就改它，缓存里的旧审计自动作废
MECH_NOTE = ('本工具只查机械层：是否出 PDF、页数、嵌入字体（汉字回退、请求与实得字族）、与对照 PDF 的逐页文本和逐页字体用字量。'
             '门全过只说明机械层没有回退，不代表版面或内容已审；对照测不到纯像素差异，逐页文本与字体一致也不等于像素一致，'
             '不能据此继承已看页（已看页复用仍按“同页、完整像素完全一致”）。')

# 书册配置未写时的默认值（新字段见返回的 profile_fields_needed）
DEFAULTS = {
    'python': '~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',
    'timeout_s': 900,
    'png_engine': 'pdftoppm',
    'house_dirs': ['/System/Library/Fonts', '/System/Library/Fonts/Supplemental', '/Library/Fonts', '~/Library/Fonts'],
    'asset_globs': ['/System/Library/AssetsV2/PreinstalledAssetsV2/InstallWithOs/com_apple_MobileAsset_Font*/*.asset/AssetData',
                    '/System/Library/AssetsV2/com_apple_MobileAsset_Font*/*.asset/AssetData'],
    'cjk_regex': r'^(STSongti|STKaiti)',   # 与 batch_health 的默认值相同
    'cjk_fail_min': 20,
    'subst_per_family': 80,
    'subst_min_cjk': 6,
    'subst_width': 12,
}
GENERIC_FAMILIES = {'sans-serif', 'serif', 'monospace', 'sans', 'mono', 'system-ui', 'cursive', 'fantasy'}
FONT_EXT = ('.ttf', '.otf', '.ttc', '.otc', '.dfont', '.pfb', '.pfa', '.otb')
CJK = re.compile('[㐀-䶿一-鿿豈-﫿]')  # 与 batch_health 相同
DIR_KEYS = ('workspace', 'aux_workspace', 'review_entry', 'review_history')
FILE_KEYS = ('handoff', 'central_state', 'review_manifest', 'progress_note')
ENV_KEYS = ('soffice_version', 'soffice_build_id', 'runtime_manifest_sha256', 'soffice_bin_sha256', 'lo_bundle_fingerprint',
            'renderer_version', 'renderer_sha256', 'fontconfig_semantic_sha256', 'font_files_sha256')
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'


class RenderError(Exception):
    """带退出码的失败；message 是给人看的中文原因。"""

    def __init__(self, code, message, detail=None):
        super().__init__(message)
        self.code = code
        self.detail = detail or {}


# ---------------------------------------------------------------- 小工具
def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def sha256_text(s):
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def sha256_json(obj):
    return sha256_text(json.dumps(obj, sort_keys=True, ensure_ascii=False))


def now_iso():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def xp(p):
    return Path(os.path.expanduser(str(p)))


def ranges(pages):
    """[1,2,3,7] → '1-3,7'"""
    ps = sorted(set(pages))
    out, i = [], 0
    while i < len(ps):
        j = i
        while j + 1 < len(ps) and ps[j + 1] == ps[j] + 1:
            j += 1
        out.append(str(ps[i]) if i == j else '%d-%d' % (ps[i], ps[j]))
        i = j + 1
    return ','.join(out)


def _expand(rs):
    out = []
    for part in filter(None, (rs or '').split(',')):
        a, _, b = part.partition('-')
        out.extend(range(int(a), int(b or a) + 1))
    return out


def parse_pages(spec, n):
    """'1-4,10,600-' → 排好序的页号；越界、写法不懂或解析结果为空都报错（退出码 2）。"""
    got = set()
    for part in filter(None, (x.strip() for x in (spec or '').split(','))):
        m = re.fullmatch(r'(\d+)?\s*-\s*(\d+)?|(\d+)', part)
        if not m:
            raise RenderError(2, '页码写法看不懂：%r（例：1-4,10,600-）' % part)
        if m.group(3):
            a = b = int(m.group(3))
        else:
            a = int(m.group(1) or 1)
            b = int(m.group(2) or n)
        if a < 1 or b > n or a > b:
            raise RenderError(2, '页码 %r 超出 1-%d' % (part, n))
        got.update(range(a, b + 1))
    if not got:
        raise RenderError(2, '--pages 解析后没有任何页（写法：1-4,10,600-）：%r' % spec)
    return sorted(got)


def clip(s, n):
    """截取原文；截断处明示。"""
    return s if len(s) <= n else s[:n] + '…〔截断〕'


def norm_family(s):
    return re.sub(r'[\s\-_]+', '', s or '').casefold()


def version_key(v):
    """数字段按数值、其余按字符串比较；纯数字版本号排在含字母的版本之后（优先取正式版本号）。"""
    parts = [p for p in re.split(r'[.\-_]', v or '') if p != '']
    numeric = bool(parts) and all(p.isdigit() for p in parts)
    return (1 if numeric else 0, tuple((1, int(p), '') if p.isdigit() else (0, 0, p) for p in parts))


# ---------------------------------------------------------------- 写入边界（按文件身份比较）
def _nk(s):
    return unicodedata.normalize('NFC', s).casefold()


def _abs(p):
    return os.path.normpath(os.path.abspath(os.path.expanduser(str(p))))


def _ino(p):
    try:
        st = os.stat(p)
        return (st.st_dev, st.st_ino)
    except OSError:
        return None


class _Loc(object):
    """一个受保护位置：realpath、大小写与 Unicode 归一后的键、存在时的 (st_dev, st_ino)。"""
    __slots__ = ('path', 'key', 'ino')

    def __init__(self, p):
        self.path = os.path.realpath(_abs(p))
        self.key = _nk(self.path)
        self.ino = _ino(self.path)


def _chain(p):
    """p 的 realpath 及其全部祖先 [(路径, 键, inode)]，从自身到根。"""
    cur = os.path.realpath(_abs(p))
    out = []
    while True:
        out.append((cur, _nk(cur), _ino(cur)))
        nxt = os.path.dirname(cur)
        if nxt == cur:
            return out
        cur = nxt


def _hit(entry, loc):
    # 两边都存在就比 inode（APFS 不区分大小写，字符串比较会被绕过）；否则比归一后的路径键
    if entry[2] is not None and loc.ino is not None:
        return entry[2] == loc.ino
    return entry[1] == loc.key


def _within(chain, loc):
    """chain 里若有与 loc 相同的祖先（含自身），返回从该祖先到目标的相对路径分量列表，否则 None。"""
    for ent in chain:
        if _hit(ent, loc):
            rest = chain[0][0][len(ent[0]):].strip(os.sep)
            return [x for x in rest.split(os.sep) if x]
    return None


def _components(p):
    a = _abs(p)
    r = os.path.realpath(a)
    return set(Path(a).parts[1:]) | set(Path(r).parts[1:])


def frozen_globs(P):
    """冻结册的目录名模式：paths.frozen_globs；未配置时按工作区目录名前缀（如 必修二*、00_必修二*）。"""
    paths = P.get('paths') or {}
    if paths.get('frozen_globs'):
        return list(paths['frozen_globs'])
    pre = Path(paths.get('workspace') or '').name.split('_')[0]
    return [pre + '*', '00_' + pre + '*'] if len(pre) >= 2 else []


def _glob_hit(comps, globs):
    return any(fnmatch.fnmatchcase(_nk(c), _nk(g)) for c in comps for g in globs)


def _title(P):
    return P.get('title') or P.get('book_id') or '?'


class WriteGuard(object):
    """汇总所有书册配置的受保护位置；check() 在写盘前调用，违规抛 RenderError(4)。"""

    def __init__(self, profiles, docx=None, selected=None):
        self.rules, self.roots, self.ws_ok, self.frozen = [], [], [], []
        seen = set()
        for P in profiles:
            pid = P.get('_profile_path') or P.get('book_id')
            if pid in seen:
                continue
            seen.add(pid)
            paths = P.get('paths') or {}
            if not paths.get('root'):
                continue

            def R(k, P=P, paths=paths):
                return resolve(P, paths[k])
            root = _Loc(resolve(P, '.'))
            self.roots.append((root, P))

            def parent_loc(k):
                # 文件所在目录；若恰是项目根就不当作受保护目录（否则整棵项目根都被锁住）
                loc = _Loc(R(k).parent)
                return None if _hit((loc.path, loc.key, loc.ino), root) else loc
            for k in ('review_entry', 'review_history'):
                if paths.get(k):
                    self.rules.append(('subtree', _Loc(R(k)), P, '审阅入口或审阅历史（发布另有工具与流程）'))
            for k in FILE_KEYS:
                if paths.get(k):
                    self.rules.append(('file', _Loc(R(k)), P, '协作或状态文件（%s）' % k))
            if paths.get('handoff') and parent_loc('handoff'):
                self.rules.append(('collab', parent_loc('handoff'), P, '协作目录'))
            if paths.get('central_state') and parent_loc('central_state'):
                self.rules.append(('subtree', parent_loc('central_state'), P, '中心状态目录'))
            for k in ('workspace', 'aux_workspace'):
                if paths.get(k):
                    self.rules.append(('exact', _Loc(R(k)), P, '书册工作区根目录（书稿旁边）'))
            if P.get('frozen'):
                locs = [_Loc(R(k)) for k in DIR_KEYS if paths.get(k)]
                locs += [l for l in (parent_loc(k) for k in FILE_KEYS if paths.get(k)) if l is not None]
                self.frozen.append((P, locs, frozen_globs(P)))
            else:
                for k in ('workspace', 'aux_workspace'):
                    if paths.get(k):
                        self.ws_ok.append(_Loc(R(k)))
        self.skill_dir = _Loc(HERE.parent)
        self.docx_dir = _Loc(Path(_abs(docx)).parent) if docx else None
        self.source_frozen = self.frozen_owner(docx) if docx else None
        if self.source_frozen is None and selected is not None and selected.get('frozen'):
            self.source_frozen = selected

    def frozen_owner(self, path):
        ch, comps = _chain(path), _components(path)
        for P, locs, globs in self.frozen:
            if any(_within(ch, l) is not None for l in locs) or _glob_hit(comps, globs):
                return P
        return None

    @staticmethod
    def _frozen_refuse(P, action):
        try:
            frozen_guard(P, action)
        except SystemExit as e:
            raise RenderError(4, str(e))
        raise RenderError(4, '%s 已冻结，拒绝%s' % (_title(P), action))

    def check(self, target, is_file=False):
        t = _abs(target)
        if is_file:
            f0 = _chain(t)[0]
            for kind, loc, P, label in self.rules:
                if kind == 'file' and _hit(f0, loc):
                    raise RenderError(4, '拒绝写入%s《%s》：%s' % (label, _title(P), t))
            d = os.path.dirname(t)
        else:
            d = t
        ch, comps = _chain(d), _components(d)
        for P, locs, globs in self.frozen:
            if any(_within(ch, l) is not None for l in locs) or _glob_hit(comps, globs):
                self._frozen_refuse(P, '写入本册目录 %s' % d)
        if self.source_frozen is not None:
            for loc, P in self.roots:
                if _within(ch, loc) is not None:
                    self._frozen_refuse(self.source_frozen, '把渲染产物写进项目根（冻结册只允许渲染到项目根以外，如 scratch）：%s' % d)
        if _within(ch, self.skill_dir) is not None:
            raise RenderError(4, '拒绝写入 Skill 目录：%s' % d)
        if self.docx_dir is not None and _hit(ch[0], self.docx_dir):
            raise RenderError(4, '拒绝写入书稿同目录：%s（请用子目录或 scratch 作 --out-dir）' % d)
        if os.path.isdir(d):
            try:
                names = os.listdir(d)
            except OSError:
                names = []
            docs = [n for n in names if n.lower().endswith('.docx') and not n.startswith('~$')]
            if docs:
                raise RenderError(4, '拒绝写入直接含 DOCX 的目录（书稿旁边）：%s（例：%s）' % (d, clip(docs[0], 40)))
        for kind, loc, P, label in self.rules:
            if kind == 'subtree' and _within(ch, loc) is not None:
                raise RenderError(4, '拒绝写入%s《%s》：%s' % (label, _title(P), d))
            if kind == 'exact' and _hit(ch[0], loc):
                raise RenderError(4, '拒绝写入%s《%s》：%s' % (label, _title(P), d))
            if kind == 'collab':
                rel = _within(ch, loc)
                if rel is not None and not (len(rel) >= 4 and _nk(rel[0]) == _nk('候选')):
                    raise RenderError(4, '拒绝写入%s《%s》：%s（协作目录内只允许写到 协作/候选/<执行者>/<批次>/<子目录> 以下）'
                                      % (label, _title(P), d))
        for loc, P in self.roots:
            if _within(ch, loc) is not None and not any(_within(ch, w) is not None for w in self.ws_ok):
                raise RenderError(4, '项目根内只允许写到非冻结册的工作区（且避开协作、状态、审阅目录）：%s' % d)
        return d


# ---------------------------------------------------------------- 书册配置与环境
def all_profiles(extra=None):
    out = []
    for n in list_profiles():
        try:
            out.append(load_profile(n))
        except Exception as e:
            raise RenderError(2, '书册配置读不出：%s（%s）' % (n, e))
    for p in extra or []:
        try:
            out.append(load_profile(str(xp(p))))
        except Exception as e:
            raise RenderError(2, '--guard-profile 读不出：%s（%s）' % (p, e))
    return out


def locate_book(path, profiles):
    """按 inode 判断 path 属于哪本书（工作区、审阅入口、审阅历史）；冻结册另按目录名模式判断。找不到返回 None。"""
    ch = _chain(path)
    best = None
    for P in profiles:
        paths = P.get('paths') or {}
        if not paths.get('root'):
            continue
        for k in DIR_KEYS:
            if paths.get(k):
                loc = _Loc(resolve(P, paths[k]))
                if _within(ch, loc) is not None and (best is None or len(loc.path) > best[0]):
                    best = (len(loc.path), P)
    if best:
        return best[1]
    comps = _components(path)
    for P in profiles:
        if P.get('frozen') and _glob_hit(comps, frozen_globs(P)):
            return P
    return None


def pick_renderer(pattern):
    """按 glob 找 render_docx.py，优先取纯数字版本号最大的一份；版本号取 glob 里 * 对应的那一级目录名。"""
    pat = str(xp(pattern))
    hits = sorted(h for h in glob.glob(pat) if os.path.isfile(h))
    if not hits:
        raise RenderError(2, '渲染环境缺失：找不到 render_docx.py（glob：%s）。宿主可能正在更新 documents 插件，'
                             '请确认 ~/.codex/plugins/cache/openai-primary-runtime/documents/ 下有版本目录' % pat)
    parts = Path(pat).parts
    star = next((i for i, x in enumerate(parts) if '*' in x), None)
    cands = []
    for h in hits:
        hp = Path(h).parts
        if star is not None and len(hp) > star:
            v = hp[star]
        else:
            v = next((x for x in reversed(hp) if re.fullmatch(r'\d+(\.\d+)+', x)), Path(h).parent.name)
        cands.append((version_key(v), v, h))
    cands.sort(key=lambda c: c[0])
    _, ver, path = cands[-1]
    warn = []
    odd = [c[1] for c in cands if c[0][0] == 0]
    if odd:
        warn.append('渲染器候选里有非纯数字的版本目录：%s（按规则优先取纯数字版本号最大的一份）' % '、'.join(odd))
    if version_key(ver)[0] == 0:
        warn.append('所选渲染器版本 %s 不是纯数字版本号，请核对' % ver)
    return {'renderer_path': path, 'renderer_version': ver, 'renderer_sha256': sha256_file(path),
            'renderer_candidates': [c[2] for c in cands], 'renderer_warnings': warn}


def _bundle_fingerprint(contents):
    acc = []
    for sub in ('MacOS', 'Frameworks', 'Resources', 'PlugIns', 'Library'):
        for r, ds, fs in os.walk(str(contents / sub)):
            ds.sort()
            for f in sorted(fs):
                p = os.path.join(r, f)
                try:
                    st = os.lstat(p)
                except OSError:
                    continue
                acc.append('%s|%d|%d' % (os.path.relpath(p, str(contents)), st.st_size, int(st.st_mtime)))
    return sha256_text('\n'.join(acc)), len(acc)


def soffice_info(soffice):
    """soffice 身份：Info.plist 版本、versionrc 构建号、运行时 manifest、可执行文件 SHA、程序包文件指纹（路径|大小|mtime）。"""
    s = xp(soffice)
    if not s.is_file():
        raise RenderError(2, '渲染环境缺失：soffice 不存在：%s' % s)
    contents = s.parent.parent
    info = OrderedDict([('soffice_path', str(s)), ('soffice_version', None), ('soffice_short_version', None),
                        ('soffice_build_id', None), ('runtime_manifest', None), ('runtime_manifest_path', None),
                        ('runtime_manifest_sha256', None)])
    plist = contents / 'Info.plist'
    if plist.exists():
        try:
            with open(str(plist), 'rb') as f:
                pl = plistlib.load(f)
            info['soffice_version'] = pl.get('CFBundleVersion')
            info['soffice_short_version'] = pl.get('CFBundleShortVersionString')
        except Exception:
            pass
    vrc = contents / 'Resources' / 'versionrc'
    if vrc.exists():
        m = re.search(r'^buildid=(\S+)', vrc.read_text(encoding='utf-8', errors='replace'), re.M)
        info['soffice_build_id'] = m.group(1) if m else None
    for up in list(s.parents)[:6]:
        mf = up / 'manifest.json'
        if mf.is_file():
            info['runtime_manifest_path'] = str(mf)
            info['runtime_manifest_sha256'] = sha256_file(mf)
            try:
                d = json.loads(mf.read_text(encoding='utf-8'))
            except Exception:
                d = None
            if isinstance(d, dict):
                info['runtime_manifest'] = OrderedDict((k, d.get(k)) for k in ('name', 'version', 'sourceRef', 'patchSha256', 'targetArch'))
            break
    info['soffice_bin_sha256'] = sha256_file(s)
    info['lo_bundle_fingerprint'], info['lo_bundle_files'] = _bundle_fingerprint(contents)
    if not info['soffice_version']:
        info['soffice_version'] = 'unknown-sha256:' + info['soffice_bin_sha256'][:16]
    bundled = contents / 'Resources' / 'fonts'
    info['lo_bundled_fonts'] = str(bundled) if bundled.exists() else None
    return info


def render_cfg(prof):
    r = dict(prof.get('render') or {})
    if r.get('engine', 'libreoffice_bundled') != 'libreoffice_bundled':
        raise RenderError(2, '不支持的渲染引擎：%s（本工具只支持 libreoffice_bundled）' % r.get('engine'))
    for k in ('soffice', 'renderer_glob', 'path_prepend'):
        if not r.get(k):
            raise RenderError(2, '书册配置缺 render.%s' % k)
    if not r.get('python'):
        # 运行时 Python 与 path_prepend 同在 dependencies 下
        guess = xp(r['path_prepend']).parent.parent / 'python' / 'bin' / 'python3'
        r['python'] = str(guess) if guess.exists() else DEFAULTS['python']
        r['_python_defaulted'] = True
    ident = r.get('identity_file', '同版身份.json')
    if '/' in ident or ident.startswith('.') or not ident.endswith('.json'):
        raise RenderError(2, 'render.identity_file 只能是 .json 纯文件名：%r' % ident)
    return r


def check_python(py):
    """渲染前先核运行时 Python：存在、3.10+、能 import pdf2image；不合用报退出码 2（在复制 DOCX 之前）。"""
    p = xp(py)
    if not p.exists():
        raise RenderError(2, '渲染环境缺失：运行时 Python 不存在：%s（render_docx.py 需要 3.10+ 与 pdf2image；可在 render.python 指定）' % p)
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP')}
    code = 'import sys\nprint("%d.%d.%d" % sys.version_info[:3], flush=True)\nimport pdf2image\n'
    try:
        r = subprocess.run([str(p), '-B', '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RenderError(2, '渲染环境缺失：运行时 Python 无法执行：%s（%s）' % (p, e))
    ver = r.stdout.decode('utf-8', 'replace').strip().split('\n')[0] if r.stdout else ''
    vt = tuple(int(x) for x in ver.split('.')) if re.fullmatch(r'\d+\.\d+\.\d+', ver) else None
    if vt is None:
        raise RenderError(2, '渲染环境缺失：运行时 Python 读不出版本：%s（%s）' % (p, clip(r.stderr.decode('utf-8', 'replace').strip(), 300)))
    if vt < (3, 10):
        raise RenderError(2, '渲染环境缺失：运行时 Python 版本 %s 低于 3.10（render_docx.py 的类型注解需要 3.10+）：%s' % (ver, p))
    if r.returncode != 0:
        raise RenderError(2, '渲染环境缺失：运行时 Python %s 不能 import pdf2image：%s（%s）' % (
            ver, p, clip(r.stderr.decode('utf-8', 'replace').strip().split('\n')[-1], 200)))
    return ver


# ---------------------------------------------------------------- 字体名表（TTF/OTF/TTC）
def _sfnt_names(read):
    """read(offset, n) → bytes。返回 [(face_index, {nameID: [str]})]，只取 1/4/6/16。"""
    out = []
    head = read(0, 12)
    if len(head) < 12:
        return out
    offs = [0]
    if head[:4] == b'ttcf':
        n = struct.unpack('>I', head[8:12])[0]
        if n > 512:
            return out
        offs = list(struct.unpack('>%dI' % n, read(12, 4 * n)))
    for idx, o in enumerate(offs):
        h = read(o, 12)
        if len(h) < 12:
            continue
        nt = struct.unpack('>H', h[4:6])[0]
        if nt > 200:
            continue
        recs = read(o + 12, 16 * nt)
        loc = None
        for k in range(nt):
            rec = recs[16 * k:16 * k + 16]
            if len(rec) < 16:
                break
            tag, _, off, ln = struct.unpack('>4sIII', rec)
            if tag == b'name':
                loc = (off, ln)
        if not loc:
            continue
        data = read(loc[0], loc[1])
        if len(data) < 6:
            continue
        _, cnt, so = struct.unpack('>HHH', data[:6])
        names = {}
        for k in range(cnt):
            r = data[6 + 12 * k:18 + 12 * k]
            if len(r) < 12:
                break
            pid, eid, lid, nid, ln, off = struct.unpack('>6H', r)
            if nid not in (1, 4, 6, 16):
                continue
            raw = data[so + off:so + off + ln]
            try:
                if pid in (0, 3):
                    s = raw.decode('utf-16-be')
                elif pid == 1 and eid == 0 and lid == 0:
                    s = raw.decode('mac_roman')
                else:
                    continue
            except Exception:
                continue
            s = s.strip('\x00').strip()
            if s:
                names.setdefault(nid, set()).add(s)
        out.append((idx, {k: sorted(v) for k, v in names.items()}))
    return out


def font_file_names(path):
    try:
        with open(path, 'rb') as f:
            def read(o, n):
                f.seek(o)
                return f.read(n)
            return _sfnt_names(read)
    except Exception:
        return []


def font_files(dirs):
    files = []
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for root, _, fns in os.walk(d):
            for fn in fns:
                if fn.lower().endswith(FONT_EXT):
                    files.append(os.path.join(root, fn))
    return sorted(set(files))


def font_fingerprint(files):
    acc = []
    for p in files:
        try:
            st = os.stat(p)
            acc.append('%s|%d|%d' % (p, st.st_size, int(st.st_mtime)))
        except OSError:
            pass
    return sha256_text('\n'.join(acc)), len(acc)


def build_font_index(files, docx_fonts=None):
    """PostScript 名 → {families, fulls, files}。DOCX 内嵌字体一并收进来。"""
    idx = {}

    def add(ps, fams, fulls, src):
        e = idx.setdefault(ps, {'families': set(), 'fulls': set(), 'files': set()})
        e['families'].update(fams)
        e['fulls'].update(fulls)
        e['files'].add(src)

    for p in files:
        if not p.lower().endswith(('.ttf', '.otf', '.ttc', '.otc')):
            continue
        for face, nm in font_file_names(p):
            for ps in nm.get(6, []):
                add(ps, set(nm.get(1, [])) | set(nm.get(16, [])), set(nm.get(4, [])), '%s#%d' % (p, face))
    for item in docx_fonts or []:
        for ps in item['ps_names']:
            add(ps, set(item['families']) | {item['declared']}, set(), 'docx:' + item['part'])
    return idx


# ---------------------------------------------------------------- DOCX 请求字体与内嵌字体
def docx_font_decls(docx):
    """DOCX 各部件里 rFonts（ascii/hAnsi/eastAsia/cs）、w:sym、主题实际请求过的字体；fontTable 单列，不算“请求”。
    内嵌字体按 ECMA-376 17.8.1 反混淆后读名表。"""
    z = zipfile.ZipFile(docx)
    names = z.namelist()
    attr_counts, elem_counts = Counter(), Counter()
    for n in names:
        if not (n.startswith('word/') and n.endswith('.xml')):
            continue
        s = z.read(n).decode('utf-8', 'replace')
        for m in re.finditer(r'<w:rFonts\b([^>]*)>', s):
            vals = re.findall(r'w:(?:ascii|hAnsi|eastAsia|cs)="([^"]+)"', m.group(1))
            attr_counts.update(vals)
            elem_counts.update(set(vals))
        for v in re.findall(r'<w:sym\b[^>]*w:font="([^"]+)"', s):
            attr_counts[v] += 1
            elem_counts[v] += 1
        if 'theme' in n:
            # 主题只取 latin/ea/cs 与简繁中文脚本字体；其余语种脚本的字体方案不算本书请求
            for v in re.findall(r'<a:(?:latin|ea|cs) typeface="([^"]+)"', s) + re.findall(r'<a:font script="Han[st]" typeface="([^"]+)"', s):
                if not v.startswith('+'):
                    attr_counts[v] += 1
                    elem_counts[v] += 1
    table, embedded = [], []
    if 'word/fontTable.xml' in names:
        ft = z.read('word/fontTable.xml').decode('utf-8', 'replace')
        rels = {}
        if 'word/_rels/fontTable.xml.rels' in names:
            rx = z.read('word/_rels/fontTable.xml.rels').decode('utf-8', 'replace')
            for rid, tgt in re.findall(r'Id="([^"]+)"[^>]*Target="([^"]+)"', rx):
                rels[rid] = tgt
            for tgt, rid in re.findall(r'Target="([^"]+)"[^>]*Id="([^"]+)"', rx):
                rels.setdefault(rid, tgt)
        for m in re.finditer(r'<w:font w:name="([^"]+)"(.*?)</w:font>', ft, re.S):
            name, body = m.group(1), m.group(2)
            table.append(name)
            for alt in re.findall(r'<w:altName w:val="([^"]+)"', body):
                table.append(alt)
            for kind, rid, key in re.findall(r'<w:embed(\w+) r:id="([^"]+)" w:fontKey="\{([^}]+)\}"', body):
                part = 'word/' + rels.get(rid, '').lstrip('/')
                if part not in names:
                    continue
                data = bytearray(z.read(part))
                kb = bytes.fromhex(key.replace('-', ''))[::-1]
                for i in range(min(32, len(data))):
                    data[i] ^= kb[i % 16]
                buf = bytes(data)
                faces = _sfnt_names(lambda o, n, b=buf: b[o:o + n])
                embedded.append({'declared': name, 'kind': kind, 'part': part,
                                 'ps_names': sorted({ps for _, nm in faces for ps in nm.get(6, [])}),
                                 'families': sorted({f for _, nm in faces for f in nm.get(1, []) + nm.get(16, [])})})
    return {'rfonts_attr_counts': dict(attr_counts.most_common()), 'rfonts_element_counts': dict(elem_counts.most_common()),
            'requested': sorted(elem_counts), 'font_table': table, 'embedded': embedded}


def rfonts_placement(docx, fonts):
    """正文 document.xml 里这些字体的 rFonts 元素落在哪：run 上且东亚属性是它、run 上只作西文属性、段落标记（pPr/rPr）、其他。"""
    from lxml import etree
    want = set(fonts)
    out = {f: OrderedDict([('run_eastAsia', 0), ('run_latin_only', 0), ('paragraph_mark', 0), ('other', 0)]) for f in want}
    if not want:
        return out
    doc = etree.fromstring(zipfile.ZipFile(docx).read('word/document.xml'))
    for rf in doc.iter(W + 'rFonts'):
        vals = {rf.get(W + a) for a in ('ascii', 'hAnsi', 'eastAsia', 'cs')} & want
        if not vals:
            continue
        rpr = rf.getparent()
        par = rpr.getparent() if rpr is not None else None
        for f in vals:
            if par is not None and par.tag == W + 'pPr':
                out[f]['paragraph_mark'] += 1
            elif par is not None and par.tag == W + 'r':
                out[f]['run_eastAsia' if rf.get(W + 'eastAsia') == f else 'run_latin_only'] += 1
            else:
                out[f]['other'] += 1
    return out


def _on(el):
    return el is not None and el.get(W + 'val') not in ('0', 'false', 'off')


def _rpr_ea(rpr):
    if rpr is None:
        return None
    rf = rpr.find(W + 'rFonts')
    if rf is None:
        return None
    t = rf.get(W + 'eastAsiaTheme')
    if t:
        return ('theme', t)
    v = rf.get(W + 'eastAsia')
    return ('font', v) if v else None


def docx_ea_segments(docx):
    """按段落把相邻、请求同一东亚字体的可见 run 合并成片段 [(请求字体或 None, 原文, 是否在表格里)]。
    解析顺序：直接格式 → 字符样式链 → 段落样式链（无 pStyle 用默认段落样式）→ 文档默认 → 主题；表格样式、编号样式不计。"""
    from lxml import etree
    z = zipfile.ZipFile(docx)
    names = set(z.namelist())
    styles, default_para, doc_default = {}, None, None
    if 'word/styles.xml' in names:
        st = etree.fromstring(z.read('word/styles.xml'))
        dd = st.find(W + 'docDefaults/' + W + 'rPrDefault/' + W + 'rPr')
        doc_default = _rpr_ea(dd)
        for s in st.findall(W + 'style'):
            b = s.find(W + 'basedOn')
            styles[s.get(W + 'styleId')] = (b.get(W + 'val') if b is not None else None, _rpr_ea(s.find(W + 'rPr')))
            if s.get(W + 'type') == 'paragraph' and s.get(W + 'default') in ('1', 'true', 'on'):
                default_para = s.get(W + 'styleId')
    theme = {}
    th = sorted(n for n in names if re.fullmatch(r'word/theme/theme\d*\.xml', n))
    if th:
        tr = etree.fromstring(z.read(th[0]))
        for kind in ('major', 'minor'):
            f = tr.find('.//' + A + kind + 'Font')
            if f is None:
                continue
            ea = f.find(A + 'ea')
            v = ea.get('typeface') if ea is not None else ''
            if not v:
                hans = [x.get('typeface') for x in f.findall(A + 'font') if x.get('script') == 'Hans']
                v = hans[0] if hans else ''
            theme[kind + 'EastAsia'] = v or None

    def chain(sid):
        seen = set()
        while sid and sid not in seen and sid in styles:
            seen.add(sid)
            based, ea = styles[sid]
            if ea:
                return ea
            sid = based
        return None

    def name_of(ea):
        if ea is None:
            return None
        return theme.get(ea[1]) if ea[0] == 'theme' else ea[1]

    doc = etree.fromstring(z.read('word/document.xml'))
    body = doc.find(W + 'body')
    segs = []
    if body is None:
        return segs
    for p in body.iter(W + 'p'):
        ppr = p.find(W + 'pPr')
        ps = ppr.find(W + 'pStyle') if ppr is not None else None
        p_ea = chain(ps.get(W + 'val') if ps is not None else default_para)
        in_tbl = next(p.iterancestors(W + 'tc'), None) is not None
        cur, buf = object(), []
        for r in p.iter(W + 'r'):
            anc = r.getparent()
            while anc is not None and anc.tag != W + 'p':
                anc = anc.getparent()
            if anc is not p:
                continue  # 文本框里的嵌套段落另算
            rpr = r.find(W + 'rPr')
            if rpr is not None and _on(rpr.find(W + 'vanish')):
                continue
            txt = ''.join(t.text or '' for t in r.findall(W + 't'))
            if not txt:
                continue
            ea = _rpr_ea(rpr)
            if ea is None and rpr is not None and rpr.find(W + 'rStyle') is not None:
                ea = chain(rpr.find(W + 'rStyle').get(W + 'val'))
            fam = name_of(ea or p_ea or doc_default)
            if fam != cur and buf:
                segs.append((cur, ''.join(buf), in_tbl))
                buf = []
            cur = fam
            buf.append(txt)
        if buf:
            segs.append((cur, ''.join(buf), in_tbl))
    return segs


# ---------------------------------------------------------------- 私有 fontconfig
def _canon(el):
    from lxml import etree
    e = copy.deepcopy(el)
    e.tail = None
    for x in e.iter():
        if not isinstance(x.tag, str):
            continue
        x.text = x.text.strip() if x.text and x.text.strip() else None
        if x is not e:
            x.tail = x.tail.strip() if x.tail and x.tail.strip() else None
    return etree.tostring(e, method='c14n').decode('utf-8')


def fc_signature(text, label):
    """规范化语义签名：去掉注释、PI、cachedir；<dir> 按顺序记绝对路径，其余元素按顺序记 C14N。
    含 <include>、带 prefix 或非绝对路径的 <dir> 一律报错（本工具不展开，也无法保证其中的 cachedir 不写进书册目录）。"""
    from lxml import etree
    parser = etree.XMLParser(remove_comments=True, remove_pis=True, resolve_entities=False, no_network=True, load_dtd=False)
    try:
        root = etree.fromstring(text.encode('utf-8'), parser)
    except etree.XMLSyntaxError as e:
        raise RenderError(2, 'fontconfig 不是合法 XML：%s（%s）' % (label, e))
    if root.tag != 'fontconfig':
        raise RenderError(2, 'fontconfig 根元素不是 <fontconfig>：%s' % label)
    bad, dirs, others, aliases = [], [], [], OrderedDict()
    for el in root.iter():
        if isinstance(el.tag, str) and el.tag == 'include':
            bad.append('<include>%s</include>' % (el.text or '').strip())
        if isinstance(el.tag, str) and el.tag == 'dir' and el.getparent() is not root:
            bad.append('嵌套的 <dir>')
    for el in root:
        if not isinstance(el.tag, str) or el.tag == 'cachedir':
            continue
        if el.tag == 'dir':
            txt = (el.text or '').strip()
            if el.get('prefix') or not txt.startswith('/'):
                bad.append('<dir%s>%s</dir>' % (' prefix="%s"' % el.get('prefix') if el.get('prefix') else '', txt))
            dirs.append([os.path.normpath(txt), sorted((k, v) for k, v in el.attrib.items())])
            continue
        if el.tag == 'alias':
            fam = (el.findtext('family') or '').strip()
            for f in el.findall('prefer/family'):
                if f.text and f.text.strip():
                    aliases.setdefault(fam, []).append(f.text.strip())
        others.append(_canon(el))
    if bad:
        raise RenderError(2, 'fontconfig 含本工具不支持的写法：%s（%s）。请改成绝对路径 <dir>、去掉 <include> 后再用'
                             '（render_docx 会把 HOME 改到一次性目录，~ 与相对路径不指向本机字体）' % ('；'.join(bad), label))
    sig = {'dirs': dirs, 'others': others}
    return sig, sha256_json(sig), aliases


def _families_in_dir(d):
    fams = set()
    for p in font_files([d]):
        for _, nm in font_file_names(p):
            for f in nm.get(1, []) + nm.get(16, []):
                fams.add(norm_family(f))
    return fams


def typography_families(prof):
    fams = []
    for v in (prof.get('typography') or {}).values():
        if isinstance(v, dict):
            for k in ('ea', 'ascii', 'hAnsi', 'cs', 'family'):
                if isinstance(v.get(k), str) and v[k] not in fams:
                    fams.append(v[k])
    return fams


def _alias_target(v):
    return v['family'] if isinstance(v, dict) else v


def house_fontconfig(prof, fcfg, cachedir):
    """house 模板：dirs_extra 在前，再是系统标准目录，最后补上提供书册字体（typography 与 aliases 目标）的系统字体资产目录。"""
    std = [str(xp(d)) for d in (fcfg.get('house_dirs') or DEFAULTS['house_dirs'])]
    extra = [str(xp(d)) for d in (fcfg.get('dirs_extra') or [])]
    aliases = fcfg.get('aliases') or {}
    need = typography_families(prof) + [_alias_target(v) for v in aliases.values()]
    have = set()
    for d in extra + std:
        if os.path.isdir(d):
            have |= _families_in_dir(d)
    missing = [f for f in dict.fromkeys(need) if norm_family(f) not in have]
    assets, found = [], set()
    if missing:
        for g in fcfg.get('asset_globs') or DEFAULTS['asset_globs']:
            for d in sorted(glob.glob(g)):
                fams = _families_in_dir(d)
                hit = [f for f in missing if norm_family(f) in fams]
                if hit and d not in assets:
                    assets.append(d)
                    found.update(hit)
    dirs = list(dict.fromkeys(extra + std + assets))
    lines = ['<?xml version="1.0"?>', '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">', '<fontconfig>',
             '  <!-- render_book.py 按书册配置生成（template=house）；字体目录只读引用 -->']
    lines += ['  <dir>%s</dir>' % d for d in dirs]
    lines.append('  <cachedir>%s</cachedir>' % cachedir)
    for k, v in aliases.items():
        binding = v.get('binding') if isinstance(v, dict) else (None if k in GENERIC_FAMILIES else 'strong')
        b = ' binding="%s"' % binding if binding else ''
        lines.append('  <alias%s><family>%s</family><prefer><family>%s</family></prefer></alias>' % (b, k, _alias_target(v)))
    lines += ['  <config></config>', '</fontconfig>', '']
    return '\n'.join(lines), {'dirs': dirs, 'asset_dirs_added': assets,
                              'families_not_found': [f for f in missing if f not in found]}


def make_fontconfig(prof, rc, cache_dir, mode='auto', explicit=None, write=True):
    """生成私有 fontconfig 文本并算身份；write=False 时只在内存里算，不写盘（--key-only）。"""
    fcfg = rc.get('fontconfig') or {}
    fc_dir = Path(cache_dir) / 'fontconfig'
    fc_cache = fc_dir / 'fc-cache'
    info = OrderedDict([('fontconfig_mode', None), ('fontconfig_source', None), ('fontconfig_source_sha256', None),
                        ('fontconfig_cachedir', str(fc_cache))])
    hist = resolve(prof, fcfg.get('historical_file')) if fcfg.get('historical_file') else None
    hist_ok = hist is not None and hist.is_file()
    prefix = fcfg.get('historical_sha256_prefix')
    hist_sha = sha256_file(hist) if hist_ok else None
    hist_text = hist.read_text(encoding='utf-8') if hist_ok else None
    if explicit:
        src = xp(explicit)
        if not src.is_file():
            raise RenderError(2, '指定的 fontconfig 不存在：%s' % src)
        mode_used, text_src = 'explicit', src.read_text(encoding='utf-8')
        info.update(fontconfig_source=str(src), fontconfig_source_sha256=sha256_file(src))
    elif mode in ('auto', 'historical') and hist_ok:
        if prefix and not hist_sha.startswith(prefix):
            raise RenderError(2, '历史 fontconfig 已变：%s 的 SHA256 为 %s，配置记录前缀 %s。请核对后改用 '
                                 '--fontconfig-mode template 或更新书册配置' % (hist, hist_sha[:16], prefix))
        mode_used, text_src = 'historical', hist_text
        info.update(fontconfig_source=str(hist), fontconfig_source_sha256=hist_sha)
    elif mode == 'historical':
        raise RenderError(2, '书册配置没有可用的 historical_file：%s' % hist)
    else:
        mode_used = 'template'
        if fcfg.get('template', 'house') != 'house':
            raise RenderError(2, '未知的 fontconfig 模板：%s' % fcfg.get('template'))
        text_src = None
    detail = None
    if text_src is not None:
        fc_signature(text_src, info['fontconfig_source'])  # 先核源文件写法
        body = re.sub(r'\s*<cachedir\b[^>]*>.*?</cachedir>', '', text_src, flags=re.S)
        body = re.sub(r'\s*<cachedir\b[^>]*/>', '', body)
        if '</fontconfig>' not in body:
            raise RenderError(2, 'fontconfig 源文件缺 </fontconfig>：%s' % info['fontconfig_source'])
        # 注释里不放路径：XML 注释不能含 “--”，而 scratch 路径常含
        note = '  <!-- render_book.py 派生（源文件 sha256 %s，路径见同版身份），只把 cachedir 改到私有缓存 -->\n  <cachedir>%s</cachedir>\n' % (
            (info['fontconfig_source_sha256'] or '')[:16], fc_cache)
        text = body.replace('</fontconfig>', note + '</fontconfig>', 1)
    else:
        text, detail = house_fontconfig(prof, fcfg, fc_cache)
    sig, sem_sha, aliases = fc_signature(text, '派生 fontconfig')
    equiv = None
    if hist_ok:
        info['fontconfig_historical'] = str(hist)
        info['fontconfig_historical_sha256'] = hist_sha
        try:
            equiv = fc_signature(hist_text, str(hist))[0] == sig
        except RenderError as e:
            info['fontconfig_historical_problem'] = str(e)
    out = fc_dir / ('%s_%s.conf' % (prof.get('book_id', 'book'), mode_used))
    if write:
        fc_cache.mkdir(parents=True, exist_ok=True)
        if not out.exists() or out.read_text(encoding='utf-8') != text:
            tmp = out.with_suffix('.tmp')
            tmp.write_text(text, encoding='utf-8')
            os.replace(str(tmp), str(out))
    info.update(OrderedDict([
        ('fontconfig_mode', mode_used), ('fontconfig_path', str(out)), ('fontconfig_written', bool(write)),
        ('fontconfig_sha256', hist_sha if equiv else sem_sha),
        ('fontconfig_sha256_basis', 'historical_equivalent' if equiv else 'semantic'),
        ('fontconfig_semantic_sha256', sem_sha), ('fontconfig_file_sha256', sha256_text(text)),
        ('fontconfig_equivalent_to_historical', equiv),
        ('fontconfig_dirs', [d[0] for d in sig['dirs']]),
        ('fontconfig_missing_dirs', [d[0] for d in sig['dirs'] if not os.path.isdir(d[0])]),
        ('fontconfig_aliases', aliases), ('template_detail', detail)]))
    return info


# ---------------------------------------------------------------- 渲染（驱动 render_docx.py，只出 PDF）
DRIVER = r'''
import sys, json, inspect, importlib.util, traceback
sys.dont_write_bytecode = True
a = json.loads(sys.argv[1])
res = {"ok": False, "commands": [], "first_proc": None}

class Blocked(Exception):
    pass

def run():
    spec = importlib.util.spec_from_file_location("render_docx_rb", a["renderer"])
    rd = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(rd)
    except Exception as e:
        res["error"] = "env"
        res["message"] = "渲染环境缺失：render_docx.py 导入失败（%s: %s）。运行时 Python 需 3.10+ 且装有 pdf2image" % (type(e).__name__, e)
        return
    miss = [n for n in ("make_renderable_docx_copy", "convert_to_pdf", "_run_cmd") if not hasattr(rd, n)]
    params = list(inspect.signature(rd.convert_to_pdf).parameters) if hasattr(rd, "convert_to_pdf") else []
    if miss or params[:5] != ["doc_path", "user_profile", "convert_tmp_dir", "stem", "verbose"]:
        res["error"] = "interface"
        res["message"] = "render_docx.py 接口与本工具不符：缺 %s；convert_to_pdf 参数 %s" % (miss, params)
        return
    orig_resolve = getattr(rd, "_resolve_soffice", None)
    if orig_resolve is not None:
        def _resolve():
            res["renderer_resolved_soffice"] = orig_resolve()  # 保留渲染器自己的 PATH 处理
            return a["soffice"]
        rd._resolve_soffice = _resolve
    orig_run = rd._run_cmd
    def _run(cmd, env, verbose):
        if res["commands"] and not a["allow_fallback"]:
            res["blocked_command"] = [str(x) for x in cmd]
            raise Blocked()
        res["commands"].append([str(x) for x in cmd])
        p = orig_run(cmd, env=env, verbose=verbose)
        if res["first_proc"] is None:
            res["first_proc"] = {"returncode": p.returncode, "stdout": (p.stdout or "")[-4000:], "stderr": (p.stderr or "")[-4000:]}
        return p
    rd._run_cmd = _run
    if hasattr(rd, "_default_macos_tmpdir_for_soffice"):
        rd._default_macos_tmpdir_for_soffice()
    src, tmp = rd.make_renderable_docx_copy(a["docx"], verbose=False)
    res["ooxml_repaired"] = src != a["docx"]
    try:
        pdf, log = rd.convert_to_pdf(src, a["user_profile"], a["convert_dir"], a["stem"], False)
    finally:
        if tmp is not None:
            tmp.cleanup()
    res.update(ok=bool(pdf), pdf=pdf, log=(log or "")[-8000:])

try:
    run()
except Blocked:
    res["error"] = "blocked_fallback"
    res["message"] = "DOCX→PDF 直转没有产出 PDF；render_docx 想改走 DOCX→ODT→PDF 回退，已按规则拦下，未重跑"
except BaseException:
    res["error"] = "exception"
    res["message"] = "渲染驱动异常：" + traceback.format_exc()[-4000:]
finally:
    with open(a["result_file"], "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False)
'''


def _clean_env(rc, fc_path):
    env = os.environ.copy()
    for k in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONSTARTUP'):
        env.pop(k, None)
    env['PATH'] = str(xp(rc['path_prepend'])) + os.pathsep + env.get('PATH', '')
    env['FONTCONFIG_FILE'] = str(fc_path)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['TMPDIR'] = '/private/tmp' if os.path.isdir('/private/tmp') else env.get('TMPDIR', '/tmp')
    return env


def _run_group(cmd, env, timeout):
    """在独立进程组里跑；超时就整组杀掉（含 soffice.bin），不重跑。"""
    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.communicate()
        raise RenderError(3, '渲染超时（%d 秒），已终止 LibreOffice 进程组，未重跑。可加大 --timeout，或检查是否有残留的'
                             ' soffice 进程占用' % timeout)
    return p.returncode, out.decode('utf-8', 'replace'), err.decode('utf-8', 'replace')


def convert(mode, rc, env_info, fc_path, docx_copy, work, lo_profile, timeout, allow_fallback):
    convert_dir = work / 'convert'
    convert_dir.mkdir(parents=True, exist_ok=True)
    env = _clean_env(rc, fc_path)
    stem = docx_copy.stem
    t0 = time.perf_counter()
    if mode == 'render_docx':
        rf = work / 'driver_result.json'
        args = {'renderer': env_info['renderer_path'], 'soffice': env_info['soffice_path'], 'docx': str(docx_copy),
                'user_profile': str(lo_profile), 'convert_dir': str(convert_dir), 'stem': stem,
                'allow_fallback': bool(allow_fallback), 'result_file': str(rf)}
        code, out, err = _run_group([str(xp(rc['python'])), '-B', '-c', DRIVER, json.dumps(args, ensure_ascii=False)], env, timeout)
        if not rf.exists():
            raise RenderError(3, '渲染驱动异常退出（返回码 %s），没有结果文件' % code, {'stderr': err[-4000:], 'stdout': out[-2000:]})
        res = json.loads(rf.read_text(encoding='utf-8'))
        if res.get('error') == 'env':
            raise RenderError(2, res['message'])
        if res.get('error') == 'interface':
            raise RenderError(3, res['message'])
        if not res.get('ok'):
            raise RenderError(3, res.get('message') or 'LibreOffice 没有产出 PDF', {
                'first_proc': res.get('first_proc'), 'commands': res.get('commands'),
                'blocked_command': res.get('blocked_command'), 'log': res.get('log')})
        pdf = Path(res['pdf'])
        detail = {'commands': res.get('commands'), 'renderer_resolved_soffice': res.get('renderer_resolved_soffice'),
                  'ooxml_repaired': res.get('ooxml_repaired'), 'odt_fallback_used': len(res.get('commands') or []) > 1}
    else:
        cmd = [env_info['soffice_path'], '-env:UserInstallation=' + Path(lo_profile).resolve().as_uri(), '--headless',
               '--convert-to', 'pdf', '--outdir', str(convert_dir), str(docx_copy)]
        code, out, err = _run_group(cmd, env, timeout)
        pdf = convert_dir / (stem + '.pdf')
        if not pdf.exists() or pdf.stat().st_size == 0:
            raise RenderError(3, 'soffice 直接转换没有产出 PDF（返回码 %s）' % code, {'stdout': out[-4000:], 'stderr': err[-4000:]})
        detail = {'commands': [cmd], 'odt_fallback_used': False}
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RenderError(3, 'PDF 为空或不存在：%s' % pdf)
    detail['seconds'] = round(time.perf_counter() - t0, 2)
    return pdf, detail


# ---------------------------------------------------------------- PDF 扫描、字体审计、对照
def _visual_rows(block):
    """同一 block 里基线重合的 line 合成一行、行内按 x 排序（LibreOffice 把回退字形另起 line 输出，内容流顺序会打乱）。"""
    rows = []
    for ln in block.get('lines', []):
        spans = list(ln.get('spans', []))
        if tuple(ln.get('dir', (1.0, 0.0))) != (1.0, 0.0):
            rows.append([None, 0, spans])  # 非横排保持原序
            continue
        y0, y1 = ln['bbox'][1], ln['bbox'][3]
        yc, h = (y0 + y1) / 2, max(y1 - y0, 0.1)
        for r in rows:
            if r[0] is not None and abs(r[0] - yc) < 0.35 * min(h, r[1]):
                r[2].extend(spans)
                break
        else:
            rows.append([yc, h, spans])
    for r in rows:
        if r[0] is not None:
            r[2].sort(key=lambda sp: sp['bbox'][0])
    return [r[2] for r in rows]


def scan_pdf(pdf, lite=False):
    """逐页：按 span 字体计字数与汉字数，拼出页文本（视觉行内 span 相连、行间换行）；另建全书去空白字符串与 span 字体索引。
    lite=True 只取对照要用的页文本与每页字体用字数（对照 PDF 用）。"""
    import fitz
    doc = fitz.open(str(pdf))
    pages, xref_fonts = [], {}
    flags = fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES  # 不裁到 mediabox，与 batch_health 计汉字一致
    parts, starts, sfonts, spages, pos = [], [], [], [], 0
    for pno, pg in enumerate(doc, 1):
        for f in pg.get_fonts(full=False):
            xref_fonts[f[0]] = {'basefont': f[3], 'ext': f[1], 'type': f[2]}
        fonts, lines = {}, []
        for b in pg.get_text('dict', flags=flags).get('blocks', []):
            for spans in _visual_rows(b):
                line_text = ''.join(sp.get('text', '') for sp in spans)
                for sp in spans:
                    t = sp.get('text', '')
                    vis = re.sub(r'\s', '', t)
                    if not vis:
                        continue
                    name = re.sub(r'^[A-Z]{6}\+', '', sp.get('font', ''))
                    e = fonts.setdefault(name, {'chars': 0, 'cjk': 0, 'set': Counter(), 'samples': [], 'cjk_samples': []})
                    if lite:
                        e['chars'] += len(vis)
                        continue
                    nc = len(CJK.findall(vis))
                    e['chars'] += len(vis)
                    e['cjk'] += nc
                    e['set'].update(vis)
                    smp = {'span': clip(t.strip(), 30), 'line': clip(line_text.strip(), 60)}
                    if len(e['samples']) < 2:
                        e['samples'].append(smp)
                    if nc and len(e['cjk_samples']) < 2:
                        e['cjk_samples'].append(smp)
                    starts.append(pos)
                    sfonts.append(name)
                    spages.append(pno)
                    parts.append(vis)
                    pos += len(vis)
                lines.append(line_text)
        pages.append({'text': '\n'.join(lines), 'fonts': fonts})
    meta = dict(doc.metadata or {})
    n = doc.page_count
    doc.close()
    return {'pages': pages, 'page_count': n, 'xref_fonts': xref_fonts, 'metadata': meta,
            'flat': {'text': ''.join(parts), 'starts': starts, 'fonts': sfonts, 'pages': spages}}


def _font_class(*names):
    """按字体名关键词粗分 楷/黑/宋/其他（启发式，只作提示）。"""
    s = ' '.join(x for x in names if x).casefold()
    if re.search(r'楷|kai', s):
        return 'kai'
    if re.search(r'黑|hei|sans|gothic|yahei|pingfang|arial|helvetica|maru', s):
        return 'hei'
    if re.search(r'宋|song|simsun|ming|mincho|serif', s):
        return 'song'
    return 'other'


def _find_all(hay, needle, cap=60):
    out, k = [], hay.find(needle)
    while k >= 0 and len(out) < cap:
        out.append(k)
        k = hay.find(needle, k + 1)
    return out


def check_requests(segs, scan, font_index, prof_aliases, conf_aliases, fallback_fonts=()):
    """请求与实得核对。DOCX 片段与 PDF 都去空白拼成全书字符串，按位置可查“这段字 DOCX 请求什么字体、PDF 实际用什么字体”。
    正向抽样：每个请求字体均匀抽至多 N 个片段，取一段文字；DOCX 里该段文字每处出现请求都一致、PDF 出现次数不多于 DOCX 时，
    逐处看 PDF 承载其中汉字的字体。反向追查：从 PDF 里落在 fallback_fonts 的每个汉字 span 出发，取所在位置的一段文字回查
    DOCX 请求。字体相符＝属于请求字族或书册 render.fontconfig.aliases 目标字族；fontconfig 自身的别名不算书册认可。"""
    per, min_cjk, width = DEFAULTS['subst_per_family'], DEFAULTS['subst_min_cjk'], DEFAULTS['subst_width']
    flat = scan['flat']
    T, starts, sfonts, spages = flat['text'], flat['starts'], flat['fonts'], flat['pages']
    dparts, dstarts, dfams, dtbl, pos = [], [], [], [], 0
    for fam, txt, tb in segs:
        s = re.sub(r'\s', '', txt)
        if s:
            dparts.append(s)
            dstarts.append(pos)
            dfams.append(fam)
            dtbl.append(tb)
            pos += len(s)
    D = ''.join(dparts)

    def docx_req(sample):
        """DOCX 里该段文字每处出现所请求的字体集合与出现次数（跨片段且字体不同记 None）。"""
        reqs, hits = set(), _find_all(D, sample)
        for k in hits:
            i, e = bisect_right(dstarts, k) - 1, bisect_right(dstarts, k + len(sample) - 1) - 1
            fs = set(dfams[i:e + 1])
            reqs.add(fs.pop() if len(fs) == 1 else None)
        return reqs, len(hits)

    def pdf_used(k, L):
        j, used = bisect_right(starts, k) - 1, Counter()
        page = spages[max(j, 0)]
        while j < len(starts) and starts[j] < k + L:
            a0, b0 = max(k, starts[j]), min(k + L, starts[j + 1] if j + 1 < len(starts) else len(T))
            n = len(CJK.findall(T[a0:b0]))
            if n:
                used[sfonts[j]] += n
            j += 1
        return used, page

    def fams_of(ps):
        ent = font_index.get(ps)
        out = {norm_family(ps)}
        if ent:
            out |= {norm_family(f) for f in ent['families'] | ent['fulls']}
        return out

    def accepted(fam):
        acc = {norm_family(fam)}
        if fam in prof_aliases:
            acc.add(norm_family(_alias_target(prof_aliases[fam])))
        return acc

    pairs = OrderedDict()
    installed = set()
    for e in font_index.values():
        installed |= {norm_family(x) for x in e['families']}

    def record(fam, f, page, text, direction, in_tbl):
        pr = pairs.setdefault((fam, f), {'forward': 0, 'reverse': 0, 'in_table': 0, 'pages': [], 'examples': []})
        pr[direction] += 1
        pr['in_table'] += bool(in_tbl)
        pr['pages'].append(page)
        if len(pr['examples']) < 3 and all(x['page'] != page for x in pr['examples']):
            pr['examples'].append({'page': page, 'docx_text': clip(text, 40), 'direction': direction})

    # 正向抽样
    by_fam, unresolved = OrderedDict(), 0
    for fam, s, tb in zip(dfams, dparts, dtbl):
        if len(CJK.findall(s)) < min_cjk:
            continue
        if not fam:
            unresolved += 1
            continue
        by_fam.setdefault(fam, []).append((s, tb))
    coverage = OrderedDict()
    for fam, lst in by_fam.items():
        acc = accepted(fam)
        cov = OrderedDict([('segments', len(lst)), ('sampled', 0), ('located', 0), ('matched', 0), ('substituted', 0),
                           ('pdf_occurrences', 0), ('not_located', 0), ('ambiguous', 0)])
        k = min(per, len(lst))
        for i in sorted({int(j * len(lst) / k) for j in range(k)}):
            s, tb = lst[i]
            cjk_pos = [m.start() for m in CJK.finditer(s)]
            wins = []
            for off in (cjk_pos[0], max(0, len(s) // 2 - width // 2), max(0, len(s) - width)):
                w = s[off:off + width]
                if len(CJK.findall(w)) >= min_cjk and w not in wins:
                    wins.append(w)
            if not wins:
                continue
            cov['sampled'] += 1
            state = 'not_located'
            for w in wins:
                reqs, dn = docx_req(w)
                if reqs != {fam}:
                    state = 'ambiguous'
                    continue
                occ = _find_all(T, w)
                if not occ:
                    continue
                if len(occ) > dn:
                    state = 'ambiguous'
                    continue
                state = 'located'
                bad = False
                for p0 in occ:
                    cov['pdf_occurrences'] += 1
                    used, page = pdf_used(p0, len(w))
                    for f in used:
                        if not (acc & fams_of(f)):
                            bad = True
                            record(fam, f, page, s, 'forward', tb)
                cov['substituted' if bad else 'matched'] += 1
                break
            if state == 'located':
                cov['located'] += 1
            else:
                cov[state] += 1
        coverage[fam] = cov

    # 反向追查：从回退 span 出发
    rev = OrderedDict([('spans', 0), ('traced', 0), ('untraced', 0), ('request_matches_actual', 0)])
    fb = set(fallback_fonts)
    done = set()
    for j, f in enumerate(sfonts):
        if f not in fb or rev['spans'] >= 400:
            continue
        a0, b0 = starts[j], starts[j + 1] if j + 1 < len(starts) else len(T)
        if not CJK.search(T[a0:b0]):
            continue
        rev['spans'] += 1
        traced = False
        for s0 in (max(0, a0 - 4), a0, max(0, b0 - width)):
            w = T[s0:s0 + width]
            if len(CJK.findall(w)) < 4 or (w, f) in done:
                continue
            reqs, dn = docx_req(w)
            reqs.discard(None)
            if len(reqs) != 1 or not dn:
                continue
            fam = reqs.pop()
            done.add((w, f))
            traced = True
            if fam and not (accepted(fam) & fams_of(f)):
                k2 = D.find(w)
                i = bisect_right(dstarts, k2) - 1
                record(fam, f, spages[j], dparts[i], 'reverse', dtbl[i])
            else:
                rev['request_matches_actual'] += 1
            break
        rev['traced' if traced else 'untraced'] += 1

    out_pairs = []
    for (fam, f), pr in pairs.items():
        ent = font_index.get(f)
        fams = sorted(ent['families']) if ent else []
        cr = _font_class(fam, _alias_target(prof_aliases.get(fam, '')) or '')
        ca = _font_class(f, *fams)
        out_pairs.append(OrderedDict([
            ('requested', fam), ('actual', f), ('actual_families', fams[:6]),
            ('book_alias', _alias_target(prof_aliases[fam]) if fam in prof_aliases else None),
            ('requested_installed', norm_family(fam) in installed or (fam in prof_aliases and norm_family(_alias_target(prof_aliases[fam])) in installed)),
            ('fontconfig_alias', conf_aliases.get(fam)), ('forward_hits', pr['forward']), ('reverse_hits', pr['reverse']),
            ('in_table_hits', pr['in_table']),
            ('samples', pr['forward'] + pr['reverse']), ('pages', ranges(pr['pages'])),
            ('class_requested', cr), ('class_actual', ca), ('class_mismatch', cr != ca),
            ('examples', pr['examples'])]))
    out_pairs.sort(key=lambda x: (not x['class_mismatch'], -x['samples']))
    located = sum(c['located'] for c in coverage.values())
    gate = 'warn' if out_pairs else ('pass' if located or rev['traced'] else 'not_run')
    return OrderedDict([
        ('gate', gate), ('pairs', out_pairs), ('coverage', coverage), ('reverse', rev), ('unresolved_segments', unresolved),
        ('method', '正向抽样：每个请求的东亚字体均匀抽至多 %d 个片段（至少 %d 个汉字），在片段首、中、尾各取 %d 个非空白字符试查；'
                   'DOCX 里该段文字每处出现请求都一致、PDF（全书去空白拼接）出现次数不多于 DOCX 时，逐处看承载汉字的字体。'
                   '反向追查：从 PDF 里汉字落在回退字体的每个 span（至多 400 个）取所在位置一段文字回查 DOCX 请求。'
                   '相符＝属于请求字族或书册 render.fontconfig.aliases 目标。请求字体解析：直接格式→字符样式→段落样式→文档默认→主题'
                   % (per, min_cjk, width)),
        ('limits', '正向是抽样，不是全量；反向只追查回退字体；表格样式、编号样式里的字体不解析；fontconfig 自身的别名不算书册认可；'
                   'reverse.request_matches_actual 是 DOCX 本就请求了该字体的回退 span（不算替换，原因在请求本身）；'
                   'class_* 只按字体名关键词粗分（楷/黑/宋/其他），仅作提示'),
    ])


def audit_fonts(scan, prof, rc, decl, font_index, subst):
    pf = prof.get('pdf_fonts') or {}
    rx_s = pf.get('expected_cjk_regex') or DEFAULTS['cjk_regex']
    rx = re.compile(rx_s)
    th = int(pf.get('fail_min_chars_page', DEFAULTS['cjk_fail_min']))
    fa = rc.get('font_audit') or {}
    profile_fams = typography_families(prof) + list(fa.get('expected_families') or [])
    aliases = (rc.get('fontconfig') or {}).get('aliases') or {}
    requested = set(decl['requested'])
    requested |= {_alias_target(aliases[k]) for k in aliases if k in requested}
    pn = {norm_family(x) for x in profile_fams}
    dn = {norm_family(x) for x in requested}
    ignore = {norm_family(x) for x in (fa.get('ignore_fonts') or [])}
    usage = OrderedDict()
    fail_pages, warn_pages = [], []
    for i, pg in enumerate(scan['pages'], 1):
        bad = 0
        for name, e in pg['fonts'].items():
            u = usage.setdefault(name, {'chars': 0, 'cjk': 0, 'pages': [], 'cjk_pages': [], 'set': Counter(),
                                        'samples': [], 'cjk_samples': []})
            u['chars'] += e['chars']
            u['cjk'] += e['cjk']
            u['pages'].append(i)
            if e['cjk']:
                u['cjk_pages'].append(i)
            u['set'].update(e['set'])
            for key in ('samples', 'cjk_samples'):
                for smp in e[key]:
                    if len(u[key]) < 5 and all(x['line'] != smp['line'] for x in u[key]):
                        u[key].append(dict(page=i, **smp))
            if e['cjk'] and not rx.search(name):  # 门只用 pdf_fonts 两个键，与 batch_health 完全一致
                bad += e['cjk']
        if bad:
            (fail_pages if bad >= th else warn_pages).append(i)
    fonts, by_font = [], []
    for name, u in usage.items():
        ent = font_index.get(name)
        fams = sorted(ent['families']) if ent else []
        fn = {norm_family(f) for f in fams} | {norm_family(name)}
        if norm_family(name) in ignore:
            cat = 'ignored'
        elif not ent:
            cat = 'unmapped'
        elif fn & pn:
            cat = 'profile'
        elif fn & dn:
            cat = 'docx_requested'
        else:
            cat = 'other'
        cjk_ok = bool(rx.search(name))
        item = OrderedDict([('font', name), ('category', cat), ('expected_cjk', cjk_ok), ('families', fams[:6]),
                            ('chars', u['chars']), ('cjk_chars', u['cjk']), ('page_count', len(u['pages']))])
        flagged = bool(u['cjk'] and not cjk_ok)
        if cat != 'profile' or flagged:
            item['pages'] = ranges(u['pages'])
            item['distinct_chars'] = clip(''.join(c for c, _ in u['set'].most_common()), 80)
            item['samples'] = u['cjk_samples'] if flagged else u['samples']
            item['source_files'] = sorted(ent['files'])[:3] if ent else []
        fonts.append(item)
        if flagged:
            by_font.append(OrderedDict([('font', name), ('category', cat), ('cjk_chars', u['cjk']),
                                        ('cjk_page_count', len(u['cjk_pages'])), ('cjk_pages', ranges(u['cjk_pages'])),
                                        ('samples', u['cjk_samples'])]))
    order = {'unmapped': 0, 'other': 1, 'docx_requested': 2, 'ignored': 3, 'profile': 4}
    fonts.sort(key=lambda x: (not (x['cjk_chars'] and not x['expected_cjk']), order[x['category']], -x['chars']))
    by_font.sort(key=lambda x: -x['cjk_chars'])
    gate = 'fail' if fail_pages else ('warn' if warn_pages else 'pass')
    installed = set()
    for e in font_index.values():
        installed |= {norm_family(f) for f in e['families']}
    decl_missing = OrderedDict((f, OrderedDict([('rfonts_elements', c), ('rfonts_attrs', decl['rfonts_attr_counts'].get(f, 0))]))
                               for f, c in decl['rfonts_element_counts'].items() if norm_family(f) not in installed)
    for f, pl in (decl.get('placement') or {}).items():
        if f in decl_missing:
            decl_missing[f]['document_xml_placement'] = pl
    non_cjk = [OrderedDict([('font', f['font']), ('category', f['category']), ('chars', f['chars']),
                            ('pages', f.get('pages')), ('distinct_chars', f.get('distinct_chars'))])
               for f in fonts if f['category'] in ('other', 'unmapped') and not f['cjk_chars']]
    return OrderedDict([
        ('cjk_fallback', OrderedDict([
            ('gate', gate),
            ('rule', 'profile.pdf_fonts（与 batch_health 同一规则）：某页落在 expected_cjk_regex 以外字体的汉字数 ≥ '
                     'fail_min_chars_page 记 FAIL 页，否则 WARN 页；符号、标点以外的非汉字不计'),
            ('expected_cjk_regex', rx_s), ('fail_min_chars_page', th),
            ('fail_page_count', len(fail_pages)), ('warn_page_count', len(warn_pages)),
            ('fail_pages', ranges(fail_pages)), ('warn_pages', ranges(warn_pages)), ('by_font', by_font)])),
        ('substitution', subst),
        ('non_cjk_other_fonts', non_cjk),
        ('unexpected_count', len(by_font)),
        ('unexpected_pages', ranges(fail_pages + warn_pages)),
        ('profile_families', profile_fams),
        ('fonts', fonts),
        ('not_embedded', sorted({v['basefont'] for v in scan['xref_fonts'].values() if v['ext'] in ('n/a', '')})),
        ('docx_requested_not_installed', decl_missing),
        ('docx_embedded_fonts', [{k: e[k] for k in ('declared', 'kind', 'ps_names')} for e in decl['embedded']]),
        ('method', 'PyMuPDF get_text(dict) 逐 span 字体名（去子集前缀）；PostScript 名经字体文件名表（fontconfig 目录＋LibreOffice 自带'
                   '＋DOCX 内嵌）映射到字族。category：profile=书册 typography（及 render.font_audit.expected_families）字族，'
                   'docx_requested=DOCX 的 rFonts/w:sym/主题实际请求过（fontTable 只列名不算），other=两者都不是，unmapped=名表里找不到。'
                   '门只看 cjk_fallback（汉字）与 substitution（请求与实得）；non_cjk_other_fonts 只列出，不计门。'
                   'docx_requested_not_installed 里 rfonts_elements 按 rFonts 元素计（一个元素多个属性写同一字体算一次），'
                   'rfonts_attrs 按属性计，document_xml_placement 是正文里这些元素的位置（run 东亚属性才影响汉字；段落标记不影响文字）'),
    ])


def compare_scans(new, ref, limit=40):
    n, m = new['page_count'], ref['page_count']
    same_text = same_ws = same_fonts = 0
    text_diff, font_diff, diff_pages, diffs = [], [], [], []
    for i in range(min(n, m)):
        a, b = new['pages'][i], ref['pages'][i]
        ta, tb = a['text'], b['text']
        fa = {k: v['chars'] for k, v in a['fonts'].items()}
        fb = {k: v['chars'] for k, v in b['fonts'].items()}
        eq = ta == tb
        eqws = eq or re.sub(r'\s+', '', ta) == re.sub(r'\s+', '', tb)
        same_text += eq
        same_ws += eqws
        same_fonts += fa == fb
        if not eq:
            text_diff.append(i + 1)
        if fa != fb:
            font_diff.append(i + 1)
        if not eq or fa != fb:
            diff_pages.append(i + 1)
            if len(diffs) < limit:
                k = next((j for j in range(min(len(ta), len(tb))) if ta[j] != tb[j]), min(len(ta), len(tb)))
                diffs.append({'page': i + 1, 'text_equal': eq, 'text_equal_ignoring_whitespace': eqws,
                              'fonts_equal': fa == fb, 'first_diff_at': None if eq else k,
                              'new': None if eq else clip(ta[max(0, k - 15):k + 25], 40),
                              'ref': None if eq else clip(tb[max(0, k - 15):k + 25], 40),
                              'font_chars_new': None if fa == fb else fa, 'font_chars_ref': None if fa == fb else fb})
    extra = list(range(min(n, m) + 1, max(n, m) + 1))
    text_gate = 'pass' if n == m and not text_diff else 'fail'
    font_gate = 'pass' if n == m and not font_diff else 'fail'

    def tot(s):
        c = Counter()
        for p in s['pages']:
            for k, v in p['fonts'].items():
                c[k] += v['chars']
        return c
    tn, tr = tot(new), tot(ref)
    return OrderedDict([
        ('gate', 'pass' if text_gate == font_gate == 'pass' else 'fail'), ('text_gate', text_gate), ('font_gate', font_gate),
        ('pages_new', n), ('pages_ref', m), ('page_count_equal', n == m),
        ('text_equal_pages', same_text), ('text_equal_ignoring_whitespace_pages', same_ws),
        ('font_usage_equal_pages', same_fonts), ('compared_pages', min(n, m)),
        ('all_text_equal', n == m and not text_diff),
        ('differing_page_count', len(diff_pages) + len(extra)), ('differing_pages', ranges(diff_pages + extra)),
        ('text_differing_pages', ranges(text_diff)), ('font_differing_pages', ranges(font_diff)),
        ('extra_pages', ranges(extra)), ('extra_pages_in', ('new' if n > m else 'ref') if extra else None),
        ('diffs', diffs), ('diffs_total', len(diff_pages)), ('diffs_limit', limit), ('diffs_truncated', len(diff_pages) > limit),
        ('font_totals_only_in_new', {k: v for k, v in tn.items() if k not in tr}),
        ('font_totals_only_in_ref', {k: v for k, v in tr.items() if k not in tn}),
        ('font_totals_changed', {k: [tn[k], tr[k]] for k in tn if k in tr and tn[k] != tr[k]}),
        ('method', '逐页 PyMuPDF get_text(dict) 拼接文本（含页脚页码）精确比较，另报去空白比较与每页字体用字数；页数、文本、字体用字量'
                   '任一不等即不一致'),
        ('limits', '测不到纯像素差异：文本与字体一致不代表像素一致（换行位置不变的字形、间距、图片变化都看不出）。像素对照留给 page_delta'),
    ])


# ---------------------------------------------------------------- PNG（仅 --png 时）
def export_png(pdf, pages, dpi, engine, png_root, rc, pdf_sha):
    """图放在 <png_root>/<PDF哈希前16位>_<dpi>dpi_<光栅器>/；先清掉该目录里本工具命名的旧页图，使目录与本次结果一致。"""
    sub = Path(png_root) / ('%s_%ddpi_%s' % (pdf_sha[:16], dpi, engine))
    sub.mkdir(parents=True, exist_ok=True)
    removed = 0
    for f in sub.iterdir():
        if f.is_file() and re.fullmatch(r'page-\d+\.png', f.name):
            f.unlink()
            removed += 1
        elif f.is_dir() and f.name.startswith('.tmp_'):
            shutil.rmtree(str(f), ignore_errors=True)
    t0 = time.perf_counter()
    made = []
    if engine == 'fitz':
        import fitz
        doc = fitz.open(str(pdf))
        for p in pages:
            out = sub / ('page-%d.png' % p)
            doc[p - 1].get_pixmap(dpi=dpi).save(str(out))
            made.append(out.name)
        doc.close()
        rast = 'PyMuPDF %s' % fitz.VersionBind
    else:
        tool = shutil.which('pdftoppm', path=str(xp(rc['path_prepend'])))
        if not tool:
            raise RenderError(2, '渲染环境缺失：%s 下没有 pdftoppm（可改用 --png-engine fitz）' % rc['path_prepend'])
        rast = subprocess.run([tool, '-v'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True).stdout.split('\n')[0].strip()
        segs, cur = [], []
        for p in pages:
            if cur and p != cur[-1] + 1:
                segs.append(cur)
                cur = []
            cur.append(p)
        if cur:
            segs.append(cur)
        jobs = []
        for s in segs:
            k = max(1, min(8, len(s) // 40))
            step = -(-len(s) // k)
            jobs += [s[i:i + step] for i in range(0, len(s), step)]
        tmp = sub / ('.tmp_%d' % os.getpid())
        tmp.mkdir(exist_ok=True)
        running = []
        for j, s in enumerate(jobs):
            running.append(subprocess.Popen([tool, '-r', str(dpi), '-f', str(s[0]), '-l', str(s[-1]), '-png', str(pdf), str(tmp / ('j%d' % j))],
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE))
            if len(running) >= 8:
                running.pop(0).wait()
        for r in running:
            r.wait()
        for f in tmp.glob('j*-*.png'):
            dst = sub / ('page-%d.png' % int(f.stem.rsplit('-', 1)[1]))
            os.replace(str(f), str(dst))
            made.append(dst.name)
        shutil.rmtree(str(tmp), ignore_errors=True)
        if len(made) != len(pages):
            raise RenderError(3, 'PNG 数量不对：要 %d 张，得到 %d 张' % (len(pages), len(made)))
    files = sorted((f.name for f in sub.iterdir() if f.is_file() and re.fullmatch(r'page-\d+\.png', f.name)),
                   key=lambda x: int(re.findall(r'\d+', x)[0]))
    return OrderedDict([('png_dir', str(sub)), ('png_count', len(files)), ('png_pages', ranges(pages)), ('png_files', files),
                        ('png_removed_old', removed), ('png_dpi', dpi), ('png_engine', engine), ('png_rasterizer', rast),
                        ('png_seconds', round(time.perf_counter() - t0, 2))])


# ---------------------------------------------------------------- 缓存
def env_snapshot(prof, rc, mode, cache_dir, fc_mode, fc_explicit, write=True):
    env = OrderedDict()
    env.update(soffice_info(rc['soffice']))
    if mode == 'render_docx':
        env.update(pick_renderer(rc.get('_renderer_override') or rc['renderer_glob']))
    else:
        env.update(renderer_path=None, renderer_version='soffice-direct', renderer_sha256=None, renderer_candidates=[],
                   renderer_warnings=[])
    env.update(make_fontconfig(prof, rc, cache_dir, fc_mode, fc_explicit, write))
    files = font_files(env['fontconfig_dirs'] + ([env['lo_bundled_fonts']] if env['lo_bundled_fonts'] else []))
    env['font_files_sha256'], env['font_files'] = font_fingerprint(files)
    env['_font_file_list'] = files
    comp = OrderedDict((k, env.get(k)) for k in ENV_KEYS)
    comp['mode'] = mode
    env['env_components'] = comp
    env['env_sha256'] = sha256_json(comp)
    return env


def cache_key(docx_sha, mode, env, allow_fallback):
    comp = OrderedDict([('key_version', 2), ('docx_sha256', docx_sha), ('mode', mode), ('env_sha256', env['env_sha256']),
                        ('allow_odt_fallback', bool(allow_fallback))])
    return sha256_json(comp), comp


def _place(src, dst):
    """把缓存 PDF 放到输出位置：能硬链接就硬链接（不重复占盘），否则复制。"""
    dst = Path(dst)
    if dst.exists():
        try:
            if os.path.samefile(str(src), str(dst)):
                return 'existing_link'
        except OSError:
            pass
    tmp = Path(str(dst) + '.tmp-%d' % os.getpid())
    if tmp.exists():
        tmp.unlink()
    try:
        os.link(str(src), str(tmp))
        how = 'hardlink'
    except OSError:
        shutil.copyfile(str(src), str(tmp))
        how = 'copy'
    os.replace(str(tmp), str(dst))
    return how


def prune_cache(cache_dir, keep=3, protect=()):
    """只删本工具命名的缓存条目（entries/<64位哈希>.json 与 pdf/<同名>.pdf）：按最近使用保留 keep 条及 protect 里的键。"""
    cd = Path(cache_dir)
    ed, pd = cd / 'entries', cd / 'pdf'
    rx = re.compile(r'^[0-9a-f]{64}$')
    ents = sorted((p for p in ed.glob('*.json') if rx.match(p.stem)), key=lambda p: p.stat().st_mtime, reverse=True) if ed.is_dir() else []
    keep_keys = set(protect) | {p.stem for p in ents[:max(0, keep)]}
    removed, freed = [], 0
    victims = [p.stem for p in ents if p.stem not in keep_keys]
    if pd.is_dir():
        victims += [f.stem for f in pd.glob('*.pdf') if rx.match(f.stem) and f.stem not in keep_keys and not (ed / (f.stem + '.json')).exists()]
    for k in dict.fromkeys(victims):
        for f in (pd / (k + '.pdf'), ed / (k + '.json')):
            if f.exists():
                st = f.stat()
                if st.st_nlink == 1:
                    freed += st.st_size
                f.unlink()
        removed.append(k[:16])
    return OrderedDict([('cache_dir', str(cd)), ('kept', len(keep_keys & ({p.stem for p in ents}))), ('removed', removed),
                        ('freed_bytes', freed), ('note', '硬链接到输出目录的 PDF 删缓存后仍在，不计入释放量')])


# ---------------------------------------------------------------- 已存在文件的归属
def _read_own_json(p, what):
    """已存在的 JSON 必须是本工具写的（有 tool 字段）才允许覆盖；不存在返回 None。"""
    p = Path(p)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        d = None
    if not (isinstance(d, dict) and str(d.get('tool', '')).startswith('render_book.py')):
        raise RenderError(4, '拒绝覆盖不是 render_book 写的%s：%s' % (what, p))
    return d


def _pdf_owned(out_pdf, ident_data, cache_dir):
    sha = sha256_file(out_pdf)
    if ident_data and ident_data.get('pdf_sha256') == sha and os.path.normpath(str(ident_data.get('pdf', ''))) == str(out_pdf):
        return True
    ed = Path(cache_dir) / 'entries'
    if ed.is_dir():
        for p in ed.glob('*.json'):
            try:
                if json.loads(p.read_text(encoding='utf-8')).get('pdf_sha256') == sha:
                    return True
            except Exception:
                pass
    return False


def _plain_name(name, what):
    s = str(name)
    if (not s or s != s.strip() or '/' in s or '\\' in s or '\x00' in s or s in ('.', '..') or s.startswith('.')
            or os.path.isabs(s)):
        raise RenderError(2, '%s 只接受纯文件名（不含路径分隔符、..、绝对路径，不以点开头）：%r' % (what, s))
    return s


# ---------------------------------------------------------------- 主流程
def render_book(docx, out_dir, book=None, profile=None, mode='render_docx', cache_dir=None, no_cache=False,
                key_only=False, png=False, pages=None, dpi=None, png_engine=None, png_dir=None, compare_pdf=None,
                fontconfig_mode='auto', fontconfig=None, lo_profile_mode='fresh', timeout=None,
                allow_odt_fallback=False, identity=None, pdf_name=None, renderer=None,
                fail_on_fallback=False, fail_on_substitution=False, guard_profiles=None, prune_keep=None):
    """返回结果字典；失败抛 RenderError（带退出码）。门结果在 result['gates']，status 由门结果决定。"""
    T0 = time.perf_counter()
    tm = OrderedDict()
    docx = Path(_abs(docx))
    if not docx.exists():
        raise RenderError(2, 'DOCX 不存在：%s' % docx)
    if not docx.is_file():
        raise RenderError(2, 'DOCX 不是文件：%s' % docx)
    try:
        with zipfile.ZipFile(str(docx)) as z:
            if 'word/document.xml' not in z.namelist():
                raise RenderError(2, '不是有效的 DOCX（缺 word/document.xml）：%s' % docx)
    except zipfile.BadZipFile:
        raise RenderError(2, '不是有效的 DOCX（不是 zip 包）：%s' % docx)
    if pages and not png:
        raise RenderError(2, '--pages 只在 --png 时有效')

    # 书册：选定的配置与 DOCX 实际所在的书必须一致
    profs = all_profiles(guard_profiles)
    located = locate_book(docx, profs)
    if profile:
        prof = load_profile(str(xp(profile)))
    elif book:
        try:
            prof = load_profile(book)
        except FileNotFoundError:
            raise RenderError(2, '没有书册配置：%s（可选：%s）' % (book, ', '.join(list_profiles())))
    elif located is not None:
        prof = located
    else:
        raise RenderError(2, '无法从路径判断书册，请用 --book 指定（可选：%s）' % ', '.join(list_profiles()))
    if located is not None and located.get('book_id') != prof.get('book_id'):
        raise RenderError(2, '书册不一致：DOCX 位于《%s》（%s）的目录，却指定了 %s。请去掉 --book/--profile 或改用对应书册' % (
            _title(located), located.get('book_id'), prof.get('book_id')))
    if not any(p.get('_profile_path') == prof.get('_profile_path') for p in profs):
        profs.append(prof)
    rc = render_cfg(prof)
    if renderer:
        rc['_renderer_override'] = str(xp(renderer))

    # 输出位置
    out_dir = Path(_abs(out_dir))
    if not cache_dir and rc.get('cache_dir'):
        cache_dir = str(rc['cache_dir']).replace('<build_dir>', str(out_dir))
    cache_dir = Path(_abs(cache_dir)) if cache_dir else out_dir / '.render_cache'
    lo_base = Path(_abs(str(rc.get('lo_profile') or '<build_dir>/lo_profile').replace('<build_dir>', str(out_dir))))
    stem = docx.stem
    if pdf_name:
        stem = _plain_name(pdf_name, '--pdf-name')
        stem = stem[:-4] if stem.lower().endswith('.pdf') else stem
        if not stem:
            raise RenderError(2, '--pdf-name 不能只是 .pdf')
    out_pdf = out_dir / (stem + '.pdf')
    ident = Path(_abs(identity)) if identity else out_dir / rc.get('identity_file', '同版身份.json')
    if _within(_chain(ident.parent), _Loc(out_dir)) is None:
        raise RenderError(4, '--identity 必须位于 --out-dir 之内：%s' % ident)
    if ident.suffix.lower() != '.json' or _nk(str(ident)) == _nk(str(out_pdf)):
        raise RenderError(2, '--identity 必须是 .json 文件，且不能与输出 PDF 同名：%s' % ident)
    pngd = Path(_abs(png_dir)) if png_dir else out_dir / 'png'
    guard = WriteGuard(profs, docx, prof)
    for d in [out_dir, out_dir / '.work', cache_dir, lo_base] + ([pngd] if png else []):
        guard.check(d)
    for f in (out_pdf, ident):
        guard.check(f, is_file=True)
    assert out_pdf.parent == out_dir

    t = time.perf_counter()
    docx_sha = sha256_file(docx)
    env = env_snapshot(prof, rc, mode, cache_dir, fontconfig_mode, fontconfig, write=not key_only)
    key, comp = cache_key(docx_sha, mode, env, allow_odt_fallback)
    tm['key_seconds'] = round(time.perf_counter() - t, 3)
    entry_path = cache_dir / 'entries' / (key + '.json')
    cached_pdf = cache_dir / 'pdf' / (key + '.pdf')
    pub_env = OrderedDict((k, v) for k, v in env.items() if not k.startswith('_'))
    result = OrderedDict([('tool', TOOL), ('book_id', prof.get('book_id')), ('title', prof.get('title')),
                          ('frozen', bool(prof.get('frozen'))), ('profile_path', prof.get('_profile_path')),
                          ('docx', str(docx)), ('docx_sha256', docx_sha), ('mode', mode), ('cache_key', key),
                          ('cache_key_components', comp), ('cache_dir', str(cache_dir))])
    if key_only:
        hit = False
        if entry_path.exists() and cached_pdf.exists():
            try:
                hit = sha256_file(cached_pdf) == json.loads(entry_path.read_text(encoding='utf-8')).get('pdf_sha256')
            except Exception:
                hit = False
        result.update(cache_hit=hit, env=pub_env, timings=tm, wrote_nothing=True)
        return result

    # 已存在且不是本工具写的，不覆盖
    prev_ident = _read_own_json(ident, '同版身份')
    if out_pdf.exists() and not _pdf_owned(out_pdf, prev_ident, cache_dir):
        raise RenderError(4, '拒绝覆盖已存在、且不是 render_book 写的 PDF：%s（请换 --out-dir 或 --pdf-name）' % out_pdf)

    out_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / 'entries').mkdir(parents=True, exist_ok=True)
    (cache_dir / 'pdf').mkdir(exist_ok=True)
    lock = open(str(cache_dir / ('.lock-' + key[:16])), 'w')
    fcntl.flock(lock, fcntl.LOCK_EX)
    scan = None
    try:
        entry, status, reason = None, 'miss', None
        if no_cache:
            reason = '按 --no-cache 强制重渲'
        elif entry_path.exists():
            entry = json.loads(entry_path.read_text(encoding='utf-8'))
            if cached_pdf.exists() and sha256_file(cached_pdf) == entry.get('pdf_sha256'):
                status = 'hit'
                os.utime(str(entry_path), None)  # 记最近使用，供 --prune-cache
            else:
                reason = '缓存条目存在但缓存 PDF 缺失或 SHA 不符（可能被就地改过），按未命中重渲'
                entry = None
        if status == 'miss':
            py_ver = check_python(rc['python']) if mode == 'render_docx' else None  # 在复制 DOCX 之前
            work = out_dir / '.work' / ('%s-%d' % (time.strftime('%Y%m%d-%H%M%S'), os.getpid()))
            (work / 'src').mkdir(parents=True, exist_ok=True)
            docx_copy = work / 'src' / docx.name
            shutil.copyfile(str(docx), str(docx_copy))
            if sha256_file(docx_copy) != docx_sha:
                raise RenderError(3, '复制出的 DOCX 与源 SHA 不同，源文件可能正在被写入：%s' % docx)
            lo_profile = lo_base / work.name if lo_profile_mode == 'fresh' else lo_base
            lo_profile.mkdir(parents=True, exist_ok=True)
            try:
                pdf_tmp, render_detail = convert(mode, rc, env, env['fontconfig_path'], docx_copy, work, lo_profile,
                                                 int(timeout or rc.get('timeout_s') or DEFAULTS['timeout_s']), allow_odt_fallback)
            except RenderError as e:
                # 失败现场保留，便于查原因；不重跑
                e.detail.update(work_dir=str(work), lo_profile=str(lo_profile), cache_key=key)
                raise
            render_detail['python_version'] = py_ver
            tm['convert_seconds'] = render_detail['seconds']
            tmpc = Path(str(cached_pdf) + '.tmp-%d' % os.getpid())
            try:
                os.replace(str(pdf_tmp), str(tmpc))
            except OSError:
                shutil.copyfile(str(pdf_tmp), str(tmpc))
            os.replace(str(tmpc), str(cached_pdf))
            entry = {'tool': TOOL, 'key': key, 'components': comp, 'env_components': env['env_components'],
                     'pdf_sha256': sha256_file(cached_pdf), 'rendered_at': now_iso(), 'docx': str(docx),
                     'render_detail': render_detail, 'lo_profile_mode': lo_profile_mode}
            # 本次自己建的临时目录（源副本、转换目录、一次性 LibreOffice 配置）用完即清
            shutil.rmtree(str(work), ignore_errors=True)
            if lo_profile_mode == 'fresh':
                shutil.rmtree(str(lo_profile), ignore_errors=True)
            for d in (work.parent, lo_base):
                try:
                    d.rmdir()  # 只删空目录
                except OSError:
                    pass
        pdf_sha = entry['pdf_sha256']
        placed = _place(cached_pdf, out_pdf)

        # 字体审计：输入不变就复用
        t = time.perf_counter()
        audit_on = rc.get('font_embed_audit', True) is not False
        fa_cfg = json.dumps({'typ': typography_families(prof), 'fa': rc.get('font_audit'), 'pf': prof.get('pdf_fonts'),
                             'al': (rc.get('fontconfig') or {}).get('aliases')}, sort_keys=True, ensure_ascii=False)
        audit_key = sha256_text('|'.join([TOOL, AUDIT_REV, pdf_sha, docx_sha, env['font_files_sha256'], env['fontconfig_semantic_sha256'], fa_cfg]))
        if not audit_on:
            audit, audit_state = None, 'disabled'
            if not entry.get('pdf_pages'):
                import fitz
                with fitz.open(str(out_pdf)) as d:
                    entry.update(pdf_pages=d.page_count, pdf_producer=(d.metadata or {}).get('producer'),
                                 embedded_fonts=sorted({f[3] for pg in d for f in pg.get_fonts(full=False)}))
        elif entry.get('font_audit') and entry.get('audit_key') == audit_key:
            audit, audit_state = entry['font_audit'], 'reused'
        else:
            scan = scan_pdf(out_pdf)
            decl = docx_font_decls(str(docx))
            idx = build_font_index(env['_font_file_list'], decl['embedded'])
            inst = {norm_family(x) for e in idx.values() for x in e['families']}
            decl['placement'] = rfonts_placement(str(docx), [f for f in decl['rfonts_element_counts'] if norm_family(f) not in inst])
            rx = re.compile((prof.get('pdf_fonts') or {}).get('expected_cjk_regex') or DEFAULTS['cjk_regex'])
            fb_fonts = {n for pg in scan['pages'] for n, e in pg['fonts'].items() if e['cjk'] and not rx.search(n)}
            subst = check_requests(docx_ea_segments(str(docx)), scan, idx, (rc.get('fontconfig') or {}).get('aliases') or {},
                                   env.get('fontconfig_aliases') or {}, fb_fonts)
            audit, audit_state = audit_fonts(scan, prof, rc, decl, idx, subst), 'run'
            entry.update(font_audit=audit, audit_key=audit_key, pdf_pages=scan['page_count'],
                         pdf_producer=scan['metadata'].get('producer'),
                         embedded_fonts=sorted({v['basefont'] for v in scan['xref_fonts'].values()}))
        pages_n = entry['pdf_pages']
        tm['font_audit_seconds'] = round(time.perf_counter() - t, 3)
        tmp = entry_path.with_suffix('.tmp')
        tmp.write_text(json.dumps(entry, ensure_ascii=False, indent=1), encoding='utf-8')
        os.replace(str(tmp), str(entry_path))
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()

    # 对照：结果另存 compare_<对照PDF哈希前16位>.json；同一 PDF 的历次对照留在 compare_history
    cmp_res, cmp_file = None, None
    history = list(prev_ident.get('compare_history') or []) if prev_ident and prev_ident.get('pdf_sha256') == pdf_sha else []
    if compare_pdf:
        t = time.perf_counter()
        ref = Path(_abs(compare_pdf))
        if not ref.is_file():
            raise RenderError(2, '对照 PDF 不存在：%s' % ref)
        if scan is None:
            scan = scan_pdf(out_pdf)
        cmp_res = compare_scans(scan, scan_pdf(ref, lite=True))
        ref_sha = sha256_file(ref)
        cmp_res['ref_pdf'], cmp_res['ref_pdf_sha256'] = str(ref), ref_sha
        cmp_file = out_dir / ('compare_%s.json' % ref_sha[:16])
        guard.check(cmp_file, is_file=True)
        _read_own_json(cmp_file, '对照结果')
        doc = OrderedDict([('tool', TOOL), ('pdf', str(out_pdf)), ('pdf_sha256', pdf_sha), ('written_at', now_iso())])
        doc.update(cmp_res)
        tmp = cmp_file.with_suffix('.tmp')
        tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
        os.replace(str(tmp), str(cmp_file))
        cmp_res['compare_file'] = str(cmp_file)
        history.append(OrderedDict([('at', now_iso()), ('ref_pdf', str(ref)), ('ref_pdf_sha256', ref_sha), ('gate', cmp_res['gate']),
                                    ('text_gate', cmp_res['text_gate']), ('font_gate', cmp_res['font_gate']),
                                    ('pages_new', cmp_res['pages_new']), ('pages_ref', cmp_res['pages_ref']),
                                    ('differing_page_count', cmp_res['differing_page_count']), ('compare_file', str(cmp_file))]))
        tm['compare_seconds'] = round(time.perf_counter() - t, 2)

    png_res = None
    if png:
        pl = parse_pages(pages, pages_n) if pages else list(range(1, pages_n + 1))
        eng = png_engine or rc.get('png_engine') or DEFAULTS['png_engine']
        png_res = export_png(out_pdf, pl, int(dpi or rc.get('png_dpi') or 120), eng, pngd, rc, pdf_sha)
        tm['png_seconds'] = png_res['png_seconds']

    # 门与状态
    gates = OrderedDict([('render', 'pass')])
    if cmp_res:
        gates['compare'], gates['compare_source'] = cmp_res['gate'], 'this_run'
    elif history:
        gates['compare'], gates['compare_source'] = history[-1]['gate'], 'history'
    else:
        gates['compare'], gates['compare_source'] = 'not_run', None
    gates['font_audit'] = audit_state
    gates['font_cjk_fallback'] = audit['cjk_fallback']['gate'] if audit else 'not_run'
    gates['font_substitution'] = audit['substitution']['gate'] if audit else 'not_run'
    flags = []
    if gates['compare'] == 'fail':
        flags.append('FAIL_COMPARE' if gates['compare_source'] == 'this_run' else 'FAIL_COMPARE_PREVIOUS')
    if gates['font_cjk_fallback'] in ('fail', 'warn'):
        flags.append('FAIL_FONT_FALLBACK' if fail_on_fallback else 'WARN_FONT_FALLBACK')
    if gates['font_substitution'] == 'warn':
        flags.append('FAIL_FONT_SUBSTITUTION' if fail_on_substitution else 'WARN_FONT_SUBSTITUTION')
    status_s = next((f for f in flags if f.startswith('FAIL')), None) or next((f for f in flags if f.startswith('WARN')), 'PASS')
    exit_code = 0
    if cmp_res and cmp_res['gate'] == 'fail':
        exit_code = 5
    elif fail_on_fallback and gates['font_cjk_fallback'] in ('fail', 'warn'):
        exit_code = 6
    elif fail_on_substitution and gates['font_substitution'] == 'warn':
        exit_code = 7
    tm['total_seconds'] = round(time.perf_counter() - T0, 2)

    if audit:
        emb = [OrderedDict([('font', f['font']), ('category', f['category']), ('chars', f['chars']),
                            ('cjk_chars', f['cjk_chars']), ('page_count', f['page_count'])]) for f in audit['fonts']]
    else:
        emb = entry.get('embedded_fonts')
    vals = OrderedDict([('docx_sha256', docx_sha), ('pdf_sha256', pdf_sha), ('pdf_pages', pages_n),
                        ('png_count', png_res['png_count'] if png_res else 0),
                        ('renderer_path', env['renderer_path']), ('renderer_version', env['renderer_version']),
                        ('soffice_version', env['soffice_version']), ('fontconfig_sha256', env['fontconfig_sha256']),
                        ('embedded_fonts', emb)])
    rec = OrderedDict()
    for k in rc.get('record') or list(vals):
        rec[k] = vals.get(k)
    for k, v in vals.items():  # 配置没列的核心字段也写上，放在后面
        rec.setdefault(k, v)
    result.update(rec)
    result.update(OrderedDict([
        ('status', status_s), ('status_flags', flags), ('gates', gates), ('exit_code', exit_code),
        ('pdf', str(out_pdf)), ('pdf_placed', placed), ('rendered_from_docx_sha256', docx_sha),
        ('pdf_producer', entry.get('pdf_producer')),
        ('env_sha256', env['env_sha256']), ('env_components', env['env_components']),
        ('cache', OrderedDict([('status', status), ('hit', status == 'hit'), ('reason', reason),
                               ('entry', str(entry_path)), ('cached_pdf', str(cached_pdf)),
                               ('source_rendered_at', entry.get('rendered_at')), ('font_audit', audit_state)])),
        ('renderer_sha256', env['renderer_sha256']), ('renderer_candidates', env['renderer_candidates']),
        ('renderer_warnings', env['renderer_warnings']),
        ('soffice_path', env['soffice_path']), ('soffice_short_version', env['soffice_short_version']),
        ('soffice_build_id', env['soffice_build_id']), ('soffice_bin_sha256', env['soffice_bin_sha256']),
        ('runtime_manifest', env['runtime_manifest']), ('runtime_manifest_path', env['runtime_manifest_path']),
        ('runtime_manifest_sha256', env['runtime_manifest_sha256']),
        ('lo_bundle_fingerprint', env['lo_bundle_fingerprint']), ('lo_bundle_files', env['lo_bundle_files']),
        ('python', str(xp(rc['python'])) if mode == 'render_docx' else None),
        ('python_version', (entry.get('render_detail') or {}).get('python_version')),
        ('path_prepend', str(xp(rc['path_prepend']))),
        ('lo_profile', str(lo_base)), ('lo_profile_mode', lo_profile_mode),
        ('fontconfig_sha256_basis', env['fontconfig_sha256_basis']),
        ('fontconfig_semantic_sha256', env['fontconfig_semantic_sha256']),
        ('fontconfig_file_sha256', env['fontconfig_file_sha256']),
        ('fontconfig_source_sha256', env['fontconfig_source_sha256']),
        ('fontconfig', OrderedDict((k, env.get(k)) for k in (
            'fontconfig_path', 'fontconfig_mode', 'fontconfig_source', 'fontconfig_historical', 'fontconfig_historical_sha256',
            'fontconfig_equivalent_to_historical', 'fontconfig_cachedir', 'fontconfig_dirs', 'fontconfig_missing_dirs',
            'fontconfig_aliases', 'template_detail'))),
        ('font_files', env['font_files']), ('font_files_sha256', env['font_files_sha256']),
        ('render_detail', entry.get('render_detail')),
        ('font_audit', audit), ('compare', cmp_res), ('compare_history', history),
        ('png', png_res),
        ('previous_identity', OrderedDict([('pdf_sha256', prev_ident.get('pdf_sha256')), ('status', prev_ident.get('status')),
                                           ('written_at', prev_ident.get('written_at'))]) if prev_ident else None),
        ('timings', tm), ('note', MECH_NOTE), ('written_at', now_iso()),
    ]))
    ident.parent.mkdir(parents=True, exist_ok=True)
    tmp = ident.with_suffix('.tmp')
    tmp.write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    os.replace(str(tmp), str(ident))
    result['identity_file'] = str(ident)
    if prune_keep is not None:
        result['prune'] = prune_cache(cache_dir, prune_keep, protect=[key])
    return result


def summary_lines(r):
    if 'pdf' not in r:
        return ['render_book｜%s｜只算缓存键（未写盘）：%s｜%s' % (r.get('title'), r['cache_key'][:16], '缓存命中' if r.get('cache_hit') else '缓存未命中')]
    c, tm, a, g = r['cache'], r['timings'], r.get('font_audit'), r['gates']
    head = '缓存命中，复用 %s 的渲染' % c['source_rendered_at'] if c['hit'] else '缓存未命中→已渲染（LibreOffice %.1f 秒）' % tm.get('convert_seconds', 0)
    out = ['render_book｜%s｜%s｜%d 页｜总用时 %.2f 秒｜status %s' % (r['title'], head, r['pdf_pages'], tm['total_seconds'], r['status'])]
    out.append('PDF：%s（sha256 %s…，%s）' % (r['pdf'], r['pdf_sha256'][:16], r['pdf_placed']))
    out.append('环境：渲染器 %s｜soffice %s（build %s）｜fontconfig %s（%s；%s）｜env %s' % (
        r['renderer_version'], r['soffice_version'], (r.get('soffice_build_id') or '?')[:12], r['fontconfig_sha256'][:16],
        r['fontconfig']['fontconfig_mode'], r['fontconfig_sha256_basis'], r['env_sha256'][:16]))
    for w in r.get('renderer_warnings') or []:
        out.append('警告：' + w)
    fcw = r['fontconfig']
    if fcw.get('fontconfig_missing_dirs'):
        out.append('警告：fontconfig 里有 %d 个字体目录不存在：%s' % (len(fcw['fontconfig_missing_dirs']), clip('；'.join(fcw['fontconfig_missing_dirs']), 120)))
    if (fcw.get('template_detail') or {}).get('families_not_found'):
        out.append('警告：模板没找到这些书册字体：%s' % '、'.join(fcw['template_detail']['families_not_found']))
    if a:
        cf = a['cjk_fallback']
        out.append('汉字回退门：%s（规则 %s，FAIL 页 %d，WARN 页 %d）' % (cf['gate'], cf['expected_cjk_regex'], cf['fail_page_count'], cf['warn_page_count']))
        for f in cf['by_font']:
            smp = f['samples'][0] if f['samples'] else None
            out.append('  %s：%d 个汉字，%d 页（p.%s）%s' % (f['font'], f['cjk_chars'], f['cjk_page_count'], clip(f['cjk_pages'], 50),
                                                  '例 p.%d「%s」' % (smp['page'], smp['span']) if smp else ''))
        sb = a['substitution']
        cov = sb['coverage']
        rv = sb['reverse']
        out.append('请求与实得：%s（正向抽样定位 %d 段，相符 %d，不符 %d；反向追查回退 span %d 个，查到请求 %d 个）' % (
            sb['gate'], sum(x['located'] for x in cov.values()), sum(x['matched'] for x in cov.values()),
            sum(x['substituted'] for x in cov.values()), rv['spans'], rv['traced']))
        for p in sb['pairs'][:8]:
            ex = p['examples'][0] if p['examples'] else None
            out.append('  请求 %s%s → 实得 %s：%d 处（表格内 %d；p.%s）%s%s' % (
                p['requested'], '（本机已装）' if p['requested_installed'] else '（本机未装）', p['actual'], p['samples'],
                p['in_table_hits'], clip(p['pages'], 40), '〔字类不同〕' if p['class_mismatch'] else '',
                ' 例 p.%d「%s」' % (ex['page'], ex['docx_text']) if ex else ''))
        if a['non_cjk_other_fonts']:
            out.append('非书册字体（无汉字，只列出不计门）：%s' % '；'.join('%s %d 字 p.%s' % (f['font'], f['chars'], clip(f['pages'] or '', 30))
                                                        for f in a['non_cjk_other_fonts'][:6]))
    else:
        out.append('字体审计：未做（profile.render.font_embed_audit=false）')
    if r.get('compare'):
        k = r['compare']
        out.append('对照：%s｜页数 %d/%d；逐页文本一致 %d/%d（去空白 %d）；逐页字体用量一致 %d；不同页 %d 页：%s%s' % (
            k['gate'], k['pages_new'], k['pages_ref'], k['text_equal_pages'], k['compared_pages'],
            k['text_equal_ignoring_whitespace_pages'], k['font_usage_equal_pages'], k['differing_page_count'],
            clip(k['differing_pages'] or '无', 80), '（明细只列前 %d 页）' % k['diffs_limit'] if k['diffs_truncated'] else ''))
        out.append('  对照结果：%s；%s' % (k['compare_file'], k['limits']))
    elif g['compare_source'] == 'history':
        h = r['compare_history'][-1]
        out.append('对照：本次未做；沿用本 PDF 前次记录 %s（%s，对照 %s）' % (h['gate'], h['at'], h['ref_pdf']))
    if r.get('png'):
        out.append('PNG：%d 张（%s dpi，%s）→ %s' % (r['png']['png_count'], r['png']['png_dpi'], r['png']['png_rasterizer'], r['png']['png_dir']))
    if r.get('prune'):
        out.append('缓存清理：删 %d 条，释放 %.1f MB' % (len(r['prune']['removed']), r['prune']['freed_bytes'] / 1e6))
    out.append('同版身份：%s' % r.get('identity_file'))
    out.append('说明：' + MECH_NOTE)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description='按书册配置把 DOCX 渲染成 PDF（缓存、同版身份、嵌入字体审计、写入边界保护；默认不转 PNG）')
    ap.add_argument('--docx', help='要渲染的 DOCX（只读；会先复制到 <out-dir>/.work 再转换）')
    ap.add_argument('--out-dir', help='输出目录（PDF、同版身份.json、默认缓存都在这里；不能是书稿同目录或受保护目录）')
    ap.add_argument('--book', help='书册 id（profiles/<id>.json）；不给就按 DOCX 路径判断；与 DOCX 所在书册不一致时报错')
    ap.add_argument('--profile', help='直接给书册配置文件路径')
    ap.add_argument('--guard-profile', action='append', default=[],
                    help='额外纳入写入保护的书册配置文件（尚未放进 profiles/ 的书册或测试用；可重复）')
    ap.add_argument('--mode', choices=['render_docx', 'soffice'], default='render_docx',
                    help='render_docx=与各批 05 全书渲染同一路径（默认）；soffice=与 03 目录定位同样的直接转换')
    ap.add_argument('--cache-dir', help='缓存目录（默认 <out-dir>/.render_cache，或 profile.render.cache_dir）')
    ap.add_argument('--no-cache', action='store_true', help='不查缓存，强制重渲（结果仍写入缓存）')
    ap.add_argument('--key-only', action='store_true', help='只算缓存键和是否命中，不渲染、不写盘')
    ap.add_argument('--png', action='store_true', help='另外转 PNG（默认不转）')
    ap.add_argument('--pages', help='只给这些页转 PNG，例：1-4,321,600-（须与 --png 同用）')
    ap.add_argument('--dpi', type=int, help='PNG 分辨率（默认 profile.render.png_dpi）')
    ap.add_argument('--png-engine', choices=['pdftoppm', 'fitz'], help='PNG 光栅器（默认 pdftoppm，与 render_docx 同为 poppler）')
    ap.add_argument('--png-dir', help='PNG 根目录（默认 <out-dir>/png；图实际放在其下 <PDF哈希>_<dpi>dpi_<光栅器>/）')
    ap.add_argument('--compare-pdf', help='对照 PDF：比较页数、逐页文本与逐页字体用字量（不比像素），任一不等退出码 5')
    ap.add_argument('--fontconfig-mode', choices=['auto', 'historical', 'template'], default='auto',
                    help='auto=有 historical_file 且 SHA 前缀相符就用它派生，否则按 house 模板生成')
    ap.add_argument('--fontconfig', help='直接指定 fontconfig 源文件（仍会改写 cachedir 后使用；不支持 <include> 与 prefix/相对 <dir>）')
    ap.add_argument('--lo-profile-mode', choices=['fresh', 'reuse'], default='fresh',
                    help='fresh=每次新建 LibreOffice 用户配置（与 render_docx 相同，默认）；reuse=复用 lo_profile')
    ap.add_argument('--timeout', type=int, help='渲染超时秒数（默认 profile.render.timeout_s 或 900）')
    ap.add_argument('--allow-odt-fallback', action='store_true', help='允许 render_docx 在直转失败时改走 ODT 回退（默认拦下并报错）')
    ap.add_argument('--fail-on-fallback', action='store_true', help='汉字字体回退（FAIL 或 WARN 页）时以退出码 6 结束')
    ap.add_argument('--fail-on-substitution', action='store_true', help='请求与实得字族不符时以退出码 7 结束')
    ap.add_argument('--identity', help='同版身份 JSON 路径（默认 <out-dir>/profile.render.identity_file；必须在 --out-dir 内）')
    ap.add_argument('--pdf-name', help='输出 PDF 文件名（纯文件名；默认与 DOCX 同名）')
    ap.add_argument('--renderer', help='指定某一版 render_docx.py（默认按 profile.render.renderer_glob 取最新）')
    ap.add_argument('--prune-cache', action='store_true', help='清缓存旧条目（只删本工具命名的缓存文件）；不给 --docx 时只清理')
    ap.add_argument('--keep', type=int, default=3, help='--prune-cache 时按最近使用保留的条目数（默认 3，另保留本次条目）')
    ap.add_argument('--json', action='store_true', help='把完整结果 JSON 打到标准输出')
    a = ap.parse_args(argv)
    try:
        if not a.docx:
            if not a.prune_cache or not (a.out_dir or a.cache_dir):
                ap.error('需要 --docx 与 --out-dir（只清缓存时用 --prune-cache 加 --out-dir 或 --cache-dir）')
            cd = Path(_abs(a.cache_dir)) if a.cache_dir else Path(_abs(a.out_dir)) / '.render_cache'
            WriteGuard(all_profiles(a.guard_profile)).check(cd)
            r = prune_cache(cd, a.keep)
            print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else
                  'render_book｜缓存清理：%s｜删 %d 条，释放 %.1f MB' % (r['cache_dir'], len(r['removed']), r['freed_bytes'] / 1e6))
            return 0
        if not a.out_dir:
            ap.error('需要 --out-dir')
        r = render_book(a.docx, a.out_dir, book=a.book, profile=a.profile, mode=a.mode, cache_dir=a.cache_dir,
                        no_cache=a.no_cache, key_only=a.key_only, png=a.png, pages=a.pages, dpi=a.dpi,
                        png_engine=a.png_engine, png_dir=a.png_dir, compare_pdf=a.compare_pdf,
                        fontconfig_mode=a.fontconfig_mode, fontconfig=a.fontconfig, lo_profile_mode=a.lo_profile_mode,
                        timeout=a.timeout, allow_odt_fallback=a.allow_odt_fallback, identity=a.identity, pdf_name=a.pdf_name,
                        renderer=a.renderer, fail_on_fallback=a.fail_on_fallback, fail_on_substitution=a.fail_on_substitution,
                        guard_profiles=a.guard_profile, prune_keep=a.keep if a.prune_cache else None)
    except RenderError as e:
        print('render_book 失败（退出码 %d）：%s' % (e.code, e), file=sys.stderr)
        if e.detail:
            print(json.dumps(e.detail, ensure_ascii=False, indent=1)[:6000], file=sys.stderr)
        return e.code
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    print('\n'.join(summary_lines(r)))
    return 0 if a.key_only else r['exit_code']


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(1)
