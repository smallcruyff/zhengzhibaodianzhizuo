"""R4 对抗用例（CLI，不带 --debug）：守卫绕过、原子性、批内部分失败、异常提示语言、冻结册、SHA。"""
from common import *
sys.path.insert(0, str(C))
import run_tests_block_insert as rt
A = WORK / 'adv'; shutil.rmtree(A, ignore_errors=True); A.mkdir()
parent = A / 'parent.docx'; shutil.copyfile(BOOK, parent)
def unit(**kw):
    return rt._minimal_unit(BOOK_SHA, **kw)
def case(name, u, out, extra=(), profile=PROF, expect=None, docx=parent, mode='apply'):
    up = A / f'{name}.json'; up.write_text(json.dumps(u, ensure_ascii=False))
    out = Path(out); existed = out.exists() or out.is_symlink()
    args = [mode, '--docx', str(docx), '--insert', str(up), '--profile', str(profile)] + (['--out', str(out)] if mode == 'apply' else []) + list(extra)
    rc, so, se = run_tool(args)
    left = (not existed) and out.exists()
    tb = 'Traceback' in se
    ok = (expect is None or rc == expect) and not (left and expect in (2, 3)) and not tb
    tmp_left = [p.name for p in out.parent.glob('.block_insert_*')] if out.parent.exists() else []
    print(f"{'OK ' if ok else 'BAD'} {name}: rc={rc} expect={expect} out_left={left} tmp_left={tmp_left} tb={tb} | {se.strip()[-220:]}")
    return rc, so, se
# 1 符号链接绕过：临时区里的链接指向书稿目录
link = A / 'link_to_book'; link.symlink_to(R / '必修三_最新Skill修订_20260913')
case('symlink_to_book', unit(), link / 'x.docx', expect=3)
# 2 输出落在候选目录 C 根（非 构建/）
case('C_root', unit(), C / 'r4_probe_should_not_exist.docx', expect=3)
# 3 输出落在 C/审查/（非 构建/）
case('C_review', unit(), C / '审查' / 'r4_probe_should_not_exist.docx', expect=3)
# 4 输出落在 云端/ 与 后勤管理/
case('cloud_dir', unit(), R / '云端' / 'x.docx', expect=3)
case('logistics_dir', unit(), R / '后勤管理' / 'x.docx', expect=3)
# 5 原材料目录
case('raw_dir', unit(), R / '00_共同资料' / '原材料' / 'x.docx', expect=3)
# 6 --report 指向书稿目录：docx 不应写出
out6 = A / 'r6.docx'
case('report_in_book', unit(), out6, extra=['--report', str(R / '必修三_最新Skill修订_20260913' / 'x.json')], expect=3)
# 7 --report 指向 Skill 下已有 json
sk_json = next((SK.parent).rglob('*.json'))
b7 = sha(sk_json)
case('report_over_skill_json', unit(), A / 'r7.docx', extra=['--report', str(sk_json)], expect=3)
print('   skill json unchanged:', sha(sk_json) == b7)
# 8 批内第 2 条 insert 失败 → 整批中止、不留输出
u8 = unit(); ins2 = json.loads(json.dumps(u8['inserts'][0])); ins2['id'] = 'N2'; ins2['title'] = '例题 94　2099负例第2题'
ins2['template_block'] = {'title_contains': '不存在的样板_xyz'}; u8['inserts'].append(ins2)
case('batch_second_fails', u8, A / 'r8.docx', expect=2)
# 9 重复 id / 标题已存在
u9 = unit(); ins = json.loads(json.dumps(u9['inserts'][0])); u9['inserts'].append(ins)
case('dup_id', u9, A / 'r9.docx', expect=2)
case('title_exists', unit(title='例题 3　2024朝阳二模第18题'), A / 'r10.docx', expect=2)
# 10 kind 非法
u11 = unit(); u11['inserts'][0]['content'][0]['kind'] = 'question'
case('bad_kind', u11, A / 'r11.docx', expect=2)
# 11 from.docx 指向 PDF/非 zip
pdf = next((R / '00_共同资料' / '原材料').rglob('*.pdf'))
u12 = unit(content=[{'role': 'source', 'text': '【题目】负例。'}, {'role': 'image', 'from': {'docx': str(pdf), 'index': 1}}] + rt._MINIMAL_CONTENT[1:])
case('from_docx_is_pdf', u12, A / 'r12.docx', expect=2)
# 12 image file 是 PDF
u13 = unit(content=[{'role': 'source', 'text': '【题目】负例。'}, {'role': 'image', 'file': str(pdf)}] + rt._MINIMAL_CONTENT[1:])
case('image_file_is_pdf', u13, A / 'r13.docx', expect=2)
# 13 输出已存在（不覆盖）
ex = A / 'exists.docx'; ex.write_bytes(b'old'); 
case('out_exists', unit(), ex, expect=3)
print('   existing untouched:', ex.read_bytes() == b'old')
# 14 输出目录不存在
case('out_dir_missing', unit(), A / 'nope' / 'x.docx', expect=3)
# 15 冻结册 apply（book 一致）
case('frozen_apply', unit(book='bixiu2'), A / 'r15.docx', profile=C / 'profiles_cloud/bixiu2_frozen_test.json', expect=3)
# 16 SHA 错
case('sha_wrong', rt._minimal_unit('f' * 64), A / 'r16.docx', expect=2)
# 17 父稿不是 docx
bad = A / 'notdocx.docx'; bad.write_bytes(b'garbage')
u17 = rt._minimal_unit(sha(bad))
case('parent_not_zip', u17, A / 'r17.docx', docx=bad, expect=2)
# 18 anchor 同时给两个
case('two_anchor_kinds', unit(anchor={'after_block': {'title_contains': '例题 3　2024朝阳二模第18题'}, 'before_block': {'title_contains': '例题 4　2024'}}), A / 'r18.docx', expect=2)
# 19 method_end 缺 method_contains 的类型错误（数字）
case('method_contains_int', unit(anchor={'method_end': {'method_contains': 3}}), A / 'r19.docx', expect=2)
# 20 正例对照（临时区）
case('control_ok', unit(), A / 'r20.docx', expect=0)
print('leftover in C (should be none):', [p.name for p in C.glob('r4_probe*')], [p.name for p in (C / '审查').glob('r4_probe*')])
