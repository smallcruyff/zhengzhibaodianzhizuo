#!/usr/bin/env python3
"""A1/A2 单练的抽取、核对、生成——写书侧通用工具之一（流程优化线 2026-09-24，返修版）。

用途
    把"抽取单练条目→核对结构与准入→按批准结果重排/生成单练区"这三步机械活，从各册各自的一次性脚本
    收拢成一个按 profiles/<book>.json 的 drill.* 配置运行的通用工具。判定（认条目、认正误、认颜色、
    与体检门的口径）一律复用 batch_health（bh.collect_drill / bh.check_drill / bh.walk / bh.Prof），本
    工具只负责：①把 bh 认出的条目落成人可读、可编辑、可回填的 items.json（原文，不做 norm）；②在 bh
    的体检门之外补几条 bh 没做的检查（题源是否为空、序号连续、A1/A2 题干逐字一致、分组标签格式、可选
    的显式准入核对）；③按批准后的 items.json 重新生成 A1/A2 区域的表格行（写路径，逐行"未改动则原样
    保留"）。支持 drill.layout：
      - table3   （三列表：题肢｜判断｜题源；必修二 bixiu2、必修三 bixiu3 都是这个版式，已有正式配置）
      - paragraph（段落对：条目段 + 其后的"纠正："段；哲学、选必一等，目前无正式配置，仅 extract/check
                   可跑，build 未实现——见下方"已知不做的事"）
      - card     （整题题卡，A2 带【解析】；选必二、推理等，2026-09-24 第三批新增；也接受草案配置里
                   profile_probe 猜出来的 'cards' 复数写法）——bh.collect_drill 没有为 card 单独分支，
                   extract/check 完全在本工具内实现（见 _collect_cards 等函数说明），缺必要配置（如
                   drill.part）时如实报告缺哪些字段并以非零退出，不伪造识别结果；build 仍未实现，同样
                   如实拒绝并列出所需字段（见"已知不做的事"）。

用法
    drill_tool.py extract --docx X.docx --out items.json [--profile bixiu3] [--report r.json]
    drill_tool.py check   --docx X.docx [--admission decisions.json [--admission-mode decision|execution]] \
                          [--profile bixiu3] [--report r.json]
      admission-mode: decision（默认，核决策文件完整/格式对，在父稿上跑）｜execution（核决策是否已被正确执行，在候选稿上用题干哈希这种稳定 id 核对，不用位置性 group:no）。
    drill_tool.py build   --docx 父稿.docx --items approved.json --out 候选.docx \
                          [--profile bixiu3] [--expect-sha 父稿SHA] [--allow-rebase] \
                          [--order as-given|alternate] [--seed N] [--report r.json]

读写承诺
    - extract：只读父稿；--out 写 items.json，过 guard_json（本质是 docx_lib.guard_write(kind='.json')，
      只放行系统临时目录 / 受保护根下的 …/协作/候选/<谁>/<批次>/构建/，冻结册目录一律拒绝——包括冻结册
      自身工作区、审阅入口等，也包括受保护根、Skill scripts/、项目根这些不该新建 json 的地方）。
    - check：只读父稿与可选的 --admission 决策文件；--report 同样过 guard_json。
    - build：只读父稿与 --items；--out 写 .docx，写出前过 docx_lib.guard_write（冻结册在这里真正拒绝，
      退出码 3）；只改 word/document.xml，其余 ZIP 成员逐字节照抄，写后重开核对；写后对新文档重跑
      bh.check_drill，只要比父稿新增 FAIL 就整批中止、不留输出文件。任何一条校验失败（含 --report 路径
      不合规）都在写出主输出之前拦下；如果写报告失败，回滚已写出的主输出。
    - 不改 batch_health.py / docx_lib.py / profile_lib.py / profiles/ 下任何文件；不运行 collab.py；
      不启子进程写文件；不联网。

退出码
    0 成功 / 无待办（check：0 条发现；build：写出且写后体检未比父稿新增 FAIL）；
    1 check 模式发现待处理（任何 FAIL/WARN/CANDIDATE，含 --admission 校验失败）；extract 遇到
      a1/a2 条数不一致时也用 1（items.json 仍然写出，供人核对，但明确"没抽全"）；
    2 输入或配置错误、结构中止（父稿 SHA 不符、items.json 格式错、锚点/分组对不上、非条目行未处理、
      写后体检比父稿新增 FAIL 等，均不留输出文件）；
    3 拒绝写出（guard_write/guard_json 守卫、冻结册、写权、输出与输入同一文件）。
    异常一律转中文错误信息打印到 stderr 并按上述退出码返回；--debug 打开原始 traceback。

items.json 格式（extract 的输出 = build/check --admission 的输入，schema: baodian_drill_items_v1）
{
  "schema": "baodian_drill_items_v1", "book": "bixiu3", "layout": "table3",
  "source_docx": "...", "source_sha256": "...", "count": N, "a1_count": N, "a2_count": N,
  "a1_a2_count_mismatch": false, "non_item_rows": 0,
  "records": [
    {"no": "12", "group": 328,
     "stem": "题干正文原文（不含"纠正："，未做 norm，空白按原稿保留）",
     "verdict": "正确" | "错误",
     "error_runs": [{"text": "...", "start": 3, "end": 9}, ...],  // 相对 stem 的字符偏移，先后顺序
     "correction": "纠正：……"（原文） 或 null,
     "note": null 或段落式版式里紧跟的非"纠正："附注文字,
     "source": "题源"（原文；table3 才有，paragraph 版式恒为空字符串）,
     "a1": {"table": 308, "row": 10, "text": "原 A1 单元格全文", "answer": "（　）"} 或 null（a1/a2 条数
           不一致时缺的一侧填 null）,
     "a2": {"table": 328, "row": 10, "text": "原 A2 单元格全文"}
    }, ...
  ]
}
card 版式（整题题卡，粒度是一张卡一条记录，见 _extract_card）另外还有：
    "answer": "答案标签之后、解析标签之前的原文，已 strip" 或 null,
    "answer_raw": "答案标签之后未截断的原文（可能含解析全文），已 strip" 或 null（修复 minor：原先
                  answer 字段直接把这段未截断原文塞进去，混了解析文字，下游容易误用；answer 现在只取
                  解析标签之前的部分，answer_raw 保留原样供确需原文的下游自己再截）,
    "has_analysis": true | false,
build 用得到 group/stem/verdict/error_runs/correction/source；a1/a2/no 除了供人核对，还用来判断"这条与
父稿现在这个位置的内容是否完全一致"——完全一致的记录，原样复制父稿里的那两行 XML（不经任何模板），
只有新增或改过的记录才用"同组相邻行"的 XML 当模板重新生成，模板的序号分隔符与 pPr 都取自那个模板行
本身（不是全书第一条）。

已知不做的事（写进回执 known_limits，不在这里静默处理）
    - build 目前只支持 drill.layout == 'table3'；paragraph 是功能未实现（非配置缺失），报错信息列出所需
      配置字段（item_styles/correction_styles/group_label_regex 或 group_style/paragraph_verdict_regex），
      留给下一轮或人工，已列入 needs_user_decision；card 版式（2026-09-24 起）extract/check 已实现，
      build 仍未实现，报错信息列出所需配置字段（见 _CARD_BUILD_NEEDED_FIELDS）。
    - card 版式的 check 不支持 --admission（功能未实现，不是配置缺失），显式 Abort(2)。
    - card 版式"答案字母合法"只核字符集合（drill.card.answer_alphabet_regex，默认 A-D 与circled 数字
      ①-⑩），不核该字母是否真的对应正确题肢——那是教学判断，规格"不做教学判断"条明确排除。
    - card 版式"A1/A2 题干一致"只在 A2 侧确有复述文字时才比较（见 _card_scan：A2 没有复述题干的卡，如
      选必二绝大多数条目，只核题源与编号配对，不核题干字面——因为那些卡在 A2 侧本来就不重复印一遍题
      干，没有可比对象，不是工具漏检）。**这类书 check 无法核出"A1 题干本身有没有被悄悄改过"，只能核
      "A1 卡至少有非空的题干/选项内容"这条底线（缺内容会报"A1 题卡正文为空或没有题干/选项内容"）；只有
      A2 确有复述（如推理 v7.50）时，题干被改才会被"A2 复述内容在 A1 找不到"这条抓到。**
    - card 版式的 check 不经 batch_health 的单练体检门：batch_health 对 card 版式完全不核内容，配置了
      单练但认不出 table3/paragraph 结构时只报一条 WARN（"配置了单练，文中没有找到单练部分"），不会报
      这里报的任何 FAIL。**card 版式的单练必须单独跑 drill_tool check，只看体检结论会误以为没问题**
      （check 的 summary 里也带了 bh_health_note 这条提醒，终端输出与 --report 都能看到）。
    - build 只有"内容真正新增/改动"的行才用模板重新生成；只是插入/删除条目导致重新编号、内容没变的行，
      走"原样复制原 tr、只替换开头序号文字"，原有分隔符/pPr/rPr/纠正段落结构（含同段模板）都不受影响。
    - build 的 --order alternate 只是启发式交替，不保证 alternation.max_same_run_per_table 这个阈值
      （该阈值本来就只是 WARN 级提示值，不是用户原话的硬指标）。
    - "对照正文核对被选题肢应为正确"（规格 check 一节里的"可选对照正文"）未实现：工程量接近
      batch_health.diff_source 一整套，超出本工具"薄封装"的定位，留给主代理按需扩展。
    - --admission 的 input_sha256 核对：drill_tool 在内存里现抽候选，不落候选文件，因此把 decisions
      里的 input_sha256（如果有）与 --docx 的 sha256 比对，而不是与某个候选文件的字节 sha256 比对
      （check_drill_admission.main() 单独跑时比对的是候选文件字节）。两种用法的"input"含义不同，这里
      按"决策是针对哪一版书稿做的"来解释，如果与准入台账的真实口径不同，见 needs_user_decision。
"""
import argparse
import copy
import hashlib
import itertools
import json
import random
import re
import sys
import time
import traceback
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_health as bh  # noqa: E402
import check_drill_admission as cda  # noqa: E402
import docx_lib as dl  # noqa: E402
from profile_lib import detect_profile, load_profile, list_profiles  # noqa: E402

from lxml import etree  # noqa: E402

TOOL_VERSION = '1.3.0'  # 2026-09-24 返修：见 verify_drill_card.json / fix_drill_card.json（major 1-3 + minor）
W = bh.W
MC = bh.MC
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'


class Abort(Exception):
    def __init__(self, code, msg):
        super().__init__(msg)
        self.code = code


def say(msg):
    print(msg, file=sys.stderr)


# ------------------------------------------------------------------ 书册配置
def get_profile_readonly(args):
    """extract/check 用：只读，不强求路径能被 detect_profile 认出（草案配置、临时目录副本都要能跑）。"""
    if args.profile:
        return load_profile(args.profile)
    pd = detect_profile(args.docx)
    if pd is None:
        raise Abort(2, '无法按路径判断书册，请用 --profile 指定（可选：%s）' % '、'.join(list_profiles()))
    return pd


def get_profile_strict(args):
    """build 用：始终用 detect_profile 反查 --docx 实际属于哪本书，命中冻结册就拒绝，与 --profile 无关
    （与 apply_patch.py / layout_prepare.py 同一套写路径判定，避免声明 --profile 绕过冻结册守卫）。"""
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


# ------------------------------------------------------------------ 报告 / items.json 输出守卫
# 修复 blocker 1：不再自己维护一份"只查冻结册目录"的守卫，改成套 docx_lib.guard_write 本尊（kind='.json'），
# 这样受保护根（项目根、~/GaokaoPolitics、~/Desktop、Skill 目录……都来自 profiles/_house.json 经
# load_profile() 合并进每份 profile 的 output_guard.protected_roots）与冻结册目录的口径与
# apply_patch/layout_prepare 等其他写工具完全一致。只把传进去的 profile 拷贝一份、强制 frozen=False 再
# 传给 guard_write——这是与"整份 guard_write 对 frozen 一律拒绝任何输出"唯一的差异：json 输出不因"这本书
# 冻结"本身被拦，冻结册的目录仍然由 guard_write 内部按位置判断的 _frozen_hits() 挡（不管传进去的 prof
# 是不是冻结，_frozen_hits 都会重新查一遍全部 profiles 的冻结登记）。传 None 会漏掉 _house.json 里那些
# 通用受保护根（因为 cfg(prof,...) 需要一个真的 profile 对象才能读到合并后的 output_guard），所以这里
# 一定要传 profile 副本，不能像最初那版一样图省事传 None。
def _is_own_json(p, tool='drill_tool', purpose='out', mode=None):
    """purpose='out'：只认自己产出的 items.json；purpose='report'：只认 tool.name+mode 都匹配的报告，
    items.json 判定为"不是这份报告"不给覆盖——防止 --report 悄悄冲掉已批准的 approved.json（修复 major 7）。"""
    try:
        j = json.loads(Path(p).read_text(encoding='utf-8'))
    except (ValueError, OSError):
        return False
    if not isinstance(j, dict):
        return False
    if purpose == 'report':
        t = j.get('tool')
        return isinstance(t, dict) and t.get('name') == tool and (mode is None or j.get('mode') == mode)
    # purpose == 'out'：extract --out 只允许覆盖本工具自己产出的 items.json。
    return j.get('schema') == 'baodian_drill_items_v1'


def guard_json(out_path, pd, inputs, tool='drill_tool', purpose='out', mode=None):
    out = Path(out_path).expanduser().resolve()
    overwrite = out.exists() and _is_own_json(out, tool, purpose=purpose, mode=mode)
    pd2 = dict(pd) if pd else None
    if pd2 is not None:
        pd2['frozen'] = False
    try:
        return dl.guard_write(out, pd2, inputs=inputs, kind='.json', overwrite=overwrite)
    except dl.GuardError as e:
        # GuardError 一律是"守卫"性质的拒绝，按规格一·6 统一算 3，不再按消息文字分流到 2（修复 minor）。
        raise Abort(3, str(e))


def write_json(out, payload):
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name('.' + out.name + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
    import os
    os.replace(str(tmp), str(out))


# ------------------------------------------------------------------ bh 没暴露的薄封装：单元格 run 级颜色切分
def _row_cell_runs(items, tbl, row, col):
    """某个 (表格, 行, 列) 单元格按文档顺序拼起来的 run 列表（bh.collect_drill 只聚合了颜色布尔值，
    这里要拿具体哪几个子串是红/绿的，得回到 items 自己重新聚合——与 collect_drill 的聚合口径一致，
    只是多留了 run 边界，故意不复用它内部的 defaultdict，避免动它的返回结构。"""
    runs = []
    for it in items:
        if it['tbl'] == tbl and it['row'] == row and it['col'] == col:
            runs.extend(it['runs'])
    return runs


def _cell_raw_text(items, tbl, row, col):
    return ''.join(t for t, _ in _row_cell_runs(items, tbl, row, col))


def _colored_segments_with_offsets(runs, color, base_abs, span_start, span_end):
    """runs 是某单元格全文（题干+纠正）按顺序拼出的 (text,color) 列表；只取 [span_start,span_end)
    （单元格内绝对偏移）范围内颜色为 color 的子串，返回相对 span_start 的 {text,start,end}（修复
    major 4：build 按偏移上色，不再靠 str.find() 猜第一次出现处）。"""
    out = []
    pos = base_abs
    for t, c in runs:
        seg_s, seg_e = pos, pos + len(t)
        pos = seg_e
        if seg_e <= span_start or seg_s >= span_end or not t:
            continue
        s = max(seg_s, span_start)
        e = min(seg_e, span_end)
        if c == color and e > s:
            out.append({'text': t[s - seg_s:e - seg_s], 'start': s - span_start, 'end': e - span_start})
    return out


def _default_run_color(runs, exclude_colors):
    for t, c in runs:
        if c not in exclude_colors:
            return c
    return runs[0][1] if runs else '000000'


# ------------------------------------------------------------------ 非条目行（修复 major 5：build 不许悄悄删表头/小标题）
def _non_item_rows_table3(items, tbl_ids, c):
    item_rx = re.compile(c.get('item_regex') or r'^(\d+)[、.．]\s*(.*)$', re.S)
    sc = c.get('stem_col', 0)
    ncols = c.get('columns', 3)
    rows = {}
    order = []
    for it in items:
        if it['zone'] != 'drill' or it['tbl'] not in tbl_ids:
            continue
        key = (it['tbl'], it['row'])
        if key not in rows:
            rows[key] = {}
            order.append(key)
        rows[key][it['col']] = rows[key].get(it['col'], '') + it['text']
    bad = []
    for key in order:
        cells = rows[key]
        stem = cells.get(sc, '')
        if len(cells) != ncols or not item_rx.match(stem):
            bad.append({'table': key[0], 'row': key[1], 'text': bh.clip(stem, 40)})
    return bad


# ------------------------------------------------------------------ extract
def _extract_table3(items, P, c):
    """修复 major 3：字段一律取单元格原文（只去掉序号前缀），不经 bh.norm——bh.collect_drill 里的
    stem/src/ans 是给"判定"用的规整口径，落进 items.json 给人回填/给 build 写回，必须是原文，否则半角
    空格、制表符这些会被悄悄删掉。修复 major 4：error_runs 记偏移，不只记子串。"""
    marker = c.get('correction_marker', '纠正：')
    err_c = (c.get('colors', {}) or {}).get('error_run', 'C00000').upper()
    sc, ac, rc = c.get('stem_col', 0), c.get('answer_col', 1), c.get('source_col', 2)
    item_rx = re.compile(c.get('item_regex') or r'^(\d+)[、.．]\s*(.*)$', re.S)
    D = bh.collect_drill(items, P)
    A1 = [x for x in D['recs'] if x['sec'] == 'A1']
    A2 = [x for x in D['recs'] if x['sec'] != 'A1']
    mismatch = len(A1) != len(A2)
    pairs = list(itertools.zip_longest(A1, A2)) if mismatch else list(zip(A1, A2))
    recs = []
    for x, y in pairs:
        if y is None:
            continue  # A1 多出来的尾巴：extract 以 A2 为准全量输出，A1 单独多出的一条无处安放，计入 mismatch 由调用方报告
        it = y['it']
        stem_runs = _row_cell_runs(items, it['tbl'], it['row'], sc)
        raw_cell = ''.join(t for t, _ in stem_runs)
        m = item_rx.match(raw_cell)
        no = m.group(1) if m else y['no']
        body_start = m.start(2) if m else 0
        raw_body = m.group(2) if m else raw_cell
        marker_at = raw_body.find(marker)
        if marker_at >= 0:
            stem_raw = raw_body[:marker_at]
            correction = raw_body[marker_at:]
            stem_span_end = body_start + marker_at
        else:
            stem_raw = raw_body
            correction = None
            stem_span_end = body_start + len(raw_body)
        error_runs = _colored_segments_with_offsets(stem_runs, err_c, 0, body_start, stem_span_end)
        raw_source = _cell_raw_text(items, it['tbl'], it['row'], rc)
        a1_dict = None
        if x is not None:
            a1_dict = {'table': x['it']['tbl'], 'row': x['it']['row'], 'text': x['text'], 'answer': x['ans']}
        rec = {
            'no': no, 'group': it['tbl'],
            'stem': stem_raw, 'verdict': y['ans'],
            'error_runs': error_runs, 'correction': correction, 'note': None,
            'source': raw_source,
            'a1': a1_dict,
            'a2': {'table': it['tbl'], 'row': it['row'], 'text': y['text']},
        }
        recs.append(rec)
    return recs, D, len(A1), len(A2), mismatch


def _extract_paragraph(items, P, c):
    marker = c.get('correction_marker', '纠正：')
    err_c = (c.get('colors', {}) or {}).get('error_run', 'C00000').upper()
    D = bh.collect_drill(items, P)
    A1 = [x for x in D['recs'] if x['sec'] == 'A1']
    A2 = [x for x in D['recs'] if x['sec'] != 'A1']
    mismatch = len(A1) != len(A2)
    pairs = list(itertools.zip_longest(A1, A2)) if mismatch else list(zip(A1, A2))
    recs = []
    for x, y in pairs:
        if y is None:
            continue
        it = y['it']
        runs = it.get('runs', [])
        raw_text = ''.join(t for t, _ in runs)
        marker_at = raw_text.find(marker)
        if marker_at >= 0:
            stem_raw = raw_text[:marker_at]
        else:
            stem_raw = raw_text
        error_runs = _colored_segments_with_offsets(runs, err_c, 0, 0, len(stem_raw))
        correction = None
        corr_it = y.get('corr_it')
        if corr_it is not None:
            correction = corr_it['text']
        elif marker_at >= 0:
            correction = raw_text[marker_at:]
        note = None
        if y.get('notes'):
            note = y['notes'][0]['text']
        grp = y['tbl'][2] if isinstance(y['tbl'], tuple) and len(y['tbl']) > 2 else None
        a1_dict = None
        if x is not None:
            a1_dict = {'table': None, 'row': None, 'para_i': x['it']['i'], 'text': x['text']}
        rec = {
            'no': y['no'], 'group': grp,
            'stem': stem_raw, 'verdict': y['ans'],
            'error_runs': error_runs, 'correction': correction, 'note': note,
            'source': '',
            'a1': a1_dict,
            'a2': {'table': None, 'row': None, 'para_i': it['i'], 'text': y['text']},
        }
        recs.append(rec)
    return recs, D, len(A1), len(A2), mismatch


# ------------------------------------------------------------------ card（题卡式单练：选必二、推理等；
# 流程优化线 2026-09-24 第三批新增。bh.collect_drill 对 layout=='card' 没有专门分支——传别的 layout 值
# 进去只会退化成 paragraph 逻辑，按 item_regex 认段落，题卡文本认不出任何条目，只会产生一堆 other，
# 所以 card 的识别完全在本工具内实现（"薄封装"，不动 bh），只借用 bh.walk() 已经打好的 it['part']
# （由 structure.parts[].match 打标，与该 part 是否配了 "drill": true 无关，因此选必二/推理这种"A1/A2
# 各自是一个独立顶层部分"的写法不需要额外改 bh）。
#   识别口径（按选必二 r22、推理 v7.50 两本书的实际写法总结，两本书都用 drill.part 里第一个/第二个部
#   分分别装 A1/A2，卡与卡之间用一条"A1-数字 分隔符 题源"或"A2-数字 分隔符 题源"的标题段落分界，分隔
#   符选必二是"｜"、推理是空格——默认正则两种都认）：
#     drill.part                       ：题卡所在的两个部分 id（复用 table3/paragraph 也在用的字段，
#                                         哪个是 A1/哪个是 A2 不看数组顺序，看标题里 A1-/A2- 前缀本身）
#     drill.card.title_regex           ：题卡标题正则，默认 r'^(A[12])-(\d+)[｜\s]+(.*)$'
#     drill.card.stem_label            ：题干重述标签，默认 '【题目】'（A2 卡如果整段没有这行，说明这
#                                         张卡在 A2 侧不重述题干，check 的"题干一致"对这张卡自动跳过）
#     drill.card.answer_label          ：答案标签，默认 '【答案】'
#     drill.card.analysis_labels       ：解析标签（列表，命中其一即算有解析），默认 ['【解析】','【逐项解析】']
#     drill.card.a1_forbidden_labels   ：A1 卡不该出现的标签（列表），默认含带方括号的答案/解析/错肢
#                                         分析标签＋drill.correction_marker＋修复 minor 后新增的几种无
#                                         方括号写法（'答案：''答案:''答案为''正确答案'）
#     drill.card.answer_alphabet_regex ：答案栏合法字符的单字符正则，默认 r'[A-D①②③④⑤⑥⑦⑧⑨⑩]'
#       （只到 D／⑩，五选项以上或用别的记号的书需要主代理按需登记，见回执 profile_fields_needed）；
#       "合法"改成两条都核：答案段至少有一个合法字符（缺字母），且答案段里所有看起来像选项记号的字符
#       （_CARD_OPTION_TOKEN_RX，拉丁字母/圈码数字的超集）都必须属于这个正则（混入非法字母），修复
#       major 2——原先只核前一条，'AE'这类合法非法混着写查不出来。
# 已知不做的事：build 仍未实现（见 _CARD_BUILD_NEEDED_FIELDS，抛 Abort(2) 并列出缺的字段，不伪造）；
# --admission 对 card 版式也未实现（同样明确拒绝，不是配置缺失，是功能缺失）；"对照正文核对答案字母是
# 否真的对应正确题肢"这类教学判断不做，答案字母合法只核字符集合，不核是否真的答对——这是形式核验，不
# 是替主代理判卷。
_CARD_TITLE_RX_DEFAULT = r'^(A[12])-(\d+)[｜\s]+(.*)$'
_CARD_STEM_LABEL_DEFAULT = '【题目】'
_CARD_ANSWER_LABEL_DEFAULT = '【答案】'
_CARD_ANALYSIS_LABELS_DEFAULT = ['【解析】', '【逐项解析】']
_CARD_A1_FORBIDDEN_DEFAULT = ['【答案】', '【解析】', '【逐项解析】', '【错肢分析】',
                              '答案：', '答案:', '答案为', '正确答案']
_CARD_ANSWER_ALPHABET_DEFAULT = r'[A-D①②③④⑤⑥⑦⑧⑨⑩]'
_CARD_MISSING_PART_FIELD = ('drill.part（题卡所在的两个部分 id，如 ["APPX1","APPX2"] 或 ["A1","A2"]；'
                             '顺序不影响识别，A1/A2 由题卡标题本身的前缀决定）')
_CARD_BUILD_NEEDED_FIELDS = [
    'drill.card.build_template（新增/改动题卡时用哪张现有卡的 XML 当模板，题卡结构比三列表复杂得多，'
    '不能像 table3 那样直接借同组相邻行）',
    'drill.card.id_format（重排后题卡编号怎么重新打印，如 "A1-%03d" 还是 "A1-%02d"，两本书两种位数）',
    'drill.card.rebuild_zones（卡内哪些子段落允许在 build 时重写，哪些必须原样保留，例如题卡里嵌的表格）',
]


def _norm_layout(layout):
    """profile_probe 生成的草案里写的是 'cards'（复数，见两本书 draft.json 的 drill.layout），00_规格.md
    六节登记的是 'card'（单数）；两个都认，不强行要求先改草案文件才能跑。"""
    return 'card' if layout in ('card', 'cards') else layout


def _card_cfg(c):
    """未显式配置的字段按选必二 r22、推理 v7.50 两本书的现状取默认值（规格"配置字段缺省值按两本书现状
    给"）；title_regex 默认同时兼容选必二"A1-001｜题源"（分隔符是｜）与推理"A1-01 题源"（分隔符是空格）
    两种真实写法。"""
    cc = c.get('card') or {}
    return {
        'parts': list(c.get('part') or cc.get('parts') or []),
        'title_regex': cc.get('title_regex') or _CARD_TITLE_RX_DEFAULT,
        'stem_label': cc.get('stem_label', _CARD_STEM_LABEL_DEFAULT),
        'answer_label': cc.get('answer_label') or _CARD_ANSWER_LABEL_DEFAULT,
        'analysis_labels': list(cc.get('analysis_labels') or _CARD_ANALYSIS_LABELS_DEFAULT),
        'a1_forbidden': list(cc.get('a1_forbidden_labels') or _CARD_A1_FORBIDDEN_DEFAULT),
        'answer_alphabet': cc.get('answer_alphabet_regex') or _CARD_ANSWER_ALPHABET_DEFAULT,
        'correction_marker': c.get('correction_marker', '纠正：'),
        # 推理 v7.50 里有的选项不叫"纠正："而是"提示：……原题给定答案为 X"（如 B 项"见提示"时），跟纠正
        # 段一样是附注、不是题干，默认把两种前缀都当"不算题干候选"处理；correction_marker 已经在这里面
        # 兜底一次，主代理登记时可通过 drill.card.note_prefixes 覆盖或追加别的书的写法。
        'note_prefixes': list(cc.get('note_prefixes') or [c.get('correction_marker', '纠正：'), '提示：']),
    }


def _collect_cards(items, c):
    """把 drill.part 指到的两个部分（只靠 bh.walk() 已经打好的 it['part']，与该 part 是否配置了
    "drill": true 无关）按 drill.card.title_regex 切成一张张题卡：匹配到标题正则的段落是卡的分界（同时
    给出 A1/A2、编号、题源），直到下一张卡标题（或离开这两个部分）之间的所有段落/表格单元格是这张卡的
    正文（原样保留顺序，含表格）。返回 (cards, cc, missing)；missing 非空时 cards 为 None，调用方据此
    Abort 并列出缺的字段，不伪造识别结果（修复"card 版式认不出任何条目"就地拒绝、不再往下走的老问题：
    现在只有真的缺配置才拒绝，配置够就真的抽）。"""
    cc = _card_cfg(c)
    parts = set(cc['parts'])
    if not parts:
        return None, cc, [_CARD_MISSING_PART_FIELD]
    title_rx = re.compile(cc['title_regex'])
    cards = {'A1': [], 'A2': []}
    cur = None
    cur_part = None
    for it in items:
        p = it.get('part')
        if p not in parts:
            if cur is not None:
                cards[cur['sec']].append(cur)
                cur = None
            cur_part = None
            continue
        if p != cur_part:
            # 修复 major 1：A1→A2（或反过来）换部分时，不管这两个部分是否都在 drill.part 里，都要先把
            # 上一张未收的卡收掉——否则 A2 部分开头的标题/导语段会在下一张卡标题出现前被当成上一张 A1 卡
            # 的正文，吞进最后一张 A1 卡（两本真实书都中招，见回执 verify_drill_card.json major 1）。
            if cur is not None:
                cards[cur['sec']].append(cur)
                cur = None
            cur_part = p
        m = title_rx.match(it['text']) if (it['tbl'] is None and it['text']) else None
        if m and m.group(1) in ('A1', 'A2'):
            if cur is not None:
                cards[cur['sec']].append(cur)
            cur = {'sec': m.group(1), 'no': m.group(2), 'source': m.group(3).strip(),
                   'title_i': it['i'], 'title_it': it, 'body': []}
            continue
        if cur is not None:
            cur['body'].append(it)
    if cur is not None:
        cards[cur['sec']].append(cur)
    if not cards['A1'] and not cards['A2']:
        return None, cc, ['drill.card.title_regex（当前 %r 在 drill.part=%r 指到的部分里一条都没匹配上，'
                           '不是默认正则不适用就是 drill.part 这两个部分 id 配错了）' % (cc['title_regex'], sorted(parts))]
    return cards, cc, []


def _card_scan(body, cc):
    """把一张卡的正文（段落+表格单元格，按文档顺序）扫一遍，取"题干候选"片段（stem_fragments：既不是
    stem_label 本身、也不含答案/解析/a1_forbidden 里任何标签、也不是纠正段的那些原文片段）、有没有出现
    答案标签、答案标签之后那段原文（供核答案字母，可能与解析共段，如选必二"【答案】 D。【解析】 ……"）、
    有没有出现任一解析标签。
    两本书的 A2 卡"题干候选"落法完全不同，都得靠这个过滤器而不是"取第一段到某标签为止"才对：选必二
    的【错肢分析】先于【答案】…【解析】出现，若只以"答案标签之前"为界，错肢分析的文字会被误当题干；
    推理的题干（含 A/B/C/D 或①②③④各选项）在【逐项解析】之后按选项原样散布、与"纠正："交替，若只取
    答案标签之前那一小段，会漏掉全部选项。两种都用"排除法"处理：不管段落在卡内什么位置，凡是命中
    stem_label/answer_label/analysis_labels/a1_forbidden/correction_marker 之一的，一律不算题干候选，
    其余原样按文档顺序收进 stem_fragments。check 用 stem_fragments 逐段核在 A1 里能不能找到（子串，见
    _check_card），不要求 A2 侧题干候选拼起来后与 A1 整体逐字相等——推理书的 A2 本来就只挑"需要纠正"
    的选项落地，正确选项常常整段不印（如 A2-02 只印①③、不印正确的②），这是书稿本身的编排约定，不是
    数据缺口，若按"拼起来跟 A1 逐字相等"判就会对着正常书稿全数假报 FAIL。"""
    answer_label = cc['answer_label']
    analysis_labels = cc['analysis_labels']
    stem_label = cc['stem_label']
    note_prefixes = [p for p in cc['note_prefixes'] if p]
    exclude_labels = set(cc['a1_forbidden']) | set(analysis_labels) | ({answer_label} if answer_label else set())
    pre, answer_line, has_analysis = [], None, False
    for it in body:
        t = it.get('text') or ''
        if not t:
            continue
        if answer_line is None and answer_label and answer_label in t:
            answer_line = t.split(answer_label, 1)[1]
        for al in analysis_labels:
            if al in t:
                has_analysis = True
        excluded = ((stem_label and t.strip() == stem_label) or any(lab and lab in t for lab in exclude_labels)
                    or any(t.startswith(p) for p in note_prefixes))
        if not excluded:
            pre.append(t)
    frags = [bh.norm(x) for x in pre if bh.norm(x)]
    return {'stem_text': bh.norm(''.join(pre)), 'stem_fragments': frags, 'has_answer': answer_line is not None,
            'answer_line': answer_line, 'has_analysis': has_analysis}


def _forbidden_hits(body, cc):
    labels = list(cc['a1_forbidden'])
    if cc['correction_marker'] and cc['correction_marker'] not in labels:
        labels.append(cc['correction_marker'])
    hits = []
    for it in body:
        t = it.get('text') or ''
        for lab in labels:
            if lab and lab in t and lab not in hits:
                hits.append(lab)
    return hits


def _no_sort_key(no):
    try:
        return (0, int(no))
    except (TypeError, ValueError):
        return (1, no)


def _card_answer_segment(answer_line, cc):
    """答案标签之后那段原文里，解析标签出现之前的部分（不含解析原文）。extract 的 answer 字段、check
    的"答案字母合法/非法"判断共用这一段，修复 minor：原先 extract 把解析标签之后的整段原文也当"答案"
    收进 items.json，下游（如对照正文核对被选题肢）容易把解析原文误当答案用。"""
    if not answer_line:
        return ''
    seg = answer_line
    cut = len(seg)
    for al in cc['analysis_labels']:
        p = seg.find(al)
        if p >= 0:
            cut = min(cut, p)
    return seg[:cut]


_CARD_OPTION_TOKEN_RX = re.compile(r'[A-Za-z①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]')


def _card_answer_tokens(answer_line, cc):
    """答案段（_card_answer_segment）里按 drill.card.answer_alphabet_regex 逐字符匹配到的合法答案字母；
    返回空列表＝没找到任何合法答案字母，check 据此判"缺合法答案字母"。"""
    return re.findall(cc['answer_alphabet'], _card_answer_segment(answer_line, cc))


def _card_answer_illegal_tokens(answer_line, cc):
    """修复 major 2：原先"答案字母合法"只要求答案段里至少有一个合法字符（见 _card_answer_tokens），非法
    字母（如选项越界的 E、答案栏里混进另一处的字母）只要跟合法字母混在一起就漏检（'AE'、'E错误；A正确'
    这类都能骗过去）。这里改成："答案段里所有看起来像选项记号的字符（拉丁字母或圈码数字，_CARD_OPTION_
    TOKEN_RX 这个候选集是 answer_alphabet_regex 的超集）逐一核对，只要有一个不属于 answer_alphabet_regex
    就算非法"；返回非法字符列表（去重，保留出现顺序），空列表＝没有非法字符。允许的中文连接词（"错误"
    "正确""原题答案"等）本来就不会被 _CARD_OPTION_TOKEN_RX 命中，天然被剥掉，不需要额外维护一张连接词
    表。"""
    seg = _card_answer_segment(answer_line, cc)
    alphabet_rx = re.compile(cc['answer_alphabet'])
    bad = []
    for ch in _CARD_OPTION_TOKEN_RX.findall(seg):
        if not alphabet_rx.fullmatch(ch) and ch not in bad:
            bad.append(ch)
    return bad


def _extract_card(items, c):
    """把 _collect_cards 认出的题卡整理成 items.json 的 records：一张卡一条记录（题卡本身就是最小可核
    对单位，不是逐题肢一条，粒度与 table3/paragraph 不同，在文件头 items.json 格式说明里另注）。no/
    source/count 以 A2 侧为准全量输出（与 table3/paragraph 口径一致：extract 不悄悄截断，缺的 A1 侧填
    null，交给 check 报"A1 缺失"）。返回 (recs, D, a1n, a2n, mismatch, missing)。"""
    cards, cc, missing = _collect_cards(items, c)
    if missing:
        return None, None, 0, 0, False, missing
    a1_by_no = {x['no']: x for x in cards['A1']}
    a2_sorted = sorted(cards['A2'], key=lambda x: _no_sort_key(x['no']))
    recs = []
    for a2 in a2_sorted:
        a1 = a1_by_no.get(a2['no'])
        a1_scan = _card_scan(a1['body'], cc) if a1 else None
        a2_scan = _card_scan(a2['body'], cc)
        stem = a1_scan['stem_text'] if (a1_scan and a1_scan['stem_text']) else a2_scan['stem_text']
        answer_seg = _card_answer_segment(a2_scan['answer_line'], cc).strip()
        recs.append({
            'no': a2['no'], 'group': None, 'stem': stem, 'verdict': None,
            'error_runs': [], 'correction': None, 'note': None, 'source': a2['source'],
            # 修复 minor：answer 只取解析标签之前的答案本身；answer_raw 保留标签之后未截断的原文（可能含
            # 解析全文），供需要原文的下游自行截取，不悄悄丢信息。
            'answer': answer_seg or None,
            'answer_raw': (a2_scan['answer_line'] or '').strip() or None,
            'has_analysis': a2_scan['has_analysis'],
            'a1': ({'table': None, 'row': None, 'para_i': a1['title_i'], 'text': a1_scan['stem_text'],
                    'source': a1['source']} if a1 else None),
            'a2': {'table': None, 'row': None, 'para_i': a2['title_i'], 'text': a2_scan['stem_text'] or None,
                   'source': a2['source']},
        })
    a1n, a2n = len(cards['A1']), len(cards['A2'])
    D = {'total': a1n + a2n, 'other': 0}
    return recs, D, a1n, a2n, a1n != a2n, []


def _check_card(items, c, F):
    """card 版式的 check：完全在 drill_tool 内实现，不经 bh.check_drill/bh.collect_drill——它们对
    layout=='card' 没有专门分支，会退化成 paragraph 逻辑（按 item_regex 认段落），对题卡文本只会产生
    大量"other"、报出的 FAIL 是误判而不是真实问题，所以这里整段跳过 bh 的单练门，只用这套 card 专用逻
    辑（已在文件头"已知不做的事"注明，不是疏漏）。至少核：A1/A2 张数相等、逐张题源与题干一致（题干只在
    A2 确有复述时才比，见 _card_scan 说明）、A1 不含答案与解析、A2 有答案与解析、答案字母合法。"""
    cards, cc, missing = _collect_cards(items, c)
    if missing:
        raise Abort(2, 'drill.layout 为 card 但缺少必要配置，认不出题卡：%s' % '；'.join(missing))
    a1_by_no, a2_by_no = {}, {}
    for x in cards['A1']:
        a1_by_no.setdefault(x['no'], []).append(x)
    for x in cards['A2']:
        a2_by_no.setdefault(x['no'], []).append(x)
    for no, lst in a1_by_no.items():
        if len(lst) > 1:
            F.add('drill_tool', 'FAIL', 'A1 题卡编号重复', lst[-1]['title_it'], no=no, count=len(lst))
    for no, lst in a2_by_no.items():
        if len(lst) > 1:
            F.add('drill_tool', 'FAIL', 'A2 题卡编号重复', lst[-1]['title_it'], no=no, count=len(lst))
    a1n, a2n = len(cards['A1']), len(cards['A2'])
    if a1n != a2n:
        F.add('drill_tool', 'FAIL', 'A1/A2 题卡张数不相等', None, a1_count=a1n, a2_count=a2n)
    a1_nos, a2_nos = set(a1_by_no), set(a2_by_no)
    missing_a1 = sorted(a2_nos - a1_nos, key=_no_sort_key)
    missing_a2 = sorted(a1_nos - a2_nos, key=_no_sort_key)
    if missing_a1:
        F.add('drill_tool', 'FAIL', 'A2 有但 A1 缺失的题卡编号', None, nos=missing_a1[:30])
    if missing_a2:
        F.add('drill_tool', 'FAIL', 'A1 有但 A2 缺失的题卡编号', None, nos=missing_a2[:30])
    # 修复 major 3：原先 A1 卡正文可以整段清空、check 不报——选必二这类 A2 不复述题干的书，"逐张题干一致"
    # 实际完全没核，唯一的底线是"A1 卡本身至少有题干/选项内容"。对全部 A1 卡（不止与 A2 配上号的）都查，
    # 缺失的一侧同样该报（missing_a2 里那些 A1 卡也可能正文是空的）。
    for no in sorted(a1_nos, key=_no_sort_key):
        a1x = a1_by_no[no][0]
        if not _card_scan(a1x['body'], cc)['stem_fragments']:
            F.add('drill_tool', 'FAIL', 'A1 题卡正文为空或没有题干/选项内容', a1x['title_it'], no=no)
    for no in sorted(a1_nos & a2_nos, key=_no_sort_key):
        a1, a2 = a1_by_no[no][0], a2_by_no[no][0]
        a1_scan, a2_scan = _card_scan(a1['body'], cc), _card_scan(a2['body'], cc)
        if bh.norm(a1['source']) != bh.norm(a2['source']):
            F.add('drill_tool', 'FAIL', 'A1/A2 题源不一致', a2['title_it'], no=no,
                  a1=bh.clip(a1['source'], 40), a2=bh.clip(a2['source'], 40))
        # 题干只在 A2 确有复述文字时才比；比的是"A2 复述的每一段，在 A1 里能不能找到"（子串），不是
        # "拼起来跟 A1 整体逐字相等"——见 _card_scan 说明：推理书的 A2 常只挑需纠正的选项落地，正确
        # 选项整段不印是书稿编排约定，不是数据缺口。
        a1_ref = a1_scan['stem_text']
        bad_frag = next((f for f in a2_scan['stem_fragments'] if f not in a1_ref), None)
        if bad_frag is not None:
            F.add('drill_tool', 'FAIL', 'A2 题干复述内容在 A1 找不到对应原文', a2['title_it'], no=no,
                  text=bh.clip(bad_frag, 60))
        hits = _forbidden_hits(a1['body'], cc)
        if hits:
            F.add('drill_tool', 'FAIL', 'A1 题卡混入答案/解析等不该出现的标签', a1['title_it'], no=no, labels=hits)
        if not a2_scan['has_answer']:
            F.add('drill_tool', 'FAIL', 'A2 题卡缺答案（未找到 %s）' % cc['answer_label'], a2['title_it'], no=no)
        else:
            if not _card_answer_tokens(a2_scan['answer_line'], cc):
                F.add('drill_tool', 'FAIL', '答案栏未找到合法答案字母（drill.card.answer_alphabet_regex）',
                      a2['title_it'], no=no, text=bh.clip(a2_scan['answer_line'] or '', 40))
            else:
                # 修复 major 2：原先只要答案段里有一个合法字符就放行，非法字母混在合法字母中间（如
                # 'AE'、'E错误；A正确'）查不出来；现在把答案段里所有像选项记号的字符都过一遍 answer_
                # alphabet_regex，混进任何一个不合法的都报。
                illegal = _card_answer_illegal_tokens(a2_scan['answer_line'], cc)
                if illegal:
                    F.add('drill_tool', 'FAIL', '答案栏混入不合法的答案字母（drill.card.answer_alphabet_regex）',
                          a2['title_it'], no=no, illegal=illegal, text=bh.clip(a2_scan['answer_line'] or '', 40))
        if not a2_scan['has_analysis']:
            F.add('drill_tool', 'FAIL', 'A2 题卡缺解析（未找到 %s）' % '/'.join(cc['analysis_labels']),
                  a2['title_it'], no=no)
    return {
        'layout': 'card', 'a1': a1n, 'a2': a2n, 'matched': len(a1_nos & a2_nos),
        'missing_in_a1': len(missing_a1), 'missing_in_a2': len(missing_a2),
        # 修复 major 4：batch_health 体检对 card 版式单练完全不核内容（草案配置下只会报一条 WARN"配置了
        # 单练，文中没有找到单练部分"），本工具这里报出的 FAIL 体检看不到。这条注记跟着 summary 一起进
        # check 的终端输出与 --report，让只看体检结论的人也能在 card 版式这条路上看到提醒，不必现在就去
        # 改 batch_health/profiles（本工具不改那两处）。
        'bh_health_note': ('batch_health 体检不核 card 版式单练内容，只会报一条“配置了单练，文中没有找到'
                            '单练部分”的 WARN；上面这些 FAIL/WARN/CANDIDATE 是本工具单独核出来的，card 版'
                            '式单练必须单独跑 drill_tool check，不能只看体检结论。'),
    }


def cmd_extract(args):
    pd = get_profile_readonly(args)
    P = bh.Prof(pd)
    items, _ = bh.read_docx(args.docx)
    bh.walk(items, P)
    c = pd.get('drill') or {}
    layout = _norm_layout(c.get('layout', 'table3'))
    non_item = []
    if layout == 'card':
        recs, D, a1n, a2n, mismatch, missing = _extract_card(items, c)
        if missing:
            raise Abort(2, 'drill.layout=%r（card）缺少必要配置，认不出题卡：%s' % (c.get('layout'), '；'.join(missing)))
    elif layout == 'table3':
        recs, D, a1n, a2n, mismatch = _extract_table3(items, P, c)
        # 修复 major 6：A1/A2 条数不同不再静默截断——extract 仍然把 A2 全量输出（缺的 A1 侧填 null），
        # 但退出码非零，让人在 build 之前就看到"没抽全"，而不是等 build 用截断后的 items 悄悄丢条目。
        tbl_ids = {r['group'] for r in recs} | {r['a1']['table'] for r in recs if r.get('a1')}
        non_item = _non_item_rows_table3(items, tbl_ids, c)
    else:
        recs, D, a1n, a2n, mismatch = _extract_paragraph(items, P, c)
        if layout != 'paragraph':
            say('提示：drill.layout=%r 不是 table3/card，也不是登记过的 paragraph；本工具按 paragraph 逻辑'
                '（bh.collect_drill 对未知 layout 走的同一分支）尝试抽取，结构未必认得对，见 report 里'
                'other_rows/count 的比例。' % layout)
        if not recs:
            raise Abort(2, 'drill.layout=%r 认不出任何条目（count=0）：既不是 table3/card，也没有登记过的 '
                        'paragraph 结构，paragraph 兜底逻辑也没认出来，需要人工确认版式或补配置后再跑。' % layout)

    payload = {
        'schema': 'baodian_drill_items_v1', 'tool': {'name': 'drill_tool', 'version': TOOL_VERSION},
        'book': pd.get('book_id'), 'layout': layout,
        'source_docx': str(Path(args.docx).resolve()), 'source_sha256': dl.sha256_file(args.docx),
        'count': len(recs), 'a1_count': a1n, 'a2_count': a2n,
        'rows_seen': D['total'], 'non_item_rows': D['other'], 'a1_a2_count_mismatch': mismatch,
        'non_item_row_details': non_item,
        'records': recs,
    }

    out = guard_json(args.out, pd, [args.docx], purpose='out')
    rep_out = None
    if args.report:
        rep_out = guard_json(args.report, pd, [args.docx, args.out], purpose='report', mode='extract')
    write_json(out, payload)
    rep = {'tool': {'name': 'drill_tool', 'cmd': 'extract', 'version': TOOL_VERSION}, 'mode': 'extract',
           'profile': pd.get('book_id'), 'inputs': [{'path': str(Path(args.docx).resolve()), 'sha256': payload['source_sha256']}],
           'out': str(out), 'layout': layout, 'count': len(recs), 'a1_count': a1n, 'a2_count': a2n,
           'rows_seen': D['total'], 'non_item_rows': D['other'], 'a1_a2_count_mismatch': mismatch,
           'non_item_row_details': non_item}
    if rep_out is not None:
        try:
            write_json(rep_out, rep)
        except Exception:
            try:
                out.unlink()
            except OSError:
                pass
            raise
    print(json.dumps({k: rep[k] for k in ('layout', 'count', 'a1_count', 'a2_count', 'rows_seen', 'non_item_rows',
                                           'a1_a2_count_mismatch')}, ensure_ascii=False))
    return 1 if mismatch else 0


# ------------------------------------------------------------------ check
def _check_seq_and_stems(A1, A2, F):
    """修复 major 8 之一二：序号连续（1..N，按 A2 出现顺序）、A1/A2 题干逐字一致（不只前 20 字）。"""
    nos = []
    for x in A2:
        try:
            nos.append(int(x['no']))
        except (TypeError, ValueError):
            F.add('drill_tool', 'FAIL', '条目编号不是数字', x['it'], no=x.get('no'))
            return
    expect = list(range(1, len(nos) + 1))
    if nos != expect:
        dup = sorted({n for n in nos if nos.count(n) > 1})
        missing = sorted(set(expect) - set(nos))
        extra = sorted(set(nos) - set(expect))
        F.add('drill_tool', 'FAIL', '条目编号不是 1..N 连续（跳号/重号）', None,
              dup=dup[:20], missing=missing[:20], extra=extra[:20], total=len(nos))
    mism = 0
    for x, y in zip(A1, A2):
        if bh.norm(x['stem']) != bh.norm(y['stem']):
            mism += 1
            if mism <= 20:
                F.add('drill_tool', 'FAIL', 'A1/A2 题干逐字不一致（第 20 字之后有差异）', y['it'],
                      a1=bh.clip(x['stem'], 60), a2=bh.clip(y['stem'], 60))
    if mism > 20:
        F.add('drill_tool', 'FAIL', 'A1/A2 题干逐字不一致（其余）', None, more=mism - 20)


def _check_group_labels(items, P, c, F):
    """修复 major 8 之三：分组标签格式——仅对配置了 group_label_regex 或段落式分组样式的书生效，其余
    书没有这类配置就什么都不查（不是每本书都有"分组标签"这个概念）。"""
    grp_rx_src = c.get('group_label_regex')
    if not grp_rx_src:
        return
    grp_rx = re.compile(grp_rx_src)
    group_styles = set(c.get('group_style') or []) if isinstance(c.get('group_style'), list) else (
        {c['group_style']} if c.get('group_style') else set())
    for it in items:
        if it['zone'] != 'drill' or it['tbl'] is not None:
            continue
        if it['style'] in group_styles and not grp_rx.match(it['text'] or ''):
            F.add('drill_tool', 'FAIL', '分组标签不符合 drill.group_label_regex', it, text=bh.clip(it['text'], 40))


def _stem_stable_id(stem, source=None):
    """题干（execution 模式下连题源也编进去）的稳定哈希，不用位置性的 group:no，修复 major 5；
    source 传 None 时只按 stem 算（decision 模式内部沿用旧口径），execution 模式两处调用都传
    source（修复 minor：cda.verify 本身核 statement+source，execution 只核 statement 口径不一致）。"""
    key = bh.norm(stem or '')
    if source is not None:
        key += '\x00' + bh.norm(source or '')
    return hashlib.sha1(key.encode('utf-8')).hexdigest()[:16]


def _admission_check_decision(args, items, P, layout, c, decisions, F):
    """核"决策文件本身是否完整、格式对"，不代表已经执行——exclude 的条目此刻仍在书稿里是正常状态，
    不在这里报 FAIL（这正是上一轮的 bug：决策含 exclude 时永远不能 PASS）。执行结果见 execution 模式。"""
    recs, D2, a1n, a2n, mismatch = (_extract_table3(items, P, c) if layout == 'table3'
                                     else _extract_paragraph(items, P, c))
    candidates = [{'id': '%s:%s' % (r['group'], r['no']), 'text': '%s、%s' % (r['no'], r['stem']),
                   'source': r.get('source', '')} for r in recs]
    in_sha = decisions.get('input_sha256') if isinstance(decisions, dict) else None
    docx_sha = dl.sha256_file(args.docx)
    if in_sha and in_sha.lower() != docx_sha.lower():
        F.add('drill_tool', 'FAIL', '准入裁决 input_sha256 与本次 --docx 不符（决策可能是针对另一版书稿做的）', None, decisions_sha=in_sha, docx_sha=docx_sha)
        return {'status': 'fail', 'mode': 'decision', 'error': 'input_sha256_mismatch'}
    try:
        result = cda.verify(candidates, decisions)
    except (ValueError, KeyError) as e:
        F.add('drill_tool', 'FAIL', '准入裁决核对失败：%s' % e, None)
        return {'status': 'fail', 'mode': 'decision', 'error': str(e)}
    result['mode'] = 'decision'
    return result


def _admission_check_execution(args, items, P, layout, c, decisions, F):
    """核"决策有没有被正确执行"：用稳定 id（题干哈希）比对，候选稿里剩下的条目须等于全部 retain，
    全部 exclude 一个都不在候选稿里。不用位置性 group:no，也不要求 input_sha256 与 --docx 一致。"""
    ds = decisions if isinstance(decisions, list) else (decisions or {}).get('records')
    if not isinstance(ds, list):
        F.add('drill_tool', 'FAIL', '准入执行核对失败：决策文件格式不对（缺 records）', None)
        return {'status': 'fail', 'mode': 'execution', 'error': 'bad_decisions_format'}
    retained_ids, excluded_ids, bad = set(), set(), []
    for d in ds:
        action = d.get('action') if isinstance(d, dict) else None
        statement = d.get('statement') if isinstance(d, dict) else None
        if action not in ('retain', 'exclude') or not isinstance(statement, str) or not statement.strip():
            bad.append(d.get('old_id') if isinstance(d, dict) else None)
            continue
        # 修复 minor：稳定 id 把 source 也编进去，题源被单独篡改也会体现为"这个 id 不在候选稿里了"。
        sid = _stem_stable_id(statement, d.get('source') if isinstance(d, dict) else None)
        (retained_ids if action == 'retain' else excluded_ids).add(sid)
    if bad:
        F.add('drill_tool', 'FAIL', '准入执行核对失败：%d 条决策缺 action/statement，无法算出稳定 id' % len(bad), None, old_ids=bad[:20])
        return {'status': 'fail', 'mode': 'execution', 'error': 'bad_decision_entries', 'bad_count': len(bad)}
    recs, D2, a1n, a2n, mismatch = (_extract_table3(items, P, c) if layout == 'table3'
                                     else _extract_paragraph(items, P, c))
    cur_ids = {}
    for r in recs:
        cur_ids.setdefault(_stem_stable_id(r['stem'], r.get('source')), []).append(r)
    cur_id_set = set(cur_ids.keys())
    problems = {
        'missing_retained': (sorted(retained_ids - cur_id_set), '准入裁决为保留，但候选稿里找不到该条目（题干变了或被误删）'),
        'still_excluded': (sorted(excluded_ids & cur_id_set), '准入裁决为排除，但该条目仍在候选稿内'),
        'unexpected_extra': (sorted(cur_id_set - retained_ids - excluded_ids), '候选稿里有条目不在本次准入裁决内（既不是 retain 也不是 exclude）'),
        'duplicate_stable_ids': (sorted(k for k, v in cur_ids.items() if len(v) > 1), '候选稿里有条目题干哈希重复，稳定 id 无法唯一核对，需人工复核'),
    }
    for ids, rule in problems.values():
        if ids:
            F.add('drill_tool', 'FAIL', rule, None, ids=ids[:20])
    ok = not any(ids for ids, _ in problems.values())
    out = {'status': 'pass' if ok else 'fail', 'mode': 'execution',
           'retained_expected': len(retained_ids), 'excluded_expected': len(excluded_ids), 'current_count': len(recs)}
    out.update((k, len(v[0])) for k, v in problems.items())
    return out


def _extra_drill_checks(items, P, c, F):
    """bh.check_drill 之外补的几项：题源为空（仅 table3）、序号连续、A1/A2 题干逐字一致、分组标签格式。
    cmd_check 与 build 写后自查共用同一份逻辑（修复 major 3：写后门不能只跑 bh.check_drill）。"""
    layout = c.get('layout', 'table3')
    D = bh.collect_drill(items, P)
    A1 = [x for x in D['recs'] if x['sec'] == 'A1']
    A2 = [x for x in D['recs'] if x['sec'] != 'A1']
    if layout == 'table3':
        for x in A2:
            if not (x['src'] or '').strip():
                F.add('drill_tool', 'FAIL', '题源为空', x['it'], text=bh.clip(x['text'], 40))
    _check_seq_and_stems(A1, A2, F)
    _check_group_labels(items, P, c, F)
    return D, A1, A2


def cmd_check(args):
    pd = get_profile_readonly(args)
    P = bh.Prof(pd)
    items, _ = bh.read_docx(args.docx)
    bh.walk(items, P)
    F = bh.Findings()
    c = pd.get('drill') or {}
    layout = _norm_layout(c.get('layout', 'table3'))
    admission_result = None
    if layout == 'card':
        # card 版式完全走 _check_card，不经 bh.check_drill（见 _check_card 文档串：bh 对 card 没有
        # 专门分支，会退化成 paragraph 逻辑产生误判 FAIL，不是"与 bh 结论不一致"，是 bh 根本没管这版式）。
        if args.admission:
            raise Abort(2, 'drill.layout 为 card：--admission 尚未实现（功能缺失，不是配置缺失），见文件头'
                        '"已知不做的事"')
        summary = _check_card(items, c, F)
    else:
        summary = bh.check_drill(items, P, F)
        # bh.check_drill 没检查的几项，drill_tool 补（不动 bh）
        D, A1, A2 = _extra_drill_checks(items, P, c, F)

        # --admission 分两种用法，不再混在一起判 pass/fail（修复 major 5，见上面两个函数的说明）。
        if args.admission:
            try:
                decisions_raw = Path(args.admission).read_text(encoding='utf-8')
                decisions = json.loads(decisions_raw)
            except (ValueError, OSError) as e:
                F.add('drill_tool', 'FAIL', '准入裁决文件读取失败：%s' % e, None)
                admission_result = {'status': 'fail', 'error': str(e)}
            else:
                mode = getattr(args, 'admission_mode', None) or 'decision'
                if mode == 'execution':
                    admission_result = _admission_check_execution(args, items, P, layout, c, decisions, F)
                else:
                    admission_result = _admission_check_decision(args, items, P, layout, c, decisions, F)

    fails = [f for f in F.items if f['level'] == 'FAIL']
    warns = [f for f in F.items if f['level'] == 'WARN']
    cands = [f for f in F.items if f['level'] == 'CANDIDATE']
    rep = {'tool': {'name': 'drill_tool', 'cmd': 'check', 'version': TOOL_VERSION}, 'mode': 'check',
           'profile': pd.get('book_id'),
           'inputs': [{'path': str(Path(args.docx).resolve()), 'sha256': dl.sha256_file(args.docx)}],
           'layout': layout, 'summary': summary,
           'counts': {'FAIL': len(fails), 'WARN': len(warns), 'CANDIDATE': len(cands)},
           'findings': F.items}
    if admission_result is not None:
        rep['admission'] = admission_result
    if args.report:
        write_json(guard_json(args.report, pd, [args.docx, args.admission], purpose='report', mode='check'), rep)
    print(json.dumps({'layout': layout, 'summary': summary, 'counts': rep['counts']}, ensure_ascii=False))
    return 1 if F.items else 0


# ------------------------------------------------------------------ build（仅 table3）
def _top_level_tables(body):
    out = []

    def rec(el):
        for ch in el:
            if ch.tag == W + 'tbl':
                out.append(ch)
            elif ch.tag in (W + 'sdt', W + 'sdtContent', W + 'customXml', W + 'smartTag'):
                rec(ch)
            elif ch.tag == MC + 'AlternateContent':
                cc = ch.find(MC + 'Choice')
                if cc is not None:
                    rec(cc)
    rec(body)
    return out


def _ordered_tables(items, want_sec):
    seen = []
    for it in items:
        if it.get('zone') == 'drill' and it.get('drill_sec') == want_sec and it['tbl'] is not None:
            if it['tbl'] not in seen:
                seen.append(it['tbl'])
    return seen


def _fill_paragraph_runs(p, specs):
    """把一个 <w:p> 里现有的 w:r 全部换成 specs 描述的新 run，rPr（字体等）继承该段原有第一个带
    rPr 的 run，只改 w:color；w:pPr（段落格式，如行距）完全不碰，天然沿用调用方传进来的这个 tc 原有
    的段落——所以模板必须取"同组相邻的原稿行"，而不是全书随便一行，见 _pick_template。"""
    tmpl_rpr = None
    for r in p.findall(W + 'r'):
        rpr = r.find(W + 'rPr')
        if rpr is not None:
            tmpl_rpr = rpr
            break
    for r in p.findall(W + 'r'):
        p.remove(r)
    for spec in specs:
        text = spec.get('text', '')
        kind = spec.get('t')
        if kind not in ('tab', 'br') and not text:
            continue
        r = etree.SubElement(p, W + 'r')
        if tmpl_rpr is not None:
            rpr = copy.deepcopy(tmpl_rpr)
            color = spec.get('color')
            if color:
                cel = rpr.find(W + 'color')
                if cel is None:
                    cel = etree.SubElement(rpr, W + 'color')
                cel.set(W + 'val', color)
            r.append(rpr)
        if kind == 'tab':
            etree.SubElement(r, W + 'tab')
        elif kind == 'br':
            etree.SubElement(r, W + 'br')
        else:
            t = etree.SubElement(r, W + 't')
            t.text = text
            t.set(XML_SPACE, 'preserve')


def _rebuild_cell(tc, specs):
    ps = tc.findall(W + 'p')
    if not ps:
        raise Abort(2, '模板单元格没有段落，drill_tool 无法生成（tc 内 w:p 数=0）')
    _fill_paragraph_runs(ps[0], specs)
    for extra in ps[1:]:
        extra.getparent().remove(extra)


def _template_num_sep_is_tab(p):
    """模板题干段落里"序号、"后面是不是紧跟一个 w:tab——不是每个模板都用 tab 分隔（B2_230 有一批
    "无制表符"的行）。第一个带非空文字的 run 视为"序号所在 run"，看它后面那个 run 是不是纯 w:tab；
    找不到文字 run 就退回旧默认 True。"""
    runs = p.findall(W + 'r')
    for i, r in enumerate(runs):
        t = r.find(W + 't')
        if t is not None and (t.text or '').strip():
            nxt = runs[i + 1] if i + 1 < len(runs) else None
            return nxt is not None and nxt.find(W + 'tab') is not None
    return True


def _template_has_br(p):
    return any(r.find(W + 'br') is not None for r in p.findall(W + 'r'))


def _rebuild_stem_cell(tc, stem_specs, correction, cor_c):
    ps = tc.findall(W + 'p')
    if not ps:
        raise Abort(2, '模板单元格没有段落，drill_tool 无法生成')
    if correction:
        if len(ps) >= 2:
            _fill_paragraph_runs(ps[0], stem_specs)
            _fill_paragraph_runs(ps[1], [{'t': 'text', 'text': correction, 'color': cor_c}])
            for extra in ps[2:]:
                extra.getparent().remove(extra)
        else:
            # 模板题干与纠正同段（只 1 个 w:p）：照模板原本是不是用 <w:br/> 隔开来生成，认不出分隔
            # 方式就 Abort（修复 minor：旧版无条件直接拼接，丢了 <w:br/> 换行，也不管模板到底是怎么
            # 分隔的，不再猜测，做不到就中止）。
            if not _template_has_br(ps[0]):
                raise Abort(2, '模板题干与纠正同段（只 1 个 w:p）但找不到 <w:br/> 分隔符，drill_tool 不'
                            '认识这类模板的排版结构，不猜测生成，需人工确认后再扩展（模板单元格文字节选：'
                            '%r）' % bh.clip(''.join((t.text or '') for t in ps[0].findall('.//' + W + 't')), 60))
            combined = list(stem_specs) + [{'t': 'br'}, {'t': 'text', 'text': correction, 'color': cor_c}]
            _fill_paragraph_runs(ps[0], combined)
    else:
        _fill_paragraph_runs(ps[0], stem_specs)
        for extra in ps[1:]:
            extra.getparent().remove(extra)


def _verify_built_stem(tr, sc, no, stem, correction=None):
    """写后第二道防线（修复 major 2）：重建行题干首段原文须恰好等于 no+stem（同段模板再接纠正）。"""
    tcs = tr.findall(W + 'tc')
    ps = tcs[sc].findall(W + 'p')
    text = ''.join((t.text or '') for t in ps[0].findall(W + 'r/' + W + 't'))
    expected = '%s、%s' % (no, stem)
    combined = correction and len(ps) < 2
    if combined:
        expected += correction
    if text != expected:
        raise Abort(2, '写后核对失败：重建行题干与 rec["stem"] 不一致（no=%s）：得到 %r，期望 %r' % (no, bh.clip(text, 60), bh.clip(expected, 60)))


def _resolve_error_run_offsets(no, stem, error_runs):
    """修复 major 4：error_runs 里每条如果自带 start/end 就直接用（并核对 stem[start:end]==text，防止
    人工改过 stem 却没同步偏移）；只给了字符串（旧式/人工新增条目常见）时退回 find()，但要求在 stem 里
    恰好出现一次，出现零次或不止一次都中止——不再"找第一次出现处"猜位置。"""
    out = []
    for seg in (error_runs or []):
        if isinstance(seg, dict):
            text, s, e = seg.get('text', ''), seg.get('start'), seg.get('end')
            if s is None or e is None:
                seg = text  # 没给偏移，走下面的字符串分支
            else:
                if not (0 <= s <= e <= len(stem)) or stem[s:e] != text:
                    raise Abort(2, 'error_runs 偏移与 stem 对不上（no=%s）：start=%s end=%s text=%r stem[start:end]=%r' %
                                (no, s, e, text[:30], stem[s:e] if 0 <= s <= e <= len(stem) else None))
                out.append((s, e, text))
                continue
        if not seg:
            continue
        n = stem.count(seg)
        if n != 1:
            raise Abort(2, 'error_runs 片段在 stem 中出现 %d 次（no=%s），位置不唯一，drill_tool 不猜：%r' %
                        (n, no, seg[:30]))
        idx = stem.find(seg)
        out.append((idx, idx + len(seg), seg))
    out.sort(key=lambda t: t[0])
    # 片段不许重叠，否则 _stem_specs 会把重叠部分写两遍，悄悄改坏题肢文字（修复 major 2）。排序后只需相邻比较。
    for i in range(1, len(out)):
        if out[i][0] < out[i - 1][1]:
            raise Abort(2, 'error_runs 片段重叠（no=%s）：%r 与 %r' % (no, out[i - 1], out[i]))
    return out


def _stem_specs(no, stem, error_runs, default_color, err_c, sep_tab=True):
    specs = [{'t': 'text', 'text': '%s、' % no, 'color': default_color}]
    if sep_tab:
        specs.append({'t': 'tab', 'color': default_color})
    segs = _resolve_error_run_offsets(no, stem, error_runs)
    pos = 0
    for s, e, _text in segs:
        if s > pos:
            specs.append({'t': 'text', 'text': stem[pos:s], 'color': default_color})
        specs.append({'t': 'text', 'text': stem[s:e], 'color': err_c})
        pos = e
    if pos < len(stem):
        specs.append({'t': 'text', 'text': stem[pos:], 'color': default_color})
    return specs


def _build_a2_tr(template, sc, ac, rc, rec, no, default_color, err_c, cor_c):
    correction = rec.get('correction') if rec.get('verdict') == '错误' else None
    if template is None:
        raise Abort(2, '本册单练里找不到一条 verdict=%s 的原稿行可当模板' % rec.get('verdict'))
    tr = copy.deepcopy(template)
    tcs = tr.findall(W + 'tc')
    if len(tcs) < 3:
        raise Abort(2, 'A2 模板行少于 3 个单元格，无法按 table3 版式生成')
    tmpl_ps = tcs[sc].findall(W + 'p')
    # 序号与题干正文之间是否有 tab，照模板本身的排版来定，不是每本书/每组都用 tab 分隔（修复 minor，
    # 与"同段模板保留 w:br"是同一处教训：生成新行不能无条件套一套固定分隔符，要先看模板长什么样）。
    sep_tab = _template_num_sep_is_tab(tmpl_ps[0]) if tmpl_ps else True
    specs = _stem_specs(no, rec['stem'], rec.get('error_runs'), default_color, err_c, sep_tab=sep_tab)
    _rebuild_stem_cell(tcs[sc], specs, correction, cor_c)
    _rebuild_cell(tcs[ac], [{'t': 'text', 'text': rec['verdict'], 'color': default_color}])
    _rebuild_cell(tcs[rc], [{'t': 'text', 'text': rec.get('source') or '', 'color': default_color}])
    return tr


def _build_a1_tr(template_tr, sc, ac, rc, rec, no, default_color, a1_blank):
    tr = copy.deepcopy(template_tr)
    tcs = tr.findall(W + 'tc')
    if len(tcs) < 3:
        raise Abort(2, 'A1 模板行少于 3 个单元格，无法按 table3 版式生成')
    tmpl_ps = tcs[sc].findall(W + 'p')
    sep_tab = _template_num_sep_is_tab(tmpl_ps[0]) if tmpl_ps else True
    specs = [{'t': 'text', 'text': '%s、' % no, 'color': default_color}]
    if sep_tab:
        specs.append({'t': 'tab', 'color': default_color})
    specs.append({'t': 'text', 'text': rec['stem'], 'color': default_color})
    _rebuild_cell(tcs[sc], specs)
    _rebuild_cell(tcs[ac], [{'t': 'text', 'text': a1_blank, 'color': default_color}])
    _rebuild_cell(tcs[rc], [{'t': 'text', 'text': rec.get('source') or '', 'color': default_color}])
    return tr


def _a1_matches_rec(items, a1_table, a1_row, rec, no, item_rx, marker, sc, ac, rc, blank_norm, err_c, cor_c):
    """A1 是否真的"由 A2 派生、未被改动"：直接核对 A1 那一行现在的真实内容（题干、空括号、题源、
    无红绿），任何一项对不上都判定为"内容变了"，交给模板重建从 A2 派生。"""
    if a1_table is None or a1_row is None:
        return False
    stem_runs = _row_cell_runs(items, a1_table, a1_row, sc)
    m = item_rx.match(''.join(t for t, _ in stem_runs))
    if not m:
        return False
    cols = {col for _, col in stem_runs}
    return (m.group(1) == str(no) and not (marker and marker in m.group(2)) and
            bh.norm(m.group(2)) == bh.norm(rec.get('stem') or '') and
            err_c not in cols and cor_c not in cols and
            bh.norm(_cell_raw_text(items, a1_table, a1_row, ac)) == blank_norm and
            bh.norm(_cell_raw_text(items, a1_table, a1_row, rc)) == bh.norm(rec.get('source') or ''))


def _leading_run_pieces(p):
    """题干段落"开头的连续 run"：w:t 记 (run, t节点, 文字)；w:tab 记 (run, None, None) 占位（不算文字，
    不打断"连续"）；遇到别的子元素（域、书签……）立即停止收集——序号只在这段纯文字/tab 前缀里找（修复
    major 2：旧版全段乱找，题干正文以同数字/年份开头，或序号拆成两个 run，都会被错误命中改坏正文）。"""
    out = []
    for r in p.findall(W + 'r'):
        t = r.find(W + 't')
        if t is not None:
            out.append((r, t, t.text or ''))
            continue
        if r.find(W + 'tab') is not None:
            out.append((r, None, None))
            continue
        break
    return out


def _tc_full_text(tc):
    return ''.join((t.text or '') for t in tc.findall('.//' + W + 't'))


def _renumber_row(tr, sc, old_no, new_no, item_rx):
    """内容没变、只是序号后移：只替换开头序号数字所占字符区间，不走模板/run 重建，原有分隔符/pPr/
    rPr/纠正段落结构全部原样保留。序号定位只认段首连续 run 拼接串（见 _leading_run_pieces），交给
    本册 item_regex 匹配，只信 group(1) 圈出的字符区间是"序号数字"；匹配不到、或数字与 old_no 不符，
    一律 Abort(2)，绝不改题干正文（修复 major 2；旧提示"改用模板重建"与实际行为不符，改成"中止"）。
    序号可能跨多个 run：新序号整个写进第一个覆盖到的 run，其余覆盖到的 run 只删自己那部分数字、保留
    分隔符不动。写后核对：整个 tc 全文须恰好等于"新序号＋原全文去掉旧序号"。"""
    tcs = tr.findall(W + 'tc')
    if len(tcs) <= sc:
        raise Abort(2, '第 %s→%s 行序号定位失败（单元格数不够），中止，不猜测位置' % (old_no, new_no))
    tc = tcs[sc]
    ps = tc.findall(W + 'p')
    if not ps:
        raise Abort(2, '第 %s→%s 行序号定位失败（题干单元格没有段落），中止，不猜测位置' % (old_no, new_no))
    before_full = _tc_full_text(tc)
    pieces = _leading_run_pieces(ps[0])
    concat = ''.join(t for _, tnode, t in pieces if tnode is not None)
    m = item_rx.match(concat)
    old_no_s = str(old_no)
    if not m or m.group(1) != old_no_s or m.start(1) != 0:
        raise Abort(2, '第 %s→%s 行序号定位失败（题干段落开头拼接文字不是"旧序号+分隔符"开头，或序号跨 '
                    'run 但仍拼不出来），中止，不猜测位置：段首拼接文字=%r' % (old_no, new_no, bh.clip(concat, 30)))
    target_len = m.end(1)  # 序号数字本身占的字符数，不含分隔符，绝不多动一个字符
    remaining = target_len
    first_written = False
    for _r, tnode, t in pieces:
        if remaining <= 0 or tnode is None or not t:
            continue
        take = min(remaining, len(t))
        if not first_written:
            tnode.text = new_no + t[take:]
            first_written = True
        else:
            tnode.text = t[take:]
        remaining -= take
    if remaining > 0 or not first_written:
        raise Abort(2, '第 %s→%s 行序号定位失败（拼接串够长但实际 run 文字不够覆盖序号区间），中止' % (old_no, new_no))
    after_full = _tc_full_text(tc)
    expected = new_no + before_full[len(old_no_s):]
    if after_full != expected:
        raise Abort(2, '写后核对失败：第 %s→%s 行重编号后单元格全文与预期不符，得到 %r，期望 %r' %
                    (old_no, new_no, bh.clip(after_full, 60), bh.clip(expected, 60)))


_LEADING_NO_RX = re.compile(r'^\d+[、.．]\s*')
# 位置/序号性质字段不参与 _fail_content_key 判定；其余字段（table、answers、a1、a2、dup/missing/
# extra、limit……）才是区分"这条 FAIL 是不是同一个对象"的判定字段。
_KEY_EXCLUDE_FIELDS = ('check', 'level', 'rule', 'src', 'where', 'excerpt')


def _fail_content_key(f):
    """写后单练门比较"父稿是否已有这条 FAIL"（修复 major 1）：旧版只用 (rule, 去序号 norm 的
    excerpt)。bh 的表级 FAIL（如"A2 表内正误不齐"）根本没有 excerpt，只有 table/answers 等字段区分
    对象，缺失时旧 key 退化成 (rule, '')——父稿在表 864 已有的 FAIL 会掩盖候选稿在表 865 新造的同规则
    FAIL。改成：excerpt 存在就仍按老办法算；同时把 finding 里除位置/序号字段外的全部判定字段取出来，
    排序序列化并入键，这样同规则不同 table/answers 的 FAIL 天然是不同键。"""
    text = f.get('excerpt')
    if text:
        text = bh.norm(_LEADING_NO_RX.sub('', text, count=1))
    else:
        text = None
    extra = {k: v for k, v in f.items() if k not in _KEY_EXCLUDE_FIELDS}
    extra_key = json.dumps(extra, ensure_ascii=False, sort_keys=True, default=str) if extra else None
    return (f.get('rule'), text, extra_key)


def _new_fails(base_fails, cand_fails):
    """候选稿 FAIL 是否比父稿"新增"：不能只靠"键在不在父稿集合里"做集合比较——一次 build 里如果同时
    修好一条父稿原有 FAIL、又新增一条与父稿另一条 FAIL 内容键完全相同的条目（如把缺题源的条目复制一
    份），候选稿里这个键的出现次数其实比父稿多了一次，但集合比较看不出"次数"，会把新增那条也当成
    "父稿已有"漏放过去。改成按内容键做多重集合（Counter）比较：候选稿逐条遍历，同一个键在候选稿里
    出现的次数一旦超过父稿该键的计数，超出的那些条目才算新增；未超出的沿用父稿基线。再按 rule 分组
    计数兜底：任一规则的 FAIL 条数比父稿多，该规则下候选稿全部 FAIL 都算新增（宁可多算，不放过）。
    （修复 major 1，收口修复"一修一增"漏洞）。"""
    from collections import Counter
    base_key_n = Counter(_fail_content_key(f) for f in base_fails)
    base_rule_n = Counter(f.get('rule') for f in base_fails)
    cand_rule_n = Counter(f.get('rule') for f in cand_fails)
    seen_key_n = Counter()
    out = []
    for f in cand_fails:
        rule = f.get('rule')
        key = _fail_content_key(f)
        seen_key_n[key] += 1
        if seen_key_n[key] > base_key_n.get(key, 0) or cand_rule_n[rule] > base_rule_n.get(rule, 0):
            out.append(f)
    return out


def _alternate_order(recs, seed):
    rnd = random.Random(seed)
    err = [r for r in recs if r.get('verdict') == '错误']
    ok = [r for r in recs if r.get('verdict') == '正确']
    others = [r for r in recs if r.get('verdict') not in ('错误', '正确')]
    if len(err) == len(ok):
        first = err if rnd.random() < 0.5 else ok
    else:
        first = err if len(err) > len(ok) else ok
    second = ok if first is err else err
    out, turn = [], 0
    a, b = list(first), list(second)
    while a or b:
        cur = a if turn % 2 == 0 else b
        other = b if turn % 2 == 0 else a
        if cur:
            out.append(cur.pop(0))
        elif other:
            out.append(other.pop(0))
        turn += 1
    return out + others


def cmd_build(args):
    pd = get_profile_strict(args)
    c = pd.get('drill') or {}
    layout = _norm_layout(c.get('layout', 'table3'))
    if layout == 'paragraph':
        # 功能未实现（非配置缺失），不只说"只支持 table3"（修复 major 6）。
        raise Abort(2, 'build 尚未实现 drill.layout=="paragraph"——功能未实现，不是配置缺失。需要以下配置全部到位并经人核验：drill.item_styles、drill.correction_styles、drill.group_label_regex 或 group_style、drill.paragraph_verdict_regex。见"已知不做的事"')
    if layout == 'card':
        # 2026-09-24 第三批：card 的 extract/check 已实现，build 仍未实现——题卡结构比三列表复杂得多，
        # 不能像 table3 那样直接借同组相邻行当模板，需要额外配置（见 _CARD_BUILD_NEEDED_FIELDS），如实
        # 拒绝，不伪造。
        needed = '；'.join(_CARD_BUILD_NEEDED_FIELDS)
        raise Abort(2, 'build 尚未实现 drill.layout=%r（功能未实现，不是配置缺失；card 版式目前只支持 '
                    'extract/check，本工具的 build 只支持 table3）。若要做 card 的 build，还需要以下配置'
                    '字段：%s，见"已知不做的事"' % (c.get('layout'), needed))
    if layout != 'table3':
        raise Abort(2, 'build 尚未实现 drill.layout=%r（功能未实现，本工具只支持 table3 和（仅 extract/'
                    'check）paragraph/card）' % layout)
    # 先过输出守卫再做任何重活：冻结册/受保护目录/输出与输入同一文件都要在这里就近拒绝（退出码 3）。
    out = dl.guard_write(args.out, pd, inputs=[args.docx, args.items], kind='.docx')
    # 修复 major 7：--report 的守卫也要在写任何主输出之前先过一遍——不能等 docx 写完才发现报告路径不合规。
    rep_out = None
    if args.report:
        rep_out = guard_json(args.report, pd, [args.docx, args.items, args.out], purpose='report', mode='build')

    d = dl.open_docx(args.docx, expect_sha256=args.expect_sha)
    P = bh.Prof(pd)
    bh.walk(d.items, P)
    before_paras = list(d.paras)

    a1_tables = _ordered_tables(d.items, 'A1')
    a2_tables = _ordered_tables(d.items, 'A2')
    if not a1_tables or not a2_tables:
        raise Abort(2, '没有识别到 A1/A2 单练表格（structure.parts[].drill / drill.a1_heading/a2_heading 配置核实）')
    if len(a1_tables) != len(a2_tables):
        raise Abort(2, 'A1 表格数（%d）与 A2 表格数（%d）不一致，drill_tool 不猜配对' % (len(a1_tables), len(a2_tables)))
    a1_of = dict(zip(a2_tables, a1_tables))

    # 修复 major 5：非条目行（表头、组内小标题……）一律不许 build 悄悄删掉；发现就中止并列出来，
    # 由人决定怎么处理（挪出表格 / 补进 drill.item_regex 白名单等），不代替人做这个判断。
    non_item = _non_item_rows_table3(d.items, set(a1_tables) | set(a2_tables), c)
    if non_item:
        raise Abort(2, '本册单练表格里有 %d 行不是可识别的条目行（表头/小标题等），build 不会替换整表，'
                    '请先处理这些行再重跑：%s' % (len(non_item), json.dumps(non_item[:10], ensure_ascii=False)))

    items_payload = json.loads(Path(args.items).read_text(encoding='utf-8'))
    if items_payload.get('schema') != 'baodian_drill_items_v1':
        raise Abort(2, '--items 不是 baodian_drill_items_v1 格式')
    # 修复 major 6：a1/a2 条数不一致的 items.json 一律拒绝喂给 build（那份 items 本身就没抽全）。
    if items_payload.get('a1_a2_count_mismatch'):
        raise Abort(2, '--items 标记 a1_a2_count_mismatch=true（抽取时 A1/A2 条数不一致），build 拒绝使用这份 items，'
                    '请先在父稿里把 A1/A2 对齐后重新 extract')
    records = items_payload.get('records')
    if not isinstance(records, list) or not records:
        raise Abort(2, '--items 里 records 为空')

    # 修复 minor：items.source_sha256 与父稿不一致时默认拒绝（防止旧父稿的 items 被套到表格序号刚好
    # 也存在、但内容已经不同的新父稿上，静默覆盖新改动）；--allow-rebase 显式放行。
    src_sha = items_payload.get('source_sha256')
    if src_sha and src_sha.lower() != d.sha256.lower() and not args.allow_rebase:
        raise Abort(2, '--items 的 source_sha256（%s…）与 --docx 当前 SHA（%s…）不一致，可能是另一版父稿抽出来的 '
                    'items；确认这些 group/no 仍然对应正确的位置后加 --allow-rebase 重跑' %
                    (src_sha[:16], d.sha256[:16]))

    by_group = {}
    order_seq = []
    for rec in records:
        g = rec.get('group')
        if g is None:
            g = (rec.get('a2') or {}).get('table')
        if g not in a2_tables:
            raise Abort(2, '条目 no=%s 的 group=%r 不是识别到的 A2 表格序号：%s' % (rec.get('no'), g, a2_tables))
        if not (rec.get('stem') or '').strip():
            raise Abort(2, '条目 group=%s no=%s 缺 stem' % (g, rec.get('no')))
        if rec.get('verdict') not in (c.get('a2_allowed') or ['正确', '错误']):
            raise Abort(2, '条目 group=%s no=%s 的 verdict=%r 不在 drill.a2_allowed 内' % (g, rec.get('no'), rec.get('verdict')))
        # 修复 minor：verdict=正确 却带 correction/error_runs，静默丢弃太危险，直接中止让人去改数据。
        if rec.get('verdict') == '正确' and (rec.get('correction') or rec.get('error_runs')):
            raise Abort(2, '条目 group=%s no=%s 的 verdict=正确 但带 correction/error_runs，drill_tool 不会静默丢弃，'
                        '请先在 items.json 里去掉这些字段或把 verdict 改成错误' % (g, rec.get('no')))
        by_group.setdefault(g, []).append(rec)
        if g not in order_seq:
            order_seq.append(g)
    missing_groups = [g for g in a2_tables if g not in by_group]
    if missing_groups:
        raise Abort(2, '这些 A2 表格在 --items 里一条记录都没有，drill_tool 不支持清空整表：%s' % missing_groups)

    body_tables = _top_level_tables(d.body)
    err_c = (c.get('colors', {}) or {}).get('error_run', 'C00000').upper()
    cor_c = (c.get('colors', {}) or {}).get('correction', '008000').upper()
    a1_blank = c.get('a1_blank', '（　）')
    sc, ac, rc = c.get('stem_col', 0), c.get('answer_col', 1), c.get('source_col', 2)
    marker = c.get('correction_marker', '纠正：')
    item_rx = re.compile(c.get('item_regex') or r'^(\d+)[、.．]\s*(.*)$', re.S)
    blank_norm = bh.norm(a1_blank)

    # 原稿当前状态的逐行记录（修复 blocker 2 的关键数据）：按 (table,row) 索引，供"这条记录跟父稿这个
    # 位置现在的内容是否完全一样"的判断使用；字段口径与 items.json 里的一致（原文，不做 norm）。
    orig_recs, _D0, _a1n0, _a2n0, _mm0 = _extract_table3(d.items, P, c)
    orig_by_a2 = {(r['a2']['table'], r['a2']['row']): r for r in orig_recs}
    orig_by_a1 = {(r['a1']['table'], r['a1']['row']): r for r in orig_recs if r.get('a1')}

    # 全书兜底模板（找不到同组模板时才用，比如整表都是新增条目）：书内第一条"正确"/"错误" A2 原始行。
    ok_rec0 = next((x for x in orig_recs if x['verdict'] == '正确'), None)
    err_rec0 = next((x for x in orig_recs if x['verdict'] == '错误'), None)
    if ok_rec0 is None and err_rec0 is None:
        raise Abort(2, '本册单练一条 A2 记录都没有，无法取模板行')
    global_ok_tpl = (copy.deepcopy(body_tables[ok_rec0['a2']['table'] - 1].findall(W + 'tr')[ok_rec0['a2']['row']])
                      if ok_rec0 else None)
    global_err_tpl = (copy.deepcopy(body_tables[err_rec0['a2']['table'] - 1].findall(W + 'tr')[err_rec0['a2']['row']])
                       if err_rec0 else None)
    global_a1_tpl = copy.deepcopy(body_tables[a1_tables[0] - 1].findall(W + 'tr')[0])
    base_rec = ok_rec0 or err_rec0
    global_a2_color = _default_run_color(
        _row_cell_runs(d.items, base_rec['a2']['table'], base_rec['a2']['row'], sc), {err_c, cor_c})
    global_a1_color = _default_run_color(
        _row_cell_runs(d.items, a1_tables[0], min(it['row'] for it in d.items if it['tbl'] == a1_tables[0]), sc),
        {err_c, cor_c})

    touched_tbl_ids = {id(body_tables[g - 1]) for g in a2_tables} | {id(body_tables[t - 1]) for t in a1_tables}

    def _in_touched(p):
        for anc in p.iterancestors():
            if id(anc) in touched_tbl_ids:
                return True
        return False

    touched_before = {i for i, p in enumerate(before_paras) if _in_touched(p)}

    plan = []
    seq = 0
    for g in a2_tables:
        recs = list(by_group[g])
        if args.order == 'alternate':
            recs = _alternate_order(recs, args.seed)
        a2_tbl_el = body_tables[g - 1]
        a1_tbl_el = body_tables[a1_of[g] - 1]

        orig_a2_trs = a2_tbl_el.findall(W + 'tr')
        orig_a1_trs = a1_tbl_el.findall(W + 'tr')
        # 同组模板：本组第一条"正确"/"错误"原始行；本组没有就退回全书兜底模板（修复 blocker 2：不再
        # 一律用全书第一行当模板，避免把别组的行距/分隔符风格带进这一组）。
        grp_ok_tpl = None
        grp_err_tpl = None
        for row_i, tr in enumerate(orig_a2_trs):
            orow = orig_by_a2.get((g, row_i))
            if orow is None:
                continue
            if orow['verdict'] == '正确' and grp_ok_tpl is None:
                grp_ok_tpl = tr
            elif orow['verdict'] == '错误' and grp_err_tpl is None:
                grp_err_tpl = tr
        grp_a1_tpl = orig_a1_trs[0] if orig_a1_trs else None

        new_a2 = []
        new_a1 = []
        reused, renumbered, rebuilt = 0, 0, 0
        for rec in recs:
            seq += 1
            no = str(seq)
            a2pos = rec.get('a2') or {}
            a1pos = rec.get('a1') or {}
            key2 = (a2pos.get('table'), a2pos.get('row'))
            key1 = (a1pos.get('table'), a1pos.get('row'))
            orow2 = orig_by_a2.get(key2)
            orow1 = orig_by_a1.get(key1)
            # A1 是否"未改动"直接读 A1 现在的真实内容核对（修复 major 3），序号用 orow2['no']（旧序号）。
            content_same = (
                orow2 is not None and orow1 is not None and orow2['group'] == g and
                orow2['stem'] == rec.get('stem') and orow2['verdict'] == rec.get('verdict') and
                (orow2.get('correction') or None) == (rec.get('correction') or None) and
                (orow2.get('source') or '') == (rec.get('source') or '') and
                _error_runs_equal(orow2.get('error_runs'), rec.get('error_runs')) and
                _a1_matches_rec(d.items, key1[0], key1[1], rec, orow2['no'], item_rx, marker, sc, ac, rc,
                                 blank_norm, err_c, cor_c)
            )
            if content_same and orow2['no'] == no:
                # 内容与父稿这个位置完全一样：原样复制父稿的 tr，round-trip 天然 0 差异（修复 blocker 2）。
                new_a2.append(copy.deepcopy(orig_a2_trs[key2[1]]))
                new_a1.append(copy.deepcopy(orig_a1_trs[key1[1]]))
                reused += 1
                continue
            if content_same:
                # 内容没变、只是序号后移：原样复制父稿两行，只改开头序号文字，保留原有分隔符/纠正段落结构（修复 major 4）。
                a2_tr = copy.deepcopy(orig_a2_trs[key2[1]])
                a1_tr = copy.deepcopy(orig_a1_trs[key1[1]])
                _renumber_row(a2_tr, sc, orow2['no'], no, item_rx)
                _renumber_row(a1_tr, sc, orow2['no'], no, item_rx)
                new_a2.append(a2_tr)
                new_a1.append(a1_tr)
                renumbered += 1
                continue
            preferred = grp_err_tpl if rec.get('verdict') == '错误' else grp_ok_tpl
            fallback_grp = grp_ok_tpl if grp_ok_tpl is not None else grp_err_tpl
            preferred_global = global_err_tpl if rec.get('verdict') == '错误' else global_ok_tpl
            a2_tpl = None
            for cand in (preferred, fallback_grp, preferred_global, global_ok_tpl, global_err_tpl):
                if cand is not None:
                    a2_tpl = cand
                    break
            a1_tpl = grp_a1_tpl if grp_a1_tpl is not None else global_a1_tpl
            a2_tr = _build_a2_tr(a2_tpl, sc, ac, rc, rec, no, global_a2_color, err_c, cor_c)
            _verify_built_stem(a2_tr, sc, no, rec['stem'],
                               rec.get('correction') if rec.get('verdict') == '错误' else None)
            new_a2.append(a2_tr)
            new_a1.append(_build_a1_tr(a1_tpl, sc, ac, rc, rec, no, global_a1_color, a1_blank))
            rebuilt += 1
        for tr in a2_tbl_el.findall(W + 'tr'):
            a2_tbl_el.remove(tr)
        for tr in new_a2:
            a2_tbl_el.append(tr)
        for tr in a1_tbl_el.findall(W + 'tr'):
            a1_tbl_el.remove(tr)
        for tr in new_a1:
            a1_tbl_el.append(tr)
        plan.append({'group': g, 'a1_table': a1_of[g], 'count': len(recs), 'reused': reused,
                      'renumbered': renumbered, 'rebuilt': rebuilt,
                      'answers': dict((v, sum(1 for r in recs if r.get('verdict') == v)) for v in set(r.get('verdict') for r in recs))})

    d.refresh()
    touched_after = {i for i, p in enumerate(d.paras) if _in_touched(p)}
    unchanged_bad = dl.unchanged_paragraphs(before_paras, d.paras, touched_before, touched_after)

    import tempfile
    import os
    fd, tmp_path = tempfile.mkstemp(prefix='.drill_tool_verify_', suffix='.docx', dir=tempfile.gettempdir())
    os.close(fd)
    os.unlink(tmp_path)
    try:
        dl.write_docx(d, tmp_path)
        d2 = dl.open_docx(tmp_path)
        bh.walk(d2.items, P)
        F2 = bh.Findings()
        summary2 = bh.check_drill(d2.items, P, F2)
        # 修复 major 3：写后门不能只跑 bh.check_drill——drill_tool 自己补的几项（题源为空、序号连续、
        # A1/A2 题干一致、分组标签）也要在候选稿上跑一遍，否则这类问题写后门看不出来，退出码仍是 0。
        _extra_drill_checks(d2.items, P, c, F2)
        fails2 = [f for f in F2.items if f['level'] == 'FAIL']
        # 修复 minor：跟父稿比"新增" FAIL，不是父稿本来就有的旧 FAIL 也一并拦。
        F0 = bh.Findings()
        bh.check_drill(d.items, P, F0)  # d.items 是原稿快照（bh.walk 早于本次改动），重跑得到父稿基线安全。
        _extra_drill_checks(d.items, P, c, F0)  # 父稿基线也要跑同一套补充检查，口径才能对齐。
        base_fails = [f for f in F0.items if f['level'] == 'FAIL']
        new_fails = _new_fails(base_fails, fails2)
        if new_fails:
            raise Abort(1, '写后单练门体检比父稿新增 %d 条 FAIL，整批中止、不留输出：%s' %
                        (len(new_fails), json.dumps(new_fails[:5], ensure_ascii=False)))
        if fails2 and not new_fails:
            say('提示：写后单练门仍有 %d 条 FAIL，但与父稿原有 FAIL 相同，不算新增，不阻塞（父稿自身的缺口）：%s' %
                (len(fails2), json.dumps(fails2[:5], ensure_ascii=False)))
        if unchanged_bad:
            raise Abort(2, '未点名段落被改动（%d 处），整批中止、不留输出：%s' %
                        (len(unchanged_bad), json.dumps(unchanged_bad[:5], ensure_ascii=False)))
        final = dl.write_docx(d, out)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    rep = {'tool': {'name': 'drill_tool', 'cmd': 'build', 'version': TOOL_VERSION}, 'mode': 'build',
           'profile': pd.get('book_id'), 'order': args.order, 'seed': args.seed,
           'inputs': [{'path': str(Path(args.docx).resolve()), 'sha256': d.sha256},
                      {'path': str(Path(args.items).resolve())}],
           'out': final, 'groups': plan, 'summary_after': summary2,
           'unchanged_check': {'bad': unchanged_bad, 'touched_before': len(touched_before), 'touched_after': len(touched_after)}}
    if rep_out is not None:
        try:
            write_json(rep_out, rep)
        except Exception:
            try:
                Path(final['out']).unlink()
            except OSError:
                pass
            raise
    print(json.dumps({'out': final['out'], 'sha256': final['sha256'], 'groups': len(plan)}, ensure_ascii=False))
    return 0


def _error_runs_equal(a, b):
    def norm_list(x):
        out = []
        for seg in (x or []):
            if isinstance(seg, dict):
                out.append((seg.get('text'), seg.get('start'), seg.get('end')))
            else:
                out.append((seg, None, None))
        return out
    la, lb = norm_list(a), norm_list(b)
    if len(la) != len(lb):
        return False
    for (ta, sa, ea), (tb, sb, eb) in zip(la, lb):
        if ta != tb:
            return False
        if sa is not None and sb is not None and (sa, ea) != (sb, eb):
            return False
    return True


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--debug', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)

    e = sub.add_parser('extract')
    e.add_argument('--docx', required=True)
    e.add_argument('--out', required=True)
    e.add_argument('--profile')
    e.add_argument('--report')

    k = sub.add_parser('check')
    k.add_argument('--docx', required=True)
    k.add_argument('--admission')
    k.add_argument('--admission-mode', dest='admission_mode', choices=['decision', 'execution'], default='decision')
    k.add_argument('--profile')
    k.add_argument('--report')

    b = sub.add_parser('build')
    b.add_argument('--docx', required=True)
    b.add_argument('--items', required=True)
    b.add_argument('--out', required=True)
    b.add_argument('--profile')
    b.add_argument('--expect-sha', dest='expect_sha')
    b.add_argument('--allow-rebase', dest='allow_rebase', action='store_true')
    b.add_argument('--order', choices=['as-given', 'alternate'], default='as-given')
    b.add_argument('--seed', type=int, default=0)
    b.add_argument('--report')

    args = ap.parse_args()
    t0 = time.time()
    try:
        if args.cmd == 'extract':
            code = cmd_extract(args)
        elif args.cmd == 'check':
            code = cmd_check(args)
        else:
            code = cmd_build(args)
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
