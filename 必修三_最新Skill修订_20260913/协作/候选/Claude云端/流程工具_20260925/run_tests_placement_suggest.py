#!/usr/bin/env python3
"""placement_suggest.py 回归测试（返修 r1，2026-09-25）。

只读真实输入（必修三第52批、哲学 R10、题库精简版）；全部输出只写系统临时目录（SCRATCH，每次运行先
清空）与候选目录 构建/placement_suggest/。baseline_guard 在测试前后各跑一次，证明真实输入未被本轮
测试改动。计算密集的评测（10题、全书留一、调参）直接 import placement_suggest 当库用，避免几百次
子进程/几百次重复解析 DOCX；CLI 本身、负例、--report/--format 落盘、五种输入入口另用子进程跑，覆盖
真实入口。

按 任务_新卷入书流水线_20260925.md 里 placement_suggest.py 的 5 组验收组织，另加两组返修新增：
  1 十题验收（分层抽样，key 级“任一命中即算”）
  2 全书留一评估（题块级，严格版，作对照防挑题）
  3 调参：调参集与十题不相交，报告用调好后的固定参数
  4 其他书（哲学 R10，草案配置）跑通
  5 负例
  6 返修 r1 回归：逐条复现 placement_suggest_审查_r1.json 里的 M1-M8/m1-m14（除范围外的 m14），
    每条修前应 FAIL、修后应 PASS
  7 五种新题输入入口（--key 已含在 1/2/5 里；这里补 --md/--text/--keys-file/--params/
    --format md --out）都实际走一遍子进程 CLI

返修 m5/m6：record() 现在都带实测用时（seconds，wall clock，不是估算）；4c 的退出码断言原先因运算符
优先级失效，这版改成显式布尔表达式并单独打印退出码。
"""
import sys

sys.dont_write_bytecode = True  # 本脚本 import placement_suggest 当库用，不留 __pycache__

import json
import math
import random
import re
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOOL = HERE / 'placement_suggest.py'
PROFILE = HERE / 'profiles_cloud' / 'bixiu3.json'
PHIL_PROFILE = HERE / 'profiles_cloud' / 'philosophy.draft.json'
FROZEN_PROFILE = HERE / 'profiles_cloud' / 'bixiu2_frozen_test.json'
BASELINE_GUARD = HERE / 'tools' / 'baseline_guard.py'
BASELINE_BASE = HERE / '构建' / 'baseline_20260925.json'
REPO_ROOT = Path('/home/user/zhengzhibaodianzhizuo')
BOOK3 = REPO_ROOT / '必修三_最新Skill修订_20260913' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
SYNC_MANIFEST = REPO_ROOT / '云端' / '同步清单.json'
BOOK3_SHA_FALLBACK = 'c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
PHIL_BOOK = REPO_ROOT / '其他书工作头' / '哲学' / '哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx'
BANK = REPO_ROOT / 'DeepSeek_政治题库资料库_20260918'

SCRATCH = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/placement_suggest')
BUILD_OUT = HERE / '构建' / 'placement_suggest'

sys.path.insert(0, str(HERE))
import placement_suggest as ps  # noqa: E402
from profile_lib import load_profile  # noqa: E402
import docx_lib as dl_mod  # noqa: E402
import apply_patch as ap_mod  # noqa: E402
try:
    # 返修 m6e（r3）：block_insert.py 是候选目录里另一条工具线的产物，可能正被并行修改甚至暂时
    # 语法损坏；原来的顶层 import 一旦失败，整份测试直接 ImportError 崩掉，一条用例都跑不了。
    # 改成记录错误，只让依赖它的少数用例（M4-r2 端到端核对锚点）记 SKIP，其余用例不受影响。
    import block_insert as bi_mod  # noqa: E402
    BI_IMPORT_ERR = None
except Exception as _bi_e:
    bi_mod = None
    BI_IMPORT_ERR = f'{type(_bi_e).__name__}: {_bi_e}'

results = []


def record(name, ok, detail='', seconds=None):
    # 返修 m8（r2）：fn() 返回 (None, detail) 表示“数据当前不满足这条用例的前提，跳过”（如全书当前
    # 没有标题重名的组），原来 bool(None)=False 会被当 FAIL 打印、混进失败计数；改成单独的 SKIP
    # 状态，不计入 failed。
    status = 'SKIP' if ok is None else ('PASS' if ok else 'FAIL')
    row = {'test': name, 'ok': ok, 'status': status, 'detail': detail}
    if seconds is not None:
        row['seconds'] = round(seconds, 3)
    results.append(row)
    tail = f'  [{seconds:.2f}s]' if seconds is not None else ''
    print(status, name, ('- ' + detail) if detail else '', tail)


def timed(name, fn):
    """跑 fn()（返回 (ok, detail)），量实际用时，record 一条。"""
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, f'{type(e).__name__}: {e}'
    record(name, ok, detail, seconds=time.time() - t0)


def run(args, timeout=180):
    t0 = time.time()
    p = subprocess.run([sys.executable, str(TOOL)] + args, capture_output=True, text=True, timeout=timeout)
    return p.returncode, p.stdout, p.stderr, time.time() - t0


def run_json(args, timeout=180):
    code, out, err, dt = run(args, timeout=timeout)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        data = None
    return code, data, err, dt


def baseline_check(label):
    t0 = time.time()
    p = subprocess.run([sys.executable, str(BASELINE_GUARD), 'check', '--base', str(BASELINE_BASE)],
                        capture_output=True, text=True, timeout=180)
    ok = p.returncode == 0
    record(f'baseline_guard（真实输入未变，{label}）', ok, p.stdout.strip()[:400] if not ok else '',
           seconds=time.time() - t0)
    return ok


def setup():
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    BUILD_OUT.mkdir(parents=True, exist_ok=True)
    for old in BUILD_OUT.glob('test_*.json'):
        old.unlink()
    for old in BUILD_OUT.glob('test_*.md'):
        old.unlink()


def book3_expected_sha():
    """返修 m6：原来是写死常量，没读 同步清单.json；改成读清单，读不到才退回常量并在 detail 里说明。"""
    try:
        manifest = json.loads(SYNC_MANIFEST.read_text(encoding='utf-8'))
        sha = manifest.get('book3_working_head_sha256')
        if sha:
            return sha, True
    except Exception:
        pass
    return BOOK3_SHA_FALLBACK, False


# ---------------------------------------------------------------- 装书 + 建索引（全测试共用一份，省重复解析）
def load_book_and_indices(docx, profile_path, params=None):
    prof = load_profile(str(profile_path))
    book = ps.load_book(str(docx), prof, expect_sha=None)
    params = params or ps.DEFAULT_PARAMS
    method_intro = ps.build_method_intro(book['doc'], book['heads'], ps.method_desc_style_set(prof))
    fields_all = ps.block_fields_all(book['blocks'], method_intro)
    indices = ps.build_indices(fields_all, params['ngram_sizes'])
    return prof, book, indices


_MD_CACHE = {}


def md_for_key(base_key):
    if base_key in _MD_CACHE:
        return _MD_CACHE[base_key]
    mdp = ps.find_md_path(BANK, base_key)
    if not mdp.is_file():
        _MD_CACHE[base_key] = None
        return None
    try:
        q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), base_key)
    except ps.InputError:
        q = None
    _MD_CACHE[base_key] = q
    return q


def key_stratum(kindset):
    if 'choice' in kindset:
        return '选择题块'
    if 'topic' in kindset or 'topic_case' in kindset:
        return '专题题块'
    if 'subjective' in kindset:
        return '主观题块'
    return None


def keys_by_stratum(blocks):
    """{题键: kind集合}，再按 key_stratum 分层；只收有题库 MD 的题键（parse_question_md 能正常解析，
    返修 M4 后“采用题面小节：无”的题键会在 md_for_key 里抛 InputError 被吃掉、正确地排除在池外）。"""
    kindset = {}
    for b in blocks:
        if b.get('key'):
            kindset.setdefault(b['key'], set()).add(b['kind'])
    strata = {'主观题块': [], '选择题块': [], '专题题块': []}
    for key, ks in kindset.items():
        s = key_stratum(ks)
        if s and md_for_key(key) is not None:
            strata[s].append(key)
    for v in strata.values():
        v.sort()
    return strata, kindset


def _kind_category(k):
    return 'choice' if k == 'choice' else 'subjective'


def lenient_eval(key, kindset_by_key, book, indices, params):
    """key 级、任一命中即算：true_group_keys = 该题键在书里全部题块的 group_key 并集。
    返修 M2：额外核查询题型（MD 解析出的 kind）与书中该题键的真实题型类别是否一致——不一致时
    hit1/hit3 记 None（评测口径里不计命中，也不计未命中），单独用 kind_mismatch 标出，避免题型误判
    误把候选池换成另一类、恰好撞上同名组这种巧合算成命中（原 BJ-2026-BJ-GAOKAO-Q18 那类问题）。
    返修 m8：同时标 unreachable——该题键的全部题块在候选池里因剔重逻辑被整组排除时，结构上不可能
    命中，不是排序算法的锅。"""
    q = md_for_key(key)
    if q is None:
        return None
    true_blocks = [b for b in book['blocks'] if b.get('key') == key]
    true_kinds = {b['kind'] for b in true_blocks}
    kind_mismatch = _kind_category(q['kind']) not in {_kind_category(k) for k in true_kinds}
    q = dict(q)
    q['base_key'] = key
    true_groups = {ps.group_key_of(b) for b in true_blocks}
    q['true_group_keys'] = true_groups
    ranked, exclude, _ = ps.rank_for_query(q, book, indices, params)
    rank = ps.true_rank_of(ranked, true_groups)
    reachable_idxs = {i for i, b in enumerate(book['blocks']) if ps.group_key_of(b) in true_groups} - exclude
    unreachable = not reachable_idxs
    hit1 = None if kind_mismatch else (rank == 1)
    hit3 = None if kind_mismatch else (rank is not None and rank <= 3)
    # 返修 m6f（r3）：十题日志原来只打印排名，不打印真实考法名称，看日志时想知道“真实考法叫什么”
    # 还得回头翻代码/JSON。这里把 group_label 算出来一起返回，print 时直接带上。
    gk_is_choice = {}
    for b in true_blocks:
        gk = ps.group_key_of(b)
        gk_is_choice[gk] = gk_is_choice.get(gk, False) or (b['kind'] == 'choice')
    true_labels = sorted(ps.group_label(gk, gk_is_choice.get(gk, False)) for gk in true_groups)
    return {'key': key, 'kind': list(kindset_by_key.get(key, [])), 'query_kind': q['kind'], 'rank': rank,
            'hit1': hit1, 'hit3': hit3, 'kind_mismatch': kind_mismatch, 'unreachable': unreachable,
            'n_true_groups': len(true_groups), 'n_ranked': len(ranked), 'true_group_labels': true_labels}


def strict_eval_block(i, book, indices, params):
    """题块级、严格版：true_group = 这一个题块自己的 group_key（不看同题键的其它实例）。
    返修 M2/m8：同 lenient_eval，加 kind_mismatch 与 unreachable。"""
    b = book['blocks'][i]
    q = md_for_key(b['key'])
    if q is None:
        return None
    kind_mismatch = _kind_category(q['kind']) != _kind_category(b['kind'])
    q = dict(q)
    q['base_key'] = b['key']
    true_gk = ps.group_key_of(b)
    q['true_group_keys'] = {true_gk}
    ranked, exclude, _ = ps.rank_for_query(q, book, indices, params)
    rank = ps.true_rank_of(ranked, q['true_group_keys'])
    same_group_idxs = {j for j, bb in enumerate(book['blocks']) if ps.group_key_of(bb) == true_gk}
    unreachable = bool(same_group_idxs) and same_group_idxs.issubset(exclude)
    hit1 = None if kind_mismatch else (rank == 1)
    hit3 = None if kind_mismatch else (rank is not None and rank <= 3)
    return {'block_id': b['id'], 'key': b['key'], 'kind': b['kind'], 'rank': rank,
            'hit1': hit1, 'hit3': hit3, 'kind_mismatch': kind_mismatch, 'unreachable': unreachable}


# ---------------------------------------------------------------- 1. 十题验收
SEED_10 = 20260925
COUNTS_10 = {'主观题块': 4, '选择题块': 3, '专题题块': 3}


def pick_10(strata):
    rnd = random.Random(SEED_10)
    picked = {}
    for s, n in COUNTS_10.items():
        pool = list(strata[s])
        rnd.shuffle(pool)
        picked[s] = pool[:n]
    return picked


def group1(book, indices, kindset_by_key, params, label='默认参数'):
    t0 = time.time()
    strata, _ = keys_by_stratum(book['blocks'])
    picked = pick_10(strata)
    flat = [k for v in picked.values() for k in v]
    record(f'1a 十题分层抽样可复现（seed={SEED_10}，固定种子+按题键排序后 shuffle+截取，主观4/选择3/专题3）',
           len(flat) == 10, f'picked={picked}')
    rows = [lenient_eval(k, kindset_by_key, book, indices, params) for k in flat]
    rows = [r for r in rows if r is not None]
    eligible = [r for r in rows if not r['kind_mismatch']]
    mismatched = [r for r in rows if r['kind_mismatch']]
    hit1 = sum(1 for r in eligible if r['hit1'])
    hit3 = sum(1 for r in eligible if r['hit3'])
    for r in rows:
        tag = '题型不一致，不计命中' if r['kind_mismatch'] else f"hit1={r['hit1']} hit3={r['hit3']}"
        # 返修 m9（r2）：日志里补打印 n_true_groups——同一题键落在几个考法（规格要求“注明”）。
        # 返修 m6f（r3）：只打排名不打真实考法名称，看日志想知道“真实考法叫什么”还得翻 JSON；
        # 补打印 true_group_labels。
        labels = '；'.join(r.get('true_group_labels') or []) or '（无）'
        print(f"    {r['key']} kind={r['kind']} query_kind={r['query_kind']} "
              f"真实考法第{r['rank']}名（候选总数{r['n_ranked']}，该题键落在{r['n_true_groups']}个考法："
              f"{labels}） {tag}")
    record(f'1b 十题命中率（{label}）：前1 {hit1}/{len(eligible)}，前3 {hit3}/{len(eligible)}'
           + (f'（另有 {len(mismatched)} 题查询题型≠书中题型，已剔除不计，见 M2）' if mismatched else ''),
           len(rows) == 10, f'hit1={hit1}/{len(eligible)} hit3={hit3}/{len(eligible)} '
           f'mismatched={[r["key"] for r in mismatched]}', seconds=time.time() - t0)
    return {'rows': rows, 'hit1': hit1, 'hit3': hit3, 'n': len(eligible),
            'n_kind_mismatch': len(mismatched)}, flat


# ---------------------------------------------------------------- 2. 全书留一评估
def group2(book, indices, kindset_by_key, params, label='默认参数'):
    blocks = book['blocks']
    idxs = [i for i, b in enumerate(blocks) if b.get('key') and md_for_key(b['key']) is not None]
    t0 = time.time()
    rows = [strict_eval_block(i, book, indices, params) for i in idxs]
    rows = [r for r in rows if r is not None]
    dt = time.time() - t0
    eligible = [r for r in rows if not r['kind_mismatch']]
    mismatched = [r for r in rows if r['kind_mismatch']]
    unreachable = [r for r in eligible if r['unreachable']]
    by_kind = {}
    for r in eligible:
        by_kind.setdefault(r['kind'], []).append(r)
    overall_hit1 = sum(1 for r in eligible if r['hit1'])
    overall_hit3 = sum(1 for r in eligible if r['hit3'])
    detail = [f"总体 {overall_hit1}/{len(eligible)} (前1) {overall_hit3}/{len(eligible)} (前3)",
              f"题型不一致剔除 {len(mismatched)}（M2）", f"结构上不可能命中 {len(unreachable)}（m8，仍计入分母）"]
    per_kind = {}
    for k, rs in sorted(by_kind.items()):
        h1 = sum(1 for r in rs if r['hit1'])
        h3 = sum(1 for r in rs if r['hit3'])
        per_kind[k] = {'n': len(rs), 'hit1': h1, 'hit3': h3}
        detail.append(f"{k}: {h1}/{len(rs)}(前1) {h3}/{len(rs)}(前3)")
    record(f'2a 全书留一评估（{label}，{len(rows)} 题块，{dt:.1f}s）：题块级严格口径，作十题结果的对照',
           len(rows) > 500, '；'.join(detail), seconds=dt)
    return {'n': len(eligible), 'hit1': overall_hit1, 'hit3': overall_hit3, 'by_kind': per_kind,
            'n_kind_mismatch': len(mismatched), 'n_unreachable': len(unreachable), 'seconds': round(dt, 1)}


# ---------------------------------------------------------------- 3. 调参（调参集与十题不相交）
SEED_TUNE = 20260926
TUNE_N = {'主观题块': 16, '选择题块': 12, '专题题块': 12}
PARAM_GRID_WEIGHTS = [
    {'material': 1.0, 'ask': 1.8, 'rubric': 1.3, 'method': 0.6},   # 默认
    {'material': 1.0, 'ask': 1.0, 'rubric': 1.0, 'method': 1.0},   # 等权
    {'material': 0.6, 'ask': 2.2, 'rubric': 1.0, 'method': 0.4},   # 更重设问
    {'material': 1.2, 'ask': 1.4, 'rubric': 1.8, 'method': 0.3},   # 更重细则
    {'material': 1.0, 'ask': 1.8, 'rubric': 1.3, 'method': 0.0},   # 不用考法字段
]
PARAM_GRID_AGG = [(1, 1.0), (3, 0.6), (3, 1.0), (5, 0.5)]


def pick_tune_set(strata, exclude_keys):
    rnd = random.Random(SEED_TUNE)
    picked = []
    for s, n in TUNE_N.items():
        pool = [k for k in strata[s] if k not in exclude_keys]
        rnd.shuffle(pool)
        picked += pool[:n]
    return picked


def group3(book, indices, kindset_by_key, exclude_keys):
    t0 = time.time()
    strata, _ = keys_by_stratum(book['blocks'])
    tune_keys = pick_tune_set(strata, set(exclude_keys))
    overlap = set(tune_keys) & set(exclude_keys)
    record('3a 调参集与十题评估集不相交（先从题键池里剔除十题的 key 再抽样）', not overlap,
           f'调参集{len(tune_keys)}题，重叠={overlap}')
    best = None
    grid_results = []
    for w in PARAM_GRID_WEIGHTS:
        for top_k, mix in PARAM_GRID_AGG:
            params = {'weights': w, 'agg_top_k': top_k, 'agg_mix': mix,
                      'bm25_k1': ps.DEFAULT_PARAMS['bm25_k1'], 'bm25_b': ps.DEFAULT_PARAMS['bm25_b'],
                      'ngram_sizes': ps.DEFAULT_PARAMS['ngram_sizes']}
            hit1 = hit3 = 0
            for key in tune_keys:
                r = lenient_eval(key, kindset_by_key, book, indices, params)
                if r is None or r['kind_mismatch']:
                    continue
                hit1 += r['hit1']
                hit3 += r['hit3']
            score = hit1 * 2 + hit3   # 前1优先，前3次之
            grid_results.append({'weights': w, 'agg_top_k': top_k, 'agg_mix': mix,
                                  'hit1': hit1, 'hit3': hit3, 'score': score})
            if best is None or score > best['score']:
                best = grid_results[-1]
    dt = time.time() - t0
    record(f'3b 调参网格（{len(PARAM_GRID_WEIGHTS)}×{len(PARAM_GRID_AGG)}={len(grid_results)} 组，'
           f'调参集{len(tune_keys)}题）跑通，选出最优组合',
           best is not None, f"最优: weights={best['weights']} agg_top_k={best['agg_top_k']} "
           f"agg_mix={best['agg_mix']} → hit1={best['hit1']}/{len(tune_keys)} hit3={best['hit3']}/{len(tune_keys)}",
           seconds=dt)
    tuned_params = {'weights': best['weights'], 'agg_top_k': best['agg_top_k'], 'agg_mix': best['agg_mix'],
                     'bm25_k1': ps.DEFAULT_PARAMS['bm25_k1'], 'bm25_b': ps.DEFAULT_PARAMS['bm25_b'],
                     'ngram_sizes': ps.DEFAULT_PARAMS['ngram_sizes']}
    out = BUILD_OUT / 'tuned_params.json'
    out.write_text(json.dumps({'tuned_on_n_keys': len(tune_keys), 'grid': grid_results, 'chosen': tuned_params},
                               ensure_ascii=False, indent=1), encoding='utf-8')
    return tuned_params, tune_keys


# ---------------------------------------------------------------- 4. 其他书（哲学 R10，草案配置）
def group4():
    if not PHIL_BOOK.is_file():
        record('4a 哲学 R10 书稿存在', False, f'找不到：{PHIL_BOOK}')
        return
    t0 = time.time()
    try:
        prof, book, indices = load_book_and_indices(PHIL_BOOK, PHIL_PROFILE)
    except Exception as e:
        record('4a 哲学 R10（草案配置）能装书、切出题块、建索引', False, f'{type(e).__name__}: {e}',
               seconds=time.time() - t0)
        return
    record('4a 哲学 R10（草案配置 philosophy.draft.json）能装书、切出题块、建索引', len(book['blocks']) > 0,
           f"blocks={len(book['blocks'])} by_kind={dict(Counter(b['kind'] for b in book['blocks']))}",
           seconds=time.time() - t0)
    strata, kindset_by_key = keys_by_stratum(book['blocks'])
    n_with_md = sum(len(v) for v in strata.values())
    record('4b 哲学题块能在题库（module_hint=哲学与文化）里找到对应 MD', n_with_md > 0,
           f"有MD的题键数：{ {k: len(v) for k, v in strata.items()} }")
    code, out, err, dt = run(['--docx', str(PHIL_BOOK), '--profile', str(PHIL_PROFILE),
                               '--key', 'BJ-2020-BJ-GAOKAO-Q3', '--format', 'md', '--top-k', '3'])
    # 返修 m6：原断言 `code in (0,1) and '候选考法' in out or (...)` 因 and/or 优先级，'候选考法'
    # 那半句其实从没被判过。改成显式布尔表达式，且真的检查退出码。
    code_ok = code in (0, 1)
    out_ok = ('##' in out and len(out) > 50)
    record('4c CLI 对哲学书跑一条真实题键、能出候选（不保证命中，只要求流程走通）',
           code_ok and out_ok,
           f'exit={code}（code_ok={code_ok}） out_ok={out_ok} out[:200]={out[:200]!r} err={err[:200]!r}',
           seconds=dt)
    if n_with_md >= 10:
        rnd = random.Random(SEED_10 + 1)
        sample_keys = []
        for v in strata.values():
            pool = list(v)
            rnd.shuffle(pool)
            sample_keys += pool[:6]
        rows = [lenient_eval(k, kindset_by_key, book, indices, ps.DEFAULT_PARAMS) for k in sample_keys]
        rows = [r for r in rows if r is not None]
        eligible = [r for r in rows if not r['kind_mismatch']]
        if eligible:
            hit1 = sum(1 for r in eligible if r['hit1'])
            hit3 = sum(1 for r in eligible if r['hit3'])
            record(f'4d 哲学书命中率能算就报（{len(eligible)} 题抽样，非正式配置，仅供参考）', True,
                   f'hit1={hit1}/{len(eligible)} hit3={hit3}/{len(eligible)}')


# ---------------------------------------------------------------- 5. 负例
def group5():
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE),
                               '--key', 'BJ-2099-NOSUCH-YIMO-Q1'])
    record('5a 题键不在题库 → 退出2', code == 2, f'exit={code} err={err.strip()[:200]}', seconds=dt)

    import docx as pydocx
    blank = SCRATCH / 'blank.docx'
    d = pydocx.Document()
    d.add_paragraph('这是一份没有任何题块结构的空文档，仅用于负例测试。')
    d.save(str(blank))
    code, out, err, dt = run(['--docx', str(blank), '--profile', str(PROFILE), '--key', 'BJ-2020-BJ-GAOKAO-Q1'])
    record('5b 书稿按此配置 0 题块 → 退出2', code == 2, f'exit={code} err={err.strip()[:200]}', seconds=dt)

    no_bank_profile = SCRATCH / 'bixiu3_no_bank.json'
    prof = json.loads(PROFILE.read_text(encoding='utf-8'))
    prof.get('sources', {}).pop('bank', None)
    no_bank_profile.write_text(json.dumps(prof, ensure_ascii=False), encoding='utf-8')
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(no_bank_profile),
                               '--key', 'BJ-2020-BJ-GAOKAO-Q1'])
    record('5c 配置缺 sources.bank.root 且未给 --bank → 退出2', code == 2, f'exit={code} err={err.strip()[:200]}',
           seconds=dt)

    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE),
                               '--expect-sha', '0' * 64, '--key', 'BJ-2020-BJ-GAOKAO-Q1'])
    record('5d 父稿 SHA 不符（--expect-sha 给错）→ 退出2', code == 2, f'exit={code} err={err.strip()[:200]}',
           seconds=dt)

    bad_target = REPO_ROOT / '必修三_最新Skill修订_20260913' / 'test_placement_report.json'
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE),
                               '--key', 'BJ-2020-BJ-GAOKAO-Q1', '--report', str(bad_target)])
    wrote = bad_target.exists()
    if wrote:
        bad_target.unlink()
    record('5e --report 落受保护目录（书稿工作区根，不在 构建/ 下）→ 退出3，且未落盘', code == 3 and not wrote,
           f'exit={code} wrote={wrote}', seconds=dt)

    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(FROZEN_PROFILE),
                               '--key', 'BJ-2020-BJ-GAOKAO-Q1',
                               '--report', str(BUILD_OUT / 'test_frozen.json')])
    wrote = (BUILD_OUT / 'test_frozen.json').exists()
    record('5f 冻结配置 + --report → 退出3（docx_lib.guard_write 对 frozen profile 一律拒写，且返修 M8 后'
           '这一步挪到装书之前，属于“立即”拒绝；不给 --report 时仍可只读出候选，见 known_limits）',
           code == 3 and not wrote, f'exit={code} wrote={wrote}', seconds=dt)

    good = BUILD_OUT / 'test_good_report.json'
    if good.exists():
        good.unlink()
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE),
                               '--key', 'BJ-2020-BJ-GAOKAO-Q1', '--report', str(good)])
    record('5g 正例：--report 落候选目录 构建/ 下 → 成功写出', good.is_file() and code in (0, 1),
           f'exit={code} exists={good.is_file()}', seconds=dt)

    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE)])
    record('5h 一个新题输入都不给 → 退出2', code == 2, f'exit={code} err={err.strip()[:200]}', seconds=dt)


# ---------------------------------------------------------------- 6. 返修 r1 回归：逐条复现审查发现
CONFLICT_MD = """## 身份
题型：非选择题

## 题面
材料：
A．经济发展优先
B．生态优先
C．两者并重
D．因地制宜
运用所学知识分析材料。

## 正式评分材料（E1）
未找到该题独立的正式评分材料。
"""

LIST_OPTION_MD = """## 身份
题型：选择题

## 题面
- **A**: 加强宏观调控
- **B**: 减少政府干预
- **C**: 扩大市场准入
- **D**: 完善产权保护

## 正式评分材料（E1）
（未找到，选择题无需此项）
"""


def group6(book, indices, ten_keys, prof):
    # M4-r2 端到端核对要用 apply_patch.zones_of 现算的题块（block_insert 消费的就是这份），和
    # block_index 的题块按标题逐一核对过对齐（见 t_m4r2_e2e 的断言）。只算一次，供本组多个用例共用。
    d_for_bi = dl_mod.open_docx(str(BOOK3))
    _, _, bh_blocks, _ = ap_mod.zones_of(d_for_bi, prof)
    assert [b['title'] for b in book['blocks']] == [b['title'] for b in bh_blocks], \
        'block_index 与 apply_patch.zones_of 切出的题块标题序列不一致，M4-r2 端到端核对的前提不成立'
    block_id_to_idx = {b['id']: i for i, b in enumerate(book['blocks'])}

    # ---- M1：题型字段优先于选项行启发式，冲突时加 flag 不静默覆盖 ----
    def t_m1a():
        q = ps.parse_question_md(CONFLICT_MD, 'synthM1a')
        ok = (q['kind'] == 'subjective') and (q['kind_conflict'] is not None) and (q['e1_present'] is False)
        return ok, f"kind={q['kind']} conflict={bool(q['kind_conflict'])} e1_present={q['e1_present']}"
    timed('M1a 题型字段“非选择题”优先于题面里的 A/B/C/D 选项行启发式（修前会被判成 choice、e1_present '
          '被强制 True）', t_m1a)

    def t_m1b():
        q = ps.parse_question_md(LIST_OPTION_MD, 'synthM1b')
        return q['kind'] == 'choice' and q['kind_conflict'] is None, f"kind={q['kind']}"
    timed('M1b 列表式选项“- **A**: …”（无“A．”标准写法）也能被选项行启发式认出为选择题', t_m1b)

    def t_m1c():
        base = 'BJ-2026-HD-ERMO-Q21'
        mdp = ps.find_md_path(BANK, base)
        if not mdp.is_file():
            return None, '找不到 MD，跳过（环境问题非本工具问题）'
        q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), base)
        return q['kind'] == 'subjective', f"kind={q['kind']} kind_field={q['kind_field_raw']!r}（审查 R01：修前=choice）"
    timed('M1c 实题 BJ-2026-HD-ERMO-Q21（题型字段“非选择题（由同卷结构推断…）”）判为 subjective', t_m1c)

    # ---- M2：题型不一致的查询不计入命中率（这里验证 kind_mismatch 检测本身、以及 M1 修复后
    #      BJ-2026-BJ-GAOKAO-Q18 不再是“伪命中” ----
    def t_m2():
        base = 'BJ-2026-BJ-GAOKAO-Q18'
        mdp = ps.find_md_path(BANK, base)
        if not mdp.is_file():
            return None, '找不到 MD，跳过'
        q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), base)
        true_blocks = [b for b in book['blocks'] if b.get('key') == base]
        if not true_blocks:
            return None, '该题不在本书，跳过（审查评估池外）'
        true_kinds = {b['kind'] for b in true_blocks}
        mismatch = _kind_category(q['kind']) not in {_kind_category(k) for k in true_kinds}
        return (q['kind'] == 'subjective') and (not mismatch), \
            f"query_kind={q['kind']} true_kinds={true_kinds}（审查 R15：修前 query_kind=choice，"\
            f"在 20 个选择组里伪命中第1名；真实考法按主观题排第8）"
    timed('M2 BJ-2026-BJ-GAOKAO-Q18 修 M1 后查询题型与书中题型一致，不再是选择题伪命中', t_m2)

    # ---- M3：E1 节名放宽 + 多候选取第一个有实质内容的 ----
    def t_m3a():
        md = ("## 题面\n材料与设问……\n\n## 答案层\n### 正式评分材料原文\n（未找到该题独立的正式评分"
              "材料。）\n\n### 正式评分材料（E1，限同题等级标准）\n水平1：0-2分……水平4：7-8分……逐点"
              "给分标准如下。\n")
        q = ps.parse_question_md(md, 'synthM3a')
        ok = q['e1_present'] and '限同题等级标准' in (q['e1_header'] or '')
        return ok, f"e1_present={q['e1_present']} e1_header={q['e1_header']!r}"
    timed('M3a 同一 MD 先有空的“正式评分材料原文”、后有带等级分值的“正式评分材料（E1）”——取后者',
          t_m3a)

    def t_m3b():
        md = ("## 题面\n材料与设问……\n\n## 答案层\n### E1阅卷细则原文（原栏：阅卷细则）\n"
              "逐点给分：①制度设计角度2分 ②实施成效角度2分 ③各方主体作用2分，合计不超过6分\n")
        q = ps.parse_question_md(md, 'synthM3b')
        return q['e1_present'] and 'E1阅卷细则原文' in (q['e1_header'] or ''), \
            f"e1_present={q['e1_present']} e1_header={q['e1_header']!r}"
    timed('M3b 节名“E1阅卷细则原文”（不含“正式评分”字样）被认作 E1', t_m3b)

    def t_m3c():
        base = 'BJ-2023-DC-ERMO-Q21'
        mdp = ps.find_md_path(BANK, base)
        if not mdp.is_file():
            return None, '找不到 MD，跳过'
        q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), base)
        return q['e1_present'], f"e1_present={q['e1_present']} e1_header={q['e1_header']!r}（审查 R05：修前 False）"
    timed('M3c 实题 BJ-2023-DC-ERMO-Q21（第76行空节在前，第122行有内容的 E1 节在后）e1_present=True',
          t_m3c)

    # ---- M4：读取指引“无”如实报错；讲评/答案类标题不当题面兜底 ----
    def t_m4a():
        base = 'BJ-2025-CY-YIMO-Q1'
        mdp = ps.find_md_path(BANK, base)
        if not mdp.is_file():
            return None, '找不到 MD，跳过'
        try:
            ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), base)
            return False, '应该抛 InputError（读取指引点名“无”）却没有'
        except ps.InputError as e:
            return '无可用题面' in str(e) or '无' in str(e), str(e)[:200]
    timed('M4a 读取指引“采用题面小节: 无”（无反引号）如实报 InputError，不再拿讲评块当题面（审查 R06）',
          t_m4a)

    def t_m4b():
        md = ("## 读取指引（机器可读）\n- 采用题面小节: 无\n\n"
              "## 讲评来源块（含答案与解析，不得当作题面）\n1、2、6、11、13、14、15\n")
        try:
            ps.parse_question_md(md, 'synthM4b')
            return False, '应该抛 InputError'
        except ps.InputError as e:
            return True, str(e)[:200]
    timed('M4b 合成 MD：读取指引“无”（无反引号写法）+ 只有讲评块可退——确认走的是“无”分支而不是'
          '关键词兜底命中讲评块', t_m4b)

    # ---- M5（r1）/ M4-r2：锚点唯一性 + method_end 兜底 + before_block 重定向 ----
    # 返修 m8：原来按“混合题型”分组统计，和 CLI 实际按 KIND_GROUPS 分池（choice 单独一池，
    # subjective/topic/topic_case 一池）不是一回事；这里改成和 candidate_detail 同口径的分池。
    def _anchors_by_kind():
        combined = [0.0] * len(book['blocks'])
        out = []
        for qkind, kset in ps.KIND_GROUPS.items():
            ranked = ps.aggregate_methods(book['blocks'], combined, kset, set(), ps.DEFAULT_PARAMS)
            for g in ranked:
                gk = g['group_key']
                last_idx = max(g['block_idxs'], key=lambda i: book['blocks'][i]['p_range'][0])
                last_b = book['blocks'][last_idx]
                is_choice = book['blocks'][g['block_idxs'][0]]['kind'] == 'choice'
                anchor, unique, note = ps.anchor_for_group(book['blocks'], gk, last_b, is_choice)
                out.append({'query_kind': qkind, 'group_key': gk, 'last_b': last_b, 'anchor': anchor,
                            'unique': unique, 'note': note})
        return out

    def t_m5():
        rows = _anchors_by_kind()
        title_hits = [r for r in rows if ps._title_hit_count(book['blocks'], r['last_b']['title']) > 1]
        if not title_hits:
            return None, '本书当前没有标题重名的考法组末题，跳过（数据变化导致，非代码问题）'
        # 标题本身不唯一时，anchor_for_group 一律不该给 after_block（否则 block_insert 会 Abort）；
        # 改给的 method_end/before_block 是否恰好也能唯一收窄看具体数据，不强制要求。
        wrong_kind = [r for r in title_hits if next(iter(r['anchor'])) == 'after_block']
        return not wrong_kind, \
            (f"{len(title_hits)} 个组的末题标题本身不唯一，其中 {len(wrong_kind)} 个仍被错误地给了 "
             f"after_block 锚点（审查 probe8：全书 746 个标题里 50 个不唯一，原代码没有这层检查、"
             f"一律给 anchor_title_contains）")
    timed('M5a 标题本身不唯一的考法组，锚点一律改给 method_end/before_block（不再无条件给 after_block）', t_m5)

    def t_m5b():
        rows = _anchors_by_kind()
        n_unique = sum(1 for r in rows if r['unique'])
        n_nonunique = len(rows) - n_unique
        # 期望：绝大多数组走 after_block 且唯一；极少数（如全书唯一一个“【常见表述】”这种通用考法名
        # 在多个节点重复出现）连 method_end 收窄后仍不唯一，如实标 anchor_unique=False，不假装唯一。
        return n_unique > 0, f"考法组共 {len(rows)}（按 CLI 实际题型分池），anchor_unique=True 的 " \
                             f"{n_unique} 个，False 的 {n_nonunique} 个（如实报告，不强求全部唯一）"
    timed('M5b 全书考法组（按 CLI 实际题型分池）的锚点唯一性如实统计', t_m5b)

    def t_m4r2_e2e():
        """M4-r2 端到端核对：把每个候选组的锚点原样喂 block_insert.resolve_insert_anchor（真实
        ap.zones_of 现算的题块集合），核实际解析结果是否落在 insert_after 声称的题块之后。
        after_block/method_end 应精确落在 last_b 自己；本轮新增的 before_block 重定向应精确落在
        重定向目标（紧随其后的选择例题）自己，且该目标确实在 last_b 之后（不是被错位到别处）。"""
        if bi_mod is None:
            return None, f'block_insert 导入失败，跳过（{BI_IMPORT_ERR}）'
        rows = _anchors_by_kind()
        bad = []
        for r in rows:
            if not r['unique']:
                continue
            kind = next(iter(r['anchor']))
            try:
                _, rb, _pos = bi_mod.resolve_insert_anchor(bh_blocks, r['anchor'])
            except bi_mod.Abort as e:
                bad.append({'group': r['group_key'], 'anchor': r['anchor'], 'err': str(e)[:200]})
                continue
            last_idx = block_id_to_idx[r['last_b']['id']]
            rb_idx = bh_blocks.index(rb)
            if kind in ('after_block', 'method_end'):
                ok = rb_idx == last_idx
            else:  # before_block：应落在 last_b 之后、且标题匹配重定向目标
                want_title = r['anchor']['before_block']['title_contains']
                ok = (rb_idx > last_idx) and (rb['title'] == want_title)
            if not ok:
                bad.append({'group': r['group_key'], 'anchor': r['anchor'],
                            'claimed_after': r['last_b']['id'], 'resolved_title': rb['title']})
        return not bad, f"{len(rows)} 组唯一锚点全部核过 block_insert，端到端落点错误 {len(bad)} 个" \
                        + (f"：{bad[:3]}" if bad else "")
    timed('M4-r2 全部锚点端到端核 block_insert.resolve_insert_anchor（修前 3 个 method_end 组落在'
          '选择区之后，本版改给 before_block 后应全部落对）', t_m4r2_e2e)

    def t_m4r2_named_groups():
        """审查点名的 3 个具体错位组：03党员考法2/06人大代表考法3/03司法考法6——修前这 3 组的
        method_end 兜底会被 block_insert 解析到本节点选择区之后（B0115/B0309/B0547，而非声称的
        B0107/B0302/B0512）；本版应全部改用 before_block，且端到端解析正确。"""
        named = [('党员', '考法2'), ('人大代表', '考法3'), ('司法', '考法6')]
        rows = _anchors_by_kind()
        found, wrong = [], []
        for r in rows:
            if r['query_kind'] != 'subjective':
                continue
            node, method = r['group_key'][1] or '', r['group_key'][2] or ''
            for nname, mname in named:
                if nname in node and mname in method:
                    kind = next(iter(r['anchor']))
                    found.append((node, method, kind, r['unique']))
                    if kind != 'before_block':
                        wrong.append((node, method, kind))
        if len(found) < 3:
            return None, f'本书当前只找到 {len(found)}/3 个点名组，跳过（数据变化导致，非代码问题）：{found}'
        return not wrong, f'3 个点名组均改用 before_block：{found}' + (f'；仍未改的：{wrong}' if wrong else '')
    timed('M4-r2 审查点名的 3 个错位组（党员考法2/人大代表考法3/司法考法6）都已改用 before_block',
          t_m4r2_named_groups)

    # ---- M6：题键已在本书落位时的提示 ----
    def t_m6():
        if not ten_keys:
            return None, '跳过（无可用题键）'
        key = ten_keys[0]
        mdp = ps.find_md_path(BANK, key)
        q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), key)
        q['base_key'] = key
        q['subq'] = None
        q['true_group_keys'] = None
        res = ps.build_query_result(q, book, indices, ps.DEFAULT_PARAMS, 3, 800, [])
        hit = any('已在本书落位' in f for f in res['flags'])
        return hit and bool(res['excluded_block_ids']), \
            f"flags={res['flags']} excluded={res['excluded_block_ids'][:3]}（审查 R08：修前无提示、退出0）"
    timed('M6 题键已在本书落位时 build_query_result 的 flags 里有“已在本书落位”提示', t_m6)

    # ---- M7：--report 的 summary/inputs 字段 ----
    def t_m7():
        rep_path = BUILD_OUT / 'test_M7_report.json'
        if rep_path.exists():
            rep_path.unlink()
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--report', str(rep_path)])
        if not rep_path.is_file():
            return False, f'未写出报告 exit={code} err={err[:200]}'
        rep = json.loads(rep_path.read_text(encoding='utf-8'))
        has_summary = 'summary' in rep and 'n_queries' in rep['summary']
        q0 = rep['inputs']['questions'][0] if rep['inputs'].get('questions') else {}
        has_source = bool(q0.get('path')) and bool(q0.get('sha256'))
        cand0 = (rep['results'][0]['candidates'][0] if rep['results'] and rep['results'][0]['candidates']
                 else {})
        has_h1h2 = 'h1' in cand0 and 'h2' in cand0
        has_body_range = 'body_range' in cand0.get('most_similar_block', {}) \
            and 'body_range' in cand0.get('insert_after', {})
        ok = has_summary and has_source and has_h1h2 and has_body_range
        return ok, (f'summary={has_summary} source_path/sha={has_source} h1/h2={has_h1h2} '
                    f'body_range={has_body_range}（审查 R10：这几项修前都没有）')
    timed('M7 --report 含 summary、题源 path+sha256、候选 h1/h2、题块 body_range', t_m7)

    # ---- M8：原子性——两个输出中一个 guard 失败时，另一个也不落盘 ----
    def t_m8():
        out_md = BUILD_OUT / 'test_M8.md'
        bad_report = REPO_ROOT / '必修三_最新Skill修订_20260913' / 'test_M8_should_not_exist.json'
        for p in (out_md, bad_report):
            if p.exists():
                p.unlink()
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--format', 'md', '--out', str(out_md),
                                   '--report', str(bad_report)])
        out_wrote = out_md.exists()
        report_wrote = bad_report.exists()
        if report_wrote:
            bad_report.unlink()
        if out_wrote:
            out_md.unlink()
        return code == 3 and not out_wrote and not report_wrote, \
            f'exit={code} out_md存在={out_wrote} bad_report存在={report_wrote}（审查 R09：修前 out_md 会先写出）'
    timed('M8 --report 落受保护目录时，同批的 --out（合法路径）也不落盘——原子性', t_m8)

    def t_m8b():
        """连临时文件也不该留下：--out 合法但 --report 的目录不合法，检查 构建/ 目录下没有 .tmp 残留。"""
        before = set(BUILD_OUT.glob('.*'))
        bad_report = REPO_ROOT / '必修三_最新Skill修订_20260913' / 'test_M8b_should_not_exist.json'
        out_md = BUILD_OUT / 'test_M8b.md'
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--format', 'md', '--out', str(out_md),
                                   '--report', str(bad_report)])
        after = set(BUILD_OUT.glob('.*'))
        leftover = after - before
        for p in leftover:
            p.unlink()
        if bad_report.exists():
            bad_report.unlink()
        return code == 3 and not leftover, f'exit={code} leftover_tmp={leftover}'
    timed('M8b 中止后 构建/ 目录不留 .tmp 临时文件', t_m8b)

    # ---- m2：零相似信号 ----
    def t_m2_zero():
        qinfo = {'source': 'synthetic-zero', 'kind': 'subjective', 'ask': '龘龘龘龘龘龘龘龘龘龘',
                 'material': '', 'rubric': '龘龘龘龘龘龘', 'e1_present': True, 'base_key': None,
                 'true_group_keys': None, 'kind_field_raw': None, 'kind_conflict': None,
                 'ask_heuristic': False}
        res = ps.build_query_result(qinfo, book, indices, ps.DEFAULT_PARAMS, 3, 800, [])
        hit = any('无相似信号' in f for f in res['flags'])
        return hit, f"flags={res['flags']}（审查 R11：修前退出0、给3个0分候选、无任何提示）"
    timed('m2 与全书零重合的查询加“无相似信号”flag', t_m2_zero)

    # ---- m3：--top-k / --max-chars 校验 ----
    def t_m3_topk():
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--top-k', '-1'])
        return code == 2, f'exit={code}（审查 R12：修前=0，给19个候选）'
    timed('m3a --top-k -1 → 退出2', t_m3_topk)

    def t_m3_topk0():
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--top-k', '0'])
        return code == 2, f'exit={code}'
    timed('m3b --top-k 0 → 退出2', t_m3_topk0)

    def t_m3_maxchars():
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--max-chars', '-5'])
        return code == 2, f'exit={code}'
    timed('m3c --max-chars -5 → 退出2', t_m3_maxchars)

    # ---- m4：退出码/中文提示/BOM/全角括号 ----
    def t_m4_sk_missing():
        iso_dir = SCRATCH / 'no_sk_iso'
        iso_dir.mkdir(parents=True, exist_ok=True)
        iso_tool = iso_dir / 'placement_suggest_iso.py'
        shutil.copyfile(TOOL, iso_tool)
        import os as _os
        env = dict(_os.environ)
        env.pop('BAODIAN_SKILL_SCRIPTS', None)
        p = subprocess.run([sys.executable, str(iso_tool), '--docx', 'x', '--profile', 'y'],
                            capture_output=True, text=True, timeout=30, cwd=str(iso_dir), env=env)
        return p.returncode == 2, f'exit={p.returncode} err={p.stderr.strip()[:200]}（审查 A01：修前=1）'
    timed('m4a 找不到 Skill 脚本目录 → 退出2（原来 raise SystemExit(字符串) 退出1）', t_m4_sk_missing)

    def t_m4_argparse():
        code, out, err, dt = run([])
        return code == 2 and '参数错误' in err, f'exit={code} err={err.strip()[:200]}'
    timed('m4b 不给任何参数（缺 --docx/--profile）→ argparse 报错，退出2且中文提示前缀', t_m4_argparse)

    def t_m4_docx_missing():
        code, out, err, dt = run(['--docx', str(SCRATCH / 'no_such_file.docx'), '--profile', str(PROFILE),
                                   '--key', 'BJ-2020-BJ-GAOKAO-Q1'])
        return code == 2 and 'No such file' not in err and '不存在' in err, \
            f'exit={code} err={err.strip()[:200]}（审查 m4：修前是英文系统信息、算“内部错误”）'
    timed('m4c --docx 文件不存在 → 退出2，中文提示“文件不存在”而非英文系统异常', t_m4_docx_missing)

    def t_m4_not_zip():
        bad = SCRATCH / 'not_a_docx.docx'
        bad.write_text('这不是一个 zip/docx 文件', encoding='utf-8')
        code, out, err, dt = run(['--docx', str(bad), '--profile', str(PROFILE),
                                   '--key', 'BJ-2020-BJ-GAOKAO-Q1'])
        return code == 2 and '不是有效' in err, f'exit={code} err={err.strip()[:200]}'
    timed('m4d --docx 不是合法 zip → 退出2，中文提示', t_m4_not_zip)

    def t_m4_bom():
        kf = SCRATCH / 'keys_bom.txt'
        kf.write_bytes('﻿'.encode('utf-8') + 'BJ-2020-BJ-GAOKAO-Q1\n'.encode('utf-8'))
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE),
                                   '--keys-file', str(kf), '--format', 'md'])
        return code in (0, 1), f'exit={code} err={err.strip()[:200]}（审查 m4：修前 BOM 混进题键，报“题库没有这个题键”）'
    timed('m4e --keys-file 带 UTF-8 BOM 时第一个题键仍能正确解析', t_m4_bom)

    def t_m4_fullwidth():
        base, sub = ps.parse_key_arg('BJ-2020-BJ-GAOKAO-Q1（1）')
        return base == 'BJ-2020-BJ-GAOKAO-Q1' and sub == '1', f'base={base} sub={sub}'
    timed('m4f 全角括号“（1）”小问写法被接受', t_m4_fullwidth)

    # ---- m9：跨模块守卫只查设问，不查材料 ----
    def t_m9():
        guard_list = ['《经济与社会》']
        qinfo = {'source': 's', 'kind': 'subjective', 'ask': '运用政治与法治知识分析该现象',
                 'material': '材料对比了《经济与社会》与本模块的异同', 'rubric': '略略略略略略略',
                 'e1_present': True, 'base_key': None, 'true_group_keys': None, 'kind_field_raw': None,
                 'kind_conflict': None, 'ask_heuristic': False}
        res = ps.build_query_result(qinfo, book, indices, ps.DEFAULT_PARAMS, 3, 800, guard_list)
        hit = any('跨模块' in f for f in res['flags'])
        return not hit, f"flags={res['flags']}（材料命中守卫词但设问没有，不应触发；审查 m9）"
    timed('m9 跨模块守卫只查设问，材料里出现《经济与社会》不再误标', t_m9)

    def t_m9b():
        guard_list = ['《经济与社会》']
        qinfo = {'source': 's2', 'kind': 'subjective', 'ask': '运用《经济与社会》知识分析该现象',
                 'material': '材料略略略略略略', 'rubric': '略略略略略略略', 'e1_present': True,
                 'base_key': None, 'true_group_keys': None, 'kind_field_raw': None, 'kind_conflict': None,
                 'ask_heuristic': False}
        res = ps.build_query_result(qinfo, book, indices, ps.DEFAULT_PARAMS, 3, 800, guard_list)
        return any('跨模块' in f for f in res['flags']), f"flags={res['flags']}"
    timed('m9b 守卫词真的出现在设问里时仍正常触发（确认没有矫枉过正）', t_m9b)

    # ---- m10：同题键剔除看 keys_all，不只看主键 ----
    def t_m10():
        b0737 = next((b for b in book['blocks'] if b['id'] == 'B0737'), None)
        if b0737 is None:
            return None, '本书当前没有 B0737，跳过（数据变化导致）'
        idx = book['blocks'].index(b0737)
        excl = ps.matching_block_idxs(book['blocks'], 'BJ-2026-BJ-GAOKAO-Q18')
        return idx in excl, f"B0737 key={b0737['key']} keys_all={b0737['keys_all']}（审查 probe4：修前不剔除）"
    timed('m10 B0737（主键 2022，keys_all 含 2026 Q18(2)）查询 2026 Q18 时也被剔除', t_m10)

    # ---- m11：--key 路径规范化 ----
    def t_m11():
        try:
            ps.find_md_path(BANK, '../../etc/passwd-Q1')
            return False, '应该抛 InputError'
        except ps.InputError as e:
            return True, str(e)[:200]
    timed('m11 --key 里带 .. 被拒绝（防越出题库 questions/ 目录）', t_m11)

    # ---- m9（r3）：小问 # 写法只收数字；--keys-file 报错给真实行号 ----
    def t_m9r3_subq_digits_only():
        bad = []
        try:
            ps.parse_key_arg('BJ-2020-BJ-GAOKAO-Q1#abc')
            bad.append('#abc 未报错，被静默接受')
        except ps.InputError:
            pass
        base, sub = ps.parse_key_arg('BJ-2020-BJ-GAOKAO-Q1#1')
        if sub != '1':
            bad.append(f'#1 应该仍能解析出小问=1，实际 sub={sub!r}')
        return not bad, f'不符：{bad}' if bad else '#abc 拒绝、#1 仍正常解析（修前 #abc 被静默接受）'
    timed('m9（r3）--key 小问 "#" 写法只收数字（#abc 拒绝，#1 仍正常）', t_m9r3_subq_digits_only)

    def t_m9r3_keysfile_lineno():
        kf = SCRATCH / 'keys_lineno.txt'
        kf.write_text('# 注释行\n\nBJ-2020-BJ-GAOKAO-Q1\nBJ-2099-NOSUCH-YIMO-Q1\n', encoding='utf-8')
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE),
                                   '--keys-file', str(kf), '--format', 'md'])
        # 坏题键在第4行（1起，含注释/空行）
        return code == 2 and '第 4 行' in err, f'exit={code} err={err.strip()[:200]}（修前给的是行内容不是行号）'
    timed('m9（r3）--keys-file 出错时报真实行号（含注释/空行也计入，和文本编辑器一致）',
          t_m9r3_keysfile_lineno)


# ---------------------------------------------------------------- 7. 五种新题输入入口
def group7():
    sample_key = 'BJ-2020-BJ-GAOKAO-Q1'
    mdp = ps.find_md_path(BANK, sample_key)

    # --md
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--md', str(mdp),
                               '--format', 'md'])
    record('7a --md 入口跑通（逐题 MD 直接给文件，不经题库题键）', code in (0, 1) and '##' in out,
           f'exit={code} out[:120]={out[:120]!r}', seconds=dt)

    # --text（返修 M3-r3：原细则“①…2分 ②…2分 ③…2分”去空白只 12 字，低于 e1_present 的 15 字
    # 门槛，测的其实是“无细则”分支，和 7b 标题说的“有细则”不符——回执 m8 曾误写这条已经改过。
    # 这里换成真的够长、能触发 e1_present=True 的细则文字，并在库调用层面直接断言，不只看 CLI
    # 输出字符串。）
    txt = SCRATCH / 'new_q.txt'
    txt.write_text('材料：某市开展基层协商民主试点。\n运用政治与法治知识，说明基层协商民主的意义。\n'
                    '细则：\n①制度设计角度：政府主导、多方参与的协商机制符合协商民主制度设计要求，2分'
                    '②实施成效角度：对接群众诉求、化解基层矛盾成效明显，2分'
                    '③各方主体作用角度：党组织、居民代表、社会组织等协同发挥作用，2分，合计不超过6分',
                    encoding='utf-8')
    q_check = ps.load_question_from_text(str(txt), 'subjective')
    rubric_len = len(re.sub(r'\s', '', q_check['rubric']))
    record('7b0 --text 用例本身的细则够长、真的触发 e1_present=True（返修 M3-r3：库调用层面直接断言，'
           '不只看 CLI 输出字符串）', q_check['e1_present'] is True and rubric_len >= 15,
           f"e1_present={q_check['e1_present']} rubric去空白长度={rubric_len}（修前12字，碰巧测的是"
           "“无细则”分支）")
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--text', str(txt),
                               '--kind', 'subjective', '--format', 'md'])
    record('7b --text 入口跑通（纯文本设问+细则；细则够长，CLI 输出里不应再出现“未找到正式评分'
           '细则”这条无细则 flag）',
           code in (0, 1) and '##' in out and '未找到正式评分细则' not in out,
           f'exit={code} out[:120]={out[:120]!r}', seconds=dt)

    # --keys-file
    kf = SCRATCH / 'keys.txt'
    kf.write_text(f'# 注释行\n{sample_key}\n', encoding='utf-8')
    report = BUILD_OUT / 'test_keysfile_report.json'
    if report.exists():
        report.unlink()
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--keys-file', str(kf),
                               '--report', str(report)])
    ok = report.is_file()
    if ok:
        rep = json.loads(report.read_text(encoding='utf-8'))
        ok = rep['inputs'].get('keys_file') is not None
    record('7c --keys-file 入口跑通，报告 inputs.keys_file 记了路径+SHA', ok, f'exit={code}', seconds=dt)

    # --params
    params_file = SCRATCH / 'params.json'
    params_file.write_text(json.dumps({'agg_top_k': 5, 'weights': {'ask': 2.0}}), encoding='utf-8')
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', sample_key,
                               '--params', str(params_file)])
    record('7d --params 入口跑通（覆盖内置默认参数）', code in (0, 1), f'exit={code}', seconds=dt)

    # --format md --out
    out_md = BUILD_OUT / 'test_format_md_out.md'
    if out_md.exists():
        out_md.unlink()
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', sample_key,
                               '--format', 'md', '--out', str(out_md)])
    record('7e --format md --out 落盘到候选目录 构建/ 下', out_md.is_file() and code in (0, 1),
           f'exit={code} exists={out_md.is_file()}', seconds=dt)

    # --out 在 json 模式下有提示但不报错
    code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', sample_key,
                               '--out', str(SCRATCH / 'ignored.md')])
    record('7f json 模式下给 --out：不报错，stderr 有提示（返修 m11）', code in (0, 1) and '不生效' in err,
           f'exit={code} err={err.strip()[:200]}', seconds=dt)


# ---------------------------------------------------------------- 8. 返修 r2/r3 回归：逐条复现审查发现
# 需人工核对的边界题键（审查 M1-r2/M1-r3 自己承认“需人工判”，不强求某个方向；BJ-2024-DC-ERMO-Q21
# 在 r3 已靠 OFFICIAL_ANSWER_AND_SCORING 节名解决，从这份名单移出，见 t_M1r3_named）：
E1_NEEDS_HUMAN = {'BJ-2024-SJS-YIMO-Q16', 'BJ-2024-SJS-YIMO-Q20', 'BJ-2025-FT-QIMO-Q21'}
# 返修 M1-r3：审查点名的“索引已匹配正式材料但工具判无E1”共6个题键（rerun_order 里的 fix_hint），
# 逐一人工核对过：DC-ERMO-Q17/Q19/Q21 是真漏判（本轮已修，见 t_M1r3_named）；FT-YIMO-Q17/Q19/Q20
# 的 MD 正文明写“N/A_with_basis；无 E1，不得把 E3 升级为 E1”，是索引本身过时，工具判 False 是对
# 的（r2 important_notes 已有此说明）——留在假阴独立信号扫描的“已解释”名单里，不当作待修问题。
KNOWN_STALE_INDEX_FN = {'BJ-2026-FT-YIMO-Q17', 'BJ-2026-FT-YIMO-Q19', 'BJ-2026-FT-YIMO-Q20'}
# BJ-2025-DC-ERMO-Q17：MD 正文是“细则.pdf”原文逐字引用的真实评分标准，索引把它标成“边界”只是指
# “这份原始材料涉及多题、这里只截取本题部分”，工具判 True 合理（r2 important_notes 已有此说明）。
KNOWN_ACCEPTED_FP = {'BJ-2025-DC-ERMO-Q17'}


def _bank_e1_scan():
    """全题库主观题假阳/假阴独立信号扫描（返修 M1-r3）：原假阴检测复用了 placement_suggest.py 里
    E1_HEADER_RX 的字面拷贝——POS 正则和工具的 E1_HEADER_RX（旧版）逐字相同，天生看不到任何该正则
    不认的节名（如 OFFICIAL_ANSWER_AND_SCORING），按构造就测不到这一类漏判，审查 M1-r3 明确点名。
    改成假阴侧用题库索引 indexes/rubric_links.csv 的 pair_status 字段作独立信号——这是题库自己的
    机读数据，和工具的标题识别完全无关；pair_status=='已匹配正式材料' 但工具判 e1_present=False，
    记一条“疑似假阴”，交调用方与 KNOWN_STALE_INDEX_FN（索引已知过时的例外）比对（此前用纯内容
    “正文含>=3个赋分标记”做独立信号试过，全库误报94个假阴——材料里提到分值、等级描述表等和真正的
    逐点评分细则文本上分不开，噪声太大，不可用，改用索引字段）。假阳侧维持标题+正文交叉核对
    （审查没有点名这一侧是自我复用问题，仍能发现“标题工具认得、但正文其实没有真内容”这一类）。"""
    import csv
    rubric_hits = set()
    p = BANK / 'indexes' / 'rubric_links.csv'
    with p.open(encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            if (row.get('pair_status') or '').strip() == '已匹配正式材料':
                qid = (row.get('question_id') or '').strip()
                if qid:
                    rubric_hits.add(qid)
    NEG_H = re.compile(r'E3|非\s*E1|非正式|不是正式|不得(当作|视为|据此|升格)|不能(当作|升格)|严格不升格|边界|N/?A')
    NEG_B = re.compile(r'正式评分槽为\s*0|正式评分槽.{0,4}0|没有为本题提供|无\s*E1|N/A_with_basis|不能升级为|'
                       r'不得升格|按\s*E3\s*保留|非\s*E1|不是正式评分细则|不等同于同题独立正式评分细则|'
                       r'无正式(评分)?细则|无分项阅卷细则')
    # 返修 M1-r3：FP 侧的 POS 也加上 r3 新收的 3 种节名，否则本轮工具新判为 True 的题（DC-ERMO/
    # FT-ERMO/DC-YIMO 那批）会因为这个手工副本认不出新节名而全部被错报成“假阳”。
    POS = re.compile(r'E1(?!\d)|正式评分|阅卷细则|评分细则|评标|'
                     r'OFFICIAL_ANSWER_AND_SCORING|同卷正式材料|详细题级评分主载体')
    fp, fn = [], []
    for p_md in sorted((BANK / 'questions').glob('*/*.md')):
        if p_md.name == 'README.md':
            continue
        text = p_md.read_text(encoding='utf-8', errors='replace')
        try:
            q = ps.parse_question_md(text, p_md.stem)
        except ps.InputError:
            continue
        if q['kind'] == 'choice':
            continue
        heads = ps.all_headings(text)
        if q['e1_present']:
            real = False
            for i, (lvl, h, s, e) in enumerate(heads):
                if POS.search(h) and not NEG_H.search(h) and not ps.E1_EXCLUDE_TITLE_RX.search(h):
                    body = ps.clean_prose(ps.section_body(text, heads, i))
                    if ps.e1_present(body) and not NEG_B.search(body):
                        real = True
                        break
            if not real:
                fp.append(p_md.stem)
        else:
            if p_md.stem in rubric_hits:
                fn.append(p_md.stem)
    return fp, fn


def group8(book, indices, ten_keys, prof):
    # ---- M1-r2：E1 假阳/假阴——先按真实题键逐一断言，再对全题库扫一遍作总量回归 ----
    def t_M1r2_named():
        cases_false = ['BJ-2023-FT-ERMO-Q17', 'BJ-2025-BJ-GAOKAO-Q18', 'BJ-2023-DC-ERMO-Q18',
                       'BJ-2023-FT-YIMO-Q16', 'BJ-2026-FT-YIMO-Q17']
        cases_true = ['BJ-2024-HD-QIZHONG-Q16', 'BJ-2024-HD-QIZHONG-Q17', 'BJ-2024-HD-QIZHONG-Q18',
                      'BJ-2024-HD-QIZHONG-Q19', 'BJ-2024-HD-QIZHONG-Q20', 'BJ-2024-HD-QIZHONG-Q21']
        bad = []
        for k, want in [(k, False) for k in cases_false] + [(k, True) for k in cases_true]:
            mdp = ps.find_md_path(BANK, k)
            if not mdp.is_file():
                continue
            q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
            if q['e1_present'] != want:
                bad.append((k, q['e1_present'], want, q['e1_header']))
        return not bad, f'{len(cases_false) + len(cases_true)} 个真题键核过，不符 {len(bad)} 个：{bad}'
    timed('M1-r2 假阳/假阴真题键回归（审查点名的题库明写“非E1”7例应为False；'
          'BJ-2024-HD-QIZHONG-Q16/17/18/19/20/21 有嵌套真 E1 应为True，修前 5 道回退为 False）',
          t_M1r2_named)

    # 返修 M1-r3：审查具名指出的三种未覆盖节名（OFFICIAL_ANSWER_AND_SCORING/同卷正式材料/详细题级
    # 评分主载体），逐一列成具名回归，不依赖全库扫描（M3-r3 教训：全库扫描的独立信号本身也可能有
    # 噪声，具名回归才是硬保证）。
    def t_M1r3_named():
        cases_true = ['BJ-2024-DC-ERMO-Q17', 'BJ-2024-DC-ERMO-Q19', 'BJ-2024-DC-ERMO-Q21',
                      'BJ-2024-FT-ERMO-Q18', 'BJ-2024-DC-YIMO-Q16', 'BJ-2024-DC-YIMO-Q17',
                      'BJ-2024-DC-YIMO-Q18', 'BJ-2024-DC-YIMO-Q19', 'BJ-2024-DC-YIMO-Q20',
                      'BJ-2024-DC-YIMO-Q21']
        expect_header = {'BJ-2024-DC-ERMO-Q17': 'OFFICIAL_ANSWER_AND_SCORING',
                         'BJ-2024-FT-ERMO-Q18': '同卷正式材料', 'BJ-2024-DC-YIMO-Q16': '详细题级评分主载体'}
        bad = []
        for k in cases_true:
            mdp = ps.find_md_path(BANK, k)
            if not mdp.is_file():
                continue
            q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
            want_frag = expect_header.get(k)
            if q['e1_present'] is not True or (want_frag and want_frag not in (q['e1_header'] or '')):
                bad.append((k, q['e1_present'], q['e1_header']))
        return not bad, f'{len(cases_true)} 个真题键（3 种 M1-r3 新收节名各至少1个）核过，不符 ' \
                        f'{len(bad)} 个：{bad}（修前全部 e1_present=False，判“按规则不收”）'
    timed('M1-r3 三种未覆盖节名（OFFICIAL_ANSWER_AND_SCORING/同卷正式材料/详细题级评分主载体）'
          '具名回归，均应 e1_present=True', t_M1r3_named)

    def t_M1r3_bank():
        fp, fn = _bank_e1_scan()
        unexplained_fp = [k for k in fp if k not in KNOWN_ACCEPTED_FP]
        unexplained_fn = [k for k in fn if k not in KNOWN_STALE_INDEX_FN]
        ok = not unexplained_fp and not unexplained_fn
        return ok, (f'全题库扫描（假阴侧改用 indexes/rubric_links.csv 的 pair_status 作独立信号，'
                    f'不再是工具自己标题正则的字面拷贝）：假阳 {len(fp)}（{fp}，未解释 {unexplained_fp}），'
                    f'假阴 {len(fn)}（{fn}，未解释 {unexplained_fn}，已知索引过时的3个见'
                    f'KNOWN_STALE_INDEX_FN）')
    timed('M1-r3 全题库假阳/假阴独立信号回归（FN 用题库索引，不再复用工具自己的标题正则）', t_M1r3_bank)

    # ---- M2-r2：设问句守卫（全部小问）+ 引用块题面不丢 ----
    def t_M2r2_guard():
        guard = ((prof.get('sources') or {}).get('stem_module_guard')) or []
        cases = ['BJ-2023-CY-YIMO-Q20', 'BJ-2022-BJ-GAOKAO-Q19', 'BJ-2024-HD-YIMO-Q17']
        bad = []
        for k in cases:
            mdp = ps.find_md_path(BANK, k)
            q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
            sents = ps.ask_like_sentences(q['stem_full'])
            hit = any(ps.stem_module_guard_hit(s, guard) for s in sents)
            if not hit:
                bad.append(k)
        return not bad, f'{len(cases)} 个真题键（含前置小问才带模块限定词的）核过，守卫仍漏报 {len(bad)} 个：{bad}' \
                        '（修前 34 道漏报，只查 split_ask 切出的末尾一句）'
    timed('M2-r2 跨模块守卫改查全部设问句（含前置小问），真题回归', t_M2r2_guard)

    def t_M2r2_blockquote():
        q = ps.parse_question_md(
            ps.find_md_path(BANK, 'BJ-2024-HD-YIMO-Q17').read_text(encoding='utf-8', errors='replace'),
            'BJ-2024-HD-YIMO-Q17')
        has_real_text = len(re.sub(r'\s', '', q['stem_full'])) >= 40 and '经济与社会' in q['stem_full']
        return has_real_text, f"stem_full 长度={len(q['stem_full'])}（修前引用块被整行丢弃，只剩来源/页图" \
                              f"元数据）；ask={q['ask'][:60]!r}"
    timed('M2-r2 引用块（>开头）题面文字保留，不再整行丢弃', t_M2r2_blockquote)

    # ---- M3-r2：--md 输入的已入书查重 ----
    def t_M3r2():
        mdp = ps.find_md_path(BANK, 'BJ-2024-DC-ERMO-Q21')
        q = ps.load_question_from_md(mdp)
        ok_basekey = q['base_key'] == 'BJ-2024-DC-ERMO-Q21'
        q['true_group_keys'] = None
        res = ps.build_query_result(q, book, indices, ps.DEFAULT_PARAMS, 3, 800, [])
        hit = any('已在本书落位' in f for f in res['flags'])
        return ok_basekey and hit, f"base_key={q['base_key']!r}（应等于文件名本身） flags={res['flags']}" \
                                   "（修前 --md 完全不查重、退出0，最像题块就是它自己）"
    timed('M3-r2 --md 输入从文件名识别出题库题键，已入书时同样加“已在本书落位”flag', t_M3r2)

    def t_M3r2_fallback():
        """base_key 识别不出时（如合成/改名过的 MD），退回相似度提示，不是直接放行也不是报错。"""
        top_b = book['blocks'][0]
        fake_text = ps.render_recs(top_b['_recs'][1:], book['doc']['rels'])
        q = {'source': 's', 'kind': top_b['kind'], 'material': fake_text, 'ask': '',
             'rubric': '略略略略略略略略略略略略略略略', 'e1_present': True, 'base_key': None,
             'true_group_keys': None, 'kind_field_raw': None, 'kind_conflict': None,
             'ask_heuristic': False, 'stem_full': fake_text, 'directive_note': None}
        res = ps.build_query_result(q, book, indices, ps.DEFAULT_PARAMS, 3, 800, [])
        return any('疑似题库重复' in f for f in res['flags']), f"flags={res['flags']}"
    timed('M3-r2 base_key 识别不出时，用最像题块的 3-gram 包含度给“疑似题库重复”兜底提示', t_M3r2_fallback)

    # ---- M2-r3：重复检测对所有输入都跑、和全书未截断正文比 ----
    def t_M2r3_crosskey():
        """已知错号重卷：BJ-2025-HD-QIZHONG 与书里已有的 2024 版是同一张卷。用 --key 查 2025 版
        应触发“疑似题库重复”并退出 1（修前 base_key 有值、exclude 为空，检查被整段跳过，exit=0、
        无任何提示，最像题块就是书里的 2024 版同题）。"""
        bad = []
        for k in ('BJ-2025-HD-QIZHONG-Q9', 'BJ-2025-HD-QIZHONG-Q19'):
            mdp = ps.find_md_path(BANK, k)
            if not mdp.is_file():
                continue
            code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key', k,
                                       '--format', 'md'])
            if not (code == 1 and '疑似题库重复' in out and 'HD-QIZHONG' in out):
                bad.append((k, code, out[:200]))
        return not bad, f'不符 {len(bad)} 个：{bad}（修前 exit=0，无提示，最像题块就是书里的2024版同题）'
    timed('M2-r3 命名回归：BJ-2025-HD-QIZHONG-Q9/Q19（错号重卷，--key 查询）触发疑似重复', t_M2r3_crosskey)

    def t_M2r3_fallback_named():
        """去键兜底：BJ-2021-BJ-GAOKAO-Q21 全文（含两个小问）与书里 8 个题块中的若干个 3-gram
        包含度 0.93，去掉题键后仍应能查出（修前只比聚合候选组第 1 名的截断切片，且候选组第 1 名
        碰巧不是包含度最高的那个块，漏报——全书无键兜底漏报 59/141）。"""
        key = 'BJ-2021-BJ-GAOKAO-Q21'
        mdp = ps.find_md_path(BANK, key)
        if not mdp.is_file():
            return None, '找不到 MD，跳过'
        q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), key)
        q = dict(q); q['base_key'] = None; q['true_group_keys'] = None
        res = ps.build_query_result(q, book, indices, ps.DEFAULT_PARAMS, 3, 800, [])
        hit = any('疑似题库重复' in f for f in res['flags'])
        return hit, f"flags={res['flags']}（去键后应仍能靠全书未截断正文比对找到高包含度孪生块）"
    timed('M2-r3 去键兜底：BJ-2021-BJ-GAOKAO-Q21 去掉题键后仍能查出高包含度孪生块', t_M2r3_fallback_named)

    def t_M2r3_no_bm25_prefilter():
        """M2-r3 的教训：曾经试过只比 BM25 组合分最高的前 N 块（预筛提速），但书里被多题共享的
        材料会被 idf 压低分数，真正的孪生块可能排到几百名之外，预筛会直接漏掉。这里直接核实
        find_suspected_duplicate 对 BJ-2021-BJ-GAOKAO-Q21 找到的孪生块确实不在 BM25 组合分前
        50 名——如果这条断言以后失真（数据变化导致孪生块碰巧进了前50），至少证明当前实现没有
        依赖 BM25 排名做预筛，而是老老实实和全书比过一遍。"""
        key = 'BJ-2021-BJ-GAOKAO-Q21'
        mdp = ps.find_md_path(BANK, key)
        q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), key)
        q = dict(q); q['base_key'] = None
        ranked, exclude, query_fields = ps.rank_for_query(q, book, indices, ps.DEFAULT_PARAMS)
        combined, _ = ps.score_blocks(query_fields, indices, len(book['blocks']), ps.DEFAULT_PARAMS)
        dup = ps.find_suspected_duplicate(q, book, exclude)
        if not dup:
            return False, '本应找到孪生块却没找到（find_suspected_duplicate 本身的回归已在别处覆盖，这里应有结果）'
        idxs = sorted(range(len(book['blocks'])), key=lambda i: combined[i], reverse=True)
        block_id_to_rank = {book['blocks'][i]['id']: r for r, i in enumerate(idxs)}
        dup_rank = block_id_to_rank.get(dup['block_id'])
        return dup_rank is not None and dup_rank > 50, \
            f"孪生块 {dup['block_id']}（包含度{dup['ratio']:.2f}）的 BM25 组合分排名第 {dup_rank}" \
            "（>50，证明当前实现和全书比过，不是只挑 BM25 前几十名）"
    timed('M2-r3 佐证：真孪生块的 BM25 排名很靠后，证明重复检测没有走 BM25 前N预筛这条捷径',
          t_M2r3_no_bm25_prefilter)

    # ---- m1：anchor 形状 block_insert 能原样接受 ----
    def t_m1_anchor_shape():
        if bi_mod is None:
            return None, f'block_insert 导入失败，跳过（{BI_IMPORT_ERR}）'
        combined = [0.0] * len(book['blocks'])
        ranked = ps.aggregate_methods(book['blocks'], combined, ps.KIND_GROUPS['subjective'], set(),
                                       ps.DEFAULT_PARAMS)
        d_ = dl_mod.open_docx(str(BOOK3))
        _, _, bh_blocks, _ = ap_mod.zones_of(d_, prof)
        ok_n = 0
        for g in ranked[:30]:
            last_idx = max(g['block_idxs'], key=lambda i: book['blocks'][i]['p_range'][0])
            last_b = book['blocks'][last_idx]
            anchor, unique, _note = ps.anchor_for_group(book['blocks'], g['group_key'], last_b, False)
            if not unique:
                continue
            try:
                bi_mod.resolve_insert_anchor(bh_blocks, anchor)  # 原样喂，不额外包装
                ok_n += 1
            except bi_mod.Abort:
                pass
        return ok_n > 0, f'30 个候选组里唯一锚点原样喂 block_insert 成功解析 {ok_n} 个（修前 0/122，形状不对' \
                        '“anchor 必须且只能给 after_block/before_block/method_end 之一”）'
    timed('m1 anchor 输出形状 block_insert 能原样接受（不用额外包装）', t_m1_anchor_shape)

    # ---- m1（r3）：--format md 打印真实 anchor，不再拿可能不唯一的 last_b 标题充当锚点 ----
    def t_m1r3_format_md_anchor():
        """审查点名 BJ-2023-XC-ERMO-Q20：锚点改用 method_end/before_block 恰恰是因为 last_b 标题
        本身不唯一，修前 Markdown 却写“锚点‘<该标题>’（…，锚点唯一）”，模型照抄会让 block_insert
        因命中2块 Abort。这里找一个 anchor_unique=True 但 kind 不是 after_block 的候选组（即
        last_b 标题本身不唯一、改靠 method_end/before_block 收窄成唯一），确认 Markdown 里不再
        把 last_b 的标题打成“锚点”字样。"""
        combined = [0.0] * len(book['blocks'])
        found_gk = None
        for qkind, kset in ps.KIND_GROUPS.items():
            ranked = ps.aggregate_methods(book['blocks'], combined, kset, set(), ps.DEFAULT_PARAMS)
            for g in ranked:
                last_idx = max(g['block_idxs'], key=lambda i: book['blocks'][i]['p_range'][0])
                last_b = book['blocks'][last_idx]
                is_choice = book['blocks'][g['block_idxs'][0]]['kind'] == 'choice'
                anchor, unique, _note = ps.anchor_for_group(book['blocks'], g['group_key'], last_b, is_choice)
                if unique and next(iter(anchor)) != 'after_block' and \
                        ps._title_hit_count(book['blocks'], last_b['title']) > 1:
                    found_gk = g
                    break
            if found_gk:
                break
        if not found_gk:
            return None, ('本书当前没有这种组合（last_b 标题不唯一但改靠 method_end/before_block 收窄'
                          '唯一），跳过（数据变化导致）')
        detail = ps.candidate_detail(book, found_gk, {'material': '', 'ask': '', 'rubric': ''}, indices, 800)
        r = {'source': 's', 'kind': 'subjective', 'flags': [], 'kind_field_raw': None, 'candidates': [detail]}
        md_text = ps.format_md([r], '测试')
        last_title = detail['insert_after']['block_title']
        bad = f'锚点"{last_title}"' in md_text or f'锚点“{last_title}”' in md_text
        return not bad, f"标题不唯一的 last_b={last_title!r} 未被打成“锚点”字样，实际 anchor 行含 " \
                        f"anchor：{ps._anchor_human(detail['insert_after']['anchor'])!r}"
    timed('m1（r3）--format md 打印真实 anchor 字典，last_b 标题不唯一时不再被误标“锚点唯一”',
          t_m1r3_format_md_anchor)

    # ---- m2（r3）：most_similar_block 标题不唯一时，template_block 换成组内标题唯一的块 ----
    def t_m2r3_template_block():
        combined = [0.0] * len(book['blocks'])
        found = None
        for qkind, kset in ps.KIND_GROUPS.items():
            ranked = ps.aggregate_methods(book['blocks'], combined, kset, set(), ps.DEFAULT_PARAMS)
            for g in ranked:
                top_idx = g['block_idxs'][0]
                if ps._title_hit_count(book['blocks'], book['blocks'][top_idx]['title']) > 1:
                    found = g
                    break
            if found:
                break
        if not found:
            return None, '本书当前没有 most_similar_block 标题不唯一的候选组，跳过（数据变化导致）'
        detail = ps.candidate_detail(book, found, {'material': '', 'ask': '', 'rubric': ''}, indices, 800)
        tmpl = detail.get('template_block')
        ok = tmpl is not None and 'template_unique' in tmpl
        note = ''
        if ok and tmpl['id'] != detail['most_similar_block']['id']:
            note = f"（已换成组内标题唯一的 {tmpl['id']}，most_similar_block 本身 " \
                   f"{detail['most_similar_block']['id']} 标题不唯一）"
        elif ok and not tmpl['template_unique']:
            note = '（同组内也没有标题唯一的块，如实标 template_unique=false，不假装唯一）'
        return ok, f"template_block={tmpl}{note}（修前没有 template_block 字段，r1 M5 残留）"
    timed('m2（r3）most_similar_block 标题不唯一时，template_block 换成组内标题唯一的块（或如实标 '
          'template_unique=false）', t_m2r3_template_block)

    # ---- m4（r3）：--params 数值区间与未知字段校验 ----
    def t_m4r3_params_range():
        cases = [
            ({'agg_top_k': 2.5}, 'agg_top_k'),
            ({'ngram_sizes': [0]}, 'ngram_sizes'),
            ({'bm25_k1': -1}, 'bm25_k1'),
            ({'agg_mix': 5}, 'agg_mix'),
            ({'bm25_b': 1.5}, 'bm25_b'),
            ({'weights': {'bogus': 1.0}}, 'weights'),
        ]
        bad = []
        for i, (ov, tag) in enumerate(cases):
            pf = SCRATCH / f'bad_params_range_{i}.json'
            pf.write_text(json.dumps(ov), encoding='utf-8')
            try:
                ps._load_params(str(pf))
                bad.append((tag, '未报错，被静默接受'))
            except ps.InputError as e:
                if tag not in str(e):
                    bad.append((tag, f'报错但没点名字段：{e}'))
            except Exception as e:
                bad.append((tag, f'{type(e).__name__}: {e}（应为中文 InputError，不是内部错误）'))
        return not bad, f'{len(cases)} 组越界/未知取值核过，不符 {len(bad)} 个：{bad}（修前 agg_top_k=2.5 报' \
                        '英文“内部错误：slice indices must be integers…”，其余全部静默接受）'
    timed('m4（r3）--params 数值区间与未知 weights 键校验（agg_top_k/ngram_sizes/bm25_k1/agg_mix/'
          'bm25_b/未知weights键）', t_m4r3_params_range)

    def t_m4r3_params_cli():
        pf = SCRATCH / 'bad_params_cli.json'
        pf.write_text(json.dumps({'agg_top_k': 2.5}), encoding='utf-8')
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--params', str(pf)])
        return code == 2 and '内部错误' not in err and 'agg_top_k' in err, \
            f'exit={code} err={err.strip()[:150]}（修前退出2但报英文“内部错误：slice indices…”）'
    timed('m4（r3）--params agg_top_k=2.5 走 CLI 子进程，退出2、中文提示、不是“内部错误”', t_m4r3_params_cli)

    # ---- m2：INSERT_NOTE 原样引用规则，不说反 ----
    def t_m2_note():
        ok = '在现有节点内确定新增题的局部插入位置' in ps.INSERT_NOTE and '只适用于' not in ps.INSERT_NOTE
        return ok, (f'INSERT_NOTE[:80]={ps.INSERT_NOTE[:80]!r}（修前说“那组键只用于用户明确授权的全书'
                    '重排或新建结构”，把规则说反了）')
    timed('m2 INSERT_NOTE 原样引用 project-rules.md/counting-sorting-policy.md，不说反排序键的适用范围',
          t_m2_note)

    # ---- m3：具名无 E1 例外卷 ----
    def t_m3_exception():
        bad = []
        for key in ('BJ-2024-SY-ERMO-Q16', 'BJ-2026-SJS-QIMO-Q16'):
            mdp = ps.find_md_path(BANK, key)
            q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), key)
            if q['e1_present']:
                continue  # 该题本身就有 E1，不测例外分支
            q = dict(q); q['base_key'] = key; q['true_group_keys'] = None
            res = ps.build_query_result(q, book, indices, ps.DEFAULT_PARAMS, 3, 800, [], prof=prof,
                                         bank_root=BANK)
            has_exempt = any('具名例外' in f for f in res['flags'])
            has_no_e1 = any('按规则候选“不收”' in f for f in res['flags'])
            if not has_exempt or has_no_e1:
                bad.append((key, res['flags']))
        return not bad, f'具名例外卷（2024顺义二模/2026石景山期末）核过，不符 {len(bad)} 个：{bad}' \
                        '（修前没有豁免口径，一律标“按规则不收”）'
    timed('m3 profile.sources.no_e1_exceptions 具名例外卷不算“按规则不收”', t_m3_exception)

    # ---- m4：STEM_HEADER_RX 加“原题转录”；读取指引点名节找不到时给 note ----
    def t_m4_stem_header():
        base = 'BJ-2026-SJS-QIMO-Q16'
        mdp = ps.find_md_path(BANK, base)
        if not mdp.is_file():
            return None, '找不到 MD，跳过'
        try:
            q = ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), base)
        except ps.InputError as e:
            return False, f'仍然报错：{e}（修前“原题转录”节名不被 STEM_HEADER_RX 认得，退出2）'
        return bool(q['stem_header']), f"stem_header={q['stem_header']!r}"
    timed('m4a STEM_HEADER_RX 认得“原题转录”节名（2026石景山期末 20 个 MD 用这个写法）', t_m4_stem_header)

    def t_m4_directive_note():
        note = ps._directive_missing_note('题目原文（原卷·native，读取优先）', found=False)
        ok = bool(note) and '题目原文（原卷·native，读取优先）' in note
        return ok, f'note={note!r}（修前读取指引点名的节找不到时悄悄退回关键词匹配，不提示）'
    timed('m4b 读取指引点名的节在文档里找不到时，给出可转成 flag 的说明', t_m4_directive_note)

    # ---- m5：原子写失败清理临时文件 ----
    def t_m5_atomic_cleanup():
        target = SCRATCH / 'atomic_fail_dir'  # 目标本身是个目录，os.replace 到目录会失败
        target.mkdir(parents=True, exist_ok=True)
        before = set(p.name for p in SCRATCH.glob('.*'))
        try:
            ps._atomic_write_text(target, '内容')
            wrote_ok = True
        except Exception:
            wrote_ok = False
        after = set(p.name for p in SCRATCH.glob('.*'))
        leftover = after - before
        for name in leftover:
            try:
                (SCRATCH / name).unlink()
            except OSError:
                pass
        return (not wrote_ok) and not leftover, f'写成功={wrote_ok}（应为 False） 残留临时文件={leftover}' \
                                                '（修前 os.replace 失败时 .tmp<pid> 不清理）'
    timed('m5 _atomic_write_text 写失败时清理临时文件，不残留 .tmp<pid>', t_m5_atomic_cleanup)

    # ---- m6：--params 中文报错 ----
    def t_m6_bad_json():
        bad = SCRATCH / 'bad_params.json'
        bad.write_text('{not valid json', encoding='utf-8')
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--params', str(bad)])
        return code == 2 and '不是合法 JSON' in err, f'exit={code} err={err.strip()[:150]}'
    timed('m6a --params 非法 JSON → 退出2，中文提示（修前“内部错误：Expecting property name…”）',
          t_m6_bad_json)

    def t_m6_bad_type():
        bad = SCRATCH / 'bad_params_type.json'
        bad.write_text(json.dumps({'weights': {'ask': 'not_a_number'}}), encoding='utf-8')
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--params', str(bad)])
        return code == 2 and '必须是数字' in err, f'exit={code} err={err.strip()[:150]}'
    timed('m6b --params.weights 字段类型不对 → 退出2，中文提示（修前“内部错误：can\'t multiply…”）',
          t_m6_bad_type)

    def t_m6_missing_file():
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--params', str(SCRATCH / 'no_such_params.json')])
        return code == 2 and '不存在' in err, f'exit={code} err={err.strip()[:150]}'
    timed('m6c --params 文件不存在 → 退出2，中文提示', t_m6_missing_file)

    # ---- m9：评测池剔除数披露 + n_true_groups 打印（见 main() 里 group1 的调用输出与 test_results.json）
    def t_m9_pool_disclosure():
        # 返修 m6a（r3）：原断言 len(no_md)>=0 恒真，不管数据怎样都 PASS，不是真的测试。改成核实
        # 这些题键确实“文件缺失”或“确有 InputError”，不是 find_md_path 拼路径拼错这种别的原因——
        # 如果哪个题键其实能正常解析（parse_question_md 不报错），md_for_key 却说 None，就是
        # 评测池口径本身出了问题，应该 FAIL。
        blocks = book['blocks']
        keyed = {b['key'] for b in blocks if b.get('key')}
        no_md = [k for k in keyed if md_for_key(k) is None]
        bad = []
        for k in no_md:
            mdp = ps.find_md_path(BANK, k)
            if not mdp.is_file():
                continue
            try:
                ps.parse_question_md(mdp.read_text(encoding='utf-8', errors='replace'), k)
                bad.append(k)
            except ps.InputError:
                pass
        return not bad, (f'题库无可用题面（“采用题面小节: 无”等）导致进不了评测池的题键数：{len(no_md)}'
                         f'（约定7“如实报告”，已写进回执 known_limits）；核实每个都是文件缺失或真的 '
                         f'InputError，口径不一致 {len(bad)} 个：{bad[:5]}')
    timed('m9 评测池剔除数可统计并披露，且每个剔除都真的是文件缺失/InputError（不是恒真断言）',
          t_m9_pool_disclosure)

    # ---- m10：真实考法组与剔除口径一致（两处都用 matching_block_idxs）----
    def t_m10_consistency():
        b0737 = next((b for b in book['blocks'] if b['id'] == 'B0737'), None)
        if b0737 is None:
            return None, '本书当前没有 B0737，跳过（数据变化导致）'
        key = 'BJ-2026-BJ-GAOKAO-Q18'
        excl = ps.matching_block_idxs(book['blocks'], key)
        true_groups = {ps.group_key_of(book['blocks'][i]) for i in excl}
        idx0737 = book['blocks'].index(b0737)
        return (idx0737 in excl) and (ps.group_key_of(b0737) in true_groups), \
            f'B0737 剔除={idx0737 in excl} 真实考法含其组={ps.group_key_of(b0737) in true_groups}' \
            '（修前 run() 里 true_group_keys 只看主键，和 rank_for_query 的剔除口径不一致）'
    timed('m10 run() 的 true_group_keys 与 rank_for_query 的剔除口径统一用 matching_block_idxs', t_m10_consistency)

    # ---- m11：--report 的 profile 段带 SHA ----
    def t_m11_profile_sha():
        rep_path = BUILD_OUT / 'test_m11_report.json'
        if rep_path.exists():
            rep_path.unlink()
        code, out, err, dt = run(['--docx', str(BOOK3), '--profile', str(PROFILE), '--key',
                                   'BJ-2020-BJ-GAOKAO-Q1', '--report', str(rep_path)])
        if not rep_path.is_file():
            return False, f'未写出报告 exit={code}'
        rep = json.loads(rep_path.read_text(encoding='utf-8'))
        return bool(rep.get('profile', {}).get('sha256')), f"profile={rep.get('profile')}"
    timed('m11 --report 的 profile 段带 sha256（修前只有 book_id/path/frozen）', t_m11_profile_sha)


def main():
    setup()
    t0 = time.time()
    baseline_check('测试前')

    prof, book, indices = load_book_and_indices(BOOK3, PROFILE)
    actual_sha = ps.sha256_file(BOOK3)
    expected_sha, from_manifest = book3_expected_sha()
    record('0 必修三第52批 SHA 与同步清单一致', actual_sha.lower() == expected_sha.lower(),
           f'实际={actual_sha[:16]}… 期望={expected_sha[:16]}…'
           f'（{"读自 云端/同步清单.json" if from_manifest else "清单读取失败，退回写死常量，见 m6"}）')
    strata, kindset_by_key = keys_by_stratum(book['blocks'])
    record('0b 题键分层池非空', all(len(v) >= 10 for v in strata.values()),
           str({k: len(v) for k, v in strata.items()}))

    default_10, ten_keys = group1(book, indices, kindset_by_key, ps.DEFAULT_PARAMS, label='内置默认参数')
    default_full = group2(book, indices, kindset_by_key, ps.DEFAULT_PARAMS, label='内置默认参数')

    tuned_params, tune_keys = group3(book, indices, kindset_by_key, ten_keys)

    tuned_10, _ = group1(book, indices, kindset_by_key, tuned_params, label='调好后的固定参数')
    tuned_full = group2(book, indices, kindset_by_key, tuned_params, label='调好后的固定参数')

    group4()
    group5()
    group6(book, indices, ten_keys, prof)
    group7()
    group8(book, indices, ten_keys, prof)

    baseline_check('测试后')
    dt = time.time() - t0
    total = len(results)
    skipped = [r for r in results if r['ok'] is None]
    failed = [r for r in results if r['ok'] is False]
    print(f'\n合计 {total} 条，跳过 {len(skipped)} 条，失败 {len(failed)} 条，用时 {dt:.1f}s')
    (BUILD_OUT / 'test_results.json').write_text(json.dumps({
        'total': total, 'skipped': len(skipped), 'failed': len(failed), 'seconds': round(dt, 1),
        'default_params_10': default_10, 'default_params_full': default_full,
        'tuned_params': tuned_params, 'tuned_params_10': tuned_10, 'tuned_params_full': tuned_full,
        'ten_eval_keys': ten_keys, 'tune_set_n': len(tune_keys), 'results': results,
    }, ensure_ascii=False, indent=1), encoding='utf-8')
    return len(failed)


if __name__ == '__main__':
    sys.exit(main())
