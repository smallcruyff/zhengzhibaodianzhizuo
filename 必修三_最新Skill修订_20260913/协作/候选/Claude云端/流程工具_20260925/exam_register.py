#!/usr/bin/env python3
"""新卷登记前检查：届别推算 + 重复登记拦截 + 建议卷号/改号链（新卷入书流水线第 2 步）。

背景：user-requirements-ledger.md REQ-PROJ-20260924-COHORT-YEAR——期中、期末按“届别”（该届学生
参加高考的年份）定年份，不是按考试日历年、不是按学年起始年。原件目录名/文件名/网站标题常按考试
年份命名，题库 exams.csv 的 year/school_year 也已知会错，都不能单独定届别。

用法
  check --exam-id BJ-2024-HD-QIZHONG [--report x.json]     # 题库已有卷复核
  check --files 原卷.pdf [细则.docx ...] [--region 海淀] [--stage 期中] [--claimed-id ...] [--report x.json]
  check --exam-dir DeepSeek.../questions/某卷目录 [--claimed-id ...] [--report x.json]
  audit [--report x.json]                                  # 对题库全部卷跑一遍
公共参数：--bank（默认按 --profile 的 sources.bank.root，否则 <仓库根>/DeepSeek_政治题库资料库_20260918）、
  --raw-root（默认 <仓库根>/00_共同资料/原材料）、--profile（名字或配置路径，只用来定位 paths.root 与
  --report 的写出守卫）、--debug（打印 traceback；可放在子命令前后）。

届别推算（证据由强到弱，见 infer_cohort）：
  A 原卷文字层（PDF 用 pypdf，取不到/不可读再用 fitz——两个引擎的结果都会做可读字符占比校验，
    印厂专用编码/轮廓字这类“有字符无可读中文”的乱码文字层按无文字层处理，不当成 A 层证据，见
    MIN_READABLE_RATIO 与 known_limits 的 M-J；DOCX 优先用 bh.read_docx，取不到退回 python-docx；
    全文，卷首证据只看第一题题号之前，且会跳过“考生须知/注意事项”一类说明性编号，避免在那里截断）
  B 题库该卷 README.md 前 HEADER_WINDOW 字 + 卷首说明文件（文件名/标题含“front_matter/卷首/身份”，
    如 00_exam_front_matter.md，整份）+ 逐题 MD 的“身份…”小节（不读题面，题面里的年份/年级不算
    证据；--exam-id 与 --exam-dir 走同一套读法）；这类叙述里“某日期属于一份被排除、改归到别的卷号
    的参考文件”不计入证据（见 EXCLUSION_MARKER_RX），但日期前 20 字内出现“本卷”时视为本卷自身的
    证据，不论后文是否出现排除措辞（m5：避免同一个长句里，本卷日期与另一份被排除文件的说明离得太近
    而被一起误伤）
  C indexes/exams.csv 的 year/school_year（弱证据，已知会错，只在 --exam-id 模式存在——命中即报告，
    单独出现且原件有可读文字层时定为 WEAK_ONLY；原件没有任何可用文字层时不能靠它独立定届别，见 M-K）
  D 目录名/文件名（最弱，只作旁证，永不参与裁决——不止在原件无文字层时才如此，原件有文字层但卷首
    没写日期/学年时同样不能退回文件名单独下断，见 known_limits 的 M-E）
  推算规则：找到“YYYY—YYYY学年”写法 → 届别=后一年；“YYYY届”→届别=YYYY；找到考试日期 → 期中/
  期末：9—12月→年+1，次年1月→年（不变）；一模/二模/高考：3—7月→年（不变）。卷首窗口内出现
  “高二”且未同时出现“高三”→ 届别在上述基础上再 +1（学年末年+1），并写进 issues 供复核。A 层有
  证据即按 A 层裁决（不与 B 层比较取 CONFLICT，见 infer_cohort 与 known_limits）；A/B 均无证据时看
  C（仅 --exam-id）；A/B 均无证据、且原件没有任何可用文字层时，C 的年份只作 weak_hint 参考列出，
  状态为 NEEDS_LOCAL、不生成建议号（M-K）；A/B/C 均无证据（或只有 D）同样 NEEDS_LOCAL。

重复登记 / 复用拦截：逐题做归一化（NFKC 全半角统一、去空白、去①-⑩、去 A-D 选项字母标记、去常见标点）
  后取 10-gram 字符指纹集合，用 containment=|交集|/min(两集合大小) 衡量相似度；单题 >= DUP_QUESTION_SIM
  记为匹配，候选题与对手卷内的题一对一贪心配对（按相似度降序，各只用一次，避免“须知编号误切/OCR
  碎片”把一道对手题重复算进多道候选题）；匹配题数占候选卷题数比例 > DUP_EXAM_FRACTION（严格大于）
  记为 duplicate_registration，否则只要有匹配即 shared_or_reused_questions；分母优先用题库覆盖率的
  total（fingerprint_coverage，而不是只数得出题面的那几道），覆盖率过低时降级为不判定 duplicate_
  registration（fraction_reliable=False）。--files 新卷模式下按各文件分别切题、分别比对（每份文件
  自己的块数做自己的分母，互不合并、互不稀释），同一对手卷在多份文件里都命中时取占比/可靠度最高的
  一份做判定（M-H：同一原卷给两份副本、或同一文件给两次，不会把重复登记稀释成复用）；切题只要出现
  “单调递增到位却半途卡住、后面题号全部吞进最后一块”的迹象（文中出现过的题号数远多于切出的块数，
  或某块长度远超中位数）即判该文件切题不可靠，按“整卷”同等降级处理，不参与 duplicate_registration
  判定（M-I，见 _split_is_reliable）。题面小节优先复用题库 bank.py 的受控别名表（同 qpack.
  adopted_stem_heading 口径，ast 只读，不 import、不执行）；表内未命中时退回 qpack.classify/
  classify_regex 按语义识别，OCR/候选类标题降级为 fallback_low_confidence 仍参与指纹，但任一侧
  （候选题或对手题）基于这类节的配对单列 low_confidence_pairs，不计入 duplicate_registration/
  shared_or_reused_questions 的判定（这类节常混入往年对照例题，是串题不是复用）。报告给出每卷
  fingerprint_coverage（按 basis 分解），覆盖率过低写 issue，不悄悄漏检。阈值均为本文件顶部常量，
  写进报告 thresholds。

改号链：若建议卷号已被占用，对占用卷递归复核（届别 + 它自己的重复登记情况），拓扑出 rename_plan
  （retire 占用卷 → 已存在的正确登记 / 或占用卷自己改号腾位）与 old→new 的 redirects 草案（含本卷
  自己的旧号→新号，见 reused_ids：同一卷号在不同执行阶段可能指向不同的考试）。只有占用卷自身登记号
  与证据不符、且目标卷号本身正确时才 retire 占用卷；占用卷登记号本身没问题（只是恰好与另一张卷判定
  重复）时终止为 blocked_conflict，不给 redirects——不会把“正确卷号”并入“错号”。候选本身与占用卷
  判定重复登记时，直接给出“已登记为 X，不要再登记”，不构造改号链。只给建议，不改题库。

只读，除 --report（落 guard_write 允许的位置；云端另加 REPO_ROOT/bank/raw_root 为受保护根，见
write_report，因为 guard_write 默认的受保护根只认调用方 --profile 里登记的路径，不传 --profile 时
不能只靠它）。不改题库、不改书稿。
退出码：0 无问题；1 有待处理（届别与卷号不符、重复登记、建议卷号被占用、证据冲突、需本地看图、
  弱证据、覆盖率过低）；2 输入/参数错误；3 拒绝写出。异常一律中文提示，不打印 traceback（--debug 打开）。
"""
import sys

sys.dont_write_bytecode = True  # 不在 Skill 母版 scripts/ 里留下 __pycache__

import argparse
import csv
import hashlib
import json
import logging
import os
import re
import traceback
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

logging.getLogger('pypdf').setLevel(logging.ERROR)  # pypdf 的英文告警（EOF marker not found 等）不落到 stderr

TOOL = 'exam_register'
VERSION = '1.3.0'

# ---------------------------------------------------------------- 常量（阈值写进报告，勿散落魔数）
NGRAM_N = 10                 # 归一化后字符 n-gram 长度
DUP_QUESTION_SIM = 0.55      # 单题相似度阈值（containment）；真实重复对实测 0.97，无关题对实测 0.0
DUP_EXAM_FRACTION = 0.5      # 匹配题数占候选卷题数比例超过此值（严格 >，见 scan_duplicates/m7）→
                              # duplicate_registration，否则 shared_or_reused；规格原文“大部分题相同”，
                              # 恰好一半不算“大部分”
MIN_TEXT_LEN = 60            # 原件抽出的文字少于此长度视为“无有效文字层”
CANDIDATE_MAX_ROOTS = 2      # locate_raw_files 最多取几份原件
MIN_STEM_LEN = 40            # 归一化后题面短于此长度视为抽取失败，跳过指纹，计入 duplicates_skipped_no_stem
HEADER_WINDOW = 1000         # 找不到第一个题号时，卷首证据窗口退回的字符数上限
MIN_FINGERPRINT_COVERAGE = 0.7   # 单卷题面指纹覆盖率低于此值时写 issue（audit 汇总“不可查重的卷”）
RAW_MAX_PAGES = 60           # 原件全文抽取的页数上限（PDF）；真实原卷通常 6～12 页，留足余量
RAW_MAX_CHARS = 200000       # 原件全文抽取的字符数上限（DOCX），只作失控保护，不是常规截断
HEADER_RAW_MAX_PAGES = 6     # 届别证据只看卷首，原件只需抽前几页就够（比全文抽取快得多）
HEADER_RAW_MAX_CHARS = 8000  # 同上，DOCX 版
MAX_RENAME_CHAIN_DEPTH = 6   # 改号链最多展开几层，超出报“链条过长，需人工核查”，不是真的会有这么长
MIN_READABLE_RATIO = 0.30    # 抽出的文字里 CJK 汉字占比低于此值时，视为“有字符但无可读中文”的乱码
                              # 文字层（印厂专用编码/轮廓字），按无文字层处理，不当 A 层证据（M-J；
                              # 真实乱码原件用 pypdf 实测占比 0.0，退回 fitz 后取到的也只是版心外的
                              # 几个字（如版式代号“【四校】…”），占比 0.17，仍是页眉页脚残片不是正文，
                              # 正常原件正文占比 0.74+，阈值取两者中间偏正常一侧，留足余量）
SPLIT_MAX_MISSING_QNUM = 2   # 原件全文里出现过的题号（不要求单调）比实际切出的块数多出这么多，视为
                              # 中途漏切、后面的题号全部被吞进最后一块（M-I）


# ---------------------------------------------------------------- 定位 Skill 脚本目录（硬规则 1）
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
    raise SystemExit(
        '找不到 Skill 脚本目录（docx_lib.py）：本文件同目录、环境变量 BAODIAN_SKILL_SCRIPTS、'
        '向上逐级 .claude/skills/beijing-gaokao-politics/scripts 均未找到')


SK_DIR = _find_skill_dir()
sys.path.insert(0, str(SK_DIR))
try:  # m9：环境缺依赖（如 lxml/python-docx）时给中文提示、退出2，不打印英文 traceback
    import docx_lib as dl  # noqa: E402
    import batch_health as bh  # noqa: E402  （复用其 read_docx 取原件段落流，含表格单元格文字；m2：
                                 # python-docx 直读会漏掉表格里的卷首，改用与 docx_lib 同源的这份读法）
    import qpack  # noqa: E402  （复用其 split_md/guide_fields/adopted_stem_heading/classify/load_bank_tables）
    from block_index import REGION, STAGE  # noqa: E402  （复用题库区县/阶段代码表，不另写一套）
    from profile_lib import load_profile  # noqa: E402
except Exception as _sk_import_err:
    print(f'Skill 依赖模块加载失败（环境缺少依赖，如 lxml/python-docx 等）：{_sk_import_err}', file=sys.stderr)
    if '--debug' in sys.argv:
        traceback.print_exc()
    sys.exit(2)

REGION_CODE = {v: k for k, v in REGION.items()}
STAGE_CODE = {v: k for k, v in STAGE.items()}
STAGE_CODE['GAOKAO'] = '高考'


def _repo_root_from_sk(sk_dir):
    for anc in [sk_dir] + list(sk_dir.parents):
        if anc.name == '.claude':
            return anc.parent
    return sk_dir.parents[3] if len(sk_dir.parents) >= 4 else sk_dir.parent


REPO_ROOT = _repo_root_from_sk(SK_DIR)


# ---------------------------------------------------------------- 基础工具
def sha256_file(p):
    return dl.sha256_file(p)


def read_csv_rows(path):
    if not path.is_file():
        return []
    with open(path, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def now_iso():
    return datetime.now(timezone.utc).isoformat()


class InputError(Exception):
    """参数/输入错误，退出码 2。"""


class ExamIdFormatError(InputError):
    pass


EXAM_ID_RX = re.compile(r'^BJ-(?P<year>\d{4})-(?P<region>[A-Z]{2,4})-(?P<stage>YIMO|ERMO|QIMO|QIZHONG|GAOKAO)$')


def parse_exam_id(exam_id):
    m = EXAM_ID_RX.match((exam_id or '').strip())
    if not m:
        raise ExamIdFormatError(f'卷号格式不符合 BJ-<年>-<区县代码>-<阶段代码>：{exam_id!r}')
    year = int(m.group('year'))
    reg_code, stg_code = m.group('region'), m.group('stage')
    if stg_code == 'GAOKAO':
        if reg_code != 'BJ':
            raise ExamIdFormatError(f'高考卷号区县位固定为 BJ（本市统考，不分区县）：{exam_id!r}')
        region_name = '北京市（高考）'
    else:
        if reg_code not in REGION_CODE:
            raise ExamIdFormatError(f'卷号区县代码未知（block_index.REGION 无此代码）：{reg_code!r}（{exam_id}）')
        region_name = REGION_CODE[reg_code]
    return {'exam_id': exam_id, 'year': year, 'region_code': reg_code, 'region_name': region_name,
            'stage_code': stg_code, 'stage_name': STAGE_CODE[stg_code]}


def build_exam_id(cohort_year, region_name, stage_name):
    if stage_name == '高考':
        return f'BJ-{cohort_year}-BJ-GAOKAO'
    if region_name not in REGION:
        raise InputError(f'区县名不在 block_index.REGION 表中：{region_name!r}')
    if stage_name not in STAGE:
        raise InputError(f'阶段名不在 block_index.STAGE 表中：{stage_name!r}')
    return f'BJ-{cohort_year}-{REGION[region_name]}-{STAGE[stage_name]}'


# ---------------------------------------------------------------- 文字抽取（原始文件；非书稿，不走 docx_lib 的父稿对齐）
class RawOpenError(Exception):
    """文件本身打不开（损坏/非本格式），区别于“打开了但没有文字层”。"""


def _import_fitz_quiet():
    """PyMuPDF 的 fitz 兼容层 import 时会直接 print 一行弃用提示到 stdout（不是走 warnings/stderr），
    会把本工具的 stdout JSON 弄脏；延迟导入时临时吞掉 stdout。"""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        import fitz
    return fitz


_CJK_RX = re.compile(r'[一-鿿]')


def _readable_ratio(text):
    """M-J：抽出的字符里 CJK 汉字占比。题库全部是中文卷子，正常抽出的正文 CJK 占比通常在 70% 以上；
    印厂专用编码/轮廓字这类字体，pypdf/fitz 抽出的往往是私用区/控制字符，偶尔夹杂几个可打印 ASCII
    字母（如某些嵌入字体的 glyph 名残留），长度可能过 MIN_TEXT_LEN，但 CJK 占比接近 0——只看长度、
    或把可打印 ASCII 也算作“可读”都会把这类乱码误判为“有文字层”（真实原件 CJK 占比实测 0.0 vs
    正常原件 0.74+，见审查 r3 probe_garbled_textlayer_r3.log）。空文本按 0 处理（调用方另有
    MIN_TEXT_LEN 的长度判定）。"""
    s = text.strip()
    if not s:
        return 0.0
    return len(_CJK_RX.findall(s)) / len(s)


def _text_usable(text):
    return len(text.strip()) >= MIN_TEXT_LEN and _readable_ratio(text) >= MIN_READABLE_RATIO


def extract_pdf_text(path, max_pages=RAW_MAX_PAGES):
    """PDF 全文（至多 max_pages 页）；pypdf 结果长度不够或可读字符占比过低（M-J）时再试 fitz（延迟
    导入）；两者都可用时取更长的一份，只有一份可用时取可用的那份，两者都不可用时仍返回更长的一份
    （长度供参考，调用方按 _text_usable 判定“无文字层”，不是靠这里的返回值二次判定）。两者都打不开
    文件本身（损坏/加密/非 PDF）→ 抛 RawOpenError；打开了但页面空白/乱码 → 返回原样文本，调用方按
    “无文字层”处理，不是输入错误。返回 (text, engine)。"""
    text_pypdf, text_fitz = '', ''
    pypdf_opened = fitz_opened = False
    try:
        from pypdf import PdfReader
        r = PdfReader(str(path))
        pypdf_opened = True
        parts = []
        for i in range(min(max_pages, len(r.pages))):
            try:
                parts.append(r.pages[i].extract_text() or '')
            except Exception:
                pass
        text_pypdf = '\n'.join(parts)
    except Exception:
        text_pypdf = ''
    if not _text_usable(text_pypdf):
        try:
            fitz = _import_fitz_quiet()
            doc = fitz.open(str(path))
            fitz_opened = True
            parts = []
            for i in range(min(max_pages, doc.page_count)):
                parts.append(doc[i].get_text() or '')
            doc.close()
            text_fitz = '\n'.join(parts)
        except Exception:
            text_fitz = ''
    if not pypdf_opened and not fitz_opened:
        raise RawOpenError(f'PDF 打不开（损坏或非本格式）：{path}')
    pypdf_ok, fitz_ok = _text_usable(text_pypdf), _text_usable(text_fitz)
    if pypdf_ok and not fitz_ok:
        return text_pypdf, 'pypdf'
    if fitz_ok and not pypdf_ok:
        return text_fitz, 'fitz'
    text, engine = (text_pypdf, 'pypdf')
    if len(text_fitz.strip()) > len(text_pypdf.strip()):
        text, engine = (text_fitz, 'fitz')
    return text, engine


def extract_docx_text(path, max_chars=RAW_MAX_CHARS):
    """优先用 bh.read_docx（docx_lib 同源读法）：段落流含表格单元格递归展开的文字，python-docx 直读
    的 d.paragraphs 不含表格内容，原卷卷首常见的表格版式（如两栏卷头）会因此漏读（m2）。bh.read_docx
    打不开（极少数非常规 docx 结构）时退回 python-docx 直读，仍能力所能及地抽出正文；两者都不含
    文本框（wps:txbx/w:pict）内文字——batch_health 全库其它工具同样不解析文本框，不在本工具里另起
    一套，如实记入 known_limits。"""
    try:
        items, _tcount = bh.read_docx(str(path))
    except Exception:
        items = None
    if items is not None:
        parts, total = [], 0
        for it in items:
            t = it.get('text') or ''
            if t:
                parts.append(t)
                total += len(t)
            if total >= max_chars:
                break
        if parts:
            return '\n'.join(parts), 'docx_lib(bh.read_docx)'
    try:
        import docx
    except Exception as e:
        raise RawOpenError(f'python-docx 不可用：{e}')
    try:
        d = docx.Document(str(path))
    except Exception as e:
        raise RawOpenError(f'DOCX 打开失败（损坏或非本格式）：{e}')
    parts = []
    total = 0
    for p in d.paragraphs:
        t = p.text or ''
        if t.strip():
            parts.append(t)
            total += len(t)
        if total >= max_chars:
            break
    return '\n'.join(parts), 'python-docx(fallback)'


def extract_file_text(path, max_pages=RAW_MAX_PAGES, max_chars=RAW_MAX_CHARS):
    suf = path.suffix.lower()
    if suf == '.pdf':
        return extract_pdf_text(path, max_pages=max_pages)
    if suf == '.docx':
        return extract_docx_text(path, max_chars=max_chars)
    raise RawOpenError(f'不支持的格式（{suf}），需先转成 .pdf/.docx 或本地转写')


# ---------------------------------------------------------------- 届别推算
SCHOOL_YEAR_RX = re.compile(r'(20\d{2})\s*[—\-–~至]\s*(20\d{2})\s*学年')
# 日期写法：2024.11 / 2024-11 / 2024年11月 / 2024 ~ 2025 学年度…2024.11（取最后出现的月份数字）
DATE_RX = re.compile(r'(20\d{2})\s*[.\-年]\s*0?(\d{1,2})\s*月?(?!\d)')
GRADE2_RX = re.compile(r'高二(?!.{0,6}升高三)')  # “高二”出现（排除“高二升高三”这类跨届描述，保守）
GRADE3_RX = re.compile(r'高三')
ISO_TS_TAIL_RX = re.compile(r'-\d{2}T\d{2}:')  # 紧跟“-DDTHH:”→是 2026-09-24T10:32:35 一类验收时间戳，非考试日期
# 高考卷原文常只写年份、不写月（如“2025 北京高考真题”“2025年北京…统一考试”），高考只在每年6月，
# 年份本身即届别，不需要月份换算，单列一条规则。
GAOKAO_YEAR_RX = re.compile(
    r'(20\d{2})\s*年?\s*(?:北京)?\s*(?:高考真题|普通高等学校招生全国统一考试|普通高中学业水平等级性考试|高考)')
# 网站式标题“YYYY 北京XX高三（上）期中/期末”：这类标题按考次月份规则换算（期中默认按上学期9-12月估，
# 即 YYYY+1；期末不带月份信息，太弱，不生成候选，只作 D 级旁证由 filename 规则处理）
WEBTITLE_QIZHONG_RX = re.compile(r'(20\d{2})\s*(?:北京)?\S{0,4}高三[（(]?上[）)]?\S{0,4}期中')
# 题号切分：行首“N．/N、”，不要求后面不是数字（“2．2025年8月……”这类题号后紧跟年份的写法也要认得出，
# 靠 split_questions_raw 的“单调递增”校验过滤误切；卷首窗口截断点复用同一条正则）
QNUM_SPLIT_RX = re.compile(r'(?:(?<=\n)|^)\s*(\d{1,3})[.、．]')
# 常见扫描字体把句点渲染进私用区（PUA/PUA-A/PUA-B）：数字之间出现私用区字符，当作句点处理
_PUA_DOT_RX = re.compile(r'(?<=\d)\s*[\U0000E000-\U0000F8FF\U000F0000-\U000FFFFD\U00100000-\U0010FFFD]+\s*(?=\d)')
# “YYYY届”：届别的直接写法，届别年即 YYYY 本身，不需要月份/学年换算（m4 部分修复，见 known_limits）
COHORT_YIJIE_RX = re.compile(r'(20\d{2})\s*届')
# README/身份说明里常见的“排除/改归属”表述：紧跟在某个学年/日期之后，说明该日期属于一份被排除、
# 改归到别的卷号的参考文件，不是本卷自身的证据（m3：避免 README 叙述里提到的另一场考试污染本卷判定）
EXCLUSION_MARKER_RX = re.compile(
    r'不是同一场考试|已正确归属到|不采用|不采纳|错配|另属|并非本卷|非本卷|不属于本卷|已改registrar|该文件属于')
EXCLUSION_LOOKAHEAD = 220
EXCLUSION_LOOKBEHIND = 20    # m5：日期/学年前这么多字内若出现“本卷”，视为本卷自身的证据，不论后文
                              # 是否出现排除标记——README 常见的一整句话里同时提到“本卷（日期）”和
                              # 一份被排除文件的说明，固定往后看 220 字会连本卷自己的日期一起误伤


def _normalize_raw(text):
    """NFKC（全半角统一）+ 私用区伪句点修复；届别推算与切题共用同一份归一化，避免各自漏判。"""
    text = unicodedata.normalize('NFKC', text or '')
    return _PUA_DOT_RX.sub('.', text)


def _first_question_start(text):
    """找“正文题号真正的起点”，不是文本里第一个形如“N．”的东西——“考生须知/注意事项”一类说明性
    编号（“1．本试卷共8页。2．考试时长90分钟。3．……”）自己也满足这个形状，且往往紧跟在卷首日期
    之后；若直接取第一个匹配来截断，会连日期一起截掉（m5）。改为枚举每个“1．”作为候选起点，各自
    往后数能单调递增（1,2,3,…，中间夹杂的无关数字忽略，不中断，遇到下一个“1”才收尾）多少步，取
    步数最多的那个候选——正文题号通常有十几二十道，比须知的两三条编号长得多。步数 < 3 的候选不采信
    （太短，不足以确认是正文），找不到则返回 None（退回不截断）。"""
    matches = list(QNUM_SPLIT_RX.finditer(text))
    best_start, best_len = None, 0
    for i, m in enumerate(matches):
        if int(m.group(1)) != 1:
            continue
        expect, length = 2, 1
        for m2 in matches[i + 1:]:
            v = int(m2.group(1))
            if v == expect:
                length += 1
                expect += 1
            elif v == 1:
                break  # 下一个“1”另起一段候选，当前候选到此为止
        if length > best_len:
            best_len, best_start = length, m.start()
    return best_start if best_len >= 3 else None


def header_window_text(text, window=HEADER_WINDOW, cut_at_qnum=False):
    """卷首窗口：默认只取前 window 字（README/身份小节/exams.csv/文件名都很短，这样最安全，不会把
    远处无关小节——如 README 里“## 本轮修订记录（……2026-09-22……）”这类工程日志——当成卷首信息）。
    cut_at_qnum=True 时改为“截到第一个题号之前”，只用于原件全文（Tier A）：原件前几千字里第1—3题的
    题干/年级/日期字样不是卷子自身的届别信息，必须先把它们切掉，不能只按固定字数截；截断点见
    _first_question_start（跳过“考生须知”一类说明性编号，见 m5）。"""
    text = _normalize_raw(text)
    if cut_at_qnum:
        pos = _first_question_start(text)
        if pos and pos > 0:
            return text[:min(pos, window * 6)]
    return text[:window]


def _cohort_from_school_year(y1, y2, is_g2):
    base = y2
    return base + 1 if is_g2 else base


def _cohort_from_date(year, month, stage_name, is_g2):
    if stage_name in ('期中', '期末'):
        if 9 <= month <= 12:
            base = year + 1
        elif month == 1:
            base = year
        else:
            return None
    elif stage_name in ('一模', '二模', '高考'):
        if 3 <= month <= 7:
            base = year
        else:
            return None
    else:
        return None
    return base + 1 if is_g2 else base


def extract_year_signals(text, source, tier, stage_name, window=HEADER_WINDOW, cut_at_qnum=False):
    """从一段文字的卷首窗口里找“学年”写法与“年.月”写法，各自推出候选届别；返回证据条目列表。
    只看卷首：cut_at_qnum=True（原件全文）时窗口截到第一个题号之前，题干正文里偶尔出现的年份/年级
    字样（如某道题面提到“高二年级足球联赛”）不会混入；其余来源（README/身份小节/exams.csv/文件名）
    本来就短，用固定字数窗口即可，不找题号（找了反而可能把远处无关小节的日期带进来）。"""
    if not text:
        return []
    text = header_window_text(text, window, cut_at_qnum=cut_at_qnum)
    out = []
    is_g2 = bool(GRADE2_RX.search(text)) and not GRADE3_RX.search(text)

    def _excluded(start_pos, end_pos):
        # m5：日期/学年紧跟在“本卷（……）”这类括注里，是本卷自身的证据，不论同一个长句后文是否
        # 出现下面这条排除标记（常见写法是一整句话里先提本卷日期作对照，再说明另一份文件被排除）
        if '本卷' in text[max(0, start_pos - EXCLUSION_LOOKBEHIND):start_pos]:
            return False
        # README/身份小节常见写法：某个日期/学年紧跟着“……不是同一场考试，已正确归属到 BJ-xxx”一类
        # 说明，讲的是一份被排除、改归到别的卷号的参考文件，不是本卷自身的证据（m3）
        return bool(EXCLUSION_MARKER_RX.search(text[end_pos:end_pos + EXCLUSION_LOOKAHEAD]))

    for m in SCHOOL_YEAR_RX.finditer(text):
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y2 - y1 != 1:
            continue
        if _excluded(m.start(), m.end()):
            out.append({'tier': tier, 'source': source, 'kind': 'school_year_excluded_ref', 'raw': m.group(0),
                        'cohort_year': None, 'grade2': is_g2,
                        'snippet': _snippet(text, m.start(), m.end(), radius=60)})
            continue
        cohort = _cohort_from_school_year(y1, y2, is_g2)
        out.append({'tier': tier, 'source': source, 'kind': 'school_year', 'raw': m.group(0),
                     'cohort_year': cohort, 'grade2': is_g2,
                     'snippet': _snippet(text, m.start(), m.end())})
    for m in DATE_RX.finditer(text):
        year, month = int(m.group(1)), int(m.group(2))
        if not (1 <= month <= 12):
            continue
        if ISO_TS_TAIL_RX.match(text, m.end()):
            continue  # 形如 2026-09-24T10:32:35 的验收/记录时间戳，不是考试日期
        if _excluded(m.start(), m.end()):
            out.append({'tier': tier, 'source': source, 'kind': 'exam_date_excluded_ref', 'raw': m.group(0),
                        'cohort_year': None, 'grade2': is_g2, 'month': month,
                        'snippet': _snippet(text, m.start(), m.end(), radius=60)})
            continue
        cohort = _cohort_from_date(year, month, stage_name, is_g2)
        if cohort is None:
            continue
        out.append({'tier': tier, 'source': source, 'kind': 'exam_date', 'raw': m.group(0),
                     'cohort_year': cohort, 'grade2': is_g2, 'month': month,
                     'snippet': _snippet(text, m.start(), m.end())})
    for m in COHORT_YIJIE_RX.finditer(text):
        year = int(m.group(1))
        if _excluded(m.start(), m.end()):
            continue
        out.append({'tier': tier, 'source': source, 'kind': 'cohort_yijie', 'raw': m.group(0),
                    'cohort_year': year, 'grade2': is_g2,
                    'snippet': _snippet(text, m.start(), m.end())})
    if stage_name == '高考':
        for m in GAOKAO_YEAR_RX.finditer(text):
            year = int(m.group(1))
            cohort = year + 1 if is_g2 else year
            out.append({'tier': tier, 'source': source, 'kind': 'gaokao_year', 'raw': m.group(0),
                        'cohort_year': cohort, 'grade2': is_g2,
                        'snippet': _snippet(text, m.start(), m.end())})
    elif stage_name == '期中':
        for m in WEBTITLE_QIZHONG_RX.finditer(text):
            year = int(m.group(1))
            cohort = (year + 1 + 1) if is_g2 else (year + 1)
            out.append({'tier': tier, 'source': source, 'kind': 'webtitle_qizhong', 'raw': m.group(0),
                        'cohort_year': cohort, 'grade2': is_g2,
                        'snippet': _snippet(text, m.start(), m.end())})
    return out


def _snippet(text, start, end, radius=24):
    a, b = max(0, start - radius), min(len(text), end + radius)
    return re.sub(r'\s+', ' ', text[a:b]).strip()


def _resolve_tier(tier_ev):
    """同一层内多条证据：全一致→OK；多数一致、个别不同（多为题干正文引用的无关历史日期，如“1944年7月11日
    开始的实验，直到2013年7月11日……”混进候选）→按多数裁决，少数记为 outlier 但保留在证据里，不隐瞒；
    真正打平（如 1:1、2:2）→ CONFLICT，不代裁决。"""
    counts = Counter(e['cohort_year'] for e in tier_ev)
    if len(counts) == 1:
        return next(iter(counts)), 'OK', []
    ranked = counts.most_common()
    if ranked[0][1] > ranked[1][1]:
        outliers = [v for v, c in ranked[1:]]
        return ranked[0][0], 'OK_MAJORITY', outliers
    return None, 'CONFLICT', []


def infer_cohort(evidences):
    """按证据层裁决：A 层有可用证据就按 A 层定（不再与 B 层比较），A 层没有证据再看 B 层——同一份卷子
    的原件文字层（A）与题库整理出的身份说明（B）都指向卷子本身，不是两个互相独立、地位相等的信源，
    没有必要为“A 说 2024、B 说 2025”强行报 CONFLICT；A 层内部、或 B 层内部意见不一致时仍报 CONFLICT。
    A/B 均无证据时看 C（exams.csv，已知会错，仅在 --exam-id 模式下存在）→ WEAK_ONLY；C 也没有则
    NEEDS_LOCAL。D（目录名/文件名）永远不参与裁决（M-E：规格明令“最弱，只作旁证，不能单独定届别”，
    不止在原件无文字层时才如此——原件有文字层但卷首没写日期/学年时，同样不能退回文件名单独下断），
    只在证据里如实带出供人工参考。"""
    usable = [e for e in evidences if e.get('cohort_year') is not None]  # bare_year 等纯信息条目不参与裁决
    strong = [e for e in usable if e['tier'] in ('A', 'B')]
    weak_c = [e for e in usable if e['tier'] == 'C']
    if not strong:
        if weak_c:
            cohort, status, outliers = _resolve_tier(weak_c)
            return {'cohort_year': cohort, 'status': 'WEAK_ONLY' if status.startswith('OK') else 'CONFLICT',
                    'grade2': any(e.get('grade2') for e in weak_c), 'outliers': outliers}
        return {'cohort_year': None, 'status': 'NEEDS_LOCAL', 'grade2': False, 'outliers': []}
    for tier in ('A', 'B'):
        tier_ev = [e for e in strong if e['tier'] == tier]
        if not tier_ev:
            continue
        cohort, status, outliers = _resolve_tier(tier_ev)
        return {'cohort_year': cohort, 'status': 'OK' if status.startswith('OK') else 'CONFLICT',
                'grade2': any(e.get('grade2') for e in tier_ev), 'outliers': outliers}
    return {'cohort_year': None, 'status': 'CONFLICT', 'grade2': False, 'outliers': []}


# ---------------------------------------------------------------- 原件定位（exam_files.csv 优先，退回 MD 里的“来源：`路径`”引用）
ROLE_PRIORITY = ['原卷', '教师版', '混合载体']
SRC_REF_RX = re.compile(r'[`]([^`]+\.(?:pdf|docx|doc|rtf))[`]', re.IGNORECASE)


def locate_raw_files_by_csv(exam_id, exam_files_rows, raw_root):
    rows = [r for r in exam_files_rows if r.get('exam_id') == exam_id]
    rows = [r for r in rows if r.get('role') in ROLE_PRIORITY and r.get('format', '').lower() in ('pdf', 'docx')]
    rows.sort(key=lambda r: (ROLE_PRIORITY.index(r['role']), r.get('rel_path', '')))
    out = []
    seen = set()
    for r in rows:
        rel = r.get('rel_path')
        if not rel or rel in seen:
            continue
        seen.add(rel)
        p = resolve_raw_path(rel, raw_root)
        if p is not None:
            out.append({'path': p, 'rel_path': rel, 'role': r.get('role')})
        if len(out) >= CANDIDATE_MAX_ROOTS:
            break
    return out


def resolve_raw_path(rel_path, raw_root):
    p = (raw_root / rel_path)
    if p.is_file():
        return p
    sub = REPO_ROOT / '云端' / '大文件PDF版' / '00_共同资料' / '原材料' / (rel_path + '.pdf')
    if sub.is_file():
        return sub
    return None


def locate_raw_files_via_md_refs(md_texts, raw_root):
    """从逐题 MD 全文（含“### 来源”一类工程小节）里“来源：`路径`”一类引用退出候选原件路径
    （exam_files.csv 查不到时的退路）。传入的必须是 MD 原文，不能是已抽出的题面——题面小节按规则
    跳过 ### 子标题，那样“来源：`路径`”永远命中不到。"""
    seen, out = set(), []
    for text in md_texts:
        for m in SRC_REF_RX.finditer(text):
            rel = m.group(1)
            if rel in seen:
                continue
            seen.add(rel)
            ctx = _snippet(text, m.start(), m.end(), radius=12)
            role_hint = '原卷' if ('原卷' in ctx or 'native' in ctx) else ('教师版' if '教师版' in ctx else '')
            p = resolve_raw_path(rel, raw_root)
            if p is not None and p.suffix.lower() in ('.pdf', '.docx'):
                out.append({'path': p, 'rel_path': rel, 'role': role_hint or '未知'})
    out.sort(key=lambda r: 0 if r['role'] == '原卷' else (1 if r['role'] == '教师版' else 2))
    return out[:CANDIDATE_MAX_ROOTS]


# ---------------------------------------------------------------- 题面/身份小节抽取（复用 qpack，不另写识别逻辑）
IDENTITY_HEAD_PREFIX = '身份'
FRONT_MATTER_NAME_RX = re.compile(r'front_matter|卷首|试卷身份', re.IGNORECASE)  # m3：这类文件是独立的
                              # 顶级标题（“# … 试卷身份与卷首说明”），不是逐题 MD 里的“## 身份…”
                              # 小节，identity_section_text 找不到，需单独按文件名识别、整份当 B 层证据


def _find_front_matter(exam_dir):
    if not exam_dir or not exam_dir.is_dir():
        return None
    for p in sorted(exam_dir.glob('*.md')):
        if p.name.upper() != 'README.MD' and FRONT_MATTER_NAME_RX.search(p.name):
            return p
    return None


def load_bank_alias_tables(bank_root):
    """题库 bank.py 的小节别名表（ast 只读，不 import、不执行，不留 __pycache__），与 qpack 同口径；
    bank.py 不存在或读取失败时返回 (None, None)，调用方退回 qpack.classify_regex 单独工作。"""
    bank_py = bank_root / 'scripts' / 'bank.py'
    if not bank_py.is_file():
        return None, None
    try:
        return qpack.load_bank_tables(bank_py)
    except Exception:
        return None, None


def _clean_section_body(body):
    """qpack.split_md 按 ## 切出的小节正文常把题面整段放进 blockquote；去掉引用符号本身与纯说明性
    引用行（“本节/本题/本卷……”），题面/身份内容原样保留——qpack 没有单独暴露这一步，这里薄封装。"""
    out = []
    for l in body.splitlines():
        if l.startswith('### '):
            continue
        if l.startswith('>'):
            inner = l[1:].strip()
            if not inner or inner.startswith(('本节', '本题', '本卷')):
                continue
            out.append(inner)
            continue
        out.append(l)
    return '\n'.join(out).strip()


def identity_section_text(md_text):
    """逐题 MD 里“身份…”小节的正文（question_id/exam_id/题号等元信息，不含题面）——Tier B 证据只读
    这里，不读题面，避免题干里的年份/年级字样冒充卷子自身的届别信息。"""
    try:
        _, secs = qpack.split_md(md_text)
    except Exception:
        return ''
    for s in secs:
        if s['heading'].startswith(IDENTITY_HEAD_PREFIX):
            return _clean_section_body(s['body'])
    return ''


def extract_stem_from_md(text, T=None):
    """题面抽取：优先 qpack.adopted_stem_heading（与 bank.py get --with-rubric 同口径的受控别名表，
    含“读取指引”里的“采用题面小节”）；命中即为 confirmed（basis='bank_guide'/'bank_alias'）。
    未命中时退回 qpack.classify/classify_regex 按标题语义识别 stem 角色的小节：非 OCR/候选类的记
    fallback_regex；只剩 OCR 候选/教师版含答案这类小节时仍纳入（basis='fallback_low_confidence'，
    覆盖率与噪声风险在报告里如实注明，不是悄悄漏检）。都取不到时返回 ('', None)。"""
    try:
        pre, secs = qpack.split_md(text)
    except Exception:
        return '', None
    if not secs:
        body = pre.strip()
        return (body, 'no_heading') if body else ('', None)
    if T is not None:
        guide = qpack.guide_fields(secs)
        heading, basis = qpack.adopted_stem_heading(secs, T, guide)
        if heading:
            sec = next((s for s in secs if s['heading'] == heading), None)
            if sec:
                body = _clean_section_body(sec['body'])
                if body:
                    return body, basis
    picked, ocr = [], []
    for s in secs:
        role, rbasis = (qpack.classify(s['heading'], T, None) if T is not None else qpack.classify_regex(s['heading']))
        if role != 'stem':
            continue
        body = _clean_section_body(s['body'])
        if not body:
            continue
        (ocr if rbasis == 'bank_passthrough' else picked).append(body)
    if picked:
        return '\n'.join(picked), 'fallback_regex'
    if ocr:
        return '\n'.join(ocr), 'fallback_low_confidence'
    return '', None


# ---------------------------------------------------------------- 归一化与 n-gram 指纹
_STRIP_RX = re.compile(
    r'[\s，。、；：？！“”‘’《》〈〉「」『』【】（）()\[\]{}.,;:!?\-—–·…"\']')
_CIRCLE_RX = re.compile(r'[①②③④⑤⑥⑦⑧⑨⑩]')
_OPTLETTER_RX = re.compile(r'[A-D][.、．]')


def normalize_stem(s):
    s = unicodedata.normalize('NFKC', s or '')
    s = _CIRCLE_RX.sub('', s)
    s = _OPTLETTER_RX.sub('', s)
    s = _STRIP_RX.sub('', s)
    return s.lower()


def ngrams(s, n=NGRAM_N):
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def fingerprint_stem(stem):
    """题面 -> 归一化后的 n-gram 集合；归一化后短于 MIN_STEM_LEN 视为抽取失败，返回 None（不是真的短题）。"""
    norm = normalize_stem(stem)
    if len(norm) < MIN_STEM_LEN:
        return None
    return ngrams(norm)


def containment(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / min(len(a), len(b))


# ---------------------------------------------------------------- 题库题面语料（供重复/复用比对）
def bank_exam_ids(bank_root):
    qd = bank_root / 'questions'
    if not qd.is_dir():
        return []
    return sorted(p.name for p in qd.iterdir() if p.is_dir() and p.name.startswith('BJ-'))


def _coverage_summary(total, entries):
    by_basis = Counter(e['basis'] for e in entries)
    found = len(entries)
    return {'total': total, 'found': found, 'ratio': round(found / total, 4) if total else 1.0,
            'by_basis': dict(by_basis)}


def load_exam_questions(bank_root, exam_id, T=None):
    """返回 (out, skipped, coverage)：out=[{'qid','text','ngrams','basis'}]；抽不出题面/短于
    MIN_STEM_LEN 的题跳过，计入 skipped；coverage 是本卷题面指纹覆盖率（按 basis 分解，见
    MIN_FINGERPRINT_COVERAGE）。"""
    qd = bank_root / 'questions' / exam_id
    out, skipped = [], []
    files = sorted(qd.glob(f'{exam_id}-Q*.md')) if qd.is_dir() else []
    for p in files:
        try:
            raw = p.read_text(encoding='utf-8')
        except OSError:
            continue
        stem, basis = extract_stem_from_md(raw, T)
        ng = fingerprint_stem(stem) if stem else None
        if not ng:
            skipped.append(p.stem)
            continue
        out.append({'qid': p.stem, 'text': stem, 'ngrams': ng, 'basis': basis})
    return out, skipped, _coverage_summary(len(files), out)


class BankIndex:
    """题库题面倒排索引：ngram -> {(exam_id, qid), ...}，避免全量 O(n^2) 比对。"""

    def __init__(self, bank_root):
        self.bank_root = bank_root
        self.T, self.T_fp = load_bank_alias_tables(bank_root)
        self.by_exam = {}       # exam_id -> [{'qid','ngrams','basis'}, ...]
        self.posting = {}       # ngram -> set((exam_id, qid))
        self.skipped = {}       # exam_id -> [qid,...]（抽不出题面）
        self.coverage = {}      # exam_id -> coverage dict
        self.exam_row_by_id = {}

    def ensure(self, exam_id):
        if exam_id in self.by_exam:
            return
        qs, skipped, cov = load_exam_questions(self.bank_root, exam_id, self.T)
        self.by_exam[exam_id] = qs
        self.skipped[exam_id] = skipped
        self.coverage[exam_id] = cov
        for q in qs:
            for g in q['ngrams']:
                self.posting.setdefault(g, set()).add((exam_id, q['qid']))

    def ensure_all(self):
        for eid in bank_exam_ids(self.bank_root):
            self.ensure(eid)

    def match_question(self, exam_id, qid, ng, exclude_exam=None):
        """候选题指纹 ng 与索引里的题比，返回按相似度降序的 [{'exam_id','qid','sim','basis'}]（basis 是
        对手题面的抽取依据，M-C 据此识别低置信 OCR 命中）；相似度相同时按 exam_id/qid 排序，结果与
        posting 里 set 的哈希顺序无关（跨 PYTHONHASHSEED 稳定）。"""
        cand_counts = {}
        for g in ng:
            for key in self.posting.get(g, ()):
                if exclude_exam is not None and key[0] == exclude_exam:
                    continue
                if key == (exam_id, qid):
                    continue
                cand_counts[key] = cand_counts.get(key, 0) + 1
        results = []
        for (eid, oqid), _cnt in cand_counts.items():
            other = next((q for q in self.by_exam.get(eid, ()) if q['qid'] == oqid), None)
            if other is None:
                continue
            sim = containment(ng, other['ngrams'])
            if sim >= DUP_QUESTION_SIM:
                results.append({'exam_id': eid, 'qid': oqid, 'sim': round(sim, 4), 'basis': other.get('basis')})
        results.sort(key=lambda r: (-r['sim'], r['exam_id'], r['qid']))
        return results


def scan_duplicates(index, exam_id, questions, exclude_exam=None, fraction_reliable=True, total_questions=None):
    """候选卷（questions: [{'qid','ngrams','basis'}]) 与题库比对。

    一对一匹配（m6）：候选题与对手卷内的题按相似度降序贪心配对，候选题、对手题各只用一次——不这样做，
    “考生须知编号误切/OCR 碎片一题对多题”会把同一道对手题重复算进好几道候选题的匹配数，占比超过 100%
    （如 22/21）。已选定但因对手题被更高分候选题占用而放弃的配对计入 contested_matches，只作提示。

    低置信隔离（M-C）：题库把“回原页对照前不得采用”的 OCR 候选/含答案节标记为 fallback_low_confidence
    ——这类节常常整段混入往年对照例题，containment 对这种“一段夹私货”的文本几乎总能打出高分，是串题
    不是复用。任一侧（候选题或对手题）基于这类节的配对单列 low_confidence_pairs，不计入
    duplicate_registration/shared_or_reused_questions 的判定分子，避免“题库 OCR 串题被报成真复用”。

    分母（M-D）：total_questions 传入时按它算占比（用于覆盖率低的卷——分母该是卷内全部题数，不是
    只数得出题面的那几道，否则复用 1 题就能因为分母被压到 1 而算出 100%）；不传则退回 len(questions)。
    阈值判定用严格 > （m7，规格“大部分题相同”不含恰好一半）。"""
    q_basis = {q['qid']: q.get('basis') for q in questions}
    by_opp = {}   # exam_id -> [(sim, cqid, oqid, obasis), ...]
    for q in questions:
        for m in index.match_question(exam_id, q['qid'], q['ngrams'], exclude_exam=exclude_exam):
            by_opp.setdefault(m['exam_id'], []).append((m['sim'], q['qid'], m['qid'], m.get('basis')))
    total = total_questions if total_questions is not None else len(questions)
    against = []
    for opp, triples in by_opp.items():
        triples.sort(key=lambda t: (-t[0], t[1], t[2]))
        used_c, used_o, matched, contested = set(), set(), [], 0
        for sim, cqid, oqid, obasis in triples:
            if cqid in used_c:
                continue
            if oqid in used_o:
                contested += 1
                continue
            used_c.add(cqid)
            used_o.add(oqid)
            matched.append({'qid': cqid, 'against_qid': oqid, 'sim': sim,
                             'candidate_basis': q_basis.get(cqid), 'opponent_basis': obasis})
        low_conf = [p for p in matched if p['candidate_basis'] == 'fallback_low_confidence'
                    or p['opponent_basis'] == 'fallback_low_confidence']
        reliable = [p for p in matched if p not in low_conf]
        n_reliable = len(reliable)
        frac = n_reliable / total if total else 0.0
        entry = {'exam_id': opp, 'total_questions': total,
                  'pairs': sorted(reliable, key=lambda p: p['qid']),
                  'low_confidence_pairs': sorted(low_conf, key=lambda p: p['qid'])}
        if n_reliable:
            entry['matched_questions'] = n_reliable
            entry['fraction'] = round(frac, 4)
            if fraction_reliable:
                entry['kind'] = 'duplicate_registration' if frac > DUP_EXAM_FRACTION else 'shared_or_reused_questions'
            else:
                entry['kind'] = 'shared_or_reused_questions'  # 切题失败/覆盖率过低时不敢按占比判“重复登记”
            entry['fraction_reliable'] = fraction_reliable
        else:
            entry['matched_questions'] = 0
            entry['fraction'] = 0.0
            entry['kind'] = 'needs_verification_low_confidence'
            entry['fraction_reliable'] = False
        if contested:
            entry['contested_matches'] = contested
        against.append(entry)
    against.sort(key=lambda a: (-a['fraction'], -len(a['low_confidence_pairs']), a['exam_id']))
    return against


# ---------------------------------------------------------------- 改号链（占用卷本身是否也要改号、先后顺序、重定向表）
def _reliable_dup(against, other_id=None):
    """dup_against 列表里“可靠的 duplicate_registration”——kind 对且 fraction_reliable 为真（M-D：覆盖率
    过低/切题失败时不认，不能把这类误判带进改号链）；other_id 给出时只找与该卷的那一条。"""
    for a in against:
        if a['kind'] != 'duplicate_registration' or not a.get('fraction_reliable'):
            continue
        if other_id is not None and a['exam_id'] != other_id:
            continue
        return a
    return None


def build_rename_chain(dup_against_candidate, want_id, resolver, own_id=None, max_depth=MAX_RENAME_CHAIN_DEPTH):
    """want_id 已被占用时调用。resolver(exam_id) 返回该已登记卷自己的 check_one 结果（resolve_chain=False，
    避免互相递归）。own_id 是本卷当前的登记号（exam-id/exam-dir 复核已登记卷时才有；--files 新卷为 None）。
    返回 dict：kind + note + rename_plan（执行顺序，最先发生的排最前）+ redirects + reused_ids。
    候选本身与占用卷已判定 duplicate_registration 时不构造改号链，直接说明“已登记，不要再登记”——
    own_id 存在时（exam-id/exam-dir 复核已登记卷本身，m11），给出把 own_id 并入/撤销、改用 want_id
    的 plan/redirect；own_id 为空时（--files 新卷）措辞改为“不应再注册新卷号”。

    retire 方向（M-A）：占用卷 X 与另一卷 Y 判定重复登记，不能只看“判定重复”就把 X 并入 Y——必须
    X 自己 id_mismatch（X 的登记号本身与证据不符）且 Y 自身登记号正确（Y 没有 id_mismatch、且有
    可用的届别证据）才 retire X into Y；否则（X 本身登记号正确、或 Y 同样有问题）终止为
    blocked_conflict，不给 redirects——把“正确卷号被并入错号”的方向性错误挡在这里。"""
    direct = _reliable_dup(dup_against_candidate, want_id)
    if direct:
        if own_id and own_id != want_id:
            return {'kind': 'already_registered',
                    'rename_plan': [{'old': own_id, 'retire_into': want_id,
                                      'reason': f'与 {want_id} 判定为重复登记（题面匹配 '
                                                f'{direct["matched_questions"]}/{direct["total_questions"]} 题），'
                                                '应并入/撤销，不再单独占用卷号'}],
                    'redirects': [{'old': own_id, 'new': want_id, 'after_step': 1}], 'reused_ids': [],
                    'note': (f'{own_id} 与 {want_id} 判定为同一场考试（题面匹配 {direct["matched_questions"]}/'
                             f'{direct["total_questions"]} 题），应将 {own_id} 并入/撤销并改用 {want_id}，'
                             '不应两个卷号各自保留。')}
        return {'kind': 'already_registered', 'rename_plan': [], 'redirects': [], 'reused_ids': [],
                'note': (f'{want_id} 已登记为同一场考试（题面匹配 {direct["matched_questions"]}/'
                         f'{direct["total_questions"]} 题），不应再注册新卷号；如需登记请先核实与 '
                         f'{want_id} 是否确为同一场考试，而不是直接改号顶替它。')}

    chain = []           # [(occupant_id, occ_result, terminal_dict)]
    visited, cur = set(), want_id
    while cur not in visited:
        visited.add(cur)
        if len(chain) >= max_depth:
            return {'kind': 'chain_too_long', 'rename_plan': [], 'redirects': [], 'reused_ids': [],
                    'note': f'改号链超过 {max_depth} 层仍未收敛，未继续展开，需人工核查（占用链：{[c[0] for c in chain]}）。'}
        occ = resolver(cur)
        if occ is None:
            return {'kind': 'occupant_unreadable', 'rename_plan': [], 'redirects': [], 'reused_ids': [],
                    'note': f'{cur} 已被占用，但复核占用卷本身失败，需人工核查。'}
        if occ.get('retired'):
            rinfo = occ['retired']
            chain.append((cur, occ, {'terminal': 'conflict',
                                      'reason': f'{cur} 在 exams.csv 中已标记为撤销登记'
                                                f'（{rinfo.get("extract_status")}：{rinfo.get("notes")}），'
                                                '是否可以把该号让给别的考试需人工核实撤销原因，不代为判定。'}))
            break
        occ_dup_elsewhere = _reliable_dup([a for a in occ.get('duplicates', ()) if a['exam_id'] != cur])
        occ_sugg = occ.get('suggestion') or {}
        if occ_dup_elsewhere:
            target_id = occ_dup_elsewhere['exam_id']
            target_occ = resolver(target_id) if occ.get('id_mismatch') else None
            target_ok = bool(target_occ) and not target_occ.get('id_mismatch') and target_occ.get('cohort_year') is not None
            if occ.get('id_mismatch') and target_ok:
                chain.append((cur, occ, {'terminal': 'retire', 'into': target_id,
                                          'matched': occ_dup_elsewhere['matched_questions'],
                                          'total': occ_dup_elsewhere['total_questions']}))
                break
            if not occ.get('id_mismatch'):
                reason = (f'{cur} 自身届别证据与登记号一致（登记号本身没有问题），虽然与 {target_id} '
                          f'判定为重复登记（{occ_dup_elsewhere["matched_questions"]}/'
                          f'{occ_dup_elsewhere["total_questions"]} 题匹配），但按当前证据看应当改号的是 '
                          f'{target_id} 而不是 {cur}；若两者确为不同场次的考试（例如一份是高二卷），'
                          '卷号体系需人工核定，不建议自动把正确卷号并入另一张卷。')
            else:
                reason = (f'{cur} 自身登记号与证据不符，且与 {target_id} 判定为重复登记，但 {target_id} '
                          '自身届别证据也核实不了（同样可能登记号有误或证据不足），无法确定该把谁并入谁，'
                          '需人工核查。')
            chain.append((cur, occ, {'terminal': 'conflict', 'reason': reason}))
            break
        if occ.get('id_mismatch') and occ_sugg.get('suggested_id') and occ_sugg['suggested_id'] != cur:
            nxt = occ_sugg['suggested_id']
            if not occ_sugg.get('occupied'):
                chain.append((cur, occ, {'terminal': 'move', 'to': nxt}))
                break
            chain.append((cur, occ, {'terminal': None, 'to': nxt}))
            cur = nxt
            continue
        status_txt = ('自身届别证据与登记号一致' if occ.get('cohort_status') == 'OK' else
                      f'自身届别证据不足以核实（状态：{occ.get("cohort_status")}），不代表登记号一定正确')
        chain.append((cur, occ, {'terminal': 'conflict',
                                  'reason': f'{cur} {status_txt}，且未发现与其他卷可靠的重复登记，'
                                            '可能是同一卷号被两场不同考试各自认领的真实冲突，需人工判定。'}))
        break
    else:
        return {'kind': 'cycle', 'rename_plan': [], 'redirects': [], 'reused_ids': [],
                'note': f'改号链出现循环（回到 {cur}），需人工核查（占用链：{[c[0] for c in chain]}）。'}

    unresolved = chain[-1][2]['terminal'] == 'conflict'
    plan, redirects = [], []
    for occ_id, occ, term in reversed(chain):
        step_no = len(plan) + 1
        if term['terminal'] == 'retire':
            plan.append({'old': occ_id, 'retire_into': term['into'],
                          'reason': f'与 {term["into"]} 判定为重复登记（{term["matched"]}/{term["total"]} 题匹配，'
                                     f'{occ_id} 自身登记号也确实与证据不符），应并入/撤销，不再单独占用卷号'})
            redirects.append({'old': occ_id, 'new': term['into'], 'after_step': step_no})
        elif term['terminal'] == 'move':
            plan.append({'old': occ_id, 'new': term['to'], 'reason': '自身届别证据与登记号不符，先改到未被占用的正确卷号'})
            redirects.append({'old': occ_id, 'new': term['to'], 'after_step': step_no})
        elif term['terminal'] == 'conflict':
            plan.append({'old': occ_id, 'new': None, 'reason': term['reason']})
        else:
            plan.append({'old': occ_id, 'new': term['to'], 'reason': '自身届别证据与登记号不符，且目标号也被占用，需先腾出目标号'})
            redirects.append({'old': occ_id, 'new': term['to'], 'after_step': step_no})

    if unresolved:
        # m1：redirects 一律置空——note 说“不给出重定向表”，实际却可能因为冲突点之前还有 retire/move
        # 步骤而非空；冲突点在 rename_plan 里是第一步（reversed(chain) 决定了执行顺序，最先发生的排
        # 最前，冲突发生在链条最深处、最先被展开，因此排在 plan[0]），不是“最后一步”。
        note = ('占用链存在无法机械判定的真实冲突（见 rename_plan 第一步），改号顺序只给到冲突点为止，'
                '冲突解决前不建议把本卷改到 ' + want_id + '，也不给出重定向表。')
        return {'kind': 'blocked_conflict', 'rename_plan': plan, 'redirects': [], 'reused_ids': [], 'note': note}

    final_step_no = len(plan) + 1
    if own_id and own_id != want_id:
        plan.append({'old': own_id, 'new': want_id,
                      'reason': f'上述步骤腾出 {want_id} 后，本卷（现卷号 {own_id}）改为该号'})
        redirects.append({'old': own_id, 'new': want_id, 'after_step': final_step_no})
    else:
        plan.append({'old': None, 'new': want_id, 'reason': f'上述步骤腾出 {want_id} 后，本卷改为该号'})

    old_ids = {r['old'] for r in redirects}
    new_ids = {r['new'] for r in redirects}
    # M-B/M-L：某卷号先作为“旧号”被重定向出去，又被后面的步骤重新指派给另一场考试——同一卷号在不同
    # 执行阶段指向不同的考试。own_id 为空时（--files 新卷），最后一步“本卷 → want_id”不是一条
    # redirects（没有旧号可写），但 want_id 在此之前一定已作为某一步的 old 被重定向走，同样要提醒
    # （M-L：并到 new_ids 里再求交集，而不是只看 redirects 本身的 old∩new）。
    reused_ids = sorted(old_ids & (new_ids | {want_id}))
    steps_txt = '；'.join(
        (f'{i + 1}. {s["old"]}→{s.get("retire_into") or s.get("new")}（{s["reason"]}）' if s['old'] else
         f'{i + 1}. 本卷 → {s["new"]}（{s["reason"]}）')
        for i, s in enumerate(plan))
    note = f'{want_id} 已被占用，改号顺序建议：{steps_txt}'
    if reused_ids:
        note += ('；注意：' + '、'.join(reused_ids) + ' 在本计划中既作为“旧号”被重定向出去，又被后续步骤'
                 '重新指派给另一场考试——同一卷号在执行完不同步骤后指向不同的考试，引用它的旧材料要按'
                 'rename_plan 的步骤顺序（对照 redirects 的 after_step）逐条改，不能把 redirects 当一次性'
                 '替换表来批量替换。')
    return {'kind': 'chain', 'rename_plan': plan, 'redirects': redirects, 'reused_ids': reused_ids, 'note': note}


# ---------------------------------------------------------------- 单卷检查主流程
def check_one(exam_id_hint, claimed_id, bank_root, raw_root, exams_rows, exam_files_rows,
              index, region_name=None, stage_name=None, md_dir=None, files=None,
              exclude_self=True, resolve_chain=True):
    """统一入口：exam_id_hint（题库已登记卷号，可为 None）/ md_dir（--exam-dir）/ files（--files）。
    返回单卷结果 dict；不做任何写入。resolve_chain=False 时不构造改号链（占用卷自身复核用，避免
    互相递归）。"""
    issues = []
    claim = claimed_id or exam_id_hint
    claim_parsed = None
    if claim:
        try:
            claim_parsed = parse_exam_id(claim)
        except ExamIdFormatError as e:
            issues.append(f'claimed_id 格式问题（仅作参考，不影响推算）：{e}')

    if region_name is None and claim_parsed:
        region_name = claim_parsed['region_name']
    if stage_name is None and claim_parsed:
        stage_name = claim_parsed['stage_name']
    if stage_name is None:
        raise InputError('无法确定阶段（期中/期末/一模/二模/高考）：请给 --exam-id、--claimed-id 或 --stage')

    # --exam-dir 位于 bank/questions/ 下时，目录名即候选自身的卷号：查重与占用检查都要排除它，
    # 否则会把候选和它自己的数据比出“重复登记”“建议卷号已被占用”
    self_id = None
    if md_dir is not None:
        try:
            rel = Path(md_dir).resolve().relative_to((bank_root / 'questions').resolve())
            if len(rel.parts) == 1:
                self_id = rel.parts[0]
        except (ValueError, OSError):
            pass

    evidences = []

    # Tier A：原件文字层（全文；卷首窗口在 extract_year_signals 内部截取）
    raw_files = []
    if exam_id_hint:
        raw_files = locate_raw_files_by_csv(exam_id_hint, exam_files_rows, raw_root)
    if not raw_files and files:
        raw_files = [{'path': Path(f).resolve(), 'rel_path': str(f), 'role': '给定文件'} for f in files]

    md_full_texts = []  # 原始 MD 全文（供“### 来源”回退定位原件、身份小节抽取），不是抽出的题面
    md_full_paths = []  # 与 md_full_texts 一一对应（只在读取成功时同步 append，供 m11 的 SHA 清单用）
    if exam_id_hint:
        for p in sorted((bank_root / 'questions' / exam_id_hint).glob(f'{exam_id_hint}-Q*.md'))[:5]:
            try:
                md_full_texts.append(p.read_text(encoding='utf-8'))
                md_full_paths.append(p)
            except OSError:
                pass
    elif md_dir:
        for p in sorted(Path(md_dir).glob('*.md')):
            if p.name.upper() == 'README.MD':
                continue
            try:
                md_full_texts.append(p.read_text(encoding='utf-8'))
                md_full_paths.append(p)
            except OSError:
                pass
    if not raw_files and md_full_texts:
        raw_files = locate_raw_files_via_md_refs(md_full_texts, raw_root)

    raw_file_reports = []
    for rf in raw_files:
        try:
            text, engine = extract_file_text(rf['path'], max_pages=HEADER_RAW_MAX_PAGES, max_chars=HEADER_RAW_MAX_CHARS)
        except RawOpenError as e:
            if rf['role'] == '给定文件':  # --files 直接给的文件本身打不开/格式不对，是输入错误，不是“需本地看图”
                raise InputError(str(e))
            raw_file_reports.append({'path': str(rf['path']), 'role': rf['role'], 'engine': None,
                                      'has_text_layer': False, 'chars': 0, 'open_error': str(e),
                                      'sha256': _input_sha(rf['path'])})
            continue
        has_text = _text_usable(text)  # M-J：不只看长度，乱码/轮廓字文字层可读字符占比过低也算无文字层
        raw_file_reports.append({'path': str(rf['path']), 'role': rf['role'], 'engine': engine,
                                  'has_text_layer': has_text, 'chars': len(text.strip()),
                                  'readable_ratio': round(_readable_ratio(text), 4),
                                  'sha256': _input_sha(rf['path'])})
        if has_text:
            evidences.extend(extract_year_signals(text, str(rf['path']), 'A', stage_name, cut_at_qnum=True))

    # Tier B：题库 README 前 HEADER_WINDOW 字（m7：不是全文，extract_year_signals 默认按这个窗口截，
    # README 本身很短，一般不会漏；更长的另见下面的卷首说明文件，整份读）+ 逐题 MD 的“身份…”小节
    # （不读题面）——exam_id_hint（已登记卷复核）与 md_dir（--exam-dir，刚产出的逐题 MD，规格点名的
    # 主用法之一）走同一套读法，不再是前者独有（M-F：此前 --exam-dir 分支不读 README，同一份内容按
    # --exam-id 跑能核实届别、按 --exam-dir 跑却 NEEDS_LOCAL）。
    readme_path = None
    if exam_id_hint:
        readme_path = bank_root / 'questions' / exam_id_hint / 'README.md'
    elif md_dir:
        readme_path = Path(md_dir) / 'README.md'
    readme_info = None
    if readme_path and readme_path.is_file():
        try:
            rtext = readme_path.read_text(encoding='utf-8')
            evidences.extend(extract_year_signals(rtext, str(readme_path), 'B', stage_name))
            readme_info = {'path': str(readme_path), 'sha256': _input_sha(readme_path)}
        except OSError:
            pass

    # m3：卷首说明文件（如 00_exam_front_matter.md）——独立顶级标题，identity_section_text 找不到，
    # 单独按文件名识别、整份当 B 层证据（同一目录：exam_id_hint 用题库目录，md_dir 用给定目录）
    fm_dir = (bank_root / 'questions' / exam_id_hint) if exam_id_hint else (Path(md_dir) if md_dir else None)
    front_matter_path = _find_front_matter(fm_dir)
    front_matter_info = None
    if front_matter_path:
        try:
            fmtext = front_matter_path.read_text(encoding='utf-8')
            evidences.extend(extract_year_signals(fmtext, str(front_matter_path), 'B', stage_name))
            front_matter_info = {'path': str(front_matter_path), 'sha256': _input_sha(front_matter_path)}
        except OSError:
            pass
    md_sources = []
    if exam_id_hint or md_dir:
        src_label = exam_id_hint or Path(md_dir).name
        for p, t in zip(md_full_paths, md_full_texts):
            md_sources.append({'path': str(p), 'sha256': _input_sha(p)})
            idt = identity_section_text(t)
            if idt:
                evidences.extend(extract_year_signals(idt, f'{src_label} 身份小节', 'B', stage_name))

    # Tier C：exams.csv
    exam_row = None
    if exam_id_hint:
        exam_row = next((r for r in exams_rows if r.get('exam_id') == exam_id_hint), None)
        if exam_row:
            sy = exam_row.get('school_year') or ''
            evidences.extend(extract_year_signals(sy, 'exams.csv school_year', 'C', stage_name))
            y = exam_row.get('year') or ''
            if re.fullmatch(r'20\d{2}', y.strip()):
                evidences.append({'tier': 'C', 'source': 'exams.csv year', 'kind': 'bare_year',
                                   'raw': y, 'cohort_year': None, 'grade2': False, 'snippet': y})

    # Tier D：目录名/文件名（旁证）
    name_bits = []
    if exam_id_hint:
        name_bits.append(exam_id_hint)
    for rf in raw_files:
        name_bits.append(rf.get('rel_path', ''))
    for bit in name_bits:
        evidences.extend(extract_year_signals(bit, f'路径/文件名：{bit}', 'D', stage_name))

    cohort = infer_cohort(evidences)
    no_raw_text = not any(r['has_text_layer'] for r in raw_file_reports)
    no_bank_text = readme_info is None and front_matter_info is None and not md_sources

    weak_hint_year = None
    if cohort['status'] == 'WEAK_ONLY' and no_raw_text:
        # M-K：只有 C 层（exams.csv，已知会错）证据、且原件没有任何可用文字层时，不能靠它单独定届别——
        # 规格 A 原文“只有扫描页无文字层时标‘需本地看图’，不猜”管的是这一层，不止 D 层。年份只作
        # weak_hint 参考列出，不升格为 WEAK_ONLY、不生成建议号（cohort_year 置空后 suggestion/chain
        # 会自动跳过，见下文）。
        weak_hint_year = cohort['cohort_year']
        cohort = {'cohort_year': None, 'status': 'NEEDS_LOCAL', 'grade2': cohort.get('grade2', False), 'outliers': []}

    if cohort['cohort_year'] is None:
        if cohort['status'] == 'CONFLICT':
            issues.append('届别证据冲突（同层或 A/B 两层给出不同结果），列出全部证据，不代为裁决')
        elif weak_hint_year is not None:
            issues.append(f'原件无可用文字层，仅 exams.csv（已知会错）显示届别可能为 {weak_hint_year}，'
                           '需本地看图核实届别，不据此生成建议卷号（M-K）')
        else:
            cohort['status'] = 'NEEDS_LOCAL'
            if no_raw_text and (not exam_id_hint or no_bank_text):
                issues.append('原件无文字层且题库无可查文字证据，需本地看图核实届别')
            else:
                issues.append('原件与题库均未给出可用的届别信号（无日期/学年写法），需本地核实')
    elif cohort['status'] == 'WEAK_ONLY':
        issues.append('仅有弱证据（exams.csv，已知会错）支持届别，原件/题库文字层未给出可用信号')
    if cohort['cohort_year'] is not None and cohort['status'] == 'OK':
        # m3：A 层裁决即采信、不与 B 层比较取 CONFLICT，是设计如此（同一份卷子的原件与题库整理稿
        # 不是两个地位相等的独立信源）；但 B 层若确有不同意见，至少写一条 issue 供复核，不是完全不提
        b_ev = [e for e in evidences if e['tier'] == 'B' and e.get('cohort_year') is not None]
        if b_ev:
            b_cohort, b_status, _ = _resolve_tier(b_ev)
            if b_status.startswith('OK') and b_cohort != cohort['cohort_year']:
                issues.append(f'B 层（题库整理稿 README/身份小节）另有证据显示届别为 {b_cohort}，与已采信的 '
                               f'A 层（原件）结论 {cohort["cohort_year"]} 不一致；以 A 层为准，仅供参考核实')
    if cohort.get('grade2'):
        issues.append('证据窗口内出现“高二”且未见“高三”，届别已按学年末年+1 处理，请复核是否确为高二卷')
    if cohort.get('outliers'):
        issues.append(f'同层多数证据一致，另有 {cohort["outliers"]} 个别不同（很可能是题干引用的无关历史日期，'
                       f'已按多数裁决，未采信；证据详情见 evidence）')

    # 撤销登记（exams.csv extract_status=retired_*）
    retired = None
    if exam_row and str(exam_row.get('extract_status') or '').startswith('retired'):
        retired = {'extract_status': exam_row.get('extract_status'), 'notes': exam_row.get('notes')}
        issues.append(f'该卷号在 exams.csv 中标记为已撤销登记（{retired["extract_status"]}）：{retired["notes"]}')

    # 与登记号（或 claimed）比对
    id_mismatch = None
    if cohort['cohort_year'] is not None and claim_parsed and claim_parsed['year'] != cohort['cohort_year']:
        id_mismatch = {'registered_year': claim_parsed['year'], 'evidence_cohort_year': cohort['cohort_year']}
        issues.append(f'登记号年份（{claim_parsed["year"]}）与证据推算届别（{cohort["cohort_year"]}）不符')

    # 建议卷号 + 占用检查（--exam-dir 落在 bank/questions/ 下时，占用者是自己不算占用）
    suggestion = None
    if cohort['cohort_year'] is not None and region_name and stage_name:
        try:
            suggested_id = build_exam_id(cohort['cohort_year'], region_name, stage_name)
        except InputError as e:
            suggested_id = None
            issues.append(str(e))
        if suggested_id:
            self_ids = {x for x in (exam_id_hint, self_id) if x}
            occupied_dir = (bank_root / 'questions' / suggested_id).is_dir()
            occupied_csv = any(r.get('exam_id') == suggested_id for r in exams_rows)
            occupant = None
            if (occupied_dir or occupied_csv) and suggested_id not in self_ids:
                occupant = {'exam_id': suggested_id, 'occupied': True}
                issues.append(f'建议卷号 {suggested_id} 已被占用')
            suggestion = {'suggested_id': suggested_id, 'occupied': bool(occupant), 'occupant': occupant}

    # 重复登记 / 复用扫描
    dup_against = []
    dup_skipped = []
    fp_coverage = None
    if exam_id_hint:
        index.ensure(exam_id_hint)
        qs = index.by_exam.get(exam_id_hint, [])
        dup_skipped = index.skipped.get(exam_id_hint, [])
        fp_coverage = index.coverage.get(exam_id_hint)
        cov_ok = not (fp_coverage and fp_coverage['total'] and fp_coverage['ratio'] < MIN_FINGERPRINT_COVERAGE)
        dup_against = scan_duplicates(index, exam_id_hint, qs, exclude_exam=exam_id_hint if exclude_self else None,
                                       fraction_reliable=cov_ok,
                                       total_questions=fp_coverage['total'] if fp_coverage else None)
    elif md_dir:
        qs, dup_skipped, fp_coverage = load_exam_questions_from_dir(md_dir, index.T)
        pseudo_id = self_id or claim or '__NEW__'
        cov_ok = not (fp_coverage and fp_coverage['total'] and fp_coverage['ratio'] < MIN_FINGERPRINT_COVERAGE)
        dup_against = scan_duplicates(index, pseudo_id, qs, exclude_exam=self_id, fraction_reliable=cov_ok,
                                       total_questions=fp_coverage['total'] if fp_coverage else None)
    elif files:
        pseudo_id = claim or '__NEW__'
        dup_against, files_reliable = scan_files_duplicates(index, pseudo_id, raw_files)
        if not files_reliable:
            if any(r['has_text_layer'] for r in raw_file_reports):
                # M-I：至少一份文件有可用文字层，但切题都不可靠（中途漏题号/块长度异常）
                issues.append('原件题号切分失败或不可靠（可能中途漏题号、块长度异常），只能整卷粗略比对：'
                               '下面的 duplicates 一律降级为 shared_or_reused_questions，不据此判定 '
                               'duplicate_registration，需人工核实占比')
            else:
                # M-J：没有一份文件有可用文字层（含“有字符无可读内容”的乱码文字层），没有任何题可比对，
                # 不是“已整卷粗略比对”——duplicates 为空不代表查过没查到，需明说未执行
                issues.append('原件均无可用文字层（或乱码文字层无法识别为中文），未能对原件做任何查重，'
                               '重复登记/复用需本地核实')

    if fp_coverage and fp_coverage['total'] and fp_coverage['ratio'] < MIN_FINGERPRINT_COVERAGE:
        issues.append(f'题面指纹覆盖率偏低（{fp_coverage["found"]}/{fp_coverage["total"]}='
                       f'{fp_coverage["ratio"]}，低于 {MIN_FINGERPRINT_COVERAGE}）：部分题抽不出题面，分母改用'
                       f'覆盖率的 total（M-D），查重结果仍可能漏检，见 duplicates_skipped_no_stem')

    for a in dup_against:
        if a['kind'] == 'needs_verification_low_confidence':
            issues.append(f'疑似串题/低置信匹配：{a["exam_id"]}（{len(a["low_confidence_pairs"])} 处命中全部'
                           '来自题库标注“回原页对照前不得采用”的 OCR 候选/含答案等低置信小节，可能是该小节'
                           '混入了往年对照例题，不计入正式的复用/重复登记判定，需回原页核实，见 M-C）')
        else:
            extra = (f'；另有 {len(a["low_confidence_pairs"])} 处低置信命中未计入（见 M-C）'
                     if a.get('low_confidence_pairs') else '')
            issues.append(f'{a["kind"]}：与 {a["exam_id"]} 匹配 {a["matched_questions"]}/{a["total_questions"]} 题'
                           f'（占比 {a["fraction"]}）' + extra)
        if a.get('contested_matches'):
            issues.append(f'与 {a["exam_id"]} 比对时有 {a["contested_matches"]} 处候选题命中了已被更高分候选题'
                           '占用的同一道对手题，已按一对一贪心匹配只取分数更高的那对，未重复计数（m6）')

    # m12：建议号未被占用、但候选本身与某张已有卷可靠重复时，不能把建议号表述成“可用的新登记”
    if suggestion is not None:
        rd = _reliable_dup(dup_against)
        if rd:
            suggestion['already_registered_as'] = rd['exam_id']

    # 改号链：建议卷号被占用时，递归复核占用卷，给出先后顺序与重定向表
    chain = None
    own_id = exam_id_hint or self_id
    if resolve_chain and suggestion and suggestion.get('occupied'):
        def _resolver(occ_id, _bank=bank_root, _raw=raw_root, _er=exams_rows, _ef=exam_files_rows, _ix=index):
            try:
                return check_one(occ_id, None, _bank, _raw, _er, _ef, _ix, exclude_self=True, resolve_chain=False)
            except Exception:
                return None
        chain = build_rename_chain(dup_against, suggestion['suggested_id'], _resolver, own_id=own_id)
        issues.append(chain['note'])

    return {
        'exam_id': exam_id_hint, 'claimed_id': claim, 'region': region_name, 'stage': stage_name,
        'self_id': self_id, 'evidence': evidences, 'raw_files': raw_file_reports,
        'readme': readme_info, 'front_matter': front_matter_info, 'md_sources': md_sources,
        'cohort_year': cohort['cohort_year'], 'cohort_status': cohort['status'], 'grade2': cohort['grade2'],
        'cohort_outliers': cohort.get('outliers', []), 'cohort_weak_hint': weak_hint_year,
        'exams_csv_row': {k: exam_row.get(k) for k in ('year', 'school_year', 'region', 'stage')} if exam_row else None,
        'retired': retired, 'id_mismatch': id_mismatch, 'suggestion': suggestion, 'chain': chain,
        'chain_note': chain['note'] if chain else None,
        'duplicates': dup_against, 'duplicates_skipped_no_stem': dup_skipped,
        'fingerprint_coverage': fp_coverage, 'issues': issues,
    }


Q_FILE_RX = re.compile(r'-Q\d+\.md$', re.IGNORECASE)  # m4：只认逐题 MD（{exam_id}-Q{n}.md），排除
                              # README/00_exam_front_matter.md/complete_candidate.md 等工程文件


def load_exam_questions_from_dir(md_dir, T=None):
    out, skipped = [], []
    files = [p for p in sorted(Path(md_dir).glob('*.md')) if Q_FILE_RX.search(p.name)]
    for p in files:
        try:
            raw = p.read_text(encoding='utf-8')
        except OSError:
            continue
        stem, basis = extract_stem_from_md(raw, T)
        ng = fingerprint_stem(stem) if stem else None
        if not ng:
            skipped.append(p.stem)
            continue
        out.append({'qid': p.stem, 'text': stem, 'ngrams': ng, 'basis': basis})
    return out, skipped, _coverage_summary(len(files), out)


def split_questions_raw(text):
    """新卷原件切题：找“N．”起始且题号单调递增（步长1，起于1或前若干题内出现1）的切点；切不出则整卷。
    误配的数字（如年份“2025.”）几乎不可能恰好按 1,2,3… 单调递增排列，靠这一校验过滤，不用担心题号
    后紧跟数字会被切错位置。"""
    matches = list(QNUM_SPLIT_RX.finditer(text))
    picked = []
    expect = 1
    for m in matches:
        n = int(m.group(1))
        if n == expect:
            picked.append((n, m.start()))
            expect += 1
        elif n == 1 and not picked:
            picked = [(1, m.start())]
            expect = 2
    if len(picked) < 3:
        return [('整卷', text)], False
    out = []
    for i, (n, start) in enumerate(picked):
        end = picked[i + 1][1] if i + 1 < len(picked) else len(text)
        out.append((str(n), text[start:end]))
    return out, True


def _split_is_reliable(chunks, ok, text):
    """M-I：split_questions_raw 只要单调递增到 >=3 步就算 split_ok=True，但某个题号一旦没被正则识别到
    （漏句点、OCR 把题号并到上一行、格式换了），expect 卡住，后面所有题号都不会再被“采纳”进 picked，
    最后一个已采纳的块会把剩下的题全部吞进去——块数远小于题数，但仍报 split_ok=True。信号：全文里
    出现过的题号（不要求单调，只看正则命中过的最大值）比实际切出的块数多得多，说明还有题号没被采纳
    进任何一块。不用“块长度远超中位数”这条信号——正卷最后一道大题（材料分析/论述）本来就比选择题
    长好几倍，会把完全正常的切题误判为不可靠（见 8g 回归：某真实原件最后一块 1316 字、中位数仅
    328 字，仍是 20/20 的正确切法）。任一出现即判不可靠，调用方按“整卷”同等降级（不参与
    duplicate_registration 判定），真实原件的复现见审查 r3 probe_split_counts_r3.log（6 份
    split_ok=True 但块数不到题库题数一半，其中 5 份能被本条规则识别；BJ-2024-FT-YIMO 全文本身
    就只出现了 3 个题号，文本内部没有任何信号可判，见 known_limits）与 probe_poor_split_false_dup_r3.py
    （20 题漏切 1 题号，2/3 误判 duplicate_registration）。"""
    if not ok or len(chunks) < 3:
        return False
    all_nums = [int(m.group(1)) for m in QNUM_SPLIT_RX.finditer(text)]
    return not (all_nums and max(all_nums) - len(chunks) > SPLIT_MAX_MISSING_QNUM)


def split_and_fingerprint_one(raw_file):
    """单份原件切题+指纹（M-H：按文件分别算，不与其他文件的块合并成一个分母）；读全文（不受
    extract_file_text 内部页数/字数上限以外的额外截断），届别推算仍只看卷首窗口，两者互不影响。
    返回 (questions, reliable)：reliable 已经过 M-I 的切题合理性校验，文字不可用（无文字层/乱码，
    M-J）或打不开时返回 ([], False)。"""
    try:
        text, _engine = extract_file_text(raw_file['path'])
    except RawOpenError:
        return [], False
    text = _normalize_raw(text)
    if not _text_usable(text):
        return [], False
    chunks, ok = split_questions_raw(text)
    reliable = _split_is_reliable(chunks, ok, text)
    out = []
    for qno, chunk in chunks:
        ng = fingerprint_stem(chunk)
        if ng:
            out.append({'qid': f'{Path(raw_file["path"]).stem}-{qno}', 'text': chunk, 'ngrams': ng, 'basis': 'raw_file'})
    return out, reliable


def _merge_file_dup_entries(per_file_entries):
    """M-H：按对手卷号合并各文件独立算出的比对结果，同一对手取“最强”的一份（fraction_reliable 优先，
    其次 fraction，再次 matched_questions）——不同文件各自的分子分母互不影响，同一份原件给两次、或
    另给同 SHA 副本时，两次算出的结果相同，取最强的一份等价于只算一次，天然不受“文件越多分母越大”
    影响。"""
    best = {}
    for entries in per_file_entries:
        for e in entries:
            key = (e['fraction_reliable'], e['fraction'], e['matched_questions'])
            cur = best.get(e['exam_id'])
            if cur is None or key > (cur['fraction_reliable'], cur['fraction'], cur['matched_questions']):
                best[e['exam_id']] = e
    return sorted(best.values(), key=lambda a: (-a['fraction'], -len(a['low_confidence_pairs']), a['exam_id']))


def scan_files_duplicates(index, pseudo_id, raw_files):
    """--files 新卷查重的入口：逐个文件独立切题、独立比对（M-H），再按对手卷合并取最强的一份。返回
    (dup_against, any_reliable)：any_reliable 为假时（全部文件切题都不可靠、或没有一份能抽出文字）
    调用方在 issues 里说明查重未能可靠执行。"""
    per_file = []
    any_reliable = False
    for rf in raw_files:
        qs, reliable = split_and_fingerprint_one(rf)
        any_reliable = any_reliable or reliable
        if not qs:
            continue
        per_file.append(scan_duplicates(index, pseudo_id, qs, exclude_exam=None,
                                         fraction_reliable=reliable, total_questions=len(qs)))
    return _merge_file_dup_entries(per_file), any_reliable


# ---------------------------------------------------------------- 报告
def _input_sha(p):
    try:
        return sha256_file(Path(p)) if Path(p).is_file() else None
    except OSError:
        return None


def build_report(mode, args, items, extra=None, prof=None):
    inputs = {
        'bank': str(args.bank), 'raw_root': str(args.raw_root), 'profile': args.profile,
        'exams_csv_sha256': _input_sha(args.bank / 'indexes' / 'exams.csv'),
        'exam_files_csv_sha256': _input_sha(args.bank / 'indexes' / 'exam_files.csv'),
    }
    if args.profile:
        inputs['profile_sha256'] = _input_sha(args.profile)  # m11：profile 本身也是输入，之前只有路径字符串
    if prof:
        inputs['profile_book_id'] = prof.get('book_id')
    files_arg = getattr(args, 'files', None)
    if files_arg:
        inputs['files_sha256'] = {f: _input_sha(f) for f in files_arg}
    exam_dir_arg = getattr(args, 'exam_dir', None)
    if exam_dir_arg:
        inputs['exam_dir'] = str(exam_dir_arg)
    rep = {
        'tool': TOOL, 'version': VERSION, 'mode': mode, 'generated_at': now_iso(),
        'thresholds': {'ngram_n': NGRAM_N, 'dup_question_sim': DUP_QUESTION_SIM,
                        'dup_exam_fraction': DUP_EXAM_FRACTION, 'min_text_len': MIN_TEXT_LEN,
                        'min_stem_len': MIN_STEM_LEN, 'header_window': HEADER_WINDOW,
                        'min_fingerprint_coverage': MIN_FINGERPRINT_COVERAGE},
        'inputs': inputs, 'items': items,
    }
    if extra:
        rep.update(extra)
    return rep


def _extra_protected_roots(args):
    """云端补充守卫：guard_write 只保护调用方 --profile 里登记的根，不传 --profile（或传的 profile
    没登记仓库根）时题库/书稿/原材料一律放行——这里再加一层，REPO_ROOT/bank/raw_root 一律按受保护根
    检查，只放行系统临时目录与 …/协作/候选/<谁>/<批次>/构建/ 之下（复用 dl.WRITE_ALLOW_RX 同一条
    正则，候选目录下的正常写出不受影响）。不再把“--files/--exam-dir 输入所在目录”也当受保护根
    （m8：那样会把候选目录自己的 构建/ 或系统临时目录里的 synth/ 子目录当成一个独立的、要求自己
    再嵌套一层“构建/”的根，导致本来允许的位置被误拒——防止输出覆盖输入本身，靠 write_report 把
    真实输入路径传给 dl.guard_write 的 inputs= 处理，不靠把目录整体划为受保护根）。"""
    roots = {REPO_ROOT}
    for p in (getattr(args, 'bank', None), getattr(args, 'raw_root', None)):
        if p:
            try:
                roots.add(Path(p).resolve())
            except OSError:
                pass
    return roots


def _extra_guard_check(out_path, roots):
    o = Path(out_path).resolve()
    allow = re.compile(dl.WRITE_ALLOW_RX)
    for r in roots:
        try:
            rel = o.relative_to(r)
        except ValueError:
            continue
        if not allow.search('/' + str(rel.parent) + '/'):
            raise dl.GuardError(f'落在受保护目录 {r} 内（云端补充守卫；只允许 …/协作/候选/<谁>/<批次>/构建/ 之下或系统临时目录）')


def write_report(path, prof, rep, extra_roots=(), input_paths=()):
    out = dl.guard_write(Path(path), prof, inputs=input_paths, kind='.json')
    _extra_guard_check(out, set(extra_roots) | {REPO_ROOT})
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding='utf-8')
    return out


# ---------------------------------------------------------------- CLI
def _load_profile_arg(name_or_path):
    """--profile 是用户输入，找不到/解析不了是输入错误（退出2），不是内部错误（m9：修复前 load_profile
    抛的 FileNotFoundError 等会被 main() 的兜底 except Exception 当成“内部错误”）。"""
    if not name_or_path:
        return None
    try:
        return load_profile(name_or_path)
    except InputError:
        raise
    except Exception as e:
        raise InputError(f'--profile 无法加载（{name_or_path}）：{e}')


def _default_bank_raw(prof, bank_arg, raw_root_arg):
    root = REPO_ROOT
    if prof:
        try:
            root = Path(prof['paths']['root']).expanduser()
        except KeyError:
            pass
    bank = Path(bank_arg) if bank_arg else None
    if bank is None and prof:
        rel = ((prof.get('sources') or {}).get('bank') or {}).get('root')
        if rel:
            bank = (root / rel) if not Path(rel).is_absolute() else Path(rel)
    if bank is None:
        bank = root / 'DeepSeek_政治题库资料库_20260918'
    raw_root = Path(raw_root_arg) if raw_root_arg else (root / '00_共同资料' / '原材料')
    return bank.resolve(), raw_root.resolve()


def cmd_check(args):
    prof = _load_profile_arg(args.profile)
    args.bank, args.raw_root = _default_bank_raw(prof, args.bank, args.raw_root)
    if not args.bank.is_dir():
        raise InputError(f'题库根不存在：{args.bank}')
    if not args.raw_root.is_dir():
        raise InputError(f'原材料根不存在：{args.raw_root}（m9：不再静默降级为 NEEDS_LOCAL）')
    modes = sum(bool(x) for x in (args.exam_id, args.files, args.exam_dir))
    if modes != 1:
        raise InputError('check 需要且只能给一种输入：--exam-id / --files / --exam-dir')

    input_paths = []  # 实际读取的输入文件/目录，传给 write_report 的 guard_write(inputs=) 防覆盖输入本身（m8）
    if args.exam_id:
        parse_exam_id(args.exam_id)  # 格式先校验，错误直接抛 ExamIdFormatError（退出码 2）
    elif args.files:
        if args.region is not None and args.region not in REGION:
            raise InputError(f'--region 不在 block_index.REGION 表中：{args.region}')
        if args.stage is not None and args.stage not in STAGE and args.stage != '高考':
            raise InputError(f'--stage 不在 block_index.STAGE 表中：{args.stage}')
        for f in args.files:
            p = Path(f)
            if not p.is_file():
                raise InputError(f'文件不存在：{f}')
            if p.suffix.lower() not in ('.pdf', '.docx'):
                raise InputError(f'不支持的文件格式（只认 .pdf/.docx）：{f}')
            input_paths.append(p)
    else:
        d = Path(args.exam_dir)
        if not d.is_dir():
            raise InputError(f'目录不存在：{d}')
        if not any(q.name.upper() != 'README.MD' for q in d.glob('*.md')):
            raise InputError(f'--exam-dir 目录下没有任何逐题 MD（只有/没有 README.md 也算）：{d}')  # m9
        if args.region is not None and args.region not in REGION:
            raise InputError(f'--region 不在 block_index.REGION 表中：{args.region}')
        if args.stage is not None and args.stage not in STAGE and args.stage != '高考':
            raise InputError(f'--stage 不在 block_index.STAGE 表中：{args.stage}')
        input_paths.append(d)

    exams_rows = read_csv_rows(args.bank / 'indexes' / 'exams.csv')
    exam_files_rows = read_csv_rows(args.bank / 'indexes' / 'exam_files.csv')
    if args.exam_id and not any(r.get('exam_id') == args.exam_id for r in exams_rows) and \
            not (args.bank / 'questions' / args.exam_id).is_dir():
        raise InputError(f'题库无此卷号：{args.exam_id}')  # 参数校验到此为止，才值得付构建全库索引的开销

    index = BankIndex(args.bank)
    index.ensure_all()  # 重复/复用比对要与题库全部已有卷比，不能只建候选卷自己的索引

    if args.exam_id:
        result = check_one(args.exam_id, args.claimed_id, args.bank, args.raw_root, exams_rows,
                            exam_files_rows, index, exclude_self=True)
    elif args.files:
        result = check_one(None, args.claimed_id, args.bank, args.raw_root, exams_rows, exam_files_rows,
                            index, region_name=args.region, stage_name=args.stage, files=args.files)
    else:
        claim = args.claimed_id
        cparsed = None
        if claim:
            try:
                cparsed = parse_exam_id(claim)
            except ExamIdFormatError:
                pass
        else:
            try:
                cparsed = parse_exam_id(Path(args.exam_dir).name)
                claim = Path(args.exam_dir).name
            except ExamIdFormatError:
                pass
        result = check_one(None, claim, args.bank, args.raw_root, exams_rows, exam_files_rows, index,
                            region_name=(cparsed['region_name'] if cparsed else args.region),
                            stage_name=(cparsed['stage_name'] if cparsed else args.stage), md_dir=args.exam_dir)

    summary = {
        'cohort_status': result['cohort_status'], 'has_id_mismatch': bool(result['id_mismatch']),
        'duplicate_count': len(result['duplicates']), 'issue_count': len(result['issues']),
        'fingerprint_coverage': result.get('fingerprint_coverage'),
    }
    rep = build_report('check', args, [result], extra={'summary': summary}, prof=prof)
    if args.report:
        out = write_report(args.report, prof, rep, extra_roots=_extra_protected_roots(args),
                            input_paths=input_paths)
        print(f'报告已写：{out}', file=sys.stderr)
    print(json.dumps({'exam_id': result.get('exam_id') or result.get('claimed_id'),
                       'cohort_year': result['cohort_year'], 'cohort_status': result['cohort_status'],
                       'grade2': result.get('grade2'), 'suggestion': result['suggestion'],
                       'chain_kind': (result['chain'] or {}).get('kind'),
                       'rename_plan': (result['chain'] or {}).get('rename_plan'),
                       'redirects': (result['chain'] or {}).get('redirects'),
                       'reused_ids': (result['chain'] or {}).get('reused_ids'),
                       'id_mismatch': result.get('id_mismatch'),
                       'duplicates': [{'exam_id': a['exam_id'], 'kind': a['kind'],
                                        'matched': a['matched_questions'], 'total': a['total_questions'],
                                        'fraction_reliable': a['fraction_reliable'],
                                        'low_confidence_count': len(a.get('low_confidence_pairs') or [])}
                                       for a in result['duplicates']],
                       'fingerprint_coverage': result.get('fingerprint_coverage'),
                       'retired': result.get('retired'),
                       'issues': result['issues']}, ensure_ascii=False, indent=1))
    return 1 if result['issues'] else 0


def cmd_audit(args):
    prof = _load_profile_arg(args.profile)
    args.bank, args.raw_root = _default_bank_raw(prof, args.bank, args.raw_root)
    if not args.bank.is_dir():
        raise InputError(f'题库根不存在：{args.bank}')
    if not args.raw_root.is_dir():
        raise InputError(f'原材料根不存在：{args.raw_root}')
    if args.limit is not None and args.limit < 0:
        raise InputError(f'--limit 不能为负数：{args.limit}（m9：修复前会被当成“不限”，静默跑全库）')
    exams_rows = read_csv_rows(args.bank / 'indexes' / 'exams.csv')
    exam_files_rows = read_csv_rows(args.bank / 'indexes' / 'exam_files.csv')
    index = BankIndex(args.bank)
    index.ensure_all()

    ids = bank_exam_ids(args.bank)
    if args.limit is not None:
        ids = ids[:args.limit]
    items = []
    for eid in ids:
        try:
            parse_exam_id(eid)
        except ExamIdFormatError:
            items.append({'exam_id': eid, 'issues': ['卷号格式不是 BJ-<年>-<区县>-<阶段>（可能是 ASM- 汇编卷等，跳过届别推算）'],
                          'cohort_year': None, 'cohort_status': 'SKIPPED', 'duplicates': [], 'retired': None})
            continue
        r = check_one(eid, None, args.bank, args.raw_root, exams_rows, exam_files_rows, index, exclude_self=True)
        items.append(r)

    active = [it for it in items if not it.get('retired')]
    mismatches = [it for it in active if it.get('id_mismatch')]
    # 低置信/疑似串题（M-C）不算“真实复用/重复登记”，不计入 has_duplicate_or_reuse——否则 OCR 串题会
    # 和真正的复用/重复登记混在同一个计数里，误导使用者
    dups = [it for it in active
            if any(a['kind'] != 'needs_verification_low_confidence' for a in it.get('duplicates', ()))]
    low_conf_only = [it for it in active if it.get('duplicates')
                      and all(a['kind'] == 'needs_verification_low_confidence' for a in it['duplicates'])]
    conflicts = [it for it in active if it.get('cohort_status') == 'CONFLICT']
    needs_local = [it for it in active if it.get('cohort_status') == 'NEEDS_LOCAL']
    weak_only = [it for it in active if it.get('cohort_status') == 'WEAK_ONLY']
    retired = [it for it in items if it.get('retired')]
    low_cov = [it for it in active if (it.get('fingerprint_coverage') or {}).get('total')
               and it['fingerprint_coverage']['ratio'] < MIN_FINGERPRINT_COVERAGE]
    verified_by_a = sum(1 for it in active if any(e['tier'] == 'A' for e in it.get('evidence', ())
                                                    if e.get('cohort_year') == it.get('cohort_year')))
    verified_by_b = sum(1 for it in active if it.get('cohort_status') == 'OK'
                         and not any(e['tier'] == 'A' for e in it.get('evidence', ())
                                     if e.get('cohort_year') == it.get('cohort_year')))
    rep = build_report('audit', args, items, extra={
        'summary': {'exams_scanned': len(items), 'id_year_mismatches': len(mismatches),
                    'has_duplicate_or_reuse': len(dups), 'conflicts': len(conflicts),
                    'needs_local': len(needs_local), 'weak_only': len(weak_only), 'retired': len(retired),
                    'low_fingerprint_coverage': len(low_cov), 'verified_by_A': verified_by_a,
                    'verified_by_B': verified_by_b, 'needs_verification_low_confidence_only': len(low_conf_only)}},
        prof=prof)
    if args.report:
        out = write_report(args.report, prof, rep, extra_roots=_extra_protected_roots(args))
        print(f'报告已写：{out}', file=sys.stderr)
    print(json.dumps(rep['summary'], ensure_ascii=False, indent=1))
    print('届别不符：', ', '.join(f"{it['exam_id']}(→{it['id_mismatch']['evidence_cohort_year']})" for it in mismatches) or '无')
    print('重复/复用：', ', '.join(f"{it['exam_id']}→{[a['exam_id'] for a in it['duplicates']]}" for it in dups) or '无')
    print('弱证据（未取得原件/题库文字层佐证）：', ', '.join(it['exam_id'] for it in weak_only) or '无')
    print('已撤销登记：', ', '.join(it['exam_id'] for it in retired) or '无')
    return 1 if (mismatches or dups or conflicts or needs_local or weak_only or low_cov) else 0


def build_arg_parser():
    ap = argparse.ArgumentParser(prog='exam_register.py', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--debug', action='store_true', help='打印 traceback')
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--bank', default=None, help='题库根（默认按 --profile 的 sources.bank.root，否则仓库根下 DeepSeek_政治题库资料库_20260918）')
        p.add_argument('--raw-root', default=None, help='原材料根（默认仓库根下 00_共同资料/原材料）')
        p.add_argument('--profile', default=None, help='书册配置（名字或路径），只用来定位 paths.root 与 --report 写出守卫')
        p.add_argument('--report', default=None, help='写 JSON 报告到此路径（受 guard_write 约束）')
        # m2：default=SUPPRESS——子命令没给 --debug 时不在 namespace 里覆盖主解析器已经解析出的
        # True（两个解析器都定义同名 --debug 时，子解析器的默认值会覆盖主解析器的值，导致放在子命令
        # 前面的 --debug 不起作用）；子命令后面确实给了 --debug 时仍按 store_true 正常生效。
        p.add_argument('--debug', action='store_true', default=argparse.SUPPRESS, help='打印 traceback（子命令前后都可以给）')

    pc = sub.add_parser('check', help='新卷登记前检查（单卷）')
    common(pc)
    pc.add_argument('--exam-id', default=None, help='题库已登记卷号，复核用')
    pc.add_argument('--files', nargs='+', default=None, help='新卷原件（原卷.pdf/细则.docx…），尚未进题库')
    pc.add_argument('--exam-dir', default=None, help='刚产出的逐题 MD 目录（questions/某卷）')
    pc.add_argument('--claimed-id', default=None, help='拟登记/待核对的卷号（--files、--exam-dir 时给出用于比对）')
    pc.add_argument('--region', default=None, help='考区中文名（如 海淀），可选——给出才会生成建议卷号')
    pc.add_argument('--stage', default=None, help='阶段中文名（期中/期末/一模/二模/高考），可选——给不出且 --claimed-id 也推不出时报错，不会静默按“期中”处理')
    pc.set_defaults(func=cmd_check)

    pa = sub.add_parser('audit', help='对题库全部卷跑一遍')
    common(pa)
    pa.add_argument('--limit', type=int, default=None, help='只跑前 N 张卷（调试/控速用；0 表示 0 张，不是不限）')
    pa.set_defaults(func=cmd_audit)
    return ap


def main(argv=None):
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    debug = args.debug  # m2：子解析器 default=SUPPRESS 后，args.debug 就是主/子解析器合并后的真值
    try:
        return args.func(args)
    except InputError as e:
        print(f'输入/参数错误：{e}', file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 2
    except dl.GuardError as e:
        print(f'拒绝写出：{e}', file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 3
    except Exception as e:
        print(f'内部错误：{e}', file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
