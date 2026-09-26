#!/usr/bin/env python3
"""连图带表插入整道题——写书侧通用工具之一（流程优化线 2026-09-25，云端候选）。

背景：apply_patch.py v1 只能改文字段落（replace_text/replace_paragraph/insert_after/insert_before/
delete_paragraph/set_format/set_keepnext），做不了"按样板题块复制样式、从原件带入图表、整道新题插入
书稿"——这正是新卷入书九步流程第 8 步的缺口。本工具补这一块：按插入单（baodian_insert_v1）把一道
新例题（标题＋材料＋图/表＋设问＋教学栏目）插到书稿里指定位置，自动重建图片关系与媒体成员，表格从
原件复制并套用样板格式。

复用（不另写一套判定/写出逻辑）：
    - docx_lib：open_docx/para_elements/para_text/para_sha/unchanged_paragraphs/guard_write；
      write_docx 只能替换已有成员，不能新增 word/media 成员，本工具另写 _write_with_new_media()
      薄封装写出函数，保持同等的原子写出 + 写后逐成员复核承诺（见该函数注释）。
    - batch_health（bh）：read_docx/Prof/walk/cfg/_word_lists/run_health——认题块、栏目、区位、
      词表全部转交 bh，本工具不重新实现。
    - apply_patch（ap）：_resolve_style_id（按 w:name 查 styleId）、_run_spans（按 run 顺序取纯
      文字，供本工具自己的 build_text_paragraph 判断标签/引导词边界）、_forbidden_hit 的同口径
      词表检查、zones_of（跑一遍 bh.walk 拿题块与区位，写后区位复核也用它）、Abort/RefuseWrite
      两个异常类（退出码语义与 apply_patch 完全一致）。_build_paragraph 只在 content 条目显式给了
      "runs"（作者自己按 run 分好格式）时原样复用；不给 runs 的 source/teaching/rubric 正文段改由
      本工具自己的 build_text_paragraph 构造（R2-B2 修复：_build_paragraph 的"整段套模板段 pPr/
      首个 run rPr"路径会把标签/引导词格式带进正文，见下文"角色→样式"一节）。这些都是 apply_patch
      模块级函数，按 import 复用；本工具不复制其实现。
    - block_index：只在写后复核阶段调用 build_index() 验证新题块被独立识别、media/tables 计数
      与插入单一致——不用它来定位插入点（它的段落计数含 mc:Fallback 分支，口径与 docx_lib/bh 不
      完全相同，定位一律用 bh.walk 对齐 d.paras 的下标空间，见下文"口径"）。
    - layout_prepare：--renumber 通过子进程调用（把它当作独立命令行工具串联，不导入其内部函数、
      不复制编号/考法题数逻辑）。

口径
    - 段落下标：全部使用 docx_lib.open_docx() 打开后 d.paras 的下标空间（与 bh.read_docx 的
      items[i] 一一对应，含表格单元格内段落，不含 mc:Fallback 分支——docx_lib 打开时已经用
      check_alignment() 证明这一点）。题块边界改用 apply_patch.zones_of()（内部即 bh.walk）
      现算，不信任 block_index 索引里的 p_range/body_range（block_index 用自己的段落计数，
      含 Fallback 分支，与 d.paras 下标空间不保证一致，只在写后复核里作为独立交叉验证使用）。
    - 图：本工具不从 PDF 原件裁图（那一步没有 fitz 版式判断，会裁错）；PDF 原件的图必须由调用方
      先另行裁出图片文件（比如 fitz 取页内嵌位图），再用 content[].role=="image"，"file":"…" 传入，
      本工具原样接受、标"需本地核图"。只有原件本身是 DOCX 时，本工具才会自己按 rId/序号/邻近文字
      去这份 DOCX 里取图（含表格内的图）。
    - 表：从原件 DOCX 复制 w:tbl 时，先按 (type, w:name) 在本书 word/styles.xml 里找同类型同名的
      样式改绑表级 tblStyle，找不到就删除（R2-B1 修复：旧版只按 styleId 是否在本书"存在"判断能
      不能保留引用，不同文档自动生成的 styleId 会撞号——同一个 id 在不同文档里可能是完全不同类型
      /名字的样式，真实原件实测三份全部撞号，被静默改绑到本书无关样式，如超链接变成别的段落样式
      的字符版本）；单元格段落/run 的 pPr/rPr 整体套样板表格表头行/表体行的格式（与 rows 数组生成
      表格同口径，见下），不再按 styleId 逐个判断保留或删除——这样比单纯清理引用更彻底：源表格里
      未经样式引用、直接写在段落/run 上的字体、字号、行距、缩进等直接格式（常见于不同学校原件，
      如楷体正文、超大行距）同样会被样板格式整体覆盖掉（R2-M4 修复）。表宽：改用样板表格的 tblW，
      列宽（tblGrid 的 gridCol，连同各单元格 tcW）按样板总宽等比缩放，不再"本表已有 tblW 就保留"
      （R2-M4：源表格保留自己的列宽会让 fixed 布局下的表格宽度超出版心）。也支持给 rows 数组直接
      生成简单表（套样板表格的列宽等分与单元格段落格式，样板题块没有表格时回退到全书第 1 个表格，
      在报告里写明）。
    - 角色→样式：content[].role 取值 "source"|"teaching"|"rubric"（对应书册配置 styles.source/
      teaching/rubric 三个样式名桶，如必修三 source=[题目材料,题目设问,题目选项]、
      teaching=[分析过程,答案落点,宝典正文]、rubric=[细则说明]）或 "image"/"table"（特殊角色，
      不落成普通文字段）。每个文字角色段的具体样式来自模板题块（anchor.template_block 指到的
      那个题块）里同角色桶的段落，按 content 文字的"标签形状"（_para_shape：'label' 整段就是
      "【…】"、'label_prefix' 标签+内容同段如"【题目】17．（8分）"、'stem' 以"结合/运用/根据/
      依据/针对"等设问引导词开头如"结合材料，运用……说明……"、'plain' 其余正文）挑同形状的候选，
      同形状里若不止一个再挑"格式最常见"的那个（_pick_by_shape/_pick_majority_format）——
      不是"doc 序第一个"：本书思维链条/答案落点的【标签】常与正文颜色不同（深蓝 vs 黑），
      "【题目】17．（8分）"这类"标签+编号同段"与真正的材料/设问正文也不是一回事，只按"是不是
      纯标签"这一粗二分会把标签/标题行的版式带进正文，见 R2-B1/R2-B2 两轮实测。候选段落一律
      排除表格单元格内的段落（R2-B2 修复：非表格文字角色不该从表格单元格段选模板，样板题块带
      表格时曾把设问段套成单元格的 pPr）。'stem' 这一形状专为区分"设问段"与"材料段"新增——本书
      同一个"题目材料"样式下，材料段大多不显式写字体（继承样式默认楷体），设问段几乎全部显式
      写宋体（style-spec.md："主观题材料正文中文Kaiti SC，设问……中文Songti SC"），若不分形状，
      "多数格式"会被材料段的数量优势带偏，把设问段的宋体丢成楷体（R2-B2 两个金标用例、三道
      真实新题实测都踩过）。给了 "like"（子串）就在模板题块内按它定位到唯一一段，用它的
      pPr/首个 run rPr（不再按形状筛选——作者显式点名，信任这次选择）。teaching 桶下同时有
      "分析过程"与"答案落点"两种具体样式时，不给 like 默认按标签形状匹配，要落到"答案落点"
      须显式 like:"答案落点"；模板题块内该角色桶一段都没有，就回退到全书该角色桶第一次出现的
      同形状段落（同样排除表格内段落），在报告 fallbacks 里写明。image/table 角色同理：模板题块
      自己的图/表优先，没有就回退全书第一个图/表，报告写明。也支持显式 "style":"样式名" 整段指定
      具体样式（此时限定在该角色桶内按标签形状挑选，不是忽略角色桶——R2-M1 修复：style 覆盖若能
      跳出角色桶，学生正文词表的豁免口径会被绕过，见下文"题面零改写"一节），供角色桶按 like/
      默认匹配不到位时兜底。role=="source" 的段落还支持显式 "kind":"stem"（设问）或 "material"
      （材料），跳过下面这条"标签形状"里 stem/plain 两态的自动判断（R3-B1 新增，见 _para_shape_
      ctx/_stem_position_index）——本书约 21% 的真实设问不以"结合/运用/根据/依据"等引导词开头
      （引语、"有人说……"、"要求：……"、"（2）从……谈谈"这类写法），单靠文字判据分不出来，默认
      改用"这条 insert 的 content 里最后一个 source 项多半是设问"这一位置信号补（全书回归验证
      452/453 用这条位置信号就够，不必每次都显式给 kind）；只有一条 insert 里连着给了两个都像
      "设问收尾"的 source 段（比如同时给一段真设问和一段对照句）这类少见情形，位置信号只认最后
      一个，才需要显式 kind 指出另一个。
    - 每个 content 条目落成书稿里的**一段**（image/table 各落成一段/一个表格结构），条目顺序即
      正文顺序；标签是否与正文同段完全由插入单作者决定（例如"【题目】17．（8分）"整段一起给，
      或"【思维链条】"单独一段再接内容段——本书两种写法都在用，见 B0005：题目标签与首段材料
      同段，思维链条/答案落点标签各自单独成段）。
    - 题面零改写：source 角色段落的文字须逐字取自原件或插入单本身（不改写），insert 条目须给
      "source_zone":"restore"|"approved_edit" 与非空 "reason"；词表豁免只在 role=="source" 且
      source_zone=="restore" 时对该条目生效（与 apply_patch 同口径：教学/细则区永不豁免，
      approved_edit 也不豁免）；未豁免的 content 文字统一过 bh._word_lists 词表（工程标签、
      forbidden_words_common/book、forbidden_word_groups），命中即整批中止。显式 "style" 覆盖
      （见上文"角色→样式"）限定在该角色自己的样式桶内，不能借 style 跳到别的角色桶去（R2-M1
      修复：role=="source" 配合 style="分析过程"这类教学桶样式曾能绕过豁免口径本身没问题——
      豁免只看 role/source_zone，被绕过的是"角色桶"这道门，效果是把工程词写系进了教学栏目而不
      触发中止）。apply 写出后还会用重新打开的输出文件重新跑一遍 bh.walk，核对每个 restore 豁免
      段（含标题段）的真实区位确实落在 source/title 区；没落在的话对它的最终文字补跑一遍词表，
      命中即删输出、整批中止（与 apply_patch 的写后区位复核同一套逻辑，见 verify_output）。

插入单格式（baodian_insert_v1，写在这里就是正式说明）：
{"schema": "baodian_insert_v1", "book": "bixiu3", "parent_docx_sha256": "…",
 "approved_by": "claude:… | codex:… | user", "approval_ref": "…",
 "inserts": [{"id": "I001",
   "anchor": {"after_block": {"title_contains": "…"}}
           | {"before_block": {"title_contains": "…"}}
           | {"method_end": {"method_contains": "…", "node_contains": "…可选"}},
   "template_block": {"title_contains": "…"},
   "title": "例题 N　2026××一模第17题",
   "source_zone": "restore" | "approved_edit", "reason": "…",
   "content": [
     {"role": "source", "text": "【题目】17．（8分）"},
     {"role": "source", "text": "材料第一段……"},
     {"role": "image",
      "from": {"docx": "原件.docx", "rid": "rId14"} 或 {"docx": "原件.docx", "index": 1}
             或 {"docx": "原件.docx", "near_text": "…邻近文字…"},
      "width_cm": 可选} 或 {"role": "image", "file": "图片文件路径", "width_cm": 可选},
     {"role": "table",
      "from": {"docx": "原件.docx", "table_index": 1} 或 {"docx": "原件.docx", "contains": "…单元格文字…"}}
      或 {"role": "table", "rows": [["表头1", "表头2"], ["单元格", "单元格"]]},
     {"role": "source", "text": "结合材料，运用……说明……"},
     {"role": "source", "text": "……（不以设问引导词开头、也不是本条 insert 里最后一个 source 项的"
      "另一句真实设问）", "kind": "stem"},
     {"role": "teaching", "like": "思维链条", "text": "【思维链条】"},
     {"role": "teaching", "like": "思维链条", "text": "……"},
     {"role": "teaching", "like": "答案落点", "runs": [{"text": "④……", "bold": true}]},
     {"role": "rubric", "text": "【细则说明】 ……"}
   ]}
 ]}

用法
    block_insert.py check --docx 父稿.docx --insert i.json [--profile bixiu3] [--report r.json]
    block_insert.py apply --docx 父稿.docx --insert i.json --out 候选.docx
                   [--profile bixiu3] [--report r.json] [--health] [--renumber] [--render-check]

退出码（同共同约定第 6 条）：0 成功/无待办；1 check 有待处理的合法插入（尚未插入）、写后体检新增
FAIL、--renumber 未成功、--render-check 转换失败（云端渲染引擎粗查，不阻断写出）、或 --health 本身
执行异常（R3-m9 修复：插入已写出且写后复核已通过，--health 这一步没跑成不等于"整批中止"，不删
已写出的输出，见该处注释）；2 输入/配置
错误、整批中止（父稿 SHA 不符、锚点 0/多命中、模板题块/角色/图/表找不到、图片损坏、词表命中、写后
postcondition 不通过——含新题块未被 block_index 认成恰好 1 个、media/tables 计数不符、栏目缺失
（R2-M2 修复：block_index 的 missing 字段原先只写报告不中止，现改为硬失败）、restore 豁免段写后
未落在 source/title 区且命中词表）；3 拒绝写出（守卫、冻结册、写权）。异常一律转中文提示，不打印
traceback（--debug 打开）。

不做教学判断：本工具只机械落地插入单里已经写好的文字/图/表，不判题肢对错、不判材料是否该收、不判
插入位置是否教学合理——这些仍由主代理/人工在插入单里定好，工具只负责"能不能唯一、安全地落到
DOCX 上"。

精简：本工具目标 ≤1200 行（设计稿允许的上限，图表插入本身比纯文字补丁复杂得多）；不复制
batch_health/block_index 的题块判定逻辑，不复制 apply_patch 的段落构造/词表逻辑（按 import 复用）。
本轮（返修 r3）为堵 1 个 blocker + 3 个 major：设问形状识别改成"文字判据 + 位置信号"两层
（_para_shape_ctx/_stem_position_index，全书 self-template 回归 453/453 不再变字体，R3-B1）；
表格单元格格式套用改成按列取样板对应格式并识别样板有没有真正的表头（_template_row_fmt/
_template_header_distinct，金标 T2_tbl 差异从 25 处回落到 4 处，R3-M1）；覆盖格式时保留下划线/
上下标/着重号/删除线等语义 run 属性（R3-M3）；T4b 改成用哲学书真实带图题块的真实内容写入、断言
写出成功+block_index 认块完整+media_match，另加 --renumber 链路（R3-M2）。顺手修了多条 minor：
_SHAPE_PREF 的 label/label_prefix 退化顺序、嵌套表格 sanitize/reformat、浮动表 tblpPr 剥离、
样板 tblW 为 pct/auto 时的换算、width_cm 非正值校验、fitz 弃用警告改 import pymupdf、插入单
类型错误改中文提示、--health 异常不再吞掉输出、--render-check 提示拼接、wp14:anchorId/editId
重分配。行数从 2364 涨到本文件当前行数——都是实打实的新校验/新逻辑（见各处 R3- 前缀注释），
没有为了凑行数删必要的注释或校验，已在回执 known_limits 里说明。

已知限制（详见返修回执 known_limits）：顶层 VML 老式图（w:pict）无法定位；完全同名的题块不能作
锚点/样板（设计边界，不修）；--render-check 在云端只能做"能否转出非空 PDF"的粗查；设问位置信号
按"块内/插入单 content 里最后一个 source 项"判断，全书仍有 1 处孤例（一句本身读起来像设问、但
书里格式是楷体的"结合材料，综合运用所学……"，与另一句"要求：……"同块，见 R3-B1 回执）判不准，
可用插入单新增的 content[].kind:"stem"/"material" 字段显式指定；块内退化匹配到 'plain' 形状时，
如果块内唯一候选恰好是个格式异常段（如表格上方全段加粗的图注），仍会带出这份异常格式（R3-m1
部分修复，全书 label_prefix 形状混杂"块开场标题"与"材料内子标签"两种角色，doc-wide 兜底选不出
干净的"材料子标签"专属样本，需要更大改动才能分开，本轮未做）。
"""
import sys
sys.dont_write_bytecode = True  # 在 import 任何 SK 模块之前——不在 Skill 母版里留 __pycache__

import argparse
import copy
import json
import os
import re
import tempfile
import traceback
import zipfile
from pathlib import Path

from lxml import etree

# ------------------------------------------------------------------ 定位 SK（按共同约定第 1 条）
_HERE = Path(__file__).resolve().parent
if (_HERE / 'docx_lib.py').exists():
    _SK = _HERE
elif os.environ.get('BAODIAN_SKILL_SCRIPTS'):
    _SK = Path(os.environ['BAODIAN_SKILL_SCRIPTS']).expanduser().resolve()
else:
    _SK = None
    for _p in _HERE.parents:
        _cand = _p / '.claude' / 'skills' / 'beijing-gaokao-politics' / 'scripts'
        if _cand.exists():
            _SK = _cand
            break
    if _SK is None:
        raise SystemExit('找不到 Skill scripts 目录（docx_lib.py 同目录 / BAODIAN_SKILL_SCRIPTS / 向上找 .claude/skills/…/scripts）')
sys.path.insert(0, str(_SK))

import batch_health as bh          # noqa: E402
import docx_lib as dl              # noqa: E402
import block_index as bidx         # noqa: E402
import apply_patch as ap           # noqa: E402
from profile_lib import load_profile, detect_profile  # noqa: E402

TOOL_VERSION = '1.0.0'
W = bh.W
MC = bh.MC
A_NS = '{http://schemas.openxmlformats.org/drawingml/2006/main}'
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
WP_NS = '{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
PIC_NS = '{http://schemas.openxmlformats.org/drawingml/2006/picture}'
PKG_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'
CT_NS = '{http://schemas.openxmlformats.org/package/2006/content-types}'
VML_NS = '{urn:schemas-microsoft-com:vml}'   # v:imagedata（表格内老式 VML 图片），见 B2 修复
WP14_NS = '{http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing}'  # wp14:anchorId/editId，R3-m11 修复
REL_IMAGE_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/image'
REL_HYPERLINK_TYPE = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink'
CONTENT_TYPES_PATH = '[Content_Types].xml'
RELS_PATH = 'word/_rels/document.xml.rels'
EXT_CONTENT_TYPE = {
    'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg', 'gif': 'image/gif',
    'bmp': 'image/bmp', 'tif': 'image/tiff', 'tiff': 'image/tiff', 'wmf': 'image/x-wmf',
    'emf': 'image/x-emf', 'svg': 'image/svg+xml',
}
DEFAULT_TABLE_WIDTH_TWIPS = 9026   # 无样板表格可套用时的兜底总宽（见 B3 现有表格实测宽度量级）
DEFAULT_MAX_IMG_EMU = 5000000      # 无样板图片可套用时的兜底最大宽（约 13.9cm）
EMU_PER_CM = 360000

Abort = ap.Abort
RefuseWrite = ap.RefuseWrite
_UNSET = object()  # lxml Element 的 __bool__ 按子节点数判真假，不能用 `x or 默认值` 判"没算过"，
                   # 用这个哨兵对象区分"还没求值"与"求值结果是 None"（求出的模板元素本身可能是空段）


# ------------------------------------------------------------------ profile / 基础
def _load_prof(args, unit):
    # m12 修复：--profile 未给时原先会退回插入单 unit['book']（一个名字，如"bixiu3"），
    # profile_lib.load_profile 按名字解析走的是 Skill 母版自己的 profiles/<name>.json（指向本机
    # Mac 路径），不是云端这份 profiles_cloud/ 副本——云端探针证实这条路径下 guard_write 会认不出
    # 仓库根，书稿与原材料目录因此不受保护。main() 里已把 apply 子命令的 --profile 设成 argparse
    # required，这里的 Abort 是给"以后有人从代码直接调 cmd_apply/cmd_check、绕过了 argparse"的
    # 第二道防线。
    name = getattr(args, 'profile', None) or (unit or {}).get('book')
    if not name:
        raise Abort('请用 --profile 指定书册配置（名字或配置文件路径；云端必须显式传入 '
                    'profiles_cloud/ 下的配置，不能省略）')
    try:
        prof = load_profile(name)
    except FileNotFoundError:
        # R2-m6 修复：profile_lib.load_profile 对不存在的配置名直接 Path.read_text()，抛的是英文
        # FileNotFoundError（"[Errno 2] No such file or directory: …"）——profile_lib 是 Skill
        # 模块，不能改，这里在调用点接住转成中文提示。
        raise Abort(f'书册配置不存在："{name}"（--profile 后跟配置名或配置文件路径）')
    except json.JSONDecodeError as e:
        raise Abort(f'书册配置不是合法 JSON（第 {e.lineno} 行第 {e.colno} 列）：{name}')
    root = (prof.get('paths') or {}).get('root')
    if root and not Path(root).expanduser().exists():
        raise Abort(f'书册配置 paths.root 在本环境不存在：{root}（本环境须用指向本仓库根的配置，'
                    f'云端见 profiles_cloud/）')
    # R2-m9 修复：插入单 book 字段原先从不与实际生效的 --profile 核对——两者不一致时，工具仍然
    # 按 --profile 的样式/词表/守卫工作，却在报告里留一个跟实际书册对不上的 book 字段，容易被
    # 误当成"确实按这本书处理"的凭据。
    book_field = (unit or {}).get('book')
    if book_field and prof.get('book_id') and book_field != prof.get('book_id'):
        raise Abort(f'插入单 book 字段（{book_field}）与 --profile 实际书册（{prof.get("book_id")}）'
                    f'不一致')
    return prof


def sha256_bytes(b):
    return dl.sha256_bytes(b)


# ------------------------------------------------------------------ 顶层结构遍历（与 docx_lib.para_elements
# 同一套 tag 派发：w:sdt/customXml/smartTag 透传、mc:AlternateContent 只取 Choice），供在“body 直接子节点”
# 层面定位插入锚点（addnext/addprevious 必须挂在 body 的直接子节点上），以及按 bh.read_docx 同样的口径
# 枚举顶层表格（表格编号与 d.items[i]['tbl'] 对齐，嵌套表格不单独计数，与 bh.read_docx 完全同口径）。
def _top_level_anchor(body, el):
    node = el
    while node.getparent() is not None and node.getparent() is not body:
        node = node.getparent()
    return node


def _top_tables(body):
    out = []

    def rec(el):
        tag = el.tag
        if tag == W + 'tbl':
            out.append(el)
        elif tag in (W + 'sdt', W + 'sdtContent', W + 'customXml', W + 'smartTag'):
            for ch in el:
                rec(ch)
        elif tag == MC + 'AlternateContent':
            ch = el.find(MC + 'Choice')
            for x in (ch if ch is not None else []):
                rec(x)
    for el in body:
        rec(el)
    return out


def block_extent_end(b):
    """块在 d.paras 下标空间里的最后一段（含标题；块体为空时就是标题本身）。"""
    idxs = [b['title_i']] + list(b.get('paras') or [])
    return max(idxs)


# ------------------------------------------------------------------ 角色→样式桶→模板段落
def _style_ids_for_bucket(prof, styles_obj, bucket):
    names = set(prof.get('styles', {}).get(bucket, []) or [])
    return {sid for sid, n in (styles_obj.name or {}).items() if n in names}


def _para_style_id(styles_obj, p):
    ps = p.find(f'{W}pPr/{W}pStyle')
    return ps.get(W + 'val') if ps is not None else styles_obj.default_pstyle


_LABEL_ONLY_RX = re.compile(r'^【[^】]{1,30}】$')
_INLINE_LABEL_RX = re.compile(r'^(【[^】]{1,30}】[ 　]?)(.+)$', re.S)
# 设问段引导词（R2-B2 修复）：本书主观题设问几乎全部以这几个动词开头（可带前置编号，如
# "（1）结合材料……""运用所学……"），与材料段（叙述性文字，极少以这些词起句）在文档惯例上
# 是两种不同的段落，但样式桶（都在 styles.source）与旧的"标签/非标签"二分都分不出来——同一个
# "题目材料"样式下，材料段大多不显式写字体（继承样式默认楷体），设问段几乎全部显式写宋体
# （style-spec.md 第69条），"多数格式"选模板时材料段数量占优，会把设问段的宋体丢成楷体。
_STEM_LEAD_RX = re.compile(r'^[（(]?\d*[）)]?\s*(结合|运用|根据|依据|请结合|请运用|请根据|综合运用)')
# 题号+分值单独成段（如"21．（10分）"），没有【】也没有设问引导词，但在本书里就是设问区的题头，
# 与"【题目】17．（8分）"这类带括号标签的题头是同一件事的两种写法（stem_plain_list.txt #1010）。
_SCORE_HEADER_RX = re.compile(r'^\d+[.．]\s*[（(]\s*\d+\s*分\s*[）)]\s*$')
# R3-B1 修复（反向误判两处）："针对"整体从引导词表里去掉——全书实测：以"针对"开头的 source 段
# 全部 2 处都是材料收尾叙述句（"针对李某一次性赔偿确有困难……法官提出了……方案"），全书没有一个
# 真正的设问以"针对"开头，留着它只会误判、不会多认出任何真设问（见回执 tests：stem_leadword_
# probe）。"运用《…》…知识，完成下列任务。"这类"多个小题共用的开场白"也会被"运用"误判——它本身
# 不是一条完整设问，后面还跟着独立编号的分题——用 _STEM_PREAMBLE_RX 排除这一种收尾方式（全书
# 实测：全部 5 处都是这种共用开场白，没有一个真设问以"完成下列任务/完成以下任务"收尾）。
_STEM_PREAMBLE_RX = re.compile(r'完成(下列|以下)(任务|问题)[。.．]?\s*$')
# R3-B1 修复：开头引导词只覆盖了本书设问的一部分写法（约79%）——北京卷大量设问以引语/背景句开头
# （"……"结合材料……、有人说……、要求：……、（2）从……谈谈……、以……为例……），本身的开头字面
# 认不出"这是设问"。审查者与本轮返修都先试过"全段任意位置命中关键词即认为是设问"这条路
# （_STEM_CONTAIN_RX），穷举"结合材料/运用…知识/谈谈/要求：/如何…？"等关键词后，全书 94 个漏判
# 里能靠关键词补上的确实多，但代价是把"阅读上述材料……运用《政治与法治》知识，写一篇 200 字左右
# 的短文"这类整段仍是材料叙述、只是句中带了"运用…知识"字样的段落也错判成设问，反而在 8 个既有
# 反向误判之外新增 25 处（本书同一道题里"材料收尾句"与"真正设问"两段一旦都被判成 stem，多数格式
# 按文档序取先出现的一个，恰好是材料收尾句，把真正设问也带偏），已实测并放弃这条路（见回执
# tests：stem_contain_regression）。改为只留最精确的两条文字判据（开头引导词、独立题号题头），
# 剩下的靠位置信号（_stem_position_index/_para_shape_ctx）补——本书结构里"材料在前、设问在后"
# 几乎是硬规律，位置信号本身已经把 94 个漏判里的 93 个补上（全书 self-template 回归实测），比
# 关键词穷举更准、也不会引入新的假阳性。


def _is_label_only(text):
    return bool(_LABEL_ONLY_RX.match((text or '').strip()))


def _para_shape(text):
    """段落"标签形状"四态（B1/R2-B2/R3-B1 三轮修复：最初只有"是否纯标签"二态，把"标签+内容同段"
    错判成可以当正文模板——必修三"【题目】17．（8分）"这一段整段就是这个形状，纯标签正则
    ('^【…】$') 判它是"非纯标签"，于是被旧版 _pick_by_label_shape 当成正文候选，把标签专属的
    加粗深蓝带进后面所有材料/设问正文段。四态：
      'label'        —— 整段就是【…】（比如单独一行的"【思维链条】"）。
      'label_prefix' —— 以【…】开头、后面还有内容（比如"【题目】17．（8分）"、"【细则说明】 ……"）。
      'stem'         —— 设问段：以"结合/运用/根据/依据"等引导词开头且不是共用开场白
                        （_STEM_LEAD_RX 且不命中 _STEM_PREAMBLE_RX，R3-B1 修复：去掉"针对"、排除
                        "……完成下列任务"这类开场白，见上方两个正则的注释），或是独立成段的
                        "题号．（N分）"题头（_SCORE_HEADER_RX，R3-B1 新增）。
      'plain'        —— 其余正文（比如 B0005 第150段材料）。仅凭文字判不出来的"设问段用引语/背景
                        句开头，不带这些引导词"这一大类残留情形（全书约 21%），不靠正则硬穷举
                        （穷举关键词反而会把材料收尾句误判成设问，见上），改由位置信号补
                        （_stem_position_index/_para_shape_ctx）。"""
    t = (text or '').strip()
    if _LABEL_ONLY_RX.match(t):
        return 'label'
    if _INLINE_LABEL_RX.match(t):
        return 'label_prefix'
    if _SCORE_HEADER_RX.match(t):
        return 'stem'
    if _STEM_LEAD_RX.match(t) and not _STEM_PREAMBLE_RX.search(t):
        return 'stem'
    return 'plain'


def _para_shape_ctx(text, is_stem_position):
    """R3-B1 修复：在纯文字判据（_para_shape）之上叠加一层位置信号——本书主观题的段落顺序几乎
    总是"材料在前、设问在后"，材料段数量上远多于设问段，"结合材料"这类关键词穷举得再多也难免
    有漏网（审查 r3 实测穷举关键词后仍剩 1 个纯题号题头，且以后书里出现全新写法的设问一样会漏）。
    调用方按"块内/插入单 content 里最后一个 source 角色段"算出 is_stem_position；只在文字判据判
    成 'plain' 时才把它升级成 'stem'——'label'/'label_prefix'/文字判据已经认定的 'stem' 都不受
    位置信号影响（不会把最后一段材料如果恰好是"【裁判结果】…"这类内联标签强行说成设问）。"""
    shape = _para_shape(text)
    return 'stem' if (shape == 'plain' and is_stem_position) else shape


_SHAPE_PREF = {
    'label': ('label', 'label_prefix', 'plain', 'stem'),
    'label_prefix': ('label_prefix', 'label', 'plain', 'stem'),
    'stem': ('stem', 'plain', 'label_prefix', 'label'),
    'plain': ('plain', 'stem', 'label_prefix', 'label'),
}
# R3-B1 修复：content[].kind（可选，见 plan_inserts）——插入单作者显式指定"这段是设问还是材料"，
# 跳过文字/位置的自动判断。只开放 stem/material 两个值，与 _para_shape 的四态里唯二"需要判断"的
# 两态对应（label/label_prefix 由【…】结构本身决定，从来不需要人工指定）。
_KIND_TO_SHAPE = {'stem': 'stem', 'material': 'plain'}


def _pick_by_shape(d, idxs, want_shape, stem_pos=frozenset()):
    """按 _para_shape_ctx 的四态在候选段落里挑一个：想要的形状优先，找不到按 _SHAPE_PREF 顺序退而
    求其次——不管走 style_override 还是角色桶默认匹配，都按这一个规则挑，不重复实现两套判断（这一
    函数只处理"标签形状"这一件事，具体样式/角色桶是否匹配、是否排除表格内段落由调用方筛过 idxs 后
    再传进来）。同一形状里不止一个候选时，不取文档序第一个，取"格式最常见"的那个（_pick_majority_
    format）——真实数据里踩过：B0003 表格上方"2024年国务院《政府工作报告》的形成过程"是整句加粗的
    图注，样式桶（题目材料）与形状（plain）都跟表格下方的设问段一样，文档序还排在设问段前面；若只
    取文档序第一个，会把图注的加粗格式当模板套进设问段。同一角色桶+形状里，真正的正文段（表格单
    元格、设问）在数量上远多于这类零星图注/说明行，"多数格式"能自然避开这类离群格式。stem_pos
    （R3-B1 新增）：位置信号命中的段号集合，穿透传给 _para_shape_ctx，见该函数与 _stem_position_
    index。"""
    shapes = {i: _para_shape_ctx(dl.para_text(d.paras[i]), i in stem_pos) for i in idxs}
    for want in _SHAPE_PREF[want_shape]:
        pool = [i for i in idxs if shapes[i] == want]
        if pool:
            # R3-B1 修复：'stem' 形状的多数格式打平时，取块内位置最靠后的一个，不取文档序第一个
            # （见 _pick_majority_format 的 prefer_last 参数说明——"材料在前、设问在后"几乎是本书
            # 硬规律，"结合/运用/针对"这几个引导词偶尔会被材料收尾句借用，一旦借用恰好排在真正
            # 设问之前，打平取先出现的一个会把材料收尾句的格式误当设问格式套出去，真正设问反而被
            # 带偏，见回执 tests：stem_tiebreak）。其余形状不受影响，仍取文档序最靠前的一个。
            return _pick_majority_format(d, pool, prefer_last=(want == 'stem'))
    return None


def _pick_majority_format(d, idxs, prefer_last=False):
    """idxs（同一形状的候选段落下标，至少 1 个）里"格式最常见"的一个：每段先取自己的 _dominant_rpr
    签名，签名出现次数最多的那一组获胜。打平（不止一种格式并列最多）时默认取组内文档序最靠前的
    （决定性、可复现）；prefer_last=True（R3-B1 新增，只用于 'stem' 形状，见 _pick_by_shape）时取
    组内文档序最靠后的——本书"材料在前、设问在后"的位置规律比"先出现"这一默认约定更能反映哪一个
    才是真正的设问格式，见 _pick_by_shape 调用处注释。"""
    if len(idxs) == 1:
        return idxs[0]
    sigs = [_rpr_sig(_dominant_rpr(d.paras[i])) for i in idxs]
    counts = {}
    for s in sigs:
        counts[s] = counts.get(s, 0) + 1
    best = max(counts.values())
    ordered = list(zip(idxs, sigs))
    if prefer_last:
        ordered = list(reversed(ordered))
    for i, s in ordered:
        if counts[s] == best:
            return i
    return idxs[0]


def _stem_position_index(d, styles_obj, prof, blocks):
    """R3-B1 修复：全书按块预算一遍"位置信号"——每个块里最后一个 source 角色、非表格、非空、且
    当前按纯文字判据（_para_shape）仍是 'plain' 形状的段落，如果这个块不像选择题（块内没有
    "A．/B．/……"这类选项段——本书选择题的"源"样式段多是选项列表，最后一段不代表"设问"，位置
    信号在这类块里不成立），就把它计入结果集合；find_role_template/_pick_by_shape 用
    _para_shape_ctx 据此把这一段的形状从 'plain' 升级成 'stem'。已经被文字判据（含 R3-B1 新增的
    _STEM_CONTAIN_RX/_SCORE_HEADER_RX）认出 'stem'/'label'/'label_prefix' 的段落不受影响。
    对全书 453 个主观题设问的实测：单靠文字判据仍有 94 个漏判成 'plain'（穷举关键词后剩 1 个），
    全部是"块内最后一个 source 段"；本函数与文字判据合起来能把 452/453 纠正过来，剩下 1 个
    （题号单独一行、且后面还跟另一段真正的设问，不是"最后一段"）已改由 _SCORE_HEADER_RX 单独覆盖
    （见回执 tests：stem_position 全书回归）。"""
    src_ids = _style_ids_for_bucket(prof, styles_obj, 'source')
    out = set()
    for b in blocks:
        idxs = [i for i in (b.get('paras') or [])
                if not d.items[i].get('tbl') and _para_style_id(styles_obj, d.paras[i]) in src_ids
                and dl.para_text(d.paras[i]).strip()]
        if not idxs:
            continue
        if any(re.match(r'^[A-D][.．]', dl.para_text(d.paras[i]).strip()) for i in idxs):
            continue
        last_i = max(idxs)
        if _para_shape(dl.para_text(d.paras[last_i])) == 'plain':
            out.add(last_i)
    return out


def find_role_template(d, styles_obj, prof, block, role, like, style_override, content_shape, fallbacks,
                        exclude_idx=None, stem_pos=frozenset()):
    """定位模板段（供 build_text_paragraph 取 pPr/rPr）。role 为 source/teaching/rubric。返回
    (模板段元素, styleId, 模板段的位置感知形状)——第三项供调用方与新内容自己的形状比较
    （build_text_paragraph 的 same_shape 判断，R3-B1 修复：两边必须用同一套位置感知形状比，不能
    一边升级一边不升级，否则"块内自身作样板"这类本该 same_shape=True 的情形会被错判成 False，
    多丢一次 keepNext/firstLine）。

    content_shape（R3-B1 修复，原参数名 content_text）：调用方须先用 _para_shape_ctx（结合插入单
    自己 content 列表里的位置信号，见 plan_inserts）算好这段新文字的位置感知形状再传进来，本函数
    不再自己对 content_text 调用不带位置信号的 _para_shape——旧版"只看新文字自己的开头/字面"在
    "结合材料，综合运用所学……"这类不以引导词开头的设问上会误判成 'plain'，把材料段的楷体模板
    套给设问（全书 94/453 个主观题设问踩过，见审查 r3 blocker R3-B1）。

    exclude_idx（R2-B2 残留修复）：不是这条 insert 的第一个 content 条目时，调用方会传入模板题块
    自己"标题之后第一段"的段号——按插入单格式约定（文件头 baodian_insert_v1 示例），content[0]
    通常就是块自己的"【题目】…"开场标签行；块内材料/裁判结果这类"另一种【标签】"（比如
    "【裁判结果】法院认为……"）如果恰好也是 label_prefix 形状、且块内这个形状的候选只有开场标签
    这一段，旧版会把开场标签专属的加粗深蓝原样套给完全不同性质的材料内标签（真实新题 T1c 实测：
    【裁判结果】被套成跟【题目】一样的加粗+1F4E79+keepNext；而全书 191 个材料内【】标签里 163 个
    只加粗不上色）。排除这一段后，块内再无同形状候选就会退到全书搜索，全书范围的"多数格式"能
    正确反映"材料内标签多数只加粗不上色"这个真实分布。只在 ci>0 时排除（ci==0 就是在构造这条块
    自己的开场标签本身，不该排除它自己）。

    按 content_shape 的"标签形状"（_para_shape_ctx）四态挑同形状的模板段（_pick_by_shape）——本书
    思维链条/答案落点/细则说明/题目等栏目的【标签】常与正文颜色不同（深蓝 vs 黑），"【题目】17．
    （8分）"这类"标签+编号同段"的段落也自成一种形状，设问段（'stem'）与材料段（'plain'）虽然
    样式相同也不是一回事，与纯正文不是一回事；style_override/角色桶默认匹配如果只按"是不是纯
    标签"这一粗二分，会把"标签+编号同段"的段落或材料段当正文模板，把它的格式带进设问/正文
    （B1/R2-B2：金标回归与真实新题实测都踩过这个坑，见审查 r1/r2）。四态形状只解决"别选错模板
    段的宏观格式（pPr/整体 rPr 基调）"；模板段内部"引导词/标签 run 与正文 run 格式不同"这一层，
    由 build_text_paragraph 的 _auto_split_label_runs/_prefix_split_by_template/_dominant_rpr
    三级兜底处理（同一份 fix，见该函数注释）。

    候选段落一律排除表格单元格内的段落（R2-B2 修复：source/teaching/rubric 都是普通正文角色，
    不该从表格单元格段选模板——样板题块带表格时，"多数格式"或退回全书搜索都可能选中单元格段，
    把单元格的 pPr（常见 keepLines、firstLine=0 这类表格惯用格式）带进正文，真实新题与金标回归
    都实测踩过）。

    style_override（显式 "style":"样式名"）限定在角色自己的样式桶内（R2-M1 修复：不加这层限制，
    role=="source" 配合 style="分析过程"（teaching 桶）能落到教学区的样式，而词表豁免只看
    role/source_zone、不看落到的样式桶，等于绕开了"教学/细则区永不豁免"这条线——写后区位复核
    是第二道防线，这里先把口子从源头堵上）。"""

    def _not_in_table(idxs):
        return [i for i in idxs if not d.items[i].get('tbl')]

    def _pick(in_block, in_doc_fn):
        """先在 in_block 里按 want_shape 挑；找不到再调用 in_doc_fn() 取全书候选池重挑。返回
        (idx_or_None, used_fallback_to_doc_bool)。

        want_shape=='stem' 时不走下面"块内退化匹配、块内没有才试全书"这条通用路径：先把"块内、
        精确 stem 形状"和"全书、精确 stem 形状"两关都试过（都不接受在同一个池子里退化成
        'plain' 等其他形状），两关都没有精确候选（理论上不会发生，全书 284 个显式宋体设问段）
        才退回通用的退化匹配。R2-B2 残留修复（金标回归 T2_tbl 复测两轮才发现的坑）：第一版只在
        "块内查 stem"这一步加了精确匹配，块内没有精确 stem 时仍然调用 _pick_by_shape(in_block,
        'stem')——它按 _SHAPE_PREF['stem']=('stem','plain',...) 退化，块内材料段（'plain'）
        几乎总是存在，会在"块内"这一步就直接返回材料段格式，根本走不到"退到全书"这一步；必须把
        "块内精确 stem" 和 "全书精确 stem" 这两次严格查找连续做完，都失败了才允许退化。"""
        def _shape(i):
            return _para_shape_ctx(dl.para_text(d.paras[i]), i in stem_pos)

        if want_shape == 'stem':
            strict_block = [i for i in in_block if _shape(i) == 'stem']
            if strict_block:
                return _pick_majority_format(d, strict_block, prefer_last=True), False
            in_doc = in_doc_fn()
            strict_doc = [i for i in in_doc if _shape(i) == 'stem']
            if strict_doc:
                return _pick_majority_format(d, strict_doc, prefer_last=True), True
            i = _pick_by_shape(d, in_block, want_shape, stem_pos)
            if i is not None:
                return i, False
            return _pick_by_shape(d, in_doc, want_shape, stem_pos), True
        i = _pick_by_shape(d, in_block, want_shape, stem_pos)
        if i is not None:
            return i, False
        in_doc = in_doc_fn()
        return _pick_by_shape(d, in_doc, want_shape, stem_pos), True

    want_shape = content_shape
    bucket_ids = _style_ids_for_bucket(prof, styles_obj, role)
    if not bucket_ids:
        raise Abort(f'书册配置 styles.{role} 未配置任何样式名，无法为角色 "{role}" 找模板')
    cand = _not_in_table(block.get('paras') or [])
    if exclude_idx is not None:
        cand = [i for i in cand if i != exclude_idx]
    if style_override:
        sid = ap._resolve_style_id(styles_obj, style_override)
        if sid not in bucket_ids:
            raise Abort(f'style="{style_override}" 不在角色 "{role}" 的样式桶内（styles.{role}），'
                        f'不允许用 style 覆盖到桶外样式（R2-M1 修复）')
        in_block = [i for i in cand if _para_style_id(styles_obj, d.paras[i]) == sid]
        i, escalated = _pick(in_block, lambda: _not_in_table(
            [i for i, p in enumerate(d.paras) if _para_style_id(styles_obj, p) == sid]))
        if i is not None:
            if escalated:
                fallbacks.append({'role': role, 'style': style_override,
                                   'reason': '样板题块内无该显式样式段落，回退到全书首个同形状实例', 'index': i})
            return d.paras[i], sid, _para_shape_ctx(dl.para_text(d.paras[i]), i in stem_pos)
        raise Abort(f'全书找不到样式 "{style_override}" 的段落（角色 "{role}" 桶内、非表格）')
    if like:
        hits = [i for i in cand if like in dl.para_text(d.paras[i])]
        if len(hits) != 1:
            raise Abort(f'模板题块内 like="{like}" 命中 {len(hits)} 段（须恰好 1 段，且不在表格内）')
        p = d.paras[hits[0]]
        sid = _para_style_id(styles_obj, p)
        if sid not in bucket_ids:
            raise Abort(f'模板题块内 like="{like}" 命中的段落样式不在 styles.{role} 桶内（实际样式 '
                        f'{styles_obj.name.get(sid, sid)}）')
        return p, sid, _para_shape_ctx(dl.para_text(p), hits[0] in stem_pos)
    # 没给 like、也没给 style：按角色桶 + 标签形状挑（见函数头说明）。
    in_block = [i for i in cand if _para_style_id(styles_obj, d.paras[i]) in bucket_ids]
    i, escalated = _pick(in_block, lambda: _not_in_table(
        [i for i, p in enumerate(d.paras) if _para_style_id(styles_obj, p) in bucket_ids]))
    if i is not None:
        if escalated:
            fallbacks.append({'role': role, 'reason': '样板题块无该角色样式段落，回退到全书首个同形状实例',
                               'index': i})
        return d.paras[i], _para_style_id(styles_obj, d.paras[i]), _para_shape_ctx(dl.para_text(d.paras[i]), i in stem_pos)
    raise Abort(f'全书都找不到角色 "{role}"（styles.{role}）对应的段落，无法提供模板（已排除表格内段落）')


def find_image_template(d, block, fallbacks):
    for i in (block.get('paras') or []):
        if d.items[i].get('img'):
            return d.paras[i]
    for i, it in enumerate(d.items):
        if it.get('img'):
            fallbacks.append({'role': 'image', 'reason': '样板题块无图片段落，回退到全书首个图片段落',
                               'index': i})
            return d.paras[i]
    return None


# ------------------------------------------------------------------ 原件 DOCX：取图 / 取表
class _SourceDocx:
    """打开一份原件 DOCX（只读，供取图/取表），缓存 body/rels/媒体字节；同一插入单里多次引用同一
    原件只打开一次。与本工具正在改写的目标 DOCX（d）完全独立——不共用任何对象。"""
    def __init__(self, path):
        self.path = Path(path)
        if not self.path.exists():
            raise Abort(f'原件不存在：{path}')
        self.z = zipfile.ZipFile(self.path)
        names = set(self.z.namelist())
        if 'word/document.xml' not in names:
            raise Abort(f'原件不是 Word 正文包：{path}')
        self.root = etree.fromstring(self.z.read('word/document.xml'))
        self.body = self.root.find(W + 'body')
        self.rels = {}          # rId -> Target
        self.rel_types = {}     # rId -> Type（B2：重建关系时按类型分流，不再只认 a:blip/v:imagedata）
        self.rel_mode = {}      # rId -> TargetMode（'External' 或 None=Internal；超链接判定用）
        if 'word/_rels/document.xml.rels' in names:
            for r in etree.fromstring(self.z.read('word/_rels/document.xml.rels')):
                rid = r.get('Id')
                self.rels[rid] = r.get('Target')
                self.rel_types[rid] = r.get('Type')
                self.rel_mode[rid] = r.get('TargetMode')
        self.paras = dl.para_elements(self.body)
        # R2-B1 修复：原件自己的 word/styles.xml（styleId -> (type, w:name)），供 sanitize_table_
        # styles 按名字而不是按 styleId 给表格样式引用找目标书里的对应样式——styleId 是 Word 在各
        # 文档里各自生成的，同一个 id 在不同文档里可能是完全不同类型/名字的样式。
        self.styles_root = (etree.fromstring(self.z.read('word/styles.xml'))
                             if 'word/styles.xml' in names else None)
        self._type_name_map = None

    def style_type_name(self):
        if self._type_name_map is None:
            self._type_name_map = _style_type_name_map(self.styles_root)
        return self._type_name_map

    def media_bytes(self, target):
        p = target.lstrip('/') if target.startswith('/') else 'word/' + target
        try:
            return self.z.read(p)
        except KeyError:
            raise Abort(f'原件 {self.path.name} 里找不到媒体成员：{p}')


_source_cache = {}


def open_source(path):
    key = str(Path(path).resolve())
    if key not in _source_cache:
        _source_cache[key] = _SourceDocx(path)
    return _source_cache[key]


def _close_source_cache():
    """m16 修复：_source_cache 原先是跨调用存活的全局缓存，ZipFile 句柄也从不关闭——进程内连续
    多次调用 plan_inserts()（比如未来串联调用，或测试里为了 monkeypatch 直接进程内调用本模块
    函数）会把上一次打开的原件带进这一次的报告，句柄也越攒越多。取完"本次用过哪些原件"快照后
    立即调用本函数：关闭全部句柄、清空缓存，不影响"同一次调用内重复引用同一原件只打开一次"这个
    既有优化（缓存只在一次 plan_inserts() 调用的生命周期内有效）。"""
    for src in _source_cache.values():
        try:
            src.z.close()
        except Exception:
            pass
    _source_cache.clear()


def _drawing_elements(root):
    """全文 wp:inline/wp:anchor 元素，按文档序（用于 index 选择器）。"""
    return [el for el in root.iter() if el.tag in (WP_NS + 'inline', WP_NS + 'anchor')]


def _drawing_extent(dr):
    ext = dr.find(WP_NS + 'extent')
    if ext is None:
        return None, None
    try:
        return int(ext.get('cx')), int(ext.get('cy'))
    except (TypeError, ValueError):
        return None, None


def _drawing_rid(dr):
    blip = dr.find(f'.//{A_NS}blip')
    if blip is None:
        return None
    return blip.get(R_NS + 'embed') or blip.get(R_NS + 'link')


def locate_source_image(src, selector):
    """selector: {'rid':…} | {'index':k(1起)} | {'near_text':…}。返回 (rid, target, cx, cy, was_anchor)
    ——was_anchor 标记原件里这张图是不是 wp:anchor 浮动图（本工具统一转 wp:inline，见 M5）。"""
    drs = _drawing_elements(src.root)
    if 'rid' in selector:
        want = selector['rid']
        hits = [dr for dr in drs if _drawing_rid(dr) == want]
        if len(hits) != 1:
            raise Abort(f'原件里 rId="{want}" 的图形命中 {len(hits)} 处（须恰好 1 处）')
        dr = hits[0]
    elif 'index' in selector:
        k = int(selector['index'])
        if not (1 <= k <= len(drs)):
            raise Abort(f'原件里第 {k} 个图形不存在（共 {len(drs)} 个）')
        dr = drs[k - 1]
    elif 'near_text' in selector:
        want = selector['near_text']
        hits = []
        n = len(src.paras)
        for i, p in enumerate(src.paras):
            local = _drawing_elements(p)
            if not local:
                continue
            near = dl.para_text(p)
            if i > 0:
                near += '\n' + dl.para_text(src.paras[i - 1])
            if i + 1 < n:
                near += '\n' + dl.para_text(src.paras[i + 1])
            if want in near:
                hits += local
        if len(hits) != 1:
            raise Abort(f'原件里邻近文字含 "{want}" 的图形命中 {len(hits)} 处（须恰好 1 处；本图所在段'
                        f'/前一段/后一段文字合并后查找）')
        dr = hits[0]
    else:
        raise Abort('image.from 须给 rid/index/near_text 之一')
    rid = _drawing_rid(dr)
    if not rid:
        raise Abort('定位到的图形没有 r:embed/r:link，取不到图片')
    target = src.rels.get(rid)
    if not target:
        raise Abort(f'原件关系表里没有 {rid} 对应的媒体')
    cx, cy = _drawing_extent(dr)
    return rid, target, cx, cy, dr.tag == WP_NS + 'anchor'


def locate_source_table(src, selector):
    tops = _top_tables(src.body)
    if 'table_index' in selector:
        k = int(selector['table_index'])
        if not (1 <= k <= len(tops)):
            raise Abort(f'原件里第 {k} 个表格不存在（共 {len(tops)} 个）')
        return tops[k - 1]
    if 'contains' in selector:
        want = selector['contains']
        hits = [t for t in tops if want in ''.join(dl.para_text(p) for p in dl.para_elements(t))]
        if len(hits) != 1:
            raise Abort(f'原件里含 "{want}" 的表格命中 {len(hits)} 个（须恰好 1 个）')
        return hits[0]
    raise Abort('table.from 须给 table_index/contains 之一')


def _image_px_size(data):
    """用 PyMuPDF 读像素宽高（延迟导入；也顺带当作"图片是否可解析"的校验，损坏文件在这里报错）。
    R3-m6 修复：改 `import pymupdf`，不再 `import fitz`——旧式 `fitz` 这个名字导入时会把一行
    弃用警告打到 stdout（"warning: The `fitz` API is deprecated…"），check 模式的 stdout 就是
    一行 JSON，这行警告混进去会让下游按 stdout 解析 summary 的调用方（如 intake_run）
    json.loads 失败；`import pymupdf` 是同一个包的新名字，不产生这行输出。"""
    import pymupdf  # noqa: 延迟导入，按共同约定第 2 条
    try:
        pm = pymupdf.Pixmap(data)
    except Exception as e:
        raise Abort(f'图片文件无法解析（可能已损坏）：{e}')
    return pm.width, pm.height


# ------------------------------------------------------------------ 媒体成员 / 关系 / Content_Types / id 分配
class MediaCtx:
    """收集本次插入要新增的 word/media/ 成员、document.xml.rels 新关系、[Content_Types].xml 新
    Default 扩展名；write 阶段一次性落到输出包（docx_lib.write_docx 只能替换已有成员，新增成员要
    另写函数，见 _write_with_new_media）。"""
    def __init__(self, d):
        self.d = d
        with zipfile.ZipFile(d.path) as z:
            self.existing_media = [n for n in z.namelist() if n.startswith('word/media/')]
            self.rels_root = etree.fromstring(z.read(RELS_PATH)) if RELS_PATH in z.namelist() else None
            self.ct_root = etree.fromstring(z.read(CONTENT_TYPES_PATH))
        if self.rels_root is None:
            raise Abort('父稿缺 word/_rels/document.xml.rels，无法新增图片关系')
        self._next_media_no = 1
        for n in self.existing_media:
            m = re.search(r'image(\d+)\.', Path(n).name)
            if m:
                self._next_media_no = max(self._next_media_no, int(m.group(1)) + 1)
        self._next_rid_no = 1
        for r in self.rels_root:
            m = re.match(r'rId(\d+)$', r.get('Id') or '')
            if m:
                self._next_rid_no = max(self._next_rid_no, int(m.group(1)) + 1)
        self.new_media = {}       # member path -> bytes
        self.new_rels = []        # (rid, type, target, mode) 追加进 rels；mode='External'|None
        self.ct_exts = set(c.get('Extension', '').lower() for c in self.ct_root
                            if c.tag == CT_NS + 'Default')

    def add_image(self, data, ext):
        ext = ext.lower().lstrip('.')
        no = self._next_media_no
        self._next_media_no += 1
        name = f'word/media/image{no}.{ext}'
        rid = f'rId{self._next_rid_no}'
        self._next_rid_no += 1
        self.new_media[name] = data
        self.new_rels.append((rid, REL_IMAGE_TYPE, f'media/image{no}.{ext}', None))
        if ext not in self.ct_exts:
            self.ct_exts.add(ext)
            ct = EXT_CONTENT_TYPE.get(ext, 'application/octet-stream')
            etree.SubElement(self.ct_root, CT_NS + 'Default', Extension=ext, ContentType=ct)
        return rid

    def add_external_rel(self, rel_type, target):
        """表格内超链接等外部关系（B2 修复）：TargetMode="External"，Target 是原样的 URL/外部
        引用，不落盘媒体成员。只用于原件关系表里 TargetMode 明确是 External 的引用；Internal
        引用（指向原件自己包内的其他部件，如脚注/书签）在目标文档里无法安全解析，调用方须 Abort。"""
        rid = f'rId{self._next_rid_no}'
        self._next_rid_no += 1
        self.new_rels.append((rid, rel_type, target, 'External'))
        return rid

    def rels_bytes(self):
        for rid, typ, target, mode in self.new_rels:
            attrs = {'Id': rid, 'Type': typ, 'Target': target}
            if mode:
                attrs['TargetMode'] = mode
            etree.SubElement(self.rels_root, PKG_REL + 'Relationship', **attrs)
        return etree.tostring(self.rels_root, xml_declaration=True, encoding='UTF-8', standalone=True)

    def content_types_bytes(self):
        return etree.tostring(self.ct_root, xml_declaration=True, encoding='UTF-8', standalone=True)


def _existing_docpr_ids(root):
    return {int(x) for x in (el.get('id') for el in root.iter(WP_NS + 'docPr')) if x and x.isdigit()}


class IdAllocator:
    def __init__(self, root):
        self.root = root
        ids = _existing_docpr_ids(root)
        self._next_docpr = (max(ids) + 1) if ids else 1
        self._issued_docpr = set()
        bids = {int(b.get(W + 'id')) for b in root.iter(W + 'bookmarkStart') if (b.get(W + 'id') or '').isdigit()}
        self._next_bm = (max(bids) + 1) if bids else 1
        self._names = {b.get(W + 'name') for b in root.iter(W + 'bookmarkStart')}

    def docpr_id(self):
        while self._next_docpr in self._issued_docpr:
            self._next_docpr += 1
        v = self._next_docpr
        self._issued_docpr.add(v)
        self._next_docpr += 1
        return v

    def bookmark(self, hint):
        bid = self._next_bm
        self._next_bm += 1
        base = re.sub(r'[^A-Za-z0-9_]', '_', hint)[:32] or 'ins'
        name = f'baodian_ins_{base}_{bid}'
        n = 1
        while name in self._names:
            n += 1
            name = f'baodian_ins_{base}_{bid}_{n}'
        self._names.add(name)
        return bid, name


def _enclosing_drawing(el):
    """el（如 a:blip/v:imagedata）所在的 wp:inline/wp:anchor 祖先，供转 inline、重分配 docPr 用。"""
    node = el
    while node is not None:
        if node.tag in (WP_NS + 'inline', WP_NS + 'anchor'):
            return node
        node = node.getparent()
    return None


def _anchor_to_inline(anchor_el):
    """把 wp:anchor 浮动图换成 wp:inline（就地替换进父级 w:drawing），只搬 extent/effectExtent/
    docPr/cNvGraphicFramePr/graphic 这几个两者共有的子节点，丢弃 simplePos/positionH/positionV/
    wrap* 等浮动专属属性——与文件头"原件 wp:anchor 转 inline"的既定口径一致（M1/M5 修复：表内图片
    与顶层 build_image_paragraph 走同一条转换路径）。返回新的 inline 元素。"""
    new_el = etree.Element(WP_NS + 'inline',
                            distT=anchor_el.get('distT', '0'), distB=anchor_el.get('distB', '0'),
                            distL=anchor_el.get('distL', '0'), distR=anchor_el.get('distR', '0'))
    extent = anchor_el.find(WP_NS + 'extent')
    if extent is not None:
        new_el.append(copy.deepcopy(extent))
    effect = anchor_el.find(WP_NS + 'effectExtent')
    new_el.append(copy.deepcopy(effect) if effect is not None
                  else etree.Element(WP_NS + 'effectExtent', l='0', t='0', r='0', b='0'))
    docpr = anchor_el.find(WP_NS + 'docPr')
    if docpr is not None:
        new_el.append(copy.deepcopy(docpr))
    cnv = anchor_el.find(WP_NS + 'cNvGraphicFramePr')
    if cnv is not None:
        new_el.append(copy.deepcopy(cnv))
    graphic = anchor_el.find(A_NS + 'graphic')
    if graphic is not None:
        new_el.append(copy.deepcopy(graphic))
    parent = anchor_el.getparent()
    parent.replace(anchor_el, new_el)
    return new_el


def find_table_template(d, block, body, fallbacks):
    tops = _top_tables(body)
    nums = sorted({d.items[i]['tbl'] for i in (block.get('paras') or []) if d.items[i]['tbl']})
    if nums and nums[0] - 1 < len(tops):
        return tops[nums[0] - 1]
    if tops:
        fallbacks.append({'role': 'table', 'reason': '样板题块无表格，回退到全书第 1 个表格'})
        return tops[0]
    return None


# ------------------------------------------------------------------ 段落 / 表格构造
def _rpr_at_offset(spans, offset):
    pos = 0
    for run, text in spans:
        if offset < pos + len(text) or (not text and offset == pos):
            return run.find(W + 'rPr')
        pos += len(text)
    return spans[-1][0].find(W + 'rPr') if spans else None


def _rpr_sig(rpr):
    return etree.tostring(rpr) if rpr is not None else b''


def _auto_split_label_runs(text, template_p):
    """自动拆"【标签】正文"同段两种格式：本书细则说明等栏目常见"标签深蓝、正文黑"同段两色（如
    B0003 的【细则说明】），content 条目给整段 text（不给 runs）又命中这个形状、且模板段标签/正文
    确实不同格式时，按模板段对应位置的 rPr 各自克隆，不整段套标签格式——这是从真实体检 FAIL
    （教学正文误蓝）里发现的坑，见文件头"角色→样式"一节。格式相同（模板段本来就没分色）时返回
    None，退回整段单一 run 的简单路径。"""
    m = _INLINE_LABEL_RX.match(text or '')
    if not m or template_p is None:
        return None
    spans = ap._run_spans(template_p)
    full = ''.join(t for _, t in spans)
    tm = _INLINE_LABEL_RX.match(full)
    if not tm:
        return None
    label_end = tm.end(1)
    label_rpr, rest_rpr = _rpr_at_offset(spans, 0), _rpr_at_offset(spans, label_end)
    if _rpr_sig(label_rpr) == _rpr_sig(rest_rpr):
        return None
    return m.group(1), m.group(2), label_rpr, rest_rpr


def _clone_ppr(template_p):
    if template_p is None:
        return None
    ppr = template_p.find(W + 'pPr')
    if ppr is None:
        return None
    ppr2 = copy.deepcopy(ppr)
    for tag in (W + 'bookmarkStart', W + 'bookmarkEnd'):
        for x in ppr2.findall(tag):
            ppr2.remove(x)
    return ppr2


def _clone_body_ppr(template_p):
    """正文段（source/teaching/rubric 文字角色）的 pPr：从模板段克隆（已去 bookmark，见 _clone_ppr），
    额外去掉 w:keepNext 与 w:ind 的 firstLine/firstLineChars（B1 修复）——三道真实新题与金标回归实测
    都踩过：模板段选中的恰好是"标题/标签行"本身（比如"【题目】17．（8分）"），它常见"与下一段同页
    （keepNext）、首行不缩进（firstLine=0）"这类版式，是标题行的版式，不是正文的版式；按同一模板段
    构造出来的材料/设问/教学正文段不该继承。keepNext 整个去掉；ind 只去 firstLine 两个属性，其余
    left/hanging 等缩进属性原样保留（那些通常是正文该有的缩进，不是标题行特有的）。"""
    ppr2 = _clone_ppr(template_p)
    if ppr2 is None:
        return None
    kn = ppr2.find(W + 'keepNext')
    if kn is not None:
        ppr2.remove(kn)
    ind = ppr2.find(W + 'ind')
    if ind is not None:
        changed = False
        for attr in (W + 'firstLine', W + 'firstLineChars'):
            if ind.get(attr) is not None:
                del ind.attrib[attr]
                changed = True
        if changed and len(ind.attrib) == 0:
            ppr2.remove(ind)
    return ppr2


def _prefix_split_by_template(text, template_p):
    """通用版"引导词/正文两段式"拆分（B1 修复，覆盖 _auto_split_label_runs 管不到的非【】引导词，
    如"从材料选知识：""从设问定层次："——这两个都是"短引导词加粗、长正文不加粗，同色"的两 run 段）：
    content 文字若整串以模板段自己第一个 run 的文字原样开头，且该 run 格式与模板段其余部分不同，
    就按这个边界切成两个 run；引导词沿用模板引导词的格式，其余沿用模板其余部分的格式。要求引导词
    完全等长匹配，不满足就返回 None，交给 _dominant_rpr 兜底（不强行拆，宁可退到"多数格式"）。"""
    if template_p is None or not text:
        return None
    spans = ap._run_spans(template_p)
    if len(spans) < 2:
        return None
    first_run, first_text = spans[0]
    if not first_text or not text.startswith(first_text):
        return None
    label_rpr = first_run.find(W + 'rPr')
    rest_rpr = _rpr_at_offset(spans, len(first_text))
    if _rpr_sig(label_rpr) == _rpr_sig(rest_rpr):
        return None
    return first_text, text[len(first_text):], label_rpr, rest_rpr


def _dominant_rpr(template_p):
    """模板段里"贡献字符数最多"的那种格式的 rPr（B1 修复）——单 run 模板段就是那一个 run 的格式；
    多 run 模板段（常见"短引导词/标签加粗 + 长正文不加粗"两段式）不再无条件取第一个 run（那样会把
    短引导词的加粗/变色套进整段新文字，审查 r1 B1 的核心问题），改取字符数占多数的那种格式——这是
    "新内容与模板引导词形状对不上、_prefix_split_by_template 也拆不了"时的最后一道兜底，宁可丢失
    模板段内部的次要强调格式，也不能让新正文整段被短引导词的格式染色。

    返回的是深拷贝，不是模板段自己 rPr 元素的引用（R3-M1 返修期间踩过的坑）：lxml 元素只能挂在
    一个父节点下，调用方如果拿到的是模板树里那个 rPr 的原始引用，随手 `.append()` 到别处会把它
    从模板段（往往就是书稿里另一道题自己的段落）里连根拔走，被写权守卫之外的"未点名段落发生变化"
    复核当场抓到（真实用例 T1b 实测：rows[] 生成新表格时借用了 B0003 自己表格的 rPr，B0003 那一格
    的 run 因此丢了 rPr）。调用方不需要、也不该在拿到返回值后自己再 deepcopy 一遍才安全——这里
    统一返回一份独立拷贝，谁都能直接用。"""
    spans = ap._run_spans(template_p)
    if not spans:
        return None
    lens, rprs = {}, {}
    for run, text in spans:
        rpr = run.find(W + 'rPr')
        sig = _rpr_sig(rpr)
        lens[sig] = lens.get(sig, 0) + len(text)
        rprs.setdefault(sig, rpr)
    best_sig = max(lens, key=lambda s: lens[s])
    best = rprs[best_sig]
    return copy.deepcopy(best) if best is not None else None


def build_text_paragraph(item, template_p, styles_obj, content_shape=None, template_shape=None):
    """source/teaching/rubric 三种文字角色的正文段构造（B1 修复：不再无条件复用
    apply_patch._build_paragraph 的"模板段整段 pPr + 首个 run rPr"路径，那条路径是把标签/引导词
    格式带进正文的根源）。显式给了 runs（插入单作者自己按 run 分好格式，如【答案落点】④…这种要保留
    加粗的场景）的条目仍走 ap._build_paragraph，尊重作者的显式覆盖；不给 runs、只给整段 text 的条目
    按三级顺序处理：
      1) _auto_split_label_runs——text 本身是"【标签】+正文"且模板段也是这个形状、标签/正文格式
         确实不同，按模板段【】边界切两个 run（细则说明/题目标签这类）。
      2) _prefix_split_by_template——text 以模板段自己第一个 run 的原文开头（非【】的引导词，如
         "从材料选知识："），按模板段的引导词边界切两个 run。
      3) 都不满足：整段一个 run，取 _dominant_rpr（模板段里多数格式），不取首个 run。
    pPr 按模板段与新内容"标签形状"是否一致分两种取法：一致（比如原样重插【题目】标签行本身，模板
    也恰好是同一种"标签+编号同段"形状）就用 _clone_ppr 原样继承，包括 keepNext/firstLine——这时
    模板确实代表"这一类形状该有的版式"，keepNext/firstLine 是这一类行本该有的格式，不是误带入的；
    不一致（模板是退而求其次/显式 like/style 落到的别的形状）才用 _clone_body_ppr 去掉 keepNext/
    firstLine，避免标题/标签行的版式误带进不该有的正文（B1 修复；金标回归实测发现：统一去掉会让
    原样重插的【题目】标签行本身丢失它自己原有的 keepNext/firstLine=0，见回执）。

    content_shape/template_shape（R3-B1 修复）：调用方（plan_inserts）已经用同一套位置感知
    _para_shape_ctx 分别算好新文字与模板段各自的形状，这里直接比较、不再各自对纯文字重新调用不带
    位置信号的 _para_shape——否则"新文字被位置信号升级成 stem、模板段本身也是位置升级来的 stem"
    这类本该 same_shape=True 的情形会因为两边判据不一致被错判成 False。两个参数都不给时（供其他
    调用方/测试直接构造）退回旧的纯文字比较，行为不变。"""
    if item.get('runs'):
        return ap._build_paragraph({'runs': item['runs']}, template_p, styles_obj)
    text = item.get('text', '')
    split = _auto_split_label_runs(text, template_p) or _prefix_split_by_template(text, template_p)
    if content_shape is not None and template_shape is not None:
        same_shape = template_p is not None and content_shape == template_shape
    else:
        same_shape = template_p is not None and _para_shape(text) == _para_shape(dl.para_text(template_p))
    new_p = etree.Element(W + 'p')
    ppr2 = _clone_ppr(template_p) if same_shape else _clone_body_ppr(template_p)
    if ppr2 is not None:
        new_p.append(ppr2)
    if split:
        label_part, rest, label_rpr, rest_rpr = split
        for part, rpr in ((label_part, label_rpr), (rest, rest_rpr)):
            r = etree.SubElement(new_p, W + 'r')
            if rpr is not None:
                r.append(copy.deepcopy(rpr))
            ap._emit_text(r, part)
    else:
        r = etree.SubElement(new_p, W + 'r')
        rpr = _dominant_rpr(template_p)
        if rpr is not None:
            r.append(copy.deepcopy(rpr))
        ap._emit_text(r, text)
    return new_p


def build_title_paragraph(title_text, template_title_p, styles_obj, id_alloc, fallbacks):
    new_p = ap._build_paragraph({'text': title_text}, template_title_p, styles_obj)
    bms = template_title_p.findall(W + 'bookmarkStart') if template_title_p is not None else []
    if bms:
        bid, name = id_alloc.bookmark(re.sub(r'\s', '', title_text)[:16])
        ppr = new_p.find(W + 'pPr')
        pos = 1 if ppr is not None else 0
        new_p.insert(pos, etree.Element(W + 'bookmarkStart', {W + 'id': str(bid), W + 'name': name}))
        new_p.append(etree.Element(W + 'bookmarkEnd', {W + 'id': str(bid)}))
        fallbacks.append({'note': f'模板标题带书签，为新标题生成书签 {name}（id={bid}）'})
    return new_p


def _fit_extent(cx, cy, width_cm, max_cx):
    """按 width_cm（可选，作者显式要求的图片显示宽度，单位 cm）与 max_cx（版心/样板图片宽度上限，
    单位 EMU）算最终 wp:extent。R3-m5 修复：width_cm 必须是正数，且换算出的 EMU 宽度必须是正整数
    ——OOXML 的 wp:extent 走 ST_PositiveCoordinate，不允许 0 或负值；旧版对 width_cm=-5（换算出
    cx=-1800000）、width_cm=1e-9（四舍五入到 cx=0）都不挡，写出非法 extent 也没有校验查得出来
    （verify_output 不比 extent 数值），照样 rc=0（见审查 r3 R3-m5）。类型（必须是 int/float、
    不能是字符串/bool）已经在 _validate_unit_schema/_check_type 挡过，这里只管值范围。"""
    if width_cm is not None:
        if width_cm <= 0:
            raise Abort(f'width_cm 必须是正数：{width_cm!r}')
        if cx:
            cx2 = int(round(width_cm * EMU_PER_CM))
            if cx2 <= 0:
                raise Abort(f'width_cm={width_cm!r} 换算出的图片宽度不是正整数 EMU（{cx2}），'
                            f'请给一个更大的 width_cm')
            cy = int(round(cy * cx2 / cx)) if cx else cy
            cx = cx2
    if max_cx and cx and cx > max_cx:
        cy = int(round(cy * max_cx / cx))
        cx = max_cx
    return cx, cy


def build_image_paragraph(template_p, rid, cx, cy, name_hint, docpr_id):
    new_p = etree.Element(W + 'p')
    base_rpr = None
    if template_p is not None:
        ppr = template_p.find(W + 'pPr')
        if ppr is not None:
            ppr2 = copy.deepcopy(ppr)
            for tag in (W + 'bookmarkStart', W + 'bookmarkEnd'):
                for x in ppr2.findall(tag):
                    ppr2.remove(x)
            new_p.append(ppr2)
        for r in template_p.iter(W + 'r'):
            if r.find(W + 'drawing') is not None:
                base_rpr = r.find(W + 'rPr')
                break
    else:
        ppr = etree.SubElement(new_p, W + 'pPr')
        etree.SubElement(ppr, W + 'spacing', {W + 'line': '240', W + 'lineRule': 'auto'})
        etree.SubElement(ppr, W + 'jc', {W + 'val': 'center'})
    r = etree.SubElement(new_p, W + 'r')
    if base_rpr is not None:
        r.append(copy.deepcopy(base_rpr))
    drawing = etree.SubElement(r, W + 'drawing')
    inline = etree.SubElement(drawing, WP_NS + 'inline',
                               distT='0', distB='0', distL='0', distR='0')
    etree.SubElement(inline, WP_NS + 'extent', cx=str(cx), cy=str(cy))
    etree.SubElement(inline, WP_NS + 'effectExtent', l='0', t='0', r='0', b='0')
    etree.SubElement(inline, WP_NS + 'docPr', id=str(docpr_id), name=(name_hint or 'Picture')[:60])
    cnv = etree.SubElement(inline, WP_NS + 'cNvGraphicFramePr')
    etree.SubElement(cnv, A_NS + 'graphicFrameLocks', noChangeAspect='1')
    graphic = etree.SubElement(inline, A_NS + 'graphic')
    gd = etree.SubElement(graphic, A_NS + 'graphicData',
                           uri='http://schemas.openxmlformats.org/drawingml/2006/picture')
    pic = etree.SubElement(gd, PIC_NS + 'pic')
    nv = etree.SubElement(pic, PIC_NS + 'nvPicPr')
    etree.SubElement(nv, PIC_NS + 'cNvPr', id=str(docpr_id), name=(name_hint or 'image')[:80])
    etree.SubElement(nv, PIC_NS + 'cNvPicPr')
    fill = etree.SubElement(pic, PIC_NS + 'blipFill')
    etree.SubElement(fill, A_NS + 'blip', {R_NS + 'embed': rid})
    stretch = etree.SubElement(fill, A_NS + 'stretch')
    etree.SubElement(stretch, A_NS + 'fillRect')
    sppr = etree.SubElement(pic, PIC_NS + 'spPr')
    xfrm = etree.SubElement(sppr, A_NS + 'xfrm')
    etree.SubElement(xfrm, A_NS + 'off', x='0', y='0')
    etree.SubElement(xfrm, A_NS + 'ext', cx=str(cx), cy=str(cy))
    geom = etree.SubElement(sppr, A_NS + 'prstGeom', prst='rect')
    etree.SubElement(geom, A_NS + 'avLst')
    return new_p


def _style_type_name_map(styles_root):
    """styleId -> (w:type, w:name) 从一份 word/styles.xml 的根元素解析（R2-B1 修复用）。type 缺省
    当 'paragraph'（OOXML 对 w:style 的 w:type 缺省值就是 paragraph）；name 缺省用 styleId 本身
    （极少数手写样式没有 w:name 子节点）。"""
    out = {}
    if styles_root is None:
        return out
    for st in styles_root.iter(W + 'style'):
        sid = st.get(W + 'styleId')
        if not sid:
            continue
        typ = st.get(W + 'type') or 'paragraph'
        n = st.find(W + 'name')
        name = n.get(W + 'val') if n is not None else sid
        out[sid] = (typ, name)
    return out


def _name_to_id_index(type_name_map):
    """(type, name) -> styleId 反向索引；同类型同名重复时取先出现的一个（文档序）——真实
    word/styles.xml 里同类型同名重复极罕见，够用。"""
    idx = {}
    for sid, key in type_name_map.items():
        idx.setdefault(key, sid)
    return idx


def sanitize_table_styles(tbl, target_name_to_id, src_type_name):
    """只处理表级 w:tblStyle（R2-B1 修复＋精简）。单元格段落/run 的样式与直接格式改由
    _reformat_table_cells 整段套样板表头/表体行格式覆盖（该函数对每个单元格段落的 pPr、每个 run
    的 rPr 要么整体换成样板格式、要么整体去掉），旧版按"styleId 是否在本书 styles.xml 里存在"
    判断能不能保留 pStyle/rStyle 引用的逻辑不再需要——那条逻辑本身就是 R2-B1 的坑：不同 Word
    文档各自生成的 styleId（a、a9、ab、af0…）会撞号，同一个 id 在不同文档里可能是完全不同类型/
    名字的样式，"存在就保留"会把引用静默改绑到本书毫不相干的样式（真实原件实测：pStyle a9 在
    原件是"List Paragraph"，在本书是字符样式"标题 字符"；rStyle ab 原件"Hyperlink"，本书是
    "副标题 字符"；tblStyle af0 原件"Table Grid"，本书是段落样式"macro"）。

    tblStyle 是整张表只有一处的表级属性，_reformat_table_cells 管不到，这里改按 (type, w:name)
    在目标书 word/styles.xml 里找同类型同名的样式，找不到就删除——不再像旧版一样只要 styleId 在
    本书"存在"（哪怕类型、名字完全不同）就当作可以保留。"""
    tblpr = tbl.find(W + 'tblPr')
    if tblpr is None:
        return
    ts = tblpr.find(W + 'tblStyle')
    if ts is None:
        return
    old_id = ts.get(W + 'val')
    info = src_type_name.get(old_id)
    new_id = target_name_to_id.get(info) if info else None
    if new_id:
        ts.set(W + 'val', new_id)
    else:
        tblpr.remove(ts)


_PPR_ORDER = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr', 'widowControl', 'numPr',
              'suppressLineNumbers', 'pBdr', 'shd', 'tabs', 'suppressAutoHyphens', 'kinsoku', 'wordWrap',
              'overflowPunct', 'topLinePunct', 'autoSpaceDE', 'autoSpaceDN', 'bidi', 'adjustRightInd',
              'snapToGrid', 'spacing', 'ind', 'contextualSpacing', 'mirrorIndents', 'suppressOverlap',
              'jc', 'textDirection', 'textAlignment', 'textboxTightWrap', 'outlineLvl', 'divId',
              'cnfStyle', 'rPr', 'sectPr']
_RPR_ORDER = ['ins', 'del', 'rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike',
              'dstrike', 'outline', 'shadow', 'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish',
              'webHidden', 'color', 'spacing', 'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u',
              'effect', 'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs', 'em', 'lang',
              'eastAsianLayout', 'specVanish', 'oMath']
# R3-M3 修复：整体覆盖 rPr 时原样保留这几项——它们改变的是文字本身怎么呈现/是不是有空位（下划线
# 常被用作填空题面的空位、上下标、着重号、删除线），不是"字体统不统一"这类版式问题，覆盖格式不
# 该连着把它们也抹掉（真实题卷实测：教师版填空题的下划线空位被整表格式覆盖后消失，文字逐字不变，
# 题面零改写的文字校验查不出来）。
_SEMANTIC_RPR_TAGS = ('u', 'vertAlign', 'em', 'strike')


def _insert_ordered(parent, el, order):
    """把 el 按 order（该元素类型允许的子元素顺序，OOXML CT_pPr/CT_rPr 都要求顺序）插到 parent
    正确的位置——不是随手 insert(0,...)/append，避免生成顺序不合规的 pPr/rPr（R3-M1/R3-M3 修复
    新增 jc/b/u 等元素时都要经过这个函数）。order 里找不到的标签一律放最后（append）。"""
    local = etree.QName(el).localname
    if local not in order:
        parent.append(el)
        return
    pos = order.index(local)
    idx = len(parent)
    for i, child in enumerate(parent):
        cl = etree.QName(child).localname
        cpos = order.index(cl) if cl in order else len(order)
        if cpos > pos:
            idx = i
            break
    parent.insert(idx, el)


def _template_row_fmt(template_tbl, row_index, col_index=0):
    """样板表格第 row_index 行（0=表头，其余=表体）第 col_index 个单元格（超出样板列数时 clamp 到
    最后一列）首个段落的 pPr（已去 bookmark，复用 _clone_ppr）与"多数格式" rPr（复用 _dominant_
    rpr——同一段内多个 run 时取贡献字符数最多的那种格式，不取第一个 run，避免局部强调格式被当成
    整行代表格式）。样板没有这一行/这一行没有单元格/没有段落时返回 (None, None)。

    col_index（R3-M1 修复）：旧版无条件只取"这一行第一个单元格"的格式套给整行所有单元格——样板
    例题 4 的表格每行首格是"夯基固本/着眼长远"这类 keepNext=True 的小标题格、其余格是普通内容格，
    只取首格会把小标题格的 keepNext、非居中对齐扩散到源表格每一个单元格（金标回归 T2_tbl 实测：
    21 个单元格段全部带上不该有的 keepNext）。改按列对应取样板同一列的格式，样板列数不够时 clamp
    到样板最后一列（源表格列数多于样板时，多出的列沿用样板最后一列的格式，不是首列）。"""
    if template_tbl is None:
        return None, None
    trs = template_tbl.findall(W + 'tr')
    if row_index >= len(trs):
        return None, None
    tcs = trs[row_index].findall(W + 'tc')
    if not tcs:
        return None, None
    tc = tcs[min(col_index, len(tcs) - 1)]
    fp = tc.find(W + 'p')
    if fp is None:
        return None, None
    return _clone_ppr(fp), _dominant_rpr(fp)


def _template_header_distinct(template_tbl):
    """样板表格是不是真的有一行区别于表体的"表头"（首行整体加粗或居中，且与表体不同）——R3-M1
    修复：例题 4 这类"每行首格是 keepNext 小标题、没有独立表头行"的样板，首行与表体其实是同一套
    格式（都是"小标题格+内容格"），不能算"有表头"；例题 2 这类"第一行整行加粗居中、其余行左对齐
    不加粗"的样板才算"有表头"。只按第 0 列比较——表头往往整行统一，第 0 列足够代表。样板只有
    1 行、或读不到格式时保守当"没有表头"（返回 False），交给调用方按"没有表头"的分支处理（保留
    源表自己的表头强调，见 _reformat_table_cells）。"""
    header_ppr, header_rpr = _template_row_fmt(template_tbl, 0, 0)
    if header_ppr is None and header_rpr is None:
        return False
    h_jc = header_ppr.find(W + 'jc') if header_ppr is not None else None
    h_center = h_jc is not None and h_jc.get(W + 'val') == 'center'
    h_bold = header_rpr is not None and header_rpr.find(W + 'b') is not None
    if not (h_center or h_bold):
        return False
    body_ppr, body_rpr = _template_row_fmt(template_tbl, 1, 0)
    if body_ppr is None and body_rpr is None:
        return True
    b_jc = body_ppr.find(W + 'jc') if body_ppr is not None else None
    b_center = b_jc is not None and b_jc.get(W + 'val') == 'center'
    b_bold = body_rpr is not None and body_rpr.find(W + 'b') is not None
    return (h_center and not b_center) or (h_bold and not b_bold)


def _apply_cell_paragraph_fmt(p, row_ppr, row_rpr, preserve_emphasis=False):
    """把 row_ppr/row_rpr（样板对应行/列的格式，_template_row_fmt 取来的）整体套到单元格段落 p
    上，替换原有 pPr 与每个 run 的 rPr（R2-M4 的整体覆盖原样保留），但以下几类东西不跟着一起抹掉
    或借用：
      - w:keepNext 永远不从样板借（R3-M1 修复，比 preserve_emphasis 更基础的一条）：keepNext 是
        源内容自己"这一段要不要跟下一段/下一行绑在一起换页"的编辑意图，不是"字体/字号/颜色看起来
        统不统一"这类版式问题——真实样板（例题 4）表格退化成"每行都是一个 keepNext 小标题格、
        没有第二列"，_template_row_fmt 按列 clamp 后每一列都会拿到这唯一一列的格式，把 keepNext
        原样借给整表每一格；改成不论样板这一格有没有 keepNext，新段落的 keepNext 状态永远原样
        照抄源段落自己原来有没有（没有就是没有，不因为样板这一格恰好有就多出来）。
      - 语义 run 属性（_SEMANTIC_RPR_TAGS：下划线/上下标/着重号/删除线，R3-M3 修复）：原 run 有
        这几项时，原样保留到新 rPr 上（新格式里同名的会被原 run 的值覆盖；原 run 没有的不会无端
        生出这几项）。
      - preserve_emphasis=True 时（这一行没有样板表头格式可套，源表自己却有真正的表头强调，见
        _template_header_distinct/_reformat_table_cells）：保留段落原有的居中对齐（pPr/jc，哪怕
        样板这一格自己也带了 jc——原样覆盖回源段落的值，不是"样板没有才补"）与加粗（run 有
        w:b），不因为"样板没有独立表头格式"就把源表真正的表头强调一起抹平。"""
    old_ppr = p.find(W + 'pPr')
    orig_jc, orig_keep_next = None, False
    if old_ppr is not None:
        jc = old_ppr.find(W + 'jc')
        if jc is not None:
            orig_jc = jc.get(W + 'val')
        orig_keep_next = old_ppr.find(W + 'keepNext') is not None
        p.remove(old_ppr)
    new_ppr = copy.deepcopy(row_ppr) if row_ppr is not None else None
    if new_ppr is None and (orig_keep_next or (preserve_emphasis and orig_jc)):
        new_ppr = etree.Element(W + 'pPr')
    if new_ppr is not None:
        p.insert(0, new_ppr)
        kn = new_ppr.find(W + 'keepNext')
        if orig_keep_next and kn is None:
            _insert_ordered(new_ppr, etree.Element(W + 'keepNext'), _PPR_ORDER)
        elif not orig_keep_next and kn is not None:
            new_ppr.remove(kn)
        if preserve_emphasis:
            jc2 = new_ppr.find(W + 'jc')
            if orig_jc:
                if jc2 is None:
                    jc2 = etree.Element(W + 'jc')
                    _insert_ordered(new_ppr, jc2, _PPR_ORDER)
                jc2.set(W + 'val', orig_jc)
            elif jc2 is not None:
                new_ppr.remove(jc2)
    for r in p.iter(W + 'r'):
        old_rpr = r.find(W + 'rPr')
        semantic = []
        orig_bold = False
        if old_rpr is not None:
            semantic = [copy.deepcopy(el) for el in old_rpr if etree.QName(el).localname in _SEMANTIC_RPR_TAGS]
            orig_bold = old_rpr.find(W + 'b') is not None
            r.remove(old_rpr)
        new_rpr = copy.deepcopy(row_rpr) if row_rpr is not None else None
        if not semantic and not (preserve_emphasis and orig_bold) and new_rpr is None:
            continue
        if new_rpr is None:
            new_rpr = etree.Element(W + 'rPr')
        for tag in _SEMANTIC_RPR_TAGS:
            old = new_rpr.find(W + tag)
            if old is not None:
                new_rpr.remove(old)
        for el in semantic:
            _insert_ordered(new_rpr, el, _RPR_ORDER)
        if preserve_emphasis and orig_bold and new_rpr.find(W + 'b') is None:
            _insert_ordered(new_rpr, etree.Element(W + 'b'), _RPR_ORDER)
        r.insert(0, new_rpr)


def _reformat_table_cells(tbl, template_tbl):
    """按样板表头行/表体行的段落格式整体覆盖源表格每个单元格段落的直接格式（R2-M4 修复）：源表格
    多来自不同学校/年份的原件 DOCX，字体、字号、行距、缩进都是原件自己的直接格式（如楷体正文、
    行距 360、首行缩进 200 字符），套进本书后与本书其它表格观感不一致，光靠 sanitize_table_styles
    清理样式引用清不掉（这些是没有走样式、直接写在段落/run 上的属性）。与 build_table_from_rows
    同一口径：第 0 行按样板表头格式，其余行按样板表体格式（样板只有 1 行时表体退回表头）；单元格
    段落的 pPr、每个 run 的 rPr 整体替换成样板对应行/对应列的格式（没有就整体去掉，回默认格式）；
    图片等非文字子元素（w:drawing 等）不受影响，只是它所在的 run 的 rPr 被替换。

    R3-M1/R3-M3 两处修复（金标回归 T2_tbl 实测踩出）：
      1) 不再无条件只取"这一行第一个单元格"的格式套给整行——改按列对应（_template_row_fmt 的
         col_index），样板"首列小标题格+其余列内容格"这类结构不会把小标题格的 keepNext 扩散到
         整行（详见该函数注释）。
      2) 样板本身没有区别于表体的独立表头格式时（_template_header_distinct 判 False，比如例题 4
         这类样板），源表真正的表头行（第 0 行）改用样板表体格式打底，但保留源表自己原有的加粗/
         居中（_apply_cell_paragraph_fmt 的 preserve_emphasis），不因为"样板没有表头格式"就把
         源表真正的表头强调也抹平。
      3) 覆盖 run 格式时保留 w:u/vertAlign/em/strike 这几项语义属性（填空空位、上下标等），不算
         "局部加粗"这类可接受的代价，见 _apply_cell_paragraph_fmt。"""
    trs = tbl.findall(W + 'tr')
    if not trs:
        return
    n_template_rows = len((template_tbl.findall(W + 'tr') if template_tbl is not None else []))
    has_header = _template_header_distinct(template_tbl)
    for ri, tr in enumerate(trs):
        if ri == 0 and (has_header or n_template_rows < 2):
            t_row = 0
        elif n_template_rows >= 2:
            t_row = 1
        else:
            t_row = 0
        preserve = ri == 0 and not has_header and n_template_rows >= 1
        for ci, tc in enumerate(tr.findall(W + 'tc')):
            row_ppr, row_rpr = _template_row_fmt(template_tbl, t_row, ci)
            for p in tc.findall(W + 'p'):
                _apply_cell_paragraph_fmt(p, row_ppr, row_rpr, preserve_emphasis=preserve)


def apply_template_tblpr(new_tblpr, template_tbl):
    """套样板表格的边框/cellMar/布局；宽度：本表已有 tblW 就保留（贴合本表实际列内容），没有才借
    样板的 tblW。供 build_table_from_rows（rows 数组生成的表格自己没有源宽度）使用；从原件 DOCX
    复制的表格改用下面的 apply_template_tblpr_for_source（R2-M4：源表格自带宽度，规格要求改用
    样板宽度、按比例缩放，不是"没有才借"）。"""
    if template_tbl is None:
        return
    t_tblpr = template_tbl.find(W + 'tblPr')
    if t_tblpr is None:
        return
    for tag in (W + 'tblBorders', W + 'tblCellMar', W + 'tblLayout', W + 'tblLook'):
        old = new_tblpr.find(tag)
        tnode = t_tblpr.find(tag)
        if tnode is not None:
            if old is not None:
                new_tblpr.remove(old)
            new_tblpr.append(copy.deepcopy(tnode))
    if new_tblpr.find(W + 'tblW') is None:
        tw = t_tblpr.find(W + 'tblW')
        if tw is not None:
            new_tblpr.insert(0, copy.deepcopy(tw))


def _template_target_width_twips(template_tbl):
    """样板表格该借给源表格的总宽度，统一换算成 dxa（twips）绝对值（R3-m4 修复）：旧版直接
    `int(t_tw.get('w'))` 不看 w:type，遇到样板 tblW 是 pct（百分之几，w 是"万分之一"单位，5000=
    100%）时会把这个百分数当成 twips 用（真实样板 5000 被当成 5000 twips≈8.8cm，比实际版心窄
    得多）；遇到 auto/nil（Word 按内容自动布局，没有显式宽度，本书 15 张、哲学 19 张、选必二
    144 张表格都是这种）时直接 return（旧版判断 target_w<=0 才 return，可 auto 的 w 属性本就
    可能缺失/是 0），源表格原有的过宽 tblGrid 完全不缩放。改成三态都算出一个具体的 dxa 值：
    dxa 原样用；pct 按"这个百分比 × 兜底总宽"换算（本工具没有去读文档的 sectPr 页边距，用
    DEFAULT_TABLE_WIDTH_TWIPS 这个全书表格宽度量级做近似，比不缩放/按 pct 数值当 twips 用都更
    接近真实版心）；auto/nil/无法解析统一退到兜底总宽——不再"没有才借""借不到就不缩放"，缩放
    这件事本身不能跳过。"""
    if template_tbl is None:
        return DEFAULT_TABLE_WIDTH_TWIPS
    t_tblpr = template_tbl.find(W + 'tblPr')
    t_tw = t_tblpr.find(W + 'tblW') if t_tblpr is not None else None
    if t_tw is None:
        return DEFAULT_TABLE_WIDTH_TWIPS
    w_type = t_tw.get(W + 'type') or 'dxa'
    raw = t_tw.get(W + 'w')
    try:
        raw_val = int(raw) if raw is not None else 0
    except ValueError:
        raw_val = 0
    if w_type == 'dxa' and raw_val > 0:
        return raw_val
    if w_type == 'pct' and raw_val > 0:
        return max(1, round(raw_val / 5000 * DEFAULT_TABLE_WIDTH_TWIPS))
    return DEFAULT_TABLE_WIDTH_TWIPS  # auto/nil/缺失/非正值


def apply_template_tblpr_for_source(new_tblpr, template_tbl, tbl):
    """R2-M4 修复：源表格（从原件 DOCX 复制）先套 apply_template_tblpr 的边框/cellMar/布局，
    宽度再无条件改用样板换算出的总宽（不是"没有才借"——源表格几乎总是自带 tblW，旧版因此从不
    生效，真实原件实测 gridCol 总宽 9742 twips 超出版心 9298，fixed 布局下表格会伸进页边距）；
    w:tblGrid 的每个 gridCol、每个单元格的 tcW 按"样板总宽 / 源表格总宽"的比例统一缩放——按
    比例而不是按列位置对应，避免合并单元格（gridSpan）导致列数与 gridCol 数对不上。新 tblW 统一
    写成 type="dxa"（R3-m4 修复：不再照抄样板 tblW 的原始 type——旧版 pct 样板会把百分数类型的
    tblW 原样复制过来，跟按绝对值缩放过的 gridCol/tcW 混在一起，"tblW=100%"与"gridCol 合计只有
    5000 twips"两个数字互相矛盾，Word 按哪个算都不对）。

    R3-m3 顺手修复：源表格的 w:tblpPr（浮动表定位）原样删除——样板表格（书稿里的表格）都是正常
    随文流动的表，浮动表的绝对定位/环绕在书稿版式下没有意义，原样保留会让表格脱离正文位置（全书
    245 张原件表格里 43 张是浮动表，见回执 known_limits：只影响其中 1 张有实际内容的浮动表）。"""
    apply_template_tblpr(new_tblpr, template_tbl)
    tblppr = new_tblpr.find(W + 'tblpPr')
    if tblppr is not None:
        new_tblpr.remove(tblppr)
    target_w = _template_target_width_twips(template_tbl)
    old_tw = new_tblpr.find(W + 'tblW')
    if old_tw is not None:
        new_tblpr.remove(old_tw)
    new_tblpr.insert(0, etree.Element(W + 'tblW', {W + 'w': str(target_w), W + 'type': 'dxa'}))
    grid = tbl.find(W + 'tblGrid')
    if grid is None:
        return
    cols = grid.findall(W + 'gridCol')
    widths = []
    for c in cols:
        try:
            widths.append(int(c.get(W + 'w') or 0))
        except ValueError:
            widths.append(0)
    total = sum(widths)
    if total <= 0:
        return
    ratio = target_w / total
    for c, w in zip(cols, widths):
        c.set(W + 'w', str(max(1, round(w * ratio))))
    for tc in tbl.iter(W + 'tc'):
        tcpr = tc.find(W + 'tcPr')
        tcw = tcpr.find(W + 'tcW') if tcpr is not None else None
        if tcw is not None and tcw.get(W + 'w'):
            try:
                old_w = int(tcw.get(W + 'w'))
            except ValueError:
                continue
            tcw.set(W + 'w', str(max(1, round(old_w * ratio))))


def _r_attrs(el):
    return [(k, v) for k, v in el.attrib.items() if k.startswith(R_NS) and v]


def _regen_wp14_ids(dr):
    """R3-m11 修复（R2-m11 只补了 pic:cNvPr，这半条一直没修）：wp:inline/wp:anchor 上的
    wp14:anchorId/editId 是 Word 自己配的一对 GUID 式编号，原件里这两个 id 只保证在原件自己的
    文档内唯一；表格从原件复制进本书后，这两个属性原样带过来，可能和本书自己已有的图形 id 撞号。
    docPr/cNvPr 的 id 已经在调用点重新分配（R2-m11），这里补上 wp14 这一对——用 8 字节随机十六
    进制拼一个新的、大小写沿用 Word 习惯（全大写），两者本就该互不相干、各自随机即可，不需要
    像 docPr/cNvPr 那样彼此一致。"""
    for tag in ('anchorId', 'editId'):
        if dr.get(WP14_NS + tag) is not None:
            dr.set(WP14_NS + tag, os.urandom(4).hex().upper())


def rebuild_table_rels(tbl, src, media_ctx, id_alloc, report_media):
    """把复制进来的表格里所有 r: 命名空间引用改绑到目标文档新建的关系上（B2 修复：写后"rel 完整性"
    复核之前一直是死代码，本函数本身才是真正堵住"外来 r:id 被静默错绑"这个洞的地方）：
      - a:blip（r:embed/r:link）、v:imagedata（r:id）——图片：从原件取字节另落新 media 成员/rId；
        所在 wp:anchor 转 wp:inline（M1/M5），docPr id 用 id_alloc 重新分配、全文唯一（M1）。
      - w:hyperlink r:id——仅当原件关系是 TargetMode="External"（外部 URL）才能安全重建：在目标
        文档新增同一 URL 的 External 关系；Internal 超链接（指向原件自己包内的部件，如书签/脚注）
        在目标文档里无法解析，Abort。
      - 其余任何带 r: 命名空间属性的元素（OLE 对象、自定义 XML 引用等）——本工具不认识就不能装作
        安全，一律 Abort，不静默复制（fix_hint 原话）。
    """
    for el in list(tbl.iter()):
        for attr, old_rid in _r_attrs(el):
            local = attr[len(R_NS):]
            if el.tag == A_NS + 'blip' and local in ('embed', 'link'):
                target = src.rels.get(old_rid)
                if not target:
                    raise Abort(f'表格内图片关系 {old_rid} 在原件 {src.path.name} 里找不到目标')
                data = src.media_bytes(target)
                ext = Path(target).suffix.lstrip('.') or 'png'
                new_rid = media_ctx.add_image(data, ext)
                el.set(attr, new_rid)
                dr = _enclosing_drawing(el)
                was_anchor = dr is not None and dr.tag == WP_NS + 'anchor'
                if was_anchor:
                    dr = _anchor_to_inline(dr)
                docpr_id = None
                if dr is not None:
                    docpr = dr.find(WP_NS + 'docPr')
                    if docpr is not None:
                        docpr_id = id_alloc.docpr_id()
                        docpr.set('id', str(docpr_id))
                    # R2-m11 修复：pic:cNvPr 的 id 原先沿用原件自己的编号，没有跟 docPr 一起重新
                    # 分配——与 docPr id 一样都可能和目标文档已有的 id 冲突。两者按惯例本就该一致，
                    # 这里让它们共用同一个新分配的 id。
                    cnvpr = dr.find(f'.//{PIC_NS}cNvPr')
                    if cnvpr is not None and docpr_id is not None:
                        cnvpr.set('id', str(docpr_id))
                    _regen_wp14_ids(dr)
                report_media.append({'kind': 'image', 'from': f'{src.path.name}:{target}',
                                      'new_rid': new_rid, 'bytes': len(data),
                                      'sha256': dl.sha256_bytes(data), 'docpr_id': docpr_id,
                                      'source_layout': 'anchor' if was_anchor else 'inline',
                                      'anchor_converted': was_anchor})
            elif el.tag == VML_NS + 'imagedata' and local == 'id':
                target = src.rels.get(old_rid)
                if not target:
                    raise Abort(f'表格内 VML 图片关系 {old_rid} 在原件 {src.path.name} 里找不到目标')
                data = src.media_bytes(target)
                ext = Path(target).suffix.lstrip('.') or 'png'
                new_rid = media_ctx.add_image(data, ext)
                el.set(attr, new_rid)
                # R2-m1 修复：VML v:imagedata 没有 wp:docPr 这个 DrawingML 概念（老式图片没有等价
                # 的编号机制），report 条目原先缺 docpr_id 这个键，被 verify_output 的
                # `m['docpr_id']` 直接取值时 KeyError；统一带上这个键、值为 None，与图片条目的
                # 字段集合保持一致，下游按 .get('docpr_id') 取值即可安全跳过。
                report_media.append({'kind': 'image', 'from': f'{src.path.name}:{target}',
                                      'new_rid': new_rid, 'bytes': len(data), 'docpr_id': None,
                                      'sha256': dl.sha256_bytes(data), 'note': 'VML v:imagedata（老式图片）'})
            elif el.tag == W + 'hyperlink' and local == 'id':
                rmode = src.rel_mode.get(old_rid)
                rtarget = src.rels.get(old_rid)
                if rmode != 'External' or not rtarget:
                    raise Abort(f'表格内超链接关系 {old_rid} 不是外部链接（TargetMode!=External）或找不到'
                                f'目标，本工具无法安全重建，整批中止（见 B2）')
                rtype = src.rel_types.get(old_rid) or REL_HYPERLINK_TYPE
                new_rid = media_ctx.add_external_rel(rtype, rtarget)
                el.set(attr, new_rid)
                report_media.append({'kind': 'hyperlink', 'from': f'{src.path.name}:{old_rid}',
                                      'new_rid': new_rid, 'target': rtarget})
            else:
                raise Abort(f'表格内出现本工具不支持重建的关系引用：{el.tag} {attr}={old_rid}'
                            f'（无法安全带入目标文档，整批中止，见 B2）')


def build_table_from_source(src_tbl, template_tbl, target_name_to_id, src, media_ctx, id_alloc, report_media):
    """从原件 DOCX 复制表格。顺序：清 bookmark/拒文本框 -> sanitize_table_styles（表级 tblStyle
    按名字改绑或删，R2-B1）-> apply_template_tblpr_for_source（边框/cellMar/布局 + 样板宽度按比例
    缩放，R2-M4）-> _reformat_table_cells（单元格段落/run 整体套样板表头/表体格式，R2-M4）->
    rebuild_table_rels（图片/超链接关系重建，B2）。格式相关的三步（sanitize/tblpr/reformat）必须
    在 rebuild_table_rels 之前：rebuild_table_rels 只认 r: 命名空间引用，不受格式覆盖影响，顺序
    对它没有影响，放最后单纯是让"结构变换"与"关系重建"两类操作分开、各自独立可读。"""
    tbl = copy.deepcopy(src_tbl)
    for tag in ('.//' + W + 'bookmarkStart', './/' + W + 'bookmarkEnd'):
        for x in tbl.findall(tag):
            x.getparent().remove(x)
    textboxes = [el for el in tbl.iter() if etree.QName(el).localname == 'txbxContent']
    if textboxes:
        raise Abort(f'原件表格内含 {len(textboxes)} 个文本框（w:txbxContent），本工具不支持复制文本框'
                    f'内容（已知限制，见回执 known_limits），整批中止')
    sanitize_table_styles(tbl, target_name_to_id, src.style_type_name())
    tblpr = tbl.find(W + 'tblPr')
    if tblpr is None:
        tblpr = etree.Element(W + 'tblPr')
        tbl.insert(0, tblpr)
    apply_template_tblpr_for_source(tblpr, template_tbl, tbl)
    _reformat_table_cells(tbl, template_tbl)
    # R3-m2 修复：嵌套表格（单元格里还有一个 w:tbl）原先完全没走 sanitize_table_styles/
    # _reformat_table_cells——两个函数都只看 tbl 自己的直接子节点（find/findall 不递归），嵌套表格
    # 因此既没有按名字改绑 tblStyle（R2-B1 那个"styleId 在不同文档里可能是完全不同类型/名字的
    # 样式"的坑，嵌套表格一样会踩，真实原件实测 4 处嵌套 tblStyle 撞号），单元格格式也不统一。
    # 这里对每个嵌套表格补做样式改绑与单元格格式统一——不套 apply_template_tblpr_for_source 的
    # 宽度缩放（嵌套表格通常是紧贴父格宽度的小表，套整页宽的样板宽度会显著变形，比不缩放更糟；
    # 保留嵌套表格自己的 tblGrid/tblW，只统一"看得见的格式"这一层，与外层表格同一套安全考虑，
    # 只是不缩放宽度）。
    for nested in tbl.findall('.//' + W + 'tbl'):
        sanitize_table_styles(nested, target_name_to_id, src.style_type_name())
        _reformat_table_cells(nested, template_tbl)
    rebuild_table_rels(tbl, src, media_ctx, id_alloc, report_media)
    return tbl


def build_table_from_rows(rows, template_tbl):
    if not rows or not all(isinstance(r, list) and r for r in rows):
        raise Abort('table.rows 必须是非空的二维数组')
    tbl = etree.Element(W + 'tbl')
    tblpr = etree.SubElement(tbl, W + 'tblPr')
    apply_template_tblpr(tblpr, template_tbl)
    ncols = max(len(r) for r in rows)
    # R3-m4 修复：总宽统一走 _template_target_width_twips（按 dxa/pct/auto 三态换算，见该函数），
    # 不再直接读 apply_template_tblpr 已经原样复制过来的样板 tblW——那份可能是 pct 类型（数值是
    # 万分之一，不是 twips），会把百分数误当成极窄的绝对宽度。这里算完之后覆盖掉 tblpr 里的
    # tblW，统一以 dxa 类型写出。
    total_w = _template_target_width_twips(template_tbl)
    old_tw = tblpr.find(W + 'tblW')
    if old_tw is not None:
        tblpr.remove(old_tw)
    tblpr.insert(0, etree.Element(W + 'tblW', {W + 'w': str(total_w), W + 'type': 'dxa'}))
    colw = max(1, total_w // ncols)
    grid = etree.SubElement(tbl, W + 'tblGrid')
    for _ in range(ncols):
        etree.SubElement(grid, W + 'gridCol', {W + 'w': str(colw)})
    # B1/R3-M1 修复：样板表格第 0 行（表头）与其余行（表体）的格式分开取，且按列对应（复用
    # _template_row_fmt/_template_header_distinct，与 _reformat_table_cells 同一套逻辑、不重复
    # 实现——必修三真实表格表头整行加粗、表体不加粗，统一套第一格会把表体也一起加粗（审查 r1
    # evidence：T1b 输出 128-133 段全部加粗）；样板首列是小标题格时也不该把它的格式扩散到其余列
    # （R3-M1，见 _template_row_fmt 注释）。样板只有 1 行、或没有独立表头格式时，表头行也退回
    # 表体格式（rows[] 是作者自己新写的表格，没有"源表自己的表头强调"要保留，不需要
    # _apply_cell_paragraph_fmt 的 preserve_emphasis 分支）。
    n_template_rows = len(template_tbl.findall(W + 'tr')) if template_tbl is not None else 0
    has_header = _template_header_distinct(template_tbl)
    for ri, row in enumerate(rows):
        t_row = 0 if (ri == 0 and (has_header or n_template_rows < 2)) else min(1, max(n_template_rows - 1, 0))
        tr = etree.SubElement(tbl, W + 'tr')
        for ci in range(ncols):
            text = row[ci] if ci < len(row) else ''
            row_ppr, row_rpr = _template_row_fmt(template_tbl, t_row, ci)
            tc = etree.SubElement(tr, W + 'tc')
            tcpr = etree.SubElement(tc, W + 'tcPr')
            etree.SubElement(tcpr, W + 'tcW', {W + 'w': str(colw), W + 'type': 'dxa'})
            p = etree.SubElement(tc, W + 'p')
            if row_ppr is not None:
                p.append(row_ppr)  # _template_row_fmt 已经是新分配的深拷贝，可直接挂
            r = etree.SubElement(p, W + 'r')
            if row_rpr is not None:
                r.append(row_rpr)
            t = etree.SubElement(r, W + 't')
            t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            t.text = text
    return tbl


# ------------------------------------------------------------------ 写出：新增成员（docx_lib.write_docx
# 只能替换已有成员，做不到"新增 word/media/imageN.ext + 改 rels + 改 Content_Types"这件事，这里薄封装
# 一个写出函数，保持与 docx_lib.write_docx 同等的安全承诺：原子写出（同目录临时文件 + os.replace）、
# 写后重开逐成员核对（未点名的原有成员必须逐字节不变、成员顺序不变、新增成员集合与预期一致、
# document.xml 能重新解析）。
def _write_with_new_media(d, out, extra_members, new_media):
    out = Path(out)
    new_doc = d.document_xml()
    repl = {dl.DOC_XML: new_doc}
    repl.update(extra_members or {})
    fd, tmp = tempfile.mkstemp(prefix='.block_insert_', suffix='.docx', dir=str(out.parent))
    os.close(fd)
    try:
        with zipfile.ZipFile(d.path) as zin, zipfile.ZipFile(tmp, 'w') as zout:
            existing = set()
            for info in zin.infolist():
                existing.add(info.filename)
                data = repl.get(info.filename)
                if data is None:
                    data = zin.read(info.filename)
                zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
                zi.compress_type = info.compress_type
                zi.external_attr = info.external_attr
                zi.create_system = info.create_system
                zout.writestr(zi, data)
            missing = set(repl) - existing
            if missing:
                raise ValueError(f'要替换的成员在原包里不存在：{sorted(missing)}')
            dup = set(new_media) & existing
            if dup:
                raise ValueError(f'新增成员与已有成员重名：{sorted(dup)}')
            for name, data in (new_media or {}).items():
                zi = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                zi.compress_type = zipfile.ZIP_DEFLATED
                zout.writestr(zi, data)
        changed = []
        with zipfile.ZipFile(d.path) as zin, zipfile.ZipFile(tmp) as zchk:
            zin_names = [i.filename for i in zin.infolist()]
            chk_names = [i.filename for i in zchk.infolist()]
            if chk_names[:len(zin_names)] != zin_names:
                raise ValueError('写后原有成员顺序被打乱')
            if set(chk_names) - set(zin_names) != set(new_media or {}):
                raise ValueError('写后新增成员集合与预期不符')
            for info in zin.infolist():
                a, b = zin.read(info.filename), zchk.read(info.filename)
                if a != b:
                    if info.filename not in repl:
                        raise ValueError(f'未点名的成员被改动：{info.filename}')
                    changed.append(info.filename)
            for name, data in (new_media or {}).items():
                if zchk.read(name) != data:
                    raise ValueError(f'新增成员写入后字节不符：{name}')
            etree.fromstring(zchk.read(dl.DOC_XML))
        os.replace(tmp, out)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return {'out': str(out.resolve()), 'sha256': dl.sha256_file(out), 'bytes': out.stat().st_size,
            'changed_members': changed, 'new_members': sorted(new_media or {})}


# ------------------------------------------------------------------ 锚点解析（题块由 ap.zones_of 现算，
# 即 bh.walk 的结果，与 d.paras 同一下标空间——不信任 block_index 的 p_range，见文件头"口径"）
def resolve_insert_anchor(blocks, anchor):
    keys = [k for k in ('after_block', 'before_block', 'method_end') if k in anchor]
    if len(keys) != 1:
        raise Abort('anchor 必须且只能给 after_block/before_block/method_end 之一')
    kind = keys[0]
    spec = anchor[kind] or {}
    if kind in ('after_block', 'before_block'):
        want = spec.get('title_contains')
        if not want:
            raise Abort(f'anchor.{kind} 缺 title_contains')
        hits = [b for b in blocks if want in (b['title'] or '')]
        if len(hits) != 1:
            cand = [{'title': b['title'], 'title_i': b['title_i']} for b in hits[:20]]
            raise Abort(f'anchor.{kind}.title_contains="{want}" 命中 {len(hits)} 个题块（须恰好 1 个）'
                        f'；候选：{cand}')
        b = hits[0]
        pos_p = block_extent_end(b) if kind == 'after_block' else b['title_i']
        return kind, b, pos_p
    mc = spec.get('method_contains')
    if not mc:
        raise Abort('anchor.method_end 缺 method_contains')
    nc = spec.get('node_contains')
    hits = [b for b in blocks if mc in (b.get('method') or '') and (not nc or nc in (b.get('node') or ''))]
    if not hits:
        raise Abort(f'anchor.method_end：method_contains="{mc}"'
                    f'{"、node_contains=" + repr(nc) if nc else ""} 未命中任何题块')
    # M3 修复：以前不管 hits 里混了几个不同的(节点,考法)分组都直接取全书 title_i 最大的一个，静默落
    # 到"最后一个匹配"——method_contains 不给 node_contains 收窄时，"考法1"这种短串在811页合订本里
    # 命中几十个不同节点下的同名考法，实测 20 组，工具却当没看见。改成按 (node, method) 分组，命中
    # 的组数必须恰好 1 个，否则 Abort 并列出候选组，逼插入单作者用 node_contains 收窄。
    groups = {}  # 普通 dict：Python 3.7+ 保留插入顺序，不用另引入 collections.OrderedDict
    for b in hits:
        groups.setdefault((b.get('node'), b.get('method')), []).append(b)
    if len(groups) != 1:
        cand = [{'node': k[0], 'method': k[1], 'n_blocks': len(v)} for k, v in list(groups.items())[:20]]
        raise Abort(f'anchor.method_end：method_contains="{mc}"'
                    f'{"、node_contains=" + repr(nc) if nc else ""} 命中 {len(groups)} 个不同的'
                    f'(节点,考法)分组（须恰好 1 个，用 node_contains 收窄）；候选：{cand}')
    (only_group,) = groups.values()
    b = max(only_group, key=lambda x: x['title_i'])
    return kind, b, block_extent_end(b)


# ------------------------------------------------------------------ 规划（check 与 apply 共用：全部
# 解析、校验、构造新元素都在这一步完成，且完全不触碰 d.root——新元素是游离的 lxml 节点，图片/表格
# 的媒体字节也只是准备在 MediaCtx 里，写不写盘由调用方决定；check 模式因此能做到"定位、模板匹配、
# 图表构造、词表"这些不落盘就能做的校验，和 apply 走的是同一份代码、同等彻底。R3-m8 修复：check
# 与 apply 并不是"完全一样彻底"——写后复核（verify_output：block_index 重新认块、媒体/表格计数、
# 栏目齐全、restore 豁免段写后区位、python-docx 重新打开）必须读一份真的写出来的文件才能做，
# check 不落盘就做不到这些，见 cmd_check 只到 plan_inserts 这一步；同一条插入单 check 给出"能插"
# 后，apply 仍可能在写后复核栏目缺失/media 计数不符而中止——这不是 bug，是 check 天然做不到的那
# 一层，共同约定第 4 条"默认只检查、不写"的代价，不是本工具的疏漏（旧注释曾写"完全一样彻底"，
# 与实际不符，已改正，见 R3-m8）。
def plan_inserts(d, prof_dict, unit, media_ctx):
    _close_source_cache()  # m16 修复：不带入上一次调用打开过的原件（见 _close_source_cache 注释）
    with zipfile.ZipFile(d.path) as z:
        styles_xml = etree.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None
    styles_obj = bh.Styles(styles_xml)
    target_name_to_id = _name_to_id_index(_style_type_name_map(styles_xml))  # R2-B1：表格样式按名字映射
    _, _, blocks, _ = ap.zones_of(d, prof_dict)
    stem_pos = _stem_position_index(d, styles_obj, prof_dict, blocks)  # R3-B1：全书位置信号，见该函数
    tag_list, wlist = bh._word_lists(prof_dict)
    allow = bh.cfg(prof_dict, 'student_text.allow_contexts', {}) or {}
    existing_titles = {bh.norm(b['title']) for b in blocks}
    id_alloc = IdAllocator(d.root)
    plans, seen_ids = [], set()
    for ins in unit.get('inserts') or []:
        iid = ins.get('id') or f'I{len(plans) + 1:03d}'
        if iid in seen_ids:
            raise Abort(f'插入单里 id 重复：{iid}')
        seen_ids.add(iid)
        title = ins.get('title')
        if not title or not title.strip():
            raise Abort(f'{iid}：缺 title')
        if bh.norm(title) in existing_titles:
            raise Abort(f'{iid}：标题 "{title}" 已在书稿里存在——本工具不做已插入检测/幂等重放，'
                        f'请先确认是否真的还没插入')
        sz = ins.get('source_zone')
        if sz not in ('restore', 'approved_edit'):
            raise Abort(f'{iid}：source_zone 只能是 restore/approved_edit')
        if not (ins.get('reason') or '').strip():
            raise Abort(f'{iid}：必须给非空 reason')
        # M4 修复：title 原先在任何 source_zone 下都不过词表（旧版只查 content 里 source/teaching/
        # rubric 三种文字，title 是另一条完全没检查的通道）；豁免口径与 source 角色文字相同——只在
        # restore（逐字取自原件/原稿）时豁免，approved_edit 仍要过词表。
        if sz != 'restore':
            hit = ap._forbidden_hit(title, tag_list, wlist, allow)
            if hit:
                raise Abort(f'{iid}：标题命中禁用词表 {hit[0]}:{hit[1]}')
        anchor = ins.get('anchor') or {}
        kind, anchor_block, pos_p = resolve_insert_anchor(blocks, anchor)
        before = kind == 'before_block'
        anchor_el = _top_level_anchor(d.body, d.paras[pos_p])
        tb_spec = ins.get('template_block') or {}
        want = tb_spec.get('title_contains')
        if not want:
            raise Abort(f'{iid}：template_block 缺 title_contains')
        tb_hits = [b for b in blocks if want in (b['title'] or '')]
        if len(tb_hits) != 1:
            raise Abort(f'{iid}：template_block.title_contains="{want}" 命中 {len(tb_hits)} 个题块'
                        f'（须恰好 1 个）')
        template_block = tb_hits[0]
        template_title_p = d.paras[template_block['title_i']]
        content = ins.get('content') or []
        if not content:
            raise Abort(f'{iid}：content 不能为空')

        fallbacks, media_report, elements, exempt_elems = [], [], [], []
        title_p = build_title_paragraph(title, template_title_p, styles_obj, id_alloc, fallbacks)
        elements.append(('title', title_p))
        if sz == 'restore':
            # R2-M1 修复第二道防线：restore 豁免的不止 content 里的 source 段，标题本身在
            # sz=='restore' 时也整段豁免词表（见上方 `if sz != 'restore': 查 title 词表`）——
            # 一并记下来，写出后核实它真的落在 title/source 区，不是只信插入单自己声明。
            exempt_elems.append(title_p)
        img_tpl = _UNSET
        # R2-B2 残留修复：模板题块自己"标题之后第一段"的段号——多半是块自己的开场【题目】标签，
        # 见 find_role_template 的 exclude_idx 参数说明。只在 ci>0 的 content 条目上排除它。
        tb_paras = template_block.get('paras') or []
        opening_idx = min(tb_paras) if tb_paras else None
        # R3-B1 修复：这条插入单自己 content 列表里"最后一个 role=='source' 条目"的下标——与
        # _stem_position_index 对全书既有段落用的是同一个位置信号（块内最后一个 source 段多半是
        # 设问，不是材料），content 列表本身就是这条新题块未来的段落顺序，同一条规则原样套用。
        last_source_ci = None
        for _ci2, _it2 in enumerate(content):
            if _it2.get('role') == 'source':
                last_source_ci = _ci2
        for ci, item in enumerate(content):
            role = item.get('role')
            where = f'{iid}.content[{ci}]'
            if role in ('source', 'teaching', 'rubric'):
                runs = item.get('runs')
                txt = ''.join(r.get('text', '') for r in runs) if runs else item.get('text')
                if not txt:
                    raise Abort(f'{where}：role={role} 缺非空 text/runs')
                exempt = role == 'source' and sz == 'restore'
                if not exempt:
                    hit = ap._forbidden_hit(txt, tag_list, wlist, allow)
                    if hit:
                        raise Abort(f'{where}：新文字命中禁用词表 {hit[0]}:{hit[1]}')
                kind = item.get('kind')
                if kind is not None and kind not in _KIND_TO_SHAPE:
                    raise Abort(f'{where}：kind 只能是 "stem"（设问）或 "material"（材料）')
                if kind is not None:
                    # R3-B1 修复（fix_hint 建议的显式字段）：文字判据 + 位置信号已经把全书 452/453
                    # 个真实设问都能正确认出（见 _para_shape/_stem_position_index），但插入单作者
                    # 如果在同一条 insert 里连着给两个"看起来都像设问收尾"的 source 段（比如同时给
                    # 一段引语开头的真设问和一段对照用的"结合材料……"），位置信号只认最后一个——
                    # 这里给作者一个不看文字、不看位置、直接指定的逃生口，跳过下面的自动判断。
                    content_shape = _KIND_TO_SHAPE[kind]
                else:
                    is_stem_pos = role == 'source' and ci == last_source_ci
                    content_shape = _para_shape_ctx(txt, is_stem_pos)
                tp, _sid, tp_shape = find_role_template(
                    d, styles_obj, prof_dict, template_block, role,
                    item.get('like'), item.get('style'), content_shape, fallbacks,
                    exclude_idx=(None if ci == 0 else opening_idx), stem_pos=stem_pos)
                new_p = build_text_paragraph(item, tp, styles_obj, content_shape=content_shape,
                                              template_shape=tp_shape)
                elements.append(('para', new_p))
                if exempt:
                    exempt_elems.append(new_p)
            elif role == 'image':
                if img_tpl is _UNSET:
                    img_tpl = find_image_template(d, template_block, fallbacks)
                tpl = img_tpl
                max_cx = None
                if tpl is not None:
                    cx0, cy0 = None, None
                    dr = tpl.find(f'.//{WP_NS}inline') if tpl is not None else None
                    if dr is not None:
                        cx0, cy0 = _drawing_extent(dr)
                    max_cx = cx0
                max_cx = max_cx or DEFAULT_MAX_IMG_EMU
                needs_local_check = source_layout = None
                if 'from' in item:
                    src = open_source(_resolve_ref(item['from'].get('docx')))
                    rid_src, target, cx, cy, was_anchor = locate_source_image(src, item['from'])
                    data = src.media_bytes(target)
                    ext = Path(target).suffix.lstrip('.') or 'png'
                    if cx is None or cy is None:
                        px_w, px_h = _image_px_size(data)
                        cx, cy = px_w * 9525, px_h * 9525
                    src_note = f'{src.path.name}:{target}'
                    source_layout = 'anchor' if was_anchor else 'inline'  # M5：原件浮动/内嵌标记
                elif 'file' in item:
                    fp = Path(_resolve_ref(item['file']))
                    if not fp.exists():
                        raise Abort(f'{where}：图片文件不存在：{fp}')
                    data = fp.read_bytes()
                    ext = fp.suffix.lstrip('.') or 'png'
                    px_w, px_h = _image_px_size(data)
                    cx, cy = px_w * 9525, px_h * 9525
                    src_note = str(fp)
                    needs_local_check = '需本地核图'  # M5：显式图片文件（多半来自 PDF 原件裁图）一律标注
                else:
                    raise Abort(f'{where}：image 须给 from 或 file 之一')
                cx, cy = _fit_extent(cx, cy, item.get('width_cm'), max_cx)
                rid = media_ctx.add_image(data, ext)
                docpr_id = id_alloc.docpr_id()
                p = build_image_paragraph(tpl, rid, cx, cy, item.get('name') or src_note, docpr_id)
                elements.append(('para', p))
                # R2-m8 修复：table 内图片的 report 条目本来就带 anchor_converted（B2/M1 修复时
                # 加的），顶层图片条目这里漏了同一个字段——两条路径都"原件是 wp:anchor 就统一转
                # inline"（build_image_paragraph 总是重新构造 wp:inline，不看原件是不是浮动图），
                # 字段应该一致，方便 summary 汇总（见 cmd_check/cmd_apply 的 _media_summary）。
                media_report.append({'kind': 'image', 'from': src_note, 'new_rid': rid,
                                      'bytes': len(data), 'sha256': dl.sha256_bytes(data),
                                      'extent_emu': [cx, cy], 'docpr_id': docpr_id,
                                      'source_layout': source_layout, 'needs_local_check': needs_local_check,
                                      'anchor_converted': (source_layout == 'anchor')})
            elif role == 'table':
                tpl_tbl = find_table_template(d, template_block, d.body, fallbacks)
                if 'from' in item:
                    src = open_source(_resolve_ref(item['from'].get('docx')))
                    src_tbl = locate_source_table(src, item['from'])
                    tbl = build_table_from_source(src_tbl, tpl_tbl, target_name_to_id, src, media_ctx,
                                                   id_alloc, media_report)
                    media_report.append({'kind': 'table', 'from': f'{src.path.name}',
                                          'rows': len(src_tbl.findall(W + 'tr'))})
                elif 'rows' in item:
                    rows = item['rows']
                    # M4 修复：rows 单元格文字原先在任何 source_zone 下都不过词表——approved_edit
                    # 场景下作者自己拼的表格文字应该像 source 正文一样受词表约束，豁免口径与 source
                    # 相同（只在 restore 时豁免）。
                    if sz != 'restore':
                        for row in rows:
                            for cell in row:
                                hit = ap._forbidden_hit(str(cell), tag_list, wlist, allow)
                                if hit:
                                    raise Abort(f'{where}：表格文字命中禁用词表 {hit[0]}:{hit[1]}'
                                                f'（单元格：{bh.clip(str(cell), 20)}）')
                    tbl = build_table_from_rows(rows, tpl_tbl)
                    media_report.append({'kind': 'table', 'from': 'rows[]', 'rows': len(rows)})
                else:
                    raise Abort(f'{where}：table 须给 from 或 rows 之一')
                elements.append(('table', tbl))
            else:
                raise Abort(f'{where}：role 未知：{role!r}')
        plans.append({'id': iid, 'title': title, 'anchor_kind': kind, 'before': before,
                       'anchor_el': anchor_el, 'anchor_block_title': anchor_block['title'],
                       'template_block_title': template_block['title'], 'elements': elements,
                       'fallbacks': fallbacks, 'media': media_report, 'source_zone': sz,
                       'reason': ins.get('reason'), 'exempt_elems': exempt_elems})
    return plans


def _resolve_ref(p):
    """插入单里的原件/图片路径：绝对路径原样；相对路径按当前工作目录解析（调用方负责给出能定位到
    的路径——本工具不读题库/原材料索引，找哪份原件是插入单作者的事）。"""
    q = Path(p).expanduser()
    return str(q if q.is_absolute() else Path.cwd() / q)


# ------------------------------------------------------------------ 落地（挂到树上；写盘在 cmd_apply）
def do_insert(d, plans):
    """把 plan_inserts() 已经构造好的游离元素挂到 d.root 上。同一批多条 insert 互不依赖——锚点用的
    是 lxml 元素引用（plan_inserts 阶段就定死），不是段号，后续 insert 的挂载不会让前面 insert 的
    锚点失效（与 apply_patch.do_apply 用元素身份而不是段号定位同一个道理）。

    返回"新段落元素"列表本身（不是 id() 集合）——lxml 的 Python 代理对象只在被某处 Python 引用
    持有期间才保证同一节点重复访问拿到同一个对象、id() 稳定；`e.iter(W+'p')` 拿到的表格内段落若
    只在这里取一次 id() 就丢掉引用，函数返回后就可能被回收、id() 被后续对象复用，等 cmd_apply 里
    d.refresh() 后再按 id() 反查会认错人（实测踩过这个坑：新增段落数对不上、被误判"未点名段落
    变了"）。调用方必须把返回的列表一直攥在手里（不能只留 id() 集合），直到算完 touched_after。

    m3 修复：同一批里多条 insert 共用同一个 after_block/method_end 锚点时，原先每条都从锚点元素
    本身往后挂（`prev = anchor_el`），第二条会插在第一条前面（落位与插入单顺序相反，实测
    bm_order.py：A1(例题90)、A2(例题91) 依次插入后输出顺序是 91、90）。改成用 after_cursor 按
    锚点元素的身份记住"上一条插到哪个元素为止"，后续同锚点的 insert 接着往后挂，保持插入单顺序。
    before_block 不需要这个修复：`anchor_el.addprevious(e)` 每次都紧贴同一个 anchor_el 插入，
    后一条自然落在前一条和 anchor_el 之间，顺序天然正确（已用真实多条 insert 验证，见测试）。"""
    new_paras = []
    after_cursor = {}  # id(anchor_el) -> 上一条已插入的最后一个元素（跨 insert 保持顺序，见上）
    for plan in plans:
        anchor_el = plan['anchor_el']
        els = [e for _, e in plan['elements']]
        if plan['before']:
            for e in els:
                anchor_el.addprevious(e)
        else:
            prev = after_cursor.get(id(anchor_el), anchor_el)
            for e in els:
                prev.addnext(e)
                prev = e
            after_cursor[id(anchor_el)] = prev
        for kind, e in plan['elements']:
            if kind == 'table':
                new_paras.extend(e.iter(W + 'p'))
            else:
                new_paras.append(e)
    return new_paras


# ------------------------------------------------------------------ 写后复核
def _scan_rids(root):
    """全文所有带 r: 命名空间属性的引用（B2 修复：原先按 tag 白名单 W+'blip'/W+'imagedata' 找，两个
    命名空间都写错了——a:blip 在 drawingml 命名空间、v:imagedata 在 VML 命名空间，W 命名空间下根本
    没有这两个 tag，旧实现在真实输出上恒返回 0，"写后复核 rel 完整性"名存实亡。改成不看 tag，直接
    扫全树任意元素的任意 r: 命名空间属性——这样才能真的核到 w:hyperlink r:id 这类关系。"""
    out = []
    for el in root.iter():
        for attr, val in el.attrib.items():
            if attr.startswith(R_NS) and val:
                out.append(val)
    return out


def verify_output(out_path, prof_dict, orig_paras, touched_after, plans, render_check, problems,
                   exempt_after=None):
    """重开输出文件逐条核对；硬失败（unchanged 段落被动、关系/成员缺失、docPr 冲突、书签不配对、
    Content_Types 缺覆盖、python-docx 打不开、新题块未被认成恰好 1 个、media/tables 计数不符、
    栏目缺失、restore 豁免段写后未落在 source/title 区且命中词表）append 进 problems 供调用方删
    输出、整批中止（R2-M1/R2-M2 修复：block_index 的 missing 与 restore 写后区位原先都只写报告
    不中止，见下文两处）；--render-check 只作报告，不构成硬失败（云端渲染引擎只能粗查，见
    cmd_apply 对失败结果的处理——降级为退出码 1，不删输出）。

    touched_after：新段落在"写出前"的段号集合（在写入前的活树 d.paras 上按元素身份换算得到，见
    cmd_apply）——写出后重新打开是一棵全新的树，元素身份对不上，只能靠段号做桥梁；write_docx/
    _write_with_new_media 只是把同一棵内存树序列化，不改变段落顺序/数量，所以这个段号在写出后的
    d_out.paras 上仍然有效（与 apply_patch.cmd_apply 的 idx_of_mem 技巧同一个道理）。exempt_after
    同样是"写出前换算好的段号"，但按 (plan_id, index) 记录，供写后区位复核用。"""
    rep = {}
    d_out = dl.open_docx(out_path)
    bad = dl.unchanged_paragraphs(orig_paras, d_out.paras, set(), touched_after)
    if bad:
        problems.append('未点名段落发生变化')
        rep['unchanged_check'] = bad[:20]
    with zipfile.ZipFile(out_path) as z:
        names = set(z.namelist())
        ct_root = etree.fromstring(z.read(CONTENT_TYPES_PATH))
        rels_root = (etree.fromstring(z.read(RELS_PATH)) if RELS_PATH in names else None)
        rel_map = {r.get('Id'): r.get('Target') for r in rels_root} if rels_root is not None else {}
        rel_mode_map = ({r.get('Id'): r.get('TargetMode') for r in rels_root}
                         if rels_root is not None else {})
        rids = _scan_rids(d_out.root)
        missing_rel, missing_target = [], []
        for rid in set(rids):
            tgt = rel_map.get(rid)
            if tgt is None:
                missing_rel.append(rid)
                continue
            if rel_mode_map.get(rid) == 'External':
                continue  # 外部关系（超链接等）的 Target 是 URL，不是包内部件，不能按包路径核
            p = tgt.lstrip('/') if tgt.startswith('/') else 'word/' + tgt
            if p not in names:
                missing_target.append({'rid': rid, 'target': p})
        if missing_rel:
            problems.append('部分 r:embed/r:id 在 rels 里找不到关系')
            rep['missing_rel'] = missing_rel
        if missing_target:
            problems.append('部分关系目标成员不在包里')
            rep['missing_target'] = missing_target
        media_exts = {Path(n).suffix.lstrip('.').lower() for n in names if n.startswith('word/media/')}
        ct_exts = {c.get('Extension', '').lower() for c in ct_root if c.tag == CT_NS + 'Default'}
        ct_overrides = {c.get('PartName') for c in ct_root if c.tag == CT_NS + 'Override'}
        uncovered = [e for e in media_exts if e and e not in ct_exts
                     and not any(o and o.endswith('.' + e) for o in ct_overrides)]
        if uncovered:
            problems.append('word/media 里有扩展名未在 Content_Types 里注册')
            rep['content_types_uncovered'] = sorted(uncovered)
    all_docpr = [el.get('id') for el in d_out.root.iter(WP_NS + 'docPr')]
    new_docpr = [m['docpr_id'] for pl in plans for m in pl['media'] if m.get('kind') == 'image']
    dup_new = [i for i in new_docpr if all_docpr.count(str(i)) > 1]
    if dup_new:
        problems.append('新分配的 docPr id 与全文其他 id 冲突')
        rep['docpr_conflict'] = dup_new
    bm_start = {(b.get(W + 'id'), b.get(W + 'name')) for b in d_out.root.iter(W + 'bookmarkStart')}
    bm_end_ids = [b.get(W + 'id') for b in d_out.root.iter(W + 'bookmarkEnd')]
    start_ids = [i for i, _ in bm_start]
    if sorted(start_ids) != sorted(bm_end_ids):
        problems.append('bookmarkStart/End 不配对')
    names_seen = [n for _, n in bm_start]
    if len(names_seen) != len(set(names_seen)):
        problems.append('bookmarkStart 的 name 有重复')
    try:
        import docx as _docx_lib
        _docx_lib.Document(str(out_path))
        rep['python_docx_open'] = 'ok'
    except Exception as e:
        problems.append('python-docx 打不开输出文件')
        rep['python_docx_open'] = f'失败：{e}'
    # M2 修复：block_index 认块与 media/tables 计数原先只写进报告、不中止——即便新题块被认成"不是
    # 恰好 1 个块"或图/表数对不上，工具照样退出 0。规格把这条列为写后复核项，改成硬失败：found_
    # blocks != 1 或 media/tables 计数对不上都 append 进 problems，让调用方删输出、整批中止。表内
    # 图片（relink_table_rels 追加的 media 条目）现在也带 kind='image'（同一处 B2/M1 修复），不再
    # 漏计导致带图表格永远 media_match=false。
    block_report = []
    try:
        idx = bidx.build_index(str(out_path), prof_dict)
        by_title = {}
        for b in idx['blocks']:
            by_title.setdefault(bh.norm(b['title']), []).append(b)
        for pl in plans:
            hits = by_title.get(bh.norm(pl['title']), [])
            n_img = sum(1 for m in pl['media'] if m.get('kind') == 'image')
            n_tbl = sum(1 for m in pl['media'] if m.get('kind') == 'table')
            entry = {'id': pl['id'], 'title': pl['title'], 'found_blocks': len(hits)}
            if len(hits) != 1:
                problems.append(f'{pl["id"]}：block_index 认出的题块数是 {len(hits)}（须恰好 1 个）')
            else:
                blk = hits[0]
                media_match = len(blk.get('media') or []) == n_img
                tables_match = len(blk.get('tables') or []) == n_tbl
                entry.update({'schema': blk.get('schema'), 'missing': blk.get('missing'),
                              'media_count': len(blk.get('media') or []), 'tables_count': len(blk.get('tables') or []),
                              'media_expect': n_img, 'tables_expect': n_tbl,
                              'media_match': media_match, 'tables_match': tables_match})
                if not media_match:
                    problems.append(f'{pl["id"]}：block_index 认出的图片数 {len(blk.get("media") or [])} '
                                     f'与插入单预期 {n_img} 不符')
                if not tables_match:
                    problems.append(f'{pl["id"]}：block_index 认出的表格数 {len(blk.get("tables") or [])} '
                                     f'与插入单预期 {n_tbl} 不符')
                # R2-M2 修复：missing 原先只写进报告不中止（r1 M2 只把 found_blocks/media/tables
                # 改成硬失败，栏目缺失这一项漏了，docstring 也还写着"只作报告"，与已修的另外两项
                # 自相矛盾）。block_index 的 missing 是这道新题块缺了哪些必须栏目（比如
                # 【答案落点】【细则说明】），规格明确要求"栏目齐全"是写后复核项、失败即中止。
                if blk.get('missing'):
                    problems.append(f'{pl["id"]}：block_index 认出的题块缺少栏目：{blk["missing"]}')
            block_report.append(entry)
    except Exception as e:
        problems.append(f'block_index 复核异常：{e}')
        block_report = [{'error': str(e)}]
    rep['block_index_check'] = block_report
    # R2-M1 修复第二道防线：restore 豁免只在 plan_inserts 阶段看插入单自己声明的
    # role=="source"/标题 + source_zone=="restore"，不代表这段新文字写出后真的落在 source/title
    # 区——find_role_template 的角色桶限制（见该函数）已经堵住了"style 覆盖跳到教学桶"这一具体
    # 绕法，这里再按写出后重新打开的文档重新跑一遍 bh.walk 取真实区位，与 apply_patch 的写后
    # 区位复核同一套逻辑，防未知的其他绕法（比如错误的锚点让豁免段实际插进了教学区）。
    if exempt_after:
        zone_after, _, _, _ = ap.zones_of(d_out, prof_dict)
        tag_list, wlist = bh._word_lists(prof_dict)
        allow = bh.cfg(prof_dict, 'student_text.allow_contexts', {}) or {}
        leak = []
        for pid, i in exempt_after:
            zi = zone_after[i] if i < len(zone_after) else None
            if zi in ('source', 'title'):
                continue
            txt = dl.para_text(d_out.paras[i])
            hit = ap._forbidden_hit(txt, tag_list, wlist, allow)
            if hit:
                leak.append({'id': pid, 'index': i, 'zone': zi, 'hit': f'{hit[0]}:{hit[1]}',
                             'text': bh.clip(txt, 40)})
        if leak:
            problems.append('restore 豁免的段落写后未落在 source/title 区，且新文字命中禁用词表')
            rep['wordlist_leak'] = leak
    if render_check:
        rep['render_check'] = _render_check(out_path)
    return rep


def _render_check(out_path):
    import shutil
    import subprocess
    soffice = shutil.which('soffice')
    if not soffice:
        return {'ran': False, 'note': '本环境无 soffice，跳过'}
    outdir = tempfile.mkdtemp(prefix='block_insert_render_')
    try:
        r = subprocess.run([soffice, '--headless', '--convert-to', 'pdf', '--outdir', outdir, str(out_path)],
                            capture_output=True, timeout=180)
        pdf = Path(outdir) / (Path(out_path).stem + '.pdf')
        ok = r.returncode == 0 and pdf.exists() and pdf.stat().st_size > 0
        return {'ran': True, 'ok': ok, 'returncode': r.returncode,
                'pdf_bytes': pdf.stat().st_size if pdf.exists() else 0,
                'note': '云端渲染引擎（字体与本机不同），只作粗查：能否转出非空 PDF'}
    except Exception as e:
        return {'ran': True, 'ok': False, 'error': str(e)}
    finally:
        shutil.rmtree(outdir, ignore_errors=True)


# ------------------------------------------------------------------ --renumber：串联调用 layout_prepare
# （子进程调用独立命令行工具，不 import 它的内部函数、不复制编号/考法题数逻辑——按共同约定第 1/3 条，
# 插入会让例题编号、考法"（N题）"需要重排，这活直接交给 layout_prepare.py repair）。
def _shell_cmd(cmd):
    """m10 修复：next_command 原先用 ' '.join(cmd) 拼字符串，路径/参数里有空格或 shell 特殊字符
    时照抄重跑会被拆错；改用 shlex.quote 逐项转义。"""
    import shlex
    return ' '.join(shlex.quote(str(c)) for c in cmd)


def run_renumber(profile_path, docx_path, out_path, expect_sha, report_path):
    import subprocess
    # m7 修复：--renumber 原先额外带了 --keepnext，超出"编号/考法题数"的范围——插入动作本身不该
    # 触发全书 keepNext 修补（那是 layout_prepare 自己另一条独立的排版体检项，与本工具"插入后重排
    # 编号/考法题数"这一件事无关，见审查 r1 m7）。
    cmd = [sys.executable, str(_SK / 'layout_prepare.py'), 'repair',
           '--docx', str(docx_path), '--out', str(out_path), '--numbering', '--method-counts',
           '--profile', str(profile_path), '--expect-sha', expect_sha]
    if report_path:
        cmd += ['--report', str(report_path)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        return {'ok': False, 'error': str(e), 'cmd': cmd, 'next_command': _shell_cmd(cmd)}
    ok = r.returncode == 0
    next_cmd = None
    if not ok:
        # m10 修复：原样重跑会撞上这次已经写出（或至少占用过）的 --out 路径；换一个还没被占用的
        # 路径再给出重跑命令，不沿用旧的 out_path。
        retry_out = Path(out_path).with_name(Path(out_path).stem + '_retry' + Path(out_path).suffix)
        retry_cmd = list(cmd)
        oi = retry_cmd.index('--out')
        retry_cmd[oi + 1] = str(retry_out)
        next_cmd = _shell_cmd(retry_cmd)
    return {'ok': ok, 'returncode': r.returncode, 'stdout': r.stdout[-4000:], 'stderr': r.stderr[-4000:],
            'cmd': cmd, 'next_command': next_cmd}


# ------------------------------------------------------------------ --health（与 apply_patch 同口径：
# 按 (check,rule,题块,栏目,摘录) 的多重集合做输入/输出差集，不是简单去重）
def _fkey(f):
    where = f.get('where') or {}
    return (f['check'], f['rule'], where.get('example'), where.get('part'), f.get('label'), f.get('excerpt'))


def health_diff(parent_docx, out_docx, prof_dict):
    import collections
    in_h = bh.run_health(str(parent_docx), profile=prof_dict)
    out_h = bh.run_health(str(out_docx), profile=prof_dict)
    in_f = [f for f in in_h['findings'] if f['level'] == 'FAIL']
    out_f = [f for f in out_h['findings'] if f['level'] == 'FAIL']
    in_count = collections.Counter(_fkey(f) for f in in_f)
    seen, new_fail = collections.Counter(), []
    for f in out_f:
        k = _fkey(f)
        if seen[k] < in_count.get(k, 0):
            seen[k] += 1
            continue
        seen[k] += 1
        new_fail.append(f)
    return {'input_FAIL': in_h['summary']['FAIL'], 'output_FAIL': out_h['summary']['FAIL'],
            'new_FAIL': new_fail[:30], 'new_FAIL_count': len(new_fail)}


# ------------------------------------------------------------------ 报告写出（移植 apply_patch._own_json
# 的覆盖口径，R2-M3 修复：原先无条件 overwrite=True，已批准的补丁/插入单、构建/baseline_*.json
# 这类"真实文件未变证明"都能被 --report 静默覆盖，与文件头/回执声称的"同 apply_patch 同口径"不符）
def _own_json(path, mode=None):
    """path 已存在时，判断本工具的 --report 能不能覆盖它。只允许覆盖"本工具自己以前写的同类
    报告"：tool=='block_insert' 且（不给 mode 时不比对，给了就要相同）。schema 是
    baodian_patch_v1（apply_patch 补丁）或 baodian_insert_v1（本工具自己的插入单）的文件，不论
    是否已批准，一律拒绝覆盖——覆盖范围要跟 apply_patch._own_json 一样窄：--report 只应该写
    "本工具自己的报告"，撞上别的 json（哪怕看着像自己人）也该老实拒绝。不是合法 JSON、不是
    dict，同样拒绝（保守：拿不准就不许覆盖，比误删更安全）。"""
    try:
        p = Path(path)
        if not p.exists():
            return True
        obj = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(obj, dict):
            return False
        if obj.get('schema') in ('baodian_patch_v1', 'baodian_insert_v1'):
            return False
        return obj.get('tool') == 'block_insert' and (mode is None or obj.get('mode') == mode)
    except Exception:
        return False


def _atomic_write_text(path, text):
    """R2-M3 修复：原先直接 out.write_text(...)，中途失败会留一个半写的文件；改临时文件 +
    os.replace 原子写出（同 _write_with_new_media 对 docx 的写出承诺一致）。"""
    path = Path(path)
    fd, tmp = tempfile.mkstemp(prefix='.block_insert_report_', suffix='.json', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _write_report(path, prof_dict, obj, guard_inputs=None):
    if not path:
        return None
    report_prof = dict(prof_dict or {})
    report_prof['frozen'] = False
    overwrite = _own_json(path, obj.get('mode'))
    out = dl.guard_write(path, report_prof, inputs=guard_inputs or [], kind='.json', overwrite=overwrite)
    _atomic_write_text(out, json.dumps(obj, ensure_ascii=False, indent=2, default=str))
    return str(out)


def _base_report(mode, unit, d_sha, prof_dict, docx_path, insert_path):
    # m4 修复：inputs 原先只给 docx 一份 SHA，插入单本身与插入单里引用的原件 DOCX 都没有 SHA——
    # 共同约定第 7 条要求"路径＋SHA"。插入单的 SHA 在这里补上；引用的原件散在各条 insert 的 content
    # 里，openn 过程用 _source_cache 收集，写在 cmd_apply/cmd_check 算完 plan 之后再补进 inputs。
    return {'tool': 'block_insert', 'version': TOOL_VERSION, 'mode': mode,
            'inputs': {'docx': str(docx_path), 'docx_sha256': d_sha, 'insert': str(insert_path),
                       'insert_sha256': dl.sha256_file(insert_path),
                       'insert_schema': unit.get('schema'), 'insert_book': unit.get('book'),
                       'source_docs': []},
            'profile': {'book_id': prof_dict.get('book_id'), 'frozen': bool(prof_dict.get('frozen'))}}


def _source_docs_used():
    """本次规划过程中通过 open_source() 打开过的原件 DOCX 路径＋SHA（m4：报告 inputs 需要列出）。"""
    return [{'path': str(src.path), 'sha256': dl.sha256_file(src.path)} for src in _source_cache.values()]


def _source_docs_used_and_close():
    """取完快照立即关闭句柄、清空缓存（m16 修复，见 _close_source_cache）。cmd_check/cmd_apply
    每条退出路径在给 rep['inputs']['source_docs'] 赋值时都改调用这个，取代裸的 _source_docs_
    used()——赋值之后两个函数都不会再读 _source_cache，关闭是安全的。"""
    docs = _source_docs_used()
    _close_source_cache()
    return docs


def _media_summary(plans):
    """R2-m8 修复：汇总 needs_local_check（多半来自 PDF 原件裁图，需要人工核对）与
    anchor_converted（原件是浮动图、本工具统一转成内嵌图）这两项数量——r1 M5 的 fix_hint 已经
    要求"summary 汇总 needs_local_check"，回执当时只在逐条明细里留了字段、没有做汇总；
    anchor_converted 原先只在表格内图片的明细里有、顶层图片明细缺这个字段（已在 plan_inserts
    里补上，见该处 R2-m8 注释），这里统一按有这个字段的条目汇总。check 与 apply 两个子命令的
    summary 共用这一份，字段名与已有的 media_images/media_tables/fallbacks 保持一致，只新增
    needs_local_check/anchor_converted 两个键。"""
    imgs = [m for pl in plans for m in pl['media'] if m.get('kind') == 'image']
    tbls = [m for pl in plans for m in pl['media'] if m.get('kind') == 'table']
    return {
        'media_images': len(imgs), 'media_tables': len(tbls),
        'needs_local_check': sum(1 for m in imgs if m.get('needs_local_check')),
        'anchor_converted': sum(1 for m in imgs if m.get('anchor_converted')),
        'fallbacks': sum(len(pl['fallbacks']) for pl in plans),
    }


def _plan_summary(plans):
    out = []
    for pl in plans:
        out.append({'id': pl['id'], 'title': pl['title'], 'anchor_kind': pl['anchor_kind'],
                     'anchor_block_title': pl['anchor_block_title'],
                     'template_block_title': pl['template_block_title'],
                     'n_content': len(pl['elements']) - 1, 'fallbacks': pl['fallbacks'],
                     'media': pl['media'], 'source_zone': pl['source_zone'], 'reason': pl['reason']})
    return out


# ------------------------------------------------------------------ 子命令
_UNIT_KEYS = {'schema', 'book', 'parent_docx_sha256', 'approved_by', 'approval_ref', 'inserts'}
_INSERT_KEYS = {'id', 'anchor', 'template_block', 'title', 'source_zone', 'reason', 'content'}
_ANCHOR_TOP_KEYS = {'after_block', 'before_block', 'method_end'}
_BLOCK_SPEC_KEYS = {'title_contains'}
_METHOD_SPEC_KEYS = {'method_contains', 'node_contains'}
_CONTENT_KEYS = {'role', 'text', 'runs', 'like', 'style', 'from', 'file', 'width_cm', 'name', 'rows', 'kind'}
_FROM_KEYS = {'docx', 'rid', 'index', 'near_text', 'table_index', 'contains'}


def _check_keys(d, allowed, where):
    if not isinstance(d, dict):
        raise Abort(f'{where}：必须是 JSON 对象（实际是 {type(d).__name__}）')
    extra = sorted(set(d) - allowed)
    if extra:
        raise Abort(f'{where}：出现未知字段 {extra}（写错字段名会被静默忽略——比如把 "like" 拼成 '
                    f'"lik"，回退到默认匹配还照样能跑，只是不是作者想要的那段——见 R2-m9 修复；'
                    f'允许的字段：{sorted(allowed)}）')


def _check_type(v, types, where, allow_none=True):
    """R3-m7 修复：字段类型不对时原先没有专门校验，直接被后续逻辑当成对的类型去用，抛出的是
    Python 自己的英文异常（如 "'list' object has no attribute 'get'"、"'int' object has no
    attribute 'strip'"），退出码 2 本身没错但提示不是中文。这里在正式处理前先按类型挡一道，
    类型不对就给出中文原因；allow_none=True 时值缺失（None）不算错（"要不要给"由各处 Abort
    自己管，这里只管"给了但类型不对"）。"""
    if v is None and allow_none:
        return
    if isinstance(v, bool) and bool not in types:  # bool 是 int 的子类，不能被 int 类型悄悄接住
        raise Abort(f'{where}：类型应为 {"/".join(t.__name__ for t in types)}，实际是 bool')
    if not isinstance(v, types):
        raise Abort(f'{where}：类型应为 {"/".join(t.__name__ for t in types)}，实际是 '
                    f'{type(v).__name__}')


_RUN_KEYS = {'text', 'bold', 'color'}


def _validate_unit_schema(unit):
    """R2-m9/R3-m7 两轮修复：插入单原先没有正式的键名/类型校验。R2-m9 堵了"键名写错=静默忽略"
    （比如 "like" 拼成 "lik"）；R3-m7 补上"键名对、类型错"这一层——顶层不是对象、inserts 元素
    不是对象、title/like/style/kind/name/file 不是字符串、width_cm 不是数字、runs 不是对象数组、
    runs 内部键名错、anchor/template_block 给了非对象——这些原先都会一路带着错类型走到深处，
    抛 Python 自己的英文异常（退出码 2 没错，提示不是中文，见审查 r3 probe_errors.txt）。这里对
    顶层、每条 insert、anchor 及其内层 spec、template_block、每个 content 条目、image/table 的
    "from" 子对象、runs 数组逐项做键名+类型校验；不校验业务取值范围（source_zone 的取值、role
    的取值等各自处理逻辑里已经在查）。"""
    _check_keys(unit, _UNIT_KEYS, '插入单顶层')
    inserts = unit.get('inserts')
    if not isinstance(inserts, list):
        raise Abort(f'插入单顶层.inserts：必须是数组（实际是 {type(inserts).__name__}）')
    for ii, ins in enumerate(inserts):
        if not isinstance(ins, dict):
            raise Abort(f'inserts[{ii}]：必须是 JSON 对象（实际是 {type(ins).__name__}）')
        iid = ins.get('id') or f'inserts[{ii}]'
        _check_keys(ins, _INSERT_KEYS, f'{iid}')
        _check_type(ins.get('title'), (str,), f'{iid}.title')
        _check_type(ins.get('source_zone'), (str,), f'{iid}.source_zone')
        _check_type(ins.get('reason'), (str,), f'{iid}.reason')
        anchor = ins.get('anchor')
        if anchor is not None:
            _check_keys(anchor, _ANCHOR_TOP_KEYS, f'{iid}.anchor')
            for k in ('after_block', 'before_block'):
                if k in anchor:
                    _check_keys(anchor[k], _BLOCK_SPEC_KEYS, f'{iid}.anchor.{k}')
                    _check_type(anchor[k].get('title_contains'), (str,), f'{iid}.anchor.{k}.title_contains',
                                allow_none=False)
            if 'method_end' in anchor:
                _check_keys(anchor['method_end'], _METHOD_SPEC_KEYS, f'{iid}.anchor.method_end')
        tb = ins.get('template_block')
        if tb is not None:
            _check_keys(tb, _BLOCK_SPEC_KEYS, f'{iid}.template_block')
            _check_type(tb.get('title_contains'), (str,), f'{iid}.template_block.title_contains',
                        allow_none=False)
        content = ins.get('content')
        if content is not None and not isinstance(content, list):
            raise Abort(f'{iid}.content：必须是数组（实际是 {type(content).__name__}）')
        for ci, item in enumerate(content or []):
            where = f'{iid}.content[{ci}]'
            _check_keys(item, _CONTENT_KEYS, where)
            for k in ('like', 'style', 'text', 'name', 'kind', 'file'):
                _check_type(item.get(k), (str,), f'{where}.{k}')
            _check_type(item.get('width_cm'), (int, float), f'{where}.width_cm')
            frm = item.get('from')
            if frm is not None:
                _check_keys(frm, _FROM_KEYS, f'{where}.from')
                for k in ('docx', 'near_text', 'rid', 'contains'):
                    _check_type(frm.get(k), (str,), f'{where}.from.{k}')
                for k in ('index', 'table_index'):
                    _check_type(frm.get(k), (int,), f'{where}.from.{k}')
            runs = item.get('runs')
            if runs is not None:
                if not isinstance(runs, list):
                    raise Abort(f'{where}.runs：必须是数组（实际是 {type(runs).__name__}）')
                for ri, rs in enumerate(runs):
                    rwhere = f'{where}.runs[{ri}]'
                    if not isinstance(rs, dict):
                        raise Abort(f'{rwhere}：必须是 JSON 对象（实际是 {type(rs).__name__}）')
                    _check_keys(rs, _RUN_KEYS, rwhere)
                    _check_type(rs.get('text'), (str,), f'{rwhere}.text')
                    _check_type(rs.get('bold'), (bool,), f'{rwhere}.bold')
                    _check_type(rs.get('color'), (str,), f'{rwhere}.color')


def _load_unit(path):
    p = Path(path)
    if not p.exists():
        raise Abort(f'插入单文件不存在：{p}')
    try:
        text = p.read_text(encoding='utf-8')
    except OSError as e:
        # R2-m6 修复：文件存在但读不出来（权限、编码等）时 Path.read_text 抛英文 OSError；
        # 上面先判是否存在只覆盖"不存在"这一种，这里兜住其余读取失败，一并转中文。
        raise Abort(f'插入单文件读取失败：{p}（{e}）')
    try:
        unit = json.loads(text)
    except json.JSONDecodeError as e:
        raise Abort(f'插入单不是合法 JSON（第 {e.lineno} 行第 {e.colno} 列）：{p}')
    # R3-m7 修复：顶层不是 JSON 对象（比如整份文件是一个数组）时，原先直接 unit.get('schema') 会
    # 抛英文 AttributeError（'list' object has no attribute 'get'）；这里先挡一道给中文提示。
    if not isinstance(unit, dict):
        raise Abort(f'插入单顶层必须是 JSON 对象（实际是 {type(unit).__name__}）：{p}')
    if unit.get('schema') != 'baodian_insert_v1':
        raise Abort('插入单 schema 不是 baodian_insert_v1')
    if not unit.get('parent_docx_sha256'):
        raise Abort('插入单缺 parent_docx_sha256（必填）')
    if not unit.get('inserts'):
        raise Abort('插入单 inserts 为空')
    _validate_unit_schema(unit)
    return unit


def _require_docx_exists(path):
    # R3-m7 修复（顺手）：--docx 指向不存在的文件时，dl.open_docx 内部按 zipfile/Path 打开会抛
    # 英文 FileNotFoundError（"[Errno 2] No such file or directory: …"），main() 的通用异常处理
    # 只在前面加"错误："三个字，后面仍是英文——这是 Skill 模块（docx_lib）自己的异常文字，不能改
    # docx_lib，只能在调用点先挡一道。
    if not Path(path).exists():
        raise Abort(f'父稿 DOCX 不存在：{path}')


def cmd_check(args):
    unit = _load_unit(args.insert)
    prof_dict = _load_prof(args, unit)
    _require_docx_exists(args.docx)
    d = dl.open_docx(args.docx, expect_sha256=unit['parent_docx_sha256'])
    rep = _base_report('check', unit, d.sha256, prof_dict, args.docx, args.insert)
    guard_inputs = [args.docx, args.insert]
    media_ctx = MediaCtx(d)
    try:
        plans = plan_inserts(d, prof_dict, unit, media_ctx)
    except Abort as e:
        rep['aborted'] = True
        rep['reason'] = str(e)
        rep['inputs']['source_docs'] = _source_docs_used_and_close()
        _write_report(args.report, prof_dict, rep, guard_inputs)
        print('中止：' + str(e), file=sys.stderr)
        return 2
    rep['inputs']['source_docs'] = _source_docs_used_and_close()
    rep['plan'] = _plan_summary(plans)
    rep['summary'] = dict(_media_summary(plans), total=len(plans), pending=len(plans))
    _write_report(args.report, prof_dict, rep, guard_inputs)
    print(json.dumps(rep['summary'], ensure_ascii=False))
    return 1 if plans else 0


def cmd_apply(args):
    unit = _load_unit(args.insert)
    prof_dict = _load_prof(args, unit)
    _require_docx_exists(args.docx)
    # 冻结册：--profile 自己声明 frozen 就立即拒绝，不等 plan_inserts 先去解析锚点/模板题块——
    # 冻结册的书往往结构对不上当前 --docx（比如误传别的书），先做完整规划再查冻结反而会被"锚点
    # 找不到"之类的 Abort 抢先，冻结拒绝就测不到、也不该等那么久。detect_profile(docx) 另外按输入
    # 稿路径反查一次（与 apply_patch.cmd_apply 同一道防线），云端 SK 本地 profiles 多半对不上路径、
    # 常年是 None，只作纵深防御，不是这里的主防线。
    if prof_dict.get('frozen'):
        print(f'拒绝写出：{prof_dict.get("title", prof_dict.get("book_id"))} 已冻结'
              f'（{prof_dict.get("frozen_note", "")}）', file=sys.stderr)
        return 3
    try:
        real_prof = detect_profile(args.docx)
    except Exception:
        real_prof = None
    if real_prof is not None and bool(real_prof.get('frozen')):
        print(f'拒绝写出：{real_prof.get("title", real_prof.get("book_id"))} 已冻结'
              f'（{real_prof.get("frozen_note", "")}）', file=sys.stderr)
        return 3
    d = dl.open_docx(args.docx, expect_sha256=unit['parent_docx_sha256'])
    rep = _base_report('apply', unit, d.sha256, prof_dict, args.docx, args.insert)
    guard_inputs = [args.docx, args.insert, args.out]
    media_ctx = MediaCtx(d)
    try:
        plans = plan_inserts(d, prof_dict, unit, media_ctx)
    except Abort as e:
        rep['aborted'] = True
        rep['reason'] = str(e)
        rep['inputs']['source_docs'] = _source_docs_used_and_close()
        _write_report(args.report, prof_dict, rep, guard_inputs)
        print('中止：' + str(e), file=sys.stderr)
        return 2
    rep['inputs']['source_docs'] = _source_docs_used_and_close()
    try:
        out_path = dl.guard_write(args.out, prof_dict, inputs=[args.docx, args.insert], kind='.docx')
    except dl.GuardError as e:
        rep['aborted'] = True
        rep['reason'] = str(e)
        _write_report(args.report, prof_dict, rep, guard_inputs)
        print('拒绝写出：' + str(e), file=sys.stderr)
        return 3
    if args.report:
        try:
            report_prof = dict(prof_dict)
            report_prof['frozen'] = False
            # R2-M3 修复：预检也改用 _own_json 判断能不能覆盖（不再无条件 overwrite=True），跟
            # 后面 _write_report 真正落盘时用的判断一致——预检的意义就是"提前发现会被拒绝"，判断
            # 口径本身不一致就失去了预检的意义。
            dl.guard_write(args.report, report_prof, inputs=guard_inputs, kind='.json',
                            overwrite=_own_json(args.report, 'apply'))
        except dl.GuardError as e:
            print('拒绝写出：' + str(e), file=sys.stderr)
            return 3
    orig_root = etree.fromstring(d.doc_xml_orig)
    orig_paras = dl.para_elements(orig_root.find(W + 'body'))
    new_para_elems = do_insert(d, plans)  # 必须一直攥着这个列表（见 do_insert 注释），不能只留 id()
    # 写出前，在活树上把"新段落"的元素身份换算成段号（写出后重开是全新的树，元素身份对不上，
    # 只能靠段号做桥梁——与 apply_patch.cmd_apply 的 idx_of_mem 同一个道理，见 verify_output 注释）。
    d.refresh()
    new_para_ids = {id(p) for p in new_para_elems}
    touched_after = {i for i, p in enumerate(d.paras) if id(p) in new_para_ids}
    if len(touched_after) != len(new_para_elems):
        raise Abort(f'内部错误：新段落身份换算失败（应 {len(new_para_elems)} 段，换算出 '
                    f'{len(touched_after)} 段），拒绝继续写出')
    # R2-M1 修复第二道防线：把每个 plan 的 exempt_elems（restore 豁免的段落，见 plan_inserts）
    # 也按同一套"元素身份 -> 写出前段号"技巧换算成 (plan_id, 段号)，供 verify_output 写后核实
    # 真实区位。
    exempt_id_to_plan = {id(p): pl['id'] for pl in plans for p in pl.get('exempt_elems') or []}
    exempt_after = [(exempt_id_to_plan[id(p)], i) for i, p in enumerate(d.paras) if id(p) in exempt_id_to_plan]
    extra_members = {}
    # R2-m1 修复：原先只在 new_media 非空时才写 rels/Content_Types，只新增外部关系（表格内超链接、
    # 没有新图片）时 new_media 为空、new_rels 非空，rels 就漏写了——改成两者任一非空都写。
    if media_ctx.new_media or media_ctx.new_rels:
        extra_members[RELS_PATH] = media_ctx.rels_bytes()
        extra_members[CONTENT_TYPES_PATH] = media_ctx.content_types_bytes()
    write_receipt = _write_with_new_media(d, out_path, extra_members, media_ctx.new_media)
    problems = []
    try:
        verify_rep = verify_output(out_path, prof_dict, orig_paras, touched_after, plans,
                                    args.render_check, problems, exempt_after)
    except Exception as e:
        # m6 修复：verify_output 内部除 block_index 复核外没有 try/except，若它自己抛异常（比如
        # zip/xml 读取失败），原先会带着已经写盘的 out_path 直接向外传播、被 main() 的通用异常处理
        # 接住转成退出码 2，但没有人删掉这个已经落盘的输出文件——"整批中止不留输出文件"（共同约定
        # 第 4 条）就破功了。这里补一层 try/except，异常也当成"写后复核不通过"处理：删输出、写
        # aborted 报告、退出码 2。
        Path(out_path).unlink(missing_ok=True)
        rep['aborted'] = True
        rep['reason'] = f'写后复核执行异常：{e}'
        _write_report(args.report, prof_dict, rep, guard_inputs)
        print('中止：写后复核执行异常，已删除输出：' + str(e), file=sys.stderr)
        return 2
    rep['plan'] = _plan_summary(plans)
    rep['output'] = write_receipt
    rep['verify'] = verify_rep
    if problems:
        Path(out_path).unlink(missing_ok=True)
        rep['aborted'] = True
        rep['reason'] = '写后复核不通过：' + '；'.join(problems)
        _write_report(args.report, prof_dict, rep, guard_inputs)
        print('中止：写后复核不通过，已删除输出：' + '；'.join(problems), file=sys.stderr)
        return 2
    final_docx = out_path
    exit_code = 0
    # R2-m3 修复：--render-check 转换失败原先静默——ok=False 时既不提示也不影响退出码，回执甚至
    # 把"缺 writer 组件的转换失败"误记成"环境没有 soffice"。转换真的跑过但失败时，在 stderr 提示
    # 并把退出码提到 1（同共同约定第 6 条"1=发现待处理"，不阻断写出——渲染检查本来就是粗查）。
    rc_info = verify_rep.get('render_check') or {}
    if rc_info.get('ran') and not rc_info.get('ok'):
        exit_code = max(exit_code, 1)
        # R3-m13 修复：note/returncode 原先直接拼在一个 f-string 里，note 有内容、returncode 也有
        # 值时中间没有分隔符，显示成"source file could not be loaded1"这种粘连文字——分开列出。
        rc_bits = [str(rc_info.get('note') or rc_info.get('error') or '').strip(),
                   f'returncode={rc_info.get("returncode")}' if rc_info.get('returncode') is not None else '']
        rc_detail = '；'.join(b for b in rc_bits if b)
        print(f'注意：--render-check 转换失败（{rc_detail}），仅供参考，不阻断写出', file=sys.stderr)
    if args.renumber:
        renum_out = out_path.with_name(out_path.stem + '_renumbered' + out_path.suffix)
        renum_report = out_path.with_name(out_path.stem + '_renumber.json') if args.report else None
        rn = run_renumber(prof_dict.get('_profile_path') or args.profile, out_path, renum_out,
                           write_receipt['sha256'], renum_report)
        rep['renumber'] = rn
        if rn.get('ok'):
            final_docx = renum_out
        else:
            # m2 修复：--renumber 失败原先仍以 exit_code=0 收尾（初始化在这段代码之后），流水线按
            # 退出码会把它当成功放过——插入本身是成功的，但请求的编号/考法题数重排没有完成，属于
            # "发现待处理"，退出码提到 1（同共同约定第 6 条 1 的语义），并在 stderr 给出下一步命令。
            exit_code = 1
            print(f'注意：--renumber 未成功（{rn.get("returncode")}），保留未重排的插入结果；'
                  f'下一条命令：{rn.get("next_command")}', file=sys.stderr)
    if args.health:
        try:
            h = health_diff(args.docx, final_docx, prof_dict)
            rep['health'] = h
            if h['new_FAIL_count']:
                exit_code = max(exit_code, 1)
        except Exception as e:
            # m5 修复：--health 异常原先只记进报告、退出码仍是 0，体检本身有没有跑通被悄悄吞掉。
            # R3-m9 修复：这里原先用 exit_code=2，但插入本身已经写出、写后复核（verify_output）也
            # 已经通过——2 在共同约定第 6 条里是"整批中止"，该语义要求不留输出文件，这里却仍然保留
            # 了已经写好的插入结果，两者不一致。--health 执行异常是"体检这一步没跑成"，不是插入
            # 本身出了问题，改用 1（"发现待处理"）更贴切，且不删除已经通过复核的输出——回执/报告
            # 如实写明"体检未完成"，不谎称体检通过。
            rep['health'] = {'error': str(e)}
            exit_code = max(exit_code, 1)
            print(f'注意：--health 执行异常，体检未完成（不影响已写出的插入结果）：{e}', file=sys.stderr)
    # m4 修复：apply 报告原先没有顶层 summary（check 模式有），也没法一眼看出这批插入的图/表/回退
    # 汇总数——共同约定第 7 条要求"summary、逐条明细"都要有。
    final_sha = write_receipt['sha256'] if final_docx == out_path else dl.sha256_file(final_docx)
    rep['summary'] = dict(
        _media_summary(plans),
        inserts=len(plans),
        renumbered=bool(args.renumber and rep.get('renumber', {}).get('ok')),
        new_FAIL_count=rep.get('health', {}).get('new_FAIL_count'),
        render_check_ok=(rc_info.get('ok') if rc_info.get('ran') else None),
        final_out=str(final_docx), final_sha256=final_sha,
    )
    _write_report(args.report, prof_dict, rep, guard_inputs)
    print(json.dumps({'out': str(final_docx), 'sha256': final_sha}, ensure_ascii=False))
    return exit_code


def main(argv=None):
    ap_ = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap_.add_argument('--debug', action='store_true')
    sub = ap_.add_subparsers(dest='command', required=True)

    c1 = sub.add_parser('check')
    c1.add_argument('--docx', required=True)
    c1.add_argument('--insert', required=True)
    c1.add_argument('--profile')
    c1.add_argument('--report')

    c2 = sub.add_parser('apply')
    c2.add_argument('--docx', required=True)
    c2.add_argument('--insert', required=True)
    c2.add_argument('--out', required=True)
    # m12 修复：apply（写模式）强制要求显式 --profile，不允许回退到插入单 book 字段做名字解析——
    # 见 _load_prof 的注释。check（只读）仍允许省略，退回名字解析风险较小（不落盘）。
    c2.add_argument('--profile', required=True)
    c2.add_argument('--report')
    c2.add_argument('--health', action='store_true')
    c2.add_argument('--renumber', action='store_true')
    c2.add_argument('--render-check', action='store_true')

    args = ap_.parse_args(argv)
    try:
        if args.command == 'check':
            return cmd_check(args)
        if args.command == 'apply':
            return cmd_apply(args)
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
