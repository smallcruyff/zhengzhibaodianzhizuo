import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
prof, book, idx, fa, mi = load()
guard = prof['sources']['stem_module_guard']
for k in ['BJ-2023-FT-ERMO-Q16','BJ-2024-DC-YIMO-Q18','BJ-2024-HD-ERMO-Q18','BJ-2024-HD-QIZHONG-Q21','BJ-2024-SY-ERMO-Q18','BJ-2024-SY-ERMO-Q19','BJ-2025-SJS-YIMO-Q17','BJ-2025-XC-ERMO-Q17']:
    q = mdq(k)
    ina = ps.stem_module_guard_hit(q['ask'], guard); inm = ps.stem_module_guard_hit(q['material'], guard)
    print(k, 'in_ask=', ina, 'in_material=', inm, '| ask:', q['ask'][:90].replace('\n',' '))
print('method_desc styles:', ps.method_desc_style_set(prof), 'intros:', len(mi))
mh = [h['text'] for h in book['heads'] if h['level']=='method']
print('method heads', len(mh), 'dup texts', [t for t,c in Counter(mh).items() if c>1][:5])
