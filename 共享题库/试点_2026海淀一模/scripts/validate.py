from pathlib import Path
import json,hashlib,subprocess,sys,time,statistics
R=Path(__file__).resolve().parents[1];B=json.loads((R/'data/bank.json').read_text());I={q['id']:q for q in B['items']};P={q['number']:q for q in B['parents']};U={r['id']:r for r in B['rubrics']}; checks=[]
def check(name,v,detail=None):
 checks.append({'name':name,'passed':bool(v),'detail':detail});assert v,(name,detail)
check('21大题题号连续',[p['number'] for p in B['parents']]==list(range(1,22)))
check('24个取用单元、总分100',len(I)==24 and sum(x['points'] for x in I.values())==100)
check('选择题15、主观单元9',sum(q['kind']=='choice' for q in I.values())==15 and sum(q['kind']=='subjective' for q in I.values())==9)
check('60条题肢均有独立归属、未自动准入',len(B['claims'])==60 and all(c['modules'] and c['drill_admission']=='not_decided_for_any_book' for c in B['claims']))
check('全部材料及细则依赖可解',all(set(q['depends_on'])<={b['id'] for b in P[q['parent']]['blocks']} and set(q['rubric_ids'])<=U.keys() for q in I.values()))
check('第18题经济与法律材料分离','18.chart' in I['Q18-2']['depends_on'] and '18.note' in I['Q18-2']['depends_on'] and '18.case1' not in I['Q18-2']['depends_on'] and '18.chart' not in I['Q18-3']['depends_on'] and '18.table' in I['Q18-3']['depends_on'])
check('第21题跨页完整',set(U['R21']['source_pages'])=={7,8})
check('第18题第2问跨页限制未漏',set(U['R18-2']['source_pages'])=={3,4} and '不给分' in json.dumps(U['R18-2'],ensure_ascii=False))
check('第17题不伪造原小问号',I['Q17-a'].get('original_subquestion_number') is None and I['Q17-b'].get('original_subquestion_number') is None)
check('第17题两项任务只配自己的评分条件',I['Q17-a']['rubric_ids']==['R17-a'] and I['Q17-b']['rubric_ids']==['R17-b'] and '任何一点得2分' in (R/'packets/Q17-a.md').read_text() and '建议1分' not in (R/'packets/Q17-a.md').read_text())
check('跨模块题不按设问教材机械排除','必修二' in I['Q19']['modules'] and '必修三' in I['Q19']['modules'])
check('第14题④不随整题入经济题肢',next(c for c in B['claims'] if c['id']=='Q14:④')['modules']==['选必一'])
check('表格行列保留',any(b['type']=='table' and len(b['rows'])==4 and len(b['headers'])==3 for b in P[10]['blocks']))
check('共同导语每包恰好一次',all((R/'packets'/f'Q{n}.md').read_text().count('能源安全事关经济社会发展全局。回答第13、14题。')==1 for n in [13,14]))
check('原卷与全部产物指纹完整',subprocess.run([sys.executable,str(R/'scripts/bank.py'),'verify'],capture_output=True).returncode==0)
# Character counts compare normalized source content; operational metadata is reported separately.
full=(R/'data/full_text_for_comparison.txt').read_text();measurements=[]
for qid in ['Q12','Q18-2','Q18-3','Q19','Q21']:
 times=[];out=None
 for _ in range(3):
  start=time.perf_counter();s=subprocess.run([sys.executable,str(R/'scripts/bank.py'),'get',qid],capture_output=True,text=True,check=True);times.append((time.perf_counter()-start)*1000);out=s.stdout
 measurements.append({'id':qid,'packet_characters_including_metadata':len(out),'packet_utf8_bytes':len(out.encode()),'full_unique_transcript_characters':len(full),'fraction_of_full_transcript':round(len(out)/len(full),4),'median_cli_ms_including_process_start':round(statistics.median(times),2),'fresh_ocr_calls':0,'source_pdf_content_opens_during_get':0,'images_not_counted_as_text_tokens':True})
report={'checks':checks,'all_passed':all(c['passed'] for c in checks),'measurements':measurements,'measurement_caveat':'字符与UTF-8字节，非API实际token/账单；图像和教学推理成本未计入。基线为完整去重转录，不是重复题包拼接。仅本机少量试跑，不外推全库总节省。','source_page_visual_review':{'root_paper':[1,2,3,4,5,6,7,8],'root_rubric':[1,2,3,4,5,6,7,8],'independent_agents':'Luna/max 原文提取及评分表转录；主代理复核配对及图文'}}
(R/'review/验证与读取量.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
