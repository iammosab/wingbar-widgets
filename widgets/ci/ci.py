#!/usr/bin/env python3
"""GitHub Actions widget for wingbar (called by ci.sh, which checks the settings and tools).

Prints wingbar's script protocol: line 1 `level|label`, then `menu:` lines.
  ok    newest finished run passed       "CI ✓ 7/8" (today's passed/finished runs)
  warn  a run is in progress or queued   "CI ▶ Tests +1"
  alert newest finished run failed       "CI ✗ Tests"
  dim   no data / gh problem             "CI ?" with a menu reading saying why

GitHub answers are cached in ${TMPDIR:-/tmp}/wingbar-ci/ for WINGBAR_CI_TTL seconds (default 20),
so polling often costs nothing. If GitHub can't be reached, the last good answer (up to 10 min old)
is shown with a "?" after the label. gh handles authentication; no token is read or printed here.
"""
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from datetime import datetime, timezone

GH = os.environ.get("GH") or "gh"
REPO = os.environ.get("WINGBAR_CI_REPO", "")
BRANCH = os.environ.get("WINGBAR_CI_BRANCH", "").strip()
HOST = os.environ.get("GH_HOST", "").strip() or "github.com"


def setting_int(name, default, lo, hi):
    try:
        return max(lo, min(hi, int(os.environ.get(name, default))))
    except ValueError:
        return default


LIMIT = setting_int("WINGBAR_CI_LIMIT", 6, 1, 15)
PR_LIMIT = setting_int("WINGBAR_CI_PRS", 5, 0, 15)
TTL = setting_int("WINGBAR_CI_TTL", 20, 0, 3600)
RUNNERS = os.environ.get("WINGBAR_CI_RUNNERS", "") in ("1", "true", "yes")
FETCH = 50          # runs fetched: enough for "today" in most repos
STALE_OK = 600      # show the last good answer this long when GitHub can't be reached
TIMEOUT = 8         # seconds per gh call (they run in parallel)

if not re.fullmatch(r"[A-Za-z0-9.-]+(:[0-9]+)?", HOST):
    HOST = "github.com"
BASE = f"https://{HOST}/{REPO}"

CACHE = os.path.join(os.environ.get("TMPDIR") or "/tmp", "wingbar-ci")
KEY = re.sub(r"[^A-Za-z0-9._-]", "_", f"{HOST}_{REPO}_{BRANCH}")

ENV = dict(os.environ, GH_PROMPT_DISABLED="1", GH_NO_UPDATE_NOTIFIER="1", GH_SPINNER_DISABLED="1",
           NO_COLOR="1", CLICOLOR="0")

URL_RE = re.compile(r"https://[A-Za-z0-9.-]+(:[0-9]+)?/[A-Za-z0-9._~/%-]*")


# ── helpers ───────────────────────────────────────────────────────────────────
def clean(s, n=None):
    """Text GitHub controls, made safe for a menu title: no `|`, no control characters."""
    s = "".join(c for c in str(s or "") if c != "|" and unicodedata.category(c) not in ("Cc", "Cf", "Zl", "Zp"))
    s = " ".join(s.split())
    if n and len(s) > n:
        s = s[: n - 1].rstrip() + "…"
    return s


def open_cmd(url):
    """`open '<url>'` for a plain https URL, else None (the item becomes a reading)."""
    return f"open '{url}'" if url and URL_RE.fullmatch(url) else None


def ts(s):
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def dur(sec):
    if sec is None or sec < 0:
        return "–"
    sec = int(sec)
    if sec < 60:
        return f"{sec}s"
    if sec < 3600:
        return f"{sec // 60}m{sec % 60:02d}s"
    return f"{sec // 3600}h{sec % 3600 // 60:02d}m"


def ago(sec):
    sec = int(max(0, sec))
    return f"{sec}s" if sec < 60 else f"{sec // 60}m" if sec < 3600 else f"{sec // 3600}h"


def path(kind):
    return os.path.join(CACHE, f"{KEY}.{kind}.json")


def load(kind):
    try:
        with open(path(kind)) as f:
            d = json.load(f)
        return d if isinstance(d, dict) and "t" in d else None
    except (OSError, ValueError):
        return None


def save(kind, data):
    try:
        os.makedirs(CACHE, mode=0o700, exist_ok=True)
        tmp = f"{path(kind)}.{os.getpid()}.tmp"
        with open(tmp, "w") as f:
            json.dump({"t": time.time(), "data": data}, f)
        os.replace(tmp, path(kind))
    except OSError:
        pass


def why(err):
    """A short, human reason from gh's stderr (never contains a token)."""
    e = err.lower()
    if "timed out" in e:
        return "GitHub didn't answer in time"
    if "gh auth login" in e or "not logged" in e or "authentication" in e or "bad credentials" in e or "401" in e:
        return "gh is not logged in: run gh auth login"
    if "could not resolve to a repository" in e or "404" in e or "not found" in e:
        return "Repo not found (check WINGBAR_CI_REPO; private repos need gh access)"
    if "rate limit" in e:
        return "GitHub rate limit reached; try again later"
    line = next((x for x in err.splitlines() if x.strip()), "gh failed")
    return clean(line, 80)


# ── fetch (parallel gh calls, cached) ─────────────────────────────────────────
def gh_args():
    runs = ["run", "list", "-R", REPO, "-L", str(FETCH), "--json",
            "databaseId,workflowName,name,status,conclusion,headBranch,displayTitle,event,createdAt,startedAt,updatedAt,url"]
    if BRANCH:
        runs += ["--branch", BRANCH]
    jobs = {"runs": runs}
    if PR_LIMIT:
        prs = ["pr", "list", "-R", REPO, "-L", str(PR_LIMIT), "--json", "number,title,url,isDraft,statusCheckRollup",
               "--jq", "[.[] | {number, title, url, isDraft, checks: [.statusCheckRollup[]? | "
                       "{status: (.status // \"\"), conclusion: (.conclusion // \"\"), state: (.state // \"\")}]}]"]
        if BRANCH:
            prs += ["--base", BRANCH]
        jobs["prs"] = prs
    if RUNNERS:
        jobs["runners"] = ["api", f"repos/{REPO}/actions/runners?per_page=100",
                           "--jq", "[.runners[] | {name, status, busy}]"]
    return jobs


def fetch(kinds):
    """Run the gh calls for `kinds` in parallel. Returns {kind: (data or None, error or None)}."""
    procs, out = {}, {}
    for kind in kinds:
        try:
            procs[kind] = subprocess.Popen([GH] + gh_args()[kind], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=True, env=ENV)
        except OSError as e:
            out[kind] = (None, clean(e, 80))
    deadline = time.time() + TIMEOUT
    for kind, p in procs.items():
        try:
            so, se = p.communicate(timeout=max(0.1, deadline - time.time()))
        except subprocess.TimeoutExpired:
            p.kill()
            p.communicate()
            out[kind] = (None, "timed out")
            continue
        if p.returncode != 0:
            out[kind] = (None, se or so or "gh failed")
            continue
        try:
            data = json.loads(so)
            save(kind, data)
            out[kind] = (data, None)
        except ValueError:
            out[kind] = (None, "gh printed something that isn't JSON")
    return out


def backoff(kind, err):
    """Seconds before a failed call is tried again (a missing permission won't fix itself soon)."""
    e = (err or "").lower()
    if kind == "runners" and ("403" in e or "permission" in e or "admin" in e):
        return 600
    return max(TTL, 30)


def get_all():
    """{kind: {"data", "age", "err"}} from the cache, fetching what is older than TTL."""
    now = time.time()
    kinds = list(gh_args())
    cached = {k: load(k) for k in kinds}
    failed = {k: load(f"{k}.fail") for k in kinds}
    stale = [k for k in kinds
             if (not cached[k] or now - cached[k]["t"] >= TTL)
             and not (failed[k] and now - failed[k]["t"] < backoff(k, failed[k].get("data")))]
    fresh = {}
    if stale:
        os.makedirs(CACHE, mode=0o700, exist_ok=True)
        lock = path("lock")
        try:
            os.mkdir(lock)
        except FileExistsError:
            # another run is fetching: use the cache; break a lock left by a killed run
            try:
                if now - os.stat(lock).st_mtime > 3 * TIMEOUT:
                    os.rmdir(lock)
            except OSError:
                pass
        except OSError:
            pass
        else:
            try:
                fresh = fetch(stale)
            finally:
                try:
                    os.rmdir(lock)
                except OSError:
                    pass
    res = {}
    for k in kinds:
        c, f = cached[k], failed[k]
        data, err = fresh.get(k, (None, None))
        if data is not None:
            try:
                os.remove(path(f"{k}.fail"))
            except OSError:
                pass
            res[k] = {"data": data, "age": 0, "err": None}
            continue
        if k in fresh:
            save(f"{k}.fail", err)
        elif f and (not c or f["t"] > c["t"]):
            err = f.get("data")
        if c and now - c["t"] < (STALE_OK if err else max(STALE_OK, TTL)):
            res[k] = {"data": c["data"], "age": now - c["t"], "err": err}
        else:
            res[k] = {"data": None, "age": None, "err": err}
    return res


# ── view ──────────────────────────────────────────────────────────────────────
NEUTRAL = ("skipped", "cancelled", "neutral", "stale")
ACTIVE = ("in_progress", "queued", "waiting", "pending", "requested")


def mark(r):
    st, c = r.get("status"), r.get("conclusion")
    if st == "in_progress":
        return "▶"
    if st in ACTIVE:
        return "◌"
    if c == "success":
        return "✓"
    if c in NEUTRAL:
        return "–"
    return "✗"


def rollup(checks):
    bad = {"FAILURE", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED", "STARTUP_FAILURE", "ERROR"}
    if not checks:
        return "no checks"
    if any((c.get("conclusion") or c.get("state") or "").upper() in bad for c in checks):
        return "failing"
    if any((c.get("status") or "").upper() not in ("", "COMPLETED") or (c.get("state") or "").upper() == "PENDING"
           for c in checks):
        return "pending"
    return "passing"


def today_stats(runs):
    today = datetime.now().astimezone().date()
    day = [r for r in runs if ts(r.get("createdAt")) and datetime.fromtimestamp(ts(r["createdAt"])).date() == today]
    real = [r for r in day if r.get("status") == "completed" and r.get("conclusion") not in NEUTRAL]
    ok = sum(1 for r in real if r.get("conclusion") == "success")
    return len(day), ok, len(real)


def run_line(r, now):
    wf = clean(r.get("workflowName") or r.get("name") or "run", 24)
    who = r.get("displayTitle") if (BRANCH or r.get("event") == "pull_request") else r.get("headBranch")
    if who and clean(who) == clean(r.get("workflowName") or r.get("name")):
        who = r.get("event")  # scheduled runs are titled with the workflow's name
    start = ts(r.get("startedAt") or r.get("createdAt"))
    if r.get("status") == "completed":
        end = ts(r.get("updatedAt"))
        d = dur(end - start) if start and end else "–"
    elif r.get("status") == "in_progress":
        d = dur(now - start) if start else "–"
    else:
        d = "queued"
    return f"{mark(r)} {wf} · {clean(who, 40)} · {d}" if who else f"{mark(r)} {wf} · {d}"


def menu(title, url=None):
    cmd = open_cmd(url) if url else None
    return f"menu: {title} | {cmd}" if cmd else f"menu: {title}"


def main():
    now = time.time()
    got = get_all()
    runs_r = got["runs"]
    runs = runs_r["data"]
    lines = []

    if runs is None:
        reason = why(runs_r["err"] or "no data yet")
        short = "gh not logged in" if "not logged in" in reason else "repo?" if reason.startswith("Repo not") else "?"
        print(f"dim|CI {short}")
        print(menu(clean(REPO)))
        print(menu(reason))
        print("menu: ---")
        print(menu("Open Actions", f"{BASE}/actions"))
        return

    if not isinstance(runs, list):
        runs = []
    active = [r for r in runs if r.get("status") in ACTIVE]
    done = [r for r in runs if r.get("status") == "completed" and r.get("conclusion") not in NEUTRAL]
    last = done[0] if done else None
    n_day, n_ok, n_real = today_stats(runs)
    stale = "?" if runs_r["err"] else ""

    # line 1
    running = [r for r in active if r.get("status") == "in_progress"]
    if running:
        more = f" +{len(active) - 1}" if len(active) > 1 else ""
        head = f"warn|CI ▶ {clean(running[0].get('workflowName') or running[0].get('name'), 14)}{more}"
    elif active:
        head = f"warn|CI ◌ {len(active)} queued"
    elif last and last.get("conclusion") != "success":
        head = f"alert|CI ✗ {clean(last.get('workflowName') or last.get('name'), 14)}"
    elif last:
        head = f"ok|CI ✓ {n_ok}/{n_real}" if n_real else "ok|CI ✓"
    else:
        head = "dim|CI –"
    lines.append(head + stale)

    # readings
    lines.append(menu(clean(f"{REPO} · {BRANCH}" if BRANCH else REPO)))
    if runs_r["err"]:
        lines.append(menu(f"{why(runs_r['err'])}; showing data from {ago(runs_r['age'])} ago"))
    if n_day:
        plus = "+" if n_day >= len(runs) == FETCH else ""
        rate = f" · {n_ok}/{n_real} passed ({round(100 * n_ok / n_real)}%)" if n_real else ""
        lines.append(menu(f"Today: {n_day}{plus} run{'' if n_day == 1 else 's'}{rate}"))
    else:
        lines.append(menu("Today: no runs"))
    if active:
        lines.append(menu(f"Running: {len(running)} · queued: {len(active) - len(running)}"))

    if RUNNERS:
        rr = got["runners"]
        if rr["data"] is None:
            e = (rr["err"] or "").lower()
            lines.append(menu("Runners: needs admin access to the repo" if "403" in e or "permission" in e
                              else f"Runners: {why(rr['err'] or 'no data')}"))
        else:
            rs = rr["data"] if isinstance(rr["data"], list) else []
            on = [x for x in rs if x.get("status") == "online"]
            busy = sum(1 for x in on if x.get("busy"))
            off = [x for x in rs if x.get("status") != "online"]
            if not rs:
                lines.append(menu("Runners: no self-hosted runners"))
            else:
                lines.append(menu(f"Runners: {len(on)} online ({busy} busy) · {len(off)} offline",
                                  f"{BASE}/settings/actions/runners"))
                for x in off[:3]:
                    lines.append(menu(f"  offline: {clean(x.get('name'), 30)}"))

    # recent runs
    if runs:
        lines.append("menu: ---")
        lines.append(menu("Recent runs"))
        for r in runs[:LIMIT]:
            lines.append(menu(run_line(r, now), r.get("url")))
    else:
        lines.append(menu("No workflow runs yet"))

    # open PRs
    if PR_LIMIT:
        pr = got["prs"]
        prs = pr["data"] if isinstance(pr["data"], list) else None
        lines.append("menu: ---")
        if prs is None:
            lines.append(menu(f"Pull requests: {why(pr['err'] or 'no data')}"))
        elif not prs:
            lines.append(menu("No open pull requests"))
        else:
            lines.append(menu(f"Open pull requests ({len(prs)}{'+' if len(prs) >= PR_LIMIT else ''})"))
            for p in prs[:PR_LIMIT]:
                state = rollup(p.get("checks") or [])
                m = {"passing": "✓", "failing": "✗", "pending": "◌"}.get(state, "·")
                draft = " (draft)" if p.get("isDraft") else ""
                lines.append(menu(f"{m} #{p.get('number')} {clean(p.get('title'), 40)}{draft} · {state}", p.get("url")))

    # actions
    lines.append("menu: ---")
    lines.append(menu("Open Actions", f"{BASE}/actions"))
    lines.append(menu("Open Pull Requests", f"{BASE}/pulls"))

    print("\n".join(lines[:60]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # never fail noisily in the bar
        print("dim|CI ?")
        print(menu(f"Widget error: {clean(type(e).__name__)}"))
    sys.exit(0)
