"""Claude plan usage for wingbar (the numbers Claude Code's /usage shows).

Reads Claude Code's own OAuth access token (macOS Keychain, or its credentials
file) at run time, asks Anthropic's usage endpoint, and prints wingbar's script
protocol. The token is never written anywhere, never refreshed and never put on
a command line (it goes to curl on stdin). Only the usage reply, the plan name
and which Keychain item held the token are cached, in ${TMPDIR:-/tmp}/wingbar-claude/.
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

SECURITY = os.environ.get("WINGBAR_SECURITY") or "security"
CURL = os.environ.get("WINGBAR_CURL") or "curl"
API = "https://api.anthropic.com/api/oauth"
USAGE_PAGE = "https://claude.ai/settings/usage"
SERVICE = "Claude Code-credentials"  # also "Claude Code-credentials-<hash>", one per config dir
CACHE = os.path.join(os.environ.get("TMPDIR") or "/tmp", "wingbar-claude")
USAGE = os.path.join(CACHE, "usage.json")
PROFILE = os.path.join(CACHE, "profile.json")
ITEM = os.path.join(CACHE, "keychain_item")
USAGE_TTL = 60          # seconds: manual refreshes don't hit the API
STALE_OK = 3600         # show a cached reply this old when the API can't be reached
PROFILE_TTL = 86400


def setting(name, default):
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


WARN = setting("WINGBAR_CLAUDE_WARN", 75)
ALERT = setting("WINGBAR_CLAUDE_ALERT", 90)
SHOW_PLAN = os.environ.get("WINGBAR_CLAUDE_PLAN", "0") == "1"


def clean(s):
    """Text for a menu title: no '|' (it would start a command) and no control characters."""
    return re.sub(r"[|\x00-\x1f\x7f]", "", str(s)).strip()


def quote(s):
    return "'" + s.replace("'", "'\\''") + "'"


def done(line, menu=()):
    print(line)
    for m in menu:
        print("menu: " + m)
    sys.exit(0)


def run(args, stdin=None, timeout=10):
    try:
        p = subprocess.run(args, input=stdin, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def age(path):
    try:
        return time.time() - os.path.getmtime(path)
    except OSError:
        return float("inf")


def write_private(path, text):
    os.makedirs(CACHE, mode=0o700, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.replace(tmp, path)


# ── Credentials ──────────────────────────────────────────────────────────────

def parse_creds(raw):
    """(token, expires_ms) from Claude Code's credentials JSON, or None."""
    raw = (raw or "").strip()
    if re.fullmatch(r"(?:[0-9a-fA-F]{2})+", raw):  # `security -w` prints odd bytes as hex
        try:
            raw = bytes.fromhex(raw).decode()
        except ValueError:
            return None
    try:
        o = json.loads(raw).get("claudeAiOauth") or {}
        tok, exp = o.get("accessToken") or "", int(o.get("expiresAt") or 0)
    except (ValueError, AttributeError, TypeError):
        return None
    # Only token characters: it goes into a curl config line.
    if not re.fullmatch(r"[A-Za-z0-9._~+/=-]+", tok):
        return None
    return tok, exp


def from_keychain(svc, acct):
    code, out = run([SECURITY, "find-generic-password", "-s", svc, "-a", acct, "-w"])
    return parse_creds(out) if code == 0 else None


def keychain_items():
    """(service, account) of every Claude Code item in the login keychain (names only)."""
    keychain = os.path.expanduser("~/Library/Keychains/login.keychain-db")
    _, out = run([SECURITY, "dump-keychain", keychain], timeout=10)
    items, svc, acct = set(), None, None
    for line in out.splitlines() + ["keychain:"]:
        if line.startswith("keychain:"):
            if svc:
                items.add((svc, acct or ""))
            svc, acct = None, None
            continue
        m = re.search(r'"(svce|acct)"<blob>="(.*)"\s*$', line)
        if not m:
            continue
        if m.group(1) == "svce" and m.group(2).startswith(SERVICE):
            svc = m.group(2)
        elif m.group(1) == "acct":
            acct = m.group(2)
    return sorted(items)


def credentials():
    """(token, expires_ms) with the latest expiry, or None when not signed in."""
    now_ms = time.time() * 1000
    # Fast path: the item that worked last time.
    try:
        svc, acct = open(ITEM).read().rstrip("\n").split("\t", 1)
        c = from_keychain(svc, acct)
        if c and c[1] > now_ms:
            return c
    except (OSError, ValueError):
        pass
    best, best_item = None, None
    for svc, acct in keychain_items():
        c = from_keychain(svc, acct)
        if c and (best is None or c[1] > best[1]):
            best, best_item = c, (svc, acct)
    cred_file = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR") or os.path.expanduser("~/.claude"),
                             ".credentials.json")
    try:
        c = parse_creds(open(cred_file).read())
        if c and (best is None or c[1] > best[1]):
            best, best_item = c, None
    except OSError:
        pass
    if best_item:
        write_private(ITEM, "\t".join(best_item) + "\n")
    else:
        forget_item()
    return best


def forget_item():
    try:
        os.remove(ITEM)
    except OSError:
        pass


# ── API ──────────────────────────────────────────────────────────────────────

def get(path, token):
    """(http status, body). The token reaches curl on stdin, not in its arguments."""
    config = (f'header = "Authorization: Bearer {token}"\n'
              'header = "anthropic-beta: oauth-2025-04-20"\n')
    code, out = run([CURL, "-sS", "--max-time", "8", "-K", "-", "-w", "\n%{http_code}", API + path],
                    stdin=config, timeout=12)
    body, _, status = out.rpartition("\n")
    return (int(status) if status.isdigit() else 0), body


def load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return None


def plan_name(token):
    if age(PROFILE) >= PROFILE_TTL:
        status, body = get("/profile", token)
        try:
            org = json.loads(body).get("organization") or {} if status == 200 else None
        except ValueError:
            org = None
        if org is not None:  # keep the plan only; the rest of the profile is never stored
            plan = org.get("plan_display_name") or \
                {"claude_max": "Max", "claude_pro": "Pro"}.get(org.get("organization_type"), "")
            write_private(PROFILE, json.dumps({"plan": plan}))
    return clean((load(PROFILE) or {}).get("plan") or "")


# ── Formatting ───────────────────────────────────────────────────────────────

def when(iso):
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return ""
    dt = (dt + timedelta(seconds=30)).replace(second=0, microsecond=0)
    secs = (dt - datetime.now(dt.tzinfo)).total_seconds()
    if secs < 0:
        return ""
    if secs < 86400:
        h, m = divmod(int(secs // 60), 60)
        return f"resets in {h}h {m:02d}m" if h else f"resets in {m}m"
    return "resets " + dt.strftime("%a %-d %b %H:%M" if secs > 6 * 86400 else "%a %H:%M")


def pct(x):
    try:
        return round(float(x))
    except (TypeError, ValueError):
        return None


def limits(d):
    """[(name, percent, resets_at, severity)] for every limit the account has."""
    rows = []
    five = d.get("five_hour")
    if isinstance(five, dict) and pct(five.get("utilization")) is not None:
        rows.append(("Session (5h)", pct(five["utilization"]), five.get("resets_at"), None))
    shares = {x.get("limit_index"): x for x in d.get("weekly_scoped_shares") or [] if isinstance(x, dict)}
    listed = d.get("limits") if isinstance(d.get("limits"), list) else []
    for i, lim in enumerate(listed):
        if not isinstance(lim, dict) or pct(lim.get("percent")) is None:
            continue
        if lim.get("kind") in ("session", "five_hour"):
            continue
        scope = lim.get("scope") or {}
        model = (scope.get("model") or {}).get("display_name") if isinstance(scope.get("model"), dict) else None
        surface = scope.get("surface")
        surface = surface.get("display_name") if isinstance(surface, dict) else surface
        name = "Week · " + clean(model or surface or "all models")
        share = (shares.get(i) or {}).get("allowance_percent_of_weekly")
        if share:
            name += f" (up to {share}% of the week)"
        rows.append((name, pct(lim["percent"]), lim.get("resets_at"), lim.get("severity")))
    if not listed:  # older replies
        for key, name in (("seven_day", "Week · all models"), ("seven_day_opus", "Week · Opus"),
                          ("seven_day_sonnet", "Week · Sonnet")):
            b = d.get(key)
            if isinstance(b, dict) and pct(b.get("utilization")) is not None:
                rows.append((name, pct(b["utilization"]), b.get("resets_at"), None))
    return rows


def credits_line(d):
    sp = d.get("spend") if isinstance(d.get("spend"), dict) else {}
    if not sp.get("enabled"):
        return "Usage credits: off"

    def money(x):
        try:
            return f"${x['amount_minor'] / 10 ** x.get('exponent', 2):,.2f}"
        except (TypeError, KeyError, ZeroDivisionError):
            return ""
    used, cap = money(sp.get("used")), money(sp.get("limit"))
    return "Usage credits: " + (f"{used} of {cap}" if cap else used or "on")


def main():
    actions = ["---", f"Open usage page | open {quote(USAGE_PAGE)}"]
    creds = credentials()
    if not creds:
        done("dim|Claude: sign in", ["Not signed in to Claude Code",
                                     "Run  claude  in a terminal and sign in"] + actions)
    token, expires = creds
    if expires <= time.time() * 1000:
        done("dim|Claude: login expired", ["Claude Code's login has expired",
                                           "Use Claude Code once to renew it"] + actions)

    note = ""
    if age(USAGE) >= USAGE_TTL:
        status, body = get("/usage", token)
        ok = False
        if status == 200:
            try:
                ok = isinstance(json.loads(body), dict)
            except ValueError:
                pass
        if ok:
            write_private(USAGE, body)
        elif status == 401:
            forget_item()
            done("dim|Claude: login expired", ["Claude Code's login was rejected",
                                               "Run  claude  in a terminal and sign in again"] + actions)
        elif age(USAGE) < STALE_OK:
            note = "Couldn't reach Anthropic: showing " + \
                datetime.fromtimestamp(os.path.getmtime(USAGE)).strftime("%H:%M")
        else:
            why = "rate limited" if status == 429 else "offline"
            done(f"dim|Claude: {why}", ["Couldn't reach Anthropic's usage endpoint",
                                        "Tries again on the next run"] + actions)
    d = load(USAGE) or {}
    rows = limits(d)
    if not rows:
        done("dim|Claude", ["No usage data yet"] + actions)

    plan = plan_name(token)
    worst = max(p for _, p, _, _ in rows)
    sev = {s for *_, s in rows}
    level = "alert" if worst >= ALERT or "critical" in sev else \
        "warn" if worst >= WARN or "warning" in sev else "ok"
    print(f"{level}|{plan + ' · ' if SHOW_PLAN and plan else ''}{worst}%")

    menu = [f"Claude {plan} plan" if plan else "Claude plan limits"]
    for name, p, reset, _ in rows:
        menu.append(f"{name}: {p}%" + (f" · {when(reset)}" if when(reset) else ""))
    menu.append(credits_line(d))
    if worst >= 100:
        menu.append("Limit reached" + (": now using usage credits" if "credits: off" not in menu[-1]
                                       else ": turn on usage credits to keep going"))
    if note:
        menu.append(note)
    menu += actions
    menu.append(f"Refresh now | rm -f {quote(USAGE)}")
    for m in menu:
        print("menu: " + m)


if __name__ == "__main__":
    main()
