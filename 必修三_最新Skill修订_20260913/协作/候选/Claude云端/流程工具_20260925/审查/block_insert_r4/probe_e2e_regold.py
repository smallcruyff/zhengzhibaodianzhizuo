"""R4 端到端：删掉一个题块，用 block_insert CLI 按原文重插（source 段不给 style/like/kind，走默认路径；
教学/细则段照测试金标做法给 style），与原稿逐段比格式。argv: 目标标题 样板标题 锚点类型 锚点标题 标签"""
from common import *
sys.path.insert(0, str(C))
import run_tests_block_insert as rt
target, template, akind, atitle, label = sys.argv[1:6]
prof = bi.load_profile(str(PROF))
pristine = WORK / f'{label}_pristine.docx'; shutil.copyfile(BOOK, pristine)
before = WORK / f'{label}_before.docx'; shutil.copyfile(BOOK, before)
deleted = WORK / f'{label}_deleted.docx'; deleted.unlink(missing_ok=True)
rt.delete_block_copy(before, deleted, prof, [target])
d0 = dl.open_docx(pristine)
items = d0.items
blocks = bh.walk(items, bh.Prof(prof))
b = [x for x in blocks if target in (x.get('title') or '')][0]
ti = b['title_i']; ei = max([ti] + list(b.get('paras') or []))
content = rt.gold_content_from_span(items, ti, ei, pristine)
for c in content:
    if c.get('role') == 'source':
        c.pop('style', None)
unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': sha(deleted),
        'approved_by': 'claude:review-r4', 'approval_ref': 'R4 审查探针',
        'inserts': [{'id': 'G1', 'anchor': {akind: {'title_contains': atitle}},
                     'template_block': {'title_contains': template}, 'title': items[ti]['text'],
                     'source_zone': 'restore', 'reason': 'R4 审查探针：原稿原文重插', 'content': content}]}
up = WORK / f'{label}_insert.json'; up.write_text(json.dumps(unit, ensure_ascii=False, indent=1))
out = WORK / f'{label}_out.docx'; out.unlink(missing_ok=True)
rep = WORK / f'{label}_report.json'; rep.unlink(missing_ok=True)
rc, so, se = run_tool(['apply', '--docx', str(deleted), '--insert', str(up), '--out', str(out),
                       '--profile', str(PROF), '--report', str(rep), '--health'])
print('rc', rc, so.strip()[:200], se.strip()[:400])
r = json.loads(rep.read_text())
print('fallbacks', json.dumps(r.get('plan', [{}])[0].get('fallbacks'), ensure_ascii=False)[:600])
print('health new_FAIL', (r.get('health') or {}).get('new_FAIL_count'), [ (f['check'], f['rule']) for f in (r.get('health') or {}).get('new_FAIL', [])][:5])
if out.exists():
    d2 = dl.open_docx(out)
    nb = [x for x in bh.walk(d2.items, bh.Prof(prof)) if x['title'] == items[ti]['text']][0]
    new_idx = sorted([nb['title_i']] + list(nb.get('paras') or []))
    orig_idx = list(range(ti, ei + 1))
    print('text flow same:', [dl.para_text(d0.paras[i]) for i in orig_idx] == [dl.para_text(d2.paras[i]) for i in new_idx])
    for oi, ni in zip(orig_idx, new_idx):
        po, pn = d0.paras[oi], d2.paras[ni]
        if items[oi].get('tbl'): continue
        so_, sn_ = rt._para_fmt_sig(po), rt._para_fmt_sig(pn)
        flag = '' if so_ == sn_ else '  <<DIFF'
        ind_o = po.find(f'{W}pPr/{W}ind'); ind_n = pn.find(f'{W}pPr/{W}ind')
        print(f'{oi:>6} {pstyle_name(po)}->{pstyle_name(pn)} font {eff_font(po)}->{eff_font(pn)} '
              f'ind {dict(ind_o.attrib) if ind_o is not None else None}->{dict(ind_n.attrib) if ind_n is not None else None} '
              f'{dl.para_text(po)[:24]!r}{flag}')
