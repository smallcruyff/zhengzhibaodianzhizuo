import sys
sys.dont_write_bytecode = True
import os, json, re, zipfile, shutil, subprocess, hashlib
from pathlib import Path
R = Path('/home/user/zhengzhibaodianzhizuo')
C = R / '必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925'
SK = R / '.claude/skills/beijing-gaokao-politics/scripts'
HERE = Path(__file__).resolve().parent
WORK = HERE / 'work'  # 探针产物（大 DOCX）写这里；审查时实际用的是云端临时区 scratchpad/review_block_insert_r4/work
WORK.mkdir(exist_ok=True)
sys.path.insert(0, str(C)); sys.path.insert(0, str(SK))
import block_insert as bi
import docx_lib as dl
import batch_health as bh
import apply_patch as ap
from lxml import etree
W = bh.W
BOOK = R / '必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
BOOK_SHA = 'c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
PROF = C / 'profiles_cloud/bixiu3.json'
TOOL = C / 'block_insert.py'

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def run_tool(args, timeout=600, debug=False):
    cmd = [sys.executable, str(TOOL)] + (['--debug'] if debug else []) + list(args)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=env)
    return r.returncode, r.stdout, r.stderr

_ctx = {}
def style_ctx(docx=BOOK):
    key = str(docx)
    if key in _ctx: return _ctx[key]
    with zipfile.ZipFile(docx) as z:
        st = etree.fromstring(z.read('word/styles.xml'))
    font_idx, based, name = {}, {}, {}
    for s in st.iter(W + 'style'):
        sid = s.get(W + 'styleId')
        rf = s.find(f'{W}rPr/{W}rFonts')
        b = s.find(W + 'basedOn')
        n = s.find(W + 'name')
        font_idx[sid] = rf.get(W + 'eastAsia') if rf is not None else None
        based[sid] = b.get(W + 'val') if b is not None else None
        name[sid] = n.get(W + 'val') if n is not None else sid
    rf0 = st.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}rFonts')
    dfont = rf0.get(W + 'eastAsia') if rf0 is not None else None
    _ctx[key] = (font_idx, based, name, dfont, bh.Styles(st))
    return _ctx[key]

def eff_font(p, docx=BOOK):
    font_idx, based, name, dfont, S = style_ctx(docx)
    ps = p.find(f'{W}pPr/{W}pStyle')
    sid = ps.get(W + 'val') if ps is not None else S.default_pstyle
    def chain(s):
        seen = set()
        while s and s not in seen:
            seen.add(s)
            if font_idx.get(s): return font_idx[s]
            s = based.get(s)
        return dfont
    for r, txt in ap._run_spans(p):
        if not txt.strip(): continue
        rpr = r.find(W + 'rPr')
        rf = rpr.find(W + 'rFonts') if rpr is not None else None
        if rf is not None and rf.get(W + 'eastAsia'):
            return rf.get(W + 'eastAsia')
        return chain(sid)
    return None

def pstyle_name(p, docx=BOOK):
    font_idx, based, name, dfont, S = style_ctx(docx)
    ps = p.find(f'{W}pPr/{W}pStyle')
    sid = ps.get(W + 'val') if ps is not None else S.default_pstyle
    return name.get(sid, sid)
