import sys
sys.dont_write_bytecode = True
from pathlib import Path
C = Path('/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
sys.path.insert(0, str(C))
import placement_suggest as ps  # noqa
from profile_lib import load_profile  # noqa
REPO = Path('/home/user/zhengzhibaodianzhizuo')
BOOK3 = REPO / '必修三_最新Skill修订_20260913' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
PROFILE = C / 'profiles_cloud' / 'bixiu3.json'
BANK = REPO / 'DeepSeek_政治题库资料库_20260918'

def load():
    prof = load_profile(str(PROFILE))
    book = ps.load_book(str(BOOK3), prof)
    mi = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
    fa = ps.block_fields_all(book['blocks'], mi)
    idx = ps.build_indices(fa, ps.DEFAULT_PARAMS['ngram_sizes'])
    return prof, book, idx

def md(key):
    p = ps.find_md_path(BANK, key)
    if not p.is_file():
        return None, None
    t = p.read_text(encoding='utf-8', errors='replace')
    try:
        return ps.parse_question_md(t, key), t
    except ps.InputError:
        return None, t
