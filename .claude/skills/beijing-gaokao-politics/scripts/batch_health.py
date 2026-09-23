#!/usr/bin/env python3
"""每批体检：只读 DOCX（可加同版 PDF、上一批基线 DOCX），输出确定性指标。

同一文件每次跑出同样的数字；指标全绿不等于内容已审，只说明机械层没有回退。
不改任何输入文件。用法：
  python3 batch_health.py --docx 本批.docx [--pdf 本批.pdf] [--baseline 上批.docx] [--out 体检.json]
退出码：0 全部通过；1 有 FAIL 项；2 输入错误。
"""
import argparse, hashlib, json, re, sys, zipfile
from collections import Counter, OrderedDict
from pathlib import Path
from lxml import etree

W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'

# 学生正文里不得出现的工程/后台话语（style-spec「段落与工程痕迹」、C-108、用户2026-09-15/22 意见）
ENGINEERING_WORDS = [
    'uncertain', '需核', '待核', '原提取', '（供参考）', '评分位置', '直接命中', '稳妥覆盖',
    '覆盖当前标题', '其他评分位置', '本节点', '当前标题', '后台', '我们的归纳', '合并记录',
    '答题公式', '套路', '口诀', '来源：', '出处', 'E1', 'E3', 'TODO', '？？',
]
# 只提示、不拦：细则可能原样引用官方的“不是……而是”
WARN_PATTERNS = {'不是……而是句式': re.compile(r'不是[^。；！？\n]{1,40}而是')}
# 条目末尾括注试卷信息或分值（用户2026-09-15：常见表述等栏目不跟试卷、题号、分值、来源）
TRAILING_TAG = re.compile(r'[（(][^（()）]*((20\d{2}|\d{2})\s*[一-龥]{0,4}(一模|二模|期中|期末|高考|适应性)'
                          r'|第\d+(\(\d\))?题|\d+\s*分)[^（()）]*[)）][。；]?$')

# 按样式名分区：题面原文与标题可以有年份、题号
SOURCE_STYLES = {'题目材料', '题目设问', '题目选项', 'heading 3'}
TOC_STYLES = {'目录一级', '目录二级', 'toc 1', 'toc 2', 'toc 3'}
# 细则可写分值；专题里列主例、变式题源的考法分类行本来就写题源与分值
TAG_OK_STYLES = {'细则说明', '考法分类', 'heading 1', 'heading 2'} | SOURCE_STYLES
TITLE_RE = re.compile(r'^(例题|选择例题)\s*(\d+)[　 ]+(.+)$')
METHOD_RE = re.compile(r'^考法(\d+)[　 ].*?（(\d+)题）\s*$')
SUBJ_LABELS = ['【题目】', '【思维链条】', '【答案落点】', '【细则说明】']
CHOICE_LABELS = ['【答案】', '【分析过程】']


def sha256(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def norm(t):
    return re.sub(r'\s+', '', t)


def load_docx(path):
    z = zipfile.ZipFile(path)
    styles = {}
    for st in etree.fromstring(z.read('word/styles.xml')).iter(W + 'style'):
        n = st.find(W + 'name')
        styles[st.get(W + 'styleId')] = n.get(W + 'val') if n is not None else st.get(W + 'styleId')
    body = etree.fromstring(z.read('word/document.xml')).find(W + 'body')
    paras = []
    for p in body.iter(W + 'p'):
        s = p.find(f'{W}pPr/{W}pStyle')
        sid = s.get(W + 'val') if s is not None else None
        in_tbl = any(a.tag == W + 'tbl' for a in p.iterancestors())
        # 域代码（PAGEREF 等）不算正文文字
        txt = ''.join(t.text or '' for t in p.iter(W + 't')).strip()
        instr = ''.join(t.text or '' for t in p.iter(W + 'instrText'))
        if txt or instr:
            paras.append({'i': len(paras), 'style': styles.get(sid, sid or '正文'), 'text': txt, 'instr': instr, 'table': in_tbl})
    return paras


def analyse(paras):
    r = OrderedDict()
    # 1. 栏目计数
    labels = Counter()
    for p in paras:
        for m in re.findall(r'【[^】]{2,10}】', p['text']):
            labels[m] += 1
    titles = [(p, TITLE_RE.match(p['text'])) for p in paras if p['style'] == 'heading 3']
    titles = [(p, m) for p, m in titles if m]
    n_subj = sum(1 for _, m in titles if m.group(1) == '例题')
    n_choice = sum(1 for _, m in titles if m.group(1) == '选择例题')
    subj = {k: labels[k] for k in SUBJ_LABELS}
    choice = {k: labels[k] for k in CHOICE_LABELS}
    r['columns'] = {
        'subjective_titles': n_subj, 'choice_titles': n_choice,
        'subjective_labels': subj, 'choice_labels': choice,
        'pass': len(set(subj.values()) | {n_subj}) == 1 and len(set(choice.values()) | {n_choice}) == 1,
        'all_labels_top': dict(labels.most_common(40)),
    }

    # 2. 例题编号：每个 heading 1/2 下，例题与选择例题各自从 1 连续
    issues, ctx, seen = [], None, {}
    for p in paras:
        if p['style'] in ('heading 1', 'heading 2'):
            ctx, seen = p['text'][:30], {}
            continue
        if p['style'] == 'heading 3':
            m = TITLE_RE.match(p['text'])
            if not m:
                continue
            kind, num = m.group(1), int(m.group(2))
            exp = seen.get(kind, 0) + 1
            if num != exp:
                issues.append({'node': ctx, 'expected': exp, 'actual': num, 'text': p['text'][:40]})
            seen[kind] = num
    r['numbering'] = {'titles': len(titles), 'issues': issues[:30], 'issue_count': len(issues), 'pass': not issues}

    # 3. 考法标称题数 = 该考法下实际例题数（到下一考法或下一节点为止）
    bad, cur = [], None
    def close(c):
        if c and c['claimed'] != c['actual']:
            bad.append({k: c[k] for k in ('method', 'claimed', 'actual')})
    for p in paras:
        if p['style'] == '具体考法':
            close(cur)
            m = METHOD_RE.match(p['text'])
            cur = {'method': p['text'][:36], 'claimed': int(m.group(2)) if m else None, 'actual': 0}
        elif p['style'] in ('heading 1', 'heading 2'):
            close(cur); cur = None
        elif p['style'] == 'heading 3' and cur:
            # 标称题数只算主观例题；选择例题统一放在节点末尾
            m = TITLE_RE.match(p['text'])
            if m and m.group(1) == '例题':
                cur['actual'] += 1
    close(cur)
    n_methods = sum(1 for p in paras if p['style'] == '具体考法')
    r['method_counts'] = {'methods': n_methods, 'mismatch': bad, 'pass': not bad}

    # 4. 学生正文工程痕迹与禁用句式（题面原文、题目标题、目录除外）
    hits, warns = [], []
    for p in paras:
        if p['style'] in SOURCE_STYLES or p['style'] in TOC_STYLES:
            continue
        t = p['text']
        for w in ENGINEERING_WORDS:
            if w in t:
                hits.append({'rule': '工程词:' + w, 'style': p['style'], 'text': t[:60]})
        if not p['table'] and p['style'] not in TAG_OK_STYLES and TRAILING_TAG.search(t):
            hits.append({'rule': '条目末尾带试卷/分值', 'style': p['style'], 'text': t[-60:]})
        for name, rx in WARN_PATTERNS.items():
            if rx.search(t):
                warns.append({'rule': name, 'style': p['style'], 'text': t[:60]})
    by_rule = Counter(h['rule'] for h in hits)
    r['student_text'] = {'hit_count': len(hits), 'by_rule': dict(by_rule), 'samples': hits[:40], 'pass': not hits,
                         'warning_count': len(warns), 'warnings': warns[:40]}

    # 5. 题肢单练（表格内）不得出现“不选”
    notsel = [p['text'][:40] for p in paras if p['table'] and re.fullmatch(r'不选', p['text'])]
    r['drill_notsel'] = {'count': len(notsel), 'pass': not notsel}

    # 6. 目录缓存页码
    toc = []
    for p in paras:
        if p['style'] in TOC_STYLES:
            m = re.match(r'^(.*?)\s*(\d+)$', p['text'])
            if m:
                toc.append({'title': m.group(1).strip(), 'cached_page': int(m.group(2))})
    r['toc'] = {'entries': len(toc), 'items': toc}
    return r, titles


def example_blocks(paras):
    """例题块：从例题标题到下一个标题/考法/节点；键=节点+题源+同节点序号。"""
    blocks, node, cur, occ = OrderedDict(), '', None, Counter()
    for p in paras:
        st = p['style']
        if st in ('heading 1', 'heading 2'):
            node, cur = p['text'][:30], None
            continue
        if st == 'heading 3':
            m = TITLE_RE.match(p['text'])
            if m:
                base = (node, m.group(1), m.group(3))
                occ[base] += 1
                key = ' | '.join(base) + f' #{occ[base]}'
                cur = blocks.setdefault(key, [])
                continue
            cur = None
            continue
        if st in ('具体考法', '考法说明'):
            cur = None
            continue
        if cur is not None:
            cur.append(p['text'])
    return OrderedDict((k, hashlib.sha1('\n'.join(v).encode()).hexdigest()[:12]) for k, v in blocks.items())


def by_source(blocks):
    """去掉节点与序号，只按题源聚合，用于区分“移动/重编号”与“正文改动”。"""
    out = {}
    for k, h in blocks.items():
        node, kind, src_occ = k.split(' | ', 2)
        out.setdefault(kind + ' | ' + src_occ.rsplit(' #', 1)[0], Counter())[h] += 1
    return out


def diff(cur_blocks, base_blocks):
    a, b = by_source(base_blocks), by_source(cur_blocks)
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
    moved = sorted(k for k in set(cur_blocks) - set(base_blocks)
                   if k.split(' | ', 1)[1].rsplit(' #', 1)[0] in set(a) and k.split(' | ', 1)[1].rsplit(' #', 1)[0] not in changed)
    return {'base_blocks': len(base_blocks), 'cur_blocks': len(cur_blocks),
            'unchanged_body_sources': len(set(a) & set(b)) - len(changed),
            'added': added, 'removed': removed, 'body_changed': changed,
            'relocated_block_keys': len(moved)}


def check_pdf(pdf, paras, toc):
    import fitz
    d = fitz.open(pdf)
    pages = [pg.get_text() for pg in d]
    out = {'pages': len(d)}
    # 页脚“— N —”连续
    foot = []
    for i, t in enumerate(pages):
        m = re.search(r'—\s*(\d+)\s*—', t)
        foot.append(int(m.group(1)) if m else None)
    breaks = [i + 1 for i, n in enumerate(foot) if n is not None and n != i + 1]
    missing = [i + 1 for i, n in enumerate(foot) if n is None]
    out['footer'] = {'missing': missing[:20], 'not_sequential': breaks[:20], 'pass': not breaks}
    # 目录缓存页码 vs 标题实际所在页（跳过目录页本身）
    npages = [norm(t) for t in pages]
    toc_pages = {i for i, t in enumerate(pages[:8]) if '目录' in t[:30] or '.......' in t}
    wrong, notfound = [], []
    for e in toc:
        key = norm(e['title'])[:18]
        found = next((i + 1 for i, t in enumerate(npages) if i not in toc_pages and key in t), None)
        if found is None:
            notfound.append(e['title'][:30])
        elif found != e['cached_page']:
            wrong.append({'title': e['title'][:30], 'toc': e['cached_page'], 'pdf': found})
    out['toc_vs_pdf'] = {'checked': len(toc), 'wrong': wrong, 'not_found': notfound, 'pass': not wrong and not notfound}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--docx', required=True)
    ap.add_argument('--pdf')
    ap.add_argument('--baseline', help='上一批 DOCX，用来列出正文真正改动的例题')
    ap.add_argument('--out')
    a = ap.parse_args()
    for f in (a.docx, a.pdf, a.baseline):
        if f and not Path(f).is_file():
            print('找不到文件：', f, file=sys.stderr); return 2

    paras = load_docx(a.docx)
    rep, _ = analyse(paras)
    res = OrderedDict([('docx', {'path': str(Path(a.docx).resolve()), 'sha256': sha256(a.docx)})])
    res.update(rep)
    toc_items = rep['toc'].pop('items')
    if a.pdf:
        res['pdf'] = {'path': str(Path(a.pdf).resolve()), 'sha256': sha256(a.pdf)}
        res['pdf'].update(check_pdf(a.pdf, paras, toc_items))
    cur_blocks = example_blocks(paras)
    if a.baseline:
        base_paras = load_docx(a.baseline)
        base_rep, _ = analyse(base_paras)
        res['baseline'] = {'path': str(Path(a.baseline).resolve()), 'sha256': sha256(a.baseline)}
        res['baseline']['metric_delta'] = {
            'subjective_titles': [base_rep['columns']['subjective_titles'], rep['columns']['subjective_titles']],
            'choice_titles': [base_rep['columns']['choice_titles'], rep['columns']['choice_titles']],
            'methods': [base_rep['method_counts']['methods'], rep['method_counts']['methods']],
            'student_text_hits': [base_rep['student_text']['hit_count'], rep['student_text']['hit_count']],
        }
        res['baseline']['examples'] = diff(cur_blocks, example_blocks(base_paras))

    gates = OrderedDict([
        ('四栏目与标题数一致', rep['columns']['pass']),
        ('例题编号连续', rep['numbering']['pass']),
        ('考法标称题数', rep['method_counts']['pass']),
        ('学生正文无工程痕迹', rep['student_text']['pass']),
        ('单练无“不选”', rep['drill_notsel']['pass']),
    ])
    if a.pdf:
        gates['页脚页码连续'] = res['pdf']['footer']['pass']
        gates['目录页码对PDF'] = res['pdf']['toc_vs_pdf']['pass']
    res['gates'] = gates
    res['pass'] = all(gates.values())

    out = Path(a.out) if a.out else Path(a.docx).with_suffix('.体检.json')
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1))

    c = rep['columns']
    print(f"主观例题 {c['subjective_titles']}｜选择例题 {c['choice_titles']}｜考法 {rep['method_counts']['methods']}"
          + (f"｜PDF {res['pdf']['pages']} 页" if a.pdf else ''))
    for k, v in gates.items():
        print(('  PASS ' if v else '  FAIL ') + k)
    if not rep['student_text']['pass']:
        print('  工程痕迹分布：', rep['student_text']['by_rule'])
    if rep['student_text']['warning_count']:
        print(f"  提示（不拦）：“不是……而是”句式 {rep['student_text']['warning_count']} 处，见明细 warnings")
    if a.baseline:
        e = res['baseline']['examples']
        print(f"  对上批：新增题源 {len(e['added'])}，删除 {len(e['removed'])}，正文改动 {len(e['body_changed'])}，"
              f"仅换位/重编号 {e['relocated_block_keys']}；正文未变 {e['unchanged_body_sources']}")
    print('明细：', out)
    return 0 if res['pass'] else 1


if __name__ == '__main__':
    sys.exit(main())
