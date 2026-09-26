#!/usr/bin/env python3
"""新卷入书总控清单——对“一批新卷 × 各本书”列出九步流程各自的完成状态，给出下一条该跑的命令。

背景：见 后勤管理/20260923_脚本化与跨书工具/书侧工具_20260924/新卷入书流水线_设计.md 的九步表。
本工具是流水线第 4 个新工具（exam_register.py/placement_suggest.py/block_insert.py 之后），
只读，不做任何题库/书稿写入，也不代替任何一步做判断——只去看那一步该有的真实产物在不在、说了
什么，汇总成状态表，并给出下一条命令的完整命令行。判定优先级：真实产物 > 猜测；找不到真实产物
就如实报 TODO/NEEDS_MODEL/NEEDS_LOCAL，不假装知道。

九步与状态判据（模型只在第 4/6/7 步出手，见设计稿）
  1 source_intake  新文件差分：exam_id 已在题库 questions/<id>/ 下 → DONE（历史卷，非本次新文件，
    差分环节的意义已经过去）；--files 给的新原件，看 <workdir>/01_source_intake/*.json 里是否已有
    覆盖这些文件路径的报告。
  2 exam_register  登记卷身份：看 <workdir>/02_exam_register/<exam_id或claimed_id>.json（本工具
    自己不跑 exam_register.py，只读它写好的报告）。report.items[0].duplicates 里出现
    kind=='duplicate_registration'，或 summary.cohort_status=='CONFLICT'，或 has_id_mismatch → BLOCKED；
    cohort_status=='NEEDS_LOCAL' → NEEDS_LOCAL；issue_count>0（弱证据/建议号被占用等）→ TODO；
    否则 → DONE。
  3 doc2md/bank_compile  逐题 MD 与题库验收门：题库 questions/<exam_id>/ 存在、有逐题 MD、且
    shared_conversion_state.json 的 accepted==true → DONE；否则 TODO（给出 bank_compile.py
    check --exam 命令核实门禁细节，本工具不复述 G1-G11 的判断）。
  4 模块归属判定（模型）：查 归属表_v1/attribution_ruled.csv 的 归属_<书代码> 列（见 ATTR_CODE）。
    该卷完全不在表里 → NEEDS_MODEL（需走归属表流水线：切片→模型判定→并入 rulings.jsonl）；
    有行但该列有空值 → NEEDS_MODEL（部分题未判）；全部非空 → DONE。
  5 该收清单 + placement_suggest：归属_<码>=='IN' 的题里，先按 (canonical_qid, subq) 归并孪生/别名行
    （见下“孪生归并”），再按 admission/各书清单_v4 类别过滤准入（见下“准入过滤”），过滤后仍为空 → DONE
    （无需落位建议，若有 admission=待裁决 的行报 NEEDS_MODEL）；非空则看
    <workdir>/05_placement/<book>/<exam_id>.json 是否覆盖了这些题键（report.summary.by_query 的
    source 字段）。
  6 教学内容改动单（模型，qpack 取材）：产物是 baodian_insert_v1 插入单（与 block_insert.py 的输入
    同一份东西——“改动单”写完、经批准，就是插入单）。看 <workdir>/06_insert/<book>/<exam_id>.json，
    schema 对、approved_by 非空、parent_docx_sha256 等于当前稿真实 SHA、inserts 覆盖该收清单 → DONE。
  7 题肢（模型）：只对该收题里的选择题（同样先过准入过滤）。产物复用已有的 check_drill_admission.py
    验证结果（候选/裁决/报告三元组，见该脚本文件头），看 <workdir>/07_drill/<book>/<exam_id>.json 的
    status=='pass'。
  8 block_insert 插入整道题：该书该卷 归属_<码> 在 ('IN','COLLECTED') 的题（孪生归并、准入过滤后，
    COLLECTED＝已经通过孪生/别名题并入书中，不需要再插一次）用 block_index.select() 在该书当前稿里
    查——不管是不是本流程插入的，查得到题键就算 DONE（复用 block_index，不另写识别逻辑）。第4步未完成
    时本步也报 NEEDS_MODEL，不假装“应收题为空”。
  9 layout_prepare/batch_health/publish_review 预检：看 <workdir>/09_layout/<book>.json 与
    <候选构建根>/体检/<workdir名>/<book>.json（batch_health 输出守卫只放行 …/构建/体检/，见
    _health_report_dir）与 <workdir>/09_publish/<book>.json 是否都已产出且 layout 报告 pending==0、
    blocked_count 全 0、toc_version_problems 为空。云端默认只到这一步——定稿渲染、页码与最终发布按
    CLAUDE.md 一律回本地做，最高只报 NEEDS_LOCAL；本地传 --local-final 且额外证据（同版身份记录、
    publish_review --apply 回执）齐全才可能报 DONE，云端不接受这个参数报 DONE（见 check_step9）。

  孪生归并（M1）：归属表 README v3/v4 规定按 (canonical_qid, subq) 去重——BJ-2024/2025-HD-QIZHONG
    这类重复登记别名卷，两侧行指向同一道真实的题。merge_twin_rows() 把同组行合成一条，unit_id 统一换
    成 canonical 形式（block_index 认的就是这个），每个 归属_<码> 列取组内最“确定”的结论
    （COLLECTED > IN > MAYBE > OUT——任一侧已在书里就算在书里）。
  准入过滤（M4）：“该收”只算 admission 不以“不收”“身份”开头、且不是“待裁决”的 IN 行；有
    各书清单_v4/<码>_漏收候选.csv 时以它的“类别”为准（漏收＝收，其余＝按 admission 兜底的语义处理），
    在 evidence 里写明依据（collectable_rows()）。“待裁决”/有争议的行只列 NEEDS_MODEL/CANDIDATE，不
    当“该收”也不当“不收”。

状态词：DONE / TODO / BLOCKED(reason) / SKIP(reason) / NEEDS_MODEL / NEEDS_LOCAL。
  bixiu2 全流程 SKIP（冻结、不在云端），不加载配置、不读该书任何真实产物。

用法
  intake_run.py init   --out 清单骨架.json [--batch 批次名] [--exam-id ID ...] [--book 书 ...]
                        [--workdir DIR]（不给则按 --out 所在 构建/ 目录下 入书_<批次>/ 推算）
      生成一份 baodian_intake_v1 清单骨架（可编辑后交 status 用），并 mkdir -p 出 workdir 下
      01_source_intake/02_exam_register/03_bank_compile/09_layout/09_publish 及按 --book 逐本建的
      05_placement/06_insert/07_drill/<书>/（M6：guard_write 要求父目录已存在，建到 <书> 这层才够）。
      09_health 不在 workdir 下建——batch_health 的输出守卫只放行 …/构建/体检/，见
      _health_report_dir()。只读题库/书稿；--out 与 workdir 都受 guard_write 同款守卫（见
      _extra_guard_check/_check_workdir_allowed）。
  intake_run.py status --manifest 清单.json [--report x.json] [--md x.md] [--quiet]
                        [--bank DIR] [--attribution-csv CSV] [--local-final] [--debug]
      对清单里 exams × books 的每个组合跑九步判定，终端打印精简表；--report 给完整 JSON（tool/
      version/mode/inputs/summary/rows，每行 9 步逐条 reason/evidence/next_command）；--md 给模型
      读的 Markdown 清单（每格只写状态与下一条命令，不夹判断）；--report/--md 允许覆盖自己以前写的
      同名报告（status 本来就要反复重跑），别的文件不行（_status_overwrite_ok，m3）。--bank/
      --attribution-csv 缺省按已加载 profile 的 paths.root/sources.bank.root 推（M3）。--local-final
      仅本地：第9步在证据齐全外再核 publish 是否真 --apply 且 gates_pass，齐了才报 DONE（云端不给，
      最高 NEEDS_LOCAL，见 check_step9）。

清单格式（baodian_intake_v1）
  {"schema": "baodian_intake_v1", "batch": "…",
   "exams": [{"exam_id": "BJ-2026-HD-QIZHONG"} 或 {"files": ["原卷.pdf", ...], "claimed_id": "…"}],
   "books": ["bixiu3", "philosophy", "culture", "xuanbi1", "xuanbi2", "mind", "reasoning", "bixiu2"],
   "profiles": {"bixiu3": "配置路径", …}（除 bixiu2 外每本书必须给）,
   "workdir": "…/构建/入书_<批次>/"}

只读承诺：不改题库、书稿、协作登记、Skill、归属表；不运行 collab.py；不调用任何写模式的子命令
  （不 apply、不 --out 改书稿）；唯一写出是本工具自己的 --report/--md 与 init 的清单骨架/目录骨架，
  一律过 guard_write 同款守卫（只许系统临时目录或 …/协作/候选/<谁>/<批次>/构建/ 之下）。

退出码：0 成功且全部 DONE/SKIP；1 存在待处理（TODO/BLOCKED/NEEDS_MODEL/NEEDS_LOCAL 任一）；
  2 输入/清单/配置错误；3 拒绝写出（守卫）。异常一律中文提示，不打印 traceback（--debug 打开）。
"""
import sys

sys.dont_write_bytecode = True  # 不在 Skill 母版 scripts/ 里留下 __pycache__（硬规则 1）

import argparse
import csv
import json
import os
import re
import traceback
from collections import Counter, OrderedDict
from datetime import datetime, timezone
from pathlib import Path

TOOL = 'intake_run'
VERSION = '1.0.0'


# ---------------------------------------------------------------- 定位 Skill 脚本目录（硬规则 1）
def _find_skill_dir():
    here = Path(__file__).resolve().parent
    if (here / 'docx_lib.py').is_file():
        return here
    env = os.environ.get('BAODIAN_SKILL_SCRIPTS')
    if env and (Path(env) / 'docx_lib.py').is_file():
        return Path(env).resolve()
    p = here
    for _ in range(12):
        cand = p / '.claude' / 'skills' / 'beijing-gaokao-politics' / 'scripts'
        if (cand / 'docx_lib.py').is_file():
            return cand
        if p.parent == p:
            break
        p = p.parent
    raise SystemExit(
        '找不到 Skill 脚本目录（docx_lib.py）：本文件同目录、环境变量 BAODIAN_SKILL_SCRIPTS、'
        '向上逐级 .claude/skills/beijing-gaokao-politics/scripts 均未找到')


SK_DIR = _find_skill_dir()
THIS_DIR = Path(__file__).resolve().parent  # exam_register/placement_suggest/block_insert 的所在目录：
# 装进 Skill 前四个新工具一起放在候选目录，装进 Skill 后一起放在 SK_DIR——两种情况下都是本文件的
# 同目录，用它定位这三个“新流水线”同伴工具，不假定它们已经在 SK_DIR（见文件头“只读承诺”前一节）。
sys.path.insert(0, str(SK_DIR))
try:  # 环境缺依赖（如 lxml/python-docx）时给中文提示、退出 2，不打印英文 traceback
    import docx_lib as dl  # noqa: E402
    import block_index as bidx  # noqa: E402  （build_index/select，不另写题键识别逻辑）
    from profile_lib import load_profile  # noqa: E402
except Exception as _sk_import_err:
    print(f'Skill 依赖模块加载失败（环境缺少依赖，如 lxml/python-docx 等）：{_sk_import_err}', file=sys.stderr)
    if '--debug' in sys.argv:
        traceback.print_exc()
    sys.exit(2)


def _repo_root_from_sk(sk_dir):
    """只作最后兜底：装进任意位置的 Skill 母版后这条链可能猜错（M3），真正的题库/归属表默认根一律
    优先取已加载 profile 的 paths.root/sources.bank.root（见 _default_bank_root/_default_attribution_
    csv），不依赖这里。"""
    for anc in [sk_dir] + list(sk_dir.parents):
        if anc.name == '.claude':
            return anc.parent
    return sk_dir.parents[3] if len(sk_dir.parents) >= 4 else sk_dir.parent


REPO_ROOT = _repo_root_from_sk(SK_DIR)
DEFAULT_BANK = REPO_ROOT / 'DeepSeek_政治题库资料库_20260918'
DEFAULT_ATTRIBUTION_CSV = (REPO_ROOT / '后勤管理' / '20260923_脚本化与跨书工具' / '完整性调查_20260924'
                            / '归属表_v1' / 'attribution_ruled.csv')

# 新流水线三个同伴工具（不在 SK 里，跟本文件同目录）；其余全部是 SK 里已有的脚本。
PEER_TOOLS = {'exam_register.py', 'placement_suggest.py', 'block_insert.py'}

# 与 exam_register.py 的 EXAM_ID_RX 同一模式（peer 候选工具，不是 SK 脚本；不 import 它，避免子进程
# 工具间产生 import 依赖，这里薄封装重声明一份，m7）。
EXAM_ID_RX = re.compile(r'^BJ-(?P<year>\d{4})-(?P<region>[A-Z]{2,4})-(?P<stage>YIMO|ERMO|QIMO|QIZHONG|GAOKAO)$')


def tool_path(name):
    return str((THIS_DIR if name in PEER_TOOLS else SK_DIR) / name)


def _profile_root(prof):
    try:
        return Path(prof['paths']['root']).expanduser()
    except Exception:
        return REPO_ROOT


def _default_bank_root(prof):
    """与 exam_register.py 的 _default_bank_raw 同口径：优先 profile 的 paths.root + sources.bank.root
    （M3：装进任意位置的 Skill 母版后仍能找对题库，不依赖 REPO_ROOT 从 SK_DIR 祖先猜测的那条链）。"""
    root = _profile_root(prof)
    rel = ((prof or {}).get('sources') or {}).get('bank', {}).get('root') if prof else None
    if rel:
        p = Path(rel).expanduser()
        return (p if p.is_absolute() else root / p).resolve()
    return (root / 'DeepSeek_政治题库资料库_20260918').resolve()


def _default_attribution_csv(prof):
    """归属表不是 profile 字段，仍按 profile 的 paths.root 推（M3 同一口径）；没有可用 profile 时退回
    REPO_ROOT。"""
    root = _profile_root(prof)
    return (root / '后勤管理' / '20260923_脚本化与跨书工具' / '完整性调查_20260924'
            / '归属表_v1' / 'attribution_ruled.csv').resolve()


# 书代码（归属表 归属_<码> 列）；bixiu2 一律 SKIP，不加载配置、不读该书任何真实产物。
ATTR_CODE = OrderedDict([
    ('bixiu3', 'B3'), ('philosophy', 'PH'), ('culture', 'CU'), ('xuanbi1', 'X1'),
    ('xuanbi2', 'X2'), ('mind', 'MI'), ('reasoning', 'RE'), ('bixiu2', 'B2'),
])
FROZEN_SKIP_BOOKS = {'bixiu2'}

STEP_NAMES = OrderedDict([
    (1, 'source_intake 新文件差分'), (2, 'exam_register 登记卷身份'),
    (3, 'doc2md/bank_compile 逐题MD与验收门'), (4, '模块归属判定'),
    (5, '该收清单+placement_suggest'), (6, '教学内容改动单'), (7, '题肢准入'),
    (8, 'block_insert 插入整道题'), (9, 'layout/health/publish 预检'),
])
PENDING = {'TODO', 'BLOCKED', 'NEEDS_MODEL', 'NEEDS_LOCAL'}


class InputError(Exception):
    pass


# ---------------------------------------------------------------- 基础工具
def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sr(step, status, reason, evidence=None, next_command=None):
    return OrderedDict([('step', step), ('name', STEP_NAMES[step]), ('status', status),
                        ('reason', reason), ('evidence', evidence or {}), ('next_command', next_command)])


def _read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def normalize_qid(q):
    """归属表 unit_id 的小问写法是 “…-Q17#1”，block_index/placement_suggest 认的是 “…-Q17(1)”。"""
    return re.sub(r'#(\d+)$', r'(\1)', q)


def exam_label(entry):
    if entry.get('exam_id'):
        return entry['exam_id']
    if entry.get('claimed_id'):
        return entry['claimed_id']
    files = entry.get('files') or []
    return 'FILES:' + (Path(files[0]).name if files else '?')


# ---------------------------------------------------------------- 清单加载与校验
def load_manifest(path):
    p = Path(path)
    if not p.is_file():
        raise InputError(f'清单文件不存在：{path}')
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
    except Exception as e:
        raise InputError(f'清单不是合法 JSON：{e}')
    if not isinstance(data, dict):
        raise InputError('清单顶层必须是 JSON 对象')
    if data.get('schema') != 'baodian_intake_v1':
        raise InputError(f'清单 schema 不是 baodian_intake_v1（实际：{data.get("schema")!r}）')
    for k in ('batch', 'exams', 'books', 'profiles', 'workdir'):
        if k not in data:
            raise InputError(f'清单缺字段：{k}')
    if not isinstance(data['exams'], list) or not data['exams']:
        raise InputError('exams 必须是非空数组')
    seen_labels = set()
    for i, e in enumerate(data['exams']):
        if not isinstance(e, dict) or not (e.get('exam_id') or e.get('files')):
            raise InputError(f'exams[{i}] 必须给 exam_id 或 files 之一')
        if e.get('exam_id') is not None:
            if not isinstance(e['exam_id'], str) or not e['exam_id'].strip():
                raise InputError(f'exams[{i}].exam_id 必须是非空字符串')
            if not EXAM_ID_RX.match(e['exam_id'].strip()):
                raise InputError(f'exams[{i}].exam_id 格式不对（应如 BJ-2026-HD-QIZHONG）：{e["exam_id"]!r}')
        if e.get('files') is not None and not isinstance(e['files'], list):
            raise InputError(f'exams[{i}].files 必须是数组')
        if e.get('claimed_id') is not None and (not isinstance(e['claimed_id'], str) or not e['claimed_id'].strip()):
            raise InputError(f'exams[{i}].claimed_id 必须是非空字符串')
        lbl = e.get('exam_id') or e.get('claimed_id')
        if lbl:
            if lbl in seen_labels:
                raise InputError(f'exams 里重复：{lbl!r}（m7：同一卷只列一次，避免状态表重复行）')
            seen_labels.add(lbl)
    if not isinstance(data['books'], list) or not data['books']:
        raise InputError('books 必须是非空数组')
    if len(data['books']) != len(set(data['books'])):
        raise InputError('books 有重复（m7）')
    for b in data['books']:
        if b not in ATTR_CODE:
            raise InputError(f'书名未知：{b!r}（已知书名：{", ".join(ATTR_CODE)}）')
    if not isinstance(data['profiles'], dict):
        raise InputError('profiles 必须是对象（书名 → 配置路径）')
    for b in data['books']:
        if b in FROZEN_SKIP_BOOKS:
            continue
        if not (data['profiles'].get(b) or '').strip() if isinstance(data['profiles'].get(b), str) else not data['profiles'].get(b):
            raise InputError(f'缺少 profiles.{b}（配置路径）')
    if not isinstance(data['workdir'], str) or not data['workdir'].strip():
        raise InputError('workdir 必须是非空字符串')
    return data


def load_book_profile(book, path_str):
    try:
        return load_profile(path_str)
    except InputError:
        raise
    except Exception as e:
        raise InputError(f'配置找不到或无法加载：profiles.{book}={path_str!r}（{type(e).__name__}: {e}）')


# ---------------------------------------------------------------- 归属表
def load_attribution(csv_path):
    """exam_id（raw 或 canonical） → 该卷全部行（dict，含 归属_<码> 各列与 type/unit_id）。"""
    p = Path(csv_path)
    if not p.is_file():
        return {}, None
    out = {}
    with p.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        # exam_id_raw 与 exam_id_canonical 常常同值（非别名卷）；用 set 去重，否则这类卷的每一行
        # 都会在同一个 exam_id 下被计入两次（IN/OUT/… 计数与 to_place 列表都会翻倍）。
        keys = {row.get('exam_id_raw'), row.get('exam_id_canonical')} - {None, ''}
        for k in keys:
            out.setdefault(k, []).append(row)
    return out, dl.sha256_file(p)


def attribution_rows_for(attr_by_exam, exam_id):
    return attr_by_exam.get(exam_id, []) if exam_id else []


# 归属_<码> 列取值按“已在书里/该收”的确定程度排序（M1：孪生任一侧更确定的结论生效）。
_STATUS_RANK = {'COLLECTED': 4, 'IN': 3, 'MAYBE': 2, 'OUT': 1}


def merge_twin_rows(rows):
    """M1：归属表 README v3/v4——重复登记别名卷（如 BJ-2024/2025-HD-QIZHONG）的题按 (canonical_qid,
    subq) 是同一道真实的题，需去重合并，否则第5/8步会把同一道题按两个 unit_id 各算一次，报出假的
    “尚未在书中”。同组行合成一条“虚拟行”：unit_id 换成 canonical 形式（canonical_qid 本身即不带
    小问的 qid；block_index 认的就是这个），每个 归属_<码> 列取组内最确定的结论
    （COLLECTED > IN > MAYBE > OUT——任一侧已在书里就算在书里）；admission/type 等非归属列取“本卷
    自身”（exam_id_raw==exam_id_canonical）那一行，没有就取组内第一行。返回 (merged_rows, alias_map)，
    alias_map 记录 别名 unit_id → canonical unit_id，供 evidence 说明（不是教学判断，只是同一等价类
    的记账口径）。"""
    groups = OrderedDict()
    for r in rows:
        cq = (r.get('canonical_qid') or '').strip() or r['unit_id']
        subq = (r.get('subq') or '').strip()
        groups.setdefault((cq, subq), []).append(r)
    merged, alias_map = [], {}
    for (cq, subq), grp in groups.items():
        canon_uid = cq + (('#' + subq) if subq else '')
        primary = next((r for r in grp if r.get('exam_id_raw') == r.get('exam_id_canonical')), grp[0])
        out = dict(primary)
        out['unit_id'] = canon_uid
        for code in ATTR_CODE.values():
            col = '归属_' + code
            vals = [(r.get(col) or '').strip() for r in grp]
            vals = [v for v in vals if v]
            out[col] = (max(vals, key=lambda v: _STATUS_RANK.get(v, 0)) if vals else '')
        merged.append(out)
        for r in grp:
            if r['unit_id'] != canon_uid:
                alias_map[r['unit_id']] = canon_uid
    return merged, alias_map


def load_book_lists_v4(attr_csv_path):
    """各书清单_v4/<码>_漏收候选.csv（与 attribution_ruled.csv 同目录）：unit_id → {'类别': ...} 的
    下游裁定，比归属表自己的 admission 列更精（M4）。文件不存在（某本书没有这份清单）时该书返回空
    字典，退回 admission 前缀判断，不当错误。"""
    base = Path(attr_csv_path).resolve().parent / '各书清单_v4'
    out = {}
    for code in ATTR_CODE.values():
        p = base / f'{code}_漏收候选.csv'
        d = {}
        if p.is_file():
            try:
                with p.open(encoding='utf-8-sig', newline='') as f:
                    for row in csv.DictReader(f):
                        if row.get('unit_id'):
                            d[row['unit_id']] = row
            except (OSError, csv.Error):
                d = {}
        out[code] = d
    return out


def _classify_admission(row, code, book_lists_v4):
    """M4：这道 归属_<码>=='IN' 的题是否真的“该收”。优先级：各书清单_v4 的“类别”（下游已用
    admission+人工复核产出的裁定）> 归属表自己的 admission 前缀。返回 ('collect'|'defer'|'exclude',
    basis 说明字符串)——不是教学判断，只是转述归属表/各书清单自己已经写好的结论。"""
    uid = row['unit_id']
    v4 = (book_lists_v4 or {}).get(code, {}).get(uid)
    admission = (row.get('admission') or '').strip()
    if v4 is not None:
        cat = (v4.get('类别') or '').strip()
        if cat == '漏收':
            return 'collect', f'各书清单_v4/{code}_漏收候选.csv 类别=漏收'
        if cat in ('待核证据',):
            return 'defer', f'各书清单_v4/{code}_漏收候选.csv 类别={cat}'
        return 'exclude', f'各书清单_v4/{code}_漏收候选.csv 类别={cat or "(空)"}'
    if admission.startswith('不收') or admission.startswith('身份'):
        return 'exclude', f'归属表 admission={admission or "(空)"}'
    if admission.startswith('待裁决'):
        return 'defer', f'归属表 admission={admission}'
    return 'collect', f'归属表 admission={admission or "(空)"}'


def collectable_rows(rows, code, book_lists_v4):
    """归属_<码>=='IN' 的行按 _classify_admission 分三类：collect（真正该收）/defer（待裁决，
    NEEDS_MODEL）/exclude（不收/身份错误，不列入）。返回三个 [{'unit_id','basis'}] 列表。"""
    collect, defer, exclude = [], [], []
    for r in rows:
        if (r.get('归属_' + code) or '').strip() != 'IN':
            continue
        verdict, basis = _classify_admission(r, code, book_lists_v4)
        item = {'unit_id': r['unit_id'], 'basis': basis}
        (collect if verdict == 'collect' else defer if verdict == 'defer' else exclude).append(item)
    return collect, defer, exclude


def qids_by_attr(rows, code, values):
    return [r['unit_id'] for r in rows if (r.get('归属_' + code) or '').strip() in values]


# ---------------------------------------------------------------- 当前稿定位（step8/9 用）
def current_docx_for_book(prof):
    paths = prof.get('paths') or {}
    cs_path = paths.get('central_state')
    if cs_path and Path(cs_path).is_file():
        try:
            cs = _read_json(cs_path)
            wh = cs.get('working_head')
            if wh:
                cand = Path(paths['root']) / paths.get('workspace', '') / Path(wh).name
                if cand.is_file():
                    return cand, None
                return None, f'central_state.working_head 指向的文件在仓库里找不到：{cand}'
        except Exception as e:
            return None, f'central_state 读取失败（{cs_path}）：{e}'
    ws = Path(paths.get('root', REPO_ROOT)) / (paths.get('workspace') or '')
    if not ws.is_dir():
        return None, f'workspace 目录不存在：{ws}'
    docxs = sorted(p for p in ws.glob('*.docx') if not p.name.startswith('~$'))
    if len(docxs) == 1:
        return docxs[0], None
    if not docxs:
        return None, f'{ws} 下没有 .docx，需本地确认当前工作稿'
    return None, f'{ws} 下有 {len(docxs)} 份 .docx，无法唯一确定当前稿（需本地指定）：{[d.name for d in docxs]}'


class BookIndexCache:
    """block_index.build_index() 按书只算一次（≈2~3秒/本），跨 exams 复用。"""

    def __init__(self):
        self._cache = {}

    def get(self, book, prof, docx_path):
        if book in self._cache:
            return self._cache[book]
        try:
            idx = bidx.build_index(str(docx_path), prof)
            self._cache[book] = (idx, None)
        except Exception as e:
            self._cache[book] = (None, f'block_index 解析失败：{type(e).__name__}: {e}')
        return self._cache[book]

    def has_key(self, book, prof, docx_path, qid):
        """返回 (hit, via, err)。via：'block'＝整道题的题块本身命中（真正的“已在书里”）；
        'drill'＝只在题肢单练附录命中（m2：单练条目不是整道题，第8步不该当 DONE 处理）；err 非空时
        hit/via 都是 None。"""
        idx, err = self.get(book, prof, docx_path)
        if idx is None:
            return None, None, err
        key = normalize_qid(qid)
        sel_b, _sel_d_ignored = bidx.select(idx, keys=[key], with_drill=False)
        if sel_b:
            return True, 'block', None
        _sel_b2, sel_d = bidx.select(idx, keys=[key])
        if sel_d:
            return True, 'drill', None
        return False, None, None


# ---------------------------------------------------------------- 9 个判定函数（1/2/3 与书无关；4-9 按书）
def check_step1(entry, bank_root, workdir):
    exam_id = entry.get('exam_id')
    if exam_id:
        qdir = bank_root / 'questions' / exam_id
        if qdir.is_dir():
            return sr(1, 'DONE', f'{exam_id} 已在题库 questions/ 下（历史卷，非本次新文件差分对象）',
                      {'bank_dir': str(qdir)})
        cmd = (f'python3 {tool_path("source_intake.py")} <原卷/细则原件路径...> '
               f'--cache {workdir}/01_source_intake/cache --report {workdir}/01_source_intake/{exam_id}.json')
        return sr(1, 'TODO', f'题库尚无 questions/{exam_id}/，需先跑 source_intake 差分新原件', {}, cmd)
    files = entry.get('files') or []
    label = exam_label(entry)
    reports_dir = workdir / '01_source_intake'
    resolved = {str(Path(f).resolve()) for f in files}
    if reports_dir.is_dir():
        for rp in sorted(reports_dir.glob('*.json')):
            try:
                data = _read_json(rp)
            except Exception:
                continue
            seen = {x.get('path') for x in data.get('files', [])}
            if resolved and resolved <= seen:
                return sr(1, 'DONE', f'原件差分报告已覆盖全部给定文件：{rp.name}',
                          {'report': str(rp), 'counts': data.get('counts')})
    cmd = (f'python3 {tool_path("source_intake.py")} {" ".join(files)} '
           f'--cache {reports_dir}/cache --report {reports_dir}/{label.replace(":", "_")}.json')
    return sr(1, 'TODO', f'{label} 的新原件尚未跑 source_intake 差分（{len(files)} 个文件）', {'files': files}, cmd)


def check_step2(entry, ref_profile_path, workdir):
    exam_id = entry.get('exam_id')
    claimed = entry.get('claimed_id')
    key = exam_id or claimed
    if not key:
        return sr(2, 'BLOCKED', '既没有 exam_id 也没有 claimed_id，无法登记检查')
    rp = workdir / '02_exam_register' / f'{key}.json'
    prof_arg = f' --profile {ref_profile_path}' if ref_profile_path else ''
    if not rp.is_file():
        if exam_id:
            cmd = f'python3 {tool_path("exam_register.py")} check --exam-id {exam_id}{prof_arg} --report {rp}'
        elif entry.get('files'):
            cmd = (f'python3 {tool_path("exam_register.py")} check --files {" ".join(entry["files"])} '
                   f'--claimed-id {claimed}{prof_arg} --report {rp}')
        else:
            cmd = f'python3 {tool_path("exam_register.py")} check --exam-dir <逐题MD目录> --claimed-id {claimed}{prof_arg} --report {rp}'
        return sr(2, 'TODO', f'{key} 尚未跑登记检查', {}, cmd)
    try:
        data = _read_json(rp)
    except Exception as e:
        return sr(2, 'TODO', f'登记报告读取失败（重跑）：{e}', {}, f'python3 {tool_path("exam_register.py")} check --exam-id {exam_id or claimed}{prof_arg} --report {rp}')
    rerun_cmd = f'python3 {tool_path("exam_register.py")} check --exam-id {exam_id or claimed}{prof_arg} --report {rp}'
    result = (data.get('items') or [{}])[0]
    # m11：只按文件名 <key>.json 读第一条，不核这条结论是不是本卷、是不是 check 模式——报告放错位置
    # 或来自别的模式（如多卷 audit）时会把别的卷的结论当本卷用。
    if data.get('mode') != 'check':
        return sr(2, 'TODO', f'{rp} 不是 exam_register check 模式的报告（mode={data.get("mode")!r}），需重跑',
                  {'report': str(rp)}, rerun_cmd)
    result_key = result.get('exam_id') or result.get('claimed_id')
    if result_key != key:
        return sr(2, 'TODO', f'{rp} 记录的是 {result_key!r}，与本卷 {key!r} 不符，需重跑', {'report': str(rp)}, rerun_cmd)
    summary = data.get('summary') or {}
    dup_kinds = {d.get('kind') for d in result.get('duplicates', [])}
    # m8：files/claimed-id 模式没有现成 exam_id，第3步一直 BLOCKED；exam_register 报告里的
    # suggestion.suggested_id 就是它给这批新原件建议的卷号，第2步一旦有报告就可以把它转给第3步用。
    suggested = (result.get('suggestion') or {}).get('suggested_id')
    evidence = {'report': str(rp), 'summary': summary, 'duplicates': result.get('duplicates'),
                'suggested_exam_id': suggested}
    if 'duplicate_registration' in dup_kinds:
        others = [d['exam_id'] for d in result['duplicates'] if d['kind'] == 'duplicate_registration']
        return sr(2, 'BLOCKED', f'重复登记：与 {others} 判定为同一场考试', evidence)
    if summary.get('cohort_status') == 'CONFLICT' or result.get('id_mismatch'):
        return sr(2, 'BLOCKED', f'届别/卷号冲突：cohort_status={summary.get("cohort_status")}，'
                                 f'id_mismatch={result.get("id_mismatch")}', evidence)
    if summary.get('cohort_status') == 'NEEDS_LOCAL':
        return sr(2, 'NEEDS_LOCAL', '届别证据不足（无文字层/无卷首证据），需本地看原件', evidence)
    if summary.get('issue_count'):
        return sr(2, 'TODO', f'仍有 {summary["issue_count"]} 条待处理（见报告 issues，如弱证据/建议号占用）', evidence)
    return sr(2, 'DONE', f'登记检查通过：cohort_status={summary.get("cohort_status")}，无重复/冲突/待处理', evidence)


def check_step3(entry, bank_root, exam_id_hint=None):
    exam_id = entry.get('exam_id') or exam_id_hint
    if not exam_id:
        return sr(3, 'BLOCKED', 'exam_id 尚未确定（第2步给出建议卷号后可用，见第2步 evidence.suggested_'
                  'exam_id；files/claimed-id 模式需先完成登记检查）')
    qdir = bank_root / 'questions' / exam_id
    cmd = f'python3 {tool_path("bank_compile.py")} check --exam {exam_id} --json'
    if not qdir.is_dir():
        return sr(3, 'TODO', f'题库尚无 questions/{exam_id}/（先完成第1步转写）', {}, cmd)
    md_files = [p for p in qdir.glob('*.md') if p.name.upper() != 'README.MD']
    state_path = qdir / 'shared_conversion_state.json'
    evidence = {'bank_dir': str(qdir), 'md_count': len(md_files)}
    if not md_files:
        return sr(3, 'TODO', f'{qdir} 下没有逐题 MD', evidence, cmd)
    if not state_path.is_file():
        return sr(3, 'TODO', f'逐题MD {len(md_files)} 份，但缺 shared_conversion_state.json（转换状态未知）', evidence, cmd)
    try:
        st = _read_json(state_path)
    except Exception as e:
        return sr(3, 'TODO', f'shared_conversion_state.json 读取失败：{e}', evidence, cmd)
    evidence['status'] = st.get('status')
    evidence['accepted'] = bool(st.get('accepted'))
    if not st.get('accepted'):
        return sr(3, 'TODO', f'shared_conversion_state.status={st.get("status")!r}，尚未 accepted', evidence, cmd)
    return sr(3, 'DONE', f'逐题MD {len(md_files)} 份，shared_conversion_state 已 accepted（status={st.get("status")}）', evidence)


def check_step4(exam_id, code, rows, alias_map=None):
    if not exam_id:
        return sr(4, 'BLOCKED', 'exam_id 尚未确定，无法查归属表')
    if not rows:
        return sr(4, 'NEEDS_MODEL', f'{exam_id} 未出现在归属表（attribution_ruled.csv），'
                                     f'需先走归属表流水线（新题切片 → 模型判定 → 并入 rulings.jsonl）')
    col = '归属_' + code
    # m1（部分修复）：admission 自己写明“身份错误/未确认-不计入分母”的行，归属表口径本就不算进分母；
    # 只有这些行没有别的信息，从 missing 判据里剔除，不再让它们把第4步拖成 NEEDS_MODEL 或反过来悄悄
    # 算进 DONE 的计数。rulings.jsonl 里模型显式“暂缓(证据不足)”的格子未接入（另需读取归属表工作区
    # 之外的原始 rulings 记录，本轮未做，见回执 known_limits）。
    identity_excluded = [r['unit_id'] for r in rows if (r.get('admission') or '').startswith('身份')]
    judged_rows = [r for r in rows if r['unit_id'] not in set(identity_excluded)]
    missing = [r['unit_id'] for r in judged_rows if not (r.get(col) or '').strip()]
    counts = dict(Counter((r.get(col) or '').strip() or '(空)' for r in judged_rows))
    evidence = {'counts': counts}
    if identity_excluded:
        evidence['identity_excluded'] = identity_excluded
    if alias_map:
        evidence['alias_to_canonical'] = alias_map
    if missing:
        evidence['missing'] = missing
        return sr(4, 'NEEDS_MODEL', f'{len(missing)}/{len(judged_rows)} 题在 {col} 列未判定：{missing[:6]}', evidence)
    return sr(4, 'DONE', f'{len(judged_rows)} 题归属已全部判定：{counts}'
              + (f'（另 {len(identity_excluded)} 题身份错误/未确认，不计入分母）' if identity_excluded else ''),
              evidence)


def check_step5(exam_id, book, code, rows, step4_status, workdir, book_profile_path, docx_path, book_lists_v4):
    if step4_status != 'DONE':
        return sr(5, 'NEEDS_MODEL', '归属判定未完成，无法定“该收清单”（见第4步）')
    collect, defer, exclude = collectable_rows(rows, code, book_lists_v4)
    to_place = [x['unit_id'] for x in collect]
    ev0 = {}
    if defer:
        ev0['deferred'] = defer
    if exclude:
        ev0['excluded'] = exclude
    if not to_place:
        if defer:
            return sr(5, 'NEEDS_MODEL', f'{len(defer)} 道 IN 题准入待裁决（admission=待裁决/各书清单_v4'
                       f'=待核证据），本工具不做教学判断：{[d["unit_id"] for d in defer][:6]}', ev0)
        return sr(5, 'DONE', '本卷本书没有确定该收的新增题（IN 为空，或全部被准入过滤排除），无需插入位置建议', ev0)
    rp = workdir / '05_placement' / book / f'{exam_id}.json'

    def _cmd(qids):
        docx_s = str(docx_path) if docx_path else '<当前工作稿.docx>'
        keys = ' '.join(f'--key {q}' for q in qids)
        return (f'python3 {tool_path("placement_suggest.py")} --docx {docx_s} --profile {book_profile_path} '
                f'{keys} --top-k 3 --report {rp}')
    if not rp.is_file():
        return sr(5, 'TODO', f'{len(to_place)} 道 IN 题尚无插入位置建议：{to_place[:6]}',
                  dict(ev0, to_place=to_place), _cmd(to_place))
    try:
        data = _read_json(rp)
    except Exception as e:
        return sr(5, 'TODO', f'placement 报告读取失败：{e}', ev0, _cmd(to_place))
    covered = {q.get('source') for q in ((data.get('summary') or {}).get('by_query') or [])}
    missing = [q for q in to_place if q not in covered]
    if missing:
        return sr(5, 'TODO', f'报告缺 {len(missing)}/{len(to_place)} 题：{missing[:6]}',
                  dict(ev0, covered=sorted(covered), missing=missing), _cmd(missing))
    flagged = [q.get('source') for q in data['summary']['by_query'] if q.get('has_flags')]
    reason = f'{len(to_place)} 题均已给出插入位置建议'
    if flagged:
        reason += f'；{len(flagged)} 题带 flags 待主代理裁定（{flagged[:4]}）'
    return sr(5, 'DONE', reason, dict(ev0, flagged=flagged, report=str(rp)))


def check_step6(exam_id, book, code, rows, step4_status, workdir, docx_sha256, book_lists_v4, book_profile_path):
    if step4_status != 'DONE':
        return sr(6, 'NEEDS_MODEL', '归属判定未完成，无法起草教学内容改动单')
    collect, defer, _exclude = collectable_rows(rows, code, book_lists_v4)
    to_place = [x['unit_id'] for x in collect]
    if not to_place:
        return sr(6, 'DONE' if not defer else 'NEEDS_MODEL',
                  '本卷本书无需新增教学内容' if not defer else f'{len(defer)} 道 IN 题准入待裁决，暂不起草改动单')
    rp = workdir / '06_insert' / book / f'{exam_id}.json'
    # m10：qpack.py get 是接受 --profile 的（--bank 才是顶层参数，get 子命令本身不收）；带上 profile
    # 让“限定某册的裁定”生效，命令更完整。
    prof_arg6 = f' --profile {book_profile_path}' if book_profile_path else ''
    get_cmds = '；'.join(f'python3 {tool_path("qpack.py")} get {q} --layers e1,stem{prof_arg6} --json' for q in to_place[:3])
    cmd = get_cmds + (' 等（先取材，模型据此起草 baodian_insert_v1 插入单/改动单，approved_by 后落 '
                      f'{rp}）')
    if not rp.is_file():
        return sr(6, 'NEEDS_MODEL', f'{len(to_place)} 题尚无教学内容改动单：{to_place[:6]}', {'to_place': to_place}, cmd)
    try:
        data = _read_json(rp)
    except Exception as e:
        return sr(6, 'NEEDS_MODEL', f'改动单不是合法 JSON：{e}', {}, cmd)
    if data.get('schema') != 'baodian_insert_v1':
        return sr(6, 'NEEDS_MODEL', f'schema 不是 baodian_insert_v1（实际：{data.get("schema")!r}）', {}, cmd)
    approved = (data.get('approved_by') or '').strip()
    if not approved:
        return sr(6, 'NEEDS_MODEL', '改动单已起草但 approved_by 为空（未获批准）', {'report': str(rp)}, cmd)
    # m4：DONE 前再核两条最容易被合成/过期插入单蒙混过去的事——父稿 SHA 是否等于当前稿真实 SHA、
    # inserts 是否覆盖了该收清单（哪怕两者都齐，最终仍要 block_insert 自己 check/apply 才算数，这里
    # 只挡“明显不对”的插入单，不代替它）。
    parent_sha = (data.get('parent_docx_sha256') or '').strip().lower()
    if docx_sha256 and parent_sha and parent_sha != docx_sha256.lower():
        return sr(6, 'NEEDS_MODEL', f'改动单 parent_docx_sha256 与当前稿真实 SHA 不符（{parent_sha[:12]}…'
                  f' != {docx_sha256[:12]}…），需重新起草或核对当前稿', {'report': str(rp)}, cmd)
    n_inserts = len(data.get('inserts') or [])
    if n_inserts < len(to_place):
        # 插入单没有 qid 字段可比对（baodian_insert_v1 按 anchor/template_block 定位，不按题库题键），
        # 只能做条数这一层粗核：条数不够，覆盖不全是确定的；条数够不等于确定覆盖对了，block_insert
        # 自己 check/apply 才是准的（本步不代替它）。
        return sr(6, 'NEEDS_MODEL', f'改动单只有 {n_inserts} 条 insert，少于该收清单 {len(to_place)} 题，'
                  '覆盖不全', {'report': str(rp), 'to_place': to_place}, cmd)
    return sr(6, 'DONE', f'改动单已起草并批准（approved_by={approved}，{n_inserts} 条 insert ≥ '
              f'{len(to_place)} 题该收清单）', {'report': str(rp), 'approved_by': approved})


def check_step7(exam_id, book, code, rows, step4_status, workdir, book_lists_v4):
    if step4_status != 'DONE':
        return sr(7, 'NEEDS_MODEL', '归属判定未完成，无法定题肢准入范围')
    collect, _defer, _exclude = collectable_rows(rows, code, book_lists_v4)
    to_place_choice = [x['unit_id'] for x in collect
                        if any(r['unit_id'] == x['unit_id'] and '选择' in (r.get('type') or '') for r in rows)]
    if not to_place_choice:
        return sr(7, 'DONE', '本卷本书没有新增选择题，无需题肢准入裁决')
    d = workdir / '07_drill' / book
    rp, cand, dec = d / f'{exam_id}.json', d / f'{exam_id}_candidates.json', d / f'{exam_id}_decisions.json'
    cmd = f'python3 {tool_path("check_drill_admission.py")} --candidates {cand} --decisions {dec} --report {rp}'
    if not rp.is_file():
        return sr(7, 'NEEDS_MODEL', f'{len(to_place_choice)} 道选择题尚无题肢准入裁决：{to_place_choice[:6]}',
                  {'to_place_choice': to_place_choice}, cmd)
    try:
        data = _read_json(rp)
    except Exception as e:
        return sr(7, 'NEEDS_MODEL', f'准入报告不是合法 JSON：{e}', {}, cmd)
    if data.get('status') != 'pass':
        return sr(7, 'NEEDS_MODEL', f'准入报告 status={data.get("status")!r}，未通过', {'report': str(rp)}, cmd)
    return sr(7, 'DONE', f'题肢准入裁决通过（retained={data.get("retained_count")}，excluded={data.get("excluded_count")}）',
              {'report': str(rp)})


def check_step8(exam_id, book, code, rows, step4_status, index_cache, prof, docx_path, docx_err,
                step6_evidence, book_profile_path, book_lists_v4):
    if step4_status != 'DONE':
        return sr(8, 'NEEDS_MODEL', '归属判定未完成，无法确定应收题范围（见第4步）——M2：不假装“应收题为空”')
    collect, _defer, _exclude = collectable_rows(rows, code, book_lists_v4)
    target = sorted({x['unit_id'] for x in collect} | set(qids_by_attr(rows, code, {'COLLECTED'})))
    if not target:
        return sr(8, 'DONE', '本卷本书应收题为空（准入过滤后 IN 为空，且没有 COLLECTED 题）')
    if docx_path is None:
        return sr(8, 'NEEDS_LOCAL', f'{book} 当前稿路径未能确定：{docx_err}')
    missing, found, drill_only, errs = [], [], [], []
    for q in target:
        hit, via, err = index_cache.has_key(book, prof, docx_path, q)
        if err:
            errs.append(err)
            break
        if hit and via == 'block':
            found.append(q)
        elif hit and via == 'drill':
            drill_only.append(q)  # m2：只在题肢单练附录命中，例题题块本身没插，不算“整题已在书里”
        else:
            missing.append(q)
    if errs:
        return sr(8, 'NEEDS_LOCAL', errs[0])
    insert_json = (step6_evidence or {}).get('report') or '<06_insert改动单路径.json>'
    prof_arg = book_profile_path or book
    if missing or drill_only:
        need = missing + drill_only
        # 占位符不能含空格——它要落进一条会被当 shell 命令行解析的字符串，含空格会被切成两个 token
        cmd = f'python3 {tool_path("block_insert.py")} check --docx {docx_path} --insert {insert_json} --profile {prof_arg}'
        reason = f'{len(missing)}/{len(target)} 应收题尚未在 {book} 当前稿中：{missing[:6]}'
        if drill_only:
            reason += f'；另 {len(drill_only)} 题只在题肢单练附录命中，例题题块本身未插：{drill_only[:6]}'
        return sr(8, 'TODO', reason,
                  {'missing': missing, 'drill_only': drill_only, 'found': found, 'docx': str(docx_path),
                   'need_insert': need}, cmd)
    return sr(8, 'DONE', f'{len(target)} 道应收题（IN/COLLECTED，孪生归并+准入过滤后）均已在 {book} 当前稿中'
              '题块本身命中（block_index 核对，不含仅题肢单练命中）', {'docx': str(docx_path), 'found': found})


def _health_report_dir(workdir):
    """batch_health 的输出守卫只放行 …/协作/候选/<谁>/<批次>/构建/体检/ 之下（M6：_house.json
    output_guard.allowed_subpath_regex 比 docx_lib.guard_write 的通用“构建(/|$)”更窄）；health 报告
    不能留在 workdir 自己的 09_health/ 里，改放到同一候选批次“构建”目录下的 体检/ 子目录，workdir
    目录名作最后一层区分多个批次/沙盒。不在候选目录下（如系统临时目录）时退回 workdir 自己的子目录，
    仍在临时目录内可写。"""
    o = Path(workdir).resolve()
    m = re.search(r'^(.*/协作/候选/[^/]+/[^/]+/构建)(?=/|$)', str(o))
    if m:
        return Path(m.group(1)) / '体检' / o.name
    return o / '09_health'


def check_step9(book, prof, docx_path, docx_err, workdir, local_final=False):
    if docx_path is None:
        return sr(9, 'NEEDS_LOCAL', f'{book} 当前稿路径未能确定：{docx_err}')
    layout_rp = workdir / '09_layout' / f'{book}.json'
    health_rp = _health_report_dir(workdir) / f'{book}.json'
    publish_rp = workdir / '09_publish' / f'{book}.json'
    prof_arg = prof.get('_profile_path') or book
    if not layout_rp.is_file():
        cmd = f'python3 {tool_path("layout_prepare.py")} check --docx {docx_path} --profile {prof_arg} --report {layout_rp}'
        return sr(9, 'TODO', '尚未跑 layout_prepare check（编号/考法题数/keepNext/目录）', {}, cmd)
    try:
        ld = _read_json(layout_rp)
    except Exception as e:
        cmd = f'python3 {tool_path("layout_prepare.py")} check --docx {docx_path} --profile {prof_arg} --report {layout_rp}'
        return sr(9, 'TODO', f'layout 报告读取失败：{e}', {}, cmd)
    pending = ld.get('pending') or 0
    blocked = sum((ld.get('blocked_count') or {}).values())
    tocv = len(ld.get('toc_version_problems') or [])
    if pending or blocked or tocv:
        cmd = (f'python3 {tool_path("layout_prepare.py")} repair --docx {docx_path} --out <候选.docx> '
               f'--numbering --method-counts --keepnext --profile {prof_arg} --report <r.json>')
        return sr(9, 'TODO', f'layout_prepare 待改 pending={pending}，blocked={blocked}，toc_version_problems={tocv}',
                  {'layout_report': str(layout_rp)}, cmd)
    if not health_rp.is_file():
        cmd = f'python3 {tool_path("batch_health.py")} --docx {docx_path} --profile {prof_arg} --out {health_rp}'
        return sr(9, 'TODO', 'layout 已 0 待改，尚未跑 batch_health 体检', {}, cmd)
    if not publish_rp.is_file():
        cmd = (f'python3 {tool_path("publish_review.py")} --profile {prof_arg} --batch <批次号> --docx {docx_path} '
               f'--pdf <候选PDF> --acceptance <验收.json> --actor <actor> --report {publish_rp}')
        return sr(9, 'TODO', 'layout/health 已具备，尚未跑 publish_review dry-run 预检', {}, cmd)
    evidence = {'layout_report': str(layout_rp), 'health_report': str(health_rp), 'publish_report': str(publish_rp)}
    if not local_final:
        return sr(9, 'NEEDS_LOCAL',
                  '云端证据（layout 0 待改 + health + publish dry-run 报告）齐全；'
                  '定稿渲染、页码与最终发布一律回本地做（CLAUDE.md：云端字体与本机不同，只作粗查）', evidence,
                  '回本地：render_book.py 渲染定稿 PDF → page_delta.py 只看改动页 → 人工审阅 → publish_review.py --apply')
    # --local-final（m5）：这一分支只在本地、显式传 --local-final 时才会走到；云端从不传这个开关。
    # 不重新发明同版身份/page_delta 的文件路径约定（那样会伪造一份本工具自己也没验证过的契约）——
    # 直接信 publish_review.py 自己的门（它自己就有 same_version_identity 等门，'gates_pass' 是它算好
    # 的总闸）：报告必须是一次真正的 --apply（不是 dry-run）且 gates_pass 为真，才报 DONE；哪个查不到
    # 都仍报 NEEDS_LOCAL，不假装本地也齐了（“不伪造：需要看图/看原页才能定的，标需本地”）。
    try:
        pd = _read_json(publish_rp)
    except Exception as e:
        return sr(9, 'NEEDS_LOCAL', f'--local-final 但 publish 报告读取失败：{e}', evidence)
    if pd.get('mode') != 'apply':
        return sr(9, 'NEEDS_LOCAL', f'publish 报告 mode={pd.get("mode")!r}，不是 --apply（未真正发布），'
                  '--local-final 也不能报 DONE', evidence)
    if not pd.get('gates_pass'):
        fail_ids = [g.get('id') for g in (pd.get('gates') or []) if g.get('level') == 'FAIL']
        return sr(9, 'NEEDS_LOCAL', f'publish 报告 gates_pass 不为真（FAIL 门：{fail_ids}），'
                  '--local-final 也不能报 DONE', evidence)
    return sr(9, 'DONE', '本地：layout/health 齐全，publish_review 已 --apply 且 gates_pass（含它自己的'
              'same_version_identity 等门），--local-final 下报 DONE', evidence)


# ---------------------------------------------------------------- 编排
def _docx_sha(cache, docx_path):
    if docx_path is None:
        return None
    key = str(docx_path)
    if key not in cache:
        cache[key] = dl.sha256_file(docx_path)
    return cache[key]


def compute_row(entry, book, prof, attr_by_exam, index_cache, workdir, bank_root, ref_profile_path,
                 book_profile_path, book_lists_v4, docx_sha_cache, local_final):
    exam_id = entry.get('exam_id')
    label = exam_label(entry)
    if book in FROZEN_SKIP_BOOKS:
        steps = [sr(i, 'SKIP', '必修二已送印冻结，且不在云端仓库，本流程不处理') for i in range(1, 10)]
        return {'exam': label, 'book': book, 'steps': steps, 'next_action': None}

    s1 = check_step1(entry, bank_root, workdir)
    s2 = check_step2(entry, ref_profile_path, workdir)
    s3 = check_step3(entry, bank_root, (s2.get('evidence') or {}).get('suggested_exam_id'))
    code = ATTR_CODE[book]
    raw_rows = attribution_rows_for(attr_by_exam, exam_id)
    rows, alias_map = merge_twin_rows(raw_rows)  # M1：孪生/别名先按 (canonical_qid, subq) 归并
    s4 = check_step4(exam_id, code, rows, alias_map)
    docx_path, docx_err = current_docx_for_book(prof) if prof else (None, '配置未加载')
    docx_sha256 = _docx_sha(docx_sha_cache, docx_path)
    s5 = check_step5(exam_id, book, code, rows, s4['status'], workdir, book_profile_path, docx_path, book_lists_v4)
    s6 = check_step6(exam_id, book, code, rows, s4['status'], workdir, docx_sha256, book_lists_v4, book_profile_path)
    s7 = check_step7(exam_id, book, code, rows, s4['status'], workdir, book_lists_v4)
    s8 = check_step8(exam_id, book, code, rows, s4['status'], index_cache, prof, docx_path, docx_err,
                      s6['evidence'], book_profile_path, book_lists_v4)
    s9 = check_step9(book, prof, docx_path, docx_err, workdir, local_final) if prof else \
        sr(9, 'NEEDS_LOCAL', '配置未加载，无法预检')
    steps = [s1, s2, s3, s4, s5, s6, s7, s8, s9]
    next_action = next((s for s in steps if s['status'] in PENDING), None)
    return {'exam': label, 'book': book, 'steps': steps,
            'next_action': ({'step': next_action['step'], 'status': next_action['status'],
                             'reason': next_action['reason'], 'command': next_action['next_command']}
                            if next_action else None)}


def run_status(args):
    manifest = load_manifest(args.manifest)
    manifest_dir = Path(args.manifest).resolve().parent  # m7：相对 workdir 按清单目录解析，不按 CWD
    workdir = Path(args.workdir) if args.workdir else Path(manifest['workdir'])
    if not workdir.is_absolute():
        workdir = manifest_dir / workdir

    # M3：题库根/归属表默认值优先取已加载 profile 的 paths.root/sources.bank.root（与 exam_register.py
    # 同口径），不依赖 REPO_ROOT 从 SK_DIR 祖先猜测的那条链——装进任意位置的 Skill 母版后仍能找对。
    # 配置找不到/加载失败是清单层面的输入错误，不捕获，直接向 main() 传播成整批中止（约定4：任一
    # 校验失败→整批中止），退出码 2。
    profiles = {}
    for book in manifest['books']:
        if book in FROZEN_SKIP_BOOKS:
            continue
        profiles[book] = load_book_profile(book, manifest['profiles'][book])
    ref_profile_path = manifest['profiles'].get('bixiu3') or next(
        (v for k, v in manifest['profiles'].items() if k not in FROZEN_SKIP_BOOKS), None)
    ref_prof = profiles.get('bixiu3') or next(iter(profiles.values()), None)

    bank_root = Path(args.bank).resolve() if args.bank else _default_bank_root(ref_prof)
    attr_csv = Path(args.attribution_csv).resolve() if args.attribution_csv else _default_attribution_csv(ref_prof)
    if not bank_root.is_dir():
        raise InputError(f'题库根不存在：{bank_root}（M3：--bank 未给时按 profile 的 sources.bank.root 推，'
                          '路径不对时不再静默给出错误结论，直接中止）')
    if not attr_csv.is_file():
        raise InputError(f'归属表不存在：{attr_csv}（M3：--attribution-csv 未给时按 profile 的 paths.root '
                          '推，路径不对时不再静默给出错误结论，直接中止）')
    attr_by_exam, attr_sha = load_attribution(attr_csv)
    book_lists_v4 = load_book_lists_v4(attr_csv)  # M4：各书清单_v4，同目录

    index_cache = BookIndexCache()
    docx_sha_cache = {}
    rows = []
    for entry in manifest['exams']:
        for book in manifest['books']:
            prof = profiles.get(book)
            book_profile_path = prof.get('_profile_path') if prof else manifest['profiles'].get(book)
            rows.append(compute_row(entry, book, prof, attr_by_exam, index_cache, workdir, bank_root,
                                     ref_profile_path, book_profile_path, book_lists_v4, docx_sha_cache,
                                     args.local_final))

    books_info = OrderedDict()
    for b, p in profiles.items():
        dp, _err = current_docx_for_book(p)
        books_info[b] = {'docx': str(dp) if dp else None, 'docx_sha256': _docx_sha(docx_sha_cache, dp)}

    by_step_status = {i: Counter() for i in range(1, 10)}
    for r in rows:
        for s in r['steps']:
            by_step_status[s['step']][s['status']] += 1
    pending_rows = [r for r in rows if r['next_action'] is not None]

    if not args.quiet:
        for r in rows:
            abbr = ' '.join(f'{s["step"]}={s["status"]}' for s in r['steps'])
            na = (f'  next[{r["next_action"]["step"]}] {r["next_action"]["reason"]}'
                  if r['next_action'] else '  已全部 DONE/SKIP')
            print(f'{r["exam"]:24s} x {r["book"]:11s} {abbr}{na}')
        print(f'合计 {len(rows)} 组合，{len(pending_rows)} 组合仍有待处理。')

    rep = OrderedDict([
        ('tool', TOOL), ('version', VERSION), ('mode', 'status'), ('generated_at', now_iso()),
        ('inputs', OrderedDict([
            ('manifest', {'path': str(Path(args.manifest).resolve()), 'sha256': dl.sha256_file(args.manifest)}),
            ('attribution_csv', {'path': str(attr_csv), 'sha256': attr_sha}),
            ('bank_root', str(bank_root)), ('workdir', str(workdir)), ('local_final', bool(args.local_final)),
            ('profiles', {b: {'path': p.get('_profile_path'),
                              'sha256': dl.sha256_file(p['_profile_path']) if p.get('_profile_path') else None}
                         for b, p in profiles.items()}),
            ('books', books_info),  # m6：书稿 SHA 入 inputs，第8步结论依赖它
        ])),
        ('batch', manifest['batch']),
        ('summary', OrderedDict([
            ('exams', len(manifest['exams'])), ('books', len(manifest['books'])), ('combos', len(rows)),
            ('pending_combos', len(pending_rows)),
            ('by_step_status', {str(i): dict(c) for i, c in by_step_status.items()}),
        ])),
        ('rows', rows),
    ])

    # m3：先把两个输出都校验通过（guard_write 只算路径、不写盘），再落盘——任一校验失败都不留下另一个
    # 半成品（约定4）；status 是要反复重跑的工具自己的报告，允许覆盖自己以前写的同名旧报告，但不是
    # 随便什么已存在的文件都覆盖（_status_overwrite_ok）。
    report_out = dl.guard_write(Path(args.report), _house_guard_profile(), inputs=[args.manifest], kind='.json',
                                 overwrite=_status_overwrite_ok(args.report)) if args.report else None
    if report_out:
        _extra_guard_check(report_out, {REPO_ROOT})
    md_out = dl.guard_write(Path(args.md), _house_guard_profile(), inputs=[args.manifest], kind='.md',
                             overwrite=_status_overwrite_ok(args.md)) if args.md else None
    if md_out:
        _extra_guard_check(md_out, {REPO_ROOT})
    if report_out:
        report_out.write_text(rep_json(rep), encoding='utf-8')
        print(f'报告已写：{report_out}', file=sys.stderr)
    if md_out:
        md_out.write_text(render_md(rep), encoding='utf-8')
        print(f'Markdown 已写：{md_out}', file=sys.stderr)
    return 1 if pending_rows else 0


def rep_json(rep):
    return json.dumps(rep, ensure_ascii=False, indent=1)


def render_md(rep):
    lines = [f'# 新卷入书状态：{rep["batch"]}', '', f'生成时间：{rep["generated_at"]}', '',
             f'{rep["summary"]["combos"]} 组合（{rep["summary"]["exams"]} 卷 × {rep["summary"]["books"]} 本），'
             f'{rep["summary"]["pending_combos"]} 组合有待处理。', '']
    header = '| 卷 | 书 | ' + ' | '.join(str(i) for i in range(1, 10)) + ' | 下一条命令 |'
    sep = '|---' * 12 + '|'  # m9：表头 卷/书/1-9/下一条命令 共12列，分隔行原先只给11列
    lines += [header, sep]
    for r in rep['rows']:
        cells = ' | '.join(s['status'] for s in r['steps'])
        na = f'[{r["next_action"]["step"]}] {r["next_action"]["command"] or r["next_action"]["reason"]}' \
            if r['next_action'] else '（已完成）'
        lines.append(f'| {r["exam"]} | {r["book"]} | {cells} | {na} |')
    lines.append('')
    for r in rep['rows']:
        lines.append(f'## {r["exam"]} × {r["book"]}')
        for s in r['steps']:
            lines.append(f'- {s["step"]}.{s["name"]}：**{s["status"]}** —— {s["reason"]}')
            if s['next_command']:
                lines.append(f'  - 下一条命令：`{s["next_command"]}`')
        lines.append('')
    return '\n'.join(lines)


# ---------------------------------------------------------------- 写出守卫（云端补充版，同 exam_register.py）
_HOUSE_GUARD_PROFILE = None


def _house_guard_profile():
    """M5：guard_write 传 prof=None 时，_house.json 的 output_guard.protected_roots（~/GaokaoPolitics、
    ~/.codex/skills、~/.claude/skills、~/Desktop）不生效——exam_register/placement_suggest/block_insert
    都把已加载的书册 profile 传给 guard_write，本工具也该给。但本工具的写出（--report/--md/init 清单）
    与具体某本书无关，不为它专门要求一份完整书册 profile；直接读 SK 自带的 _house.json（与
    profile_lib.load_profile 合并进每本书配置的是同一份文件，见 profile_lib.PROFILE_DIR），只取它的
    output_guard 配置传给 guard_write，比每次现凑一份书册 profile 更直接、也不依赖任何具体书是否
    加载成功。没有 'frozen' 字段，不会被 guard_write 当成冻结册拒绝。"""
    global _HOUSE_GUARD_PROFILE
    if _HOUSE_GUARD_PROFILE is None:
        house_path = SK_DIR / 'profiles' / '_house.json'
        try:
            _HOUSE_GUARD_PROFILE = json.loads(house_path.read_text(encoding='utf-8'))
        except Exception:
            _HOUSE_GUARD_PROFILE = {}
    return _HOUSE_GUARD_PROFILE


def _extra_guard_check(out_path, roots):
    o = Path(out_path).resolve()
    allow = re.compile(dl.WRITE_ALLOW_RX)
    for r in roots:
        try:
            rel = o.relative_to(r)
        except ValueError:
            continue
        if not allow.search('/' + str(rel.parent) + '/'):
            raise dl.GuardError(f'落在受保护目录 {r} 内（云端补充守卫；只允许 …/协作/候选/<谁>/<批次>/构建/ 之下或系统临时目录）')


def _status_overwrite_ok(path):
    """status 要反复重跑（m3），--report/--md 允许覆盖自己以前写的同名报告——但不是随便什么已存在的
    文件都能覆盖：.json 报告核 tool=='intake_run'；.md 报告没有机读 tool 字段，核首行是不是本工具
    render_md() 写的标题行。不存在则本来就不用覆盖。"""
    p = Path(path)
    if not p.exists():
        return True
    if p.suffix.lower() == '.json':
        try:
            return json.loads(p.read_text(encoding='utf-8')).get('tool') == TOOL
        except Exception:
            return False
    try:
        text = p.read_text(encoding='utf-8')
        first_line = text.splitlines()[0] if text else ''
    except Exception:
        first_line = ''
    return first_line.startswith('# 新卷入书状态：')


def write_guarded(path, text, kind, inputs=(), overwrite=False):
    out = dl.guard_write(Path(path), _house_guard_profile(), inputs=inputs, kind=kind, overwrite=overwrite)
    _extra_guard_check(out, {REPO_ROOT})
    out.write_text(text, encoding='utf-8')
    return out


def _check_workdir_allowed(workdir):
    """init 用：workdir 必须落在允许的位置——只做位置检查，不动文件系统（不经 guard_write，因为
    guard_write 认的是“文件”，这里检查的是目录）。约定4“任一校验失败→整批中止、不留输出文件”：
    这一步必须排在 write_guarded(manifest) 之前，否则 workdir 位置不合法时清单骨架已经写出。

    M5 修复：本文件头“只读承诺”写死了 workdir 只许系统临时目录或
    …/协作/候选/<谁>/<批次>/构建/ 之下——这是比 guard_write 的“受保护根内才挡”更窄的自我承诺，
    所以直接按这条白名单判，不看 workdir 是否落在某个受保护根内（旧版“不在仓库根之内就放行”会让
    任意仓库外路径都能建目录，如 /home/user/随便一个目录）。"""
    o = Path(workdir).resolve()
    if any(_within(o, t) for t in _temp_roots_local()):
        return o
    allow = re.compile(dl.WRITE_ALLOW_RX)
    if allow.search(str(o) + '/'):
        return o
    raise dl.GuardError(f'workdir 不在允许位置（只许系统临时目录，或 …/协作/候选/<谁>/<批次>/构建/ 之下）：{o}')


def _mkdirs(workdir_abs, books=None):
    for sub in ('01_source_intake', '02_exam_register', '03_bank_compile', '09_layout', '09_publish'):
        (workdir_abs / sub).mkdir(parents=True, exist_ok=True)
    # M6：05_placement/06_insert/07_drill 的产物路径都带 <book> 一层（check_step5/6/7 的 rp），guard_write
    # 要求父目录已存在——只建到 05_placement/ 这层不够，placement_suggest 等命令照抄就会因“输出目录不
    # 存在”被拒。09_health 不在这里建：health 报告改放 _health_report_dir()（体检/…），不在 workdir 下。
    for book in (books or [k for k in ATTR_CODE if k not in FROZEN_SKIP_BOOKS]):
        for sub in ('05_placement', '06_insert', '07_drill'):
            (workdir_abs / sub / book).mkdir(parents=True, exist_ok=True)
    return workdir_abs


def _within(p, root):
    try:
        p.relative_to(root)
        return True
    except ValueError:
        return False


def _temp_roots_local():
    import tempfile
    roots = {Path(tempfile.gettempdir()).resolve()}
    for env in ('TMPDIR', 'TEMP', 'TMP'):
        v = os.environ.get(env)
        if v:
            roots.add(Path(v).resolve())
    return roots


# ---------------------------------------------------------------- init 子命令
def run_init(args):
    if not args.batch:
        raise InputError('init 需要 --batch 批次名')
    for b in (args.book or []):  # m7：未知书名不再原样写进清单骨架
        if b not in ATTR_CODE:
            raise InputError(f'书名未知：{b!r}（已知书名：{", ".join(ATTR_CODE)}）')
    for e in (args.exam_id or []):  # m7：卷号格式不对不再原样写进清单骨架
        if not EXAM_ID_RX.match(e.strip()):
            raise InputError(f'--exam-id 格式不对（应如 BJ-2026-HD-QIZHONG）：{e!r}')
    workdir_str = args.workdir or f'{Path(args.out).resolve().parent}/入书_{args.batch}'
    workdir_abs = _check_workdir_allowed(workdir_str)  # 先校验位置，不留半成品（约定4）
    manifest = OrderedDict([
        ('schema', 'baodian_intake_v1'), ('batch', args.batch),
        ('exams', [{'exam_id': e} for e in (args.exam_id or [])] or [{'exam_id': 'BJ-YYYY-XX-STAGE'}]),
        ('books', args.book or list(k for k in ATTR_CODE if k != 'bixiu2') ),
        ('profiles', OrderedDict((b, None) for b in (args.book or list(ATTR_CODE)) if b != 'bixiu2')),
        ('workdir', workdir_str),
    ])
    out = write_guarded(args.out, json.dumps(manifest, ensure_ascii=False, indent=1), kind='.json')
    made = _mkdirs(workdir_abs, args.book or None)  # M6：按清单里的书建 05_placement/06_insert/07_drill 子目录
    print(f'清单骨架已写：{out}', file=sys.stderr)
    print(f'workdir 子目录已建：{made}', file=sys.stderr)
    print(json.dumps({'manifest': str(out), 'workdir': str(made)}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------- CLI
def build_arg_parser():
    ap = argparse.ArgumentParser(prog='intake_run.py', description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--debug', action='store_true', help='打印 traceback')
    sub = ap.add_subparsers(dest='cmd', required=True)

    pi = sub.add_parser('init', help='生成清单骨架 + workdir 子目录')
    pi.add_argument('--out', required=True, help='清单骨架输出路径（受 guard_write 约束）')
    pi.add_argument('--batch', required=True, help='批次名')
    pi.add_argument('--exam-id', action='append', default=[], help='预填的卷号，可多次给')
    pi.add_argument('--book', action='append', default=[], help='预填的书名，可多次给（缺省填全部非 bixiu2 书）')
    pi.add_argument('--workdir', default=None, help='缺省为 --out 同目录下 入书_<批次>/')
    pi.add_argument('--debug', action='store_true', default=argparse.SUPPRESS)
    pi.set_defaults(func=run_init)

    ps = sub.add_parser('status', help='对清单里 exams×books 跑九步判定')
    ps.add_argument('--manifest', required=True, help='baodian_intake_v1 清单路径')
    ps.add_argument('--workdir', default=None, help='覆盖清单里的 workdir')
    ps.add_argument('--bank', default=None, help='题库根（缺省仓库根下 DeepSeek_政治题库资料库_20260918）')
    ps.add_argument('--attribution-csv', default=None, help='归属表 attribution_ruled.csv 路径（缺省按仓库真实位置）')
    ps.add_argument('--report', default=None, help='写 JSON 报告（受 guard_write 约束）')
    ps.add_argument('--md', default=None, help='写 Markdown 清单（受 guard_write 约束）')
    ps.add_argument('--quiet', action='store_true', help='不打印逐行终端表')
    ps.add_argument('--local-final', action='store_true',
                     help='仅本地：第9步在 layout/health/publish(dry-run) 证据齐全的基础上，再核 publish '
                          '报告是否真的 --apply 且 gates_pass，齐了才报 DONE；不给此开关（云端默认）第9步'
                          '最高只报 NEEDS_LOCAL（m5）')
    ps.add_argument('--debug', action='store_true', default=argparse.SUPPRESS)
    ps.set_defaults(func=run_status)
    return ap


def main(argv=None):
    ap = build_arg_parser()
    args = ap.parse_args(argv)
    debug = args.debug
    try:
        return args.func(args)
    except InputError as e:
        print(f'输入/参数错误：{e}', file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 2
    except dl.GuardError as e:
        print(f'拒绝写出：{e}', file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 3
    except Exception as e:
        print(f'内部错误：{e}', file=sys.stderr)
        if debug:
            traceback.print_exc()
        return 2


if __name__ == '__main__':
    sys.exit(main())
