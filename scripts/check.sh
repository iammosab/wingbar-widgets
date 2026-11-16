#!/bin/bash
# Before sharing: syntax, widget.json, and nothing personal or secret in the files.
# Generic patterns only; put your own words to keep out (name, repos, IDs) one per
# line in .leakwords (git-ignored) and they're checked too.
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
files=$(git ls-files 2>/dev/null || find . -type f -not -path './.git/*')
files=$(printf '%s\n' "$files" | grep -v -E '^(\./)?(scripts/check\.sh|CONVENTIONS\.md|\.leakwords)$')

for f in widgets/*/*.sh install.sh; do bash -n "$f" || { echo "syntax: $f"; fail=1; }; done
for f in widgets/*/*.py; do
  python3 -c 'import ast,sys; ast.parse(open(sys.argv[1]).read())' "$f" || { echo "syntax: $f"; fail=1; }
done
for d in widgets/*/; do
  n=$(basename "$d")
  for need in "$n.sh" widget.json README.md; do [ -f "$d$need" ] || { echo "missing: $d$need"; fail=1; }; done
  python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert list(d)==[sys.argv[2]], "key"' "$d/widget.json" "$n" \
    || { echo "widget.json: $d (one key, named $n)"; fail=1; }
  grep -q '^## Privacy' "$d/README.md" || { echo "no Privacy section: $d/README.md"; fail=1; }
done

leak() { # label, extended regex[, path to skip]
  local hits
  hits=$(printf '%s\n' "$files" | grep -v -E "${3:-^$}" | xargs grep -n -I -i -E "$2" 2>/dev/null)
  [ -n "$hits" ] && { echo "possible $1:"; printf '%s\n' "$hits" | head -5; fail=1; }
}
leak "home path" '/Users/[A-Za-z]|/home/[a-z]'
leak "email" '[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+\.[A-Za-z]{2,}'
leak "private IP" '\b(10\.[0-9]+\.[0-9]+\.[0-9]+|192\.168\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)\b' '^(\./)?scripts/demo/' # demo addresses are made up
leak "MAC address" '\b([0-9a-f]{2}:){5}[0-9a-f]{2}\b'
leak "token" '(ghp_|gho_|ghs_|github_pat_|sk-ant-|xox[abp]-|pk_[0-9]{4,}_|AKIA[0-9A-Z]{12})'
if [ -s .leakwords ]; then
  while IFS= read -r w; do [ -n "$w" ] && leak "personal word" "$w"; done < .leakwords
fi
[ $fail -eq 0 ] && echo "check: ok ($(ls -d widgets/*/ | wc -l | tr -d ' ') widgets)"
exit $fail
