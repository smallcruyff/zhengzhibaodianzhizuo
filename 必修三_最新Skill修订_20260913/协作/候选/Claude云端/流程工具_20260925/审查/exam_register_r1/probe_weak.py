import sys, json, re
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
import exam_register as er
from pathlib import Path
R = Path('/home/user/zhengzhibaodianzhizuo')
bank = R/'DeepSeek_政治题库资料库_20260918'; raw = R/'00_共同资料/原材料'
rep = json.load(open(R/'必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925/构建/exam_register/test_audit_full.json', encoding='utf-8'))
ef = er.read_csv_rows(bank/'indexes/exam_files.csv')
for it in rep['items']:
    if it.get('cohort_status') != 'WEAK_ONLY': continue
    eid = it['exam_id']
    rows = [r for r in ef if r['exam_id']==eid]
    print('=====', eid, 'raw_files=', [(Path(x['path']).name, x['has_text_layer'], x['chars']) for x in it['raw_files']])
    print('   exam_files rows:', [(r['role'], r['format'], r['rel_path'][-50:], (raw/r['rel_path']).is_file()) for r in rows][:8])
    for x in it['raw_files']:
        t, eng = er.extract_file_text(Path(x['path']))
        print('   RAWTEXT[:200]:', re.sub(r'\s+',' ',t[:200]))
    rd = bank/'questions'/eid/'README.md'
    if rd.is_file():
        t = rd.read_text(encoding='utf-8')
        m = re.search(r'学年|20\d\d\s*[.年]\s*\d{1,2}', t)
        print('   README[:160]:', re.sub(r'\s+',' ',t[:160]), '| first year-ish hit at', m.start() if m else None, (re.sub(r'\s+',' ',t[max(0,m.start()-40):m.start()+40]) if m else ''))
