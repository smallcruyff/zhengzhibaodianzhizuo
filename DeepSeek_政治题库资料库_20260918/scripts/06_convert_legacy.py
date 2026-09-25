#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段3：旧格式 DOC/PPT -> 现代格式转换（在副本上做，保留原文件与转换链）。

规范四.5：DOC、PPT 等旧格式可在副本上使用本地工具转换，保留原文件和转换链。
失败时尝试实际可用的替代读取路径；仍失败就登记阻断。

产出：
  evidence/{sid}/converted/xxx.docx|pptx    转换产物（副本）
  evidence/{sid}/convert_log.json
转换产物随后交给 04_extract_docx.py / 05_extract_pptx.py 处理（--source 指向转换件需另建清单）
"""
import argparse
import csv
import json
import os
import shutil
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def convert(src, destdir, target):
    P.ensure_dirs(destdir)
    env = P.env_with_fontconfig()
    t0 = time.time()
    rc, out, err = P.run([P.SOFFICE, "--headless", "--norestore", "--convert-to", target,
                          "--outdir", destdir, src], timeout=300, env=env)
    made = [f for f in sorted(os.listdir(destdir))
            if f.lower().endswith("." + target.split(":")[0])]
    return {"rc": rc, "seconds": round(time.time() - t0, 2),
            "produced": made, "stdout": out[:500], "stderr": err[:500],
            "fontconfig": P.fontconfig_file()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh)
                if r["format"] in ("doc", "ppt", "rtf") and r["in_scope"] == "Y"]
    if a.source:
        rows = [r for r in rows if r["source_id"] == a.source]
    if a.limit:
        rows = rows[:a.limit]
    print("legacy to convert:", len(rows))
    for i, r in enumerate(rows, 1):
        sid = r["source_id"]
        src = r["original_path"]
        d = os.path.join(P.EVID_DIR, sid)
        cdir = os.path.join(d, "converted")
        P.ensure_dirs(d, cdir)
        target = "pptx" if r["format"] == "ppt" else "docx"
        rec = {"source_id": sid, "src": src, "rel_path": r["rel_path"],
               "format": r["format"], "target": target}
        try:
            c = convert(src, cdir, target)
            rec.update(c)
            if c["produced"]:
                rec["status"] = "converted"
                rec["converted_path"] = os.path.join(cdir, c["produced"][0])
            else:
                # 替代路径：textutil（仅 doc/rtf）
                if r["format"] in ("doc", "rtf"):
                    alt = os.path.join(cdir, os.path.splitext(os.path.basename(src))[0] + ".txt")
                    rc2, o2, e2 = P.run(["/usr/bin/textutil", "-convert", "txt", "-output", alt, src], timeout=120)
                    if rc2 == 0 and os.path.isfile(alt):
                        rec["status"] = "converted_textutil"
                        rec["converted_path"] = alt
                        rec["textutil"] = {"rc": rc2, "stderr": e2[:300]}
                    else:
                        rec["status"] = "blocked"
                        rec["block_reason"] = "soffice 未产出且 textutil 失败"
                        rec["textutil"] = {"rc": rc2, "stderr": e2[:300]}
                else:
                    rec["status"] = "blocked"
                    rec["block_reason"] = "soffice 未产出，且 ppt 无替代路径"
        except Exception as e:
            rec["status"] = "blocked"
            rec["error"] = repr(e)
        print("[%d/%d] %s %s -> %s %ss" % (i, len(rows), sid, rec.get("status"),
                                           rec.get("produced"), rec.get("seconds")))
        with open(os.path.join(P.VAL_DIR, "03_legacy_convert_log.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        with open(os.path.join(d, "convert_log.json"), "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
