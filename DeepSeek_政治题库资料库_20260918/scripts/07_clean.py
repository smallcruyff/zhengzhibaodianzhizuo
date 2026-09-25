#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段4：原文清洗（保真优先，可审计）。

规范五.1：恢复真实自然段和材料层级，清除 PDF 物理折行造成的异常断句；
不得把多段材料压成一段，也不得把本来连贯的段落拆成碎句；
不得改写设问、用答案反补缺失题干、凭常识补全模糊文字、自动改正原卷知识错误。

原则：
  - 原始抽取留在 evidence/{sid}/native_text/raw.txt（或 raw.md），**本脚本不修改它**
  - 清洗结果写 evidence/{sid}/cleaned/clean.md，并同步为 processed_markdown/{sid}.full.md
  - 每一次合并/删除都在 cleaning_log.jsonl 留证（原行、结果、依据、原因）

只做三类操作：
  1) 删除页眉页脚（须有跨页重复证据，逐条登记）
  2) 合并 PDF 折行（上一行未以句末标点结尾且下一行不构成新块）
  3) 标记需视觉处理的页（扫描/空白待确认）
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

TERMINAL = "。！？；：…"
CLOSERS = "”》）】》」』〕"
# 新块起始标记
RE_QNUM = re.compile(r"^\s*(\d{1,2})\s*[．.、]\s*\S")
RE_SUBQ = re.compile(r"^\s*[（(]\s*\d{1,2}\s*[）)]\s*\S")
RE_OPT = re.compile(r"^\s*[A-D]\s*[．.、]\s*\S")
RE_SEC = re.compile(r"^\s*(第[一二三四五六七八九十]+部分|[一二三四五六七八九十]\s*[、．.]\s*\S)")
RE_MAT = re.compile(r"^\s*(材料[一二三四五六七八九十\d]|【|阅读材料|注[:：])")
RE_PAGENUM = re.compile(r"^\s*[-—]?\s*\d{1,3}\s*[-—]?\s*$")
RE_HDRFOOT = re.compile(r"(第\s*\d+\s*页|共\s*\d+\s*页|第\s*\d+\s*张|/\s*\d+\s*页)")


def ends_terminal(s):
    s = s.rstrip()
    if not s:
        return True
    return s[-1] in TERMINAL or s[-1] in CLOSERS


def starts_new_block(s):
    s = s.strip()
    if not s:
        return False
    for rx in (RE_QNUM, RE_SUBQ, RE_OPT, RE_SEC, RE_MAT):
        if rx.match(s):
            return True
    return False


def detect_headers(pages):
    """跨页重复的短行 -> 页眉页脚候选（须有重复证据）。"""
    cnt = Counter()
    for pg in pages:
        for ln in pg["lines"]:
            t = ln.strip()
            if not t or len(t) > 40:
                continue
            if RE_HDRFOOT.search(t) or RE_PAGENUM.match(t):
                cnt[t] += 1
    n_pages = len(pages)
    hdr = set()
    for t, c in cnt.items():
        if c >= 2 or (n_pages >= 3 and c >= n_pages * 0.5):
            hdr.add(t)
    return hdr


def clean_pdf(sid, meta, d):
    raw_path = os.path.join(d, "native_text", "raw.txt")
    if not os.path.isfile(raw_path):
        return None
    with open(raw_path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    blocks = re.split(r"\n<<<PAGE (\d+)>>>\n", raw)
    pages = []
    # blocks: ['', '1', text1, '2', text2, ...]
    it = iter(blocks[1:])
    for num, txt in zip(it, it):
        pages.append({"page": int(num), "text": txt,
                      "lines": [l for l in txt.splitlines()]})

    pj = {}
    pj_path = os.path.join(d, "native_text", "pages.jsonl")
    if os.path.isfile(pj_path):
        for ln in open(pj_path, encoding="utf-8"):
            try:
                o = json.loads(ln)
                pj[o["page"]] = o
            except Exception:
                pass

    hdr = detect_headers(pages)
    log = []
    out = []
    for pg in pages:
        p = pg["page"]
        cls = (pj.get(p) or {}).get("class", "?")
        chars = (pj.get(p) or {}).get("chars", 0)
        out.append("\n## 第 %d 页（%s，%d 字符）\n" % (p, cls, chars))
        if cls == "scan_or_empty" and chars < 5:
            out.append("> 〔本页无文字层，需视觉核验；原页图见 `%s`〕\n"
                       % ((pj.get(p) or {}).get("render", "") or "（未渲染）"))
            log.append({"page": p, "action": "flag_needs_visual", "reason": "文字层为空，未确认是否真空白"})
            continue
        kept = []
        for i, ln in enumerate(pg["lines"]):
            t = ln.rstrip()
            if t.strip() in hdr:
                log.append({"page": p, "line": i, "action": "drop_header_footer",
                            "text": t.strip(), "reason": "跨页重复且含页码特征"})
                continue
            kept.append(t)
        # 合并折行
        merged = []
        for i, t in enumerate(kept):
            s = t.strip()
            if not s:
                if merged and merged[-1] != "":
                    merged.append("")
                continue
            if not merged:
                merged.append(s)
                continue
            prev = merged[-1]
            if prev == "":
                merged.append(s)
                continue
            if starts_new_block(s) or ends_terminal(prev):
                merged.append(s)
            else:
                joined = prev + s
                merged[-1] = joined
                log.append({"page": p, "action": "join_wrapped",
                            "before": prev[-30:] + " ⏎ " + s[:30],
                            "after": joined[-60:],
                            "reason": "上一行未以句末标点结尾且本行非新块起点"})
        out.extend([x for x in merged if x != "" or True])
        out.append("")
    return "\n".join(out), log


def clean_md(sid, meta, d):
    """docx/pptx 的 raw.md 基本已是结构化文本，仅做轻量归一。"""
    raw_path = os.path.join(d, "native_text", "raw.md")
    if not os.path.isfile(raw_path):
        return None
    with open(raw_path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    log = [{"action": "no_op", "reason": "docx/pptx 抽取已按文档结构分块，不做折行合并以避免破坏结构"}]
    return raw, log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-year", default="")
    a = ap.parse_args()

    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["in_scope"] == "Y"]
    if a.source:
        rows = [r for r in rows if r["source_id"] == a.source]
    if a.only_year:
        rows = [r for r in rows if r["rel_path"].startswith(a.only_year)]
    if a.limit:
        rows = rows[:a.limit]

    done = 0
    for i, r in enumerate(rows, 1):
        sid = r["source_id"]
        d = os.path.join(P.EVID_DIR, sid)
        if not os.path.isdir(d):
            continue
        meta = {}
        mp = os.path.join(d, "meta.json")
        if os.path.isfile(mp):
            try:
                meta = json.load(open(mp, encoding="utf-8"))
            except Exception:
                pass
        try:
            if r["format"] == "pdf":
                res = clean_pdf(sid, meta, d)
            else:
                res = clean_md(sid, meta, d)
            if not res:
                continue
            text, log = res
            P.ensure_dirs(os.path.join(d, "cleaned"))
            with open(os.path.join(d, "cleaned", "clean.md"), "w", encoding="utf-8") as fh:
                fh.write(text)
            with open(os.path.join(d, "cleaning_log.jsonl"), "w", encoding="utf-8") as fh:
                for e in log:
                    fh.write(json.dumps(e, ensure_ascii=False) + "\n")
            # 主档 = 清洗后正文
            head = ("# %s\n\n> source_id: %s\n> 原始路径: `%s`\n> 状态: **清洗后正文**"
                    "（原始抽取见 `evidence/%s/native_text/`，未被覆盖）\n> 清洗操作数: %d\n\n"
                    % (os.path.basename(r["original_path"]), sid, r["original_path"], sid, len(log)))
            with open(os.path.join(P.MD_DIR, "%s.full.md" % sid), "w", encoding="utf-8") as fh:
                fh.write(head + text)
            done += 1
            if i % 20 == 0:
                print("  cleaned", i)
        except Exception as e:
            with open(os.path.join(P.VAL_DIR, "07_clean_errors.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"source_id": sid, "error": repr(e)}, ensure_ascii=False) + "\n")
    print("cleaned files:", done)


if __name__ == "__main__":
    main()
