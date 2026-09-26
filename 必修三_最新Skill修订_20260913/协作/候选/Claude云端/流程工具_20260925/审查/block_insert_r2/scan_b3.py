import sys
sys.dont_write_bytecode = True
import csv, zipfile, re, json
from pathlib import Path
from lxml import etree
R = Path('/home/user/zhengzhibaodianzhizuo')
raw = R / '00_共同资料/原材料'
F = R / '后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924/归属表_v1/各书清单_v4/B3_漏收候选.csv'
rows = list(csv.DictReader(open(F, encoding='utf-8-sig')))
files = list(csv.DictReader(open(R / 'DeepSeek_政治题库资料库_20260918/indexes/exam_files.csv', encoding='utf-8-sig')))
by_exam = {}
for f in files:
    by_exam.setdefault(f['exam_id'], []).append(f)
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
out = []
for r in rows:
    if r['题型'] != '主观题':
        continue
    ex = r['卷']
    docx_papers = [f for f in by_exam.get(ex, []) if f['format'] == 'docx' and f['role'] in ('试卷', '试题', '试卷+答案', '题目', 'paper') ]
    roles = sorted({(f['format'], f['role']) for f in by_exam.get(ex, [])})
    qmd = list((R / 'DeepSeek_政治题库资料库_20260918/questions' / ex).glob('*.md')) if (R / 'DeepSeek_政治题库资料库_20260918/questions' / ex).exists() else []
    uid = r['unit_id']
    qn = re.match(r'(\d+)', r['题号_小问']).group(1)
    md = [p for p in qmd if re.search(rf'Q{qn}(\D|$)', p.stem)]
    txt = ''.join(p.read_text(encoding='utf-8') for p in md)
    has_tbl_md = '|' in txt and '---' in txt
    has_img_md = ('![' in txt) or ('图' in txt and ('如图' in txt or '下图' in txt or '图示' in txt))
    out.append({'unit': uid, 'roles': roles, 'md_table': has_tbl_md, 'md_img_hint': has_img_md})
cands = [o for o in out if (o['md_table'] or o['md_img_hint']) and any(fm == 'docx' for fm, _ in o['roles'])]
print(len(out), 'subjective candidates;', len(cands), 'with table/img hints and some docx')
for c in cands[:40]:
    print(c['unit'], c['md_table'], c['md_img_hint'], [x for x in c['roles'] if x[0]=='docx'])
