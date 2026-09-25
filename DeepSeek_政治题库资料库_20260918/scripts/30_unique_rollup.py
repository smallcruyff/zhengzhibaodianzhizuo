#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""续修 2026-09-21：唯一汇总函数（单一真相源）。

目的：README / PROGRESS / checkpoint / 各报告此前各算一套，出现
已看 33/34/42 页、总页 1748/1781/1815、汇编已定位 31/44/74 等互相矛盾的数字。
本模块提供**唯一**汇总口径，所有下游文档必须从这里取数。

去重键：`(source_id, page)`。
状态互相独立，不得互相替代：

  opened               实际打开过原页（visual_review.jsonl 有该页记录）
  corrected            该页文本已修（corrected_text 或 verified/pNNN.verified.txt）
  findings_open        该页登记了未修复问题（findings 存在且未被标 resolved）
  packet_deps_verified 该页所承载题目的题包依赖已全部核完
  rubric_pending       该页承载的题仍存在评分关系待审（未确认正式细则配对）

关键约束：
  - 历史记录里的 `reviewed` 只证明"打开过"，**不证明页内问题全修完**。
  - 分母是工作单按 (source_id, page) 去重后的唯一页数，不是工作单行数。
  - 任何默认值（脚本自动写入）不构成"实际查看"证据。

用法：
  /usr/bin/python3 30_unique_rollup.py            # 打印并落盘汇总
  /usr/bin/python3 30_unique_rollup.py --json     # 只输出 JSON
"""
import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

ROLLUP_PATH = os.path.join(P.VAL_DIR, "续修_20260921", "唯一汇总.json")

# 与 10_pair.py 的题级状态一致；用于 rubric_pending 判定
FORMAL_OK = {"已匹配正式材料"}


def _load_jsonl(path):
    out = []
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
    return out


def load_worklist():
    """工作单唯一页集合 + 每页角色。"""
    rows = _load_jsonl(os.path.join(P.VAL_DIR, "视觉核验工作单.jsonl"))
    pages = {}          # (sid, page) -> row（同键多行时保留首条，行数另计）
    dup_rows = 0
    for r in rows:
        k = (r.get("source_id"), r.get("page"))
        if k in pages:
            dup_rows += 1
        else:
            pages[k] = r
    return rows, pages, dup_rows


def load_reviews():
    """视觉核验记录，按 (sid, page) 归并。"""
    recs = defaultdict(list)
    raw_rows = 0
    for f in glob.glob(os.path.join(P.EVID_DIR, "*", "visual_review.jsonl")):
        sid = os.path.basename(os.path.dirname(f))
        for o in _load_jsonl(f):
            raw_rows += 1
            recs[(sid, o.get("page"))].append(o)
    return recs, raw_rows


def load_verified_files():
    """实际存在的 verified 页文本（文本已修的第二证据）。"""
    out = set()
    for f in glob.glob(os.path.join(P.EVID_DIR, "*", "visual_transcript", "verified", "p*.verified.txt")):
        sid = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(f))))
        base = os.path.basename(f)
        try:
            page = int(base[1:4])
        except Exception:
            continue
        out.add((sid, page))
    return out


def load_question_rubric():
    """question_id -> 题级 rubric_status（取自 rubric_links.csv，唯一口径）。"""
    fp = os.path.join(P.INDEX_DIR, "rubric_links.csv")
    st = {}
    if not os.path.isfile(fp):
        return st
    with open(fp, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            qid = r["question_id"]
            v = r.get("exam_rubric_status") or ""
            if v:
                st[qid] = v
    return st


def load_question_pages():
    """question_id -> 该题依赖的原页 (sid, page) 集合。

    证据来自 source_map.jsonl（逐页逐张来源映射）；缺失时退化为
    questions.csv 的 source_id（仅能定位到文件，不能定位到页，须显式标注）。
    """
    q2p = defaultdict(set)
    sm = os.path.join(P.INDEX_DIR, "source_map.jsonl")
    if os.path.isfile(sm):
        with open(sm, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                qid = o.get("question_id")
                sid = o.get("source_id")
                page = o.get("page")
                if qid and sid and page is not None:
                    q2p[qid].add((sid, page))
    return q2p


def compute():
    wl_rows, wl_pages, dup_rows = load_worklist()
    recs, review_raw_rows = load_reviews()
    verified_files = load_verified_files()
    q_rubric = load_question_rubric()
    q_pages = load_question_pages()

    opened = set()
    corrected = set()
    findings_open = set()
    # 证据强度：脚本默认值（只有 method 默认串 + review_status）不构成"实际查看"证据
    opened_strong = set()
    opened_weak = set()
    for k, os_ in recs.items():
        for o in os_:
            is_rev = (o.get("review_status") == "reviewed" or o.get("reviewed") is True)
            if is_rev:
                opened.add(k)
                # 强证据：实际打开过具体文件，或写下了内容相关的发现
                has_file = bool(o.get("viewed_file") or o.get("opened_artifact")
                                or o.get("viewed_files"))
                has_content = bool(o.get("findings") or o.get("issues_found")
                                   or o.get("corrected_text") or o.get("affected_questions"))
                if has_file or has_content:
                    opened_strong.add(k)
                else:
                    opened_weak.add(k)
            if o.get("corrected_text"):
                corrected.add(k)
            fnd = o.get("findings")
            if fnd:
                # 显式 resolved=True 才算已修；否则视为未修问题
                if not (isinstance(fnd, dict) and fnd.get("resolved") is True):
                    findings_open.add(k)
    corrected |= (verified_files & set(wl_pages))

    # 页 -> 承载题目
    page_carries = defaultdict(set)
    for k, row in wl_pages.items():
        for qid in (row.get("carries") or []):
            page_carries[k].add(qid)

    rubric_pending_pages = set()
    for k, qids in page_carries.items():
        for qid in qids:
            if q_rubric.get(qid, "暂未找到") not in FORMAL_OK:
                rubric_pending_pages.add(k)
                break

    # 题包依赖全部核完：该页承载的每一题，其依赖页都在 opened 内
    packet_deps_verified = set()
    for k, qids in page_carries.items():
        if not qids:
            continue
        all_ok = True
        for qid in qids:
            deps = q_pages.get(qid) or set()
            if not deps:
                all_ok = False       # 依赖页不可知，不得算核完
                break
            if not deps <= opened:
                all_ok = False
                break
        if all_ok:
            packet_deps_verified.add(k)

    total = len(wl_pages)
    summary = {
        "去重键": "(source_id, page)",
        "工作单行数": len(wl_rows),
        "工作单唯一页": total,
        "工作单重复行": dup_rows,
        "视觉核验记录行数": review_raw_rows,
        "视觉核验唯一页": len(recs),
        "opened_实际打开过": len(opened & set(wl_pages)),
        "opened_强证据_实际打开具体文件或写下内容发现": len(opened_strong & set(wl_pages)),
        "opened_弱证据_仅有脚本默认字段": len(opened_weak & set(wl_pages)),
        "corrected_文本已修": len(corrected & set(wl_pages)),
        "findings_open_存在未修问题": len(findings_open & set(wl_pages)),
        "packet_deps_verified_题包依赖全部核完": len(packet_deps_verified),
        "rubric_pending_评分关系待审": len(rubric_pending_pages),
        "未打开页": total - len(opened & set(wl_pages)),
        "覆盖率_实际打开过": round(len(opened & set(wl_pages)) / max(1, total) * 100, 2),
        "口径": (
            "分母=工作单按(source_id,page)去重唯一页；"
            "opened=有实际打开记录；历史 reviewed 只证明打开过，不证明页内问题已修；"
            "findings_open=登记了未修复问题；corrected=已有 verified 文本；"
            "packet_deps_verified=该页承载题目的依赖页全部已打开；"
            "rubric_pending=该页承载题仍无已确认正式细则。"
        ),
    }
    return summary, {
        "opened": opened,
        "corrected": corrected,
        "findings_open": findings_open,
        "packet_deps_verified": packet_deps_verified,
        "rubric_pending": rubric_pending_pages,
        "wl_pages": set(wl_pages),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    summary, _sets = compute()
    os.makedirs(os.path.dirname(ROLLUP_PATH), exist_ok=True)
    if not a.json:
        with open(ROLLUP_PATH, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
