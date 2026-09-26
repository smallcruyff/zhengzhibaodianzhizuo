"""r2 探针：WEAK_ONLY 且原件有文字层的卷，看卷首窗口截到了什么、原件前 1500 字里有没有日期/学年。只读。"""
import sys, json, re
sys.dont_write_bytecode = True
from pathlib import Path
HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
import exam_register as er
rep = json.load(open(sys.argv[1]))
for it in rep['items']:
    if it.get('cohort_status') != 'WEAK_ONLY':
        continue
    for rf in it.get('raw_files', []):
        if not rf['has_text_layer']:
            continue
        text, eng = er.extract_file_text(Path(rf['path']), max_pages=er.HEADER_RAW_MAX_PAGES, max_chars=er.HEADER_RAW_MAX_CHARS)
        norm = er._normalize_raw(text)
        hw = er.header_window_text(text, cut_at_qnum=True)
        m = er.QNUM_SPLIT_RX.search(norm)
        full_sig = [(mm.group(0)) for mm in er.DATE_RX.finditer(norm[:3000])] + [mm.group(0) for mm in er.SCHOOL_YEAR_RX.finditer(norm[:3000])]
        print('==', it['exam_id'], rf['role'], eng, 'cut_at=', m.start() if m else None, 'first_qnum_line=', repr(norm[m.start():m.start()+30]) if m else None)
        print('   header_window=', repr(hw[:300]))
        print('   signals_in_first_3000=', full_sig[:6])
