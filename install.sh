#!/bin/bash
# Install widgets from this collection into wingbar.
#
#   ./install.sh ci salat            in a clone
#   curl -fsSL https://raw.githubusercontent.com/iammosab/wingbar-widgets/main/install.sh | bash -s -- ci salat
#   ./install.sh --list              the widgets there are
#
# For each widget: its folder is copied to ~/.config/wingbar/widgets/<name>/
# (run again to update the scripts), and, unless a widget of that name is
# already on your bar, it is added with `wingbar widget add` and the options
# of its widget.json. Edit its settings afterwards in wingbar's config.json
# (they're the variables at the start of its "command").
set -euo pipefail

REPO="iammosab/wingbar-widgets"

main() {
  local src="" here stage=""
  if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
    here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
    [ -d "$here/widgets" ] && src=$here
  fi
  if [ -z "$src" ]; then
    stage=$(mktemp -d)
    # shellcheck disable=SC2064
    trap "rm -rf '$stage'" EXIT
    curl -fsSL "https://codeload.github.com/$REPO/tar.gz/refs/heads/main" | tar -xz -C "$stage"
    src=$(find "$stage" -mindepth 1 -maxdepth 1 -type d | head -1)
  fi

  if [ $# -eq 0 ] || [ "$1" = "--list" ] || [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    echo "usage: install.sh WIDGET...   (widgets: $(cd "$src/widgets" && ls | tr '\n' ' '))"
    [ $# -eq 0 ] && exit 2 || exit 0
  fi

  local wb
  wb=$(command -v wingbar || true)
  [ -z "$wb" ] && [ -x "$HOME/.local/bin/wingbar" ] && wb="$HOME/.local/bin/wingbar"
  [ -z "$wb" ] && { echo "wingbar isn't installed: https://github.com/iammosab/wingbar" >&2; exit 1; }

  local dest="$HOME/.config/wingbar/widgets" name
  [ -n "${WINGBAR_CONFIG:-}" ] && dest="$(dirname "$WINGBAR_CONFIG")/widgets"
  for name in "$@"; do
    if [ ! -f "$src/widgets/$name/widget.json" ]; then
      echo "no widget \"$name\" (there are: $(cd "$src/widgets" && ls | tr '\n' ' '))" >&2
      continue
    fi
    mkdir -p "$dest/$name"
    cp -R "$src/widgets/$name/." "$dest/$name/"
    chmod +x "$dest/$name"/*.sh
    echo "→ $name: scripts in $dest/$name"
    add "$wb" "$name" "$src/widgets/$name/widget.json"
  done
}

# Add a widget to the bar from its widget.json, unless one of that name exists.
add() {
  local wb=$1 name=$2 json=$3 cmd opt val
  if "$wb" widget list --json 2>/dev/null | grep -q "\"key\": *\"$name\""; then
    echo "  a widget named \"$name\" is already in your settings: only its scripts were updated"
    echo "  (to start from this one's settings: wingbar widget remove $name, then install it again)"
    return
  fi
  cmd=$(plutil -extract "$name.command" raw -o - "$json")
  "$wb" widget add script --as "$name" --right --command "$cmd" | grep -v '^note:' || true
  for opt in every timeout icon levels click rightClick middleClick menuOn hideWhenEmpty iconOnly greyWhenOk iconFromLabel; do
    case $(plutil -type "$name.$opt" "$json" 2>/dev/null) in
      dictionary | array) val=$(plutil -extract "$name.$opt" json -o - "$json") ;;
      "") continue ;;
      *) val=$(plutil -extract "$name.$opt" raw -o - "$json") ;;
    esac
    "$wb" widget set "$name" "$opt" "$val" >/dev/null 2>&1 || echo "  couldn't set $opt" >&2
  done
  echo "  added to the right wing; its settings are at the start of its \"command\" in config.json"
}

main "$@"
