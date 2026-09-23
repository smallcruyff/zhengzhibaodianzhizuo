from pathlib import Path
from copy import deepcopy
import json,zipfile,hashlib,re
from lxml import etree as E
R=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913');S=R/'必修三政治与法治宝典_R31续修_第43批_候选3.docx';parent=hashlib.sha256(S.read_bytes()).hexdigest();assert parent=='36983a4163ea2f81548cf059087a34612b3ccd4b345dd283a964600c47e7d118'
z=zipfile.ZipFile(S);tr=E.fromstring(z.read('word/document.xml'));W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';ns={'w':W};b=tr.find('w:body',ns)
C=json.loads(Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/检查资料/agent_1_110/batch42_review/candidate_body.json').read_text())
changes={
391:'【答案落点】 ①中国式现代化是党领导人民长期探索和实践出来的，党的全面领导为探索把准方向、提供根本政治保证。进入关键时期，未来产业、人工智能治理、市场监管和民生保障仍面临新问题，既有经验需要在新的实践中发展。只有继续在党的领导下依靠人民探索，把实践经验转化为制度创新，才能破解发展难题，使中国式现代化道路越走越宽、越走越稳。',
392:'【细则说明】 中国式现代化由党领导人民长期探索形成，关键时期必须在党的领导下继续依靠人民探索，解决新情况新问题，使现代化道路越走越宽、越走越稳。“必要性分析”共3分，须兼顾中国式现代化、党和人民，不能把党与人民另拆分相加。',
584:'【为什么能想到】 题面写的是设施老化、服务滞后和改造难等问题，多方诉求与资源需要协调。因此可以提出由党组织深入社区了解民意、统筹各方资源、牵头破解难题的办法，联系党建引领基层治理。党发挥领导和协调作用，具体行政职责仍由政府履行。',
585:'【答案落点】 ①坚持党的领导，以党建引领基层治理。党员干部应深入社区了解民意，党组织应协调各方资源、牵头破解安全、养老和改造难题，为平安社区建设提供方向引领和组织保障。',
670:'【细则说明】 “党的领导”或“国家顶层设计”可概括为一项有利条件。在“发挥作用”部分，党的领导与政府宏观调控、经济职能或集中力量办大事的制度优势共用1分；说明促进人工智能与完整产业体系深度融合得1分，落到建设现代化产业体系或推动产业结构优化升级再得1分。',
3239:'【细则说明】 “政府宏观调控”可概括为一项有利条件。在“发挥作用”部分，政府宏观调控、经济职能与党的领导或集中力量办大事的制度优势共用1分；说明促进人工智能与完整产业体系深度融合得1分，落到建设现代化产业体系或推动产业结构优化升级再得1分。',
497:'【细则说明】 “党的领导”出现即计2分，“三统一”与“党的领导”作同项处理，不重复计分。结合区域发展战略，可进一步说明党中央从全局谋划，推动区域优势互补、政策协同，把发展落差转化为协同发展动能。',
4042:'本附录整理732条题肢，A1供独立判断练习，A2按相同编号给出答案与纠正。'
}
for i,marker in [(374,'作答整题还必须'),(2758,'完全照抄材料'),(3203,'；只罗列知识'),(3988,'，缺少具体')]:
 v=C[i]['text'].split(marker)[0].rstrip('；， ')
 if not v.endswith('。'):v+='。'
 changes[i]=v
# A cross-module distractor: its judgement hinges on the civil-law voluntary principle (选必二), not a Bixiu 3 proposition.
removes=[4993,6358,6359]
log=[]
def txt(p):return ''.join(p.xpath('.//w:t/text()',namespaces=ns))
def pos(i):return i-sum(k<i for k in [261,488,1073,1284,1811,2042,2295,2429])+7*(i>=4678)+7*(i>=5938)
original=list(b)
for i,new in changes.items():
 p=original[pos(i)];old=txt(p);assert old==C[i]['text'],(i,old)
 non=[r for r in p.findall('w:r',ns) if txt(r).strip()];lp=deepcopy(non[0].find('w:rPr',ns));tp=deepcopy(non[-1].find('w:rPr',ns));assert not p.xpath('.//w:drawing|.//w:fldChar',namespaces=ns)
 for r in p.findall('w:r',ns):p.remove(r)
 lab=re.match('^(【[^】]+】)\\s*',new)
 for tx,pr in ([(lab.group(1),lp),(' '+new[lab.end():],tp)] if lab else [(new,tp)]):
  r=E.SubElement(p,'{'+W+'}r')
  if pr is not None:r.append(deepcopy(pr))
  t=E.SubElement(r,'{'+W+'}t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=tx
 log.append({'parent42_body_i':i,'before':old,'after':new})
for i in removes:
 p=original[pos(i)];assert txt(p)==C[i]['text'];log.append({'parent42_body_i':i,'before':txt(p),'after':None,'reason':'2023高考9第675补4肢判断核心为选必二民事自愿原则；不能因户政材料直接归必修三。原编号保留，A1/A2同步排除。'});b.remove(p)
O=R/'必修三政治与法治宝典_R31续修_第43批_候选4.docx'
with zipfile.ZipFile(O,'w',zipfile.ZIP_DEFLATED) as oz:
 for info in z.infolist():oz.writestr(info,E.tostring(tr,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
record={'parent':str(S),'parent_sha256':parent,'output':str(O),'output_sha256':hashlib.sha256(O.read_bytes()).hexdigest(),'changes':log,'status':'saved_candidate_not_rendered','source_review':'西城一模21当前原题嵌图实看；朝阳一模18六处同题审题全查；海淀期中两处疑字与源DOCX/PDF均相同，未擅改，保持原源待核'}
(R/'主代理修订/第四组修订记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));print(len(log),record['output_sha256'])
