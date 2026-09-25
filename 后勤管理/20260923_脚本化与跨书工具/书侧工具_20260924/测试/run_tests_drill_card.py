#!/usr/bin/env python3
"""drill_tool.py 新增 card（题卡式单练）版式的可重跑测试脚本（流程优化线 2026-09-24 第三批；
第四批返修见文件头新增的负例④⑤⑥与 verify_drill_card.json 对应的复现片段）。

覆盖：① 选必二 r22（card，用 profile_probe 现生成的草案配置）extract 146/146、check；
      ② 推理 v7.50（card，同样现生成草案）extract 144/144、check；
      ③ 负例：临时副本里删一张 A1 卡、A2 卡去掉【解析】、A1 卡混入答案 → check 逐一抓到；
      ④ 负例：A1-006 正文全部清空（无表格的纯段落卡）→ check 报"A1 题卡正文为空或没有题干/选项
         内容"（修复 verify_drill_card.json major 3：原先 A1 正文可以整张清空都不报）；
      ⑤ 负例：A2-012 答案栏改成"CE"（合法字母 C 与非法字母 E 混在一起）→ check 报"答案栏混入
         不合法的答案字母"（修复 major 2：原先只要答案段里有一个合法字符就放行，非法字母混在合法
         字母中间查不出来）；
      ⑥ 回归断言：①②里最后一张 A1 卡（选必二 no=146、推理 no=144）的 a1.text 不得包含另一部分
         的标题/导语文字（修复 major 1：_collect_cards 原先只在离开 drill.part 两个部分时收卡，
         A1→A2 部分切换不收卡，最后一张 A1 卡会把 A2 部分的标题和导语一起吞进去）；
      ⑦ table3/paragraph 的行为不在本脚本重复验证——那部分的回归见同目录
      run_tests_drill_tool.py（已更新其中两处 card 专属断言，其余断言原样未动，已重跑全过）。

只读输入：选必二 r22、推理 v7.50（均为真实工作稿，只读，不改一个字节）。
所有输出只写 DRILL_CARD_TEST_OUT 环境变量指到的目录（未设时退回系统临时目录，保持脚本本身可在
任何会话下独立重跑）；本次返修在 scratchpad/booktools3/drill_card/ 下先跑通，见回执
fix_drill_card.json。不碰任何书稿目录、审阅入口、中央状态、协作/接管.json、题库、Skill scripts/ 目录。

用法：/usr/bin/python3 run_tests_drill_card.py
     DRILL_CARD_TEST_OUT=/path/to/scratch /usr/bin/python3 run_tests_drill_card.py
退出码：0 全部按预期；1 有用例结果与预期不符（详见打印）。
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(os.environ.get('DRILL_CARD_TEST_OUT') or (Path(tempfile.gettempdir()) / 'drill_card_test_out'))
if HERE.exists():
    shutil.rmtree(HERE)
HERE.mkdir(parents=True, exist_ok=True)
SCRIPTS = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts')
TOOL = SCRIPTS / 'drill_tool.py'
PY = '/usr/bin/python3'

XB2 = Path('/Users/wanglifei/Desktop/2026模拟题/选必二_v15.0续作_20260908/工作稿/'
           '选必二法律与生活宝典_v15.0_出版校订稿_20260908_r22.docx')
REA = Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/推理_v7.31续作_20260908/输出/'
           '选必三_逻辑与思维_推理宝典_v7.50_主观原图与评分替代条件修订工作稿_20260908.docx')
REAL_INPUTS = [XB2, REA]

FAILED = []


def sha_mtime(p):
    p = Path(p)
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest(), p.stat().st_mtime


def run(args, expect_code=None, label=''):
    t0 = time.time()
    p = subprocess.run([PY, str(TOOL)] + [str(a) for a in args], cwd=str(SCRIPTS),
                        capture_output=True, text=True)
    dt = time.time() - t0
    ok = expect_code is None or p.returncode == expect_code
    print('[%s] exit=%d (expect %s) %.1fs %s' % (label, p.returncode, expect_code, dt, 'OK' if ok else 'MISMATCH'))
    if not ok:
        FAILED.append(label)
        print('   stdout:', p.stdout.strip()[-800:])
        print('   stderr:', p.stderr.strip()[-800:])
    return {'exit': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr, 'seconds': round(dt, 2)}


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def check_eq(label, got, want):
    ok = got == want
    print('  %s: got=%r want=%r %s' % (label, got, want, 'OK' if ok else 'MISMATCH'))
    if not ok:
        FAILED.append(label)


def probe(docx, book_id):
    p = subprocess.run([PY, str(SCRIPTS / 'profile_probe.py'), '--docx', str(docx), '--book-id', book_id,
                        '--out', str(HERE / 'probe')], capture_output=True, text=True)
    print('%s profile_probe exit=%d' % (book_id, p.returncode))
    draft = HERE / 'probe' / ('%s.draft.json' % book_id)
    if not draft.exists():
        FAILED.append('%s profile_probe 未生成草案' % book_id)
        print(p.stdout[-500:], p.stderr[-500:])
        return None
    return draft


def main():
    before = {str(p): sha_mtime(p) for p in REAL_INPUTS if p.exists()}
    print('== 输入 SHA/mtime（测试前）==')
    for k, v in before.items():
        print(' ', k, v[0][:16], v[1])

    # ---------------- ① 选必二 r22（card）----------------
    draft2 = probe(XB2, 'xuanbi2')
    if draft2:
        d2 = json.loads(draft2.read_text(encoding='utf-8'))
        check_eq('选必二草案 drill.layout', d2.get('drill', {}).get('layout'), 'cards')
        rec = run(['extract', '--docx', XB2, '--out', HERE / 'xb2_items.json', '--profile', draft2,
                   '--report', HERE / 'xb2_extract.json'], 0, '选必二 r22 extract')
        items = load(HERE / 'xb2_items.json')
        check_eq('选必二 count', items['count'], 146)
        check_eq('选必二 a1_count', items['a1_count'], 146)
        check_eq('选必二 a2_count', items['a2_count'], 146)
        check_eq('选必二 a1_a2_count_mismatch', items['a1_a2_count_mismatch'], False)
        # 修复 major 1 回归：最后一张 A1 卡（按 a1.para_i 最大）不得混入 A2 部分的标题/导语文字。
        last_a1 = max((r for r in items['records'] if r.get('a1')), key=lambda r: r['a1']['para_i'])
        last_a1_text = last_a1['a1']['text'] or ''
        check_eq('选必二最后一张 A1 卡（no=%s）不含【答案】/【解析】' % last_a1['no'],
                  ('【答案】' in last_a1_text or '【解析】' in last_a1_text), False)
        check_eq('选必二最后一张 A1 卡（no=%s）不含 A2 部分标题前缀' % last_a1['no'],
                  ('A2-' in last_a1_text or '附录二' in last_a1_text), False)
        rec = run(['check', '--docx', XB2, '--profile', draft2, '--report', HERE / 'xb2_check.json'],
                   1, '选必二 r22 check')
        chk = load(HERE / 'xb2_check.json')
        check_eq('选必二 check a1/a2', (chk['summary']['a1'], chk['summary']['a2']), (146, 146))
        check_eq('选必二 check matched', chk['summary']['matched'], 146)
        check_eq('选必二 check FAIL 条数', chk['counts']['FAIL'], 1)
        if chk['findings']:
            check_eq('选必二唯一 FAIL 的规则', chk['findings'][0]['rule'], 'A2 题卡缺解析（未找到 【解析】/【逐项解析】）')
            check_eq('选必二唯一 FAIL 的编号', chk['findings'][0]['no'], '087')
        print('  选必二 r22：146/146 全配对，仅 A2-087 真实缺【解析】（真实书稿缺口，如实报告，非工具 bug）')

    # ---------------- ② 推理 v7.50（card）----------------
    draftr = probe(REA, 'reasoning')
    if draftr:
        run(['extract', '--docx', REA, '--out', HERE / 'rea_items.json', '--profile', draftr,
             '--report', HERE / 'rea_extract.json'], 0, '推理 v7.50 extract')
        ritems = load(HERE / 'rea_items.json')
        check_eq('推理 count', ritems['count'], 144)
        check_eq('推理 a1_count', ritems['a1_count'], 144)
        check_eq('推理 a2_count', ritems['a2_count'], 144)
        check_eq('推理 a1_a2_count_mismatch', ritems['a1_a2_count_mismatch'], False)
        # 修复 major 1 回归：同上，推理书最后一张 A1 卡也不得混入 A2 部分的标题/导语文字。
        rlast_a1 = max((r for r in ritems['records'] if r.get('a1')), key=lambda r: r['a1']['para_i'])
        rlast_a1_text = rlast_a1['a1']['text'] or ''
        check_eq('推理最后一张 A1 卡（no=%s）不含【答案】/【解析】/【逐项解析】' % rlast_a1['no'],
                  any(lab in rlast_a1_text for lab in ('【答案】', '【解析】', '【逐项解析】')), False)
        check_eq('推理最后一张 A1 卡（no=%s）不含 A2 部分标题前缀' % rlast_a1['no'],
                  'A2-' in rlast_a1_text, False)
        run(['check', '--docx', REA, '--profile', draftr, '--report', HERE / 'rea_check.json'],
            0, '推理 v7.50 check')
        rchk = load(HERE / 'rea_check.json')
        check_eq('推理 check a1/a2', (rchk['summary']['a1'], rchk['summary']['a2']), (144, 144))
        check_eq('推理 check FAIL 条数', rchk['counts']['FAIL'], 0)
        print('  推理 v7.50：144/144 全配对，0 FAIL（A2 侧只挑需纠正的选项落地、正确选项整段不印属书稿'
              '编排约定，check 按"A2 复述片段能否在 A1 找到"核对，不误判）')

    # ---------------- ③ 负例（选必二 r22 临时副本）----------------
    if draft2:
        sys.path.insert(0, str(SCRIPTS))
        import batch_health as bh  # noqa: E402
        import docx_lib as dl      # noqa: E402
        from profile_lib import load_profile  # noqa: E402
        from lxml import etree     # noqa: E402
        pd = load_profile(str(draft2))
        P = bh.Prof(pd)
        W = bh.W
        title_rx = re.compile(r'^(A[12])-(\d+)[｜\s]+(.*)$')

        def titles_of(items, sec):
            return [(i, it) for i, it in enumerate(items)
                    if it.get('part') in ('APPX1', 'APPX2') and it['tbl'] is None and it['text']
                    and title_rx.match(it['text']) and title_rx.match(it['text']).group(1) == sec]

        # 负例 1：删一张 A1 卡（编号 002：标题段+正文段整段移除）
        d1 = dl.open_docx(str(XB2))
        bh.walk(d1.items, P)
        a1t = titles_of(d1.items, 'A1')
        i2 = next(i for i, it in a1t if title_rx.match(it['text']).group(2) == '002')
        i3 = next(i for i, it in a1t if title_rx.match(it['text']).group(2) == '003')
        for p in d1.paras[i2:i3]:
            p.getparent().remove(p)
        out1 = HERE / 'neg_delete_a1.docx'
        dl.write_docx(d1, str(out1))
        rec = run(['check', '--docx', out1, '--profile', draft2, '--report', HERE / 'neg1_check.json'],
                   1, '负例①：删一张 A1 卡（编号 002）')
        c1 = load(HERE / 'neg1_check.json')
        rules1 = {f['rule'] for f in c1['findings']}
        check_eq('负例①命中"张数不相等"', 'A1/A2 题卡张数不相等' in rules1, True)
        check_eq('负例①命中"A2 有但 A1 缺失"', 'A2 有但 A1 缺失的题卡编号' in rules1, True)
        nos1 = next((f.get('nos') for f in c1['findings'] if f['rule'] == 'A2 有但 A1 缺失的题卡编号'), None)
        check_eq('负例①缺失编号', nos1, ['002'])

        # 负例 2：A2 卡（编号 005）去掉【解析】——把"【答案】 C。【解析】……"截断到"【答案】 C。"
        d2doc = dl.open_docx(str(XB2))
        bh.walk(d2doc.items, P)
        a2t = titles_of(d2doc.items, 'A2')
        i005 = next(i for i, it in a2t if title_rx.match(it['text']).group(2) == '005')
        ans_i = next(i for i in range(i005, i005 + 6) if '【解析】' in (d2doc.items[i]['text'] or ''))
        p2 = d2doc.paras[ans_i]
        cut_run = None
        for r in p2.findall(W + 'r'):
            t = r.find(W + 't')
            txt = (t.text or '') if t is not None else ''
            if '【解析】' in txt:
                cut_run, cutpos = r, txt.find('【解析】')
                t.text = txt[:cutpos]
                break
        remove = False
        for r in list(p2.findall(W + 'r')):
            if r is cut_run:
                remove = True
                continue
            if remove:
                p2.remove(r)
        out2 = HERE / 'neg_no_analysis.docx'
        dl.write_docx(d2doc, str(out2))
        rec = run(['check', '--docx', out2, '--profile', draft2, '--report', HERE / 'neg2_check.json'],
                   1, '负例②：A2-005 去掉【解析】')
        c2 = load(HERE / 'neg2_check.json')
        nos2 = sorted(f.get('no') for f in c2['findings'] if f['rule'] == 'A2 题卡缺解析（未找到 【解析】/【逐项解析】）')
        check_eq('负例②抓到 A2-005 缺解析（连同真实的 A2-087）', nos2, ['005', '087'])

        # 负例 3：A1 卡（编号 004）混入答案标签
        d3 = dl.open_docx(str(XB2))
        bh.walk(d3.items, P)
        a1t3 = titles_of(d3.items, 'A1')
        i004 = next(i for i, it in a1t3 if title_rx.match(it['text']).group(2) == '004')
        p3 = d3.paras[i004 + 1]
        r_new = etree.SubElement(p3, W + 'r')
        t_new = etree.SubElement(r_new, W + 't')
        t_new.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        t_new.text = '【答案】D。'
        out3 = HERE / 'neg_a1_answer.docx'
        dl.write_docx(d3, str(out3))
        rec = run(['check', '--docx', out3, '--profile', draft2, '--report', HERE / 'neg3_check.json'],
                   1, '负例③：A1-004 混入答案')
        c3 = load(HERE / 'neg3_check.json')
        hit3 = next((f for f in c3['findings'] if f['rule'] == 'A1 题卡混入答案/解析等不该出现的标签'
                     and f.get('no') == '004'), None)
        check_eq('负例③命中', hit3 is not None, True)
        if hit3:
            check_eq('负例③命中的标签', hit3.get('labels'), ['【答案】'])

        # 负例 4：A1-006 正文全部清空（这张卡没有表格，纯 5 个段落，清空后 body 应真正空）——
        # 修复 major 3：原先 check 对整张清空的 A1 卡零报告。
        d4 = dl.open_docx(str(XB2))
        bh.walk(d4.items, P)
        a1t4 = titles_of(d4.items, 'A1')
        i006 = next(i for i, it in a1t4 if title_rx.match(it['text']).group(2) == '006')
        i007 = next(i for i, it in a1t4 if title_rx.match(it['text']).group(2) == '007')
        for p in d4.paras[i006 + 1:i007]:
            for r in p.findall(W + 'r'):
                t = r.find(W + 't')
                if t is not None:
                    t.text = ''
        out4 = HERE / 'neg_empty_a1.docx'
        dl.write_docx(d4, str(out4))
        rec = run(['check', '--docx', out4, '--profile', draft2, '--report', HERE / 'neg4_check.json'],
                   1, '负例④：A1-006 正文全部清空')
        c4 = load(HERE / 'neg4_check.json')
        hit4 = next((f for f in c4['findings'] if f['rule'] == 'A1 题卡正文为空或没有题干/选项内容'
                     and f.get('no') == '006'), None)
        check_eq('负例④命中 A1-006 正文为空', hit4 is not None, True)

        # 负例 5：A2-012 答案栏"C"改成"CE"（合法字母与非法字母混写）——修复 major 2：原先只要答案段
        # 里有一个合法字符就放行，非法字母混在合法字母中间查不出来（'AE'、'CE' 这类都能骗过去）。
        d5 = dl.open_docx(str(XB2))
        bh.walk(d5.items, P)
        a2t5 = titles_of(d5.items, 'A2')
        i012 = next(i for i, it in a2t5 if title_rx.match(it['text']).group(2) == '012')
        ans_i5 = next(i for i in range(i012, i012 + 6) if '【答案】' in (d5.items[i]['text'] or ''))
        p5 = d5.paras[ans_i5]
        # 答案标签与答案字母常常各占一个 run（如'【答案】'/' C。'/'【解析】'/'……'四个 run），不能假设
        # 同一个 run 里同时有标签和字母；按 run 顺序找答案标签之后第一个含独立字母的 run 来改。
        runs5 = p5.findall(W + 'r')
        label_idx = next((k for k, r in enumerate(runs5)
                           if (r.find(W + 't') is not None and '【答案】' in (r.find(W + 't').text or ''))), None)
        hit_run = False
        if label_idx is not None:
            for r in runs5[label_idx + 1:]:
                t = r.find(W + 't')
                txt = (t.text or '') if t is not None else ''
                if ' C。' in txt:
                    t.text = txt.replace(' C。', ' CE。', 1)
                    hit_run = True
                    break
        if not hit_run:
            raise RuntimeError('负例⑤构造失败：A2-012 答案段未找到预期的 " C。" 片段，书稿写法变了，需要人工核对')
        out5 = HERE / 'neg_answer_ce.docx'
        dl.write_docx(d5, str(out5))
        rec = run(['check', '--docx', out5, '--profile', draft2, '--report', HERE / 'neg5_check.json'],
                   1, '负例⑤：A2-012 答案栏 "C" 改成 "CE"（混入非法字母 E）')
        c5 = load(HERE / 'neg5_check.json')
        hit5 = next((f for f in c5['findings'] if f['rule'] == '答案栏混入不合法的答案字母（drill.card.answer_alphabet_regex）'
                     and f.get('no') == '012'), None)
        check_eq('负例⑤命中 A2-012 答案栏混入非法字母', hit5 is not None, True)
        if hit5:
            check_eq('负例⑤命中的非法字母', hit5.get('illegal'), ['E'])

    after = {str(p): sha_mtime(p) for p in REAL_INPUTS if p.exists()}
    print('== 输入 SHA/mtime（测试后，应与测试前逐一相同）==')
    for k, v in after.items():
        same = before.get(k) == v
        print(' ', k, 'unchanged' if same else 'CHANGED!!!', v[0][:16], v[1])
        if not same:
            FAILED.append('输入文件被改动：%s' % k)

    print()
    if FAILED:
        print('全部用例：FAIL，未通过项：%s' % FAILED)
        return 1
    print('全部用例：PASS')
    return 0


if __name__ == '__main__':
    sys.exit(main())
