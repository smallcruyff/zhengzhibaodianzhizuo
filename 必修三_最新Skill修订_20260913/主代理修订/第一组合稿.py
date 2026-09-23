from pathlib import Path
from copy import deepcopy
import json, zipfile, hashlib, re
from lxml import etree as E
ROOT=Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913')
SRC=Path('/Users/wanglifei/Desktop/gpt6/00_必修三最新审查稿/必修三政治与法治宝典_R31续修_第42批_当前工作稿.docx')
SHA='f4d5b295e73bebfa67cf86eb8cf3719c91752ff9a7d80ac6381e2c0298359946'
assert hashlib.sha256(SRC.read_bytes()).hexdigest()==SHA
cache=json.loads(Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/检查资料/agent_1_110/batch42_review/candidate_body.json').read_text())
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main'; ns={'w':W}
z=zipfile.ZipFile(SRC); tree=E.fromstring(z.read('word/document.xml'));body=tree.find('w:body',ns)
changes={
98:'【细则说明】 全国人大通过法定程序将党的主张上升为国家意志，实现了党的领导、人民当家作主、依法治国的有机统一，得2分。本题“是什么”部分任答一种可采表述得2分，与全国人大行使立法权等表述不重复计分。',
291:'【题目】 21．（9分）新时代，在我们党提出的一系列治国理政新理念新思想新战略中，统筹是其中蕴含的重要思想方法和工作方法。新征程上，我国发展环境面临深刻复杂变化，经济社会发展中矛盾错综复杂，这要求我们用好统筹方法。',
292:'● 统筹中华民族伟大复兴战略全局和世界百年未有之大变局\n● 统筹发展和安全\n● 统筹推进“五位一体”总体布局\n● 统筹依法治国各领域工作\n● ……',
293:'推进中国式现代化是一个系统工程，需要统筹兼顾、系统谋划、整体推进。从上述“统筹”中任选其一，综合运用所学，谈谈如何用好统筹方法推进中国式现代化。',
294:'【为什么能想到】 材料先指出“我们党”提出治国理政理念，再列出涉及发展、安全和多个治理领域的统筹任务。这些任务相互联系，需要从全局协调推进，由此联系党总揽全局、协调各方的领导核心作用。若选“统筹发展和安全”，就要说明党怎样把发展任务与安全要求一并谋划、协调落实，进而推进中国式现代化。',
542:'【为什么能想到】 材料说三部法律把党的十八大以来的生态文明建设成果、民族工作要求和国家发展规划制度用法律形式确定下来，又明确由全国人大表决通过。把这两层信息连起来，就能想到党的主张经法定程序上升为国家意志，联系党对全面依法治国的领导。',
544:'【细则说明】 通过法定程序将党的主张上升为国家意志，得2分。本题“是什么”部分任答一种可采表述得2分，与全国人大行使立法权、三者有机统一等表述不重复计分。',
2104:'【细则说明】 全国人大表决通过三部法律，体现全国人大行使立法权，得2分。本题“是什么”部分任答一种可采表述得2分，与党的主张上升为国家意志、三者有机统一等表述不重复计分。',
2692:'【细则说明】 全国人大行使立法权，三部法律成为中国特色社会主义法律体系的标志性“新成员”，得2分；三部法律使法律体系与时俱进、回应人民群众需求，得2分；夯实法治根基、提升国家治理体系和治理能力现代化水平，得2分。后4分也可分别说明三部法律制定的必要性，每部1分，再从法治、依法治国或国家治理层面概括得1分。',
3164:'【细则说明】 政府坚持依法行政，确保法律正确实施，属于推动法律落地见效的举措，得2分。这部分任答一种可采举措得2分，与公正司法、全民守法等举措不重复计分。',
3537:'【细则说明】 司法机关公正司法，确保法律正确实施，属于推动法律落地见效的举措，得2分。这部分任答一种可采举措得2分，与依法行政、全民守法等举措不重复计分。',
3761:'【细则说明】 加强法律宣传教育，推动全民守法；或增强法治意识，自觉学习和遵守，履行法定义务，得2分。这部分任答一种可采举措得2分，与依法行政、公正司法等举措不重复计分。',
1447:'【为什么能想到】 题面给出的是老旧社区的现实问题，设问问“如何”推动建设，需要提出措施。“居民意见不统一、改造方案制定和实施难”提示，应让居民参与协商、决策和实施，并通过监督评价改进治理，由此联系发展全过程人民民主。不能把这些拟采取的办法写成材料中已经发生的事实。',
1448:'【答案落点】 ①发展全过程人民民主，保障居民知情、参与、表达和监督。应组织居民围绕改造方案协商建言，引导居民有序参与社区事务、共同实施治理方案并开展监督评价，使民意贯穿决策和治理过程，推动平安社区建设。',
1074:'例题 2（补）　2021年北京高考第21题第（2）问',
4020:'【科学立法、民主立法与依法立法的做法】',
4021:'① 科学立法：立法机关深入调查研究，遵循社会发展规律，立足国情和实际，提高立法的科学性。',
4022:'② 民主立法：公开征求意见，健全立法机关和社会公众沟通机制，广泛听取社情民意。',
4023:'③ 民主立法：发挥基层立法联系点民意直通车作用，使基层意见直接进入立法过程。',
4024:'④ 组织专家论证、风险评估，增强法规的针对性和可操作性，侧重科学立法；开展多方协商、广泛听取意见，侧重民主立法。',
4025:'⑤ 依法立法：依照法定职权和法定程序立法，维护法制统一。'
}
# Restore source punctuation in all seven occurrences after checking exact question string.
for i in [95,541,2101,2689,3161,3534,3758]:
 assert '开局之年、三部' in cache[i]['text']
 changes[i]=cache[i]['text'].replace('开局之年、三部','开局之年，三部')
log=[]
for i,new in sorted(changes.items()):
 p=body[i];old=''.join(p.xpath('.//w:t/text()',namespaces=ns))
 assert p.tag==f'{{{W}}}p' and old==cache[i]['text'],(i,old)
 assert not p.xpath('.//w:drawing|.//w:pict|.//w:fldChar|.//w:commentRangeStart',namespaces=ns)
 runs=p.findall('w:r',ns);label=re.match(r'^(【[^】]+】)\s*',new)
 original_nonempty=[r for r in runs if ''.join(r.xpath('.//w:t/text()',namespaces=ns)).strip()]
 labelpr=deepcopy(original_nonempty[0].find('w:rPr',ns)) if original_nonempty else None
 textpr=deepcopy(original_nonempty[-1].find('w:rPr',ns)) if original_nonempty else None
 for r in runs:p.remove(r)
 def add(text,pr):
  r=E.SubElement(p,f'{{{W}}}r')
  if pr is not None:r.append(deepcopy(pr))
  for k,line in enumerate(text.split('\n')):
   if k:E.SubElement(r,f'{{{W}}}br')
   t=E.SubElement(r,f'{{{W}}}t');t.set('{http://www.w3.org/XML/1998/namespace}space','preserve');t.text=line
 if label:
  add(label.group(1),labelpr);add(' '+new[label.end():],textpr)
 else:add(new,textpr)
 log.append({'body_i_parent':i,'before':old,'after':new,'previous_anchor':cache[i-1]['text'],'next_anchor':cache[i+1]['text']})
out=ROOT/'必修三政治与法治宝典_R31续修_第43批_候选.docx'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as oz:
 for info in z.infolist():oz.writestr(info,E.tostring(tree,xml_declaration=True,encoding='UTF-8',standalone=True) if info.filename=='word/document.xml' else z.read(info.filename))
record={'parent':str(SRC),'parent_sha256':SHA,'output':str(out),'output_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'changes':log,'evidence':['2026朝阳一模/细则/细则.docx body114–127原件全文核对','hd_second_original.json body143–146及hd_second_pool-091/092.png实看'],'status':'saved_candidate_not_rendered'}
(ROOT/'主代理修订/第一组修订记录.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(len(log),record['output_sha256'],out)
