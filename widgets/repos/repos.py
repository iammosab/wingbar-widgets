"""GitHub repo stats for wingbar: release downloads, traffic and stars of a few repos.

Run by repos.sh (which checks the settings and tools). GitHub keeps traffic for 14 days
only, so each day's views and clones, and each day's download total, are kept in a small
history file: that gives downloads "today" and views since tracking began.
"""

import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

GH = os.environ.get("GH") or "gh"
REPOS = [r for r in os.environ.get("WINGBAR_REPOS", "").split() if r][:8]
HOST = os.environ.get("GH_HOST") or "github.com"
CACHE = os.path.join(os.environ.get("TMPDIR") or "/tmp", "wingbar-repos")
STATE = os.path.join(os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state"), "wingbar-repos")
HISTORY = os.path.join(STATE, "history.json")


def setting(name, default, lo, hi):
    try:
        return max(lo, min(hi, int(os.environ.get(name) or default)))
    except ValueError:
        return default


TTL = setting("WINGBAR_REPOS_TTL", 900, 60, 86400)
LABEL = os.environ.get("WINGBAR_REPOS_LABEL") or "both"


def clean(s, n=60):
    """Text from GitHub for a menu line: no `|`, tabs or control characters, no leading
    marker that would restyle the row, and at most n characters."""
    s = re.sub(r"[|\x00-\x1f\x7f]", " ", str(s or "")).strip().lstrip("#_>~- ").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def quote(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


def num(n):
    return f"{n:,}" if isinstance(n, int) else "?"


def gh(path):
    """(json, error): one GitHub API reply through gh."""
    try:
        p = subprocess.run([GH, "api", "-H", "Accept: application/vnd.github+json", path],
                           capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as e:
        return None, str(e)
    if p.returncode != 0:
        err = (p.stderr or p.stdout).strip().splitlines()
        return None, clean(err[-1] if err else "gh failed", 80)
    try:
        return json.loads(p.stdout), None
    except ValueError:
        return None, "unreadable reply"


def fetch(repo):
    """Everything shown for one repo (cached for TTL; the last answer is kept on failure)."""
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    path = os.path.join(CACHE, repo.replace("/", "_") + ".json")
    try:
        if time.time() - os.path.getmtime(path) < TTL:
            return json.load(open(path))
    except (OSError, ValueError):
        pass
    info, err = gh(f"repos/{repo}")
    if info is None:
        try:
            old = json.load(open(path))
            old["error"] = err
            return old
        except (OSError, ValueError):
            return {"repo": repo, "error": err}
    out = {"repo": repo, "stars": info.get("stargazers_count"), "forks": info.get("forks_count"),
           "private": bool(info.get("private")), "fetched": time.time()}
    rel, _ = gh(f"repos/{repo}/releases?per_page=100")
    if isinstance(rel, list):
        dls = [(r.get("tag_name"), sum(a.get("download_count") or 0 for a in r.get("assets") or []))
               for r in rel if not r.get("draft")]
        out["downloads"] = sum(n for _, n in dls)
        out["releases"] = len(dls)
        if dls:
            out["latest"] = [clean(dls[0][0], 30), dls[0][1]]
    for kind in ("views", "clones"):
        t, terr = gh(f"repos/{repo}/traffic/{kind}")
        if isinstance(t, dict):
            out[kind] = {"count": t.get("count") or 0, "uniques": t.get("uniques") or 0,
                         "days": {d["timestamp"][:10]: [d.get("count") or 0, d.get("uniques") or 0]
                                  for d in t.get(kind) or [] if d.get("timestamp")}}
        elif terr and "403" in terr or (terr and "push access" in terr.lower()):
            out["traffic_denied"] = True
    refs, _ = gh(f"repos/{repo}/traffic/popular/referrers")
    if isinstance(refs, list):
        out["referrers"] = [[clean(r.get("referrer"), 24), r.get("count") or 0] for r in refs[:3]]
    tmp = path + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(out, f)
    os.replace(tmp, path)
    return out


def update_history(stats):
    """Merge today's numbers into the history; returns it."""
    try:
        h = json.load(open(HISTORY))
    except (OSError, ValueError):
        h = {}
    today = date.today().isoformat()
    cutoff = (date.today() - timedelta(days=400)).isoformat()
    for s in stats:
        r = h.setdefault(s["repo"], {})
        for kind in ("views", "clones"):
            if kind in s:
                days = r.setdefault(kind, {})
                days.update(s[kind]["days"])
                for d in [d for d in days if d < cutoff]:
                    del days[d]
        if isinstance(s.get("downloads"), int):
            dl = r.setdefault("downloads", {})
            dl[today] = s["downloads"]  # the last total seen each day
            for d in sorted(dl)[:-60]:
                del dl[d]
    os.makedirs(STATE, mode=0o700, exist_ok=True)
    tmp = HISTORY + ".tmp"
    with open(os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as f:
        json.dump(h, f)
    os.replace(tmp, HISTORY)
    return h


def downloads_today(h, repo, now_total):
    """New downloads since the last total seen before today (0 on the first day)."""
    dl = (h.get(repo) or {}).get("downloads") or {}
    before = [d for d in dl if d < date.today().isoformat()]
    return max(0, now_total - dl[max(before)]) if before and isinstance(now_total, int) else 0


def ago(ts):
    m = int((time.time() - ts) // 60) if ts else -1
    return "just now" if 0 <= m < 1 else f"{m}m ago" if m < 60 else f"{m // 60}h {m % 60:02d}m ago"


def main():
    with ThreadPoolExecutor(max_workers=len(REPOS)) as ex:
        stats = list(ex.map(fetch, REPOS))
    ok = [s for s in stats if "stars" in s]
    if not ok:
        err = next((s.get("error") for s in stats if s.get("error")), "no data")
        level = "dim|Repos: gh not logged in" if "auth" in (err or "").lower() else "dim|Repos ?"
        print(level)
        print(f"menu: # GitHub\tno data")
        print(f"menu: {clean(err, 70)}")
        print("menu: _ run  gh auth login  if you haven't")
        return
    h = update_history(ok)

    total_dl = sum(s.get("downloads") or 0 for s in ok)
    today_dl = sum(downloads_today(h, s["repo"], s.get("downloads")) for s in ok)
    views = sum((s.get("views") or {}).get("count", 0) for s in ok)
    new = today_dl > 0
    dl_text = f"↓{num(total_dl)}" + (f" +{today_dl}" if today_dl else "")
    label = {"downloads": dl_text, "views": f"{num(views)} views"}.get(LABEL, f"{dl_text} · {num(views)} views")
    print(f"{'up' if new else 'ok'}|{label}")

    menu = [f"# GitHub\t{len(ok)} repo{'s' if len(ok) != 1 else ''} · traffic of 14 days"]
    top = max([(s.get("views") or {}).get("count", 0) for s in ok] + [1])
    order = sorted(stats, key=lambda s: -((s.get("views") or {}).get("count", 0) + 10 * (s.get("downloads") or 0)))
    for s in order:
        repo = s["repo"]
        url = f"https://{HOST}/{repo}"
        name = clean(repo.split("/", 1)[1], 30)
        if "stars" not in s:
            menu += [f"## {name}\tunavailable | open {quote(url)}", f"_ {clean(s.get('error'), 70)}"]
            continue
        menu.append(f"## {name}\t★ {num(s['stars'])} · forks {num(s.get('forks'))} | open {quote(url)}")
        if s.get("releases"):
            d = downloads_today(h, repo, s.get("downloads"))
            menu.append(f"Downloads\t{num(s['downloads'])}{f' · +{d} today' if d else ''} | open {quote(url + '/releases')}")
            if s.get("latest"):
                n = s["releases"]
                menu.append(f"_ latest {s['latest'][0]}: {num(s['latest'][1])} · {n} release{'s' if n != 1 else ''}")
        if s.get("traffic_denied"):
            menu.append("Traffic\tneeds push access")
            continue
        v, c = s.get("views"), s.get("clones")
        if v:
            menu.append(f"Views\t{num(v['count'])} · {num(v['uniques'])} unique | open {quote(url + '/graphs/traffic')}")
            if v["count"]:
                menu.append(f"~{round(100 * v['count'] / top)} blue")
        if c:
            menu.append(f"Clones\t{num(c['count'])} · {num(c['uniques'])} unique")
        tracked = sum(n for n, _ in ((h.get(repo) or {}).get("views") or {}).values())
        since = min(((h.get(repo) or {}).get("views") or {"": 0}).keys() or [""])
        bits = []
        if s.get("referrers"):
            bits.append("from " + ", ".join(f"{r} {n}" for r, n in s["referrers"]))
        # only once the history reaches past GitHub's own 14 days
        if since and since < (date.today() - timedelta(days=16)).isoformat() and tracked > (v or {}).get("count", 0):
            bits.append(f"{num(tracked)} views since {datetime.fromisoformat(since).strftime('%-d %b')}")
        if bits:
            menu.append("_ " + " · ".join(bits))
        if s.get("error"):
            menu.append(f"_ couldn't update: {clean(s['error'], 50)}")
    oldest = min((s.get("fetched") or 0) for s in ok)
    menu += [f"_ updated {ago(oldest)}", "---",
             f"> Refresh | rm -f {quote(CACHE)}/*.json",
             f"> GitHub | open {quote('https://' + HOST + '/' + REPOS[0].split('/')[0] + '?tab=repositories')}"]
    for m in menu:
        print("menu: " + m)


if __name__ == "__main__":
    sys.exit(main())
