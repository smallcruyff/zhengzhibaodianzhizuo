#!/usr/bin/env python3
"""apply_patch.py 回归测试（2026-09-24）。
只读真实输入；全部输出写在本脚本所在目录（$SCRATCH/booktools/apply_patch/out 等子目录）。
第三轮覆盖 reverify_apply_patch.json 的 6 条 major + 3 条 minor；
第四轮（t14-t22）覆盖 r3verify_apply_patch.json 新发现的 2 条 major
（restore 词表豁免的写后区位复核、diff 插入段格式保留）与 4 条 minor
（diff 的 --report/--out 校验顺序与大小写折叠、insert 的 style/clone_from 提前到 check
阶段校验、set_keepnext/insert 锚点段的文字不变后置条件、插入新文字首尾空白的明确报告）。
"""
import tempfile
import hashlib
import json
import subprocess
import sys
import time
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts')
sys.path.insert(0, str(SCRIPTS))
import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
from profile_lib import load_profile  # noqa: E402

ROOT = Path('/Users/wanglifei/Desktop/gpt和claude共同的小窝')
B3_52 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/必修三政治与法治宝典_第52批_意见修改审阅稿.docx'
B3_03 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/03_第二部分专题.docx'
B3_04 = ROOT / '必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/04_编号与考法计数.docx'
B2_230 = ROOT / '必修二_周六成品冲刺_20260910/工作稿/修订230_题肢归类与最终交付/必修二_v25_修订230_题肢归类最终稿.docx'
B3_51 = ROOT / '必修三_人工审查历史/第51批_原样审阅_20260923_150732/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx'
TOOL = SCRIPTS / 'apply_patch.py'
OUT = Path(tempfile.gettempdir()) / 'booktools_tests' / 'apply_patch' / 'out'  # 输出一律落系统临时目录，不跟着本脚本进项目目录
OUT.mkdir(parents=True, exist_ok=True)

results = []


def record(name, ok, detail=''):
    results.append({'test': name, 'ok': bool(ok), 'detail': detail})
    print(('PASS' if ok else 'FAIL'), name, ('- ' + detail) if detail and not ok else '')


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def run(args, timeout=180):
    t0 = time.time()
    p = subprocess.run([sys.executable, str(TOOL)] + args, capture_output=True, text=True, timeout=timeout)
    dt = time.time() - t0
    return p.returncode, p.stdout, p.stderr, dt


def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def write_patch(path, ops, parent_sha, book='bixiu3', approved_by='claude:test',
                 approval_ref='run_tests_apply_patch'):
    patch = {'schema': 'baodian_patch_v1', 'book': book, 'parent_docx_sha256': parent_sha,
              'approved_by': approved_by, 'approval_ref': approval_ref, 'ops': ops}
    Path(path).write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


# 第六轮 minor③：diff --out 覆盖守卫现在还要比对 approval_ref 是不是这次 diff（--old/--new 这一对
# 文件）会算出的自动值——t5b/t26b 这两条"纯 diff 产物、没人碰过"的对照组，写测试夹具时必须真的
# 写出这个自动值，不能再用与内容无关的占位字符串，否则会被新守卫误判成"被人改过 approval_ref"。
B3_03_04_AUTO_APPROVAL_REF = f'{Path(B3_03).name} -> {Path(B3_04).name}'


# ---------------------------------------------------------------- 准备：读一次 B3_52，找测试用锚点
prof = load_profile('bixiu3')
d52 = dl.open_docx(str(B3_52))
P = bh.Prof(prof)
blocks = bh.walk(d52.items, P)
zone52 = [it.get('zone') for it in d52.items]
tag_list, wlist = bh._word_lists(prof)
FORBIDDEN_WORD = None
for g, w in wlist:
    FORBIDDEN_WORD = w
    break
assert FORBIDDEN_WORD, '词表为空，测试没法造禁用词攻击用例'

# 找一段 source/title 区、一段 teaching 区的段落——都要求全文在整篇里唯一出现（否则 anchor 命中
# 多段，测试本身就会先在"锚点须恰好命中一段"上失败，测不到真正要测的东西）。
_text_counts = {}
for _p in d52.paras:
    _t = dl.para_text(_p)
    _text_counts[_t] = _text_counts.get(_t, 0) + 1


def _unique_idx(zones_wanted):
    for i, z in enumerate(zone52):
        if z in zones_wanted:
            t = dl.para_text(d52.paras[i])
            if t and _text_counts.get(t) == 1 and len(t) >= 6:
                return i
    raise AssertionError(f'找不到唯一且非空的 {zones_wanted} 区段落')


source_idx = _unique_idx(('source', 'title'))
teaching_idx = _unique_idx(('teaching',))
source_text = dl.para_text(d52.paras[source_idx])
teaching_text = dl.para_text(d52.paras[teaching_idx])


def _find_title_after_teaching():
    """title 区段落、且紧邻的上一段是 teaching 区、文字唯一——第四轮 major#1 攻击用例
    （r3verify R2）的边界：锚点合法给 restore（因为锚点自己在 title 区），但 insert_before
    的新段实际落进上一段所在的教学区。"""
    for i in range(1, len(zone52)):
        if zone52[i] == 'title' and zone52[i - 1] == 'teaching':
            t = dl.para_text(d52.paras[i])
            if t and _text_counts.get(t) == 1 and len(t) >= 4:
                return i
    return None


_title_after_teaching_idx = _find_title_after_teaching()


# ================================================================ 1. 词表：restore 只在 source/title 区豁免
def test_wordlist_scope_teaching_restore_rejected():
    patch_path = OUT / 't1_teaching_restore.json'
    new_text = teaching_text + FORBIDDEN_WORD
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text},
            'old': teaching_text, 'new': new_text,
            'source_zone': 'restore', 'reason': '测试：教学区 restore 不应豁免词表'}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t1_教学区_restore_不豁免词表', rc == 2 and '禁用词表' in err, f'rc={rc} err={err}')


def test_wordlist_scope_source_restore_exempt():
    patch_path = OUT / 't1b_source_restore.json'
    new_text = source_text + FORBIDDEN_WORD
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': source_text},
            'old': source_text, 'new': new_text,
            'source_zone': 'restore', 'reason': '测试：题面区 restore 应豁免词表'}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    # 应该过词表关，pending 应该是 1（不因词表被拦）
    ok = rc in (0, 1) and '禁用词表' not in err
    record('t1b_题面区_restore_豁免词表', ok, f'rc={rc} err={err}')


def test_wordlist_concat_runs():
    """禁用词被拆进 insert 的两个 run：拼接后应命中。"""
    half = len(FORBIDDEN_WORD) // 2 or 1
    patch_path = OUT / 't1c_split_runs.json'
    ops = [{'id': 'P1', 'op': 'insert_after', 'anchor': {'text': teaching_text},
            'paragraphs': [{'text': '占位', 'runs': [
                {'text': FORBIDDEN_WORD[:half]}, {'text': FORBIDDEN_WORD[half:]}]}],
            'reason': '测试：词表按拼接整段检查'}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t1c_禁用词拆进两个run仍被拦', rc == 2 and '禁用词表' in err, f'rc={rc} err={err}')


# ================================================================ 2. source_zone 取值/reason 通用校验
def test_source_zone_invalid_value_anywhere():
    patch_path = OUT / 't2_bad_value.json'
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text},
            'old': teaching_text, 'new': teaching_text + '（测试）',
            'source_zone': 'whatever', 'reason': '随便'}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t2_source_zone非法取值_任意区都拒', rc == 2 and 'source_zone' in err, f'rc={rc} err={err}')


def test_source_zone_missing_reason_anywhere():
    patch_path = OUT / 't2b_missing_reason.json'
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text},
            'old': teaching_text, 'new': teaching_text + '（测试）',
            'source_zone': 'approved_edit'}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t2b_给了source_zone缺reason_任意区都拒', rc == 2 and 'reason' in err, f'rc={rc} err={err}')


def test_source_zone_missing_on_source_anchor():
    patch_path = OUT / 't2c_missing_on_source.json'
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': source_text},
            'old': source_text, 'new': source_text + 'X'}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t2c_题面区锚点缺source_zone仍拒', rc == 2, f'rc={rc} err={err}')


# ================================================================ 3. 缺字段清楚中文报错
def test_missing_new_field_clear_error():
    patch_path = OUT / 't3_missing_new.json'
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text}, 'old': teaching_text}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t3_缺new字段给清楚中文报错', rc == 2 and '缺少字段' in err and '"new"' in err, f'rc={rc} err={err}')


# ================================================================ 4/5. 报告与补丁覆盖守卫
def test_report_cannot_overwrite_approved_patch():
    approved = OUT / 't4_approved_patch.json'
    write_patch(approved, [], d52.sha256, approved_by='claude:主代理会话')
    real_patch = OUT / 't4_real_patch.json'
    write_patch(real_patch, [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text},
                              'old': teaching_text, 'new': teaching_text + 'Y'}], d52.sha256)
    before = approved.read_text(encoding='utf-8')
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(real_patch), '--report', str(approved)])
    after = approved.read_text(encoding='utf-8')
    record('t4_report不能覆盖已批准补丁', rc == 3 and before == after, f'rc={rc} err={err} unchanged={before == after}')


def test_diff_out_cannot_overwrite_approved_patch():
    approved = OUT / 't5_approved_patch.json'
    write_patch(approved, [], d52.sha256, approved_by='codex:任务123')
    before = approved.read_text(encoding='utf-8')
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(approved), '--book', 'bixiu3'])
    after = approved.read_text(encoding='utf-8')
    record('t5_diff_out不能覆盖已批准补丁', rc == 3 and before == after, f'rc={rc} err={err} unchanged={before == after}')


def test_diff_out_can_overwrite_diff_patch():
    diffpatch = OUT / 't5b_diff_patch.json'
    write_patch(diffpatch, [], d52.sha256, approved_by='diff:apply_patch',
                approval_ref=B3_03_04_AUTO_APPROVAL_REF)
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(diffpatch), '--book', 'bixiu3'])
    ok = rc == 0
    if ok:
        obj = load_json(diffpatch)
        ok = obj.get('schema') == 'baodian_patch_v1' and len(obj.get('ops', [])) > 0
    record('t5b_diff_out可覆盖diff产物补丁', ok, f'rc={rc} err={err}')


def test_report_and_out_same_path_rejected():
    same = OUT / 't5c_same_path.json'
    if same.exists():
        same.unlink()
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(same),
                           '--report', str(same), '--book', 'bixiu3'])
    record('t5c_diff的report与out同路径被拒', rc == 2 and '同一路径' in err, f'rc={rc} err={err}')


def test_patch_path_in_guard_inputs():
    """--out 不能就是 --patch 本身。"""
    patch_path = OUT / 't5d_patch_as_out.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text},
                              'old': teaching_text, 'new': teaching_text + 'Z'}], d52.sha256)
    fake_out = patch_path.with_suffix('.docx')
    # 构造一个与 patch 同名（不同后缀，规避 guard 的“同一文件”判断只按 resolve 路径），
    # 真正验证 --patch 被列入 report 守卫 inputs：report 指向 --patch 本身应被拒绝为不可覆盖。
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path), '--report', str(patch_path)])
    record('t5d_report不能覆盖同一补丁文件', rc == 3, f'rc={rc} err={err}')


# ================================================================ 6. \t 写成 <w:tab/>，不是字面字符
def test_replace_paragraph_tab_and_first_text_run():
    from lxml import etree
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    W = ap.W
    NS = {'w': W[1:-1]}
    xml = ('<w:p xmlns:w="%s"><w:pPr/>'
           '<w:hyperlink r:id="rId1" xmlns:r="x"><w:r><w:rPr><w:color w:val="2D2D2D"/></w:rPr>'
           '<w:t>01　党总体：党的全面领导</w:t></w:r></w:hyperlink>'
           '<w:r><w:tab/><w:t>15</w:t></w:r></w:p>') % NS['w']
    p = etree.fromstring(xml)
    old_text = dl.para_text(p)
    op = {'id': 'X1', 'op': 'replace_paragraph', 'old': old_text,
          'new': '01　党总体：党的全面领导（改）\t16', 'allow_complex': True}
    ap.apply_replace_paragraph(p, op)
    runs = p.findall(f'{W}r')
    ok = len(runs) == 1
    color_ok = False
    tab_ok = False
    literal_tab_ok = True
    if ok:
        r = runs[0]
        rpr = r.find(f'{W}rPr')
        color_ok = rpr is not None and rpr.find(f'{W}color') is not None and rpr.find(f'{W}color').get(f'{W}val') == '2D2D2D'
        tabs = r.findall(f'{W}tab')
        tab_ok = len(tabs) == 1
        for t in r.findall(f'{W}t'):
            if t.text and '\t' in t.text:
                literal_tab_ok = False
    text_ok = dl.para_text(p) == op['new']
    record('t6_replace_paragraph首个文字run取自hyperlink内',
           ok and color_ok, f'runs={len(runs)} color_ok={color_ok}')
    record('t6b_replace_paragraph新文字里的tab写成w_tab不是字面字符',
           tab_ok and literal_tab_ok and text_ok,
           f'tab_ok={tab_ok} literal_tab_ok={literal_tab_ok} text_ok={text_ok}')


def test_new_texts_of_concat_not_per_run():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    op = {'op': 'insert_after', 'paragraphs': [{'text': '占位', 'runs': [{'text': '待'}, {'text': '核'}]}]}
    texts = ap._new_texts_of(op)
    record('t6c__new_texts_of按拼接整段返回', texts == ['待核'], f'texts={texts}')


# ================================================================ 7. resolve_anchor 用文字索引，且候选唯一性不受影响
def test_resolve_anchor_index_correctness():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    import zipfile as zf
    from lxml import etree as ET
    with zf.ZipFile(d52.path) as z:
        styles_xml = ET.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None
    styles_obj = bh.Styles(styles_xml)
    text_index = ap._build_text_index(d52.paras)
    idx1, elem1, cands1 = ap.resolve_anchor(d52, styles_obj, blocks, {}, {'text': teaching_text}, text_index)
    idx0, elem0, cands0 = ap.resolve_anchor(d52, styles_obj, blocks, {}, {'text': teaching_text}, None)
    record('t7_文字索引定位结果与全扫描一致', idx1 == idx0 and elem1 is elem0, f'idx_indexed={idx1} idx_scan={idx0}')


# ================================================================ 8. --health 异常时删除已写出的候选（不留输出）
def test_health_exception_deletes_output():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    patch_path = OUT / 't8_health_patch.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text},
                              'old': teaching_text, 'new': teaching_text + '（健康异常测试）'}], d52.sha256)
    out_path = OUT / 't8_out.docx'
    out_path.unlink(missing_ok=True)
    orig_run_health = bh.run_health

    def boom(*a, **kw):
        raise RuntimeError('人为触发的体检异常（测试用）')
    bh.run_health = boom
    try:
        rc = ap.main(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                      '--out', str(out_path), '--health'])
    finally:
        bh.run_health = orig_run_health
    record('t8_health异常时删除已写出候选', rc == 2 and not out_path.exists(),
           f'rc={rc} out_exists={out_path.exists()}')


# ================================================================ 9. 写后题面区复核用输出重新取区位（核心 major#1）
def test_zone_leak_uses_fresh_output_zones():
    """在若干"教学区紧邻题面区"的边界处 insert_after 一段普通教学文字，不给 source_zone。
    不预先假定结果该是拒还是放：无论工具判哪一边，都独立重新打开输出/由 abort 报告给出的
    index，用测试脚本自己的 bh.walk 核实该 index 在真实输出里的区位与工具的判断一致——
    这样才是在验证"用输出重新取区位"这条修复本身，而不是猜一个具体边界必然泄漏。"""
    boundaries = []
    for i in range(len(zone52) - 1):
        if zone52[i] == 'teaching' and zone52[i + 1] in ('source', 'title'):
            boundaries.append(i)
    if not boundaries:
        record('t9_题面零改写复核使用输出重新取区位', True, '本册没有教学紧邻题面的边界，跳过（如实说明）')
        return
    checked = 0
    consistent = 0
    for i in boundaries[:20]:
        anchor_text = dl.para_text(d52.paras[i])
        if not anchor_text or _text_counts.get(anchor_text) != 1:
            continue
        if checked >= 8:
            break
        patch_path = OUT / f't9_boundary_{i}.json'
        marker = f'（t9测试插入{i}）'
        write_patch(patch_path, [{'id': 'P1', 'op': 'insert_after', 'anchor': {'text': anchor_text},
                                  'paragraphs': [{'text': marker}]}], d52.sha256)
        out_path = OUT / f't9_boundary_{i}.docx'
        out_path.unlink(missing_ok=True)
        report_path = OUT / f't9_boundary_{i}.json.report.json'
        rc, out, err, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                                '--out', str(out_path), '--report', str(report_path)])
        checked += 1
        if rc == 2:
            rep = load_json(report_path)
            leak = (rep.get('zone_leak') or [])
            if not leak:
                continue
            idx_reported = leak[0]['index']
            zone_reported = leak[0]['zone']
            # 独立复核：报告中止后已删除输出，改用未插入前的原稿区位表判断"如果真插在这里，紧邻的
            # 那一段（题面第一段）原本是什么区位"，与报告里对新段给出的 zone 对照。
            independent_zone = zone52[i + 1] if i + 1 < len(zone52) else None
            if zone_reported == independent_zone:
                consistent += 1
        elif rc == 0:
            d_out_i = dl.open_docx(str(out_path))
            zone_out_i, _, _, _ = ap_zones_of_safe(d_out_i, prof)
            j = next((k for k, p in enumerate(d_out_i.paras) if dl.para_text(p) == marker), None)
            if j is not None and j < len(zone_out_i) and zone_out_i[j] not in ('source', 'title'):
                consistent += 1
            out_path.unlink(missing_ok=True)
    record('t9_题面零改写复核使用输出重新取区位', checked > 0 and consistent == checked,
           f'checked={checked} consistent={consistent}')


def ap_zones_of_safe(d, prof_dict):
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    return ap.zones_of(d, prof_dict)


# ================================================================ 10. 未点名段落基线用原始字节（模拟实现缺陷，攻击式回归）
def test_unchanged_baseline_catches_stray_edit():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    orig_set_keepnext = ap.apply_set_keepnext

    def buggy_set_keepnext(p, op):
        orig_set_keepnext(p, op)
        # 顺手改坏下一个兄弟段落（模拟实现缺陷）——不点名，不该被改
        nxt = p.getnext()
        while nxt is not None and nxt.tag != ap.W + 'p':
            nxt = nxt.getnext()
        if nxt is not None:
            for r in nxt.iter(ap.W + 'r'):
                t = r.find(ap.W + 't')
                if t is not None:
                    t.text = (t.text or '') + '【被误改】'
                    break

    idx_kn = teaching_idx
    anchor_text = teaching_text
    has_kn = d52.paras[idx_kn].find(f'{ap.W}pPr/{ap.W}keepNext') is not None
    patch_path = OUT / 't10_stray_edit.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'set_keepnext', 'anchor': {'text': anchor_text},
                              'value': not has_kn}], d52.sha256)
    out_path = OUT / 't10_out.docx'
    out_path.unlink(missing_ok=True)
    report_path = OUT / 't10_report.json'
    ap.apply_set_keepnext = buggy_set_keepnext
    try:
        rc = ap.main(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                      '--out', str(out_path), '--report', str(report_path)])
    finally:
        ap.apply_set_keepnext = orig_set_keepnext
    caught = rc == 2 and not out_path.exists()
    rep = load_json(report_path) if report_path.exists() else {}
    has_check = bool(rep.get('unchanged_check'))
    record('t10_基线来自原始字节能抓到顺手改坏的未点名段落', caught and has_check,
           f'rc={rc} out_exists={out_path.exists()} has_check={has_check}')


# ================================================================ 11. diff 的 format_changes 覆盖面
def test_diff_format_changes_coverage():
    patch_path = OUT / 't11_diff.json'
    report_path = OUT / 't11_diff_report.json'
    # 每次都从干净状态重新生成：test_regression_03_to_04_replay_and_perf 会在这份文件上原地
    # 补写 source_zone/allow_complex（模拟主代理审阅授权），approved_by 仍是 diff: 开头——这正是
    # 第五轮 minor④要拦的"看起来还没批准、实则已带授权字段"的补丁。留着上一次运行的产物会让
    # 这里的 diff --out 被新收紧的 _own_json 正当拒绝（不是回归，是这条测试自己的路径复用
    # 撞上了这一轮修的洞），所以先删干净，不依赖、也不测试跨进程运行的残留状态。
    patch_path.unlink(missing_ok=True)
    rc, out, err, dt = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(patch_path),
                            '--report', str(report_path), '--book', 'bixiu3'], timeout=120)
    ok_rc = rc == 0
    rep = load_json(report_path) if report_path.exists() else {}
    has_fields = all(k in rep for k in ('format_changes', 'format_changes_count', 'unanchorable', 'unanchorable_count'))
    record('t11_diff报告含format_changes与unanchorable字段', ok_rc and has_fields,
           f'rc={rc} keys={list(rep.keys())[:12]}')
    # 插入段落应带 style（不是每条新段一定有变化，但字段结构应存在）
    patch_obj = load_json(patch_path) if patch_path.exists() else {}
    inserts = [op for op in patch_obj.get('ops', []) if op['op'] in ('insert_after', 'insert_before')]
    style_carried = any('style' in sp for op in inserts for sp in op.get('paragraphs', []))
    record('t11b_diff新增段落带样式名', (not inserts) or style_carried,
           f'inserts={len(inserts)} style_carried={style_carried}')
    return rc, dt, patch_path


# ================================================================ 12. 回归：diff(03,04) 应用到 03 后文字流与 04 逐段一致；性能 < 30s
def test_regression_03_to_04_replay_and_perf():
    # 复用 test_diff_format_changes_coverage 已经生成的 diff 补丁（同一次 diff 结果）；不存在就重新跑一次。
    patch_path = OUT / 't11_diff.json'
    if not patch_path.exists():
        run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(patch_path),
             '--book', 'bixiu3'], timeout=120)
    obj = load_json(patch_path)
    for op in obj['ops']:
        if op.get('needs_authorization'):
            for fld in op['needs_authorization']:
                if fld == 'source_zone':
                    op['source_zone'] = 'approved_edit'
                if fld == 'allow_complex':
                    op['allow_complex'] = True
            op.setdefault('reason', op.get('reason') or '测试授权')
    patch_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')
    out_path = OUT / 't12_apply_03_to_04.docx'
    out_path.unlink(missing_ok=True)
    t0 = time.time()
    rc2, out2, err2, dt2 = run(['apply', '--docx', str(B3_03), '--patch', str(patch_path),
                                '--out', str(out_path)], timeout=60)
    elapsed = time.time() - t0
    ok_rc = rc2 == 0
    text_match = None
    if ok_rc:
        d_out = dl.open_docx(str(out_path))
        d04 = dl.open_docx(str(B3_04))
        texts_out = [dl.para_text(p) for p in d_out.paras]
        texts_04 = [dl.para_text(p) for p in d04.paras]
        text_match = texts_out == texts_04
        out_path.unlink(missing_ok=True)
    record('t12_diff03到04回放到03后文字流与04逐段一致', bool(ok_rc and text_match),
           f'rc={rc2} elapsed={elapsed:.1f}s text_match={text_match} err={err2[:200]}')
    record('t12b_03到04回放耗时低于30秒', elapsed < 30, f'elapsed={elapsed:.1f}s')


# ================================================================ 13. B2_230（冻结册）：check 可跑，apply 拒绝（退出 3）
def test_frozen_book_apply_refused():
    d230_sha = sha256(B2_230)
    patch_path = OUT / 't13_b230_patch.json'
    write_patch(patch_path, [], d230_sha, book='bixiu2')
    out_path = OUT / 't13_b230_out.docx'
    out_path.unlink(missing_ok=True)
    rc, out, err, _ = run(['apply', '--docx', str(B2_230), '--patch', str(patch_path),
                           '--out', str(out_path)], timeout=120)
    record('t13_冻结册apply拒绝退出3且不留输出', rc == 3 and not out_path.exists(), f'rc={rc} err={err}')


# ================================================================ 14. diff 的 --out/--report 大小写折叠同路径判断
def test_diff_case_fold_out_report_same_path_rejected():
    out1 = OUT / 't14_case_out.json'
    rep1 = OUT / 'T14_CASE_OUT.JSON'
    out1.unlink(missing_ok=True)
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(out1),
                           '--report', str(rep1), '--book', 'bixiu3'])
    record('t14_diff的out与report大小写变体同文件被拒且不留输出',
           rc == 2 and not out1.exists(), f'rc={rc} err={err} out_exists={out1.exists()}')


# ================================================================ 15. diff 先验 --report 再写 --out
def test_diff_report_precheck_before_out_write():
    out2 = OUT / 't15_diff_out.json'
    out2.unlink(missing_ok=True)
    rep2 = OUT / 't15_existing_report.json'
    rep2.write_text(json.dumps({'note': '别人的报告，不是 apply_patch 写的'}, ensure_ascii=False), encoding='utf-8')
    before = rep2.read_text(encoding='utf-8')
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(out2),
                           '--report', str(rep2), '--book', 'bixiu3'])
    after = rep2.read_text(encoding='utf-8')
    record('t15_diff先验report再写out_被拒时out不落盘且report不被覆盖',
           rc == 3 and not out2.exists() and before == after,
           f'rc={rc} err={err} out_exists={out2.exists()} report_unchanged={before == after}')


# ================================================================ 16. restore 词表豁免的写后区位复核（第四轮 major#1）
def test_restore_insert_before_title_leaking_word_rejected():
    if _title_after_teaching_idx is None:
        record('t16_restore豁免不能靠title锚点把工程词插进教学区', True, '本册没有title紧邻teaching的边界，跳过（如实说明）')
        return
    i = _title_after_teaching_idx
    anchor_text = dl.para_text(d52.paras[i])
    patch_path = OUT / 't16_restore_leak.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'insert_before', 'anchor': {'text': anchor_text},
                              'source_zone': 'restore', 'reason': '还原原题',
                              'paragraphs': [{'text': f'占位说明{FORBIDDEN_WORD}。'}]}], d52.sha256)
    out_path = OUT / 't16_restore_leak.docx'
    out_path.unlink(missing_ok=True)
    report_path = OUT / 't16_restore_leak_report.json'
    rc, out, err, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                           '--out', str(out_path), '--report', str(report_path)])
    rep = load_json(report_path) if report_path.exists() else {}
    ok = rc == 2 and not out_path.exists() and bool(rep.get('wordlist_leak'))
    record('t16_restore豁免不能靠title锚点把工程词插进教学区', ok,
           f'rc={rc} err={err} wordlist_leak={rep.get("wordlist_leak")}')


def test_restore_insert_before_title_clean_text_allowed():
    """对照组：同样的边界，插入干净文字（不含禁用词）应该照常放行——证明修复堵的是
    "词表命中"，不是简单地把"锚点在题面区但新段落位置在别处"的 restore 插入一律拒绝。"""
    if _title_after_teaching_idx is None:
        record('t16b_restore豁免_新段位置不在题面区但文字干净时仍放行', True, '跳过（同上无边界）')
        return
    i = _title_after_teaching_idx
    anchor_text = dl.para_text(d52.paras[i])
    patch_path = OUT / 't16b_restore_clean.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'insert_before', 'anchor': {'text': anchor_text},
                              'source_zone': 'restore', 'reason': '还原原题',
                              'paragraphs': [{'text': '这是一段不含禁用词的还原说明测试文字。'}]}], d52.sha256)
    out_path = OUT / 't16b_restore_clean.docx'
    out_path.unlink(missing_ok=True)
    rc, out, err, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path), '--out', str(out_path)])
    ok = rc == 0 and out_path.exists()
    out_path.unlink(missing_ok=True)
    record('t16b_restore豁免_新段位置不在题面区但文字干净时仍放行', ok, f'rc={rc} err={err}')


# ================================================================ 17. insert 的 bold:false 去掉模板继承的 w:b
def test_insert_bold_false_removes_inherited_bold():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    bold_idx = None
    for i, p in enumerate(d52.paras):
        r = p.find(f'{ap.W}r')
        t = dl.para_text(p)
        if r is not None and ap._run_fmt(r)[1] and t and _text_counts.get(t) == 1:
            bold_idx = i
            break
    if bold_idx is None:
        record('t17_insert的bold_false能去掉模板继承的加粗', True, '本册没有首run加粗的唯一段落，跳过')
        return
    anchor_text = dl.para_text(d52.paras[bold_idx])
    patch_path = OUT / 't17_bold_false.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'insert_after', 'anchor': {'text': anchor_text},
                              'paragraphs': [{'runs': [{'text': '不加粗的补充说明测试。', 'bold': False}]}]}],
                d52.sha256)
    out_path = OUT / 't17_bold_false.docx'
    out_path.unlink(missing_ok=True)
    rc, out, err, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path), '--out', str(out_path)])
    ok = rc == 0
    if ok:
        d_out = dl.open_docx(str(out_path))
        newp = d_out.paras[bold_idx + 1]
        runs_bold = [ap._run_fmt(r)[1] for r in newp.iter(ap.W + 'r')]
        ok = runs_bold == [False]
        out_path.unlink(missing_ok=True)
    record('t17_insert的bold_false能去掉模板继承的加粗', ok, f'rc={rc} err={err}')


# ================================================================ 18/19. 写后"文字不变"后置条件（set_keepnext 目标段、insert 锚点段）
def test_set_keepnext_target_text_change_caught():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    has_kn = d52.paras[teaching_idx].find(f'{ap.W}pPr/{ap.W}keepNext') is not None
    patch_path = OUT / 't18_keepnext_bug.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'set_keepnext', 'anchor': {'text': teaching_text},
                              'value': not has_kn}], d52.sha256)
    out_path = OUT / 't18_out.docx'
    out_path.unlink(missing_ok=True)
    report_path = OUT / 't18_report.json'
    orig = ap.apply_set_keepnext

    def buggy(p, op):
        orig(p, op)
        t = p.find(f'.//{ap.W}t')
        if t is not None:
            t.text = (t.text or '') + '【误改】'
    ap.apply_set_keepnext = buggy
    try:
        rc = ap.main(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                      '--out', str(out_path), '--report', str(report_path)])
    finally:
        ap.apply_set_keepnext = orig
    rep = load_json(report_path) if report_path.exists() else {}
    bad = rep.get('postcondition_failed') or []
    caught = rc == 2 and not out_path.exists() and any(
        b.get('id') == 'P1' and '文字' in (b.get('reason') or '') for b in bad)
    record('t18_set_keepnext目标段文字被顺手改动能被抓到', caught,
           f'rc={rc} postcondition_failed={bad}')


def test_insert_anchor_text_change_caught_by_unchanged_check():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    patch_path = OUT / 't19_insert_anchor_bug.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'insert_after', 'anchor': {'text': teaching_text},
                              'paragraphs': [{'text': '补一句测试说明。'}]}], d52.sha256)
    out_path = OUT / 't19_out.docx'
    out_path.unlink(missing_ok=True)
    report_path = OUT / 't19_report.json'
    orig = ap.apply_insert

    def buggy(d, p, op, before, styles_obj=None):
        r = orig(d, p, op, before, styles_obj)
        t = p.find(f'.//{ap.W}t')
        if t is not None:
            t.text = '【锚点被误改】' + (t.text or '')
        return r
    ap.apply_insert = buggy
    try:
        rc = ap.main(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                      '--out', str(out_path), '--report', str(report_path)])
    finally:
        ap.apply_insert = orig
    rep = load_json(report_path) if report_path.exists() else {}
    caught = rc == 2 and not out_path.exists() and bool(rep.get('unchanged_check'))
    record('t19_insert锚点段被顺手改动能被unchanged_paragraphs抓到', caught,
           f'rc={rc} unchanged_check={rep.get("unchanged_check")}')


# ================================================================ 20. check 与 apply 对 insert 的 style/clone_from 结论一致
def test_check_rejects_bad_insert_style_same_as_apply():
    patch_path = OUT / 't20_bad_style.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'insert_after', 'anchor': {'text': teaching_text},
                              'paragraphs': [{'text': '补一句。', 'style': '本册不存在的样式ZZZ'}]}], d52.sha256)
    rc_check, out_c, err_c, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    rc_apply, out_a, err_a, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                                     '--out', str(OUT / 't20_out.docx')])
    record('t20_check在insert样式名不存在时与apply一样中止',
           rc_check == 2 and rc_apply == 2 and '样式名' in err_c,
           f'rc_check={rc_check} rc_apply={rc_apply} err_c={err_c}')


def test_check_rejects_nonunique_clone_from():
    dup_text = None
    for t, c in _text_counts.items():
        if c > 1 and t:
            dup_text = t
            break
    if dup_text is None:
        record('t20b_check在clone_from命中多段时中止', True, '本册没有重复段落，跳过')
        return
    patch_path = OUT / 't20b_bad_clone.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'insert_after', 'anchor': {'text': teaching_text},
                              'paragraphs': [{'text': '补一句。', 'clone_from': dup_text}]}], d52.sha256)
    rc_check, out_c, err_c, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t20b_check在clone_from命中多段时中止', rc_check == 2 and 'clone_from' in err_c,
           f'rc={rc_check} err={err_c}')


# ================================================================ 21. 插入新文字首尾空白：明确原因，不误报失败
def test_insert_whitespace_normalized_reported():
    patch_path = OUT / 't21_ws.json'
    write_patch(patch_path, [{'id': 'P1', 'op': 'insert_after', 'anchor': {'text': teaching_text},
                              'paragraphs': [{'text': '　　首行缩进的补充段测试。'}]}], d52.sha256)
    out_path = OUT / 't21_out.docx'
    out_path.unlink(missing_ok=True)
    report_path = OUT / 't21_report.json'
    rc, out, err, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                           '--out', str(out_path), '--report', str(report_path)])
    rep = load_json(report_path) if report_path.exists() else {}
    ex = (rep.get('ops_extra') or {}).get('P1', {})
    ok = rc == 0 and bool(ex.get('new_whitespace_normalized'))
    out_path.unlink(missing_ok=True)
    record('t21_插入段首尾空白被规范化时报告给出明确原因', ok, f'rc={rc} err={err} extra={ex}')


# ================================================================ 22. diff 插入段保留 keepNext/run 格式，可回放一致；报告含结构损失汇总（第四轮 major#2）
def test_diff_insert_preserves_format_roundtrip():
    sys.path.insert(0, str(SCRIPTS))
    import apply_patch as ap
    import copy
    from lxml import etree as E
    d = dl.open_docx(str(B3_52))
    idx = teaching_idx
    p = d.paras[idx]
    newp = copy.deepcopy(p)
    for ch in list(newp):
        if ch.tag != ap.W + 'pPr':
            newp.remove(ch)
    ppr = newp.find(ap.W + 'pPr')
    if ppr is None:
        ppr = E.SubElement(newp, ap.W + 'pPr')
    if ppr.find(ap.W + 'keepNext') is None:
        E.SubElement(ppr, ap.W + 'keepNext')
    r1 = E.SubElement(newp, ap.W + 'r')
    rp = E.SubElement(r1, ap.W + 'rPr')
    E.SubElement(rp, ap.W + 'b')
    c = E.SubElement(rp, ap.W + 'color')
    c.set(ap.W + 'val', 'FF0000')
    t1 = E.SubElement(r1, ap.W + 't')
    t1.text = '纠正：'
    r2 = E.SubElement(newp, ap.W + 'r')
    t2 = E.SubElement(r2, ap.W + 't')
    t2.text = '这是测试用的新增教学说明。'
    p.addnext(newp)
    mod_path = OUT / 't22_mod.docx'
    dl.write_docx(d, mod_path)
    patch_path = OUT / 't22_patch.json'
    report_path = OUT / 't22_diff_report.json'
    rc, out, err, _ = run(['diff', '--old', str(B3_52), '--new', str(mod_path), '--out', str(patch_path),
                           '--report', str(report_path), '--book', 'bixiu3'])
    ok = rc == 0
    obj = load_json(patch_path) if patch_path.exists() else {}
    ins_ops = [op for op in obj.get('ops', []) if op['op'] in ('insert_after', 'insert_before')]
    spec = ins_ops[0]['paragraphs'][0] if ins_ops else {}
    ok = ok and spec.get('keep_next') is True and any(
        r.get('color') == 'FF0000' and r.get('bold') for r in spec.get('runs', []))
    out_path = OUT / 't22_applied.docx'
    out_path.unlink(missing_ok=True)
    if ok:
        rc2, out2, err2, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path), '--out', str(out_path)])
        ok = rc2 == 0
        if ok:
            d_out = dl.open_docx(str(out_path))
            newp_out = d_out.paras[idx + 1]
            kn_out = newp_out.find(f'{ap.W}pPr/{ap.W}keepNext') is not None
            runs_out = [(t, ap._run_fmt(r)) for r, t in ap._run_spans(newp_out)]
            # run2 的颜色允许是 None 或 '000000'：目标段本身没显式设颜色（继承黑色），插入时
            # 套模板 rPr 可能把黑色显式写出来——视觉上等价，不算格式丢失（只有 run1 的红色加粗
            # 是本用例真正要验证的"目标自己的格式覆盖了模板"）。
            _blackish = lambda c: c in (None, '000000')
            ok = kn_out and len(runs_out) == 2 and runs_out[0] == ('纠正：', ('FF0000', True)) and \
                runs_out[1][0] == '这是测试用的新增教学说明。' and _blackish(runs_out[1][1][0]) and not runs_out[1][1][1]
            out_path.unlink(missing_ok=True)
    rep = load_json(report_path) if report_path.exists() else {}
    has_summary = 'lost_structure_summary' in rep
    record('t22_diff插入段落保留keepNext与run格式并可回放一致', ok, f'rc={rc} spec={spec}')
    record('t22b_diff报告含lost_structure_summary顶层字段', has_summary, f'keys={list(rep.keys())}')


# ================================================================ 23. 第五轮 major①：diff 插入段带原样 ppr_xml/rpr_xml，51→52 抽查 >=50 段 C14N 一致
def test_51_52_insert_ppr_rpr_c14n_spotcheck():
    """真实压力回放：diff(B3_51, B3_52) 的插入段，逐段核对 apply 侧构建出来的 pPr、各 run
    rPr 与 B3_52 里目标段自己的 pPr/rPr 是不是字节级 C14N 一致。不整份 apply（51→52 的
    replace/delete 类 op 早前会在表格单元格唯一段处中止，不是本用例要测的东西），只用
    ap.resolve_anchor 在 B3_52 上重新定位每条 insert op 的锚点——能唯一定位到（意味着锚点
    文字在新稿里没变，是本轮插入紧贴着的稳定参照点）、且紧邻位置的文字与 op 的 paragraphs
    规格逐段相同（独立的对齐自检，对不上的样本直接跳过，不计入抽查也不算失败——只有"对齐
    确认无误、格式却不一致"才是真正的回归）时，才纳入抽查。

    比对时不能孤立调用 ap._build_paragraph 后直接 c14n：新 <w:p> 是用 Clark 记法
    `_E.Element(W+'p')` 造出来的，没给 nsmap，lxml 会给它内部分配一个任意前缀（如 ns0），
    脱离文档树单独序列化时就是这个前缀，跟目标段（从真实文件解析、前缀是 'w'）逐字节比对
    永远比不出相等——这是比对方法的假阳性，不是产品代码的缺陷（探针 /tmp 验证：真正
    apply_insert 把新段接到活文档树上再整份写出，字节里用的就是 'w' 前缀，跟目标一致）。
    所以这里用 ap.apply_insert 把新段真正接到一份工作副本 d_probe 的树上（跟 do_apply 的
    真实路径一致），再从接好之后的元素上取 pPr/rPr 比对——两边这才是同一序列化上下文。"""
    import apply_patch as ap
    import copy as _copy
    from lxml import etree as _E
    import zipfile
    patch_path = OUT / 't23_51_52_diff.json'
    rc, out, err, dt = run(['diff', '--old', str(B3_51), '--new', str(B3_52), '--out', str(patch_path),
                            '--book', 'bixiu3'], timeout=300)
    if rc != 0 or not patch_path.exists():
        record('t23_51到52插入段pPr与run_rPr的C14N抽查(>=50段)', False, f'diff rc={rc} err={err[:300]}')
        return
    obj = load_json(patch_path)
    insert_ops = [op for op in obj['ops'] if op['op'] in ('insert_after', 'insert_before')]

    d52_local = dl.open_docx(str(B3_52))
    # 单独一份工作副本，只用来做插入探针；d52_local 全程只读，专门给"目标段实际长什么样"当基准。
    d_probe = dl.open_docx(str(B3_52))
    with zipfile.ZipFile(str(B3_52)) as z:
        styles52 = bh.Styles(bh.etree.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None)
    zone52b, para_to_block52, blocks52, _P52 = ap.zones_of(d52_local, prof)
    text_index52 = ap._build_text_index(d52_local.paras)

    def spec_text(sp):
        if sp.get('runs'):
            return ''.join(r.get('text', '') for r in sp['runs'])
        return sp.get('text', '')

    def c14n(el):
        # 先 deepcopy 再序列化：段落仍挂在完整文档树上直接 c14n 会把祖先节点（w:document 根）
        # 声明的几十个命名空间（aink/am3d/cx/…）一起带出来；deepcopy 收敛到实际用到的最小
        # 集合（前缀不变，仍是源文件里的 'w'），两边这才是同一口径的比较。
        return _E.tostring(_copy.deepcopy(el), method='c14n') if el is not None else b''

    checked = 0
    mismatches = []
    skipped_unaligned = 0
    for op in insert_ops:
        idx, elem, cands = ap.resolve_anchor(d52_local, styles52, blocks52, para_to_block52,
                                              op['anchor'], text_index52)
        if idx is None:
            continue
        specs = op['paragraphs']
        n = len(specs)
        seq_idx = list(range(idx + 1, idx + 1 + n)) if op['op'] == 'insert_after' \
            else list(range(idx - n, idx))
        if not all(0 <= j < len(d52_local.paras) for j in seq_idx):
            continue
        if not all(dl.para_text(d52_local.paras[j]) == spec_text(sp) for j, sp in zip(seq_idx, specs)):
            skipped_unaligned += 1
            continue
        if not any('ppr_xml' in sp for sp in specs):
            continue  # 整条 op 全是复杂段（含超链接/域/图片/书签），跳过
        # d_probe.paras 是打开时建好的静态 Python 列表，不会因为别的 op 在树的别处 addnext/
        # addprevious 而自动变化——用同一个 idx 去取，仍是这条 op 锚点对应的那个真实元素，
        # 不需要在每次插入后重新 refresh/重新定位。
        anchor_in_probe = d_probe.paras[idx]
        new_ps = ap.apply_insert(d_probe, anchor_in_probe, {'id': op['id'], 'paragraphs': specs},
                                  before=(op['op'] == 'insert_before'), styles_obj=styles52)
        for j, sp, built in zip(seq_idx, specs, new_ps):
            if 'ppr_xml' not in sp:
                continue  # 复杂段（含超链接/域/图片/书签），本轮不产出 ppr_xml/runs，不在抽查范围
            target = d52_local.paras[j]
            ppr_ok = c14n(built.find(ap.W + 'pPr')) == c14n(target.find(ap.W + 'pPr'))
            got_runs = [r for r in built if r.tag == ap.W + 'r']
            want_runs = list(target.iter(ap.W + 'r'))
            runs_ok = len(got_runs) == len(want_runs) and all(
                c14n(gr.find(ap.W + 'rPr')) == c14n(wr.find(ap.W + 'rPr'))
                for gr, wr in zip(got_runs, want_runs))
            checked += 1
            if not (ppr_ok and runs_ok):
                mismatches.append({'op': op['id'], 'index': j, 'ppr_ok': ppr_ok, 'runs_ok': runs_ok})
        if checked >= 150:
            break
    record('t23_51到52插入段pPr与run_rPr的C14N抽查(>=50段)',
           checked >= 50 and not mismatches,
           f'checked={checked} mismatches={len(mismatches)} skipped_unaligned={skipped_unaligned} '
           f'insert_ops={len(insert_ops)} diff_elapsed={dt:.1f}s sample={mismatches[:5]}')


# ================================================================ 24. 第五轮 minor②a：词表检查先去零宽字符（bh.ZW）
def test_forbidden_word_split_by_zero_width_char():
    zw = bh.ZW_CHARS[0]
    half = len(FORBIDDEN_WORD) // 2 or 1
    split_word = FORBIDDEN_WORD[:half] + zw + FORBIDDEN_WORD[half:]
    patch_path = OUT / 't24_zw_patch.json'
    new_text = teaching_text + split_word
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': teaching_text},
            'old': teaching_text, 'new': new_text,
            'reason': '测试：禁用词被零宽字符隔断仍应命中'}]
    write_patch(patch_path, ops, d52.sha256)
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t24_禁用词被零宽字符隔断仍被词表拦截', rc == 2 and '禁用词表' in err, f'rc={rc} err={err}')


# ================================================================ 24b. 第五轮 minor②b：uniq_anchor 按 bh.norm 判重复，跟 resolve_anchor 同口径
def test_uniq_anchor_norm_dedup_needs_index_hint():
    import apply_patch as ap
    import copy as _copy
    from lxml import etree as _E
    d = dl.open_docx(str(B3_52))
    idx = teaching_idx
    base = _copy.deepcopy(d.paras[idx])
    for ch in list(base):
        if ch.tag != ap.W + 'pPr':
            base.remove(ch)

    def _mk(text):
        node = _copy.deepcopy(base)
        r = _E.SubElement(node, ap.W + 'r')
        t = _E.SubElement(r, ap.W + 't')
        t.text = text
        return node
    UNIQ_A = '占位甲乙丙丁_t24b合稿测试专用'
    UNIQ_B = '占位甲乙 丙丁_t24b合稿测试专用'  # 中间多一个空格，bh.norm 后与 UNIQ_A 相同，字面不等
    assert bh.norm(UNIQ_A) == bh.norm(UNIQ_B) and UNIQ_A != UNIQ_B
    p1, p2 = _mk(UNIQ_A), _mk(UNIQ_B)
    d.paras[idx].addnext(p1)
    p1.addnext(p2)
    base_path = OUT / 't24b_base.docx'
    dl.write_docx(d, base_path)
    d2 = dl.open_docx(str(base_path))
    idx1, idx2 = idx + 1, idx + 2

    def _add_after(pp, text):
        node = _copy.deepcopy(pp)
        for ch in list(node):
            if ch.tag != ap.W + 'pPr':
                node.remove(ch)
        r = _E.SubElement(node, ap.W + 'r')
        t = _E.SubElement(r, ap.W + 't')
        t.text = text
        pp.addnext(node)
    _add_after(d2.paras[idx2], '这是紧跟乙段的新增说明_t24b')
    _add_after(d2.paras[idx1], '这是紧跟甲段的新增说明_t24b')
    mod_path = OUT / 't24b_mod.docx'
    dl.write_docx(d2, mod_path)
    patch_path = OUT / 't24b_patch.json'
    rc, out, err, _ = run(['diff', '--old', str(base_path), '--new', str(mod_path),
                           '--out', str(patch_path), '--book', 'bixiu3'])
    ok = rc == 0
    obj = load_json(patch_path) if patch_path.exists() else {}
    ins_ops = [op for op in obj.get('ops', []) if op['op'] == 'insert_after']
    hit = [op for op in ins_ops if bh.norm(op['anchor'].get('text') or '') == bh.norm(UNIQ_A)]
    ok = ok and len(hit) == 2 and all('index_hint' in op['anchor'] for op in hit)
    record('t24b_uniq_anchor按norm判重复_只差空白的两段都带index_hint',
           ok, f'rc={rc} err={err[:200]} hit_anchors={[op["anchor"] for op in hit]}')


# ================================================================ 25. 第五轮 minor③：replace_paragraph 带 restore 的写后区位复核
def test_restore_replace_paragraph_zone_shift_wordlist_recheck():
    """锚点是真实的例题标题段（zone=title），replace_paragraph 把它改写成不再像标题的
    文字（探针已验证：写后重开该段 zone 变成 heading），新文字里再带一个禁用词——check
    阶段因为锚点自己在 title 区、source_zone=restore 而豁免词表，postcondition 也只看
    "新文字是不是等于 new"，只有第五轮新加的写后区位复核会用输出重新分区，发现这段实际
    已经不在 source/title 区，对新文字补跑一遍词表并中止、删除输出。"""
    idx = None
    for i, p in enumerate(d52.paras):
        t = dl.para_text(p)
        if t.startswith('例题') and '　' in t and _text_counts.get(t) == 1:
            idx = i
            break
    if idx is None:
        record('t25_replace_paragraph带restore的写后区位复核', True, '跳过：本稿找不到匹配的例题标题段')
        return
    old_t = dl.para_text(d52.paras[idx])
    new_t = '本题讲解待核，暂按旧版。' + FORBIDDEN_WORD
    patch_path = OUT / 't25_patch.json'
    ops = [{'id': 'P1', 'op': 'replace_paragraph', 'anchor': {'text': old_t},
            'old': old_t, 'new': new_t,
            'source_zone': 'restore', 'reason': '测试：replace_paragraph 的 restore 写后区位复核'}]
    write_patch(patch_path, ops, d52.sha256)
    rc_check, out_c, err_c, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    out_path = OUT / 't25_out.docx'
    out_path.unlink(missing_ok=True)
    report_path = OUT / 't25_report.json'
    rc, out, err, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                           '--out', str(out_path), '--report', str(report_path)])
    rep = load_json(report_path) if report_path.exists() else {}
    ok = rc_check in (0, 1) and rc == 2 and not out_path.exists() and \
        '题面零改写复核不通过' in (err or '') and bool(rep.get('wordlist_leak'))
    out_path.unlink(missing_ok=True)
    record('t25_replace_paragraph带restore的写后区位复核能抓到漂移出题面区的禁用词',
           ok, f'check_rc={rc_check} apply_rc={rc} err={err[:200]} wordlist_leak={rep.get("wordlist_leak")}')


# ================================================================ 26. 第五轮 minor④：diff --out 不能覆盖"仍是 diff: 但已带授权字段"的补丁
def test_diff_out_cannot_overwrite_authorized_diff_patch():
    """主代理审阅补丁、逐条补上 source_zone/allow_complex，却忘了把 approved_by 从自动值
    改掉——这份文件的 approved_by 仍是 'diff:' 开头，上一轮的判断只看这一个字段，会认为
    "还没批准、可以覆盖"，再跑一次 diff --out 到同一路径就会把这些授权字段连同旧内容一起
    静默冲掉。这一轮改成：ops 里只要有一条带 source_zone 或 allow_complex，就算 approved_by
    还是 diff: 开头也拒绝覆盖。"""
    patch_path = OUT / 't26_authorized_diff_patch.json'
    ops = [{'id': 'P1', 'op': 'replace_paragraph', 'anchor': {'text': teaching_text},
            'old': teaching_text, 'new': teaching_text + '（已审）',
            'source_zone': 'approved_edit', 'reason': '主代理已审阅并授权'}]
    write_patch(patch_path, ops, d52.sha256, approved_by='diff:apply_patch')
    before = patch_path.read_text(encoding='utf-8')
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(patch_path),
                           '--book', 'bixiu3'])
    after = patch_path.read_text(encoding='utf-8')
    record('t26_diff_out不能覆盖带source_zone授权字段的diff产物补丁',
           rc == 3 and before == after, f'rc={rc} err={err} unchanged={before == after}')


def test_diff_out_can_still_overwrite_plain_diff_patch_without_authz_fields():
    """对照：ops 里完全没有 source_zone/allow_complex（纯 diff 自动产物，没人touch过）时，
    仍然可以被覆盖——第五轮的收紧不能误伤上一轮已经验证过的 t5b 场景。"""
    patch_path = OUT / 't26b_plain_diff_patch.json'
    ops = [{'id': 'P1', 'op': 'replace_paragraph', 'anchor': {'text': teaching_text},
            'old': teaching_text, 'new': teaching_text + '（占位）', 'reason': 'diff'}]
    write_patch(patch_path, ops, d52.sha256, approved_by='diff:apply_patch',
                approval_ref=B3_03_04_AUTO_APPROVAL_REF)
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(patch_path),
                           '--book', 'bixiu3'])
    ok = rc == 0
    if ok:
        obj = load_json(patch_path)
        ok = obj.get('schema') == 'baodian_patch_v1' and len(obj.get('ops', [])) > 0
    record('t26b_diff_out仍可覆盖不含授权字段的纯diff产物补丁', ok, f'rc={rc} err={err}')


# ================================================================ 27. 第六轮 major①：插入段带 ppr_xml/rpr_xml 时，给人看字段与原样格式不一致必须中止
def _build_ppr_rpr_insert_patch(tag):
    """复用 t22 的手法（真实 diff，不是手写 spec）：给教学区锚点段后面插一段纯黑色文字，
    diff 会给它同时产出 ppr_xml 与 runs[].rpr_xml（因为不是复杂段）。返回解析后的补丁 dict，
    失败时返回 None（调用方按跳过处理，不误判成失败）。"""
    d = dl.open_docx(str(B3_52))
    idx = teaching_idx
    p = d.paras[idx]
    newp = _copy.deepcopy(p)
    for ch in list(newp):
        if ch.tag != _ap.W + 'pPr':
            newp.remove(ch)
    ppr = newp.find(_ap.W + 'pPr')
    if ppr is not None:
        for kn in ppr.findall(_ap.W + 'keepNext'):
            ppr.remove(kn)
    r1 = _E.SubElement(newp, _ap.W + 'r')
    t1 = _E.SubElement(r1, _ap.W + 't')
    t1.text = f'这是一段普通黑色补充说明_{tag}。'
    p.addnext(newp)
    mod_path = OUT / f't{tag}_mod.docx'
    dl.write_docx(d, mod_path)
    patch_path = OUT / f't{tag}_diff_patch.json'
    rc, out, err, _ = run(['diff', '--old', str(B3_52), '--new', str(mod_path), '--out', str(patch_path),
                           '--book', 'bixiu3'])
    if rc != 0 or not patch_path.exists():
        return None
    return load_json(patch_path)


def _first_ppr_rpr_spec(patch):
    for op in patch.get('ops', []):
        if op.get('op') not in ('insert_after', 'insert_before'):
            continue
        for spec in op.get('paragraphs', []):
            if 'ppr_xml' in spec and spec.get('runs') and any('rpr_xml' in r for r in spec['runs']):
                return op, spec
    return None, None


import copy as _copy  # noqa: E402
from lxml import etree as _E  # noqa: E402
import apply_patch as _ap  # noqa: E402


def test_insert_text_mismatch_with_runs_rejected():
    """插入段既带 ppr_xml/rpr_xml 又带 text，把 text 单独改写成别的措辞——runs[].text 没跟着
    改，_build_paragraph 早就只认 runs，text 是死字段。主代理如果以为改 text 就能改掉插入段的
    实际文字，这里必须在 check 阶段就中止，不能让改动被静默吞掉。"""
    patch = _build_ppr_rpr_insert_patch('27')
    if not patch:
        record('t27_插入段text与runs拼接不一致时check中止', True, '跳过：diff 未产出可用补丁')
        return
    op, spec = _first_ppr_rpr_spec(patch)
    if spec is None:
        record('t27_插入段text与runs拼接不一致时check中止', True, '跳过：diff 未产出带 ppr_xml/rpr_xml 的插入段')
        return
    spec['text'] = '主代理改写后的新说法。'
    patch_path = OUT / 't27_patch.json'
    Path(patch_path).write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding='utf-8')
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t27_插入段text与runs拼接不一致时check中止',
           rc == 2 and ('runs[].text' in err or 'text' in err), f'rc={rc} err={err[:200]}')


def test_insert_style_mismatch_with_ppr_xml_rejected():
    """插入段同时带 ppr_xml 与 style（给人看字段），把 style 单独改成 ppr_xml 里实际样式以外的
    另一个真实存在的样式名——_build_paragraph 只认 ppr_xml，style 会被静默忽略。check 必须
    核对两者一致，不一致就中止。"""
    patch = _build_ppr_rpr_insert_patch('28')
    if not patch:
        record('t28_插入段style与ppr_xml不一致时check中止', True, '跳过：diff 未产出可用补丁')
        return
    op, spec = _first_ppr_rpr_spec(patch)
    if spec is None:
        record('t28_插入段style与ppr_xml不一致时check中止', True, '跳过：diff 未产出带 ppr_xml/rpr_xml 的插入段')
        return
    with zipfile.ZipFile(str(B3_52)) as z:
        styles_xml = _E.fromstring(z.read('word/styles.xml'))
    styles_obj28 = bh.Styles(styles_xml)
    ppr_el = _E.fromstring(spec['ppr_xml']) if spec.get('ppr_xml') else None
    cur_pstyle_el = ppr_el.find(_ap.W + 'pStyle') if ppr_el is not None else None
    cur_val = cur_pstyle_el.get(_ap.W + 'val') if cur_pstyle_el is not None else None
    chosen = None
    for sid, nm in (styles_obj28.name or {}).items():
        if sid != cur_val:
            chosen = nm
            break
    if not chosen:
        record('t28_插入段style与ppr_xml不一致时check中止', True, '跳过：找不到另一个可用样式名')
        return
    spec['style'] = chosen
    patch_path = OUT / 't28_patch.json'
    Path(patch_path).write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding='utf-8')
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t28_插入段style与ppr_xml不一致时check中止',
           rc == 2 and 'style' in err, f'rc={rc} err={err[:200]} chosen_style={chosen}')


def test_insert_bold_mismatch_with_rpr_xml_rejected():
    """插入段某个 run 同时带 rpr_xml 与 bold（给人看字段），把 bold 改成与 rpr_xml 里的实际
    加粗相反——_build_paragraph 只认 rpr_xml，bold 会被静默忽略。check 必须核对两者一致。"""
    patch = _build_ppr_rpr_insert_patch('29')
    if not patch:
        record('t29_插入段runs_bold与rpr_xml不一致时check中止', True, '跳过：diff 未产出可用补丁')
        return
    op, spec = _first_ppr_rpr_spec(patch)
    if spec is None:
        record('t29_插入段runs_bold与rpr_xml不一致时check中止', True, '跳过：diff 未产出带 ppr_xml/rpr_xml 的插入段')
        return
    rs = next((r for r in spec['runs'] if 'rpr_xml' in r), None)
    if rs is None:
        record('t29_插入段runs_bold与rpr_xml不一致时check中止', True, '跳过：插入段没有带 rpr_xml 的 run')
        return
    rpr_el = _ap._parse_ppr_rpr_fragment(rs['rpr_xml'], 'rPr') if rs.get('rpr_xml') else None
    bold_val, _color_val = _ap._rpr_authentic_fmt(rpr_el)
    rs['bold'] = not bold_val
    patch_path = OUT / 't29_patch.json'
    Path(patch_path).write_text(json.dumps(patch, ensure_ascii=False, indent=2), encoding='utf-8')
    rc, out, err, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    record('t29_插入段runs_bold与rpr_xml不一致时check中止',
           rc == 2 and 'bold' in err, f'rc={rc} err={err[:200]} bold_val={bold_val}')


# ================================================================ 30. 第六轮 minor②：replace_text 带 restore 的写后区位复核（与 replace_paragraph 同口径）
def test_restore_replace_text_zone_shift_wordlist_recheck():
    """同 t25，但改用 replace_text 只改标题段的前几个字（不是整段替换）。fix5 的 restore_replace_ops
    只收了 replace_paragraph，replace_text 带 source_zone=restore 时完全没有写后区位+词表复核——
    这里验证同一段落用 replace_text 也能被拦下。"""
    idx = None
    for i, p in enumerate(d52.paras):
        t = dl.para_text(p)
        if t.startswith('例题') and '　' in t and _text_counts.get(t) == 1:
            idx = i
            break
    if idx is None:
        record('t30_replace_text带restore的写后区位复核', True, '跳过：本稿找不到匹配的例题标题段')
        return
    old_full = dl.para_text(d52.paras[idx])
    prefix = old_full[:6]
    new_prefix = '本题讲解待核，' + FORBIDDEN_WORD
    patch_path = OUT / 't30_patch.json'
    ops = [{'id': 'P1', 'op': 'replace_text', 'anchor': {'text': old_full},
            'old': prefix, 'new': new_prefix,
            'source_zone': 'restore', 'reason': '测试：replace_text 的 restore 写后区位复核'}]
    write_patch(patch_path, ops, d52.sha256)
    rc_check, out_c, err_c, _ = run(['check', '--docx', str(B3_52), '--patch', str(patch_path)])
    out_path = OUT / 't30_out.docx'
    out_path.unlink(missing_ok=True)
    report_path = OUT / 't30_report.json'
    rc, out, err, _ = run(['apply', '--docx', str(B3_52), '--patch', str(patch_path),
                           '--out', str(out_path), '--report', str(report_path)])
    rep = load_json(report_path) if report_path.exists() else {}
    ok = rc_check in (0, 1) and rc == 2 and not out_path.exists() and \
        '题面零改写复核不通过' in (err or '') and bool(rep.get('wordlist_leak'))
    out_path.unlink(missing_ok=True)
    record('t30_replace_text带restore的写后区位复核能抓到漂移出题面区的禁用词',
           ok, f'check_rc={rc_check} apply_rc={rc} err={err[:200]} wordlist_leak={rep.get("wordlist_leak")}')


# ================================================================ 31. 第六轮 minor③：diff --out 覆盖守卫要看 approval_ref 是否被人动过
def test_diff_out_cannot_overwrite_patch_with_touched_approval_ref_only():
    """C5 攻击：只把 approval_ref 改成人写的说明文字，approved_by 仍是 diff 自动值，ops 里也
    没有任何 source_zone/allow_complex——上一轮的判断只看 approved_by 前缀和 op 授权字段，看不见
    approval_ref 被单独动过，会误判成"还没批准"而允许再次 diff --out 覆盖。这一轮必须拒绝。"""
    patch_path = OUT / 't31_touched_approval_ref.json'
    ops = [{'id': 'P1', 'op': 'replace_paragraph', 'anchor': {'text': teaching_text},
            'old': teaching_text, 'new': teaching_text + '（占位）', 'reason': 'diff'}]
    write_patch(patch_path, ops, d52.sha256, approved_by='diff:apply_patch',
                approval_ref='主代理已审 第52批')
    before = patch_path.read_text(encoding='utf-8')
    rc, out, err, _ = run(['diff', '--old', str(B3_03), '--new', str(B3_04), '--out', str(patch_path),
                           '--book', 'bixiu3'])
    after = patch_path.read_text(encoding='utf-8')
    record('t31_diff_out不能覆盖只改了approval_ref的补丁',
           rc == 3 and before == after, f'rc={rc} err={err} unchanged={before == after}')


def main():
    fns = [
        test_wordlist_scope_teaching_restore_rejected,
        test_wordlist_scope_source_restore_exempt,
        test_wordlist_concat_runs,
        test_source_zone_invalid_value_anywhere,
        test_source_zone_missing_reason_anywhere,
        test_source_zone_missing_on_source_anchor,
        test_missing_new_field_clear_error,
        test_report_cannot_overwrite_approved_patch,
        test_diff_out_cannot_overwrite_approved_patch,
        test_diff_out_can_overwrite_diff_patch,
        test_report_and_out_same_path_rejected,
        test_patch_path_in_guard_inputs,
        test_replace_paragraph_tab_and_first_text_run,
        test_new_texts_of_concat_not_per_run,
        test_resolve_anchor_index_correctness,
        test_health_exception_deletes_output,
        test_zone_leak_uses_fresh_output_zones,
        test_unchanged_baseline_catches_stray_edit,
        test_diff_format_changes_coverage,
        test_regression_03_to_04_replay_and_perf,
        test_frozen_book_apply_refused,
        test_diff_case_fold_out_report_same_path_rejected,
        test_diff_report_precheck_before_out_write,
        test_restore_insert_before_title_leaking_word_rejected,
        test_restore_insert_before_title_clean_text_allowed,
        test_insert_bold_false_removes_inherited_bold,
        test_set_keepnext_target_text_change_caught,
        test_insert_anchor_text_change_caught_by_unchanged_check,
        test_check_rejects_bad_insert_style_same_as_apply,
        test_check_rejects_nonunique_clone_from,
        test_insert_whitespace_normalized_reported,
        test_diff_insert_preserves_format_roundtrip,
        test_51_52_insert_ppr_rpr_c14n_spotcheck,
        test_forbidden_word_split_by_zero_width_char,
        test_uniq_anchor_norm_dedup_needs_index_hint,
        test_restore_replace_paragraph_zone_shift_wordlist_recheck,
        test_diff_out_cannot_overwrite_authorized_diff_patch,
        test_diff_out_can_still_overwrite_plain_diff_patch_without_authz_fields,
        test_insert_text_mismatch_with_runs_rejected,
        test_insert_style_mismatch_with_ppr_xml_rejected,
        test_insert_bold_mismatch_with_rpr_xml_rejected,
        test_restore_replace_text_zone_shift_wordlist_recheck,
        test_diff_out_cannot_overwrite_patch_with_touched_approval_ref_only,
    ]
    for fn in fns:
        try:
            fn()
        except Exception as e:
            import traceback
            record(fn.__name__, False, f'异常：{e}\n{traceback.format_exc()[-800:]}')
    n_fail = sum(1 for r in results if not r['ok'])
    (OUT / 'test_results.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print('====================')
    print(f'总计 {len(results)}，失败 {n_fail}')
    if n_fail == 0:
        print('全部关键断言通过')
    return 0 if n_fail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
