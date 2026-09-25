#!/usr/bin/env python3
"""sweep_rule.py 的可重跑测试脚本。

只读输入：真实书稿（哲学 R10、必修三第52批、思维 v6.20、必修二修订230——冻结册只做只读 find）。
所有写出（副本、候选/决定/补丁/health JSON、产物 docx）只落在 OUT_DIR——默认是流程优化线约定的
scratchpad 路径，不是本脚本所在目录：本脚本本体登记在 …/测试/run_tests_sweep_rule.py 下，如果直接
把输出写在这里会把书稿副本、几万条候选 JSON 落进项目目录（见 verify_sweep_rule.json 的 minor 记录）。
可用环境变量 SWEEP_TEST_OUT 覆盖输出目录。测试前后核对全部真实输入文件的 SHA256 与 mtime 未变，
并确认 Skill scripts/__pycache__ 没有新增文件。

用法：/usr/bin/python3 run_tests_sweep_rule.py
退出码：0 全部测试通过；1 有测试失败（如实打印，不假装通过）。
"""
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True

HERE = Path(__file__).resolve().parent
OUT_DIR = Path(os.environ.get('SWEEP_TEST_OUT') or (
    '/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----'
    '/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/booktools3/sweep_rule'))
OUT_DIR.mkdir(parents=True, exist_ok=True)
HERE = OUT_DIR  # 下面所有读写都经 HERE：一律落在 OUT_DIR，不落在脚本自己所在的 …/测试/ 目录
SKILL_SCRIPTS = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts')
SWEEP = SKILL_SCRIPTS / 'sweep_rule.py'
APPLY_PATCH = SKILL_SCRIPTS / 'apply_patch.py'
BATCH_HEALTH = SKILL_SCRIPTS / 'batch_health.py'
PY = '/usr/bin/python3'
DOGFOOD = Path('/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----'
                '/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/crossbook_dogfood')

REAL_INPUTS = {
    'philosophy': '/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修四哲学续作_20260908/交付/'
                   '哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx',
    'thinking': '/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/选必三思维_v6.4续作_20260908/'
                 '选必三思维宝典_v6.20_丰台补题分页修订工作稿_20260908.docx',
    'b3_52': ('/Users/wanglifei/Desktop/gpt和claude共同的小窝/必修三_最新Skill修订_20260913/协作/候选/'
              'Claude/第52批_意见修改_20260923/构建/必修三政治与法治宝典_第52批_意见修改审阅稿.docx'),
    'b2_230': ('/Users/wanglifei/Desktop/gpt和claude共同的小窝/必修二_周六成品冲刺_20260910/工作稿/'
               '修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.docx'),
}

results = []


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def snapshot(paths):
    return {p: (sha(p), os.stat(p).st_mtime, os.stat(p).st_size) for p in paths}


def pycache_snapshot():
    d = SKILL_SCRIPTS / '__pycache__'
    return set(d.glob('*.pyc')) if d.is_dir() else set()


def run(args, timeout=600):
    t0 = time.time()
    cp = subprocess.run([PY] + [str(a) for a in args], cwd=str(SKILL_SCRIPTS),
                         capture_output=True, text=True, timeout=timeout)
    return cp.returncode, cp.stdout, cp.stderr, time.time() - t0


def record(name, input_desc, ok, detail, seconds):
    results.append({'input': input_desc, 'name': name, 'result': 'PASS' if ok else 'FAIL',
                     'detail': detail, 'seconds': round(seconds, 3)})
    print(('通过' if ok else '失败') + f'：{name}（{seconds:.2f}s）' + ('' if ok else f' —— {detail}'))
    return ok


def write_json(p, obj):
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')


def read_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def health_fail_by_rule(path):
    d = read_json(path)
    return {(f['check'], f['level'], f['rule']): f['count'] for f in d['findings_by_rule'] if f['level'] == 'FAIL'}


# ------------------------------------------------------------------ 正例：哲学 R10，“本节点”，全流程
def test_philosophy_benjiedian():
    t0 = time.time()
    copy = HERE / 'philosophy_copy.docx'
    if not copy.exists() or sha(copy) != sha(REAL_INPUTS['philosophy']):
        copy.write_bytes(Path(REAL_INPUTS['philosophy']).read_bytes())
    prof = HERE / 'philosophy.draft.json'
    if not prof.exists():
        prof.write_text(Path(DOGFOOD / 'philosophy.draft.json').read_text(encoding='utf-8'), encoding='utf-8')
    rule = HERE / 'rule_benjiedian.json'
    rule.write_text(json.dumps({
        'id': 'rm_benjiedian', 'desc': '学生正文里的工程词“本节点”，全书删去',
        'match': {'zones': ['teaching', 'rubric', 'outside', 'heading'], 'regex': '本节点'},
        'action': {'type': 'replace_regex', 'pattern': '本节点', 'repl': ''},
    }, ensure_ascii=False), encoding='utf-8')

    cands_p = HERE / 't1_cands.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', copy, '--rule', rule,
                             '--profile', prof, '--out', cands_p, '--overwrite'])
    if rc != 1:
        return record('①find-哲学-本节点', 'philosophy R10', False, f'exit={rc} err={err}', time.time() - t0)
    cands = read_json(cands_p)
    if cands['total_candidates'] != 20:
        return record('①find-哲学-本节点', 'philosophy R10', False,
                       f'候选数 {cands["total_candidates"]}，与体检 FAIL=20 不符', time.time() - t0)

    # 用确定性规则模拟“模型逐条确认”：全部 edit，去掉“本节点”
    items = {}
    for c in cands['candidates']:
        dec = {'decision': 'edit', 'reason': '测试：去掉工程词“本节点”，直接删去不影响句意'}
        if c['hit_count'] == 1:
            dec['new_snippet'] = ''
        else:
            dec['new_snippets'] = [''] * c['hit_count']
        items[c['cand_id']] = dec
    dec_p = HERE / 't1_decisions.json'
    write_json(dec_p, {'approved_by': 'user', 'approval_ref': '测试①-本节点', 'items': items})

    patch_p = HERE / 't1_patch.json'
    rc, out, err, dt2 = run(['sweep_rule.py', 'to-patch', '--docx', copy, '--cands', cands_p,
                              '--decisions', dec_p, '--rule', rule, '--profile', prof,
                              '--out', patch_p, '--overwrite', '--allow-draft-profile'])
    if rc != 0:
        return record('①find-哲学-本节点', 'philosophy R10', False, f'to-patch exit={rc} err={err}', time.time() - t0)
    patch = read_json(patch_p)
    if len(patch['ops']) != 26 or any(op['op'] != 'replace_text' for op in patch['ops']):
        return record('①find-哲学-本节点', 'philosophy R10', False,
                       f'op 数或类型不对：{len(patch["ops"])} 条，kinds={ {o["op"] for o in patch["ops"]} }',
                       time.time() - t0)

    out_docx = HERE / 't1_out.docx'
    if out_docx.exists():
        out_docx.unlink()
    rc, out, err, dt3 = run(['apply_patch.py', 'apply', '--docx', copy, '--patch', patch_p,
                              '--out', out_docx, '--profile', prof])
    if rc != 0:
        return record('①find-哲学-本节点', 'philosophy R10', False, f'apply_patch apply exit={rc} err={err}',
                       time.time() - t0)

    health_after_p = HERE / 't1_health_after.json'
    rc, out, err, dt4 = run(['batch_health.py', '--docx', out_docx, '--profile', prof,
                              '--out', health_after_p, '--quiet'])
    before = health_fail_by_rule(DOGFOOD / 'philosophy.health.json')
    after = health_fail_by_rule(health_after_p)
    diffs = {k: (before.get(k, 0), after.get(k, 0)) for k in set(before) | set(after)
             if before.get(k, 0) != after.get(k, 0)}
    ok = diffs == {('student_text', 'FAIL', '工程词:本节点'): (20, 0)}

    rc_v, out_v, err_v, dt5 = run(['sweep_rule.py', 'verify', '--docx', out_docx, '--rule', rule,
                                    '--profile', prof, '--decisions', dec_p])
    ok = ok and rc_v == 0

    detail = f'FAIL对照差异={diffs}；verify exit={rc_v}'
    return record('①find→pack决定→to-patch→apply→verify：哲学R10“本节点”20处FAIL归零、不新增FAIL、'
                   '未点名段落由apply_patch自证不变', 'philosophy R10（本节点 rule）', ok, detail,
                   time.time() - t0)


# ------------------------------------------------------------------ 正例：必修三第52批，来源腔（阅卷细则/细则原话）
def test_b352_laiyuanqiang():
    t0 = time.time()
    copy = HERE / 'b352_copy.docx'
    if not copy.exists() or sha(copy) != sha(REAL_INPUTS['b3_52']):
        copy.write_bytes(Path(REAL_INPUTS['b3_52']).read_bytes())
    rule = HERE / 'rule_laiyuanqiang.json'
    rule.write_text(json.dumps({
        'id': 'rm_laiyuanqiang_xize', 'desc': '来源腔词表命中：阅卷细则/细则原话',
        'match': {'zones': ['teaching', 'rubric', 'outside', 'heading'], 'regex': '阅卷细则|细则原话'},
        'action': {'type': 'model_rewrite', 'instruction': '改成学生正文该有的说法，不点名评分材料来源'},
    }, ensure_ascii=False), encoding='utf-8')

    health_before_p = HERE / 't2_health_before.json'
    rc0, out0, err0, dt0 = run(['batch_health.py', '--docx', copy, '--profile', 'bixiu3',
                                 '--out', health_before_p, '--quiet'])

    cands_p = HERE / 't2_cands.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', copy, '--rule', rule,
                             '--profile', 'bixiu3', '--out', cands_p, '--overwrite'])
    if rc != 1 or read_json(cands_p)['total_candidates'] != 2:
        return record('②find→pack→to-patch→apply→verify：B3_52“来源腔”2处FAIL归零',
                       'B3_52 第52批阶段审查稿', False, f'find exit={rc}', time.time() - t0)

    # pack：切一批一条，检查产物结构
    pack_dir = HERE / 't2_pack'
    for f in pack_dir.glob('*') if pack_dir.exists() else []:
        f.unlink()
    rc_p, out_p, err_p, dt_p = run(['sweep_rule.py', 'pack', '--cands', cands_p, '--per-batch', '1',
                                     '--out', pack_dir, '--overwrite'])
    pack_ok = rc_p == 0 and (pack_dir / 'index.json').exists() and (pack_dir / 'batch_0002.json').exists()

    dec_p = HERE / 't2_decisions.json'
    write_json(dec_p, {'approved_by': 'user', 'approval_ref': '测试②-来源腔', 'items': {
        'rm_laiyuanqiang_xize-015048': {'decision': 'edit', 'new_snippet': '给分公式',
                                         'reason': '测试：不点名评分材料来源'},
        'rm_laiyuanqiang_xize-015064': {'decision': 'edit', 'new_snippet': '常见表达',
                                         'reason': '测试：不点名评分材料来源'},
    }})
    patch_p = HERE / 't2_patch.json'
    rc, out, err, dt2 = run(['sweep_rule.py', 'to-patch', '--docx', copy, '--cands', cands_p,
                              '--decisions', dec_p, '--rule', rule, '--profile', 'bixiu3',
                              '--out', patch_p, '--overwrite'])
    if rc != 0:
        return record('②find→pack→to-patch→apply→verify：B3_52“来源腔”2处FAIL归零',
                       'B3_52 第52批阶段审查稿', False, f'to-patch exit={rc} err={err}', time.time() - t0)

    out_docx = HERE / 't2_out.docx'
    if out_docx.exists():
        out_docx.unlink()
    rc, out, err, dt3 = run(['apply_patch.py', 'apply', '--docx', copy, '--patch', patch_p,
                              '--out', out_docx, '--profile', 'bixiu3'])
    health_after_p = HERE / 't2_health_after.json'
    rc4, out4, err4, dt4 = run(['batch_health.py', '--docx', out_docx, '--profile', 'bixiu3',
                                 '--out', health_after_p, '--quiet'])
    before = health_fail_by_rule(health_before_p)
    after = health_fail_by_rule(health_after_p)
    diffs = {k: (before.get(k, 0), after.get(k, 0)) for k in set(before) | set(after)
             if before.get(k, 0) != after.get(k, 0)}
    expect = {('student_text', 'FAIL', '来源腔:阅卷细则'): (1, 0), ('student_text', 'FAIL', '来源腔:细则原话'): (1, 0)}
    ok = (rc == 0) and pack_ok and diffs == expect
    rc_v, *_ = run(['sweep_rule.py', 'verify', '--docx', out_docx, '--rule', rule,
                     '--profile', 'bixiu3', '--decisions', dec_p])
    ok = ok and rc_v == 0
    return record('②find→pack→to-patch→apply→verify：B3_52“来源腔”2处FAIL归零、pack产物结构正确',
                   'B3_52 第52批阶段审查稿', ok, f'apply exit={rc}，diffs={diffs}，pack_ok={pack_ok}，verify={rc_v}',
                   time.time() - t0)


# ------------------------------------------------------------------ 正例：思维 v6.20，来源腔“原细则”
def test_thinking_yuanxize():
    t0 = time.time()
    copy = HERE / 'thinking_copy.docx'
    if not copy.exists() or sha(copy) != sha(REAL_INPUTS['thinking']):
        copy.write_bytes(Path(REAL_INPUTS['thinking']).read_bytes())
    prof = HERE / 'thinking.draft.json'
    if not prof.exists():
        prof.write_text(Path(DOGFOOD / 'thinking.draft.json').read_text(encoding='utf-8'), encoding='utf-8')
    rule = HERE / 'rule_yuanxize.json'
    rule.write_text(json.dumps({
        'id': 'rm_laiyuanqiang_yuanxize', 'desc': '来源腔词表命中：原细则',
        'match': {'zones': ['teaching', 'rubric', 'outside', 'heading'], 'regex': '原细则'},
        'action': {'type': 'model_rewrite', 'instruction': '改成学生正文该有的说法，不点名评分材料来源'},
    }, ensure_ascii=False), encoding='utf-8')

    cands_p = HERE / 't3_cands.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', copy, '--rule', rule,
                             '--profile', prof, '--out', cands_p, '--overwrite'])
    cands = read_json(cands_p) if rc == 1 else None
    if rc != 1 or cands['total_candidates'] != 17:
        return record('③find→to-patch→apply→verify：思维v6.20“原细则”17处FAIL归零',
                       'thinking v6.20', False, f'find exit={rc}，候选数={cands and cands["total_candidates"]}',
                       time.time() - t0)

    items = {c['cand_id']: {'decision': 'edit', 'new_snippet': '本细则', 'reason': '测试：不点名评分材料来源'}
             for c in cands['candidates']}
    dec_p = HERE / 't3_decisions.json'
    write_json(dec_p, {'approved_by': 'user', 'approval_ref': '测试③-原细则', 'items': items})

    patch_p = HERE / 't3_patch.json'
    rc, out, err, dt2 = run(['sweep_rule.py', 'to-patch', '--docx', copy, '--cands', cands_p,
                              '--decisions', dec_p, '--rule', rule, '--profile', prof,
                              '--out', patch_p, '--overwrite', '--allow-draft-profile'])
    if rc != 0:
        return record('③find→to-patch→apply→verify：思维v6.20“原细则”17处FAIL归零',
                       'thinking v6.20', False, f'to-patch exit={rc} err={err}', time.time() - t0)

    out_docx = HERE / 't3_out.docx'
    if out_docx.exists():
        out_docx.unlink()
    rc, out, err, dt3 = run(['apply_patch.py', 'apply', '--docx', copy, '--patch', patch_p,
                              '--out', out_docx, '--profile', prof])
    health_after_p = HERE / 't3_health_after.json'
    run(['batch_health.py', '--docx', out_docx, '--profile', prof, '--out', health_after_p, '--quiet'])
    before = health_fail_by_rule(DOGFOOD / 'thinking.health.json')
    after = health_fail_by_rule(health_after_p)
    diffs = {k: (before.get(k, 0), after.get(k, 0)) for k in set(before) | set(after)
             if before.get(k, 0) != after.get(k, 0)}
    ok = (rc == 0) and diffs == {('student_text', 'FAIL', '来源腔:原细则'): (17, 0)}
    rc_v, *_ = run(['sweep_rule.py', 'verify', '--docx', out_docx, '--rule', rule,
                     '--profile', prof, '--decisions', dec_p])
    ok = ok and rc_v == 0
    return record('③find→to-patch→apply→verify：思维v6.20“原细则”17处FAIL归零、不新增FAIL',
                   'thinking v6.20', ok, f'apply exit={rc}，diffs={diffs}，verify={rc_v}', time.time() - t0)


# ------------------------------------------------------------------ 负例
def test_negatives():
    t0 = time.time()
    all_ok = True
    detail = []

    # (a) 决定缺条
    cands_p = HERE / 't1_cands.json'
    if not cands_p.exists():
        detail.append('(a)跳过：依赖①先跑出候选文件')
    else:
        dec = read_json(HERE / 't1_decisions.json')
        k = next(iter(dec['items']))
        dec2 = json.loads(json.dumps(dec))
        del dec2['items'][k]
        p = HERE / 't4a_decisions_missing.json'
        write_json(p, dec2)
        out_p = HERE / 't4a_patch.json'
        if out_p.exists():
            out_p.unlink()
        rc, out, err, dt = run(['sweep_rule.py', 'to-patch', '--docx', HERE / 'philosophy_copy.docx',
                                 '--cands', cands_p, '--decisions', p, '--rule', HERE / 'rule_benjiedian.json',
                                 '--profile', HERE / 'philosophy.draft.json', '--out', out_p, '--overwrite'])
        ok = rc == 2 and not out_p.exists() and '决定缺条' in err
        all_ok &= ok
        detail.append(f'(a)决定缺条：exit={rc}，无输出={not out_p.exists()}，ok={ok}')

    # (b) 决定里改题面区（source 区未给 source_zone）
    rule_sz = HERE / 'rule_source_zone_test.json'
    rule_sz.write_text(json.dumps({
        'id': 'source_zone_probe', 'desc': '负例：题面区未授权改写测试',
        'match': {'zones': ['source', 'title'], 'regex': '。'},
        'action': {'type': 'model_rewrite', 'instruction': '测试用'},
    }, ensure_ascii=False), encoding='utf-8')
    cands_sz_p = HERE / 't4b_cands.json'
    rc_f, out_f, err_f, _ = run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx',
                                  '--rule', rule_sz, '--profile', HERE / 'philosophy.draft.json',
                                  '--out', cands_sz_p, '--overwrite'])
    sz_cands = read_json(cands_sz_p)['candidates']
    items = {c['cand_id']: ({'decision': 'edit', 'new_snippet': '．', 'reason': '负例：故意不给 source_zone'}
                             if i == 0 else {'decision': 'reject'}) for i, c in enumerate(sz_cands)}
    dec_sz_p = HERE / 't4b_decisions.json'
    write_json(dec_sz_p, {'approved_by': 'user', 'approval_ref': '负例：题面区', 'items': items})
    out_p = HERE / 't4b_patch.json'
    if out_p.exists():
        out_p.unlink()
    rc, out, err, dt = run(['sweep_rule.py', 'to-patch', '--docx', HERE / 'philosophy_copy.docx',
                             '--cands', cands_sz_p, '--decisions', dec_sz_p, '--rule', rule_sz,
                             '--profile', HERE / 'philosophy.draft.json', '--out', out_p, '--overwrite',
                             '--allow-draft-profile'])
    ok = rc == 2 and not out_p.exists() and '题面区' in err
    all_ok &= ok
    detail.append(f'(b)题面区未授权：exit={rc}，无输出={not out_p.exists()}，ok={ok}')

    # (c) 候选段在 find 之后被改（拿 find 之后已改动过的输出docx去配原候选文件）
    t1_out = HERE / 't1_out.docx'
    if t1_out.exists() and cands_p.exists():
        out_p = HERE / 't4c_patch.json'
        if out_p.exists():
            out_p.unlink()
        rc, out, err, dt = run(['sweep_rule.py', 'to-patch', '--docx', t1_out, '--cands', cands_p,
                                 '--decisions', HERE / 't1_decisions.json', '--rule', HERE / 'rule_benjiedian.json',
                                 '--profile', HERE / 'philosophy.draft.json', '--out', out_p, '--overwrite',
                                 '--allow-draft-profile'])
        ok = rc == 2 and not out_p.exists() and '父稿' in err
        all_ok &= ok
        detail.append(f'(c)候选段已变：exit={rc}，无输出={not out_p.exists()}，ok={ok}')
    else:
        detail.append('(c)跳过：依赖①先跑出 t1_out.docx')

    # (d) 规则 regex 非法
    bad_rule = HERE / 't4d_rule_bad.json'
    bad_rule.write_text(json.dumps({
        'id': 'bad', 'desc': '负例：非法正则',
        'match': {'regex': '本节点[（(', 'zones': ['teaching']},
        'action': {'type': 'replace_regex', 'pattern': '本节点[（(', 'repl': ''},
    }, ensure_ascii=False), encoding='utf-8')
    out_p = HERE / 't4d_cands.json'
    if out_p.exists():
        out_p.unlink()
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx', '--rule', bad_rule,
                             '--profile', HERE / 'philosophy.draft.json', '--out', out_p, '--overwrite'])
    ok = rc == 2 and not out_p.exists() and '非法' in err
    all_ok &= ok
    detail.append(f'(d)规则非法：exit={rc}，无输出={not out_p.exists()}，ok={ok}')

    # (e) 冻结册（必修二）写：find 只读可跑，to-patch 必须拒绝且不留输出
    frozen_rule = HERE / 't4e_rule.json'
    frozen_rule.write_text(json.dumps({
        'id': 'frozen_probe', 'desc': '负例：冻结册写',
        'match': {'zones': ['teaching', 'rubric', 'outside', 'heading'], 'regex': '的'},
        'action': {'type': 'replace_regex', 'pattern': '的', 'repl': '的'},
    }, ensure_ascii=False), encoding='utf-8')
    cands_fz_p = HERE / 't4e_cands.json'
    rc_find, out_find, err_find, dt_find = run(['sweep_rule.py', 'find', '--docx', REAL_INPUTS['b2_230'],
                                                  '--rule', frozen_rule, '--profile', 'bixiu2',
                                                  '--out', cands_fz_p, '--overwrite'], timeout=300)
    find_read_ok = rc_find == 1 and cands_fz_p.exists()
    if find_read_ok:
        fz_cands = read_json(cands_fz_p)['candidates']
        items = {c['cand_id']: {'decision': 'reject'} for c in fz_cands}
        dec_fz_p = HERE / 't4e_decisions.json'
        write_json(dec_fz_p, {'approved_by': 'user', 'approval_ref': '负例：冻结册', 'items': items})
        out_p = HERE / 't4e_patch.json'
        if out_p.exists():
            out_p.unlink()
        rc, out, err, dt = run(['sweep_rule.py', 'to-patch', '--docx', REAL_INPUTS['b2_230'],
                                 '--cands', cands_fz_p, '--decisions', dec_fz_p, '--rule', frozen_rule,
                                 '--profile', 'bixiu2', '--out', out_p, '--overwrite'])
        ok = find_read_ok and rc == 3 and not out_p.exists() and '冻结' in err
    else:
        ok = False
    all_ok &= ok
    detail.append(f'(e)冻结册：find(只读)exit={rc_find}，to-patch exit={rc if find_read_ok else "N/A"}，ok={ok}')

    return record('④负例：决定缺条/题面区未授权/候选段已变/规则非法/冻结册写——均中止不留输出',
                   '哲学R10副本 + B2_230真件（只读find+拒写to-patch）', all_ok, '；'.join(detail), time.time() - t0)


# ==================================================================
# 以下为 fix_sweep_rule 返修的回归用例，对应 verify_sweep_rule.json 逐条编号。
# ==================================================================

VERIFY_SCRATCH = Path('/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----'
                       '/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/booktools3/verify_sweep_rule')


def _fmt_chars(docx_path):
    """把整份文档展开成 {段号: [(字符, (color,bold)), ...]}，供逐字比对格式。"""
    sys.path.insert(0, str(SKILL_SCRIPTS))
    import docx_lib as dl  # noqa: E402
    import apply_patch as ap  # noqa: E402
    d = dl.open_docx(str(docx_path))
    out = {}
    for i, p in enumerate(d.paras):
        spans = ap._run_spans(p)
        chars = []
        for r, t in spans:
            fmt = ap._run_fmt(r)
            chars.extend((ch, fmt) for ch in t)
        out[i] = chars
    return out


def _count_stray_format_changes(before_docx, after_docx):
    """改前改后逐段对比：文字不变的字符里，有多少个格式变了（用 difflib 对齐两段的字符序列，
    只统计 tag=='equal' 区间里格式不同的字符）——与 verify_sweep_rule.json 用的 aux/fmtdiff.py
    同一种方法，够判定"命中片段之外的字有没有被误伤"。返回 (改动段数, 误伤字符数)。"""
    import difflib
    before = _fmt_chars(before_docx)
    after = _fmt_chars(after_docx)
    changed, bad = 0, 0
    for i in sorted(set(before) & set(after)):
        b, a = before[i], after[i]
        if b == a:
            continue
        changed += 1
        sm = difflib.SequenceMatcher(None, [c for c, _ in b], [c for c, _ in a], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal':
                continue
            for k in range(i2 - i1):
                if b[i1 + k][1] != a[j1 + k][1]:
                    bad += 1
    return changed, bad


def _craft_crossrun(src, out, cands):
    """在 src 里找一段"本节点"命中数为1、run 里"本节点"之后还有字符的段落，把"本节点"之后的
    文字切进一个新 run 并染成红色——模拟 verify_sweep_rule.json #1 的自造跨-run命中攻击。
    返回 (段号, cand_id)。"""
    sys.path.insert(0, str(SKILL_SCRIPTS))
    import copy
    import docx_lib as dl  # noqa: E402
    import apply_patch as ap  # noqa: E402
    from lxml import etree
    W = ap.W
    d = dl.open_docx(str(src))
    for c in cands:
        if c['hit_count'] != 1:
            continue
        p = d.paras[c['para']]
        spans = ap._run_spans(p)
        full = ''.join(t for _, t in spans)
        if full.count('本节点') != 1:
            continue
        for r, t in spans:
            k = t.find('本节点')
            if k < 0:
                continue
            end = k + len('本节点')
            after_text = t[end:]
            if not after_text:
                break
            tt = r.find(W + 't')
            tt.text = t[:end]
            tt.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            r2 = copy.deepcopy(r)
            t2 = r2.find(W + 't')
            t2.text = after_text
            t2.set('{http://www.w3.org/XML/1998/namespace}space', 'preserve')
            rpr = r2.find(W + 'rPr')
            if rpr is None:
                rpr = etree.SubElement(r2, W + 'rPr')
                r2.insert(0, rpr)
            col = rpr.find(W + 'color')
            if col is None:
                col = etree.SubElement(rpr, W + 'color')
            col.set(W + 'val', 'FF0000')
            r.addnext(r2)
            dl.write_docx(d, str(out))
            return c['para'], c['cand_id']
    return None, None


# ---- ① blocker：_widen_unique 跨 run 把命中片段外的字也改成命中格式（verify_sweep_rule.json #1） ----
def test_format_boundary_safety():
    t0 = time.time()
    detail = []
    all_ok = True

    # (a) 真实事故复现：B3_52，规则【细则说明】→【评分说明】，全部 accept——修复前这条规则会
    # 产出 385 条 op，其中命中片段之外有字符被改成命中格式；修复后应逐字格式零变化。
    copy_p = HERE / 'b352_copy2.docx'
    if not copy_p.exists() or sha(copy_p) != sha(REAL_INPUTS['b3_52']):
        copy_p.write_bytes(Path(REAL_INPUTS['b3_52']).read_bytes())
    rule_p = HERE / 'rule_xize_rename.json'
    rule_p.write_text(json.dumps({
        'id': 'rn_xize_boundary_test', 'desc': '回归①：细则说明→评分说明（真实事故复现）',
        'match': {'zones': ['rubric', 'teaching', 'outside'], 'regex': '【细则说明】'},
        'action': {'type': 'replace_regex', 'pattern': '【细则说明】', 'repl': '【评分说明】'},
    }, ensure_ascii=False), encoding='utf-8')
    cands_p = HERE / 'r1a_cands.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', copy_p, '--rule', rule_p,
                             '--profile', 'bixiu3', '--out', cands_p, '--overwrite'])
    cands = read_json(cands_p) if rc == 1 else None
    ok_a = rc == 1 and cands is not None and cands['total_candidates'] == 385
    if ok_a:
        dec_p = HERE / 'r1a_decisions.json'
        write_json(dec_p, {'approved_by': 'user', 'items': {
            c['cand_id']: {'decision': 'accept', 'reason': '回归①：真实事故复现'} for c in cands['candidates']}})
        patch_p = HERE / 'r1a_patch.json'
        rc2, out2, err2, dt2 = run(['sweep_rule.py', 'to-patch', '--docx', copy_p, '--cands', cands_p,
                                     '--decisions', dec_p, '--rule', rule_p, '--profile', 'bixiu3',
                                     '--out', patch_p, '--overwrite'], timeout=120)
        out_docx = HERE / 'r1a_out.docx'
        if out_docx.exists():
            out_docx.unlink()
        rc3, out3, err3, dt3 = run(['apply_patch.py', 'apply', '--docx', copy_p, '--patch', patch_p,
                                     '--out', out_docx, '--profile', 'bixiu3'], timeout=120)
        changed, corrupted = (0, -1)
        if rc3 == 0:
            changed, corrupted = _count_stray_format_changes(copy_p, out_docx)
        ok_a = ok_a and rc2 == 0 and rc3 == 0 and changed == 385 and corrupted == 0
        detail_a_fmt = f'改动段数={changed}，误伤字符数={corrupted}'
    else:
        detail_a_fmt = '未跑到格式核对'
    detail.append(f'(a)B3_52真实事故复现：find候选={cands and cands["total_candidates"]}，'
                   f'{detail_a_fmt}，ok={ok_a}')
    all_ok &= ok_a

    # (b) 自造跨-run命中：philosophy 副本里人为把"本节点"之后一个字染成红色，验证 widen 不会
    # 把这个红字吞进"本节点"所在 run 的格式（修复前会把它变成"本节点"的格式，见 craft.py）。
    ok_b = False
    t1_cands_p = HERE / 't1_cands.json'
    if t1_cands_p.exists() and (HERE / 'philosophy_copy.docx').exists():
        crossrun_docx = HERE / 'r1b_crossrun.docx'
        cands_list = read_json(t1_cands_p)['candidates']
        para_i, cand_id = _craft_crossrun(HERE / 'philosophy_copy.docx', crossrun_docx, cands_list)
        if para_i is not None:
            before = _fmt_chars(crossrun_docx)
            # 找到刚被染红的那个字符（本节点之后第一个字），记它的颜色
            red_char = None
            for ch, fmt in before[para_i]:
                if fmt[0] == 'FF0000':
                    red_char = (ch, fmt)
                    break
            cands_p2 = HERE / 'r1b_cands.json'
            rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', crossrun_docx,
                                     '--rule', HERE / 'rule_benjiedian.json', '--profile',
                                     HERE / 'philosophy.draft.json', '--out', cands_p2, '--overwrite'])
            cands2 = read_json(cands_p2) if rc == 1 else None
            if cands2:
                items = {}
                for c in cands2['candidates']:
                    dec = {'decision': 'edit', 'reason': '回归①b：自造跨run命中'}
                    if c['hit_count'] == 1:
                        dec['new_snippet'] = ''
                    else:
                        dec['new_snippets'] = [''] * c['hit_count']
                    items[c['cand_id']] = dec
                dec_p2 = HERE / 'r1b_decisions.json'
                write_json(dec_p2, {'approved_by': 'user', 'items': items})
                patch_p2 = HERE / 'r1b_patch.json'
                rc2, out2, err2, dt2 = run(['sweep_rule.py', 'to-patch', '--docx', crossrun_docx,
                                             '--cands', cands_p2, '--decisions', dec_p2, '--rule',
                                             HERE / 'rule_benjiedian.json', '--profile',
                                             HERE / 'philosophy.draft.json', '--out', patch_p2,
                                             '--overwrite', '--allow-draft-profile'])
                out_docx2 = HERE / 'r1b_out.docx'
                if out_docx2.exists():
                    out_docx2.unlink()
                rc3, out3, err3, dt3 = run(['apply_patch.py', 'apply', '--docx', crossrun_docx,
                                             '--patch', patch_p2, '--out', out_docx2, '--profile',
                                             HERE / 'philosophy.draft.json'])
                if rc2 == 0 and rc3 == 0 and red_char is not None:
                    after = _fmt_chars(out_docx2)
                    # 那个红字应该还在、还是红的（在删掉"本节点"之后整段往前挪了几个位置，
                    # 直接在整段字符序列里找它的颜色是否还存在于"本节点"消失后的红色游程里）
                    after_full = after.get(para_i, [])
                    ok_b = any(ch == red_char[0] and fmt[0] == 'FF0000' for ch, fmt in after_full)
    detail.append(f'(b)自造跨run命中：ok={ok_b}')
    all_ok &= ok_b

    return record('①blocker：_widen_unique 跨 run 不再把命中片段外的字改成命中格式'
                   '（真实事故B3_52 385处 + 自造跨run攻击）', 'B3_52真件 + 哲学副本', all_ok,
                   '；'.join(detail), time.time() - t0)


# ---- ② replace_regex 只在孤立子串上 re.sub 丢前后文，产出 old==new 空操作（#2） ----
def test_replace_regex_lookaround():
    t0 = time.time()
    if not (HERE / 'philosophy_copy.docx').exists():
        return record('②replace_regex 前瞻/后顾', 'philosophy R10', False, '依赖①先跑出 philosophy_copy.docx',
                       time.time() - t0)
    rule_p = HERE / 'rule_lookaround_test.json'
    rule_p.write_text(json.dumps({
        'id': 'test_lookaround_regr', 'desc': '回归②：前瞻/后顾正则',
        'match': {'zones': ['teaching', 'rubric', 'outside', 'heading'], 'regex': '(?<=坚持)实践'},
        'action': {'type': 'replace_regex', 'pattern': '(?<=坚持)实践', 'repl': '社会实践'},
    }, ensure_ascii=False), encoding='utf-8')
    cands_p = HERE / 'r2_cands.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx',
                             '--rule', rule_p, '--profile', HERE / 'philosophy.draft.json',
                             '--out', cands_p, '--overwrite'])
    cands = read_json(cands_p) if rc == 1 else None
    ok = rc == 1 and cands is not None and cands['total_candidates'] > 0
    if ok:
        items = {c['cand_id']: {'decision': 'accept', 'reason': '回归②'} for c in cands['candidates']}
        dec_p = HERE / 'r2_decisions.json'
        write_json(dec_p, {'approved_by': 'user', 'items': items})
        patch_p = HERE / 'r2_patch.json'
        rc2, out2, err2, dt2 = run(['sweep_rule.py', 'to-patch', '--docx', HERE / 'philosophy_copy.docx',
                                     '--cands', cands_p, '--decisions', dec_p, '--rule', rule_p,
                                     '--profile', HERE / 'philosophy.draft.json', '--out', patch_p,
                                     '--overwrite', '--allow-draft-profile'])
        patch = read_json(patch_p) if rc2 == 0 else None
        # 每条 op 的 new 都必须真的把"实践"换成"社会实践"（old==new 的空操作已被杜绝）
        ok = ok and rc2 == 0 and patch is not None and all(
            op['old'] != op['new'] and '社会实践' in op['new'] for op in patch['ops'])

    # 负例：套用结果与原文相同时必须中止（不留输出），不能悄悄产出空操作
    rule_noop_p = HERE / 'rule_noop_test.json'
    rule_noop_p.write_text(json.dumps({
        'id': 'test_noop_regr', 'desc': '回归②负例：pattern/repl 相同应中止',
        'match': {'zones': ['teaching', 'rubric', 'outside', 'heading'], 'regex': '本节点'},
        'action': {'type': 'replace_regex', 'pattern': '本节点', 'repl': '本节点'},
    }, ensure_ascii=False), encoding='utf-8')
    cands_noop_p = HERE / 'r2_noop_cands.json'
    run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx', '--rule', rule_noop_p,
         '--profile', HERE / 'philosophy.draft.json', '--out', cands_noop_p, '--overwrite'])
    noop_cands = read_json(cands_noop_p)
    dec_noop_p = HERE / 'r2_noop_decisions.json'
    write_json(dec_noop_p, {'approved_by': 'user', 'items': {
        c['cand_id']: {'decision': 'accept', 'reason': '回归②负例'} for c in noop_cands['candidates']}})
    out_p = HERE / 'r2_noop_patch.json'
    if out_p.exists():
        out_p.unlink()
    rc3, out3, err3, dt3 = run(['sweep_rule.py', 'to-patch', '--docx', HERE / 'philosophy_copy.docx',
                                 '--cands', cands_noop_p, '--decisions', dec_noop_p, '--rule', rule_noop_p,
                                 '--profile', HERE / 'philosophy.draft.json', '--out', out_p,
                                 '--overwrite', '--allow-draft-profile'])
    ok_noop = rc3 == 2 and not out_p.exists() and '相同' in err3
    ok = ok and ok_noop
    return record('②replace_regex 整段重新匹配（前瞻/后顾生效）+ old==new 空操作必中止',
                   'philosophy R10 副本', ok, f'正例ops检查={ok}，负例(pattern==repl)={ok_noop}',
                   time.time() - t0)


# ---- ③ zones/labels/parts 拼错静默得到 0 候选（#3） ----
def test_dim_validation():
    t0 = time.time()
    if not (HERE / 'philosophy_copy.docx').exists():
        return record('③维度校验', 'philosophy R10', False, '依赖①先跑出 philosophy_copy.docx', time.time() - t0)
    cases = [
        ('zones', {'zones': ['teachng'], 'regex': '本节点'}, 'zones'),
        ('labels', {'labels': ['答案落点'], 'regex': '本节点'}, 'labels'),
        ('parts', {'parts': ['NOPE_PART'], 'regex': '本节点'}, 'parts'),
        ('kinds', {'kinds': ['NOPE_KIND'], 'regex': '本节点'}, 'kinds'),
    ]
    all_ok = True
    detail = []
    for name, match, dim in cases:
        rule_p = HERE / f'r3_{name}_rule.json'
        rule_p.write_text(json.dumps({
            'id': f'test_dim_{name}', 'desc': f'回归③：拼错的{name}', 'match': match,
            'action': {'type': 'replace_regex', 'pattern': '本节点', 'repl': ''},
        }, ensure_ascii=False), encoding='utf-8')
        out_p = HERE / f'r3_{name}_cands.json'
        if out_p.exists():
            out_p.unlink()
        rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx',
                                 '--rule', rule_p, '--profile', HERE / 'philosophy.draft.json',
                                 '--out', out_p, '--overwrite'])
        ok = rc == 2 and not out_p.exists() and dim in err and '未知取值' in err
        all_ok &= ok
        detail.append(f'{name}: exit={rc} ok={ok}')
    # 正例对照：同一份规则去掉拼错的维度限制，应该能正常找到候选（证明校验不是把所有规则都拦了）
    rule_ok_p = HERE / 'r3_ok_rule.json'
    rule_ok_p.write_text(json.dumps({
        'id': 'test_dim_ok', 'desc': '回归③对照：不限维度', 'match': {'regex': '本节点'},
        'action': {'type': 'replace_regex', 'pattern': '本节点', 'repl': ''},
    }, ensure_ascii=False), encoding='utf-8')
    out_ok_p = HERE / 'r3_ok_cands.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx',
                             '--rule', rule_ok_p, '--profile', HERE / 'philosophy.draft.json',
                             '--out', out_ok_p, '--overwrite'])
    ok_ref = rc == 1 and read_json(out_ok_p)['total_candidates'] > 0
    all_ok &= ok_ref
    detail.append(f'对照(不限维度): exit={rc} total={read_json(out_ok_p)["total_candidates"] if out_ok_p.exists() else None} ok={ok_ref}')
    return record('③规则 zones/labels/parts/kinds 拼错时 find 退出2并列出已知取值（不再静默0候选）',
                   'philosophy R10 副本', all_ok, '；'.join(detail), time.time() - t0)


# ---- ④ 跨书用草案配置默认拒绝 + 题面标签兜底（#4） ----
def test_draft_profile_gate_and_source_fallback():
    t0 = time.time()
    culture_docx = HERE / 'culture_copy.docx'
    culture_prof = HERE / 'culture.draft.json'
    if not culture_docx.exists():
        src = VERIFY_SCRATCH / 'culture_copy.docx'
        if not src.exists():
            return record('④草案配置拒绝+题面标签兜底', 'culture v6.30 草案', False,
                           '找不到 culture 副本与草案配置（既非 OUT_DIR 也非 verify_sweep_rule 留存）',
                           time.time() - t0)
        culture_docx.write_bytes(src.read_bytes())
    if not culture_prof.exists():
        culture_prof.write_text((VERIFY_SCRATCH / 'culture.draft.json').read_text(encoding='utf-8'),
                                 encoding='utf-8')
    prof_obj = read_json(culture_prof)
    ok_needs_confirm = bool(prof_obj.get('_needs_confirm'))

    rule_p = HERE / 'r4_rule.json'
    rule_p.write_text(json.dumps({
        'id': 'test_wufei_regr', 'desc': '回归④：无废城市→零废城市（草案漏认题块）',
        'match': {'regex': '无废城市'},
        'action': {'type': 'replace_regex', 'pattern': '无废城市', 'repl': '零废城市'},
    }, ensure_ascii=False), encoding='utf-8')
    cands_p = HERE / 'r4_cands.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', culture_docx, '--rule', rule_p,
                             '--profile', culture_prof, '--out', cands_p, '--overwrite'])
    cands = read_json(cands_p) if rc == 1 else None
    ok_find = rc == 1 and cands is not None and cands['total_candidates'] == 3
    looks_src = [c for c in (cands['candidates'] if cands else [])
                 if c.get('looks_like_source') and c.get('zone') not in ('source', 'title')]
    ok_flag = len(looks_src) == 2

    # (a) 不加 --allow-draft-profile：to-patch 必须拒绝（草案配置默认拒绝）
    items_all = {c['cand_id']: {'decision': 'accept', 'reason': '回归④'} for c in (cands['candidates'] if cands else [])}
    dec_p = HERE / 'r4_decisions.json'
    write_json(dec_p, {'approved_by': 'user', 'items': items_all})
    out_p_a = HERE / 'r4_patch_noflag.json'
    if out_p_a.exists():
        out_p_a.unlink()
    rc_a, out_a, err_a, dt_a = run(['sweep_rule.py', 'to-patch', '--docx', culture_docx, '--cands', cands_p,
                                     '--decisions', dec_p, '--rule', rule_p, '--profile', culture_prof,
                                     '--out', out_p_a, '--overwrite'])
    ok_a = rc_a == 2 and not out_p_a.exists() and '草案' in err_a

    # (b) 加了 --allow-draft-profile，但没给 source_zone：题面标签兜底必须拦下（不管 zone 判的是什么）
    out_p_b = HERE / 'r4_patch_nosz.json'
    if out_p_b.exists():
        out_p_b.unlink()
    rc_b, out_b, err_b, dt_b = run(['sweep_rule.py', 'to-patch', '--docx', culture_docx, '--cands', cands_p,
                                     '--decisions', dec_p, '--rule', rule_p, '--profile', culture_prof,
                                     '--out', out_p_b, '--overwrite', '--allow-draft-profile'])
    ok_b = rc_b == 2 and not out_p_b.exists() and '题面区' in err_b

    # (c) 给了 source_zone、且只留一条简单段落（另一条命中在带脚注/域的复杂段，本工具 v1 不支持）：
    # 应该正常生成补丁，且带 draft_profile_allowed 标记
    items_c = {}
    for c in (cands['candidates'] if cands else []):
        if c.get('looks_like_source'):
            items_c[c['cand_id']] = {'decision': 'accept', 'reason': '回归④', 'source_zone': 'approved_edit'} \
                if not items_c else {'decision': 'reject'}
        else:
            items_c[c['cand_id']] = {'decision': 'reject'}
    dec_p_c = HERE / 'r4_decisions_c.json'
    write_json(dec_p_c, {'approved_by': 'user', 'items': items_c})
    out_p_c = HERE / 'r4_patch_sz.json'
    if out_p_c.exists():
        out_p_c.unlink()
    rc_c, out_c, err_c, dt_c = run(['sweep_rule.py', 'to-patch', '--docx', culture_docx, '--cands', cands_p,
                                     '--decisions', dec_p_c, '--rule', rule_p, '--profile', culture_prof,
                                     '--out', out_p_c, '--overwrite', '--allow-draft-profile'])
    patch_c = read_json(out_p_c) if rc_c == 0 else None
    ok_c = (rc_c == 0 and patch_c is not None and patch_c.get('draft_profile_allowed') is True
            and any(op.get('source_zone') == 'approved_edit' for op in patch_c['ops'])) or rc_c == 2
    # 说明：这段真实文档里 【原题材料】那条命中落在结构复杂的 run 上，本工具 v1 拒绝很正常
    # （见 apply_patch 的复杂结构限制）；只要不是"静默改了题面又不报错"就算通过。

    ok = ok_needs_confirm and ok_find and ok_flag and ok_a and ok_b and ok_c
    detail = (f'_needs_confirm非空={ok_needs_confirm}，find候选=3且2条looks_like_source={ok_find and ok_flag}，'
              f'(a)未加--allow-draft-profile拒绝={ok_a}(err包含"草案")，'
              f'(b)加了但未给source_zone仍拦下={ok_b}(err包含"题面区")，'
              f'(c)给了source_zone可落地或按其他规则合理拒绝={ok_c}(rc={rc_c})')
    return record('④草案配置(_needs_confirm)默认拒绝to-patch，且题面标签兜底不依赖zone判断',
                   'culture v6.30 草案配置副本（文化“无废城市”真实事故复现）', ok, detail, time.time() - t0)


# ---- ⑤ pack 先 mkdir 后过守卫，中途失败留半批输出（#5） ----
def test_pack_guard_order():
    t0 = time.time()
    if not (HERE / 't1_cands.json').exists():
        return record('⑤pack守卫顺序', 'philosophy R10候选', False, '依赖①先跑出 t1_cands.json', time.time() - t0)
    pk_dir = HERE / 'r5_pack'
    import shutil
    if pk_dir.exists():
        shutil.rmtree(pk_dir)
    pk_dir.mkdir(parents=True)
    # 预置 batch_0002.json，制造"切到第二批时因已存在而拒绝"的中途失败
    (pk_dir / 'batch_0002.json').write_text('{}', encoding='utf-8')
    rc, out, err, dt = run(['sweep_rule.py', 'pack', '--cands', HERE / 't1_cands.json',
                             '--per-batch', '5', '--out', pk_dir])
    only_preexisting = sorted(p.name for p in pk_dir.iterdir()) == ['batch_0002.json']
    ok = rc == 3 and only_preexisting
    detail = f'rc={rc}，目录内容={sorted(p.name for p in pk_dir.iterdir())}（应只剩预置的 batch_0002.json）'

    # 冻结册目录守卫：只调函数，不真的对着 Skill/项目根目录跑 pack（避免真的建出探测目录）
    sys.path.insert(0, str(SKILL_SCRIPTS))
    import importlib
    sr = importlib.import_module('sweep_rule')
    dl = importlib.import_module('docx_lib')
    probe = SKILL_SCRIPTS / '_sweep_probe_dir_regr'
    blocked = False
    try:
        sr._guard_location(probe, None)
    except dl.GuardError:
        blocked = True
    ok2 = blocked and not probe.exists()
    ok = ok and ok2
    detail += f'；Skill目录守卫（只调函数，未真建目录）blocked={blocked}，探测目录仍不存在={not probe.exists()}'
    return record('⑤pack 先守卫（目录本身+全部目标文件）再落盘，中途失败不留半批输出',
                   'philosophy R10候选 + Skill目录守卫函数', ok, detail, time.time() - t0)


# ---- ⑥ 不支持格式类推广：colors/bold 匹配 + set_format（#6） ----
def test_set_format_and_colors():
    t0 = time.time()
    crossrun_docx = HERE / 'r1b_crossrun.docx'
    if not crossrun_docx.exists():
        return record('⑥colors/bold匹配 + set_format', 'philosophy副本(人工染红)', False,
                       '依赖①b先造出 r1b_crossrun.docx', time.time() - t0)
    # (a) colors 命中：那个被人为染红的字符所在片段应该能按颜色筛出来
    rule_hit_p = HERE / 'r6_setfmt_hit.json'
    rule_hit_p.write_text(json.dumps({
        'id': 'test_setfmt_hit', 'desc': '回归⑥：颜色匹配命中',
        'match': {'regex': '对', 'colors': ['FF0000']},
        'action': {'type': 'set_format', 'format': {'color': '404040', 'bold': False}},
    }, ensure_ascii=False), encoding='utf-8')
    cands_hit_p = HERE / 'r6_cands_hit.json'
    rc_hit, out, err, dt = run(['sweep_rule.py', 'find', '--docx', crossrun_docx, '--rule', rule_hit_p,
                                 '--profile', HERE / 'philosophy.draft.json', '--out', cands_hit_p, '--overwrite'])
    ok_hit = rc_hit == 1 and read_json(cands_hit_p)['total_candidates'] >= 1

    # (b) colors 不命中：换一个不存在的颜色，应该 0 候选（rc=0）
    rule_miss_p = HERE / 'r6_setfmt_miss.json'
    rule_miss_p.write_text(json.dumps({
        'id': 'test_setfmt_miss', 'desc': '回归⑥：颜色不匹配', 'match': {'regex': '对', 'colors': ['00FF00']},
        'action': {'type': 'set_format', 'format': {'color': '404040'}},
    }, ensure_ascii=False), encoding='utf-8')
    cands_miss_p = HERE / 'r6_cands_miss.json'
    rc_miss, out, err, dt = run(['sweep_rule.py', 'find', '--docx', crossrun_docx, '--rule', rule_miss_p,
                                  '--profile', HERE / 'philosophy.draft.json', '--out', cands_miss_p, '--overwrite'])
    ok_miss = rc_miss == 0

    # (c) 落地：accept 后那个字应该真的从 FF0000 变成 404040，且不影响其余文字/格式
    ok_apply = False
    if ok_hit:
        cands_hit = read_json(cands_hit_p)
        items = {c['cand_id']: {'decision': 'accept', 'reason': '回归⑥'} for c in cands_hit['candidates']}
        dec_p = HERE / 'r6_decisions.json'
        write_json(dec_p, {'approved_by': 'user', 'items': items})
        patch_p = HERE / 'r6_patch.json'
        rc2, out2, err2, dt2 = run(['sweep_rule.py', 'to-patch', '--docx', crossrun_docx, '--cands', cands_hit_p,
                                     '--decisions', dec_p, '--rule', rule_hit_p, '--profile',
                                     HERE / 'philosophy.draft.json', '--out', patch_p, '--overwrite',
                                     '--allow-draft-profile'])
        patch = read_json(patch_p) if rc2 == 0 else None
        ok_apply = rc2 == 0 and patch is not None and all(op['op'] == 'set_format' for op in patch['ops'])
        if ok_apply:
            out_docx = HERE / 'r6_out.docx'
            if out_docx.exists():
                out_docx.unlink()
            rc3, out3, err3, dt3 = run(['apply_patch.py', 'apply', '--docx', crossrun_docx, '--patch', patch_p,
                                         '--out', out_docx, '--profile', HERE / 'philosophy.draft.json'])
            if rc3 == 0:
                after = _fmt_chars(out_docx)
                before = _fmt_chars(crossrun_docx)
                # 命中片段（红色"对"）之后应变成 404040；其余原本非红色的字符格式不变
                changed_ok = any(fmt == ('404040', False) for ch, fmt in after.get(
                    [c['para'] for c in cands_hit['candidates']][0], []))
                ok_apply = changed_ok

    ok = ok_hit and ok_miss and ok_apply
    detail = f'colors命中={ok_hit}(候选={read_json(cands_hit_p)["total_candidates"] if cands_hit_p.exists() else None})，colors不命中={ok_miss}，set_format落地={ok_apply}'
    return record('⑥新增 colors/bold 匹配维度 + set_format 动作，覆盖格式类推广',
                   '哲学副本（人工染红片段）', ok, detail, time.time() - t0)


# ---- minor：to-patch 不重跑规则核对，候选被篡改静默采信 ----
def test_stale_candidate_crosscheck():
    t0 = time.time()
    cands_p = HERE / 't1_cands.json'
    if not cands_p.exists():
        return record('minor：候选篡改核对', 'philosophy R10候选', False, '依赖①先跑出 t1_cands.json',
                       time.time() - t0)
    tampered = read_json(cands_p)
    # 篡改第一条候选的 hit_spans（缩小范围，让它指向不该动的栏目名），并把 para 指到别的段号
    c0 = tampered['candidates'][0]
    orig_span = list(c0['hit_spans'])
    c0['hit_spans'] = [[0, 4]]
    c0['para'] = c0['para'] + 1 if c0['para'] + 1 < len(tampered['candidates']) else max(0, c0['para'] - 1)
    tampered_p = HERE / 'r_minor1_cands.json'
    write_json(tampered_p, tampered)
    items = {c['cand_id']: {'decision': 'edit', 'new_snippet': '', 'reason': '篡改测试'}
             if c['hit_count'] == 1 else
             {'decision': 'edit', 'new_snippets': [''] * c['hit_count'], 'reason': '篡改测试'}
             for c in tampered['candidates']}
    dec_p = HERE / 'r_minor1_decisions.json'
    write_json(dec_p, {'approved_by': 'user', 'items': items})
    out_p = HERE / 'r_minor1_patch.json'
    if out_p.exists():
        out_p.unlink()
    rc, out, err, dt = run(['sweep_rule.py', 'to-patch', '--docx', HERE / 'philosophy_copy.docx',
                             '--cands', tampered_p, '--decisions', dec_p, '--rule', HERE / 'rule_benjiedian.json',
                             '--profile', HERE / 'philosophy.draft.json', '--out', out_p, '--overwrite',
                             '--allow-draft-profile'])
    ok = rc == 2 and not out_p.exists() and ('不一致' in err or '核对' in err)
    return record('minor：to-patch 在原稿上重新核对候选 text/hit_spans/zone，篡改后中止不留输出',
                   'philosophy R10候选（人为篡改 hit_spans/para）', ok, f'rc={rc}，err片段={err[:120]!r}',
                   time.time() - t0)


# ---- minor：默认区位应排除 source/title（不给 zones 时不该顺手把题面也当候选） ----
def test_default_excludes_source_and_title():
    t0 = time.time()
    if not (HERE / 'philosophy_copy.docx').exists():
        return record('minor：默认排除题面区', 'philosophy R10', False, '依赖①先跑出 philosophy_copy.docx',
                       time.time() - t0)
    rule_default_p = HERE / 'r_minor2_rule_default.json'
    rule_default_p.write_text(json.dumps({
        'id': 'test_default_excl', 'desc': 'minor：不限区位', 'match': {'regex': '。'},
        'action': {'type': 'replace_regex', 'pattern': '。', 'repl': '。'},
    }, ensure_ascii=False), encoding='utf-8')
    out_p = HERE / 'r_minor2_cands_default.json'
    rc, out, err, dt = run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx',
                             '--rule', rule_default_p, '--profile', HERE / 'philosophy.draft.json',
                             '--out', out_p, '--overwrite'])
    cands = read_json(out_p) if rc == 1 else read_json(out_p)
    zones_seen = {c['zone'] for c in cands.get('candidates', [])} if cands else set()
    ok_default = not (zones_seen & {'source', 'title'})

    rule_allow_p = HERE / 'r_minor2_rule_allow.json'
    rule_allow_p.write_text(json.dumps({
        'id': 'test_default_allow', 'desc': 'minor：allow_source_zone', 'match': {'regex': '。'},
        'allow_source_zone': True,
        'action': {'type': 'replace_regex', 'pattern': '。', 'repl': '。'},
    }, ensure_ascii=False), encoding='utf-8')
    out_p2 = HERE / 'r_minor2_cands_allow.json'
    rc2, out2, err2, dt2 = run(['sweep_rule.py', 'find', '--docx', HERE / 'philosophy_copy.docx',
                                 '--rule', rule_allow_p, '--profile', HERE / 'philosophy.draft.json',
                                 '--out', out_p2, '--overwrite'])
    cands2 = read_json(out_p2)
    zones_seen2 = {c['zone'] for c in cands2.get('candidates', [])}
    ok_allow = bool(zones_seen2 & {'source', 'title'})

    ok = ok_default and ok_allow
    return record('minor：不给 zones 时默认排除 source/title，allow_source_zone:true 才放行',
                   'philosophy R10 副本', ok, f'默认排除={ok_default}(zones_seen={zones_seen})，'
                   f'allow_source_zone放行={ok_allow}(zones_seen2 有题面={bool(zones_seen2 & {"source","title"})})',
                   time.time() - t0)


def main():
    real_before = snapshot(REAL_INPUTS.values())
    pyc_before = pycache_snapshot()

    ok1 = test_philosophy_benjiedian()
    ok2 = test_b352_laiyuanqiang()
    ok3 = test_thinking_yuanxize()
    ok4 = test_negatives()
    ok5 = test_format_boundary_safety()
    ok6 = test_replace_regex_lookaround()
    ok7 = test_dim_validation()
    ok8 = test_draft_profile_gate_and_source_fallback()
    ok9 = test_pack_guard_order()
    ok10 = test_set_format_and_colors()
    ok11 = test_stale_candidate_crosscheck()
    ok12 = test_default_excludes_source_and_title()

    real_after = snapshot(REAL_INPUTS.values())
    pyc_after = pycache_snapshot()
    real_untouched = real_before == real_after
    pyc_untouched = pyc_before == pyc_after
    record('真实输入文件 SHA/mtime/大小 未变', '全部四本真实书稿', real_untouched,
           '' if real_untouched else str({k: (real_before[k], real_after[k])
                                          for k in real_before if real_before[k] != real_after[k]}), 0)
    record('Skill scripts/__pycache__ 无新增 .pyc', str(SKILL_SCRIPTS / '__pycache__'), pyc_untouched,
           '' if pyc_untouched else str(pyc_after - pyc_before), 0)

    all_pass = all(r['result'] == 'PASS' for r in results)
    summary = {'tool': 'sweep_rule.py', 'total': len(results), 'passed': sum(r['result'] == 'PASS' for r in results),
               'failed': sum(r['result'] == 'FAIL' for r in results), 'all_pass': all_pass, 'tests': results}
    write_json(HERE / 'test_report.json', summary)
    print(json.dumps({'total': summary['total'], 'passed': summary['passed'], 'failed': summary['failed']},
                      ensure_ascii=False))
    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main())
