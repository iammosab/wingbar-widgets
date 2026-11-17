# repos

Stats of a few of your GitHub repositories: release downloads, traffic (views, clones,
where visitors come from) and stars, the numbers GitHub's *Insights → Traffic* page shows.

- **Bar:** total release downloads and the views of the last 14 days, e.g. `↓55 · 209 views`.
  New downloads since yesterday show as `↓55 +3` and turn the widget `up` (green).
- **Menu (hover):** a section per repository (busiest first) with its stars and forks; under it
  **Downloads** (all releases, with today's new ones) and the latest release's count, **Views**
  and **Clones** of the last 14 days with unique visitors, a meter comparing the repos' views,
  and a caption with the top referrers and, once the widget has run for more than 14 days,
  the views counted since it started. Click a section to open the repository, *Downloads* to
  open its releases, *Views* its traffic page. Buttons: *Refresh* and *GitHub*.

```text
GitHub                     3 repos · traffic of 14 days
adbrent                           ★ 0 · forks 0
Downloads                           39 · +3 today ›
latest v0.4.5: 5 · 13 releases
Views                              83 · 14 unique ›
━━━━━━━━━━━━━━━━━━━━━━━━━──────────────
Clones                            387 · 149 unique
from github.com 11, linkedin.com 3, Google 2
…
updated 3m ago
          Refresh       │       GitHub
```

## Needs

- wingbar 0.4 or later (for the menu's columns and meters).
- [`gh`](https://cli.github.com), logged in: `brew install gh`, then `gh auth login`.
- Traffic is only shown to people who can push to a repository (GitHub's rule); for other
  repositories the menu says *needs push access* and shows downloads and stars only.
- `python3`: comes with the Xcode Command Line Tools (`xcode-select --install`).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/iammosab/wingbar-widgets/main/install.sh | bash -s -- repos
```

then put your repositories in its `command` in `~/.config/wingbar/config.json`:
`WINGBAR_REPOS="you/app you/tool"`.

## Settings

| Variable | Default | What it does |
|---|---|---|
| `WINGBAR_REPOS` | (required) | Repositories, space or comma separated: `owner/a owner/b` (up to 8). |
| `WINGBAR_REPOS_LABEL` | `both` | What the bar shows: `both`, `downloads` or `views`. |
| `WINGBAR_REPOS_TTL` | `900` | Seconds GitHub's answers are reused (traffic updates about hourly). |
| `WINGBAR_GH` / `WINGBAR_PYTHON` | `gh` / `python3` | Tool paths, for tests. |
| `GH_HOST` | `github.com` | `gh`'s own setting, for GitHub Enterprise; also used for the links. |

## Privacy

- **Reads:** nothing on your Mac but its own cache and history. `gh` does the authentication;
  the widget never reads or prints a token.
- **Sends:** through `gh`, to GitHub's API only, per repository every `WINGBAR_REPOS_TTL`
  seconds: the repository, its releases, `traffic/views`, `traffic/clones` and
  `traffic/popular/referrers` (5 requests).
- **Stores:**
  - `${TMPDIR:-/tmp}/wingbar-repos/` (`0700`/`0600`): the last answer per repository
    (counts, latest release tag, top referrer names).
  - `${XDG_STATE_HOME:-~/.local/state}/wingbar-repos/history.json` (`0600`): views and clones per
    day (up to 400 days) and the download total per day (60 days), so the widget can count past
    GitHub's 14-day window and show today's new downloads. Delete it to start over.
