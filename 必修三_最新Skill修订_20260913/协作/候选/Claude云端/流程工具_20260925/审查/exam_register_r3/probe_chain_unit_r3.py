#!/usr/bin/env python3
"""r3 纯函数探针：build_rename_chain 在两层链、末端 conflict 时的返回（不读题库）。"""
import sys, json
sys.dont_write_bytecode = True
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import exam_register as er  # noqa
occ = {
    'BJ-2024-XX': {'id_mismatch': {'registered_year': 2024, 'evidence_cohort_year': 2025}, 'cohort_status': 'OK', 'cohort_year': 2025,
                   'duplicates': [], 'suggestion': {'suggested_id': 'BJ-2025-XX', 'occupied': True}},
    'BJ-2025-XX': {'id_mismatch': None, 'cohort_status': 'OK', 'cohort_year': 2025, 'duplicates': [],
                   'suggestion': {'suggested_id': 'BJ-2025-XX', 'occupied': False}},
}
r = er.build_rename_chain([], 'BJ-2024-XX', lambda x: occ.get(x), own_id=None)
print(json.dumps(r, ensure_ascii=False, indent=1))
print('kind', r['kind'], '| redirects non-empty while note says 不给出重定向表:', bool(r['redirects']) and '不给出重定向表' in r['note'])
