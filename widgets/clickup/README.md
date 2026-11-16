# clickup

Your ClickUp time tracking: the running timer and how much you've tracked today.

- **Bar:** with a timer running, its elapsed time and today's total (`0:42 · 3.4h`, or with the
  task name in front when `WINGBAR_CLICKUP_SHOW_TASK=1`); with none, today's total, dimmed
  (`3.4h`). With a daily target set it shows `3.4/7h` and turns `done` (green) once you reach it.
- **Menu (hover):** the running task and since when, today's total, today's time per task (the top
  five), then *Stop timer* / *Start timer*, *Open task* (while a timer runs) and *Open ClickUp*.
- **Right-click:** opens the running timer's task (or ClickUp). ⌥-right-click still opens
  wingbar's own menu. Remove `rightClick` from the entry if you'd rather have wingbar's menu there.

Today's total counts your finished time entries since midnight in every workspace, plus the
running timer live.

Without a token the bar shows a dimmed `ClickUp` and the menu says how to add one.

## Needs

- A ClickUp personal API token: ClickUp > Settings > Apps > API Token (it starts with `pk_`).
  Put it in `~/.config/wingbar/secrets.env` (create the file, `chmod 600` it, keep it out of any
  repository):

  ```sh
  CLICKUP_TOKEN=pk_your_token_here
  ```

  A `CLICKUP_TOKEN` in the environment wins over the file.
- `python3` (Xcode Command Line Tools: `xcode-select --install`), plus `curl`, `open` and
  `osascript`, which come with macOS.

## Install

Copy this folder to `~/.config/wingbar/widgets/clickup/`, paste the entry from `widget.json` under
`"widgets"` in `~/.config/wingbar/config.json`, and add `"clickup"` to `left` or `right`.

## Settings

Set as environment variables at the start of `command` in `widget.json` (the menu's Start/Stop
passes the ones it needs on to `clickup_toggle.sh`).

| Setting | Default | What it does |
| --- | --- | --- |
| `WINGBAR_CLICKUP_TEAMS` | empty: every workspace the token can see | Workspace (team) IDs to read, comma separated, e.g. `123456,789012`. The ID is the first number in a ClickUp URL (`app.clickup.com/123456/…`). When empty they are found with one request a day. |
| `WINGBAR_CLICKUP_START_TEAM` | the first workspace | Workspace in which *Start timer* starts a timer, e.g. `123456`. |
| `WINGBAR_CLICKUP_START_TASK` | empty: a timer without a task | Task ID *Start timer* tracks against, e.g. `86abc123x` (from `app.clickup.com/t/<id>`). A timer without a task is described as "Started from wingbar"; some ClickUp plans only allow timers on tasks. |
| `WINGBAR_CLICKUP_TARGET_HOURS` | `0` (none) | Daily target in hours, e.g. `7`: shown as `3.4/7h`, level `done` once reached. |
| `WINGBAR_CLICKUP_SHOW_TASK` | `0` | `1` puts the running task's name (shortened) in the bar. |
| `WINGBAR_SECRETS` | `~/.config/wingbar/secrets.env` | Where the token is read from. |
| `WINGBAR_PYTHON3`, `WINGBAR_CURL`, `WINGBAR_OPEN`, `WINGBAR_OSASCRIPT` | `python3`, `curl`, `open`, `osascript` | Tool paths (for testing). |

Each run asks ClickUp for the running timer (one request per workspace); today's entries are
fetched again every 2 minutes, or as soon as the running timer changes. A failed start or stop
shows a macOS notification with ClickUp's reason.

Files: `clickup.sh` (the widget), `clickup_toggle.sh` (stop the running timer, or start one),
`clickup_open.sh` (open the running task), `clickup.py` (all three, `python3` only).

## Privacy

- **Reads:** `CLICKUP_TOKEN` from the environment or the `CLICKUP_TOKEN=` line of
  `~/.config/wingbar/secrets.env` (only that line is used; the file is not
  run as a script).
- **Sends:** the token, to ClickUp only, over HTTPS (`api.clickup.com/api/v2`), as the
  `Authorization` header: `GET /team` (finding your workspaces, when `WINGBAR_CLICKUP_TEAMS` is
  empty), `GET /team/<id>/time_entries/current` (the running timer),
  `GET /team/<id>/time_entries?start_date=…&end_date=…` (today's entries), and, only when you choose
  *Start timer* / *Stop timer*, `POST /team/<id>/time_entries/start` or `…/stop`. The token goes to
  `curl` on its standard input, so it never appears in a process list. Task links are opened in
  your browser.
- **Stores:** only in `${TMPDIR:-/tmp}/wingbar-clickup/` (folder `0700`, files `0600`):
  `teams.json` (your workspace IDs, refreshed daily) and `entries.json` (today's finished entries:
  start, duration and task name or description). The token is never written anywhere. Delete the
  folder at any time.
