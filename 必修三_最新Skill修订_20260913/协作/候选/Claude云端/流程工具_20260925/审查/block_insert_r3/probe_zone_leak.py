"""第二道防线实测：role=source + restore 的段放在【思维链条】之后（题目材料样式不在 source_style_reenter 里，
bh.walk 会把它算进 teaching 区），文字带工程标签 TODO。期望：写后区位复核抓到，rc=2，输出不留。"""
from common import *
def unit(extra_source_after_teaching, title):
    return {'schema':'baodian_insert_v1','book':'bixiu3','parent_docx_sha256':BOOK_SHA,
     'approved_by':'claude:review-r3','approval_ref':'审查探针',
     'inserts':[{'id':'Z1','anchor':{'after_block':{'title_contains':'例题 5　2026门头沟一模第17题'}},
       'template_block':{'title_contains':'例题 5　2026门头沟一模第17题'},
       'title':title,'source_zone':'restore','reason':'审查探针：验证写后区位复核',
       'content':[
        {'role':'source','text':'【题目】17．（8分）'},
        {'role':'source','text':'某市推进社区治理创新，建立居民议事会。'},
        {'role':'source','text':'结合材料，运用《政治与法治》知识，说明其意义。'},
        {'role':'teaching','like':'思维链条','text':'【思维链条】'},
        {'role':'source','text':extra_source_after_teaching},
        {'role':'teaching','like':'答案落点','text':'【答案落点】'},
        {'role':'teaching','text':'①发展基层民主，保障人民当家作主。'},
        {'role':'rubric','text':'【细则说明】 意义角度每点2分。'}]}]}
for tag, txt in (('leak','从材料选知识：此处 TODO 待核，本落位。'), ('clean','从材料选知识：居民议事会拓宽了参与渠道。')):
    docx = copy_book(f'zl_{tag}_parent.docx')
    up = wjson(f'zl_{tag}_insert.json', unit(txt, f'例题 90　2099审查探针{tag}第1题'))
    out = WORK / f'zl_{tag}_out.docx'; out.unlink(missing_ok=True)
    rep = WORK / f'zl_{tag}_report.json'; rep.unlink(missing_ok=True)
    rc, so, se = run(['apply','--docx',docx,'--insert',up,'--out',out,'--profile',PROF,'--report',rep])
    r = json.loads(rep.read_text()) if rep.exists() else {}
    print(tag, 'rc=',rc,'out_exists=',out.exists(), 'stderr=', se.strip()[-400:])
    print('   wordlist_leak=', (r.get('verify') or {}).get('wordlist_leak'))
    if out.exists():
        d2 = dl.open_docx(out)
        prof = bi.load_profile(str(PROF))
        zone,_,_,_ = ap.zones_of(d2, prof)
        for i,p in enumerate(d2.paras):
            if '从材料选知识：' in dl.para_text(p) and ('TODO' in dl.para_text(p) or '议事会拓宽' in dl.para_text(p)):
                print('   para', i, 'zone', zone[i], dl.para_text(p))
