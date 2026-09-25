#!/usr/bin/env python3
"""drill_tool.py 的对抗性复核脚本（独立审查者，2026-09-24）。

只读真实输入（B3_52、B3_51、B2_230），所有输出只写 --out 目录（系统临时目录下的 scratch）。
不改 drill_tool.py / batch_health.py / docx_lib.py / profile_lib.py / profiles/。
写路径越权类用例一律用“直接调用守卫函数、看它放不放行”的方式取证，绝不真的往书稿/审阅入口/中央状态写文件。

用法：/usr/bin/python3 drill_tool_verify.py --out <scratch>/drill_tool_verify/cases
"""
import argparse
import copy
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
from profile_lib import load_profile  # noqa: E402
from lxml import etree  # noqa: E402

W = bh.W
PY = '/usr/bin/python3'
TOOL = HERE / 'drill_tool.py'
ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
B3_52 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/必修三政治与法治宝典_第52批_意见修改审阅稿.docx'
B3_51 = ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx'
B2_230 = ROOT / '必修二_周六成品冲刺_20260910/工作稿/修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.docx'
RESULTS = []


def rec(case, expect, got, ok, **extra):
    r = {'case': case, 'expect': expect, 'got': got, 'as_expected': ok}
    r.update(extra)
    RESULTS.append(r)
    print('[%s] %s  expect=%s got=%s' % ('OK ' if ok else 'BUG', case, expect, got))


def run(args):
    p = subprocess.run([PY, '-B', str(TOOL)] + [str(a) for a in args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()[-1500:], p.stderr.strip()[-1500:]


def top_tables(root):
    out = []

    def r(el):
        for ch in el:
            if ch.tag == W + 'tbl':
                out.append(ch)
            elif ch.tag in (W + 'sdt', W + 'sdtContent', W + 'customXml', W + 'smartTag'):
                r(ch)
    r(root.find(W + 'body'))
    return out


def mutate(src, dst, fn):
    """复制 src 到 dst，并对 document.xml 调 fn(root) 修改。"""
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, 'w') as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename == 'word/document.xml':
                root = etree.fromstring(data)
                fn(root)
                data = etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True)
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zout.writestr(zi, data)


def items_of(path, prof='bixiu3'):
    P = bh.Prof(load_profile(prof))
    items, _ = bh.read_docx(str(path))
    bh.walk(items, P)
    return items, P


def cell(root, tbl, row, col):
    return top_tables(root)[tbl - 1].findall(W + 'tr')[row].findall(W + 'tc')[col]


def set_cell_text(tc, text):
    ps = tc.findall(W + 'p')
    p = ps[0]
    rs = p.findall(W + 'r')
    for r in rs[1:]:
        p.remove(r)
    r = rs[0] if rs else etree.SubElement(p, W + 'r')
    for ch in list(r):
        if ch.tag != W + 'rPr':
            r.remove(ch)
    t = etree.SubElement(r, W + 't')
    t.text = text
    t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')


def replace_in_cell(tc, old, new, count=1):
    for t in tc.iter(W + 't'):
        if t.text and old in t.text:
            t.text = t.text.replace(old, new, count)
            return True
    return False


def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def findings_of(rep):
    return [(f['level'], f['rule']) for f in load_json(rep)['findings']]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    O = Path(a.out).resolve()
    O.mkdir(parents=True, exist_ok=True)
    for f in O.iterdir():
        if f.is_file() or f.is_symlink():
            f.unlink()
        else:
            shutil.rmtree(f)

    base = O / 'b3_base.docx'
    shutil.copyfile(B3_52, base)
    items, P = items_of(base)
    D = bh.collect_drill(items, P)
    A1 = [x for x in D['recs'] if x['sec'] == 'A1']
    A2 = [x for x in D['recs'] if x['sec'] != 'A1']
    # 一条“错误”、一条“正确”、有题源的样本
    xe = next(i for i, y in enumerate(A2) if y['ans'] == '错误' and y['src'] and len(y['stem']) > 30)
    xo = next(i for i, y in enumerate(A2) if y['ans'] == '正确' and y['src'] and len(y['stem']) > 30)
    E1, E2, O1, O2 = A1[xe]['it'], A2[xe]['it'], A1[xo]['it'], A2[xo]['it']

    # ---------------- 1) 规格④ check 负例（编写者未做）----------------
    def neg(name, fn, want_rule):
        dst = O / ('neg_%s.docx' % name)
        mutate(base, dst, fn)
        rep = O / ('neg_%s.json' % name)
        code, so, se = run(['check', '--docx', dst, '--profile', 'bixiu3', '--report', rep])
        fs = findings_of(rep) if rep.exists() else []
        hit = [f for f in fs if re.search(want_rule, f[1])]
        rec('check负例:' + name, 'FAIL 命中 /%s/' % want_rule, {'exit': code, 'hits': hit[:3],
            'non_src_findings': [f for f in fs if f[1] != '题源为空'][:6]}, bool(hit) and code == 1)
        dst.unlink()

    neg('A1填答案', lambda r: set_cell_text(cell(r, E1['tbl'], E1['row'], 1), '错误'), 'A1 判断栏')
    neg('A2不选', lambda r: set_cell_text(cell(r, O2['tbl'], O2['row'], 1), '不选'), 'A2 判断只允许')

    def drop_corr(r):
        tc = cell(r, E2['tbl'], E2['row'], 0)
        ps = tc.findall(W + 'p')
        for p in ps[1:]:
            tc.remove(p)
    neg('错误项缺纠正', drop_corr, '缺绿色')
    stemE = A1[xe]['stem']
    ch_front = stemE[3]
    neg('A1A2题干前20字不一致', lambda r: replace_in_cell(cell(r, E1['tbl'], E1['row'], 0), ch_front, '■'), '同序号条目不一致')
    # 第 25 个字以后改一个字（题干逐字一致要求）
    ch_tail = stemE[-3]
    neg('A1A2题干第20字后不一致', lambda r: replace_in_cell(cell(r, E1['tbl'], E1['row'], 0),
                                                        stemE[-6:], stemE[-6:-3] + '■' + stemE[-2:]), '同序号条目不一致')

    def skip_no(r):
        # A1 与 A2 同步跳号：把第 xo 条之后本组所有序号 +1（A1、A2 各自一致，只是跳了一个号）
        for sec in (A1, A2):
            for y in sec[xo:]:
                it = y['it']
                tc = cell(r, it['tbl'], it['row'], 0)
                replace_in_cell(tc, '%s、' % y['no'], '%d、' % (int(re.match(r'\d+', y['no']).group()) + 1))
    neg('A1A2同步跳号', skip_no, '序号|跳号|连续')
    neg('A1A2题源不一致', lambda r: set_cell_text(cell(r, O1['tbl'], O1['row'], 2), A1[xo]['src'] + '改'), '同序号条目不一致')
    neg('A2题源为空', lambda r: set_cell_text(cell(r, O2['tbl'], O2['row'], 2), ''), '题源为空')

    # ---------------- 2) guard_json 越权：直接调函数看是否放行（不写任何文件）----------------
    sys.argv = ['drill_tool.py']
    import drill_tool as dt
    pd3 = load_profile('bixiu3')
    pd2 = load_profile('bixiu2')
    probes = [
        ROOT / '00_必修三最新审查稿' / 'drill_items_probe_never_written.json',
        ROOT / '必修三_最新Skill修订_20260913' / '协作' / 'drill_items_probe_never_written.json',
        ROOT / '必修三_最新Skill修订_20260913' / 'drill_items_probe_never_written.json',
        Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/drill_items_probe_never_written.json'),
        HERE / 'drill_items_probe_never_written.json',
        ROOT / 'drill_items_probe_never_written.json',
    ]
    for pth in probes:
        assert not pth.exists()
        try:
            dt.guard_json(str(pth), pd3, [str(B3_52)])
            g1 = 'ALLOWED'
        except dt.Abort as e:
            g1 = 'refused(%d)' % e.code
        try:
            dl.guard_write(str(pth), pd3, inputs=[str(B3_52)], kind='.json')
            g2 = 'ALLOWED'
        except dl.GuardError:
            g2 = 'refused'
        rec('guard_json 受保护位置:' + str(pth.relative_to(pth.parents[1])), 'refused（规格：只允许 构建/ 或系统临时目录）',
            {'drill_tool.guard_json': g1, 'docx_lib.guard_write(kind=.json)': g2}, g1 != 'ALLOWED')
        assert not pth.exists()
    # 冻结册目录：guard_json 应拒绝
    pz = ROOT / '必修二_周六成品冲刺_20260910' / 'drill_items_probe_never_written.json'
    try:
        dt.guard_json(str(pz), pd3, [])
        g = 'ALLOWED'
    except dt.Abort as e:
        g = 'refused(%d)' % e.code
    rec('guard_json 冻结册目录', 'refused(3)', g, g == 'refused(3)')

    # ---------------- 3) 失败留半成品：build 的 --report 守卫在写 docx 之后才跑 ----------------
    items_json = O / 'b3_items.json'
    code, so, se = run(['extract', '--docx', base, '--out', items_json, '--profile', 'bixiu3'])
    assert code == 0, se
    outd = O / 'halfdone_build.docx'
    bad_report = ROOT / '必修二_周六成品冲刺_20260910' / 'drill_report_probe_never_written.json'  # 冻结册目录 → guard_json 拒绝
    code, so, se = run(['build', '--docx', base, '--items', items_json, '--out', outd, '--profile', 'bixiu3',
                        '--report', bad_report])
    rec('build 报告路径被拒后是否留下 docx', 'exit!=0 且不留 docx', {'exit': code, 'docx_left': outd.exists(),
        'stderr': se[-200:]}, not outd.exists())
    assert not bad_report.exists()
    # 报告目标是已存在的非本工具 json → 同样在 docx 写出之后才拒
    foreign = O / 'foreign.json'
    foreign.write_text('{"x":1}', encoding='utf-8')
    outd2 = O / 'halfdone_build2.docx'
    code, so, se = run(['build', '--docx', base, '--items', items_json, '--out', outd2, '--profile', 'bixiu3',
                        '--report', foreign])
    rec('build 报告目标已存在(非本工具)时是否留下 docx', 'exit!=0 且不留 docx',
        {'exit': code, 'docx_left': outd2.exists(), 'stderr': se[-160:]}, not outd2.exists())
    # extract：--report 非法后缀 → items.json 已写出
    ij = O / 'halfdone_items.json'
    code, so, se = run(['extract', '--docx', base, '--out', ij, '--profile', 'bixiu3', '--report', O / 'r.txt'])
    rec('extract 报告路径非法时是否留下 items.json', 'exit!=0 且不留 items.json',
        {'exit': code, 'items_left': ij.exists()}, not ij.exists())

    # ---------------- 4) 写后体检失败：不留输出、不留临时文件 ----------------
    it = load_json(items_json)
    for r in it['records']:
        if r['verdict'] == '错误':
            r['correction'] = None
            break
    bad = O / 'items_err_no_corr.json'
    bad.write_text(json.dumps(it, ensure_ascii=False), encoding='utf-8')
    outd3 = O / 'postfail.docx'
    before_tmp = set(os.listdir(tempfile.gettempdir()))
    code, so, se = run(['build', '--docx', base, '--items', bad, '--out', outd3, '--profile', 'bixiu3'])
    leftovers = [f for f in os.listdir(O) if f.startswith('.docx_lib_')] + \
                [f for f in set(os.listdir(tempfile.gettempdir())) - before_tmp if f.startswith('.drill_tool_verify_')]
    rec('写后单练门 FAIL（错误项缺纠正）', '中止、不留输出与临时文件；规格退出码 1', {'exit': code, 'out_left': outd3.exists(),
        'leftovers': leftovers, 'stderr': se[:120]}, (not outd3.exists()) and not leftovers and code in (1, 2),
        note='退出码 2 与规格“写后体检出现新 FAIL→1”不符，见 issue')

    # ---------------- 5) 同一片段在题干里出现两次：红色落到第一次出现处 ----------------
    rE = A2[xe]
    seg_rows = bh.collect_drill(items, P)
    runs = [t for t, c in dt._row_cell_runs(items, E2['tbl'], E2['row'], 0) if c == 'C00000']
    red = runs[0]

    def dup_red(r):
        tc = cell(r, E2['tbl'], E2['row'], 0)
        p = tc.findall(W + 'p')[0]
        rs = p.findall(W + 'r')
        # 在编号+制表符之后插入一个黑色 run，文字与红色片段相同
        idx = next(i for i, x in enumerate(rs) if x.find(W + 'tab') is not None)
        nr = copy.deepcopy(rs[idx])
        for ch in list(nr):
            if ch.tag != W + 'rPr':
                nr.remove(ch)
        t = etree.SubElement(nr, W + 't')
        t.text = red + '，'
        t.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        rpr = nr.find(W + 'rPr')
        if rpr is not None and rpr.find(W + 'color') is not None:
            rpr.find(W + 'color').set(W + 'val', '000000')
        rs[idx].addnext(nr)
    dupd = O / 'dup_red.docx'
    mutate(base, dupd, dup_red)
    ij2 = O / 'dup_red_items.json'
    run(['extract', '--docx', dupd, '--out', ij2, '--profile', 'bixiu3'])
    outd4 = O / 'dup_red_build.docx'
    code, so, se = run(['build', '--docx', dupd, '--items', ij2, '--out', outd4, '--profile', 'bixiu3'])
    got = {}
    if outd4.exists():
        i0, _ = items_of(dupd)
        i1, _ = items_of(outd4)
        before = [(t, c) for t, c in dt._row_cell_runs(i0, E2['tbl'], E2['row'], 0)]
        after = [(t, c) for t, c in dt._row_cell_runs(i1, E2['tbl'], E2['row'], 0)]
        rb = ''.join(t if c != 'C00000' else '[' + t + ']' for t, c in before)
        ra = ''.join(t if c != 'C00000' else '[' + t + ']' for t, c in after)
        got = {'exit': code, 'before': rb[:90], 'after': ra[:90], 'same': rb == ra}
    rec('重复片段的红色位置', '往返后红色仍在原位置', got, got.get('same') is True)

    # ---------------- 6) 表内非条目行（表头）被 build 静默删掉 ----------------
    g2 = A2[xo]['it']['tbl']

    def add_header(r):
        tb = top_tables(r)[g2 - 1]
        first = tb.findall(W + 'tr')[0]
        hdr = copy.deepcopy(first)
        for tc, txt in zip(hdr.findall(W + 'tc'), ['题肢', '判断', '题源']):
            ps = tc.findall(W + 'p')
            for p in ps[1:]:
                tc.remove(p)
            set_cell_text(tc, txt)
        first.addprevious(hdr)
    hd = O / 'header_row.docx'
    mutate(base, hd, add_header)
    ij3 = O / 'header_items.json'
    code0, so0, se0 = run(['extract', '--docx', hd, '--out', ij3, '--profile', 'bixiu3'])
    outd5 = O / 'header_build.docx'
    code, so, se = run(['build', '--docx', hd, '--items', ij3, '--out', outd5, '--profile', 'bixiu3'])
    kept = None
    if outd5.exists():
        root = etree.fromstring(zipfile.ZipFile(outd5).read('word/document.xml'))
        first_txt = ''.join(top_tables(root)[g2 - 1].findall(W + 'tr')[0].itertext())
        kept = first_txt.startswith('题肢')
    rec('A2 表内表头行（非条目行）', 'build 保留或拒绝（不静默删除）',
        {'extract_non_item_rows': load_json(ij3)['non_item_rows'] if ij3.exists() else None, 'build_exit': code,
         'header_kept': kept}, kept is not False)

    # ---------------- 7) A1 少一行：extract 静默截断，build 丢掉最后一条 A2 ----------------
    last1 = A1[-1]['it']

    def drop_a1_row(r):
        tb = top_tables(r)[last1['tbl'] - 1]
        tb.remove(tb.findall(W + 'tr')[last1['row']])
    d7 = O / 'a1_missing_last.docx'
    mutate(base, d7, drop_a1_row)
    ij7 = O / 'a1_missing_items.json'
    c7, so7, se7 = run(['extract', '--docx', d7, '--out', ij7, '--profile', 'bixiu3'])
    j7 = load_json(ij7) if ij7.exists() else {}
    outd7 = O / 'a1_missing_build.docx'
    cb7, sob7, seb7 = run(['build', '--docx', d7, '--items', ij7, '--out', outd7, '--profile', 'bixiu3'])
    after_n = None
    if outd7.exists():
        i7, P7 = items_of(outd7)
        after_n = bh.check_drill(i7, P7, bh.Findings())['a2']
    rec('A1 缺一行时 extract→build', 'extract 非 0 退出或 build 拒绝；不得丢 A2 条目',
        {'extract_exit': c7, 'count': j7.get('count'), 'a1': j7.get('a1_count'), 'a2': j7.get('a2_count'),
         'build_exit': cb7, 'a2_after_build': after_n, 'a2_before': len(A2)},
        not (c7 == 0 and cb7 == 0 and after_n is not None and after_n < len(A2)))

    # ---------------- 8) items.json 来自别的父稿（B3_51）→ build 到 B3_52 是否被拒 ----------------
    ij8 = O / 'b3_51_items.json'
    c8, so8, se8 = run(['extract', '--docx', B3_51, '--out', ij8, '--profile', 'bixiu3'])
    outd8 = O / 'stale_items_build.docx'
    cb8, sob8, seb8 = run(['build', '--docx', base, '--items', ij8, '--out', outd8, '--profile', 'bixiu3'])
    j8 = load_json(ij8) if ij8.exists() else {}
    diffcnt = None
    if outd8.exists():
        i8, _ = items_of(outd8)
        n8 = [x for x in bh.collect_drill(i8, P)['recs'] if x['sec'] != 'A1']
        diffcnt = sum(1 for x, y in zip(A2, n8) if (x['stem'], x['src']) != (y['stem'], y['src'])) + abs(len(A2) - len(n8))
    rec('旧父稿(B3_51)的 items.json 套到 B3_52', '拒绝（items.source_sha256≠父稿）或至少警告',
        {'extract_51_exit': c8, 'b51_count': j8.get('count'), 'build_exit': cb8, 'build_stderr': seb8[-200:],
         'a2_rows_changed_vs_B3_52': diffcnt}, cb8 != 0)

    # ---------------- 9) --admission：exclude 的条目仍在书里却 exit 0 ----------------
    itj = load_json(items_json)
    decs = []
    for k, r in enumerate(itj['records']):
        decs.append({'old_id': '%s:%s' % (r['group'], r['no']),
                     'statement': re.sub(r'^\d+[、.．]', '', r['a2']['text'], count=1), 'source': r['source'],
                     'action': 'exclude' if k < 3 else 'retain', 'reason': '测试'})
    dj = O / 'decisions_exclude3.json'
    dj.write_text(json.dumps({'records': decs, 'input_sha256': '0' * 64}, ensure_ascii=False), encoding='utf-8')
    # 为了只看准入逻辑，用一份没有题源为空问题的文档：直接用 base（16 条题源为空会让 exit=1），所以看 findings
    rep9 = O / 'admission_exclude.json'
    c9, so9, se9 = run(['check', '--docx', base, '--profile', 'bixiu3', '--admission', dj, '--report', rep9])
    r9 = load_json(rep9)
    adm_f = [f for f in r9['findings'] if '准入' in f['rule']]
    rec('--admission 有 3 条 exclude（书里仍在）且 input_sha256 不符', '报 FAIL/CANDIDATE',
        {'exit': c9, 'admission_status': r9.get('admission', {}).get('status'),
         'excluded_count': r9.get('admission', {}).get('excluded_count'), 'admission_findings': len(adm_f)},
        bool(adm_f))

    # ---------------- 10) 冻结册绕过尝试 ----------------
    c, so, se = run(['build', '--docx', B2_230, '--items', items_json, '--out', O / 'fz1.docx', '--profile', 'bixiu3'])
    rec('冻结: 真实 B2_230 + --profile bixiu3', 'exit 3', {'exit': c, 'left': (O / 'fz1.docx').exists()}, c == 3)
    tmpprof = O / 'bixiu2_unfrozen.json'
    pj = json.loads((HERE / 'profiles/bixiu2.json').read_text(encoding='utf-8'))
    pj['frozen'] = False
    tmpprof.write_text(json.dumps(pj, ensure_ascii=False), encoding='utf-8')
    link = O / 'b2_symlink.docx'
    os.symlink(str(B2_230), str(link))
    c, so, se = run(['build', '--docx', link, '--items', items_json, '--out', O / 'fz2.docx', '--profile', tmpprof])
    rec('冻结: 临时目录符号链接→真实 B2_230 + frozen:false 配置副本', 'exit 3',
        {'exit': c, 'left': (O / 'fz2.docx').exists(), 'stderr': se[:120]}, c == 3)
    link.unlink()
    # 输出目录是指向冻结册工作区的符号链接：只调守卫函数取证
    ldir = O / 'link_to_b2_workspace'
    os.symlink(str(ROOT / '必修二_周六成品冲刺_20260910'), str(ldir))
    try:
        dl.guard_write(str(ldir / 'x.docx'), pd3, inputs=[str(base)], kind='.docx')
        g = 'ALLOWED'
    except dl.GuardError:
        g = 'refused'
    try:
        dt.guard_json(str(ldir / 'x.json'), pd3, [str(base)])
        gj = 'ALLOWED'
    except dt.Abort as e:
        gj = 'refused(%d)' % e.code
    ldir.unlink()
    rec('冻结: --out 经符号链接目录指向冻结册', 'refused', {'guard_write': g, 'guard_json': gj},
        g == 'refused' and gj.startswith('refused'))
    # 输出与输入同一文件（经符号链接）
    ln2 = O / 'same_as_input.docx'
    os.symlink(str(base), str(ln2))
    c, so, se = run(['build', '--docx', base, '--items', items_json, '--out', ln2, '--profile', 'bixiu3'])
    rec('输出=输入（经符号链接）', 'exit 3，输入不变', {'exit': c, 'base_sha_same': sha(base) == sha(O / 'b3_base.docx')},
        c == 3)
    ln2.unlink()

    # ---------------- 11) 正确项带 correction / error_runs ----------------
    it = load_json(items_json)
    tgt = next(r for r in it['records'] if r['verdict'] == '正确')
    tgt['correction'] = '纠正：这条批准稿里写了纠正'
    ij11 = O / 'ok_with_corr.json'
    ij11.write_text(json.dumps(it, ensure_ascii=False), encoding='utf-8')
    outd11 = O / 'ok_with_corr.docx'
    c, so, se = run(['build', '--docx', base, '--items', ij11, '--out', outd11, '--profile', 'bixiu3'])
    dropped = None
    if outd11.exists():
        dropped = '这条批准稿里写了纠正' not in zipfile.ZipFile(outd11).read('word/document.xml').decode('utf-8')
    rec('“正确”项带 correction', '拒绝或报告，不静默丢弃', {'exit': c, 'correction_silently_dropped': dropped},
        not (c == 0 and dropped))

    # ---------------- 12) 空白被 norm 吃掉（真实 B3_52 往返）----------------
    outd12 = O / 'roundtrip.docx'
    c, so, se = run(['build', '--docx', base, '--items', items_json, '--out', outd12, '--profile', 'bixiu3'])
    ia, _ = items_of(base)
    ib, _ = items_of(outd12)
    da = [x['text'] for x in ia if x['zone'] == 'drill' and x['tbl'] is not None]
    db = [x['text'] for x in ib if x['zone'] == 'drill' and x['tbl'] is not None]
    diff = [(x, y) for x, y in zip(da, db) if x != y]
    rec('B3_52 往返单练区逐段文字', '0 处不同', {'exit': c, 'n': len(diff), 'sample': diff[:2]}, not diff)

    (O / 'RESULTS.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1), encoding='utf-8')
    bugs = [r for r in RESULTS if not r['as_expected']]
    print('\n共 %d 例，不符合预期 %d 例' % (len(RESULTS), len(bugs)))
    return 1 if bugs else 0


if __name__ == '__main__':
    sys.exit(main())
