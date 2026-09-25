#!/usr/bin/env python3
"""apply_rulings.py —— 追加式裁定日志（缺口5）：读 rulings.jsonl，把裁定叠加到 attribution.csv 上，
生成 attribution_ruled.csv；不改 attribution.csv 本身（脚本产物）、不改 rulings.jsonl（人工/主代理追加）。

rulings.jsonl 每行一条 JSON，字段：
  ts            裁定时间，ISO8601
  ruler         裁定人，例如 "主代理"、"用户"
  scope         {"unit_id": "..."}（推荐，精确到小问/题）或 {"qid": "...", "module": "B3"}（该题整条对某模块的裁定）
  field         要覆盖的列名，取值见 attribution.csv 表头，例如 "归属_B3"、"admission"、"evidence"
  value         新值
  reason        裁定理由（写清依据：E1页码/主代理判断/用户明确指示等）
  rule_version  这条裁定对应哪个规则版本；规则改版后，脚本据此判断哪些旧裁定需要重新审视（本脚本目前只记录，不自动失效——
                失效逻辑留给主代理按 rule_version 是否落后于 attribution.csv 当前 rule_version 来决定是否重跑）

用法：
  python3 apply_rulings.py --attribution attribution.csv --rulings rulings.jsonl --out attribution_ruled.csv
无 rulings.jsonl 或为空文件时，输出与输入相同（只加一列 ruled=no，供下游区分）。
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, json
from pathlib import Path
from collections import defaultdict


def load_rulings(path):
    p = Path(path)
    if not p.exists():
        return []
    out = []
    for i, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
        line = line.strip()
        if not line or line.startswith('//') or line.startswith('#'):
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError as e:
            print(f'警告：rulings.jsonl 第{i}行解析失败，已跳过：{e}', file=sys.stderr)
    return out


def match(row, scope):
    if 'unit_id' in scope:
        return row['unit_id'] == scope['unit_id']
    if 'qid' in scope:
        return row['qid'] == scope['qid']
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', default='attribution.csv')
    ap.add_argument('--rulings', default='rulings.jsonl')
    ap.add_argument('--out', default='attribution_ruled.csv')
    a = ap.parse_args()

    with open(a.attribution, encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    rulings = load_rulings(a.rulings)
    applied = defaultdict(int)
    changelog = []

    for r in rulings:
        field = r.get('field')
        scope = r.get('scope', {})
        if field and field not in fieldnames:
            fieldnames.append(field)
            for row in rows:
                row.setdefault(field, '')
        for row in rows:
            if match(row, scope) and (('module' not in scope) or True):
                old = row.get(field, '')
                new = r.get('value', '')
                if old != new:
                    changelog.append({
                        'unit_id': row['unit_id'], 'field': field, 'old': old, 'new': new,
                        'reason': r.get('reason', ''), 'ruler': r.get('ruler', ''), 'ts': r.get('ts', ''),
                    })
                row[field] = new
                applied[field] += 1

    if 'ruled' not in fieldnames:
        fieldnames.append('ruled')
    for row in rows:
        row['ruled'] = 'yes' if rulings else 'no'

    with open(a.out, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    log_path = Path(a.out).with_suffix('.changelog.json')
    log_path.write_text(json.dumps(changelog, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'rulings读取 {len(rulings)} 条；覆盖字段计数 {dict(applied)}；变更记录 {len(changelog)} 条写入 {log_path}')


if __name__ == '__main__':
    main()
