#!/usr/bin/env python3
"""apply_patch.py 对抗验证（审查者自写，2026-09-24）。只读真实书稿；所有输出写 --out 目录（系统临时目录）。

  /usr/bin/python3 apply_patch_verify.py --out $SCRATCH/booktools/apply_patch_verify/cases

每个用例记录 命令、退出码、stderr 摘录与事后检查；结果汇总到 <out>/verify_results.json。
不改工具、不改 batch_health/docx_lib/profile_lib/profiles，不写书稿目录、审阅入口、中央状态、题库。
"""
import argparse
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
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
TOOL = HERE / 'apply_patch.py'
ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
BUILD = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建'
B52 = BUILD / '必修三政治与法治宝典_第52批_意见修改审阅稿.docx'
B04 = BUILD / '04_编号与考法计数.docx'
B230 = ROOT / '必修二_周六成品冲刺_20260910/工作稿/修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.docx'
REAL = [B52, B04, BUILD / '03_第二部分专题.docx', BUILD / '同版身份.json', B230]

OUT = None
RES = []


def sha(p):
    return dl.sha256_file(p)


def snap():
    return {str(p): (sha(p), os.stat(p).st_mtime) for p in REAL}


def run(args):
    t = time.time()
    r = subprocess.run(['/usr/bin/python3', '-B', str(TOOL)] + [str(a) for a in args], capture_output=True, text=True)
    return {'rc': r.returncode, 'out': r.stdout.strip()[-400:], 'err': r.stderr.strip()[-400:], 's': round(time.time() - t, 2)}


def wpatch(name, ops, parent, book='bixiu3', **kw):
    p = OUT / f'{name}.json'
    obj = {'schema': 'baodian_patch_v1', 'book': book, 'approved_by': 'verify', 'approval_ref': 'verify', 'ops': ops}
    if parent is not None:
        obj['parent_docx_sha256'] = parent
    obj.update(kw)
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    return p


def rec(cid, desc, expect_safe, got, finding):
    RES.append({'case': cid, 'desc': desc, 'expected_safe_behaviour': expect_safe, 'got': got, 'finding': finding})
    print(f'[{cid}] {finding}: {json.dumps(got, ensure_ascii=False)[:300]}')


def texts_of(path):
    d = dl.open_docx(path)
    return d, [dl.para_text(p) for p in d.paras]


def fresh(name):
    p = OUT / name
    if p.exists():
        p.unlink()
    return p


# ------------------------------------------------------------------ 用例
def c01_diff_report_unguarded():
    victim = OUT / 'c01_victim.docx'
    victim.write_bytes(b'ORIGINAL-NOT-JSON')
    try:
        dl.guard_write(victim, load_profile('bixiu3'), kind='.json')
        guard = 'accepted'
    except dl.GuardError as e:
        guard = 'GuardError: ' + str(e)
    r = run(['diff', '--old', B04, '--new', B52, '--out', fresh('c01_patch.json'), '--report', victim])
    after = victim.read_bytes()[:40]
    rec('C01', 'diff --report 指向已存在的 .docx（guard_write 对同一路径会拒绝）', 'exit 3 且不写',
        {'run': r, 'guard_same_path': guard, 'victim_head_after': after.decode('utf-8', 'replace')},
        'FAIL' if after != b'ORIGINAL-NOT-JSON' else 'ok')


def c02_json_overwrite_in_build():
    prof = load_profile('bixiu3')
    out = {}
    for tgt in (BUILD / '同版身份.json', BUILD / '04_编号与考法计数.json'):
        for ow in (False, True):
            try:
                dl.guard_write(tgt, prof, kind='.json', overwrite=ow)
                out[f'{tgt.name}|overwrite={ow}'] = 'accepted'
            except dl.GuardError as e:
                out[f'{tgt.name}|overwrite={ow}'] = 'refused: ' + str(e)[:60]
    rec('C02', '--report / diff --out 以 overwrite=True 过 guard：构建/ 下已有 JSON 记录（同版身份.json、Codex 报告）可被覆盖',
        '已存在文件一律拒绝', out, 'FAIL' if any(v == 'accepted' for k, v in out.items() if 'True' in k) else 'ok')


def c03_leftover_on_report_refusal(b52sha):
    ops = [{'id': 'G1', 'op': 'replace_text', 'anchor': {'text': '地方党委', 'style': '题目材料'},
            'old': '地方党委', 'new': '地方党工委', 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c03_patch', ops, b52sha)
    out = fresh('c03_out.docx')
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out, '--report', OUT / 'c03_report.txt'])
    rec('C03', 'apply 成功写出后 --report 被守卫拒绝', '不留输出或先校验 report 路径',
        {'run': r, 'docx_left_on_disk': out.exists()}, 'FAIL' if (r['rc'] != 0 and out.exists()) else 'ok')


def _b2_op():
    return [{'id': 'F1', 'op': 'replace_text', 'anchor': {'text': 'B．通过标准化生产摊薄成本，实现规模效应', 'style': '题目选项'},
             'old': '标准化生产', 'new': '标准化流程生产', 'reason': 'r', 'evidence': 'e', 'source_zone': 'approved_edit'}]


def c04_c06_frozen_bypass(b230sha):
    pp2 = wpatch('c04_b2_patch_book_bixiu2', _b2_op(), b230sha, book='bixiu2')
    out = fresh('c04_b2_as_bixiu3.docx')
    r = run(['apply', '--docx', B230, '--patch', pp2, '--out', out, '--profile', 'bixiu3'])
    rec('C04', '冻结册 B2_230 + --profile bixiu3', 'exit 3（冻结册按输入稿识别）',
        {'run': r, 'written': out.exists()}, 'FAIL' if out.exists() else 'ok')
    pp3 = wpatch('c05_b2_patch_book_bixiu3', _b2_op(), b230sha, book='bixiu3')
    out = fresh('c05_b2_book_field.docx')
    r = run(['apply', '--docx', B230, '--patch', pp3, '--out', out])
    rec('C05', '冻结册 B2_230，补丁 book="bixiu3"，不给 --profile（detect_profile 被 book 字段抢先）', 'exit 3',
        {'run': r, 'written': out.exists()}, 'FAIL' if out.exists() else 'ok')
    out = fresh('c06_b2_allow_frozen_test.docx')
    r = run(['apply', '--docx', B230, '--patch', pp2, '--out', out, '--profile', 'bixiu2', '--allow-frozen-test'])
    rec('C06', '真实 bixiu2 配置 + 隐藏开关 --allow-frozen-test', '规格：真实 bixiu2 配置下必须拒写（exit 3）',
        {'run': r, 'written': out.exists()}, 'FAIL' if out.exists() else 'ok')
    rep = OUT / 'c07_b2_check_report.json'
    r = run(['check', '--docx', B230, '--patch', pp2, '--profile', 'bixiu2', '--report', rep])
    rec('C07', '冻结册只读 check 带 --report（临时目录）', '只读检查可以跑：exit 1 并写报告',
        {'run': r, 'report_written': rep.exists()}, 'FAIL' if r['rc'] == 3 else 'ok')
    # 符号链接输入：指向 B2，不给 profile/book → detect_profile 应解析到 bixiu2 并拒写
    link = OUT / 'c19_link_to_b2.docx'
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(B230)
    pp4 = wpatch('c19_b2_patch_nobook', _b2_op(), b230sha, book='')
    out = fresh('c19_via_symlink.docx')
    r = run(['apply', '--docx', link, '--patch', pp4, '--out', out])
    rec('C19', '输入为指向 B2_230 的符号链接，不给 profile/book', 'exit 3', {'run': r, 'written': out.exists()},
        'ok' if (r['rc'] == 3 and not out.exists()) else 'FAIL')


def c19b_symlink_out_guard():
    ld = OUT / 'c19_link_dir'
    if ld.is_symlink() or ld.exists():
        ld.unlink()
    ld.symlink_to(ROOT / '00_必修三最新审查稿')
    try:
        dl.guard_write(ld / 'x.docx', load_profile('bixiu3'))
        g = 'accepted'
    except dl.GuardError as e:
        g = 'refused: ' + str(e)[:80]
    ld.unlink()
    rec('C19b', '输出目录是临时目录里指向审阅入口的符号链接（只调 guard_write，不写）', 'refused', {'guard': g},
        'ok' if g.startswith('refused') else 'FAIL')


def c08_no_parent_sha():
    ops = [{'id': 'G1', 'op': 'replace_text', 'anchor': {'text': '地方党委', 'style': '题目材料'},
            'old': '地方党委', 'new': '地方党工委', 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c08_no_parent', ops, None)
    r = run(['check', '--docx', B52, '--patch', pp])
    out = fresh('c08_out.docx')
    r2 = run(['apply', '--docx', B52, '--patch', pp, '--out', out])
    rec('C08', '补丁缺 parent_docx_sha256', 'exit 2（父稿身份无法核对）', {'check': r, 'apply': r2, 'written': out.exists()},
        'FAIL' if out.exists() else 'ok')


def c09_index_only(b52sha):
    ops = [{'id': 'X1', 'op': 'replace_text', 'anchor': {'contains': '', 'index_hint': 10870},
            'old': '地方党委', 'new': '地方党工委', 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c09_index_only', ops, b52sha)
    rep = OUT / 'c09_report.json'
    r = run(['check', '--docx', B52, '--patch', pp, '--report', rep])
    idx = None
    if rep.exists():
        j = json.loads(rep.read_text(encoding='utf-8'))
        idx = (j.get('ops') or [{}])[0].get('index')
    rec('C09', 'anchor={"contains":"", "index_hint":10870}（空子串命中全书，再按段号选）', 'exit 2：不得只凭段号定位',
        {'run': r, 'resolved_index': idx}, 'FAIL' if r['rc'] in (0, 1) else 'ok')


def c10_idempotency_new_contains_old(b52sha):
    ops = [{'id': 'I1', 'op': 'replace_text', 'anchor': {'contains': '地方党', 'style': '题目材料'},
            'old': '党委', 'new': '党委机关', 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c10_patch', ops, b52sha)
    out1 = fresh('c10_out1.docx')
    r1 = run(['apply', '--docx', B52, '--patch', pp, '--out', out1])
    s1 = sha(out1)
    pp2 = wpatch('c10_patch_recheck', ops, s1)
    r2 = run(['check', '--docx', out1, '--patch', pp2])
    out2 = fresh('c10_out2.docx')
    r3 = run(['apply', '--docx', out1, '--patch', pp2, '--out', out2])
    t2 = None
    if out2.exists():
        _, tx = texts_of(out2)
        t2 = [t for t in tx if t.startswith('地方党委')][:2]
    rec('C10', 'replace_text 的 new 包含 old（"党委"→"党委机关"）后对输出再 check/apply', '再 check 应为 already_applied（exit 0）',
        {'apply1': r1['rc'], 'recheck': r2, 'reapply': r3['rc'], 'para_after_second_apply': t2},
        'FAIL' if r2['rc'] != 0 else 'ok')


def c11_empty_cell(b52sha):
    d = dl.open_docx(B52)
    tx = [dl.para_text(p) for p in d.paras]
    pos = {id(p): i for i, p in enumerate(d.paras)}
    target = None
    for tc in d.body.iter(W + 'tc'):
        ps = [ch for ch in tc if ch.tag == W + 'p']
        if len(ps) == 2:
            ii = [pos[id(p)] for p in ps]
            if all(tx[i] for i in ii):
                target = ii
                break
    ops = []
    for k, i in enumerate(target):
        ops.append({'id': f'E{k}', 'op': 'delete_paragraph',
                    'anchor': {'text': tx[i], 'index_hint': i, 'prev': tx[i - 1][:15] if tx[i - 1] else None},
                    'old': tx[i], 'reason': 'r', 'evidence': 'e', 'source_zone': 'approved_edit'})
        if ops[-1]['anchor']['prev'] is None:
            del ops[-1]['anchor']['prev']
    pp = wpatch('c11_patch', ops, b52sha)
    out = fresh('c11_out.docx')
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out])
    empty = None
    if out.exists():
        root = etree.fromstring(zipfile.ZipFile(out).read('word/document.xml'))
        empty = sum(1 for tc in root.iter(W + 'tc') if tc.find(W + 'p') is None and tc.find(W + 'tbl') is None)
    rec('C11', f'两条 delete_paragraph 删掉同一单元格的两段（段 {target}）', 'exit 2（单元格被删空）',
        {'run': r, 'tc_without_block_content': empty}, 'FAIL' if empty else 'ok')


def c12_insert_into_source(b52sha):
    d = dl.open_docx(B52)
    P = bh.Prof(load_profile('bixiu3'))
    bh.walk(d.items, P)
    tx = [it['text'] for it in d.items]
    tgt = None
    for i in range(1, len(d.items)):
        a, b = d.items[i - 1], d.items[i]
        if a['zone'] == 'source' and b['zone'] == 'teaching' and b['tbl'] is None and b['text'] and \
                sum(1 for t in tx if t == b['text']) == 1:
            tgt = i
            break
    new_text = '这是一段新增讲解文字。'
    ops = [{'id': 'Z1', 'op': 'insert_before', 'anchor': {'text': tx[tgt]}, 'paragraphs': [{'text': new_text}],
            'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c12_patch', ops, b52sha)
    out = fresh('c12_out.docx')
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out])
    zone_new = None
    if out.exists():
        d2 = dl.open_docx(out)
        bh.walk(d2.items, P)
        zone_new = [(it['i'], it['zone'], it['label']) for it in d2.items if it['text'] == new_text]
    rec('C12', f'insert_before 例题块首个教学标签段（段 {tgt}，前一段 zone=source），不带 source_zone', '应要求 source_zone（新段落进了题面区）',
        {'run': r, 'anchor_zone': d.items[tgt]['zone'], 'prev_zone': d.items[tgt - 1]['zone'], 'new_para_zone_in_output': zone_new},
        'FAIL' if zone_new and zone_new[0][1] == 'source' else 'ok')


def c13_forbidden_split_runs(b52sha):
    ops = [{'id': 'W1', 'op': 'insert_after', 'anchor': {'text': '地方党委', 'style': '题目材料'},
            'paragraphs': [{'runs': [{'text': '地方党委（待'}, {'text': '核）'}]}], 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c13_patch', ops, b52sha)
    r0 = run(['check', '--docx', B52, '--patch', pp])
    out = fresh('c13_out.docx')
    rep = OUT / 'c13_report.json'
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out, '--health', '--report', rep])
    nf = None
    if rep.exists():
        h = json.loads(rep.read_text(encoding='utf-8')).get('health', {})
        nf = [(f.get('check'), f.get('rule')) for f in h.get('new_FAIL', [])]
    rec('C13', '插入段用 runs 把“待核”拆成两个 run（每个 run 单独过词表）', 'check 阶段 exit 2（按拼接后的整段文字过词表）',
        {'check': r0, 'apply_health': r, 'new_FAIL': nf}, 'FAIL' if r0['rc'] == 1 else 'ok')


def c14_style_and_clone(b52sha):
    ops = [{'id': 'S1', 'op': 'insert_after', 'anchor': {'text': '地方党委', 'style': '题目材料'},
            'paragraphs': [{'text': '样式测试一', 'style': '宝典正文'},
                           {'text': '样式测试二', 'style': '根本不存在的样式XYZ'},
                           {'text': '克隆测试', 'clone_from': '根本不存在的定位串QQQ'}],
            'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c14_patch', ops, b52sha)
    out = fresh('c14_out.docx')
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out])
    got = {'run': r}
    if out.exists():
        d = dl.open_docx(out)
        z = zipfile.ZipFile(out)
        st = etree.fromstring(z.read('word/styles.xml'))
        ids = {s.get(W + 'styleId') for s in st.findall(W + 'style')}
        for it, p in zip(d.items, d.paras):
            if it['text'] in ('样式测试一', '样式测试二', '克隆测试'):
                ps = p.find(f'{W}pPr/{W}pStyle')
                v = ps.get(W + 'val') if ps is not None else None
                got[it['text']] = {'pStyle_val': v, 'val_is_real_styleId': v in ids, 'batch_health_style': it['style']}
    rec('C14', 'insert 的 style 用样式名“宝典正文”（styleId=aff5）与不存在的样式；clone_from 找不到', 'exit 2（样式名须存在；clone_from 须唯一命中）',
        got, 'FAIL' if r['rc'] == 0 else 'ok')


def c15_overlap_three_ops(b52sha):
    d = dl.open_docx(B52)
    tx = [dl.para_text(p) for p in d.paras]
    # 选一段文字唯一、非题面、足够长的纯文字段
    P = bh.Prof(load_profile('bixiu3'))
    bh.walk(d.items, P)
    from collections import Counter
    cnt = Counter(tx)
    pick = None
    for i, it in enumerate(d.items):
        t = tx[i]
        if it['zone'] == 'teaching' and it['tbl'] is None and cnt[t] == 1 and 40 <= len(t) <= 200 \
                and not dl.para_text(d.paras[i]) != t and d.paras[i].find('.//' + W + 'tab') is None:
            a, b, c = t[10:14], t[len(t) - 6:len(t) - 2], t[12:17]
            if t.count(a) == t.count(b) == t.count(c) == 1 and '【甲】' not in t:
                pick = (i, t, a, b, c)
                break
    i, t, a, b, c = pick
    ops = [{'id': 'O1', 'op': 'replace_text', 'anchor': {'text': t}, 'old': a, 'new': '【甲】', 'reason': 'r', 'evidence': 'e'},
           {'id': 'O2', 'op': 'replace_text', 'anchor': {'text': t}, 'old': b, 'new': '【乙】', 'reason': 'r', 'evidence': 'e'},
           {'id': 'O3', 'op': 'replace_text', 'anchor': {'text': t}, 'old': c, 'new': '【甲】', 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c15_patch', ops, b52sha)
    r0 = run(['check', '--docx', B52, '--patch', pp])
    out = fresh('c15_out.docx')
    rep = OUT / 'c15_report.json'
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out, '--report', rep])
    after = None
    if out.exists():
        _, tx2 = texts_of(out)
        after = tx2[i]
    rec('C15', f'同段三条 replace_text：O1[{a}] 与 O3[{c}] 重叠，O2 在段尾（段 {i}）', 'check 就判重叠冲突 exit 2',
        {'check': r0, 'apply': r, 'before': t[:40], 'after': (after or '')[:40],
         'O3_status_in_report': [o.get('status') for o in json.loads(rep.read_text(encoding='utf-8')).get('ops', [])] if rep.exists() else None},
        'FAIL' if r0['rc'] == 1 else 'ok')


def _synthetic(b52sha):
    """临时目录里造一份 B52 副本：给三段注入 w:br、双 w:t、批注引用（真实书稿里这些结构在别的册/后续批次会出现）。"""
    d = dl.open_docx(B52)
    tx = [dl.para_text(p) for p in d.paras]
    i_br = tx.index('地方党委')
    i_mt = tx.index('基层党组织')
    i_cm = tx.index('党的位置')
    E = etree
    # 1) 地方党委：在文字 run 里 w:t 之前加 w:br（样式“段内换行后接文字”）
    r = d.paras[i_br].find(W + 'r')
    r.insert(list(r).index(r.find(W + 't')), E.Element(W + 'br'))
    # 2) 基层党组织：把单个 w:t 拆成两个 w:t（同一 run）
    r = d.paras[i_mt].find(W + 'r')
    t = r.find(W + 't')
    t.text = '基层'
    t2 = E.Element(W + 't')
    t2.text = '党组织'
    t.addnext(t2)
    # 3) 党的位置：加批注范围与批注引用 run
    p = d.paras[i_cm]
    first_r = p.find(W + 'r')
    cs = E.Element(W + 'commentRangeStart')
    cs.set(W + 'id', '901')
    first_r.addprevious(cs)
    ce = E.Element(W + 'commentRangeEnd')
    ce.set(W + 'id', '901')
    p.append(ce)
    rr = E.SubElement(p, W + 'r')
    cr = E.SubElement(rr, W + 'commentReference')
    cr.set(W + 'id', '901')
    out = fresh('synthetic_b52.docx')
    dl.write_docx(d, out)
    return out, sha(out)


def c16_run_level(b52sha):
    syn, ssha = _synthetic(b52sha)
    res = {}
    cases = [
        ('br', [{'id': 'R1', 'op': 'set_format', 'anchor': {'text': '地方党委'}, 'old': '党委',
                 'format': {'color': 'FF0000'}, 'reason': 'r', 'evidence': 'e'}]),
        ('multi_t', [{'id': 'R2', 'op': 'replace_text', 'anchor': {'text': '基层党组织'}, 'old': '基层党组织',
                      'new': '基层党的组织', 'reason': 'r', 'evidence': 'e'}]),
        ('comment', [{'id': 'R3', 'op': 'replace_paragraph', 'anchor': {'text': '党的位置'}, 'old': '党的位置',
                      'new': '党的地位', 'reason': 'r', 'evidence': 'e'}]),
    ]
    for name, ops in cases:
        pp = wpatch(f'c16_{name}', ops, ssha)
        out = fresh(f'c16_{name}.docx')
        r = run(['apply', '--docx', syn, '--patch', pp, '--out', out, '--profile', 'bixiu3'])
        g = {'rc': r['rc'], 'err': r['err'][-160:]}
        if out.exists():
            d = dl.open_docx(out)
            tx = [dl.para_text(p) for p in d.paras]
            key = {'br': '地方党委', 'multi_t': '基层党', 'comment': '党的'}[name]
            j = [k for k, t in enumerate(tx) if t.startswith(key) and len(t) <= 12][0]
            p = d.paras[j]
            g.update({'text_after': tx[j], 'br_count': len(p.findall('.//' + W + 'br')),
                      'commentReference': len(p.findall('.//' + W + 'commentReference')),
                      'commentRange': len(p.findall(W + 'commentRangeStart')) + len(p.findall(W + 'commentRangeEnd'))})
        res[name] = g
    bad = (res['br'].get('br_count', 0) > 1 or res['multi_t'].get('text_after') not in (None, '基层党的组织')
           or (res['comment'].get('rc') == 0 and res['comment'].get('commentReference') == 0))
    rec('C16', '合成稿：run 内含 w:br 时 set_format；同一 run 两个 w:t 时 replace_text；带批注引用的段 replace_paragraph',
        'br 不重复、文字正确、带批注段按复杂段拒绝', res, 'FAIL' if bad else 'ok')


def c17_health_masking(b52sha):
    d = dl.open_docx(B52)
    P = bh.Prof(load_profile('bixiu3'))
    blocks = bh.walk(d.items, P)
    tx = [it['text'] for it in d.items]
    tgt = None
    for b in blocks:
        if b['title_i'] in (12263, 12659) or b['labels'].get('【细则】', 0) != 1:
            continue
        for i in b['paras']:
            it = d.items[i]
            if it['label'] == '【细则】' and it['tbl'] is None and not d.paras[i].findall('.//' + W + 'drawing'):
                tgt = i
                break
        if tgt:
            break
    anchor = {'text': tx[tgt], 'index_hint': tgt}
    if tgt and tx[tgt - 1]:
        anchor['prev'] = tx[tgt - 1][:15]
    ops = [{'id': 'H1', 'op': 'delete_paragraph', 'anchor': anchor, 'old': tx[tgt], 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c17_patch', ops, b52sha)
    out = fresh('c17_out.docx')
    rep = OUT / 'c17_report.json'
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out, '--health', '--report', rep])
    h = json.loads(rep.read_text(encoding='utf-8')).get('health') if rep.exists() else None
    rec('C17', f'删掉另一例题块唯一的【细则】标签段（段 {tgt}）后 --health', '新增“栏目缺失”FAIL 应计入 new_FAIL 并 exit 1',
        {'run': r, 'health': h}, 'FAIL' if h and h.get('output_FAIL', 0) > h.get('input_FAIL', 0) and not h.get('new_FAIL_count') else 'ok')


def c21_malformed(b52sha):
    ops = [{'id': 'M1', 'op': 'replace_text', 'anchor': {'text': '地方党委', 'style': '题目材料'}, 'old': '地方党委'}]
    pp = wpatch('c21_patch', ops, b52sha)
    r = run(['check', '--docx', B52, '--patch', pp])
    rec('C21', 'replace_text 缺 new', 'exit 2 且中文说明缺哪个字段', r, 'minor' if "'new'" in r['err'] else 'ok')


def c22_single_run_tail_loss(b52sha):
    d = dl.open_docx(B52)
    P = bh.Prof(load_profile('bixiu3'))
    bh.walk(d.items, P)
    from collections import Counter
    tx = [it['text'] for it in d.items]
    cnt = Counter(tx)
    pick = None
    for i, it in enumerate(d.items):
        t = tx[i]
        if it['zone'] != 'teaching' or it['tbl'] is not None or cnt[t] != 1 or not (30 <= len(t) <= 120):
            continue
        runs = [r for r in d.paras[i].iter(W + 'r') if r.find(W + 't') is not None]
        if len(runs) == 1 and ''.join(x.text or '' for x in runs[0].findall(W + 't')) == t:
            old = t[8:12]
            if t.count(old) == 1:
                pick = (i, t, old)
                break
    i, t, old = pick
    ops = [{'id': 'T1', 'op': 'replace_text', 'anchor': {'text': t}, 'old': old, 'new': old + '（改）',
            'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c22_patch', ops, b52sha)
    out = fresh('c22_out.docx')
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out])
    after = None
    if out.exists():
        _, tx2 = texts_of(out)
        after = tx2[i]
    expect = t.replace(old, old + '（改）')
    rec('C22', f'单 run 段落中间子串 replace_text（段 {i}，old={old!r}）', '只替换 old，其余文字不变',
        {'run': r, 'before': t, 'expected': expect, 'after': after, 'lost_chars': len(expect) - len(after or '')},
        'FAIL' if after is not None and after != expect else 'ok')


def c12b_insert_source_style(b52sha):
    d = dl.open_docx(B52)
    P = bh.Prof(load_profile('bixiu3'))
    bh.walk(d.items, P)
    tx = [it['text'] for it in d.items]
    tgt = None
    for i in range(1, len(d.items)):
        a, b = d.items[i - 1], d.items[i]
        if a['zone'] == 'source' and b['zone'] == 'teaching' and b['tbl'] is None and a['tbl'] is None and b['text'] and \
                tx.count(b['text']) == 1 and a['text'] and tx.count(a['text']) == 1:
            tgt = i
            break
    new_text = '（2）结合材料，说明其中的道理。'
    ops = [{'id': 'Z2', 'op': 'insert_before', 'anchor': {'text': tx[tgt]},
            'paragraphs': [{'text': new_text, 'clone_from': tx[tgt - 1]}], 'reason': 'r', 'evidence': 'e'}]
    pp = wpatch('c12b_patch', ops, b52sha)
    out = fresh('c12b_out.docx')
    r = run(['apply', '--docx', B52, '--patch', pp, '--out', out, '--health', '--report', OUT / 'c12b_report.json'])
    zone_new = None
    if out.exists():
        d2 = dl.open_docx(out)
        bh.walk(d2.items, P)
        zone_new = [(it['i'], it['zone'], it['style']) for it in d2.items if it['text'] == new_text]
    rec('C12b', f'insert_before 首个教学标签段（段 {tgt}），新段克隆上一段题面样式，不带 source_zone', '应要求 source_zone（新段落落进题面区）',
        {'run': r, 'anchor_zone': d.items[tgt]['zone'], 'new_para_zone_in_output': zone_new},
        'FAIL' if zone_new and zone_new[0][1] == 'source' else 'ok')


def main():
    global OUT
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--only')
    a = ap.parse_args()
    OUT = Path(a.out).resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    before = snap()
    b52sha, b230sha = sha(B52), sha(B230)
    todo = [('C01', c01_diff_report_unguarded, ()), ('C02', c02_json_overwrite_in_build, ()),
            ('C03', c03_leftover_on_report_refusal, (b52sha,)), ('C04', c04_c06_frozen_bypass, (b230sha,)),
            ('C19b', c19b_symlink_out_guard, ()), ('C08', c08_no_parent_sha, ()), ('C09', c09_index_only, (b52sha,)),
            ('C10', c10_idempotency_new_contains_old, (b52sha,)), ('C11', c11_empty_cell, (b52sha,)),
            ('C12', c12_insert_into_source, (b52sha,)), ('C13', c13_forbidden_split_runs, (b52sha,)),
            ('C14', c14_style_and_clone, (b52sha,)), ('C15', c15_overlap_three_ops, (b52sha,)),
            ('C16', c16_run_level, (b52sha,)), ('C17', c17_health_masking, (b52sha,)), ('C21', c21_malformed, (b52sha,)),
            ('C22', c22_single_run_tail_loss, (b52sha,)), ('C12b', c12b_insert_source_style, (b52sha,))]
    only = set(a.only.split(',')) if a.only else None
    for cid, fn, args in todo:
        if only and cid not in only:
            continue
        try:
            fn(*args)
        except Exception as e:  # 用例自身出错也记下来
            rec(cid, fn.__name__, '-', {'harness_error': repr(e)}, 'harness_error')
    after = snap()
    rec('SNAP', '真实输入 SHA+mtime 前后比对', 'unchanged', {'unchanged': before == after}, 'ok' if before == after else 'FAIL')
    (OUT / ('verify_results.json' if not only else f'verify_results_{a.only}.json')).write_text(
        json.dumps(RES, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
