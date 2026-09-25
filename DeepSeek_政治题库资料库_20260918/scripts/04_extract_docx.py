#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""阶段3：DOCX 提取（保真、结构完整）。

规范四.3：不能只读 paragraphs；必须按正文顺序读取段落、自动编号、表格、文本框、
嵌图、公式、脚注、尾注、批注和修订信息。

产出：
  evidence/{sid}/native_text/raw.md       按 body 顺序的完整结构转写
  evidence/{sid}/native_text/parts.jsonl  逐块记录（类型/序号/定位/内容）
  evidence/{sid}/figure_objects.jsonl     图片/图形对象清单（约束2）
  evidence/{sid}/comments.json            批注 + 修订（单列，不擅自接受）
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

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"
V = "{urn:schemas-microsoft-com:vml}"
WPS = "{http://schemas.microsoft.com/office/word/2010/wordprocessingShape}"


def sid_dir(sid):
    d = os.path.join(P.EVID_DIR, sid)
    P.ensure_dirs(d, os.path.join(d, "native_text"), os.path.join(d, "figures"),
                  os.path.join(d, "visual_transcript"), os.path.join(d, "cleaned"))
    return d


def para_text(p):
    """段落文本，含 w:t / w:tab / w:br，并保留修订标记。"""
    out = []
    for node in p.iter():
        tag = node.tag
        if tag == W + "t":
            out.append(node.text or "")
        elif tag == W + "tab":
            out.append("\t")
        elif tag in (W + "br", W + "cr"):
            out.append("\n")
        elif tag == W + "delText":
            out.append("〔修订删除:%s〕" % (node.text or ""))
        elif tag == W + "ins":
            pass
    return "".join(out)


def para_marks(p):
    """保留具有题意作用的格式：加粗/下划线/着重/颜色。"""
    marks = set()
    for r in p.iter(W + "r"):
        rPr = r.find(W + "rPr")
        if rPr is None:
            continue
        if rPr.find(W + "b") is not None:
            marks.add("bold")
        if rPr.find(W + "u") is not None:
            marks.add("underline")
        if rPr.find(W + "em") is not None:
            marks.add("emphasis")
        c = rPr.find(W + "color")
        if c is not None and c.get(W + "val") not in (None, "auto", "000000"):
            marks.add("color:" + c.get(W + "val"))
    return sorted(marks)


def table_to_struct(tbl):
    """表格结构：保留合并关系与空白。"""
    rows = []
    for tr in tbl.findall(W + "tr"):
        cells = []
        for tc in tr.findall(W + "tc"):
            tcPr = tc.find(W + "tcPr")
            span = 1
            vmerge = None
            if tcPr is not None:
                gs = tcPr.find(W + "gridSpan")
                if gs is not None:
                    try:
                        span = int(gs.get(W + "val"))
                    except Exception:
                        span = 1
                vm = tcPr.find(W + "vMerge")
                if vm is not None:
                    vmerge = vm.get(W + "val") or "continue"
            txt = "\n".join(para_text(p) for p in tc.findall(W + "p"))
            cells.append({"text": txt, "gridSpan": span, "vMerge": vmerge})
        rows.append(cells)
    return rows


def table_to_md(rows):
    """简单表 -> Markdown；含合并则退回 HTML 结构（规范五.2）。"""
    has_merge = any(c["gridSpan"] != 1 or c["vMerge"] for r in rows for c in r)
    if not has_merge and rows and all(len(r) == len(rows[0]) for r in rows):
        out = []
        head = [c["text"].replace("\n", "<br>") or " " for c in rows[0]]
        out.append("| " + " | ".join(head) + " |")
        out.append("| " + " | ".join(["---"] * len(head)) + " |")
        for r in rows[1:]:
            out.append("| " + " | ".join((c["text"].replace("\n", "<br>") or " ") for c in r) + " |")
        return "\n".join(out), False
    out = ["<table>"]
    for r in rows:
        out.append("  <tr>")
        for c in r:
            attrs = ""
            if c["gridSpan"] != 1:
                attrs += ' colspan="%d"' % c["gridSpan"]
            if c["vMerge"]:
                attrs += ' vmerge="%s"' % c["vMerge"]
            out.append("    <td%s>%s</td>" % (attrs, (c["text"] or "").replace("\n", "<br>")))
        out.append("  </tr>")
    out.append("</table>")
    return "\n".join(out), True


def read_zip_xml(path, member):
    try:
        with zipfile.ZipFile(path) as zf:
            if member in zf.namelist():
                return zf.read(member).decode("utf-8", "replace")
    except Exception:
        pass
    return ""


def extract_comments(path):
    """批注与修订单列（不擅自接受修订）。"""
    res = {"comments": [], "revisions": {"ins": 0, "del": 0}}
    xml = read_zip_xml(path, "word/comments.xml")
    if xml:
        from lxml import etree
        try:
            root = etree.fromstring(xml.encode("utf-8"))
            for c in root.iter(W + "comment"):
                res["comments"].append({
                    "id": c.get(W + "id"), "author": c.get(W + "author"),
                    "date": c.get(W + "date"),
                    "text": "".join(t.text or "" for t in c.iter(W + "t")),
                })
        except Exception as e:
            res["comments_error"] = repr(e)
    dxml = read_zip_xml(path, "word/document.xml")
    if dxml:
        res["revisions"]["ins"] = dxml.count("<w:ins ")
        res["revisions"]["del"] = dxml.count("<w:del ")
    return res


def process_one(row):
    sid = row["source_id"]
    docx = row["original_path"]
    d = sid_dir(sid)
    t0 = time.time()
    from docx import Document
    doc = Document(docx)
    body = doc.element.body

    parts = []
    md = []
    figs = []
    seq = 0
    tbl_i = 0
    for child in body.iterchildren():
        tag = child.tag
        if tag == W + "p":
            seq += 1
            txt = para_text(child)
            marks = para_marks(child)
            ndraw = len(list(child.iter(WP + "drawing"))) + len(list(child.iter(WP + "inline")))
            ntxbx = len(list(child.iter(WPS + "txbx")))
            npict = len(list(child.iter(V + "shape"))) + len(list(child.iter(V + "imagedata")))
            loc = {"kind": "p", "index": seq}
            parts.append({"type": "paragraph", "seq": seq, "text": txt, "marks": marks,
                          "drawings": ndraw, "textboxes": ntxbx, "pict": npict})
            if txt.strip():
                prefix = ""
                if "bold" in marks:
                    prefix += "**"
                md.append(prefix + txt.rstrip() + ("**" if prefix else ""))
            else:
                md.append("")
            if ndraw or npict:
                figs.append({"kind": "drawing", "paragraph_seq": seq, "drawings": ndraw,
                             "pict": npict, "textboxes": ntxbx,
                             "near_text": txt.strip()[:80]})
        elif tag == W + "tbl":
            tbl_i += 1
            seq += 1
            rows = table_to_struct(child)
            t, is_html = table_to_md(rows)
            parts.append({"type": "table", "seq": seq, "table_index": tbl_i,
                          "rows": len(rows), "html_fallback": is_html, "struct": rows})
            md.append("\n<!-- 表格 %d（%d 行%s） -->" % (tbl_i, len(rows), "，含合并" if is_html else ""))
            md.append(t)
            md.append("")
        else:
            continue

    # 页眉页脚
    try:
        hf = []
        for s in doc.sections:
            for name, part in (("header", s.header), ("footer", s.footer)):
                for p in part.paragraphs:
                    if p.text.strip():
                        hf.append({"section": name, "text": p.text.strip()})
        parts.append({"type": "header_footer", "items": hf})
    except Exception:
        pass

    comments = extract_comments(docx)

    with open(os.path.join(d, "native_text", "parts.jsonl"), "w", encoding="utf-8") as fh:
        for p in parts:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")
    with open(os.path.join(d, "figure_objects.jsonl"), "w", encoding="utf-8") as fh:
        for f in figs:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    with open(os.path.join(d, "comments.json"), "w", encoding="utf-8") as fh:
        json.dump(comments, fh, ensure_ascii=False, indent=2)
    with open(os.path.join(d, "native_text", "raw.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md))

    head = ["# %s\n" % os.path.basename(docx),
            "> source_id: %s\n> 原始路径: `%s`\n> 状态: 原始抽取（未清洗）\n> 段落 %d / 表格 %d / 图形对象 %d\n"
            % (sid, docx, sum(1 for p in parts if p["type"] == "paragraph"),
               tbl_i, len(figs))]
    if comments["comments"]:
        head.append("\n## 批注（单列，未擅自接受）\n")
        for c in comments["comments"]:
            head.append("- [%s %s] %s" % (c.get("author"), c.get("date"), c.get("text")))
    if comments["revisions"]["ins"] or comments["revisions"]["del"]:
        head.append("\n## 修订标记计数\n- 插入 w:ins = %d；删除 w:del = %d\n"
                    % (comments["revisions"]["ins"], comments["revisions"]["del"]))
    with open(os.path.join(P.MD_DIR, "%s.full.md" % sid), "w", encoding="utf-8") as fh:
        fh.write("\n".join(head) + "\n" + "\n".join(md))

    rec = {"source_id": sid, "status": "extracted", "docx": docx, "rel_path": row["rel_path"],
           "paragraphs": sum(1 for p in parts if p["type"] == "paragraph"),
           "tables": tbl_i, "figure_objects": len(figs),
           "comments": len(comments["comments"]),
           "revisions": comments["revisions"],
           "chars": sum(len(p.get("text", "")) for p in parts if p["type"] == "paragraph"),
           "seconds": round(time.time() - t0, 2),
           "md_path": os.path.join(P.MD_DIR, "%s.full.md" % sid)}
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only-year", default="")
    ap.add_argument("--converted", action="store_true",
                    help="处理 .doc/.rtf 经 06_convert_legacy 转出的 docx 副本")
    a = ap.parse_args()
    if a.converted:
        # 从 evidence/*/convert_log.json 取转换成功项
        rows = []
        for sid in sorted(os.listdir(P.EVID_DIR)):
            lp = os.path.join(P.EVID_DIR, sid, "convert_log.json")
            if not os.path.isfile(lp):
                continue
            try:
                rec = json.load(open(lp, encoding="utf-8"))
            except Exception:
                continue
            cp = rec.get("converted_path")
            if not cp or not os.path.isfile(cp) or not cp.endswith(".docx"):
                continue
            rows.append({"source_id": sid, "original_path": cp,
                         "rel_path": rec.get("rel_path", ""), "format": "docx",
                         "in_scope": "Y", "converted_from": rec.get("src")})
        if a.source:
            rows = [r for r in rows if r["source_id"] == a.source]
        if a.only_year:
            rows = [r for r in rows if r["rel_path"].startswith(a.only_year)]
        if a.limit:
            rows = rows[:a.limit]
        print("converted DOCX to process:", len(rows))
        for i, r in enumerate(rows, 1):
            try:
                rec = process_one(r)
            except Exception as e:
                rec = {"source_id": r["source_id"], "status": "blocked", "error": repr(e),
                       "rel_path": r["rel_path"]}
            rec["converted_from"] = r.get("converted_from")
            print("[%d/%d] %s %s paras=%s tbl=%s fig=%s" % (
                i, len(rows), r["source_id"], rec.get("status"), rec.get("paragraphs"),
                rec.get("tables"), rec.get("figure_objects")))
            with open(os.path.join(P.VAL_DIR, "03_docx_extract_log.jsonl"), "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return

    with open(os.path.join(P.INDEX_DIR, "source_manifest.csv"), "r", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["format"] == "docx" and r["in_scope"] == "Y"]
    if a.source:
        rows = [r for r in rows if r["source_id"] == a.source]
    if a.only_year:
        rows = [r for r in rows if r["rel_path"].startswith(a.only_year)]
    if a.limit:
        rows = rows[:a.limit]
    print("DOCX to process:", len(rows))
    for i, r in enumerate(rows, 1):
        try:
            rec = process_one(r)
        except Exception as e:
            rec = {"source_id": r["source_id"], "status": "blocked", "error": repr(e),
                   "rel_path": r["rel_path"]}
        print("[%d/%d] %s %s paras=%s tbl=%s fig=%s %ss" % (
            i, len(rows), r["source_id"], rec.get("status"), rec.get("paragraphs"),
            rec.get("tables"), rec.get("figure_objects"), rec.get("seconds")))
        with open(os.path.join(P.VAL_DIR, "03_docx_extract_log.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
