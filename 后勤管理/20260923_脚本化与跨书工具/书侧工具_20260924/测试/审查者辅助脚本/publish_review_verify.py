#!/usr/bin/env python3
"""publish_review.py 的对抗性复验（独立审查者写，不改被测工具）。

只读真实数据；所有输出写 $SCRATCH/booktools/publish_review_verify/。
跑法：/usr/bin/python3 -B publish_review_verify.py <输出目录>
"""
import sys
sys.dont_write_bytecode = True
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

S = Path(__file__).resolve().parent
TOOL = S / 'publish_review.py'
PY = '/usr/bin/python3'
ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
C52 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923'
REAL = {
    'docx52': C52 / '构建/必修三政治与法治宝典_第52批_意见修改审阅稿.docx',
    'pdf52': C52 / '构建/rendered/必修三政治与法治宝典_第52批_意见修改审阅稿.pdf',
    'acc52': C52 / '构建/最终主代理技术验收.json',
    'id52': C52 / '构建/同版身份.json',
    'docx04': C52 / '构建/04_编号与考法计数.docx',
    'pdf04': C52 / '构建/目录定位/04_编号与考法计数.pdf',
}
OUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path('/tmp/publish_review_verify')
RESULTS = []


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def tree(base):
    base = Path(base)
    out = {}
    for dp, dn, fn in os.walk(base, followlinks=False):
        for n in dn + fn:
            p = Path(dp) / n
            rel = str(p.relative_to(base))
            if p.is_symlink():
                out[rel] = 'link->' + os.readlink(p)
            elif p.is_dir():
                out[rel] = '<dir>'
            else:
                out[rel] = sha(p)[:16]
    return out


def tdiff(a, b):
    return {'added': sorted(set(b) - set(a)), 'removed': sorted(set(a) - set(b)),
            'changed': sorted(k for k in set(a) & set(b) if a[k] != b[k])}


def mkpdf(path, pages):
    from pypdf import PdfWriter
    w = PdfWriter()
    for _ in range(pages):
        w.add_blank_page(width=200, height=200)
    with open(path, 'wb') as f:
        w.write(f)


def build(name, stem_tpl='必修三政治与法治宝典_R31续修_第{n}批_阶段审查稿', old_stem='必修三政治与法治宝典_R31续修_第51批_阶段审查稿',
          backup_tpl='{candidate}/发布准备/状态备份/{stamp}', central_extra=None, history=True, cand_rel=None,
          latest_batch='batch51', manifest_extra=None, acc_mut=None, real_files=False):
    base = OUT / 'sb' / name
    if base.exists():
        shutil.rmtree(base)
    (base / 'workspace/协作').mkdir(parents=True)
    (base / 'review_entry').mkdir(parents=True)
    if history:
        (base / 'review_history').mkdir(parents=True)
    # 现有版本
    old_docx = base / 'review_entry' / f'{old_stem}.docx'
    old_pdf = base / 'review_entry' / f'{old_stem}.pdf'
    old_docx.write_bytes(b'OLD-DOCX-51')
    mkpdf(old_pdf, 3)
    (base / 'workspace' / f'{old_stem}.docx').write_bytes(b'OLD-DOCX-51')
    (base / 'review_entry' / '先看这里.md').write_text('# 旧说明\n', encoding='utf-8')
    man = {'docx': str(old_docx), 'docx_sha256': sha(old_docx), 'pdf': str(old_pdf), 'pdf_sha256': sha(old_pdf),
           'latest_batch': latest_batch, 'status': 'stage_review_copy_not_final'}
    man.update(manifest_extra or {})
    (base / 'review_entry/.review-manifest.json').write_text(json.dumps(man, ensure_ascii=False), encoding='utf-8')
    central = {'working_head': str(base / 'workspace' / f'{old_stem}.docx'), 'working_head_sha256': sha(old_docx),
               'working_head_bytes': 11, 'latest_batch': latest_batch, 'latest_render': {}, 'updated_at': 'x'}
    central.update(central_extra or {})
    cpath = base / 'central_state.json'
    cpath.write_text(json.dumps(central, ensure_ascii=False), encoding='utf-8')
    (base / 'workspace/协作/接管.json').write_text(json.dumps({'owner': 'test:a', 'phase': 'owned'}), encoding='utf-8')
    # 候选
    cand_dir = base / (cand_rel or 'workspace/协作/候选/test/第52批_t_20260924/构建')
    cand_dir.mkdir(parents=True, exist_ok=True)
    if real_files:
        cd, cp = cand_dir / 'cand.docx', cand_dir / 'cand.pdf'
        shutil.copy2(REAL['docx52'], cd)
        shutil.copy2(REAL['pdf52'], cp)
        pages = 811
    else:
        cd, cp = cand_dir / 'cand.docx', cand_dir / 'cand.pdf'
        cd.write_bytes(b'NEW-DOCX-52')
        mkpdf(cp, 5)
        pages = 5
    binding = {'docx_sha256': sha(cd), 'pdf_sha256': sha(cp), 'pdf_pages': pages, 'status': 'PASS'}
    (cand_dir / '同版身份.json').write_text(json.dumps(binding), encoding='utf-8')
    acc = {'approval_type': 'root_technical_acceptance', 'approved': True, 'final_qa_passed': True, 'actor_owned': 'test:a',
           'batch': '52', 'expected_current_working_head_sha256': central['working_head_sha256'],
           'candidate': {'docx_sha256': sha(cd), 'pdf_sha256': sha(cp), 'pdf_pages': pages},
           'same_version_binding': dict(binding)}
    if acc_mut:
        acc_mut(acc)
    apath = cand_dir / '验收.json'
    apath.write_text(json.dumps(acc, ensure_ascii=False), encoding='utf-8')
    prof = json.loads((S / 'profiles/bixiu3.json').read_text(encoding='utf-8'))
    prof.update({'book_id': 'sb_' + name, 'title': '沙盒' + name, 'frozen': False, 'collab_key': 'sandbox_never_matches'})
    prof['paths'] = {'root': str(base), 'workspace': 'workspace', 'review_entry': 'review_entry',
                     'review_manifest': 'review_entry/.review-manifest.json', 'central_state': str(cpath),
                     'handoff': 'workspace/协作/接管.json'}
    if history:
        prof['paths']['review_history'] = 'review_history'
    prof['publish'] = {'entry': 'review_entry', 'note_file': '先看这里.md', 'manifest': '.review-manifest.json',
                       'preserve': ['.DS_Store', '~$*'], 'central_state_backup': backup_tpl}
    if history:
        prof['publish']['archive_to'] = 'review_history/第{prev}批_原样审阅_{stamp}'
    prof['naming'] = {'docx_stem': stem_tpl, 'feedback_hint': '请按“第{n}批＋PDF页码”提意见'}
    ppath = OUT / 'sb' / (name + '_profile.json')
    ppath.write_text(json.dumps(prof, ensure_ascii=False), encoding='utf-8')
    return {'base': base, 'prof': ppath, 'docx': cd, 'pdf': cp, 'acc': apath, 'central': cpath, 'cand_dir': cand_dir}


def args_of(sb, batch='52', actor='test:a', extra=()):
    return ['--profile', str(sb['prof']), '--batch', batch, '--docx', str(sb['docx']), '--pdf', str(sb['pdf']),
            '--acceptance', str(sb['acc']), '--actor', actor] + list(extra)


def run(argv, inject=None):
    """inject：None 直接跑 CLI；否则用包装器在进程内打补丁后调用 main()。"""
    t0 = time.time()
    if inject is None:
        cmd = [PY, '-B', str(TOOL)] + argv
    else:
        wrapper = (
            'import sys,json\nsys.dont_write_bytecode=True\nsys.path.insert(0,%r)\nimport publish_review as pr\n' % str(S)
            + inject + '\nsys.exit(pr.main(json.loads(sys.argv[1])))\n')
        cmd = [PY, '-B', '-c', wrapper, json.dumps(argv, ensure_ascii=False)]
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        payload = json.loads(p.stdout)
    except Exception:
        payload = None
    return p.returncode, payload, p.stderr, round(time.time() - t0, 2)


def rec(tid, desc, **kw):
    kw = dict(kw)
    RESULTS.append(dict(id=tid, desc=desc, **kw))
    print(f'== {tid} {desc}\n' + json.dumps(kw, ensure_ascii=False, indent=1, default=str)[:3000])


def gates(payload):
    return {g['id']: g['level'] for g in payload['gates']} if payload else None


# 注入：atomic_write_json 写到某个名字时抛错（写前抛 / 写后抛）
INJ_BEFORE = '''
_o = pr.atomic_write_json
def _w(p, d):
    if str(p).endswith(%r):
        raise RuntimeError('注入故障')
    return _o(p, d)
pr.atomic_write_json = _w
'''
INJ_AFTER = '''
_o = pr.atomic_write_json
def _w(p, d):
    r = _o(p, d)
    if str(p).endswith(%r):
        raise RuntimeError('注入故障(写后)')
    return r
pr.atomic_write_json = _w
'''


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # A1 晚期故障（写中央状态时失败）：全树是否与发布前一致
    sb = build('A1_late_fault_central')
    t0 = tree(sb['base'])
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']), INJ_BEFORE % 'central_state.json')
    d = tdiff(t0, tree(sb['base']))
    rec('A1', '第6步写中央状态时注入故障，回滚后沙盒全树对比', rc=rc, stderr=err[-600:], diff=d, seconds=sec)

    # A2 写晋升回执后故障：已存在的旧回执被覆盖且不恢复、PROMOTED 回执残留
    sb = build('A2_fault_after_receipt')
    (sb['cand_dir'].parent / '发布准备').mkdir()
    (sb['cand_dir'].parent / '发布准备/晋升回执.json').write_text('{"status":"OLD_RECEIPT"}', encoding='utf-8')
    t0 = tree(sb['base'])
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']), INJ_AFTER % '晋升回执.json')
    after = (sb['cand_dir'].parent / '发布准备/晋升回执.json').read_text(encoding='utf-8')
    rec('A2', '写晋升回执后注入故障（模拟复核失败），看回执是否残留 PROMOTED、旧回执是否恢复', rc=rc, stderr=err[-400:],
        receipt_after=after[:200], diff=tdiff(t0, tree(sb['base'])), seconds=sec)

    # A3 固定文件名审阅副本（新 stem = 旧登记名）+ 晚期故障：回滚顺序导致审阅入口丢稿
    sb = build('A3_same_name_rollback', stem_tpl='必修三_最新审阅稿', old_stem='必修三_最新审阅稿')
    t0 = tree(sb['base'])
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']), INJ_BEFORE % 'central_state.json')
    t1 = tree(sb['base'])
    rec('A3', '新旧同名（固定审阅副本名）时第6步故障，回滚后审阅入口是否还有 docx/pdf', rc=rc, stderr=err[-500:],
        review_entry_after=sorted(os.listdir(sb['base'] / 'review_entry')), diff=tdiff(t0, t1), seconds=sec)

    # A4 工作区根已有同名文件（人工改稿）：apply 静默覆盖、无备份；故障时也不恢复
    for variant, inj in (('ok', None), ('fault', INJ_BEFORE % 'central_state.json')):
        sb = build('A4_ws_clobber_' + variant)
        hand = sb['base'] / 'workspace/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
        hand.write_bytes(b'HAND-EDITED-BY-USER')
        hs = sha(hand)
        rc, pl, err, sec = run(args_of(sb, extra=['--apply']), inj)
        survivors = [k for k, v in tree(sb['base']).items() if v == hs[:16]]
        rec('A4_' + variant, '工作区根预先存在同名手改稿，apply 后该稿是否还在（任何位置）', rc=rc, stderr=err[-300:],
            hand_file_sha_now=sha(hand)[:16] if hand.exists() else None, hand_sha_before=hs[:16],
            copies_of_hand_edit_anywhere=survivors, seconds=sec)

    # A5 符号链接：review_history / review_entry 本身是指向配置位置之外的链接
    outside = OUT / 'outside'
    if outside.exists():
        shutil.rmtree(outside)
    outside.mkdir(parents=True)
    sb = build('A5a_history_symlink')
    shutil.rmtree(sb['base'] / 'review_history')
    (outside / 'hist').mkdir()
    os.symlink(outside / 'hist', sb['base'] / 'review_history')
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']))
    rec('A5a', 'review_history 是指向 paths.root 之外的符号链接', rc=rc, stderr=err[-300:],
        written_outside_root=sorted(str(p.relative_to(outside)) for p in (outside / 'hist').rglob('*')), seconds=sec)
    sb = build('A5b_entry_symlink')
    real_entry = outside / 'entry'
    shutil.move(str(sb['base'] / 'review_entry'), str(real_entry))
    os.symlink(real_entry, sb['base'] / 'review_entry')
    # 清单里登记的是旧绝对路径（名字不变），门只看名字
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']))
    rec('A5b', 'review_entry 是指向 paths.root 之外的符号链接', rc=rc, stderr=err[-300:],
        outside_entry_after=sorted(os.listdir(real_entry)), seconds=sec)
    # A5c 工作区根目标文件是指向外部的链接 → _confine 拒绝；看退出码与回滚
    sb = build('A5c_ws_target_symlink')
    tgt = outside / 'victim.docx'
    tgt.write_bytes(b'VICTIM')
    os.symlink(tgt, sb['base'] / 'workspace/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx')
    t0 = tree(sb['base'])
    rc, pl, err, sec = run(args_of(sb))
    dry_rc, dry_gates = rc, gates(pl)
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']))
    rec('A5c', '工作区根目标名是指向外部的符号链接：dry-run 能否预见、apply 退出码（规格：越界应为 3）、回滚全树', dry_rc=dry_rc,
        dry_gates=dry_gates, apply_rc=rc, stderr=err[-400:], victim=tgt.read_bytes().decode(),
        diff=tdiff(t0, tree(sb['base'])), seconds=sec)

    # A6 --label 路径逃逸（带 {label} 的命名模板，如必修二）
    sb = build('A6_label_escape', stem_tpl='必修三_修订{n}_{label}')
    t0 = tree(sb['base'])
    rc, pl, err, sec = run(args_of(sb, extra=['--label', '../../review_history/x']))
    dry = (rc, pl['naming'] if pl else None)
    rc, pl, err, sec = run(args_of(sb, extra=['--label', '../../review_history/x', '--apply']))
    rec('A6', '--label 含 ../ 的路径逃逸：dry-run 是否预警、apply 退出码与回滚', dry_rc=dry[0], dry_naming=dry[1], apply_rc=rc,
        stderr=err[-400:], diff=tdiff(t0, tree(sb['base'])), seconds=sec)

    # A7 冻结册绕过：真实 bixiu2 配置复制一份 frozen=false（配置路径），目标仍是真实必修二（只 dry-run，不写）
    b2 = json.loads((S / 'profiles/bixiu2.json').read_text(encoding='utf-8'))
    b2['frozen'] = False
    b2p = OUT / 'sb' / 'bixiu2_unfrozen_copy.json'
    b2p.write_text(json.dumps(b2, ensure_ascii=False), encoding='utf-8')
    sb = build('A7_frozen_src')
    rc, pl, err, sec = run(['--profile', str(b2p), '--batch', '231', '--docx', str(sb['docx']), '--pdf', str(sb['pdf']),
                            '--acceptance', str(sb['acc']), '--actor', 'test:a'])
    sys.path.insert(0, str(S))
    import docx_lib as dl
    try:
        dl.guard_write(str(ROOT / '00_必修二最新审查稿/probe.json'), b2, kind='.json')
        gw = 'guard_write 放行'
    except Exception as e:
        gw = f'guard_write 拒绝：{e}'
    rec('A7', 'frozen=false 的 bixiu2 配置副本（--profile 路径）：冻结门是否仍拦、目标是否为真实必修二', rc=rc,
        gates=[(g['id'], g['level'], g['message'][:120]) for g in pl['gates']] if pl else None,
        targets=pl['targets'] if pl else None, stderr=err[-300:], docx_lib_guard_same_target=gw, seconds=sec)
    for mode in ([], ['--apply']):
        rc, pl, err, sec = run(['--profile', 'bixiu2', '--batch', '231', '--docx', str(sb['docx']), '--pdf', str(sb['pdf']),
                                '--acceptance', str(sb['acc']), '--actor', 'test:a'] + mode)
        rec('A7_real_bixiu2' + ('_apply' if mode else '_dry'), '真实 bixiu2 配置', rc=rc, stderr=err[-200:],
            frozen_gate=pl['gates'][0] if pl else None, seconds=sec)

    # A8 候选不在 候选/<谁>/<批次>/构建/ 下：备份与晋升回执写到哪里
    sb = build('A8_candidate_in_ws_root', cand_rel='workspace')
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']))
    rec('A8', '候选 docx 放在工作区根（非 构建/）时 apply 的备份/回执落点', rc=rc, stderr=err[-300:],
        apply_result=(pl or {}).get('apply_result'),
        workspace_after=sorted(os.listdir(sb['base'] / 'workspace')), seconds=sec)
    sb = build('A8b_candidate_in_review_entry', cand_rel='review_entry/sub')
    rc, pl, err, sec = run(args_of(sb))
    rec('A8b', '候选 docx 放在审阅入口子目录（dry-run）', rc=rc, gates=gates(pl), seconds=sec)

    # A9 父稿 SHA：只给别名键 expected_working_head_sha256（前身 publish_b52 接受）且值是错的
    def mut9(a):
        a.pop('expected_current_working_head_sha256')
        a['expected_working_head_sha256'] = '0' * 64
    sb = build('A9_parent_alias', acc_mut=mut9)
    rc, pl, err, sec = run(args_of(sb))
    rec('A9', '验收只用别名键给出错误父稿 SHA', rc=rc, gates=[(g['id'], g['level'], g['message'][:100]) for g in pl['gates']], seconds=sec)
    # A9b 中央状态 working_head 文件已被人工改动（磁盘 SHA ≠ 记录），前身会拒绝
    sb = build('A9b_head_file_changed')
    Path(json.loads(sb['central'].read_text())['working_head']).write_bytes(b'HAND-CHANGED-HEAD')
    rc, pl, err, sec = run(args_of(sb))
    rec('A9b', '中央状态 working_head 磁盘文件与记录 SHA 不符', rc=rc, gates=gates(pl), seconds=sec)

    # A10 中央状态与清单的陈旧指针（真实中央状态有 review_entry/review_manifest/latest_rendered_*，清单有 previous_review_archive）
    sb = build('A10_stale_pointers',
               central_extra={'review_entry': 'WILL_BE_SET_BELOW', 'review_manifest': 'X', 'latest_rendered_docx_sha256': 'OLD',
                              'latest_rendered_pages': 3},
               manifest_extra={'previous_review_archive': '/old/第50批_原样审阅', 'body_changed': True,
                               'verified': 'root technical acceptance JSON', 'source_state': '/old/state.json'})
    c = json.loads(sb['central'].read_text())
    c['review_entry'] = str(sb['base'] / 'review_entry/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx')
    sb['central'].write_text(json.dumps(c, ensure_ascii=False))
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']))
    c2 = json.loads(sb['central'].read_text())
    m2 = json.loads((sb['base'] / 'review_entry/.review-manifest.json').read_text())
    rec('A10', 'apply 后中央状态 review_entry/latest_rendered_* 与清单 previous_review_archive 是否更新', rc=rc,
        central_review_entry=c2.get('review_entry'), central_review_entry_exists=Path(c2.get('review_entry')).exists(),
        latest_rendered_docx_sha256=c2.get('latest_rendered_docx_sha256'), latest_rendered_pages=c2.get('latest_rendered_pages'),
        manifest_previous_review_archive=m2.get('previous_review_archive'), actual_archive=(pl or {}).get('apply_result', {}).get('archive'),
        manifest_body_changed=m2.get('body_changed'), seconds=sec)

    # A11 --report 被守卫拒绝时的行为（沙盒受保护根），以及父目录不存在
    sb = build('A11_report_guard')
    prof = json.loads(sb['prof'].read_text())
    rc, pl, err, sec = run(args_of(sb, extra=['--report', str(OUT / 'no_such_dir' / 'r.json')]))
    rc2, pl2, err2, _ = run(args_of(sb, extra=['--report', str(OUT / 'r.txt')]))
    rec('A11', '--report 被 guard_write 拒绝（父目录不存在 / 扩展名不是 .json）：退出码与是否打印 traceback', rc=rc,
        traceback_printed='Traceback' in err, stderr_tail=err[-300:], rc_txt=rc2, traceback_txt='Traceback' in err2,
        stdout_plan_printed=pl is not None, seconds=sec)

    # A12 畸形输入
    cases = {
        'pdf_pages_str': lambda a: a['candidate'].__setitem__('pdf_pages', 'abc'),
        'binding_pages_str': lambda a: a['same_version_binding'].__setitem__('pdf_pages', '5'),
        'approved_str_true': lambda a: a.__setitem__('approved', 'true'),
    }
    for k, fn in cases.items():
        sb = build('A12_' + k, acc_mut=fn)
        rc, pl, err, sec = run(args_of(sb))
        rec('A12_' + k, '畸形验收字段', rc=rc, gates=gates(pl), stderr=err[-200:], traceback='Traceback' in err)
    sb = build('A12_acc_list')
    sb['acc'].write_text('[1,2]')
    rc, pl, err, sec = run(args_of(sb))
    rec('A12_acc_list', '验收 JSON 是数组', rc=rc, stderr=err[-200:], traceback='Traceback' in err)
    sb = build('A12_bad_pdf')
    sb['pdf'].write_bytes(b'not a pdf')
    rc, pl, err, sec = run(args_of(sb))
    rec('A12_bad_pdf', 'PDF 损坏', rc=rc, stderr=err[-200:], traceback='Traceback' in err)
    sb = build('A12_batch_text')
    rc, pl, err, sec = run(args_of(sb, batch='第52批'))
    rec('A12_batch_text', '--batch 第52批（与验收 52 写法不同）', rc=rc, gates=gates(pl))

    # A13 配置没有 review_history：归档目标渲染成文件系统根下路径，无任何 containment
    sb = build('A13_no_history', history=False)
    rc, pl, err, sec = run(args_of(sb))
    dry = (rc, gates(pl))
    t0 = tree(sb['base'])
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']))
    rec('A13', '配置缺 paths.review_history（及 publish.archive_to 用默认模板）', dry_rc=dry[0], dry_gates=dry[1], apply_rc=rc,
        stderr=err[-400:], diff=tdiff(t0, tree(sb['base'])), root_dir_probe=[p for p in os.listdir('/') if '原样审阅' in p])

    # A14 latest_batch 带别的数字：递增门取第一个数字
    sb = build('A14_batch_parse', latest_batch='R31续修_batch52')
    rc, pl, err, sec = run(args_of(sb, batch='40', extra=[]),)
    rec('A14', '中央状态 latest_batch=R31续修_batch52 时 --batch 40 的递增门', rc=rc,
        batch_gate=[g for g in pl['gates'] if g['id'] == 'batch_monotonic'] if pl else None)

    # A15 dry-run 计划是否列出逐文件的复制/归档/更新目标与 SHA
    sb = build('A15_plan')
    rc, pl, err, sec = run(args_of(sb))
    rec('A15', 'dry-run 计划内容', rc=rc, plan_keys=sorted(pl.keys()), targets=pl['targets'],
        has_archive_target=('archive' in json.dumps(pl, ensure_ascii=False)))

    # A16 真实 bixiu3 发布模板（central_state_backup 不带 {stamp}）：两次失败/成功是否覆盖旧备份
    sb = build('A16_backup_nostamp', backup_tpl='{candidate}/发布准备/状态备份')
    bdir = sb['cand_dir'].parent / '发布准备/状态备份'
    bdir.mkdir(parents=True)
    (bdir / 'central_state.json').write_text('{"EARLIER_BACKUP": true}')
    rc, pl, err, sec = run(args_of(sb, extra=['--apply']), INJ_BEFORE % 'central_state.json')
    rec('A16', 'bixiu3 实际模板 "{candidate}/发布准备/状态备份"（无 stamp）：已有备份是否被覆盖', rc=rc,
        earlier_backup_now=(bdir / 'central_state.json').read_text()[:80])

    # A17 health 门与 batch_health 一致性（进程内，B3_04 + 目录定位PDF；accepted_health_fails 分支）
    import batch_health as bh
    import publish_review as pr
    p3 = json.loads((S / 'profiles/bixiu3.json').read_text(encoding='utf-8'))
    p3 = bh.load_profile('bixiu3') if hasattr(bh, 'load_profile') else p3

    class A:
        health = True
    t = time.time()
    rep = bh.run_health(str(REAL['docx04']), str(REAL['pdf04']), profile=p3)
    fail_rules = sorted({f['rule'] for f in rep['findings'] if f['level'] == 'FAIL'})
    g_none = pr.gate_health(A, p3, REAL['docx04'], REAL['pdf04'], {})
    g_acc = pr.gate_health(A, p3, REAL['docx04'], REAL['pdf04'], {'accepted_health_fails': fail_rules})
    g_part = pr.gate_health(A, p3, REAL['docx04'], REAL['pdf04'], {'accepted_health_fails': fail_rules[:1]})
    rec('A17', 'health 门与 bh.run_health 结论（B3_04＋目录定位PDF）', bh_summary=dict(rep['summary']), bh_fail_rules=fail_rules,
        gate_no_accept=g_none, gate_all_accepted=g_acc, gate_partial=g_part, seconds=round(time.time() - t, 1))

    # A18 真实数据 dry-run（bixiu3，batch52 与 batch53），真实 actor
    for b in ('52', '53'):
        rc, pl, err, sec = run(['--profile', 'bixiu3', '--batch', b, '--docx', str(REAL['docx52']), '--pdf', str(REAL['pdf52']),
                                '--acceptance', str(REAL['acc52']), '--actor', 'claude:3bd4f1ab-82ef-482b-9938-ae3c518113e0'])
        rec('A18_real_b' + b, '真实数据 dry-run', rc=rc, gates=[(g['id'], g['level'], g['message'][:260]) for g in pl['gates']] if pl else None,
            stderr=err[-300:], seconds=sec)

    (OUT / 'results.json').write_text(json.dumps(RESULTS, ensure_ascii=False, indent=1, default=str), encoding='utf-8')
    print('写出', OUT / 'results.json')


if __name__ == '__main__':
    main()
