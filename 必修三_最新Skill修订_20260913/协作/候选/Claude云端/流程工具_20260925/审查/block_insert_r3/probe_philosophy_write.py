"""验收 4 可行性：哲学（草案配置）上按真实栏目写入 1 道带图题（内容取自 例题 1　2026年东城二模第16题 本身，
图按原书第几个图形定位），看工具能否真正写出——对照 T4b 只插 1 段 source、被栏目缺失拦下却记 PASS。"""
from common import *
import zipfile
from lxml import etree
PH = R/'其他书工作头/哲学/哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx'
PP = C/'profiles_cloud/philosophy.draft.json'
prof = bi.load_profile(str(PP))
src_copy = WORK/'ph_src.docx'; shutil.copyfile(PH, src_copy)
d = dl.open_docx(src_copy)
_,_,blocks,_ = ap.zones_of(d, prof)
b = [x for x in blocks if '例题 1　2026年东城二模第16题' in x['title']][0]
with zipfile.ZipFile(src_copy) as z: root = etree.fromstring(z.read('word/document.xml'))
alld = bi._drawing_elements(root)
paras_src = dl.para_elements(root.find(W+'body'))
content = []
for i in b['paras']:
    it = d.items[i]
    if it.get('img'):
        dr = next(x for x in paras_src[i].iter() if x.tag in (bi.WP_NS+'inline', bi.WP_NS+'anchor'))
        content.append({'role':'image','from':{'docx':str(src_copy),'index':alld.index(dr)+1}}); continue
    zone = it.get('zone'); role = {'source':'source','teaching':'teaching','rubric':'rubric'}[zone]
    content.append({'role':role,'style':it['style'],'text':it['text']})
sha = dl.sha256_file(PH)
unit = {'schema':'baodian_insert_v1','book':'philosophy','parent_docx_sha256':sha,'approved_by':'claude:review-r3','approval_ref':'审查探针：验收4可行性',
  'inserts':[{'id':'PH1','anchor':{'after_block':{'title_contains':b['title']}},'template_block':{'title_contains':b['title']},
   'title':'例题 2　2026年东城二模第16题（复制）','source_zone':'restore','reason':'审查探针：原书同题逐字复制，验证草案配置能否写入带图题','content':content}]}
docx = WORK/'ph_parent.docx'; shutil.copyfile(PH, docx)
up = wjson('ph_insert.json', unit)
out = WORK/'ph_out.docx'; out.unlink(missing_ok=True)
rep = WORK/'ph_report.json'; rep.unlink(missing_ok=True)
rc, so, se = run(['apply','--docx',docx,'--insert',up,'--out',out,'--profile',PP,'--report',rep,'--health'])
r = json.loads(rep.read_text()) if rep.exists() else {}
print('rc=',rc,'out_exists=',out.exists()); print('stdout', so.strip()[:300]); print('stderr', se.strip()[-600:])
print('block_index_check', json.dumps((r.get('verify') or {}).get('block_index_check'), ensure_ascii=False))
print('health', json.dumps({k: v for k, v in (r.get('health') or {}).items() if k != 'new_FAIL'}, ensure_ascii=False))
for f in (r.get('health') or {}).get('new_FAIL', [])[:10]: print('  NEW FAIL', f.get('check'), f.get('rule'), (f.get('excerpt') or '')[:60])
print('fallbacks', json.dumps([p['fallbacks'] for p in r.get('plan', [])], ensure_ascii=False)[:600])
