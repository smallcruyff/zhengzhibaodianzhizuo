#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段3：PPTX 提取（逐张，含隐藏页、备注、表格、图片、组合形状）。

规范四.4：逐张处理所有幻灯片，包括隐藏页；检查正文、表格、图表、组合形状、图片、
箭头关系、备注及相关批注；备注/隐藏页/被遮挡信息分别登记。

产出：
  evidence/{sid}/native_text/raw.md
  evidence/{sid}/native_text/slides.jsonl      逐张结构（含隐藏标记）
  evidence/{sid}/native_text/notes.md          演讲者备注（分区，不混入正文）
  evidence/{sid}/figure_objects.jsonl          图片/图形对象清单（约束2）
  processed_markdown/{sid}.full.md
"""
import argparse
import csv
import json
import os
import sys
import time
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _paths as P


def sid_dir(sid):
    d = os.path.join(P.EVID_DIR, sid)
    P.ensure_dirs(d, os.path.join(d, "native_text"), os.path.join(d, "figures"),
                  os.path.join(d, "visual_transcript"), os.path.join(d, "cleaned"))
    return d


def hidden_slide_indices(path):
    """presentation.xml 中 show="0" 的幻灯片序号（1-based）。"""
    hid = set()
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("ppt/presentation.xml").decode("utf-8", "replace")
        import re
        for m in re.finditer(r'<p:sldId[^>]*show="0"[^>]*/>', xml):
            pass
        # 更稳的方式：按 sldId 顺序索引
        ids = re.findall(r"<p:sldId\b[^>]*>", xml)
        for i, tag in enumerate(ids, 1):
            if 'show="0"' in tag:
                hid.add(i)
    except Exception:
        pass
    return hid


def shape_walk(shapes, depth=0):
    """递归展开组合形状。返回 [(shape, depth)]"""
    out = []
    for sh in shapes:
        out.append((sh, depth))
        if sh.shape_type is not None and str(sh.shape_type).startswith("GROUP"):
            try:
                out.extend(shape_walk(sh.shapes, depth + 1))
            except Exception:
                pass
    return out


def shape_text(sh):
    try:
        if sh.has_text_frame:
            return sh.text_frame.text
    except Exception:
        pass
    return ""


# OOXML 各部件可能引用到但未声明的标准前缀（仅做"补声明"，不改动任何内容）
NS_URI = {
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "v": "urn:schemas-microsoft-com:vml",
    "o": "urn:schemas-microsoft-com:office:office",
    "m": "http://schemas.openxmlformats.org/officeDocument/2006/math",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "mc": "http://schemas.openxmlformats.org/markup-compatibility/2006",
    "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
    "dgm": "http://schemas.openxmlformats.org/drawingml/2006/diagram",
    "p14": "http://schemas.microsoft.com/office/powerpoint/2010/main",
    "p15": "http://schemas.microsoft.com/office/powerpoint/2012/main",
}


def repair_namespaces(pptx, destdir):
    """部分 pptx 内部 XML 引用了未声明的命名空间前缀（如 w:/p:），导致 python-pptx 打不开。
    修补方式：按 lxml 报错逐个把缺失前缀的 xmlns 声明补到根元素上，再重新打包。
    只补声明，不增删任何元素或文字。返回 (修补后路径, 修补明细) 或 (None, 明细)。"""
    import re as _re
    from lxml import etree
    P.ensure_dirs(destdir)
    out = os.path.join(destdir, "repaired.pptx")
    try:
        zin = zipfile.ZipFile(pptx)
    except Exception as e:
        return None, {"open_error": repr(e)}
    fixed = {}
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename.endswith((".xml", ".rels")):
                    try:
                        txt = data.decode("utf-8")
                    except Exception:
                        zout.writestr(item.filename, data)
                        continue
                    added = []
                    for _ in range(12):
                        try:
                            etree.fromstring(txt.encode("utf-8"))
                            break
                        except etree.XMLSyntaxError as e:
                            m = _re.search(r"[Nn]amespace prefix (\w+)", str(e))
                            if not m:
                                break
                            pfx = m.group(1)
                            uri = NS_URI.get(pfx)
                            if not uri:
                                added.append("%s:未知前缀,放弃" % pfx)
                                break
                            rm = _re.search(r"<([A-Za-z_][\w.:-]*)(\s|/?>)", txt)
                            if not rm:
                                break
                            txt = (txt[:rm.end(1)] + ' xmlns:%s="%s"' % (pfx, uri)
                                   + txt[rm.end(1):])
                            added.append(pfx)
                    if added:
                        fixed[item.filename] = added
                        data = txt.encode("utf-8")
                zout.writestr(item.filename, data)
        zin.close()
        return (out if fixed else None), {"fixed_parts": fixed}
    except Exception as e:
        return None, {"repair_error": repr(e), "fixed_parts": fixed}


def damaged_slide_parts(path, min_bytes=160):
    """找出源文件中被破坏的幻灯片部件（例如只剩自闭合根元素 <p:sld/>）。
    这些是原件自身的缺陷，必须逐条登记，不能当作"空页"静默带过。"""
    out = []
    try:
        with zipfile.ZipFile(path) as zf:
            for n in zf.namelist():
                if not (n.startswith("ppt/slides/slide") and n.endswith(".xml")):
                    continue
                raw = zf.read(n)
                if len(raw) < min_bytes:
                    idx = "".join(c for c in os.path.basename(n) if c.isdigit())
                    out.append({"part": n, "slide_index": int(idx) if idx else None,
                                "bytes": len(raw), "raw": raw.decode("utf-8", "replace")[:200]})
    except Exception:
        pass
    return out


def process_one(row):
    sid = row["source_id"]
    pptx = row["original_path"]
    d = sid_dir(sid)
    t0 = time.time()
    from pptx import Presentation
    prs = Presentation(pptx)
    hid = hidden_slide_indices(pptx)

    slides = []
    figs = []
    notes_md = []
    md = []
    n_notes = 0
    n_tables = 0
    n_pics = 0
    n_charts = 0
    for i, slide in enumerate(prs.slides, 1):
        items = []
        for sh, depth in shape_walk(slide.shapes):
            st = str(sh.shape_type) if sh.shape_type is not None else "UNKNOWN"
            name = getattr(sh, "name", "")
            txt = shape_text(sh)
            entry = {"type": st, "name": name, "depth": depth, "text": txt}
            if "PICTURE" in st:
                n_pics += 1
                entry["kind"] = "picture"
                figs.append({"slide": i, "kind": "picture", "name": name,
                             "w": getattr(sh, "width", None), "h": getattr(sh, "height", None)})
            if "TABLE" in st:
                n_tables += 1
                try:
                    rows = []
                    for r in sh.table.rows:
                        rows.append([c.text for c in r.cells])
                    entry["table"] = rows
                except Exception as e:
                    entry["table_error"] = repr(e)
            if "CHART" in st or "CHART" in name.upper():
                n_charts += 1
                entry["kind"] = "chart"
                figs.append({"slide": i, "kind": "chart", "name": name})
            if "GROUP" in st:
                entry["kind"] = "group"
            items.append(entry)

        notes = ""
        try:
            if slide.has_notes_slide:
                notes = slide.notes_slide.notes_text_frame.text or ""
        except Exception:
            notes = ""
        if notes.strip():
            n_notes += 1
            notes_md.append("\n### 第 %d 张 备注\n\n%s\n" % (i, notes.rstrip()))

        slides.append({"slide": i, "hidden": i in hid, "shape_count": len(items),
                       "items": items, "notes": notes})

        md.append("\n## 第 %d 张%s\n" % (i, "（隐藏页）" if i in hid else ""))
        for it in items:
            if it.get("text", "").strip():
                md.append(it["text"].rstrip())
            if "table" in it:
                md.append("<!-- 表格 -->")
                for r in it["table"]:
                    md.append("| " + " | ".join((c or " ") for c in r) + " |")
        if notes.strip():
            md.append("\n<!-- 备注见 notes.md -->")

    # 批注（pptx 现代批注在 ppt/comments/）
    comments = []
    try:
        with zipfile.ZipFile(pptx) as zf:
            for n in zf.namelist():
                if n.startswith("ppt/comments/") and n.endswith(".xml"):
                    comments.append({"member": n, "bytes": len(zf.read(n))})
    except Exception:
        pass

    with open(os.path.join(d, "native_text", "slides.jsonl"), "w", encoding="utf-8") as fh:
        for s in slides:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")
    with open(os.path.join(d, "native_text", "notes.md"), "w", encoding="utf-8") as fh:
        fh.write("# 演讲者备注（分区，不混入正文）\n" + "".join(notes_md))
    with open(os.path.join(d, "figure_objects.jsonl"), "w", encoding="utf-8") as fh:
        for f in figs:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with open(os.path.join(d, "native_text", "raw.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    head = ["# %s\n" % os.path.basename(pptx),
            "> source_id: %s\n> 原始路径: `%s`\n> 幻灯片 %d 张（隐藏 %d 张）\n"
            "> 有备注 %d 张 / 表格 %d / 图片 %d / 图表 %d\n> 状态: 原始抽取（未清洗）\n"
            % (sid, pptx, len(slides), len(hid), n_notes, n_tables, n_pics, n_charts)]
    dmg = damaged_slide_parts(pptx)
    if dmg:
        head.append("> ⚠ 源文件缺陷：以下幻灯片部件在原件中已被破坏，内容无法恢复，须回原稿核对 —— "
                    + ", ".join("第%s张(%d字节)" % (x["slide_index"], x["bytes"]) for x in dmg) + "\n")
    with open(os.path.join(P.MD_DIR, "%s.full.md" % sid), "w", encoding="utf-8") as fh:
        fh.write("\n".join(head) + "\n".join(md))
        if notes_md:
            fh.write("\n\n---\n\n## 演讲者备注（分区）\n" + "".join(notes_md))

    rec = {"source_id": sid, "status": "extracted", "pptx": pptx, "rel_path": row["rel_path"],
           "slides": len(slides), "hidden_slides": sorted(hid), "slides_with_notes": n_notes,
           "tables": n_tables, "pictures": n_pics, "charts": n_charts,
           "comments_members": comments, "figure_objects": len(figs),
           "seconds": round(time.time() - t0, 2),
           "md_path": os.path.join(P.MD_DIR, "%s.full.md" % sid),
           "needs_visual_check": sorted(set(
               [f["slide"] for f in figs] + [s["slide"] for s in slides if s["hidden"]])),
           "damaged_slides": damaged_slide_parts(pptx)}
    if rec["damaged_slides"]:
        rec["needs_review"] = ("源文件内 %d 张幻灯片部件已被破坏（仅剩空根元素），"
                               "内容无法从原件恢复；须回原页/原稿核对或另找同版文件"
                               % len(rec["damaged_slides"]))
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-year", default="")
    a = ap.parse_args()
    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["format"] == "pptx" and r["in_scope"] == "Y"]
    if a.source:
        rows = [r for r in rows if r["source_id"] == a.source]
    if a.only_year:
        rows = [r for r in rows if r["rel_path"].startswith(a.only_year)]
    if a.limit:
        rows = rows[:a.limit]
    print("PPTX to process:", len(rows))
    for i, r in enumerate(rows, 1):
        try:
            rec = process_one(r)
        except Exception as e:
            d = sid_dir(r["source_id"])
            rec = {"source_id": r["source_id"], "status": "blocked",
                   "error": repr(e), "rel_path": r["rel_path"],
                   "original_path": r["original_path"]}

            # 替代路径1：补声明缺失命名空间后重试
            rep, repinfo = repair_namespaces(r["original_path"], os.path.join(d, "repaired"))
            rec["repair_attempt"] = {"repaired_path": rep, "ok": False, "detail": repinfo}
            if rep:
                try:
                    rec2 = process_one({"source_id": r["source_id"], "original_path": rep,
                                        "rel_path": r["rel_path"]})
                    rec2["status"] = "extracted_repaired"
                    rec2["repaired_from"] = r["original_path"]
                    rec2["repair_attempt"] = {"repaired_path": rep, "ok": True, "detail": repinfo}
                    rec = rec2
                except Exception as e2:
                    rec["repair_attempt"]["error2"] = repr(e2)

            # 替代路径2：soffice 转 pdf 后交由 PDF 通道
            if rec.get("status") == "blocked":
                cdir = os.path.join(d, "converted")
                env = P.env_with_fontconfig()
                rc, out, err = P.run([P.SOFFICE, "--headless", "--norestore",
                                      "--convert-to", "pdf", "--outdir", cdir,
                                      r["original_path"]], timeout=600, env=env)
                made = [f for f in os.listdir(cdir) if f.lower().endswith(".pdf")] if os.path.isdir(cdir) else []
                rec["soffice_fallback"] = {"rc": rc, "produced": made, "stderr": err[:300]}
                if made:
                    rec["status"] = "blocked_converted_to_pdf"
                    rec["block_reason"] = ("python-pptx 与命名空间修补均失败；已转出 PDF 供 PDF 通道处理"
                                           "（PPT 备注/隐藏页信息在转换中可能丢失，须另记）")
        print("[%d/%d] %s %s slides=%s notes=%s tbl=%s pic=%s %ss" % (
            i, len(rows), r["source_id"], rec.get("status"), rec.get("slides"),
            rec.get("slides_with_notes"), rec.get("tables"), rec.get("pictures"), rec.get("seconds")))
        with open(os.path.join(P.VAL_DIR, "03_pptx_extract_log.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
