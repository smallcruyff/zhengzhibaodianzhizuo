#!/usr/bin/env python3
"""page_delta.py —— 两版 PDF “看哪几页”的统一工具（按书册配置运行，只读）。

合并了前期四套看页方案（page_diff 签名对齐、ledger_sim 看页账本、png_body_equal 正文区像素、
page_lint 版面预筛）与 pagediff 文本哈希，给出本版需要人看的页（must_review）与原因。

做什么
  1. 两个 PDF 逐页取文本签名（去空白、去页脚/页眉页码），用 difflib 做序列对齐，分出
     新增页 inserted / 文字改动页 text_changed / 文字相同页，以及旧版被删除的页。
  2. 文字相同页按 profile.pixel.policy 做像素判定：
       same_page_pixel_identical  同页号、整页像素完全一致 —— 现行规则下唯一可继承账本已看记录的类别；
       shifted_body_identical     页号不同或页脚不同、遮去页码后正文区像素一致 —— 信息类别，
                                  只有 profile.pixel.allow_content_addressed_map=true 才可继承（默认 false，待用户裁定）；
       pixel_changed              文字相同但像素不同（附原因诊断：疑亚像素位移 / 图片 / 图形 / 其他非文字变化 等，只作信息）。
     分辨率：先按 render.png_dpi（--dpi 只能调高）比全部配对页；要继承的旧页记录写了看图 dpi 且不同的，
     再按该 dpi 逐一复比，每个 dpi 都一致才算一致（像素一致与否随 dpi 变化，不单调）。
     两侧同版身份 JSON 显示渲染器、字体配置、字体文件或 PDF Producer 不一致时拒绝像素继承，只做文本层对齐。
  3. must_review（现行规则口径）= 新增页 + 文字改动页 + 像素不同页 + 这些页及删除点的相邻页 + 无法继承的页
     （错位页、账本里旧页没有有效实看记录的页、旧页有未解决问题记录的页、本版有未解决问题记录的页、未做像素判定的页）。
     没给账本或账本里没有旧版记录时，旧页未读，全部页都要看；此时另报“差异页候选”（只说明哪些页变了，
     未核旧页实看，不是现行规则口径）。
  4. 机器预筛 flags（空白页、大面积留白、页脚缺失/页码不连续、贴边/出框/压页脚、字体回退）只附在页上作候选，
     预筛不等于视觉通过。未识别书册配置时字体与页脚两项不做。
  5. 只在需要时转图：像素判定只转文字相同的配对页；联系表/单页 PNG 只转 must_review 页，不整书转 PNG。

用法
  python3 page_delta.py OLD.pdf NEW.pdf [--profile bixiu3] [--json out.json] [--out-dir DIR]
        [--old-identity 旧同版身份.json --new-identity 新同版身份.json]
        [--ledger 看页账本.json|.jsonl ...] [--ledger-out 继承记录.jsonl]
        [--context 1] [--dpi 120] [--no-pixel] [--contact-sheet] [--export-pages] [--jobs 8]
  python3 page_delta.py record --pdf 本版.pdf --pages 2-3,52-95 --viewer "wf_xxx Sonnet 12份"
        --level subagent --verdict PASS [--kind viewed|ruling] [--issue-pages 225] [--dpi 171] [--evidence 路径]
        --ledger-out 账本.jsonl
  也可 import：from page_delta import compute_delta, load_ledger, ledger_state, ranges, contact_sheets, export_pages
  （多进程用 spawn：调用方脚本须有 if __name__ == '__main__' 保护；stdin/交互环境自动退回单进程。）

看页账本（JSON 的 {"records":[...]} 或数组，或 JSONL 每行一条）
  {"pdf_sha256": "64位十六进制", "pages": [2,3] 或 "2-3,52—95", "viewer": "谁看的",
   "viewer_level": "user|main_agent|subagent|external_main|external_subagent", "kind": "viewed|ruling|inherited",
   "viewed_at": "ISO时间", "verdict": "PASS|ISSUES|FAIL", "issue_pages": [..], "dpi": 171, "evidence": "原始记录路径"}
  只接受上述等级与 kind、SHA 合法、页号可解析的记录；machine 等级、machine_check 等其他 kind、缺等级或缺 kind 的
  记录列入 ignored_records，不用于继承，也不会写进 --ledger-out。
  同一 PDF 同一页有多条记录时：
    ① 任一非 PASS 记录（verdict 不是 PASS；或该页列在 issue_pages）都挡住该页，除非有一条时间更晚（viewed_at）、
       kind 为 viewed 或 ruling、证据等级不低于它、并且页号覆盖该页的 PASS 记录；缺 viewed_at 的记录无法排先后，
       既不能解除别人的问题，自己的问题也不会被解除。像素继承来的记录（inherited）不能解除问题。
    ② 没有未解除的问题时，实际看页（viewed/ruling）优先于像素继承来的记录，其次证据等级高者、时间晚者。
  ISSUES 列了 issue_pages 时只挡这些页；ISSUES 没列、FAIL 或无法识别的 verdict 挡整条记录。
  继承只沿用原看图者与证据等级，本工具不做视觉判断，也不把机器比较结果标成已看或已核验。

只读承诺
  不修改、移动、重存任何输入 PDF/DOCX/身份/账本。输出只写到 --json / --out-dir / --ledger-out 指定位置，并且拒绝：
  输入 PDF 所在目录本身及其直接子项；任一书册的审阅入口、审阅历史目录（含子目录）；协作/交接目录（只允许
  候选/<执行者>/<批次>/<子目录>/ 之下）；非冻结书册工作区里候选批次子目录以外的位置；题库、共同资料与同步程序目录；
  项目根目录直接子项；本技能目录。冻结册（profile.frozen=true）的一切目录与账本写入一律经 frozen_guard 拒绝。

退出码
  0 正常完成（不论 must_review 多少页）；2 参数或输入文件错误（含不是 PDF、身份/账本 JSON 类型不对、页号无法解析）；
  3 输出位置不安全或冻结册拒绝写入。
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from profile_lib import load_profile, detect_profile, frozen_guard, resolve, list_profiles  # noqa: E402

import fitz  # PyMuPDF

TOOL = 'page_delta.py'
SCHEMA = 'baodian-page-delta/2'
LEDGER_SCHEMA = 'baodian-page-ledger/0.2'
WS_RE = re.compile(r'\s+')
DIG_RE = re.compile(r'\d+')
SHA_RE = re.compile(r'^[0-9a-f]{64}$')
PASS_WORDS = {'PASS', 'OK', '通过', '无问题'}
ISSUE_WORDS = {'ISSUES', 'ISSUE', '有问题'}
FAIL_WORDS = {'FAIL', 'FAILED', '不通过'}
LEVELS = ['user', 'main_agent', 'subagent', 'external_main', 'external_subagent']
LEVEL_RANK = {'user': 0, 'main_agent': 1, 'external_main': 1, 'subagent': 2, 'external_subagent': 2}
KINDS = ('viewed', 'ruling', 'inherited')
BASIS_STRICT = 'same_page_full_pixels'
BASIS_SHIFT = 'content_addressed_body_pixels'
SUBPIXEL_PT = 0.5
# 未识别书册时的通用页码行：“— 12 —”“12”“第12页”“12 / 93”
GENERIC_PN_RE = r'^\s*[-—–－]*\s*第?\s*(\d{1,4})\s*页?(?:\s*/\s*\d{1,4})?\s*[-—–－]*\s*$'
# 项目根下的受保护目录（题库、共同资料、同步程序、题库流水线）；书册配置可用 paths.protected_extra 追加
PROTECTED_DEFAULT = ['共享题库', 'DeepSeek_政治题库资料库_20260918', '2026模拟题_学生题库_按考试类型整理_20260914',
                     '公共题库预处理_方案与盘点_20260913', '02_题库与预处理', '00_共同资料', 'Claude协作同步_20260914',
                     '后勤管理/MD全库流水线_20260921']

# 配置缺省值：书册配置没写的字段用这里的值（新增字段见返回的 profile_fields_needed）
DEFAULTS = {
    'footer': {'regex': r'—\s*(\d+)\s*—', 'exempt_pages': [], 'page_offset': 0, 'continuous': True,
               'bottom_band': 0.12},
    'header': {'regex': None, 'top_band': 0.12},
    'pixel': {'policy': 'same_page_full_pixels', 'allow_content_addressed_map': False,
              'inherit_unchanged_without_ledger': False, 'subpixel_tolerance_pt': 0.0,
              'context_pages': 1, 'footer_mask_pad_pt': 2.0,
              'contact_sheet': {'cols': 4, 'rows': 3, 'thumb_dpi': 50}},
    'render': {'png_dpi': 120, 'font_fallback_allow': [], 'expected_fonts': []},
    'pagination': {'blank_threshold_ratio': 0.33, 'edge_safe_pt': 14.0, 'frame_tolerance_pt': 12.0,
                   'edge_exempt_pages': [1], 'forced_break_min_pt': None},
}

WHY_ZH = {'inserted': '新增', 'text_changed': '改文字', 'pixel_changed': '像素不同', 'context_of': '相邻',
          'adjacent_to_deleted_old': '删除点相邻', 'policy_blocked_shifted': '错位不可继承',
          'no_ledger_record': '旧页无实看记录（终审口径）', 'ledger_not_pass': '旧页有未解决问题记录',
          'ledger_issue_on_this_pdf': '本版有未解决问题记录', 'text_same_not_compared': '未做像素判定'}

CAT_ZH = {
    'inserted': '新增页', 'text_changed': '文字改动页',
    'same_page_pixel_identical': '同页号整页像素一致', 'shifted_body_identical': '错位且仅页码/页脚不同',
    'pixel_changed': '文字相同但像素不同', 'text_same_not_compared': '文字相同、未做像素判定',
    'subpixel_only': '仅亚像素字形位移（容差内，视同未变）',
}

CAUSE_ZH = {'subpixel_shift_suspect': '疑亚像素位移', 'glyph_layout_shift': '字形位移≥0.5pt',
            'glyph_style_changed': '字形样式/次序变化', 'image_changed': '图片变化', 'drawing_changed': '图形变化',
            'non_text_other': '其他非文字变化（颜色/透明度/渲染等，文字图片图形层均未见差异）'}


class InputError(ValueError):
    """输入文件或参数错误（退出码 2）。"""


class UnsafeOutput(SystemExit):
    """输出位置不安全（退出码 3）。"""


# ---------------- 小工具 ----------------

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _sha1(s):
    return hashlib.sha1(s.encode('utf-8')).hexdigest()[:16]


def ranges(nums):
    """[1,2,3,7] -> '1-3,7'"""
    nums = sorted(set(nums))
    out, i = [], 0
    while i < len(nums):
        j = i
        while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
            j += 1
        out.append(str(nums[i]) if i == j else '%d-%d' % (nums[i], nums[j]))
        i = j + 1
    return ','.join(out)


_RANGE_DASH = re.compile(r'\s*(?:[-—–－‐～~]+|至|到)\s*')


def parse_pages(spec):
    """'2-3,52—95'、'2、3；52～95' 或 [2,3] -> 排好序的正整数列表；无法解析抛 ValueError。"""
    if spec is None or spec == '':
        return []
    if isinstance(spec, (list, tuple, set)):
        out = set()
        for x in spec:
            if isinstance(x, bool):
                raise ValueError('页号不能是布尔值：%r' % (x,))
            if isinstance(x, int):
                out.add(x)
            else:
                out.update(parse_pages(str(x)))
    elif isinstance(spec, int) and not isinstance(spec, bool):
        out = {spec}
    elif isinstance(spec, str):
        out = set()
        for part in re.split(r'[,，、;；\s]+', _RANGE_DASH.sub('-', spec.strip())):
            if not part:
                continue
            if re.fullmatch(r'\d+', part):
                out.add(int(part))
            elif re.fullmatch(r'\d+-\d+', part):
                a, b = (int(x) for x in part.split('-'))
                if b < a:
                    raise ValueError('页号区间倒置：%s' % part)
                out.update(range(a, b + 1))
            else:
                raise ValueError('无法解析的页号：%r' % part)
    else:
        raise ValueError('页号类型不对：%r' % (spec,))
    if any(p < 1 for p in out):
        raise ValueError('页号必须从 1 开始')
    return sorted(out)


def _clip(s, n=24):
    """截取原文，截断处明确标注（不做归纳）。"""
    s = s.strip()
    return s if len(s) <= n else s[:n] + '…（截断）'


def _cfg(prof, sect, key):
    v = (prof or {}).get(sect, {}).get(key) if prof else None
    return DEFAULTS[sect][key] if v is None else v


def _norm_font(s):
    s = s.split('+', 1)[-1]
    return re.sub(r'[^a-z0-9]', '', s.lower())


def _parse_time(v):
    """ISO 时间 -> 时间戳；无法解析返回 None（无时区按本机时区）。"""
    if not v or not isinstance(v, str):
        return None
    s = v.strip().replace('Z', '+00:00')
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt.timestamp()


def _int_or_none(v):
    try:
        x = int(v)
    except (TypeError, ValueError):
        return None
    return x if 20 <= x <= 1200 else None


def expected_fonts(prof):
    """本册应出现的字体：typography 里所有 ea/ascii、fontconfig 别名目标、render.expected_fonts。"""
    names = set()

    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ('ea', 'ascii') and isinstance(v, str):
                    names.add(v)
                else:
                    walk(v)
    walk((prof or {}).get('typography', {}))
    names.update(((prof or {}).get('render', {}).get('fontconfig', {}) or {}).get('aliases', {}).values())
    names.update(_cfg(prof, 'render', 'expected_fonts'))
    return sorted({_norm_font(n) for n in names if n})


def _font_ok(font, exp, allow, cjk_rx):
    if cjk_rx and cjk_rx.search(font.split('+', 1)[-1]):
        return True
    f = _norm_font(font)
    if any(_norm_font(a) and _norm_font(a) in f for a in allow):
        return True
    return any(e and (e in f or f in e) for e in exp)


def check_pdf(p):
    """输入必须是能打开、至少一页的 PDF（按文件头 %PDF- 判定，不接受 DOCX 等被 MuPDF 排版的文件）。"""
    if not p or not os.path.isfile(p):
        raise InputError('输入文件不存在：%s' % p)
    with open(p, 'rb') as f:
        head = f.read(1024)
    if b'%PDF-' not in head:
        raise InputError('不是 PDF 文件（文件头没有 %%PDF-）：%s' % p)
    try:
        n = fitz.open(p).page_count
    except Exception as e:  # noqa: BLE001
        raise InputError('PDF 打不开：%s（%s）' % (p, e))
    if n < 1:
        raise InputError('PDF 没有页：%s' % p)
    return n


def _load_json_obj(pth, what):
    try:
        d = json.loads(Path(pth).read_text(encoding='utf-8'))
    except (OSError, ValueError) as e:
        raise InputError('%s读不了或不是 JSON：%s（%s）' % (what, pth, e))
    if not isinstance(d, dict):
        raise InputError('%s必须是 JSON 对象（现在是 %s）：%s' % (what, type(d).__name__, pth))
    return d


# ---------------- 并行 ----------------

def _run_pool(fn, tasks, jobs):
    """多进程执行；调用方主模块不是真实文件（stdin/交互）或进程池崩溃时自动退回单进程。"""
    import __main__
    mf = getattr(__main__, '__file__', None)
    if jobs > 1 and (not mf or not os.path.exists(mf)):
        jobs = 1
    if jobs <= 1:
        return [fn(t) for t in tasks]
    from concurrent.futures.process import BrokenProcessPool
    try:
        with ProcessPoolExecutor(jobs) as ex:
            return list(ex.map(fn, tasks))
    except BrokenProcessPool:
        return [fn(t) for t in tasks]


# ---------------- 逐页分析（子进程） ----------------

def _pn_match(rx, st):
    """整行基本就是页码时返回页码数字（可能为 None），否则返回 False。"""
    m = rx.search(st)
    if not m or len(WS_RE.sub('', st)) > len(WS_RE.sub('', m.group(0))) + 2:
        return False
    return next((int(g) for g in m.groups() if g and g.isdigit()), None)


def _analyze_chunk(args):
    path, lo, hi, footer_regex, foot_y, header_regex, head_y, exp, allow, cjk_re = args
    foot_re = re.compile(footer_regex)
    head_re = re.compile(header_regex) if header_regex else None
    cjk_rx = re.compile(cjk_re) if cjk_re else None
    doc = fitz.open(path)
    flags = fitz.TEXTFLAGS_DICT & ~fitz.TEXT_PRESERVE_IMAGES
    out = []
    for i in range(lo, hi):
        pg = doc[i]
        W, H = pg.rect.width, pg.rect.height
        d = pg.get_text('dict', flags=flags)
        text_parts, style_parts, mlines, rlines, lines = [], [], [], [], []
        footer, header, pn_boxes = None, None, []
        fonts_bad = {}
        unmapped = 0
        for b in d.get('blocks', []):
            if b.get('type') != 0:
                continue
            for ln in b.get('lines', []):
                spans = ln.get('spans', [])
                txt = ''.join(sp.get('text', '') for sp in spans)
                st = txt.strip()
                if not st:
                    continue
                bb = ln['bbox']
                num = _pn_match(foot_re, st) if bb[1] > foot_y * H else False
                where = 'footer'
                if num is False and head_re is not None and bb[3] < head_y * H:
                    num, where = _pn_match(head_re, st), 'header'
                if num is not False:
                    # 页码行：翻页位移时必然变化，不进文本签名；像素比对时遮去
                    fb = [round(v, 2) for v in bb]
                    pn_boxes.append(fb)
                    rec = {'text': st, 'num': num, 'bbox': fb}
                    if where == 'footer' and footer is None:
                        footer = rec
                    elif where == 'header' and header is None:
                        header = rec
                    continue
                text_parts.append(txt)
                raw = WS_RE.sub('', txt)
                rlines.append(raw)
                mlines.append(DIG_RE.sub('#', raw))
                size = max((sp.get('size', 0) for sp in spans), default=0)
                lines.append((round(bb[0], 2), round(bb[1], 2), round(bb[2], 2), round(bb[3], 2), size, st))
                style_parts.append('L%s' % (tuple(round(v) for v in bb),))
                for sp in spans:
                    style_parts.append('%s|%.1f|%s|%s' % (sp.get('font', ''), sp.get('size', 0),
                                                          sp.get('color', 0), sp.get('flags', 0)))
                    t = sp.get('text', '')
                    unmapped += t.count('�')
                    fn = sp.get('font', '')
                    if t.strip() and not _font_ok(fn, exp, allow, cjk_rx):
                        rec = fonts_bad.setdefault(fn, [0, Counter(), 0, t.strip()])
                        rec[0] += len(t.strip())
                        rec[1].update(c for c in t if not c.isspace())
                        rec[2] += sum(1 for c in t if '㐀' <= c <= '鿿')
        images = []
        try:
            for im in pg.get_image_info(hashes=True):
                dg = im.get('digest')
                dg = dg.hex() if isinstance(dg, (bytes, bytearray)) else str(dg)
                ib = [round(v, 2) for v in im.get('bbox', (0, 0, 0, 0))]
                images.append(ib)
                style_parts.append('I%s|%s' % (dg, tuple(round(v) for v in ib)))
        except Exception:  # noqa: BLE001
            pass
        draws = []
        try:
            acc = []
            for g in pg.get_drawings():
                r = g.get('rect')
                if r is None:
                    continue
                draws.append([round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)])
                acc.append('%s|%s|%s' % (tuple(round(v) for v in r), g.get('color'), g.get('fill')))
            style_parts.append('D%d|%s' % (len(acc), _sha1(';'.join(acc))))
        except Exception:  # noqa: BLE001
            pass
        text = WS_RE.sub('', ''.join(text_parts))
        tsig = _sha1(text)
        out.append({
            'n': i + 1, 'w': round(W, 2), 'h': round(H, 2), 'tsig': tsig,
            'ssig': _sha1(tsig + '\n'.join(style_parts)), 'nchar': len(text),
            'mlines': [x for x in mlines if x], 'rlines': [x for x in rlines if x], 'lines': lines,
            'images': images, 'draws': draws, 'footer': footer, 'header': header, 'pn_boxes': pn_boxes,
            'unmapped': unmapped,
            # char_set_by_freq 是按出现次数排的字符集合，不是原文；first_run 才是原文截取
            'fonts_bad': {k: {'chars': v[0], 'cjk_chars': v[2], 'first_run': _clip(v[3], 16),
                              'char_set_by_freq': ''.join(c for c, _ in v[1].most_common(12))}
                          for k, v in fonts_bad.items()},
        })
    return out


def analyze_pdfs(paths, cfg, jobs):
    """paths: [old, new]；返回 ([旧页信息], [新页信息]), [页数]，并行分块。"""
    tasks, owner = [], []
    counts = []
    for k, p in enumerate(paths):
        n = fitz.open(p).page_count
        counts.append(n)
        step = max(8, -(-n // (jobs * 2)))
        for lo in range(0, n, step):
            tasks.append((p, lo, min(n, lo + step), cfg['footer_regex'], cfg['footer_y'], cfg['header_regex'],
                          cfg['header_y'], cfg['expected_fonts'], cfg['font_allow'], cfg['cjk_regex']))
            owner.append(k)
    parts = _run_pool(_analyze_chunk, tasks, jobs)
    res = [[] for _ in paths]
    for k, part in zip(owner, parts):
        res[k].extend(part)
    for r in res:
        r.sort(key=lambda x: x['n'])
    return res, counts


# ---------------- 像素判定（子进程） ----------------

def _pix(page, dpi):
    return page.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)


def _diff_stats(pa, pb, dpi):
    from PIL import Image, ImageChops
    a = Image.frombytes('RGB', (pa.width, pa.height), pa.samples)
    b = Image.frombytes('RGB', (pb.width, pb.height), pb.samples)
    df = ImageChops.difference(a, b)
    bbox = df.getbbox()
    hist = df.convert('L').histogram()
    nz = sum(hist[1:])
    mx = max((k for k, v in enumerate(hist) if v), default=0)
    s = 72.0 / dpi
    return {'diff_pixels': nz, 'max_gray_delta': mx, 'diff_dpi': dpi,
            'diff_bbox_pt': [round(v * s, 1) for v in bbox] if bbox else None}


def _pixel_chunk(args):
    old_path, new_path, pairs, dpi = args
    od, nd = fitz.open(old_path), fitz.open(new_path)
    k = dpi / 72.0
    out = []
    for n, o, masks in pairs:
        pa, pb = _pix(od[o - 1], dpi), _pix(nd[n - 1], dpi)
        same_size = (pa.width, pa.height) == (pb.width, pb.height)
        full = same_size and pa.samples == pb.samples
        body = full
        info = {}
        if not same_size:
            info['size'] = [[pa.width, pa.height], [pb.width, pb.height]]
        elif not full:
            if masks:
                for m in masks:
                    ir = fitz.IRect(int(m[0] * k) - 1, int(m[1] * k) - 1, int(m[2] * k) + 2, int(m[3] * k) + 2)
                    pa.set_rect(ir, (255, 255, 255))
                    pb.set_rect(ir, (255, 255, 255))
                body = pa.samples == pb.samples
            if not body:
                info.update(_diff_stats(pa, pb, dpi))
        out.append((n, o, full, body, info))
    return out


def pixel_compare(old_path, new_path, pairs, dpi, jobs):
    """pairs: [(新页, 旧页, 遮罩框列表)] -> {新页: (旧页, 整页一致, 遮页码后一致, 差异信息)}"""
    if not pairs:
        return {}
    step = max(4, -(-len(pairs) // (jobs * 3)))
    tasks = [(old_path, new_path, pairs[i:i + step], dpi) for i in range(0, len(pairs), step)]
    parts = _run_pool(_pixel_chunk, tasks, jobs)
    return {n: (o, full, body, info) for part in parts for n, o, full, body, info in part}


def _in_masks(bb, masks):
    cx, cy = (bb[0] + bb[2]) / 2.0, (bb[1] + bb[3]) / 2.0
    return any(m[0] <= cx <= m[2] and m[1] <= cy <= m[3] for m in masks)


def _glyphs(page, masks=()):
    """逐字形 (字, 字体, 颜色, 字号, 基线原点)；页码遮罩框内的字形不计（页码随翻页必然不同）。"""
    out = []
    for b in page.get_text('rawdict', flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']:
        for ln in b.get('lines', []):
            for sp in ln.get('spans', []):
                for c in sp.get('chars', []):
                    if masks and _in_masks(c['bbox'], masks):
                        continue
                    out.append((c['c'], sp.get('font'), sp.get('color'), round(sp.get('size', 0), 2), c['origin']))
    return out


def _objects(page, masks=()):
    imgs, drs = [], []
    try:
        for im in page.get_image_info(hashes=True):
            dg = im.get('digest')
            dg = dg.hex() if isinstance(dg, (bytes, bytearray)) else str(dg)
            bb = tuple(im.get('bbox', (0, 0, 0, 0)))
            if not (masks and _in_masks(bb, masks)):
                imgs.append((dg, bb))
    except Exception:  # noqa: BLE001
        pass
    try:
        for g in page.get_drawings():
            r = g.get('rect')
            if masks and r is not None and _in_masks(tuple(r), masks):
                continue
            drs.append(((g.get('type'), g.get('color'), g.get('fill'), g.get('width'), g.get('fill_opacity'),
                         g.get('stroke_opacity'), g.get('even_odd')), tuple(r) if r is not None else ()))
    except Exception:  # noqa: BLE001
        pass
    return imgs, drs


def _max_delta(pairs):
    m = 0.0
    for a, b in pairs:
        if len(a) != len(b):
            return None
        for x, y in zip(a, b):
            m = max(m, abs((x or 0) - (y or 0)))
    return m


def pixel_diagnose(old_pdf, new_pdf, pairs):
    """文字相同但像素不同的页：比字形序列与坐标、图片摘要与位置、图形样式与位置，给出原因标签（只作信息，
    不改变判定）。疑亚像素位移 = 字形序列相同、有字形移动且最大位移 <0.5pt、图片与图形未变（或位移 <0.5pt）。
    pairs: [(新页, 旧页, 页码遮罩框)]，遮罩框内的对象不参与比较。"""
    od, nd = fitz.open(old_pdf), fitz.open(new_pdf)
    res = {}
    for n, o, masks in pairs:
        pa, pb = od[o - 1], nd[n - 1]
        a, b = _glyphs(pa, masks), _glyphs(pb, masks)
        same_seq = len(a) == len(b) and all(x[:4] == y[:4] for x, y in zip(a, b))
        d = {'same_glyph_style_sequence': same_seq}
        causes = []
        moved, mx = 0, 0.0
        if same_seq:
            mx = max([max(abs(x[4][0] - y[4][0]), abs(x[4][1] - y[4][1])) for x, y in zip(a, b)] + [0.0])
            moved = sum(1 for x, y in zip(a, b) if x[4] != y[4])
            d['max_glyph_shift_pt'] = round(mx, 3)
            d['glyphs_moved'] = moved
            if moved and mx >= SUBPIXEL_PT:
                causes.append('glyph_layout_shift')
        else:
            causes.append('glyph_style_changed')
        ia, da = _objects(pa, masks)
        ib, db = _objects(pb, masks)
        img_same = [x[0] for x in ia] == [x[0] for x in ib]
        img_d = _max_delta([(x[1], y[1]) for x, y in zip(ia, ib)]) if img_same else None
        drw_same = len(da) == len(db) and all(x[0] == y[0] for x, y in zip(da, db))
        drw_d = _max_delta([(x[1], y[1]) for x, y in zip(da, db)]) if drw_same else None
        d['images'] = {'old': len(ia), 'new': len(ib), 'same_digests': img_same,
                       'max_shift_pt': None if img_d is None else round(img_d, 3)}
        d['drawings'] = {'old': len(da), 'new': len(db), 'same_styles': drw_same,
                         'max_shift_pt': None if drw_d is None else round(drw_d, 3)}
        if img_d is None or img_d >= SUBPIXEL_PT:
            causes.append('image_changed')
        if drw_d is None or drw_d >= SUBPIXEL_PT:
            causes.append('drawing_changed')
        if not causes and same_seq and moved and 0 < mx < SUBPIXEL_PT:
            causes = ['subpixel_shift_suspect']
        elif not causes:
            causes = ['non_text_other']
        d['causes'] = causes
        res[n] = d
    return res


# ---------------- 同版身份 ----------------

def _renderer_version(path):
    m = re.search(r'/documents/(\d+\.\d+\.\d+)/', str(path or ''))
    return m.group(1) if m else None


def check_identity(old_pdf, new_pdf, old_sha, new_sha, old_id_path, new_id_path):
    """返回 {status, allowed, comparisons, notes}。不一致 => 拒绝像素继承；缺字段 => 注明未核。"""
    comps, notes = [], []
    prod = []
    for p in (old_pdf, new_pdf):
        try:
            prod.append(fitz.open(p).metadata.get('producer'))
        except Exception:  # noqa: BLE001
            prod.append(None)
    comps.append({'field': 'pdf_producer', 'old': prod[0], 'new': prod[1], 'equal': prod[0] == prod[1]})
    res = {'old_identity': old_id_path, 'new_identity': new_id_path, 'comparisons': comps}
    if not old_id_path and not new_id_path:
        res['status'] = 'not_provided'
        notes.append('未提供同版身份：渲染器与字体配置是否一致未核，只比对了 PDF Producer。')
    elif not (old_id_path and new_id_path):
        res['status'] = 'one_side_only'
        notes.append('只提供了一侧同版身份，无法比对渲染环境。')
    else:
        ids = []
        for pth, sha, side in ((old_id_path, old_sha, '旧'), (new_id_path, new_sha, '新')):
            d = _load_json_obj(pth, '%s版同版身份' % side)
            if d.get('pdf_sha256') and str(d['pdf_sha256']).lower() != sha:
                comps.append({'field': 'identity_pdf_sha256(%s)' % side, 'old': str(d['pdf_sha256'])[:16],
                              'new': sha[:16], 'equal': False})
                notes.append('%s版同版身份记录的 pdf_sha256 与实际 PDF 不符，身份不属于这个文件。' % side)
            ids.append(d)
        a, b = ids
        va = a.get('renderer_version') or _renderer_version(a.get('renderer'))
        vb = b.get('renderer_version') or _renderer_version(b.get('renderer'))
        fields = [('renderer_sha256', a.get('renderer_sha256'), b.get('renderer_sha256')),
                  ('renderer_version', va, vb),
                  ('soffice_version', a.get('soffice_version'), b.get('soffice_version')),
                  ('env_sha256', a.get('env_sha256'), b.get('env_sha256')),
                  ('fontconfig_sha256', a.get('fontconfig_sha256'), b.get('fontconfig_sha256')),
                  ('font_files_sha256', a.get('font_files_sha256'), b.get('font_files_sha256'))]
        missing = []
        for f, x, y in fields:
            if x is None or y is None:
                if f in ('renderer_version', 'fontconfig_sha256') or x or y:
                    missing.append(f)
                continue
            comps.append({'field': f, 'old': x, 'new': y, 'equal': x == y})
        if missing:
            notes.append('同版身份缺字段，未核：%s' % '、'.join(missing))
        res['unverified_fields'] = missing
        res['status'] = 'partial' if missing else 'consistent'
    bad = [c for c in comps if not c['equal']]
    if bad:
        res['status'] = 'inconsistent'
        notes.append('不一致：%s —— 拒绝像素继承，只做文本层对齐。' % '、'.join(c['field'] for c in bad))
    if res['status'] in ('consistent', 'partial'):
        notes.insert(0, '一致：%s。' % '、'.join(c['field'] for c in comps if c['equal']))
    res['allowed'] = res['status'] in ('not_provided', 'consistent', 'partial')
    res['notes'] = notes
    return res


# ---------------- 看页账本 ----------------

def _norm_verdict(v):
    s = str(v or '').strip()
    u = s.upper()
    if u in PASS_WORDS or s in PASS_WORDS:
        return 'PASS'
    if u in ISSUE_WORDS or s in ISSUE_WORDS:
        return 'ISSUES'
    if u in FAIL_WORDS or s in FAIL_WORDS:
        return 'FAIL'
    return 'UNKNOWN'


def _validate_record(r, allow_shift):
    """返回 (忽略原因, None) 或 (None, 规范化记录)。"""
    if not isinstance(r, dict):
        return '不是 JSON 对象', None
    lv = r.get('viewer_level')
    if lv not in LEVELS:
        return ('缺 viewer_level' if not lv else 'viewer_level=%s 不是实际看页等级（只认 %s）' % (lv, '/'.join(LEVELS))), None
    kd = r.get('kind')
    if kd not in KINDS:
        return ('缺 kind' if not kd else 'kind=%s 不是实际看页（只认 %s）' % (kd, '/'.join(KINDS))), None
    sha = str(r.get('pdf_sha256') or '').strip().lower()
    if not SHA_RE.match(sha):
        return 'pdf_sha256 不是 64 位十六进制', None
    try:
        pages = parse_pages(r.get('pages'))
        iss = set(parse_pages(r.get('issue_pages')))
    except ValueError as e:
        return '页号无法解析：%s' % e, None
    if not pages:
        return '没有页号', None
    if kd == 'inherited':
        basis = str(r.get('basis') or '')
        if basis != BASIS_STRICT and not (allow_shift and basis.startswith(BASIS_SHIFT)):
            return '继承依据 %s 不被现行规则承认' % (basis or '缺失'), None
    verdict = _norm_verdict(r.get('verdict'))
    rec = dict(r)
    rec.update(pdf_sha256=sha, _pages=pages, _issue_pages=iss, _verdict=verdict, _t=_parse_time(r.get('viewed_at')),
               _dpi=_int_or_none(r.get('dpi')), _ok=verdict == 'PASS' or (verdict == 'ISSUES' and bool(iss)))
    return None, rec


def load_ledger(paths, allow_shift=False, ignored=None):
    """读一个或多个账本文件，返回有效记录列表（每条带 _src/_rid 等）。无效记录追加到 ignored（列表）并附原因。
    文件本身读不了或类型不对抛 InputError。"""
    recs = []
    ign = ignored if ignored is not None else []
    for p in paths or []:
        pp = Path(p).expanduser().resolve()
        try:
            raw = pp.read_text(encoding='utf-8')
        except OSError as e:
            raise InputError('账本读不了：%s（%s）' % (pp, e))
        fsha = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:12]
        items = []
        s = raw.strip()
        if s:
            try:
                d = json.loads(s)
            except json.JSONDecodeError:
                d = None
                for ln_no, line in enumerate(raw.splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        items.append((ln_no, json.loads(line)))
                    except json.JSONDecodeError as e:
                        ign.append({'record': '%s#%d' % (pp, ln_no), 'viewer': None, 'reason': 'JSON 解析失败：%s' % e})
            if d is not None:
                if isinstance(d, dict):
                    if isinstance(d.get('records'), list):
                        items = list(enumerate(d['records'], 1))
                    elif 'pdf_sha256' in d:
                        items = [(1, d)]
                    else:
                        raise InputError('账本 JSON 对象里没有 records 数组：%s' % pp)
                elif isinstance(d, list):
                    items = list(enumerate(d, 1))
                else:
                    raise InputError('账本必须是对象、数组或 JSONL（现在是 %s）：%s' % (type(d).__name__, pp))
        for k, r in items:
            rid = '%s#%d' % (pp, k)
            reason, rec = _validate_record(r, allow_shift)
            if reason:
                ign.append({'record': rid, 'viewer': r.get('viewer') if isinstance(r, dict) else None,
                            'viewer_level': r.get('viewer_level') if isinstance(r, dict) else None, 'reason': reason})
                continue
            rec['_src'] = str(pp)
            rec['_src_sha12'] = fsha
            rec['_rid'] = rid
            recs.append(rec)
    return recs


def ledger_state(recs, sha):
    """某个 PDF SHA 的页 -> {'state': 'pass'|'blocked', 'rec': 采用的记录, 'blockers': [...], 'resolved': [...]}。
    规则见模块说明：未解除的非 PASS 记录挡住该页；解除须更晚、viewed/ruling、等级不低、页号覆盖该页的 PASS 记录。"""
    per = defaultdict(list)
    for r in recs:
        if r['pdf_sha256'] != sha:
            continue
        for p in r['_pages']:
            per[p].append((r, r['_ok'] and p not in r['_issue_pages']))
    out = {}
    for p, ents in per.items():
        passes = [r for r, ok in ents if ok]
        unresolved, resolved = [], []
        for b in (r for r, ok in ents if not ok):
            fix = [r for r in passes if r['kind'] in ('viewed', 'ruling')
                   and LEVEL_RANK[r['viewer_level']] <= LEVEL_RANK[b['viewer_level']]
                   and r['_t'] is not None and b['_t'] is not None and r['_t'] > b['_t']]
            if fix:
                resolved.append((b, max(fix, key=lambda r: r['_t'])))
            else:
                unresolved.append(b)
        if unresolved:
            rec = sorted(unresolved, key=lambda r: (LEVEL_RANK[r['viewer_level']], -(r['_t'] or 0)))[0]
            out[p] = {'state': 'blocked', 'rec': rec, 'blockers': unresolved, 'resolved': resolved}
        else:
            rec = sorted(passes, key=lambda r: (1 if r['kind'] == 'inherited' else 0, LEVEL_RANK[r['viewer_level']],
                                                -(r['_t'] or 0)))[0]
            out[p] = {'state': 'pass', 'rec': rec, 'blockers': [], 'resolved': resolved}
    return out


def _rec_brief(r):
    return {'viewer': r.get('viewer'), 'viewer_level': r.get('viewer_level'), 'viewed_at': r.get('viewed_at'),
            'verdict': r.get('verdict'), 'record': r.get('_rid'), 'view_dpi': r.get('_dpi'),
            'record_kind': r.get('kind'), 'evidence': r.get('evidence'), 'origin': r.get('origin')}


def _state_brief(s):
    d = _rec_brief(s['rec'])
    if s['blockers']:
        d['unresolved_issue_records'] = [{'record': b['_rid'], 'viewer': b.get('viewer'), 'viewer_level': b['viewer_level'],
                                          'verdict': b.get('verdict'), 'viewed_at': b.get('viewed_at')}
                                         for b in s['blockers']]
    if s['resolved']:
        d['resolved_issue_records'] = [{'record': b['_rid'], 'resolved_by': f['_rid']} for b, f in s['resolved']]
    return d


# ---------------- 主流程 ----------------

def defaults_used(prof):
    """列出本次因书册配置缺字段而用了代码缺省值的键（供登记 profile_fields_needed）。"""
    out = []
    for sect, kv in DEFAULTS.items():
        for k in kv:
            if (prof or {}).get(sect, {}).get(k) is None:
                out.append('%s.%s' % (sect, k))
    return out


def _config(prof, dpi=None, context=None):
    """返回 (配置, 被拒绝的放宽参数说明)。--dpi 只能调高、--context 不能低于配置值（否则不是现行规则口径）。"""
    notes = []
    png = int(_cfg(prof, 'render', 'png_dpi'))
    ctx0 = int(_cfg(prof, 'pixel', 'context_pages'))
    if dpi is not None and int(dpi) < png:
        notes.append('--dpi %d 低于 render.png_dpi %d，已按 %d 判定（不放宽）。' % (int(dpi), png, png))
    if context is not None and int(context) < ctx0:
        notes.append('--context %d 低于配置的相邻页数 %d，已按 %d（不放宽）。' % (int(context), ctx0, ctx0))
    no_prof = prof is None
    cjk = ((prof or {}).get('pdf_fonts') or {}).get('expected_cjk_regex') if prof else None
    return {
        'policy': _cfg(prof, 'pixel', 'policy'),
        'allow_shift': bool(_cfg(prof, 'pixel', 'allow_content_addressed_map')),
        # 用户2026-09-23：阶段稿里与上一版完全一样的页不用重看；终审（--final）仍要求旧页有实看记录
        'stage_inherit': bool(_cfg(prof, 'pixel', 'inherit_unchanged_without_ledger')),
        'subpixel_tol': float(_cfg(prof, 'pixel', 'subpixel_tolerance_pt') or 0.0),
        'context': max(ctx0, int(context)) if context is not None else ctx0,
        'mask_pad': float(_cfg(prof, 'pixel', 'footer_mask_pad_pt')),
        'dpi': max(png, int(dpi)) if dpi is not None else png,
        'footer_regex': GENERIC_PN_RE if no_prof else _cfg(prof, 'footer', 'regex'),
        'footer_y': 1.0 - float(_cfg(prof, 'footer', 'bottom_band')),
        'header_regex': _cfg(prof, 'header', 'regex'),
        'header_y': float(_cfg(prof, 'header', 'top_band')),
        'footer_exempt': set(_cfg(prof, 'footer', 'exempt_pages')),
        'footer_offset': int(_cfg(prof, 'footer', 'page_offset')),
        'footer_continuous': bool(_cfg(prof, 'footer', 'continuous')),
        'blank_ratio': float(_cfg(prof, 'pagination', 'blank_threshold_ratio')),
        'edge_safe': float(_cfg(prof, 'pagination', 'edge_safe_pt')),
        'frame_tol': float(_cfg(prof, 'pagination', 'frame_tolerance_pt')),
        'edge_exempt': set(_cfg(prof, 'pagination', 'edge_exempt_pages')),
        'forced_break_pt': _cfg(prof, 'pagination', 'forced_break_min_pt')
        or float(((prof or {}).get('typography', {}).get('h1') or {}).get('pt', 18)),
        'expected_fonts': expected_fonts(prof),
        'font_allow': list(_cfg(prof, 'render', 'font_fallback_allow')),
        'cjk_regex': cjk,
        'prescreen_font': not no_prof,
        'prescreen_footer': not no_prof,
    }, notes


def _align(osig, nsig):
    """difflib 对齐文本签名：返回 new->old 映射、各类页、删除点、改动段。"""
    ot = [p['tsig'] for p in osig]
    nt = [p['tsig'] for p in nsig]
    sm = difflib.SequenceMatcher(None, ot, nt, autojunk=False)
    same, changed, inserted, deleted, del_points, blocks = {}, [], [], [], [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                same[j1 + k + 1] = i1 + k + 1
        elif tag == 'delete':
            deleted.extend(range(i1 + 1, i2 + 1))
            del_points.append((j1, (i1 + 1, i2)))
        elif tag == 'insert':
            inserted.extend((n, i1) for n in range(j1 + 1, j2 + 1))
        else:
            changed.extend(range(j1 + 1, j2 + 1))
            blocks.append((i1, i2, j1, j2))
    return same, changed, inserted, deleted, del_points, blocks


def _match_old(osig, nsig, blocks, win=15):
    """文字改动页找最像的旧页（按遮数字后的行重合度，窗口内），供并排对照。"""
    res = {}
    for i1, i2, j1, j2 in blocks:
        ln = max(1, j2 - j1)
        for j in range(j1, j2):
            nl = set(nsig[j]['mlines'])
            if not nl:
                continue
            c = i1 + int((j - j1) * (i2 - i1) / ln)
            best, bo = 0.0, None
            for i in range(max(i1, c - win), min(i2, c + win + 1)):
                ol = set(osig[i]['mlines'])
                if ol:
                    r = len(nl & ol) / len(nl)
                    if r > best:
                        best, bo = r, i + 1
            if bo and best >= 0.2:
                res[j + 1] = (bo, round(best, 2))
    return res


def _doc_frame(nsig):
    """从全书统计正文框：左边 = 行起点 x 的众数，右边按左右页边距对称取（行尾标点悬挂不影响），
    上下 = 各页内容上沿中位数 / 下沿 90 分位。"""
    x0 = Counter(round(l[0] * 2) / 2 for p in nsig for l in p['lines'])
    tops, bots, fy = [], [], []
    for p in nsig:
        ys0 = [l[1] for l in p['lines']] + [b[1] for b in p['images']]
        ys1 = [l[3] for l in p['lines']] + [b[3] for b in p['images']]
        if ys0:
            tops.append(min(ys0))
            bots.append(max(ys1))
        if p['footer']:
            fy.append(p['footer']['bbox'][1])
    tops.sort()
    bots.sort()
    fy.sort()
    h = nsig[0]['h'] if nsig else 842
    return {
        'left': x0.most_common(1)[0][0] if x0 else 0,
        'right': round(nsig[0]['w'] - x0.most_common(1)[0][0], 2) if x0 else 0,
        'top': tops[len(tops) // 2] if tops else 0.08 * h,
        'bottom': bots[int(len(bots) * 0.9)] if bots else 0.92 * h,
        'footer_y0': fy[len(fy) // 2] if fy else None,
    }


def _flags(p, nxt, fr, cfg, last):
    """机器预筛：只给候选，不等于视觉通过。"""
    out = []
    n, W, H = p['n'], p['w'], p['h']
    content = [(l[0], l[1], l[2], l[3]) for l in p['lines']] + [tuple(b) for b in p['images']]
    draws = [tuple(d) for d in p['draws'] if d[2] - d[0] > 0.5 or d[3] - d[1] > 0.5]
    if not content and not draws:
        out.append({'kind': 'blank_page'})
    else:
        bottom = max([c[3] for c in content] + [d[3] for d in draws if d[3] < (fr['footer_y0'] or H)] + [0])
        span = fr['bottom'] - fr['top']
        ratio = (fr['bottom'] - bottom) / span if span > 0 else 0
        if ratio > cfg['blank_ratio'] and not last:
            f = {'kind': 'large_blank', 'blank_ratio': round(ratio, 2)}
            if nxt and nxt['lines']:
                fl = min(nxt['lines'], key=lambda l: (l[1], l[0]))
                f['next_page_starts'] = _clip(fl[5])
                f['before_forced_break'] = fl[4] >= cfg['forced_break_pt'] - 0.5
            elif nxt:
                f['next_page_starts'] = '（下一页无文字层）'
            out.append(f)
    if cfg['prescreen_footer'] and n not in cfg['footer_exempt']:
        ft = p['footer']
        if not ft:
            out.append({'kind': 'footer_missing'})
        elif cfg['footer_continuous'] and ft['num'] is not None and ft['num'] != n + cfg['footer_offset']:
            out.append({'kind': 'footer_number_mismatch', 'found': ft['num'], 'expected': n + cfg['footer_offset']})
    if n not in cfg['edge_exempt']:
        safe, tol = cfg['edge_safe'], cfg['frame_tol']
        items = []
        objs = [('text', l[:4], l[5]) for l in p['lines']] + [('image', tuple(b), '') for b in p['images']] \
            + [('drawing', d, '') for d in draws]
        for what, bb, txt in objs:
            why = []
            if bb[0] < -0.5 or bb[1] < -0.5 or bb[2] > W + 0.5 or bb[3] > H + 0.5:
                why.append('off_page')
            elif bb[0] < safe or bb[1] < safe or bb[2] > W - safe or bb[3] > H - safe:
                why.append('near_edge')
            if fr['right'] and (bb[0] < fr['left'] - tol or bb[2] > fr['right'] + tol):
                why.append('beyond_frame')
            if fr['footer_y0'] and bb[3] > fr['footer_y0'] - 1 and bb[1] < fr['footer_y0'] + 12:
                why.append('into_footer')
            if why:
                items.append({'what': what, 'why': why, 'bbox_pt': [round(v, 1) for v in bb],
                              'text': _clip(txt, 16) if txt else ''})
        if items:
            out.append({'kind': 'edge_overflow', 'count': len(items), 'items': items[:5]})
    if cfg['prescreen_font'] and (p['fonts_bad'] or p['unmapped']):
        f = {'kind': 'font_fallback', 'fonts': [dict(font=k, **v) for k, v in sorted(p['fonts_bad'].items())]}
        f['has_cjk'] = any(v['cjk_chars'] for v in p['fonts_bad'].values())
        if p['unmapped']:
            f['unmapped_glyphs'] = p['unmapped']
        out.append(f)
    return out


def _inherit(pages, shift_ok, st_old, st_new, use_ledger=True, stage=False):
    """按账本决定每页是否可继承；返回 {page: inherit dict}。
    use_ledger=False 时是“差异页候选”口径：不看账本，只按像素判定（旧页是否实看未核）。
    stage=True（阶段稿口径）时，与上一版一样的页即使没有旧页实看记录也不必重看，状态记 unchanged_from_previous；
    旧页有未解决问题记录的仍要看。"""
    res = {}
    for n, e in pages.items():
        cat, o = e['category'], e['old_page']
        if use_ledger and n in st_new:
            s = st_new[n]
            if s['state'] == 'blocked':
                st = 'ledger_issue_on_this_pdf'
            else:
                st = 'inherited_on_this_pdf' if s['rec']['kind'] == 'inherited' else 'viewed_on_this_pdf'
            res[n] = dict(status=st, **_state_brief(s))
            continue
        shifted = cat == 'shifted_body_identical' or (cat == 'subpixel_only' and n != o)
        can = cat == 'same_page_pixel_identical' or (cat == 'subpixel_only' and n == o) or (shifted and shift_ok)
        if shifted and not shift_ok:
            res[n] = {'status': 'policy_blocked_shifted'}
        elif not can:
            res[n] = {'status': 'not_applicable' if cat in ('inserted', 'text_changed') else 'not_inheritable'}
        elif not use_ledger:
            res[n] = {'status': 'delta_only_unverified'}
        else:
            s = st_old.get(o)
            if not s:
                res[n] = {'status': 'unchanged_from_previous'} if stage else {'status': 'no_ledger_record'}
            elif s['state'] == 'blocked':
                res[n] = dict(status='ledger_not_pass', from_page=o, **_state_brief(s))
            else:
                res[n] = dict(status='inherited', basis=BASIS_STRICT if cat == 'same_page_pixel_identical'
                              else BASIS_SHIFT + '(用户2026-09-23授权)', from_page=o, pixel_dpis=e.get('pixel_dpis'),
                              **_state_brief(s))
    return res


def _must(pages, inh, affected, context_of, del_adj):
    must = {}
    for n, e in pages.items():
        st = inh[n]['status']
        if st in ('viewed_on_this_pdf', 'inherited_on_this_pdf'):
            continue
        why = []
        if e['category'] in ('inserted', 'text_changed', 'pixel_changed', 'text_same_not_compared'):
            why.append(e['category'])
        if n in context_of and n not in affected:
            why.append('context_of:%s' % ranges(context_of[n]))
        if n in del_adj and n not in affected:
            why.append('adjacent_to_deleted_old:%s' % del_adj[n])
        if st in ('policy_blocked_shifted', 'no_ledger_record', 'ledger_not_pass', 'ledger_issue_on_this_pdf'):
            why.append(st)
        if why:
            must[n] = why
    return must


def _masks(osig, nsig, n, o, pad):
    boxes = osig[o - 1]['pn_boxes'] + nsig[n - 1]['pn_boxes']
    return [(b[0] - pad, b[1] - pad, b[2] + pad, b[3] + pad) for b in boxes]


def compute_delta(old_pdf, new_pdf, prof=None, old_identity=None, new_identity=None, ledger_paths=None,
                  context=None, dpi=None, pixel=True, jobs=None, flags_on=True, final=False):
    t0 = time.time()
    tm = {}
    jobs = jobs or min(8, os.cpu_count() or 4)
    for p in (old_pdf, new_pdf):
        check_pdf(p)
    cfg, cfg_notes = _config(prof, dpi, context)
    if final:
        cfg['stage_inherit'] = False
    old_sha, new_sha = sha256_file(old_pdf), sha256_file(new_pdf)
    tm['sha256'] = round(time.time() - t0, 2)
    ident = check_identity(old_pdf, new_pdf, old_sha, new_sha, old_identity, new_identity)
    ignored = []
    recs = load_ledger(ledger_paths, cfg['allow_shift'], ignored)
    st_old, st_new = ledger_state(recs, old_sha), ledger_state(recs, new_sha)

    t1 = time.time()
    (osig, nsig), counts = analyze_pdfs([old_pdf, new_pdf], cfg, jobs)
    tm['page_signatures'] = round(time.time() - t1, 2)

    same, changed, inserted, deleted, del_points, blocks = _align(osig, nsig)
    old_match = _match_old(osig, nsig, blocks)
    old_lines = Counter(l for p in osig for l in p['mlines'])
    old_raw = Counter(l for p in osig for l in p['rlines'])
    new_lines = set(l for p in nsig for l in p['mlines'])
    missing_by_old = {p['n']: sum(1 for l in p['mlines'] if l not in new_lines) for p in osig}
    net_ins = sum(max(0, (j2 - j1) - (i2 - i1)) for i1, i2, j1, j2 in blocks)
    net_del = sum(max(0, (i2 - i1) - (j2 - j1)) for i1, i2, j1, j2 in blocks)

    pages = {}
    for n, o in same.items():
        pages[n] = {'page': n, 'old_page': o, 'category': 'text_same_not_compared', 'reasons': []}
        if osig[o - 1]['ssig'] != nsig[n - 1]['ssig']:
            pages[n]['reasons'].append('style_signature_differs')
    for n in changed:
        m = old_match.get(n)
        nov = sum(1 for l in nsig[n - 1]['mlines'] if l not in old_lines)
        nov_raw = sum(1 for l in nsig[n - 1]['rlines'] if l not in old_raw)
        lost = missing_by_old.get(m[0], 0) if m else 0
        rs = ['novel_lines:%d' % nov] if nov else ['no_unseen_line_after_digit_mask']
        if not nov and nov_raw:
            rs.append('digit_changed_lines:%d(可能是编号，也可能是分值/年份)' % nov_raw)
        if lost:
            rs.append('old_lines_missing:%d' % lost)
        pages[n] = {'page': n, 'old_page': m[0] if m else None, 'category': 'text_changed', 'reasons': rs,
                    'novel_lines': nov, 'novel_lines_raw': nov_raw, 'old_lines_missing': lost}
        if m:
            pages[n]['old_match_ratio'] = m[1]
    for n, i1 in inserted:
        pages[n] = {'page': n, 'old_page': None, 'category': 'inserted', 'reasons': ['after_old_page:%d' % i1]}
    matched_old = {e['old_page'] for e in pages.values() if e.get('old_page')}
    old_unmatched_missing = sorted(o for o, k in missing_by_old.items() if k and o not in matched_old)

    # 像素判定：只转文字相同的配对页；先按基础 dpi，再按要继承的旧页记录的看图 dpi 复比
    t2 = time.time()
    do_pixel = pixel and ident['allowed']
    pix_pairs = 0
    dpis_used = []
    if do_pixel:
        pad = cfg['mask_pad']
        mask = {n: _masks(osig, nsig, n, o, pad) for n, o in same.items()}
        pix = pixel_compare(old_pdf, new_pdf, [(n, o, mask[n]) for n, o in sorted(same.items())], cfg['dpi'], jobs)
        pix_pairs = len(pix)
        dpis_used.append(cfg['dpi'])
        for n, (o, full, body, info) in pix.items():
            e = pages[n]
            e['pixel_dpis'] = [cfg['dpi']]
            if full and n == o:
                e['category'] = 'same_page_pixel_identical'
            elif body:
                e['category'] = 'shifted_body_identical'
                e['reasons'].append('page_index_differs' if n != o else 'footer_differs_same_index')
            else:
                e['category'] = 'pixel_changed'
                e['pixel'] = info
        extra = defaultdict(list)
        for n, e in pages.items():
            if e['category'] not in ('same_page_pixel_identical', 'shifted_body_identical') or n in st_new:
                continue
            so = st_old.get(e['old_page'])
            d = so['rec']['_dpi'] if so and so['state'] == 'pass' else None
            if d and d != cfg['dpi']:
                extra[d].append((n, e['old_page'], mask[n]))
        for d, prs in sorted(extra.items()):
            dpis_used.append(d)
            for n, (o, full, body, info) in pixel_compare(old_pdf, new_pdf, prs, d, jobs).items():
                e = pages[n]
                e['pixel_dpis'].append(d)
                ok = full if e['category'] == 'same_page_pixel_identical' else body
                if not ok:
                    e['category'] = 'pixel_changed'
                    e['pixel'] = dict(info, differs_only_at_view_dpi=d)
                    e['reasons'].append('identical_at_%ddpi_but_differs_at_view_dpi_%d' % (cfg['dpi'], d))
        # 同页号的页码不该变，不遮；错位页的页码必然不同，诊断时遮去
        pc = [(n, e['old_page'], mask[n] if n != e['old_page'] else ()) for n, e in pages.items()
              if e['category'] == 'pixel_changed']
        for n, g in pixel_diagnose(old_pdf, new_pdf, pc).items():
            pages[n]['pixel'].update(g)
            pages[n]['reasons'].extend('%s(诊断)' % c for c in g['causes'])
            # 只有字形位移且在容差内（文字、图片、图形都没变）：视同未变
            if (cfg['subpixel_tol'] > 0 and g['causes'] == ['subpixel_shift_suspect']
                    and (g.get('max_glyph_shift_pt') or 0) < cfg['subpixel_tol']):
                pages[n]['category'] = 'subpixel_only'
                pages[n]['reasons'].append('subpixel_within_%.2fpt' % cfg['subpixel_tol'])
    else:
        reason = 'pixel_disabled_by_option' if not pixel else 'pixel_refused_identity_%s' % ident['status']
        for n in same:
            pages[n]['reasons'].append(reason)
    tm['pixel'] = round(time.time() - t2, 2)

    # 受影响页与相邻页
    N = len(nsig)
    affected = {n for n, e in pages.items() if e['category'] in ('inserted', 'text_changed', 'pixel_changed')}
    context_of = defaultdict(set)
    for a in affected:
        for q in range(a - cfg['context'], a + cfg['context'] + 1):
            if 1 <= q <= N and q != a:
                context_of[q].add(a)
    del_adj = {}
    for j1, (d0, d1) in del_points:
        for q in (j1, j1 + 1):
            if 1 <= q <= N:
                del_adj[q] = ranges(range(d0, d1 + 1))
                pages[q]['reasons'].append('adjacent_to_deleted_old:%s' % del_adj[q])

    inh = _inherit(pages, cfg['allow_shift'], st_old, st_new, stage=cfg['stage_inherit'])
    must = _must(pages, inh, affected, context_of, del_adj)
    must_alt = _must(pages, _inherit(pages, True, st_old, st_new, stage=cfg['stage_inherit']),
                     affected, context_of, del_adj)
    inh_d = _inherit(pages, cfg['allow_shift'], {}, {}, use_ledger=False)
    must_d = _must(pages, inh_d, affected, context_of, del_adj)
    must_d_alt = _must(pages, _inherit(pages, True, {}, {}, use_ledger=False), affected, context_of, del_adj)
    # 只按文本层（像素被拒时的参考口径）：新增+改文字+其相邻+删除点相邻
    t_aff = {n for n, e in pages.items() if e['category'] in ('inserted', 'text_changed')}
    text_only = set(t_aff) | set(del_adj)
    for a_ in t_aff:
        text_only.update(q for q in range(a_ - cfg['context'], a_ + cfg['context'] + 1) if 1 <= q <= N)
    text_only = sorted(text_only)

    # 机器预筛
    t3 = time.time()
    frame = _doc_frame(nsig)
    for n, e in pages.items():
        e['flags'] = _flags(nsig[n - 1], nsig[n] if n < N else None, frame, cfg, n == N) if flags_on else []
    tm['prescreen'] = round(time.time() - t3, 2)

    for n, e in pages.items():
        e['must_review'] = n in must
        e['must_review_why'] = must.get(n, [])
        e['inherit'] = inh[n]
        e['delta_candidate'] = n in must_d

    cat_count = Counter(e['category'] for e in pages.values())
    ctx_words = ('context_of', 'adjacent_to_deleted_old')
    ctx_only_inh = [n for n, ws in must.items() if all(w.startswith(ctx_words) for w in ws)
                    and inh[n]['status'] == 'inherited']
    ctx_only_d = [n for n, ws in must_d.items() if all(w.startswith(ctx_words) for w in ws)
                  and inh_d[n]['status'] == 'delta_only_unverified']
    why_count = Counter(w.split(':')[0] for ws in must.values() for w in ws)
    inh_levels = Counter(v.get('viewer_level') for v in inh.values() if v['status'] == 'inherited')
    viewed_levels = Counter(v.get('viewer_level') for v in inh.values() if v['status'] == 'viewed_on_this_pdf')
    inh_here = Counter(v.get('viewer_level') for v in inh.values() if v['status'] == 'inherited_on_this_pdf')
    status_count = Counter(v['status'] for v in inh.values())
    cause_count = Counter(c for e in pages.values() if e['category'] == 'pixel_changed'
                          for c in e.get('pixel', {}).get('causes', []))
    non_text = sum(1 for e in pages.values() if e['category'] == 'pixel_changed' and
                   set(e.get('pixel', {}).get('causes', [])) & {'image_changed', 'drawing_changed', 'non_text_other'})
    flag_pages = defaultdict(list)
    for n, e in sorted(pages.items()):
        for f in e['flags']:
            flag_pages[f['kind']].append(n)
    must_pages = sorted(must)
    cjk_fb = [n for n, e in sorted(pages.items()) for f in e['flags'] if f['kind'] == 'font_fallback' and f.get('has_cjk')]
    if cjk_fb:
        flag_pages['font_fallback_cjk'] = cjk_fb
    flag_in_must = {k: len([p for p in v if p in must]) for k, v in flag_pages.items()}
    # 去重页集合：每页恰属其一
    sets = {'must_review': must_pages,
            'viewed_on_this_pdf': sorted(n for n, v in inh.items() if v['status'] == 'viewed_on_this_pdf'),
            'inherited_on_this_pdf': sorted(n for n, v in inh.items() if v['status'] == 'inherited_on_this_pdf'),
            'inherited_not_in_must': sorted(n for n, v in inh.items() if v['status'] == 'inherited' and n not in must),
            # 阶段稿口径：与上一版一样、没有实看记录也不重看的页
            'unchanged_from_previous_not_in_must': sorted(n for n, v in inh.items()
                                                          if v['status'] == 'unchanged_from_previous' and n not in must)}
    covered = set().union(*[set(v) for v in sets.values()])
    if len(covered) != N or sum(len(v) for v in sets.values()) != N:
        raise RuntimeError('内部错误：页集合没有覆盖全书或有重叠（%d/%d）' % (len(covered), N))
    no_old_records = not any(r['pdf_sha256'] == old_sha for r in recs)

    res = {
        'tool': TOOL, 'schema': SCHEMA, 'generated_at': datetime.now().astimezone().isoformat(timespec='seconds'),
        'profile': {'book_id': (prof or {}).get('book_id'), 'title': (prof or {}).get('title'),
                    'frozen': bool((prof or {}).get('frozen')), 'path': (prof or {}).get('_profile_path'),
                    'recognized': prof is not None},
        'config': {k: (sorted(v) if isinstance(v, set) else v) for k, v in cfg.items()},
        'config_defaults_used': defaults_used(prof),
        'config_overrides_refused': cfg_notes,
        'old': {'path': str(old_pdf), 'sha256': old_sha, 'pages': counts[0]},
        'new': {'path': str(new_pdf), 'sha256': new_sha, 'pages': counts[1]},
        'identity': ident,
        'ledger': {'files': [str(p) for p in (ledger_paths or [])], 'valid_records': len(recs),
                   'ignored_records': ignored,
                   'records_without_viewed_at': len([r for r in recs if r['_t'] is None]),
                   'records_unknown_verdict': len([r for r in recs if r['_verdict'] == 'UNKNOWN']),
                   'old_pdf_pages_recorded': len(st_old), 'new_pdf_pages_recorded': len(st_new),
                   'old_pdf_pages_blocked': ranges(p for p, s in st_old.items() if s['state'] == 'blocked'),
                   'new_pdf_pages_blocked': ranges(p for p, s in st_new.items() if s['state'] == 'blocked'),
                   'view_dpi_in_records': sorted({r['_dpi'] for r in recs if r['_dpi']
                                                  and r['pdf_sha256'] in (old_sha, new_sha)}),
                   'no_old_pdf_records': no_old_records},
        'pixel': {'compared': do_pixel, 'dpi': cfg['dpi'] if do_pixel else None, 'dpis_used': dpis_used,
                  'dpi_max': max(dpis_used) if dpis_used else None, 'pairs': pix_pairs,
                  'rasterizer': 'PyMuPDF %s' % fitz.VersionBind, 'policy': cfg['policy'],
                  'allow_content_addressed_map': cfg['allow_shift'], 'subpixel_tolerance_pt': cfg['subpixel_tol'],
                  'mode': 'stage' if cfg['stage_inherit'] else 'final'},
        'counts': {'new_pages': N, 'old_pages': len(osig), 'text_same': len(same), 'text_changed': len(changed),
                   'inserted': len(inserted), 'inserted_net_in_changed_blocks': net_ins,
                   'deleted_old': len(deleted), 'deleted_net_in_changed_blocks': net_del,
                   'by_category': dict(cat_count), 'inherit_status': dict(status_count),
                   'must_review': len(must_pages), 'must_review_by_reason': dict(why_count),
                   'delta_candidates': len(must_d),
                   'context_only_but_pixel_inheritable': len(ctx_only_inh),
                   'delta_context_only_pixel_identical': len(ctx_only_d),
                   'pixel_changed_by_cause': dict(cause_count),
                   'pixel_changed_subpixel_suspect': cause_count.get('subpixel_shift_suspect', 0),
                   'pixel_changed_non_text': non_text,
                   'inherited_by_level': dict(inh_levels), 'viewed_on_this_pdf_by_level': dict(viewed_levels),
                   'inherited_on_this_pdf_by_level': dict(inh_here),
                   'text_changed_with_novel_lines': sum(1 for e in pages.values() if e.get('novel_lines')),
                   'text_changed_no_unseen_line_after_digit_mask': sum(
                       1 for e in pages.values() if e['category'] == 'text_changed' and not e.get('novel_lines')),
                   'text_changed_digit_changed_only': sum(
                       1 for e in pages.values() if e['category'] == 'text_changed' and not e.get('novel_lines')
                       and e.get('novel_lines_raw')),
                   'text_changed_with_old_lines_missing': sum(1 for e in pages.values() if e.get('old_lines_missing')),
                   'old_lines_missing_total': sum(missing_by_old.values()),
                   'old_pages_with_missing_lines_unmatched': len(old_unmatched_missing)},
        'must_review': must_pages, 'must_review_ranges': ranges(must_pages),
        'page_sets': {k: ranges(v) for k, v in sets.items()},
        'page_set_counts': {k: len(v) for k, v in sets.items()},
        'delta_candidates': {
            'count': len(must_d), 'ranges': ranges(must_d),
            'note': '差异页候选：新增/改文字/像素不同及其相邻页、错位页（按现行规则不可继承）；不看账本、未核旧页实看，'
                    '不是现行规则口径，只用于和历史“变化页＋相邻页”数字对照。'},
        'text_layer_review_ranges': ranges(text_only), 'text_layer_review_count': len(text_only),
        'if_content_addressed_allowed': {
            'must_review': len(must_alt), 'must_review_ranges': ranges(must_alt),
            'delta_candidates': len(must_d_alt), 'delta_candidates_ranges': ranges(must_d_alt),
            'note': '仅供用户裁定参考：若把 profile.pixel.allow_content_addressed_map 设为 true（错位但正文区像素一致也可继承），'
                    '现行账本口径与差异页候选分别会是这两个数；当前规则未启用。'},
        'deleted_old_pages': ranges(deleted),
        'old_pages_with_missing_lines_unmatched': ranges(old_unmatched_missing),
        'flags': {'pages_by_kind': {k: ranges(v) for k, v in flag_pages.items()},
                  'count_by_kind': {k: len(v) for k, v in flag_pages.items()},
                  'count_in_must_review': flag_in_must, 'frame_pt': frame,
                  'font_and_footer_prescreen': cfg['prescreen_font']},
        'pages': [pages[n] for n in sorted(pages)],
        'notes': [
            '判定规则：现行 same_page_full_pixels（同页号、整页像素完全一致、零容差，且在基础 dpi 与被继承记录的看图 dpi '
            '下都一致）并且旧页有有效实看记录、没有未解决问题记录，才可继承；shifted_body_identical 只作信息类别，默认不可继承。',
            '账本优先级：未解除的非 PASS 记录挡住该页；只有更晚、kind 为 viewed/ruling、证据等级不低、页号覆盖该页的 PASS '
            '记录才能解除；像素继承来的记录不能解除问题；缺 viewed_at 的记录不参与先后判断。实际看页优先于继承记录。',
            '继承只沿用原看图者与证据等级（viewer_level 原样保留）；本工具不做视觉判断，机器比对结果不等于已看，也不等于已核验。',
            '没有旧版实看记录的页一律列入 must_review（旧页未读须重看）；“差异页候选”只说明哪些页变了，不是现行规则口径。',
            'flags 是机器预筛候选，预筛不等于视觉通过；预筛没有命中也不代表版面没有问题。',
            '本工具只做机械层比对；全部通过也只说明机械层没有回退，不代表视觉或教学内容已审。',
            '像素不同页附差异统计与原因标签（疑亚像素位移、图片/图形/其他非文字变化等），仅供判断；是否设容差须用户裁定，脚本不放宽。',
            '文字改动页的“遮数字后无未见行”不等于只改了编号：分值、年份等数字改动也会落在这一类；另列旧页在新版找不到的'
            '排版行数（按行比，删改和重新折行都会计入，只作提示）。',
        ] + (['未识别书册配置：字体回退与页脚两项预筛不做，页码行按通用规则识别。'] if prof is None else [])
        + cfg_notes + ident['notes'],
        'seconds': dict(tm, total=round(time.time() - t0, 2)),
    }
    res['summary_zh'] = summary_zh(res)
    return res


def summary_zh(r):
    c = r['counts']
    bc = c['by_category']
    L = []
    if not r['profile']['recognized']:
        L.append('未识别书册配置，预筛不可用（字体回退、页脚两项未做；空白/留白/贴边为通用几何检查，仅供参考）。')
    s = '新版 %d 页（旧版 %d 页，净变化 %+d）：文字改动 %d 页' % (
        c['new_pages'], c['old_pages'], c['new_pages'] - c['old_pages'], c['text_changed'])
    if c['text_changed']:
        s += '（含未见新行 %d；遮数字后无未见行 %d，其中 %d 页有数字改动——可能是编号，也可能是分值/年份；' \
             '%d 页对应旧页有排版行在新版找不到——删改或改动后重新折行都会造成）' % (
                 c['text_changed_with_novel_lines'], c['text_changed_no_unseen_line_after_digit_mask'],
                 c['text_changed_digit_changed_only'], c['text_changed_with_old_lines_missing'])
    s += '；文字相同 %d 页。' % c['text_same']
    if c['inserted'] or c['deleted_old'] or c['inserted_net_in_changed_blocks'] or c['deleted_net_in_changed_blocks']:
        s += '对齐结果：整段插入 %d 页、整段删除 %d 页；改动段内新版多出 %d 页、旧版多出 %d 页（大段移动时这两个数会同时偏大）。' % (
            c['inserted'], c['deleted_old'], c['inserted_net_in_changed_blocks'], c['deleted_net_in_changed_blocks'])
    if c['old_pages_with_missing_lines_unmatched']:
        s += '旧版另有 %d 页有排版行在新版找不到且没有对应新页（删改、大段移动后重新折行都会造成）：%s。' % (
            c['old_pages_with_missing_lines_unmatched'], r['old_pages_with_missing_lines_unmatched'])
    L.append(s)
    if r['pixel']['compared']:
        cz = c['pixel_changed_by_cause']
        L.append('像素判定（%s dpi，亚像素容差 %.2fpt）：同页号整页一致 %d、错位且仅页码/页脚不同 %d、仅亚像素位移 %d、像素不同 %d%s。' % (
            '+'.join(str(x) for x in r['pixel']['dpis_used']), r['pixel'].get('subpixel_tolerance_pt') or 0,
            bc.get('same_page_pixel_identical', 0), bc.get('shifted_body_identical', 0), bc.get('subpixel_only', 0),
            bc.get('pixel_changed', 0),
            ('（原因诊断，一页可多项：%s；容差内的亚像素位移已另归“仅亚像素位移”，视同未变）' % '，'.join(
                '%s %d' % (CAUSE_ZH.get(k, k), v) for k, v in sorted(cz.items(), key=lambda x: -x[1]))) if cz else ''))
    else:
        L.append('未做像素判定（同版身份：%s）：文字相同页不可继承，全部计入 must_review；仅按文本层需看 %d 页：%s。' % (
            r['identity']['status'], r['text_layer_review_count'], r['text_layer_review_ranges'] or '无'))
    stage = r['pixel'].get('mode') == 'stage'
    L.append('%s must_review %d 页：%s。%s' % (
        '阶段稿口径（与上一版一样的页不重看）' if stage else '终审口径（旧页须有实看记录）',
        c['must_review'], r['must_review_ranges'] or '无',
        '（账本里没有旧版的有效实看记录：旧页未读，按终审规则须重看。）' if r['ledger']['no_old_pdf_records'] and not stage else ''))
    L.append('原因（一页可多因）：' + '，'.join('%s %d' % (WHY_ZH.get(k, k), v) for k, v in
                                        sorted(c['must_review_by_reason'].items(), key=lambda x: -x[1])) + '。'
             + ('其中 %d 页只因相邻入列、本身与旧版同页像素一致且可继承。' % c['context_only_but_pixel_inheritable']
                if c['context_only_but_pixel_inheritable'] else ''))
    L.append('差异页候选 %d 页：%s（未核旧页实看，不是现行规则口径；只说明与旧版相比哪些页变了及其相邻页）。' % (
        r['delta_candidates']['count'], r['delta_candidates']['ranges'] or '无'))
    alt = r['if_content_addressed_allowed']
    if r['pixel']['compared'] and (alt['must_review'] != c['must_review'] or alt['delta_candidates'] != c['delta_candidates']):
        L.append('若用户裁定允许错位继承（allow_content_addressed_map=true，当前未启用）：现行账本口径 %d 页，差异页候选 %d 页：%s。' % (
            alt['must_review'], alt['delta_candidates'], alt['delta_candidates_ranges'] or '无'))
    lg = r['ledger']
    if lg['files']:
        ign = Counter(x['reason'].split('：')[0].split('（')[0] for x in lg['ignored_records'])
        L.append('看页账本：有效记录 %d 条（旧版覆盖 %d 页、本版 %d 页）%s；继承按证据等级：%s；本版已看：%s；'
                 '旧版有未解决问题记录的页：%s（继承的是当时看图者的结论）。' % (
                     lg['valid_records'], lg['old_pdf_pages_recorded'], lg['new_pdf_pages_recorded'],
                     ('，忽略 %d 条（%s），不用于继承' % (len(lg['ignored_records']), '、'.join(
                         '%s %d' % (k, v) for k, v in ign.items()))) if lg['ignored_records'] else '',
                     '、'.join('%s %d 页' % (k, v) for k, v in c['inherited_by_level'].items()) or '无',
                     '、'.join('%s %d 页' % (k, v) for k, v in c['viewed_on_this_pdf_by_level'].items()) or '无',
                     lg['old_pdf_pages_blocked'] or '无'))
        if lg['records_without_viewed_at']:
            L.append('账本中 %d 条记录缺 viewed_at：无法排先后，它们不能解除问题记录，自身的问题也不会被解除。'
                     % lg['records_without_viewed_at'])
    else:
        L.append('未给看页账本：阶段稿口径下与上一版一样的页不重看；定稿、送印前的终审请加 --final 并用 record 登记实看。'
                 if stage else '未给看页账本：没有任何旧页实看证据，终审口径下 must_review 为全书；看完用 record 登记。')
    fk = r['flags']['count_by_kind']
    if fk:
        zh = {'blank_page': '空白页', 'large_blank': '大面积留白', 'footer_missing': '页脚缺失',
              'footer_number_mismatch': '页码不连续', 'edge_overflow': '贴边/出框', 'font_fallback': '字体回退',
              'font_fallback_cjk': '其中汉字落到回退字体'}
        L.append('机器预筛（全书/其中在 must_review）：' + '，'.join(
            '%s %d/%d' % (zh.get(k, k), v, r['flags']['count_in_must_review'].get(k, 0)) for k, v in fk.items())
                 + '；预筛不等于视觉通过。')
    for n in r['config_overrides_refused']:
        L.append('参数：' + n)
    for n in r['identity']['notes']:
        L.append('同版身份：' + n)
    L.append('说明：本结果只是机械层比对，全部通过也只说明机械层没有回退，不代表视觉或教学内容已审。用时 %.1f 秒。'
             % r['seconds']['total'])
    return '\n'.join(L)


# ---------------- 输出：路径安全、联系表、单页图、继承记录 ----------------

def _inside(p, b):
    return p == b or b in p.parents


def _depth_below(p, b):
    try:
        return len(p.relative_to(b).parts)
    except ValueError:
        return None


def _cand_root(q):
    pat = (q.get('paths') or {}).get('candidate_dir_pattern')
    if pat and '{' in pat:
        return resolve(q, pat.split('{', 1)[0].rstrip('/')).resolve()
    h = (q.get('paths') or {}).get('handoff')
    return (resolve(q, h).resolve().parent / '候选') if h else None


def check_out_path(path, prof=None, inputs=(), is_dir=False):
    """输出位置安全检查（对所有书册配置都查，不只本次所用配置）。不安全抛 UnsafeOutput / frozen_guard 的 SystemExit。
    is_dir=True 时按“该目录下的直接子文件”判定。"""
    p0 = Path(path).expanduser().resolve()
    p = p0 / '_' if is_dir else p0

    def refuse(msg):
        raise UnsafeOutput('拒绝写入 %s：%s' % (p0, msg))
    skill_dir = Path(__file__).resolve().parent.parent
    if _inside(p, skill_dir):
        refuse('位于技能目录 %s 之内' % skill_dir)
    for x in inputs:
        b = Path(x).expanduser().resolve().parent
        if p.parent == b:
            refuse('就在输入 PDF 所在目录 %s 里（输出请写到构建子目录或 scratch）' % b)
    profs = []
    for name in list_profiles():
        try:
            profs.append(load_profile(name))
        except Exception:  # noqa: BLE001
            continue
    if prof and prof.get('_profile_path') not in {q.get('_profile_path') for q in profs}:
        profs.append(prof)
    roots, extra = set(), []
    for q in profs:
        paths = q.get('paths') or {}
        if not paths.get('root'):
            continue
        roots.add(Path(paths['root']).expanduser().resolve())
        extra.extend(paths.get('protected_extra') or [])

        def rp(k):
            v = paths.get(k)
            return resolve(q, v).resolve() if v else None
        hd = rp('handoff').parent if paths.get('handoff') else None
        if q.get('frozen'):
            for k in ('workspace', 'aux_workspace', 'review_entry', 'review_history'):
                b = rp(k)
                if b and _inside(p, b):
                    frozen_guard(q, '在冻结册目录 %s 内写入 %s' % (b, p0))
            if hd and _inside(p, hd):
                frozen_guard(q, '在冻结册协作目录 %s 内写入 %s' % (hd, p0))
        for k, zh in (('review_entry', '审阅入口'), ('review_history', '审阅历史目录')):
            b = rp(k)
            if b and _inside(p, b):
                refuse('位于%s的%s %s 之内' % (q.get('book_id'), zh, b))
        cand = _cand_root(q)
        in_cand = bool(cand and _inside(p, cand) and (_depth_below(p, cand) or 0) >= 4)
        if hd and _inside(p, hd) and not in_cand:
            refuse('位于%s的协作/交接目录 %s（只允许写到 候选/<执行者>/<批次>/<子目录>/ 之下）' % (q.get('book_id'), hd))
        ws = rp('workspace')
        if ws and _inside(p, ws) and not in_cand:
            refuse('位于%s书册工作区 %s 的书稿旁（工作区内只允许写到候选批次的子目录之下）' % (q.get('book_id'), ws))
        if paths.get('central_state'):
            c = resolve(q, paths['central_state']).resolve().parent
            if p.parent == c:
                refuse('就在%s中央状态文件所在目录 %s' % (q.get('book_id'), c))
    for r in roots:
        for rel in PROTECTED_DEFAULT + extra:
            b = (r / rel).resolve()
            if _inside(p, b):
                refuse('位于受保护目录 %s（题库/共同资料/同步程序）' % b)
        if p.parent == r:
            refuse('就在项目根目录 %s' % r)
    return p0


def _label_font(size):
    from PIL import ImageFont
    for f in ('/System/Library/Fonts/STHeiti Medium.ttc', '/System/Library/Fonts/Hiragino Sans GB.ttc',
              '/System/Library/Fonts/Helvetica.ttc'):
        if os.path.exists(f):
            try:
                return ImageFont.truetype(f, size)
            except Exception:  # noqa: BLE001
                pass
    return ImageFont.load_default()


def contact_sheets(res, out_dir, pages=None, cols=None, rows=None, thumb_dpi=None, prof=None):
    """must_review 页联系表（缩略图，只供版面总览；逐页细看用 export_pages 的单页图）。写前做输出位置安全检查。"""
    from PIL import Image, ImageDraw
    check_out_path(out_dir, prof, [res['old']['path'], res['new']['path']], is_dir=True)
    cs = _cfg(prof, 'pixel', 'contact_sheet') if prof else DEFAULTS['pixel']['contact_sheet']
    cols, rows = cols or cs.get('cols', 4), rows or cs.get('rows', 3)
    thumb_dpi = thumb_dpi or cs.get('thumb_dpi', 50)
    pages = res['must_review'] if pages is None else pages
    info = {e['page']: e for e in res['pages']}
    doc = fitz.open(res['new']['path'])
    color = {'inserted': (200, 0, 0), 'text_changed': (220, 110, 0), 'pixel_changed': (150, 0, 180),
             'shifted_body_identical': (0, 110, 200), 'same_page_pixel_identical': (0, 140, 60),
             'text_same_not_compared': (120, 120, 120)}
    font = _label_font(max(11, thumb_dpi // 3))
    out = []
    per = cols * rows
    os.makedirs(out_dir, exist_ok=True)
    for s in range(0, len(pages), per):
        chunk = pages[s:s + per]
        thumbs = []
        for n in chunk:
            pm = doc[n - 1].get_pixmap(dpi=thumb_dpi, colorspace=fitz.csRGB, alpha=False)
            thumbs.append((n, Image.frombytes('RGB', (pm.width, pm.height), pm.samples)))
        tw = max(t.width for _, t in thumbs)
        th = max(t.height for _, t in thumbs)
        lab = font.size + 8 if hasattr(font, 'size') else 20
        cw, ch = tw + 12, th + lab + 12
        sheet = Image.new('RGB', (cw * cols, ch * ((len(chunk) - 1) // cols + 1)), (255, 255, 255))
        dr = ImageDraw.Draw(sheet)
        for k, (n, im) in enumerate(thumbs):
            x, y = (k % cols) * cw + 6, (k // cols) * ch + 6
            e = info[n]
            col = color.get(e['category'], (0, 0, 0))
            sheet.paste(im, (x, y + lab))
            dr.rectangle([x - 2, y + lab - 2, x + im.width + 1, y + lab + im.height + 1], outline=col, width=3)
            fl = ','.join(sorted({f['kind'] for f in e['flags']}))
            why = '、'.join(WHY_ZH.get(w.split(':')[0], w.split(':')[0]) + ('(%s)' % w.split(':', 1)[1] if ':' in w and
                                                                         w.startswith('context') else '')
                           for w in e['must_review_why'])
            t = 'p%d%s %s｜%s%s' % (n, ' ←旧%s' % e['old_page'] if e['old_page'] and e['old_page'] != n else '',
                                   why or '-', CAT_ZH.get(e['category'], e['category']), (' [%s]' % fl) if fl else '')
            dr.text((x, y), t, fill=col, font=font)
        fn = Path(out_dir) / ('contact_%03d_p%d-%d.png' % (s // per + 1, chunk[0], chunk[-1]))
        sheet.save(fn)
        out.append({'file': str(fn), 'pages': chunk})
    return out


def export_pages(res, out_dir, pages=None, dpi=None, prof=None):
    """只为 must_review 页导出单页 PNG（看图用；不整书转图）。dpi 缺省取像素判定用过的最高分辨率。
    写前做输出位置安全检查。"""
    check_out_path(out_dir, prof, [res['old']['path'], res['new']['path']], is_dir=True)
    pages = res['must_review'] if pages is None else pages
    dpi = dpi or res['pixel'].get('dpi_max') or res['config']['dpi']
    doc = fitz.open(res['new']['path'])
    os.makedirs(out_dir, exist_ok=True)
    out = []
    for n in pages:
        fn = Path(out_dir) / ('page-%d.png' % n)
        doc[n - 1].get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False).save(str(fn))
        out.append(str(fn))
    return out


def inherited_records(res):
    """把本次继承结果写成新版 PDF 的账本记录（沿用原看图者与等级，注明是像素继承而非新看）。
    按原记录（完整路径#序号）分组；同组看图者或等级不一致即报错停止。"""
    groups = defaultdict(dict)
    meta = {}
    for e in res['pages']:
        ih = e['inherit']
        if ih['status'] != 'inherited':
            continue
        key = (ih['record'], ih['basis'])
        if key in meta and (meta[key]['viewer'], meta[key]['viewer_level'], meta[key]['record_kind']) != (
                ih['viewer'], ih['viewer_level'], ih['record_kind']):
            raise RuntimeError('继承记录分组冲突：%s 下看图者或等级不一致（%s/%s vs %s/%s），停止写出' % (
                ih['record'], meta[key]['viewer'], meta[key]['viewer_level'], ih['viewer'], ih['viewer_level']))
        groups[key][e['page']] = (ih['from_page'], tuple(e.get('pixel_dpis') or ()))
        meta[key] = ih
    out = []
    now = datetime.now().astimezone().isoformat(timespec='seconds')
    for key, mp in groups.items():
        ih = meta[key]
        out.append({
            'kind': 'inherited', 'pdf_sha256': res['new']['sha256'], 'pdf_path': res['new']['path'],
            'pages': ranges(mp), 'verdict': 'PASS', 'viewer': ih['viewer'], 'viewer_level': ih['viewer_level'],
            'viewed_at': ih['viewed_at'], 'evidence': ih.get('evidence'), 'dpi': ih.get('view_dpi'),
            'origin': ih.get('origin') or {'pdf_sha256': res['old']['sha256'], 'record': ih['record'],
                                           'record_kind': ih['record_kind']},
            'inherited_from': {'pdf_sha256': res['old']['sha256'], 'record': ih['record'],
                               'page_map': {str(k): v[0] for k, v in sorted(mp.items()) if k != v[0]}},
            'basis': ih['basis'].split('(')[0], 'pixel_dpis': sorted({d for v in mp.values() for d in v[1]}),
            'rasterizer': res['pixel']['rasterizer'], 'created_by': TOOL, 'created_at': now,
            'note': '由像素比对继承原看图结论，不是新的视觉检查；证据等级沿用原记录。',
        })
    return out


# ---------------- 命令行 ----------------

def _load_prof(name, pdfs):
    """显式给名则用之；否则按新 PDF、再按旧 PDF 路径识别。"""
    if name:
        return load_profile(name)
    for p in pdfs:
        q = detect_profile(p) if p else None
        if q:
            return q
    return None


def _frozen_among(pdfs, prof):
    qs = [prof] + [detect_profile(p) for p in pdfs if p]
    return next((q for q in qs if q and q.get('frozen')), None)


def cmd_record(argv):
    ap = argparse.ArgumentParser(prog='page_delta.py record', description='登记一次实际看页（追加到账本 JSONL）。')
    ap.add_argument('--pdf', required=True, help='实际看过的那个 PDF（按其 SHA256 绑定）')
    ap.add_argument('--pages', required=True, help='实际打开看过的页，如 2-3,52-95（也接受 52—95、52～95）')
    ap.add_argument('--viewer', required=True, help='谁看的（会话/工作流/代理名）')
    ap.add_argument('--level', required=True, choices=LEVELS, help='证据等级：用户/主代理/子代理/外部主控/外部子代理')
    ap.add_argument('--kind', default='viewed', choices=['viewed', 'ruling'],
                    help='viewed=实际看页；ruling=对已报问题的裁定（须同样看过该页）')
    ap.add_argument('--verdict', required=True, choices=['PASS', 'ISSUES', 'FAIL'], help='看页结论')
    ap.add_argument('--issue-pages', default='', help='有问题（不可继承）的页')
    ap.add_argument('--dpi', type=int, help='当时看图的分辨率（像素继承会在这个 dpi 下复比）')
    ap.add_argument('--evidence', help='原始看页记录路径')
    ap.add_argument('--viewed-at', help='看页时间（ISO），缺省为现在')
    ap.add_argument('--note', default='')
    ap.add_argument('--profile', help='书册配置名；缺省按 PDF 路径识别')
    ap.add_argument('--ledger-out', required=True, help='追加写入的账本 JSONL（不得在审阅入口/书稿目录）')
    a = ap.parse_args(argv)
    try:
        n = check_pdf(a.pdf)
        pages = parse_pages(a.pages)
        issues = parse_pages(a.issue_pages)
    except (InputError, ValueError) as e:
        print('输入错误：%s' % e, file=sys.stderr)
        return 2
    if a.viewed_at and _parse_time(a.viewed_at) is None:
        print('--viewed-at 不是 ISO 时间：%s' % a.viewed_at, file=sys.stderr)
        return 2
    bad = [p for p in pages + issues if not 1 <= p <= n]
    if bad or not pages:
        print('页号超出 1-%d 或为空：%s' % (n, ranges(bad) or '（空）'), file=sys.stderr)
        return 2
    try:
        prof = _load_prof(a.profile, [a.pdf])
        fz = _frozen_among([a.pdf], prof)
        if fz:
            frozen_guard(fz, '写看页账本')
        out = check_out_path(a.ledger_out, prof, [a.pdf])
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 3
    rec = {'kind': a.kind, 'pdf_sha256': sha256_file(a.pdf), 'pdf_path': str(Path(a.pdf).resolve()),
           'pdf_pages': n, 'pages': ranges(pages), 'viewer': a.viewer, 'viewer_level': a.level,
           'viewed_at': a.viewed_at or datetime.now().astimezone().isoformat(timespec='seconds'),
           'verdict': a.verdict, 'issue_pages': ranges(issues), 'dpi': a.dpi,
           'evidence': a.evidence, 'note': a.note, 'recorded_by': TOOL, 'schema': LEDGER_SCHEMA}
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')
    print('已追加 %d 页看页记录（%s，%s，%s）到 %s' % (len(pages), a.level, a.kind, a.verdict, out))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == 'record':
        return cmd_record(argv[1:])
    ap = argparse.ArgumentParser(
        prog='page_delta.py', description='两版 PDF 看哪几页：文本签名对齐 + 同页整页像素判定 + 看页账本继承 + 机器预筛（只读）。'
        '另有子命令：page_delta.py record ...（登记实际看页）。')
    ap.add_argument('old', help='上一版 PDF')
    ap.add_argument('new', help='本版 PDF')
    ap.add_argument('--profile', help='书册配置名（如 bixiu3）；缺省按新 PDF、再按旧 PDF 路径识别')
    ap.add_argument('--old-identity', help='上一版同版身份 JSON')
    ap.add_argument('--new-identity', help='本版同版身份 JSON')
    ap.add_argument('--ledger', action='append', default=[], help='看页账本（可多次给）')
    ap.add_argument('--final', action='store_true',
                    help='终审口径（定稿、送印前全书检查）：与上一版一样的页也须有旧页实看记录才免看')
    ap.add_argument('--ledger-out', help='把本次继承结果写成新版账本记录（JSONL，追加）')
    ap.add_argument('--context', type=int, help='受影响页前后各加几页（不能低于 profile.pixel.context_pages，缺省 1）')
    ap.add_argument('--dpi', type=int, help='基础像素判定分辨率（只能高于 profile.render.png_dpi；被继承记录的看图 dpi 另行复比）')
    ap.add_argument('--no-pixel', action='store_true', help='不做像素判定（文字相同页一律不可继承）')
    ap.add_argument('--no-flags', action='store_true', help='不做机器预筛')
    ap.add_argument('--json', help='JSON 明细输出路径（缺省 --out-dir/page_delta.json）')
    ap.add_argument('--out-dir', help='输出目录（联系表、单页图、JSON）')
    ap.add_argument('--contact-sheet', action='store_true', help='为 must_review 页生成联系表 PNG')
    ap.add_argument('--export-pages', action='store_true', help='为 must_review 页导出单页 PNG（dpi 取像素判定用过的最高值）')
    ap.add_argument('--jobs', type=int, help='并行进程数（缺省 min(8, CPU)）')
    ap.add_argument('--quiet', action='store_true', help='不打印中文摘要')
    a = ap.parse_args(argv)
    try:
        for p in (a.old, a.new):
            check_pdf(p)
        for p in [a.old_identity, a.new_identity] + a.ledger:
            if p and not os.path.isfile(p):
                raise InputError('输入文件不存在：%s' % p)
        prof = _load_prof(a.profile, [a.new, a.old])
    except InputError as e:
        print('输入错误：%s' % e, file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001
        print('书册配置读取失败：%s' % e, file=sys.stderr)
        return 2
    inputs = [a.old, a.new]
    try:
        jpath = a.json or (os.path.join(a.out_dir, 'page_delta.json') if a.out_dir else None)
        if jpath:
            check_out_path(jpath, prof, inputs)
        if a.out_dir:
            check_out_path(a.out_dir, prof, inputs, is_dir=True)
        if a.ledger_out:
            fz = _frozen_among(inputs, prof)
            if fz:
                frozen_guard(fz, '写看页账本')
            lo = check_out_path(a.ledger_out, prof, inputs)
            if any(Path(x).resolve() == lo for x in a.ledger):
                raise UnsafeOutput('拒绝写入：--ledger-out 不能与输入账本同一文件')
        if (a.contact_sheet or a.export_pages) and not a.out_dir:
            raise UnsafeOutput('--contact-sheet / --export-pages 需要 --out-dir')
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 3
    try:
        res = compute_delta(a.old, a.new, prof, a.old_identity, a.new_identity, a.ledger, a.context, a.dpi,
                            pixel=not a.no_pixel, jobs=a.jobs, flags_on=not a.no_flags, final=a.final)
        recs = inherited_records(res) if a.ledger_out else None
    except (InputError, RuntimeError, ValueError) as e:
        print('处理失败：%s' % e, file=sys.stderr)
        return 2
    t = time.time()
    if a.contact_sheet:
        res['contact_sheets'] = contact_sheets(res, os.path.join(a.out_dir, 'contact'), prof=prof)
    if a.export_pages:
        res['exported_pages_dir'] = os.path.join(a.out_dir, 'pages')
        res['exported_pages'] = len(export_pages(res, res['exported_pages_dir'], prof=prof))
        res['exported_pages_dpi'] = res['pixel'].get('dpi_max') or res['config']['dpi']
    if a.contact_sheet or a.export_pages:
        res['seconds']['images'] = round(time.time() - t, 2)
    if a.ledger_out:
        Path(a.ledger_out).parent.mkdir(parents=True, exist_ok=True)
        with open(a.ledger_out, 'a', encoding='utf-8') as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + '\n')
        res['ledger_out'] = {'path': a.ledger_out, 'records': len(recs),
                             'pages': sum(len(parse_pages(r['pages'])) for r in recs)}
    if jpath:
        Path(jpath).parent.mkdir(parents=True, exist_ok=True)
        Path(jpath).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding='utf-8')
    if not a.quiet:
        print(res['summary_zh'])
        if jpath:
            print('JSON：%s' % jpath)
        if res.get('contact_sheets'):
            print('联系表 %d 张：%s' % (len(res['contact_sheets']), os.path.join(a.out_dir, 'contact')))
        if res.get('ledger_out'):
            print('继承记录 %d 条（%d 页）追加到 %s' % (res['ledger_out']['records'], res['ledger_out']['pages'], a.ledger_out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
