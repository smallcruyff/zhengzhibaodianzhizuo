#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""merge_judgments.py —— 把模型判定批次结果并入 rulings.jsonl，找出需要升级
复判的单元，并（--final）在升级结果并入后重建 attribution_ruled.csv 与各书清单。

判定结果文件格式（judge 输出，见本目录 README.md）：
  {"batch_id": "...", "judge": "<模型名>", "units": [
    {"unit_id": "...",
     "rel": {"B3": "主", "B2": "跨"},
     "opt": {"①": ["B3"], ...},
     "chk": {"B3": "维持", "PH": "错收"},
     "conf": "高|中|低",
     "why": "..."}]}

写入 rulings.jsonl 的记录沿用 apply_rulings*.py 已在用的格式（scope/field/value/
reason/ruler/rule_version/ts），本脚本只是这份日志新增来源：
  - ruler = "model:<judge>:<batch_id>"
  - rel[m] in {主,跨} 且该模块当前不是 COLLECTED  → 记一条"候选相关，待人工核收"
    （field=归属_<m>, value=IN，不直接标COLLECTED——收不收书稿仍由人工/主代理定）。
  - chk[m] == "维持" → 记一条确认性留痕（value 不变，只留审计轨迹）。
  - chk[m] == "错收" → 记一条 value=OUT 的候选修正（同样不直接改书稿，只是归属表候选值）。
  - chk[m] == "暂缓" → 只留痕，不改 value。
本脚本不改 attribution.csv 本身、不改任何书稿/题库/Skill文件；--final 时只在
新写出的 attribution_ruled.csv / book_lists/ 里落地，且需要显式传 --attribution
指向要参照的 attribution.csv（默认同目录）。

用法：
  # 1) 把已产出的判定结果并入日志，找出需要升级复判的单元
  /usr/bin/python3 merge_judgments.py --judgments-dir model_batch/judgments \
      --rulings rulings.jsonl --rule-version 2026-09-24-model-batch-v1 \
      --escalation-out model_batch/escalation

  # 2) 升级批次判完后，再次运行、传入升级结果并 --final，重建 ruled 产物
  /usr/bin/python3 merge_judgments.py --judgments-dir model_batch/judgments \
      --escalation-judgments-dir model_batch/escalation/judgments \
      --rulings rulings.jsonl --rule-version 2026-09-24-model-batch-v1 \
      --final --attribution attribution.csv --out-ruled attribution_ruled.csv \
      --book-lists-dir book_lists
"""
import sys
sys.dont_write_bytecode = True
import argparse
import csv
import datetime
import glob
import json
import os
from collections import defaultdict

MODULES = ["B2", "B3", "PH", "CU", "X1", "X2", "MI", "RE"]
CHOICE_MAX_PER_BATCH = 60
SUBJ_MAX_PER_BATCH = 25
CHAR_BUDGET = 39500
ESCALATION_MAX_PER_BATCH = 40


def now_ts():
    return datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def load_json_files(dir_or_glob):
    if not dir_or_glob:
        return []
    if os.path.isdir(dir_or_glob):
        paths = sorted(glob.glob(os.path.join(dir_or_glob, "*.json")))
    else:
        paths = sorted(glob.glob(dir_or_glob))
    out = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            out.append((p, json.load(fh)))
    return out


def load_batch_universe(*dirs):
    """Index every unit slice that appears in the given batch/gold directories,
    so we know the expected unit set (for 缺判 detection) and can re-pack full
    unit content into escalation batches without touching bank.py/题库 again."""
    index = {}
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        for p in sorted(glob.glob(os.path.join(d, "*.json"))):
            with open(p, encoding="utf-8") as fh:
                data = json.load(fh)
            units = data.get("units", [])
            for u in units:
                uid = u.get("unit_id")
                if uid:
                    index[uid] = u
    return index


def load_judgments(dir_or_glob):
    """unit_id -> (judgment, judge, batch_id, source_path)."""
    out = {}
    dup = 0
    for path, data in load_json_files(dir_or_glob):
        judge = data.get("judge", "unknown")
        batch_id = data.get("batch_id", os.path.basename(path))
        for u in data.get("units", []):
            uid = u.get("unit_id")
            if not uid:
                continue
            if uid in out:
                dup += 1
            out[uid] = (u, judge, batch_id, path)
    if dup:
        print("警告：判定结果里 %d 个 unit_id 重复出现，按加载顺序（sorted文件名）取最后一次" % dup,
              file=sys.stderr)
    return out


def ruling_dedup_key(obj):
    """Identity for de-duplication purposes: everything except 'ts', so
    re-running merge_judgments on the same judgment files is idempotent
    (a fresh wall-clock timestamp must not look like a new ruling)."""
    return json.dumps({k: v for k, v in obj.items() if k != "ts"},
                       sort_keys=True, ensure_ascii=False)


def existing_ruling_keys(path):
    keys = set()
    if not os.path.isfile(path):
        return keys
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            keys.add(ruling_dedup_key(obj))
    return keys


def build_rulings_for_unit(uid, judgment, source_label, rule_version):
    out = []
    rel = judgment.get("rel") or {}
    chk = judgment.get("chk") or {}
    why = judgment.get("why", "")
    conf = judgment.get("conf", "")

    for m, label in rel.items():
        if m not in MODULES:
            continue
        if label in ("主", "跨") and m not in chk:
            # candidate addition signal; does not itself flip 书稿收录，只留
            # 待人工核收的候选值，供后续合稿判断。
            out.append({
                "ts": now_ts(), "ruler": source_label,
                "scope": {"unit_id": uid}, "field": "归属_%s" % m, "value": "IN",
                "reason": "model judge: rel=%s conf=%s why=%s" % (label, conf, why),
                "rule_version": rule_version,
            })

    for m, label in chk.items():
        if m not in MODULES:
            continue
        if label == "维持":
            out.append({
                "ts": now_ts(), "ruler": source_label,
                "scope": {"unit_id": uid}, "field": "归属_%s" % m, "value": "COLLECTED",
                "reason": "model judge: chk=维持 conf=%s why=%s" % (conf, why),
                "rule_version": rule_version,
            })
        elif label == "错收":
            out.append({
                "ts": now_ts(), "ruler": source_label,
                "scope": {"unit_id": uid}, "field": "归属_%s" % m, "value": "OUT",
                "reason": "model judge: chk=错收候选 conf=%s why=%s（书稿是否真删仍需人工确认，"
                          "本条只改归属表候选值，不代为改书稿）" % (conf, why),
                "rule_version": rule_version,
            })
        elif label == "暂缓":
            out.append({
                "ts": now_ts(), "ruler": source_label,
                "scope": {"unit_id": uid}, "field": "归属_%s" % m, "value": "MAYBE",
                "reason": "model judge: chk=暂缓(证据不足) conf=%s why=%s" % (conf, why),
                "rule_version": rule_version,
            })
    return out


def needs_escalation(uid, judgment):
    if judgment is None:
        return "缺判"
    if judgment.get("conf") == "低":
        return "conf低"
    chk = judgment.get("chk") or {}
    if any(v == "错收" for v in chk.values()):
        return "chk错收"
    return None


def pack_escalation_batches(units_map, uids, out_dir, rule_version):
    os.makedirs(out_dir, exist_ok=True)
    choice = [u for u in uids if (units_map.get(u) or {}).get("type") == "选择题"]
    subj = [u for u in uids if (units_map.get(u) or {}).get("type") == "主观题"]
    other = [u for u in uids if u not in choice and u not in subj]
    written = []

    def pack(ids, prefix, qtype):
        idx = 1
        cur = []
        for uid in ids:
            cur.append(uid)
            if len(cur) >= ESCALATION_MAX_PER_BATCH:
                written.append(flush(cur, prefix, idx, qtype))
                idx += 1
                cur = []
        if cur:
            written.append(flush(cur, prefix, idx, qtype))

    def flush(ids, prefix, idx, qtype):
        bid = "%s%02d" % (prefix, idx)
        payload = {
            "batch_id": bid, "rule_version": rule_version, "type": qtype,
            "n_units": len(ids),
            "units": [units_map[u] for u in ids if u in units_map],
        }
        path = os.path.join(out_dir, bid + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=1)
        return {"id": bid, "path": path, "type": qtype, "n_units": len(ids)}

    pack(choice, "escc", "choice")
    pack(subj, "escs", "subjective")
    if other:
        pack(other, "escx", "mixed")
    return written


def apply_rulings_to_attribution(attribution_csv, rulings_path, out_csv):
    """Same semantics as scripts/apply_rulings_v3.py's match()+apply loop
    (last matching ruling wins per field), reimplemented here so this script
    is self-contained for --final without importing a sibling file."""
    with open(attribution_csv, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)
    by_unit = {r["unit_id"]: r for r in rows}
    by_qid = defaultdict(list)
    for r in rows:
        by_qid[r["qid"]].append(r)

    rulings = []
    if os.path.isfile(rulings_path):
        with open(rulings_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rulings.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    changelog = []
    for r in rulings:
        field = r.get("field")
        scope = r.get("scope", {})
        if field and field not in fieldnames:
            fieldnames.append(field)
            for row in rows:
                row.setdefault(field, "")
        targets = []
        if "unit_id" in scope and scope["unit_id"] in by_unit:
            targets = [by_unit[scope["unit_id"]]]
        elif "qid" in scope:
            targets = by_qid.get(scope["qid"], [])
        for row in targets:
            old = row.get(field, "")
            new = r.get("value", "")
            if old != new:
                changelog.append({"unit_id": row["unit_id"], "field": field,
                                   "old": old, "new": new, "reason": r.get("reason", ""),
                                   "ruler": r.get("ruler", ""), "ts": r.get("ts", "")})
            row[field] = new

    if "ruled" not in fieldnames:
        fieldnames.append("ruled")
    for row in rows:
        row["ruled"] = "yes" if rulings else "no"

    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    log_path = os.path.splitext(out_csv)[0] + ".changelog.json"
    with open(log_path, "w", encoding="utf-8") as fh:
        json.dump({"changes": changelog}, fh, ensure_ascii=False, indent=1)

    return rows, changelog


def write_book_lists(rows, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for m in MODULES:
        field = "归属_%s" % m
        sel = [r for r in rows if r.get(field) == "COLLECTED"]
        path = os.path.join(out_dir, "%s_collected.csv" % m)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["unit_id", "qid", "exam_id_canonical", "num", "subq", "type", "grain", "admission", field])
            for r in sel:
                w.writerow([r.get("unit_id"), r.get("qid"), r.get("exam_id_canonical"), r.get("num"),
                            r.get("subq"), r.get("type"), r.get("grain"), r.get("admission"), r.get(field)])
        written.append({"module": m, "path": path, "n": len(sel)})
    return written


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judgments-dir", required=True, help="目录或glob，正常批次的判定结果")
    ap.add_argument("--escalation-judgments-dir", default=None, help="--final 时：升级批次的判定结果（覆盖原判）")
    ap.add_argument("--gold", default=None, help="可选：gold_final.json，仅用于把金标单元也纳入覆盖率统计")
    ap.add_argument("--rulings", default="rulings.jsonl")
    ap.add_argument("--rule-version", required=True)
    ap.add_argument("--batches-dir", default="model_batch/batches")
    ap.add_argument("--gold-dir", default="model_batch/gold")
    ap.add_argument("--escalation-out", default=None, help="目录：把需升级复判的单元切成升级批次写到这里")
    ap.add_argument("--final", action="store_true",
                     help="并入升级结果（覆盖原判）后重建 attribution_ruled.csv 与各书清单")
    ap.add_argument("--attribution", default="attribution.csv")
    ap.add_argument("--out-ruled", default="attribution_ruled.csv")
    ap.add_argument("--book-lists-dir", default="book_lists")
    a = ap.parse_args()

    universe = load_batch_universe(a.batches_dir, a.gold_dir)
    if a.gold:
        for u in load_unit_list_safe(a.gold):
            universe.setdefault(u.get("unit_id"), u)

    judgments = load_judgments(a.judgments_dir)
    source_label_of = {uid: "model:%s:%s" % (j, b) for uid, (_, j, b, _) in judgments.items()}

    if a.final and a.escalation_judgments_dir:
        esc_judgments = load_judgments(a.escalation_judgments_dir)
        for uid, (u, j, b, p) in esc_judgments.items():
            judgments[uid] = (u, j, b, p)
            source_label_of[uid] = "model:%s:%s" % (j, b)

    existing_keys = existing_ruling_keys(a.rulings)
    new_rulings = []
    for uid, (judgment, judge, batch_id, path) in judgments.items():
        for r in build_rulings_for_unit(uid, judgment, source_label_of[uid], a.rule_version):
            key = ruling_dedup_key(r)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            new_rulings.append(r)

    if new_rulings:
        with open(a.rulings, "a", encoding="utf-8") as fh:
            for r in new_rulings:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    print("本次新增 rulings: %d 条（写入 %s）" % (len(new_rulings), a.rulings))

    # ---- escalation set ----
    escalate = {}
    for uid in universe:
        j = judgments.get(uid, (None,))[0]
        reason = needs_escalation(uid, j)
        if reason:
            escalate[uid] = reason
    print("需升级复判单元: %d（缺判=%d, conf低=%d, chk错收=%d，可重叠计一次）" % (
        len(escalate),
        sum(1 for r in escalate.values() if r == "缺判"),
        sum(1 for r in escalate.values() if r == "conf低"),
        sum(1 for r in escalate.values() if r == "chk错收"),
    ))

    if a.escalation_out and escalate:
        written = pack_escalation_batches(universe, sorted(escalate.keys()), a.escalation_out, a.rule_version)
        with open(os.path.join(a.escalation_out, "escalation_manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"rule_version": a.rule_version, "n_units": len(escalate),
                       "reasons": escalate, "batches": written}, fh, ensure_ascii=False, indent=1)
        print("升级批次已写入 %s（%d 个批次）" % (a.escalation_out, len(written)))

    if a.final:
        rows, changelog = apply_rulings_to_attribution(a.attribution, a.rulings, a.out_ruled)
        print("attribution_ruled 已重建: %s（变更 %d 条）" % (a.out_ruled, len(changelog)))
        lists = write_book_lists(rows, a.book_lists_dir)
        for l in lists:
            print("  %s: %d 条 -> %s" % (l["module"], l["n"], l["path"]))


def load_unit_list_safe(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and "units" in data:
            return data["units"]
        if isinstance(data, list):
            return data
    except Exception as e:
        print("警告：无法读取 --gold %s: %s" % (path, e), file=sys.stderr)
    return []


if __name__ == "__main__":
    main()
