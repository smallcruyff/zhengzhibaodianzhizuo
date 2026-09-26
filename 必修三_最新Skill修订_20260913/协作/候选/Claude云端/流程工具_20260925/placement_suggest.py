#!/usr/bin/env python3
"""新题插入位置建议：给一道新题找目标书里最像的考法与相邻样板题块（新卷入书流水线第 5 步）。

用法
  单题（题库题键，可带小问 #1 或 (1)，小问目前不裁剪，按整题处理——见 known_limits）：
    placement_suggest.py --docx 目标书.docx --profile bixiu3 --key BJ-2026-HD-YIMO-Q17 [--report x.json]
  批量：
    placement_suggest.py --docx 目标书.docx --profile bixiu3 --keys-file 新题清单.txt [--format md --out x.md]
  逐题 MD（不经题库题键，直接给文件）：
    placement_suggest.py --docx 目标书.docx --profile bixiu3 --md 某题.md
  纯文本（设问＋细则，格式见 load_question_from_text）：
    placement_suggest.py --docx 目标书.docx --profile bixiu3 --text 新题.txt --kind subjective
公共参数：--bank（默认 cfg.bank，即 profile 的 sources.bank.root）、--top-k（默认 3）、
  --max-chars（样例切片截断，默认 800）、--params 参数 JSON（覆盖 DEFAULT_PARAMS）、
  --report x.json、--format json|md（md 给模型读）、--out（--format md 的落盘路径）、--debug。

做法（设计稿第 5 步）
  1. 目标书用 block_index.walk/finish_blocks（作库调用，不重写识别逻辑）切出题块；每块正文按段首
     【标签】切成若干“标签桶”，标签文字按关键词分到四个抽象角色：material（材料/题目/答案，含无标签
     前导文本——本书选择题没有【题目】标签，材料就是无标签前导段）、ask（设问）、rubric（细则）、
     teaching（分析过程/答案落点/思维链条/为什么能想到/错肢分析/答案与错项，等等——选择题没有“细则”
     标签时，用这个角色的文字顶替 rubric）。这套角色关键词表与具体书册的 column_schemas 标签名无关，
     同一套代码不经改动就能跑 bixiu3 的 subj4/topic5/choice 与哲学等书的 p1_subjective/p1_choice
     （已用 profiles_cloud 草案验证，见回执）。
  2. “考法说明”（考法标题下、第一道例题前的说明段）不在 block_index 的输出里（walk() 认出这段但按
     node_level_paras 丢弃文字），本工具按 profile styles.method_desc 的样式名直接从 doc['paras'] 里
     取，归到离它最近的“考法”标题（heads 记录的位置顺序），与“考法名”拼成一个 method 字段。
  3. 新题的“材料/设问”来自题库逐题 MD：MD 若自带“读取指引（机器可读）”一节并点名“采用题面小节：
     `节名`”（反引号可选），优先按这个精确节名取（覆盖 native/OCR候选等分歧、按 MD 自己的判断选更可信
     的一份；点名“无”就是题库本身没有可用题面，如实报 InputError，不猜、不退回关键词兜底）；没有这一
     节时退回关键词匹配（“题面”“题干”“题目原文”“原题保真”“原卷逐字/逐项转写”等，节名写法随导出批次
     而不同，见 STEM_HEADER_RX；关键词兜底排除“不得当作题面/讲评/含答案/参考答案”类标题，避免命中
     明令不得当题面的讲评块——返修 M4）。取到题面后用同一句末引导词启发式（运用/结合/说明/分析/……）
     从末尾切出“设问”，切不出就把最后一句当设问并标 ask_heuristic=true；“细则”取节名命中“正式评分|
     E1|阅卷细则|评分细则|评标|OFFICIAL_ANSWER_AND_SCORING|同卷正式材料|详细题级评分主载体”（返修
     M1-r3：后三种节名不含前几个字样，题库有整卷用这几种写法）且排除“候选评分材料/参考答案（E3）”
     的节，多个候选标题时取层级最深、同层取文档序更早的（返修 M3/M1-r2）；判定为“无 E1”时若题库
     索引 rubric_links.csv 另有信号，加提示不静默（返修 M1-r3）。题型：MD 的“题型”字段（写“选择/
     非选择/主观”等）优先于 A/B/C/D 选项行
     启发式；两者冲突（如“非选择题”但题面里恰好有 A．开头的观点列举）只加 kind_conflict 说明，不
     静默互相覆盖；字段缺失/含糊时才退回选项行启发式兜底，兜底同时认“A．/A：/- **A**:”等写法
     （返修 M1：原来选项行启发式无条件覆盖字段，题型判反的题会绕过“主观题无细则→不收”这条过滤）。
  4. 四个字段各建一个字符 2–3gram BM25 倒排索引（整本书只建一次），按 DEFAULT_PARAMS['weights'] 加权、
     每字段先按本次查询里的最大值归一化再求和，得到每个题块的匹配分；按（部分, 节点, 考法名）分组，
     组内取分最高的 agg_top_k 个题块，以 agg_mix*最高分+(1-agg_mix)*均值 作为该考法的分数，取分最高的
     --top-k 组为候选。选择题只在 choice 题块里选考法，主观题/专题只在 subjective/topic/topic_case
     里选（KIND_GROUPS）；选择题在本书没有独立考法标题，候选标签标成“节点选择区”而非假装是考法
     （返修 m7）。
  5. 过滤但不删除（只标注，交主代理裁定）：设问（只查设问，不再连材料一起查——返修 m9）命中 profile
     的 sources.stem_module_guard（如“《经济与社会》”）→ flags 加“设问含跨模块限定”；非选择题细则
     判定为空（e1_present=false）→ flags 加“主观题无正式细则，按规则不收”；题键已在本书落位（按
     b['key'] 或 keys_all 命中，覆盖“一块引两个题键”的情况——返修 m10）→ flags 加“已在本书落位”并
     退出 1（返修 M6：原来静默剔除、无任何提示）；未被题键剔除时另按全书每个题块的未截断正文再查
     一次疑似重复（find_suspected_duplicate，不再要求 base_key 缺失才查、也不再只挑 BM25 排名
     靠前的子集——返修 M2-r3，专防错号重卷这类“给的题键在书里查不到、内容却几乎相同”的漏报）
     → flags 加“疑似题库重复”并退出1；查询与全书候选均零相似信号 → flags 加“无相似信号”
     （返修 m2）。
  6. 每个候选考法给：部分/一级/二级节点/考法名、分数、主要贡献词（查询与该组最像题块共有的、idf 加权
     最高的若干 n-gram）、组内最像的题块（含 p_range/body_range/题型）、插入点建议——project-rules.md
     “题目排序”明文必修三 v5.7-R 系列只在节点内按既有顺序插入新增题（不套用该文件/counting-sorting-
     policy.md 给的“主观先于客观/…/年份从新到旧”那组键，那组键只用于用户明确授权的全书重排），本工具
     因此给“考法末尾”（该组当前文档序最后一个题块之后）并注明依据，具体插在哪由主代理定；同时给出
     block_insert 能直接引用的锚点——先核末题标题在全书是否唯一命中，不唯一时改给 method_end
     （method_contains+node_contains）并核该组是否唯一，两种都给 anchor_unique 如实标注（返修 M5：
     原来无条件给 title_contains，约 10% 的组会让 block_insert 因“命中 2 个题块”整批 Abort）；同样
     给 template_block（most_similar_block 标题不唯一时换成组内标题唯一的块，仍不唯一如实标
     template_unique=false——返修 m2）。--format md 直接打印 anchor 字典本身，不再拿一个可能不
     唯一的标题充当“锚点”（返修 m1）。另附一道最像题块的原文切片（block_index.render_recs 同一
     渲染口径，--max-chars 截断处写明）。

只读；除 --report/--out（落 docx_lib.guard_write 允许的位置：…/协作/候选/<谁>/<批次>/构建/ 或系统临时
目录）不写任何文件。不改书稿、不改题库、不判教学对错，只给 CANDIDATE。
两个输出路径的 guard_write 校验挪到装书、算候选之前做（冻结册等问题在这一步就“立即”拒绝，不用等算完），
真正落盘挪到全部算完之后、用临时文件+os.replace 原子写，任一步失败都清理已写出的另一个文件（含临时
文件本身），全部写成功才打印“已写”提示，不留半成品、不提前报喜（返修 M8/m5）。
退出码：0 正常出候选且无需注意项；1 出了候选但有 flags（跨模块/无细则/已在本书落位/无相似信号/题型
冲突/具名无E1例外）需要主代理看；2 输入/参数错误（题键不在题库、书稿按此配置 0 题块、缺 --bank 且
profile 无 sources.bank.root、--top-k/--max-chars 越界、--params 非法等）；3 拒绝写出（--report/--out
落点不合规、profile 已冻结）。异常一律中文提示，不打印 traceback（--debug 打开）。

返修历史：r1/r2/r3（2026-09-25）分别按 placement_suggest_审查_r1/r2/r3.json 修复，完整叙述见
C/回执/placement_suggest_返修_r1/r2.json、本轮 …_r3.json；代码内注释只保留仍生效的关键决定与本轮
新改动，过程性叙述不在代码里重复（返修 m8：行数超限，历史移出代码）。
"""
import sys

sys.dont_write_bytecode = True  # 不在 Skill 母版 scripts/ 里留下 __pycache__

import argparse
import json
import math
import os
import re
import time
import traceback
import zipfile
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path

TOOL = 'placement_suggest'
VERSION = '1.3.0'


# ---------------------------------------------------------------- 定位 Skill 脚本目录（硬规则 1，同 exam_register.py）
def _find_skill_dir():
    here = Path(__file__).resolve().parent
    if (here / 'docx_lib.py').is_file():
        return here
    env = os.environ.get('BAODIAN_SKILL_SCRIPTS')
    if env and (Path(env) / 'docx_lib.py').is_file():
        return Path(env).resolve()
    p = here
    for _ in range(12):
        cand = p / '.claude' / 'skills' / 'beijing-gaokao-politics' / 'scripts'
        if (cand / 'docx_lib.py').is_file():
            return cand
        if p.parent == p:
            break
        p = p.parent
    # 返修 m4：raise SystemExit('字符串') 会被 Python 当非整数消息处理，只打印消息、退出码固定是 1；
    # 约定 6 要求配置错误退出 2。这里自己打印中文提示，再用整数触发 SystemExit，退出码精确为 2。
    print('找不到 Skill 脚本目录（docx_lib.py）：本文件同目录、环境变量 BAODIAN_SKILL_SCRIPTS、'
          '向上逐级 .claude/skills/beijing-gaokao-politics/scripts 均未找到', file=sys.stderr)
    raise SystemExit(2)


SK_DIR = _find_skill_dir()
sys.path.insert(0, str(SK_DIR))
import docx_lib as dl  # noqa: E402
from profile_lib import load_profile  # noqa: E402
from block_index import (BookCfg, load_docx, walk, finish_blocks, sha256_file,  # noqa: E402
                          LABEL_AT, sig, render_recs, _exempt)

DEFAULT_PARAMS = {
    'weights': {'material': 1.0, 'ask': 1.8, 'rubric': 1.3, 'method': 0.6},
    'agg_top_k': 3,     # 该考法下取分最高的几个题块参与聚合
    'agg_mix': 0.6,     # 聚合 = agg_mix*组内最高分 + (1-agg_mix)*这几个题块的均分
    'bm25_k1': 1.5,
    'bm25_b': 0.75,
    'ngram_sizes': [2, 3],
}
KIND_GROUPS = {'choice': {'choice'}, 'subjective': {'subjective', 'topic', 'topic_case'}}

# 题库 MD 的“题面”一节，节名按导出批次不同至少见过这些写法（不同批题源转写脚本不同）；命中任一即可。
# 返修 m4（r2）：加“原题转录”——2026石景山期末整卷 20 个 MD 用这个节名，原来一律退出 2。
STEM_HEADER_RX = re.compile(r'题面|题干|题目原文|原题保真|原卷题面|原题文字|原卷逐字转写|原卷逐项转写|'
                             r'原题（E0|题库缓存转写|原卷\s*OCR\s*候选|原题完整候选文字|原题转录')
# 返修 M4：关键词兜底命中题面标题时，必须排除这些“明令不得当作题面”的标题（讲评/答案类小节），
# 否则 STEM_HEADER_RX 里的“题面”会命中“讲评来源块（含答案与解析，不得当作题面）”这类标题。
STEM_EXCLUDE_RX = re.compile(r'不得当作题面|讲评|含答案|参考答案|答案与解析')
# 原来只认“正式评分”，漏认“E1阅卷细则原文”“E1评分条件原文”“评分细则”“评标”等写法（返修 M3）；
# 用 E1(?!\d) 避免误命中 E10/E11 这类编号（本题库未见，留作防呆）。返修 M1-r3：题库还有三种节名
# 完全不含以上任何字样——“## 来源角色：OFFICIAL_ANSWER_AND_SCORING”（如 BJ-2024-DC-ERMO 全卷）、
# “## 评分材料（同卷正式材料·P…）”（BJ-2024-FT-ERMO 全卷）、“## 详细题级评分主载体（S…）”
# （BJ-2024-DC-YIMO 全卷）；三者节下都有逐点分值，且逐个核对过标题本身不含任何负面状态语，加入
# 候选（是否真有 E1 仍交下面 e1_present() 判正文，不是加了就直接算 True）。
E1_HEADER_RX = re.compile(r'E1(?!\d)|正式评分|阅卷细则|评分细则|评标|'
                           r'OFFICIAL_ANSWER_AND_SCORING|同卷正式材料|详细题级评分主载体')
# 返修 M1-r2：E1_HEADER_RX 放宽后必须同步收紧排除，否则会命中题库里明写“这不是 E1”的标题——
# “参考答案（E3；不得视为正式评分细则）”“E1评分层（严格不升格）”等（37 例见返修回执）。排除
# 含 E3/非E1/非正式/不是正式/不得当作或视为或据此或升格/严格不升格/候选评分材料/pending/N-A
# 字样的标题；单纯写“边界”不在此列，是否真有 E1 交给下面 e1_present() 判正文（fix_hint 原话
# “边界要看正文”）。N/A 加字母边界避免误命中“native/national”这类词里的“na”子串（真题
# BJ-2026-SY-ERMO-Q21 撞过）。“^来源[：:]”排除 2943 个“来源：`路径`”引用标签标题（指向原始
# 证据文件，不是“这就是 E1”的声明），但“来源角色：”（中间夹了“角色”二字）不在此列，不误伤
# M1-r3 新加的 OFFICIAL_ANSWER_AND_SCORING 候选。
E1_EXCLUDE_TITLE_RX = re.compile(
    r'候选评分材料|E3|非\s*E1(?!\d)|非正式|不是正式|不得(当作|视为|据此|升格)|严格不升格|'
    r'(?<![A-Za-z])N[/\-]?A(?![A-Za-z])|pending|^来源[：:]', re.IGNORECASE)
IDENTITY_HEADER_RX = re.compile(r'身份')
GUIDE_SECTION_RX = re.compile(r'读取指引')
# 返修 M4：真实 MD 里“采用题面小节: 无”并不总带反引号（原正则要求反引号，写法一变就整节被跳过）；
# 反引号改成可选，值仍按原样截到行尾/下一个反引号。
GUIDE_STEM_RX = re.compile(r'采用题面小节[：:]\s*`?([^`\n]+?)`?\s*(?:\n|$)')
# 返修 M1-r2：负面状态语只在候选节自己正文的“状态行”（前几行）里查，不再对整节全文做子串匹配
# （旧的“课件没有”会误伤后面嵌套子节，已删除——嵌套问题改由 section_own_body 从根上解决，见下）。
# 补上题库常见状态码：not_available、N/A_with_basis、E1_candidate_pending、正式评分槽为0、
# 没有为本题提供、按E3保留、no_fixed_slots（same_exam_level_table_no_fixed_slots 的核心信号）。
NO_E1_HINTS = ('未提供', '未找到', '没有该题', '无题级', '不得从其他题', '无逐点', '无该题独立',
               'not_available', 'N/A_with_basis', 'E1_candidate_pending', '正式评分槽为0',
               '没有为本题提供', '按E3保留', '按 E3 保留', 'no_fixed_slots')
NO_E1_HINT_RX = re.compile('|'.join(re.escape(h) for h in NO_E1_HINTS), re.IGNORECASE)
# 返修 M2-r2：跨模块守卫要看全部“设问句”（含未被 split_ask 切出的前置小问），不能只看 split_ask
# 切出的末尾那一句；候选设问句 = 含 ASK_MARKERS 引导词的句子，或以“（n）/(n)”开头的句子。
SUBQ_START_RX = re.compile(r'^[（(]\s*\d+\s*[)）]')
# 返修 M3-r2：--md 输入尽量从文件名/正文识别出题库题键，供“已在本书落位”查重复用。
MD_KEY_PATTERN_RX = re.compile(r'^[A-Z]{2}-\d{4}-.+-Q\d+$')
MD_KEY_IN_TEXT_RX = re.compile(r'question_id[`\s:：]*`?([A-Z]{2}-\d{4}-[A-Z0-9-]+?-Q\d+)`?')
MD_KEY_H1_RX = re.compile(r'(?m)^#\s+([A-Z]{2}-\d{4}-[A-Z0-9-]+?-Q\d+)\s*$')
# 返修 M1：原来只认“A．”“A.”“A、”，漏认“A：”“A:”与列表式“- **A**: ……”写法；这些常见写法当年被
# 判成“非选择题”的题里也会出现细则文字，是本条兜底探测应认的“选项行”。
OPTION_LINE_RX = re.compile(r'(?:^|\n)\s*[-*]?\s*\*{0,2}\s*[A-D]\s*\*{0,2}\s*[：:．.、]')
# 返修 M1：题型字段显式写“非选择题/主观题”时，即便题面里出现“A．”开头的观点/热点列表（很常见），
# 也不能被选项行启发式覆盖——字段明确时以字段为准，见 parse_question_md。
NONCHOICE_KIND_RX = re.compile(r'非选择|主观')
ASK_MARKERS = ('运用', '结合', '说明', '分析', '阐释', '阐述', '评析', '概括', '简析', '谈谈', '指出',
               '归纳', '请从', '请你', '设计', '拟写', '评价', '解读', '为什么')
SENT_SPLIT_RX = re.compile(r'(?<=[。！？])')
# 返修 m12（未实现，记入 known_limits）：这套关键词表是本工具自己另起的一套，没有接到各书 profile
# 的 column_schemas/labels_rules（约定3 的字面意思是“认题块/栏目/区位/编号复用 batch_health”，这套
# 角色分类是在题块之上再做的一层抽象聚合，batch_health 本身并不提供这一层，所以没有现成的东西可
# 直接复用）。已知代价：【答案】被并进 material、不是独立角色；段内软回车后的标签不切分（同
# block_index._labels_in 的既有行为，没有另起口径）。审查方接受“跨书能跑是优点”，本轮只在此注明，
# 不实现按 profile 覆盖——一是没有具体书反馈需要不同角色映射，二是这层改动会牵动打分口径，应放
# 到有真实需求（某本书的角色分类明显不对）时再单独改，避免为了“可配置”而无验证地引入新参数。
ROLE_RULES = [
    ('rubric', ('细则',)),
    ('ask', ('设问',)),
    ('teaching', ('分析过程', '答案落点', '思维链条', '为什么能想到', '为什么', '错肢分析', '答案与错项',
                  '评分标准', '评分方向')),
    ('material', ('材料', '题目', '答案')),
]


class InputError(Exception):
    """输入/参数错误，退出码 2。"""


# ================================================================== 题库 MD 解析
HEAD_RX = re.compile(r'(?m)^(#{1,6})\s+(.+?)\s*$')


def all_headings(text):
    """[(层级, 标题文字, 标题行起点, 标题行终点)]，按出现顺序。"""
    return [(len(m.group(1)), m.group(2).strip(), m.start(), m.end()) for m in HEAD_RX.finditer(text)]


def section_body(text, headings, i):
    """第 i 个标题自己的正文：到下一个层级 <= 它的标题为止（同级或更高级的兄弟/上级标题不算进来）；
    比它更深的子标题（如“## 答案层”下的“### 正式评分材料（E1）”）算作它的正文的一部分。"""
    level, _, _, end = headings[i]
    stop = len(text)
    for j in range(i + 1, len(headings)):
        if headings[j][0] <= level:
            stop = headings[j][2]
            break
    return text[end:stop]


def section_own_body(text, headings, i, extra_boundary_idxs=None):
    """返修 M1-r2：同 section_body，但 extra_boundary_idxs（E1 候选集合）里的标题即便层级更深，
    也提前当边界，用于判断某个 E1 候选节自己是否“有实质内容”，同时不误吞普通的组织性子标题。
    E1 候选常嵌套两种情况：(a) 外层标题本身也命中 E1_HEADER_RX 但正文只是背景说明，真内容在紧跟
    着的更深一层子候选里（如 BJ-2024-HD-QIZHONG-Q16“## 答案层”下的“### 正式评分材料（E1）”）；
    (b) 候选自己就是真内容，但正文按来源页/幻灯片再分了不命中 E1_HEADER_RX 的组织性子标题（如
    BJ-2026-FT-ERMO-Q16 的“### 幻灯片3”），不该被当边界。只有“同样命中 E1_HEADER_RX 的候选”才
    提前收尾，其余子标题照旧折进来，两种情况都能分开处理。"""
    level, _, _, end = headings[i]
    stop = len(text)
    for j in range(i + 1, len(headings)):
        if headings[j][0] <= level or (extra_boundary_idxs and j in extra_boundary_idxs):
            stop = headings[j][2]
            break
    return text[end:stop]


def find_heading(headings, rx, max_level=6, exclude_rx=None):
    """找第一个层级 <= max_level 且标题文字命中 rx（且不命中 exclude_rx）的标题；不同 MD 把 E1 放二级
    或三级（嵌在“答案层”下）都不固定，先按“较浅层级优先”找，找不到再放宽到任意层级。"""
    for lvl_cap in (max_level, 6):
        for i, (level, head, s, e) in enumerate(headings):
            if level <= lvl_cap and rx.search(head) and not (exclude_rx and exclude_rx.search(head)):
                return i
    return None


def find_heading_all(headings, rx, max_level=6, exclude_rx=None):
    """同 find_heading，但返回全部命中（按“较浅层级优先”的同一批次），供 M3 在多个候选标题里挑
    “第一个有实质内容”的那个，而不是无条件取文档序第一个。"""
    for lvl_cap in (max_level, 6):
        hits = [i for i, (level, head, s, e) in enumerate(headings)
                if level <= lvl_cap and rx.search(head) and not (exclude_rx and exclude_rx.search(head))]
        if hits:
            return hits
    return []


def clean_prose(text):
    """去 MD 噪声：子标题行、引用符（保留正文，只剥符号）、元数据项（`- \\`key\\`: ...`）、代码反引号、
    链接语法。返修 M2-r2：原来整行丢弃“>”开头的行；但部分批次把题面/评分材料整段用 Markdown 引用
    块包裹（如 BJ-2025-DC-ERMO-Q17 的“来源：细则.pdf”节、BJ-2024-HD-YIMO-Q17/18 的题面小问），
    整行丢弃会连题目文字、逐点分值一起丢掉，只剩“来源/页图”这类元数据行（题面里≥40字的引用块文字
    被丢的 MD 有 185 个，见 审查/placement_suggest_r2/probe_blockquote_stem2.log）。改成只剥离
    每行开头的一个或多个“>”（嵌套引用块），保留其后的正文；剥完只剩空行才丢弃。"""
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith('#'):
            continue
        while s.startswith('>'):
            s = s[1:].lstrip()
        if not s:
            continue
        if re.match(r'^[-*]\s*`', s):
            continue
        s = re.sub(r'`([^`]*)`', r'\1', s)
        s = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', s)
        out.append(s)
    return '\n'.join(out)


def e1_present(text):
    """返修 M1-r2：负面状态语只在候选节自己正文的前 3 个非空行（截 200 字）内查——真实题库里，
    “未提供/not_available/正式评分槽为0”这类状态语几乎总在候选节最前面（“- 状态：…”“- rubric_status:
    …”一类首行字段），全文子串匹配会被后面无关段落里的同形文字误伤（如背景说明句里恰好出现
    “未找到”）。"""
    t = re.sub(r'\s+', '', text or '')
    if len(t) < 15:
        return False
    head_lines = [ln.strip() for ln in (text or '').splitlines() if ln.strip()][:3]
    head = ('\n'.join(head_lines))[:200]
    return not NO_E1_HINT_RX.search(head)


def split_ask(text):
    """启发式：从末尾找第一条含引导词（ASK_MARKERS）的句子，其后到末尾算“设问”，之前算“材料”。
    找不到就把最后一句当设问（返回 heuristic=True，未必准，见 known_limits）。"""
    text = (text or '').strip()
    if not text:
        return '', '', False
    parts = [p for p in SENT_SPLIT_RX.split(text) if p.strip()]
    if len(parts) <= 1:
        return '', text, True
    for i in range(len(parts) - 1, -1, -1):
        if any(k in parts[i] for k in ASK_MARKERS):
            return ''.join(parts[:i]).strip(), ''.join(parts[i:]).strip(), False
    return ''.join(parts[:-1]).strip(), parts[-1].strip(), True


CHOICE_KIND_RX = re.compile(r'(?<!非)选择')  # “选择题”命中，“非选择题”不命中


def guided_stem_directive(text, headings):
    """有些批次的 MD 自带“读取指引”一节，直接点名“采用题面小节：`...`”（如指向题面的 native 版而非
    OCR 候选版），比关键词猜更准。返回指引里点名的原始字符串（未 strip 判断），没有“读取指引”一节
    或没有这一行都返回 None，交调用方判断。"""
    gi = find_heading(headings, GUIDE_SECTION_RX, max_level=2)
    if gi is None:
        return None
    m = GUIDE_STEM_RX.search(section_body(text, headings, gi))
    if not m:
        return None
    return m.group(1).strip()


def guided_stem_index(headings, directive):
    """按读取指引点名的小节名（精确文字匹配某个标题）找该标题的下标；指引未点名、或点名的小节在
    文档里找不到，都返回 None，交调用方退回 STEM_HEADER_RX 关键词匹配。“无”的判断在调用方做
    （见 parse_question_md），这里只管名字查找。"""
    if not directive:
        return None
    for i, (_, head, _, _) in enumerate(headings):
        if head.strip() == directive:
            return i
    return None


def _directive_missing_note(directive, found):
    """返修 m4（r2）：读取指引点名了一个具体节名，但文档里没有这个标题时，原来悄悄退回关键词匹配，
    不提示（28 个 MD 属这种情况，见 probe_bank_survey.log 的 dir_missing）。这里给调用方一条可选
    说明，供 parse_question_md 附进返回值、build_query_result 转成 flag，不是错误、不中止。"""
    if directive and not directive.startswith('无') and not found:
        return f'题库读取指引点名的题面小节“{directive}”在本 MD 里未找到，已退回关键词匹配（需人工核对）'
    return None


def parse_question_md(text, label):
    headings = all_headings(text)
    id_i = find_heading(headings, IDENTITY_HEADER_RX, max_level=2)
    id_body = section_body(text, headings, id_i) if id_i is not None else ''
    m = re.search(r'题型[：:]\s*(\S+)', id_body)
    kind_field = m.group(1) if m else ''

    # ---- 题面（返修 M4：读取指引点名“无”要如实报错，不能落到关键词兜底去猜） ----
    directive = guided_stem_directive(text, headings)
    if directive is not None and directive.startswith('无'):
        raise InputError(f'{label}：题库读取指引标注“采用题面小节：{directive}”——题库本身没有可用题面，'
                          f'如实报错，不猜')
    stem_i = guided_stem_index(headings, directive)
    directive_note = _directive_missing_note(directive, stem_i is not None)  # 返修 m4（r2）
    if stem_i is None:
        stem_i = find_heading(headings, STEM_HEADER_RX, max_level=2, exclude_rx=STEM_EXCLUDE_RX)
    stem_h = headings[stem_i][1] if stem_i is not None else None
    stem = clean_prose(section_body(text, headings, stem_i)) if stem_i is not None else ''
    if not stem_h:
        raise InputError(f'{label}：读取指引未点名题面小节，关键词（题面|题干|题目原文|原题保真|原卷题面 等，'
                          f'已排除“不得当作题面/讲评/含答案”类标题）在本 MD 的二级/三级标题里也未命中，'
                          f'需人工核对该 MD 格式')

    # ---- 正式评分 E1（返修 M3：节名放宽；返修 M1-r2：改按全部层级搜候选（不再“二级命中就不看
    # 三级”），每个候选只按 section_own_body 判自己的正文，不同候选各自独立判断） ----
    e1_candidates = find_heading_all(headings, E1_HEADER_RX, max_level=6, exclude_rx=E1_EXCLUDE_TITLE_RX)
    e1_cand_set = set(e1_candidates)
    e1_i, e1_h, rubric = None, None, ''
    best_key = None
    for pos, i in enumerate(e1_candidates):
        body = clean_prose(section_own_body(text, headings, i, extra_boundary_idxs=e1_cand_set))
        if not e1_present(body):
            continue
        # 多个候选都“无负面状态语、够长”时，取层级最深的那个（同层级取文档序更早的）：外层
        # 组织性标题（如“答案层（与评分细则分层）”）即使折进了非 POS 的子节内容、凑够长度，本质
        # 还是背景/参考答案，真正逐点分值的候选在更深一层（真题回归见 BJ-2024-HD-QIZHONG-Q16/
        # 17/19/20/21；同层级多候选见 BJ-2026-FT-ERMO-Q16，详见返修回执）。
        key = (headings[i][0], -pos)
        if best_key is None or key > best_key:
            best_key, e1_i, rubric = key, i, body
    if e1_i is None and e1_candidates:
        e1_i = e1_candidates[0]
        rubric = clean_prose(section_own_body(text, headings, e1_i, extra_boundary_idxs=e1_cand_set))
    if e1_i is not None:
        e1_h = headings[e1_i][1]

    # ---- 题型（返修 M1：字段明确时以字段为准，选项行启发式只在字段缺失/含糊时兜底；两者冲突只
    # 加 flag，不静默互相覆盖） ----
    option_hit = bool(OPTION_LINE_RX.search(stem))
    field_nonchoice = bool(NONCHOICE_KIND_RX.search(kind_field)) if kind_field else False
    field_choice = bool(CHOICE_KIND_RX.search(kind_field)) if kind_field else False
    kind_conflict = None
    if field_nonchoice:
        is_choice = False
        if option_hit:
            kind_conflict = (f'题型字段写“{kind_field}”（非选择/主观），但题面里探测到形如 “A．/A：/'
                              f'- **A**:” 的选项行——按字段判为非选择题，选项行按普通文本处理（可能只是'
                              f'材料里的观点/热点列举），如需复核请人工核对')
    elif field_choice:
        is_choice = True
        if not option_hit:
            kind_conflict = (f'题型字段写“{kind_field}”（选择），但题面里未探测到 A/B/C/D 选项行——'
                              f'按字段判为选择题，如需复核请人工核对（可能选项被截断或格式特殊）')
    else:
        is_choice = option_hit  # 字段缺失/含糊，退回选项行启发式兜底
    material, ask, heuristic = (stem, '', False) if is_choice else split_ask(stem)
    return {
        'source': label, 'kind': 'choice' if is_choice else 'subjective',
        'kind_field_raw': kind_field or None, 'kind_conflict': kind_conflict,
        'stem_header': stem_h, 'e1_header': e1_h,
        'material': material, 'ask': ask, 'ask_heuristic': heuristic,
        'rubric': rubric, 'e1_present': (True if is_choice else e1_present(rubric)),
        'stem_full': stem, 'directive_note': directive_note,
    }


def base_key_from_md(path, text):
    """返修 M3-r2：--md 输入原来完全不查“是否已在本书落位”（r1 的 M6 只修了 --key/--keys-file 那
    一半）。逐题 MD 的文件名本身就是题键（如 BJ-2024-DC-ERMO-Q21.md），优先用文件名；文件名不像
    题键（如测试用的合成文件名）时退回正文里的 question_id 字段或一级标题。都找不到时返回 None，
    交调用方走 find_suspected_duplicate 相似度兜底提示（build_query_result 里调用），不强行报错。"""
    stem = Path(path).stem
    if MD_KEY_PATTERN_RX.match(stem):
        return stem
    m = MD_KEY_IN_TEXT_RX.search(text)
    if m:
        return m.group(1)
    m = MD_KEY_H1_RX.search(text)
    if m:
        return m.group(1)
    return None


def load_question_from_md(path):
    p = Path(path)
    if not p.is_file():
        raise InputError(f'--md 文件不存在：{p}')
    text = p.read_text(encoding='utf-8', errors='replace')
    q = parse_question_md(text, f'MD:{p.name}')
    q['md_path'] = str(p.resolve())
    q['md_sha256'] = sha256_file(p)
    q['base_key'] = base_key_from_md(p, text)  # 返修 M3-r2
    q['subq'] = None
    return q


def load_question_from_text(path, kind_hint=None):
    """--text 纯文本文件：整份内容默认当“设问”；若含独立一行“细则/评分细则/正式评分/E1”（可带冒号），
    该行之后算“细则”，之前按 split_ask 再切一次材料/设问。识别不到分节、也未给 --kind 时默认 subjective。"""
    p = Path(path)
    if not p.is_file():
        raise InputError(f'--text 文件不存在：{p}')
    raw = p.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'(?im)^\s*(?:【?细则】?|评分细则|正式评分(?:材料|细则)?|E1)\s*[：:]?\s*$', raw)
    head, rubric = (raw[:m.start()], raw[m.end():].strip()) if m else (raw, '')
    is_choice = (kind_hint == 'choice') or (kind_hint is None and bool(OPTION_LINE_RX.search(head)))
    material, ask, heuristic = (head.strip(), '', False) if is_choice else split_ask(head)
    return {'source': f'TEXT:{p.name}', 'kind': 'choice' if is_choice else (kind_hint or 'subjective'),
            'kind_field_raw': None, 'kind_conflict': None, 'stem_header': '(纯文本，无分节)',
            'e1_header': '(纯文本)',
            'material': material, 'ask': ask, 'ask_heuristic': heuristic, 'rubric': rubric,
            'e1_present': True if is_choice else e1_present(rubric), 'stem_full': head.strip(),
            'md_path': str(p.resolve()), 'md_sha256': sha256_file(p), 'directive_note': None,
            'base_key': None, 'subq': None}


def parse_key_arg(raw):
    """'BJ-...-Q17'、'BJ-...-Q17(1)'、'BJ-...-Q17(１)'、'BJ-...-Q17#1' → (基础题键, 小问或None)。
    小问目前只记录，不裁剪正文。返修 m4：全角括号“（1）”原先不被接受，加上全角 （） 两种写法。
    返修 m9（r3）：'#' 写法原来接受任意非空白（'#abc' 被静默当成合法小问），小问本来就只有数字，
    改成只收数字，和 (1)/（1) 两种写法的校验口径一致。"""
    m = re.match(r'^(?P<base>.+-Q\d+)(?:[(（](?P<p1>\d+)[)）]|#(?P<p2>\d+))?$', raw.strip())
    if not m:
        raise InputError(f'--key 格式不像题库题键（应形如 BJ-2026-HD-YIMO-Q17，可带 (1)/（1）或 #1）：{raw!r}')
    return m.group('base'), (m.group('p1') or m.group('p2'))


def find_md_path(bank_root, base_key):
    """返修 m11：base_key 来自 --key/--keys-file，未做路径规范化时 '../../x-Q1' 能读到题库外的
    .md（虽只读，仍不应允许绕出 questions/ 目录）；这里在拼路径前拒绝任何带路径分隔符或 '..' 的题键，
    并在拼出路径后再核实解析结果确实落在 questions/ 目录下（双保险，防 exam 段落里藏编码过的分隔符）。"""
    if '/' in base_key or '\\' in base_key or '..' in base_key:
        raise InputError(f'题键里不能含路径分隔符或 ..：{base_key!r}')
    exam, _, qno = base_key.rpartition('-Q')
    questions_root = (Path(bank_root) / 'questions').resolve()
    p = (questions_root / exam / f'{exam}-Q{qno}.md').resolve()
    try:
        p.relative_to(questions_root)
    except ValueError:
        raise InputError(f'题键解析出的路径越出题库 questions/ 目录：{base_key!r}')
    return p


# ================================================================== 目标书：题块与字段
def load_book(docx, prof, expect_sha=None):
    if expect_sha:
        actual = sha256_file(docx)
        if actual.lower() != expect_sha.lower():
            raise InputError(f'父稿 SHA 不符：期望 {expect_sha[:16]}…，实际 {actual[:16]}…')
    cfg = BookCfg(prof)
    doc = load_docx(docx)
    blocks, drill_rows, heads, stats = walk(doc, cfg)
    blocks = finish_blocks(blocks, doc, cfg)
    if not blocks:
        raise InputError('该书稿按此 --profile 未识别到任何题块（配置可能不适用这本书，或正文为空）')
    return {'doc': doc, 'cfg': cfg, 'blocks': blocks, 'heads': heads}


def label_role(label):
    if not label:
        return 'material'  # 无标签前导文本（如本书选择题没有【题目】标签，材料/选项直接是前导段）
    for role, kws in ROLE_RULES:
        if any(k in label for k in kws):
            return role
    return 'other'


def segment_block_labels(recs):
    """按段首【标签】把题块正文（不含标题段）切成 {标签文字(''=前导无标签文本): 拼接正文}。"""
    buckets = OrderedDict()
    cur = ''
    for r in recs:
        t = r['text'].strip()
        if not t:
            continue
        m = LABEL_AT.match(t)
        if m:
            cur = m.group(1)
            rest = t[m.end():].strip()
            buckets.setdefault(cur, []).append(rest)
        else:
            buckets.setdefault(cur, []).append(t)
    return {k: '\n'.join(v).strip() for k, v in buckets.items() if '\n'.join(v).strip()}


def method_desc_style_set(prof):
    return set((prof.get('styles') or {}).get('method_desc') or [])


def build_method_intro(doc, heads, desc_styles):
    """考法标题到下一个标题前、样式为 styles.method_desc（如“考法说明”）的正文，按最近的前一个 method
    标题归并。walk() 会把这类段落判成 node_level_paras 并丢弃文字（不进任何题块），这里从 doc['paras']
    按样式直接取，是 block_index 本身没有暴露的东西，薄封装、不改它的识别逻辑。"""
    if not desc_styles:
        return {}
    mheads = sorted((h for h in heads if h['level'] == 'method'), key=lambda h: h['p'])
    if not mheads:
        return {}
    buckets, idx, cur = {}, 0, None
    for r in doc['paras']:
        while idx < len(mheads) and mheads[idx]['p'] <= r['p']:
            cur = mheads[idx]
            idx += 1
        if cur is None:
            continue
        if r['style'] in desc_styles and r['text'].strip():
            buckets.setdefault((cur['part'], cur['text']), []).append(r['text'].strip())
    return {k: '\n'.join(v) for k, v in buckets.items()}


def block_fields(block, method_intro):
    buckets = segment_block_labels(block['_recs'][1:])
    roled = {'material': [], 'ask': [], 'rubric': [], 'teaching': []}
    for label, text in buckets.items():
        role = label_role(label)
        if role in roled:
            roled[role].append(text)
    material = '\n'.join(roled['material']).strip()
    ask = '\n'.join(roled['ask']).strip()
    rubric = ('\n'.join(roled['rubric']) or '\n'.join(roled['teaching'])).strip()
    if not ask and material and block['kind'] != 'choice':
        # 大多数主观题块（如 subj4 的【题目】栏）材料与设问写在一起、没有独立【设问】栏；
        # 用同一条 split_ask 启发式补切，行为与新题从 MD 取设问时一致。选择题材料末句常是选项行，
        # 不是设问，不对选择题做这一步（与 parse_question_md 对选择题的处理一致）。
        material, ask, _ = split_ask(material)
    method_name = block['method'] or block['group'] or ''
    intro = method_intro.get((block['part'], method_name), '') if method_name else ''
    return {'material': material, 'ask': ask, 'rubric': rubric, 'method': (method_name + '\n' + intro).strip()}


FIELD_NAMES = ('material', 'ask', 'rubric', 'method')


def block_fields_all(blocks, method_intro):
    return [block_fields(b, method_intro) for b in blocks]


def matching_block_idxs(blocks, base_key):
    """返回题键为 base_key 的题块下标。返修 m10：原来只比较主键（b['key']，即 keys_all[0]），书里
    B0737 这类“一块引用两个题键”（如同时引 2022 与 2026 题）的题块，按非主键查询时漏排除。改成同时
    核对 keys_all（元素形如 'BASEKEY' 或 'BASEKEY(subq)'）。"""
    out = set()
    for i, b in enumerate(blocks):
        if b.get('key') == base_key:
            out.add(i)
            continue
        for k in (b.get('keys_all') or ()):
            if k == base_key or k.startswith(base_key + '('):
                out.add(i)
                break
    return out


def group_key_of(block):
    return (block['part'], block['node'], block['method'] or block['group'] or '')


def group_label(gk, is_choice=False):
    """返修 m7：选择题在本书没有独立“考法”标题，block_index 把它们挂在所在节点最后一个主观考法名
    下（继承上下文），显示成“…｜考法6｜”会让人误以为选择题也有专属考法。选择题组改标“节点选择区”，
    并把继承到的考法名注记为挂名，不当真考法呈现。"""
    part, node, method = gk
    if is_choice:
        tail = f"（书内挂在“{method}”名下，非独立考法）" if method else ''
        return f"{part}｜{node}｜节点选择区{tail}"
    return f"{part}｜{node}｜{method or '（无考法名）'}"


def stem_module_guard_hit(text, guard_list):
    for g in guard_list or ():
        if g and g in (text or ''):
            return g
    return None


def ask_like_sentences(text):
    """返修 M2-r2：跨模块守卫（规格“设问限定其他模块”）要看全部“设问句”，不能只看 split_ask 切出
    的末尾那一句——多小问的题（“（1）……（2）……”）常常只有最后一小问被 split_ask 当作“设问”，
    前面小问（含模块限定词的那句）落进 material，守卫因此漏报（34 道，见 审查/placement_suggest_r2/
    probe_guard_miss.log）。这里对整份题面（stem_full）逐句判：含 ASK_MARKERS 引导词，或以
    “（n）/(n)”开头的句子都算“设问句”，逐句喂给 stem_module_guard_hit，而不是把材料一起塞进去
    （m9 已修：材料里出现模块名不算）。"""
    parts = [p.strip() for p in SENT_SPLIT_RX.split(text or '') if p.strip()]
    return [p for p in parts if any(k in p for k in ASK_MARKERS) or SUBQ_START_RX.match(p)]


def _ngram_set(text, n=3):
    s = sig(text or '')
    return set(s[i:i + n] for i in range(len(s) - n + 1)) if len(s) >= n else set()


def ngram_containment(query_text, ref_text, n=3):
    """query_text 的 n-gram 有多大比例被 ref_text 覆盖（0-1）；用于疑似重复检查——退而用相似度
    提醒“很像已入书的这一块”，不是按题键就能精确剔重时的兜底信号（返修 M3-r2/M2-r3）。"""
    q = _ngram_set(query_text, n)
    if not q:
        return 0.0
    r = _ngram_set(ref_text, n)
    return (len(q & r) / len(q)) if r else 0.0


DUP_SCAN_THRESHOLD = 0.6


def find_suspected_duplicate(qinfo, book, exclude, threshold=DUP_SCAN_THRESHOLD):
    """返修 M2-r3：重复入书检测原来（a）只在 base_key 缺失时才跑——已知错号重卷（如 2025/2024 海淀
    期中是同一张卷）用 --key 查另一个题键时，base_key 有值但书里没有同键题块，检查被整段跳过，
    退出 0、无任何提示；（b）就算跑了，也只和聚合后候选组第 1 名（candidates[0]）比、且比的是按
    --max-chars 截断的 sample_slice，两处都会漏报（全书无键兜底漏报 59/141，见返修回执）。改成：
    不管 base_key 有没有识别出来，只要没有被题键剔重（exclude 为空）就跑；且和全书每个未剔除
    题块的未截断正文（render_recs 原样渲染，不受 --max-chars 影响）逐一比 3-gram 包含度，不再
    只挑 BM25 排名靠前的子集——试过“只比 BM25 组合分最高的前 N 块”，但书里有些材料被多个跨模块
    题块反复引用，BM25 的 idf 加权会把这类共享材料的分压得很低，真正的孪生块反而排不进前几十名
    （BJ-2021-BJ-GAOKAO-Q21 的孪生块 3-gram 包含度 0.93，按 BM25 组合分却排到第 349 名，前 N 块
    预筛会直接漏掉，返修时用真实数据验证过）。全书题块数通常在千余，逐块渲染＋算 3-gram 集合一次
    约 0.4 秒（746 块实测），比对本身几乎不耗时，可以承受，换成和全书直接比。命中（包含度 >=
    threshold）返回对方题块信息，交调用方转成 flag、退出 1；没命中返回 None。"""
    query_text = qinfo.get('stem_full') or ((qinfo.get('material') or '') + '\n' + (qinfo.get('ask') or ''))
    if not query_text.strip():
        return None
    blocks, doc = book['blocks'], book['doc']
    best = None
    for i, b in enumerate(blocks):
        if i in exclude:
            continue
        ref_text = render_recs(b['_recs'][1:], doc['rels'])
        ratio = ngram_containment(query_text, ref_text)
        if ratio >= threshold and (best is None or ratio > best[1]):
            best = (b, ratio)
    if best is None:
        return None
    b, ratio = best
    return {'block_id': b['id'], 'title': b['title'], 'key': b.get('key'), 'ratio': ratio}


_EXAM_LABEL_CACHE = {}


def exam_paper_label(bank_root, exam_id):
    """返修 m3（r2）：把题库 indexes/exams.csv 的 year+region+stage 拼成中文卷名（如“2024顺义二模”
    “2026石景山期末”“2026北京高考”），供 no_e1_exceptions.whole_papers 按子串匹配（与 block_index
    的 _exempt 同一口径：squash 后子串包含）。exams.csv 读不到或找不到这一行都返回空串，不报错——
    exempt 检查本就是“宁可漏判为不豁免，也不猜”，缺数据时按未豁免处理，仍然安全（只是少给一条
    “具名例外”的说明，不会误放行本该拦的假 E1）。"""
    key = str(bank_root)
    if key not in _EXAM_LABEL_CACHE:
        labels = {}
        p = Path(bank_root) / 'indexes' / 'exams.csv'
        if p.is_file():
            import csv
            with p.open(encoding='utf-8-sig', newline='') as f:
                for row in csv.DictReader(f):
                    eid = (row.get('exam_id') or '').strip()
                    if eid:
                        labels[eid] = ((row.get('year') or '').strip() + (row.get('region') or '').strip()
                                       + (row.get('stage') or '').strip())
        _EXAM_LABEL_CACHE[key] = labels
    return _EXAM_LABEL_CACHE[key].get(exam_id, '')


_RUBRIC_INDEX_CACHE = {}


def rubric_index_signal(bank_root, base_key):
    """返修 M1-r3：indexes/rubric_links.csv 的 pair_status 作 E1 判定的第二信号——工具从 MD 标题/
    正文判定 e1_present=False，但索引里这个题键有任一行 pair_status=='已匹配正式材料'时，两者
    冲突，不能静默：加一条 flag 提示人工核对（不直接翻转 e1_present，索引本身也可能过时，见
    m3-r2 important_notes 里 FT-YIMO 那几个例子）。读不到索引文件就返回 False（宁可不提示，不
    猜）。"""
    if not base_key or not bank_root:
        return False
    key = str(bank_root)
    if key not in _RUBRIC_INDEX_CACHE:
        hits = set()
        p = Path(bank_root) / 'indexes' / 'rubric_links.csv'
        if p.is_file():
            import csv
            with p.open(encoding='utf-8-sig', newline='') as f:
                for row in csv.DictReader(f):
                    if (row.get('pair_status') or '').strip() == '已匹配正式材料':
                        qid = (row.get('question_id') or '').strip()
                        if qid:
                            hits.add(qid)
        _RUBRIC_INDEX_CACHE[key] = hits
    return base_key in _RUBRIC_INDEX_CACHE[key]


def no_e1_exception_hit(prof, bank_root, base_key):
    """SCOPE-E1（user-requirements-ledger.md）：“已由用户具名的无细则例外不变”——profile 的
    sources.no_e1_exceptions 具名整卷/具名题，题库没有 E1 节时不算“按规则不收”，是“E3方向性，
    不拆E1”。原来完全没读这份配置。用 exam_paper_label 拼出的中文卷名 + base_key 本身一起喂给
    block_index._exempt（与 batch_health/block_index 同一豁免口径的薄封装，不改 block_index），
    任一命中即豁免。"""
    if not base_key or not bank_root:
        return False
    exam_id = base_key.rpartition('-Q')[0]
    label = exam_paper_label(bank_root, exam_id)
    return bool(_exempt(f'{base_key} {label}'.strip(), prof, 'sources.no_e1_exceptions'))


# ================================================================== 字符 n-gram BM25
class NGramIndex:
    def __init__(self, sizes=(2, 3)):
        self.sizes = tuple(sizes)
        self.docs = []       # [(tf_counter, doc_len)]
        self.df = Counter()
        self.postings = {}
        self.idf = {}
        self.avgdl = 0.0

    def _tok(self, text):
        s = sig(text)
        out = []
        for n in self.sizes:
            if len(s) >= n:
                out.extend(s[i:i + n] for i in range(len(s) - n + 1))
        return out

    def add(self, text):
        tf = Counter(self._tok(text))
        self.docs.append((tf, sum(tf.values())))
        for t in tf:
            self.df[t] += 1

    def finalize(self):
        n = len(self.docs)
        self.avgdl = (sum(dl for _, dl in self.docs) / n) if n else 0.0
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in self.df.items()}
        self.postings = {}
        for i, (tf, _) in enumerate(self.docs):
            for t, c in tf.items():
                self.postings.setdefault(t, []).append((i, c))

    def score(self, text, k1=1.5, b=0.75):
        qtok = Counter(self._tok(text))
        out = {}
        if not self.docs or not qtok:
            return out
        for t in qtok:
            plist = self.postings.get(t)
            idf = self.idf.get(t, 0.0)
            if not plist or idf <= 0:
                continue
            for i, c in plist:
                dl = self.docs[i][1]
                denom = c + k1 * (1 - b + b * (dl / self.avgdl if self.avgdl else 1.0))
                out[i] = out.get(i, 0.0) + idf * (c * (k1 + 1)) / denom
        return out

    def top_terms(self, text, doc_idx, limit=6):
        qtok = set(self._tok(text))
        tf = self.docs[doc_idx][0]
        contrib = sorted(((self.idf.get(t, 0.0) * tf[t], t) for t in qtok if t in tf), reverse=True)
        return [t for _, t in contrib[:limit] if t]


def build_indices(field_dicts, sizes):
    idxs = {f: NGramIndex(sizes) for f in FIELD_NAMES}
    for fd in field_dicts:
        for f in FIELD_NAMES:
            idxs[f].add(fd.get(f, ''))
    for idx in idxs.values():
        idx.finalize()
    return idxs


def score_blocks(query_fields, indices, n_blocks, params):
    weights = params['weights']
    combined = [0.0] * n_blocks
    per_field = {}
    for f, idx in indices.items():
        raw = idx.score(query_fields.get(f, ''), params['bm25_k1'], params['bm25_b'])
        mx = max(raw.values()) if raw else 0.0
        norm = {i: (v / mx if mx > 0 else 0.0) for i, v in raw.items()}
        per_field[f] = norm
        w = weights.get(f, 0.0)
        for i, v in norm.items():
            combined[i] += w * v
    return combined, per_field


def aggregate_methods(blocks, combined, kind_set, exclude_idx, params):
    """按（部分,节点,考法名）分组聚合，返回按分数降序的完整列表（不截断，截断交调用方）。"""
    groups = {}
    for i, b in enumerate(blocks):
        if i in exclude_idx or b['kind'] not in kind_set:
            continue
        groups.setdefault(group_key_of(b), []).append(i)
    ranked = []
    for gk, idxs in groups.items():
        idxs_sorted = sorted(idxs, key=lambda i: combined[i], reverse=True)
        top = idxs_sorted[:max(1, params['agg_top_k'])]
        scores = [combined[i] for i in top]
        agg = params['agg_mix'] * max(scores) + (1 - params['agg_mix']) * (sum(scores) / len(scores))
        ranked.append({'group_key': gk, 'agg_score': agg, 'block_idxs': idxs_sorted})
    ranked.sort(key=lambda r: r['agg_score'], reverse=True)
    return ranked


# ================================================================== 单条候选详情（含原文切片）
def truncate_slice(body, max_chars):
    if not max_chars or len(body) <= max_chars:
        return body, False
    cut = max_chars
    if body.rfind('〔', 0, cut) > body.rfind('〕', 0, cut):
        cut = body.find('〕', cut) + 1 or cut
    return body[:cut] + f'\n〔截断：本题块原文共 {len(body)} 字，此处只给前 {cut} 字〕', True


# 返修 m2（r2）：原文字断章取义地说这组排序键“只用于用户明确授权的全书重排或新建结构”，但
# project-rules.md 第151行、counting-sorting-policy.md 第113/136行原文写的是也适用于“在现有
# 节点内确定新增题的局部插入位置”——本工具不算这组排序键（只给“考法末尾”交主代理定组内位置），
# 但不能把规则说反，改成原样引用。
INSERT_NOTE = ('project-rules.md“题目排序”与 counting-sorting-policy.md“受控排序”给出的“主观先于'
               '客观/高考先于模拟/区县层级/…/年份从新到旧”这组排序键，按规则原文同时适用于“用户'
               '明确授权的全书重排、新建结构”和“在现有节点内确定新增题的局部插入位置”；本工具不计算'
               '这组排序键，只按既有文档序给“考法末尾”，组内具体插在哪一题之后、是否需要套用排序键'
               '由主代理按规则裁定。')


def _title_hit_count(blocks, title):
    return sum(1 for b in blocks if title and title in (b.get('title') or ''))


def _method_end_group_count(blocks, method, node):
    groups = set()
    for b in blocks:
        if method and method in (b.get('method') or '') and (not node or node in (b.get('node') or '')):
            groups.add((b.get('node'), b.get('method')))
    return len(groups)


def _anchor_dict(kind, **kwargs):
    """返修 m1（r2）：block_insert.resolve_insert_anchor 要的锚点形状是 {kind: {字段...}}
    （如 {'after_block': {'title_contains': ...}}、{'method_end': {'method_contains':…,
    'node_contains':…}}），不是 r1 给的扁平 {kind, title_contains}——原样喂 block_insert 会
    0/122 通过“anchor 必须且只能给 after_block/before_block/method_end 之一”这条检查（安全
    失败，但达不到规格“输出字段能直接被 block_insert 的插入单引用”）。"""
    body = OrderedDict((k, v) for k, v in kwargs.items() if v is not None)
    return OrderedDict([(kind, body)])


def _anchor_title_contains(anchor):
    for kind in ('after_block', 'before_block'):
        spec = anchor.get(kind)
        if spec:
            return spec.get('title_contains')
    return None


def _anchor_human(anchor):
    """返修 m1（r3）：--format md 原来固定打印 last_b 的标题当“锚点”，method_end/before_block
    改锚点恰恰是因为 last_b 标题在全书不唯一——模型照抄这个标题去填 after_block.title_contains，
    block_insert 会因命中 2 块 Abort（约 4/1029 个生产候选）。改成直接把 anchor 字典本身的
    kind+字段打出来，模型要抄就只能抄真正喂给 block_insert 的那个结构。"""
    kind = next(iter(anchor))
    spec = anchor[kind]
    if kind in ('after_block', 'before_block'):
        return f'{kind}（title_contains={spec.get("title_contains")!r}）'
    return f'method_end（method_contains={spec.get("method_contains")!r}, node_contains={spec.get("node_contains")!r}）'


def anchor_for_group(blocks, gk, last_b, is_choice_group=False):
    """返修 M5（r1）+ M4-r2：锚点要能直接喂给 block_insert.resolve_insert_anchor（要求
    title_contains 恰好命中 1 个题块）。末题标题不唯一时，r1 无条件改给 method_end，但本书的选择
    例题挂在节点最后一个主观考法名下、和主观组共享 (节点,考法)，method_end 会取组内“最后一块”，
    即选择区末题，把插入点错位到选择区之后（10 个兜底里错 3 个，详见返修回执与 probe_e2e_
    anchor_bykind.log）。改成：非选择题组、且组内 last_b 之后同组里还有选择例题时，改给
    before_block 定位到这些选择例题里文档序最先的一块（等价于“last_b 之后、选择区之前”），该
    标题不唯一时如实标 anchor_unique=false。选择题组与没有紧随选择例题的主观组，行为同 r1。
    返回 (anchor, anchor_unique, redirect_note)。"""
    title = last_b['title']
    if _title_hit_count(blocks, title) == 1:
        return _anchor_dict('after_block', title_contains=title), True, None
    method, node = gk[2] or '', gk[1] or ''
    if not is_choice_group:
        trailing_choice = sorted(
            (b for b in blocks if b['kind'] == 'choice' and b.get('node') == node
             and (b.get('method') or b.get('group') or '') == method
             and b['p_range'][0] > last_b['p_range'][0]),
            key=lambda b: b['p_range'][0])
        if trailing_choice:
            first_choice = trailing_choice[0]
            ftitle = first_choice['title']
            unique = _title_hit_count(blocks, ftitle) == 1
            note = (f'本组末题“{title}”标题在全书不唯一；本节点内紧随其后还有选择例题'
                    f'（{first_choice["id"]}），method_end 兜底会解析到选择区之后（错位），改用 '
                    f'before_block 定位到该选择例题之前，等价于“{title}”之后')
            return _anchor_dict('before_block', title_contains=ftitle), unique, note
    n_groups = _method_end_group_count(blocks, method, node) if method else 0
    return (_anchor_dict('method_end', method_contains=method or None, node_contains=node or None),
            n_groups == 1, None)


def _pick_template_block(blocks, group_block_idxs, top_idx):
    """返修 m2（r3，r1 M5 残留）：most_similar_block 的标题若在全书不唯一，模型照抄进
    block_insert 插入单的 template_block.title_contains 会因命中多块 Abort（生产候选里
    22/1029，其中第一候选 8 个）。同组内换一个标题唯一的块顶替（同一考法下的样板，教学结构本就
    类似）；同组也找不到标题唯一的块，如实标 template_unique=false，不假装唯一。"""
    top_b = blocks[top_idx]
    if _title_hit_count(blocks, top_b['title']) == 1:
        return top_b, True
    for i in group_block_idxs:
        b = blocks[i]
        if _title_hit_count(blocks, b['title']) == 1:
            return b, True
    return top_b, False


def candidate_detail(book, group, query_fields, indices, max_chars):
    blocks, doc = book['blocks'], book['doc']
    gk = group['group_key']
    top_idx = group['block_idxs'][0]
    last_idx = max(group['block_idxs'], key=lambda i: blocks[i]['p_range'][0])
    top_b, last_b = blocks[top_idx], blocks[last_idx]
    is_choice = top_b['kind'] == 'choice'
    terms = []
    for f in ('ask', 'material', 'rubric'):
        terms += indices[f].top_terms(query_fields.get(f, ''), top_idx, limit=4)
    slice_text, cut = truncate_slice(render_recs(top_b['_recs'][1:], doc['rels']), max_chars)
    anchor, anchor_unique, anchor_note = anchor_for_group(blocks, gk, last_b, is_choice)
    tmpl_b, tmpl_unique = _pick_template_block(blocks, group['block_idxs'], top_idx)
    return OrderedDict([
        ('part', gk[0]), ('h1', last_b.get('h1') or None), ('h2', last_b.get('h2') or None),
        ('node', gk[1]), ('method', gk[2] or None), ('label', group_label(gk, is_choice)),
        ('score', round(group['agg_score'], 4)), ('n_blocks_in_group', len(group['block_idxs'])),
        ('top_contrib_terms', [t for t in dict.fromkeys(terms) if t][:8]),
        ('most_similar_block', OrderedDict([
            ('id', top_b['id']), ('title', top_b['title']), ('key', top_b['key']), ('kind', top_b['kind']),
            ('h1', top_b.get('h1') or None), ('h2', top_b.get('h2') or None),
            ('p_range', top_b['p_range']), ('body_range', top_b.get('body_range'))])),
        ('template_block', OrderedDict([
            ('id', tmpl_b['id']), ('title', tmpl_b['title']), ('kind', tmpl_b['kind']),
            ('title_contains', tmpl_b['title']), ('template_unique', tmpl_unique)])),
        ('insert_after', OrderedDict([
            ('block_id', last_b['id']), ('block_title', last_b['title']), ('kind', last_b['kind']),
            ('p_range', last_b['p_range']), ('body_range', last_b.get('body_range')),
            ('position', '考法末尾'),
            ('anchor', anchor), ('anchor_unique', anchor_unique),
            ('anchor_redirect_note', anchor_note),  # 返修 M4-r2：改用 before_block 时说明原因
            # 兼容字段：旧版消费方可能只认 anchor_title_contains；反映 anchor 实际指向的标题（可能
            # 是 before_block 改指的选择例题，而不是 last_b 自己），method_end 没有标题时退回
            # last_b['title'] 仅供人读，不保证唯一。
            ('anchor_title_contains', _anchor_title_contains(anchor) or last_b['title']),
            ('note', INSERT_NOTE),
        ])),
        ('sample_slice', slice_text), ('sample_slice_truncated', cut),
    ])


def rank_for_query(qinfo, book, indices, params):
    """只算分与排序，不生成候选详情（原文切片等）；供 CLI 与评测共用，评测大批量跑时省掉渲染开销。"""
    blocks = book['blocks']
    exclude = matching_block_idxs(blocks, qinfo['base_key']) if qinfo.get('base_key') else set()
    kind_set = KIND_GROUPS['choice' if qinfo['kind'] == 'choice' else 'subjective']
    # method 索引的“文档”是考法名+考法说明；新题没有考法，用它自己的设问+材料去查，捕捉主题词面上的
    # 重合（例如新题材料提到“人民代表大会”，恰与某考法名/说明共享该词）——弱信号，权重本就比其它字段低。
    query_fields = {'material': qinfo['material'], 'ask': qinfo['ask'], 'rubric': qinfo['rubric'],
                     'method': (qinfo['ask'] + '\n' + qinfo['material']).strip()}
    combined, _ = score_blocks(query_fields, indices, len(blocks), params)
    ranked = aggregate_methods(blocks, combined, kind_set, exclude, params)
    return ranked, exclude, query_fields


def true_rank_of(ranked, true_group_keys):
    if not true_group_keys:
        return None
    for i, g in enumerate(ranked, 1):
        if g['group_key'] in true_group_keys:
            return i
    return None


def build_query_result(qinfo, book, indices, params, top_k, max_chars, guard_list, prof=None, bank_root=None):
    blocks = book['blocks']
    ranked, exclude, query_fields = rank_for_query(qinfo, book, indices, params)
    flags = []
    # 返修 M2-r2：跨模块守卫要看全部设问句（含未被 split_ask 切出的前置小问），逐句喂
    # stem_module_guard_hit；m9（r1）的“只查设问不查材料”仍然保留（ask_like_sentences 只挑
    # “像设问的句子”，材料里的普通提及不会入选）。stem_full 缺失时 material/ask 分开抽句、不拼接
    # （避免 material 尾句和 ask 首句连成跑合句，material 沾上 ask 的引导词被误判成设问）。
    ask_sent_pool = (ask_like_sentences(qinfo['stem_full']) if qinfo.get('stem_full')
                     else ask_like_sentences(qinfo.get('material') or '')
                     + ask_like_sentences(qinfo.get('ask') or ''))
    seen_guard = OrderedDict()
    for s in ask_sent_pool:
        hit = stem_module_guard_hit(s, guard_list)
        if hit and hit not in seen_guard:
            seen_guard[hit] = s
    for hit, s in seen_guard.items():
        snippet = s if len(s) <= 60 else s[:60] + '…'
        flags.append(f'设问含跨模块限定“{hit}”（命中句：{snippet}）：CANDIDATE 不作本册例题，最终由'
                     f'主代理裁定')
    if qinfo['kind'] != 'choice' and not qinfo['e1_present']:
        # 返修 m3（r2）：具名无 E1 例外卷（profile 的 sources.no_e1_exceptions）不算“按规则不收”，
        # 是“E3方向性，不拆E1”（SCOPE-E1）。
        if prof is not None and no_e1_exception_hit(prof, bank_root, qinfo.get('base_key')):
            flags.append('具名例外（sources.no_e1_exceptions）：本卷/本题已由用户认定为整卷无正式细则'
                         '例外，E3方向性、不拆E1——不算“按规则不收”，仍可候选，但教学内容不得使用未'
                         '经确认的固定分值，最终由主代理核 E3 依据后裁定')
        else:
            flags.append('主观题未找到正式评分细则（E1）：按规则候选“不收”，最终由主代理核 E1 后裁定')
            # 返修 M1-r3：第二信号（rubric_links.csv）与工具判定冲突时不静默，加提示交人工核对，
            # 不直接翻转结论（索引也可能过时）。
            if prof is not None and rubric_index_signal(bank_root, qinfo.get('base_key')):
                flags.append('注意：题库索引 indexes/rubric_links.csv 标记本题已匹配正式材料，但工具未在 '
                             'MD 正文找到判定为有效 E1 的节——可能是节名未覆盖或索引过时，请人工核对')
    if qinfo.get('kind_conflict'):
        flags.append(f'题型判定：{qinfo["kind_conflict"]}')
    if qinfo.get('directive_note'):  # 返修 m4（r2）
        flags.append(qinfo['directive_note'])
    # 返修 M6（r1）：题键已在本书落位时，rank_for_query 已把这些题块从候选池剔除（供评测剔重用）；
    # 生产 CLI/报告用法原来对此完全不提示，容易误当新题重复插入。这里显式加 flag 并退出 1。
    if exclude:
        ex_blocks = sorted((blocks[i] for i in exclude), key=lambda b: b['id'])
        desc = '、'.join(f"{b['id']}（{b.get('method') or b.get('group') or b.get('node') or '—'}）"
                        for b in ex_blocks[:5])
        more = f'等共 {len(ex_blocks)} 个题块' if len(ex_blocks) > 5 else ''
        flags.append(f'该题键已在本书落位：{desc}{more}——候选已排除这些题块，注意核对是否已经入书、'
                     f'避免重复插入')
    # 返修 m2（r1）：与全书零重合（BM25 各字段都没有命中词）时，原来仍按 dict 顺序给 3 个 0 分候选、
    # 退出 0，看起来像正常出了候选。加“无相似信号”flag，提醒这几个候选分数无意义、不能当真候选看。
    if ranked and all(g['agg_score'] <= 0 for g in ranked):
        flags.append('查询与全书候选考法均无相似信号（BM25 各字段零命中）：以下候选按内置顺序排列、'
                     '分数均为 0，不构成有效候选，需人工核对输入')
    candidates = [candidate_detail(book, g, query_fields, indices, max_chars) for g in ranked[:top_k]]
    # 返修 M2-r3：疑似重复检查不再只在 base_key 缺失时才跑（已知错号重卷这类“给的题键在书里查不到、
    # 但内容和书里另一个题键几乎一样”的情况，base_key 有值但 exclude 为空，原来整段跳过）；比对
    # 对象也从“聚合候选组第 1 名的截断切片”改成“全书每个未剔除题块的未截断正文”（find_suspected_
    # duplicate，见其 docstring）。exclude 非空时已有“已在本书落位”flag，不重复。
    if not exclude:
        dup = find_suspected_duplicate(qinfo, book, exclude)
        if dup:
            flags.append(f'疑似题库重复：本题与题块 {dup["block_id"]}（{dup["title"]}，题键 '
                         f'{dup["key"] or "未知"}）文字高度相似（3-gram包含度 {dup["ratio"]:.2f}）——'
                         f'请人工核对是否与已入书题目为同一张卷的重号/串题（如错号重卷），避免重复插入')
    has_truth = bool(qinfo.get('true_group_keys'))
    true_rank = true_rank_of(ranked, qinfo.get('true_group_keys')) if has_truth else None
    hit1 = (true_rank == 1) if has_truth else None
    hit3 = (true_rank is not None and true_rank <= 3) if has_truth else None
    return OrderedDict([
        ('source', qinfo['source']), ('source_path', qinfo.get('md_path')),
        ('source_sha256', qinfo.get('md_sha256')),
        ('base_key', qinfo.get('base_key')), ('subq', qinfo.get('subq')),
        ('kind', qinfo['kind']), ('kind_field_raw', qinfo.get('kind_field_raw')),
        ('kind_conflict', qinfo.get('kind_conflict')),
        ('ask_heuristic', qinfo.get('ask_heuristic', False)), ('e1_present', qinfo['e1_present']),
        ('flags', flags), ('excluded_block_ids', sorted(blocks[i]['id'] for i in exclude)),
        ('n_candidate_groups', len(ranked)), ('candidates', candidates),
        ('eval_true_rank', true_rank), ('eval_hit_at_1', hit1), ('eval_hit_at_3', hit3),
    ])


# ================================================================== CLI
def _load_params(path):
    """返修 m6（r2）：非法 JSON、文件不存在、字段类型不对原来都落到 main() 最外层 except Exception，
    报“内部错误：<英文异常原文>”（如 JSONDecodeError/TypeError 的原始信息）；退出码 2 本就对，
    但提示不是中文。这里改成校验清楚再转 InputError，中文说明具体是哪个字段。"""
    p = dict(DEFAULT_PARAMS)
    p['weights'] = dict(DEFAULT_PARAMS['weights'])
    if not path:
        return p
    if not Path(path).is_file():
        raise InputError(f'--params 文件不存在：{path}')
    try:
        ov = json.loads(Path(path).read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise InputError(f'--params 不是合法 JSON（{path}）：{e}')
    if not isinstance(ov, dict):
        raise InputError(f'--params 顶层必须是 JSON 对象（{path}），给的是 {type(ov).__name__}')
    # 返修 m4（r3）：原来只校验“是不是数字”，无意义取值（浮点 agg_top_k、负数 bm25_k1、越界
    # agg_mix/bm25_b、未知 weights 键）全部静默接受，agg_top_k=2.5 还会在切片处炸出英文“内部
    # 错误：slice indices must be integers…”。这里按字段各自的合法区间/类型校验，全部转中文
    # InputError（点名字段），不留静默接受、也不留英文报错。
    if 'weights' in ov:
        if not isinstance(ov['weights'], dict):
            raise InputError(f'--params.weights 必须是对象（{path}）')
        allowed_w = set(DEFAULT_PARAMS['weights'])
        for k, v in ov['weights'].items():
            if k not in allowed_w:
                raise InputError(f'--params.weights 含未知字段 {k!r}，只接受 {sorted(allowed_w)}（{path}）')
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                raise InputError(f'--params.weights.{k} 必须是数字，给的是 {type(v).__name__}（{path}）')
        p['weights'].update(ov['weights'])
    if 'agg_top_k' in ov:
        v = ov['agg_top_k']
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise InputError(f'--params.agg_top_k 必须是 >=1 的整数，给的是 {v!r}（{path}）')
        p['agg_top_k'] = v
    if 'agg_mix' in ov:
        v = ov['agg_mix']
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0 <= v <= 1):
            raise InputError(f'--params.agg_mix 必须在 [0,1] 区间，给的是 {v!r}（{path}）')
        p['agg_mix'] = v
    if 'bm25_k1' in ov:
        v = ov['bm25_k1']
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            raise InputError(f'--params.bm25_k1 必须是正数，给的是 {v!r}（{path}）')
        p['bm25_k1'] = v
    if 'bm25_b' in ov:
        v = ov['bm25_b']
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not (0 <= v <= 1):
            raise InputError(f'--params.bm25_b 必须在 [0,1] 区间，给的是 {v!r}（{path}）')
        p['bm25_b'] = v
    if 'ngram_sizes' in ov:
        ns = ov['ngram_sizes']
        if not (isinstance(ns, list) and ns
                and all(isinstance(x, int) and not isinstance(x, bool) and x >= 1 for x in ns)):
            raise InputError(f'--params.ngram_sizes 必须是非空正整数列表（元素>=1），给的是 {ns!r}（{path}）')
        p['ngram_sizes'] = ns
    return p


def _load_key_query(raw, bank_root):
    base, subq = parse_key_arg(raw)
    mdp = find_md_path(bank_root, base)
    if not mdp.is_file():
        raise InputError(f'题库没有这个题键的 MD：{base}（找的路径：{mdp}）')
    q = parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), raw)
    q['base_key'] = base
    q['subq'] = subq
    # 返修 M7：--key/--keys-file 走的是 parse_question_md 直接解析，原来没像 load_question_from_md
    # 那样带上题源 MD 的路径与 SHA，--report 的 inputs 里因此查不到新题来自哪份文件、内容是否变过。
    q['md_path'] = str(mdp.resolve())
    q['md_sha256'] = sha256_file(mdp)
    return q


def collect_queries(args, bank_root):
    queries = []
    for raw in (args.key or []):
        queries.append(_load_key_query(raw, bank_root))
    if args.keys_file:
        kf = Path(args.keys_file)
        if not kf.is_file():
            raise InputError(f'--keys-file 不存在：{kf}')
        # 返修 m4：utf-8-sig 而非 utf-8——原来遇到带 BOM 的题键清单，BOM 会粘在第一行第一个题键
        # 前面，让它匹配不上任何题库路径（报错文案里看不出来是 BOM 在作怪）。
        # 返修 m9（r3）：报错原来只给行内容（line!r），文件长、同一题键出现多次时看不出是哪一行；
        # 改用 enumerate 给出真实行号（1 起，含空行/注释行，和文本编辑器里看到的行号一致）。
        for lineno, raw_line in enumerate(kf.read_text(encoding='utf-8-sig').splitlines(), 1):
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            try:
                q = _load_key_query(line, bank_root)
            except InputError as e:
                raise InputError(f'{e}（来自 --keys-file 第 {lineno} 行：{line!r}）')
            queries.append(q)
    for path in (args.md or []):
        # 返修 M3-r2：base_key 现在由 load_question_from_md 自己按文件名/正文识别（找不到才是
        # None），不再无条件覆盖成 None——覆盖成 None 会让“已在本书落位”查重对 --md 完全失效。
        queries.append(load_question_from_md(path))
    for path in (args.text or []):
        queries.append(load_question_from_text(path, args.kind))
    if not queries:
        raise InputError('未给任何新题输入：至少给一个 --key / --keys-file / --md / --text')
    return queries


def format_md(results, book_title):
    """返修 m13：原版过简（没有样例切片、没有已剔除/已落位信息、没有锚点唯一性），模型写教学内容
    时还得回头翻 JSON。这版把这几项都带上，flags（含 M6 的“已落位”、m2 的“无相似信号”）已经在
    r['flags'] 里，照旧整段打出。"""
    out = [f'# 新题插入位置建议（{book_title}）', '']
    for r in results:
        out.append(f"## {r['source']}（{r['kind']}）")
        if r.get('kind_field_raw'):
            out.append(f"- 题库题型字段：{r['kind_field_raw']}")
        if r['flags']:
            for fl in r['flags']:
                out.append(f'- 注意：{fl}')
        if not r['candidates']:
            out.append('- 未找到候选考法（可能该题型在本册没有对应部分，或本书按此配置只识别到极少题块）')
        for i, c in enumerate(r['candidates'], 1):
            ins = c['insert_after']
            anchor_note = '锚点唯一' if ins['anchor_unique'] else '锚点不唯一，需按 anchor 里的 method_end 或人工收窄'
            out.append(f"{i}. **{c['label']}**（分 {c['score']}，组内 {c['n_blocks_in_group']} 题，"
                        f"一级 {c.get('h1') or '—'}／二级 {c.get('h2') or '—'}）")
            out.append(f"   - 最像题块：{c['most_similar_block']['title']}"
                        f"（{c['most_similar_block']['id']}，{c['most_similar_block']['kind']}，"
                        f"贡献词：{'、'.join(c['top_contrib_terms'][:5]) or '（无）'}）")
            tb = c.get('template_block')
            if tb:
                tb_note = '标题唯一，可用于 title_contains' if tb['template_unique'] else '标题仍不唯一，需人工收窄'
                out.append(f"   - 样板题块（template_block）：{tb['title']}（{tb['id']}，{tb_note}）")
            # 返修 m1（r3）：直接打印真实 anchor 结构，last_b 标题只作“插在其后”的说明，不再假装
            # 是能直接照抄进 title_contains 的锚点（method_end/before_block 时它本来就不唯一）。
            out.append(f"   - 插入点：{ins['position']}（紧随 {ins['block_title']}／{ins['block_id']} 之后）")
            out.append(f"     anchor：{_anchor_human(ins['anchor'])}（{anchor_note}）")
            slice_head = (c['sample_slice'] or '')[:200].replace('\n', ' ')
            out.append(f"   - 样例切片（截断到200字预览，完整见 sample_slice）：{slice_head}")
        out.append('')
    return '\n'.join(out)


class ZhArgumentParser(argparse.ArgumentParser):
    """返修 m4：argparse 默认 error() 只打印英文 usage/message，本工具其它地方都要求中文提示。
    退出码本就是 2（argparse.error 内部调用 self.exit(2, ...)），不用改，只在英文 usage 后面
    追加一行中文前缀，不吞掉原始英文细节（便于对照 argparse 自身的参数名拼写）。"""

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f'参数错误：{message}', file=sys.stderr)
        self.exit(2)


def build_arg_parser():
    ap = ZhArgumentParser(prog='placement_suggest.py', description=__doc__,
                           formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docx', required=True)
    ap.add_argument('--profile', required=True)
    ap.add_argument('--expect-sha', default=None, help='校验目标书 SHA256（可选）')
    ap.add_argument('--bank', default=None, help='题库根（默认 profile 的 sources.bank.root）')
    ap.add_argument('--key', action='append', default=[])
    ap.add_argument('--keys-file', default=None)
    ap.add_argument('--md', action='append', default=[])
    ap.add_argument('--text', action='append', default=[])
    ap.add_argument('--kind', choices=['subjective', 'choice'], default=None, help='--text 模式题型（识别不出时用它）')
    ap.add_argument('--top-k', type=int, default=3)
    ap.add_argument('--max-chars', type=int, default=800)
    ap.add_argument('--params', default=None, help='参数 JSON（weights/agg_top_k/agg_mix/…），覆盖内置默认值')
    ap.add_argument('--report', default=None, help='写 JSON 报告（受 guard_write 约束）')
    ap.add_argument('--format', choices=['json', 'md'], default='json')
    ap.add_argument('--out', default=None, help='--format md 的落盘路径（受 guard_write 约束）；缺省只打印终端')
    ap.add_argument('--debug', action='store_true')
    return ap


def _atomic_write_text(path, text):
    """临时文件 + os.replace：写入过程中出错不会留下半截文件，写成功后是一次原子改名。
    返修 m5（r2）：os.replace 本身失败时（如目标是另一个符号链接绕出的坏路径），原来不清理已经
    写出的 .tmp<pid> 文件；改成 write_text/os.replace 任一步出错都在 finally 里删掉这个临时文件
    （删不掉——例如它其实没写成功——就静默忽略，不掩盖原始异常）。"""
    path = Path(path)
    tmp = path.with_name(f'.{path.name}.tmp{os.getpid()}')
    try:
        tmp.write_text(text, encoding='utf-8')
        os.replace(str(tmp), str(path))
    except Exception:
        try:
            tmp.unlink()
        except OSError:
            pass
        raise


FLAG_CATEGORY_PREFIXES = [
    ('设问含跨模块', 'cross_module_guard'),
    ('具名例外（sources.no_e1_exceptions）', 'no_e1_exception'),  # 返修 m3（r2），须排在 no_e1 前面
    ('主观题未找到正式评分细则', 'no_e1'),
    ('注意：题库索引 indexes/rubric_links.csv 标记本题已匹配正式材料', 'e1_index_conflict'),  # M1-r3
    ('题型判定：', 'kind_conflict'),
    ('该题键已在本书落位', 'already_in_book'),
    ('查询与全书候选考法均无相似信号', 'zero_signal'),
    ('疑似题库重复', 'suspected_duplicate'),  # 返修 M3-r2
    ('题库读取指引点名的题面小节', 'stem_directive_missing'),  # 返修 m4（r2）
]


def _flag_category(fl):
    for prefix, cat in FLAG_CATEGORY_PREFIXES:
        if fl.startswith(prefix):
            return cat
    return 'other'


def run(args):
    # 返修 m3：--top-k/--max-chars 原来不校验，-1 会让 Python 的负数切片悄悄丢最后一个候选、0 给空
    # 候选、--max-chars 负数会从切片尾部倒着截；都当输入错误挡在最前面。
    if args.top_k < 1:
        raise InputError(f'--top-k 必须 >= 1（给的是 {args.top_k}）')
    if args.max_chars < 0:
        raise InputError(f'--max-chars 不能为负数（给的是 {args.max_chars}）')
    # 返修 m11：--out 只在 --format md 时落盘，json 模式下原来静默忽略；改成提示一句，不是错误
    # （不少人习惯不管什么格式都顺手带 --out，直接报错太苛刻）。
    if args.out and args.format != 'md':
        print('提示：--out 只在 --format md 时落盘；当前 --format json，本次 --out 不生效', file=sys.stderr)

    try:
        prof = load_profile(args.profile)
    except InputError:
        raise
    except Exception as e:
        # 返修 m4：profile 路径不存在/JSON 损坏，原先落到 main() 最外层的 except Exception，报成
        # “内部错误：[Errno 2] No such file…”。这类问题就是用户给错了 --profile，改判输入错误。
        raise InputError(f'--profile 加载失败（{args.profile}）：{type(e).__name__}: {e}')

    # 返修 M8：约定4“任一校验失败→整批中止、不留输出文件”。原实现先把 --format md 的 --out 写盘，
    # 再对 --report 跑 guard_write，后者失败（如落在受保护目录）时前者已经写出，留下半成品。这里把
    # 两个输出路径的 guard_write（纯校验，不写文件；也顺带让冻结册在这一步就“立即”拒绝，不用等装书、
    # 算候选跑完）都挪到装书与计算之前；真正落盘挪到全部算完之后，用 _atomic_write_text 原子写，
    # 且任一步写失败都清理已写出的另一个文件，不留半成品。
    out_path = dl.guard_write(Path(args.out), prof, inputs=[args.docx], kind='.md') \
        if (args.out and args.format == 'md') else None
    report_path = dl.guard_write(Path(args.report), prof, inputs=[args.docx], kind='.json') \
        if args.report else None

    if not Path(args.docx).is_file():
        raise InputError(f'--docx 文件不存在：{args.docx}')
    try:
        book = load_book(args.docx, prof, args.expect_sha)
    except InputError:
        raise
    except zipfile.BadZipFile:
        # 返修 m4：非 docx/zip 文件原先报“内部错误：File is not a zip file”（英文系统信息）。
        raise InputError(f'--docx 不是有效的 .docx（zip）文件：{args.docx}')
    except (KeyError, OSError) as e:
        raise InputError(f'--docx 读取失败（{args.docx}）：{type(e).__name__}: {e}')

    bank_root = args.bank or ((book['cfg'].bank or {}).get('root'))
    if (args.key or args.keys_file) and not bank_root:
        raise InputError('要用 --key/--keys-file 但既没给 --bank，profile 的 sources.bank.root 也解析不出题库根')
    queries = collect_queries(args, bank_root)
    for q in queries:
        # 返修 m10：真实考法组要和 rank_for_query 的剔重口径一致，都用 matching_block_idxs（同时
        # 核 keys_all），不能只比较主键——否则 B0737 这类“一块引两个题键”的块，按非主键查询时会被
        # rank_for_query 剔除，却因为这里只看主键而漏算进“真实考法”，评测口径两处不一致。
        q['true_group_keys'] = ({group_key_of(book['blocks'][i])
                                 for i in matching_block_idxs(book['blocks'], q['base_key'])}
                                 if q.get('base_key') else None)
    params = _load_params(args.params)
    method_intro = build_method_intro(book['doc'], book['heads'], method_desc_style_set(prof))
    fields_all = block_fields_all(book['blocks'], method_intro)
    indices = build_indices(fields_all, params['ngram_sizes'])
    guard_list = ((prof.get('sources') or {}).get('stem_module_guard')) or []
    results = [build_query_result(q, book, indices, params, args.top_k, args.max_chars, guard_list,
                                   prof=prof, bank_root=bank_root)
               for q in queries]
    any_flag = any(r['flags'] for r in results)

    text = None
    if args.format == 'md':
        text = format_md(results, prof.get('title') or prof.get('book_id'))
        print(text)
    else:
        print(json.dumps({'n_queries': len(results), 'any_flag': any_flag,
                          'summary': [{'source': r['source'], 'top': (r['candidates'][0]['label']
                                       if r['candidates'] else None), 'flags': r['flags']} for r in results]},
                          ensure_ascii=False, indent=1))

    rep_text = None
    if report_path is not None:
        # 返修 M7：原报告没有 summary，也没有每道新题的来源路径＋SHA（--key/--keys-file 解析出的
        # md_sha256 算了却被丢掉），--keys-file/--params 本身的路径＋SHA 也不记；约定7 明确要求这些。
        flag_counts = Counter(_flag_category(fl) for r in results for fl in r['flags'])
        summary = OrderedDict([
            ('n_queries', len(results)),
            ('n_with_flags', sum(1 for r in results if r['flags'])),
            ('flag_category_counts', dict(flag_counts)),
            ('by_query', [{'source': r['source'], 'kind': r['kind'],
                          'top_candidate': (r['candidates'][0]['label'] if r['candidates'] else None),
                          'has_flags': bool(r['flags'])} for r in results]),
        ])
        inputs = OrderedDict([
            ('docx', str(Path(args.docx).resolve())), ('docx_sha256', sha256_file(args.docx)),
            ('bank_root', str(bank_root) if bank_root else None),
            ('keys_file', ({'path': str(Path(args.keys_file).resolve()), 'sha256': sha256_file(args.keys_file)}
                           if args.keys_file else None)),
            ('params_file', ({'path': str(Path(args.params).resolve()), 'sha256': sha256_file(args.params)}
                             if args.params else None)),
            ('questions', [{'source': r['source'], 'base_key': r['base_key'], 'path': r['source_path'],
                            'sha256': r['source_sha256']} for r in results]),
        ])
        rep = OrderedDict([
            ('tool', TOOL), ('version', VERSION), ('mode', 'suggest'),
            ('generated_at', datetime.now(timezone.utc).isoformat()),
            ('summary', summary), ('inputs', inputs),
            # 返修 m11：约定7 要求 inputs（含 profile）都记路径＋SHA，原来只有 book_id/path/frozen。
            ('profile', {'book_id': prof.get('book_id'), 'path': prof.get('_profile_path'),
                        'sha256': (sha256_file(prof['_profile_path']) if prof.get('_profile_path') else None),
                        'frozen': bool(prof.get('frozen'))}),
            ('params', params), ('results', results),
        ])
        rep_text = json.dumps(rep, ensure_ascii=False, indent=1)

    # 返修 m5（r2）：原来每写完一个文件就立刻打印“已写”，第二个文件的 guard_write/落盘若失败，
    # 第一个文件已经被打印过“已写”、随后又被这里的异常处理删掉——终端上留下一句和实际结果矛盾的
    # 提示（“已写”之后其实被回滚了）。改成全部写完、确认都成功之后，一次性统一打印。
    written = []
    try:
        if out_path is not None:
            _atomic_write_text(out_path, text)
            written.append(('Markdown', out_path))
        if report_path is not None:
            _atomic_write_text(report_path, rep_text)
            written.append(('报告', report_path))
    except Exception:
        for _, w in written:
            try:
                Path(w).unlink()
            except OSError:
                pass
        raise
    for label, w in written:
        print(f'{label}已写：{w}', file=sys.stderr)
    return 1 if any_flag else 0


def main(argv=None):
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    try:
        return run(args)
    except InputError as e:
        print(f'输入/参数错误：{e}', file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 2
    except dl.GuardError as e:
        print(f'拒绝写出：{e}', file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 3
    except Exception as e:
        print(f'内部错误：{e}', file=sys.stderr)
        if args.debug:
            traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
