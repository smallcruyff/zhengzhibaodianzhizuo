#!/usr/bin/env python3
"""placement_suggest.py 对抗审查（第 1 轮）可重跑探针。

只读真实输入；产物只写系统临时目录（SCR）与本目录下 adv_results.json。
每条用例写“规格期望”与“实际”，PASS=工具行为符合规格/共同约定，FAIL=不符合。
退出码＝FAIL 数（这是审查探针，FAIL 表示被审工具的问题，不表示探针坏了）。
"""
import sys

sys.dont_write_bytecode = True

import glob
import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
C = HERE.parent.parent
TOOL = C / 'placement_suggest.py'
PROFILE = C / 'profiles_cloud' / 'bixiu3.json'
FROZEN = C / 'profiles_cloud' / 'bixiu2_frozen_test.json'
REPO = Path('/home/user/zhengzhibaodianzhizuo')
BOOK3 = REPO / '必修三_最新Skill修订_20260913' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
BANK = REPO / 'DeepSeek_政治题库资料库_20260918'
SK = REPO / '.claude' / 'skills' / 'beijing-gaokao-politics' / 'scripts'
SCR = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/'
           'scratchpad/review_placement_suggest_r1/adv_py')

sys.path.insert(0, str(C))
import placement_suggest as ps  # noqa: E402
from profile_lib import load_profile  # noqa: E402
import docx_lib as dl  # noqa: E402
import apply_patch as ap  # noqa: E402

rows = []


def rec(cid, ok, expect, actual, t0):
    rows.append({'id': cid, 'result': 'PASS' if ok else 'FAIL', 'expect': expect, 'actual': actual,
                 'seconds': round(time.time() - t0, 2)})
    print(('PASS' if ok else 'FAIL'), cid, f'({time.time() - t0:.1f}s)', '-', actual[:300])


def cli(args, env=None):
    p = subprocess.run([sys.executable, str(TOOL)] + args, capture_output=True, text=True, timeout=300,
                       env=env)
    return p.returncode, p.stdout, p.stderr


def mdq(key):
    p = ps.find_md_path(BANK, key)
    return ps.parse_question_md(p.read_text(encoding='utf-8', errors='replace'), key)


def main():
    if SCR.exists():
        shutil.rmtree(SCR)
    SCR.mkdir(parents=True)
    t0 = time.time()
    prof = load_profile(str(PROFILE))
    book = ps.load_book(str(BOOK3), prof)
    B = book['blocks']
    mi = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
    idx = ps.build_indices(ps.block_fields_all(B, mi), ps.DEFAULT_PARAMS['ngram_sizes'])
    print(f'装书+建索引 {time.time() - t0:.1f}s')

    # R01 题型：MD 明写“非选择题”，材料含 A．B．观点行 → 应按主观题处理
    t = time.time()
    q = mdq('BJ-2026-HD-ERMO-Q21')
    rec('R01 题型字段“非选择题”被选项行启发式覆盖', q['kind'] == 'subjective',
        'MD 身份节题型=非选择题 → kind=subjective（主观题须过 E1 过滤）',
        f"kind={q['kind']} kind_field={q['kind_field_raw']!r}", t)

    # R02 合成：非选择题 + A-D 观点行 + 明确无 E1 → 应标“主观题无正式细则，按规则不收”，退出 1
    t = time.time()
    md = SCR / 'synthetic_subj_noe1.md'
    md.write_text('# BJ-2099-XX-YIMO-Q18\n\n## 身份信息\n- 题型：非选择题\n\n## 题面\n'
                  '18．（10分）某市围绕公园管理征求市民意见。市民观点如下：\n'
                  'A．公园里骑车撞到老人和小孩怎么办？\nB．在公园里骑车赏景是很好的休闲方式。\n'
                  'C．没有滑板车，小孩子逛公园太累了。\nD．商拍占道占景，影响游览体验。\n'
                  '结合材料，运用《政治与法治》知识，就完善公园管理提出建议。\n\n'
                  '## 正式评分材料原文\n（未找到已确认的正式评分材料；见下方候选区）\n', encoding='utf-8')
    rep = SCR / 'R02.json'
    code, out, err = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--md', str(md), '--report', str(rep)])
    r = json.loads(rep.read_text(encoding='utf-8'))['results'][0] if rep.exists() else {}
    rec('R02 无细则主观题绕过 SCOPE-E1 过滤', code == 1 and any('细则' in f for f in r.get('flags', [])),
        '退出 1 且 flags 含“主观题未找到正式评分细则”', f"exit={code} kind={r.get('kind')} e1_present={r.get('e1_present')} flags={r.get('flags')}", t)

    # R03 选择题选项写成“- **A**: ①②”、无题型字段 → 应认成选择题
    t = time.time()
    q = mdq('BJ-2024-DC-ERMO-Q5')
    rec('R03 选择题（列表式选项）被认成主观题', q['kind'] == 'choice',
        '书中为选择题 B0368，MD 选项行“- **A**: ①②” → kind=choice，且不应标“主观题无细则”',
        f"kind={q['kind']} e1_present={q['e1_present']}", t)

    # R04/R05 E1 节名：“E1阅卷细则原文…”、后出现的“正式评分材料（E1，…）”
    for cid, key in (('R04', 'BJ-2024-DC-ERMO-Q18'), ('R05', 'BJ-2023-DC-ERMO-Q21')):
        t = time.time()
        q = mdq(key)
        rec(f'{cid} E1 节漏认 → 误标“按规则不收”（{key}）', q['e1_present'],
            'MD 含实际 E1 节（阅卷细则/等级标准原文）→ e1_present=True',
            f"e1_header={q['e1_header']!r} e1_present={q['e1_present']} rubric[:40]={q['rubric'][:40]!r}", t)

    # R06 读取指引“采用题面小节: 无” → 应退出 2（工具文档承诺“如实报错，不猜”）
    t = time.time()
    code, out, err = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', 'BJ-2025-CY-YIMO-Q1'])
    q = mdq('BJ-2025-CY-YIMO-Q1')
    rec('R06 题库标“采用题面小节: 无”时仍拿“不得当作题面”的讲评块当题面', code == 2,
        '退出 2，提示题库无可用题面', f"exit={code} stem_header={q['stem_header']!r} stem[:30]={q['stem_full'][:30]!r}", t)

    # R07 锚点可被 block_insert 唯一解析
    t = time.time()
    d = dl.open_docx(str(BOOK3))
    _, _, bhb, _ = ap.zones_of(d, prof)
    bt = [b['title'] or '' for b in bhb]
    bad = []
    for ks in ps.KIND_GROUPS.values():
        groups = {}
        for i, b in enumerate(B):
            if b['kind'] in ks:
                groups.setdefault(ps.group_key_of(b), []).append(i)
        for gk, ix in groups.items():
            last = max(ix, key=lambda i: B[i]['p_range'][0])
            n = sum(1 for u in bt if B[last]['title'] in u)
            if n != 1:
                bad.append((ps.group_label(gk)[:40], B[last]['title'], n))
    rec('R07 “考法末尾”锚点 anchor_title_contains 在 block_insert 里须恰好命中 1 块', not bad,
        '全部候选组的锚点唯一（或工具给出可用替代，如 method_end）',
        f'{len(bad)} 个组的锚点命中≠1 块，例：{bad[:3]}', t)

    # R08 题键已在本书 → 应提示（不应静默剔除）
    t = time.time()
    code, out, err = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', 'BJ-2026-HD-ERMO-Q11', '--format', 'md'])
    rec('R08 题键已在本书落位时无任何提示', ('已' in out and '落位' in out) or code != 0,
        'flags/Markdown 提示“该题键已在本书 Bxxxx 落位”', f'exit={code} md 输出未提已落位：{out[:160]!r}', t)

    # R09 原子性：--out 过守卫先写，--report 被拒 → 不应留下 .md
    t = time.time()
    mdout = SCR / 'R09.md'
    bad_rep = BOOK3.parent / 'R09_should_not_exist.json'
    code, out, err = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', 'BJ-2026-HD-ERMO-Q11',
                          '--format', 'md', '--out', str(mdout), '--report', str(bad_rep)])
    left = mdout.exists()
    if bad_rep.exists():
        bad_rep.unlink()
    rec('R09 一处写出被拒时另一输出已落盘（不留半成品）', code == 3 and not left,
        '退出 3 且不留任何输出文件', f'exit={code} md_left={left}', t)

    # R10 --report 字段：summary、题源路径+SHA
    t = time.time()
    rep = SCR / 'R10.json'
    code, out, err = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', 'BJ-2026-HD-ERMO-Q11',
                          '--report', str(rep)])
    j = json.loads(rep.read_text(encoding='utf-8'))
    txt = rep.read_text(encoding='utf-8')
    rec('R10 --report 缺 summary 与题源 MD 路径/SHA', 'summary' in j and 'BJ-2026-HD-ERMO-Q11.md' in txt,
        '共同约定 7：tool/version/mode/inputs(路径+SHA)/profile/summary/明细',
        f"顶层键={list(j)}；题源 MD 路径出现={'BJ-2026-HD-ERMO-Q11.md' in txt}", t)

    # R11 空输入/零信号 → 不应给 0 分“候选”且退出 0
    t = time.time()
    txtf = SCR / 'english.txt'
    txtf.write_text('The quick brown fox jumps over the lazy dog.\n', encoding='utf-8')
    rep = SCR / 'R11.json'
    code, out, err = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--text', str(txtf), '--kind', 'choice',
                          '--report', str(rep)])
    c = json.loads(rep.read_text(encoding='utf-8'))['results'][0]['candidates'] if rep.exists() else []
    rec('R11 与全书零重合的输入仍给出 3 个 0 分候选、退出 0', not (code == 0 and c and all(x['score'] == 0 for x in c)),
        '退出 2 或加 flag“无相似信号”', f'exit={code} scores={[x["score"] for x in c]}', t)

    # R12 --top-k 非法值
    t = time.time()
    rep = SCR / 'R12.json'
    code, out, err = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', 'BJ-2026-HD-ERMO-Q11',
                          '--top-k', '-1', '--report', str(rep)])
    n = len(json.loads(rep.read_text(encoding='utf-8'))['results'][0]['candidates']) if rep.exists() else None
    rec('R12 --top-k -1 未校验', code == 2, '退出 2（参数非法）', f'exit={code} 候选数={n}', t)

    # R13 守卫：受保护目录 / 符号链接绕行 / 冻结册
    t = time.time()
    link = SCR / 'link_to_book_dir'
    os.symlink(str(BOOK3.parent), str(link))
    code1, _, _ = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', 'BJ-2026-HD-ERMO-Q11',
                       '--report', str(link / 'R13_evil.json')])
    code2, _, _ = cli(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', 'BJ-2026-HD-ERMO-Q11',
                       '--report', str(SK.parent / 'R13_x.json')])
    code3, _, _ = cli(['--docx', str(BOOK3), '--profile', str(FROZEN), '--key', 'BJ-2026-HD-ERMO-Q11',
                       '--report', str(SCR / 'R13_frozen.json')])
    code4, _, _ = cli(['--docx', str(BOOK3), '--profile', str(FROZEN), '--key', 'BJ-2026-HD-ERMO-Q11'])
    leaked = (BOOK3.parent / 'R13_evil.json').exists() or (SK.parent / 'R13_x.json').exists() \
        or (SCR / 'R13_frozen.json').exists()
    rec('R13 守卫（符号链接绕行/Skill 目录/冻结册写出拒绝；冻结册只读可跑）',
        (code1, code2, code3) == (3, 3, 3) and code4 in (0, 1) and not leaked,
        '符号链接→3、Skill→3、冻结+写→3、冻结只读→0/1，均不落盘',
        f'codes={(code1, code2, code3, code4)} leaked={leaked}', t)

    # R14 找不到 SK → 应退出 2（配置错误）
    t = time.time()
    solo = SCR / 'solo'
    solo.mkdir()
    shutil.copy(str(TOOL), str(solo / 'placement_suggest.py'))
    env = dict(os.environ)
    env.pop('BAODIAN_SKILL_SCRIPTS', None)
    p = subprocess.run([sys.executable, str(solo / 'placement_suggest.py'), '--docx', str(BOOK3),
                        '--profile', str(PROFILE), '--key', 'BJ-2026-HD-ERMO-Q11'],
                       capture_output=True, text=True, env=env, cwd='/tmp')
    rec('R14 找不到 Skill 脚本目录时退出码', p.returncode == 2, '退出 2（配置错误）',
        f'exit={p.returncode} err={p.stderr.strip()[:80]}', t)

    # R15 十题验收：命中题的查询题型须与书中题型一致（否则是题型误判带来的伪命中）
    t = time.time()
    tr = json.loads((C / '构建' / 'placement_suggest' / 'test_results.json').read_text(encoding='utf-8'))
    spurious = []
    for row in tr['default_params_10']['rows']:
        q = mdq(row['key'])
        book_choice = set(row['kind']) == {'choice'}
        if row['hit3'] and (q['kind'] == 'choice') != book_choice:
            spurious.append((row['key'], row['kind'], q['kind'], row['rank']))
    rec('R15 十题验收里有题型误判的“命中”', not spurious, '命中题的查询题型与书中题型一致',
        f'伪命中={spurious}', t)

    # R16 SK 下无 __pycache__
    t = time.time()
    pc = [str(x) for x in SK.rglob('__pycache__')]
    rec('R16 Skill scripts 下无 __pycache__', not pc, '无', f'{pc}', t)

    # R17 vermin 3.9
    t = time.time()
    p = subprocess.run(['vermin', '-t=3.9-', '--no-tips', '--eval-annotations', '--violations',
                        str(TOOL), str(C / 'run_tests_placement_suggest.py')], capture_output=True, text=True)
    rec('R17 vermin -t=3.9- 无违规', p.returncode == 0, 'exit 0', f'exit={p.returncode} {p.stdout.strip()[-120:]}', t)

    fails = sum(1 for r in rows if r['result'] == 'FAIL')
    (HERE / 'adv_results.json').write_text(json.dumps({'tool': 'placement_suggest 对抗审查探针 r1',
                                                       'total': len(rows), 'fail': fails, 'rows': rows},
                                                      ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'\n合计 {len(rows)} 条，FAIL {fails} 条（FAIL＝被审工具不符合规格），用时 {time.time() - t0:.1f}s')
    return fails


if __name__ == '__main__':
    sys.exit(main())
