import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import re
prof, book, idx, fa, mi = load()
B = book['blocks']
kinds = {}
for b in B:
    if b['key']: kinds.setdefault(b['key'], set()).add(b['kind'])
print('unique keys in book', len(kinds))
nomd = []; parsefail = []; mism = []; noe1_subj = []; guard_hits = []; heur = 0
guard = (prof.get('sources') or {}).get('stem_module_guard') or []
print('stem_module_guard', guard)
for k, ks in sorted(kinds.items()):
    p = ps.find_md_path(BANK, k)
    if not p.is_file(): nomd.append(k); continue
    try:
        q = ps.parse_question_md(p.read_text(encoding='utf-8', errors='replace'), k)
    except ps.InputError as e:
        parsefail.append(k); continue
    bookchoice = ks == {'choice'}
    if (q['kind']=='choice') != bookchoice:
        mism.append((k, sorted(ks), q['kind'], q['kind_field_raw']))
    if q['kind']!='choice' and not q['e1_present']:
        noe1_subj.append((k, q['e1_header'], q['rubric'][:80].replace('\n',' ')))
    h = ps.stem_module_guard_hit(q['ask']+q['material'], guard)
    if h: guard_hits.append((k, h, sorted(ks)))
    heur += q['ask_heuristic']
print('no md', len(nomd), nomd)
print('parse fail', len(parsefail))
print('kind mismatch', len(mism))
for m in mism: print('  ', m)
print('subjective flagged no-E1', len(noe1_subj))
for m in noe1_subj: print('  ', m)
print('guard hits', len(guard_hits))
for m in guard_hits[:30]: print('  ', m)
print('ask_heuristic', heur)
