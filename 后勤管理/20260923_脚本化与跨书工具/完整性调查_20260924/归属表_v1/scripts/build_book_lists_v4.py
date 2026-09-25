import sys; sys.dont_write_bytecode = True
import csv, json, os, collections

SALV = "/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/attribution_salvage/"
OUT_DIR = "/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924/归属表_v1/各书清单_v4/"
os.makedirs(OUT_DIR, exist_ok=True)

BOOKS = ['B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']  # B2 冻结，单独只作记录
ALL_BOOKS = ['B2'] + BOOKS

GET_FROM_RAW = 'attribution_v4.csv'  # 注意：必须用未叠加模型裁定的原始版本判定"书稿是否已收"。
# attribution_ruled_v4.csv 已经把 chk=错收 的裁定写回 归属_<M>=OUT，如果拿它来判定"是否已收"，
# 会和错收候选的判据（chk=错收）自我循环、必然算出0条错收——这是本脚本上一版的bug，这里改正。
with open(SALV + GET_FROM_RAW, encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))

final = json.load(open(SALV + 'final_judgments.json', encoding='utf-8'))

kind_label = {'gold': '金标', 'escalation': '升级复判', 'first_pass': '首判'}

# 身份错误/身份未确认行完全不参与任何候选（不计入分母）
rows = [r for r in rows if not (r.get('admission') or '').startswith('身份')]

by_qid_canon = collections.defaultdict(list)
for r in rows:
    by_qid_canon[r.get('canonical_qid') or r['qid']].append(r)

summary = {m: collections.Counter() for m in ALL_BOOKS}
book_rows = {m: {'miss': [], 'extra': [], 'opt': []} for m in ALL_BOOKS}

for r in rows:
    uid = r['unit_id']
    j = final.get(uid)
    admission = r.get('admission', '')
    typ = r.get('type', '')
    exam = r.get('exam_id_canonical', '')
    num = r.get('num', '')
    subq = r.get('subq', '')
    label = (num + (('(' + subq + ')') if subq else ''))

    rel = (j['j'].get('rel') or {}) if j else {}
    chk = (j['j'].get('chk') or {}) if j else {}
    opt = (j['j'].get('opt') or {}) if j else {}
    conf = (j.get('j', {}).get('conf', '') if j else '')
    why = (j.get('j', {}).get('why', '') if j else '')
    src_kind = j.get('kind', '') if j else '无判定'
    src_batch = j.get('batch', '') if j else ''
    src_label = ('%s(%s)' % (kind_label.get(src_kind, src_kind), src_batch)) if j else '无模型判定'

    for m in ALL_BOOKS:
        field = '归属_' + m
        collected = r.get(field) == 'COLLECTED'
        relval = rel.get(m)
        chkval = chk.get(m)

        # ---- 漏收候选 ----
        if (not collected) and relval in ('主', '跨'):
            gate_ok = False
            gate_note = ''
            if typ == '选择题':
                gate_ok = True
            else:
                if admission in ('完整题-有E1', '收-具名例外'):
                    gate_ok = True
                elif admission == '待裁决-证据未核实':
                    gate_ok = None  # 待核证据，单列
                else:
                    gate_ok = False
                    gate_note = '主观题准入不合规(%s)，不列入漏收' % admission
            if gate_ok is True or gate_ok is None:
                bucket = '漏收' if gate_ok is True else '待核证据'
                book_rows[m]['miss'].append({
                    '卷': exam, '题号_小问': label, '题型': typ, '主或跨': relval,
                    '证据状态': admission, '判定来源': src_label, 'conf': conf, 'why': why,
                    'unit_id': uid, '类别': bucket,
                })
                summary[m]['miss_' + bucket] += 1
                summary[m]['miss_' + bucket + '_' + ('选择' if typ == '选择题' else '主观')] += 1
                summary[m]['miss_' + bucket + '_' + ('主考' if relval == '主' else '跨模块')] += 1

        # ---- 错收候选 ----
        if collected and chkval == '错收':
            book_rows[m]['extra'].append({
                '卷': exam, '题号_小问': label, '题型': typ,
                '最终rel': relval if relval else '(未列为相关)', '证据状态': admission,
                '判定来源': src_label, 'conf': conf,
                'why': why + '（chk=错收，供参考，非唯一依据；本表以“已收(小问精确)且最终rel未affirm本模块相关”为主判据）',
                'unit_id': uid,
            })
            summary[m]['extra'] += 1
            summary[m]['extra_' + ('选择' if typ == '选择题' else '主观')] += 1

        # ---- 题肢候选（仅选择题） ----
        if typ == '选择题' and (not collected) and opt:
            for mark, mods in opt.items():
                if m in mods:
                    book_rows[m]['opt'].append({
                        '卷': exam, '题号': num, '题肢': mark, '题型': '选择题(题肢)',
                        '模块': m, '判定来源': src_label, 'conf': conf,
                        'why': why + '（无法机械核对该题肢是否已被其它入口单独收录，如实列出供人工核对）',
                        'unit_id': uid,
                    })
                    summary[m]['opt_candidates'] += 1

# ---- write per-book CSVs ----
for m in ALL_BOOKS:
    miss_path = OUT_DIR + m + '_漏收候选.csv'
    with open(miss_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['类别', '卷', '题号_小问', '题型', '主或跨', '证据状态',
                                          '判定来源', 'conf', 'why', 'unit_id'])
        w.writeheader()
        for row in sorted(book_rows[m]['miss'], key=lambda x: (x['类别'] != '漏收', x['卷'], x['题号_小问'])):
            w.writerow(row)

    extra_path = OUT_DIR + m + '_错收候选.csv'
    with open(extra_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['卷', '题号_小问', '题型', '最终rel', '证据状态',
                                          '判定来源', 'conf', 'why', 'unit_id'])
        w.writeheader()
        for row in sorted(book_rows[m]['extra'], key=lambda x: (x['卷'], x['题号_小问'])):
            w.writerow(row)

    opt_path = OUT_DIR + m + '_题肢候选.csv'
    with open(opt_path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['卷', '题号', '题肢', '题型', '模块', '判定来源', 'conf', 'why', 'unit_id'])
        w.writeheader()
        for row in sorted(book_rows[m]['opt'], key=lambda x: (x['卷'], x['题号'])):
            w.writerow(row)

    print(m, 'miss(漏收+待核证据)=', len(book_rows[m]['miss']), 'extra(错收)=', len(book_rows[m]['extra']),
          'opt(题肢)=', len(book_rows[m]['opt']))

json.dump({m: dict(summary[m]) for m in ALL_BOOKS}, open(SALV + 'summary_counts.json', 'w'),
           ensure_ascii=False, indent=1)
print('done')
