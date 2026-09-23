from pathlib import Path
from copy import deepcopy
import json,zipfile,hashlib,re
from lxml import etree as E
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');S=R/'必修三政治与法治宝典_R31续修_第43批_候选2.docx';parent=hashlib.sha256(S.read_bytes()).hexdigest();assert parent=='d36879ea281af117560fd3302a3a25871fdd80a233234bb8c5ad6beecfd7e2d6'
z=zipfile.ZipFile(S);tr=E.fromstring(z.read('word/document.xml'));W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';ns={'w':W};b=tr.find('w:body',ns)
C=json.loads(Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/检查资料/agent_1_110/batch42_review/candidate_body.json').read_text())
changes={
716:'【细则说明】 中国共产党以全面从严治党塑造政治势能，通过制度建构将潜在力量转化为现实动能。应说明党怎样在尊重规律的基础上发挥主动性，把时代条件转化为推进事业的力量，回应“把握势的智慧”。',
1212:'【细则说明】 中国共产党以全面从严治党塑造政治势能，通过制度建构将潜在力量转化为现实动能。联系党的自我革命，说明加强自身建设怎样增强应对风险和组织发展的能力，回应“把握势的智慧”。',
1424:'【细则说明】 全过程民主，实现维护好最广大人民根本利益，是“治理重民生”的可采表达。结合基层立法联系点让居民意见进入国家立法，说明人民意愿怎样转化为治理实践；与科学民主立法、公正司法同属治理方面，不重复累加。',
1830:'【细则说明】 人民性可以联系群众观、党的宗旨或初心，说明“民生为大”的价值取向。联系收入、医疗、教育和体育服务，再说明优化公共服务、发展成果由人民共享、满足人民美好生活需要，体现其在实践中的要求。',
2672:'【细则说明】 科学民主立法，实现维护好最广大人民根本利益，是“治理重民生”的可采表达。联系全国人大加强民生立法、基层立法联系点吸纳意见，说明民生诉求怎样转成法律保障；与全过程民主、公正司法同属治理方面，不重复累加。',
3529:'【细则说明】 公正司法，保障人民权益、维护公平正义，是“治理重民生”的可采表达。联系检察机关办理就业、食品药品安全等民生案件，说明司法履职怎样保障民生；与立法、民主参与同属治理方面，不重复累加。',
163:'【细则说明】 论述要把所选中国式现代化特色、有利条件与民族复兴连起来。例如选择共同富裕，应说明党的领导和制度优势怎样促进发展、改善民生、推动发展成果共享。',
777:'【细则说明】 围绕所选中国式现代化特色，说明党的领导怎样发挥作用。例如分析共同富裕，应说明党怎样统一方向、统筹政策、凝聚力量，推动发展成果惠及全体人民，服务民族复兴。',
1261:'【细则说明】 完善党内法规并与宪法法律衔接，把管党治党与国家治理贯通起来。围绕依法治国与依规治党的统一展开，说明二者怎样相互促进、共同发挥作用。',
2407:'【细则说明】 选择民族区域自治制度，应说明国家统一领导与依法自治怎样共同发挥作用，并结合民族地区发展成就，论证制度优势怎样转化为治理和发展的实际成效。',
2477:'【细则说明】 从基层群众自治展开，可写村民共同商议村落保护、参与文化设施管理、完善村规民约，说明自治怎样使乡村文化建设回应村民需要、获得持续参与。',
3011:'【细则说明】 从国家职能展开，可结合文化和旅游部门联合发文，写政府提供政策支持、完善公共文化服务、协调资源，说明这些做法怎样解决村落保护和文化生活中的问题。'
}
# Root reviewed these exact passages. Remove only named generic penalty/tier tails, retaining all positive scoring statements.
cut={123:'；只写概括句',186:'只写概括句',357:'只写党的领导',454:'只抄材料',953:'；只完成其中一步',1432:'；不结合材料',1917:'只写“以人民为中心”',2116:'只写制度名称',2181:'只写制度名称',3769:'；不结合材料',1820:'全篇达到7—8分',3326:'建议笼统',1674:'只列热线和平台',2636:'全篇任取三个有效角度',3132:'写创新及产业融合后'}
for i,marker in cut.items():
 old=C[i]['text'];assert marker in old,(i,marker);v=old.split(marker,1)[0].rstrip('；， ')
 if not v.endswith('。'):v+='。'
 changes[i]=v
# Specific false-score safeguards are retained; only general student-facing penalties are removed.
for i,segments in {
107:['；只写“党人法有机统一”不给分'],
2700:['；不结合材料只得1分'],
1387:['；写组织名称或同一性质的重复主体不得分','建议不合理，所配理由不给分或少给分。'],
1799:['建议若不合理，所配理由不给分或少给分。'],
3951:['若建议不合理，理由不给分或少给分。'],
2912:['只写“政府加强宏观调控，有利于人才培训”，分析链条不充分，不能取得这一角度的完整3分。','主体单一要酌情扣分；'],
3173:['；只列监管做法而不说明效果，拿不到材料分']
}.items():
 v=C[i]['text']
 for seg in segments:assert seg in v,(i,seg);v=v.replace(seg,'')
 changes[i]=v
# Keep only the currently titled selectable angle; whole-question financial/economic conditions stay in background.
for i,marker in [(487,'阐述须回应'),(1810,'阐述须回应')]:
 v=C[i]['text'].split(marker)[0];changes[i]=v
# Remove continuation paragraphs that contain only whole-question conditions in these two entries.
removes=[488,1811]
for i in removes:assert C[i]['text'].startswith('整题还必须解释政府金融政策'),i
log=[]
def pos(i):return i-sum(k<i for k in [261,1073,1284,2042,2295,2429])+7*(i>=4678)+7*(i>=5938)
def txt(p):return ''.join(p.xpath('.//w:t/text()',namespaces=ns))
original=list(b)
for i,new in changes.items():
 p=original[pos(i)];old=txt(p);assert old==C[i]['text'],(i,old)
 runs=p.findall('w:r',ns);non=[r for r in runs if txt(r).strip()];lp=deepcopy(non[0].find('w:rPr',ns));tp=deepcopy(non[-1].find('w:rPr',ns));assert not p.xpath('.//w:drawing|.//w:fldChar',namespaces=ns)
 for r in runs:p.remove(r)
 lab=re.match('^(【[^】]+】)\\s*',new)
 for tx,pr in ([(lab.group(1),lp),(' '+new[lab.end():],tp)] if lab else [(new,tp)]):
  r=E.SubElement(p,'{'+W+'}r')
  if pr is not None:r.append(deepcopy(pr))
  t=E.SubElement(r,'{'+W+'}t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=tx
 log.append({'parent42_body_i':i,'before':old,'after':new,'purpose':'学生版简化；保留原评分事实，不将整体评价拆为固定分'})
for i in removes:
 p=original[pos(i)];assert txt(p)==C[i]['text'];log.append({'parent42_body_i':i,'before':txt(p),'after':None,'purpose':'整题其他模块条件留后台'});b.remove(p)
O=R/'必修三政治与法治宝典_R31续修_第43批_候选3.docx'
with zipfile.ZipFile(O,'w',zipfile.ZIP_DEFLATED) as oz:
 for info in z.infolist():oz.writestr(info,E.tostring(tr,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
record={'parent':str(S),'parent_sha256':parent,'output':str(O),'output_sha256':hashlib.sha256(O.read_bytes()).hexdigest(),'changes':log,'status':'saved_candidate_not_rendered','source_review':'2025东城期末评分PDF16—17实看；2025丰台二模21原件含表格全文；其他精简不新增评分事实，原E1状态不升级'}
(R/'主代理修订/第三组修订记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(len(log),record['output_sha256'])
