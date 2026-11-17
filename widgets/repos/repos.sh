#!/bin/bash
# GitHub repo stats for wingbar: release downloads, traffic (views, clones, referrers)
# and stars of a few repositories you can push to.
# Settings (environment variables, see README.md):
#   WINGBAR_REPOS        repositories, space or comma separated: owner/a owner/b (required)
#   WINGBAR_REPOS_TTL    seconds GitHub answers are cached (default 900)
#   WINGBAR_GH / WINGBAR_PYTHON   tool paths (default: gh / python3 from PATH)
# gh does its own authentication; this widget never reads or prints a token.

DIR=$(cd "$(dirname "$0")" && pwd)
GH=${WINGBAR_GH:-gh}
PYTHON=${WINGBAR_PYTHON:-python3}

REPOS=$(printf '%s' "${WINGBAR_REPOS:-}" | tr ',' ' ')
if [ -z "${REPOS// /}" ] || [ "$REPOS" = "owner/repo" ]; then
  echo "dim|Repos: set repos"
  echo "menu: Set WINGBAR_REPOS=\"owner/a owner/b\" in this widget's command"
  exit 0
fi
for r in $REPOS; do
  if ! printf '%s' "$r" | grep -Eq '^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'; then
    echo "dim|Repos: bad repo"
    echo "menu: Each entry of WINGBAR_REPOS must look like owner/repo"
    exit 0
  fi
done
if ! command -v "$GH" >/dev/null 2>&1; then
  echo "dim|Repos: install gh"
  echo "menu: Needs the GitHub CLI: brew install gh, then gh auth login"
  echo "menu: Open cli.github.com | open 'https://cli.github.com'"
  exit 0
fi
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "dim|Repos: needs python3"
  echo "menu: Needs python3: run xcode-select --install"
  exit 0
fi

WINGBAR_REPOS="$REPOS" GH=$(command -v "$GH") exec "$PYTHON" -I "$DIR/repos.py"
