import sys
sys.dont_write_bytecode=True
import os, json, zipfile, glob
from common import *
sys.path.insert(0, str(C)); sys.path.insert(0, str(R / '.claude/skills/beijing-gaokao-politics/scripts'))
import block_insert as bi
res={}
u = unit([{'role':'source','text':'【题目】审查探针一句。'},
          {'role':'image','from':{'docx':str(R/'00_共同资料/原材料/2023模拟题/2023各区模拟题(1)/各区二模/√西城/西城-高三政治二模试卷-定(2).docx'),'rid':'rId14'}}],
         anchor={'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}}, template='例题 5　2026门头沟一模第17题')
up = write_unit(u, 'atomic_insert.json')
outdir = WORK/'atomic_out'; outdir.mkdir(exist_ok=True)
for f in outdir.iterdir(): f.unlink()
# 1) crash mid-zip-write
parent = fresh('atomic_parent.docx')
orig_writestr = zipfile.ZipFile.writestr
cnt = {'n': 0}
def bad_writestr(self, *a, **k):
    cnt['n'] += 1
    if cnt['n'] == 20: raise OSError('注入：磁盘写满')
    return orig_writestr(self, *a, **k)
zipfile.ZipFile.writestr = bad_writestr
rc = bi.main(['apply','--docx',str(parent),'--insert',str(up),'--out',str(outdir/'o1.docx'),'--profile',str(PROF),'--report',str(outdir/'r1.json')])
zipfile.ZipFile.writestr = orig_writestr
res['crash_mid_write'] = {'rc': rc, 'files_left': sorted(p.name for p in outdir.iterdir())}
# 2) verify raises
bi._source_cache.clear()
orig_open = bi.dl.open_docx
calls = {'n': 0}
def bad_open(p, *a, **k):
    calls['n'] += 1
    if calls['n'] == 2: raise RuntimeError('注入：写后重开失败')
    return orig_open(p, *a, **k)
bi.dl.open_docx = bad_open
rc = bi.main(['apply','--docx',str(parent),'--insert',str(up),'--out',str(outdir/'o2.docx'),'--profile',str(PROF),'--report',str(outdir/'r2.json')])
bi.dl.open_docx = orig_open
res['verify_raises'] = {'rc': rc, 'files_left': sorted(p.name for p in outdir.iterdir()), 'report_reason': json.load(open(outdir/'r2.json')).get('reason') if (outdir/'r2.json').exists() else None}
# 3) block_index raises → counts as problem (hard fail)
orig_bi = bi.bidx.build_index
def bad_bi(*a, **k): raise RuntimeError('注入：block_index 崩溃')
bi.bidx.build_index = bad_bi
rc = bi.main(['apply','--docx',str(parent),'--insert',str(up),'--out',str(outdir/'o3.docx'),'--profile',str(PROF)])
bi.bidx.build_index = orig_bi
res['block_index_raises'] = {'rc': rc, 'o3_exists': (outdir/'o3.docx').exists()}
print(json.dumps(res, ensure_ascii=False, indent=1))
