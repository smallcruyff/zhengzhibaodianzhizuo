"""intake_run.py 对抗探针（审查 r1）。只写本 scratch 目录；不改被审工具。"""
import json, os, shutil, subprocess, sys, time
from pathlib import Path
sys.dont_write_bytecode = True
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
TOOL = C / 'intake_run.py'
S = Path(sys.argv[1]); W = S / 'adv'
if W.exists(): shutil.rmtree(W)
W.mkdir(parents=True)
P3 = str(C / 'profiles_cloud/bixiu3.json')
log = []

def run(args, cwd=None, tool=TOOL, env=None):
    t = time.time()
    p = subprocess.run([sys.executable, '-B', str(tool)] + [str(a) for a in args], capture_output=True, text=True, cwd=cwd, env=env, timeout=300)
    return p.returncode, p.stdout, p.stderr, round(time.time() - t, 1)

def man(name, exams, books=('bixiu3',), profiles=None, workdir=None, **extra):
    d = {'schema': 'baodian_intake_v1', 'batch': name, 'exams': exams, 'books': list(books),
         'profiles': profiles if profiles is not None else {'bixiu3': P3}, 'workdir': str(workdir or (W / ('wd_' + name)))}
    d.update(extra)
    p = W / f'm_{name}.json'
    p.write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    return p

def rec(case, rc, out, err, dt, note=''):
    log.append({'case': case, 'rc': rc, 'stdout_tail': out[-600:], 'stderr_tail': err[-600:], 'seconds': dt, 'note': note})
    print(f'== {case} rc={rc} ({dt}s) {note}\n  stdout: {out.strip()[-300:]}\n  stderr: {err.strip()[-300:]}')

# A1 归属表路径写错 → 是否当输入错误（退出2）？
m = man('a1', [{'exam_id': 'BJ-2026-CY-QIZHONG'}])
rc, o, e, dt = run(['status', '--manifest', m, '--attribution-csv', W / 'no_such_attr.csv', '--report', W / 'a1.json', '--quiet'])
rep = json.loads((W / 'a1.json').read_text()) if (W / 'a1.json').is_file() else None
s4 = rep['rows'][0]['steps'][3] if rep else None
rec('A1 --attribution-csv 不存在', rc, o, e, dt, f'step4={s4 and s4["status"]} reason={s4 and s4["reason"][:80]}')

# A2 题库根写错
rc, o, e, dt = run(['status', '--manifest', m, '--bank', W / 'no_such_bank', '--report', W / 'a2.json', '--quiet'])
rep = json.loads((W / 'a2.json').read_text()) if (W / 'a2.json').is_file() else None
rec('A2 --bank 不存在', rc, o, e, dt, 'steps=' + (str([s['status'] for s in rep['rows'][0]['steps']]) if rep else ''))

# A3 重跑同一 --report（状态表本该反复跑）
rc, o, e, dt = run(['status', '--manifest', m, '--report', W / 'a1.json', '--quiet'])
rec('A3 重跑写同一 --report', rc, o, e, dt)

# A4 --report 合法 + --md 受保护 → 退出3，但 --report 是否已落盘（原子性）
rp = W / 'a4.json'; mdp = R / '后勤管理' / 'intake_review_probe_should_not_exist.md'
rc, o, e, dt = run(['status', '--manifest', m, '--report', rp, '--md', mdp, '--quiet'])
rec('A4 --md 受保护、--report 合法', rc, o, e, dt, f'report_left_behind={rp.is_file()} md_exists={mdp.exists()}')

# A5 --report 等于清单本身（输入）
rc, o, e, dt = run(['status', '--manifest', m, '--report', m, '--quiet'])
rec('A5 --report == 清单', rc, o, e, dt)

# A6 符号链接逃逸：临时目录里的链接指向仓库受保护目录
link = W / 'link_to_houqin'
os.symlink(R / '后勤管理', link)
tgt = R / '后勤管理' / 'intake_review_symlink_probe.json'
rc, o, e, dt = run(['status', '--manifest', m, '--report', link / 'intake_review_symlink_probe.json', '--quiet'])
rec('A6 --report 经符号链接落到 后勤管理/', rc, o, e, dt, f'written={tgt.exists()}')

# A7 --report 后缀不是 .json
rc, o, e, dt = run(['status', '--manifest', m, '--report', W / 'a7.txt', '--quiet'])
rec('A7 --report 后缀 .txt', rc, o, e, dt, f'written={(W / "a7.txt").exists()}')

# A8 --report 落 SK 目录
skp = R / '.claude/skills/beijing-gaokao-politics/scripts/intake_probe.json'
rc, o, e, dt = run(['status', '--manifest', m, '--report', skp, '--quiet'])
rec('A8 --report 落 Skill 目录', rc, o, e, dt, f'written={skp.exists()}')

# A9 --report 落候选目录的 构建/ 之外（C/审查/）
cp = C / '审查' / 'intake_probe_should_not_exist.json'
rc, o, e, dt = run(['status', '--manifest', m, '--report', cp, '--quiet'])
rec('A9 --report 落 C/审查/（构建/之外）', rc, o, e, dt, f'written={cp.exists()}')

# A10 exam_id 路径穿越/非法卷号
m10 = man('a10', [{'exam_id': '../indexes'}, {'exam_id': 'not-an-exam'}])
rc, o, e, dt = run(['status', '--manifest', m10, '--report', W / 'a10.json', '--quiet'])
rep = json.loads((W / 'a10.json').read_text()) if (W / 'a10.json').is_file() else None
rec('A10 exam_id 非法（../indexes、not-an-exam）', rc, o, e, dt,
    'steps=' + (str([[s['status'] for s in r['steps']] for r in rep['rows']]) if rep else ''))

# A11 exam_id 非字符串
m11 = man('a11', [{'exam_id': 123}])
rc, o, e, dt = run(['status', '--manifest', m11, '--quiet'])
rec('A11 exam_id=123（非字符串）', rc, o, e, dt, f'traceback_in_stderr={"Traceback" in e}')

# A12 books 重复
m12 = man('a12', [{'exam_id': 'BJ-2026-CY-QIZHONG'}], books=('bixiu3', 'bixiu3'))
rc, o, e, dt = run(['status', '--manifest', m12, '--quiet', '--report', W / 'a12.json'])
rep = json.loads((W / 'a12.json').read_text()) if (W / 'a12.json').is_file() else None
rec('A12 books 重复', rc, o, e, dt, f'combos={rep and rep["summary"]["combos"]}')

# A13 profiles 指向 JSON 损坏的文件
bad = W / 'bad_profile.json'; bad.write_text('{oops', encoding='utf-8')
m13 = man('a13', [{'exam_id': 'BJ-2026-CY-QIZHONG'}], profiles={'bixiu3': str(bad)})
rc, o, e, dt = run(['status', '--manifest', m13, '--quiet'])
rec('A13 配置 JSON 损坏', rc, o, e, dt, f'traceback_in_stderr={"Traceback" in e}')

# A14 bixiu3 书名但配置给冻结册副本（必修二冻结配置）
m14 = man('a14', [{'exam_id': 'BJ-2026-CY-QIZHONG'}], profiles={'bixiu3': str(C / 'profiles_cloud/bixiu2_frozen_test.json')})
rc, o, e, dt = run(['status', '--manifest', m14, '--quiet', '--report', W / 'a14.json'])
rec('A14 bixiu3 书名 + 冻结册配置（只读应可跑）', rc, o, e, dt)

# A15 files 模式（新原件，尚无 exam_id）
m15 = man('a15', [{'files': [str(R / '00_共同资料/原材料/不存在的卷.pdf')], 'claimed_id': 'BJ-2027-HD-QIZHONG'},
                  {'files': [str(R / '00_共同资料/原材料/x.pdf')]}])
rc, o, e, dt = run(['status', '--manifest', m15, '--report', W / 'a15.json', '--quiet'])
rep = json.loads((W / 'a15.json').read_text()) if (W / 'a15.json').is_file() else None
rec('A15 files 模式', rc, o, e, dt, 'rows=' + (json.dumps([[ (s['status'], (s['next_command'] or '')[:160]) for s in r['steps'][:3]] for r in rep['rows']], ensure_ascii=False) if rep else ''))

# A16 init：书名未知/卷号乱写是否被校验
rc, o, e, dt = run(['init', '--out', W / 'init_a16' / 'm.json', '--batch', 'x', '--book', 'no_such_book', '--exam-id', '乱写'])
rec('A16 init --book 未知书名', rc, o, e, dt, f'manifest_written={(W / "init_a16" / "m.json").is_file()}')

# A17 init：workdir 在仓库外任意位置（非临时目录）
evil = Path('/home/user/intake_review_probe_outside_repo')
rc, o, e, dt = run(['init', '--out', W / 'init_a17' / 'm.json', '--batch', 'x', '--workdir', evil])
rec('A17 init --workdir 在仓库外（非临时目录）', rc, o, e, dt, f'created={evil.exists()}')
if evil.exists(): shutil.rmtree(evil)

# A18 init：--out 父目录不存在
rc, o, e, dt = run(['init', '--out', W / 'no' / 'such' / 'dir' / 'm.json', '--batch', 'x'])
rec('A18 init --out 父目录不存在', rc, o, e, dt, f'traceback_in_stderr={"Traceback" in e}')

# A19 init 默认 workdir 下 per-book 子目录是否建好（05_placement/<书>/ 等）
rc, o, e, dt = run(['init', '--out', W / 'init_a19' / 'm.json', '--batch', 'b19', '--book', 'bixiu3', '--exam-id', 'BJ-2026-CY-QIZHONG'])
wd = W / 'init_a19' / '入书_b19'
rec('A19 init 目录骨架', rc, o, e, dt, 'dirs=' + str(sorted(str(p.relative_to(wd)) for p in wd.rglob('*') if p.is_dir())))

json.dump(log, open(S / 'probe_adv_log.json', 'w'), ensure_ascii=False, indent=1)
