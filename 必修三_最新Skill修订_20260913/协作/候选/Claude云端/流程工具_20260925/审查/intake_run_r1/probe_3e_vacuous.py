"""对抗探针：run_tests 3e（“必修三当前稿里已能用 block_index 查到部分应收题”）是否真能抓到查找失效。
把 BookIndexCache.has_key 打补丁成永远查不到（模拟 block_index 查找整体失效），按 3e 同一判据重算。
另：给 bixiu3 索引注入一条只在题肢单练附录里出现的 BJ-2026-CY-QIZHONG-Q9 条目，看第8步是否因此判 DONE。"""
import sys, copy
sys.dont_write_bytecode = True
from pathlib import Path
R='/home/user/zhengzhibaodianzhizuo'
C=R+'/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
sys.path.insert(0, C)
import intake_run as ir
EX = ['BJ-2023-HD-QIZHONG','BJ-2024-HD-QIZHONG','BJ-2024-CY-QIZHONG','BJ-2026-CY-QIZHONG','BJ-2026-HD-QIZHONG']
prof = ir.load_book_profile('bixiu3', C+'/profiles_cloud/bixiu3.json')
docx, _ = ir.current_docx_for_book(prof)
attr, _ = ir.load_attribution(ir.DEFAULT_ATTRIBUTION_CSV)
class Broken(ir.BookIndexCache):
    def has_key(self, *a, **k):
        return False, None
b = Broken()
s8 = [ir.check_step8(e, 'bixiu3', 'B3', ir.attribution_rows_for(attr, e), b, prof, docx, None, {}) for e in EX]
pred = any(s['status'] == 'DONE' or (s['status'] == 'TODO' and s['evidence'].get('found')) for s in s8)
print('查找全部失效时各卷第8步：', [(s['status'], len(s['evidence'].get('found') or [])) for s in s8])
print('3e 判据仍然成立（测试照样 PASS）：', pred)
# 题肢条目冒充整题
cache = ir.BookIndexCache()
idx, _ = cache.get('bixiu3', prof, docx)
rows = ir.attribution_rows_for(attr, 'BJ-2026-CY-QIZHONG')
print('注入前第8步：', ir.check_step8('BJ-2026-CY-QIZHONG', 'bixiu3', 'B3', rows, cache, prof, docx, None, {})['status'])
fake = copy.deepcopy(idx['drill_items'][0]); fake.update({'id': 'D9999', 'key': 'BJ-2026-CY-QIZHONG-Q9', 'keys_all': ['BJ-2026-CY-QIZHONG-Q9'], 'subq': None, 'src': '2026朝阳期中9'})
idx['drill_items'].append(fake)
s = ir.check_step8('BJ-2026-CY-QIZHONG', 'bixiu3', 'B3', rows, cache, prof, docx, None, {})
print('只多一条题肢单练条目（无例题题块）后第8步：', s['status'], s['reason'])
