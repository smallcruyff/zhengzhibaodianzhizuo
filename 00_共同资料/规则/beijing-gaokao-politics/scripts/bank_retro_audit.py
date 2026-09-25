#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bank_retro_audit.py — 已验收题库卷的回溯体检：默认读法的题面/答案 vs 原件文字层，逐题字符级比对。

用途
  audit（默认）：对转换主清单里状态为“已验收”的每一卷，取题库题级 MD 的默认读法（bank.py 的 adopted_stem
    与 E1/E3/学生层小节；bank.py 取不到题面时按读取指引标题前缀、再按标题启发式取并单独标注），分两道通道比：
    ① 文字层通道：逐行对齐到该卷原件的文字层（DOCX XML、PPTX 文本、PDF 文字层）；差异证据等级 machine_diff。
    ② OCR 双通道（2026-09-24 起默认开，--ocr off 关）：文字层对不上的行，改对该卷无可靠文字层的页
       （扫描、矢量描边字、方正/ClearScan 乱码、PPT 图片页、DOCX 嵌图）的 OCR 候选：优先复用题库
       evidence/<sid>/visual_transcript/pNNN.ocr.txt（页码=PDF 物理页），缺页用本机 ocr-vision 只写
       --out-dir/_ocr_cache；先按实测 OCR 混淆表归一（入/人、为→力/丢“为”、党/觉、已/己/巳……表见
       OCR_CONFUSIONS，可用 ocr-confusions 模式重统计），仍不同的列差异，证据等级 ocr_candidate。
       OCR 差异分高/低：高=第二读法（macOS Vision 按 200dpi 重识别，带行框与置信度）同样读成 OCR 那样、
       行置信 1.0、是 1—4 字的错漏增，且不像 OCR 误读；像 OCR 误读的判据（2026-09-24 按裁图校准）：光栅扫描页上
       错字两边字形相关≥0.57、或题库多字而 OCR 少字；清晰页（矢量描边字、嵌图、PPT 页图）上字形相关≥0.8 且 OCR
       读法在题库其他卷默认读法里一处没有。其余（标点、题号、长段、表格行、图表读序、题库自加标注、学生手写、
       低置信、第二读法与题库一致……）为低。每条 OCR 差异给原页裁图（红框为按字数估计的位置），并按卷拼成
       “差异拼图”（每张 --sheet-size 条，默认 24，带编号与题库/OCR 两边文字），供模型或人一次看一批。
    差异分类：错字、漏字、增字、标点、题号、选项。只输出报告，不改题库。
  eval：把 doc2md --exam 的候选目录与题库已验收 MD 比对，报一致率（召回口径，未定位部分单列）与拆题率。
  ocr-confusions：用“有可靠文字层且题库有 OCR 的页”（原生字 vs OCR）和“扫描页 OCR vs 题库默认题面”
    统计真实 OCR 混淆对，写 ocr_confusions.json，供更新 OCR_CONFUSIONS（不改题库）。

用法（必须用 /usr/bin/python3〔3.9〕，依赖 PyMuPDF、python-pptx、Pillow；OCR 通道另用 ~/.local/bin/ocr-vision，
      第二读法用系统 swiftc 现场编译一个 60 行 Vision 小工具到 --out-dir/_ocr_cache/_bin，编译失败则自动降级）
  python3 bank_retro_audit.py [--exam BJ-2026-BJ-GAOKAO ...] --out-dir DIR [--crops 30] [--top 20]
        [--ocr auto|off] [--no-run-ocr] [--second-read auto|off] [--sheet-size 24]
  python3 bank_retro_audit.py eval --exam BJ-2025-DC-ERMO --candidate-dir <doc2md 输出根> --out-dir DIR
  python3 bank_retro_audit.py ocr-confusions --out-dir DIR
  作为库：from bank_retro_audit import audit_exam, reading_lines, eval_exam

输出（--out-dir；不给时取 $DOC2MD_OUT/retro_audit 或 $DOC2MD_OUT/eval，两者都没有则拒绝运行）
  retro_audit.jsonl 逐条差异（channel=text_layer|ocr）；summary.json 每卷统计、未审全卷名单与 TOP 清单；
  top.md 便于人工逐条看（名次同时给去重后/去重前两种口径，题库文件行号 1 起）；crops/ TOP 差异原页裁图；
  ocr_diffs.md OCR 高等级差异清单；ocr_crops/<卷>/ 每条 OCR 差异裁图；sheets/<卷>/high_NN.png、low_NN.png
  差异拼图与 sheets/<卷>/index.jsonl（拼图编号→差异）；_ocr_cache/ OCR 文字与行框缓存（重跑复用，渲染页用完即删）。
  分母口径（2026-09-24）：默认读法里对不上任何原件、且属于题库自注（N/A、来源/状态/核验说明、E1/E3 标注、
  跨≥3题重复的样板句）、页眉页脚、图示描述、答案键行或学生手写层的行，单列 excluded_*，不计入“应审”分母；
  其余对不上的行计入分母并算“未审”。每卷报题面实际被审的题数（文字层或 OCR 任一定位≥50%）与字符比例
  （audit_share；旧口径 located_share 仍保留）。应审字符定位不到 50% 或题面审到不足一半的卷写进
  not_auditable 并说明原因。上下文窗口的截断处标〔前略〕〔后略〕，拼图文字截断处标“…”。

证据等级
  文字层差异是 machine_diff，OCR 通道差异是 ocr_candidate；两者都不是“已核实错误”，不得标成已核验；
  题库“已验收”也不等于“主代理已核原页”。需要人工看原页（或拼图）裁定，修正走题库写权人（Luna）的
  controller_multi_fix.py。门全过只说明机械层没有发现回退。

只读承诺
  题库、原件、转换主清单、书稿一律只读；导入 bank.py 时禁止写 .pyc；输出目录受 doc2md.guard_out_dir 护栏约束。
  OCR、渲染、抽图、编译都只写 --out-dir 下的 _ocr_cache/（ocr-vision 只读原件与题库页图）。

退出码
  0 完成；2 参数错误、依赖缺失、拒绝写入或异常。（差异条数不影响退出码：这是报告工具，不是门禁。）
"""
import argparse
import collections
import glob
import hashlib
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import doc2md as D  # noqa: E402

BANK_Q = os.path.join(D.BANK, "questions")
# 输出目录：--out-dir，或环境变量 DOC2MD_OUT 下的 retro_audit/、eval/；都没有则拒绝运行
DEFAULT_OUT = os.path.join(D.DEFAULT_OUT, "retro_audit") if D.DEFAULT_OUT else None

PAPER_ROLES = {"原卷", "教师版", "混合载体", "教师版/转录题源"}
E1_ROLES = {"评分材料", "评分细则_分题切片", "阅卷总结"}
E3_ROLES = {"参考答案"}
UNDECIDED = {"分题切片_待定"}
ROLE_PREF = {"stem": PAPER_ROLES | {"可读派生见证"}, "e1": E1_ROLES | UNDECIDED,
             "e3": E3_ROLES | PAPER_ROLES | E1_ROLES | UNDECIDED,
             "student": E1_ROLES | UNDECIDED | {"讲评", "试题分析材料"}}
W_ROLE = {"stem": 3.0, "e1": 3.0, "e3": 2.5, "student": 1.0}
W_CAT = {"错字": 3.0, "漏字": 3.0, "选项": 3.0, "增字": 2.0, "题号": 2.0, "标点": 1.0}
TIER_W = {"native": 1.0, "derived_witness": 0.8, "legacy_converted": 0.5, "ocr_layer": 0.3, "garbled_font": 0.2}

RE_META_TITLE = re.compile(r"身份|读取指引|配对|来源定位|来源页|来源角色|来源覆盖|质量|证据|覆盖|审计|验收|工程|状态|修复记录|限制|"
                           r"边界|独立复核|本轮|结论|页/段|说明|定性|资产|页图|图像|原页|OCR|候选|变体|原样保留，不作为")
# bank.py 别名表之外、题库实际在用的题面标题（2026-09-23 对 50 卷普查）：题面…/题目原文…/原题（E0…）/原题文字…/
# 原题完整候选文字…/原卷完整题面…/E0教师版有界题面…/视觉核定完整题面…/来源角色：ORIGINAL_QUESTION…
RE_STEM_TITLE = re.compile(r"^(题面|题目原文|原卷题面|原卷完整题面|原题（|原题文字|原题完整|原题题面|原题保真|原题转录|原卷逐字|"
                           r"原卷视觉核对结构化转写|已核题面|视觉核定完整题面|题库缓存转写|E0.*题面|来源角色[：:]\s*ORIGINAL_QUESTION)")
# 题面旁的结构/页图/资产小节不是题面文字
RE_STEM_EXCLUDE = re.compile(r"页图|原页图|图片|图像|图表|资产|证据|版面|结构|OCR|候选（未|(?<!不)含答案|须回原卷")
RE_E1_TITLE = re.compile(r"E1|正式评分|评分细则|阅卷标准")
RE_E3_TITLE = re.compile(r"E3|参考答案|答案")
RE_STUDENT_TITLE = re.compile(r"学生")
RE_SKIP_LINE = re.compile(r"^(```|\|?\s*:?-{3,}|!\[|<!--)|sha256|SHA-256|\.png|\.pdf|\.docx|\.pptx|evidence/|assets/|"
                          r"^- ?(来源|证据|独立审计|依据|页码|原页|状态|说明|注)[：:\s]|^来源[：:]|^\*\*(核验依据|原图依据|执行者|本批|改正内容|父稿)")
RE_NOTE_QUOTE = re.compile(r"核验依据|原图依据|执行者|本批|改正内容|父稿|本节|不得|来源|证据|注：|复核|核对|转写|原页|页图|OCR|候选|"
                           r"E1|E3|评分依据|不等于|原样|角色")
RE_BANK_PREFIX = re.compile(r"^(?:P\d{2,4}\s*[:：]\s*|\d{1,3}\.\s+|\[DOCX\s*P\d+\]\s*|Row\s*\d+\s*[:：]\s*)")
RE_BOX_LABEL = re.compile(r"^(资料卡|知识链接|相关链接|背景资料|小贴士|链接|阅读卡|知识卡|名词解释|探究与分享)$")
PUNCT = set("，。、；：？！“”‘’（）《》【】—…·,.;:?!\"'()[]<>-~/%+=　 ")

# 启发式标题的角色：先去掉否定短语（“不是正式评分细则”“非E1”“不得据此拆分E1”……），再按显式层标记判定。
# 旧逻辑按“评分细则”四字先判 E1，把“参考答案与解析（E3，不是正式评分细则）”“内附详解（…非正式评分细则）”
# 判成 E1，只许对评分材料，教师版里的答案/详解因此整段对不上（2020 高考、2023 丰台一模等）。
RE_TITLE_NEG = re.compile(r"(?:不是|非|不得视为|不得当作|不得作为|不作为|不等同于?|不得据此拆分|不能证明|不提升为|不升格为|与)\s*"
                          r"(?:主观)?(?:正式)?(?:逐点|题级)?(?:评分细则|评分材料|评分依据|细则|E1|评分)[^，；、（）()]*")


def title_role(ti):
    """启发式小节标题 → e1/e3/student/None（bank.py 别名表之外的标题才用）。"""
    if RE_STUDENT_TITLE.search(ti):
        return "student"
    t = RE_TITLE_NEG.sub("", ti)
    if re.search(r"来源块|候选", t) and not re.search(r"E[13]", t):
        return None
    # 同时像答案层又像细则层的（“参考答案与正式评分层”）按 e3：e3 可对的原件角色包含 e1 的全部
    if "E3" in t or re.search(r"参考答案|答案|详解|解析|等级描述", t):
        return "e3"
    if "E1" in t or re.search(r"正式评分|评分细则|阅卷标准|评分标准|评标", t):
        return "e1"
    return None


# 对不上任何原件的行里，哪些是题库自己写的说明（不计入“应审”分母，单列 excluded_*）。只对“两道通道都对不上”的行用。
RE_NOTE_LINE = re.compile(
    r"N/?A|缺源|未提供|未找到|未发现|未见|不适用|无独立|没有独立|来源[：:为页]|来源角色|来源定位|证据等级|状态[：:]|"
    r"裁定|登记|核对|核验|复核|校对|转写|原页|原图|页图|渲染|OCR|候选|本题未|本题没有|本卷|本轮|本节|本候选|本文件|"
    r"见下方|见上方|详见|原文如此|原样保留|分层|层级|角色|载体|slide|幻灯片|\bp\d{2,3}\b|P\d{3}|(?<![A-Za-z])E[013](?![0-9])|"
    r"Luna|DeepSeek|Codex|Claude|答案键|答案登记|机器值|`|sha256|\.md\b|\.json|\.pdf|\.pptx|\.docx|evidence/|assets/|sources/|"
    r"不得当作|不得视为|不得据|不作为|不是正式|非正式|不等于|不等同|不冒充|不补造|不推算|推算|不另行|不从|不把|不能证明|"
    r"读取指引|题库|缓存|独立回执|回执|身份|映射|对应关系|绑定|切片|定位|截断|已截|页码|物理页")
RE_FIG_LINE = re.compile(r"图|框|箭头|底色|颜色|红色|蓝色|黄色|绿色|紫色|橙色|灰色|黑色|高亮|下划线|加粗|左侧|右侧|上方|下方|"
                         r"左上|右上|左下|右下|居中|虚线|实线|柱状|折线|饼状|坐标|纵轴|横轴|图例|刻度|示意|版式|排版|竖排|"
                         r"横排|圆角|矩形|标题栏|气泡|表头|单元格|行列|手写|字迹|笔迹|涂改|批注|圈划|√|×|✓")
RE_ANSWER_KEY_LINE = re.compile(r"^(?:\d{1,2}\s*[．.、:：]?\s*)?(?:【?(?:标准|参考|官方)?答案】?|答案键|客观答案|选择题答案)"
                                r"\s*[：:]?\s*\**[A-D]\**|^[\d\s．.、A-D|\-:：]{6,}$")


def _import_bank():
    sys.path.insert(0, os.path.join(D.BANK, "scripts"))
    try:
        import bank  # noqa: F401
        return bank
    except Exception:
        return None


BANKPY = _import_bank()


def sha_text(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- 题库默认读法
def reading_sections(md, qid=None):
    """返回 [(role, title, body, basis)]：bank.py 默认读法能取到的题面/E1/E3/学生层；取不到题面时启发式补一节并标注。"""
    out = []
    if BANKPY is not None:
        secs = BANKPY.split_md(md)
        by = dict(secs)
        t, body = BANKPY.adopted_stem(md)
        used = set()
        if t:
            out.append(("stem", t, body, "bank_default"))
            used.add(t)
        else:
            fb = next((x for x in BANKPY.DEFAULT_PASSTHROUGH_SECTIONS if x in by), None)
            heur = [ti for ti, _ in secs if is_stem_title(ti)]
            if not heur:
                # 读取指引点名的题面小节标题与实际标题只差括注（如指引写“原卷 OCR 候选（未逐字对照…）”，
                # 实际是“原卷 OCR 候选（已对照原页修复题界）”）：按括注前的前缀认，单独标注读取依据
                g = re.search(r"^-\s*采用题面小节\s*[:：]\s*`?([^`\n]+?)`?\s*$", by.get("读取指引（机器可读）", ""), re.M)
                pre = re.split(r"[（(]", g.group(1))[0].strip() if g and g.group(1) not in by else ""
                gp = [ti for ti, _ in secs if pre and len(pre) >= 3 and ti.startswith(pre) and not RE_STEM_EXCLUDE.search(
                    re.sub(r"OCR|候选", "", ti))] if pre else []
                for ti in gp:
                    out.append(("stem", ti, by[ti], "guide_title_prefix"))
                    used.add(ti)
                if gp:
                    fb = None
            for ti in heur:
                # bank.py 取不到题面：按标题启发式取全部题面小节（同题多页/多版本都审），并单独标注读取依据
                out.append(("stem", ti, by[ti], "heuristic_no_default_stem"))
                used.add(ti)
            if not heur and fb:
                out.append(("stem", fb, by[fb], "bank_default_passthrough"))
                used.add(fb)
        for role in ("e1", "e3", "student"):
            for ti, bo in BANKPY.role_sections(by, role, qid):
                if ti not in used:
                    out.append((role, ti, bo, "bank_role_alias"))
                    used.add(ti)
        for ti, bo in secs:
            if ti in used or ti in BANKPY.DEFAULT_PASSTHROUGH_SECTIONS:
                continue
            if "OCR" in ti or "候选" in ti or "变体" in ti:
                continue
            role = title_role(ti)
            if role is None and ti in getattr(BANKPY, "PASSTHROUGH_SECTIONS", ()) and re.search(r"答案|评分", ti):
                role = "e3" if "答案" in ti else "e1"
            if role and not (RE_META_TITLE.search(ti) and role not in ("e1", "e3", "student")):
                out.append((role, ti, bo, "heuristic_title"))
                used.add(ti)
    return out


def is_stem_title(ti):
    return bool(RE_STEM_TITLE.match(ti)) and not RE_STEM_EXCLUDE.search(ti)


def reading_lines(md, qid=None):
    """逐行拆默认读法（去元数据与注释行），返回 [dict(role,title,basis,raw,disp,canon,md_line)]。"""
    lines_all = md.splitlines()
    pos = {}
    for i, l in enumerate(lines_all):
        m = re.match(r"^## (.+)$", l)
        if m:
            pos.setdefault(m.group(1).strip(), i + 1)
    out = []
    for role, title, body, basis in reading_sections(md, qid):
        base = pos.get(title, 0)
        in_code = False
        sub = ""
        for k, raw in enumerate(body.splitlines()):
            s = raw.strip()
            if s.startswith("```"):
                in_code = not in_code
                continue
            if s.startswith("###"):
                sub = s
                continue
            if not s or s.startswith("#"):
                continue
            if RE_SKIP_LINE.search(s):
                continue
            if s.startswith(">"):
                q = s.lstrip("> ").strip()
                if not q or RE_NOTE_QUOTE.search(q[:30]):
                    continue
                s = q
            s = re.sub(r"^[-*]\s+", "", s)
            # 题库自加的段落编号（“P007: ”“25. ”）不是原文；给一个去前缀的备选读法，对齐时取更好的
            m = RE_BANK_PREFIX.match(s)
            alt_prefix = m.group(0) if m else None
            for ci, chunk in enumerate(_chunks(s)):
                d = D.norm_display(chunk)
                if len(d) < 4:
                    continue
                row = {"role": role, "title": title, "basis": basis, "raw": D.clip(chunk, 400), "disp": d,
                       "canon": D.canon(d), "md_line": base + k,
                       "ocr_sub": bool(re.search(r"ocr_candidate|OCR", sub))}
                if alt_prefix and ci == 0:
                    d2 = D.norm_display(chunk[len(alt_prefix):])
                    if len(d2) >= 4:
                        row["alt"] = {"disp": d2, "canon": D.canon(d2), "prefix": alt_prefix.strip(),
                                      "plen": len(D.norm_display(alt_prefix))}
                out.append(row)
    return out


def _chunks(s, limit=260):
    if len(s) <= limit:
        return [s]
    parts, cur = [], ""
    for piece in re.split(r"(?<=[。；！？])", s):
        if len(cur) + len(piece) > limit and cur:
            parts.append(cur)
            cur = piece
        else:
            cur += piece
    if cur:
        parts.append(cur)
    return parts


# ---------------------------------------------------------------- 原件文字层语料
def tier_of(fine, block):
    if block.get("ocr"):
        return "ocr_layer" if fine in D.OCR_LAYER_CLASSES else None
    if fine in ("symbol_garbled", "garbled_text_layer"):
        return "garbled_font"
    if fine == "legacy_converted":
        return "legacy_converted"
    if fine in D.DIRECT_CLASSES:
        return "native"
    return None


def source_index(exam_id, man=None, work_dir=None):
    """一卷全部原件的文字层 → TextIndex（外部 OCR、扫描页不入）。返回 (task, index, sources_info)。
    doc/rtf 的 textutil 转换副本只写 work_dir（调用方放在 --out-dir 内并负责清理）；不给时用自动清理的临时目录。"""
    task, srcs = D.exam_sources(exam_id, man)
    idx = D.TextIndex()
    infos = []
    for s in srcs:
        if not s["path"]:
            infos.append({"rel_path": s["rel_path"], "role": s["role_key"], "missing": True})
            continue
        try:
            blocks, flags, pages, info = D.extract_source(
                s["path"], s.get("format"), s.get("source_id"), asset_root=None, ocr_dirs=[], render_dpi=0,
                work_dir=os.path.join(work_dir, s.get("source_id") or "src") if work_dir else None)
        except Exception as e:
            infos.append({"rel_path": s["rel_path"], "role": s["role_key"], "error": D.clip(repr(e), 300)})
            continue
        info.update(role=s["role_key"], rel_path=s["rel_path"])
        infos.append(info)
        fine_of = {p["page"]: p["fine_class"] for p in pages}
        info["page_fine"] = fine_of  # OCR 通道按页选单元用（页码=PDF 物理页/PPT 张号/DOCX 估算页）
        n_added = 0
        for b in blocks:
            if b["kind"] not in ("p", "textbox", "table", "notes"):
                continue
            fine = fine_of.get(b.get("page"), b.get("class"))
            tier = tier_of(fine, b)
            if tier is None:
                continue
            if tier == "native" and s["role_key"] == "可读派生见证":
                tier = "derived_witness"  # 题库自制的可读副本（如 LibreOffice 重排），不是原件本身
            lab = {"sid": info["source_id"], "role": s["role_key"], "rel": s["rel_path"], "page": b.get("page"),
                   "fine": fine, "tier": tier, "bbox": b.get("bbox"), "fmt": info["format"], "path": s["path"],
                   "kind": b["kind"]}
            idx.add_nosep(b.get("text", ""), lab)
            n_added += 1
        idx.sep()
        info["blocks_indexed"] = n_added
    idx.build()
    return task, idx, infos


def _patch_textindex():
    """给 doc2md.TextIndex 加“同源不分隔”的追加方式（块间可跨行对齐，来源之间仍隔开）。"""
    def add_nosep(self, text, label):
        d = D.norm_display(text)
        if not d:
            return
        c = D.canon(d)
        self.segs.append((self._len, self._len + len(c), label))
        self.disp.append(d)
        self.canon_s.append(c)
        self._len += len(c)
        self.grams = None

    def sep(self):
        if self.disp and self.disp[-1] != "\x00":
            self.disp.append("\x00")
            self.canon_s.append("\x00")
            self._len += 1
    D.TextIndex.add_nosep = add_nosep
    D.TextIndex.sep = sep


_patch_textindex()


# ---------------------------------------------------------------- 差异分类
def _is_punct(s):
    s = D.canon(s)
    return bool(s) and all(c in PUNCT for c in s)


def classify(a, b, line_disp, a0):
    """a=题库字，b=原件字（均为去空白后的显示形）。"""
    seg = a + b
    if re.match(r"^\d{1,2}[.．、]", line_disp) and a0 <= 2 and re.search(r"\d", seg):
        return "题号"
    if re.match(r"^[A-D][.．、]", line_disp) and (a0 <= 1 or re.search(r"[①②③④⑤⑥A-D]", seg)) and \
            re.fullmatch(r"[①②③④⑤⑥A-D.．、]+", seg or "x"):
        return "选项"
    if _is_punct(a) and _is_punct(b) or (not a and _is_punct(b)) or (not b and _is_punct(a)):
        return "标点"
    if a and b:
        return "错字"
    if b and not a:
        return "漏字"
    return "增字"


def subtype(a, b):
    seg = a + b
    if re.search(r"\d", seg):
        return "digit"
    if re.search(r"[①-⑳]", seg):
        return "circled"
    if re.search(r"[A-Za-z]", seg):
        return "latin"
    if D.CJK.search(seg):
        return "cjk"
    return "other"


def benign_flags(a, b, lab, line):
    f = []
    if D.BAD.search(a + b):
        f.append("source_replacement_char")
    if lab and lab.get("tier") != "native":
        f.append("tier_" + lab.get("tier", "?"))
    if re.fullmatch("[□■▲△○●◆◇☆★✓✗•·▶►◀→←↑↓⇒➢❖✔✘◎※\uf000-\uf0ff]+", (a + b) or "x"):
        f.append("decor_symbol")
    if a and re.search(r"原卷|原页|页脚|页眉|要点框|框[：:]|图[：:]|表[：:]|【表|【图|示意|转写|（图|〔|注：|DOCX|PDF|P\d{2}", a):
        f.append("model_annotation_in_bank")
    if lab and lab.get("kind") == "table":
        f.append("source_table_order")
    if not a and re.fullmatch(r"\d+", b or "x"):
        f.append("source_stray_digit")
    if re.search(r"\d\s*分", a + b) and re.fullmatch(r"[，。；、,.;:：\s]*[（(]?\s*\d+\s*分\s*[）)]?[，。；、,.;:：\s]*", (b or a)):
        f.append("score_mark_only")  # 只差“（1分）”这类分值标注：常是参考答案与细则两份文件本来不同
    if line.get("raw", "").lstrip().startswith("|") or "<td" in line.get("raw", ""):
        f.append("table_row")
    if max(len(a), len(b)) > 12:
        f.append("long_span")
    return f


# ---------------------------------------------------------------- 单卷体检
KNOWN_ROLES = PAPER_ROLES | E1_ROLES | E3_ROLES | {"讲评"}


def _best_align(idx, ln, min_ratio):
    """只在同角色原件里对齐（题面→原卷/教师版；E1→评分材料；E3→答案/卷内答案/评分材料），
    角色未定的来源（分题切片_待定、辅助材料等）两边都可用。跨角色命中（如细则复述题干）不算。"""
    n = ln["canon"]
    pref = ROLE_PREF.get(ln["role"], set())
    ok = lambda lab: lab is not None and (lab.get("role") in pref or bool(pref & lab.get("roles", set())))
    al = idx.align(n, allow=ok)
    if al is not None and al["ops"]:
        # 同角色有多份原件（如同卷 DOCX 与 PDF 两个版本）时，逐份再对一次，取最吻合的一份，避免版本差异冒充题库错误
        sids = {l.get("sid") for _, _, l in idx.segs if ok(l)}
        if len(sids) > 1:
            for sd in sids:
                al2 = idx.align(n, allow=lambda lab, sd=sd: ok(lab) and lab.get("sid") == sd)
                if al2 is not None and (al2["ratio"] > al["ratio"] or (al2["ratio"] == al["ratio"] and
                                                                     len(al2["ops"]) < len(al["ops"]))):
                    al = al2
    return al


def _ok(al, min_ratio):
    return al is not None and al["ratio"] >= min_ratio


def _text_layer_diffs(exam_id, qid, ln, al, idx, seg_bounds, nxt_disp, st):
    """文字层通道的逐条差异（分类、降权标记、优先级与 2026-09-23 版相同）。"""
    diffs = []
    lab = idx.label_at(al["start"] + 1)
    for tag, a0, a1, b0, b1 in al["ops"]:
        a = ln["disp"][a0:a1]
        b = idx.D[b0:b1].replace("\x00", "")
        if not a and not b:
            continue
        labb = idx.label_at(b0) if b1 > b0 else lab
        cat = classify(a, b, ln["disp"], a0)
        if (labb or {}).get("tier") == "garbled_font" and re.fullmatch(r"[\W_A-Za-z0-9]*", a + b):
            st["suppressed_garbled_symbol"] += 1  # 方正类字体映射错：标点/数字错码是原件文字层的问题
            continue
        flags = benign_flags(a, b, labb, ln)
        if a0 == 0 and re.fullmatch(r"(P\d*[:：]?|\d{1,3}\.)", a):
            flags.append("bank_line_prefix")
        if a0 <= 3 and re.fullmatch(r"[\d（）()．.、分\s]*", a + b) and cat != "题号":
            flags.append("line_head_label")  # 题号类差异不叠这个降权（植入的题号错误原先只有约 1.8 分）
        if cat == "漏字" and b and (any(abs(b0 - x) <= 1 and abs(b1 - y) <= 1 for x, y in seg_bounds) or
                                     RE_BOX_LABEL.match(b)):
            flags.append("source_whole_block")  # 原件里单独成块的方框标题（资料卡、知识链接…）被文字层插进正文
        if cat == "漏字" and a0 >= len(ln["disp"]) - 2 and b and nxt_disp.startswith(b[:4]):
            flags.append("line_boundary")  # 原件同一段在题库里拆成了两行，漏的字就在下一行开头
        if ln.get("ocr_sub"):
            flags.append("bank_ocr_candidate_block")
        # 题库这一处（连前后几个字）在同角色原件的别处原样出现：另一版本或同一文件另一页（如教师版答案区重抄题干）
        snip = ln["canon"][max(0, a0 - 6):a1 + 6]
        pos = idx.C.find(snip) if len(snip) >= 8 else -1
        here = ((labb or {}).get("sid"), (labb or {}).get("page"))
        while pos >= 0:
            lp = idx.label_at(pos)
            if lp and (lp.get("sid"), lp.get("page")) != here and lp.get("role") in ROLE_PREF.get(ln["role"], ()):
                flags.append("other_version_matches_bank")
                break
            pos = idx.C.find(snip, pos + 1)
        pri = W_ROLE.get(ln["role"], 1) * W_CAT[cat] * (1.0 if max(len(a), len(b)) <= 6 else 0.3) * \
            TIER_W.get((labb or {}).get("tier"), 0.2) * al["ratio"]
        if "decor_symbol" in flags or "source_replacement_char" in flags:
            pri *= 0.2
        if "model_annotation_in_bank" in flags or "source_table_order" in flags or "bank_line_prefix" in flags \
                or "source_stray_digit" in flags or "line_head_label" in flags or "line_boundary" in flags \
                or "bank_ocr_candidate_block" in flags or "score_mark_only" in flags \
                or "other_version_matches_bank" in flags or "source_whole_block" in flags:
            pri *= 0.3
        if "table_row" in flags:
            pri *= 0.5
        # 排序经验（只影响名次，不删差异）：两边都是 1—2 个汉字的替换/增删最像真错字，略升；
        # 一边是数字/括号/箭头、另一边是汉字的，多是排版或分值标注差异，略降
        seg_ab = a + b
        if max(len(a), len(b)) <= 2 and seg_ab and all(D.CJK.match(c) for c in seg_ab):
            pri *= 1.25
            flags.append("cjk_short")
        elif re.search(r"[\d\[\]→（）()①-⑳]", seg_ab) and D.CJK.search(seg_ab) and cat != "题号":
            pri *= 0.6
            flags.append("mixed_symbol_cjk")
        bref = "questions/%s/%s.md:%s" % (exam_id, qid, ln["md_line"])
        sref = "%s 第%s页" % ((labb or {}).get("rel"), (labb or {}).get("page"))
        bctx, bcut = D.clip_window(ln["disp"], a0 - 12, a1 + 12, bref)
        sctx, scut = D.clip_window(idx.D, b0 - 12, b1 + 12, sref)
        diffs.append({
            "exam": exam_id, "qid": qid, "role": ln["role"], "section": ln["title"], "basis": ln["basis"],
            "md_line": ln["md_line"], "category": cat, "subtype": subtype(a, b), "bank_text": a, "source_text": b,
            "bank_context": bctx, "source_context": sctx.replace("\x00", "|"),
            "context_truncated": bcut or scut,
            "source_id": (labb or {}).get("sid"), "source_role": (labb or {}).get("role"),
            "source_rel": (labb or {}).get("rel"), "page": (labb or {}).get("page"),
            "page_class": (labb or {}).get("fine"), "tier": (labb or {}).get("tier"),
            "bbox": (labb or {}).get("bbox"), "line_ratio": round(al["ratio"], 3), "flags": flags,
            "priority": round(pri, 3), "channel": "text_layer", "evidence_level": "machine_diff",
            "_snip": snip,
            "bank_section_claims_verified": bool(re.search(r"verified|核验|核对|复核|核校", ln["title"]))})
        st["diff_" + cat] += 1
    return diffs


def unlocated_bucket(ln, n_questions_same_line):
    """两道通道都对不上的行：题库自注/页眉页脚/图示描述/答案键行/学生手写层 → 不计入“应审”分母（单列）；
    其余返回 None（计入分母、算未审）。只看行本身的写法，不看是否对得上。"""
    raw = ln.get("raw", "")
    p = D.plain(raw).strip()
    if ln["role"] == "student":
        return "student_layer"
    if D.RE_PAGENO.match(p) or RE_BANK_PAGENO.match(p) or D.RE_TYPESET_LABEL.search(p):
        return "page_furniture"
    if RE_ANSWER_KEY_LINE.search(p):
        return "answer_key_line"
    if n_questions_same_line >= 3 or RE_NOTE_LINE.search(raw):
        return "bank_note"
    if RE_FIG_LINE.search(raw):
        return "figure_description"
    return None


# ---------------------------------------------------------------- OCR 双通道
# 实测 OCR 混淆表（原字 → OCR 读成的字, 次数）。来源（2026-09-24 统计，ocr-confusions 模式可重算）：
#   ① 446 页“原生文字层可靠且题库有 OCR”的页，原生字 vs 题库 OCR（约 30 万字）；
#   ② 180 页扫描/描边/乱码页的题库 OCR vs 题库默认题面；两者合并、同一对须在≥2处不同上下文出现。
#   另加三条有实物依据的：③→3（题库 OCR 里“①3”12 处，README 第 6 节亦记）、宣→宜（“虚假宜传”“学习宜传”4 处）、
#   诫→诚与遏→過（README 第 6 节实测记录）。只按“题库字→OCR 字”这个方向归一：反方向（题库写成“觉”、OCR 读“党”）
#   不在表里，仍当差异报——那正是题库错字的样子。
OCR_CONFUSIONS = (
    ("→", "一", 171), ("；", "：", 88), ("党", "觉", 52), ("—", "一", 32), ("为", "力", 26), ("为", "次", 20),
    (":", ".", 20), ("为", "沟", 18), ("入", "人", 12), ("→", "-", 11), ("一", "—", 10), ("予", "子", 10),
    ("为", "内", 8), ("＋", "十", 8), ("国", "困", 7), ("持", "特", 7), ("粱", "梁", 7), ("荣", "菜", 6),
    ("已", "己", 6), ("曰", "日", 6), ("巩", "现", 6), ("裁", "栽", 5), ("为", "汐", 5), ("舆", "奥", 5),
    ("邓", "双", 4), ("减", "減", 4), ("土", "士", 4), ("由", "日", 4), ("兔", "免", 4), ("巳", "已", 4),
    ("融", "触", 4), ("谐", "谱", 4), ("为", "沩", 4), ("。", "，", 4), ("责", "贵", 4), ("墙", "墻", 3),
    ("重", "童", 3), ("冶", "治", 3), ("鸟", "乌", 3), ("自", "白", 3), ("晶", "品", 3), ("况", "況", 3),
    ("客", "容", 3), ("乙", "己", 3), ("、", "，", 3), ("→", "—", 3), ("已", "巴", 3), ("境", "竞", 3),
    ("】", "：", 3), ("－", "一", 2), (";", "：", 2), ("丙", "两", 2), ("I", "l", 2), ("未", "来", 2),
    ("为", "為", 2), ("鸮", "鴞", 2), ("出", "茁", 2), ("未", "末", 2), ("揽", "搅", 2), ("治", "洽", 2),
    ("倡", "侣", 2), ("于", "干", 2), ("：", "；", 2), ("一", "-", 2), ("体", "休", 2), ("李", "季", 2),
    ("中", "申", 2), ("，", ".", 2), ("→", "›", 2), ("千", "干", 2), ("贫", "贪", 2),
    ("③", "3", 12), ("宣", "宜", 4), ("诫", "诚", 1), ("遏", "過", 1))
# OCR 常丢的字（题库有、OCR 没有）：“为”234 处、“殊”11 处，归一为通过；其他丢字只降为低等级
OCR_DROP_PASS = set("为殊")
OCR_DROP_LOW = set("矛切境党—”“】→．-，。…")
# 项目符号/图标：OCR 常把行首符号读成字（OCR 有、题库没有）：•70 个47 ＞19 令11 今10 心9 夕7 〇7 0 7 仑3 品3 …；
# 题库的 ⊙ 在 OCR 里常成 ◎/©。纯符号两边互换、或题库有符号 OCR 没有，归一为通过；被读成汉字的只在 OCR 行首才归一
BULLET_SYM = set("•·●◆◇◎©⊙○■□▪➢➤►▶❖♣✧◦＞>")
BULLET_MISREAD = set("个令今心夕〇0冬口品仑\\’の")
OCR_BULLET = BULLET_SYM | BULLET_MISREAD
ELLIPSIS = set("…⋯•·.．。")
LOW_FLAGS = {"cat_标点", "cat_题号", "cat_选项", "long_span", "symbol_only", "latin", "student_layer", "table_row",
             "weak_line_match", "line_edge", "bank_ocr_candidate_block", "ocr_drop_common", "ocr_insert_symbol",
             "score_or_table_digit", "model_annotation_in_bank", "ocr_reading_order", "question_number",
             "multi_char_replace", "bank_page_furniture", "ocr_dup_char", "arrow_symbol", "bank_note_line"}
# 只用于给 OCR 差异降级的“说明行”标记，比 RE_NOTE_LINE 窄（“角色”“来源”“状态”等正文也常见的词不算）
RE_NOTE_STRONG = re.compile(r"N/?A|缺源|未提供|未找到|原图|原页|页图|示意图|见下方|见上方|详见|原文如此|slide|幻灯片|证据等级|"
                            r"来源[：:]|本题未|转写|OCR|候选|跨题|示例（|机器值|难辨|无法辨认")
RE_BANK_PAGENO = re.compile(r"^.{0,30}第\s*\d+\s*页\s*[/／（(]?\s*共\s*\d+\s*页\s*[）)]?\s*$|^第\s*\d+\s*页$|^共\s*\d+\s*页")
# 光栅扫描类单元（OCR 在这类页上形近字误读多）；矢量描边字、乱码字体页、DOCX/PPT 嵌图按清晰处理
RASTER_FINE = {"scan_no_text", "ocr_layer_over_scan", "scan_with_ocr_layer", "ocr_text_layer", "empty"}
RE_BANK_ANN = re.compile(r"【|】|图[：:]|表[：:]|示意|转写|（图|标签|〔|DOCX|PDF|P\d{2}|原卷|原页|框.{0,2}[：:]|旁注|"
                         r"总规则[：:]|附“|^[上下左右中]\S?[：:]|箭头|原图|示意图|图中|框内")


def _confusion_set():
    s = set()
    for x, y, _n in OCR_CONFUSIONS:
        cx, cy = D.canon(x), D.canon(y)
        if cx != cy:
            s.add((cx, cy))
    return s


OCR_SUB = _confusion_set()
OCR_DROP_PASS_C = {D.canon(c) for c in OCR_DROP_PASS}
OCR_DROP_LOW_C = {D.canon(c) for c in OCR_DROP_LOW}
OCR_BULLET_C = {D.canon(c) for c in OCR_BULLET}
BULLET_SYM_C = {D.canon(c) for c in BULLET_SYM}
ELLIPSIS_C = {D.canon(c) for c in ELLIPSIS}


def ocr_equiv(a, b, ocr_line_start=False):
    """题库段 a 与 OCR 段 b 是否只差实测 OCR 混淆；是则返回归一类别，否则 None。"""
    A, Bs = D.canon(a), D.canon(b)
    if A == Bs:
        return "canon"
    if A and len(A) == len(Bs) and all(x == y or (x, y) in OCR_SUB for x, y in zip(A, Bs)):
        return "confusion"
    if A and not Bs and all(c in OCR_DROP_PASS_C for c in A):
        return "ocr_drop"
    if (A or Bs) and all(c in BULLET_SYM_C for c in A):
        if not Bs:
            return "bullet"  # 题库有符号、OCR 没读出
        if all(c in BULLET_SYM_C for c in Bs):
            return "bullet"  # 两边都是纯符号（⊙↔◎ 等）
        if all(c in OCR_BULLET_C for c in Bs) and ocr_line_start:
            return "bullet"  # OCR 行首把符号读成“个/令/今/心…”
    if (A or Bs) and set(A) <= ELLIPSIS_C and set(Bs) <= ELLIPSIS_C and ("…" in a or "…" in A or "⋯" in b or "·" in Bs):
        return "ellipsis"
    return None


_GLYPH = {}


def _glyph_vec(c):
    if c in _GLYPH:
        return _GLYPH[c]
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
    f = cjk_font(56)
    im = Image.new("L", (64, 64), 0)
    ImageDraw.Draw(im).text((4, 0), c, font=f, fill=255)
    a = np.asarray(im.filter(ImageFilter.GaussianBlur(2.0)), dtype=float)
    a -= a.mean()
    n = float(np.linalg.norm(a))
    _GLYPH[c] = a / n if n else a
    return _GLYPH[c]


def glyph_sim(a, b):
    """两段等长汉字的逐字字形相关（模糊后归一化互相关）均值；不等长或含非汉字返回 None。"""
    A, Bs = D.canon(a), D.canon(b)
    if not A or len(A) != len(Bs) or not all(D.CJK.match(c) for c in A + Bs):
        return None
    try:
        return round(sum(float((_glyph_vec(x) * _glyph_vec(y)).sum()) for x, y in zip(A, Bs)) / len(A), 3)
    except Exception:
        return None


_CORPUS = {}


def _bank_corpus():
    """题库全部卷默认读法（不含 OCR 候选小块）的规范化文字，按卷分开；只建一次（约 1 秒）。"""
    if not _CORPUS:
        by = collections.defaultdict(list)
        for f in glob.glob(os.path.join(BANK_Q, "*", "*-Q*.md")):
            e = os.path.basename(os.path.dirname(f))
            try:
                md = open(f, encoding="utf-8").read()
                by[e].append("".join(l["canon"] for l in reading_lines(md, os.path.basename(f)[:-3]) if not l.get("ocr_sub")))
            except Exception:
                continue
        _CORPUS["by"] = {e: "\x00".join(v) for e, v in by.items()}
        _CORPUS["all"] = "\x00".join(_CORPUS["by"].values())
    return _CORPUS


def _count_other(exam_id, ng):
    c = _bank_corpus()
    return c["all"].count(ng) - c["by"].get(exam_id, "").count(ng)


def corpus_attest(exam_id, ctx, a, b):
    """题库读法与 OCR 读法在其他卷默认读法里是否出现过（窗口：左2+差异、差异+右2、左1+差异+右1，至少 3 字）。
    返回 bank_only / ocr_only / both / neither。"""
    L, R = ctx
    A, Bs = D.canon(a), D.canon(b)

    def wins(x):
        out = {L[-2:] + x, x + R[:2], L[-1:] + x + R[:1]} if x else {L[-2:] + R[:2]}
        return [w for w in out if len(w) >= 3 and "\x00" not in w]
    ba = any(_count_other(exam_id, w) > 0 for w in wins(A))
    oa = any(_count_other(exam_id, w) > 0 for w in wins(Bs))
    return "both" if ba and oa else ("bank_only" if ba else ("ocr_only" if oa else "neither"))


SWIFT_BOXES = r'''
import Foundation
import Vision
import AppKit
// bank_retro_audit 第二读法：ocr_boxes IMG... → stdout JSON [{file,w,h,lines:[{t,c,x,y,w,h}]}]（坐标 0–1，原点左下）
var out: [[String: Any]] = []
for p in CommandLine.arguments.dropFirst() {
  autoreleasepool {
    guard let img = NSImage(contentsOfFile: p),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
      out.append(["file": p, "error": "unreadable"]); return
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.recognitionLanguages = ["zh-Hans", "en-US"]
    req.usesLanguageCorrection = true
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    do { try h.perform([req]) } catch { out.append(["file": p, "error": "\(error)"]); return }
    var lines: [[String: Any]] = []
    for o in (req.results ?? []) {
      guard let c = o.topCandidates(1).first else { continue }
      let b = o.boundingBox
      lines.append(["t": c.string, "c": c.confidence, "x": b.origin.x, "y": b.origin.y,
                    "w": b.size.width, "h": b.size.height])
    }
    out.append(["file": p, "w": cg.width, "h": cg.height, "lines": lines])
  }
}
let d = try! JSONSerialization.data(withJSONObject: out, options: [])
FileHandle.standardOutput.write(d)
'''


def ensure_boxes_helper(cache):
    """用系统 swiftc 把 SWIFT_BOXES 编译到 cache/_bin（模块缓存与临时文件也放那里）；失败返回 None。"""
    h = hashlib.sha256(SWIFT_BOXES.encode()).hexdigest()[:12]
    bdir = os.path.join(cache, "_bin")
    exe = os.path.join(bdir, "ocr_boxes_" + h)
    if os.path.isfile(exe) and os.access(exe, os.X_OK):
        return exe
    import shutil
    import subprocess
    swiftc = shutil.which("swiftc") or "/usr/bin/swiftc"
    if not os.path.isfile(swiftc):
        return None
    os.makedirs(os.path.join(bdir, "tmp"), exist_ok=True)
    src = os.path.join(bdir, "ocr_boxes.swift")
    open(src, "w", encoding="utf-8").write(SWIFT_BOXES)
    env = dict(os.environ, TMPDIR=os.path.join(bdir, "tmp"), CLANG_MODULE_CACHE_PATH=os.path.join(bdir, "mc"))
    try:
        subprocess.run([swiftc, "-O", "-module-cache-path", os.path.join(bdir, "mc"), src, "-o", exe],
                       capture_output=True, timeout=600, env=env)
    except Exception:
        return None
    # 模块缓存约 270MB，只在编译时用；编译完即删，只留约 70KB 的可执行文件
    shutil.rmtree(os.path.join(bdir, "mc"), ignore_errors=True)
    shutil.rmtree(os.path.join(bdir, "tmp"), ignore_errors=True)
    return exe if os.path.isfile(exe) else None


def _ocr_txt_lines(txt):
    out = []
    for l in (txt or "").splitlines():
        s = l.strip()
        if not s or re.match(r"^=====.*=====$", s):
            continue
        s = re.sub(r"<<<OCR [^>]*>>>", "", s).strip()
        if s:
            out.append(s)
    return out


def _split_ocr_vision_output(raw_dir):
    """ocr-vision 输出（一个文件可含多页，页头“===== 名 page N =====”或“===== 名 =====”）→ {(名, 页或None): 文本}。"""
    got = {}
    for f in sorted(os.listdir(raw_dir)):
        if not f.endswith(".txt"):
            continue
        cur, buf = None, []
        for l in open(os.path.join(raw_dir, f), encoding="utf-8", errors="replace").read().splitlines():
            m = re.match(r"^=====\s*(.+?)(?:\s+page\s+(\d+))?\s*=====$", l.strip())
            if m:
                if cur is not None:
                    got[cur] = "\n".join(buf)
                cur, buf = (m.group(1), int(m.group(2)) if m.group(2) else None), []
            else:
                buf.append(l)
        if cur is not None:
            got[cur] = "\n".join(buf)
    return got


class OcrChannel:
    """一卷的 OCR 候选语料：无可靠文字层的页/图 → OCR 文本（题库已有优先，缺的本机 ocr-vision 补跑到缓存）→ TextIndex；
    有差异的单元再跑第二读法（Vision 行框+置信度）→ 裁图、分级、拼图。"""
    NATIVE = {"text_reliable", "docx", "pptx_text", "legacy_converted"}
    IMG_EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tif", ".tiff")

    def __init__(self, exam_id, infos, roles, cfg):
        self.exam_id, self.infos, self.cfg = exam_id, infos, cfg
        self.allowed = set()
        for r in roles:
            self.allowed |= ROLE_PREF.get(r, set())
        self.cache = cfg["cache"]
        self.units, self.by_uid = [], {}
        self.idx, self.line_starts = None, set()
        self.stat = collections.Counter()
        self.sec = collections.Counter()
        self.helper = None
        self.renders = []

    # ---- 选单元
    def _add_unit(self, u):
        if u["uid"] in self.by_uid:
            self.by_uid[u["uid"]]["roles"].add(u["role"])
            return
        u["roles"] = {u["role"]}
        self.units.append(u)
        self.by_uid[u["uid"]] = u

    def collect(self):
        for inf in self.infos:
            if inf.get("missing") or inf.get("error") or inf.get("role") not in self.allowed:
                continue
            sid, fmt, path = inf["source_id"], inf.get("format"), inf.get("path")
            base = dict(sid=sid, role=inf["role"], rel=inf["rel_path"], path=path, fmt=fmt)
            vt = os.path.join(D.BANK, "evidence", sid, "visual_transcript")
            fine = {int(k): v for k, v in (inf.get("page_fine") or {}).items()}
            if fmt == "pdf":
                for pg in sorted(fine):
                    bank_txt, _f = D.find_ocr_text(sid, pg, [vt])
                    if fine[pg] in self.NATIVE and not bank_txt:
                        continue
                    self._add_unit(dict(base, uid="%s:p%03d" % (sid, pg), page=pg, sub=None, kind="pdf_page",
                                        fine=fine[pg], image=None, bank_txt=bank_txt))
            elif fmt == "pptx":
                need = [pg for pg in sorted(fine) if fine[pg] in ("pptx_picture", "pptx_mixed")]
                pics = None
                for pg in need:
                    png = os.path.join(D.BANK, "evidence", sid, "pages", "p%03d.png" % pg)
                    bank_txt, _f = D.find_ocr_text(sid, pg, [vt])
                    if os.path.isfile(png):
                        self._add_unit(dict(base, uid="%s:s%03d" % (sid, pg), page=pg, sub=None, kind="slide_png",
                                            fine=fine[pg], image=png, bank_txt=bank_txt))
                        continue
                    if pics is None:
                        pics = self._pptx_pictures(path, sid)
                    for k, img in enumerate(pics.get(pg, []), 1):
                        self._add_unit(dict(base, uid="%s:s%03d_img%02d" % (sid, pg, k), page=pg,
                                            sub=os.path.basename(img), kind="slide_pic", fine=fine[pg], image=img,
                                            bank_txt=None))
            elif fmt == "docx" and any(v == "docx_with_image" for v in fine.values()):
                for k, img in enumerate(self._docx_images(path, sid), 1):
                    self._add_unit(dict(base, uid="%s:img%02d" % (sid, k), page=None, sub=os.path.basename(img),
                                        kind="docx_img", fine="docx_with_image", image=img, bank_txt=None))
        self.stat["units"] = len(self.units)

    def _img_dir(self, sid):
        d = os.path.join(self.cache, sid, "img")
        os.makedirs(d, exist_ok=True)
        return d

    def _pptx_pictures(self, path, sid):
        """没有题库页图的 PPT 图片页：取该张里面积≥3%的图片原图（只写缓存）。"""
        out = collections.defaultdict(list)
        try:
            prs, _n = D.open_pptx(path)
        except Exception:
            return out
        area = float((prs.slide_width or 1) * (prs.slide_height or 1))

        def walk(shapes, i):
            for sh in shapes:
                if sh.__class__.__name__ == "GroupShape":
                    walk(sh.shapes, i)
                    continue
                if getattr(sh, "shape_type", None) == 13 or sh.__class__.__name__ == "Picture":
                    try:
                        if (sh.width or 0) * (sh.height or 0) / area < 0.03:
                            continue
                        img = sh.image
                        if "." + img.ext.lower() not in self.IMG_EXT:
                            continue
                        fp = os.path.join(self._img_dir(sid), "s%03d_%s.%s" % (i, img.sha1[:10], img.ext))
                        if not os.path.isfile(fp):
                            open(fp, "wb").write(img.blob)
                        if fp not in out[i]:
                            out[i].append(fp)
                    except Exception:
                        continue
        for i, s in enumerate(prs.slides, 1):
            walk(s.shapes, i)
        return out

    def _docx_images(self, path, sid):
        import zipfile
        out = []
        try:
            z = zipfile.ZipFile(path)
        except Exception:
            return out
        from PIL import Image
        for n in sorted(z.namelist()):
            if not n.startswith("word/media/") or not n.lower().endswith(self.IMG_EXT):
                continue
            fp = os.path.join(self._img_dir(sid), "d_" + os.path.basename(n))
            if not os.path.isfile(fp):
                open(fp, "wb").write(z.read(n))
            try:
                w, h = Image.open(fp).size
            except Exception:
                continue
            if w >= 200 and h >= 50:
                out.append(fp)
        return out

    # ---- OCR 文本
    def _cache_txt(self, u):
        return os.path.join(self.cache, u["sid"], "ocr", u["uid"].split(":", 1)[1] + ".ocr.txt")

    def acquire_text(self):
        import subprocess
        t0 = time.time()
        todo_pdf = collections.defaultdict(list)
        todo_img = collections.defaultdict(list)
        for u in self.units:
            if u.get("bank_txt"):
                u["lines"], u["ocr_src"] = _ocr_txt_lines(u["bank_txt"]), "bank_evidence_ocr"
                continue
            c = self._cache_txt(u)
            if os.path.isfile(c):
                u["lines"], u["ocr_src"] = _ocr_txt_lines(open(c, encoding="utf-8").read()), "ocr_vision_cached"
                continue
            if u["kind"] == "pdf_page":
                todo_pdf[(u["sid"], u["path"])].append(u)
            else:
                todo_img[u["sid"]].append(u)
        exe = D.ocr_exe() if self.cfg.get("run_new", True) else None
        jobs = []
        if exe:
            for (sid, path), us in todo_pdf.items():
                jobs.append(("pdf", sid, path, us))
            for sid, us in todo_img.items():
                for k in range(0, len(us), 40):
                    jobs.append(("img", sid, None, us[k:k + 40]))

        def run(job):
            kind, sid, path, us = job
            raw = os.path.join(self.cache, sid, "_raw_%d_%d" % (os.getpid(), id(job)))
            os.makedirs(raw, exist_ok=True)
            if kind == "pdf":
                cmd = [exe, "--out", raw, "--pages", ",".join(str(u["page"]) for u in us), path]
            else:
                cmd = [exe, "--out", raw] + [u["image"] for u in us]
            try:
                subprocess.run(cmd, capture_output=True, timeout=60 + 15 * len(us))
            except Exception:
                pass
            got = _split_ocr_vision_output(raw)
            for u in us:
                if kind == "pdf":
                    txt = next((v for (n, p), v in got.items() if p == u["page"]), None)
                else:
                    txt = next((v for (n, p), v in got.items() if n == os.path.basename(u["image"])), None)
                if txt is None:
                    continue
                c = self._cache_txt(u)
                os.makedirs(os.path.dirname(c), exist_ok=True)
                open(c, "w", encoding="utf-8").write(txt)
            import shutil
            shutil.rmtree(raw, ignore_errors=True)
            return len(us)

        if jobs:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=3) as ex:
                list(ex.map(run, jobs))
        for u in self.units:
            if "lines" in u:
                continue
            c = self._cache_txt(u)
            if os.path.isfile(c):
                u["lines"], u["ocr_src"] = _ocr_txt_lines(open(c, encoding="utf-8").read()), "ocr_vision_run"
            else:
                u["lines"], u["ocr_src"] = [], "none"
        for u in self.units:
            self.stat["units_" + u["ocr_src"]] += 1
        self.sec["ocr_text"] += time.time() - t0

    def build(self):
        self.collect()
        if not self.units:
            return self
        self.acquire_text()
        idx = D.TextIndex()
        for u in self.units:
            if not u["lines"]:
                continue
            for i, line in enumerate(u["lines"]):
                start = idx._len
                idx.add_nosep(line, {"sid": u["sid"], "role": u["role"], "roles": u["roles"], "rel": u["rel"],
                                     "page": u["page"], "unit": u["uid"], "kind": u["kind"], "fine": u["fine"],
                                     "tier": "ocr_candidate", "ocr_src": u["ocr_src"], "line_no": i,
                                     "n_lines": len(u["lines"])})
                if idx._len > start:
                    self.line_starts.add(start)
            idx.sep()
        idx.build()
        self.idx = idx if idx.segs else None
        return self

    # ---- 逐条差异
    def diffs_for(self, exam_id, qid, ln, al, st, qtext=None):
        idx = self.idx
        out = []
        lab0 = idx.label_at(al["start"] + 1)
        for tag, a0, a1, b0, b1 in al["ops"]:
            a = ln["disp"][a0:a1]
            b = idx.D[b0:b1].replace("\x00", "")
            if not a and not b:
                continue
            labb = idx.label_at(b0) if b1 > b0 else lab0
            at_start = any(p in self.line_starts for p in range(b0, max(b1, b0 + 1)))
            eq = ocr_equiv(a, b, at_start)
            if eq:
                st["ocr_pass_" + eq] += 1
                continue
            cat = classify(a, b, ln["disp"], a0)
            flags = []
            seg = a + b
            if cat in ("标点", "题号", "选项"):
                flags.append("cat_" + cat)
            if max(len(a), len(b)) > 4:
                flags.append("long_span")
            if not D.CJK.search(seg) and not re.search(r"[\d①-⑳]", seg):
                flags.append("symbol_only")
            if re.search(r"[A-Za-z]", seg):
                flags.append("latin")
            if ln["role"] == "student":
                flags.append("student_layer")
            if ln.get("raw", "").lstrip().startswith("|") or "<td" in ln.get("raw", ""):
                flags.append("table_row")
            if al["ratio"] < 0.85:
                flags.append("weak_line_match")
            if cat in ("漏字", "增字") and (a0 <= 1 or a1 >= len(ln["disp"]) - 1):
                flags.append("line_edge")
            if ln.get("ocr_sub"):
                flags.append("bank_ocr_candidate_block")
            if a and not b and all(D.canon(c) in OCR_DROP_LOW_C for c in a):
                flags.append("ocr_drop_common")
            if b and not a and all(c in OCR_BULLET_C for c in D.canon(b)):
                flags.append("ocr_insert_symbol")
            if (labb or {}).get("kind") in ("docx_img", "slide_pic"):
                flags.append("embedded_image")
            if re.fullmatch(r"[，。,.；;：:]?\s*\d{1,2}\s*[.．、]\s*", b or "x") or re.fullmatch(r"[，。,.；;：:]?\s*\d{1,2}\s*[.．、]\s*", a or "x") \
                    or re.search(r"\d{1,2}[.．]\s*$", b) and cat in ("漏字", "错字"):
                flags.append("question_number")  # OCR 把下一题/下一条的编号接进来
            if cat == "错字" and len(D.canon(a)) >= 3 and len(D.canon(b)) >= 3:
                flags.append("multi_char_replace")
            near = ln["disp"][max(0, a0 - 3):a1 + 3]
            if re.search(r"\d", a + b) and re.search(r"分", near):
                flags.append("score_or_table_digit")
            if D.RE_PAGENO.match(D.plain(ln.get("raw", "")).strip()) or RE_BANK_PAGENO.match(D.plain(ln.get("raw", "")).strip()):
                flags.append("bank_page_furniture")
            if re.search(r"[→←↑↓⇒➝]", a + b):
                flags.append("arrow_symbol")  # 流程图箭头在 OCR 里常丢或并进邻字（“策→”读成“束”）
            if cat == "错字":
                bw = D.canon(ln["disp"][max(0, a0 - 2):a1 + 2])
                if len(bw) >= 4 and any(abs(p_ - b0) <= 400 and (idx.label_at(p_) or {}).get("unit") == (labb or {}).get("unit")
                                        for p_ in _find_all(idx.C, bw, 20)):
                    flags.append("ocr_reading_order")  # 题库这几个字在同单元 OCR 附近原样有：是对齐到了版面相似处
            if re.search(r"\d", a + b):
                # 数字差异：题库这一处的整个数（如“2016”）在同单元 OCR 别处原样有，或 OCR 这个数在本题题库别处有 → 图表/时间轴读序
                ctx0 = D.canon(ln["disp"][max(0, a0 - 4):a1 + 4])
                num_a = max(re.findall(r"\d+", ctx0) or [""], key=len)
                num_b = max(re.findall(r"\d+", idx.C[max(0, b0 - 4):b1 + 4]) or [""], key=len)
                if (len(num_a) >= 2 and any((idx.label_at(p_) or {}).get("unit") == (labb or {}).get("unit")
                                            for p_ in _find_all(idx.C, num_a, 20))) or \
                        (len(num_b) >= 2 and num_b in (qtext or "")):
                    flags.append("ocr_reading_order")
            if RE_NOTE_STRONG.search(ln.get("raw", "")):
                flags.append("bank_note_line")  # 题库自写的说明行碰巧与 OCR 部分对上
            if cat == "漏字" and len(D.canon(b)) == 1 and D.canon(b) in D.canon(ln["disp"][max(0, a0 - 3):a0 + 3]):
                flags.append("ocr_reading_order")  # OCR 多出的单字就在题库本处前后 3 字内（图注/读序插入，“已通表过圭表”）
            if cat == "漏字" and b and len(D.canon(b)) == 1 and (idx.C[b0 - 1:b0] == D.canon(b) or idx.C[b1:b1 + 1] == D.canon(b)):
                flags.append("ocr_dup_char")  # OCR 重复读了相邻字（“圭圭表”）
            if a and RE_BANK_ANN.search(a):
                flags.append("model_annotation_in_bank")  # 题库自加的【图】【资料卡】【图示标签：】等标注
            # OCR 读序与版面不同（图中标签、短尾行被排到别处）：题库多出的字在同单元 OCR 附近另有，或 OCR 多出的字在本题题库别处另有
            ca, cb = D.canon(a), D.canon(b)
            if cat == "增字" and len(ca) >= 2:
                for p_ in _find_all(idx.C, ca, 20):
                    if abs(p_ - b0) <= 600 and (idx.label_at(p_) or {}).get("unit") == (labb or {}).get("unit"):
                        flags.append("ocr_reading_order")
                        break
            elif cat == "漏字" and len(cb) >= 2 and (cb in ln["canon"] or cb in (qtext or "")):
                flags.append("ocr_reading_order")
            if re.search(r"\d", seg) and (ln.get("raw", "").lstrip().startswith("|") or re.search(r"\d\s*分", seg)):
                flags.append("score_or_table_digit")
            pri = W_ROLE.get(ln["role"], 1) * W_CAT[cat] * (1.0 if max(len(a), len(b)) <= 4 else 0.3) * al["ratio"]
            if max(len(a), len(b)) <= 2 and seg and all(D.CJK.match(c) for c in seg):
                pri *= 1.25
                flags.append("cjk_short")
            bref = "questions/%s/%s.md:%s" % (exam_id, qid, ln["md_line"])
            sref = "%s %s OCR" % ((labb or {}).get("rel"), (labb or {}).get("unit"))
            bctx, bcut = D.clip_window(ln["disp"], a0 - 12, a1 + 12, bref)
            sctx, scut = D.clip_window(idx.D, b0 - 12, b1 + 12, sref)
            # 同一单元内的 OCR 片段（第二读法与裁图定位用），不跨单元
            u0, u1 = max(0, b0 - 8), min(len(idx.C), b1 + 8)
            wseg = idx.C[u0:u1]
            if "\x00" in wseg:
                k = b0 - u0
                left = wseg[:k].rsplit("\x00", 1)[-1]
                right = wseg[k:].split("\x00", 1)[0]
                wseg = left + right
                u0 = b0 - len(left)
            out.append({
                "exam": exam_id, "qid": qid, "role": ln["role"], "section": ln["title"], "basis": ln["basis"],
                "md_line": ln["md_line"], "category": cat, "subtype": subtype(a, b), "bank_text": a, "source_text": b,
                "ocr_text": b, "bank_context": bctx, "source_context": sctx.replace("\x00", "|"),
                "context_truncated": bcut or scut, "source_id": (labb or {}).get("sid"),
                "source_role": (labb or {}).get("role"), "source_rel": (labb or {}).get("rel"),
                "page": (labb or {}).get("page"), "unit": (labb or {}).get("unit"), "unit_kind": (labb or {}).get("kind"),
                "page_class": (labb or {}).get("fine"), "tier": "ocr_candidate", "ocr_src": (labb or {}).get("ocr_src"),
                "ocr_line_no": (labb or {}).get("line_no"), "ocr_n_lines": (labb or {}).get("n_lines"),
                "line_ratio": round(al["ratio"], 3), "flags": flags, "priority": round(pri, 3), "channel": "ocr",
                "evidence_level": "ocr_candidate", "grade": None, "ocr_conf": None, "second_read": None,
                "_bank_snip": D.canon(ln["disp"][max(0, a0 - 6):a1 + 6]), "_ocr_snip": wseg, "_ocr_off": b0 - u0,
                "_ngram_ctx": (D.canon(ln["disp"][max(0, a0 - 2):a0]), D.canon(ln["disp"][a1:a1 + 2])),
                "_ocr_len": b1 - b0, "_bank_mark": (ln["disp"][max(0, a0 - 8):a0], a, ln["disp"][a1:a1 + 8]),
                "_ocr_mark": (idx.D[max(0, b0 - 8):b0].split("\x00")[-1], b, idx.D[b1:b1 + 8].split("\x00")[0])})
            st["ocr_diff_" + cat] += 1
        # 同一行里一处“漏 X”、附近一处“增 X”（单字换位）：OCR 读序问题
        for i_, d1 in enumerate(out):
            for d2 in out[i_ + 1:]:
                if {d1["category"], d2["category"]} == {"漏字", "增字"} and \
                        D.canon(d1["bank_text"] or d1["ocr_text"]) == D.canon(d2["bank_text"] or d2["ocr_text"]) and \
                        abs(d1["md_line"] - d2["md_line"]) == 0:
                    for x in (d1, d2):
                        if "ocr_reading_order" not in x["flags"]:
                            x["flags"].append("ocr_reading_order")
        return out

    # ---- 第二读法（行框 + 置信度）
    def _unit_image(self, u):
        if u.get("image"):
            return u["image"]
        if u["kind"] != "pdf_page":
            return None
        import fitz
        d = os.path.join(self.cache, u["sid"], "render")
        os.makedirs(d, exist_ok=True)
        fp = os.path.join(d, "p%03d.png" % u["page"])
        if not os.path.isfile(fp):
            doc = fitz.open(u["path"])
            doc[u["page"] - 1].get_pixmap(dpi=self.cfg.get("dpi", 200)).save(fp)
            self.renders.append(fp)
        u["image"] = fp
        return fp

    def second_read(self, uids):
        import subprocess
        t0 = time.time()
        want = [self.by_uid[x] for x in uids if x in self.by_uid]
        for u in want:
            self._unit_image(u)
        if not self.cfg.get("second_read", True):
            return
        if self.helper is None:
            self.helper = ensure_boxes_helper(self.cache) or False
        if not self.helper:
            self.stat["second_read_unavailable"] += 1
            return
        todo = []
        for u in want:
            cj = os.path.join(self.cache, u["sid"], "boxes", u["uid"].split(":", 1)[1] + ".json")
            u["boxes_path"] = cj
            if os.path.isfile(cj):
                try:
                    u["boxes"] = json.load(open(cj, encoding="utf-8"))
                    continue
                except Exception:
                    pass
            if u.get("image") and os.path.isfile(u["image"]):
                todo.append(u)
        chunks = [todo[k:k + 6] for k in range(0, len(todo), 6)]

        def run(chunk):
            try:
                r = subprocess.run([self.helper] + [u["image"] for u in chunk], capture_output=True, timeout=120 + 30 * len(chunk))
                res = json.loads(r.stdout.decode("utf-8") or "[]")
            except Exception:
                return 0
            by = {x.get("file"): x for x in res}
            for u in chunk:
                x = by.get(u["image"])
                if not x or x.get("error"):
                    continue
                os.makedirs(os.path.dirname(u["boxes_path"]), exist_ok=True)
                json.dump(x, open(u["boxes_path"], "w", encoding="utf-8"), ensure_ascii=False)
                u["boxes"] = x
            return len(chunk)

        if chunks:
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(max_workers=4) as ex:
                list(ex.map(run, chunks))
        self.stat["second_read_units"] += sum(1 for u in want if u.get("boxes"))
        self.sec["second_read"] += time.time() - t0

    @staticmethod
    def _boxes_index(u):
        if "_bidx" in u:
            return u["_bidx"]
        bi = D.TextIndex(k=4)
        starts = []
        for i, l in enumerate((u.get("boxes") or {}).get("lines", [])):
            s0 = bi._len
            bi.add_nosep(l.get("t", ""), {"i": i})
            starts.append((s0, bi._len, i))
        bi.sep()
        bi.build()
        u["_bidx"] = (bi, starts) if bi.segs else (None, [])
        return u["_bidx"]

    def judge(self, d):
        """第二读法定位、置信度与高/低分级（不改差异本身）。"""
        u = self.by_uid.get(d.get("unit"))
        flags = d["flags"]
        low_flags = [f for f in flags if f in LOW_FLAGS]
        d["second_read"], d["ocr_conf"], d["_box"] = None, None, None
        if u is not None and u.get("boxes"):
            bi, starts = self._boxes_index(u)
            if bi is not None:
                snip = d["_ocr_snip"]
                al = bi.align(snip) if len(snip) >= 4 else None
                if al is not None and al["ratio"] >= 0.5:
                    pos = al["start"] + d["_ocr_off"]
                    li = next((s for s in starts if s[0] <= pos < s[1]), None) or \
                        min(starts, key=lambda s: abs(s[0] - pos))
                    box = u["boxes"]["lines"][li[2]]
                    d["ocr_conf"] = round(float(box.get("c", 0)), 2)
                    d["_box"] = (box, max(0, pos - li[0]), max(1, li[1] - li[0]))
                    win = bi.C[max(0, al["start"] - 2):al["end"] + 2]
                    bank_s, ocr_s = d["_bank_snip"], snip
                    if bank_s and bank_s in bi.C and not (ocr_s and ocr_s in bi.C):
                        d["second_read"] = "bank"
                    elif ocr_s and ocr_s in bi.C and not (bank_s and bank_s in bi.C):
                        d["second_read"] = "ocr"
                    else:
                        import difflib
                        rb = difflib.SequenceMatcher(None, bank_s, win, autojunk=False).ratio()
                        ro = difflib.SequenceMatcher(None, ocr_s, win, autojunk=False).ratio()
                        d["second_read"] = "bank" if rb > ro + 0.03 else ("ocr" if ro > rb + 0.03 else "tie")
        if d["second_read"] == "bank":
            flags.append("second_read_matches_bank")
        if d["ocr_conf"] is not None and d["ocr_conf"] < 0.99:
            flags.append("low_ocr_conf")
        # OCR 误读的两个旁证（只用于分级，不删差异）：
        #   字形近——错字两边逐字字形相关≥0.72（实测 OCR 混淆对中位 0.80，随机字对均值 0.47、p95 0.67；获/取 0.59）；
        #   OCR 读法成“非词”——题库读法（前后各 1—2 字的窗口）在题库其他卷的默认读法里出现过，OCR 读法一处都没有。
        a, b, cat = d["bank_text"], d["ocr_text"], d["category"]
        gs = glyph_sim(a, b) if cat == "错字" else None
        d["glyph_sim"] = gs
        if gs is not None and gs >= 0.72:
            flags.append("glyph_similar")
        att = corpus_attest(self.exam_id, d["_ngram_ctx"], a, b)
        d["corpus"] = att
        if att == "bank_only":
            flags.append("ocr_nonword")
        elif att == "ocr_only":
            flags.append("bank_ngram_unattested")
        # 分级经验（2026-09-24 在 26 卷 43 条高等级上逐条看裁图校准）：
        #   光栅扫描页：错字两边字形相关≥0.57 多是 OCR 形近误读（活/话、鹌/鹤、国/图、适/造、殷/殿），不等长汉字替换且
        #     OCR 读法成非词的也多是误读（作答要→作笛）；等长低字形相关的（或→及、相→盲）与带标点的改写保持高；
        #     题库多字、OCR 少字（增字）多是 OCR 丢字，除非只有 OCR 读法在其他卷出现过；
        #   清晰页（矢量描边字、嵌图、PPT 页图）：OCR 很少误读，只有字形很近（≥0.8）且 OCR 读法成非词才降级——
        #     原件自身笔误（“轻营决策”“教据链”“检查机关”）OCR 如实读出、题库悄悄改正，也按差异报。
        raster = d.get("page_class") in RASTER_FINE
        if raster:
            uneq_cjk = len(D.canon(a)) != len(D.canon(b)) and a and b and all(D.CJK.match(c) for c in D.canon(a + b))
            ocr_like = (cat == "错字" and (gs is not None and gs >= 0.57 or (uneq_cjk and att == "bank_only"))) or \
                (cat == "增字" and att != "ocr_only")
        else:
            ocr_like = cat == "错字" and gs is not None and gs >= 0.8 and att == "bank_only"
        if ocr_like:
            flags.append("ocr_like_misread")
        strict = not low_flags and cat in ("错字", "漏字", "增字") and not ocr_like
        if d["second_read"] is not None:
            d["grade"] = "high" if strict and d["second_read"] == "ocr" and (d["ocr_conf"] or 0) >= 0.99 else "low"
            d["grade_basis"] = "second_read"
        else:
            # 没有第二读法（swiftc 不可用或该单元定位失败）：只按文字规则，且 OCR 字不在混淆表里才算高
            conf_pair = any((D.canon(x), D.canon(y)) in OCR_SUB for x in d["bank_text"] for y in d["ocr_text"])
            d["grade"] = "high" if strict and not conf_pair and d["line_ratio"] >= 0.9 else "low"
            d["grade_basis"] = "text_rules_only"
        d["priority"] = round(d["priority"] * (1.0 if d["grade"] == "high" else 0.3) *
                              (d["ocr_conf"] if d["ocr_conf"] is not None else 0.8), 3)

    # ---- 裁图
    def crop(self, d, out_dir, n):
        from PIL import Image, ImageDraw
        u = self.by_uid.get(d.get("unit"))
        img_path = self._unit_image(u) if u else None
        if not img_path or not os.path.isfile(img_path):
            return None
        im = Image.open(img_path).convert("RGB")
        W, H = im.size
        approx = False
        if d.get("_box"):
            box, off, L = d["_box"]
            x0, x1 = box["x"] * W, (box["x"] + box["w"]) * W
            y0, y1 = (1 - box["y"] - box["h"]) * H, (1 - box["y"]) * H
            lh = max(8.0, y1 - y0)
            cw = (x1 - x0) / float(L)  # 按行内字数均分估计字宽
            cx0 = x0 + off * cw
            cx1 = cx0 + max(1, d["_ocr_len"]) * cw
            half = max(lh * 12, cw * 12)
            mid = (cx0 + cx1) / 2
            rx0, rx1 = max(0, mid - half), min(W, mid + half)
            ry0, ry1 = max(0, y0 - lh * 0.7), min(H, y1 + lh * 0.7)
            mark = (cx0 - rx0 - 2, y0 - ry0 - 2, cx1 - rx0 + 2, y1 - ry0 + 2)
        else:
            # 没有行框：按 OCR 行序估计纵向位置，裁一条三行高的全宽带（approx）
            approx = True
            i, nl = d.get("ocr_line_no") or 0, max(1, d.get("ocr_n_lines") or 1)
            yc = H * (0.06 + 0.88 * (i + 0.5) / nl)
            lh = H / 45.0
            rx0, rx1, ry0, ry1 = 0, W, max(0, yc - 2 * lh), min(H, yc + 2 * lh)
            mark = None
        c = im.crop((int(rx0), int(ry0), int(rx1), int(ry1)))
        if mark:
            dr = ImageDraw.Draw(c)
            dr.rectangle([max(0, mark[0]), max(0, mark[1]), min(c.size[0] - 1, mark[2]), min(c.size[1] - 1, mark[3])],
                         outline=(230, 0, 0), width=3)
        os.makedirs(out_dir, exist_ok=True)
        name = "%04d_%s_%s.png" % (n, d["qid"].rsplit("-", 1)[-1], re.sub(r"[^\w]+", "_", d.get("unit") or "u"))
        fp = os.path.join(out_dir, name)
        if c.size[0] > 1600:
            c = c.resize((1600, max(1, int(c.size[1] * 1600.0 / c.size[0]))))
        c.save(fp)
        d["crop_approx"] = approx
        return fp

    def cleanup(self):
        for fp in self.renders:
            try:
                os.remove(fp)
            except OSError:
                pass


def cjk_font(size):
    from PIL import ImageFont
    for p in ("/System/Library/Fonts/Hiragino Sans GB.ttc", "/System/Library/Fonts/STHeiti Medium.ttc",
              "/System/Library/Fonts/STHeiti Light.ttc", "/Library/Fonts/Arial Unicode.ttf",
              "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _fit(font, s, width):
    if font.getlength(s) <= width:
        return s
    while s and font.getlength(s + "…") > width:
        s = s[:-1]
    return s + "…"


def make_sheets(items, out_dir, exam, level, per_sheet=24):
    """差异拼图：每张 per_sheet 条（2 列），每格=裁图+两行文字（题库/OCR，差异处加【】）。返回生成的文件列表。"""
    from PIL import Image, ImageDraw
    if not items:
        return []
    os.makedirs(out_dir, exist_ok=True)
    cols, cell_w, crop_h, pad = 2, 800, 72, 8
    f, fh = cjk_font(19), cjk_font(22)
    cell_h = crop_h + 2 * 25 + pad * 2
    files = []
    nsheet = (len(items) + per_sheet - 1) // per_sheet
    lvl = {"high": "高", "low": "低"}.get(level, level)
    idx_rows = []
    for s in range(nsheet):
        chunk = items[s * per_sheet:(s + 1) * per_sheet]
        rows = (len(chunk) + cols - 1) // cols
        canvas = Image.new("RGB", (cols * cell_w, 44 + rows * cell_h), "white")
        dr = ImageDraw.Draw(canvas)
        dr.text((10, 10), _fit(fh, "%s 差异拼图·%s %02d/%02d（ocr_candidate 候选差异，非核验；红框=估计位置；上行题库，下行 OCR）" % (
            exam, lvl, s + 1, nsheet), cols * cell_w - 20), font=fh, fill=(0, 0, 0))
        for j, d in enumerate(chunk):
            no = s * per_sheet + j + 1
            r, c = divmod(j, cols)
            x0, y0 = c * cell_w, 44 + r * cell_h
            dr.rectangle([x0 + 1, y0 + 1, x0 + cell_w - 2, y0 + cell_h - 2], outline=(190, 190, 190))
            if d.get("crop_path") and os.path.isfile(d["crop_path"]):
                im = Image.open(d["crop_path"]).convert("RGB")
                sc = min((cell_w - 2 * pad) / float(im.size[0]), crop_h / float(im.size[1]), 2.0)
                im = im.resize((max(1, int(im.size[0] * sc)), max(1, int(im.size[1] * sc))))
                canvas.paste(im, (x0 + pad, y0 + pad))
            else:
                dr.text((x0 + pad, y0 + pad + 20), "（无裁图）", font=f, fill=(120, 120, 120))
            bl, ba, br = d["_bank_mark"]
            ol, ob, orr = d["_ocr_mark"]
            head = "%02d %s p%s %s" % (no, d["qid"].rsplit("-", 1)[-1], d.get("page") if d.get("page") else
                                       (d.get("unit") or "").split(":")[-1], d["category"])
            t1 = "%s｜库：%s【%s】%s" % (head, bl, ba or "（缺）", br)
            t2 = "      OCR：%s【%s】%s｜置信%s 二读%s%s" % (ol, ob or "（缺）", orr, d.get("ocr_conf"),
                                                    {"ocr": "同OCR", "bank": "同题库", "tie": "不定"}.get(d.get("second_read"), "无"),
                                                    "｜位置估计" if d.get("crop_approx") else "")
            dr.text((x0 + pad, y0 + pad + crop_h + 2), _fit(f, t1, cell_w - 2 * pad), font=f, fill=(0, 0, 150))
            dr.text((x0 + pad, y0 + pad + crop_h + 27), _fit(f, t2, cell_w - 2 * pad), font=f, fill=(160, 0, 0))
            d["sheet"] = "%s_%02d.png" % (level, s + 1)
            d["sheet_item"] = no
            idx_rows.append({"sheet": d["sheet"], "item": no, "diff_id": d.get("diff_id"), "qid": d["qid"],
                             "page": d.get("page"), "unit": d.get("unit"), "category": d["category"],
                             "bank_text": d["bank_text"], "ocr_text": d["ocr_text"], "bank_context": d["bank_context"],
                             "ocr_context": d["source_context"], "md_line": d["md_line"], "crop_path": d.get("crop_path"),
                             "grade": d.get("grade"), "evidence_level": "ocr_candidate"})
        fp = os.path.join(out_dir, "%s_%02d.png" % (level, s + 1))
        canvas.save(fp, optimize=True)
        files.append(fp)
    with open(os.path.join(out_dir, "index.jsonl"), "a", encoding="utf-8") as fh_:
        for r in idx_rows:
            fh_.write(json.dumps(r, ensure_ascii=False) + "\n")
    return files


def audit_exam(exam_id, man=None, min_ratio=0.75, work_dir=None, ocr=None):
    """ocr=None：只走文字层（旧行为）；ocr=dict(cache, out_dir, run_new, second_read, min_ratio, dpi, sheet_size,
    sheets, crops)：文字层对不上的行再走 OCR 候选双通道（见文件头）。"""
    t0 = time.time()
    task, idx, infos = source_index(exam_id, man, work_dir)
    seg_bounds = {(a, b_) for a, b_, _ in idx.segs}
    t_idx = time.time() - t0
    qdir = os.path.join(BANK_Q, exam_id)
    invalid = {k.get("old_question_id") for k in (task.get("historical_invalid_keys") or []) if isinstance(k, dict)}
    files = sorted((f for f in glob.glob(os.path.join(qdir, exam_id + "-Q*.md"))
                    if os.path.basename(f)[:-3] not in invalid),  # 主清单登记的历史失效题键（如 Q0/Q24/Q25）不审
                   key=lambda x: int(re.search(r"-Q(\d+)\.md$", x).group(1)) if re.search(r"-Q(\d+)\.md$", x) else 0)
    # ---- 第一道：文字层
    recs, qmeta = [], collections.OrderedDict()
    for f in files:
        qid = os.path.basename(f)[:-3]
        md = open(f, encoding="utf-8").read()
        lines = reading_lines(md, qid)
        qmeta[qid] = {"md_sha256": sha_text(md), "bases": sorted({l["basis"] for l in lines if l["role"] == "stem"})}
        for li, ln in enumerate(lines):
            nxt_disp = re.sub(r"^(\d{1,3}[.．、]|[（(]\d[）)])", "", lines[li + 1]["disp"]) if li + 1 < len(lines) else ""
            al = _best_align(idx, ln, min_ratio)
            stripped = False
            if al is not None and ln.get("alt"):
                alt = dict(ln, disp=ln["alt"]["disp"], canon=ln["alt"]["canon"])
                al2 = _best_align(idx, alt, min_ratio)
                head_diff = any(o[1] <= ln["alt"]["plen"] for o in al["ops"])
                if al2 is not None and (al2["ratio"] >= al["ratio"] + 0.02 or (head_diff and al2["ratio"] >= al["ratio"] - 1e-9)):
                    stripped = True
                    ln, al = alt, al2
            rec = {"qid": qid, "ln": ln, "al": al, "nxt": nxt_disp, "stripped": stripped, "st": collections.Counter()}
            if _ok(al, min_ratio):
                rec["tdiffs"] = _text_layer_diffs(exam_id, qid, ln, al, idx, seg_bounds, nxt_disp, rec["st"])
            recs.append(rec)
    # ---- 第二道：OCR 候选（文字层对不上的行；以及落在 OCR 文字层/乱码字体层上的文字层差异做交叉核对）
    ch, ocr_info = None, None
    if ocr:
        need = [r for r in recs if not _ok(r["al"], min_ratio)]
        xcheck = [d for r in recs for d in r.get("tdiffs", []) if d.get("tier") in ("ocr_layer", "garbled_font")]
        roles = {r["ln"]["role"] for r in need} | {d["role"] for d in xcheck}
        if roles:
            ch = OcrChannel(exam_id, infos, roles, ocr).build()
            if ch.idx is not None:
                for r in need:
                    al2 = _best_align(ch.idx, r["ln"], ocr.get("min_ratio", 0.7))
                    if _ok(al2, ocr.get("min_ratio", 0.7)):
                        r["al_ocr"] = al2
                for d in xcheck:
                    # 文字层本身是 OCR 层/乱码字体：本机 Vision OCR 读出的与题库一致 → 多半是文字层自身的错，降权
                    if len(d["_snip"]) >= 8 and any(ch.idx.label_at(p) and ch.idx.label_at(p).get("sid") == d["source_id"]
                                                    for p in _find_all(ch.idx.C, d["_snip"], 5)):
                        d["flags"].append("vision_ocr_matches_bank")
                        d["priority"] = round(d["priority"] * 0.3, 3)
    # ---- 对不上的样板句（同卷≥3 题出现同一句）
    rep = collections.defaultdict(set)
    for r in recs:
        if not _ok(r["al"], min_ratio) and not r.get("al_ocr"):
            rep[r["ln"]["canon"]].add(r["qid"])
    # ---- 统计与差异
    diffs, odiffs, qstat, tot = [], [], {}, collections.Counter()
    samples = collections.defaultdict(list)  # 不计入分母/未审的行各留几条样例，供人核口径
    by_q = collections.OrderedDict((q, []) for q in qmeta)
    for r in recs:
        by_q[r["qid"]].append(r)
    for qid, rs in by_q.items():
        st = collections.Counter()
        qtext = "".join(r["ln"]["canon"] for r in rs)
        stem_seen = stem_loc = stem_loc_ocr = stem_excl = 0
        for r in rs:
            ln, al = r["ln"], r["al"]
            n = ln["canon"]
            L = len(n)
            st["chars"] += L
            st.update(r["st"])
            if r["stripped"]:
                st["bank_prefix_stripped"] += 1
            is_stem = ln["role"] == "stem"
            if is_stem:
                stem_seen += L
            if _ok(al, min_ratio):
                st["located_chars"] += L
                st["matched_chars"] += al["matched"]
                if is_stem:
                    stem_loc += L
                diffs += r.get("tdiffs", [])
                continue
            if r.get("al_ocr"):
                st["located_ocr_chars"] += L
                st["matched_ocr_chars"] += r["al_ocr"]["matched"]
                st["located_ocr_" + ln["role"]] += L
                if is_stem:
                    stem_loc_ocr += L
                odiffs += ch.diffs_for(exam_id, qid, ln, r["al_ocr"], st, qtext)
                continue
            b = unlocated_bucket(ln, len(rep.get(n, ())))
            key = "excluded_" + b if b else "unlocated_content"
            if len(samples[key]) < 8:
                samples[key].append("%s:%s %s" % (qid.rsplit("-", 1)[-1], ln["md_line"], D.clip(ln["raw"], 70)))
            if b:
                st["excluded_" + b] += L
                st["excluded_chars"] += L
                if is_stem:
                    stem_excl += L
            else:
                st["unlocated_chars"] += L
                st["unlocated_lines"] += 1
                st["unlocated_" + ln["role"]] += L
        st["stem_chars"] = stem_seen
        st["stem_located_chars"] = stem_loc
        st["stem_located_ocr_chars"] = stem_loc_ocr
        st["stem_excluded_chars"] = stem_excl
        stem_den = stem_seen - stem_excl
        qstat[qid] = dict(st, stem_basis=qmeta[qid]["bases"], md_sha256=qmeta[qid]["md_sha256"],
                          stem_audited_text=bool(stem_seen) and stem_loc >= 0.5 * stem_seen,
                          stem_audited=stem_den > 0 and stem_loc + stem_loc_ocr >= 0.5 * stem_den,
                          stem_channel=("text" if stem_loc >= stem_loc_ocr else "ocr") if stem_loc + stem_loc_ocr else None)
        tot.update(st)
    # ---- OCR 差异：第二读法、分级、裁图、拼图
    sheets = []
    if ch is not None:
        try:
            ch.second_read(sorted({d["unit"] for d in odiffs if d.get("unit")}))
            for d in odiffs:
                ch.judge(d)
            odiffs.sort(key=lambda x: (x["grade"] != "high", -x["priority"]))
            for i, d in enumerate(odiffs, 1):
                d["diff_id"] = "%s#o%04d" % (exam_id, i)
                if ocr.get("crops", True):
                    try:
                        d["crop_path"] = ch.crop(d, os.path.join(ocr["out_dir"], "ocr_crops", exam_id), i)
                    except Exception as e:
                        d["crop_error"] = D.clip(repr(e), 120)
            if ocr.get("sheets", True):
                sdir = os.path.join(ocr["out_dir"], "sheets", exam_id)
                if os.path.isfile(os.path.join(sdir, "index.jsonl")):
                    os.remove(os.path.join(sdir, "index.jsonl"))
                for lv in ("high", "low"):
                    items = [d for d in odiffs if d["grade"] == lv and (lv == "high" or ocr.get("sheet_low", True))]
                    sheets += make_sheets(items, sdir, exam_id, lv, ocr.get("sheet_size", 24))
        finally:
            ch.cleanup()
        ocr_info = {"units": ch.stat.get("units", 0), "unit_sources": {k[6:]: v for k, v in ch.stat.items() if k.startswith("units_")},
                    "second_read_units": ch.stat.get("second_read_units", 0),
                    "second_read_available": not ch.stat.get("second_read_unavailable"),
                    "seconds_ocr_text": round(ch.sec["ocr_text"], 2), "seconds_second_read": round(ch.sec["second_read"], 2),
                    "diffs_high": sum(1 for d in odiffs if d["grade"] == "high"),
                    "diffs_low": sum(1 for d in odiffs if d["grade"] == "low"),
                    "passed_by_confusion": {k[9:]: v for k, v in tot.items() if k.startswith("ocr_pass_")},
                    "sheets": [os.path.relpath(p, ocr["out_dir"]) for p in sheets],
                    "sheets_high": sum(1 for p in sheets if os.path.basename(p).startswith("high_")),
                    "sheets_low": sum(1 for p in sheets if os.path.basename(p).startswith("low_"))}
    for d in diffs:
        d.pop("_snip", None)
    for d in odiffs:
        for k in [k for k in d if k.startswith("_")]:
            d.pop(k, None)
    reader = collections.Counter(tuple(v["stem_basis"]) for v in qstat.values())
    pc = collections.Counter()
    for inf in infos:
        for k, v in (inf.get("fine_classes") or {}).items():
            pc[k] += v
    direct = sum(v for k, v in pc.items() if k in D.DIRECT_CLASSES)
    # 审不了/没审全的原因逐条列出
    na = []
    loc_share = tot["located_chars"] / float(tot["chars"] or 1)
    den = tot["chars"] - tot["excluded_chars"]
    audited = tot["located_chars"] + tot["located_ocr_chars"]
    audit_share = audited / float(den or 1)
    no_stem = sorted(q for q, v in qstat.items() if not v["stem_basis"])
    stem_audited = sum(1 for v in qstat.values() if v.get("stem_audited"))
    stem_audited_text = sum(1 for v in qstat.values() if v.get("stem_audited_text"))
    if ocr is None:
        if tot["located_chars"] < 0.05 * (tot["chars"] or 1):
            na.append("原件文字层不可用（页型 %s）；本卷只能看图或 OCR 校对，脚本未审" % dict(pc))
        elif direct < sum(pc.values()) * 0.5:
            na.append("原件约%d%%页无可靠文字层（页型 %s）；这些页上的题面未审" % (
                100 - 100 * direct // max(1, sum(pc.values())), dict(pc)))
    if no_stem:
        na.append("%d 题没取到题面小节（无题面），这些题的题面未审：%s" % (
            len(no_stem), D.clip("、".join(q.rsplit("-", 1)[-1] for q in no_stem), 120)))
    if ocr is None and loc_share < 0.5:
        na.append("默认读法只有 %.1f%% 的字在原件文字层里定位到（<50%%），未定位部分未审" % (100 * loc_share))
    if ocr is not None:
        if audit_share < 0.5:
            na.append("应审字符（去掉题库自注/页眉页脚/图示描述/答案键行/学生手写层后 %d 字）只有 %.1f%% 在原件文字层"
                      "（%.1f%%）或 OCR 候选（%.1f%%）里定位到（<50%%），其余未审" % (
                          den, 100 * audit_share, 100.0 * tot["located_chars"] / (den or 1),
                          100.0 * tot["located_ocr_chars"] / (den or 1)))
        if len(qstat) and stem_audited < 0.5 * len(qstat):
            na.append("题面只审到 %d/%d 题（文字层或 OCR 定位≥50%% 才算）" % (stem_audited, len(qstat)))
    not_auditable = "；".join(na) or None
    res = {"exam": exam_id, "questions": len(files), "stem_questions_audited": stem_audited,
           "stem_questions_audited_text": stem_audited_text,
           "stem_questions_audited_ocr_only": sum(1 for v in qstat.values() if v.get("stem_audited") and not v.get("stem_audited_text")),
           "skipped_historical_invalid_keys": sorted(invalid),
           "questions_without_stem": no_stem, "not_auditable_reasons": na,
           "sources": infos, "index_seconds": round(t_idx, 2),
           "seconds": round(time.time() - t0, 2), "totals": dict(tot),
           "located_share": round(loc_share, 4),
           "audit_share": round(audit_share, 4), "audit_denominator_chars": den,
           "located_text_share_of_denominator": round(tot["located_chars"] / float(den or 1), 4),
           "located_ocr_share_of_denominator": round(tot["located_ocr_chars"] / float(den or 1), 4),
           "excluded_chars": {k[9:]: v for k, v in tot.items() if k.startswith("excluded_") and k != "excluded_chars"},
           "match_in_located": round(tot["matched_chars"] / float(tot["located_chars"] or 1), 4),
           "diff_by_category": {k[5:]: v for k, v in tot.items() if k.startswith("diff_")},
           "ocr_diff_by_category": {k[9:]: v for k, v in tot.items() if k.startswith("ocr_diff_")},
           "ocr_channel": ocr_info, "line_samples": dict(samples),
           "stem_reading_basis": {"|".join(k) or "无题面": v for k, v in reader.items()},
           "source_page_classes": dict(pc), "not_auditable": not_auditable,
           "per_question": qstat}
    return res, diffs + odiffs


def _find_all(s, sub, limit):
    out, p = [], s.find(sub)
    while p >= 0 and len(out) < limit:
        out.append(p)
        p = s.find(sub, p + 1)
    return out


# ---------------------------------------------------------------- 裁图
def crop_diff(d, out_dir, zoom=2.0):
    if not d.get("bbox") or not d.get("source_rel") or not str(d.get("source_rel")).lower().endswith(".pdf"):
        return None
    import fitz
    path = D.locate_source(d["source_rel"])
    if not path:
        return None
    doc = fitz.open(path)
    pg = doc[d["page"] - 1]
    r = fitz.Rect(d["bbox"])
    r = fitz.Rect(max(0, r.x0 - 6), max(0, r.y0 - 6), min(pg.rect.width, r.x1 + 6), min(pg.rect.height, r.y1 + 6))
    os.makedirs(out_dir, exist_ok=True)
    name = "%s_p%03d_%s.png" % (d["qid"], d["page"], hashlib.md5((d["bank_text"] + "|" + d["source_text"]).encode()).hexdigest()[:6])
    fp = os.path.join(out_dir, name)
    pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=r).save(fp)
    return fp


# ---------------------------------------------------------------- eval：doc2md 候选 vs 题库已验收
def candidate_index(cand_exam_dir):
    """候选题级 MD（按页标记切块）→ TextIndex，label={qid,page,class}；另建 sources/*.full.md 全卷语料。"""
    qi = D.TextIndex()
    for f in sorted(glob.glob(os.path.join(cand_exam_dir, "*-Q*.md")) + glob.glob(os.path.join(cand_exam_dir, "00_*.md"))):
        qid = os.path.basename(f)[:-3]
        txt = open(f, encoding="utf-8").read()
        txt = re.split(r"^## 机器自检", txt, flags=re.M)[0]
        parts = re.split(r"<!-- 第(\d+)页 (\S*) -->", txt)
        qi.add_nosep(parts[0], {"qid": qid, "page": None, "class": "head"})
        for i in range(1, len(parts), 3):
            qi.add_nosep(parts[i + 2], {"qid": qid, "page": int(parts[i]), "class": parts[i + 1] or "?"})
        qi.sep()
    qi.build()
    si = D.TextIndex()
    for f in sorted(glob.glob(os.path.join(cand_exam_dir, "sources", "*", "source.full.md"))):
        txt = open(f, encoding="utf-8").read()
        txt = re.sub(r"^# .*\n\n> source_id:.*\n", "", txt)
        parts = re.split(r"<!-- 第(\d+)页 (\S*) -->", txt)
        fmt = "docx" if "\n" in parts[0] and len(parts) == 1 else "head"
        si.add_nosep(parts[0], {"sid": os.path.basename(os.path.dirname(f)), "page": None, "class": fmt})
        for i in range(1, len(parts), 3):
            si.add_nosep(parts[i + 2], {"sid": os.path.basename(os.path.dirname(f)), "page": int(parts[i]),
                                        "class": parts[i + 1] or "?"})
        si.sep()
    si.build()
    return qi, si


# 未定位行里“像题库自写说明”的（来源/状态/N/A/图示描述等）；只用于把未定位部分拆开报，不参与一致率分子
RE_MODEL_NOTE = re.compile(r"来源|E1|E3|E0|N/A|状态|本题|本卷|本页|不得|复核|核对|核验|审计|定位|原页|原图|页图|图示|图中|框线|箭头|"
                           r"候选|转写|载体|角色|细则PDF|细则 PDF|第\s*\d+\s*页|slide|幻灯片|证据|说明|示意|读图|约值|估读|嵌图|"
                           r"要点框|（图|【原页|【表|【图|答案键|选择题答案|不是|非独立|不等于|未提供|缺源|Luna|Sol|Claude|Codex")
RE_BANK_KEY = [re.compile(r"^\s*(\d{1,2})\s*[．.、]\s*\**([A-D])\**\s*$"), re.compile(r"答案[：:\s]*\**([A-D])\**"),
               re.compile(r"第\s*(\d{1,2})\s*题[^A-D]{0,12}?\**([A-D])\**")]


def bank_choice_key(md, n):
    for role, title, body, basis in reading_sections(md):
        if role not in ("e3", "e1"):
            continue
        for l in body.splitlines():
            s = re.sub(r"^[-*]\s+", "", D.plain(l).strip())
            m = RE_BANK_KEY[0].match(s)
            if m and int(m.group(1)) == n:
                return m.group(2)
            m = re.match(r"^\s*(?:【答案】|(?:选择题)?(?:官方)?答案(?:键)?[：:])\s*\**([A-D])(?![A-Za-z])", s)
            if m:
                return m.group(1)
            m = RE_BANK_KEY[2].search(s)
            if m and int(m.group(1)) == n and "答案" in s:
                return m.group(2)
    return None


def _located(al, n, min_ratio):
    return al is not None and al["ratio"] >= min_ratio and al.get("longest", 0) >= min(8, max(4, len(n) // 2))


def candidate_lines(md):
    """候选题级 MD 的内容行（题面/E1/E3/讲评节），去掉身份、指引、自检、占位与图片行。"""
    out = []
    keep = False
    for raw in md.splitlines():
        m = re.match(r"^## (.+)$", raw)
        if m:
            t = m.group(1)
            keep = t in (D.LAYER_TITLE["paper"], D.LAYER_TITLE["teacher"], D.LAYER_TITLE["ocr"], D.LAYER_TITLE["E1"],
                         D.LAYER_TITLE["E3"], D.LAYER_TITLE["lecture"], D.LAYER_TITLE["aux"])
            continue
        s = re.sub(r"^(〔(OCR候选|字体映射疑误)〕)+", "", raw.strip())
        if not keep or not s or s.startswith(("#", "<!--", "![", "〔", "- 选择题答案键", "```")):
            continue
        d = D.norm_display(s)
        if len(d) >= 8:
            out.append(D.canon(d))
    return out


def eval_exam(exam_id, cand_root, min_ratio=0.5):
    """一致率（召回：题库默认读法的字有多少在候选全卷语料里找到）、未定位占比（再拆“像题库说明”与其他）、
    拆题率（两个方向：题库行落在同号候选题的比例；候选题内容落在同号题库题的比例=切题精度）、答案键一致。
    8 字以下短行（如“答案：B”）不计入一致率与拆题率，答案键另做字母比对。"""
    ced = os.path.join(cand_root, exam_id)
    qi, si = candidate_index(ced)
    cand_sc = json.load(open(os.path.join(ced, "selfcheck.json"), encoding="utf-8"))
    files = sorted(glob.glob(os.path.join(BANK_Q, exam_id, exam_id + "-Q*.md")))
    tot = collections.Counter()
    by_class = collections.defaultdict(collections.Counter)
    by_fine = collections.defaultdict(collections.Counter)
    unloc_samples, keys = [], collections.Counter()
    bank_idx = D.TextIndex()
    for f in files:
        qid = os.path.basename(f)[:-3]
        md = open(f, encoding="utf-8").read()
        lines = reading_lines(md, qid)
        for ln in lines:
            bank_idx.add_nosep(ln["disp"], {"qid": qid})
        bank_idx.sep()
        for ln in lines:
            n = ln["canon"]
            if len(n) < 8:
                tot["short_lines_skipped"] += 1
                continue
            tot["chars"] += len(n)
            tot["chars_" + ln["role"]] += len(n)
            al = si.align(n)
            if not _located(al, n, min_ratio):
                tot["unlocated"] += len(n)
                tot["unlocated_" + ln["role"]] += len(n)
                note = bool(RE_MODEL_NOTE.search(ln["raw"]))
                tot["unlocated_note_like" if note else "unlocated_other"] += len(n)
                if not note and len(unloc_samples) < 30:
                    unloc_samples.append({"qid": qid, "role": ln["role"], "line": D.clip(ln["raw"], 90, "questions/%s/%s.md:%s" % (exam_id, qid, ln["md_line"]))})
                continue
            tot["located"] += len(n)
            tot["matched"] += al["matched"]
            tot["matched_" + ln["role"]] += al["matched"]
            lab = si.label_at(al["start"] + 1) or {}
            cls = D.COARSE.get(lab.get("class"), lab.get("class"))
            by_class[cls]["chars"] += len(n)
            by_class[cls]["matched"] += al["matched"]
            by_fine[lab.get("class")]["chars"] += len(n)
            by_fine[lab.get("class")]["matched"] += al["matched"]
            aq = qi.align(n, allow=lambda l, q=qid: l is not None and l.get("qid") == q)
            tot["split_base"] += len(n)
            if _located(aq, n, min_ratio):
                tot["split_ok"] += len(n)
        m = re.search(r"-Q(\d+)$", qid)
        if m:
            qn = int(m.group(1))
            bk = bank_choice_key(md, qn)
            cf = os.path.join(ced, qid + ".md")
            ck = None
            if os.path.isfile(cf):
                mm = re.search(r"第%d题 \*\*([A-D])\*\*" % qn, open(cf, encoding="utf-8").read())
                ck = mm.group(1) if mm else None
            if bk:
                keys["bank_has"] += 1
                keys["agree" if ck == bk else ("candidate_missing" if ck is None else "disagree")] += 1
    bank_idx.build()
    # 反方向：候选题内容是否落在同号题库题（切题精度）
    for cf in sorted(glob.glob(os.path.join(ced, exam_id + "-Q*.md"))):
        qid = os.path.basename(cf)[:-3]
        for n in candidate_lines(open(cf, encoding="utf-8").read()):
            al = bank_idx.align(n)
            if not _located(al, n, 0.6):
                tot["cand_unlocated"] += len(n)
                continue
            tot["cand_located"] += len(n)
            same = bank_idx.align(n, allow=lambda l, q=qid: l is not None and l.get("qid") == q)
            if _located(same, n, 0.6):
                tot["cand_same_q"] += len(n)
    r = lambda a, b: round(a / float(b), 4) if b else None
    return {"exam": exam_id, "bank_questions": len(files), "candidate_questions": cand_sc.get("questions"),
            "candidate_selfcheck_hard_fail": cand_sc.get("hard_fail"),
            "candidate_score_total": cand_sc.get("score_total_resolved"),
            "candidate_score_unresolved": cand_sc.get("score_unresolved"),
            "chars": tot["chars"], "short_lines_skipped": tot["short_lines_skipped"],
            "recall_all": r(tot["matched"], tot["chars"]), "recall_located": r(tot["matched"], tot["located"]),
            "unlocated_share": r(tot["unlocated"], tot["chars"]),
            "unlocated_note_like_share": r(tot["unlocated_note_like"], tot["chars"]),
            "unlocated_other_share": r(tot["unlocated_other"], tot["chars"]),
            "split_rate": r(tot["split_ok"], tot["split_base"]),
            "split_precision": r(tot["cand_same_q"], tot["cand_located"]),
            "candidate_chars_not_in_bank_share": r(tot["cand_unlocated"], tot["cand_located"] + tot["cand_unlocated"]),
            "by_role": {k: {"chars": tot["chars_" + k], "recall_all": r(tot["matched_" + k], tot["chars_" + k]),
                            "unlocated_share": r(tot["unlocated_" + k], tot["chars_" + k])}
                        for k in ("stem", "e1", "e3", "student") if tot["chars_" + k]},
            "by_page_type": {k: dict(v, ratio=r(v["matched"], v["chars"])) for k, v in by_class.items()},
            "by_fine_class": {k: dict(v, ratio=r(v["matched"], v["chars"])) for k, v in by_fine.items()},
            "answer_key": dict(keys), "unlocated_samples": unloc_samples}


# ---------------------------------------------------------------- 命令行
def accepted_exams(man):
    return [t["exam_id"] for t in man["tasks"] if t.get("status") == "已验收"]


def write_top_md(path, top, crops):
    L = ["# 回溯体检 TOP 差异（machine_diff，须人工看原页裁定）", "",
         "> 证据等级：脚本比对差异，不是已核实错误；“已验收”也不等于主代理已核原页。",
         "> 名次口径：按优先级排序后，同卷同题同一对（题库字→原件字）只保留一条，记“去重后第 N”；“未去重第 N”是去重前的位置。",
         "> 题库文件行号为 1 起、指向差异所在的那一行；上下文里的〔前略〕〔后略〕表示窗口截断。", ""]
    for i, d in enumerate(top, 1):
        L.append("## %d. %s %s（%s｜%s）" % (i, d["qid"], d["category"], d["role"], D.clip(d["section"], 30)))
        L.append("- 名次：去重后第 %s（未去重第 %s）；题库：`%s` → 原件：`%s`（%s 第%s页，%s，层级 %s，行比 %.2f，优先级 %.2f）" % (
            d.get("rank_dedup"), d.get("rank_raw"), d["bank_text"] or "∅", d["source_text"] or "∅", d["source_role"],
            d["page"], d["page_class"], d.get("tier"), d["line_ratio"], d["priority"]))
        L.append("- 题库上下文：%s" % d["bank_context"])
        L.append("- 原件上下文：%s" % d["source_context"])
        L.append("- 题库文件行：questions/%s/%s.md:%s；读取依据 %s；标记 %s" % (d["exam"], d["qid"], d["md_line"], d["basis"],
                                                                     ",".join(d["flags"]) or "无"))
        if crops.get(i):
            L.append("- 裁图：%s" % crops[i])
        L.append("")
    open(path, "w", encoding="utf-8").write("\n".join(L))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = "audit"
    if argv and argv[0] in ("audit", "eval", "ocr-confusions"):
        mode = argv.pop(0)
    ap = argparse.ArgumentParser(description="已验收题库卷回溯体检（只读，只写 --out-dir）。第一个参数可写 audit（默认，体检）、"
                                             "eval（doc2md 候选对题库的一致率/拆题率，需 --candidate-dir）或 ocr-confusions"
                                             "（重统计 OCR 混淆对）。退出码 0 完成；2 参数错误/拒绝写入/异常")
    ap.add_argument("--exam", action="append", help="只查这些卷（可多次）；默认全部已验收卷")
    ap.add_argument("--out-dir", default=None, help="输出目录（必须给出；或设环境变量 DOC2MD_OUT，则默认其下 retro_audit/ 或 eval/）")
    ap.add_argument("--crops", type=int, default=30, help="文字层通道：为优先级最高的 N 条差异裁原页图（仅 PDF；0=不裁）")
    ap.add_argument("--top", type=int, default=20, help="文字层通道 TOP 清单条数")
    ap.add_argument("--min-ratio", type=float, default=0.75, help="行对齐率低于此值视为未定位，不报差异")
    ap.add_argument("--ocr", choices=("auto", "off"), default="auto",
                    help="OCR 双通道：auto（默认）=文字层对不上的行改对 OCR 候选；off=只走文字层（2026-09-23 旧行为）")
    ap.add_argument("--no-run-ocr", action="store_true", help="只用题库已有 OCR 与本输出目录缓存，不新跑 ocr-vision")
    ap.add_argument("--second-read", choices=("auto", "off"), default="auto",
                    help="第二读法（swiftc 现场编译的 Vision 行框小工具，给裁图定位、置信度与高/低分级）；off 则只按文字规则分级")
    ap.add_argument("--ocr-min-ratio", type=float, default=0.7, help="OCR 通道行对齐率门槛（默认 0.7）")
    ap.add_argument("--sheet-size", type=int, default=24, help="每张差异拼图的条数（20—30 为宜，默认 24）")
    ap.add_argument("--no-sheet-low", action="store_true", help="低等级差异不拼图（仍写 jsonl 与裁图）")
    ap.add_argument("--ocr-cache", default=None, help="OCR 文字/行框缓存目录（默认 --out-dir/_ocr_cache；可指向上次输出目录的缓存以复用，"
                                                      "受同一写入护栏约束）")
    ap.add_argument("--candidate-dir", help="eval 模式：doc2md 输出根目录（含 <EXAM>/）")
    a = ap.parse_args(argv)
    dep = D.check_deps()
    if dep:
        print("运行环境不满足：%s" % dep)
        return 2
    out = a.out_dir or (DEFAULT_OUT if mode == "audit" else (os.path.join(D.DEFAULT_OUT, mode) if D.DEFAULT_OUT else None))
    try:
        D.guard_out_dir(out)
        if a.ocr_cache:
            D.guard_out_dir(a.ocr_cache)
    except SystemExit as e:
        print(e)
        return 2
    os.makedirs(out, exist_ok=True)
    try:
        return _run(mode, a, out)
    except SystemExit as e:
        print(e)
        return 2
    except Exception as e:
        print("体检异常（%s: %s）；产物不完整。" % (type(e).__name__, e))
        return 2


def ocr_confusion_stats(man, out):
    """重统计 OCR 混淆对：①原生文字层可靠页（题库有 OCR）的原生字 vs OCR；②扫描类页的题库 OCR vs 题库默认题面。
    只输出候选表（ocr_confusions.json），是否并入 OCR_CONFUSIONS 由人定。"""
    import fitz
    pairs, ctxs, src = collections.Counter(), collections.defaultdict(set), collections.defaultdict(set)

    def feed(tag, index, lines):
        for line in lines:
            d = D.norm_display(line)
            if len(d) < 6:
                continue
            al = index.align(D.canon(d))
            if al is None or al["ratio"] < 0.8:
                continue
            for _t, a0, a1, b0, b1 in al["ops"]:
                o, g = d[a0:a1], index.D[b0:b1].replace("\x00", "")
                if max(len(o), len(g)) <= 3 and (o or g):
                    pairs[(g, o)] += 1
                    ctxs[(g, o)].add(d[max(0, a0 - 6):a1 + 6])
                    src[(g, o)].add(tag)
    seen = set()
    for t in man["tasks"]:
        stem_idx = None
        for role, lst in t["sources"].items():
            for s in lst:
                sid, p = s.get("source_id"), D.locate_source(s["rel_path"])
                if not p or not p.lower().endswith(".pdf") or sid in seen:
                    continue
                seen.add(sid)
                vt = os.path.join(D.BANK, "evidence", sid, "visual_transcript")
                if not glob.glob(os.path.join(vt, "p*.ocr.txt")):
                    continue
                try:
                    blocks, _f, pages, _i = D.extract_source(p, "pdf", sid, asset_root=None, ocr_dirs=[], render_dpi=0)
                except Exception:
                    continue
                for pg in pages:
                    txt, _x = D.find_ocr_text(sid, pg["page"], [vt])
                    if not txt:
                        continue
                    lines = D.ocr_paras("\n".join(_ocr_txt_lines(txt)))
                    if pg["fine_class"] == "text_reliable":
                        ix = D.TextIndex()
                        for b in blocks:
                            if b.get("page") == pg["page"] and b["kind"] in ("p", "textbox", "table"):
                                ix.add(b.get("text", ""), {})
                        ix.build()
                        feed("native", ix, lines)
                    elif role in PAPER_ROLES and t.get("status") == "已验收" and pg["fine_class"] not in OcrChannel.NATIVE:
                        if stem_idx is None:
                            stem_idx = D.TextIndex()
                            for f in glob.glob(os.path.join(BANK_Q, t["exam_id"], t["exam_id"] + "-Q*.md")):
                                for ln in reading_lines(open(f, encoding="utf-8").read(), os.path.basename(f)[:-3]):
                                    if ln["role"] == "stem" and not ln.get("ocr_sub"):
                                        stem_idx.add_nosep(ln["disp"], {})
                                stem_idx.sep()
                            stem_idx.build()
                        feed("bank_stem", stem_idx, lines)
    rows = [{"original": k[0], "ocr": k[1], "count": v, "distinct_contexts": len(ctxs[k]), "from": sorted(src[k]),
             "examples": sorted(ctxs[k])[:3]} for k, v in pairs.most_common()]
    fp = os.path.join(out, "ocr_confusions.json")
    json.dump({"generated_by": "bank_retro_audit.py ocr-confusions", "note": "原字→OCR 字；候选表，须人工挑选后并入 OCR_CONFUSIONS",
               "rows": rows}, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("OCR 混淆对 %d 种（≥2 处上下文的 %d 种）；明细 %s" % (len(rows), sum(1 for r in rows if r["distinct_contexts"] >= 2), fp))
    return 0


def write_ocr_md(path, odiffs):
    L = ["# OCR 双通道高等级差异（ocr_candidate，须人工看裁图/原页裁定）", "",
         "> 证据等级：ocr_candidate——题库默认读法与 OCR 候选的差异，不是已核实错误；不得标成已核验。",
         "> 高等级=第二读法同样读成 OCR 那样、行置信 1.0、1—4 字的汉字/数字错漏增，且无表格/题号/标点/长段等降级标记。",
         "> 上下文里的〔前略〕〔后略〕表示窗口截断。", ""]
    for d in odiffs:
        L.append("## %s %s %s（%s｜%s）" % (d.get("diff_id"), d["qid"], d["category"], d["role"], D.clip(d["section"], 30)))
        L.append("- 题库：`%s` → OCR：`%s`（%s，第%s页/单元 %s，OCR 来源 %s，置信 %s，第二读法 %s，行比 %.2f）" % (
            d["bank_text"] or "∅", d["ocr_text"] or "∅", d.get("source_rel"), d.get("page"), d.get("unit"),
            d.get("ocr_src"), d.get("ocr_conf"), d.get("second_read"), d["line_ratio"]))
        L.append("- 题库上下文：%s" % d["bank_context"])
        L.append("- OCR 上下文：%s" % d["source_context"])
        L.append("- 题库文件行：questions/%s/%s.md:%s；标记 %s；拼图 %s 第 %s 格；裁图 %s" % (
            d["exam"], d["qid"], d["md_line"], ",".join(d["flags"]) or "无", d.get("sheet"), d.get("sheet_item"),
            d.get("crop_path")))
        L.append("")
    open(path, "w", encoding="utf-8").write("\n".join(L))


def _run(mode, a, out):
    man = D.load_manifest()
    exams = a.exam or accepted_exams(man)
    t0 = time.time()
    if mode == "ocr-confusions":
        return ocr_confusion_stats(man, out)
    if mode == "eval":
        if not a.candidate_dir:
            print("eval 需要 --candidate-dir")
            return 2
        rows = []
        for e in exams:
            rows.append(eval_exam(e, a.candidate_dir))
            x = rows[-1]
            print("%s 召回(全部)=%s 召回(已定位)=%s 未定位=%s（像说明%s/其他%s） 拆题率=%s 切题精度=%s 答案键=%s 候选硬失败=%d" % (
                e, x["recall_all"], x["recall_located"], x["unlocated_share"], x["unlocated_note_like_share"],
                x["unlocated_other_share"], x["split_rate"], x["split_precision"], x["answer_key"],
                len(x["candidate_selfcheck_hard_fail"] or [])))
        json.dump({"rows": rows, "seconds": round(time.time() - t0, 2)}, open(os.path.join(out, "eval.json"), "w",
                                                                           encoding="utf-8"), ensure_ascii=False, indent=1)
        print("摘要：%d 卷；明细 %s；一致率为召回口径（题库字在候选中找到的比例），未定位部分单列。" % (len(rows), os.path.join(out, "eval.json")))
        return 0
    ocr = None
    if a.ocr != "off":
        ocr = {"cache": a.ocr_cache or os.path.join(out, "_ocr_cache"), "out_dir": out, "run_new": not a.no_run_ocr,
               "second_read": a.second_read != "off", "min_ratio": a.ocr_min_ratio, "dpi": 200,
               "sheet_size": max(5, min(40, a.sheet_size)), "sheets": True, "crops": True,
               "sheet_low": not a.no_sheet_low}
        for sub in ("sheets", "ocr_crops"):
            for e in exams:
                import shutil
                shutil.rmtree(os.path.join(out, sub, e), ignore_errors=True)
    all_diffs, per = [], []
    status = {t["exam_id"]: t.get("status") for t in man["tasks"]}
    work = os.path.join(out, "_work_legacy")
    try:
        for e in exams:
            try:
                res, diffs = audit_exam(e, man, a.min_ratio, work_dir=work, ocr=ocr)
            except SystemExit as ex:
                per.append({"exam": e, "error": str(ex)})
                continue
            res["manifest_status"] = status.get(e)
            per.append(res)
            all_diffs += diffs
            oc = res.get("ocr_channel") or {}
            print("%s 题%d 题面审到%d（文字层%d） 应审字定位%.1f%%（文字层%.1f%%+OCR%.1f%%） 文字层差异%s OCR差异 高%s/低%s 拼图%s 用时%.1fs%s" % (
                e, res["questions"], res["stem_questions_audited"], res["stem_questions_audited_text"],
                100 * res["audit_share"], 100 * res["located_text_share_of_denominator"],
                100 * res["located_ocr_share_of_denominator"], res["diff_by_category"], oc.get("diffs_high", 0),
                oc.get("diffs_low", 0), len(oc.get("sheets", [])), res["seconds"],
                "  〔未审全：%s〕" % D.clip(res["not_auditable"], 80) if res["not_auditable"] else ""), flush=True)
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)  # doc/rtf 转换副本用完即删
    with open(os.path.join(out, "retro_audit.jsonl"), "w", encoding="utf-8") as fh:
        for d in all_diffs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    tdiffs = [d for d in all_diffs if d.get("channel", "text_layer") == "text_layer"]
    odiffs = [d for d in all_diffs if d.get("channel") == "ocr"]
    ordered = sorted(tdiffs, key=lambda x: -x["priority"])
    seen, top = set(), []
    for raw_i, d in enumerate(ordered, 1):
        k = (d["exam"], d["qid"], d["bank_text"], d["source_text"])
        if k in seen:
            continue
        seen.add(k)
        d["rank_raw"] = raw_i
        d["rank_dedup"] = len(top) + 1
        top.append(d)
        if len(top) >= max(a.top, a.crops):
            break
    crops = {}
    for i, d in enumerate(top[:a.crops], 1):
        try:
            fp = crop_diff(d, os.path.join(out, "crops"))
            if fp:
                crops[i] = fp
                d["crop_path"] = fp
        except Exception:
            pass
    cat_tot = collections.Counter(d["category"] for d in tdiffs)
    tot_chars = sum(p.get("totals", {}).get("chars", 0) for p in per)
    loc_chars = sum(p.get("totals", {}).get("located_chars", 0) for p in per)
    loc_ocr = sum(p.get("totals", {}).get("located_ocr_chars", 0) for p in per)
    den = sum(p.get("audit_denominator_chars", 0) for p in per)
    reader = collections.Counter()
    for p in per:
        for k, v in p.get("stem_reading_basis", {}).items():
            reader[k] += v
    na = [p for p in per if p.get("not_auditable")]
    high = [d for d in odiffs if d.get("grade") == "high"]
    summ = {"generated_by": "bank_retro_audit.py", "doc2md": D.VERSION, "manifest_updated_at": man.get("updated_at"),
            "exams": len(per), "seconds_total": round(time.time() - t0, 2), "diffs_total": len(tdiffs),
            "diff_by_category": dict(cat_tot), "chars_total": tot_chars, "located_chars": loc_chars,
            "located_share": round(loc_chars / float(tot_chars or 1), 4), "stem_reading_basis": dict(reader),
            "audit_denominator_chars": den, "located_ocr_chars": loc_ocr,
            "audit_share": round((loc_chars + loc_ocr) / float(den or 1), 4),
            "ocr_mode": a.ocr, "ocr_diffs_total": len(odiffs), "ocr_diffs_high": len(high),
            "ocr_diffs_low": len(odiffs) - len(high),
            "ocr_diff_by_category": dict(collections.Counter(d["category"] for d in odiffs)),
            "sheets_total": sum(len((p.get("ocr_channel") or {}).get("sheets", [])) for p in per),
            "sheets_high": sum((p.get("ocr_channel") or {}).get("sheets_high", 0) for p in per),
            "questions_total": sum(p.get("questions", 0) for p in per),
            "stem_questions_audited_total": sum(p.get("stem_questions_audited", 0) for p in per),
            "stem_questions_audited_text_total": sum(p.get("stem_questions_audited_text", 0) for p in per),
            "not_auditable_exams": [{"exam": p["exam"], "reasons": p.get("not_auditable_reasons")} for p in na],
            "evidence_level": "文字层差异 machine_diff、OCR 通道差异 ocr_candidate：都是脚本比对差异，不是已核实错误；"
                              "门全过也只说明机械层没有发现回退。",
            "denominator_basis": "audit_share=（文字层定位字+OCR 定位字）/（全部默认读法字 − 两道都对不上的题库自注、"
                                 "页眉页脚、图示描述、答案键行、学生手写层）；located_share 为旧口径（文字层定位字/全部字）",
            "rank_basis": "top 只排文字层差异：按优先级降序、同卷同题同一对差异去重；每条带 rank_dedup 与 rank_raw；"
                          "OCR 差异见 ocr_diffs.md 与 sheets/",
            "per_exam": [{k: p.get(k) for k in ("exam", "questions", "stem_questions_audited", "stem_questions_audited_text",
                                                "stem_questions_audited_ocr_only", "seconds", "located_share", "audit_share",
                                                "audit_denominator_chars", "located_text_share_of_denominator",
                                                "located_ocr_share_of_denominator", "excluded_chars",
                                                "match_in_located", "diff_by_category", "ocr_diff_by_category",
                                                "ocr_channel", "stem_reading_basis", "not_auditable", "error",
                                                "manifest_status")}
                         for p in per],
            "top": top[:a.top]}
    json.dump(summ, open(os.path.join(out, "summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(per, open(os.path.join(out, "per_exam_detail.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    write_top_md(os.path.join(out, "top.md"), top[:a.top], crops)
    if ocr is not None:
        write_ocr_md(os.path.join(out, "ocr_diffs.md"), high)
    print("摘要：%d 卷 %d 题，题面审到 %d 题（文字层 %d）；文字层差异 %d 条 %s；OCR 差异 高 %d/低 %d，拼图 %d 张（高 %d）；"
          "应审字定位 %.1f%%（旧口径文字层 %.1f%%）；总用时 %.1fs。" % (
              len(per), summ["questions_total"], summ["stem_questions_audited_total"],
              summ["stem_questions_audited_text_total"], len(tdiffs), dict(cat_tot), len(high), len(odiffs) - len(high),
              summ["sheets_total"], summ["sheets_high"], 100.0 * summ["audit_share"], 100.0 * summ["located_share"],
              summ["seconds_total"]))
    if na:
        print("未审全 %d 卷：%s" % (len(na), "、".join(p["exam"] for p in na)))
    print("文字层差异为 machine_diff、OCR 差异为 ocr_candidate，须人工看原页/拼图裁定；门全过也只说明机械层没有发现回退。明细 %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
