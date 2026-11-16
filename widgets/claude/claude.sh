#!/bin/bash
# Claude plan usage for wingbar: the tightest limit in the bar, every limit in the menu.
# The work is in claude.py next to this file (see README.md).
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${WINGBAR_PYTHON3:-python3}

# /usr/bin/python3 is only a stub until the Command Line Tools are installed, and
# running it would pop up an installer every minute.
if [ "$(command -v "$PY")" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then
  echo "dim|Claude: needs python3"
  echo "menu: Needs python3: run  xcode-select --install  in a terminal"
  exit 0
fi
exec "$PY" "$DIR/claude.py" "$@"
