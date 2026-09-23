from pathlib import Path
from copy import deepcopy
import json,zipfile,hashlib,re
from lxml import etree as E
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');S=R/'必修三政治与法治宝典_R31续修_第43批_候选.docx'
assert hashlib.sha256(S.read_bytes()).hexdigest()=='bc7b8392da1fddff0258d2dc4bdbdae5ae099cbc1e8209e4f3ee3657e23e9302'
z=zipfile.ZipFile(S);tr=E.fromstring(z.read('word/document.xml'));W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';ns={'w':W};b=tr.find('w:body',ns);orig=list(b)
C=json.loads(Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/检查资料/agent_1_110/batch42_review/candidate_body.json').read_text())
changes={
260:'【细则说明】 从党的领导这一战略性条件展开，要说明党怎样推动所选战略实施，进而服务社会主义现代化国家建设。如分析创新驱动发展，可联系党统筹创新资源、推动关键技术突破和成果转化的作用。',
1072:'【细则说明】 从基层党组织的战斗堡垒作用展开，应说明其怎样组织群众、协调关系、落实乡村振兴任务，进而服务社会主义现代化国家建设。',
1283:'【细则说明】 以全过程人民民主说明制度优势，要结合所选战略，解释人民参与怎样改善决策、凝聚力量、促进战略落实，进而服务社会主义现代化国家建设。',
2041:'【细则说明】 以人民代表大会制度说明制度优势，应把人大的有关职权与所选战略的具体任务联系起来，说明国家权力运行怎样保障战略实施，进而服务社会主义现代化国家建设。',
2294:'【细则说明】 以中国共产党领导的多党合作和政治协商制度说明制度优势，要把协商建言和监督与科教兴国的需要联系起来，说明其怎样完善政策、凝聚共识、推动战略落实，进而服务社会主义现代化国家建设。',
2428:'【细则说明】 从基层群众自治制度展开，应说明村民参与、共同管理和监督怎样服务乡村振兴，进而服务社会主义现代化国家建设。',
279:'【细则说明】 把坚持人民立场与群众观点、加强自身建设与自我革命、理论创新与实践和认识的关系相联系，结合对应材料说明党怎样永葆青春活力。政治知识与哲学原理应同材料、论述相匹配。',
980:'【细则说明】 把党的指导思想、科学理论与实践和认识的关系相联系，说明党坚持解放思想和实事求是相统一，不断推进理论创新，为新的实践提供科学指导，从而保持青春活力。',
1016:'【细则说明】 材料二可联系党员先锋模范作用和正确价值观的指导作用，说明党员怎样在实践中保持先进性、带动群众，使党永葆青春活力。',
1084:'【细则说明】 材料二可联系基层党组织战斗堡垒作用和正确价值观的指导作用，说明基层党组织怎样组织党员群众、落实党的要求，使党永葆青春活力。',
1169:'【细则说明】 把加强党的建设、自我革命与内因或辩证否定相联系，结合清除政治灰尘、防范风险的追问，说明党怎样解决自身问题、保持青春活力。',
1720:'【细则说明】 把以人民为中心、全心全意为人民服务、群众路线和人民主体地位，与群众观点相联系，结合发展和减贫成就，说明党怎样依靠人民、为了人民而保持青春活力。',
4679:'495、推进智慧交通建设，公交公司及时推送交通信息',
5939:'495、推进智慧交通建设，公交公司及时推送交通信息'
}
removes=[261,1073,1284,2042,2295,2429]
intro=['2024东城一模第4题（第494—497肢依次对应原题①—④）','让市民出行更美好、更舒心。回答4、5题。','4．问卷调查统计情况','✧ 公交站台存在障碍物、过街斑马线不够宽。','✧ 上学时段公交车拥挤、容易堵车不准时。','✧ 接送学生车辆乱停乱放。','某校学生围绕学校周边交通状况进行了调研（调研结果见上）。针对上述情况，下列建议最适合的是']
log=[]
def text(p):return ''.join(p.xpath('.//w:t/text()',namespaces=ns))
def settext(p,new):
 runs=p.findall('w:r',ns);non=[r for r in runs if text(r).strip()];lp=deepcopy(non[0].find('w:rPr',ns)) if non else None;tp=deepcopy(non[-1].find('w:rPr',ns)) if non else None
 for r in runs:p.remove(r)
 lab=re.match('^(【[^】]+】)\\s*',new);parts=[(lab.group(1),lp),(' '+new[lab.end():],tp)] if lab else [(new,tp)]
 for tx,pr in parts:
  r=E.SubElement(p,'{'+W+'}r')
  if pr is not None:r.append(deepcopy(pr))
  t=E.SubElement(r,'{'+W+'}t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=tx
for i,new in changes.items():
 p=orig[i];old=text(p);assert old==C[i]['text'],i
 settext(p,new);log.append({'op':'replace','parent_body_i':i,'before':old,'after':new,'prior_anchor':C[i-1]['text']})
for i in removes:
 p=orig[i];assert text(p)==C[i]['text'] and not p.xpath('.//w:drawing|.//w:bookmarkStart|.//w:fldChar',namespaces=ns)
 log.append({'op':'remove_student_rubric_tiers','parent_body_i':i,'before':text(p),'after':None});b.remove(p)
# Use an existing neutral appendix material paragraph, not a claim (whose color encodes judgement).
for i in [4678,5938]:
 anchor=orig[i];assert text(anchor)==C[i]['text']
 for tx in intro:
  p=deepcopy(orig[6356]);settext(p,tx)
  for x in p.xpath('.//w:bookmarkStart|.//w:bookmarkEnd',namespaces=ns):x.getparent().remove(x)
  anchor.addprevious(p)
 log.append({'op':'insert_before','parent_body_i':i,'anchor':C[i]['text'],'paragraphs':intro,'source':'/Users/wanglifei/Desktop/2024模拟题/2024东城一模/试卷/试卷.pdf#page=2'})
O=R/'必修三政治与法治宝典_R31续修_第43批_候选2.docx'
with zipfile.ZipFile(O,'w',zipfile.ZIP_DEFLATED) as oz:
 for info in z.infolist():oz.writestr(info,E.tostring(tr,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
out={'parent':str(S),'parent_sha256':hashlib.sha256(S.read_bytes()).hexdigest(),'output':str(O),'output_sha256':hashlib.sha256(O.read_bytes()).hexdigest(),'changes':log,'complete_rubric_preserved':'第42批原件与本记录保留完整等级；gk23q20_rubric-1/2与gk21E1p6/7亲自实看','status':'saved_candidate_not_rendered'}
(R/'主代理修订/第二组修订记录.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(len(log),out['output_sha256'])
