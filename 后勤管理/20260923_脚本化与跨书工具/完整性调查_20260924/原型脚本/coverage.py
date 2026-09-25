#!/usr/bin/env python3
"""coverage.py —— 跨册题源覆盖比对原型（只读；产物只写 --out 目录）。

以题库全集（indexes/questions.csv 的唯一题键）为分母，把各书的例题块、题肢、题肢卡、正文里的题源提及
解析成题库题键，给出：每书解析率与按卷分布、按卷×书覆盖矩阵、孤儿题候选、跨书重复、书有库无、身份不一致候选。

复用（不改）Skill 母版脚本：block_index（切块）、qpack（题源写法→题键、身份更正表、学年写法、身份探针）。
自己只加两层：①全文题源提及扫描；②题库全文指纹（把无题源的题肢、身份探针对不上的例题，按原文片段在题库全文里反查）。

用法：
  python3 coverage.py --books books.tsv --out 输出目录 [--no-fp] [--baseline 上次/coverage_state.json]
books.tsv：每行 book_id<TAB>配置名或配置JSON路径<TAB>docx路径
"""
import sys
sys.dont_write_bytecode = True
import argparse, bisect, csv, json, re, time
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

SKILL = Path('/Users/wanglifei/.codex/skills/beijing-gaokao-politics/scripts')
sys.path.insert(0, str(SKILL))
import block_index as BI   # noqa: E402
import qpack as QP          # noqa: E402
from profile_lib import load_profile  # noqa: E402

T = OrderedDict()


def tick(name, t0):
    T[name] = round(T.get(name, 0) + time.time() - t0, 3)
    return time.time()


# ------------------------------------------------------------------ 题库全集
def load_universe(bank):
    rows = QP.read_csv(bank.root / 'indexes/questions.csv')
    by = defaultdict(list)
    for r in rows:
        by[r['question_id']].append(r)
    uni = OrderedDict()
    for q, rs in by.items():
        sts = {r['extraction_status'] for r in rs}
        if sts and all('misparsed' in s for s in sts):
            continue
        tys = Counter(r['type'] for r in rs if r['type'] in ('选择题', '非选择题'))
        num = int(rs[0]['num']) if rs[0]['num'].isdigit() else -1
        ty = tys.most_common(1)[0][0] if tys else ('选择题' if 0 < num <= 15 else '非选择题')
        uni[q] = {'exam': rs[0]['exam_id'], 'num': num, 'type': ty,
                  'type_conflict': len(tys) > 1, 'md': bank.md_path(q).exists(),
                  'status': sorted(sts)}
    return uni


class FP:
    """题库全文指纹：所有题级 MD 归一化后连成一条大串，按片段 find 反查题键。"""

    def __init__(self, bank, uni):
        self.keys, self.starts, parts, pos = [], [], [], 0
        self.text = {}
        self.nostem = set()
        for q in uni:
            p = bank.md_path(q)
            if not p.exists():
                continue
            t = p.read_text(encoding='utf-8', errors='replace')
            self.text[q] = t
            if re.search(r'采用题面小节[:：]\s*无', t):
                self.nostem.add(q)
            n = QP.norm_text(t)
            self.keys.append(q)
            self.starts.append(pos)
            parts.append(n + '|')
            pos += len(n) + 1
        self.big = ''.join(parts)

    def owner(self, off):
        return self.keys[bisect.bisect_right(self.starts, off) - 1]

    def hits(self, snip, cap=12):
        out, i = set(), self.big.find(snip)
        while i >= 0 and len(out) < cap:
            out.add(self.owner(i))
            i = self.big.find(snip, i + 1)
        return out

    SKIP = re.compile(r'^\s*(#|>|-|\||（未|（无|\*)')

    def stem(self, q, limit=500):
        out, n = [], 0
        for ln in self.text.get(q, '').split('\n'):
            if not ln.strip() or self.SKIP.match(ln):
                continue
            out.append(ln)
            n += len(QP.norm_text(ln))
            if n > limit:
                break
        return '\n'.join(out)

    def selfdup(self, cache=None, sig=None):
        """题库自查：每题取题面前 500 字的 5 个片段全库反查，别的题命中≥4 记为重复对。按 questions.csv 签名缓存。"""
        if cache and Path(cache).exists():
            d = json.loads(Path(cache).read_text(encoding='utf-8'))
            if d.get('sig') == sig:
                return d['pairs'], True
        pairs = []
        for q in self.keys:
            best, sc, n, top = self.search(self.stem(q))
            for k, v in top.items():
                if k != q and v >= 4 and n >= 4:
                    pairs.append([q, k, v, n])
        if cache:
            Path(cache).write_text(json.dumps({'sig': sig, 'pairs': pairs}, ensure_ascii=False), encoding='utf-8')
        return pairs, False

    def search(self, material, n=5, width=10):
        snips = QP.probe_snippets(material, n, width)
        if not snips:
            return None, 0, 0, {}
        c = Counter()
        for s in snips:
            for q in self.hits(s):
                c[q] += 1
        if not c:
            return None, 0, len(snips), {}
        ranked = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
        return ranked[0][0], ranked[0][1], len(snips), dict(ranked)


# ------------------------------------------------------------------ 单本书
SRC_LABELS = ('【材料原文】', '【原题材料】', '【题目】', '【材料】', '【设问】', '【题干】', '【原题】')


def book_material(b, src_styles):
    lines = [(r['style'], r['text'].strip()) for r in b['_recs'][1:] if r['text'].strip()]
    return QP.material_text(lines, src_styles)


def scan_book(book_id, prof_ref, docx, bank, keymap, fp):
    t0 = time.time()
    prof = load_profile(prof_ref)
    cfg = BI.BookCfg(prof)
    doc = BI.load_docx(docx)
    blocks, drill_rows, heads, stats = BI.walk(doc, cfg)
    blocks = BI.finish_blocks(blocks, doc, cfg)
    items, _ = BI.finish_drill(drill_rows, cfg) if drill_rows else ([], 0)
    t0 = tick('01_切块(block_index)', t0)
    src_styles = set(prof.get('styles', {}).get('source') or [])
    refs = []   # 每条：来源层、位置、写法、解析结果
    for b in blocks:
        layer = 'drill_card' if b['kind'].startswith('drill_card') else 'block'
        mat = book_material(b, src_styles) if fp is not None else None
        res = QP.resolve_all(b['src'] or b['title'], bank, keymap, probe_text=mat)
        for r in res:
            refs.append({'layer': layer, 'kind': b['kind'], 'id': b['id'], 'node': b['node'], 'raw': b['src'] or b['title'],
                         'key': r.get('key'), 'subq': r.get('subq'), 'status': r['status'],
                         'cands': r.get('candidates'), 'notes': r.get('notes'), 'basis': r.get('basis'),
                         '_mat': mat if len(res) == 1 else None})
    t0 = tick('02_例题题源解析(qpack.resolve_all＋探针)', t0)
    seen_stem = {}
    for it in items:
        if it['src']:
            for r in QP.resolve_all(it['src'], bank, keymap):
                refs.append({'layer': 'drill', 'kind': 'drill', 'id': it['id'], 'node': it['group'], 'raw': it['src'],
                             'key': r.get('key'), 'subq': r.get('subq'), 'status': r['status'],
                             'cands': r.get('candidates'), 'notes': r.get('notes'), 'basis': r.get('basis')})
        elif fp is not None:
            st = QP.norm_text(it['stem'])
            if st in seen_stem:
                q, sc, n = seen_stem[st]
            else:
                q, sc, n, _ = fp.search(it['stem'], n=3, width=8)
                seen_stem[st] = (q, sc, n)
            ok = q is not None and n >= 2 and sc >= 2
            refs.append({'layer': 'drill_fp' if ok else 'drill_nosrc', 'kind': 'drill', 'id': it['id'], 'node': it['group'],
                         'raw': it['stem'][:60], 'key': q if ok else None, 'subq': None,
                         'status': 'fp_ok' if ok else 'fp_none', 'fp': f'{sc}/{n}'})
        else:
            refs.append({'layer': 'drill_nosrc', 'kind': 'drill', 'id': it['id'], 'node': it['group'], 'raw': it['stem'][:60],
                         'key': None, 'subq': None, 'status': 'no_src'})
    t0 = tick('03_题肢题源解析/指纹', t0)
    # 全文题源提及（含目录、细则说明里的“同类题”、题肢行内括注等）
    for p in doc['paras']:
        if p['fallback'] or not p['text'].strip():
            continue
        t = p['text']
        if not QP.has_source(t):
            continue
        for r in QP.resolve_all(t, bank, keymap):
            if r['status'] == 'unparsed':
                continue
            refs.append({'layer': 'mention', 'kind': p['style'], 'id': f"p{p['p']}", 'node': '', 'raw': t[:80],
                         'key': r.get('key'), 'subq': r.get('subq'), 'status': r['status'],
                         'cands': r.get('candidates')})
    t0 = tick('04_全文题源提及扫描', t0)
    # 身份探针：例题题面与所解析题键的题级 MD 对不上时，全库反查
    idmis = []
    if fp is not None:
        for r in refs:
            mat = r.pop('_mat', None)
            if r['layer'] == 'block' and r['status'] != 'ok' and mat and len(QP.norm_text(mat)) >= 40:
                q, sc, n, top = fp.search(mat)
                second = max([v for k, v in top.items() if k != q] + [0])
                r['fp_suggest'] = q if (q and sc >= QP.PROBE_MIN and sc - second >= QP.PROBE_LEAD) else None
                r['fp_top'] = top
                continue
            if r['layer'] != 'block' or r['status'] != 'ok' or not mat or len(QP.norm_text(mat)) < 40:
                continue
            own = QP.probe_text(mat, fp.text.get(r['key'], ''))
            r['probe'] = f'{own[0]}/{own[1]}'
            if own[1] and own[0] <= 1:
                q, sc, n, top = fp.search(mat)
                second = max([v for k, v in top.items() if k != q] + [own[0]])
                strong = q is not None and q != r['key'] and sc >= QP.PROBE_MIN and sc - second >= QP.PROBE_LEAD
                nostem = r['key'] in fp.nostem
                verdict = ('bank_stem_missing_no_redirect' if nostem and strong else
                           'content_is_other_question' if strong else 'weak_or_bank_text_unusable')
                strong = strong and not nostem
                idmis.append({'book': book_id, 'block': r['id'], 'raw': r['raw'], 'key': r['key'], 'own_probe': f'{own[0]}/{own[1]}',
                              'best': q, 'best_probe': f'{sc}/{n}', 'top': top, 'node': r['node'],
                              'verdict': verdict,
                              'own_exam_status': (bank.tasks.get(r['key'].rsplit('-Q', 1)[0]) or {}).get('current_stage', '')})
                if strong and REDIRECT:
                    r['orig_key'], r['key'], r['basis'] = r['key'], q, (r.get('basis') or '') + '+fp_redirect'
    else:
        for r in refs:
            r.pop('_mat', None)
    t0 = tick('05_身份探针与全库反查', t0)
    meta = {'book': book_id, 'docx': docx, 'profile': prof.get('_profile_path'), 'blocks': len(blocks),
            'blocks_by_kind': dict(Counter(b['kind'] for b in blocks)), 'drill_items': len(items),
            'drill_src_empty': sum(1 for i in items if not i['src'])}
    return meta, refs, idmis


# ------------------------------------------------------------------ 汇总
STRONG = ('block', 'drill_card', 'drill')
REDIRECT = True
FINISHED = ('bixiu2', 'bixiu3')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--books', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--no-fp', action='store_true', help='不建题库全文指纹（最快；无题源题肢不归属、不做身份反查）')
    ap.add_argument('--cache', help='题库自查缓存目录（缺省为脚本旁 _cache/）；题库 questions.csv 不变则复用')
    ap.add_argument('--baseline', help='上次的 coverage_state.json；给出则输出新增/消失的覆盖')
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    t_all = t0 = time.time()
    bank = QP.Bank()
    keymap = QP.load_keymap()
    uni = load_universe(bank)
    t0 = tick('00_读题库索引', t0)
    fp = None
    if not a.no_fp:
        fp = FP(bank, uni)
        t0 = tick('00b_题库全文指纹', t0)
    books = [l.rstrip('\n').split('\t') for l in open(a.books, encoding='utf-8') if l.strip() and not l.startswith('#')]
    metas, allrefs, allmis = [], {}, []
    for bid, prof, docx in books:
        m, refs, mis = scan_book(bid, prof, docx, bank, keymap, fp)
        metas.append(m)
        allrefs[bid] = refs
        allmis += mis
    t0 = time.time()
    bids = [b[0] for b in books]

    # 每书解析统计
    per_book = OrderedDict()
    cover = defaultdict(lambda: defaultdict(lambda: {'layers': Counter(), 'subq': set()}))  # qid -> book -> info
    notin = []
    for bid in bids:
        refs = allrefs[bid]
        st = OrderedDict()
        for layer in ('block', 'drill_card', 'drill', 'drill_fp', 'drill_nosrc', 'mention'):
            rr = [r for r in refs if r['layer'] == layer]
            if not rr:
                continue
            st[layer] = {'refs': len(rr), 'status': dict(Counter(r['status'] for r in rr)),
                         'keys_unique': len({r['key'] for r in rr if r['key']})}
        blk = [r for r in refs if r['layer'] in STRONG]
        ok = [r for r in blk if r['status'] == 'ok']
        st['strong_refs'] = len(blk)
        st['strong_ok'] = len(ok)
        st['strong_ok_rate'] = round(len(ok) / len(blk), 4) if blk else None
        bad = [r for r in blk if r['status'] != 'ok']
        st['unresolved_samples'] = [{k: r.get(k) for k in ('layer', 'id', 'raw', 'status', 'cands', 'notes', 'key')}
                                    for r in bad[:12]]
        st['unresolved_by_status'] = dict(Counter(r['status'] for r in bad))
        per_book[bid] = st
        for r in refs:
            if r['layer'] in STRONG and r['status'] != 'ok' and r.get('fp_suggest') and REDIRECT:
                notin.append({'book': bid, **{k: r.get(k) for k in ('layer', 'id', 'raw', 'status', 'key', 'cands', 'notes', 'fp_suggest', 'fp_top')}})
                r['orig_key'], r['orig_status'], r['key'], r['status'] = r.get('key'), r['status'], r['fp_suggest'], 'ok'
                r['basis'] = (r.get('basis') or '') + '+fp_resolved'
            if r['key'] and r['status'] in ('ok', 'fp_ok') and r['key'] in uni:
                c = cover[r['key']][bid]
                c['layers'][r['layer']] += 1
                if r.get('subq'):
                    c['subq'].add(r['subq'])
                elif r['layer'] in STRONG:
                    c['subq'].add('整题')
            elif r['layer'] in STRONG and r['status'] != 'ok':
                notin.append({'book': bid, **{k: r.get(k) for k in ('layer', 'id', 'raw', 'status', 'key', 'cands', 'notes', 'fp_suggest', 'fp_top')}})
            elif r['layer'] in STRONG and r['key'] and r['key'] not in uni:
                notin.append({'book': bid, 'layer': r['layer'], 'id': r['id'], 'raw': r['raw'], 'status': 'key_not_in_questions_csv',
                              'key': r['key'], 'cands': None, 'notes': None})
    # 每书按卷分布（强覆盖＋指纹）
    by_exam = defaultdict(Counter)
    for q, bb in cover.items():
        for bid, c in bb.items():
            if any(c['layers'][l] for l in STRONG + ('drill_fp',)):
                by_exam[uni[q]['exam']][bid] += 1

    def level(c):
        if any(c['layers'][l] for l in STRONG):
            return 'S'
        if c['layers']['drill_fp']:
            return 'F'
        if c['layers']['mention']:
            return 'M'
        return ''
    # 题库重复登记：跨卷重复对 → 等价类（覆盖任一即视为覆盖）；卷对重复≥半数记为重复登记卷
    alias = {}
    dup_exams = []
    if fp is not None:
        qcsv = bank.root / 'indexes/questions.csv'
        sig = f"{qcsv.stat().st_size}:{int(qcsv.stat().st_mtime)}:{len(fp.keys)}"
        cdir = Path(a.cache) if a.cache else Path(__file__).resolve().parent / '_cache'
        cdir.mkdir(parents=True, exist_ok=True)
        pairs, cached = fp.selfdup(cdir / 'selfdup.json', sig)
        t0 = tick('00c_题库自查重复' + ('(缓存)' if cached else ''), t0)
        par = {}

        def find(x):
            while par.get(x, x) != x:
                x = par[x]
            return x
        cross = [(a_, b_) for a_, b_, _, _ in pairs if a_.rsplit('-Q', 1)[0] != b_.rsplit('-Q', 1)[0]]
        for a_, b_ in cross:
            ra, rb = find(a_), find(b_)
            if ra != rb:
                par[max(ra, rb)] = min(ra, rb)
        groups = defaultdict(set)
        for q in {x for pr in cross for x in pr}:
            groups[find(q)].add(q)
        for g in groups.values():
            for q in g:
                alias[q] = sorted(g)
        ep = Counter()
        for a_, b_ in {tuple(sorted(pr)) for pr in cross}:
            ep[tuple(sorted((a_.rsplit('-Q', 1)[0], b_.rsplit('-Q', 1)[0])))] += 1
        for (ea, eb), n in ep.most_common():
            na = sum(1 for u in uni.values() if u['exam'] == ea)
            nb = sum(1 for u in uni.values() if u['exam'] == eb)
            dup_exams.append({'exam_a': ea, 'exam_b': eb, 'dup_questions': n, 'qa': na, 'qb': nb,
                              'kind': 'duplicate_registration' if n >= 0.5 * min(na, nb) else 'shared_or_reused_questions'})
        same_exam_pairs = sum(1 for a_, b_, _, _ in pairs if a_.rsplit('-Q', 1)[0] == b_.rsplit('-Q', 1)[0])
    else:
        same_exam_pairs = None
    # 矩阵
    exams = sorted({u['exam'] for u in uni.values()})
    targets = [b for b in bids if b not in FINISHED]
    exam_touch6 = {e: sum(by_exam[e][b] for b in targets) for e in exams}
    mrows, orphans, multi = [], [], []
    for q, u in uni.items():
        cells = {bid: level(cover[q][bid]) if bid in cover.get(q, {}) else '' for bid in bids}
        sub = {bid: '/'.join(sorted(cover[q][bid]['subq'])) for bid in bids if cover.get(q, {}).get(bid) and cover[q][bid]['subq']}
        strong_books = [b for b in bids if cells[b] in ('S', 'F')]
        dup_cov = sorted({b for k in alias.get(q, []) if k != q for b in bids
                          if cover.get(k, {}).get(b) and level(cover[k][b]) in ('S', 'F')})
        row = OrderedDict([('qid', q), ('exam', u['exam']), ('num', u['num']), ('type', u['type']), ('n_books', len(strong_books))])
        for b in bids:
            row[b] = cells[b] + (f"[{sub[b]}]" if b in sub and sub[b] != '整题' else '')
        row['dup_of'] = ';'.join(k for k in alias.get(q, []) if k != q)
        row['dup_covered_by'] = ';'.join(dup_cov)
        mrows.append(row)
        if not strong_books:
            if dup_cov:
                cat = 'dup_of_covered'
            elif exam_touch6[u['exam']] == 0:
                cat = 'exam_untouched_by_targets'
            else:
                cat = 'scattered_in_processed_exam'
            orphans.append(OrderedDict([('qid', q), ('exam', u['exam']), ('num', u['num']), ('type', u['type']),
                                        ('category', cat), ('dup_of', row['dup_of']), ('dup_covered_by', row['dup_covered_by']),
                                        ('mention_in', ';'.join(b for b in bids if cells[b] == 'M')), ('md', u['md']),
                                        ('bank_status', (bank.tasks.get(u['exam']) or {}).get('status', ''))]))
        if len(strong_books) >= 2:
            subs = {b: cover[q][b]['subq'] for b in strong_books}
            named = {b: {x for x in v if x != '整题'} for b, v in subs.items()}
            same = set()
            bl = list(strong_books)
            for i in range(len(bl)):
                for j in range(i + 1, len(bl)):
                    same |= named[bl[i]] & named[bl[j]]
            whole = [b for b in strong_books if '整题' in subs[b]]
            if u['type'] == '选择题':
                mk = 'choice_in_multiple_books'
            elif same:
                mk = 'same_subq_in_multiple_books'
            elif whole:
                mk = 'whole_question_ref_overlaps'
            else:
                mk = 'different_subq_split'
            multi.append(OrderedDict([('qid', q), ('type', u['type']), ('books', ';'.join(strong_books)), ('kind', mk),
                                      ('subq', ' | '.join(f"{b}:{'/'.join(sorted(subs[b])) or '指纹'}" for b in strong_books)),
                                      ('same_subq', '/'.join(sorted(same))), ('whole_in', ';'.join(whole))]))
    # 各目标书卷级缺口：该书在某卷 0 题；偏少：低于该书非零卷中位数的 40%
    gaps = []
    for b in bids:
        nz = sorted(by_exam[e][b] for e in exams if by_exam[e][b])
        med = nz[len(nz) // 2] if nz else 0
        for e in exams:
            n = by_exam[e][b]
            if n == 0 or n < 0.4 * med:
                gaps.append(OrderedDict([('book', b), ('exam', e), ('covered', n), ('book_median_per_exam', med),
                                         ('flag', 'zero' if n == 0 else 'low'),
                                         ('other_targets_touch', exam_touch6[e] - (n if b in targets else 0)),
                                         ('bank_status', (bank.tasks.get(e) or {}).get('status', ''))]))
    t0 = tick('06_汇总矩阵', t0)

    # 写文件
    def wcsv(name, rows, fields=None):
        with open(out / name, 'w', encoding='utf-8-sig', newline='') as f:
            if not rows:
                f.write('')
                return
            w = csv.DictWriter(f, fieldnames=fields or list(rows[0].keys()))
            w.writeheader()
            for r in rows:
                w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()})
    wcsv('matrix.csv', mrows)
    wcsv('orphans.csv', orphans)
    wcsv('multi_book.csv', multi)
    wcsv('not_resolved_or_not_in_bank.csv', notin)
    wcsv('identity_mismatch.csv', allmis)
    em = [OrderedDict([('exam', e), ('bank_q', sum(1 for u in uni.values() if u['exam'] == e))] +
                      [(b, by_exam[e][b]) for b in bids] +
                      [('orphans', sum(1 for o in orphans if o['exam'] == e))]) for e in exams]
    wcsv('by_exam.csv', em)
    wcsv('exam_gaps.csv', gaps)
    wcsv('bank_duplicate_exams.csv', dup_exams)
    state = {q: {b: level(cover[q][b]) for b in cover[q]} for q in cover}
    (out / 'coverage_state.json').write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
    delta = None
    if a.baseline and Path(a.baseline).exists():
        old = json.loads(Path(a.baseline).read_text(encoding='utf-8'))
        gained, lost = [], []
        for q in set(old) | set(state):
            for b in set(old.get(q, {})) | set(state.get(q, {})):
                o, n = old.get(q, {}).get(b, ''), state.get(q, {}).get(b, '')
                if o in ('S', 'F') and n not in ('S', 'F'):
                    lost.append((q, b, o, n))
                elif n in ('S', 'F') and o not in ('S', 'F'):
                    gained.append((q, b, o, n))
        delta = {'gained': len(gained), 'lost': len(lost), 'lost_list': lost[:200], 'gained_list': gained[:200]}
    # 汇总
    typ = Counter(o['type'] for o in orphans)
    summary = OrderedDict([
        ('bank', str(bank.root)), ('universe_questions', len(uni)), ('universe_exams', len(exams)),
        ('universe_by_type', dict(Counter(u['type'] for u in uni.values()))),
        ('books', metas), ('per_book', per_book),
        ('covered_any_strong_or_fp', sum(1 for r in mrows if r['n_books'] >= 1)),
        ('orphans', len(orphans)), ('orphans_by_type', dict(typ)),
        ('orphans_by_category', dict(Counter(o['category'] for o in orphans))),
        ('orphans_by_category_type', {f"{k[0]}|{k[1]}": v for k, v in Counter((o['category'], o['type']) for o in orphans).items()}),
        ('multi_book_by_kind', dict(Counter(m['kind'] for m in multi))),
        ('bank_duplicate_exam_pairs', dup_exams[:20]), ('bank_same_exam_overlap_pairs', same_exam_pairs),
        ('exam_gaps_zero_by_book', {b: sum(1 for g in gaps if g['book'] == b and g['flag'] == 'zero') for b in bids}),
        ('identity_by_verdict', dict(Counter(m['verdict'] for m in allmis))),
        ('identity_redirected', sum(1 for b in bids for r in allrefs[b] if r.get('orig_key'))),
        ('orphans_mention_only', sum(1 for o in orphans if o['mention_in'])),
        ('multi_book', len(multi)), ('multi_book_same_subq_or_whole', sum(1 for m in multi if m['same_subq'] or m['whole_in'])),
        ('not_resolved_or_not_in_bank', len(notin)), ('not_resolved_by_status', dict(Counter(n['status'] for n in notin))),
        ('identity_mismatch_candidates', len(allmis)),
        ('bank_questions_without_stem', len(fp.nostem) if fp else None),
        ('delta_vs_baseline', delta),
        ('timing_seconds', T), ('total_seconds', round(time.time() - t_all, 2)),
    ])
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    refs_out = {b: [{k: v for k, v in r.items() if not k.startswith('_')} for r in allrefs[b]] for b in bids}
    (out / 'refs.json').write_text(json.dumps(refs_out, ensure_ascii=False), encoding='utf-8')
    print(json.dumps({k: summary[k] for k in ('universe_questions', 'covered_any_strong_or_fp', 'orphans', 'orphans_by_type',
                                              'multi_book', 'not_resolved_or_not_in_bank', 'identity_mismatch_candidates',
                                              'total_seconds')}, ensure_ascii=False))
    print(json.dumps(T, ensure_ascii=False))


if __name__ == '__main__':
    main()
