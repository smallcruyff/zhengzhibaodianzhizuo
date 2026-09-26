#!/bin/bash
# 对抗 CLI 探针（第 3 轮）；只写 SCR 与 C/构建/placement_suggest/r3adv_*
C=/home/user/zhengzhibaodianzhizuo/必修三_最新Skill修订_20260913/协作/候选/Claude云端/流程工具_20260925
R=/home/user/zhengzhibaodianzhizuo
BOOK=$R/必修三_最新Skill修订_20260913/必修三政治与法治宝典_R31续修_第52批_阶段审查稿.docx
P=$C/profiles_cloud/bixiu3.json
FZ=$C/profiles_cloud/bixiu2_frozen_test.json
SCR=/tmp/claude-0/-home-user-zhengzhibaodianzhizuo/2415817c-761f-5954-bb79-9bc9fa3464ca/scratchpad/review_placement_suggest_r3/adv
B=$C/构建/placement_suggest
rm -rf $SCR; mkdir -p $SCR; rm -f $B/r3adv_* $B/.r3adv_*
T="python3 $C/placement_suggest.py --docx $BOOK"
K=BJ-2020-BJ-GAOKAO-Q1
run(){ name="$1"; shift; out=$("$@" 2>$SCR/err.txt >$SCR/out.txt; echo $?); echo "== $name exit=$out"; head -c 300 $SCR/err.txt | tr '\n' ' '; echo; grep -c Traceback $SCR/err.txt | sed 's/^/   traceback_lines=/'; }
run "B01 frozen + --out (md)" $T --profile $FZ --key $K --format md --out $B/r3adv_frozen.md
ls $B/r3adv_frozen.md 2>/dev/null && echo "   !! file written"
run "B02 frozen read-only (no write)" $T --profile $FZ --key $K
ln -sf $R/云端/同步清单.json $B/r3adv_link.json
sha_before=$(sha256sum $R/云端/同步清单.json | cut -c1-16)
run "B03 --report = symlink in 构建/ -> 云端/同步清单.json" $T --profile $P --key $K --report $B/r3adv_link.json
echo "   sync manifest sha before=$sha_before after=$(sha256sum $R/云端/同步清单.json | cut -c1-16); link still symlink: $(test -L $B/r3adv_link.json && echo yes || echo no)"
rm -f $B/r3adv_link.json
echo x > $B/r3adv_exists.json
run "B04 --report existing file" $T --profile $P --key $K --report $B/r3adv_exists.json
echo "   content now: $(cat $B/r3adv_exists.json | head -c 20)"
rm -f $B/r3adv_exists.json
run "B05 --report nonexistent subdir" $T --profile $P --key $K --report $B/no_such_dir/r.json
run "B06 --out with .json suffix under --format md" $T --profile $P --key $K --format md --out $B/r3adv_x.json
echo '{"agg_top_k": 2.5}' > $SCR/p1.json
run "B07 --params agg_top_k=2.5 (float)" $T --profile $P --key $K --params $SCR/p1.json
echo '{"bm25_k1": -1, "bm25_b": 1}' > $SCR/p2.json
run "B08 --params bm25_k1=-1" $T --profile $P --key $K --params $SCR/p2.json
echo '{"ngram_sizes": [0]}' > $SCR/p3.json
run "B09 --params ngram_sizes=[0]" $T --profile $P --key $K --params $SCR/p3.json
echo '{"agg_mix": 5, "weights": {"bogus": 3}}' > $SCR/p4.json
run "B10 --params agg_mix=5 + unknown weight key" $T --profile $P --key $K --params $SCR/p4.json
: > $SCR/empty.txt
run "B11 --text empty file" $T --profile $P --text $SCR/empty.txt
head -c 3000 /dev/urandom > $SCR/bin.md
run "B12 --md binary garbage" $T --profile $P --md $SCR/bin.md
run "B13 wrong profile (philosophy draft) on bixiu3 book" $T --profile $C/profiles_cloud/philosophy.draft.json --key BJ-2024-DC-ERMO-Q21
run "B14 --key lowercase" $T --profile $P --key bj-2020-bj-gaokao-q1
run "B15 --key with subq #abc" $T --profile $P --key "$K#abc"
printf 'BJ-2020-BJ-GAOKAO-Q1\nnot a key\n' > $SCR/keys_bad.txt
run "B16 --keys-file with a bad line" $T --profile $P --keys-file $SCR/keys_bad.txt
run "B17 --expect-sha correct" $T --profile $P --key $K --expect-sha c007d7198422050cdf47d1ec679a097d0b350f1bfb9c70d41672103780f76eb6
run "B18 --docx is a directory" $T --profile $P --key $K --docx $SCR
run "B19 --profile nonexistent" $T --profile $SCR/nope.json --key $K
echo '{"book_id": "x"}' > $SCR/minprof.json
run "B20 --profile missing most fields" $T --profile $SCR/minprof.json --key $K
out=$(python3 $C/placement_suggest.py --docx $BOOK --profile $P --key $K --format md --report $B/r3adv_pipe.json 2>$SCR/pipe_err.txt | head -c 10; echo; echo "pipestatus=${PIPESTATUS[0]}")
echo "== B21 stdout closed early (| head -c 10) + --report: $out"; head -c 300 $SCR/pipe_err.txt | tr '\n' ' '; echo; ls $B/r3adv_pipe.json 2>/dev/null || echo "   report NOT written"
rm -f $B/r3adv_*
echo "== leftover tmp in 构建/: $(ls -a $B | grep '^\.' | grep -v '^\.\.\?$' | tr '\n' ' ')"
echo "== SK __pycache__: $(find $R/.claude -name __pycache__ | wc -l)"
