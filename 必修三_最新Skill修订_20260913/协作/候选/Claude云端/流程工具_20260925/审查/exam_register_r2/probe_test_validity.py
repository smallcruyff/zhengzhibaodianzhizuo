"""r2 探针：测试 2a 的“届别不符”断言是否可能失败——把已知错号卷放进对照组，按 2a 原样判定。只读。"""
import json, subprocess, sys
from pathlib import Path
C = Path(__file__).resolve().parents[2]
P = str(C / 'profiles_cloud' / 'bixiu3.json')
bad = []
for eid in ['BJ-2023-HD-QIZHONG', 'BJ-2024-CY-QIZHONG']:   # 已知错号卷，2a 若有效应当判“误报届别不符”
    p = subprocess.run([sys.executable, '-B', str(C / 'exam_register.py'), 'check', '--exam-id', eid, '--profile', P], capture_output=True, text=True)
    d = json.loads(p.stdout)
    if d.get('id_mismatch') is not None:          # ← run_tests 2a 第 185 行原样
        bad.append(f'{eid}: 误报届别不符 {d["id_mismatch"]}')
    print(eid, 'stdout keys 含 id_mismatch?', 'id_mismatch' in d, '| cohort', d['cohort_year'], '| issues[0]', d['issues'][:1])
print('2a 判定：', 'PASS（断言恒真，已知错号卷也通过）' if not bad else 'FAIL', bad)
