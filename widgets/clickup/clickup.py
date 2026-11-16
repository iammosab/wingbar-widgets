"""ClickUp time tracking for wingbar.

  clickup.py         the widget: running timer + today's tracked total, with a menu
  clickup.py toggle  stop the running timer, or start one
  clickup.py open    open the running timer's task (or ClickUp)

The token is CLICKUP_TOKEN, from the environment or ~/.config/wingbar/secrets.env.
It goes to curl on stdin (never on a command line) and is never written anywhere.
Caches live in ${TMPDIR:-/tmp}/wingbar-clickup/.
"""
import json
import os
import re
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

CURL = os.environ.get("WINGBAR_CURL") or "curl"
OPEN = os.environ.get("WINGBAR_OPEN") or "open"
OSASCRIPT = os.environ.get("WINGBAR_OSASCRIPT") or "osascript"
API = "https://api.clickup.com/api/v2"
APP = "https://app.clickup.com/"
SECRETS = os.path.expanduser(os.environ.get("WINGBAR_SECRETS") or "~/.config/wingbar/secrets.env")
CACHE = os.path.join(os.environ.get("TMPDIR") or "/tmp", "wingbar-clickup")
TEAMS_FILE = os.path.join(CACHE, "teams.json")
ENTRIES_FILE = os.path.join(CACHE, "entries.json")
TEAMS_TTL = 86400
ENTRIES_TTL = 120
DIR = os.path.dirname(os.path.abspath(__file__))
# What the toggle needs from the widget's settings (menu commands don't inherit `command`'s).
TOGGLE_SETTINGS = ("WINGBAR_CLICKUP_TEAMS", "WINGBAR_CLICKUP_START_TEAM", "WINGBAR_CLICKUP_START_TASK",
                   "WINGBAR_SECRETS", "WINGBAR_PYTHON3", "WINGBAR_CURL", "WINGBAR_OSASCRIPT")


def ids(text):
    """Comma/space separated IDs; anything that isn't a plain ID is dropped."""
    return [x for x in re.split(r"[,\s]+", text or "") if re.fullmatch(r"[A-Za-z0-9_-]+", x)]


TEAMS = ids(os.environ.get("WINGBAR_CLICKUP_TEAMS"))
START_TEAM = (ids(os.environ.get("WINGBAR_CLICKUP_START_TEAM")) or [""])[0]
START_TASK = (ids(os.environ.get("WINGBAR_CLICKUP_START_TASK")) or [""])[0]
SHOW_TASK = os.environ.get("WINGBAR_CLICKUP_SHOW_TASK", "0") == "1"
try:
    TARGET = max(0.0, float(os.environ.get("WINGBAR_CLICKUP_TARGET_HOURS") or 0)) * 3600
except ValueError:
    TARGET = 0


class ApiError(Exception):
    def __init__(self, status, message=""):
        super().__init__(message or f"HTTP {status}")
        self.status = status


def clean(s, n=40):
    """Text for the bar or a menu title: no '|', no control characters, at most n characters."""
    s = re.sub(r"\s+", " ", re.sub(r"[|\x00-\x1f\x7f]", " ", str(s or ""))).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def label(s, n=40):
    """Text from ClickUp as the start of a menu line: cleaned, and without a leading
    `#`, `_`, `>`, `~` or `-` that would make it a header, caption, button, meter or separator."""
    return clean(s, n).lstrip("#_>~- ") or "No task"


def quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def done(line, menu=()):
    print(line)
    for m in menu:
        print("menu: " + m)
    sys.exit(0)


def token():
    tok = os.environ.get("CLICKUP_TOKEN", "")
    if not tok:
        try:
            for line in open(SECRETS):
                m = re.match(r"\s*(?:export\s+)?CLICKUP_TOKEN\s*=\s*(.*)$", line)
                if m:
                    v = m.group(1).strip()
                    if v[:1] in "\"'" and v[:1] and v.count(v[0]) >= 2:
                        v = v[1:v.index(v[0], 1)]
                    else:
                        v = v.split(" #", 1)[0].strip()
                    tok = v
        except OSError:
            pass
    # Only token characters: it goes into a curl config line.
    return tok if re.fullmatch(r"[A-Za-z0-9_-]+", tok) else ""


def api(tok, path, method="GET", body=None):
    """The reply's JSON; ApiError on any failure. The token reaches curl on stdin."""
    args = [CURL, "-sS", "--max-time", "6", "-K", "-", "-w", "\n%{http_code}", "-X", method]
    if body is not None:
        args += ["-H", "Content-Type: application/json", "--data-binary", json.dumps(body)]
    try:
        p = subprocess.run(args + [API + path], input=f'header = "Authorization: {tok}"\n',
                           capture_output=True, text=True, timeout=10)
        out = p.stdout
    except (OSError, subprocess.SubprocessError):
        out = ""
    text, _, status = out.rpartition("\n")
    status = int(status) if status.isdigit() else 0
    try:
        data = json.loads(text) if text.strip() else {}
    except ValueError:
        data = None
    if status != 200 or not isinstance(data, dict):
        err = data.get("err") if isinstance(data, dict) else ""
        raise ApiError(status, clean(err, 80))
    return data


def load(path, ttl):
    try:
        if time.time() - os.path.getmtime(path) < ttl:
            return json.load(open(path))
    except (OSError, ValueError):
        pass
    return None


def save(path, obj):
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def forget(*paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


def teams(tok):
    """Workspace IDs: the setting, else every workspace the token can see (cached a day)."""
    if TEAMS:
        return TEAMS
    cached = load(TEAMS_FILE, TEAMS_TTL)
    if isinstance(cached, list) and cached:
        return cached
    found = ids(" ".join(str(t.get("id", "")) for t in api(tok, "/team").get("teams") or []))
    if found:
        save(TEAMS_FILE, found)
    return found


def each(tok, team_ids, path):
    """[(team, reply or ApiError)] for path (with {team}) on every team, in parallel."""
    def one(t):
        try:
            return t, api(tok, path.format(team=t))
        except ApiError as e:
            return t, e
    with ThreadPoolExecutor(max_workers=min(4, len(team_ids) or 1)) as pool:
        return list(pool.map(one, team_ids))


def running(tok, team_ids):
    """(team, entry) of the running timer, or (None, None). Raises when no team answered."""
    replies = each(tok, team_ids, "/team/{team}/time_entries/current")
    for t, r in replies:
        if isinstance(r, dict) and isinstance(r.get("data"), dict):
            return t, r["data"]
    errors = [r for _, r in replies if isinstance(r, ApiError)]
    if errors and len(errors) == len(replies):
        raise errors[0]
    return None, None


def name_of(e):
    task = e.get("task") if isinstance(e.get("task"), dict) else {}
    return task.get("name") or e.get("description") or "No task"


def url_of(e):
    url = str(e.get("task_url") or (e.get("task") or {}).get("url") or "") if isinstance(e, dict) else ""
    if re.fullmatch(r"https://app\.clickup\.com/[A-Za-z0-9/_.-]+", url):
        return url
    tid = (e.get("task") or {}).get("id") if isinstance(e.get("task"), dict) else ""
    return f"{APP}t/{tid}" if tid and re.fullmatch(r"[A-Za-z0-9_-]+", str(tid)) else ""


def today_entries(tok, team_ids, run_id):
    """[(start_s, seconds, name)] of today's finished entries, all teams. Cached; fetched again
    when the running timer changes, so a just-stopped entry is never missing."""
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    day = midnight.date().isoformat()
    c = load(ENTRIES_FILE, ENTRIES_TTL)
    if isinstance(c, dict) and c.get("day") == day and c.get("run") == run_id and c.get("teams") == team_ids:
        return c["entries"]
    since, now = int(midnight.timestamp() * 1000), int(time.time() * 1000)
    out, failed = [], False
    for _, r in each(tok, team_ids, f"/team/{{team}}/time_entries?start_date={since}&end_date={now}"):
        if isinstance(r, ApiError):
            failed = True
            continue
        for e in r.get("data") or []:
            try:
                start, dur = int(e["start"]) // 1000, int(e.get("duration") or 0) // 1000
            except (KeyError, TypeError, ValueError):
                continue
            if dur > 0:  # a running entry has a negative duration; it's counted live
                out.append([start, dur, clean(name_of(e))])
    if failed:  # keep the last good copy of today over a partial one
        try:
            old = json.load(open(ENTRIES_FILE))
            if old.get("day") == day:
                return old["entries"]
        except (OSError, ValueError, AttributeError):
            pass
    else:
        save(ENTRIES_FILE, {"day": day, "run": run_id, "teams": team_ids, "entries": out})
    return out


def hm(s):
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}"


def hours(s):
    return "0h" if s < 36 else f"{s / 3600:.1f}h"


def long(s):
    h, m = divmod(int(s) // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


def command(script):
    """A menu command running a script next to this one with the same settings."""
    env = " ".join(f"{k}={quote(os.environ[k])}" for k in TOGGLE_SETTINGS if os.environ.get(k))
    return (env + " " if env else "") + "bash " + quote(os.path.join(DIR, script))


FIX = ["---", f"> ClickUp | open {quote(APP)}"]


def need_token():
    done("dim|ClickUp", ["# ClickUp\tNo token", "Set CLICKUP_TOKEN in ~/.config/wingbar/secrets.env",
                         "_ Get a personal token in ClickUp: Settings > Apps",
                         "---", f"> Apps settings | open {quote(APP + 'settings/apps')}",
                         f"> ClickUp | open {quote(APP)}"])


def failed(e):
    if e.status == 401:
        if TEAMS and "orkspace" in str(e):  # "Workspace not authorized": a wrong team ID
            done("dim|ClickUp: check teams", ["# ClickUp\tCheck teams", f"ClickUp: {e}",
                                              "_ Check WINGBAR_CLICKUP_TEAMS, or leave it empty"] + FIX)
        done("dim|ClickUp: token rejected", ["# ClickUp\tToken rejected",
                                             "ClickUp rejected CLICKUP_TOKEN" + (f" ({e})" if str(e) else ""),
                                             "_ Check it in ~/.config/wingbar/secrets.env"] + FIX)
    done("dim|ClickUp: offline", ["# ClickUp\tOffline", "Couldn't reach ClickUp" + (f" ({e})" if e.status else ""),
                                  "_ Tries again on the next run"] + FIX)


def widget():
    tok = token()
    if not tok:
        need_token()
    try:
        team_ids = teams(tok)
        if not team_ids:
            done("dim|ClickUp: no workspace", ["# ClickUp\tNo workspace",
                                               "This token sees no ClickUp workspace"] + FIX)
        _, cur = running(tok, team_ids)
        entries = today_entries(tok, team_ids, str(cur.get("id", "")) if cur else "")
    except ApiError as e:
        failed(e)

    now = int(time.time())
    midnight = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    per_task = defaultdict(int)
    for start, dur, name in entries:
        part = max(0, min(dur, start + dur - midnight))  # only the part after midnight
        per_task[name] += part
    session = 0
    if cur:
        try:
            run_start = int(cur.get("start")) // 1000
        except (TypeError, ValueError):
            run_start = now
        session = max(0, now - run_start)
        per_task[clean(name_of(cur))] += max(0, now - max(run_start, midnight))
    today = sum(per_task.values())

    total = f"{hours(today)}" if not TARGET else f"{hours(today)[:-1]}/{TARGET / 3600:g}h"
    reached = TARGET and today >= TARGET
    if cur:
        task = clean(name_of(cur), 24) + " " if SHOW_TASK else ""
        print(f"{'done' if reached else 'ok'}|{task}{hm(session)} · {total}")
    else:
        print(f"{'done' if reached else 'dim'}|{total}")

    menu = [f"# ClickUp\tToday {total if TARGET else long(today)}"]
    if cur:
        menu.append(f"▶ {label(name_of(cur), 34)}\t{hm(session)}")
        menu.append(f"_ running since {datetime.fromtimestamp(now - session):%H:%M}")
    else:
        menu.append("No timer running")
    menu.append(f"## Today\t{long(today)}" + (f" of {TARGET / 3600:g}h" if TARGET else ""))
    if TARGET:
        menu.append(f"~{min(100, round(today * 100 / TARGET))} {'green' if reached else 'magenta'}")
        if reached:
            menu.append("_ daily target reached")
        else:
            left = TARGET - today
            menu.append(f"_ {long(left)} to go" + (f" · done at {datetime.fromtimestamp(now + left):%H:%M}"
                                                   if cur else ""))
    top = sorted(((n, s) for n, s in per_task.items() if s >= 60), key=lambda kv: -kv[1])
    menu += [f"{label(n)}\t{long(s)}" for n, s in top[:5]]
    if len(top) > 5:
        menu.append(f"{len(top) - 5} more\t{long(sum(s for _, s in top[5:]))}")
    if not top:
        menu.append("_ nothing tracked yet today")
    menu.append("---")
    if cur:
        menu.append(f"> Stop timer | {command('clickup_toggle.sh')}")
        if url_of(cur):
            menu.append(f"> Open task | open {quote(url_of(cur))}")
    else:
        menu.append(f"> Start timer | {command('clickup_toggle.sh')}")
    menu.append(f"> ClickUp | open {quote(APP)}")
    for m in menu:
        print("menu: " + m)


def notify(message):
    subprocess.run([OSASCRIPT, "-e", "on run argv", "-e",
                    'display notification (item 1 of argv) with title "ClickUp"', "-e", "end run",
                    message], capture_output=True, timeout=5)


def toggle():
    tok = token()
    if not tok:
        notify("Set CLICKUP_TOKEN in ~/.config/wingbar/secrets.env")
        return
    cur = None
    try:
        team_ids = teams(tok)
        if not team_ids:
            notify("This token sees no ClickUp workspace")
            return
        team, cur = running(tok, team_ids)
        if cur:
            api(tok, f"/team/{team}/time_entries/stop", "POST", {})
        else:
            # Against a task: basic time tracking. Without one: ClickUp may need a plan that
            # allows timers without a task.
            body = {"tid": START_TASK} if START_TASK else {"description": "Started from wingbar"}
            api(tok, f"/team/{START_TEAM or team_ids[0]}/time_entries/start", "POST", body)
    except ApiError as e:
        notify(f"Couldn't {'stop' if cur else 'start'} the timer: {e}")
    forget(ENTRIES_FILE)


def open_task():
    tok, url = token(), ""
    if tok:
        try:
            _, cur = running(tok, teams(tok))
            url = url_of(cur) if cur else ""
        except ApiError:
            pass
    subprocess.run([OPEN, url or APP], capture_output=True, timeout=10)


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    {"toggle": toggle, "open": open_task}.get(mode, widget)()
