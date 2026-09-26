#!/usr/bin/env python3
"""r3 探针：audit 报告里 has_text_layer=True 的原件，统计其前 6 页文字里 CJK 字符占比；
占比极低（<10%）即“有字符但无可读中文”的乱码文字层（印厂专用编码/轮廓字），工具仍当有文字层。只读。"""
import sys, json, re
sys.dont_write_bytecode = True
from pathlib import Path
HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
import exam_register as er  # noqa
rep = json.load(open(sys.argv[1], encoding='utf-8'))
cjk = re.compile(r'[一-鿿]')
rows = []
for it in rep['items']:
    for rf in it.get('raw_files', []):
        if not rf.get('has_text_layer'):
            continue
        t, eng = er.extract_file_text(Path(rf['path']), max_pages=6, max_chars=8000)
        s = t.strip()
        ratio = len(cjk.findall(s)) / max(1, len(s))
        if ratio < 0.10:
            rows.append((it['exam_id'], it['cohort_status'], round(ratio, 3), len(s), Path(rf['path']).name, repr(s[:60])))
for r in rows:
    print(*r)
print('garbled_count', len(rows))
