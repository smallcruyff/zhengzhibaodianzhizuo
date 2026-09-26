import sys
sys.dont_write_bytecode = True
from pathlib import Path
SK = '/home/user/zhengzhibaodianzhizuo/.claude/skills/beijing-gaokao-politics/scripts'
sys.path.insert(0, SK)
sys.path.insert(0, '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
import qpack
import exam_register as er
bank = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
T, _ = qpack.load_bank_tables(bank / 'scripts/bank.py')
tool_skip = qp_ok = qp_ok_on_tool_skip = total = 0
guided_ocr = 0
for ed in sorted((bank/'questions').iterdir()):
    if not ed.name.startswith('BJ-'): continue
    for p in sorted(ed.glob(f'{ed.name}-Q*.md')):
        total += 1
        t = p.read_text(encoding='utf-8')
        s = er.extract_stem_from_md(t)
        tool_ok = bool(s) and er.fingerprint_stem(s) is not None
        pre, secs = qpack.split_md(t)
        g = qpack.guide_fields(secs)
        h, how = qpack.adopted_stem_heading(secs, T, g)
        if 'OCR' in g.get('采用题面小节', ''): guided_ocr += 1
        if h: qp_ok += 1
        if not tool_ok:
            tool_skip += 1
            if h: qp_ok_on_tool_skip += 1
print(f'total={total} tool_skipped={tool_skip} qpack_has_adopted_stem={qp_ok} qpack_ok_where_tool_skipped={qp_ok_on_tool_skip} guide_names_OCR_section={guided_ocr}')
