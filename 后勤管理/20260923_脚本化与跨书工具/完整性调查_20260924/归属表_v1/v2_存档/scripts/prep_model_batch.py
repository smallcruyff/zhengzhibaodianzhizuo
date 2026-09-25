#!/usr/bin/env python3
"""prep_model_batch.py —— 缺口4的“准备”部分：只算队列大小、估算调用次数与token；不调模型、不生成正式切片内容。

队列 = attribution.csv 里至少一个模块仍是 MAYBE 的题（跨模块判定合一，一次看全9模块），
       并入 conflict_script_out 非空的“错收候选”复核队列（同一 qid 若已在 MAYBE 队列则不重复计数）。
内容体量直接从 classifier/units.jsonl 的 stem_len / rubric_len 取真实字符数（未截断口径，
呼应 blind_spot：主观题细则不许再截前400字）。

输出 slice_estimate.json：队列规模、按类型的字符统计、假设的批大小、估算调用次数与token区间。
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
    ap.add_argument('--batch-choice', type=int, default=25, help='假设每次调用打包的选择题单元数')
    ap.add_argument('--batch-subj', type=int, default=10, help='假设每次调用打包的主观题单元数（细则不截断，体量大，批更小）')
    ap.add_argument('--overhead-tokens', type=int, default=3000, help='每次调用的固定开销估算（边界卡+说明+输出schema）')
    ap.add_argument('--chars-per-token', type=float, default=1.5, help='中文字符/token 粗估比例')
    ap.add_argument('--output-tokens-per-unit', type=int, default=120, help='每单元结构化JSON输出估算token')
    a = ap.parse_args()

    with open(a.attribution, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    maybe_qids = {r['qid'] for r in rows if any(r['归属_' + m] == 'MAYBE' for m in MODS)}
    conflict_qids = {r['qid'] for r in rows if r.get('conflict_script_out')}
    queue_qids = maybe_qids | conflict_qids

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

    n_choice, n_subj = len(choice_stem), len(subj_stem)
    chars_choice = sum(choice_stem)
    chars_subj = sum(subj_stem) + sum(subj_rubric)

    calls_choice = math.ceil(n_choice / a.batch_choice) if n_choice else 0
    calls_subj = math.ceil(n_subj / a.batch_subj) if n_subj else 0
    calls_total = calls_choice + calls_subj

    content_tokens = (chars_choice + chars_subj) / a.chars_per_token
    overhead_tokens = calls_total * a.overhead_tokens
    output_tokens = (n_choice + n_subj) * a.output_tokens_per_unit
    input_tokens_low = content_tokens + overhead_tokens
    input_tokens_high = input_tokens_low * 1.3  # 留给切片重叠/边界卡增补的浮动

    result = {
        'rule_version': '2026-09-24-attribution-v1',
        'method': (
            '队列=归属列里至少一模块为MAYBE的题，并入conflict_script_out非空的疑似错收题（去重）。'
            '字符数直接取 classifier/units.jsonl 的 stem_len/rubric_len 真实值，不做400字截断假设（呼应blind_spot修复）。'
            '批大小、每次调用开销、中文字符/token比例、每题输出token都是本脚本的可调假设（见各参数），不是实测值；'
            '真正执行时应先用一批小样本实测校准这些参数，再乘队列规模。'
        ),
        'queue_unique_qids': len(queue_qids),
        'queue_maybe_only': len(maybe_qids),
        'queue_conflict_only_extra': len(queue_qids) - len(maybe_qids),
        'queue_missing_from_units_jsonl': missing,
        'by_type': {
            '选择题': {'n_units': n_choice, 'chars_total': chars_choice,
                     'chars_avg': round(chars_choice / n_choice) if n_choice else 0},
            '主观题': {'n_units': n_subj, 'chars_stem_total': sum(subj_stem), 'chars_rubric_total': sum(subj_rubric),
                     'chars_avg_stem': round(sum(subj_stem) / n_subj) if n_subj else 0,
                     'chars_avg_rubric': round(sum(subj_rubric) / n_subj) if n_subj else 0},
        },
        'assumptions': {
            'batch_size_choice_units_per_call': a.batch_choice,
            'batch_size_subj_units_per_call': a.batch_subj,
            'overhead_tokens_per_call': a.overhead_tokens,
            'chars_per_token': a.chars_per_token,
            'output_tokens_per_unit': a.output_tokens_per_unit,
        },
        'estimate': {
            'calls_choice_batches': calls_choice,
            'calls_subj_batches': calls_subj,
            'calls_total': calls_total,
            'input_tokens_content_only': round(content_tokens),
            'input_tokens_overhead_only': round(overhead_tokens),
            'input_tokens_low': round(input_tokens_low),
            'input_tokens_high': round(input_tokens_high),
            'output_tokens_estimate': output_tokens,
            'total_tokens_low': round(input_tokens_low + output_tokens),
            'total_tokens_high': round(input_tokens_high + output_tokens),
        },
        'compare_to_critic_prior_estimate': (
            '三路调查与审查摘要.txt 第122行：旧口径（含400字截断、更大批大小）估算约78次调用、0.95M-1.73M token。'
            '本估算队列更小（只含仍MAYBE/冲突的题，不含已确定题）但细则不截断，量级应相近或略高，供主代理定批大小前参考，不是最终值。'
        ),
    }
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
    print(json.dumps(result['estimate'], ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()
