import sys, os
sys.dont_write_bytecode = True
sys.path.insert(0, '/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925')
import run_tests_placement_suggest as rt
prof, book, idx = rt.load_book_and_indices(rt.BOOK3, rt.PROFILE)
strata, kbk = rt.keys_by_stratum(book['blocks'])
ten = [k for v in rt.pick_10(strata).values() for k in v]
tune = rt.pick_tune_set(strata, set(ten))
best = None
for w in rt.PARAM_GRID_WEIGHTS:
    for top_k, mix in rt.PARAM_GRID_AGG:
        params = dict(rt.ps.DEFAULT_PARAMS); params.update({'weights': w, 'agg_top_k': top_k, 'agg_mix': mix})
        h1 = h3 = 0
        for k in tune:
            r = rt.lenient_eval(k, kbk, book, idx, params)
            if r is None or r['kind_mismatch']: continue
            h1 += r['hit1']; h3 += r['hit3']
        s = 2*h1 + h3
        if best is None or s > best[0]: best = (s, h1, h3, w, top_k, mix)
print('PYTHONHASHSEED', os.environ.get('PYTHONHASHSEED'), 'best', best, 'n_tune', len(tune))
