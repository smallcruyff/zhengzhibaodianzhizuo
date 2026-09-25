#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compare_to_gold.py —— 用金标裁定核验模型判定批次的质量。

读 gold_final.json（人工/主代理对 gold/gold_units.json 做完最终裁定后的产物；
本脚本首次交付时该文件尚不存在，需先跑金标批次判定+人工核校再生成）与若干判定
结果文件（model_batch/judgments/*.json 或命令行给出的具体文件，格式见
model_batch/README_v1_batches.md 与本目录 README.md 的"判定结果文件格式"）。

按"单元×模块"计算"相关（主或跨）"的召回率/精确率/F1，分选择题/主观题、
分模块（B2/B3/PH/CU/X1/X2/MI/RE，以及仅用于剔除检查的B1）汇总；另外计算
"chk"（错收/维持/暂缓）结论与金标的一致率，并单独给"错收"类的精确率/召回率
（这是本项目最关心的误收风险指标）。

只读，不修改 gold_final.json、任何判定结果文件或 attribution 系列文件。

用法：
  /usr/bin/python3 compare_to_gold.py --gold gold_final.json \
      --judgments "model_batch/gold/judgments/*.json" --out compare_report.json
"""
import sys
sys.dont_write_bytecode = True
import argparse
import glob
import json
import os
from collections import defaultdict

MODULES = ["B1", "B2", "B3", "PH", "CU", "X1", "X2", "MI", "RE"]
REL_POSITIVE = {"主", "跨"}


def load_unit_list(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict) and "units" in data:
        return data["units"]
    if isinstance(data, list):
        return data
    raise ValueError("无法识别的金标/判定文件结构: %s（既不是{'units':[...]}也不是[...]）" % path)


def load_gold(path):
    units = load_unit_list(path)
    by_id = {}
    for u in units:
        uid = u.get("unit_id")
        if not uid:
            continue
        if uid in by_id:
            print("警告：gold_final.json 中 unit_id 重复：%s，后者覆盖前者" % uid, file=sys.stderr)
        by_id[uid] = u
    return by_id


def load_type_lookup(path):
    """gold_final.json / judgments/*.json 的 units 本身不带 type 字段（只有
    gold_units.json 这份原始抽样清单带 type: 选择题/主观题）。不联表就会导致
    qtype 恒为 'unknown'、分选择题/主观题的统计全部落空——这是本脚本原先的
    bug。path 不存在时返回空字典，调用方退回 unit_id 前缀猜测。"""
    if not path or not os.path.isfile(path):
        return {}
    units = load_unit_list(path)
    lookup = {}
    for u in units:
        uid = u.get("unit_id")
        t = u.get("type")
        if uid and t:
            lookup[uid] = t
    return lookup




def expand_judgment_globs(patterns):
    files = []
    for pat in patterns:
        hits = sorted(glob.glob(pat))
        if not hits and os.path.isfile(pat):
            hits = [pat]
        files.extend(hits)
    seen = set()
    out = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def load_predictions(paths):
    """Return unit_id -> (judgment_dict, source_label). Last file wins per
    unit_id on duplicates, with a warning (mirrors apply_rulings.py's
    last-write-wins convention for rulings)."""
    preds = {}
    dup_count = 0
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
        batch_id = data.get("batch_id", os.path.basename(p))
        judge = data.get("judge", "unknown")
        for u in data.get("units", []):
            uid = u.get("unit_id")
            if not uid:
                continue
            if uid in preds:
                dup_count += 1
            preds[uid] = (u, "%s:%s:%s" % ("model", judge, batch_id))
    if dup_count:
        print("警告：判定结果里有 %d 个 unit_id 出现在多份文件中，按加载顺序取最后一次覆盖前面" % dup_count,
              file=sys.stderr)
    return preds


def rel_modules(entry):
    rel = entry.get("rel") or {}
    return {m for m, v in rel.items() if v in REL_POSITIVE and m in MODULES}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gold", required=True, help="gold_final.json 路径（人工核定后的金标终稿）")
    ap.add_argument("--judgments", nargs="+", required=True,
                     help="判定结果文件或glob，可传多个，例如 model_batch/gold/judgments/*.json")
    ap.add_argument("--units", default=None,
                     help="带 type 字段（选择题/主观题）的原始抽样清单，默认取 --gold 同目录下的 "
                          "gold_units.json；gold_final.json/judgments 本身不带 type 字段，不联表分"
                          "选择题/主观题的统计会全部落空到 unknown")
    ap.add_argument("--out", default="compare_report.json")
    a = ap.parse_args()

    gold = load_gold(a.gold)
    units_path = a.units or os.path.join(os.path.dirname(os.path.abspath(a.gold)), "gold_units.json")
    type_lookup = load_type_lookup(units_path)
    if not type_lookup:
        print("警告：未能从 %s 加载 unit_id→type 映射，分选择题/主观题的统计会全部落到 unknown" % units_path,
              file=sys.stderr)
    judgment_files = expand_judgment_globs(a.judgments)
    if not judgment_files:
        print("错误：--judgments 未匹配到任何文件：%r" % a.judgments, file=sys.stderr)
        sys.exit(1)
    preds = load_predictions(judgment_files)

    common_ids = [uid for uid in gold if uid in preds]
    missing_from_pred = [uid for uid in gold if uid not in preds]
    extra_in_pred = [uid for uid in preds if uid not in gold]

    # ---- rel (主/跨) confusion matrix, split by type and by module ----
    # counts[key] -> {tp, fp, fn, tn}
    def new_counter():
        return {"tp": 0, "fp": 0, "fn": 0, "tn": 0}

    by_module = defaultdict(new_counter)
    by_type_module = defaultdict(new_counter)  # key=(type, module)
    by_type_overall = defaultdict(new_counter)  # key=type, micro-averaged over modules

    chk_total = 0
    chk_agree = 0
    chk_confusion = defaultdict(lambda: defaultdict(int))  # gold_label -> pred_label -> count
    misjudge_tp = 0  # gold=错收, pred=错收
    misjudge_fp = 0  # gold!=错收, pred=错收
    misjudge_fn = 0  # gold=错收, pred!=错收 (含缺判)

    n_missing_chk_pred = 0

    for uid in common_ids:
        g = gold[uid]
        p, _src = preds[uid]
        qtype = g.get("type") or p.get("type") or type_lookup.get(uid) or "unknown"
        g_rel = rel_modules(g)
        p_rel = rel_modules(p)
        for m in MODULES:
            gl = m in g_rel
            pl = m in p_rel
            bucket = "tp" if (gl and pl) else "fp" if (pl and not gl) else "fn" if (gl and not pl) else "tn"
            by_module[m][bucket] += 1
            by_type_module[(qtype, m)][bucket] += 1
            by_type_overall[qtype][bucket] += 1

        g_chk = g.get("chk") or {}
        p_chk = p.get("chk") or {}
        for m, g_label in g_chk.items():
            chk_total += 1
            p_label = p_chk.get(m)
            if p_label is None:
                n_missing_chk_pred += 1
            if p_label == g_label:
                chk_agree += 1
            chk_confusion[g_label][p_label if p_label is not None else "(缺判)"] += 1
            if g_label == "错收":
                if p_label == "错收":
                    misjudge_tp += 1
                else:
                    misjudge_fn += 1
            elif p_label == "错收":
                misjudge_fp += 1

    def prf(c):
        tp, fp, fn = c["tp"], c["fp"], c["fn"]
        precision = tp / (tp + fp) if (tp + fp) else None
        recall = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * precision * recall / (precision + recall)
              if precision is not None and recall is not None and (precision + recall) > 0 else None)
        return {"tp": tp, "fp": fp, "fn": fn, "tn": c["tn"], "precision": precision, "recall": recall, "f1": f1}

    report = {
        "gold_path": os.path.abspath(a.gold),
        "judgment_files": judgment_files,
        "n_gold_units": len(gold),
        "n_predicted_units": len(preds),
        "n_common": len(common_ids),
        "n_missing_from_predictions": len(missing_from_pred),
        "n_extra_in_predictions_not_in_gold": len(extra_in_pred),
        "missing_from_predictions_sample": missing_from_pred[:50],
        "rel_by_module": {m: prf(c) for m, c in by_module.items()},
        "rel_by_type": {t: prf(c) for t, c in by_type_overall.items()},
        "rel_by_type_and_module": {
            "%s|%s" % (t, m): prf(c) for (t, m), c in by_type_module.items()
        },
        "chk_agreement": {
            "n_compared": chk_total,
            "n_agree": chk_agree,
            "agreement_rate": (chk_agree / chk_total) if chk_total else None,
            "n_missing_pred": n_missing_chk_pred,
            "confusion": {g: dict(p) for g, p in chk_confusion.items()},
        },
        "misjudge_wrong_collection_class": {
            "note": "以 chk=='错收' 为正类：tp=金标与判定都判错收；fp=判定判错收但金标不是；fn=金标判错收但判定不是或缺判。",
            "tp": misjudge_tp, "fp": misjudge_fp, "fn": misjudge_fn,
            "precision": (misjudge_tp / (misjudge_tp + misjudge_fp)) if (misjudge_tp + misjudge_fp) else None,
            "recall": (misjudge_tp / (misjudge_tp + misjudge_fn)) if (misjudge_tp + misjudge_fn) else None,
        },
    }

    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=1)

    print("金标单元: %d  判定覆盖: %d  共有: %d  缺判: %d  多余: %d" % (
        len(gold), len(preds), len(common_ids), len(missing_from_pred), len(extra_in_pred)))
    print("chk一致率: %s (%d/%d)" % (report["chk_agreement"]["agreement_rate"], chk_agree, chk_total))
    print("错收类 precision=%s recall=%s" % (
        report["misjudge_wrong_collection_class"]["precision"],
        report["misjudge_wrong_collection_class"]["recall"]))
    print("详见", a.out)


if __name__ == "__main__":
    main()
