#!/bin/bash
# placement_suggest r4 对抗 CLI 探针（只读；输出只落 系统临时目录 或 C/构建/placement_suggest/r4probe_*）
C=/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925
R=/home/user/zhengzhibaodianzhizuo
T=$C/placement_suggest.py
P=$C/profiles_cloud/bixiu3.json
FZ=$C/profiles_cloud/bixiu2_frozen_test.json
B=$R/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx
S=/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_placement_suggest_r4
BO=$C/构建/placement_suggest
rm -rf $S; mkdir -p $S
rm -f $BO/r4probe_* $BO/.r4probe_*
probe() { # name, args...
  local name=$1; shift
  local t0=$(date +%s.%N)
  python3 $T "$@" > $S/out.txt 2> $S/err.txt; local code=$?
  local tb=$(grep -c "Traceback" $S/err.txt)
  echo "=== $name exit=$code traceback=$tb dt=$(echo "$(date +%s.%N) - $t0" | bc)"
  echo "   args: $*" | cut -c1-300
  echo "   stderr: $(head -c 600 $S/err.txt | tr '\n' ' ')"
  echo "   stdout: $(head -c 900 $S/out.txt | tr '\n' ' ')"
}
probe B01_twin_Q9 --docx $B --profile $P --key BJ-2025-HD-QIZHONG-Q9 --format md
probe B02_twin_Q19 --docx $B --profile $P --key BJ-2025-HD-QIZHONG-Q19 --format md
probe B03_twin_Q7 --docx $B --profile $P --key BJ-2025-HD-QIZHONG-Q7
probe B04_e1_DC_ERMO_Q17 --docx $B --profile $P --key BJ-2024-DC-ERMO-Q17
probe B05_e1_FT_ERMO_Q18 --docx $B --profile $P --key BJ-2024-FT-ERMO-Q18
probe B06_frozen_out --docx $B --profile $FZ --key BJ-2020-BJ-GAOKAO-Q1 --format md --out $BO/r4probe_frozen.md
ls $BO/r4probe_frozen.md 2>/dev/null && echo "   !! frozen out file exists"
probe B07_frozen_readonly --docx $B --profile $FZ --key BJ-2020-BJ-GAOKAO-Q1
# symlinked directory inside 构建 pointing to 云端/
ln -sfn $R/云端 $BO/r4probe_linkdir
probe B08_report_symlink_dir --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --report $BO/r4probe_linkdir/r4probe_x.json
ls $R/云端/r4probe_x.json 2>/dev/null && echo "   !! wrote into 云端/"
rm -f $BO/r4probe_linkdir
# path traversal out of 构建 via ..
probe B09_report_dotdot --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --report $BO/../../审查/r4probe_dotdot.json
ls $C/审查/r4probe_dotdot.json 2>/dev/null && echo "   !! wrote outside 构建"
# into skill dir
probe B10_report_skill --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --report $R/.claude/skills/beijing-gaokao-politics/r4probe.json
ls $R/.claude/skills/beijing-gaokao-politics/r4probe.json 2>/dev/null && echo "   !! wrote into skill"
# system temp dir allowed
probe B11_report_tmp --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --report $S/r4_ok.json
ls -la $S/r4_ok.json
# existing target
probe B12_report_exists --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --report $S/r4_ok.json
# --out good + --report bad → nothing written
probe B13_out_ok_report_bad --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --format md --out $S/r4_md.md --report $R/云端/r4probe_bad.json
ls $S/r4_md.md $R/云端/r4probe_bad.json 2>/dev/null && echo "   !! partial output left"
# empty text input
: > $S/empty.txt
probe B14_text_empty --docx $B --profile $P --text $S/empty.txt
printf '   \n\n' > $S/blank.txt
probe B15_text_blank --docx $B --profile $P --text $S/blank.txt
# binary md
head -c 2000 /dev/urandom > $S/bin.md
probe B16_md_binary --docx $B --profile $P --md $S/bin.md
# key traversal
probe B17_key_traversal --docx $B --profile $P --key '../../../etc/passwd-Q1'
# profile = empty object
echo '{}' > $S/empty_profile.json
probe B18_profile_empty --docx $B --profile $S/empty_profile.json --key BJ-2020-BJ-GAOKAO-Q1
# profile missing styles
python3 - "$P" "$S/nostyles.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1])); p.pop('styles',None); json.dump(p,open(sys.argv[2],'w'),ensure_ascii=False)
PY
probe B19_profile_nostyles --docx $B --profile $S/nostyles.json --key BJ-2020-BJ-GAOKAO-Q1
python3 - "$P" "$S/nocols.json" <<'PY'
import json,sys
p=json.load(open(sys.argv[1]))
for k in ('column_schemas','labels','labels_rules','structure'):
    p.pop(k,None)
json.dump(p,open(sys.argv[2],'w'),ensure_ascii=False)
PY
probe B20_profile_nocols --docx $B --profile $S/nocols.json --key BJ-2020-BJ-GAOKAO-Q1
# correct expect-sha
probe B21_expect_sha_ok --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --expect-sha c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6
# expect-sha mismatch + --report → no file
probe B22_sha_bad_report --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --expect-sha deadbeef --report $S/r4_sha_bad.json
ls $S/r4_sha_bad.json 2>/dev/null && echo "   !! report left after sha mismatch"
# bad key in keys-file after good key + report → no report
printf 'BJ-2020-BJ-GAOKAO-Q1\nBJ-2099-NOPE-YIMO-Q1\n' > $S/keys_bad.txt
probe B23_keysfile_partial_bad --docx $B --profile $P --keys-file $S/keys_bad.txt --report $S/r4_kf_bad.json
ls $S/r4_kf_bad.json 2>/dev/null && echo "   !! report left after bad key"
# docx that is a directory
probe B24_docx_dir --docx $S --profile $P --key BJ-2020-BJ-GAOKAO-Q1
# xuanbi1 draft profile
XB=$(ls $R/其他书工作头/选必一/*.docx)
probe B25_xuanbi1 --docx "$XB" --profile $C/profiles_cloud/xuanbi1.draft.json --key BJ-2024-HD-YIMO-Q20 --format md
# --text copy of an in-book block text → dup?
probe B26_top_k_zero --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --top-k 0
probe B27_max_chars_zero --docx $B --profile $P --key BJ-2020-BJ-GAOKAO-Q1 --max-chars 0
probe B28_subq_key --docx $B --profile $P --key 'BJ-2024-DC-ERMO-Q17(1)'
probe B29_md_no_key_name --docx $B --profile $P --md $R/DeepSeek_政治题库资料库_20260918/questions/BJ-2025-HD-QIZHONG/README.md
ls -la $BO | grep -i r4probe
find $R/.claude -name __pycache__
ls $C/__pycache__ 2>/dev/null
