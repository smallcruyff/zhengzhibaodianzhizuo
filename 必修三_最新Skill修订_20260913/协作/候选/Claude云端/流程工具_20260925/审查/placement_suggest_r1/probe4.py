import sys; sys.dont_write_bytecode = True  # 不留 __pycache__
from common import *
import re
prof, book, idx, fa, mi = load()
B = book['blocks']
multi = [(b['id'], b['key'], b['keys_all'], b['title']) for b in B if len(b['keys_all'])>1]
print('blocks with >1 keys', len(multi))
for m in multi[:20]: print('  ', m)
nokey = [b for b in B if not b['key']]
print('blocks without key', len(nokey), Counter(b['kind'] for b in nokey))
for b in nokey[:15]: print('   ', b['id'], b['kind'], b['title'], '|', b['key_note'])
# keys appearing in keys_all but not as primary key of that block
secondary = {}
for b in B:
    for k in b['keys_all'][1:]:
        base = re.sub(r'\(.*\)$','',k)
        secondary.setdefault(base, []).append(b['id'])
print('secondary keys', len(secondary))
