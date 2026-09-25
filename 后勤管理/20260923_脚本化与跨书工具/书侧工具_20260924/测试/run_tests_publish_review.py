#!/usr/bin/env python3
"""publish_review.py 的可重跑测试。只读真实数据，所有输出写在本脚本所在的 $SCRATCH 目录下的
sandbox/ 子目录里；沙盒配置把 paths.root / paths.central_state / paths.review_entry /
paths.workspace / paths.review_history 全部指到沙盒内部，绝不写真实审阅入口、真实中央状态、
真实接管.json 或题库。真实数据只读（docx/pdf/验收JSON/同版身份.json），测试前后核对其 SHA 与
mtime 未变。

跑法：/usr/bin/python3 run_tests_publish_review.py
"""
import tempfile
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(tempfile.gettempdir()).resolve() / 'booktools_tests' / 'publish_review'  # 输出一律落系统临时目录，不跟着本脚本进项目目录
HERE.mkdir(parents=True, exist_ok=True)
TOOL = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts/publish_review.py')
ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
PROFILES_DIR = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts/profiles')

REAL_INPUTS = {
    'B3_52_docx': ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/必修三政治与法治宝典_第52批_意见修改审阅稿.docx',
    'B3_52_pdf': ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/rendered/必修三政治与法治宝典_第52批_意见修改审阅稿.pdf',
    'B3_52_identity': ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/同版身份.json',
    'B3_52_acceptance': ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/最终主代理技术验收.json',
    'B3_51_docx': ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx',
    'B3_51_pdf': ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.pdf',
    'B3_51_manifest': ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/.review-manifest.json',
    'B3_51_note': ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/先看这里.md',
    'real_bixiu3_profile': PROFILES_DIR / 'bixiu3.json',
    'real_central_state': Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修三续作_20260908/当前状态.json'),
    'real_handoff': ROOT / '必修三_最新Skill修订_20260913/协作/接管.json',
    'real_review_entry_dir': ROOT / '00_必修三最新审查稿',
}

RESULTS = []


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def snapshot(paths):
    snap = {}
    for name, p in paths.items():
        p = Path(p)
        if p.is_file():
            snap[name] = {'sha256': sha256(p), 'mtime': p.stat().st_mtime, 'kind': 'file'}
        elif p.is_dir():
            snap[name] = {'listing': sorted(x.name for x in p.iterdir()), 'kind': 'dir'}
        else:
            snap[name] = {'kind': 'missing'}
    return snap


def run_tool(args, label):
    t0 = time.time()
    proc = subprocess.run(['/usr/bin/python3', str(TOOL)] + args, capture_output=True, text=True)
    dt = round(time.time() - t0, 3)
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip().startswith('{') else None
    except Exception:
        payload = None
    rec = {'input': label, 'args': args, 'returncode': proc.returncode, 'seconds': dt,
           'stderr_tail': proc.stderr[-2000:], 'result': payload if payload is not None else proc.stdout[-2000:]}
    RESULTS.append(rec)
    return proc, payload


def run_tool_inject(args, label, inject_code):
    """第五轮返修新增：跟 run_tool 一样跑一次 publish_review.py CLI，但先在子进程里执行
    `inject_code`（可引用已 import 好的 `pr` = publish_review 模块）打补丁，再调用 `pr.main()`。
    专用于覆盖只有在"回滚过程中再次故障"才会走到的代码路径（R19/R20/R21），CLI 本身没有开关
    能触发这些场景，只能在进程内打补丁（monkeypatch）。"""
    wrapper = (
        'import sys, json\n'
        f'sys.path.insert(0, {str(TOOL.parent)!r})\n'
        'sys.dont_write_bytecode = True\n'
        'import publish_review as pr\n'
        + inject_code + '\n'
        'sys.exit(pr.main(json.loads(sys.argv[1])))\n'
    )
    t0 = time.time()
    proc = subprocess.run(['/usr/bin/python3', '-B', '-c', wrapper, json.dumps(args, ensure_ascii=False)],
                           capture_output=True, text=True)
    dt = round(time.time() - t0, 3)
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip().startswith('{') else None
    except Exception:
        payload = None
    rec = {'input': label, 'args': args, 'returncode': proc.returncode, 'seconds': dt,
           'stderr_tail': proc.stderr[-2000:], 'result': payload if payload is not None else proc.stdout[-2000:]}
    RESULTS.append(rec)
    return proc, payload


def check(cond, msg):
    status = 'PASS' if cond else 'FAIL'
    print(f'[{status}] {msg}')
    if not cond:
        raise AssertionError(msg)


def build_sandbox(base, book_id='sandboxbixiu3'):
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    (base / 'workspace' / '协作').mkdir(parents=True)
    (base / 'review_entry').mkdir(parents=True)
    (base / 'review_history').mkdir(parents=True)

    # “现有已发布版本”＝真实 B3_51，复制进沙盒工作区根与审阅入口（只读真实文件，写的是沙盒副本）
    name51 = '必修三政治与法治宝典_R31续修_第51批_阶段审查稿'
    shutil.copy2(REAL_INPUTS['B3_51_docx'], base / 'workspace' / f'{name51}.docx')
    shutil.copy2(REAL_INPUTS['B3_51_pdf'], base / 'workspace' / f'{name51}.pdf')
    shutil.copy2(REAL_INPUTS['B3_51_docx'], base / 'review_entry' / f'{name51}.docx')
    shutil.copy2(REAL_INPUTS['B3_51_pdf'], base / 'review_entry' / f'{name51}.pdf')
    old_manifest = json.loads(REAL_INPUTS['B3_51_manifest'].read_text(encoding='utf-8'))
    old_manifest.update({
        'docx': str(base / 'review_entry' / f'{name51}.docx'), 'docx_sha256': sha256(REAL_INPUTS['B3_51_docx']),
        'bytes': REAL_INPUTS['B3_51_docx'].stat().st_size,
        'pdf': str(base / 'review_entry' / f'{name51}.pdf'), 'pdf_sha256': sha256(REAL_INPUTS['B3_51_pdf']),
        'latest_batch': 'batch51',
    })
    (base / 'review_entry' / '.review-manifest.json').write_text(json.dumps(old_manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    shutil.copy2(REAL_INPUTS['B3_51_note'], base / 'review_entry' / '先看这里.md')
    (base / 'review_entry' / '.DS_Store').write_bytes(b'\x00')  # 应被 publish.preserve 放行

    central = {
        'working_head': str(base / 'workspace' / f'{name51}.docx'),
        'working_head_sha256': sha256(REAL_INPUTS['B3_51_docx']),
        'working_head_bytes': REAL_INPUTS['B3_51_docx'].stat().st_size,
        'latest_batch': 'batch51', 'latest_render_sha256': sha256(REAL_INPUTS['B3_51_docx']),
        'latest_render_pages': 782, 'latest_render': {}, 'updated_at': '2026-09-23T00:00:00+00:00',
    }
    central_path = base / 'central_state.json'
    central_path.write_text(json.dumps(central, ensure_ascii=False, indent=2), encoding='utf-8')

    handoff = {'owner': 'test:actor-1', 'phase': 'owned', 'updated_at': '2026-09-24T00:00:00+00:00'}
    (base / 'workspace' / '协作' / '接管.json').write_text(json.dumps(handoff, ensure_ascii=False, indent=2), encoding='utf-8')

    real_prof = json.loads(REAL_INPUTS['real_bixiu3_profile'].read_text(encoding='utf-8'))
    prof = dict(real_prof)
    prof['book_id'] = book_id
    prof['title'] = '（沙盒）必修三政治与法治'
    prof['frozen'] = False
    prof.pop('frozen_note', None)
    prof['collab_key'] = 'sandbox_publish_review_从不匹配真实目录'
    prof['paths'] = {
        'root': str(base), 'workspace': 'workspace', 'review_entry': 'review_entry',
        'review_manifest': 'review_entry/.review-manifest.json', 'review_history': 'review_history',
        'central_state': str(central_path), 'handoff': 'workspace/协作/接管.json',
    }
    prof['publish'] = {
        'entry': 'review_entry', 'note_file': '先看这里.md', 'manifest': '.review-manifest.json',
        'archive_to': 'review_history/第{prev}批_原样审阅_{stamp}', 'preserve': ['.DS_Store', '~$*'],
        'central_state_backup': '{candidate}/发布准备/状态备份/{stamp}',
    }
    prof['naming'] = {
        'batch_label': '第{n}批', 'docx_stem': '必修三政治与法治宝典_R31续修_第{n}批_阶段审查稿',
        'feedback_hint': '请按“第{n}批＋PDF页码”提意见',
    }
    prof_path = base / 'sandbox_profile.json'
    prof_path.write_text(json.dumps(prof, ensure_ascii=False, indent=2), encoding='utf-8')

    # 候选目录：workspace/协作/候选/<actor>/第52批_测试_日期/构建/
    cand_dir = base / 'workspace' / '协作' / '候选' / 'test-actor' / '第52批_测试_20260924' / '构建'
    cand_dir.mkdir(parents=True)
    cand_docx = cand_dir / '必修三政治与法治宝典_第52批_候选.docx'
    cand_pdf = cand_dir / '必修三政治与法治宝典_第52批_候选.pdf'
    shutil.copy2(REAL_INPUTS['B3_52_docx'], cand_docx)
    shutil.copy2(REAL_INPUTS['B3_52_pdf'], cand_pdf)
    identity = json.loads(REAL_INPUTS['B3_52_identity'].read_text(encoding='utf-8'))
    identity['docx'] = str(cand_docx)
    identity['pdf'] = str(cand_pdf)
    (cand_dir / '同版身份.json').write_text(json.dumps(identity, ensure_ascii=False, indent=2), encoding='utf-8')

    acc = json.loads(REAL_INPUTS['B3_52_acceptance'].read_text(encoding='utf-8'))
    acc['actor_owned'] = 'test:actor-1'
    acc['batch'] = '52'
    acc['expected_current_working_head_sha256'] = central['working_head_sha256']
    acc['candidate'] = {'docx_sha256': sha256(cand_docx), 'pdf_sha256': sha256(cand_pdf), 'pdf_pages': acc['candidate']['pdf_pages']}
    acc['same_version_binding'].update({'docx_sha256': sha256(cand_docx), 'pdf_sha256': sha256(cand_pdf),
                                         'rendered_from_docx_sha256': sha256(cand_docx), 'status': 'PASS'})
    acc_path = cand_dir / '验收.json'
    acc_path.write_text(json.dumps(acc, ensure_ascii=False, indent=2), encoding='utf-8')

    note_path = cand_dir.parent / '本轮说明.md'
    note_path.write_text('# 沙盒测试说明\n\n本文件是测试用的最小审查说明，用于验证 --note 原样写入。\n', encoding='utf-8')

    return {'base': base, 'prof_path': prof_path, 'central_path': central_path,
            'cand_docx': cand_docx, 'cand_pdf': cand_pdf, 'acc_path': acc_path, 'note_path': note_path,
            'cand_dir': cand_dir, 'handoff_path': base / 'workspace/协作/接管.json',
            'review_entry': base / 'review_entry', 'manifest_path': base / 'review_entry/.review-manifest.json',
            'name51_docx_sha': sha256(REAL_INPUTS['B3_51_docx'])}


def base_args(sb, batch='52', actor='test:actor-1', extra=None):
    a = ['--profile', str(sb['prof_path']), '--batch', batch, '--docx', str(sb['cand_docx']), '--pdf', str(sb['cand_pdf']),
         '--acceptance', str(sb['acc_path']), '--actor', actor, '--note', str(sb['note_path'])]
    return a + (extra or [])


REAL_BIXIU2 = {
    'central_state': Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/必修二_周六成品冲刺_20260910/状态/当前基线.json'),
    'handoff': Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝/必修二_Astra审核修订_20260913/协作/接管.json'),
}


def test_regressions(sb_dir):
    """对应 verify_publish_review.json 里逐条 blocker/major 的回归用例。每条独立建沙盒，只读真实
    数据（若涉及），绝不写真实审阅入口/中央状态/接管.json/题库。"""

    # ---- R1（blocker#1）：工作区根同名异容文件，拒绝覆盖，不丢手改稿 ----
    r1 = build_sandbox(sb_dir / 'r1_ws_overwrite')
    ws_target = r1['base'] / 'workspace' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
    ws_target.write_bytes(b'HAND-EDITED-BY-USER')
    hand_sha = sha256(ws_target)
    proc, payload = run_tool(base_args(r1, extra=['--apply']), 'R1 工作区根同名异容覆盖 --apply')
    check(proc.returncode == 2, 'R1: 工作区根已有同名异容文件时 --apply 应门 FAIL 中止（exit 2），不是静默覆盖')
    check(sha256(ws_target) == hand_sha, 'R1: 工作区根的手改稿内容必须原封不动')
    proc, payload = run_tool(base_args(r1), 'R1 dry-run 也应报告')
    check(any(g['id'] == 'write_targets' and g['level'] == 'FAIL' for g in payload['gates']),
          'R1: dry-run 的 write_targets 门也应 FAIL（不等 --apply 才发现）')

    # ---- R2/R4（blocker#2 + major#4）：固定命名模板（新 stem 与旧登记文件同名）+ 晚期故障注入 ----
    # 只让“审阅入口里现有登记文件”与本批新 stem 同名（复现 A3 的“固定审阅副本名”场景）；
    # 工作区根的工作头仍是另一个文件名，避免和 blocker#1 的“工作区根同名异容拒绝覆盖”混在一起。
    r2 = build_sandbox(sb_dir / 'r2_same_name_rollback')
    FIXED_STEM = '必修三政治与法治宝典_审阅副本'
    old_docx = r2['review_entry'] / '必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx'
    old_pdf = r2['review_entry'] / '必修三政治与法治宝典_R31续修_第51批_阶段审查稿.pdf'
    old_docx_sha = sha256(old_docx)
    old_pdf_sha = sha256(old_pdf)
    new_old_docx = r2['review_entry'] / f'{FIXED_STEM}.docx'
    new_old_pdf = r2['review_entry'] / f'{FIXED_STEM}.pdf'
    old_docx.rename(new_old_docx)
    old_pdf.rename(new_old_pdf)
    manifest2 = json.loads(r2['manifest_path'].read_text(encoding='utf-8'))
    manifest2['docx'] = str(new_old_docx)
    manifest2['pdf'] = str(new_old_pdf)
    r2['manifest_path'].write_text(json.dumps(manifest2, ensure_ascii=False, indent=2), encoding='utf-8')
    prof2 = json.loads(r2['prof_path'].read_text(encoding='utf-8'))
    prof2['naming']['docx_stem'] = FIXED_STEM  # 不含 {n}，与刚重命名的旧登记文件同名
    r2['prof_path'].write_text(json.dumps(prof2, ensure_ascii=False), encoding='utf-8')
    before_central2 = r2['central_path'].read_text(encoding='utf-8')
    before_manifest2 = r2['manifest_path'].read_text(encoding='utf-8')
    before_note2 = (r2['review_entry'] / '先看这里.md').read_text(encoding='utf-8')
    review_history_dir = r2['base'] / 'review_history'
    receipt_path2 = r2['cand_dir'].parent / '发布准备' / '晋升回执.json'
    os.chmod(r2['base'], 0o500)  # 只挡“直接在 base 下新建/替换条目”——命中中央状态原子写的临时文件
    try:
        proc, payload = run_tool(base_args(r2, extra=['--apply']), 'R2/R4 同名 stem + 晚期故障注入')
    finally:
        os.chmod(r2['base'], 0o700)
    check(proc.returncode == 2, 'R2: 晚期故障注入应门/中止类错误退出（2）')
    check(r2['central_path'].read_text(encoding='utf-8') == before_central2, 'R2: 回滚后中央状态应与写入前一致')
    check(r2['manifest_path'].read_text(encoding='utf-8') == before_manifest2, 'R2: 回滚后清单应与写入前一致')
    check((r2['review_entry'] / '先看这里.md').read_text(encoding='utf-8') == before_note2, 'R2: 回滚后先看这里应与写入前一致')
    check(new_old_docx.is_file() and sha256(new_old_docx) == old_docx_sha and
          new_old_pdf.is_file() and sha256(new_old_pdf) == old_pdf_sha,
          'R2: 新 stem 与旧登记文件同名时，回滚后审阅入口应恢复旧版内容（不是被新内容顶替后又整体消失）')
    check(list(review_history_dir.iterdir()) == [], 'R4: 回滚后归档目录应整体删除，不留清单副本/指纹文件等半成品')
    check(not receipt_path2.is_file(), 'R4: 复核前失败不应留下 status=PROMOTED 的晋升回执')

    # ---- R3（blocker#3）：frozen=false 的 profile 副本，但写入目标是真实已登记冻结册目录 ----
    if REAL_BIXIU2['central_state'].is_file() and REAL_BIXIU2['handoff'].is_file():
        real_bixiu2 = json.loads((PROFILES_DIR / 'bixiu2.json').read_text(encoding='utf-8'))
        fake = dict(real_bixiu2)
        fake['frozen'] = False
        fake.pop('frozen_note', None)
        fake_path = sb_dir / 'r3_fake_unfrozen_bixiu2.json'
        fake_path.write_text(json.dumps(fake, ensure_ascii=False), encoding='utf-8')
        dummy_acc = sb_dir / 'r3_dummy_acceptance.json'
        dummy_acc.write_text(json.dumps({'approval_type': 'root_technical_acceptance'}, ensure_ascii=False), encoding='utf-8')
        args_r3 = ['--profile', str(fake_path), '--batch', '999', '--docx', str(REAL_INPUTS['B3_52_docx']),
                   '--pdf', str(REAL_INPUTS['B3_52_pdf']), '--acceptance', str(dummy_acc), '--actor', 'test:r3']
        proc, payload = run_tool(args_r3, 'R3 冒充非冻结 profile 但目标是真实冻结册目录（dry-run）')
        check(proc.returncode == 3, 'R3: 即使 profile.frozen=false，目标落在真实已登记冻结册目录也必须 GuardRefusal 退出 3（dry-run 也不放过）')
        check('冻结册' in (proc.stderr or ''), 'R3: 拒绝信息应点名冻结册')
    else:
        print('[SKIP] R3：真实必修二中央状态/接管.json 路径不存在，跳过（不应发生在本项目里）')

    # ---- R5（major#5）：review_history/review_entry 本身是指向沙盒外的符号链接 ----
    r5 = build_sandbox(sb_dir / 'r5_symlink_escape')
    outside = sb_dir / 'r5_outside'
    if outside.exists():
        shutil.rmtree(outside)
    outside.mkdir(parents=True)
    real_history = r5['base'] / 'review_history'
    shutil.rmtree(real_history)
    (outside / 'hist').mkdir()
    os.symlink(str(outside / 'hist'), str(real_history))
    proc, payload = run_tool(base_args(r5), 'R5a review_history 是外链（dry-run）')
    check(proc.returncode == 3, 'R5a: review_history 本身是符号链接应 dry-run 就 GuardRefusal 退出 3')
    check(list((outside / 'hist').iterdir()) == [], 'R5a: 外部目录不应被写入任何文件')

    r5b = build_sandbox(sb_dir / 'r5b_symlink_escape_entry')
    outside_entry = sb_dir / 'r5b_outside'
    if outside_entry.exists():
        shutil.rmtree(outside_entry)
    outside_entry.mkdir(parents=True)
    real_entry = r5b['base'] / 'review_entry'
    # review_entry 已含文件，先原样移到外部目录，再用外链指回沙盒
    shutil.move(str(real_entry), str(outside_entry / 'entry'))
    os.symlink(str(outside_entry / 'entry'), str(real_entry))
    proc, payload = run_tool(base_args(r5b), 'R5b review_entry 是外链（dry-run）')
    check(proc.returncode == 3, 'R5b: review_entry 本身是符号链接应 dry-run 就 GuardRefusal 退出 3')

    # ---- R6（major#6）：dry-run 逐文件计划 + stem 路径分隔符注入 + 缺 review_history ----
    r6 = build_sandbox(sb_dir / 'r6_dryrun_plan')
    proc, payload = run_tool(base_args(r6), 'R6a dry-run 应给出逐文件计划')
    files_plan = payload['targets']['files']
    check(len(files_plan) >= 5 and all('action' in f and 'dst' in f for f in files_plan),
          'R6a: dry-run 计划应含逐文件 {action,dst,...}，不止三个目录')
    check(any(f['action'] == 'archive_dir' for f in files_plan), 'R6a: 计划应包含归档目录条目')

    r6b = build_sandbox(sb_dir / 'r6b_label_traversal')
    prof6b = json.loads(r6b['prof_path'].read_text(encoding='utf-8'))
    prof6b['naming']['docx_stem'] = '必修三政治与法治宝典_第{n}批_{label}'  # 模板用到 {label}，复现 A6 的注入面
    r6b['prof_path'].write_text(json.dumps(prof6b, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(r6b, extra=['--label', '../../review_history/x']), 'R6b --label 路径穿越（dry-run）')
    check(proc.returncode == 2, 'R6b: 渲染出的 stem 含 ../ 时 dry-run 应门 FAIL（exit 2），不是 exit 0')
    check(any(g['id'] == 'write_targets' and g['level'] == 'FAIL' and '路径分隔符' in g['message'] for g in payload['gates']),
          'R6b: write_targets 门应指出 stem 含路径分隔符/上级目录')
    check(not any((sb_dir / 'r6b_label_traversal' / 'review_history').glob('*x*')),
          'R6b: 不应真的在 review_history 之外或之内产生按注入名命名的文件')

    r6c = build_sandbox(sb_dir / 'r6c_missing_history')
    prof6c = json.loads(r6c['prof_path'].read_text(encoding='utf-8'))
    del prof6c['paths']['review_history']
    r6c['prof_path'].write_text(json.dumps(prof6c, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(r6c), 'R6c 缺 paths.review_history（dry-run）')
    check(proc.returncode == 2, 'R6c: 缺 review_history 应 dry-run 门 FAIL（exit 2），不是 exit 0 之后 apply 才炸 OSError')
    check(any(g['id'] == 'write_targets' and g['level'] == 'FAIL' and 'review_history' in g['message'] for g in payload['gates']),
          'R6c: write_targets 门应指出缺 review_history')

    r6d = build_sandbox(sb_dir / 'r6d_ws_symlink_escape')
    outside_ws = sb_dir / 'r6d_outside'
    if outside_ws.exists():
        shutil.rmtree(outside_ws)
    outside_ws.mkdir(parents=True)
    ws_link_target = r6d['base'] / 'workspace' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
    os.symlink(str(outside_ws / 'evil.docx'), str(ws_link_target))
    proc, payload = run_tool(base_args(r6d), 'R6d 工作区根目标是外链（dry-run）')
    check(proc.returncode == 3, 'R6d: 工作区根目标本身是符号链接，dry-run 就应 GuardRefusal 退出 3（不是 apply 时才 2）')
    proc, payload = run_tool(base_args(r6d, extra=['--apply']), 'R6d --apply 同样应 3')
    check(proc.returncode == 3, 'R6d: --apply 时 GuardRefusal 不应被 do_apply 的 except-all 改写成退出码 2')
    check(not outside_ws.exists() or list(outside_ws.iterdir()) == [], 'R6d: 外部目录不应被写入')

    # ---- R7（major#7）：中央状态新增字段 ----
    r7 = build_sandbox(sb_dir / 'r7_central_fields')
    proc, payload = run_tool(base_args(r7, extra=['--apply']), 'R7 apply 后核中央状态新字段')
    check(proc.returncode == 0, 'R7: 正常 apply 应成功')
    new_central7 = json.loads(r7['central_path'].read_text(encoding='utf-8'))
    new_docx7 = r7['review_entry'] / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
    check(new_central7.get('review_entry') == str(new_docx7), 'R7: 中央状态 review_entry 应指向新审阅入口 docx')
    check(new_central7.get('review_manifest') == str(r7['manifest_path']), 'R7: 中央状态 review_manifest 应指向清单')
    check(new_central7.get('latest_rendered_docx_sha256') == sha256(r7['cand_docx']), 'R7: latest_rendered_docx_sha256 应更新为候选')
    check(new_central7.get('latest_rendered_pages') is not None, 'R7: latest_rendered_pages 应写出')
    new_manifest7 = json.loads(r7['manifest_path'].read_text(encoding='utf-8'))
    check(new_manifest7.get('previous_review_archive'), 'R7: 新清单应显式写 previous_review_archive（本次归档，不是沿用旧值）')
    check(new_manifest7.get('source_state') == str(r7['central_path']), 'R7: 新清单应显式写 source_state 指向中央状态文件')

    # ---- R8（major#8）：候选目录不在 …/协作/候选/<谁>/<批次>/ 下 ----
    r8 = build_sandbox(sb_dir / 'r8_candidate_root')
    bad_cand_dir = r8['base'] / 'workspace' / '构建'
    bad_cand_dir.mkdir(parents=True)
    bad_docx = bad_cand_dir / '候选.docx'
    bad_pdf = bad_cand_dir / '候选.pdf'
    shutil.copy2(r8['cand_docx'], bad_docx)
    shutil.copy2(r8['cand_pdf'], bad_pdf)
    args_r8 = ['--profile', str(r8['prof_path']), '--batch', '52', '--docx', str(bad_docx), '--pdf', str(bad_pdf),
               '--acceptance', str(r8['acc_path']), '--actor', 'test:actor-1']
    proc, payload = run_tool(args_r8, 'R8 候选目录不在 协作/候选/ 下（dry-run）')
    check(proc.returncode == 2, 'R8: 候选目录形态不对应门 FAIL（exit 2）')
    check(any(g['id'] == 'candidate_root' and g['level'] == 'FAIL' for g in payload['gates']),
          'R8: candidate_root 门应 FAIL')
    check(not (r8['base'] / 'workspace' / '发布准备').exists(), 'R8: 不应在工作区根新建 发布准备 目录')

    # ---- minor：批次号解析歧义（'R31续修_batch52' 这类）不再取第一个数字 ----
    r9 = build_sandbox(sb_dir / 'r9_batch_parse')
    central9 = json.loads(r9['central_path'].read_text(encoding='utf-8'))
    central9['latest_batch'] = 'R31续修_batch51'
    r9['central_path'].write_text(json.dumps(central9, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(r9, batch='52'), 'R9 批次号形如 R31续修_batch51 时应解析出 51')
    bm = [g for g in payload['gates'] if g['id'] == 'batch_monotonic'][0]
    check(bm['level'] == 'PASS' and '51' in bm['message'], 'R9: 批次门应从 batch51 解析出 51（而不是把 R31 的 31 当成当前批次）')
    proc, payload = run_tool(base_args(r9, batch='40'), 'R9b 用 batch51 语义下 40 应判定为倒退')
    bm2 = [g for g in payload['gates'] if g['id'] == 'batch_monotonic'][0]
    check(bm2['level'] == 'FAIL', 'R9b: 40 < 51，应判定批次倒退（旧实现会把 latest_batch 误读成 31 从而放过）')

    # R9c（r3verify minor）：归档目录名里的 {prev} 也要用同一套解析口径，不能仍取第一个数字。
    proc, payload = run_tool(base_args(r9, batch='52'), 'R9c dry-run 归档目录名应含 51，不是 31')
    archive_target = [f for f in payload['targets']['files'] if f['action'] == 'archive_dir'][0]
    check('第51批_原样审阅' in archive_target['dst'] and '第31批_原样审阅' not in archive_target['dst'],
          'R9c: 归档目录名（{prev}）应解析出 51，不应仍取 latest_batch 字符串里的第一个数字 31')

    # ---- minor：--report 路径被 guard_write 拒绝时应中文提示 + exit 3，不是 traceback + exit 1 ----
    r10 = build_sandbox(sb_dir / 'r10_report_guard')
    bad_report = sb_dir / 'r10_nonexistent_dir' / 'r.json'
    proc, payload = run_tool(base_args(r10, extra=['--report', str(bad_report)]), 'R10 --report 目标目录不存在')
    check(proc.returncode == 3, 'R10: --report 被 guard_write 拒绝应 exit 3（不是未捕获异常的 exit 1）')
    check('Traceback' not in (proc.stderr or ''), 'R10: 不应打印 Python traceback')

    # ---- minor：备份模板不含 {stamp}（真实 bixiu3 模板）时不应覆盖上一次已有的备份 ----
    r11 = build_sandbox(sb_dir / 'r11_backup_no_stamp')
    prof11 = json.loads(r11['prof_path'].read_text(encoding='utf-8'))
    prof11['publish']['central_state_backup'] = '{candidate}/发布准备/状态备份'  # 真实 bixiu3 模板，无 {stamp}
    r11['prof_path'].write_text(json.dumps(prof11, ensure_ascii=False), encoding='utf-8')
    bdir11 = r11['cand_dir'].parent / '发布准备' / '状态备份'
    bdir11.mkdir(parents=True)
    sentinel = '{"EARLIER_BACKUP": true}'
    (bdir11 / 'central_state.json').write_text(sentinel, encoding='utf-8')
    proc, payload = run_tool(base_args(r11, extra=['--apply']), 'R11 备份模板无 {stamp}，已有备份是否被吞')
    check((bdir11 / 'central_state.json').read_text(encoding='utf-8') == sentinel,
          'R11: 已有的旧备份文件不应被新一次发布直接覆盖（应套一层时间戳子目录）')
    check(proc.returncode == 0, 'R11: 套时间戳子目录后本次 apply 仍应正常成功')

    # ---- R12（r3verify blocker）：归档目录发布前就已存在，绝不能被回滚整目录删除 ----
    # R12a：archive_to 模板不含 {stamp}，归档目标在发布前就已存在 —— dry-run 的 write_targets
    # 门必须直接 FAIL（不能等到 --apply 才发现，见 compute_targets 里新加的存在性检查）。
    r12a = build_sandbox(sb_dir / 'r12a_archive_preexists_dryrun')
    prof12a = json.loads(r12a['prof_path'].read_text(encoding='utf-8'))
    prof12a['publish']['archive_to'] = 'review_history/第{prev}批_原样审阅'  # 不含 {stamp}，复现撞名/预先存在
    r12a['prof_path'].write_text(json.dumps(prof12a, ensure_ascii=False), encoding='utf-8')
    preexisting12 = r12a['base'] / 'review_history' / '第51批_原样审阅'
    preexisting12.mkdir(parents=True)
    sentinel12 = preexisting12 / '用户历史审阅稿.docx'
    sentinel12.write_bytes(b'PRECIOUS-HISTORY')
    proc, payload = run_tool(base_args(r12a), 'R12a 归档目录发布前已存在（dry-run）')
    check(any(g['id'] == 'write_targets' and g['level'] == 'FAIL' and '已存在' in g['message'] for g in payload['gates']),
          'R12a: 归档目录发布前已存在时，dry-run 的 write_targets 门应直接 FAIL')
    check(sentinel12.is_file() and sentinel12.read_bytes() == b'PRECIOUS-HISTORY', 'R12a: dry-run 不应动预先存在的归档目录')
    proc, payload = run_tool(base_args(r12a, extra=['--apply']), 'R12a --apply 同样应被 write_targets 门挡住')
    check(proc.returncode == 2, 'R12a: --apply 应因 write_targets 门 FAIL 中止（exit 2），不应进入写入流程')
    check(preexisting12.is_dir() and sentinel12.is_file() and sentinel12.read_bytes() == b'PRECIOUS-HISTORY',
          'R12a: --apply 中止后，发布前已存在的历史归档目录及内容必须原封不动')

    # R12b：直接单测 _rollback——即使调用方在 archive_dir.mkdir() 之前就把 archive_dir 指向了
    # 一个已存在的目录（例如 compute_targets 的新检查被绕过，或撞名发生在两次 stamp() 调用之间），
    # archive_created=False 时 _rollback 也绝不能 rmtree 这个目录。这是本次修复的核心断言：
    # 旧实现里 _rollback 第 3 步对 archive_dir 无条件 rmtree，会把发布前就存在的历史归档删掉。
    work12b = sb_dir / 'r12b_rollback_unit'
    if work12b.exists():
        shutil.rmtree(work12b)
    work12b.mkdir(parents=True)
    preexisting_archive12b = work12b / '第51批_原样审阅'
    preexisting_archive12b.mkdir()
    sentinel12b = preexisting_archive12b / '用户历史审阅稿.docx'
    sentinel12b.write_bytes(b'PRECIOUS-HISTORY')
    central12b = work12b / 'central.json'
    central12b.write_text('{"a":1}', encoding='utf-8')
    manifest12b = work12b / 'manifest.json'
    manifest12b.write_text('{"b":2}', encoding='utf-8')
    note12b = work12b / 'note.md'
    note12b.write_text('note', encoding='utf-8')
    receipt12b = work12b / 'receipt.json'
    backup12b = work12b / 'backup'
    backup12b.mkdir()
    shutil.copy2(central12b, backup12b / central12b.name)
    shutil.copy2(manifest12b, backup12b / manifest12b.name)
    shutil.copy2(note12b, backup12b / note12b.name)
    unit_script = (
        "import sys\n"
        f"sys.path.insert(0, {str(TOOL.parent)!r})\n"
        "import publish_review as pr\n"
        "from pathlib import Path\n"
        f"central = Path({str(central12b)!r})\n"
        f"manifest = Path({str(manifest12b)!r})\n"
        f"note = Path({str(note12b)!r})\n"
        f"receipt = Path({str(receipt12b)!r})\n"
        f"backup = Path({str(backup12b)!r})\n"
        f"archive = Path({str(preexisting_archive12b)!r})\n"
        "note_out = pr._rollback(central, manifest, note, receipt, backup,\n"
        "                        pr.sha256_file(central), pr.sha256_file(manifest), pr.sha256_file(note), None,\n"
        "                        [], [], archive, False, False)\n"
        "print(note_out)\n"
    )
    proc12b = subprocess.run(['/usr/bin/python3', '-B', '-c', unit_script], capture_output=True, text=True)
    check(proc12b.returncode == 0, f'R12b: 单测 _rollback 不应抛异常：{proc12b.stderr[-1000:]}')
    check(preexisting_archive12b.is_dir() and sentinel12b.is_file() and sentinel12b.read_bytes() == b'PRECIOUS-HISTORY',
          'R12b: archive_created=False 时 _rollback 绝不能删除传入的（发布前已存在的）归档目录')
    check('原样保留' in proc12b.stdout or '不是本次新建' in proc12b.stdout,
          'R12b: 回滚说明应明确指出该归档目录不是本次新建、未被删除')

    # ---- R13（r3verify major）：paths.review_entry 路径中间一级是指向项目根之外的符号链接 ----
    # 上一轮 major#5 只挡住了“目录本身是链接”，这里是“中间一级是链接”，_reject_symlink 看
    # 的是最后一级、不会拦；_confine 又拿 resolve 后的目录跟自己比，形同虚设。
    r13 = build_sandbox(sb_dir / 'r13_midpath_symlink_review_entry')
    outside13 = sb_dir / 'r13_outside'
    if outside13.exists():
        shutil.rmtree(outside13)
    (outside13 / 'entry').mkdir(parents=True)
    link13 = r13['base'] / 'lnk_review_entry'
    os.symlink(str(outside13), str(link13))
    prof13 = json.loads(r13['prof_path'].read_text(encoding='utf-8'))
    prof13['paths']['review_entry'] = 'lnk_review_entry/entry'
    r13['prof_path'].write_text(json.dumps(prof13, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(r13), 'R13 review_entry 路径中间一级是外链（dry-run）')
    check(proc.returncode == 3, 'R13: review_entry 路径中间一级是指向项目根之外的符号链接，dry-run 就应 GuardRefusal 退出 3')
    check(list((outside13 / 'entry').iterdir()) == [], 'R13: dry-run 不应向外部目录写入任何文件')
    proc, payload = run_tool(base_args(r13, extra=['--apply']), 'R13 --apply 同样应 3')
    check(proc.returncode == 3, 'R13: --apply 也不能绕过路径中间一级符号链接检查')
    check(list((outside13 / 'entry').iterdir()) == [], 'R13: --apply 之后外部目录仍不应有新文件')

    # ---- R14（r3verify major）：中央状态 status 与 active_revision_round 应随批次更新 ----
    # 前身 publish_b52 会更新这两项，本工具之前遗漏；只更新 latest_batch/working_head 会让
    # 读 status/active_revision_round 判断当前轮次的主代理和 collab 被旧批次文字/旧字段误导。
    r14 = build_sandbox(sb_dir / 'r14_central_status_active_round')
    proc, payload = run_tool(base_args(r14, extra=['--apply']), 'R14 apply 后核 status/active_revision_round')
    check(proc.returncode == 0, 'R14: 正常 apply 应成功')
    new_central14 = json.loads(r14['central_path'].read_text(encoding='utf-8'))
    check(new_central14.get('status') == '第52批完成，待人工审阅；整书教研终审未完成',
          'R14: 中央状态 status 应更新为新批次文案，不再是旧批次残留')
    ar14 = payload['apply_result']
    check('status' not in (ar14.get('central_state_fields_not_updated') or []), 'R14: status 不应被列为未更新字段')
    check('active_revision_round' not in (ar14.get('central_state_fields_not_updated') or []),
          'R14: active_revision_round 不应被列为未更新字段')
    active14 = new_central14.get('active_revision_round') or {}
    check(active14.get('revision') == 'batch52', 'R14: active_revision_round.revision 应指向新批次')
    check(active14.get('owner') == 'test:actor-1', 'R14: active_revision_round.owner 应是本次 actor')
    check(active14.get('docx_sha256') == sha256(r14['cand_docx']), 'R14: active_revision_round.docx_sha256 应更新为候选')
    check(active14.get('status') == 'completed_for_human_review_not_final', 'R14: active_revision_round.status 应写出')

    # ==================================================================
    # 第五轮返修回归用例（终审 final_publish_review.json）：note_file/archive_to/
    # central_state_backup 逃逸（major#1）、回滚途中再故障（major#2）、archive 中间目录清理、
    # review_history 存在性、中央状态第6步预检、summary/pdf_pages（minor）。
    # ==================================================================

    def _mutate_prof(sb, mut):
        p = json.loads(sb['prof_path'].read_text(encoding='utf-8'))
        mut(p)
        sb['prof_path'].write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding='utf-8')

    # ---- R15/R16（终审 major#1）：publish.note_file 带 '../'，之前 compute_targets 的
    # `_confine(p,[p.parent])` 恒真，能把"先看这里"写到审阅入口之外／根之外，还会连带把根外
    # 原文件当"新建"覆盖。现在 build_context 直接拒绝非单级文件名，dry-run 就 GuardRefusal。
    for rid, rel in (('R15', '../../R15_外部.md'), ('R16', '../R16_根内非入口.md')):
        rsb = build_sandbox(sb_dir / f'{rid.lower()}_note_escape')
        victim = (rsb['review_entry'] / rel).resolve()
        victim.parent.mkdir(parents=True, exist_ok=True)
        victim.write_text('# 不属于审阅入口，不应被搬走或改写\n', encoding='utf-8')
        v0 = sha256(victim)
        _mutate_prof(rsb, lambda p, rel=rel: p['publish'].__setitem__('note_file', rel))
        proc, _ = run_tool(base_args(rsb), f'{rid} dry-run')
        check(proc.returncode == 3, f'{rid}: note_file 带路径分隔符/上级目录，dry-run 应 GuardRefusal 退出 3')
        proc, _ = run_tool(base_args(rsb, extra=['--apply']), f'{rid} --apply')
        check(proc.returncode == 3, f'{rid}: --apply 同样应拒绝，不能绕过')
        check(victim.is_file() and sha256(victim) == v0, f'{rid}: 根外/入口外的同名文件不应被改写')

    # ---- R17（终审 major#1）：publish.archive_to 模板里塞 '../' 逃出 paths.review_history。
    r17 = build_sandbox(sb_dir / 'r17_archive_to_escape')
    _mutate_prof(r17, lambda p: p['publish'].__setitem__(
        'archive_to', 'review_history/../../R17_archive_外逃/第{prev}批_{stamp}'))
    proc, _ = run_tool(base_args(r17), 'R17 dry-run')
    check(proc.returncode == 3, 'R17: publish.archive_to 逃出 paths.review_history，dry-run 应 GuardRefusal 退出 3')
    proc, _ = run_tool(base_args(r17, extra=['--apply']), 'R17 --apply')
    check(proc.returncode == 3, 'R17: --apply 同样应拒绝')
    check(not (r17['base'].parent / 'R17_archive_外逃').exists(), 'R17: 不应在项目根之外新建任何目录')

    # ---- R18（终审 major#1）：publish.central_state_backup 模板逃出候选目录。
    r18 = build_sandbox(sb_dir / 'r18_backup_escape')
    _mutate_prof(r18, lambda p: p['publish'].__setitem__(
        'central_state_backup', '{candidate}/../../../R18_backup_外逃/{stamp}'))
    proc, _ = run_tool(base_args(r18), 'R18 dry-run')
    check(proc.returncode == 3, 'R18: publish.central_state_backup 逃出候选目录，dry-run 应 GuardRefusal 退出 3')
    proc, _ = run_tool(base_args(r18, extra=['--apply']), 'R18 --apply')
    check(proc.returncode == 3, 'R18: --apply 同样应拒绝')

    # ---- R19（终审 major#2）：第 6 步写中央状态失败 → 回滚里"移回归档文件"的 shutil.move
    # 再故障（双重故障）。旧版 _rollback 的这一步没有 try/except，会直接把异常抛出 _rollback
    # 本身，一路冒到 main() 的通用 `except Exception`，打印成"输入或配置错误"，让人误以为
    # 什么都没写。现在应该：_rollback 不再抛出、继续跑完剩余步骤，do_apply 改抛
    # RollbackIncomplete，main() 退出码 4，stderr 明确写"回滚不完整，需要人工核查"，且失败
    # 未能移回的文件仍完整保留在归档目录里（不会被后续的 rmtree 顺手删掉）。
    r19 = build_sandbox(sb_dir / 'r19_rollback_double_fault_move')
    inject19 = (
        "import shutil as _sh\n"
        "_om = _sh.move\n"
        "_n = [0]\n"
        "def _m(a, b, *k, **kw):\n"
        "    _n[0] += 1\n"
        "    if _n[0] == 4:\n"
        "        raise OSError('注入：回滚移回故障')\n"
        "    return _om(a, b, *k, **kw)\n"
        "_sh.move = _m\n"
        "_oj = pr.atomic_write_json\n"
        "def _w(p, d):\n"
        "    if str(p).endswith('central_state.json'):\n"
        "        raise RuntimeError('注入故障')\n"
        "    return _oj(p, d)\n"
        "pr.atomic_write_json = _w\n"
    )
    proc19, _ = run_tool_inject(base_args(r19, extra=['--apply']), 'R19 --apply 双重故障', inject19)
    check(proc19.returncode == 4, f'R19: 回滚途中再故障应退出新定义的 4，不是 2；stderr={proc19.stderr[-500:]}')
    check('回滚不完整' in proc19.stderr and '需要人工核查' in proc19.stderr,
          'R19: stderr 应明确写"回滚不完整，需要人工核查"')
    check('输入或配置错误' not in proc19.stderr, 'R19: 不能落进"输入或配置错误"的通用提示')
    old_stem19 = '必修三政治与法治宝典_R31续修_第51批_阶段审查稿'
    archived19 = list((r19['base'] / 'review_history').glob(f'*/{old_stem19}.docx'))
    check(len(archived19) == 1 and archived19[0].is_file(),
          'R19: 未能移回的旧 docx 必须仍完整留在归档目录里（不能被后续 rmtree 一并删掉、彻底丢失）')
    check(not (r19['review_entry'] / f'{old_stem19}.docx').is_file(),
          'R19（现状记录）: 该文件确实没能移回原位，这正是 incomplete 要人工核查的内容')

    # ---- R20（终审 major#2）：回滚第 4 步恢复中央状态的 shutil.copy2 再故障。
    r20 = build_sandbox(sb_dir / 'r20_rollback_double_fault_copy2')
    central_before20 = sha256(r20['central_path'])
    inject20 = (
        "import shutil as _sh\n"
        "_oc = _sh.copy2\n"
        "_armed = [False]\n"
        "def _c(a, b, *k, **kw):\n"
        "    if _armed[0] and str(b).endswith('central_state.json'):\n"
        "        raise OSError('注入：回滚恢复中央状态故障')\n"
        "    return _oc(a, b, *k, **kw)\n"
        "_sh.copy2 = _c\n"
        "_ow = pr.atomic_write_json\n"
        "def _w(p, d):\n"
        "    r = _ow(p, d)\n"
        "    if str(p).endswith('central_state.json'):\n"
        "        _armed[0] = True\n"
        "        raise RuntimeError('注入故障(写后)')\n"
        "    return r\n"
        "pr.atomic_write_json = _w\n"
    )
    proc20, _ = run_tool_inject(base_args(r20, extra=['--apply']), 'R20 --apply 双重故障', inject20)
    check(proc20.returncode == 4, f'R20: 应退出 4；stderr={proc20.stderr[-500:]}')
    check('回滚不完整' in proc20.stderr and '需要人工核查' in proc20.stderr, 'R20: stderr 应写明回滚不完整')
    check('输入或配置错误' not in proc20.stderr, 'R20: 不能落进"输入或配置错误"')
    check(sha256(r20['central_path']) != central_before20,
          'R20（现状记录）: 中央状态确实没能恢复到发布前，stderr 已如实报告，不是谎称"已回滚"')

    # ---- R21（终审 minor）：archive_dir.mkdir(parents=True) 顺带新建的中间目录，失败回滚后
    # 应该被一并删掉（只删本次新建的）。
    r21 = build_sandbox(sb_dir / 'r21_archive_intermediate_dir')
    _mutate_prof(r21, lambda p: p['publish'].__setitem__(
        'archive_to', 'review_history/新子目录/第{prev}批_原样审阅_{stamp}'))
    inject21 = (
        "_oj = pr.atomic_write_json\n"
        "def _w(p, d):\n"
        "    if str(p).endswith('central_state.json'):\n"
        "        raise RuntimeError('注入故障')\n"
        "    return _oj(p, d)\n"
        "pr.atomic_write_json = _w\n"
    )
    proc21, _ = run_tool_inject(base_args(r21, extra=['--apply']), 'R21 --apply', inject21)
    check(proc21.returncode in (2, 4), f'R21: 单一故障应回滚（2 或已知不完整则 4）；rc={proc21.returncode}')
    check(not (r21['base'] / 'review_history' / '新子目录').exists(),
          'R21: archive_to 模板带的中间目录（本次新建）回滚后不应残留')

    # ---- R22（终审 minor）：paths.review_history 配了但磁盘上不存在时，dry-run 就应 FAIL，
    # 不能全部门 PASS（旧版只能等 --apply 里 mkdir(parents=True) 顺带新建）。
    r22 = build_sandbox(sb_dir / 'r22_review_history_missing_on_disk')
    shutil.rmtree(r22['base'] / 'review_history')
    proc22, payload22 = run_tool(base_args(r22), 'R22 dry-run')
    check(proc22.returncode == 2, 'R22: paths.review_history 磁盘上不存在，dry-run 应 FAIL 退出 2')
    wt22 = next((g for g in (payload22 or {}).get('gates', []) if g['id'] == 'write_targets'), None)
    check(wt22 is not None and wt22['level'] == 'FAIL' and '不存在' in wt22['message'],
          'R22: write_targets 门应明确指出 review_history 在磁盘上不存在')

    # ---- R23/R24/R25（终审 minor）：中央状态第 6 步可预见失败在 dry-run 阶段就报出。
    r23 = build_sandbox(sb_dir / 'r23_central_fields_missing_keys')
    _mutate_prof(r23, lambda p: p['publish'].__setitem__('central_state_fields', {
        'working_head': 'working_head', 'working_head_sha256': 'working_head_sha256',
        'working_head_bytes': 'working_head_bytes', 'previous_working_head': 'previous_working_head',
        'latest_batch': 'latest_batch', 'latest_render': 'latest_render',
        'latest_render_sha256': 'latest_render_sha256', 'latest_render_pages': 'latest_render_pages',
        'updated_at': 'updated_at'}))  # 缺 review_entry/review_manifest/latest_rendered_*
    proc23, payload23 = run_tool(base_args(r23), 'R23 dry-run')
    check(proc23.returncode == 2, 'R23: central_state_fields 缺必需字段名映射，dry-run 应 FAIL 退出 2')
    wt23 = next((g for g in (payload23 or {}).get('gates', []) if g['id'] == 'write_targets'), None)
    check(wt23 is not None and wt23['level'] == 'FAIL' and 'central_state_fields' in wt23['message'],
          'R23: write_targets 门应指出缺哪些中央状态字段名映射')

    r24 = build_sandbox(sb_dir / 'r24_status_tpl_bad_placeholder')
    _mutate_prof(r24, lambda p: p['publish'].__setitem__('central_state_status_template', '第{n}批完成，{who}待审'))
    proc24, payload24 = run_tool(base_args(r24), 'R24 dry-run')
    check(proc24.returncode == 2, 'R24: publish.central_state_status_template 带未知占位符，dry-run 应 FAIL 退出 2')

    r25 = build_sandbox(sb_dir / 'r25_active_revision_round_not_dict')
    central25 = json.loads(r25['central_path'].read_text(encoding='utf-8'))
    central25['active_revision_round'] = 'batch51'
    r25['central_path'].write_text(json.dumps(central25, ensure_ascii=False), encoding='utf-8')
    proc25, payload25 = run_tool(base_args(r25), 'R25 dry-run')
    check(proc25.returncode == 2, 'R25: 中央状态里 active_revision_round 不是 dict，dry-run 应 FAIL 退出 2')

    # ---- R26（终审 minor）：active_revision_round.summary 指向本轮"先看这里"，
    # previous_working_head 带 pdf_pages。
    r26 = build_sandbox(sb_dir / 'r26_summary_and_pdf_pages')
    central26 = json.loads(r26['central_path'].read_text(encoding='utf-8'))
    central26['active_revision_round'] = {'revision': 'batch51', 'summary': '旧第51批说明.md', 'owner': 'someone'}
    central26['latest_render_pages'] = 782
    r26['central_path'].write_text(json.dumps(central26, ensure_ascii=False), encoding='utf-8')
    proc26, payload26 = run_tool(base_args(r26, extra=['--apply']), 'R26 --apply')
    check(proc26.returncode == 0, 'R26: 正常 apply 应成功')
    new_central26 = json.loads(r26['central_path'].read_text(encoding='utf-8'))
    active26 = new_central26.get('active_revision_round') or {}
    note_path26 = str((r26['review_entry'] / '先看这里.md').resolve())
    check(active26.get('summary') == note_path26,
          f'R26: active_revision_round.summary 应指向本轮"先看这里"，不是旧批次残留；实际={active26.get("summary")!r}')
    prev26 = new_central26.get('previous_working_head') or {}
    check(prev26.get('pdf_pages') == 782, f'R26: previous_working_head 应带旧 pdf_pages；实际={prev26.get("pdf_pages")!r}')

    # ---- R27（confirm major#1 剩余口子）：先看这里.md 本身是符号链接，指向项目根内、审阅入口
    # 之外的另一个真实文件。之前 note_path 在 build_context 里先 .resolve() 才检查是不是符号
    # 链接，链接早被解引用查不出来；_confine_no_escape 又只要求 realpath 落在项目根内（该攻击
    # 目标恰好还在根内），所以能以 --apply 覆盖入口外的文件。现在必须：①resolve 前逐级查符号
    # 链接，命中即 GuardRefusal；②realpath 还要求真落在 realpath(审阅入口) 内。
    r27 = build_sandbox(sb_dir / 'r27_note_symlink_inside_root_outside_entry')
    victim27 = r27['base'] / '根内他人文件.md'
    victim27.write_text('# 根内、审阅入口外的无关文件，不应被覆盖\n', encoding='utf-8')
    victim27_before = victim27.read_text(encoding='utf-8')
    note_link27 = r27['review_entry'] / '先看这里.md'
    note_link27.unlink()
    os.symlink(str(victim27), str(note_link27))
    proc, payload = run_tool(base_args(r27), 'R27 先看这里.md 是指向根内、入口外文件的符号链接（dry-run）')
    check(proc.returncode == 3, f'R27: dry-run 就应 GuardRefusal 退出 3；实际 rc={proc.returncode} stderr={proc.stderr[-500:]}')
    check(victim27.read_text(encoding='utf-8') == victim27_before, 'R27: dry-run 不应改动根内、入口外的无关文件')
    proc, payload = run_tool(base_args(r27, extra=['--apply']), 'R27 --apply 同样应 GuardRefusal')
    check(proc.returncode == 3, f'R27: --apply 也不能绕过，应退出 3；实际 rc={proc.returncode} stderr={proc.stderr[-500:]}')
    check(victim27.read_text(encoding='utf-8') == victim27_before, 'R27: --apply 之后根内、入口外的无关文件仍不应被覆盖')

    # ---- R27b（同一处修复的姊妹用例）：先看这里.md 是符号链接、指向审阅入口内的另一个文件——
    # 这种情况虽然 realpath 落在审阅入口内，但目标本身仍是符号链接，同样必须 GuardRefusal，
    # 不能因为"最终落点在入口内"就放行覆盖入口内的另一个已登记文件。
    r27b = build_sandbox(sb_dir / 'r27b_note_symlink_inside_entry')
    other27b = r27b['review_entry'] / '必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx'
    other27b_sha_before = sha256(other27b)
    note_link27b = r27b['review_entry'] / '先看这里.md'
    note_link27b.unlink()
    os.symlink(str(other27b), str(note_link27b))
    proc, payload = run_tool(base_args(r27b), 'R27b 先看这里.md 是指向审阅入口内另一文件的符号链接（dry-run）')
    check(proc.returncode == 3, f'R27b: dry-run 就应 GuardRefusal 退出 3；实际 rc={proc.returncode} stderr={proc.stderr[-500:]}')
    check(sha256(other27b) == other27b_sha_before, 'R27b: dry-run 不应改动被链接指向的入口内文件')

    # ---- R28（confirm minor）：_rollback 第 5 步核对回滚结果时，sha256_file 读取中央状态文件
    # 抛 OSError（比如文件被并发进程锁住、磁盘暂时不可读）。之前这个调用没有 try 保护，异常会
    # 冒出 _rollback，被 main() 的通用 except 打印成"输入或配置错误"（退出 2）——让人以为写入
    # 之前就失败了，而实际上中央状态/清单/先看这里可能已经在第 4 步正确恢复，只是核对读失败。
    # 现在必须：该异常计入"回滚不完整"清单（退出 4），不得冒充"输入或配置错误"，也不能跳过
    # 清单/先看这里的后续恢复与核对。
    r28 = build_sandbox(sb_dir / 'r28_rollback_verify_read_fault')
    central_before28 = r28['central_path'].read_bytes()
    inject28 = (
        "_osha = pr.sha256_file\n"
        "_armed = [False]\n"
        "def _sha(p):\n"
        "    if _armed[0] and str(p).endswith('central_state.json'):\n"
        "        raise OSError('注入：回滚核对读失败')\n"
        "    return _osha(p)\n"
        "pr.sha256_file = _sha\n"
        "_ow = pr.atomic_write_json\n"
        "def _w(p, d):\n"
        "    r = _ow(p, d)\n"
        "    if str(p).endswith('central_state.json'):\n"
        "        _armed[0] = True\n"
        "        raise RuntimeError('注入故障(写后，触发回滚)')\n"
        "    return r\n"
        "pr.atomic_write_json = _w\n"
    )
    proc28, _ = run_tool_inject(base_args(r28, extra=['--apply']), 'R28 --apply 回滚核对读故障', inject28)
    check(proc28.returncode == 4, f'R28: 回滚核对读失败应退出新定义的 4，不是 2；rc={proc28.returncode} stderr={proc28.stderr[-500:]}')
    check('回滚不完整' in proc28.stderr and '需要人工核查' in proc28.stderr,
          'R28: stderr 应明确写"回滚不完整，需要人工核查"')
    check('输入或配置错误' not in proc28.stderr, 'R28: 不能落进"输入或配置错误"的通用提示')
    check(r28['central_path'].read_bytes() == central_before28,
          'R28（现状记录）: 第 4 步的 copy2 恢复其实成功了，中央状态磁盘内容与发布前一致，'
          '只是第 5 步核对读失败——如实报告"回滚不完整"，不静默吞掉')
    old_stem28 = '必修三政治与法治宝典_R31续修_第51批_阶段审查稿'
    check((r28['review_entry'] / f'{old_stem28}.docx').is_file()
          and sha256(r28['review_entry'] / f'{old_stem28}.docx') == r28['name51_docx_sha'],
          'R28: 清单/先看这里/审阅入口文件等其余恢复步骤不应因中央状态核对读失败而被跳过——'
          '旧批次文件应已移回原位')
    new_stem28 = '必修三政治与法治宝典_R31续修_第52批_阶段审查稿'
    check(not (r28['review_entry'] / f'{new_stem28}.docx').is_file(),
          'R28: 本次新写入审阅入口的候选文件应已在回滚第 1 步被删除')

    print('回归①全部通过')


def main():
    print('== 真实输入 SHA/mtime（测试前） ==')
    before = snapshot(REAL_INPUTS)
    print(json.dumps(before, ensure_ascii=False, indent=1, default=str)[:2000])

    sb_dir = HERE / 'out'
    sb1 = build_sandbox(sb_dir / 'sandbox1')

    print('\n== 必测①：dry-run（全部门应 PASS） ==')
    proc, payload = run_tool(base_args(sb1), 'sandbox1 dry-run')
    print('returncode=', proc.returncode)
    check(proc.returncode == 0, 'dry-run 应 exit 0')
    check(payload['gates_pass'] is True, 'dry-run 门应全过')
    for g in payload['gates']:
        print(' gate', g['id'], g['level'], g['message'][:80])

    print('\n== 必测①：--apply（沙盒内真实写入） ==')
    proc, payload = run_tool(base_args(sb1, extra=['--apply']), 'sandbox1 apply')
    print('returncode=', proc.returncode)
    if proc.returncode != 0:
        print(proc.stdout[-3000:], proc.stderr[-3000:])
    check(proc.returncode == 0, 'apply 应 exit 0')
    ar = payload['apply_result']
    check(all(ar['recheck'].values()), 'apply 写后复核应全部通过')
    new_docx = sb1['review_entry'] / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
    check(new_docx.is_file() and sha256(new_docx) == sha256(sb1['cand_docx']), '审阅入口新 docx 应等于候选')
    archived51 = Path(ar['archive']) / '必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx'
    check(archived51.is_file(), '旧版应归档')
    check(not (sb1['review_entry'] / '必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx').exists(), '旧版应从审阅入口搬走')
    check((sb1['review_entry'] / '.DS_Store').is_file(), 'publish.preserve 里的 .DS_Store 应原样保留')
    new_manifest = json.loads(sb1['manifest_path'].read_text(encoding='utf-8'))
    check(new_manifest['docx_sha256'] == sha256(sb1['cand_docx']), '新清单 docx_sha256 应等于候选')
    new_central = json.loads(sb1['central_path'].read_text(encoding='utf-8'))
    check(new_central['working_head_sha256'] == sha256(sb1['cand_docx']), '中央状态 working_head_sha256 应更新为候选')
    check(new_central['previous_working_head']['docx_sha256'] == sb1['name51_docx_sha'], '中央状态应记录上一版')
    check(Path(ar['receipt']).is_file(), '晋升回执应写出')
    note_text = (sb1['review_entry'] / '先看这里.md').read_text(encoding='utf-8')
    check('沙盒测试说明' in note_text, '--note 内容应原样写入先看这里.md')

    print('\n== 必测①再跑一次：应报告已是此版/批次不递增 ==')
    proc, payload = run_tool(base_args(sb1), 'sandbox1 second dry-run (no-op expected)')
    check(proc.returncode != 0, '重复发布同一批应不再 PASS')
    ids_fail = [g['id'] for g in payload['gates'] if g['level'] == 'FAIL']
    print(' 失败的门：', ids_fail, [g['message'][:120] for g in payload['gates'] if g['level'] == 'FAIL'])
    check('batch_monotonic' in ids_fail or 'review_entry' in ids_fail, '应在 batch_monotonic 或 review_entry 门报告')

    print('\n== 必测②：故障注入 + 回滚（改坏归档目录已存在，制造中途失败）==')
    sb2 = build_sandbox(sb_dir / 'sandbox2')
    before_files = {p: sha256(p) if p.is_file() else None for p in sb2['review_entry'].rglob('*')}
    before_central = sb2['central_path'].read_text(encoding='utf-8')
    before_manifest = sb2['manifest_path'].read_text(encoding='utf-8')
    before_note = (sb2['review_entry'] / '先看这里.md').read_text(encoding='utf-8')
    # 提前把 apply 将要用的归档目录建出来（非空、只读父目录不会被删），逼 do_apply 的 archive_dir.mkdir(exist_ok=False) 抛错
    from datetime import datetime
    # 不知道 apply 用的确切 stamp，改用只读权限手法：把 review_history 整个目录设为只读，让 mkdir 失败
    rh = sb2['base'] / 'review_history'
    os.chmod(rh, 0o500)
    try:
        proc, payload = run_tool(base_args(sb2, extra=['--apply']), 'sandbox2 apply (fault injected: review_history 只读)')
    finally:
        os.chmod(rh, 0o700)
    print('returncode=', proc.returncode)
    print(proc.stderr[-1500:])
    check(proc.returncode == 2, '故障注入应以门/中止类错误退出（2）')
    check(sb2['central_path'].read_text(encoding='utf-8') == before_central, '回滚后中央状态应与写入前一致')
    check(sb2['manifest_path'].read_text(encoding='utf-8') == before_manifest, '回滚后清单应与写入前一致')
    check((sb2['review_entry'] / '先看这里.md').read_text(encoding='utf-8') == before_note, '回滚后先看这里应与写入前一致')
    after_files = {p: sha256(p) if p.is_file() else None for p in sb2['review_entry'].rglob('*')}
    check(before_files == after_files, '回滚后审阅入口文件集合与内容应与写入前一致')

    print('\n== 必测③：负例 ==')
    neg = {}

    # 冻结册：克隆沙盒配置但 frozen=true
    sb3 = build_sandbox(sb_dir / 'sandbox3')
    prof3 = json.loads(sb3['prof_path'].read_text(encoding='utf-8'))
    prof3['frozen'] = True
    prof3['frozen_note'] = '沙盒冻结测试'
    sb3['prof_path'].write_text(json.dumps(prof3, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(sb3, extra=['--apply']), '负例-冻结册 --apply')
    check(proc.returncode == 3, '冻结册 --apply 应 exit 3')
    neg['frozen_apply'] = proc.returncode
    proc, payload = run_tool(base_args(sb3), '负例-冻结册 dry-run')
    check(proc.returncode != 0 and payload['gates'][0]['level'] == 'FAIL', '冻结册 dry-run 应明说拒绝')
    neg['frozen_dryrun'] = proc.returncode

    # actor 不符
    proc, payload = run_tool(base_args(sb1, actor='someone:else'), '负例-actor不符')
    check(proc.returncode != 0, 'actor 不符应失败')
    fails = [g for g in payload['gates'] if g['level'] == 'FAIL']
    check(any(g['id'] in ('ownership', 'acceptance') for g in fails), 'actor 不符应在 ownership 或 acceptance 门报告')
    neg['actor_mismatch'] = [g['id'] for g in fails]

    # phase = offered
    sb4 = build_sandbox(sb_dir / 'sandbox4')
    ho = json.loads(sb4['handoff_path'].read_text(encoding='utf-8'))
    ho['phase'] = 'offered'
    sb4['handoff_path'].write_text(json.dumps(ho, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(sb4), '负例-phase=offered')
    check(proc.returncode != 0, 'phase=offered 应失败')
    check(any(g['id'] == 'ownership' and g['level'] == 'FAIL' for g in payload['gates']), 'ownership 门应 FAIL')
    neg['phase_offered'] = 'ownership FAIL'

    # 验收 SHA 不符
    sb5 = build_sandbox(sb_dir / 'sandbox5')
    acc5 = json.loads(sb5['acc_path'].read_text(encoding='utf-8'))
    acc5['candidate']['docx_sha256'] = 'f' * 64
    sb5['acc_path'].write_text(json.dumps(acc5, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(sb5), '负例-验收候选SHA不符')
    check(proc.returncode != 0 and any(g['id'] == 'acceptance' and g['level'] == 'FAIL' for g in payload['gates']), '验收 SHA 不符应 acceptance 门 FAIL')
    neg['acceptance_sha_mismatch'] = 'acceptance FAIL'

    # 页数不符
    sb6 = build_sandbox(sb_dir / 'sandbox6')
    acc6 = json.loads(sb6['acc_path'].read_text(encoding='utf-8'))
    acc6['candidate']['pdf_pages'] = 1
    sb6['acc_path'].write_text(json.dumps(acc6, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(sb6), '负例-页数不符')
    check(proc.returncode != 0 and any(g['id'] == 'acceptance' and g['level'] == 'FAIL' for g in payload['gates']), '页数不符应 acceptance 门 FAIL')
    neg['pdf_pages_mismatch'] = 'acceptance FAIL'

    # 同版身份不符
    sb7 = build_sandbox(sb_dir / 'sandbox7')
    ident7_path = sb7['cand_dir'] / '同版身份.json'
    ident7 = json.loads(ident7_path.read_text(encoding='utf-8'))
    ident7['pdf_pages'] = 999999
    ident7_path.write_text(json.dumps(ident7, ensure_ascii=False), encoding='utf-8')
    proc, payload = run_tool(base_args(sb7), '负例-同版身份不符')
    check(proc.returncode != 0 and any(g['id'] == 'same_version_identity' and g['level'] == 'FAIL' for g in payload['gates']), '同版身份不符应 FAIL')
    neg['same_version_identity_mismatch'] = 'same_version_identity FAIL'

    # 审阅入口多出未知文件
    sb8 = build_sandbox(sb_dir / 'sandbox8')
    (sb8['review_entry'] / '未登记的杂项.txt').write_text('x', encoding='utf-8')
    proc, payload = run_tool(base_args(sb8), '负例-审阅入口多出未知文件')
    check(proc.returncode != 0 and any(g['id'] == 'review_entry' and g['level'] == 'FAIL' for g in payload['gates']), '多出未知文件应 review_entry 门 FAIL')
    neg['review_entry_unknown_file'] = 'review_entry FAIL'

    # 批次不递增
    proc, payload = run_tool(base_args(sb1, batch='51'), '负例-批次不递增')
    check(proc.returncode != 0 and any(g['id'] == 'batch_monotonic' and g['level'] == 'FAIL' for g in payload['gates']), '批次不递增应 FAIL')
    neg['batch_not_increasing'] = 'batch_monotonic FAIL'

    print('\n负例小结：', json.dumps(neg, ensure_ascii=False, indent=1))

    print('\n== 回归①（fix_publish_review 回执 issues_resolved 逐条用例）==')
    test_regressions(sb_dir)

    print('\n== 必测④：真实数据 dry-run（bixiu3 batch52，真实文件绝不可写）==')
    real_args = ['--profile', 'bixiu3', '--batch', '52', '--docx', str(REAL_INPUTS['B3_52_docx']),
                 '--pdf', str(REAL_INPUTS['B3_52_pdf']), '--acceptance', str(REAL_INPUTS['B3_52_acceptance']),
                 '--actor', 'claude:3bd4f1ab-82ef-482b-9938-ae3c518113e0']
    proc, payload = run_tool(real_args, 'real bixiu3 batch52 dry-run')
    print('returncode=', proc.returncode)
    print(json.dumps(payload['gates'], ensure_ascii=False, indent=1) if payload else proc.stdout[-3000:])
    real_dry_run_report = payload

    after = snapshot(REAL_INPUTS)
    check(before == after, '真实输入 SHA/mtime 测试前后必须完全一致')
    print('\n真实输入 SHA/mtime（测试后，核对与测试前一致）：一致')

    print('\n== __pycache__ 核对 ==')
    pcache = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts/__pycache__')
    listing = sorted(p.name for p in pcache.iterdir()) if pcache.is_dir() else []
    print(listing)
    check(not any('publish_review' in n for n in listing), '__pycache__ 不应出现 publish_review 的编译缓存')

    out = {
        'ok': True,
        'results': RESULTS,
        'negatives': neg,
        'real_dry_run_report': real_dry_run_report,
        'real_inputs_before': before,
        'real_inputs_after': after,
    }
    (HERE / 'test_results.json').write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding='utf-8')
    print('\n全部测试通过，结果见', HERE / 'test_results.json')


if __name__ == '__main__':
    try:
        main()
    except AssertionError as e:
        print('测试失败：', e, file=sys.stderr)
        sys.exit(1)
