import sys, os, json
sys.dont_write_bytecode = True
from pathlib import Path
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
SK = R / '.claude/skills/beijing-gaokao-politics/scripts'
WORK = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_block_insert_r3/work')  # 本地重跑时改成任意临时目录
sys.path.insert(0, str(C)); sys.path.insert(0, str(SK))
import block_insert as bi
import docx_lib as dl
import batch_health as bh
import apply_patch as ap
W = bh.W
BOOK = R / '必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
BOOK_SHA = 'c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
PROF = C / 'profiles_cloud/bixiu3.json'
TOOL = C / 'block_insert.py'
import subprocess, shutil
def run(args, debug=False):
    cmd = [sys.executable, str(TOOL)] + (['--debug'] if debug else []) + [str(a) for a in args]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    return r.returncode, r.stdout, r.stderr
def copy_book(name):
    p = WORK / name
    if p.exists(): p.unlink()
    shutil.copyfile(BOOK, p)
    return p
def wjson(name, obj):
    p = WORK / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding='utf-8')
    return p
