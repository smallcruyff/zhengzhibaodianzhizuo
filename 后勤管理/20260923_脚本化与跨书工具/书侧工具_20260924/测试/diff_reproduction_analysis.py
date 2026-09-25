#!/usr/bin/env python3
"""对 diff() 生成的补丁做逐条可行性画像（不是 apply_patch.py 的一部分，只是本工具测试用的分析脚本）。

apply_patch 的 check/apply 是整批要么全过要么中止（按规格"所有 op 先在原稿上定位，互不依赖；
……任何一条校验失败 → 整批中止"），所以没法直接从一次 apply 调用里读出"1652 条里有多少条本身是
站得住的"。这里对每条 op 单独跑一遍"锚点能否唯一定位 + 是否落在题面区却没给 source_zone + 是否
结构过复杂 + 新文字是否过词表"，不做整批互斥判断（不查同段冲突），统计各类失败原因，
如实反映"diff 生成的补丁，改一步中止之外，到底有多大比例是本来就可以人工按类型放行的"。
"""
import json
import sys
import time
from pathlib import Path

SKILL = Path("/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts")
sys.path.insert(0, str(SKILL))
sys.dont_write_bytecode = True
import batch_health as bh  # noqa: E402
import docx_lib as dl  # noqa: E402
import apply_patch as ap  # noqa: E402
from profile_lib import load_profile  # noqa: E402


def analyze(old_path, patch_path, book='bixiu3'):
    t0 = time.time()
    prof = load_profile(book)
    d = dl.open_docx(old_path)
    import zipfile
    from lxml import etree as _E
    with zipfile.ZipFile(d.path) as z:
        styles_xml = _E.fromstring(z.read('word/styles.xml')) if 'word/styles.xml' in z.namelist() else None
    styles_obj = bh.Styles(styles_xml)
    zone, para_to_block, blocks, P = ap.zones_of(d, prof)
    tag_list, wlist = bh._word_lists(prof)
    allow = bh.cfg(prof, 'student_text.allow_contexts', {}) or {}
    patch = json.loads(Path(patch_path).read_text(encoding='utf-8'))
    reasons = {}
    ok = 0
    # 预取每段文字与样式名，避免 resolve_anchor 对每条 op 都重新遍历全篇 XML（diff 补丁条数大时太慢）。
    texts_cache = [dl.para_text(p) for p in d.paras]
    styles_cache = [ap._style_name(styles_obj, p) for p in d.paras]
    norm_cache = [bh.norm(t) for t in texts_cache]
    from collections import defaultdict
    by_norm = defaultdict(list)
    for i, nt in enumerate(norm_cache):
        by_norm[nt].append(i)

    def fast_resolve(anchor):
        text_want = anchor.get('text')
        contains_want = anchor.get('contains')
        if text_want is None and contains_want is None:
            return None, []
        if text_want is not None:
            base = by_norm.get(bh.norm(text_want), [])
        else:
            base = range(len(texts_cache))
        cands = []
        for i in base:
            t = texts_cache[i]
            if contains_want is not None and contains_want not in t:
                continue
            if anchor.get('style') and not ap._match_style(anchor['style'], styles_cache[i]):
                continue
            if anchor.get('prev') is not None:
                if i == 0 or anchor['prev'] not in texts_cache[i - 1]:
                    continue
            if anchor.get('block') is not None:
                blk = para_to_block.get(i)
                if not blk or anchor['block'] not in (blk.get('title') or ''):
                    continue
            cands.append(i)
        if len(cands) == 1:
            return cands[0], cands
        if len(cands) > 1 and anchor.get('index_hint') is not None:
            narrowed = [c for c in cands if c == anchor['index_hint']]
            if len(narrowed) == 1:
                return narrowed[0], cands
        return None, cands

    for op in patch['ops']:
        kind = op['op']
        anchor = op.get('anchor') or {}
        idx, cands = fast_resolve(anchor)
        if idx is None:
            key = f'anchor_{"zero" if not cands else "ambiguous"}'
            reasons[key] = reasons.get(key, 0) + 1
            continue
        z = zone[idx] if idx < len(zone) else None
        if z in ('source', 'title') and not op.get('source_zone'):
            reasons['source_zone_missing'] = reasons.get('source_zone_missing', 0) + 1
            continue
        if kind in ('replace_paragraph', 'delete_paragraph') and ap._is_complex_paragraph(d.paras[idx]) \
                and not op.get('allow_complex'):
            reasons['complex_paragraph'] = reasons.get('complex_paragraph', 0) + 1
            continue
        bad_word = None
        for txt in ap._new_texts_of(op):
            hit = ap._forbidden_hit(txt, tag_list, wlist, allow)
            if hit:
                bad_word = hit
                break
        if bad_word:
            reasons['forbidden_word'] = reasons.get('forbidden_word', 0) + 1
            continue
        if kind == 'replace_paragraph':
            old_t = texts_cache[idx]
            if old_t != op['old']:
                reasons['old_mismatch'] = reasons.get('old_mismatch', 0) + 1
                continue
        elif kind == 'delete_paragraph':
            old_t = texts_cache[idx]
            if old_t != op['old']:
                reasons['old_mismatch'] = reasons.get('old_mismatch', 0) + 1
                continue
            if ap._in_table_cell_alone(d.paras[idx]):
                reasons['table_cell_alone'] = reasons.get('table_cell_alone', 0) + 1
                continue
        ok += 1
    total = len(patch['ops'])
    return {'total': total, 'individually_ok': ok, 'reasons': reasons,
            'reproduction_rate_if_no_cross_op_conflict': round(ok / total, 4) if total else None,
            'seconds': round(time.time() - t0, 2)}


if __name__ == '__main__':
    OUT = Path(__file__).resolve().parent
    ROOT = Path("/Users/wanglifei/Desktop/gpt和claude共同的小窝")
    cases = [
        ('B03_to_B04', ROOT / "必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/03_第二部分专题.docx",
         OUT / 'B03_to_B04_patch.json'),
        ('B04_to_B52', ROOT / "必修三_最新Skill修订_20260913/协作/候选/Claude/第52批_意见修改_20260923/构建/04_编号与考法计数.docx",
         OUT / 'B04_to_B52_patch.json'),
        ('B51_to_B52_stress', ROOT / "必修三_人工审查历史/第51批_原样审阅_20260923_150732/必修三政治与法治宝典_R31续修_第51批_阶段审查稿.docx",
         OUT / 'B51_to_B52_stress_patch.json'),
    ]
    report = {}
    for name, old_path, patch_path in cases:
        if not patch_path.exists():
            report[name] = {'error': '补丁文件不存在，需先跑 run_tests_apply_patch.py 生成 diff 补丁'}
            continue
        report[name] = analyze(old_path, patch_path)
        print(name, json.dumps(report[name], ensure_ascii=False))
    (OUT / 'diff_reproduction_analysis.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
