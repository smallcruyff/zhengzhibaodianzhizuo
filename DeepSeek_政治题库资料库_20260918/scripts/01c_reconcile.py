#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段1c：对账深挖（约束1 收口）。

目标：
  1. 列出各原料根"主输入所无"的真实文件，剔除工程产物/缓存/渲染件/__MACOSX
  2. 判定其中是否含真正的独有题源原件（试卷/答案/细则/讲评）
  3. 输出 indexes/unique_sources.csv + 对账补充结论
"""
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P

CACHE = os.path.join(P.INDEX_DIR, "_hash_cache.json")

SRC_EXT = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".csv", ".rtf", ".txt"}
# 工程产物/缓存/派生件特征
ENG_PAT = re.compile(
    r"(续作_|工作稿|渲染|_r\d{2}\.|/核验/|/审计|导出日志|运行日志|执行日志|渲染日志|"
    r"全文对照|全文缓存|待改文字|待改完整文字|回源|原件保全|只读回滚母本|样页|局部核验|"
    r"dist-info|__MACOSX|\.DS_Store|/logs?/|/cache/|/tmp/|源字体|索引\.csv|"
    r"PATCH_REPLAY|APPLY_IN_WORK|task-continuity|启动消息|项目指令|"
    r"宝典|校订稿|终审版|重建版|落位|修订单|baseline|基线)")
# 疑似真正题源的角色词
ROLE_PAT = re.compile(r"(试卷|试题|答案|细则|评标|评分标准|评分参考|阅卷|讲评|评标实录|"
                      r"原卷|参考答案|答题卡|参考答案及评分)")


def main():
    with open(CACHE, "r", encoding="utf-8") as fh:
        cache = json.load(fh)
    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        man = list(csv.DictReader(fh))
    primary_hashes = set(r["sha256"] for r in man if r["sha256"])

    # 汇总所有根
    roots = {}
    for r in P.AUTHORIZED_ROOTS:
        roots[r["root_id"]] = r["path"]

    uniq = []
    for ap, c in cache.items():
        sha = c.get("sha")
        if not sha or sha in primary_hashes:
            continue
        ext = os.path.splitext(ap)[1].lower()
        if ext not in SRC_EXT:
            continue
        # 归到哪个根
        rid = None
        for k, p in roots.items():
            if ap.startswith(p + os.sep):
                rid = k
                break
        if rid is None:
            rid = "ZIP" if "/zip_extract/" in ap else "OTHER"
        is_eng = bool(ENG_PAT.search(ap))
        is_mac = "__MACOSX" in ap
        has_role = bool(ROLE_PAT.search(os.path.basename(ap)))
        uniq.append({
            "root": rid, "path": ap, "ext": ext.lstrip("."), "size": c.get("size"),
            "sha256": sha, "engineering_like": "Y" if is_eng else "N",
            "macosx": "Y" if is_mac else "N",
            "has_source_role_word": "Y" if has_role else "N",
        })

    uniq.sort(key=lambda x: (x["root"], x["engineering_like"], x["path"]))
    cols = ["root", "path", "ext", "size", "sha256", "engineering_like", "macosx",
            "has_source_role_word"]
    with open(os.path.join(P.INDEX_DIR, "unique_sources.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for u in uniq:
            w.writerow(u)

    # 候选独有原件：非工程、非__MACOSX、含题源角色词
    cand = [u for u in uniq if u["engineering_like"] == "N" and u["macosx"] == "N"
            and u["has_source_role_word"] == "Y"]
    # 更宽的候选：非工程、非macosx（不论角色词）
    cand2 = [u for u in uniq if u["engineering_like"] == "N" and u["macosx"] == "N"]

    print("=== 各根唯一文件（题源类扩展名，主输入所无）===")
    agg = {}
    for u in uniq:
        agg.setdefault(u["root"], [0, 0, 0])
        agg[u["root"]][0] += 1
        if u["engineering_like"] == "N" and u["macosx"] == "N":
            agg[u["root"]][1] += 1
    for k in sorted(agg):
        print("  %-10s 合计 %-6d 其中非工程非macosx %-6d" % (k, agg[k][0], agg[k][1]))

    print("\n=== 候选独有原件（非工程 + 含题源角色词）===")
    for u in cand:
        print("  [%s] %s" % (u["root"], u["path"]))
    print("\n候选数:", len(cand), " / 非工程非macosx总数:", len(cand2))

    with open(os.path.join(P.VAL_DIR, "01b_独有原件候选.json"), "w", encoding="utf-8") as fh:
        json.dump({"candidates_strict": cand, "candidates_loose": cand2[:400]},
                  fh, ensure_ascii=False, indent=2)
    print("\nWROTE indexes/unique_sources.csv, validation/01b_独有原件候选.json")


if __name__ == "__main__":
    main()
