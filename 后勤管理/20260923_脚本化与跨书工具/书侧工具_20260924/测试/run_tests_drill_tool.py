#!/usr/bin/env python3
"""drill_tool.py 的可重跑测试脚本（流程优化线 2026-09-24；2026-09-24 返修版）。

只读输入：B3_52、B3_04（可选对照）、B2_230（冻结册，只读）、哲学 R10、选必二 r22。
所有输出只写系统临时目录（见 HERE），不碰任何书稿目录、审阅入口、中央状态、协作/接管.json、题库——
本脚本自己存放在项目的 后勤管理/.../测试/ 目录下以便留档重跑，但 HERE 不跟着 __file__ 走：drill_tool
返修后 guard_json 真的按 docx_lib.guard_write 的口径拒绝往项目目录写 json（这正是本次要修的 blocker），
所以测试输出必须落到系统临时目录，不能再假定"脚本文件在哪、输出就能写在哪"。冻结册（B2_230）需要
"写"路径的用例，用本脚本临时生成的 frozen:false 配置副本 + 输入文件的临时拷贝（避免 --docx 路径落在
冻结册登记的工作区目录下被 detect_profile 认出而按真实配置拒绝），不改真实 profiles/bixiu2.json，
也不改真实 B2_230 文件。

用法：/usr/bin/python3 run_tests_drill_tool.py
退出码：0 全部按预期；1 有用例结果与预期不符（详见打印与 RESULTS 里的 records）。
"""
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(tempfile.gettempdir()) / 'drill_tool_test_out'
if HERE.exists():
    shutil.rmtree(HERE)  # 可重跑：每次先清空自己的临时输出目录，不依赖上一次运行手动清理
HERE.mkdir(parents=True, exist_ok=True)
SCRIPTS = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts')
TOOL = SCRIPTS / 'drill_tool.py'
PY = '/usr/bin/python3'
ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')

B3_52 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/必修三政治与法治宝典_第52批_意见修改审阅稿.docx'
B2_230 = ROOT / '必修二_周六成品冲刺_20260910/工作稿/修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.docx'
PHIL = Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修四哲学续作_20260908/交付/'
            '哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx')
XB2 = Path('/Users/wanglifei/Desktop/2026模拟题/选必二_v15.0续作_20260908/工作稿/'
           '选必二法律与生活宝典_v15.0_出版校订稿_20260908_r22.docx')
REAL_INPUTS = [B3_52, B2_230, PHIL, XB2]

RESULTS = []


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
    rec = {'label': label, 'cmd': [str(a) for a in args], 'exit': p.returncode, 'expect': expect_code, 'ok': ok,
           'seconds': round(dt, 2), 'stdout': p.stdout.strip()[-2000:], 'stderr': p.stderr.strip()[-2000:]}
    RESULTS.append(rec)
    print('[%s] exit=%d (expect %s) %.1fs %s' % (label, p.returncode, expect_code, dt, 'OK' if ok else 'MISMATCH'))
    if not ok:
        print('   stdout:', p.stdout.strip()[-500:])
        print('   stderr:', p.stderr.strip()[-500:])
    return rec


def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    # 提前导入（r3 返修回归用例要用，B2_230 段落里也要用），避免重复 import。
    import sys as _sys
    _sys.path.insert(0, str(SCRIPTS))
    import docx_lib as _dl          # noqa: E402
    import batch_health as _bh      # noqa: E402
    from lxml import etree as _etree  # noqa: E402
    import drill_tool as _dt        # noqa: E402
    from profile_lib import load_profile as _load_profile  # noqa: E402
    _W = _bh.W

    before = {str(p): sha_mtime(p) for p in REAL_INPUTS if p.exists()}
    print('== 输入 SHA/mtime（测试前）==')
    for k, v in before.items():
        print(' ', k, v[0][:16], v[1])

    # ---------------- B3_52（table3，非冻结）----------------
    run(['extract', '--docx', B3_52, '--out', HERE / 'b3_52_items.json', '--report', HERE / 'b3_52_extract.json'],
        0, 'B3_52 extract')
    items = load(HERE / 'b3_52_items.json')
    assert items['count'] == 676 and items['a1_count'] == 676 and items['a2_count'] == 676, items
    assert items['non_item_rows'] == 0
    print('  B3_52 extract 676/676 non_item=0 OK')

    run(['check', '--docx', B3_52, '--report', HERE / 'b3_52_check.json'], 1, 'B3_52 check')
    chk = load(HERE / 'b3_52_check.json')
    assert chk['summary']['a1'] == 676 and chk['summary']['a2'] == 676
    src_empty_fails = [f for f in chk['findings'] if f['rule'] == '题源为空']
    print('  B3_52 check：题源为空 FAIL=%d 条（真实书稿缺口，如实报告，非工具 bug）' % len(src_empty_fails))

    sha52 = before[str(B3_52)][0]
    run(['build', '--docx', B3_52, '--items', HERE / 'b3_52_items.json', '--out', HERE / 'b3_52_build.docx',
         '--expect-sha', sha52, '--report', HERE / 'b3_52_build_report.json'], 0, 'B3_52 build round-trip')
    run(['extract', '--docx', HERE / 'b3_52_build.docx', '--out', HERE / 'b3_52_build_items.json',
         '--profile', 'bixiu3'], 0, 'B3_52 build round-trip re-extract')
    a = load(HERE / 'b3_52_items.json')['records']
    b = load(HERE / 'b3_52_build_items.json')['records']
    key = lambda r: (r['group'], r['no'], r['stem'], r['verdict'], r['error_runs'], r['correction'], r['source'])
    diffs = sum(1 for x, y in zip(a, b) if key(x) != key(y))
    print('  round-trip 内容 diff=%d（应为 0）' % diffs)
    assert diffs == 0 and len(a) == len(b) == 676
    rep = load(HERE / 'b3_52_build_report.json')
    assert rep['unchanged_check']['bad'] == [], rep['unchanged_check']
    print('  round-trip 未点名段落核对：bad=[]，touched_before=%d touched_after=%d' %
          (rep['unchanged_check']['touched_before'], rep['unchanged_check']['touched_after']))

    # ---------------- 新增 3 条题肢（1 正确 2 错误）----------------
    items2 = copy.deepcopy(load(HERE / 'b3_52_items.json'))
    new_recs = [
        {'group': 328, 'stem': '党的自我革命能够解决大党独有难题，一劳永逸消除所有风险隐患',
         'verdict': '错误', 'error_runs': ['一劳永逸消除所有风险隐患'],
         'correction': '纠正：自我革命是持续的过程，不能说“一劳永逸消除所有风险隐患”，仍需常抓不懈。',
         'source': 'drill_tool测试新增1'},
        {'group': 328, 'stem': '发展全过程人民民主是社会主义民主政治的本质属性',
         'verdict': '正确', 'error_runs': [], 'correction': None, 'source': 'drill_tool测试新增2'},
        {'group': 328, 'stem': '只要坚持依法治国，就能自动实现国家治理体系和治理能力现代化',
         'verdict': '错误', 'error_runs': ['只要坚持依法治国，就能自动实现'],
         'correction': '纠正：国家治理现代化需要多方面共同发力，不是坚持依法治国这一个条件就能自动实现的。',
         'source': 'drill_tool测试新增3'},
    ]
    items2['records'] = items2['records'] + new_recs
    (HERE / 'b3_52_items_plus3.json').write_text(json.dumps(items2, ensure_ascii=False, indent=2), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'b3_52_items_plus3.json', '--out', HERE / 'b3_52_build_plus3.docx',
         '--expect-sha', sha52, '--report', HERE / 'b3_52_build_plus3_report.json'], 0, 'B3_52 build +3 items')
    run(['check', '--docx', HERE / 'b3_52_build_plus3.docx', '--profile', 'bixiu3',
         '--report', HERE / 'b3_52_check_plus3.json'], None, 'B3_52 +3 items check')
    chk3 = load(HERE / 'b3_52_check_plus3.json')
    bh_fails = [f for f in chk3['findings'] if f['check'] == 'drill' and f['level'] == 'FAIL']
    print('  +3 条后 bh.check_drill 门 FAIL=%d（应为 0）；A1/A2=%d/%d（应为 679/679）' %
          (len(bh_fails), chk3['summary']['a1'], chk3['summary']['a2']))
    assert not bh_fails
    assert chk3['summary']['a1'] == 679 and chk3['summary']['a2'] == 679

    # ---------------- 负例：error_runs 片段不在 stem 里 ----------------
    bad1 = copy.deepcopy(items2)
    bad1['records'][-1]['error_runs'] = ['这段文字压根不在stem里']
    (HERE / 'bad_error_runs.json').write_text(json.dumps(bad1, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'bad_error_runs.json', '--out', HERE / 'bad1.docx',
         '--expect-sha', sha52], 2, '负例：error_runs 片段找不到')
    assert not (HERE / 'bad1.docx').exists()

    # ---------------- 负例：group 不是已识别的 A2 表格 ----------------
    bad2 = copy.deepcopy(items2)
    bad2['records'][-1]['group'] = 999999
    (HERE / 'bad_group.json').write_text(json.dumps(bad2, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'bad_group.json', '--out', HERE / 'bad2.docx',
         '--expect-sha', sha52], 2, '负例：group 不是已识别表格')
    assert not (HERE / 'bad2.docx').exists()

    # ---------------- 负例：verdict 不在 a2_allowed ----------------
    bad3 = copy.deepcopy(items2)
    bad3['records'][-1]['verdict'] = '不选'
    (HERE / 'bad_verdict.json').write_text(json.dumps(bad3, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'bad_verdict.json', '--out', HERE / 'bad3.docx',
         '--expect-sha', sha52], 2, '负例：verdict 非法')
    assert not (HERE / 'bad3.docx').exists()

    # ---------------- 负例：父稿 SHA 不符 ----------------
    run(['build', '--docx', B3_52, '--items', HERE / 'b3_52_items.json', '--out', HERE / 'bad4.docx',
         '--expect-sha', '0' * 64], 2, '负例：父稿 SHA 不符')
    assert not (HERE / 'bad4.docx').exists()

    # ---------------- 负例：输出落在受保护目录（审阅入口）----------------
    protected_out = ROOT / '必修三_最新Skill修订_20260913/00_必修三最新审查稿/不该出现的文件.docx'
    run(['build', '--docx', B3_52, '--items', HERE / 'b3_52_items.json', '--out', str(protected_out),
         '--expect-sha', sha52], 3, '负例：输出落在受保护目录（审阅入口）')
    assert not protected_out.exists()

    # ---------------- B2_230（冻结册）----------------
    run(['extract', '--docx', B2_230, '--out', HERE / 'b2_230_items.json', '--profile', 'bixiu2',
         '--report', HERE / 'b2_230_extract.json'], 0, 'B2_230 extract（只读）')
    items230 = load(HERE / 'b2_230_items.json')
    assert items230['count'] == 820 and items230['a1_count'] == 820 and items230['a2_count'] == 820
    print('  B2_230 extract 820/820 OK（只读）')

    run(['check', '--docx', B2_230, '--profile', 'bixiu2', '--report', HERE / 'b2_230_check.json'],
        None, 'B2_230 check（只读）')
    chk230 = load(HERE / 'b2_230_check.json')
    print('  B2_230 check counts=%s（信息性 WARN/CANDIDATE，本册已冻结不处理）' % chk230['counts'])

    # 真实配置：任何写模式立即拒绝，退出码 3，不留输出
    sha230 = before[str(B2_230)][0]
    run(['build', '--docx', B2_230, '--items', HERE / 'b2_230_items.json', '--out', HERE / 'b2_230_should_fail.docx',
         '--expect-sha', sha230], 3, 'B2_230 真实配置 build 应拒绝（冻结册）')
    assert not (HERE / 'b2_230_should_fail.docx').exists()

    # 往返测试：临时目录里一份 frozen:false 的配置副本 + 输入文件临时拷贝（避免路径被 detect_profile
    # 认成真实 bixiu2 而按真实配置拒绝——这条本身也顺带验证了“不能靠 --profile 绕过真实冻结判定”）。
    unfrozen = json.loads((SCRIPTS / 'profiles' / 'bixiu2.json').read_text(encoding='utf-8'))
    unfrozen['frozen'] = False
    unfrozen.pop('_profile_path', None)
    (HERE / 'bixiu2_unfrozen.json').write_text(json.dumps(unfrozen, ensure_ascii=False, indent=1), encoding='utf-8')
    shutil.copyfile(B2_230, HERE / 'b2_230_copy.docx')
    sha230c = sha_mtime(HERE / 'b2_230_copy.docx')[0]
    run(['build', '--docx', HERE / 'b2_230_copy.docx', '--items', HERE / 'b2_230_items.json',
         '--out', HERE / 'b2_230_build.docx', '--expect-sha', sha230c,
         '--profile', HERE / 'bixiu2_unfrozen.json', '--report', HERE / 'b2_230_build_report.json'],
        0, 'B2_230 往返（临时 frozen:false 配置副本 + 临时输入拷贝）')
    run(['extract', '--docx', HERE / 'b2_230_build.docx', '--out', HERE / 'b2_230_build_items.json',
         '--profile', HERE / 'bixiu2_unfrozen.json'], 0, 'B2_230 往返 re-extract')
    a230 = load(HERE / 'b2_230_items.json')['records']
    b230 = load(HERE / 'b2_230_build_items.json')['records']
    diffs230 = sum(1 for x, y in zip(a230, b230) if key(x) != key(y))
    print('  B2_230 往返内容 diff=%d（应为 0）' % diffs230)
    assert diffs230 == 0 and len(a230) == len(b230) == 820
    rep230 = load(HERE / 'b2_230_build_report.json')
    assert rep230['unchanged_check']['bad'] == []

    # ---- 回归 r3-4a（major 只改序号的行必须原样复制原 tr，不得被套上"N、+制表符"模板）----
    # B2_230 里有约 190 条原行的序号后面没有制表符（'N、题肢' 而不是 'N、\t题肢'）；在同组更前面插入一条
    # 新记录会让这些行整体后移一位、序号+1，若走模板重建就会被强行套上制表符，文字被改坏。
    def _tables_of(doc):
        return _dt._top_level_tables(doc.body)

    def _row_plain_text(tr, sc):
        tc = tr.findall(_W + 'tc')[sc]
        return ''.join((t.text or '') for p in tc.findall(_W + 'p') for t in p.findall(_W + 'r/' + _W + 't'))

    _b2_pd = _load_profile(str(HERE / 'bixiu2_unfrozen.json'))
    _b2c = _b2_pd.get('drill') or {}
    _sc2 = _b2c.get('stem_col', 0)
    _notab_idx = next((i for i, r in enumerate(items230['records'])
                        if not re.match(r'^\d+[、.．]\t', r['a2']['text'])), None)
    assert _notab_idx is not None, 'B2_230 应存在至少一条无制表符的原行（已知约 190 条）'
    _notab_rec = items230['records'][_notab_idx]
    _items230_notab = copy.deepcopy(items230)
    _new_ok = {'group': _notab_rec['group'], 'stem': '回归测试：插入题肢占位甲乙丙。', 'verdict': '正确',
               'error_runs': [], 'correction': None, 'source': '回归测试', 'a1': None, 'a2': None}
    _items230_notab['records'] = (_items230_notab['records'][:_notab_idx] + [_new_ok] +
                                   _items230_notab['records'][_notab_idx:])
    _items230_notab['count'] = len(_items230_notab['records'])
    (HERE / 'b2_230_notab_items.json').write_text(json.dumps(_items230_notab, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', HERE / 'b2_230_copy.docx', '--items', HERE / 'b2_230_notab_items.json',
         '--out', HERE / 'b2_230_notab_build.docx', '--expect-sha', sha230c,
         '--profile', HERE / 'bixiu2_unfrozen.json'], 0, 'r3-4a：无制表符原行前插入新题肢')
    _d_orig4a = _dl.open_docx(str(HERE / 'b2_230_copy.docx'))
    _orig_text4a = _row_plain_text(
        _tables_of(_d_orig4a)[_notab_rec['group'] - 1].findall(_W + 'tr')[_notab_rec['a2']['row']], _sc2)
    _d_new4a = _dl.open_docx(str(HERE / 'b2_230_notab_build.docx'))
    _new_text4a = _row_plain_text(
        _tables_of(_d_new4a)[_notab_rec['group'] - 1].findall(_W + 'tr')[_notab_rec['a2']['row'] + 1], _sc2)
    assert re.sub(r'^\d+', '', _orig_text4a) == re.sub(r'^\d+', '', _new_text4a), (_orig_text4a, _new_text4a)
    assert not re.match(r'^\d+[、.．]\t', _new_text4a), '不该被套上制表符（%r）' % _new_text4a
    print('  B2_230：无制表符原行只被改序号，分隔符/文字不变（修复 major 4a）')

    # ---- 回归 r3-4b（major 题干与纠正同段的模板组：插入新错误条目不应再一律 Abort(2)）----
    _tabs230_orig = _tables_of(_d_orig4a)
    _combined_group = None
    for _g in sorted({r['group'] for r in items230['records'] if r['verdict'] == '错误'}):
        _first_err = next(r for r in items230['records'] if r['group'] == _g and r['verdict'] == '错误')
        _tc0 = _tabs230_orig[_g - 1].findall(_W + 'tr')[_first_err['a2']['row']].findall(_W + 'tc')[_sc2]
        if len(_tc0.findall(_W + 'p')) < 2:
            _combined_group = _g
            break
    assert _combined_group is not None, 'B2_230 应存在题干与纠正同段的模板组（已知 869/870）'
    _items230_combo = copy.deepcopy(items230)
    _stem_combo = '回归测试：插入组内的错误条目占位丙丁戊。'
    _s_combo = _stem_combo.find('丙丁戊')
    _new_err = {'group': _combined_group, 'stem': _stem_combo, 'verdict': '错误',
                'error_runs': [{'text': '丙丁戊', 'start': _s_combo, 'end': _s_combo + 3}],
                'correction': '纠正：回归测试占位改正。', 'source': '回归测试', 'a1': None, 'a2': None}
    _idx_g = next(i for i, r in enumerate(_items230_combo['records']) if r['group'] == _combined_group)
    _items230_combo['records'] = (_items230_combo['records'][:_idx_g] + [_new_err] +
                                   _items230_combo['records'][_idx_g:])
    _items230_combo['count'] = len(_items230_combo['records'])
    (HERE / 'b2_230_combo_items.json').write_text(json.dumps(_items230_combo, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', HERE / 'b2_230_copy.docx', '--items', HERE / 'b2_230_combo_items.json',
         '--out', HERE / 'b2_230_combo_build.docx', '--expect-sha', sha230c,
         '--profile', HERE / 'bixiu2_unfrozen.json'], 0,
        'r3-4b：题干与纠正同段的模板组插入新错误条目（修复 major 4b）')
    print('  B2_230：题干与纠正同段模板下插入新错误条目，build 不再 Abort(2)（修复 major 4b）')

    # ---------------- 哲学 R10（paragraph，无正式配置，用 profile_probe 草案）----------------
    p = subprocess.run([PY, str(SCRIPTS / 'profile_probe.py'), '--docx', str(PHIL), '--book-id', 'philosophy',
                        '--out', str(HERE / 'probe')], capture_output=True, text=True)
    print('philosophy profile_probe exit=%d: %s' % (p.returncode, p.stdout.strip().splitlines()[0] if p.stdout else p.stderr[:300]))
    draft = HERE / 'probe' / 'philosophy.draft.json'
    if draft.exists():
        run(['extract', '--docx', PHIL, '--out', HERE / 'philosophy_items.json', '--profile', draft,
             '--report', HERE / 'philosophy_extract.json'], 0, '哲学 R10 extract（草案配置）')
        pit = load(HERE / 'philosophy_items.json')
        print('  哲学 R10：layout=%s count=%d a1=%d a2=%d non_item_rows=%d（规格提示约 645/645，草案未经确认，'
              '本工具照实记录，不强行凑数）' % (pit['layout'], pit['count'], pit['a1_count'], pit['a2_count'], pit['non_item_rows']))
        run(['check', '--docx', PHIL, '--profile', draft, '--report', HERE / 'philosophy_check.json'],
            None, '哲学 R10 check（草案配置）')
    else:
        print('  哲学 R10：profile_probe 没能生成草案，如实跳过（草案生成失败原因见 probe 输出）')

    # ---------------- 选必二 r22（card，无正式配置；2026-09-24 第三批：card 的 extract/check 真正实现）----------------
    p = subprocess.run([PY, str(SCRIPTS / 'profile_probe.py'), '--docx', str(XB2), '--book-id', 'xuanbi2',
                        '--out', str(HERE / 'probe')], capture_output=True, text=True)
    print('选必二 profile_probe exit=%d: %s' % (p.returncode, p.stdout.strip().splitlines()[0] if p.stdout else p.stderr[:300]))
    draft2 = HERE / 'probe' / 'xuanbi2.draft.json'
    if draft2.exists():
        d2 = json.loads(draft2.read_text(encoding='utf-8'))
        print('  选必二草案 drill.layout=%r（card 题卡版式）' % (d2.get('drill', {}).get('layout')))
        run(['extract', '--docx', XB2, '--out', HERE / 'xuanbi2_items.json', '--profile', draft2,
             '--report', HERE / 'xuanbi2_extract.json'], 0,
            '选必二 r22 extract（card 版式，2026-09-24 第三批新增支持，不再一律拒绝）')
        xb2_items = load(HERE / 'xuanbi2_items.json')
        assert xb2_items['count'] == 146 and xb2_items['a1_count'] == 146 and xb2_items['a2_count'] == 146, xb2_items
        print('  选必二 r22 extract 146/146 OK（card 版式，drill.part=["APPX1","APPX2"] 靠 A1-/A2- 标题前缀识别）')
        run(['check', '--docx', XB2, '--profile', draft2, '--report', HERE / 'xuanbi2_check.json'],
            1, '选必二 r22 check（card 版式）')
        chk_xb2 = load(HERE / 'xuanbi2_check.json')
        assert chk_xb2['summary']['a1'] == 146 and chk_xb2['summary']['a2'] == 146
        assert chk_xb2['counts']['FAIL'] == 1
        assert chk_xb2['findings'][0]['rule'] == 'A2 题卡缺解析（未找到 【解析】/【逐项解析】）'
        assert chk_xb2['findings'][0]['no'] == '087'
        print('  选必二 r22 check：146/146 全配对，仅 A2-087 真实缺【解析】（真实书稿缺口，如实报告，非工具 bug）')

    # =====================================================================
    # 返修回归用例（fix_drill_tool 2026-09-24，对应 verify_drill_tool.json 的 blocker/major）
    # =====================================================================
    print('\n== 返修回归用例 ==')

    # ---- 回归 1（blocker guard_json）：受保护根/冻结册目录一律拒绝，只放行临时目录与 …/构建/ ----
    _pd52 = _load_profile('bixiu3')
    _guard_cases = {
        '审阅入口': ROOT / '00_必修三最新审查稿' / '__回归探针不应落地__.json',
        '协作根': ROOT / '必修三_最新Skill修订_20260913/协作/__回归探针不应落地__.json',
        '工作区根': ROOT / '必修三_最新Skill修订_20260913/__回归探针不应落地__.json',
        'GaokaoPolitics续作目录': Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/__回归探针不应落地__.json'),
        'Skill_scripts目录': SCRIPTS / '__回归探针不应落地__.json',
        '项目根': ROOT / '__回归探针不应落地__.json',
    }
    for label, path in _guard_cases.items():
        try:
            _dt.guard_json(str(path), _pd52, [])
            print('  [BUG] guard_json 未拒绝：%s -> %s' % (label, path))
            assert False, 'guard_json 应拒绝 %s' % label
        except _dt.Abort as e:
            assert e.code in (2, 3), (label, e.code, str(e))
            print('  guard_json 正确拒绝 %s：exit=%d' % (label, e.code))
        assert not path.exists(), '回归探针不应真的落地：%s' % path
    _allowed = HERE / 'guard_probe_allowed.json'
    out_allowed = _dt.guard_json(str(_allowed), _pd52, [])
    print('  guard_json 正确放行本工具自己的临时目录：%s' % out_allowed)

    # ---- 回归 2/3/4（blocker 金标准往返 + major stem/source 不做 norm + error_runs 偏移）----
    # 严格往返：逐段原文（不经 bh.norm）+ run 颜色序列 + w:pPr 的 C14N 全部相同，不是"聚合字段 0 差异"。
    def _run_colors(p):
        out = []
        for r in p.findall(_W + 'r'):
            rpr = r.find(_W + 'rPr')
            color = None
            if rpr is not None:
                cel = rpr.find(_W + 'color')
                color = cel.get(_W + 'val') if cel is not None else None
            texts = [ch.text or '' if ch.tag == _W + 't' else ('\t' if ch.tag == _W + 'tab' else '') for ch in r]
            out.append((''.join(texts), color))
        return out

    def _ppr_c14n(p):
        ppr = p.find(_W + 'pPr')
        return b'' if ppr is None else _etree.tostring(ppr, method='c14n')

    def strict_roundtrip(a_path, b_path, label):
        da = _dl.open_docx(str(a_path))
        db = _dl.open_docx(str(b_path))
        assert len(da.paras) == len(db.paras), (label, len(da.paras), len(db.paras))
        text_diff = color_diff = ppr_diff = 0
        for pa, pb in zip(da.paras, db.paras):
            if _dl.para_text(pa) != _dl.para_text(pb):
                text_diff += 1
            if _run_colors(pa) != _run_colors(pb):
                color_diff += 1
            if _ppr_c14n(pa) != _ppr_c14n(pb):
                ppr_diff += 1
        print('  %s 严格往返：text_diff=%d color_diff=%d ppr_diff=%d（应全为 0）' %
              (label, text_diff, color_diff, ppr_diff))
        assert text_diff == 0 and color_diff == 0 and ppr_diff == 0, (label, text_diff, color_diff, ppr_diff)

    strict_roundtrip(B3_52, HERE / 'b3_52_build.docx', 'B3_52')
    strict_roundtrip(HERE / 'b2_230_copy.docx', HERE / 'b2_230_build.docx', 'B2_230')

    # error_runs 现在带偏移，直接核对第一条真实错误记录的偏移与文字一致
    _b3items = load(HERE / 'b3_52_items.json')
    _err_recs = [r for r in _b3items['records'] if r['verdict'] == '错误' and r['error_runs']]
    assert _err_recs, '应至少有一条错误条目带 error_runs'
    for _seg in _err_recs[0]['error_runs']:
        assert isinstance(_seg, dict) and 'start' in _seg and 'end' in _seg, _seg
        _stem = _err_recs[0]['stem']
        assert _stem[_seg['start']:_seg['end']] == _seg['text'], (_seg, _stem)
    print('  error_runs 携带 start/end 偏移，且与 stem 切片一致（修复 major 4）')

    # ---- 回归 5（major 非条目行不许悄悄删）----
    _mut_src = shutil.copyfile(B3_52, HERE / 'b3_52_mut_header.docx')
    _dmut = _dl.open_docx(str(_mut_src))
    _tables = []

    def _rec_tbl(el):
        for ch in el:
            if ch.tag == _W + 'tbl':
                _tables.append(ch)
            elif ch.tag in (_W + 'sdt', _W + 'sdtContent', _W + 'customXml', _W + 'smartTag'):
                _rec_tbl(ch)
    _rec_tbl(_dmut.body)
    _tbl328 = _tables[328 - 1]
    _hdr = copy.deepcopy(_tbl328.findall(_W + 'tr')[0])
    for _tc, _txt in zip(_hdr.findall(_W + 'tc'), ['题肢', '判断', '题源']):
        _ps = _tc.findall(_W + 'p')
        _p0 = _ps[0]
        for _r in _p0.findall(_W + 'r'):
            _p0.remove(_r)
        for _extra in _ps[1:]:
            _extra.getparent().remove(_extra)
        _r = _etree.SubElement(_p0, _W + 'r')
        _t = _etree.SubElement(_r, _W + 't')
        _t.text = _txt
    _tbl328.insert(0, _hdr)
    _final_mut = _dl.write_docx(_dmut, str(HERE / 'b3_52_mut_header.docx'))
    run(['extract', '--docx', HERE / 'b3_52_mut_header.docx', '--out', HERE / 'mut_items.json', '--profile', 'bixiu3'],
        0, '插入表头行后 extract（a1/a2 条数未变，退出 0，但如实报告 non_item_rows=1 供 build 把关）')
    _mut_items = load(HERE / 'mut_items.json')
    assert _mut_items['non_item_rows'] == 1 and _mut_items['non_item_row_details'], _mut_items['non_item_row_details']
    run(['build', '--docx', HERE / 'b3_52_mut_header.docx', '--items', HERE / 'mut_items.json',
         '--out', HERE / 'mut_build.docx', '--expect-sha', _final_mut['sha256'], '--profile', 'bixiu3'],
        2, '插入表头行后 build 必须中止（不许悄悄删非条目行）')
    assert not (HERE / 'mut_build.docx').exists()
    print('  非条目行（表头）插入后：extract 报出、build 中止且不留输出（修复 major 5）')

    # ---- 回归 6（major A1/A2 条数不一致不再静默截断）----
    _mut_a1 = shutil.copyfile(B3_52, HERE / 'b3_52_mut_a1_short.docx')
    _da1 = _dl.open_docx(str(_mut_a1))
    _tables2 = []
    _rec_tbl2 = _rec_tbl
    _tables.clear()
    _rec_tbl(_da1.body)
    _tbl308 = _tables[308 - 1]  # 与 A2 表 328 配对的 A1 表
    _a1_trs = _tbl308.findall(_W + 'tr')
    _tbl308.remove(_a1_trs[-1])
    _final_a1 = _dl.write_docx(_da1, str(HERE / 'b3_52_mut_a1_short.docx'))
    rec_mm = run(['extract', '--docx', HERE / 'b3_52_mut_a1_short.docx', '--out', HERE / 'mm_items.json', '--profile', 'bixiu3'],
                 1, 'A1 少一行后 extract（a1_a2_count_mismatch，退出 1，仍按 A2 全量输出）')
    _mm = load(HERE / 'mm_items.json')
    assert _mm['a1_a2_count_mismatch'] is True and _mm['a1_count'] != _mm['a2_count']
    assert len(_mm['records']) == _mm['a2_count'], 'records 应按 A2 全量输出，不截断'
    assert any(r['a1'] is None for r in _mm['records']), '缺 A1 的那条应 a1=null，不是被丢弃'
    run(['build', '--docx', HERE / 'b3_52_mut_a1_short.docx', '--items', HERE / 'mm_items.json',
         '--out', HERE / 'mm_build.docx', '--expect-sha', _final_a1['sha256'], '--profile', 'bixiu3'],
        2, 'a1_a2_count_mismatch=true 的 items 喂给 build 必须拒绝')
    assert not (HERE / 'mm_build.docx').exists()
    print('  A1/A2 条数不一致：extract 全量输出+非零退出，build 拒绝使用（修复 major 6）')

    # ---- 回归 7（major 半成品：--report 路径不合规时不留主输出）----
    # 修复 minor（退出码统一）：guard_json 里 dl.GuardError 一律 Abort(3)（规格一·6："3 拒绝写出（守卫……）"），
    # 不再按消息文字猜"已存在非本工具产物"该判 2 还是判 3——这两种都是 guard_write 的守卫拒绝，统一为 3。
    (HERE / 'not_owned.json').write_text('{"foo":1}', encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'b3_52_items.json', '--out', HERE / 'half_build.docx',
         '--expect-sha', sha52, '--report', HERE / 'not_owned.json', '--profile', 'bixiu3'],
        3, '--report 目标已存在且非本工具产物时 build 不留 .docx（修复 minor：guard 统一退出码 3）')
    assert not (HERE / 'half_build.docx').exists()
    run(['extract', '--docx', B3_52, '--out', HERE / 'half_extract.json', '--report', HERE / 'half_extract.txt',
         '--profile', 'bixiu3'], 3, '--report 后缀不是 .json 时 extract 不留 items.json（修复 minor：guard 统一退出码 3）')
    assert not (HERE / 'half_extract.json').exists()
    print('  --report 路径不合规：extract/build 都不留主输出，guard 拒绝统一退出码 3（修复 major 7 / minor）')

    # ---- 回归 8（major check 补齐：序号连续、A1/A2 题干逐字一致、分组标签）----
    _F1 = _bh.Findings()
    _A2_skip = [{'no': '1', 'stem': '甲' * 30, 'it': None}, {'no': '2', 'stem': '甲' * 30, 'it': None},
                {'no': '4', 'stem': '甲' * 30, 'it': None}]
    _A1_skip = [dict(x) for x in _A2_skip]
    _dt._check_seq_and_stems(_A1_skip, _A2_skip, _F1)
    assert any('连续' in f['rule'] for f in _F1.items), _F1.items
    _F2_ = _bh.Findings()
    _A2_tail = [{'no': '1', 'stem': '甲乙丙丁' * 10 + '尾巴A', 'it': None}]
    _A1_tail = [{'no': '1', 'stem': '甲乙丙丁' * 10 + '尾巴B', 'it': None}]
    _dt._check_seq_and_stems(_A1_tail, _A2_tail, _F2_)
    assert any('第 20 字之后' in f['rule'] for f in _F2_.items), _F2_.items
    print('  check 新增：序号跳号、A1/A2 题干第 20 字后不一致都能抓到（修复 major 8）')

    # ---- 回归 r3-5（major --admission 拆成 decision / execution 两种用法，不再自相矛盾）----
    # decision 模式：核"决策文件本身完整、格式对"，在决策针对的那版父稿上跑；exclude 的条目此刻还在
    # 书稿里是正常状态，不该报 FAIL（这正是上一轮"决策含 exclude 时永远不能 PASS"的 bug）。
    _cand_ids = ['%s:%s' % (r['group'], r['no']) for r in _b3items['records']]
    _exclude_ids = set(_cand_ids[:3])
    _dec_records = [
        {'old_id': cid, 'statement': r['stem'], 'source': r.get('source', ''),
         'action': ('exclude' if cid in _exclude_ids else 'retain'), 'reason': '回归测试'}
        for cid, r in zip(_cand_ids, _b3items['records'])]
    _decision_doc = {'input_sha256': sha52, 'records': _dec_records}
    (HERE / 'r3_admission_decision.json').write_text(json.dumps(_decision_doc, ensure_ascii=False), encoding='utf-8')
    run(['check', '--docx', B3_52, '--admission', HERE / 'r3_admission_decision.json',
         '--report', HERE / 'r3_admission_decision_report.json', '--profile', 'bixiu3'],
        None, 'r3-5 decision 模式：在父稿上核决策完整性')
    _dec_rep = load(HERE / 'r3_admission_decision_report.json')
    assert _dec_rep['admission']['status'] == 'pass' and _dec_rep['admission']['mode'] == 'decision', _dec_rep['admission']
    assert _dec_rep['admission']['excluded_count'] == 3
    _exclude_still_fails = [f for f in _dec_rep['findings'] if '排除' in f['rule']]
    assert not _exclude_still_fails, ('decision 模式不该因为 exclude 条目还在书里就报 FAIL', _exclude_still_fails)
    print('  --admission-mode decision（默认）：全部有裁决→pass，exclude 仍在父稿里不算 FAIL（修复 major 5）')

    _wrong_sha_dec = dict(_decision_doc, input_sha256='0' * 64)
    (HERE / 'r3_admission_wrong_sha.json').write_text(json.dumps(_wrong_sha_dec, ensure_ascii=False), encoding='utf-8')
    run(['check', '--docx', B3_52, '--admission', HERE / 'r3_admission_wrong_sha.json',
         '--report', HERE / 'r3_admission_wrong_sha_report.json', '--profile', 'bixiu3'],
        None, 'r3-5 decision 模式 input_sha256 不符仍应 fail')
    _wsha_rep = load(HERE / 'r3_admission_wrong_sha_report.json')
    assert _wsha_rep['admission']['status'] == 'fail' and _wsha_rep['admission'].get('error') == 'input_sha256_mismatch'

    # execution 模式：先真的按决策删掉 exclude 的 3 条，生成候选稿，再用稳定 id（题干哈希）核执行结果。
    _exec_items = copy.deepcopy(_b3items)
    _exec_items['records'] = [r for r in _exec_items['records']
                               if '%s:%s' % (r['group'], r['no']) not in _exclude_ids]
    _exec_items['count'] = len(_exec_items['records'])
    (HERE / 'r3_admission_exec_items.json').write_text(json.dumps(_exec_items, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'r3_admission_exec_items.json',
         '--out', HERE / 'r3_admission_exec_build.docx', '--expect-sha', sha52, '--profile', 'bixiu3'],
        0, 'r3-5：按决策删掉 3 条 exclude 生成候选稿')
    run(['check', '--docx', HERE / 'r3_admission_exec_build.docx', '--admission', HERE / 'r3_admission_decision.json',
         '--admission-mode', 'execution', '--report', HERE / 'r3_admission_exec_report.json', '--profile', 'bixiu3'],
        None, 'r3-5 execution 模式：在执行后的候选稿上核对')
    _exec_rep = load(HERE / 'r3_admission_exec_report.json')
    assert _exec_rep['admission']['status'] == 'pass' and _exec_rep['admission']['mode'] == 'execution', _exec_rep['admission']
    assert _exec_rep['admission']['still_excluded'] == 0 and _exec_rep['admission']['missing_retained'] == 0
    print('  --admission-mode execution：候选稿上 retained=书内、excluded 全部不在 → pass（修复 major 5）')

    run(['check', '--docx', B3_52, '--admission', HERE / 'r3_admission_decision.json',
         '--admission-mode', 'execution', '--report', HERE / 'r3_admission_exec_on_parent.json', '--profile', 'bixiu3'],
        None, 'r3-5 execution 模式在未执行的父稿上核对，应 fail')
    _exec_parent_rep = load(HERE / 'r3_admission_exec_on_parent.json')
    assert _exec_parent_rep['admission']['status'] == 'fail' and _exec_parent_rep['admission']['still_excluded'] == 3
    print('  --admission-mode execution 在未执行的父稿上正确报 fail（still_excluded=3，不再用位置性 group:no）（修复 major 5）')

    # ---- 回归 minor（verdict=正确 却带 correction/error_runs 必须拒绝，不静默丢弃）----
    _bad_ok = copy.deepcopy(_b3items)
    _bad_ok['records'][-1]['verdict'] = '正确'
    _bad_ok['records'][-1]['correction'] = '纠正：不该有这个'
    (HERE / 'bad_ok_with_correction.json').write_text(json.dumps(_bad_ok, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'bad_ok_with_correction.json', '--out', HERE / 'bad_ok.docx',
         '--expect-sha', sha52, '--profile', 'bixiu3'], 2, '负例：verdict=正确 却带 correction')
    assert not (HERE / 'bad_ok.docx').exists()

    # ---- 回归 minor（items.source_sha256 与父稿不符默认拒绝，--allow-rebase 放行）----
    _fake_sha_items = copy.deepcopy(_b3items)
    _fake_sha_items['source_sha256'] = 'deadbeef' * 8
    (HERE / 'items_fake_sha.json').write_text(json.dumps(_fake_sha_items, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'items_fake_sha.json', '--out', HERE / 'bad_sha.docx',
         '--expect-sha', sha52, '--profile', 'bixiu3'], 2, '负例：items.source_sha256 与父稿不符且未加 --allow-rebase')
    assert not (HERE / 'bad_sha.docx').exists()
    run(['build', '--docx', B3_52, '--items', HERE / 'items_fake_sha.json', '--out', HERE / 'ok_sha.docx',
         '--expect-sha', sha52, '--profile', 'bixiu3', '--allow-rebase'], 0, '--allow-rebase 放行 source_sha256 不符')
    assert (HERE / 'ok_sha.docx').exists()
    print('  verdict=正确 带 correction 拒绝；items.source_sha256 不符默认拒绝、--allow-rebase 放行（修复 minor）')

    # ---- 回归 minor（写后单练门只拦"新增" FAIL，退出码 1，且不留输出）----
    _missing_red = copy.deepcopy(_b3items)
    _missing_red['records'].append({'group': 328, 'stem': '回归测试用缺红占位题肢文本内容',
                                     'verdict': '错误', 'error_runs': [], 'correction': '纠正：占位。', 'source': '回归测试'})
    (HERE / 'items_missing_red.json').write_text(json.dumps(_missing_red, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'items_missing_red.json', '--out', HERE / 'missing_red.docx',
         '--expect-sha', sha52, '--profile', 'bixiu3'], 1, '新增条目缺红：写后体检新增 FAIL，退出码应为 1')
    assert not (HERE / 'missing_red.docx').exists()
    print('  写后单练门新增 FAIL：退出码 1、不留输出（修复 minor）')

    # ---- 回归 r3-2（major error_runs 偏移重叠必须 Abort(2)，不得把重叠部分写两遍）----
    try:
        _dt._resolve_error_run_offsets('T', '一二三四五六七八', [{'text': '二三四', 'start': 1, 'end': 4},
                                                               {'text': '三四五', 'start': 2, 'end': 5}])
        assert False, 'r3-2：重叠的 error_runs 应该 Abort(2)'
    except _dt.Abort as _e2:
        assert _e2.code == 2 and '重叠' in str(_e2), str(_e2)
    print('  error_runs 片段重叠被拒绝，不再重复写字（修复 major 2）')

    # ---- 回归 r3-1（major 写后单练门"新增 FAIL"识别：基线键不能是 (rule, None)）----
    # 父稿先破坏出一条真实的 "A2 错误行缺绿色纠正" FAIL（清掉某条纠正段落的绿色），确认基线确实有这条
    # FAIL；再新增一条题干不同、但触发同一规则的坏条目——旧代码的基线键是 (rule, f.get('text'))，
    # 而 bh.Findings 记的字段叫 'excerpt' 不叫 'text'，所以键实际上是 (rule, None)，父稿只要有一条同规则
    # FAIL，新造的同规则 FAIL 就会被一并放行。
    def _iter_tables(el, out):
        for ch in el:
            if ch.tag == _W + 'tbl':
                out.append(ch)
            elif ch.tag in (_W + 'sdt', _W + 'sdtContent', _W + 'customXml', _W + 'smartTag'):
                _iter_tables(ch, out)

    _d_pf = _dl.open_docx(str(B3_52))
    _tabs_pf = []
    _iter_tables(_d_pf.body, _tabs_pf)
    _err_rec0 = next(r for r in _b3items['records'] if r['verdict'] == '错误' and r.get('correction'))
    _pf_tc = _tabs_pf[_err_rec0['group'] - 1].findall(_W + 'tr')[_err_rec0['a2']['row']].findall(_W + 'tc')[0]
    _pf_ps = _pf_tc.findall(_W + 'p')
    assert len(_pf_ps) >= 2, 'r3-1 需要一条纠正在独立段落的记录做基线破坏'
    for _r in _pf_ps[1].findall(_W + 'r'):
        _rpr = _r.find(_W + 'rPr')
        _cel = _rpr.find(_W + 'color') if _rpr is not None else None
        if _cel is not None:
            _cel.set(_W + 'val', '000000')
    _final_pf = _dl.write_docx(_d_pf, str(HERE / 'r3_parentfail.docx'))
    run(['check', '--docx', HERE / 'r3_parentfail.docx', '--profile', 'bixiu3',
         '--report', HERE / 'r3_parentfail_check.json'], None, 'r3-1 父稿破坏基线')
    _pf_chk = load(HERE / 'r3_parentfail_check.json')
    assert any(f['rule'] == 'A2 错误行缺绿色“纠正”' for f in _pf_chk['findings']), _pf_chk['findings']

    _items_pf = copy.deepcopy(_b3items)
    _items_pf['source_sha256'] = _final_pf['sha256']
    _stem_new_bad = '回归测试新增错误题肢：甲机关是乙机关的派出机构'
    _s2 = _stem_new_bad.find('乙机关')
    _items_pf['records'].append({'group': _err_rec0['group'], 'stem': _stem_new_bad, 'verdict': '错误',
                                  'error_runs': [{'text': '乙机关', 'start': _s2, 'end': _s2 + 3}],
                                  'correction': None, 'source': '回归测试', 'a1': None, 'a2': None})
    _items_pf['count'] += 1
    (HERE / 'r3_parentfail_items.json').write_text(json.dumps(_items_pf, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', HERE / 'r3_parentfail.docx', '--items', HERE / 'r3_parentfail_items.json',
         '--out', HERE / 'r3_parentfail_build.docx', '--expect-sha', _final_pf['sha256'], '--profile', 'bixiu3'],
        1, 'r3-1：父稿已有同规则 FAIL 时，新增同规则 FAIL 仍必须被拦')
    assert not (HERE / 'r3_parentfail_build.docx').exists()
    print('  写后单练门"新增 FAIL"改用内容 key（去序号+norm），不再被父稿同规则旧 FAIL 掩盖（修复 major 1）')

    # ---- 回归 r3-3（major A1 必须由 A2 派生：A1 漂移不能被当"未改动"原样保留）----
    _pd3 = _load_profile('bixiu3')
    _c3 = _pd3.get('drill') or {}
    _ac3 = _c3.get('answer_col', 1)
    _d_a1d = _dl.open_docx(str(B3_52))
    _tabs_a1d = []
    _iter_tables(_d_a1d.body, _tabs_a1d)
    _rec0 = _b3items['records'][0]
    _ans_tc0 = _tabs_a1d[_rec0['a1']['table'] - 1].findall(_W + 'tr')[_rec0['a1']['row']].findall(_W + 'tc')[_ac3]
    _ans_p0 = _ans_tc0.findall(_W + 'p')[0]
    for _r in _ans_p0.findall(_W + 'r'):
        _ans_p0.remove(_r)
    _r_new = _etree.SubElement(_ans_p0, _W + 'r')
    _t_new = _etree.SubElement(_r_new, _W + 't')
    _t_new.text = '错误'
    _final_a1d = _dl.write_docx(_d_a1d, str(HERE / 'r3_a1_drift.docx'))
    run(['build', '--docx', HERE / 'r3_a1_drift.docx', '--items', HERE / 'b3_52_items.json',
         '--out', HERE / 'r3_a1_drift_build.docx', '--expect-sha', _final_a1d['sha256'], '--profile', 'bixiu3',
         '--allow-rebase'],  # items 是从原始 B3_52 抽的，source_sha256 与只改了 A1 答案栏的这份父稿不同
        0, 'r3-3：A1 判断栏被填答案，build 应重建 A1，不得原样保留')
    run(['check', '--docx', HERE / 'r3_a1_drift_build.docx', '--profile', 'bixiu3',
         '--report', HERE / 'r3_a1_drift_check.json'], None, 'r3-3 核对生成结果')
    _a1d_chk = load(HERE / 'r3_a1_drift_check.json')
    assert not any(f['rule'] == 'A1 判断栏不是空括号' for f in _a1d_chk['findings']), _a1d_chk['findings']
    print('  A1 判断栏漂移不会被原样保留，build 会重新由 A2 派生 A1（修复 major 3）')

    # ---- 回归 r3-6（major paragraph/card build 拒绝信息要说明"功能未实现"并列出所需配置字段）----
    if draft.exists():
        rec_build_phil = run(['build', '--docx', PHIL, '--items', '/nonexistent_items_for_test.json',
                               '--out', HERE / 'philosophy_build_reject.docx', '--profile', draft],
                              2, 'r3-6：paragraph 版式 build 拒绝，且说明未实现＋所需配置')
        assert '功能未实现' in rec_build_phil['stderr'] and 'item_styles' in rec_build_phil['stderr']
        assert not (HERE / 'philosophy_build_reject.docx').exists()
    if draft2.exists():
        rec_build_xb2 = run(['build', '--docx', XB2, '--items', '/nonexistent_items_for_test.json',
                              '--out', HERE / 'xuanbi2_build_reject.docx', '--profile', draft2],
                             2, 'r3-6：card 版式 build 拒绝（extract/check 已实现，build 仍未实现），且列出所需配置字段')
        assert '功能未实现' in rec_build_xb2['stderr'] and 'build_template' in rec_build_xb2['stderr']
        assert not (HERE / 'xuanbi2_build_reject.docx').exists()
    print('  paragraph/card build 拒绝信息区分"功能未实现"并列出所需配置字段（修复 major 6）')

    # ---- 回归 r3-7（major --report 不得覆盖已存在的 items.json，即便 schema 匹配）----
    _victim_items = HERE / 'r3_victim_items.json'
    shutil.copyfile(HERE / 'b3_52_items.json', _victim_items)
    _victim_before = sha_mtime(_victim_items)
    run(['check', '--docx', B3_52, '--profile', 'bixiu3', '--report', _victim_items], 3,
        'r3-7：--report 不得覆盖已存在的 items.json')
    assert sha_mtime(_victim_items) == _victim_before, 'items.json 被 --report 覆盖了！'
    print('  --report 不会覆盖已存在的 items.json（修复 major 7）')

    # =====================================================================
    # 第五轮返修回归用例（fix5_drill_tool 2026-09-24，对应 final_drill_tool.json 的 major 1/2/3、minor）
    # =====================================================================
    print('\n== 第五轮返修回归用例 ==')

    def _tbls(doc):
        out = []

        def _rc(el):
            for ch in el:
                if ch.tag == _W + 'tbl':
                    out.append(ch)
                elif ch.tag in (_W + 'sdt', _W + 'sdtContent', _W + 'customXml', _W + 'smartTag'):
                    _rc(ch)
        _rc(doc.body)
        return out

    # ---- 回归 fix5-1（major 1：写后"新增 FAIL"基线键必须能区分表级 FAIL 的对象，不能退化成 (rule, None)）----
    # B2_230 配置了 each_table_has_both=true：先把 G1 全部"错误"行删掉（G1 只剩"正确"，触发一条没有
    # excerpt 的表级 FAIL"A2 表内正误不齐" table=G1），再把 G2 的全部"错误"行也删掉（G2 新造同规则、
    # 不同 table 的 FAIL）。旧版基线键退化成 (rule, '')，G1 的旧 FAIL 会掩盖 G2 的新 FAIL；修复后必须
    # 按 table 等判定字段区分，build 退出码应为 1、不留输出。
    _groups230 = []
    for _r in items230['records']:
        if _r['group'] not in _groups230:
            _groups230.append(_r['group'])
    _G1, _G2 = _groups230[0], _groups230[1]
    _g1_err = [r for r in items230['records'] if r['group'] == _G1 and r['verdict'] == '错误']
    assert _g1_err, 'B2_230 第一组应有错误条目'
    _d_g1 = _dl.open_docx(str(HERE / 'b2_230_copy.docx'))
    _tabs_g1 = _tbls(_d_g1)
    _pairs_g1 = ([(r['a2']['table'], r['a2']['row']) for r in _g1_err] +
                 [(r['a1']['table'], r['a1']['row']) for r in _g1_err])
    _by_g1 = {}
    for _t, _r in _pairs_g1:
        _by_g1.setdefault(_t, []).append(_r)
    for _t, _rows in _by_g1.items():
        _trs_g1 = _tabs_g1[_t - 1].findall(_W + 'tr')
        for _r in sorted(_rows, reverse=True):
            _tabs_g1[_t - 1].remove(_trs_g1[_r])
    _final_g1 = _dl.write_docx(_d_g1, str(HERE / 'fix5_1_parent.docx'))
    run(['check', '--docx', HERE / 'fix5_1_parent.docx', '--profile', HERE / 'bixiu2_unfrozen.json',
         '--report', HERE / 'fix5_1_parent_check.json'], None, 'fix5-1 父稿破坏：G1 全变正确')
    _g1_chk = load(HERE / 'fix5_1_parent_check.json')
    assert any(f['rule'] == 'A2 表内正误不齐' and f.get('table') == str(_G1) for f in _g1_chk['findings']), _g1_chk['findings']
    run(['extract', '--docx', HERE / 'fix5_1_parent.docx', '--out', HERE / 'fix5_1_parent_items.json',
         '--profile', HERE / 'bixiu2_unfrozen.json'], 0, 'fix5-1 父稿破坏后重抽')
    _items_g1 = load(HERE / 'fix5_1_parent_items.json')
    _items_g1['records'] = [r for r in _items_g1['records'] if not (r['group'] == _G2 and r['verdict'] == '错误')]
    _items_g1['count'] = len(_items_g1['records'])
    (HERE / 'fix5_1_items.json').write_text(json.dumps(_items_g1, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', HERE / 'fix5_1_parent.docx', '--items', HERE / 'fix5_1_items.json',
         '--out', HERE / 'fix5_1_out.docx', '--expect-sha', _final_g1['sha256'],
         '--profile', HERE / 'bixiu2_unfrozen.json'],
        1, 'fix5-1：父稿 G1 已有表级 FAIL，候选稿 G2 新造同规则表级 FAIL 必须算新增')
    assert not (HERE / 'fix5_1_out.docx').exists()
    print('  写后单练门表级 FAIL（如"A2 表内正误不齐"）基线键按 table 等字段区分，不再被别的表掩盖（修复 major 1）')

    # ---- 回归 fix5-2（major 2：_renumber_row 只信段首连续 run 拼接串，序号跨 run／题干同数字开头都不能改错）----
    _rec10 = next(r for r in _b3items['records'] if r['no'] == '10')
    _d_split = _dl.open_docx(str(B3_52))
    _T_split = _tbls(_d_split)
    for _side in ('a2', 'a1'):
        _tr_s = _T_split[_rec10[_side]['table'] - 1].findall(_W + 'tr')[_rec10[_side]['row']]
        _p0_s = _tr_s.findall(_W + 'tc')[0].findall(_W + 'p')[0]
        _runs_s = _p0_s.findall(_W + 'r')
        _first_s = next(r for r in _runs_s if r.find(_W + 't') is not None and (r.find(_W + 't').text or '').startswith('10'))
        _t0_s = _first_s.find(_W + 't')
        _rest_s = _t0_s.text[2:]
        _t0_s.text = '1'
        _r2_s = copy.deepcopy(_first_s)
        _r2_s.find(_W + 't').text = '0' + _rest_s
        _first_s.addnext(_r2_s)
        _stem_run_s = next(r for r in _p0_s.findall(_W + 'r')[2:]
                            if r.find(_W + 't') is not None and (r.find(_W + 't').text or '').strip())
        _stem_run_s.find(_W + 't').text = '10个' + _stem_run_s.find(_W + 't').text
    _final_split = _dl.write_docx(_d_split, str(HERE / 'fix5_2_parent.docx'))
    run(['extract', '--docx', HERE / 'fix5_2_parent.docx', '--out', HERE / 'fix5_2_items.json', '--profile', 'bixiu3'],
        0, 'fix5-2 父稿：序号 10 拆成两个 run，题干改成"10个…"，重抽')
    _it_split = load(HERE / 'fix5_2_items.json')
    _rec10b = next(r for r in _it_split['records'] if r['no'] == '10')
    assert _rec10b['stem'].startswith('10个'), _rec10b['stem'][:20]
    _groups_split = []
    for r in _it_split['records']:
        if r['group'] not in _groups_split:
            _groups_split.append(r['group'])
    _new_split = {'no': 'N', 'group': _groups_split[0], 'stem': '回归测试新增占位题肢甲乙丙。', 'verdict': '正确',
                  'error_runs': [], 'correction': None, 'note': None, 'source': '回归测试', 'a1': None, 'a2': None}
    _i0_split = next(i for i, r in enumerate(_it_split['records']) if r['group'] == _groups_split[0])
    _it_split['records'][_i0_split:_i0_split] = [_new_split]
    (HERE / 'fix5_2_items_ins.json').write_text(json.dumps(_it_split, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', HERE / 'fix5_2_parent.docx', '--items', HERE / 'fix5_2_items_ins.json',
         '--out', HERE / 'fix5_2_out.docx', '--expect-sha', _final_split['sha256'], '--profile', 'bixiu3'],
        0, 'fix5-2：插入 1 条使第 10 条走重编号路径，不得改坏题干')
    _d_split_out = _dl.open_docx(str(HERE / 'fix5_2_out.docx'))
    _T_split_out = _tbls(_d_split_out)
    _shift_split = 1 if _rec10b['group'] == _groups_split[0] else 0
    for _side in ('a2', 'a1'):
        _tr_out = _T_split_out[_rec10b[_side]['table'] - 1].findall(_W + 'tr')[_rec10b[_side]['row'] + _shift_split]
        _txt_out = ''.join((t.text or '') for p in _tr_out.findall(_W + 'tc')[0].findall(_W + 'p')
                            for t in p.findall(_W + 'r/' + _W + 't'))
        assert _txt_out.startswith('11、') and '10个' in _txt_out, (_side, _txt_out[:40])
    run(['check', '--docx', HERE / 'fix5_2_out.docx', '--profile', 'bixiu3', '--report', HERE / 'fix5_2_check.json'],
        None, 'fix5-2 核对')
    _chk_split = load(HERE / 'fix5_2_check.json')
    assert not any('编号' in f['rule'] for f in _chk_split['findings']), _chk_split['findings']
    print('  序号拆 run + 题干以同数字开头：_renumber_row 只认段首拼接串，正确改号且不动题干（修复 major 2）')

    # ---- 回归 fix5-3（major 3：build 写后门必须也跑 drill_tool 自己补的检查，不能只跑 bh.check_drill）----
    _it_empty_src = copy.deepcopy(_b3items)
    _groups_es = []
    for r in _it_empty_src['records']:
        if r['group'] not in _groups_es:
            _groups_es.append(r['group'])
    _new_es = {'no': 'N', 'group': _groups_es[0], 'stem': '回归测试新增题源为空占位题肢甲乙丙。', 'verdict': '正确',
               'error_runs': [], 'correction': None, 'note': None, 'source': '', 'a1': None, 'a2': None}
    _i0_es = next(i for i, r in enumerate(_it_empty_src['records']) if r['group'] == _groups_es[0])
    _it_empty_src['records'][_i0_es:_i0_es] = [_new_es]
    (HERE / 'fix5_3_items.json').write_text(json.dumps(_it_empty_src, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'fix5_3_items.json', '--out', HERE / 'fix5_3_out.docx',
         '--expect-sha', sha52, '--profile', 'bixiu3'],
        1, 'fix5-3：新增条目题源为空（bh.check_drill 不查这项），build 写后门必须自己拦下')
    assert not (HERE / 'fix5_3_out.docx').exists()
    print('  build 写后门覆盖 drill_tool 自己补的检查（题源为空/序号连续/A1A2一致/分组标签），不再只跑 bh.check_drill（修复 major 3）')

    # ---- 回归 fix5-4a（minor：同段纠正模板插入新错误项必须保留 <w:br/>，不得多加序号后的制表符）----
    _d_combo_out = _dl.open_docx(str(HERE / 'b2_230_combo_build.docx'))
    _T_combo_out = _tbls(_d_combo_out)
    _combo_tr = _T_combo_out[_combined_group - 1].findall(_W + 'tr')[0]
    _combo_ps = _combo_tr.findall(_W + 'tc')[_sc2].findall(_W + 'p')
    assert len(_combo_ps) == 1, '同段模板生成的新行应仍是 1 个 w:p（题干与纠正同段）'
    _combo_run_kinds = [[k.tag.split('}')[1] for k in r if k.tag != _W + 'rPr'] for r in _combo_ps[0].findall(_W + 'r')]
    assert any('br' in kk for kk in _combo_run_kinds), ('新行缺少 <w:br/> 分隔符', _combo_run_kinds)
    _tmpl_tr = _tabs230_orig[_combined_group - 1].findall(_W + 'tr')[_first_err['a2']['row']]
    _tmpl_ps0 = _tmpl_tr.findall(_W + 'tc')[_sc2].findall(_W + 'p')[0]
    _tmpl_run_kinds = [[k.tag.split('}')[1] for k in r if k.tag != _W + 'rPr'] for r in _tmpl_ps0.findall(_W + 'r')]
    _tmpl_has_tab_after_no = len(_tmpl_run_kinds) > 1 and _tmpl_run_kinds[1] == ['tab']
    _combo_has_tab_after_no = len(_combo_run_kinds) > 1 and _combo_run_kinds[1] == ['tab']
    assert _combo_has_tab_after_no == _tmpl_has_tab_after_no, (
        '新行序号后是否带 tab 应与模板一致', _tmpl_run_kinds, _combo_run_kinds)
    print('  同段纠正模板插入新错误项：新行按模板结构生成，保留 <w:br/>，序号分隔符与模板一致（修复 minor）')

    # ---- 回归 fix5-4b（minor：--admission-mode execution 必须也核题源，不能只核题干）----
    _cands_fix54 = [{'id': '%s:%s' % (r['group'], r['no']), 'stem': r['stem'], 'source': r.get('source', '')}
                     for r in _b3items['records']]
    _ex_ids_fix54 = {_cands_fix54[3]['id'], _cands_fix54[30]['id']}
    _dec_fix54 = {'input_sha256': sha52, 'records': [
        {'old_id': c['id'], 'statement': c['stem'], 'source': c['source'],
         'action': 'exclude' if c['id'] in _ex_ids_fix54 else 'retain', 'reason': '回归测试'} for c in _cands_fix54]}
    (HERE / 'fix5_4b_dec.json').write_text(json.dumps(_dec_fix54, ensure_ascii=False), encoding='utf-8')
    _it_badsrc = copy.deepcopy(_b3items)
    _it_badsrc['records'] = [r for r in _it_badsrc['records']
                             if '%s:%s' % (r['group'], r['no']) not in _ex_ids_fix54]
    _it_badsrc['records'][0]['source'] = (_it_badsrc['records'][0].get('source') or '') + '（回归测试改错源）'
    (HERE / 'fix5_4b_items.json').write_text(json.dumps(_it_badsrc, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'fix5_4b_items.json', '--out', HERE / 'fix5_4b_out.docx',
         '--expect-sha', sha52, '--profile', 'bixiu3'], 0, 'fix5-4b：按决策删除后另把 1 条保留条目的题源改掉')
    run(['check', '--docx', HERE / 'fix5_4b_out.docx', '--profile', 'bixiu3', '--admission', HERE / 'fix5_4b_dec.json',
         '--admission-mode', 'execution', '--report', HERE / 'fix5_4b_check.json'], None, 'fix5-4b execution 核对')
    _adm54 = load(HERE / 'fix5_4b_check.json')['admission']
    assert _adm54['status'] == 'fail', _adm54
    print('  --admission-mode execution 把题源编进稳定 id，保留条目题源被单独篡改也能发现（修复 minor 4）')

    # =====================================================================
    # 第六轮返修回归用例（fix6_drill_tool 2026-09-24，对应 confirm_drill_tool.json 的 major①收口：
    # "一修一增"漏洞）
    # =====================================================================
    print('\n== 第六轮返修回归用例 ==')

    # ---- 回归 fix6-1（major，收口：_new_fails 必须按内容键做多重集合（Counter）计数，不能只判断
    # "键在不在父稿集合里"——同一次 build 里既修好一条父稿原有"题源为空"、又新增一条与父稿另一条
    # "题源为空"内容完全相同的条目时，候选稿这个键的出现次数其实比父稿多了一次，纯集合比较看不出
    # "次数"，会把新增那条也当成"父稿已有"漏放过去。修复后必须 exit 1、不留输出）----
    _empties_fix6 = [r for r in _b3items['records'] if not (r.get('source') or '').strip()]
    assert len(_empties_fix6) >= 2, 'B3_52 应至少有 2 条题源为空的条目供回归用例使用'
    _it_fix6 = copy.deepcopy(_b3items)
    _empties_fix6_c = [r for r in _it_fix6['records'] if not (r.get('source') or '').strip()]
    _fixr6, _dup6 = _empties_fix6_c[0], _empties_fix6_c[1]
    _fixr6['source'] = '回归测试补填题源'  # 修好父稿原有一条"题源为空"
    _new6 = copy.deepcopy(_dup6)
    _new6['no'] = 'N'
    _new6['a1'] = None
    _new6['a2'] = None
    _i6 = next(i for i, r in enumerate(_it_fix6['records']) if r is _dup6)
    _it_fix6['records'][_i6 + 1:_i6 + 1] = [_new6]  # 同时新增一条与 _dup6 内容完全相同的"题源为空"
    (HERE / 'fix6_1_items.json').write_text(json.dumps(_it_fix6, ensure_ascii=False), encoding='utf-8')
    run(['build', '--docx', B3_52, '--items', HERE / 'fix6_1_items.json', '--out', HERE / 'fix6_1_out.docx',
         '--expect-sha', sha52, '--profile', 'bixiu3'],
        1, 'fix6-1：修好一条题源为空、同时复制另一条题源为空条目（同规则计数不变）→ 必须算新增，exit 1')
    assert not (HERE / 'fix6_1_out.docx').exists()
    print('  _new_fails 按内容键做多重集合（Counter）比较，"一修一增"不再被父稿基线掩盖（修复 major，收口 fix6）')

    print('\n== 输入 SHA/mtime（测试后，应与测试前逐一相同）==')
    changed = []
    for k, v0 in before.items():
        v1 = sha_mtime(k)
        same = v0 == v1
        print(' ', k, 'unchanged' if same else 'CHANGED!!!', v1)
        if not same:
            changed.append(k)
    assert not changed, 'real inputs changed: %s' % changed

    ok_all = all(r['ok'] for r in RESULTS)
    (HERE / 'RESULTS.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n全部用例：', 'PASS' if ok_all else 'FAIL', '（详见 RESULTS.json）')
    return 0 if ok_all else 1


if __name__ == '__main__':
    sys.exit(main())
