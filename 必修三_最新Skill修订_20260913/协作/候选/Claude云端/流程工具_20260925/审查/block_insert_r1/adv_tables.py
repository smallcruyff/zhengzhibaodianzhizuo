import sys; sys.dont_write_bytecode=True
import json, shutil, subprocess, zipfile, collections, posixpath, os
from pathlib import Path
from lxml import etree
HERE=Path(__file__).resolve().parent
C=Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
RAW=Path('/home/user/zhengzhibaodianzhizuo/00_共同资料/原材料')
BOOK=Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx')
SHA='c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
PROF=C/'profiles_cloud/bixiu3.json'
OUT=HERE/'adv_out'; OUT.mkdir(exist_ok=True)
parent=OUT/'parent.docx'
if not parent.exists(): shutil.copyfile(BOOK,parent)
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
R='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
WP='{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}'
cases={
 'dc_teacher_tbl4': RAW/'2026模拟题/2026各区二模/2026东城二模/试卷/2026北京东城高三二模政治（教师版）.docx',
 'hyperlink_21': RAW/'2024模拟题/东城二模/细则/分题细则/阅卷总结/21题/21.docx',
 'cp_teacher_tbl1': RAW/'2026模拟题/2026各区二模/2026昌平二模/2026北京昌平高三二模政治（教师版）.docx',
 'dc16_pict': RAW/'2024模拟题/东城二模/细则/分题细则/阅卷总结/16题/16题二模阅卷总结.docx',
}
tidx={'dc_teacher_tbl4':4,'hyperlink_21':1,'cp_teacher_tbl1':1,'dc16_pict':1}
def check(out):
    z=zipfile.ZipFile(out); names=set(z.namelist())
    root=etree.fromstring(z.read('word/document.xml'))
    rels={r.get('Id'):(r.get('Type').split('/')[-1],r.get('Target'),r.get('TargetMode')) for r in etree.fromstring(z.read('word/_rels/document.xml.rels'))}
    pz=zipfile.ZipFile(parent); prels={r.get('Id'):(r.get('Type').split('/')[-1],r.get('Target')) for r in etree.fromstring(pz.read('word/_rels/document.xml.rels'))}
    proot=etree.fromstring(pz.read('word/document.xml'))
    pids=collections.Counter(e.get('id') for e in proot.iter(WP+'docPr'))
    ids=collections.Counter(e.get('id') for e in root.iter(WP+'docPr'))
    newdup={k:v for k,v in ids.items() if v>1 and v!=pids.get(k)}
    # r:* attributes in output whose meaning differs from source: find hyperlinks
    hl=[(el.get(R+'id'),rels.get(el.get(R+'id'))) for el in root.iter(W+'hyperlink') if el.get(R+'id')]
    phl=[(el.get(R+'id')) for el in proot.iter(W+'hyperlink') if el.get(R+'id')]
    anchors=len(list(root.iter(WP+'anchor'))) - len(list(proot.iter(WP+'anchor')))
    vml=[el.get(R+'id') for el in root.iter('{urn:schemas-microsoft-com:vml}imagedata')]
    dang=[(el.tag.split('}')[1],a.split('}')[1],v) for el in root.iter() for a,v in el.attrib.items() if a.startswith(R) and v not in rels]
    return {'new_docPr_dups':newdup,'hyperlinks_out':hl[:6],'hyperlinks_parent':len(phl),'new_anchors':anchors,'vml_imagedata_rids':[(v,rels.get(v)) for v in vml][:6],'dangling':dang[:8]}
res={}
for name,src in cases.items():
    unit={'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':SHA,'approved_by':'claude:review-r1','approval_ref':'对抗审查',
      'inserts':[{'id':'X1','anchor':{'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}},
        'template_block':{'title_contains':'例题 3　2024朝阳二模第18题'},'title':'例题 95　2026东城二模第99题',
        'source_zone':'restore','reason':'对抗审查：外部原件表格',
        'content':[{'role':'source','text':'【题目】16．（8分）阅读材料，回答问题。'},
                   {'role':'table','from':{'docx':str(src),'table_index':tidx[name]}},
                   {'role':'source','text':'结合材料，说明理由。'}]}]}
    up=OUT/f'{name}_unit.json'; up.write_text(json.dumps(unit,ensure_ascii=False),encoding='utf-8')
    out=OUT/f'{name}_out.docx'; rep=OUT/f'{name}_rep.json'
    for p in (out,rep):
        if p.exists(): p.unlink()
    r=subprocess.run([sys.executable,str(C/'block_insert.py'),'apply','--docx',str(parent),'--insert',str(up),'--out',str(out),'--profile',str(PROF),'--report',str(rep)],capture_output=True,text=True)
    info={'rc':r.returncode,'stdout':r.stdout[-300:],'stderr':r.stderr[-400:],'out_exists':out.exists()}
    if out.exists():
        info.update(check(out))
        try:
            import docx; docx.Document(str(out)); info['python_docx']='ok'
        except Exception as e: info['python_docx']=str(e)
        if rep.exists():
            rj=json.loads(rep.read_text()); info['verify']={k:v for k,v in rj.get('verify',{}).items() if k!='block_index_check'}; info['bic']=rj.get('verify',{}).get('block_index_check')
    res[name]=info
    print(name, json.dumps(info,ensure_ascii=False,indent=1)[:2500])
(OUT/'adv_tables_result.json').write_text(json.dumps(res,ensure_ascii=False,indent=1,default=str),encoding='utf-8')
