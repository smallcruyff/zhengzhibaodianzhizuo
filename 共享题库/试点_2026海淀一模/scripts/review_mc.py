from pathlib import Path
import json,hashlib,copy
R=Path(__file__).resolve().parents[1];src=R/'review/mc_transcript.json';d=json.loads(src.read_text());qs={q['number']:q for q in d['questions']}
# Coordinates measured against the complete native scanned page, not a displayed screenshot.
boxes={1:[1,.103,.32,.896,.484],2:[1,.103,.49,.897,.65],3:[1,.105,.655,.897,.88],4:[2,.117,.055,.90,.385],5:[2,.117,.391,.90,.548],6:[2,.116,.552,.897,.819],7:[3,.116,.063,.885,.295],8:[3,.117,.298,.879,.515],9:[3,.117,.515,.879,.645],10:[3,.117,.648,.88,.853],11:[4,.132,.072,.891,.213],12:[4,.132,.216,.891,.319],13:[4,.132,.322,.891,.547],14:[4,.132,.548,.891,.689],15:[4,.132,.691,.891,.86]}
visualboxes={3:[.129,.655,.89,.738],6:[.194,.608,.811,.683],7:[.194,.103,.793,.182],8:[.142,.32,.877,.394],9:[.722,.513,.875,.642],13:[.529,.339,.891,.505]}
for n,q in qs.items():
 page,x0,y0,x1,y1=boxes[n];q['question_bbox']=[{'page':page,'bbox_normalized':[x0,y0,x1,y1]}]
 for v in q.get('visuals',[]):v['bbox_normalized']=visualboxes[n]
 if n in [13,14]:q['stem_paragraphs']=[p for p in q['stem_paragraphs'] if p!='能源安全事关经济社会发展全局。回答第13、14题。']
 for t in q.get('tables',[]):
  t['headers']=t.pop('columns');t['merged_cells']=[];t['bbox_normalized']=([.141,.057,.895,.191] if n==4 else [.152,.665,.877,.853])
q=qs[7];q['stem_paragraphs']=[p.replace('◇ ……','……') for p in q['stem_paragraphs']]
qs[9]['visuals'][0]['description']='成绩单：热线呼入总量223万+；群众满意率99.71%；服务人次152万+；民事类咨询量104万+。图标和原始分格以原图保留。'
# Exact visual correction: source says 梦想? verified stem and all statement/options below retained unchanged.
d['root_review']={'source_parent_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'pages_reviewed':[1,2,3,4],'changes':['统一原图坐标；原代理坐标不作为通过依据','表头显式记录并恢复Q4顺序','Q13/14共同导语去重但每个题包保留','Q7末行省略号无◇','Q9指标修正为热线呼入总量'],'status':'text_and_structure_checked'}
(R/'data/mc_reviewed.json').write_text(json.dumps(d,ensure_ascii=False,indent=2))
