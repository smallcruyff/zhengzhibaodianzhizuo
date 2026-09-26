"""R4 原子性：写出过程中各点失败（os.replace 抛错、写后成员复核抛错、verify_output 抛错），确认不留输出也不留临时文件，退出码 2/非 0。"""
from common import *
sys.path.insert(0, str(C))
import run_tests_block_insert as rt
import io, contextlib
A = WORK / 'atomic'; shutil.rmtree(A, ignore_errors=True); A.mkdir()
parent = A / 'parent.docx'; shutil.copyfile(BOOK, parent)
up = A / 'u.json'
u = rt._minimal_unit(BOOK_SHA, content=[{'role': 'source', 'text': '【题目】原子性探针材料。'},
      {'role': 'image', 'from': {'docx': str(rt.XC_ERMO_DOCX), 'index': 1}}] + rt._MINIMAL_CONTENT[1:])
up.write_text(json.dumps(u, ensure_ascii=False))
def run(label, patch):
    out = A / f'{label}.docx'
    undo = patch()
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = bi.main(['apply', '--docx', str(parent), '--insert', str(up), '--out', str(out), '--profile', str(PROF)])
    finally:
        undo()
    left = sorted(p.name for p in A.iterdir() if p.name.startswith('.block_insert_') or p.name == out.name)
    print(f'{label}: rc={rc} leftovers={left} | {err.getvalue().strip()[-160:]}')
real_replace = os.replace
def p1():
    def boom(a, b):
        if str(b).endswith('.docx'): raise OSError('模拟：原子替换失败')
        return real_replace(a, b)
    bi.os.replace = boom
    return lambda: setattr(bi.os, 'replace', real_replace)
run('replace_fails', p1)
real_fs = bi.etree.fromstring
def p2():
    state = {'n': 0}
    orig = bi._write_with_new_media
    def wrapped(d, out, extra, new_media):
        new_media = dict(new_media); new_media['word/document.xml'] = b'x'  # 与已有成员重名 → 应拒绝
        return orig(d, out, extra, new_media)
    bi._write_with_new_media = wrapped
    return lambda: setattr(bi, '_write_with_new_media', orig)
run('dup_member', p2)
def p3():
    orig = bi.verify_output
    def boom(*a, **k): raise RuntimeError('模拟：写后复核异常')
    bi.verify_output = boom
    return lambda: setattr(bi, 'verify_output', orig)
run('verify_raises', p3)
def p4():
    orig = bi.bidx.build_index
    def fake(path, prof):
        r = orig(path, prof)
        for b in r['blocks']:
            if '2099负例测试占位卷' in b['title']:
                b['missing'] = ['【答案落点】']
        return r
    bi.bidx.build_index = fake
    return lambda: setattr(bi.bidx, 'build_index', orig)
run('postcondition_missing_column', p4)
run('control', lambda: (lambda: None))
