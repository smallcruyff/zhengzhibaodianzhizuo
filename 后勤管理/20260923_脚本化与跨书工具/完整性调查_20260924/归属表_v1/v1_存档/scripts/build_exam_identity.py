#!/usr/bin/env python3
"""build_exam_identity.py —— 卷身份/别名/重定向表（缺口1）。只读，零模型token。

输入（只读）：
  DeepSeek_政治题库资料库_20260918/indexes/exams.csv
  DeepSeek_政治题库资料库_20260918/indexes/assembly_blocks.csv
  后勤管理/…/完整性调查_20260924/bank_duplicate_exams.csv（coverage.py 产物，重复登记候选）
  .claude/skills/beijing-gaokao-politics/references/source-inventory.md（人工核验记录，只摘引用行号）

输出：exam_identity.json —— {exam_id: {status, canonical, aliases, corrections, evidence, notes}}
用法：python3 build_exam_identity.py --out exam_identity.json
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


def read_csv(p):
    with open(p, encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='exam_identity.json')
    a = ap.parse_args()

    exams = read_csv(BANK / 'indexes/exams.csv')
    exam_by_id = {r['exam_id']: r for r in exams}
    dup_rows = read_csv(REVIEW_DIR / 'bank_duplicate_exams.csv')
    asm_rows = read_csv(BANK / 'indexes/assembly_blocks.csv')

    identity = {}

    def entry(eid):
        return identity.setdefault(eid, {
            'exam_id': eid,
            'status': 'active',
            'canonical_of': None,   # 若本条是别名，指向的正式 exam_id
            'aliases': [],
            'corrections': {},      # 字段 -> {corrected_value, evidence}
            'notes': [],
            'evidence': [],
        })

    # ---- 1) 正常登记的卷：先都建成 active 条目 ----
    for r in exams:
        e = entry(r['exam_id'])
        e['evidence'].append({
            'type': 'exams.csv_row',
            'path': str(BANK / 'indexes/exams.csv'),
            'fields': {k: r[k] for k in ('year', 'school_year', 'region', 'stage', 'has_paper', 'has_rubric', 'extract_status')},
        })
        if r.get('extract_status') == 'retired_duplicate_registration':
            e['status'] = 'retired_duplicate_registration'
            e['notes'].append('exams.csv 自带撤销说明：' + (r.get('notes') or ''))

    # ---- 2) 重复登记（coverage.py bank_duplicate_exams.csv, kind=duplicate_registration）----
    for r in dup_rows:
        if r['kind'] != 'duplicate_registration':
            continue  # shared_or_reused_questions 是真实复用，不是重复登记，不建别名
        a_id, b_id = r['exam_a'], r['exam_b']
        # canonical 选：exams.csv 里已有正式验收记录（extract_status=all_available_source_conversion_accepted）优先；
        # 否则按 exam_id 里的年份数字较小者为准（沿用最早登记）。
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
                f"共同题 {r['dup_questions']} 道（题号偏移 qa={r['qa']} vs qb={r['qb']}）。")
        ea['notes'].append(note)
        ea['evidence'].append({'type': 'bank_duplicate_exams.csv_row', 'path': str(REVIEW_DIR / 'bank_duplicate_exams.csv'), 'row': r})

    # ---- 3) 只在汇编里出现、题库无独立登记的卷（缺卷行，进分母但标 compilation_only）----
    asm_only = defaultdict(list)
    for r in asm_rows:
        eid = (r.get('matched_exam_id') or '').strip()
        if not eid:
            continue
        if eid in exam_by_id:
            continue  # 题库已单独登记该卷，不算“只在汇编里”
        asm_only[eid].append(r)
    for eid, rows in asm_only.items():
        e = entry(eid)
        e['status'] = 'compilation_only_no_exam_row'
        srcs = sorted({r.get('assembly_id', '') for r in rows})
        e['notes'].append(
            f'exams.csv 无该 exam_id 独立行；仅在汇编（{srcs}）中以“{rows[0].get("status","")}”登记，'
            f'{len(rows)} 个区块。按缺卷行计入分母（见纳入范围 2026-09-24 裁定：只在汇编里出现的卷同样按“有细则的主观题才收”处理）。'
        )
        e['evidence'].append({
            'type': 'assembly_blocks.csv_rows', 'path': str(BANK / 'indexes/assembly_blocks.csv'),
            'sample_evidence': [r.get('evidence', '') for r in rows[:3]],
        })

    # ---- 4) 人工核验记录里已经写清楚、需要固化进身份层的具体条目（只摘引 source-inventory.md 行号，不改写判断）----
    manual = [
        {
            'exam_id': 'BJ-2024-MTG-YIMO',
            'status': 'disputed_scope',
            'notes': [
                'source-inventory.md 第152行：2026-08-23 用户确认“2024门头沟一模从未上传到本项目数据源”，'
                '此前取得的门头沟原卷/参考答案（含 Q12、Q13、Q19 记录）撤销本项目题源身份——但该条上下文限定在“选必二”小节（第150行标题：选必二 v14.4 回源证据结算）。',
                'source-inventory.md 第136行：另一条记录说“2024房山一模、门头沟一模目前只在分类汇编中出现，原卷与正式评分载体尚未取得；这两卷登记为汇编线索／原卷与E1继续检索，不是项目源缺失或确认无细则”——与第152行的“撤销”是否是同一份撤销、撤销范围是否覆盖全部书（含必修三第52批仍引用的汇编题肢）不一致。',
                '需主代理裁定：撤销是仅对选必二生效的书内证据门禁，还是对该 exam_id 的全局身份撤销；本条目已建立跨书共享的一处身份记录，避免出现“一册收一册撤”。',
            ],
            'evidence': [
                {'type': 'source-inventory.md_line', 'path': str(SOURCE_INV), 'line': 152},
                {'type': 'source-inventory.md_line', 'path': str(SOURCE_INV), 'line': 136},
                {'type': 'critic_summary_line', 'path': str(REVIEW_DIR / '三路调查与审查摘要.txt'), 'line': 131},
            ],
        },
        {
            'exam_id': 'BJ-2024-FS-YIMO',
            'status': 'compilation_only_pending_source',
            'notes': [
                'source-inventory.md 第136行：2024房山一模只在分类汇编中出现，原卷与正式评分载体尚未取得，登记为“汇编线索／原卷与E1继续检索”，不是确认无细则。',
                'exams.csv 无该 exam_id 独立行；assembly_blocks.csv 中以“已解析出处但本库无此卷（原料缺口）”多次出现。按纳入范围裁定②：模块归属逐题按实际考查内容判；按裁定①：该卷主观题需同题同小问 E1 才收，选择题照收——但目前连原卷全文都未取得，暂只能作为候选登记，不能核实题面。',
            ],
            'evidence': [
                {'type': 'source-inventory.md_line', 'path': str(SOURCE_INV), 'line': 136},
                {'type': 'assembly_blocks.csv_rows', 'path': str(BANK / 'indexes/assembly_blocks.csv')},
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
    ]
    for m in manual:
        e = entry(m['exam_id'])
        e['status'] = m['status']
        e['notes'].extend(m['notes'])
        e['evidence'].extend(m['evidence'])
        if 'corrections' in m:
            e['corrections'].update(m['corrections'])

    # ---- 5) 具名例外登记（“收”，不是身份问题，但和身份层共用一处存放，避免各册各查一遍）----
    named_exceptions = {
        'BJ-2026-BJ-GAOKAO': {
            'kind': 'named_exception_whole_exam_no_rubric',
            'evidence': 'project-constitution.md special_override 行（第13行附近）：'
                         '“2026-08-22 用户明确宣布 2026 北京高考为第三套整卷无正式细则例外”。',
        },
        'BJ-2024-SJS-YIMO': {
            'kind': 'named_exception_item_level_no_rubric',
            'scope': 'Q19(1)',
            'evidence': 'project-constitution.md special_override 行：'
                         '“2026-08-27 用户明确特批 2024 石景山一模第 19 题第（1）问为题级无正式细则例外”。',
        },
        'BJ-2024-SY-ERMO': {
            'kind': 'named_exception_whole_exam_no_rubric',
            'evidence': 'exams.csv 本行 notes 原话：“独立E3参考答案，非E1”（all_available_source_conversion_accepted）；'
                        'book-philosophy.md 第30行、book-culture.md 第34行均把“2024顺义二模”列入“书末E3例外”白名单——'
                        '与 project-constitution.md special_override 行（列的是2026北京高考整卷、2024石景山一模Q19(1)）不是同一份名单，'
                        '说明具名例外至少有两处独立登记（project-constitution.md 与各书 book-*.md 书末例外），本表把两处都收，不互相替代。',
        },
        'BJ-2026-SJS-QIMO': {
            'kind': 'named_exception_whole_exam_no_rubric',
            'evidence': 'exams.csv 本行 notes 原话：“Q1-Q20按2026石景山期末具名无正式细则例外使用E3”（题库自身登记，非本表推断）；'
                        'book-philosophy.md 第30行、book-culture.md 第34行的“书末E3例外”白名单同样列了“2026石景山期末”。'
                        '三路调查与审查摘要.txt 第132行提到09-23必修三比对曾以“只有参考答案”为由暂缓该卷（ledger第399行）——'
                        '这看起来是必修三当时尚未采用此例外，而不是该例外本身不成立；具体以哪个状态为准，需主代理按 book-bixiu-3.md 当前口径确认。',
        },
    }
    for eid, info in named_exceptions.items():
        e = entry(eid)
        e.setdefault('named_exceptions', []).append(info)

    out = {
        'rule_version': '2026-09-24-identity-v1',
        'generated_by': 'build_exam_identity.py（只读脚本，零模型token）',
        'sources_read': [
            str(BANK / 'indexes/exams.csv'),
            str(BANK / 'indexes/assembly_blocks.csv'),
            str(REVIEW_DIR / 'bank_duplicate_exams.csv'),
            str(SOURCE_INV),
            str(REVIEW_DIR / '三路调查与审查摘要.txt'),
        ],
        'legend': {
            'status': {
                'active': '正常登记，无已知身份问题',
                'retired_duplicate_registration': 'exams.csv 自身已标记撤销的重复登记',
                'duplicate_registration_alias': '本表新判定的重复登记别名，canonical_of 指向正式条目',
                'compilation_only_no_exam_row': '只在汇编中出现，题库未单独登记该卷',
                'compilation_only_pending_source': '只在汇编中出现，原卷/细则仍在找，不是“确认无细则”',
                'disputed_scope': '已有人工记录，但记录之间对该卷身份/撤销范围有冲突，需主代理裁定',
                'school_year_correction_pending_confirm': '学年字段疑似写错，本表给出改正建议和依据，未直接改题库',
                'active_distinct_from_qizhong': '曾被误合并为另一张卷，本条目确认二者应分别计数',
            },
        },
        'exams': identity,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
    n_alias = sum(1 for e in identity.values() if e['status'] == 'duplicate_registration_alias')
    n_comp = sum(1 for e in identity.values() if e['status'].startswith('compilation_only'))
    n_disp = sum(1 for e in identity.values() if e['status'] == 'disputed_scope')
    print(f'exams total={len(identity)} alias={n_alias} compilation_only={n_comp} disputed={n_disp}')


if __name__ == '__main__':
    main()
