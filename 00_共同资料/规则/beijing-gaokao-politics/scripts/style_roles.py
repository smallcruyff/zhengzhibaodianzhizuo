#!/usr/bin/env python3
"""样式角色修复（按书册配置运行）：只改 run 的字体、颜色、字号格式（rPr），绝不改文字，暂不支持加粗
（w:b/w:bCs，见 KNOWN_LIMITS）。

背景
    必修三第52批曾因“答案落点蓝字过多”全书返修，耗费约 2.2 亿 token；batch_health 的 check_blue 等
    检查能查出误蓝、字体偏离、单练红绿错位，但过去只能靠人工或一次性脚本逐处改，没有按“样式角色”
    （教学正文/材料区/题面区……应该长什么样）批量核对再批量修的通用工具。本工具补这一环，只做机械的
    格式核对与格式改写，题肢对错、细则取舍等教学判断一律不做，只在 audit 里列 CANDIDATE 交主代理。

    2026-09-24 对抗性审查发现 material_font/stem_teaching_font 只按样式名判定角色，不区分选择题/
    主观题/材料/设问，在已定稿的书上产生大面积误报且被标为可机械修复；本版改为：没有人工登记的显式
    条件角色表（typography.<角色>.rules）时，这两类只做 CANDIDATE 计数，永不 fixable、永不进 plan。
    teach_mis_blue 链路（口径与 bh.check_blue 完全一致，七本书验证过）不受影响，继续可用；同时补上
    themeColor 感知、误蓝修复目标色、apply 端独立重算等修复（详见下文与各函数注释）。

子命令
    audit --docx X [--profile P] [--report r.json]
        只读。分四类：
          teach_mis_blue      教学正文（zone∈teaching/rubric）误用标签蓝——口径与 bh.check_blue 的
                               FAIL 规则“教学正文误蓝”完全一致（标签【…】范围与豁免样式/前缀除外），
                               只是这里把命中落到具体 run 上，供 plan/apply 使用。fixable 要求：run
                               整体在标签范围外、颜色是 run 自己 rPr 里的直接格式（不是从段落/字符样式
                               继承来的设计色，那种一律 CANDIDATE，需人工核实是不是有意设计如分组标题）。
                               目标色 after.color 不再写死 auto：优先取配置的正文色（typography.
                               stem_teaching.color / typography.material.color / typography.colors.
                               body），没有配置就取同段其余非蓝文字 run 的颜色众数，都没有才退回 auto。
          material_font       材料区字体（typography.material）与配置不符。
          stem_teaching_font  题面/教学区（typography.stem_teaching，旧配置叫 stem_options_teaching）
                               字体族或字号（pt）与配置不符。
                               这两类字体角色现在要求配置里给显式条件表 typography.<key>.rules（每条
                               带 kind 题型条件，可选 zone/label，见下）才会做精确判定并允许 fixable/
                               plan；没有这张表时（目前所有 profile 都没有）只按 (ex.kind, zone, label,
                               style) 分组展示观测到的字体/字号，级别 CANDIDATE，fixable 恒 False——
                               不判断对错、不生成 after，纯粹给主代理看“现在长什么样”，据此决定要不要
                               补一张真正的角色表。原因：启发式按样式名猜的单一角色，在不同题型/区位下
                               应有的格式常常不同（例：同一个“题目材料”样式，完整选择题题干按协议要
                               宋体、主观题材料要楷体；同一批 run 也可能被两个角色重复统计），机械按
                               单一目标改写会把符合版式协议的格式改坏。这是本工具最大的已知局限。
          drill_color         单练红色错处/绿色纠正用错位置——直接复用 bh.check_drill 的判定结果
                               （按 bh_rule 原名显式白名单挑出颜色相关的几条，不是按“红/绿/颜色/纠正”
                               这几个字关键词猜，避免漏掉不含这些字的规则名），只做汇总展示；这一类
                               涉及“哪个字/哪个题肢错了”的内容判断，本工具的 plan 不支持为它生成计划。

        typography.<role>.rules（role = material / stem_teaching，本工具建议的新字段，尚未登记进任何
        profile，需要时写进 profile_fields_needed 交主代理确认登记）：
          [{"kind": ["choice"], "zone": ["source"], "label": ["设问"], "styles": ["题目材料"],
            "ea": "Songti SC", "ascii": "Times New Roman", "pt": 10.5}, ...]
          kind 必填（对应 bh.walk 给每个例题块标的 ex['kind']，如 choice/subjective/topic），styles
          必填；zone/label 可选进一步限定。同一个 run 命中多条目标不同的规则记为配置冲突（FAIL，不
          fixable，交主代理裁定），不会二选一瞎猜。

    plan --docx X --audit r.json --rules 规则id,... --out plan.json
        把 audit 报告里选中类别的偏差转成逐 run 修改计划，只读，不改任何书稿。先核对 --docx 的
        SHA256 等于 audit.inputs.docx_sha256（不符按父稿不符中止，退出码 2）。--rules 只接受
        teach_mis_blue，以及本书确实登记了 typography.<key>.rules 时的 material_font/
        stem_teaching_font；否则中止并说明原因。drill_color 从不支持 plan。每条计划带段号、run 序号、
        run 当前文字（逐字，供 apply 核对）、before/after 的 rPr 摘要（只含 color/ea/ascii/pt 这几个
        键，绝不含 text）。

    apply --docx X --plan plan.json --out Y [--expect-sha S] [--health/--no-health，默认开启]
        按计划改 rPr，只改 word/document.xml。**不信任 plan 文件里记的 before/after**：对每条操作，
        在当前书稿上用与 audit 完全相同的判定函数独立重算一遍这个 run 现在的判定，要求重算结果
        fixable 且 after 与计划里记的逐字段相等，否则整批中止——这样即使 plan 文件被篡改（颜色改成
        任意值、混进不支持的字段、把已经改好的 run 再点一遍、把干净的 run 点成误蓝等），也过不了这一
        关，不会带着攻击者写的 after 去改 XML。写后重开核对：全书段落文字与原稿逐段一致（bh.read_docx
        口径的 text，一个字都不许变）、未点名的 run 的 rPr 用 C14N 逐个比对不变、未点名的段落整段
        C14N 不变（docx_lib.unchanged_paragraphs）、其余 ZIP 成员逐字节不变（docx_lib.write_docx 内部
        保证）；任一条不满足，一律整批中止、删掉已写的输出、不留文件。
        写后体检默认跑 batch_health（--no-health 关闭）：按 (check, rule) 逐门比较 FAIL 计数，不是只
        比总数——任何一门比输入多，一律中止、删掉已写的输出（避免“修好一处、别处新增一处误蓝”被总数
        抵消而放过）。颜色/字体在写入时会一并删除 themeColor/themeTint/themeShade 或 eastAsiaTheme/
        asciiTheme，避免 Word 仍按主题色渲染、显得“没修好”。

读写承诺
    - 只读书稿、audit 报告、plan 文件；只写 --report/--out 指定的 .json/.docx，写出前一律经
      docx_lib.guard_write()（冻结册拒绝写、受保护目录只放行 …/协作/候选/<谁>/<批次>/构建/、系统临时
      目录放行）。audit 与 plan 都不写 docx，只有 apply 写。报告只允许覆盖“本工具生成的、mode 与
      docx_sha256 都相同”的旧文件，防止 plan --out 静默覆盖别的 audit 报告。
    - 不改 batch_health.py / docx_lib.py / profile_lib.py / profiles/ 及其他脚本；不运行 collab.py；
      不联网、不起子进程写文件。
    - 判定复用 batch_health：Prof/walk 给每段标 zone/label/ex（含 ex['kind']），check_blue 的蓝色集合
      与标签排除口径原样照抄（bh 没暴露到 run 级，这里薄封装一份到 run 粒度，注释里写明与 check_blue
      的对应关系）；单练红绿错位直接调用 bh.check_drill，不重新判定。

退出码
    0 成功/无待处理（audit：0 处偏差；plan：生成的计划为空；apply：写出且未新增体检 FAIL）
    1 audit 发现偏差（check 语义）；plan 生成的计划非空（仍需主代理批准才能 apply）；
      或 apply --health 后某个检查门新增 FAIL（已中止、已删除输出）
    2 输入/配置错误、或整批中止（父稿 SHA 不符、run 文字不符、计划与独立重算的判定不符、
      计划想改文字或用不支持字段、--rules 里包含不支持 plan 的类别、audit/plan 文件 schema 不对等）
    3 拒绝写出（guard_write 守卫、冻结册、输出与输入同一文件等）
    异常一律转中文提示打印到 stderr，不打印 traceback；--debug 打开时打印。

读取的配置字段（均已有默认值；下列前两组不需要新登记，第三组是本工具的建议新字段）
    - styles.* / structure.* / example_titles / labels_rules.* / column_schemas / section_labels /
      hidden_labels / example_kind_by_labels / drill.* —— 全部转交 batch_health.Prof/walk/collect_drill/
      check_drill 解释，本工具不重复实现。
    - colors.blue、colors.blue_exempt_prefix、colors.blue_exempt_styles、typography.colors.label_blue
      —— teach_mis_blue 判定用，口径照抄 bh.check_blue（bh.cfg 兜底到 bh.DEFAULTS）。
    - typography.stem_teaching.color / typography.material.color / typography.colors.body —— 误蓝
      修复的目标色（按此顺序取第一个有值的）；都没有时退回同段非蓝文字 run 的颜色众数，再没有才 auto。
    - typography.material.{ea,ascii,pt,_style,styles}、
      typography.stem_teaching.{ea,ascii,pt,_style,styles}（或 typography.stem_options_teaching，
      兼容必修二旧命名）—— 没有 .rules 时，仅用于决定 CANDIDATE 扫描范围（不是确定目标）。
    - 【建议新增，尚未登记进任何 profile，profile_fields_needed 里已列】
      typography.material.rules / typography.stem_teaching.rules：按题型/区位给出这个角色在不同条件
      下的目标格式（见上文子命令 audit 一节的例子），是 material_font/stem_teaching_font 能精确判定、
      能生成修改计划的前提；主代理确认后可登记。
"""
import argparse
import copy
import hashlib
import json
import re
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
from profile_lib import detect_profile, load_profile  # noqa: E402
from lxml import etree  # noqa: E402

TOOL = 'style_roles'
VERSION = '0.2.0'
W = bh.W
CJK = bh.CJK
clip = bh.clip
norm_label = bh.norm_label

# CT_RPr 子元素的 schema 顺序（够用的子集）；插入新子元素时按此序找插入点，不打乱既有顺序，
# 避免 Word 因元素顺序不对而报“需要修复”。
RPR_ORDER = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike',
             'outline', 'shadow', 'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish', 'webHidden',
             'color', 'spacing', 'w', 'kern', 'position', 'sz', 'szCs', 'highlight', 'u', 'effect',
             'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs', 'em', 'lang', 'eastAsianLayout',
             'specVanish', 'oMath', 'rPrChange']
ALLOWED_AFTER_FIELDS = {'color', 'ea', 'ascii', 'pt'}
_HEX_COLOR_RE = re.compile(r'^[0-9A-Fa-f]{6}$')

TYPO_KEYS = {'material_font': ['material'], 'stem_teaching_font': ['stem_teaching', 'stem_options_teaching']}
DRILL_COLOR_RULES = {
    'A1 带正误颜色或纠正',
    'A2 错误行缺红色错处',
    'A2 错误行缺绿色“纠正”',
    'A2 正确行带红绿或纠正',
    'A2 表内正误不齐',
}
KNOWN_LIMITS = [
    '没有登记 typography.<role>.rules（按 ex.kind/zone/label 的条件角色表）时，material_font/'
    'stem_teaching_font 只做 CANDIDATE 计数，不判断对错、不支持 plan——启发式猜出的单一角色在不同'
    '题型下应有格式往往不同（例：同一“材料”样式，选择题题干与主观题材料的目标字体不同），机械按单一'
    '目标改写会把符合版式协议的格式改坏。',
    '不支持加粗（w:b/w:bCs）的审计与修复；ALLOWED_AFTER_FIELDS 只有 color/ea/ascii/pt。',
    '字体/颜色完全由 *Theme 属性决定、没有可读的直接值时（例如只写 eastAsiaTheme 没写 eastAsia），'
    '本工具不解析主题色板（themeN.xml），一律当作未知跳过，不计入偏差，也不会误判为已修复。',
    '主观题“材料”与“设问”常共用同一段落样式（同段甚至同段不同 run），无法仅凭样式名/段落 zone 区分，'
    '需要更细的人工标注或书内一致的标签才能精确到 run 级角色。',
]


class Abort(Exception):
    """整批中止：调用方捕获后按“不留输出”处理。"""


# ---------------------------------------------------------------- 小工具
def _run_raw_text(r):
    """与 bh.read_docx 组装 run 文字同一口径（w:t/w:tab/w:sym，translate 掉零宽字符），但不 strip——
    这是单个 run 的文字，不是整段，前后空白可能有意义，且要和 plan 里记的原文逐字比对。"""
    buf = []
    for ch in r:
        tag = ch.tag
        if tag == W + 't':
            buf.append(ch.text or '')
        elif tag == W + 'tab':
            buf.append('\t')
        elif tag == W + 'sym':
            buf.append(bh._sym_char(ch))
    return ''.join(buf).translate(bh.ZW)


def _run_list(p):
    """段落里的 run 元素，按文档序，跳过 mc:Fallback 里的重复内容——与 docx_lib.para_text /
    bh.read_docx 对同一段落的取字口径一致，只是这里返回 run 元素本身（供改 rPr 用）。"""
    skip = set()
    for fb in p.iter(bh.MC + 'Fallback'):
        skip.update(fb.iter())
    return [r for r in p.iter(W + 'r') if not (skip and r in skip)]


def _rpr_get(rpr, tag):
    return rpr.find(W + tag) if rpr is not None else None


def _rpr_ensure(r):
    """确保 run 有 w:rPr（必须是第一个子元素），返回它。"""
    rpr = r.find(W + 'rPr')
    if rpr is None:
        rpr = etree.SubElement(r, W + 'rPr')
        r.remove(rpr)
        r.insert(0, rpr)
    return rpr


def _rpr_insert(rpr, tag_name, build):
    """在 rpr 里按 RPR_ORDER 顺序放一个子元素：已存在就地改，不存在就在正确位置插入新元素。
    build(el) 负责把想要的属性写到 el 上（el 是新建或已存在的同名元素）。"""
    existing = rpr.find(W + tag_name)
    if existing is not None:
        build(existing)
        return existing
    el = etree.Element(W + tag_name)
    build(el)
    pos = RPR_ORDER.index(tag_name)
    insert_at = len(rpr)
    for i, ch in enumerate(rpr):
        local = etree.QName(ch).localname
        if local in RPR_ORDER and RPR_ORDER.index(local) > pos:
            insert_at = i
            break
    rpr.insert(insert_at, el)
    return el


def _apply_field(r, field, value):
    """把一个 after 字段（color/ea/ascii/pt）写进 run 的 rPr，只改这一个子元素，其余不动。设置颜色/
    字体时一并删除对应的 theme 属性（themeColor/themeTint/themeShade、eastAsiaTheme/asciiTheme）——
    否则 Word 渲染时 theme 属性优先于 val，改了 val 也不会真的变色/变字体（2026-09-24 对抗性审查
    issue 4）。"""
    rpr = _rpr_ensure(r)
    if field == 'color':
        def build(el):
            el.set(W + 'val', value)
            for attr in ('themeColor', 'themeTint', 'themeShade'):
                if el.get(W + attr) is not None:
                    del el.attrib[W + attr]
        _rpr_insert(rpr, 'color', build)
    elif field in ('ea', 'ascii'):
        # 内部字段名 'ea' 对应的真实 XML 属性是 w:eastAsia，不是 w:ea——2026-09-24 返修时用真实
        # apply 全流程测出：旧代码一直把 attr 直接当 XML 属性名用，'ea' 从未真正写对过（'ascii' 凑巧
        # 同名所以之前没发现），font 类 fixable 又长期恒为 True 却从没人跑通过 apply，才没暴露。
        xml_attr = 'eastAsia' if field == 'ea' else 'ascii'
        theme_attr = 'eastAsiaTheme' if field == 'ea' else 'asciiTheme'

        def build(el, attr=xml_attr, theme_attr=theme_attr):
            el.set(W + attr, value)
            if el.get(W + theme_attr) is not None:
                del el.attrib[W + theme_attr]
        _rpr_insert(rpr, 'rFonts', build)
    elif field == 'pt':
        half = str(int(round(float(value) * 2)))
        _rpr_insert(rpr, 'sz', lambda el: el.set(W + 'val', half))
        cs = rpr.find(W + 'szCs')
        if cs is not None:
            cs.set(W + 'val', half)
    else:
        raise Abort(f'不支持的格式字段：{field}（本工具目前只支持 color/ea/ascii/pt，暂不支持加粗 b/bCs）')


def _run_direct_fields(rpr):
    """run 或样式自己 rPr 里直接写的字段（不含继承）。同时记录 *Theme 属性：*_theme 有值表示这一层
    对应属性带主题引用；本工具不解析主题色板（themeN.xml），只用这个标记决定“能不能确信当前值”。"""
    out = {}
    if rpr is None:
        return out
    fonts = rpr.find(W + 'rFonts')
    if fonts is not None:
        if fonts.get(W + 'eastAsia'):
            out['ea'] = fonts.get(W + 'eastAsia')
        if fonts.get(W + 'ascii'):
            out['ascii'] = fonts.get(W + 'ascii')
        if fonts.get(W + 'eastAsiaTheme'):
            out['ea_theme'] = fonts.get(W + 'eastAsiaTheme')
        if fonts.get(W + 'asciiTheme'):
            out['ascii_theme'] = fonts.get(W + 'asciiTheme')
    sz = rpr.find(W + 'sz')
    if sz is not None and sz.get(W + 'val'):
        try:
            out['pt'] = int(sz.get(W + 'val')) / 2.0
        except ValueError:
            pass
    color = rpr.find(W + 'color')
    if color is not None:
        if color.get(W + 'val'):
            out['color'] = color.get(W + 'val').upper()
        if color.get(W + 'themeColor'):
            out['color_theme'] = color.get(W + 'themeColor')
    rstyle = rpr.find(W + 'rStyle')
    if rstyle is not None:
        out['_rstyle'] = rstyle.get(W + 'val')
    return out


class StyleTable:
    """word/styles.xml 的字体/字号/颜色继承链（bh.Styles 只做了颜色/keepNext，这里补字体/字号，
    薄封装、不改 batch_health）。"""

    def __init__(self, path):
        import zipfile
        self.own, self.based, self.default_pstyle = {}, {}, None
        self.doc_default = {}
        self._cache = {}
        with zipfile.ZipFile(path) as z:
            if 'word/styles.xml' not in z.namelist():
                return
            root = etree.fromstring(z.read('word/styles.xml'))
        for st in root.iter(W + 'style'):
            sid = st.get(W + 'styleId')
            b = st.find(W + 'basedOn')
            self.based[sid] = b.get(W + 'val') if b is not None else None
            self.own[sid] = _run_direct_fields(st.find(W + 'rPr'))
            if st.get(W + 'type') == 'paragraph' and st.get(W + 'default') in ('1', 'true'):
                self.default_pstyle = sid
        self.doc_default = _run_direct_fields(root.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr'))

    def effective(self, sid):
        if sid is None:
            return {}
        if sid in self._cache:
            return self._cache[sid]
        self._cache[sid] = {}  # 防循环 basedOn
        parent = self.based.get(sid)
        eff = dict(self.effective(parent)) if parent else {}
        eff.update({k: v for k, v in self.own.get(sid, {}).items() if k != '_rstyle'})
        self._cache[sid] = eff
        return eff

    def run_format(self, p, r):
        """直接 rPr > rStyle 链 > pStyle 链 > docDefaults，解析这个 run 实际生效的 ea/ascii/pt/color。
        返回的 dict 里 <key>_theme 表示该值所在的那一层还带着对应的 theme 属性（真实渲染可能不是这里
        算出来的值，见 KNOWN_LIMITS）；某个 key 直接层只有 theme 属性、没有可读的 val/eastAsia/ascii
        时，视为这一层“未知但已被 run 自己改写”，不再往样式链找（跳过，不当作确定值）。"""
        direct = _run_direct_fields(r.find(W + 'rPr'))
        rstyle_sid = direct.pop('_rstyle', None)
        ps = p.find(f'{W}pPr/{W}pStyle')
        pstyle_sid = ps.get(W + 'val') if ps is not None else self.default_pstyle
        layers = []
        if rstyle_sid:
            layers.append(self.effective(rstyle_sid))
        layers.append(self.effective(pstyle_sid))
        layers.append(self.doc_default)
        out = {}
        theme_of = {'ea': 'ea_theme', 'ascii': 'ascii_theme', 'color': 'color_theme'}
        for key in ('ea', 'ascii', 'pt', 'color'):
            tk = theme_of.get(key)
            if key in direct:
                out[key] = direct[key]
                if tk and direct.get(tk):
                    out[tk] = direct[tk]
                continue
            if tk and direct.get(tk):
                # run 自己的 rPr 只写了 theme 属性、没写可读的值：run 一定改写了这一属性，但真实值
                # 不确定，不能再往样式链找（那是错的），也不能假装继承了样式的值。
                out[tk] = direct[tk]
                continue
            for layer in layers:
                if key in layer:
                    out[key] = layer[key]
                    if tk and layer.get(tk):
                        out[tk] = layer[tk]
                    break
                if tk and layer.get(tk):
                    out[tk] = layer[tk]
                    break
        return out


# ---------------------------------------------------------------- profile / 角色
def _load_prof(args):
    if args.profile:
        return load_profile(args.profile)
    prof = detect_profile(args.docx)
    if prof is None:
        raise Abort('识别不出书册，请显式传 --profile（书名或配置路径）')
    return prof


def _fallback_style_scopes(prof):
    """CANDIDATE 兜底的启发式猜测（旧行为，不再当作确定目标）：材料 = styles.source 里样式名含
    “材料”的那个，其余 source 并入 teaching。"""
    src = set(bh.cfg(prof, 'styles.source', []) or [])
    teach = set(bh.cfg(prof, 'styles.teaching', []) or [])
    material_guess = {s for s in src if ('材料' in s or 'material' in s.lower())} or (set([sorted(src)[0]]) if src else set())
    stem_guess = (src - material_guess) | teach
    return {'material_font': material_guess, 'stem_teaching_font': stem_guess}


def _role_candidate_styles(prof, role):
    """决定 CANDIDATE 兜底扫描哪些样式名（不是确定目标）：typography.<key>.styles（无条件旧字段）>
    typography.<key>._style（画像单样式）> 启发式猜测。"""
    fallback = _fallback_style_scopes(prof).get(role, set())
    typo_keys = TYPO_KEYS.get(role, [])
    for key in typo_keys:
        v = bh.cfg(prof, f'typography.{key}')
        if not isinstance(v, dict):
            continue
        styles = v.get('styles')
        if styles:
            return set(styles if isinstance(styles, list) else [styles]), key
        s1 = v.get('_style')
        if isinstance(s1, str):
            return {s1}, key
        if isinstance(s1, list) and s1:
            return set(s1), key
    return fallback, (typo_keys[0] if typo_keys else None)


def _role_rules(prof, role):
    """返回这个角色的显式条件规则列表：typography.<key>.rules，每条必须给 kind（题型条件）与
    styles；zone/label 可选进一步限定。没有配置、或列表里没有一条同时给了 kind 和 styles，返回
    None——表示这本书没有可信的角色表，material_font/stem_teaching_font 只做 CANDIDATE 计数，
    禁止生成修改计划（这是 2026-09-24 对抗性审查后的默认行为，不是临时降级）。"""
    for key in TYPO_KEYS.get(role, []):
        raw = bh.cfg(prof, f'typography.{key}.rules')
        if not isinstance(raw, list) or not raw:
            continue
        rules = []
        for r in raw:
            if not isinstance(r, dict) or not r.get('styles') or not r.get('kind'):
                continue
            kind, zone, label, styles = r['kind'], r.get('zone'), r.get('label'), r['styles']
            rules.append({
                'kind': set(kind) if isinstance(kind, list) else {kind},
                'zone': set(zone) if isinstance(zone, list) else ({zone} if zone else None),
                'label': set(label) if isinstance(label, list) else ({label} if label else None),
                'styles': set(styles) if isinstance(styles, list) else {styles},
                'ea': r.get('ea'), 'ascii': r.get('ascii'), 'pt': r.get('pt'), 'typo_key': key,
            })
        if rules:
            return rules
    return None


def _rule_matches(rule, it):
    if it['style'] not in rule['styles']:
        return False
    ex = it.get('ex')
    kind = ex.get('kind') if ex else None
    if kind not in rule['kind']:
        return False
    if rule['zone'] is not None and it['zone'] not in rule['zone']:
        return False
    if rule['label'] is not None and it.get('label') not in rule['label']:
        return False
    return True


# ---------------------------------------------------------------- audit：教学正文误蓝（run 级）
def _blue_label_spans(raw, zone, block_labels):
    return [m.span() for m in re.finditer(r'【[^】]{1,40}】', raw)
            if zone != 'source' or norm_label(m.group(0)) in block_labels]


_STYLE_TABLE_CACHE = {}


def _style_table(d):
    key = str(d.path)
    st = _STYLE_TABLE_CACHE.get(key)
    if st is None:
        st = StyleTable(d.path)
        _STYLE_TABLE_CACHE[key] = st
    return st


def _target_body_color(d, p, exclude_ridx, blue, cfg_color):
    """误蓝修复的目标色（issue 5：不再写死 auto，也不假装知道“该书正文色”是黑色）：优先取配置给的
    正文色（typography.stem_teaching.color / typography.material.color / typography.colors.body，
    按此顺序取第一个有值的），没有配置就取同段其余非蓝文字 run 的颜色众数（与被改 run 视觉上最接近，
    不会造成同段颜色不一致），都没有才退回 auto。"""
    if cfg_color:
        c = str(cfg_color).strip()
        return 'auto' if c.lower() == 'auto' else c.upper()
    table = _style_table(d)
    cnt = Counter()
    for ridx, r in enumerate(_run_list(p)):
        if ridx == exclude_ridx:
            continue
        t = _run_raw_text(r)
        if not (CJK.search(t) or re.search(r'[A-Za-z0-9]', t)):
            continue
        c = (table.run_format(p, r).get('color') or 'AUTO').upper()
        if c not in blue:
            cnt[c] += 1
    if cnt:
        top = cnt.most_common(1)[0][0]
        return 'auto' if top == 'AUTO' else top
    return 'auto'


def _style_color_consistency(d, blue, min_n=3, threshold=0.8):
    """按段落样式统计它在全书（不限区位）里的颜色分布：某个样式绝大多数实例都是同一个蓝色时，判定
    这是书里“这个样式本来就设计成这个颜色”的约定——不管技术上是样式自带颜色还是每处都直接格式化成
    一样的颜色（后一种在实测的哲学“错肢分组”标题上就是反例：颜色是每处 run 直接写的 1F4E79，不是
    继承自 pStyle，但全书 18 处里 17 处一致，明显是设计色，只是这一处恰好落进了 teaching 区）。仅凭
    “run 有没有直接 rPr 颜色”不足以分辨这种情况，需要这个跨段一致性统计做补充（issue 1/5）。返回
    {style_name: 该蓝色} 字典；样本太少（<min_n）不下结论。"""
    table = _style_table(d)
    hist = defaultdict(Counter)
    for it in d.items:
        st = it.get('style')
        if not st or it.get('tbl') is not None or not it.get('text'):
            continue
        p = d.paras[it['i']]
        for r in _run_list(p):
            rt = _run_raw_text(r)
            if not (CJK.search(rt) or re.search(r'[A-Za-z0-9]', rt)):
                continue
            c = table.run_format(p, r).get('color') or 'AUTO'
            hist[st][c] += 1
    designed = {}
    for st, cnt in hist.items():
        total = sum(cnt.values())
        if total < min_n:
            continue
        top_color, top_n = cnt.most_common(1)[0]
        if top_color in blue and top_n / total >= threshold:
            designed[st] = top_color
    return designed


def audit_mis_blue(d, P, items):
    """口径与 bh.check_blue 的 FAIL 规则“教学正文误蓝”完全一致（这条链已在七本书上验证过，不改动
    判定范围），只多做几步：①把命中落到具体 run；②只有同时满足“run 自己 rPr 里直接写了颜色”与
    “这个样式在全书不是一贯设计成这个蓝色”才 fixable——两条有一条不满足就标 CANDIDATE，不机械修复
    （issue 5：可能是有意的样式设计，如错肢分组标题色，只是被算进了 teaching/rubric 区，机械改会把
    设计色改没）；③目标色用 _target_body_color 算，不写死 auto。"""
    blue = {x.upper() for x in bh.cfg(P.d, 'colors.blue', [])}
    lb = bh.cfg(P.d, 'typography.colors.label_blue')
    if lb:
        blue.add(lb.upper())
    ex_pre = tuple(bh.cfg(P.d, 'colors.blue_exempt_prefix', []) or [])
    ex_sty = set(bh.cfg(P.d, 'colors.blue_exempt_styles', []) or []) | P.heading_like | P.title_styles | P.toc_styles
    cfg_color = (bh.cfg(P.d, 'typography.stem_teaching.color') or bh.cfg(P.d, 'typography.material.color')
                 or bh.cfg(P.d, 'typography.colors.body'))
    designed_styles = _style_color_consistency(d, blue)
    table = _style_table(d)
    out = []
    for it in items:
        z = it['zone']
        if z not in ('teaching', 'rubric') or it['style'] in ex_sty:
            continue
        if not it['text'] or it.get('_subhead') or (ex_pre and it['text'].startswith(ex_pre)):
            continue
        raw = ''.join(t for t, _ in it['runs'])
        spans = _blue_label_spans(raw, z, P.block_labels)
        p = d.paras[it['i']]
        runs = _run_list(p)
        o = 0
        for ridx, r in enumerate(runs):
            t = _run_raw_text(r)
            a, o = o, o + len(t)
            fmt = table.run_format(p, r)
            c = fmt.get('color') or 'AUTO'  # 与旧 _run_effective_color 同一口径：主题独占的颜色算不出
            if c not in blue:                # 值，key 不存在，落到 'AUTO'，不会被误判为蓝——保守但安全
                continue
            in_label = [k for k in range(len(t)) if any(x <= a + k < y for x, y in spans)]
            rest = ''.join(ch for k, ch in enumerate(t) if k not in in_label)
            if not (CJK.search(rest) or re.search(r'[A-Za-z0-9]', rest)):
                continue
            direct = _run_direct_fields(r.find(W + 'rPr'))
            has_direct_color = 'color' in direct
            designed_color = designed_styles.get(it['style'])
            if in_label:
                fixable, note = False, 'run 里既有标签文字又有正文，物理上无法只改格式'
            elif not has_direct_color:
                fixable, note = False, ('蓝色来自段落/字符样式而不是 run 自己的直接格式，可能是有意的'
                                         '样式设计（如分组标题），需人工核实后再处理，不机械修复')
            elif designed_color and designed_color.upper() == c:
                fixable, note = False, (f'“{it["style"]}”样式在全书里绝大多数实例都是这个蓝色，像是'
                                         f'有意的设计色（只是这一处被归进了 teaching/rubric 区），'
                                         f'需人工核实是不是真的误蓝，不机械修复')
            else:
                fixable, note = True, None
            after = {'color': _target_body_color(d, p, ridx, blue, cfg_color)} if fixable else None
            out.append({'rule': 'teach_mis_blue', 'level': 'FAIL', 'para': it['i'], 'run': ridx,
                        'style': it['style'], 'zone': z, 'node': clip(it.get('node'), 30),
                        'example': clip((it.get('ex') or {}).get('title'), 40) if it.get('ex') else None,
                        'text': t, 'excerpt': clip(rest, 40), 'before': {'color': c},
                        'after': after, 'fixable': fixable, 'note': note})
    return out


# ---------------------------------------------------------------- audit：材料区/题面教学区字体字号
def _audit_font_role_rules(d, role, rules, items):
    """有显式 typography.<key>.rules（带题型/区位条件）时的精确审计：按 ex.kind/zone/label 细分角色，
    同一 run 命中多条目标不同的规则记为配置冲突（不 fixable，交主代理裁定，不二选一瞎猜）。字体完全
    由 *Theme 决定、没有可读直接值的字段跳过（不当成确定偏差，见 StyleTable.run_format）。"""
    table = _style_table(d)
    out = []
    for it in items:
        if not it['text'] or it['zone'] in ('cover', 'heading', 'toc', 'title'):
            continue
        matches = [r for r in rules if _rule_matches(r, it)]
        if not matches:
            continue
        p = d.paras[it['i']]
        ex = it.get('ex')
        kind = ex.get('kind') if ex else None
        targets = {(m.get('ea'), m.get('ascii'), m.get('pt')) for m in matches}
        conflict = len(targets) > 1
        want_ea = want_ascii = want_pt = None
        if not conflict:
            want_ea, want_ascii, want_pt = next(iter(targets))
        for ridx, r in enumerate(_run_list(p)):
            t = _run_raw_text(r)
            if not t.strip():
                continue
            if conflict:
                out.append({'rule': role, 'level': 'FAIL', 'para': it['i'], 'run': ridx, 'style': it['style'],
                            'zone': it['zone'], 'kind': kind, 'label': it.get('label'),
                            'node': clip(it.get('node'), 30), 'text': t, 'excerpt': clip(t, 40),
                            'before': None, 'after': None, 'fixable': False,
                            'note': '同一个 run 命中多条角色规则且目标格式不同（配置冲突），交主代理裁定',
                            'conflict_targets': sorted(str(x) for x in targets)})
                continue
            fmt = table.run_format(p, r)
            before, after = {}, {}
            for key, want, charset_ok in (('ea', want_ea, CJK.search(t)),
                                           ('ascii', want_ascii, re.search(r'[A-Za-z]', t))):
                if not want or not charset_ok:
                    continue
                cur = fmt.get(key)
                if cur is None and fmt.get(f'{key}_theme'):
                    continue  # 完全由主题决定，本工具不解析主题色板，不当成确定偏差（issue 4）
                if (cur or '').strip() != want:
                    before[key], after[key] = cur, want
            if want_pt is not None:
                cur_pt = fmt.get('pt')
                if cur_pt is None or abs(float(cur_pt) - float(want_pt)) > 0.05:
                    before['pt'], after['pt'] = cur_pt, want_pt
            if not before:
                continue
            out.append({'rule': role, 'level': 'FAIL', 'para': it['i'], 'run': ridx, 'style': it['style'],
                        'zone': it['zone'], 'kind': kind, 'label': it.get('label'),
                        'node': clip(it.get('node'), 30), 'text': t, 'excerpt': clip(t, 40),
                        'before': before, 'after': after, 'fixable': True, 'note': None})
    return out


def _audit_font_role_candidate(d, role, typo_key, styles, items):
    """没有显式 typography.<key>.rules 时的兜底：按 (ex.kind, zone, label, style) 列出观测到的字体/
    字号，CANDIDATE 级、fixable 恒 False、不生成 after、不支持 plan——见模块 docstring 与
    KNOWN_LIMITS。只供人工核对“现在长什么样”，不代表“这是错的”。"""
    if not styles or not typo_key:
        return []
    table = _style_table(d)
    note = (f'没有登记 typography.{typo_key}.rules（按题型/区位细分的角色表），仅供人工核对观测到的'
            f'格式分布，不构成体检偏差、不支持 plan')
    out = []
    for it in items:
        if it['style'] not in styles or not it['text'] or it['zone'] in ('cover', 'heading', 'toc', 'title'):
            continue
        p = d.paras[it['i']]
        ex = it.get('ex')
        kind = ex.get('kind') if ex else None
        for ridx, r in enumerate(_run_list(p)):
            t = _run_raw_text(r)
            if not t.strip():
                continue
            fmt = table.run_format(p, r)
            out.append({'rule': role, 'level': 'CANDIDATE', 'para': it['i'], 'run': ridx, 'style': it['style'],
                        'zone': it['zone'], 'kind': kind, 'label': it.get('label'), 'node': clip(it.get('node'), 30),
                        'text': t, 'excerpt': clip(t, 40),
                        'before': {'ea': fmt.get('ea'), 'ascii': fmt.get('ascii'), 'pt': fmt.get('pt')},
                        'after': None, 'fixable': False, 'note': note})
    return out


def audit_font_role(d, prof, role, items):
    """按角色分派：有显式条件规则表就精确判定，没有就退化为 CANDIDATE 观测。返回 (findings, precise)。"""
    rules = _role_rules(prof, role)
    if rules:
        return _audit_font_role_rules(d, role, rules, items), True
    styles, typo_key = _role_candidate_styles(prof, role)
    return _audit_font_role_candidate(d, role, typo_key, styles, items), False


# ---------------------------------------------------------------- audit：单练红绿错位（只读汇总，不支持 plan）
def audit_drill_color(items, P):
    """直接复用 bh.check_drill 的判定；用 bh_rule 原名显式白名单挑出“颜色/纠正位置错了”的几条，不用
    “规则名里有没有红/绿/颜色/纠正”猜——那样会漏掉不含这几个字但同属此类的规则名（如“A2 表内正误
    不齐”），issue: minor。"""
    F = bh.Findings()
    bh.check_drill(items, P, F)
    out = []
    for f in F.items:
        if f.get('check') != 'drill':
            continue
        rule = f.get('rule', '')
        if rule not in DRILL_COLOR_RULES:
            continue
        w = f.get('where') or {}
        out.append({'rule': 'drill_color', 'level': f.get('level'), 'para': w.get('para'),
                    'run': None, 'style': w.get('style'), 'zone': w.get('zone'), 'node': w.get('node'),
                    'text': f.get('excerpt'), 'excerpt': f.get('excerpt'), 'before': None, 'after': None,
                    'fixable': False, 'note': '涉及“哪个题肢/哪个字错了”的内容判断，本工具不生成修改计划，'
                                               '与 bh.check_drill 的判定同源', 'bh_rule': rule})
    return out


# ---------------------------------------------------------------- 报告基础结构
def _base_report(mode, docx_path, d_sha, prof):
    return {'tool': TOOL, 'version': VERSION, 'mode': mode, 'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'inputs': {'docx': str(docx_path), 'docx_sha256': d_sha},
            'profile': {'book_id': prof.get('book_id'), 'frozen': bool(prof.get('frozen'))}}


def _own_report(path, mode=None, docx_sha=None):
    """判断已存在的文件是不是“本工具生成的、同一次操作（mode 与 docx_sha256 都相同）的旧报告”——
    只有这种情况才允许覆盖，防止 plan --out 指向另一份 audit 报告时被静默覆盖（issue: minor）。"""
    p = Path(path)
    if not p.exists():
        return False
    try:
        obj = json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return False
    if obj.get('tool') != TOOL:
        return False
    if mode is not None and obj.get('mode') != mode:
        return False
    if docx_sha is not None and (obj.get('inputs') or {}).get('docx_sha256') != docx_sha:
        return False
    return True


def _guard_report_path(path, prof, guard_inputs, mode=None, docx_sha=None):
    rp = dict(prof or {})
    rp['frozen'] = False  # 报告不是书稿，冻结册判定不适用于报告本身
    return dl.guard_write(path, rp, inputs=guard_inputs or [], kind='.json',
                           overwrite=_own_report(path, mode=mode, docx_sha=docx_sha))


def _write_report(path, prof, obj, guard_inputs, mode=None, docx_sha=None):
    if not path:
        return None
    out = _guard_report_path(path, prof, guard_inputs, mode=mode, docx_sha=docx_sha)
    out.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    return str(out)


# ---------------------------------------------------------------- 子命令：audit
def cmd_audit(args):
    prof = _load_prof(args)
    d = dl.open_docx(args.docx)
    P = bh.Prof(prof)
    bh.walk(d.items, P)
    findings = []
    findings += audit_mis_blue(d, P, d.items)
    material_findings, material_precise = audit_font_role(d, prof, 'material_font', d.items)
    stem_findings, stem_precise = audit_font_role(d, prof, 'stem_teaching_font', d.items)
    findings += material_findings
    findings += stem_findings
    findings += audit_drill_color(d.items, P)
    rep = _base_report('audit', args.docx, d.sha256, prof)
    by_rule = Counter(f['rule'] for f in findings)
    # teach_mis_blue 的“处”按段落数计（与 bh.check_blue 的 FAIL 计数同一粒度：一段里两个 run 都
    # 误蓝只算一处），findings 列表本身仍按 run 展开，供 plan/apply 使用。
    paras_by_rule = defaultdict(set)
    for f in findings:
        paras_by_rule[f['rule']].add(f['para'])
    by_rule_paragraphs = {k: len(v) for k, v in paras_by_rule.items()}
    rep['summary'] = {'total_runs': len(findings), 'by_rule_runs': dict(by_rule),
                       'by_rule_paragraphs': by_rule_paragraphs,
                       'fixable_runs': sum(1 for f in findings if f.get('fixable'))}

    def _role_note(precise, key):
        return None if precise else (f'没有登记 typography.{key}.rules（按题型/区位条件的角色表），'
                                      f'字体检查已降级为 CANDIDATE 计数、不支持 plan')
    rep['role_config'] = {
        'material_font': {'precise_rules': material_precise, 'note': _role_note(material_precise, 'material')},
        'stem_teaching_font': {'precise_rules': stem_precise,
                                'note': _role_note(stem_precise, 'stem_teaching')},
    }
    rep['known_limits'] = KNOWN_LIMITS
    rep['findings'] = findings
    _write_report(args.report, prof, rep, guard_inputs=[args.docx], mode='audit', docx_sha=d.sha256)
    print(json.dumps(rep['summary'], ensure_ascii=False))
    return 1 if findings else 0


# ---------------------------------------------------------------- 子命令：plan
KNOWN_PLAN_RULES = {'teach_mis_blue', 'material_font', 'stem_teaching_font'}


def cmd_plan(args):
    audit = json.loads(Path(args.audit).read_text(encoding='utf-8'))
    if audit.get('tool') != TOOL or audit.get('mode') != 'audit':
        raise Abort('audit 文件不是本工具的 audit 报告（tool/mode 不符）')
    audit_sha = (audit.get('inputs') or {}).get('docx_sha256')
    if not audit_sha:
        raise Abort('audit 报告缺 inputs.docx_sha256，无法核对是不是同一份书稿')
    docx_sha = dl.sha256_file(args.docx)
    if docx_sha != audit_sha.lower():
        raise dl.ParentMismatch(f'--docx 与 audit 报告记录的原稿不符：audit={audit_sha[:16]}… '
                                 f'现状={docx_sha[:16]}…（{Path(args.docx).name}）')
    rules = [r for r in (args.rules or '').split(',') if r]
    if not rules:
        raise Abort('--rules 不能为空')
    unknown = [r for r in rules if r not in KNOWN_PLAN_RULES]
    if unknown:
        raise Abort(f'不认识的类别：{unknown}；已知类别：{sorted(KNOWN_PLAN_RULES)}；'
                    f'drill_color 涉及内容判断，本工具从不为它生成计划')
    prof = _load_prof(args)
    ready = {'teach_mis_blue'} | {role for role in ('material_font', 'stem_teaching_font') if _role_rules(prof, role)}
    not_ready = [r for r in rules if r not in ready]
    if not_ready:
        raise Abort(f'这些类别本书没有登记 typography.<角色>.rules（按题型/区位条件的角色表），字体检查'
                    f'只做 CANDIDATE 审计，禁止生成修改计划（需要人工确认角色表后再登记进 profile）：'
                    f'{not_ready}')
    ops, skipped = [], []
    for f in audit.get('findings', []):
        if f['rule'] not in rules:
            continue
        if not f.get('fixable') or not f.get('after'):
            skipped.append({'para': f['para'], 'run': f.get('run'), 'rule': f['rule'],
                            'reason': f.get('note') or '不可机械修复'})
            continue
        bad = set(f['after']) - ALLOWED_AFTER_FIELDS
        if bad:
            raise Abort(f'审计结果里出现不支持的格式字段：{bad}（第 {f["para"]} 段第 {f.get("run")} 个 run）')
        ops.append({'id': f'{f["rule"]}#{f["para"]}#{f["run"]}', 'rule': f['rule'], 'para': f['para'],
                    'run': f['run'], 'style': f.get('style'), 'zone': f.get('zone'), 'text': f['text'],
                    'excerpt': f.get('excerpt'), 'before': f['before'], 'after': f['after']})
    rep = {'tool': TOOL, 'version': VERSION, 'mode': 'plan', 'generated_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
           'inputs': {'docx': str(Path(args.docx).resolve()), 'docx_sha256': docx_sha,
                      'audit_report': str(Path(args.audit).resolve())},
           'profile': {'book_id': prof.get('book_id'), 'frozen': bool(prof.get('frozen'))},
           'rules': rules, 'ops': ops, 'skipped': skipped,
           'summary': {'ops': len(ops), 'skipped': len(skipped)}}
    _write_report(args.out, prof, rep, guard_inputs=[args.audit], mode='plan', docx_sha=docx_sha)
    print(json.dumps(rep['summary'], ensure_ascii=False))
    return 1 if ops else 0


# ---------------------------------------------------------------- 子命令：apply
def _load_plan(path):
    plan = json.loads(Path(path).read_text(encoding='utf-8'))
    if plan.get('tool') != TOOL or plan.get('mode') != 'plan':
        raise Abort('plan 文件不是本工具的 plan（tool/mode 不符）')
    return plan


def _recheck_op(d, P, role_rules, op, pi, ri):
    """按 op 的 rule 在当前书稿上独立重算这个 run 现在的判定，直接复用 audit 用的判定函数（只喂这一
    段进去），不信任 plan 文件里记的 before/after——防 plan 被篡改（改颜色、改字号、混进不支持字段、
    把已经修好或本来就干净的 run 也点上）。返回重算出的 finding dict；算不出（规则不认识、这本书没
    登记角色表）返回 None。"""
    it = d.items[pi]
    if op['rule'] == 'teach_mis_blue':
        found = audit_mis_blue(d, P, [it])
    elif op['rule'] in ('material_font', 'stem_teaching_font'):
        rules = role_rules.get(op['rule'])
        if not rules:
            return None
        found = _audit_font_role_rules(d, op['rule'], rules, [it])
    else:
        return None
    for f in found:
        if f['run'] == ri:
            return f
    return None


def cmd_apply(args):
    plan = _load_plan(args.plan)
    prof_for_frozen = None
    try:
        prof_for_frozen = detect_profile(args.docx)
    except Exception:
        prof_for_frozen = None
    if prof_for_frozen is not None and bool(prof_for_frozen.get('frozen')):
        print(f'拒绝写出：{prof_for_frozen.get("title", prof_for_frozen.get("book_id"))} 已冻结'
              f'（{prof_for_frozen.get("frozen_note", "")}）', file=sys.stderr)
        return 3
    prof = _load_prof(args) if args.profile else (prof_for_frozen or load_profile(plan['profile']['book_id']))
    expect_sha = args.expect_sha or plan['inputs']['docx_sha256']
    d = dl.open_docx(args.docx, expect_sha256=expect_sha)
    ops = plan.get('ops') or []
    if not ops:
        print('计划里没有可应用的操作', file=sys.stderr)
        return 0
    P = bh.Prof(prof)
    bh.walk(d.items, P)
    role_rules = {role: _role_rules(prof, role) for role in ('material_font', 'stem_teaching_font')}
    # 第一遍：只校验，不改任何 XML——run 文字必须逐字符与计划记录相符，after 字段必须都在允许集合内，
    # 且与现在独立重算的判定逐字段相等（不信任 plan 文件里的 before/after，见 _recheck_op）。
    planned = []
    seen_run_ids = set()
    for op in ops:
        pi, ri = op.get('para'), op.get('run')
        if pi is None or pi < 0 or pi >= len(d.paras):
            raise Abort(f'计划第 {op["id"]} 条段号越界：{pi}')
        p = d.paras[pi]
        runs = _run_list(p)
        if ri is None or ri < 0 or ri >= len(runs):
            raise Abort(f'计划第 {op["id"]} 条 run 序号越界：{ri}')
        r = runs[ri]
        cur = _run_raw_text(r)
        if cur != op['text']:
            raise Abort(f'计划第 {op["id"]} 条 run 文字与当前稿不符：计划={op["text"]!r} 现状={cur!r}')
        after = op.get('after') or {}
        bad = set(after) - ALLOWED_AFTER_FIELDS
        if bad:
            raise Abort(f'计划第 {op["id"]} 条 after 里有不支持的格式字段（本工具目前只支持 '
                        f'color/ea/ascii/pt，暂不支持加粗 b/bCs）：{bad}')
        for field, value in after.items():
            if field == 'color' and not (value.lower() == 'auto' or _HEX_COLOR_RE.match(value)):
                raise Abort(f'计划第 {op["id"]} 条颜色格式不合法：{value!r}（只能是 auto 或 6 位十六进制）')
        recomputed = _recheck_op(d, P, role_rules, op, pi, ri)
        if recomputed is None or not recomputed.get('fixable') or (recomputed.get('after') or {}) != after:
            raise Abort(f'计划第 {op["id"]} 条与现在独立重算的判定不符（plan 文件可能被篡改，或书稿'
                        f'在生成计划后又变了）：重算结果={recomputed}')
        key = (pi, ri)
        if key in seen_run_ids:
            raise Abort(f'同一个 run 被计划里多条操作重复指名：段 {pi} run {ri}')
        seen_run_ids.add(key)
        planned.append((p, r, ri, after))
    # 写权守卫：先于任何 XML 改动。
    try:
        out_path = dl.guard_write(args.out, prof, inputs=[args.docx, args.plan], kind='.docx')
    except dl.GuardError as e:
        print('拒绝写出：' + str(e), file=sys.stderr)
        return 3
    if args.report:
        try:
            _guard_report_path(args.report, prof, guard_inputs=[args.docx, args.plan, args.out],
                                mode='apply', docx_sha=d.sha256)
        except dl.GuardError as e:
            print('拒绝写出：' + str(e), file=sys.stderr)
            return 3
    # 写前基线：来自原始 document.xml 字节独立解析出的一棵树，不能用 d.paras 本身（会被下面原地改）。
    orig_root = etree.fromstring(d.doc_xml_orig)
    orig_paras = dl.para_elements(orig_root.find(W + 'body'))
    orig_runs_by_para = {i: _run_list(op_p) for i, op_p in enumerate(orig_paras)}
    touched_para_idx = {op['para'] for op in ops}
    touched_run_by_para = {}
    for op in ops:
        touched_run_by_para.setdefault(op['para'], set()).add(op['run'])
    # 第二遍：实际改 rPr。
    for p, r, ri, after in planned:
        for field, value in after.items():
            _apply_field(r, field, value)
    write_res = dl.write_docx(d, out_path)
    ok, bad = True, []
    try:
        d2 = dl.open_docx(out_path)
        if len(d2.items) != len(d.items):
            ok = False
            bad.append({'reason': '段落数变化', 'before': len(d.items), 'after': len(d2.items)})
        else:
            for i, (a, b) in enumerate(zip(d.items, d2.items)):
                if a['text'] != b['text']:
                    ok = False
                    bad.append({'reason': '段落文字改变', 'para': i})
                    if len(bad) >= 20:
                        break
        if ok:
            diffs = dl.unchanged_paragraphs(orig_paras, d2.paras, set(touched_para_idx), set(touched_para_idx))
            if diffs:
                ok = False
                bad.append({'reason': '未点名段落发生变化', 'detail': diffs[:10]})
        if ok:
            for pi in touched_para_idx:
                new_p = d2.paras[pi]
                new_runs = _run_list(new_p)
                old_runs = orig_runs_by_para[pi]
                if len(new_runs) != len(old_runs):
                    ok = False
                    bad.append({'reason': 'run 数量变化', 'para': pi})
                    break
                touched_ri = touched_run_by_para.get(pi, set())
                for ri2, (orun, nrun) in enumerate(zip(old_runs, new_runs)):
                    if ri2 in touched_ri:
                        if _run_raw_text(orun) != _run_raw_text(nrun):
                            ok = False
                            bad.append({'reason': '被改 run 的文字变了', 'para': pi, 'run': ri2})
                    else:
                        if etree.tostring(orun, method='c14n') != etree.tostring(nrun, method='c14n'):
                            ok = False
                            bad.append({'reason': '未点名 run 的格式变了', 'para': pi, 'run': ri2})
    except Exception as e:
        ok = False
        bad.append({'reason': f'写后重开核对异常：{e}'})
    rep = _base_report('apply', args.docx, d.sha256, prof)
    rep['plan'] = {'path': str(Path(args.plan).resolve()), 'ops': len(ops)}
    rep['output'] = write_res
    rep['postcheck'] = {'ok': ok, 'problems': bad}
    if not ok:
        try:
            Path(out_path).unlink()
        except OSError:
            pass
        rep['aborted'] = True
        _write_report(args.report, prof, rep, guard_inputs=[args.docx, args.plan], mode='apply', docx_sha=d.sha256)
        print('中止（写后核对未通过，已删除输出）：' + json.dumps(bad[:5], ensure_ascii=False), file=sys.stderr)
        return 2
    if args.health:
        before_health = after_health = None
        try:
            before_health = bh.run_health(args.docx, profile=prof)
            after_health = bh.run_health(str(out_path), profile=prof)
        except Exception as e:
            rep['health_error'] = str(e)
        if before_health is not None and after_health is not None:
            def _fail_map(rep_):
                return {(f['check'], f['rule']): f['count'] for f in rep_.get('findings_by_rule', []) if f['level'] == 'FAIL'}
            b_map, a_map = _fail_map(before_health), _fail_map(after_health)
            keys = sorted(set(b_map) | set(a_map))
            by_check_rule = [{'check': k[0], 'rule': k[1], 'before': b_map.get(k, 0), 'after': a_map.get(k, 0)}
                              for k in keys if b_map.get(k, 0) or a_map.get(k, 0)]
            regressions = [row for row in by_check_rule if row['after'] > row['before']]
            rep['health'] = {'before_fail_total': before_health.get('summary', {}).get('FAIL'),
                              'after_fail_total': after_health.get('summary', {}).get('FAIL'),
                              'by_check_rule': by_check_rule, 'regressions': regressions}
            if regressions:
                try:
                    Path(out_path).unlink()
                except OSError:
                    pass
                rep['aborted'] = True
                _write_report(args.report, prof, rep, guard_inputs=[args.docx, args.plan],
                              mode='apply', docx_sha=d.sha256)
                print('中止（写后体检：以下检查门新增 FAIL，已删除输出）：' +
                      json.dumps(regressions, ensure_ascii=False), file=sys.stderr)
                return 1
    _write_report(args.report, prof, rep, guard_inputs=[args.docx, args.plan], mode='apply', docx_sha=d.sha256)
    print(json.dumps({'out': str(out_path), 'ops_applied': len(ops)}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--debug', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)

    a = sub.add_parser('audit')
    a.add_argument('--docx', required=True)
    a.add_argument('--profile')
    a.add_argument('--report')

    p = sub.add_parser('plan')
    p.add_argument('--docx', required=True)
    p.add_argument('--audit', required=True)
    p.add_argument('--rules', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--profile')

    ap2 = sub.add_parser('apply')
    ap2.add_argument('--docx', required=True)
    ap2.add_argument('--plan', required=True)
    ap2.add_argument('--out', required=True)
    ap2.add_argument('--expect-sha')
    ap2.add_argument('--profile')
    ap2.add_argument('--report')
    ap2.add_argument('--health', dest='health', action='store_true', default=True,
                     help='写后跑 batch_health 按门比较 FAIL（默认开启）')
    ap2.add_argument('--no-health', dest='health', action='store_false', help='跳过写后体检')

    args = ap.parse_args(argv)
    fn = {'audit': cmd_audit, 'plan': cmd_plan, 'apply': cmd_apply}[args.cmd]
    try:
        return fn(args)
    except dl.GuardError as e:
        print('拒绝写出：' + str(e), file=sys.stderr)
        return 3
    except dl.ParentMismatch as e:
        print('中止：' + str(e), file=sys.stderr)
        return 2
    except (Abort, dl.AlignmentError, ValueError, KeyError, FileNotFoundError) as e:
        if args.debug:
            traceback.print_exc()
        print('中止：' + str(e), file=sys.stderr)
        return 2
    except Exception as e:
        if args.debug:
            traceback.print_exc()
        print('内部错误：' + str(e), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
