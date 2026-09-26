#!/bin/sh
# r2 审查：--exam-dir 探针所需的题库外副本（只在临时区复制，不改题库）。本地复现时把 S、B 改成本机路径。
S=/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_exam_register_r2
B=/home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918/questions
rm -rf "$S/examdir"; mkdir -p "$S/examdir"
cp -r "$B/BJ-2026-HD-QIMO"    "$S/examdir/新卷_HDQIMO"        # E1：README 写明“海淀区 2025-2026 学年高三第一学期期末练习”
cp -r "$B/BJ-2025-HD-QIZHONG" "$S/examdir/新卷_HDQZ25"        # E2
cp -r "$B/BJ-2024-HD-QIZHONG" "$S/examdir/BJ-2024-HD-QIZHONG" # E3：README 写明“2024—2025学年…2024.11”
cp -r "$B/BJ-2025-CY-YIMO"    "$S/examdir/新卷_CYYIMO"        # D1：21 题里只有 Q18 抽得出题面
cp "$B/BJ-2026-HD-QIZHONG/BJ-2026-HD-QIZHONG-Q17.md" "$S/examdir/新卷_CYYIMO/BJ-2025-CY-YIMO-Q18.md"  # 仅这 1 题复用他卷
# D1 复现：python3 -B exam_register.py check --exam-dir "$S/examdir/新卷_CYYIMO" --region 朝阳 --stage 一模 --profile profiles_cloud/bixiu3.json
#   → duplicates=[BJ-2026-HD-QIZHONG duplicate_registration 1/1 fraction_reliable=true]
