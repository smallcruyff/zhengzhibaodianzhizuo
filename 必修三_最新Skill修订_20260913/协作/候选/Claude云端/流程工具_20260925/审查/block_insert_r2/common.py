import sys
sys.dont_write_bytecode = True
import json, os, shutil, subprocess, zipfile, io
from pathlib import Path
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
TOOL = C / 'block_insert.py'
PROF = C / 'profiles_cloud/bixiu3.json'
BOOK = R / '必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
BOOK_SHA = 'c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
WORK = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_block_insert_r2/work')
WORK.mkdir(parents=True, exist_ok=True)
ENV = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')

def fresh(name):
    p = WORK / name
    if p.exists(): p.unlink()
    shutil.copyfile(BOOK, p)
    return p

def run(args, debug=False):
    cmd = [sys.executable, str(TOOL)] + (['--debug'] if debug else []) + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True, env=ENV, timeout=600)
    return r.returncode, r.stdout, r.stderr

def unit(content, title='例题 93　2099审查探针卷第1题', anchor=None, template='例题 3　2024朝阳二模第18题',
         sz='approved_edit', sha=BOOK_SHA, extra=None):
    ins = {'id': 'X1', 'anchor': anchor or {'after_block': {'title_contains': '例题 3　2024朝阳二模第18题'}},
           'template_block': {'title_contains': template}, 'title': title, 'source_zone': sz,
           'reason': '审查探针', 'content': content}
    if extra: ins.update(extra)
    return {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': sha,
            'approved_by': 'claude:review-r2', 'approval_ref': '审查探针', 'inserts': [ins]}

def write_unit(u, name):
    p = WORK / name
    p.write_text(json.dumps(u, ensure_ascii=False, indent=1), encoding='utf-8')
    return p

def apply(u, name, extra_args=(), debug=False):
    parent = fresh(name + '_parent.docx')
    up = write_unit(u, name + '_insert.json')
    out = WORK / (name + '_out.docx')
    rep = WORK / (name + '_report.json')
    for p in (out, rep, out.with_name(out.stem + '_renumbered.docx')):
        if p.exists(): p.unlink()
    rc, so, se = run(['apply', '--docx', parent, '--insert', up, '--out', out, '--profile', PROF, '--report', rep] + list(extra_args), debug)
    repj = json.loads(rep.read_text(encoding='utf-8')) if rep.exists() else {}
    return rc, so, se, out, repj
