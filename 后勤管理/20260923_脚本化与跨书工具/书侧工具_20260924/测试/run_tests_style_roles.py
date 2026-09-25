#!/usr/bin/env python3
"""style_roles.py 的可重跑测试。所有产出只写系统临时目录（本文件所在的 booktools3/style_roles 下，
或更深的临时子目录），绝不写回任何真实书稿目录；真实输入一律先复制成副本再改。

用法：/usr/bin/python3 run_tests_style_roles.py [--keep]
    --keep 不清理本次跑测生成的临时 docx（默认跑完删除，只留 JSON 报告方便复核）。

跑之前会记录用到的真实输入文件的 SHA256 与 mtime，跑完再核对一遍，证明测试过程没有改动它们
（读取用 shutil.copy2 独立复制一份，从不对原路径做任何写操作）。
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPTS = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts')
TOOL = SCRIPTS / 'style_roles.py'
PY = '/usr/bin/python3'
# 输出一律写系统临时目录，不写到本脚本所在目录——这份文件可能被复制进项目里的“测试/”目录留档，
# 那里在受保护根之内，guard_write 只放行 …/协作/候选/<谁>/<批次>/构建/，写测试产物会被正确拒绝。
WORK = Path(tempfile.mkdtemp(prefix='style_roles_tests_'))
ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
DOG = Path('/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----'
           '/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/crossbook_dogfood')

REAL_INPUTS = {
    'b3_52': ROOT / '00_必修三最新审查稿/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx',
    'b2_230': ROOT / '必修二_周六成品冲刺_20260910/工作稿/修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.docx',
    'xuanbi2': Path('/Users/wanglifei/Desktop/2026模拟题/选必二_v15.0续作_20260908/工作稿/'
                     '选必二法律与生活宝典_v15.0_出版校订稿_20260908_r22.docx'),
    'philosophy': Path('/Users/wanglifei/GaokaoPolitics/Codex的北京高考政治/必修四哲学续作_20260908/'
                        '交付/哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx'),
}
RESULTS = []


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def snapshot_inputs():
    return {k: (sha256(p), p.stat().st_mtime) for k, p in REAL_INPUTS.items() if p.exists()}


def run(args, timeout=600):
    t0 = time.time()
    r = subprocess.run([PY, str(TOOL)] + args, capture_output=True, text=True, timeout=timeout)
    return r, time.time() - t0


def record(name, ok, detail, seconds):
    RESULTS.append({'input': name, 'result': 'PASS' if ok else 'FAIL', 'detail': detail, 'seconds': round(seconds, 2)})
    print(('PASS' if ok else 'FAIL') + f' - {name} ({seconds:.1f}s): {detail}')


def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def main():
    keep = '--keep' in sys.argv
    before = snapshot_inputs()
    print(f'临时工作目录：{WORK}')

    # ---- 准备副本 ----
    xuanbi2_docx = WORK / 'xuanbi2.docx'
    shutil.copy2(REAL_INPUTS['xuanbi2'], xuanbi2_docx)
    xuanbi2_prof = WORK / 'xuanbi2.profile.json'
    shutil.copy2(DOG / 'xuanbi2.draft.json', xuanbi2_prof)

    b3_52_docx = WORK / 'b3_52.docx'
    shutil.copy2(REAL_INPUTS['b3_52'], b3_52_docx)

    b2_230_docx = WORK / 'b2_230.docx'
    shutil.copy2(REAL_INPUTS['b2_230'], b2_230_docx)

    phil_docx = WORK / 'philosophy.docx'
    shutil.copy2(REAL_INPUTS['philosophy'], phil_docx)
    phil_prof = WORK / 'philosophy.profile.json'
    shutil.copy2(DOG / 'philosophy.draft.json', phil_prof)

    # ---- ① 选必二 r22：audit(52) -> plan -> apply -> 体检误蓝降到 0，全书文字不变 ----
    audit_json = WORK / 'xuanbi2.audit.json'
    t0 = time.time()
    r, secs = run(['audit', '--docx', str(xuanbi2_docx), '--profile', str(xuanbi2_prof), '--report', str(audit_json)])
    rep = load_json(audit_json) if audit_json.exists() else {}
    n52 = rep.get('summary', {}).get('by_rule_paragraphs', {}).get('teach_mis_blue')
    record('① xuanbi2 audit 教学正文误蓝段落数', n52 == 52 and r.returncode == 1, f'exit={r.returncode} 段落数={n52}（应为52）', secs)

    plan_json = WORK / 'xuanbi2.plan.json'
    r, secs = run(['plan', '--docx', str(xuanbi2_docx), '--audit', str(audit_json), '--rules', 'teach_mis_blue',
                   '--out', str(plan_json), '--profile', str(xuanbi2_prof)])
    plan = load_json(plan_json) if plan_json.exists() else {}
    # 2026-09-24 返修 issue（minor）：计划非空按“check 语义”退出 1（文件头“生成的计划为空 → 0”，
    # 非空应为 1；旧代码写反了，这里改成断言修好后的行为）。
    record('① xuanbi2 plan', r.returncode == 1 and plan.get('summary', {}).get('ops', 0) > 0,
           f'exit={r.returncode} ops={plan.get("summary")}', secs)

    fixed_docx = WORK / 'xuanbi2.fixed.docx'
    apply_json = WORK / 'xuanbi2.apply.json'
    if fixed_docx.exists():
        fixed_docx.unlink()
    r, secs = run(['apply', '--docx', str(xuanbi2_docx), '--plan', str(plan_json), '--out', str(fixed_docx),
                   '--profile', str(xuanbi2_prof), '--report', str(apply_json)])
    apply_rep = load_json(apply_json) if apply_json.exists() else {}
    ok_apply = r.returncode == 0 and fixed_docx.exists() and apply_rep.get('postcheck', {}).get('ok')
    record('① xuanbi2 apply（rPr-only，写后自核）', ok_apply, f'exit={r.returncode} postcheck={apply_rep.get("postcheck")}', secs)

    # 体检交叉核对：教学正文误蓝应降到 0，其余 FAIL 不因本工具变化
    if fixed_docx.exists():
        sys.path.insert(0, str(SCRIPTS))
        import importlib
        bh = importlib.import_module('batch_health')
        t0 = time.time()
        before_health = bh.run_health(str(xuanbi2_docx), profile=str(xuanbi2_prof))
        after_health = bh.run_health(str(fixed_docx), profile=str(xuanbi2_prof))
        secs = time.time() - t0

        def count(rep_, rule):
            return sum(1 for f in rep_['findings'] if f.get('check') == 'blue' and f.get('rule') == rule)
        b_n, a_n = count(before_health, '教学正文误蓝'), count(after_health, '教学正文误蓝')
        b_fail, a_fail = before_health['summary']['FAIL'], after_health['summary']['FAIL']
        # 全书文字逐段一致
        docx_lib = importlib.import_module('docx_lib')
        d1 = docx_lib.open_docx(str(xuanbi2_docx))
        d2 = docx_lib.open_docx(str(fixed_docx))
        text_ok = len(d1.items) == len(d2.items) and all(a['text'] == b_['text'] for a, b_ in zip(d1.items, d2.items))
        ok = a_n == 0 and (b_fail - a_fail) == (b_n - a_n) and text_ok
        record('① xuanbi2 batch_health 交叉核对（误蓝FAIL降到0，其余FAIL不变，全书文字不变）', ok,
               f'教学正文误蓝 {b_n}->{a_n}；总FAIL {b_fail}->{a_fail}；文字逐段一致={text_ok}', secs)

    # ---- ② 必修三第52批：audit 只读，应与 bh.check_blue 结论一致（基本干净） ----
    audit2_json = WORK / 'b3_52.audit.json'
    r, secs = run(['audit', '--docx', str(b3_52_docx), '--profile', 'bixiu3', '--report', str(audit2_json)])
    rep2 = load_json(audit2_json) if audit2_json.exists() else {}
    n_blue = rep2.get('summary', {}).get('by_rule_paragraphs', {}).get('teach_mis_blue', 0)
    sys.path.insert(0, str(SCRIPTS))
    import importlib
    bh = importlib.import_module('batch_health')
    bh_rep = bh.run_health(str(b3_52_docx), profile='bixiu3')
    bh_n = sum(1 for f in bh_rep['findings'] if f.get('check') == 'blue' and f.get('rule') == '教学正文误蓝')
    record('② 必修三52批 audit 教学正文误蓝 与 bh.check_blue 一致', n_blue == bh_n,
           f'style_roles={n_blue} bh={bh_n}（exit={r.returncode}，其余偏差见报告 by_rule_paragraphs={rep2.get("summary",{}).get("by_rule_paragraphs")}）', secs)

    # ---- ③ 必修二修订230：audit 只读可跑；apply 对真实冻结路径必须拒绝（只读，不写真实文件） ----
    audit3_json = WORK / 'b2_230.audit.json'
    r, secs = run(['audit', '--docx', str(b2_230_docx), '--profile', 'bixiu2', '--report', str(audit3_json)])
    rep3 = load_json(audit3_json) if audit3_json.exists() else {}
    record('③ 必修二230 audit 只读可跑', r.returncode in (0, 1) and 'summary' in rep3,
           f'exit={r.returncode} summary={rep3.get("summary")}', secs)

    plan3_json = WORK / 'b2_230.plan.json'
    run(['plan', '--docx', str(b2_230_docx), '--audit', str(audit3_json), '--rules', 'teach_mis_blue',
         '--out', str(plan3_json), '--profile', 'bixiu2'])
    bogus_out = WORK / '__should_not_appear__.docx'
    if bogus_out.exists():
        bogus_out.unlink()
    t0 = time.time()
    r = subprocess.run([PY, str(TOOL), 'apply', '--docx', str(REAL_INPUTS['b2_230']), '--plan', str(plan3_json),
                        '--out', str(bogus_out), '--profile', 'bixiu2'], capture_output=True, text=True)
    secs = time.time() - t0
    record('③ 必修二230 apply 对真实冻结路径拒绝（退出码3，不留输出）', r.returncode == 3 and not bogus_out.exists(),
           f'exit={r.returncode} stderr={r.stderr.strip()[:80]}', secs)

    # ---- ④ 哲学 R10：audit 只读，列出各类偏差计数 ----
    audit4_json = WORK / 'philosophy.audit.json'
    r, secs = run(['audit', '--docx', str(phil_docx), '--profile', str(phil_prof), '--report', str(audit4_json)])
    rep4 = load_json(audit4_json) if audit4_json.exists() else {}
    record('④ 哲学R10 audit 只读列出各类计数', 'summary' in rep4 and bool(rep4.get('summary', {}).get('by_rule_paragraphs')),
           f'exit={r.returncode} by_rule_paragraphs={rep4.get("summary",{}).get("by_rule_paragraphs")}', secs)

    # ==================================================================
    # 2026-09-24 对抗性审查（verify_style_roles.json）返修后新增的回归用例
    # ==================================================================

    # ---- ⑥ blocker：material_font/stem_teaching_font 在已定稿书上不再误报 fixable，
    #        没有登记 typography.<角色>.rules 时禁止为它们生成计划 ----
    n_material = rep2.get('summary', {}).get('by_rule_runs', {}).get('material_font', 0)
    record('⑥ b3_52 material_font 不再产生误报（fixable_runs 恒 0）', rep2.get('summary', {}).get('fixable_runs') == 0,
           f'material_font命中={n_material}（应远大于0，属CANDIDATE观测） fixable_runs={rep2.get("summary",{}).get("fixable_runs")}（应为0）', 0)
    plan6_json = WORK / 'b3_52.matfont.plan.json'
    r, secs = run(['plan', '--docx', str(b3_52_docx), '--audit', str(audit2_json), '--rules', 'material_font',
                   '--out', str(plan6_json), '--profile', 'bixiu3'])
    record('⑥ b3_52 没有角色表时 plan material_font 被拒绝（退出码2，不留输出）',
           r.returncode == 2 and not plan6_json.exists(), f'exit={r.returncode} stderr={r.stderr.strip()[:120]}', secs)
    role_cfg = rep2.get('role_config', {})
    record('⑥ audit 报告如实标注 material_font/stem_teaching_font 未登记角色表',
           role_cfg.get('material_font', {}).get('precise_rules') is False
           and role_cfg.get('stem_teaching_font', {}).get('precise_rules') is False,
           json.dumps(role_cfg, ensure_ascii=False), 0)

    # ---- ⑦ major：蓝色来自“全书一贯设计”的样式（哲学“错肢分组”标题）不机械修复，
    #        plan 应得到 0 ops（旧代码会生成 1 个错误的 plan） ----
    n52_phil_paras = rep4.get('summary', {}).get('by_rule_paragraphs', {}).get('teach_mis_blue')
    fixable4 = rep4.get('summary', {}).get('fixable_runs')
    record('⑦ 哲学R10 “错肢分组”样式误蓝不再判 fixable', fixable4 == 0,
           f'teach_mis_blue段落数={n52_phil_paras}（应为1） fixable_runs={fixable4}（应为0，旧代码是1）', 0)
    plan7_json = WORK / 'philosophy.blue.plan.json'
    r, secs = run(['plan', '--docx', str(phil_docx), '--audit', str(audit4_json), '--rules', 'teach_mis_blue',
                   '--out', str(plan7_json), '--profile', str(phil_prof)])
    plan7 = load_json(plan7_json) if plan7_json.exists() else {}
    record('⑦ 哲学R10 teach_mis_blue plan 得到 0 ops（不再误修分组标题）',
           r.returncode == 0 and plan7.get('summary', {}).get('ops') == 0,
           f'exit={r.returncode} summary={plan7.get("summary")}', secs)

    # ---- ⑧ major：themeColor 感知——audit 仍能确认判定（val 存在），apply 写入后把
    #        themeColor 一并删除，不会出现“判定已修好、Word 里仍显蓝”的假阳性 ----
    sys.path.insert(0, str(SCRIPTS))
    import importlib
    dl = importlib.import_module('docx_lib')
    sr = importlib.import_module('style_roles')
    from lxml import etree as _ET
    W = bh.W
    theme_docx = WORK / 'xuanbi2_theme.docx'
    d_theme = dl.open_docx(str(xuanbi2_docx))
    r78 = sr._run_list(d_theme.paras[78])
    rpr78 = sr._rpr_ensure(r78[2])
    c78 = rpr78.find(W + 'color')
    if c78 is None:
        c78 = sr._rpr_insert(rpr78, 'color', lambda e: None)
    c78.set(W + 'val', '1F4E79')
    c78.set(W + 'themeColor', 'accent1')
    if theme_docx.exists():
        theme_docx.unlink()
    dl.write_docx(d_theme, str(theme_docx))
    theme_audit_json = WORK / 'xuanbi2_theme.audit.json'
    r, secs = run(['audit', '--docx', str(theme_docx), '--profile', str(xuanbi2_prof), '--report', str(theme_audit_json)])
    theme_rep = load_json(theme_audit_json) if theme_audit_json.exists() else {}
    hit78 = next((f for f in theme_rep.get('findings', []) if f['rule'] == 'teach_mis_blue' and f['para'] == 78 and f['run'] == 2), None)
    record('⑧ 带 themeColor 的蓝字：val 明确时 audit 仍判 fixable', bool(hit78 and hit78.get('fixable')),
           f'hit={hit78}', secs)
    theme_plan_json = WORK / 'xuanbi2_theme.plan.json'
    run(['plan', '--docx', str(theme_docx), '--audit', str(theme_audit_json), '--rules', 'teach_mis_blue',
         '--out', str(theme_plan_json), '--profile', str(xuanbi2_prof)])
    theme_out = WORK / 'xuanbi2_theme.out.docx'
    if theme_out.exists():
        theme_out.unlink()
    t0 = time.time()
    r = subprocess.run([PY, str(TOOL), 'apply', '--docx', str(theme_docx), '--plan', str(theme_plan_json),
                        '--out', str(theme_out), '--profile', str(xuanbi2_prof), '--no-health'],
                       capture_output=True, text=True)
    secs = time.time() - t0
    theme_ok = False
    if r.returncode == 0 and theme_out.exists():
        d_out = dl.open_docx(str(theme_out))
        rr = sr._run_list(d_out.paras[78])[2]
        c = rr.find(W + 'rPr').find(W + 'color')
        theme_ok = c.get(W + 'val') != '1F4E79' and c.get(W + 'themeColor') is None
    record('⑧ apply 修蓝字时一并删除 themeColor（不再出现“判已修好、Word仍显蓝”）', theme_ok,
           f'exit={r.returncode}', secs)

    # ---- ⑨ major：apply 不再信任 plan 文件里的 after——颜色改任意值/混入 bold/非法颜色值/
    #        重复指名同一 run，一律独立重算校验，中止且不留输出 ----
    if plan_json.exists():
        base_plan = json.loads(plan_json.read_text(encoding='utf-8'))

        def neg_apply(name, mutate):
            p_ = json.loads(json.dumps(base_plan))
            mutate(p_)
            path_ = WORK / f'{name}.plan.json'
            path_.write_text(json.dumps(p_, ensure_ascii=False), encoding='utf-8')
            out_ = WORK / f'{name}.out.docx'
            if out_.exists():
                out_.unlink()
            t0_ = time.time()
            rr = subprocess.run([PY, str(TOOL), 'apply', '--docx', str(xuanbi2_docx), '--plan', str(path_),
                                 '--out', str(out_), '--profile', str(xuanbi2_prof), '--no-health'],
                                capture_output=True, text=True)
            secs_ = time.time() - t0_
            record(f'⑨ 负例：{name}', rr.returncode == 2 and not out_.exists(),
                   f'exit={rr.returncode} stderr={rr.stderr.strip()[:100]}', secs_)

        neg_apply('neg_red_color', lambda p_: p_['ops'].__setitem__(0, {**p_['ops'][0], 'after': {'color': 'FF0000'}}))
        neg_apply('neg_bold_field', lambda p_: p_['ops'].__setitem__(0, {**p_['ops'][0], 'after': {'color': '222222', 'bold': True}}))
        neg_apply('neg_illegal_color', lambda p_: p_['ops'].__setitem__(0, {**p_['ops'][0], 'after': {'color': 'auto"/><w:t>x'}}))
        neg_apply('neg_dup_run', lambda p_: p_['ops'].append(dict(p_['ops'][0])))

    # ---- ⑩ minor：报告只允许覆盖“本工具生成、mode与docx_sha256都相同”的旧文件——
    #        plan --out 指向另一份 audit 报告不会被静默覆盖 ----
    other_audit = WORK / 'other.audit.json'
    shutil.copy2(audit_json, other_audit)
    r = subprocess.run([PY, str(TOOL), 'plan', '--docx', str(xuanbi2_docx), '--audit', str(audit_json),
                        '--rules', 'teach_mis_blue', '--out', str(other_audit), '--profile', str(xuanbi2_prof)],
                       capture_output=True, text=True)
    other_mode = load_json(other_audit).get('mode') if other_audit.exists() else None
    record('⑩ plan --out 指向别的 audit 报告时拒绝覆盖（退出码3，内容不变）',
           r.returncode == 3 and other_mode == 'audit', f'exit={r.returncode} mode仍为={other_mode}', 0)

    # ---- ⑪ minor：drill_color 类别改用 bh_rule 白名单，不再靠“红/绿/颜色/纠正”几个字猜——
    #        覆盖 A2 表内正误不齐（不含这几个字，旧写法会漏掉） ----
    drill_findings = [f for f in rep4.get('findings', []) if f.get('bh_rule')]
    all_drill_category_renamed = all(f['rule'] == 'drill_color' for f in drill_findings)
    record('⑪ drill_color 类别已改名（不再叫 drill_color_misplace）',
           all_drill_category_renamed and 'drill_color' in {f['rule'] for f in drill_findings},
           f'样本={drill_findings[:2]}', 0)
    record('⑪ 白名单包含 A2 表内正误不齐（旧“红/绿/颜色/纠正”关键词匹配会漏掉这条）',
           'A2 表内正误不齐' in sr.DRILL_COLOR_RULES, str(sorted(sr.DRILL_COLOR_RULES)), 0)

    # ---- ⑫ major：apply --health 默认开启，按 (check, rule) 逐门比较，任何门新增 FAIL 都
    #        中止并删除输出（不是只比总数）——用打桩隔离，不依赖真的能在真书上造出回归 ----
    def _fail_map_rows(rows):
        return {'gates': [], 'summary': {'FAIL': sum(x['count'] for x in rows if x['level'] == 'FAIL')},
                'findings_by_rule': rows}

    before_rows = [{'check': 'blue', 'level': 'FAIL', 'rule': '教学正文误蓝', 'count': 52, 'shown': 52},
                   {'check': 'columns', 'level': 'FAIL', 'rule': '栏目缺失或重复', 'count': 146, 'shown': 60}]
    after_rows_ok = [{'check': 'blue', 'level': 'FAIL', 'rule': '教学正文误蓝', 'count': 0, 'shown': 0},
                      {'check': 'columns', 'level': 'FAIL', 'rule': '栏目缺失或重复', 'count': 146, 'shown': 60}]
    after_rows_regress = after_rows_ok + [{'check': 'blue', 'level': 'FAIL', 'rule': '答案落点疑似蓝字残留', 'count': 3, 'shown': 3}]

    class _FakeArgs:
        pass

    def run_health_gated(seq, expect_ok, label):
        out12 = WORK / f'health_gate_{label}.docx'
        rep12 = WORK / f'health_gate_{label}.json'
        for p_ in (out12, rep12):
            if p_.exists():
                p_.unlink()
        a = _FakeArgs()
        a.docx, a.plan, a.out = str(xuanbi2_docx), str(plan_json), str(out12)
        a.expect_sha, a.profile, a.report, a.health = None, str(xuanbi2_prof), str(rep12), True
        calls = {'n': 0}
        real = bh.run_health

        def fake(path, profile=None, **kw):
            calls['n'] += 1
            return seq[calls['n'] - 1]
        bh.run_health = fake
        try:
            rc = sr.cmd_apply(a)
        finally:
            bh.run_health = real
        ok_ = (rc == (0 if expect_ok else 1)) and (out12.exists() == expect_ok)
        record(f'⑫ apply --health 按门比较（{label}）', ok_,
               f'rc={rc}（期望{0 if expect_ok else 1}） 输出存在={out12.exists()}（期望{expect_ok}）', 0)

    if plan_json.exists():
        run_health_gated([_fail_map_rows(before_rows), _fail_map_rows(after_rows_ok)], True, 'improve')
        run_health_gated([_fail_map_rows(before_rows), _fail_map_rows(after_rows_regress)], False, 'regress')

    # ---- ⑬ blocker 的正向路径：登记了显式 typography.material.rules（按 kind 细分）后，
    #        material_font 能精确判定、能生成计划、apply 真的把 rFonts 写对（顺带测出了旧代码
    #        w:ea 而不是 w:eastAsia 的写属性名 bug——写字体从没真正生效过）----
    b3_prof_path = SCRIPTS / 'profiles' / 'bixiu3.json'
    rules_prof = WORK / 'bixiu3_with_rules.json'
    prof13 = json.loads(b3_prof_path.read_text(encoding='utf-8'))
    prof13.setdefault('typography', {}).setdefault('material', {})['rules'] = [
        {'kind': ['choice'], 'styles': ['题目材料', '题目设问', '题目选项'],
         'ea': 'Songti SC', 'ascii': 'Times New Roman', 'pt': 10.5},
    ]
    rules_prof.write_text(json.dumps(prof13, ensure_ascii=False), encoding='utf-8')

    audit13a_json = WORK / 'b3_52.rules.audit.json'
    r, secs = run(['audit', '--docx', str(b3_52_docx), '--profile', str(rules_prof), '--report', str(audit13a_json)])
    rep13a = load_json(audit13a_json) if audit13a_json.exists() else {}
    record('⑬ 登记显式 rules 后，选择题题干（Songti，符合协议）不再被误报',
           rep13a.get('summary', {}).get('fixable_runs') == 0
           and rep13a.get('role_config', {}).get('material_font', {}).get('precise_rules') is True,
           f'summary={rep13a.get("summary")}', secs)

    # 制造一个真偏差：把一个选择题题干 run 的字体改成 Kaiti SC（协议要求 Songti），验证能测出、能修好
    d13 = dl.open_docx(str(b3_52_docx))
    from profile_lib import load_profile as _load_profile
    P13 = bh.Prof(_load_profile(str(rules_prof)))
    bh.walk(d13.items, P13)
    target13 = None
    for it in d13.items:
        if it['style'] == '题目材料' and it.get('ex') and it['ex'].get('kind') == 'choice' and it['text']:
            p_ = d13.paras[it['i']]
            for rr in sr._run_list(p_):
                t_ = sr._run_raw_text(rr)
                if sr.CJK.search(t_) and (sr._style_table(d13).run_format(p_, rr).get('ea') or '') == 'Songti SC':
                    target13 = (it['i'], rr)
                    break
        if target13:
            break
    mut13_docx = WORK / 'b3_52_mut.docx'
    if target13:
        pi13, r13 = target13
        r13.find(W + 'rPr').find(W + 'rFonts').set(W + 'eastAsia', 'Kaiti SC')
        if mut13_docx.exists():
            mut13_docx.unlink()
        dl.write_docx(d13, str(mut13_docx))
        audit13b_json = WORK / 'b3_52_mut.audit.json'
        run(['audit', '--docx', str(mut13_docx), '--profile', str(rules_prof), '--report', str(audit13b_json)])
        rep13b = load_json(audit13b_json)
        hit13 = next((f for f in rep13b['findings'] if f['rule'] == 'material_font' and f['para'] == pi13), None)
        record('⑬ 人为制造的选择题题干字体偏差被精确判定为 fixable',
               bool(hit13 and hit13.get('fixable') and hit13['after'].get('ea') == 'Songti SC'), f'hit={hit13}', 0)
        plan13_json = WORK / 'b3_52_mut.plan.json'
        run(['plan', '--docx', str(mut13_docx), '--audit', str(audit13b_json), '--rules', 'material_font',
             '--out', str(plan13_json), '--profile', str(rules_prof)])
        fixed13_docx = WORK / 'b3_52_mut.fixed.docx'
        if fixed13_docx.exists():
            fixed13_docx.unlink()
        r13res = subprocess.run([PY, str(TOOL), 'apply', '--docx', str(mut13_docx), '--plan', str(plan13_json),
                                  '--out', str(fixed13_docx), '--profile', str(rules_prof), '--no-health'],
                                 capture_output=True, text=True)
        fixed_ok = False
        if r13res.returncode == 0 and fixed13_docx.exists():
            d13f = dl.open_docx(str(fixed13_docx))
            r13f = sr._run_list(d13f.paras[pi13])[0]
            fixed_ok = r13f.find(W + 'rPr').find(W + 'rFonts').get(W + 'eastAsia') == 'Songti SC'
        record('⑬ apply 真的把 rFonts eastAsia 写对（旧代码写成不存在的 w:ea 属性，从未生效）',
               fixed_ok, f'exit={r13res.returncode}', 0)
    else:
        record('⑬ 未找到可制造偏差的选择题题干样本（跳过，非 FAIL）', True, '样本未命中', 0)

    # ---- ⑤ 负例：run 文字不符 / after 想改文字 / 父稿 SHA 不符，均中止不留输出 ----
    if plan_json.exists():
        bad_a = json.loads(plan_json.read_text(encoding='utf-8'))
        bad_a['ops'][0]['text'] = '__不匹配的文字__'
        bad_a_path = WORK / 'neg_a.plan.json'
        bad_a_path.write_text(json.dumps(bad_a, ensure_ascii=False), encoding='utf-8')
        out_a = WORK / 'neg_a_out.docx'
        if out_a.exists():
            out_a.unlink()
        t0 = time.time()
        r = subprocess.run([PY, str(TOOL), 'apply', '--docx', str(xuanbi2_docx), '--plan', str(bad_a_path),
                            '--out', str(out_a), '--profile', str(xuanbi2_prof)], capture_output=True, text=True)
        secs = time.time() - t0
        record('⑤ 负例：run 文字与当前稿不符', r.returncode == 2 and not out_a.exists(), f'exit={r.returncode}', secs)

        bad_b = json.loads(plan_json.read_text(encoding='utf-8'))
        bad_b['ops'][0]['after'] = {'text': '想改的新文字'}
        bad_b_path = WORK / 'neg_b.plan.json'
        bad_b_path.write_text(json.dumps(bad_b, ensure_ascii=False), encoding='utf-8')
        out_b = WORK / 'neg_b_out.docx'
        if out_b.exists():
            out_b.unlink()
        t0 = time.time()
        r = subprocess.run([PY, str(TOOL), 'apply', '--docx', str(xuanbi2_docx), '--plan', str(bad_b_path),
                            '--out', str(out_b), '--profile', str(xuanbi2_prof)], capture_output=True, text=True)
        secs = time.time() - t0
        record('⑤ 负例：计划 after 想改文字（不支持字段）', r.returncode == 2 and not out_b.exists(), f'exit={r.returncode}', secs)

    if fixed_docx.exists() and plan_json.exists():
        out_c = WORK / 'neg_c_out.docx'
        if out_c.exists():
            out_c.unlink()
        t0 = time.time()
        r = subprocess.run([PY, str(TOOL), 'apply', '--docx', str(fixed_docx), '--plan', str(plan_json),
                            '--out', str(out_c), '--profile', str(xuanbi2_prof)], capture_output=True, text=True)
        secs = time.time() - t0
        record('⑤ 负例：父稿 SHA 不符', r.returncode == 2 and not out_c.exists(), f'exit={r.returncode}', secs)

    # ---- 收尾：真实输入未变；__pycache__ 无新增 ----
    after = snapshot_inputs()
    unchanged = all(before.get(k) == after.get(k) for k in REAL_INPUTS)
    record('真实书稿 SHA/mtime 全程未变', unchanged, json.dumps({k: (before.get(k) == after.get(k)) for k in REAL_INPUTS}, ensure_ascii=False), 0)
    pyc = SCRIPTS / '__pycache__'
    has_style_roles_pyc = pyc.exists() and any('style_roles' in p.name for p in pyc.iterdir())
    record('Skill 目录 __pycache__ 无 style_roles 字节码', not has_style_roles_pyc, str(pyc), 0)

    if not keep:
        for f in WORK.glob('*.docx'):
            try:
                f.unlink()
            except OSError:
                pass

    n_fail = sum(1 for r_ in RESULTS if r_['result'] == 'FAIL')
    print(f'\n共 {len(RESULTS)} 项，{n_fail} 项 FAIL')
    result_path = WORK / 'test_results.json'
    result_path.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'明细：{result_path}')
    return 1 if n_fail else 0


if __name__ == '__main__':
    sys.exit(main())
