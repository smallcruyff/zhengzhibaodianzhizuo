import sys
sys.dont_write_bytecode = True
import json, zipfile
from lxml import etree
from common import *
res = {}
for name, src in (('hl_only', WORK / 'src_hyperlink_only.docx'), ('vml_tbl', WORK / 'src_vml_in_table.docx')):
    u = unit([{'role': 'source', 'text': '【题目】审查探针材料一句。'},
              {'role': 'table', 'from': {'docx': str(src), 'table_index': 1}}])
    rc, so, se, out, rep = apply(u, name)
    res[name] = {'rc': rc, 'stdout': so.strip()[-300:], 'stderr': se.strip()[-600:], 'out_exists': out.exists(),
                 'reason': rep.get('reason'), 'verify': rep.get('verify', {}).get('missing_rel')}
    # also check mode
    parent = fresh(name + '_chk.docx'); up = write_unit(u, name + '_chk.json')
    rc2, so2, se2 = run(['check', '--docx', parent, '--insert', up, '--profile', PROF])
    res[name]['check_rc'] = rc2
print(json.dumps(res, ensure_ascii=False, indent=1))
