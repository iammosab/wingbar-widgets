# claude

Your Claude plan usage, the same numbers Claude Code's `/usage` shows.

- **Bar:** the tightest limit you have right now, e.g. `25%` (optionally with the plan: `Max · 25%`).
  It turns `warn` at 75 % and `alert` at 90 %, or earlier when Anthropic marks a limit as
  warning / critical.
- **Menu (hover):** a panel headed *Claude* with your plan (`Max plan`). Under it every limit
  (session (5h), week for all models, per-model weekly limits) as a row with its percentage on the
  right, a meter coloured by level (green, `warn` from 75 %, `alert` from 90 %, or earlier when
  Anthropic marks the limit warning / critical) and a caption with when it resets
  (`resets in 2h 06m`, `resets Fri 10:21`). Then usage credits (spent of the cap, with a meter when
  there is a cap); with `WINGBAR_CLAUDE_OFFERS=1` your *Limit resets* (how many can be used, each
  with its use-by date) and any bonus offer; a note when a limit is reached, when the numbers were fetched
  (`updated 1m ago`, or that the last reply is shown because Anthropic couldn't be reached), and
  two buttons: *Usage page* and *Refresh*. When signed out or offline the panel says why and how to
  fix it, with the same buttons.

  ```text
  Claude                      Max plan
  Session (5h)                     38%
  ▬▬▬▬▬▬▬▬───────────────────────────
  resets in 2h 06m
  Week · all models                21%
  ▬▬▬▬▬──────────────────────────────
  resets Fri 10:21
  Usage credits                    off
  updated just now
  ───────────────────────────────────
     Usage page     │     Refresh
  ```
- **Click:** opens claude.ai's usage page.

When Claude Code isn't signed in the bar shows `Claude: sign in`; when its login has expired,
`Claude: login expired` (using Claude Code once renews it; this widget never renews or changes
your login).

## Needs

- wingbar 0.4 or later (for the menu's columns and meters).
- [Claude Code](https://claude.com/claude-code), signed in with a Claude subscription (Pro, Max, …)
  on this Mac.
- `python3` (Xcode Command Line Tools: `xcode-select --install`), plus `security` and `curl`,
  which come with macOS.

## Install

Copy this folder to `~/.config/wingbar/widgets/claude/`, paste the entry from `widget.json` under
`"widgets"` in `~/.config/wingbar/config.json`, and add `"claude"` to `left` or `right`.

## Settings

Set as environment variables at the start of `command` in `widget.json`.

| Setting | Default | What it does |
| --- | --- | --- |
| `WINGBAR_CLAUDE_WARN` | `75` | Percentage at which the widget turns `warn`. |
| `WINGBAR_CLAUDE_ALERT` | `90` | Percentage at which the widget turns `alert`. |
| `WINGBAR_CLAUDE_PLAN` | `0` | `1` puts the plan name before the percentage (`Max · 25%`). |
| `WINGBAR_CLAUDE_OFFERS` | `0` | `1` also checks for free limit resets and bonus offers (what Claude Code's `/limit-reset` shows): the bar gets a `↺` while a reset can be used, and the menu a *Limit resets* section with each one and its use-by date. See Privacy: these requests say they are Claude Code. |
| `CLAUDE_CONFIG_DIR` | `~/.claude` | Where Claude Code keeps its credentials file, if it uses one instead of the Keychain. |
| `WINGBAR_PYTHON3`, `WINGBAR_SECURITY`, `WINGBAR_CURL` | `python3`, `security`, `curl` | Tool paths (for testing). |

The usage reply is cached for 60 s, so `every` below that (or *Refresh* clicked often) doesn't
call the API more often. When the API can't be reached the last reply (up to an hour old) is shown
with a note.

## Privacy

- **Reads:** Claude Code's own OAuth credentials, at run time, from your login Keychain: the
  generic password items whose service is `Claude Code-credentials` or
  `Claude Code-credentials-<hash>` (one per Claude Code config folder; when there are several, the
  one that expires last wins). If there is none, it reads `~/.claude/.credentials.json` (or
  `$CLAUDE_CONFIG_DIR/.credentials.json`). To find the items it lists the login keychain's item
  names with `security dump-keychain` (names only, no passwords). macOS may ask you once to let
  `security` read the item. Only the access token is used: the refresh token stored with it is
  ignored (never sent, stored or used), and the item is never changed.
- **Sends:** the access token, to Anthropic only, over HTTPS:
  `GET https://api.anthropic.com/api/oauth/usage` (at most once a minute) and
  `GET https://api.anthropic.com/api/oauth/profile` (once a day, for the plan name). The token goes
  to `curl` on its standard input, so it never appears in a process list. These are the
  **undocumented** endpoints Claude Code itself uses for `/usage`; Anthropic may change or remove
  them at any time, and the widget will then show `Claude: offline` or no data until it is updated.
  With `WINGBAR_CLAUDE_OFFERS=1`, also `GET …/oauth/usage?cedar_ember=1&skip_spend=1` and
  `…?starry_waterfall=cli_menu&skip_spend=1` every 10 minutes. Anthropic answers these only to Claude
  Code, so these two requests send Claude Code's User-Agent (`claude-cli/<the version installed here>`):
  they identify as Claude Code. That's why it's off unless you turn it on.
- **Stores:** only in `${TMPDIR:-/tmp}/wingbar-claude/` (folder `0700`, files `0600`):
  `usage.json` (the usage reply: percentages and reset times), `offers.json` (with offers on: your
  limit resets and bonus offers, their labels and dates), `profile.json` (just the plan name;
  the rest of the profile, such as your email, is discarded) and `keychain_item` (the service and
  account *names* of the Keychain item that worked, so the next run reads only that one). The token
  itself is never written anywhere. Nothing else is written; delete the folder at any time.
