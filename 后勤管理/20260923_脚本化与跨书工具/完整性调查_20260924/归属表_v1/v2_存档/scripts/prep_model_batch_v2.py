#!/usr/bin/env python3
"""prep_model_batch_v2.py —— 缺口4"准备"部分 v2：只算队列大小、估算调用次数与token；不调模型。

相对 v1 的变更（对应 审查意见.json major④⑤、minor项）：
  1. 队列新增"COLLECTED复判"层：全部 归属_<某模块>==COLLECTED 的单元都排进复判队列，不再局限于
     conflict_script_out非空的80对。"已收只标待复核"要落到真的会被模型/人工复判一遍，不能停在标签上。
  2. missing_from_units_jsonl 排序后再输出（消除集合迭代顺序不确定的问题）。
  3. token估算明确加一条 caching_and_multiturn_caveat：本估算只算一次性内容token，不含缓存重读和
     多轮调用可能把实际用量放大一个数量级的提示（回应审查意见minor项）。
  4. 切片长度改为直接引用 units.jsonl 的 stem_len/rubric_len 全长（未变，v1已如此），并新增
     length_not_truncated_check：抽查这些单元的真实字符数是否等于声明的_len，帮助发现"切片阶段
     如果直接截断"的回归。
"""
import sys
sys.dont_write_bytecode = True
import argparse, csv, json, math
from pathlib import Path

CLASSIFIER = Path('/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/bf450d67-a650-441b-9b69-41f5207feba6/scratchpad/completeness/classifier')
MODS = ['B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--attribution', default='attribution.csv')
    ap.add_argument('--out', default='model_batch/slice_estimate.json')
    ap.add_argument('--batch-choice', type=int, default=25)
    ap.add_argument('--batch-subj', type=int, default=10)
    ap.add_argument('--batch-collected-recheck', type=int, default=20, help='COLLECTED复判假设每次调用打包的单元数(复判只需二元判断,批可更大)')
    ap.add_argument('--overhead-tokens', type=int, default=3000)
    ap.add_argument('--chars-per-token', type=float, default=1.5)
    ap.add_argument('--output-tokens-per-unit', type=int, default=120)
    ap.add_argument('--output-tokens-per-recheck-unit', type=int, default=40, help='COLLECTED复判每单元只需是/否+一句理由,输出token更小')
    a = ap.parse_args()

    with open(a.attribution, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    maybe_qids = {r['qid'] for r in rows if any(r['归属_' + m] == 'MAYBE' for m in MODS)}
    conflict_qids = {r['qid'] for r in rows if r.get('conflict_script_out')}
    queue_qids = maybe_qids | conflict_qids

    # ---- COLLECTED复判队列（major④修复：不再局限conflict_script_out）----
    collected_units = set()
    collected_pairs = 0
    for r in rows:
        for m in MODS:
            if r['归属_' + m] == 'COLLECTED':
                collected_units.add(r['qid'])
                collected_pairs += 1

    units = {}
    with open(CLASSIFIER / 'units.jsonl', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            units[d['qid']] = d

    choice_stem, subj_stem, subj_rubric, missing = [], [], [], []
    for q in queue_qids:
        u = units.get(q)
        if not u:
            missing.append(q)
            continue
        if u.get('type') == '选择题':
            choice_stem.append(u.get('stem_len', 0) or 0)
        else:
            subj_stem.append(u.get('stem_len', 0) or 0)
            subj_rubric.append(u.get('rubric_len', 0) or 0)
    missing.sort()

    n_choice, n_subj = len(choice_stem), len(subj_stem)
    chars_choice = sum(choice_stem)
    chars_subj = sum(subj_stem) + sum(subj_rubric)

    calls_choice = math.ceil(n_choice / a.batch_choice) if n_choice else 0
    calls_subj = math.ceil(n_subj / a.batch_subj) if n_subj else 0

    # COLLECTED复判队列的字符量（同样取真实stem_len/rubric_len，不截断）
    recheck_chars = 0
    recheck_missing = []
    for q in sorted(collected_units):
        u = units.get(q)
        if not u:
            recheck_missing.append(q)
            continue
        recheck_chars += (u.get('stem_len', 0) or 0) + (u.get('rubric_len', 0) or 0)
    n_recheck = len(collected_units)
    calls_recheck = math.ceil(n_recheck / a.batch_collected_recheck) if n_recheck else 0

    calls_total = calls_choice + calls_subj + calls_recheck

    content_tokens = (chars_choice + chars_subj + recheck_chars) / a.chars_per_token
    overhead_tokens = calls_total * a.overhead_tokens
    output_tokens = (n_choice + n_subj) * a.output_tokens_per_unit + n_recheck * a.output_tokens_per_recheck_unit
    input_tokens_low = content_tokens + overhead_tokens
    input_tokens_high = input_tokens_low * 1.3

    # 长度未截断抽查：真实stem/rubric字符数是否等于声明的_len（防止切片阶段直接取截断字段）
    length_check_sample = []
    with open(CLASSIFIER / 'units.jsonl', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 2000:
                break
            d = json.loads(line)
            stem = d.get('stem', '')
            rubric = d.get('rubric', '')
            if stem and len(stem) != (d.get('stem_len') or -1):
                length_check_sample.append({'qid': d['qid'], 'field': 'stem', 'declared_len': d.get('stem_len'), 'actual_len': len(stem)})
            if rubric and len(rubric) != (d.get('rubric_len') or -1):
                length_check_sample.append({'qid': d['qid'], 'field': 'rubric', 'declared_len': d.get('rubric_len'), 'actual_len': len(rubric)})

    result = {
        'rule_version': '2026-09-24-attribution-v2',
        'method': (
            '队列①=归属列里至少一模块为MAYBE的题，并入conflict_script_out非空的疑似错收题（去重）。'
            '队列②(新增,major④)=全部COLLECTED模块单元，逐一复判"书稿收的对不对"，不再局限于脚本已发现冲突的80对。'
            '字符数直接取 classifier/units.jsonl 的 stem_len/rubric_len 真实值，不做截断假设。'
            '批大小、每次调用开销、字符/token比例、每题输出token都是可调假设，不是实测值。'
        ),
        'queue1_maybe_or_conflict': {
            'unique_qids': len(queue_qids), 'maybe_only': len(maybe_qids),
            'conflict_only_extra': len(queue_qids) - len(maybe_qids),
            'missing_from_units_jsonl': missing,
        },
        'queue2_collected_recheck': {
            'unique_qids': n_recheck, 'module_unit_pairs': collected_pairs,
            'missing_from_units_jsonl': sorted(recheck_missing),
            'note': 'major④修复：COLLECTED模块单元不能只标签"已收待复核"就不再实际复核，本队列排进模型批次，'
                    '逐单元逐模块输出"维持收录/改判错收/证据不足暂缓"三态结论，错收候选=书稿收录-模型或人工判定的相关集合，'
                    '不是build_diffs.py里那80对script conflict能单独算出来的。',
        },
        'by_type': {
            '选择题(队列1)': {'n_units': n_choice, 'chars_total': chars_choice,
                     'chars_avg': round(chars_choice / n_choice) if n_choice else 0},
            '主观题(队列1)': {'n_units': n_subj, 'chars_stem_total': sum(subj_stem), 'chars_rubric_total': sum(subj_rubric),
                     'chars_avg_stem': round(sum(subj_stem) / n_subj) if n_subj else 0,
                     'chars_avg_rubric': round(sum(subj_rubric) / n_subj) if n_subj else 0},
            'COLLECTED复判(队列2)': {'n_units': n_recheck, 'chars_total': recheck_chars,
                     'chars_avg': round(recheck_chars / n_recheck) if n_recheck else 0},
        },
        'assumptions': {
            'batch_size_choice_units_per_call': a.batch_choice,
            'batch_size_subj_units_per_call': a.batch_subj,
            'batch_size_collected_recheck_units_per_call': a.batch_collected_recheck,
            'overhead_tokens_per_call': a.overhead_tokens,
            'chars_per_token': a.chars_per_token,
            'output_tokens_per_unit': a.output_tokens_per_unit,
            'output_tokens_per_recheck_unit': a.output_tokens_per_recheck_unit,
        },
        'estimate': {
            'calls_choice_batches': calls_choice,
            'calls_subj_batches': calls_subj,
            'calls_collected_recheck_batches': calls_recheck,
            'calls_total': calls_total,
            'input_tokens_content_only': round(content_tokens),
            'input_tokens_overhead_only': round(overhead_tokens),
            'input_tokens_low': round(input_tokens_low),
            'input_tokens_high': round(input_tokens_high),
            'output_tokens_estimate': output_tokens,
            'total_tokens_low': round(input_tokens_low + output_tokens),
            'total_tokens_high': round(input_tokens_high + output_tokens),
        },
        'caching_and_multiturn_caveat': (
            '本估算只算"一次性把内容发一遍"的输入/输出token，不含：①同一批次多轮往返时被重复计费的缓存重读；'
            '②边界卡/说明书随每次调用重复携带的固定开销在长会话里可能不止overhead_tokens_per_call这一份；'
            '③人工复核后二次修订触发的重跑。审查意见指出实际用量可能比本估算放大一个数量级，正式执行前必须先用'
            '10—20题的小样本实测校准，而不是直接按本估算的量级申请预算。'
        ),
        'length_not_truncated_spotcheck': {
            'sampled_units': 2000,
            'mismatches_found': len(length_check_sample),
            'sample': length_check_sample[:10],
            'note': '若mismatches_found>0，说明units.jsonl本身的stem/rubric字段已经是截断后的文本，'
                    '真正切片必须回题库原文取全文，不能直接复用units.jsonl的stem/rubric字段。',
        },
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(result['estimate'], ensure_ascii=False, indent=1))
    print('length_spotcheck mismatches:', len(length_check_sample))


if __name__ == '__main__':
    main()
