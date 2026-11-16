#!/bin/bash
# GitHub Actions widget for wingbar: latest runs, today's pass rate and open PRs of one repo.
# Settings (environment variables, see README.md):
#   WINGBAR_CI_REPO     owner/repo (required)
#   WINGBAR_CI_BRANCH   only runs on this branch (default: all branches)
#   WINGBAR_CI_LIMIT    recent runs in the menu (default 6, 1-15)
#   WINGBAR_CI_PRS      open PRs in the menu (default 5, 0 hides them)
#   WINGBAR_CI_RUNNERS  1 = add a self-hosted runner reading (needs admin access to the repo)
#   WINGBAR_CI_TTL      seconds GitHub answers are cached (default 20)
#   WINGBAR_GH / WINGBAR_PYTHON   tool paths (default: gh / python3 from PATH)
# gh does its own authentication; this widget never reads or prints a token.

DIR=$(cd "$(dirname "$0")" && pwd)
GH=${WINGBAR_GH:-gh}
PYTHON=${WINGBAR_PYTHON:-python3}

REPO=${WINGBAR_CI_REPO:-}
if [ -z "$REPO" ] || [ "$REPO" = "owner/repo" ]; then
  echo "dim|CI: set repo"
  echo "menu: Set WINGBAR_CI_REPO=owner/repo in this widget's command"
  exit 0
fi
if ! printf '%s' "$REPO" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'; then
  echo "dim|CI: bad repo"
  echo "menu: WINGBAR_CI_REPO must look like owner/repo"
  exit 0
fi
if ! command -v "$GH" >/dev/null 2>&1; then
  echo "dim|CI: install gh"
  echo "menu: Needs the GitHub CLI: brew install gh, then gh auth login"
  echo "menu: Open cli.github.com | open 'https://cli.github.com'"
  exit 0
fi
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "dim|CI: needs python3"
  echo "menu: Needs python3: run xcode-select --install"
  exit 0
fi

GH=$(command -v "$GH") exec "$PYTHON" -I "$DIR/ci.py"
