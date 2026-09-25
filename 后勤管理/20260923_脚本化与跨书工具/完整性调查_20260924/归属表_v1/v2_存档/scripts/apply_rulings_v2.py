#!/usr/bin/env python3
"""apply_rulings_v2.py —— 追加式裁定日志（缺口5）v2：读 rulings.jsonl，把裁定叠加到 attribution.csv 上，
生成 attribution_ruled.csv；不改 attribution.csv 本身（脚本产物）、不改 rulings.jsonl（人工/主代理追加）。

相对 v1 的变更（minor项修复）：match() 里 `('module' not in scope) or True` 的 `or True` 是个bug，
会让 module 过滤形同虚设——任何 scope 只要 unit_id/qid 对上就无条件应用，不管 module 写的是什么。
v2 改为：如果 scope 里给了 module，就要求 field 必须是该 module 对应的 `归属_<module>` 列，
否则跳过并在 changelog 里记一条"scope.module 与 field 不一致，已跳过"的警告，而不是静默套用。

rulings.jsonl 字段同 v1，见 rulings.example.jsonl 与本文件 docstring。
用法：
  python3 apply_rulings_v2.py --attribution attribution.csv --rulings rulings.jsonl --out attribution_ruled.csv
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, json
from pathlib import Path
from collections import defaultdict

MODS = ['B1', 'B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']


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
    warnings = []

    for r in rulings:
        field = r.get('field')
        scope = r.get('scope', {})
        module = scope.get('module')
        if module and field != f'归属_{module}':
            warnings.append({
                'scope': scope, 'field': field,
                'warning': f"scope.module={module} 但 field={field}，两者不一致，本条裁定已跳过未应用"
                           f"（v1的match()有'or True'的bug会无条件套用，v2已修复并改为显式跳过+记录）。",
            })
            continue
        if field and field not in fieldnames:
            fieldnames.append(field)
            for row in rows:
                row.setdefault(field, '')
        for row in rows:
            if match(row, scope):
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
    log_path.write_text(json.dumps({'changes': changelog, 'skipped_module_mismatch': warnings}, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'rulings读取 {len(rulings)} 条；覆盖字段计数 {dict(applied)}；变更记录 {len(changelog)} 条、跳过{len(warnings)}条写入 {log_path}')


if __name__ == '__main__':
    main()
