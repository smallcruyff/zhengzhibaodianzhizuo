#!/usr/bin/env python3
"""r4 审查探针：对题库在册卷的全部原件（exam_files.csv 中 原卷/教师版/混合载体，pdf/docx）
逐份统计：文字层长度、CJK 占比（M-J 新阈值）、切题块数、块里能做指纹的块数（--files 分母）、
全文最大题号（M-I 新信号）、_split_is_reliable 结果，与题库该卷逐题 MD 数对照。
只读；输出 JSON 到 argv[1]。"""
import sys
sys.dont_write_bytecode = True
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parents[1]
sys.path.insert(0, str(C))
import exam_register as er  # noqa: E402

BANK = er.REPO_ROOT / 'DeepSeek_政治题库资料库_20260918'
RAW = er.REPO_ROOT / '00_共同资料' / '原材料'

rows = er.read_csv_rows(BANK / 'indexes' / 'exam_files.csv')
out = []
for r in rows:
    if r.get('role') not in er.ROLE_PRIORITY or r.get('format', '').lower() not in ('pdf', 'docx'):
        continue
    eid = r['exam_id']
    if not eid.startswith('BJ-'):
        continue
    p = er.resolve_raw_path(r['rel_path'], RAW)
    if p is None:
        out.append({'exam_id': eid, 'rel': r['rel_path'], 'missing': True})
        continue
    bank_q = len(list((BANK / 'questions' / eid).glob(f'{eid}-Q*.md')))
    rec = {'exam_id': eid, 'rel': r['rel_path'], 'role': r['role'], 'bank_q': bank_q}
    try:
        text, engine = er.extract_file_text(p)
    except Exception as e:
        rec['open_error'] = str(e)
        out.append(rec)
        continue
    rec['engine'] = engine
    rec['chars'] = len(text.strip())
    rec['ratio_raw'] = round(er._readable_ratio(text), 3)
    rec['len_ok_only'] = len(text.strip()) >= er.MIN_TEXT_LEN
    rec['usable_new'] = er._text_usable(text)
    nt = er._normalize_raw(text)
    rec['ratio_norm'] = round(er._readable_ratio(nt), 3)
    chunks, ok = er.split_questions_raw(nt)
    rec['split_ok'] = ok
    rec['chunks'] = len(chunks)
    rec['fp_chunks'] = sum(1 for _q, c in chunks if er.fingerprint_stem(c))
    nums = [int(m.group(1)) for m in er.QNUM_SPLIT_RX.finditer(nt)]
    rec['max_num'] = max(nums) if nums else None
    # 哪些行首“数字+点”超过了切出的块数（M-I 信号的来源）
    if nums and ok:
        big = [m for m in er.QNUM_SPLIT_RX.finditer(nt) if int(m.group(1)) > len(chunks) + er.SPLIT_MAX_MISSING_QNUM]
        rec['big_num_samples'] = [re.sub(r'\s+', ' ', nt[max(0, m.start() - 15):m.end() + 25]) for m in big[:4]]
    rec['reliable_new'] = er._split_is_reliable(chunks, ok, nt) if rec['usable_new'] else False
    out.append(rec)
    print(eid, rec.get('role'), 'chars', rec['chars'], 'ratio', rec['ratio_raw'], 'usable', rec['usable_new'],
          'split_ok', ok, 'chunks', rec['chunks'], 'fp', rec['fp_chunks'], 'max', rec['max_num'],
          'bank_q', bank_q, 'reliable', rec['reliable_new'], flush=True)

Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
