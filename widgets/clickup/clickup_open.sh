#!/bin/bash
# Open the running timer's task in ClickUp, or ClickUp itself (handy as rightClick).
DIR=$(cd "$(dirname "$0")" && pwd)
PY=${WINGBAR_PYTHON3:-python3}

# /usr/bin/python3 is only a stub until the Command Line Tools are installed, and
# running it would pop up an installer on every run.
if [ "$(command -v "$PY")" = /usr/bin/python3 ] && ! xcode-select -p >/dev/null 2>&1; then
  echo "dim|ClickUp: needs python3"
  echo "menu: Needs python3: run  xcode-select --install  in a terminal"
  exit 0
fi
exec "$PY" "$DIR/clickup.py" open "$@"
