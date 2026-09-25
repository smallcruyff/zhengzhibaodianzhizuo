#!/usr/bin/env python3
"""按已批准的补丁 JSON 写 DOCX——写书侧通用工具之一（流程优化线 2026-09-24）。

用途：
    把补丁作者（主代理或 Codex）判定好的一组段落级修改，从"决定"机械落地成 XML 改动，
    不做任何认题块/判词对错/取舍细则之类的教学判断——那些仍由 batch_health 的判定与人
    工/模型审阅完成。本工具只回答"这条补丁能不能唯一、安全地落到这份 DOCX 上"。

用法：
    apply_patch.py check --docx 父稿.docx --patch p.json [--profile bixiu3] [--report r.json]
    apply_patch.py apply --docx 父稿.docx --patch p.json --out 候选.docx
                   [--profile bixiu3] [--report r.json] [--health]
    apply_patch.py diff  --old A.docx --new B.docx --out p.json [--book bixiu3] [--report r.json]

    --profile 缺省按 profile_lib.detect_profile(docx) 自动判断（也可用补丁里的 "book" 字段兜底）。
    冻结册：写模式下总是对输入稿本身重新 detect_profile，命中任何 frozen 配置一律拒绝（退出码 3），
        不看 --profile/补丁 book 字段怎么说。测试要在冻结册上走写路径，只能自己在临时目录放一份
        frozen=false 的配置副本，用 --profile 指向那份临时配置（load_profile 接受路径），不提供
        绕过真实配置的开关。

读写承诺：
    - 只新增/覆盖 --out 指定的 .docx、--report 指定的 .json；写出前一律经 docx_lib.guard_write()。
    - 只读父稿/父稿 A/B、补丁 JSON；不改 batch_health.py、docx_lib.py、profile_lib.py、profiles/。
    - 不联网、不调用 collab.py、不启子进程写文件。
    - 默认只检查（check、diff 均不写 docx；apply 未显式给 --out 时报错，不写任何文件）。

退出码：0 成功/无待办（check：全部 already_applied，没有可应用的改动；apply：写出且写后体检未新增 FAIL）；
    1 check 模式发现待处理的合法补丁（可以应用但尚未应用）；或 --health 后输出比输入多 FAIL；
    2 输入/配置错误、或补丁未通过校验而整批中止（父稿 SHA 不符、锚点 0/2 命中、old 不符、同段冲突、
      题面区未标 source_zone、新文字命中禁用词、已应用的 op 出现在 apply 里、结构过复杂且未 allow_complex 等）；
    3 拒绝写出（guard_write 守卫、冻结册、写权、输出与输入同一文件等）。
    异常一律转 clean 的中文错误信息打印到 stderr 并按上述退出码返回；--debug 打开时打印 traceback。

读取的配置字段（书册 profile，均已有默认值，找不到时用下列默认值；本工具目前不需要 profiles/ 增补新字段）：
    - styles.*、structure.*、example_titles、labels_rules.*、column_schemas、section_labels、hidden_labels、
      example_kind_by_labels、drill.* —— 全部转交 batch_health.Prof/walk 解释，本工具不重复实现判定。
    - student_text.engineering_tags / forbidden_words_common / forbidden_words_book / forbidden_word_groups
      —— 新文字过词表用；缺省即 _house.json 里的通用词表（batch_health 已在读，本工具原样复用）。
    - frozen / frozen_note —— 冻结册判定，交给 docx_lib.guard_write。
    默认值一律来自 batch_health.DEFAULTS（经 bh.cfg 兜底），本工具不自带一份重复的默认值表。

补丁格式（baodian_patch_v1）：
{
  "schema": "baodian_patch_v1", "book": "bixiu3", "parent_docx_sha256": "…（sha256_file 小写十六进制）",
  "approved_by": "claude:会话ID | codex:任务ID | user", "approval_ref": "台账编号或说明",
  "ops": [
    {"id": "P001", "op": "replace_text",
     "anchor": {"text": "…", "contains": "…", "style": "样式名或[样式名,…]",
                "prev": "…", "block": "…", "index_hint": 123},
     "old": "…", "new": "…", "reason": "…", "evidence": "…",
     "source_zone": "restore|approved_edit",           // 仅锚点落在 source/title 区时必须给
     "new_format": {"color": "FF0000", "bold": true}},  // 可选：让 new 单独成一个 run
    {"op": "replace_paragraph", "anchor": {...}, "old": "…", "new": "…", "allow_complex": false, ...},
    {"op": "insert_after"|"insert_before", "anchor": {...},
     "paragraphs": [{"text": "…", "style": "样式名", "clone_from": "另一段的定位子串",
                     "runs": [{"text": "…", "bold": true, "color": "FF0000"}]}], ...},
    {"op": "delete_paragraph", "anchor": {...}, "old": "…", "allow_complex": false, ...},
    {"op": "set_format", "anchor": {...}, "old": "…", "format": {"color": "FF0000", "bold": true}, ...},
    {"op": "set_keepnext", "anchor": {...}, "value": true, ...}
  ]
}

anchor 必须恰好命中一段：给 "text" 时按段落全文归一（bh.norm，去空白）后全等；给 "contains" 时按段内
原文子串（区分空白）唯一出现；两者都给时先按 text 缩小候选、contains 出现在其中再筛。可选 "style"
（样式名或样式名列表，与该段 w:pStyle 对应的 w:name 相符）、"prev"（上一段原文包含该子串）、"block"
（所在例题块标题包含该子串，判定用 bh.walk 的结果）进一步收窄；"index_hint" 只是消歧提示，不能替代
text/contains 单独定位——补丁不给 text 也不给 contains 时判定为补丁格式错误。0 段或多段命中都会让本条
op、进而整批中止；报告里按段号、样式、区位、前后文各列出候选，供补丁作者改锚点。

op 的安全规则见文件内 `check_ops()`；简述：所有 op 先在原稿上各自定位，互不依赖；同一段落上只允许互不
重叠的 replace_text/set_format 共存，其余组合判冲突；锚点段落落在 source/title 区（bh.walk 判的 zone）
时必须显式给 source_zone 与 reason；新文字（new/paragraphs[].text/runs[].text）一律过学生正文词表
（工程标签、house 与本册 forbidden_words、forbidden_word_groups），命中即整批中止，source_zone=="restore"
的 op 豁免；old 不在段内但 new 已恰好在段内 → 该 op 记 already_applied，apply 模式下整批中止（不做部分
重放），check 模式据此让本条不计入"待处理"。

表格结构（增删行列）不在 v1 范围内，遇到需要新增/删除表格行列的补丁一律按"结构过复杂"处理（op 中止），
写进 known_limits，留给 layout_prepare 或人工。
"""
import argparse
import copy
import difflib
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
from profile_lib import detect_profile, load_profile  # noqa: E402

TOOL_VERSION = '1.0.0'
W = bh.W
M = '{http://schemas.openxmlformats.org/officeDocument/2006/math}'
COMPLEX_TAGS = (W + 'drawing', W + 'bookmarkStart', W + 'fldSimple', W + 'fldChar', W + 'hyperlink',
                W + 'commentReference', W + 'commentRangeStart', W + 'commentRangeEnd',
                W + 'footnoteReference', W + 'endnoteReference', W + 'pict', W + 'object',
                W + 'ins', W + 'del', W + 'sectPr', M + 'oMath', M + 'oMathPara')


class Abort(Exception):
    """整批中止（退出码 2）：父稿不符、锚点问题、词表命中、结构过复杂……"""


class RefuseWrite(Exception):
    """拒绝写出（退出码 3）：冻结册、守卫、写权。"""


# ------------------------------------------------------------------ 基础：profile / 词表 / 区位
def _load_prof(args, patch):
    name = getattr(args, 'profile', None) or (patch or {}).get('book')
    if name:
        return load_profile(name)
    docx_path = getattr(args, 'docx', None) or getattr(args, 'old', None)
    pd = detect_profile(docx_path)
    if pd is None:
        raise Abort('无法判断书册：请用 --profile 指定，或在补丁 "book" 字段写明')
    return pd


def _forbidden_hit(text, tag_list, wlist, allow):
    # 第五轮 minor②：先按写后读回的口径（bh.ZW）去掉零宽字符再过词表——bh.norm/写后读回都会
    # translate(bh.ZW)，补丁作者把禁用词拆成"待​核"这样零宽字符插在词中间的写法，读回后
    # 学生看到的还是这个词，词表检查却因为零宽字符隔断了子串匹配而放行，见 final_apply_patch.json
    # minor（F3）。这里统一先去零宽字符，check 与写后复核共用这一个函数，口径自然一致。
    text = text.translate(bh.ZW)
    for g, w in wlist:
        q = text.find(w)
        if q >= 0 and not any(a in text for a in allow.get(w, [])):
            return g, w
    return None


def _new_texts_of(op):
    """一条 op 里全部"新文字"（要过词表的）。按拼接后的整段文字检查，不按单个 run——
    禁用词可能被补丁作者拆进多个 run（比如 runs:[{"text":"待"},{"text":"核"}]），
    逐 run 分别过词表会漏掉拼接后才出现的词。"""
    out = []
    if op['op'] in ('replace_text', 'replace_paragraph'):
        if 'new' in op:
            out.append(op['new'])
    elif op['op'] in ('insert_after', 'insert_before'):
        for para in op.get('paragraphs', []):
            if para.get('runs'):
                out.append(''.join(r.get('text', '') for r in para['runs']))
            elif 'text' in para:
                out.append(para['text'])
    return out


# ------------------------------------------------------------------ 锚点定位
def _style_name(styles_obj, p):
    """与 bh.read_docx 同口径：段落无显式 pStyle 时落到文档默认样式，否则按 styleId 查 w:name。"""
    pstyle = p.find(f'{W}pPr/{W}pStyle')
    sid = pstyle.get(W + 'val') if pstyle is not None else styles_obj.default_pstyle
    return styles_obj.name.get(sid, sid) if sid else '(默认)'


def _match_style(want, style_name):
    if want is None:
        return True
    wants = want if isinstance(want, list) else [want]
    return style_name in wants


def _build_text_index(paras):
    """归一文字 -> 段号列表，供 resolve_anchor 按 text 定位时不用整篇扫描。只对给了 text 的锚点生效，
    只给 contains 的锚点仍全篇扫描（数量通常远少于 diff 产出的 text 锚点）。"""
    idx = {}
    for i, p in enumerate(paras):
        idx.setdefault(bh.norm(dl.para_text(p)), []).append(i)
    return idx


def resolve_anchor(d, styles_obj, blocks, para_to_block, anchor, text_index=None):
    """在 d.paras（当前状态）里定位唯一一段，返回 (index, 候选描述列表)。命中数不为 1 时候选列表非空。"""
    text_want = anchor.get('text')
    contains_want = anchor.get('contains')
    if text_want is None and contains_want is None:
        raise Abort('anchor 必须给 text 或 contains 之一，不能只给 index_hint')
    if text_want == '' or contains_want == '':
        raise Abort('anchor 的 text/contains 不得为空串（空串会命中全书，等同于只按段号定位）')
    style_want = anchor.get('style')
    prev_want = anchor.get('prev')
    block_want = anchor.get('block')
    idx_hint = anchor.get('index_hint')
    cands = []
    n = len(d.paras)
    norm_want = bh.norm(text_want) if text_want is not None else None
    if text_want is not None and text_index is not None:
        candidate_idxs = text_index.get(norm_want, [])
    else:
        candidate_idxs = range(n)
    for i in candidate_idxs:
        p = d.paras[i]
        t = dl.para_text(p)
        if text_want is not None and bh.norm(t) != norm_want:
            continue
        if contains_want is not None and contains_want not in t:
            continue
        sname = _style_name(styles_obj, p)
        if not _match_style(style_want, sname):
            continue
        if prev_want is not None:
            if i == 0 or prev_want not in dl.para_text(d.paras[i - 1]):
                continue
        if block_want is not None:
            blk = para_to_block.get(i)
            if not blk or block_want not in (blk.get('title') or ''):
                continue
        cands.append({'index': i, 'style': sname, 'text': bh.clip(t, 60),
                       'prev': bh.clip(dl.para_text(d.paras[i - 1]), 40) if i else None})
    if len(cands) == 1:
        return cands[0]['index'], d.paras[cands[0]['index']], cands
    if len(cands) > 1 and idx_hint is not None:
        narrowed = [c for c in cands if c['index'] == idx_hint]
        if len(narrowed) == 1:
            return narrowed[0]['index'], d.paras[narrowed[0]['index']], cands
    return None, None, cands


# ------------------------------------------------------------------ 区位（复用 batch_health.walk）
def zones_of(d, prof_dict):
    """跑一遍 bh.walk，返回 (每段 zone 列表, 段号→所在例题块 dict)。只用来判"题面零改写"与 block 锚点。"""
    P = bh.Prof(prof_dict)
    blocks = bh.walk(d.items, P)
    zone = [it.get('zone') for it in d.items]
    para_to_block = {}
    for b in blocks:
        for i in b.get('paras', []):
            para_to_block[i] = b
        para_to_block[b['title_i']] = b
    return zone, para_to_block, blocks, P


# ------------------------------------------------------------------ 段落安全性
def _is_complex_paragraph(p):
    for tag in COMPLEX_TAGS:
        if p.find(f'.//{tag}') is not None:
            return True
    return False


_COMPLEX_PART_CATS = (
    ('hyperlink', (W + 'hyperlink',)),
    ('field', (W + 'fldSimple', W + 'fldChar')),
    ('bookmark', (W + 'bookmarkStart',)),
    ('image', (W + 'drawing', W + 'pict', W + 'object')),
    ('comment', (W + 'commentReference', W + 'commentRangeStart', W + 'commentRangeEnd')),
    ('note', (W + 'footnoteReference', W + 'endnoteReference')),
    ('other', (W + 'ins', W + 'del', W + 'sectPr', M + 'oMath', M + 'oMathPara')),
)


def _complex_parts(p):
    """段内复杂结构按类别计数（超链接/域/书签/图片/批注/脚注/其他），只用于报告和授权提示，
    不参与判定——判定仍是 _is_complex_paragraph 的有/无。"""
    out = {}
    for name, tags in _COMPLEX_PART_CATS:
        n = sum(len(p.findall(f'.//{t}')) for t in tags)
        if n:
            out[name] = n
    return out


def _structure_fingerprint(p):
    """replace_paragraph/delete_paragraph 改前改后的结构快照：复杂结构分类计数（超链接/域/…）、
    彩色 run 数、段内 tab 字符数——供 apply 报告逐条给出结构损失，不是"整批只报一个汇总数"。"""
    spans = _run_spans(p)
    colored = sum(1 for r, _ in spans if _run_fmt(r)[0])
    tabs = sum(t.count('\t') for _, t in spans)
    return {'complex_parts': _complex_parts(p), 'colored_runs': colored, 'tab_count': tabs}


def _run_fmt(r):
    """run 的 (color, bold) 二元组，None/False 表示未显式设置。"""
    rpr = r.find(W + 'rPr')
    if rpr is None:
        return (None, False)
    return (bh._color(rpr.find(W + 'color')), bool(bh._on(rpr.find(W + 'b'))))


_RUN_EXTRA_FMT_TAGS = (W + 'sz', W + 'szCs', W + 'rFonts', W + 'i', W + 'iCs', W + 'u',
                       W + 'strike', W + 'dstrike', W + 'vertAlign', W + 'spacing',
                       W + 'position', W + 'highlight', W + 'shd')


def _run_extra_fmt(r):
    """run 里除了颜色/加粗之外，本工具 runs 规格（text/bold/color）表达不了的格式
    （字号、字体、斜体、下划线等）。只用于 diff 报告里如实提醒"这段格式差异插入后会丢"，
    不参与判定。"""
    rpr = r.find(W + 'rPr')
    if rpr is None:
        return False
    return any(rpr.find(t) is not None for t in _RUN_EXTRA_FMT_TAGS)


def _format_matches(el, old, fmt):
    """el 段内 old 子串（须恰好命中 1 次）当前的 run 格式是否满足 fmt（color/bold）。"""
    spans = _run_spans(el)
    full = ''.join(t for _, t in spans)
    hits = _find_span(full, old)
    if len(hits) != 1:
        return False
    runs = _locate_runs(spans, hits[0], hits[0] + len(old))
    if not runs:
        return False

    def _one(r):
        color, bold = _run_fmt(r)
        ok = True
        if 'color' in fmt:
            ok = ok and color == fmt['color'].upper()
        if 'bold' in fmt:
            ok = ok and bold == bool(fmt['bold'])
        return ok
    return all(_one(r) for r, *_ in runs)


def _in_table_cell_alone(p):
    """该段是否是所在表格单元格里唯一的段落（删除会留空单元格，Word 不允许）。"""
    tc = p.getparent()
    while tc is not None and tc.tag != W + 'tc':
        tc = tc.getparent()
    if tc is None:
        return False
    return len([ch for ch in tc if ch.tag == W + 'p']) <= 1


# ------------------------------------------------------------------ run 级文字定位（跨 run 替换/置格式）
def _run_spans(p):
    """段内按 w:r 顺序取每个 run 贡献的纯文字（w:t/w:tab/w:sym，口径同 dl.para_text），
    跳过 mc:Fallback。返回 [(run_element, text)]；tab/sym 计入偏移但不支持作为替换/置格式的落点。"""
    skip = set()
    for fb in p.iter(bh.MC + 'Fallback'):
        skip.update(fb.iter())
    out = []
    for r in p.iter(W + 'r'):
        if skip and r in skip:
            continue
        buf = []
        for ch in r:
            if ch.tag == W + 't':
                buf.append(ch.text or '')
            elif ch.tag == W + 'tab':
                buf.append('\t')
            elif ch.tag == W + 'sym':
                buf.append(bh._sym_char(ch))
        out.append((r, ''.join(buf)))
    return out


def _find_span(full, old):
    """old 在 full 里的出现次数与位置；不做零宽字符处理（假定补丁作者从 dl.para_text 抄的原文）。"""
    idxs = [m.start() for m in re.finditer(re.escape(old), full)]
    return idxs


def _locate_runs(spans, start, end):
    """[start,end) 落在哪些 run 上；每项 (run, run_text, local_a, local_b)。要求全部落在 w:t 段（不跨 tab/sym）。"""
    out = []
    pos = 0
    for r, t in spans:
        a, b = pos, pos + len(t)
        pos = b
        if b <= start or a >= end:
            continue
        la, lb = max(0, start - a), min(len(t), end - a)
        out.append([r, t, la, lb])
    return out


def _has_tab_or_sym(r):
    return any(ch.tag in (W + 'tab', W + 'sym') for ch in r)


# run 只含 rPr 与 (0..n 个) w:t 时才是"简单 run"；含 w:br、w:tab、w:sym、脚注/批注引用、域字符等
# 其他子元素的 run 一律不参与 replace_text/set_format 的 run 级改写，直接中止，避免复制/清空时把这些
# 非文字子元素弄丢或弄重。
_RUN_SIMPLE_TAGS = (W + 'rPr', W + 't')


def _run_is_simple(r):
    return all(ch.tag in _RUN_SIMPLE_TAGS for ch in r)


def _emit_text(parent_run, text):
    """在 parent_run（一个 w:r）末尾按文字生成 w:t/<w:tab/> 序列——新文字里的 '\\t' 写成真正的
    <w:tab/> 元素，不写字面制表符（字面制表符落进 w:t 会被 Word 当普通字符显示，且下次 para_text()
    读回来的 '\\t' 其实来自不同的 XML 结构，两者不等价）。"""
    parts = text.split('\t')
    for i, part in enumerate(parts):
        if i > 0:
            bh.etree.SubElement(parent_run, W + 'tab')
        t = bh.etree.SubElement(parent_run, W + 't')
        t.text = part
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def _set_run_text(r, new_text):
    """清空 run 里已有的 w:t/w:tab/w:sym（run 已经过 _run_is_simple 校验，只含 rPr/w:t，
    但仍按三种标签一并清理以防万一），按新文字重建，tab 字符写成 <w:tab/>。"""
    for ch in list(r):
        if ch.tag in (W + 't', W + 'tab', W + 'sym'):
            r.remove(ch)
    _emit_text(r, new_text)


def _clone_run_with_format(run, fmt):
    new_r = copy.deepcopy(run)
    for t in new_r.findall(W + 't'):
        new_r.remove(t)
    rpr = new_r.find(W + 'rPr')
    from lxml import etree as _E
    if rpr is None:
        rpr = _E.Element(W + 'rPr')
        new_r.insert(0, rpr)
    if 'color' in fmt:
        c = rpr.find(W + 'color')
        if c is None:
            c = _E.SubElement(rpr, W + 'color')
        c.set(W + 'val', fmt['color'])
    if 'bold' in fmt:
        b = rpr.find(W + 'b')
        if fmt['bold']:
            if b is None:
                _E.SubElement(rpr, W + 'b')
        elif b is not None:
            rpr.remove(b)
    return new_r


def _already_applied_replace(full, old, new):
    """old 未直接命中时，判断该段是否已经是 old->new 替换一次后的状态。
    覆盖 new 本身包含 old 作为子串的情形（否则替换后 old 仍会在 new 内被"找到"，
    误判为待处理并再次改写）。"""
    if old == new:
        return False
    newhits = _find_span(full, new)
    if not newhits:
        return False
    if len(newhits) != 1:
        return False
    nh = newhits[0]
    oldhits = _find_span(full, old)
    if not oldhits:
        return True
    # old 命中都落在这唯一一处 new 的范围内，且是 new 内部本就含有的 old（而不是外部残留）→ 已应用
    if all(nh <= h < nh + len(new) for h in oldhits):
        return True
    return False


def _ws_norm(t):
    """段落读取口径（dl.para_text）固定会去掉两端空白、折叠零宽字符；补丁作者写的新文字若首尾
    带空白（比如全角空格缩进），写进 XML 后原样保留，但重新打开读回来时一定会被这一步削掉——
    这不是写坏了，是读取口径本身如此，写后自证比较前要先按同一口径归一，不能拿"归一前"的原文
    直接去比"归一后"的读回文字（那样任何首尾带空白的新文字都会被误判成 postcondition 失败，
    见 r3verify R8）。"""
    return t.translate(bh.ZW).strip()


def _ws_check(got, want_raw):
    """(ok, ws_lost)：ok 表示 got（段落读回来的文字）与 want_raw 按读取口径归一后一致；
    ws_lost 表示 want_raw 本身两端带空白（归一后确实会被削掉，值得在报告里如实提一句，
    不能不声不响地丢格式）。"""
    norm = _ws_norm(want_raw)
    return got == norm, norm != want_raw


def apply_replace_text(p, op, report_extra):
    spans = _run_spans(p)
    full = ''.join(t for _, t in spans)
    old, new = op['old'], op['new']
    hits = _find_span(full, old)
    if _already_applied_replace(full, old, new):
        report_extra['already_applied'] = True
        return
    if not hits:
        raise Abort(f'op {op.get("id")}：old 在段内未找到')
    if len(hits) > 1:
        raise Abort(f'op {op.get("id")}：old 在段内出现 {len(hits)} 次，无法唯一定位')
    start = hits[0]
    end = start + len(old)
    runs = _locate_runs(spans, start, end)
    if not runs:
        raise Abort(f'op {op.get("id")}：old 落点定位失败')
    if any(_has_tab_or_sym(r) for r, *_ in runs):
        raise Abort(f'op {op.get("id")}：old 跨制表符/符号字符，本工具 v1 不支持')
    if any(not _run_is_simple(r) for r, *_ in runs):
        raise Abort(f'op {op.get("id")}：落点所在 run 结构复杂（脚注/批注/域等），本工具 v1 不支持')
    cross_run = len(runs) > 1
    if cross_run:
        rprs = [bh.etree.tostring(r.find(W + 'rPr')) if r.find(W + 'rPr') is not None else b'' for r, *_ in runs]
        report_extra['cross_run'] = True
        report_extra['cross_run_format_uniform'] = len(set(rprs)) <= 1
        report_extra['runs_touched'] = len(runs)
        # 逐 run 格式（供报告看清跨了几种格式）；被完全吞掉的中间 run（文字整段消失，不只是被截断）
        # 单列出来，带上它本来的文字和格式——这段文字之后不会再出现在任何 run 里。
        report_extra['run_formats'] = [{'color': c, 'bold': b} for r, *_ in runs for c, b in [_run_fmt(r)]]
        report_extra['swallowed_runs'] = [
            {'text': t, 'color': c, 'bold': b}
            for r, t, *_ in runs[1:-1] for c, b in [_run_fmt(r)]
        ]
    new_format = op.get('new_format')
    first_r, first_t, fa, fb = runs[0]
    last_r, last_t, la, lb = runs[-1]
    before = first_t[:fa]
    after = last_t[lb:]
    same_run = not cross_run  # first_r is last_r
    # 保留原 run 的格式（rPr），供 new_format 分支里 after 段落另起一个"原格式" run 使用
    orig_rpr = copy.deepcopy(first_r.find(W + 'rPr')) if first_r.find(W + 'rPr') is not None else None
    if new_format:
        new_run = _clone_run_with_format(first_r, new_format)
        _emit_text(new_run, new)
        _set_run_text(first_r, before)
        first_r.addnext(new_run)
        if same_run:
            # old 后面还有文字（after），且它和 before 同属一个 run：另起一个与原 run 同格式的 run 承接
            if after:
                after_run = copy.deepcopy(first_r)
                for t_ in after_run.findall(W + 't'):
                    after_run.remove(t_)
                # 清掉可能残留的非文字子元素引用后按原 rPr 重建
                for ch in list(after_run):
                    if ch.tag != W + 'rPr':
                        after_run.remove(ch)
                if orig_rpr is not None and after_run.find(W + 'rPr') is None:
                    after_run.append(copy.deepcopy(orig_rpr))
                _set_run_text(after_run, after)
                new_run.addnext(after_run)
        else:
            _set_run_text(last_r, after)
            for r, *_ in runs[1:-1]:
                _set_run_text(r, '')
    else:
        if same_run:
            _set_run_text(first_r, before + new + after)
        else:
            _set_run_text(first_r, before + new)
            _set_run_text(last_r, after)
            for r, *_ in runs[1:-1]:
                _set_run_text(r, '')
    report_extra['runs_touched'] = len(runs)
    # 自证 postcondition：改后整段文字必须恰好等于"按 old→new 替换一次"的结果，一个字都不能多丢或漏留
    expected = full[:start] + new + full[end:]
    got = ''.join(t for _, t in _run_spans(p))
    if got != expected:
        raise Abort(f'op {op.get("id")}：写后整段文字与期望不符（疑似丢字/多字），已中止')


def apply_set_format(p, op):
    spans = _run_spans(p)
    full = ''.join(t for _, t in spans)
    old = op['old']
    hits = _find_span(full, old)
    if not hits:
        raise Abort(f'op {op.get("id")}：old 在段内未找到')
    if len(hits) > 1:
        raise Abort(f'op {op.get("id")}：old 在段内出现 {len(hits)} 次，无法唯一定位')
    start, end = hits[0], hits[0] + len(old)
    runs = _locate_runs(spans, start, end)
    if any(_has_tab_or_sym(r) for r, *_ in runs):
        raise Abort(f'op {op.get("id")}：old 跨制表符/符号字符，本工具 v1 不支持')
    if any(not _run_is_simple(r) for r, *_ in runs):
        raise Abort(f'op {op.get("id")}：落点所在 run 结构复杂（脚注/批注/域等），本工具 v1 不支持')
    fmt = op['format']
    from lxml import etree as _E
    new_runs = []
    for r, t, a, b in runs:
        before, mid, after = t[:a], t[a:b], t[b:]
        if before:
            r0 = copy.deepcopy(r)
            _set_run_text(r0, before)
            new_runs.append(r0)
        rm = _clone_run_with_format(r, fmt)
        _set_run_text(rm, mid)
        new_runs.append(rm)
        if after:
            r1 = copy.deepcopy(r)
            _set_run_text(r1, after)
            new_runs.append(r1)
    anchor_el = runs[0][0]
    for nr in new_runs:
        anchor_el.addprevious(nr)
    for r, *_ in runs:
        r.getparent().remove(r)


def _first_text_run(p):
    """段内第一个含 w:t 的 run（跨 w:hyperlink 等容器查找，取规格原意的"首个文字 run"，
    不是"段落第一个直接子 w:r"——目录行这类 run 都包在 w:hyperlink 里，直接子查找会找不到，
    导致 rPr 全部丢掉、颜色变白）。"""
    for r in p.iter(W + 'r'):
        if r.find(W + 't') is not None:
            return r
    return None


def apply_replace_paragraph(p, op):
    if _is_complex_paragraph(p) and not op.get('allow_complex'):
        raise Abort(f'op {op.get("id")}：段落含图片/书签/域/超链接，结构过复杂，未给 allow_complex')
    old = dl.para_text(p)
    new = op['new']
    if old != op['old']:
        if old == new:
            return 'already_applied'
        raise Abort(f'op {op.get("id")}：old 与段落全文不等')
    from lxml import etree as _E
    first_r = _first_text_run(p)
    rpr = copy.deepcopy(first_r.find(W + 'rPr')) if first_r is not None and first_r.find(W + 'rPr') is not None else None
    for ch in list(p):
        if ch.tag != W + 'pPr':
            p.remove(ch)
    r = _E.SubElement(p, W + 'r')
    if rpr is not None:
        r.append(rpr)
    _emit_text(r, new)
    return None


def apply_delete_paragraph(p, op):
    if _is_complex_paragraph(p) and not op.get('allow_complex'):
        raise Abort(f'op {op.get("id")}：段落含图片/书签/域/超链接，结构过复杂，未给 allow_complex')
    if _in_table_cell_alone(p):
        raise Abort(f'op {op.get("id")}：是所在表格单元格唯一段落，删除会留空单元格')
    old = dl.para_text(p)
    if old != op['old']:
        if old == '':
            return 'already_applied'
        raise Abort(f'op {op.get("id")}：old 与段落全文不等')
    p.getparent().remove(p)


def _resolve_style_id(styles_obj, name):
    """按样式名（w:name，补丁作者从 Word 界面上看到的名字）查 styleId；找不到即中止——
    不接受把样式名直接当 styleId 写进 w:pStyle（本册"宝典正文"这类样式名与其 styleId 不同，
    直接写名字会让 Word 退回默认样式，还被误判成命中了目标样式）。"""
    hits = [sid for sid, n in (styles_obj.name or {}).items() if n == name]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise Abort(f'insert：样式名 "{name}" 在 word/styles.xml 里找不到（须是 w:name，不是 styleId）')
    raise Abort(f'insert：样式名 "{name}" 命中 {len(hits)} 个 styleId，无法唯一解析：{hits}')


_REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def _parse_ppr_rpr_fragment(xml_str, tag):
    """校验并解析补丁自带的 ppr_xml/rpr_xml 原始片段（tag 是 'pPr' 或 'rPr'，第五轮 major①）。

    diff 为每个插入段的目标段落/每个 run 各带一份"整段原样格式"：ppr_xml 是目标段 w:pPr 的
    序列化，rpr_xml 是该 run w:rPr 的序列化；没有 pPr/rPr 时就是空串（不是缺字段，是确实没有）。
    apply 构建插入段时，spec/run 里带了这两个字段就原样使用，不再从锚点段继承 pPr/首个 run
    rPr——上一轮的漏洞正在这里：锚点没格式的新段会被"顺手"套上锚点的加粗/颜色/居中/缩进。
    手写补丁不带这两个字段时，_build_paragraph 仍走原来的锚点继承 + style/keep_next/
    bold/color 覆盖那一套，完全不受这个函数影响。

    校验只做三件事：根元素必须恰好是 w:pPr 或 w:rPr；树内不得出现 relationships 命名空间的
    引用属性（r:id/r:embed 等——这类引用跨文档搬不动，指向的关系可能在目标文档里根本不存在
    或指向别的东西）；不得含 w:sectPr（分节符不能靠插入段带进文档，会破坏分节结构）。三条
    任一不满足都 Abort，绝不静默丢弃字段退回旧的继承逻辑——静默降级会让补丁作者以为原样格式
    生效了，实际却又在悄悄套锚点格式，等于把这一轮要修的洞换个位置重开。空串直接判定"没有
    这个元素"，返回 None，调用方据此不给新段/新 run 附加 pPr/rPr。"""
    if not xml_str:
        return None
    from lxml import etree as _E
    want = W + tag
    try:
        el = _E.fromstring(xml_str.encode('utf-8') if isinstance(xml_str, str) else xml_str)
    except Exception as e:
        raise Abort(f'{tag}_xml 不是合法的 XML 片段：{e}')
    if el.tag != want:
        raise Abort(f'{tag}_xml 根元素必须是 {want}，实际是 {el.tag}')
    for node in el.iter():
        for attr in node.attrib:
            if attr.startswith(_REL_NS):
                raise Abort(f'{tag}_xml 含关系引用属性 {attr}，不允许（跨文档无法保证关系表一致）')
        if node.tag == W + 'sectPr':
            raise Abort(f'{tag}_xml 含 w:sectPr，不允许（分节符不能通过插入段带入文档）')
    return el


_CONSISTENCY_HINT = ('diff 产物请改 runs[].text（或删去 ppr_xml/rpr_xml 改用手写格式）')


def _ppr_authentic_fmt(ppr_el):
    """从已解析的 w:pPr 元素（可能是 None）里取出'给人看的字段'能对应到的两个值：
    pStyle 的 styleId、keepNext 是否存在。供 check_ops 核对 ppr_xml 与 style/keep_next
    是否一致（第六轮 major①）。"""
    if ppr_el is None:
        return None, False
    pstyle_el = ppr_el.find(W + 'pStyle')
    pstyle = pstyle_el.get(W + 'val') if pstyle_el is not None else None
    keep_next = ppr_el.find(W + 'keepNext') is not None
    return pstyle, keep_next


def _rpr_authentic_fmt(rpr_el):
    """同上，取已解析的 w:rPr 元素对应的 bold/color。"""
    if rpr_el is None:
        return False, None
    bold = rpr_el.find(W + 'b') is not None
    color_el = rpr_el.find(W + 'color')
    color = color_el.get(W + 'val') if color_el is not None else None
    return bold, color


def _build_paragraph(spec, template_p, styles_obj=None):
    from lxml import etree as _E
    new_p = _E.Element(W + 'p')
    has_ppr_xml = 'ppr_xml' in spec
    if has_ppr_xml:
        ppr = _parse_ppr_rpr_fragment(spec['ppr_xml'], 'pPr')
        if ppr is not None:
            new_p.append(copy.deepcopy(ppr))
        # 原样使用：style/keep_next 这两个字段这时只是给人看的元数据（diff 连同 ppr_xml 一并
        # 写出，方便报告/审阅不用解析 XML 就知道目标样式与 keepNext），实际落地的 pPr 完全以
        # ppr_xml 为准，不再叠加 style/keep_next 的覆盖逻辑，也不再看模板 template_p 的 pPr。
    else:
        ppr = None
        if template_p is not None and template_p.find(W + 'pPr') is not None:
            ppr = copy.deepcopy(template_p.find(W + 'pPr'))
            for tag in (W + 'bookmarkStart', W + 'bookmarkEnd'):
                for x in ppr.findall(tag):
                    ppr.remove(x)
        if ppr is not None:
            new_p.append(ppr)
        if spec.get('style'):
            style_id = _resolve_style_id(styles_obj, spec['style']) if styles_obj is not None else spec['style']
            if new_p.find(W + 'pPr') is None:
                new_p.insert(0, _E.Element(W + 'pPr'))
            pstyle = new_p.find(f'{W}pPr/{W}pStyle')
            if pstyle is None:
                pstyle = _E.SubElement(new_p.find(W + 'pPr'), W + 'pStyle')
            pstyle.set(W + 'val', style_id)
        if 'keep_next' in spec:
            # 目标段自己的 keepNext（diff 带上）必须能覆盖模板/克隆来源继承的值，不论模板有没有——
            # 只要 spec 显式给了这个键就按它来，不看模板原状态。
            if new_p.find(W + 'pPr') is None:
                new_p.insert(0, _E.Element(W + 'pPr'))
            ppr_el = new_p.find(W + 'pPr')
            kn = ppr_el.find(W + 'keepNext')
            if spec['keep_next']:
                if kn is None:
                    _E.SubElement(ppr_el, W + 'keepNext')
            elif kn is not None:
                ppr_el.remove(kn)
    tmpl_rpr = None
    if template_p is not None:
        tr = template_p.find(W + 'r')
        if tr is not None and tr.find(W + 'rPr') is not None:
            tmpl_rpr = tr.find(W + 'rPr')
    runs = spec.get('runs')
    if not runs:
        runs = [{'text': spec.get('text', '')}]
    for rs in runs:
        r = _E.SubElement(new_p, W + 'r')
        if 'rpr_xml' in rs:
            rpr = _parse_ppr_rpr_fragment(rs['rpr_xml'], 'rPr')
            if rpr is not None:
                r.append(copy.deepcopy(rpr))
            # 原样使用：不再套模板/克隆来源的 rPr，也不再叠加 bold/color 覆盖——rpr_xml 里已经
            # 是目标 run 真实的完整格式（字号、字体、斜体、下划线等 bold/color 表达不了的格式
            # 也在其中），不需要、也不应该再改。
        else:
            if tmpl_rpr is not None:
                r.append(copy.deepcopy(tmpl_rpr))
            fmt = {k: v for k, v in rs.items() if k in ('color', 'bold')}
            if fmt:
                rpr = r.find(W + 'rPr')
                if rpr is None:
                    rpr = _E.Element(W + 'rPr')
                    r.insert(0, rpr)
                if 'color' in fmt:
                    c = rpr.find(W + 'color')
                    if c is None:
                        c = _E.SubElement(rpr, W + 'color')
                    c.set(W + 'val', fmt['color'])
                if 'bold' in fmt:
                    # bold:false 必须能去掉模板/克隆来源继承来的 w:b（否则模板本身加粗时，显式要求
                    # 不加粗的新 run 会保持加粗——见 r3verify R5）。
                    b = rpr.find(W + 'b')
                    bcs = rpr.find(W + 'bCs')
                    if fmt['bold']:
                        if b is None:
                            _E.SubElement(rpr, W + 'b')
                    else:
                        if b is not None:
                            rpr.remove(b)
                        if bcs is not None:
                            rpr.remove(bcs)
        _emit_text(r, rs.get('text', ''))
    return new_p


def apply_insert(d, p, op, before, styles_obj=None):
    new_ps = []
    for spec in op['paragraphs']:
        tmpl = p
        if spec.get('clone_from'):
            hits = [cand for cand in d.paras if spec['clone_from'] in dl.para_text(cand)]
            if len(hits) != 1:
                raise Abort(f'op {op.get("id")}：clone_from "{spec["clone_from"]}" 命中 {len(hits)} 段，'
                            f'须恰好命中 1 段')
            tmpl = hits[0]
        new_ps.append(_build_paragraph(spec, tmpl, styles_obj))
    if before:
        for np_ in new_ps:
            p.addprevious(np_)
    else:
        anchor_el = p
        for np_ in new_ps:
            anchor_el.addnext(np_)
            anchor_el = np_
    return new_ps


def apply_set_keepnext(p, op):
    from lxml import etree as _E
    ppr = p.find(W + 'pPr')
    if ppr is None:
        ppr = _E.Element(W + 'pPr')
        p.insert(0, ppr)
    kn = ppr.find(W + 'keepNext')
    if op['value']:
        if kn is None:
            _E.SubElement(ppr, W + 'keepNext')
    elif kn is not None:
        ppr.remove(kn)


# ------------------------------------------------------------------ 主校验 + 落地
def check_ops(d, prof_dict, patch, for_apply=False):
    """在原稿（d 打开时的状态）上核对全部 op，返回 (results, blocks_info)。
    只读校验：不改 d 的 XML；真正写入在 do_apply() 里，写之前必须先整批过 check_ops。"""
    # 样式名（w:name）在 word/styles.xml 里，不在 document.xml；锚点的 style 约束要按 w:name 比对。
    import zipfile
    from lxml import etree as _E
    with zipfile.ZipFile(d.path) as z:
        styles_xml = _E.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None
    styles_obj = bh.Styles(styles_xml)
    zone, para_to_block, blocks, P = zones_of(d, prof_dict)
    tag_list, wlist = bh._word_lists(prof_dict)
    allow = bh.cfg(prof_dict, 'student_text.allow_contexts', {}) or {}
    text_index = _build_text_index(d.paras)
    results = []
    elem_by_id = {}  # op id -> 段落元素（对象引用），do_apply 靠它而不是 idx 定位——idx 只在原稿上有效
    touched = {}  # idx -> [op ids]，用于冲突检测（同段多条只允许不重叠 replace_text/set_format）
    seen_ids = set()
    _REQUIRED_FIELDS = {
        'replace_text': ('old', 'new'), 'replace_paragraph': ('old', 'new'),
        'delete_paragraph': ('old',), 'set_format': ('old', 'format'), 'set_keepnext': ('value',),
    }
    for op in patch['ops']:
        oid = op.get('id') or f'op{len(results)+1}'
        if oid in seen_ids:
            raise Abort(f'补丁里 op id 重复：{oid}')
        seen_ids.add(oid)
        kind = op.get('op')
        if kind not in ('replace_text', 'replace_paragraph', 'insert_after', 'insert_before',
                        'delete_paragraph', 'set_format', 'set_keepnext'):
            raise Abort(f'op {oid}：未知 op 类型 {kind}')
        for fld in _REQUIRED_FIELDS.get(kind, ()):
            if fld not in op:
                raise Abort(f'op {oid}：缺少字段 "{fld}"（{kind} 必填）')
        # source_zone 只要给了，取值与 reason 就必须合法——不论锚点自身区位是什么；见下方题面区
        # 强制，以及写后对 insert 新段落真实落点的复核（cmd_apply 里），两处都靠这条通过与否放行。
        if 'source_zone' in op:
            if op.get('source_zone') not in ('restore', 'approved_edit'):
                raise Abort(f'op {oid}：source_zone 只能是 restore/approved_edit')
            if not (op.get('reason') or '').strip():
                raise Abort(f'op {oid}：给了 source_zone 就必须同时给非空 reason')
        anchor = op.get('anchor') or {}
        idx, elem, cands = resolve_anchor(d, styles_obj, blocks, para_to_block, anchor, text_index)
        row = {'id': oid, 'op': kind, 'status': 'ok'}
        if idx is None:
            row['status'] = 'anchor_error'
            row['candidates'] = [{'index': c['index'], 'style': c['style'], 'text': c['text']} for c in cands[:20]]
            row['candidate_count'] = len(cands)
            results.append(row)
            raise Abort(f'op {oid}：锚点命中 {len(cands)} 段（须恰好 1 段）')
        row['index'] = idx
        elem_by_id[oid] = elem
        z = zone[idx] if idx < len(zone) else None
        row['zone'] = z
        row['style'] = _style_name(styles_obj, elem)
        row['before_text'] = bh.clip(dl.para_text(elem), 60)
        row['before_sha'] = dl.para_sha(elem)
        in_source_zone = z in ('source', 'title')
        if in_source_zone:
            if not op.get('source_zone') or not (op.get('reason') or '').strip():
                raise Abort(f'op {oid}：锚点落在题面区（zone={z}），必须给 source_zone 与非空 reason（段号 {idx}）')
        # 词表豁免只在"锚点段落在原稿里确属 source/title 区，且 source_zone=='restore'"时才生效；
        # 教学区给 restore 不豁免，照常过词表（题面还原豁免不能被拿来给教学段贴工程标签）。
        wordlist_exempt = in_source_zone and op.get('source_zone') == 'restore'
        if not wordlist_exempt:
            for txt in _new_texts_of(op):
                hit = _forbidden_hit(txt, tag_list, wlist, allow)
                if hit:
                    raise Abort(f'op {oid}：新文字命中禁用词表 {hit[0]}:{hit[1]}（段号 {idx}）')
        priors = touched.get(idx) or []
        for pk, prange, prior_id in priors:
            if not ({pk, kind} <= {'replace_text', 'set_format'}):
                raise Abort(f'op {oid}：与 {prior_id} 同段冲突（段号 {idx}，非 replace_text/set_format 组合）')
            if kind in ('replace_text', 'set_format') and 'old' in op:
                full = ''.join(t for _, t in _run_spans(d.paras[idx]))
                hits = _find_span(full, op['old'])
                if hits:
                    a, b = hits[0], hits[0] + len(op['old'])
                    if not (b <= prange[0] or a >= prange[1]):
                        raise Abort(f'op {oid}：与 {prior_id} 落点重叠（段号 {idx}）')
        if kind in ('replace_text', 'set_format') and 'old' in op:
            full = ''.join(t for _, t in _run_spans(d.paras[idx]))
            hits = _find_span(full, op['old'])
            if hits:
                touched.setdefault(idx, []).append((kind, (hits[0], hits[0] + len(op['old'])), oid))
            else:
                touched.setdefault(idx, []).append((kind, (-1, -1), oid))
        else:
            touched.setdefault(idx, []).append((kind, (0, 10**9), oid))
        if kind == 'insert_after' or kind == 'insert_before':
            if not op.get('paragraphs'):
                raise Abort(f'op {oid}：insert 缺 paragraphs')
            # style/clone_from 在 check 阶段就要能定位，不能等到 apply 才报错（check 报 ok，
            # apply 才中止会误导主代理——见 r3verify R7）；口径与 apply_insert 完全一致。
            for spec in op['paragraphs']:
                if spec.get('style'):
                    _resolve_style_id(styles_obj, spec['style'])
                if spec.get('clone_from'):
                    hits = [cand for cand in d.paras if spec['clone_from'] in dl.para_text(cand)]
                    if len(hits) != 1:
                        raise Abort(f'op {oid}：clone_from "{spec["clone_from"]}" 命中 {len(hits)} 段，'
                                    f'须恰好命中 1 段')
                # ppr_xml/rpr_xml（第五轮 major①：带原样格式的插入段）在 check 阶段就解析校验，
                # 不留到 apply 才发现格式片段非法——口径与上面 style/clone_from 提前校验一致。
                has_ppr_xml = 'ppr_xml' in spec
                ppr_el = None
                if has_ppr_xml:
                    try:
                        ppr_el = _parse_ppr_rpr_fragment(spec['ppr_xml'], 'pPr')
                    except Abort as e:
                        raise Abort(f'op {oid}：{e}')
                    # 第六轮 major①：ppr_xml 是原样格式，style/keep_next 这时只是 diff 顺带写出的
                    # "给人看"字段——上一轮 _build_paragraph 已经改成完全不看它俩、只认 ppr_xml，
                    # 但 check 阶段从未验证过两者是否一致。主代理如果以为改 style/keep_next 就能
                    # 改掉插入段的实际样式/keepNext，写出的却仍是 ppr_xml 里的旧值，改动被静默
                    # 吞掉且没有任何提示。这里强制两者一致，不一致就中止，不允许"按 ppr_xml 为准
                    # 悄悄丢弃 style/keep_next"这条路径继续存在。
                    pstyle_val, keep_next_val = _ppr_authentic_fmt(ppr_el)
                    if spec.get('style'):
                        want_id = _resolve_style_id(styles_obj, spec['style'])
                        if want_id != pstyle_val:
                            raise Abort(f'op {oid}：插入段 style="{spec["style"]}" 与 ppr_xml 里的'
                                        f'实际样式不一致（{_CONSISTENCY_HINT}）')
                    if 'keep_next' in spec and bool(spec['keep_next']) != keep_next_val:
                        raise Abort(f'op {oid}：插入段 keep_next={spec["keep_next"]!r} 与 ppr_xml '
                                    f'里的实际 keepNext 不一致（{_CONSISTENCY_HINT}）')
                runs_spec = spec.get('runs') or []
                any_rpr_xml = False
                for rs in runs_spec:
                    if 'rpr_xml' in rs:
                        any_rpr_xml = True
                        try:
                            rpr_el = _parse_ppr_rpr_fragment(rs['rpr_xml'], 'rPr')
                        except Abort as e:
                            raise Abort(f'op {oid}：{e}')
                        # 同上：bold/color 是给人看字段，run 真正的格式以 rpr_xml 为准
                        # （_build_paragraph 早已不再叠加 bold/color 覆盖），这里核对一致性。
                        bold_val, color_val = _rpr_authentic_fmt(rpr_el)
                        if 'bold' in rs and bool(rs['bold']) != bold_val:
                            raise Abort(f'op {oid}：插入段 runs[].bold={rs["bold"]!r} 与 rpr_xml 里的'
                                        f'实际加粗不一致（{_CONSISTENCY_HINT}）')
                        if 'color' in rs and (rs.get('color') or None) != color_val:
                            raise Abort(f'op {oid}：插入段 runs[].color={rs.get("color")!r} 与 rpr_xml '
                                        f'里的实际颜色不一致（{_CONSISTENCY_HINT}）')
                # 第六轮 major①：text（若有）必须等于 runs 文字拼接——只在这个插入段确实带了
                # 原样格式（ppr_xml 或任一 run 的 rpr_xml）时才校验；纯手写规格（没有 ppr_xml/
                # rpr_xml）不受影响，仍走 _build_paragraph 原来那套 style/keep_next/bold/color
                # 覆盖逻辑，spec['text'] 与 runs 同时出现在手写规格里本就不常见，不在本轮改动范围。
                if (has_ppr_xml or any_rpr_xml) and runs_spec and 'text' in spec:
                    runs_text = ''.join(r.get('text', '') for r in runs_spec)
                    if spec['text'] != runs_text:
                        raise Abort(f'op {oid}：插入段 text 与 runs[].text 拼接结果不一致'
                                    f'（{_CONSISTENCY_HINT}）')
        if kind == 'set_keepnext':
            if 'value' not in op:
                raise Abort(f'op {oid}：set_keepnext 缺 value')
            has_kn = d.paras[idx].find(f'{W}pPr/{W}keepNext') is not None
            if has_kn == bool(op['value']):
                row['status'] = 'already_applied'
        if kind == 'set_format' and not op.get('format'):
            raise Abort(f'op {oid}：set_format 缺 format')
        # already_applied 检测（只对有 old 的 op；不实际改 XML，只探测）
        if kind == 'replace_text':
            full = ''.join(t for _, t in _run_spans(d.paras[idx]))
            if _already_applied_replace(full, op['old'], op['new']):
                row['status'] = 'already_applied'
            else:
                hits = _find_span(full, op['old'])
                if not hits:
                    raise Abort(f'op {oid}：old 在段内未找到（段号 {idx}）')
                if len(hits) > 1:
                    raise Abort(f'op {oid}：old 在段内出现 {len(hits)} 次（段号 {idx}）')
        elif kind == 'replace_paragraph':
            old_t = dl.para_text(d.paras[idx])
            if old_t != op['old']:
                if old_t == op['new']:
                    row['status'] = 'already_applied'
                else:
                    raise Abort(f'op {oid}：old 与段落全文不等（段号 {idx}）')
            elif _is_complex_paragraph(d.paras[idx]) and not op.get('allow_complex'):
                raise Abort(f'op {oid}：段落含图片/书签/域/超链接，结构过复杂（段号 {idx}）')
        elif kind == 'delete_paragraph':
            old_t = dl.para_text(d.paras[idx])
            if old_t != op['old']:
                if old_t == '':
                    row['status'] = 'already_applied'
                else:
                    raise Abort(f'op {oid}：old 与段落全文不等（段号 {idx}）')
            elif _is_complex_paragraph(d.paras[idx]) and not op.get('allow_complex'):
                raise Abort(f'op {oid}：段落含图片/书签/域/超链接，结构过复杂（段号 {idx}）')
            elif _in_table_cell_alone(d.paras[idx]):
                raise Abort(f'op {oid}：是表格单元格唯一段落（段号 {idx}）')
        elif kind == 'set_format':
            spans2 = _run_spans(d.paras[idx])
            full = ''.join(t for _, t in spans2)
            hits = _find_span(full, op['old'])
            if not hits:
                raise Abort(f'op {oid}：old 在段内未找到（段号 {idx}）')
            if len(hits) > 1:
                raise Abort(f'op {oid}：old 在段内出现 {len(hits)} 次（段号 {idx}）')
            if _format_matches(d.paras[idx], op['old'], op.get('format') or {}):
                row['status'] = 'already_applied'
        elif kind in ('insert_after', 'insert_before'):
            # 已应用检测（启发式）：锚点自身文字不受插入影响，仍能定位；若紧邻位置已经是同样的新段落文字，
            # 判 already_applied。做不到的情形（比如新段落本身与旧段落文字撞车）如实按"未检测到"处理，不误判。
            specs = op['paragraphs']
            n = len(specs)

            def spec_text(sp):
                if sp.get('runs'):
                    return ''.join(r.get('text', '') for r in sp['runs'])
                return sp.get('text', '')
            if kind == 'insert_after':
                seq = list(range(idx + 1, idx + 1 + n))
            else:
                seq = list(range(idx - n, idx))
            if all(0 <= j < len(d.paras) for j in seq) and \
               all(dl.para_text(d.paras[j]) == spec_text(sp) for j, sp in zip(seq, specs)):
                row['status'] = 'already_applied'
        results.append(row)
    return results, elem_by_id, styles_obj


def do_apply(d, patch, results, elem_by_id, styles_obj=None):
    """真正改 XML。elem_by_id 是 check_ops 在原稿上定位到的段落元素引用——用元素身份而不是段号
    定位，因为前面的 op（插入/删除）会让后续段号整体偏移，元素对象本身在 d.refresh() 后仍是同一个。
    返回 (extra, inserted_elements, inserted_by_op)：inserted_elements 供写后核对时把新插入段落排除在
    "未点名段落不变"外；inserted_by_op 按 op id 分组，供"题面零改写"核对新段落落进哪个区用。"""
    by_id = {r['id']: r for r in results}
    extra = {}
    inserted = []
    inserted_by_op = {}  # op id -> 该 op 新插入的段落元素列表
    for op in patch['ops']:
        oid = op.get('id')
        p = elem_by_id[oid]
        kind = op['op']
        e = {}
        if kind == 'replace_text':
            apply_replace_text(p, op, e)
            if e.get('already_applied'):
                # check_ops 已经判过这条不是 already_applied；apply 阶段又判到，说明同段更早的 op
                # 造成了未预期的状态——整批中止，不静默跳过（不留输出，main() 里已在 write_docx 之前）
                raise Abort(f'op {oid}：apply 阶段发现已应用（可能与同段其他 op 相互影响），整批中止')
        elif kind == 'replace_paragraph':
            e['lost_structure_before'] = _structure_fingerprint(p)
            apply_replace_paragraph(p, op)
            e['lost_structure_after'] = _structure_fingerprint(p)
        elif kind == 'delete_paragraph':
            e['lost_structure'] = _structure_fingerprint(p)
            apply_delete_paragraph(p, op)
        elif kind == 'set_format':
            apply_set_format(p, op)
        elif kind == 'set_keepnext':
            apply_set_keepnext(p, op)
        elif kind in ('insert_after', 'insert_before'):
            new_ps = apply_insert(d, p, op, before=(kind == 'insert_before'), styles_obj=styles_obj)
            inserted.extend(new_ps)
            inserted_by_op[oid] = new_ps
        extra[oid] = e
        d.refresh()
    return extra, inserted, inserted_by_op


# ------------------------------------------------------------------ 报告
def _own_json(path, purpose, mode=None, expected_approved_by=None, expected_approval_ref=None):
    """path 已存在时，判断这次写出（purpose='report'：--report 目标；purpose='patch'：diff --out
    目标）能不能覆盖它。

    规则（覆盖范围必须窄，上一轮"看见 schema 就当自己人"的口子在这里收紧）：
    - 已存在文件是补丁（schema=='baodian_patch_v1'）：只有 purpose=='patch' 且该文件本身是
      diff 产物（approved_by 以 'diff:' 开头，还没被人工/主代理批准）才允许覆盖；一份带真实
      approved_by 的已批准补丁，不论 --report 还是 diff --out，一律不许覆盖。
      第五轮 minor④：即使 approved_by 仍是 'diff:' 开头，只要 ops 里已经有任意一条带上了
      source_zone/allow_complex——这两个字段代表人工/主代理已经在这份补丁上签字授权（题面区
      改写、结构过复杂的段落）——就不再当"还没批准"，同样拒绝覆盖。上一轮的漏洞正是：主代理
      review 补丁、逐条补上 source_zone/allow_complex/approval_ref，却忘了把 approved_by
      从自动值改掉，这时再跑一次 diff --out 到同一路径会把这些授权字段连同旧内容一起静默冲掉，
      而覆盖判断只看了 approved_by 一个字段（见 final_apply_patch.json minor R4：原命令重跑，
      authorization_lost=true）。
    - 已存在文件不是补丁：purpose=='report' 时，只有它也是 apply_patch 写的报告（tool==
      'apply_patch'）且 mode 相同（不给 mode 则不比对）才允许覆盖；purpose=='patch' 时一律不允许
      （diff --out 只应该写补丁文件，撞上别的 json 就该老实拒绝，不能顺手把报告吃了）。
    """
    try:
        p = Path(path)
        if not p.exists():
            return True  # 不存在，谈不上覆盖，交给 guard_write 正常判断
        obj = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(obj, dict):
            return False
        if obj.get('schema') == 'baodian_patch_v1':
            if purpose != 'patch':
                return False
            approved_by = str(obj.get('approved_by') or '')
            if not approved_by.startswith('diff:'):
                return False
            # 第六轮 minor③：只看 approved_by 前缀不够——C5 攻击只改了 approval_ref（或只改了
            # op 里给人看的文字），approved_by 仍是 diff 自动值 'diff:apply_patch'，照样被判定
            # "还没批准"而允许覆盖。diff 每次调用都能重新算出这次会写出的 approved_by/approval_ref
            # 是什么（调用方传进来）；只要磁盘上现有文件这两个字段跟"这次重新 diff 会写出的值"
            # 不完全一样，就说明有人已经在这份补丁上动过手（哪怕只改了 approval_ref 这一处文字），
            # 一律当已批准处理，拒绝覆盖。expected_* 为 None 时（老调用点未传）不做这项比对，
            # 保持原有口径，不新增回归。
            if expected_approved_by is not None and approved_by != expected_approved_by:
                return False
            if expected_approval_ref is not None and \
                    str(obj.get('approval_ref') or '') != expected_approval_ref:
                return False
            for op in (obj.get('ops') or []):
                if isinstance(op, dict) and ('source_zone' in op or 'allow_complex' in op):
                    return False
            return True
        if purpose == 'report':
            return obj.get('tool') == 'apply_patch' and (mode is None or obj.get('mode') == mode)
        return False
    except Exception:
        return False


def _guard_report_path(path, prof_dict, guard_inputs=None, mode=None):
    """报告写出的路径守卫：不看"本册是否冻结"（只读检查也该能出报告），但仍经 guard_write 的
    目录级守卫（含冻结册目录、Skill/项目根等受保护目录），且只允许覆盖本工具自己以前写的同类
    报告——绝不允许覆盖补丁文件（哪怕补丁的 schema/tool 字段看起来像"自己人"）。"""
    report_prof = dict(prof_dict or {})
    report_prof['frozen'] = False  # 报告本身不是书稿，冻结册判定不适用；目录级守卫仍由 guard_write 内部做
    overwrite = _own_json(path, 'report', mode=mode)
    return dl.guard_write(path, report_prof, inputs=guard_inputs or [], kind='.json', overwrite=overwrite)


def _write_report(path, prof_dict, obj, guard_inputs=None, mode=None):
    if not path:
        return None
    out = _guard_report_path(path, prof_dict, guard_inputs, mode=mode or obj.get('mode'))
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(out)


def _base_report(mode, patch, d_sha, prof_dict, docx_path=None, patch_path=None):
    return {
        'tool': 'apply_patch', 'version': TOOL_VERSION, 'mode': mode,
        'inputs': {'docx': str(docx_path) if docx_path else None, 'docx_sha256': d_sha,
                   'patch': str(patch_path) if patch_path else None,
                   'patch_schema': patch.get('schema'), 'patch_book': patch.get('book')},
        'profile': {'book_id': prof_dict.get('book_id'), 'frozen': bool(prof_dict.get('frozen'))},
    }


# ------------------------------------------------------------------ 子命令
def cmd_check(args):
    patch = json.loads(Path(args.patch).read_text(encoding='utf-8'))
    if patch.get('schema') != 'baodian_patch_v1':
        raise Abort('补丁 schema 不是 baodian_patch_v1')
    if not patch.get('parent_docx_sha256'):
        raise Abort('补丁缺 parent_docx_sha256（必填）')
    prof_dict = _load_prof(args, patch)
    d = dl.open_docx(args.docx, expect_sha256=patch.get('parent_docx_sha256'))
    rep = _base_report('check', patch, d.sha256, prof_dict, docx_path=args.docx, patch_path=args.patch)
    guard_inputs = [args.docx, args.patch]
    try:
        results, _, _ = check_ops(d, prof_dict, patch)
    except Abort as e:
        rep['aborted'] = True
        rep['reason'] = str(e)
        _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='check')
        print('中止：' + str(e), file=sys.stderr)
        return 2
    rep['ops'] = results
    n_pending = sum(1 for r in results if r['status'] == 'ok')
    n_applied = sum(1 for r in results if r['status'] == 'already_applied')
    rep['summary'] = {'total': len(results), 'pending': n_pending, 'already_applied': n_applied}
    _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='check')
    print(json.dumps(rep['summary'], ensure_ascii=False))
    return 1 if n_pending else 0


def cmd_apply(args):
    patch = json.loads(Path(args.patch).read_text(encoding='utf-8'))
    if patch.get('schema') != 'baodian_patch_v1':
        raise Abort('补丁 schema 不是 baodian_patch_v1')
    if not patch.get('parent_docx_sha256'):
        raise Abort('补丁缺 parent_docx_sha256（必填）')
    prof_dict = _load_prof(args, patch)
    # 冻结册守卫：不能只信 --profile/补丁 book 字段——那两者都可能被写补丁的人指向一个非冻结配置，
    # 而实际输入稿其实属于某本冻结册。写模式下总是对输入稿本身重新跑 detect_profile 核对。
    try:
        real_prof = detect_profile(args.docx)
    except Exception:
        real_prof = None
    if real_prof is not None:
        if bool(real_prof.get('frozen')):
            print(f'拒绝写出：{real_prof.get("title", real_prof.get("book_id"))} 已冻结'
                  f'（{real_prof.get("frozen_note", "")}）', file=sys.stderr)
            return 3
        if real_prof.get('book_id') and prof_dict.get('book_id') and real_prof.get('book_id') != prof_dict.get('book_id'):
            print(f'中止：--profile/补丁 book 字段（{prof_dict.get("book_id")}）与输入稿实际书册'
                  f'（{real_prof.get("book_id")}）不一致', file=sys.stderr)
            return 2
    d = dl.open_docx(args.docx, expect_sha256=patch.get('parent_docx_sha256'))
    rep = _base_report('apply', patch, d.sha256, prof_dict, docx_path=args.docx, patch_path=args.patch)
    guard_inputs = [args.docx, args.patch, args.out]
    try:
        results, elem_by_id, styles_obj = check_ops(d, prof_dict, patch)
    except Abort as e:
        rep['aborted'] = True
        rep['reason'] = str(e)
        _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
        print('中止：' + str(e), file=sys.stderr)
        return 2
    applied_ids = [r['id'] for r in results if r['status'] == 'already_applied']
    if applied_ids:
        rep['aborted'] = True
        rep['reason'] = f'op 已应用（不做部分重放）：{applied_ids}'
        rep['ops'] = results
        _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
        print('中止：' + rep['reason'], file=sys.stderr)
        return 2
    # 写权守卫：先于任何 XML 改动；--patch 本身也列入 inputs，输出不许和补丁文件撞在一起
    try:
        out_path = dl.guard_write(args.out, prof_dict, inputs=[args.docx, args.patch], kind='.docx')
    except dl.GuardError as e:
        rep['aborted'] = True
        rep['reason'] = str(e)
        _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
        print('拒绝写出：' + str(e), file=sys.stderr)
        return 3
    # --report 路径预检：在写 docx 之前就确认报告能落盘，避免"docx 写出但报告被拒"的半成品
    if args.report:
        try:
            _guard_report_path(args.report, prof_dict, guard_inputs=guard_inputs, mode='apply')
        except dl.GuardError as e:
            print('拒绝写出：' + str(e), file=sys.stderr)
            return 3
    before_paras = list(d.paras)
    op_kind_by_id = {r['id']: r['op'] for r in results}
    # touched_before：按元素身份换算成"改动前"列表里的下标（delete 的段落在改动前列表里也要排除）。
    # insert 的锚点段本身不会被 apply_insert 改动（只在它前面/后面插新段），不算"点名改动"，不放
    # 进 touched——让它照常参与下面 unchanged_paragraphs 的 C14N 核对，比只核对"锚点段文字不变"
    # 更严格：任何 XML 差异（不只是文字）都会被抓到（见 r3verify R6 的"锚点被误改"复现）。
    touched_elems = set(id(e) for oid, e in elem_by_id.items()
                         if op_kind_by_id.get(oid) not in ('insert_after', 'insert_before'))
    touched_before = {i for i, p in enumerate(before_paras) if id(p) in touched_elems}
    # set_keepnext 目标段允许改 pPr（因此仍在 touched 里，不受 unchanged_paragraphs 的 C14N 约束），
    # 但目标段自己的文字不该被顺手改动——写前快照，写后单独核对文字不变（见 r3verify R6）。
    text_before_keepnext = {op.get('id'): dl.para_text(elem_by_id[op.get('id')])
                             for op in patch['ops'] if op.get('op') == 'set_keepnext'}
    # "未点名段落不变"的基线：必须来自原始 document.xml 字节独立解析出的一棵树，不能用 before_paras——
    # before_paras 只是对 d.paras 的引用列表，do_apply 会原地改这些元素所在的活树，写后再对 before_paras
    # 算指纹拿到的其实是"改后"的状态，核对形同虚设（复现见 attack N6：do_apply 顺手多改了未点名的
    # 相邻段落，这道核对因为基线本身已经被污染而看不出来）。d.doc_xml_orig 是打开时读到的原始字节，
    # 从它单独 fromstring 出一棵全新的树，跟 d.paras 用的活树没有任何共享节点。
    _orig_root = bh.etree.fromstring(d.doc_xml_orig)
    orig_paras = dl.para_elements(_orig_root.find(W + 'body'))
    extra, inserted, inserted_by_op = do_apply(d, patch, results, elem_by_id, styles_obj)
    # 写后（内存态）逐条 postcondition：新文字在目标段/新段已生效、被删段已脱离树。
    # insert_after/insert_before/set_format/set_keepnext 都有各自显式的后置条件，不只是替换类 op。
    post_bad = []
    for op in patch['ops']:
        oid = op['id']
        kind = op['op']
        if kind in ('delete_paragraph',):
            if elem_by_id[oid].getparent() is not None:
                post_bad.append({'id': oid, 'reason': '删除后仍在树中'})
        elif kind in ('replace_text',):
            if op['new'] not in dl.para_text(elem_by_id[oid]):
                post_bad.append({'id': oid, 'reason': 'new 文字未出现在目标段'})
        elif kind == 'replace_paragraph':
            got = dl.para_text(elem_by_id[oid])
            ok, ws_lost = _ws_check(got, op['new'])
            if not ok:
                post_bad.append({'id': oid, 'reason': '段落全文与 new 不等'})
            elif ws_lost:
                extra.setdefault(oid, {})['new_whitespace_normalized'] = True
        elif kind == 'set_keepnext':
            has_kn = elem_by_id[oid].find(f'{W}pPr/{W}keepNext') is not None
            if has_kn != bool(op['value']):
                post_bad.append({'id': oid, 'reason': 'keepNext 未生效'})
            elif dl.para_text(elem_by_id[oid]) != text_before_keepnext.get(oid):
                post_bad.append({'id': oid, 'reason': 'set_keepnext 目标段文字发生变化（应只改 keepNext）'})
        elif kind == 'set_format':
            if not _format_matches(elem_by_id[oid], op['old'], op.get('format') or {}):
                post_bad.append({'id': oid, 'reason': 'set_format 未生效'})
        elif kind in ('insert_after', 'insert_before'):
            ps = inserted_by_op.get(oid, [])
            specs = op.get('paragraphs') or []
            if len(ps) != len(specs):
                post_bad.append({'id': oid, 'reason': f'插入段落数（{len(ps)}）与 paragraphs 数（{len(specs)}）不符'})
            else:
                def _spec_text(sp):
                    if sp.get('runs'):
                        return ''.join(r.get('text', '') for r in sp['runs'])
                    return sp.get('text', '')
                ws_notes = []
                bad_here = False
                for pi, (p_, sp) in enumerate(zip(ps, specs)):
                    got = dl.para_text(p_)
                    want_raw = _spec_text(sp)
                    ok, ws_lost = _ws_check(got, want_raw)
                    if not ok:
                        post_bad.append({'id': oid, 'reason': '插入段落文字与 paragraphs 规格不符'})
                        bad_here = True
                        break
                    if ws_lost:
                        ws_notes.append(pi)
                if ws_notes and not bad_here:
                    extra.setdefault(oid, {})['new_whitespace_normalized'] = ws_notes
    if post_bad:
        rep['aborted'] = True
        rep['reason'] = '写后 postcondition 不通过'
        rep['postcondition_failed'] = post_bad
        _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
        print('中止：写后 postcondition 不通过，未写出', file=sys.stderr)
        return 2
    # 插入段落在写出前的位置（用当前内存树的段号）——这是"这条 op 的新段落最终落在文档第几段"的
    # 唯一可靠记录：写出后重开是一棵全新的树，元素身份对不上，只能靠段号做桥梁；而这个段号在
    # write_docx 之后不会变（write_docx 只是把同一棵内存树序列化，不改变段落顺序/数量），所以可以
    # 直接拿去索引重开后 d_out 的区位表。
    idx_of_mem = {id(p): i for i, p in enumerate(d.paras)}
    inserted_idx_by_op = {oid: [idx_of_mem[id(p_)] for p_ in ps if id(p_) in idx_of_mem]
                           for oid, ps in inserted_by_op.items()}
    after_elems = set(touched_elems) | set(id(e) for e in inserted)
    touched_after = {i for i, p in enumerate(d.paras) if id(p) in after_elems}
    write_receipt = dl.write_docx(d, out_path)
    # "未点名段落不变"必须对重新打开的输出文件核对，基线用原始 document.xml 字节独立解析出的
    # orig_paras（见上），不是内存里被 do_apply 顺手改过的活树。
    try:
        d_out = dl.open_docx(out_path)
    except Exception as e:
        out_path.unlink(missing_ok=True)
        rep['aborted'] = True
        rep['reason'] = f'写出后重新打开失败，已删除输出：{e}'
        _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
        print('中止：写出后重新打开失败，已删除输出', file=sys.stderr)
        return 2
    bad = dl.unchanged_paragraphs(orig_paras, d_out.paras, touched_before, touched_after)
    if bad:
        out_path.unlink(missing_ok=True)
        rep['aborted'] = True
        rep['reason'] = '未点名段落发生变化（对重新打开的输出文件核对）'
        rep['unchanged_check'] = bad[:20]
        _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
        print('中止：未点名段落发生变化，已删除输出', file=sys.stderr)
        return 2
    # 题面零改写：check_ops 只查"锚点自己是否落在 source/title 区"，insert 型 op 的锚点可以合法地在
    # teaching 区，但新段落实际插入位置可能落进 source/title 区（比如插到题面最后一段之后、标签之前）。
    # 必须用重新打开的输出文件重跑 bh.walk 取区位——上一轮在这里直接用了 d.items（打开原稿时读的、
    # 长度和顺序都对应原稿的区位表），d.refresh() 只重建 d.paras 不重读 items，于是新段落的段号被
    # 拿去查一张跟当前树对不上的旧区位表，既会漏拦（新段真进了题面，查到的却是别处的区位）也会误拦
    # （前面的插入/删除让段号整体偏移，合法的教学区插入被判成落进题面）。这里改成对 d_out（写出后
    # 重新打开、用 bh.read_docx 从实际字节读出的区位）跑 zones_of，用上面记录的写出前段号去查。
    # 只看被点名插入的段落本身，不做全书级 source/title 文字序列比对——全书比对在这种规模的文档上
    # 对 walk 的位置敏感、容易在完全无关的地方产生误判，会把大量正常补丁一起挡下。
    # 第五轮 minor③：上一轮这道写后区位复核只覆盖 insert，replace_paragraph 带 source_zone=
    # restore 时完全没有对应检查——把题面区的标题段改成不像标题的文字，写后该段区位可能已经
    # 变成 heading/outside（不再是 source/title），check 阶段基于原稿区位给的词表豁免这时已经
    # 不成立，但没有人再补跑一遍词表（见 final_apply_patch.json minor F1）。这里把 replace_paragraph
    # 的 restore op 一并纳入同一套"写后重开、按输出区位补跑词表"的复核，用 idx_of_mem 把
    # elem_by_id 记录的段落元素身份换算成输出文件里的段号（跟 insert 那段用的是同一张映射表）。
    # 第六轮 minor②：final 原文写的是"replace_paragraph 或 replace_text 带 restore"，上一轮
    # restore_replace_ops 只收了 replace_paragraph，replace_text 带 source_zone=restore 时完全
    # 没有写后区位+词表复核——两者用的是同一套 elem_by_id/idx_of_mem 桥接（apply_replace_text 跟
    # apply_replace_paragraph 一样是原地改 p，不换元素），口径必须一致，这里把筛选条件扩到两种 op。
    restore_replace_ops = [op for op in patch['ops']
                            if op.get('op') in ('replace_paragraph', 'replace_text')
                            and op.get('source_zone') == 'restore']
    if inserted_idx_by_op or restore_replace_ops:
        op_by_id = {op.get('id'): op for op in patch['ops']}
        zone_after, _, _, _ = zones_of(d_out, prof_dict)
        tag_list, wlist = bh._word_lists(prof_dict)
        allow = bh.cfg(prof_dict, 'student_text.allow_contexts', {}) or {}
        zone_leak = []
        wordlist_leak = []
        for oid, idxs in inserted_idx_by_op.items():
            op = op_by_id.get(oid, {})
            sz = op.get('source_zone')
            # check_ops 已经强制：给了 source_zone 就必须是 restore/approved_edit 且 reason 非空；
            # 这里只需要认"有没有给"，不重复校验取值（否则一条格式非法的 source_zone 会在这里被
            # 当成"没给"而误报 zone_leak，反而掩盖了它本该在 check_ops 就被拒绝的事实）。
            if not sz:
                for i in idxs:
                    if i < len(zone_after) and zone_after[i] in ('source', 'title'):
                        zone_leak.append({'id': oid, 'index': i, 'zone': zone_after[i],
                                           'text': bh.clip(dl.para_text(d_out.paras[i]), 40)})
                continue
            if sz != 'restore':
                # approved_edit：check_ops 里词表从不豁免（wordlist_exempt 只在 restore 时成立），
                # 新文字已经按锚点区位过了一遍词表，这里不用再补跑。
                continue
            # restore 的词表豁免只在"新文字在输出里确实落在 source/title 区"时才成立：锚点自己在
            # title 区、insert_before 却把新段插到了上一块的教学区（见 r3verify R2：锚点是选择例题
            # 的标题段，插到它前面正好落进上一题的教学区），这种情况不能算合法豁免。新段真实区位
            # 不是 source/title 时，对它的实际文字补跑一遍词表，命中就跟 zone_leak 一样删输出、
            # 整批中止——不能让"锚点本身在题面区"成为把工程词写进教学正文的后门。
            for i in idxs:
                zi = zone_after[i] if i < len(zone_after) else None
                if zi in ('source', 'title'):
                    continue
                txt = dl.para_text(d_out.paras[i])
                hit = _forbidden_hit(txt, tag_list, wlist, allow)
                if hit:
                    wordlist_leak.append({'id': oid, 'index': i, 'zone': zi,
                                           'hit': f'{hit[0]}:{hit[1]}',
                                           'text': bh.clip(txt, 40)})
        for op in restore_replace_ops:
            oid = op.get('id')
            elem = elem_by_id.get(oid)
            i = idx_of_mem.get(id(elem)) if elem is not None else None
            if i is None:
                continue
            zi = zone_after[i] if i < len(zone_after) else None
            if zi in ('source', 'title'):
                continue
            txt = dl.para_text(d_out.paras[i])
            hit = _forbidden_hit(txt, tag_list, wlist, allow)
            if hit:
                wordlist_leak.append({'id': oid, 'index': i, 'zone': zi,
                                       'hit': f'{hit[0]}:{hit[1]}',
                                       'text': bh.clip(txt, 40)})
        if zone_leak or wordlist_leak:
            out_path.unlink(missing_ok=True)
            rep['aborted'] = True
            reasons = []
            if zone_leak:
                reasons.append('插入的新段落落进了 source/title 区，但对应 op 没有给 source_zone')
            if wordlist_leak:
                reasons.append('restore 豁免的段落（新插入或 replace_paragraph 改写后）实际未落在 '
                               'source/title 区，且新文字命中禁用词表')
            rep['reason'] = '；'.join(reasons)
            rep['zone_leak'] = zone_leak
            rep['wordlist_leak'] = wordlist_leak
            _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
            print('中止：题面零改写复核不通过，已删除输出', file=sys.stderr)
            return 2
    # 写后逐条补 after_text/after_sha/插入段落详情，供报告给出改前/改后文字与段落指纹
    for op in patch['ops']:
        oid = op['id']
        kind = op['op']
        e = extra.setdefault(oid, {})
        if kind == 'delete_paragraph':
            e['after_text'] = None
            e['after_sha'] = None
        elif kind in ('replace_text', 'replace_paragraph', 'set_format', 'set_keepnext'):
            el = elem_by_id[oid]
            e['after_text'] = bh.clip(dl.para_text(el), 60)
            e['after_sha'] = dl.para_sha(el)
        elif kind in ('insert_after', 'insert_before'):
            e['inserted'] = [{'text': bh.clip(dl.para_text(p_), 60), 'sha': dl.para_sha(p_)}
                              for p_ in inserted_by_op.get(oid, [])]
    rep['ops'] = results
    rep['ops_extra'] = extra
    rep['output'] = write_receipt
    if args.health:
        import collections

        def _fkey(f):
            # 不能用绝对段号：本工具自己的 insert/delete 就会让后面所有 FAIL 的段号整体偏移，
            # 段号一变就会把"其实没变"的老 FAIL 误判成新增。改用位置无关的身份——所在例题标题
            # （where.example）+ 具体标签/摘录，比 (check, rule) 更细，但不受段落整体偏移影响。
            where = f.get('where') or {}
            return (f['check'], f['rule'], where.get('example'), where.get('part'), f.get('label'),
                    f.get('excerpt'))
        try:
            in_health = bh.run_health(str(args.docx), profile=prof_dict)
            out_health = bh.run_health(write_receipt['out'], profile=prof_dict)
            in_findings = [f for f in in_health['findings'] if f['level'] == 'FAIL']
            out_findings = [f for f in out_health['findings'] if f['level'] == 'FAIL']
            in_count = collections.Counter(_fkey(f) for f in in_findings)
            # 按 (check, rule, 段号, 摘录) 的多重集合做差集：既不因输入已有同名 FAIL 就吞掉输出里
            # 新增的同名 FAIL（不同段号/摘录，或数量更多），也不靠 (check, rule) 单独去重。
            seen = collections.Counter()
            out_fail = []
            for f in out_findings:
                k = _fkey(f)
                if seen[k] < in_count.get(k, 0):
                    seen[k] += 1
                    continue
                seen[k] += 1
                out_fail.append(f)
            rep['health'] = {'input_FAIL': in_health['summary']['FAIL'], 'output_FAIL': out_health['summary']['FAIL'],
                              'new_FAIL': out_fail[:30], 'new_FAIL_count': len(out_fail)}
            _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
            if out_fail:
                print(f'写出但体检新增 {len(out_fail)} 条 FAIL：{write_receipt["out"]}', file=sys.stderr)
                return 1
        except Exception as e:
            # 共同约定第 4 条"中止不留输出"：--health 本身抛异常时，写出的候选状态未知（既没有
            # 拿到"无新增 FAIL"的证明，也不是明确的新增 FAIL），不能保留——保留一份状态不明的
            # 候选比"新 FAIL 但保留供查看"更危险，后者好歹是明确判定过的。
            out_path.unlink(missing_ok=True)
            rep['aborted'] = True
            rep['health'] = {'error': str(e)}
            rep['reason'] = f'写后体检异常，已删除输出（状态未知，不留输出）：{e}'
            _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
            print(f'中止：写后体检异常，已删除输出：{e}', file=sys.stderr)
            return 2
    _write_report(args.report, prof_dict, rep, guard_inputs=guard_inputs, mode='apply')
    print(json.dumps({'out': write_receipt['out'], 'sha256': write_receipt['sha256']}, ensure_ascii=False))
    return 0


def _diff_style_of(styles_obj, p):
    return _style_name(styles_obj, p)


def cmd_diff(args):
    import zipfile
    from lxml import etree as _E
    # 同路径判断按 guard_write 的口径折叠大小写（macOS/APFS 大小写不敏感，字面不同的路径可能是
    # 同一个文件——上一轮这里只做了精确 resolve() 相等比较，--out x.json --report X.JSON 这种
    # 大小写变体会漏判，见 r3verify R3 大小写变体）。仍按补丁格式错误处理（退出码 2，与既有
    # t5c 用例一致），不是 guard_write 那类"输出落在受保护目录/已存在不可覆盖"的拒绝写出。
    if args.report and dl._cf(str(Path(args.report).expanduser().resolve())) == \
            dl._cf(str(Path(args.out).expanduser().resolve())):
        raise Abort('--report 与 --out 不能是同一路径（补丁与报告必须是两个文件）')
    d_old = dl.open_docx(args.old)
    d_new = dl.open_docx(args.new)
    old_texts = [dl.para_text(p) for p in d_old.paras]
    # 第五轮 minor②：uniq_anchor 判重复要跟 resolve_anchor 定位用同一个归一口径（bh.norm，
    # 去空白）——上一轮 uniq_anchor 按精确字符串相等数重复，resolve_anchor 却按 bh.norm 匹配，
    # 两段只差空白（比如一个多一个空格）时 uniq_anchor 判"唯一"、不带 index_hint，apply 时
    # resolve_anchor 却按 norm 命中 2 段而中止，见 final_apply_patch.json minor（51→52 里
    # D1184/D1185 等 6 条同类锚点）。这里预先按 bh.norm 统计一遍重复次数，一次扫描，供
    # uniq_anchor 直接查表，不必每次调用都重新扫描整篇（old_texts 可能上千段）。
    _norm_counts = {}
    for _t in old_texts:
        _n = bh.norm(_t)
        _norm_counts[_n] = _norm_counts.get(_n, 0) + 1
    new_texts = [dl.para_text(p) for p in d_new.paras]
    with zipfile.ZipFile(d_old.path) as z:
        styles_old = bh.Styles(_E.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None)
    with zipfile.ZipFile(d_new.path) as z:
        styles_new = bh.Styles(_E.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None)
    diff_prof = None
    try:
        diff_prof = _load_prof(args, {'book': args.book} if args.book else None)
    except Exception:
        diff_prof = None
    # --report 路径先于 --out 校验（守卫全套：受保护目录、冻结册目录、"已存在且不是自己的报告"
    # 等等），避免"补丁已经写到 --out、报告才被拒绝"的半成品——上一轮先写 --out 再验 --report，
    # 见 r3verify R3：报告校验被拒时补丁已经落盘。这里只做校验（不写文件），真正写报告仍在最后，
    # 用同一份 guard_inputs 再算一次（guard_write 是纯函数式的路径判断，两次调用结论一致）。
    if args.report:
        _guard_report_path(args.report, diff_prof or {}, guard_inputs=[args.old, args.new, args.out], mode='diff')
    old_zone = None
    complex_flags = [_is_complex_paragraph(p) for p in d_old.paras]
    if diff_prof is not None:
        try:
            old_zone, _p2b, _blocks, _P = zones_of(d_old, diff_prof)
        except Exception:
            old_zone = None

    def _authz(op, oi, check_complex):
        """diff 只产出审阅材料，不替人授权：锚点落在题面区/段落结构复杂时，只标注
        zone/complex_parts 与 needs_authorization，不自动写 source_zone/allow_complex——
        那两个字段代表人工签字，必须由补丁作者（人或主代理）在审阅后显式补上。check/apply
        遇到缺这两个字段的题面区/复杂段 op 会照常中止，这正是设计意图，不是 bug。"""
        needs = []
        if old_zone is not None and 0 <= oi < len(old_zone) and old_zone[oi] in ('source', 'title'):
            op['zone'] = old_zone[oi]
            needs.append('source_zone')
        if check_complex and 0 <= oi < len(complex_flags) and complex_flags[oi]:
            op['complex_parts'] = _complex_parts(d_old.paras[oi])
            needs.append('allow_complex')
        if needs:
            op['needs_authorization'] = needs
    sm = difflib.SequenceMatcher(a=old_texts, b=new_texts, autojunk=False)
    ops = []
    format_changes = []
    unanchorable = []
    seq = 1
    # 报告顶层的结构损失汇总（不是逐条 format_changes 里才看得到）：replace_paragraph/
    # delete_paragraph 一律清空段内除首个文字 run 外的一切（apply_replace_paragraph/
    # apply_delete_paragraph 的实现如此），旧段里的超链接、域、书签、图片、批注、脚注等复杂结构
    # 和除首个 run 外的彩色 run 全部计入"丢失"；插入段落里表达不了的复杂结构（本工具 v1 的
    # runs 规格只有 text/bold/color）另计；首尾空白段数是"新文字被读取口径 strip 掉"的段落数，
    # 三处（equal 对比的新稿本身、replace_paragraph 的 new、insert 的新段）都算。
    lost_structure_summary = {
        'hyperlink_lost': 0, 'field_lost': 0, 'bookmark_lost': 0, 'image_lost': 0,
        'comment_lost': 0, 'note_lost': 0, 'other_complex_lost': 0,
        'colored_runs_before': 0, 'colored_runs_after': 0,
        'insert_complex_paragraphs': 0, 'insert_extra_format_paragraphs': 0,
        'whitespace_lost_paragraphs': 0,
    }

    def _note_replace_or_delete_loss(oi):
        """replace_paragraph/delete_paragraph 生成时，把旧段（oi，原稿）的复杂结构与彩色 run
        计入顶层汇总——这是"如果这条 op 被应用会丢什么"的估算，不是真的跑一遍 apply；
        replace_paragraph 只留首个文字 run 的颜色（如果有），delete_paragraph 什么都不留。"""
        p_old = d_old.paras[oi]
        parts = _complex_parts(p_old)
        for cat, n in parts.items():
            key = cat + '_lost'
            lost_structure_summary[key] = lost_structure_summary.get(key, 0) + n
        fp = _structure_fingerprint(p_old)
        lost_structure_summary['colored_runs_before'] += fp['colored_runs']
        first_r = _first_text_run(p_old)
        if first_r is not None and _run_fmt(first_r)[0]:
            lost_structure_summary['colored_runs_after'] += 1

    def _note_whitespace(ni):
        raw = ''.join(t for _, t in _run_spans(d_new.paras[ni]))
        if raw != _ws_norm(raw):
            lost_structure_summary['whitespace_lost_paragraphs'] += 1

    def uniq_anchor(i):
        """给旧稿第 i 段生成一个尽量唯一的 text 锚点；重复时带 index_hint（+ prev 消歧）。
        重复判定按 bh.norm（去空白）计数，跟 resolve_anchor 定位用的口径完全一致——两段只差
        空白也算重复，必须带 index_hint/prev，不能让 apply 时才发现锚点命中 2 段。"""
        t = old_texts[i]
        dup = _norm_counts.get(bh.norm(t), 1)
        a = {'text': t}
        if dup > 1:
            a['index_hint'] = i
            prevt = old_texts[i - 1] if i else None
            if prevt:
                a['prev'] = prevt[:20]
        return a

    def _equal_pair_diff(oi, ni):
        """text 相同（equal 分段内配对）但格式可能不同的一对段落：
        keepNext 差异 -> 返回 True（调用方据此生成 set_keepnext op）；
        pStyle 差异（哪怕文字和 keepNext 都没变）、run 颜色/加粗差异（含 run 结构不同、无法逐 run
        比对的情形）-> 追加进 format_changes（仅报告，不生成 op——补丁 op 表里没有"只改样式"这一种）。"""
        p_old, p_new = d_old.paras[oi], d_new.paras[ni]
        kn_old = p_old.find(f'{W}pPr/{W}keepNext') is not None
        kn_new = p_new.find(f'{W}pPr/{W}keepNext') is not None
        style_old = _diff_style_of(styles_old, p_old)
        style_new = _diff_style_of(styles_new, p_new)
        if style_old != style_new:
            format_changes.append({
                'index': oi, 'kind': 'pStyle', 'text': bh.clip(old_texts[oi], 40),
                'style_before': style_old, 'style_after': style_new,
                'summary': '文字未变，仅 pStyle 不同（本工具没有"只改样式"的 op，只报告不生成 op）'})
        old_spans = [(t, _run_fmt(r)) for r, t in _run_spans(p_old)]
        new_spans = [(t, _run_fmt(r)) for r, t in _run_spans(p_new)]
        if [t for t, _ in old_spans] == [t for t, _ in new_spans]:
            for (t, fo), (_, fn) in zip(old_spans, new_spans):
                if fo != fn:
                    format_changes.append({
                        'index': oi, 'kind': 'run_format', 'style': style_old, 'text': bh.clip(t, 40),
                        'before_format': {'color': fo[0], 'bold': fo[1]},
                        'after_format': {'color': fn[0], 'bold': fn[1]},
                        'summary': 'run 颜色/加粗不同（文字未变）'})
        elif old_spans != new_spans:
            format_changes.append({
                'index': oi, 'kind': 'run_split', 'style': style_old,
                'text': bh.clip(''.join(t for t, _ in old_spans), 40),
                'summary': 'run 切分/数量不同，未逐 run 比对格式，仅如实标注存在差异'})
        return kn_old != kn_new, kn_new

    def _replace_format_note(oi, ni, op_id):
        """replace_paragraph 保留旧段的 pPr（含 pStyle、keepNext），文字改了但这两项也变了的话，
        回放会把它们的变化静默丢掉——这里如实报进 format_changes，不生成额外 op（规格没有"改文字
        同时改样式"的 op），提醒补丁审阅者这条 replace_paragraph 回放后样式/keepNext 对不上新稿。"""
        p_old, p_new = d_old.paras[oi], d_new.paras[ni]
        kn_old = p_old.find(f'{W}pPr/{W}keepNext') is not None
        kn_new = p_new.find(f'{W}pPr/{W}keepNext') is not None
        style_old = _diff_style_of(styles_old, p_old)
        style_new = _diff_style_of(styles_new, p_new)
        if kn_old != kn_new or style_old != style_new:
            format_changes.append({
                'index': oi, 'op_id': op_id, 'kind': 'replace_paragraph_format',
                'style_before': style_old, 'style_after': style_new,
                'keepnext_before': kn_old, 'keepnext_after': kn_new,
                'summary': 'replace_paragraph 保留旧 pPr，此差异回放时会静默丢失'})

    def _sanitize_ppr_copy(ppr_el):
        """深拷贝一份 pPr，去掉不该跟着插入段搬走的东西：书签（理论上不出现在 pPr 下，防御性
        清一遍）、分节符 w:sectPr（_parse_ppr_rpr_fragment 在 apply 侧也会拒绝，这里先自己
        不产出，不指望对面的校验兜底）。"""
        ppr = copy.deepcopy(ppr_el)
        for tag in (W + 'bookmarkStart', W + 'bookmarkEnd', W + 'sectPr'):
            for x in ppr.findall(tag):
                ppr.remove(x)
        return ppr

    def _new_para_specs(nis):
        """新增段落规格：带上目标稿（新稿）自己的样式名、keepNext（供人读的元数据），以及
        ppr_xml（目标段 w:pPr 整段序列化）与 runs[{text, bold, color, rpr_xml}]（每个 run
        的 w:rPr 整段序列化）——第五轮 major①：apply 侧 _build_paragraph 见到 ppr_xml/rpr_xml
        就原样使用，不再从锚点段继承 pPr/首个 run rPr。上一轮只给"颜色/加粗"两个字段，锚点
        自己有格式、目标段没格式（或反过来）时，_build_paragraph 仍会把锚点的 pPr（jc/ind/
        keepLines/spacing/tabs）和首个 run 的 rPr（含 w:b、w:color）套到新段上——这正是这一轮
        要堵的洞（见 final_apply_patch.json major：51→52 压力回放里 533 个插入段格式不符，
        432 个连 format_changes 都没报）。ppr_xml/rpr_xml 是目标段的原样 XML，插入位置换成
        哪个锚点都不影响结果，从根子上不再有"继承谁"的问题。

        样式名在父稿里若不存在，check 阶段就会给出清楚的中文中止理由（见 _resolve_style_id 的
        check_ops 调用点），不会静默丢弃到 apply 才发现；ppr_xml/rpr_xml 本身的格式非法（根
        元素不对、含关系引用、含 sectPr）同样在 check 阶段就中止（_parse_ppr_rpr_fragment）。

        段内本身含超链接/域/图片/书签等复杂结构（本工具 v1 完全不支持插入这些）时，如实记进
        format_changes（kind=insert_format）并计入顶层 lost_structure_summary，这部分依旧只能
        插成纯文字，不产出 ppr_xml/runs。"""
        specs = []
        for ni in nis:
            p_new = d_new.paras[ni]
            sp = {'text': new_texts[ni]}
            sname = _diff_style_of(styles_new, p_new)
            if sname and sname != '(默认)':
                sp['style'] = sname
            sp['keep_next'] = p_new.find(f'{W}pPr/{W}keepNext') is not None
            if _is_complex_paragraph(p_new):
                parts = _complex_parts(p_new)
                format_changes.append({
                    'index': ni, 'kind': 'insert_format', 'text': bh.clip(new_texts[ni], 40),
                    'complex_parts': parts,
                    'summary': '新增段落含超链接/域/图片/书签等复杂结构，本工具只能把它插成纯文字，'
                               '这些结构整体丢失'})
                lost_structure_summary['insert_complex_paragraphs'] += 1
                for cat, n in parts.items():
                    key = cat + '_lost'
                    lost_structure_summary[key] = lost_structure_summary.get(key, 0) + n
            else:
                ppr_el = p_new.find(W + 'pPr')
                ppr_copy = _sanitize_ppr_copy(ppr_el) if ppr_el is not None else None
                sp['ppr_xml'] = _E.tostring(ppr_copy, encoding='unicode') if ppr_copy is not None else ''
                spans = [(r, t) for r, t in _run_spans(p_new) if t]
                if not spans:
                    sp['runs'] = [{'text': '', 'bold': False, 'rpr_xml': ''}]
                else:
                    runs = []
                    for r, t in spans:
                        color, bold = _run_fmt(r)
                        rs = {'text': t, 'bold': bool(bold)}
                        if color:
                            rs['color'] = color
                        rpr_el = r.find(W + 'rPr')
                        rs['rpr_xml'] = _E.tostring(copy.deepcopy(rpr_el), encoding='unicode') \
                            if rpr_el is not None else ''
                        runs.append(rs)
                    sp['runs'] = runs
            _note_whitespace(ni)
            specs.append(sp)
        return specs

    for tag, a1, a2, b1, b2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(a2 - a1):
                oi, ni = a1 + k, b1 + k
                kn_changed, kn_new_val = _equal_pair_diff(oi, ni)
                if kn_changed:
                    if old_texts[oi] == '':
                        # 空段落上的 keepNext 变化：anchor 的 text/contains 不许是空串（resolve_anchor
                        # 硬性拒绝），没有办法让 set_keepnext 的锚点指向"这一段自己"。规格允许的两条路
                        # ——借前一段的 contains 或整条标"不可回放"——这里选后者：单列进 unanchorable，
                        # 不塞进 ops，不能让这一条把整份补丁的回放挡在 resolve_anchor 的空串检查上。
                        unanchorable.append({
                            'index': oi, 'kind': 'set_keepnext', 'value': kn_new_val,
                            'prev_text': bh.clip(old_texts[oi - 1], 40) if oi else None,
                            'reason': 'keepNext 变化落在空段落，本工具的锚点机制（按段落自身文字定位）无法指向它'})
                        continue
                    op = {'id': f'D{seq:04d}', 'op': 'set_keepnext', 'anchor': uniq_anchor(oi),
                          'value': kn_new_val, 'reason': 'diff：keepNext 差异（文字未变）', 'evidence': 'diff'}
                    _authz(op, oi, check_complex=False)
                    ops.append(op)
                    seq += 1
            continue
        if tag == 'replace' and (a2 - a1) == 1 and (b2 - b1) == 1:
            oid = f'D{seq:04d}'
            op = {'id': oid, 'op': 'replace_paragraph', 'anchor': uniq_anchor(a1),
                  'old': old_texts[a1], 'new': new_texts[b1], 'reason': 'diff', 'evidence': 'diff'}
            _authz(op, a1, check_complex=True)
            _replace_format_note(a1, b1, oid)
            _note_replace_or_delete_loss(a1)
            _note_whitespace(b1)
            ops.append(op)
            seq += 1
            continue
        # 一般情形：前一份对应关系里第一对做 replace_paragraph（若两边都非空），
        # 旧稿多出的做 delete_paragraph，新稿多出的做 insert_after（锚在旧稿最后一段或前一段）
        pairs = min(a2 - a1, b2 - b1)
        for k in range(pairs):
            oi, ni = a1 + k, b1 + k
            if old_texts[oi] != new_texts[ni]:
                oid = f'D{seq:04d}'
                op = {'id': oid, 'op': 'replace_paragraph', 'anchor': uniq_anchor(oi),
                      'old': old_texts[oi], 'new': new_texts[ni], 'reason': 'diff', 'evidence': 'diff'}
                _authz(op, oi, check_complex=True)
                _replace_format_note(oi, ni, oid)
                _note_replace_or_delete_loss(oi)
                _note_whitespace(ni)
                ops.append(op)
                seq += 1
        for oi in range(a1 + pairs, a2):
            op = {'id': f'D{seq:04d}', 'op': 'delete_paragraph', 'anchor': uniq_anchor(oi),
                  'old': old_texts[oi], 'reason': 'diff', 'evidence': 'diff'}
            _authz(op, oi, check_complex=True)
            _note_replace_or_delete_loss(oi)
            ops.append(op)
            seq += 1
        if b2 - b1 > pairs:
            anchor_i = a1 + pairs - 1 if pairs else a1 - 1
            if anchor_i < 0:
                # 插在第一段之前
                new_paras = _new_para_specs(range(b1 + pairs, b2))
                op = {'id': f'D{seq:04d}', 'op': 'insert_before', 'anchor': uniq_anchor(a1),
                      'paragraphs': new_paras, 'reason': 'diff', 'evidence': 'diff'}
                _authz(op, a1, check_complex=False)
                ops.append(op)
            else:
                new_paras = _new_para_specs(range(b1 + pairs, b2))
                op = {'id': f'D{seq:04d}', 'op': 'insert_after', 'anchor': uniq_anchor(anchor_i),
                      'paragraphs': new_paras, 'reason': 'diff', 'evidence': 'diff'}
                _authz(op, anchor_i, check_complex=False)
                ops.append(op)
            seq += 1
    diff_approved_by = 'diff:apply_patch'
    diff_approval_ref = f'{Path(args.old).name} -> {Path(args.new).name}'
    patch = {'schema': 'baodian_patch_v1', 'book': args.book or '', 'parent_docx_sha256': d_old.sha256,
             'approved_by': diff_approved_by, 'approval_ref': diff_approval_ref,
             'ops': ops}
    out_guard_prof = dict(diff_prof or (load_profile(args.book) if args.book else {}) or {})
    out_guard_prof['frozen'] = False  # 补丁 json 本身不是书稿；目录级/冻结册目录守卫仍在 guard_write 内部生效
    # purpose='patch'：已批准的补丁（approved_by 不是 'diff:' 开头，或 approved_by/approval_ref
    # 跟这次 diff 会算出的自动值不一致，或任意 op 带 source_zone/allow_complex）一律不许被这次
    # diff 覆盖，不看它的 schema 是不是 baodian_patch_v1——上一轮"看见 schema 就当自己人"正是
    # 这里的漏洞。
    out_path = dl.guard_write(args.out, out_guard_prof, inputs=[args.old, args.new], kind='.json',
                               overwrite=_own_json(args.out, 'patch',
                                                    expected_approved_by=diff_approved_by,
                                                    expected_approval_ref=diff_approval_ref))
    out_path.write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding='utf-8')
    needs_authz_count = sum(1 for op in ops if op.get('needs_authorization'))
    rep = {'tool': 'apply_patch', 'version': TOOL_VERSION, 'mode': 'diff',
           'inputs': {'old': str(args.old), 'new': str(args.new), 'old_sha256': d_old.sha256, 'new_sha256': d_new.sha256},
           'needs_authorization_count': needs_authz_count, 'format_changes': format_changes,
           'format_changes_count': len(format_changes),
           'unanchorable': unanchorable, 'unanchorable_count': len(unanchorable),
           'lost_structure_summary': lost_structure_summary,
           'ops_count': len(ops), 'op_kinds': {}, 'out': str(out_path)}
    for op in ops:
        rep['op_kinds'][op['op']] = rep['op_kinds'].get(op['op'], 0) + 1
    if args.report:
        # --patch 不适用于 diff（diff 没有 --patch 参数），但 --out（补丁本身）必须列进 report 的
        # 守卫 inputs：report 与 out 不能是同一份文件，也不能互相覆盖对方。
        rep_path = _guard_report_path(args.report, diff_prof or {}, guard_inputs=[args.old, args.new, args.out],
                                       mode='diff')
        rep_path.write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'ops': len(ops), 'out': str(out_path)}, ensure_ascii=False))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--debug', action='store_true')
    sub = ap.add_subparsers(dest='command', required=True)

    c1 = sub.add_parser('check')
    c1.add_argument('--docx', required=True)
    c1.add_argument('--patch', required=True)
    c1.add_argument('--profile')
    c1.add_argument('--report')

    c2 = sub.add_parser('apply')
    c2.add_argument('--docx', required=True)
    c2.add_argument('--patch', required=True)
    c2.add_argument('--out', required=True)
    c2.add_argument('--profile')
    c2.add_argument('--report')
    c2.add_argument('--health', action='store_true')

    c3 = sub.add_parser('diff')
    c3.add_argument('--old', required=True)
    c3.add_argument('--new', required=True)
    c3.add_argument('--out', required=True)
    c3.add_argument('--book')
    c3.add_argument('--report')

    args = ap.parse_args(argv)
    try:
        if args.command == 'check':
            return cmd_check(args)
        if args.command == 'apply':
            return cmd_apply(args)
        if args.command == 'diff':
            return cmd_diff(args)
    except RefuseWrite as e:
        print('拒绝写出：' + str(e), file=sys.stderr)
        return 3
    except dl.GuardError as e:
        print('拒绝写出：' + str(e), file=sys.stderr)
        return 3
    except dl.ParentMismatch as e:
        print('父稿不符：' + str(e), file=sys.stderr)
        return 2
    except (dl.AlignmentError, Abort, ValueError, KeyError) as e:
        if args.debug:
            traceback.print_exc()
        print('中止：' + str(e), file=sys.stderr)
        return 2
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        print('错误：' + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
