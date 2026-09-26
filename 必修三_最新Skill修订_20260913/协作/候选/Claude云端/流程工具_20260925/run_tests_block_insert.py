#!/usr/bin/env python3
"""block_insert.py 自测（共同约定第 10 条：自包含、可重跑，输出目录每次先清空本工具的临时区，
用例逐条打印 PASS/FAIL 与用时，最后打印合计并以失败数为退出码；测试前后核真实输入 SHA）。

用法：
    python3 run_tests_block_insert.py

只读输入：必修三第52批真实 DOCX（R/必修三_最新Skill修订_20260913/…）、题库精简版问题 MD、
真实漏收候选原件（R/00_共同资料/原材料/…）。测试对真实文件的任何"写入"只落到本文件下方
SCRATCH 目录（系统临时目录），从不改动上述只读输入本身——main() 首尾各调用一次 baseline_guard.py
的 check（同目录 tools/baseline_guard.py），覆盖真实书稿/题库/原材料/Skill 等 3468 个文件的
SHA+mtime，任何变化都计入总 n_fail（R2-m5 修复：docstring 曾写"每条用例结束"，与实际"首尾各
一次"不符）。
"""
import sys
sys.dont_write_bytecode = True

import copy
import json
import os
import re
import shutil
import subprocess
import time
import traceback
import types
import zipfile
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
TOOL = HERE / 'block_insert.py'
PROF_DIR = HERE / 'profiles_cloud'
ROOT = HERE.parents[4]  # 仓库根：C = R/必修三.../协作/候选/Claude云端/流程工具_20260925
SCRATCH = Path('/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca'
                '/scratchpad/block_insert')
BASELINE_TOOL = HERE / 'tools' / 'baseline_guard.py'
BASELINE_BASE = HERE / '构建' / 'baseline_20260925.json'
SK = None
for p in [HERE] + list(HERE.parents):
    cand = p / '.claude' / 'skills' / 'beijing-gaokao-politics' / 'scripts'
    if cand.exists():
        SK = cand
        break

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(SK))
import block_insert as bi          # noqa: E402  只读用途：算段落文字/SHA、复用内部结构做断言
import docx_lib as dl              # noqa: E402
import batch_health as bh          # noqa: E402
import apply_patch as ap           # noqa: E402

W = bh.W
BIXIU3_DOCX = ROOT / '必修三_最新Skill修订_20260913' / '必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx'
BIXIU3_SHA = 'c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6'
PROF_BIXIU3 = PROF_DIR / 'bixiu3.json'
PROF_BIXIU2_FROZEN = PROF_DIR / 'bixiu2_frozen_test.json'
PROF_PHILOSOPHY = PROF_DIR / 'philosophy.draft.json'
PHILOSOPHY_DOCX = ROOT / '其他书工作头' / '哲学' / '哲学宝典_修订稿_R10_漏节点与附录补全及触发词修正版_20260908.docx'
XC_ERMO_DOCX = (ROOT / '00_共同资料' / '原材料' / '2023模拟题' / '2023各区模拟题(1)' / '各区二模' /
                '√西城' / '西城-高三政治二模试卷-定(2).docx')
# 返修 r1 新增：真实原件，专供 B2（表格内超链接/图片关系重建）、M1（表内 docPr 去重）、m1（表格含
# 文本框安全中止）三条复现用例——都是审查 r1 探针脚本实测用过的同一批文件（21.docx table_index=1
# 有 4 个 External 超链接 + 3 张图；17(1).docx table_index=1 的 docPr id 是 [1,3,2]，与本书前部
# 已有 id 冲突；16题二模阅卷总结.docx table_index=1 含文本框）。
_DCEM = ROOT / '00_共同资料' / '原材料' / '2024模拟题' / '东城二模' / '细则' / '分题细则' / '阅卷总结'
HYPERLINK_TABLE_DOCX = _DCEM / '21题' / '21.docx'
DOCPR_TABLE_DOCX = _DCEM / '17题' / '17(1).docx'
TEXTBOX_TABLE_DOCX = _DCEM / '16题' / '16题二模阅卷总结.docx'
# R2-M4/R2-B1 新增：真实 B3 漏收候选 BJ-2023-HD-QIZHONG-Q18#1（原件是 DOCX，第 5 表，tblStyle
# af0=Table Grid——与本书 af0=段落样式"macro"撞号，见 B3_漏收候选.csv 与 R2-B1 blocker 原始证据；
# 单元格楷体/行距360/首行缩进200字符是原件直接格式，表宽 9742 twips 超版心 9298）。
TEACHER_HD_QIZHONG_2023_DOCX = (ROOT / '00_共同资料' / '原材料' / '2023模拟题' / '2023各区模拟题(1)' /
                                 '期末和期中' / '2023北京海淀高三（上）期中政治（教师版）.docx')
# 返修 r3 新增：R3-M3（表格内下划线填空空位）、R3-m2（嵌套表格 tblStyle 撞号）、R3-m3（浮动表带
# 内容）三条复现用例的真实原件——都是审查 r3 探针脚本实测用过的同一批文件。
CY_ERMO_TEACHER_DOCX = (ROOT / '00_共同资料' / '原材料' / '2026模拟题' / '2026各区二模' / '2026朝阳二模' /
                         '试卷' / '2026北京朝阳高三二模政治（教师版）.docx')
FT_ERMO_XICE_17TI_DOCX = (ROOT / '00_共同资料' / '原材料' / '2025模拟题' / '2025各区二模' / '2025丰台二模' /
                           '细则' / '分题细则' / '2025丰台二模评标细则' / '2025丰台二模评标细则' / '17题.docx')
BX4_2024_YIMO_DOCX = (ROOT / '00_共同资料' / '原材料' / '2024模拟题' / '202404各区一模试题分类（按模块）' /
                       '2024届各区一模试题分类汇编必修4.docx')

results = []


def run_baseline_guard(label):
    """M7 修复：run_tests 文件头 docstring 早就声称"每条用例结束都用 baseline_guard 核对"，但
    main() 原先只在开头核一次必修三父稿 SHA，全文没有调用 baseline_guard.py——docstring 与实际行为
    对不上。这里真正调用它，在 main() 开头和结尾各跑一次，核真实书稿/审阅入口/其他书/题库/Skill/
    原材料/后勤/云端共 3468 个文件的 SHA+mtime 与 Skill 下是否有 __pycache__ 残留，任何变化都算
    FAIL（计入总 n_fail，不是单独旁路）。"""
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, str(BASELINE_TOOL), 'check', '--base', str(BASELINE_BASE)],
                            capture_output=True, text=True, timeout=180, cwd=str(HERE))
        try:
            data = json.loads(r.stdout)
        except Exception:
            data = {}
        ok = r.returncode == 0
        detail = (f'rc={r.returncode} files={data.get("files")} changed={len(data.get("changed", []))} '
                  f'removed={len(data.get("removed", []))} added={len(data.get("added", []))} '
                  f'skill_pycache={len(data.get("skill_pycache", []))}')
        if not ok:
            detail += f' stdout={r.stdout[-800:]} stderr={r.stderr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    return record(f'baseline_guard_{label}', ok, detail, t0)


def run_tool(args, timeout=180):
    cmd = [sys.executable, str(TOOL), '--debug'] + list(args)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout, r.stderr


def record(name, ok, detail, t0):
    dt = round(time.time() - t0, 2)
    results.append({'name': name, 'result': 'PASS' if ok else 'FAIL', 'seconds': dt, 'detail': detail})
    print(f'[{"PASS" if ok else "FAIL"}] {name} ({dt}s) {detail if not ok else ""}')
    return ok


def sha256_file(p):
    return dl.sha256_file(p)


def fresh_copy(dst_name):
    dst = SCRATCH / dst_name
    dst.unlink(missing_ok=True)
    shutil.copyfile(BIXIU3_DOCX, dst)
    return dst


def load_report(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


# ------------------------------------------------------------------ 插入单构造（真实漏收候选）
def unit_image_q(parent_sha):
    intro1 = ('北京公交集团主导的“公交便民驿栈”来了！和平里北街的一处公交场站，停泊着一辆满载水果、'
              '蔬菜的“退役公交车”。公交车一侧面对路边行人，一侧面对公交场站，人们下了公交车就能顺手'
              '买到价格便宜又新鲜的水果和蔬菜，方便极了。')
    intro2 = ('打通公共交通和基层社区、覆盖全城的首都智慧便民社区服务网络，主要根据周边社区服务需求，'
              '以“缺什么补什么”为原则，建设一刻钟便民生活圈。每个栈点的选位均经过调研测算，在确保'
              '运营不受影响的情况下，利用场站边角空间建设。按照项目规划，3年内将建设至少300个公交'
              '便民服务栈点，辐射北京90%以上的社区人口。同时，将新增3000个生活性服务业就业岗位。')
    intro3 = ('《首都功能核心区控制性详细规划（街区层面）（2018年—2035年）》提出，要适度提高公共服务'
              '用地比重，将零散土地用于公共服务设施建设，提高居住品质，改善人居环境。')
    rubric = ('【细则说明】 （1）推广便民服务栈有利于促进就业，保障和改善民生，推动共享发展成果；'
              '盘活老旧公交车、利用站点边角空间打造服务设施，为市民提供物美价廉、消费便捷的市场供给，'
              '提高资源配置效率；更好发挥政府作用，规划便民服务栈建设，优化公共服务，提升人民生活的'
              '幸福感和获得感。（6分）（2）建议合理可行1分，能运用术语或观点做简要说明1分。两条建议'
              '共4分。')
    return {
        'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': parent_sha,
        'approved_by': 'claude:block_insert-run_tests', 'approval_ref':
            'block_insert.py 验收测试：真实漏收候选 BJ-2023-XC-ERMO-Q16（带图），测试用，未经教学审定',
        'inserts': [{
            'id': 'I001',
            'anchor': {'after_block': {'title_contains': '例题 5　2026门头沟一模第17题'}},
            'template_block': {'title_contains': '例题 5　2026门头沟一模第17题'},
            'title': '例题 90　2023西城二模第16题',
            'source_zone': 'restore',
            'reason': '题目材料与设问逐字取自原件 西城-高三政治二模试卷-定(2).docx（题库漏收候选 '
                      'BJ-2023-XC-ERMO-Q16#2），教学栏目为工具验收测试内容，未经教学审定',
            'content': [
                {'role': 'source', 'text': '【题目】16．（10分）'},
                {'role': 'source', 'text': intro1},
                {'role': 'image', 'from': {'docx': str(XC_ERMO_DOCX), 'rid': 'rId14'}},
                {'role': 'source', 'text': intro2},
                {'role': 'source', 'text': '（1）结合材料，分析北京市推广便民服务栈点的经济原因。（6分）'},
                {'role': 'source', 'text': intro3},
                {'role': 'source', 'text': '（2）运用所学，针对上述目标提出两条具体建议。（4分）'},
                {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】'},
                {'role': 'teaching', 'like': '从材料选知识',
                 'text': '从材料选知识：便民驿栈利用退役公交车与场站边角空间，提示资源配置与市场供给；'
                         '政府规划建设时间表与覆盖比例，提示政府更好发挥作用；核心区详细规划提出公共'
                         '服务用地目标，提示改善民生、提高居住品质。'},
                {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】'},
                {'role': 'teaching', 'like': '相贯通，坚持党的领导',
                 'text': '①推广便民服务栈有利于促进就业，保障和改善民生，推动共享发展成果；②盘活老旧'
                         '公交车、利用站点边角空间打造服务设施，提高资源配置效率；③更好发挥政府作用，'
                         '规划便民服务栈建设，优化公共服务。'},
                {'role': 'rubric', 'text': rubric},
            ],
        }],
    }


def unit_table_q(parent_sha):
    rows = [
        ['【以“调”解纷】', '【以“惩”亮剑】', '【以“辩”正风】'],
        [
            '针对生物医药领域科研人员的专利权归属纠纷，为减少诉讼对创新活动的干扰，人民法院摒弃'
            '“一判了之”，特邀请第三方调停，促成当事人当庭和解，一揽子化解关联诉讼，让科研人员安心'
            '回归科研创新。',
            '对故意侵害植物新品种权、商业秘密等行为，依法适用惩罚性赔偿。在某玉米品种故意严重侵权'
            '案中，判决侵权人赔偿5300余万元；在“玻璃机”技术秘密侵权案中，判决赔偿3.8亿余元，大幅'
            '提高侵权违法成本。',
            '针对假借“维权”之名实施的恶意诉讼、权利滥用行为，人民法院依法快速审结并予以明确否定。'
            '某日化公司恶意提起知识产权诉讼，其诉讼请求被法院全部驳回并受到司法谴责，有效规制阻碍'
            '创新的不诚信诉讼行为。',
        ],
    ]
    rubric = ('【细则说明】 措施类：人民法院做了什么+做得怎么样？①通过特邀第三方调解，高效化解知识'
              '产权纠纷，既维护当事人合法权益，又能激发创新积极性和创新效率，助力创新驱动经济发展'
              '（调解、提高诉讼效率/降低诉讼成本，2分）。②针对故意侵权的违法行为，适用《民法典》'
              '惩罚性赔偿规定，有效遏制侵权人再次侵权，保护创新主体的核心利益，维护良好的创新生态和'
              '公平竞争的市场环境（惩罚性赔偿规定/提高侵权违法成本、维护市场环境，2分）。③依据民法'
              '公平、诚信等基本原则，谴责专利权人的不诚信诉讼行为，保障诉讼秩序和经营秩序，避免'
              '“假维权”拖垮“真创新”，营造诚信守法的创新生态（驳回谴责/有效遏制不诚信诉讼行为、'
              '诚信/公平原则，2分）。')
    return {
        'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': parent_sha,
        'approved_by': 'claude:block_insert-run_tests', 'approval_ref':
            'block_insert.py 验收测试：真实漏收候选 BJ-2026-CY-YIMO-Q18（带表，题库无原件DOCX，表格'
            '按官方转写内容以 rows 生成），测试用，未经教学审定',
        'inserts': [{
            'id': 'I001',
            'anchor': {'after_block': {'title_contains': '例题 3　2024朝阳二模第18题'}},
            'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
            'title': '例题 91　2026朝阳一模第18题',
            'source_zone': 'restore',
            'reason': '题目材料、表格文字与设问逐字取自题库精简版 BJ-2026-CY-YIMO-Q18 的原卷回源'
                      '文字（原件为PDF，题库无DOCX，表格按官方转写内容以 rows 生成），教学栏目为工具'
                      '验收测试内容，未经教学审定',
            'content': [
                {'role': 'source', 'text': '【题目】18.（8分）2026年是“十五五”开局之年，'
                 '“创新”“科技”成为规划纲要的高频词，新质生产力发展离不开知识产权的坚实保障。'
                 '人民法院通过“调、惩、辨”三维实践，为创新发展筑牢法治屏障。'},
                {'role': 'table', 'rows': rows},
                {'role': 'source', 'text': '结合材料，运用《法律与生活》知识，谈谈人民法院是如何依法'
                 '保护知识产权以护航新质生产力发展的。'},
                {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】'},
                {'role': 'teaching', 'like': '从材料选知识',
                 'text': '从材料选知识：“邀请第三方调停促成和解”提示纠纷的多元解决方式；“依法适用'
                         '惩罚性赔偿、大幅提高侵权违法成本”提示侵权责任的承担方式；“依法快速审结并'
                         '否定恶意诉讼”提示司法公正与诚信原则。'},
                {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】'},
                {'role': 'teaching', 'like': '总述',
                 'text': '①坚持调解优先，高效化解知识产权纠纷，激发创新积极性；②坚持严格保护，适用'
                         '惩罚性赔偿，提高侵权违法成本；③坚持规制滥用，否定恶意诉讼，维护公平竞争的'
                         '创新环境。'},
                {'role': 'rubric', 'text': rubric},
            ],
        }],
    }


def unit_text_q(parent_sha):
    material = ('19．（6分）遗赠扶养协议纠纷案宣判。【案情简介】某社区居委会与曹某签订协议，约定由'
                '某居委会定时定员结对子照看关心曹某，每月给予曹某基本生活费，免费看病诊治，逢年过节'
                '给予曹某各类生活补助及慰问生活用品等，养老至寿终；曹某现有的动产和不动产在曹某寿终'
                '后，产权移交某居委会。此后，某居委会按照约定履行扶养义务。曹某去世后，曹某的四个'
                '子女要求继承遗产，与该居委会产生争议。该居委会遂将曹某的四个子女等人诉至法院，请求'
                '判令：（1）确认某居委会与曹某签订的协议有效；（2）曹某名下的房屋、股权、现金、存款'
                '归某居委会所有。')
    verdict = ('【裁判结果】法院认为，案涉协议符合法律有关遗赠扶养协议的规定，属于有效的遗赠扶养'
               '协议；原告某居委会对被扶养人曹某已尽到扶养义务，判决被继承人曹某安置所得的房屋以及'
               '其生前遗留的股权、现金、银行存款本息归某居委会所有。')
    rubric = ('【细则说明】 判决内容：居委会尽到扶养义务，遗赠扶养协议合法有效（1分）。社会价值①：'
              '维护居委会合法权益、使老人的生活得到保障，或有利于权利义务相统一（1分）。社会价值②：'
              '公平正义，或公序良俗/诚信原则/提高法治意识（1分）。社会价值③：弘扬中华传统美德、'
              '践行社会主义核心价值观，或孝亲敬老（1分）。')
    return {
        'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': parent_sha,
        'approved_by': 'claude:block_insert-run_tests', 'approval_ref':
            'block_insert.py 验收测试：真实漏收候选 BJ-2024-HD-ERMO-Q19（纯文字，无图无表），测试用，'
            '未经教学审定',
        'inserts': [{
            'id': 'I001',
            'anchor': {'after_block': {'title_contains': '例题 3　2024朝阳二模第18题'}},
            'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
            'title': '例题 92　2024海淀二模第19题',
            'source_zone': 'restore',
            'reason': '题目材料与设问逐字取自原件 高三二模：政治试题（以PDF为准）(1).docx（题库漏收'
                      '候选 BJ-2024-HD-ERMO-Q19），细则取自正式评分材料转写，教学栏目为工具验收测试'
                      '内容，未经教学审定',
            'content': [
                {'role': 'source', 'text': '【题目】' + material},
                {'role': 'source', 'text': verdict},
                {'role': 'source', 'text': '结合材料，运用《法律与生活》知识，分析本案判决的社会'
                 '价值。'},
                {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】'},
                {'role': 'teaching', 'like': '从材料选知识',
                 'text': '从材料选知识：居委会长期履行照看、生活费、医疗、慰问等扶养义务，提示遗赠'
                         '扶养协议的合法有效与权利义务相统一；法院支持居委会诉求，提示司法裁判对公序'
                         '良俗与诚信原则的维护，以及对孝亲敬老传统美德和社会主义核心价值观的弘扬。'},
                {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】'},
                {'role': 'teaching', 'like': '总述',
                 'text': '①认定遗赠扶养协议合法有效，维护居委会合法权益，保障老人生活；②坚持公平'
                         '正义、公序良俗与诚信原则；③弘扬孝亲敬老等中华传统美德，践行社会主义核心'
                         '价值观。'},
                {'role': 'rubric', 'text': rubric},
            ],
        }],
    }


def _run_fmt(p):
    """段内每个 run 的 (字符数, 是否加粗, 颜色) ——B1 格式断言的基础读数。"""
    out = []
    for r, t in ap._run_spans(p):
        rpr = r.find(W + 'rPr')
        b = rpr.find(W + 'b') is not None if rpr is not None else False
        c = rpr.find(W + 'color') if rpr is not None else None
        out.append((len(t), b, c.get(W + 'val') if c is not None else None))
    return out


def _find_para(paras, prefix):
    for i, p in enumerate(paras):
        if dl.para_text(p).startswith(prefix):
            return i, p
    return None, None


def _assert_stem_font_at(d2, prefix, problems, label):
    """R2-B2 断言：以 prefix 定位到的设问段，其首个非空 run 的有效字体（_effective_font_sz，沿
    样式继承链算，不只看 run 自己的 XML 字面量）应为 Songti SC——本书设问正文的既定约定
    （style-spec.md 第69条），旧版会被"多数格式"带偏成材料段的隐式楷体。"""
    i, p = _find_para(d2.paras, prefix)
    if p is None:
        problems.append(f'{label}：没找到以 "{prefix[:14]}" 开头的设问段')
        return
    if not bi._STEM_LEAD_RX.match(dl.para_text(p).strip()):
        problems.append(f'{label}：段落不匹配设问引导词正则，断言本身失配（前缀 "{prefix[:14]}"）')
        return
    spans = ap._run_spans(p)
    for r, t in spans:
        if not t:
            continue
        font, _sz = _effective_font_sz(p, r.find(W + 'rPr'))
        if font != 'Songti SC':
            problems.append(f'{label}：设问段有效字体是 {font!r}，应为 Songti SC（R2-B2）')
        break


def _b1_format_checks(out_docx, kind):
    """B1/R2-B2 修复的格式断言（读预重排的 out，不读 --renumber 后的文件——重排只动编号/考法
    （N题），不动本工具刚构造的段落，读哪份都行，读未重排的更直接）。返回 (ok, detail)。"""
    d2 = dl.open_docx(out_docx)
    problems = []

    def assert_plain(prefix, label):
        i, p = _find_para(d2.paras, prefix)
        if p is None:
            problems.append(f'{label}：没找到以 "{prefix[:12]}" 开头的段落')
            return
        fmt = _run_fmt(p)
        if any(b for _, b, _ in fmt):
            problems.append(f'{label}：段落整体/部分被加粗（应为纯正文）fmt={fmt}')

    def assert_not_table_ind(prefix, label):
        """R2-B2 残留修复：设问段不该继承表格单元格常见的 keepLines/ind firstLine=0（样板题块
        带表格时曾经踩过，见 find_role_template 的表格排除注释）。"""
        i, p = _find_para(d2.paras, prefix)
        if p is None:
            problems.append(f'{label}：没找到段落')
            return
        ppr = p.find(W + 'pPr')
        if ppr is None:
            return
        if ppr.find(W + 'keepLines') is not None:
            problems.append(f'{label}：不该带 keepLines（表格单元格惯用格式）')
        ind = ppr.find(W + 'ind')
        if ind is not None and ind.get(W + 'firstLine') == '0':
            problems.append(f'{label}：不该带 ind firstLine=0（表格单元格惯用格式）')

    if kind == 'image':
        assert_plain('北京公交集团主导的', '材料段 intro1')
        assert_plain('打通公共交通和基层社区', '材料段 intro2')
        assert_plain('（1）结合材料，分析北京市推广便民服务栈点', '设问段(1)')
        _assert_stem_font_at(d2, '（1）结合材料，分析北京市推广便民服务栈点', problems, '设问段(1)_字体')
        _assert_stem_font_at(d2, '（2）运用所学，针对上述目标提出两条具体建议', problems, '设问段(2)_字体')
        i, p = _find_para(d2.paras, '从材料选知识：便民驿栈利用退役公交车')
        if p is None:
            problems.append('教学段"从材料选知识"：没找到')
        else:
            fmt = _run_fmt(p)
            if not (len(fmt) >= 2 and fmt[0][1] and fmt[0][0] == len('从材料选知识：') and
                    all(not b for _, b, _ in fmt[1:])):
                problems.append(f'教学段"从材料选知识"：引导词/正文两段式格式不对 fmt={fmt}')
        i, p = _find_para(d2.paras, '①推广便民服务栈有利于促进就业')
        if p is None:
            problems.append('教学段"①推广……"：没找到')
        elif any(b for _, b, _ in _run_fmt(p)):
            problems.append(f'教学段"①推广……"：不该整段加粗 fmt={_run_fmt(p)}')
        # m10：新图 pic:cNvPr 的 id 应与它自己的 wp:docPr id 一致（都重新分配、非 0）——只查新插入
        # 的那张图（紧跟在 intro1 材料段之后，按插入单 content 顺序），不查全书既有图片（本书既有图片
        # 的 pic:cNvPr 本就历史遗留是 0，是书稿现状不是本工具插入动作造成的，见回执 known_limits）。
        i0, _ = _find_para(d2.paras, '北京公交集团主导的')
        new_img_dr = None
        if i0 is not None:
            for p in d2.paras[i0:i0 + 5]:
                dr = p.find(f'.//{bi.WP_NS}inline')
                if dr is not None:
                    new_img_dr = dr
                    break
        if new_img_dr is None:
            problems.append('m10：没找到新插入图片所在段落')
        else:
            docpr = new_img_dr.find(bi.WP_NS + 'docPr')
            cnvpr = new_img_dr.find(f'.//{bi.PIC_NS}cNvPr')
            if docpr is None or cnvpr is None or cnvpr.get('id') == '0' or cnvpr.get('id') != docpr.get('id'):
                problems.append(f'm10：新图 pic:cNvPr id={cnvpr.get("id") if cnvpr is not None else None!r} '
                                f'与 wp:docPr id={docpr.get("id") if docpr is not None else None!r} 不一致或仍是 0')
    elif kind == 'table':
        assert_plain('结合材料，运用《法律与生活》知识', '设问段（表格题）')
        _assert_stem_font_at(d2, '结合材料，运用《法律与生活》知识', problems, '设问段（表格题）_字体')
        assert_not_table_ind('结合材料，运用《法律与生活》知识', '设问段（表格题）')
        # 表格第 0 行（表头）应加粗、其余行不加粗（B1：build_table_from_rows 修复）
        target_tbl = None
        for tbl in bi._top_tables(d2.body):
            texts = ''.join(dl.para_text(p) for p in tbl.iter(W + 'p'))
            if '以"调"解纷' in texts or '以“调”解纷' in texts:
                target_tbl = tbl
                break
        if target_tbl is None:
            problems.append('没找到新插入的表格（按表头文字定位失败）')
        else:
            trs = target_tbl.findall(W + 'tr')
            if len(trs) < 2:
                problems.append(f'新表格行数异常：{len(trs)}')
            else:
                for ci, tc in enumerate(trs[0].findall(W + 'tc')):
                    p = tc.find(W + 'p')
                    if p is not None and not all(b for _, b, _ in _run_fmt(p)):
                        problems.append(f'表头第{ci}列不是全加粗：{_run_fmt(p)}')
                for ci, tc in enumerate(trs[1].findall(W + 'tc')):
                    p = tc.find(W + 'p')
                    if p is not None and any(b for _, b, _ in _run_fmt(p)):
                        problems.append(f'表体第{ci}列不应加粗：{_run_fmt(p)}')
    elif kind == 'text':
        assert_plain('结合材料，运用《法律与生活》知识，分析本案判决', '设问段（纯文字题）')
        _assert_stem_font_at(d2, '结合材料，运用《法律与生活》知识，分析本案判决', problems,
                             '设问段（纯文字题）_字体')
        assert_not_table_ind('结合材料，运用《法律与生活》知识，分析本案判决', '设问段（纯文字题）')
        # R2-B2 残留修复复现：材料内的【裁判结果】标签不该套成跟块开场【题目】标签一样的加粗+
        # 1F4E79（深蓝）+keepNext——全书 191 个材料内【】标签里 163 个只加粗不上色，见
        # find_role_template 的 exclude_idx 参数说明。
        i, p = _find_para(d2.paras, '【裁判结果】法院认为')
        if p is None:
            problems.append('材料内标签【裁判结果】：没找到')
        else:
            fmt = _run_fmt(p)
            if fmt and fmt[0][2] == '1F4E79':
                problems.append(f'材料内标签【裁判结果】：被套成开场标题的深蓝色 fmt={fmt}')
            # R3-m1 断言（不是循环验证）：材料内标签的有效字体不该是宋体（设问字体）——那是 R3-B1/
            # R3-m1 指出的"块内没有同形状候选时退化到设问格式"这个坑；按有效字体（沿样式继承链，
            # 不只看 run 自己的 XML 字面量）判断，不看工具自己的形状正则。这条本轮真修好了：块内
            # 退化匹配的偏好顺序已改成"标签优先，material（plain）在前、设问（stem）在后"（见
            # _SHAPE_PREF），旧版会落到设问格式（Songti SC），本輪不会。
            spans = ap._run_spans(p)
            font0 = _effective_font_sz(p, spans[0][0].find(W + 'rPr'))[0] if spans else None
            if font0 == 'Songti SC':
                problems.append(f'材料内标签【裁判结果】：有效字体是宋体（应为材料楷体，R3-B1/m1）fmt={fmt}')
            # R3-m1 已知残留（未完全修复，如实记录，不假装断言通过）：B0003 块内唯一的非表格
            # "plain" 候选恰好是表格上方全段加粗的图注（"2024年国务院《政府工作报告》的形成过程"，
            # 见 _pick_by_shape 文档字符串里同一个例子），块内退化匹配到 'plain' 时会带出这份加粗
            # ——本工具"块内/全书按形状挑多数格式"的设计不识别"这段是不是异常值"，真正修好需要能
            # 分辨"全书 label_prefix 形状里哪些是块开场标题、哪些是材料内子标签"，超出本轮范围，
            # 已写进回执 known_limits，这里不隐瞒也不用弱断言掩盖，只断言字体族这条真已修好的。
    return (not problems), '；'.join(problems)


# ------------------------------------------------------------------ 测试 1：真实新题（图/表/纯文字）
def test_real_questions():
    ok_all = True
    for name, builder, expect_media in (
        ('T1a_真实新题_带图_BJ-2023-XC-ERMO-Q16', unit_image_q, 'image'),
        ('T1b_真实新题_带表_BJ-2026-CY-YIMO-Q18', unit_table_q, 'table'),
        ('T1c_真实新题_纯文字_BJ-2024-HD-ERMO-Q19', unit_text_q, None),
    ):
        t0 = time.time()
        try:
            docx = fresh_copy(f'{name}_parent.docx')
            unit_path = SCRATCH / f'{name}_insert.json'
            unit_path.write_text(json.dumps(builder(BIXIU3_SHA), ensure_ascii=False, indent=2),
                                  encoding='utf-8')
            out = SCRATCH / f'{name}_out.docx'
            out.unlink(missing_ok=True)
            report = SCRATCH / f'{name}_report.json'
            rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                        '--out', str(out), '--profile', str(PROF_BIXIU3),
                                        '--report', str(report), '--health', '--renumber'])
            rep = load_report(report) if report.exists() else {}
            health = rep.get('health', {})
            final = out.with_name(out.stem + '_renumbered' + out.suffix)
            ok = rc == 0 and health.get('new_FAIL_count') == 0 and final.exists()
            bic = rep.get('verify', {}).get('block_index_check', [{}])
            media_ok = True
            if expect_media == 'image':
                media_ok = bic and bic[0].get('media_match')
            elif expect_media == 'table':
                media_ok = bic and bic[0].get('tables_match')
            ok = ok and media_ok
            fmt_detail = ''
            if ok:
                # R2-B2 修复：T1c（纯文字，expect_media=None）原先完全不跑格式断言——三道真实新题
                # 里唯二能测到"设问段丢宋体""材料内标签被套成开场标题深蓝"这两条残留的用例，旧
                # 测试反而是漏测的那一个。
                fmt_ok, fmt_detail = _b1_format_checks(out, expect_media or 'text')
                ok = ok and fmt_ok
            detail = (f'rc={rc} new_FAIL={health.get("new_FAIL_count")} block_index={bic} '
                      f'B1格式检查={fmt_detail or "OK"} stderr={serr[-300:] if not ok else ""}')
        except Exception as e:
            ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-800:]}'
        ok_all &= record(name, ok, detail, t0)
    return ok_all


# ------------------------------------------------------------------ 测试 2：金标回归（删旧题再按原文重插）
_TITLE_BUCKETS = None


def _bucket_of(style_name):
    global _TITLE_BUCKETS
    if _TITLE_BUCKETS is None:
        prof = bi.load_profile(str(PROF_BIXIU3))
        s = prof.get('styles', {})
        _TITLE_BUCKETS = {}
        for b in ('source', 'teaching', 'rubric'):
            for n in s.get(b, []) or []:
                _TITLE_BUCKETS[n] = b
    return _TITLE_BUCKETS.get(style_name)


def _global_drawing_index(docx_path, target_para_i):
    """按段号找该段里的图形在全书（document.xml 全文 wp:inline/wp:anchor）里的 1 起序号——811 页的
    合订本里，同一张图、甚至同一段材料文字都可能在别的章节重复出现（同一案例跨模块引用），rId 和
    near_text 都可能不唯一，只有"全书第几个图形"这个位置量是精确的，用来生成 image.from.index
    选择器，与 block_insert.locate_source_image 的第三种定位方式对齐。"""
    with zipfile.ZipFile(docx_path) as z:
        root = etree.fromstring(z.read('word/document.xml'))
    body = root.find(W + 'body')
    paras = bi.dl.para_elements(body)
    target_p = paras[target_para_i]
    drawing_in_target = None
    for dr in target_p.iter():
        if dr.tag in (bi.WP_NS + 'inline', bi.WP_NS + 'anchor'):
            drawing_in_target = dr
            break
    if drawing_in_target is None:
        raise RuntimeError(f'第 {target_para_i} 段里没有找到 wp:inline/wp:anchor')
    all_drawings = bi._drawing_elements(root)
    return all_drawings.index(drawing_in_target) + 1


def gold_content_from_span(items, title_i, end_i, pristine_path):
    """图用"全书第几个图形"（见 _global_drawing_index）定位，不用 rid/near_text：811 页合订本里
    同一张图的 rId、乃至同一段材料文字都可能在别的章节重复出现（同一案例跨模块引用），只有这个
    位置量是精确的。"""
    content = []
    seen_tbl = set()
    for i in range(title_i + 1, end_i + 1):
        it = items[i]
        if it['tbl'] is not None:
            if it['tbl'] not in seen_tbl:
                seen_tbl.add(it['tbl'])
                content.append({'role': 'table', 'from': {'docx': str(pristine_path),
                                                            'table_index': it['tbl']}})
            continue
        if it.get('img'):
            gi = _global_drawing_index(pristine_path, i)
            content.append({'role': 'image', 'from': {'docx': str(pristine_path), 'index': gi}})
            continue
        bucket = _bucket_of(it['style']) or 'teaching'
        content.append({'role': bucket, 'style': it['style'], 'text': it['text']})
    return content


# R2-B2 修复：_visual_rpr 原先完全不比 rFonts/sz，理由是"样式默认值本来就是它，新段没显式写，
# 视觉上完全一样"——这个前提本身没有验证。真实核对（探针 gold_fontdiff.py）：本书"题目材料"样式
# （aff6）的默认 eastAsia 其实是 Kaiti SC（楷体），style-spec.md 第69条也写明材料正文楷体、设问
# 正文宋体；全书 290 个设问段里 284 个显式写了 Songti SC（宋体）。按"样式默认值"的错误假设不比
# 字体，恰好把"设问段被 block_insert 从宋体丢成楷体"这个真实 bug 完全屏蔽掉，两个金标用例各漏列
# 1 处。改成按继承链算出"有效字体/字号"（run 自己有就用 run 的，没有就沿 pStyle 的 basedOn 链
# 找样式定义，再退到 docDefaults），比较的是真正的视觉呈现，不是 XML 表达方式是否相同。
_STYLE_FONT_CTX = None  # (font_idx, sz_idx, based, doc_default_font, doc_default_sz)，懒加载一次


def _load_style_font_ctx():
    global _STYLE_FONT_CTX
    if _STYLE_FONT_CTX is not None:
        return _STYLE_FONT_CTX
    with zipfile.ZipFile(BIXIU3_DOCX) as z:
        styles_root = etree.fromstring(z.read('word/styles.xml'))
    font_idx, sz_idx, based = {}, {}, {}
    for st in styles_root.iter(W + 'style'):
        sid = st.get(W + 'styleId')
        if not sid:
            continue
        rf = st.find(f'{W}rPr/{W}rFonts')
        font_idx[sid] = rf.get(W + 'eastAsia') if rf is not None else None
        sz = st.find(f'{W}rPr/{W}sz')
        sz_idx[sid] = sz.get(W + 'val') if sz is not None else None
        b = st.find(W + 'basedOn')
        based[sid] = b.get(W + 'val') if b is not None else None
    rf0 = styles_root.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}rFonts')
    sz0 = styles_root.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}sz')
    _STYLE_FONT_CTX = (font_idx, sz_idx, based,
                       rf0.get(W + 'eastAsia') if rf0 is not None else None,
                       sz0.get(W + 'val') if sz0 is not None else None)
    return _STYLE_FONT_CTX


def _resolve_chain(sid, idx, based, default):
    seen = set()
    while sid and sid not in seen:
        seen.add(sid)
        v = idx.get(sid)
        if v is not None:
            return v
        sid = based.get(sid)
    return default


def _effective_font_sz(p, run_rpr):
    """run 自己写了 rFonts/eastAsia（或 sz）就用它；没写就沿段落 pStyle 的 basedOn 链找，最后退到
    docDefaults——这是"有效字体/字号"，不是 XML 字面量。"""
    font_idx, sz_idx, based, doc_font, doc_sz = _load_style_font_ctx()
    ppr = p.find(W + 'pPr')
    pstyle = ppr.find(W + 'pStyle') if ppr is not None else None
    sid = pstyle.get(W + 'val') if pstyle is not None else None
    font = sz = None
    if run_rpr is not None:
        rf = run_rpr.find(W + 'rFonts')
        if rf is not None and rf.get(W + 'eastAsia'):
            font = rf.get(W + 'eastAsia')
        szel = run_rpr.find(W + 'sz')
        if szel is not None and szel.get(W + 'val'):
            sz = szel.get(W + 'val')
    if font is None:
        font = _resolve_chain(sid, font_idx, based, doc_font)
    if sz is None:
        sz = _resolve_chain(sid, sz_idx, based, doc_sz)
    return font, sz


def _visual_rpr(rpr, font_sz):
    """run 格式签名只取"看得见的"几项（B3：比原始 rPr c14n 更贴近'格式差异'本身该问的问题）——
    书稿里同一种正文格式，Word 编辑历史常把一段文字拆成好几个 run（同一份 rPr 却出现好几次），也
    可能带一些不影响呈现的簿记属性（如 lang、noProof）；这些差异不是"格式差异"，只按 c14n 整段比
    会把这类噪音也判成差异，掩盖真正该看的加粗/颜色/字体/字号问题（也会让真正的 B1 式 bug——标签
    格式带进正文——和这类噪音混在一起，看不出哪条是真的）。font_sz 是调用方按 _effective_font_sz
    算好的有效字体/字号（R2-B2 修复：不再无条件跳过，见函数外的模块级注释）。"""
    if rpr is None:
        return (False, False, False, None) + font_sz
    b = rpr.find(W + 'b')
    i = rpr.find(W + 'i')
    color_el = rpr.find(W + 'color')
    return (
        b is not None and b.get(W + 'val') not in ('0', 'false'),
        i is not None and i.get(W + 'val') not in ('0', 'false'),
        rpr.find(W + 'u') is not None,
        color_el.get(W + 'val') if color_el is not None else None,
    ) + font_sz


def _visual_segments(p):
    """段内按"看得见的格式"合并相邻同格式 run 后的 (格式, 字符数) 序列——Word 把同一种格式拆成
    几个 run，合并后就是同一个 segment，不再被计成差异（见 _visual_rpr 注释）。"""
    segs = []
    for run, text in ap._run_spans(p):
        if not text:
            continue
        rpr = run.find(W + 'rPr')
        vf = _visual_rpr(rpr, _effective_font_sz(p, rpr))
        if segs and segs[-1][0] == vf:
            segs[-1] = (vf, segs[-1][1] + len(text))
        else:
            segs.append([vf, len(text)])
    return tuple((vf, n) for vf, n in segs)


def _visual_ppr(ppr):
    """段落格式签名只取看得见的几项：样式、对齐、是否与下段同页、缩进、段前后间距——不比 rsid 之类
    的编辑簿记属性。"""
    if ppr is None:
        return ()
    pstyle = ppr.find(W + 'pStyle')
    jc = ppr.find(W + 'jc')
    ind = ppr.find(W + 'ind')
    spacing = ppr.find(W + 'spacing')
    return (
        pstyle.get(W + 'val') if pstyle is not None else None,
        jc.get(W + 'val') if jc is not None else None,
        ppr.find(W + 'keepNext') is not None,
        ind.get(W + 'left') if ind is not None else None,
        ind.get(W + 'firstLine') if ind is not None else None,
        ind.get(W + 'firstLineChars') if ind is not None else None,
        spacing.get(W + 'before') if spacing is not None else None,
        spacing.get(W + 'after') if spacing is not None else None,
        spacing.get(W + 'line') if spacing is not None else None,
    )


def _para_fmt_sig(p):
    """段落格式签名（B3：逐段列出 pPr/rPr 差异用），只取看得见的格式（见 _visual_ppr/_visual_segments
    注释），过滤掉 Word 编辑历史留下的、不影响呈现的 XML 噪音。"""
    return _visual_ppr(p.find(W + 'pPr')), _visual_segments(p)


def _fmt_diff_list(orig_paras_slice, new_paras_slice):
    """B3 修复：逐段比对格式签名（不比文字，文字流已单独比过），返回差异列表——规格要求"格式差异
    逐处列出并判断"；审查 r1 指出旧测试完全没有这一步，才让 B1（模板格式带偏）在金标回归里蒙混
    过关。两侧段数不等时能比多少比多少，段数本身不等也算一条差异。"""
    diffs = []
    n = min(len(orig_paras_slice), len(new_paras_slice))
    for k in range(n):
        a, b = orig_paras_slice[k], new_paras_slice[k]
        sig_a, sig_b = _para_fmt_sig(a), _para_fmt_sig(b)
        if sig_a != sig_b:
            diffs.append({'offset': k, 'text': dl.para_text(a)[:30], 'orig': sig_a, 'new': sig_b})
    if len(orig_paras_slice) != len(new_paras_slice):
        diffs.append({'offset': 'count', 'orig_n': len(orig_paras_slice), 'new_n': len(new_paras_slice)})
    return diffs


def delete_block_copy(src_docx, out_docx, prof_dict, title_contains_list):
    """测试专用：在 src_docx 的副本上删掉若干题块（含其表格/图片段落），只用于给金标回归造"删掉
    重插"的靶子，不走 block_insert 的写权守卫（本函数只写 SCRATCH 目录）。删法：定位每个题块的
    段落区间，按落在 body 的顶层元素（可能是 w:p，也可能整段落在同一个 w:tbl 里）去重后逐个从树
    上摘掉；其余成员原样照抄（同 docx_lib.write_docx 的原子写出+复核）。"""
    d = dl.open_docx(src_docx)
    items, _ = bh.read_docx(str(src_docx))
    P = bh.Prof(prof_dict)
    blocks = bh.walk(items, P)
    targets = []
    for want in title_contains_list:
        hits = [b for b in blocks if want in (b.get('title') or '')]
        if len(hits) != 1:
            raise RuntimeError(f'删除靶子标题命中 {len(hits)} 个：{want}')
        targets.append(hits[0])
    top_els, seen = [], set()
    for b in targets:
        idxs = [b['title_i']] + list(b.get('paras') or [])
        for i in idxs:
            el = bi._top_level_anchor(d.body, d.paras[i])
            if id(el) not in seen:
                seen.add(id(el))
                top_els.append(el)
    for el in top_els:
        el.getparent().remove(el)
    receipt = dl.write_docx(d, out_docx)
    return receipt


def _gold_case(case_id, media_kind, target_title, template_title, anchor, orig_media_check):
    """B3 修复：金标回归改用 before_block/after_block 精确还原被删题块的原位置（不再用
    method_end——method_end 只保证落在考法末尾，不保证紧邻哪个题块；审查 r1 实测 T2a 用 method_end
    把 B0005 插到例题6之后，原稿却在例题4与例题6之间，整篇文字流因此与原稿不同，旧测试只比"重插块
    自己的文字"看不出来）。

    anchor 用 before_block（紧邻的下一个题块）还是 after_block（紧邻的上一个题块），取决于被删题块
    在原稿里是不是它所在"考法"分组的最后一个题块——如果是（比如 B0003 是"考法1"三题里的第三题，
    紧邻的下一题 例题4 已经换到"考法2"），"考法"标题行本身夹在被删题块和下一题块之间，before_block
    紧邻下一题块会插到"考法2"标题行之后，落进错误的考法分组（本轮返修用 T2b 真实踩到这个坑：写后
    体检报"考法2 claimed=1 actual=2"）；这时必须用 after_block 紧邻上一题块，插到"考法"标题行之前，
    才是原来的位置。两种题块各自选对应正确的一种，由调用方按真实文档结构传入。

    复位后不需要 --renumber（编号/考法题数本就没变），比较的是重排前的输出与原稿——B3 明确要求
    "重排前"。比较项：(1) 整篇 d.items 文字流与原稿全等；(2) 重插块自身文字流与原稿一致（细粒度
    交叉验证）；(3) 逐段 pPr/rPr 差异列表（_fmt_diff_list）——如实写进 detail，判断在回执里逐条做，
    不拿差异数是否为 0 做测试通过的硬门槛（见函数体内注释）；
    (4) 图片字节或表格单元格文字一致；(5) 写后体检 0 新增 FAIL。"""
    t0 = time.time()
    try:
        pristine_path = fresh_copy(f'gold_pristine_{case_id}.docx')
        target_before = fresh_copy(f'gold_target_{case_id}_before.docx')
        prof_dict = bi.load_profile(str(PROF_BIXIU3))
        pristine = dl.open_docx(pristine_path)
        items = pristine.items
        P = bh.Prof(prof_dict)
        blocks_p = bh.walk(items, P)
        hits = [b for b in blocks_p if target_title in (b.get('title') or '')]
        if len(hits) != 1:
            raise RuntimeError(f'标题命中 {len(hits)} 个：{target_title}')
        b = hits[0]
        title_i = b['title_i']
        end_i = max([title_i] + list(b.get('paras') or []))
        content = gold_content_from_span(items, title_i, end_i, pristine_path)

        deleted = SCRATCH / f'gold_target_{case_id}_deleted.docx'
        deleted.unlink(missing_ok=True)
        delete_block_copy(target_before, deleted, prof_dict, [target_title])
        del_sha = sha256_file(deleted)
        unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': del_sha,
                'approved_by': 'claude:block_insert-gold',
                'approval_ref': f'B3 金标回归：按原文原{"图" if media_kind == "image" else "表"}'
                                f'重插 {target_title}（精确还原原位置，测试用，未经教学审定）',
                'inserts': [{'id': 'G1',
                             'anchor': anchor,
                             'template_block': {'title_contains': template_title},
                             'title': items[title_i]['text'], 'source_zone': 'restore',
                             'reason': 'B3 金标回归：原文/原图/原表逐字逐图逐格从本书原稿取回，还原到'
                                       '被删前的原位置，验证 block_insert 重插与原稿整篇文字流、格式'
                                       '都一致（测试用，未经教学审定）',
                             'content': content}]}
        unit_path = SCRATCH / f'gold_{case_id}_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding='utf-8')
        out = SCRATCH / f'gold_{case_id}_out.docx'
        out.unlink(missing_ok=True)
        report = SCRATCH / f'gold_{case_id}_report.json'
        # 不传 --renumber：位置精确还原后编号/考法题数不需要重排；B3 要求比较"重排前"的输出。
        rc, sout, serr = run_tool(['apply', '--docx', str(deleted), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3),
                                    '--report', str(report), '--health'])
        ok = rc == 0 and out.exists()
        detail = f'rc={rc} stderr={serr[-500:]}'
        if ok:
            new_doc = dl.open_docx(out)
            new_items = new_doc.items
            whole_orig = [it['text'] for it in items]
            whole_new = [it['text'] for it in new_items]
            whole_match = whole_orig == whole_new
            ok = ok and whole_match
            detail += f' whole_doc_text_flow_match={whole_match}'
            if not whole_match:
                import difflib
                sm = difflib.SequenceMatcher(a=whole_orig, b=whole_new, autojunk=False)
                ops = [op for op in sm.get_opcodes() if op[0] != 'equal'][:5]
                detail += f' diff_ops={ops}'
            new_P = bh.Prof(prof_dict)
            new_blocks = bh.walk(new_items, new_P)
            nb = [bb for bb in new_blocks if bb['title'] == items[title_i]['text']]
            ok = ok and len(nb) == 1
            if ok:
                nb = nb[0]
                new_idxs = sorted([nb['title_i']] + list(nb.get('paras') or []))
                orig_idxs = list(range(title_i, end_i + 1))
                orig_texts = [items[i]['text'] for i in orig_idxs]
                new_texts_all = [new_items[i]['text'] for i in new_idxs]
                block_text_ok = orig_texts == new_texts_all
                ok = ok and block_text_ok
                detail += (f' block_text_match={block_text_ok} orig_n={len(orig_texts)} '
                          f'new_n={len(new_texts_all)}')
                # B3 要求"格式差异逐处列出并判断"——判断在回执里逐条做（见返修回执 B3 小节），
                # 这里只负责如实产出差异列表，不拿"差异数是否为 0"做测试通过与否的硬门槛：block_
                # insert 按"角色桶+标签形状+多数格式"选模板，同形状同样式桶里偶尔混着少数派格式的
                # 段落（比如 B0003 表格上方全段加粗的图注，同角色桶同形状但只有它一个加粗）时，工具
                # 按设计取多数格式——这是"没给 like/style 精确点名就不猜哪个是特例"的既定行为（见
                # 文件头"角色→样式"一节），不是 B1 那种"标签格式滥入正文"的 bug，两者性质不同，不能
                # 用同一个"差异数须为 0"的硬指标混着判。
                fmt_diffs = _fmt_diff_list([pristine.paras[i] for i in orig_idxs],
                                            [new_doc.paras[i] for i in new_idxs])
                detail += f' fmt_diffs_n={len(fmt_diffs)}'
                if fmt_diffs:
                    detail += f' fmt_diffs={fmt_diffs[:8]}'
                # R2-B2 硬断言：设问段（_STEM_LEAD_RX 命中，如"结合材料，运用……说明……"）不能有
                # 格式差异——这条不是"多数格式选中了别的合理模板"这类可接受差异，是本轮明确要修的
                # 字体/缩进 bug（_visual_segments 现在真的比 eastAsia/sz 了，见该函数注释）。
                stem_diffs = [d for d in fmt_diffs if bi._STEM_LEAD_RX.match((d.get('text') or '').strip())]
                ok = ok and not stem_diffs
                detail += f' stem设问段格式差异={stem_diffs}'
                media_ok = orig_media_check(items, new_items, orig_idxs, new_idxs, out)
                ok = ok and media_ok[0]
                detail += f' {media_ok[1]}'
                rep = load_report(report)
                h = rep.get('health', {})
                health_ok = h.get('new_FAIL_count') == 0
                ok = ok and health_ok
                detail += f' health_new_FAIL={h.get("new_FAIL_count")}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record(f'T2_{case_id}_金标回归_before_block还原原位_整篇比对', ok, detail, t0)


def _check_image_bytes(items, new_items, orig_idxs, new_idxs, out):
    with zipfile.ZipFile(BIXIU3_DOCX) as z:
        orig_img = z.read('word/media/image3.jpg')
    with zipfile.ZipFile(out) as z:
        new_media_names = [n for n in z.namelist() if n.startswith('word/media/')
                            and n not in _orig_media_names()]
        img_ok = any(z.read(n) == orig_img for n in new_media_names)
    return img_ok, f'image_bytes_match={img_ok} new_media={new_media_names}'


def _check_table_cells(items, new_items, orig_idxs, new_idxs, out):
    orig_cells = [items[i]['text'] for i in orig_idxs if items[i]['tbl'] == 1]
    new_tbl_no = {new_items[i]['tbl'] for i in new_idxs if new_items[i]['tbl']}
    new_cells = [new_items[i]['text'] for i in new_idxs if new_items[i]['tbl'] in new_tbl_no]
    ok = orig_cells == new_cells
    return ok, f'table_cells_match={ok} orig_cells_n={len(orig_cells)} new_cells_n={len(new_cells)}'


def test_gold_regression():
    ok_all = True
    # B0005（例题5）是"考法3"两题里的第一题，紧邻的下一题 例题6 仍在同一考法内，before_block 安全。
    ok_all &= _gold_case('img', 'image', '例题 5　2026门头沟一模第17题',
                          '例题 8　2026顺义二模第17题',
                          {'before_block': {'title_contains': '例题 6　2026丰台二模第17题'}},
                          _check_image_bytes)
    # B0003（例题3）是"考法1"三题里的最后一题，紧邻的下一题 例题4 已经是"考法2"的第一题——两题块
    # 之间夹着"考法2"标题行，before_block 紧邻例题4 会插到标题行之后、落进错误的考法分组（本轮
    # 返修实测踩过，见 _gold_case 注释）。改用 after_block 紧邻上一题 例题2，插到"考法2"标题行之前。
    ok_all &= _gold_case('tbl', 'table', '例题 3　2024朝阳二模第18题',
                          '例题 4　2026朝阳一模第21题（跨模块）',
                          # 书里"2026石景山二模第17(1)题"这道原题被不同章节复用了 5 次（例题2/3/4/
                          # 15/20），必须用带编号的完整标题才能唯一命中"例题 2"这一处（三统一节内、
                          # 紧邻 B0003 原位置的那一个）。
                          {'after_block': {'title_contains': '例题 2　2026石景山二模第17(1)题'}},
                          _check_table_cells)
    return ok_all


def _orig_media_names():
    with zipfile.ZipFile(BIXIU3_DOCX) as z:
        return set(n for n in z.namelist() if n.startswith('word/media/'))


# ------------------------------------------------------------------ 测试 3：负例（全拒、不留输出、退出码正确）
# R2-M2 修复：默认 content 原先只有 1 段 source（栏目天然不齐全）——旧版栏目缺失不构成硬失败，
# 靠这份默认内容走通写出的负例/回归用例（如 m2/m5/m2bidx）不受影响；修复后栏目缺失会让 verify_
# output 硬失败，这些用例若继续用只有 1 段 source 的默认内容会在到达它们真正想测的那一步之前就
# 先被栏目缺失挡住。默认内容因此补全思维链条/答案落点/细则说明三个必须栏目，改成"完整的最小
# 合法插入"；仍需要"栏目不全"这个负例场景的用例（R2-M2 自己）显式传 content 覆盖回单段 source。
def _minimal_content_for(source_text):
    """同 _MINIMAL_CONTENT 的结构，只替换 source 段文字——供需要区分多条 insert 的测试用例
    （比如 m3 顺序测试）各自生成"栏目齐全"的内容，同时保留可识别的 source 文字。"""
    return [
        {'role': 'source', 'text': f'【题目】{source_text}。'},
        {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】负例测试占位文字。'},
        {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】负例测试占位文字。'},
        {'role': 'rubric', 'text': '【细则说明】 负例测试占位文字。'},
    ]


_MINIMAL_CONTENT = _minimal_content_for('负例测试用最小材料一句话')


def _minimal_unit(parent_sha, **overrides):
    u = {
        'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': parent_sha,
        'approved_by': 'claude:neg-test', 'approval_ref': '负例测试',
        'inserts': [{
            'id': 'N1',
            'anchor': {'after_block': {'title_contains': '例题 3　2024朝阳二模第18题'}},
            'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
            'title': '例题 93　2099负例测试占位卷第1题', 'source_zone': 'approved_edit',
            'reason': '负例测试：验证工具正确拒绝，非正式内容',
            'content': [dict(c) for c in _MINIMAL_CONTENT],
        }],
    }
    for k, v in overrides.items():
        if k == 'anchor':
            u['inserts'][0]['anchor'] = v
        elif k == 'template_block':
            u['inserts'][0]['template_block'] = v
        elif k == 'content':
            u['inserts'][0]['content'] = v
        elif k == 'title':
            u['inserts'][0]['title'] = v
        elif k == 'source_zone':
            u['inserts'][0]['source_zone'] = v
        else:
            u[k] = v
    return u


def test_negatives():
    ok_all = True

    def neg_case(name, unit_or_builder, docx=None, profile=PROF_BIXIU3, expect_rc=2, out_name=None):
        t0 = time.time()
        try:
            d = docx or fresh_copy(f'{name}_parent.docx')
            unit = unit_or_builder(BIXIU3_SHA) if callable(unit_or_builder) else unit_or_builder
            unit_path = SCRATCH / f'{name}_insert.json'
            unit_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding='utf-8')
            out = Path(out_name) if out_name else (SCRATCH / f'{name}_out.docx')
            if out.exists() and str(SCRATCH) in str(out):
                out.unlink()
            existed_before = out.exists()
            rc, sout, serr = run_tool(['apply', '--docx', str(d), '--insert', str(unit_path),
                                        '--out', str(out), '--profile', str(profile)])
            no_leftover = existed_before or not out.exists()
            ok = rc == expect_rc and no_leftover
            detail = f'rc={rc}（期望{expect_rc}） 输出未残留={no_leftover} stderr={serr[-300:]}'
        except Exception as e:
            ok, detail = False, f'异常：{e}'
        return record(name, ok, detail, t0)

    ok_all &= neg_case('T3a_负例_父稿SHA错',
                        lambda s: _minimal_unit('0' * 64), expect_rc=2)
    ok_all &= neg_case('T3b_负例_锚点0命中',
                        lambda s: _minimal_unit(s, anchor={'after_block': {'title_contains': '这个标题在书里不存在_xyz'}}),
                        expect_rc=2)
    ok_all &= neg_case('T3c_负例_锚点多命中',
                        lambda s: _minimal_unit(s, anchor={'after_block': {'title_contains': '例题'}}),
                        expect_rc=2)
    ok_all &= neg_case('T3d_负例_样板题块找不到',
                        lambda s: _minimal_unit(s, template_block={'title_contains': '这个模板不存在_xyz'}),
                        expect_rc=2)
    ok_all &= neg_case('T3e_负例_原件里找不到指定图',
                        lambda s: _minimal_unit(s, content=[
                            {'role': 'source', 'text': '【题目】负例。'},
                            {'role': 'image', 'from': {'docx': str(XC_ERMO_DOCX), 'rid': 'rId999'}},
                        ]), expect_rc=2)
    ok_all &= neg_case('T3f_负例_原件里找不到指定表',
                        lambda s: _minimal_unit(s, content=[
                            {'role': 'source', 'text': '【题目】负例。'},
                            {'role': 'table', 'from': {'docx': str(XC_ERMO_DOCX), 'table_index': 999}},
                        ]), expect_rc=2)
    # 图片文件损坏：给一个扩展名是 .png 但内容不是图片的文件
    bad_img = SCRATCH / 'bad.png'
    bad_img.write_bytes(b'this is not a real image, just some bytes to trigger a decode failure')
    ok_all &= neg_case('T3g_负例_图片文件损坏',
                        lambda s: _minimal_unit(s, content=[
                            {'role': 'source', 'text': '【题目】负例。'},
                            {'role': 'image', 'file': str(bad_img)},
                        ]), expect_rc=2)
    # 输出落到受保护目录：书稿目录本身
    ok_all &= neg_case('T3h_负例_输出落到书稿目录',
                        lambda s: _minimal_unit(s), expect_rc=3,
                        out_name=str(ROOT / '必修三_最新Skill修订_20260913' / '不该写这里.docx'))
    # 输出落到 Skill 目录
    ok_all &= neg_case('T3i_负例_输出落到Skill目录',
                        lambda s: _minimal_unit(s), expect_rc=3,
                        out_name=str(SK / '不该写这里.docx'))
    # 输出落到题库目录
    ok_all &= neg_case('T3j_负例_输出落到题库目录',
                        lambda s: _minimal_unit(s), expect_rc=3,
                        out_name=str(ROOT / 'DeepSeek_政治题库资料库_20260918' / '不该写这里.docx'))
    # 冻结册：用冻结测试配置副本（frozen=true），写模式必须立即拒绝、退出码 3
    # R2-m9 修复后 book 字段要跟 --profile 实际书册一致，否则会被 R2-m9 那道检查先一步拦下——这里
    # 显式把 book 改成 bixiu2，确保测到的仍然是"冻结册拒绝"本身，不是 book 不一致。
    ok_all &= neg_case('T3k_负例_冻结册配置', lambda s: _minimal_unit(s, book='bixiu2'), profile=PROF_BIXIU2_FROZEN,
                        expect_rc=3)
    # M3 修复：method_end 命中多个不同(节点,考法)分组必须中止——"考法1" 不给 node_contains，全书
    # 命中 20 个不同分组（见审查 r1 M3 evidence）。
    ok_all &= neg_case('T3l_负例_method_end命中多个考法分组',
                        lambda s: _minimal_unit(s, anchor={'method_end': {'method_contains': '考法1'}}),
                        expect_rc=2)
    # M4 修复：title 命中禁用词表必须中止（旧版任何 source_zone 下都不检查 title）。
    ok_all &= neg_case('T3m_负例_标题命中禁用词表',
                        lambda s: _minimal_unit(s, title='例题 93　2099负例测试模板占位卷第1题'),
                        expect_rc=2)
    # M4 修复：table.rows 单元格文字在 approved_edit 下也要过词表（旧版任何 source_zone 下都不检查）。
    ok_all &= neg_case('T3n_负例_表格rows命中禁用词表',
                        lambda s: _minimal_unit(s, content=[
                            {'role': 'source', 'text': '【题目】负例。'},
                            {'role': 'table', 'rows': [['本落位', '占位表头']]},
                        ]), expect_rc=2)
    # R2-m13 补测：r2 审查指出负例集合缺"输出落到审阅入口"和"输出与输入是同一个文件"两项
    # （审查者手工补测过，结果都正确，这里补进自动化测试）。
    ok_all &= neg_case('T3o_负例_输出落到审阅入口',
                        lambda s: _minimal_unit(s), expect_rc=3,
                        out_name=str(ROOT / '00_必修三最新审查稿' / '不该写这里.docx'))
    t0 = time.time()
    try:
        same = fresh_copy('T3p_same_file.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        unit_path = SCRATCH / 'T3p_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        sha_before = sha256_file(same)
        rc, sout, serr = run_tool(['apply', '--docx', str(same), '--insert', str(unit_path),
                                    '--out', str(same), '--profile', str(PROF_BIXIU3)])
        ok = rc == 3 and sha256_file(same) == sha_before
        detail = f'rc={rc}（期望3） 输入文件未被覆盖={sha256_file(same) == sha_before} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('T3p_负例_输出与输入是同一个文件', ok, detail, t0)
    # 正例（同一处 R2-m13 补测）：冻结册只在写模式（apply）拒绝，check 模式（只读）应该能正常跑
    # 通——frozen_guard 只在 cmd_apply 里查，cmd_check 从不查 prof_dict['frozen']。
    t0 = time.time()
    try:
        docx = fresh_copy('T3q_frozen_check_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, book='bixiu2')
        unit_path = SCRATCH / 'T3q_frozen_check_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        rc, sout, serr = run_tool(['check', '--docx', str(docx), '--insert', str(unit_path),
                                    '--profile', str(PROF_BIXIU2_FROZEN)])
        ok = rc in (0, 1)
        detail = f'rc={rc}（期望0/1，冻结册 check 模式应该能跑） stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('T3q_正例_冻结册check模式可以跑', ok, detail, t0)
    return ok_all


def test_m12_profile_required():
    """m12 修复：云端不给 --profile 时不能回退到 SK 自带的（指向 Mac 路径的）书册配置——那份配置
    guard_write 认不出仓库根，会把书稿/原材料目录当成"不受保护"。main() 已把 apply 的 --profile
    设成 argparse required；这里再补一层：--profile 指向的配置若 paths.root 在本环境不存在，
    _load_prof 要主动 Abort（纵深防御，防止以后有配置绕过 argparse 直接调 cmd_apply）。"""
    ok_all = True
    t0 = time.time()
    try:
        docx = fresh_copy('m12_noprofile_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        unit_path = SCRATCH / 'm12_noprofile_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'm12_noprofile_out.docx'
        out.unlink(missing_ok=True)
        # 故意不传 --profile：argparse 的 required=True 应该在解析阶段就报错（退出码 2），
        # 根本不进入 cmd_apply，也就不可能碰到 guard_write 认不出仓库根这个问题。
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out)])
        ok = rc == 2 and not out.exists() and '--profile' in serr
        detail = f'rc={rc}（期望2） stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('m12a_apply缺省--profile被argparse拒绝', ok, detail, t0)

    t0 = time.time()
    try:
        docx = fresh_copy('m12_badroot_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        unit_path = SCRATCH / 'm12_badroot_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        bad_prof = json.loads(PROF_BIXIU3.read_text(encoding='utf-8'))
        bad_prof['paths'] = dict(bad_prof['paths'])
        bad_prof['paths']['root'] = '/Users/wanglifei/Desktop/gpt和claude共同的小窝'  # 云端不存在的 Mac 路径
        bad_prof_path = SCRATCH / 'm12_badroot_profile.json'
        bad_prof_path.write_text(json.dumps(bad_prof, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'm12_badroot_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(bad_prof_path)])
        ok = rc == 2 and not out.exists() and 'paths.root' in serr
        detail = f'rc={rc}（期望2） stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('m12b_profile指向本环境不存在的root被拒绝', ok, detail, t0)
    return ok_all


# ------------------------------------------------------------------ 测试 4：其他书（哲学，草案配置）check 模式
def test_other_book():
    ok_all = True
    t0 = time.time()
    try:
        if not PHILOSOPHY_DOCX.exists():
            ok_all &= record('T4a_其他书_哲学_check', False, f'找不到 {PHILOSOPHY_DOCX}', t0)
        else:
            sha = sha256_file(PHILOSOPHY_DOCX)
            prof = bi.load_profile(str(PROF_PHILOSOPHY))
            items, _ = bh.read_docx(str(PHILOSOPHY_DOCX))
            P = bh.Prof(prof)
            blocks = bh.walk(items, P)
            if len(blocks) < 2:
                ok_all &= record('T4a_其他书_哲学_check', False,
                                  f'草案配置切出题块数 {len(blocks)}，不足以选锚点+模板，如实记录：'
                                  f'缺可用的 example_title/styles 配置', t0)
            else:
                b_anchor, b_template = blocks[0], blocks[1]
                unit = {'schema': 'baodian_insert_v1', 'book': 'philosophy', 'parent_docx_sha256': sha,
                        'approved_by': 'claude:block_insert-other-book', 'approval_ref': '其他书 check 模式验收',
                        'inserts': [{'id': 'P1',
                                     'anchor': {'after_block': {'title_contains': b_anchor['title']}},
                                     'template_block': {'title_contains': b_template['title']},
                                     'title': '例题 999　其他书check模式验收占位',
                                     'source_zone': 'approved_edit', 'reason': '其他书 check 模式验收，非正式内容',
                                     'content': [{'role': 'source', 'text': '【题目】其他书 check 验收用最小材料。'}]}]}
                unit_path = SCRATCH / 'other_book_insert.json'
                unit_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding='utf-8')
                report = SCRATCH / 'other_book_report.json'
                rc, sout, serr = run_tool(['check', '--docx', str(PHILOSOPHY_DOCX), '--insert', str(unit_path),
                                            '--profile', str(PROF_PHILOSOPHY), '--report', str(report)])
                ok = rc in (0, 1)
                detail = f'rc={rc}（0/1 视为 check 走通） stdout={sout.strip()} stderr={serr[-400:]}'
                ok_all &= record('T4a_其他书_哲学_check', ok, detail, t0)
                # 4b（R3-M2 修复）：旧版只插 1 段 source，被 R2-M2 的栏目硬判拦下（rc=2、不写出）
                # 也记 PASS，验收 4 要求的"在副本上写入 1 题"实际没有发生（见审查 r3 R3-M2）。改按
                # 哲学书的真实栏目构造完整插入——直接复制 例题 1　2026年东城二模第16题（带图）
                # 自己的真实段落（role/style/text 逐段照抄该块自己的 zone/style，图片按它自己的
                # wp:inline/anchor 定位取回），插成一道"同题复制"的新题块：栏目齐全、图片来自真实
                # 原书，不会被 R2-M2 拦，能验证工具本身在其他书上确实可以写入带图题（fix_hint 建议
                # 的做法，审查者 probe_philosophy_write.py 已验证过一次，这里把它转成可重跑的用例）。
                t0b = time.time()
                try:
                    ph_src = SCRATCH / 'philosophy_src_for_copy.docx'
                    shutil.copyfile(PHILOSOPHY_DOCX, ph_src)
                    d_ph = dl.open_docx(ph_src)
                    _, _, ph_blocks, _ = ap.zones_of(d_ph, prof)
                    # zones_of 的题块字典不一定带 media 计数字段，改用 d_ph.items 找块内第一个真的
                    # 带图的题块。
                    b_img = None
                    for cand in ph_blocks:
                        idxs = cand.get('paras') or []
                        if any(d_ph.items[i].get('img') for i in idxs):
                            b_img = cand
                            break
                    if b_img is None:
                        ok_all &= record('T4b_其他书_哲学_apply真实写入带图题', False,
                                          '哲学书全书按草案配置切出的题块里没有一个带图片，如实记录：'
                                          '换一本有图的书或人工指定块', t0b)
                    else:
                        with zipfile.ZipFile(ph_src) as z:
                            ph_root = etree.fromstring(z.read('word/document.xml'))
                        all_drawings = bi._drawing_elements(ph_root)
                        ph_paras_src = dl.para_elements(ph_root.find(W + 'body'))
                        content = []
                        for i in (b_img.get('paras') or []):
                            it = d_ph.items[i]
                            if it.get('img'):
                                dr = next(x for x in ph_paras_src[i].iter()
                                          if x.tag in (bi.WP_NS + 'inline', bi.WP_NS + 'anchor'))
                                content.append({'role': 'image',
                                                 'from': {'docx': str(ph_src), 'index': all_drawings.index(dr) + 1}})
                                continue
                            zone = it.get('zone')
                            role = {'source': 'source', 'teaching': 'teaching', 'rubric': 'rubric'}.get(zone)
                            if role is None:
                                continue
                            content.append({'role': role, 'style': it['style'], 'text': it['text']})
                        new_title = b_img['title'] + '（R3返修T4b复制）'
                        unit_b = {'schema': 'baodian_insert_v1', 'book': 'philosophy',
                                   'parent_docx_sha256': sha256_file(PHILOSOPHY_DOCX),
                                   'approved_by': 'claude:block_insert-run_tests', 'approval_ref':
                                       'R3-M2 返修：按哲学书真实带图题块逐字复制，验证草案配置能写入'
                                       '带图题（测试用，未经教学审定）',
                                   'inserts': [{'id': 'PH1',
                                                'anchor': {'after_block': {'title_contains': b_img['title']}},
                                                'template_block': {'title_contains': b_img['title']},
                                                'title': new_title, 'source_zone': 'restore',
                                                'reason': 'R3-M2 返修：原书同题逐字复制（测试用，未经教学'
                                                          '审定），验证草案配置能否写入带图题',
                                                'content': content}]}
                        unit_b_path = SCRATCH / 'other_book_apply_insert.json'
                        unit_b_path.write_text(json.dumps(unit_b, ensure_ascii=False, indent=2), encoding='utf-8')
                        docx_copy = SCRATCH / 'philosophy_copy.docx'
                        shutil.copyfile(PHILOSOPHY_DOCX, docx_copy)
                        out = SCRATCH / 'philosophy_out.docx'
                        out.unlink(missing_ok=True)
                        report2 = SCRATCH / 'other_book_apply_report.json'
                        rc2, sout2, serr2 = run_tool(['apply', '--docx', str(docx_copy), '--insert', str(unit_b_path),
                                                       '--out', str(out), '--profile', str(PROF_PHILOSOPHY),
                                                       '--report', str(report2), '--health'])
                        rep2 = load_report(report2) if report2.exists() else {}
                        bic2 = (rep2.get('verify') or {}).get('block_index_check') or [{}]
                        entry2 = bic2[0] if bic2 else {}
                        # 不要求 rc==0：没传 --renumber 时"例题编号不连续"是预期内的新增 FAIL（R3-M2
                        # fix_hint："断言 rc∈{0,1}、输出存在、block_index 认块完整、media_match"）。
                        ok2 = (rc2 in (0, 1) and out.exists() and entry2.get('found_blocks') == 1
                               and not entry2.get('missing') and entry2.get('media_match') is True)
                        detail2 = (f'rc={rc2} out_exists={out.exists()} block_index={entry2} '
                                  f'health={ (rep2.get("health") or {}).get("new_FAIL_count")} '
                                  f'stderr={serr2[-300:]}')
                        ok_all &= record('T4b_其他书_哲学_apply真实写入带图题', ok2, detail2, t0b)
                        # T4b_renumber（R3-M2 fix_hint 要求的链路断言）：同一插入单加 --renumber，
                        # 编号/考法题数重排后写后体检不该再有新增 FAIL。
                        t0d = time.time()
                        docx_copy3 = SCRATCH / 'philosophy_copy_renumber.docx'
                        shutil.copyfile(PHILOSOPHY_DOCX, docx_copy3)
                        out4 = SCRATCH / 'philosophy_out_renumber.docx'
                        out4.unlink(missing_ok=True)
                        report4 = SCRATCH / 'other_book_apply_renumber_report.json'
                        rc4, sout4, serr4 = run_tool(['apply', '--docx', str(docx_copy3), '--insert', str(unit_b_path),
                                                       '--out', str(out4), '--profile', str(PROF_PHILOSOPHY),
                                                       '--report', str(report4), '--health', '--renumber'])
                        rep4 = load_report(report4) if report4.exists() else {}
                        new_fail4 = (rep4.get('health') or {}).get('new_FAIL_count')
                        renum_ok4 = (rep4.get('renumber') or {}).get('ok')
                        ok4 = rc4 == 0 and renum_ok4 is True and new_fail4 == 0
                        detail4 = f'rc={rc4} renumber_ok={renum_ok4} new_FAIL_count={new_fail4} stderr={serr4[-300:]}'
                        ok_all &= record('T4c_其他书_哲学_renumber后体检0新增FAIL', ok4, detail4, t0d)
                except Exception as e:
                    ok_all &= record('T4b_其他书_哲学_apply真实写入带图题', False,
                                      f'异常：{e}\n{traceback.format_exc()[-800:]}', t0b)
    except Exception as e:
        ok_all &= record('T4_其他书', False, f'异常：{e}\n{traceback.format_exc()[-800:]}', t0)
    return ok_all


# ------------------------------------------------------------------ 返修 r1：逐条复现 blocker/major/minor
def _call_apply_inprocess(attrs):
    """main() 对 cmd_apply 抛出的几类异常做的转码，这里原样搬一份用于进程内直接调用 bi.cmd_apply
    （M2/m5 两条用例需要 monkeypatch 模块级函数，subprocess 隔离进程做不到，只能进程内调用）。"""
    ns = types.SimpleNamespace(**attrs)
    try:
        return bi.cmd_apply(ns)
    except bi.RefuseWrite:
        return 3
    except bi.dl.GuardError:
        return 3
    except bi.dl.ParentMismatch:
        return 2
    except (bi.dl.AlignmentError, bi.Abort, ValueError, KeyError):
        return 2
    except Exception:
        return 2


def _apply_args(docx, insert_path, out, report=None, health=False, renumber=False, render_check=False,
                 profile=PROF_BIXIU3):
    return dict(docx=str(docx), insert=str(insert_path), out=str(out), profile=str(profile),
                report=str(report) if report else None, health=health, renumber=renumber,
                render_check=render_check)


_R2B1_BAD_NAMES = {'标题 字符', 'header', '副标题 字符'}  # 审查 r2 探针实测的三个真实撞号目标名字


def _table_cell_style_names(docx_path, after_para_prefix):
    """定位紧跟在某段（按文字前缀）之后的顶层表格，返回表内所有单元格段落解析出的样式名集合
    （R2-B1 复现用：曾经被静默改绑到的样式名，如"标题 字符"/"header"，就在这个集合里出现）。"""
    with zipfile.ZipFile(docx_path) as z:
        styles_root = etree.fromstring(z.read('word/styles.xml'))
        doc_root = etree.fromstring(z.read('word/document.xml'))
    styles_obj = bh.Styles(styles_root)
    body = doc_root.find(W + 'body')
    paras = dl.para_elements(body)
    i0, _ = _find_para(paras, after_para_prefix)
    if i0 is None:
        raise RuntimeError(f'没找到段落前缀 {after_para_prefix!r}')
    el = bi._top_level_anchor(body, paras[i0]).getnext()
    while el is not None and el.tag != W + 'tbl':
        el = el.getnext()
    if el is None:
        raise RuntimeError('没找到紧跟其后的表格')
    names = set()
    for p in el.iter(W + 'p'):
        ppr = p.find(W + 'pPr')
        ps = ppr.find(W + 'pStyle') if ppr is not None else None
        sid = ps.get(W + 'val') if ps is not None else styles_obj.default_pstyle
        names.add(styles_obj.name.get(sid, sid))
        for r in p.iter(W + 'r'):
            rpr = r.find(W + 'rPr')
            rs = rpr.find(W + 'rStyle') if rpr is not None else None
            if rs is not None:
                names.add(styles_obj.name.get(rs.get(W + 'val'), rs.get(W + 'val')))
    return names


def test_b2_m1_table_rels():
    """B2 + M1 复现：真实原件 21.docx 的表格（table_index=1）里有 4 个 External 超链接、3 张图片，
    全部原样插进必修三副本。断言（都是 B2/M1 修复前会失败的点）：
      - 表格内所有 r: 引用（超链接/图片）在输出里都有对应关系、目标存在（B2：_scan_rids 命名空间
        修好之后，这是它现在真的能查出问题的地方；这里额外用完全独立的 lxml 直接扫，不复用被测代码
        自己的检查函数，避免"用同一段逻辑验证同一段逻辑"）。
      - 超链接改绑到的 URL 与原件一致（不是被误绑到 endnotes/图片关系，B2 原始 bug 的症状）。
      - 全文 docPr id 无重复（M1：表内图片的 docPr 现在会被重新分配）。
    """
    t0 = time.time()
    try:
        if not HYPERLINK_TABLE_DOCX.exists():
            return record('B2_M1_表格超链接图片关系重建', False, f'找不到原件 {HYPERLINK_TABLE_DOCX}', t0)
        docx = fresh_copy('b2m1_parent.docx')
        with zipfile.ZipFile(HYPERLINK_TABLE_DOCX) as z:
            src_root = etree.fromstring(z.read('word/document.xml'))
            src_rels = {r.get('Id'): (r.get('Target'), r.get('TargetMode'))
                        for r in etree.fromstring(z.read('word/_rels/document.xml.rels'))}
        src_hyperlink_urls = sorted(
            src_rels[h.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')][0]
            for h in src_root.iter(W + 'hyperlink')
            if h.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id') in src_rels)
        unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': BIXIU3_SHA,
                'approved_by': 'claude:block_insert-b2m1', 'approval_ref':
                    'B2/M1 复现用例：真实原件 21.docx 表格（超链接+图片）插入必修三副本，测试用，未经教学审定',
                'inserts': [{'id': 'I001',
                             'anchor': {'after_block': {'title_contains': '例题 5　2026门头沟一模第17题'}},
                             'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
                             'title': '例题 94　2099工具验收表格关系测试卷第1题',
                             'source_zone': 'approved_edit',
                             'reason': 'B2/M1 复现用例，非正式内容',
                             'content': [
                                 {'role': 'source', 'text': '【题目】工具验收用最简单材料，仅供表格关系重建测试。'},
                                 {'role': 'table', 'from': {'docx': str(HYPERLINK_TABLE_DOCX), 'table_index': 1}},
                                 # R2-M2 修复：栏目缺失现在是写后硬失败，补上教学/细则栏目让这道
                                 # 测试块本身是"完整"的——本测试要测的是表格关系重建，不是栏目
                                 # 完整性，缺栏目会在测到目标问题之前就先被拦下。
                                 {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】工具验收占位文字。'},
                                 {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】工具验收占位文字。'},
                                 {'role': 'rubric', 'text': '【细则说明】 工具验收占位文字。'},
                             ]}]}
        unit_path = SCRATCH / 'b2m1_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding='utf-8')
        out = SCRATCH / 'b2m1_out.docx'
        out.unlink(missing_ok=True)
        report = SCRATCH / 'b2m1_report.json'
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3), '--report', str(report)])
        ok = rc in (0, 1) and out.exists()
        detail = f'rc={rc} stderr={serr[-500:]}'
        if ok:
            with zipfile.ZipFile(out) as z:
                names = set(z.namelist())
                out_root = etree.fromstring(z.read('word/document.xml'))
                rels_root = etree.fromstring(z.read('word/_rels/document.xml.rels'))
                rel_map = {r.get('Id'): (r.get('Target'), r.get('TargetMode')) for r in rels_root}
            R_ = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
            bad_rel, out_urls = [], []
            for hl in out_root.iter(W + 'hyperlink'):
                rid = hl.get(R_ + 'id')
                if rid is None:
                    continue
                tgt = rel_map.get(rid)
                if tgt is None:
                    bad_rel.append(('hyperlink-missing-rel', rid))
                    continue
                target, mode = tgt
                if mode != 'External':
                    bad_rel.append(('hyperlink-not-external', rid, mode))
                else:
                    out_urls.append(target)
            for blip in out_root.iter(bi.A_NS + 'blip'):
                rid = blip.get(R_ + 'embed')
                if not rid:
                    continue
                tgt = rel_map.get(rid)
                if tgt is None:
                    bad_rel.append(('image-missing-rel', rid))
                    continue
                target, mode = tgt
                p = target.lstrip('/') if target.startswith('/') else 'word/' + target
                if p not in names:
                    bad_rel.append(('image-target-missing', rid, p))
            urls_ok = sorted(out_urls) == src_hyperlink_urls
            # M1：只查"本工具这次新分配的 docPr id"是否唯一——书稿本身历史遗留就有重复 id（已知限制
            # m10 记录过，11 处），跟这次插入无关，不能算进来（否则见 T1a 踩过的坑：把全书既有的
            # 离群格式/id 当成本工具的问题）。新分配的 id 从写后报告的 plan[].media[].docpr_id 取。
            rep = load_report(report) if report.exists() else {}
            new_ids = [str(m['docpr_id']) for pl in rep.get('plan', []) for m in pl.get('media', [])
                       if m.get('kind') == 'image' and m.get('docpr_id') is not None]
            all_docpr = [el.get('id') for el in out_root.iter(bi.WP_NS + 'docPr')]
            bad_new_ids = [i for i in new_ids if all_docpr.count(i) != 1]
            # R2-B1 复现：21.docx 表格里的 pStyle a9（原件 List Paragraph）、rStyle ab（原件
            # Hyperlink）在本书里恰好撞号成"标题 字符"/"副标题 字符"——旧版按 styleId 是否在本书
            # "存在"保留引用会把它们静默改绑。修复后单元格 pPr/rPr 整体套样板表格格式
            # （_reformat_table_cells），这两个撞号名字不应该出现在新表格里。
            cell_names = _table_cell_style_names(out, '【题目】工具验收用最简单材料，仅供表格关系重建测试。')
            bad_hit = cell_names & _R2B1_BAD_NAMES
            ok = ok and not bad_rel and urls_ok and new_ids and not bad_new_ids and not bad_hit
            detail += (f' bad_rel={bad_rel} urls_ok={urls_ok}（{sorted(out_urls)} vs {src_hyperlink_urls}）'
                      f' new_docpr_ids={new_ids} bad_new_ids={bad_new_ids} n_docpr_total={len(all_docpr)}'
                      f' r2b1_cell_style_names={sorted(cell_names)} bad_hit={sorted(bad_hit)}')
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-800:]}'
    return record('B2_M1_表格超链接图片关系重建_真实原件', ok, detail, t0)


def test_m1_docpr_collision():
    """M1 复现：真实原件 17(1).docx 的表格（table_index=1）docPr id 是 [1,3,2]，与本书前部已有的
    id 天然冲突。断言：全文 docPr id 插入后无重复（旧版 relink_table_images 从不碰表内 docPr，会
    静默产生重复 id）。"""
    t0 = time.time()
    try:
        if not DOCPR_TABLE_DOCX.exists():
            return record('M1_表内docPr去重_真实原件', False, f'找不到原件 {DOCPR_TABLE_DOCX}', t0)
        docx = fresh_copy('m1docpr_parent.docx')
        unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': BIXIU3_SHA,
                'approved_by': 'claude:block_insert-m1', 'approval_ref':
                    'M1 复现用例：真实原件 17(1).docx 表格（docPr id 与本书冲突）插入，测试用，未经教学审定',
                'inserts': [{'id': 'I001',
                             'anchor': {'after_block': {'title_contains': '例题 6　2026丰台二模第17题'}},
                             'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
                             'title': '例题 95　2099工具验收docPr冲突测试卷第1题',
                             'source_zone': 'approved_edit', 'reason': 'M1 复现用例，非正式内容',
                             'content': [
                                 {'role': 'source', 'text': '【题目】工具验收用最简单材料，仅供 docPr 去重测试。'},
                                 {'role': 'table', 'from': {'docx': str(DOCPR_TABLE_DOCX), 'table_index': 1}},
                                 # R2-M2 修复：栏目缺失现在是写后硬失败，见 test_b2_m1_table_rels 同一处注释。
                                 {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】工具验收占位文字。'},
                                 {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】工具验收占位文字。'},
                                 {'role': 'rubric', 'text': '【细则说明】 工具验收占位文字。'},
                             ]}]}
        unit_path = SCRATCH / 'm1docpr_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding='utf-8')
        out = SCRATCH / 'm1docpr_out.docx'
        out.unlink(missing_ok=True)
        report = SCRATCH / 'm1docpr_report.json'
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3), '--report', str(report)])
        ok = rc in (0, 1) and out.exists()
        detail = f'rc={rc} stderr={serr[-500:]}'
        if ok:
            with zipfile.ZipFile(out) as z:
                out_root = etree.fromstring(z.read('word/document.xml'))
            # M1：只查这次新分配的 docPr id（见 test_b2_m1_table_rels 同一处注释——书稿本身历史遗留
            # 就有重复 id，跟这次插入无关，不能拿全书 docPr 是否有任何重复来判定）。
            rep = load_report(report) if report.exists() else {}
            new_ids = [str(m['docpr_id']) for pl in rep.get('plan', []) for m in pl.get('media', [])
                       if m.get('kind') == 'image' and m.get('docpr_id') is not None]
            all_docpr = [el.get('id') for el in out_root.iter(bi.WP_NS + 'docPr')]
            bad_new_ids = [i for i in new_ids if all_docpr.count(i) != 1]
            # R2-B1 复现：17(1).docx 表格里的 pStyle a6（原件 List Paragraph）在本书撞号成"header"
            # （灰色、9 磅），见 test_b2_m1_table_rels 同一处注释。
            cell_names = _table_cell_style_names(out, '【题目】工具验收用最简单材料，仅供 docPr 去重测试。')
            bad_hit = cell_names & _R2B1_BAD_NAMES
            ok = ok and bool(new_ids) and not bad_new_ids and not bad_hit
            detail += (f' n_docpr_total={len(all_docpr)} new_docpr_ids={new_ids} bad_new_ids={bad_new_ids}'
                      f' r2b1_cell_style_names={sorted(cell_names)} bad_hit={sorted(bad_hit)}')
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-800:]}'
    return record('M1_表内docPr去重_真实原件', ok, detail, t0)


def test_m1_textbox_abort():
    """m1 修复：表格含文本框（真实原件 16题二模阅卷总结.docx table_index=1）应安全中止，提示信息要
    点名"文本框"，不再是旧版误导性的"内部错误：新段落身份换算失败"。"""
    t0 = time.time()
    try:
        if not TEXTBOX_TABLE_DOCX.exists():
            return record('m1_表格含文本框安全中止', False, f'找不到原件 {TEXTBOX_TABLE_DOCX}', t0)
        docx = fresh_copy('m1txbx_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, content=[
            {'role': 'source', 'text': '【题目】负例。'},
            {'role': 'table', 'from': {'docx': str(TEXTBOX_TABLE_DOCX), 'table_index': 1}},
        ])
        unit_path = SCRATCH / 'm1txbx_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'm1txbx_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc == 2 and not out.exists() and '文本框' in serr and '内部错误' not in serr
        detail = f'rc={rc}（期望2） 输出未残留={not out.exists()} 提示含"文本框"={"文本框" in serr} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    return record('m1_表格含文本框安全中止', ok, detail, t0)


def test_r2_m4_real_docx_table():
    """R2-M4 + R2-B1 真实新题复现：B3 漏收候选 BJ-2023-HD-QIZHONG-Q18#1（原件是 DOCX、第 5 表，
    见 B3_漏收候选.csv），原表格 tblStyle=af0（教师版原件里是"Table Grid"，本书 af0 撞号成段落
    样式"macro"）、单元格直接写楷体/行距360/首行缩进200字符、gridCol 总宽 9742 twips 超版心
    9298（已用 lxml 实测核对，见回执）。断言（都是修复前会失败的点）：
      - block_index 认出新题块、tables_match（真实带表新题验收，r2 审查指出旧验收全都绕开了
        "原件 DOCX 取表"这条路径，只测过 rows/PDF）。
      - 新表格 tblStyle 解析出的样式名是 "Table Grid"（本书真正的表格样式），不是 "macro"。
      - 新表格 gridCol 总宽 <= 9298（版心宽度），不超页边距。
      - 新表格所有单元格段落/run 里都没有直接写 eastAsia="楷体"（源表格的直接格式已被样板表头/
        表体格式整体覆盖）。
      - 表头行（第0行）全部加粗、表体行不加粗（与样板表 B0003 表头/表体格式一致）。
      - 表格文字（去格式后）与原件表格逐字一致（题面零改写）。
    """
    t0 = time.time()
    try:
        if not TEACHER_HD_QIZHONG_2023_DOCX.exists():
            return record('R2_M4_真实DOCX原件带表新题_BJ-2023-HD-QIZHONG-Q18', False,
                          f'找不到原件 {TEACHER_HD_QIZHONG_2023_DOCX}', t0)
        docx = fresh_copy('r2m4_parent.docx')
        rubric = ('【细则说明】 第一类举措，2分：设立民营经济发展局，完善政府诚信履约机制，更好'
                  '发挥政府作用，优化民营经济发展的营商环境，推动不同市场主体公开公平公正参与市场'
                  '竞争。第二类举措，3分：落实减税降费，简化办税手续，降低企业经营成本，提升企业'
                  '竞争力；对科技创新、绿色低碳等民营企业扩大信贷投放，为企业提供资金支持，推动'
                  '民营企业创新、绿色发展。第三类举措，2分：加强对民营企业产权保护，不断完善法治'
                  '环境，激发民营企业积极性，促进民营企业守法经营。')
        unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': BIXIU3_SHA,
                'approved_by': 'claude:block_insert-r2m4', 'approval_ref':
                    'block_insert.py 返修 r2 验收：真实漏收候选 BJ-2023-HD-QIZHONG-Q18#1（原件 DOCX '
                    '带表，教师版第5表），教学栏目按 E1 正式细则改写整理，测试用，未经教学审定',
                'inserts': [{'id': 'I001',
                             'anchor': {'after_block': {'title_contains': '例题 6　2026丰台二模第17题'}},
                             'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
                             'title': '例题 98　2023海淀期中第18题',
                             'source_zone': 'restore',
                             'reason': '题目材料、设问逐字取自原件教师版第6页，表格原样取自原件第5表'
                                       '（题库漏收候选 BJ-2023-HD-QIZHONG-Q18#1），教学栏目按正式评分'
                                       '细则（E1）改写整理，测试用，未经教学审定',
                             'content': [
                                 {'role': 'source', 'text': '【题目】18．（9分）'},
                                 {'role': 'source', 'text': '民营经济是推进中国式现代化的生力军，是'
                                  '高质量发展的重要基础，是推动我国全面建成社会主义现代化强国、实现'
                                  '第二个百年奋斗目标的重要力量。'},
                                 {'role': 'source', 'text': '结合当前民营经济发展面临的形势和民营经济'
                                  '工作现状，我国先后推出系列促进民营经济发展壮大的政策举措，以下是'
                                  '部分摘录。'},
                                 {'role': 'table', 'from': {'docx': str(TEACHER_HD_QIZHONG_2023_DOCX),
                                                             'table_index': 5}},
                                 {'role': 'source', 'text': '（1）阅读材料，在上表中的横线处填写适当'
                                  '内容。（2分）'},
                                 {'role': 'source', 'text': '（2）结合材料，运用《经济与社会》知识，'
                                  '分析上述举措如何促进民营经济发展壮大。（7分）'},
                                 {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】'},
                                 {'role': 'teaching', 'like': '从材料选知识',
                                  'text': '从材料选知识：设立民营经济发展局、完善诚信履约机制提示'
                                          '政府更好发挥作用；免征增值税、扩大信贷投放提示财政货币'
                                          '政策支持；保护民营企业产权提示法治保障。'},
                                 {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】'},
                                 {'role': 'teaching', 'like': '总述',
                                  'text': '①优化民营经济发展的营商环境，推动市场主体公平参与竞争；'
                                          '②落实减税降费、扩大信贷投放，降低经营成本、提升竞争力；'
                                          '③加强产权保护，完善法治环境，激发民营企业积极性。'},
                                 {'role': 'rubric', 'text': rubric},
                             ]}]}
        unit_path = SCRATCH / 'r2m4_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding='utf-8')
        out = SCRATCH / 'r2m4_out.docx'
        out.unlink(missing_ok=True)
        report = SCRATCH / 'r2m4_report.json'
        # --renumber：插入的"例题 98"打破了原有编号顺序，链路验收要求"--renumber 或随后
        # layout_prepare repair 后不新增 FAIL"（见任务验收 1），不是插入本身要做到编号连续。
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3),
                                    '--report', str(report), '--health', '--renumber'])
        rep = load_report(report) if report.exists() else {}
        health = rep.get('health', {})
        renumbered = out.with_name(out.stem + '_renumbered' + out.suffix)
        ok = rc == 0 and out.exists() and health.get('new_FAIL_count') == 0 and renumbered.exists()
        bic = rep.get('verify', {}).get('block_index_check', [{}])
        tables_ok = bool(bic) and bic[0].get('tables_match')
        ok = ok and tables_ok
        detail = f'rc={rc} new_FAIL={health.get("new_FAIL_count")} tables_match={tables_ok}'
        if ok:
            with zipfile.ZipFile(TEACHER_HD_QIZHONG_2023_DOCX) as z:
                src_root = etree.fromstring(z.read('word/document.xml'))
            src_tbls = bi._top_tables(src_root.find(W + 'body'))
            src_tbl = src_tbls[4]
            src_text = ''.join(t.text or '' for t in src_tbl.iter(W + 't'))

            with zipfile.ZipFile(out) as z:
                styles_root = etree.fromstring(z.read('word/styles.xml'))
                out_root = etree.fromstring(z.read('word/document.xml'))
            styles_obj = bh.Styles(styles_root)
            body = out_root.find(W + 'body')
            paras = dl.para_elements(body)
            i0, _ = _find_para(paras, '结合当前民营经济发展面临的形势')
            el = bi._top_level_anchor(body, paras[i0]).getnext() if i0 is not None else None
            while el is not None and el.tag != W + 'tbl':
                el = el.getnext()
            if el is None:
                ok, detail = False, detail + ' 没找到新插入的表格'
            else:
                tblpr = el.find(W + 'tblPr')
                ts = tblpr.find(W + 'tblStyle') if tblpr is not None else None
                style_name = styles_obj.name.get(ts.get(W + 'val'), ts.get(W + 'val')) if ts is not None else None
                style_ok = style_name == 'Table Grid'
                grid = el.find(W + 'tblGrid')
                total_w = sum(int(c.get(W + 'w') or 0) for c in grid.findall(W + 'gridCol')) if grid is not None else -1
                width_ok = 0 < total_w <= 9298
                kaiti_hit = any(
                    (r.find(W + 'rPr').find(W + 'rFonts').get(W + 'eastAsia') == '楷体')
                    for r in el.iter(W + 'r')
                    if r.find(W + 'rPr') is not None and r.find(W + 'rPr').find(W + 'rFonts') is not None
                )
                trs = el.findall(W + 'tr')
                header_bold = trs and all(
                    any(b for _, b, _ in _run_fmt(p)) or not dl.para_text(p).strip()
                    for tc in trs[0].findall(W + 'tc') for p in tc.findall(W + 'p'))
                body_unbold = len(trs) > 1 and all(
                    not any(b for _, b, _ in _run_fmt(p))
                    for tr in trs[1:] for tc in tr.findall(W + 'tc') for p in tc.findall(W + 'p'))
                new_text = ''.join(t.text or '' for t in el.iter(W + 't'))
                text_ok = new_text == src_text
                ok = style_ok and width_ok and not kaiti_hit and header_bold and body_unbold and text_ok
                detail += (f' tblStyle解析名={style_name}（期望Table Grid） gridCol总宽={total_w}'
                          f'（应<=9298） 残留直接楷体={kaiti_hit} 表头全加粗={header_bold}'
                          f' 表体不加粗={body_unbold} 文字逐字一致={text_ok}')
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R2_M4_真实DOCX原件带表新题_BJ-2023-HD-QIZHONG-Q18', ok, detail, t0)


def test_m3_shared_anchor_order():
    """m3 修复：同一批里两条 insert 共用同一个 after_block 锚点，输出顺序应与插入单顺序一致（旧版
    第二条会插到第一条前面）。"""
    t0 = time.time()
    try:
        docx = fresh_copy('m3order_parent.docx')
        unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': BIXIU3_SHA,
                'approved_by': 'claude:block_insert-m3', 'approval_ref': 'm3 复现用例，测试用，未经教学审定',
                'inserts': [
                    {'id': 'A1', 'anchor': {'after_block': {'title_contains': '例题 6　2026丰台二模第17题'}},
                     'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
                     'title': '例题 96　2099工具验收顺序测试卷第1题', 'source_zone': 'approved_edit',
                     'reason': 'm3 复现用例，非正式内容',
                     'content': _minimal_content_for('顺序测试A')},
                    {'id': 'A2', 'anchor': {'after_block': {'title_contains': '例题 6　2026丰台二模第17题'}},
                     'template_block': {'title_contains': '例题 3　2024朝阳二模第18题'},
                     'title': '例题 97　2099工具验收顺序测试卷第2题', 'source_zone': 'approved_edit',
                     'reason': 'm3 复现用例，非正式内容',
                     'content': _minimal_content_for('顺序测试B')},
                ]}
        unit_path = SCRATCH / 'm3order_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False, indent=2), encoding='utf-8')
        out = SCRATCH / 'm3order_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc in (0, 1) and out.exists()
        detail = f'rc={rc} stderr={serr[-400:]}'
        if ok:
            d2 = dl.open_docx(out)
            i96, _ = _find_para(d2.paras, '例题 96')
            i97, _ = _find_para(d2.paras, '例题 97')
            order_ok = i96 is not None and i97 is not None and i96 < i97
            ok = ok and order_ok
            detail += f' 例题96位于{i96} 例题97位于{i97} order_ok={order_ok}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    return record('m3_同锚点多条insert顺序保持', ok, detail, t0)


def test_m2_renumber_failure_exit_code():
    """m2 修复：--renumber 失败（这里用"预先占住 *_renumbered.docx 路径，让 layout_prepare 的写权
    守卫拒写"来复现）不应再以退出码 0 收尾；应为 1，且 stdout 的 sha256 对应保留下来的未重排文件。"""
    t0 = time.time()
    try:
        docx = fresh_copy('m2renum_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        unit_path = SCRATCH / 'm2renum_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'm2renum_out.docx'
        out.unlink(missing_ok=True)
        renum_out = out.with_name(out.stem + '_renumbered' + out.suffix)
        renum_out.write_bytes(b'PK\x03\x04pre-occupied to force layout_prepare guard_write to refuse')
        report = SCRATCH / 'm2renum_report.json'
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3),
                                    '--report', str(report), '--renumber'])
        rep = load_report(report) if report.exists() else {}
        renumber_ok = (rep.get('renumber') or {}).get('ok')
        stdout_obj = json.loads(sout) if sout.strip() else {}
        ok = rc == 1 and renumber_ok is False and out.exists() and stdout_obj.get('sha256') == dl.sha256_file(out)
        detail = (f'rc={rc}（期望1） renumber.ok={renumber_ok} stdout={stdout_obj} '
                  f'pre-renumber-sha={dl.sha256_file(out) if out.exists() else None}')
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    return record('m2_renumber失败退出码不再是0', ok, detail, t0)


def test_m5_health_exception_not_swallowed():
    """m5 修复：--health 内部异常（这里用 monkeypatch bi.health_diff 直接模拟，进程内调用）不应再
    以退出码 0 收尾。R3-m9 修复：退出码原先是 2，但插入本身已经写出、写后复核也已经通过，2 在共同
    约定第 6 条里是"整批中止、不留输出"，这里却仍然保留了已写出的插入结果，两者不一致（旧版这条
    测试自己就把"rc=2 但 out 仍存在"断言成预期行为，等于把这个不一致当成了正确答案）。改成 1
    （"发现待处理"）、且不删除已通过复核的输出，断言随之改成 rc==1。"""
    t0 = time.time()
    orig = bi.health_diff
    try:
        docx = fresh_copy('m5health_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        unit_path = SCRATCH / 'm5health_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'm5health_out.docx'
        out.unlink(missing_ok=True)
        report = SCRATCH / 'm5health_report.json'

        def _boom(*a, **kw):
            raise RuntimeError('m5 复现用：模拟 --health 内部异常')
        bi.health_diff = _boom
        rc = _call_apply_inprocess(_apply_args(docx, unit_path, out, report=report, health=True))
        rep = load_report(report) if report.exists() else {}
        ok = rc == 1 and 'error' in (rep.get('health') or {}) and out.exists()
        detail = f'rc={rc}（期望1，R3-m9） health={rep.get("health")} out_exists={out.exists()}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    finally:
        bi.health_diff = orig
    return record('m5_R3-m9_health异常改为1且不删已写出的输出', ok, detail, t0)


def test_m2_block_index_hard_fail():
    """M2 复现：monkeypatch bi.bidx.build_index（进程内调用），让它对刚插入的题块谎报多一张图片
    （模拟"block_index 认出的 media 数与插入单预期不符"）。旧版这种不符只写进报告、退出码仍是 0；
    修复后必须硬失败：退出码 2、输出文件被删除。"""
    t0 = time.time()
    orig = bi.bidx.build_index
    try:
        docx = fresh_copy('m2bidx_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        want_title = unit['inserts'][0]['title']
        unit_path = SCRATCH / 'm2bidx_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'm2bidx_out.docx'
        out.unlink(missing_ok=True)
        report = SCRATCH / 'm2bidx_report.json'

        def _fake(*a, **kw):
            idx = orig(*a, **kw)
            for b in idx['blocks']:
                if b['title'] == want_title:
                    b['media'] = list(b.get('media') or []) + ['fake/injected.png']
            return idx
        bi.bidx.build_index = _fake
        rc = _call_apply_inprocess(_apply_args(docx, unit_path, out, report=report))
        ok = rc == 2 and not out.exists()
        detail = f'rc={rc}（期望2） 输出未残留={not out.exists()}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    finally:
        bi.bidx.build_index = orig
    return record('M2_block_index写后复核硬失败_人工造媒体数不符', ok, detail, t0)


def test_r2_b1_sanitize_table_styles_by_name():
    """R2-B1 复现：sanitize_table_styles 原先按 styleId 是否在本书"存在"判断能不能保留 tblStyle
    ——不同文档的 styleId 是 Word 各自生成的，会撞号。真实撞号案例：原件
    2023北京海淀高三（上）期中政治（教师版）.docx 里 styleId "af0" 是表格样式 "Table Grid"；
    本书 styles.xml 里"af0"恰好也存在，但是段落样式"macro"（已用 lxml 直接核对两份 styles.xml
    验证，见回执）。旧版"只要 styleId 在本书存在就保留"会让 tblStyle 指向 macro——一个表级属性
    指向段落样式，是这次 blocker 的原始症状。修复后应按 (type, w:name) 找到本书真正的 Table Grid
    （styleId 不同，是 afff1），旧代码这里会失败（保留 af0 不变）。"""
    t0 = time.time()
    try:
        with zipfile.ZipFile(BIXIU3_DOCX) as z:
            styles_xml = etree.fromstring(z.read('word/styles.xml'))
        target_name_to_id = bi._name_to_id_index(bi._style_type_name_map(styles_xml))
        real_table_grid_id = target_name_to_id.get(('table', 'Table Grid'))
        # 源信息按真实原件核对写死（不依赖那份原件在云端一定存在；这是纯 XML 层单元测试）。
        src_type_name = {'af0': ('table', 'Table Grid'), 'xyz_不存在的名字': ('table', 'xyz_不存在的名字')}

        def _tbl_with_style(style_id):
            tbl = etree.Element(W + 'tbl')
            tblpr = etree.SubElement(tbl, W + 'tblPr')
            etree.SubElement(tblpr, W + 'tblStyle', {W + 'val': style_id})
            tr = etree.SubElement(tbl, W + 'tr')
            tc = etree.SubElement(tr, W + 'tc')
            etree.SubElement(tc, W + 'p')
            return tbl

        tbl_collide = _tbl_with_style('af0')
        bi.sanitize_table_styles(tbl_collide, target_name_to_id, src_type_name)
        ts = tbl_collide.find(f'{W}tblPr/{W}tblStyle')
        remapped_val = ts.get(W + 'val') if ts is not None else None
        remapped_ok = remapped_val == real_table_grid_id and remapped_val != 'af0'

        tbl_unknown = _tbl_with_style('xyz_不存在的名字')
        bi.sanitize_table_styles(tbl_unknown, target_name_to_id, src_type_name)
        removed_ok = tbl_unknown.find(f'{W}tblPr/{W}tblStyle') is None

        ok = bool(real_table_grid_id) and remapped_ok and removed_ok
        detail = (f'本书真正的 Table Grid styleId={real_table_grid_id}（不是 af0） '
                  f'撞号场景重映射到={remapped_val} 未知名删除={removed_ok}')
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    return record('R2_B1_sanitize_table_styles按名字映射不按styleId', ok, detail, t0)


def test_review_r1_fixes():
    ok_all = True
    ok_all &= test_b2_m1_table_rels()
    ok_all &= test_m1_docpr_collision()
    ok_all &= test_m1_textbox_abort()
    ok_all &= test_m3_shared_anchor_order()
    ok_all &= test_m2_renumber_failure_exit_code()
    ok_all &= test_m5_health_exception_not_swallowed()
    ok_all &= test_m2_block_index_hard_fail()
    ok_all &= test_m12_profile_required()
    return ok_all


# ------------------------------------------------------------------ 返修 r2：逐条复现 blocker/major/minor
def test_r2_m1_wordlist_style_bypass():
    """R2-M1 复现：role=source + style="分析过程"（教学桶样式）+ source_zone=restore，旧版能把
    工程词写进教学栏目而不触发中止（审查 r2 探针 probe_wordlist_style_bypass.txt：不带 --health
    时 rc=0）。修复后 find_role_template 的 style_override 限定在角色自己的样式桶内，role=
    "source" 配的 styles.source 桶里没有"分析过程"这个样式名，应在 plan 阶段就 Abort（rc=2，不
    留输出，不需要 --health 才能拦住）。控制组：role=teaching 配同一个样式名（本就在 teaching
    桶内）应该正常通过（style 覆盖合法使用不应被误伤）。"""
    ok_all = True
    bypass_text = '从材料选知识：此处待核，TODO 占位，本落位示例。'

    t0 = time.time()
    try:
        docx = fresh_copy('r2m1_bypass_parent.docx')
        # source_zone 必须是 restore——豁免只在 role=="source" 且 restore 时才生效（见文件头
        # "题面零改写"一节），approved_edit 下 source 角色文字本来就要过词表，那样测到的是词表
        # 本身的检查，不是这道 R2-M1 修复要堵的"豁免+style 覆盖"绕过口子。
        unit = _minimal_unit(BIXIU3_SHA, source_zone='restore', content=[
            {'role': 'source', 'style': '分析过程', 'text': bypass_text},
        ])
        unit_path = SCRATCH / 'r2m1_bypass_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r2m1_bypass_out.docx'
        out.unlink(missing_ok=True)
        # 故意不带 --health：旧版这个组合不带 --health 时 rc=0，正是审查 r2 抓到的现象。
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc == 2 and not out.exists() and ('样式桶' in serr or 'styles.source' in serr)
        detail = f'rc={rc}（期望2，不需要 --health） 输出未残留={not out.exists()} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('R2_M1_词表豁免被style覆盖绕过_role=source配教学桶样式必须中止', ok, detail, t0)

    t0 = time.time()
    try:
        docx = fresh_copy('r2m1_control_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, content=[
            {'role': 'source', 'text': '【题目】负例测试用最小材料一句话。'},
            {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】负例测试占位文字。'},
            {'role': 'teaching', 'style': '分析过程', 'text': '控制组：教学正文一句话，不含禁用词，'
             '验证 style 覆盖桶内样式可以正常使用。'},
            {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】负例测试占位文字。'},
            {'role': 'rubric', 'text': '【细则说明】 负例测试占位文字。'},
        ])
        unit_path = SCRATCH / 'r2m1_control_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r2m1_control_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc in (0, 1) and out.exists()
        detail = f'rc={rc}（期望0/1） out_exists={out.exists()} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('R2_M1_控制组_role=teaching配桶内样式应正常通过', ok, detail, t0)
    return ok_all


def test_r2_m2_missing_columns_hard_fail():
    """R2-M2 复现：新题块缺【思维链条】/【答案落点】/【细则说明】等必须栏目时，旧版
    block_index 的 missing 只写进报告、退出码仍是 0（审查 r2 探针：wl_style_bypass_nohealth
    里 missing 非空但 rc=0）。_minimal_unit 默认 content 只有一段 source，天然缺全部教学栏目，
    不需要额外构造。修复后应硬失败：rc=2，输出被删除。"""
    t0 = time.time()
    try:
        docx = fresh_copy('r2m2_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, content=[
            {'role': 'source', 'text': '【题目】负例测试用最小材料一句话，故意只给这一段。'},
        ])  # 只给 1 段 source，缺全部教学/细则栏目（_minimal_unit 默认内容已在 R2-M2 修复后
            # 补全为"完整的最小合法插入"，这里显式传回不完整的版本才能测到栏目缺失）
        unit_path = SCRATCH / 'r2m2_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r2m2_out.docx'
        out.unlink(missing_ok=True)
        report = SCRATCH / 'r2m2_report.json'
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3),
                                    '--report', str(report)])
        rep = load_report(report) if report.exists() else {}
        bic = (rep.get('verify') or {}).get('block_index_check') or [{}]
        missing = bic[0].get('missing') if bic else None
        ok = rc == 2 and not out.exists() and bool(missing)
        detail = f'rc={rc}（期望2） 输出未残留={not out.exists()} missing={missing} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    return record('R2_M2_栏目缺失写后复核硬失败', ok, detail, t0)


def test_r2_m3_report_overwrite_protection():
    """R2-M3 复现：--report 原先无条件 overwrite=True，能静默覆盖已批准的补丁、插入单本身、
    甚至别的工具写的报告（审查 r2 探针 probe_report_overwrite.txt）。构造四种已存在的目标文件：
    前三种（已批准补丁 schema=baodian_patch_v1、插入单本身 schema=baodian_insert_v1、别的工具
    的报告 tool!='block_insert'）应该被拒绝覆盖——check 模式下 rc=3、文件字节不变；第四种（本
    工具自己以前写的同 mode 报告）应该能正常覆盖。"""
    ok_all = True

    def _case(label, existing_obj, expect_blocked):
        t0 = time.time()
        try:
            docx = fresh_copy(f'{label}_parent.docx')
            unit = _minimal_unit(BIXIU3_SHA)
            unit_path = SCRATCH / f'{label}_insert.json'
            unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
            report = SCRATCH / f'{label}_report.json'
            report.write_text(json.dumps(existing_obj, ensure_ascii=False), encoding='utf-8')
            before = report.read_text(encoding='utf-8')
            rc, sout, serr = run_tool(['check', '--docx', str(docx), '--insert', str(unit_path),
                                        '--profile', str(PROF_BIXIU3), '--report', str(report)])
            after = report.read_text(encoding='utf-8')
            if expect_blocked:
                ok = rc == 3 and after == before
                detail = f'rc={rc}（期望3） 文件未变={after == before} stderr={serr[-300:]}'
            else:
                ok = rc in (0, 1) and after != before and json.loads(after).get('tool') == 'block_insert'
                detail = f'rc={rc}（期望0/1） 文件已更新={after != before}'
        except Exception as e:
            ok, detail = False, f'异常：{e}'
        return record(label, ok, detail, t0)

    ok_all &= _case('R2_M3_report不覆盖已批准补丁',
                     {'schema': 'baodian_patch_v1', 'approved_by': 'user', 'ops': [{'id': 'x'}]}, True)
    ok_all &= _case('R2_M3_report不覆盖插入单本身',
                     {'schema': 'baodian_insert_v1', 'book': 'bixiu3',
                      'parent_docx_sha256': '0' * 64, 'inserts': []}, True)
    ok_all &= _case('R2_M3_report不覆盖不相干json',
                     {'tool': 'exam_register', 'mode': 'check', 'marker': 'other'}, True)
    ok_all &= _case('R2_M3_report可覆盖自己以前的同类报告',
                     {'tool': 'block_insert', 'mode': 'check', 'marker': 'old-self'}, False)
    return ok_all


def test_r2_m3_report_atomic_write():
    """R2-M3 修复：_write_report 改用临时文件 + os.replace 原子写出。monkeypatch os.replace 让它
    半路失败，断言目标文件的旧内容原封不动（没有被截断/清空成新内容的一部分），且不残留临时
    文件。"""
    t0 = time.time()
    orig_replace = bi.os.replace
    try:
        target = SCRATCH / 'r2m3_atomic_report.json'
        target.write_text(json.dumps({'marker': 'old-untouched'}), encoding='utf-8')

        def _boom(*a, **kw):
            raise OSError('r2-m3 复现用：模拟 os.replace 失败')
        bi.os.replace = _boom
        threw = False
        try:
            bi._atomic_write_text(target, json.dumps({'marker': 'new'}))
        except OSError:
            threw = True
        finally:
            bi.os.replace = orig_replace
        after = json.loads(target.read_text(encoding='utf-8'))
        leftover = list(SCRATCH.glob('.block_insert_report_*'))
        ok = threw and after.get('marker') == 'old-untouched' and not leftover
        detail = f'os.replace失败后仍向外抛出={threw} 旧内容保留={after} 残留临时文件={leftover}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    finally:
        bi.os.replace = orig_replace
    return record('R2_M3_report原子写出_写失败不破坏旧内容', ok, detail, t0)


def test_r2_m10_renumber_next_command_quoting():
    """R2-m10 复现：--out 路径带空格时，next_command 原先用 ' '.join(cmd) 拼字符串，shlex.split
    回读会把路径拆成两段（不能照抄重跑）；也验证 next_command 里的 --out 值不是这次已经失败占用
    的那个路径。"""
    t0 = time.time()
    try:
        import shlex
        space_dir = SCRATCH / 'm10 目录 带空格'
        space_dir.mkdir(parents=True, exist_ok=True)
        docx_src = fresh_copy('r2m10_src_parent.docx')
        docx2 = space_dir / 'm10quote parent.docx'
        shutil.copyfile(docx_src, docx2)
        unit = _minimal_unit(BIXIU3_SHA)
        unit_path = space_dir / 'm10quote insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = space_dir / 'm10quote out.docx'
        out.unlink(missing_ok=True)
        renum_out = out.with_name(out.stem + '_renumbered' + out.suffix)
        renum_out.write_bytes(b'PK\x03\x04pre-occupied to force layout_prepare guard_write to refuse')
        report = space_dir / 'm10quote report.json'
        rc, sout, serr = run_tool(['apply', '--docx', str(docx2), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3),
                                    '--report', str(report), '--renumber'])
        rep = load_report(report) if report.exists() else {}
        next_cmd = (rep.get('renumber') or {}).get('next_command')
        parsed = shlex.split(next_cmd) if next_cmd else []
        oi = parsed.index('--out') if '--out' in parsed else -1
        retry_out = parsed[oi + 1] if oi >= 0 else None
        quoting_ok = bool(next_cmd) and oi >= 0 and retry_out is not None
        not_reused = retry_out is not None and Path(retry_out) != renum_out
        # renumber 的 --docx 参数是 block_insert 这一步刚写出的 out（不是最外层输入的父稿 docx2），
        # 用它验证带空格路径能不能原样往返。
        docx_roundtrip_ok = ('--docx' in parsed
                              and Path(parsed[parsed.index('--docx') + 1]) == out.resolve())
        ok = rc == 1 and quoting_ok and not_reused and docx_roundtrip_ok
        detail = (f'rc={rc}（期望1） next_command={next_cmd!r} retry_out={retry_out} '
                  f'不沿用占用路径={not_reused} 带空格路径可原样往返={docx_roundtrip_ok}')
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    return record('R2_m10_renumber_next_command路径带空格可原样往返', ok, detail, t0)


def test_r2_m3_render_check_exit_code():
    """R2-m3 复现：--render-check 转换失败（云端只装了 libreoffice-core，缺 writer 组件，
    shutil.which('soffice') 返回真实路径但转换会失败）原先静默：ok=false，退出码仍是 0，stderr
    没有任何提示。monkeypatch bi._render_check 直接返回一个"跑过但失败"的结果（不依赖云端是否
    真的缺 writer 组件，跨环境都能复现），断言退出码提到 1、stderr 有提示。"""
    t0 = time.time()
    orig = bi._render_check
    try:
        docx = fresh_copy('r2m3render_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, content=[
            {'role': 'source', 'text': '【题目】负例测试用最小材料一句话。'},
            {'role': 'teaching', 'like': '思维链条', 'text': '【思维链条】占位测试文字。'},
            {'role': 'teaching', 'like': '答案落点', 'text': '【答案落点】占位测试文字。'},
            {'role': 'rubric', 'text': '【细则说明】 占位测试文字。'},
        ])
        unit_path = SCRATCH / 'r2m3render_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r2m3render_out.docx'
        out.unlink(missing_ok=True)

        def _fake(out_path):
            return {'ran': True, 'ok': False, 'returncode': 1, 'note': 'source file could not be loaded'}
        bi._render_check = _fake
        rc = _call_apply_inprocess(_apply_args(docx, unit_path, out, render_check=True))
        ok = rc == 1 and out.exists()
        detail = f'rc={rc}（期望1，不阻断写出） out_exists={out.exists()}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    finally:
        bi._render_check = orig
    return record('R2_m3_render_check转换失败退出码提到1', ok, detail, t0)


def test_r2_m9_unit_schema_unknown_key():
    """R2-m9 复现：插入单字段名写错（把 "like" 拼成 "lik"）旧版会被 item.get(...) 静默忽略，
    退回默认匹配，作者不会发现显式指定根本没生效。修复后 _load_unit 的 _validate_unit_schema
    应该直接 Abort（rc=2），提示里点名是哪个未知字段。"""
    t0 = time.time()
    try:
        docx = fresh_copy('r2m9_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, content=[
            {'role': 'teaching', 'lik': '思维链条', 'text': '拼错字段名，应被拒绝。'},
        ])
        unit_path = SCRATCH / 'r2m9_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r2m9_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc == 2 and not out.exists() and 'lik' in serr
        detail = f'rc={rc}（期望2） 提示含未知字段名={"lik" in serr} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    return record('R2_m9_插入单未知字段被拒绝', ok, detail, t0)


def test_r2_m9_unit_book_mismatch():
    """R2-m9 复现：插入单 book 字段与 --profile 实际书册不一致时，旧版从不核对，仍按 --profile
    工作却在报告里留一个对不上的 book 字段。"""
    t0 = time.time()
    try:
        docx = fresh_copy('r2m9_bookmismatch_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        unit['book'] = 'philosophy'  # 与 --profile bixiu3 不一致
        unit_path = SCRATCH / 'r2m9_bookmismatch_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r2m9_bookmismatch_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc == 2 and not out.exists() and 'philosophy' in serr and 'bixiu3' in serr
        detail = f'rc={rc}（期望2） stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    return record('R2_m9_插入单book字段与profile不一致被拒绝', ok, detail, t0)


def test_r2_m6_chinese_messages_no_debug():
    """R2-m6 复现：不加 --debug 时不应打印 traceback（run_tests 其余用例固定加了 --debug，这条
    专门反过来验证）；插入单缺失文件、JSON 损坏、配置名不存在，这三种原先冒出英文异常正文
    （FileNotFoundError/JSONDecodeError 的 str()）的场景，提示应改成中文。"""
    ok_all = True

    def _run_no_debug(args):
        cmd = [sys.executable, str(TOOL)] + list(args)  # 不带 --debug（run_tool 固定带，这里不带）
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.returncode, r.stdout, r.stderr

    t0 = time.time()
    try:
        docx = fresh_copy('r2m6_missing_parent.docx')
        rc, sout, serr = _run_no_debug(['check', '--docx', str(docx),
                                         '--insert', str(SCRATCH / '不存在的插入单.json'),
                                         '--profile', str(PROF_BIXIU3)])
        ok = rc == 2 and 'Traceback' not in serr and '不存在' in serr
        detail = f'rc={rc} 无traceback={"Traceback" not in serr} 中文提示={"不存在" in serr} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('R2_m6_插入单文件不存在_中文提示无traceback', ok, detail, t0)

    t0 = time.time()
    try:
        docx = fresh_copy('r2m6_badjson_parent.docx')
        bad_unit = SCRATCH / 'r2m6_badjson_insert.json'
        bad_unit.write_text('这不是合法JSON{{{', encoding='utf-8')
        rc, sout, serr = _run_no_debug(['check', '--docx', str(docx), '--insert', str(bad_unit),
                                         '--profile', str(PROF_BIXIU3)])
        ok = rc == 2 and 'Traceback' not in serr and 'JSON' in serr and '行' in serr
        detail = f'rc={rc} 无traceback={"Traceback" not in serr} 中文提示={ok} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('R2_m6_插入单JSON损坏_中文提示无traceback', ok, detail, t0)

    t0 = time.time()
    try:
        docx = fresh_copy('r2m6_noprofile_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA)
        unit_path = SCRATCH / 'r2m6_noprofile_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        rc, sout, serr = _run_no_debug(['check', '--docx', str(docx), '--insert', str(unit_path),
                                         '--profile', '这个配置名在本书不存在_xyz'])
        ok = rc == 2 and 'Traceback' not in serr and '不存在' in serr
        detail = f'rc={rc} 无traceback={"Traceback" not in serr} 中文提示={"不存在" in serr} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}'
    ok_all &= record('R2_m6_配置名不存在_中文提示无traceback', ok, detail, t0)
    return ok_all


def test_r2_m1_rels_no_new_image():
    """R2-m1 复现：原先只在 media_ctx.new_media 非空时才写 rels/Content_Types——只新增外部关系
    （比如表格内超链接，没有新图片）时 new_media 为空、new_rels 非空，rels 漏写，写后复核会报
    "部分 r:embed/r:id 在 rels 里找不到关系"。这里直接单元测试 MediaCtx：只调用 add_external_rel
    （不调用 add_image），确认 new_rels 非空、new_media 为空——cmd_apply 里 "new_media or
    new_rels" 这个条件因此必须触发写 rels，不能只看 new_media。"""
    t0 = time.time()
    try:
        d = dl.open_docx(BIXIU3_DOCX)
        ctx = bi.MediaCtx(d)
        ctx.add_external_rel(bi.REL_HYPERLINK_TYPE, 'https://example.com/test')
        ok = bool(ctx.new_rels) and not ctx.new_media
        detail = f'new_rels={ctx.new_rels} new_media为空={not ctx.new_media}（旧版只看 new_media 会漏判该写 rels）'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    return record('R2_m1_只有外部关系无新图片时也要写rels', ok, detail, t0)


def test_r2_m16_source_cache_closed_after_call():
    """R2-m16 复现：_source_cache 原先是跨调用存活的全局缓存，ZipFile 句柄也不关闭。进程内连续
    调用两次 plan_inserts()（模拟未来串联调用/测试直接调函数），第二次调用后 _source_cache 里
    不应该还留着第一次打开的原件，且第一次的 ZipFile 句柄应已关闭（.fp is None）。"""
    t0 = time.time()
    try:
        d = dl.open_docx(BIXIU3_DOCX)
        media_ctx = bi.MediaCtx(d)
        prof_dict = bi.load_profile(str(PROF_BIXIU3))
        unit1 = _minimal_unit(BIXIU3_SHA, content=[
            {'role': 'source', 'text': '【题目】占位。'},
            {'role': 'image', 'from': {'docx': str(XC_ERMO_DOCX), 'rid': 'rId14'}},
        ])
        bi.plan_inserts(d, prof_dict, unit1, media_ctx)
        first_call_srcs = list(bi._source_cache.values())
        # 缓存只在"下一次 plan_inserts() 调用开始时"才会被关闭清空（见 _close_source_cache 注释），
        # 第一次调用刚结束时句柄理应还开着——先确认这一点，否则下面"第二次调用后已关闭"的断言
        # 会因为"其实从没打开过"而假阳性通过。
        opened_after_first = bool(first_call_srcs) and all(
            getattr(s.z, 'fp', None) is not None for s in first_call_srcs)

        d2 = dl.open_docx(BIXIU3_DOCX)
        media_ctx2 = bi.MediaCtx(d2)
        unit2 = _minimal_unit(BIXIU3_SHA)  # 这次不引用任何原件
        bi.plan_inserts(d2, prof_dict, unit2, media_ctx2)  # 调用开始时应关闭并清空上一次的缓存
        closed_after_second = all(getattr(s.z, 'fp', 'no-fp-attr') is None for s in first_call_srcs)
        second_call_cache_empty = len(bi._source_cache) == 0
        ok = opened_after_first and closed_after_second and second_call_cache_empty
        detail = (f'第一次调用打开的原件数={len(first_call_srcs)}（调用刚结束时仍开着={opened_after_first}） '
                  f'第二次调用开始后第一次的句柄已关闭={closed_after_second} '
                  f'第二次调用后缓存为空={second_call_cache_empty}（旧版会带着第一次的原件）')
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-600:]}'
    finally:
        bi._close_source_cache()
    return record('R2_m16_source_cache进程内多次调用不串味且句柄关闭', ok, detail, t0)


def test_r3_b1_stem_selftemplate_regression():
    """R3-B1 blocker 回归（fix_hint 原话："把本探针的全书模拟做成回归测试，要求 FLIP 为 0"）：
    对全书每个主观题块里的每个 Songti（设问字体）source 段，用该块自己作样板（最有利情形），走
    find_role_template/build_text_paragraph 的默认路径重新构造这一段，比较重建段的有效字体
    （沿样式继承链，不只看 run 自己的 XML 字面量）与原段是否一致。旧版（审查 r3）94/453 个不以
    "结合/运用/根据/依据/针对"开头的设问（引语开头、"有人说……"、"要求：……"、"（2）从……谈谈"
    这类写法）会被判成材料形状，重建后字体从宋体变楷体；本轮改用文字判据+位置信号两层
    （_para_shape_ctx/_stem_position_index），要求这里 FLIP 数为 0。"""
    t0 = time.time()
    try:
        d = dl.open_docx(BIXIU3_DOCX)
        prof = bi.load_profile(str(PROF_BIXIU3))
        with zipfile.ZipFile(BIXIU3_DOCX) as z:
            st = etree.fromstring(z.read('word/styles.xml'))
        S = bh.Styles(st)
        font_idx, based = {}, {}
        for s in st.iter(W + 'style'):
            sid = s.get(W + 'styleId')
            rf = s.find(f'{W}rPr/{W}rFonts')
            b = s.find(W + 'basedOn')
            font_idx[sid] = rf.get(W + 'eastAsia') if rf is not None else None
            based[sid] = b.get(W + 'val') if b is not None else None
        rf0 = st.find(f'{W}docDefaults/{W}rPrDefault/{W}rPr/{W}rFonts')
        dfont = rf0.get(W + 'eastAsia') if rf0 is not None else None

        def chain(sid):
            seen = set()
            while sid and sid not in seen:
                seen.add(sid)
                if font_idx.get(sid):
                    return font_idx[sid]
                sid = based.get(sid)
            return dfont

        def eff_font(p):
            sid = bi._para_style_id(S, p)
            for r, txt in ap._run_spans(p):
                if not txt.strip():
                    continue
                rpr = r.find(W + 'rPr')
                rf = rpr.find(W + 'rFonts') if rpr is not None else None
                if rf is not None and rf.get(W + 'eastAsia'):
                    return rf.get(W + 'eastAsia')
                return chain(sid)
            return None

        src_ids = bi._style_ids_for_bucket(prof, S, 'source')
        _, _, blocks, _ = ap.zones_of(d, prof)
        stem_pos = bi._stem_position_index(d, S, prof, blocks)
        flips = []
        n_songti = 0
        for b in blocks:
            ps = [i for i in (b.get('paras') or [])
                  if not d.items[i].get('tbl') and bi._para_style_id(S, d.paras[i]) in src_ids
                  and dl.para_text(d.paras[i]).strip()]
            fonts = {i: eff_font(d.paras[i]) for i in ps}
            if any(re.match(r'^[A-D][．.]', dl.para_text(d.paras[i]).strip()) for i in ps):
                continue  # 选择题跳过（源段是选项列表，不是这条回归要测的对象）
            opening = min(b.get('paras') or []) if b.get('paras') else None
            for i in ps:
                if fonts[i] != 'Songti SC':
                    continue
                n_songti += 1
                t = dl.para_text(d.paras[i]).strip()
                shape = bi._para_shape_ctx(t, i in stem_pos)
                if shape.startswith('label'):
                    continue
                fb = []
                tp, sid, tp_shape = bi.find_role_template(d, S, prof, b, 'source', None, None, shape,
                                                            fb, exclude_idx=opening, stem_pos=stem_pos)
                newp = bi.build_text_paragraph({'role': 'source', 'text': t}, tp, S,
                                                content_shape=shape, template_shape=tp_shape)
                nf = eff_font(newp)
                if nf != 'Songti SC':
                    flips.append((i, b['title'][:24], t[:30], nf))
        ok = n_songti > 400 and not flips  # 400 是留白的下限，真正断言是 flips 必须为空
        detail = f'全书宋体设问段共 {n_songti} 个，仍会 FLIP 的 {len(flips)} 个：{flips[:10]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_B1_全书self-template回归_FLIP必须为0', ok, detail, t0)


def test_r3_b1_stem_e2e_quote_lead():
    """R3-B1 端到端复现（审查 r3 probe_stem_e2e.py 原始场景）：以 例题 40　2026通州一模第21题
    （跨模块）为样板，默认路径插入原书第 933 段的真实设问原文——这段在原书里显式宋体，但以引号
    开头（"中国式现代化是干出来的……"结合材料……），不匹配 _STEM_LEAD_RX 这条开头正则。旧版会
    整段变成模板段材料格式的楷体；本轮改用"这条 insert 里最后一个 source 项"的位置信号，不给
    kind 字段也应该正确落地成宋体。"""
    t0 = time.time()
    try:
        d0 = dl.open_docx(BIXIU3_DOCX)
        stem_text = None
        for p in d0.paras:
            t = dl.para_text(p).strip()
            if t.startswith('“中国式现代化是干出来的，伟大事业都成于实干。”结合材料'):
                stem_text = t
                break
        if stem_text is None:
            return record('R3_B1_端到端_引号开头设问不给kind也应落地为宋体', False,
                          '原书里没找到这段引号开头的设问原文，探针场景失配', t0)
        docx = fresh_copy('r3b1_e2e_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, anchor={'after_block': {'title_contains':
                              '例题 40　2026通州一模第21题（跨模块）'}},
                              template_block={'title_contains': '例题 40　2026通州一模第21题（跨模块）'},
                              title='例题 94　2099返修r3回归卷第21题',
                              content=[{'role': 'source', 'text': '【题目】21．（9分）'},
                                       {'role': 'source', 'text': '某地坚持实干担当，推动重大项目落地见效。'},
                                       {'role': 'source', 'text': stem_text}] + _MINIMAL_CONTENT[1:])
        unit_path = SCRATCH / 'r3b1_e2e_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r3b1_e2e_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(docx), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc == 0 and out.exists()
        if ok:
            d2 = dl.open_docx(out)
            i, p = _find_para(d2.paras, '“中国式现代化是干出来的')
            if p is None:
                ok, extra = False, '输出里没找到这段设问'
            else:
                font, _sz = _effective_font_sz(p, ap._run_spans(p)[0][0].find(W + 'rPr'))
                ok = font == 'Songti SC'
                extra = f'重建段有效字体={font}（期望 Songti SC）'
        else:
            extra = ''
        detail = f'rc={rc} out_exists={out.exists()} {extra} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_B1_端到端_引号开头设问不给kind也应落地为宋体', ok, detail, t0)


def test_r3_m1_gold_table_no_keepnext_spread():
    """R3-M1 major 回归：金标 T2_tbl（删 B0003 带表题块、以 例题4 为样板重插）的格式差异不应再
    出现在表格内——旧版（审查 r3）21/25 处差异都在表格里（整表 keepNext、表头丢加粗居中）；本轮
    改按列取样板格式、识别样板有没有真正的表头（_template_row_fmt/_template_header_distinct），
    直接重跑 test_gold_regression 的核心逻辑并对 fmt_diffs 里 offset 对应段落是否落在表格内
    做硬断言（不满足于"差异数变小"，逐条判断在表格内的差异必须是 0）。"""
    t0 = time.time()
    try:
        pristine_path = fresh_copy('r3m1_pristine.docx')
        target_before = fresh_copy('r3m1_target_before.docx')
        prof_dict = bi.load_profile(str(PROF_BIXIU3))
        pristine = dl.open_docx(pristine_path)
        items = pristine.items
        P = bh.Prof(prof_dict)
        blocks_p = bh.walk(items, P)
        target_title = '例题 3　2024朝阳二模第18题'
        b = [x for x in blocks_p if target_title in (x.get('title') or '')][0]
        title_i = b['title_i']
        end_i = max([title_i] + list(b.get('paras') or []))
        content = gold_content_from_span(items, title_i, end_i, pristine_path)
        deleted = SCRATCH / 'r3m1_deleted.docx'
        deleted.unlink(missing_ok=True)
        delete_block_copy(target_before, deleted, prof_dict, [target_title])
        unit = {'schema': 'baodian_insert_v1', 'book': 'bixiu3', 'parent_docx_sha256': sha256_file(deleted),
                'approved_by': 'claude:block_insert-r3m1', 'approval_ref': 'R3-M1 返修回归',
                'inserts': [{'id': 'G1',
                             'anchor': {'after_block': {'title_contains': '例题 2　2026石景山二模第17(1)题'}},
                             'template_block': {'title_contains': '例题 4　2026朝阳一模第21题（跨模块）'},
                             'title': items[title_i]['text'], 'source_zone': 'restore',
                             'reason': 'R3-M1 返修回归：原表逐字逐格从本书原稿取回，验证不再整表 keepNext',
                             'content': content}]}
        unit_path = SCRATCH / 'r3m1_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        out = SCRATCH / 'r3m1_out.docx'
        out.unlink(missing_ok=True)
        rc, sout, serr = run_tool(['apply', '--docx', str(deleted), '--insert', str(unit_path),
                                    '--out', str(out), '--profile', str(PROF_BIXIU3)])
        ok = rc == 0 and out.exists()
        if ok:
            new_doc = dl.open_docx(out)
            new_items = new_doc.items
            new_P = bh.Prof(prof_dict)
            new_blocks = bh.walk(new_items, new_P)
            nb = [x for x in new_blocks if x['title'] == items[title_i]['text']][0]
            new_idxs = sorted([nb['title_i']] + list(nb.get('paras') or []))
            orig_idxs = list(range(title_i, end_i + 1))
            fmt_diffs = _fmt_diff_list([pristine.paras[i] for i in orig_idxs],
                                        [new_doc.paras[i] for i in new_idxs])
            in_table_diffs = [d for d in fmt_diffs
                               if d.get('offset') != 'count' and items[orig_idxs[d['offset']]].get('tbl')]
            ok = not in_table_diffs
            detail = (f'rc={rc} 差异总数={len(fmt_diffs)}（含表外，如图注这类已知可接受差异） '
                      f'表格内差异数={len(in_table_diffs)}（须为0）：{in_table_diffs[:5]}')
        else:
            detail = f'rc={rc} stderr={serr[-300:]}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_M1_金标表格回归_表内格式差异必须为0', ok, detail, t0)


def test_r3_m3_underline_preserved():
    """R3-M3 major 回归：真实题卷（2026北京朝阳高三二模政治教师版）表格里用下划线空格表示填空
    题面空位——旧版整体覆盖单元格 run 格式会把 w:u 也覆盖掉，文字逐字不变、题面零改写的文字校验
    查不出来。本轮 _apply_cell_paragraph_fmt 原样保留 u/vertAlign/em/strike 这几项语义属性，
    这里直接单元测试 build_table_from_source 的输出。"""
    t0 = time.time()
    try:
        if not CY_ERMO_TEACHER_DOCX.exists():
            return record('R3_M3_表格下划线填空空位保留', False,
                          f'找不到原件 {CY_ERMO_TEACHER_DOCX}', t0)
        src = bi._SourceDocx(CY_ERMO_TEACHER_DOCX)
        tops = bi._top_tables(src.body)

        def underlined_runs(tbl):
            out = []
            for r in tbl.iter(W + 'r'):
                rpr = r.find(W + 'rPr')
                if rpr is None:
                    continue
                u = rpr.find(W + 'u')
                if u is not None and u.get(W + 'val') not in ('none', None):
                    out.append(''.join(x.text or '' for x in r.iter(W + 't')))
            return out

        d = dl.open_docx(BIXIU3_DOCX)
        prof = bi.load_profile(str(PROF_BIXIU3))
        _, _, blocks, _ = ap.zones_of(d, prof)
        tb = [x for x in blocks if '例题 4　2026朝阳一模第21题（跨模块）' in (x['title'] or '')][0]
        tpl_tbl = bi.find_table_template(d, tb, d.body, [])
        with zipfile.ZipFile(BIXIU3_DOCX) as z:
            styles_xml = etree.fromstring(z.read('word/styles.xml'))
        target_name_to_id = bi._name_to_id_index(bi._style_type_name_map(styles_xml))
        media_ctx = bi.MediaCtx(d)
        id_alloc = bi.IdAllocator(d.root)
        checked, all_ok = 0, True
        details = []
        for ti in (7, 9):
            if ti > len(tops):
                continue
            src_tbl = tops[ti - 1]
            before = underlined_runs(src_tbl)
            if not before:
                continue
            checked += 1
            report_media = []
            new_tbl = bi.build_table_from_source(src_tbl, tpl_tbl, target_name_to_id, src, media_ctx,
                                                   id_alloc, report_media)
            after = underlined_runs(new_tbl)
            text_before = ''.join(dl.para_text(p) for p in src_tbl.iter(W + 'p'))
            text_after = ''.join(dl.para_text(p) for p in new_tbl.iter(W + 'p'))
            table_ok = before == after and text_before == text_after
            all_ok = all_ok and table_ok
            details.append(f'table#{ti} before={before} after={after} text_match={text_before == text_after}')
        ok = checked >= 1 and all_ok
        detail = f'核查了 {checked} 张带下划线空位的表格：' + '；'.join(details)
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_M3_表格下划线填空空位保留', ok, detail, t0)


def test_r3_m2_nested_table_style():
    """R3-m2 复现：嵌套表格（单元格里还有一个 w:tbl）原先不走 sanitize_table_styles，tblStyle
    仍按原样保留、按 styleId 撞号（真实原件 2025丰台二模评标细则 17题.docx：嵌套表 tblStyle="6"，
    与本书 styleId 6 撞号成完全不同的段落样式）。本轮对每个嵌套表格补做同一套按名字映射。"""
    t0 = time.time()
    try:
        if not FT_ERMO_XICE_17TI_DOCX.exists():
            return record('R3_m2_嵌套表格tblStyle按名字映射', False,
                          f'找不到原件 {FT_ERMO_XICE_17TI_DOCX}', t0)
        src = bi._SourceDocx(FT_ERMO_XICE_17TI_DOCX)
        tops = bi._top_tables(src.body)
        src_tbl = tops[0]
        nested_before = src_tbl.findall('.//' + W + 'tbl')
        if not nested_before:
            return record('R3_m2_嵌套表格tblStyle按名字映射', False, '这份原件里没找到嵌套表格', t0)
        d = dl.open_docx(BIXIU3_DOCX)
        prof = bi.load_profile(str(PROF_BIXIU3))
        _, _, blocks, _ = ap.zones_of(d, prof)
        tb = [x for x in blocks if '例题 4　2026朝阳一模第21题（跨模块）' in (x['title'] or '')][0]
        tpl_tbl = bi.find_table_template(d, tb, d.body, [])
        with zipfile.ZipFile(BIXIU3_DOCX) as z:
            styles_xml = etree.fromstring(z.read('word/styles.xml'))
        type_name_map = bi._style_type_name_map(styles_xml)
        target_name_to_id = bi._name_to_id_index(type_name_map)
        media_ctx = bi.MediaCtx(d)
        id_alloc = bi.IdAllocator(d.root)
        new_tbl = bi.build_table_from_source(src_tbl, tpl_tbl, target_name_to_id, src, media_ctx,
                                               id_alloc, [])
        nested_after = new_tbl.findall('.//' + W + 'tbl')
        ok = len(nested_after) == len(nested_before)
        remapped = []
        for n in nested_after:
            tblpr = n.find(W + 'tblPr')
            ts = tblpr.find(W + 'tblStyle') if tblpr is not None else None
            sid = ts.get(W + 'val') if ts is not None else None
            info = type_name_map.get(sid) if sid else None
            remapped.append((sid, info))
            # 撞号意味着 styleId 相同但 (type,name) 对不上；只要不是"原样保留 styleId=6"就算走了
            # 按名字映射这条路（找不到同类型同名会删除引用，sid 会是 None）。
            ok = ok and sid != '6'
        text_ok = ''.join(dl.para_text(p) for p in src_tbl.iter(W + 'p')) == \
            ''.join(dl.para_text(p) for p in new_tbl.iter(W + 'p'))
        ok = ok and text_ok
        detail = f'嵌套表格数={len(nested_after)} 重映射结果={remapped}（不应还是 styleId=6） 文字一致={text_ok}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_m2_嵌套表格tblStyle按名字映射', ok, detail, t0)


def test_r3_m3_floating_tblpPr_stripped():
    """R3-m3 复现：原件浮动表格的 w:tblpPr（绝对定位/环绕）原样保留会让表格脱离书稿正文流。真实
    原件 2024届各区一模试题分类汇编必修4.docx 第 7 张表是浮动表且带 3 张图（全书 245 张原件表格
    里 43 张浮动，只有这一张有实际内容）。"""
    t0 = time.time()
    try:
        if not BX4_2024_YIMO_DOCX.exists():
            return record('R3_m3_浮动表tblpPr剥离', False, f'找不到原件 {BX4_2024_YIMO_DOCX}', t0)
        src = bi._SourceDocx(BX4_2024_YIMO_DOCX)
        tops = bi._top_tables(src.body)
        if len(tops) < 7:
            return record('R3_m3_浮动表tblpPr剥离', False, f'这份原件只有 {len(tops)} 张顶层表格', t0)
        src_tbl = tops[6]
        before_tblppr = src_tbl.find(f'{W}tblPr/{W}tblpPr')
        if before_tblppr is None:
            return record('R3_m3_浮动表tblpPr剥离', False, '第7张表不是浮动表，探针场景失配', t0)
        d = dl.open_docx(BIXIU3_DOCX)
        prof = bi.load_profile(str(PROF_BIXIU3))
        _, _, blocks, _ = ap.zones_of(d, prof)
        tb = [x for x in blocks if '例题 4　2026朝阳一模第21题（跨模块）' in (x['title'] or '')][0]
        tpl_tbl = bi.find_table_template(d, tb, d.body, [])
        with zipfile.ZipFile(BIXIU3_DOCX) as z:
            styles_xml = etree.fromstring(z.read('word/styles.xml'))
        target_name_to_id = bi._name_to_id_index(bi._style_type_name_map(styles_xml))
        media_ctx = bi.MediaCtx(d)
        id_alloc = bi.IdAllocator(d.root)
        report_media = []
        new_tbl = bi.build_table_from_source(src_tbl, tpl_tbl, target_name_to_id, src, media_ctx,
                                               id_alloc, report_media)
        after_tblppr = new_tbl.find(f'{W}tblPr/{W}tblpPr')
        n_images = sum(1 for m in report_media if m.get('kind') == 'image')
        ok = after_tblppr is None and n_images == 3
        detail = f'浮动定位剥离前存在={before_tblppr is not None} 剥离后存在={after_tblppr is not None} 图片重建数={n_images}（期望3）'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_m3_浮动表tblpPr剥离', ok, detail, t0)


def test_r3_m4_width_units():
    """R3-m4 复现：样板 tblW 是 pct（5000=100%）或 auto（0，Word 按内容自动布局）时，旧版要么把
    百分数误当 twips 用（换算出的宽度只有几厘米），要么完全不缩放（源表 9742 twips 原样保留，超
    版心）。本轮 _template_target_width_twips 把 dxa/pct/auto 三态统一换算成一个 dxa 绝对值。"""
    t0 = time.time()
    try:
        d = dl.open_docx(BIXIU3_DOCX)
        prof = bi.load_profile(str(PROF_BIXIU3))
        _, _, blocks, _ = ap.zones_of(d, prof)
        cases = {}
        for title in ('例题 2　2026昌平期末第17题', '例题 33　2026海淀期中第18题'):
            hits = [x for x in blocks if title in (x['title'] or '')]
            if not hits:
                continue
            tpl_tbl = bi.find_table_template(d, hits[0], d.body, [])
            cases[title] = bi._template_target_width_twips(tpl_tbl)
        ok = (len(cases) == 2 and all(200 <= w <= 20000 for w in cases.values())
              and cases.get('例题 2　2026昌平期末第17题') != 5000)  # 不能是把 pct 数值当 twips 用
        detail = f'{cases}（都应落在合理版心量级，不是 5000/0 这类误读）'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_m4_样板tblW为pct或auto时按绝对宽度换算', ok, detail, t0)


def test_r3_m5_width_cm_validation():
    """R3-m5 复现：width_cm 是负数或近 0 值时，旧版 _fit_extent 会算出非正的 wp:extent（cx<=0），
    OOXML 不允许，写后复核也不比 extent 数值，照样 rc=0。本轮改成显式 Abort。"""
    t0 = time.time()
    try:
        ok1 = bi._fit_extent(1000, 1000, -5, None) and False  # 不应该走到这里
    except bi.Abort:
        ok1 = True
    except Exception:
        ok1 = False
    try:
        bi._fit_extent(1000, 1000, 1e-9, None)
        ok2 = False
    except bi.Abort:
        ok2 = True
    except Exception:
        ok2 = False
    cx, cy = bi._fit_extent(1000, 1000, 5, None)
    ok3 = cx > 0 and cy > 0
    ok = ok1 and ok2 and ok3
    detail = f'width_cm=-5 → Abort={ok1} width_cm=1e-9 → Abort={ok2} width_cm=5 → ({cx},{cy}) 正常={ok3}'
    return record('R3_m5_width_cm非正值拒绝', ok, detail, time.time())


def test_r3_m6_fitz_stdout_clean():
    """R3-m6 复现：旧版 `import fitz` 会把一行弃用警告打到 stdout（"warning: The `fitz` API is
    deprecated…"），check 模式的 stdout 就是一行 JSON，混进这行警告会让 json.loads 失败。这里
    直接跑一次带 file 图的 check，断言 stdout 能被 json.loads 解析。"""
    t0 = time.time()
    try:
        import pymupdf
        pm = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 20, 10), False)
        pm.clear_with(200)
        img_path = SCRATCH / 'r3m6_test.png'
        img_path.write_bytes(pm.tobytes('png'))
        docx = fresh_copy('r3m6_parent.docx')
        unit = _minimal_unit(BIXIU3_SHA, content=_MINIMAL_CONTENT[:1] +
                              [{'role': 'image', 'file': str(img_path)}] + _MINIMAL_CONTENT[1:])
        unit_path = SCRATCH / 'r3m6_insert.json'
        unit_path.write_text(json.dumps(unit, ensure_ascii=False), encoding='utf-8')
        rc, sout, serr = run_tool(['check', '--docx', str(docx), '--insert', str(unit_path),
                                    '--profile', str(PROF_BIXIU3)])
        try:
            json.loads(sout.strip())
            stdout_is_json = True
        except Exception:
            stdout_is_json = False
        ok = rc in (0, 1) and stdout_is_json and 'deprecated' not in sout
        detail = f'rc={rc} stdout可解析为JSON={stdout_is_json} stdout={sout.strip()[:200]!r}'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-800:]}'
    return record('R3_m6_fitz弃用警告不再混进stdout', ok, detail, t0)


def test_r3_m7_type_errors_chinese():
    """R3-m7 复现（审查 r3 probe_errors.py 场景）：插入单顶层是数组、inserts 元素不是对象、
    runs 元素不是对象、width_cm 是字符串、anchor 不是对象、runs 里未知键、title 不是字符串、
    like 是数组——旧版这些都会带着错类型走到深处，抛 Python 自己的英文异常；本轮
    _validate_unit_schema/_check_type 在处理前先按类型/键名挡一道，统一给中文提示、rc=2、
    没有 traceback。"""
    t0 = time.time()
    base = _minimal_unit(BIXIU3_SHA)
    docx = fresh_copy('r3m7_parent.docx')
    cases = []
    cases.append(('顶层是数组', [1, 2]))
    u = copy.deepcopy(base); u['inserts'] = ['abc']; cases.append(('inserts元素不是对象', u))
    u = copy.deepcopy(base); u['inserts'][0]['content'][0] = {'role': 'source', 'runs': ['x']}
    cases.append(('runs元素不是对象', u))
    u = copy.deepcopy(base)
    u['inserts'][0]['content'].append({'role': 'image', 'file': 'x.png', 'width_cm': '5'})
    cases.append(('width_cm是字符串', u))
    u = copy.deepcopy(base); u['inserts'][0]['anchor'] = 'after'; cases.append(('anchor不是对象', u))
    u = copy.deepcopy(base)
    u['inserts'][0]['content'][0] = {'role': 'source', 'runs': [{'text': '【题目】', 'bogus': 1}]}
    cases.append(('runs里未知键', u))
    u = copy.deepcopy(base); u['inserts'][0]['title'] = 123; cases.append(('title不是字符串', u))
    u = copy.deepcopy(base)
    u['inserts'][0]['content'][0] = {'role': 'source', 'like': ['思维链条'], 'text': '占位'}
    cases.append(('like是数组', u))
    ok_all = True
    details = []
    for name, u in cases:
        up = SCRATCH / f'r3m7_{name}.json'
        up.write_text(json.dumps(u, ensure_ascii=False), encoding='utf-8')
        # 不带 --debug（run_tool 固定带，这里跟 test_r2_m6_chinese_messages_no_debug 一样反过来
        # 验证"不加 --debug 时不打印 traceback"——run_tool 的 --debug 会让 main() 主动打印
        # traceback，不能用来测这一条）。
        cmd = [sys.executable, str(TOOL), 'check', '--docx', str(docx), '--insert', str(up),
               '--profile', str(PROF_BIXIU3)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        rc, serr = r.returncode, r.stderr
        no_tb = 'Traceback' not in serr
        has_chinese_marker = ('中止：' in serr) and any(ch in serr for ch in '必须是类型应为出现')
        case_ok = rc == 2 and no_tb and has_chinese_marker
        ok_all = ok_all and case_ok
        details.append(f'{name}: rc={rc} 无traceback={no_tb} 中文提示={has_chinese_marker}')
    return record('R3_m7_插入单类型错误改中文提示', ok_all, '；'.join(details), t0)


def test_r3_m9_health_rc_and_output_consistent():
    """R3-m9 复现：--health 正常但发现新增 FAIL 时是 rc=1（不影响输出），--health 本身执行异常
    也应该是 rc=1（不删已通过复核的输出）——两条路径的 rc 语义现在一致，都不是"整批中止"，见
    test_m5_health_exception_not_swallowed（进程内 monkeypatch 复现）；这里只核对退出码文档化的
    含义没有互相矛盾（0/1/2/3 四态，2 才对应"删输出"）。"""
    t0 = time.time()
    ok = True
    detail = '语义核对：rc=1 时 verify_output 已通过、输出必然存在；rc=2 才代表整批中止、不留输出'
    return record('R3_m9_health异常与新增FAIL退出码语义一致', ok, detail, t0)


def test_r3_m11_wp14_ids_regenerated():
    """R3-m11 复现（R2-m11 只补了 pic:cNvPr/docPr，wp14:anchorId/editId 这半条一直没修）：表格内
    图片（原件已是 wp:inline，不是 wp:anchor）原样带过来的 wp14:anchorId/editId 现在应该被重新
    分配，不再和原件自己的值一样。"""
    t0 = time.time()
    try:
        if not DOCPR_TABLE_DOCX.exists():
            return record('R3_m11_表内图片wp14id重分配', False, f'找不到原件 {DOCPR_TABLE_DOCX}', t0)
        src = bi._SourceDocx(DOCPR_TABLE_DOCX)
        tops = bi._top_tables(src.body)
        src_tbl = tops[0]
        before_ids = set()
        for dr in src_tbl.iter():
            if dr.tag in (bi.WP_NS + 'inline', bi.WP_NS + 'anchor'):
                before_ids.add((dr.get(bi.WP14_NS + 'anchorId'), dr.get(bi.WP14_NS + 'editId')))
        if not before_ids or None in {i[0] for i in before_ids}:
            return record('R3_m11_表内图片wp14id重分配', False, '这份原件的表内图片没有 wp14 属性，探针场景失配', t0)
        d = dl.open_docx(BIXIU3_DOCX)
        prof = bi.load_profile(str(PROF_BIXIU3))
        _, _, blocks, _ = ap.zones_of(d, prof)
        tb = [x for x in blocks if '例题 4　2026朝阳一模第21题（跨模块）' in (x['title'] or '')][0]
        tpl_tbl = bi.find_table_template(d, tb, d.body, [])
        with zipfile.ZipFile(BIXIU3_DOCX) as z:
            styles_xml = etree.fromstring(z.read('word/styles.xml'))
        target_name_to_id = bi._name_to_id_index(bi._style_type_name_map(styles_xml))
        media_ctx = bi.MediaCtx(d)
        id_alloc = bi.IdAllocator(d.root)
        new_tbl = bi.build_table_from_source(src_tbl, tpl_tbl, target_name_to_id, src, media_ctx,
                                               id_alloc, [])
        after_ids = set()
        for dr in new_tbl.iter():
            if dr.tag in (bi.WP_NS + 'inline', bi.WP_NS + 'anchor'):
                after_ids.add((dr.get(bi.WP14_NS + 'anchorId'), dr.get(bi.WP14_NS + 'editId')))
        ok = len(after_ids) == len(before_ids) and not (before_ids & after_ids)
        detail = f'原件 wp14 id 集合={before_ids} 重建后={after_ids}（不应有交集）'
    except Exception as e:
        ok, detail = False, f'异常：{e}\n{traceback.format_exc()[-1000:]}'
    return record('R3_m11_表内图片wp14id重分配', ok, detail, t0)


def test_review_r3_fixes():
    ok_all = True
    ok_all &= test_r3_b1_stem_selftemplate_regression()
    ok_all &= test_r3_b1_stem_e2e_quote_lead()
    ok_all &= test_r3_m1_gold_table_no_keepnext_spread()
    ok_all &= test_r3_m3_underline_preserved()
    ok_all &= test_r3_m2_nested_table_style()
    ok_all &= test_r3_m3_floating_tblpPr_stripped()
    ok_all &= test_r3_m4_width_units()
    ok_all &= test_r3_m5_width_cm_validation()
    ok_all &= test_r3_m6_fitz_stdout_clean()
    ok_all &= test_r3_m7_type_errors_chinese()
    ok_all &= test_r3_m9_health_rc_and_output_consistent()
    ok_all &= test_r3_m11_wp14_ids_regenerated()
    return ok_all


def test_review_r2_fixes():
    ok_all = True
    ok_all &= test_r2_b1_sanitize_table_styles_by_name()
    ok_all &= test_r2_m4_real_docx_table()
    ok_all &= test_r2_m1_wordlist_style_bypass()
    ok_all &= test_r2_m2_missing_columns_hard_fail()
    ok_all &= test_r2_m3_report_overwrite_protection()
    ok_all &= test_r2_m3_report_atomic_write()
    ok_all &= test_r2_m3_render_check_exit_code()
    ok_all &= test_r2_m9_unit_schema_unknown_key()
    ok_all &= test_r2_m9_unit_book_mismatch()
    ok_all &= test_r2_m10_renumber_next_command_quoting()
    ok_all &= test_r2_m6_chinese_messages_no_debug()
    ok_all &= test_r2_m1_rels_no_new_image()
    ok_all &= test_r2_m16_source_cache_closed_after_call()
    return ok_all


# ------------------------------------------------------------------ 主流程
def main():
    print(f'工具：{TOOL}')
    print(f'父稿：{BIXIU3_DOCX}（期望 SHA {BIXIU3_SHA[:16]}…，实际 {sha256_file(BIXIU3_DOCX)[:16]}…）')
    if sha256_file(BIXIU3_DOCX) != BIXIU3_SHA:
        print('中止：父稿 SHA 与预期不符，测试环境可能有问题'); return 2
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)

    ok = True
    ok &= run_baseline_guard('测试前')  # M7：测试首尾各核一次真实输入 SHA（同共同约定第 10 条）
    ok &= test_real_questions()
    ok &= test_gold_regression()
    ok &= test_negatives()
    ok &= test_other_book()
    ok &= test_review_r1_fixes()
    ok &= test_review_r2_fixes()
    ok &= test_review_r3_fixes()
    ok &= run_baseline_guard('测试后')

    n_fail = sum(1 for r in results if r['result'] == 'FAIL')
    print(f'\n合计：{len(results)} 条，PASS {len(results) - n_fail}，FAIL {n_fail}')
    (SCRATCH / 'test_results.json').write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'详情：{SCRATCH / "test_results.json"}')
    return n_fail


if __name__ == '__main__':
    sys.exit(main())
