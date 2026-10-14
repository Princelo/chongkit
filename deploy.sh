#!/bin/sh

set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$script_dir"

python3 deploy.py

squirrel="/Library/Input Methods/Squirrel.app/Contents/MacOS/Squirrel"
if [ ! -x "$squirrel" ]; then
  echo "Squirrel executable not found: $squirrel" >&2
  exit 1
fi

"$squirrel" --reload
