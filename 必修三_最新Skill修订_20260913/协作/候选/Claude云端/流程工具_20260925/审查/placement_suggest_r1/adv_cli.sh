#!/bin/bash
# 对抗用例：placement_suggest CLI（只读；产物只落本目录）
C=/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925
T=$C/placement_suggest.py
P=$C/profiles_cloud/bixiu3.json
FZ=$C/profiles_cloud/bixiu2_frozen_test.json
BOOK=/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx
R=/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_placement_suggest_r1/adv
rm -rf $R; mkdir -p $R
run() { name="$1"; shift; python3 $T "$@" > $R/$name.out 2> $R/$name.err; code=$?; echo "== $name exit=$code"; head -c 400 $R/$name.err; echo; }
run A01_no_docx_arg --profile $P --key BJ-2024-DC-ERMO-Q18
run A02_docx_missing --docx $R/nosuch.docx --profile $P --key BJ-2024-DC-ERMO-Q18
echo notzip > $R/fake.docx
run A03_docx_not_zip --docx $R/fake.docx --profile $P --key BJ-2024-DC-ERMO-Q18
run A04_profile_missing --docx $BOOK --profile $R/nosuch.json --key BJ-2024-DC-ERMO-Q18
run A05_profile_name_unknown --docx $BOOK --profile nosuchbook --key BJ-2024-DC-ERMO-Q18
echo '{bad json' > $R/bad.json
run A06_profile_bad_json --docx $BOOK --profile $R/bad.json --key BJ-2024-DC-ERMO-Q18
run A07_params_bad_json --docx $BOOK --profile $P --key BJ-2024-DC-ERMO-Q18 --params $R/bad.json
run A08_topk_negative --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --top-k -1 --report $R/A08.json
python3 -c "import json;r=json.load(open('$R/A08.json'));print('A08 n candidates with --top-k -1:',len(r['results'][0]['candidates']))"
run A09_key_fullwidth_paren --docx $BOOK --profile $P --key 'BJ-2024-DC-ERMO-Q18（2）'
run A10_key_traversal --docx $BOOK --profile $P --key '../../../tmp/x/evil-Q1'
: > $R/empty.txt
run A11_text_empty --docx $BOOK --profile $P --text $R/empty.txt --report $R/A11.json
python3 -c "import json;r=json.load(open('$R/A11.json'));x=r['results'][0];print('A11 empty text -> candidates',[ (c['label'],c['score']) for c in x['candidates']], 'flags', x['flags'])"
echo 'The quick brown fox jumps over the lazy dog.' > $R/english.txt
run A12_text_nomatch --docx $BOOK --profile $P --text $R/english.txt --kind choice --report $R/A12.json
python3 -c "import json;r=json.load(open('$R/A12.json'));x=r['results'][0];print('A12 no-overlap text -> candidates',[ (c['label'][:30],c['score']) for c in x['candidates']], 'flags', x['flags'])"
# atomicity: md --out ok, --report refused
run A13_md_out_ok_report_bad --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --format md --out $R/A13.md --report /home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/A13_should_not_exist.json
ls -la $R/A13.md 2>&1; ls /home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/A13_should_not_exist.json 2>&1
# --out silently ignored in json mode
run A14_out_json_mode --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --out $R/A14.md
ls $R/A14.md 2>&1
# symlink escape
ln -s /home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913 $R/link_to_book_dir
run A15_symlink_escape --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --report $R/link_to_book_dir/evil.json
ls /home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/evil.json 2>&1
# report over existing file
echo '{}' > $R/exists.json
run A16_report_exists --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --report $R/exists.json
cat $R/exists.json
# report into Skill dir
run A17_report_into_skill --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --report /home/user/zhengzhibaodianzhizuo/.claude/skills/beijing-gaokao-politics/x.json
ls /home/user/zhengzhibaodianzhizuo/.claude/skills/beijing-gaokao-politics/x.json 2>&1
# report into bank
run A18_report_into_bank --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --report /home/user/zhengzhibaodianzhizuo/DeepSeek_政治题库资料库_20260918/x.json
# report == docx path (kind check)
run A19_report_is_docx --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --report $BOOK
# frozen read-only (no write) should run
run A20_frozen_readonly --docx $BOOK --profile $FZ --key BJ-2026-HD-ERMO-Q11
# frozen + md out
run A21_frozen_md_out --docx $BOOK --profile $FZ --key BJ-2026-HD-ERMO-Q11 --format md --out $R/A21.md
ls $R/A21.md 2>&1
# expect-sha correct
run A22_expect_sha_ok --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --expect-sha C007D7198422050CDF47D1EC679A097D0B350F1BFB9C70D41672103780F76EB6
# keys-file with BOM
printf '\xef\xbb\xbfBJ-2026-HD-ERMO-Q11\n' > $R/bom.txt
run A23_keysfile_bom --docx $BOOK --profile $P --keys-file $R/bom.txt
run A24_keysfile_missing --docx $BOOK --profile $P --keys-file $R/nosuch.txt
# md with no stem heading
printf '# X\n\n## 身份\n- 题型：非选择题\n\n## 其他\n文字\n' > $R/nostem.md
run A25_md_no_stem --docx $BOOK --profile $P --md $R/nostem.md
# synthetic subjective with A-D lettered opinions and NO E1 -> should be flagged 不收
cat > $R/synthetic_subj_noe1.md <<'MD'
# BJ-2099-XX-YIMO-Q18

## 身份信息
- 题型：非选择题

## 题面
18．（10分）某市围绕公园管理征求市民意见。市民观点如下：
A．公园里骑车撞到老人和小孩怎么办？
B．在公园里骑车赏景是很好的休闲方式。
C．没有滑板车，小孩子逛公园太累了。
D．商拍占道占景，影响游览体验。
结合材料，运用《政治与法治》知识，就完善公园管理提出建议。

## 正式评分材料原文
（未找到已确认的正式评分材料；见下方候选区）
MD
run A26_subj_letters_noE1 --docx $BOOK --profile $P --md $R/synthetic_subj_noe1.md --report $R/A26.json
python3 -c "import json;r=json.load(open('$R/A26.json'));x=r['results'][0];print('A26 kind=',x['kind'],'kind_field=',x['kind_field_raw'],'e1_present=',x['e1_present'],'flags=',x['flags'],'top=',[c['most_similar_block']['title'] for c in x['candidates']])"
# key already in book: silent exclusion?
run A27_key_already_in_book --docx $BOOK --profile $P --key BJ-2026-HD-ERMO-Q11 --format md
cat $R/A27_key_already_in_book.out
