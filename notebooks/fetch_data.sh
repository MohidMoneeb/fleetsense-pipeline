#!/usr/bin/env bash
# Fetch NASA C-MAPSS FD001 files into ./data/ (run from the notebooks/ folder).
set -euo pipefail
mkdir -p data
BASE="https://raw.githubusercontent.com/edwardzjl/CMAPSSData/master"
for f in train_FD001.txt test_FD001.txt RUL_FD001.txt; do
  echo "Downloading $f ..."
  curl -sSL -o "data/$f" "$BASE/$f"
done
echo "Done. Files in ./data/:"
ls -la data/
