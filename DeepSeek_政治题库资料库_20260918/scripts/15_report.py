#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段10：汇总真实数字，生成 PROGRESS.md、checkpoint.json 与最终报告。

所有数字一律从实际产物（索引/证据目录/校验结果）现算，不引用任何先前报告的说法。
"""
import csv
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def rd(name):
    p = os.path.join(P.INDEX_DIR, name)
    if not os.path.isfile(p):
        return []
    with open(p, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def rd_jsonl(p):
    if not os.path.isfile(p):
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for ln in fh:
            try:
                out.append(json.loads(ln))
            except Exception:
                pass
    return out


def main():
    man = rd("source_manifest.csv")
    aliases = rd("source_aliases.csv")
    ef = rd("exam_files.csv")
    exams = rd("exams.csv")
    qs = rd("questions.csv")
    rl = rd("rubric_links.csv")
    asr = rd("assets.csv")
    smap = rd_jsonl(os.path.join(P.INDEX_DIR, "source_map.jsonl"))
    review = rd_jsonl(os.path.join(P.INDEX_DIR, "split_review.jsonl"))
    stats01 = json.load(open(os.path.join(P.VAL_DIR, "01_盘点统计.json"), encoding="utf-8")) \
        if os.path.isfile(os.path.join(P.VAL_DIR, "01_盘点统计.json")) else {}
    mach = json.load(open(os.path.join(P.VAL_DIR, "12_machine_check.json"), encoding="utf-8")) \
        if os.path.isfile(os.path.join(P.VAL_DIR, "12_machine_check.json")) else {}

    # ---- 原料覆盖 ----
    in_scope = [m for m in man if m["in_scope"] == "Y"]
    out_scope = [m for m in man if m["in_scope"] != "Y"]
    uniq_hash = set(m["sha256"] for m in in_scope if m["sha256"])
    years = sorted(set(e["year"] for e in exams if e.get("year") and e["year"] not in ("", "UNK")))
    real_exams = [e for e in exams if e.get("is_assembly") != "Y"]
    asm = [e for e in exams if e.get("is_assembly") == "Y"]

    # ---- 载体处理量 ----
    pages_total = pages_processed = 0
    slides_total = 0
    docx_n = pptx_n = pdf_n = 0
    ocr_pages = 0
    for m in in_scope:
        meta = os.path.join(P.EVID_DIR, m["source_id"], "meta.json")
        if not os.path.isfile(meta):
            continue
        try:
            d = json.load(open(meta, encoding="utf-8"))
        except Exception:
            continue
        fmt = m["format"]
        if fmt == "pdf" or d.get("pdf"):
            pdf_n += 1
            pages_total += d.get("pages") or 0
            pages_processed += d.get("pages") or 0
        elif fmt == "docx":
            docx_n += 1
        elif fmt == "pptx":
            pptx_n += 1
            slides_total += d.get("slides") or 0
    for f in glob.glob(os.path.join(P.EVID_DIR, "*", "visual_transcript", "*.ocr.txt")):
        ocr_pages += 1
    rendered = len(glob.glob(os.path.join(P.EVID_DIR, "*", "pages", "*.png")))
    figobj = sum(len(rd_jsonl(os.path.join(P.EVID_DIR, m["source_id"], "figure_objects.jsonl")))
                 for m in in_scope)

    # ---- 视觉核验（续修 2026-09-21：统一走 30_unique_rollup 的唯一口径）----
    import importlib
    ur = importlib.import_module("30_unique_rollup")
    vsum, _vsets = ur.compute()
    vrecs, vfiles = [], set()
    for f in glob.glob(os.path.join(P.EVID_DIR, "*", "visual_review.jsonl")):
        recs = rd_jsonl(f)
        vrecs += recs
        if recs:
            vfiles.add(os.path.basename(os.path.dirname(f)))
    vreviewed = vsum["opened_实际打开过"]        # 唯一页，不是行数
    vreviewed_rows = len(vrecs)                   # 保留行数供对照，明确区分
    vworklist_rows = vsum["工作单行数"]
    vworklist_pages = vsum["工作单唯一页"]
    visual_tasks = []
    for f in glob.glob(os.path.join(P.EVID_DIR, "*", "visual_tasks.jsonl")):
        visual_tasks += rd_jsonl(f)

    # ---- 题目 ----
    uniq_q = set(q["question_id"] for q in qs)
    by_var = Counter(q["variant"] for q in qs)
    by_type = Counter(q["type"] for q in qs)
    by_st = Counter(q["extraction_status"] for q in qs)
    nr = sum(1 for q in qs if q["needs_review"] == "Y")
    subj_with_sub = sum(1 for q in qs if q["subq_hint"])
    subq_total = sum(len([x for x in q["subq_hint"].split("/") if x]) for q in qs)

    # ---- 配对 ----
    q_status = {}
    for c in rl:
        q_status.setdefault(c["question_id"], c["exam_rubric_status"])
    st_counter = Counter(q_status.values())
    no_link = len(uniq_q) - len(q_status)
    if no_link:
        st_counter["暂未找到"] += no_link
    # 续修 2026-09-21 修订：题级冲突看 exam_rubric_status（10_pair 在"同题>=2份正式材料"
    # 时把题级状态置为存在冲突），pair_status 逐条链接不会写"存在冲突"，
    # 旧写法导致"存在冲突题 0 道"与配对表 21 道互相矛盾。
    conf_q = sorted(set(q for q, st in q_status.items() if st == "存在冲突"))
    conf_detail = sorted(set(c["question_id"] for c in rl
                            if c.get("pair_status") in ("存在冲突", "已排除（文件名指向他题）")))

    # ---- 资产 ----
    asset_kind = Counter(a["kind"] for a in asr)
    bad_assets = [a for a in asr
                  if not os.path.isfile(os.path.join(P.OUT_ROOT, a["path"]))]

    # ---- 汇编出处（续修 2026-09-21：从 assembly_blocks.csv 现算，不再硬编码）----
    ab = rd("assembly_blocks.csv")
    ab_status = Counter(r.get("status", "") for r in ab)
    asm_located = sum(v for k, v in ab_status.items() if k.startswith("已定位"))
    asm_missing = sum(v for k, v in ab_status.items() if "原料缺口" in k)
    asm_pending = sum(v for k, v in ab_status.items() if k == "待复核")
    asm_other = len(ab) - asm_located - asm_missing - asm_pending

    # ---- 未入索引的实物单题文件（现算，不硬编码）----
    _files = set(os.path.basename(f)[:-3]
                 for f in glob.glob(os.path.join(P.Q_DIR, "*", "*.md")))
    _idx = set(q["question_id"] for q in qs)
    orphan_ids = sorted(_files - _idx)
    missing_files = sorted(_idx - _files)

    # ---- 剩余缺口 ----
    gaps = defaultdict(list)
    for r in review:
        gaps[r.get("action", "unknown")].append(r)
    blocked_src = [m for m in in_scope
                   if not os.path.isfile(os.path.join(P.MD_DIR, "%s.full.md" % m["source_id"]))]

    R = {
        "generated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "output_root": P.OUT_ROOT,
        "primary_input": P.PRIMARY_ROOT,
        "authorized_roots": [{"root_id": r["root_id"], "path": r["path"], "role": r["role"]}
                             for r in P.AUTHORIZED_ROOTS],
        "material": {
            "paths_hashed": len(aliases),
            "unique_hashes": stats01.get("unique_hashes_total"),
            "unique_hashes_note": ("unique_hashes 是全部已授权根去重后的总数；"
                                   "范围内去重原件数见 in_scope_unique_sha"),
            "in_scope_rows": len(in_scope),
            "in_scope_unique_sha": len(uniq_hash),
            "primary_files": stats01.get("primary_files"),
            "in_scope_files": len(in_scope),
            "out_of_scope_files": len(out_scope),
            "source_alias_rows": len(aliases),
            "exam_count": len(real_exams),
            "assembly_count": len(asm),
            "year_range": [years[0], years[-1]] if years else [],
            "years": years,
            "exam_files_total": len(ef),
        },
        "carriers": {
            "pdf_files": pdf_n, "pdf_pages": pages_total, "pages_processed": pages_processed,
            "docx_files": docx_n, "pptx_files": pptx_n, "pptx_slides": slides_total,
            "pages_rendered": rendered, "ocr_candidate_pages": ocr_pages,
            "figure_objects": figobj,
        },
        "questions": {
            "unique_questions": len(uniq_q),
            "question_source_records": len(qs),
            "by_variant": dict(by_var), "by_type": dict(by_type),
            "by_extraction_status": dict(by_st),
            "needs_review_records": nr,
            "records_with_subquestions": subj_with_sub,
            "subquestion_marks_total": subq_total,
        },
        "rubric": dict(st_counter),
        "rubric_links": len(rl),
        "conflicting_questions": conf_q,
        "conflict_or_excluded_questions": conf_detail,
        "visual_review": {
            "pages_reviewed": vreviewed,
            "pages_reviewed_strong_evidence": vsum["opened_强证据_实际打开具体文件或写下内容发现"],
            "pages_reviewed_weak_evidence": vsum["opened_弱证据_仅有脚本默认字段"],
            "review_record_rows": vreviewed_rows,
            "worklist_rows": vworklist_rows,
            "worklist_unique_pages": vworklist_pages,
            "remaining_pages": vsum["未打开页"],
            "percent": vsum["覆盖率_实际打开过"],
            "pages_with_open_findings": vsum["findings_open_存在未修问题"],
            "pages_with_corrected_text": vsum["corrected_文本已修"],
            "pages_packet_deps_verified": vsum["packet_deps_verified_题包依赖全部核完"],
            "pages_rubric_pending": vsum["rubric_pending_评分关系待审"],
            "pending_tasks": len(visual_tasks),
            "files_reviewed": len(vfiles),
            "口径": vsum["口径"],
            "唯一汇总源": "validation/续修_20260921/唯一汇总.json",
        },
        "assets": {"total": len(asr), "by_kind": dict(asset_kind),
                   "unopenable": len(bad_assets)},
        "source_map_entries": len(smap),
        "assembly_blocks": {
            "total": len(ab),
            "located": asm_located,
            "missing_source": asm_missing,
            "pending": asm_pending,
            "other": asm_other,
            "by_status": dict(ab_status),
            "unresolved": asm_missing + asm_pending,
            "来源": "indexes/assembly_blocks.csv（现算）",
        },
        "orphan_question_files": {
            "count": len(orphan_ids),
            "items": orphan_ids,
            "定性": "validation/续修_20260921/五个未入索引文件_定性.md",
            "口径": "实物单题文件题号 - indexes/questions.csv 唯一题号（现算）",
        },
        "gaps": {k: len(v) for k, v in sorted(gaps.items(), key=lambda x: -len(x[1]))},
        "sources_without_master_md": len(blocked_src),
        "machine_check": {"passed": mach.get("summary", {}).get("passed"),
                          "total": mach.get("summary", {}).get("total"),
                          "fails": [c["check"] for c in mach.get("checks", []) if not c["ok"]]},
    }

    # 视觉核验任务清单（按风险排序：纯扫描页优先，其次图对象多的页）
    prio = []
    for m in in_scope:
        meta = os.path.join(P.EVID_DIR, m["source_id"], "meta.json")
        if not os.path.isfile(meta):
            continue
        try:
            d = json.load(open(meta, encoding="utf-8"))
        except Exception:
            continue
        pc = d.get("page_classes") or {}
        nscan = pc.get("scan_or_empty", 0)
        pj = os.path.join(P.EVID_DIR, m["source_id"], "native_text", "pages.jsonl")
        figs = {}
        if os.path.isfile(pj):
            for ln in open(pj, encoding="utf-8"):
                try:
                    o = json.loads(ln)
                except Exception:
                    continue
                figs[o["page"]] = o.get("figure_objects", 0)
        for pg in (d.get("needs_visual_check") or []):
            f = figs.get(pg, 0)
            score = (2 if nscan else 0) + min(f, 40) / 40.0
            prio.append({"source_id": m["source_id"], "exam_id": m.get("exam_id", ""),
                         "role": m.get("role", ""), "page": pg, "figure_objects": f,
                         "page_is_scan": bool(nscan), "priority": round(score, 3),
                         "render": "evidence/%s/pages/p%03d.png" % (m["source_id"], pg),
                         "rel_path": m["rel_path"]})
    prio.sort(key=lambda x: -x["priority"])
    with open(os.path.join(P.VAL_DIR, "视觉核验任务清单.jsonl"), "w", encoding="utf-8") as fh:
        for x in prio:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")
    R["visual_review"]["priority_task_records"] = len(prio)
    R["visual_review"]["task_records_collected"] = len(visual_tasks)
    with open(os.path.join(P.VAL_DIR, "10_汇总数字.json"), "w", encoding="utf-8") as fh:
        json.dump(R, fh, ensure_ascii=False, indent=2)

    # checkpoint（续修 2026-09-21：与唯一汇总同源，不再各写一套）
    with open(os.path.join(P.OUT_ROOT, "checkpoint.json"), "w", encoding="utf-8") as fh:
        json.dump({"stage": "阶段10 收尾",
                   "state": "本轮执行完成（题库续修 2026-09-21 已接入唯一汇总口径）",
                   "counts": {"unique_questions": len(uniq_q),
                              "question_source_records": len(qs),
                              "rubric_links": len(rl),
                              "assets": len(asr),
                              "source_map_entries": len(smap),
                              "visual_reviewed_pages": vreviewed,
                              "visual_review_record_rows": vreviewed_rows,
                              "visual_worklist_rows": vworklist_rows,
                              "visual_worklist_unique_pages": vworklist_pages,
                              "visual_remaining_pages": vsum["未打开页"]},
                   "counts_source": "validation/续修_20260921/唯一汇总.json",
                   "resume_hint": ("索引与单题文件已落盘，可直接使用；"
                                   "若需继续，优先做视觉核验（见 validation/视觉核验工作单.jsonl）"
                                   "与人工裁决存在冲突的题。"
                                   "所有统计口径见 validation/续修_20260921/唯一汇总.json。"),
                   "generated_at": R["generated_at"]}, fh, ensure_ascii=False, indent=2)

    print(json.dumps(R, ensure_ascii=False, indent=2)[:4000])
    return R


if __name__ == "__main__":
    main()
