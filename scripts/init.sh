#!/usr/bin/env bash 
set -x
dir_name=$(cd $(dirname $0) && pwd)

cd $dir_name

mkdir -p ../data/
./get_data.sh
if command -v uv >/dev/null 2>&1; then
  uv run python ./save_to_sqlite.py
else
  python3 ./save_to_sqlite.py
fi

set +x
