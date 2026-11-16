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

- The repo (and branch), today's runs and pass rate, running/queued counts.
- The most recent runs: `✓`/`✗`/`▶`/`◌`/`–`, workflow, branch (or PR title), duration. Click to
  open the run.
- Open pull requests with their check state (passing, failing, pending). Click to open the PR.
- Open Actions, Open Pull Requests.
- Optional: a self-hosted runner reading (online / busy / offline), see `WINGBAR_CI_RUNNERS`.

## Needs

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
