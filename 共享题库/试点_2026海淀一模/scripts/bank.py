"""Read-only retrieval. get reads one derived packet; list reads only the small index."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def checked_packet(qid):
 if qid not in {x['id'] for x in json.loads((ROOT/'data/index.json').read_text())}: raise ValueError('题键不存在')
 p=ROOT/'packets'/f'{qid}.md';m=json.loads((ROOT/'data/integrity.json').read_text())
 if sha(p)!=m[str(p.relative_to(ROOT))]:raise ValueError('取用包内容已变更，须重新核验后生成')
 return p.read_text()
def main():
 a=argparse.ArgumentParser(description=__doc__);s=a.add_subparsers(dest='cmd',required=True)
 l=s.add_parser('list');l.add_argument('--module');l.add_argument('--kind',choices=['choice','subjective']);l.add_argument('--query')
 g=s.add_parser('get');g.add_argument('id')
 s.add_parser('verify');s.add_parser('stats')
 x=a.parse_args()
 if x.cmd=='get':print(checked_packet(x.id));return
 if x.cmd=='list':
  records=json.loads((ROOT/'data/index.json').read_text())
  for q in records:
   if x.module and x.module not in q['modules']:continue
   if x.kind and x.kind!=q['kind']:continue
   if x.query and x.query not in json.dumps(q,ensure_ascii=False):continue
   print(json.dumps(q,ensure_ascii=False,separators=(',',':')))
 elif x.cmd=='verify':
  errors=[]
  for rel,h in json.loads((ROOT/'data/integrity.json').read_text()).items():
   p=ROOT/rel
   if not p.exists() or sha(p)!=h:errors.append({'artifact':rel,'error':'missing_or_changed'})
  for d in json.loads((ROOT/'data/sources.json').read_text())['sources']:
   p=Path(d['path'])
   if not p.exists() or sha(p)!=d['sha256']:errors.append({'source':d['path'],'error':'missing_or_changed_requires_review'})
  print(json.dumps({'ok':not errors,'errors':errors},ensure_ascii=False));sys.exit(bool(errors))
 else:
  index=json.loads((ROOT/'data/index.json').read_text());print(json.dumps({'main_questions':21,'retrieval_units':len(index),'choice':sum(q['kind']=='choice' for q in index),'subjective':sum(q['kind']=='subjective' for q in index),'question_points_total':100},ensure_ascii=False))
if __name__=='__main__': main()
