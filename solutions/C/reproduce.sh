#!/usr/bin/env bash
# 一键复现（须在 solutions/C 下运行）。约 15-25 分钟；分片并行以节省时间。
set -e
cd "$(dirname "$0")"
for s in 1 2 3 4 5; do python run_all.py $s & done; wait
for i in 0 1 2 3; do python cv_q3.py $i & done; wait
python cv_grid.py
python analysis_final.py
python make_results.py
python check_results.py
python write_paper.py
