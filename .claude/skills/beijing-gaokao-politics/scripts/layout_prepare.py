#!/usr/bin/env python3
"""排版准备（按书册配置运行）：例题/考法编号、考法标称题数、keepNext、目录页码回填。

用途
  把 book_incremental.py（必修二）与 Codex final_layout_prepare.py（必修三）里反复手写的四件机械活
  合成一个按 profiles/<book>.json 配置运行的通用工具：
    - 例题编号是否与 bh.check_numbering 的期望连号一致，不一致就改标题里的数字；
    - 考法标题“（N题）”是否与 bh.check_method_counts 数出的实际题数一致，不一致就改数字；
    - 例题/考法标题、材料小标题是否按 bh.check_keepnext 的规则设了 keepNext，没设就补上；
    - 目录条目缓存的页码是否与同版 PDF 里的超链接落页一致（bh.check_toc_docx/check_toc_pdf 同一套判定），
      不一致就把目录行里那个纯数字的缓存文字改掉。
  “该不该改”的判定全部来自 batch_health 已经跑通的检查函数，本工具不另写一套识别逻辑，只负责把判定
  结果落回 XML；批注：目录页码来源与匹配算法照抄 bh.check_toc_pdf 的做法（bh 只暴露 FAIL，不暴露目标页
  码本身，这里薄封装一份返回页码而不是发现项），并额外做 bh.check_toc_pdf 自己的两道闸（链接行数=条目
  数、落页上能找到标题），任一条不满足就整批中止、不做“找不到就按下标兜底配对”。

用法
  python3 layout_prepare.py check --docx X.docx [--pdf 同版.pdf] [--toc-pdf 同版.pdf] [--profile bixiu3] [--report x.json]
      只读，列出需要改的地方（用 repair 同一套计划函数，口径与 repair 一致）；有待改退出 1，没有退出 0
      ——待改包括 toc_version_problems（目录页码与所给 PDF 有差异但该 PDF 未经同版身份绑定）：这类
      差异同样让 check 退出 1，报告与 stdout 会给出 toc_note，说明要用 render_book.py 渲染出带身份
      记录的 PDF、或 repair 时显式 --allow-unbound-pdf 才能回填，不是“无需处理”。
  正式流程：--toc-pdf / --pdf 用于目录回填时应传 render_book.py 渲染出的 PDF（会一并写 同版身份.json，
      供 prove_same_version 认定 identity=='match'）；没有身份记录的 soffice 直出 PDF（例如临时的目录
      定位稿）只能在 repair 时配 --allow-unbound-pdf 显式降级使用，check 对这类 PDF 的页码差异一律计入
      toc_version_problems、不计入可修 pending。
  python3 layout_prepare.py repair --docx X.docx --out Y.docx \
      [--numbering] [--method-counts] [--keepnext] [--toc --toc-pdf P.pdf] \
      [--profile bixiu3] [--expect-sha 父稿SHA] [--allow-blocked] [--health] [--report y.json]
      每种操作必须显式点名，只改点名的部分；写前后都会核对：未点名段落指纹不变、点名的门写后必须 0 FAIL/0 WARN，
      任一条不满足 → 中止且不留输出文件（已写出的会被删除）。

读写承诺
  check 只读，不写任何书稿文件（--report 除外，且必须落在系统临时目录或
  “…/协作/候选/<谁>/<批次>/构建/”之下，见本文件 guard_report）。
  repair 只改 word/document.xml；其余 ZIP 成员逐字节照抄；写前用 docx_lib.open_docx 核父稿 SHA、写后
  用 docx_lib.write_docx 原子替换并复核未点名成员未变；未被本次操作点名的段落用 docx_lib.unchanged_paragraphs
  核对指纹不变（比对对象是打开时另外解析出的原始 document.xml，不是改过的树自己比自己）。
  书册判定：不只信 --profile——始终用 profile_lib.detect_profile(docx) 反查输入实际属于哪本书；命中已登记
  的冻结册就拒绝写出，与 --profile 指定什么无关；detect 出的书与 --profile 不一致时中止。冻结册（profile.frozen）
  任何写操作立即拒绝，check 仍可跑。

退出码
  0 成功 / check 无待改；1 check 有待改（含 toc_version_problems：目录页码与所给 PDF 不符但该 PDF
    未经同版身份绑定，见 toc_note），或 repair 写后复核（点名的门 / --health 体检）失败（已删除输出）；
  2 输入或配置错误、参数不全、SHA 不符、书册探测与 --profile 不一致、目录版本不匹配、定位被跳过（blocked）等
    中止（不留输出）；3 拒绝写出（冻结册或落在受保护目录）。异常一律转中文提示，--debug 打开原始 traceback。

读取的配置字段（见 profiles/schema.md；缺省值取自 batch_health.DEFAULTS 或本文件内注明）
  styles.example_title、example_titles[].regex（要求命名组 num）——沿用 bh.Prof.title 的判定；
  structure.parts[].numbering_reset、numbering.per_kind、numbering.unnumbered_kinds；
  method_count.regex（缺省 `（(\\d+)题）\\s*$`）、bearer_styles、count_kinds、unit；
  pagination.keep_next_title_required（缺省 true）、keep_next_label_regex、keep_next_target_style、
  forbid_long_chains（缺省未设即不限）；
  pagination.max_keep_next_chain —— 本工具新增字段（两册配置尚未登记，见回执 profile_fields_needed），
    缺省 20：某次补 keepNext 后若把它所在的那条连续 keepNext=true 链（含本段）撑到超过这个长度、且比
    改前这条链本身更长，就跳过这条、在报告里列为 blocked，不静默做大长链（按局部链长比较，不再拿全书
    最长链当基准——原实现用全书 max() 当基准会被别处已有的更长链“掩护”）；
  pagination.keep_next_labels —— 本工具新增字段：整段就是标签本身、要求单独加 keepNext 的行；
    缺省 []（未配置不启用，2026-09-24 起不再在代码里给必修三的两个标签值当全局缺省，避免误套到
    未登记该字段的其他册）；必修三 profiles/bixiu3.json 已登记该字段（['【思维链条】', '【答案落点】']），
    只对显式点名 --keepnext 的书生效，不做“只对某册生效”的硬编码判断。
  toc.mode —— pageref_in_hyperlink（必修三：超链接＋PAGEREF 域，取 separate/end 之间的结果）或
    hyperlink_static（必修二：静态页码文字，取 w:fldSimple 内或 w:hyperlink 内最后一个数字）；
  toc.styles、toc.toc_pdf_pages、toc.scan_first_pages（缺省 8）——目录条目定位与 PDF 落页匹配同 bh。
  toc.pdf_align_min —— 本工具新增字段（尚未登记，见回执 profile_fields_needed），缺省 0.98：目录同版闸
    在“没有同版身份记录、用 --allow-unbound-pdf 降级放行”这条兜底路径上要求的双向正文对位率阈值
    （复用 block_index.align 的对位算法，见 prove_same_version）。
  目录同版闸（2026-09-24 第五轮返修，见 prove_same_version）：分页是否相同，正文对位率——不管单向双向——
    本质上都证明不了，只有 SHA 才行（同一份文字排两次版，分页可能不同；例如旧版直接渲染的 PDF 拿去配
    后来加了 keepNext 的新版，文字对得上、分页却变了）。因此 repair --toc 缺省要求同版身份记录
    （bh._identity_records：render_book.py 渲染时写的 render.identity_file，或 .review-manifest.json）
    且 identity=='match'（docx_sha256 与 pdf_sha256 都对上）才允许回填；记录冲突（docx_mismatch/
    pdf_mismatch）一律直接拒绝，不看任何开关。没有记录（identity 为 unrelated/not_found）时缺省整批
    中止（exit 2），除非显式传 --allow-unbound-pdf "理由"——这时退回到正文对位率兜底，且改成双向：
    正向（DOCX 段落能否在 PDF 文字流里找到，原有算法）与反向（PDF 文字行能否在 DOCX 文字流里找到，
    用同一个 bx.align 算法调换角色跑一遍，见 _pdf_line_paras）都须 ≥ toc.pdf_align_min，任一方向不
    达标都拒绝；通过也只是“未经 SHA 绑定”的降级放行，报告标 pdf_same_version_proven=false、stderr 写
    WARN“未经 SHA 绑定，页码可能与最终分页不符”。check（--toc-pdf 只读诊断）永远不看这个开关：识别
    不到身份记录就总把对应的页码差异列进 toc_version_problems（附 identity/method/align_ratio/
    reverse_align_ratio），不算进可修 pending，即便双向对位率都很高——check 不写东西，没必要替 repair
    做“要不要采信”的决定，那是主代理和 --allow-unbound-pdf 的事。双向对位率仍是文字证据：小规模删增
    段（百段量级以下）可能两个方向都测不出来，见文件头 known_limits，别当成分页正确性的证明。
  --allow-mass-renumber（repair 新增开关）—— 输入路径未落在任何登记书册目录下（profile_lib.detect_profile
    判空）、且计划编号改动超过例题标题数 10%、或有考法题数将归零时，缺省整批中止（blocked，退出 2），
    这条不受 --allow-blocked 影响，只能用 --allow-mass-renumber 显式放行（放行也写入报告）。

已知不做的事（写进回执 known_limits，不在这里静默处理）
  目录页码换算“印刷页脚偏移”：现有两册的 toc 校验都是直接拿 PDF 内部链接落页跟目录缓存页码比
  （bh.check_toc_pdf 就是这样判 FAIL 的），本工具照此口径回填，不做 footer.page_offset 换算；
  表格结构增删、跨段编号（补丁范围）不在本工具内；--allow-unbound-pdf 兜底路径的双向正文对位率对
  “大段增删”（百段量级）敏感，对“小段增删”（十几到一百段量级）可能两个方向都测不出来——这只是文字
  证据，永远证明不了分页相同，真正要防的还是靠身份记录；这条兜底路径存在的意义只是给“确实没法补身份
  记录、又确认是同一份文字”的场景一个可控的人工降级口子，不是自动的同版证明。
"""
import argparse
import json
import os
import re
import sys
import tempfile
import time
import traceback
from collections import Counter, OrderedDict
from pathlib import Path

from lxml import etree

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import batch_health as bh  # noqa: E402
import block_index as bx  # noqa: E402  # 目录同版闸复用：bx.load_docx/BookCfg/pdf_stream/align 做正文对位率
import docx_lib as dl  # noqa: E402
from profile_lib import load_profile, detect_profile, list_profiles, resolve  # noqa: E402

TOOL_VERSION = '1.2.1'
W = bh.W
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'


class Abort(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def say(msg):
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------- 书册配置（始终用 detect_profile 反查，
# 不管 --profile 说了什么；命中已登记的冻结册就拒绝，与 --profile 无关）
def get_profile(args):
    detected = None
    try:
        detected = detect_profile(args.docx)
    except Exception:
        detected = None
    if args.profile:
        pd = load_profile(args.profile)
        if detected is not None:
            det_path = str(Path(detected.get('_profile_path', '')).resolve())
            pd_path = str(Path(pd.get('_profile_path', '')).resolve())
            if det_path != pd_path:
                if detected.get('frozen'):
                    raise Abort(3, '%s 已冻结，拒绝写出（按 --docx 路径探测得到，与 --profile 指定的 %s 无关）：%s' %
                                (detected.get('title', detected.get('book_id')), pd.get('book_id', '?'),
                                 detected.get('frozen_note', '')))
                raise Abort(2, '按 --docx 路径探测到的书册（%s）与 --profile 指定的（%s）不一致，拒绝继续' %
                            (detected.get('book_id', '?'), pd.get('book_id', '?')))
        return pd
    if detected is None:
        raise Abort(2, '无法按路径判断书册，请用 --profile 指定（可选：%s）' % '、'.join(list_profiles()))
    return detected


# ---------------------------------------------------------------- w:t 节点级文字操作（只在 w:t 坐标系里定位，
# 与 batch_health 的 it['text']（含 w:tab/w:sym）分开算，避免把制表符位置误当成数字位置）
def _fallback_skip(p):
    skip = set()
    for fb in p.iter(bh.MC + 'Fallback'):
        skip.update(fb.iter())
    return skip


def text_nodes(p):
    skip = _fallback_skip(p)
    out = []
    for r in p.iter(W + 'r'):
        if r in skip:
            continue
        for ch in r:
            if ch.tag == W + 't':
                out.append(ch)
    return out


def t_text(p):
    return ''.join(n.text or '' for n in text_nodes(p))


def has_tab_or_sym(p):
    """段内是否真的含 w:tab/w:sym（决定 t_text 的 w:t 坐标系是否可信用来定位数字 span）。
    不再用 t_text(p) != it['text'] 判断——那个比较会被段尾/段首空白 run、零宽字符等 read_docx 已经
    strip/去掉的差异误伤（把纯空白差异也报成“含 w:tab/w:sym”），这里直接看有没有真的 tab/sym 元素。"""
    skip = _fallback_skip(p)
    for r in p.iter(W + 'r'):
        if r in skip:
            continue
        for ch in r:
            if ch.tag in (W + 'tab', W + 'sym'):
                return True
    return False


def replace_span(p, start, end, new):
    """在 w:t 节点坐标系里替换 [start,end) 为 new（非数字场景，如目录标签文字）：保留全部 run/格式，
    只可能清空跨过的 run 的 w:t，新字整段放进第一个覆盖到的节点。"""
    nodes = text_nodes(p)
    if start < 0 or end < start:
        raise ValueError('区间非法：%d:%d' % (start, end))
    off, first = 0, None
    for node in nodes:
        old = node.text or ''
        a, b = off, off + len(old)
        off = b
        os_, oe = max(start, a), min(end, b)
        if os_ >= oe:
            continue
        la, lb = os_ - a, oe - a
        if first is None:
            node.text = old[:la] + new + old[lb:]
            first = node
        else:
            node.text = old[:la] + old[lb:]
        if node.text and (node.text[0] == ' ' or node.text[-1] == ' '):
            node.set(XML_SPACE, 'preserve')
    if first is None:
        raise ValueError('区间 %d:%d 落在段落文字之外（可能跨 w:tab/w:sym，未处理）' % (start, end))


def replace_span_digits(p, start, end, new):
    """数字专用替换（编号、考法题数）：位数相同时按位分配回原节点，各节点保留自己的 rPr；跨 run 且新旧
    位数不同时，前面节点按原宽度截取，多出或缺少的位并入最后一个覆盖节点。返回是否发生了“跨 run 且位数
    不同”的情况（调用方据此在报告里注明 cross_run_digits_redistributed）。"""
    nodes = text_nodes(p)
    covered = []
    off = 0
    for node in nodes:
        old = node.text or ''
        a, b = off, off + len(old)
        off = b
        os_, oe = max(start, a), min(end, b)
        if os_ >= oe:
            continue
        covered.append((node, a, os_ - a, oe - a))
    if not covered:
        raise ValueError('区间 %d:%d 落在段落文字之外（可能跨 w:tab/w:sym，未处理）' % (start, end))
    if len(covered) == 1:
        node, a, la, lb = covered[0]
        old = node.text or ''
        node.text = old[:la] + new + old[lb:]
        if node.text and (node.text[0] == ' ' or node.text[-1] == ' '):
            node.set(XML_SPACE, 'preserve')
        return False
    widths = [lb - la for _, _, la, lb in covered]
    uneven = sum(widths) != len(new)
    cursor = 0
    for idx, (node, a, la, lb) in enumerate(covered):
        old = node.text or ''
        if idx < len(covered) - 1:
            w = widths[idx]
            piece = new[cursor:cursor + w]
            cursor += w
        else:
            piece = new[cursor:]
        node.text = old[:la] + piece + old[lb:]
        if node.text and (node.text[0] == ' ' or node.text[-1] == ' '):
            node.set(XML_SPACE, 'preserve')
    return uneven


def ensure_ppr(p):
    ppr = p.find(W + 'pPr')
    if ppr is None:
        ppr = etree.Element(W + 'pPr')
        p.insert(0, ppr)
    return ppr


def set_keep_next_true(p):
    """在 pPr 里补 w:keepNext；已存在（含 val=0）时改为生效。返回是否真的改动。
    插入位置：直接 append 到 pPr 末尾（含 rPr 之后），不追求 CT_PPrBase 的严格 schema 顺序——这是本册
    历史产出（04/…/52 一路渲染发布的稿子）实际的写法（book_incremental.py、Codex final_layout_prepare.py
    的 add_keep_next 都是 ppr.append(...)），Word/渲染管线已经这样用过很多批，不再改成“更规范”的插到
    rPr 之前，否则与既有稿子逐段 XML 比对时会多出一堆无意义差异。"""
    ppr = ensure_ppr(p)
    kn = ppr.find(W + 'keepNext')
    if kn is not None:
        if kn.get(W + 'val') in (None, '1', 'true', 'on'):
            return False
        del kn.attrib[W + 'val']
        return True
    ppr.append(etree.Element(W + 'keepNext'))
    return True


def true_numbering(items, P):
    """薄封装，且与 bh.check_numbering 语义不同，注明原因：check_numbering 是“棘轮”式单点核对——它把
    上一个标题的实际数字当成下一个的基数（`seen[k] = e['num']`），只用来在体检里抓“比上一条多/少了一个”
    这类单点típo，不是拿来算“这批本该是几”。批量重排必须按纯序数重新数（`seen[k] = seen.get(k,0)+1`，
    不看原有数字），这与 book_incremental.refresh()、Codex final_layout_prepare.numbering_audit 的算法
    一致。二者共用同一套 part/resets/title_kind 扫描规则（照抄 bh.check_numbering 的扫描部分），只有
    这一行“基数从哪来”不同。返回 {段号: 应该是的数字}（只含需要编号的标题）。"""
    parts = {p['id']: p for p in P.parts}
    unnumbered = set(bh.cfg(P.d, 'numbering.unnumbered_kinds', []) or [])
    per_kind = bh.cfg(P.d, 'numbering.per_kind', True)
    seen, out = {}, {}
    for it in items:
        pr = parts.get(it['part'], {})
        resets = set(pr.get('numbering_reset', ['h2']))
        if it['zone'] == 'heading':
            if (it['style'] in P.h1 and it['tbl'] is None) or ('h2' in resets and it['style'] in P.h2 and it['tbl'] is None) \
                    or ('method' in resets and it['_method']) or ('group_heading' in resets and it['_group']):
                seen = {}
        e = it['_title']
        if not e:
            continue
        if e['kind'] in unnumbered or e['title_kind'] in unnumbered or not e['numbered']:
            continue
        k = e['title_kind'] if per_kind else '*'
        seen[k] = seen.get(k, 0) + 1
        out[it['i']] = seen[k]
    return out


# ---------------------------------------------------------------- 编号定位（薄封装：bh.Prof.title 只给判定
# 结果，不给数字在 w:t 坐标系里的 span，这里重跑一次同一份正则拿 span）
def num_span_in_ttext(P, it, tt):
    """按标题正则重新定位编号 span：bh.read_docx 的 it['text'] 是 raw.strip()（去首尾空白）后再拿去配正则，
    这里的 tt = t_text(p) 是未 strip 的 w:t 原文拼接——段首若有一个只含空白的 run（不影响 it['text']，
    但会出现在 tt 里），会让 rx.match(tt) 因为多出的前导空白而整段匹配不上、被判 blocked。按同一规则先去掉
    tt 的前导空白再匹配，返回的 span 再加回被去掉的长度，落回 tt 自己的坐标系（replace_span_digits 用的就是
    这个坐标系）。"""
    if it['tbl'] is not None or it['style'] not in P.title_styles:
        return None
    lead = len(tt) - len(tt.lstrip())
    tt2 = tt[lead:]
    for kind, rx, sts, numbered in P.titles:
        if (sts and it['style'] not in sts) or (not sts and it['style'] not in P.base_title_styles):
            continue
        m = rx.match(tt2)
        if m and numbered and 'num' in rx.groupindex:
            a, b = m.span('num')
            return (a + lead, b + lead)
    return None


def method_count_span_in_ttext(P, tt):
    m = P.count_rx.search(tt)
    return m.span(1) if m else None


# ---------------------------------------------------------------- 目录：定位缓存页码节点、匹配同版 PDF 落页
def toc_page_nodes(p, mode='pageref_in_hyperlink'):
    """按 toc.mode 分别定位段内目录缓存页码的数字节点：
    pageref_in_hyperlink：PAGEREF 域 fldChar separate 与 end 之间、且该域的 instrText 含 PAGEREF 的数字 w:t；
    hyperlink_static：w:fldSimple 内的数字 w:t，没有则取 w:hyperlink 内最后一个数字 w:t。
    不再只看“落在 hyperlink/fldSimple 之内、整段是数字”——那种判法会把标签里恰好独立成 run 的数字
    （页码域之外的普通文字）误当成页码节点。"""
    skip = _fallback_skip(p)
    if mode == 'hyperlink_static':
        out = []
        for host in p.iter(W + 'fldSimple'):
            for t in host.iter(W + 't'):
                if t in skip:
                    continue
                if re.fullmatch(r'\s*\d+\s*', t.text or ''):
                    out.append(t)
        if out:
            return _dedup(out)
        for host in p.iter(W + 'hyperlink'):
            nums = [t for t in host.iter(W + 't') if t not in skip and re.fullmatch(r'\s*\d+\s*', t.text or '')]
            if nums:
                out.append(nums[-1])
        return _dedup(out)
    # pageref_in_hyperlink（缺省）：按段内 run 的先后顺序识别 fldChar begin/separate/end 与其间的 instrText、w:t。
    # 域代码（如 " PAGEREF _Toc123456 \\h "）常被 Word 拆成多个 <w:instrText>（甚至分属不同 run），
    # 单个片段各含半个 "PAGEREF" 时谁都不命中子串——按 begin..separate 累积拼接后再判断，不逐片段单看。
    out, state, instr_buf = [], 'idle', ''
    for r in p.iter(W + 'r'):
        if r in skip:
            continue
        for ch in r:
            if ch.tag == W + 'fldChar':
                kind = ch.get(W + 'fldCharType')
                if kind == 'begin':
                    state, instr_buf = 'begin', ''
                elif kind == 'separate':
                    state = 'collect' if (state == 'begin' and 'PAGEREF' in instr_buf) else 'idle'
                elif kind == 'end':
                    state, instr_buf = 'idle', ''
            elif ch.tag == W + 'instrText':
                if state == 'begin':
                    instr_buf += ch.text or ''
            elif ch.tag == W + 't' and state == 'collect':
                if re.fullmatch(r'\s*\d+\s*', ch.text or ''):
                    out.append(ch)
    return _dedup(out)


def _dedup(nodes):
    seen, uniq = set(), []
    for n in nodes:
        if id(n) not in seen:
            seen.add(id(n))
            uniq.append(n)
    return uniq


def _pdf_line_paras(pdf_path, cfgb):
    """反向对位用：把 PDF 逐页文字按行拆成伪“段落”列表 [{'p','text','fallback'}]，喂给 bx.align 当它的
    第一个参数（paras），DOCX 侧的签名串当它的 stream，就能反过来查“PDF 这行文字有没有对应的 DOCX 段落”
    ——发现正向对位率查不出的删段类错版（DOCX 删了一大截，PDF 还是旧的，正向对位率照样很高，因为剩下的
    段落原样能在 PDF 里找到）。行级别的粗细粒度足够：align 内部按 sig() 再签一遍、按锚点/探针定位，不需
    要精确的“段”边界。跳过与 pdf_stream 相同的页脚行，短行按 bx.ALIGN_MIN 预先筛掉（align 自己也会筛，
    这里只是少建一些注定被丢弃的候选，省内存）。"""
    import fitz
    doc = fitz.open(str(pdf_path))
    try:
        out, idx = [], 0
        for pg in doc:
            for ln in pg.get_text('text').split('\n'):
                s = ln.strip()
                if len(s) <= 16 and cfgb.footer_rx.search(s):
                    continue
                if len(s) < bx.ALIGN_MIN:
                    continue
                out.append({'p': idx, 'text': s, 'fallback': False})
                idx += 1
        return out
    finally:
        doc.close()


def prove_same_version(pd, P, docx_path, pdf_path, docx_sha, pdf_sha, soft=False, allow_unbound=None):
    """目录同版闸：证明 pdf_path 确由 docx_path 这份稿子渲染，不只信文件名/调用者传参。
    分页是否相同，正文对位率——不管单向双向——本质上都证明不了：同一份文字排两次版，分页可能不同（旧版
    直接渲染的 PDF 拿去配后来加了 keepNext 的新版，文字对得上、分页却变了）。唯一能真正证明的是同版身份
    记录（bh._identity_records：render_book.py 渲染时写的 render.identity_file，或 .review-manifest.json）
    ——SHA 双双吻合（identity=='match'）才算数，不再叠加对位率（cryptographic identity 不需要文字证据
    背书）；记录冲突（docx_mismatch/pdf_mismatch）是确凿证据，一律直接拒绝，任何开关都不放行。
    没有身份记录（identity 为 unrelated/not_found）：
      - soft=False（repair）缺省直接 Abort(2)，不计算对位率——除非调用方传入非空 allow_unbound
        （--allow-unbound-pdf 的理由文本），这时退回到正文对位率兜底，且改双向：正向（bx.align 原有算法：
        DOCX 段落能否在 PDF 文字流里找到）与反向（_pdf_line_paras + bx.align 调换角色：PDF 文字行能否在
        DOCX 文字流里找到）都须 ≥ toc.pdf_align_min，任一方向不达标都拒绝；通过也只是“未经 SHA 绑定”的
        降级放行，result 标 pdf_same_version_proven=false，stderr 写 WARN。
      - soft=True（check）永远不看 allow_unbound（check 只读诊断，没有必要放行）：一样算出双向对位率
        （供调用方在 toc_version_problems 里附 method/align_ratio），但无论对位率多高都不算“证明成立”，
        ok 恒为 False——check 不写东西，没必要替 repair 做“要不要采信”的决定。
    返回 (result, ok)。"""
    recs = bh._identity_records(P, docx_path, pdf_path)
    both = [r for r in recs if r['docx_sha256'] == docx_sha and r['pdf_sha256'] == pdf_sha]
    d_only = [r for r in recs if r['docx_sha256'] == docx_sha and r['pdf_sha256'] and r['pdf_sha256'] != pdf_sha]
    p_only = [r for r in recs if r['pdf_sha256'] == pdf_sha and r['docx_sha256'] and r['docx_sha256'] != docx_sha]
    if both:
        identity = 'match'
    elif d_only:
        identity = 'pdf_mismatch'
    elif p_only:
        identity = 'docx_mismatch'
    elif recs:
        identity = 'unrelated'
    else:
        identity = 'not_found'
    threshold = float(bh.cfg(pd, 'toc.pdf_align_min', 0.98))
    result = OrderedDict([('method', 'identity_record'), ('identity', identity), ('threshold', threshold)])
    if both:
        result['identity_file'] = both[0]['file']

    def _fail(reason):
        result['reason'] = reason
        result['pdf_same_version_proven'] = False
        if soft:
            return result, False
        raise Abort(2, '目录同版闸：%s，拒绝执行目录操作，不写输出' % reason)

    if identity in ('pdf_mismatch', 'docx_mismatch'):
        result['identity_file'] = (d_only or p_only)[0]['file']
        reason = ('同版身份记录里本 DOCX 对应的不是这份 PDF（%s）' % result['identity_file'] if identity == 'pdf_mismatch'
                 else '同版身份记录显示这份 PDF 由另一份 DOCX 渲染（%s）' % result['identity_file'])
        return _fail(reason)
    if identity == 'match':
        result['pdf_same_version_proven'] = True
        return result, True
    # identity in ('unrelated', 'not_found')：没有能证明这一对 docx/pdf 同版的身份记录
    if not soft and not allow_unbound:
        return _fail('没有同版身份记录（identity=%s）；可用 --allow-unbound-pdf "理由" 降级放行'
                    '（仍须双向正文对位率达标，且页码可能与最终分页不符）' % identity)
    # 走到这里：soft（check，只诊断不放行）或 allow_unbound（repair 显式降级）——都要算双向对位率
    result['method'] = 'identity_record+block_index_align(bidirectional)'
    doc = bx.load_docx(str(docx_path))
    cfgb = bx.BookCfg(pd)
    stream, starts, _footers, _toc, _npages = bx.pdf_stream(str(pdf_path), cfgb)
    pmap, tried, n_anchor = bx.align(doc['paras'], stream, starts)
    rate = round(len(pmap) / tried, 4) if tried else 0.0
    docx_stream = ''.join(bx.sig(r['text']) for r in doc['paras'] if not r['fallback'])
    pdf_paras = _pdf_line_paras(pdf_path, cfgb)
    pmap_r, tried_r, n_anchor_r = bx.align(pdf_paras, docx_stream, [0])
    rate_r = round(len(pmap_r) / tried_r, 4) if tried_r else 0.0
    result.update(align_ratio=rate, paras_tried=tried, anchors=n_anchor,
                  reverse_align_ratio=rate_r, pdf_lines_tried=tried_r, reverse_anchors=n_anchor_r)
    align_ok = bool(tried) and bool(tried_r) and rate >= threshold and rate_r >= threshold
    if not allow_unbound:
        # soft 且未放行：对位率仅供参考，不采信为证明，页码差异交调用方放进 toc_version_problems
        result['reason'] = '没有同版身份记录（identity=%s），对位率仅供参考、不采信为证明' % identity
        result['pdf_same_version_proven'] = False
        return result, False
    result['unbound_reason'] = allow_unbound
    if not align_ok:
        return _fail('已用 --allow-unbound-pdf 放行，但双向正文对位率仍有一项低于阈值'
                    '（正向 %.2f%%、反向 %.2f%%，阈值 %.0f%%），疑似不同版'
                    % (rate * 100, rate_r * 100, threshold * 100))
    result['pdf_same_version_proven'] = False
    say('WARN：--allow-unbound-pdf 已放行（理由：%s）——未经 SHA 绑定，页码可能与最终分页不符' % allow_unbound)
    return result, True


def toc_pdf_dests(pdf_path, ents, items, P):
    """薄封装：与 bh.check_toc_pdf 同一套按页收链接、按目录文字前缀配对的算法，并且做它的两道闸——
    链接行数是否等于条目数、落页上是否能找到对应标题——任一条不满足就在 problems 里如实列出，不做
    “按下标兜底配对”。调用方（repair）看到 problems 非空必须整批中止、不写输出。
    返回 (dests, n_links, problems)：dests[i] 是第 i 条目录条目在 PDF 里的落页（找不到给 None）。"""
    import fitz
    doc = fitz.open(str(pdf_path))
    try:
        pages = bh.cfg(P.d, 'toc.toc_pdf_pages') or list(range(1, min(bh.cfg(P.d, 'toc.scan_first_pages', 8), len(doc)) + 1))
        tocset = set(pages)
        links = []
        for pno in pages:
            if pno - 1 >= len(doc) or pno - 1 < 0:
                continue
            pg = doc[pno - 1]
            for l in sorted(pg.get_links(), key=lambda l: (round(l['from'].y0), l['from'].x0)):
                if l.get('kind') != fitz.LINK_GOTO:
                    continue
                y = round(l['from'].y0)
                if links and links[-1]['p'] == pno and abs(links[-1]['y'] - y) <= 3:
                    continue
                links.append({'p': pno, 'y': y, 'dest': l.get('page', -1) + 1, 'text': bh.norm(pg.get_textbox(l['from']))})
        links.sort(key=lambda x: (x['p'], x['y']))
        scan = bh.pdf_scan(doc, P)
        texts = bh.pdf_pages_text(scan)
        npages = [bh.norm(t) for t in texts]
        problems = []
        if len(links) != len(ents):
            problems.append('PDF 目录链接行数（%d）与 DOCX 目录条目数（%d）不同' % (len(links), len(ents)))
        used, out = set(), []
        for idx, e in enumerate(ents):
            lab = bh.norm(e['label'])
            cand = [j for j, l in enumerate(links) if j not in used and l['text'].startswith(lab[:10])]
            if not cand:
                out.append(None)
                problems.append('目录条目「%s」在 PDF 里未按文字匹配到链接（不做下标兜底）' % bh.clip(e['label'], 20))
                continue
            j = cand[0]
            used.add(j)
            l = links[j]
            head = bh.norm(items[e['target_i']]['text'])[:12] if e['target_i'] is not None else ''
            on_page = bool(head) and 0 < l['dest'] <= len(doc) and head in npages[l['dest'] - 1]
            if not on_page:
                problems.append('目录条目「%s」PDF 链接落页 %s 上找不到对应标题' % (bh.clip(e['label'], 20), l['dest']))
            out.append(l['dest'])
        return out, len(links), problems
    finally:
        doc.close()


# ---------------------------------------------------------------- keepNext 链长（简化：按段落顺序数连续
# keepnext=True 的段，不区分表格边界；本工具只加不减，风险在“合并出超长链”，见文件头 known_limits）
def keepnext_chain_lengths(flags):
    lens, run = [], 0
    for v in flags:
        if v:
            run += 1
        else:
            if run:
                lens.append(run + 1)
            run = 0
    if run:
        lens.append(run + 1)
    return lens


def chain_len_at(flags, i):
    """位置 i 若为 True，返回它所在那条连续 keepNext 链的长度（含链尾黏住的下一段）；否则返回 0。
    比较改前/改后要看“这条链自己涨到多长”，不能拿全书 max() 当基准——全书已有更长链时，任何局部新
    链都能“借道”超过上限而不被拦。"""
    if not flags[i]:
        return 0
    n = len(flags)
    j = i
    while j > 0 and flags[j - 1]:
        j -= 1
    k = i
    while k + 1 < n and flags[k + 1]:
        k += 1
    return (k - j + 1) + (1 if k + 1 < n else 0)


# ---------------------------------------------------------------- check/repair 共用的“计划”函数：check 用
# 它们列出待办，repair 用它们决定要改什么，口径统一（不再各算一套，避免 check 少报、repair 多改）
def plan_numbering(items, P):
    want = true_numbering(items, P)
    todo = []
    for i, expected in sorted(want.items()):
        it = items[i]
        actual = it['_title']['num']
        if actual != expected:
            todo.append({'para': i, 'old': actual, 'new': expected, 'title': bh.clip(it['text'], 50)})
    return todo


def plan_method_counts(items, P):
    F = bh.Findings()
    bh.check_method_counts(items, P, F)
    todo = []
    for f in F.items:
        if f['level'] == 'FAIL':
            todo.append({'para': f['where']['para'], 'claimed': f['claimed'], 'actual': f['actual'],
                        'title': f.get('excerpt')})
    return todo


def plan_keepnext(items, pd, P):
    F = bh.Findings()
    bh.check_keepnext(items, P, F)
    todo = [{'para': f['where']['para'], 'rule': f['rule'], 'excerpt': f.get('excerpt')}
            for f in F.items if f['level'] == 'WARN']
    # pagination.keep_next_labels：本工具新增字段。bh.check_keepnext 只覆盖“例题/考法标题”和“材料小
    # 标题”两类；Codex final_layout_prepare.py 另给【思维链条】【答案落点】这类整段就是标签本身的行加
    # keepNext（让标签不能单独留在页尾、后面没跟内容），bh 没有这条检查，这里按配置补上。缺省 []：未
    # 登记该字段的书册不套用任何标签（2026-09-24 起 profiles/bixiu3.json 已登记必修三的两个标签值，
    # 不在代码里给全局缺省，避免误套到其他册）。check 与 repair 都调这个函数，口径一致。
    labels = set(bh.cfg(pd, 'pagination.keep_next_labels', []) or [])
    if labels:
        norm_labels = {bh.norm(x) for x in labels}
        for it in items:
            if it['tbl'] is None and bh.norm(it['text']) in norm_labels and not it['keepnext']:
                todo.append({'para': it['i'], 'rule': '标签行未设 keepNext（pagination.keep_next_labels）',
                            'excerpt': bh.clip(it['text'], 20)})
    return todo


def keepnext_gate(items, pd, P, wanted):
    """在 plan_keepnext 的候选列表上模拟长链闸（pagination.forbid_long_chains / max_keep_next_chain），
    按段落顺序依次假设“已设置”推进链长，拆成 (allowed, blocked)：allowed 是安全可设的（保持原相对顺序），
    blocked 会把所在链撑到超过上限。check 与 repair 都调用这同一个函数，口径一致——之前 check 把会被
    repair 挡掉的条目也算进可修待办，两边不一致（reverify minor n4）。"""
    flags = [bool(it['keepnext']) for it in items]
    max_chain = bh.cfg(pd, 'pagination.max_keep_next_chain', 20)
    forbid_long = bh.cfg(pd, 'pagination.forbid_long_chains', False)
    allowed, blocked = [], []
    for f in wanted:
        i = f['para']
        before_here = chain_len_at(flags, i)
        trial = list(flags)
        trial[i] = True
        after_here = chain_len_at(trial, i)
        if forbid_long and after_here > max_chain and after_here > before_here:
            blocked.append({'para': i, 'reason': '会把 keepNext 链撑到 %d 段（上限 %d，改前这条链 %d 段）'
                            % (after_here, max_chain, before_here)})
            continue
        allowed.append(f)
        flags[i] = True
    return allowed, blocked


def plan_toc(items, P, pdf_path):
    """返回 (todo, problems)：pdf_path 为空时不判定，todo 为空、problems 为空。"""
    ents, _ = bh.check_toc_docx(items, P, bh.Findings())
    if not pdf_path or not ents:
        return [], []
    dests, _, problems = toc_pdf_dests(pdf_path, ents, items, P)
    todo = []
    if not problems:
        for e, dest in zip(ents, dests):
            if dest is not None and e['cached'] != dest:
                todo.append({'para': e['it']['i'], 'label': e['label'], 'cached': e['cached'], 'pdf_dest': dest})
    return todo, problems


# ---------------------------------------------------------------- check
def do_check(args):
    pd = get_profile(args)
    P = bh.Prof(pd)
    items, tables = bh.read_docx(args.docx)
    blocks = bh.walk(items, P)
    F = bh.Findings()
    n_stat = bh.check_numbering(items, blocks, P, F)
    m_stat = bh.check_method_counts(items, P, F)
    k_stat = bh.check_keepnext(items, P, F)
    ents, toc_stat = bh.check_toc_docx(items, P, F)
    pdf_stat = None
    if args.pdf:
        import fitz
        doc = fitz.open(args.pdf)
        try:
            scan = bh.pdf_scan(doc, P)
            texts = bh.pdf_pages_text(scan)
            pdf_stat = bh.check_toc_pdf(doc, ents, items, P, F, texts)
        finally:
            doc.close()
    by = OrderedDict()
    for f in F.items:
        by.setdefault(f['check'], Counter())[f['level']] += 1

    # 本工具实际会改的“待办”，用 repair 同一套计划函数（不是 bh 的门结果）：check 与 repair 口径一致。
    todo_numbering = plan_numbering(items, P)
    todo_method = plan_method_counts(items, P)
    todo_keepnext_raw = plan_keepnext(items, pd, P)
    todo_keepnext, keepnext_blocked = keepnext_gate(items, pd, P, todo_keepnext_raw)
    toc_pdf_arg = args.toc_pdf or args.pdf
    same_version = None
    if toc_pdf_arg:
        # check 从不放行 --allow-unbound-pdf（那是 repair 的降级开关，check 只读、没必要替 repair 决定
        # “要不要采信对位率”）：identity!='match' 时 soft 分支恒返回 ok=False，但仍算出（双向）对位率
        # 供参考——diffs 本身照样算出来（跟 identity 是否证明无关），只是不采信的分支把它们从可修待办
        # 挪进 toc_version_problems，附带同版判定用的方法与对位率，供主代理判断要不要人工核实/用
        # --allow-unbound-pdf 重跑 repair。
        same_version, version_ok = prove_same_version(pd, P, args.docx, toc_pdf_arg,
                                                       bh.sha256(args.docx), bh.sha256(toc_pdf_arg), soft=True)
        diffs, structural_problems = plan_toc(items, P, toc_pdf_arg)
        if version_ok:
            todo_toc, toc_problems = diffs, structural_problems
        else:
            todo_toc = []
            toc_problems = list(structural_problems)
            if diffs:
                toc_problems.append(OrderedDict([
                    ('reason', '目录同版闸未证明同版（%s），以下页码差异不计入可修待办，不采信对位率'
                              % (same_version.get('reason') or same_version.get('identity'))),
                    ('identity', same_version.get('identity')),
                    ('method', same_version.get('method')),
                    ('align_ratio', same_version.get('align_ratio')),
                    ('reverse_align_ratio', same_version.get('reverse_align_ratio')),
                    ('threshold', same_version.get('threshold')),
                    ('diff_count', len(diffs)),
                    ('diffs', diffs[:args.max_items]),
                ]))
    else:
        todo_toc, toc_problems = [], []
    plan = OrderedDict([
        ('numbering', todo_numbering[:args.max_items]),
        ('method_counts', todo_method[:args.max_items]),
        ('keepnext', todo_keepnext[:args.max_items]),
        ('toc', todo_toc[:args.max_items]),
    ])
    plan_count = {k: len(v) for k, v in
                  (('numbering', todo_numbering), ('method_counts', todo_method),
                   ('keepnext', todo_keepnext), ('toc', todo_toc))}
    # toc_version_problems 不是“本工具能改的”（要么身份没证明、要么结构性问题），按规格不计入可修 pending，
    # 只在报告里如实列出；pending 恒等于四类计划项之和（跟“repairable”这个名字对上）。
    repairable_pending = sum(plan_count.values())
    blocked_count = {'keepnext': len(keepnext_blocked)}
    blocked_total = sum(blocked_count.values())

    rep = OrderedDict()
    rep['tool'] = OrderedDict([('name', 'layout_prepare'), ('version', TOOL_VERSION), ('mode', 'check')])
    rep['profile'] = OrderedDict([('book_id', pd.get('book_id')), ('frozen', bool(pd.get('frozen')))])
    rep['inputs'] = OrderedDict([('docx', OrderedDict([('path', str(Path(args.docx).resolve())),
                                                       ('sha256', bh.sha256(args.docx)), ('paragraphs', len(items))]))])
    if args.pdf:
        rep['inputs']['pdf'] = OrderedDict([('path', str(Path(args.pdf).resolve())), ('sha256', bh.sha256(args.pdf))])
    if args.toc_pdf:
        rep['inputs']['toc_pdf'] = OrderedDict([('path', str(Path(args.toc_pdf).resolve())), ('sha256', bh.sha256(args.toc_pdf))])
    rep['stats'] = OrderedDict([('numbering', n_stat), ('method_counts', m_stat), ('keepnext', k_stat),
                                ('toc', toc_stat)] + ([('toc_pdf', pdf_stat)] if pdf_stat else []))
    rep['gate_counts_bh_reference'] = {k: dict(v) for k, v in by.items()}  # bh 的门结果，只作参考，不是本工具口径
    rep['repairable_plan'] = plan
    rep['repairable_plan_count'] = plan_count
    if same_version is not None:
        rep['pdf_same_version'] = same_version
    rep['toc_version_problems'] = toc_problems
    rep['blocked'] = {'keepnext': keepnext_blocked[:args.max_items]}
    rep['blocked_count'] = blocked_count
    # keepNext 长链闸：check 与 repair 的退出码口径必须一致——repair --keepnext 遇到 blocked 且没有
    # --allow-blocked 会整批 Abort(2)，check 不能因为这些候选不算“可修待办”就报 exit 0，让主代理误以为
    # 能直接跑 repair（reverify minor：check/repair 长链闸退出码不一致）。
    rep['blocked_note'] = ('有 %d 项会被长链闸挡住，repair 将中止（除非显式加 --allow-blocked）' % blocked_total
                           if blocked_total else None)
    # toc_version_problems 虽不计入 repairable_pending（本工具改不了、要么身份没证明、要么结构性问题），
    # 但不能让 check 因此 exit 0：那样主代理会误以为目录无需处理。这里单独计入退出码判断（同 pending、
    # blocked_total 一样），并给出 toc_note 说明降级路径（reverify major：check exit 0 未把
    # toc_version_problems 算进去，与 repair --toc 因同一输入 exit 2 的口径不一致）。
    toc_version_total = len(toc_problems)
    rep['toc_note'] = ('目录页码与所给 PDF 不符，但该 PDF 未经同版身份绑定：请用 render_book.py 渲染出'
                       '带身份记录的 PDF，或 repair 时显式 --allow-unbound-pdf' if toc_version_total else None)
    rep['pending'] = repairable_pending
    rep['findings'] = F.items[:args.max_items]
    rep['findings_total'] = len(F.items)
    write_report(guard_report(args, pd), rep)
    print(json.dumps({'pending': rep['pending'], 'repairable_plan_count': plan_count,
                      'blocked_count': blocked_count, 'blocked_note': rep['blocked_note'],
                      'toc_version_problems': toc_problems, 'toc_note': rep['toc_note']}, ensure_ascii=False))
    return 1 if (rep['pending'] or blocked_total or toc_version_total) else 0


# ---------------------------------------------------------------- repair
def do_repair(args):
    ops = {'numbering': args.numbering, 'method_counts': args.method_counts,
           'keepnext': args.keepnext, 'toc': args.toc}
    if not any(ops.values()):
        raise Abort(2, '至少要点名一种操作：--numbering / --method-counts / --keepnext / --toc')
    if args.toc and not args.toc_pdf:
        raise Abort(2, '--toc 需要 --toc-pdf（同版 PDF，用于落页匹配）')
    if getattr(args, 'allow_unbound_pdf', None) is not None and not args.allow_unbound_pdf.strip():
        raise Abort(2, '--allow-unbound-pdf 需要给出非空的理由文本')
    pd = get_profile(args)
    if pd.get('frozen'):
        raise Abort(3, '%s 已冻结，拒绝写出：%s' % (pd.get('title', pd.get('book_id')), pd.get('frozen_note', '')))
    P = bh.Prof(pd)

    # 报告目标在动手写任何东西之前先过守卫，避免“写了 DOCX 才发现报告路径被拒”留下半成品。
    report_out = guard_report(args, pd)

    d = dl.open_docx(args.docx, expect_sha256=args.expect_sha)
    bh.walk(d.items, P)  # 给每个 it 标注 part/node/method/ex 等，true_numbering/check_* 都要用
    out = dl.guard_write(args.out, pd, inputs=[args.docx] + ([args.toc_pdf] if args.toc_pdf else []), kind='.docx')

    # 批量误改保护：--docx 不落在任何登记书册目录下（detect_profile 判空，通常是拿别的书稿硬套了
    # --profile）时，若计划编号改动比例过高、或有考法题数将归零，很可能是配置用错了，整批中止（不受
    # --allow-blocked 影响，只认 --allow-mass-renumber）；命中已登记书册目录的正常用法不受影响。
    try:
        registered_book = detect_profile(args.docx) is not None
    except Exception:
        registered_book = False
    numbering_todo = plan_numbering(d.items, P) if ops['numbering'] else []
    method_todo = plan_method_counts(d.items, P) if ops['method_counts'] else []
    mass_risk, mass_reason = False, None
    if not registered_book:
        total_titles = len(true_numbering(d.items, P))
        ratio = (len(numbering_todo) / total_titles) if total_titles else 0.0
        zero_method = [t for t in method_todo if t['actual'] == 0]
        if ops['numbering'] and total_titles and ratio > 0.10:
            mass_risk = True
            mass_reason = ('计划编号改动 %d/%d（%.1f%%）超过 10%%' % (len(numbering_todo), total_titles, ratio * 100))
        if ops['method_counts'] and zero_method:
            mass_risk = True
            extra = '%d 处考法实际题数将归零' % len(zero_method)
            mass_reason = (mass_reason + '；' + extra) if mass_reason else extra
    if mass_risk and not getattr(args, 'allow_mass_renumber', False):
        raise Abort(2, '批量误改保护：--docx 未落在任何登记书册目录下（detect_profile 判空），且%s，'
                    '疑似误套了别的书册的配置，整批中止、不写输出（确需继续，显式传 --allow-mass-renumber；'
                    '--allow-blocked 不放行这一条）' % mass_reason)

    # 原始 document.xml 的独立副本：证明“未点名段落没动”要跟这份比，不能跟改过之后的树自己比自己。
    before_root = etree.fromstring(d.doc_xml_orig)
    before_body = before_root.find(W + 'body')
    before_paras = dl.para_elements(before_body)

    touched = set()
    changes = OrderedDict([(k, []) for k in ops if ops[k]])
    blocked = OrderedDict([(k, []) for k in ops if ops[k]])

    if ops['numbering']:
        for t in numbering_todo:
            i = t['para']
            it, p = d.items[i], d.paras[i]
            if has_tab_or_sym(p):
                blocked['numbering'].append({'para': i, 'reason': '段内含 w:tab/w:sym，w:t 坐标系与判定文字不一致'})
                continue
            tt = t_text(p)
            span = num_span_in_ttext(P, it, tt)
            if not span:
                blocked['numbering'].append({'para': i, 'reason': '重新匹配标题正则未取到编号 span'})
                continue
            uneven = replace_span_digits(p, span[0], span[1], str(t['new']))
            touched.add(i)
            entry = OrderedDict(t)
            if uneven:
                entry['cross_run_digits_redistributed'] = True
            changes['numbering'].append(entry)

    if ops['method_counts']:
        for t in method_todo:
            i = t['para']
            it, p = d.items[i], d.paras[i]
            if t['actual'] == 0:
                blocked['method_counts'].append({'para': i, 'reason': '考法实际题数算出 0，判定信号可疑，不自动回填'})
                continue
            if has_tab_or_sym(p):
                blocked['method_counts'].append({'para': i, 'reason': '段内含 w:tab/w:sym，w:t 坐标系与判定文字不一致'})
                continue
            tt = t_text(p)
            span = method_count_span_in_ttext(P, tt)
            if not span:
                blocked['method_counts'].append({'para': i, 'reason': '重新匹配考法计数正则未取到数字 span'})
                continue
            uneven = replace_span_digits(p, span[0], span[1], str(t['actual']))
            touched.add(i)
            entry = OrderedDict(t)
            if uneven:
                entry['cross_run_digits_redistributed'] = True
            changes['method_counts'].append(entry)

    if ops['keepnext']:
        wanted = plan_keepnext(d.items, pd, P)
        before_lens = keepnext_chain_lengths([bool(it['keepnext']) for it in d.items])
        allowed, blocked_kn = keepnext_gate(d.items, pd, P, wanted)  # check 用同一个函数算 blocked，口径一致
        blocked['keepnext'].extend(blocked_kn)
        flags = [bool(it['keepnext']) for it in d.items]
        for f in allowed:
            i = f['para']
            if set_keep_next_true(d.paras[i]):
                flags[i] = True
                touched.add(i)
                changes['keepnext'].append({'para': i, 'rule': f['rule'], 'text': f.get('excerpt')})
        after_lens_final = keepnext_chain_lengths(flags)
        changes['keepnext_chain_lengths'] = {'before': dict(Counter(before_lens)), 'after': dict(Counter(after_lens_final))}

    same_version = None
    if ops['toc']:
        ents, _ = bh.check_toc_docx(d.items, P, bh.Findings())
        if not ents:
            raise Abort(2, '本册未识别出任何目录条目（toc.styles 是否配对？）')
        # 目录同版闸：证明 --toc-pdf 确由 --docx 渲染，不通过就整批中止（不写输出），见 prove_same_version。
        # 没有同版身份记录时缺省中止，--allow-unbound-pdf 才降级到双向对位率兜底（仍可能因对位率不达标中止）。
        same_version, _ = prove_same_version(pd, P, args.docx, args.toc_pdf, d.sha256, bh.sha256(args.toc_pdf),
                                             soft=False, allow_unbound=getattr(args, 'allow_unbound_pdf', None))
        dests, n_links, problems = toc_pdf_dests(args.toc_pdf, ents, d.items, P)
        if problems:
            raise Abort(2, '目录与同版 PDF 版本不匹配，拒绝回填（不写输出）：' + '；'.join(problems[:6]))
        mode = bh.cfg(pd, 'toc.mode', 'pageref_in_hyperlink')
        for e, dest in zip(ents, dests):
            i = e['it']['i']
            if e['cached'] == dest:
                continue
            p = d.paras[i]
            nodes = toc_page_nodes(p, mode)
            if len(nodes) != 1 or not re.fullmatch(r'\s*\d+\s*', nodes[0].text or '') or int(nodes[0].text) != e['cached']:
                blocked['toc'].append({'para': i, 'label': e['label'],
                                       'reason': '段内缓存页码数字节点定位失败（须恰好 1 个且等于目录条目 cached=%s）' % e['cached']})
                continue
            node = nodes[0]
            old = (node.text or '').strip()
            new = str(dest)
            node.text = re.sub(r'\d+', new, node.text)
            touched.add(i)
            changes['toc'].append({'para': i, 'label': e['label'], 'old': old, 'new': new,
                                   'digits_changed': len(new) != len(old)})

    # blocked 非空按规格判失败：不留输出（--allow-blocked 时放行，仍如实记录）。
    blocked_total = sum(len(v) for v in blocked.values())
    if blocked_total and not args.allow_blocked:
        raise Abort(2, '定位被跳过（blocked，共 %d 处），按规格判失败，不写输出（--allow-blocked 可放行）：%r'
                    % (blocked_total, {k: v[:3] for k, v in blocked.items() if v}))

    # “未点名段落没动”核对：跟打开时的原始副本比，不是跟改过的树自己比。
    bad = dl.unchanged_paragraphs(before_paras, d.paras, touched, touched)
    if bad:
        raise Abort(2, '未点名段落指纹不一致（异常，见细节）：%r' % bad[:5])

    receipt = dl.write_docx(d, out)
    out_path = Path(receipt['out'])

    def fail_after_write(code, msg):
        raise Abort(code, msg)

    # 写出之后的整段复核与写报告都包在这层里：任何异常（不只是上面几个显式判定失败，也包括写后重读
    # PDF/DOCX 崩溃、--health 的 bh.run_health 抛异常、write_report 的 OSError 等）都先删掉已写出的
    # DOCX 再往外抛，不留半成品（reverify major：写后失败清理不完整，此前只有 fail_after_write 的分支删）。
    try:
        # 写后复核：重新解析输出，再做一次“未点名段落没动”，并对每个点名的门重跑判定，不依赖可选的 --health。
        d2 = dl.open_docx(str(out_path))
        bad2 = dl.unchanged_paragraphs(before_paras, d2.paras, touched, touched)
        if bad2:
            fail_after_write(1, '写后复核：未点名段落指纹不一致，已删除输出：%r' % bad2[:5])
        P2 = bh.Prof(pd)
        bh.walk(d2.items, P2)
        if ops['numbering']:
            want2 = true_numbering(d2.items, P2)
            bad_num = sorted(i for i, exp in want2.items() if d2.items[i]['_title']['num'] != exp
                             if i not in {b['para'] for b in blocked['numbering']})
            if bad_num:
                fail_after_write(1, '写后编号仍不连号，已删除输出：段 %r' % bad_num[:10])
        if ops['method_counts']:
            F2 = bh.Findings()
            bh.check_method_counts(d2.items, P2, F2)
            skip_paras = {b['para'] for b in blocked['method_counts']}
            remaining = [f for f in F2.items if f['level'] == 'FAIL' and f['where']['para'] not in skip_paras]
            if remaining:
                fail_after_write(1, '写后考法题数仍有 FAIL，已删除输出：%d 处' % len(remaining))
        if ops['keepnext']:
            F2 = bh.Findings()
            bh.check_keepnext(d2.items, P2, F2)
            skip_paras = {b['para'] for b in blocked['keepnext']}
            remaining = [f for f in F2.items if f['level'] == 'WARN' and f['where']['para'] not in skip_paras]
            if remaining:
                fail_after_write(1, '写后仍有未补 keepNext，已删除输出：%d 处' % len(remaining))
        if ops['toc']:
            ents2, _ = bh.check_toc_docx(d2.items, P2, bh.Findings())
            dests2, _, problems2 = toc_pdf_dests(args.toc_pdf, ents2, d2.items, P2)
            skip_paras = {b['para'] for b in blocked['toc']}
            mismatches2 = [e for e, dst in zip(ents2, dests2)
                          if dst is not None and e['cached'] != dst and e['it']['i'] not in skip_paras]
            if problems2 or mismatches2:
                fail_after_write(1, '写后目录页码与同版 PDF 落页仍不一致，已删除输出：%d 处' % len(mismatches2))

        pre_health = post_health = None
        regressed = []
        if args.health:
            pre_health = bh.run_health(args.docx, profile=pd)
            post_health = bh.run_health(str(out_path), profile=pd)
            pre_by = {g['check']: g['counts'].get('FAIL', 0) for g in pre_health['gates']}
            for g in post_health['gates']:
                base = pre_by.get(g['check'], 0)
                now = g['counts'].get('FAIL', 0)
                if now > base:
                    regressed.append({'check': g['check'], 'before_FAIL': base, 'after_FAIL': now})
            if regressed:
                fail_after_write(1, '写后体检比输入新增 FAIL，已删除输出：%r' % regressed[:5])

        needs_rerender = any(c.get('digits_changed') for c in changes.get('toc', []))
        if needs_rerender:
            say('WARN：目录页码位数变化，需重渲以确认排版（changes.toc 里 digits_changed=true 的条目）')

        rep = OrderedDict()
        rep['tool'] = OrderedDict([('name', 'layout_prepare'), ('version', TOOL_VERSION), ('mode', 'repair')])
        rep['profile'] = OrderedDict([('book_id', pd.get('book_id')), ('frozen', bool(pd.get('frozen')))])
        rep['inputs'] = OrderedDict([('docx', OrderedDict([('path', str(Path(args.docx).resolve())), ('sha256', d.sha256)]))])
        if args.toc_pdf:
            rep['inputs']['toc_pdf'] = OrderedDict([('path', str(Path(args.toc_pdf).resolve())), ('sha256', bh.sha256(args.toc_pdf))])
        rep['parent_sha_checked'] = bool(args.expect_sha)
        if not args.expect_sha:
            say('WARN：未传 --expect-sha，未核对父稿 SHA')
        rep['book_registered'] = registered_book
        rep['mass_renumber_risk'] = mass_risk
        rep['mass_renumber_allowed'] = bool(getattr(args, 'allow_mass_renumber', False))
        rep['output'] = receipt
        rep['ops'] = OrderedDict((k, True) for k in ops if ops[k])
        if same_version is not None:
            rep['pdf_same_version'] = same_version
        rep['changes'] = changes
        rep['changes_count'] = {k: len(v) for k, v in changes.items() if isinstance(v, list)}
        rep['blocked'] = blocked
        rep['blocked_allowed'] = bool(args.allow_blocked)
        rep['touched_paragraphs'] = sorted(touched)
        rep['needs_rerender'] = needs_rerender
        if args.health:
            rep['health_regressions'] = regressed
        write_report(report_out, rep)
    except BaseException:
        try:
            out_path.unlink()
        except OSError:
            pass
        raise
    print(json.dumps({'out': receipt['out'], 'sha256': receipt['sha256'],
                      'changes_count': rep['changes_count'], 'blocked_count': {k: len(v) for k, v in blocked.items()}},
                     ensure_ascii=False))
    return 0


def _is_own_report(p):
    try:
        j = json.loads(Path(p).read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return False
    return isinstance(j, dict) and isinstance(j.get('tool'), dict) and j['tool'].get('name') == 'layout_prepare'


def guard_report(args, pd):
    """报告输出守卫：路径规则与 --out 同一套，一律过 docx_lib.guard_write(kind='.json')——受保护根
    （各册 paths.root、Skill 目录、output_guard.protected_roots）内只许 “…/协作/候选/<谁>/<批次>/构建/” 之下，
    否则只许系统临时目录；冻结册目录、与输入同一文件都拒绝；路径先 resolve，符号链接按真实落点判断。
    只在两点上放宽/收紧：① 传入去掉 frozen 标志的配置副本，冻结册的 check 仍能把报告写进临时目录
    （冻结册目录本身仍由 guard_write 内的 _frozen_hits 拒绝）；② 目标已存在时只允许覆盖本工具自己写的
    报告，不覆盖 batch_health 报告或其他文件。
    （2026-09-24 返修：上一版自成一套、只拦冻结册目录，--report 可经符号链接写进必修三审阅入口，真实留下过
    00_必修三最新审查稿/__verify_never_written__.json。）返回解析后的 Path，或 args.report 为空时返回 None。"""
    if not args.report:
        return None
    out = Path(args.report).expanduser().resolve()
    if out.suffix.lower() != '.json':
        raise Abort(3, '报告输出必须是 .json 文件：%s' % out.name)
    if out.exists() and (not out.is_file() or not _is_own_report(out)):
        raise Abort(3, '目标已存在且不是本工具自己写的报告，拒绝覆盖：%s' % out)
    inputs = [args.docx, getattr(args, 'pdf', None), getattr(args, 'toc_pdf', None)]
    try:
        return dl.guard_write(out, dict(pd or {}, frozen=False), inputs=inputs, kind='.json', overwrite=out.exists())
    except dl.GuardError as e:
        raise Abort(3, '报告输出被拒：%s' % e)


def write_report(out, rep):
    """临时文件改用 tempfile.mkstemp（同目录、随机名）：固定名 .<name>.tmp 若被预先放一个指向受保护文件
    的符号链接占位，write_text 会跟着链接把内容写进链接目标，guard_report 只查过最终路径，查不到这个
    临时路径——mkstemp 每次生成一个此前不存在的随机文件名并以 O_CREAT|O_EXCL 建它，不会踩中现有链接。"""
    if out is None:
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix='.' + out.name + '.', suffix='.tmp', dir=str(out.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
        os.replace(tmp_name, str(out))
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--debug', action='store_true', help='出错时打印原始 traceback')
    sub = ap.add_subparsers(dest='cmd', required=True)

    c = sub.add_parser('check', help='只读检查')
    c.add_argument('--docx', required=True)
    c.add_argument('--pdf')
    c.add_argument('--toc-pdf', dest='toc_pdf')
    c.add_argument('--profile')
    c.add_argument('--report')
    c.add_argument('--max-items', type=int, default=60)

    r = sub.add_parser('repair', help='按点名操作写出候选 DOCX')
    r.add_argument('--docx', required=True)
    r.add_argument('--out', required=True)
    r.add_argument('--profile')
    r.add_argument('--expect-sha')
    r.add_argument('--numbering', action='store_true')
    r.add_argument('--method-counts', dest='method_counts', action='store_true')
    r.add_argument('--keepnext', action='store_true')
    r.add_argument('--toc', action='store_true')
    r.add_argument('--toc-pdf', dest='toc_pdf')
    r.add_argument('--allow-unbound-pdf', dest='allow_unbound_pdf', metavar='理由',
                   help='--toc-pdf 没有同版身份记录（identity!=match）时缺省整批中止；传入非空理由文本'
                        '可降级放行，但仍要求双向正文对位率≥toc.pdf_align_min，且页码可能与最终分页不符'
                        '（写 WARN 到 stderr，报告标 pdf_same_version_proven=false）；身份记录冲突'
                        '（docx_mismatch/pdf_mismatch）不受这个开关影响，一律拒绝')
    r.add_argument('--allow-blocked', action='store_true', help='定位被跳过时仍放行写出（缺省视为失败、不留输出）')
    r.add_argument('--allow-mass-renumber', dest='allow_mass_renumber', action='store_true',
                   help='--docx 未落在任何登记书册目录下且计划改动比例过高/考法题数将归零时，仍放行写出'
                        '（--allow-blocked 不放行这一条，只认这个）')
    r.add_argument('--health', action='store_true', help='写后再额外对输入与输出各跑一遍 bh.run_health 比较全部门')
    r.add_argument('--report')

    args = ap.parse_args()
    t0 = time.time()
    try:
        if args.cmd == 'check':
            code = do_check(args)
        else:
            code = do_repair(args)
    except Abort as e:
        say('%s（%.1fs）' % (e, time.time() - t0))
        if args.debug:
            traceback.print_exc()
        return e.code
    except dl.ParentMismatch as e:
        say(str(e))
        if args.debug:
            traceback.print_exc()
        return 2
    except dl.GuardError as e:
        say(str(e))
        if args.debug:
            traceback.print_exc()
        return 3
    except (dl.AlignmentError, ValueError, KeyError, OSError) as e:
        say('输入或配置错误：%s' % e)
        if args.debug:
            traceback.print_exc()
        return 2
    except Exception as e:  # noqa: BLE001
        say('内部错误：%s' % e)
        if args.debug:
            traceback.print_exc()
        return 2
    return code


if __name__ == '__main__':
    sys.exit(main())
