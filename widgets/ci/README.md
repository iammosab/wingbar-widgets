# ci: GitHub Actions

Shows the state of one GitHub repository's Actions runs in the bar, with a hover menu of
today's numbers, recent runs and open pull requests.

| Bar | Level | When |
|---|---|---|
| `CI ✓ 7/8` | `ok` | the newest finished run passed (7 of today's 8 finished runs passed) |
| `CI ▶ Tests +1` | `warn` | a run is in progress (`+1`: one more running or queued) |
| `CI ◌ 2 queued` | `warn` | runs are queued, none running yet |
| `CI ✗ Tests` | `alert` | the newest finished run failed (cancelled and skipped runs don't count) |
| `CI ?`, `CI: set repo`, … | `dim` | no data, or something to fix (the menu says what) |

A `?` after the label means GitHub couldn't be reached and the last answer (at most 10 minutes
old) is shown.

## Menu

A panel in columns, labels on the left and values on the right:

- **CI · owner/repo**, with the branch and the state on the right (passing, failing, running,
  queued). If GitHub can't be reached, a line under it says why and how old the data is.
- Optional: **Runner(s)**, online / busy / idle / offline, and the offline ones by name (see
  `WINGBAR_CI_RUNNERS`). Click to open the repo's runner settings.
- **In progress**: how many runs are running and queued (only while there are some).
- **Today**: the number of runs, **Passed** `7/8 · 88%` with a meter (green when all passed,
  your theme's `warn` colour from 80%, `alert` below), and the median time of the two busiest
  workflows.
- **Recent**: the latest runs, `✓`/`✗`/`▶`/`◌`/`–` with workflow and branch (or PR/commit title) on
  the left, the duration on the right. Click a run to open it, or the section to open Actions.
- **Open PRs**: each with its check state on the right (passing, failing, pending, draft). Click
  to open the PR, or the section to open the pull request list.
- When it was updated, then buttons: **Actions**, **Pull requests**, **Runners** (with
  `WINGBAR_CI_RUNNERS`) and **Refresh** (forgets the cached answers so GitHub is asked again now).

With `theme.menus: "native"` the same lines show as a plain macOS menu, without the meter.

## Needs

- wingbar 0.4 or later (for the menu's columns and meters).

- [`gh`](https://cli.github.com) (the GitHub CLI), logged in: `brew install gh`, then
  `gh auth login`. Private repositories work when your `gh` account can read them.
- `python3` (Xcode Command Line Tools: `xcode-select --install`).

## Install

```sh
cp -R widgets/ci ~/.config/wingbar/widgets/
```

Paste the entry from `widget.json` under `"widgets"` in `~/.config/wingbar/config.json`, replace
`owner/repo`, and add `"ci"` to `left` or `right`.

## Settings

Set them as environment variables at the start of `command` in `widget.json`.

| Variable | Default | Meaning |
|---|---|---|
| `WINGBAR_CI_REPO` | (required) | The repository, `owner/repo`. |
| `WINGBAR_CI_BRANCH` | empty: all branches | Only runs on this branch, and only PRs into it. Recommended for busy repos (e.g. `main`), so a failing PR run doesn't turn the bar red. |
| `WINGBAR_CI_LIMIT` | `6` | Recent runs in the menu (1–15). |
| `WINGBAR_CI_PRS` | `5` | Open pull requests in the menu (0–15; `0` hides them and skips that call). |
| `WINGBAR_CI_RUNNERS` | off | `1` adds a self-hosted runner reading. GitHub only answers this for repo admins; otherwise the menu says "needs admin access" and the call is retried every 10 minutes. |
| `WINGBAR_CI_TTL` | `20` | Seconds GitHub's answers are cached. |
| `WINGBAR_GH` | `gh` | Path to `gh`. |
| `WINGBAR_PYTHON` | `python3` | Path to `python3`. |
| `GH_HOST` | `github.com` | `gh`'s own setting, for GitHub Enterprise Server; also used for the menu's links. |

The entry polls every 30 s. Each fetch is 2 `gh` calls (3 with runners), made in parallel: about
1–2 s without the cache, under 0.1 s with it. That is about 240 GitHub API requests an hour, well
inside the 5,000 an hour a logged-in user gets. A failed call is retried after 30 s at the earliest.

## Privacy

- **Reads:** your repository's workflow runs, open pull requests and (only with
  `WINGBAR_CI_RUNNERS=1`) its self-hosted runners, through `gh`. `gh` uses its own stored login;
  this widget never reads, prints or stores a token.
- **Sends:** only `gh`'s requests to GitHub's API (`api.github.com`, or your `GH_HOST`). Nothing
  else leaves the machine.
- **Stores:** `gh`'s JSON answers (run titles, branches, PR titles, links) and the last error
  message in `${TMPDIR:-/tmp}/wingbar-ci/` (folder readable only by you). Delete the folder at any
  time; it is rebuilt on the next poll.
