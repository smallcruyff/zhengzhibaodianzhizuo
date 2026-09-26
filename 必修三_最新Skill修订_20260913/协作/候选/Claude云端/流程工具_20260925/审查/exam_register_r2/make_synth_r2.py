"""r2 审查合成用例（只写本会话临时区）。"""
import sys, shutil
sys.dont_write_bytecode = True
from pathlib import Path
import docx
S = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_exam_register_r2/synth')
if S.exists():
    shutil.rmtree(S)
S.mkdir(parents=True)
HERE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HERE))
import exam_register as er
BANK = Path('/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918')
T, _ = er.load_bank_alias_tables(BANK)
QS = [
 '某市推行“接诉即办”改革，市民热线诉求当天响应、限期办结，并将办理结果纳入部门考核。这一做法①坚持以人民为中心的发展思想②说明政府职能已经由管理转向服务③有利于提高政府的公信力和执行力④表明群众可以直接决定政府的施政方向A．①②B．①③C．②④D．③④',
 '某县探索“党建引领、村民议事、乡贤助力”的乡村治理模式，村内公共事务由村民议事会讨论决定。这一模式①丰富了基层民主的实现形式②改变了村民委员会的性质③有利于调动村民参与治理的积极性④说明村民议事会是基层政权组织A．①③B．①④C．②③D．②④',
 '某省人大常委会在制定地方性法规过程中，通过基层立法联系点广泛收集群众意见，并对意见采纳情况予以反馈。这体现了①全过程人民民主的实践②地方人大享有国家立法权③科学立法、民主立法的要求④人民群众直接行使立法权A．①③B．①④C．②③D．②④',
 '某区检察院针对校园周边食品安全问题发出检察建议，督促相关行政机关依法履职并开展专项整治。这说明①检察机关是国家的法律监督机关②检察机关可以直接行使行政处罚权③检察建议有助于推动依法行政④检察机关领导行政机关开展工作A．①③B．①④C．②③D．②④',
 '某市政协围绕“老旧小区改造”开展专题协商，委员们深入调研并提出多项建议，被有关部门吸收采纳。这表明①人民政协是专门协商机构②人民政协是国家权力机关③政协协商有助于科学民主决策④政协委员可以代替政府作出决策A．①③B．①④C．②③D．②④',
 '某地法院设立“共享法庭”，把诉讼服务延伸到村社网格，就地化解矛盾纠纷。这一做法①便利群众参与诉讼②改变了法院的审判职能③推动矛盾纠纷源头化解④意味着调解可以替代审判A．①③B．①④C．②③D．②④',
]
def mk(name, header, qs, numbered=True):
    d = docx.Document()
    for h in header:
        d.add_paragraph(h)
    for i, q in enumerate(qs):
        d.add_paragraph(f'{i + 1}．{q}' if numbered else q)
    d.save(str(S / name))
    return S / name
def stem(eid, q):
    p = BANK / 'questions' / eid / f'{eid}-Q{q}.md'
    s, _ = er.extract_stem_from_md(p.read_text(encoding='utf-8'), T)
    import re
    return re.sub(r'^\s*\d{1,2}\s*[.．、]\s*', '', s.strip())
# R1 高三“新”卷，届别 2025 海淀期中，但题面全新（与已登记 BJ-2025-HD-QIZHONG 不是同一张卷）
mk('r1_new_hd_2025_qizhong.docx', ['海淀区2024—2025学年第一学期期中练习', '高三思想政治', '2024.11'], QS)
# R2 真高二卷：2023—2024 学年高二 → 届别 2025，建议号同样落在 BJ-2025-HD-QIZHONG
mk('r2_grade2_hd.docx', ['海淀区2023—2024学年第一学期期中练习', '高二思想政治', '2023.11'], QS)
# R3 原件有文字层但卷首无日期；日期只在文件名里 → 只凭文件名能否定届别？
mk('2024.11海淀高三期中试卷.docx', ['北京市海淀区高三思想政治期中练习', '思想政治'], QS)
# R4 考生须知编号 + 21 道真实 BJ-2026-HD-QIZHONG 题面（整卷复印新卷）
real = [stem('BJ-2026-HD-QIZHONG', i) for i in range(1, 23)]
mk('r4_notice_numbered_copy_of_2026hd.docx',
   ['海淀区2025—2026学年第一学期期中练习', '高三思想政治', '2025.11', '考生须知',
    '1．本试卷共8页，共两部分，22道题，满分100分。考试时长90分钟。', '2．在试卷和答题纸上准确填写学校名称、班级名称、姓名。',
    '3．答案一律填涂或书写在答题纸上，在试卷上作答无效。', '4．考试结束，将本试卷、答题纸一并交回。', '第一部分'], real)
# R5 真实卷改掉大部分题面：BJ-2026-HD-QIZHONG 保留 Q1-Q4 原文，其余 18 题换成新题 → 应只报复用
mixed = real[:4] + (QS * 4)[:18]
mk('r5_mostly_rewritten_2026hd.docx', ['海淀区2026—2027学年第一学期期中练习', '高三思想政治', '2026.11'], mixed)
# R6 半数复用：11/22 原题 → 按 0.5 阈值会判 duplicate_registration
half = real[:11] + (QS * 3)[:11]
mk('r6_half_reuse.docx', ['海淀区2026—2027学年第一学期期中练习', '高三思想政治', '2026.11'], half)
# R7 高三卷首，第 2 行起就是 1．（无“第一部分”），卷首 1000 字内另有 2 个题干日期
mk('r7_header_date_after_notice.docx', ['海淀区高三年级第一学期期中练习', '考生须知', '1．本试卷共8页。', '2．考试时长90分钟。', '3．请在答题纸上作答。', '2024.11'], QS)
print('ok', sorted(p.name for p in S.iterdir()))
