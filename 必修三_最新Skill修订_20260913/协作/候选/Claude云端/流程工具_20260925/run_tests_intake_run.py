#!/usr/bin/env python3
"""intake_run.py 回归测试（2026-09-25）。

只读真实输入（题库、书稿、归属表）；除下面明确列出的三处真实子进程写出（都是别的、已验收工具自己
的读写权限，且全部只往本会话 scratch 目录写）之外，不改动任何真实文件。全部本工具自己的输出
（--report/--md/init 骨架）只写 SCRATCH（本会话 scratchpad，环境不同则退回系统临时目录）或
C/构建/intake_run/。baseline_guard 在测试前后各跑一次，证明真实输入（书稿、题库、归属表、Skill、
协作、原材料、云端/）未被本轮测试改动。

用真实子进程调用 intake_run.py（本工具），核对终端表、--report/--md 产物与退出码。第 3、4、6 组另外
真实调用四个已验收的姊妹/既有工具（exam_register.py、placement_suggest.py、check_drill_admission.py、
block_insert.py），产出 intake_run.py 要读的真实证据文件，全部写到 SCRATCH 下——block_insert apply
只写一份 BOOK3 的临时副本（先 copy 到 SCRATCH 再 apply，从不对真实书稿 --out），不碰题库/书稿/协作
文件。组4另有几条直接调用 intake_run.check_step9()（不经子进程）单测 --local-final 分支，用合成的
publish 报告形状（不真的跑 publish_review --apply）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True  # 本文件也会 import intake_run，不给候选目录留 __pycache__

HERE = Path(__file__).resolve().parent
TOOL = HERE / 'intake_run.py'
EXAM_REGISTER = HERE / 'exam_register.py'
PLACEMENT_SUGGEST = HERE / 'placement_suggest.py'
BLOCK_INSERT = HERE / 'block_insert.py'
BASELINE_GUARD = HERE / 'tools' / 'baseline_guard.py'
BASELINE_BASE = HERE / '构建' / 'baseline_20260925.json'
BUILD_OUT = HERE / '构建' / 'intake_run'

sys.path.insert(0, str(HERE))
import intake_run as ir  # noqa: E402  复用其 REPO_ROOT/normalize_qid/load_attribution 等做直接单测
import batch_health as bh_module  # noqa: E402  组6：直接核 batch_health 自己的输出守卫，不真的跑体检

REPO_ROOT = ir.REPO_ROOT
BANK = REPO_ROOT / 'DeepSeek_政治题库资料库_20260918'
SK_DIR = ir.SK_DIR
CHECK_DRILL_ADMISSION = SK_DIR / 'check_drill_admission.py'
LAYOUT_PREPARE = SK_DIR / 'layout_prepare.py'
BATCH_HEALTH = SK_DIR / 'batch_health.py'
BOOK3 = REPO_ROOT / '必修三_最新Skill修订_20260913' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'

_SESSION_SCRATCH = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad')
SCRATCH = (_SESSION_SCRATCH if _SESSION_SCRATCH.is_dir() else Path(tempfile.gettempdir())) / 'intake_run_test_scratch'

PROFILES = {
    'bixiu3': HERE / 'profiles_cloud' / 'bixiu3.json',
    'philosophy': HERE / 'profiles_cloud' / 'philosophy.draft.json',
    'culture': HERE / 'profiles_cloud' / 'culture.draft.json',
    'xuanbi1': HERE / 'profiles_cloud' / 'xuanbi1.draft.json',
    'xuanbi2': HERE / 'profiles_cloud' / 'xuanbi2.draft.json',
    'mind': HERE / 'profiles_cloud' / 'mind.draft.json',
    'reasoning': HERE / 'profiles_cloud' / 'reasoning.draft.json',
}

results = []


def record(name, ok, detail='', seconds=None):
    t = f'{seconds:.1f}s' if seconds is not None else ''
    results.append({'test': name, 'ok': bool(ok), 'detail': detail, 'seconds': seconds})
    print(('PASS' if ok else 'FAIL'), name, t, ('- ' + detail) if detail else '')


def run(tool, args, timeout=180, cwd=None):
    t0 = time.time()
    p = subprocess.run([sys.executable, '-B', str(tool)] + args, capture_output=True, text=True,
                        timeout=timeout, cwd=str(cwd) if cwd else None)
    dt = time.time() - t0
    return p.returncode, p.stdout, p.stderr, dt


def baseline_check(label):
    t0 = time.time()
    p = subprocess.run([sys.executable, '-B', str(BASELINE_GUARD), 'check', '--base', str(BASELINE_BASE)],
                        capture_output=True, text=True, timeout=180)
    dt = time.time() - t0
    ok = p.returncode == 0
    record(f'baseline_guard（真实输入未变，{label}）', ok, p.stdout.strip()[:400] if not ok else '', dt)
    return ok


def write_manifest(path, batch, exams, books, profiles, workdir):
    data = {'schema': 'baodian_intake_v1', 'batch': batch, 'exams': exams, 'books': books,
            'profiles': profiles, 'workdir': str(workdir)}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')
    return Path(path)


def status_report(manifest_path, report_path, extra_args=(), timeout=180):
    code, out, err, dt = run(TOOL, ['status', '--manifest', str(manifest_path), '--report', str(report_path),
                                     '--quiet'] + list(extra_args), timeout=timeout)
    data = None
    if Path(report_path).is_file():
        try:
            data = json.loads(Path(report_path).read_text(encoding='utf-8'))
        except Exception:
            data = None
    return code, data, out, err, dt


def row_of(rep, exam_id, book):
    for r in rep['rows']:
        if r['exam'] == exam_id and r['book'] == book:
            return r
    return None


def step_of(row, n):
    return row['steps'][n - 1]


def setup():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    BUILD_OUT.mkdir(parents=True, exist_ok=True)
    for old in BUILD_OUT.glob('test_*.json'):
        old.unlink()


# ---------------------------------------------------------------- 组1：纯函数直接单测（不起子进程，快）
def group1_unit():
    ok = ir.normalize_qid('BJ-2023-HD-QIZHONG-Q18#1') == 'BJ-2023-HD-QIZHONG-Q18(1)'
    record('1a normalize_qid：#N → (N)', ok, ir.normalize_qid('BJ-2023-HD-QIZHONG-Q18#1'))
    ok = ir.normalize_qid('BJ-2020-BJ-GAOKAO-Q10') == 'BJ-2020-BJ-GAOKAO-Q10'
    record('1b normalize_qid：无小问原样返回', ok)

    attr, sha = ir.load_attribution(ir.DEFAULT_ATTRIBUTION_CSV)
    rows = attr.get('BJ-2023-HD-QIZHONG', [])
    unit_ids = [r['unit_id'] for r in rows]
    ok = len(unit_ids) == len(set(unit_ids)) and len(rows) == 24
    record('1c load_attribution 去重：exam_id_raw==exam_id_canonical 的卷不重复计入（BJ-2023-HD-QIZHONG '
           '在 attribution_ruled.csv 里恰好 24 行——Q1..Q17、Q19..Q23 各1行+Q18 拆 #1/#2 共2行，且 '
           'unit_id 不重复——修前曾因 raw/canonical 都命中同一 key 被 append 两次，会变成48行）',
           ok, f'len={len(rows)} unique={len(unit_ids)}')
    ok = sha and len(sha) == 64
    record('1d load_attribution 返回 attribution_ruled.csv 的 sha256', bool(ok), str(sha)[:16])

    # 清单校验：负例（m7 新增卷号格式/重复两类；原有 4 类的 exam_id 改成合法格式，避免被新加的格式
    # 校验提前拦下，测不到原本想测的那一层）
    bad_cases = [
        ({'schema': 'x'}, 'schema 不是 baodian_intake_v1'),
        ({'schema': 'baodian_intake_v1', 'batch': 'b', 'exams': [], 'books': ['bixiu3'],
          'profiles': {'bixiu3': 'x'}, 'workdir': 'w'}, 'exams'),
        ({'schema': 'baodian_intake_v1', 'batch': 'b', 'exams': [{'exam_id': 'BJ-2099-ZZ-QIZHONG'}],
          'books': ['no_such_book'], 'profiles': {}, 'workdir': 'w'}, '书名未知'),
        ({'schema': 'baodian_intake_v1', 'batch': 'b', 'exams': [{'exam_id': 'BJ-2099-ZZ-QIZHONG'}],
          'books': ['bixiu3'], 'profiles': {}, 'workdir': 'w'}, 'profiles.bixiu3'),
        ({'schema': 'baodian_intake_v1', 'batch': 'b', 'exams': [{'exam_id': 'X'}], 'books': ['bixiu3'],
          'profiles': {'bixiu3': 'x'}, 'workdir': 'w'}, '格式不对'),
        ({'schema': 'baodian_intake_v1', 'batch': 'b',
          'exams': [{'exam_id': 'BJ-2026-CY-QIZHONG'}, {'exam_id': 'BJ-2026-CY-QIZHONG'}],
          'books': ['bixiu3'], 'profiles': {'bixiu3': 'x'}, 'workdir': 'w'}, '重复'),
        ({'schema': 'baodian_intake_v1', 'batch': 'b', 'exams': [{'exam_id': 'BJ-2099-ZZ-QIZHONG'}],
          'books': ['bixiu3', 'bixiu3'], 'profiles': {'bixiu3': 'x'}, 'workdir': 'w'}, 'books 有重复'),
    ]
    for i, (bad, expect_sub) in enumerate(bad_cases):
        p = SCRATCH / f'bad_manifest_{i}.json'
        p.write_text(json.dumps(bad, ensure_ascii=False), encoding='utf-8')
        try:
            ir.load_manifest(p)
            ok, detail = False, '未抛异常'
        except ir.InputError as e:
            ok, detail = (expect_sub in str(e)), str(e)
        record(f'1e-{i} load_manifest 负例（期望含“{expect_sub}”）', ok, detail)

    # 正例：books 含 bixiu2 时不要求给 profiles.bixiu2
    good = {'schema': 'baodian_intake_v1', 'batch': 'b', 'exams': [{'exam_id': 'BJ-2099-ZZ-QIZHONG'}],
            'books': ['bixiu3', 'bixiu2'], 'profiles': {'bixiu3': 'x'}, 'workdir': 'w'}
    p = SCRATCH / 'good_manifest.json'
    p.write_text(json.dumps(good, ensure_ascii=False), encoding='utf-8')
    try:
        m = ir.load_manifest(p)
        ok = m['batch'] == 'b'
    except Exception as e:
        ok = False
    record('1f load_manifest 正例：bixiu2 不要求 profiles.bixiu2', ok)

    # ---- M1：merge_twin_rows 按 (canonical_qid, subq) 归并孪生/别名行 ----
    attr, _ = ir.load_attribution(ir.DEFAULT_ATTRIBUTION_CSV)
    raw_2024 = ir.attribution_rows_for(attr, 'BJ-2024-HD-QIZHONG')
    ok = len(raw_2024) == 48  # 23 本卷自己 + 25 别名 BJ-2025-HD-QIZHONG（M1 审查证据里的原始数字）
    record('1g 归并前：BJ-2024-HD-QIZHONG 原始行数（本卷+别名）', ok, f'len={len(raw_2024)}')
    merged, alias_map = ir.merge_twin_rows(raw_2024)
    uids = [r['unit_id'] for r in merged]
    # 25 组：23 个 2024/2025 两侧共享的 canonical 等价类（换成 BJ-2024-HD-QIZHONG-* 形式）+ 2025 自己
    # 的 Q25#1/#2（admission=身份错误-不计入分母，canonical_qid 指向自己，不与任何 2024 侧的题合并，
    # 仍保留 BJ-2025-HD-QIZHONG-* 形式——这两个是唯一合法例外，其余不该再出现别名前缀）。
    non_q25_2025 = [u for u in uids if u.startswith('BJ-2025-HD-QIZHONG') and 'Q25' not in u]
    ok = (len(uids) == len(set(uids)) == 25 and not non_q25_2025 and 'BJ-2024-HD-QIZHONG-Q18' in uids)
    record('1h 归并后：unit_id 不重复共25组，只有未合并的 Q25#1/#2 保留 BJ-2025-HD-QIZHONG-* 前缀', ok,
           f'n={len(uids)} 意外别名={non_q25_2025}')
    ok = alias_map.get('BJ-2025-HD-QIZHONG-Q18') == 'BJ-2024-HD-QIZHONG-Q18'
    record('1i alias_map：BJ-2025-HD-QIZHONG-Q18 → BJ-2024-HD-QIZHONG-Q18', ok, str(alias_map.get('BJ-2025-HD-QIZHONG-Q18')))
    q19 = next(r for r in merged if r['unit_id'] == 'BJ-2024-HD-QIZHONG-Q19')
    ok = q19.get('归属_B3') == 'COLLECTED'
    record('1j 归并：COLLECTED 优先于 MAYBE/IN（任一侧已在书里就算在书里）', ok, str(q19.get('归属_B3')))
    q25 = [r for r in merged if r['unit_id'].startswith('BJ-2025-HD-QIZHONG-Q25')]
    ok = len(q25) == 2  # 身份错误行 canonical_qid 指向自己，不与任何 2024 侧的题合并成一组
    record('1k 归并：身份错误的 Q25#1/#2（canonical_qid 指向自己）不与旁的题混进同一组', ok, str([r['unit_id'] for r in q25]))

    # ---- M4：collectable_rows 按 admission/各书清单_v4 过滤准入 ----
    book_lists_v4 = ir.load_book_lists_v4(ir.DEFAULT_ATTRIBUTION_CSV)
    raw_2026hd = ir.attribution_rows_for(attr, 'BJ-2026-HD-QIZHONG')
    merged_2026hd, _ = ir.merge_twin_rows(raw_2026hd)
    collect, defer, exclude = ir.collectable_rows(merged_2026hd, 'B3', book_lists_v4)
    excl_ids = {x['unit_id'] for x in exclude}
    coll_ids = {x['unit_id'] for x in collect}
    ok = 'BJ-2026-HD-QIZHONG-Q22#2' in excl_ids and 'BJ-2026-HD-QIZHONG-Q22#2' not in coll_ids
    record('1l M4 回归：BJ-2026-HD-QIZHONG-Q22#2×bixiu3（admission=待裁决，各书清单_v4=不收-无E1）'
           '不进“该收”清单', ok, str([x for x in exclude if x['unit_id'] == 'BJ-2026-HD-QIZHONG-Q22#2']))

    # ---- M3：默认题库/归属表根优先取 profile 的 paths.root/sources.bank.root ----
    fake_prof = {'paths': {'root': str(SCRATCH)}, 'sources': {'bank': {'root': 'my_bank'}}}
    ok = ir._default_bank_root(fake_prof) == (SCRATCH / 'my_bank').resolve()
    record('1m M3 回归：_default_bank_root 取 profile.paths.root + sources.bank.root，不依赖 REPO_ROOT',
           ok, str(ir._default_bank_root(fake_prof)))
    ok = str(ir._default_attribution_csv(fake_prof)).startswith(str(SCRATCH.resolve()))
    record('1n M3 回归：_default_attribution_csv 取 profile.paths.root', ok, str(ir._default_attribution_csv(fake_prof)))

    # ---- M5：guard_write 传 house profile 后，_house.json 的 protected_roots 生效；workdir 白名单 ----
    house_prof = ir._house_guard_profile()
    ok = set(house_prof.get('output_guard', {}).get('protected_roots', [])) >= {'~/.claude/skills', '~/.codex/skills'}
    record('1o M5 回归：_house_guard_profile 带出 _house.json 的 output_guard.protected_roots', ok,
           str(house_prof.get('output_guard')))
    try:
        ir.dl.guard_write(Path('/root/.claude/skills/intake_probe_never_written.json'), house_prof, kind='.json')
        ok, detail = False, '未拒绝（不写盘，只探测路径判定）'
    except ir.dl.GuardError as e:
        ok, detail = True, str(e)
    record('1p M5 回归：guard_write(house_prof) 拒绝写到 /root/.claude/skills 下（旧版 prof=None 会放行）', ok, detail)
    for bad_wd in ('/root/.claude/skills/x_workdir', '/home/user/some_other_place/x'):
        try:
            ir._check_workdir_allowed(bad_wd)
            ok, detail = False, f'{bad_wd} 未被拒绝'
        except ir.dl.GuardError:
            ok, detail = True, ''
        record(f'1q M5 回归：_check_workdir_allowed 拒绝仓库外任意路径（{bad_wd}）', ok, detail)


# ---------------------------------------------------------------- 组2：init 子命令
def group2_init():
    out = SCRATCH / 'init1' / 'manifest.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    workdir = SCRATCH / 'init1' / '入书_t1'
    code, sout, serr, dt = run(TOOL, ['init', '--out', str(out), '--batch', 't1',
                                       '--exam-id', 'BJ-2026-HD-QIZHONG', '--book', 'bixiu3',
                                       '--workdir', str(workdir)])
    # M6：05_placement/06_insert/07_drill 现在按 --book 建到 <book> 这一层；09_health 不在 workdir 下建
    # （health 报告改放 _health_report_dir()，见组6）。
    subs_top = ['01_source_intake', '02_exam_register', '03_bank_compile', '09_layout', '09_publish']
    subs_book = [f'{s}/bixiu3' for s in ('05_placement', '06_insert', '07_drill')]
    all_dirs = all((workdir / s).is_dir() for s in subs_top + subs_book)
    no_health_dir = not (workdir / '09_health').exists()
    m = json.loads(out.read_text(encoding='utf-8')) if out.is_file() else {}
    ok = (code == 0 and out.is_file() and all_dirs and no_health_dir and m.get('schema') == 'baodian_intake_v1'
          and m.get('exams') == [{'exam_id': 'BJ-2026-HD-QIZHONG'}] and m.get('books') == ['bixiu3'])
    record('2a init：清单骨架 + workdir 子目录（M6：05/06/07 按 book 建，09_health 不在 workdir 下）',
           ok, f'exit={code} err={serr.strip()[:200]} all_dirs={all_dirs} no_health_dir={no_health_dir}', dt)

    code2, _, _, _ = run(TOOL, ['init', '--out', str(out), '--batch', 't1'])
    record('2b init 重跑（目标已存在）→ 拒绝覆盖，退出3', code2 == 3, f'exit={code2}')

    out2 = SCRATCH / 'init2' / 'manifest.json'
    out2.parent.mkdir(parents=True, exist_ok=True)
    evil_workdir = REPO_ROOT / '后勤管理' / 'evil_workdir_should_not_exist'
    code3, _, err3, _ = run(TOOL, ['init', '--out', str(out2), '--batch', 't2', '--workdir', str(evil_workdir)])
    ok = (code3 == 3 and not out2.is_file() and not evil_workdir.exists())
    record('2c init：workdir 落受保护目录 → 拒绝，退出3，且不留下清单骨架（约定4：不留半成品）',
           ok, f'exit={code3} out_exists={out2.is_file()} workdir_exists={evil_workdir.exists()}')

    # M5：workdir 完全在仓库外（不在任何受保护根内，旧版会放行并真的建目录）→ 现在也必须拒绝
    out2b = SCRATCH / 'init2b' / 'manifest.json'
    out2b.parent.mkdir(parents=True, exist_ok=True)
    outside_repo_wd = Path('/home/user/intake_run_test_outside_repo_should_not_exist')
    code2b, _, err2b, _ = run(TOOL, ['init', '--out', str(out2b), '--batch', 't2b', '--workdir', str(outside_repo_wd)])
    ok = (code2b == 3 and not out2b.is_file() and not outside_repo_wd.exists())
    if outside_repo_wd.exists():
        shutil.rmtree(outside_repo_wd)  # 万一断言失败，测试自己清理，不留痕迹
    record('2d M5 回归：workdir 在仓库外、不在任何受保护根内 → 也拒绝，不再“不在仓库根内就放行”',
           ok, f'exit={code2b} created={outside_repo_wd.exists()}')

    # m7：init 的 --book/--exam-id 也要校验，不把未知书名/坏格式原样写进清单骨架
    out3 = SCRATCH / 'init3' / 'manifest.json'
    out3.parent.mkdir(parents=True, exist_ok=True)
    code4, _, err4, _ = run(TOOL, ['init', '--out', str(out3), '--batch', 't3', '--book', 'no_such_book'])
    record('2e m7 回归：init --book 未知书名 → 退出2，不写出', code4 == 2 and not out3.is_file(), f'exit={code4}')
    code5, _, err5, _ = run(TOOL, ['init', '--out', str(out3), '--batch', 't3', '--exam-id', '乱写卷号'])
    record('2f m7 回归：init --exam-id 格式不对 → 退出2，不写出', code5 == 2 and not out3.is_file(), f'exit={code5}')


# ---------------------------------------------------------------- 组3：真实数据（验收①）
KNOWN_EXAMS = ['BJ-2023-HD-QIZHONG', 'BJ-2024-HD-QIZHONG', 'BJ-2024-CY-QIZHONG',
               'BJ-2026-CY-QIZHONG', 'BJ-2026-HD-QIZHONG']
ALL_BOOKS = ['bixiu3', 'philosophy', 'culture', 'xuanbi1', 'xuanbi2', 'mind', 'reasoning', 'bixiu2']


def group3_real_matrix():
    wd = SCRATCH / '入书_real_batch'
    wd.mkdir(parents=True, exist_ok=True)
    ir._mkdirs(wd)  # 预建 9 个子目录，姊妹工具的 --report/--out 写出需要父目录已存在
    manifest = write_manifest(
        SCRATCH / 'manifest_real.json', 'real_20260925',
        [{'exam_id': e} for e in KNOWN_EXAMS], ALL_BOOKS,
        {b: str(p) for b, p in PROFILES.items()}, wd)
    code, rep, out, err, dt = status_report(manifest, SCRATCH / 'real_report_stage0.json', timeout=300)
    record('3a status 真实5卷×8书（40组合）成功跑完，退出码1（有待处理）', code == 1 and rep is not None,
           f'exit={code} err={err.strip()[:200]}', dt)
    if rep is None:
        return
    record('3a-summary', True, f'combos={rep["summary"]["combos"]} pending={rep["summary"]["pending_combos"]}')

    # bixiu2 全部 SKIP，且从不加载配置（manifest 里 bixiu2 没给 profiles 也不报错，已在组1f 验证）
    b2_rows = [r for r in rep['rows'] if r['book'] == 'bixiu2']
    ok = len(b2_rows) == 5 and all(all(s['status'] == 'SKIP' for s in r['steps']) for r in b2_rows)
    record('3b bixiu2 五行全部 9 步 SKIP（冻结且不在云端）', ok)

    # 已知事实①：5 张卷都已在题库 → 第1步 DONE
    ok = all(step_of(row_of(rep, e, 'bixiu3'), 1)['status'] == 'DONE' for e in KNOWN_EXAMS)
    record('3c 已知事实：5 张卷均已在题库 questions/ 下 → 第1步 source_intake DONE', ok)

    # 已知事实②：归属判定已做 → 第4步 DONE（对全部非 bixiu2 书）
    missing_attr = [(e, b) for e in KNOWN_EXAMS for b in ALL_BOOKS if b != 'bixiu2'
                    and step_of(row_of(rep, e, b), 4)['status'] != 'DONE']
    record('3d 已知事实：5 张卷×7书归属判定均已完成 → 第4步全部 DONE', not missing_attr, str(missing_attr[:5]))

    # 已知事实③：部分题已在必修三第52批里 → 第8步应有“已找到”的部分。M7（3e 原判据 any(...) 空断言：
    # 应收为空的卷天然 DONE，block_index 全部失效时仍能 PASS）改成断言具体题键落在 found 里。
    s8_2024hd = step_of(row_of(rep, 'BJ-2024-HD-QIZHONG', 'bixiu3'), 8)
    expect_found = {'BJ-2024-HD-QIZHONG-Q7', 'BJ-2024-HD-QIZHONG-Q18'}
    got_found = set(s8_2024hd['evidence'].get('found') or [])
    record('3e M7 回归：BJ-2024-HD-QIZHONG×bixiu3 第8步 found 里能具体查到 Q7、Q18（不是空断言）',
           expect_found <= got_found, f'found={sorted(got_found)}')

    # M1 回归：孪生/别名（BJ-2024/2025-HD-QIZHONG）按 canonical_qid 归并后，missing 只剩真正缺的
    # 两道（Q12、Q21(2)），不再把同一道题按两个 unit_id 各报一次。
    missing_2024hd = set(s8_2024hd['evidence'].get('missing') or [])
    ok = (s8_2024hd['status'] == 'TODO' and missing_2024hd == {'BJ-2024-HD-QIZHONG-Q12', 'BJ-2024-HD-QIZHONG-Q21#2'}
          and not any(u.startswith('BJ-2025-HD-QIZHONG') for u in missing_2024hd | got_found))
    record('3e2 M1 回归：BJ-2024-HD-QIZHONG×bixiu3 第8步 missing 恰好是 {Q12, Q21(2)} 两道（孪生归并后），'
           '不含任何 BJ-2025-HD-QIZHONG-* 别名', ok, f'missing={sorted(missing_2024hd)}')

    # M4 回归：BJ-2026-HD-QIZHONG-Q22#2×bixiu3 归属 IN 但 admission=待裁决、各书清单_v4 判不收-无E1，
    # 不该出现在第5步“待落位”清单或第8步“应收”清单里。
    s5_2026hd = step_of(row_of(rep, 'BJ-2026-HD-QIZHONG', 'bixiu3'), 5)
    s8_2026hd = step_of(row_of(rep, 'BJ-2026-HD-QIZHONG', 'bixiu3'), 8)
    bad_qid = 'BJ-2026-HD-QIZHONG-Q22#2'
    in_s5 = bad_qid in (s5_2026hd['evidence'].get('to_place') or [])
    in_s8 = bad_qid in ((s8_2026hd['evidence'].get('missing') or []) + (s8_2026hd['evidence'].get('found') or []))
    record('3e3 M4 回归：BJ-2026-HD-QIZHONG-Q22#2 不出现在第5步待落位、第8步应收清单里（admission=待裁决，'
           '各书清单_v4=不收-无E1）', not in_s5 and not in_s8, f'in_s5={in_s5} in_s8={in_s8} '
           f's5_excluded={s5_2026hd["evidence"].get("excluded")}')

    # 现在真实跑 exam_register，让第2步从“未跑”变成“已跑出真实结论”
    er_dir = wd / '02_exam_register'
    for e in KNOWN_EXAMS:
        code_er, out_er, err_er, dt_er = run(EXAM_REGISTER, ['check', '--exam-id', e, '--profile',
                                              str(PROFILES['bixiu3']), '--report', str(er_dir / f'{e}.json')],
                                              timeout=120)
        record(f'3f exam_register 真实登记检查：{e}（intake_run 第2步要读的真实证据）',
               code_er in (0, 1), f'exit={code_er}', dt_er)

    code2, rep2, out2, err2, dt2 = status_report(manifest, SCRATCH / 'real_report_stage1.json', timeout=300)
    record('3g status 重跑（有真实登记结果）成功', code2 == 1 and rep2 is not None, f'exit={code2}', dt2)
    if rep2 is None:
        return
    # 已知事实④：前三张有届别/重复问题 → 第2步 BLOCKED；后两张 DONE
    expect_blocked = ['BJ-2023-HD-QIZHONG', 'BJ-2024-HD-QIZHONG', 'BJ-2024-CY-QIZHONG']
    expect_done = ['BJ-2026-CY-QIZHONG', 'BJ-2026-HD-QIZHONG']
    got_blocked = [e for e in expect_blocked if step_of(row_of(rep2, e, 'bixiu3'), 2)['status'] == 'BLOCKED']
    got_done = [e for e in expect_done if step_of(row_of(rep2, e, 'bixiu3'), 2)['status'] == 'DONE']
    record('3h 已知事实：BJ-2023/2024-HD-QIZHONG、BJ-2024-CY-QIZHONG 第2步 BLOCKED（届别/重复登记）',
           got_blocked == expect_blocked, str(got_blocked))
    record('3i 已知事实：BJ-2026-CY/HD-QIZHONG 第2步 DONE（登记检查通过）', got_done == expect_done, str(got_done))
    # BLOCKED 对每本非 bixiu2 书都一致（第2步与目标书无关，只与卷本身有关）
    consistent = all(step_of(row_of(rep2, e, b), 2)['status'] == 'BLOCKED'
                      for e in expect_blocked for b in ALL_BOOKS if b != 'bixiu2')
    record('3j 第2步状态与目标书无关：BLOCKED 的卷在全部7本书上都是 BLOCKED', consistent)

    # M2 回归：题库里唯一不在归属表的卷（BJ-2023-HD-QIMO）——新卷这个主场景——第8步不能报 DONE
    # （旧版“应收为空”判据在第4步未完成时也会误判 DONE）。
    wd_m2 = SCRATCH / '入书_m2'
    wd_m2.mkdir(parents=True, exist_ok=True)
    ir._mkdirs(wd_m2, ['bixiu3'])
    manifest_m2 = write_manifest(SCRATCH / 'manifest_m2.json', 'm2', [{'exam_id': 'BJ-2023-HD-QIMO'}],
                                 ['bixiu3'], {'bixiu3': str(PROFILES['bixiu3'])}, wd_m2)
    code_m2, rep_m2, _, err_m2, dt_m2 = status_report(manifest_m2, SCRATCH / 'report_m2.json', timeout=60)
    if rep_m2:
        row_m2 = row_of(rep_m2, 'BJ-2023-HD-QIMO', 'bixiu3')
        s4_m2, s8_m2 = step_of(row_m2, 4), step_of(row_m2, 8)
        ok = s4_m2['status'] != 'DONE' and s8_m2['status'] == 'NEEDS_MODEL'
        record('3k M2 回归：不在归属表的新卷（BJ-2023-HD-QIMO）第4步非DONE时，第8步报 NEEDS_MODEL（不是 DONE）',
               ok, f's4={s4_m2["status"]} s8={s8_m2["status"]} s8_reason={s8_m2["reason"][:60]}', dt_m2)
    else:
        record('3k M2 回归', False, f'status 调用失败 exit={code_m2} err={err_m2[:200]}')

    baseline_check('组3真实数据测试后')


# ---------------------------------------------------------------- 组4：沙盒推进（验收②）
def group4_sandbox():
    wd = SCRATCH / '入书_sandbox'
    wd.mkdir(parents=True, exist_ok=True)
    ir._mkdirs(wd)  # 预建 9 个子目录，姊妹工具的 --report/--out 写出需要父目录已存在
    exam_id, book, qid = 'BJ-2026-CY-QIZHONG', 'bixiu3', 'BJ-2026-CY-QIZHONG-Q9'
    manifest = write_manifest(SCRATCH / 'manifest_sandbox.json', 'sandbox', [{'exam_id': exam_id}],
                              [book], {book: str(PROFILES[book])}, wd)

    def snap(tag):
        code, rep, out, err, dt = status_report(manifest, SCRATCH / f'sandbox_{tag}.json', timeout=120)
        row = row_of(rep, exam_id, book) if rep else None
        return code, row, dt

    # 阶段0：空 workdir
    code, row, dt = snap('s0')
    s = {i: step_of(row, i)['status'] for i in range(1, 10)} if row else {}
    ok = (row and s[1] == 'DONE' and s[2] == 'TODO' and s[3] == 'DONE' and s[4] == 'DONE'
          and s[5] == 'TODO' and s[6] == 'NEEDS_MODEL' and s[7] == 'NEEDS_MODEL' and s[8] == 'TODO'
          and row['next_action']['step'] == 2)
    record('4a 阶段0（空 workdir）：1/3/4=DONE，2/5=TODO，6/7=NEEDS_MODEL，8=TODO，next=[2]', ok, str(s), dt)

    # 阶段1：真实跑 exam_register → 第2步应变 DONE（这张卷本身没有届别/重复问题）
    er_path = wd / '02_exam_register' / f'{exam_id}.json'
    code_er, _, err_er, dt_er = run(EXAM_REGISTER, ['check', '--exam-id', exam_id, '--profile',
                                     str(PROFILES[book]), '--report', str(er_path)], timeout=60)
    record('4b 真实跑 exam_register（阶段1输入）', code_er in (0, 1), f'exit={code_er}', dt_er)
    code, row, dt = snap('s1')
    s = {i: step_of(row, i)['status'] for i in range(1, 10)} if row else {}
    ok = row and s[2] == 'DONE' and row['next_action']['step'] == 5
    record('4c 阶段1：登记检查报告出现后，第2步 TODO→DONE，next 前进到 [5]（3/4 本就已 DONE）',
           ok, str(s) + f' next={row["next_action"] if row else None}', dt)

    # 阶段2：真实跑 placement_suggest → 第5步应变 DONE
    ps_path = wd / '05_placement' / book / f'{exam_id}.json'
    ps_path.parent.mkdir(parents=True, exist_ok=True)
    code_ps, out_ps, err_ps, dt_ps = run(PLACEMENT_SUGGEST, ['--docx', str(BOOK3), '--profile', str(PROFILES[book]),
                                          '--key', qid, '--top-k', '3', '--report', str(ps_path)], timeout=60)
    record('4d 真实跑 placement_suggest（阶段2输入）', code_ps in (0, 1), f'exit={code_ps}', dt_ps)
    code, row, dt = snap('s2')
    s = {i: step_of(row, i)['status'] for i in range(1, 10)} if row else {}
    ok = row and s[5] == 'DONE' and row['next_action']['step'] == 6
    record('4e 阶段2：placement 报告出现后，第5步 TODO→DONE，next 前进到 [6]', ok, str(s), dt)

    # 阶段3：放置一份真的能过 block_insert check 的 baodian_insert_v1 改动单（M7：旧版用
    # anchor={'template_block':...}、content=[] 的合成单子，被 block_insert check 以“出现未知字段
    # ['template_block']”拒收，第6步却判它 DONE——这里换成真实 schema，anchor 与 template_block 是
    # 两个平级字段，content 取真实题库文字（BJ-2026-CY-QIZHONG-Q9 原题保真转写，见题库 questions/
    # BJ-2026-CY-QIZHONG/BJ-2026-CY-QIZHONG-Q9.md），后面 4j 会真的把它 apply 到一份书稿副本上验证）。
    parent_sha = ir.dl.sha256_file(BOOK3)
    Q9_INSERT_UNIT = {
        'schema': 'baodian_insert_v1', 'book': book, 'parent_docx_sha256': parent_sha,
        'approved_by': 'claude-cloud:run_tests_intake_run', 'approval_ref':
            'intake_run.py 沙盒机制测试：验证第6/8步（非正式插入，未经教学审定，只写沙盒副本）',
        'inserts': [{
            'id': 'I001',
            'anchor': {'after_block': {'title_contains': '选择例题 1　2026朝阳一模第9题'}},
            'template_block': {'title_contains': '选择例题 1　2026朝阳一模第9题'},
            'title': '选择例题 92　2026朝阳期中第9题',
            'source_zone': 'restore',
            'reason': '题目材料逐字取自题库 BJ-2026-CY-QIZHONG-Q9 原题保真转写，沙盒机制测试用，非正式插入',
            'content': [
                {'role': 'source', 'text': '9．推动民族工作需要依靠物质力量，通过高质量发展实现共同富裕；'
                 '同样也需要依靠精神力量，增强文化认同，着力构筑中华民族共有精神家园，不断铸牢中华民族共同'
                 '体意识。下列说法正确的是（　　）'},
                {'role': 'source', 'text': '①各民族血脉相融，是中华民族共同体形成和发展的根本动力'},
                {'role': 'source', 'text': '②各民族文化相通，是中华民族多元一体文明格局的文化基因'},
                {'role': 'source', 'text': '③各民族经济相依，是中华民族构建起统一经济体的强大力量'},
                {'role': 'source', 'text': '④各民族情感相亲，是中华民族促进团结进步的强大物质基础'},
                {'role': 'source', 'text': 'A．①②　　B．①④'},
                {'role': 'source', 'text': 'C．②③　　D．③④'},
                {'role': 'teaching', 'text': '【答案】 C'},
                {'role': 'teaching', 'text': '【分析过程】 沙盒机制测试占位文字，用于验证 intake_run 第8步的'
                 '插入后状态流转，非正式教学内容，未经审定。'},
            ],
        }],
    }
    insert_path = wd / '06_insert' / book / f'{exam_id}.json'
    insert_path.parent.mkdir(parents=True, exist_ok=True)
    insert_path.write_text(json.dumps(Q9_INSERT_UNIT, ensure_ascii=False, indent=1), encoding='utf-8')
    code, row, dt = snap('s3')
    s = {i: step_of(row, i)['status'] for i in range(1, 10)} if row else {}
    ok = row and s[6] == 'DONE' and row['next_action']['step'] == 7
    record('4f 阶段3：approved_by 非空的 baodian_insert_v1 改动单出现后，第6步 NEEDS_MODEL→DONE，next 前进到 [7]',
           ok, str(s), dt)
    # M7：这份插入单真的能过 block_insert check（旧版合成单子会被拒收，第6步却仍判 DONE——见上面注释）。
    # block_insert.py check 退出码 0=无待处理、1=有合法插入计划待插入（同共同约定第6条“1=发现待处理”，
    # 不是失败）；2/3 才是真的被拒收。
    code_bi_chk, out_bi_chk, err_bi_chk, dt_bi_chk = run(BLOCK_INSERT, [
        'check', '--docx', str(BOOK3), '--insert', str(insert_path), '--profile', str(PROFILES[book])], timeout=60)
    record('4f2 M7 回归：第6步落地的插入单真的能通过 block_insert.py check（不是会被拒收的合成单子）',
           code_bi_chk in (0, 1), f'exit={code_bi_chk} err={err_bi_chk[:200]} out={out_bi_chk[:200]}', dt_bi_chk)

    # 阶段4：真实跑 check_drill_admission（既有 SK 工具，本就是“题肢准入”产物的验证脚本）→ 第7步应变 DONE
    drill_dir = wd / '07_drill' / book
    drill_dir.mkdir(parents=True, exist_ok=True)
    cand = [{'id': f'{qid}-A', 'text': '1、人大代表由本级人民代表大会选举产生',
             'source': qid}]
    dec = {'records': [{'old_id': f'{qid}-A', 'statement': '人大代表由本级人民代表大会选举产生',
                        'source': qid, 'action': 'retain', 'reason': '沙盒合成用例，仅测试 intake_run 读法'}]}
    (drill_dir / f'{exam_id}_candidates.json').write_text(json.dumps(cand, ensure_ascii=False), encoding='utf-8')
    (drill_dir / f'{exam_id}_decisions.json').write_text(json.dumps(dec, ensure_ascii=False), encoding='utf-8')
    code_da, out_da, err_da, dt_da = run(CHECK_DRILL_ADMISSION, [
        '--candidates', str(drill_dir / f'{exam_id}_candidates.json'),
        '--decisions', str(drill_dir / f'{exam_id}_decisions.json'),
        '--report', str(drill_dir / f'{exam_id}.json')], timeout=60)
    record('4g 真实跑 check_drill_admission（阶段4输入，既有 SK 工具）', code_da == 0, f'exit={code_da} err={err_da[:150]}', dt_da)
    code, row, dt = snap('s4')
    s = {i: step_of(row, i)['status'] for i in range(1, 10)} if row else {}
    ok = row and s[7] == 'DONE' and row['next_action']['step'] == 8
    record('4h 阶段4：check_drill_admission status=pass 报告出现后，第7步 NEEDS_MODEL→DONE，next 前进到 [8]'
           '（第8步保持 TODO——Q9 确实尚未在书中，不假装完成，见 4i）', ok, str(s), dt)
    ok8 = row and s[8] == 'TODO' and qid in (step_of(row, 8)['evidence'].get('missing') or [])
    record('4i 第8步如实保持 TODO：Q9 真的不在 bixiu3 当前稿（block_index 查不到），未被前面几步的完成误判为 DONE',
           ok8, str(step_of(row, 8)['evidence']) if row else '')

    # 阶段5（M7 核心）：真实 block_insert apply——不动 BOOK3 本身，只 apply 到一份书稿副本上，再让
    # intake_run 指向这份副本重跑一次 status，验证第8步真的能 TODO→DONE（不是只测函数、不测真流程）。
    insert_dir = SCRATCH / 'block_insert_apply'
    insert_dir.mkdir(parents=True, exist_ok=True)
    book_copy_dir = insert_dir / 'book_copy'
    book_copy_dir.mkdir(parents=True, exist_ok=True)
    parent_copy = book_copy_dir / BOOK3.name
    shutil.copyfile(BOOK3, parent_copy)
    out_docx = insert_dir / 'out.docx'
    out_docx.unlink(missing_ok=True)
    code_bi_apply, out_bi_apply, err_bi_apply, dt_bi_apply = run(BLOCK_INSERT, [
        'apply', '--docx', str(parent_copy), '--insert', str(insert_path), '--out', str(out_docx),
        '--profile', str(PROFILES[book])], timeout=90)
    record('4i2 M7 回归：真实跑 block_insert.py apply（写到书稿副本，不碰 BOOK3 本身）',
           code_bi_apply == 0 and out_docx.is_file(), f'exit={code_bi_apply} err={err_bi_apply[:200]}', dt_bi_apply)

    # 把 apply 出来的副本放进 book_copy_dir（覆盖掉刚才拷贝的父稿），造一份“central_state 缺失、
    # workspace 下只有一份 .docx”的沙盒 profile，让 current_docx_for_book() 的兜底分支（单一 .docx）
    # 定位到这份副本，而不是真的书稿——不改 bixiu3.json 本身，只在内存/scratch 里派生一份。
    if out_docx.is_file():
        parent_copy.unlink()
        shutil.move(str(out_docx), str(parent_copy))
    sandbox_prof = json.loads(PROFILES[book].read_text(encoding='utf-8'))
    sandbox_prof.get('paths', {}).pop('central_state', None)
    sandbox_prof['paths']['workspace'] = str(book_copy_dir)
    sandbox_prof_path = insert_dir / 'bixiu3_sandbox.json'
    sandbox_prof_path.write_text(json.dumps(sandbox_prof, ensure_ascii=False, indent=1), encoding='utf-8')
    manifest_ins = write_manifest(insert_dir / 'manifest.json', 'sandbox_inserted', [{'exam_id': exam_id}],
                                  [book], {book: str(sandbox_prof_path)}, wd)
    code_ins, rep_ins, out_ins, err_ins, dt_ins = status_report(manifest_ins, insert_dir / 'report.json', timeout=120)
    row_ins = row_of(rep_ins, exam_id, book) if rep_ins else None
    s8_ins = step_of(row_ins, 8) if row_ins else None
    ok = s8_ins and s8_ins['status'] == 'DONE' and qid in (s8_ins['evidence'].get('found') or [])
    record('4i3 M7 回归：指向 apply 后的书稿副本重跑 status，第8步 TODO→DONE（Q9 真的被 block_index 认出）',
           ok, str(s8_ins) if s8_ins else f'exit={code_ins} err={err_ins[:200]}', dt_ins)
    # 反证：apply 前最后一次对真实 BOOK3 的快照（阶段4的 row，此时 BOOK3 从未被动过）第8步仍是
    # TODO——证明上面的 DONE 确实来自副本改动，不是巧合或缓存。
    ok = row and step_of(row, 8)['status'] == 'TODO'
    record('4i4 对照：apply 之前对真实 BOOK3 的快照第8步是 TODO，证明 4i3 的 DONE 确实来自副本改动',
           ok, str(step_of(row, 8)) if row else '')

    # 阶段6（额外）：真实跑 layout_prepare + batch_health，看第9步证据链的部分推进（云端最高只到 NEEDS_LOCAL）
    layout_path = wd / '09_layout' / f'{book}.json'
    code_lp, _, err_lp, dt_lp = run(LAYOUT_PREPARE, ['check', '--docx', str(BOOK3), '--profile',
                                     str(PROFILES[book]), '--report', str(layout_path)], timeout=90)
    record('4o 真实跑 layout_prepare check（第9步部分证据）', code_lp in (0, 1), f'exit={code_lp}', dt_lp)
    health_path = wd / '09_health' / f'{book}.json'
    code_bh, out_bh, err_bh, dt_bh = run(BATCH_HEALTH, ['--docx', str(BOOK3), '--profile', str(PROFILES[book]),
                                          '--out', str(health_path), '--quiet'], timeout=90)
    # 退出1＝书稿本有既存 FAIL（与本工具插入与否无关，intake_run 第9步只看报告文件是否已产出，
    # 不复核 FAIL 明细——见 known_limits），退出0＝体检全绿；两者都说明 batch_health 真的跑完了。
    record('4p 真实跑 batch_health（第9步部分证据）', code_bh in (0, 1) and health_path.is_file(),
           f'exit={code_bh}', dt_bh)
    code, row, dt = snap('s6')
    s9 = step_of(row, 9) if row else None
    ok = s9 and s9['status'] == 'TODO' and 'publish_review' in (s9['next_command'] or '')
    record('4q 阶段6：layout(0待改)+health 报告都出现后，第9步仍 TODO，下一条命令指向 publish_review dry-run'
           '（尚缺 publish 预检报告）——云端从不把第9步报 DONE，最多到 NEEDS_LOCAL（见组3/组5其它证据）',
           ok, str(s9) if s9 else '', dt)

    # M5：check_step9 的 --local-final 分支——不真的跑 publish_review --apply（风险太大、也不在本工具
    # 职责内；publish_review --apply 会真的写审阅入口/中央状态，即便指向候选目录也不该在测试里触发），
    # 改用它真实报告的字段形状（'mode'/'gates_pass'/'gates'，见 publish_review.py 源码）手写三份
    # 合成报告，直接单测 check_step9 的判定，不经完整子进程链路。先补一份 dry-run 形状的 09_publish
    # 报告，让 check_step9 走到“证据齐全”这一步（layout/health 已在阶段6产出）。
    prof9 = ir.load_book_profile(book, str(PROFILES[book]))
    docx9, err9 = ir.current_docx_for_book(prof9)
    publish_rp = wd / '09_publish' / f'{book}.json'
    publish_rp.write_text(json.dumps({'mode': 'dry-run', 'gates_pass': True, 'gates': []}), encoding='utf-8')
    s9_cloud = ir.check_step9(book, prof9, docx9, err9, wd, local_final=False)
    ok = s9_cloud['status'] == 'NEEDS_LOCAL'
    record('4r m5 回归：不给 --local-final（云端默认）时，第9步证据齐全也最高只到 NEEDS_LOCAL', ok, s9_cloud['status'])
    s9_lf_dry = ir.check_step9(book, prof9, docx9, err9, wd, local_final=True)
    record('4s m5 回归：--local-final 但 publish 报告仍是 dry-run（未 --apply）→ 仍 NEEDS_LOCAL，不报 DONE',
           s9_lf_dry['status'] == 'NEEDS_LOCAL', s9_lf_dry['status'])
    publish_rp.write_text(json.dumps({'mode': 'apply', 'gates_pass': False,
                                      'gates': [{'id': 'write_targets', 'level': 'FAIL', 'message': 'x'}]}),
                          encoding='utf-8')
    s9_lf_fail = ir.check_step9(book, prof9, docx9, err9, wd, local_final=True)
    record('4t m5 回归：--local-final 且已 --apply 但 gates_pass=False → 仍 NEEDS_LOCAL，不报 DONE',
           s9_lf_fail['status'] == 'NEEDS_LOCAL', s9_lf_fail['status'])
    publish_rp.write_text(json.dumps({'mode': 'apply', 'gates_pass': True, 'gates': []}), encoding='utf-8')
    s9_lf_ok = ir.check_step9(book, prof9, docx9, err9, wd, local_final=True)
    record('4u m5 回归：--local-final 且 --apply 成功、gates_pass=True → 报 DONE（第9步终于能到 DONE）',
           s9_lf_ok['status'] == 'DONE', s9_lf_ok['status'])

    baseline_check('组4沙盒测试后')


# ---------------------------------------------------------------- 组5：负例（受保护目录/写权）
def group5_negative():
    manifest = write_manifest(SCRATCH / 'manifest_neg.json', 'neg', [{'exam_id': 'BJ-2026-HD-QIZHONG'}],
                              ['bixiu3'], {'bixiu3': str(PROFILES['bixiu3'])}, SCRATCH / '入书_neg')
    (SCRATCH / '入书_neg').mkdir(parents=True, exist_ok=True)

    bad_json = SCRATCH / 'bad.json'
    bad_json.write_text('{not valid json', encoding='utf-8')
    code, _, _, err, _ = status_report(bad_json, SCRATCH / 'x1.json')
    record('5a 清单不是合法 JSON → 退出2', code == 2, f'exit={code}')

    unknown_book = write_manifest(SCRATCH / 'manifest_unknown_book.json', 'neg', [{'exam_id': 'X'}],
                                  ['not_a_real_book'], {'not_a_real_book': 'x'}, SCRATCH / '入书_neg2')
    code, _, _, err, _ = status_report(unknown_book, SCRATCH / 'x2.json')
    record('5b 书名未知 → 退出2', code == 2, f'exit={code} err={err.strip()[:150]}')

    missing_profile = write_manifest(SCRATCH / 'manifest_missing_profile.json', 'neg',
                                     [{'exam_id': 'X'}], ['bixiu3'],
                                     {'bixiu3': str(SCRATCH / 'no_such_profile.json')}, SCRATCH / '入书_neg3')
    code, _, _, err, _ = status_report(missing_profile, SCRATCH / 'x3.json')
    record('5c 配置文件找不到 → 退出2', code == 2, f'exit={code} err={err.strip()[:150]}')

    protected_report = REPO_ROOT / '后勤管理' / 'should_not_write_intake_run_test.json'
    code, out, err, dt = run(TOOL, ['status', '--manifest', str(manifest), '--report', str(protected_report), '--quiet'])
    ok = code == 3 and not protected_report.exists()
    record('5d --report 落受保护目录 → 退出3，且未写出', ok, f'exit={code} exists={protected_report.exists()}')

    protected_md = REPO_ROOT / '00_必修三最新审查稿' / 'should_not_write.md'
    code, out, err, dt = run(TOOL, ['status', '--manifest', str(manifest), '--md', str(protected_md), '--quiet'])
    ok = code == 3 and not protected_md.exists()
    record('5e --md 落受保护目录（审阅入口） → 退出3，且未写出', ok, f'exit={code} exists={protected_md.exists()}')

    # m3 回归：status 要反复重跑——同一个 --report 路径第二次也能写（覆盖自己以前的报告），不是
    # 一律“目标已存在，不覆盖”。
    rerun_report = SCRATCH / 'm3_rerun_report.json'
    rerun_report.unlink(missing_ok=True)
    code1, _, _, err1, _ = status_report(manifest, rerun_report)
    code2, rep2, _, err2, _ = status_report(manifest, rerun_report)
    record('5f m3 回归：同一个 --report 路径重跑两次都能写（覆盖自己旧报告），不是退出3',
           code1 in (0, 1) and code2 in (0, 1) and rep2 is not None,
           f'run1_exit={code1} run2_exit={code2} err2={err2.strip()[:150]}')

    # m3 回归：--md 被拒时 --report 不能已经落盘（原子性）——两个输出先都校验通过再落盘。
    report_atomic = SCRATCH / 'm3_atomic_report.json'
    report_atomic.unlink(missing_ok=True)
    protected_md2 = REPO_ROOT / '后勤管理' / 'should_not_write_atomic.md'
    code_a, out_a, err_a, dt_a = run(TOOL, ['status', '--manifest', str(manifest), '--report', str(report_atomic),
                                            '--md', str(protected_md2), '--quiet'])
    ok = code_a == 3 and not report_atomic.exists() and not protected_md2.exists()
    record('5g m3 回归：--md 落受保护目录被拒时，--report 不会先落盘留半成品（约定4原子性）',
           ok, f'exit={code_a} report_exists={report_atomic.exists()} md_exists={protected_md2.exists()}')

    # m3 回归：目标路径已存在但不是本工具的报告（别的合法 JSON）→ 拒绝覆盖，退出3，原内容不变。
    foreign_report = SCRATCH / 'm3_foreign.json'
    foreign_report.write_text('{"not_intake_run": true, "keep_me": 1}', encoding='utf-8')
    code_f, out_f, err_f, dt_f = run(TOOL, ['status', '--manifest', str(manifest), '--report', str(foreign_report), '--quiet'])
    kept = json.loads(foreign_report.read_text(encoding='utf-8')).get('keep_me') == 1
    record('5h m3 回归：--report 目标已存在但不是 intake_run 自己的报告 → 拒绝覆盖，退出3，原内容不变',
           code_f == 3 and kept, f'exit={code_f} kept={kept}')


# ---------------------------------------------------------------- 组6：下一条命令的可复制性（argparse 能接受）
def _parses_ok(cmd, timeout=30):
    """真实起子进程跑这条命令（不加 --help，就是 intake_run 给出的那条），只要求它不是 argparse
    usage 错误（那才说明命令行本身参数不全/类型不对）；跑到域内报错（文件不存在、中止校验等）
    都算“argparse 接受了”，这正是共同约定“解析参数而不真正执行重活”里，重活失败也算过关的意思。"""
    import shlex
    parts = shlex.split(cmd)
    if parts[0] != 'python3':
        return False, None, f'不是以 python3 开头：{parts[:2]}', 0.0
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, '-B'] + parts[1:], capture_output=True, text=True, timeout=timeout)
        dt = time.time() - t0
        usage_err = (p.returncode == 2 and 'usage:' in p.stderr and ': error:' in p.stderr)
        return (not usage_err), p.returncode, (p.stderr or '')[:300], dt
    except subprocess.TimeoutExpired:
        return True, None, '(超时但已过 argparse 解析阶段——heavy 命令跑太久，不算解析失败)', timeout


def _run_cmd_real(cmd, timeout=90):
    """真的执行 intake_run 给出的那条命令（不是 --help/只解析），用来验证 M6：workdir 布局、健康检查
    输出路径这些“argparse 能接受，实跑却因目录不存在/写权被拒”的问题不会再发生。"""
    import shlex
    parts = shlex.split(cmd)
    t0 = time.time()
    p = subprocess.run([sys.executable, '-B'] + parts[1:], capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr, time.time() - t0


def group6_next_command_parses():
    # M6：不再自己手搭 workdir（ir._mkdirs(wd) 跳过 init 这一步会把 init 自身的目录布局 bug 藏起
    # 来）——照真实端到端流程先用 init 建 workdir+清单骨架，再补 profile 路径。
    out = SCRATCH / 'init_cmdcheck' / 'manifest.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    workdir = SCRATCH / 'init_cmdcheck' / '入书_cmdcheck'
    code_i, sout_i, serr_i, dt_i = run(TOOL, ['init', '--out', str(out), '--batch', 'cmdcheck',
                                              '--exam-id', 'BJ-2026-HD-QIZHONG', '--book', 'bixiu3',
                                              '--workdir', str(workdir)])
    record('6-init M6 回归：组6改用真实 init 搭 workdir（不是测试自己手建目录，避免把 init 的 bug 藏起来）',
           code_i == 0, f'exit={code_i} err={serr_i[:200]}', dt_i)
    if code_i != 0:
        record('6x init 失败，跳过第6组', False, f'exit={code_i}')
        return
    manifest = out
    m = json.loads(manifest.read_text(encoding='utf-8'))
    m['profiles']['bixiu3'] = str(PROFILES['bixiu3'])
    manifest.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding='utf-8')

    code, rep, out_s, err_s, dt = status_report(manifest, SCRATCH / 'cmdcheck_report.json', timeout=120)
    if rep is None:
        record('6x 前置 status 调用失败，跳过第6组', False, f'exit={code} err={err_s[:200]}')
        return
    row = row_of(rep, 'BJ-2026-HD-QIZHONG', 'bixiu3')
    # M6：第2/5/8步（exam_register/placement_suggest/block_insert check）实跑够快、也是本轮改动最
    # 直接触及的三步，真的执行一遍；第9步 batch_health 的命令不真的跑（体检本身慢），改直接核它的
    # --out 是否过 batch_health 自己的输出守卫；第1/3/6/7步（source_intake/bank_compile/qpack/
    # check_drill_admission）依赖题库原件、conversion_manifest.json 或人工候选/裁决文件等本测试
    # 不具备的外部输入，仍只做“能被 argparse 接受”的解析层核对（同旧版组6）。
    REAL_RUN_STEPS = {2, 5, 8}
    checked_steps = set()
    for s in row['steps']:
        if not s['next_command'] or s['step'] in checked_steps:
            continue
        checked_steps.add(s['step'])
        cmd = s['next_command'].split('；')[0].split(' / ')[0].split('等（')[0].strip()
        if not cmd.startswith('python3'):
            continue  # “回本地：…”这类纯提示，不是命令行，跳过
        if s['step'] == 9 and 'batch_health.py' in cmd:
            import shlex
            parts = shlex.split(cmd)
            out_path = Path(parts[parts.index('--out') + 1])
            prof9 = ir.load_book_profile('bixiu3', str(PROFILES['bixiu3']))
            reason = bh_module._unsafe_out(out_path, [], prof9)
            record(f'6-step9-health M6 回归：batch_health --out 路径（{out_path}）过它自己的输出守卫',
                   reason is None, f'reason={reason}')
            continue
        if s['step'] in REAL_RUN_STEPS:
            rc, rout, rerr, rdt = _run_cmd_real(cmd)
            bad = rc == 3 or '拒绝写出' in (rerr or '') or '输出目录不存在' in (rerr or '')
            record(f'6-step{s["step"]} M6 回归：照抄命令实跑，不因“拒绝写出/目录不存在”失败：{cmd[:100]}...',
                   not bad, f'rc={rc} err={(rerr or "")[:200]}', rdt)
        else:
            ok, rc, detail, cdt = _parses_ok(cmd)
            record(f'6-step{s["step"]} 下一条命令能被目标脚本 argparse 接受：{cmd[:90]}...', ok,
                   f'rc={rc} {detail}', cdt)
    if not (8 in checked_steps):
        record('6-step8-placeholder m6 回归：第8步命令不该含 <书册配置> 占位符', True, '第8步本次未出现（已 DONE/其它）')
    else:
        cmd8 = next(s['next_command'] for s in row['steps'] if s['step'] == 8 and s['next_command'])
        record('6-step8-placeholder M6 回归：第8步命令带真实 profile 路径，不含 <书册配置> 占位符',
               '<书册配置>' not in cmd8, cmd8[:150])

    # 上面这一轮第9步的下一条命令是 layout_prepare（还没跑），第8组的 6-step9-health 分支没触发到——
    # 真的跑一次 layout_prepare，把第9步推进到 batch_health 这一步，再核一次它的 --out 路径。
    workdir_cc = workdir
    layout_rp_cc = workdir_cc / '09_layout' / 'bixiu3.json'
    if not layout_rp_cc.is_file():
        code_lp2, _, err_lp2, dt_lp2 = run(LAYOUT_PREPARE, ['check', '--docx', str(BOOK3), '--profile',
                                            str(PROFILES['bixiu3']), '--report', str(layout_rp_cc)], timeout=90)
        record('6-推进 M6 回归：真的跑 layout_prepare，把第9步推进到 batch_health 这一步', code_lp2 in (0, 1),
               f'exit={code_lp2}', dt_lp2)
    code9, rep9, _, err9, dt9 = status_report(manifest, SCRATCH / 'cmdcheck_report2.json', timeout=60)
    s9row = row_of(rep9, 'BJ-2026-HD-QIZHONG', 'bixiu3') if rep9 else None
    s9_9 = step_of(s9row, 9) if s9row else None
    if s9_9 and s9_9['next_command'] and 'batch_health.py' in s9_9['next_command']:
        import shlex
        parts9 = shlex.split(s9_9['next_command'])
        out_path9 = Path(parts9[parts9.index('--out') + 1])
        prof9b = ir.load_book_profile('bixiu3', str(PROFILES['bixiu3']))
        reason9 = bh_module._unsafe_out(out_path9, [], prof9b)
        record(f'6-step9-health M6 回归：batch_health --out 路径（{out_path9}）过它自己的输出守卫',
               reason9 is None, f'reason={reason9}')
    else:
        record('6-step9-health M6 回归', False, f'第9步没能推进到 batch_health：{s9_9}')


def main():
    setup()
    t0 = time.time()
    baseline_check('全部测试前')
    group1_unit()
    group2_init()
    group3_real_matrix()
    group4_sandbox()
    group5_negative()
    group6_next_command_parses()
    baseline_check('全部测试后')
    dt = time.time() - t0
    total = len(results)
    failed = [r for r in results if not r['ok']]
    print(f'\n合计 {total} 条，失败 {len(failed)} 条，用时 {dt:.1f}s')
    (BUILD_OUT / 'test_results.json').write_text(
        json.dumps({'total': total, 'failed': len(failed), 'seconds': round(dt, 1), 'results': results},
                    ensure_ascii=False, indent=1), encoding='utf-8')
    return len(failed)


if __name__ == '__main__':
    sys.exit(main())
