#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bank_compile.py — 题库逐题 MD 的“编译器”与“完成门禁”（只读题库）。

用途
  compile  把 DeepSeek 题库 questions/<卷>/<题键>.md 编译成干净的读者版。每个二级小节先定角色：
           题面 stem、选项 options、答案 answer、正式细则 e1、教师解析 e3、讲评 commentary、
           学生 student、图表 figures、后台 backstage（修复记录、变体对照、配对状态、候选说明、身份与父对象等）。
           读者版 clean/<卷>/<题键>.md 只收标准角色小节，正文逐字取自原小节（标题行改成“角色｜原标题”，正文不改、
           不摘要），文件开头写机器可读头；另出逐题目录 catalog.jsonl / catalog.csv（UTF-8 BOM，Excel 直接打开）、
           卷级 exams.jsonl 与中文 report.md。
  check    按《给Codex的题库收尾提示词》第五节第 1 条逐项给门（PASS / FAIL / SKIP，附清单）：
           G1 卷状态终结  G2 题号连续·题数一致·索引登记  G3 编译成功·无歧义小节  G4 题面有内容且可采用
           G5 题面不夹答案  G6 选项与题型一致  G7 图片存在且非空白  G8 E1 有正文或具名例外/缺源
           G9 已验收文件无候选/隔离横幅  G10 卷号冲突与重复登记  G11 回溯体检高优先级差异已裁定（给 --retro-summary 时）
           另有附加门：X1 bank.py 默认读法取得到题面（第四节第 1 条）、X2 结构整洁（代码围栏闭合、无嵌入整份旧稿、
           无同名小节）、X4 角色表与 bank.py 别名一致；X3 答案层齐全只提示（--strict 时计入）。
  roles    普查全库二级标题，列出未登记与歧义标题（维护 bank_compile_data/heading_roles.json 用）。

小节角色的判定顺序（不猜）
  1 文件内“读取指引（机器可读）”或“读取指引”点名的题面小节（采用题面小节 / 题面优先读取）与评分小节
    （采用评分小节 / 正式评分优先读取）；
  2 bank.py 的受控别名（STEM_ALIASES、GUIDED_STEM_ALIASES、ROLE_SECTION_ALIASES、ROLE_SECTION_QID_ALIASES、
    STRUCTURE_SECTIONS；只读导入，不修改；bank.py 以后加的别名自动生效）；
  3 bank_compile_data/heading_roles.json 的精确标题表（每条附依据与示例文件），再看 qid_overrides 逐题改判。
  三处都没有的标题判“未登记”，表里标 ambiguous 的判“歧义”，原样来源块（source_block）只有在每行都已在本文件
  别处出现时才当重复进后台，否则也判歧义。未登记与歧义都让该题编译失败并列入报告。
  同一文件有多份题面时按读取指引取一份，其余当备选题面进后台；读取指引点名的是 OCR 候选或教师版含答案块时照取，
  但由 G4 报“不可采用”。

用法（必须用 /usr/bin/python3〔3.9〕；只用标准库与 PIL，fitz 不需要）
  python3 bank_compile.py compile --out-dir DIR [--exam BJ-2026-FS-ERMO ...]
  python3 bank_compile.py check   [--out-dir DIR] [--exam ...] [--retro-summary 回溯体检/summary.json]
                                  [--rulings 题库/validation/retro_rulings.jsonl] [--strict] [--json]
  python3 bank_compile.py roles   [--out-dir DIR] [--emit-draft]
  写进题库 compiled/（只许题库写权人）：
    BANK_ACTOR=<state.json 的 shared_writer> python3 bank_compile.py compile --out-dir <题库>/compiled

输出（全部在 --out-dir 下）
  compile：catalog.jsonl、catalog.csv、exams.jsonl、clean/<卷>/<题键>.md、report.md、_image_cache.json（图片空白检测缓存）
  check  ：check.json、check.md、rulings_todo.jsonl（有未裁定的高优先级差异时，裁定模板）
  roles  ：roles_census.json（--emit-draft 另印未登记标题的 JSON 草稿）
  check 不给 --out-dir 时只在终端打印门禁表。

证据等级
  编译通过只说明结构可读、不代表内容已核验；证据等级照原文件（目录里逐题抄出原文件与 questions.csv 的状态字段）。
  门禁全绿也只说明机械层没有发现问题，不等于内容已核验；逐字准确仍靠回溯体检裁定与主代理抽检。

只读承诺
  题库（DeepSeek_政治题库资料库_20260918）、原件、转换主清单、书稿、协作文件一律只读；导入 bank.py / doc2md.py
  时不写 .pyc。--out-dir 受 doc2md.guard_out_dir 护栏约束（题库、原料、桌面、Skill 目录、书册 profile 目录一律拒绝，
  路径按 realpath、大小写折叠与逐级 inode 三重比较；冻结册走 profile_lib.frozen_guard）。唯一例外：--out-dir 落在
  题库 compiled/ 目录内，且环境变量 BANK_ACTOR 等于 state.json 的 shared_writer。

退出码
  compile：0 编译完成（有编译失败的题也算完成，看 report.md）；2 参数错误、拒绝写入或异常。
  check  ：0 全绿（所有门 PASS，没有 SKIP；--allow-skip 时 SKIP 不算）；1 有 FAIL 或 SKIP；2 参数错误、拒绝写入或异常。
  roles  ：0 没有未登记与歧义标题；1 有；2 异常。
"""
import argparse
import collections
import csv
import glob
import hashlib
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True  # 不在 Skill 目录与题库 scripts 目录留 .pyc
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doc2md as D  # noqa: E402  只用路径常量与写入护栏

VERSION = "bank-compile-2026.09.24"
DATA = os.path.join(HERE, "bank_compile_data", "heading_roles.json")
BANK = D.BANK
QDIR = os.path.join(BANK, "questions")
IDX = os.path.join(BANK, "indexes")
COMPILED = os.path.join(BANK, "compiled")
RECEIPTS = os.path.join(D.PIPE, "receipts")
DEFAULT_RULINGS = os.path.join(BANK, "validation", "retro_rulings.jsonl")
DISCLAIMER = "编译通过只说明结构可读、不代表内容已核验；证据等级照原文件。"

ROLE_ORDER = ["stem", "options", "figures", "answer", "e1", "e3", "commentary", "student"]
CLEAN_ROLES = set(ROLE_ORDER)
ROLE_CN = {"stem": "题面", "options": "选项", "figures": "图表", "answer": "答案", "e1": "正式评分细则E1",
           "e3": "教师解析E3", "commentary": "讲评", "student": "学生答卷", "backstage": "后台",
           "stem_variant": "题面变体", "source_block": "原样来源块", "ambiguous": "歧义", "unmapped": "未登记"}
VALID_ROLES = CLEAN_ROLES | {"stem_variant", "backstage", "source_block", "ambiguous"}
ACCEPTED = "已验收"
RETIRED = "重复登记已撤销"
CLOSED = {ACCEPTED, RETIRED}
BANK_ROLE_MAP = {"e1": "e1", "e3": "answer", "student": "student"}

# ---------------------------------------------------------------- 正则
RE_H2 = re.compile(r"^## (.+)$", re.M)            # 与 bank.split_md 完全一致
RE_H1 = re.compile(r"^# (?!#)(.*)$", re.M)
RE_FENCE = re.compile(r"^\s{0,3}(```|~~~)", re.M)
RE_CJK = re.compile(r"[㐀-鿿豈-﫿]")
RE_WORD = re.compile(r"[㐀-鿿豈-﫿A-Za-z0-9]")
RE_RETIRED = re.compile(r"历史误分片|不属于本卷真实题号|已移出有效题目")
RE_BANNER = re.compile(r"候选|隔离|candidate|not[_ ]merged|quarantin|未晋升|未验收|pending_independent|isolated", re.I)
RE_BANNER_RETIRED = re.compile(r"已停用|历史候选标签|生成时记录|此句仅记载")
RE_BANNER_EXEMPT = re.compile(r"历史记录|关闭[^。；]{0,12}候选|候选[^。；]{0,6}已关闭|已通过独立复核|共享题库正式内容")
RE_BANNER_HARD = re.compile(r"未晋升|未验收|尚未|不能视为|pending|not_accepted|not_merged|candidate_only|不是[^。；]{0,8}验收", re.I)
RE_NOTE = re.compile(r"本节|不得|来源|核验|核对|依据|OCR|候选|原页|页图|转写|见下|注[:：]|说明|保留|不含|分层|E0|E1|E3|角色|"
                     r"原文如此|证据|复核|父稿|SHA|渲染|视觉")
RE_PROV = re.compile(r"^\s*(?:[-*]\s*)?(?:\*\*)?(?:来源|证据|出处|原件|source|page_asset|source_pdf|SHA|sha256|页图|原页|"
                     r"渲染页|定位|路径|原卷来源页|参考答案来源页|本地证据页|角色边界|性质)(?:\*\*)?\s*[:：`\[（(]|"
                     r"^\s*#{3,6}\s*(?:来源|出处)|^\s*<!--|^\s*(```|~~~)|^\s*!\[|^\s*[-*]?\s*\[[^\]]*\]\([^)]*\)\s*[。；;，,]?\s*$|"
                     r"sha256|SHA-256", re.I)
RE_ANS_STRONG = re.compile(r"【(?:答案|解析|分析|详解|点评|解答)】|故选\s*[:：]?\s*[A-D]|(?:正确|标准|参考)?答案\s*[:：为是]\s*\**\s*[A-D](?![A-Za-z])|"
                           r"^\s*#{3,6}\s*(?:参考答案|答案|正式评分|评分细则|阅卷细则|E1|E3|解析|详解)|"
                           r"^[\s>*#]*(?:[\u4e00-\u9fff]{0,10})参考答案(?:及评分(?:标准|参考))?[\s*]*$|细则\s*♣|给\s*\d\s*分")
RE_ANS_WEAK = re.compile(r"参考答案|评分细则|阅卷细则|评分标准|采分点|酌情给分|言之有理即可|细则\s*[:：]")
RE_ANS_CONTENT = re.compile(r"\d\s*分|【|角度|作答|要点|水平\s*\d|①|答：|可从")
RE_NOTE_ANY = re.compile(r"本节|不得|来源|核验|核对|依据|OCR|候选|原页|页图|转写|见下|下方|上方|注[:：]|说明|保留|不含|分层|"
                         r"E0|E1|E3|角色|原文如此|证据|复核|父稿|SHA|渲染|视觉|追溯|PDF|DOCX|PPTX|页首|教师版|刻度|印刷|不用|填入")
RE_NOTE_STRONG = re.compile(r"核验依据|原图依据|执行者|本批|改正内容|父稿|独立复核修正|→|改为|误写|原候选|本轮")
RE_OPT_INLINE = re.compile(r"(?<![A-Za-z0-9_/\\.\-])\**([A-D])\**\s*[．\.、:：]\s*(?=\S|$)", re.M)
RE_OPT_BARE = re.compile(r"^[\s>|*]*([A-D](?:[\s|*]+[A-D])*)[\s|*]*$", re.M)
RE_OPT_TABLE = re.compile(r"(?:^\s*|(?<=\|))\|?\s*\**\s*([A-D])\s*\**\s*[\.．、]?\s*(?=\|)", re.M)
RE_OPT_BOLD = re.compile(r"\*\*([A-D])\*\*(?=\s*[（(：:．.、]|\s*$)", re.M)
RE_STEM_SELF_OCR = re.compile(r"raw OCR|OCR ?原状|未逐字对照|未对照原页|OCR 候选层")
RE_DOUBT = re.compile(r"疑点|原件笔误|笔误|存疑|无法辨认|uncertain|原文如此|疑似")
RE_EVID = re.compile(r"(extraction_status|证据等级|evidence_status|evidence_level|候选状态|candidate_status|text_status|"
                     r"e1_status|rubric_status|转换状态|答案证据等级)\s*[:：]\s*(.+)")
# E1 状态词表（与第四节“写明具名例外或缺源说明”对齐；只写“未提供/未定位/not_provided”不算）
RE_EXC = re.compile(r"N/A_with_basis|N/A with basis|N/A_objective|not_available_for_choice|not_applicable|具名例外|"
                    r"整卷无正式细则例外|唯一整卷无正式细则|无E1整卷例外|唯一无E1")
RE_MISSING = re.compile(r"缺源|source_not_provided|missing_source|原料缺口|原件缺失|原件不在|D-00\d")
RE_EXAM_E1_EXC = re.compile(r"(?:N/A_with_basis|具名例外|缺源|唯一无E1|无E1整卷例外|整卷无正式细则例外)[^。；;]{0,40}?(?:细则|E1|评分)|"
                            r"(?:细则|E1|评分)[^。；;]{0,40}?(?:N/A_with_basis|具名例外|缺源|无E1整卷例外)")
RE_NEG = re.compile(r"没有[^。；\n]{0,20}?(?:提供|正式|细则|评分|E1)|未[^。；\n]{0,40}?(?:提供|找到|定位|配对|确认|发现|闭合|晋升)|"
                    r"不(?:升级|升格)|not_provided|pending|"
                    r"无(?:题级|正式|同题|独立|本题|对应|Q\d|逐题)|不适用|N/A|缺源|不能升级|不得(?:把|将|以|据|升|作为)|不构成|"
                    r"不是正式|非\s*E1|暂未|仅有参考|不宣称|不写正式|不生成\s*E1")
RE_RUBRIC = re.compile(r"[（(]\s*\d+\s*分\s*[)）]|\d+\s*[-—～~]?\s*\d*\s*分(?!析|层|类|别|配|布|数)|水平\s*[1-4一二三四]|等级(?:水平|描述)|"
                       r"角度\s*[1-9一二三四]|给\s*\d|酌情|评分要点|赋分|扣\s*\d")
RE_IMG_EXT = r"\.(?:png|jpe?g|gif|webp|bmp|tiff?)"
RE_IMG_BT = re.compile(r"`([^`\n]+?%s)`" % RE_IMG_EXT, re.I)
RE_IMG_BARE = re.compile(r"(?<![\w/.`(\[<\-])((?:\.\./)*(?:assets|evidence|sources|source_render|rubric_pages)/[^\s`'\"）)\]，。；、>]+?%s)"
                         % RE_IMG_EXT, re.I)
RE_SID = re.compile(r"\bS[0-9a-f]{12}\b")
RE_EXAM_ID = re.compile(r"BJ-\d{4}-[A-Z]+-[A-Z]+")


# ---------------------------------------------------------------- 基础读写
def sha_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def read_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def load_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def clip(s, n=80):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def cjk_count(s):
    return len(RE_CJK.findall(s or ""))


# ---------------------------------------------------------------- bank.py 别名（只读导入）
class BankInfo(object):
    """只读取 bank.py 的别名表和函数，不修改它。"""

    def __init__(self):
        self.mod = None
        self.error = None
        sys.path.insert(0, os.path.join(BANK, "scripts"))
        try:
            import bank as B  # noqa
            self.mod = B
        except Exception as e:  # pragma: no cover
            self.error = "%s: %s" % (type(e).__name__, e)
        B = self.mod
        g = (lambda n, d=(): getattr(B, n, d) if B else d)
        self.stem = set(g("STEM_ALIASES")) | set(g("GUIDED_STEM_ALIASES"))
        self.guided = set(g("GUIDED_STEM_ALIASES"))
        self.role_alias = {k: set(v) for k, v in dict(g("ROLE_SECTION_ALIASES", {})).items()}
        self.qid_alias = {k: {q: set(t) for q, t in v.items()} for k, v in dict(g("ROLE_SECTION_QID_ALIASES", {})).items()}
        self.structure = set(g("STRUCTURE_SECTIONS"))
        self.passthrough = list(g("PASSTHROUGH_SECTIONS"))
        self.unknown = list(g("UNKNOWN_ROLE_SECTIONS"))

    def role(self, title, qid):
        if title in self.stem:
            return "stem"
        for r, ts in self.role_alias.items():
            if title in ts:
                return BANK_ROLE_MAP.get(r)
        for r, byq in self.qid_alias.items():
            if title in byq.get(qid, ()):
                return BANK_ROLE_MAP.get(r)
        if title in self.structure:
            return "figures"
        return None

    def expected_roles(self):
        """bank.py 别名 → 本工具角色（一致性检查用）。"""
        out = {}
        for t in self.stem:
            out.setdefault(t, set()).add("stem")
        for r, ts in self.role_alias.items():
            for t in ts:
                out.setdefault(t, set()).add(BANK_ROLE_MAP.get(r))
        for r, byq in self.qid_alias.items():
            for ts in byq.values():
                for t in ts:
                    out.setdefault(t, set()).add(BANK_ROLE_MAP.get(r))
        for t in self.structure:
            out.setdefault(t, set()).add("figures")
        return out

    def adopted_stem(self, md):
        if not self.mod:
            return None
        try:
            return self.mod.adopted_stem(md)[0]
        except Exception:
            return None

    def destinations(self, text):
        if self.mod and hasattr(self.mod, "markdown_destinations"):
            try:
                return [raw for raw, _ in self.mod.markdown_destinations(text)]
            except Exception:
                pass
        return re.findall(r"\]\(\s*<?([^)>\s]+)>?\s*\)", text)


# ---------------------------------------------------------------- 角色表
def load_roles(path=DATA):
    d = load_json(path)
    if not d or "headings" not in d:
        raise SystemExit("角色表读不到或格式不对：%s" % path)
    bad = []
    for t, e in d["headings"].items():
        if e.get("role") not in VALID_ROLES:
            bad.append("标题「%s」角色 %r 不在 %s" % (t, e.get("role"), sorted(VALID_ROLES)))
        if not (e.get("basis") or "").strip():
            bad.append("标题「%s」缺 basis（依据）" % t)
    for q, m in (d.get("qid_overrides") or {}).items():
        for t, e in m.items():
            if e.get("role") not in VALID_ROLES or not (e.get("basis") or "").strip():
                bad.append("逐题改判 %s「%s」角色或依据不合法" % (q, t))
    d["_errors"] = bad
    d.setdefault("qid_overrides", {})
    d.setdefault("stem_marker_allow", {})
    return d


# ---------------------------------------------------------------- 题库状态
class Bank(object):
    def __init__(self):
        self.manifest = load_json(D.MANIFEST, {}) or {}
        self.tasks = collections.OrderedDict((t["exam_id"], t) for t in self.manifest.get("tasks", []))
        self.task_dups = [e for e, n in collections.Counter(t["exam_id"] for t in self.manifest.get("tasks", [])).items()
                          if n > 1]
        self.qrows = collections.defaultdict(list)
        for r in read_csv(os.path.join(IDX, "questions.csv")):
            self.qrows[r["question_id"]].append(r)
        self.exams_csv = {r["exam_id"].strip(): r for r in read_csv(os.path.join(IDX, "exams.csv"))}
        self.writer = (load_json(D.STATE, {}) or {}).get("shared_writer", "")
        # source_id / 相对路径 → 登记在哪些在用卷
        self.src_exams = collections.defaultdict(set)
        self.path_sid = {}
        base_seen = collections.defaultdict(set)
        for e, t in self.tasks.items():
            for role, lst in (t.get("sources") or {}).items():
                for s in (lst if isinstance(lst, list) else [lst]):
                    if not isinstance(s, dict):
                        continue
                    sid = s.get("source_id")
                    if sid:
                        if t.get("status") != RETIRED:
                            self.src_exams[sid].add(e)
                        rp = (s.get("rel_path") or "").strip()
                        if rp:
                            self.path_sid[rp] = sid
                            base_seen[os.path.basename(rp)].add(sid)
        for b, sids in base_seen.items():   # 只收唯一的文件名（“试卷.pdf”这类重名不作映射）
            if len(sids) == 1 and b not in self.path_sid:
                self.path_sid[b] = next(iter(sids))

    def exam_dir(self, e):
        t = self.tasks.get(e, {})
        od = t.get("output_dir") or ""
        if od:
            p = os.path.join(os.path.dirname(BANK), od)
            if os.path.isdir(p):
                return p
        return os.path.join(QDIR, e)

    def index_row(self, qid):
        rows = self.qrows.get(qid) or []
        return next((r for r in rows if r.get("variant") == "visual_checked_shared"), rows[0] if rows else None)


# ---------------------------------------------------------------- 解析题文件
def split_sections(md):
    """[(title, body, heading_line, end_line)]；切分规则与 bank.split_md 相同（行首“## ”，不看代码围栏）。"""
    ms = list(RE_H2.finditer(md))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        hl = md.count("\n", 0, m.start()) + 1
        el = md.count("\n", 0, max(m.start(), end - 1)) + 1
        out.append((m.group(1).strip(), md[m.end():end], hl, el))
    return out, (md[:ms[0].start()] if ms else md)


RE_PAGE_FURNITURE = re.compile(r"^\s*第\s*\d+\s*页|共\s*\d+\s*页|参考答案及评分(?:标准|参考)\s*$")


def norm_cmp(t):
    """比较用：去空白、引用符、强调符、HTML 标签与反引号。"""
    t = re.sub(r"<[^>]*>|<!--.*?-->", "", t)
    return re.sub(r"[\s>*`#|]+", "", t)


def content_lines(body):
    """去掉出处、注记、链接行后的正文行。"""
    out = []
    for ln in body.split("\n"):
        s = ln.strip()
        if not s:
            continue
        if RE_PROV.search(s):
            continue
        if s.startswith(">") and RE_NOTE.search(s):
            continue
        out.append(s)
    return out


def substantive(body):
    """(汉字数, 字词数)：只数正文行；链接地址、反引号路径、HTML 注释不算。"""
    t = "\n".join(content_lines(body))
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"\]\([^)]*\)", "]", t)
    t = re.sub(r"`[^`\n]*?(?:/|\.png|\.pdf|\.docx|\.pptx|\.md|\.json)[^`\n]*`", "", t)
    return cjk_count(t), len(RE_WORD.findall(t))


def parse_guide(sections):
    g = {"stem": [], "e1": [], "alt": [], "forbid": [], "stem_nature": "", "present": False}
    keys = {"采用题面小节": "stem", "题面优先读取": "stem", "采用评分小节": "e1", "正式评分优先读取": "e1",
            "备选题面小节": "alt", "不得当作题面": "forbid"}
    for title, body, _, _ in sections:
        if title not in ("读取指引（机器可读）", "读取指引"):
            continue
        g["present"] = True
        for ln in body.split("\n"):
            m = re.match(r"^\s*-\s*([^:：\n`]+?)\s*[:：]\s*(.*)$", ln)
            if not m:
                continue
            k, v = m.group(1).strip(), m.group(2).strip()
            if k == "采用题面来源性质":
                g["stem_nature"] = v
                continue
            role = keys.get(k)
            if not role:
                continue
            names = re.findall(r"`([^`]+)`", v)
            if not names and v and v not in ("无", "（无）"):
                names = [v]
            g[role] = [n.strip() for n in names if n.strip() and n.strip() != "无"]
    return g


def id_field(text, names):
    for n in names:
        m = re.search(r"(?:^|[\s；;，,|（(])%s\s*[:：]\s*`?([^`\n；;|，,]+)" % n, text, re.M)
        if m:
            return m.group(1).strip().strip("*` ")
    return ""


def norm_type(s):
    s = s or ""
    if re.search(r"非选择|主观|简答|论述|材料分析", s):
        return "非选择题"
    if "选择" in s:
        return "选择题"
    return ""


def option_labels(stem_body):
    lines = []
    for ln in stem_body.split("\n"):
        s = ln.strip()
        if not s or RE_PROV.search(s):
            continue
        if s.startswith(">") and (RE_NOTE_STRONG.search(s) or (RE_NOTE.search(s) and not re.search(r"[A-D]\**\s*[．\.、]", s))):
            continue
        lines.append(ln)
    t = "\n".join(lines)
    t = re.sub(r"\]\([^)]*\)", "]", t)
    t = re.sub(r"!\[[^\]]*\]", "", t)
    fam = [collections.Counter(m.group(1) for m in RE_OPT_INLINE.finditer(t)),
           collections.Counter(m.group(1) for m in RE_OPT_TABLE.finditer(t)),
           collections.Counter(m.group(1) for m in RE_OPT_BOLD.finditer(t)),
           collections.Counter()]
    for m in RE_OPT_BARE.finditer(t):   # 图片选项：只剩字母的行（如“A      B”）
        for x in re.findall(r"[A-D]", m.group(1)):
            fam[3][x] += 1
    # 同一种写法里重复才算“重复”；表格+粗体复述同一组选项不算
    return collections.Counter({x: max(f.get(x, 0) for f in fam) for x in "ABCD" if any(f.get(x) for f in fam)})


def answer_letters(text, num, bare=False):
    pats = [r"答案键[^A-D\n]{0,12}?\**\s*([A-D])(?![A-Za-z])",
            r"第\s*%d\s*题\s*(?:答案)?\s*(?:为|是|=|：|:)\s*\**\s*([A-D])(?![A-Za-z])" % num,
            r"故选\s*[:：]?\s*([A-D])(?![A-Za-z])",
            r"【答案】\s*([A-D])(?![A-Za-z])",
            r"(?:标准答案|参考答案|客观答案|选择题答案|答案登记|同卷答案键|answer_key|答案)\s*[:：]\s*[`*\s]*([A-D])(?![A-Za-z])",
            r"(?m)^\s*[>\-*\s]*(?:Q)?%d\s*[\.．、:=：]\s*\**\s*([A-D])(?![A-Za-z])" % num,
            r"Q%d\s*=\s*\**\s*([A-D])(?![A-Za-z])" % num]
    if bare:  # 答案小节里单独成行的字母（如“B”）
        pats.append(r"(?m)^\s*[>\-*\s]*\**([A-D])\**\s*[。.]?\s*$")
    out = []
    for p in pats:
        out += re.findall(p, text)
    return out


def image_refs(text, bankinfo, bases=()):
    """图片引用：Markdown 链接/图片一律算；反引号与裸路径只在像本地路径时算（首段目录真实存在，
    或能解析到文件），像 `word/media/image1.png`、`img-000.png` 这种描述原件内部位置的写法不算。"""
    links = []
    for raw in bankinfo.destinations(text):
        p = raw.strip().strip("<>")
        if re.search(RE_IMG_EXT + r"(?:[#?].*)?$", p, re.I) and not re.match(r"^[a-z]+://", p, re.I):
            links.append(p)
    names = set(os.path.basename(x) for x in links)
    loose = []
    for r in RE_IMG_BT.findall(text) + RE_IMG_BARE.findall(text):
        r = r.strip()
        if not r or os.path.basename(r) in names:   # 与链接同名的反引号路径多是对同一张图的描述
            continue
        if "..." in r.replace("../", "") or "…" in r:
            continue
        first = r.split("/", 1)[0] if "/" in r else ""
        looks_local = r.startswith(("../", "./", "/")) or (first and any(os.path.isdir(os.path.join(b, first)) for b in bases[:2])) \
            or any(os.path.isfile(os.path.join(b, r)) for b in bases)
        if looks_local:
            loose.append(r)
    seen, out = set(), []
    for r in links + loose:
        if r and r not in seen:
            seen.add(r)
            out.append(r)
    return out


def resolve_ref(ref, qdir, exam_dir):
    from urllib.parse import unquote
    p = unquote(ref.split("#", 1)[0].split("?", 1)[0]).strip()
    if os.path.isabs(p):
        return p, os.path.isfile(p)
    for base in (qdir, exam_dir, BANK, os.path.dirname(BANK), D.RAW):
        c = os.path.normpath(os.path.join(base, p))
        if os.path.isfile(c):
            return c, True
    return os.path.normpath(os.path.join(qdir, p)), False


class ImageChecker(object):
    """PIL 判空白：近白（≥246）像素比例与墨迹（<128）比例；结果按路径+大小+mtime 缓存。"""

    def __init__(self, cache_path=None, ink=0.002, white=0.95):
        self.cache_path = cache_path
        self.cache = load_json(cache_path, {}) if cache_path else {}
        self.ink, self.white = ink, white
        self.pil = None
        try:
            from PIL import Image  # noqa
            self.pil = Image
        except Exception:
            pass

    def check(self, path):
        try:
            st = os.stat(path)
        except OSError:
            return {"exists": False}
        key = "%s|%d|%d" % (path, st.st_size, int(st.st_mtime))
        if key in self.cache:
            return self.cache[key]
        r = {"exists": True}
        if self.pil is None:
            r["blank"] = None
            r["note"] = "PIL 不可用，未判空白"
        else:
            try:
                im = self.pil.open(path)
                r["size"] = list(im.size)
                try:
                    im.draft("L", (1200, 1200))
                except Exception:
                    pass
                if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                    im = im.convert("RGBA")
                    bg = self.pil.new("RGBA", im.size, (255, 255, 255, 255))
                    bg.alpha_composite(im)
                    im = bg
                im = im.convert("L")
                if max(im.size) > 1200:
                    im.thumbnail((1200, 1200))
                h = im.histogram()
                tot = float(sum(h)) or 1.0
                r["near_white"] = round(sum(h[246:]) / tot, 5)
                r["ink"] = round(sum(h[:128]) / tot, 5)
                lo, hi = im.getextrema()
                r["blank"] = bool((r["ink"] < self.ink and r["near_white"] >= self.white) or hi - lo < 8)
            except Exception as e:
                r["blank"] = True
                r["note"] = "打不开：%s" % type(e).__name__
        self.cache[key] = r
        return r

    def save(self):
        if self.cache_path:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as fh:
                json.dump(self.cache, fh, ensure_ascii=False)


# ---------------------------------------------------------------- 单题编译
def issue(code, gate, msg, severity="FAIL"):
    return {"code": code, "gate": gate, "severity": severity, "msg": msg}


def e1_status(secs):
    """secs: [(title, body)]。返回 (状态, 说明)。状态：text / 具名例外 / 缺源 / 空（仅写未提供/未定位） / 空（仅出处/链接） / 空 / 无E1小节。"""
    if not secs:
        return "无E1小节", ""
    best, note = None, ""
    rank = {"text": 5, "具名例外": 4, "缺源": 3, "空（仅写未提供/未定位）": 2, "空（仅出处/链接）": 1, "空": 0}
    for title, body in secs:
        c, _ = substantive(body)
        txt = "\n".join(content_lines(body))
        allt = title + "\n" + body
        neg = bool(RE_NEG.search(title + "\n" + txt))
        rub = bool(RE_RUBRIC.search(txt))
        # 状态说明（“没有/未提供/不升级为E1”这类句子）短于 120 字时不当作细则正文
        if c >= 30 and ((not neg) or (rub and c >= 120) or c >= 300):
            st = "text"
        elif 8 <= c < 30 and rub and not neg:
            st = "text"
        elif RE_EXC.search(allt):
            st = "具名例外"
        elif RE_MISSING.search(allt):
            st = "缺源"
        elif c == 0 and re.search(r"\]\(|`[^`]+\.(?:md|pdf|docx|pptx|png)`|来源|出处", body):
            st = "空（仅出处/链接）"
            links = [a or b for a, b in re.findall(r"\]\(([^)]+\.md)[^)]*\)|`([^`]+\.md)`", body)]
            if links:
                note = "正文可能在链接文件：%s" % "、".join(links[:3])
        elif neg:
            st = "空（仅写未提供/未定位）"
        elif c > 0:
            st = "text"
        else:
            st = "空"
        if best is None or rank[st] > rank[best]:
            best = st
    return best, note


def exam_e1_exception(task, num):
    """转换主清单 exceptions / source_limitations 里的卷级 E1 例外（须用具名例外/缺源词表）；有题号范围的只管范围内的题。"""
    for x in list(task.get("exceptions") or []) + list(task.get("source_limitations") or []):
        if not isinstance(x, str) or not RE_EXAM_E1_EXC.search(x):
            continue
        rng = re.findall(r"Q(\d+)\s*[-—–~]\s*Q?(\d+)", x)
        one = re.findall(r"Q(\d+)(?!\s*[-—–~\d])", x)
        if rng or one:
            ok = any(int(a) <= num <= int(b) for a, b in rng) or str(num) in one
            if not ok:
                continue
        return clip(x, 60)
    return ""


def student_status(secs):
    if not secs:
        return "无小节"
    anyc = False
    for _, body in secs:
        c, _ = substantive(body)
        if re.search(r"N/A|未提供|不适用|缺源|没有|未发现|无学生", body) and c < 250:
            continue
        if c > 0 or re.search(r"!\[|\.png|\.jpe?g", body):
            anyc = True
    return "有" if anyc else "N/A（写明）"


def compile_question(exam, fname, qpath, bank, roles, bankinfo, imgs, opts):
    md = open(qpath, encoding="utf-8").read()
    qid = fname[:-3]
    num = int(re.search(r"-Q(\d+)$", qid).group(1))
    qdir = os.path.dirname(qpath)
    exam_dir = bank.exam_dir(exam)
    sections, preamble = split_sections(md)
    rec = collections.OrderedDict()
    rec["question_id"] = qid
    rec["exam_id"] = exam
    rec["exam_status"] = (bank.tasks.get(exam) or {}).get("status", "")
    rec["num"] = num
    rec["source_path"] = os.path.relpath(qpath, BANK)
    rec["file_sha256"] = sha_text(md)
    issues = []
    head = "\n".join(md.split("\n")[:5])
    # 历史误分片兼容入口：开头声明不属本卷真实题号，且没有正文小节（只剩指向历史副本的链接）
    rec["retired"] = bool(RE_RETIRED.search(head)) and len(sections) <= 1
    if rec["retired"]:
        rec["compile_status"] = "retired"
        rec["issues"] = []
        return rec, None, md

    guide = parse_guide(sections)
    ov = roles["qid_overrides"].get(qid, {})
    table = roles["headings"]
    # ---- 逐节定角色
    info = []
    for i, (title, body, hl, el) in enumerate(sections):
        ent = table.get(title) or {}
        b = bankinfo.role(title, qid)
        if b:
            role, basis = b, "bank.py 别名"
        elif title in ov:
            role, basis, ent = ov[title]["role"], "逐题改判：" + ov[title].get("basis", ""), ov[title]
        elif ent:
            role, basis = ent["role"], "角色表：" + ent.get("basis", "")
        else:
            role, basis = "unmapped", "未登记标题"
        if title in guide["e1"]:
            role, basis = "e1", "读取指引（采用评分小节）"
        info.append({"i": i, "title": title, "body": body, "hl": hl, "el": el, "role": role, "basis": basis, "ent": ent})
    by_title = collections.defaultdict(list)
    for s in info:
        by_title[s["title"]].append(s)
    # ---- 题面
    stem = None
    stem_basis = ""
    gtitle = guide["stem"][0] if guide["stem"] else ""
    if gtitle:
        if gtitle in by_title:
            stem = by_title[gtitle][-1]   # 与 bank.py dict(secs) 一致：同名取最后一个
            stem_basis = "读取指引"
        else:
            issues.append(issue("GUIDE_MISSING_SECTION", "X2", "读取指引点名的题面小节「%s」在文件里不存在（已改按别名/角色表取题面）" % gtitle))
    bank_stem = bankinfo.adopted_stem(md)
    if stem is None and bank_stem and bank_stem in by_title:
        stem = by_title[bank_stem][-1]
        stem_basis = "bank.py 默认读法"
    stems = [s for s in info if s["role"] == "stem"]
    stem_titles = list(collections.OrderedDict((s["title"], 1) for s in stems))
    if stem is None and stems:
        stem = stems[0]
        stem_basis = "角色表（唯一题面小节）" if len(stem_titles) == 1 else "角色表（多份题面取第一份）"
        if len(stem_titles) > 1:
            issues.append(issue("MULTI_STEM_NO_GUIDE", "G3", "有 %d 份题面小节（%s）而读取指引没有裁定采用哪一份" % (
                len(stem_titles), "、".join("「%s」" % clip(t, 30) for t in stem_titles))))
    if stem is None:
        variants = [s for s in info if s["role"] == "stem_variant"]
        order = {"teacher_with_answers": 0, "alt_transcription": 1, "embedded_legacy": 2, "ocr_candidate": 3}
        variants.sort(key=lambda s: (order.get(s["ent"].get("variant"), 9), s["i"]))
        if variants:
            stem = variants[0]
            stem_basis = "兜底：只有题面变体"
    if stem is not None:
        stem["role"] = "stem"
        stem["adopted"] = True
        ent = stem["ent"] or {}
        if ent.get("unsafe_as_stem") or ent.get("role") == "stem_variant":
            others = [t for t in stem_titles if t != stem["title"]]
            hint = "；文件内另有题面小节 %s，读取指引应改指向它" % "、".join("「%s」" % clip(t, 40) for t in others) if others else ""
            issues.append(issue("STEM_UNSAFE_VARIANT", "G4", "采用的题面小节「%s」是%s，不可作定稿题面%s" % (
                clip(stem["title"], 40), ent.get("unsafe_as_stem") or "题面变体", hint)))
        head_lines = "\n".join(stem["body"].split("\n")[:12])
        if RE_STEM_SELF_OCR.search(head_lines) and not re.search(r"逐字(?:对照|核对)(?:一致|完成|通过)", head_lines):
            issues.append(issue("STEM_SELF_OCR", "G4", "题面小节自述为未核对的 OCR 原状：%s" % clip(
                RE_STEM_SELF_OCR.search(head_lines).group(0), 30)))
        for s in stems:
            if s is not stem:
                s["role"] = "backstage"
                s["basis"] = "备选题面（未采用）"
        extra = [t for t in stem_titles if t != stem["title"]]
        if extra and stem_basis == "读取指引":
            issues.append(issue("EXTRA_STEMS", "G3", "另有 %d 份题面小节未采用（按读取指引）：%s" % (
                len(extra), "、".join("「%s」" % clip(t, 30) for t in extra)), "WARN"))
    for s in info:
        if s["role"] == "stem_variant":
            s["role"] = "backstage"
            s["basis"] = "题面变体（未采用）"
    # ---- 原样来源块：全重复→后台，否则歧义
    for s in info:
        if s["role"] != "source_block":
            continue
        others = "".join(norm_cmp(o["body"]) for o in info if o is not s)
        lines = []
        for ln in s["body"].split("\n"):
            if not ln.strip() or re.match(r"^\s*(?:#{3,6}|>\s*这些块|>\s*参考答案不等于|>\s*讲评块|<!--)", ln):
                continue
            x = re.sub(r"^[-*]|^\d+[\.、]", "", norm_cmp(ln))
            if cjk_count(x) >= 10 and not RE_PAGE_FURNITURE.search(ln):
                lines.append((x, ln.strip()))
        miss = [raw for x, raw in lines if x not in others]
        if miss:
            s["role"] = "ambiguous"
            s["basis"] = "原样来源块有 %d/%d 行不见于本文件其他小节（如「%s」），须把内容并入对应角色小节或写明排除" % (
                len(miss), len(lines), clip(miss[0], 40))
        else:
            s["role"] = "backstage"
            s["basis"] = "原样来源块（全部内容已在其他小节）"
    # ---- 歧义 / 未登记
    for s in info:
        if s["role"] == "ambiguous":
            issues.append(issue("AMBIGUOUS_SECTION", "G3", "小节「%s」角色有歧义：%s" % (
                clip(s["title"], 50), clip(s["basis"].replace("角色表：", ""), 90))))
        elif s["role"] == "unmapped":
            issues.append(issue("UNMAPPED_HEADING", "G3", "小节「%s」标题未登记（bank.py 别名与角色表都没有）" % clip(s["title"], 60)))
    if stem is None:
        issues.append(issue("NO_STEM", "G4", "没有可作题面的小节"))
    # ---- 结构整洁
    h1 = RE_H1.findall(md)
    if len(h1) != 1:
        issues.append(issue("EMBEDDED_H1", "X2", "文件有 %d 个一级标题（疑似嵌入整份旧题稿）" % len(h1)))
    dup = [t for t, v in by_title.items() if len(v) > 1]
    if dup:
        issues.append(issue("DUP_TITLE", "X2", "同名小节重复：%s" % "、".join("「%s」×%d" % (clip(t, 30), len(by_title[t])) for t in dup)))
    for s in info:
        if len(RE_FENCE.findall(s["body"])) % 2:
            issues.append(issue("UNCLOSED_FENCE", "X2", "小节「%s」里代码围栏未闭合（渲染时会吞掉后面的小节）" % clip(s["title"], 40)))
    # ---- bank.py 默认读法
    if bank_stem is None:
        issues.append(issue("BANK_GET_NO_STEM", "X1", "bank.py get 取不到题面（adopted_stem 为空）"))
    elif stem is not None and bank_stem != stem["title"]:
        issues.append(issue("BANK_GET_DIFFERENT", "X1", "bank.py get 取的是「%s」，编译采用「%s」" % (
            clip(bank_stem, 30), clip(stem["title"], 30)), "WARN"))
    if not bank.qrows.get(qid):
        issues.append(issue("NOT_IN_INDEX", "X1", "questions.csv 没有本题登记（bank.py get 会报“未找到”）"))

    # ---- 角色汇总
    roles_secs = collections.defaultdict(list)
    for s in info:
        if s["role"] in CLEAN_ROLES:
            roles_secs[s["role"]].append(s)
    ident_text = preamble + "".join("\n" + s["body"] for s in info if "身份" in s["title"])
    idx = bank.index_row(qid) or {}
    stem_body = stem["body"] if stem else ""
    stem_c, stem_w = substantive(stem_body)
    rec["stem_title"] = stem["title"] if stem else ""
    rec["stem_basis"] = stem_basis
    rec["stem_line"] = stem["hl"] if stem else None
    if stem is not None and stem_c < 20:
        issues.append(issue("STEM_EMPTY", "G4", "题面正文只有 %d 个汉字" % stem_c))
    # 题型
    t_decl = norm_type(id_field(ident_text, ["题型", "question_type", "类型"]) or id_field(md, ["题型", "question_type"]))
    t_idx = norm_type(idx.get("type", ""))
    labels = option_labels(stem_body)
    ef = re.search(r"(?<![A-Za-z0-9_/\\.\-])\**[EF]\**\s*[．\.、:：]\s*\S", stem_body)
    full = all(labels.get(x) for x in "ABCD") and not ef   # 出现 E、F 标号的是表述组，不是四选一选项
    score_stem = ""
    m = re.search(r"[（(]\s*(\d{1,2})\s*分\s*[)）]", stem_body)
    if m:
        score_stem = m.group(1) + "分"
    if full:
        t_struct = "选择题"
    elif not any(labels.values()) and (re.search(r"[（(]\s*(?:[4-9]|1\d|2\d)\s*分\s*[)）]", stem_body)
                                       or re.search(r"运用.{0,20}知识|结合材料|谈谈|说明|分析|阐明|论述", stem_body)):
        t_struct = "非选择题"
    else:
        t_struct = ""
    t_final = t_decl or t_idx or t_struct
    rec["type"] = t_final
    rec["type_declared"] = t_decl
    rec["type_index"] = t_idx
    rec["type_structure"] = t_struct
    known = [x for x in (t_decl, t_idx, t_struct) if x]
    if len(set(known)) > 1:
        issues.append(issue("TYPE_CONFLICT", "G6", "题型标注不一致：MD「%s」/ questions.csv「%s」/ 题面结构「%s」" % (
            t_decl or "未标", t_idx or "未标", t_struct or "不明")))
    if not t_decl and not t_idx:
        issues.append(issue("TYPE_MISSING", "G6", "MD 与 questions.csv 都没有标题型", "WARN"))
    if stem is not None:
        if t_final == "选择题":
            miss = [x for x in "ABCD" if not labels.get(x)]
            dupl = [x for x in "ABCD" if labels.get(x, 0) > 1]
            if miss:
                issues.append(issue("CHOICE_OPTIONS_MISSING", "G6", "选择题题面缺选项 %s" % "".join(miss)))
            if dupl:
                issues.append(issue("CHOICE_OPTIONS_DUP", "G6", "选择题题面选项字母重复：%s" % "、".join(
                    "%s×%d" % (x, labels[x]) for x in dupl)))
        elif t_final == "非选择题" and full:
            issues.append(issue("NONCHOICE_HAS_OPTIONS", "G6", "非选择题题面里有完整的 A—D 选项组"))
    rec["options"] = "".join(x for x in "ABCD" if labels.get(x))
    rec["options_count"] = {x: labels.get(x, 0) for x in "ABCD"}
    rec["score"] = clip(id_field(ident_text, ["分值", "printed_score", "score"]), 40)
    rec["score_stem"] = score_stem
    subq = clip(id_field(ident_text, ["小问"]), 40)
    if not subq:
        nums = sorted(set(re.findall(r"(?m)^[>\s*]*[（(]([1-9])[)）]", stem_body)))
        subq = ("题面检出 %d 问" % len(nums)) if len(nums) > 1 else ""
    rec["subq"] = subq
    # 题面夹答案
    allow = roles["stem_marker_allow"].get(qid, [])
    hits = []
    for ln in stem_body.split("\n"):
        s = ln.strip()
        if not s or re.match(r"^#{3,6}\s*来源|^<!--", s):
            continue
        if any(a and a in s for a in allow):
            continue
        m1 = RE_ANS_STRONG.search(s)
        m2 = None
        if not m1 and not RE_PROV.search(s) and not RE_NOTE_ANY.search(s):
            m2 = RE_ANS_WEAK.search(s)
            if m2 and not RE_ANS_CONTENT.search(s):
                m2 = None
        mm = m1 or m2
        if mm:
            hits.append(clip(s[max(0, mm.start() - 12):mm.end() + 18], 60))
    if hits:
        issues.append(issue("STEM_HAS_ANSWER", "G5", "题面里有答案/评分字样 %d 处，如：%s" % (len(hits), " | ".join(hits[:3]))))
    rec["stem_answer_hits"] = hits[:5]
    # 各角色字数
    layer = collections.OrderedDict()
    for r in ROLE_ORDER:
        if r == "options":
            layer[r] = {"present": bool(rec["options"]), "chars": sum(labels.values()), "from": "题面解析"}
            continue
        ss = roles_secs.get(r, [])
        c = sum(substantive(s["body"])[0] for s in ss)
        layer[r] = {"present": bool(ss), "chars": c, "sections": [s["title"] for s in ss]}
    for s in roles_secs.get("answer", []):
        for inc in (s["ent"] or {}).get("includes", []):
            if inc in layer and not layer[inc]["present"]:
                layer[inc]["present"] = True
                layer[inc]["sections"].append(s["title"] + "（同块）")
    rec["layers"] = layer
    # 答案键：依次看答案、解析、E1、讲评小节，先找到的为准
    letters, key_from = [], ""
    if t_final == "选择题":
        for r_ in ("answer", "e3", "e1", "commentary"):
            for s in roles_secs.get(r_, []):
                letters += answer_letters(s["body"], num, bare=(r_ == "answer"))
            if letters:
                key_from = ROLE_CN[r_]
                break
    keys = sorted(set(letters))
    na_key = any(re.search(r"N/A|缺源|没有.{0,10}答案|未提供.{0,10}答案|无独立参考答案|不补造答案", s["body"])
                 for s in roles_secs.get("answer", []))
    rec["answer_key"] = keys[0] if len(keys) == 1 else ("冲突:" + "/".join(keys) if keys else ("缺源（写明）" if na_key and t_final == "选择题" else ""))
    rec["answer_key_from"] = key_from
    rec["answer_source_roles"] = sorted(set((s["ent"] or {}).get("source_role") or "E3 参考答案" for s in roles_secs.get("answer", [])))
    if t_final == "选择题":
        if not keys and na_key:
            issues.append(issue("CHOICE_KEY_NA", "X3", "选择题答案键写明缺源/N/A", "WARN"))
        elif not keys:
            issues.append(issue("CHOICE_NO_KEY", "X3", "选择题没有从答案/解析/细则/讲评小节解析到答案键", "WARN"))
        elif len(keys) > 1:
            issues.append(issue("CHOICE_KEY_CONFLICT", "X3", "答案键不唯一：%s（如属来源冲突须在疑点里写明）" % "/".join(keys), "WARN"))
    # E1
    e1s, e1note = e1_status([(s["title"], s["body"]) for s in roles_secs.get("e1", [])])
    exam_exc = exam_e1_exception(bank.tasks.get(exam, {}), num) if e1s not in ("text", "具名例外", "缺源") else ""
    if t_final == "选择题" and e1s != "text":
        e1s_disp = "选择题不要求｜%s" % e1s
    elif exam_exc:
        e1s_disp = "卷级例外｜%s" % e1s
    else:
        e1s_disp = e1s
    rec["e1_status"] = e1s_disp
    rec["e1_exam_exception"] = exam_exc
    if t_final != "选择题" and e1s not in ("text", "具名例外", "缺源"):
        if exam_exc:
            issues.append(issue("E1_EXAM_LEVEL_ONLY", "G8", "题文件 E1 状态为「%s」，靠主清单卷级例外放行：%s" % (e1s, exam_exc), "WARN"))
        else:
            issues.append(issue("E1_EMPTY", "G8", "非选择题 E1 状态为「%s」：须补正式细则原文，或写明具名例外（N/A_with_basis 等）/缺源%s" % (
                e1s, "；" + e1note if e1note else "")))
    # E1 藏在其他角色小节的 ### 子节里（脚本按小节取 E1 时会漏）
    for s in info:
        if s["role"] in CLEAN_ROLES and s["role"] not in ("e1", "figures"):
            subs = re.findall(r"(?m)^#{3,5}\s*(.+)$", s["body"])
            hid = [x for x in subs if re.search(r"正式评分|E1|评分细则|阅卷细则", x) and not re.search(r"来源|定位|非\s*(?:正式)?\s*E1|非正式|不是|不得|E3|答案层", x)]
            if hid:
                issues.append(issue("E1_HIDDEN_IN_SUBSECTION", "G3", "E1 写在「%s」（%s）的子节「%s」里，须拆成独立的 E1 小节" % (
                    clip(s["title"], 30), ROLE_CN[s["role"]], clip(hid[0], 30))))
    if t_final != "选择题" and not layer["answer"]["chars"] and e1s != "text":
        issues.append(issue("NONCHOICE_NO_ANSWER", "X3", "非选择题既无参考答案正文也无 E1 正文", "WARN"))
    rec["student_status"] = student_status([(s["title"], s["body"]) for s in roles_secs.get("student", [])])
    # 图片
    img = []
    for s in info:
        included = s["role"] in CLEAN_ROLES
        for ref in image_refs(s["body"], bankinfo, (qdir, exam_dir, BANK)):
            path, ok = resolve_ref(ref, qdir, exam_dir)
            r = {"ref": ref, "path": path, "exists": ok, "section": s["title"], "role": s["role"], "included": included}
            if ok:
                c = imgs.check(path)
                r["blank"] = c.get("blank")
                if c.get("ink") is not None:
                    r["ink"] = c["ink"]
                    r["near_white"] = c.get("near_white")
                    r["low_ink"] = bool(not c.get("blank") and c["ink"] < opts.blank_ink * 2 and c.get("near_white", 0) >= 0.97)
                if c.get("note"):
                    r["note"] = c["note"]
            img.append(r)
    inc = [x for x in img if x["included"]]
    rec["images"] = img
    rec["img_refs"] = len(inc)
    miss = [x for x in inc if not x["exists"]]
    blank = [x for x in inc if x.get("blank")]
    if miss:
        issues.append(issue("IMG_MISSING", "G7", "读者版小节引用的图片不存在 %d 个：%s" % (
            len(miss), "；".join("%s（%s）" % (x["ref"], clip(x["section"], 16)) for x in miss[:4]))))
    if blank:
        issues.append(issue("IMG_BLANK", "G7", "图片疑似空白 %d 个：%s" % (
            len(blank), "；".join("%s（墨迹%s）" % (x["ref"], x.get("ink")) for x in blank[:4]))))
    low = [x for x in inc if x.get("low_ink")]
    if low:
        issues.append(issue("IMG_LOW_INK", "G7", "图片墨迹偏低（疑似缺字渲染或近空页，请目视）%d 个：%s" % (
            len(low), "；".join("%s（墨迹%s）" % (x["ref"], x.get("ink")) for x in low[:3])), "WARN"))
    bmiss = [x for x in img if not x["included"] and (not x["exists"] or x.get("blank"))]
    if bmiss:
        issues.append(issue("BACKSTAGE_IMG_BAD", "G7", "后台小节引用的图片缺失或空白 %d 个：%s" % (
            len(bmiss), "；".join(x["ref"] for x in bmiss[:3])), "WARN"))
    # 横幅
    zone = []
    lines = md.split("\n")
    first_h2 = next((i for i, ln in enumerate(lines) if ln.startswith("## ")), len(lines))
    known_titles = set(table) | bankinfo.stem | set(bankinfo.passthrough)
    for i, ln in enumerate(lines[:max(opts.banner_lines, 0)] + lines[opts.banner_lines:first_h2]):
        if ln.startswith("## "):
            continue
        s = re.sub(r"`([^`]*)`", lambda m: "" if (m.group(1) in known_titles or "候选（" in m.group(1)) else m.group(0), ln)
        if RE_BANNER.search(s) and not RE_BANNER_RETIRED.search(s) and not (RE_BANNER_EXEMPT.search(s) and not RE_BANNER_HARD.search(s)):
            zone.append(clip(ln, 70))
    rec["banner_lines"] = zone[:4]
    if zone and rec["exam_status"] == ACCEPTED:
        issues.append(issue("STALE_BANNER", "G9", "已验收卷文件开头仍有候选/隔离字样：%s" % " | ".join(zone[:2])))
    # 来源角色与页码
    nature = guide["stem_nature"]
    m = re.search(r"角色\s*([^/／，,）)\s]+)\s*[/／]\s*([A-Za-z_]+)", stem_body[:1500])
    role_in = "%s/%s" % (m.group(1), m.group(2)) if m else ""
    rec["source_role"] = "；".join(x for x in (nature, role_in, idx.get("role", "")) if x)
    pg_text = (stem["title"] if stem else "") + "\n" + nature + "\n" + "\n".join(stem_body.split("\n")[:10])
    pages = []
    for mm in re.finditer(r"(?<![A-Za-z0-9])[pP]\.?\s?0*(\d{1,3})(?:\s*[-–—]\s*[pP]?0*(\d{1,3}))?", pg_text):
        pages.append("p%s%s" % (mm.group(1), "-p%s" % mm.group(2) if mm.group(2) else ""))
    for mm in re.finditer(r"第\s*(\d{1,3})\s*(?:[-–—]\s*(\d{1,3})\s*)?页", pg_text):
        pages.append("p%s%s" % (mm.group(1), "-p%s" % mm.group(2) if mm.group(2) else ""))
    rec["source_pages"] = list(collections.OrderedDict((p, 1) for p in pages))[:6]
    rec["stem_source_ids"] = sorted(set(RE_SID.findall("\n".join(stem_body.split("\n")[:15]) + nature)))
    rec["stem_source_paths"] = [p for p in re.findall(r"`([^`\n]+\.(?:pdf|docx?|pptx?))`", "\n".join(stem_body.split("\n")[:15]))]
    # 证据等级（照原文件）
    ev = []
    if idx.get("extraction_status"):
        ev.append("questions.csv:" + idx["extraction_status"])
    for mm in RE_EVID.finditer(md):
        v = "%s:%s" % (mm.group(1), clip(mm.group(2).strip("`* "), 60))
        if v not in ev:
            ev.append(v)
        if len(ev) >= 6:
            break
    rec["evidence"] = ev
    dl = []
    for s in info:
        for ln in s["body"].split("\n"):
            if RE_DOUBT.search(ln):
                mm = RE_DOUBT.search(ln)
                dl.append("%s：%s" % (clip(s["title"], 12), clip(ln[max(0, mm.start() - 20):mm.end() + 30], 60)))
    rec["doubts_count"] = len(dl)
    rec["doubts"] = dl[:3]
    rec["sections"] = [{"title": s["title"], "role": s["role"], "basis": clip(s["basis"], 80), "lines": [s["hl"], s["el"]],
                        "sha256": sha_text(s["body"])} for s in info]
    fatal = [x for x in issues if x["gate"] in ("G3", "G4") and x["severity"] == "FAIL"]
    rec["compile_status"] = "fail" if fatal else ("ok_with_issues" if any(x["severity"] == "FAIL" for x in issues) else "ok")
    rec["issues"] = issues
    rec["_stem_body"] = stem_body
    rec["_clean_secs"] = [s for r in ROLE_ORDER for s in roles_secs.get(r, [])]
    return rec, info, md


def render_clean(rec, clean_path):
    link_base = os.path.relpath(os.path.join(BANK, os.path.dirname(rec["source_path"])), os.path.dirname(clean_path))
    hdr = collections.OrderedDict()
    hdr["bank_compile"] = VERSION
    hdr["note"] = "读者版：只含标准角色小节，正文逐字取自原小节；" + DISCLAIMER
    for k in ("question_id", "exam_id", "exam_status", "num", "type", "score", "score_stem", "subq", "options", "answer_key",
              "e1_status", "student_status", "source_role", "source_pages", "evidence", "compile_status"):
        hdr[k] = rec.get(k)
    hdr["issues"] = ["%s %s" % (x["code"], x["msg"]) for x in rec["issues"] if x["severity"] == "FAIL"]
    hdr["source_file"] = rec["source_path"]
    hdr["source_sha256"] = rec["file_sha256"]
    hdr["link_base"] = link_base
    hdr["link_base_abs"] = os.path.join(BANK, os.path.dirname(rec["source_path"]))
    hdr["sections"] = [{"role": s["role"], "title": s["title"], "lines": [s["hl"], s["el"]]} for s in rec["_clean_secs"]]
    out = ["---"]
    for k, v in hdr.items():
        out.append("%s: %s" % (k, json.dumps(v, ensure_ascii=False)))
    out.append("---")
    out.append("# %s" % rec["question_id"])
    out.append("")
    out.append("> 读者版（bank_compile）：正文逐字取自原题文件对应小节，标题行为“角色｜原标题”。相对链接以头部 link_base 为基准。"
               + DISCLAIMER)
    text = "\n".join(out) + "\n\n"
    for s in rec["_clean_secs"]:
        if not text.endswith("\n"):
            text += "\n"
        # 标题行改为“角色｜原标题”；正文原样拼接（原正文已以换行收尾时不再加空行，保证逐字相同）
        text += "## %s｜%s%s" % (ROLE_CN[s["role"]], s["title"], s["body"])
    if not text.endswith("\n"):
        text += "\n"
    return text


# ---------------------------------------------------------------- 编译全库
def list_exams(bank, only=None):
    ex = list(bank.tasks)
    for e in sorted(os.listdir(QDIR)) if os.path.isdir(QDIR) else []:
        if e not in bank.tasks and os.path.isdir(os.path.join(QDIR, e)) and e.startswith("BJ-"):
            ex.append(e)
    if only:
        miss = [e for e in only if e not in ex]
        if miss:
            raise SystemExit("卷号不在转换主清单或 questions/ 里：%s" % "、".join(miss))
        ex = [e for e in ex if e in only]
    return ex


def compile_all(bank, roles, bankinfo, opts, exams, write_dir=None):
    imgs = ImageChecker(os.path.join(write_dir, "_image_cache.json") if write_dir else None, opts.blank_ink, opts.blank_white)
    recs, per_exam = [], collections.OrderedDict()
    for e in exams:
        d = bank.exam_dir(e)
        files = []
        if os.path.isdir(d):
            pat = re.compile(r"^%s-Q(\d+)\.md$" % re.escape(e))
            files = sorted((f for f in os.listdir(d) if pat.match(f)), key=lambda f: int(pat.match(f).group(1)))
        per_exam[e] = {"dir": d, "files": files, "records": []}
        for f in files:
            try:
                rec, info, md = compile_question(e, f, os.path.join(d, f), bank, roles, bankinfo, imgs, opts)
            except Exception as ex:  # 单题异常不拖垮全库
                rec = collections.OrderedDict([("question_id", f[:-3]), ("exam_id", e), ("num", None),
                                               ("source_path", os.path.relpath(os.path.join(d, f), BANK)),
                                               ("compile_status", "fail"), ("retired", False),
                                               ("issues", [issue("PARSE_ERROR", "G3", "编译异常 %s: %s" % (type(ex).__name__, ex))])])
            recs.append(rec)
            per_exam[e]["records"].append(rec)
    imgs.save()
    return recs, per_exam


def exam_summary(bank, e, pe):
    t = bank.tasks.get(e, {})
    active = [r for r in pe["records"] if not r.get("retired")]
    retired = [r["question_id"] for r in pe["records"] if r.get("retired")]
    nums = sorted(r["num"] for r in active if r.get("num") is not None)
    srcs = t.get("sources") or {}
    roles = set(srcs)
    ch = [r for r in active if r.get("type") == "选择题"]
    nc = [r for r in active if r.get("type") != "选择题"]
    ex = bank.exams_csv.get(e, {})
    s = collections.OrderedDict()
    s["exam_id"] = e
    s["status"] = t.get("status", "（不在主清单）")
    s["year"], s["region"], s["stage"] = t.get("year"), t.get("region"), t.get("stage")
    s["school_year_exams_csv"] = ex.get("school_year", "")
    s["question_md_count"] = t.get("question_md_count")
    s["question_index_count"] = t.get("question_index_count")
    s["files"] = len(active)
    s["retired_files"] = retired
    s["numbers"] = nums
    s["contiguous"] = bool(nums) and nums == list(range(1, len(nums) + 1))
    s["compiled_ok"] = sum(1 for r in active if r.get("compile_status") in ("ok", "ok_with_issues"))
    s["compile_fail"] = sum(1 for r in active if r.get("compile_status") == "fail")
    s["clean_no_fail"] = sum(1 for r in active if r.get("compile_status") == "ok")
    s["source_layers"] = collections.OrderedDict([
        ("题面来源（原卷/教师版/混合载体）", bool(roles & {"原卷", "教师版", "混合载体", "教师版/转录题源"})),
        ("参考答案文件", "参考答案" in roles), ("评分材料（E1）", bool(roles & {"评分材料", "评分细则_分题切片", "阅卷总结"})),
        ("讲评", "讲评" in roles), ("登记角色", sorted(roles))])
    s["question_layers"] = collections.OrderedDict([
        ("题面", sum(1 for r in active if (r.get("layers") or {}).get("stem", {}).get("chars", 0) >= 20)),
        ("选择题有答案键", "%d/%d" % (sum(1 for r in ch if r.get("answer_key") and not r["answer_key"].startswith("冲突")), len(ch))),
        ("非选择题E1正文", "%d/%d" % (sum(1 for r in nc if r.get("e1_status") == "text"), len(nc))),
        ("非选择题E1例外/缺源", "%d/%d" % (sum(1 for r in nc if r.get("e1_status") in ("具名例外", "缺源")
                                               or str(r.get("e1_status", "")).startswith("卷级例外")), len(nc))),
        ("有解析E3", sum(1 for r in active if (r.get("layers") or {}).get("e3", {}).get("present"))),
        ("有讲评", sum(1 for r in active if (r.get("layers") or {}).get("commentary", {}).get("present"))),
        ("学生层有内容", sum(1 for r in active if r.get("student_status") == "有")),
        ("图表小节", sum(1 for r in active if (r.get("layers") or {}).get("figures", {}).get("present")))])
    s["exceptions"] = t.get("exceptions") or []
    s["source_limitations"] = len(t.get("source_limitations") or [])
    s["conversion_unresolved"] = len(t.get("conversion_unresolved") or [])
    s["has_shared_state"] = os.path.isfile(os.path.join(pe["dir"], "shared_conversion_state.json"))
    return s


CSV_FIELDS = [("question_id", "题键"), ("exam_id", "卷号"), ("exam_status", "卷状态"), ("num", "题号"), ("type", "题型"),
              ("type_declared", "题型_MD"), ("type_index", "题型_索引"), ("type_structure", "题型_结构"), ("score", "分值"),
              ("score_stem", "分值_题面"), ("subq", "小问"), ("L_stem", "题面字数"), ("stem_title", "题面小节"),
              ("stem_basis", "题面取用依据"), ("options", "选项"), ("L_answer", "答案字数"), ("answer_key", "答案键"),
              ("answer_source_roles", "答案来源角色"), ("L_e1", "E1字数"), ("e1_status", "E1状态"), ("L_e3", "解析字数"),
              ("L_commentary", "讲评字数"), ("L_student", "学生层字数"), ("student_status", "学生层状态"),
              ("L_figures", "图表字数"), ("img_refs", "图片引用数"), ("img_missing", "缺失图片"), ("img_blank", "空白图片"),
              ("img_paths", "图片路径"), ("source_role", "题面来源角色"), ("source_pages", "来源页码"),
              ("evidence", "证据等级（照原文件）"), ("doubts", "疑点"), ("file_sha256", "题文件SHA256"),
              ("compile_status", "编译状态"), ("issues", "问题清单"), ("clean_path", "读者版"), ("source_path", "原题文件")]


def csv_row(r):
    L = r.get("layers") or {}
    row = {}
    for k, _ in CSV_FIELDS:
        if k.startswith("L_"):
            x = L.get(k[2:], {})
            v = x.get("chars", 0) if x.get("present") else "无"
        elif k == "img_missing":
            v = sum(1 for i in r.get("images", []) if i["included"] and not i["exists"])
        elif k == "img_blank":
            v = sum(1 for i in r.get("images", []) if i["included"] and i.get("blank"))
        elif k == "img_paths":
            v = "；".join("%s%s" % (i["ref"], "〔缺〕" if not i["exists"] else ("〔空白〕" if i.get("blank") else ""))
                         for i in r.get("images", []) if i["included"])
        elif k == "issues":
            v = "；".join("[%s]%s" % (x["code"], x["msg"]) for x in r.get("issues", []) if x["severity"] == "FAIL")
        elif k == "doubts":
            v = ("%d处：" % r.get("doubts_count", 0) + " | ".join(r.get("doubts", []))) if r.get("doubts_count") else ""
        else:
            v = r.get(k, "")
            if isinstance(v, (list, tuple)):
                v = "；".join(str(x) for x in v)
        row[k] = v
    return row


def write_compile(out, recs, per_exam, bank, roles, bankinfo, seconds):
    os.makedirs(out, exist_ok=True)
    active = [r for r in recs if not r.get("retired")]
    with open(os.path.join(out, "catalog.jsonl"), "w", encoding="utf-8") as fj, \
            open(os.path.join(out, "catalog.csv"), "w", encoding="utf-8-sig", newline="") as fc:
        w = csv.DictWriter(fc, fieldnames=[k for k, _ in CSV_FIELDS])
        fc.write(",".join(cn for _, cn in CSV_FIELDS) + "\r\n")
        for r in recs:
            if r.get("retired"):
                continue
            if r.get("_clean_secs") is not None:
                cp = os.path.join(out, "clean", r["exam_id"], r["question_id"] + ".md")
                os.makedirs(os.path.dirname(cp), exist_ok=True)
                with open(cp, "w", encoding="utf-8") as fh:
                    fh.write(render_clean(r, cp))
                r["clean_path"] = os.path.relpath(cp, out)
            pub = collections.OrderedDict((k, v) for k, v in r.items() if not k.startswith("_"))
            fj.write(json.dumps(pub, ensure_ascii=False) + "\n")
            w.writerow(csv_row(r))
    ex_rows = []
    with open(os.path.join(out, "exams.jsonl"), "w", encoding="utf-8") as fh:
        for e, pe in per_exam.items():
            s = exam_summary(bank, e, pe)
            ex_rows.append(s)
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    # 报告
    n = len(active)
    ok = sum(1 for r in active if r.get("compile_status") in ("ok", "ok_with_issues"))
    amb = collections.defaultdict(list)
    unm = collections.defaultdict(list)
    codes = collections.Counter()
    for r in active:
        for x in r.get("issues", []):
            codes[(x["code"], x["gate"], x["severity"])] += 1
        for s in r.get("sections", []) or []:
            if s["role"] == "ambiguous":
                amb[s["title"]].append((r["question_id"], s["basis"]))
            elif s["role"] == "unmapped":
                unm[s["title"]].append(r["question_id"])
    L = ["# 题库编译报告（bank_compile）", "",
         "- 生成：%s；工具 %s；题库 `%s`" % (time.strftime("%Y-%m-%d %H:%M:%S"), VERSION, BANK),
         "- 转换主清单更新于 %s；角色表 %d 条标题（%s）" % (bank.manifest.get("updated_at", "?"), len(roles["headings"]),
                                                "、".join("%s %d" % (ROLE_CN.get(k, k), v) for k, v in sorted(
                                                    collections.Counter(x["role"] for x in roles["headings"].values()).items()))),
         "- 用时 %.1f 秒" % seconds, "",
         "> %s门禁结论见同目录 check.md（由 check 子命令生成）。" % DISCLAIMER, "",
         "## 总览", "",
         "- 卷 %d 套（主清单 %d 套）；有效题文件 %d 个，历史误分片兼容入口 %d 个（不计）" % (
             len(per_exam), len(bank.tasks), n, len(recs) - n),
         "- 编译成功 %d / %d（%.1f%%）；其中无任何 FAIL 问题 %d 题" % (ok, n, 100.0 * ok / (n or 1),
                                                       sum(1 for r in active if r.get("compile_status") == "ok")),
         "- 歧义小节涉及标题 %d 种、%d 处；未登记标题 %d 种、%d 处" % (
             len(amb), sum(len(v) for v in amb.values()), len(unm), sum(len(v) for v in unm.values())), ""]
    L += ["## 问题分布（按问题码）", "", "| 问题码 | 门 | 级别 | 题数 |", "|---|---|---|---|"]
    for (c, g, sv), k in sorted(codes.items(), key=lambda x: (x[0][1], -x[1])):
        L.append("| %s | %s | %s | %d |" % (c, g, sv, k))
    L += ["", "## 按卷", "", "| 卷 | 状态 | 题数 | 编译成功 | 失败 | 无FAIL | 选择题答案键 | 非选择题E1正文 |", "|---|---|---|---|---|---|---|---|"]
    for s in ex_rows:
        L.append("| %s | %s | %d | %d | %d | %d | %s | %s |" % (
            s["exam_id"], s["status"], s["files"], s["compiled_ok"], s["compile_fail"], s["clean_no_fail"],
            s["question_layers"]["选择题有答案键"], s["question_layers"]["非选择题E1正文"]))
    L += ["", "## 歧义小节（须拆分或改标题；不猜）", ""]
    if not amb:
        L.append("（无）")
    for t, v in sorted(amb.items(), key=lambda x: -len(x[1])):
        L.append("- 「%s」%d 处，如 %s；原因：%s" % (t, len(v), "、".join(q for q, _ in v[:3]), clip(v[0][1], 90)))
    L += ["", "## 未登记标题（bank.py 别名与角色表都没有）", ""]
    if not unm:
        L.append("（无）")
    for t, v in sorted(unm.items(), key=lambda x: -len(x[1])):
        L.append("- 「%s」%d 处，如 %s" % (t, len(v), "、".join(v[:3])))
    L += ["", "## 输出文件", "",
          "- `catalog.jsonl`：逐题一行（全部字段，含小节角色表、图片检查、问题清单）",
          "- `catalog.csv`：同上的表格版（UTF-8 BOM，Excel 直接打开）；角色列为字数，“无”表示没有该角色小节",
          "- `exams.jsonl`：逐卷状态、题数、题号、来源层与逐题层覆盖", "- `clean/<卷>/<题键>.md`：读者版",
          "- `report.md`：本报告", ""]
    with open(os.path.join(out, "report.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L))
    return ex_rows


# ---------------------------------------------------------------- 门禁
def stem_norm(t):
    keep = []
    for ln in t.split("\n"):
        s = ln.strip()
        if not s or RE_PROV.search(s) or (s.startswith(">") and RE_NOTE.search(s)):
            continue
        keep.append(s)
    x = re.sub(r"\]\([^)]*\)", "]", "".join(keep))
    x = "".join(RE_WORD.findall(x))
    return re.sub(r"^\d{1,2}", "", x)


def similarity_pairs(recs, k=8, df_cap=30, thr=0.8):
    sh = {}
    for r in recs:
        if r.get("retired") or not r.get("_stem_body"):
            continue
        s = stem_norm(r["_stem_body"])
        if len(s) < 30:
            continue
        sh[r["question_id"]] = (r["exam_id"], set(hash(s[i:i + k]) for i in range(len(s) - k + 1)))
    post = collections.defaultdict(list)
    for q, (_, S) in sh.items():
        for h in S:
            post[h].append(q)
    cnt = collections.Counter()
    for h, qs in post.items():
        if len(qs) < 2 or len(qs) > df_cap:
            continue
        qs = sorted(qs)
        for i in range(len(qs)):
            for j in range(i + 1, len(qs)):
                cnt[(qs[i], qs[j])] += 1
    out = []
    for (a, b), c in cnt.items():
        if c < 10:
            continue
        ea, sa = sh[a]
        eb, sb = sh[b]
        cont = c / float(min(len(sa), len(sb)))
        if cont >= thr:
            out.append((ea, a, eb, b, round(cont, 3)))
    return out


def school_year_from_label(label):
    m = re.search(r"(\d{4})\s*[—–\-~至]+\s*(\d{4})\s*学年", label or "")
    if m:
        return "%s-%s学年" % (m.group(1), m.group(2))
    m = re.search(r"(20\d{2})\s*[.．年]\s*(\d{1,2})", label or "")
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return "%d-%d学年" % ((y, y + 1) if mo >= 8 else (y - 1, y))
    return ""


GATE_HINT = {
    "G1": "转换主清单 tasks[].status 须为“已验收”或“重复登记已撤销”。",
    "G2": "题文件须 Q1…QN 连续，N = question_md_count = question_index_count；每题都在 questions.csv 登记；历史误分片兼容入口不计题数。",
    "G3": "把混合小节拆成单一角色的二级小节（题面/答案/E1/解析/讲评/学生/图表）；新标题在 heading_roles.json 登记并写依据；"
          "原样来源块里独有的行并入对应角色小节；E1 不要写在别的小节的 ### 子节里。",
    "G4": "读取指引“采用题面小节”须指向已核题面；不能是 OCR 候选、教师版含答案块或自述 raw OCR 的小节。",
    "G5": "题面小节只放材料、设问与选项；答案、解析、细则、答案文件标题移到对应小节。",
    "G6": "选择题题面 A—D 各出现一次；非选择题不能有 A—D 选项组；MD、questions.csv 与题面结构的题型一致。",
    "G7": "修正或补齐图片路径；空白或缺字的页图重新渲染。",
    "G8": "非选择题 E1 小节写细则原文；确无细则时写 N/A_with_basis（具名例外）或“缺源”并给依据；也可在主清单 exceptions 用同一词表写卷级例外。",
    "G9": "已验收卷文件头部删去“候选/隔离/未晋升”等过时横幅（保留的历史标签注明“已停用”）。",
    "G10": "主清单、exams.csv 学年与身份报告三者一致；高度相似的两卷判定是否同一场考试，重复的按“重复登记已撤销”处理。",
    "G11": "逐条裁定 rulings_todo.jsonl 的差异，写入 validation/retro_rulings.jsonl（结论：已修/原件笔误保留并标疑点/OCR 噪声/非差异，附依据页）。",
    "X1": "统一题面标题或给 bank.py 补别名，使 bank.py get 默认读法取得到题面；题目须在 questions.csv 登记。",
    "X2": "闭合代码围栏；嵌入的整份旧稿移出题文件；同名小节合并；读取指引指向存在的小节。",
    "X3": "选择题补答案键或写明缺源；非选择题补参考答案或 E1。",
    "X4": "heading_roles.json 与 bank.py 别名冲突时以 bank.py 为准改表。",
}


def gate(gid, name, fails, source="第五节", warns=None, skipped=None, note=""):
    st = "SKIP" if skipped else ("FAIL" if fails else "PASS")
    return collections.OrderedDict([("gate", gid), ("name", name), ("status", st), ("fail_count", len(fails)),
                                    ("source", source), ("note", note or (skipped or "")), ("how_to_fix", GATE_HINT.get(gid, "")),
                                    ("fails", fails), ("warns", warns or [])])


def q_items(recs, gate_id, exams_filter=None):
    fails, warns = [], []
    for r in recs:
        if r.get("retired"):
            continue
        if exams_filter and r["exam_id"] not in exams_filter:
            continue
        for x in r.get("issues", []):
            if x["gate"] != gate_id:
                continue
            item = "%s｜%s｜%s" % (r["question_id"], x["code"], x["msg"])
            (fails if x["severity"] == "FAIL" else warns).append(item)
    return fails, warns


def run_check(bank, roles, bankinfo, recs, per_exam, exams, opts):
    gates = []
    sel = set(exams)
    # G1
    f = ["%s｜状态「%s」" % (e, bank.tasks[e].get("status")) for e in exams if e in bank.tasks and bank.tasks[e].get("status") not in CLOSED]
    f += ["%s｜不在转换主清单" % e for e in exams if e not in bank.tasks]
    gates.append(gate("G1", "卷状态终结（撤销的重复登记除外）", f))
    # G2
    f, w = [], []
    for e in exams:
        t = bank.tasks.get(e, {})
        if t.get("status") == RETIRED:
            continue
        pe = per_exam[e]
        act = [r for r in pe["records"] if not r.get("retired")]
        nums = sorted(r["num"] for r in act if r.get("num") is not None)
        mdc, ixc = t.get("question_md_count"), t.get("question_index_count")
        if not os.path.isdir(pe["dir"]):
            f.append("%s｜题目录不存在：%s" % (e, pe["dir"]))
            continue
        if nums != list(range(1, len(nums) + 1)):
            gaps = sorted(set(range(1, (max(nums) if nums else 0) + 1)) - set(nums))
            f.append("%s｜题号不连续：现有 %s；缺 %s" % (e, ",".join(map(str, nums)), ",".join(map(str, gaps)) or "—"))
        if mdc is not None and len(nums) != mdc:
            f.append("%s｜题文件 %d 个 ≠ 主清单 question_md_count %s" % (e, len(nums), mdc))
        if mdc is not None and ixc is not None and mdc != ixc:
            f.append("%s｜主清单 question_md_count %s ≠ question_index_count %s" % (e, mdc, ixc))
        idx_q = set(q for q, rows in bank.qrows.items() if any(x.get("exam_id") == e for x in rows))
        files_q = set(r["question_id"] for r in act)
        retired_q = set(r["question_id"] for r in pe["records"] if r.get("retired"))
        lack = sorted(files_q - idx_q, key=lambda q: int(q.rsplit("Q", 1)[1]))
        extra = sorted(idx_q - files_q - retired_q)
        if lack:
            f.append("%s｜questions.csv 未登记 %d 题：%s" % (e, len(lack), ",".join(q.rsplit("-", 1)[1] for q in lack)))
        if extra:
            f.append("%s｜questions.csv 有题键但无题文件：%s" % (e, ",".join(extra[:8])))
        if retired_q:
            w.append("%s｜历史误分片兼容入口（不计题数）：%s" % (e, ",".join(sorted(retired_q))))
    gates.append(gate("G2", "题号连续、题数与主清单一致、索引登记齐全", f, warns=w))
    # G3/G4/G5/G6/G7/G8/G9
    for gid, name in (("G3", "每题编译成功、无歧义/未登记小节"), ("G4", "题面有内容且来源可采用"),
                      ("G5", "题面不夹答案"), ("G6", "选择题 A—D 齐全不重复、非选择题无选项组、题型标注一致"),
                      ("G7", "图片引用存在且非空白"), ("G8", "非选择题 E1 有正文或具名例外/缺源"),
                      ("G9", "已验收文件开头无候选/隔离横幅")):
        f, w = q_items(recs, gid, sel)
        note = ""
        if gid == "G9":
            note = "只查已验收卷；检查范围：一级标题、第一个二级标题前的前言与文件前 %d 行" % opts.banner_lines
        if gid == "G8":
            note = "选择题不要求 E1；认可的例外词：N/A_with_basis、N/A_objective、not_applicable、具名例外、“不适用+依据”；缺源词：缺源、source_not_provided 等"
        gates.append(gate(gid, name, f, warns=w, note=note))
    # G10 卷号冲突与重复登记
    f, w = [], []
    for e in bank.task_dups:
        f.append("%s｜在转换主清单里登记了多次" % e)
    for sid, es in sorted(bank.src_exams.items()):
        if len(es) > 1 and es & sel:
            f.append("%s｜同一来源登记在多个在用卷：%s" % (sid, "、".join(sorted(es))))
    act_ex = [e for e in bank.tasks if bank.tasks[e].get("status") != RETIRED]
    keyed = collections.defaultdict(list)
    for e in act_ex:
        row = bank.exams_csv.get(e)
        if not row:
            if e in sel:
                f.append("%s｜exams.csv 没有登记" % e)
            continue
        m = re.match(r"BJ-(\d{4})-", e)
        sy = (row.get("school_year") or "").strip()
        if m and sy and sy != "unknown":
            y = int(m.group(1))
            if sy != "%d-%d学年" % (y - 1, y) and e in sel:
                f.append("%s｜exams.csv 学年「%s」与卷号届别 %d（应为 %d-%d学年）不符" % (e, sy, y, y - 1, y))
            keyed[(sy, row.get("region"), row.get("stage"))].append(e)
        # exams.csv 的有无原卷/细则/答案标记与主清单登记的来源角色不符（只提示）
        roles_ = set((bank.tasks[e].get("sources") or {}).keys())
        flags = {"has_paper": bool(roles_ & {"原卷", "教师版", "混合载体", "教师版/转录题源"}),
                 "has_rubric": bool(roles_ & {"评分材料", "评分细则_分题切片", "阅卷总结"}),
                 "has_answer": bool(roles_ & {"参考答案", "教师版", "混合载体", "教师版/转录题源"})}
        bad = ["%s=%s（主清单%s）" % (k, row.get(k), "有" if v else "无") for k, v in flags.items()
               if row.get(k) in ("Y", "N") and (row.get(k) == "Y") != v]
        if bad and e in sel:
            w.append("%s｜exams.csv 来源标记与主清单不符：%s" % (e, "，".join(bad)))
    for k, es in keyed.items():
        if len(es) > 1 and set(es) & sel:
            f.append("%s｜exams.csv 同学年同区同考次登记了 %d 个卷号（%s %s %s）" % ("、".join(es), len(es), k[0], k[1], k[2]))
    for rp in sorted(glob.glob(os.path.join(RECEIPTS, "**", "identity_report*.json"), recursive=True)):
        rep = load_json(rp, {}) or {}
        rel = os.path.relpath(rp, os.path.dirname(D.PIPE))
        for it in rep.get("files", []) or []:
            sid = it.get("source_id_in_manifest")
            should = RE_EXAM_ID.findall(it.get("should_belong_to") or "")
            if not sid or not should:
                continue
            reg = bank.src_exams.get(sid, set())
            if not ((reg | {should[0]}) & sel):
                continue
            if should[0] not in reg and bank.tasks.get(should[0], {}).get("status") != RETIRED:
                f.append("%s｜身份报告称应属 %s，主清单登记在 %s（%s）" % (sid, should[0], "、".join(sorted(reg)) or "无", rel))
            elif reg - {should[0]}:
                f.append("%s｜身份报告称只属 %s，主清单另登记在 %s（%s）" % (sid, should[0], "、".join(sorted(reg - {should[0]})), rel))
        for it in rep.get("duplicate_or_missing", []) or []:
            for e in RE_EXAM_ID.findall(it.get("exam_id") or ""):
                if e in sel and bank.tasks.get(e, {}).get("status") not in (RETIRED, None):
                    f.append("%s｜身份报告判为重复登记，主清单状态仍是「%s」（%s）" % (e, bank.tasks[e].get("status"), rel))
        for it in rep.get("true_exams", []) or []:
            e = (RE_EXAM_ID.findall(it.get("recommended_exam_id") or "") or [None])[0]
            sy = school_year_from_label(it.get("true_exam_label") or "")
            if not e or not sy or e not in sel:
                continue
            row = bank.exams_csv.get(e, {})
            y = int(e.split("-")[1])
            if row.get("school_year") and row["school_year"] != "unknown" and row["school_year"] != sy:
                f.append("%s｜身份报告卷首「%s」推得 %s，exams.csv 写「%s」（%s）" % (
                    e, clip(it.get("true_exam_label"), 40), sy, row["school_year"], rel))
            if sy.split("-")[1][:4] != str(y):
                f.append("%s｜身份报告卷首推得 %s（%s届），与卷号年份 %d 不符（%s）" % (e, sy, sy.split("-")[1][:4], y, rel))
    for r in recs:
        if r.get("retired") or r["exam_id"] not in sel or r.get("compile_status") is None:
            continue
        sids = set(r.get("stem_source_ids") or [])
        for p in r.get("stem_source_paths") or []:
            sid = bank.path_sid.get(p) or bank.path_sid.get(os.path.basename(p))
            if sid:
                sids.add(sid)
        for sid in sids:
            reg = bank.src_exams.get(sid)
            if reg and r["exam_id"] not in reg:
                f.append("%s｜题面引用的来源 %s 在主清单登记于 %s，不属本卷" % (r["question_id"], sid, "、".join(sorted(reg))))
    pairs = similarity_pairs(recs)
    by_pair = collections.defaultdict(list)
    for ea, a, eb, b, c in pairs:
        if ea != eb:
            by_pair[tuple(sorted((ea, eb)))].append((a, b, c))
        elif ea in sel and c >= 0.9:
            w.append("%s｜同卷两题题面高度相似（疑串题）：%s ~ %s（包含度 %.2f）" % (ea, a, b, c))
    for (ea, eb), v in sorted(by_pair.items(), key=lambda x: -len(x[1])):
        if not ({ea, eb} & sel):
            continue
        qs = sorted(set((x[0], x[1]) for x in v))
        txt = "、".join("%s~%s" % (a.rsplit("-", 1)[1], b.rsplit("-", 1)[1]) for a, b in qs[:8])
        if len({a for a, _ in qs}) >= 3:
            f.append("%s × %s｜%d 组题面高度相似（包含度≥0.8）：%s" % (ea, eb, len(qs), txt))
        else:
            w.append("%s × %s｜%d 组题面高度相似：%s" % (ea, eb, len(qs), txt))
    gates.append(gate("G10", "卷号冲突与重复登记（主清单、exams.csv、身份报告、题面来源、跨卷题面相似度）", f, warns=w))
    # G11 回溯体检裁定
    gates.append(retro_gate(opts, recs, sel))
    # 附加门
    for gid, name in (("X1", "bank.py 默认读法取得到题面、题目已入 questions.csv（第四节第1条）"),
                      ("X2", "结构整洁：代码围栏闭合、无嵌入整份旧稿、无同名小节")):
        f, w = q_items(recs, gid, sel)
        gates.append(gate(gid, name, f, source="附加", warns=w))
    f, w = q_items(recs, "X3", sel)
    g = gate("X3", "答案层齐全（选择题有唯一答案键；非选择题有参考答案或 E1 正文）", (w if opts.strict else []), source="附加（提示）",
             warns=[] if opts.strict else w, note="默认只提示；--strict 时计入")
    gates.append(g)
    f = list(roles.get("_errors", []))
    exp = bankinfo.expected_roles()
    for t, rs in sorted(exp.items()):
        ent = roles["headings"].get(t)
        if ent and ent["role"] not in rs:
            f.append("「%s」bank.py 视为 %s，角色表写 %s" % (t, "/".join(sorted(x for x in rs if x)), ent["role"]))
    if bankinfo.error:
        f.append("bank.py 导入失败：%s" % bankinfo.error)
    for t in bankinfo.passthrough + bankinfo.unknown:
        if t not in roles["headings"] and t not in exp:
            f.append("「%s」是 bank.py 透传小节，角色表没有登记" % t)
    gates.append(gate("X4", "角色表与 bank.py 别名一致、角色表格式合法", f, source="附加（工具自检）"))
    return gates


def retro_gate(opts, recs, sel):
    if not opts.retro_summary:
        return gate("G11", "回溯体检高优先级差异全部有裁定", [], source="第五节（第3条）",
                    skipped="未给 --retro-summary（回溯体检 summary.json）")
    summ = load_json(opts.retro_summary, None)
    if summ is None:
        return gate("G11", "回溯体检高优先级差异全部有裁定", ["读不到 %s" % opts.retro_summary], source="第五节（第3条）")
    hi = list(summ.get("top") or [])
    if opts.retro_min_priority is not None:
        rj = os.path.join(os.path.dirname(opts.retro_summary), "retro_audit.jsonl")
        if os.path.isfile(rj):
            seen = set((d["exam"], d["qid"], d["bank_text"], d["source_text"]) for d in hi)
            for ln in open(rj, encoding="utf-8"):
                d = json.loads(ln)
                k = (d["exam"], d["qid"], d["bank_text"], d["source_text"])
                if d.get("priority", 0) >= opts.retro_min_priority and k not in seen:
                    seen.add(k)
                    hi.append(d)
    rulings = []
    rp = opts.rulings or DEFAULT_RULINGS
    if os.path.isfile(rp):
        for i, ln in enumerate(open(rp, encoding="utf-8"), 1):
            ln = ln.strip()
            if not ln:
                continue
            try:
                rulings.append(json.loads(ln))
            except Exception:
                rulings.append({"_bad": i})
    valid = {"已修", "原件笔误保留并标疑点", "OCR 噪声", "OCR噪声", "非差异"}
    f, w, todo = [], [], []
    bad = [r["_bad"] for r in rulings if "_bad" in r]
    if bad:
        f.append("裁定文件第 %s 行不是合法 JSON" % ",".join(map(str, bad[:10])))
    qfile = {r["question_id"]: os.path.join(BANK, r["source_path"]) for r in recs if r.get("source_path")}
    for d in hi:
        if sel and d["exam"] not in sel:
            continue
        did = hashlib.sha1(("%s|%s|%s|%s" % (d["exam"], d["qid"], d["bank_text"], d["source_text"])).encode("utf-8")).hexdigest()[:10]
        qn = d["qid"].rsplit("-", 1)[1]
        hit = None
        for r in rulings:
            if "_bad" in r:
                continue
            if r.get("diff_id") == did:
                hit = r
                break
            juan, ti, cha = str(r.get("卷", "")), str(r.get("题", "")), str(r.get("差异", ""))
            if not (juan and (juan in d["exam"] or d["exam"] in juan)):
                continue
            if not (ti in (d["qid"], qn, qn[1:]) or d["qid"].endswith("-" + ti)):
                continue
            if (d["bank_text"] and d["bank_text"] in cha) or (d["source_text"] and d["source_text"] in cha):
                hit = r
                break
        label = "%s｜%s→%s（%s 第%s页，优先级 %s）" % (d["qid"], d["bank_text"] or "∅", d["source_text"] or "∅",
                                                d.get("source_rel", ""), d.get("page"), d.get("priority"))
        if not hit:
            f.append("未裁定：" + label)
            todo.append(collections.OrderedDict([("diff_id", did), ("卷", d["exam"]), ("题", qn),
                                                 ("差异", "%s→%s" % (d["bank_text"] or "∅", d["source_text"] or "∅")),
                                                 ("结论", ""), ("依据页", "%s p%s" % (d.get("source_rel", ""), d.get("page"))),
                                                 ("题库位置", "questions/%s/%s.md:%s" % (d["exam"], d["qid"], d.get("md_line"))),
                                                 ("priority", d.get("priority"))]))
            continue
        concl = str(hit.get("结论", "")).strip()
        if concl not in valid:
            f.append("结论不合规（应为 已修/原件笔误保留并标疑点/OCR 噪声/非差异）：%s｜结论「%s」" % (label, concl))
            continue
        if not str(hit.get("依据页", "")).strip():
            w.append("缺依据页：" + label)
        if concl == "已修":
            ctx = re.sub(r"〔[^〕]*〕", "", d.get("bank_context") or "")
            ctx = re.sub(r"\s+", "", ctx)
            p = qfile.get(d["qid"])
            if len(ctx) >= 8 and p and os.path.isfile(p):
                cur = re.sub(r"\s+", "", open(p, encoding="utf-8").read())
                if ctx in cur:
                    f.append("裁定“已修”但题库仍是旧文：%s｜旧文「%s」" % (label, clip(ctx, 30)))
    g = gate("G11", "回溯体检高优先级差异全部有裁定", f, source="第五节（第3条）", warns=w,
             note="高优先级 = summary.json 的 top%s；裁定文件 %s（%d 条）" % (
                 "（另加 priority≥%s）" % opts.retro_min_priority if opts.retro_min_priority is not None else "",
                 rp, len(rulings)))
    g["_todo"] = todo
    return g


def write_check(out, gates, opts, seconds, scope):
    os.makedirs(out, exist_ok=True)
    todo = []
    for g in gates:
        todo += g.pop("_todo", []) if "_todo" in g else []
    overall = overall_status(gates, opts)
    doc = collections.OrderedDict([("generated_by", VERSION), ("generated_at", time.strftime("%Y-%m-%d %H:%M:%S")),
                                   ("scope", scope), ("overall", overall), ("seconds", round(seconds, 1)),
                                   ("disclaimer", DISCLAIMER + "门禁全绿也不等于内容已核验。"), ("gates", gates)])
    with open(os.path.join(out, "check.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    L = ["# 题库完成门禁（bank_compile check）", "", "- 生成：%s；工具 %s；范围：%s；用时 %.1f 秒" % (
        doc["generated_at"], VERSION, scope, seconds), "- **总结论：%s**" % overall, "", "> " + doc["disclaimer"], "",
         "| 门 | 内容 | 来源 | 结果 | FAIL 数 | 提示数 |", "|---|---|---|---|---|---|"]
    for g in gates:
        L.append("| %s | %s | %s | %s | %d | %d |" % (g["gate"], g["name"], g["source"], g["status"], g["fail_count"], len(g["warns"])))
    for g in gates:
        L += ["", "## %s %s：%s" % (g["gate"], g["name"], g["status"])]
        if g["note"]:
            L.append("> %s" % g["note"])
        if g["status"] == "FAIL" and g.get("how_to_fix"):
            L.append("")
            L.append("怎么修：%s" % g["how_to_fix"])
        if g["fails"]:
            L.append("")
            L.append("FAIL %d 条%s：" % (len(g["fails"]), "（下列前 %d 条，全文见 check.json）" % opts.md_limit if len(g["fails"]) > opts.md_limit else ""))
            L += ["- " + x for x in g["fails"][:opts.md_limit]]
        if g["warns"]:
            L.append("")
            L.append("提示 %d 条%s：" % (len(g["warns"]), "（前 %d 条）" % min(opts.md_limit, 40) if len(g["warns"]) > min(opts.md_limit, 40) else ""))
            L += ["- " + x for x in g["warns"][:min(opts.md_limit, 40)]]
    with open(os.path.join(out, "check.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    if todo:
        with open(os.path.join(out, "rulings_todo.jsonl"), "w", encoding="utf-8") as fh:
            for t in todo:
                fh.write(json.dumps(t, ensure_ascii=False) + "\n")
    return overall


def overall_status(gates, opts):
    fail = [g["gate"] for g in gates if g["status"] == "FAIL"]
    skip = [g["gate"] for g in gates if g["status"] == "SKIP"]
    if fail:
        return "未全绿：FAIL %s%s" % ("、".join(fail), "；SKIP %s" % "、".join(skip) if skip else "")
    if skip and not opts.allow_skip:
        return "未全绿：无 FAIL，但 %s 未评（SKIP）" % "、".join(skip)
    return "全绿" + ("（%s 按 --allow-skip 跳过）" % "、".join(skip) if skip else "")


# ---------------------------------------------------------------- 写入护栏
def guard_out(out):
    """题库 compiled/ 只对题库写权人放行；其余一律走 doc2md.guard_out_dir。"""
    if not out:
        raise SystemExit("没有输出目录：请给 --out-dir")
    o = os.path.realpath(os.path.abspath(out))
    roots = {D.ROOT, D.CANON_ROOT}
    compiled = [os.path.join(r, "DeepSeek_政治题库资料库_20260918", "compiled") for r in roots] + [COMPILED]
    if any(D.path_inside(o, c) for c in compiled):
        actor = os.environ.get("BANK_ACTOR", "")
        writer = (load_json(D.STATE, {}) or {}).get("shared_writer", "")
        if not (actor and writer and actor == writer):
            raise SystemExit("拒绝写入：%s 在题库 compiled/ 内，只有题库写权人（BANK_ACTOR=state.json 的 shared_writer）可写；"
                             "其他人请用 scratchpad。" % o)
        dirs, frozen = D._profile_dirs()
        for d, prof in frozen:
            if D.path_inside(o, d):
                from profile_lib import frozen_guard
                frozen_guard(prof, "写入 bank_compile 输出")
        return o
    return D.guard_out_dir(o)


# ---------------------------------------------------------------- 命令
def cmd_compile(a):
    t0 = time.time()
    out = guard_out(a.out_dir)
    roles = load_roles(a.roles)
    if roles["_errors"]:
        print("角色表有 %d 处不合法（照常编译，check 的 X4 会报）：%s" % (len(roles["_errors"]), "；".join(roles["_errors"][:3])))
    bank, bi = Bank(), BankInfo()
    exams = list_exams(bank, a.exam)
    os.makedirs(out, exist_ok=True)
    recs, per_exam = compile_all(bank, roles, bi, a, exams, out)
    ex_rows = write_compile(out, recs, per_exam, bank, roles, bi, time.time() - t0)
    act = [r for r in recs if not r.get("retired")]
    ok = sum(1 for r in act if r.get("compile_status") in ("ok", "ok_with_issues"))
    print(json.dumps({"输出": out, "卷": len(exams), "题": len(act), "编译成功": ok, "编译失败": len(act) - ok,
                      "无FAIL": sum(1 for r in act if r.get("compile_status") == "ok"),
                      "耗时秒": round(time.time() - t0, 1)}, ensure_ascii=False))
    print("摘要：编译完成，详见 %s/report.md。%s" % (out, DISCLAIMER))
    return 0


def cmd_check(a):
    t0 = time.time()
    out = guard_out(a.out_dir) if a.out_dir else None
    roles = load_roles(a.roles)
    bank, bi = Bank(), BankInfo()
    exams = list_exams(bank, a.exam)
    all_ex = list_exams(bank, None)
    # 相似度要看全库题面，所以全库都编译（不写读者版）
    recs, per_exam = compile_all(bank, roles, bi, a, all_ex, out)
    gates = run_check(bank, roles, bi, recs, per_exam, exams, a)
    scope = "全部 %d 卷" % len(exams) if not a.exam else "、".join(exams)
    if out:
        overall = write_check(out, gates, a, time.time() - t0, scope)
    else:
        for g in gates:
            g.pop("_todo", None)
        overall = overall_status(gates, a)
    if a.json:
        print(json.dumps({"overall": overall, "gates": [{k: g[k] for k in ("gate", "status", "fail_count")} for g in gates]},
                         ensure_ascii=False))
    else:
        print("门禁（%s）：%s" % (scope, overall))
        for g in gates:
            print("  %-4s %-4s FAIL %-5d %s" % (g["gate"], g["status"], g["fail_count"], g["name"]))
            for x in g["fails"][:a.show]:
                print("        - %s" % clip(x, 150))
        if out:
            print("明细：%s/check.md、check.json" % out)
        print(DISCLAIMER + "门禁全绿也不等于内容已核验。")
    return 0 if overall.startswith("全绿") else 1


def cmd_roles(a):
    out = guard_out(a.out_dir) if a.out_dir else None
    roles = load_roles(a.roles)
    bank, bi = Bank(), BankInfo()
    census = collections.OrderedDict()
    for e in list_exams(bank, None):
        d = bank.exam_dir(e)
        if not os.path.isdir(d):
            continue
        pat = re.compile(r"^%s-Q(\d+)\.md$" % re.escape(e))
        for f in sorted(os.listdir(d)):
            if not pat.match(f):
                continue
            secs, _ = split_sections(open(os.path.join(d, f), encoding="utf-8").read())
            for t, _, _, _ in secs:
                c = census.setdefault(t, {"count": 0, "example": "questions/%s/%s" % (e, f)})
                c["count"] += 1
    unm, amb = [], []
    for t, c in census.items():
        b = bi.role(t, None)
        ent = roles["headings"].get(t)
        c["role"] = b or (ent or {}).get("role") or "unmapped"
        c["by"] = "bank.py" if b else ("角色表" if ent else "无")
        if c["role"] == "unmapped":
            unm.append(t)
        elif c["role"] == "ambiguous":
            amb.append(t)
    print("二级标题 %d 种；未登记 %d 种，歧义 %d 种" % (len(census), len(unm), len(amb)))
    for t in unm:
        print("  未登记 %4d  %s  （%s）" % (census[t]["count"], t, census[t]["example"]))
    for t in amb:
        print("  歧义   %4d  %s" % (census[t]["count"], t))
    if a.emit_draft and unm:
        draft = {t: {"role": "ambiguous", "basis": "待填：看过 %s 的正文后写明角色依据" % census[t]["example"],
                     "example": census[t]["example"], "files": census[t]["count"]} for t in unm}
        print(json.dumps(draft, ensure_ascii=False, indent=1))
    if out:
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "roles_census.json"), "w", encoding="utf-8") as fh:
            json.dump(census, fh, ensure_ascii=False, indent=1)
    return 1 if (unm or amb) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="题库逐题 MD → 干净读者版 + 目录 + 完成门禁（只读题库）。" + DISCLAIMER,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--exam", action="append", help="只处理指定卷号（可重复给）；默认转换主清单全部卷")
        p.add_argument("--roles", default=DATA, help="角色表路径（默认 %(default)s）")
        p.add_argument("--banner-lines", type=int, default=12, help="横幅检查看文件前几行（另加第一个二级标题前的前言；默认 12）")
        p.add_argument("--blank-ink", type=float, default=0.002, help="墨迹（灰度<128）像素比例低于此值且近白比例够高即判空白（默认 0.002）")
        p.add_argument("--blank-white", type=float, default=0.95, help="判空白所需的近白（灰度≥246）像素比例（默认 0.95）")

    p = sub.add_parser("compile", help="编译读者版、目录与报告")
    p.add_argument("--out-dir", required=True, help="输出目录（不得在题库内；题库 compiled/ 只许写权人）")
    common(p)
    p.set_defaults(f=cmd_compile)
    p = sub.add_parser("check", help="完成门禁（第五节第1条逐项 PASS/FAIL）")
    p.add_argument("--out-dir", help="写 check.json/check.md/rulings_todo.jsonl 的目录；不给只打印")
    p.add_argument("--retro-summary", help="bank_retro_audit.py 的 summary.json；给了才评 G11")
    p.add_argument("--rulings", help="差异裁定 JSONL（默认 题库/validation/retro_rulings.jsonl）")
    p.add_argument("--retro-min-priority", type=float, help="另把 retro_audit.jsonl 里优先级≥此值的差异也算高优先级")
    p.add_argument("--strict", action="store_true", help="X3 答案层齐全也计入 FAIL")
    p.add_argument("--allow-skip", action="store_true", help="SKIP 的门不影响全绿与退出码")
    p.add_argument("--json", action="store_true", help="终端只打印一行 JSON 摘要")
    p.add_argument("--show", type=int, default=3, help="终端每门列出几条 FAIL（默认 3）")
    p.add_argument("--md-limit", type=int, default=200, help="check.md 每门最多列几条（默认 200；全文在 check.json）")
    common(p)
    p.set_defaults(f=cmd_check)
    p = sub.add_parser("roles", help="二级标题普查：列出未登记与歧义标题")
    p.add_argument("--out-dir", help="写 roles_census.json 的目录")
    p.add_argument("--emit-draft", action="store_true", help="打印未登记标题的角色表草稿（role 先填 ambiguous，须人工改判）")
    p.add_argument("--roles", default=DATA, help="角色表路径")
    p.set_defaults(f=cmd_roles)
    a = ap.parse_args(argv)
    if not getattr(a, "f", None):
        ap.print_help()
        return 2
    try:
        return a.f(a)
    except SystemExit as e:
        if isinstance(e.code, int):
            return e.code
        print(e)
        return 2
    except Exception as e:
        import traceback
        traceback.print_exc()
        print("异常（%s: %s）；产物可能不完整。" % (type(e).__name__, e))
        return 2


if __name__ == "__main__":
    sys.exit(main())
