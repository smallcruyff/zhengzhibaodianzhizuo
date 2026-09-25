#!/usr/bin/env python3
"""按规则做“全书推广”——写书侧通用工具（流程优化线 2026-09-24，第三批）。

用途：
    主代理/用户在某一处认可一种改法后，不再让模型逐题去全书里找同样的地方改（那样一轮就是
    几亿 token），而是把“认可的改法”写成一条规则 JSON：在哪些区位/样式/栏目/题型/部分（bh.walk
    判的 zone、样式名、【标签】、例题 kind、结构 part）、命中什么正则，套用什么改法（正则替换，
    或交给模型逐条改写）。本工具只负责“列候选＋切批＋把决定拼成 apply_patch 认得的补丁＋核对改
    后是否还有漏网”，机械落地仍由 apply_patch.py 完成——绝不做“回车全局替换”。

用法：
    sweep_rule.py find     --docx X.docx --rule r.json [--profile P] [--out cands.json]
    sweep_rule.py pack     --cands c.json --per-batch N --out DIR
    sweep_rule.py to-patch --docx X.docx --cands c.json --decisions d.json --rule r.json --out patch.json
                           [--profile P] [--allow-draft-profile]
    sweep_rule.py verify   --docx Y.docx --rule r.json [--profile P] [--decisions d.json]

    --profile 缺省按 profile_lib.detect_profile(docx) 自动判断；判不出且规则/候选文件里也没有
    book_id 时报错，不瞎猜。

读写承诺：
    - find/verify 只读 docx 与规则 JSON；--out 给了才写候选/报告 JSON（未给就打印到 stdout）。
    - pack 只读候选 JSON；把它切成小批写进 --out 指定的目录（目录须已存在或可创建于安全路径）。
    - to-patch 只读 docx／候选／决定 JSON；写出的是 baodian_patch_v1 补丁 JSON（apply_patch.py
      吃的那种），本工具本身**不改任何 .docx**，真正落地永远是另起一步 apply_patch.py check/apply。
    - 所有输出路径一律先过 docx_lib.guard_write()：冻结册目录、Skill/项目根等受保护目录拒写；
      系统临时目录放行；默认不覆盖已存在文件（可用 --overwrite）。
    - 不改 batch_health.py / docx_lib.py / apply_patch.py / profile_lib.py / profiles/；判定
      （认题块、栏目、区位、样式）一律调用 batch_health.walk/Prof，本工具不重复实现；补丁的安全
      校验（锚点唯一、题面区授权、禁用词表、同段冲突……）一律调用 apply_patch.check_ops，本工具
      不重复实现，也不绕过它。
    - 不联网、不启子进程写文件、不运行 collab.py。

退出码：
    find   ：0 没有候选；1 找到候选（正常情况，不是错误）；2 规则/输入错误（regex 非法、docx 打不
             开、书册判不出等）。
    pack   ：0 切出至少一批并写出；1 候选为空（没什么可切）；2 输入错误；3 拒绝写出（守卫）。
    to-patch：0 生成了带 ≥1 条 op 的补丁并写出、且已用 apply_patch.check_ops 在原稿上验证过锚点
             唯一/题面区授权/禁用词表；1 决定全部 reject（没有可落地的改动，仍会写出一份 ops:[]
             的补丁存档，除非 --no-empty-patch）；2 输入/决定错误或整批中止（决定缺条、候选段
             在 find 之后被改、锚点非唯一、题面区未显式授权、新文字命中禁用词、规则/补丁格式错误
             ——均不留输出文件）；3 拒绝写出（目标书册已冻结，或 guard_write 守卫）。
    verify ：0 规则重新跑一遍后零候选（或与 --decisions 对照，剩余数正好等于当初 reject 的数量）；
             1 还有未预期的候选残留；2 输入错误。
    异常一律转中文提示打印到 stderr；--debug 打开时打印 traceback。

规则 JSON（本工具自定的格式，不是 profiles/ 的字段，不需要登记进书册配置）：
{
  "id": "rm_benjiedian", "desc": "学生正文里的工程词“本节点”",
  "allow_source_zone": false,      // 缺省＝false：不给 zones 时，题面/标题区（source/title）
                                     // 默认也不进候选，跟 toc/cover 一样；确实要碰题面才置 true，
                                     // 或者在 match.zones 里显式写上 source/title
  "match": {
    "zones": ["teaching", "rubric", "outside", "source", "title", "drill", "heading"],
        // 缺省＝除 toc/cover/source/title 外的全部区位；区位判定来自 bh.walk 给每段标的
        // it['zone']；写了这里的任何一个值，find/verify 都会先对照本书的已知取值全集校验
        // （zones 全集固定；styles 看文档里实际出现过的样式名；labels/parts/kinds 看 profile
        // 声明的——拼错、漏中括号、书册判错都会在这里退出 2，不会静默得到 0 候选）
    "styles": ["宝典正文"],          // 缺省＝不限样式（对应 w:pStyle 的 w:name）
    "labels": ["【答案落点】"],       // 缺省＝不限；对应 it['label']（bh.walk 认的段内【…】标签，
                                     // 与 profile 的 labels_rules.* 同一份写法，含中括号）
    "kinds": ["subjective", "choice"], // 缺省＝不限；对应该段所在例题块 it['ex']['kind']
    "parts": ["TOPIC"],             // 缺省＝不限；对应 profile 的 structure.parts[].id
    "colors": ["0000FF"],           // 缺省＝不限；命中片段每个字所在 run 的显式颜色（6 位十六
                                     // 进制，大小写不敏感）都要落在这个集合里才算数——本工具
                                     // 目前唯一能表达“格式类推广”的入口，配 action.type=
                                     // set_format 使用；replace_regex/model_rewrite 规则也能拿
                                     // 它筛（比如“只改红色的‘的地得’”）
    "bold": true,                   // 缺省＝不限；命中片段每个字是否加粗都要等于这个值
    "regex": "本节点"                // model_rewrite/set_format 规则必须给；replace_regex 规则
                                     // 缺省时退化为用 action.pattern 当 match.regex
  },
  "exclude": { ...同 match 的维度（含 colors/bold），外加 "regex": "…" ... },
        // 命中即整段跳过（colors/bold 是"命中片段落在这个格式里就跳过"）；维度留空＝不筛
  "action": {
    "type": "replace_regex", "pattern": "本节点", "repl": ""    // re.sub 语义，repl 可用 \\1；
                                     // accept 时按整段重新匹配算替换片段（不是只在切片上
                                     // re.sub），带前瞻/后顾/^$ 的正则也能正确生效
  }
  // 或： "action": {"type": "model_rewrite", "instruction": "去掉工程词“本节点”，保持句子通顺"}
  // 或： "action": {"type": "set_format", "format": {"color": "000000", "bold": false}}
        // 只改格式、不改文字：命中片段必须在段内唯一（不支持靠扩上下文消歧，那样会连带改到
        // 别处的格式），产出 apply_patch 的 set_format op；决定里可给 "format" 覆盖规则默认值
}
跨书用 profile_probe.py 生成的草案配置（顶层带 "_needs_confirm" 且非空）时，to-patch 默认拒绝
生成补丁（退出 2），须显式加 --allow-draft-profile 才放行；补丁会记一笔 draft_profile_allowed。

候选 JSON（find 的输出，schema=baodian_sweep_cands_v1）：docx/docx_sha256/profile/rule_id/
total_candidates/by_part/by_node 之外，candidates[] 每条：cand_id、para（段号，仅供人工参考——
to-patch 不采信，段落定位一律以在原稿上重新核算的结果为准）、part/node/method、block_title/
block_src/block_kind（所在例题块，没有则 None）、zone/label/style、text（段落全文）、hit_spans
（命中片段在 text 里的 [start,end] 列表）、hit_count、prev_text（上一段全文，供人工/模型消歧，
不是锚点本身）、predicted_new_text（仅 replace_regex：对整段文字一次性 re.sub 后的全文；
model_rewrite/set_format 规则此字段为 null，新文本/格式由决定文件给）、mixed_format（段内颜色
不止一种，整段重写会坍缩格式）、looks_like_source（题面标签兜底命中但 zone 判的不是
source/title——这类候选决定也必须给 source_zone，不管 zone 字段写的是什么）。

决定 JSON（pack 之后人工/模型填、喂给 to-patch；本工具不规定文件名，只规定内容）：
{"approved_by": "claude:会话ID | codex:任务ID | user", "approval_ref": "台账编号或说明",
 "items": {"<cand_id>": {"decision": "accept|reject|edit", "reason": "…"（accept/edit 必填）,
   "new_snippet": "…"（命中 1 处时可选：只给替换片段，生成 1 条 replace_text；不给则 accept 时
                    用规则自己按 action.pattern/repl 对命中片段算，edit 时必须给它或 new_text）,
   "new_snippets": ["…", "…"]（命中 >1 处时推荐：按 hit_spans 顺序逐处给替换片段，生成多条
                    replace_text，各自只改自己那一小片、其余原文与格式原样保留；不给则 accept
                    时按 action.pattern/repl 逐处自动算），
   "new_text": "…"（命中 >1 处且明确要整段重写时才给：生成 1 条 replace_paragraph——会把全段
                    坍缩成段内第一个 run 的格式，段内本来有多种颜色/加粗会被抹平，只在确认这段
                    本来就是单一格式、或愿意承担这个风险时才用；有 new_snippets 更安全，优先它）,
   "format": {"color": "…", "bold": true}（仅 action.type=set_format：覆盖规则的 action.format；
                    不给则用规则默认值。set_format 没有 new_snippet/new_snippets/new_text——只改
                    格式不改文字），
   "source_zone": "restore|approved_edit"（锚点段落在 source/title 区、或段首是题面类标签
                    （candidate 的 looks_like_source=true）时必给，否则整批中止；zone 本身的判定
                    与 apply_patch 完全同口径——本工具不判，转交 apply_patch.check_ops 判，但题面
                    标签兜底是本工具自己加的一道，不依赖 apply_patch 那边的 zone 判断是否准确），
   "evidence": "…"}}}
每个候选都必须在 items 里有对应决定（哪怕是 reject），漏掉任何一条、或出现候选文件里没有的
cand_id → 整批中止，不留输出。

读取的配置字段：本工具不给 profiles/ 增补新字段；沿用 apply_patch.py 已经在读的那些
（structure.*/styles.*/example_titles/labels_rules.*/drill.*/student_text.* 等，全部转交
batch_health.Prof/walk 与 apply_patch.check_ops 解释）。
"""
import argparse
import copy
import json
import re
import sys
import traceback
from collections import Counter, OrderedDict
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
import apply_patch as ap  # noqa: E402
from profile_lib import load_profile, detect_profile  # noqa: E402

TOOL_VERSION = '1.1.0'
SCHEMA_CANDS = 'baodian_sweep_cands_v1'
SCHEMA_PATCH = 'baodian_patch_v1'
DEFAULT_EXCLUDE_ZONES = {'toc', 'cover'}
# 题面/标题区默认也排除：不给 zones 时，规则不该顺手把题面也当候选（返修230教训）；
# 规则确实要碰题面（比如按题面标签兜底改错别字）时须显式在 match.zones 里写 source/title，
# 或者在规则顶层给 allow_source_zone:true。
SOURCE_ZONES = {'source', 'title'}
# bh.walk 给每段标的 zone 全集（见 batch_health.walk 文档字符串）；规则里 zones 拼错时应
# 在 find/verify 就报错退出，不能静默得到 0 候选。
VALID_ZONES = {'cover', 'heading', 'toc', 'title', 'source', 'teaching', 'rubric', 'outside', 'drill'}
# 题面类标签兜底名单：跨书用草案配置时，block_labels 可能没认全，这里按常见题面标签硬兜底——
# 命中即视为题面，不论 bh.walk 判的 zone 是什么，都要求决定里显式给 source_zone。
FALLBACK_SOURCE_LABELS = {'【原题材料】', '【材料】', '【材料呈现】', '【题目】', '【设问】', '【问题】',
                          '【原题】', '【情境】', '【试题】', '【题干】'}
DIMS = ('zones', 'styles', 'labels', 'kinds', 'parts')


class Abort(Exception):
    """整批中止（退出码 2）：规则非法、决定缺条、候选段已变、题面区未授权、锚点非唯一……"""


# ------------------------------------------------------------------ 规则 / 书册
def _load_prof(profile_arg, docx_path, cands_book=None):
    if profile_arg:
        return load_profile(profile_arg)
    pd = detect_profile(docx_path)
    if pd is not None:
        return pd
    if cands_book:
        return load_profile(cands_book)
    raise Abort('无法判断书册：请用 --profile 指定（或规则/候选文件里给出可识别的书册线索）')


_COLOR_RX = re.compile(r'^[0-9A-Fa-f]{6}$')


def _check_fmt_spec(spec, where):
    """校验 match/exclude 里的 colors/bold 取值格式（不校验是否在文档里真出现过——颜色值
    本就是任意 6 位十六进制，不像 zones/labels/parts 那样有一份可枚举的全集）。"""
    colors = spec.get('colors')
    if colors is not None:
        if not isinstance(colors, list) or not colors:
            raise Abort(f'{where}.colors 必须是非空数组（6 位十六进制颜色，如 "0000FF"）')
        for c in colors:
            if not isinstance(c, str) or not _COLOR_RX.match(c):
                raise Abort(f'{where}.colors 里的 {c!r} 不是合法的 6 位十六进制颜色')
    bold = spec.get('bold')
    if bold is not None and not isinstance(bold, bool):
        raise Abort(f'{where}.bold 必须是 true/false')


def _load_rule(path):
    try:
        rule = json.loads(Path(path).read_text(encoding='utf-8'))
    except Exception as e:
        raise Abort(f'规则文件不是合法 JSON：{e}')
    if not isinstance(rule, dict) or 'match' not in rule or 'action' not in rule:
        raise Abort('规则缺 match 或 action 字段')
    match = rule.get('match') or {}
    act = rule.get('action') or {}
    if act.get('type') not in ('replace_regex', 'model_rewrite', 'set_format'):
        raise Abort(f'规则 action.type 必须是 replace_regex/model_rewrite/set_format，得到 {act.get("type")!r}')
    if act.get('type') == 'replace_regex':
        if not act.get('pattern'):
            raise Abort('规则 action.type=replace_regex 必须给 action.pattern')
        try:
            re.compile(act['pattern'])
        except re.error as e:
            raise Abort(f'规则 action.pattern 非法：{e}')
    if act.get('type') == 'set_format':
        fmt = act.get('format')
        if not isinstance(fmt, dict) or not fmt:
            raise Abort('规则 action.type=set_format 必须给 action.format（至少 color 或 bold 之一）')
        if 'color' in fmt and (not isinstance(fmt['color'], str) or not _COLOR_RX.match(fmt['color'])):
            raise Abort(f'规则 action.format.color 不是合法的 6 位十六进制颜色：{fmt.get("color")!r}')
        if 'bold' in fmt and not isinstance(fmt['bold'], bool):
            raise Abort('规则 action.format.bold 必须是 true/false')
        if not match.get('regex'):
            raise Abort('规则 action.type=set_format 必须显式给 match.regex（不像 replace_regex 那样能退化用 '
                        'action.pattern——set_format 没有 pattern 概念）')
    match_rx_src = match.get('regex') or (act.get('pattern') if act.get('type') == 'replace_regex' else None)
    if not match_rx_src:
        raise Abort('规则缺 match.regex（model_rewrite/set_format 规则必须给；replace_regex 规则缺省时退化为 '
                    'action.pattern）')
    try:
        match_rx = re.compile(match_rx_src)
    except re.error as e:
        raise Abort(f'规则 match.regex 非法：{e}')
    exclude = rule.get('exclude') or {}
    if exclude.get('regex'):
        try:
            re.compile(exclude['regex'])
        except re.error as e:
            raise Abort(f'规则 exclude.regex 非法：{e}')
    _check_fmt_spec(match, 'match')
    _check_fmt_spec(exclude, 'exclude')
    return rule, match_rx


def _known_dims(prof, P, items):
    """规则里 zones/styles/labels/kinds/parts 各维度的已知取值全集，供 find/verify 校验；
    拼错时应该在这里就报错退出（2），不能静默得到 0 候选（见 verify_sweep_rule.json #3）。"""
    valid_parts = {pt.get('id') for pt in P.parts if pt.get('id')}
    valid_kinds = {t.get('kind') for t in (prof.get('example_titles') or []) if t.get('kind')} | \
        {t[0] for t in P.titles if t[0]}
    for pt in P.parts:
        valid_kinds |= set((pt.get('kind_override') or {}).values())
    valid_labels = set(P.block_labels) | set(P.section_labels) | FALLBACK_SOURCE_LABELS
    valid_styles = {it.get('style') for it in items if it.get('style')}
    return {'zones': VALID_ZONES, 'parts': valid_parts, 'kinds': valid_kinds,
            'labels': valid_labels, 'styles': valid_styles}


def _check_dim_values(rule, known):
    """规则 match/exclude 里各维度的取值必须落在 _known_dims() 给出的全集里，否则整批中止（2），
    并把可用取值列进错误信息，方便照着改（不用另外查文档）。"""
    for spec_name in ('match', 'exclude'):
        spec = rule.get(spec_name) or {}
        for dim in DIMS:
            vals = spec.get(dim)
            if not vals:
                continue
            known_vals = known.get(dim) or set()
            unknown = sorted(set(vals) - known_vals)
            if unknown:
                sample = '、'.join(sorted(known_vals)[:30]) or '(本书当前没有已知取值)'
                raise Abort(f'规则 {spec_name}.{dim} 里有未知取值 {unknown}；本书已知 {dim}：{sample}'
                            f'{"…" if len(known_vals) > 30 else ""}')


def cands_rule_id_mismatch(cands_path, rule):
    try:
        obj = json.loads(Path(cands_path).read_text(encoding='utf-8'))
    except Exception:
        return False
    cid, rid = obj.get('rule_id'), rule.get('id')
    return bool(cid and rid and cid != rid)


def _spec_hits(it, spec):
    """spec 给的维度（zones/styles/labels/kinds/parts）都满足才算命中；没给的维度不限。"""
    if spec.get('zones') and it.get('zone') not in set(spec['zones']):
        return False
    if spec.get('styles') and it.get('style') not in set(spec['styles']):
        return False
    if spec.get('labels') and it.get('label') not in set(spec['labels']):
        return False
    if spec.get('parts') and it.get('part') not in set(spec['parts']):
        return False
    if spec.get('kinds'):
        ex = it.get('ex')
        if not ex or ex.get('kind') not in set(spec['kinds']):
            return False
    return True


def _excluded(it, exclude):
    if not exclude:
        return False
    has_dim = any(exclude.get(k) for k in DIMS)
    if has_dim and not _spec_hits(it, exclude):
        return False
    rx_src = exclude.get('regex')
    if rx_src and not re.search(rx_src, it['text']):
        return False
    if not has_dim and not rx_src:
        return False
    return True


# ------------------------------------------------------------------ 段内逐字格式（跨 run 安全 / colors/bold 匹配）
def _para_fmt_map(el):
    """段落 el 的逐字格式，对齐到 bh/dl 的取字口径（ZW 折叠＋两端 strip 后的 it['text']）。
    返回 (raw, fmt_list, text, idx_map)：
      raw      —— ap._run_spans 按 run 顺序拼出的原始整段文字（未折叠 ZW、未 strip）；
      fmt_list —— 与 raw 逐字对应的 (color, bold)（ap._run_fmt，即该字所在 run 的显式格式）；
      text     —— raw 按 dl.para_text 同一口径折叠/裁剪后的文字，理应与 it['text'] 完全相同
                  （dl.open_docx 的 check_alignment 已经在整份文档上验证过这一点）；
      idx_map  —— idx_map[j] 是 text[j] 对应的 raw 下标，取 fmt_list[idx_map[j]] 即 text[j] 的格式。
    跨 run 定位（_widen_unique 的格式边界判断）与 colors/bold 匹配都基于这份映射，不重复实现
    ap._run_spans/_run_fmt，只是把它们的结果换算到 sweep_rule 一直在用的“段落全文下标”口径。"""
    spans = ap._run_spans(el)
    raw_parts, fmt_parts = [], []
    for r, t in spans:
        fmt = ap._run_fmt(r)
        raw_parts.append(t)
        fmt_parts.extend([fmt] * len(t))
    raw = ''.join(raw_parts)
    kept_idx = [i for i, ch in enumerate(raw) if ord(ch) not in bh.ZW]
    translated = ''.join(raw[i] for i in kept_idx)
    lead = len(translated) - len(translated.lstrip())
    text = translated.strip()
    idx_map = kept_idx[lead:lead + len(text)]
    return raw, fmt_parts, text, idx_map


def _fmt_sig(fmap, i):
    """cand['text'] 下标 i 处字符的 (color, bold)；越界返回 None（视为与任何格式都不同）。"""
    _, fmt_list, _, idx_map = fmap
    if i < 0 or i >= len(idx_map):
        return None
    return fmt_list[idx_map[i]]


def _spans_match_fmt(fmap, spans, colors_spec, bold_spec):
    """按 match/exclude 里的 colors/bold 过滤命中片段：片段内每个字都要满足（片段本身跨格式时，
    只要有一个字不满足就整个片段不算数——宁可漏检也不产出一条自己都说不清格式的候选）。
    colors_spec/bold_spec 都没给时原样放行。"""
    if not colors_spec and bold_spec is None:
        return spans
    colors_set = set(c.upper() for c in colors_spec) if colors_spec else None
    kept = []
    for s, e in spans:
        ok = True
        for i in range(s, e):
            c, b = _fmt_sig(fmap, i) or (None, False)
            if colors_set is not None and (c or '').upper() not in colors_set:
                ok = False
                break
            if bold_spec is not None and bool(b) != bool(bold_spec):
                ok = False
                break
        if ok:
            kept.append([s, e])
    return kept


def _looks_like_source_label(text, P):
    """题面标签兜底：不管 bh.walk（可能用的是没确认的草案配置）判的 zone 是什么，段首是
    profile 声明的 source_labels 或本工具硬兜底的常见题面标签时，一律按题面对待（要求
    决定必须给 source_zone）。见 verify_sweep_rule.json #4：文化草案漏认题块，题面被改。"""
    m = bh.LABEL_START.match(text)
    if not m:
        return False
    lab = bh.norm_label(m.group(1))
    return lab in P.source_labels or lab in FALLBACK_SOURCE_LABELS


# ------------------------------------------------------------------ find
def _iter_candidates(items, P, rule, match_rx, paras=None):
    blocks = bh.walk(items, P)
    match = rule.get('match') or {}
    exclude = rule.get('exclude') or {}
    zones_given = bool(match.get('zones'))
    allow_source_zone = bool(rule.get('allow_source_zone'))
    act = rule.get('action') or {}
    repl_rx = re.compile(act['pattern']) if act.get('type') == 'replace_regex' else None
    repl = act.get('repl', '') if act.get('type') == 'replace_regex' else None
    m_colors, m_bold = match.get('colors'), match.get('bold')
    x_colors, x_bold = exclude.get('colors'), exclude.get('bold')
    for it in items:
        if not it['text']:
            continue
        if not zones_given:
            if it.get('zone') in DEFAULT_EXCLUDE_ZONES:
                continue
            # 题面/标题区默认不进候选，除非规则显式要（match.zones 里写了 source/title，或
            # allow_source_zone:true）——不能靠“反正 apply_patch 会挡”，那条防线本身依赖
            # 同一份（可能是草案的）profile 判出来的 zone，见 verify_sweep_rule.json #8。
            if not allow_source_zone and it.get('zone') in SOURCE_ZONES:
                continue
        if not _spec_hits(it, match):
            continue
        if _excluded(it, exclude):
            continue
        spans = [list(m.span()) for m in match_rx.finditer(it['text'])]
        if not spans:
            continue
        if (m_colors or m_bold is not None or x_colors or x_bold is not None) and paras is not None:
            fmap = _para_fmt_map(paras[it['i']])
            if m_colors or m_bold is not None:
                spans = _spans_match_fmt(fmap, spans, m_colors, m_bold)
            if x_colors or x_bold is not None:
                excluded_spans = _spans_match_fmt(fmap, spans, x_colors, x_bold)
                spans = [sp for sp in spans if sp not in excluded_spans]
            if not spans:
                continue
        ex = it.get('ex')
        predicted = repl_rx.sub(repl, it['text']) if repl_rx is not None else None
        yield it, spans, ex, predicted
    return blocks


def cmd_find(args):
    rule, match_rx = _load_rule(args.rule)
    prof = _load_prof(args.profile, args.docx)
    d = dl.open_docx(args.docx)
    items = d.items
    P = bh.Prof(prof)
    _check_dim_values(rule, _known_dims(prof, P, items))
    cands = []
    by_part, by_node = Counter(), Counter()
    for it, spans, ex, predicted in _iter_candidates(items, P, rule, match_rx, paras=d.paras):
        colors = sorted({c for _, c in (it.get('runs') or []) if c})
        cand = OrderedDict([
            ('cand_id', f"{rule.get('id', 'R')}-{it['i']:06d}"),
            ('rule_id', rule.get('id')),
            ('para', it['i']),
            ('part', it.get('part')), ('node', bh.clip(it.get('node') or '', 40)),
            ('method', it.get('method')),
            ('block_title', bh.clip(ex['title'], 40) if ex else None),
            ('block_src', ex.get('src') if ex else None),
            ('block_kind', ex.get('kind') if ex else None),
            ('zone', it.get('zone')), ('label', it.get('label')), ('style', it.get('style')),
            ('text', it['text']),
            ('hit_spans', spans), ('hit_count', len(spans)),
            ('prev_text', items[it['i'] - 1]['text'] if it['i'] > 0 else None),
            ('predicted_new_text', predicted),
            # 段内颜色不止一种时，整段 replace_paragraph 会把全段坍缩成第一个 run 的格式
            # （apply_patch.apply_replace_paragraph 的既定行为——只保留首个 run 的 rPr），
            # 命中 >1 处又想保真必须走 per-hit 的 replace_text（见 new_snippets）；这里提前
            # 标出来，供 pack/模型判断，避免重演“答案落点蓝字过多全书返修”那种坍缩事故。
            ('mixed_format', len(colors) > 1),
            ('looks_like_source', _looks_like_source_label(it['text'], P) and it.get('zone') not in SOURCE_ZONES),
        ])
        cands.append(cand)
        by_part[it.get('part')] += 1
        by_node[(it.get('part'), it.get('node'))] += 1
    result = OrderedDict([
        ('schema', SCHEMA_CANDS), ('tool', 'sweep_rule'), ('tool_version', TOOL_VERSION), ('mode', 'find'),
        ('rule_id', rule.get('id')), ('rule_desc', rule.get('desc')),
        ('docx', str(Path(args.docx).resolve())), ('docx_sha256', dl.sha256_file(args.docx)),
        ('profile', prof.get('book_id')),
        ('total_candidates', len(cands)),
        ('by_part', dict(by_part)),
        ('by_node', [OrderedDict([('part', k[0]), ('node', k[1]), ('count', v)]) for k, v in by_node.items()]),
        ('candidates', cands),
    ])
    _emit(result, args.out, prof, [args.docx], args.overwrite)
    return 1 if cands else 0


def cmd_verify(args):
    rule, match_rx = _load_rule(args.rule)
    prof = _load_prof(args.profile, args.docx)
    d = dl.open_docx(args.docx)
    items = d.items
    P = bh.Prof(prof)
    _check_dim_values(rule, _known_dims(prof, P, items))
    remaining = [it['i'] for it, spans, ex, predicted
                 in _iter_candidates(items, P, rule, match_rx, paras=d.paras)]
    result = OrderedDict([
        ('schema', 'baodian_sweep_verify_v1'), ('tool', 'sweep_rule'), ('tool_version', TOOL_VERSION),
        ('mode', 'verify'), ('rule_id', rule.get('id')),
        ('docx', str(Path(args.docx).resolve())), ('docx_sha256', dl.sha256_file(args.docx)),
        ('profile', prof.get('book_id')), ('remaining_count', len(remaining)), ('remaining_paras', remaining),
    ])
    expected = None
    if args.decisions:
        dec = json.loads(Path(args.decisions).read_text(encoding='utf-8'))
        expected = sum(1 for v in (dec.get('items') or {}).values() if v.get('decision') == 'reject')
        result['expected_remaining_from_decisions'] = expected
        # 段号在 replace_text/replace_paragraph 之后不变（本工具/apply_patch 不做增删段），
        # 数量吻合即可当作“确实只剩被 reject 的”；不吻合只报数量差异，具体是不是同一批段落
        # 由主代理核对 remaining_paras。
        result['matches_expected'] = (expected == len(remaining))
    _emit(result, args.out, prof, [args.docx], args.overwrite)
    if expected is not None:
        return 0 if result['matches_expected'] else 1
    return 1 if remaining else 0


def _emit(obj, out, prof, inputs, overwrite):
    """find/verify 只读；候选/verify 报告本身不是书稿，冻结册判定不适用于它俩（与
    apply_patch._guard_report_path 同一口径——只读检查允许出报告），目录级守卫仍然生效。"""
    if out:
        report_prof = dict(prof or {})
        report_prof['frozen'] = False
        p = dl.guard_write(out, report_prof, inputs=inputs, kind='.json', overwrite=overwrite)
        p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    else:
        print(json.dumps(obj, ensure_ascii=False, indent=1))


# ------------------------------------------------------------------ pack
PACK_INSTRUCTION = (
    '逐条给出决定，回一个 JSON：{"approved_by": "…", "approval_ref": "…", "items": {'
    '"<cand_id>": {"decision": "accept|reject|edit", "reason": "…（accept/edit 必填，写清为什么这样改）", '
    '"new_snippet": "…（hit_spans 只有1个时可选：只给替换片段）", '
    '"new_snippets": ["…", ...]（hit_spans 有多个时优先用这个：按 hit_spans 顺序逐处给替换片段，'
    '保留段内其余原文与格式；不要用整段 new_text 去改多颜色/多格式的段落，会把全段格式坍缩成一种）", '
    '"new_text": "…（只在确认这段本来就是单一格式、必须整段重写时才给）", '
    '"source_zone": "restore|approved_edit（仅当 zone 是 source/title 时必给，否则这条会让整批中止）", '
    '"evidence": "…"}}}。每条候选都必须出现在 items 里，哪怕是 reject。不确定就 reject 并写明原因，'
    '不要因为前面几条像就整批 accept——命中片段可能来自完全不同的语境；mixed_format=true 的候选'
    '尤其要用 new_snippet(s)，不要用 new_text。'
)


def _guard_location(o, prof):
    """校验某个路径（目录或文件，不要求已存在）是否落在冻结册目录/其他受保护根目录内——
    与 dl.guard_write 的判据完全一致，只是跳过它前半段“o.parent 必须已存在”的检查（pack 的
    输出目录第一次跑时通常还没建出来，没法先拿一个不存在父目录的文件去问 guard_write）。
    不重新实现判据本身：直接复用 dl/bh 已有的私有 helper（_frozen_hits/_within/_temp_roots/
    _cf/list_profiles/load_profile），只是换一种不依赖存在性的调用顺序。"""
    if prof and prof.get('frozen'):
        raise dl.GuardError(f'{prof.get("title", prof.get("book_id"))} 已冻结，拒绝写出：{prof.get("frozen_note", "")}')
    fz = dl._frozen_hits(o)
    if fz:
        raise dl.GuardError(f'落在冻结册目录（{fz[0].get("title")}），拒绝写出')
    if any(bh._within(o, t) for t in bh._temp_roots()):
        return
    roots = []
    for name in dl.list_profiles():
        try:
            r = dl.load_profile(name).get('paths', {}).get('root')
        except Exception:
            r = None
        if r:
            roots.append(Path(r).expanduser().resolve())
    for r in (bh.cfg(prof, 'output_guard.protected_roots', []) or []) if prof else []:
        roots.append(Path(r).expanduser().resolve())
    roots.append(Path(__file__).resolve().parent.parent)
    allow = re.compile(dl.WRITE_ALLOW_RX)
    for r in roots:
        if bh._within(o, r):
            rel = '/' + bh._cf(o)[len(bh._cf(r).rstrip('/')) + 1:]
            if not allow.search(str(Path(rel).parent) + '/'):
                raise dl.GuardError(f'落在受保护目录 {r} 内（只允许 …/协作/候选/<谁>/<批次>/构建/ 之下或系统临时目录）')


def cmd_pack(args):
    obj = json.loads(Path(args.cands).read_text(encoding='utf-8'))
    if obj.get('schema') != SCHEMA_CANDS:
        raise Abort(f'候选文件 schema 不是 {SCHEMA_CANDS}')
    cands = obj.get('candidates') or []
    if not cands:
        print('候选为空，没有可切的批次', file=sys.stderr)
        return 1
    n = max(1, args.per_batch)
    batches = [cands[i:i + n] for i in range(0, len(cands), n)]
    out_dir = Path(args.out).expanduser().resolve()
    # 先核这个目录位置本身允不允许写（目录很可能还不存在，不能先 mkdir 再问），
    # 不通过就什么都不建——不留一个空目录在受保护的地方（见 verify_sweep_rule.json #5）。
    _guard_location(out_dir, None)
    created_dir = not out_dir.exists()
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        # 第一遍：只核对全部目标文件的写权（已存在/不覆盖、受保护根……），不写任何内容；
        # 全部通过才进入第二遍真正落盘——整批要么全写、要么一个字节都不落地。
        targets = [dl.guard_write(out_dir / f'batch_{bi:04d}.json', None, inputs=[args.cands],
                                   kind='.json', overwrite=args.overwrite)
                   for bi in range(1, len(batches) + 1)]
        idx_target = dl.guard_write(out_dir / 'index.json', None, inputs=[args.cands], kind='.json',
                                     overwrite=args.overwrite)
        files = []
        for bi, (batch, target) in enumerate(zip(batches, targets), 1):
            items_out = []
            for c in batch:
                items_out.append(OrderedDict([
                    ('cand_id', c['cand_id']), ('block_title', c.get('block_title')), ('block_src', c.get('block_src')),
                    ('part', c.get('part')), ('node', c.get('node')),
                    ('zone', c.get('zone')), ('label', c.get('label')), ('style', c.get('style')),
                    ('prev_text', c.get('prev_text')), ('text', c['text']),
                    ('excerpt', bh.window(c['text'], c['hit_spans'][0][0], c['hit_spans'][0][1], 30) if c.get('hit_spans') else None),
                    ('hit_spans', c.get('hit_spans')), ('mixed_format', c.get('mixed_format')),
                    ('looks_like_source', c.get('looks_like_source')),
                    ('predicted_new_text', c.get('predicted_new_text')),
                ]))
            target.write_text(json.dumps(OrderedDict([
                ('rule_id', obj.get('rule_id')), ('rule_desc', obj.get('rule_desc')),
                ('batch', bi), ('total_batches', len(batches)), ('instruction', PACK_INSTRUCTION),
                ('items', items_out),
            ]), ensure_ascii=False, indent=1), encoding='utf-8')
            files.append(target.name)
        idx_target.write_text(json.dumps(OrderedDict([
            ('rule_id', obj.get('rule_id')), ('cands_file', str(Path(args.cands).resolve())),
            ('total_candidates', len(cands)), ('per_batch', n), ('batches', files),
        ]), ensure_ascii=False, indent=1), encoding='utf-8')
    except BaseException:
        if created_dir and out_dir.is_dir() and not any(out_dir.iterdir()):
            out_dir.rmdir()
        raise
    print(json.dumps({'batches': len(files), 'total_candidates': len(cands)}, ensure_ascii=False))
    return 0


# ------------------------------------------------------------------ to-patch
def _ctx_ok(fmap, lo, hi, s, e):
    """widen 后的 [lo,hi) 是否仍在格式边界内：左侧新增的上下文字符（[lo,s)）必须和命中起点 s
    处同格式，右侧新增的（[e,hi)）必须和命中终点前一字（e-1）同格式——命中片段本身 [s,e) 不
    受限（那是模型明确要改的地方，本来就可能跨格式）。任何一个新增字符对不上，说明这一步 widen
    会跨过 run/格式边界：apply_patch 的跨 run replace_text 会把 [lo,hi) 整体按第一个 run 的格式
    重写，越界带进来的上下文字符就会被改成命中片段的格式（蓝/粗/红……），这正是
    verify_sweep_rule.json #1 那类事故的成因，所以这里直接判不安全，不采用。"""
    left_anchor = _fmt_sig(fmap, s) if s < e else None
    for i in range(lo, s):
        if _fmt_sig(fmap, i) != left_anchor:
            return False
    right_anchor = _fmt_sig(fmap, e - 1) if s < e else None
    for i in range(e, hi):
        if _fmt_sig(fmap, i) != right_anchor:
            return False
    return True


def _widen_unique(full, s, e, lo_bound, hi_bound, fmap):
    """把 [s,e) 在 [lo_bound,hi_bound) 范围内向两边扩，直到 full[lo:hi] 在整段里只出现一次
    （给 replace_text 当 old），且每一步新增的上下文字符都要过 _ctx_ok（不越过命中片段的格式
    边界）。一侧扩不动（越界）就试另一侧；两侧都扩不动、又还没唯一，如实放弃（返回 None），
    不瞎猜、更不允许把命中片段之外、格式不同的字也带进 old/new（旧版本这里只顾唯一性、不管
    格式，见 verify_sweep_rule.json #1 的 blocker）。fmap 为 None 时退化为不做格式检查。"""
    def ok(lo, hi):
        return full.count(full[lo:hi]) == 1

    def ctx(lo, hi):
        return fmap is None or _ctx_ok(fmap, lo, hi, s, e)

    lo, hi = s, e
    # 历史经验：优先先吃 1 个右侧字符再判断唯一性——纯靠左侧上下文会让 new 变成 old 在同一
    # 起点的严格前缀，容易撞上 apply_patch._already_applied_replace 的“已应用”误判（见
    # _make_replace_text 里的第二道保险）；这一步同样要先过格式边界检查，不安全就不吃。
    if hi_bound > e and ctx(lo, hi + 1) and ok(lo, hi + 1):
        return lo, hi + 1
    if ok(lo, hi):
        return lo, hi
    guard = 0
    while not ok(lo, hi) and guard < 4000:
        moved = False
        if hi < hi_bound and ctx(lo, hi + 1):
            hi += 1
            moved = True
            if ok(lo, hi):
                return lo, hi
        if lo > lo_bound and ctx(lo - 1, hi):
            lo -= 1
            moved = True
            if ok(lo, hi):
                return lo, hi
        if not moved:
            break
        guard += 1
    return (lo, hi) if ok(lo, hi) else None


def _verify_no_stray_format_change(cand_id, el, old, new):
    """后置条件：在真实段落的一份深拷贝上真的跑一遍 apply_patch.apply_replace_text，逐字比对
    命中片段以外的格式有没有被动到——不把安全寄托在“体检事后抽查”上（verify_sweep_rule.json
    #1 的建议）。这是 _widen_unique 格式边界检查之外独立的第二道保险：哪怕前面的判断有疏漏，
    这里会真刀真枪跑一次并当场拦下，绝不放一条会悄悄改动未点名字符格式的 op 出去。"""
    spans_before = ap._run_spans(el)
    full_before = ''.join(t for _, t in spans_before)
    hits = ap._find_span(full_before, old)
    if len(hits) != 1:
        # old 理论上必然能在这里找到（它就是从这段原文切出来的）；真找不到就交给 apply_patch
        # 在真正 apply 时按它自己的口径处理，这里不越俎代庖、不额外中止。
        return
    start = hits[0]
    fmt_before = [ap._run_fmt(r) for r, t in spans_before for _ in t]
    el2 = copy.deepcopy(el)
    try:
        ap.apply_replace_text(el2, {'id': cand_id, 'old': old, 'new': new}, {})
    except ap.Abort as e:
        raise Abort(f'{cand_id}：后置校验发现这条 op 会被 apply_patch 自己拒绝（{e}），已中止，不生成它')
    fmt_after = [ap._run_fmt(r) for r, t in ap._run_spans(el2) for _ in t]
    for i in range(0, start):
        if fmt_before[i] != fmt_after[i]:
            raise Abort(f'{cand_id}：后置校验发现命中片段以外第 {i} 字的格式被改变'
                        f'（{fmt_before[i]} → {fmt_after[i]}），已中止，不生成这条 op')
    tail_before, tail_after = fmt_before[start + len(old):], fmt_after[start + len(new):]
    if len(tail_before) != len(tail_after):
        raise Abort(f'{cand_id}：后置校验发现改后段落长度与期望不符，已中止')
    for j, (fb, fa) in enumerate(zip(tail_before, tail_after)):
        if fb != fa:
            raise Abort(f'{cand_id}：后置校验发现命中片段之后第 {j} 字的格式被改变'
                        f'（{fb} → {fa}），已中止，不生成这条 op')


def _make_replace_text(cand_id, text, s, e, core_new, lo_bound, hi_bound, el):
    """算一条安全的 (old, new)：old 在段内唯一、不越过命中片段的格式边界、不会被 apply_patch
    的已应用探测误判，且真的在段落副本上跑过一遍、确认命中片段以外的格式零变化。做不到就
    Abort（整批中止），不留一条“看起来对、实际会悄悄改坏格式或被 apply_patch 拒绝”的 op。"""
    fmap = _para_fmt_map(el) if el is not None else None
    widened = _widen_unique(text, s, e, lo_bound, hi_bound, fmap)
    if widened is None:
        raise Abort(f'{cand_id}：命中片段在段内加上下文仍不能唯一定位（且不越过原有格式边界），'
                    f'需要整段 new_text（会坍缩该段格式，风险自负）')
    lo, hi = widened
    old, new = text[lo:hi], text[lo:s] + core_new + text[e:hi]
    guard = 0
    while ap._already_applied_replace(text, old, new) and guard < 200:
        # old 确实存在（这里的 old 就是从原文切出来的），会走到这一步说明 new 恰好等于 old
        # 在同一起点的一段截断——继续吃右侧上下文，让 new 不再是 old 的纯前缀；同样要过格式
        # 边界检查，不安全或不再唯一就直接中止，不允许绕过。
        if hi >= hi_bound or (fmap is not None and not _ctx_ok(fmap, lo, hi + 1, s, e)):
            raise Abort(f'{cand_id}：new 与 old 撞上 apply_patch 的已应用探测（new 是 old 在同一'
                        f'起点的前缀），且已经无法再安全扩右侧上下文，需要整段 new_text')
        hi += 1
        if text.count(text[lo:hi]) != 1:
            raise Abort(f'{cand_id}：为避开已应用误判而扩右侧上下文后锚点不再唯一，需要整段 new_text')
        old, new = text[lo:hi], text[lo:s] + core_new + text[e:hi]
        guard += 1
    if el is not None:
        _verify_no_stray_format_change(cand_id, el, old, new)
    return old, new


def _build_set_format_ops(text, cand, act, fmt_override, base_op, seq0):
    """set_format 规则的落地：不做上下文扩展消歧——widen 会把命中片段之外、本不该改格式的字
    也一起改了格式（set_format 语义就是“把 old 这段文字的格式改掉”，扩大 old 等于扩大改动范围，
    跟 replace_text 的“扩上下文只为定位、文字本身不变”完全不是一回事）。命中片段在段内不唯一
    时如实中止，请把规则写得更精确（加 zones/labels/parts 或收紧正则）。"""
    cand_id = cand['cand_id']
    if not isinstance(fmt_override, dict) or not fmt_override:
        raise Abort(f'{cand_id}：set_format 规则缺 format（规则 action.format 或决定里的 format 至少给一个）')
    ops = []
    for k, (s, e) in enumerate(cand['hit_spans']):
        old = text[s:e]
        if text.count(old) != 1:
            raise Abort(f'{cand_id}：set_format 不支持靠扩上下文消歧（那样会连带改到别处的格式）；'
                        f'命中片段 {old!r} 在段内出现 {text.count(old)} 次，请把规则改得更精确或手动处理')
        op = base_op(seq0 + k)
        op['op'], op['old'], op['format'] = 'set_format', old, dict(fmt_override)
        ops.append(op)
    return ops


def _build_ops(rule, cand, dec, seq0, paras, P):
    """一条决定可能拆成多条 op（命中 >1 处、走 per-hit replace_text/set_format 保格式时）；
    返回 op 列表（reject 或命中数为 0 时返回 []）。seq0 是下一条 op 该用的编号，调用方按返回
    长度自增。paras 是 cmd_to_patch 里已经过原稿重新核对的段落元素表（按段号索引），P 是
    bh.Prof(profile)，用于题面标签兜底判断（_looks_like_source_label）。"""
    cand_id = cand['cand_id']
    decision = dec.get('decision')
    if decision not in ('accept', 'reject', 'edit'):
        raise Abort(f'{cand_id}：decision 必须是 accept/reject/edit，得到 {decision!r}')
    if decision == 'reject':
        return []
    reason = (dec.get('reason') or '').strip()
    if not reason:
        raise Abort(f'{cand_id}：{decision} 必须给非空 reason')
    text = cand['text']
    act = rule.get('action') or {}
    act_type = act.get('type')

    # 题面兜底：不管 bh.walk（可能是没确认的草案配置）判的 zone 是什么，段首是题面类标签就
    # 一律要求决定显式给 source_zone（见 verify_sweep_rule.json #4）。
    if (cand.get('zone') in SOURCE_ZONES or _looks_like_source_label(text, P)) and not dec.get('source_zone'):
        raise Abort(f'{cand_id}：锚点落在题面区（区位或题面标签命中），决定必须显式给 source_zone'
                    f'（restore|approved_edit），否则整批中止')

    def anchor():
        a = {'text': text}
        if cand.get('style'):
            a['style'] = cand['style']
        if cand.get('prev_text'):
            a['prev'] = cand['prev_text'][-40:]
        if cand.get('block_title'):
            a['block'] = cand['block_title']
        a['index_hint'] = cand['_para_idx']
        return a

    def base_op(seq):
        o = OrderedDict([('id', f'S{seq:04d}'), ('anchor', anchor()), ('reason', reason)])
        if dec.get('evidence'):
            o['evidence'] = dec['evidence']
        if dec.get('source_zone'):
            o['source_zone'] = dec['source_zone']
        return o

    if act_type == 'set_format':
        fmt_override = dec.get('format') or act.get('format')
        return _build_set_format_ops(text, cand, act, fmt_override, base_op, seq0)

    hit_count = cand['hit_count']
    new_snippet = dec.get('new_snippet')
    new_snippets = dec.get('new_snippets')
    new_text = dec.get('new_text')
    is_replace_regex = act_type == 'replace_regex'
    arx = re.compile(act['pattern']) if is_replace_regex else None
    el = paras[cand['_para_idx']]

    if decision == 'accept' and act_type == 'model_rewrite':
        raise Abort(f'{cand_id}：model_rewrite 规则不能 accept，必须 edit 并给出新文本')

    def regex_core(s, e):
        """按整段重新匹配算替换片段，不是只在孤立子串上 re.sub——否则带前瞻/后顾/^$ 的正则会
        因为切片里没有上下文而失效，产出 old==new 的空操作（见 verify_sweep_rule.json #2：
        predicted_new_text 显示已替换，实际生成的 op 却是空操作，两者不一致）。"""
        m = None
        for cm in arx.finditer(text):
            if cm.start() == s and cm.end() == e:
                m = cm
                break
        if m is None:
            raise Abort(f'{cand_id}：match.regex 与 action.pattern 在整段上的命中位置对不上'
                        f'（候选记的是 {s}:{e}），本工具不能安全套用 replace_regex，请改用 model_rewrite '
                        f'或让两个正则一致')
        core = m.expand(act.get('repl', ''))
        if core == text[s:e]:
            raise Abort(f'{cand_id}：规则套用结果与命中片段原文相同（常见于前瞻/后顾/^$ 在切片里未生效），'
                        f'拒绝生成空操作；请检查 match.regex 与 action.pattern 是否一致、或改用 model_rewrite')
        return core

    if hit_count == 1:
        s, e = cand['hit_spans'][0]
        if new_text is not None and new_snippet is None and new_snippets is None:
            op = base_op(seq0)
            op['op'], op['old'], op['new'] = 'replace_paragraph', text, new_text
            return [op]
        core_new = new_snippet if new_snippet is not None else (new_snippets[0] if new_snippets else None)
        if core_new is None:
            if decision != 'accept':
                raise Abort(f'{cand_id}：edit 必须给 new_snippet 或 new_text 之一')
            core_new = regex_core(s, e)
        old, new = _make_replace_text(cand_id, text, s, e, core_new, 0, len(text), el)
        op = base_op(seq0)
        op['op'], op['old'], op['new'] = 'replace_text', old, new
        return [op]

    # hit_count > 1：优先 per-hit replace_text（保留其余 run 的格式，不坍缩整段）；
    # 只有决定明确给了整段 new_text 时才走 replace_paragraph（并因此坍缩格式，由决定者知情选用）。
    if new_text is not None and new_snippets is None and new_snippet is None:
        op = base_op(seq0)
        op['op'], op['old'], op['new'] = 'replace_paragraph', text, new_text
        return [op]
    if new_snippets is not None and len(new_snippets) != hit_count:
        raise Abort(f'{cand_id}：new_snippets 有 {len(new_snippets)} 条，须等于命中数 {hit_count}')
    spans = cand['hit_spans']
    ops = []
    for k, (s, e) in enumerate(spans):
        core_new = new_snippets[k] if new_snippets is not None else None
        if core_new is None:
            if decision != 'accept':
                raise Abort(f'{cand_id}：命中 {hit_count} 处，edit 须给 new_snippets（每处一条）或 new_text（整段）')
            core_new = regex_core(s, e)
        lo_bound = spans[k - 1][1] if k > 0 else 0
        hi_bound = spans[k + 1][0] if k + 1 < len(spans) else len(text)
        old, new = _make_replace_text(cand_id, text, s, e, core_new, lo_bound, hi_bound, el)
        op = base_op(seq0 + k)
        op['op'], op['old'], op['new'] = 'replace_text', old, new
        ops.append(op)
    return ops


def cmd_to_patch(args):
    cands_obj = json.loads(Path(args.cands).read_text(encoding='utf-8'))
    if cands_obj.get('schema') != SCHEMA_CANDS:
        raise Abort(f'候选文件 schema 不是 {SCHEMA_CANDS}')
    decisions = json.loads(Path(args.decisions).read_text(encoding='utf-8'))
    items_dec = decisions.get('items')
    if not isinstance(items_dec, dict):
        raise Abort('决定文件缺 items（对象，键是 cand_id）')
    approved_by = decisions.get('approved_by')
    if not approved_by:
        raise Abort('决定文件缺 approved_by')
    cands = cands_obj.get('candidates') or []
    cand_ids = {c['cand_id'] for c in cands}
    missing = [c['cand_id'] for c in cands if c['cand_id'] not in items_dec]
    if missing:
        raise Abort(f'决定缺条：{missing[:20]}{"…" if len(missing) > 20 else ""}（共 {len(missing)} 条未给决定）')
    # 决定文件里多出候选文件没有的 cand_id 不能静默忽略——要么是候选文件被换过，要么是决定
    # 文件手改错了 key，都值得整批中止让人核对（见 verify_sweep_rule.json 小问题）。
    unknown_keys = sorted(set(items_dec) - cand_ids)
    if unknown_keys:
        raise Abort(f'决定文件里有候选文件没有的 cand_id：{unknown_keys[:20]}'
                    f'{"…" if len(unknown_keys) > 20 else ""}')

    rule = args._rule_full

    prof = _load_prof(args.profile, args.docx, cands_obj.get('profile'))
    # 草案配置默认拒绝跨书落地：_needs_confirm 非空说明这份 profile 是 profile_probe.py 自动
    # 推断、还没人核对过的草案，区位/题块判定可能是错的（见 verify_sweep_rule.json #4：文化
    # 草案漏认题块，题面被当 outside 改掉）。真要用就显式 --allow-draft-profile；补丁里记一笔，
    # 方便主代理事后知道这批是在未确认的草案配置下生成的。
    draft_allowed = False
    if prof.get('_needs_confirm'):
        if not args.allow_draft_profile:
            raise Abort(f'{prof.get("title", prof.get("book_id"))} 的配置是未确认的草案'
                        f'（_needs_confirm 有 {len(prof["_needs_confirm"])} 项待人工确认），跨书推广默认拒绝'
                        f'在这份草案下生成补丁；确认无误后加 --allow-draft-profile 重跑')
        draft_allowed = True

    # 冻结册：这份补丁将来是要喂给 apply_patch.py apply 的，冻结册一律拒绝在这一步就生成补丁——
    # 不看 --profile 怎么说，总是对输入稿本身重新判断（与 apply_patch.cmd_apply 同口径）。
    try:
        real_prof = detect_profile(args.docx)
    except Exception:
        real_prof = None
    check_prof = real_prof if real_prof is not None else prof
    if check_prof.get('frozen'):
        print(f'拒绝写出：{check_prof.get("title", check_prof.get("book_id"))} 已冻结'
              f'（{check_prof.get("frozen_note", "")}）', file=sys.stderr)
        return 3

    # 候选段是否在 find 之后被改：docx 整体 SHA 与候选文件里记录的不一致就直接中止——
    # 本工具只产 replace_text/replace_paragraph/set_format，不增删段落，SHA 一致就意味着候选
    # 记录的段号仍然有效（下面仍会逐条重新核对文字/命中片段，不直接采信）。
    d = dl.open_docx(args.docx, expect_sha256=cands_obj.get('docx_sha256'))
    P = bh.Prof(prof)

    # 不直接采信候选文件里的 text/hit_spans/para：在原稿上重新跑一遍同一条规则，逐条核对每个
    # cand_id 的文字/命中片段/区位是否与重新算出来的一致——候选文件被篡改（改 hit_spans、改
    # para 指到别的段、伪造 cand_id）时这里会发现并中止，段号一律采用这次重新核算的结果，不
    # 相信候选文件自己写的 para（见 verify_sweep_rule.json 小问题①）。
    fresh_by_id = {}
    for it, spans, ex, predicted in _iter_candidates(d.items, P, rule, args._rule_match_rx, paras=d.paras):
        fresh_by_id[f"{rule.get('id', 'R')}-{it['i']:06d}"] = it, spans
    bad = []
    for c in cands:
        fresh = fresh_by_id.get(c['cand_id'])
        if fresh is None:
            bad.append(f'{c["cand_id"]}：规则在原稿上重跑后找不到这条候选了')
            continue
        fit, fspans = fresh
        if fit['text'] != c['text'] or fspans != list(c.get('hit_spans') or []) or fit.get('zone') != c.get('zone'):
            bad.append(f'{c["cand_id"]}：候选的 text/hit_spans/zone 与在原稿上重新核算的结果不一致')
        else:
            c['_para_idx'] = fit['i']
    if bad:
        raise Abort('候选文件与原稿核对不一致，可能被篡改或规则/配置变了：' + '；'.join(bad[:10])
                    + ('…' if len(bad) > 10 else ''))

    ops = []
    for c in cands:
        dec = items_dec[c['cand_id']]
        new_ops = _build_ops(rule, c, dec, len(ops) + 1, d.paras, P)
        ops.extend(new_ops)

    patch = OrderedDict([
        ('schema', SCHEMA_PATCH), ('book', prof.get('book_id')), ('parent_docx_sha256', d.sha256),
        ('approved_by', approved_by), ('approval_ref', decisions.get('approval_ref') or f'sweep_rule:{rule["id"]}'),
        ('ops', ops),
    ])
    if draft_allowed:
        patch['draft_profile_allowed'] = True
    if ops:
        # 复用 apply_patch 自己的校验——锚点唯一、题面区必须显式 source_zone、新文字过禁用词表、
        # 同段冲突……本工具不重复实现，也不允许绕过；这里失败就是整批中止，不留 patch.json。
        ap.check_ops(d, prof, patch)

    if args.out:
        out = dl.guard_write(args.out, prof, inputs=[args.docx, args.cands, args.decisions], kind='.json',
                              overwrite=args.overwrite)
        out.write_text(json.dumps(patch, ensure_ascii=False, indent=1), encoding='utf-8')
    else:
        print(json.dumps(patch, ensure_ascii=False, indent=1))
    print(json.dumps({'ops': len(ops), 'candidates': len(cands)}, ensure_ascii=False))
    return 0 if ops else 1


# ------------------------------------------------------------------ CLI
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--debug', action='store_true')
    sub = p.add_subparsers(dest='command', required=True)

    c1 = sub.add_parser('find')
    c1.add_argument('--docx', required=True)
    c1.add_argument('--rule', required=True)
    c1.add_argument('--profile')
    c1.add_argument('--out')
    c1.add_argument('--overwrite', action='store_true')

    c2 = sub.add_parser('pack')
    c2.add_argument('--cands', required=True)
    c2.add_argument('--per-batch', type=int, default=20)
    c2.add_argument('--out', required=True)
    c2.add_argument('--overwrite', action='store_true')

    c3 = sub.add_parser('to-patch')
    c3.add_argument('--docx', required=True)
    c3.add_argument('--cands', required=True)
    c3.add_argument('--decisions', required=True)
    c3.add_argument('--rule', required=True)
    c3.add_argument('--profile')
    c3.add_argument('--out')
    c3.add_argument('--overwrite', action='store_true')
    c3.add_argument('--allow-draft-profile', action='store_true',
                     help='书册配置是未确认的草案（_needs_confirm 非空）时默认拒绝生成补丁，显式给这个开关才放行')

    c4 = sub.add_parser('verify')
    c4.add_argument('--docx', required=True)
    c4.add_argument('--rule', required=True)
    c4.add_argument('--profile')
    c4.add_argument('--decisions')
    c4.add_argument('--out')
    c4.add_argument('--overwrite', action='store_true')

    args = p.parse_args(argv)
    try:
        if args.command == 'find':
            return cmd_find(args)
        if args.command == 'pack':
            return cmd_pack(args)
        if args.command == 'to-patch':
            # to-patch 需要完整规则（match/exclude/action）才能在原稿上重新核对候选、给
            # accept 决定算默认新文本（replace_regex/set_format）；model_rewrite 规则每条
            # 都必须 edit 显式给新文本，accept 直接中止。
            r, match_rx = _load_rule(args.rule)
            if cands_rule_id_mismatch(args.cands, r):
                raise Abort('候选文件的 rule_id 与 --rule 给的规则 id 不一致，像是拿错了规则文件')
            args._rule_full = r
            args._rule_match_rx = match_rx
            return cmd_to_patch(args)
        if args.command == 'verify':
            return cmd_verify(args)
    except dl.GuardError as e:
        print('拒绝写出：' + str(e), file=sys.stderr)
        return 3
    except dl.ParentMismatch as e:
        print('候选段所在书稿在 find 之后已变化（父稿不符）：' + str(e), file=sys.stderr)
        return 2
    except (dl.AlignmentError, Abort, ap.Abort, ValueError, KeyError, FileNotFoundError) as e:
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
