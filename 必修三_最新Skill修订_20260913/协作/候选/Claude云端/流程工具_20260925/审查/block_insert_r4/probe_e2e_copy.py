"""R4 端到端：在第52批副本上把某题块原文复制成一道新题（样板=该块自己，最有利情形），source 段走默认路径
（不给 style/like/kind），教学/细则段照金标做法给 style；--renumber --health。逐段比 source 段可见格式。"""
from common import *
sys.path.insert(0, str(C))
import run_tests_block_insert as rt
target, label = sys.argv[1], sys.argv[2]
prof = bi.load_profile(str(PROF))
parent = WORK / f'{label}_parent.docx'; shutil.copyfile(BOOK, parent)
d0 = dl.open_docx(parent); items = d0.items
b = [x for x in bh.walk(items, bh.Prof(prof)) if target in (x.get('title') or '')][0]
ti = b['title_i']; ei = max([ti] + list(b.get('paras') or []))
content = rt.gold_content_from_span(items, ti, ei, parent)
for c in content:
    if c.get('role') == 'source': c.pop('style', None)
new_title = items[ti]['text'] + '（复制）'
unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': sha(parent),
        'approved_by': 'claude:review-r4', 'approval_ref': 'R4 审查探针',
        'inserts': [{'id': 'C1', 'anchor': {'after_block': {'title_contains': items[ti]['text']}},
                     'template_block': {'title_contains': items[ti]['text']}, 'title': new_title,
                     'source_zone': 'restore', 'reason': 'R4 审查探针：同块复制', 'content': content}]}
up = WORK / f'{label}_insert.json'; up.write_text(json.dumps(unit, ensure_ascii=False, indent=1))
out = WORK / f'{label}_out.docx'; out.unlink(missing_ok=True)
for extra in list(WORK.glob(f'{label}_out_*')): extra.unlink()
rep = WORK / f'{label}_report.json'; rep.unlink(missing_ok=True)
rc, so, se = run_tool(['apply', '--docx', str(parent), '--insert', str(up), '--out', str(out),
                       '--profile', str(PROF), '--report', str(rep), '--health', '--renumber'])
r = json.loads(rep.read_text())
print('rc', rc, 'renumber', (r.get('renumber') or {}).get('ok'), 'new_FAIL', (r.get('health') or {}).get('new_FAIL_count'),
      'fallbacks', json.dumps(r.get('plan', [{}])[0].get('fallbacks'), ensure_ascii=False)[:300], se.strip()[:200])
d2 = dl.open_docx(out)
nb = [x for x in bh.walk(d2.items, bh.Prof(prof)) if x['title'] == new_title][0]
new_idx = sorted(list(nb.get('paras') or []))
orig_idx = sorted(list(b.get('paras') or []))
for oi, ni in zip(orig_idx, new_idx):
    if items[oi].get('tbl') or items[oi].get('img'): continue
    if bi.dl.para_text(d0.paras[oi]) != bi.dl.para_text(d2.paras[ni]): print('TEXT MISMATCH', oi, ni); continue
    a, c = rt._para_fmt_sig(d0.paras[oi]), rt._para_fmt_sig(d2.paras[ni])
    if a != c:
        print(f'{oi}->{ni} {items[oi]["style"]} {dl.para_text(d0.paras[oi])[:22]!r}\n   orig {a}\n   new  {c}')
