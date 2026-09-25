#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21 · 共性问题修复（第一步）。

修复三件事，全部可逐条复核：

A. 头尾配对状态矛盾
   头部 `## 配对状态`（10_pair.py 写的）与尾部 `## 质量标记 / rubric_status: 暂未配对`
   （09_split.py 的硬编码占位）互相冲突：1687 份尾部全部写"暂未配对"，
   其中 263 份头部写"已匹配正式材料"。
   → 尾部改为**从 rubric_links.csv 当前配对记录派生**的同一字段。
     不把候选升级为正式细则；不凭文件名给 E1。

B. 题目原文混层
   `## 题目原文` 里同时塞了 原卷 / OCR候选 / 教师版 / 评分材料 / 参考答案 / 讲评。
   实测 467 份混入"评分材料"、323 份混入"教师版"、82 份混入"参考答案"、66 份混入"讲评"。
   → 按角色拆分为独立小节：原卷(native) / 原卷OCR候选 / 非原卷题面 / 评分 / 答案 / 讲评。
     原始文本逐字保留，只搬家不改字。

C. 图像依赖只给整个 source 目录
   → 用 evidence/{sid}/native_text/pages.jsonl 的逐页文本块把题块定位到具体页，
     输出 `assets/{sid}/pages/pNNN.png` 与 `evidence/{sid}/pages/pNNN.png`，
     并列出该页 figure_objects 数量。

用法：
  /usr/bin/python3 31_fix_question_files.py --dry-run --limit 30 --out-dir /tmp/x
  /usr/bin/python3 31_fix_question_files.py
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

RE_SECTION = re.compile(r"^## (.+)$", re.M)
HEAD_RE = re.compile(
    r"^### 来源：`(?P<path>.*?)`（角色 (?P<role>\S+?) / (?P<variant>\S+?)，位置 (?P<loc>[^，]*)(?P<rest>[^\n]*)）\s*$",
    re.M)

BUCKET = {
    "原卷": "yuanjuan",
    "教师版": "teacher",
    "评分材料": "rubric",
    "评分细则_分题切片": "rubric",
    "阅卷总结": "rubric",
    "参考答案": "answer",
    "讲评": "lecture",
    "分题切片_待定": "pending",
}

BUCKET_TITLE = {
    "yuanjuan": "题目原文（原卷·native，读取优先）",
    "ocr": "原卷 OCR 候选（未逐字对照，不得直接采用）",
    "teacher": "教师版题面来源（含答案，须回原卷核实）",
    "rubric": "评分材料来源块（原样保留，配对状态见下）",
    "answer": "参考答案来源块（不得当作评分依据）",
    "lecture": "讲评来源块（含答案与解析，不得当作题面）",
    "pending": "待确认材料来源块（角色未定，须人工裁决）",
}

BUCKET_NOTE = {
    "yuanjuan": "本节只放原卷角色的原生文字层；OCR 候选与其它角色另列下方各节。",
    "ocr": "OCR 候选存在真实错字与串行（见 README 第 6 节），回原页对照前不得采用。",
    "teacher": "教师版把题面与答案排在同一块，整块取用会夹带答案。",
    "rubric": "这些块来自评分/阅卷文件，不是题面；不得插入书稿的题目原文。",
    "answer": "参考答案不等于正式细则。",
    "lecture": "讲评块常把题面与解析连写，不能当作题面。",
    "pending": "角色未定，须人工裁决后再归位。",
}

NO_YUANJUAN_WARN = (
    "\n> ⚠ 本题未取得「原卷」角色文本；下方各节均非原卷，"
    "题面须回原卷核实后方可使用。\n"
)

# bank.py 等读取器据此选择题面小节，不默认吐出全部重复版本
GUIDE_TITLE = "读取指引（机器可读）"


def build_guide(buckets, head_st):
    if buckets.get("yuanjuan"):
        adopted = BUCKET_TITLE["yuanjuan"]
        adopted_src = "原卷 / native"
    elif buckets.get("teacher"):
        adopted = BUCKET_TITLE["teacher"]
        adopted_src = "教师版 / native（无原卷，含答案风险）"
    elif buckets.get("ocr"):
        adopted = BUCKET_TITLE["ocr"]
        adopted_src = "原卷 / ocr_candidate（无原生文字层）"
    else:
        adopted = ""
        adopted_src = "无（本题来源块均非题面）"
    alt = []
    for k in ("teacher", "ocr"):
        if buckets.get(k) and BUCKET_TITLE[k] != adopted:
            alt.append("`%s`" % BUCKET_TITLE[k])
    lines = [
        "\n## %s\n" % GUIDE_TITLE,
        "- 采用题面小节: %s" % ("`%s`" % adopted if adopted else "无"),
        "- 采用题面来源性质: %s" % adopted_src,
        "- 备选题面小节: %s" % ("、".join(alt) if alt else "无"),
        "- 不得当作题面: `%s`、`%s`、`%s`、`%s`" % (
            BUCKET_TITLE["lecture"], BUCKET_TITLE["answer"],
            BUCKET_TITLE["rubric"], BUCKET_TITLE["pending"]),
        "- 评分关系状态: %s" % head_st,
        "",
    ]
    return "\n".join(lines), adopted, adopted_src


def split_sections(md):
    """返回 [(title, body)]，title 不含 '## '。"""
    ms = list(RE_SECTION.finditer(md))
    out = []
    for i, m in enumerate(ms):
        e = ms[i + 1].start() if i + 1 < len(ms) else len(md)
        out.append((m.group(1).strip(), md[m.end():e]))
    return out


def parse_blocks(body):
    """把题目原文区拆成 [(match, full_text)]。"""
    ms = list(HEAD_RE.finditer(body))
    out = []
    for i, m in enumerate(ms):
        s = m.start()
        e = ms[i + 1].start() if i + 1 < len(ms) else len(body)
        out.append((m, body[s:e].rstrip("\n")))
    return out


def norm(s):
    return re.sub(r"\s+", "", s or "")


class PageIndex:
    """source_id -> [(page, normalized_page_text)]，用于把题块定位到页。"""

    def __init__(self):
        self.cache = {}

    def pages(self, sid):
        if sid in self.cache:
            return self.cache[sid]
        fp = os.path.join(P.EVID_DIR, sid, "native_text", "pages.jsonl")
        out = []
        if os.path.isfile(fp):
            with open(fp, encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        o = json.loads(ln)
                    except Exception:
                        continue
                    t = "".join(b.get("text", "") for b in (o.get("text_blocks") or []))
                    out.append((o.get("page"), norm(t)))
        self.cache[sid] = out
        return out

    def locate(self, sid, block_text):
        pages = self.pages(sid)
        if not pages:
            return []
        nb = norm(block_text)
        if len(nb) < 20:
            return []
        probes = [nb[:120], nb[:60], nb[:40]]
        hits = []
        for pno, ptxt in pages:
            if not ptxt:
                continue
            for pr in probes:
                if pr and pr in ptxt:
                    hits.append(pno)
                    break
        return sorted({h for h in hits if h is not None})


def load_figure_pages(sid):
    fp = os.path.join(P.ASSET_DIR, sid, "figures.jsonl")
    out = defaultdict(int)
    if os.path.isfile(fp):
        with open(fp, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                out[o.get("page")] += 1
    return dict(out)


def render_asset_lines(sid, pages):
    figs = load_figure_pages(sid)
    lines = []
    for p in pages:
        a = "assets/%s/pages/p%03d.png" % (sid, p)
        e = "evidence/%s/pages/p%03d.png" % (sid, p)
        have_a = os.path.isfile(os.path.join(P.OUT_ROOT, a))
        have_e = os.path.isfile(os.path.join(P.OUT_ROOT, e))
        parts = []
        if have_a:
            parts.append("`%s`" % a)
        if have_e:
            parts.append("`%s`" % e)
        if not parts:
            parts.append("（本页无渲染图）")
        seg = "第 %d 页：" % p + " / ".join(parts)
        fig = figs.get(p, 0)
        if fig:
            seg += "；figure_objects=%d" % fig
        lines.append(seg)
    return lines


def derive_rubric_status():
    fp = os.path.join(P.INDEX_DIR, "rubric_links.csv")
    st = {}
    if os.path.isfile(fp):
        with open(fp, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                v = r.get("exam_rubric_status") or ""
                if v:
                    st[r["question_id"]] = v
    return st


def load_rel2sid():
    m = {}
    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            m.setdefault(r["rel_path"], r["source_id"])
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--only", default="")
    ap.add_argument("--report", default="")
    a = ap.parse_args()

    rub = derive_rubric_status()
    rel2sid = load_rel2sid()
    pi = PageIndex()

    files = sorted(glob.glob(os.path.join(P.Q_DIR, "*", "*.md")))
    if a.only:
        files = [f for f in files if a.only in f]
    if a.limit:
        files = files[:a.limit]

    log = []
    stats = defaultdict(int)
    for fp in files:
        qid = os.path.basename(fp)[:-3]
        with open(fp, encoding="utf-8") as fh:
            md = fh.read()
        secs = split_sections(md)
        titles = [s[0] for s in secs]
        if "题目原文" not in titles:
            stats["跳过_无题目原文区"] += 1
            continue
        head_st = rub.get(qid, "暂未找到")

        body = secs[titles.index("题目原文")][1]
        blocks = parse_blocks(body)
        buckets = defaultdict(list)
        page_hits = defaultdict(set)
        old_tail = ""

        for m, txt in blocks:
            role = m.group("role")
            variant = m.group("variant")
            b = BUCKET.get(role, "pending")
            if b == "yuanjuan" and variant != "native":
                b = "ocr"
            buckets[b].append(txt)
            sid = rel2sid.get(m.group("path"))
            if sid:
                blk = txt.split("\n", 1)[1] if "\n" in txt else ""
                pgs = pi.locate(sid, blk)
                if pgs:
                    page_hits[sid] |= set(pgs)

        new_body = []
        if not buckets.get("yuanjuan"):
            new_body.append(NO_YUANJUAN_WARN)
        for key in ("yuanjuan", "ocr", "teacher", "rubric", "answer", "lecture", "pending"):
            if not buckets.get(key):
                continue
            new_body.append("\n## %s\n" % BUCKET_TITLE[key])
            new_body.append("> %s\n" % BUCKET_NOTE[key])
            for txt in buckets[key]:
                new_body.append(txt + "\n")
            new_body.append("")

        out = ["# %s\n\n" % qid]
        if "身份信息" in titles:
            out.append("## 身份信息" + secs[titles.index("身份信息")][1])
        guide, adopted, adopted_src = build_guide(buckets, head_st)
        out.append(guide)
        out.append("".join(new_body))
        for t in ("正式评分材料原文", "参考答案原文",
                  "候选评分材料（尚未确认，不得当作正式细则）",
                  "题号冲突线索（须人工裁决，不得直接采用）",
                  "已排除的材料（文件名明确指向他题，非本题材料）",
                  "配对状态"):
            if t in titles:
                out.append("## %s%s" % (t, secs[titles.index(t)][1]))

        if "来源定位" in titles:
            src_body = secs[titles.index("来源定位")][1].rstrip("\n")
            extra = []
            for sid, pgs in sorted(page_hits.items()):
                extra.append("- 页级定位 `%s`：第 %s 页（由逐页文本块比对得出）"
                             % (sid, "、".join(str(p) for p in sorted(pgs))))
            out.append("## 来源定位" + src_body + "\n" + ("\n".join(extra) + "\n" if extra else ""))

        if "质量标记" in titles:
            qb = secs[titles.index("质量标记")][1]
            old_m = re.search(r"^- rubric_status: .*$", qb, re.M)
            old_tail = old_m.group(0) if old_m else ""
            new_line = ("- rubric_status: %s"
                        "（与头部配对状态同源，派生自 indexes/rubric_links.csv）" % head_st)
            qb2 = re.sub(r"^- rubric_status: .*$", new_line, qb, count=1, flags=re.M)
            img_lines = []
            for sid, pgs in sorted(page_hits.items()):
                img_lines += render_asset_lines(sid, sorted(pgs))
            if img_lines:
                img_block = ("- 图像依赖（页级，须显式打开）：\n"
                             + "\n".join("  - " + x for x in img_lines))
            else:
                img_block = "- 图像依赖：本题来源无逐页渲染图（非分页载体），须打开原件核对"
            qb2 = re.sub(r"^- 图像依赖: .*$", img_block, qb2, count=1, flags=re.M)
            out.append("## 质量标记" + qb2)

        new_md = "".join(out)
        if not new_md.endswith("\n"):
            new_md += "\n"

        changed = (new_md != md)
        stats["已改" if changed else "未变"] += 1
        log.append({
            "question_id": qid,
            "file": os.path.relpath(fp, P.OUT_ROOT),
            "old_rubric_status_tail": old_tail,
            "new_rubric_status_tail": new_line,
            "head_rubric_status": head_st,
            "adopted_stem_section": adopted,
            "adopted_stem_source": adopted_src,
            "buckets": {k: len(v) for k, v in buckets.items()},
            "page_hits": {k: sorted(v) for k, v in page_hits.items()},
            "changed": changed,
        })

        if not a.dry_run:
            target = fp
            if a.out_dir:
                sub = os.path.basename(os.path.dirname(fp))
                os.makedirs(os.path.join(a.out_dir, sub), exist_ok=True)
                target = os.path.join(a.out_dir, sub, "%s.md" % qid)
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(new_md)

    rpt = a.report or os.path.join(P.VAL_DIR, "续修_20260921", "31_修复日志.jsonl")
    os.makedirs(os.path.dirname(rpt), exist_ok=True)
    with open(rpt, "w", encoding="utf-8") as fh:
        for x in log:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    print("处理文件:", len(files), dict(stats))
    print("日志:", rpt)


if __name__ == "__main__":
    main()
