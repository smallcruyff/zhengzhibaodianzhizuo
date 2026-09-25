import sys; sys.dont_write_bytecode = True
import csv, glob, json, os, datetime, collections

ROOT = "/Users/wanglifei/Desktop/gpt和claude共同的小窝/后勤管理/20260923_脚本化与跨书工具/完整性调查_20260924/归属表_v1/"
MB = ROOT + "model_batch/"
SALV = "/private/tmp/claude-501/-Users-wanglifei-Desktop-gpt-claude-----/07ecc7d4-1283-4309-9858-715c562b9892/scratchpad/attribution_salvage/"
BOOKS = ['B2', 'B3', 'PH', 'CU', 'X1', 'X2', 'MI', 'RE']
RULE_VERSION_FINAL = '2026-09-24-attribution-v4-final'


def now_ts():
    return datetime.datetime.now().astimezone().isoformat(timespec='seconds')


def load_units(fname):
    d = json.load(open(fname, encoding='utf-8'))
    return d


# ---- 1. load attribution_v4.csv (subq-precise, identity/E1-fixed base) ----
with open(SALV + 'attribution_v4.csv', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    fieldnames = list(reader.fieldnames)
    attr_rows = list(reader)
by_uid = {r['unit_id']: r for r in attr_rows}

# ---- 2. load first-pass / escalation / gold judgments ----
def load_judgments(pattern):
    out = {}
    for path in sorted(glob.glob(pattern)):
        d = json.load(open(path, encoding='utf-8'))
        judge = d.get('judge', 'unknown')
        batch_id = d.get('batch_id', os.path.basename(path))
        for u in d.get('units', []):
            uid = u.get('unit_id')
            if uid:
                out[uid] = {'j': u, 'judge': judge, 'batch': batch_id, 'path': path}
    return out


first = load_judgments(MB + 'judgments/[cs][0-9][0-9][0-9].json')
esc = load_judgments(MB + 'judgments/esc*.json')
gold_data = json.load(open(MB + 'gold/gold_final.json', encoding='utf-8'))
gold = {}
for u in gold_data['units']:
    gold[u['unit_id']] = {'j': u, 'judge': gold_data.get('judge', 'claude-opus-5-5'),
                           'batch': 'gold_final', 'path': MB + 'gold/gold_final.json'}

print('first-pass units:', len(first), 'escalation units:', len(esc), 'gold units:', len(gold))
print('escalation ∩ gold:', len(set(esc) & set(gold)))

# final in-memory judgment (for LIST building): gold > escalation > first-pass
final = dict(first)
final.update(esc)
final.update(gold)
print('final merged units:', len(final))
src_kind = {}
for uid in final:
    if uid in gold:
        src_kind[uid] = 'gold'
    elif uid in esc:
        src_kind[uid] = 'escalation'
    else:
        src_kind[uid] = 'first_pass'
print('final source-kind counts:', collections.Counter(src_kind.values()))

# ---- 3. append rulings.jsonl (escalation-only-not-gold, to avoid corrupting existing
#          gold>escalation priority order that is already correctly in the file) ----
MODULES = BOOKS

def build_rulings_for_unit(uid, judgment, source_label, rule_version):
    out = []
    rel = judgment.get('rel') or {}
    chk = judgment.get('chk') or {}
    why = judgment.get('why', '')
    conf = judgment.get('conf', '')
    for m, label in rel.items():
        if m not in MODULES:
            continue
        if label in ('主', '跨') and m not in chk:
            out.append({'ts': now_ts(), 'ruler': source_label, 'scope': {'unit_id': uid},
                        'field': '归属_%s' % m, 'value': 'IN',
                        'reason': 'model judge: rel=%s conf=%s why=%s' % (label, conf, why),
                        'rule_version': rule_version})
    for m, label in chk.items():
        if m not in MODULES:
            continue
        if label == '维持':
            val = 'COLLECTED'
            reason = 'model judge: chk=维持 conf=%s why=%s' % (conf, why)
        elif label == '错收':
            val = 'OUT'
            reason = ('model judge: chk=错收候选 conf=%s why=%s（书稿是否真删仍需人工确认，本条只改归属表候选值，'
                       '不代为改书稿）' % (conf, why))
        elif label == '暂缓':
            val = 'MAYBE'
            reason = 'model judge: chk=暂缓(证据不足) conf=%s why=%s' % (conf, why)
        else:
            continue
        out.append({'ts': now_ts(), 'ruler': source_label, 'scope': {'unit_id': uid},
                    'field': '归属_%s' % m, 'value': val, 'reason': reason, 'rule_version': rule_version})
    return out


def dedup_key(o):
    return json.dumps({k: v for k, v in o.items() if k != 'ts'}, sort_keys=True, ensure_ascii=False)


existing_keys = set()
rulings_path = ROOT + 'rulings.jsonl'
with open(rulings_path, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            existing_keys.add(dedup_key(json.loads(line)))
        except json.JSONDecodeError:
            continue

gold_uids = set(gold.keys())
new_lines = []
n_skipped_gold_overlap = 0
for uid, info in esc.items():
    if uid in gold_uids:
        n_skipped_gold_overlap += 1
        continue  # gold已在文件中且优先级更高，保留其现有位置，不追加escalation覆盖
    label = 'model:%s:%s' % (info['judge'], info['batch'])
    for r in build_rulings_for_unit(uid, info['j'], label, RULE_VERSION_FINAL):
        k = dedup_key(r)
        if k in existing_keys:
            continue
        existing_keys.add(k)
        new_lines.append(r)

print('escalation units skipped (already superseded by gold, no append needed):', n_skipped_gold_overlap)
print('new ruling lines to append:', len(new_lines))

with open(rulings_path, 'a', encoding='utf-8') as fh:
    for r in new_lines:
        fh.write(json.dumps(r, ensure_ascii=False) + '\n')

# ---- 4. rebuild attribution_ruled.csv (last-matching-ruling-wins per field, same as apply_rulings_v3.py) ----
by_qid = collections.defaultdict(list)
for r in attr_rows:
    by_qid[r['qid']].append(r)

rulings_all = []
with open(rulings_path, encoding='utf-8') as fh:
    for line in fh:
        line = line.strip()
        if line:
            try:
                rulings_all.append(json.loads(line))
            except json.JSONDecodeError:
                pass
print('total rulings applied:', len(rulings_all))

changelog = []
for r in rulings_all:
    field = r.get('field')
    scope = r.get('scope', {})
    module = scope.get('module')
    if module and field != '归属_%s' % module:
        continue
    if field and field not in fieldnames:
        fieldnames.append(field)
        for row in attr_rows:
            row.setdefault(field, '')
    targets = []
    if 'unit_id' in scope and scope['unit_id'] in by_uid:
        targets = [by_uid[scope['unit_id']]]
    elif 'qid' in scope:
        targets = by_qid.get(scope['qid'], [])
    for row in targets:
        old = row.get(field, '')
        new = r.get('value', '')
        if old != new:
            changelog.append({'unit_id': row['unit_id'], 'field': field, 'old': old, 'new': new,
                              'reason': r.get('reason', ''), 'ruler': r.get('ruler', ''), 'ts': r.get('ts', '')})
        row[field] = new

if 'ruled' not in fieldnames:
    fieldnames.append('ruled')
for row in attr_rows:
    row['ruled'] = 'yes' if rulings_all else 'no'

with open(SALV + 'attribution_ruled_v4.csv', 'w', encoding='utf-8-sig', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(attr_rows)
json.dump({'changes': changelog}, open(SALV + 'attribution_ruled_v4.changelog.json', 'w'),
           ensure_ascii=False, indent=1)
print('attribution_ruled_v4.csv written; changelog entries:', len(changelog))

# ---- persist merge state for list-building step ----
dump = {}
for uid, info in final.items():
    dump[uid] = {'j': info['j'], 'judge': info['judge'], 'batch': info['batch'], 'kind': src_kind[uid]}
json.dump(dump, open(SALV + 'final_judgments.json', 'w'), ensure_ascii=False)
print('final_judgments.json written:', len(dump), 'units')
