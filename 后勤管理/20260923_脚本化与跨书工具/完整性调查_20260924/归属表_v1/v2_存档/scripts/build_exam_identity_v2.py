#!/usr/bin/env python3
"""build_exam_identity_v2.py —— 卷身份/别名/重定向表（缺口1）v2。只读，零模型token。

相对 v1 的变更（对应 审查意见.json blocker③、major①、minor项）：
  1. BJ-2024-MTG-YIMO：不再只留"disputed_scope待主代理裁定"，按主代理2026-09-24裁定固化为
     "项目级计入(compilation_only_project_level_include)"，身份层同时保留两条原始记录
     (2026-08-23选必二撤销 与 2026-09-24 REQ-PROJ-20260924-SCOPE-E1 取代)及其取代关系，
     并补上 book-xuanbi-1.md:401 的反向证据（该卷Q18已确认属于选必一题源）。
  2. 新增 BJ-2024-CY-QIZHONG 学年更正记录（原件文件名"202411朝阳高三政治期中1试题"→2024年11月→
     2024-2025学年，exams.csv 现登记2023-2024学年疑似同类学年错误），同 BJ-2023-HD-QIZHONG 一并
     列入"回传题库线"清单，不直接改题库。
  3. 新增 qid_redirects：BJ-2025-FT-YIMO-Q18 切分错误标记（题库把Q12的BMI表尾部与另一题选项
     拼成一道伪选择题，书稿引用的"2025丰台一模Q18(1)"主观题不在分母里）。
  4. named_exceptions 补齐 project-constitution.md 第50行的整卷例外名单（顺义二模/石景山期末/
     北京高考三卷），并标注"各book-*.md记的题数是该书实际用法，不是证据资格上限"。
  5. 输出 回传题库线_v2.json（不改题库文件，只登记待 Luna/题库负责人处理的条目）。

输出：exam_identity.json、回传题库线_v2.json
用法：python3 build_exam_identity_v2.py --out exam_identity.json --luna-out 回传题库线_v2.json
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, json
from pathlib import Path
from collections import defaultdict

BANK = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/DeepSeek_政治题库资料库_20260918')
INV = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
REVIEW_DIR = INV / '后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924'
SOURCE_INV = INV / '.claude/skills/beijing-gaokao-politics/references/source-inventory.md'
XUANBI1 = INV / '.claude/skills/beijing-gaokao-politics/references/book-xuanbi-1.md'
LEDGER = INV / '.claude/skills/beijing-gaokao-politics/references/user-requirements-ledger.md'
CONSTITUTION = INV / '.claude/skills/beijing-gaokao-politics/references/project-constitution.md'


def read_csv(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='exam_identity.json')
    ap.add_argument('--luna-out', default='回传题库线_v2.json')
    a = ap.parse_args()

    exams = read_csv(BANK / 'indexes/exams.csv')
    exam_by_id = {r['exam_id']: r for r in exams}
    dup_rows = read_csv(REVIEW_DIR / 'bank_duplicate_exams.csv')
    asm_rows = read_csv(BANK / 'indexes/assembly_blocks.csv')

    identity = {}
    luna_items = []

    def entry(eid):
        return identity.setdefault(eid, {
            'exam_id': eid, 'status': 'active', 'canonical_of': None,
            'aliases': [], 'corrections': {}, 'notes': [], 'evidence': [],
        })

    for r in exams:
        e = entry(r['exam_id'])
        e['evidence'].append({
            'type': 'exams.csv_row', 'path': str(BANK / 'indexes/exams.csv'),
            'fields': {k: r[k] for k in ('year', 'school_year', 'region', 'stage', 'has_paper', 'has_rubric', 'extract_status')},
        })
        if r.get('extract_status') == 'retired_duplicate_registration':
            e['status'] = 'retired_duplicate_registration'
            e['notes'].append('exams.csv 自带撤销说明：' + (r.get('notes') or ''))

    for r in dup_rows:
        if r['kind'] != 'duplicate_registration':
            continue
        a_id, b_id = r['exam_a'], r['exam_b']
        ra, rb = exam_by_id.get(a_id, {}), exam_by_id.get(b_id, {})
        a_accepted = ra.get('extract_status') == 'all_available_source_conversion_accepted'
        b_accepted = rb.get('extract_status') == 'all_available_source_conversion_accepted'
        if a_accepted and not b_accepted:
            canon, alias = a_id, b_id
        elif b_accepted and not a_accepted:
            canon, alias = b_id, a_id
        else:
            canon, alias = sorted([a_id, b_id])
        ec = entry(canon)
        ea = entry(alias)
        ea['status'] = 'duplicate_registration_alias'
        ea['canonical_of'] = canon
        if alias not in ec['aliases']:
            ec['aliases'].append(alias)
        note = (f"coverage.py bank_duplicate_exams.csv：{a_id} 与 {b_id} 重复登记，"
                f"共同题 {r['dup_questions']} 道（题号偏移 qa={r['qa']} vs qb={r['qb']}）。"
                f"题级对应不是简单同号一一对应：matrix.csv 的 dup_of 列已给出逐题对应关系"
                f"（例如2024 Q16↔2025 Q25），2025 Q16/Q18 在 matrix.csv 中无对应，本表不重复枚举，"
                f"归属表生成时直接读 matrix.csv 的 dup_of/dup_covered_by 逐题合并，不按"
                f"'同号即孪生'的粗糙假设处理（blocker③修复）。")
        ea['notes'].append(note)
        ea['evidence'].append({'type': 'bank_duplicate_exams.csv_row', 'path': str(REVIEW_DIR / 'bank_duplicate_exams.csv'), 'row': r})

    asm_only = defaultdict(list)
    for r in asm_rows:
        eid = (r.get('matched_exam_id') or '').strip()
        if not eid or eid in exam_by_id:
            continue
        asm_only[eid].append(r)
    for eid, rows in asm_only.items():
        e = entry(eid)
        e['status'] = 'compilation_only_no_exam_row'
        srcs = sorted({r.get('assembly_id', '') for r in rows})
        e['notes'].append(
            f'exams.csv 无该 exam_id 独立行；仅在汇编（{srcs}）中以“{rows[0].get("status","")}”登记，'
            f'{len(rows)} 个区块。按用户2026-09-24裁定 REQ-PROJ-20260924-SCOPE-E1 项目级计入：'
            f'选择题照收，主观题按同题同小问E1判定（暂无原卷/正式评分载体时标待裁决-证据未核实）。'
        )
        e['evidence'].append({
            'type': 'assembly_blocks.csv_rows', 'path': str(BANK / 'indexes/assembly_blocks.csv'),
            'sample_evidence': [r.get('evidence', '') for r in rows[:3]],
        })

    # ---- 人工核验记录固化（v2：门头沟/房山已按主代理裁定收口，不再是"待裁定"）----
    manual = [
        {
            'exam_id': 'BJ-2024-MTG-YIMO',
            'status': 'compilation_only_project_level_include',
            'notes': [
                '记录①（2026-08-23，选必二范围内，source-inventory.md第152行）：'
                '“用户于2026-08-23确认2024门头沟一模从未上传到本项目数据源。此前取得的门头沟原卷/参考答案'
                '及其Q12、Q13、Q19记录属于跨项目或外部线索污染，撤销其本项目题源身份；不得进入选必二正文、'
                'A1/A2、Excel、题量、评分统计或证据门。”——该条上下文明确限定在选必二一册的证据门禁。',
                '记录②（2026-09-24，项目级，user-requirements-ledger.md REQ-PROJ-20260924-SCOPE-E1）：'
                '“只要有细则的都收。没细则的只收选择题”“只在汇编里出现的卷同此处理（2024门头沟一模、房山一模'
                '按此项目级计入、只收选择题，取代2026-08-23选必二以‘非本项目上传数据源’撤销门头沟一模的口径；'
                '选必二重做时按新口径处理）”——已写入 incremental-question-intake.md“纳入范围”第9行。',
                '取代关系：记录②是2026-09-24用户明确针对记录①的口径更新，逐字写明“取代……撤销门头沟一模的口径”，'
                '本表按记录②执行，记录①仍完整保留作为历史依据，不删除。',
                '反向证据（补审查意见提到的缺口）：book-xuanbi-1.md 第401行：“2024门头沟一模Q18已确认属于'
                '本项目选必一题源，纠正历史‘题源边界待核’状态；当前载体仍只提供E3参考答案，没有同卷独立正式E1，'
                '因此只修订审计状态，不改正文和正式槽。”——即选必一已经把该卷Q18的题源身份问题单独核实为“确认属于'
                '本项目”，与记录①“撤销题源身份”并存的表面矛盾，实际是“选必二在2026-08-23误用了跨项目污染证据、'
                '选必一后来单独核实同一份汇编题源没有污染问题”，两册各自的证据链本来就不同源，本次项目级裁定统一'
                '按记录②的新口径执行，不需要再区分。',
                '必修三第52批仍引用该卷的汇编题肢（三路调查与审查摘要.txt第131行）——与项目级计入口径一致，不冲突。',
            ],
            'evidence': [
                {'type': 'source-inventory.md_line', 'path': str(SOURCE_INV), 'line': 152},
                {'type': 'source-inventory.md_line', 'path': str(SOURCE_INV), 'line': 136},
                {'type': 'user-requirements-ledger.md_section', 'path': str(LEDGER), 'anchor': 'REQ-PROJ-20260924-SCOPE-E1'},
                {'type': 'book-xuanbi-1.md_line', 'path': str(XUANBI1), 'line': 401},
                {'type': 'critic_summary_line', 'path': str(REVIEW_DIR / '三路调查与审查摘要.txt'), 'line': 131},
            ],
        },
        {
            'exam_id': 'BJ-2024-FS-YIMO',
            'status': 'compilation_only_project_level_include',
            'notes': [
                'source-inventory.md 第136行：2024房山一模只在分类汇编中出现，原卷与正式评分载体尚未取得，'
                '登记为“汇编线索／原卷与E1继续检索”，不是确认无细则。',
                '按 REQ-PROJ-20260924-SCOPE-E1 项目级计入：选择题照收，主观题需同题同小问E1才收，'
                '目前原卷全文未取得，暂只能生成候选行(见assembly_blocks候选)，题面/题型只能按汇编标注文本粗略推断，'
                '不能核实完整题面，主观题一律标“待裁决-证据未核实”。',
            ],
            'evidence': [
                {'type': 'source-inventory.md_line', 'path': str(SOURCE_INV), 'line': 136},
                {'type': 'user-requirements-ledger.md_section', 'path': str(LEDGER), 'anchor': 'REQ-PROJ-20260924-SCOPE-E1'},
            ],
        },
        {
            'exam_id': 'BJ-2023-HD-QIZHONG',
            'status': 'school_year_correction_pending_confirm',
            'corrections': {
                'school_year': {
                    'current_value': exam_by_id.get('BJ-2023-HD-QIZHONG', {}).get('school_year'),
                    'proposed_value': '2023-2024学年',
                    'evidence': '题库原件路径文件名为《2023北京海淀高三（上）期中政治（教师版）.docx》——“高三（上）”即2023年秋季学期，对应2023—2024学年，而不是exams.csv当前登记的2022-2023学年。',
                },
            },
            'notes': [
                '三路调查与审查摘要.txt 第129行（blind_spots）已指出该卷“exams.csv 里写的是2022-2023学年，但题面材料出现‘2023年9月’，实为2023—2024学年”。',
                '必修三台账称此卷“2023海淀期中”，必修二台账称“2024海淀期中”；history 线把它和“2023海淀一模（原名：2023海淀高三下期中）”误合并——两者是不同卷，已在本表分别登记，不应再合并。',
                '不改题库文件；已列入回传题库线清单（回传题库线_v2.json）。',
            ],
            'evidence': [
                {'type': 'source_map_or_exam_files_path', 'path': '2023模拟题/2023各区模拟题(1)/期末和期中/2023北京海淀高三（上）期中政治（教师版）.docx'},
                {'type': 'critic_summary_line', 'path': str(REVIEW_DIR / '三路调查与审查摘要.txt'), 'line': 129},
            ],
        },
        {
            'exam_id': 'BJ-2023-HD-YIMO',
            'status': 'active_distinct_from_qizhong',
            'notes': [
                '原件路径含“各区一模/海淀/…第二学期期中练习”，是2023海淀高三下学期期中练习（一模性质），与 BJ-2023-HD-QIZHONG（2023高三上学期期中）是两份不同的卷。'
                'history 线曾把二者当同一卷合并、误报“必修三台账缺2023海淀一模”（三路调查与审查摘要.txt 第120行已更正）。',
            ],
            'evidence': [
                {'type': 'critic_summary_line', 'path': str(REVIEW_DIR / '三路调查与审查摘要.txt'), 'line': 120},
            ],
        },
        {
            'exam_id': 'BJ-2024-CY-QIZHONG',
            'status': 'school_year_correction_pending_confirm',
            'corrections': {
                'school_year': {
                    'current_value': exam_by_id.get('BJ-2024-CY-QIZHONG', {}).get('school_year'),
                    'proposed_value': '2024-2025学年',
                    'evidence': '题库原件路径含《202411朝阳高三政治 期中1试题(1).pdf》——“202411”即2024年11月，'
                                 '对应2024年秋季学期→2024-2025学年，而不是exams.csv当前登记的2023-2024学年；'
                                 '与BJ-2023-HD-QIZHONG是同类“文件名年月 vs 登记学年”错位问题。',
                },
            },
            'notes': [
                '审查意见.json blocker③证据：“BJ-2024-CY-QIZHONG 的原件为‘202411…期中’，材料写‘2024年9月’，'
                'exams.csv 登记为2023-2024学年，属于同类学年错误，但没有登记。”本表按其提示核实原件路径后确认登记。',
                '不改题库文件；已列入回传题库线清单（回传题库线_v2.json）。',
            ],
            'evidence': [
                {'type': 'source_file_path', 'path': '2024模拟题/2024朝阳期中/试卷/补充材料/202411朝阳高三政治 期中1试题(1).pdf'},
            ],
        },
    ]
    for m in manual:
        e = entry(m['exam_id'])
        e['status'] = m['status']
        e['notes'].extend(m['notes'])
        e['evidence'].extend(m['evidence'])
        if 'corrections' in m:
            e['corrections'].update(m['corrections'])

    # ---- qid 级重定向（切分错误/串题；blocker③）----
    qid_redirects = {
        'BJ-2025-FT-YIMO-Q18': {
            'kind': 'split_error_fake_choice_question',
            'exclude_from_admission': True,
            'note': (
                '题库把该题登记为选择题（4个选项），但 units.jsonl 的 stem 实际是 '
                '“18.54~24 正常/24~28 超重/≥28 肥胖”——这是Q12题干里BMI分级表的尾部行随页面换行被误切成'
                '“Q18”，选项A-D的文字与Q13“下列选项中犯了与示例相同逻辑错误的是”一题的语境高度吻合，'
                '而题库里Q13的stem恰好缺选项（只到“第4页/共11页”截断）。可确认这是抽取阶段的切分错误，'
                '不是一道真实独立的第18题。该卷原卷“第二部分共6题”，但题库只登记了Q16/17/19/20/21五道主观题，'
                '真实的主观题“第18题”未被登记为任何 qid，书稿如引用“2025丰台一模Q18(1)”，指的是这道缺失的'
                '真实主观题，不是题库里的这个伪选择题。本表不猜测真实Q18内容，只标记该qid不计入选择题'
                '“照收”分母，并将“回补真实Q18、修正Q13选项归属”列入回传题库线清单，不直接改题库文件。'
            ),
        },
    }

    named_exceptions = {
        'BJ-2026-BJ-GAOKAO': {
            'kind': 'named_exception_whole_exam_no_rubric',
            'evidence': 'project-constitution.md special_override 行（第13行）：'
                         '“2026-08-22 用户明确宣布 2026 北京高考为第三套整卷无正式细则例外”；'
                         '第50行同列此卷为全项目三份整卷例外之一。',
        },
        'BJ-2024-SJS-YIMO': {
            'kind': 'named_exception_item_level_no_rubric',
            'scope': 'Q19(1)',
            'evidence': 'project-constitution.md special_override 行（第13行）：'
                         '“2026-08-27 用户明确特批 2024 石景山一模第 19 题第（1）问为题级无正式细则例外”；'
                         '第50行重申“该特批只覆盖这一小问，不扩张到同卷其他题目”。',
        },
        'BJ-2024-SY-ERMO': {
            'kind': 'named_exception_whole_exam_no_rubric',
            'evidence': 'project-constitution.md 第50行：“全项目当前只有2024顺义二模、2026石景山期末和'
                        '2026北京高考三份具名试卷属于整卷无正式评分细则例外”——证据资格是整卷级；'
                        'exams.csv本行notes原话：“独立E3参考答案，非E1”；'
                        'book-philosophy.md、book-culture.md的“书末E3例外”白名单是该书目前实际动用例外的'
                        '用法范围（各自记“两题”），不是证据资格的上限，本表evidence列按第50行的整卷证据资格填写，'
                        '各册具体收几题仍由各册自定。',
        },
        'BJ-2026-SJS-QIMO': {
            'kind': 'named_exception_whole_exam_no_rubric',
            'scope': 'Q1-Q20',
            'evidence': 'exams.csv 本行 notes 原话：“Q1-Q20按2026石景山期末具名无正式细则例外使用E3”（题库自身登记）；'
                        'project-constitution.md 第50行同列此卷为全项目三份整卷例外之一；'
                        'book-philosophy.md、book-culture.md的“书末E3例外”白名单同样列了“2026石景山期末”'
                        '（书用法范围，不是证据资格上限，理由同上条）。',
        },
    }
    for eid, info in named_exceptions.items():
        e = entry(eid)
        e.setdefault('named_exceptions', []).append(info)

    out = {
        'rule_version': '2026-09-24-identity-v2',
        'generated_by': 'build_exam_identity_v2.py（只读脚本，零模型token）',
        'sources_read': [
            str(BANK / 'indexes/exams.csv'), str(BANK / 'indexes/assembly_blocks.csv'),
            str(REVIEW_DIR / 'bank_duplicate_exams.csv'), str(SOURCE_INV),
            str(XUANBI1), str(LEDGER), str(CONSTITUTION),
            str(REVIEW_DIR / '三路调查与审查摘要.txt'),
        ],
        'legend': {
            'status': {
                'active': '正常登记，无已知身份问题',
                'retired_duplicate_registration': 'exams.csv 自身已标记撤销的重复登记',
                'duplicate_registration_alias': '本表新判定的重复登记别名，canonical_of 指向正式条目',
                'compilation_only_no_exam_row': '只在汇编中出现，题库未单独登记该卷',
                'compilation_only_project_level_include': '只在汇编中出现，按2026-09-24用户裁定项目级计入（选择题照收，主观题按E1判）',
                'school_year_correction_pending_confirm': '学年字段疑似写错，本表给出改正建议和依据，未直接改题库',
                'active_distinct_from_qizhong': '曾被误合并为另一张卷，本条目确认二者应分别计数',
            },
        },
        'qid_redirects': qid_redirects,
        'exams': identity,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')

    # ---- 回传题库线清单（不改题库文件，只登记）----
    luna_items = [
        {
            'exam_id': 'BJ-2023-HD-QIZHONG', 'field': 'school_year',
            'current_value': exam_by_id.get('BJ-2023-HD-QIZHONG', {}).get('school_year'),
            'proposed_value': '2023-2024学年',
            'evidence': '原件文件名《2023北京海淀高三（上）期中政治（教师版）.docx》"高三（上）"=2023秋季学期',
            'action': '更正 indexes/exams.csv 的 school_year 字段', 'status': 'pending_luna',
        },
        {
            'exam_id': 'BJ-2024-CY-QIZHONG', 'field': 'school_year',
            'current_value': exam_by_id.get('BJ-2024-CY-QIZHONG', {}).get('school_year'),
            'proposed_value': '2024-2025学年',
            'evidence': '原件文件名《202411朝阳高三政治 期中1试题(1).pdf》"202411"=2024年11月=2024秋季学期',
            'action': '更正 indexes/exams.csv 的 school_year 字段', 'status': 'pending_luna',
        },
        {
            'exam_id': 'BJ-2025-FT-YIMO', 'field': 'question_split(Q13/Q18)',
            'current_value': 'Q18登记为选择题(实为Q12 BMI表尾部误切)，Q13缺选项，真实主观题"第18题"未登记',
            'proposed_value': '重新切分：Q13补回真实选项；新增真实主观题Q18(1)(2)；删除/合并现有伪Q18选择题条目',
            'evidence': 'units.jsonl中BJ-2025-FT-YIMO-Q18的stem为BMI表残片；原卷"第二部分共6题"但题库只登记5道主观题(16/17/19/20/21)',
            'action': '回原卷PDF重新OCR/切分第12-19题区间', 'status': 'pending_luna',
        },
        {
            'exam_id': 'BJ-2024-BJ-GAOKAO', 'field': 'rubric_links覆盖缺口',
            'current_value': 'indexes/rubric_links.csv对该卷全部主观题只有已匹配参考答案(E3)行，没有正式评分材料(E1)行',
            'proposed_value': '补登《2024年北京市高考政治试题分析(1)》为该卷主观题的正式评分材料匹配行',
            'evidence': 'source-inventory.md第102行：用户2026-09-22确认该文件【细则】为2024高考正式细则，按E1使用',
            'action': '把该PDF逐题跑一遍rubric_links匹配流程，登记material_kind=正式评分材料/pair_status=已匹配正式材料',
            'status': 'pending_luna',
        },
    ]
    Path(a.luna_out).write_text(json.dumps({
        'rule_version': '2026-09-24-identity-v2',
        'purpose': '题库侧待修正条目清单，只读记录，不由本工具直接修改题库文件；由题库负责人(Luna线)核实后处理。',
        'items': luna_items,
    }, ensure_ascii=False, indent=1), encoding='utf-8')

    n_alias = sum(1 for e in identity.values() if e['status'] == 'duplicate_registration_alias')
    n_comp = sum(1 for e in identity.values() if e['status'].startswith('compilation_only'))
    print(f'exams total={len(identity)} alias={n_alias} compilation_only={n_comp} '
          f'qid_redirects={len(qid_redirects)} luna_items={len(luna_items)}')


if __name__ == '__main__':
    main()
