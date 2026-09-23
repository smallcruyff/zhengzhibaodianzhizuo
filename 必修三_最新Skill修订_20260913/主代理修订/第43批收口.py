from pathlib import Path
import json, hashlib, shutil
from datetime import datetime

R = Path('/Users/wanglifei/Desktop/gpt6/必修三_最新Skill修订_20260913')
V = Path('/Users/wanglifei/Desktop/gpt6/00_必修三最新审查稿')
S = Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/当前状态.json')
def read(p): return json.loads(p.read_text())
def write(p, d): p.write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
now = datetime.now().astimezone().isoformat()
render = read(R/'主代理修订/同版渲染记录.json')
tech = read(R/'主代理修订/最终技术核验.json')
pixels = read(R/'页面检查/验收逐像素核验.json')
root = read(R/'页面检查/主代理实看与裁决.json')
nav = read(R/'主代理修订/目录同版核验.json')
doc = Path(render['docx']); pdf = Path(render['pdf'])
assert sha(doc) == render['docx_sha256'] == tech['sha256']
assert sha(pdf) == render['pdf_sha256'] == pixels['final_pdf_sha256'] == root['final_pdf_sha256']
assert render['pages'] == render['png_count'] == 532
assert len(nav) == 32 and all(x['heading_present_on_pdf_page'] for x in nav)
seen = set(); agents = []
for name in ['Luna_1_180.json','Luna_141_180.json','Luna_181_360.json','Luna_361_532.json']:
    p = R/'页面检查'/name; d = read(p)
    assert d.get('status',d.get('review_status')) == 'complete', name
    pages = set(d.get('viewed_pages',d.get('pages_viewed',[])))
    seen |= pages
    agents.append({'record':str(p),'sha256':sha(p),'pages':sorted(pages),'same_round_prior_render_inheritance':d.get('pixel_inherited_pages',d.get('pixel_comparison_181_192'))})
direct = set(root['actual_view_image_pages_by_directory']['第43批页面_验收'])
inherited = seen & set(pixels['identical_pages']) - direct
covered = direct | inherited
assert covered == set(range(1,533)), sorted(set(range(1,533))-covered)
assert set(pixels['changed_pages']) <= direct
qa = {'checked_at':now,'docx_sha256':sha(doc),'pdf_sha256':sha(pdf),'pages':532,'scope':'整书页面逐页检查完成；非整书题源、教研或送印终审','agents':agents,'final_direct_root_pages':sorted(direct),'final_zero_pixel_difference_inherited_pages':sorted(inherited),'covered_pages':sorted(covered),'covered_count':len(covered),'pixel_record':str(R/'页面检查/验收逐像素核验.json'),'root_decisions':str(R/'页面检查/主代理实看与裁决.json'),'known_limits':['原卷扫描图38/114/398页小字噪点','整块材料分页留白','282/284/286页旧显式分页后的短续文页'],'status':'phase_review_complete_with_disclosed_limits'}
write(R/'页面检查/整书页面验收.json',qa)
render['visual_review_complete']=True;render['visual_review_record']=str(R/'页面检查/整书页面验收.json');write(R/'主代理修订/同版渲染记录.json',render)
tech['visual_review']=str(R/'页面检查/整书页面验收.json');write(R/'主代理修订/最终技术核验.json',tech)

notes = '''# 第43批阶段审查稿

本轮已按 Skill 6.2.0 实际修订，保留必修三现有框架与四栏目。Word与原生PDF为同版，PDF共532页。供教师人工审阅，尚非整书终审或送印定稿。

本轮主要变化：

- 按正式细则修正2026朝阳一模21的分值与各落位逻辑；七处没有机械改成同一分值。
- 恢复2026海淀二模21的四项统筹材料与设问，重写材料到党的领导的推理；修正2025朝阳一模18等把建议写成材料事实的问题。
- 对2023高考20、2021高考21(2)、东城期末、丰台二模、石景山一模等同题各落位，精简等级赋分和泛泛提示，保留当前角度有依据的踩分表述与真实分值；校准附录立法方式辨析。
- 补回2024东城一模4的问卷和“最适合”设问，修正495题肢；将449、675（补4）两条跨册题肢从练习与答案同步剔除。原编号保留，A1/A2各731条，题肢文本及编号逐条一致。
- 修正重复例题编号、目录缓存、标题衔接、项目符号字距。385处主观题落位均保留四栏目；234个正文表格、95幅插图保留，所用插图字节未变。

核验范围：原任务三项Luna检查已全部接收；主代理亲自核高优先级原题、正式细则并改写教学内容。页面由三路Luna分段逐张查看，主代理复核问题页；最终变化5页重新实看，其余页面仅在同物理页逐像素完全相同且已有实看记录时继承。最终532页全部有实看或严格继承记录，32个目录页码与PDF实际标题位置一致。

仍待解决：2025高考第21题未找到可靠独立正式评分来源，不虚构分值或新增例外。2026选择题旧缓存25条关联复核中有24条与当前编号不对应，已隔离，未按错误编号修改正文；这不是24条正文错误的结论。全题源覆盖和全部教研证据未在本轮重新宣称通过，后续需沿实际审计未决继续。

版式保留项：38、114、398页同一原卷流程图有扫描噪点；部分整块材料起于下页，产生留白；282、284、286页沿旧题序显式分页，保留短续文页。材料内容完整，送印清晰度与压页优化仍待后续处理。第2页前言留白为用户要求。

请按“第43批＋PDF页码”提出修改意见。旧第42批审阅文件与可能批注可恢复保留，原工程和题源未覆盖。
'''
(R/'本轮修订与审查说明.md').write_text(notes)

# All acceptance work above is complete before touching the fixed review entry.
oldmanifest = read(V/'.review-manifest.json'); olddoc=Path(oldmanifest['docx'])
assert oldmanifest['docx_sha256']=='f4d5b295e73bebfa67cf86eb8cf3719c91752ff9a7d80ac6381e2c0298359946'
assert sha(olddoc)==oldmanifest['docx_sha256'], 'User review copy changed; preserve and reconcile first'
archive = Path('/Users/wanglifei/Desktop/gpt6/必修三_人工审查历史')/datetime.now().strftime('第42批_原样审阅_%Y%m%d_%H%M%S')
assert not archive.exists(); archive.mkdir(parents=True)
registered=[olddoc,V/'先看这里.md',V/'.review-manifest.json']
if oldmanifest.get('pdf'): registered.append(Path(oldmanifest['pdf']))
moves=[]
for p in registered:
    assert p.parent==V and p.is_file()
    target=archive/p.name; fingerprint=sha(p);shutil.move(str(p),str(target));assert sha(target)==fingerprint
    moves.append({'from':str(p),'to':str(target),'sha256':fingerprint})
for p in [doc,pdf]:
    q=V/p.name;assert not q.exists();shutil.copy2(p,q);assert sha(q)==sha(p)
entry = f'''# 必修三最新审查稿：第43批

更新时间：{now}

当前为第43批阶段审查稿，Word与原生PDF同版，532页。尚非整书终审或送印定稿。

- [打开Word]({V/doc.name})
- [打开同版PDF]({V/pdf.name})
- [本轮修订与审查说明]({R/'本轮修订与审查说明.md'})

本轮修正细则分值和材料推理、恢复遗漏题面，校准立法辨析与题肢范围，并完成整书页面检查。主观题落位385处，练习与答案各731条。2025高考21正式评分来源仍待核，部分旧稿留白与扫描噪点保留。

请按“第43批＋PDF页码”反馈。上一份第42批审阅稿已原样保存在[人工审查历史]({archive})；用户未登记文件及Word锁文件未删除。
'''
(V/'先看这里.md').write_text(entry)
manifest={'copied_at':now,'source_state':str(S),'source_docx':str(doc),'source_pdf':str(pdf),'docx':str(V/doc.name),'docx_sha256':sha(doc),'bytes':doc.stat().st_size,'pdf':str(V/pdf.name),'pdf_sha256':sha(pdf),'pdf_pages':532,'status':'stage_review_copy_not_final','latest_batch':'batch43','body_changed':True,'verified':'native Word same-version export; ZIP and structure checked; 32 navigation pages matched; 532 visual pages covered with disclosed limitations','review_record':str(R/'页面检查/整书页面验收.json'),'previous_review_archive':str(archive)}
write(V/'.review-manifest.json',manifest)
write(R/'主代理修订/审阅入口更新记录.json',{'time':now,'moves':moves,'published':manifest,'unregistered_files_preserved':[p.name for p in V.iterdir() if p.name not in [doc.name,pdf.name,'先看这里.md','.review-manifest.json']]})

state=read(S);write(R/'主代理修订/晋升前中央状态.json',state)
state['target']='按Skill 6.2.0修订必修三R31第42批实际工作头，完成第43批阶段审查；保留既有框架与四栏目'
state['status']='第43批阶段修订完成，待用户人工审阅；整书终审未完成'
state['updated_at']=now
state['previous_working_head']={'path':state['working_head'],'sha256':state['working_head_sha256'],'bytes':state['working_head_bytes'],'revision':'batch42'}
state['working_head']=str(doc);state['working_head_sha256']=sha(doc);state['working_head_bytes']=doc.stat().st_size;state['release_head']=None
state['outputs']=[str(doc),str(pdf)];state['body_placements_current']=385;state['appendix_entries_current']=731;state['appendix_paired_items_current']=731;state['appendix_entries_excluded']=81;state['appendix_boundary_exclusions']=81
state['latest_batch']='batch43：正式分值与教学逻辑修正、题面恢复、学生版细则精简、题肢配对及范围校准、同版原生导出与532页阶段检查完成'
state['audit_xlsx_status']='已核实际XLSX为第42批，385落位/733配对/79排除；历史XLSX原件未改，本轮385/731/81以第43批增量JSON为准'
state['audit_incremental_json']=str(R/'主代理修订/最终技术核验.json')
state['latest_render']={'docx_sha256':sha(doc),'pdf':str(pdf),'pdf_sha256':sha(pdf),'directory':render['png_count'] and str(R/'第43批页面_验收'),'pages':532,'whole_book_visual_complete':True,'visual_review_scope':'phase review with disclosed source-quality and legacy-pagination limitations','record':str(R/'页面检查/整书页面验收.json')}
state['latest_render_sha256']=sha(doc);state['latest_rendered_docx_sha256']=sha(doc);state['latest_render_pages']=532;state['latest_rendered_pages']=532;state['latest_render_directory']=str(R/'第43批页面_验收');state['latest_root_visual_review_record']=str(R/'页面检查/主代理实看与裁决.json')
state['active_revision_round']={'revision':'batch43','skill':'6.2.0','directory':str(R),'status':'completed_for_human_review_not_final','docx':str(doc),'docx_sha256':sha(doc),'pdf':str(pdf),'pdf_sha256':sha(pdf),'pages':532,'body_placements':385,'paired_claims':731,'excluded_claims':81,'original_three_luna_results':'全部收齐并经主代理裁决','remaining':'2025高考21 E1来源等既有证据未决、全题源终审、旧扫描清晰度与部分分页优化','summary':str(R/'本轮修订与审查说明.md')}
state['review_entry']=str(V);state['review_manifest']=str(V/'.review-manifest.json')
state['next']='接收用户第43批＋PDF页码意见；后续按实际证据未决和覆盖账续修，不自动启动下一轮'
state['next_action']=state['next']
write(S,state)
handoff=R/'00_新任务交接.md';text=handoff.read_text();banner=f'截至{now}：本轮已完成第43批阶段修订与固定审阅入口更新。当前工作头以中央状态及本目录《本轮修订与审查说明.md》为准。下文为接续时历史记录，不再代表当前稿件或任务进度。\n\n'
handoff.write_text(banner+text)
assert sha(V/doc.name)==state['working_head_sha256'] and sha(V/pdf.name)==manifest['pdf_sha256']
print(json.dumps({'status':'published_stage_review','docx':manifest['docx'],'pdf':manifest['pdf'],'pages':532,'visual_covered':len(covered),'direct_final_root':len(direct),'strictly_inherited':len(inherited),'archive':str(archive)},ensure_ascii=False,indent=2))
