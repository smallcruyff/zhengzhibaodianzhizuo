"""Verify explicit item-level admission; never infer curriculum relevance.

Candidates: JSON array (or {records: [...]}) with id, text, source.
Decisions: {records: [{old_id, statement, source, action, reason, ...}]}.
IDs are scoped to this frozen candidate file. New intake may use stable item keys
as IDs; book numbering alone must not be reused across different inputs.
"""
import argparse,hashlib,json,re
from pathlib import Path

def records(value):
    return value if isinstance(value,list) else value['records']

def verify(candidates, decisions):
    cs=records(candidates);ds=records(decisions)
    cmap={str(x['id']):x for x in cs};dmap={str(x['old_id']):x for x in ds}
    if len(cmap)!=len(cs) or len(dmap)!=len(ds):raise ValueError('重复条目身份')
    if cmap.keys()!=dmap.keys():raise ValueError('缺少或多出逐条准入裁决')
    retained=[];excluded=[]
    for key,c in cmap.items():
        d=dmap[key];text=re.sub(r'^\d+[、.．]','',c['text'],count=1)
        if d['statement']!=text or d['source']!=c['source']:raise ValueError('原文或来源不符: '+key)
        if d.get('action') not in ['retain','exclude']:raise ValueError('未明确准入: '+key)
        if not isinstance(d.get('reason'),str) or not d['reason'].strip():raise ValueError('缺少本册依据/排除理由: '+key)
        if d['action']=='retain':retained.append(c)
        else:excluded.append(c)
    return {'status':'pass','candidate_count':len(cs),'retained_count':len(retained),'excluded_count':len(excluded),'retained':retained,'excluded_ids':[c['id'] for c in excluded],'limit':'仅验证逐条裁决与执行集合，不证明教材归属判断正确；主代理须实际审阅。'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['candidates','decisions','report']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();cb=a.candidates.read_bytes();db=a.decisions.read_bytes()
    d=json.loads(db)
    if isinstance(d,dict) and d.get('input_sha256') and d['input_sha256']!=hashlib.sha256(cb).hexdigest():raise ValueError('候选SHA与裁决绑定不符')
    result=verify(json.loads(cb),d);result.update(candidates_sha256=hashlib.sha256(cb).hexdigest(),decisions_sha256=hashlib.sha256(db).hexdigest())
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:result[k] for k in ['status','candidate_count','retained_count','excluded_count']})
if __name__=='__main__':main()
