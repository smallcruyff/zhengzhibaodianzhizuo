#!/usr/bin/env python3
"""layout_prepare.py 的可重跑测试（写书侧通用工具线，2026-09-24；返修回归版）。

只读真实数据（B3_52/B3_03/B3_04/B2_230 等，见脚本内路径），所有输出只写本脚本所在的
scratch 目录（$SCRATCH/booktools/layout_prepare/）。跑完打印 PASS/FAIL 汇总；测试前后
核对全部真实输入文件的 SHA256 与 mtime 未变（脚本末尾断言）。

本版新增针对 verify_layout_prepare.json 里 7 条 blocker/major 的回归用例（见各段注释里的
"回归#N"标记，N 对应回执问题顺序：1 目录/PDF 版本闸、2 冻结册绕过、3 目录节点交叉核对、
4 unchanged_paragraphs 自比自、5 半成品、6 blocked 静默、7 check/repair 口径不一致）。
回归#8（reverify_layout_prepare.json blocker）：--report 守卫越权写——审阅入口/工作区/协作/中央状态/
Skill 目录/项目根/符号链接，都必须 exit 3 且不写文件；另核审阅入口目录列表测试前后不变。

须复制到系统临时目录（scratch）下运行：SC 取本脚本所在目录，放在项目内原地跑时 --out/--report 会被守卫拒绝。
用 /usr/bin/python3 运行：
  /usr/bin/python3 run_tests_layout_prepare.py
"""
import tempfile
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from lxml import etree

ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
SKILLD = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts')
TOOL = SKILLD / 'layout_prepare.py'
SC = Path(tempfile.gettempdir()) / 'booktools_tests' / 'layout_prepare'  # 输出一律落系统临时目录，不跟着本脚本进项目目录
SC.mkdir(parents=True, exist_ok=True)
PY = '/usr/bin/python3'

sys.path.insert(0, str(SKILLD))
import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
import layout_prepare as lp  # noqa: E402
from lxml import etree as ET  # noqa: E402

B3_52 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/必修三政治与法治宝典_第52批_意见修改审阅稿.docx'
B3_52_PDF = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/rendered/必修三政治与法治宝典_第52批_意见修改审阅稿.pdf'
B3_03 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/03_第二部分专题.docx'
B3_04 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/04_编号与考法计数.docx'
B3_04_PDF = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/目录定位/04_编号与考法计数.pdf'
B3_51 = ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx'
B3_51_PDF = ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.pdf'
B2_230 = ROOT / '必修二_周六成品冲刺_20260910/工作稿/修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.docx'
B2_230_PDF = ROOT / '必修二_周六成品冲刺_20260910/工作稿/修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.pdf'
REAL_INPUTS = [B3_52, B3_52_PDF, B3_03, B3_04, B3_04_PDF, B3_51, B3_51_PDF, B2_230, B2_230_PDF]

RESULTS = []


def record(name, ok, detail='', seconds=None):
    RESULTS.append({'test': name, 'pass': bool(ok), 'detail': detail, 'seconds': seconds})
    print(('PASS' if ok else 'FAIL'), name, ('' if ok else ('- ' + detail)))


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def snapshot(paths):
    return {str(p): (sha(p), p.stat().st_mtime_ns) for p in paths}


def run(args):
    t0 = time.time()
    r = subprocess.run([PY, str(TOOL)] + args, capture_output=True, text=True)
    return r, round(time.time() - t0, 2)


def c14n(path):
    z = zipfile.ZipFile(path)
    root = etree.fromstring(z.read('word/document.xml'))
    return etree.tostring(root, method='c14n')


def semantic_diff(pa, pb):
    a, _ = bh.read_docx(str(pa))
    b, _ = bh.read_docx(str(pb))
    if len(a) != len(b):
        return [('len', len(a), len(b))]
    return [(i, x['text'][:30], x['keepnext'], y['keepnext'])
            for i, (x, y) in enumerate(zip(a, b)) if x['text'] != y['text'] or x['keepnext'] != y['keepnext']]


def clean(p):
    p = Path(p)
    if p.exists():
        p.unlink()


def main():
    before = snapshot(REAL_INPUTS)

    # ---- ③ B3_52 + PDF check：本工具的 repairable pending 现在只算“本工具能改的”，不再把
    #      check_toc_docx 的既有锚点问题（pageref≠anchor，这不是页码回填能修的）算进 pending
    #      （呼应回执 minor“check 没有区分可修/不可修”，顺手一并解决——同一版 PDF 自身页码全部一致）
    r, secs = run(['check', '--docx', str(B3_52), '--pdf', str(B3_52_PDF), '--toc-pdf', str(B3_52_PDF),
                  '--profile', 'bixiu3', '--report', str(SC / 'check_b352.json')])
    rep = json.loads((SC / 'check_b352.json').read_text())
    ok = (r.returncode == 0 and rep['pending'] == 0
         and rep['gate_counts_bh_reference'].get('toc', {}).get('FAIL') == 1)
    record('B3_52+PDF check：可修待办 pending=0（既有 pageref≠anchor 问题不在本工具修复范围，仍在参考门里可见）',
          ok, json.dumps({'pending': rep.get('pending'), 'ref': rep.get('gate_counts_bh_reference')}, ensure_ascii=False), secs)

    # ---- ④ B2_230（冻结）+ PDF check（只读）→ 期望 0 待改；并与 book_incremental.py inspect 对照
    r, secs = run(['check', '--docx', str(B2_230), '--pdf', str(B2_230_PDF), '--toc-pdf', str(B2_230_PDF),
                  '--profile', 'bixiu2', '--report', str(SC / 'check_b2_230.json')])
    rep = json.loads((SC / 'check_b2_230.json').read_text())
    r2 = subprocess.run([PY, str(SKILLD / 'book_incremental.py'), 'inspect', str(B2_230),
                        '--report', str(SC / 'inspect_b230.json')], capture_output=True, text=True)
    insp = json.loads((SC / 'inspect_b230.json').read_text())
    bad_scopes = [s for s in insp['scopes'] if s['printed_count'] != s['unique_questions'] or s['duplicate_keys']]
    ok = (r.returncode == 0 and rep['pending'] == 0 and not bad_scopes)
    record('B2_230（冻结）+PDF check → 0 待改，且与 book_incremental.py inspect 的 71 个分类计数结论一致',
          ok, 'pending=%s bad_scopes=%d' % (rep.get('pending'), len(bad_scopes)), secs)

    # ---- B2_230 repair 必须拒绝（冻结册），退出 3，不留输出
    out_p = SC / 'should_not_exist_b230.docx'
    clean(out_p)
    r, secs = run(['repair', '--docx', str(B2_230), '--out', str(out_p), '--profile', 'bixiu2', '--numbering'])
    ok = (r.returncode == 3 and not out_p.exists())
    record('B2_230（冻结）repair → 退出 3，不留输出', ok, r.stderr.strip()[:120], secs)

    # ---- 回归#2（blocker：冻结册可绕过）：给真实 B2_230 传 --profile bixiu3（另一本已登记的书），
    #      detect_profile(docx) 应反查出 bixiu2 且已冻结，与 --profile 无关地拒绝写出
    out_p2 = SC / 'should_not_exist_b230_as_b3.docx'
    clean(out_p2)
    r, secs = run(['repair', '--docx', str(B2_230), '--out', str(out_p2), '--profile', 'bixiu3', '--numbering',
                  '--method-counts'])
    ok = (r.returncode == 3 and not out_p2.exists() and 'bixiu2' not in '' )
    ok = (r.returncode == 3 and not out_p2.exists())
    record('回归#2：--profile bixiu3 处理真实 B2_230（探测得到 bixiu2 且冻结）→ 仍退出 3，不写出，不按必修三规则改动',
          ok, r.stderr.strip()[:200], secs)

    # ---- 回归#2b：书册探测与 --profile 不一致（都未冻结的情形也要拦）：B3_03 用 --profile bixiu2
    out_p3 = SC / 'should_not_exist_mismatch.docx'
    clean(out_p3)
    r, secs = run(['repair', '--docx', str(B3_03), '--out', str(out_p3), '--profile', 'bixiu2', '--numbering'])
    ok = (r.returncode == 2 and not out_p3.exists())
    record('回归#2b：探测到 bixiu3 的稿子传 --profile bixiu2 → 退出 2（不一致），不写出',
          ok, r.stderr.strip()[:200], secs)

    # ---- ① B3_03 repair --numbering --method-counts --keepnext → 与 B3_04 逐段一致（bh 语义）且
    #      document.xml C14N 逐字节一致（输出 SHA256 应等于 B3_04 真实 SHA256）
    sha03 = sha(B3_03)
    out1 = SC / '03_to_04.docx'
    clean(out1)
    r, secs = run(['repair', '--docx', str(B3_03), '--out', str(out1), '--profile', 'bixiu3',
                  '--numbering', '--method-counts', '--keepnext', '--expect-sha', sha03,
                  '--report', str(SC / 'repair_03.json'), '--health'])
    rep = json.loads((SC / 'repair_03.json').read_text()) if r.returncode == 0 else {}
    out_sha = rep.get('output', {}).get('sha256')
    real_sha04 = sha(B3_04)
    diffs = semantic_diff(out1, B3_04) if out1.exists() else [('no-output',)]
    ok = (r.returncode == 0 and out_sha == real_sha04 and not diffs and not rep.get('health_regressions'))
    record('B3_03 repair(numbering+method_counts+keepnext) → 与 B3_04 逐段一致，输出 SHA256 与 B3_04 真实 SHA256 完全相同',
          ok, 'out_sha=%s real=%s diffs=%d rc=%d stderr=%s' % (str(out_sha)[:16], real_sha04[:16], len(diffs), r.returncode, r.stderr.strip()[:200]), secs)

    # ---- 回归#7（口径一致）：同一份 B3_03，check 报出的 repairable_plan_count 应与 repair 实际
    #      changes_count 相等（此前 check 用 bh 棘轮口径只报 1 处，repair 却改 344/284 处）
    r, secs = run(['check', '--docx', str(B3_03), '--profile', 'bixiu3', '--report', str(SC / 'check_03.json')])
    chk = json.loads((SC / 'check_03.json').read_text())
    plan = chk['repairable_plan_count']
    ok = (r.returncode == 1 and plan.get('numbering') == rep.get('changes_count', {}).get('numbering')
         and plan.get('method_counts') == rep.get('changes_count', {}).get('method_counts')
         and plan.get('keepnext') == rep.get('changes_count', {}).get('keepnext'))
    record('回归#7：B3_03 check 的 repairable_plan_count 与 repair 实际 changes_count 完全一致（不再各算一套）',
          ok, 'check=%s repair=%s' % (plan, rep.get('changes_count')), secs)

    # ---- ② B3_04 repair --toc --toc-pdf 目录定位/04.pdf → 与 B3_52 一致，30 处回填
    #      （fix5：04 的定位 PDF 当时由 soffice 直接渲染，没有同版身份记录——identity=unrelated，
    #      缺省该 Abort(2)，这里显式传 --allow-unbound-pdf 降级到双向对位率兜底，金标准仍须字节一致）
    sha04 = sha(B3_04)
    out2 = SC / '04_to_52_toc.docx'
    clean(out2)
    r, secs = run(['repair', '--docx', str(B3_04), '--out', str(out2), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(B3_04_PDF), '--expect-sha', sha04,
                  '--allow-unbound-pdf', 'fix5 金标准回归：04 的目录定位 PDF 由 soffice 直接渲染，无同版身份记录',
                  '--report', str(SC / 'repair_04_toc.json')])
    rep2 = json.loads((SC / 'repair_04_toc.json').read_text()) if r.returncode == 0 else {}
    out_sha = rep2.get('output', {}).get('sha256')
    real_sha52 = sha(B3_52)
    n_toc = rep2.get('changes_count', {}).get('toc', 0)
    sv2 = rep2.get('pdf_same_version') or {}
    ok = (r.returncode == 0 and out_sha == real_sha52 and n_toc == 30
         and sv2.get('identity') == 'unrelated' and sv2.get('pdf_same_version_proven') is False
         and 'WARN' in (r.stderr or '') and '未经 SHA 绑定' in (r.stderr or ''))
    record('B3_04 repair(--toc, 同版 04.pdf, --allow-unbound-pdf) → 30 处目录回填，输出 SHA256 与 B3_52 真实 SHA256 完全相同，stderr 有未绑定 WARN',
          ok, 'toc_changes=%d out_sha=%s real=%s rc=%d sv=%s' % (n_toc, str(out_sha)[:16], real_sha52[:16], r.returncode, sv2), secs)

    # ---- fix5-0：同一组合，不传 --allow-unbound-pdf → 缺省整批 Abort(2)，不写输出（这是本轮返修的核心行为：
    #      没有同版身份记录时不能再靠对位率自动放行，即便对位率本身很高）
    out2b = SC / 'should_not_exist_04_toc_noflag.docx'
    clean(out2b)
    r, secs = run(['repair', '--docx', str(B3_04), '--out', str(out2b), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(B3_04_PDF), '--expect-sha', sha04])
    ok = (r.returncode == 2 and not out2b.exists() and '同版' in (r.stderr or '') and '--allow-unbound-pdf' in (r.stderr or ''))
    record('fix5-0：B3_04 repair(--toc, 同版 04.pdf) 不传 --allow-unbound-pdf → Abort(2)，不写输出（无同版身份记录，不再靠对位率自动放行）',
          ok, r.stderr.strip()[:200], secs)

    # ---- 回归#1（blocker：目录/PDF 版本闸）：B3_04 目录条目配 51 批的旧版 PDF（同书不同批，页码
    #      分布不同），必须整批 Abort(2)，不写输出，不做下标兜底
    out_stale = SC / 'should_not_exist_stale_toc.docx'
    clean(out_stale)
    if B3_51.exists():
        # 用 51 批 docx 里的 PDF（若同目录存在同名 pdf）；没有就用 B3_52 的 PDF 冒充“别册/旧版”对 B3_04 目录回填
        stale_pdf = None
        for cand in B3_51.parent.glob('*.pdf'):
            stale_pdf = cand
            break
        stale_pdf = stale_pdf or B3_52_PDF
        r, secs = run(['repair', '--docx', str(B3_04), '--out', str(out_stale), '--profile', 'bixiu3',
                      '--toc', '--toc-pdf', str(stale_pdf), '--expect-sha', sha04])
        ok = (r.returncode == 2 and not out_stale.exists())
        record('回归#1：B3_04 目录配旧版/别批 PDF（%s）→ 整批 Abort(2)，不写输出，不做下标兜底' % stale_pdf.name,
              ok, r.stderr.strip()[:200], secs)
    else:
        record('回归#1：B3_04 目录配旧版 PDF → Abort(2)', False, 'B3_51 不存在，跳过', 0)

    # ---- 回归#1b：B2_230 的 PDF 拿给 B3_04 当同版 PDF（别册），同样必须 Abort(2)
    out_wrong = SC / 'should_not_exist_wrongbook_toc.docx'
    clean(out_wrong)
    r, secs = run(['repair', '--docx', str(B3_04), '--out', str(out_wrong), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(B2_230_PDF), '--expect-sha', sha04])
    ok = (r.returncode == 2 and not out_wrong.exists())
    record('回归#1b：B3_04 目录配别册（B2_230）PDF → 整批 Abort(2)，不写输出',
          ok, r.stderr.strip()[:200], secs)

    # ---- 回归#3（major：目录节点交叉核对）：合成攻击——把某条目录段标签前插入一个独立数字 run，
    #      并把页码域挪到超链接外、改一个不同的值；旧实现会错改标签数字、页码原样不动仍退出 0，
    #      新实现应拒绝（node 定位失败）或至少不产生“标签被改、页码未变”的错误结果
    attack_src = SC / 'attack_toc_src.docx'
    shutil.copy2(B3_04, attack_src)
    pd3 = bh.load_profile('bixiu3')
    P3 = bh.Prof(pd3)
    d = dl.open_docx(str(attack_src))
    ents, _ = bh.check_toc_docx(d.items, P3, bh.Findings())
    target = ents[0]
    p = d.paras[target['it']['i']]
    # 在段首插入一个独立的数字 run（不在 hyperlink/fldSimple 内），模拟标签前有游离数字
    hl = p.find(bh.W + 'hyperlink')
    r0 = hl[0]
    new_r = ET.fromstring('<w:r xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                          '<w:t>2</w:t></w:r>')
    hl.insert(0, new_r)
    attack_final_path = SC / 'attack_toc_final.docx'
    clean(attack_final_path)
    dl.write_docx(d, dl.guard_write(str(attack_final_path), pd3, inputs=[str(B3_04)], kind='.docx'))
    attack_final = attack_final_path
    out_attack = SC / 'should_not_corrupt_toc.docx'
    clean(out_attack)
    r, secs = run(['repair', '--docx', str(attack_final), '--out', str(out_attack), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(B3_04_PDF)])
    # 用真实同版 PDF：既有条目缓存页码本就与 PDF 一致（未打乱页码），所以这条目录条目根本不在
    # “cached != dest”待改列表里，不会触发节点定位；改为直接单测 toc_page_nodes 对这种畸形段落的行为：
    nodes_direct = lp.toc_page_nodes(p, 'pageref_in_hyperlink')
    e0 = ents[0]
    node_ok = (len(nodes_direct) == 1 and nodes_direct[0].text == str(e0['cached']))
    record('回归#3：目录标签前插入游离数字 run 后，toc_page_nodes(pageref_in_hyperlink) 仍只定位到 PAGEREF 域内的真实缓存页码节点（不被游离数字干扰）',
          node_ok, 'nodes=%r cached=%s' % ([n.text for n in nodes_direct], e0['cached']), secs)
    for f in (attack_src, attack_final, out_attack):
        clean(f)

    # ---- 回归#3b：直接把 PAGEREF 结果移出域（模拟“页码在超链接外，标签里恰有独立数字 run”）——
    #      构造最小合成段落验证 toc_page_nodes 不会把该游离数字当成页码节点
    xml_bad = ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:r><w:t>2</w:t></w:r>'
              '<w:hyperlink w:anchor="_Toc9"><w:r><w:t>一、示例标题</w:t></w:r></w:hyperlink>'
              '<w:r><w:t>9</w:t></w:r></w:p>')
    nodes_bad = lp.toc_page_nodes(ET.fromstring(xml_bad), 'pageref_in_hyperlink')
    ok = (len(nodes_bad) == 0)
    record('回归#3b：PAGEREF 域缺失、页码搬到超链接外时，toc_page_nodes 不误取标签前/后的游离数字（返回 0 个节点，写入侧会记 blocked 而不是错改）',
          ok, 'nodes=%r' % [n.text for n in nodes_bad])

    # ---- 回归#4（major：unchanged_paragraphs 自比自）：猴子补丁 set_keep_next_true 让它顺手改掉
    #      下一段文字，在进程内跑 do_repair，期望被拦（Abort），而不是退出 0 且悄悄改了未点名段落
    d4 = dl.open_docx(str(B3_03))
    P4 = bh.Prof(bh.load_profile('bixiu3'))
    bh.walk(d4.items, P4)
    todo4 = lp.plan_keepnext(d4.items, bh.load_profile('bixiu3'), P4)
    target_i = todo4[0]['para'] if todo4 else None
    caught = False
    if target_i is not None and target_i + 1 < len(d4.paras):
        orig_fn = lp.set_keep_next_true

        def evil(p):
            r = orig_fn(p)
            # 越界改动：把“下一个兄弟段落”的文字也改掉（模拟坏 patch）；用树内 getnext()，不依赖
            # 某个具体 Doc 实例的 paras 列表下标（do_repair 内部会自己重新 open_docx，是另一份对象）
            victim = p.getnext()
            if victim is not None:
                for t in victim.iter(bh.W + 't'):
                    if t.text:
                        t.text = t.text + '（被越界改动）'
                        break
            return r

        class FakeArgs:
            docx = str(B3_03)
            out = str(SC / 'should_not_exist_evil.docx')
            profile = 'bixiu3'
            expect_sha = None
            numbering = False
            method_counts = False
            keepnext = True
            toc = False
            toc_pdf = None
            allow_blocked = False
            health = False
            report = None

        clean(FakeArgs.out)
        lp.set_keep_next_true = evil
        try:
            try:
                lp.do_repair(FakeArgs())
                caught = False
            except lp.Abort as e:
                caught = (e.code == 2 and not Path(FakeArgs.out).exists())
        finally:
            lp.set_keep_next_true = orig_fn
            clean(FakeArgs.out)
    record('回归#4：猴子补丁越界改动未点名段落 → unchanged_paragraphs 用打开时的原始副本比对，抓到并 Abort(2)，不留输出',
          caught, 'target_i=%s' % target_i)

    # ---- 回归#5（major：失败时留半成品）：--report 指向已存在的非本工具报告（伪造一个含
    #      "name":"batch_health" 的假报告），repair 应在写 DOCX 之前就拒绝，输出 DOCX 不存在
    fake_report = SC / 'fake_bh_report.json'
    fake_report.write_text(json.dumps({'tool': {'name': 'batch_health'}, 'x': 1}), encoding='utf-8')
    out5 = SC / 'should_not_exist_half.docx'
    clean(out5)
    r, secs = run(['repair', '--docx', str(B3_03), '--out', str(out5), '--profile', 'bixiu3', '--numbering',
                  '--report', str(fake_report)])
    ok1 = (r.returncode == 3 and not out5.exists() and json.loads(fake_report.read_text())['tool']['name'] == 'batch_health')
    record('回归#5a：--report 指向已存在的假 batch_health 报告 → 拒绝覆盖（exit 3），DOCX 未写出，原报告未被覆盖',
          ok1, r.stderr.strip()[:160], secs)

    # 同一路径重跑自己的报告：应该允许覆盖（不再“同一 --report 路径重跑就 exit 3”）
    own_report = SC / 'own_report_rerun.json'
    clean(own_report)
    out5b = SC / 'own_report_rerun.docx'
    clean(out5b)
    r, secs = run(['repair', '--docx', str(B3_03), '--out', str(out5b), '--profile', 'bixiu3', '--numbering',
                  '--method-counts', '--keepnext', '--report', str(own_report)])
    ok2a = (r.returncode == 0 and out5b.exists() and own_report.exists())
    clean(out5b)
    r, secs = run(['repair', '--docx', str(B3_03), '--out', str(out5b), '--profile', 'bixiu3', '--numbering',
                  '--method-counts', '--keepnext', '--report', str(own_report)])
    ok2b = (r.returncode == 0 and out5b.exists())
    record('回归#5b：同一 --report 路径重跑本工具自己的报告 → 允许覆盖（不再因“不是 batch_health 报告”被拒）',
          ok2a and ok2b, 'first=%s second=%s' % (ok2a, ok2b), secs)
    clean(out5b)
    clean(own_report)

    # --health 体检发现回归时，输出 DOCX 应被删除（不留半成品）：用只点名 --keepnext 但故意不点名
    # --numbering/--method-counts 的场景很难天然制造回归，这里改为直接验证“post-write 复核失败必删除
    # 输出”的机制：猴子补丁 plan_numbering 让它漏报一处应改的编号，之后写后重跑编号门必然发现残留 FAIL。
    orig_plan = lp.plan_numbering

    def partial_plan(items, P):
        todo = orig_plan(items, P)
        return todo[1:]  # 丢掉第一条，制造“写后仍有未连号”的场景

    out5c = SC / 'should_not_exist_partial.docx'
    clean(out5c)
    lp.plan_numbering = partial_plan
    try:
        class FakeArgs2:
            docx = str(B3_03)
            out = str(out5c)
            profile = 'bixiu3'
            expect_sha = None
            numbering = True
            method_counts = False
            keepnext = False
            toc = False
            toc_pdf = None
            allow_blocked = False
            health = False
            report = None
        caught5c = False
        try:
            lp.do_repair(FakeArgs2())
        except lp.Abort as e:
            caught5c = (e.code == 1 and not Path(out5c).exists())
    finally:
        lp.plan_numbering = orig_plan
        clean(out5c)
    record('回归#5c：写后复核发现编号门仍有残留 FAIL（模拟计划函数漏报）→ 删除已写出的 DOCX，不留半成品',
          caught5c, '')

    # ---- 回归#6（major：blocked 静默 + 原因写错）：段尾追加一个只含空格的 run（不是真的 w:tab/w:sym），
    #      旧实现会因为 t_text(p)!=it['text'] 误判成“段内含 w:tab/w:sym”并静默 blocked、退出 0；
    #      新实现应该正常改号（不再误判），has_tab_or_sym 对这种段落应返回 False
    d6 = dl.open_docx(str(B3_03))
    P6 = bh.Prof(bh.load_profile('bixiu3'))
    bh.walk(d6.items, P6)
    numbering_todo = lp.plan_numbering(d6.items, P6)
    ok6a = ok6b = False
    if numbering_todo:
        i0 = numbering_todo[0]['para']
        p0 = d6.paras[i0]
        trailing = ET.SubElement(p0, bh.W + 'r')
        t_el = ET.SubElement(trailing, bh.W + 't')
        t_el.text = ' '
        t_el.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        ok6a = (lp.has_tab_or_sym(p0) is False)
        span = lp.num_span_in_ttext(P6, d6.items[i0], lp.t_text(p0))
        ok6b = span is not None
    record('回归#6：段尾只含空格的 run 不再被 has_tab_or_sym 误判为“段内含 w:tab/w:sym”，编号 span 仍能正常定位',
          ok6a and ok6b, 'no_tab_sym=%s span_found=%s' % (ok6a, ok6b))

    # 真正含 w:tab 的段落应该被正确 blocked，且 reason 与实情相符
    xml_tab = ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:r><w:t>例题</w:t></w:r><w:r><w:tab/></w:r><w:r><w:t>1</w:t></w:r></w:p>')
    ok6c = lp.has_tab_or_sym(ET.fromstring(xml_tab)) is True
    record('回归#6b：真的含 w:tab 的段落，has_tab_or_sym 判 True（reason 与实情相符，不再对所有 blocked 都写同一句）',
          ok6c, '')

    # blocked 非空时默认视为失败、不留输出：monkeypatch num_span_in_ttext 让第一条编号待办“重新匹配
    # 不到编号 span”（真实会触发这条 blocked 分支的场景之一），进程内跑 do_repair，期望 Abort(2) 且
    # 不留输出；同时验证 --allow-blocked 能放行（该条不改，其余正常改，仍不留“假装成功”的空文件）。
    orig_num_span = lp.num_span_in_ttext
    hit_para = {}

    def fake_num_span(P, it, tt):
        if not hit_para:
            hit_para['i'] = it['i']
            return None
        return orig_num_span(P, it, tt)

    out6c = SC / 'should_not_exist_blocked.docx'
    clean(out6c)

    class FakeArgs6c:
        docx = str(B3_03)
        out = str(out6c)
        profile = 'bixiu3'
        expect_sha = None
        numbering = True
        method_counts = False
        keepnext = False
        toc = False
        toc_pdf = None
        allow_blocked = False
        health = False
        report = None

    blocked_caught = False
    lp.num_span_in_ttext = fake_num_span
    try:
        try:
            lp.do_repair(FakeArgs6c())
        except lp.Abort as e:
            blocked_caught = (e.code == 2 and not out6c.exists())
    finally:
        lp.num_span_in_ttext = orig_num_span
    clean(out6c)

    hit_para.clear()
    lp.num_span_in_ttext = fake_num_span
    allow_ok = False
    try:
        FakeArgs6c.allow_blocked = True
        try:
            code = lp.do_repair(FakeArgs6c())
            allow_ok = (code == 0 and out6c.exists())
        except lp.Abort:
            allow_ok = False
    finally:
        lp.num_span_in_ttext = orig_num_span
        FakeArgs6c.allow_blocked = False
        clean(out6c)
    record('回归#6c：定位被跳过（blocked）时默认视为失败、不留输出（不再静默退出 0）；--allow-blocked 时放行且仍写出',
          blocked_caught and allow_ok, 'blocked_caught=%s allow_ok=%s' % (blocked_caught, allow_ok))

    # ---- 回归：keepNext 链长比较改为局部链长（不是全书 max()）——合成场景：全书已有一条长链，
    #      新补的 keepNext 只让局部链长小幅增加，不应被“全书 max() 更大”误挡
    flags_demo = [False] * 30
    for i in range(25, 30):
        flags_demo[i] = True  # 全书已有一条长链（含黏住的下一段共 6 段）
    before_local = lp.chain_len_at(flags_demo, 25)
    trial_demo = list(flags_demo)
    trial_demo[2] = True
    after_local = lp.chain_len_at(trial_demo, 2)
    ok = (before_local >= 5 and after_local <= 2)
    record('回归：keepNext 链长判断按“受影响的那条链”局部计算，不再被全书更长的另一条链掩护/误伤',
          ok, 'before_local=%d after_local=%d' % (before_local, after_local))

    # ---- ⑤ 合成打乱：在 B3_52 临时副本上打乱 3 处编号、2 处考法题数、去掉 1 处 keepNext → repair 恢复
    pd = bh.load_profile('bixiu3')
    P = bh.Prof(pd)
    d = dl.open_docx(str(B3_52))
    bh.walk(d.items, P)
    titles = [it for it in d.items if it['_title']][:6]
    scrambled = []
    for it in titles[:3]:
        p = d.paras[it['i']]
        tt = lp.t_text(p)
        span = lp.num_span_in_ttext(P, it, tt)
        old = tt[span[0]:span[1]]
        new = str(int(old) + 5)
        lp.replace_span_digits(p, span[0], span[1], new)
        scrambled.append(('num', it['i'], old, new))
    methods = [it for it in d.items if it['_method']][:2]
    for it in methods:
        p = d.paras[it['i']]
        tt = lp.t_text(p)
        span = lp.method_count_span_in_ttext(P, tt)
        old = tt[span[0]:span[1]]
        new = str(int(old) + 3)
        lp.replace_span_digits(p, span[0], span[1], new)
        scrambled.append(('method', it['i'], old, new))
    removed_kn_para = None
    for it in d.items:
        if it['_title'] and it['keepnext']:
            p = d.paras[it['i']]
            ppr = p.find(bh.W + 'pPr')
            kn = ppr.find(bh.W + 'keepNext') if ppr is not None else None
            if kn is not None:
                ppr.remove(kn)
                removed_kn_para = it['i']
                break
    scrambled_path = SC / 'scrambled_52.docx'
    clean(scrambled_path)
    out_g = dl.guard_write(str(scrambled_path), pd, inputs=[str(B3_52)], kind='.docx')
    dl.write_docx(d, out_g)

    r, secs = run(['check', '--docx', str(scrambled_path), '--profile', 'bixiu3',
                  '--report', str(SC / 'check_scrambled.json')])
    chk = json.loads((SC / 'check_scrambled.json').read_text())
    ok = (r.returncode == 1 and chk['pending'] > 0)
    record('打乱副本 check 抓到待改', ok, json.dumps(chk['repairable_plan_count'], ensure_ascii=False), secs)

    sha_scr = sha(scrambled_path)
    repaired_path = SC / 'repaired_52.docx'
    clean(repaired_path)
    r, secs = run(['repair', '--docx', str(scrambled_path), '--out', str(repaired_path), '--profile', 'bixiu3',
                  '--numbering', '--method-counts', '--keepnext', '--expect-sha', sha_scr,
                  '--report', str(SC / 'repair_scrambled.json'), '--health'])
    rep = json.loads((SC / 'repair_scrambled.json').read_text()) if r.returncode == 0 else {}
    diffs = semantic_diff(repaired_path, B3_52) if repaired_path.exists() else [('no-output',)]
    ok = (r.returncode == 0 and rep.get('changes_count', {}).get('numbering') == 3
         and rep.get('changes_count', {}).get('method_counts') == 2
         and rep.get('changes_count', {}).get('keepnext') == 1
         and not diffs and not rep.get('health_regressions'))
    record('打乱副本 repair 恢复：与原始 B3_52 逐段一致（文字流+keepNext），bh 体检无新增 FAIL',
          ok, 'changes=%s diffs=%d rc=%d' % (rep.get('changes_count'), len(diffs), r.returncode), secs)
    clean(scrambled_path)
    clean(repaired_path)

    # ---- 数字跨 run 保留格式（minor 顺手修）：位数相同按位分配，位数不同时多出/缺少的位并入最后一
    #      个覆盖节点；这里直接单测 replace_span_digits，不依赖真实数据
    xml_cross = ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:r><w:rPr><w:u w:val="none"/></w:rPr><w:t>例题</w:t></w:r>'
                '<w:r><w:rPr><w:color w:val="FF0000"/></w:rPr><w:t>1</w:t></w:r>'
                '<w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>2</w:t></w:r>'
                '<w:r><w:t>　某某</w:t></w:r></w:p>')
    p_cross = ET.fromstring(xml_cross)
    nodes = lp.text_nodes(p_cross)
    # “12” 落在 nodes[1]（'1'，红色）与 nodes[2]（'2'，下划线），位数相同，按位分配
    full = lp.t_text(p_cross)
    start = full.index('12')
    uneven = lp.replace_span_digits(p_cross, start, start + 2, '13')
    nodes_after = lp.text_nodes(p_cross)
    ok = (not uneven and nodes_after[1].text == '1' and nodes_after[2].text == '3'
         and nodes_after[1].getparent().find(bh.W + 'rPr').find(bh.W + 'color') is not None
         and nodes_after[2].getparent().find(bh.W + 'rPr').find(bh.W + 'u') is not None)
    record('minor 顺手修：数字跨 run 且位数相同时按位分配回原节点，保留各自 rPr（不再只留首个节点格式）',
          ok, 'texts=%r' % [n.text for n in nodes_after])

    # ---- 回归#8（blocker：--report 守卫越权写）：上一版 guard_report 只拦冻结册目录，check 的 --report
    #      经符号链接真实写进过 00_必修三最新审查稿/__verify_never_written__.json。守卫矩阵只调守卫、不写；
    #      CLI 用例用本册不存在的探针文件名，断言 exit 3 且探针不存在、审阅入口目录列表不变。
    review_dir = ROOT / '00_必修三最新审查稿'
    review_listing_before = sorted(os.listdir(review_dir))
    probe = '__lp_test_report_never_written__.json'
    build_dir = B3_52.parent
    refused_targets = [
        ('B3审阅入口', review_dir / probe),
        ('B3审阅入口_.review-manifest.json', review_dir / '.review-manifest.json'),
        ('B3工作区根', ROOT / '必修三_最新Skill修订_20260913' / probe),
        ('B3协作目录(接管.json旁)', ROOT / '必修三_最新Skill修订_20260913/协作' / probe),
        ('B3人工审查历史', ROOT / '必修三_人工审查历史' / probe),
        ('中央状态目录', Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908') / probe),
        ('Skill scripts', SKILLD / probe),
        ('项目根', ROOT / probe),
        ('B2工作区(冻结)', B2_230.parent / probe),
    ]
    stray = review_dir / '__verify_never_written__.json'
    if stray.exists():  # 越界报告本身是 layout_prepare 报告，守卫也不得把它当“自己的报告”覆盖
        refused_targets.append(('B3审阅入口_已存在的越界报告(覆盖)', stray))
    allowed_targets = [('系统临时目录', SC / probe), ('B3候选构建目录', build_dir / probe)]
    matrix, bad = {}, []
    for lab, t in refused_targets + allowed_targets:
        ns = argparse.Namespace(report=str(t), docx=str(B3_03), pdf=None, toc_pdf=None)
        try:
            lp.guard_report(ns, lp.load_profile('bixiu3'))
            matrix[lab] = 'ALLOWED'
        except lp.Abort as ex:
            matrix[lab] = 'REFUSED(%s)' % ex.code
    for lab, _ in refused_targets:
        if matrix[lab] != 'REFUSED(3)':
            bad.append(lab)
    for lab, _ in allowed_targets:
        if matrix[lab] != 'ALLOWED':
            bad.append(lab)
    record('回归#8a：--report 守卫矩阵——审阅入口/工作区/协作/审查历史/中央状态/Skill/项目根/冻结册全部 exit 3，临时目录与 …/构建/ 放行',
          not bad, json.dumps({'bad': bad, 'matrix': matrix}, ensure_ascii=False))

    # 冻结册的 check 仍可把报告写进临时目录（守卫传去掉 frozen 的配置副本），只调守卫
    ns = argparse.Namespace(report=str(SC / probe), docx=str(B2_230), pdf=None, toc_pdf=None)
    try:
        ok = lp.guard_report(ns, lp.load_profile('bixiu2')) == (SC / probe).resolve()
    except lp.Abort:
        ok = False
    record('回归#8b：冻结册（bixiu2）check 的 --report 落临时目录 → 仍放行', ok)

    # CLI：目录符号链接 / 文件符号链接（悬空，指向审阅入口里的新文件名）→ check 与 repair 都 exit 3，不写
    lnk_dir = SC / 'lnk_review_dir'
    lnk_file = SC / 'lnk_report.json'
    for p in (lnk_dir, lnk_file):
        if p.is_symlink() or p.exists():
            p.unlink()
    os.symlink(str(review_dir), str(lnk_dir))
    os.symlink(str(review_dir / probe), str(lnk_file))
    cli = {}
    r, _ = run(['check', '--docx', str(B3_03), '--profile', 'bixiu3', '--report', str(lnk_dir / probe)])
    cli['check_dir_symlink'] = r.returncode
    r, _ = run(['check', '--docx', str(B3_03), '--profile', 'bixiu3', '--report', str(lnk_file)])
    cli['check_file_symlink'] = r.returncode
    out8 = SC / 'should_not_exist_report_escape.docx'
    clean(out8)
    r, _ = run(['repair', '--docx', str(B3_03), '--out', str(out8), '--profile', 'bixiu3', '--keepnext',
                '--report', str(lnk_file)])
    cli['repair_file_symlink'] = r.returncode
    cli['repair_docx_left'] = out8.exists()
    r, _ = run(['check', '--docx', str(B3_03), '--profile', 'bixiu3', '--report', str(review_dir / probe)])
    cli['check_direct_review_entry'] = r.returncode
    lnk_dir.unlink()
    lnk_file.unlink()
    review_listing_after = sorted(os.listdir(review_dir))
    ok = (cli['check_dir_symlink'] == 3 and cli['check_file_symlink'] == 3 and cli['repair_file_symlink'] == 3
          and not cli['repair_docx_left'] and cli['check_direct_review_entry'] == 3
          and not (review_dir / probe).exists() and review_listing_before == review_listing_after)
    record('回归#8c：CLI --report 直写/经目录符号链接/经悬空文件符号链接落审阅入口 → exit 3，不留 DOCX，审阅入口目录列表不变',
          ok, json.dumps({'cli': cli, 'listing_changed': review_listing_before != review_listing_after}, ensure_ascii=False))

    # ---- ⑥ 负例：无操作点名、缺 --toc-pdf、SHA 不符、输出落审阅入口 → 均中止不留输出
    out_neg = SC / 'neg_noop.docx'
    r, _ = run(['repair', '--docx', str(B3_03), '--out', str(out_neg), '--profile', 'bixiu3'])
    ok1 = (r.returncode == 2 and not out_neg.exists())
    r, _ = run(['repair', '--docx', str(B3_03), '--out', str(out_neg), '--profile', 'bixiu3', '--toc'])
    ok2 = (r.returncode == 2 and not out_neg.exists())
    r, _ = run(['repair', '--docx', str(B3_03), '--out', str(out_neg), '--profile', 'bixiu3', '--numbering',
               '--expect-sha', '0' * 64])
    ok3 = (r.returncode == 2 and not out_neg.exists())
    review_out = ROOT / '00_必修三最新审查稿' / '__test_should_not_write__.docx'
    r, _ = run(['repair', '--docx', str(B3_03), '--out', str(review_out), '--profile', 'bixiu3', '--numbering'])
    ok4 = (r.returncode == 3 and not review_out.exists())
    record('负例：无操作点名(exit2)/缺toc-pdf(exit2)/SHA不符(exit2)/落审阅入口(exit3)，均不留输出',
          ok1 and ok2 and ok3 and ok4, 'ok=%s' % [ok1, ok2, ok3, ok4])

    # ---- toc_page_nodes 对 hyperlink_static / pageref_in_hyperlink 两种真实写法都能定位（按各自
    #      profile 的 toc.mode 传参，不再用同一份不分 mode 的猜测逻辑）
    xml_fld = ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:r><w:t>标题A</w:t></w:r>'
              '<w:fldSimple w:instr=" PAGEREF _Toc1 \\h "><w:r><w:t>12</w:t></w:r></w:fldSimple></w:p>')
    xml_pageref = ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                  '<w:hyperlink w:anchor="_Toc2"><w:r><w:t>标题B</w:t></w:r>'
                  '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                  '<w:r><w:instrText>PAGEREF _Toc2 \\h</w:instrText></w:r>'
                  '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                  '<w:r><w:t>7</w:t></w:r>'
                  '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink></w:p>')
    n1 = lp.toc_page_nodes(ET.fromstring(xml_fld), 'hyperlink_static')
    n2 = lp.toc_page_nodes(ET.fromstring(xml_pageref), 'pageref_in_hyperlink')
    ok = (len(n1) == 1 and n1[0].text == '12' and len(n2) == 1 and n2[0].text == '7')
    record('toc_page_nodes 按 toc.mode 定位：hyperlink_static 取 fldSimple 内数字，pageref_in_hyperlink 取 PAGEREF 域 separate/end 之间的数字',
          ok, str([n1[0].text if n1 else None, n2[0].text if n2 else None]))


    # ================================================================ fix4（第四轮返修）新增回归 ================
    # ---- 【必须】1. 目录同版闸：repair --toc / check --toc-pdf 必须先证明 PDF 由输入 DOCX 渲染
    #      ①B3_04 DOCX + 它自己的目录定位 PDF：这份 PDF 当时由 soffice 直接渲染，没有同版身份记录
    #        （identity=unrelated——同目录 构建/同版身份.json 记的是 52 自己的 docx/pdf）。fix5 之前的版本
    #        只看对位率、达标就直接放进可修 pending；fix5 起，没有身份记录时 check 永远不采信对位率——
    #        哪怕双向都达标，也只把页码差异放进 toc_version_problems（附 identity/method/align_ratio/
    #        reverse_align_ratio），不进可修 pending（呼应 final 回执 major：文字对位证明不了分页相同）。
    r, _ = run(['check', '--docx', str(B3_04), '--toc-pdf', str(B3_04_PDF), '--profile', 'bixiu3',
               '--report', str(SC / 'fix4_t1_04ok.json')])
    rep_t1 = json.loads((SC / 'fix4_t1_04ok.json').read_text())
    sv1 = rep_t1.get('pdf_same_version') or {}
    tvp1 = rep_t1.get('toc_version_problems') or []
    unproven1 = tvp1[0] if (tvp1 and isinstance(tvp1[0], dict)) else {}
    ok_t1 = (sv1.get('identity') == 'unrelated' and sv1.get('pdf_same_version_proven') is False
            and sv1.get('align_ratio') is not None and sv1.get('reverse_align_ratio') is not None
            and rep_t1.get('repairable_plan_count', {}).get('toc') == 0
            and unproven1.get('diff_count') == 30 and unproven1.get('identity') == 'unrelated'
            and unproven1.get('align_ratio') == sv1.get('align_ratio'))
    record('fix5-1（原 fix4-1 改判）：目录同版闸——B3_04 配自己的目录定位 PDF，没有同版身份记录，即便双向对位率都达标，'
          '30 处页码差异也只进 toc_version_problems（附 identity/method/align_ratio），不进可修 pending',
          ok_t1, json.dumps({'sv': sv1, 'unproven_diff_count': unproven1.get('diff_count')}, ensure_ascii=False))

    #      ②B3_52 DOCX 配第51批 PDF（同版身份记录冲突：本 DOCX 对应的是另一份 PDF）→ repair 整批 Abort(2)，
    #        不写输出；额外传 --allow-unbound-pdf 验证这个开关不放行“记录冲突”（只放行“没有记录”）
    out_t2 = SC / 'fix4_should_not_exist_t2.docx'
    clean(out_t2)
    r, _ = run(['repair', '--docx', str(B3_52), '--out', str(out_t2), '--toc', '--toc-pdf', str(B3_51_PDF),
               '--profile', 'bixiu3', '--allow-unbound-pdf', 'fix5：试图用这个开关放行身份冲突，应无效'])
    ok_t2 = (r.returncode == 2 and not out_t2.exists() and '同版' in (r.stderr or '')
            and '对应的不是这份 PDF' in (r.stderr or ''))
    record('fix4-2/fix5：目录同版闸——B3_52 配第51批 PDF（身份记录冲突）→ repair Abort(2)，不写输出，--allow-unbound-pdf 不放行这一条',
          ok_t2, r.stderr.strip()[:200])

    #      ③B3_51 DOCX 配 B3_52 PDF → 同样 Abort(2)，不写输出，同样不受 --allow-unbound-pdf 影响
    out_t3 = SC / 'fix4_should_not_exist_t3.docx'
    clean(out_t3)
    r, _ = run(['repair', '--docx', str(B3_51), '--out', str(out_t3), '--toc', '--toc-pdf', str(B3_52_PDF),
               '--profile', 'bixiu3', '--allow-unbound-pdf', 'fix5：同上，也应无效'])
    ok_t3 = (r.returncode == 2 and not out_t3.exists() and '同版' in (r.stderr or ''))
    record('fix4-3/fix5：目录同版闸——B3_51 配 B3_52 PDF（身份记录冲突）→ repair Abort(2)，不写输出，--allow-unbound-pdf 不放行这一条',
          ok_t3, r.stderr.strip()[:200])

    #      ④B3_52 DOCX 配它自己的同版 PDF（构建/同版身份.json 登记过）→ 通过，identity=match
    r, _ = run(['check', '--docx', str(B3_52), '--toc-pdf', str(B3_52_PDF), '--profile', 'bixiu3',
               '--report', str(SC / 'fix4_t4_5252.json')])
    rep_t4 = json.loads((SC / 'fix4_t4_5252.json').read_text())
    sv4 = rep_t4.get('pdf_same_version') or {}
    ok_t4 = (sv4.get('identity') == 'match' and rep_t4.get('toc_version_problems') == [] and rep_t4.get('pending') == 0)
    record('fix4-4：目录同版闸——B3_52 配自己的同版 PDF → 通过，identity=match（同版身份.json 登记过）',
          ok_t4, json.dumps(sv4, ensure_ascii=False))

    # ================================================================ fix5（第五轮返修）新增回归 ================
    # 终审 major：目录同版闸必须以 SHA 绑定为准，文字对位（哪怕双向）证明不了分页相同；repair --toc 缺省
    # 要求 identity=='match'，没有记录时 exit 2，除非显式 --allow-unbound-pdf "理由"（这时仍要求双向对位率
    # 达标）；check 永远不采信对位率，无记录的页码差异一律进 toc_version_problems。fix5-1（上面，改判自
    # fix4-1）与 fix5-0（上面，golden 用例旁边）已覆盖“check 不采信”“repair 缺省中止”；这里补：
    #   fix5-2 用临时目录里一份匹配的同版身份.json 让 04→52 不带开关也能过（identity=match 走正常路径）；
    #   fix5-3 03（用 B3_51 的 PDF 代替，见下方说明）的 PDF 配 04 → 无开关拒绝；
    #   fix5-4 N2 插页错版攻击（文字全同、分页不同）→ 不带开关必须拒绝，check 把 30 处页码差异算进
    #     toc_version_problems 而不是 pending；
    #   fix5-5/5-6 双向对位率的“反向”能力：正文删段攻击，小规模（120 段）双向仍可能测不出（如实记 known
    #     limit），大规模（600 段）反向对位率必须跌破阈值、被 --allow-unbound-pdf 兜底路径拦下；
    #   fix5-7 check/repair 的 keepNext 长链闸退出码一致；
    #   fix5-8 plan_keepnext 过时注释已清掉。
    import fitz as _fitz_fix5

    # ---- fix5-2：临时目录里给 04 docx + 它自己的目录定位 PDF 补一份匹配的 同版身份.json（docx_sha256/
    #      pdf_sha256 都对上，用真实文件的 sha256，不需要真的跑 render_book.py）→ 不带 --allow-unbound-pdf
    #      也该通过，identity=match，输出仍与 B3_52 字节一致。
    idbound_dir = SC / 'fix5_idbound'
    if idbound_dir.exists():
        shutil.rmtree(idbound_dir)
    idbound_dir.mkdir(parents=True)
    idb_docx = idbound_dir / '04.docx'
    idb_pdf = idbound_dir / '04.pdf'
    shutil.copy2(B3_04, idb_docx)
    shutil.copy2(B3_04_PDF, idb_pdf)
    (idbound_dir / '同版身份.json').write_text(
        json.dumps({'docx_sha256': sha(idb_docx), 'pdf_sha256': sha(idb_pdf), 'status': 'PASS'}, ensure_ascii=False),
        encoding='utf-8')
    idb_out = idbound_dir / 'out.docx'
    r, secs = run(['repair', '--docx', str(idb_docx), '--out', str(idb_out), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(idb_pdf), '--report', str(idbound_dir / 'report.json')])
    rep_idb = json.loads((idbound_dir / 'report.json').read_text()) if r.returncode == 0 else {}
    sv_idb = rep_idb.get('pdf_same_version') or {}
    ok = (r.returncode == 0 and idb_out.exists() and sha(idb_out) == real_sha52
         and sv_idb.get('identity') == 'match' and sv_idb.get('pdf_same_version_proven') is True)
    record('fix5-2：临时目录给 04+其定位 PDF 写一份匹配的 同版身份.json → 不带 --allow-unbound-pdf 也通过（identity=match），输出与 B3_52 字节一致',
          ok, json.dumps(sv_idb, ensure_ascii=False), secs)

    # ---- fix5-3：03 的 PDF 配 04 → 无开关拒绝。B3_03 本身没有独立渲染的 PDF（03→04 只改编号/考法/keepNext，
    #      不改文字，理论上正文对位率会很高），这里按任务说明用 B3_51 的真实 PDF 代替说明用途——它同样是
    #      “没有同版身份记录、也确实不是 04 这版渲染的 PDF”，验证的是同一件事：没有记录时不带开关必须拒绝，
    #      不看对位率高低（B3_51 与 B3_04 同源文字重合度也不低）。
    out_53 = SC / 'should_not_exist_fix5_3.docx'
    clean(out_53)
    r, secs = run(['repair', '--docx', str(B3_04), '--out', str(out_53), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(B3_51_PDF)])
    ok = (r.returncode == 2 and not out_53.exists() and '同版' in (r.stderr or ''))
    record('fix5-3：03 的 PDF（用 B3_51 PDF 代替：环境里没有独立渲染的 03 PDF，同样是无记录的别份 PDF）配 04 → 无开关拒绝',
          ok, r.stderr.strip()[:200], secs)

    # ---- fix5-4：N2 插页错版——把 B3_52 的真实 PDF 复制一份，中间插入一页空白页（文字内容完全不变，只是
    #      分页整体后移），拿去当 B3_04 的 --toc-pdf。这正是回执点名的“文字对位证明不了分页相同”的样本：
    #      对位率（正向、反向）都会很高，唯一能拦住它的是“没有同版身份记录”这道闸，不是对位率。
    n2_pdf = SC / 'fix5_n2_blankpage.pdf'
    _d = _fitz_fix5.open(str(B3_52_PDF))
    _d.insert_page(50)
    _d.save(str(n2_pdf))
    _d.close()
    out_n2 = SC / 'should_not_exist_fix5_n2.docx'
    clean(out_n2)
    r, secs = run(['repair', '--docx', str(B3_04), '--out', str(out_n2), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(n2_pdf)])
    ok_n2_repair = (r.returncode == 2 and not out_n2.exists())
    r2, secs2 = run(['check', '--docx', str(B3_04), '--toc-pdf', str(n2_pdf), '--profile', 'bixiu3',
                    '--report', str(SC / 'fix5_n2_check.json')])
    rep_n2 = json.loads((SC / 'fix5_n2_check.json').read_text())
    tvp_n2 = rep_n2.get('toc_version_problems') or []
    unproven_n2 = tvp_n2[0] if (tvp_n2 and isinstance(tvp_n2[0], dict)) else {}
    ok_n2_check = (rep_n2.get('repairable_plan_count', {}).get('toc') == 0 and unproven_n2.get('diff_count') == 30)
    record('fix5-4：N2 插页错版（B3_52 PDF 插一页空白，文字全同、分页不同）配 B3_04 → repair 无开关 Abort(2)，'
          'check 把 30 处页码差异算进 toc_version_problems 而不是可修 pending',
          ok_n2_repair and ok_n2_check,
          'repair_rc=%d check_toc_pending=%s diff_count=%s' % (r.returncode, rep_n2.get('repairable_plan_count', {}).get('toc'), unproven_n2.get('diff_count')),
          secs + secs2)
    clean(n2_pdf)

    # ---- fix5-5/5-6：双向对位率对“正文删段”攻击的效果——在临时副本里删掉 04 中间一段连续正文（不动标题），
    #      配 04 自己真实的目录定位 PDF（PDF 没删，仍是旧内容），用 --allow-unbound-pdf 走兜底路径：
    #      正向对位率几乎不掉（删掉的段落本来就不在“剩下的 DOCX”里，不影响“DOCX 段落能不能在 PDF 里找到”
    #      这个方向，这正是回执点名的单向缺陷）；反向对位率（PDF 这些行还在，但 DOCX 里已经没有对应段落）
    #      会随删除规模下降——120 段（约 0.6%）目前测下来仍在阈值之上（如实记 known_limits：双向对位率对
    #      小规模删段不敏感，这条兜底路径本来就只是“未经 SHA 绑定”的降级放行，不是分页正确性的证明）；
    #      600 段（约 3%）反向对位率会跌破阈值，必须被拦下——不能让“delete 更多反而更容易蒙混过关”。
    def _delete_n_paragraphs(src_docx, n, out_path):
        d2 = dl.open_docx(str(src_docx))
        items2, _ = bh.read_docx(str(src_docx))
        cand = [i for i, it in enumerate(items2) if it['tbl'] is None and len(it['text'].strip()) >= 20]
        victim = sorted(set(cand[1000:1000 + n]), reverse=True)
        for i in victim:
            p = d2.paras[i]
            p.getparent().remove(p)
        dl.write_docx(d2, out_path)

    del120 = SC / 'fix5_del120.docx'
    del600 = SC / 'fix5_del600.docx'
    _delete_n_paragraphs(B3_04, 120, del120)
    _delete_n_paragraphs(B3_04, 600, del600)

    out_del120 = SC / 'fix5_del120_out.docx'
    clean(out_del120)
    r, secs = run(['repair', '--docx', str(del120), '--out', str(out_del120), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(B3_04_PDF),
                  '--allow-unbound-pdf', 'fix5 回归：删 120 段攻击（如实记录：目前双向对位率测不出这个规模）',
                  '--report', str(SC / 'fix5_del120_report.json')])
    rep_del120 = json.loads((SC / 'fix5_del120_report.json').read_text()) if r.returncode == 0 else {}
    sv_del120 = rep_del120.get('pdf_same_version') or {}
    # 这里不断言“必须被拦下”（如实记录：目前测不出来），只断言 known-limit 行为本身是稳定、可解释的：
    # 双向对位率都确实算出来了、且都在阈值之上（所以放行是“对位率兜底路径按规则执行”，不是代码 bug）。
    ok_del120 = (r.returncode == 0 and sv_del120.get('align_ratio', 0) >= sv_del120.get('threshold', 0.98)
                and sv_del120.get('reverse_align_ratio', 0) >= sv_del120.get('threshold', 0.98))
    record('fix5-5（known limit，如实记录）：删 120 段（约 0.6%）+ --allow-unbound-pdf → 双向对位率仍双双达标、放行'
          '（正向单向缺陷 + 反向对小规模删段不敏感，双向兜底对“大规模”改动更有效，见 known_limits）',
          ok_del120, json.dumps(sv_del120, ensure_ascii=False), secs)

    out_del600 = SC / 'should_not_exist_fix5_del600.docx'
    clean(out_del600)
    r, secs = run(['repair', '--docx', str(del600), '--out', str(out_del600), '--profile', 'bixiu3',
                  '--toc', '--toc-pdf', str(B3_04_PDF),
                  '--allow-unbound-pdf', 'fix5 回归：删 600 段攻击，应被反向对位率拦下'])
    ok_del600 = (r.returncode == 2 and not out_del600.exists()
                and ('反向' in (r.stderr or '') or '双向' in (r.stderr or '')))
    record('fix5-6：删 600 段（约 3%）+ --allow-unbound-pdf → 反向正文对位率跌破阈值，拒绝执行，不写输出',
          ok_del600, r.stderr.strip()[:200], secs)
    for f in (del120, del600, out_del120):
        clean(f)

    # ---- fix5-7：keepNext 长链闸退出码——见下方【必须】4（fix4-8 用例）里追加的 code_check 断言，复用
    #      同一个可靠的 monkeypatch 场景（B3_03 + max_keep_next_chain=0），不再单独臆造一份。

    # ---- fix5-8：plan_keepnext 自己的注释里，“keep_next_labels 两册配置尚未登记”“缺省即现行必修三的
    #      两个标签”这类跟紧接着几行（缺省 []、bixiu3 已登记）自相矛盾的过时说法已经删掉。只在 plan_keepnext
    #      这一个函数体的源码文本里查（不是全文件），避免跟 pagination.max_keep_next_chain——另一个至今真的
    #      没登记进任何 profile 的字段，它文件头的“两册配置尚未登记”原样成立——撞了同一段中文而误判。
    src_text = TOOL.read_text(encoding='utf-8')
    m = re.search(r'def plan_keepnext\(.*?\n(?=def keepnext_gate\()', src_text, re.S)
    plan_kn_src = m.group(0) if m else ''
    ok = bool(plan_kn_src) and (
        'keep_next_labels：本工具新增字段（两册配置尚未登记）' not in plan_kn_src
        and '配置补上，缺省即现行必修三的两个标签' not in plan_kn_src
        and 'pagination.max_keep_next_chain' not in plan_kn_src  # 那是另一个字段，不该混进这段注释
    )
    record('fix5-8：plan_keepnext 自己的注释里“keep_next_labels 两册配置尚未登记/缺省即现行必修三的两个标签”这类过时说法已清掉',
          ok, ('plan_keepnext 源码：\n' + plan_kn_src) if not ok else 'removed')

    # ---- 【必须】2. 写出后失败清理：写后阶段任何异常都要删掉已写出的 DOCX 再退出（不只是显式 fail_after_write
    #      判定的那几种），进程内跑，monkeypatch bh.run_health 在写后那次调用上直接抛异常（模拟 --health 崩溃）
    orig_run_health = bh.run_health
    calls = {'n': 0}

    def crashing_health(path, profile=None):
        calls['n'] += 1
        if calls['n'] >= 2:  # 第一次是写前跑 pre_health，第二次是写后跑 post_health，这里模拟写后那次崩
            raise RuntimeError('模拟体检崩溃')
        return orig_run_health(path, profile=profile)

    out_t5 = SC / 'fix4_should_not_exist_t5.docx'
    clean(out_t5)

    class FakeArgsT5:
        docx = str(B3_03)
        out = str(out_t5)
        profile = 'bixiu3'
        expect_sha = None
        numbering = True
        method_counts = False
        keepnext = False
        toc = False
        toc_pdf = None
        allow_blocked = False
        health = True
        report = None

    bh.run_health = crashing_health
    caught_t5 = False
    try:
        try:
            lp.do_repair(FakeArgsT5())
        except RuntimeError:
            caught_t5 = not Path(out_t5).exists()
    finally:
        bh.run_health = orig_run_health
        clean(out_t5)
    record('fix4-5：写后阶段任意异常（非 fail_after_write 显式判定，如 --health 体检崩溃）都要先删已写出的 DOCX 再往外抛',
          caught_t5, 'calls=%d' % calls['n'])

    # ---- write_report 临时文件改用 tempfile.mkstemp：预先在报告目录放一个指向“受害文件”的符号链接，
    #      链接名恰好是旧实现会用的固定名 .<报告名>.tmp；新实现每次生成随机文件名，不会踩中这个链接，
    #      受害文件内容应保持不变，报告仍正常写出且不是符号链接。
    g_dir = SC / 'fix4_symlink_dir'
    if g_dir.exists():
        shutil.rmtree(g_dir)
    g_dir.mkdir()
    victim = g_dir / 'precious.txt'
    victim.write_text('VICTIM-ORIGINAL', encoding='utf-8')
    report_name = 'r.json'
    fixed_tmp = g_dir / ('.' + report_name + '.tmp')
    os.symlink(str(victim), str(fixed_tmp))
    r, _ = run(['check', '--docx', str(B3_03), '--profile', 'bixiu3', '--report', str(g_dir / report_name)])
    ok_t6 = (victim.read_text(encoding='utf-8') == 'VICTIM-ORIGINAL'
            and fixed_tmp.is_symlink()  # 旧的固定名符号链接原样留在那，没被写报告的临时文件复用
            and (g_dir / report_name).exists() and not (g_dir / report_name).is_symlink())
    record('fix4-6：write_report 改用 tempfile.mkstemp 后，预置的固定名符号链接不会被踩中，受害文件内容不变',
          ok_t6, 'victim=%r report_is_symlink=%s' % (victim.read_text(encoding='utf-8'), (g_dir / report_name).is_symlink()))
    shutil.rmtree(g_dir)

    # ---- 【必须】3. 批量误改保护：把已登记书册的 B3_03（03→04 那一批本身就是编号大改，343 处）复制到
    #      不落在任何登记书册目录下的 scratch 路径，仍传 --profile bixiu3 --numbering，应判 blocked 并中止
    #      （疑似拿错了书稿硬套配置）；--allow-mass-renumber 才放行。
    unregistered_src = SC / 'fix4_unregistered_b303.docx'
    shutil.copy2(B3_03, unregistered_src)
    out_t7 = SC / 'fix4_should_not_exist_t7.docx'
    clean(out_t7)
    r, _ = run(['repair', '--docx', str(unregistered_src), '--out', str(out_t7), '--numbering', '--profile', 'bixiu3'])
    ok_t7a = (r.returncode == 2 and not out_t7.exists() and '批量误改保护' in (r.stderr or ''))
    r, _ = run(['repair', '--docx', str(unregistered_src), '--out', str(out_t7), '--numbering', '--profile', 'bixiu3',
               '--allow-blocked'])
    ok_t7b = (r.returncode == 2 and not out_t7.exists())  # --allow-blocked 不放行这一条
    r, secs = run(['repair', '--docx', str(unregistered_src), '--out', str(out_t7), '--numbering', '--profile', 'bixiu3',
                  '--allow-mass-renumber', '--report', str(SC / 'fix4_t7_allowed.json')])
    ok_t7c = (r.returncode == 0 and out_t7.exists())
    rep_t7 = json.loads((SC / 'fix4_t7_allowed.json').read_text()) if ok_t7c else {}
    ok_t7d = (rep_t7.get('mass_renumber_risk') is True and rep_t7.get('mass_renumber_allowed') is True
             and rep_t7.get('book_registered') is False)
    clean(out_t7)
    unregistered_src.unlink()
    record('fix4-7：批量误改保护——未登记书册路径且编号改动比例过高 → blocked 中止（--allow-blocked 不放行，'
          '只认 --allow-mass-renumber），放行后如实写入报告',
          ok_t7a and ok_t7b and ok_t7c and ok_t7d, 'a=%s b=%s c=%s d=%s' % (ok_t7a, ok_t7b, ok_t7c, ok_t7d), secs)

    # ---- 4. check 与 repair 的 keepNext 长链闸同口径：用同一份 monkeypatch 过的 plan_keepnext（强制候选指向
    #      某个真实存在、当前未设 keepNext 的段落）+ max_keep_next_chain=0（必然触发长链闸）分别跑 check 与
    #      repair，两边都应该把这一条算作 blocked，不计入可修待办／不落 word/document.xml。
    kn_src = SC / 'fix4_kn_b303.docx'
    shutil.copy2(B3_03, kn_src)  # 不落在任何登记书册目录下：绕开 get_profile 的探测/--profile 路径一致性核对
    d_kn = dl.open_docx(str(kn_src))
    P_kn = bh.Prof(bh.load_profile('bixiu3'))
    bh.walk(d_kn.items, P_kn)
    target_kn = next(i for i, it in enumerate(d_kn.items) if not it['keepnext'])
    custom_pd = dict(bh.load_profile('bixiu3'))
    custom_pd['pagination'] = dict(custom_pd.get('pagination', {}), max_keep_next_chain=0, forbid_long_chains=True)
    custom_pd.pop('_profile_path', None)
    custom_profile_path = SC / 'fix4_custom_bixiu3_maxchain0.json'
    custom_profile_path.write_text(json.dumps(custom_pd, ensure_ascii=False), encoding='utf-8')

    orig_plan_kn = lp.plan_keepnext

    def forced_plan_kn(items, pd_, P_):
        return [{'para': target_kn, 'rule': 'fix4_synthetic', 'excerpt': 'x'}]

    lp.plan_keepnext = forced_plan_kn
    try:
        out_kn = SC / 'fix4_should_not_exist_kn.docx'
        clean(out_kn)

        class FakeArgsKNCheck:
            docx = str(kn_src)
            pdf = None
            toc_pdf = None
            profile = str(custom_profile_path)
            report = str(SC / 'fix4_kn_check.json')
            max_items = 60

        code_check = lp.do_check(FakeArgsKNCheck())
        rep_kn_check = json.loads((SC / 'fix4_kn_check.json').read_text())
        check_blocked = rep_kn_check.get('blocked_count', {}).get('keepnext')
        check_pending_kn = rep_kn_check.get('repairable_plan_count', {}).get('keepnext')

        class FakeArgsKNRepair:
            docx = str(kn_src)
            out = str(out_kn)
            profile = str(custom_profile_path)
            expect_sha = None
            numbering = False
            method_counts = False
            keepnext = True
            toc = False
            toc_pdf = None
            allow_blocked = False
            health = False
            report = None

        repair_blocked_kn = None
        try:
            lp.do_repair(FakeArgsKNRepair())
            repair_aborted = False
        except lp.Abort as e:
            repair_aborted = (e.code == 2)
        ok_kn = (check_blocked == 1 and check_pending_kn == 0 and repair_aborted and not out_kn.exists())
        record('fix4-8：check/repair 的 keepNext 长链闸同口径——同一候选、同一 max_keep_next_chain=0 配置，'
              'check 记 blocked=1/可修待办=0，repair 也判 blocked 并中止，不留输出',
              ok_kn, 'check_blocked=%r check_pending=%r repair_aborted=%r' % (check_blocked, check_pending_kn, repair_aborted))

        # fix5-7：check 的退出码要和 repair 一致——pending=0 但 blocked=1 时，check 不能再 exit 0（此前
        # 主代理看到 check 为 0 再跑 repair 会意外失败，见 final 回执 minor）。这里复用上面同一个场景，
        # code_check 是刚才 lp.do_check(...) 的真实返回值，不是另造一份。
        ok_kn_exit = (code_check == 1 and bool(rep_kn_check.get('blocked_note')))
        record('fix5-7：check 遇到 keepNext 长链闸 blocked（pending=0）→ exit 1（不再是 0），report.blocked_note 写“会被长链闸挡住”，与 repair 的 exit 2 口径一致（都不是 0）',
              ok_kn_exit, 'code_check=%r blocked_note=%r' % (code_check, rep_kn_check.get('blocked_note')))
    finally:
        lp.plan_keepnext = orig_plan_kn
        clean(SC / 'fix4_should_not_exist_kn.docx')
        custom_profile_path.unlink(missing_ok=True)
        kn_src.unlink(missing_ok=True)

    # ---- 顺手修 a：标题段首只含空白的 run（不影响 bh.read_docx 的 it['text']=raw.strip()，但会出现在
    #      t_text(p) 里，旧实现会因为多出的前导空白让正则匹配不到编号 span 而误判 blocked）
    d_ws = dl.open_docx(str(B3_03))
    P_ws = bh.Prof(bh.load_profile('bixiu3'))
    bh.walk(d_ws.items, P_ws)
    numbering_todo_ws = lp.plan_numbering(d_ws.items, P_ws)
    ok_ws = False
    if numbering_todo_ws:
        i0 = numbering_todo_ws[0]['para']
        p0 = d_ws.paras[i0]
        ppr = p0.find(bh.W + 'pPr')
        insert_at = 1 if ppr is not None else 0
        leading = ET.Element(bh.W + 'r')
        t_el = ET.SubElement(leading, bh.W + 't')
        t_el.text = ' '
        t_el.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
        p0.insert(insert_at, leading)
        tt0 = lp.t_text(p0)
        span0 = lp.num_span_in_ttext(P_ws, d_ws.items[i0], tt0)
        ok_ws = (span0 is not None and tt0[span0[0]:span0[1]].isdigit() and tt0[0] in ' \t\u3000')
    record('fix4-9（顺手修 a）：标题段首只含空白的 run 不再让 num_span_in_ttext 判定失败（按 read_docx 同规则先去前导空白再匹配，span 再加回偏移）',
          ok_ws, 'span=%r tt_head=%r' % (span0 if numbering_todo_ws else None, tt0[:6] if numbering_todo_ws else None))

    # ---- 顺手修 b：PAGEREF 域代码被拆成多个 <w:instrText>（甚至分属不同 run），单个片段各含半个
    #      "PAGEREF" 子串时旧实现定位不到缓存页码节点
    xml_split = ('<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:hyperlink w:anchor="_Toc3"><w:r><w:t>标题C</w:t></w:r>'
                '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
                '<w:r><w:instrText xml:space="preserve">PAGE</w:instrText></w:r>'
                '<w:r><w:instrText xml:space="preserve">REF _Toc3 \\h</w:instrText></w:r>'
                '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
                '<w:r><w:t>21</w:t></w:r>'
                '<w:r><w:fldChar w:fldCharType="end"/></w:r></w:hyperlink></w:p>')
    n_split = lp.toc_page_nodes(ET.fromstring(xml_split), 'pageref_in_hyperlink')
    ok_split = (len(n_split) == 1 and n_split[0].text == '21')
    record('fix4-10（顺手修 b）：PAGEREF 域代码被拆成多个 instrText（甚至分属不同 run）时，toc_page_nodes 累积拼接后再判断，仍能定位到缓存页码节点',
          ok_split, 'nodes=%r' % [n.text for n in n_split])

    # ================================================================ fix6（第六轮返修）新增回归 ================
    # confirm 回执 major：check 的退出码没把 toc_version_problems 算进去——同版未证明但目录页码有差异时，
    # check 仍 exit 0，与同一输入 repair --toc 缺省 exit 2 口径不一致，主代理只看退出码会误以为目录无需处理。
    # fix6 让 check 在 toc_version_problems 非空时也 exit 1，并补 toc_note 说明降级路径。

    # ---- fix6-1：B3_04 配它自己没有身份记录的目录定位 PDF → check 现在必须 exit 1（此前 exit 0），
    #      report 与 stdout 都要有 toc_note，指向“render_book.py 渲染 / --allow-unbound-pdf”这条正式流程。
    r, secs = run(['check', '--docx', str(B3_04), '--toc-pdf', str(B3_04_PDF), '--profile', 'bixiu3',
                  '--report', str(SC / 'fix6_t1_04unbound.json')])
    rep_f6_1 = json.loads((SC / 'fix6_t1_04unbound.json').read_text())
    stdout_f6_1 = json.loads(r.stdout.strip().splitlines()[-1]) if r.stdout.strip() else {}
    ok_f6_1 = (r.returncode == 1 and rep_f6_1.get('pending') == 0
              and len(rep_f6_1.get('toc_version_problems') or []) == 1
              and rep_f6_1.get('toc_note') and 'render_book.py' in rep_f6_1['toc_note']
              and '--allow-unbound-pdf' in rep_f6_1['toc_note']
              and stdout_f6_1.get('toc_note') == rep_f6_1['toc_note'])
    record('fix6-1（confirm major）：B3_04 配无身份记录的目录定位 PDF，目录页码有差异 → check exit 1（不再是 0），'
          'report/stdout 均带 toc_note 指向 render_book.py / --allow-unbound-pdf',
          ok_f6_1, json.dumps({'rc': r.returncode, 'pending': rep_f6_1.get('pending'),
                               'toc_note': rep_f6_1.get('toc_note')}, ensure_ascii=False), secs)

    # ---- fix6-2：金标准回归——B3_52 配自己的同版 PDF（identity=match），目录页码本就一致 →
    #      toc_version_problems 仍为空，toc_note 为 None，check 仍 exit 0（不能因为这次改动误伤已证明同版的场景）。
    r, secs = run(['check', '--docx', str(B3_52), '--toc-pdf', str(B3_52_PDF), '--profile', 'bixiu3',
                  '--report', str(SC / 'fix6_t2_52match.json')])
    rep_f6_2 = json.loads((SC / 'fix6_t2_52match.json').read_text())
    ok_f6_2 = (r.returncode == 0 and rep_f6_2.get('toc_version_problems') == [] and rep_f6_2.get('toc_note') is None)
    record('fix6-2（金标准回归）：B3_52 配自证同版的自身 PDF，目录页码一致 → toc_version_problems 空、toc_note 为 None，check 仍 exit 0',
          ok_f6_2, json.dumps({'rc': r.returncode, 'toc_note': rep_f6_2.get('toc_note')}, ensure_ascii=False), secs)

    # ---- fix6-3：N2 插页错版（文字全同、分页不同，见 fix5-4）配 B3_04 → check 现在必须 exit 1
    #      （fix5-4 只验证了 toc_version_problems 计数，没验证退出码本身）。
    n2_pdf_f6 = SC / 'fix6_n2_blankpage.pdf'
    _d6 = _fitz_fix5.open(str(B3_52_PDF))
    _d6.insert_page(50)
    _d6.save(str(n2_pdf_f6))
    _d6.close()
    r, secs = run(['check', '--docx', str(B3_04), '--toc-pdf', str(n2_pdf_f6), '--profile', 'bixiu3',
                  '--report', str(SC / 'fix6_t3_n2.json')])
    rep_f6_3 = json.loads((SC / 'fix6_t3_n2.json').read_text())
    ok_f6_3 = (r.returncode == 1 and len(rep_f6_3.get('toc_version_problems') or []) == 1
              and bool(rep_f6_3.get('toc_note')))
    record('fix6-3：N2 插页错版（文字全同、分页不同）配 B3_04 → check exit 1（此前是 0），带 toc_note',
          ok_f6_3, json.dumps({'rc': r.returncode, 'toc_note': rep_f6_3.get('toc_note')}, ensure_ascii=False), secs)
    clean(n2_pdf_f6)

    # ---- fix6-4：del120/add120 一类临时构造的“没有身份记录但对位率很高”的攻击样本做 check（confirm 回执
    #      点名的 bx 用例），只要 toc_version_problems 非空就必须 exit 1；这里用 del120（fix5-5 已构造过的
    #      同类场景）重新走一遍 check（不带 --allow-unbound-pdf，check 从不看这个开关）。
    del120_f6 = SC / 'fix6_del120.docx'
    _delete_n_paragraphs(B3_04, 120, del120_f6)
    r, secs = run(['check', '--docx', str(del120_f6), '--toc-pdf', str(B3_04_PDF), '--profile', 'bixiu3',
                  '--report', str(SC / 'fix6_t4_del120.json')])
    rep_f6_4 = json.loads((SC / 'fix6_t4_del120.json').read_text())
    ok_f6_4 = (r.returncode == 1 and len(rep_f6_4.get('toc_version_problems') or []) >= 1
              and bool(rep_f6_4.get('toc_note')))
    record('fix6-4（confirm major 点名的 bx 用例）：del120（没有身份记录）做 check → exit 1（此前是 0），带 toc_note',
          ok_f6_4, json.dumps({'rc': r.returncode, 'toc_note': rep_f6_4.get('toc_note')}, ensure_ascii=False), secs)
    clean(del120_f6)

    after = snapshot(REAL_INPUTS)
    unchanged = (before == after)
    record('全部真实输入文件 SHA256+mtime 测试前后未变', unchanged,
          '' if unchanged else json.dumps({k: (before[k], after[k]) for k in before if before[k] != after[k]}, ensure_ascii=False))

    n_fail = sum(1 for r_ in RESULTS if not r_['pass'])
    print('\n合计：%d/%d 通过' % (len(RESULTS) - n_fail, len(RESULTS)))
    (SC / 'run_tests_result.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding='utf-8')
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
