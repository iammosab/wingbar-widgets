# How a widget in this collection is built

Each widget lives in `widgets/<name>/` and is installed to
`~/.config/wingbar/widgets/<name>/` (the folder is copied as is).

## Files
- `<name>.sh` — the entry point wingbar runs (bash). Helpers (`*.py`, more `.sh`) sit next to it
  and are found relative to the script (`DIR=$(cd "$(dirname "$0")" && pwd)`), never by absolute path.
- `widget.json` — the entry to paste under `"widgets"` in wingbar's `config.json`:
  `{ "<name>": { "type": "script", "command": "bash ~/.config/wingbar/widgets/<name>/<name>.sh", "every": "…",
  "icon": "…", "levels": {…}, "menuOn": "hover" } }`. Settings go as environment variables at the
  start of `command` (`"command": "WINGBAR_CI_REPO=owner/repo bash ~/.config/…"`), with placeholder values.
- `README.md` — what it shows, what its menu has, what it needs (tools), every setting with its
  default, and a **Privacy** section: what it reads, what it sends where, what it stores.

## Output (wingbar's script protocol)
- Line 1: `level|label` (levels `ok`, `warn`, `alert`, `dim`, or your own named in `levels`).
  Empty line 1 hides the widget.
- Optional `icon: <SF Symbol or bundled icon name>`.
- Menu lines: `menu: Title | command` (an action), `menu: Title` (a reading, shown dimmed),
  `menu: ---` (separator). The first `|` ends the title: strip `|` and control characters from any
  text the script doesn't control (`tr -d '|[:cntrl:]'`). At most 64 lines / 16 KB are read.
  No submenus: flatten. Keep menus short and useful (≈ 5–15 lines).
- A menu command runs detached through bash; quote paths and URLs.

## Rules
- **Nothing personal in any file**: no names, emails, usernames, home paths (`/Users/...`; use `$HOME`
  or `~`), hostnames, IPs, repo names, team/workspace/list IDs, cities, tokens. Anything a user must
  provide is a setting with a placeholder (`owner/repo`, `123456`), or read from
  `~/.config/wingbar/secrets.env` (the user creates it; never in the repo) for secrets.
- Missing setting / tool / secret: print one helpful line (`dim|ClickUp: set CLICKUP_TOKEN`) and a
  menu reading saying how to fix it. Never fail noisily.
- Fast (< 2 s typical; cache slow network results in `${TMPDIR:-/tmp}/wingbar-<name>/`), no
  background daemons, no writes outside that cache.
- Tools available on a stock Mac first; `python3` (Xcode Command Line Tools), `gh`, `jq` allowed when
  said in the README's Needs.
- Every tool path overridable for testing: `GH=${WINGBAR_GH:-gh}` style.
